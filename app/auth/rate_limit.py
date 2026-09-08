from redis.asyncio import Redis


class RateLimiter:
    """Fixed-window counter. `hit` both records the attempt and reports whether it's still
    within the limit — callers don't need a separate check-then-increment step.
    """

    def __init__(self, redis: Redis):
        self._redis = redis

    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, window_seconds)
        return count <= limit

    async def reset(self, key: str) -> None:
        await self._redis.delete(key)
