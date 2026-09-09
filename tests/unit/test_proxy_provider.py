from app.scraping.fetch_outcome import FetchOutcome
from app.scraping.proxy import FetchError, FetchMetrics, IPRoyalProxyProvider, NullProxyProvider


async def test_null_provider_never_offers_a_proxy():
    provider = NullProxyProvider()
    assert await provider.acquire("polovniautomobili") is None


async def test_iproyal_provider_builds_expected_url():
    provider = IPRoyalProxyProvider(host="geo.iproyal.com", port=12321, username="user", password="pass")
    proxy = await provider.acquire("polovniautomobili")
    assert proxy is not None
    assert proxy.url == "http://user:pass@geo.iproyal.com:12321"


async def test_iproyal_provider_rotates_session_after_failure():
    provider = IPRoyalProxyProvider(host="geo.iproyal.com", port=12321, username="user", password="pass")
    first = await provider.acquire("polovniautomobili")
    assert first is not None

    await provider.report_failure(first, FetchError(outcome=FetchOutcome.FORBIDDEN))
    second = await provider.acquire("polovniautomobili")

    assert second is not None
    assert second.url != first.url
    assert "user_session-1" in second.url


async def test_iproyal_provider_resets_rotation_on_success():
    provider = IPRoyalProxyProvider(host="geo.iproyal.com", port=12321, username="user", password="pass")
    proxy = await provider.acquire("polovniautomobili")
    assert proxy is not None

    await provider.report_failure(proxy, FetchError(outcome=FetchOutcome.FORBIDDEN))
    await provider.report_success(proxy, FetchMetrics(status_code=200))
    reset_proxy = await provider.acquire("polovniautomobili")

    assert reset_proxy is not None
    assert reset_proxy.url == proxy.url
