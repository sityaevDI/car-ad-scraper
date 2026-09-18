import pytest
from sqlalchemy import select

import app.sources.registry as registry
from app.models.listing import Listing
from app.scraping import backfill as backfill_module
from app.scraping.backfill import _backfill
from app.scraping.detail_only_fields import DETAIL_ONLY_FIELDS
from app.scraping.fetch_outcome import FetchBlockedError, FetchOutcome
from app.sources.base import SourceListing, SourceListingRef
from tests.conftest import make_listing, seed_source

pytestmark = pytest.mark.asyncio


class _StubAdapter:
    def __init__(self, **kwargs):
        pass

    fetch_listing_calls: list[str] = []

    async def fetch_listing(self, ref: SourceListingRef) -> SourceListing:
        type(self).fetch_listing_calls.append(ref.external_id)
        if ref.external_id == "blocked":
            raise FetchBlockedError(FetchOutcome.FORBIDDEN)
        return SourceListing(
            external_id=ref.external_id,
            canonical_url=ref.url,
            title="Refetched",
            make="Skoda",
            model="Octavia",
            production_year=2019,
            mileage_km=100_000,
            price=10_000,
            currency="EUR",
            interior_material="leather" if ref.external_id != "no-value" else None,
            air_condition="automatic" if ref.external_id != "no-value" else None,
            drive_type="awd" if ref.external_id != "no-value" else None,
            equipment=["bluetooth"] if ref.external_id != "no-value" else [],
        )


async def test_backfill_sets_every_missing_field_from_one_fetch(session, monkeypatch):
    """The whole point of the unified engine over the old one-script-per-field scripts: a listing
    missing several detail-only fields gets exactly one detail-page fetch, not one per field.
    """
    monkeypatch.setitem(registry.SOURCE_REGISTRY, "polovniautomobili", _StubAdapter)
    _StubAdapter.fetch_listing_calls = []
    source = await seed_source(session)

    missing_both = make_listing(source.id, external_id="1", interior_material=None, drive_type=None)
    session.add(missing_both)
    await session.commit()

    await _backfill(session, source_code="polovniautomobili", fields=list(DETAIL_ONLY_FIELDS.values()), limit=None)

    refreshed = (await session.execute(select(Listing))).scalar_one()
    assert refreshed.interior_material == "leather"
    assert refreshed.air_condition == "automatic"
    assert refreshed.drive_type == "awd"
    assert refreshed.equipment == ["bluetooth"]
    assert _StubAdapter.fetch_listing_calls == ["1"]


async def test_backfill_never_overwrites_a_field_already_set(session, monkeypatch):
    """A listing selected because *one* field is missing must not have its already-set fields
    clobbered by the same fetch.
    """
    monkeypatch.setitem(registry.SOURCE_REGISTRY, "polovniautomobili", _StubAdapter)
    source = await seed_source(session)

    partially_set = make_listing(
        source.id, external_id="1", interior_material="cloth", air_condition=None, drive_type="front"
    )
    session.add(partially_set)
    await session.commit()

    await _backfill(session, source_code="polovniautomobili", fields=list(DETAIL_ONLY_FIELDS.values()), limit=None)

    refreshed = (await session.execute(select(Listing))).scalar_one()
    assert refreshed.interior_material == "cloth"  # untouched
    assert refreshed.drive_type == "front"  # untouched
    assert refreshed.air_condition == "automatic"  # backfilled


async def test_backfill_fields_flag_limits_which_fields_are_queried_and_written(session, monkeypatch):
    monkeypatch.setitem(registry.SOURCE_REGISTRY, "polovniautomobili", _StubAdapter)
    _StubAdapter.fetch_listing_calls = []
    source = await seed_source(session)

    # Missing drive_type only — not in `fields` below, so this listing shouldn't even be selected.
    session.add(make_listing(source.id, external_id="1", interior_material="cloth", drive_type=None))
    session.add(make_listing(source.id, external_id="2", interior_material=None, drive_type="front"))
    await session.commit()

    await _backfill(
        session, source_code="polovniautomobili", fields=[DETAIL_ONLY_FIELDS["interior_material"]], limit=None
    )

    assert _StubAdapter.fetch_listing_calls == ["2"]
    refreshed = {
        listing.external_id: listing for listing in (await session.execute(select(Listing))).scalars().all()
    }
    assert refreshed["1"].drive_type is None  # not requested, left alone
    assert refreshed["2"].interior_material == "leather"


async def test_backfill_paginates_across_multiple_batches(session, monkeypatch):
    """The keyset-pagination loop (id > last_id, ordered by id) must not skip or double-process a
    row at a batch boundary — this is the whole reason it exists over a single stream_scalars()
    cursor (see backfill.py's comment: a live cursor doesn't survive the periodic commit each
    batch needs against real Postgres/asyncpg).
    """
    monkeypatch.setitem(registry.SOURCE_REGISTRY, "polovniautomobili", _StubAdapter)
    monkeypatch.setattr(backfill_module, "_BATCH_SIZE", 2)
    _StubAdapter.fetch_listing_calls = []
    source = await seed_source(session)

    external_ids = [str(i) for i in range(5)]
    for external_id in external_ids:
        session.add(make_listing(source.id, external_id=external_id, interior_material=None))
    await session.commit()

    await _backfill(
        session, source_code="polovniautomobili", fields=[DETAIL_ONLY_FIELDS["interior_material"]], limit=None
    )

    # Every listing fetched exactly once, none skipped or repeated, despite 5 rows over batches of 2.
    assert sorted(_StubAdapter.fetch_listing_calls) == sorted(external_ids)
    refreshed = (await session.execute(select(Listing))).scalars().all()
    assert all(listing.interior_material == "leather" for listing in refreshed)


async def test_backfill_limit_applies_across_batch_boundaries(session, monkeypatch):
    monkeypatch.setitem(registry.SOURCE_REGISTRY, "polovniautomobili", _StubAdapter)
    monkeypatch.setattr(backfill_module, "_BATCH_SIZE", 2)
    _StubAdapter.fetch_listing_calls = []
    source = await seed_source(session)

    for external_id in (str(i) for i in range(5)):
        session.add(make_listing(source.id, external_id=external_id, interior_material=None))
    await session.commit()

    await _backfill(
        session, source_code="polovniautomobili", fields=[DETAIL_ONLY_FIELDS["interior_material"]], limit=3
    )

    assert len(_StubAdapter.fetch_listing_calls) == 3


async def test_backfill_skips_blocked_listings_without_aborting(session, monkeypatch):
    monkeypatch.setitem(registry.SOURCE_REGISTRY, "polovniautomobili", _StubAdapter)
    source = await seed_source(session)

    session.add(make_listing(source.id, external_id="blocked", interior_material=None))
    session.add(make_listing(source.id, external_id="no-value", interior_material=None))
    await session.commit()

    await _backfill(
        session, source_code="polovniautomobili", fields=[DETAIL_ONLY_FIELDS["interior_material"]], limit=None
    )

    refreshed = {
        listing.external_id: listing for listing in (await session.execute(select(Listing))).scalars().all()
    }
    assert refreshed["blocked"].interior_material is None
    assert refreshed["no-value"].interior_material is None
