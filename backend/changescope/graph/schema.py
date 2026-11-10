"""ChangeScope Neo4j Schema Constraints & Indices Definition."""

from changescope.common.logger import logger
from changescope.graph.driver import GraphDriverFactory

CONSTRAINTS = [
    "CREATE CONSTRAINT c_service_id IF NOT EXISTS FOR (s:Service) REQUIRE (s.tenant_id, s.id) IS UNIQUE",
    "CREATE CONSTRAINT c_endpoint_id IF NOT EXISTS FOR (e:Endpoint) REQUIRE (e.tenant_id, e.id) IS UNIQUE",
    "CREATE CONSTRAINT c_schema_id IF NOT EXISTS FOR (sc:Schema) REQUIRE (sc.tenant_id, sc.id) IS UNIQUE",
    "CREATE CONSTRAINT c_table_id IF NOT EXISTS FOR (t:DatabaseTable) REQUIRE (t.tenant_id, t.id) IS UNIQUE",
    "CREATE CONSTRAINT c_channel_id IF NOT EXISTS FOR (ch:MessageChannel) REQUIRE (ch.tenant_id, ch.id) IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX idx_endpoint_route IF NOT EXISTS FOR (e:Endpoint) ON (e.tenant_id, e.method, e.path_template)",
    "CREATE INDEX idx_service_name IF NOT EXISTS FOR (s:Service) ON (s.tenant_id, s.name)",
]


async def init_neo4j_schema() -> None:
    """Apply all Neo4j uniqueness constraints and performance indexes."""
    driver = await GraphDriverFactory.get_driver()
    async with driver.session() as session:
        for c in CONSTRAINTS:
            try:
                await session.run(c)
            except Exception as e:
                logger.warning("Constraint creation notice", constraint=c, error=str(e))

        for idx in INDEXES:
            try:
                await session.run(idx)
            except Exception as e:
                logger.warning("Index creation notice", index=idx, error=str(e))

    logger.info("Neo4j graph schema constraints and indices initialized successfully")
