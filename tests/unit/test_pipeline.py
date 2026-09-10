from collections.abc import AsyncIterator

from sqlalchemy import select

import app.sources.registry as registry
from app.models.listing import Listing, ListingStatus
from app.models.scrape_rate_limit import ScrapeRateLimit
from app.scraping.fetch_outcome import FetchBlockedError, FetchOutcome, ParserError
from app.scraping.pipeline import _COMMIT_BATCH_SIZE, run_scrape
from app.search.query import SearchQuery
from app.sources.base import SourceListing, SourceListingRef


def _listing(external_id: str, price: int) -> SourceListing:
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


class StubAdapter:
    source_code = "stub_source"
    display_name = "Stub Source"
    domain = "stub.example.com"
    country = "RS"

    def __init__(self, max_pages=5, proxy_provider=None, outcome_sink=None, **kwargs):
        self.outcome_sink = outcome_sink

    async def search_with_data(self, query: SearchQuery) -> AsyncIterator[SourceListing]:
        for external_id in self.external_ids:
            if self.outcome_sink:
                self.outcome_sink(FetchOutcome.SUCCESS)
            yield _listing(external_id, 10_000)

    async def fetch_listing(self, ref: SourceListingRef) -> SourceListing:
        return _listing(ref.external_id, 10_000)


class StubAdapterWithEquipment(StubAdapter):
    """Tracks fetch_listing calls (as a class attribute, since the pipeline instantiates a fresh
    adapter per run_scrape() call — see app/sources/registry.py) so tests can assert equipment is
    backfilled only once per listing (on creation), not re-fetched on every re-crawl. Each test
    gets its own isolated subclass via _make_stub_adapter_with_equipment below.
    """

    fetch_listing_calls: list[str]

    async def fetch_listing(self, ref: SourceListingRef) -> SourceListing:
        self.fetch_listing_calls.append(ref.external_id)
        listing = _listing(ref.external_id, 10_000)
        listing.equipment = ["bluetooth", "apple_carplay"]
        return listing


def _make_stub_adapter_with_equipment(external_ids: list[str]) -> type[StubAdapterWithEquipment]:
    return type(
        "_ConfiguredStubAdapterWithEquipment",
        (StubAdapterWithEquipment,),
        {"external_ids": external_ids, "fetch_listing_calls": []},
    )


def _make_stub_adapter(external_ids: list[str]) -> type[StubAdapter]:
    return type("_ConfiguredStubAdapter", (StubAdapter,), {"external_ids": external_ids})


class StubBlockedAdapter:
    source_code = "stub_source"
    display_name = "Stub Source"
    domain = "stub.example.com"
    country = "RS"

    def __init__(self, max_pages=5, proxy_provider=None, outcome_sink=None, **kwargs):
        self.outcome_sink = outcome_sink

    async def search_with_data(self, query: SearchQuery) -> AsyncIterator[SourceListing]:
        if self.outcome_sink:
            self.outcome_sink(FetchOutcome.SUCCESS)
        yield _listing("1", 10_000)
        yield _listing("2", 12_000)
        if self.outcome_sink:
            self.outcome_sink(FetchOutcome.FORBIDDEN)
        raise FetchBlockedError(FetchOutcome.FORBIDDEN)

    async def fetch_listing(self, ref: SourceListingRef) -> SourceListing:
        return _listing(ref.external_id, 10_000)


class StubParserErrorAdapter:
    source_code = "stub_source"
    display_name = "Stub Source"
    domain = "stub.example.com"
    country = "RS"

    def __init__(self, max_pages=5, proxy_provider=None, outcome_sink=None, **kwargs):
        self.outcome_sink = outcome_sink

    async def search_with_data(self, query: SearchQuery) -> AsyncIterator[SourceListing]:
        if self.outcome_sink:
            self.outcome_sink(FetchOutcome.SUCCESS)
        yield _listing("1", 10_000)
        if self.outcome_sink:
            self.outcome_sink(FetchOutcome.PARSER_ERROR)
        raise ParserError("unexpected page shape")

    async def fetch_listing(self, ref: SourceListingRef) -> SourceListing:
        return _listing(ref.external_id, 10_000)


