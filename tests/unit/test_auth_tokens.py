import hashlib

from app.auth.tokens import OneTimeTokenStore, generate_token


def test_generate_token_is_unique():
    assert generate_token() != generate_token()


async def test_issue_then_consume_roundtrip(redis):
    store = OneTimeTokenStore(redis, "test_ns", ttl_seconds=60)
    token = await store.issue("user-123")
    assert await store.consume(token) == "user-123"


async def test_consume_is_single_use(redis):
    store = OneTimeTokenStore(redis, "test_ns", ttl_seconds=60)
    token = await store.issue("user-123")
    await store.consume(token)
    assert await store.consume(token) is None


async def test_consume_unknown_token_returns_none(redis):
    store = OneTimeTokenStore(redis, "test_ns", ttl_seconds=60)
    assert await store.consume("never-issued") is None


async def test_issued_token_has_ttl(redis):
    store = OneTimeTokenStore(redis, "test_ns", ttl_seconds=60)
    token = await store.issue("user-123")
    key = f"test_ns:{hashlib.sha256(token.encode()).hexdigest()}"
    ttl = await redis.ttl(key)
    assert 0 < ttl <= 60
