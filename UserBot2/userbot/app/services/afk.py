"""
AFK Mode Service
Auto-reply when mentioned while away.
"""
import json
from datetime import datetime
from typing import Optional, Dict, List
from app.redis_conn import RedisClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

class AFKMode:
    """
    Manages AFK (Away From Keyboard) mode.
    """
    
    STATUS_KEY = "afk:status"
    MENTIONS_KEY = "afk:mentions"
    
    @classmethod
    async def enable(cls, reason: str = ""):
        """Enable AFK mode."""
        redis = RedisClient.get_instance()
        
        status = {
            "enabled": True,
            "reason": reason or "I'm currently AFK",
            "since": datetime.utcnow().isoformat(),
            "mentions_missed": 0
        }
        
        await redis.set(cls.STATUS_KEY, json.dumps(status))
        await redis.delete(cls.MENTIONS_KEY)  # Clear old mentions
        
        logger.info("AFK mode enabled", reason=reason)
        return status
    
    @classmethod
    async def disable(cls) -> Dict:
        """Disable AFK mode and return missed mentions."""
        redis = RedisClient.get_instance()
        
        # Get status before clearing
        status = await cls.get_status()
        mentions = await cls.get_missed_mentions()
        
        await redis.delete(cls.STATUS_KEY)
        await redis.delete(cls.MENTIONS_KEY)
        
        logger.info("AFK mode disabled", missed_mentions=len(mentions))
        
        return {
            "was_afk_since": status.get("since"),
            "missed_mentions": mentions
        }
    
    @classmethod
    async def get_status(cls) -> Dict:
        """Get current AFK status."""
        redis = RedisClient.get_instance()
        data = await redis.get(cls.STATUS_KEY)
        
        if data:
            return json.loads(data)
        
        return {"enabled": False}
    
    @classmethod
    async def is_afk(cls) -> bool:
        """Check if AFK mode is active."""
        status = await cls.get_status()
        return status.get("enabled", False)
    
    @classmethod
    async def record_mention(cls, chat_id: int, chat_name: str, 
                            sender_id: int, sender_name: str, 
                            message: str):
        """Record a missed mention."""
        redis = RedisClient.get_instance()
        
        mention = {
            "chat_id": chat_id,
            "chat_name": chat_name,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "message": message[:200],  # Truncate
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await redis.lpush(cls.MENTIONS_KEY, json.dumps(mention))
        await redis.ltrim(cls.MENTIONS_KEY, 0, 99)  # Keep last 100
        
        # Update mention count in status
        status = await cls.get_status()
        status["mentions_missed"] = status.get("mentions_missed", 0) + 1
        await redis.set(cls.STATUS_KEY, json.dumps(status))
        
        logger.info("Mention recorded", sender=sender_name, chat=chat_name)
    
    @classmethod
    async def get_missed_mentions(cls) -> List[Dict]:
        """Get all missed mentions."""
        redis = RedisClient.get_instance()
        mentions = await redis.lrange(cls.MENTIONS_KEY, 0, -1)
        return [json.loads(m) for m in mentions]
    
    @classmethod
    async def get_afk_reply(cls) -> str:
        """Get the AFK auto-reply message."""
        status = await cls.get_status()
        
        if not status.get("enabled"):
            return None
        
        reason = status.get("reason", "I'm currently AFK")
        since = status.get("since", "")
        
        # Calculate duration
        try:
            since_dt = datetime.fromisoformat(since)
            delta = datetime.utcnow() - since_dt
            hours = int(delta.total_seconds() / 3600)
            mins = int((delta.total_seconds() % 3600) / 60)
            duration = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
        except:
            duration = "a while"
        
        return f"⏸️ **AFK Mode**\n{reason}\n(Away for {duration})"
