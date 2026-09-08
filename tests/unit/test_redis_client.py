from app.infrastructure.redis import get_redis


def test_get_redis_uses_configured_url():
    kwargs = get_redis().connection_pool.connection_kwargs
    assert kwargs["host"] == "localhost"
    assert kwargs["port"] == 6379
    assert kwargs["db"] == 0


def test_get_redis_is_cached():
    assert get_redis() is get_redis()
