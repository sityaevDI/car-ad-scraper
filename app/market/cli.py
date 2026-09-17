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

from sqlalchemy import select

from app.db.session import get_session
from app.market.config import get_market_config
from app.market.repository import MarketRepository
from app.market.segment import segment_criteria_for_listing
from app.market.service import MarketPriceService
from app.models.listing import Listing, ListingStatus

_RECOMPUTE_BATCH_SIZE = 500


async def _backfill() -> None:
    async for session in get_session():
        config = await get_market_config(session)
        repository = MarketRepository(session)

        result = await session.execute(select(Listing).where(Listing.status == ListingStatus.ACTIVE))
        listings = list(result.scalars().all())
        for listing in listings:
            await repository.mark_dirty(
                segment_criteria_for_listing(listing, mileage_bucket_km=config.mileage_bucket_km)
            )
        await session.commit()
        print(f"Marked {len(listings)} active listings' segments dirty.")

        service = MarketPriceService(session)
        total = 0
        while True:
            processed = await service.recompute_due(_RECOMPUTE_BATCH_SIZE)
            await session.commit()
            total += processed
            if processed < _RECOMPUTE_BATCH_SIZE:
                break
        print(f"Computed {total} market snapshots.")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("backfill", help="Mark every active listing's segment dirty and recompute immediately")
    parser.parse_args()
    asyncio.run(_backfill())


if __name__ == "__main__":
    main()
