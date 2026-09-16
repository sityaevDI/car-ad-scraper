from app.market.pricing import equipment_adjustment_pct, score_listing
from app.models.market import MarketConfidence, MarketPriceSnapshot


def _snapshot(estimated_price: int) -> MarketPriceSnapshot:
    return MarketPriceSnapshot(
        segment_key="k",
        source_id=None,
        make="skoda",
        model="octavia",
        production_year=2019,
        fuel_type="diesel",
        transmission="automatic",
        body_type="wagon",
        engine_volume_bucket=2000,
        mileage_bucket=40_000,
        algorithm_version="v1",
        sample_size=10,
        filtered_sample_size=10,
        estimated_price=estimated_price,
        price_low=estimated_price - 500,
        price_high=estimated_price + 500,
        currency="EUR",
        confidence=MarketConfidence.MEDIUM,
    )


def test_equipment_adjustment_sums_matched_weights():
    weights = {"adaptive_cruise_control": 1.5, "panoramic_roof": 1.5}
    total = equipment_adjustment_pct(["adaptive_cruise_control", "panoramic_roof"], weights, cap_pct=15.0)

    assert total == 3.0


def test_equipment_adjustment_ignores_unknown_slugs():
    weights = {"adaptive_cruise_control": 1.5}
    total = equipment_adjustment_pct(["some_new_checkbox_the_site_added"], weights, cap_pct=15.0)

    assert total == 0.0


def test_equipment_adjustment_empty_list_is_zero():
    assert equipment_adjustment_pct([], {"adaptive_cruise_control": 1.5}, cap_pct=15.0) == 0.0


def test_equipment_adjustment_is_capped():
    weights = {f"feature_{i}": 5.0 for i in range(10)}  # would sum to 50% uncapped
    total = equipment_adjustment_pct(list(weights.keys()), weights, cap_pct=15.0)

    assert total == 15.0


def test_score_listing_at_market_price_labels_market():
    snapshot = _snapshot(10_000)
    score = score_listing(
        10_000,
        [],
        snapshot,
        {},
        max_equipment_adjustment_pct=15.0,
        deviation_market_band_pct=5.0,
        deviation_significant_band_pct=15.0,
    )

    assert score.label == "market"
    assert score.deviation_pct == 0.0
    assert score.price_ratio == 1.0


def test_score_listing_significantly_below_market():
    snapshot = _snapshot(10_000)
    score = score_listing(
        7_000,
        [],
        snapshot,
        {},
        max_equipment_adjustment_pct=15.0,
        deviation_market_band_pct=5.0,
        deviation_significant_band_pct=15.0,
    )

    assert score.label == "significantly_below"


def test_score_listing_significantly_above_market():
    snapshot = _snapshot(10_000)
    score = score_listing(
        13_000,
        [],
        snapshot,
        {},
        max_equipment_adjustment_pct=15.0,
        deviation_market_band_pct=5.0,
        deviation_significant_band_pct=15.0,
    )

    assert score.label == "significantly_above"


def test_score_listing_equipment_adjustment_shifts_the_reference_price():
    """A well-equipped car priced above the raw segment median can still read as 'market' once its
    equipment-adjusted reference price accounts for that — the whole point of #18's equipment
    adjustment (see app/market/pricing.py's module docstring).
    """
    snapshot = _snapshot(10_000)
    weights = {"adaptive_cruise_control": 5.0}

    without_equipment = score_listing(
        10_500,
        [],
        snapshot,
        weights,
        max_equipment_adjustment_pct=15.0,
        deviation_market_band_pct=5.0,
        deviation_significant_band_pct=15.0,
    )
    with_equipment = score_listing(
        10_500,
        ["adaptive_cruise_control"],
        snapshot,
        weights,
        max_equipment_adjustment_pct=15.0,
        deviation_market_band_pct=5.0,
        deviation_significant_band_pct=15.0,
    )

    assert without_equipment.label == "above"
    assert with_equipment.label == "market"
    assert with_equipment.deviation_pct < without_equipment.deviation_pct
