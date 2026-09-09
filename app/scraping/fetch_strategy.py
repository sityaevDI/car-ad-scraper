"""Fetch strategy abstraction — see docs/adr/05_ANTI_BOT_PROXY.md §1, §6, §9. Centralizes how a
page's raw HTML is retrieved (direct HTTP, proxied HTTP, browser) behind one interface, so a
source adapter only ever calls `fetcher.fetch(url)` and never touches a session/headers/proxy
directly. `HttpFetcher` and `ProxyHttpFetcher` share the same low-level request helper
(`_http_request`) so User-Agent, headers, timeout and proxy wiring live in exactly one place.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import requests

from app.scraping.fetch_outcome import (
    BLOCK_LIKE,
    FetchBlockedError,
    FetchOutcome,
    classify_exception,
    classify_response,
)
from app.scraping.proxy import FetchError, FetchMetrics, ProxyProvider
from scraping.utilities import default_request_headers


@dataclass
class FetchResult:
    outcome: FetchOutcome
    text: str | None = None
    status_code: int | None = None


class FetchStrategy(Protocol):
    async def fetch(self, url: str) -> FetchResult: ...


def _http_request(
    session: requests.Session, url: str, timeout: int, proxy_url: str | None
) -> tuple[FetchOutcome, requests.Response | None]:
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    try:
        response = session.get(url, timeout=timeout, headers=default_request_headers(), proxies=proxies)
    except Exception as exc:  # noqa: BLE001 - classified below, not swallowed
        return classify_exception(exc), None
    return classify_response(response), response


def _to_result(outcome: FetchOutcome, response: requests.Response | None) -> FetchResult:
    if response is None:
        return FetchResult(outcome=outcome)
    return FetchResult(outcome=outcome, text=response.text, status_code=response.status_code)


class HttpFetcher:
    """Direct HTTP fetch — no proxy, no block-like retry. `session` persists cookies across
    requests for whoever holds this fetcher.
    """

    def __init__(self, timeout: int = 15, outcome_sink: Callable[[FetchOutcome], None] | None = None):
        self.timeout = timeout
        self.session = requests.Session()
        self._outcome_sink = outcome_sink

    async def fetch(self, url: str) -> FetchResult:
        outcome, response = await asyncio.to_thread(_http_request, self.session, url, self.timeout, None)
        if self._outcome_sink is not None:
            self._outcome_sink(outcome)
        return _to_result(outcome, response)


class ProxyHttpFetcher:
    """Direct-first, proxy-fallback-only-when-blocked (docs/adr/05_ANTI_BOT_PROXY.md §2-4). A
    proxy attempt is only made when the direct attempt looks block-like (403/429/challenge/
    captcha) — a timeout or 5xx won't be fixed by a proxy, and every proxied request burns the
    account's limited residential-proxy quota, so those outcomes are returned immediately instead.

    Ported out of what used to be `PolovniAutomobiliSource._fetch()` so any source adapter can
    reuse the same direct/proxy decision without reimplementing it.
    """

    def __init__(
        self,
        source: str,
        proxy_provider: ProxyProvider,
        timeout: int = 15,
        outcome_sink: Callable[[FetchOutcome], None] | None = None,
    ):
        self.source = source
        self.proxy_provider = proxy_provider
        self.timeout = timeout
        self.session = requests.Session()
        self._outcome_sink = outcome_sink

    def _record(self, outcome: FetchOutcome) -> None:
        if self._outcome_sink is not None:
            self._outcome_sink(outcome)

    async def fetch(self, url: str) -> FetchResult:
        outcome, response = await asyncio.to_thread(_http_request, self.session, url, self.timeout, None)
        self._record(outcome)
        if outcome == FetchOutcome.SUCCESS or outcome not in BLOCK_LIKE:
            return _to_result(outcome, response)

        proxy = await self.proxy_provider.acquire(self.source)
        if proxy is None:
            return _to_result(outcome, response)

        proxy_outcome, proxy_response = await asyncio.to_thread(
            _http_request, self.session, url, self.timeout, proxy.url
        )
        self._record(proxy_outcome)
        if proxy_outcome == FetchOutcome.SUCCESS:
            assert proxy_response is not None
            await self.proxy_provider.report_success(proxy, FetchMetrics(status_code=proxy_response.status_code))
        else:
            await self.proxy_provider.report_failure(proxy, FetchError(outcome=proxy_outcome))
        return _to_result(proxy_outcome, proxy_response)


class PlaywrightFetcher:
    """Browser-automation fetch strategy stub (docs/adr/05_ANTI_BOT_PROXY.md §6) — for pages a
    plain HTTP client can't retrieve (JS-rendered content, harder Cloudflare challenges). Not
    implemented: this exists only so `FetchStrategy` has a real third implementation and callers
    can already depend on the interface without a rewrite once actual Playwright automation lands.
    """

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    async def fetch(self, url: str) -> FetchResult:
        raise NotImplementedError(
            "PlaywrightFetcher is a stub — browser-based fetching isn't implemented yet "
            "(docs/adr/05_ANTI_BOT_PROXY.md §6)."
        )


def raise_for_blocked(result: FetchResult, url: str) -> str:
    """Turns a non-SUCCESS FetchResult into the appropriate exception for a source adapter's
    fetch loop: block-like outcomes raise FetchBlockedError (app/scraping/pipeline.py catches
    that to stop pagination gracefully and keep partial results), anything else is a hard failure.
    """
    if result.outcome == FetchOutcome.SUCCESS:
        assert result.text is not None
        return result.text
    if result.outcome in BLOCK_LIKE:
        raise FetchBlockedError(result.outcome)
    raise RuntimeError(f"Fetch failed for {url}: {result.outcome.value}")
