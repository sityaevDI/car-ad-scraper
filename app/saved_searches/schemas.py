import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.search.query import SearchQuery


class SavedSearchCreate(BaseModel):
    name: str
    query: SearchQuery = Field(default_factory=SearchQuery)
    notification_settings: dict | None = None


class SavedSearchUpdate(BaseModel):
    name: str | None = None
    query: SearchQuery | None = None
    enabled: bool | None = None
    notification_settings: dict | None = None


class SavedSearchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    query: dict
    enabled: bool
    notification_settings: dict | None
    last_run_at: datetime | None
    created_at: datetime
