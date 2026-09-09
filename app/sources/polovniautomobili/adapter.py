"""Polovni Automobili source adapter. See app/sources/base.py for the CarSource contract and
app/sources/polovniautomobili/mapper.py for why this parses the page's `__NEXT_DATA__` JSON
instead of the original PoC's (now-stale) CSS selectors.
"""

import asyncio
import json
import re
from collections.abc import AsyncIterator, Callable
from urllib.parse import urlencode

import requests

from app.scraping.fetch_outcome import (
    BLOCK_LIKE,
    FetchBlockedError,
    FetchOutcome,
    classify_exception,
    classify_response,
)
from app.scraping.proxy import FetchError, FetchMetrics, ProxyProvider, get_proxy_provider
from app.search.query import SearchQuery
from app.sources.base import SourceListing, SourceListingRef
from app.sources.polovniautomobili.mapper import BASE_URL, map_product_data, map_search_result, normalize_fuel_type
from scraping.translation import fuel_type_codes
from scraping.utilities import default_request_headers

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

    def __init__(
        self,
        timeout: int = 15,
        max_pages: int = 20,
        proxy_provider: ProxyProvider | None = None,
        outcome_sink: Callable[[FetchOutcome], None] | None = None,
    ):
        self.timeout = timeout
        self.max_pages = max_pages
        self.session = requests.Session()
        self.proxy_provider = proxy_provider if proxy_provider is not None else get_proxy_provider()
        self._outcome_sink = outcome_sink

    def build_search_url(self, query: SearchQuery, page: int = 1) -> str:
        params: list[tuple[str, str]] = [("page", str(page)), ("sort", "basic")]
        if query.make:
            params.append(("brand", query.make))
        for model in query.models or []:
            params.append(("model[]", model))
        if query.price_min is not None:
            params.append(("price_from", str(query.price_min)))
        if query.price_max is not None:
            params.append(("price_to", str(query.price_max)))
        if query.year_min is not None:
            params.append(("year_from", str(query.year_min)))
        if query.year_max is not None:
            params.append(("year_to", str(query.year_max)))
        if query.mileage_min is not None:
            params.append(("mileage_from", str(query.mileage_min)))
        if query.mileage_max is not None:
            params.append(("mileage_to", str(query.mileage_max)))
        if query.engine_volume_min is not None:
            params.append(("engine_volume_from", str(query.engine_volume_min)))
        if query.engine_volume_max is not None:
            params.append(("engine_volume_to", str(query.engine_volume_max)))
        if query.power_min is not None:
            params.append(("power_from", str(query.power_min)))
        if query.power_max is not None:
            params.append(("power_to", str(query.power_max)))
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
        # "Price on request" listings (no numeric price) can't be grouped/compared and are
        # dropped rather than stored with a fabricated price.
        listings = [map_search_result(raw) for raw in search_results["results"] if "price" in raw]
        return listings, search_results["pageCount"]

    def parse_listing(self, html: str) -> SourceListing:
        data = _extract_next_data(html)
        page_props = data["props"]["pageProps"]
        return map_product_data(page_props["productData"], canonical_path=page_props.get("canonical"))

    def _record(self, outcome: FetchOutcome) -> None:
        if self._outcome_sink is not None:
            self._outcome_sink(outcome)

    def _request(self, url: str, proxy_url: str | None) -> tuple[FetchOutcome, requests.Response | None]:
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        try:
            response = self.session.get(url, timeout=self.timeout, headers=default_request_headers(), proxies=proxies)
        except Exception as exc:  # noqa: BLE001 - classified below, not swallowed
            return classify_exception(exc), None
        return classify_response(response), response

    async def _fetch(self, url: str) -> str:
        """Direct-first, proxy-fallback-only-when-blocked fetch. A proxy attempt is only made
        when the direct attempt looks block-like (403/429/challenge/captcha) — a timeout or 5xx
        won't be fixed by a proxy, and every proxied request burns the account's limited
        residential-proxy quota, so those are re-raised immediately instead.
        """
        outcome, response = await asyncio.to_thread(self._request, url, None)
        self._record(outcome)
        if outcome == FetchOutcome.SUCCESS:
            assert response is not None
            return response.text
        if outcome not in BLOCK_LIKE:
            raise RuntimeError(f"Fetch failed for {url}: {outcome.value}")

        proxy = await self.proxy_provider.acquire(self.source_code)
        if proxy is None:
            raise FetchBlockedError(outcome)

        proxy_outcome, proxy_response = await asyncio.to_thread(self._request, url, proxy.url)
        self._record(proxy_outcome)
        if proxy_outcome == FetchOutcome.SUCCESS:
            assert proxy_response is not None
            await self.proxy_provider.report_success(
                proxy, FetchMetrics(status_code=proxy_response.status_code)
            )
            return proxy_response.text

        await self.proxy_provider.report_failure(proxy, FetchError(outcome=proxy_outcome))
        raise FetchBlockedError(proxy_outcome)

    async def _iter_search_pages(self, query: SearchQuery) -> AsyncIterator[SourceListing]:
        page = 1
        while page <= self.max_pages:
            url = self.build_search_url(query, page)
            html = await self._fetch(url)
            listings, page_count = self.parse_search_page(html)
            for listing in listings:
                yield listing
            if page >= page_count:
                break
            page += 1

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
        return self.parse_listing(html)
