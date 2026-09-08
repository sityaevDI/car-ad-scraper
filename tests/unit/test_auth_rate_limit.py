from app.auth.rate_limit import RateLimiter


async def test_allowed_up_to_limit(redis):
    limiter = RateLimiter(redis)
    key = "test:limit"
    for _ in range(3):
        assert await limiter.hit(key, limit=3, window_seconds=60) is True


async def test_blocked_after_limit_exceeded(redis):
    limiter = RateLimiter(redis)
    key = "test:limit"
    for _ in range(3):
        await limiter.hit(key, limit=3, window_seconds=60)
    assert await limiter.hit(key, limit=3, window_seconds=60) is False


async def test_reset_clears_the_counter(redis):
    limiter = RateLimiter(redis)
    key = "test:limit"
    for _ in range(3):
        await limiter.hit(key, limit=3, window_seconds=60)
    await limiter.reset(key)
    assert await limiter.hit(key, limit=3, window_seconds=60) is True


async def test_ttl_set_on_first_hit(redis):
    limiter = RateLimiter(redis)
    key = "test:limit"
    await limiter.hit(key, limit=5, window_seconds=60)
    ttl = await redis.ttl(key)
    assert 0 < ttl <= 60
