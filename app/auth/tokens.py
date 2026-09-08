import hashlib
import secrets
from typing import cast

from redis.asyncio import Redis


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class OneTimeTokenStore:
    """Single-use, short-TTL tokens for email verification / password reset.

    Only the token's hash is stored in Redis, so a Redis dump/KEYS scan doesn't leak a usable
    token — the raw token exists only in the link sent to the user.
    """

    def __init__(self, redis: Redis, namespace: str, ttl_seconds: int):
        self._redis = redis
        self._namespace = namespace
        self._ttl_seconds = ttl_seconds

    def _key(self, token: str) -> str:
        return f"{self._namespace}:{_hash_token(token)}"

    async def issue(self, subject_id: str) -> str:
        token = generate_token()
        await self._redis.set(self._key(token), subject_id, ex=self._ttl_seconds)
        return token

    async def consume(self, token: str) -> str | None:
        key = self._key(token)
        subject_id = await self._redis.get(key)
        if subject_id is None:
            return None
        await self._redis.delete(key)
        # get_redis() always sets decode_responses=True, so this is str at runtime; the redis-py
        # stubs just don't encode that in Redis's type.
        return cast(str, subject_id)
