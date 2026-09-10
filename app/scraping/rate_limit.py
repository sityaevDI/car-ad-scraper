"""Reads/creates the singleton `ScrapeRateLimit` row (app/models/scrape_rate_limit.py) that backs
the admin-editable request pacing exposed at /api/v1/scrape/rate-limit.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.scrape_rate_limit import SINGLETON_ID, ScrapeRateLimit


async def get_scrape_rate_limit(session: AsyncSession) -> ScrapeRateLimit:
    """Same lazy-create-on-first-read pattern as app/scraping/pipeline.py's
    get_or_create_source: the row doesn't exist until something reads it, seeded from
    app/config.py's scrape_request_* defaults at that point.
    """
    row = await session.get(ScrapeRateLimit, SINGLETON_ID)
    if row is None:
        settings = get_settings()
        row = ScrapeRateLimit(
            id=SINGLETON_ID,
            request_delay_seconds=settings.scrape_request_delay_seconds,
            request_jitter_seconds=settings.scrape_request_jitter_seconds,
            network_error_retry_delay_seconds=settings.scrape_network_error_retry_delay_seconds,
        )
        session.add(row)
        await session.flush()
    return row
