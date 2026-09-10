import asyncio
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
from app.models.scrape_job import ScrapeJob, ScrapeJobStatus, ScrapeJobType
from app.models.source import Source
from app.scraping import worker as worker_module
from app.scraping.pipeline import ScrapeStats
from app.scraping.proxy import NullProxyProvider
from app.scraping.schemas import encode_job_query
from app.search.query import SearchQuery


@pytest.fixture
async def worker_session_factory():
    # StaticPool keeps every session opened from this factory on the same in-memory sqlite DB —
    # run_scrape_job opens its own session per call, so a plain per-call engine wouldn't share
    # state with the row seeded by the test (same reasoning as tests/unit/test_auth_endpoints.py).
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _seed_job(
    factory,
    status: ScrapeJobStatus = ScrapeJobStatus.PENDING,
    query: dict | None = None,
    job_type: ScrapeJobType = ScrapeJobType.SEARCH,
) -> uuid.UUID:
    async with factory() as session:
        source = (
            await session.execute(select(Source).where(Source.code == "polovniautomobili"))
        ).scalar_one_or_none()
        if source is None:
            source = Source(
                code="polovniautomobili", name="Polovni Automobili", domain="polovniautomobili.com", country="RS"
            )
            session.add(source)
            await session.flush()
        job = ScrapeJob(source_id=source.id, job_type=job_type, status=status, query=query or {})
        session.add(job)
        await session.commit()
        return job.id


async def test_run_scrape_job_marks_completed_on_success(worker_session_factory, monkeypatch):
    job_id = await _seed_job(worker_session_factory)

    async def fake_run_scrape(session, source_code, query, max_pages=5, proxy_provider=None, mark_removed=False):
        return ScrapeStats(listings_seen=3, listings_created=2, listings_updated=1, outcome_counts={"success": 3})

    monkeypatch.setattr(worker_module, "run_scrape", fake_run_scrape)

    ctx = {"session_factory": worker_session_factory, "proxy_provider": NullProxyProvider()}
    await worker_module.run_scrape_job(ctx, str(job_id))

    async with worker_session_factory() as session:
        job = await session.get(ScrapeJob, job_id)
        assert job.status == ScrapeJobStatus.COMPLETED
        assert job.stats == {
            "listings_seen": 3,
            "listings_created": 2,
            "listings_updated": 1,
            "listings_removed": 0,
            "outcome_counts": {"success": 3},
            "error_detail": None,
        }
        assert job.started_at is not None
        assert job.finished_at is not None


async def test_run_scrape_job_marks_partial_when_blocked(worker_session_factory, monkeypatch):
    job_id = await _seed_job(worker_session_factory)

    async def fake_run_scrape(session, source_code, query, max_pages=5, proxy_provider=None, mark_removed=False):
        return ScrapeStats(listings_seen=1, listings_created=1, blocked=True, outcome_counts={"forbidden": 1})

    monkeypatch.setattr(worker_module, "run_scrape", fake_run_scrape)

    ctx = {"session_factory": worker_session_factory, "proxy_provider": NullProxyProvider()}
    await worker_module.run_scrape_job(ctx, str(job_id))

    async with worker_session_factory() as session:
        job = await session.get(ScrapeJob, job_id)
        assert job.status == ScrapeJobStatus.PARTIAL


async def test_run_scrape_job_marks_failed_on_exception(worker_session_factory, monkeypatch):
    job_id = await _seed_job(worker_session_factory)

    async def fake_run_scrape(session, source_code, query, max_pages=5, proxy_provider=None, mark_removed=False):
        raise RuntimeError("boom")

    monkeypatch.setattr(worker_module, "run_scrape", fake_run_scrape)

    ctx = {"session_factory": worker_session_factory, "proxy_provider": NullProxyProvider()}
    with pytest.raises(RuntimeError):
        await worker_module.run_scrape_job(ctx, str(job_id))

    async with worker_session_factory() as session:
        job = await session.get(ScrapeJob, job_id)
        assert job.status == ScrapeJobStatus.FAILED
        assert job.error == {"type": "RuntimeError", "message": "boom"}


