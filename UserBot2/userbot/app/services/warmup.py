"""
Account Warm-Up Engine
Tracks account age and activity to protect new/low-trust accounts.
"""
import time
from datetime import datetime, timedelta
from app.redis_conn import RedisClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

class WarmupStage:
    DAY1 = "day1"
    DAY2 = "day2" 
    WEEK1 = "week1"
    MATURE = "mature"

# Send limits per stage
STAGE_LIMITS = {
    WarmupStage.DAY1: 5,
    WarmupStage.DAY2: 15,
    WarmupStage.WEEK1: 50,
    WarmupStage.MATURE: 500  # Effectively unlimited but still capped
}

class WarmupEngine:
    """
    Manages account warm-up stages and enforces send limits.
    """
    
    @staticmethod
    def _get_key(session_id: str) -> str:
        return f"account:{session_id}:stats"
    
    @classmethod
    async def initialize_account(cls, session_id: str):
        """Initialize account stats if not exists."""
        redis = RedisClient.get_instance()
        key = cls._get_key(session_id)
        
        exists = await redis.exists(key)
        if not exists:
            await redis.hset(key, mapping={
                "created_at": datetime.utcnow().isoformat(),
                "messages_sent_today": 0,
                "last_reset_date": datetime.utcnow().date().isoformat()
            })
            logger.info("Account initialized for warm-up", session_id=session_id)
    
    @classmethod
    async def get_stage(cls, session_id: str) -> str:
        """Determine current warm-up stage based on account age."""
        redis = RedisClient.get_instance()
        key = cls._get_key(session_id)
        
        created_at_str = await redis.hget(key, "created_at")
        if not created_at_str:
            await cls.initialize_account(session_id)
            return WarmupStage.DAY1
        
        created_at = datetime.fromisoformat(created_at_str)
        age = datetime.utcnow() - created_at
        
        if age < timedelta(days=1):
            return WarmupStage.DAY1
        elif age < timedelta(days=2):
            return WarmupStage.DAY2
        elif age < timedelta(days=7):
            return WarmupStage.WEEK1
        else:
            return WarmupStage.MATURE
    
    @classmethod
    async def get_daily_count(cls, session_id: str) -> int:
        """Get messages sent today, reset if new day."""
        redis = RedisClient.get_instance()
        key = cls._get_key(session_id)
        
        today = datetime.utcnow().date().isoformat()
        last_reset = await redis.hget(key, "last_reset_date")
        
        if last_reset != today:
            # New day, reset counter
            await redis.hset(key, mapping={
                "messages_sent_today": 0,
                "last_reset_date": today
            })
            return 0
        
        count = await redis.hget(key, "messages_sent_today")
        return int(count) if count else 0
    
    @classmethod
    async def increment_count(cls, session_id: str, amount: int = 1):
        """Increment daily message count."""
        redis = RedisClient.get_instance()
        key = cls._get_key(session_id)
        await redis.hincrby(key, "messages_sent_today", amount)
    
    @classmethod
    async def can_send(cls, session_id: str) -> tuple[bool, str]:
        """
        Check if account is eligible to send.
        Returns (allowed, reason).
        """
        stage = await cls.get_stage(session_id)
        limit = STAGE_LIMITS.get(stage, 5)
        current_count = await cls.get_daily_count(session_id)
        
        if current_count >= limit:
            reason = f"Daily limit reached for stage '{stage}' ({current_count}/{limit})"
            logger.warning("Warm-up limit exceeded", session_id=session_id, stage=stage, count=current_count)
            return False, reason
        
        remaining = limit - current_count
        logger.debug("Warm-up check passed", stage=stage, remaining=remaining)
        return True, f"Stage: {stage}, Remaining: {remaining}"
    
    @classmethod
    async def get_stats(cls, session_id: str) -> dict:
        """Get full account stats."""
        redis = RedisClient.get_instance()
        key = cls._get_key(session_id)
        
        stats = await redis.hgetall(key)
        stage = await cls.get_stage(session_id)
        limit = STAGE_LIMITS.get(stage, 5)
        
        return {
            "session_id": session_id,
            "stage": stage,
            "limit": limit,
            "created_at": stats.get("created_at"),
            "messages_sent_today": int(stats.get("messages_sent_today", 0)),
            "last_reset_date": stats.get("last_reset_date")
        }
