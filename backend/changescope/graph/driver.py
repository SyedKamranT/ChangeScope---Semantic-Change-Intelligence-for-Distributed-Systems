"""ChangeScope Neo4j Driver & Connection Management with Offline Mock Mode."""

import asyncio
from typing import Any

from changescope.common.logger import logger
from changescope.config import settings
from neo4j import AsyncDriver, AsyncGraphDatabase


class MockNeo4jSession:
    """In-memory mock Neo4j session for offline testing and air-gapped environments."""

    def __init__(self, records_dict: dict[str, list[dict[str, Any]]] | None = None):
        self.records_dict = records_dict or {}
        self.executed_queries: list[dict[str, Any]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def run(self, query: str, parameters: dict[str, Any] | None = None, **kwargs) -> Any:
        params = parameters or kwargs
        self.executed_queries.append({"query": query, "parameters": params})

        # Return mock result
        class MockResult:
            def __init__(self, rows: list[dict[str, Any]]):
                self.rows = rows

            async def data(self) -> list[dict[str, Any]]:
                return self.rows

            async def single(self) -> dict[str, Any] | None:
                return self.rows[0] if self.rows else None

        # Return matches based on query keywords or default empty
        matched_rows: list[dict[str, Any]] = []
        for key, rows in self.records_dict.items():
            if key in query:
                matched_rows = rows
                break

        return MockResult(matched_rows)


class MockNeo4jDriver:
    """Mock Driver mimicking official Neo4j AsyncDriver interface."""

    def __init__(self, records_dict: dict[str, list[dict[str, Any]]] | None = None):
        self.records_dict = records_dict or {}
        self.executed_queries: list[dict[str, Any]] = []

    def session(self, **kwargs) -> MockNeo4jSession:
        session = MockNeo4jSession(self.records_dict)
        self.executed_queries = session.executed_queries
        return session

    async def close(self) -> None:
        pass


class GraphDriverFactory:
    """Factory providing AsyncDriver or MockDriver based on configuration."""

    _driver: AsyncDriver | MockNeo4jDriver | None = None
    _driver_loop: asyncio.AbstractEventLoop | None = None

    @classmethod
    async def get_driver(cls) -> AsyncDriver | MockNeo4jDriver:
        current_loop = asyncio.get_running_loop()
        if cls._driver is not None:
            if cls._driver_loop is current_loop:
                return cls._driver
            # Previous event loop closed or changed: discard stale AsyncDriver safely
            cls._driver = None
            cls._driver_loop = None

        if settings.NEO4J_MOCK_MODE or settings.ENVIRONMENT == "test":
            logger.info("Using MockNeo4jDriver for offline execution")
            cls._driver = MockNeo4jDriver()
            cls._driver_loop = current_loop
            return cls._driver

        try:
            logger.info("Connecting to Neo4j instance", uri=settings.NEO4J_URI)
            cls._driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
            cls._driver_loop = current_loop
            # Verify connectivity
            async with cls._driver.session(database=settings.NEO4J_DATABASE) as session:
                await session.run("RETURN 1 AS ping")
            return cls._driver
        except Exception as e:
            logger.warning("Neo4j connection failed; falling back to MockNeo4jDriver", error=str(e))
            cls._driver = MockNeo4jDriver()
            cls._driver_loop = current_loop
            return cls._driver

    @classmethod
    async def close_driver(cls) -> None:
        if cls._driver is not None:
            await cls._driver.close()
            cls._driver = None
            cls._driver_loop = None
