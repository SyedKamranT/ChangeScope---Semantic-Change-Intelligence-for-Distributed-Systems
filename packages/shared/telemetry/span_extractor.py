"""OpenTelemetry Trace & Span Normalization Extractor."""

from typing import Any

from packages.shared.telemetry.models import NormalizedSpan, SpanKind
from packages.shared.telemetry.pii_scrubber import PIIScrubber


class SpanExtractor:
    """Normalizes raw OTLP resourceSpans payload into typed, sanitized NormalizedSpan objects."""

    KIND_MAP: dict[Any, SpanKind] = {
        1: SpanKind.INTERNAL,
        "SPAN_KIND_INTERNAL": SpanKind.INTERNAL,
        "INTERNAL": SpanKind.INTERNAL,
        2: SpanKind.SERVER,
        "SPAN_KIND_SERVER": SpanKind.SERVER,
        "SERVER": SpanKind.SERVER,
        3: SpanKind.CLIENT,
        "SPAN_KIND_CLIENT": SpanKind.CLIENT,
        "CLIENT": SpanKind.CLIENT,
        4: SpanKind.PRODUCER,
        "SPAN_KIND_PRODUCER": SpanKind.PRODUCER,
        "PRODUCER": SpanKind.PRODUCER,
        5: SpanKind.CONSUMER,
        "SPAN_KIND_CONSUMER": SpanKind.CONSUMER,
        "CONSUMER": SpanKind.CONSUMER,
    }

    @classmethod
    def extract_spans(cls, otlp_payload: dict[str, Any]) -> list[NormalizedSpan]:
        """Extracts and sanitizes all spans from an OTLP resourceSpans JSON structure."""
        normalized: list[NormalizedSpan] = []
        resource_spans = otlp_payload.get("resourceSpans", [])
        if not isinstance(resource_spans, list):
            return []

        for rs in resource_spans:
            if not isinstance(rs, dict):
                continue

            # Extract resource-level attributes
            resource = rs.get("resource", {})
            res_attrs = cls._parse_attributes(resource.get("attributes", {}))
            service_name = str(res_attrs.get("service.name") or "unknown_service")
            env = str(res_attrs.get("deployment.environment") or res_attrs.get("environment") or "production")
            sdk = str(res_attrs.get("telemetry.sdk.name") or "")

            scope_spans = rs.get("scopeSpans", [])
            for ss in scope_spans:
                if not isinstance(ss, dict):
                    continue

                spans = ss.get("spans", [])
                for span_data in spans:
                    if not isinstance(span_data, dict):
                        continue

                    span = cls._normalize_single_span(span_data, service_name, env, sdk)
                    if span:
                        normalized.append(span)

        return normalized

    @classmethod
    def _normalize_single_span(
        cls, span: dict[str, Any], default_service: str, default_env: str, sdk: str
    ) -> NormalizedSpan | None:
        """Parses a single OTLP span dictionary into a NormalizedSpan."""
        trace_id = str(span.get("traceId") or "")
        span_id = str(span.get("spanId") or "")
        if not trace_id or not span_id:
            return None

        parent_span_id = span.get("parentSpanId")
        if parent_span_id:
            parent_span_id = str(parent_span_id)
            if parent_span_id in {"0", "", "0000000000000000"}:
                parent_span_id = None

        name = str(span.get("name") or "unnamed_operation")
        raw_kind = span.get("kind", 1)
        kind = cls.KIND_MAP.get(raw_kind, SpanKind.INTERNAL)

        # Parse and sanitize attributes
        raw_attrs = cls._parse_attributes(span.get("attributes", {}))
        clean_attrs = PIIScrubber.scrub_attributes(raw_attrs)

        # Status code
        status_dict = span.get("status", {})
        status_code = "UNSET"
        if isinstance(status_dict, dict):
            raw_code = status_dict.get("code")
            if raw_code in {1, "STATUS_CODE_OK", "OK"}:
                status_code = "OK"
            elif raw_code in {2, "STATUS_CODE_ERROR", "ERROR"}:
                status_code = "ERROR"

        # Duration
        start_nano = int(span.get("startTimeUnixNano") or 0)
        end_nano = int(span.get("endTimeUnixNano") or 0)
        duration_ms = max(0.0, (end_nano - start_nano) / 1_000_000.0) if end_nano > start_nano else 0.0

        # Protocol & HTTP extraction
        http_method = clean_attrs.get("http.method") or clean_attrs.get("http.request.method")
        http_route = (
            clean_attrs.get("http.route")
            or clean_attrs.get("http.target")
            or clean_attrs.get("url.path")
            or cls._extract_route_from_name(name)
        )
        http_url = clean_attrs.get("http.url") or clean_attrs.get("url.full")
        http_status = clean_attrs.get("http.status_code") or clean_attrs.get("http.response.status_code")
        if http_status is not None:
            try:
                http_status = int(http_status)
            except (ValueError, TypeError):
                http_status = None

        # RPC extraction
        rpc_system = clean_attrs.get("rpc.system")
        rpc_service = clean_attrs.get("rpc.service")
        rpc_method = clean_attrs.get("rpc.method")

        # Messaging extraction
        messaging_system = clean_attrs.get("messaging.system")
        messaging_destination = clean_attrs.get("messaging.destination") or clean_attrs.get(
            "messaging.destination.name"
        )
        messaging_operation = clean_attrs.get("messaging.operation")

        # Database extraction
        db_system = clean_attrs.get("db.system")
        db_name = clean_attrs.get("db.name") or clean_attrs.get("db.namespace")
        db_statement = clean_attrs.get("db.statement") or clean_attrs.get("sql.query")
        db_operation = clean_attrs.get("db.operation")

        # Peer service overrides
        peer_service = (
            clean_attrs.get("peer.service") or clean_attrs.get("net.peer.name") or clean_attrs.get("server.address")
        )

        return NormalizedSpan(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            service_name=clean_attrs.get("service.name") or default_service,
            name=name,
            kind=kind,
            status_code=status_code,
            start_time_unix_nano=start_nano,
            end_time_unix_nano=end_nano,
            duration_ms=duration_ms,
            http_method=str(http_method).upper() if http_method else None,
            http_route=str(http_route) if http_route else None,
            http_url=str(http_url) if http_url else None,
            http_status_code=http_status,
            rpc_system=str(rpc_system) if rpc_system else None,
            rpc_service=str(rpc_service) if rpc_service else None,
            rpc_method=str(rpc_method) if rpc_method else None,
            messaging_system=str(messaging_system) if messaging_system else None,
            messaging_destination=str(messaging_destination) if messaging_destination else None,
            messaging_operation=str(messaging_operation) if messaging_operation else None,
            db_system=str(db_system) if db_system else None,
            db_name=str(db_name) if db_name else None,
            db_statement=str(db_statement) if db_statement else None,
            db_operation=str(db_operation) if db_operation else None,
            environment=str(clean_attrs.get("deployment.environment") or default_env),
            peer_service=str(peer_service) if peer_service else None,
            telemetry_sdk=sdk,
            attributes=clean_attrs,
        )

    @classmethod
    def _parse_attributes(cls, attrs: Any) -> dict[str, Any]:
        """Supports both standard OTLP list format and key-value dictionary format."""
        if isinstance(attrs, dict):
            return dict(attrs)
        elif isinstance(attrs, list):
            result: dict[str, Any] = {}
            for item in attrs:
                if isinstance(item, dict) and "key" in item:
                    k = item["key"]
                    v_wrapper = item.get("value")
                    val = cls._unpack_otlp_value(v_wrapper)
                    result[k] = val
            return result
        return {}

    @classmethod
    def _unpack_otlp_value(cls, v: Any) -> Any:
        """Unpacks OTLP AnyValue format (e.g. {'stringValue': 'foo'})."""
        if isinstance(v, dict):
            for val_type in ["stringValue", "intValue", "doubleValue", "boolValue"]:
                if val_type in v:
                    return v[val_type]
            if "arrayValue" in v:
                vals = v["arrayValue"].get("values", [])
                return [cls._unpack_otlp_value(item) for item in vals]
            if "kvlistValue" in v:
                kvs = v["kvlistValue"].get("values", [])
                return {item.get("key"): cls._unpack_otlp_value(item.get("value")) for item in kvs if "key" in item}
        return v

    @classmethod
    def _extract_route_from_name(cls, name: str) -> str | None:
        """Heuristic route extraction from span name if http.route is omitted (e.g. 'HTTP GET /orders')."""
        parts = name.split()
        if len(parts) >= 2 and parts[0].upper() in {"GET", "POST", "PUT", "DELETE", "PATCH", "HTTP"}:
            for part in parts:
                if part.startswith("/"):
                    return part
        return None
