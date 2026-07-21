"""
Groq AI Client with LangChain integration.
Provides shared AI client for all features.
"""
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from app.config import config
from app.utils.logger import get_logger
from typing import Optional, List

logger = get_logger(__name__)

class GroqClient:
    """
    Singleton Groq client using LangChain.
    """
    _instance: Optional[ChatGroq] = None
    
    @classmethod
    def get_client(cls) -> ChatGroq:
        """Get or create the Groq client."""
        if cls._instance is None:
            api_key = getattr(config, 'GROQ_API_KEY', None)
            model = getattr(config, 'AI_MODEL', 'llama-3.3-70b-versatile')
            
            if not api_key:
                logger.warning("GROQ_API_KEY not set, AI features disabled")
                return None
            
            cls._instance = ChatGroq(
                api_key=api_key,
                model=model,
                temperature=0.7,
                max_tokens=1024
            )
            logger.info("Groq client initialized", model=model)
        
        return cls._instance
    
    @classmethod
    async def chat(cls, prompt: str, system_prompt: str = None) -> str:
        """Simple chat completion."""
        client = cls.get_client()
        if not client:
            return "[AI not available - GROQ_API_KEY not set]"
        
        try:
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))
            
            response = await client.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error("Groq chat failed", error=str(e))
            return f"[AI Error: {str(e)}]"
    
    @classmethod
    async def summarize(cls, messages: List[str], max_words: int = 100) -> str:
        """Summarize a list of messages."""
        if not messages:
            return "No messages to summarize."
        
        combined = "\n".join(messages[-50:])  # Last 50 messages max
        
        system = f"You are a concise summarizer. Summarize the following chat messages in {max_words} words or less. Focus on key topics and decisions."
        
        return await cls.chat(combined, system)
    
    @classmethod
    async def analyze_sentiment(cls, messages: List[str]) -> dict:
        """Analyze sentiment of messages."""
        if not messages:
            return {"sentiment": "neutral", "score": 0.5, "summary": "No messages"}
        
        combined = "\n".join(messages[-30:])
        
        system = """Analyze the sentiment of these chat messages. 
Respond in this exact JSON format:
{"sentiment": "positive/negative/neutral", "score": 0.0-1.0, "summary": "brief explanation"}"""
        
        result = await cls.chat(combined, system)
        
        try:
            import json
            return json.loads(result)
        except:
            return {"sentiment": "unknown", "score": 0.5, "summary": result}
    
    @classmethod
    async def generate_reply(cls, context: str, style: str = "friendly") -> List[str]:
        """Generate smart reply suggestions."""
        system = f"""Generate 3 short reply suggestions for the following chat context.
Style: {style}
Return exactly 3 suggestions, one per line, no numbering."""
        
        result = await cls.chat(context, system)
        suggestions = [s.strip() for s in result.strip().split("\n") if s.strip()]
        return suggestions[:3]
    
    @classmethod
    async def rewrite_message(cls, message: str, variations: int = 3) -> List[str]:
        """Generate message variations."""
        system = f"""Rewrite this message {variations} different ways.
Keep the same meaning but vary the wording.
Return {variations} variations, one per line."""
        
        result = await cls.chat(message, system)
        variants = [s.strip() for s in result.strip().split("\n") if s.strip()]
        return variants[:variations] if variants else [message]
    
    @classmethod
    async def auto_reply(cls, incoming_message: str, user_context: str = "") -> str:
        """Generate contextual auto-reply."""
        system = f"""You are an AI assistant helping with auto-replies.
Context about the user: {user_context or 'None provided'}
Generate a brief, natural reply to the incoming message.
Keep it under 50 words."""
        
        return await cls.chat(incoming_message, system)
