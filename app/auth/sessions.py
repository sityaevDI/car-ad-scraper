from typing import cast

from redis.asyncio import Redis

from app.auth.tokens import generate_token

_SESSION_PREFIX = "session"
_USER_SESSIONS_PREFIX = "user_sessions"


class SessionStore:
    """Server-side session state backing the `sid` cookie. See app/auth/__init__.py for why
    this is a Redis-backed opaque session id rather than a JWT.

    Also maintains a per-user set of active session ids (`user_sessions:{user_id}`) purely to
    support `revoke_all_for_user` on password reset — individual sessions still expire on their
    own TTL regardless of that set.
    """

    def __init__(self, redis: Redis, ttl_seconds: int):
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    def _session_key(self, session_id: str) -> str:
        return f"{_SESSION_PREFIX}:{session_id}"

    def _user_sessions_key(self, user_id: str) -> str:
        return f"{_USER_SESSIONS_PREFIX}:{user_id}"

    async def create(self, user_id: str) -> str:
        session_id = generate_token()
        user_sessions_key = self._user_sessions_key(user_id)
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(self._session_key(session_id), user_id, ex=self._ttl_seconds)
            pipe.sadd(user_sessions_key, session_id)
            pipe.expire(user_sessions_key, self._ttl_seconds)
            await pipe.execute()
        return session_id

    async def get_user_id(self, session_id: str) -> str | None:
        # get_redis() always sets decode_responses=True, so this is str at runtime; the redis-py
        # stubs just don't encode that in Redis's type.
        return cast("str | None", await self._redis.get(self._session_key(session_id)))

    async def rotate(self, old_session_id: str, user_id: str) -> str:
        new_session_id = await self.create(user_id)
        await self.delete(old_session_id, user_id)
        return new_session_id

    async def delete(self, session_id: str, user_id: str) -> None:
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.delete(self._session_key(session_id))
            pipe.srem(self._user_sessions_key(user_id), session_id)
            await pipe.execute()

    async def revoke_all_for_user(self, user_id: str) -> None:
        user_sessions_key = self._user_sessions_key(user_id)
        session_ids = await self._redis.smembers(user_sessions_key)
        if session_ids:
            await self._redis.delete(*(self._session_key(cast(str, sid)) for sid in session_ids))
        await self._redis.delete(user_sessions_key)
