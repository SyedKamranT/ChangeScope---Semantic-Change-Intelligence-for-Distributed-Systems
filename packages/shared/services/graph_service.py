"""Graph Query Service enforcing tenant isolation across Neo4j and Knowledge Graph projections."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.config import settings
from packages.shared.errors import AuthorizationError
from packages.shared.impact.graph import DependencyKnowledgeGraph
from packages.shared.logger import logger
from packages.shared.models import RuntimeDependency
from packages.shared.ontology_models import OntologyRelationship
from packages.shared.security.authorization import SecurityContext, TenantRole


class GraphQueryService:
    """Service layer ensuring graph queries and traversals remain strictly isolated to caller tenants."""

    @classmethod
    async def build_tenant_graph(cls, db: AsyncSession, tenant_id: str) -> DependencyKnowledgeGraph:
        """Hydrates a tenant-scoped DependencyKnowledgeGraph from PostgreSQL runtime and ontology stores."""
        graph = DependencyKnowledgeGraph(tenant_id=tenant_id)

        dep_stmt = select(RuntimeDependency).where(RuntimeDependency.tenant_id == tenant_id)
        runtime_deps = (await db.execute(dep_stmt)).scalars().all()
        for d in runtime_deps:
            graph.add_node(node_id=d.caller_service_name, name=d.caller_service_name, entity_type="Service")
            graph.add_node(
                node_id=d.callee_service_name,
                name=d.callee_service_name,
                entity_type="Service" if not d.callee_service_name.startswith("db:") else "Database",
            )
            rel_type = "READS" if d.protocol == "DATABASE" else ("PUBLISHES" if d.protocol == "MESSAGING" else "CALLS")
            graph.add_edge(
                source_id=d.caller_service_name,
                target_id=d.callee_service_name,
                relationship_type=rel_type,
                confidence=1.0,
                provenance="RUNTIME_OBSERVED",
                is_observed=True,
                call_count_7d=d.call_count_7d,
                p95_latency_ms=d.p95_latency_ms,
                last_observed_at=d.last_observed_at,
                evidence_refs=[f"Trace exemplar: {d.exemplar_trace_id}"] if d.exemplar_trace_id else [],
            )

        rel_stmt = select(OntologyRelationship).where(OntologyRelationship.tenant_id == tenant_id)
        ontology_rels = (await db.execute(rel_stmt)).scalars().all()
        for rel in ontology_rels:
            graph.add_edge(
                source_id=rel.source_id,
                target_id=rel.target_id,
                relationship_type=rel.rel_type,
                confidence=rel.confidence,
                provenance=rel.provenance,
                valid_from=rel.valid_from,
                valid_to=rel.valid_to,
                evidence_refs=rel.evidence_refs or [],
            )

        return graph

    @classmethod
    async def project_outbox_event(
        cls,
        tenant_id: str,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> str:
        """Projects an outbox event into Neo4j using idempotent, tenant-scoped Cypher MERGE statements."""
        if settings.NEO4J_MOCK_MODE:
            logger.info(
                "neo4j_outbox_mock_projection",
                tenant_id=tenant_id,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                event_type=event_type,
            )
            return "MOCK_PROJECTED"

        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            connection_timeout=settings.NEO4J_CONNECTION_TIMEOUT,
        )
        try:
            async with driver.session(database=settings.NEO4J_DATABASE) as session:
                await session.run(
                    """
                    MERGE (a:AggregateNode {tenant_id: $tenant_id, id: $aggregate_id})
                    SET a.aggregate_type = $aggregate_type,
                        a.last_event_type = $event_type,
                        a.updated_at = datetime()
                    """,
                    tenant_id=tenant_id,
                    aggregate_id=aggregate_id,
                    aggregate_type=aggregate_type,
                    event_type=event_type,
                )
            return "PROJECTED"
        finally:
            await driver.close()

    @classmethod
    def assert_cypher_tenant_isolation(
        cls,
        context: SecurityContext,
        query: str,
        parameters: dict[str, Any],
    ) -> None:
        """Validates that a Cypher query explicitly binds and parameters supply the caller's tenant_id."""
        context.assert_role(TenantRole.VIEWER)

        # 1. Parameter Assertion
        tenant_param = parameters.get("tenant_id")
        if not tenant_param:
            raise AuthorizationError("Graph query error: Mandatory 'tenant_id' parameter is missing.")

        if tenant_param != context.tenant_id:
            raise AuthorizationError(
                f"Graph query tenant violation: Parameter tenant '{tenant_param}' does not match context '{context.tenant_id}'."
            )

        # 2. Query AST/Text Guard: Must contain tenant_id constraint
        q_lower = query.lower()
        if "tenant_id" not in q_lower and "$tenant_id" not in q_lower:
            raise AuthorizationError(
                "Graph query error: Cypher query does not enforce 'tenant_id' predicate filtering."
            )

    @classmethod
    def get_scoped_knowledge_graph(
        cls,
        context: SecurityContext,
    ) -> DependencyKnowledgeGraph:
        """Constructs an empty or tenant-bound DependencyKnowledgeGraph enforcing strict context isolation."""
        context.assert_role(TenantRole.VIEWER)
        return DependencyKnowledgeGraph(tenant_id=context.tenant_id)

    @classmethod
    def validate_graph_node_access(
        cls,
        context: SecurityContext,
        node_tenant_id: str,
    ) -> None:
        """Guards against unauthorized cross-tenant graph traversal."""
        if node_tenant_id != context.tenant_id:
            raise AuthorizationError(
                f"Unauthorized graph traversal: Node belonging to '{node_tenant_id}' cannot be accessed by '{context.tenant_id}'."
            )
