import os
from dotenv import load_dotenv
from pydantic import ValidationError
from typing import Optional

# Load .env file for local development
load_dotenv()

class Config:
    """
    Application configuration loaded from environment variables.
    """
    # Telegram credentials
    TG_API_ID: int = int(os.getenv("TG_API_ID", 0))
    TG_API_HASH: str = os.getenv("TG_API_HASH", "")
    
    # Redis configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    
    # Application settings
    OWNER_SESSION_NAME: str = os.getenv("OWNER_SESSION_NAME", "owner")
    SESSION_PATH: str = os.getenv("SESSION_PATH", "session")
    
    # === Phase 2 Feature Flags ===
    
    # Warm-up Engine
    WARMUP_ENABLED: bool = os.getenv("WARMUP_ENABLED", "true").lower() == "true"
    
    # AI Rewrite
    ENABLE_AI_REWRITE: bool = os.getenv("ENABLE_AI_REWRITE", "false").lower() == "true"
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Time Window (0,0 = disabled)
    ACTIVE_HOURS_START: int = int(os.getenv("ACTIVE_HOURS_START", 0))
    ACTIVE_HOURS_END: int = int(os.getenv("ACTIVE_HOURS_END", 0))
    
    # Priority Queue
    PRIORITY_QUEUE_ENABLED: bool = os.getenv("PRIORITY_QUEUE_ENABLED", "true").lower() == "true"
    
    # === Phase 3 AI Features ===
    
    # Groq AI
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    AI_MODEL: str = os.getenv("AI_MODEL", "llama-3.3-70b-versatile")
    
    # Proxy (comma-separated: socks5://host:port,socks5://host:port)
    PROXY_LIST: str = os.getenv("PROXY_LIST", "")

    
    @classmethod
    def validate(cls):
        """Validates that required configuration is present."""
        if not cls.TG_API_ID or not cls.TG_API_HASH:
            raise ValueError("TG_API_ID and TG_API_HASH must be set in environment variables.")

# Create a global config instance (optional, or just use class)
config = Config()

