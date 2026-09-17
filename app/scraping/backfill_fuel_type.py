"""One-off backfill for `fuel_type` on listings scraped before the three narrower hybrid facets
(hybrid_petrol / hybrid_diesel / plugin_hybrid) were added to
app/sources/polovniautomobili/mapper.py's `_FUEL_TYPE_NORMALIZED`.

Before that fix, `normalize_fuel_type()` fell back to the raw, untranslated Serbian text for
those three facets ("Hibridni pogon (benzin)" / "(dizel)" / "Plug-in hibrid"), so listings scraped
before the fix — most real hybrids, e.g. a Toyota Prius/Corolla/Yaris hybrid, which the site tags
"Hibridni pogon (benzin)" rather than the generic "Hibridni pogon" — got stored with that literal
Serbian string instead of a canonical fuel_type, and never matched a `fuel_types=["hybrid"]` (or
"hybrid_petrol") search filter.

Unlike backfill_interior_material.py / backfill_air_condition.py, no re-fetch from the source is
needed here: the raw value is already in Postgres, it just needs re-normalizing through the now-
fixed mapping.

Usage:
    python -m app.scraping.backfill_fuel_type [--source polovniautomobili]
"""

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.listing import Listing
from app.models.source import Source
from app.sources.polovniautomobili.mapper import normalize_fuel_type

# The exact raw Serbian strings normalize_fuel_type() didn't recognize before this fix — any
# listing stored with one of these literal values needs re-normalizing.
_STALE_RAW_VALUES = ["Hibridni pogon (benzin)", "Hibridni pogon (dizel)", "Plug-in hibrid"]


async def _backfill(session: AsyncSession, source_code: str) -> None:
    source = (await session.execute(select(Source).where(Source.code == source_code))).scalar_one()
    stmt = select(Listing).where(Listing.source_id == source.id, Listing.fuel_type.in_(_STALE_RAW_VALUES))
    listings = (await session.execute(stmt)).scalars().all()
    print(f"{len(listings)} listing(s) with a stale, un-normalized fuel_type")

    for listing in listings:
        listing.fuel_type = normalize_fuel_type(listing.fuel_type)
    await session.commit()
    print(f"done: {len(listings)} updated")


async def _main(args: argparse.Namespace) -> None:
    async for session in get_session():
        await _backfill(session, source_code=args.source)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="polovniautomobili")
    asyncio.run(_main(parser.parse_args()))
