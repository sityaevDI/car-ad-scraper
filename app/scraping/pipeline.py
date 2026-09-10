"""Persists a source's search results into Postgres. Runs either directly (app/scraping/cli.py,
for local dev) or from an arq job (app/scraping/worker.py).
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.listings.repository import ListingRepository
from app.models.listing import Listing
from app.models.source import Source
from app.scraping.fetch_outcome import FetchBlockedError, FetchOutcome, OutcomeCounter, ParserError
from app.scraping.proxy import ProxyProvider
from app.scraping.rate_limit import get_scrape_rate_limit
from app.search.query import SearchQuery
from app.sources.base import CarSource, SourceListing, SourceListingRef
from app.sources.registry import get_source_adapter

# Commit every N upserted listings instead of once at the end of the whole crawl. A full crawl can
# span many minutes of network I/O (page fetches, per-listing detail fetches); holding one
# transaction open across all of it holds row locks on every updated Listing for the run's entire
# duration and loses all already-scraped work if something later in the run raises an exception
# the caller doesn't treat as a partial-success case (see app/scraping/worker.py's except clause).
_COMMIT_BATCH_SIZE = 50


@dataclass
class ScrapeStats:
    listings_seen: int = 0
    listings_created: int = 0
    listings_updated: int = 0
    listings_removed: int = 0
    outcome_counts: dict[str, int] = field(default_factory=dict)
    blocked: bool = False
    # Set when `blocked` was caused by a hard abort (FetchBlockedError/ParserError bubbling out of
    # the adapter) — the message that explains why, since `outcome_counts` alone only says how many
    # of which outcome, not what actually happened. Unset for a skipped-page-only partial run,
    # where per-page detail already reads out of outcome_counts (parser_error/page_skipped counts).
    error_detail: str | None = None
    seen_external_ids: set[str] = field(default_factory=set)
    # Per-listing detail the aggregate counts above don't carry — consumed by
    # app/notifications/matching.py (issues #21/#26) to generate NEW_MATCH/PRICE_DROP events
    # without re-querying "what changed this run".
    new_listing_ids: list[uuid.UUID] = field(default_factory=list)
    price_drops: list[tuple[uuid.UUID, int, int]] = field(default_factory=list)  # (listing_id, previous, current)


async def get_or_create_source(session: AsyncSession, code: str, name: str, domain: str, country: str) -> Source:
    result = await session.execute(select(Source).where(Source.code == code))
    source = result.scalar_one_or_none()
    if source is None:
        source = Source(code=code, name=name, domain=domain, country=country)
        session.add(source)
        await session.flush()
    return source


async def _search_listings(adapter: CarSource, query: SearchQuery) -> AsyncIterator[SourceListing]:
    """Prefer an adapter's optional search_with_data() — a source whose search results already
    carry full listing data (like Polovni Automobili) skips a per-listing detail fetch this way.
    Not part of the CarSource Protocol itself, since not every source can offer it; adapters
    without it fall back to search() + fetch_listing() per ref.
    """
    search_with_data = getattr(adapter, "search_with_data", None)
    if search_with_data is not None:
        async for listing in search_with_data(query):
            yield listing
        return
    async for ref in adapter.search(query):
        yield await adapter.fetch_listing(ref)


async def _enrich_with_equipment(adapter: CarSource, repository: ListingRepository, listing: Listing) -> None:
    """Search-page results don't carry `equipment` (see mapper.py's docstring on the search vs.
    detail page JSON shapes), so a brand-new listing gets one extra detail-page fetch here to
    backfill it. Only done once, on creation — a listing's equipment doesn't change over its
    lifetime, so re-crawls of an already-known listing skip this and stay cheap.
    """
    ref = SourceListingRef(external_id=listing.external_id, url=listing.canonical_url)
    try:
        detail = await adapter.fetch_listing(ref)
    except (FetchBlockedError, ParserError):
        return
    if detail.equipment:
        repository.set_equipment(listing, detail.equipment)


async def run_scrape(
    session: AsyncSession,
    source_code: str,
    query: SearchQuery,
    max_pages: int = 5,
    proxy_provider: ProxyProvider | None = None,
    mark_removed: bool = False,
) -> ScrapeStats:
    """`mark_removed` transitions listings absent from this crawl to REMOVED (see
    ListingRepository.mark_missing_as_removed) — only safe when `query` covers the whole source,
    since anything filtered out would otherwise look "missing" and get marked removed too. Callers
    only pass it for FULL_SOURCE_REFRESH jobs (see app/scraping/worker.py), and it's skipped here
    whenever the crawl was cut short by FetchBlockedError/ParserError, since a partial crawl can't
    tell a genuinely removed listing from one it just didn't get to yet.
    """
    counter = OutcomeCounter()
    rate_limit = await get_scrape_rate_limit(session)
    # delay/jitter/network_error_retry_delay are adapter-specific kwargs only PolovniAutomobiliSource
    # accepts today (see its __init__ docstring) — fine while it's the only registered source, but
    # a second adapter without matching kwargs would need this call to become source-aware.
    adapter = get_source_adapter(
        source_code,
        max_pages=max_pages,
        proxy_provider=proxy_provider,
        outcome_sink=counter.record,
        delay=rate_limit.request_delay_seconds,
        jitter=rate_limit.request_jitter_seconds,
        network_error_retry_delay=rate_limit.network_error_retry_delay_seconds,
    )
    source = await get_or_create_source(
        session, code=adapter.source_code, name=adapter.display_name, domain=adapter.domain, country=adapter.country
    )
    repository = ListingRepository(session)

    stats = ScrapeStats()
    try:
        async for source_listing in _search_listings(adapter, query):
            stats.listings_seen += 1
            stats.seen_external_ids.add(source_listing.external_id)
            listing, is_new, previous_price = await repository.upsert_listing(source.id, source_listing)
            if is_new:
                stats.listings_created += 1
                stats.new_listing_ids.append(listing.id)
                await _enrich_with_equipment(adapter, repository, listing)
            else:
                stats.listings_updated += 1
                if previous_price is not None and previous_price > listing.price:
                    stats.price_drops.append((listing.id, previous_price, listing.price))

            if stats.listings_seen % _COMMIT_BATCH_SIZE == 0:
                await session.commit()
    except (FetchBlockedError, ParserError) as exc:
        # Stop pagination early but keep whatever was already upserted this run — a partial
        # result is more useful than losing it. FetchBlockedError means the source just told us
        # to back off (burning further proxy/direct requests would be wasteful); ParserError here
        # means the adapter itself gave up on retrying (see PolovniAutomobiliSource._fetch_listing
        # /fetch_listing, which still raise immediately — only the search-page loop retries and
        # skips instead of raising).
        stats.blocked = True
        stats.error_detail = str(exc)

    if counter.as_dict().get(FetchOutcome.PAGE_SKIPPED.value, 0) > 0:
        # A skipped page means this run isn't a complete picture of the source even though the
        # crawl otherwise ran to completion — same reasoning as the abort-mid-crawl case above.
        stats.blocked = True

    if mark_removed and not stats.blocked and stats.listings_seen > 0:
        stats.listings_removed = await repository.mark_missing_as_removed(source.id, stats.seen_external_ids)

    stats.outcome_counts = counter.as_dict()
    await session.commit()
    return stats
