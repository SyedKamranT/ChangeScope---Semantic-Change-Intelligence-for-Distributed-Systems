"""ChangeScope Database Schema Initializer."""

from changescope.db.models import Base
from changescope.db.session import engine
from sqlalchemy.ext.asyncio import AsyncEngine


async def init_db(target_engine: AsyncEngine = engine) -> None:
    """Create all canonical database tables asynchronously."""
    async with target_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db(target_engine: AsyncEngine = engine) -> None:
    """Drop all canonical database tables asynchronously."""
    async with target_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
