"""OpenAPI 3.x Specification Differ for Change Intelligence."""

from typing import Any

from packages.contracts.diff.schema_differ import SchemaDiffer
from packages.contracts.models import (
    ChangeCategory,
    ConsumerContractProfile,
    ContractFinding,
    ExtractedClientCall,
    FindingSeverity,
)
from packages.contracts.openapi_parser import OpenAPIParser


class OpenAPIDiffer:
    """Evaluates differences between base and head OpenAPI specifications."""

    @classmethod
    def diff_specs(
        cls,
        base_spec: str | dict[str, Any],
        head_spec: str | dict[str, Any],
        consumers: list[ConsumerContractProfile] | None = None,
        client_calls: list[ExtractedClientCall] | None = None,
        file_path: str = "openapi.yaml",
    ) -> list[ContractFinding]:
        """Compares base and head OpenAPI documents and returns all structural and contract findings."""
        findings: list[ContractFinding] = []
        active_consumers = consumers or []
        active_calls = client_calls or []

        # Dereference specs if passed as raw strings or raw dicts
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

        base_endpoints = {
            f"{ep['method']} {ep['path_template']}": ep for ep in OpenAPIParser.extract_canonical_endpoints(base_dict)
        }
        head_endpoints = {
            f"{ep['method']} {ep['path_template']}": ep for ep in OpenAPIParser.extract_canonical_endpoints(head_dict)
        }

        base_keys = set(base_endpoints.keys())
        head_keys = set(head_endpoints.keys())

        # 1. Endpoint Removals
        removed_endpoints = base_keys - head_keys
        for ep_key in sorted(removed_endpoints):
            base_ep = base_endpoints[ep_key]
            method = base_ep["method"]
            path = base_ep["path_template"]

            # Correlate against active client calls
            matching_calls = [
                c
                for c in active_calls
                if c.method.upper() == method and (c.url_or_path == path or path.rstrip("/") in c.url_or_path)
            ]
            evidence: dict[str, Any] = {
                "method": method,
                "path": path,
                "operation_id": base_ep.get("operation_id"),
            }
            if matching_calls:
                evidence["active_client_callers"] = [
                    {"file": c.file_path, "line": c.start_line, "lib": c.client_library} for c in matching_calls
                ]

            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.STRUCTURAL,
                    change_type="ENDPOINT_REMOVED",
                    severity=FindingSeverity.BLOCKING,
                    confidence=1.0,
                    before_state={"method": method, "path": path, "operation_id": base_ep.get("operation_id")},
                    after_state={},
                    affected_entities=[f"{method} {path}"],
                    supporting_evidence=evidence,
                    recommended_verification=f"Endpoint '{method} {path}' removed from API contract. Update all calling microservices.",
                    json_pointer=f"/paths{path}/{method.lower()}",
                    file_path=file_path,
                )
            )

        # 2. Endpoint Additions
        added_endpoints = head_keys - base_keys
        for ep_key in sorted(added_endpoints):
            head_ep = head_endpoints[ep_key]
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.STRUCTURAL,
                    change_type="ENDPOINT_ADDED",
                    severity=FindingSeverity.INFO,
                    confidence=1.0,
                    before_state={},
                    after_state={"method": head_ep["method"], "path": head_ep["path_template"]},
                    affected_entities=[ep_key],
                    supporting_evidence={"method": head_ep["method"], "path": head_ep["path_template"]},
                    recommended_verification=f"New endpoint '{ep_key}' introduced.",
                    json_pointer=f"/paths{head_ep['path_template']}/{head_ep['method'].lower()}",
                    file_path=file_path,
                )
            )

        # 3. Method modifications on existing paths
        base_paths = {ep["path_template"]: ep for ep in base_endpoints.values()}
        head_paths = {ep["path_template"]: ep for ep in head_endpoints.values()}
        common_paths = set(base_paths.keys()) & set(head_paths.keys())
        for path in sorted(common_paths):
            base_methods = {k.split()[0] for k in base_keys if k.endswith(f" {path}")}
            head_methods = {k.split()[0] for k in head_keys if k.endswith(f" {path}")}
            dropped_methods = base_methods - head_methods
            for m in sorted(dropped_methods):
                findings.append(
                    ContractFinding(
                        change_category=ChangeCategory.STRUCTURAL,
                        change_type="HTTP_METHOD_CHANGED",
                        severity=FindingSeverity.BLOCKING,
                        confidence=1.0,
                        before_state={"method": m, "path": path},
                        after_state={"supported_methods": sorted(head_methods)},
                        affected_entities=[f"{m} {path}"],
                        supporting_evidence={"dropped_method": m, "path": path},
                        recommended_verification=f"Method '{m}' was removed on path '{path}'. Clients will receive HTTP 405 Method Not Allowed.",
                        json_pointer=f"/paths{path}/{m.lower()}",
                        file_path=file_path,
                    )
                )

        # 4. Common Endpoints Deep Schema & Parameter Diffing
        common_keys = base_keys & head_keys
        for ep_key in sorted(common_keys):
            base_ep = base_endpoints[ep_key]
            head_ep = head_endpoints[ep_key]
            path = base_ep["path_template"]
            method = base_ep["method"]
            op_pointer = f"/paths{path}/{method.lower()}"

            # Parameters Diff
            findings.extend(
                cls._diff_parameters(
                    base_ep.get("parameters", []),
                    head_ep.get("parameters", []),
                    op_pointer,
                    file_path,
                )
            )

            # Request Body Schema Diff
            base_req = base_ep.get("request_schema", {})
            head_req = head_ep.get("request_schema", {})
            if base_req or head_req:
                findings.extend(
                    SchemaDiffer.diff_schemas(
                        base_req,
                        head_req,
                        pointer_prefix=f"{op_pointer}/requestBody",
                        consumers=active_consumers,
                        is_response=False,
                        file_path=file_path,
                    )
                )

            # Response Schemas Diff
            base_responses = base_ep.get("response_schemas", {})
            head_responses = head_ep.get("response_schemas", {})

            # Check for removed status codes
            removed_status = set(base_responses.keys()) - set(head_responses.keys())
            for sc in sorted(removed_status):
                findings.append(
                    ContractFinding(
                        change_category=ChangeCategory.STRUCTURAL,
                        change_type="RESPONSE_STATUS_REMOVED",
                        severity=FindingSeverity.BLOCKING,
                        confidence=1.0,
                        before_state={"status_code": sc, "schema": base_responses[sc]},
                        after_state={},
                        affected_entities=[f"{ep_key} -> {sc}"],
                        supporting_evidence={"status_code": sc, "endpoint": ep_key},
                        recommended_verification=f"Response status '{sc}' was removed from endpoint '{ep_key}'. Downstream consumers expecting {sc} will fail.",
                        json_pointer=f"{op_pointer}/responses/{sc}",
                        file_path=file_path,
                    )
                )

            # Diff common response schemas
            common_status = set(base_responses.keys()) & set(head_responses.keys())
            for sc in sorted(common_status):
                findings.extend(
                    SchemaDiffer.diff_schemas(
                        base_responses[sc],
                        head_responses[sc],
                        pointer_prefix=f"{op_pointer}/responses/{sc}",
                        consumers=active_consumers,
                        is_response=True,
                        file_path=file_path,
                    )
                )

        return findings

    @classmethod
    def _diff_parameters(
        cls,
        base_params: list[dict[str, Any]],
        head_params: list[dict[str, Any]],
        op_pointer: str,
        file_path: str,
    ) -> list[ContractFinding]:
        findings: list[ContractFinding] = []

        base_map = {f"{p.get('in')}:{p.get('name')}": p for p in base_params if isinstance(p, dict)}
        head_map = {f"{p.get('in')}:{p.get('name')}": p for p in head_params if isinstance(p, dict)}

        # Added required parameters
        for p_key, head_p in head_map.items():
            if p_key not in base_map:
                is_req = head_p.get("required", False)
                if is_req:
                    findings.append(
                        ContractFinding(
                            change_category=ChangeCategory.STRUCTURAL,
                            change_type="REQUIRED_PARAMETER_ADDED",
                            severity=FindingSeverity.BLOCKING,
                            confidence=1.0,
                            before_state={},
                            after_state=head_p,
                            affected_entities=[f"{op_pointer}/parameters/{p_key}"],
                            supporting_evidence={"param_name": head_p.get("name"), "in": head_p.get("in")},
                            recommended_verification=f"Required parameter '{head_p.get('name')}' ({head_p.get('in')}) added. Existing clients will fail requests.",
                            json_pointer=f"{op_pointer}/parameters/{head_p.get('name')}",
                            file_path=file_path,
                        )
                    )

        # Removed parameters
        for p_key, base_p in base_map.items():
            if p_key not in head_map:
                findings.append(
                    ContractFinding(
                        change_category=ChangeCategory.STRUCTURAL,
                        change_type="PARAMETER_REMOVED",
                        severity=FindingSeverity.WARNING,
                        confidence=1.0,
                        before_state=base_p,
                        after_state={},
                        affected_entities=[f"{op_pointer}/parameters/{p_key}"],
                        supporting_evidence={"param_name": base_p.get("name"), "in": base_p.get("in")},
                        recommended_verification=f"Parameter '{base_p.get('name')}' ({base_p.get('in')}) was removed.",
                        json_pointer=f"{op_pointer}/parameters/{base_p.get('name')}",
                        file_path=file_path,
                    )
                )

        return findings
