"""Normalized search query. See agent_documents/02_DOMAIN_MODEL.md §5.

Serializable with a stable hash so it can later back saved-search dedup/job-dedup
(agent_documents/09_QUEUE_PRIORITY.md §9) — not wired up yet, just designed to support it.
"""

import hashlib
import json

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    source_codes: list[str] | None = None
    make: str | None = None
    models: list[str] | None = None
    generation_id: str | None = None

    year_min: int | None = None
    year_max: int | None = None
    price_min: int | None = None
    price_max: int | None = None
    mileage_min: int | None = None
    mileage_max: int | None = None
    engine_volume_min: int | None = None
    engine_volume_max: int | None = None
    power_min: int | None = None
    power_max: int | None = None

    fuel_types: list[str] | None = None
    transmissions: list[str] | None = None
    body_types: list[str] | None = None
    location: str | None = None

    def stable_hash(self) -> str:
        canonical = json.dumps(self.model_dump(exclude_none=True), sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SearchRequest(BaseModel):
    query: SearchQuery = Field(default_factory=SearchQuery)
    group_by: list[str] | None = Field(
        default_factory=lambda: ["make", "model", "engine_volume_cc", "fuel_type", "transmission"]
    )
    sort: str = "count_desc"
    page: int = 1
    page_size: int = 20
