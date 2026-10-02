import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.search.query import SearchQuery
from app.search.service import ALLOWED_GROUP_FIELDS


class SavedSearchView(BaseModel):
    """The results layout stored with a saved search — mirrors the presentation half of
    SearchRequest. Kept apart from SearchQuery on purpose: it is not part of the query's
    stable_hash(), so two saved searches with the same filters but different grouping still dedup
    and match the same scrape job (see SavedSearch.view_settings).
    """

    group_by: list[str] = Field(max_length=len(ALLOWED_GROUP_FIELDS))
    min_group_count: int | None = Field(default=None, ge=0)
    sort: str = Field(max_length=32)

    @field_validator("group_by")
    @classmethod
    def _known_group_fields(cls, value: list[str]) -> list[str]:
        unknown = set(value) - ALLOWED_GROUP_FIELDS.keys()
        if unknown:
            raise ValueError(f"Invalid group_by fields: {sorted(unknown)}")
        return value


class SavedSearchCreate(BaseModel):
    name: str
    query: SearchQuery = Field(default_factory=SearchQuery)
    view_settings: SavedSearchView | None = None
    notification_settings: dict | None = None


class SavedSearchUpdate(BaseModel):
    name: str | None = None
    query: SearchQuery | None = None
    view_settings: SavedSearchView | None = None
    enabled: bool | None = None
    notification_settings: dict | None = None


class SavedSearchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    query: dict
    view_settings: dict | None
    enabled: bool
    notification_settings: dict | None
    last_run_at: datetime | None
    created_at: datetime
