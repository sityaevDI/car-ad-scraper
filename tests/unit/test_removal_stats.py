from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.db.session import get_session
from app.main import app
from app.market.removal_schemas import RemovalStatsResponse
from app.market.removal_service import RemovalStatsService
from app.market.removal_stats import DAILY_SERIES_DAYS, MIN_MODEL_REMOVED, refresh_removal_stats
from app.models.listing import ListingStatus
from app.models.removal_stats import ALL_SCOPE, RemovalStats
from app.models.snapshot import ListingSnapshot
from tests.conftest import make_listing, seed_source

NOW = datetime(2026, 9, 25, 4, 0, tzinfo=timezone.utc)
YESTERDAY = date(2026, 9, 24)


def _removed(source_id, *, seen_days_ago: float, on_market_days: float, **overrides):
    """A REMOVED listing whose last crawl sighting was `seen_days_ago` before NOW at noon-ish."""
    last_seen = NOW - timedelta(days=seen_days_ago)
    return make_listing(
        source_id,
        status=ListingStatus.REMOVED,
        last_seen_at=last_seen,
        first_seen_at=last_seen - timedelta(days=on_market_days),
        **overrides,
    )


async def _stats_row(session, stat_date, period, make=ALL_SCOPE, model=ALL_SCOPE) -> RemovalStats | None:
    return await session.scalar(
        select(RemovalStats).where(
            RemovalStats.stat_date == stat_date,
            RemovalStats.period_days == period,
            RemovalStats.make == make,
            RemovalStats.model == model,
        )
    )


async def test_counts_removed_listings_per_window_and_scope(session):
    source = await seed_source(session)
    # Seen yesterday (Sep 24) -> inside the day, week and month windows.
    session.add(_removed(source.id, seen_days_ago=0.5, on_market_days=10, price=10_000))
    session.add(_removed(source.id, seen_days_ago=0.5, on_market_days=20, price=14_000, make="BMW", model="320d"))
    # Seen Sep 20 -> week and month only.
    session.add(_removed(source.id, seen_days_ago=4.5, on_market_days=30, price=12_000))
    # Seen Sep 1 -> month only.
    session.add(_removed(source.id, seen_days_ago=23.5, on_market_days=5, price=8_000))
    # Still active, and removed today (Sep 25, an incomplete day): neither counts.
    session.add(make_listing(source.id, last_seen_at=NOW - timedelta(days=0.5)))
    session.add(_removed(source.id, seen_days_ago=0.1, on_market_days=5))
    await session.commit()

    await refresh_removal_stats(session, now=NOW)

    assert (await _stats_row(session, YESTERDAY, 1)).removed_count == 2
    assert (await _stats_row(session, YESTERDAY, 7)).removed_count == 3
    month = await _stats_row(session, YESTERDAY, 30)
    assert month.removed_count == 4
    assert month.median_days_on_market == 15.0
    assert month.median_price_at_removal == 11_000

    assert (await _stats_row(session, YESTERDAY, 7, make="Škoda")).removed_count == 2
    assert (await _stats_row(session, YESTERDAY, 7, make="BMW")).removed_count == 1
    # One removal is below MIN_MODEL_REMOVED, so no per-model row.
    assert await _stats_row(session, YESTERDAY, 7, make="BMW", model="320d") is None


async def test_previous_window_is_computed_for_comparison(session):
    source = await seed_source(session)
    session.add(_removed(source.id, seen_days_ago=0.5, on_market_days=1))
    # Sep 11-17 is the week before the Sep 18-24 window (as_of Sep 17).
    session.add(_removed(source.id, seen_days_ago=9.5, on_market_days=1))
    session.add(_removed(source.id, seen_days_ago=10.5, on_market_days=1))
    await session.commit()

    await refresh_removal_stats(session, now=NOW)

    assert (await _stats_row(session, YESTERDAY, 7)).removed_count == 1
    assert (await _stats_row(session, YESTERDAY - timedelta(days=7), 7)).removed_count == 2


