"""
Multi-Account Manager
Abstracts account/session handling for future scaling.
"""
import os
from typing import Optional, List
from telethon import TelegramClient
from app.config import config
from app.utils.logger import get_logger
from app.services.warmup import WarmupEngine
from app.services.risk_control import RiskControl, RiskLevel

logger = get_logger(__name__)

class AccountInfo:
    """Represents a managed account."""
    
    def __init__(self, session_id: str, client: TelegramClient):
        self.session_id = session_id
        self.client = client
        self.is_connected = False
    
    async def get_eligibility(self) -> dict:
        """Get account eligibility for tasks."""
        can_send, warmup_reason = await WarmupEngine.can_send(self.session_id)
        risk_level = await RiskControl.get_risk_level()
        
        return {
            "session_id": self.session_id,
            "can_send": can_send and risk_level != RiskLevel.FROZEN,
            "warmup_reason": warmup_reason,
            "risk_level": risk_level.value
        }


class AccountManager:
    """
    Manages multiple Telegram accounts/sessions.
    For now, supports single account with abstraction for future scaling.
    """
    
    _accounts: dict[str, AccountInfo] = {}
    _primary_session: str = None
    
    @classmethod
    async def initialize(cls):
        """Initialize account manager with configured sessions."""
        # For now, single account from config
        session_path = os.path.join(config.SESSION_PATH, config.SESSION_NAME)
        session_id = config.SESSION_NAME
        
        client = TelegramClient(
            session_path,
            config.TG_API_ID,
            config.TG_API_HASH
        )
        
        account = AccountInfo(session_id, client)
        cls._accounts[session_id] = account
        cls._primary_session = session_id
        
        # Initialize warm-up tracking
        await WarmupEngine.initialize_account(session_id)
        
        logger.info("Account manager initialized", accounts=len(cls._accounts))
    
    @classmethod
    async def get_primary_client(cls) -> TelegramClient:
        """Get the primary account client."""
        if cls._primary_session and cls._primary_session in cls._accounts:
            return cls._accounts[cls._primary_session].client
        return None
    
    @classmethod
    async def get_eligible_account(cls) -> Optional[AccountInfo]:
        """
        Get an eligible account for sending.
        Future: will select based on warm-up, risk, load.
        """
        for session_id, account in cls._accounts.items():
            eligibility = await account.get_eligibility()
            if eligibility["can_send"]:
                return account
        
        logger.warning("No eligible account found")
        return None
    
    @classmethod
    async def get_all_accounts(cls) -> List[AccountInfo]:
        """Get all managed accounts."""
        return list(cls._accounts.values())
    
    @classmethod
    async def start_all(cls):
        """Connect all accounts."""
        for session_id, account in cls._accounts.items():
            try:
                await account.client.connect()
                if await account.client.is_user_authorized():
                    account.is_connected = True
                    me = await account.client.get_me()
                    logger.info("Account connected", session_id=session_id, user_id=me.id)
                else:
                    logger.warning("Account not authorized", session_id=session_id)
            except Exception as e:
                logger.error("Failed to connect account", session_id=session_id, error=str(e))
    
    @classmethod
    async def stop_all(cls):
        """Disconnect all accounts."""
        for session_id, account in cls._accounts.items():
            try:
                await account.client.disconnect()
                account.is_connected = False
                logger.info("Account disconnected", session_id=session_id)
            except Exception as e:
                logger.error("Error disconnecting account", session_id=session_id, error=str(e))
