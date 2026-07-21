"""
Job model — persistent queue for background tasks.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import DateTime, Enum, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class JobStatus(str, enum.Enum):
    """Lifecycle states of a background job."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DEAD = "DEAD"  # moved to DLQ after max retries


class Job(TimestampMixin, Base):
    """A background task persisted to PostgreSQL and dispatched via Redis."""

    __tablename__ = "jobs"

    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    job_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
        comment="Task type: membership_check, send_content, webhook_delivery, scheduled_post",
    )
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
        comment="Serialised task arguments",
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", create_constraint=True),
        default=JobStatus.PENDING,
        server_default=JobStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    retries: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False,
    )
    max_retries: Mapped[int] = mapped_column(
        Integer, default=3, server_default="3", nullable=False,
    )
    error: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Last error message",
    )
    scheduled_at: Mapped[None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Optional: earliest time to run this job",
    )

    def __repr__(self) -> str:
        return (
            f"<Job {self.job_id} type={self.job_type} "
            f"status={self.status.value} retries={self.retries}>"
        )

    @property
    def can_retry(self) -> bool:
        """Whether the job has retries remaining."""
        return self.retries < self.max_retries
