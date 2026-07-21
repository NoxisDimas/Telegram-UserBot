"""
Dashboard statistics endpoint.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin, get_db
from app.models.channel import Channel
from app.models.content import Content
from app.models.job import Job, JobStatus
from app.models.user import User

router = APIRouter(prefix="/stats", tags=["Stats"])


@router.get("/")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Return dashboard overview statistics."""
    # Total users
    total_users = (await db.execute(select(func.count(User.user_id)))).scalar() or 0

    # Total content
    total_content = (await db.execute(select(func.count(Content.content_id)))).scalar() or 0

    # Active channels
    active_channels = (
        await db.execute(
            select(func.count(Channel.channel_id)).where(Channel.is_active == True)
        )
    ).scalar() or 0

    # Pending jobs
    pending_jobs = (
        await db.execute(
            select(func.count(Job.job_id)).where(Job.status == JobStatus.PENDING)
        )
    ).scalar() or 0

    # Recent contents (last 5)
    recent_stmt = (
        select(Content)
        .options(selectinload(Content.files))
        .order_by(Content.created_at.desc())
        .limit(5)
    )
    recent_result = await db.execute(recent_stmt)
    recent_contents = recent_result.scalars().all()

    return {
        "total_users": total_users,
        "total_content": total_content,
        "active_channels": active_channels,
        "pending_jobs": pending_jobs,
        "recent_contents": [
            {
                "content_id": str(c.content_id),
                "content_type": c.content_type.value,
                "caption": c.caption,
                "files_count": len(c.files) if c.files else 0,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in recent_contents
        ],
    }
