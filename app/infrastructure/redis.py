"""Shared Redis client. Cache/lock/queue-adjacent use only — never the source of truth for
business-critical data (that's Postgres, see app/db/).

Deliberately just a client factory: redis-py's own Redis.lock() and list commands already cover
locks and simple queues, and the actual job-queue library (ARQ/Celery/RQ) is an open decision
(see the "Decide open architecture questions" issue) — no point building a bespoke wrapper ahead
of that choice.
"""

from functools import lru_cache

from redis.asyncio import Redis

from app.config import get_settings


@lru_cache
def get_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)
