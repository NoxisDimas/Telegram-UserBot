"""
Chat Analytics Service
Track message volume, peak hours, and generate reports.
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import Counter
from app.redis_conn import RedisClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

class Analytics:
    """
    Chat analytics and statistics tracking.
    """
    
    STATS_KEY = "analytics:stats"
    HOURLY_KEY = "analytics:hourly"
    USERS_KEY = "analytics:users"
    
    @classmethod
    async def track_message(cls, chat_id: int, user_id: int, user_name: str = ""):
        """Track a message for analytics."""
        redis = RedisClient.get_instance()
        now = datetime.utcnow()
        today = now.strftime("%Y-%m-%d")
        hour = now.hour
        
        # Increment total count
        await redis.hincrby(f"{cls.STATS_KEY}:{chat_id}", "total_messages", 1)
        await redis.hincrby(f"{cls.STATS_KEY}:{chat_id}", f"day:{today}", 1)
        
        # Track hourly distribution
        await redis.hincrby(f"{cls.HOURLY_KEY}:{chat_id}", str(hour), 1)
        
        # Track user activity
        await redis.hincrby(f"{cls.USERS_KEY}:{chat_id}", str(user_id), 1)
        if user_name:
            await redis.hset(f"{cls.USERS_KEY}:{chat_id}:names", str(user_id), user_name)
    
    @classmethod
    async def get_stats(cls, chat_id: int) -> Dict:
        """Get chat statistics."""
        redis = RedisClient.get_instance()
        
        # Total messages
        stats = await redis.hgetall(f"{cls.STATS_KEY}:{chat_id}")
        total = int(stats.get("total_messages", 0))
        
        # Today's count
        today = datetime.utcnow().strftime("%Y-%m-%d")
        today_count = int(stats.get(f"day:{today}", 0))
        
        # Hourly distribution
        hourly = await redis.hgetall(f"{cls.HOURLY_KEY}:{chat_id}")
        hourly_dist = {int(k): int(v) for k, v in hourly.items()}
        
        # Find peak hour
        peak_hour = max(hourly_dist, key=hourly_dist.get) if hourly_dist else 12
        
        return {
            "chat_id": chat_id,
            "total_messages": total,
            "today_messages": today_count,
            "peak_hour": f"{peak_hour:02d}:00",
            "hourly_distribution": hourly_dist
        }
    
    @classmethod
    async def get_top_users(cls, chat_id: int, limit: int = 10) -> List[Dict]:
        """Get most active users in chat."""
        redis = RedisClient.get_instance()
        
        user_counts = await redis.hgetall(f"{cls.USERS_KEY}:{chat_id}")
        names = await redis.hgetall(f"{cls.USERS_KEY}:{chat_id}:names")
        
        # Sort by count
        sorted_users = sorted(
            [(uid, int(count)) for uid, count in user_counts.items()],
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        return [
            {
                "user_id": int(uid),
                "name": names.get(uid, "Unknown"),
                "message_count": count
            }
            for uid, count in sorted_users
        ]
    
    @classmethod
    async def generate_report(cls, chat_id: int) -> str:
        """Generate HTML analytics report."""
        stats = await cls.get_stats(chat_id)
        top_users = await cls.get_top_users(chat_id, 5)
        
        # Generate simple HTML
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Chat Analytics - {chat_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
        .stat {{ background: #f0f0f0; padding: 15px; margin: 10px 0; border-radius: 8px; }}
        .stat h3 {{ margin: 0 0 10px 0; color: #333; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
    </style>
</head>
<body>
    <h1>📊 Chat Analytics Report</h1>
    <p>Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}</p>
    
    <div class="stat">
        <h3>📈 Message Statistics</h3>
        <p>Total Messages: <strong>{stats['total_messages']}</strong></p>
        <p>Today: <strong>{stats['today_messages']}</strong></p>
        <p>Peak Hour: <strong>{stats['peak_hour']}</strong></p>
    </div>
    
    <div class="stat">
        <h3>👥 Top Contributors</h3>
        <table>
            <tr><th>#</th><th>User</th><th>Messages</th></tr>
            {"".join(f"<tr><td>{i+1}</td><td>{u['name']}</td><td>{u['message_count']}</td></tr>" 
                     for i, u in enumerate(top_users))}
        </table>
    </div>
</body>
</html>
"""
        return html
