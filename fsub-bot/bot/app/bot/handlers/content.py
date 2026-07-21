"""
Content management handler — /add_content with conversation-style FSM.

After saving content, auto-posts a catalogue entry to DB_CHANNEL
with a random cover image + deep link.
"""

from __future__ import annotations

import logging
import os
import random
import re
from pathlib import Path
from typing import Dict

from hydrogram import Client, filters, enums
from hydrogram.types import Message
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.filters.permissions import IsStaff
from app.core.config import get_settings
from app.core.database import get_session
from app.core.security import build_deep_link, encode_content_id
from app.models.content import ContentType
from app.services.content_service import create_content

logger = logging.getLogger(__name__)

# ── Assets path ──────────────────────────────────────────────
COVERS_DIR = Path(__file__).resolve().parents[3] / "assets" / "covers"

# ── Simple in-memory state tracking for conversation flow ────
# Key: user_id, Value: FSM state dict
_user_states: Dict[int, dict] = {}


async def _update_catalogue_msg_id(content_id: uuid.UUID, msg_id: int) -> None:
    """Helper to update catalogue_msg_id."""
    from app.models.content import Content
    
    async with get_session() as session:
        content = await session.get(Content, content_id)
        if content:
            content.catalogue_msg_id = msg_id
            await session.commit()

def _get_random_cover() -> str | None:
    """Pick a random cover image from assets/covers/."""
    if not COVERS_DIR.exists():
        return None
    images = [
        f for f in COVERS_DIR.iterdir()
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
    ]
    if not images:
        return None
    return str(random.choice(images))


@Client.on_message(filters.command("add_content") & filters.private & IsStaff)
async def add_content_start(client: Client, message: Message) -> None:
    """Start the content upload flow."""
    user_id = message.from_user.id

    _user_states[user_id] = {
        "step": "waiting_media",
        "files": [],
        "caption": None,
        "content_type": None,
    }

    await message.reply(
        "📤 **Add Content**\n\n"
        "Send me the media file (photo, video, document, audio, or animation).\n"
        "You can send multiple files for an album.\n\n"
        "When done, send /done to save.\n"
        "Send /cancel to abort."
    )


@Client.on_message(filters.command("done") & filters.private)
async def add_content_done(client: Client, message: Message) -> None:
    """Finish the content upload flow and save to database."""
    user_id = message.from_user.id
    state = _user_states.get(user_id)

    if state is None or state.get("step") != "waiting_media":
        return

    files = state["files"]
    if not files:
        await message.reply("❌ No files uploaded. Send media first or /cancel.")
        return

    # Ask for caption
    _user_states[user_id]["step"] = "waiting_caption"
    await message.reply(
        "📝 Send a **caption** for this content, or send /skip to skip."
    )


@Client.on_message(filters.command("skip") & filters.private)
async def skip_caption(client: Client, message: Message) -> None:
    """Skip caption and save content immediately."""
    user_id = message.from_user.id
    state = _user_states.get(user_id)

    if state is None or state.get("step") != "waiting_caption":
        return

    await _save_content(client, message, caption=None)


@Client.on_message(filters.command("cancel") & filters.private)
async def cancel_content(client: Client, message: Message) -> None:
    """Cancel the content upload flow."""
    user_id = message.from_user.id
    if user_id in _user_states:
        del _user_states[user_id]
        await message.reply("❌ Content upload cancelled.")


@Client.on_message(
    filters.private
    & (filters.photo | filters.video | filters.document | filters.audio | filters.animation)
)
async def receive_media(client: Client, message: Message) -> None:
    """Receive a media file during the upload flow."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    state = _user_states.get(user_id)

    if state is None or state.get("step") != "waiting_media":
        return

    # Determine file type and extract file_id
    file_info = _extract_file_info(message)
    if file_info is None:
        await message.reply("❌ Unsupported media type.")
        return

    state["files"].append(file_info)

    # Set content type from first file
    if state["content_type"] is None:
        state["content_type"] = file_info["file_type"]

    count = len(state["files"])
    await message.reply(
        f"✅ File #{count} received (`{file_info['file_type']}`).\n"
        f"Send more files or /done to save."
    )


@Client.on_message(
    filters.text & ~filters.command(["done", "skip", "cancel"]) & filters.private
)
async def receive_text_in_flow(client: Client, message: Message) -> None:
    """Receive text (caption or telegram link) during the upload flow."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    state = _user_states.get(user_id)

    if state is None:
        return

    step = state.get("step")
    text = message.text.strip()

    if step == "waiting_caption":
        await _save_content(client, message, caption=text)
        return
        
    if step == "waiting_media":
        # Check if text is a Telegram link
        match_public = re.match(r"https?://t\.me/([^/]+)/(\d+)", text)
        match_private = re.match(r"https?://t\.me/c/(\d+)/(\d+)", text)
        
        chat_id = None
        message_id = None
        
        if match_private:
            chat_id = int(f"-100{match_private.group(1)}")
            message_id = int(match_private.group(2))
        elif match_public:
            username = match_public.group(1)
            if username != "c":
                chat_id = username
                message_id = int(match_public.group(2))
                
        if chat_id and message_id:
            try:
                msg = await client.get_messages(chat_id, message_ids=message_id)
                if not msg or getattr(msg, "empty", False):
                    await message.reply("❌ Pesan tidak ditemukan atau bot tidak memiliki akses ke channel/grup tersebut.")
                    return
                    
                file_info = _extract_file_info(msg)
                if not file_info:
                    await message.reply("❌ Pesan pada link tersebut tidak berisi media yang didukung.")
                    return
                    
                state["files"].append(file_info)
                if state["content_type"] is None:
                    state["content_type"] = file_info["file_type"]

                count = len(state["files"])
                await message.reply(
                    f"✅ File #{count} berhasil diambil dari link (`{file_info['file_type']}`).\n"
                    f"Kirim media/link lagi atau /done untuk menyimpan."
                )
            except Exception as e:
                logger.error("Error fetching message from link: %s", e)
                await message.reply(f"❌ Gagal mengambil pesan dari link: {e}")
        else:
            await message.reply("❌ Link tidak valid. Harap kirimkan file media atau link pesan Telegram yang valid.")


