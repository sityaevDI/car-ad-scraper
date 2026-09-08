import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin

# Schema only — no queue/worker yet (Redis/ARQ job runner is a later phase per
# docs/adr/09_QUEUE_PRIORITY.md). See docs/adr/02_DOMAIN_MODEL.md §7.


class ScrapeJobType(str, enum.Enum):
    SEARCH = "search"
    LISTING_REFRESH = "listing_refresh"
    SAVED_SEARCH_REFRESH = "saved_search_refresh"
    FULL_SOURCE_REFRESH = "full_source_refresh"
    MARKET_REFRESH = "market_refresh"


class ScrapeJobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScrapeJob(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "scrape_jobs"

    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("sources.id"), nullable=False)
    job_type: Mapped[ScrapeJobType] = mapped_column(Enum(ScrapeJobType, native_enum=False, length=32), nullable=False)
    status: Mapped[ScrapeJobStatus] = mapped_column(
        Enum(ScrapeJobStatus, native_enum=False, length=16), default=ScrapeJobStatus.PENDING, nullable=False
    )
    query: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stats: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
