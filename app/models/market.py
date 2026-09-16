import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin, utcnow

SINGLETON_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class MarketConfidence(str, enum.Enum):
    INSUFFICIENT = "insufficient"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SegmentCriteriaMixin:
    """Segment-defining columns shared by MarketDirtySegment and MarketPriceSnapshot below.
    `segment_key` (app/market/segment.py::SegmentCriteria.key()) is a sha256 hash of these same
    fields — a stable, compact id for the segment — but a hash can't be reversed back into "which
    listings does this match", so the actual criteria travel alongside it on every row that needs
    to query or describe a segment, rather than being looked up from the key.
    """

    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    make: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    production_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fuel_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    transmission: Mapped[str | None] = mapped_column(String(32), nullable=True)
    body_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    engine_volume_bucket: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mileage_bucket: Mapped[int] = mapped_column(Integer, nullable=False)


class MarketPriceSnapshot(SegmentCriteriaMixin, UUIDPkMixin, Base):
    """Append-only per-segment market price estimate — see app/market/service.py. Never
    overwritten (same convention as ListingSnapshot); the "current" value for a segment is the
    row with the latest computed_at, which also makes this table double as Phase 3 (#33) history
    data without a second migration later.
    """

    __tablename__ = "market_price_snapshots"
    __table_args__ = (Index("ix_market_price_snapshots_segment_key_computed_at", "segment_key", "computed_at"),)

    segment_key: Mapped[str] = mapped_column(String(64), nullable=False)

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(16), nullable=False)

    # Raw comparable-listing count before outlier removal vs. the count actually used for the
    # estimate — see app/market/stats.py. estimated_price/price_low/price_high are null when
    # confidence is INSUFFICIENT (below market_min_sample_size raw listings).
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    filtered_sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_low: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_high: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    confidence: Mapped[MarketConfidence] = mapped_column(
        Enum(MarketConfidence, native_enum=False, length=16), nullable=False
    )


class MarketDirtySegment(SegmentCriteriaMixin, Base):
    """Poor-man's dedup queue: a segment gets one row here per "something in it changed" event
    (see app/scraping/pipeline.py), no matter how many listings in it changed before the batch
    recompute (app/scraping/scheduler.py::recompute_dirty_market_segments) gets to it. Carries the
    same segment-criteria columns as MarketPriceSnapshot so the recompute step can query "active
    listings matching this segment" directly, without needing to reverse `segment_key`.
    """

    __tablename__ = "market_dirty_segments"

    segment_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    marked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class MarketConfig(TimestampMixin, Base):
    """Runtime-editable market calculation thresholds. Singleton row (always `SINGLETON_ID`) —
    same pattern as app/models/scrape_rate_limit.py. app/config.py's market_* fields only seed
    this row the first time it's read (see app/market/config.py); once it exists, the DB row is
    the source of truth.
    """

    __tablename__ = "market_configs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=lambda: SINGLETON_ID)
    min_sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mileage_bucket_km: Mapped[int] = mapped_column(Integer, nullable=False)
    outlier_iqr_multiplier: Mapped[float] = mapped_column(Float, nullable=False)
    deviation_market_band_pct: Mapped[float] = mapped_column(Float, nullable=False)
    deviation_significant_band_pct: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_medium_min_sample: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_high_min_sample: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_high_dispersion_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    max_equipment_adjustment_pct: Mapped[float] = mapped_column(Float, nullable=False)


class MarketEquipmentWeight(TimestampMixin, Base):
    """Flat price adjustment per normalized equipment slug (see
    app/sources/polovniautomobili/mapper.py's `_EQUIPMENT_NORMALIZED`), applied on top of a
    segment's estimated_price for a specific listing — see app/market/pricing.py. Seeded with a
    curated starter list by the migration that creates this table; not exhaustive, and the
    percentages are directional placeholders, not a calibrated model.
    """

    __tablename__ = "market_equipment_weights"

    equipment_slug: Mapped[str] = mapped_column(String(64), primary_key=True)
    adjustment_pct: Mapped[float] = mapped_column(Float, nullable=False)
