"""
Rate limiting middleware — token-bucket algorithm backed by Redis.
"""

from __future__ import annotations

import logging

from hydrogram import Client, filters
from hydrogram.types import Message

from app.core.config import get_settings
from app.core.redis import incr_with_ttl

logger = logging.getLogger(__name__)


async def _rate_limit_check(
    flt: filters.Filter,
    client: Client,
    message: Message,
) -> bool:
    """Custom filter that blocks messages from users exceeding the rate limit.

    Uses Redis INCR with TTL to track request counts per user.
    Returns True if the user is WITHIN limits (message should proceed).
    Returns False if the user EXCEEDS limits (message should be dropped).
    """
    if not message.from_user:
        return True

    settings = get_settings()
    user_id = message.from_user.id
    key = f"ratelimit:{user_id}"

    try:
        count = await incr_with_ttl(key, settings.RATE_LIMIT_WINDOW_SECONDS)

        if count > settings.RATE_LIMIT_REQUESTS:
            if count == settings.RATE_LIMIT_REQUESTS + 1:
                # Notify once when limit is first exceeded
                await message.reply(
                    "⚠️ **Rate limit exceeded.** "
                    f"Please wait {settings.RATE_LIMIT_WINDOW_SECONDS}s."
                )
                logger.warning("Rate limit exceeded for user %d", user_id)
            return False

        return True

    except Exception as exc:
        # If Redis is down, allow through
        logger.error("Rate limit check failed: %s", exc)
        return True


# Instantiate as a reusable filter
RateLimitOk = filters.create(_rate_limit_check, "RateLimitOk")
