"""Orchestrates market price computation and lookup. Computation (recompute_segment/recompute_due)
runs from the batch cron job (app/scraping/scheduler.py::recompute_dirty_market_segments); lookups
(get_market_comparison/get_price_score(s)) run on API read paths and never compute synchronously —
see app/market/__init__.py for the overall flow.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.market.confidence import ALGORITHM_VERSION, score_confidence
from app.market.config import get_market_config
from app.market.pricing import score_listing
from app.market.repository import MarketRepository
from app.market.schemas import MarketComparisonOut, MarketEstimateOut, PriceScoreOut
from app.market.segment import SegmentCriteria, segment_criteria_for_listing, segment_criteria_from_row
from app.market.stats import robust_estimate
from app.models.listing import Listing
from app.models.market import MarketConfidence, MarketConfig, MarketPriceSnapshot


class MarketPriceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = MarketRepository(session)

    async def recompute_segment(self, criteria: SegmentCriteria, config: MarketConfig) -> MarketPriceSnapshot:
        listings = await self.repository.get_active_listings_for_segment(
            criteria, mileage_bucket_km=config.mileage_bucket_km
        )
        prices = [listing.price for listing in listings]
        estimate = robust_estimate(
            prices, iqr_multiplier=config.outlier_iqr_multiplier, min_sample_size=config.min_sample_size
        )
        confidence = score_confidence(
            estimate,
            confidence_medium_min_sample=config.confidence_medium_min_sample,
            confidence_high_min_sample=config.confidence_high_min_sample,
            high_dispersion_ratio=config.confidence_high_dispersion_ratio,
        )
        snapshot = MarketPriceSnapshot(
            segment_key=criteria.key(),
            **criteria.as_columns(),
            computed_at=datetime.now(timezone.utc),
            algorithm_version=ALGORITHM_VERSION,
            sample_size=estimate.sample_size,
            filtered_sample_size=estimate.filtered_sample_size,
            estimated_price=estimate.estimated_price,
            price_low=estimate.price_low,
            price_high=estimate.price_high,
            confidence=confidence,
        )
        await self.repository.write_snapshot(snapshot)
        return snapshot

    async def recompute_due(self, batch_size: int) -> int:
        """Called from the cron job — one commit per batch, not per segment, so a mid-batch
        failure doesn't leave earlier segments in this batch half-written (arq retries the whole
        job on an unhandled exception, and a partial commit would make that retry redo work that
        already landed).
        """
        config = await get_market_config(self.session)
        dirty = await self.repository.pop_due_dirty(batch_size)
        for row in dirty:
            await self.recompute_segment(segment_criteria_from_row(row), config)
        return len(dirty)

    async def get_market_comparison(self, listing: Listing) -> MarketComparisonOut:
        config = await get_market_config(self.session)
        criteria = segment_criteria_for_listing(listing, mileage_bucket_km=config.mileage_bucket_km)
        snapshot = await self.repository.get_latest_snapshot(criteria.key())
        if snapshot is None:
            return MarketComparisonOut(market=None, price_score=None)

        market = MarketEstimateOut(
            estimated_price=snapshot.estimated_price,
            currency=snapshot.currency,
            price_low=snapshot.price_low,
            price_high=snapshot.price_high,
            confidence=snapshot.confidence,
            comparable_listings_count=snapshot.sample_size,
            computed_at=snapshot.computed_at,
            algorithm_version=snapshot.algorithm_version,
        )

        price_score_out = None
        if snapshot.confidence != MarketConfidence.INSUFFICIENT:
            weights = await self.repository.get_equipment_weights()
            score = score_listing(
                listing.price,
                listing.equipment,
                snapshot,
                weights,
                max_equipment_adjustment_pct=config.max_equipment_adjustment_pct,
                deviation_market_band_pct=config.deviation_market_band_pct,
                deviation_significant_band_pct=config.deviation_significant_band_pct,
            )
            price_score_out = PriceScoreOut(
                price_ratio=score.price_ratio, deviation_pct=score.deviation_pct, label=score.label
            )

        return MarketComparisonOut(market=market, price_score=price_score_out)

    async def get_price_score(self, listing: Listing) -> PriceScoreOut | None:
        scores = await self.get_price_scores([listing])
        return scores.get(listing.id)

    async def get_price_scores(self, listings: list[Listing]) -> dict[uuid.UUID, PriceScoreOut]:
        """Batched — one snapshot query for the whole page instead of N+1. Used by
        app/search/service.py's flat (ungrouped) results and app/api/v1/listings.py's
        `_to_listing_out`.
        """
        if not listings:
            return {}
        config = await get_market_config(self.session)
        segment_key_by_listing_id = {
            listing.id: segment_criteria_for_listing(listing, mileage_bucket_km=config.mileage_bucket_km).key()
            for listing in listings
        }
        snapshots = await self.repository.get_latest_snapshots(list(set(segment_key_by_listing_id.values())))
        weights = await self.repository.get_equipment_weights()

        result: dict[uuid.UUID, PriceScoreOut] = {}
        for listing in listings:
            snapshot = snapshots.get(segment_key_by_listing_id[listing.id])
            if snapshot is None or snapshot.confidence == MarketConfidence.INSUFFICIENT:
                continue
            score = score_listing(
                listing.price,
                listing.equipment,
                snapshot,
                weights,
                max_equipment_adjustment_pct=config.max_equipment_adjustment_pct,
                deviation_market_band_pct=config.deviation_market_band_pct,
                deviation_significant_band_pct=config.deviation_significant_band_pct,
            )
            result[listing.id] = PriceScoreOut(
                price_ratio=score.price_ratio, deviation_pct=score.deviation_pct, label=score.label
            )
        return result
