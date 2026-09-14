"""Polovni Automobili source adapter. See app/sources/base.py for the CarSource contract and
app/sources/polovniautomobili/mapper.py for why this parses the page's `__NEXT_DATA__` JSON
instead of the original PoC's (now-stale) CSS selectors.
"""

import json
import logging
import re
from collections.abc import AsyncIterator, Callable
from typing import TypeVar
from urllib.parse import urlencode

from app.config import get_settings
from app.scraping.fetch_outcome import FetchOutcome, ParserError
from app.scraping.fetch_strategy import FetchStrategy, ProxyHttpFetcher, raise_for_blocked
from app.scraping.proxy import ProxyProvider, get_proxy_provider
from app.search.query import SearchQuery
from app.sources.base import SourceListing, SourceListingRef
from app.sources.polovniautomobili.mapper import (
    BASE_URL,
    SEARCH_RESULT_REQUIRED_FIELDS,
    map_product_data,
    map_search_result,
    normalize_fuel_type,
)
from scraping.translation import fuel_type_codes

_T = TypeVar("_T")

logger = logging.getLogger(__name__)

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_FUEL_CODE_BY_NORMALIZED = {normalize_fuel_type(raw): code for code, raw in fuel_type_codes.items()}


def _extract_next_data(html: str) -> dict:
    match = _NEXT_DATA_RE.search(html)
    if not match:
        raise ValueError("__NEXT_DATA__ script tag not found in response")
    return json.loads(match.group(1))


