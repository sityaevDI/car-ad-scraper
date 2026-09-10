"""Runtime-editable scrape request pacing (docs/adr/05_ANTI_BOT_PROXY.md §8,
app/scraping/fetch_strategy.py's `_RequestPacer`). A singleton row — always `SINGLETON_ID` — so an
admin can retune pacing from the admin panel (app/api/v1/scrape.py's /scrape/rate-limit routes)
without a redeploy. app/config.py's scrape_request_* fields only seed this row the first time it's
read (see app/scraping/rate_limit.py); once it exists, the DB row is the source of truth.
"""

import uuid

from sqlalchemy import Float, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin

SINGLETON_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class ScrapeRateLimit(TimestampMixin, Base):
    __tablename__ = "scrape_rate_limits"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=lambda: SINGLETON_ID)
    request_delay_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    request_jitter_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    network_error_retry_delay_seconds: Mapped[float] = mapped_column(Float, nullable=False)