async def test_run_scrape_persists_partial_results_when_blocked_mid_crawl(session, monkeypatch):
    monkeypatch.setitem(registry.SOURCE_REGISTRY, "stub_source", StubBlockedAdapter)

    stats = await run_scrape(session, source_code="stub_source", query=SearchQuery(), max_pages=1)

    assert stats.listings_seen == 2
    assert stats.listings_created == 2
    assert stats.listings_updated == 0
    assert stats.blocked is True
    assert stats.outcome_counts == {"success": 1, "forbidden": 1}
    assert stats.error_detail == "Fetch blocked: forbidden"

    persisted = (await session.execute(select(Listing))).scalars().all()
    assert len(persisted) == 2


async def test_run_scrape_persists_partial_results_on_parser_error_mid_crawl(session, monkeypatch):
    monkeypatch.setitem(registry.SOURCE_REGISTRY, "stub_source", StubParserErrorAdapter)

    stats = await run_scrape(session, source_code="stub_source", query=SearchQuery(), max_pages=1)

    assert stats.listings_seen == 1
    assert stats.blocked is True
    assert stats.outcome_counts == {"success": 1, "parser_error": 1}
    assert stats.error_detail == "Parser error: unexpected page shape"

    persisted = (await session.execute(select(Listing))).scalars().all()
    assert len(persisted) == 1


class StubPageSkippedAdapter:
    """Mirrors PolovniAutomobiliSource._iter_search_pages after a page fails to parse twice: it
    records PARSER_ERROR/PAGE_SKIPPED via the outcome sink but keeps crawling and yielding
    listings instead of raising — run_scrape should still treat the run as incomplete (skip
    mark_removed, end up PARTIAL) without losing the listings gathered after the skipped page.
    """

    source_code = "stub_source"
    display_name = "Stub Source"
    domain = "stub.example.com"
    country = "RS"

    def __init__(self, max_pages=5, proxy_provider=None, outcome_sink=None, **kwargs):
        self.outcome_sink = outcome_sink

    async def search_with_data(self, query: SearchQuery) -> AsyncIterator[SourceListing]:
        if self.outcome_sink:
            self.outcome_sink(FetchOutcome.SUCCESS)
        yield _listing("1", 10_000)
        if self.outcome_sink:
            self.outcome_sink(FetchOutcome.PARSER_ERROR)
            self.outcome_sink(FetchOutcome.PARSER_ERROR)
            self.outcome_sink(FetchOutcome.PAGE_SKIPPED)
            self.outcome_sink(FetchOutcome.SUCCESS)
        yield _listing("2", 12_000)

    async def fetch_listing(self, ref: SourceListingRef) -> SourceListing:
        return _listing(ref.external_id, 10_000)


async def test_run_scrape_marks_blocked_when_a_page_was_skipped(session, monkeypatch):
    monkeypatch.setitem(registry.SOURCE_REGISTRY, "stub_source", StubPageSkippedAdapter)

    stats = await run_scrape(session, source_code="stub_source", query=SearchQuery(), mark_removed=True)

    # Unlike a hard abort, the crawl ran to completion — both listings persisted — but the run is
    # still not a clean full pass, so it's flagged the same way as an aborted one.
    assert stats.listings_seen == 2
    assert stats.blocked is True
    assert stats.listings_removed == 0
    assert stats.error_detail is None
    assert stats.outcome_counts["page_skipped"] == 1

    persisted = (await session.execute(select(Listing))).scalars().all()
    assert len(persisted) == 2


async def test_run_scrape_marks_missing_listings_removed_when_mark_removed_is_true(session, monkeypatch):
    monkeypatch.setitem(registry.SOURCE_REGISTRY, "stub_source", _make_stub_adapter(["1", "2", "3"]))
    await run_scrape(session, source_code="stub_source", query=SearchQuery(), mark_removed=True)

    monkeypatch.setitem(registry.SOURCE_REGISTRY, "stub_source", _make_stub_adapter(["1", "2"]))
    stats = await run_scrape(session, source_code="stub_source", query=SearchQuery(), mark_removed=True)

    assert stats.listings_removed == 1
    rows = (await session.execute(select(Listing))).scalars().all()
    persisted = {listing.external_id: listing.status for listing in rows}
    assert persisted == {"1": ListingStatus.ACTIVE, "2": ListingStatus.ACTIVE, "3": ListingStatus.REMOVED}


