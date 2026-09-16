"""Price score (#18): a listing's price vs. its segment's market estimate, adjusted for the
listing's own equipment. See docs/adr/06_SEARCH_MARKET.md §6 and the plan behind #16/#18/#19
("Key design decisions" #5) for why equipment is a price adjustment applied here, at scoring time,
rather than a segmentation key in app/market/segment.py.
"""

from dataclasses import dataclass

from app.models.market import MarketPriceSnapshot

_LABEL_SIGNIFICANTLY_BELOW = "significantly_below"
_LABEL_BELOW = "below"
_LABEL_MARKET = "market"
_LABEL_ABOVE = "above"
_LABEL_SIGNIFICANTLY_ABOVE = "significantly_above"


@dataclass
class PriceScore:
    price_ratio: float
    deviation_pct: float
    label: str


def equipment_adjustment_pct(equipment: list[str], weights: dict[str, float], *, cap_pct: float) -> float:
    """Sum of matched per-feature deltas (app/models/market.py::MarketEquipmentWeight), clamped to
    ±cap_pct so one listing's option list can't push its reference price out of proportion.
    """
    total = sum(weights.get(slug, 0.0) for slug in equipment)
    return max(-cap_pct, min(cap_pct, total))


def _label(deviation_pct: float, *, market_band_pct: float, significant_band_pct: float) -> str:
    if deviation_pct <= -significant_band_pct:
        return _LABEL_SIGNIFICANTLY_BELOW
    if deviation_pct <= -market_band_pct:
        return _LABEL_BELOW
    if deviation_pct < market_band_pct:
        return _LABEL_MARKET
    if deviation_pct < significant_band_pct:
        return _LABEL_ABOVE
    return _LABEL_SIGNIFICANTLY_ABOVE


def score_listing(
    listing_price: int,
    equipment: list[str],
    snapshot: MarketPriceSnapshot,
    weights: dict[str, float],
    *,
    max_equipment_adjustment_pct: float,
    deviation_market_band_pct: float,
    deviation_significant_band_pct: float,
) -> PriceScore:
    """`snapshot.estimated_price` must not be None — callers only reach here once a segment has a
    usable estimate (see service.py, which returns None instead of calling this for INSUFFICIENT
    confidence).
    """
    assert snapshot.estimated_price is not None
    adjustment_pct = equipment_adjustment_pct(equipment, weights, cap_pct=max_equipment_adjustment_pct)
    reference_price = snapshot.estimated_price * (1 + adjustment_pct / 100)

    price_ratio = listing_price / reference_price
    deviation_pct = (listing_price - reference_price) / reference_price * 100
    label = _label(
        deviation_pct, market_band_pct=deviation_market_band_pct, significant_band_pct=deviation_significant_band_pct
    )

    return PriceScore(price_ratio=price_ratio, deviation_pct=deviation_pct, label=label)
