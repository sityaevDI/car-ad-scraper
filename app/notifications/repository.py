import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType


class NotificationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_user(self, user_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[Notification]:
        result = await self.session.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_unread(self, user_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
        return result.scalar_one()

    async def get_owned(self, notification_id: uuid.UUID, user_id: uuid.UUID) -> Notification | None:
        result = await self.session.execute(
            select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def recent_duplicate_exists(
        self, user_id: uuid.UUID, type: NotificationType, listing_id: uuid.UUID, cooldown: timedelta
    ) -> bool:
        """Backs the "same event, cooldown" rule in issue #22 — a listing that keeps re-triggering
        the same event type (e.g. a job re-checking the same saved search) shouldn't re-notify the
        user every run.
        """
        since = datetime.now(timezone.utc) - cooldown
        result = await self.session.execute(
            select(Notification.id)
            .where(
                Notification.user_id == user_id,
                Notification.type == type,
                Notification.listing_id == listing_id,
                Notification.created_at >= since,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
