from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

Period = Literal["day", "week", "month"]
PERIOD_DAYS: dict[str, int] = {"day": 1, "week": 7, "month": 30}


class RemovalMetrics(BaseModel):
    removed_count: int
    median_days_on_market: float | None = None
    median_price_at_removal: int | None = None
    # Fraction (0..1) of removed listings whose price was cut at least once before they left, and
    # the median size of that cut in percent.
    price_cut_share: float | None = None
    median_price_cut_pct: float | None = None


class RemovalBreakdownRow(RemovalMetrics):
    make: str
    model: str | None = None


class RemovalSeriesPoint(BaseModel):
    date: date
    removed_count: int


class RemovalStatsResponse(BaseModel):
    period: Period
    make: str | None = None
    as_of: date | None = None
    computed_at: datetime | None = None
    current: RemovalMetrics | None = None
    previous: RemovalMetrics | None = None
    series: list[RemovalSeriesPoint] = []
    breakdown: list[RemovalBreakdownRow] = []
