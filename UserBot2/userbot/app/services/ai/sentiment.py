"""
Sentiment Analysis Service
Monitor group mood and detect sentiment spikes.
"""
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from app.redis_conn import RedisClient
from app.utils.logger import get_logger
from app.services.ai.groq_client import GroqClient

logger = get_logger(__name__)

class SentimentAnalyzer:
    """
    AI-powered sentiment analysis for chats.
    """
    
    HISTORY_KEY = "sentiment:history"
    ALERT_KEY = "sentiment:alerts"
    
    @classmethod
    async def analyze(cls, messages: List[str]) -> Dict:
        """Analyze sentiment of messages."""
        return await GroqClient.analyze_sentiment(messages)
    
    @classmethod
    async def analyze_chat(cls, chat_id: int, messages: List[str]) -> Dict:
        """Analyze and store sentiment for a chat."""
        result = await cls.analyze(messages)
        
        # Store in history
        redis = RedisClient.get_instance()
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "sentiment": result.get("sentiment", "unknown"),
            "score": result.get("score", 0.5),
            "message_count": len(messages)
        }
        
        await redis.lpush(f"{cls.HISTORY_KEY}:{chat_id}", json.dumps(entry))
        await redis.ltrim(f"{cls.HISTORY_KEY}:{chat_id}", 0, 99)  # Keep last 100
        
        # Check for alerts
        await cls._check_alerts(chat_id, result)
        
        return result
    
    @classmethod
    async def _check_alerts(cls, chat_id: int, result: Dict):
        """Check if sentiment triggers an alert."""
        sentiment = result.get("sentiment", "neutral")
        score = result.get("score", 0.5)
        
        # Alert on very negative sentiment
        if sentiment == "negative" and score < 0.3:
            redis = RedisClient.get_instance()
            alert = {
                "chat_id": chat_id,
                "timestamp": datetime.utcnow().isoformat(),
                "sentiment": sentiment,
                "score": score,
                "summary": result.get("summary", "Negative sentiment detected")
            }
            await redis.lpush(cls.ALERT_KEY, json.dumps(alert))
            logger.warning("Negative sentiment alert", chat_id=chat_id, score=score)
    
    @classmethod
    async def get_history(cls, chat_id: int, count: int = 10) -> List[Dict]:
        """Get sentiment history for a chat."""
        redis = RedisClient.get_instance()
        history = await redis.lrange(f"{cls.HISTORY_KEY}:{chat_id}", 0, count - 1)
        return [json.loads(h) for h in history]
    
    @classmethod
    async def get_alerts(cls, count: int = 20) -> List[Dict]:
        """Get recent sentiment alerts."""
        redis = RedisClient.get_instance()
        alerts = await redis.lrange(cls.ALERT_KEY, 0, count - 1)
        return [json.loads(a) for a in alerts]
    
    @classmethod
    async def get_trend(cls, chat_id: int, hours: int = 24) -> Dict:
        """Get sentiment trend for a chat."""
        history = await cls.get_history(chat_id, 50)
        
        if not history:
            return {"trend": "unknown", "avg_score": 0.5, "samples": 0}
        
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent = []
        
        for h in history:
            try:
                ts = datetime.fromisoformat(h["timestamp"])
                if ts > cutoff:
                    recent.append(h["score"])
            except:
                continue
        
        if not recent:
            return {"trend": "unknown", "avg_score": 0.5, "samples": 0}
        
        avg = sum(recent) / len(recent)
        
        if avg > 0.6:
            trend = "positive"
        elif avg < 0.4:
            trend = "negative"
        else:
            trend = "neutral"
        
        return {"trend": trend, "avg_score": round(avg, 2), "samples": len(recent)}
