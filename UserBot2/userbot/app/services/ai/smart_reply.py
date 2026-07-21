"""
Smart Reply Suggestions
AI-generated reply suggestions based on context.
"""
from typing import List
from app.utils.logger import get_logger
from app.services.ai.groq_client import GroqClient

logger = get_logger(__name__)

class SmartReply:
    """
    Generates contextual reply suggestions using AI.
    """
    
    @classmethod
    async def get_suggestions(cls, context: str, style: str = "friendly", count: int = 3) -> List[str]:
        """Generate reply suggestions for given context."""
        return await GroqClient.generate_reply(context, style)
    
    @classmethod
    async def get_suggestions_for_chat(cls, messages: List[str], style: str = "friendly") -> List[str]:
        """Generate suggestions based on chat history."""
        if not messages:
            return ["Hi!", "How can I help?", "Thanks!"]
        
        # Use last 10 messages as context
        context = "\n".join(messages[-10:])
        return await cls.get_suggestions(context, style)
    
    @classmethod
    async def quick_reply(cls, last_message: str) -> List[str]:
        """Quick reply suggestions for a single message."""
        # Simple fallback if AI fails
        fallbacks = ["👍", "Thanks!", "Got it!"]
        
        try:
            suggestions = await GroqClient.generate_reply(last_message, "casual")
            return suggestions if suggestions else fallbacks
        except Exception as e:
            logger.error("Smart reply failed", error=str(e))
            return fallbacks
