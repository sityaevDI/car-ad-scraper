import pytest
from sqlalchemy import func, select

from app.listings.repository import ListingRepository
from app.models.listing import Listing
from app.models.snapshot import ListingSnapshot
from app.sources.base import SourceListing
from tests.conftest import seed_source


def _listing(external_id: str = "42", price: int = 10_000) -> SourceListing:
    return SourceListing(
        external_id=external_id,
        canonical_url=f"https://example.com/{external_id}",
        title="Test listing",
        make="Skoda",
        model="Octavia",
        production_year=2019,
        mileage_km=100_000,
        price=price,
        currency="EUR",
    )


@pytest.mark.asyncio
async def test_upsert_listing_creates_new_listing_and_snapshot(session):
    source = await seed_source(session)
    repo = ListingRepository(session)

    listing, is_new, previous_price = await repo.upsert_listing(source.id, _listing())

    assert is_new is True
    assert previous_price is None
    assert listing.external_id == "42"

    snapshots = await repo.get_history(listing.id)
    assert len(snapshots) == 1


@pytest.mark.asyncio
async def test_upsert_listing_concurrent_insert_falls_back_to_update(session, monkeypatch):
    """Reproduces the production race (job 75fdd3e7 on 2026-09-10): two scrape jobs for the same
    source both call upsert_listing for the same (source_id, external_id) before either has
    committed, so both see it as "new". Here that's simulated by forcing the first `_find_existing`
    check to miss a row that (from the DB's point of view) another job has just inserted and
    committed, so the subsequent INSERT hits uq_listings_source_external_id. The repository must
    catch that IntegrityError and fall back to updating the row the other job created, rather than
    letting it propagate and abort the job's session.
    """
    source = await seed_source(session)
    repo = ListingRepository(session)

    other_job_repo = ListingRepository(session)
    winning_listing, _, _ = await other_job_repo.upsert_listing(source.id, _listing(price=9_000))
    await session.commit()

    real_find_existing = ListingRepository._find_existing
    call_count = 0

    async def flaky_find_existing(self, source_id, external_id):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return None
        return await real_find_existing(self, source_id, external_id)

    monkeypatch.setattr(ListingRepository, "_find_existing", flaky_find_existing)

    listing, is_new, previous_price = await repo.upsert_listing(source.id, _listing(price=10_000))

    assert is_new is False
    assert listing.id == winning_listing.id
    assert previous_price == 9_000
    assert listing.price == 10_000

    await session.commit()

    count = await session.scalar(
        select(func.count()).select_from(Listing).where(Listing.source_id == source.id, Listing.external_id == "42")
    )
    assert count == 1

    snapshot_count = await session.scalar(
        select(func.count()).select_from(ListingSnapshot).where(ListingSnapshot.listing_id == winning_listing.id)
    )
    assert snapshot_count == 2
