"""Raw Polovni Automobili payload -> normalized SourceListing.

NOTE / deviation from the original PoC: `scraping/car_parser.py` and
`parsers/polovni_automobili/list_parser.py` scrape a server-rendered DOM (`classified-content`,
`uk-width-medium-1-4`, `article` tags, ...) that no longer exists on the live site — verified
against the real fixtures in `examples/list.html` / `examples/listing.html`, copied into
`tests/fixtures/polovniautomobili/`. The site is now a Next.js app that embeds a fully structured
JSON payload in a `<script id="__NEXT_DATA__">` tag (`props.pageProps.searchResults.results` on
the search page, `props.pageProps.productData` on the listing page) — matching the
"page data layer" reference in agent_documents/17_AGENT_INSTRUCTIONS.md. This mapper reads that
JSON instead. The old code's *vocabulary* (Serbian field values, `scraping/translation.py` code
tables) is reused below to normalize fuel/gearbox/body values.
"""

import re
import unicodedata

from app.sources.base import SourceListing

BASE_URL = "https://www.polovniautomobili.com"

# Keys are the raw Serbian values as they appear in the source JSON — same vocabulary as the
# values of `scraping.translation.fuel_type_codes` / `body_type_codes`, kept here as a direct
# value->normalized mapping since we don't need the numeric codes for parsing (only for building
# search URLs — see adapter.py).
_FUEL_TYPE_NORMALIZED = {
    "Benzin": "petrol",
    "Hibridni pogon": "hybrid",
    "Dizel": "diesel",
    "Benzin + Gas (TNG)": "lpg",
    "Električni pogon": "electric",
    "Benzin + Metan (CNG)": "cng",
}

_BODY_TYPE_NORMALIZED = {
    "Limuzina": "sedan",
    "Karavan": "wagon",
    "Hečbek": "hatchback",
    "Džip/SUV": "suv",
    "Kupe": "coupe",
    "Kabriolet/Roadster": "convertible",
    "Pickup": "pickup",
    "Monovolumen (MiniVan)": "minivan",
}


def normalize_fuel_type(raw: str | None) -> str | None:
    if not raw:
        return None
    return _FUEL_TYPE_NORMALIZED.get(raw, raw)


def normalize_transmission(raw: str | None) -> str | None:
    if not raw:
        return None
    lowered = raw.lower()
    if "automat" in lowered:
        return "automatic"
    if "manuel" in lowered or "manual" in lowered:
        return "manual"
    return raw


def normalize_body_type(raw: str | None) -> str | None:
    if not raw:
        return None
    return _BODY_TYPE_NORMALIZED.get(raw, raw)


def slugify(text: str) -> str:
    """Matches the site's own SEO slug generation closely enough to build a working listing URL
    from search-result fields alone (validated against real anchors in the search fixture).
    """
    text = text.replace("đ", "dj").replace("Đ", "Dj")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    return text


def canonical_url_from_id_title(external_id: str, title: str) -> str:
    return f"{BASE_URL}/auto-oglasi/{external_id}/{slugify(title)}"


def map_search_result(raw: dict) -> SourceListing:
    """Map one entry of `pageProps.searchResults.results` (search/list page)."""
    external_id = str(raw["id"])
    return SourceListing(
        external_id=external_id,
        canonical_url=canonical_url_from_id_title(external_id, raw["title"]),
        title=raw["title"],
        make=raw["brand"],
        model=raw["model"],
        production_year=raw["year"],
        mileage_km=raw["mileage"],
        price=raw["price"],
        currency="EUR" if raw.get("priceCurrency") == "€" else raw.get("priceCurrency", "EUR"),
        fuel_type=normalize_fuel_type(raw.get("fuel")),
        transmission=normalize_transmission(raw.get("gearBox")),
        body_type=normalize_body_type(raw.get("chassis")),
        engine_volume_cc=raw.get("engineVolume"),
        power_hp=raw.get("horsePower"),
        location=raw.get("city"),
        seller_type="dealer" if raw.get("dealer") else "private",
        raw=raw,
    )


def map_product_data(raw: dict, canonical_path: str | None = None) -> SourceListing:
    """Map `pageProps.productData` (listing detail page)."""
    external_id = str(raw["id"])
    canonical_url = f"{BASE_URL}/{canonical_path}" if canonical_path else canonical_url_from_id_title(
        external_id, raw["title"]
    )
    return SourceListing(
        external_id=external_id,
        canonical_url=canonical_url,
        title=raw["title"],
        make=raw["brand"],
        model=raw["model"],
        production_year=raw["year"],
        mileage_km=raw["mileage"],
        price=raw["price"],
        currency="EUR" if raw.get("priceCurrency") == "€" else raw.get("priceCurrency", "EUR"),
        fuel_type=normalize_fuel_type(raw.get("fuel")),
        transmission=normalize_transmission(raw.get("gearBox")),
        body_type=normalize_body_type(raw.get("chassis")),
        engine_volume_cc=raw.get("engineVolume"),
        power_hp=raw.get("horsePower"),
        location=raw.get("owner", {}).get("city"),
        seller_type="dealer" if "ROLE_DEALER" in raw.get("owner", {}).get("roles", []) else "private",
        raw=raw,
    )
