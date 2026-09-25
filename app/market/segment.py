"""Comparable-group ("segment") identity for market price calculation — docs/adr/06_SEARCH_MARKET.md
§5. Deliberately excludes `generation_id` (nothing populates it yet) and `equipment` (applied as a
price adjustment instead — see pricing.py — not as a segmentation key, which would fragment every
segment down to sample_size≈1 given equipment's ~90 possible tags).
"""

import dataclasses
import hashlib
import json
import uuid

from app.models.listing import Listing

# Engine displacement rounds to the nearest 100cc — real listings report exact cc (1968/1998/2000
# are all "2.0"), which would otherwise fragment one segment into several near-duplicates. Shared
# with app/search/service.py's grouped-search bucketing (same constant, imported from here) so the
# two never drift apart.
ENGINE_VOLUME_BUCKET_SIZE = 100


def bucket_engine_volume_cc(engine_volume_cc: int | None) -> int | None:
    if engine_volume_cc is None:
        return None
    half = ENGINE_VOLUME_BUCKET_SIZE // 2
    return ((engine_volume_cc + half) // ENGINE_VOLUME_BUCKET_SIZE) * ENGINE_VOLUME_BUCKET_SIZE


def bucket_mileage_km(mileage_km: int, bucket_size_km: int) -> int:
    """Floor to the bucket, not round-to-nearest like engine volume — mileage matters most at the
    low end (a 5k vs 25k km car reads very differently to a buyer), so round-to-nearest would blur
    exactly the boundary that matters. Floor also keeps a listing's bucket stable as it moves only
    upward across re-crawls, instead of oscillating back and forth near a rounding midpoint.
    """
    return (mileage_km // bucket_size_km) * bucket_size_km


@dataclasses.dataclass(frozen=True)
class SegmentCriteria:
    """Mirrors app/models/market.py::SegmentCriteriaMixin field-for-field — this is what gets
    stored alongside `segment_key` on MarketDirtySegment/MarketPriceSnapshot rows, since the hash
    itself can't be reversed back into "which listings does this match".
    """

    source_id: uuid.UUID
    make: str
    model: str
    production_year: int
    fuel_type: str | None
    transmission: str | None
    body_type: str | None
    engine_volume_bucket: int | None
    mileage_bucket: int

    def key(self) -> str:
        payload = dataclasses.asdict(self)
        canonical = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def as_columns(self) -> dict:
        """Field values ready to spread into a SegmentCriteriaMixin-based model constructor."""
        return dataclasses.asdict(self)


def segment_criteria_for_listing(listing: Listing, *, mileage_bucket_km: int) -> SegmentCriteria:
    return SegmentCriteria(
        source_id=listing.source_id,
        make=listing.make.lower(),
        model=listing.model.lower(),
        production_year=listing.production_year,
        fuel_type=listing.fuel_type,
        transmission=listing.transmission,
        body_type=listing.body_type,
        engine_volume_bucket=bucket_engine_volume_cc(listing.engine_volume_cc),
        mileage_bucket=bucket_mileage_km(listing.mileage_km, mileage_bucket_km),
    )


def compute_segment_key(listing: Listing, *, mileage_bucket_km: int) -> str:
    """Convenience for read paths that only need the id (to look up the latest snapshot), not the
    full criteria — see app/market/service.py's get_price_score(s).
    """
    return segment_criteria_for_listing(listing, mileage_bucket_km=mileage_bucket_km).key()


def segment_criteria_from_row(row) -> SegmentCriteria:
    """Rebuilds a SegmentCriteria from any app/models/market.py::SegmentCriteriaMixin row
    (MarketDirtySegment, MarketPriceSnapshot) — the inverse of `SegmentCriteria.as_columns()`.
    """
    return SegmentCriteria(
        source_id=row.source_id,
        make=row.make,
        model=row.model,
        production_year=row.production_year,
        fuel_type=row.fuel_type,
        transmission=row.transmission,
        body_type=row.body_type,
        engine_volume_bucket=row.engine_volume_bucket,
        mileage_bucket=row.mileage_bucket,
    )