class PolovniAutomobiliSource:
    source_code = "polovniautomobili"
    display_name = "Polovni Automobili"
    domain = "polovniautomobili.com"
    country = "RS"

    # Verified 2026-09-13 by paging a plain browser session (no scraper involved): page 751+ of
    # any search silently re-renders page 1's own listings while the URL keeps the requested
    # ?page=N — a hard, sort-independent depth cap on how far one query can be paged, not
    # proxy/IP blocking. A query with more results than this needs splitting into narrower
    # sub-queries first — see app/scraping/query_partitioning.py, which reads this attribute (and
    # calls probe_page_count below) to do that automatically for a query that needs it.
    max_crawlable_pages = 750

    def __init__(
        self,
        timeout: int = 15,
        max_pages: int = 20,
        proxy_provider: ProxyProvider | None = None,
        outcome_sink: Callable[[FetchOutcome], None] | None = None,
        fetcher: FetchStrategy | None = None,
        delay: float | None = None,
        jitter: float | None = None,
        network_error_retry_delay: float | None = None,
    ):
        """`delay`/`jitter`/`network_error_retry_delay` override app/config.py's
        scrape_request_* defaults — app/scraping/pipeline.py's run_scrape passes the current
        admin-editable values from app/scraping/rate_limit.py here. Left unset (e.g. by a direct
        caller/test), each falls back to its Settings default.
        """
        self.timeout = timeout
        self.max_pages = max_pages
        self._outcome_sink = outcome_sink
        if fetcher is not None:
            self.fetcher = fetcher
        else:
            settings = get_settings()
            self.fetcher = ProxyHttpFetcher(
                source=self.source_code,
                proxy_provider=proxy_provider if proxy_provider is not None else get_proxy_provider(),
                timeout=timeout,
                outcome_sink=outcome_sink,
                delay=delay if delay is not None else settings.scrape_request_delay_seconds,
                jitter=jitter if jitter is not None else settings.scrape_request_jitter_seconds,
                network_error_retry_delay=(
                    network_error_retry_delay
                    if network_error_retry_delay is not None
                    else settings.scrape_network_error_retry_delay_seconds
                ),
            )

    def build_search_url(self, query: SearchQuery, page: int = 1) -> str:
        # "basic" (the site's default relevance-ish order) reshuffles as ads get posted/renewed
        # while a long multi-page crawl is in flight, so the same ad can land on more than one
        # page within a single run — each re-encounter gets upserted again and inflates
        # ScrapeStats.listings_updated without a corresponding new row (see 2026-09-11/12
        # FULL_SOURCE_REFRESH runs: listings_seen/listings_updated far exceeded the real row
        # count in `listings`). renew_date_asc sorts stalest-renewed-first, so new posts and
        # renews only ever get appended at the tail (a page we haven't reached yet) instead of
        # prepended at page 1 — pages already crawled stay stable underneath us.
        params: list[tuple[str, str]] = [("page", str(page)), ("sort", "renew_date_asc")]
        if query.make:
            params.append(("brand", query.make))
        for model in query.models or []:
            params.append(("model[]", model))
        # camelCase, not snake_case: verified live 2026-09-14 that priceFrom/priceTo etc. and
        # price_from/price_to both apply the filter (same pageCount either way), but only the
        # camelCase form actually pages past page 1 — with the snake_case names every page from
        # 2 on silently re-serves page 1's own results, the same failure mode as
        # max_crawlable_pages above but starting at page 2 instead of page 751. This affects any
        # filtered crawl, not just query_partitioning's price/year brackets — a SAVED_SEARCH or
        # SEARCH job filtering on any of these previously only ever saw its first page.
        if query.price_min is not None:
            params.append(("priceFrom", str(query.price_min)))
        if query.price_max is not None:
            params.append(("priceTo", str(query.price_max)))
        if query.year_min is not None:
            params.append(("yearFrom", str(query.year_min)))
        if query.year_max is not None:
            params.append(("yearTo", str(query.year_max)))
        if query.mileage_min is not None:
            params.append(("mileageFrom", str(query.mileage_min)))
        if query.mileage_max is not None:
            params.append(("mileageTo", str(query.mileage_max)))
        if query.engine_volume_min is not None:
            params.append(("engineVolumeFrom", str(query.engine_volume_min)))
        if query.engine_volume_max is not None:
            params.append(("engineVolumeTo", str(query.engine_volume_max)))
        if query.power_min is not None:
            params.append(("powerFrom", str(query.power_min)))
        if query.power_max is not None:
            params.append(("powerTo", str(query.power_max)))
        for fuel in query.fuel_types or []:
            code = _FUEL_CODE_BY_NORMALIZED.get(fuel)
            if code is not None:
                params.append(("fuel[]", str(code)))
        return f"{BASE_URL}/auto-oglasi/pretraga?{urlencode(params, doseq=True)}"

    def parse_search_page(self, html: str) -> tuple[list[SourceListing], int]:
        """Returns (listings, total_page_count) — the search page already carries enough
        structured data per result to upsert a Listing directly, no detail fetch required.
        """
        data = _extract_next_data(html)
        search_results = data["props"]["pageProps"]["searchResults"]
        # Two reasons an entry gets dropped instead of mapped: "price on request" ads have no
        # numeric price and can't be grouped/compared, and — reproduced live across several
        # 2026-09-11/12/13 crawls — some other, rarer ads are simply missing a field entirely
        # (page 591 of a renew_date_asc crawl consistently 'model'-KeyErrors; earlier runs hit
        # 'brand' on a different page). Before this filter, one such entry raised inside
        # map_search_result and took its whole page down (PAGE_SKIPPED — see
        # _iter_search_pages), losing every other listing on that page and, worse, blocking
        # mark_missing_as_removed for the entire crawl (see pipeline.run_scrape). Dropping just
        # the incomplete entries here keeps the rest of the page.
        listings = [
            map_search_result(raw)
            for raw in search_results["results"]
            if SEARCH_RESULT_REQUIRED_FIELDS.issubset(raw)
        ]
        return listings, search_results["pageCount"]

    def parse_listing(self, html: str) -> SourceListing:
        data = _extract_next_data(html)
        page_props = data["props"]["pageProps"]
        return map_product_data(page_props["productData"], canonical_path=page_props.get("canonical"))

    def _record(self, outcome: FetchOutcome) -> None:
        if self._outcome_sink is not None:
            self._outcome_sink(outcome)

    def _guard_parse(self, fn: Callable[..., _T], *args: object) -> _T:
        try:
            return fn(*args)
        except Exception as exc:  # noqa: BLE001 - classified below, not swallowed
            self._record(FetchOutcome.PARSER_ERROR)
            raise ParserError(str(exc)) from exc

    async def _fetch(self, url: str, *, force_proxy: bool = False) -> str:
        result = await self.fetcher.fetch(url, force_proxy=force_proxy)
        return raise_for_blocked(result, url)

    async def _fetch_search_page(
        self, url: str, page: int, *, force_proxy: bool = False
    ) -> tuple[list[SourceListing], int] | None:
        """One fetch+parse attempt for a search page. Returns None (rather than raising) on a
        parse failure, so `_iter_search_pages` can retry or skip the page instead of aborting the
        whole crawl — a fetch failure (FetchBlockedError, or the RuntimeError raise_for_blocked
        raises for TIMEOUT/SERVER_ERROR) still propagates normally, since those aren't
        page-specific and retrying won't help.
        """
        html = await self._fetch(url, force_proxy=force_proxy)
        try:
            return self._guard_parse(self.parse_search_page, html)
        except ParserError as exc:
            logger.warning("polovniautomobili: page %d failed to parse (%s): %s", page, url, exc)
            return None

    async def _iter_search_pages(self, query: SearchQuery) -> AsyncIterator[SourceListing]:
        # `page_count` is anchored to whatever page 1 reports and held fixed for the rest of the
        # crawl, instead of re-trusting it fresh off every page's own response. The site is
        # supposed to report the same total on every page of one search, but a 2026-09-11
        # FULL_SOURCE_REFRESH ended at page ~179 instead of the ~2992 the site actually had:
        # every fetch still classified FetchOutcome.SUCCESS (no 403/429/captcha — see
        # app/scraping/fetch_outcome.py, so proxy fallback never triggered either), just with a
        # shrunk pageCount on a later page, and `if page >= page_count: break` took that at face
        # value and ended the run early. Page 1 is the one page a human can cross-check (the "od
        # X do Y oglasa od ukupno Z" counter rendered on the page itself), so it's the one value
        # trusted as the loop bound; a later page disagreeing is logged instead of obeyed.
        page = 1
        total_page_count: int | None = None
        while page <= self.max_pages:
            if page > self.max_crawlable_pages:
                # Past this, the site just re-serves page 1's own listings under the requested
                # ?page=N (see max_crawlable_pages above) — grinding on to self.max_pages would
                # only re-upsert those same listings over and over. A query that needs pages
                # beyond here should have been split into narrower sub-queries before reaching
                # this adapter at all (app/scraping/query_partitioning.py); this is a last-resort
                # backstop for a query that wasn't.
                logger.warning(
                    "polovniautomobili: stopping at page %d — beyond the site's %d-page crawl "
                    "depth cap; this query needs splitting into narrower sub-queries to see the "
                    "rest (see app/scraping/query_partitioning.py)",
                    page,
                    self.max_crawlable_pages,
                )
                break
            url = self.build_search_url(query, page)
            result = await self._fetch_search_page(url, page)
            if result is None:
                # One retry, forced through the proxy: the first attempt already got HTTP 200 (a
                # ParserError only happens after a successful fetch, see
                # app/scraping/fetch_outcome.py) — a same-IP direct retry would just ask the exact
                # same origin the exact same question again. A different egress IP is the one
                # thing a retry can actually change, and is exactly what fetch_outcome.py's
                # BLOCK_LIKE-only proxy escalation misses for this case: the response looked like
                # a plain success (200, parseable-looking body), just not one we could use.
                result = await self._fetch_search_page(url, page, force_proxy=True)
            if result is None:
                logger.warning("polovniautomobili: page %d skipped after two failed parse attempts (%s)", page, url)
                self._record(FetchOutcome.PAGE_SKIPPED)
                page += 1
                continue
            listings, page_count = result
            if total_page_count is None:
                total_page_count = page_count
            elif page_count != total_page_count:
                logger.warning(
                    "polovniautomobili: page %d reports pageCount=%d, page 1 reported %d (%s) — "
                    "using page 1's count",
                    page,
                    page_count,
                    total_page_count,
                    url,
                )
            for listing in listings:
                yield listing
            if page >= total_page_count:
                break
            page += 1

    async def probe_page_count(self, query: SearchQuery) -> int:
        """Total page count for `query` without crawling it — one page-1 fetch (retried once via
        proxy on a parse failure, same as _iter_search_pages above). Used by
        app/scraping/query_partitioning.py to size a bracket before committing to crawling it.
        """
        url = self.build_search_url(query, page=1)
        result = await self._fetch_search_page(url, page=1)
        if result is None:
            result = await self._fetch_search_page(url, page=1, force_proxy=True)
        if result is None:
            raise ParserError(f"could not determine page count for {url}")
        _listings, page_count = result
        return page_count

    async def search(self, query: SearchQuery) -> AsyncIterator[SourceListingRef]:
        async for listing in self._iter_search_pages(query):
            yield SourceListingRef(external_id=listing.external_id, url=listing.canonical_url)

    async def search_with_data(self, query: SearchQuery) -> AsyncIterator[SourceListing]:
        """Convenience for the scrape pipeline: search results already carry normalized listing
        data, so we can upsert directly from them without a per-listing detail fetch.
        """
        async for listing in self._iter_search_pages(query):
            yield listing

    async def fetch_listing(self, ref: SourceListingRef) -> SourceListing:
        html = await self._fetch(ref.url)
        return self._guard_parse(self.parse_listing, html)
