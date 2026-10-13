import re
from pathlib import Path

import pytest
import requests

from app.scraping.fetch_outcome import FetchBlockedError, FetchOutcome, ParserError
from app.scraping.proxy import FetchError, FetchMetrics, ProxyEndpoint
from app.sources.base import SourceListing, SourceListingRef
from app.sources.polovniautomobili.adapter import PolovniAutomobiliSource

FIXTURES = Path(__file__).parent.parent / "fixtures" / "polovniautomobili"


def _fixture_search_form_options() -> dict:
    """The site's own filter option lists (`value` is what ?<name>[]= takes) from the search page."""
    from app.sources.polovniautomobili.adapter import _extract_next_data

    html = (FIXTURES / "search_page_01.html").read_text(encoding="utf-8")
    return _extract_next_data(html)["props"]["pageProps"]["searchFormOptions"]

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
    assert all(
        x.fuel_type
        in {
            "diesel",
            "petrol",
            "hybrid",
            "hybrid_petrol",
            "hybrid_diesel",
            "plugin_hybrid",
            "electric",
            "lpg",
            "cng",
            None,
        }
        for x in listings
    )
    assert all(x.transmission in {"automatic", "manual", None} for x in listings)
    assert first.image_url and first.image_url.startswith("https://cdn.polovniautomobili.com/")
    # seats is reliably present on every search-result entry (unlike interior_material/
    # air_condition — see mapper.py's docstring), so it's extracted here directly.
    assert first.seats == "5"
    assert all(x.seats is None or re.fullmatch(r"\d+", x.seats) for x in listings)


def test_parse_listing_extracts_full_detail():
    html = (FIXTURES / "listing_01.html").read_text(encoding="utf-8")
    adapter = PolovniAutomobiliSource()

    listing = adapter.parse_listing(html)

    assert listing.make == "Škoda"
    assert listing.model == "Octavia"
    assert listing.fuel_type == "diesel"
    assert listing.drive_type == "front"
    assert listing.engine_volume_cc == 1968
    assert listing.mileage_km == 114_000
    assert listing.canonical_url == (
        "https://www.polovniautomobili.com/auto-oglasi/30136732/skoda-octavia-20tdi-sportline"
    )
    # Full raw payload (safety/equipment/etc.) preserved for the snapshot history
    assert "safety" in listing.raw
    assert "equipment" in listing.raw
    assert listing.image_url == "https://cdn.polovniautomobili.com/user-images/thumbs/3013/30136732/0d3bcb74b14a.jpg"
    # equipment is translated to normalized slugs for filtering (see mapper._EQUIPMENT_NORMALIZED)
    assert "bluetooth" in listing.equipment
    assert "apple_carplay" in listing.equipment
    assert "adaptive_cruise_control" in listing.equipment
    assert all(re.fullmatch(r"[a-z0-9_]+", item) for item in listing.equipment)  # nothing left untranslated
    # interior_material is translated too (see mapper._INTERIOR_MATERIAL_NORMALIZED) — this
    # fixture's raw productData.interiorMaterial is "Štof"
    assert listing.interior_material == "cloth"
    # air_condition is translated too (see mapper._AIR_CONDITION_NORMALIZED) — this fixture's raw
    # productData.airCondition is "Automatska klima"
    assert listing.air_condition == "automatic"
    # seats is parsed from the same "N sedišta" display string as the search page (raw
    # productData.seats is "5 sedišta")
    assert listing.seats == "5"


