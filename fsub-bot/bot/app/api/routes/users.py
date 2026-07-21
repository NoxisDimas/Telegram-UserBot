"""
User settings endpoints.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.api.security import get_password_hash, verify_password
from app.models.admin import AdminUser
from app.models.user import User, UserRole

router = APIRouter(prefix="/users", tags=["Users"])


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.put("/password")
async def change_password(
    req: ChangePasswordRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Change logged-in admin's password."""
    if not verify_password(req.old_password, current_admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect old password",
        )
    
    current_admin.password_hash = get_password_hash(req.new_password)
    db.add(current_admin)
    await db.commit()
    return {"message": "Password updated successfully"}


# ── Dashboard Admins CRUD ─────────────────────────────────────

@router.get("/admins")
async def list_admins(
    db: AsyncSession = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    stmt = select(AdminUser).order_by(AdminUser.created_at.desc())
    result = await db.execute(stmt)
    admins = result.scalars().all()
    # Mask password hash
    return [
        {
            "id": a.id,
            "username": a.username,
            "is_default": a.is_default,
            "created_at": a.created_at,
        }
        for a in admins
    ]


class CreateAdminRequest(BaseModel):
    username: str
    password: str


@router.post("/admins")
async def create_admin(
    req: CreateAdminRequest,
    db: AsyncSession = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    stmt = select(AdminUser).where(AdminUser.username == req.username)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")
        
    new_admin = AdminUser(
        username=req.username,
        password_hash=get_password_hash(req.password),
        is_default=False,
    )
    db.add(new_admin)
    await db.commit()
    return {"message": "Admin created successfully"}


class ResetPasswordRequest(BaseModel):
    new_password: str


@router.put("/admins/{admin_id}/password")
async def reset_admin_password(
    admin_id: uuid.UUID,
    req: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    stmt = select(AdminUser).where(AdminUser.id == admin_id)
    res = await db.execute(stmt)
    target = res.scalar_one_or_none()
    
    if not target:
        raise HTTPException(status_code=404, detail="Admin not found")
        
    target.password_hash = get_password_hash(req.new_password)
    db.add(target)
    await db.commit()
    return {"message": "Password reset successfully"}


@router.delete("/admins/{admin_id}")
async def delete_admin(
    admin_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    stmt = select(AdminUser).where(AdminUser.id == admin_id)
    res = await db.execute(stmt)
    target = res.scalar_one_or_none()
    
    if not target:
        raise HTTPException(status_code=404, detail="Admin not found")
        
    if target.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete default admin")
        
    await db.delete(target)
    await db.commit()
    return {"message": "Admin deleted successfully"}


# ── Telegram Bot Users CRUD ───────────────────────────────────

@router.get("/bot-users")
async def list_bot_users(
    db: AsyncSession = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    # Limit to 1000 for safety, order by newest
    stmt = select(User).order_by(User.created_at.desc()).limit(1000)
    result = await db.execute(stmt)
    return result.scalars().all()


class RoleUpdateRequest(BaseModel):
    role: UserRole


@router.put("/bot-users/{user_id}/role")
async def update_bot_user_role(
    user_id: int,
    req: RoleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    stmt = select(User).where(User.user_id == user_id)
    res = await db.execute(stmt)
    target = res.scalar_one_or_none()
    
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
        
    target.role = req.role
    db.add(target)
    await db.commit()
    return {"message": "Role updated successfully"}


class BanUpdateRequest(BaseModel):
    is_banned: bool


@router.put("/bot-users/{user_id}/ban")
async def update_bot_user_ban(
    user_id: int,
    req: BanUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    stmt = select(User).where(User.user_id == user_id)
    res = await db.execute(stmt)
    target = res.scalar_one_or_none()
    
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
        
    target.is_banned = req.is_banned
    db.add(target)
    await db.commit()
    return {"message": "Ban status updated successfully"}
