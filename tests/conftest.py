"""Global Pytest Fixtures for ChangeScope test suite."""

import pytest_asyncio

from packages.shared.database import engine
from packages.shared.models import Base


@pytest_asyncio.fixture(autouse=True)
async def setup_test_database():
    """Initializes canonical database schemas and provides isolation between test executions."""
    await engine.dispose()
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()
