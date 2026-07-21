"""
Redis async client wrapper — connection pool, health check, typed helpers.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ── Module-level singleton ───────────────────────────────────
_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Return the Redis client singleton, creating it on first call."""
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
            health_check_interval=30,
        )
    return _redis


async def close_redis() -> None:
    """Gracefully close the Redis connection pool."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def ping_redis() -> bool:
    """Health check — returns True if Redis is reachable."""
    try:
        client = await get_redis()
        return await client.ping()  # type: ignore[return-value]
    except Exception as exc:
        logger.error("Redis health check failed: %s", exc)
        return False


# ── Typed Helpers ────────────────────────────────────────────

async def get_json(key: str) -> Any | None:
    """Get a key and JSON-decode its value. Returns None if not found."""
    client = await get_redis()
    raw = await client.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


async def set_json(
    key: str,
    value: Any,
    ttl: int | None = None,
) -> None:
    """JSON-encode a value and set it in Redis with optional TTL (seconds)."""
    client = await get_redis()
    encoded = json.dumps(value)
    if ttl is not None:
        await client.setex(key, ttl, encoded)
    else:
        await client.set(key, encoded)


async def delete_key(key: str) -> int:
    """Delete a key. Returns the number of keys removed (0 or 1)."""
    client = await get_redis()
    return await client.delete(key)


async def push_to_queue(queue_name: str, payload: dict[str, Any]) -> None:
    """Push a JSON-serialised job payload into a Redis list (LPUSH)."""
    client = await get_redis()
    await client.lpush(queue_name, json.dumps(payload))


async def pop_from_queue(
    queue_name: str,
    timeout: int = 0,
) -> dict[str, Any] | None:
    """Blocking pop from a Redis list (BRPOP). Returns parsed dict or None."""
    client = await get_redis()
    result = await client.brpop(queue_name, timeout=timeout)
    if result is None:
        return None
    # result is (key, value)
    _, raw = result
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Failed to decode queue message: %s", raw)
        return None


async def incr_with_ttl(key: str, ttl: int) -> int:
    """Increment a key and set TTL if key is new. Returns new value."""
    client = await get_redis()
    pipe = client.pipeline(transaction=True)
    pipe.incr(key)
    pipe.expire(key, ttl, nx=True)
    results = await pipe.execute()
    return int(results[0])
