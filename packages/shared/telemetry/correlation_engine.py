"""Runtime-to-Static, OpenAPI, AsyncAPI, and Software Ontology Correlation Engine."""

from typing import Any

from packages.contracts.asyncapi_parser import AsyncOperation
from packages.contracts.models import ExtractedClientCall
from packages.shared.ontology_models import (
    CandidateReviewStatus,
    CoreEntityType,
    OntologyCandidate,
    ProvenanceType,
    RelationshipType,
)
from packages.shared.telemetry.models import (
    CorrelatedDependency,
    CorrelationStatus,
    ObservedServiceDependency,
    ProtocolType,
)


class RuntimeCorrelationEngine:
    """Connects observed runtime traffic to static AST dependencies, OpenAPI routes, and AsyncAPI events."""

    @classmethod
    def correlate_dependencies(
        cls,
        observed_dependencies: list[ObservedServiceDependency],
        static_client_calls: list[ExtractedClientCall] | None = None,
        openapi_endpoints: list[dict[str, Any]] | None = None,
        asyncapi_operations: list[AsyncOperation] | None = None,
    ) -> list[CorrelatedDependency]:
        """Correlates observed dependencies against static code calls, OpenAPI specs, and AsyncAPI events."""
        results: list[CorrelatedDependency] = []
        static_calls = static_client_calls or []
        endpoints = openapi_endpoints or []
        operations = asyncapi_operations or []

        # Index static calls by route/path
        static_by_path: dict[str, list[ExtractedClientCall]] = {}
        for sc in static_calls:
            static_by_path.setdefault(sc.url_or_path, []).append(sc)

        # Index OpenAPI endpoints by "METHOD PATH"
        openapi_set = {f"{ep['method']} {ep['path_template']}" for ep in endpoints if "method" in ep and "path_template" in ep}
        openapi_paths = {ep["path_template"] for ep in endpoints if "path_template" in ep}

        # Index AsyncAPI destinations
        asyncapi_dests = {op.channel_name for op in operations}

        matched_static_keys: set[str] = set()

        # 1. Process all Runtime Observed Dependencies
        for obs in observed_dependencies:
            route = obs.operation_or_route
            method = obs.http_method or "GET"

            # Check static code alignment
            matching_static = [
                c for c in static_calls
                if route in c.url_or_path or c.url_or_path.rstrip("/") in route or obs.callee_service_name in c.url_or_path
            ]
            static_confirmed = len(matching_static) > 0
            if static_confirmed:
                for ms in matching_static:
                    matched_static_keys.add(f"{ms.file_path}:{ms.start_line}")

            # Check OpenAPI alignment
            ep_key = f"{method} {route}"
            openapi_matched = ep_key in openapi_set or route in openapi_paths

            # Check AsyncAPI alignment
            asyncapi_matched = (
                obs.messaging_destination in asyncapi_dests
                if obs.protocol == ProtocolType.MESSAGING and obs.messaging_destination
                else False
            )

            status = (
                CorrelationStatus.OBSERVED_AND_STATIC_CONFIRMED
                if static_confirmed
                else CorrelationStatus.RUNTIME_ONLY
            )
            confidence = 1.0 if (static_confirmed and (openapi_matched or asyncapi_matched)) else (0.95 if static_confirmed else 0.90)

            exemplar_call = matching_static[0] if matching_static else None

            results.append(
                CorrelatedDependency(
                    caller_service=obs.caller_service_name,
                    callee_service=obs.callee_service_name,
                    route_or_channel=route,
                    correlation_status=status,
                    runtime_observed=True,
                    static_confirmed=static_confirmed,
                    openapi_matched=openapi_matched,
                    asyncapi_matched=asyncapi_matched,
                    confidence=confidence,
                    runtime_call_count=obs.call_count,
                    runtime_p95_latency_ms=obs.p95_latency_ms,
                    static_file_path=exemplar_call.file_path if exemplar_call else None,
                    static_line_number=exemplar_call.start_line if exemplar_call else None,
                    notes=(
                        "Confirmed in both static AST and live telemetry."
                        if status == CorrelationStatus.OBSERVED_AND_STATIC_CONFIRMED
                        else "Observed at runtime but static client invocation not matched in repository AST."
                    ),
                )
            )

        # 2. Process Static-Only Calls (Unexercised in sample window)
        # Invariant: Runtime absence is evidence of observed behavior, not proof that dependency cannot exist
        for sc in static_calls:
            key = f"{sc.file_path}:{sc.start_line}"
            if key not in matched_static_keys:
                matched_static_keys.add(key)
                ep_match = any(sc.url_or_path.endswith(p) for p in openapi_paths)
                results.append(
                    CorrelatedDependency(
                        caller_service="inferred_caller",
                        callee_service=cls._extract_callee_from_url(sc.url_or_path),
                        route_or_channel=sc.url_or_path,
                        correlation_status=CorrelationStatus.STATIC_ONLY,
                        runtime_observed=False,
                        static_confirmed=True,
                        openapi_matched=ep_match,
                        asyncapi_matched=False,
                        confidence=0.85,
                        runtime_call_count=0,
                        runtime_p95_latency_ms=0.0,
                        static_file_path=sc.file_path,
                        static_line_number=sc.start_line,
                        notes="Declared in static source AST but no runtime traffic observed during sample window.",
                    )
                )

        return results

    @classmethod
    def generate_ontology_candidates(
        cls,
        observed_dependencies: list[ObservedServiceDependency],
        tenant_id: str,
    ) -> list[OntologyCandidate]:
        """Converts observed runtime dependencies into OntologyCandidate records."""
        candidates: list[OntologyCandidate] = []

        for obs in observed_dependencies:
            evidence_str = "; ".join(obs.evidence_citations) if obs.evidence_citations else f"Trace {obs.exemplar_trace_id}"
            rel_type = (
                RelationshipType.READS.value
                if obs.protocol == ProtocolType.DATABASE
                else (
                    RelationshipType.PUBLISHES.value
                    if obs.protocol == ProtocolType.MESSAGING
                    else RelationshipType.CALLS.value
                )
            )
            candidates.append(
                OntologyCandidate(
                    tenant_id=tenant_id,
                    source_scanner="OTEL",
                    candidate_type="RELATIONSHIP",
                    confidence=1.0 if obs.call_count >= 10 else 0.90,
                    evidence_refs=[evidence_str],
                    review_status=CandidateReviewStatus.CANDIDATE.value,
                    proposed_payload={
                        "source": obs.caller_service_name,
                        "target": obs.callee_service_name,
                        "domain_entity_type": CoreEntityType.SERVICE.value,
                        "range_entity_type": (
                            CoreEntityType.DATABASE.value
                            if obs.protocol == ProtocolType.DATABASE
                            else CoreEntityType.SERVICE.value
                        ),
                        "relationship_type": rel_type,
                        "protocol": obs.protocol.value if hasattr(obs.protocol, "value") else str(obs.protocol),
                        "route": obs.operation_or_route,
                        "method": obs.http_method,
                        "call_count": obs.call_count,
                        "p95_latency_ms": obs.p95_latency_ms,
                        "exemplar_trace_id": obs.exemplar_trace_id,
                        "environment": obs.environment,
                        "provenance": ProvenanceType.RUNTIME_OBSERVED.value,
                    },
                )
            )

        return candidates

    @classmethod
    def _extract_callee_from_url(cls, url: str) -> str:
        """Heuristic callee name extraction from URL (e.g. 'http://payment-service/api' -> 'payment-service')."""
        if "://" in url:
            host = url.split("://", 1)[1].split("/", 1)[0].split(":")[0]
            return host.replace(".internal", "")
        return "external_service"
