"""
Session Backup Service
Backup and restore Telethon session.
"""
import os
import json
import base64
import shutil
from datetime import datetime
from typing import Optional, Dict
from app.redis_conn import RedisClient
from app.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__)

class SessionBackup:
    """
    Manages session backup and restore.
    """
    
    BACKUP_KEY = "session:backup"
    HISTORY_KEY = "session:history"
    
    @classmethod
    def _get_session_path(cls) -> str:
        """Get session file path."""
        return os.path.join(config.SESSION_PATH, f"{config.SESSION_NAME}.session")
    
    @classmethod
    async def backup(cls, to_redis: bool = True, to_file: bool = False) -> Dict:
        """Backup current session."""
        session_path = cls._get_session_path()
        
        if not os.path.exists(session_path):
            return {"success": False, "error": "Session file not found"}
        
        try:
            # Read session file
            with open(session_path, "rb") as f:
                session_data = f.read()
            
            encoded = base64.b64encode(session_data).decode()
            timestamp = datetime.utcnow().isoformat()
            
            backup_info = {
                "timestamp": timestamp,
                "size": len(session_data),
                "session_name": config.SESSION_NAME
            }
            
            # Save to Redis
            if to_redis:
                redis = RedisClient.get_instance()
                await redis.set(cls.BACKUP_KEY, encoded)
                await redis.lpush(cls.HISTORY_KEY, json.dumps(backup_info))
                await redis.ltrim(cls.HISTORY_KEY, 0, 9)  # Keep last 10
            
            # Save to file
            if to_file:
                backup_path = f"{session_path}.backup.{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(session_path, backup_path)
                backup_info["file_path"] = backup_path
            
            logger.info("Session backed up", **backup_info)
            return {"success": True, **backup_info}
            
        except Exception as e:
            logger.error("Backup failed", error=str(e))
            return {"success": False, "error": str(e)}
    
    @classmethod
    async def restore(cls, from_redis: bool = True) -> Dict:
        """Restore session from backup."""
        session_path = cls._get_session_path()
        
        try:
            if from_redis:
                redis = RedisClient.get_instance()
                encoded = await redis.get(cls.BACKUP_KEY)
                
                if not encoded:
                    return {"success": False, "error": "No backup found in Redis"}
                
                session_data = base64.b64decode(encoded)
                
                # Backup current before overwrite
                if os.path.exists(session_path):
                    shutil.copy2(session_path, f"{session_path}.pre-restore")
                
                # Write restored session
                with open(session_path, "wb") as f:
                    f.write(session_data)
                
                logger.info("Session restored from Redis")
                return {"success": True, "source": "redis"}
            
            return {"success": False, "error": "No restore source specified"}
            
        except Exception as e:
            logger.error("Restore failed", error=str(e))
            return {"success": False, "error": str(e)}
    
    @classmethod
    async def get_backup_history(cls) -> list:
        """Get backup history."""
        redis = RedisClient.get_instance()
        history = await redis.lrange(cls.HISTORY_KEY, 0, 9)
        return [json.loads(h) for h in history]
    
    @classmethod
    async def has_backup(cls) -> bool:
        """Check if backup exists."""
        redis = RedisClient.get_instance()
        return await redis.exists(cls.BACKUP_KEY)
