from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class Source(UUIDPkMixin, TimestampMixin, Base):
    """A listings source/marketplace, e.g. Polovni Automobili."""

    __tablename__ = "sources"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
