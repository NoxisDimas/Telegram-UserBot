import time
from app.redis_conn import RedisClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

class RateLimiter:
    """
    Redis-based Rate Limiter.
    Uses simple fixed-window counters with expiration.
    """

    @staticmethod
    async def check_and_increment(key_suffix: str, limit: int, period_seconds: int) -> bool:
        """
        Checks if the action is allowed under the limit. If yes, increments the counter.
        Returns:
            bool: True if allowed, False if limit exceeded.
        """
        if limit <= 0:
            return True  # No limit set
            
        redis = RedisClient.get_instance()
        key = f"rate_limit:{key_suffix}"
        
        # Increment counter
        current_count = await redis.incr(key)
        
        # If it's the first increment, set expiration
        if current_count == 1:
            await redis.expire(key, period_seconds)
            
        if current_count > limit:
            ttl = await redis.ttl(key)
            logger.warning("Rate limit exceeded", key=key, limit=limit, current=current_count, ttl=ttl)
            return False
            
        return True

    @staticmethod
    async def check_global_gcast_limit(daily_limit: int, hourly_limit: int) -> bool:
        """
        Specific check for Gcast safety.
        """
        # Check hourly
        if not await RateLimiter.check_and_increment("gcast_hourly", hourly_limit, 3600):
            return False
            
        # Check daily
        if not await RateLimiter.check_and_increment("gcast_daily", daily_limit, 86400):
            return False
            
        return True
