from sqlalchemy import select

from app.market.config import get_market_config
from app.market.segment import segment_criteria_for_listing
from app.market.service import MarketPriceService
from app.models.market import MarketConfidence, MarketDirtySegment
from tests.conftest import make_listing, seed_source


async def test_recompute_due_processes_dirty_segments_and_clears_the_queue(session):
    source = await seed_source(session)
    listings = [
        make_listing(source.id, price=10_000, mileage_km=40_000),
        make_listing(source.id, price=10_400, mileage_km=42_000),
        make_listing(source.id, price=10_800, mileage_km=45_000),
        make_listing(source.id, price=10_200, mileage_km=48_000),
        make_listing(source.id, price=9_800, mileage_km=50_000),
    ]
    for listing in listings:
        session.add(listing)
    await session.commit()

    service = MarketPriceService(session)
    config = await get_market_config(session)
    criteria = segment_criteria_for_listing(listings[0], mileage_bucket_km=config.mileage_bucket_km)
    await service.repository.mark_dirty(criteria)
    await session.commit()

    processed = await service.recompute_due(batch_size=200)
    await session.commit()

    assert processed == 1
    remaining_dirty = (await session.execute(select(MarketDirtySegment))).scalars().all()
    assert remaining_dirty == []

    snapshot = await service.repository.get_latest_snapshot(criteria.key())
    assert snapshot is not None
    assert snapshot.sample_size == 5
    assert snapshot.confidence in (MarketConfidence.LOW, MarketConfidence.MEDIUM, MarketConfidence.HIGH)
    assert snapshot.estimated_price is not None


async def test_recompute_segment_below_min_sample_size_is_insufficient(session):
    source = await seed_source(session)
    listing_a = make_listing(source.id, price=10_000, external_id="a")
    listing_b = make_listing(source.id, price=10_500, external_id="b")
    session.add(listing_a)
    session.add(listing_b)
    await session.commit()

    service = MarketPriceService(session)
    config = await get_market_config(session)  # default market_min_sample_size is 5
    criteria = segment_criteria_for_listing(listing_a, mileage_bucket_km=config.mileage_bucket_km)

    snapshot = await service.recompute_segment(criteria, config)
    await session.commit()

    assert snapshot.confidence == MarketConfidence.INSUFFICIENT
    assert snapshot.estimated_price is None
    assert snapshot.sample_size == 2


async def test_get_market_comparison_returns_none_when_no_snapshot_exists_yet(session):
    source = await seed_source(session)
    listing = make_listing(source.id, price=10_000)
    session.add(listing)
    await session.commit()

    result = await MarketPriceService(session).get_market_comparison(listing)

    assert result.market is None
    assert result.price_score is None


async def test_get_market_comparison_after_recompute(session):
    source = await seed_source(session)
    listings = [make_listing(source.id, price=10_000 + i * 100, external_id=str(i)) for i in range(6)]
    for listing in listings:
        session.add(listing)
    await session.commit()

    service = MarketPriceService(session)
    config = await get_market_config(session)
    criteria = segment_criteria_for_listing(listings[0], mileage_bucket_km=config.mileage_bucket_km)
    await service.recompute_segment(criteria, config)
    await session.commit()

    result = await service.get_market_comparison(listings[0])

    assert result.market is not None
    assert result.market.comparable_listings_count == 6
    assert result.market.confidence != MarketConfidence.INSUFFICIENT
    assert result.price_score is not None


async def test_get_price_scores_is_batched_across_listings(session):
    source = await seed_source(session)
    listings = [make_listing(source.id, price=10_000 + i * 50, external_id=str(i)) for i in range(6)]
    for listing in listings:
        session.add(listing)
    await session.commit()

    service = MarketPriceService(session)
    config = await get_market_config(session)
    criteria = segment_criteria_for_listing(listings[0], mileage_bucket_km=config.mileage_bucket_km)
    await service.recompute_segment(criteria, config)
    await session.commit()

    scores = await service.get_price_scores(listings)

    assert len(scores) == 6
    for listing in listings:
        assert listing.id in scores