def test_parse_search_page_drops_entries_missing_a_required_field():
    """Reproduced live across several 2026-09-11/12/13 FULL_SOURCE_REFRESH runs: some ad in the
    site's own search results is missing 'brand' or 'model' entirely (not just blank) — before
    this filter, that raised inside map_search_result and took its *whole page* down
    (PAGE_SKIPPED), losing every other listing on the page and blocking mark_missing_as_removed
    for the entire crawl (see pipeline.run_scrape). One bad entry must only drop itself.
    """
    import json

    good = {
        "id": 1, "title": "Skoda Octavia", "brand": "Škoda", "model": "Octavia", "year": 2019,
        "mileage": 100_000, "price": 10_000,
    }
    missing_model = {k: v for k, v in good.items() if k != "model"} | {"id": 2}
    html = (
        '<html><body><script id="__NEXT_DATA__">'
        + json.dumps(
            {
                "props": {
                    "pageProps": {
                        "searchResults": {"results": [good, missing_model], "pageCount": 3},
                    }
                }
            }
        )
        + "</script></body></html>"
    )
    adapter = PolovniAutomobiliSource()

    listings, page_count = adapter.parse_search_page(html)

    assert page_count == 3
    assert len(listings) == 1
    assert listings[0].external_id == "1"


def test_parse_search_page_does_not_include_equipment():
    html = (FIXTURES / "search_page_01.html").read_text(encoding="utf-8")
    adapter = PolovniAutomobiliSource()

    listings, _ = adapter.parse_search_page(html)

    # The search/results page JSON simply doesn't carry `equipment` — see mapper.py's docstring.
    assert all(listing.equipment == [] for listing in listings)


def test_parse_search_page_does_not_include_interior_material():
    html = (FIXTURES / "search_page_01.html").read_text(encoding="utf-8")
    adapter = PolovniAutomobiliSource()

    listings, _ = adapter.parse_search_page(html)

    # map_search_result doesn't read `interiorMaterial` — the search/results page only ever
    # carries it (as a prefixed display string, not the clean value) inside a premium listing's
    # `featuredInfo`, not as a plain per-listing field like fuel/chassis/gearBox. See mapper.py.
    assert all(listing.interior_material is None for listing in listings)


def test_parse_search_page_does_not_include_air_condition():
    html = (FIXTURES / "search_page_01.html").read_text(encoding="utf-8")
    adapter = PolovniAutomobiliSource()

    listings, _ = adapter.parse_search_page(html)

    # map_search_result doesn't read `airCondition` — the search/results page doesn't carry it at
    # all, not even unreliably (unlike interior_material). See mapper.py.
    assert all(listing.air_condition is None for listing in listings)


def test_fetcher_is_configured_from_settings():
    from app.config import get_settings

    adapter = PolovniAutomobiliSource()
    settings = get_settings()

    assert adapter.fetcher._pacer.delay == settings.scrape_request_delay_seconds
    assert adapter.fetcher._pacer.jitter == settings.scrape_request_jitter_seconds
    assert adapter.fetcher.network_error_retry_delay == settings.scrape_network_error_retry_delay_seconds


def test_build_search_url_includes_filters():
    from app.search.query import SearchQuery

    adapter = PolovniAutomobiliSource()
    url = adapter.build_search_url(
        SearchQuery(make="Skoda", models=["Octavia"], price_max=15000, year_min=2018), page=2
    )

    assert "page=2" in url
    assert "brand=Skoda" in url
    assert "model%5B%5D=Octavia" in url
    assert "priceTo=15000" in url
    assert "yearFrom=2018" in url


def test_build_search_url_uses_camel_case_for_every_range_filter():
    """Verified live 2026-09-14: the site applies price_from/mileage_from/etc. (snake_case) as a
    filter just fine, but only paginates correctly past page 1 with the camelCase names it
    actually expects (priceFrom, mileageFrom, ...) — snake_case silently re-serves page 1's own
    results on every later page. One bad param name per filter, so cover all five here.
    """
    from app.search.query import SearchQuery

    adapter = PolovniAutomobiliSource()
    url = adapter.build_search_url(
        SearchQuery(
            price_min=1000,
            price_max=5000,
            year_min=2015,
            year_max=2020,
            mileage_min=10_000,
            mileage_max=50_000,
            engine_volume_min=1000,
            engine_volume_max=2000,
            power_min=50,
            power_max=150,
        )
    )

    for expected in (
        "priceFrom=1000", "priceTo=5000",
        "yearFrom=2015", "yearTo=2020",
        "mileageFrom=10000", "mileageTo=50000",
        "engineVolumeFrom=1000", "engineVolumeTo=2000",
        "powerFrom=50", "powerTo=150",
    ):
        assert expected in url
    for unexpected in (
        "price_from", "price_to", "year_from", "year_to",
        "mileage_from", "mileage_to", "engine_volume_from", "engine_volume_to",
        "power_from", "power_to",
    ):
        assert unexpected not in url


