"""Manual trigger for the removal stats rollup (docs/adr/21_REMOVAL_STATS.md).

It normally runs from the worker's cron (03:10/15:10 UTC and at worker start). Run it by hand right
after the table is first created, or when a scheduled run was missed, instead of waiting for the
next slot.

Usage:
    python -m app.market.removal_cli refresh
"""

import argparse
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.market.removal_stats import refresh_removal_stats


async def _refresh(session: AsyncSession) -> None:
    rows = await refresh_removal_stats(session)
    print(f"Wrote {rows} removal_stats rows.")


async def _main() -> None:
    async for session in get_session():
        await _refresh(session)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("refresh", help="Recompute the removal stats rollup now")
    parser.parse_args()
    asyncio.run(_main())


if __name__ == "__main__":
    main()