# ── Helpers ──────────────────────────────────────────────────

def _extract_file_info(message: Message) -> dict | None:
    """Extract file_id, file_unique_id, and type from a media message."""
    if message.photo:
        photo = message.photo
        return {
            "file_id": photo.file_id,
            "file_unique_id": photo.file_unique_id,
            "file_type": ContentType.PHOTO.value,
        }
    elif message.video:
        return {
            "file_id": message.video.file_id,
            "file_unique_id": message.video.file_unique_id,
            "file_type": ContentType.VIDEO.value,
        }
    elif message.document:
        return {
            "file_id": message.document.file_id,
            "file_unique_id": message.document.file_unique_id,
            "file_type": ContentType.DOCUMENT.value,
        }
    elif message.audio:
        return {
            "file_id": message.audio.file_id,
            "file_unique_id": message.audio.file_unique_id,
            "file_type": ContentType.AUDIO.value,
        }
    elif message.animation:
        return {
            "file_id": message.animation.file_id,
            "file_unique_id": message.animation.file_unique_id,
            "file_type": ContentType.ANIMATION.value,
        }
    return None


async def _post_to_db_channel(
    client: Client,
    content_id: uuid.UUID,
    caption: str | None,
) -> None:
    """Post a catalogue entry to DB_CHANNEL with cover image + deep link, and save message ID."""
    settings = get_settings()
    deep_link = build_deep_link(str(content_id), settings.BOT_USERNAME)
    capt = caption or "Bikin Tegang 3 Hari Inimah"

    # Build caption text
    caption_parts = [
        "",
        f"🎬 <a href='{deep_link}'><b><i>{capt}</i></b></a>",
        "",
        f"{'━'*len(capt)}",
        "",
        "<blockquote><b>ORDER VIP 🔜 @VIPMEDIA_2BOT ❞</b></blockquote>"
    ]

    post_caption = "\n".join(caption_parts)


    # Try to send with a random cover image
    cover_path = _get_random_cover()
    if cover_path:
        try:
            msg = await client.send_photo(
                chat_id=settings.DB_CHANNEL_ID,
                photo=cover_path,
                caption=post_caption,
                parse_mode=enums.ParseMode.HTML,
            )
            logger.info(
                "Posted content %s to DB_CHANNEL %d with cover (msg_id: %s)",
                content_id, settings.DB_CHANNEL_ID, msg.id,
            )
            await _update_catalogue_msg_id(content_id, msg.id)
            return
        except Exception as exc:
            logger.warning("Failed to send cover photo, falling back to text: %s", exc)

    # Fallback: send text-only post
    try:
        msg = await client.send_message(
            chat_id=settings.DB_CHANNEL_ID,
            text=post_caption,
            parse_mode=enums.ParseMode.HTML,
        )
        logger.info(
            "Posted content %s to DB_CHANNEL %d (text only) (msg_id: %s)",
            content_id, settings.DB_CHANNEL_ID, msg.id,
        )
        await _update_catalogue_msg_id(content_id, msg.id)
    except Exception as exc:
        logger.error("Failed to post to DB_CHANNEL: %s", exc)


async def _save_content(
    client: Client,
    message: Message,
    caption: str | None,
) -> None:
    """Save collected files to the database, post to channel, and return deep link."""
    user_id = message.from_user.id
    state = _user_states.get(user_id)

    if state is None:
        return

    files = state["files"]
    content_type = ContentType(state["content_type"])

    try:
        async with get_session() as session:
            content = await create_content(
                session=session,
                uploader_id=user_id,
                content_type=content_type,
                files=files,
                caption=caption,
            )

        settings = get_settings()
        deep_link = build_deep_link(str(content.content_id), settings.BOT_USERNAME)

        # ── Auto-post to DB_CHANNEL ──────────────────────────
        await _post_to_db_channel(client, str(content.content_id), caption)

        await message.reply(
            f"✅ **Content saved!**\n\n"
            f"📎 **ID:** `{content.content_id}`\n"
            f"📁 **Files:** {len(files)}\n"
            f"🏷️ **Type:** {content_type.value}\n"
            f"📝 **Caption:** {caption or '(none)'}\n\n"
            f"🔗 **Deep Link:**\n`{deep_link}`\n\n"
            f"📢 Content has been posted to the channel!"
        )

        logger.info(
            "Content %s created by user %d with %d files",
            content.content_id, user_id, len(files),
        )

    except Exception as exc:
        logger.error("Failed to save content: %s", exc)
        await message.reply(f"❌ **Failed to save content:** {exc}")

    finally:
        # Clean up state
        if user_id in _user_states:
            del _user_states[user_id]
