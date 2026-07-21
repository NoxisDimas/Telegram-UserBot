"""
Message Forwarder Engine
Auto-forward messages with filters and anti-duplicate.
"""
import json
import hashlib
from typing import Optional, List, Dict
from app.redis_conn import RedisClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

class Forwarder:
    """
    Manages message forwarding rules.
    """
    
    RULES_KEY = "forwarder:rules"
    HASH_KEY = "forwarder:hashes"
    HASH_TTL = 86400 * 7  # 7 days
    
    @classmethod
    async def add_rule(cls, source_chat: int, target_chat: int, 
                       keywords: List[str] = None, 
                       media_only: bool = False,
                       exclude_keywords: List[str] = None) -> Dict:
        """Add a forwarding rule."""
        redis = RedisClient.get_instance()
        
        rule_id = f"fwd_{source_chat}_{target_chat}"
        
        rule = {
            "rule_id": rule_id,
            "source_chat": source_chat,
            "target_chat": target_chat,
            "keywords": keywords or [],
            "exclude_keywords": exclude_keywords or [],
            "media_only": media_only,
            "enabled": True
        }
        
        await redis.hset(cls.RULES_KEY, rule_id, json.dumps(rule))
        logger.info("Forwarder rule added", rule_id=rule_id)
        
        return rule
    
    @classmethod
    async def remove_rule(cls, source_chat: int, target_chat: int) -> bool:
        """Remove a forwarding rule."""
        redis = RedisClient.get_instance()
        rule_id = f"fwd_{source_chat}_{target_chat}"
        result = await redis.hdel(cls.RULES_KEY, rule_id)
        return result > 0
    
    @classmethod
    async def get_rules(cls) -> List[Dict]:
        """Get all forwarding rules."""
        redis = RedisClient.get_instance()
        rules = await redis.hgetall(cls.RULES_KEY)
        return [json.loads(v) for v in rules.values()]
    
    @classmethod
    async def get_rules_for_source(cls, source_chat: int) -> List[Dict]:
        """Get rules for a specific source chat."""
        rules = await cls.get_rules()
        return [r for r in rules if r["source_chat"] == source_chat and r["enabled"]]
    
    @classmethod
    def _hash_message(cls, chat_id: int, text: str) -> str:
        """Generate hash for duplicate detection."""
        content = f"{chat_id}:{text[:200]}"
        return hashlib.md5(content.encode()).hexdigest()
    
    @classmethod
    async def is_duplicate(cls, chat_id: int, text: str) -> bool:
        """Check if message is a duplicate."""
        redis = RedisClient.get_instance()
        msg_hash = cls._hash_message(chat_id, text)
        
        exists = await redis.exists(f"{cls.HASH_KEY}:{msg_hash}")
        return exists
    
    @classmethod
    async def mark_forwarded(cls, chat_id: int, text: str):
        """Mark message as forwarded to prevent duplicates."""
        redis = RedisClient.get_instance()
        msg_hash = cls._hash_message(chat_id, text)
        
        await redis.setex(f"{cls.HASH_KEY}:{msg_hash}", cls.HASH_TTL, "1")
    
    @classmethod
    def matches_rule(cls, rule: Dict, text: str, has_media: bool) -> bool:
        """Check if message matches forwarding rule."""
        # Media filter
        if rule.get("media_only") and not has_media:
            return False
        
        text_lower = text.lower() if text else ""
        
        # Exclude keywords
        for kw in rule.get("exclude_keywords", []):
            if kw.lower() in text_lower:
                return False
        
        # Include keywords (if specified)
        keywords = rule.get("keywords", [])
        if keywords:
            return any(kw.lower() in text_lower for kw in keywords)
        
        return True
    
    @classmethod
    async def should_forward(cls, source_chat: int, text: str, has_media: bool) -> List[int]:
        """Get list of target chats for forwarding."""
        if text and await cls.is_duplicate(source_chat, text):
            return []
        
        rules = await cls.get_rules_for_source(source_chat)
        targets = []
        
        for rule in rules:
            if cls.matches_rule(rule, text, has_media):
                targets.append(rule["target_chat"])
        
        return targets
