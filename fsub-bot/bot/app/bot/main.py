"""
Bot entry point — creates the Hydrogram Client and loads handler plugins.
"""

from __future__ import annotations

import logging

from hydrogram import Client

from app.core.config import get_settings
from app.core.database import close_db, init_db
from app.core.redis import close_redis, get_redis

logger = logging.getLogger(__name__)


def create_bot() -> Client:
    """Instantiate and configure the Hydrogram bot client."""
    settings = get_settings()

    bot = Client(
        name="fsub_bot",
        api_id=settings.API_ID,
        api_hash=settings.API_HASH,
        bot_token=settings.BOT_TOKEN,
        plugins=dict(root="app.bot.handlers"),
        workdir=".",
    )

    return bot


async def on_startup(bot: Client) -> None:
    """Lifecycle hook — called before the bot starts polling."""
    logger.info("Initialising database connection pool...")
    await init_db()

    logger.info("Connecting to Redis...")
    await get_redis()

    # Ensure owner is registered
    settings = get_settings()
    from app.core.database import get_session
    from app.services.auth_service import get_or_create_user
    from app.models.user import UserRole

    async with get_session() as session:
        owner = await get_or_create_user(
            session, settings.OWNER_ID, username=None, first_name="Owner"
        )
        if owner.role != UserRole.OWNER:
            owner.role = UserRole.OWNER
            session.add(owner)

    me = await bot.get_me()
    logger.info("Bot started as @%s (ID: %d)", me.username, me.id)


async def on_shutdown(bot: Client) -> None:
    """Lifecycle hook — called after the bot stops."""
    logger.info("Closing database connections...")
    await close_db()

    logger.info("Closing Redis connection...")
    await close_redis()

    logger.info("Bot shutdown complete.")
