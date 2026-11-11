"""Automated Remediation Test Generation Engine grounded in verified AST, schema, and trace evidence."""

import uuid

from packages.contracts.models import ContractFinding
from packages.shared.impact.models import ImpactedEntity, ImpactPath
from packages.shared.remediation.models import (
    AffectedIntegrationTest,
    ContractTestUpdate,
    TestRecommendation,
    TestType,
)


class RemediationTestGenerator:
    """Synthesizes evidence-backed regression, integration, and contract tests for impacted services."""

    @classmethod
    def generate_regression_tests(
        cls,
        findings: list[ContractFinding],
        impacted_entities: list[ImpactedEntity],
        impact_paths: list[ImpactPath],
    ) -> list[TestRecommendation]:
        """Generates concrete regression tests grounded in changed schemas, AST calls, and impact paths."""
        recommendations: list[TestRecommendation] = []
        path_by_target = {p.target_entity: p for p in impact_paths}

        for finding in findings:
            cat = (
                finding.change_category.value
                if hasattr(finding.change_category, "value")
                else str(finding.change_category)
            )
            c_type = finding.change_type.upper()
            target_service = finding.affected_entities[0] if finding.affected_entities else "api-service"

            # Correlate with downstream consumer if available
            matching_consumer = next(
                (e for e in impacted_entities if e.entity_id != target_service),
                None,
            )
            caller_service = matching_consumer.entity_name if matching_consumer else "consumer-client"
            path_obj = path_by_target.get(matching_consumer.entity_id) if matching_consumer else None
            evidence_refs = list(
                set(
                    [f"{finding.file_path}#L{finding.start_line}-L{finding.end_line}"]
                    + (path_obj.evidence_references if path_obj else [])
                )
            )

            # Scenario 1: Field Removal or Renaming
            if "FIELD_REMOVED" in c_type or "REMOVED" in c_type:
                field_name = finding.supporting_evidence.get("field_name", "removed_field")
                endpoint = finding.supporting_evidence.get("endpoint", "/api/v1/resource")
                method = finding.supporting_evidence.get("http_method", "POST")

                rec = TestRecommendation(
                    test_id=f"test-reg-{uuid.uuid4().hex[:8]}",
                    test_type=TestType.REGRESSION,
                    test_objective=f"Verify consumer resilience when legacy field '{field_name}' is omitted by {target_service}",
                    preconditions=[
                        f"Deploy {target_service} with updated schema (commit under test)",
                        f"Ensure {caller_service} has test fixtures initialized",
                    ],
                    test_inputs={
                        "endpoint": endpoint,
                        "method": method,
                        "payload_without_field": {k: v for k, v in finding.after_state.items() if k != field_name},
                        "legacy_payload": finding.before_state,
                    },
                    expected_behavior=(
                        f"{target_service} must return 200/201 without throwing KeyError or 500 when '{field_name}' "
                        f"is absent, and {caller_service} must gracefully handle default fallback."
                    ),
                    affected_service=caller_service,
                    relevant_finding=finding.finding_id,
                    evidence_references=evidence_refs,
                    confidence=finding.confidence,
                    code_snippet=cls._build_pytest_regression_snippet(
                        endpoint=endpoint,
                        method=method,
                        field_name=field_name,
                        service_name=target_service,
                    ),
                )
                recommendations.append(rec)

            # Scenario 2: Enum Narrowing / Value Revocation
            elif "ENUM_NARROWED" in c_type:
                enum_name = finding.supporting_evidence.get("enum_name", "StatusEnum")
                removed_values = finding.supporting_evidence.get("removed_values", ["LEGACY_VALUE"])
                val_str = ", ".join(f"'{v}'" for v in removed_values)

                rec = TestRecommendation(
                    test_id=f"test-reg-{uuid.uuid4().hex[:8]}",
                    test_type=TestType.REGRESSION,
                    test_objective=f"Assert proper 400 Bad Request error handling for revoked enum values {val_str}",
                    preconditions=[f"{target_service} schema validation active"],
                    test_inputs={
                        "invalid_enum_payload": {enum_name: removed_values[0] if removed_values else "OLD_VAL"}
                    },
                    expected_behavior=f"Returns HTTP 400 with Problem Details explaining revoked enum value {val_str}",
                    affected_service=target_service,
                    relevant_finding=finding.finding_id,
                    evidence_references=evidence_refs,
                    confidence=finding.confidence,
                    code_snippet=cls._build_enum_validation_snippet(
                        enum_name, removed_values[0] if removed_values else "OLD_VAL"
                    ),
                )
                recommendations.append(rec)

            # Scenario 3: Type Mutation (e.g. String -> Integer, Unit Shift)
            elif "TYPE_CHANGED" in c_type or "UNIT_SHIFT" in c_type or "SEMANTIC" in cat:
                field_name = finding.supporting_evidence.get("field_name", "amount")
                before_type = finding.supporting_evidence.get("before_type", "string")
                after_type = finding.supporting_evidence.get("after_type", "integer")

                rec = TestRecommendation(
                    test_id=f"test-reg-{uuid.uuid4().hex[:8]}",
                    test_type=TestType.REGRESSION,
                    test_objective=f"Verify boundary deserialization for field '{field_name}' transition from {before_type} to {after_type}",
                    preconditions=[f"Database and API deserializers updated for {target_service}"],
                    test_inputs={"sample_value": 100, "legacy_string_value": "100"},
                    expected_behavior="Validates numeric payload strictly and rejects malformed types with typed RFC7807 error",
                    affected_service=caller_service,
                    relevant_finding=finding.finding_id,
                    evidence_references=evidence_refs,
                    confidence=finding.confidence,
                    code_snippet=cls._build_type_change_snippet(field_name, after_type),
                )
                recommendations.append(rec)

            # Scenario 4: Event Schema Mutation
            elif "EVENT" in cat or "ASYNCAPI" in c_type or "CHANNEL" in c_type:
                topic = finding.supporting_evidence.get("channel", "events.topic")
                rec = TestRecommendation(
                    test_id=f"test-reg-{uuid.uuid4().hex[:8]}",
                    test_type=TestType.REGRESSION,
                    test_objective=f"Verify event consumer processing for topic '{topic}' with evolved schema",
                    preconditions=[f"Consumer subscribed to '{topic}' test harness"],
                    test_inputs={"event_payload": finding.after_state or {"event_id": "evt-test-1"}},
                    expected_behavior="Consumer processes event without dead-lettering or deserialization crash",
                    affected_service=caller_service,
                    relevant_finding=finding.finding_id,
                    evidence_references=evidence_refs,
                    confidence=finding.confidence,
                )
                recommendations.append(rec)

        return recommendations

    @classmethod
    def identify_affected_integration_tests(
        cls,
        impacted_entities: list[ImpactedEntity],
        findings: list[ContractFinding],
        known_test_files: list[str] | None = None,
    ) -> list[AffectedIntegrationTest]:
        """Identifies existing integration test files in the codebase that exercise modified paths."""
        affected_tests: list[AffectedIntegrationTest] = []
        test_files = known_test_files or [
            "tests/integration/test_orders_api.py",
            "tests/integration/test_payment_gateway.py",
            "tests/integration/test_inventory_service.py",
            "tests/e2e/test_checkout_workflow.py",
        ]

        seen: set[tuple[str, str]] = set()
        for ent in impacted_entities:
            s_name = ent.entity_name.lower().replace("-", "_")
            tokens = [p for p in s_name.split("_") if p not in ("service", "svc", "api", "app", "worker")]
            if not tokens:
                tokens = [s_name]

            # Find matching test files based on entity name or service tokens
            for tf in test_files:
                tf_lower = tf.lower()
                matches = s_name in tf_lower or any(tok in tf_lower for tok in tokens if len(tok) >= 3)
                if matches and (tf, ent.entity_name) not in seen:
                    seen.add((tf, ent.entity_name))
                    affected_tests.append(
                        AffectedIntegrationTest(
                            test_file=tf,
                            test_name=f"test_{s_name}_integration_flow",
                            service_name=ent.entity_name,
                            reason=f"Exercises communication path to {ent.entity_name} ({ent.hop_distance} hop(s) downstream)",
                            evidence_reference=f"Impact path: {' -> '.join(ent.path)}",
                        )
                    )

        return affected_tests

    @classmethod
    def suggest_contract_test_updates(
        cls,
        findings: list[ContractFinding],
        impacted_entities: list[ImpactedEntity],
    ) -> list[ContractTestUpdate]:
        """Suggests required contract test assertion updates between providers and consumers."""
        updates: list[ContractTestUpdate] = []

        for finding in findings:
            provider = finding.affected_entities[0] if finding.affected_entities else "provider-service"
            for consumer in [e for e in impacted_entities if e.entity_id != provider]:
                field_name = finding.supporting_evidence.get("field_name", "schema")
                updates.append(
                    ContractTestUpdate(
                        consumer_service=consumer.entity_name,
                        provider_service=provider,
                        contract_file=f"contracts/{consumer.entity_name}-{provider}-pact.json",
                        recommended_assertion=f"expect(response.body).toHaveProperty('{field_name}')",
                        breaking_field=field_name,
                        reason=f"Rule {finding.change_type} detected at {finding.file_path}#L{finding.start_line}",
                    )
                )

        return updates

    @staticmethod
    def _build_pytest_regression_snippet(endpoint: str, method: str, field_name: str, service_name: str) -> str:
        return f"""import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_resilience_to_omitted_{field_name}(client: AsyncClient):
    # Validates that {service_name} responds correctly when '{field_name}' is absent
    payload = {{"id": "test-item-123"}}  # legacy payload omitting '{field_name}'
    response = await client.{method.lower()}("{endpoint}", json=payload)
    assert response.status_code in [200, 201]
    data = response.json()
    assert "error" not in data
"""

    @staticmethod
    def _build_enum_validation_snippet(enum_name: str, invalid_value: str) -> str:
        return f"""import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_rejected_narrowed_enum_{enum_name}(client: AsyncClient):
    payload = {{"{enum_name}": "{invalid_value}"}}
    response = await client.post("/api/v1/resource", json=payload)
    assert response.status_code == 400
    detail = response.json()
    assert "{invalid_value}" in str(detail)
"""

    @staticmethod
    def _build_type_change_snippet(field_name: str, expected_type: str) -> str:
        return f"""import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_strict_type_validation_{field_name}(client: AsyncClient):
    # Expects {expected_type}
    payload = {{"{field_name}": 42 if "{expected_type}" == "integer" else "valid_str"}}
    response = await client.post("/api/v1/resource", json=payload)
    assert response.status_code in [200, 201]
"""
