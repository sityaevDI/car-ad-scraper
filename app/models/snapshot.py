import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UUIDPkMixin, utcnow


class ListingSnapshot(UUIDPkMixin, Base):
    """Append-only history row for a Listing (price/mileage/title over time).

    Never overwritten or deleted — see docs/adr/17_AGENT_INSTRUCTIONS.md "Never overwrite
    historical snapshots when the current listing changes". `raw_payload` holds the full raw
    parsed dict from the source adapter (object storage is an open decision — see
    docs/adr/18_DECISIONS_AND_OPEN_QUESTIONS.md — inline JSON is the MVP stand-in).
    """

    __tablename__ = "listing_snapshots"

    listing_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("listings.id"), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    price: Mapped[int] = mapped_column(Integer, nullable=False)
    mileage_km: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
