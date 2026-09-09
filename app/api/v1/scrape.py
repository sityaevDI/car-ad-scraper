import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from arq.jobs import Job
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_csrf
from app.db.session import get_session
from app.models.scrape_job import ScrapeJob, ScrapeJobStatus, ScrapeJobType
from app.models.user import User
from app.scraping.pipeline import get_or_create_source
from app.scraping.queue import get_arq_pool, get_job_enqueuer
from app.scraping.schemas import ScrapeJobCreate, ScrapeJobOut, encode_job_query
from app.sources.registry import SOURCE_REGISTRY

router = APIRouter(prefix="/scrape", tags=["scrape"])

_TERMINAL_STATUSES = {
    ScrapeJobStatus.COMPLETED,
    ScrapeJobStatus.PARTIAL,
    ScrapeJobStatus.FAILED,
    ScrapeJobStatus.CANCELLED,
}


@router.post("/jobs", response_model=ScrapeJobOut, status_code=201)
async def create_scrape_job(
    payload: ScrapeJobCreate,
    session: AsyncSession = Depends(get_session),
    enqueue: Callable[[str], Awaitable[None]] = Depends(get_job_enqueuer),
    _current_user: User = Depends(get_current_user),
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
    _current_user: User = Depends(get_current_user),
) -> ScrapeJobOut:
    job = await session.get(ScrapeJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Scrape job not found")
    return ScrapeJobOut.model_validate(job)


@router.post("/jobs/{job_id}/cancel", response_model=ScrapeJobOut)
async def cancel_scrape_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(get_current_user),
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
