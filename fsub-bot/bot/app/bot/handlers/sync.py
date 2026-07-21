"""
Handler for two-way synchronization between Telegram Channel and Database.
Listens for deleted messages in the DB_CHANNEL and removes the corresponding Content.
"""

import logging
from hydrogram import Client, filters
from hydrogram.types import Message
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import get_session
from app.models.content import Content

logger = logging.getLogger(__name__)


@Client.on_deleted_messages(filters.chat(get_settings().DB_CHANNEL_ID))
async def on_channel_message_deleted(client: Client, messages: list[Message]):
    """
    When messages are deleted in the DB_CHANNEL, find their corresponding
    Content in the database and delete it to maintain two-way sync.
    """
    msg_ids = [m.id for m in messages]
    if not msg_ids:
        return

    async with get_session() as session:
        stmt = select(Content).where(Content.catalogue_msg_id.in_(msg_ids))
        result = await session.execute(stmt)
        contents = result.scalars().all()

        for content in contents:
            logger.info("Sync: Deleting content %s because message %s was deleted from channel", content.content_id, content.catalogue_msg_id)
            await session.delete(content)
        
        if contents:
            await session.commit()
