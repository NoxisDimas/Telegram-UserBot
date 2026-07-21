"""
Scheduled Messages Service
Time-delayed and recurring message scheduling.
"""
import asyncio
import json
import time
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from app.redis_conn import RedisClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

class Scheduler:
    """
    Manages scheduled messages using Redis.
    """
    
    TASKS_KEY = "scheduler:tasks"
    
    @classmethod
    def parse_time(cls, time_str: str) -> Optional[int]:
        """Parse time string like '10m', '2h', '1d' to seconds."""
        match = re.match(r'^(\d+)(s|m|h|d)$', time_str.lower())
        if not match:
            return None
        
        value = int(match.group(1))
        unit = match.group(2)
        
        multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        return value * multipliers.get(unit, 60)
    
    @classmethod
    async def schedule(cls, chat_id: int, message: str, delay_str: str, task_id: str = None) -> Dict:
        """Schedule a message to be sent after delay."""
        delay_seconds = cls.parse_time(delay_str)
        if not delay_seconds:
            return {"success": False, "error": "Invalid time format. Use: 10s, 5m, 2h, 1d"}
        
        task_id = task_id or f"sched_{int(time.time())}_{chat_id}"
        send_at = int(time.time()) + delay_seconds
        
        task = {
            "task_id": task_id,
            "chat_id": chat_id,
            "message": message,
            "send_at": send_at,
            "created_at": int(time.time()),
            "status": "pending"
        }
        
        redis = RedisClient.get_instance()
        await redis.hset(cls.TASKS_KEY, task_id, json.dumps(task))
        
        logger.info("Message scheduled", task_id=task_id, send_at=send_at)
        return {"success": True, "task_id": task_id, "send_at": send_at, "delay": delay_str}
    
    @classmethod
    async def get_pending_tasks(cls) -> List[Dict]:
        """Get all pending scheduled tasks."""
        redis = RedisClient.get_instance()
        all_tasks = await redis.hgetall(cls.TASKS_KEY)
        
        now = int(time.time())
        pending = []
        
        for task_json in all_tasks.values():
            task = json.loads(task_json)
            if task["status"] == "pending" and task["send_at"] <= now:
                pending.append(task)
        
        return pending
    
    @classmethod
    async def get_all_tasks(cls) -> List[Dict]:
        """Get all scheduled tasks."""
        redis = RedisClient.get_instance()
        all_tasks = await redis.hgetall(cls.TASKS_KEY)
        return [json.loads(v) for v in all_tasks.values()]
    
    @classmethod
    async def mark_sent(cls, task_id: str):
        """Mark a task as sent."""
        redis = RedisClient.get_instance()
        task_json = await redis.hget(cls.TASKS_KEY, task_id)
        
        if task_json:
            task = json.loads(task_json)
            task["status"] = "sent"
            task["sent_at"] = int(time.time())
            await redis.hset(cls.TASKS_KEY, task_id, json.dumps(task))
    
    @classmethod
    async def cancel(cls, task_id: str) -> bool:
        """Cancel a scheduled task."""
        redis = RedisClient.get_instance()
        result = await redis.hdel(cls.TASKS_KEY, task_id)
        return result > 0
    
    @classmethod
    async def cleanup_old(cls, days: int = 7):
        """Remove tasks older than N days."""
        redis = RedisClient.get_instance()
        all_tasks = await redis.hgetall(cls.TASKS_KEY)
        
        cutoff = int(time.time()) - (days * 86400)
        removed = 0
        
        for task_id, task_json in all_tasks.items():
            task = json.loads(task_json)
            if task.get("sent_at", task["created_at"]) < cutoff:
                await redis.hdel(cls.TASKS_KEY, task_id)
                removed += 1
        
        logger.info("Scheduler cleanup", removed=removed)
