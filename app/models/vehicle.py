from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class Generation(UUIDPkMixin, TimestampMixin, Base):
    """Canonical vehicle generation. Deliberately thin for MVP — normalization is manual/nullable
    (see docs/adr/18_DECISIONS_AND_OPEN_QUESTIONS.md), listings link to it via a nullable FK.
    """

    __tablename__ = "generations"

    make: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    year_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
