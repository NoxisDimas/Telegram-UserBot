"""
Kill Switch (Emergency Stop)
Global flag to instantly halt all operations.
"""
from app.redis_conn import RedisClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

class KillSwitch:
    """
    Global emergency stop mechanism.
    Worker checks this flag before every task.
    """
    
    REDIS_KEY = "system:halt"
    
    @classmethod
    async def is_active(cls) -> bool:
        """Check if kill switch is active."""
        redis = RedisClient.get_instance()
        value = await redis.get(cls.REDIS_KEY)
        return value == "true" or value == "1"
    
    @classmethod
    async def activate(cls, reason: str = ""):
        """Activate the kill switch."""
        redis = RedisClient.get_instance()
        await redis.set(cls.REDIS_KEY, "true")
        
        if reason:
            await redis.set(f"{cls.REDIS_KEY}:reason", reason)
        
        logger.critical("KILL SWITCH ACTIVATED", reason=reason)
    
    @classmethod
    async def deactivate(cls):
        """Deactivate the kill switch."""
        redis = RedisClient.get_instance()
        await redis.delete(cls.REDIS_KEY)
        await redis.delete(f"{cls.REDIS_KEY}:reason")
        logger.info("Kill switch deactivated")
    
    @classmethod
    async def get_status(cls) -> dict:
        """Get kill switch status."""
        redis = RedisClient.get_instance()
        active = await cls.is_active()
        reason = await redis.get(f"{cls.REDIS_KEY}:reason") if active else None
        
        return {
            "active": active,
            "reason": reason
        }
    
    @classmethod
    async def check_and_wait(cls) -> bool:
        """
        Check kill switch. If active, log and return False.
        Used by worker before processing each task.
        """
        if await cls.is_active():
            status = await cls.get_status()
            logger.warning("Kill switch is active, task blocked", reason=status.get("reason"))
            return False
        return True
