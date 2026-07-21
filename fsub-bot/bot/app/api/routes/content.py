"""
Content Management endpoints.
"""

import os
import re
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from hydrogram import Client

from app.api.deps import get_current_admin, get_db, get_bot
from app.models.content import Content, ContentType
from app.services.content_service import create_content
from app.bot.handlers.content import _post_to_db_channel, _extract_file_info
from app.core.config import get_settings

router = APIRouter(prefix="/content", tags=["Content"])


@router.get("/")
async def list_content(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """List all contents (with files)."""
    stmt = select(Content).options(selectinload(Content.files)).order_by(Content.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.delete("/{content_id}")
async def delete_content(
    content_id: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
    bot: Client = Depends(get_bot),
):
    """Delete a content by its UUID."""
    import uuid
    try:
        content_uuid = uuid.UUID(content_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    stmt = select(Content).where(Content.content_id == content_uuid)
    result = await db.execute(stmt)
    content = result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
        
    if content.catalogue_msg_id:
        settings = get_settings()
        try:
            await bot.delete_messages(chat_id=settings.DB_CHANNEL_ID, message_ids=content.catalogue_msg_id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to delete channel message: {e}")
    
    await db.delete(content)
    await db.commit()
    return {"message": "Content deleted successfully"}


class LinkUploadRequest(BaseModel):
    link: str
    caption: str | None = None


@router.post("/from-link")
async def upload_from_link(
    data: LinkUploadRequest,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
    bot: Client = Depends(get_bot),
):
    text = data.link.strip()
    match_public = re.match(r"https?://t\.me/([^/]+)/(\d+)", text)
    match_private = re.match(r"https?://t\.me/c/(\d+)/(\d+)", text)
    
    chat_id = None
    message_id = None
    
    if match_private:
        chat_id = int(f"-100{match_private.group(1)}")
        message_id = int(match_private.group(2))
    elif match_public:
        username = match_public.group(1)
        if username != "c":
            chat_id = username
            message_id = int(match_public.group(2))
            
    if not chat_id or not message_id:
        raise HTTPException(status_code=400, detail="Invalid Telegram link format")
        
    try:
        msg = await bot.get_messages(chat_id, message_ids=message_id)
        if not msg or getattr(msg, "empty", False):
            raise HTTPException(status_code=404, detail="Message not found or bot lacks access")
            
        file_info = _extract_file_info(msg)
        if not file_info:
            raise HTTPException(status_code=400, detail="Message does not contain supported media")
            
        content_type = ContentType(file_info["file_type"])
        
        settings = get_settings()
        uploader_id = settings.OWNER_ID

        content = await create_content(
            session=db,
            uploader_id=uploader_id,
            content_type=content_type,
            files=[file_info],
            caption=data.caption,
        )
        await db.commit()
        
        await _post_to_db_channel(bot, str(content.content_id), data.caption)
        
        return {"message": "Content imported successfully", "content_id": str(content.content_id)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch or save content: {e}")


@router.post("/upload-file")
async def upload_file(
    file: UploadFile = File(...),
    caption: str = Form(None),
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
    bot: Client = Depends(get_bot),
):
    settings = get_settings()
    
    temp_path = f"/tmp/{file.filename}"
    try:
        with open(temp_path, "wb") as f:
            f.write(await file.read())
            
        mime = file.content_type or ""
        msg = None
        if mime.startswith("video/"):
            msg = await bot.send_video(chat_id=settings.DB_CHANNEL_ID, video=temp_path)
        elif mime.startswith("image/"):
            msg = await bot.send_photo(chat_id=settings.DB_CHANNEL_ID, photo=temp_path)
        elif mime.startswith("audio/"):
            msg = await bot.send_audio(chat_id=settings.DB_CHANNEL_ID, audio=temp_path)
        else:
            msg = await bot.send_document(chat_id=settings.DB_CHANNEL_ID, document=temp_path)
            
        if not msg:
            raise HTTPException(status_code=500, detail="Failed to upload file to Telegram")
            
        file_info = _extract_file_info(msg)
        if not file_info:
            raise HTTPException(status_code=500, detail="Failed to extract file info from Telegram message")
            
        await msg.delete()
        
        content_type = ContentType(file_info["file_type"])
        uploader_id = settings.OWNER_ID
        
        content = await create_content(
            session=db,
            uploader_id=uploader_id,
            content_type=content_type,
            files=[file_info],
            caption=caption,
        )
        await db.commit()
        
        await _post_to_db_channel(bot, str(content.content_id), caption)
        
        return {"message": "Content uploaded successfully", "content_id": str(content.content_id)}
        
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
