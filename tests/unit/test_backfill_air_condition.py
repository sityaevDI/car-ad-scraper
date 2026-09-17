import pytest
from sqlalchemy import select

import app.sources.registry as registry
from app.models.listing import Listing
from app.scraping.backfill_air_condition import _backfill
from app.scraping.fetch_outcome import FetchBlockedError, FetchOutcome
from app.sources.base import SourceListing, SourceListingRef
from tests.conftest import make_listing, seed_source

pytestmark = pytest.mark.asyncio


class _StubAdapter:
    def __init__(self, **kwargs):
        pass

    async def fetch_listing(self, ref: SourceListingRef) -> SourceListing:
        if ref.external_id == "blocked":
            raise FetchBlockedError(FetchOutcome.FORBIDDEN)
        return SourceListing(
            external_id=ref.external_id,
            canonical_url=ref.url,
            title="Refetched",
            make="Skoda",
            model="Octavia",
            production_year=2019,
            mileage_km=100_000,
            price=10_000,
            currency="EUR",
            air_condition="automatic" if ref.external_id != "no-value" else None,
            equipment=["bluetooth"],
        )


async def test_backfill_sets_air_condition_only_where_missing(session, monkeypatch):
    monkeypatch.setitem(registry.SOURCE_REGISTRY, "polovniautomobili", _StubAdapter)
    source = await seed_source(session)

    missing = make_listing(source.id, external_id="1", air_condition=None)
    already_set = make_listing(source.id, external_id="2", air_condition="manual")
    session.add(missing)
    session.add(already_set)
    await session.commit()

    await _backfill(session, source_code="polovniautomobili", limit=None)

    refreshed = {
        listing.external_id: listing for listing in (await session.execute(select(Listing))).scalars().all()
    }
    assert refreshed["1"].air_condition == "automatic"
    assert refreshed["1"].equipment == ["bluetooth"]
    # Already had a value — untouched, and the stub is never even asked about it.
    assert refreshed["2"].air_condition == "manual"


async def test_backfill_skips_blocked_listings_without_aborting(session, monkeypatch):
    monkeypatch.setitem(registry.SOURCE_REGISTRY, "polovniautomobili", _StubAdapter)
    source = await seed_source(session)

    session.add(make_listing(source.id, external_id="blocked", air_condition=None))
    session.add(make_listing(source.id, external_id="no-value", air_condition=None))
    await session.commit()

    await _backfill(session, source_code="polovniautomobili", limit=None)

    refreshed = {
        listing.external_id: listing for listing in (await session.execute(select(Listing))).scalars().all()
    }
    assert refreshed["blocked"].air_condition is None
    assert refreshed["no-value"].air_condition is None
