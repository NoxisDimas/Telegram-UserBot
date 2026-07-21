"""
AI Summarizer Service
Chat summarization using Groq.
"""
import json
from datetime import datetime
from typing import List, Dict
from app.redis_conn import RedisClient
from app.utils.logger import get_logger
from app.services.ai.groq_client import GroqClient

logger = get_logger(__name__)

class Summarizer:
    """
    AI-powered chat summarization.
    """
    
    HISTORY_KEY = "summarizer:history"
    DIGEST_KEY = "summarizer:digest"
    
    @classmethod
    async def summarize_messages(cls, messages: List[str], max_words: int = 150) -> str:
        """Summarize a list of messages."""
        return await GroqClient.summarize(messages, max_words)
    
    @classmethod
    async def store_message(cls, chat_id: int, sender: str, text: str):
        """Store message for later summarization."""
        redis = RedisClient.get_instance()
        key = f"{cls.HISTORY_KEY}:{chat_id}"
        
        entry = {
            "sender": sender,
            "text": text,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await redis.lpush(key, json.dumps(entry))
        # Keep only last 500 messages
        await redis.ltrim(key, 0, 499)
    
    @classmethod
    async def get_recent_messages(cls, chat_id: int, count: int = 100) -> List[str]:
        """Get recent messages for a chat."""
        redis = RedisClient.get_instance()
        key = f"{cls.HISTORY_KEY}:{chat_id}"
        
        raw_messages = await redis.lrange(key, 0, count - 1)
        
        formatted = []
        for msg_json in reversed(raw_messages):  # Chronological order
            msg = json.loads(msg_json)
            formatted.append(f"{msg['sender']}: {msg['text']}")
        
        return formatted
    
    @classmethod
    async def summarize_chat(cls, chat_id: int, count: int = 100) -> str:
        """Summarize recent chat messages."""
        messages = await cls.get_recent_messages(chat_id, count)
        
        if not messages:
            return "No messages to summarize."
        
        summary = await cls.summarize_messages(messages)
        
        # Store summary
        redis = RedisClient.get_instance()
        await redis.hset(f"{cls.DIGEST_KEY}:{chat_id}", 
                        datetime.utcnow().strftime("%Y-%m-%d"), 
                        summary)
        
        return summary
    
    @classmethod
    async def get_daily_digest(cls, chat_id: int) -> str:
        """Get today's digest for a chat."""
        redis = RedisClient.get_instance()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        
        digest = await redis.hget(f"{cls.DIGEST_KEY}:{chat_id}", today)
        
        if digest:
            return digest
        
        # Generate if not exists
        return await cls.summarize_chat(chat_id)
    
    @classmethod
    async def generate_all_digests(cls) -> Dict[int, str]:
        """Generate digests for all tracked chats."""
        redis = RedisClient.get_instance()
        
        # Find all chat histories
        cursor = 0
        chats = []
        
        while True:
            cursor, keys = await redis.scan(cursor, match=f"{cls.HISTORY_KEY}:*")
            for key in keys:
                chat_id = int(key.split(":")[-1])
                chats.append(chat_id)
            if cursor == 0:
                break
        
        digests = {}
        for chat_id in chats:
            try:
                digests[chat_id] = await cls.summarize_chat(chat_id)
            except Exception as e:
                logger.error("Digest generation failed", chat_id=chat_id, error=str(e))
        
        return digests
