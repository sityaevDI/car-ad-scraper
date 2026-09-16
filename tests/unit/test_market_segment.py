import uuid
from datetime import datetime, timezone

from app.market.segment import (
    SegmentCriteria,
    bucket_engine_volume_cc,
    bucket_mileage_km,
    compute_segment_key,
    segment_criteria_for_listing,
    segment_criteria_from_row,
)
from app.models.listing import Listing, ListingStatus


def _listing(**overrides) -> Listing:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        external_id="1",
        canonical_url="https://example.com/1",
        title="Test listing",
        make="Škoda",
        model="Octavia",
        production_year=2019,
        mileage_km=45_000,
        price=13_000,
        currency="EUR",
        fuel_type="diesel",
        transmission="automatic",
        body_type="wagon",
        engine_volume_cc=1968,
        power_hp=150,
        status=ListingStatus.ACTIVE,
        first_seen_at=now,
        last_seen_at=now,
        last_checked_at=now,
    )
    defaults.update(overrides)
    return Listing(**defaults)


def test_engine_volume_buckets_to_nearest_100cc():
    assert bucket_engine_volume_cc(1968) == 2000
    assert bucket_engine_volume_cc(1898) == 1900
    assert bucket_engine_volume_cc(2049) == 2000
    assert bucket_engine_volume_cc(2050) == 2100
    assert bucket_engine_volume_cc(None) is None


def test_mileage_buckets_by_flooring():
    assert bucket_mileage_km(0, 20_000) == 0
    assert bucket_mileage_km(19_999, 20_000) == 0
    assert bucket_mileage_km(20_000, 20_000) == 20_000
    assert bucket_mileage_km(39_999, 20_000) == 20_000


def test_segment_key_is_deterministic():
    source_id = uuid.uuid4()
    listing_a = _listing(source_id=source_id)
    listing_b = _listing(source_id=source_id, id=uuid.uuid4(), external_id="2")  # different identity, same segment

    key_a = compute_segment_key(listing_a, mileage_bucket_km=20_000)
    key_b = compute_segment_key(listing_b, mileage_bucket_km=20_000)

    assert key_a == key_b


def test_segment_key_is_case_insensitive_on_make_model():
    source_id = uuid.uuid4()
    listing_lower = _listing(source_id=source_id, make="skoda", model="octavia")
    listing_upper = _listing(source_id=source_id, make="SKODA", model="OCTAVIA")

    assert compute_segment_key(listing_lower, mileage_bucket_km=20_000) == compute_segment_key(
        listing_upper, mileage_bucket_km=20_000
    )


def test_segment_key_differs_on_production_year():
    source_id = uuid.uuid4()
    listing_2019 = _listing(source_id=source_id, production_year=2019)
    listing_2020 = _listing(source_id=source_id, production_year=2020)

    assert compute_segment_key(listing_2019, mileage_bucket_km=20_000) != compute_segment_key(
        listing_2020, mileage_bucket_km=20_000
    )


def test_criteria_roundtrips_through_as_columns_and_from_row():
    listing = _listing()
    criteria = segment_criteria_for_listing(listing, mileage_bucket_km=20_000)

    class _Row:
        pass

    row = _Row()
    for field, value in criteria.as_columns().items():
        setattr(row, field, value)

    rebuilt = segment_criteria_from_row(row)

    assert rebuilt == criteria
    assert rebuilt.key() == criteria.key()


def test_criteria_key_matches_dataclass_constructed_directly():
    listing = _listing()
    criteria = segment_criteria_for_listing(listing, mileage_bucket_km=20_000)

    same = SegmentCriteria(
        source_id=listing.source_id,
        make="škoda",
        model="octavia",
        production_year=2019,
        fuel_type="diesel",
        transmission="automatic",
        body_type="wagon",
        engine_volume_bucket=2000,
        mileage_bucket=40_000,
    )

    assert criteria.key() == same.key()
