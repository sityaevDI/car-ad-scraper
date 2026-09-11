import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_csrf
from app.db.session import get_session
from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.notifications.repository import NotificationRepository
from app.notifications.schemas import NotificationListOut, NotificationOut
from app.saved_searches.repository import SavedSearchRepository

router = APIRouter(prefix="/me/notifications", tags=["notifications"])


def _referenced_saved_search_id(notification: Notification) -> uuid.UUID | None:
    if notification.type != NotificationType.NEW_MATCH or not notification.payload:
        return None
    raw_id = notification.payload.get("saved_search_id")
    if not isinstance(raw_id, str):
        return None
    try:
        return uuid.UUID(raw_id)
    except ValueError:
        return None


async def _to_out_list(notifications: list[Notification], session: AsyncSession) -> list[NotificationOut]:
    """Batch-resolves which NEW_MATCH notifications point at a since-deleted saved search, so the
    UI can render those without a (dead) link. One query for the whole page rather than one per row.
    """
    referenced_ids = {sid for n in notifications if (sid := _referenced_saved_search_id(n)) is not None}
    existing_ids = await SavedSearchRepository(session).existing_ids(referenced_ids)

    out = []
    for notification in notifications:
        item = NotificationOut.model_validate(notification)
        referenced_id = _referenced_saved_search_id(notification)
        item.saved_search_deleted = referenced_id is not None and referenced_id not in existing_ids
        out.append(item)
    return out


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
        notifications=await _to_out_list(notifications, session),
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
    (out,) = await _to_out_list([notification], session)
    return out
