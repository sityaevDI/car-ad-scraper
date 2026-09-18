import pytest

import app.market.cli as market_cli
from app.market.cli import _backfill
from tests.conftest import make_listing, seed_source

pytestmark = pytest.mark.asyncio


async def test_backfill_marks_every_active_listing_dirty_across_batches(session, monkeypatch, capsys):
    """Keyset pagination (id > last_id, ordered by id) must cover every active listing exactly
    once even when it takes several batches — the whole reason this isn't a single
    `.scalars().all()` or a live stream_scalars() cursor (see _backfill's comment: mark_dirty()
    issues its own nested query per row, which a still-open streaming cursor can't tolerate
    against real Postgres/asyncpg).

    All 5 listings share the same make/model/year/etc. (make_listing's defaults), so they fall
    into one segment — mark_dirty is idempotent, so "Computed 1" is the correct outcome for 5
    listings, not evidence anything was skipped. The real assertion is "Marked 5/5" — every one of
    the 5 rows across (with batch size 2) 3 separate batches got visited exactly once.
    """
    monkeypatch.setattr(market_cli, "_RECOMPUTE_BATCH_SIZE", 2)
    source = await seed_source(session)
    for external_id in (str(i) for i in range(5)):
        session.add(
            make_listing(
                source.id, external_id=external_id, make="Skoda", model="Octavia", production_year=2019
            )
        )
    await session.commit()

    await _backfill(session)

    out = capsys.readouterr().out
    assert "Marked 5/5 active listings' segments dirty." in out
    assert "Computed 1 market snapshots." in out
