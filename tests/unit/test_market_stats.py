from app.market.stats import robust_estimate


def test_empty_prices_returns_insufficient():
    estimate = robust_estimate([], iqr_multiplier=1.5, min_sample_size=5)

    assert estimate.sample_size == 0
    assert estimate.filtered_sample_size == 0
    assert estimate.estimated_price is None
    assert estimate.price_low is None
    assert estimate.price_high is None


def test_below_min_sample_size_returns_insufficient():
    estimate = robust_estimate([10_000, 11_000, 12_000], iqr_multiplier=1.5, min_sample_size=5)

    assert estimate.sample_size == 3
    assert estimate.estimated_price is None


def test_all_identical_prices():
    estimate = robust_estimate([10_000] * 6, iqr_multiplier=1.5, min_sample_size=5)

    assert estimate.filtered_sample_size == 6
    assert estimate.estimated_price == 10_000
    assert estimate.price_low == 10_000
    assert estimate.price_high == 10_000


def test_single_outlier_is_excluded_from_the_median():
    prices = [10_000, 10_200, 10_400, 10_600, 10_800, 50_000]

    estimate = robust_estimate(prices, iqr_multiplier=1.5, min_sample_size=5)

    assert estimate.sample_size == 6
    assert estimate.filtered_sample_size == 5
    assert estimate.estimated_price == 10_400
    assert estimate.price_high < 50_000


def test_at_min_sample_size_boundary_is_included():
    estimate = robust_estimate([10_000, 11_000, 12_000, 13_000, 14_000], iqr_multiplier=1.5, min_sample_size=5)

    assert estimate.estimated_price is not None
