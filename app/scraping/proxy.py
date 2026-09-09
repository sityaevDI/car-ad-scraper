"""Residential proxy fallback — see docs/adr/05_ANTI_BOT_PROXY.md §2-4.

Deliberately a stub: no cooldown, no health-state-machine (that's the anti-bot state machine,
a separate later issue). `IPRoyalProxyProvider` just rotates its session suffix on failure so a
blocked source at least gets a different exit IP on the next attempt.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from app.config import get_settings
from app.scraping.fetch_outcome import FetchOutcome

_MAX_ROTATION = 5


@dataclass
class ProxyEndpoint:
    url: str  # e.g. "http://user_session-2:pass@geo.iproyal.com:12321"


@dataclass
class FetchMetrics:
    status_code: int | None = None
    elapsed_ms: float | None = None


@dataclass
class FetchError:
    outcome: FetchOutcome
    detail: str | None = None


class ProxyProvider(Protocol):
    async def acquire(self, source: str) -> ProxyEndpoint | None: ...

    async def report_success(self, proxy: ProxyEndpoint, metrics: FetchMetrics) -> None: ...

    async def report_failure(self, proxy: ProxyEndpoint, error: FetchError) -> None: ...


class NullProxyProvider:
    """Default when no proxy is configured — direct-fetch-only, so local dev/CI never need real
    credentials. Mirrors app/auth/email.py's LoggingEmailSender fallback pattern.
    """

    async def acquire(self, source: str) -> ProxyEndpoint | None:
        return None

    async def report_success(self, proxy: ProxyEndpoint, metrics: FetchMetrics) -> None:
        return None

    async def report_failure(self, proxy: ProxyEndpoint, error: FetchError) -> None:
        return None


class IPRoyalProxyProvider:
    """Single sticky residential proxy endpoint that rotates its session suffix after a failure.

    The exact IPRoyal session-suffix syntax (`_session-N`) is a best guess pending verification
    against real IPRoyal credentials — see the manual verification step in the implementation
    plan. If wrong, every request just keeps the same exit IP (degrades to no rotation, not a
    crash).
    """

    def __init__(self, host: str, port: int, username: str, password: str):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._rotation = 0

    def _build_username(self) -> str:
        if self._rotation == 0:
            return self._username
        return f"{self._username}_session-{self._rotation}"

    async def acquire(self, source: str) -> ProxyEndpoint | None:
        url = f"http://{self._build_username()}:{self._password}@{self._host}:{self._port}"
        return ProxyEndpoint(url=url)

    async def report_success(self, proxy: ProxyEndpoint, metrics: FetchMetrics) -> None:
        self._rotation = 0

    async def report_failure(self, proxy: ProxyEndpoint, error: FetchError) -> None:
        self._rotation = min(self._rotation + 1, _MAX_ROTATION)


@lru_cache
def get_proxy_provider() -> ProxyProvider:
    settings = get_settings()
    if not settings.proxy_host or not settings.proxy_port:
        return NullProxyProvider()
    return IPRoyalProxyProvider(
        host=settings.proxy_host,
        port=settings.proxy_port,
        username=settings.proxy_username or "",
        password=settings.proxy_password or "",
    )
