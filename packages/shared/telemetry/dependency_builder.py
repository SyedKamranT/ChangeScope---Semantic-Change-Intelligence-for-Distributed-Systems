"""Runtime Service Graph and Dependency Aggregation Builder."""

import statistics
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from packages.shared.telemetry.models import (
    NormalizedSpan,
    ObservedServiceDependency,
    ProtocolType,
    RuntimeServiceGraph,
    SpanKind,
)


class DependencyBuilder:
    """Discovers inter-service, database, and messaging dependencies from normalized trace spans."""

    @classmethod
    def build_service_graph(
        cls,
        spans: list[NormalizedSpan],
        tenant_id: str,
        environment: str = "production",
    ) -> RuntimeServiceGraph:
        """Constructs a complete RuntimeServiceGraph from a collection of spans."""
        dependencies = cls.extract_dependencies(spans, environment=environment)
        all_services = sorted(
            {s.service_name for s in spans if s.service_name and s.service_name != "unknown_service"}
            | {d.caller_service_name for d in dependencies}
            | {d.callee_service_name for d in dependencies if d.protocol not in {ProtocolType.DATABASE}}
        )

        return RuntimeServiceGraph(
            tenant_id=tenant_id,
            environment=environment,
            services=all_services,
            dependencies=dependencies,
            total_spans_processed=len(spans),
            generated_at=datetime.now(UTC),
        )

    @classmethod
    def extract_dependencies(
        cls,
        spans: list[NormalizedSpan],
        environment: str = "production",
    ) -> list[ObservedServiceDependency]:
        """Analyzes trace spans and aggregates observed dependency relationships."""
        # 1. Index spans by trace_id and span_id
        traces: dict[str, list[NormalizedSpan]] = defaultdict(list)
        for s in spans:
            traces[s.trace_id].append(s)

        # Dependency aggregation accumulator: key -> list of (duration_ms, is_error, trace_id, span_id, timestamp)
        # Key: (caller, callee, protocol, route_or_op, method, dest, db_sys, db_name, env)
        dep_metrics: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)

        for trace_id, trace_spans in traces.items():
            span_map = {s.span_id: s for s in trace_spans}

            for s in trace_spans:
                # -------------------------------------------------------------
                # Case 1: Direct Parent-Child RPC / HTTP Service-to-Service
                # -------------------------------------------------------------
                if s.parent_span_id and s.parent_span_id in span_map:
                    parent = span_map[s.parent_span_id]

                    # Condition A: Client span in Service A calling Server span in Service B
                    if (
                        parent.service_name != s.service_name
                        and parent.service_name != "unknown_service"
                        and s.service_name != "unknown_service"
                    ):
                        caller = parent.service_name
                        callee = s.service_name
                        protocol = ProtocolType.GRPC if (s.rpc_system or parent.rpc_system) else ProtocolType.HTTP
                        route = s.http_route or parent.http_route or s.rpc_method or s.name
                        method = s.http_method or parent.http_method or "ANY"

                        parent_key: tuple[Any, ...] = (
                            caller,
                            callee,
                            protocol,
                            route,
                            method,
                            None,
                            None,
                            None,
                            environment,
                        )
                        dep_metrics[parent_key].append(
                            {
                                "duration_ms": max(s.duration_ms, parent.duration_ms),
                                "is_error": s.status_code == "ERROR" or (s.http_status_code or 200) >= 400,
                                "trace_id": trace_id,
                                "span_id": s.span_id,
                                "time": s.observed_at,
                            }
                        )

                # -------------------------------------------------------------
                # Case 2: Outbound Client Span with peer.service or URL (Sampled Server)
                # -------------------------------------------------------------
                elif s.kind == SpanKind.CLIENT and s.peer_service:
                    caller = s.service_name
                    callee = s.peer_service
                    if caller != callee and caller != "unknown_service":
                        protocol = ProtocolType.GRPC if s.rpc_system else ProtocolType.HTTP
                        route = s.http_route or s.rpc_method or s.name
                        method = s.http_method or "ANY"

                        client_key: tuple[Any, ...] = (
                            caller,
                            callee,
                            protocol,
                            route,
                            method,
                            None,
                            None,
                            None,
                            environment,
                        )
                        dep_metrics[client_key].append(
                            {
                                "duration_ms": s.duration_ms,
                                "is_error": s.status_code == "ERROR" or (s.http_status_code or 200) >= 400,
                                "trace_id": trace_id,
                                "span_id": s.span_id,
                                "time": s.observed_at,
                            }
                        )

                # -------------------------------------------------------------
                # Case 3: Database Spans
                # -------------------------------------------------------------
                if s.db_system and s.service_name != "unknown_service":
                    caller = s.service_name
                    db_target = s.db_name or s.db_system
                    callee = f"db:{db_target}"
                    protocol = ProtocolType.DATABASE
                    op = s.db_operation or s.name

                    db_key: tuple[Any, ...] = (
                        caller,
                        callee,
                        protocol,
                        op,
                        None,
                        None,
                        s.db_system,
                        s.db_name,
                        environment,
                    )
                    dep_metrics[db_key].append(
                        {
                            "duration_ms": s.duration_ms,
                            "is_error": s.status_code == "ERROR",
                            "trace_id": trace_id,
                            "span_id": s.span_id,
                            "time": s.observed_at,
                        }
                    )

            # -----------------------------------------------------------------
            # Case 4: Messaging Producer -> Consumer in same trace
            # -----------------------------------------------------------------
            producers = [s for s in trace_spans if s.kind == SpanKind.PRODUCER and s.messaging_destination]
            consumers = [s for s in trace_spans if s.kind == SpanKind.CONSUMER and s.messaging_destination]
            for prod in producers:
                for cons in consumers:
                    if (
                        prod.service_name != cons.service_name
                        and prod.messaging_destination == cons.messaging_destination
                    ):
                        dest = prod.messaging_destination
                        msg_key: tuple[Any, ...] = (
                            prod.service_name,
                            cons.service_name,
                            ProtocolType.MESSAGING,
                            dest,
                            None,
                            dest,
                            None,
                            None,
                            environment,
                        )
                        dep_metrics[msg_key].append(
                            {
                                "duration_ms": max(prod.duration_ms, cons.duration_ms),
                                "is_error": cons.status_code == "ERROR",
                                "trace_id": trace_id,
                                "span_id": cons.span_id,
                                "time": cons.observed_at,
                            }
                        )

        # 2. Build final ObservedServiceDependency records
        results: list[ObservedServiceDependency] = []
        for key, observations in dep_metrics.items():
            caller, callee, protocol, route_or_op, method, dest, db_sys, db_name, env = key
            durations = [o["duration_ms"] for o in observations]
            errors = sum(1 for o in observations if o["is_error"])
            call_count = len(observations)

            # Compute p95 latency
            if len(durations) >= 20:
                p95 = float(statistics.quantiles(durations, n=100)[94])
            elif durations:
                p95 = float(max(durations))
            else:
                p95 = 0.0

            first_obs = min(o["time"] for o in observations)
            last_obs = max(o["time"] for o in observations)
            exemplar = observations[0]

            results.append(
                ObservedServiceDependency(
                    caller_service_name=caller,
                    callee_service_name=callee,
                    protocol=protocol,
                    operation_or_route=route_or_op or "/",
                    http_method=method,
                    messaging_destination=dest,
                    db_system=db_sys,
                    db_name=db_name,
                    environment=env,
                    call_count=call_count,
                    error_count=errors,
                    p95_latency_ms=round(p95, 2),
                    first_observed_at=first_obs,
                    last_observed_at=last_obs,
                    exemplar_trace_id=exemplar["trace_id"],
                    exemplar_span_id=exemplar["span_id"],
                    is_sampled=True,
                    sample_rate=1.0,
                    evidence_citations=[
                        f"Trace {exemplar['trace_id']}:{exemplar['span_id']} observed {call_count} calls ({errors} errors, p95={round(p95, 2)}ms)"
                    ],
                )
            )

        return sorted(results, key=lambda d: (d.caller_service_name, d.callee_service_name, d.operation_or_route))