def test_build_search_url_maps_fuel_types_to_site_codes():
    """The site splits "hybrid" into several distinct facets (see mapper.py's
    _FUEL_TYPE_NORMALIZED) — a plain "Hibridni pogon" tag (legacy numeric code 2308) is a much
    smaller, separate category from "Hibridni pogon (benzin)"/"(dizel)"/"Plug-in hibrid" (the
    site's own camelCase facet values, no legacy numeric code). Each normalized fuel_types entry
    must round-trip to the right fuel[] value, not just the generic one.
    """
    from app.search.query import SearchQuery

    adapter = PolovniAutomobiliSource()
    url = adapter.build_search_url(
        SearchQuery(fuel_types=["hybrid", "hybrid_petrol", "hybrid_diesel", "plugin_hybrid"])
    )

    assert "fuel%5B%5D=2308" in url
    assert "fuel%5B%5D=hybridGasoline" in url
    assert "fuel%5B%5D=hybridDiesel" in url
    assert "fuel%5B%5D=plugInHybrid" in url


def test_build_search_url_maps_drive_and_body_types_to_site_facets():
    """Verified live 2026-10-10: ?drive[]=4x4&chassis[]=sedan&chassis[]=caravan narrows BMW from
    297 result pages to 39. Without them a "BMW wagon/sedan AWD" saved search crawled plain
    `brand=BMW`. The normalized "awd"/"wagon" differ from the site's own facet values (4x4/caravan).
    """
    from app.search.query import SearchQuery

    adapter = PolovniAutomobiliSource()
    url = adapter.build_search_url(SearchQuery(make="BMW", body_types=["wagon", "sedan"], drive_types=["awd"]))

    assert "brand=BMW" in url
    assert "drive%5B%5D=4x4" in url
    assert "chassis%5B%5D=caravan" in url
    assert "chassis%5B%5D=sedan" in url


def test_build_search_url_maps_the_remaining_facet_filters():
    """Verified live 2026-10-12: gearBox[]/interiorMaterial[]/airCondition[]/seats[] each narrow the
    result list. Our "manual" is three of the site's gearbox facets.
    """
    from app.search.query import SearchQuery

    url = PolovniAutomobiliSource().build_search_url(
        SearchQuery(
            transmissions=["manual"],
            interior_materials=["combined_leather", "velour"],
            air_conditions=["automatic"],
            seats=["5"],
        )
    )

    for facet in ("manual4Gears", "manual5Gears", "manual6Gears"):
        assert f"gearBox%5B%5D={facet}" in url
    assert "interiorMaterial%5B%5D=combinedLeather" in url
    assert "interiorMaterial%5B%5D=velor" in url
    assert "airCondition%5B%5D=automatic" in url
    assert "seats%5B%5D=5" in url


def test_build_search_url_sends_equipment_as_boolean_params_not_an_array():
    """The site ignores equipment[]=... and takes one `<facet>=true` param per option (verified
    live 2026-10-12: panoramicRoof=true -> 35 BMW pages, heatedSeats=true -> 119, both -> 30).
    """
    from app.search.query import SearchQuery

    url = PolovniAutomobiliSource().build_search_url(SearchQuery(equipment=["panoramic_roof", "heated_seats"]))

    assert "panoramicRoof=true" in url
    assert "heatedSeats=true" in url
    assert "equipment" not in url


