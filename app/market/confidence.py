"""Confidence tier for a market price estimate — docs/adr/06_SEARCH_MARKET.md §7. That spec names
factors (sample size, age, dispersion, similarity, source coverage) without a formula. This is a
deliberately simple v1 heuristic — sample size + dispersion only. Age/similarity/source coverage
aren't meaningful yet: recompute is dirty-triggered (app/scraping/pipeline.py marks a segment dirty
the moment a listing in it changes), so a stored snapshot is fresh by construction rather than
aging between scheduled runs, and there's one source and no generation-level similarity data yet.
Tagged as ALGORITHM_VERSION on every snapshot so this can be revised later without corrupting how
older snapshots are interpreted.
"""

from app.market.stats import RawEstimate
from app.models.market import MarketConfidence

ALGORITHM_VERSION = "v1"

_DOWNGRADE = {
    MarketConfidence.HIGH: MarketConfidence.MEDIUM,
    MarketConfidence.MEDIUM: MarketConfidence.LOW,
    MarketConfidence.LOW: MarketConfidence.LOW,  # floor — dispersion alone won't drop below LOW
}


def score_confidence(
    estimate: RawEstimate,
    *,
    confidence_medium_min_sample: int,
    confidence_high_min_sample: int,
    high_dispersion_ratio: float,
) -> MarketConfidence:
    if estimate.estimated_price is None:
        return MarketConfidence.INSUFFICIENT
    # robust_estimate (app/market/stats.py) always sets price_low/price_high together with
    # estimated_price — these can't be None here, just not expressed in RawEstimate's per-field
    # Optional typing.
    assert estimate.price_low is not None
    assert estimate.price_high is not None

    if estimate.filtered_sample_size >= confidence_high_min_sample:
        tier = MarketConfidence.HIGH
    elif estimate.filtered_sample_size >= confidence_medium_min_sample:
        tier = MarketConfidence.MEDIUM
    else:
        tier = MarketConfidence.LOW

    dispersion = (estimate.price_high - estimate.price_low) / estimate.estimated_price
    if dispersion > high_dispersion_ratio:
        tier = _DOWNGRADE[tier]

    return tier
