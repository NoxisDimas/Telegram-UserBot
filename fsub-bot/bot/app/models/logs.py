"""
AccessLog & AuditLog models — tracking & compliance.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AccessLog(Base):
    """Records every content access attempt by a user."""

    __tablename__ = "access_logs"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True,
    )
    content_id: Mapped[str] = mapped_column(
        Uuid, nullable=False, index=True,
    )
    success: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="Whether the content was successfully delivered",
    )
    failure_reason: Mapped[str | None] = mapped_column(
        String(256), nullable=True,
        comment="Reason for failure (fsub, expired, banned, etc.)",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<AccessLog user={self.user_id} "
            f"content={self.content_id} ok={self.success}>"
        )


class AuditLog(Base):
    """Immutable, append-only log of all administrative actions.

    This table must never be updated or deleted from in application code.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
    )
    actor_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True,
        comment="Telegram user ID of the actor",
    )
    action: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True,
        comment="Action identifier (e.g. SET_ROLE, ADD_CONTENT, BAN_USER)",
    )
    target: Mapped[str | None] = mapped_column(
        String(256), nullable=True,
        comment="Target of the action (user ID, content ID, channel ID, etc.)",
    )
    payload: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Arbitrary JSON context for the action",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog actor={self.actor_id} "
            f"action={self.action!r} target={self.target}>"
        )
