import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin

# Schema only — no auth/repository/routes yet. See docs/adr/02_DOMAIN_MODEL.md §9 and
# the plan's "explicitly out of scope" list.


class UserRole(str, enum.Enum):
    """Access-control role — deliberately separate from billing entitlements
    (subscription_plans/user_subscriptions, see app/models/subscription.py). An admin doesn't need
    a paid plan and a paid plan doesn't grant admin access; see docs/adr/20_ROLES_AND_ADMIN.md.
    """

    USER = "user"
    ADMIN = "admin"


class User(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=16), default=UserRole.USER, nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
