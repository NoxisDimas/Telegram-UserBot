"""
AI Message Rewrite Layer
Optional, pluggable AI rewriting to reduce duplicate message fingerprinting.
"""
import random
from abc import ABC, abstractmethod
from app.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__)

class AIRewriter(ABC):
    """Abstract base class for message rewriters."""
    
    @abstractmethod
    async def rewrite(self, message: str, variations: int = 3) -> list[str]:
        """Generate variations of the message."""
        pass
    
    @abstractmethod
    async def get_random_variant(self, message: str) -> str:
        """Get a single random variant."""
        pass


class DummyRewriter(AIRewriter):
    """
    Fallback rewriter that returns the original message.
    Used when AI rewriting is disabled.
    """
    
    async def rewrite(self, message: str, variations: int = 3) -> list[str]:
        # Simple variations: add slight modifications
        variants = [message]
        
        # Add some basic variations
        if len(message) > 10:
            variants.append(message + " ")  # Trailing space
            variants.append(" " + message)  # Leading space
        
        return variants[:variations]
    
    async def get_random_variant(self, message: str) -> str:
        variants = await self.rewrite(message)
        return random.choice(variants)


class OpenAIRewriter(AIRewriter):
    """
    AI rewriter using OpenAI API.
    Requires OPENAI_API_KEY in environment.
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or getattr(config, 'OPENAI_API_KEY', None)
        
    async def rewrite(self, message: str, variations: int = 3) -> list[str]:
        if not self.api_key:
            logger.warning("OpenAI API key not configured, falling back to dummy")
            return [message]
        
        try:
            # Import here to avoid dependency if not used
            import httpx
            
            prompt = f"""Rewrite the following message {variations} different ways. 
Keep the exact same meaning and intent, but vary the wording slightly.
Return only the variations, one per line.

Original message:
{message}"""

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-3.5-turbo",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 500
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    variants = [line.strip() for line in content.split("\n") if line.strip()]
                    logger.info("AI rewrite generated", count=len(variants))
                    return variants if variants else [message]
                else:
                    logger.error("OpenAI API error", status=response.status_code)
                    return [message]
                    
        except Exception as e:
            logger.error("AI rewrite failed", error=str(e))
            return [message]
    
    async def get_random_variant(self, message: str) -> str:
        variants = await self.rewrite(message)
        return random.choice(variants)


def get_rewriter() -> AIRewriter:
    """Factory function to get the appropriate rewriter based on config."""
    if getattr(config, 'ENABLE_AI_REWRITE', False):
        api_key = getattr(config, 'OPENAI_API_KEY', None)
        if api_key:
            return OpenAIRewriter(api_key)
    
    return DummyRewriter()
