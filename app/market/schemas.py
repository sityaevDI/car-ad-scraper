from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.market import MarketConfidence


class PriceScoreOut(BaseModel):
    price_ratio: float
    deviation_pct: float
    label: str


class MarketEstimateOut(BaseModel):
    estimated_price: int | None
    currency: str
    price_low: int | None
    price_high: int | None
    confidence: MarketConfidence
    # Raw comparable-listing count in the segment before outlier filtering — "how many similar
    # cars are out there", not the (usually smaller) count actually used for the median/range.
    comparable_listings_count: int
    computed_at: datetime
    algorithm_version: str


class MarketComparisonOut(BaseModel):
    """GET /listings/{id}/market-comparison — docs/adr/08_API.md. `market` and `price_score` are
    both None when no snapshot exists yet for the listing's segment (never computed synchronously
    on this read path — see app/market/service.py).
    """

    market: MarketEstimateOut | None
    price_score: PriceScoreOut | None


class MarketConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    min_sample_size: int
    mileage_bucket_km: int
    outlier_iqr_multiplier: float
    deviation_market_band_pct: float
    deviation_significant_band_pct: float
    confidence_medium_min_sample: int
    confidence_high_min_sample: int
    confidence_high_dispersion_ratio: float
    max_equipment_adjustment_pct: float


class MarketConfigUpdate(BaseModel):
    min_sample_size: int | None = Field(default=None, ge=1)
    mileage_bucket_km: int | None = Field(default=None, ge=1)
    outlier_iqr_multiplier: float | None = Field(default=None, ge=0)
    deviation_market_band_pct: float | None = Field(default=None, ge=0)
    deviation_significant_band_pct: float | None = Field(default=None, ge=0)
    confidence_medium_min_sample: int | None = Field(default=None, ge=1)
    confidence_high_min_sample: int | None = Field(default=None, ge=1)
    confidence_high_dispersion_ratio: float | None = Field(default=None, ge=0)
    max_equipment_adjustment_pct: float | None = Field(default=None, ge=0)
