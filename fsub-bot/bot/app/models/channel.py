"""
Channel & FsubChannel models — forced subscription channel list.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Channel(TimestampMixin, Base):
    """A Telegram channel/group tracked for forced subscription."""

    __tablename__ = "channels"

    channel_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False,
        comment="Telegram chat ID (negative for channels/groups)",
    )
    title: Mapped[str] = mapped_column(
        String(256), nullable=False,
    )
    username: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="Public @username (None for private channels)",
    )
    invite_link: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Invite link for private channels",
    )
    is_private: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False,
        comment="Whether this channel is part of the active fsub list",
    )

    def __repr__(self) -> str:
        return f"<Channel {self.channel_id} title={self.title!r}>"

    @property
    def link(self) -> str:
        """Return the best available link for user-facing display."""
        if self.username:
            return f"https://t.me/{self.username}"
        if self.invite_link:
            return self.invite_link
        return f"tg://resolve?domain={self.channel_id}"
