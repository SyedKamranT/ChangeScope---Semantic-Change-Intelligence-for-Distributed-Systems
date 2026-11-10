#!/usr/bin/env python3
"""
ChangeScope End-to-End Pipeline Demonstration Script.

Runs the complete change intelligence lifecycle:
1. Static AST extraction (Python & TypeScript)
2. Contract & Schema dereferencing
3. SQL DDL Migration parsing
4. Deterministic Semantic Rule Evaluation
5. Multi-Hop Blast Radius Calculation
6. Grounded Report Synthesis with Citation Verification Guard
7. Check Run Annotation Generation
"""

import asyncio
import sys
from pathlib import Path

# Ensure backend directory is in sys.path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from changescope.analysis.contract.ddl_parser import DDLParser
from changescope.analysis.contract.openapi_parser import OpenAPIParser
from changescope.analysis.static.python_parser import PythonASTParser
from changescope.analysis.static.typescript_parser import TypeScriptASTParser
from changescope.impact.blast_radius import BlastRadiusCalculator, ImpactedConsumer
from changescope.reasoning.models import ConsumerContractProfile
from changescope.reasoning.rule_engine import SemanticRuleEngine
from changescope.reporting.github_publisher import GitHubPublisher
from changescope.reporting.langgraph_explainer import LangGraphGroundedExplainer


