"""One-off backfill for `air_condition` on listings scraped before that field existed.

New listings get it for free from the detail-page fetch every brand-new listing already gets
(see pipeline.py's `_enrich_with_detail`). This script re-fetches the detail page for listings
created before that column existed, since `ListingSnapshot.raw_payload` only ever stored the
*search-result* raw JSON for those — which doesn't carry `airCondition` at all — so there's no
way to backfill them from data already in Postgres. Mirrors backfill_interior_material.py.

Usage:
    python -m app.scraping.backfill_air_condition [--source polovniautomobili] [--limit N]
"""

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.listings.repository import ListingRepository
from app.models.listing import Listing, ListingStatus
from app.models.source import Source
from app.scraping.fetch_outcome import FetchBlockedError, ParserError
from app.scraping.rate_limit import get_scrape_rate_limit
from app.sources.base import SourceListingRef
from app.sources.registry import get_source_adapter


async def _backfill(session: AsyncSession, source_code: str, limit: int | None) -> None:
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
        Listing.air_condition.is_(None),
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    listings = (await session.execute(stmt)).scalars().all()
    print(f"{len(listings)} listing(s) missing air_condition")

    updated = skipped = 0
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
        if detail.air_condition:
            repository.set_air_condition(listing, detail.air_condition)
            updated += 1
        if detail.equipment and not listing.equipment:
            repository.set_equipment(listing, detail.equipment)
        if detail.interior_material and not listing.interior_material:
            repository.set_interior_material(listing, detail.interior_material)
        if i % 50 == 0:
            await session.commit()
    await session.commit()
    print(f"done: {updated} updated, {skipped} skipped, {len(listings) - updated - skipped} had no value on the source")


async def _main(args: argparse.Namespace) -> None:
    async for session in get_session():
        await _backfill(session, source_code=args.source, limit=args.limit)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="polovniautomobili")
    parser.add_argument("--limit", type=int, default=None)
    asyncio.run(_main(parser.parse_args()))
