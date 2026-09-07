"""Persists a source's search results into Postgres. No job queue yet (that's
agent_documents/09_QUEUE_PRIORITY.md, a later phase) — this is a directly-awaited pipeline run,
triggered manually via `app.scraping.cli` for now.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.listings.repository import ListingRepository
from app.models.source import Source
from app.search.query import SearchQuery
from app.sources.polovniautomobili.adapter import PolovniAutomobiliSource


@dataclass
class ScrapeStats:
    listings_seen: int = 0
    listings_created: int = 0
    listings_updated: int = 0


async def get_or_create_source(session: AsyncSession, code: str, name: str, domain: str, country: str) -> Source:
    result = await session.execute(select(Source).where(Source.code == code))
    source = result.scalar_one_or_none()
    if source is None:
        source = Source(code=code, name=name, domain=domain, country=country)
        session.add(source)
        await session.flush()
    return source


async def run_polovniautomobili_scrape(
    session: AsyncSession, query: SearchQuery, max_pages: int = 5
) -> ScrapeStats:
    source = await get_or_create_source(
        session,
        code="polovniautomobili",
        name="Polovni Automobili",
        domain="polovniautomobili.com",
        country="RS",
    )
    adapter = PolovniAutomobiliSource(max_pages=max_pages)
    repository = ListingRepository(session)

    stats = ScrapeStats()
    async for source_listing in adapter.search_with_data(query):
        stats.listings_seen += 1
        _, is_new = await repository.upsert_listing(source.id, source_listing)
        if is_new:
            stats.listings_created += 1
        else:
            stats.listings_updated += 1

    await session.commit()
    return stats
