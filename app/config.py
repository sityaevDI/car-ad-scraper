from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/car_aggregator"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = [
        "http://localhost:63342",
        "http://0.0.0.0:8000",
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    # Auth: HttpOnly cookie + server-side Redis session (see app/auth/__init__.py).
    session_cookie_name: str = "sid"
    csrf_cookie_name: str = "csrf_token"
    csrf_header_name: str = "X-CSRF-Token"
    cookie_secure: bool = False
    # Set to a parent domain (e.g. ".carradar.rs") when the frontend and API live on different
    # subdomains, so the browser shares auth cookies between them. Unset -> host-only cookies,
    # which only work when frontend and API share the exact same hostname.
    cookie_domain: str | None = None
    session_ttl_seconds: int = 60 * 60 * 24 * 14
    email_verification_ttl_seconds: int = 60 * 60 * 24
    password_reset_ttl_seconds: int = 60 * 30
    login_rate_limit_max_attempts: int = 5
    login_rate_limit_window_seconds: int = 60 * 15
    password_reset_rate_limit_max_attempts: int = 3
    password_reset_rate_limit_window_seconds: int = 60 * 60
    frontend_base_url: str = "http://localhost:3000"

    # Stub refresh cadence for saved searches (issue #26) — real per-plan cadence
    # (SubscriptionPlan.refresh_frequency_minutes) is Phase 5 billing, not wired up yet.
    saved_search_refresh_minutes: int = 60

    # Transactional email (verification/reset links). Unset -> falls back to a logging-only
    # sender, so local dev/CI never need real credentials. See app/auth/email.py.
    resend_api_key: str | None = None
    email_from_address: str = "onboarding@resend.dev"

    # Residential proxy fallback for blocked scrape requests (see app/scraping/proxy.py). Unset ->
    # NullProxyProvider, i.e. direct-fetch-only, so local dev/CI never need real credentials.
    proxy_provider: str | None = None
    proxy_host: str | None = None
    proxy_port: int | None = None
    proxy_username: str | None = None
    proxy_password: str | None = None

    # Scrape request pacing (docs/adr/05_ANTI_BOT_PROXY.md §8) — a courtesy to the source, not an
    # anti-bot workaround. `ProxyHttpFetcher` spaces consecutive requests through one fetcher
    # instance (i.e. within one scrape job) `scrape_request_delay_seconds` ± `_jitter_seconds`
    # apart, and on a NETWORK_ERROR waits `scrape_network_error_retry_delay_seconds` to retry
    # direct once (still no proxy) before falling back to the residential proxy — a connection
    # reset right after a request that just worked is as likely a transient blip as an IP block,
    # and the direct retry is free where a proxied one burns quota.
    #
    # These three values only seed app/models/scrape_rate_limit.py's singleton row the first time
    # it's read — after that, an admin can retune pacing live from the admin panel
    # (/api/v1/scrape/rate-limit) without touching this file or redeploying. See
    # app/scraping/rate_limit.py.
    scrape_request_delay_seconds: float = 0.8
    scrape_request_jitter_seconds: float = 0.4
    scrape_network_error_retry_delay_seconds: float = 5.0

    # Market price calculation (#16/#18/#19, docs/adr/06_SEARCH_MARKET.md). Same lazy-seed pattern
    # as scrape_request_* above — these only seed app/models/market.py's singleton MarketConfig
    # row the first time it's read (see app/market/config.py); after that the DB row is the
    # source of truth and an admin can retune it live via /api/v1/market/config.
    market_min_sample_size: int = 5
    market_mileage_bucket_km: int = 20_000
    market_outlier_iqr_multiplier: float = 1.5
    # Price score (#18) 5-tier label: |deviation_pct| under the "market" band is labeled "market";
    # between the two bands is "below"/"above"; beyond the "significant" band is "significantly
    # below"/"significantly above".
    market_deviation_market_band_pct: float = 5.0
    market_deviation_significant_band_pct: float = 15.0
    # Confidence tiers (docs/adr/06_SEARCH_MARKET.md §7), keyed by filtered (post-outlier-removal)
    # sample size. Below market_min_sample_size, confidence is "insufficient" and no estimate is
    # shown at all.
    market_confidence_medium_min_sample: int = 15
    market_confidence_high_min_sample: int = 40
    # A tier is downgraded one step when the filtered price range is this wide relative to the
    # estimate — "high confidence, huge spread" would otherwise be a misleading combination.
    market_confidence_high_dispersion_ratio: float = 0.25
    # Cap on the summed equipment adjustment (see app/market/pricing.py) so one listing's option
    # list can't push its equipment-adjusted reference price absurdly far from the segment estimate.
    market_max_equipment_adjustment_pct: float = 15.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
