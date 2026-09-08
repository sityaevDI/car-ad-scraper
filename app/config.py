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
    session_ttl_seconds: int = 60 * 60 * 24 * 14
    email_verification_ttl_seconds: int = 60 * 60 * 24
    password_reset_ttl_seconds: int = 60 * 30
    login_rate_limit_max_attempts: int = 5
    login_rate_limit_window_seconds: int = 60 * 15
    password_reset_rate_limit_max_attempts: int = 3
    password_reset_rate_limit_window_seconds: int = 60 * 60
    frontend_base_url: str = "http://localhost:3000"

    # Transactional email (verification/reset links). Unset -> falls back to a logging-only
    # sender, so local dev/CI never need real credentials. See app/auth/email.py.
    resend_api_key: str | None = None
    email_from_address: str = "onboarding@resend.dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
