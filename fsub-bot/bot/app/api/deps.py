"""
Dependencies for FastAPI endpoints.
"""

from typing import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from hydrogram import Client
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.security import ALGORITHM, SECRET_KEY
from app.core.database import get_session
from app.models.admin import AdminUser

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get DB session."""
    async with get_session() as session:
        yield session


def get_bot(request: Request) -> Client:
    """Dependency to get the Hydrogram bot client from app state."""
    return request.app.state.bot


async def get_current_admin(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    """Dependency to get the current logged-in admin user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    stmt = select(AdminUser).where(AdminUser.username == username)
    result = await db.execute(stmt)
    admin = result.scalar_one_or_none()
    
    if admin is None:
        raise credentials_exception
    return admin
