"""
Account Health Monitor
Track flood warnings, errors, and predict ban risk.
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List
from app.redis_conn import RedisClient
from app.utils.logger import get_logger
from app.services.ai.groq_client import GroqClient

logger = get_logger(__name__)

class HealthMonitor:
    """
    Monitors account health and predicts ban risk.
    """
    
    EVENTS_KEY = "health:events"
    STATS_KEY = "health:stats"
    
    @classmethod
    async def record_event(cls, event_type: str, details: str = "", severity: str = "info"):
        """Record a health-related event."""
        redis = RedisClient.get_instance()
        
        event = {
            "type": event_type,
            "details": details,
            "severity": severity,  # info, warning, error, critical
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await redis.lpush(cls.EVENTS_KEY, json.dumps(event))
        await redis.ltrim(cls.EVENTS_KEY, 0, 499)  # Keep last 500
        
        # Update stats
        await redis.hincrby(cls.STATS_KEY, f"event:{event_type}", 1)
        
        if severity in ["error", "critical"]:
            await redis.hincrby(cls.STATS_KEY, "error_count", 1)
        
        logger.info("Health event recorded", event_type=event_type, severity=severity)
    
    @classmethod
    async def record_flood_warning(cls, wait_seconds: int):
        """Record a flood warning."""
        await cls.record_event(
            "flood_warning",
            f"Wait {wait_seconds}s required",
            "critical"
        )
        
        redis = RedisClient.get_instance()
        await redis.hincrby(cls.STATS_KEY, "flood_count", 1)
    
    @classmethod
    async def record_success(cls, action: str):
        """Record successful action."""
        redis = RedisClient.get_instance()
        await redis.hincrby(cls.STATS_KEY, "success_count", 1)
        await redis.hincrby(cls.STATS_KEY, f"action:{action}", 1)
    
    @classmethod
    async def get_stats(cls) -> Dict:
        """Get health statistics."""
        redis = RedisClient.get_instance()
        stats = await redis.hgetall(cls.STATS_KEY)
        
        return {
            "total_errors": int(stats.get("error_count", 0)),
            "flood_warnings": int(stats.get("flood_count", 0)),
            "successful_actions": int(stats.get("success_count", 0)),
            "stats": {k: int(v) for k, v in stats.items()}
        }
    
    @classmethod
    async def get_recent_events(cls, count: int = 20, severity: str = None) -> List[Dict]:
        """Get recent health events."""
        redis = RedisClient.get_instance()
        events = await redis.lrange(cls.EVENTS_KEY, 0, count * 2)  # Get more to filter
        
        result = []
        for e in events:
            event = json.loads(e)
            if severity is None or event.get("severity") == severity:
                result.append(event)
                if len(result) >= count:
                    break
        
        return result
    
    @classmethod
    async def calculate_risk_score(cls) -> Dict:
        """Calculate ban risk score."""
        stats = await cls.get_stats()
        events = await cls.get_recent_events(50)
        
        # Calculate risk factors
        flood_count = stats.get("flood_warnings", 0)
        error_count = stats.get("total_errors", 0)
        success_count = stats.get("successful_actions", 1)  # Avoid div by 0
        
        # Recent critical events (last 24h)
        recent_critical = 0
        cutoff = datetime.utcnow() - timedelta(hours=24)
        
        for event in events:
            try:
                ts = datetime.fromisoformat(event["timestamp"])
                if ts > cutoff and event.get("severity") == "critical":
                    recent_critical += 1
            except:
                continue
        
        # Calculate score (0-100, higher = more risk)
        base_score = 0
        base_score += min(flood_count * 10, 40)  # Max 40 from floods
        base_score += min(error_count * 2, 20)   # Max 20 from errors
        base_score += min(recent_critical * 15, 30)  # Max 30 from recent critical
        
        # Reduce based on success ratio
        if success_count > 0:
            ratio = error_count / (success_count + error_count)
            base_score = int(base_score * (0.5 + ratio * 0.5))
        
        risk_score = min(base_score, 100)
        
        # Determine risk level
        if risk_score >= 70:
            risk_level = "HIGH"
            advice = "Reduce activity immediately. Consider pausing for 24h."
        elif risk_score >= 40:
            risk_level = "MEDIUM"
            advice = "Increase delays between actions. Monitor closely."
        else:
            risk_level = "LOW"
            advice = "Account health is good. Continue with normal delays."
        
        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "advice": advice,
            "factors": {
                "flood_warnings": flood_count,
                "total_errors": error_count,
                "recent_critical": recent_critical,
                "success_count": success_count
            }
        }
    
    @classmethod
    async def get_health_report(cls) -> str:
        """Generate health report text."""
        stats = await cls.get_stats()
        risk = await cls.calculate_risk_score()
        
        report = (
            f"**🏥 Account Health Report**\n\n"
            f"📊 **Risk Score**: `{risk['risk_score']}/100` ({risk['risk_level']})\n\n"
            f"📈 **Statistics**\n"
            f"  • Successful Actions: `{stats['successful_actions']}`\n"
            f"  • Flood Warnings: `{stats['flood_warnings']}`\n"
            f"  • Errors: `{stats['total_errors']}`\n\n"
            f"💡 **Advice**: {risk['advice']}"
        )
        
        return report