async def test_price_cut_metrics_come_from_first_snapshot(session):
    source = await seed_source(session)
    cut = _removed(source.id, seen_days_ago=0.5, on_market_days=10, price=9_000)
    also_cut = _removed(source.id, seen_days_ago=0.5, on_market_days=10, price=13_500)
    untouched = _removed(source.id, seen_days_ago=0.5, on_market_days=10, price=8_000)
    session.add_all([cut, also_cut, untouched])
    await session.flush()
    for listing, first_price in ((cut, 10_000), (also_cut, 15_000), (untouched, 8_000)):
        session.add(
            ListingSnapshot(
                listing_id=listing.id,
                captured_at=NOW - timedelta(days=20),
                price=first_price,
                mileage_km=listing.mileage_km,
                title=listing.title,
            )
        )
        # A later snapshot must not be mistaken for the starting price.
        session.add(
            ListingSnapshot(
                listing_id=listing.id,
                captured_at=NOW - timedelta(days=1),
                price=listing.price,
                mileage_km=listing.mileage_km,
                title=listing.title,
            )
        )
    await session.commit()

    await refresh_removal_stats(session, now=NOW)

    row = await _stats_row(session, YESTERDAY, 1)
    assert row.price_cut_share == pytest.approx(0.6667, abs=1e-4)
    assert row.median_price_cut_pct == 10.0  # cuts were 10% and 10%


async def test_model_row_written_at_min_sample(session):
    source = await seed_source(session)
    for _ in range(MIN_MODEL_REMOVED):
        session.add(_removed(source.id, seen_days_ago=0.5, on_market_days=3))
    await session.commit()

    await refresh_removal_stats(session, now=NOW)

    row = await _stats_row(session, YESTERDAY, 1, make="Škoda", model="Octavia")
    assert row is not None and row.removed_count == MIN_MODEL_REMOVED


async def test_refresh_is_idempotent_and_writes_empty_windows(session):
    await refresh_removal_stats(session, now=NOW)
    first_count = await session.scalar(select(func.count()).select_from(RemovalStats))
    await refresh_removal_stats(session, now=NOW)
    second_count = await session.scalar(select(func.count()).select_from(RemovalStats))

    assert first_count == second_count == DAILY_SERIES_DAYS + 4
    empty = await _stats_row(session, YESTERDAY, 7)
    assert empty.removed_count == 0 and empty.median_price_at_removal is None


async def test_service_returns_series_breakdown_and_previous(session):
    source = await seed_source(session)
    for _ in range(3):
        session.add(_removed(source.id, seen_days_ago=0.5, on_market_days=8, price=10_000))
    session.add(_removed(source.id, seen_days_ago=2.5, on_market_days=8, make="BMW", model="320d"))
    session.add(_removed(source.id, seen_days_ago=9.5, on_market_days=8))
    await session.commit()
    await refresh_removal_stats(session, now=NOW)

    result = await RemovalStatsService(session).get("week", None)

    assert result.as_of == YESTERDAY
    assert result.current.removed_count == 4
    assert result.previous.removed_count == 1
    assert [row.make for row in result.breakdown] == ["Škoda", "BMW"]
    assert len(result.series) == DAILY_SERIES_DAYS
    assert result.series[-1].date == YESTERDAY and result.series[-1].removed_count == 3
    assert sum(point.removed_count for point in result.series) == 5

    by_make = await RemovalStatsService(session).get("week", "Škoda")
    assert by_make.current.removed_count == 3
    assert [(row.make, row.model) for row in by_make.breakdown] == [("Škoda", "Octavia")]
    assert sum(point.removed_count for point in by_make.series) == 4


async def test_service_returns_empty_response_before_first_refresh(session):
    result = await RemovalStatsService(session).get("month", None)

    assert result == RemovalStatsResponse(period="month")


@pytest_asyncio.fixture
async def client(session):
    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
        yield async_client
    app.dependency_overrides.clear()


async def test_endpoint_is_public_and_validates_period(client, session):
    source = await seed_source(session)
    session.add(_removed(source.id, seen_days_ago=0.5, on_market_days=8))
    await session.commit()
    await refresh_removal_stats(session, now=NOW)

    ok = await client.get("/api/v1/market/removed-stats", params={"period": "day"})
    assert ok.status_code == 200
    assert ok.json()["current"]["removed_count"] == 1
    assert "max-age" in ok.headers["cache-control"]

    assert (await client.get("/api/v1/market/removed-stats", params={"period": "year"})).status_code == 422


async def test_cron_is_registered_in_worker():
    from app.scraping.worker import WorkerSettings

    names = {job.name for job in WorkerSettings.cron_jobs}
    assert "cron:run_refresh_removal_stats" in names
