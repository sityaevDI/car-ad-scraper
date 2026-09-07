from pathlib import Path

from app.sources.polovniautomobili.adapter import PolovniAutomobiliSource

FIXTURES = Path(__file__).parent.parent / "fixtures" / "polovniautomobili"


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
    assert all(l.fuel_type in {"diesel", "petrol", "hybrid", "electric", "lpg", "cng", None} for l in listings)
    assert all(l.transmission in {"automatic", "manual", None} for l in listings)


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
