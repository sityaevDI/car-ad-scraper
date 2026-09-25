"""Robust price statistics for one comparable-listing segment — docs/adr/06_SEARCH_MARKET.md §5/§8.
Pure functions, no I/O — the caller (service.py) supplies the raw price list.
"""

from dataclasses import dataclass


@dataclass
class RawEstimate:
    sample_size: int
    filtered_sample_size: int
    estimated_price: int | None
    price_low: int | None
    price_high: int | None


def _quantile(sorted_values: list[int], q: float) -> float:
    """Linear-interpolation quantile (same method as numpy's default `linear` interpolation) — no
    numpy dependency for what's a handful of values per segment. `sorted_values` must be sorted
    and non-empty.
    """
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    pos = q * (len(sorted_values) - 1)
    lower = int(pos)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = pos - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction


def robust_estimate(prices: list[int], *, iqr_multiplier: float, min_sample_size: int) -> RawEstimate:
    """IQR-filtered median + interquartile price range. Below `min_sample_size` raw listings,
    returns an estimate with null price fields — confidence.py turns that into INSUFFICIENT rather
    than showing a number nobody should trust.
    """
    sample_size = len(prices)
    if sample_size == 0 or sample_size < min_sample_size:
        return RawEstimate(sample_size, filtered_sample_size=0, estimated_price=None, price_low=None, price_high=None)

    ordered = sorted(prices)
    q1 = _quantile(ordered, 0.25)
    q3 = _quantile(ordered, 0.75)
    iqr = q3 - q1
    low_fence = q1 - iqr_multiplier * iqr
    high_fence = q3 + iqr_multiplier * iqr
    # A degenerate fence (e.g. every price identical, iqr=0) would exclude everything outside that
    # single value — fall back to the unfiltered set rather than reporting zero comparables.
    filtered = [p for p in ordered if low_fence <= p <= high_fence] or ordered

    median = _quantile(filtered, 0.5)
    price_low = _quantile(filtered, 0.25)
    price_high = _quantile(filtered, 0.75)

    return RawEstimate(
        sample_size=sample_size,
        filtered_sample_size=len(filtered),
        estimated_price=round(median),
        price_low=round(price_low),
        price_high=round(price_high),
    )
