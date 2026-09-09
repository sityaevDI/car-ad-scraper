from collections.abc import AsyncIterator

from sqlalchemy import select

import app.sources.registry as registry
from app.models.listing import Listing
from app.scraping.fetch_outcome import FetchBlockedError, FetchOutcome
from app.scraping.pipeline import run_scrape
from app.search.query import SearchQuery
from app.sources.base import SourceListing


def _listing(external_id: str, price: int) -> SourceListing:
    return SourceListing(
        external_id=external_id,
        canonical_url=f"https://example.com/{external_id}",
        title="Test listing",
        make="Skoda",
        model="Octavia",
        production_year=2019,
        mileage_km=100_000,
        price=price,
        currency="EUR",
    )


class StubBlockedAdapter:
    source_code = "stub_source"
    display_name = "Stub Source"
    domain = "stub.example.com"
    country = "RS"

    def __init__(self, max_pages=5, proxy_provider=None, outcome_sink=None):
        self.outcome_sink = outcome_sink

    async def search_with_data(self, query: SearchQuery) -> AsyncIterator[SourceListing]:
        if self.outcome_sink:
            self.outcome_sink(FetchOutcome.SUCCESS)
        yield _listing("1", 10_000)
        yield _listing("2", 12_000)
        if self.outcome_sink:
            self.outcome_sink(FetchOutcome.FORBIDDEN)
        raise FetchBlockedError(FetchOutcome.FORBIDDEN)


async def test_run_scrape_persists_partial_results_when_blocked_mid_crawl(session, monkeypatch):
    monkeypatch.setitem(registry.SOURCE_REGISTRY, "stub_source", StubBlockedAdapter)

    stats = await run_scrape(session, source_code="stub_source", query=SearchQuery(), max_pages=1)

    assert stats.listings_seen == 2
    assert stats.listings_created == 2
    assert stats.listings_updated == 0
    assert stats.blocked is True
    assert stats.outcome_counts == {"success": 1, "forbidden": 1}

    persisted = (await session.execute(select(Listing))).scalars().all()
    assert len(persisted) == 2
