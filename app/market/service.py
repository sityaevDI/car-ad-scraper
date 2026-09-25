from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.market.removal_stats import DAILY_SERIES_DAYS
from app.market.schemas import (
    PERIOD_DAYS,
    Period,
    RemovalBreakdownRow,
    RemovalMetrics,
    RemovalSeriesPoint,
    RemovalStatsResponse,
)
from app.models.removal_stats import ALL_SCOPE, RemovalStats

BREAKDOWN_LIMIT = 10


def _metrics(row: RemovalStats) -> RemovalMetrics:
    return RemovalMetrics(
        removed_count=row.removed_count,
        median_days_on_market=row.median_days_on_market,
        median_price_at_removal=row.median_price_at_removal,
        price_cut_share=row.price_cut_share,
        median_price_cut_pct=row.median_price_cut_pct,
    )


class RemovalStatsService:
    """Reads the precomputed `removal_stats` rows — never touches Listing."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, period: Period, make: str | None) -> RemovalStatsResponse:
        period_days = PERIOD_DAYS[period]
        make = make or None
        make_scope = make or ALL_SCOPE

        as_of = await self.session.scalar(
            select(func.max(RemovalStats.stat_date)).where(RemovalStats.period_days == period_days)
        )
        if as_of is None:
            return RemovalStatsResponse(period=period, make=make)

        current = await self._row(as_of, period_days, make_scope, ALL_SCOPE)
        previous = await self._row(as_of - timedelta(days=period_days), period_days, make_scope, ALL_SCOPE)
        overall = current if make is None else await self._row(as_of, period_days, ALL_SCOPE, ALL_SCOPE)

        return RemovalStatsResponse(
            period=period,
            make=make,
            as_of=as_of,
            computed_at=overall.computed_at if overall else None,
            current=_metrics(current) if current else RemovalMetrics(removed_count=0),
            previous=_metrics(previous) if previous else None,
            series=await self._series(make_scope),
            breakdown=await self._breakdown(as_of, period_days, make),
        )

    async def _row(self, stat_date: date, period_days: int, make: str, model: str) -> RemovalStats | None:
        return await self.session.scalar(
            select(RemovalStats).where(
                RemovalStats.stat_date == stat_date,
                RemovalStats.period_days == period_days,
                RemovalStats.make == make,
                RemovalStats.model == model,
            )
        )

    async def _series(self, make: str) -> list[RemovalSeriesPoint]:
        last_day = await self.session.scalar(select(func.max(RemovalStats.stat_date)).where(RemovalStats.period_days == 1))
        if last_day is None:
            return []
        first_day = last_day - timedelta(days=DAILY_SERIES_DAYS - 1)
        result = await self.session.execute(
            select(RemovalStats.stat_date, RemovalStats.removed_count).where(
                RemovalStats.period_days == 1,
                RemovalStats.make == make,
                RemovalStats.model == ALL_SCOPE,
                RemovalStats.stat_date >= first_day,
            )
        )
        counts = {stat_date: count for stat_date, count in result.all()}
        return [
            RemovalSeriesPoint(date=day, removed_count=counts.get(day, 0))
            for day in (first_day + timedelta(days=i) for i in range(DAILY_SERIES_DAYS))
        ]

    async def _breakdown(self, as_of: date, period_days: int, make: str | None) -> list[RemovalBreakdownRow]:
        stmt = select(RemovalStats).where(RemovalStats.stat_date == as_of, RemovalStats.period_days == period_days)
        if make:
            stmt = stmt.where(RemovalStats.make == make, RemovalStats.model != ALL_SCOPE)
        else:
            stmt = stmt.where(RemovalStats.make != ALL_SCOPE, RemovalStats.model == ALL_SCOPE)
        rows = (
            await self.session.scalars(
                stmt.order_by(RemovalStats.removed_count.desc(), RemovalStats.make, RemovalStats.model).limit(
                    BREAKDOWN_LIMIT
                )
            )
        ).all()
        return [
            RemovalBreakdownRow(make=row.make, model=row.model or None, **_metrics(row).model_dump()) for row in rows
        ]