def test_build_search_url_skips_values_the_site_has_no_facet_for():
    """A value without a facet leaves the filter off (a wider crawl; matching.py re-checks the
    full saved-search query) rather than sending something the site would ignore or choke on.
    """
    from app.search.query import SearchQuery

    url = PolovniAutomobiliSource().build_search_url(
        SearchQuery(drive_types=["hovercraft"], equipment=["flux_capacitor"], seats=["12"])
    )

    assert "drive" not in url
    assert "flux" not in url
    assert "seats" not in url


def test_build_search_url_sorts_stalest_first_by_default_and_newest_first_on_request():
    """Stalest-first keeps a long full crawl stable underneath itself; a short, capped crawl (a
    saved-search refresh) has to read the newest pages instead — verified live 2026-10-12 that on
    a 38-page search, page 1 stalest-first was a month old and the newest ads were on page 38.
    """
    from app.search.query import SearchQuery

    query = SearchQuery(make="BMW")

    assert "sort=renew_date_asc" in PolovniAutomobiliSource().build_search_url(query)
    assert "sort=renew_date_desc" in PolovniAutomobiliSource(newest_first=True).build_search_url(query)


def test_facet_tables_only_use_values_the_site_itself_offers_and_cover_every_normalized_value():
    """Guards both directions against drifting: a typo'd facet value (site ignores it, filter
    silently lost) and a normalized value the mapper can produce but no facet exists for (filter
    silently lost for that value). The site's option lists are in the search-page fixture.
    """
    from app.sources.polovniautomobili import adapter, mapper

    options = _fixture_search_form_options()

    def site_values(group: str) -> set[str]:
        return {option["value"] for option in options[group]}

    def used(table: dict) -> set[str]:
        return {facet for facets in table.values() for facet in ((facets,) if isinstance(facets, str) else facets)}

    assert used(adapter._DRIVE_FACET_BY_NORMALIZED) == site_values("drive")
    assert used(adapter._CHASSIS_FACET_BY_NORMALIZED) == site_values("chassis")
    assert used(adapter._GEARBOX_FACET_BY_NORMALIZED) == site_values("gearBox")
    assert used(adapter._INTERIOR_MATERIAL_FACET_BY_NORMALIZED) == site_values("interiorMaterial")
    assert used(adapter._AIR_CONDITION_FACET_BY_NORMALIZED) == site_values("airCondition")
    assert used(adapter._SEATS_FACET_BY_NORMALIZED) == site_values("seats")
    assert used(adapter._EQUIPMENT_FACET_BY_NORMALIZED) <= site_values("equipment")

    assert set(adapter._DRIVE_FACET_BY_NORMALIZED) == set(mapper._DRIVE_TYPE_NORMALIZED.values())
    assert set(adapter._CHASSIS_FACET_BY_NORMALIZED) == set(mapper._BODY_TYPE_NORMALIZED.values())
    assert set(adapter._INTERIOR_MATERIAL_FACET_BY_NORMALIZED) == set(mapper._INTERIOR_MATERIAL_NORMALIZED.values())
    assert set(adapter._AIR_CONDITION_FACET_BY_NORMALIZED) == set(mapper._AIR_CONDITION_NORMALIZED.values())
    assert set(adapter._EQUIPMENT_FACET_BY_NORMALIZED) == set(mapper._EQUIPMENT_NORMALIZED.values())


async def test_fetch_direct_success_never_touches_proxy(monkeypatch):
    proxy_provider = FakeProxyProvider()
    adapter = PolovniAutomobiliSource(proxy_provider=proxy_provider)

    monkeypatch.setattr(adapter.fetcher.session, "get", lambda *a, **kw: _response(200, "direct ok"))

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

    monkeypatch.setattr(adapter.fetcher.session, "get", fake_get)

    text = await adapter._fetch("https://example.com/search")

    assert text == "via proxy"
    assert len(proxy_provider.successes) == 1
    assert proxy_provider.failures == []


