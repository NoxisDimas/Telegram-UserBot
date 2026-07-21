"""
Auth service — role checks, permissions, user lifecycle.

Pure business logic — no Hydrogram imports.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.logs import AuditLog
from app.models.user import ROLE_HIERARCHY, User, UserRole

logger = logging.getLogger(__name__)


async def get_or_create_user(
    session: AsyncSession,
    user_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
) -> User:
    """Upsert a user — create if new, update profile fields if existing.

    Returns the User object (always attached to the session).
    """
    stmt = (
        pg_insert(User)
        .values(
            user_id=user_id,
            username=username,
            first_name=first_name,
            role=UserRole.USER,
        )
        .on_conflict_do_update(
            index_elements=[User.user_id],
            set_={
                "username": username,
                "first_name": first_name,
            },
        )
        .returning(User)
    )
    result = await session.execute(stmt)
    user = result.scalar_one()
    return user


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    """Fetch a user by Telegram user ID."""
    result = await session.execute(
        select(User).where(User.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_all_user_ids(session: AsyncSession) -> list[int]:
    """Fetch all Telegram user IDs."""
    result = await session.execute(select(User.user_id))
    return list(result.scalars().all())


async def check_permission(
    session: AsyncSession,
    user_id: int,
    required_role: UserRole,
) -> bool:
    """Check if a user has at least the required role level.

    Returns False if user does not exist or is banned.
    """
    user = await get_user(session, user_id)
    if user is None:
        return False
    if user.is_banned:
        return False
    return user.has_permission(required_role)


async def set_user_role(
    session: AsyncSession,
    actor_id: int,
    target_id: int,
    new_role: UserRole,
) -> bool:
    """Set a user's role with audit logging.

    Rules:
        - Only users with higher privilege can change roles.
        - Cannot promote to OWNER (there's only one).
        - Cannot change your own role.

    Returns True on success, False on denial.
    """
    actor = await get_user(session, actor_id)
    target = await get_user(session, target_id)

    if actor is None or target is None:
        return False
    if actor_id == target_id:
        return False
    if new_role == UserRole.OWNER:
        return False

    # Actor must outrank both the target's current role and the new role
    actor_level = ROLE_HIERARCHY.get(actor.role, 0)
    target_level = ROLE_HIERARCHY.get(target.role, 0)
    new_level = ROLE_HIERARCHY.get(new_role, 0)

    if actor_level <= target_level or actor_level <= new_level:
        return False

    old_role = target.role
    target.role = new_role
    session.add(target)

    # Audit log
    audit = AuditLog(
        actor_id=actor_id,
        action="SET_ROLE",
        target=str(target_id),
        payload={
            "old_role": old_role.value,
            "new_role": new_role.value,
        },
    )
    session.add(audit)

    logger.info(
        "Role changed: actor=%d target=%d %s→%s",
        actor_id, target_id, old_role.value, new_role.value,
    )
    return True


async def ban_user(
    session: AsyncSession,
    actor_id: int,
    target_id: int,
) -> bool:
    """Ban a user (prevents content access). Requires higher privilege."""
    actor = await get_user(session, actor_id)
    target = await get_user(session, target_id)

    if actor is None or target is None:
        return False
    if not actor.has_permission(UserRole.ADMIN):
        return False
    if ROLE_HIERARCHY.get(actor.role, 0) <= ROLE_HIERARCHY.get(target.role, 0):
        return False

    target.is_banned = True
    session.add(target)

    audit = AuditLog(
        actor_id=actor_id,
        action="BAN_USER",
        target=str(target_id),
    )
    session.add(audit)
    return True


async def unban_user(
    session: AsyncSession,
    actor_id: int,
    target_id: int,
) -> bool:
    """Unban a user. Requires ADMIN+ privilege."""
    actor = await get_user(session, actor_id)
    target = await get_user(session, target_id)

    if actor is None or target is None:
        return False
    if not actor.has_permission(UserRole.ADMIN):
        return False

    target.is_banned = False
    session.add(target)

    audit = AuditLog(
        actor_id=actor_id,
        action="UNBAN_USER",
        target=str(target_id),
    )
    session.add(audit)
    return True
