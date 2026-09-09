"""arq cron job: creates and enqueues a ScrapeJob for every due ScheduledScrape, then advances
next_run_at. Runs inside the same worker process as run_scrape_job (see app/scraping/worker.py) —
no separate scheduler container needed for this simple, interval-based schedule.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.models.scheduled_scrape import ScheduledScrape
from app.models.scrape_job import ScrapeJob, ScrapeJobStatus


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