async def test_fetch_raises_when_both_direct_and_proxy_are_blocked(monkeypatch):
    proxy_provider = FakeProxyProvider()
    adapter = PolovniAutomobiliSource(proxy_provider=proxy_provider)

    monkeypatch.setattr(adapter.fetcher.session, "get", lambda *a, **kw: _response(403, "blocked"))

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

    monkeypatch.setattr(adapter.fetcher.session, "get", lambda *a, **kw: _response(503, "down"))

    with pytest.raises(RuntimeError):
        await adapter._fetch("https://example.com/search")

    assert proxy_provider.successes == []
    assert proxy_provider.failures == []


async def test_fetch_records_outcomes_via_sink(monkeypatch):
    outcomes: list[FetchOutcome] = []
    adapter = PolovniAutomobiliSource(proxy_provider=FakeProxyProvider(), outcome_sink=outcomes.append)

    monkeypatch.setattr(adapter.fetcher.session, "get", lambda *a, **kw: _response(200, "ok"))

    await adapter._fetch("https://example.com/search")

    assert outcomes == [FetchOutcome.SUCCESS]


async def test_iter_search_pages_retries_once_then_skips_unparseable_page(monkeypatch):
    from app.search.query import SearchQuery

    outcomes: list[FetchOutcome] = []
    adapter = PolovniAutomobiliSource(proxy_provider=FakeProxyProvider(), outcome_sink=outcomes.append, max_pages=3)

    parsed_urls: list[str] = []
    force_proxy_flags: list[bool] = []

    async def fake_fetch(url: str, *, force_proxy: bool = False) -> str:
        force_proxy_flags.append(force_proxy)
        return url

    def fake_parse(html: str) -> tuple[list, int]:
        parsed_urls.append(html)
        if "page=1&" in html:
            raise ValueError("unexpected page shape")
        return [], 2

    monkeypatch.setattr(adapter, "_fetch", fake_fetch)
    monkeypatch.setattr(adapter, "parse_search_page", fake_parse)

    results = [listing async for listing in adapter.search_with_data(SearchQuery())]

    assert results == []
    # page 1: fetched and parsed twice (initial attempt + one retry), both fail and it's skipped;
    # page 2: fetched and parsed once, succeeds with page_count=2 so the crawl stops there.
    assert sum("page=1&" in url for url in parsed_urls) == 2
    assert sum("page=2&" in url for url in parsed_urls) == 1
    assert outcomes == [
        FetchOutcome.PARSER_ERROR,
        FetchOutcome.PARSER_ERROR,
        FetchOutcome.PAGE_SKIPPED,
    ]
    # The retry (page 1's second attempt) went through the proxy; nothing else did.
    assert force_proxy_flags == [False, True, False]


