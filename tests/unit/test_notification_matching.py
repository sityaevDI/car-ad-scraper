import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.follow import Follow
from app.models.listing import Listing, ListingStatus
from app.models.notification import Notification, NotificationType
from app.models.saved_search import SavedSearch
from app.models.scrape_job import ScrapeJob, ScrapeJobStatus, ScrapeJobType
from app.models.source import Source
from app.notifications.matching import generate_notifications_for_job
from app.scraping.pipeline import ScrapeStats
from app.scraping.schemas import encode_job_query
from app.search.query import SearchQuery


@pytest.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _seed_source_and_listing(
    session, source_id: uuid.UUID | None = None, **overrides
) -> tuple[uuid.UUID, uuid.UUID]:
    if source_id is None:
        source = Source(code="polovniautomobili", name="Polovni Automobili", domain="x.rs", country="RS")
        session.add(source)
        await session.flush()
        source_id = source.id

    now = datetime.now(timezone.utc)
    defaults = dict(
        source_id=source_id,
        external_id="1",
        canonical_url="https://x.rs/1",
        title="Skoda Octavia",
        make="Skoda",
        model="Octavia",
        production_year=2019,
        mileage_km=100_000,
        price=10_000,
        currency="EUR",
        status=ListingStatus.ACTIVE,
        first_seen_at=now,
        last_seen_at=now,
        last_checked_at=now,
    )
    defaults.update(overrides)
    listing = Listing(**defaults)
    session.add(listing)
    await session.flush()
    return source_id, listing.id


async def test_price_drop_notifies_followers(session_factory):
    async with session_factory() as session:
        _, listing_id = await _seed_source_and_listing(session)
        follower_id = uuid.uuid4()
        session.add(Follow(user_id=follower_id, listing_id=listing_id))
        job = ScrapeJob(source_id=uuid.uuid4(), job_type=ScrapeJobType.SEARCH, status=ScrapeJobStatus.RUNNING)
        session.add(job)
        await session.commit()

        stats = ScrapeStats(price_drops=[(listing_id, 12_000, 10_000)])
        await generate_notifications_for_job(session, job, stats)
        await session.commit()

        notifications = (await session.execute(select(Notification))).scalars().all()
        assert len(notifications) == 1
        assert notifications[0].user_id == follower_id
        assert notifications[0].type == NotificationType.PRICE_DROP
        assert notifications[0].payload["previous_price"] == 12_000
        assert notifications[0].payload["current_price"] == 10_000


async def test_price_drop_without_followers_creates_nothing(session_factory):
    async with session_factory() as session:
        _, listing_id = await _seed_source_and_listing(session)
        job = ScrapeJob(source_id=uuid.uuid4(), job_type=ScrapeJobType.SEARCH, status=ScrapeJobStatus.RUNNING)
        session.add(job)
        await session.commit()

        stats = ScrapeStats(price_drops=[(listing_id, 12_000, 10_000)])
        await generate_notifications_for_job(session, job, stats)
        await session.commit()

        notifications = (await session.execute(select(Notification))).scalars().all()
        assert notifications == []


async def test_new_match_notifies_owner_of_matching_saved_search(session_factory):
    async with session_factory() as session:
        source_id, listing_id = await _seed_source_and_listing(session)
        user_id = uuid.uuid4()
        query = SearchQuery(make="Skoda")
        session.add(SavedSearch(user_id=user_id, name="Skoda alert", query=query.model_dump(), enabled=True))
        job = ScrapeJob(
            source_id=source_id,
            job_type=ScrapeJobType.SAVED_SEARCH_REFRESH,
            status=ScrapeJobStatus.RUNNING,
            query=encode_job_query(query, max_pages=5),
        )
        session.add(job)
        await session.commit()

        stats = ScrapeStats(new_listing_ids=[listing_id])
        await generate_notifications_for_job(session, job, stats)
        await session.commit()

        notifications = (await session.execute(select(Notification))).scalars().all()
        assert len(notifications) == 1
        assert notifications[0].user_id == user_id
        assert notifications[0].type == NotificationType.NEW_MATCH
        assert notifications[0].listing_id is None
        assert notifications[0].payload["saved_search_name"] == "Skoda alert"
        assert notifications[0].payload["new_listings_count"] == 1
        assert notifications[0].payload["query_description"] == "Skoda"


