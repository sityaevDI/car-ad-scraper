import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.scrape_job import ScrapeJobStatus, ScrapeJobType
from app.search.query import SearchQuery

_DEFAULT_MAX_PAGES = 5


class ScrapeJobCreate(BaseModel):
    source_code: str
    query: SearchQuery = Field(default_factory=SearchQuery)
    max_pages: int = 5


def encode_job_query(query: SearchQuery, max_pages: int) -> dict:
    """ScrapeJob.query is a single JSON blob, but a scrape run needs both the search filters and
    max_pages — nesting them here (rather than storing SearchQuery's fields flat) keeps the two
    concerns distinguishable when read back by the worker (see decode_job_query).
    """
    return {"search_query": query.model_dump(), "max_pages": max_pages}


def decode_job_query(data: dict | None) -> tuple[SearchQuery, int]:
    data = data or {}
    query = SearchQuery.model_validate(data.get("search_query") or {})
    max_pages = data.get("max_pages", _DEFAULT_MAX_PAGES)
    return query, max_pages


class ScrapeJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    job_type: ScrapeJobType
    status: ScrapeJobStatus
    query: dict | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    stats: dict | None
    error: dict | None


class ScheduledScrapeCreate(BaseModel):
    source_code: str
    job_type: ScrapeJobType = ScrapeJobType.SEARCH
    query: SearchQuery = Field(default_factory=SearchQuery)
    max_pages: int = 5
    interval_minutes: int = Field(ge=5)
    start_at: datetime | None = None


class ScheduledScrapeUpdate(BaseModel):
    interval_minutes: int | None = Field(default=None, ge=5)
    enabled: bool | None = None


class ScheduledScrapeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    job_type: ScrapeJobType
    query: dict | None
    interval_minutes: int
    enabled: bool
    next_run_at: datetime
    last_run_at: datetime | None
    last_job_id: uuid.UUID | None


class ScrapeRateLimitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_delay_seconds: float
    request_jitter_seconds: float
    network_error_retry_delay_seconds: float


class ScrapeRateLimitUpdate(BaseModel):
    request_delay_seconds: float | None = Field(default=None, ge=0)
    request_jitter_seconds: float | None = Field(default=None, ge=0)
    network_error_retry_delay_seconds: float | None = Field(default=None, ge=0)
