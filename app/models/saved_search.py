import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin

# Schema only — no CRUD/scheduling/matching logic yet. See docs/adr/02_DOMAIN_MODEL.md §6.
# This is the future home of the "one filter group, alerts across every source" flow the user
# specifically called out as the standout feature.


class SavedSearch(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "saved_searches"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    query: Mapped[dict] = mapped_column(JSON, nullable=False)
    # How the results are laid out when the saved search is opened (group_by / min_group_count /
    # sort — see SavedSearchView). Deliberately a separate column from `query`: `query` is what gets
    # scraped and matched (SearchQuery.stable_hash() in app/notifications/matching.py and the job
    # query in app/scraping/scheduler.py), and presentation must never change that identity.
    # NULL = no saved layout, the opener falls back to the user's own default.
    view_settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notification_settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
