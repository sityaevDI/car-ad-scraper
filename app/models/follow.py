import uuid

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin

# A user subscribing to price-drop alerts for one listing. See issue #21 — the notification event
# itself (PRICE_DROP) is generated in app/notifications/matching.py once a scrape sees the price
# decrease, not here; this table only records the subscription.


class Follow(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "follows"
    __table_args__ = (UniqueConstraint("user_id", "listing_id", name="uq_follows_user_id_listing_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    listing_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("listings.id"), nullable=False, index=True)
