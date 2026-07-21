"""
Delivery Report & Progress Tracking
Tracks per-task progress and allows safe resume.
"""
import json
from app.redis_conn import RedisClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

class DeliveryTracker:
    """
    Tracks delivery progress for each task.
    Allows resuming from last successful recipient.
    """
    
    @staticmethod
    def _get_key(task_id: str) -> str:
        return f"task:{task_id}:progress"
    
    @classmethod
    async def initialize(cls, task_id: str, total_recipients: int):
        """Initialize tracking for a new task."""
        redis = RedisClient.get_instance()
        key = cls._get_key(task_id)
        
        await redis.hset(key, mapping={
            "total": total_recipients,
            "sent": 0,
            "failed": 0,
            "skipped": 0,
            "last_index": -1,
            "status": "running"
        })
        
        # Expire after 7 days
        await redis.expire(key, 86400 * 7)
        logger.info("Delivery tracking initialized", task_id=task_id, total=total_recipients)
    
    @classmethod
    async def record_sent(cls, task_id: str, recipient_index: int):
        """Record a successful send."""
        redis = RedisClient.get_instance()
        key = cls._get_key(task_id)
        
        await redis.hincrby(key, "sent", 1)
        await redis.hset(key, "last_index", recipient_index)
    
    @classmethod
    async def record_failed(cls, task_id: str, recipient_id: int, error: str):
        """Record a failed send."""
        redis = RedisClient.get_instance()
        key = cls._get_key(task_id)
        
        await redis.hincrby(key, "failed", 1)
        
        # Store failure details
        failures_key = f"task:{task_id}:failures"
        await redis.lpush(failures_key, json.dumps({"id": recipient_id, "error": error}))
        await redis.expire(failures_key, 86400 * 7)
    
    @classmethod
    async def record_skipped(cls, task_id: str, recipient_id: int, reason: str):
        """Record a skipped recipient."""
        redis = RedisClient.get_instance()
        key = cls._get_key(task_id)
        
        await redis.hincrby(key, "skipped", 1)
    
    @classmethod
    async def get_progress(cls, task_id: str) -> dict:
        """Get current progress for a task."""
        redis = RedisClient.get_instance()
        key = cls._get_key(task_id)
        
        data = await redis.hgetall(key)
        if not data:
            return None
        
        return {
            "task_id": task_id,
            "total": int(data.get("total", 0)),
            "sent": int(data.get("sent", 0)),
            "failed": int(data.get("failed", 0)),
            "skipped": int(data.get("skipped", 0)),
            "last_index": int(data.get("last_index", -1)),
            "status": data.get("status", "unknown")
        }
    
    @classmethod
    async def get_resume_index(cls, task_id: str) -> int:
        """Get the index to resume from (last_index + 1)."""
        redis = RedisClient.get_instance()
        key = cls._get_key(task_id)
        
        last_index = await redis.hget(key, "last_index")
        return int(last_index) + 1 if last_index else 0
    
    @classmethod
    async def mark_completed(cls, task_id: str):
        """Mark task as completed."""
        redis = RedisClient.get_instance()
        key = cls._get_key(task_id)
        await redis.hset(key, "status", "completed")
        logger.info("Task marked completed", task_id=task_id)
    
    @classmethod
    async def mark_paused(cls, task_id: str, reason: str = ""):
        """Mark task as paused (can be resumed)."""
        redis = RedisClient.get_instance()
        key = cls._get_key(task_id)
        await redis.hset(key, mapping={"status": "paused", "pause_reason": reason})
        logger.info("Task paused", task_id=task_id, reason=reason)
    
    @classmethod
    async def mark_aborted(cls, task_id: str, reason: str = ""):
        """Mark task as aborted (should not be resumed)."""
        redis = RedisClient.get_instance()
        key = cls._get_key(task_id)
        await redis.hset(key, mapping={"status": "aborted", "abort_reason": reason})
        logger.warning("Task aborted", task_id=task_id, reason=reason)
