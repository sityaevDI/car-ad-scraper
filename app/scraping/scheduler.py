"""arq cron jobs that turn "it's time to refresh X" into an enqueued ScrapeJob. Runs inside the
same worker process as run_scrape_job (see app/scraping/worker.py) — no separate scheduler
container needed for either of these simple, interval-based schedules.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.config import get_settings
from app.market.service import MarketPriceService
from app.models.scheduled_scrape import ScheduledScrape
from app.models.scrape_job import ScrapeJob, ScrapeJobStatus, ScrapeJobType
from app.models.source import Source
from app.saved_searches.repository import SavedSearchRepository
from app.scraping.schemas import encode_job_query
from app.search.query import SearchQuery

_SAVED_SEARCH_MAX_PAGES = 5

# Dirty segments processed per cron tick. This cron runs every minute (see WorkerSettings.cron_jobs
# in app/scraping/worker.py) same as the other two, so a queue deeper than this just clears over a
# few more ticks rather than blocking anything — no need to size it to "clear everything at once".
_MARKET_RECOMPUTE_BATCH_SIZE = 200


async def run_due_scheduled_scrapes(ctx: dict[str, Any]) -> None:
    session_factory = ctx["session_factory"]
    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        stmt = select(ScheduledScrape).where(ScheduledScrape.enabled.is_(True), ScheduledScrape.next_run_at <= now)
        due = (await session.execute(stmt)).scalars().all()

        for scheduled in due:
            job = ScrapeJob(
                source_id=scheduled.source_id,
                job_type=scheduled.job_type,
                status=ScrapeJobStatus.PENDING,
                query=scheduled.query,
            )
            session.add(job)
            await session.flush()

            scheduled.last_run_at = now
            scheduled.next_run_at = now + timedelta(minutes=scheduled.interval_minutes)
            scheduled.last_job_id = job.id
            await session.commit()

            await ctx["redis"].enqueue_job("run_scrape_job", str(job.id))


async def run_due_saved_search_scrapes(ctx: dict[str, Any]) -> None:
    """One ScrapeJob per (due SavedSearch, enabled Source) — see issue #26. Matches by *filters*,
    not by a source the saved search doesn't itself know about, so this already extends past
    Phase 1's single source without changes once more Source rows exist (Phase 4).
    """
    session_factory = ctx["session_factory"]
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=get_settings().saved_search_refresh_minutes)

    async with session_factory() as session:
        due_saved_searches = await SavedSearchRepository(session).list_due(cutoff)
        if not due_saved_searches:
            return

        sources = (await session.execute(select(Source).where(Source.enabled.is_(True)))).scalars().all()

        for saved_search in due_saved_searches:
            search_query = SearchQuery.model_validate(saved_search.query)
            for source in sources:
                job = ScrapeJob(
                    source_id=source.id,
                    job_type=ScrapeJobType.SAVED_SEARCH_REFRESH,
                    status=ScrapeJobStatus.PENDING,
                    query=encode_job_query(search_query, max_pages=_SAVED_SEARCH_MAX_PAGES),
                )
                session.add(job)
                await session.flush()
                await ctx["redis"].enqueue_job("run_scrape_job", str(job.id))

            saved_search.last_run_at = now
            await session.commit()


async def recompute_dirty_market_segments(ctx: dict[str, Any]) -> None:
    """Batch half of the event-driven market price cadence (see app/market/__init__.py) — the
    other half is app/scraping/pipeline.py marking a segment dirty the moment a listing in it
    changes. One commit per tick; a segment left in the queue past `_MARKET_RECOMPUTE_BATCH_SIZE`
    just gets picked up on the next minute's tick instead of blocking this one.
    """
    session_factory = ctx["session_factory"]
    async with session_factory() as session:
        await MarketPriceService(session).recompute_due(_MARKET_RECOMPUTE_BATCH_SIZE)
        await session.commit()
