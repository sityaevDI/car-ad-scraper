import uuid
from datetime import datetime, timezone

import pytest_asyncio
from fakeredis import FakeAsyncRedis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.listing import Listing, ListingStatus
from app.models.source import Source


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s

    await engine.dispose()


@pytest_asyncio.fixture
async def redis():
    client = FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()


def make_listing(source_id: uuid.UUID, **overrides) -> Listing:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid.uuid4(),
        source_id=source_id,
        external_id=str(uuid.uuid4()),
        canonical_url="https://example.com/ad",
        title="Test listing",
        make="Škoda",
        model="Octavia",
        production_year=2019,
        mileage_km=150_000,
        price=13_000,
        currency="EUR",
        fuel_type="diesel",
        transmission="automatic",
        body_type="wagon",
        engine_volume_cc=1968,
        power_hp=150,
        status=ListingStatus.ACTIVE,
        first_seen_at=now,
        last_seen_at=now,
        last_checked_at=now,
    )
    defaults.update(overrides)
    return Listing(**defaults)


async def seed_source(session) -> Source:
    source = Source(code="polovniautomobili", name="Polovni Automobili", domain="polovniautomobili.com", country="RS")
    session.add(source)
    await session.flush()
    return source
