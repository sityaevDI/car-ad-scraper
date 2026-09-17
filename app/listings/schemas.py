import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.market.schemas import PriceScoreOut
from app.models.listing import ListingStatus


class ListingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    external_id: str
    canonical_url: str
    title: str
    make: str
    model: str
    production_year: int
    mileage_km: int
    price: int
    currency: str
    fuel_type: str | None
    transmission: str | None
    body_type: str | None
    interior_material: str | None
    air_condition: str | None
    engine_volume_cc: int | None
    power_hp: int | None
    seats: str | None
    location: str | None
    image_url: str | None
    status: ListingStatus
    first_seen_at: datetime
    last_seen_at: datetime
    last_checked_at: datetime
    # Set by the route for a logged-in caller (app/listings/repository.py::FollowRepository),
    # never derived from the Listing row itself.
    is_following: bool = False
    # Set by the route via app/market/service.py::MarketPriceService — never derived from the
    # Listing row itself. None when no market snapshot exists yet for this listing's segment.
    price_score: PriceScoreOut | None = None


class ListingSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    captured_at: datetime
    price: int
    mileage_km: int
    title: str


class ListingHistoryOut(BaseModel):
    listing: ListingOut
    snapshots: list[ListingSnapshotOut]
