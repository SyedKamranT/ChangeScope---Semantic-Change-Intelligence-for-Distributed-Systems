"""ChangeScope Full Knowledge Graph Disaster Recovery & Rebuilder."""

from changescope.common.logger import logger
from changescope.db.models import Repository, RuntimeDependency
from changescope.graph.driver import GraphDriverFactory
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class GraphRebuilder:
    """Rebuilds the entire Neo4j graph projection from canonical PostgreSQL state."""

    @classmethod
    async def rebuild_tenant_graph(cls, db_session: AsyncSession, tenant_id: str) -> dict[str, int]:
        """Truncates tenant graph partition in Neo4j and re-projects all canonical records."""
        driver = await GraphDriverFactory.get_driver()

        logger.info("Starting complete graph projection rebuild", tenant_id=tenant_id)

        # 1. Clear existing tenant nodes and relationships in Neo4j
        async with driver.session() as session:
            await session.run(
                "MATCH (n {tenant_id: $tenant_id}) DETACH DELETE n",
                tenant_id=tenant_id,
            )

        # 2. Stream canonical Repositories -> Service Nodes
        result = await db_session.execute(select(Repository).where(Repository.tenant_id == tenant_id))
        repos = result.scalars().all()

        nodes_projected = 0
        edges_projected = 0

        async with driver.session() as session:
            for repo in repos:
                await session.run(
                    """
                    MERGE (s:Service {tenant_id: $tenant_id, id: $id})
                    SET s.name = $name, s.tier = $tier, s.primary_language = $lang
                    """,
                    tenant_id=tenant_id,
                    id=repo.id,
                    name=repo.name,
                    tier=repo.tier,
                    lang=repo.primary_language,
                )
                nodes_projected += 1

            # 3. Stream Runtime Dependencies -> Observed CALLS Edges
            dep_result = await db_session.execute(
                select(RuntimeDependency).where(RuntimeDependency.tenant_id == tenant_id)
            )
            deps = dep_result.scalars().all()

            for dep in deps:
                # Upsert caller service, provider service, endpoint, and CALLS edge
                await session.run(
                    """
                    MERGE (caller:Service {tenant_id: $tenant_id, name: $caller_name})
                    ON CREATE SET caller.id = $caller_name, caller.tier = 'TIER_2'

                    MERGE (provider:Service {tenant_id: $tenant_id, name: $callee_name})
                    ON CREATE SET provider.id = $callee_name, provider.tier = 'TIER_2'

                    MERGE (ep:Endpoint {tenant_id: $tenant_id, method: $method, path_template: $route})
                    ON CREATE SET ep.id = $route + ':' + $method

                    MERGE (provider)-[:EXPOSES {tenant_id: $tenant_id}]->(ep)

                    MERGE (caller)-[r:CALLS {tenant_id: $tenant_id, target_endpoint_id: ep.id}]->(ep)
                    SET r.provenance = 'OTEL_TRACE',
                        r.confidence = 0.95,
                        r.is_observed = true,
                        r.call_count_7d = $count,
                        r.p95_latency_ms = $p95,
                        r.last_observed_at = datetime(),
                        r.evidence_ref = $evidence_ref
                    """,
                    tenant_id=tenant_id,
                    caller_name=dep.caller_service_name,
                    callee_name=dep.callee_service_name,
                    method=dep.http_method,
                    route=dep.http_route,
                    count=dep.call_count_7d,
                    p95=dep.p95_latency_ms,
                    evidence_ref=f"otel_runtime_dep:{dep.id}",
                )
                edges_projected += 1

        logger.info(
            "Graph rebuild finished successfully",
            tenant_id=tenant_id,
            nodes_projected=nodes_projected,
            edges_projected=edges_projected,
        )
        return {"nodes_projected": nodes_projected, "edges_projected": edges_projected}
