"""
Admin command handlers — /stats, /health, /queue, /logs, /setrole, /ban, /unban, /broadcast.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from hydrogram import Client, filters
from hydrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked
from hydrogram.types import Message
from sqlalchemy import func, select

from app.bot.filters.permissions import IsAdmin, IsOwner, IsStaff
from app.core.database import get_session
from app.core.redis import ping_redis, get_redis
from app.models import AccessLog, AuditLog, Job, JobStatus, User
from app.services.auth_service import get_user, get_all_user_ids, set_user_role, ban_user, unban_user
from app.services.content_service import get_content_stats
from app.models.user import UserRole

logger = logging.getLogger(__name__)


# ── /stats — System statistics ───────────────────────────────

@Client.on_message(filters.command("stats") & filters.private & IsStaff)
async def stats_handler(client: Client, message: Message) -> None:
    """Show high-level system statistics."""
    async with get_session() as session:
        # User counts
        total_users = await session.scalar(
            select(func.count()).select_from(User)
        )
        banned_users = await session.scalar(
            select(func.count()).select_from(User).where(User.is_banned.is_(True))
        )

        # Content stats
        content_stats = await get_content_stats(session)

        text = (
            "📊 **Bot Statistics**\n\n"
            f"👥 **Users:** {total_users} (banned: {banned_users})\n"
            f"📁 **Content:** {content_stats['total_content']} items "
            f"({content_stats['total_files']} files)\n"
            f"📥 **Access Attempts:** {content_stats['total_accesses']}\n"
            f"✅ **Successful:** {content_stats['successful_accesses']}\n"
        )

    await message.reply(text)


# ── /health — Service health check ──────────────────────────

@Client.on_message(filters.command("health") & filters.private & IsAdmin)
async def health_handler(client: Client, message: Message) -> None:
    """Check the health of all backend services."""
    # Database
    db_ok = False
    try:
        async with get_session() as session:
            await session.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
            db_ok = True
    except Exception as exc:
        logger.error("DB health check failed: %s", exc)

    # Redis
    redis_ok = await ping_redis()

    status_emoji = lambda ok: "✅" if ok else "❌"
    text = (
        "🏥 **Health Check**\n\n"
        f"{status_emoji(db_ok)} PostgreSQL: {'Connected' if db_ok else 'Down'}\n"
        f"{status_emoji(redis_ok)} Redis: {'Connected' if redis_ok else 'Down'}\n"
        f"\n⏰ Server time: `{datetime.now(timezone.utc).isoformat()}`"
    )

    await message.reply(text)


# ── /queue — Pending jobs overview ───────────────────────────

@Client.on_message(filters.command("queue") & filters.private & IsAdmin)
async def queue_handler(client: Client, message: Message) -> None:
    """Show pending and failed job counts."""
    async with get_session() as session:
        pending = await session.scalar(
            select(func.count()).select_from(Job)
            .where(Job.status == JobStatus.PENDING)
        )
        processing = await session.scalar(
            select(func.count()).select_from(Job)
            .where(Job.status == JobStatus.PROCESSING)
        )
        failed = await session.scalar(
            select(func.count()).select_from(Job)
            .where(Job.status == JobStatus.FAILED)
        )
        dead = await session.scalar(
            select(func.count()).select_from(Job)
            .where(Job.status == JobStatus.DEAD)
        )

    # Also check Redis queue length
    try:
        redis = await get_redis()
        redis_queue_len = await redis.llen("job_queue")
    except Exception:
        redis_queue_len = "?"

    text = (
        "📋 **Job Queue**\n\n"
        f"⏳ Pending: {pending}\n"
        f"⚙️ Processing: {processing}\n"
        f"❌ Failed: {failed}\n"
        f"💀 Dead (DLQ): {dead}\n"
        f"\n📮 Redis queue length: {redis_queue_len}"
    )

    await message.reply(text)


# ── /logs — Recent audit logs ────────────────────────────────

@Client.on_message(filters.command("logs") & filters.private & IsAdmin)
async def logs_handler(client: Client, message: Message) -> None:
    """Show the 15 most recent audit log entries."""
    async with get_session() as session:
        result = await session.execute(
            select(AuditLog)
            .order_by(AuditLog.timestamp.desc())
            .limit(15)
        )
        logs = result.scalars().all()

    if not logs:
        await message.reply("📝 No audit logs yet.")
        return

    lines = ["📝 **Recent Audit Logs**\n"]
    for log in logs:
        ts = log.timestamp.strftime("%m-%d %H:%M") if log.timestamp else "?"
        lines.append(
            f"`{ts}` | **{log.action}** | "
            f"actor=`{log.actor_id}` target=`{log.target or '-'}`"
        )

    await message.reply("\n".join(lines))


# ── /setrole — Change user role ──────────────────────────────

@Client.on_message(filters.command("setrole") & filters.private & IsAdmin)
async def setrole_handler(client: Client, message: Message) -> None:
    """Set a user's role. Usage: /setrole <user_id> <ROLE>"""
    parts = message.text.strip().split()
    if len(parts) < 3:
        await message.reply(
            "Usage: `/setrole <user_id> <ROLE>`\n"
            "Roles: `ADMIN`, `STAFF`, `USER`"
        )
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.reply("❌ Invalid user ID.")
        return

    role_str = parts[2].upper()
    try:
        new_role = UserRole(role_str)
    except ValueError:
        await message.reply(f"❌ Invalid role `{role_str}`. Use: ADMIN, STAFF, USER")
        return

    async with get_session() as session:
        success = await set_user_role(
            session, message.from_user.id, target_id, new_role
        )

    if success:
        await message.reply(f"✅ User `{target_id}` role set to **{new_role.value}**.")
    else:
        await message.reply("❌ Permission denied or user not found.")


