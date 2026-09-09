import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.saved_search import SavedSearch
from app.models.scheduled_scrape import ScheduledScrape
from app.models.scrape_job import ScrapeJob, ScrapeJobStatus, ScrapeJobType
from app.models.source import Source
from app.scraping.scheduler import run_due_saved_search_scrapes, run_due_scheduled_scrapes


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


class RecordingRedis:
    def __init__(self):
        self.enqueued: list[tuple[str, tuple]] = []

    async def enqueue_job(self, function: str, *args) -> None:
        self.enqueued.append((function, args))


async def _seed_source(factory) -> object:
    async with factory() as session:
        source = Source(
            code="polovniautomobili", name="Polovni Automobili", domain="polovniautomobili.com", country="RS"
        )
        session.add(source)
        await session.commit()
        return source.id


async def _seed_schedule(factory, source_id, next_run_at, enabled=True, interval_minutes=60) -> object:
    async with factory() as session:
        schedule = ScheduledScrape(
            source_id=source_id,
            query={"search_query": {"make": "Skoda"}, "max_pages": 3},
            interval_minutes=interval_minutes,
            enabled=enabled,
            next_run_at=next_run_at,
        )
        session.add(schedule)
        await session.commit()
        return schedule.id


async def test_creates_and_enqueues_job_for_due_schedule(session_factory):
    source_id = await _seed_source(session_factory)
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    schedule_id = await _seed_schedule(session_factory, source_id, next_run_at=past)
    redis = RecordingRedis()

    await run_due_scheduled_scrapes({"session_factory": session_factory, "redis": redis})

    async with session_factory() as session:
        jobs = (await session.execute(ScrapeJob.__table__.select())).fetchall()
        assert len(jobs) == 1
        assert jobs[0].status == ScrapeJobStatus.PENDING
        assert jobs[0].query == {"search_query": {"make": "Skoda"}, "max_pages": 3}

        schedule = await session.get(ScheduledScrape, schedule_id)
        assert schedule.last_run_at is not None
        assert schedule.last_job_id == jobs[0].id
        # sqlite round-trips DateTime(timezone=True) as naive, so compare the two DB-read values
        # to each other rather than against the tz-aware `past` computed in this test.
        assert schedule.next_run_at - schedule.last_run_at >= timedelta(minutes=59)

    assert len(redis.enqueued) == 1
    assert redis.enqueued[0][0] == "run_scrape_job"


async def test_skips_schedule_not_yet_due(session_factory):
    source_id = await _seed_source(session_factory)
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    await _seed_schedule(session_factory, source_id, next_run_at=future)
    redis = RecordingRedis()

    await run_due_scheduled_scrapes({"session_factory": session_factory, "redis": redis})

    assert redis.enqueued == []
    async with session_factory() as session:
        jobs = (await session.execute(ScrapeJob.__table__.select())).fetchall()
        assert jobs == []


async def _seed_saved_search(factory, user_id=None, last_run_at=None, enabled=True, query=None) -> uuid.UUID:
    async with factory() as session:
        saved_search = SavedSearch(
            user_id=user_id or uuid.uuid4(),
            name="Skoda search",
            query=query or {"make": "Skoda"},
            enabled=enabled,
            last_run_at=last_run_at,
        )
        session.add(saved_search)
        await session.commit()
        return saved_search.id


async def test_saved_search_scheduler_creates_job_for_never_run_search(session_factory):
    source_id = await _seed_source(session_factory)
    saved_search_id = await _seed_saved_search(session_factory, last_run_at=None)
    redis = RecordingRedis()

    await run_due_saved_search_scrapes({"session_factory": session_factory, "redis": redis})

    async with session_factory() as session:
        jobs = (await session.execute(ScrapeJob.__table__.select())).fetchall()
        assert len(jobs) == 1
        assert jobs[0].source_id == source_id
        assert jobs[0].job_type == ScrapeJobType.SAVED_SEARCH_REFRESH
        assert jobs[0].query["search_query"]["make"] == "Skoda"
        assert jobs[0].query["max_pages"] == 5

        saved_search = await session.get(SavedSearch, saved_search_id)
        assert saved_search.last_run_at is not None

    assert len(redis.enqueued) == 1
    assert redis.enqueued[0][0] == "run_scrape_job"


async def test_saved_search_scheduler_skips_recently_run_search(session_factory):
    await _seed_source(session_factory)
    recent = datetime.now(timezone.utc) - timedelta(minutes=5)
    await _seed_saved_search(session_factory, last_run_at=recent)
    redis = RecordingRedis()

    await run_due_saved_search_scrapes({"session_factory": session_factory, "redis": redis})

    assert redis.enqueued == []
    async with session_factory() as session:
        jobs = (await session.execute(ScrapeJob.__table__.select())).fetchall()
        assert jobs == []


async def test_saved_search_scheduler_skips_disabled_search(session_factory):
    await _seed_source(session_factory)
    stale = datetime.now(timezone.utc) - timedelta(hours=2)
    await _seed_saved_search(session_factory, last_run_at=stale, enabled=False)
    redis = RecordingRedis()

    await run_due_saved_search_scrapes({"session_factory": session_factory, "redis": redis})

    assert redis.enqueued == []


async def test_saved_search_scheduler_creates_one_job_per_source(session_factory):
    await _seed_source(session_factory)
    async with session_factory() as session:
        session.add(Source(code="mojauto", name="Moj Auto", domain="mojauto.rs", country="RS"))
        await session.commit()
    await _seed_saved_search(session_factory, last_run_at=None)
    redis = RecordingRedis()

    await run_due_saved_search_scrapes({"session_factory": session_factory, "redis": redis})

    assert len(redis.enqueued) == 2


async def test_skips_disabled_schedule(session_factory):
    source_id = await _seed_source(session_factory)
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    await _seed_schedule(session_factory, source_id, next_run_at=past, enabled=False)
    redis = RecordingRedis()

    await run_due_scheduled_scrapes({"session_factory": session_factory, "redis": redis})

    assert redis.enqueued == []
