"""Fetch strategy abstraction — see docs/adr/05_ANTI_BOT_PROXY.md §1, §6, §9. Centralizes how a
page's raw HTML is retrieved (direct HTTP, proxied HTTP, browser) behind one interface, so a
source adapter only ever calls `fetcher.fetch(url)` and never touches a session/headers/proxy
directly. `HttpFetcher` and `ProxyHttpFetcher` share the same low-level request helper
(`_http_request`) so User-Agent, headers, timeout and proxy wiring live in exactly one place.
"""

import asyncio
import random
import time
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
    # Only set for exception-classified outcomes (TIMEOUT/NETWORK_ERROR) — a response-classified
    # outcome already has status_code/text to explain itself.
    detail: str | None = None


class FetchStrategy(Protocol):
    async def fetch(self, url: str) -> FetchResult: ...


def _http_request(
    session: requests.Session, url: str, timeout: int, proxy_url: str | None
) -> tuple[FetchOutcome, requests.Response | None, str | None]:
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    try:
        response = session.get(url, timeout=timeout, headers=default_request_headers(), proxies=proxies)
    except Exception as exc:  # noqa: BLE001 - classified below, not swallowed
        outcome, detail = classify_exception(exc)
        return outcome, None, detail
    return classify_response(response), response, None


def _to_result(outcome: FetchOutcome, response: requests.Response | None, detail: str | None = None) -> FetchResult:
    if response is None:
        return FetchResult(outcome=outcome, detail=detail)
    return FetchResult(outcome=outcome, text=response.text, status_code=response.status_code)


class _RequestPacer:
    """Sleeps so consecutive requests through one fetcher instance land `delay` ± `jitter` seconds
    apart — a courtesy to the source (docs/adr/05_ANTI_BOT_PROXY.md §8), not an anti-bot
    workaround. A fetcher is built fresh per scrape job (see app/scraping/pipeline.py), so the
    first request of a job never waits; `delay=0` (the default) disables pacing entirely, which is
    what every test gets unless it opts in.
    """

    def __init__(self, delay: float = 0.0, jitter: float = 0.0):
        self.delay = delay
        self.jitter = jitter
        self._last_request_at: float | None = None

    async def wait(self) -> None:
        if self.delay > 0 and self._last_request_at is not None:
            target = self.delay + random.uniform(-self.jitter, self.jitter)
            remaining = target - (time.monotonic() - self._last_request_at)
            if remaining > 0:
                await asyncio.sleep(remaining)
        self._last_request_at = time.monotonic()


class HttpFetcher:
    """Direct HTTP fetch — no proxy, no block-like retry. `session` persists cookies across
    requests for whoever holds this fetcher.
    """

    def __init__(
        self,
        timeout: int = 15,
        outcome_sink: Callable[[FetchOutcome], None] | None = None,
        delay: float = 0.0,
        jitter: float = 0.0,
    ):
        self.timeout = timeout
        self.session = requests.Session()
        self._outcome_sink = outcome_sink
        self._pacer = _RequestPacer(delay, jitter)

    async def fetch(self, url: str) -> FetchResult:
        await self._pacer.wait()
        outcome, response, detail = await asyncio.to_thread(_http_request, self.session, url, self.timeout, None)
        if self._outcome_sink is not None:
            self._outcome_sink(outcome)
        return _to_result(outcome, response, detail)


class ProxyHttpFetcher:
    """Direct-first, proxy-fallback-only-when-worth-it (docs/adr/05_ANTI_BOT_PROXY.md §2-4, §8).

    On NETWORK_ERROR (connection refused/reset — no HTTP response at all), one direct retry is
    made after `network_error_retry_delay` seconds, still with no proxy: a connection drop right
    after a request that just worked is as plausibly a transient blip as an IP-level block, and
    the direct retry is free where a proxied one burns the account's limited residential-proxy
    quota. Only if that retry (or the very first attempt, for a block-like outcome) still looks
    block-like or is another NETWORK_ERROR does a proxy attempt happen. TIMEOUT and SERVER_ERROR
    are never retried through the proxy: those point at the origin being slow/down, which a
    different egress IP won't fix.

    Ported out of what used to be `PolovniAutomobiliSource._fetch()` so any source adapter can
    reuse the same direct/proxy decision without reimplementing it.
    """

    _PROXY_ELIGIBLE = BLOCK_LIKE | {FetchOutcome.NETWORK_ERROR}

    def __init__(
        self,
        source: str,
        proxy_provider: ProxyProvider,
        timeout: int = 15,
        outcome_sink: Callable[[FetchOutcome], None] | None = None,
        delay: float = 0.0,
        jitter: float = 0.0,
        network_error_retry_delay: float = 0.0,
    ):
        self.source = source
        self.proxy_provider = proxy_provider
        self.timeout = timeout
        self.session = requests.Session()
        self._outcome_sink = outcome_sink
        self._pacer = _RequestPacer(delay, jitter)
        self.network_error_retry_delay = network_error_retry_delay
        self.jitter = jitter

    def _record(self, outcome: FetchOutcome) -> None:
        if self._outcome_sink is not None:
            self._outcome_sink(outcome)

    async def _direct(self, url: str) -> tuple[FetchOutcome, requests.Response | None, str | None]:
        return await asyncio.to_thread(_http_request, self.session, url, self.timeout, None)

    async def fetch(self, url: str) -> FetchResult:
        await self._pacer.wait()
        outcome, response, detail = await self._direct(url)
        self._record(outcome)

        if outcome == FetchOutcome.NETWORK_ERROR and self.network_error_retry_delay > 0:
            await asyncio.sleep(self.network_error_retry_delay + random.uniform(0, self.jitter))
            outcome, response, detail = await self._direct(url)
            self._record(outcome)

        if outcome not in self._PROXY_ELIGIBLE:
            return _to_result(outcome, response, detail)

        proxy = await self.proxy_provider.acquire(self.source)
        if proxy is None:
            return _to_result(outcome, response, detail)

        proxy_outcome, proxy_response, proxy_detail = await asyncio.to_thread(
            _http_request, self.session, url, self.timeout, proxy.url
        )
        self._record(proxy_outcome)
        if proxy_outcome == FetchOutcome.SUCCESS:
            assert proxy_response is not None
            await self.proxy_provider.report_success(proxy, FetchMetrics(status_code=proxy_response.status_code))
        else:
            await self.proxy_provider.report_failure(proxy, FetchError(outcome=proxy_outcome))
        return _to_result(proxy_outcome, proxy_response, proxy_detail)


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
    suffix = f" ({result.detail})" if result.detail else ""
    raise RuntimeError(f"Fetch failed for {url}: {result.outcome.value}{suffix}")
