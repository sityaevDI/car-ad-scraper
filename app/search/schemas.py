from typing import Any

from pydantic import BaseModel

from app.listings.schemas import ListingOut


class ListingGroupOut(BaseModel):
    group: dict[str, Any]
    label: str
    count: int
    currency: str
    price_min: int
    price_avg: int
    price_max: int
    year_min: int
    year_max: int
    mileage_min: int
    mileage_max: int


class SearchResponse(BaseModel):
    groups: list[ListingGroupOut] | None = None
    listings: list[ListingOut] | None = None
    total_listings: int
    total_groups: int | None = None
    page: int
    page_size: int
