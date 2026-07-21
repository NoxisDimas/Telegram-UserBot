"""
/start handler — entry point for deep links and welcome messages.

Flow:
    /start (no payload)  → welcome message
    /start <payload>     → decode content_id → check fsub → deliver content
"""

from __future__ import annotations

import logging

from hydrogram import Client, filters
from hydrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.core.database import get_session
from app.core.security import decode_content_id
from app.models.content import ContentType
from app.services.auth_service import get_or_create_user
from app.services.content_service import get_content, get_content_files, log_access
from app.services.fsub_service import (
    check_membership,
    get_fsub_channels,
)

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────

async def _check_telegram_membership(
    client: Client,
    user_id: int,
    channel_id: int,
) -> bool:
    """Check if a user is a member of a channel via Telegram API."""
    try:
        member = await client.get_chat_member(channel_id, user_id)
        return member.status.value in (
            "member", "administrator", "creator",
        )
    except Exception:
        return False


async def _send_join_prompt(
    client: Client,
    message: Message,
    missing_channels: list,
    content_id: str,
) -> None:
    """Send a message asking the user to join the required channels.

    Style matching the reference screenshot:
    - Greeting with user's name
    - Join buttons for each channel (URL buttons with ↗ arrow)
    - "Coba Lagi" (try again) callback button
    - "Tutup" (close) button
    """
    user_name = message.from_user.first_name or "User"

    buttons: list[list[InlineKeyboardButton]] = []

    # Channel/group join buttons — 2 per row when possible
    row: list[InlineKeyboardButton] = []
    for ch in missing_channels:
        row.append(
            InlineKeyboardButton(
                text=f"📢 {ch.title}",
                url=ch.link,
            )
        )
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # "Coba Lagi" (try again) button — re-check membership
    buttons.append([
        InlineKeyboardButton(
            text="🔄 Coba Lagi",
            callback_data=f"check_fsub|{content_id}",
        )
    ])

    # "Tutup" (close) button
    buttons.append([
        InlineKeyboardButton(
            text="❌ Tutup",
            callback_data="close_msg",
        )
    ])

    await message.reply(
        f"🖐 Hallo **{user_name}** !\n\n"
        f"Anda terlebih dahulu harus bergabung ke Channel / Grup untuk "
        f"melihat file yang saya bagikan.\n\n"
        f"Jika sudah bergabung silakan tekan tombol **Coba Lagi**.",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def _send_content_to_user(
    client: Client,
    message_or_chat_id: Message | int,
    content,  # type: ignore[no-untyped-def]
    files: list,
) -> None:
    """Send content files to the user."""
    chat_id = (
        message_or_chat_id.chat.id
        if isinstance(message_or_chat_id, Message)
        else message_or_chat_id
    )

    if len(files) == 1:
        f = files[0]
        send_method = _get_send_method(client, chat_id, f)
        await send_method(f.telegram_file_id, caption=content.caption)
    else:
        # Media group / album — send each file individually with order
        for idx, f in enumerate(files):
            caption = content.caption if idx == 0 else None
            send_method = _get_send_method(client, chat_id, f)
            await send_method(f.telegram_file_id, caption=caption)


def _get_send_method(client: Client, chat_id: int, content_file):  # type: ignore[no-untyped-def]
    """Return the appropriate Hydrogram send method for the file type."""
    type_map = {
        ContentType.PHOTO: client.send_photo,
        ContentType.VIDEO: client.send_video,
        ContentType.DOCUMENT: client.send_document,
        ContentType.AUDIO: client.send_audio,
        ContentType.ANIMATION: client.send_animation,
    }

    async def sender(file_id: str, caption: str | None = None) -> None:
        method = type_map.get(content_file.file_type, client.send_document)
        await method(chat_id, file_id, caption=caption)

    return sender


# ── /start with or without payload ───────────────────────────

@Client.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message) -> None:
    """Handle /start command — with or without deep link payload."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    parts = message.text.strip().split(maxsplit=1)

    # Register / update user
    async with get_session() as session:
        user = await get_or_create_user(
            session,
            user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )

    # No payload → welcome message
    if len(parts) < 2 or not parts[1].strip():
        await message.reply(
            "👋 **Welcome!**\n\n"
            "I'm a Forced Subscription bot. "
            "Use a content link to access protected media.\n\n"
            "If you're an admin, use /help to see available commands.",
        )
        return

    payload = parts[1].strip()

    # ── 1. Decode content_id from payload ────────────────────
    content_id = decode_content_id(payload)

    if content_id is None:
        await message.reply(
            "⚠️ **Invalid link.**\n"
            "The link you used is not valid. Please check and try again.",
        )
        return

    # ── 2. Check fsub membership ─────────────────────────────
    async with get_session() as session:
        channels = await get_fsub_channels(session)
        logger.warning("DEBUG: Found %d active fsub channels", len(channels))

    if channels:
        async def check_fn(uid: int, cid: int) -> bool:
            return await _check_telegram_membership(client, uid, cid)

        all_joined, missing = await check_membership(
            user_id, channels, check_fn, user=user,
        )

        if not all_joined:
            await _send_join_prompt(client, message, missing, content_id)
            async with get_session() as session:
                await log_access(
                    session, user_id, content_id,
                    success=False, failure_reason="fsub_not_joined",
                )
            return

    # ── 3. Fetch and send content ────────────────────────────
    async with get_session() as session:
        content = await get_content(session, content_id)
        if content is None:
            await message.reply("❌ **Content not found.** It may have been removed.")
            await log_access(
                session, user_id, content_id,
                success=False, failure_reason="content_not_found",
            )
            return

        files = await get_content_files(session, content_id)
        if not files:
            await message.reply("❌ **No files found for this content.**")
            await log_access(
                session, user_id, content_id,
                success=False, failure_reason="no_files",
            )
            return

        # Send the content
        try:
            await _send_content_to_user(client, message, content, files)
            await log_access(session, user_id, content_id, success=True)
            logger.info("Content %s delivered to user %d", content_id, user_id)
        except Exception as exc:
            logger.error(
                "Failed to send content %s to user %d: %s",
                content_id, user_id, exc,
            )
            await message.reply("❌ **Failed to send content.** Please try again.")
            await log_access(
                session, user_id, content_id,
                success=False, failure_reason=f"send_error: {exc}",
            )


# ── Callback: close message ─────────────────────────────────

@Client.on_callback_query(filters.regex(r"^close_msg$"))
async def close_msg_callback(client: Client, callback_query) -> None:
    """Delete the message when user clicks 'Tutup'."""
    try:
        await callback_query.message.delete()
    except Exception:
        await callback_query.answer("Could not delete message.", show_alert=False)
