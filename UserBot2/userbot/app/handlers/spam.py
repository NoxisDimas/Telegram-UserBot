import asyncio
from telethon import events, TelegramClient
from app.utils.logger import get_logger
from app.worker import push_task
import uuid

logger = get_logger(__name__)

async def setup_spam(client: TelegramClient):
    """
    Sets up event handlers for spamming a specific user.
    """
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.spam (\d+) ([^\s]+) (.*)"))
    async def spam_handler(event):
        try:
            count = int(event.pattern_match.group(1))
            target = event.pattern_match.group(2)
            message = event.pattern_match.group(3)
        except Exception:
            await event.edit("❌ **Penggunaan:** `.spam <jumlah> <username/id> <pesan>`\nContoh: `.spam 50 @target Halo!`")
            return
            
        if count > 1000:
            await event.edit("❌ **Maksimal jumlah spam adalah 1000 pesan.**")
            return
            
        task_id = f"spam_{uuid.uuid4().hex[:8]}"
        
        # We push a single 'spam' task to the queue
        task_data = {
            "action": "spam",
            "task_id": task_id,
            "target_chat_id": target,
            "message": message,
            "count": count,
            "origin_chat_id": event.chat_id,
            "origin_message_id": event.message.id
        }
        
        await push_task(task_data, priority="high")
        await event.edit(f"🚀 **Tugas Spam Diterima!**\nTarget: `{target}`\nJumlah: `{count}` pesan\nPesan: `{message}`\n\nSedang diproses oleh barisan Worker...")
