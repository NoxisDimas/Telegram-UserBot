"""
Adaptive Flood & Risk Control
Survives Telegram rate limiting with dynamic delay adjustment.
"""
import asyncio
from enum import Enum
from app.redis_conn import RedisClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    FROZEN = "frozen"

# Delay multipliers per risk level
RISK_DELAYS = {
    RiskLevel.LOW: 1.0,
    RiskLevel.MEDIUM: 2.0,
    RiskLevel.HIGH: 5.0,
    RiskLevel.FROZEN: float('inf')  # No sending allowed
}

# Cooldown periods (in seconds)
RISK_COOLDOWNS = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 300,      # 5 minutes
    RiskLevel.HIGH: 1800,       # 30 minutes
    RiskLevel.FROZEN: 7200      # 2 hours
}

class RiskControl:
    """
    Manages adaptive risk levels based on Telegram responses.
    """
    
    REDIS_KEY = "system:risk_level"
    FLOOD_COUNT_KEY = "system:flood_count"
    COOLDOWN_UNTIL_KEY = "system:cooldown_until"
    
    @classmethod
    async def get_risk_level(cls) -> RiskLevel:
        """Get current risk level."""
        redis = RedisClient.get_instance()
        level = await redis.get(cls.REDIS_KEY)
        
        if level and level in [r.value for r in RiskLevel]:
            return RiskLevel(level)
        
        return RiskLevel.LOW
    
    @classmethod
    async def set_risk_level(cls, level: RiskLevel):
        """Set risk level."""
        redis = RedisClient.get_instance()
        await redis.set(cls.REDIS_KEY, level.value)
        logger.warning("Risk level changed", level=level.value)
    
    @classmethod
    async def record_flood_error(cls):
        """Record a flood/rate limit error and escalate risk."""
        redis = RedisClient.get_instance()
        
        # Increment flood counter
        count = await redis.incr(cls.FLOOD_COUNT_KEY)
        await redis.expire(cls.FLOOD_COUNT_KEY, 3600)  # Reset after 1 hour
        
        # Escalate risk level based on flood count
        if count >= 5:
            await cls.set_risk_level(RiskLevel.FROZEN)
            await cls._set_cooldown(RISK_COOLDOWNS[RiskLevel.FROZEN])
        elif count >= 3:
            await cls.set_risk_level(RiskLevel.HIGH)
            await cls._set_cooldown(RISK_COOLDOWNS[RiskLevel.HIGH])
        elif count >= 1:
            await cls.set_risk_level(RiskLevel.MEDIUM)
            await cls._set_cooldown(RISK_COOLDOWNS[RiskLevel.MEDIUM])
        
        logger.critical("Flood error recorded", count=count)
    
    @classmethod
    async def _set_cooldown(cls, seconds: int):
        """Set cooldown until timestamp."""
        import time
        redis = RedisClient.get_instance()
        cooldown_until = int(time.time()) + seconds
        await redis.set(cls.COOLDOWN_UNTIL_KEY, cooldown_until)
        logger.warning("Cooldown set", seconds=seconds)
    
    @classmethod
    async def is_in_cooldown(cls) -> bool:
        """Check if system is in cooldown."""
        import time
        redis = RedisClient.get_instance()
        cooldown_until = await redis.get(cls.COOLDOWN_UNTIL_KEY)
        
        if cooldown_until:
            if int(time.time()) < int(cooldown_until):
                return True
            else:
                # Cooldown expired, reduce risk level
                await cls._reduce_risk()
        
        return False
    
    @classmethod
    async def _reduce_risk(cls):
        """Reduce risk level after cooldown."""
        current = await cls.get_risk_level()
        
        if current == RiskLevel.FROZEN:
            await cls.set_risk_level(RiskLevel.HIGH)
        elif current == RiskLevel.HIGH:
            await cls.set_risk_level(RiskLevel.MEDIUM)
        elif current == RiskLevel.MEDIUM:
            await cls.set_risk_level(RiskLevel.LOW)
        
        # Clear cooldown
        redis = RedisClient.get_instance()
        await redis.delete(cls.COOLDOWN_UNTIL_KEY)
    
    @classmethod
    async def get_delay_multiplier(cls) -> float:
        """Get delay multiplier based on current risk level."""
        level = await cls.get_risk_level()
        return RISK_DELAYS.get(level, 1.0)
    
    @classmethod
    async def can_proceed(cls) -> tuple[bool, str]:
        """Check if system can proceed with sending."""
        if await cls.is_in_cooldown():
            return False, "System is in cooldown due to flood errors"
        
        level = await cls.get_risk_level()
        if level == RiskLevel.FROZEN:
            return False, "System is frozen due to excessive flood errors"
        
        return True, f"Risk level: {level.value}"
    
    @classmethod
    async def reset(cls):
        """Reset all risk controls (manual recovery)."""
        redis = RedisClient.get_instance()
        await redis.delete(cls.REDIS_KEY)
        await redis.delete(cls.FLOOD_COUNT_KEY)
        await redis.delete(cls.COOLDOWN_UNTIL_KEY)
        logger.info("Risk control reset")
