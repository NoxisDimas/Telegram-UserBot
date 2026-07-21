"""
Fsub channel management handlers + callback query for membership re-check.
"""

from __future__ import annotations

import logging

from hydrogram import Client, filters
from hydrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.bot.filters.permissions import IsAdmin
from app.core.database import get_session
from app.models.content import ContentType
from app.services.content_service import get_content, get_content_files, log_access
from app.services.fsub_service import (
    add_fsub_channel,
    check_membership,
    get_fsub_channels,
    invalidate_membership_cache,
    remove_fsub_channel,
)

logger = logging.getLogger(__name__)


# ── /add_channel — Add a channel to fsub list ───────────────

@Client.on_message(filters.command("add_channel") & filters.private & IsAdmin)
async def add_channel_handler(client: Client, message: Message) -> None:
    """Add a channel to the forced subscription list.

    Usage: /add_channel <channel_id or @username>
    """
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(
            "Usage: `/add_channel <channel_id or @username>`\n\n"
            "Example:\n"
            "`/add_channel -1001234567890`\n"
            "`/add_channel @mychannel`"
        )
        return

    channel_ref = parts[1].strip()

    try:
        # Try to get chat info from Telegram
        chat = await client.get_chat(channel_ref)
    except Exception as exc:
        await message.reply(
            f"❌ **Could not find channel:** `{channel_ref}`\n"
            f"Error: {exc}\n\n"
            f"Make sure the bot is a member of the channel."
        )
        return

    # Check if bot is admin in the channel
    try:
        bot_member = await client.get_chat_member(chat.id, "me")
        is_admin = bot_member.status.value in ("administrator", "creator")
    except Exception:
        is_admin = False

    if not is_admin:
        await message.reply(
            f"⚠️ **Bot is not an admin in** `{chat.title}`.\n"
            f"Please make the bot an admin first."
        )
        return

    # Determine if private
    is_private = chat.username is None
    invite_link = None
    if is_private:
        try:
            invite_link = await client.export_chat_invite_link(chat.id)
        except Exception:
            invite_link = chat.invite_link

    async with get_session() as session:
        await add_fsub_channel(
            session=session,
            channel_id=chat.id,
            title=chat.title or str(chat.id),
            username=chat.username,
            invite_link=invite_link,
            is_private=is_private,
            actor_id=message.from_user.id,
        )

    await message.reply(
        f"✅ **Channel added to fsub list!**\n\n"
        f"📢 **{chat.title}**\n"
        f"🆔 `{chat.id}`\n"
        f"🔒 Private: {'Yes' if is_private else 'No'}"
    )


# ── /remove_channel ─────────────────────────────────────────

@Client.on_message(filters.command("remove_channel") & filters.private & IsAdmin)
async def remove_channel_handler(client: Client, message: Message) -> None:
    """Remove a channel from the fsub list. Usage: /remove_channel <channel_id>"""
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.reply("Usage: `/remove_channel <channel_id>`")
        return

    try:
        channel_id = int(parts[1])
    except ValueError:
        await message.reply("❌ Invalid channel ID. Use the numeric ID.")
        return

    async with get_session() as session:
        success = await remove_fsub_channel(
            session, channel_id, actor_id=message.from_user.id
        )

    if success:
        await message.reply(f"✅ Channel `{channel_id}` removed from fsub list.")
    else:
        await message.reply(f"❌ Channel `{channel_id}` not found in fsub list.")


# ── /channels — List fsub channels ──────────────────────────

@Client.on_message(filters.command("channels") & filters.private & IsAdmin)
async def channels_handler(client: Client, message: Message) -> None:
    """List all active forced subscription channels."""
    async with get_session() as session:
        channels = await get_fsub_channels(session)

    if not channels:
        await message.reply("📢 No forced subscription channels configured.")
        return

    lines = ["📢 **Forced Subscription Channels**\n"]
    for ch in channels:
        privacy = "🔒" if ch.is_private else "🌐"
        link = f"@{ch.username}" if ch.username else f"`{ch.channel_id}`"
        lines.append(f"{privacy} **{ch.title}** — {link}")

    await message.reply("\n".join(lines))


# ── Callback: "Coba Lagi" re-check ──────────────────────────

@Client.on_callback_query(filters.regex(r"^check_fsub\|"))
async def check_fsub_callback(client: Client, callback_query: CallbackQuery) -> None:
    """Re-check membership when user clicks 'Coba Lagi'.

    callback_data format: check_fsub|<content_id>
    content_id is a plain UUID string (no signing, no expiry).
    """
    user_id = callback_query.from_user.id
    data = callback_query.data or ""

    # Extract content_id directly — no signature verification needed
    _, content_id = data.split("|", 1)

    # Invalidate cache to force a fresh check
    await invalidate_membership_cache(user_id)

    # Re-check membership
    async with get_session() as session:
        channels = await get_fsub_channels(session)

    async def check_fn(uid: int, cid: int) -> bool:
        try:
            member = await client.get_chat_member(cid, uid)
            return member.status.value in ("member", "administrator", "creator")
        except Exception:
            return False

    all_joined, missing = await check_membership(user_id, channels, check_fn)

    if not all_joined:
        missing_names = ", ".join(ch.title for ch in missing)
        await callback_query.answer(
            f"❌ Belum join: {missing_names}", show_alert=True,
        )
        return

    # Membership confirmed — send the content
    await callback_query.answer("✅ Verified! Sending content...")

    async with get_session() as session:
        content = await get_content(session, content_id)
        if content is None:
            await callback_query.message.reply("❌ Content not found.")
            return

        files = await get_content_files(session, content_id)
        if not files:
            await callback_query.message.reply("❌ No files found.")
            return

        # Send content
        try:
            for idx, f in enumerate(files):
                caption = content.caption if idx == 0 else None
                type_map = {
                    ContentType.PHOTO: client.send_photo,
                    ContentType.VIDEO: client.send_video,
                    ContentType.DOCUMENT: client.send_document,
                    ContentType.AUDIO: client.send_audio,
                    ContentType.ANIMATION: client.send_animation,
                }
                method = type_map.get(f.file_type, client.send_document)
                await method(user_id, f.telegram_file_id, caption=caption)

            await log_access(session, user_id, content_id, success=True)
        except Exception as exc:
            logger.error("Failed to send content after fsub check: %s", exc)
            await callback_query.message.reply("❌ Failed to send content.")
            await log_access(
                session, user_id, content_id,
                success=False, failure_reason=f"send_error: {exc}",
            )

    # Remove the join prompt message
    try:
        await callback_query.message.delete()
    except Exception:
        pass
