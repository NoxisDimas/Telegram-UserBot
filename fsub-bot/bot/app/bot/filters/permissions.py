"""
Custom Hydrogram filters — role-based permission checks.
"""

from __future__ import annotations

from hydrogram import Client, filters
from hydrogram.types import Message

from app.core.database import get_session
from app.models.user import UserRole
from app.services.auth_service import check_permission, get_or_create_user


async def is_admin(flt: filters.Filter, client: Client, message: Message) -> bool:
    """Filter that passes only for ADMIN+ role users."""
    if not message.from_user:
        return False
    async with get_session() as session:
        return await check_permission(session, message.from_user.id, UserRole.ADMIN)


async def is_staff(flt: filters.Filter, client: Client, message: Message) -> bool:
    """Filter that passes only for STAFF+ role users."""
    if not message.from_user:
        return False
    async with get_session() as session:
        return await check_permission(session, message.from_user.id, UserRole.STAFF)


async def is_owner(flt: filters.Filter, client: Client, message: Message) -> bool:
    """Filter that passes only for the bot OWNER."""
    if not message.from_user:
        return False
    async with get_session() as session:
        return await check_permission(session, message.from_user.id, UserRole.OWNER)


# ── Instantiate as reusable filter objects ───────────────────
IsAdmin = filters.create(is_admin, "IsAdmin")
IsStaff = filters.create(is_staff, "IsStaff")
IsOwner = filters.create(is_owner, "IsOwner")
