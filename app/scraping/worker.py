"""arq worker process. Run with: arq app.scraping.worker.WorkerSettings

Shared resources (session factory, proxy provider) are put on `ctx` in on_startup — the standard
arq idiom — rather than fetched inside run_scrape_job, so the task function can be called directly
in tests with a hand-built ctx dict, no monkeypatching required.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from arq import cron
from arq.connections import RedisSettings

from app.auth.email import get_email_sender
from app.config import get_settings
from app.db.session import get_session_factory
from app.models.scrape_job import ScrapeJob, ScrapeJobStatus
from app.models.source import Source
from app.notifications.delivery import send_notification_email
from app.notifications.matching import generate_notifications_for_job
from app.scraping.pipeline import run_scrape
from app.scraping.proxy import get_proxy_provider
from app.scraping.scheduler import run_due_saved_search_scrapes, run_due_scheduled_scrapes
from app.scraping.schemas import decode_job_query


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
        await session.commit()

        source = await session.get(Source, job.source_id)
        assert source is not None
        query, max_pages = decode_job_query(job.query)

        try:
            stats = await run_scrape(
                session,
                source_code=source.code,
                query=query,
                max_pages=max_pages,
                proxy_provider=ctx["proxy_provider"],
            )
        except Exception as exc:  # noqa: BLE001 - persisted below, not swallowed silently
            job.status = ScrapeJobStatus.FAILED
            job.error = {"type": type(exc).__name__, "message": str(exc)}
            job.finished_at = datetime.now(timezone.utc)
            await session.commit()
            raise

        async def _enqueue_notification_email(notification_id: str) -> None:
            await ctx["redis"].enqueue_job("send_notification_email", notification_id)

        await generate_notifications_for_job(session, job, stats, enqueue_email=_enqueue_notification_email)

        job.status = ScrapeJobStatus.PARTIAL if stats.blocked else ScrapeJobStatus.COMPLETED
        job.stats = {
            "listings_seen": stats.listings_seen,
            "listings_created": stats.listings_created,
            "listings_updated": stats.listings_updated,
            "outcome_counts": stats.outcome_counts,
        }
        job.finished_at = datetime.now(timezone.utc)
        await session.commit()


class WorkerSettings:
    functions = [run_scrape_job, send_notification_email]
    cron_jobs = [cron(run_due_scheduled_scrapes, second=0), cron(run_due_saved_search_scrapes, second=0)]
    on_startup = _on_startup
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