async def test_run_scrape_does_not_mark_removed_by_default(session, monkeypatch):
    monkeypatch.setitem(registry.SOURCE_REGISTRY, "stub_source", _make_stub_adapter(["1", "2", "3"]))
    await run_scrape(session, source_code="stub_source", query=SearchQuery())

    monkeypatch.setitem(registry.SOURCE_REGISTRY, "stub_source", _make_stub_adapter(["1"]))
    stats = await run_scrape(session, source_code="stub_source", query=SearchQuery())

    assert stats.listings_removed == 0
    statuses = {listing.status for listing in (await session.execute(select(Listing))).scalars().all()}
    assert statuses == {ListingStatus.ACTIVE}


async def test_run_scrape_skips_mark_removed_when_blocked_mid_crawl(session, monkeypatch):
    monkeypatch.setitem(registry.SOURCE_REGISTRY, "stub_source", _make_stub_adapter(["1", "2", "3"]))
    await run_scrape(session, source_code="stub_source", query=SearchQuery(), mark_removed=True)

    monkeypatch.setitem(registry.SOURCE_REGISTRY, "stub_source", StubBlockedAdapter)
    stats = await run_scrape(session, source_code="stub_source", query=SearchQuery(), max_pages=1, mark_removed=True)

    assert stats.blocked is True
    assert stats.listings_removed == 0
    statuses = {listing.status for listing in (await session.execute(select(Listing))).scalars().all()}
    assert statuses == {ListingStatus.ACTIVE}


async def test_run_scrape_backfills_equipment_once_on_creation(session, monkeypatch):
    """Search-page results don't carry equipment (see mapper.py), so a new listing gets one
    detail-page fetch to backfill it — but only once, not on every re-crawl of the same listing.
    """
    adapter_cls = _make_stub_adapter_with_equipment(["1"])
    monkeypatch.setitem(registry.SOURCE_REGISTRY, "stub_source", adapter_cls)

    await run_scrape(session, source_code="stub_source", query=SearchQuery())
    listing = (await session.execute(select(Listing))).scalar_one()
    assert listing.equipment == ["bluetooth", "apple_carplay"]
    assert adapter_cls.fetch_listing_calls == ["1"]


async def test_run_scrape_passes_admin_configured_rate_limit_to_adapter(session, monkeypatch):
    """The delay/jitter/network_error_retry_delay an admin sets via /api/v1/scrape/rate-limit
    (app/scraping/rate_limit.py's ScrapeRateLimit row) must reach the adapter constructor, not
    just app/config.py's static defaults.
    """
    session.add(
        ScrapeRateLimit(
            request_delay_seconds=0.11,
            request_jitter_seconds=0.05,
            network_error_retry_delay_seconds=1.5,
        )
    )
    await session.flush()

    received_kwargs: dict = {}

    class RecordingStubAdapter(StubAdapter):
        external_ids = ["1"]

        def __init__(self, **kwargs):
            received_kwargs.update(kwargs)
            super().__init__(**kwargs)

    monkeypatch.setitem(registry.SOURCE_REGISTRY, "stub_source", RecordingStubAdapter)

    await run_scrape(session, source_code="stub_source", query=SearchQuery())

    assert received_kwargs["delay"] == 0.11
    assert received_kwargs["jitter"] == 0.05
    assert received_kwargs["network_error_retry_delay"] == 1.5


async def test_run_scrape_commits_periodically_during_a_long_crawl(session, monkeypatch):
    """A long crawl shouldn't hold everything in one uncommitted transaction until the very end —
    see the module docstring on _COMMIT_BATCH_SIZE for why (long-held row locks, and losing an
    entire run's work to an exception the caller doesn't treat as partial-success).
    """
    external_ids = [str(i) for i in range(_COMMIT_BATCH_SIZE * 2 + 3)]
    monkeypatch.setitem(registry.SOURCE_REGISTRY, "stub_source", _make_stub_adapter(external_ids))

    commit_count = 0
    original_commit = session.commit

    async def _counting_commit():
        nonlocal commit_count
        commit_count += 1
        await original_commit()

    monkeypatch.setattr(session, "commit", _counting_commit)

    stats = await run_scrape(session, source_code="stub_source", query=SearchQuery())

    assert stats.listings_created == len(external_ids)
    # Two mid-crawl commits (at _COMMIT_BATCH_SIZE and 2 * _COMMIT_BATCH_SIZE listings seen) plus
    # the final commit at the end of run_scrape.
    assert commit_count == 3

    persisted = (await session.execute(select(Listing))).scalars().all()
    assert len(persisted) == len(external_ids)