async def test_new_match_creates_one_aggregated_notification_for_multiple_new_listings(session_factory):
    async with session_factory() as session:
        source_id, listing_id_1 = await _seed_source_and_listing(session, external_id="1")
        _, listing_id_2 = await _seed_source_and_listing(session, source_id=source_id, external_id="2")
        user_id = uuid.uuid4()
        query = SearchQuery(make="Skoda")
        session.add(SavedSearch(user_id=user_id, name="Skoda alert", query=query.model_dump(), enabled=True))
        job = ScrapeJob(
            source_id=source_id,
            job_type=ScrapeJobType.SAVED_SEARCH_REFRESH,
            status=ScrapeJobStatus.RUNNING,
            query=encode_job_query(query, max_pages=5),
        )
        session.add(job)
        await session.commit()

        stats = ScrapeStats(new_listing_ids=[listing_id_1, listing_id_2])
        await generate_notifications_for_job(session, job, stats)
        await session.commit()

        notifications = (await session.execute(select(Notification))).scalars().all()
        assert len(notifications) == 1
        assert notifications[0].payload["new_listings_count"] == 2


async def test_new_match_ignores_non_matching_saved_search(session_factory):
    async with session_factory() as session:
        source_id, listing_id = await _seed_source_and_listing(session)
        session.add(
            SavedSearch(
                user_id=uuid.uuid4(),
                name="Audi alert",
                query=SearchQuery(make="Audi").model_dump(),
                enabled=True,
            )
        )
        job_query = SearchQuery(make="Skoda")
        job = ScrapeJob(
            source_id=source_id,
            job_type=ScrapeJobType.SAVED_SEARCH_REFRESH,
            status=ScrapeJobStatus.RUNNING,
            query=encode_job_query(job_query, max_pages=5),
        )
        session.add(job)
        await session.commit()

        stats = ScrapeStats(new_listing_ids=[listing_id])
        await generate_notifications_for_job(session, job, stats)
        await session.commit()

        notifications = (await session.execute(select(Notification))).scalars().all()
        assert notifications == []


async def test_new_match_ignores_disabled_saved_search(session_factory):
    async with session_factory() as session:
        source_id, listing_id = await _seed_source_and_listing(session)
        query = SearchQuery(make="Skoda")
        session.add(SavedSearch(user_id=uuid.uuid4(), name="Skoda alert", query=query.model_dump(), enabled=False))
        job = ScrapeJob(
            source_id=source_id,
            job_type=ScrapeJobType.SAVED_SEARCH_REFRESH,
            status=ScrapeJobStatus.RUNNING,
            query=encode_job_query(query, max_pages=5),
        )
        session.add(job)
        await session.commit()

        stats = ScrapeStats(new_listing_ids=[listing_id])
        await generate_notifications_for_job(session, job, stats)
        await session.commit()

        notifications = (await session.execute(select(Notification))).scalars().all()
        assert notifications == []


async def test_generate_notifications_enqueues_email(session_factory):
    async with session_factory() as session:
        _, listing_id = await _seed_source_and_listing(session)
        follower_id = uuid.uuid4()
        session.add(Follow(user_id=follower_id, listing_id=listing_id))
        job = ScrapeJob(source_id=uuid.uuid4(), job_type=ScrapeJobType.SEARCH, status=ScrapeJobStatus.RUNNING)
        session.add(job)
        await session.commit()

        enqueued = []

        async def enqueue_email(notification_id: str) -> None:
            enqueued.append(notification_id)

        stats = ScrapeStats(price_drops=[(listing_id, 12_000, 10_000)])
        await generate_notifications_for_job(session, job, stats, enqueue_email=enqueue_email)
        await session.commit()

        assert len(enqueued) == 1