async def test_run_scrape_job_marks_failed_when_session_needs_rollback(worker_session_factory, monkeypatch):
    """Mirrors a concurrent-scrape race in ListingRepository.upsert_listing: run_scrape leaves the
    session's transaction needing an explicit rollback (e.g. after a flush-time IntegrityError)
    before raising. Without a rollback first, the except block's own commit() would itself raise
    PendingRollbackError and the job would never get marked FAILED — see app/scraping/worker.py.
    """
    job_id = await _seed_job(worker_session_factory)

    async def fake_run_scrape(session, source_code, query, max_pages=5, proxy_provider=None, mark_removed=False):
        session.add(Source(code="polovniautomobili", name="dup", domain="dup.example.com", country="RS"))
        await session.flush()  # raises IntegrityError: code is unique

    monkeypatch.setattr(worker_module, "run_scrape", fake_run_scrape)

    ctx = {"session_factory": worker_session_factory, "proxy_provider": NullProxyProvider()}
    with pytest.raises(Exception):
        await worker_module.run_scrape_job(ctx, str(job_id))

    async with worker_session_factory() as session:
        job = await session.get(ScrapeJob, job_id)
        assert job.status == ScrapeJobStatus.FAILED
        assert job.finished_at is not None


async def test_run_scrape_job_passes_stored_query_and_max_pages_to_run_scrape(worker_session_factory, monkeypatch):
    job_id = await _seed_job(worker_session_factory, query=encode_job_query(SearchQuery(make="Audi"), max_pages=2))
    received = {}

    async def fake_run_scrape(session, source_code, query, max_pages=5, proxy_provider=None, mark_removed=False):
        received["source_code"] = source_code
        received["query"] = query
        received["max_pages"] = max_pages
        return ScrapeStats()

    monkeypatch.setattr(worker_module, "run_scrape", fake_run_scrape)

    ctx = {"session_factory": worker_session_factory, "proxy_provider": NullProxyProvider()}
    await worker_module.run_scrape_job(ctx, str(job_id))

    assert received["source_code"] == "polovniautomobili"
    assert received["query"].make == "Audi"
    assert received["max_pages"] == 2


class RecordingRedis:
    def __init__(self):
        self.enqueued: list[tuple[str, tuple]] = []

    async def enqueue_job(self, function: str, *args) -> None:
        self.enqueued.append((function, args))


