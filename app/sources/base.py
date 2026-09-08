"""Source adapter interface. See docs/adr/04_SCRAPING.md §1.

A concrete adapter (e.g. `app.sources.polovniautomobili.adapter.PolovniAutomobiliSource`) must not
know about Postgres, users or billing — it only turns a SearchQuery into refs/listings.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.search.query import SearchQuery


@dataclass
class SourceListingRef:
    """A lightweight pointer to a listing found on a source's search/results page."""

    external_id: str
    url: str
    thumbnail_url: str | None = None


@dataclass
class SourceListing:
    """A fully parsed listing, normalized to canonical field names/units, ready for mapping onto
    the `Listing`/`ListingSnapshot` ORM models. `raw` keeps the adapter's full parsed payload for
    the snapshot history.
    """

    external_id: str
    canonical_url: str
    title: str
    make: str
    model: str
    production_year: int
    mileage_km: int
    price: int
    currency: str
    fuel_type: str | None = None
    transmission: str | None = None
    body_type: str | None = None
    engine_volume_cc: int | None = None
    power_hp: int | None = None
    location: str | None = None
    seller_type: str | None = None
    image_url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class CarSource(Protocol):
    source_code: str

    async def search(self, query: SearchQuery) -> AsyncIterator[SourceListingRef]: ...

    async def fetch_listing(self, ref: SourceListingRef) -> SourceListing: ...

    def build_search_url(self, query: SearchQuery, page: int = 1) -> str: ...
