import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationType


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: NotificationType
    listing_id: uuid.UUID | None
    payload: dict | None
    read_at: datetime | None
    created_at: datetime
    # True when this is a NEW_MATCH notification whose payload.saved_search_id no longer exists —
    # lets the UI skip rendering a link that would just 404. Always False for other types.
    saved_search_deleted: bool = False


class NotificationListOut(BaseModel):
    notifications: list[NotificationOut]
    unread_count: int
