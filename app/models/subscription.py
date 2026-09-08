import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin

# Schema only — no billing/entitlement enforcement yet. Plans are deliberately kept separate from
# the user (agent_documents/02_DOMAIN_MODEL.md §10); monetization is a later phase per the
# marketer's advice reflected in agent_documents/16_MVP_ROADMAP.md Phase 5.


class SubscriptionPlan(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "subscription_plans"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)  # FREE / SUPPORTER / PRO / ADMIN
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    max_saved_searches: Mapped[int] = mapped_column(Integer, nullable=False)
    refresh_frequency_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    priority_weight: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    priority_credits_per_month: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    history_days: Mapped[int] = mapped_column(Integer, nullable=False)


class UserSubscription(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "user_subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("subscription_plans.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
