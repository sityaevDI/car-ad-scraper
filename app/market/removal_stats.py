"""Builds the `removal_stats` rollup from Listing/ListingSnapshot. Runs from an arq cron in the
scrape worker (app/scraping/worker.py) twice a day; the API only reads the result — see
docs/adr/21_REMOVAL_STATS.md.

Everything is aggregated in Python from one query rather than with SQL percentile functions: the
medians are dialect-independent (unit tests run on sqlite) and the working set — listings removed
in the last ~60 days — is small.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from statistics import median
from typing import Any

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing, ListingStatus
from app.models.removal_stats import ALL_SCOPE, RemovalStats
from app.models.snapshot import ListingSnapshot

DAILY_SERIES_DAYS = 30
# Week/month windows are also computed for the window right before them, for the "vs previous
# period" delta on the page.
WINDOW_PERIODS = (7, 30)
# A model with 1-2 removals in a window says nothing about that model, so it doesn't get a row.
MIN_MODEL_REMOVED = 3


@dataclass(frozen=True)
class _Removed:
    make: str
    model: str
    days_on_market: float
    price: int
    first_price: int | None


def _as_utc(value: datetime) -> datetime:
    # sqlite (unit tests) hands timezone-aware columns back naive.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _targets(last_day: date) -> list[tuple[date, int]]:
    targets = [(last_day - timedelta(days=i), 1) for i in range(DAILY_SERIES_DAYS)]
    for period in WINDOW_PERIODS:
        targets.append((last_day, period))
        targets.append((last_day - timedelta(days=period), period))
    return targets


def _metrics(items: list[_Removed]) -> dict[str, Any]:
    if not items:
        return {
            "removed_count": 0,
            "median_days_on_market": None,
            "median_price_at_removal": None,
            "price_cut_share": None,
            "median_price_cut_pct": None,
        }
    cuts = [
        (item.first_price - item.price) / item.first_price * 100
        for item in items
        if item.first_price and item.first_price > item.price
    ]
    return {
        "removed_count": len(items),
        "median_days_on_market": round(median(item.days_on_market for item in items), 1),
        "median_price_at_removal": int(median(item.price for item in items)),
        "price_cut_share": round(len(cuts) / len(items), 4),
        "median_price_cut_pct": round(median(cuts), 1) if cuts else None,
    }


def _rows_for_window(as_of: date, period: int, items: list[_Removed], computed_at: datetime) -> list[RemovalStats]:
    def row(make: str, model: str, scoped: list[_Removed]) -> RemovalStats:
        return RemovalStats(
            stat_date=as_of, period_days=period, make=make, model=model, computed_at=computed_at, **_metrics(scoped)
        )

    by_make: dict[str, list[_Removed]] = defaultdict(list)
    by_model: dict[tuple[str, str], list[_Removed]] = defaultdict(list)
    for item in items:
        by_make[item.make].append(item)
        by_model[(item.make, item.model)].append(item)

    rows = [row(ALL_SCOPE, ALL_SCOPE, items)]
    rows += [row(make, ALL_SCOPE, scoped) for make, scoped in by_make.items()]
    rows += [
        row(make, model, scoped)
        for (make, model), scoped in by_model.items()
        if len(scoped) >= MIN_MODEL_REMOVED
    ]
    return rows


async def _load_removed(session: AsyncSession, first_day: date, last_day: date) -> dict[date, list[_Removed]]:
    # Removal date = last_seen_at: the last crawl that still saw the listing. There's no
    # removed_at — status flips whenever the next full crawl notices it's gone (see
    # ListingRepository.mark_missing_as_removed) — and last_seen_at is the closer estimate of when
    # it actually left the source.
    first_price = (
        select(ListingSnapshot.price)
        .where(ListingSnapshot.listing_id == Listing.id)
        .order_by(ListingSnapshot.captured_at.asc())
        .limit(1)
        .correlate(Listing)
        .scalar_subquery()
    )
    start = datetime.combine(first_day, time.min, tzinfo=timezone.utc)
    end = datetime.combine(last_day + timedelta(days=1), time.min, tzinfo=timezone.utc)
    result = await session.execute(
        select(
            Listing.make,
            Listing.model,
            Listing.first_seen_at,
            Listing.last_seen_at,
            Listing.price,
            first_price.label("first_price"),
        ).where(
            Listing.status == ListingStatus.REMOVED,
            Listing.last_seen_at >= start,
            Listing.last_seen_at < end,
        )
    )

    by_day: dict[date, list[_Removed]] = defaultdict(list)
    for make, model, first_seen_at, last_seen_at, price, first_price_value in result.all():
        last_seen = _as_utc(last_seen_at)
        days_on_market = max((last_seen - _as_utc(first_seen_at)).total_seconds() / 86400, 0.0)
        by_day[last_seen.date()].append(_Removed(make, model, days_on_market, price, first_price_value))
    return by_day


async def refresh_removal_stats(session: AsyncSession, now: datetime | None = None) -> int:
    """Recompute every window the page reads, as of the last *complete* UTC day. Idempotent —
    rewrites the same (stat_date, period_days) rows each run, which is also what picks up removals
    the crawler only noticed a day or two late. Returns the number of rows written.
    """
    now = now or datetime.now(timezone.utc)
    last_day = _as_utc(now).date() - timedelta(days=1)
    targets = _targets(last_day)
    first_day = min(as_of - timedelta(days=period - 1) for as_of, period in targets)

    by_day = await _load_removed(session, first_day, last_day)

    rows: list[RemovalStats] = []
    for as_of, period in targets:
        window = [
            item
            for offset in range(period)
            for item in by_day.get(as_of - timedelta(days=offset), ())
        ]
        rows.extend(_rows_for_window(as_of, period, window, now))

    await session.execute(
        delete(RemovalStats).where(
            or_(*[and_(RemovalStats.stat_date == d, RemovalStats.period_days == p) for d, p in targets])
        )
    )
    session.add_all(rows)
    await session.commit()
    return len(rows)


async def run_refresh_removal_stats(ctx: dict[str, Any]) -> None:
    async with ctx["session_factory"]() as session:
        await refresh_removal_stats(session)
