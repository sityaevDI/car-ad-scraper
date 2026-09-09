import pytest
import requests

from app.scraping.fetch_outcome import FetchOutcome
from app.scraping.fetch_strategy import HttpFetcher, PlaywrightFetcher, ProxyHttpFetcher
from app.scraping.proxy import FetchError, FetchMetrics, ProxyEndpoint

_PROXY = ProxyEndpoint(url="http://user:pass@geo.iproyal.com:12321")


def _response(status_code: int, text: str = "ok") -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response._content = text.encode("utf-8")
    return response


class FakeProxyProvider:
    def __init__(self, proxy: ProxyEndpoint | None = _PROXY):
        self._proxy = proxy
        self.successes: list[tuple[ProxyEndpoint, FetchMetrics]] = []
        self.failures: list[tuple[ProxyEndpoint, FetchError]] = []

    async def acquire(self, source: str) -> ProxyEndpoint | None:
        return self._proxy

    async def report_success(self, proxy: ProxyEndpoint, metrics: FetchMetrics) -> None:
        self.successes.append((proxy, metrics))

    async def report_failure(self, proxy: ProxyEndpoint, error: FetchError) -> None:
        self.failures.append((proxy, error))


async def test_http_fetcher_returns_success_result(monkeypatch):
    fetcher = HttpFetcher()
    monkeypatch.setattr(fetcher.session, "get", lambda *a, **kw: _response(200, "direct ok"))

    result = await fetcher.fetch("https://example.com")

    assert result.outcome == FetchOutcome.SUCCESS
    assert result.text == "direct ok"
    assert result.status_code == 200


async def test_http_fetcher_never_touches_a_proxy(monkeypatch):
    fetcher = HttpFetcher()
    seen_proxies = []
    monkeypatch.setattr(
        fetcher.session, "get", lambda *a, proxies=None, **kw: (seen_proxies.append(proxies), _response(200))[1]
    )

    await fetcher.fetch("https://example.com")

    assert seen_proxies == [None]


async def test_http_fetcher_records_outcome_via_sink(monkeypatch):
    outcomes: list[FetchOutcome] = []
    fetcher = HttpFetcher(outcome_sink=outcomes.append)
    monkeypatch.setattr(fetcher.session, "get", lambda *a, **kw: _response(503))

    result = await fetcher.fetch("https://example.com")

    assert result.outcome == FetchOutcome.SERVER_ERROR
    assert outcomes == [FetchOutcome.SERVER_ERROR]


async def test_proxy_http_fetcher_direct_success_never_touches_proxy(monkeypatch):
    proxy_provider = FakeProxyProvider()
    fetcher = ProxyHttpFetcher(source="polovniautomobili", proxy_provider=proxy_provider)
    monkeypatch.setattr(fetcher.session, "get", lambda *a, **kw: _response(200, "direct ok"))

    result = await fetcher.fetch("https://example.com")

    assert result.outcome == FetchOutcome.SUCCESS
    assert result.text == "direct ok"
    assert proxy_provider.successes == []
    assert proxy_provider.failures == []


async def test_proxy_http_fetcher_falls_back_to_proxy_when_blocked(monkeypatch):
    proxy_provider = FakeProxyProvider()
    fetcher = ProxyHttpFetcher(source="polovniautomobili", proxy_provider=proxy_provider)

    def fake_get(url, timeout, headers, proxies=None):
        if proxies is None:
            return _response(403, "blocked")
        return _response(200, "via proxy")

    monkeypatch.setattr(fetcher.session, "get", fake_get)

    result = await fetcher.fetch("https://example.com")

    assert result.outcome == FetchOutcome.SUCCESS
    assert result.text == "via proxy"
    assert len(proxy_provider.successes) == 1
    assert proxy_provider.failures == []


async def test_proxy_http_fetcher_reports_failure_when_both_blocked(monkeypatch):
    proxy_provider = FakeProxyProvider()
    fetcher = ProxyHttpFetcher(source="polovniautomobili", proxy_provider=proxy_provider)
    monkeypatch.setattr(fetcher.session, "get", lambda *a, **kw: _response(403, "blocked"))

    result = await fetcher.fetch("https://example.com")

    assert result.outcome == FetchOutcome.FORBIDDEN
    assert proxy_provider.successes == []
    assert len(proxy_provider.failures) == 1


async def test_proxy_http_fetcher_does_not_try_proxy_on_server_error(monkeypatch):
    proxy_provider = FakeProxyProvider()
    fetcher = ProxyHttpFetcher(source="polovniautomobili", proxy_provider=proxy_provider)
    monkeypatch.setattr(fetcher.session, "get", lambda *a, **kw: _response(503, "down"))

    result = await fetcher.fetch("https://example.com")

    assert result.outcome == FetchOutcome.SERVER_ERROR
    assert proxy_provider.successes == []
    assert proxy_provider.failures == []


async def test_proxy_http_fetcher_returns_block_outcome_when_no_proxy_configured(monkeypatch):
    proxy_provider = FakeProxyProvider(proxy=None)
    fetcher = ProxyHttpFetcher(source="polovniautomobili", proxy_provider=proxy_provider)
    monkeypatch.setattr(fetcher.session, "get", lambda *a, **kw: _response(403, "blocked"))

    result = await fetcher.fetch("https://example.com")

    assert result.outcome == FetchOutcome.FORBIDDEN


async def test_proxy_http_fetcher_records_both_attempts_via_sink(monkeypatch):
    outcomes: list[FetchOutcome] = []
    proxy_provider = FakeProxyProvider()
    fetcher = ProxyHttpFetcher(source="polovniautomobili", proxy_provider=proxy_provider, outcome_sink=outcomes.append)

    def fake_get(url, timeout, headers, proxies=None):
        if proxies is None:
            return _response(429, "rate limited")
        return _response(200, "via proxy")

    monkeypatch.setattr(fetcher.session, "get", fake_get)

    await fetcher.fetch("https://example.com")

    assert outcomes == [FetchOutcome.RATE_LIMITED, FetchOutcome.SUCCESS]


async def test_playwright_fetcher_is_not_implemented():
    fetcher = PlaywrightFetcher()

    with pytest.raises(NotImplementedError):
        await fetcher.fetch("https://example.com")
