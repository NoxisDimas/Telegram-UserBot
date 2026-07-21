import os
from telethon import TelegramClient
from app.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__)

class TelegramBotClient:
    owner_client: TelegramClient = None
    worker_clients: dict[str, TelegramClient] = {}

    @classmethod
    async def get_owner_client(cls) -> TelegramClient:
        """Returns the Telethon client instance for the owner."""
        return cls.owner_client

    @classmethod
    async def get_worker_clients(cls) -> dict[str, TelegramClient]:
        """Returns the dictionary of worker clients."""
        return cls.worker_clients

    @classmethod
    async def start(cls):
        """Starts all clients found in the session folder."""
        os.makedirs(config.SESSION_PATH, exist_ok=True)
        session_files = [f for f in os.listdir(config.SESSION_PATH) if f.endswith(".session")]
        
        if not session_files:
            logger.warning("No session files found. Please run gen_session.py first.")
            return

        for sf in session_files:
            session_name = sf.replace(".session", "")
            session_file_path = os.path.join(config.SESSION_PATH, session_name)
            
            client = TelegramClient(
                session_file_path,
                config.TG_API_ID,
                config.TG_API_HASH
            )
            
            await client.connect()
            
            if not await client.is_user_authorized():
                logger.warning(f"Session {session_name} not authorized. Skipping.")
                await client.disconnect()
                continue
                
            me = await client.get_me()
            logger.info(f"Client Connected: {session_name}", user_id=me.id, username=me.username)
            
            if session_name == config.OWNER_SESSION_NAME:
                cls.owner_client = client
            else:
                cls.worker_clients[session_name] = client
                
        if not cls.owner_client:
            logger.warning(f"Owner session ({config.OWNER_SESSION_NAME}.session) not found! Commands will not be received.")

    @classmethod
    async def stop(cls):
        """Stops all clients."""
        if cls.owner_client:
            await cls.owner_client.disconnect()
        for client in cls.worker_clients.values():
            await client.disconnect()
        logger.info("All Telegram Clients Disconnected")
