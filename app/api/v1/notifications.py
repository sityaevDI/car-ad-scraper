import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_csrf
from app.db.session import get_session
from app.models.user import User
from app.notifications.repository import NotificationRepository
from app.notifications.schemas import NotificationListOut, NotificationOut

router = APIRouter(prefix="/me/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListOut)
async def list_notifications(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> NotificationListOut:
    repository = NotificationRepository(session)
    notifications = await repository.list_for_user(current_user.id, limit=limit, offset=offset)
    unread_count = await repository.count_unread(current_user.id)
    return NotificationListOut(
        notifications=[NotificationOut.model_validate(n) for n in notifications],
        unread_count=unread_count,
    )


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_notification_read(
    notification_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> NotificationOut:
    repository = NotificationRepository(session)
    notification = await repository.get_owned(notification_id, current_user.id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")

    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        await session.commit()
    return NotificationOut.model_validate(notification)
