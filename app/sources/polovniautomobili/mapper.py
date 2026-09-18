"""Raw Polovni Automobili payload -> normalized SourceListing.

NOTE / deviation from the original PoC: `scraping/car_parser.py` and
`parsers/polovni_automobili/list_parser.py` scrape a server-rendered DOM (`classified-content`,
`uk-width-medium-1-4`, `article` tags, ...) that no longer exists on the live site — verified
against the real fixtures in `examples/list.html` / `examples/listing.html`, copied into
`tests/fixtures/polovniautomobili/`. The site is now a Next.js app that embeds a fully structured
JSON payload in a `<script id="__NEXT_DATA__">` tag (`props.pageProps.searchResults.results` on
the search page, `props.pageProps.productData` on the listing page) — matching the
"page data layer" reference in docs/adr/17_AGENT_INSTRUCTIONS.md. This mapper reads that
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
    "Hibridni pogon (benzin)": "hybrid_petrol",
    "Hibridni pogon (dizel)": "hybrid_diesel",
    "Plug-in hibrid": "plugin_hybrid",
    "Dizel": "diesel",
    "Benzin + Gas (TNG)": "lpg",
    "Električni pogon": "electric",
    "Benzin + Metan (CNG)": "cng",
}

# Keys are the raw Serbian values from `productData.interiorMaterial` (detail page only — like
# `equipment`, the search-results page doesn't reliably carry this field; see map_product_data
# and app/scraping/pipeline.py's `_enrich_with_detail`). Matches the site's own facet values
# (cloth/leather/combinedLeather/velor/other), confirmed against tests/fixtures/polovniautomobili/
# search_page_01.html's interiorMaterial filter definition.
_INTERIOR_MATERIAL_NORMALIZED = {
    "Štof": "cloth",
    "Prirodna koža": "leather",
    "Kombinovana koža": "combined_leather",
    "Velur": "velour",
    "Drugi": "other",
}

# Keys are the raw Serbian values from `productData.airCondition` (detail page only — like
# `interiorMaterial`, the search-results page doesn't carry this field at all, not even
# unreliably; see map_product_data and app/scraping/pipeline.py's `_enrich_with_detail`). Matches
# the site's own facet values, confirmed against tests/fixtures/polovniautomobili/
# search_page_01.html's airCondition filter definition.
_AIR_CONDITION_NORMALIZED = {
    "Nema klimu": "none",
    "Manuelna klima": "manual",
    "Automatska klima": "automatic",
}

# Keys are the raw Serbian values from `productData.drive` (detail page only — like
# `interiorMaterial`/`airCondition`, the search-results page doesn't reliably carry this field;
# see map_product_data and app/scraping/pipeline.py's `_enrich_with_detail`). Matches the site's
# own facet values (front/rear/4x4/4x4Reducer), confirmed against
# tests/fixtures/polovniautomobili/search_page_01.html's drive filter definition and by applying
# each as ?drive[]=<value> live on the site (2026-09-18).
_DRIVE_TYPE_NORMALIZED = {
    "Prednji": "front",
    "Zadnji": "rear",
    "4x4": "awd",
    "4x4 reduktor": "awd_low_range",
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

# The `equipment` list only appears in the listing detail page's JSON (`productData.equipment`,
# see map_product_data below) — it's a closed set of checkboxes the site itself offers when
# sellers create a listing, enumerated here from real fixtures/listings rather than derived
# programmatically. Unrecognized values pass through untranslated (see normalize_equipment)
# instead of being dropped, so a new checkbox the site adds later doesn't silently disappear.
_EQUIPMENT_NORMALIZED = {
    "Metalik boja": "metallic_paint",
    "Branici u boji auta": "body_colored_bumpers",
    "Servo volan": "power_steering",
    "Multifunkcionalni volan": "multifunction_steering_wheel",
    "Tempomat": "cruise_control",
    "Daljinsko zaključavanje": "remote_central_locking",
    "Putni računar": "trip_computer",
    "Šiber": "sunroof",
    "Panoramski krov": "panoramic_roof",
    "Tonirana stakla": "tinted_windows",
    "Električni podizači prozora": "power_windows",
    "Električni retrovizori": "power_mirrors",
    "Grejači retrovizora": "heated_mirrors",
    "Sedišta podesiva po visini": "height_adjustable_seats",
    "Elektro podesiva sedišta": "power_adjustable_seats",
    "Grejanje sedišta": "heated_seats",
    "Svetla za maglu": "fog_lights",
    "Xenon svetla": "xenon_headlights",
    "Senzori za svetla": "light_sensor",
    "Senzori za kišu": "rain_sensor",
    "Parking senzori": "parking_sensors",
    "Webasto": "auxiliary_heater",
    "Krovni nosač": "roof_rack",
    "Kuka za vuču": "tow_hook",
    "Aluminijumske felne": "alloy_wheels",
    "Navigacija": "navigation_system",
    "Bluetooth": "bluetooth",
    "Radio/Kasetofon": "radio_cassette",
    "Radio CD": "radio_cd",
    "CD changer": "cd_changer",
    "DVD/TV": "dvd_tv",
    "LED prednja svetla": "led_headlights",
    "Grejači vetrobranskog stakla": "heated_windshield",
    "LED zadnja svetla": "led_taillights",
    "Naslon za ruku": "armrest",
    "Adaptivni tempomat": "adaptive_cruise_control",
    "Automatsko parkiranje": "automatic_parking",
    "Kamera": "camera",
    "Hands free": "hands_free",
    "Adaptivna svetla": "adaptive_headlights",
    "Head-up display": "head_up_display",
    "ISOFIX sistem": "isofix",
    "Start-stop sistem": "start_stop_system",
    "Prednja noćna kamera": "front_night_vision_camera",
    "Multimedija": "multimedia_system",
    "Glasovne komande": "voice_control",
    "Masažna sedišta": "massage_seats",
    "Elektrosklopivi retrovizori": "power_folding_mirrors",
    "Memorija sedišta": "seat_memory",
    "Sportska sedišta": "sport_seats",
    "Sportsko vešanje": "sport_suspension",
    "DPF filter": "dpf_filter",
    "Dnevna svetla": "daytime_running_lights",
    "Torba za skije": "ski_bag",
    "Upravljanje na sva četiri točka": "four_wheel_steering",
    "Brisači prednjih farova": "headlight_washers",
    "360 kamera": "camera_360",
    "Fabrički ugrađeno dečije sedište": "factory_child_seat",
    "Ekran na dodir": "touchscreen",
    "Kožni volan": "leather_steering_wheel",
    "Volan u kombinaciji drvo/koža": "wood_leather_steering_wheel",
    "Grejanje volana": "heated_steering_wheel",
    "Električno zatvaranje prtljažnika": "power_trunk_closing",
    "Zavesice na zadnjim prozorima": "rear_window_curtains",
    "Privlačenje vrata pri zatvaranju": "soft_close_doors",
    "USB": "usb",
    "Paljenje bez ključa": "keyless_start",
    "Hard disk": "hard_disk",
    "Ventilacija sedišta": "ventilated_seats",
    "Vazdušno vešanje": "air_suspension",
    "Ambijentalno osvetljenje": "ambient_lighting",
    "Subwoofer": "subwoofer",
    "MP3": "mp3",
    "Digitalni radio": "digital_radio",
    "Utičnica od 12V": "power_outlet_12v",
    "Električno otvaranje prtljažnika": "power_trunk_opening",
    "Zaključavanje diferencijala": "differential_lock",
    "Otvor za skije": "ski_hatch",
    "Podešavanje volana po visini": "steering_wheel_height_adjustment",
    "Ostava sa hlađenjem": "cooled_glovebox",
    "Držači za čaše": "cup_holders",
    "Ručice za menjanje brzina na volanu": "paddle_shifters",
    "Retrovizor se obara pri rikvercu": "mirror_tilt_in_reverse",
    "Automatsko zatamnjivanje retrovizora": "auto_dimming_mirror",
    "Rezervni točak": "spare_wheel",
    "Indikator niskog pritiska u gumama": "tire_pressure_monitor",
    "Keramičke kočnice": "ceramic_brakes",
    "Elektronska ručna kočnica": "electronic_parking_brake",
    "Asistencija za kretanje na uzbrdici": "hill_start_assist",
    "AUX konekcija": "aux_input",
    "Modovi vožnje": "drive_mode_selector",
    "Postolje za bežično punjenje telefona": "wireless_phone_charging",
    "Apple CarPlay": "apple_carplay",
    "Android Auto": "android_auto",
    "Autonomna vožnja": "autonomous_driving",
    "Virtuelna tabla": "digital_instrument_cluster",
    "Matrix farovi": "matrix_headlights",
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


def normalize_interior_material(raw: str | None) -> str | None:
    if not raw:
        return None
    return _INTERIOR_MATERIAL_NORMALIZED.get(raw, raw)


def normalize_air_condition(raw: str | None) -> str | None:
    if not raw:
        return None
    return _AIR_CONDITION_NORMALIZED.get(raw, raw)


def normalize_drive_type(raw: str | None) -> str | None:
    if not raw:
        return None
    return _DRIVE_TYPE_NORMALIZED.get(raw, raw)


def normalize_seats(raw: str | None) -> str | None:
    """`raw` is a Serbian display string like "5 sedišta" (both `productData.seats` on the detail
    page and `seats` on each search-result entry use this same format) — pull out just the count,
    matching the site's own facet values (`{"value":"5","text":"5 sedišta"}` in
    tests/fixtures/polovniautomobili/search_page_01.html).
    """
    if not raw:
        return None
    match = re.match(r"\d+", raw)
    return match.group() if match else raw


def normalize_equipment(raw: list[str] | None) -> list[str]:
    if not raw:
        return []
    return [_EQUIPMENT_NORMALIZED.get(item, item) for item in raw]


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


# Fields map_search_result reads unconditionally (raw["..."], not raw.get("...")) below — a
# result entry missing any of these can't be turned into a SourceListing at all. adapter.py's
# parse_search_page checks this before calling map_search_result, so one such entry drops just
# itself instead of raising and taking its whole page down (see that filter's comment).
SEARCH_RESULT_REQUIRED_FIELDS = {"id", "title", "brand", "model", "year", "mileage", "price"}


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
        seats=normalize_seats(raw.get("seats")),
        location=raw.get("city"),
        seller_type="dealer" if raw.get("dealer") else "private",
        image_url=raw.get("imageMain"),
        raw=raw,
    )


def _primary_image_url(images: list[dict] | None) -> str | None:
    if not images:
        return None
    return min(images, key=lambda img: img.get("ordering", 0)).get("fileName")


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
        seats=normalize_seats(raw.get("seats")),
        location=raw.get("owner", {}).get("city"),
        seller_type="dealer" if "ROLE_DEALER" in raw.get("owner", {}).get("roles", []) else "private",
        image_url=_primary_image_url(raw.get("images")),
        equipment=normalize_equipment(raw.get("equipment")),
        interior_material=normalize_interior_material(raw.get("interiorMaterial")),
        air_condition=normalize_air_condition(raw.get("airCondition")),
        drive_type=normalize_drive_type(raw.get("drive")),
        raw=raw,
    )
