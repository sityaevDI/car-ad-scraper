"""Registry of listing fields only reliably available on a source's detail page, not its
search-results page (see app/sources/polovniautomobili/mapper.py's docstring on the two JSON
shapes). Single source of truth for two callers that both need "every such field, from one
detail-page fetch":

- app/scraping/pipeline.py's `_enrich_with_detail`, backfilling all of them the one time a
  brand-new listing already gets a detail-page fetch.
- app/scraping/backfill.py, backfilling listings created before a given field existed — one
  detail-page fetch per listing covers every field still missing on that row, instead of a
  separate full pass (and re-fetch of the same listing) per field.

`fuel_type` is deliberately not here despite also being detail-page-derived in the general sense:
unlike these, it's reliably present on search-result entries too (see mapper.py's
map_search_result), so a stale value just needs re-normalizing in place, not a network re-fetch —
see app/scraping/backfill_fuel_type.py, a separate one-off script for that different mechanism.

Adding a new detail-only field (e.g. door_count) means: its column on Listing, its `normalize_*`
in mapper.py wired into map_product_data, a repository.set_*(), and one entry here — nowhere else.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement

from app.listings.repository import ListingRepository
from app.models.listing import Listing
from app.sources.base import SourceListing


@dataclass(frozen=True)
class DetailOnlyField:
    name: str
    # SQL predicate selecting listings missing this field — used to build backfill.py's WHERE
    # OR(...) clause up front, before any detail-page fetch.
    missing: ColumnElement[bool]
    # Re-checked in Python against the specific row right before writing — a listing selected
    # because *another* requested field was missing on it may already have this one set, and must
    # not be overwritten (mirrors the old per-field scripts' "already had a value — untouched").
    is_missing: Callable[[Listing], bool]
    get: Callable[[SourceListing], Any]
    set: Callable[[ListingRepository, Listing, Any], None]


DETAIL_ONLY_FIELDS: dict[str, DetailOnlyField] = {
    "equipment": DetailOnlyField(
        name="equipment",
        missing=Listing.equipment == [],
        is_missing=lambda listing: not listing.equipment,
        get=lambda detail: detail.equipment,
        set=lambda repo, listing, value: repo.set_equipment(listing, value),
    ),
    "interior_material": DetailOnlyField(
        name="interior_material",
        missing=Listing.interior_material.is_(None),
        is_missing=lambda listing: listing.interior_material is None,
        get=lambda detail: detail.interior_material,
        set=lambda repo, listing, value: repo.set_interior_material(listing, value),
    ),
    "air_condition": DetailOnlyField(
        name="air_condition",
        missing=Listing.air_condition.is_(None),
        is_missing=lambda listing: listing.air_condition is None,
        get=lambda detail: detail.air_condition,
        set=lambda repo, listing, value: repo.set_air_condition(listing, value),
    ),
    "drive_type": DetailOnlyField(
        name="drive_type",
        missing=Listing.drive_type.is_(None),
        is_missing=lambda listing: listing.drive_type is None,
        get=lambda detail: detail.drive_type,
        set=lambda repo, listing, value: repo.set_drive_type(listing, value),
    ),
}
