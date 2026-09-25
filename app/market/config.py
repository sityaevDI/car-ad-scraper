"""Reads/creates the singleton MarketConfig row (app/models/market.py) that backs the
admin-editable thresholds exposed at /api/v1/market/config.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.market import SINGLETON_ID, MarketConfig


async def get_market_config(session: AsyncSession) -> MarketConfig:
    """Same lazy-create-on-first-read pattern as app/scraping/rate_limit.py::get_scrape_rate_limit:
    the row doesn't exist until something reads it, seeded from app/config.py's market_* defaults
    at that point.
    """
    row = await session.get(MarketConfig, SINGLETON_ID)
    if row is None:
        settings = get_settings()
        row = MarketConfig(
            id=SINGLETON_ID,
            min_sample_size=settings.market_min_sample_size,
            mileage_bucket_km=settings.market_mileage_bucket_km,
            outlier_iqr_multiplier=settings.market_outlier_iqr_multiplier,
            deviation_market_band_pct=settings.market_deviation_market_band_pct,
            deviation_significant_band_pct=settings.market_deviation_significant_band_pct,
            confidence_medium_min_sample=settings.market_confidence_medium_min_sample,
            confidence_high_min_sample=settings.market_confidence_high_min_sample,
            confidence_high_dispersion_ratio=settings.market_confidence_high_dispersion_ratio,
            max_equipment_adjustment_pct=settings.market_max_equipment_adjustment_pct,
        )
        session.add(row)
        await session.flush()
    return row
