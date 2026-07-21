"""
Broadcast endpoints.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.models.job import Job

router = APIRouter(prefix="/broadcast", tags=["Broadcast"])


class BroadcastRequest(BaseModel):
    message_type: str  # "text", "photo", "video"
    text: str | None = None
    media_url: str | None = None  # Or telegram file_id


@router.post("/")
async def trigger_broadcast(
    req: BroadcastRequest,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Trigger a broadcast job to all users."""
    
    # Store the broadcast request as a job for the worker to process
    payload = req.model_dump(exclude_unset=True)
    
    new_job = Job(
        job_type="broadcast_message",
        payload=payload,
    )
    
    db.add(new_job)
    await db.commit()
    
    return {"message": "Broadcast job queued successfully", "job_id": new_job.job_id}
