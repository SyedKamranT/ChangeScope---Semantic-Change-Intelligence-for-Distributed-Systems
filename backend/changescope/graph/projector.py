"""ChangeScope Transactional Outbox Projector for Neo4j Graph Projections."""

from typing import Any

from changescope.common.exceptions import InvalidProvenanceError
from changescope.common.logger import logger
from changescope.graph.driver import GraphDriverFactory


class GraphProjector:
    """Consumes PostgreSQL outbox events and executes idempotent Cypher projections."""

    @staticmethod
    def _validate_dependency_edge(dep: dict[str, Any]) -> None:
        """Enforce strict provenance and evidence invariants on all graph relationships."""
        provenance = dep.get("provenance")
        if provenance not in {"STATIC_AST", "OTEL_TRACE", "CONTRACT_DECLARATION", "DDL_MIGRATION"}:
            raise InvalidProvenanceError(f"Invalid edge provenance: '{provenance}'. Must be one of verified sources.")

        confidence = dep.get("confidence")
        if confidence is None or not (0.0 <= float(confidence) <= 1.0):
            raise InvalidProvenanceError(
                f"Invalid edge confidence: '{confidence}'. Must be a float between 0.0 and 1.0."
            )

        if not dep.get("evidence_ref"):
            raise InvalidProvenanceError("Missing required 'evidence_ref' on dependency relationship.")

    @classmethod
    async def project_scan(cls, tenant_id: str, payload: dict[str, Any]) -> None:
        """Idempotently project a scan's services, endpoints, schemas, and dependencies into Neo4j."""
        driver = await GraphDriverFactory.get_driver()
        service = payload.get("service")
        endpoints = payload.get("endpoints", [])
        dependencies = payload.get("dependencies", [])

        async with driver.session() as session:
            # 1. Project Service Node
            if service:
                await session.run(
                    """
                    MERGE (s:Service {tenant_id: $tenant_id, id: $service.id})
                    ON CREATE SET s.name = $service.name, s.tier = $service.tier, s.created_at = datetime()
                    ON MATCH SET s.name = $service.name, s.tier = $service.tier, s.updated_at = datetime()
                    """,
                    tenant_id=tenant_id,
                    service=service,
                )

            # 2. Project Endpoints and EXPOSES Edges
            for ep in endpoints:
                await session.run(
                    """
                    MERGE (e:Endpoint {tenant_id: $tenant_id, id: $ep.id})
                    ON CREATE SET e.method = $ep.method, e.path_template = $ep.path_template
                    ON MATCH SET e.method = $ep.method, e.path_template = $ep.path_template
                    WITH e
                    MATCH (s:Service {tenant_id: $tenant_id, id: $service_id})
                    MERGE (s)-[:EXPOSES {tenant_id: $tenant_id}]->(e)
                    """,
                    tenant_id=tenant_id,
                    ep=ep,
                    service_id=service["id"] if service else None,
                )

            # 3. Project Dependencies (CALLS Edges) with Invariant Validation
            for dep in dependencies:
                cls._validate_dependency_edge(dep)

                # Ensure caller service node exists
                await session.run(
                    """
                    MERGE (c:Service {tenant_id: $tenant_id, id: $caller_id})
                    ON CREATE SET c.name = $caller_name, c.tier = 'TIER_2'
                    """,
                    tenant_id=tenant_id,
                    caller_id=dep["caller_service_id"],
                    caller_name=dep.get("caller_service_name", dep["caller_service_id"]),
                )

                # Merge CALLS edge with full provenance and evidence
                await session.run(
                    """
                    MATCH (c:Service {tenant_id: $tenant_id, id: $caller_id})
                    MATCH (e:Endpoint {tenant_id: $tenant_id, id: $target_ep_id})
                    MERGE (c)-[r:CALLS {tenant_id: $tenant_id, target_endpoint_id: $target_ep_id}]->(e)
                    SET r.provenance = $provenance,
                        r.confidence = $confidence,
                        r.is_observed = $is_observed,
                        r.call_count_7d = $call_count_7d,
                        r.p95_latency_ms = $p95_latency_ms,
                        r.evidence_ref = $evidence_ref,
                        r.last_observed_at = datetime()
                    """,
                    tenant_id=tenant_id,
                    caller_id=dep["caller_service_id"],
                    target_ep_id=dep["target_endpoint_id"],
                    provenance=dep["provenance"],
                    confidence=float(dep["confidence"]),
                    is_observed=bool(dep.get("is_observed", False)),
                    call_count_7d=int(dep.get("call_count_7d", 0)),
                    p95_latency_ms=float(dep.get("p95_latency_ms", 0.0)),
                    evidence_ref=dep["evidence_ref"],
                )

        logger.info(
            "Projected scan into knowledge graph",
            tenant_id=tenant_id,
            endpoints_count=len(endpoints),
            dependencies_count=len(dependencies),
        )
