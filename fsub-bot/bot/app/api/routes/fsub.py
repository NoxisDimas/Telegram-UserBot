"""
FSUB Management endpoints.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from hydrogram import Client

from app.api.deps import get_current_admin, get_db, get_bot
from app.models.channel import Channel

router = APIRouter(prefix="/fsub", tags=["FSUB"])


class ChannelCreate(BaseModel):
    identifier: str
    invite_link: str | None = None
    is_active: bool = True

class ChannelUpdate(BaseModel):
    title: str | None = None
    username: str | None = None
    invite_link: str | None = None
    is_private: bool | None = None
    is_active: bool | None = None


@router.get("/")
async def list_channels(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """List all FSUB channels."""
    stmt = select(Channel).order_by(Channel.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/")
async def add_channel(
    req: ChannelCreate,
    db: AsyncSession = Depends(get_db),
    bot: Client = Depends(get_bot),
    _admin=Depends(get_current_admin),
):
    """Add a new FSUB channel."""
    from hydrogram import enums
    
    import re
    identifier = req.identifier.strip()
    
    # 1. Parse private message link (e.g., https://t.me/c/123456789/123)
    private_msg_match = re.search(r"t\.me/c/(\d+)", identifier)
    if private_msg_match:
        chat_id = int(f"-100{private_msg_match.group(1)}")
    else:
        # 2. Parse public message link or standard link (e.g., https://t.me/username/123 or t.me/username)
        public_match = re.search(r"t\.me/([^/]+)", identifier)
        if public_match:
            part = public_match.group(1)
            if part.startswith("+") or part == "joinchat":
                raise HTTPException(status_code=400, detail="Cannot resolve private invite links directly. Please use a message link from the channel, or its Channel ID (-100...).")
            chat_id = part if part.startswith("@") else f"@{part}"
        else:
            # 3. Direct ID or Username
            try:
                chat_id = int(identifier)
            except ValueError:
                chat_id = identifier if identifier.startswith("@") else f"@{identifier}"
        
    try:
        chat = await bot.get_chat(chat_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bot failed to fetch channel details. Make sure the bot is an admin in the channel. ({e})")
        
    if chat.type not in [enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP, enums.ChatType.GROUP]:
        raise HTTPException(status_code=400, detail="Provided identifier is not a valid channel or group")

    stmt = select(Channel).where(Channel.channel_id == chat.id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Channel already exists in the database")

    new_channel = Channel(
        channel_id=chat.id,
        title=chat.title,
        username=chat.username,
        invite_link=req.invite_link or chat.invite_link,
        is_private=(chat.username is None),
        is_active=req.is_active,
    )
    db.add(new_channel)
    await db.commit()
    await db.refresh(new_channel)
    return new_channel


@router.put("/{channel_id}")
async def update_channel(
    channel_id: int,
    req: ChannelUpdate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Update an FSUB channel."""
    stmt = select(Channel).where(Channel.channel_id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(channel, key, value)
    
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return channel


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Delete an FSUB channel."""
    stmt = select(Channel).where(Channel.channel_id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    await db.delete(channel)
    await db.commit()
    return {"message": "Channel deleted successfully"}
