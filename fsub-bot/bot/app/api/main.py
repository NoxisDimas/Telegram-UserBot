"""
FastAPI application factory and main setup.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import auth, broadcast, content, fsub, stats, users
from app.api.security import get_password_hash
from app.core.config import get_settings
from app.core.database import get_session
from app.models.admin import AdminUser
from hydrogram import Client

logger = logging.getLogger(__name__)


async def seed_default_admin() -> None:
    """Create a default admin user if none exists."""
    async with get_session() as session:
        stmt = select(AdminUser).where(AdminUser.is_default == True)
        result = await session.execute(stmt)
        admin = result.scalar_one_or_none()
        
        if not admin:
            logger.info("No default admin found. Creating one...")
            default_admin = AdminUser(
                username="admin",
                password_hash=get_password_hash("admin123"),
                is_default=True,
            )
            session.add(default_admin)
            await session.commit()
            logger.info("Default admin created (username: admin, password: admin123)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events for FastAPI."""
    from app.core.database import init_db
    # Ensure DB tables exist
    await init_db()
    # Seed default user
    await seed_default_admin()
    
    settings = get_settings()
    bot_client = Client(
        name="api_bot",
        api_id=settings.API_ID,
        api_hash=settings.API_HASH,
        bot_token=settings.BOT_TOKEN,
        in_memory=True,
    )
    await bot_client.start()
    app.state.bot = bot_client

    yield

    await bot_client.stop()
    from app.core.database import close_db
    await close_db()


def create_api() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Fsub Bot Dashboard API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Allow requests from the frontend dashboard
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify the exact domain
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(auth.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    app.include_router(fsub.router, prefix="/api")
    app.include_router(content.router, prefix="/api")
    app.include_router(broadcast.router, prefix="/api")
    app.include_router(stats.router, prefix="/api")

    @app.get("/api/health")
    async def health_check():
        return {"status": "ok"}

    return app
