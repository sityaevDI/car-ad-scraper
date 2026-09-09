import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin

# Schema only — no delivery (email/in-app) yet. See docs/adr/02_DOMAIN_MODEL.md §8 and
# docs/adr/10_NOTIFICATIONS.md.


class NotificationType(str, enum.Enum):
    NEW_MATCH = "new_match"
    PRICE_DROP = "price_drop"
    LISTING_REMOVED = "listing_removed"
    MARKET_CHANGE = "market_change"


class Notification(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType, native_enum=False, length=32), nullable=False)
    # Set for listing-scoped events (NEW_MATCH/PRICE_DROP/LISTING_REMOVED); backs the send cooldown
    # in app/notifications/service.py and lets the UI link straight to the listing. MARKET_CHANGE
    # (a market-segment event, not one listing) is expected to leave this null.
    listing_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("listings.id"), nullable=True, index=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
