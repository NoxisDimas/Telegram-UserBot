"""
Media Downloader Service
Download and organize media from messages.
"""
import os
import asyncio
from datetime import datetime
from typing import Optional, Dict
from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from app.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__)

class MediaDownloader:
    """
    Download and organize media from Telegram messages.
    """
    
    DOWNLOAD_DIR = "/app/downloads"
    
    @classmethod
    def _ensure_dir(cls, path: str):
        """Ensure directory exists."""
        os.makedirs(path, exist_ok=True)
    
    @classmethod
    def _get_media_type(cls, message) -> str:
        """Determine media type from message."""
        if not message.media:
            return None
        
        if isinstance(message.media, MessageMediaPhoto):
            return "photos"
        
        if isinstance(message.media, MessageMediaDocument):
            doc = message.media.document
            
            if doc.mime_type:
                if doc.mime_type.startswith("video"):
                    return "videos"
                elif doc.mime_type.startswith("audio"):
                    return "audio"
                elif doc.mime_type.startswith("image"):
                    return "images"
            
            return "documents"
        
        return "other"
    
    @classmethod
    def _generate_filename(cls, message, media_type: str) -> str:
        """Generate filename for downloaded media."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        chat_id = abs(message.chat_id)
        msg_id = message.id
        
        return f"{timestamp}_{chat_id}_{msg_id}"
    
    @classmethod
    async def download(cls, client: TelegramClient, message, 
                      organize: bool = True) -> Optional[Dict]:
        """Download media from a message."""
        if not message.media:
            return {"success": False, "error": "No media in message"}
        
        try:
            media_type = cls._get_media_type(message)
            
            if organize:
                download_dir = os.path.join(cls.DOWNLOAD_DIR, media_type)
            else:
                download_dir = cls.DOWNLOAD_DIR
            
            cls._ensure_dir(download_dir)
            
            # Generate filename
            base_name = cls._generate_filename(message, media_type)
            
            # Download
            file_path = await client.download_media(
                message,
                file=os.path.join(download_dir, base_name)
            )
            
            if file_path:
                file_size = os.path.getsize(file_path)
                
                logger.info("Media downloaded", 
                          path=file_path, 
                          type=media_type,
                          size=file_size)
                
                return {
                    "success": True,
                    "path": file_path,
                    "type": media_type,
                    "size": file_size,
                    "message_id": message.id
                }
            
            return {"success": False, "error": "Download returned no path"}
            
        except Exception as e:
            logger.error("Download failed", error=str(e))
            return {"success": False, "error": str(e)}
    
    @classmethod
    async def download_from_reply(cls, client: TelegramClient, event) -> Optional[Dict]:
        """Download media from replied message."""
        reply = await event.get_reply_message()
        
        if not reply:
            return {"success": False, "error": "No reply message"}
        
        return await cls.download(client, reply)
    
    @classmethod
    def get_stats(cls) -> Dict:
        """Get download statistics."""
        stats = {"total_files": 0, "total_size": 0, "by_type": {}}
        
        if not os.path.exists(cls.DOWNLOAD_DIR):
            return stats
        
        for root, dirs, files in os.walk(cls.DOWNLOAD_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                size = os.path.getsize(file_path)
                
                stats["total_files"] += 1
                stats["total_size"] += size
                
                # Count by type (subdir)
                rel_dir = os.path.relpath(root, cls.DOWNLOAD_DIR)
                if rel_dir != ".":
                    stats["by_type"][rel_dir] = stats["by_type"].get(rel_dir, 0) + 1
        
        # Format size
        stats["total_size_mb"] = round(stats["total_size"] / (1024 * 1024), 2)
        
        return stats
    
    @classmethod
    async def cleanup_old(cls, days: int = 30) -> int:
        """Remove downloads older than N days."""
        import time
        
        if not os.path.exists(cls.DOWNLOAD_DIR):
            return 0
        
        cutoff = time.time() - (days * 86400)
        removed = 0
        
        for root, dirs, files in os.walk(cls.DOWNLOAD_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.getmtime(file_path) < cutoff:
                    os.remove(file_path)
                    removed += 1
        
        logger.info("Download cleanup", removed=removed)
        return removed
