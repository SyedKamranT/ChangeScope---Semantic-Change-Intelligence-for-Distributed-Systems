"""ChangeScope Contract Intelligence Engine.

Master coordinator combining structural schema diffing, semantic reasoning,
event channel validation, database migration impact, and code-to-contract alignment.
"""

from typing import Any

from packages.contracts.diff.asyncapi_differ import AsyncAPIDiffer
from packages.contracts.diff.ddl_differ import DDLDiffer
from packages.contracts.diff.openapi_differ import OpenAPIDiffer
from packages.contracts.diff.schema_differ import SchemaDiffer
from packages.contracts.models import (
    ChangeCategory,
    ConsumerContractProfile,
    ContractFinding,
    ExtractedClientCall,
    ExtractedORMModel,
    ExtractedRoute,
    FindingSeverity,
)
from packages.contracts.openapi_parser import OpenAPIParser
from packages.contracts.semantic.candidate_interpreter import CandidateSemanticInterpreter
from packages.contracts.semantic.semantic_differ import SemanticDiffer


class ContractIntelligenceEngine:
    """Master Contract Intelligence Engine analyzing structural, semantic, event, and database changes."""

    @classmethod
    def analyze_openapi_diff(
        cls,
        base_spec: str | dict[str, Any],
        head_spec: str | dict[str, Any],
        consumers: list[ConsumerContractProfile] | None = None,
        client_calls: list[ExtractedClientCall] | None = None,
        file_path: str = "openapi.yaml",
    ) -> list[ContractFinding]:
        """Analyzes structural and semantic differences between base and head OpenAPI documents."""
        findings: list[ContractFinding] = []

        # 1. Structural OpenAPI and Schema Diffing
        structural_findings = OpenAPIDiffer.diff_specs(
            base_spec=base_spec,
            head_spec=head_spec,
            consumers=consumers,
            client_calls=client_calls,
            file_path=file_path,
        )
        findings.extend(structural_findings)

        # 2. Semantic Analysis across all endpoints
        base_dict = (
            OpenAPIParser.parse_spec(base_spec)
            if isinstance(base_spec, str)
            else OpenAPIParser._dereference_spec(base_spec)
        )
        head_dict = (
            OpenAPIParser.parse_spec(head_spec)
            if isinstance(head_spec, str)
            else OpenAPIParser._dereference_spec(head_spec)
        )

        base_eps = {
            f"{ep['method']} {ep['path_template']}": ep for ep in OpenAPIParser.extract_canonical_endpoints(base_dict)
        }
        head_eps = {
            f"{ep['method']} {ep['path_template']}": ep for ep in OpenAPIParser.extract_canonical_endpoints(head_dict)
        }

        common_keys = set(base_eps.keys()) & set(head_eps.keys())
        for ep_key in sorted(common_keys):
            b_ep = base_eps[ep_key]
            h_ep = head_eps[ep_key]
            path = b_ep["path_template"]
            method = b_ep["method"]
            op_ptr = f"/paths{path}/{method.lower()}"

            # Check request schema semantics
            findings.extend(
                SemanticDiffer.analyze_schema_semantics(
                    b_ep.get("request_schema"),
                    h_ep.get("request_schema"),
                    pointer_prefix=f"{op_ptr}/requestBody",
                    file_path=file_path,
                )
            )

            # Check response schemas semantics
            b_resps = b_ep.get("response_schemas", {})
            h_resps = h_ep.get("response_schemas", {})
            for sc in sorted(set(b_resps.keys()) & set(h_resps.keys())):
                findings.extend(
                    SemanticDiffer.analyze_schema_semantics(
                        b_resps[sc],
                        h_resps[sc],
                        pointer_prefix=f"{op_ptr}/responses/{sc}",
                        file_path=file_path,
                    )
                )

        # 3. Optional Candidate Interpretation for Modified Descriptions
        cls._augment_candidate_interpretations(base_dict, head_dict, findings, file_path)

        return findings

    @classmethod
    def analyze_asyncapi_diff(
        cls,
        base_spec: str | dict[str, Any],
        head_spec: str | dict[str, Any],
        consumers: list[ConsumerContractProfile] | None = None,
        file_path: str = "asyncapi.yaml",
    ) -> list[ContractFinding]:
        """Analyzes event channels, ordering, delivery, and payload evolution."""
        findings = AsyncAPIDiffer.diff_specs(
            base_spec=base_spec,
            head_spec=head_spec,
            consumers=consumers,
            file_path=file_path,
        )
        return findings

    @classmethod
    def analyze_json_schema_diff(
        cls,
        base_schema: dict[str, Any] | None,
        head_schema: dict[str, Any] | None,
        consumers: list[ConsumerContractProfile] | None = None,
        pointer_prefix: str = "",
        is_response: bool = False,
        file_path: str = "schema.json",
    ) -> list[ContractFinding]:
        """Analyzes structural and semantic differences between two JSON schemas."""
        findings: list[ContractFinding] = []

        # 1. Structural schema diff
        findings.extend(
            SchemaDiffer.diff_schemas(
                base_schema=base_schema,
                head_schema=head_schema,
                pointer_prefix=pointer_prefix,
                consumers=consumers,
                is_response=is_response,
                file_path=file_path,
            )
        )

        # 2. Semantic analysis
        findings.extend(
            SemanticDiffer.analyze_schema_semantics(
                base_schema=base_schema,
                head_schema=head_schema,
                pointer_prefix=pointer_prefix,
                file_path=file_path,
            )
        )

        return findings

    @classmethod
    def analyze_database_diff(
        cls,
        ddl_events: list[Any],
        active_orm_models: list[ExtractedORMModel] | None = None,
        consumer_service_name: str = "service",
    ) -> list[ContractFinding]:
        """Analyzes SQL DDL migration events against active ORM models."""
        return DDLDiffer.diff_ddl_events(
            ddl_events=ddl_events,
            active_orm_models=active_orm_models,
            consumer_service_name=consumer_service_name,
        )

    @classmethod
    def analyze_code_contract_alignment(
        cls,
        extracted_routes: list[ExtractedRoute],
        openapi_endpoints: list[dict[str, Any]],
        client_calls: list[ExtractedClientCall] | None = None,
    ) -> list[ContractFinding]:
        """Verifies parity between extracted codebase AST routes/clients and declared contracts."""
        findings: list[ContractFinding] = []
        contract_endpoints = {f"{ep['method']} {ep['path_template']}" for ep in openapi_endpoints}
        code_routes = {f"{r.method} {r.path_template}": r for r in extracted_routes}

        # Code routes missing from contract (uncontracted endpoints)
        for r_key, route in code_routes.items():
            if r_key not in contract_endpoints:
                findings.append(
                    ContractFinding(
                        change_category=ChangeCategory.STRUCTURAL,
                        change_type="UNCONTRACTED_ENDPOINT",
                        severity=FindingSeverity.WARNING,
                        confidence=0.90,
                        before_state={},
                        after_state={"route": r_key, "handler": route.handler_name},
                        affected_entities=[r_key],
                        supporting_evidence={"route": r_key, "file": route.file_path, "line": route.start_line},
                        recommended_verification=f"Endpoint '{r_key}' is implemented in code ({route.file_path}:{route.start_line}) but missing from OpenAPI contract.",
                        file_path=route.file_path,
                        start_line=route.start_line,
                        end_line=route.end_line,
                    )
                )

        # Contract endpoints missing from code (declared but unimplemented)
        for ep_key in contract_endpoints:
            if ep_key not in code_routes:
                findings.append(
                    ContractFinding(
                        change_category=ChangeCategory.STRUCTURAL,
                        change_type="UNIMPLEMENTED_CONTRACT_ENDPOINT",
                        severity=FindingSeverity.WARNING,
                        confidence=0.85,
                        before_state={"endpoint": ep_key},
                        after_state={},
                        affected_entities=[ep_key],
                        supporting_evidence={"endpoint": ep_key},
                        recommended_verification=f"Endpoint '{ep_key}' is declared in contract but no matching code handler was detected.",
                    )
                )

        return findings

    @classmethod
    def _augment_candidate_interpretations(
        cls,
        base_dict: dict[str, Any],
        head_dict: dict[str, Any],
        findings: list[ContractFinding],
        file_path: str,
    ) -> None:
        """Applies candidate interpreter to schema description differences."""
        base_schemas = base_dict.get("components", {}).get("schemas", {})
        head_schemas = head_dict.get("components", {}).get("schemas", {})

        for s_name in set(base_schemas.keys()) & set(head_schemas.keys()):
            b_s = base_schemas[s_name]
            h_s = head_schemas[s_name]
            if isinstance(b_s, dict) and isinstance(h_s, dict):
                b_props = b_s.get("properties", {})
                h_props = h_s.get("properties", {})
                for p_name in set(b_props.keys()) & set(h_props.keys()):
                    b_p = b_props[p_name]
                    h_p = h_props[p_name]
                    if isinstance(b_p, dict) and isinstance(h_p, dict):
                        b_desc = str(b_p.get("description", ""))
                        h_desc = str(h_p.get("description", ""))
                        if b_desc != h_desc:
                            candidates = CandidateSemanticInterpreter.interpret_description_diff(
                                field_name=p_name,
                                base_desc=b_desc,
                                head_desc=h_desc,
                                pointer=f"#/components/schemas/{s_name}/properties/{p_name}",
                                file_path=file_path,
                            )
                            findings.extend(candidates)
