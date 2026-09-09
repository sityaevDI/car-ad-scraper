"""Producer side of the scrape job queue — importable by the FastAPI process without pulling in
worker internals (app/scraping/worker.py).
"""

from collections.abc import Awaitable, Callable

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import get_settings


async def get_arq_pool() -> ArqRedis:
    return await create_pool(RedisSettings.from_dsn(get_settings().redis_url))


async def enqueue_scrape_job(job_id: str) -> None:
    pool = await get_arq_pool()
    try:
        await pool.enqueue_job("run_scrape_job", job_id)
    finally:
        await pool.aclose()


def get_job_enqueuer() -> Callable[[str], Awaitable[None]]:
    """FastAPI dependency seam — overridden in tests with a recorder so endpoint tests don't need
    a real Redis/arq pool, mirroring app/auth/email.py's get_email_sender.
    """
    return enqueue_scrape_job
