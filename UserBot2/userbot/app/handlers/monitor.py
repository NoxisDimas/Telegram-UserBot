from telethon import events, TelegramClient
from app.redis_conn import RedisClient
from app.utils.logger import get_logger
import json
import uuid
import asyncio

logger = get_logger(__name__)

# This could be loaded from Redis or Config
MONITOR_CHATS = [] # Populate with chat IDs if static, or dynamic logic
KEYWORDS = []

async def setup_monitor(client: TelegramClient):
    """
    Sets up event handlers for monitoring messages.
    """
    
    # Example: In a real orchestrator system, these configs might come from Redis 
    # and we would refresh them. For this worker, we'll demonstrate a generic handler.
    # The requirement says "Listen only to allowed chats... Apply keyword filters".
    
    @client.on(events.NewMessage(incoming=True))
    async def incoming_message_handler(event):
        try:
            chat_id = event.chat_id
            text = event.message.message or ""
            
            # 1. Filter Check (Placeholder logic - strictly speaking this should be dynamic)
            # For demo, we log all non-private messages or specific ones
            if event.is_private:
                return # Ignore DMs unless specified
                
            # 2. Keyword Filter
            # if not any(k in text.lower() for k in KEYWORDS):
            #     return

            # 3. Push to Redis
            data = {
                "event": "new_message",
                "chat_id": chat_id,
                "sender_id": event.sender_id,
                "text": text,
                "message_id": event.message.id,
                "timestamp": event.date.isoformat()
            }
            
            redis = RedisClient.get_instance()
            await redis.lpush("userbot:monitor_events", json.dumps(data))
            logger.info("Monitored message pushed to Redis", chat_id=chat_id)
            
        except Exception as e:
            logger.error("Error in monitor handler", error=str(e))

    logger.info("Monitor handlers registered")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.info(?: (task))?$"))
    async def info_handler(event):
        """Handle .info and .info task command"""
        try:
            is_task = event.pattern_match.group(1) == "task"
            
            if is_task:
                tasks = [t for t in asyncio.all_tasks() if not t.done()]
                task_names = []
                for t in tasks:
                    coro = t.get_coro()
                    coro_name = coro.__name__ if hasattr(coro, '__name__') else str(coro)
                    # Tampilkan task yang relevan (misal scraper, gcast, dsb)
                    if any(x in coro_name for x in ['scrape', 'gcast', 'worker', 'Task']):
                        task_names.append(f"• `{coro_name}`")
                
                if not task_names:
                    task_info = "✅ Tidak ada background task yang sedang berjalan."
                else:
                    task_info = "\n".join(task_names)
                    
                info_text = (
                    f"**📋 Active Tasks Info**\n\n"
                    f"**Background Processes:**\n"
                    f"{task_info}\n\n"
                    f"-- Ketik `.info` untuk kembali melihat status bot --"
                )
            else:
                me = await client.get_me()
                info_text = (
                    f"**🤖 Userbot Worker Status**\n"
                    f"✅ Connected as: `{me.first_name}`\n"
                    f"🆔 ID: `{me.id}`\n"
                    f"⚡ System: `Redis-driven Worker`\n\n"
                    f"-- Ketik `.info task` untuk melihat task yang berjalan --"
                )
                
            reply_msg = await event.reply(info_text)
            
            # Wait 30 seconds
            await asyncio.sleep(30)
            
            # Delete both response and command
            await asyncio.gather(
                reply_msg.delete(),
                event.delete()
            )
        except Exception as e:
            logger.error("Info command failed", error=str(e))

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.gcast (.+)"))
    async def gcast_handler(event):
        """Handle .gcast <message> command"""
        try:    
            message_text = event.pattern_match.group(1)
            await event.edit(f"🚀 **Starting Gcast...**\n`{message_text}`")
            
            # 1. Fetch Joined Groups
            dialogs = await client.get_dialogs()
            groups = []
            for d in dialogs:
                if d.is_group:
                    # Explicitly exclude broadcast channels even if is_group is True (paranoid check)
                    if getattr(d.entity, 'broadcast', False):
                        continue
                    groups.append(d.entity)
            
            recipients = [{"type": "chat", "id": g.id} for g in groups]
            count = len(recipients)
            
            if count == 0:
                await event.reply("⚠️ No groups found to broadcast.")
                return

            # 2. Create Redis Task
            task_id = str(uuid.uuid4())
            task = {
                "task_id": task_id,
                "action": "safe_gcast",
                "message": message_text,
                "recipients": recipients,
                "limits": {"per_hour": 100}, # Allow higher limit for explicit user command
                "delay_range": [5, 15], # Safe delay
                "origin_chat_id": event.chat_id,
                "origin_message_id": event.message.id
            }
            
            redis = RedisClient.get_instance()
            await redis.lpush("userbot:queue", json.dumps(task))
            
            repply = await event.reply(
                f"✅ **Gcast Queue Created!**\n"
                f"🎯 Targets: `{count}` chats\n"
                f"🔑 Task ID: `{task_id}`\n"
                f"Check logs for progress."
            )
            logger.info("Gcast command received", count=count, task_id=task_id)

            await asyncio.sleep(30)
            
            await asyncio.gather(
                repply.delete(),
                event.delete()
            )
            
        except Exception as e:
            logger.error("Gcast command failed", error=str(e))
            await event.reply(f"❌ **Gcast Failed**: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.status$"))
    async def status_handler(event):
        """Handle .status command - show system status"""
        try:
            from app.services.risk_control import RiskControl
            from app.services.time_window import TimeWindow
            from app.services.kill_switch import KillSwitch
            from app.services.warmup import WarmupEngine
            from app.config import config
            
            # Get all statuses
            risk_level = await RiskControl.get_risk_level()
            can_proceed, risk_reason = await RiskControl.can_proceed()
            time_status = TimeWindow.get_status()
            kill_status = await KillSwitch.get_status()
            warmup_stats = await WarmupEngine.get_stats(config.SESSION_NAME)
            
            status_text = (
                f"**📊 System Status**\n\n"
                f"🔐 **Warm-Up**\n"
                f"  Stage: `{warmup_stats['stage']}`\n"
                f"  Sent Today: `{warmup_stats['messages_sent_today']}/{warmup_stats['limit']}`\n\n"
                f"⚠️ **Risk Control**\n"
                f"  Level: `{risk_level.value}`\n"
                f"  Can Proceed: `{can_proceed}`\n\n"
                f"⏱️ **Time Window**\n"
                f"  Active Hours: `{time_status['active_hours']}`\n"
                f"  Current: `{time_status['current_hour']}`\n"
                f"  Is Active: `{time_status['is_active']}`\n\n"
                f"🧯 **Kill Switch**\n"
                f"  Active: `{kill_status['active']}`"
            )
            
            await event.reply(status_text)
            await event.delete()
        except Exception as e:
            logger.error("Status command failed", error=str(e))
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.warmup$"))
    async def warmup_handler(event):
        """Handle .warmup command - show warm-up stats"""
        try:
            from app.services.warmup import WarmupEngine
            from app.config import config
            
            stats = await WarmupEngine.get_stats(config.SESSION_NAME)
            
            warmup_text = (
                f"**🔐 Warm-Up Status**\n\n"
                f"📅 Created: `{stats['created_at']}`\n"
                f"📈 Stage: `{stats['stage']}`\n"
                f"📤 Sent Today: `{stats['messages_sent_today']}`\n"
                f"🎯 Daily Limit: `{stats['limit']}`\n"
                f"📆 Last Reset: `{stats['last_reset_date']}`"
            )
            
            await event.reply(warmup_text)
        except Exception as e:
            logger.error("Warmup command failed", error=str(e))
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.kill$"))
    async def kill_handler(event):
        """Handle .kill command - toggle kill switch"""
        try:
            from app.services.kill_switch import KillSwitch
            
            is_active = await KillSwitch.is_active()
            
            if is_active:
                await KillSwitch.deactivate()
                await event.reply("✅ **Kill Switch Deactivated**\nWorker will resume processing.")
            else:
                await KillSwitch.activate("Manual trigger via .kill command")
                await event.reply("🛑 **Kill Switch Activated**\nAll tasks paused immediately.")
                
        except Exception as e:
            logger.error("Kill command failed", error=str(e))
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.risk reset$"))
    async def risk_reset_handler(event):
        """Handle .risk reset command - reset risk control"""
        try:
            from app.services.risk_control import RiskControl
            
            await RiskControl.reset()
            await event.reply("✅ **Risk Control Reset**\nLevel set to LOW, cooldowns cleared.")
                
        except Exception as e:
            logger.error("Risk reset command failed", error=str(e))
            await event.reply(f"❌ Error: {str(e)}")

    # === Phase 3 AI Commands ===

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.summarize(?:\s+(\d+))?$"))
    async def summarize_handler(event):
        """Handle .summarize [count] command"""
        try:
            from app.services.ai.summarizer import Summarizer
            
            count = int(event.pattern_match.group(1) or 100)
            await event.edit("🔄 Summarizing...")
            
            summary = await Summarizer.summarize_chat(event.chat_id, count)
            await event.reply(f"📝 **Chat Summary**\n\n{summary}")
            
        except Exception as e:
            logger.error("Summarize failed", error=str(e))
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.suggest$"))
    async def suggest_handler(event):
        """Handle .suggest command - get AI reply suggestions"""
        try:
            from app.services.ai.smart_reply import SmartReply
            from app.services.ai.summarizer import Summarizer
            
            await event.edit("💭 Generating suggestions...")
            
            messages = await Summarizer.get_recent_messages(event.chat_id, 10)
            suggestions = await SmartReply.get_suggestions_for_chat(messages)
            
            text = "**💬 Reply Suggestions**\n\n"
            for i, s in enumerate(suggestions, 1):
                text += f"{i}. `{s}`\n"
            
            await event.reply(text)
            
        except Exception as e:
            logger.error("Suggest failed", error=str(e))
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.mood$"))
    async def mood_handler(event):
        """Handle .mood command - analyze chat sentiment"""
        try:
            from app.services.ai.sentiment import SentimentAnalyzer
            from app.services.ai.summarizer import Summarizer
            
            await event.edit("😊 Analyzing mood...")
            
            messages = await Summarizer.get_recent_messages(event.chat_id, 30)
            result = await SentimentAnalyzer.analyze_chat(event.chat_id, messages)
            trend = await SentimentAnalyzer.get_trend(event.chat_id)
            
            emoji = {"positive": "😊", "negative": "😟", "neutral": "😐"}.get(result.get("sentiment"), "❓")
            
            text = (
                f"**{emoji} Chat Mood Analysis**\n\n"
                f"Sentiment: `{result.get('sentiment', 'unknown')}`\n"
                f"Score: `{result.get('score', 0.5):.2f}`\n"
                f"Trend (24h): `{trend['trend']}` ({trend['avg_score']:.2f})\n\n"
                f"📝 {result.get('summary', 'No summary')}"
            )
            
            await event.reply(text)
            
        except Exception as e:
            logger.error("Mood failed", error=str(e))
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.stats$"))
    async def stats_handler(event):
        """Handle .stats command - show chat analytics"""
        try:
            from app.services.analytics import Analytics
            
            stats = await Analytics.get_stats(event.chat_id)
            top_users = await Analytics.get_top_users(event.chat_id, 5)
            
            users_text = "\n".join([f"  • {u['name']}: `{u['message_count']}`" for u in top_users])
            
            text = (
                f"**📊 Chat Analytics**\n\n"
                f"📈 Total: `{stats['total_messages']}`\n"
                f"📅 Today: `{stats['today_messages']}`\n"
                f"⏰ Peak Hour: `{stats['peak_hour']}`\n\n"
                f"**👥 Top Users**\n{users_text or '  No data'}"
            )
            
            await event.reply(text)
            
        except Exception as e:
            logger.error("Stats failed", error=str(e))
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.health$"))
    async def health_handler(event):
        """Handle .health command - show account health"""
        try:
            from app.services.health_monitor import HealthMonitor
            
            report = await HealthMonitor.get_health_report()
            await event.reply(report)
            
        except Exception as e:
            logger.error("Health failed", error=str(e))
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.afk(?:\s+(.+))?$"))
    async def afk_handler(event):
        """Handle .afk [reason] command"""
        try:
            from app.services.afk import AFKMode
            
            reason = event.pattern_match.group(1) or ""
            await AFKMode.enable(reason)
            
            await event.reply(f"⏸️ **AFK Mode Enabled**\n{reason or 'No reason specified'}")
            
        except Exception as e:
            logger.error("AFK failed", error=str(e))
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.back$"))
    async def back_handler(event):
        """Handle .back command - disable AFK"""
        try:
            from app.services.afk import AFKMode
            
            result = await AFKMode.disable()
            mentions = result.get("missed_mentions", [])
            
            text = f"✅ **Welcome Back!**\n\n"
            if mentions:
                text += f"📬 Missed Mentions: `{len(mentions)}`\n"
                for m in mentions[:5]:
                    text += f"  • {m['sender_name']} in {m['chat_name']}\n"
            else:
                text += "No missed mentions."
            
            await event.reply(text)
            
        except Exception as e:
            logger.error("Back failed", error=str(e))
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.schedule\s+(\S+)\s+(.+)$"))
    async def schedule_handler(event):
        """Handle .schedule <time> <message> command"""
        try:
            from app.services.scheduler import Scheduler
            
            delay = event.pattern_match.group(1)
            message = event.pattern_match.group(2)
            
            result = await Scheduler.schedule(event.chat_id, message, delay)
            
            if result["success"]:
                await event.reply(
                    f"⏰ **Message Scheduled**\n"
                    f"🆔 Task: `{result['task_id']}`\n"
                    f"⏱️ Delay: `{result['delay']}`"
                )
            else:
                await event.reply(f"❌ {result['error']}")
            
        except Exception as e:
            logger.error("Schedule failed", error=str(e))
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.download(?: |$)(.*)"))
    async def download_handler(event):
        """Handle .download command - save replied media or link to Saved Messages via local server"""
        try:
            import os
            import tempfile
            import re
            
            args_str = event.pattern_match.group(1).strip()
            messages_to_process = []
            processed_ids = set()
            
            # If arguments are provided, parse them as links
            if args_str:
                links = args_str.split()
                for link in links:
                    private_match = re.search(r'(?:t\.me|telegram\.me|telegram\.dog)/c/(\d+)/(\d+)', link)
                    public_match = re.search(r'(?:t\.me|telegram\.me|telegram\.dog)/([a-zA-Z0-9_]+)/(\d+)', link)
                    
                    chat_id = None
                    msg_id = None
                    if private_match:
                        chat_id = int(f"-100{private_match.group(1)}")
                        msg_id = int(private_match.group(2))
                    elif public_match:
                        chat_id = public_match.group(1)
                        msg_id = int(public_match.group(2))
                    
                    if chat_id and msg_id:
                        try:
                            msgs = await client.get_messages(chat_id, ids=[msg_id])
                            if msgs and msgs[0] and msgs[0].media:
                                target_msg = msgs[0]
                                if target_msg.grouped_id:
                                    # Fetch surrounding messages to get the whole album
                                    history = await client.get_messages(chat_id, limit=20, offset_id=target_msg.id+10)
                                    for m in history:
                                        if m.grouped_id == target_msg.grouped_id and m.media:
                                            key = f"{chat_id}_{m.id}"
                                            if key not in processed_ids:
                                                messages_to_process.append(m)
                                                processed_ids.add(key)
                                else:
                                    key = f"{chat_id}_{target_msg.id}"
                                    if key not in processed_ids:
                                        messages_to_process.append(target_msg)
                                        processed_ids.add(key)
                        except Exception as e:
                            logger.error(f"Failed to get message from link {link}", error=str(e))
                            
                if not messages_to_process:
                    await event.edit("❌ Gagal mendapatkan media dari link yang diberikan.")
                    return
            else:
                # Fallback to reply
                reply = await event.get_reply_message()
                if not reply or not reply.media:
                    await event.edit("❌ Harap reply ke pesan yang berisi media atau berikan link pesan.")
                    return
                
                if reply.grouped_id:
                    # Ambil seluruh album dari chat yang sama
                    chat_id = event.chat_id
                    history = await client.get_messages(chat_id, limit=20, offset_id=reply.id+10)
                    for m in history:
                        if m.grouped_id == reply.grouped_id and m.media:
                            key = f"{chat_id}_{m.id}"
                            if key not in processed_ids:
                                messages_to_process.append(m)
                                processed_ids.add(key)
                else:
                    messages_to_process.append(reply)
            
            # Sort messages chronological so album items upload in correct order
            messages_to_process.sort(key=lambda x: x.id)
            
            temp_dir = os.path.join(tempfile.gettempdir(), "userbot_downloads")
            os.makedirs(temp_dir, exist_ok=True)
            
            status_msg = await event.edit(f"📥 Sedang memproses {len(messages_to_process)} media...")
            
            success_count = 0
            for i, msg in enumerate(messages_to_process, 1):
                await status_msg.edit(f"📥 Mendownload media {i}/{len(messages_to_process)}...")
                file_path = await msg.download_media(file=temp_dir + "/")
                
                if file_path:
                    await status_msg.edit(f"📤 Mengupload media {i}/{len(messages_to_process)} ke Telegram...")
                    # Truncate caption if too long
                    cap = msg.message or ""
                    if len(cap) > 1000:
                        cap = cap[:1000] + "..."
                    await client.send_file('me', file_path, caption=cap)
                    
                    os.remove(file_path)
                    success_count += 1
                    
            if success_count > 0:
                await status_msg.edit(f"✅ **{success_count} Media berhasil diproses dan disimpan ke Saved Messages!**")
            else:
                await status_msg.edit("❌ Gagal memproses media.")
            
        except Exception as e:
            logger.error("Download failed", error=str(e))
            await event.edit(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.backup$"))
    async def backup_handler(event):
        """Handle .backup command - backup session"""
        try:
            from app.services.session_backup import SessionBackup
            
            await event.edit("💾 Backing up...")
            
            result = await SessionBackup.backup(to_redis=True)
            
            if result["success"]:
                await event.reply(
                    f"✅ **Session Backed Up**\n"
                    f"📦 Size: `{result['size']} bytes`\n"
                    f"⏰ Time: `{result['timestamp']}`"
                )
            else:
                await event.reply(f"❌ {result['error']}")
            
        except Exception as e:
            logger.error("Backup failed", error=str(e))
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.autoreply\s+(on|off|ai)$"))
    async def autoreply_toggle_handler(event):
        """Handle .autoreply on/off/ai command"""
        try:
            from app.services.auto_reply import AutoReply
            
            mode = event.pattern_match.group(1)
            
            if mode == "on":
                await AutoReply.set_away_mode(True)
                await event.reply("✅ Auto-reply enabled (away mode)")
            elif mode == "off":
                await AutoReply.set_away_mode(False)
                await AutoReply.set_ai_mode(False)
                await event.reply("❌ Auto-reply disabled")
            elif mode == "ai":
                await AutoReply.set_ai_mode(True)
                await event.reply("🤖 AI auto-reply enabled")
            
        except Exception as e:
            logger.error("Autoreply toggle failed", error=str(e))
            await event.reply(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.getid(?: (.*))?$"))
    async def get_id_handler(event):
        """Handle .getid command - get ID from username/link or reply"""
        try:
            target = event.pattern_match.group(1)
            
            if not target:
                reply = await event.get_reply_message()
                if reply:
                    sender = await reply.get_sender()
                    if sender:
                        target = sender
                    else:
                        await event.edit("❌ Tidak dapat menemukan informasi pengirim.")
                        return
                else:
                    target = event.chat_id
            else:
                target = target.strip()
                import re
                
                # Coba parse jika berupa link Telegram
                # Format 1: t.me/c/1234567/123 (private channel/group)
                private_match = re.search(r'(?:t\.me|telegram\.me|telegram\.dog)/c/(\d+)', target)
                if private_match:
                    target = int(f"-100{private_match.group(1)}")
                else:
                    # Format 2: t.me/username/123 (public channel/group) atau t.me/username
                    public_match = re.search(r'(?:t\.me|telegram\.me|telegram\.dog)/([a-zA-Z0-9_]+)', target)
                    if public_match:
                        target = public_match.group(1)
                    else:
                        # Coba cek apakah user input berupa angka (ID manual)
                        if target.lstrip('-').isdigit():
                            target = int(target)
            
            await event.edit("🔍 Mencari ID...")
            
            try:
                from telethon import utils
                entity = await client.get_entity(target)
                
                name = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
                if getattr(entity, 'last_name', None):
                    name += f" {entity.last_name}"
                    
                username = getattr(entity, 'username', 'Tidak ada')
                entity_id = entity.id
                peer_id = utils.get_peer_id(entity)
                
                text = (
                    f"**ℹ️ Informasi ID**\n"
                    f"**Nama:** `{name}`\n"
                    f"**Username:** `@{username}`\n"
                    f"**Peer ID:** `{peer_id}`"
                )
                await event.edit(text)
                
            except ValueError:
                await event.edit("❌ Username/Link tidak valid atau belum pernah diakses oleh akun Anda.")
                
        except Exception as e:
            logger.error("Get ID failed", error=str(e))
            await event.edit(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.help$"))
    async def help_handler(event):
        """Handle .help command - show all commands"""
        help_text = """
**📖 Command Reference**

**System**
`.info [task]` - Bot & Task status
`.status` - Full system status
`.health` - Account health & risk
`.kill` - Toggle kill switch
`.risk reset` - Reset risk level

**Warm-Up**
`.warmup` - Show warm-up stats

**Broadcasting**
`.gcast <msg>` - Broadcast to groups

**AI Features**
`.summarize [N]` - Summarize last N messages
`.suggest` - AI reply suggestions
`.mood` - Chat sentiment analysis

**Analytics**
`.stats` - Chat statistics

**Utility**
`.getid [username/link]` - Get Chat/User ID
`.schedule <time> <msg>` - Schedule message
`.download` - Download replied media
`.scrapemedia <id> <limit> [date]` - Scrape media to Saved Messages
`.backup` - Backup session
`.afk [reason]` - Enable AFK
`.back` - Disable AFK

**Auto-Reply**
`.autoreply on` - Away mode
`.autoreply ai` - AI mode
`.autoreply off` - Disable
"""
        await event.reply(help_text)



