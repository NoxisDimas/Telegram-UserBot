"""
Content service — CRUD for content records, deep link generation, access logging.

Pure business logic — no Hydrogram imports.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import build_deep_link, encode_content_id
from app.models.content import Content, ContentFile, ContentType
from app.models.logs import AccessLog, AuditLog

logger = logging.getLogger(__name__)


async def create_content(
    session: AsyncSession,
    uploader_id: int,
    content_type: ContentType,
    files: list[dict[str, str]],
    caption: Optional[str] = None,
) -> Content:
    """Create a new content record with associated files.

    Args:
        session:      Database session.
        uploader_id:  Telegram user ID of the uploader.
        content_type: Media type of the content.
        files:        List of dicts, each containing:
                      ``{"file_id": str, "file_unique_id": str, "file_type": str}``.
        caption:      Optional caption text.

    Returns:
        The created ``Content`` object.
    """
    content = Content(
        content_id=uuid.uuid4(),
        caption=caption,
        content_type=content_type,
        uploader_id=uploader_id,
    )
    session.add(content)

    for idx, f in enumerate(files):
        file_type = ContentType(f.get("file_type", content_type.value))
        content_file = ContentFile(
            content_id=content.content_id,
            telegram_file_id=f["file_id"],
            file_unique_id=f["file_unique_id"],
            file_type=file_type,
            order=idx,
        )
        session.add(content_file)

    # Audit log
    audit = AuditLog(
        actor_id=uploader_id,
        action="ADD_CONTENT",
        target=str(content.content_id),
        payload={
            "type": content_type.value,
            "file_count": len(files),
        },
    )
    session.add(audit)

    await session.flush()  # ensure content_id is available
    logger.info(
        "Content created: id=%s type=%s files=%d by user=%d",
        content.content_id, content_type.value, len(files), uploader_id,
    )
    return content


async def get_content(
    session: AsyncSession,
    content_id: str | uuid.UUID,
) -> Content | None:
    """Fetch a content record with its files."""
    if isinstance(content_id, str):
        try:
            content_id = uuid.UUID(content_id)
        except ValueError:
            return None

    result = await session.execute(
        select(Content).where(Content.content_id == content_id)
    )
    return result.scalar_one_or_none()


async def get_content_files(
    session: AsyncSession,
    content_id: str | uuid.UUID,
) -> list[ContentFile]:
    """Fetch all files for a content record, ordered."""
    if isinstance(content_id, str):
        content_id = uuid.UUID(content_id)

    result = await session.execute(
        select(ContentFile)
        .where(ContentFile.content_id == content_id)
        .order_by(ContentFile.order)
    )
    return list(result.scalars().all())


async def generate_content_deep_link(content_id: str | uuid.UUID) -> str:
    """Generate a full deep-link URL for a content record."""
    settings = get_settings()
    return build_deep_link(str(content_id), settings.BOT_USERNAME)


async def generate_content_payload(content_id: str | uuid.UUID) -> str:
    """Generate just the encoded payload (for inline use)."""
    return encode_content_id(str(content_id))


async def log_access(
    session: AsyncSession,
    user_id: int,
    content_id: str | uuid.UUID,
    success: bool = True,
    failure_reason: Optional[str] = None,
) -> AccessLog:
    """Record a content access attempt."""
    if isinstance(content_id, str):
        content_id = uuid.UUID(content_id)

    log = AccessLog(
        user_id=user_id,
        content_id=content_id,
        success=success,
        failure_reason=failure_reason,
    )
    session.add(log)
    return log


async def get_content_stats(
    session: AsyncSession,
) -> dict[str, int]:
    """Return aggregate content statistics."""
    total_content = await session.scalar(
        select(func.count()).select_from(Content)
    )
    total_files = await session.scalar(
        select(func.count()).select_from(ContentFile)
    )
    total_accesses = await session.scalar(
        select(func.count()).select_from(AccessLog)
    )
    successful = await session.scalar(
        select(func.count())
        .select_from(AccessLog)
        .where(AccessLog.success.is_(True))
    )

    return {
        "total_content": total_content or 0,
        "total_files": total_files or 0,
        "total_accesses": total_accesses or 0,
        "successful_accesses": successful or 0,
    }


async def list_recent_content(
    session: AsyncSession,
    limit: int = 10,
) -> Sequence[Content]:
    """Fetch the most recently added content records."""
    result = await session.execute(
        select(Content)
        .order_by(Content.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def delete_content(
    session: AsyncSession,
    content_id: str | uuid.UUID,
    actor_id: int,
) -> bool:
    """Delete a content record and its files (cascade)."""
    content = await get_content(session, content_id)
    if content is None:
        return False

    audit = AuditLog(
        actor_id=actor_id,
        action="DELETE_CONTENT",
        target=str(content_id),
        payload={"type": content.content_type.value},
    )
    session.add(audit)

    await session.delete(content)
    return True