async def test_iter_search_pages_skips_page_on_fetch_timeout_instead_of_aborting_crawl(monkeypatch):
    """Regression test for the 2026-09-15 incident: a single search-page ReadTimeout (surfaced by
    raise_for_blocked as a bare RuntimeError, not FetchBlockedError — see fetch_strategy.py) used
    to propagate straight out of _iter_search_pages and fail the whole FULL_SOURCE_REFRESH job
    46 minutes and hundreds of successfully-crawled pages in. It must be treated like an
    unparseable page instead: retried once via proxy, then skipped so the crawl continues.
    """
    from app.search.query import SearchQuery

    outcomes: list[FetchOutcome] = []
    adapter = PolovniAutomobiliSource(proxy_provider=FakeProxyProvider(), outcome_sink=outcomes.append, max_pages=3)

    listing = SourceListing(
        external_id="1", canonical_url="https://x/1", title="x", make="Skoda", model="Octavia",
        production_year=2019, mileage_km=1, price=1, currency="EUR",
    )

    force_proxy_flags: list[bool] = []

    async def fake_fetch(url: str, *, force_proxy: bool = False) -> str:
        force_proxy_flags.append(force_proxy)
        if "page=1&" in url:
            raise RuntimeError(f"Fetch failed for {url}: timeout (ReadTimeout: read timeout=15)")
        return url

    def fake_parse(html: str) -> tuple[list, int]:
        return [listing], 2

    monkeypatch.setattr(adapter, "_fetch", fake_fetch)
    monkeypatch.setattr(adapter, "parse_search_page", fake_parse)

    results = [item async for item in adapter.search_with_data(SearchQuery())]

    # Page 1 timed out on both the direct attempt and the proxy retry and was skipped; page 2
    # fetched fine and its listing was yielded — the crawl as a whole did not raise.
    assert results == [listing]
    assert outcomes == [FetchOutcome.PAGE_SKIPPED]
    assert force_proxy_flags == [False, True, False]


async def test_iter_search_pages_recovers_if_retry_parses_successfully(monkeypatch):
    from app.search.query import SearchQuery

    outcomes: list[FetchOutcome] = []
    adapter = PolovniAutomobiliSource(proxy_provider=FakeProxyProvider(), outcome_sink=outcomes.append, max_pages=3)

    attempts: dict[str, int] = {}
    listing = SourceListing(
        external_id="1", canonical_url="https://x/1", title="x", make="Skoda", model="Octavia",
        production_year=2019, mileage_km=1, price=1, currency="EUR",
    )

    async def fake_fetch(url: str, *, force_proxy: bool = False) -> str:
        return url

    def fake_parse(html: str) -> tuple[list, int]:
        attempts[html] = attempts.get(html, 0) + 1
        if attempts[html] == 1:
            raise ValueError("transient")
        return [listing], 1

    monkeypatch.setattr(adapter, "_fetch", fake_fetch)
    monkeypatch.setattr(adapter, "parse_search_page", fake_parse)

    results = [item async for item in adapter.search_with_data(SearchQuery())]

    # The retry succeeded, so the page is NOT skipped: its listing is yielded and the loop stops
    # at page_count=1 instead of continuing — a transient failure shouldn't cost the crawl a page.
    assert results == [listing]
    assert outcomes == [FetchOutcome.PARSER_ERROR]


async def test_iter_search_pages_anchors_page_count_to_first_page(monkeypatch, caplog):
    """A later page under-reporting pageCount (see the 2026-09-11 incident: a FULL_SOURCE_REFRESH
    ended at page ~179 instead of the site's actual ~2992, entirely through this loop's own exit
    condition trusting a shrunk pageCount from a later page) must not cut the crawl short — page
    1's count is the one held fixed, and a later disagreement is only logged.
    """
    from app.search.query import SearchQuery

    adapter = PolovniAutomobiliSource(proxy_provider=FakeProxyProvider(), max_pages=5)
    listing = SourceListing(
        external_id="1", canonical_url="https://x/1", title="x", make="Skoda", model="Octavia",
        production_year=2019, mileage_km=1, price=1, currency="EUR",
    )

    async def fake_fetch(url: str, *, force_proxy: bool = False) -> str:
        return url

    def fake_parse(html: str) -> tuple[list, int]:
        # page 1 reports 4 total pages; every later page under-reports 1 (as if the site quietly
        # shrank its own count mid-crawl).
        return [listing], 4 if "page=1&" in html else 1

    monkeypatch.setattr(adapter, "_fetch", fake_fetch)
    monkeypatch.setattr(adapter, "parse_search_page", fake_parse)

    with caplog.at_level("WARNING"):
        results = [item async for item in adapter.search_with_data(SearchQuery())]

    # All 4 pages page 1 promised were crawled, not just 1 — page 1's count won.
    assert results == [listing] * 4
    assert "reports pageCount=1, page 1 reported 4" in caplog.text


