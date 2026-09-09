import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.scrape_job import ScrapeJobStatus, ScrapeJobType
from app.search.query import SearchQuery


class ScrapeJobCreate(BaseModel):
    source_code: str
    query: SearchQuery = Field(default_factory=SearchQuery)
    max_pages: int = 5


_DEFAULT_MAX_PAGES = 5


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
    started_at: datetime | None
    finished_at: datetime | None
    stats: dict | None
    error: dict | None
