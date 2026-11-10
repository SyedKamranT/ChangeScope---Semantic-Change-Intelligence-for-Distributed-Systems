"""Multi-Hop Blast Radius Traversal and Deterministic Risk Scoring Engine."""

import math
from dataclasses import dataclass, field
from typing import Any

from changescope.common.logger import logger
from changescope.graph.driver import GraphDriverFactory


@dataclass
class ImpactedConsumer:
    """A service impacted directly or transitively by a change."""

    service_id: str
    service_name: str
    service_tier: str  # 'TIER_1', 'TIER_2', 'TIER_3'
    hop_distance: int  # 1 to 5
    path_confidence: float
    is_observed: bool
    rpm: int = 0
    evidence_paths: list[list[str]] = field(default_factory=list)


@dataclass
class BlastRadiusResult:
    """The complete result of blast radius computation."""

    root_endpoint_id: str
    risk_score: int  # 0 to 100
    risk_level: str  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    direct_consumers_count: int
    transitive_consumers_count: int
    max_depth: int
    impacted_consumers: list[ImpactedConsumer]
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)


class BlastRadiusCalculator:
    """Executes multi-hop Cypher traversals in Neo4j and computes deterministic risk scores."""

    TIER_WEIGHTS = {
        "TIER_1": 20.0,
        "TIER_2": 10.0,
        "TIER_3": 5.0,
    }

    SEVERITY_WEIGHTS = {
        "BLOCKING": 50.0,
        "WARNING": 25.0,
        "INFO": 5.0,
    }

    @classmethod
    async def compute_blast_radius(
        cls,
        tenant_id: str,
        endpoint_id: str,
        max_severity: str = "BLOCKING",
        max_depth: int = 5,
        mock_impacted: list[ImpactedConsumer] | None = None,
    ) -> BlastRadiusResult:
        """Traverses knowledge graph to compute impacted consumer DAG and risk score."""
        impacted_consumers: list[ImpactedConsumer] = []

        if mock_impacted is not None:
            impacted_consumers = mock_impacted
        else:
            driver = await GraphDriverFactory.get_driver()
            async with driver.session() as session:
                query = """
                MATCH path = (root:Endpoint {id: $endpoint_id, tenant_id: $tenant_id})
                  <-[:CALLS*1..5]-(consumer:Service {tenant_id: $tenant_id})
                WHERE ALL(r IN relationships(path) WHERE r.confidence >= 0.70)
                WITH consumer,
                     length(path) AS hop_distance,
                     reduce(weight = 1.0, r IN relationships(path) | weight * r.confidence) AS path_confidence,
                     [r IN relationships(path) | r.is_observed] AS observed_flags,
                     [r IN relationships(path) | coalesce(r.call_count_7d, 0)] AS counts,
                     [n IN nodes(path) | coalesce(n.name, n.id)] AS traversal_names
                RETURN
                  consumer.id AS service_id,
                  consumer.name AS service_name,
                  consumer.tier AS service_tier,
                  min(hop_distance) AS min_depth,
                  max(path_confidence) AS max_confidence,
                  any(flag IN observed_flags WHERE flag = true) AS has_runtime_evidence,
                  max(head(counts)) AS rpm,
                  collect(traversal_names) AS evidence_paths
                ORDER BY min_depth ASC, service_tier ASC
                LIMIT 100
                """
                result = await session.run(query, tenant_id=tenant_id, endpoint_id=endpoint_id)
                records = await result.data()

                for row in records:
                    impacted_consumers.append(
                        ImpactedConsumer(
                            service_id=row["service_id"],
                            service_name=row["service_name"],
                            service_tier=row.get("service_tier", "TIER_2"),
                            hop_distance=row["min_depth"],
                            path_confidence=row["max_confidence"],
                            is_observed=row["has_runtime_evidence"],
                            rpm=row.get("rpm", 0),
                            evidence_paths=row.get("evidence_paths", []),
                        )
                    )

        # Compute deterministic risk score
        risk_score = cls._calculate_risk_score(max_severity, impacted_consumers)
        risk_level = cls._classify_risk_level(risk_score)

        direct_count = sum(1 for c in impacted_consumers if c.hop_distance == 1)
        transitive_count = sum(1 for c in impacted_consumers if c.hop_distance > 1)
        max_observed_depth = max([c.hop_distance for c in impacted_consumers], default=0)

        # Build node/edge presentation for React Flow (@xyflow/react)
        nodes = [{"id": endpoint_id, "type": "endpointNode", "data": {"label": endpoint_id, "is_origin": True}}]
        edges = []
        for c in impacted_consumers:
            nodes.append(
                {
                    "id": c.service_id,
                    "type": "consumerNode",
                    "data": {
                        "label": c.service_name,
                        "tier": c.service_tier,
                        "hop": c.hop_distance,
                        "is_observed": c.is_observed,
                        "rpm": c.rpm,
                    },
                }
            )
            edges.append(
                {
                    "id": f"e-{c.service_id}-{endpoint_id}",
                    "source": c.service_id,
                    "target": endpoint_id,
                    "label": f"Hop {c.hop_distance}",
                }
            )

        logger.info(
            "Computed blast radius",
            endpoint_id=endpoint_id,
            risk_score=risk_score,
            risk_level=risk_level,
            consumers_count=len(impacted_consumers),
        )

        return BlastRadiusResult(
            root_endpoint_id=endpoint_id,
            risk_score=risk_score,
            risk_level=risk_level,
            direct_consumers_count=direct_count,
            transitive_consumers_count=transitive_count,
            max_depth=max_observed_depth,
            impacted_consumers=impacted_consumers,
            nodes=nodes,
            edges=edges,
        )

    @classmethod
    def _calculate_risk_score(cls, max_severity: str, consumers: list[ImpactedConsumer]) -> int:
        """
        R = min(100, BaseSeverity + sum(TierWeight * (1 / Depth) * Confidence * log10(RPM + 10)))
        """
        base_severity = cls.SEVERITY_WEIGHTS.get(max_severity, 10.0)
        accumulated_impact = 0.0

        for c in consumers:
            tier_w = cls.TIER_WEIGHTS.get(c.service_tier, 10.0)
            depth_factor = 1.0 / max(1, c.hop_distance)
            conf = max(0.1, min(1.0, c.path_confidence))
            volume_factor = math.log10(max(0, c.rpm) + 10.0)

            accumulated_impact += tier_w * depth_factor * conf * volume_factor

        total = base_severity + accumulated_impact
        return min(100, int(round(total)))

    @staticmethod
    def _classify_risk_level(score: int) -> str:
        if score >= 80:
            return "CRITICAL"
        elif score >= 60:
            return "HIGH"
        elif score >= 35:
            return "MEDIUM"
        return "LOW"
