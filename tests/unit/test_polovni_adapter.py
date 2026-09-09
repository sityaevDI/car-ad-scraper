from pathlib import Path

import pytest
import requests

from app.scraping.fetch_outcome import FetchBlockedError, FetchOutcome
from app.scraping.proxy import FetchError, FetchMetrics, ProxyEndpoint
from app.sources.polovniautomobili.adapter import PolovniAutomobiliSource

FIXTURES = Path(__file__).parent.parent / "fixtures" / "polovniautomobili"

_PROXY = ProxyEndpoint(url="http://user:pass@geo.iproyal.com:12321")


def _response(status_code: int, text: str = "ok") -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response._content = text.encode("utf-8")
    return response


class FakeProxyProvider:
    def __init__(self):
        self.successes: list[tuple[ProxyEndpoint, FetchMetrics]] = []
        self.failures: list[tuple[ProxyEndpoint, FetchError]] = []

    async def acquire(self, source: str) -> ProxyEndpoint | None:
        return _PROXY

    async def report_success(self, proxy: ProxyEndpoint, metrics: FetchMetrics) -> None:
        self.successes.append((proxy, metrics))

    async def report_failure(self, proxy: ProxyEndpoint, error: FetchError) -> None:
        self.failures.append((proxy, error))


def test_parse_search_page_extracts_normalized_listings():
    html = (FIXTURES / "search_page_01.html").read_text(encoding="utf-8")
    adapter = PolovniAutomobiliSource()

    listings, page_count = adapter.parse_search_page(html)

    assert page_count > 1
    # One result on this fixture page is a "price on request" ad with no numeric price and is
    # deliberately dropped (see adapter.parse_search_page).
    assert len(listings) == 24
    first = listings[0]
    assert first.make == "Škoda"
    assert first.external_id
    assert first.price > 0
    assert first.production_year > 1990
    assert first.canonical_url.startswith("https://www.polovniautomobili.com/auto-oglasi/")
    # fuel/transmission/body normalized to the mapper's canonical vocabulary, not raw Serbian text
    assert all(x.fuel_type in {"diesel", "petrol", "hybrid", "electric", "lpg", "cng", None} for x in listings)
    assert all(x.transmission in {"automatic", "manual", None} for x in listings)
    assert first.image_url and first.image_url.startswith("https://cdn.polovniautomobili.com/")


def test_parse_listing_extracts_full_detail():
    html = (FIXTURES / "listing_01.html").read_text(encoding="utf-8")
    adapter = PolovniAutomobiliSource()

    listing = adapter.parse_listing(html)

    assert listing.make == "Škoda"
    assert listing.model == "Octavia"
    assert listing.fuel_type == "diesel"
    assert listing.engine_volume_cc == 1968
    assert listing.mileage_km == 114_000
    assert listing.canonical_url == (
        "https://www.polovniautomobili.com/auto-oglasi/30136732/skoda-octavia-20tdi-sportline"
    )
    # Full raw payload (safety/equipment/etc.) preserved for the snapshot history
    assert "safety" in listing.raw
    assert "equipment" in listing.raw
    assert listing.image_url == "https://cdn.polovniautomobili.com/user-images/thumbs/3013/30136732/0d3bcb74b14a.jpg"


def test_build_search_url_includes_filters():
    from app.search.query import SearchQuery

    adapter = PolovniAutomobiliSource()
    url = adapter.build_search_url(
        SearchQuery(make="Skoda", models=["Octavia"], price_max=15000, year_min=2018), page=2
    )

    assert "page=2" in url
    assert "brand=Skoda" in url
    assert "model%5B%5D=Octavia" in url
    assert "price_to=15000" in url
    assert "year_from=2018" in url


async def test_fetch_direct_success_never_touches_proxy(monkeypatch):
    proxy_provider = FakeProxyProvider()
    adapter = PolovniAutomobiliSource(proxy_provider=proxy_provider)

    monkeypatch.setattr(adapter.session, "get", lambda *a, **kw: _response(200, "direct ok"))

    text = await adapter._fetch("https://example.com/search")

    assert text == "direct ok"
    assert proxy_provider.successes == []
    assert proxy_provider.failures == []


async def test_fetch_falls_back_to_proxy_when_blocked(monkeypatch):
    proxy_provider = FakeProxyProvider()
    adapter = PolovniAutomobiliSource(proxy_provider=proxy_provider)

    def fake_get(url, timeout, headers, proxies=None):
        if proxies is None:
            return _response(403, "blocked")
        return _response(200, "via proxy")

    monkeypatch.setattr(adapter.session, "get", fake_get)

    text = await adapter._fetch("https://example.com/search")

    assert text == "via proxy"
    assert len(proxy_provider.successes) == 1
    assert proxy_provider.failures == []


async def test_fetch_raises_when_both_direct_and_proxy_are_blocked(monkeypatch):
    proxy_provider = FakeProxyProvider()
    adapter = PolovniAutomobiliSource(proxy_provider=proxy_provider)

    monkeypatch.setattr(adapter.session, "get", lambda *a, **kw: _response(403, "blocked"))

    with pytest.raises(FetchBlockedError) as exc_info:
        await adapter._fetch("https://example.com/search")

    assert exc_info.value.outcome == FetchOutcome.FORBIDDEN
    assert proxy_provider.successes == []
    assert len(proxy_provider.failures) == 1


async def test_fetch_does_not_try_proxy_on_server_error(monkeypatch):
    """A 5xx or timeout won't be fixed by a proxy, and every proxied request burns the account's
    limited residential-proxy quota — those outcomes must be re-raised without a proxy attempt.
    """
    proxy_provider = FakeProxyProvider()
    adapter = PolovniAutomobiliSource(proxy_provider=proxy_provider)

    monkeypatch.setattr(adapter.session, "get", lambda *a, **kw: _response(503, "down"))

    with pytest.raises(RuntimeError):
        await adapter._fetch("https://example.com/search")

    assert proxy_provider.successes == []
    assert proxy_provider.failures == []


async def test_fetch_records_outcomes_via_sink(monkeypatch):
    outcomes: list[FetchOutcome] = []
    adapter = PolovniAutomobiliSource(proxy_provider=FakeProxyProvider(), outcome_sink=outcomes.append)

    monkeypatch.setattr(adapter.session, "get", lambda *a, **kw: _response(200, "ok"))

    await adapter._fetch("https://example.com/search")

    assert outcomes == [FetchOutcome.SUCCESS]
