"""One-off/manual market recompute trigger.

Dirty-marking normally only happens as a side effect of scraping (see
app/scraping/pipeline.py::run_scrape) — a new listing or a price change on an already-scraped
listing. Listings already in the DB before this feature shipped never went through that path, so
their segments start out with no snapshot ("оценивается") until backfilled once here. Also useful
after retuning app/market/config.py-backed thresholds (market_configs) when you don't want to wait
for the next scrape to see fresh numbers.

Usage:
    python -m app.market.cli backfill
"""

import argparse
import asyncio
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.market.config import get_market_config
from app.market.repository import MarketRepository
from app.market.segment import segment_criteria_for_listing
from app.market.service import MarketPriceService
from app.models.listing import Listing, ListingStatus

_RECOMPUTE_BATCH_SIZE = 500


async def _backfill(session: AsyncSession) -> None:
    config = await get_market_config(session)
    mileage_bucket_km = config.mileage_bucket_km  # see pipeline.py's run_scrape for why
    repository = MarketRepository(session)

    total_active = (
        await session.execute(select(func.count()).select_from(Listing).where(Listing.status == ListingStatus.ACTIVE))
    ).scalar_one()
    # Paginated by id, not `.scalars().all()`-ed into one list — across every source this is
    # effectively the whole table, which would otherwise sit as live ORM objects in the session's
    # identity map for the whole run (unlike app/scraping/scheduler.py's cron equivalent, which
    # opens a fresh session per tick and so never accumulates — see the 2026-09-18 backend memory
    # investigation this all comes from). A live stream_scalars() cursor doesn't work here either,
    # for a sharper reason than just the periodic commit: repository.mark_dirty() issues its own
    # `session.get(MarketDirtySegment, ...)` query on every single row, and a second query on the
    # same session/connection while a streaming cursor from the first is still open isn't safe
    # against a real server-side-cursor driver (asyncpg). Keyset pagination by id avoids both
    # problems — each batch is one complete, independent query.
    marked = 0
    last_id: uuid.UUID | None = None
    while True:
        stmt = select(Listing).where(Listing.status == ListingStatus.ACTIVE)
        if last_id is not None:
            stmt = stmt.where(Listing.id > last_id)
        stmt = stmt.order_by(Listing.id).limit(_RECOMPUTE_BATCH_SIZE)
        batch = (await session.execute(stmt)).scalars().all()
        if not batch:
            break
        for listing in batch:
            await repository.mark_dirty(segment_criteria_for_listing(listing, mileage_bucket_km=mileage_bucket_km))
            marked += 1
            last_id = listing.id
        await session.commit()
        session.expunge_all()
    print(f"Marked {marked}/{total_active} active listings' segments dirty.")

    service = MarketPriceService(session)
    total = 0
    while True:
        processed = await service.recompute_due(_RECOMPUTE_BATCH_SIZE)
        await session.commit()
        # Same reasoning as above: this loop can run for many thousands of segments across a
        # large backlog, all inside the one session passed into this function — nothing here
        # closes/reopens per batch the way the cron's recompute_dirty_market_segments does, so
        # recompute_segment's per-segment comparable-listing samples would otherwise pile up in
        # the identity map for the whole run.
        session.expunge_all()
        total += processed
        if processed < _RECOMPUTE_BATCH_SIZE:
            break
    print(f"Computed {total} market snapshots.")


async def _main() -> None:
    async for session in get_session():
        await _backfill(session)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("backfill", help="Mark every active listing's segment dirty and recompute immediately")
    parser.parse_args()
    asyncio.run(_main())


if __name__ == "__main__":
    main()