async def test_run_scrape_job_generates_and_enqueues_notification_for_price_drop(worker_session_factory, monkeypatch):
    job_id = await _seed_job(worker_session_factory)
    now = datetime.now(timezone.utc)

    async with worker_session_factory() as session:
        source = (await session.execute(Source.__table__.select())).first()
        listing = Listing(
            source_id=source.id,
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
        session.add(listing)
        await session.flush()
        follower_id = uuid.uuid4()
        session.add(Follow(user_id=follower_id, listing_id=listing.id))
        await session.commit()
        listing_id = listing.id

    async def fake_run_scrape(session, source_code, query, max_pages=5, proxy_provider=None, mark_removed=False):
        return ScrapeStats(listings_seen=1, listings_updated=1, price_drops=[(listing_id, 12_000, 10_000)])

    monkeypatch.setattr(worker_module, "run_scrape", fake_run_scrape)

    redis = RecordingRedis()
    ctx = {"session_factory": worker_session_factory, "proxy_provider": NullProxyProvider(), "redis": redis}
    await worker_module.run_scrape_job(ctx, str(job_id))

    async with worker_session_factory() as session:
        notifications = (await session.execute(select(Notification))).scalars().all()
        assert len(notifications) == 1
        assert notifications[0].user_id == follower_id
        assert notifications[0].type == NotificationType.PRICE_DROP

    assert len(redis.enqueued) == 1
    assert redis.enqueued[0][0] == "send_notification_email"


async def test_run_scrape_job_requests_mark_removed_only_for_full_source_refresh(worker_session_factory, monkeypatch):
    search_job_id = await _seed_job(worker_session_factory, job_type=ScrapeJobType.SEARCH)
    full_refresh_job_id = await _seed_job(worker_session_factory, job_type=ScrapeJobType.FULL_SOURCE_REFRESH)

    async def fake_run_scrape(session, source_code, query, max_pages=5, proxy_provider=None, mark_removed=False):
        return ScrapeStats(listings_removed=2 if mark_removed else 0)

    monkeypatch.setattr(worker_module, "run_scrape", fake_run_scrape)
    ctx = {"session_factory": worker_session_factory, "proxy_provider": NullProxyProvider()}

    await worker_module.run_scrape_job(ctx, str(search_job_id))
    await worker_module.run_scrape_job(ctx, str(full_refresh_job_id))

    async with worker_session_factory() as session:
        search_job = await session.get(ScrapeJob, search_job_id)
        full_refresh_job = await session.get(ScrapeJob, full_refresh_job_id)
        assert search_job.stats["listings_removed"] == 0
        assert full_refresh_job.stats["listings_removed"] == 2


def test_estimate_job_timeout_seconds_scales_with_max_pages():
    # Floor: a tiny job doesn't get squeezed below the old flat default.
    assert worker_module._estimate_job_timeout_seconds(max_pages=1, delay=0.8, jitter=0.4) == (
        worker_module._MIN_JOB_TIMEOUT_SECONDS
    )
    # A big job's budget scales with max_pages instead of being capped at the same 300s.
    big = worker_module._estimate_job_timeout_seconds(max_pages=500, delay=0.8, jitter=0.4)
    assert big == pytest.approx(500 * (1 + worker_module._ASSUMED_LISTINGS_PER_PAGE) * 1.2)
    assert big > worker_module._MIN_JOB_TIMEOUT_SECONDS


async def test_run_scrape_job_marks_failed_on_computed_timeout(worker_session_factory, monkeypatch):
    """A job that outruns its computed timeout gets cancelled and recorded as FAILED instead of
    being left stuck at RUNNING forever. Reproduces the bug this fixes: arq's own flat 300s
    job_timeout used to cancel jobs like this via asyncio.CancelledError, which the old `except
    Exception` handler didn't catch (CancelledError is a BaseException, not an Exception, since
    Python 3.8) — so the job row never got updated and stayed RUNNING with no trace of the failure.
    """
    job_id = await _seed_job(worker_session_factory)
    monkeypatch.setattr(worker_module, "_estimate_job_timeout_seconds", lambda *args, **kwargs: 0.05)

    async def fake_run_scrape(session, source_code, query, max_pages=5, proxy_provider=None, mark_removed=False):
        await asyncio.sleep(10)
        return ScrapeStats()

    monkeypatch.setattr(worker_module, "run_scrape", fake_run_scrape)

    ctx = {"session_factory": worker_session_factory, "proxy_provider": NullProxyProvider()}
    with pytest.raises(TimeoutError):
        await worker_module.run_scrape_job(ctx, str(job_id))

    async with worker_session_factory() as session:
        job = await session.get(ScrapeJob, job_id)
        assert job.status == ScrapeJobStatus.FAILED
        assert job.error["type"] == "TimeoutError"
        assert job.finished_at is not None


async def test_run_scrape_job_skips_already_cancelled_job(worker_session_factory, monkeypatch):
    job_id = await _seed_job(worker_session_factory, status=ScrapeJobStatus.CANCELLED)
    called = False

    async def fake_run_scrape(*args, **kwargs):
        nonlocal called
        called = True
        return ScrapeStats()

    monkeypatch.setattr(worker_module, "run_scrape", fake_run_scrape)

    ctx = {"session_factory": worker_session_factory, "proxy_provider": NullProxyProvider()}
    await worker_module.run_scrape_job(ctx, str(job_id))

    assert called is False
    async with worker_session_factory() as session:
        job = await session.get(ScrapeJob, job_id)
        assert job.status == ScrapeJobStatus.CANCELLED
