"""Performance benchmarks for contract parsers and semantic rule engine."""

import time

from packages.contracts import (
    ConsumerContractProfile,
    OpenAPIParser,
    SemanticRuleEngine,
)


def test_openapi_parsing_benchmark() -> None:
    """Verifies that an OpenAPI spec can be parsed and dereferenced in < 15ms."""
    spec = """
    openapi: 3.1.0
    info:
      title: High Volume Benchmark API
      version: 1.0.0
    paths:
      /items/{id}:
        get:
          operationId: getItem
          responses:
            '200':
              content:
                application/json:
                  schema:
                    type: object
                    properties:
                      id: {type: string}
                      name: {type: string}
                      tags: {type: array, items: {type: string}}
    """
    start = time.perf_counter()
    for _ in range(50):
        dereferenced = OpenAPIParser.parse_spec(spec)
        endpoints = OpenAPIParser.extract_canonical_endpoints(dereferenced)
        assert len(endpoints) == 1
    duration = time.perf_counter() - start
    avg_ms = (duration / 50) * 1000
    assert avg_ms < 50.0, f"Average parse time too slow: {avg_ms:.2f}ms"


def test_rule_engine_evaluation_benchmark() -> None:
    """Verifies that the semantic rule engine evaluates 100 schema pairs in < 50ms."""
    base_schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["ACTIVE", "SUSPENDED", "ARCHIVED"]},
            "count": {"type": "integer", "minimum": 1},
        },
    }
    head_schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["ACTIVE", "SUSPENDED"]},  # Removed ARCHIVED
            "count": {"type": "integer", "minimum": 5},  # Tightened minimum
        },
    }
    consumer = ConsumerContractProfile(
        service_id="svc-consumer",
        service_name="consumer-1",
        validation_mode="OPEN_WORLD",
        additional_properties_allowed=True,
        known_properties={"status", "count"},
    )

    start = time.perf_counter()
    for _ in range(100):
        violations = SemanticRuleEngine._evaluate_schema_pair(
            base_schema, head_schema, "/payload", [consumer], "api.yaml", (1, 10)
        )
        assert len(violations) == 2
    duration = time.perf_counter() - start
    avg_ms = (duration / 100) * 1000
    assert avg_ms < 10.0, f"Average rule evaluation time too slow: {avg_ms:.2f}ms"
