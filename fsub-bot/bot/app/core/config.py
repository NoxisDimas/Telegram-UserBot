"""
Pydantic Settings — centralised configuration loaded from environment variables.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings, sourced from env vars / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Telegram ─────────────────────────────────────────────
    API_ID: int
    API_HASH: str
    BOT_TOKEN: str
    BOT_USERNAME: str = "FsubBot"
    OWNER_ID: int

    # ── DB Channel (for content catalogue posts) ─────────────
    DB_CHANNEL_ID: int

    # ── PostgreSQL ───────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://fsub_user:change_me@localhost:5432/fsub_bot"
    )
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False

    # ── Redis ────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 20

    # ── Security ─────────────────────────────────────────────
    # (Deep links are now plain base64, no HMAC needed)

    # ── Rate Limiting ────────────────────────────────────────
    RATE_LIMIT_REQUESTS: int = 30
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # ── Worker ───────────────────────────────────────────────
    WORKER_CONCURRENCY: int = 4
    MAX_RETRIES: int = 3
    RETRY_BASE_DELAY: float = 2.0  # seconds, exponential backoff

    # ── Fsub Channels (comma-separated IDs) ──────────────────
    FSUB_CHANNEL_IDS: List[int] = []

    @field_validator("FSUB_CHANNEL_IDS", mode="before")
    @classmethod
    def parse_channel_ids(cls, v: object) -> List[int]:
        if isinstance(v, str):
            if not v.strip():
                return []
            return [int(cid.strip()) for cid in v.split(",") if cid.strip()]
        if isinstance(v, list):
            return [int(cid) for cid in v]
        return []


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached singleton Settings instance."""
    return Settings()  # type: ignore[call-arg]
