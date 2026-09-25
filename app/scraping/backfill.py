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
import uuid

from sqlalchemy import func, or_, select
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

_BATCH_SIZE = 50


async def _backfill(
    session: AsyncSession, source_code: str, fields: list[DetailOnlyField], limit: int | None
) -> None:
    source = (await session.execute(select(Source).where(Source.code == source_code))).scalar_one()
    source_id = source.id  # see pipeline.py's run_scrape for why this is captured up front
    rate_limit = await get_scrape_rate_limit(session)
    adapter = get_source_adapter(
        source_code,
        delay=rate_limit.request_delay_seconds,
        jitter=rate_limit.request_jitter_seconds,
        network_error_retry_delay=rate_limit.network_error_retry_delay_seconds,
    )
    repository = ListingRepository(session)

    where_clauses = (
        Listing.source_id == source_id,
        Listing.status == ListingStatus.ACTIVE,
        or_(*(field.missing for field in fields)),
    )
    total = (
        await session.execute(select(func.count()).select_from(Listing).where(*where_clauses))
    ).scalar_one()
    if limit is not None:
        total = min(total, limit)
    field_names = ", ".join(field.name for field in fields)
    print(f"{total} listing(s) missing at least one of: {field_names}")

    # Paginated by id (not `.scalars().all()`-ed into one list, nor a single stream_scalars()
    # cursor) — a source with tens of thousands of listings missing a field would otherwise hold
    # every one of them as a live ORM object for the whole run (see
    # app/listings/repository.py's mark_missing_as_removed for the same underlying fix, and the
    # 2026-09-18 backend memory investigation this all comes from). A live streaming cursor was
    # the first thing tried here instead of this loop, but it doesn't survive a commit mid-stream:
    # against real Postgres/asyncpg a server-side cursor is scoped to the transaction that opened
    # it, so committing (needed every batch, since each fetch_listing() mutates listings that must
    # actually persist) would invalidate it. Keyset pagination by id sidesteps that — each batch is
    # its own complete, independent query, so a commit between batches never crosses an open
    # cursor. Ordering/paginating on `id` (not touched by anything this backfills) keeps batches
    # stable even as earlier rows' missing-field columns change under us mid-run.
    updated = skipped = 0
    per_field_updates = {field.name: 0 for field in fields}
    processed = 0
    last_id: uuid.UUID | None = None
    while limit is None or processed < limit:
        stmt = select(Listing).where(*where_clauses)
        if last_id is not None:
            stmt = stmt.where(Listing.id > last_id)
        stmt = stmt.order_by(Listing.id).limit(_BATCH_SIZE)
        batch = (await session.execute(stmt)).scalars().all()
        if not batch:
            break
        for listing in batch:
            if limit is not None and processed >= limit:
                break
            processed += 1
            last_id = listing.id
            ref = SourceListingRef(external_id=listing.external_id, url=listing.canonical_url)
            try:
                detail = await adapter.fetch_listing(ref)
            except (FetchBlockedError, ParserError, RuntimeError) as exc:
                # Same best-effort posture as _enrich_with_detail: one slow/blocked listing
                # shouldn't abort the whole backfill.
                print(f"  [{processed}/{total}] {listing.external_id}: skipped ({exc})")
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
        await session.commit()
        session.expunge_all()
    print(f"done: {updated}/{total} listing(s) updated, {skipped} skipped")
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
