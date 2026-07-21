"""
Fsub service — forced subscription membership verification.

Uses Redis cache with Telegram API fallback. Accepts a callable for the
actual get_chat_member check so this module stays free of Hydrogram imports.

Cache key format:  ``fsub:status:{user_id}``
Cache value:       JSON ``{"joined": [channel_ids], "missing": [channel_ids]}``
Cache TTL:         60 seconds (configurable)
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import redis as redis_client
from app.models.channel import Channel
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

# Type alias for the Telegram membership check function.
# Signature: check_fn(user_id, channel_id) -> bool
MembershipCheckFn = Callable[[int, int], Awaitable[bool]]

FSUB_CACHE_PREFIX = "fsub:status:"
FSUB_CACHE_TTL = 60  # seconds


async def get_fsub_channels(session: AsyncSession) -> list[Channel]:
    """Fetch all active forced-subscription channels from the database."""
    result = await session.execute(
        select(Channel).where(Channel.is_active.is_(True))
    )
    return list(result.scalars().all())


async def check_membership(
    user_id: int,
    channels: Sequence[Channel],
    check_fn: MembershipCheckFn,
    *,
    bypass_roles: tuple[UserRole, ...] = (UserRole.OWNER),
    user: User | None = None,
) -> tuple[bool, list[Channel]]:
    """Check if a user is a member of all required fsub channels.

    Args:
        user_id:       Telegram user ID.
        channels:      List of channels to check.
        check_fn:      Async callable that performs the actual Telegram API
                       ``get_chat_member`` call. Signature:
                       ``(user_id, channel_id) -> bool``.
        bypass_roles:  Roles that skip the check entirely.
        user:          Optional pre-fetched User object to check role.

    Returns:
        ``(all_joined, missing_channels)`` — ``all_joined`` is True if
        the user is a member of every channel; ``missing_channels``
        contains the channels the user has not yet joined.
    """
    # ── Role bypass ──────────────────────────────────────────
    if user is not None:
        if user.role in bypass_roles:
            logger.warning("DEBUG: User %d is %s -> BYPASS", user_id, user.role.value)
            return True, []
        else:
            logger.warning("DEBUG: User %d is %s -> CHECKING", user_id, user.role.value)
    else:
        logger.warning("DEBUG: User %d role unknown -> CHECKING", user_id)

    if not channels:
        logger.warning("DEBUG: No active fsub channels found in DB -> PASS")
        return True, []

    # ── Check Redis cache ────────────────────────────────────
    cache_key = f"{FSUB_CACHE_PREFIX}{user_id}"
    cached: dict[str, Any] | None = await redis_client.get_json(cache_key)

    if cached is not None:
        joined_ids_set = set(cached.get("joined", []))
        required_ids_set = {ch.channel_id for ch in channels}
        
        logger.warning(
            "DEBUG: Cache hit for %d. Cached joined: %s, Required: %s",
            user_id, joined_ids_set, required_ids_set
        )

        if required_ids_set.issubset(joined_ids_set):
            logger.warning("DEBUG: All required channels present in cache -> PASS")
            return True, []
        
        logger.warning("DEBUG: Cache insufficient (new channels?) -> RE-CHECKING")

    # ── Cache miss → call Telegram API ───────────────────────
    joined_ids: list[int] = []
    missing_channels: list[Channel] = []

    for channel in channels:
        try:
            is_member = await check_fn(user_id, channel.channel_id)
            logger.warning(
                "DEBUG: Telegram API check %d -> channel %d (%s) = %s",
                user_id, channel.channel_id, channel.title, is_member
            )
            if is_member:
                joined_ids.append(channel.channel_id)
            else:
                missing_channels.append(channel)
        except Exception as exc:
            logger.warning(
                "Membership check failed for user=%d channel=%d: %s",
                user_id, channel.channel_id, exc,
            )
            missing_channels.append(channel)

    # ── Write to cache ───────────────────────────────────────
    cache_value = {
        "joined": joined_ids,
        "missing": [ch.channel_id for ch in missing_channels],
    }
    await redis_client.set_json(cache_key, cache_value, ttl=FSUB_CACHE_TTL)

    all_joined = len(missing_channels) == 0
    if not all_joined:
        logger.info("DEBUG: Missing channels: %s", [ch.channel_id for ch in missing_channels])
    
    return all_joined, missing_channels


async def invalidate_membership_cache(user_id: int) -> None:
    """Clear the cached membership status for a user.

    Call this when a user clicks "I've joined" to force a fresh check.
    """
    cache_key = f"{FSUB_CACHE_PREFIX}{user_id}"
    await redis_client.delete_key(cache_key)


async def add_fsub_channel(
    session: AsyncSession,
    channel_id: int,
    title: str,
    username: str | None = None,
    invite_link: str | None = None,
    is_private: bool = False,
    actor_id: int | None = None,
) -> Channel:
    """Add a channel to the forced subscription list."""
    from app.models.logs import AuditLog

    channel = Channel(
        channel_id=channel_id,
        title=title,
        username=username,
        invite_link=invite_link,
        is_private=is_private,
        is_active=True,
    )
    session.add(channel)

    if actor_id is not None:
        audit = AuditLog(
            actor_id=actor_id,
            action="ADD_FSUB_CHANNEL",
            target=str(channel_id),
            payload={"title": title, "username": username},
        )
        session.add(audit)

    return channel


async def remove_fsub_channel(
    session: AsyncSession,
    channel_id: int,
    actor_id: int | None = None,
) -> bool:
    """Deactivate a channel from the fsub list (soft delete)."""
    from app.models.logs import AuditLog

    result = await session.execute(
        select(Channel).where(Channel.channel_id == channel_id)
    )
    channel = result.scalar_one_or_none()
    if channel is None:
        return False

    channel.is_active = False
    session.add(channel)

    if actor_id is not None:
        audit = AuditLog(
            actor_id=actor_id,
            action="REMOVE_FSUB_CHANNEL",
            target=str(channel_id),
        )
        session.add(audit)

    return True
