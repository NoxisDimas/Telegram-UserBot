"""
Auto-Reply Bot Service
Keyword-based auto responses with AI mode.
"""
import json
import re
from typing import Optional, List, Dict
from app.redis_conn import RedisClient
from app.utils.logger import get_logger
from app.services.ai.groq_client import GroqClient

logger = get_logger(__name__)

class AutoReply:
    """
    Manages auto-reply rules and responses.
    """
    
    RULES_KEY = "auto_reply:rules"
    SETTINGS_KEY = "auto_reply:settings"
    
    @classmethod
    async def add_rule(cls, keyword: str, response: str, match_type: str = "contains"):
        """Add an auto-reply rule."""
        redis = RedisClient.get_instance()
        
        rule = {
            "keyword": keyword.lower(),
            "response": response,
            "match_type": match_type,  # contains, exact, regex
            "enabled": True
        }
        
        await redis.hset(cls.RULES_KEY, keyword.lower(), json.dumps(rule))
        logger.info("Auto-reply rule added", keyword=keyword)
    
    @classmethod
    async def remove_rule(cls, keyword: str):
        """Remove an auto-reply rule."""
        redis = RedisClient.get_instance()
        await redis.hdel(cls.RULES_KEY, keyword.lower())
        logger.info("Auto-reply rule removed", keyword=keyword)
    
    @classmethod
    async def get_rules(cls) -> List[Dict]:
        """Get all auto-reply rules."""
        redis = RedisClient.get_instance()
        rules = await redis.hgetall(cls.RULES_KEY)
        
        return [json.loads(v) for v in rules.values()]
    
    @classmethod
    async def check_message(cls, message: str) -> Optional[str]:
        """Check if message matches any rule and return response."""
        rules = await cls.get_rules()
        message_lower = message.lower()
        
        for rule in rules:
            if not rule.get("enabled"):
                continue
            
            keyword = rule["keyword"]
            match_type = rule.get("match_type", "contains")
            
            matched = False
            if match_type == "exact":
                matched = message_lower == keyword
            elif match_type == "regex":
                matched = bool(re.search(keyword, message_lower))
            else:  # contains
                matched = keyword in message_lower
            
            if matched:
                return rule["response"]
        
        return None
    
    @classmethod
    async def set_ai_mode(cls, enabled: bool):
        """Enable/disable AI mode for auto-replies."""
        redis = RedisClient.get_instance()
        settings = await cls.get_settings()
        settings["ai_mode"] = enabled
        await redis.set(cls.SETTINGS_KEY, json.dumps(settings))
        logger.info("Auto-reply AI mode", enabled=enabled)
    
    @classmethod
    async def set_away_mode(cls, enabled: bool, message: str = None):
        """Enable/disable away mode."""
        redis = RedisClient.get_instance()
        settings = await cls.get_settings()
        settings["away_mode"] = enabled
        settings["away_message"] = message or "I'm currently away. I'll get back to you soon!"
        await redis.set(cls.SETTINGS_KEY, json.dumps(settings))
        logger.info("Away mode", enabled=enabled)
    
    @classmethod
    async def get_settings(cls) -> Dict:
        """Get auto-reply settings."""
        redis = RedisClient.get_instance()
        data = await redis.get(cls.SETTINGS_KEY)
        
        if data:
            return json.loads(data)
        
        return {
            "ai_mode": False,
            "away_mode": False,
            "away_message": "I'm currently away."
        }
    
    @classmethod
    async def get_response(cls, message: str, sender_name: str = "") -> Optional[str]:
        """Get auto-reply response for a message."""
        settings = await cls.get_settings()
        
        # 1. Check away mode first
        if settings.get("away_mode"):
            return settings.get("away_message")
        
        # 2. Check keyword rules
        rule_response = await cls.check_message(message)
        if rule_response:
            return rule_response
        
        # 3. AI mode fallback
        if settings.get("ai_mode"):
            context = f"Sender: {sender_name}" if sender_name else ""
            return await GroqClient.auto_reply(message, context)
        
        return None
