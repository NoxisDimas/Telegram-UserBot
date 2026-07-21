"""
Content & ContentFile models — metadata for Telegram-stored media.
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ContentType(str, enum.Enum):
    """Supported Telegram media types."""

    VIDEO = "VIDEO"
    PHOTO = "PHOTO"
    DOCUMENT = "DOCUMENT"
    AUDIO = "AUDIO"
    ANIMATION = "ANIMATION"


class Content(TimestampMixin, Base):
    """A piece of content that can contain one or more files (albums)."""

    __tablename__ = "contents"

    content_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    caption: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    catalogue_msg_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    content_type: Mapped[ContentType] = mapped_column(
        Enum(ContentType, name="content_type", create_constraint=True),
        nullable=False,
    )
    uploader_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Relationships ────────────────────────────────────────
    uploader: Mapped["User"] = relationship(
        "User", back_populates="contents", lazy="selectin",
    )
    files: Mapped[list["ContentFile"]] = relationship(
        "ContentFile",
        back_populates="content",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="ContentFile.order",
    )

    def __repr__(self) -> str:
        return f"<Content {self.content_id} type={self.content_type.value}>"


class ContentFile(TimestampMixin, Base):
    """Individual file within a Content (supports albums / multi-part)."""

    __tablename__ = "content_files"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
    )
    content_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("contents.content_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    telegram_file_id: Mapped[str] = mapped_column(
        String(256), nullable=False,
        comment="Telegram API file_id for sending",
    )
    file_unique_id: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="Telegram unique file identifier",
    )
    file_type: Mapped[ContentType] = mapped_column(
        Enum(ContentType, name="content_type", create_constraint=True),
        nullable=False,
    )
    order: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0",
        comment="Order within album/group",
    )

    # ── Relationships ────────────────────────────────────────
    content: Mapped["Content"] = relationship(
        "Content", back_populates="files",
    )

    def __repr__(self) -> str:
        return (
            f"<ContentFile {self.id} "
            f"unique={self.file_unique_id} type={self.file_type.value}>"
        )
