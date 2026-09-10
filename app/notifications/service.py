import uuid
from collections.abc import Awaitable, Callable
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType
from app.notifications.repository import NotificationRepository

_DEFAULT_COOLDOWN = timedelta(hours=24)

EmailEnqueuer = Callable[[str], Awaitable[None]]


class NotificationService:
    """Single entry point for creating a Notification — both the scrape pipeline's post-run
    matching (issue #26/#21) and any future manual trigger should go through this, not
    `session.add(Notification(...))` directly, so the cooldown/email-enqueue rules always apply.
    """

    def __init__(self, session: AsyncSession, enqueue_email: EmailEnqueuer | None = None):
        self.session = session
        self.repository = NotificationRepository(session)
        self.enqueue_email = enqueue_email

    async def notify(
        self,
        user_id: uuid.UUID,
        type: NotificationType,
        payload: dict,
        listing_id: uuid.UUID | None = None,
        cooldown: timedelta = _DEFAULT_COOLDOWN,
    ) -> Notification | None:
        """Returns None (and creates nothing) if an equivalent notification already fired within
        `cooldown` — only checked for listing-scoped events, since that's the only case with a
        natural dedup key (user, type, listing).
        """
        if listing_id is not None:
            duplicate = await self.repository.recent_duplicate_exists(user_id, type, listing_id, cooldown)
            if duplicate:
                return None

        notification = Notification(user_id=user_id, type=type, listing_id=listing_id, payload=payload)
        self.session.add(notification)
        await self.session.flush()

        if self.enqueue_email is not None:
            await self.enqueue_email(str(notification.id))

        return notification
