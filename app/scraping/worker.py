"""arq worker process. Run with: arq app.scraping.worker.WorkerSettings

Shared resources (session factory, proxy provider) are put on `ctx` in on_startup — the standard
arq idiom — rather than fetched inside run_scrape_job, so the task function can be called directly
in tests with a hand-built ctx dict, no monkeypatching required.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from arq import cron, func
from arq.connections import RedisSettings
from sqlalchemy.exc import IntegrityError

from app.auth.email import get_email_sender
from app.config import get_settings
from app.db.session import get_session_factory
from app.models.scrape_job import ScrapeJob, ScrapeJobStatus, ScrapeJobType
from app.models.source import Source
from app.notifications.delivery import send_notification_email
from app.notifications.matching import generate_notifications_for_job
from app.scraping.pipeline import run_scrape
from app.scraping.proxy import get_proxy_provider
from app.scraping.rate_limit import get_scrape_rate_limit
from app.scraping.scheduler import (
    recompute_dirty_market_segments,
    run_due_saved_search_scrapes,
    run_due_scheduled_scrapes,
)
from app.scraping.schemas import decode_job_query

# arq's own ceiling on the whole run_scrape_job call (it wraps every job in its own
# asyncio.wait_for, default 300s). Set deliberately far above anything _estimate_job_timeout_seconds
# below should ever produce for a realistic max_pages — this is only a last-resort net for a truly
# wedged run, not the real per-job limit.
_ARQ_HARD_TIMEOUT_SECONDS = 24 * 60 * 60

# A scrape job's own soft timeout, sized to its max_pages instead of one flat number for every
# job — a 5-page SEARCH and a 500-page FULL_SOURCE_REFRESH need wildly different budgets, and
# arq's flat 300s default killed both indiscriminately after exactly 5 minutes regardless (see the
# incident this fixes: two jobs — one 500-page FULL_SOURCE_REFRESH, one 50-page SEARCH for "Alfa
# Romeo" — both silently cancelled mid-crawl and left stuck at RUNNING forever).
#
# Worst case per page is 1 search-page fetch + one equipment-detail fetch per listing on that page
# (every listing turns out to be brand new — see pipeline.py's _enrich_with_detail). 25 matches
# the resultsPerPage Polovni Automobili actually returns (tests/fixtures/polovniautomobili/
# search_page_01.html) — not load-bearing on real scraping behavior, just the assumption this
# estimate is built on. Each of those requests is paced up to delay+jitter apart. The floor keeps
# small jobs at least as much headroom as the old flat default had.
_ASSUMED_LISTINGS_PER_PAGE = 25
_MIN_JOB_TIMEOUT_SECONDS = 300.0


def _estimate_job_timeout_seconds(max_pages: int, delay: float, jitter: float) -> float:
    requests_per_page = 1 + _ASSUMED_LISTINGS_PER_PAGE
    return max(_MIN_JOB_TIMEOUT_SECONDS, max_pages * requests_per_page * (delay + jitter))


async def _on_startup(ctx: dict[str, Any]) -> None:
    ctx["session_factory"] = get_session_factory()
    ctx["proxy_provider"] = get_proxy_provider()
    ctx["email_sender"] = get_email_sender()


async def run_scrape_job(ctx: dict[str, Any], job_id: str) -> None:
    session_factory = ctx["session_factory"]
    async with session_factory() as session:
        job = await session.get(ScrapeJob, uuid.UUID(job_id))
        if job is None:
            return
        if job.status == ScrapeJobStatus.CANCELLED:
            return

        job.status = ScrapeJobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        try:
            await session.commit()
        except IntegrityError:
            # uq_scrape_jobs_one_running_per_source (migrations/c4d5e6f7a8b9): another job for
            # this same source is already RUNNING. Two concurrent crawls of one source can
            # deadlock each other in Postgres — UPDATEing overlapping Listing rows in whatever
            # order each happens to encounter them — reproduced in production 2026-09-13. Losing
            # this race is expected and fine: the schedule/saved-search cron that created this job
            # already advanced its own next-run time regardless of whether the job succeeds (see
            # scheduler.py), so it'll simply try again next interval once the other crawl is done.
            await session.rollback()
            # rollback() expires every attribute on `job` — touching any of them (even just to
            # read source_id for the message below) without reloading first raises
            # MissingGreenlet, since the lazy-reload it'd trigger can't run mid-flush here.
            job = await session.get(ScrapeJob, uuid.UUID(job_id))
            assert job is not None
            job.status = ScrapeJobStatus.FAILED
            job.error = {
                "type": "ConcurrentScrapeError",
                "message": f"Another job for source {job.source_id} is already running",
            }
            job.finished_at = datetime.now(timezone.utc)
            await session.commit()
            return

        source = await session.get(Source, job.source_id)
        assert source is not None
        query, max_pages = decode_job_query(job.query)
        rate_limit = await get_scrape_rate_limit(session)
        timeout_seconds = _estimate_job_timeout_seconds(
            max_pages, rate_limit.request_delay_seconds, rate_limit.request_jitter_seconds
        )

        try:
            stats = await asyncio.wait_for(
                run_scrape(
                    session,
                    source_code=source.code,
                    query=query,
                    max_pages=max_pages,
                    proxy_provider=ctx["proxy_provider"],
                    mark_removed=job.job_type == ScrapeJobType.FULL_SOURCE_REFRESH,
                ),
                timeout=timeout_seconds,
            )
        except (Exception, asyncio.CancelledError) as exc:  # noqa: BLE001 - persisted below, not swallowed silently
            # A failure inside run_scrape (e.g. an IntegrityError from a concurrent scrape of the
            # same source racing on the same new listing) leaves the session's transaction needing
            # an explicit rollback before it can be used again — without this, the commit() below
            # itself raises PendingRollbackError, so the real failure never gets recorded and the
            # job is left stuck instead of FAILED.
            #
            # asyncio.CancelledError is caught explicitly alongside Exception — it isn't a subclass
            # of Exception (BaseException instead, since Python 3.8) — so a cancellation, whether
            # from the timeout above or an external one (arq's own hard ceiling, a worker
            # shutdown), still gets persisted as FAILED with error detail instead of leaving the
            # row stuck at RUNNING forever with no trace, which is exactly what silently happened
            # before this: `except Exception` let CancelledError straight through uncaught.
            await session.rollback()
            # `job` may no longer be tracked by `session` at all: a crawl of any real size hits
            # run_scrape's periodic session.expunge_all() (app/scraping/pipeline.py) well before
            # failing, which detaches every object the session was holding, `job` included.
            # Mutating a detached instance doesn't register it as dirty — commit() below would
            # silently do nothing for it, leaving the row stuck at RUNNING with no error recorded
            # (the same failure mode this rollback+reload already fixes for the IntegrityError
            # branch above, just triggered by expunge instead of rollback's attribute-expiry).
            job = await session.get(ScrapeJob, uuid.UUID(job_id))
            assert job is not None
            job.status = ScrapeJobStatus.FAILED
            if isinstance(exc, (TimeoutError, asyncio.CancelledError)):
                job.error = {
                    "type": type(exc).__name__,
                    "message": (
                        f"Scrape job exceeded its computed timeout of {timeout_seconds:.0f}s "
                        f"(max_pages={max_pages}), or was cancelled"
                    ),
                }
            else:
                job.error = {"type": type(exc).__name__, "message": str(exc)}
            job.finished_at = datetime.now(timezone.utc)
            await session.commit()
            raise

        async def _enqueue_notification_email(notification_id: str) -> None:
            await ctx["redis"].enqueue_job("send_notification_email", notification_id)

        await generate_notifications_for_job(session, job, stats, enqueue_email=_enqueue_notification_email)

        # Reload for the same reason as the exception branch above: a crawl this size has almost
        # certainly gone through session.expunge_all() at least once by now, detaching `job`.
        # Reproduced in production 2026-09-20: a FULL_SOURCE_REFRESH that touched ~2,200 listings
        # returned clean (no exception, a normal arq success log) but its own row stayed RUNNING
        # forever — job.status below was set on a floating object nothing was ever going to
        # flush — which then blocked every later job for the same source via
        # uq_scrape_jobs_one_running_per_source.
        job = await session.get(ScrapeJob, uuid.UUID(job_id))
        assert job is not None
        job.status = ScrapeJobStatus.PARTIAL if stats.blocked else ScrapeJobStatus.COMPLETED
        job.stats = {
            "listings_seen": stats.listings_seen,
            "listings_created": stats.listings_created,
            "listings_updated": stats.listings_updated,
            "listings_removed": stats.listings_removed,
            "outcome_counts": stats.outcome_counts,
            "error_detail": stats.error_detail,
        }
        job.finished_at = datetime.now(timezone.utc)
        await session.commit()


class WorkerSettings:
    functions = [func(run_scrape_job, timeout=_ARQ_HARD_TIMEOUT_SECONDS), send_notification_email]
    cron_jobs = [
        cron(run_due_scheduled_scrapes, second=0),
        cron(run_due_saved_search_scrapes, second=0),
        cron(recompute_dirty_market_segments, second=0),
    ]
    on_startup = _on_startup
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
