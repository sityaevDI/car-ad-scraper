import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
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
