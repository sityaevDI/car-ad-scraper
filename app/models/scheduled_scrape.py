import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin

# A standalone admin-defined "run this query every N minutes" schedule — deliberately not tied to
# SavedSearch/subscription plans (see docs/adr/20_ROLES_AND_ADMIN.md and issue #26, which is the
# bigger per-user/per-plan saved-search refresh scheduler this is not attempting to replace).


class ScheduledScrape(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "scheduled_scrapes"

    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("sources.id"), nullable=False)
    query: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_job_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("scrape_jobs.id"), nullable=True)
