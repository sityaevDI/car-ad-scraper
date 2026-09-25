"""Persistence for market segments: the dirty-segment queue, price snapshots, active listings
within a segment, and equipment weights.
"""

from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.market.segment import SegmentCriteria, bucket_engine_volume_cc
from app.models.listing import Listing, ListingStatus
from app.models.market import MarketDirtySegment, MarketEquipmentWeight, MarketPriceSnapshot


class MarketRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def mark_dirty(self, criteria: SegmentCriteria) -> None:
        """Idempotent — a segment already dirty stays dirty with its original marked_at, no error
        on a duplicate mark (many listings in the same segment can each trigger this in one scrape
        run; see app/scraping/pipeline.py).
        """
        segment_key = criteria.key()
        existing = await self.session.get(MarketDirtySegment, segment_key)
        if existing is None:
            self.session.add(
                MarketDirtySegment(
                    segment_key=segment_key, marked_at=datetime.now(timezone.utc), **criteria.as_columns()
                )
            )

    async def pop_due_dirty(self, batch_size: int) -> list[MarketDirtySegment]:
        """Claims up to `batch_size` dirty segments (oldest-marked first) and removes them from
        the queue. Not FOR-UPDATE-SKIP-LOCKED — a single worker process runs the recompute cron
        today (app/scraping/worker.py), so there's no concurrent claimant to skip past yet; revisit
        if a second worker process is ever added.
        """
        stmt = select(MarketDirtySegment).order_by(MarketDirtySegment.marked_at).limit(batch_size)
        rows = list((await self.session.execute(stmt)).scalars().all())
        if rows:
            keys = [row.segment_key for row in rows]
            await self.session.execute(delete(MarketDirtySegment).where(MarketDirtySegment.segment_key.in_(keys)))
        return rows

    async def get_active_listings_for_segment(
        self, criteria: SegmentCriteria, *, mileage_bucket_km: int
    ) -> list[Listing]:
        """The comparable group itself — every active listing whose own segment criteria match.
        `criteria.mileage_bucket` is a floor (see segment.py::bucket_mileage_km), so the matching
        range is `[mileage_bucket, mileage_bucket + mileage_bucket_km)` under the *current*
        mileage_bucket_km config — passed in by the caller (service.py, which already has
        MarketConfig loaded) rather than re-read here.

        make/model and engine_volume_bucket are filtered in Python, not SQL: SQLite's built-in
        `lower()` is ASCII-only (it leaves "Škoda" as "Škoda", not "škoda"), unlike Postgres's
        locale-aware `lower()` — comparing a SQL-side `func.lower(Listing.make)` against
        `criteria.make` (already lowercased in Python by segment.py) would silently disagree
        between the sqlite test DB and Postgres prod. Filtering make/model with the same Python
        `.lower()` on both sides sidesteps the dialect difference entirely. engine_volume_bucket
        has no natural SQL range test as clean as mileage's, so it's filtered the same way.
        """
        stmt = select(Listing).where(
            Listing.status == ListingStatus.ACTIVE,
            Listing.source_id == criteria.source_id,
            Listing.production_year == criteria.production_year,
            Listing.fuel_type == criteria.fuel_type,
            Listing.transmission == criteria.transmission,
            Listing.body_type == criteria.body_type,
            Listing.mileage_km >= criteria.mileage_bucket,
            Listing.mileage_km < criteria.mileage_bucket + mileage_bucket_km,
        )
        candidates = (await self.session.execute(stmt)).scalars().all()
        return [
            listing
            for listing in candidates
            if listing.make.lower() == criteria.make
            and listing.model.lower() == criteria.model
            and bucket_engine_volume_cc(listing.engine_volume_cc) == criteria.engine_volume_bucket
        ]

    async def write_snapshot(self, snapshot: MarketPriceSnapshot) -> None:
        self.session.add(snapshot)

    async def get_latest_snapshot(self, segment_key: str) -> MarketPriceSnapshot | None:
        stmt = (
            select(MarketPriceSnapshot)
            .where(MarketPriceSnapshot.segment_key == segment_key)
            .order_by(MarketPriceSnapshot.computed_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def get_latest_snapshots(self, segment_keys: list[str]) -> dict[str, MarketPriceSnapshot]:
        """One query for a page of search results instead of N+1 — see
        app/market/service.py::estimate_for_listings/score_listings.
        """
        if not segment_keys:
            return {}
        row_number = (
            func.row_number()
            .over(partition_by=MarketPriceSnapshot.segment_key, order_by=MarketPriceSnapshot.computed_at.desc())
            .label("rn")
        )
        subq = (
            select(MarketPriceSnapshot, row_number).where(MarketPriceSnapshot.segment_key.in_(segment_keys)).subquery()
        )
        snapshot_alias = aliased(MarketPriceSnapshot, subq)
        stmt = select(snapshot_alias).where(subq.c.rn == 1)
        rows = (await self.session.execute(stmt)).scalars().all()
        return {row.segment_key: row for row in rows}

    async def get_equipment_weights(self) -> dict[str, float]:
        rows = (await self.session.execute(select(MarketEquipmentWeight))).scalars().all()
        return {row.equipment_slug: row.adjustment_pct for row in rows}
