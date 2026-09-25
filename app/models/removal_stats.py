from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import UniqueConstraint

from app.db.base import Base
from app.models.mixins import UUIDPkMixin, utcnow

ALL_SCOPE = ""


class RemovalStats(UUIDPkMixin, Base):
    """Precomputed rollup of listings that disappeared from their source (Listing.status=REMOVED)
    over the `period_days` days ending on `stat_date` (inclusive, UTC). Rebuilt by
    app/market/removal_stats.py twice a day — API reads never aggregate Listing directly.

    "Removed" is a proxy for "sold", not proof of it — see docs/adr/06_SEARCH_MARKET.md §10-11.
    `make`/`model` use ALL_SCOPE ("") instead of NULL for "all makes"/"all models" so the unique
    constraint below actually dedupes (NULLs are distinct in a unique index).
    """

    __tablename__ = "removal_stats"
    __table_args__ = (
        UniqueConstraint("stat_date", "period_days", "make", "model", name="uq_removal_stats_scope"),
    )

    stat_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    make: Mapped[str] = mapped_column(String(64), nullable=False, default=ALL_SCOPE)
    model: Mapped[str] = mapped_column(String(128), nullable=False, default=ALL_SCOPE)

    removed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    median_days_on_market: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_price_at_removal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_cut_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_price_cut_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
