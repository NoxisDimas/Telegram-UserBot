"""
User model with role-based access control.
"""

from __future__ import annotations

import enum

from sqlalchemy import BigInteger, Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class UserRole(str, enum.Enum):
    """User permission levels (descending privilege)."""

    OWNER = "OWNER"
    ADMIN = "ADMIN"
    STAFF = "STAFF"
    USER = "USER"


# Permission hierarchy: OWNER > ADMIN > STAFF > USER
ROLE_HIERARCHY: dict[UserRole, int] = {
    UserRole.OWNER: 100,
    UserRole.ADMIN: 80,
    UserRole.STAFF: 60,
    UserRole.USER: 10,
}


class User(TimestampMixin, Base):
    """Telegram user tracked by the bot."""

    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False,
        comment="Telegram user ID",
    )
    username: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True,
    )
    first_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", create_constraint=True),
        default=UserRole.USER,
        server_default=UserRole.USER.value,
        nullable=False,
        index=True,
    )
    is_banned: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False,
    )

    # ── Relationships ────────────────────────────────────────
    contents: Mapped[list["Content"]] = relationship(  # noqa: F821
        "Content", back_populates="uploader", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User {self.user_id} role={self.role.value}>"

    def has_permission(self, required_role: UserRole) -> bool:
        """Check if user's role meets or exceeds the required level."""
        return ROLE_HIERARCHY.get(self.role, 0) >= ROLE_HIERARCHY.get(required_role, 0)
