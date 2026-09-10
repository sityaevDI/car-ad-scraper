import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from arq.jobs import Job
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin, require_csrf
from app.db.session import get_session
from app.models.scheduled_scrape import ScheduledScrape
from app.models.scrape_job import ScrapeJob, ScrapeJobStatus, ScrapeJobType
from app.models.user import User
from app.scraping.pipeline import get_or_create_source
from app.scraping.queue import get_arq_pool, get_job_enqueuer
from app.scraping.schemas import (
    ScheduledScrapeCreate,
    ScheduledScrapeOut,
    ScheduledScrapeUpdate,
    ScrapeJobCreate,
    ScrapeJobOut,
    encode_job_query,
)
from app.sources.registry import SOURCE_REGISTRY

# Job management is an admin action (docs/adr/13_ADMIN.md "Controls"), not a regular-user
# feature — every route here sits behind require_admin rather than get_current_user.
router = APIRouter(prefix="/scrape", tags=["scrape"])

_TERMINAL_STATUSES = {
    ScrapeJobStatus.COMPLETED,
    ScrapeJobStatus.PARTIAL,
    ScrapeJobStatus.FAILED,
    ScrapeJobStatus.CANCELLED,
}
_RETRYABLE_STATUSES = {ScrapeJobStatus.FAILED, ScrapeJobStatus.CANCELLED}


@router.get("/jobs", response_model=list[ScrapeJobOut])
async def list_scrape_jobs(
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_admin),
    status: ScrapeJobStatus | None = None,
    source_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ScrapeJobOut]:
    stmt = select(ScrapeJob).order_by(ScrapeJob.created_at.desc()).limit(limit).offset(offset)
    if status is not None:
        stmt = stmt.where(ScrapeJob.status == status)
    if source_id is not None:
        stmt = stmt.where(ScrapeJob.source_id == source_id)
    if date_from is not None:
        stmt = stmt.where(ScrapeJob.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(ScrapeJob.created_at <= date_to)
    jobs = (await session.execute(stmt)).scalars().all()
    return [ScrapeJobOut.model_validate(job) for job in jobs]


@router.post("/jobs", response_model=ScrapeJobOut, status_code=201)
async def create_scrape_job(
    payload: ScrapeJobCreate,
    session: AsyncSession = Depends(get_session),
    enqueue: Callable[[str], Awaitable[None]] = Depends(get_job_enqueuer),
    _current_user: User = Depends(require_admin),
    _csrf: None = Depends(require_csrf),
) -> ScrapeJobOut:
    adapter_cls = SOURCE_REGISTRY.get(payload.source_code)
    if adapter_cls is None:
        raise HTTPException(status_code=400, detail=f"Unknown source_code: {payload.source_code!r}")

    source = await get_or_create_source(
        session,
        code=adapter_cls.source_code,
        name=adapter_cls.display_name,
        domain=adapter_cls.domain,
        country=adapter_cls.country,
    )
    job = ScrapeJob(
        source_id=source.id,
        job_type=ScrapeJobType.SEARCH,
        status=ScrapeJobStatus.PENDING,
        query=encode_job_query(payload.query, payload.max_pages),
    )
    session.add(job)
    await session.commit()

    await enqueue(str(job.id))
    return ScrapeJobOut.model_validate(job)


@router.get("/jobs/{job_id}", response_model=ScrapeJobOut)
async def get_scrape_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_admin),
) -> ScrapeJobOut:
    job = await session.get(ScrapeJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Scrape job not found")
    return ScrapeJobOut.model_validate(job)


@router.post("/jobs/{job_id}/cancel", response_model=ScrapeJobOut)
async def cancel_scrape_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_admin),
    _csrf: None = Depends(require_csrf),
) -> ScrapeJobOut:
    """Best-effort: flips the DB row to CANCELLED and tries to abort the queued arq job. The
    worker only checks for CANCELLED once, at job start — a job already RUNNING will still run to
    completion (see app/scraping/worker.py). No anti-bot state machine (#29) backs this yet.
    """
    job = await session.get(ScrapeJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Scrape job not found")

    if job.status not in _TERMINAL_STATUSES:
        job.status = ScrapeJobStatus.CANCELLED
        job.finished_at = datetime.now(timezone.utc)
        await session.commit()

        try:
            pool = await get_arq_pool()
            try:
                await Job(str(job_id), pool).abort()
            finally:
                await pool.aclose()
        except Exception:  # noqa: BLE001 - cancellation is best-effort, DB state already updated
            pass

    return ScrapeJobOut.model_validate(job)


@router.post("/jobs/{job_id}/retry", response_model=ScrapeJobOut)
async def retry_scrape_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    enqueue: Callable[[str], Awaitable[None]] = Depends(get_job_enqueuer),
    _current_user: User = Depends(require_admin),
    _csrf: None = Depends(require_csrf),
) -> ScrapeJobOut:
    """Re-enqueues a FAILED/CANCELLED job in place (same row, same query) rather than creating a
    new one, so its history stays under one job id.
    """
    job = await session.get(ScrapeJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Scrape job not found")
    if job.status not in _RETRYABLE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Cannot retry a job in status {job.status.value!r}")

    job.status = ScrapeJobStatus.PENDING
    job.started_at = None
    job.finished_at = None
    job.error = None
    await session.commit()

    await enqueue(str(job.id))
    return ScrapeJobOut.model_validate(job)


@router.get("/schedules", response_model=list[ScheduledScrapeOut])
async def list_scheduled_scrapes(
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_admin),
) -> list[ScheduledScrapeOut]:
    stmt = select(ScheduledScrape).order_by(ScheduledScrape.created_at.desc())
    schedules = (await session.execute(stmt)).scalars().all()
    return [ScheduledScrapeOut.model_validate(s) for s in schedules]


