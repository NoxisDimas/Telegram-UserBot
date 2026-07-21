"""
Auth endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.api.security import create_access_token, verify_password
from app.models.admin import AdminUser

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Authenticate admin and return JWT."""
    stmt = select(AdminUser).where(AdminUser.username == form_data.username)
    result = await db.execute(stmt)
    admin = result.scalar_one_or_none()

    if not admin or not verify_password(form_data.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=admin.username)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
async def get_me(current_admin: AdminUser = Depends(get_current_admin)):
    """Get current logged in admin."""
    return {
        "id": str(current_admin.id),
        "username": current_admin.username,
        "is_default": current_admin.is_default,
    }
