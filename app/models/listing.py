import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import UniqueConstraint

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin, utcnow


class ListingStatus(str, enum.Enum):
    ACTIVE = "active"
    REMOVED = "removed"


class Listing(UUIDPkMixin, TimestampMixin, Base):
    """A single listing on a single source. Base unit of the domain — see
    agent_documents/02_DOMAIN_MODEL.md §1. Never deleted merely because it disappeared from the
    source; ListingSnapshot rows carry its history.
    """

    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("source_id", "external_id", name="uq_listings_source_external_id"),)

    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("sources.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)

    make: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    generation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("generations.id"), nullable=True
    )

    production_year: Mapped[int] = mapped_column(Integer, nullable=False)
    mileage_km: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)

    fuel_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    transmission: Mapped[str | None] = mapped_column(String(32), nullable=True)
    body_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    engine_volume_cc: Mapped[int | None] = mapped_column(Integer, nullable=True)
    power_hp: Mapped[int | None] = mapped_column(Integer, nullable=True)

    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seller_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    seller_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[ListingStatus] = mapped_column(
        Enum(ListingStatus, native_enum=False, length=16), default=ListingStatus.ACTIVE, nullable=False
    )

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