async def test_iter_search_pages_stops_at_the_crawlable_depth_cap(monkeypatch, caplog):
    """Past max_crawlable_pages the site silently re-serves page 1's own listings under whatever
    ?page=N was requested (verified live 2026-09-13) — grinding on to max_pages would just
    re-upsert those same listings over and over, so the loop must stop at the cap instead.
    """
    from app.search.query import SearchQuery

    adapter = PolovniAutomobiliSource(proxy_provider=FakeProxyProvider(), max_pages=5)
    adapter.max_crawlable_pages = 2
    listing = SourceListing(
        external_id="1", canonical_url="https://x/1", title="x", make="Skoda", model="Octavia",
        production_year=2019, mileage_km=1, price=1, currency="EUR",
    )

    async def fake_fetch(url: str, *, force_proxy: bool = False) -> str:
        return url

    def fake_parse(html: str) -> tuple[list, int]:
        return [listing], 5  # page 1 reports 5 total pages — well past the cap of 2

    monkeypatch.setattr(adapter, "_fetch", fake_fetch)
    monkeypatch.setattr(adapter, "parse_search_page", fake_parse)

    with caplog.at_level("WARNING"):
        results = [item async for item in adapter.search_with_data(SearchQuery())]

    # Only pages 1 and 2 (the cap) were crawled, not all 5 pageCount promised.
    assert results == [listing] * 2
    assert "beyond the site's 2-page crawl depth cap" in caplog.text


async def test_probe_page_count_returns_page_count_without_yielding_listings(monkeypatch):
    from app.search.query import SearchQuery

    adapter = PolovniAutomobiliSource(proxy_provider=FakeProxyProvider())
    listing = SourceListing(
        external_id="1", canonical_url="https://x/1", title="x", make="Skoda", model="Octavia",
        production_year=2019, mileage_km=1, price=1, currency="EUR",
    )

    async def fake_fetch(url: str, *, force_proxy: bool = False) -> str:
        return url

    monkeypatch.setattr(adapter, "_fetch", fake_fetch)
    monkeypatch.setattr(adapter, "parse_search_page", lambda html: ([listing], 137))

    page_count = await adapter.probe_page_count(SearchQuery(price_min=1000))

    assert page_count == 137


async def test_probe_page_count_retries_via_proxy_then_raises_if_still_unparseable(monkeypatch):
    from app.search.query import SearchQuery

    adapter = PolovniAutomobiliSource(proxy_provider=FakeProxyProvider())

    force_proxy_flags: list[bool] = []

    async def fake_fetch(url: str, *, force_proxy: bool = False) -> str:
        force_proxy_flags.append(force_proxy)
        return url

    def fake_parse(html: str) -> tuple[list, int]:
        raise ValueError("unexpected page shape")

    monkeypatch.setattr(adapter, "_fetch", fake_fetch)
    monkeypatch.setattr(adapter, "parse_search_page", fake_parse)

    with pytest.raises(ParserError):
        await adapter.probe_page_count(SearchQuery())

    # One direct attempt, one forced through the proxy — same retry shape as a real crawl's pages.
    assert force_proxy_flags == [False, True]


async def test_fetch_listing_records_and_raises_parser_error_on_malformed_page(monkeypatch):
    outcomes: list[FetchOutcome] = []
    adapter = PolovniAutomobiliSource(proxy_provider=FakeProxyProvider(), outcome_sink=outcomes.append)

    monkeypatch.setattr(
        adapter.fetcher.session, "get", lambda *a, **kw: _response(200, "<html>no next data here</html>")
    )

    with pytest.raises(ParserError):
        await adapter.fetch_listing(SourceListingRef(external_id="1", url="https://example.com/listing/1"))

    assert outcomes == [FetchOutcome.SUCCESS, FetchOutcome.PARSER_ERROR]
