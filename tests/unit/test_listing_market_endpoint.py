"""Endpoint-level tests for GET /listings/{id}/market-comparison, following
tests/unit/test_saved_search_endpoints.py's pattern: real FastAPI app over ASGI, dependency
overrides instead of a real Postgres.
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.market.config import get_market_config
from app.market.segment import segment_criteria_for_listing
from app.market.service import MarketPriceService
from tests.conftest import make_listing, seed_source


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()


async def test_market_comparison_returns_nulls_when_no_snapshot_yet(session_factory, client):
    async with session_factory() as session:
        source = await seed_source(session)
        listing = make_listing(source.id, price=10_000)
        session.add(listing)
        await session.commit()
        listing_id = listing.id

    response = await client.get(f"/api/v1/listings/{listing_id}/market-comparison")

    assert response.status_code == 200
    body = response.json()
    assert body["market"] is None
    assert body["price_score"] is None


async def test_market_comparison_after_recompute(session_factory, client):
    async with session_factory() as session:
        source = await seed_source(session)
        listings = [make_listing(source.id, price=10_000 + i * 100, external_id=str(i)) for i in range(6)]
        for listing in listings:
            session.add(listing)
        await session.commit()
        target_id = listings[0].id

        service = MarketPriceService(session)
        config = await get_market_config(session)
        criteria = segment_criteria_for_listing(listings[0], mileage_bucket_km=config.mileage_bucket_km)
        await service.recompute_segment(criteria, config)
        await session.commit()

    response = await client.get(f"/api/v1/listings/{target_id}/market-comparison")

    assert response.status_code == 200
    body = response.json()
    assert body["market"] is not None
    assert body["market"]["comparable_listings_count"] == 6
    assert body["market"]["confidence"] != "insufficient"
    assert body["price_score"] is not None
    assert "label" in body["price_score"]


async def test_market_comparison_unknown_listing_returns_404(client):
    response = await client.get("/api/v1/listings/00000000-0000-0000-0000-000000000000/market-comparison")

    assert response.status_code == 404