async def run_demonstration():
    print("=" * 80)
    print("CHANGESCOPE: SEMANTIC CHANGE INTELLIGENCE PLATFORM DEMO")
    print("=" * 80)

    fixtures_dir = Path(__file__).parent / "tests" / "fixtures" / "sample_repos"
    inv_py = fixtures_dir / "inventory_service" / "src" / "main.py"
    inv_oas = fixtures_dir / "inventory_service" / "openapi.yaml"
    inv_sql = fixtures_dir / "inventory_service" / "migrations" / "v2_shrink_sku.sql"
    chk_ts = fixtures_dir / "checkout_service" / "src" / "client.ts"

    # Step 1: Static Code AST Extraction
    print("\n[Step 1/6] Ingesting Codebases & Extracting AST Symbols via Tree-sitter...")
    py_parser = PythonASTParser()
    py_result = py_parser.parse_source(inv_py.read_text(encoding="utf-8"), file_path=str(inv_py))
    print(
        f"  • inventory-service: Extracted {len(py_result['routes'])} routes, {len(py_result['client_calls'])} client calls"
    )
    for r in py_result["routes"]:
        print(
            f"    - Route: {r.method} {r.path_template} (Handler: {r.handler_name}, Lines: L{r.start_line}-L{r.end_line})"
        )

    ts_parser = TypeScriptASTParser()
    ts_result = ts_parser.parse_source(chk_ts.read_text(encoding="utf-8"), file_path=str(chk_ts))
    print(f"  • checkout-service: Extracted {len(ts_result['client_calls'])} outbound client calls")
    for c in ts_result["client_calls"]:
        print(f"    - Client Call: {c.method} {c.url_or_path} (Library: {c.client_library}, Line: L{c.start_line})")

    # Step 2: Contract Dereferencing & DDL Parsing
    print("\n[Step 2/6] Ingesting OpenAPI Specs & Database Migrations...")
    dereferenced_oas = OpenAPIParser.parse_spec(inv_oas.read_text(encoding="utf-8"))
    canonical_endpoints = OpenAPIParser.extract_canonical_endpoints(dereferenced_oas)
    print(f"  • Ingested OpenAPI Spec: {len(canonical_endpoints)} canonical endpoints resolved")

    ddl_events = DDLParser.parse_sql(inv_sql.read_text(encoding="utf-8"))
    print(f"  • Parsed SQL DDL Migration: {len(ddl_events)} schema alteration events")
    for ddl in ddl_events:
        print(f"    - DDL Operation: {ddl.operation} on table '{ddl.table_name}', column '{ddl.column_name}'")

    # Step 3: Deterministic Semantic Rule Engine
    print("\n[Step 3/6] Running Deterministic Semantic Rule Engine...")
    base_endpoint = {
        "request_schema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string"},
                "sku": {"type": "string"},
                "status": {"type": "string", "enum": ["PENDING", "AVAILABLE", "DISCONTINUED"]},
            },
        }
    }
    head_endpoint = canonical_endpoints[0]

    # Consumer enforces closed world
    consumers = [
        ConsumerContractProfile(
            service_id="srv-checkout",
            service_name="checkout-service",
            validation_mode="CLOSED_WORLD",
            additional_properties_allowed=False,
            known_properties={"item_id", "sku", "status"},
        )
    ]

    violations = SemanticRuleEngine.evaluate_contract_diff(
        base_endpoint=base_endpoint,
        head_endpoint=head_endpoint,
        consumers=consumers,
        file_path="openapi.yaml",
        line_range=(15, 30),
    )

    print(f"  • Detected {len(violations)} Breaking Semantic Violations:")
    for v in violations:
        print(f"    - [{v.severity}] {v.rule_code}: {v.message}")

    # Step 4: Multi-Hop Blast Radius Calculation
    print("\n[Step 4/6] Computing Multi-Hop Blast Radius & Operational Risk Score in Neo4j...")
    mock_impacted = [
        ImpactedConsumer(
            service_id="srv-checkout",
            service_name="checkout-service",
            service_tier="TIER_1",
            hop_distance=1,
            path_confidence=0.95,
            is_observed=True,
            rpm=12500,
        ),
        ImpactedConsumer(
            service_id="srv-billing",
            service_name="billing-ledger",
            service_tier="TIER_1",
            hop_distance=2,
            path_confidence=0.90,
            is_observed=True,
            rpm=8900,
        ),
    ]

    blast_radius = await BlastRadiusCalculator.compute_blast_radius(
        tenant_id="tenant-demo",
        endpoint_id="/api/v1/items:POST",
        max_severity="BLOCKING",
        mock_impacted=mock_impacted,
    )

    print(f"  • Calculated Risk Score: {blast_radius.risk_score}/100 ({blast_radius.risk_level})")
    print(
        f"  • Direct Consumers: {blast_radius.direct_consumers_count}, Transitive: {blast_radius.transitive_consumers_count}"
    )
    for c in blast_radius.impacted_consumers:
        print(f"    - {c.service_name} ({c.service_tier}) | Distance: {c.hop_distance} hop(s) | Traffic: {c.rpm:,} RPM")

    # Step 5: Grounded Explanation & Citation Verification
    print("\n[Step 5/6] Synthesizing Grounded Explanation with LangGraph Guard...")
    verified_files = {str(inv_py), str(chk_ts), "openapi.yaml"}
    verified_traces = {"trace-span-4bf92f3577b34da6a3ce929d0e0e4736"}

    report = LangGraphGroundedExplainer.generate_explanation(
        scan_id="scan-demo-001",
        repo_name="inventory-service",
        blast_radius=blast_radius,
        violations=violations,
        verified_file_paths=verified_files,
        verified_trace_ids=verified_traces,
    )

    print(f"  • Citation Verification Audit: {'PASSED' if report['citation_audit_passed'] else 'REJECTED'}")
    print(f"  • Recommended Regression Tests: {len(report['recommended_tests'])} commands generated")
    for cmd in report["recommended_tests"]:
        print(f"    $ {cmd}")

    # Step 6: GitHub Check Run Simulation
    print("\n[Step 6/6] Generating GitHub Checks API Annotations...")
    check_run = await GitHubPublisher.publish_check_run(
        repo_owner_name="acme/inventory-service",
        head_sha="7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b",
        risk_score=blast_radius.risk_score,
        risk_level=blast_radius.risk_level,
        violations=violations,
        markdown_report=report["markdown_report"],
        github_token=None,
    )
    print(f"  • Check Run Conclusion: {check_run['conclusion'].upper()}")
    print(f"  • Annotations Ready for PR: {check_run['annotations_published']}")

    print("\n" + "=" * 80)
    print("DEMONSTRATION RUN COMPLETE: 100% SUCCESS")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_demonstration())
