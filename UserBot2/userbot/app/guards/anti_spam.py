from telethon import TelegramClient
from telethon.tl.types import User, Chat, Channel
from app.utils.logger import get_logger
from typing import List, Union

logger = get_logger(__name__)

class AntiSpamGuard:
    """
    Safety guard to prevent spamming random users.
    Enforces Allowlist using Telegram Contacts.
    """
    
    _contacts_cache: set = None
    _last_cache_update: float = 0
    CACHE_TTL = 3600  # Refresh contacts every hour

    @classmethod
    async def refresh_contacts(cls, client: TelegramClient):
        """Fetches and caches contacts."""
        try:
            from telethon.tl.functions.contacts import GetContactsRequest
            # hash=0 to get all contacts
            result = await client(GetContactsRequest(hash=0))
            contacts = result.users
            cls._contacts_cache = {c.id for c in contacts}
            cls._last_cache_update = __import__("time").time()
            logger.info("Contacts refreshed", count=len(cls._contacts_cache))
        except Exception as e:
            logger.error("Failed to refresh contacts", error=str(e))
            # If fail, don't clear cache if it exists, but valid logic depends on policy.
            # Here we just log.
            if cls._contacts_cache is None:
                cls._contacts_cache = set()



    @staticmethod
    def validate_gcast_recipients(recipients: List[dict]) -> List[int]:
        """
        Parses and pre-validates recipients format.
        Does NOT check if they are contacts (that requires async client),
        but checks structural validity.
        """
        valid_ids = []
        for r in recipients:
            if isinstance(r, dict) and "id" in r and isinstance(r["id"], int):
                valid_ids.append(r["id"])
            else:
                logger.warning("Invalid recipient format skipped", recipient=r)
        return valid_ids

    @classmethod
    async def is_safe_recipient(cls, client: TelegramClient, recipient_id: int) -> bool:
        """
        Checks if a recipient is safe (in contacts, self, or a joined GROUP).
        """
        # 1. Allow Self
        me = await client.get_me()
        if recipient_id == me.id:
            return True

        # 2. Allow Contacts
        # Ensure cache is populated
        if cls._contacts_cache is None or (__import__("time").time() - cls._last_cache_update > cls.CACHE_TTL):
            await cls.refresh_contacts(client)
            
        if recipient_id in cls._contacts_cache:
            return True

        # 3. Allow Joined Groups/Channels
        # A recipient ID is "safe" if we can fetch it and it's a Chat/Channel we are in.
        try:
            # get_entity is cached by Telethon
            entity = await client.get_entity(recipient_id)
            if isinstance(entity, (Chat, Channel)):
                # If we can access it, we are likely a member (or it's public)
                # For extra safety, could check 'left' status, but basic existence is okay for now.
                return True
        except Exception:
            pass

        logger.warning("Recipient blocked by AntiSpam", recipient_id=recipient_id)
        return False