# ── /ban & /unban ────────────────────────────────────────────

@Client.on_message(filters.command("ban") & filters.private & IsAdmin)
async def ban_handler(client: Client, message: Message) -> None:
    """Ban a user. Usage: /ban <user_id>"""
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.reply("Usage: `/ban <user_id>`")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.reply("❌ Invalid user ID.")
        return

    async with get_session() as session:
        success = await ban_user(session, message.from_user.id, target_id)

    if success:
        await message.reply(f"🚫 User `{target_id}` has been **banned**.")
    else:
        await message.reply("❌ Permission denied or user not found.")


@Client.on_message(filters.command("unban") & filters.private & IsAdmin)
async def unban_handler(client: Client, message: Message) -> None:
    """Unban a user. Usage: /unban <user_id>"""
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.reply("Usage: `/unban <user_id>`")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.reply("❌ Invalid user ID.")
        return

    async with get_session() as session:
        success = await unban_user(session, message.from_user.id, target_id)

    if success:
        await message.reply(f"✅ User `{target_id}` has been **unbanned**.")
    else:
        await message.reply("❌ Permission denied or user not found.")


# ── /broadcast — Send message to all users ──────────────────

async def _do_broadcast(client: Client, from_message: Message, text_msg: str | None) -> None:
    """Background task: send a message to every known user."""
    async with get_session() as session:
        user_ids = await get_all_user_ids(session)

    total = len(user_ids)
    success = 0
    failed = 0

    logger.info("Broadcast started: %d users", total)

    for uid in user_ids:
        try:
            if text_msg:
                await client.send_message(uid, text_msg)
            else:
                await from_message.copy(uid)
            success += 1
        except FloodWait as e:
            logger.warning("FloodWait %ds while broadcasting, sleeping...", e.value)
            await asyncio.sleep(e.value)
            try:
                if text_msg:
                    await client.send_message(uid, text_msg)
                else:
                    await from_message.copy(uid)
                success += 1
            except Exception:
                failed += 1
        except (UserIsBlocked, InputUserDeactivated):
            failed += 1
        except Exception as exc:
            logger.warning("Broadcast to %d failed: %s", uid, exc)
            failed += 1

        # Respect Telegram rate limits (~20 msg/s max, we use ~18 msg/s)
        await asyncio.sleep(0.055)

    logger.info("Broadcast done: success=%d failed=%d", success, failed)

    # Send summary back to the admin who triggered it
    try:
        await client.send_message(
            from_message.chat.id,
            f"✅ **Broadcast selesai!**\n\n"
            f"📊 Total pengguna: **{total}**\n"
            f"✔️ Berhasil: **{success}**\n"
            f"❌ Gagal: **{failed}**",
        )
    except Exception:
        pass


@Client.on_message(filters.command("broadcast") & filters.private & IsAdmin)
async def broadcast_handler(client: Client, message: Message) -> None:
    """Broadcast a message to all users.

    Usage:
        /broadcast <text>           — send text
        /broadcast (reply to msg)   — forward that message to all users
    """
    parts = message.text.strip().split(maxsplit=1)
    has_text = len(parts) >= 2 and parts[1].strip()
    has_reply = message.reply_to_message is not None

    if not has_text and not has_reply:
        await message.reply(
            "📢 **Cara pakai /broadcast:**\n\n"
            "• `/broadcast <pesan>` — kirim teks ke semua user\n"
            "• Reply ke pesan lalu ketik `/broadcast` — forward pesan itu ke semua user"
        )
        return

    async with get_session() as session:
        user_ids = await get_all_user_ids(session)
    total = len(user_ids)

    await message.reply(
        f"📣 **Broadcast dimulai...**\n"
        f"Akan dikirim ke **{total}** pengguna. Anda akan mendapat notifikasi setelah selesai."
    )

    text_to_send = parts[1].strip() if has_text else None
    source_msg = message.reply_to_message if has_reply and not has_text else None

    asyncio.create_task(
        _do_broadcast(client, source_msg or message, text_to_send)
    )


# ── /help — Command reference ────────────────────────────────

@Client.on_message(filters.command("help") & filters.private)
async def help_handler(client: Client, message: Message) -> None:
    """Show available commands based on user role."""
    async with get_session() as session:
        user = await get_user(session, message.from_user.id)

    # Base commands
    text = (
        "📖 **Available Commands**\n\n"
        "**General:**\n"
        "`/start` — Start the bot / access content via link\n"
        "`/help` — Show this message\n"
    )

    if user and user.has_permission(UserRole.STAFF):
        text += (
            "\n**Staff:**\n"
            "`/stats` — View bot statistics\n"
            "`/add_content` — Upload new content\n"
        )

    if user and user.has_permission(UserRole.ADMIN):
        text += (
            "\n**Admin:**\n"
            "`/health` — Check service health\n"
            "`/queue` — View job queue status\n"
            "`/logs` — Recent audit logs\n"
            "`/setrole <user_id> <ROLE>` — Change user role\n"
            "`/ban <user_id>` — Ban a user\n"
            "`/unban <user_id>` — Unban a user\n"
            "`/add_channel` — Add fsub channel\n"
            "`/remove_channel` — Remove fsub channel\n"
            "`/channels` — List fsub channels\n"
            "`/broadcast <pesan>` — Kirim pesan ke semua user\n"
        )

    await message.reply(text)
