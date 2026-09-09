"""Persists a source's search results into Postgres. Runs either directly (app/scraping/cli.py,
for local dev) or from an arq job (app/scraping/worker.py).
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.listings.repository import ListingRepository
from app.models.source import Source
from app.scraping.fetch_outcome import FetchBlockedError, OutcomeCounter
from app.scraping.proxy import ProxyProvider
from app.search.query import SearchQuery
from app.sources.base import CarSource, SourceListing
from app.sources.registry import get_source_adapter


@dataclass
class ScrapeStats:
    listings_seen: int = 0
    listings_created: int = 0
    listings_updated: int = 0
    outcome_counts: dict[str, int] = field(default_factory=dict)
    blocked: bool = False
    # Per-listing detail the aggregate counts above don't carry — consumed by
    # app/notifications/matching.py (issues #21/#26) to generate NEW_MATCH/PRICE_DROP events
    # without re-querying "what changed this run".
    new_listing_ids: list[uuid.UUID] = field(default_factory=list)
    price_drops: list[tuple[uuid.UUID, int, int]] = field(default_factory=list)  # (listing_id, previous, current)


async def get_or_create_source(session: AsyncSession, code: str, name: str, domain: str, country: str) -> Source:
    result = await session.execute(select(Source).where(Source.code == code))
    source = result.scalar_one_or_none()
    if source is None:
        source = Source(code=code, name=name, domain=domain, country=country)
        session.add(source)
        await session.flush()
    return source


async def _search_listings(adapter: CarSource, query: SearchQuery) -> AsyncIterator[SourceListing]:
    """Prefer an adapter's optional search_with_data() — a source whose search results already
    carry full listing data (like Polovni Automobili) skips a per-listing detail fetch this way.
    Not part of the CarSource Protocol itself, since not every source can offer it; adapters
    without it fall back to search() + fetch_listing() per ref.
    """
    search_with_data = getattr(adapter, "search_with_data", None)
    if search_with_data is not None:
        async for listing in search_with_data(query):
            yield listing
        return
    async for ref in adapter.search(query):
        yield await adapter.fetch_listing(ref)


async def run_scrape(
    session: AsyncSession,
    source_code: str,
    query: SearchQuery,
    max_pages: int = 5,
    proxy_provider: ProxyProvider | None = None,
) -> ScrapeStats:
    counter = OutcomeCounter()
    adapter = get_source_adapter(
        source_code, max_pages=max_pages, proxy_provider=proxy_provider, outcome_sink=counter.record
    )
    source = await get_or_create_source(
        session, code=adapter.source_code, name=adapter.display_name, domain=adapter.domain, country=adapter.country
    )
    repository = ListingRepository(session)

    stats = ScrapeStats()
    try:
        async for source_listing in _search_listings(adapter, query):
            stats.listings_seen += 1
            listing, is_new, previous_price = await repository.upsert_listing(source.id, source_listing)
            if is_new:
                stats.listings_created += 1
                stats.new_listing_ids.append(listing.id)
            else:
                stats.listings_updated += 1
                if previous_price is not None and previous_price > listing.price:
                    stats.price_drops.append((listing.id, previous_price, listing.price))
    except FetchBlockedError:
        # Stop pagination early but keep whatever was already upserted this run — a partial
        # result is more useful than losing it, and burning further proxy/direct requests against
        # a source that just told us to back off would be wasteful.
        stats.blocked = True

    stats.outcome_counts = counter.as_dict()
    await session.commit()
    return stats
