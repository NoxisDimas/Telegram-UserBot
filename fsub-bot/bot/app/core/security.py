"""
Security module — simple base64url deep links (no expiry, permanent access).

Link format:
    base64url(content_id)

Deep links are permanent — no HMAC, no expiry, no anti-replay.
"""

from __future__ import annotations

import base64
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def encode_content_id(content_id: str | int) -> str:
    """Base64url-encode a content_id for use as a deep link payload.

    Returns:
        The payload string to append to ``https://t.me/Bot?start=<payload>``.
    """
    raw = str(content_id).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_content_id(payload: str) -> str | None:
    """Decode a base64url payload back into a content_id string.

    Returns:
        The content_id string, or None if decoding fails.
    """
    try:
        # Add back padding
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding
        decoded = base64.urlsafe_b64decode(payload.encode()).decode()
        return decoded if decoded else None
    except Exception:
        return None


def build_deep_link(content_id: str | int, bot_username: str) -> str:
    """Build a full deep-link URL for the given content.

    Returns:
        ``https://t.me/<bot_username>?start=<encoded_content_id>``
    """
    payload = encode_content_id(content_id)
    return f"https://t.me/{bot_username}?start={payload}"
