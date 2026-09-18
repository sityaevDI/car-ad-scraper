"""Unified backfill for listings created before a detail-only field existed (see
app/scraping/detail_only_fields.py for the registry and what "detail-only" means, and
pipeline.py's `_enrich_with_detail` for the "on creation" counterpart this mirrors).

One detail-page fetch per listing backfills every requested field still missing on that row,
instead of a separate full pass — and re-fetch of the same listing's detail page — per field.
Supersedes the old backfill_interior_material.py / backfill_air_condition.py /
backfill_drive_type.py, which each queried and fetched independently even though a single listing
missing e.g. both interior_material and drive_type only ever needed one fetch to fill both.

Usage:
    python -m app.scraping.backfill                                    # every registered field
    python -m app.scraping.backfill --fields drive_type,interior_material
    python -m app.scraping.backfill --source polovniautomobili --limit 500
"""

import argparse
import asyncio

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.listings.repository import ListingRepository
from app.models.listing import Listing, ListingStatus
from app.models.source import Source
from app.scraping.detail_only_fields import DETAIL_ONLY_FIELDS, DetailOnlyField
from app.scraping.fetch_outcome import FetchBlockedError, ParserError
from app.scraping.rate_limit import get_scrape_rate_limit
from app.sources.base import SourceListingRef
from app.sources.registry import get_source_adapter


async def _backfill(
    session: AsyncSession, source_code: str, fields: list[DetailOnlyField], limit: int | None
) -> None:
    source = (await session.execute(select(Source).where(Source.code == source_code))).scalar_one()
    rate_limit = await get_scrape_rate_limit(session)
    adapter = get_source_adapter(
        source_code,
        delay=rate_limit.request_delay_seconds,
        jitter=rate_limit.request_jitter_seconds,
        network_error_retry_delay=rate_limit.network_error_retry_delay_seconds,
    )
    repository = ListingRepository(session)

    stmt = select(Listing).where(
        Listing.source_id == source.id,
        Listing.status == ListingStatus.ACTIVE,
        or_(*(field.missing for field in fields)),
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    listings = (await session.execute(stmt)).scalars().all()
    field_names = ", ".join(field.name for field in fields)
    print(f"{len(listings)} listing(s) missing at least one of: {field_names}")

    updated = skipped = 0
    per_field_updates = {field.name: 0 for field in fields}
    for i, listing in enumerate(listings, start=1):
        ref = SourceListingRef(external_id=listing.external_id, url=listing.canonical_url)
        try:
            detail = await adapter.fetch_listing(ref)
        except (FetchBlockedError, ParserError, RuntimeError) as exc:
            # Same best-effort posture as _enrich_with_detail: one slow/blocked listing shouldn't
            # abort the whole backfill.
            print(f"  [{i}/{len(listings)}] {listing.external_id}: skipped ({exc})")
            skipped += 1
            continue
        touched = False
        for field in fields:
            if not field.is_missing(listing):
                continue
            value = field.get(detail)
            if value:
                field.set(repository, listing, value)
                per_field_updates[field.name] += 1
                touched = True
        if touched:
            updated += 1
        if i % 50 == 0:
            await session.commit()
    await session.commit()
    print(f"done: {updated}/{len(listings)} listing(s) updated, {skipped} skipped")
    for name, count in per_field_updates.items():
        print(f"  {name}: {count} set")


async def _main(args: argparse.Namespace) -> None:
    names = args.fields.split(",") if args.fields else list(DETAIL_ONLY_FIELDS)
    unknown = set(names) - DETAIL_ONLY_FIELDS.keys()
    if unknown:
        raise SystemExit(f"unknown field(s): {sorted(unknown)} — choose from {sorted(DETAIL_ONLY_FIELDS)}")
    fields = [DETAIL_ONLY_FIELDS[name] for name in names]
    async for session in get_session():
        await _backfill(session, source_code=args.source, fields=fields, limit=args.limit)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="polovniautomobili")
    parser.add_argument("--fields", default=None, help="comma-separated subset (default: all registered fields)")
    parser.add_argument("--limit", type=int, default=None)
    asyncio.run(_main(parser.parse_args()))
