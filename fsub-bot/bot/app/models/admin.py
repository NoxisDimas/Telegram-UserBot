"""
AdminUser model for Dashboard access.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AdminUser(TimestampMixin, Base):
    """User account for accessing the dashboard."""

    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    username: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(256), nullable=False,
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False,
        comment="Whether this is the initial default admin account",
    )

    def __repr__(self) -> str:
        return f"<AdminUser {self.username}>"
