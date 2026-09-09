"""Manual scrape trigger for dev/testing, ahead of a real job queue.

Usage:
    python -m app.scraping.cli --make Skoda --model Octavia --max-pages 2
"""

import argparse
import asyncio

from app.db.session import get_session
from app.scraping.pipeline import run_scrape
from app.search.query import SearchQuery


async def _main(args: argparse.Namespace) -> None:
    query = SearchQuery(
        make=args.make,
        models=[args.model] if args.model else None,
        year_min=args.year_min,
        year_max=args.year_max,
        price_max=args.price_max,
    )
    async for session in get_session():
        stats = await run_scrape(session, source_code="polovniautomobili", query=query, max_pages=args.max_pages)
        print(stats)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--make")
    parser.add_argument("--model")
    parser.add_argument("--year-min", type=int)
    parser.add_argument("--year-max", type=int)
    parser.add_argument("--price-max", type=int)
    parser.add_argument("--max-pages", type=int, default=2)
    asyncio.run(_main(parser.parse_args()))