_SCHEDULABLE_JOB_TYPES = {ScrapeJobType.SEARCH, ScrapeJobType.FULL_SOURCE_REFRESH}


@router.post("/schedules", response_model=ScheduledScrapeOut, status_code=201)
async def create_scheduled_scrape(
    payload: ScheduledScrapeCreate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_admin),
    _csrf: None = Depends(require_csrf),
) -> ScheduledScrapeOut:
    adapter_cls = SOURCE_REGISTRY.get(payload.source_code)
    if adapter_cls is None:
        raise HTTPException(status_code=400, detail=f"Unknown source_code: {payload.source_code!r}")

    if payload.job_type not in _SCHEDULABLE_JOB_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported job_type for a schedule: {payload.job_type.value!r}")

    if payload.job_type == ScrapeJobType.FULL_SOURCE_REFRESH and payload.query.model_dump(exclude_none=True):
        # mark_missing_as_removed (app/listings/repository.py) treats "not seen this crawl" as
        # "removed from the source" — safe only when the crawl actually covers the whole source.
        raise HTTPException(
            status_code=400, detail="full_source_refresh schedules must not filter the search query"
        )

    source = await get_or_create_source(
        session,
        code=adapter_cls.source_code,
        name=adapter_cls.display_name,
        domain=adapter_cls.domain,
        country=adapter_cls.country,
    )
    schedule = ScheduledScrape(
        source_id=source.id,
        job_type=payload.job_type,
        query=encode_job_query(payload.query, payload.max_pages),
        interval_minutes=payload.interval_minutes,
        next_run_at=payload.start_at or datetime.now(timezone.utc),
    )
    session.add(schedule)
    await session.commit()
    return ScheduledScrapeOut.model_validate(schedule)


@router.patch("/schedules/{schedule_id}", response_model=ScheduledScrapeOut)
async def update_scheduled_scrape(
    schedule_id: uuid.UUID,
    payload: ScheduledScrapeUpdate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_admin),
    _csrf: None = Depends(require_csrf),
) -> ScheduledScrapeOut:
    schedule = await session.get(ScheduledScrape, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if payload.interval_minutes is not None:
        schedule.interval_minutes = payload.interval_minutes
    if payload.enabled is not None:
        schedule.enabled = payload.enabled
    await session.commit()
    return ScheduledScrapeOut.model_validate(schedule)


@router.delete("/schedules/{schedule_id}", status_code=204)
async def delete_scheduled_scrape(
    schedule_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_admin),
    _csrf: None = Depends(require_csrf),
) -> None:
    schedule = await session.get(ScheduledScrape, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await session.delete(schedule)
    await session.commit()
