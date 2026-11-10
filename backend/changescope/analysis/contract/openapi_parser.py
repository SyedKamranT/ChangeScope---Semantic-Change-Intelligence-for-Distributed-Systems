"""OpenAPI 3.0/3.1 Contract Parser and $ref Resolver."""

import json
from typing import Any

import yaml
from changescope.common.exceptions import ParseError


class OpenAPIParser:
    """Parses OpenAPI 3.0/3.1 specifications and dereferences schemas into canonical models."""

    @classmethod
    def parse_spec(cls, content: str) -> dict[str, Any]:
        """Parses YAML or JSON OpenAPI spec string."""
        try:
            if content.strip().startswith("{"):
                spec = json.loads(content)
            else:
                spec = yaml.safe_load(content)
        except Exception as e:
            raise ParseError(f"Failed to parse OpenAPI document: {str(e)}") from e

        if not isinstance(spec, dict) or ("openapi" not in spec and "swagger" not in spec):
            raise ParseError("Document is not a valid OpenAPI/Swagger specification (missing 'openapi' root field).")

        return cls._dereference_spec(spec)

    @classmethod
    def _dereference_spec(cls, spec: dict[str, Any]) -> dict[str, Any]:
        """Recursively resolves internal $ref pointers (e.g. #/components/schemas/User)."""

        def resolve_ref(ref_str: str, root: dict[str, Any]) -> Any:
            if not ref_str.startswith("#/"):
                return {"type": "object", "description": f"External reference unresolved: {ref_str}"}

            parts = ref_str.lstrip("#/").split("/")
            curr = root
            for part in parts:
                part = part.replace("~1", "/").replace("~0", "~")
                if isinstance(curr, dict) and part in curr:
                    curr = curr[part]
                else:
                    return {"type": "object", "description": f"Dangling reference: {ref_str}"}
            return curr

        def walk(node: Any, root: dict[str, Any], depth: int = 0) -> Any:
            if depth > 50:  # Circular reference protection
                return {"type": "object", "description": "Circular reference detected"}

            if isinstance(node, dict):
                if "$ref" in node and isinstance(node["$ref"], str):
                    target = resolve_ref(node["$ref"], root)
                    # Merge resolved schema with any local overrides (ignoring the $ref itself)
                    resolved = {k: v for k, v in node.items() if k != "$ref"}
                    resolved_target = walk(target, root, depth + 1)
                    if isinstance(resolved_target, dict):
                        return {**resolved_target, **resolved}
                    return resolved_target
                return {k: walk(v, root, depth + 1) for k, v in node.items()}
            elif isinstance(node, list):
                return [walk(item, root, depth + 1) for item in node]
            return node

        return walk(spec, spec)

    @classmethod
    def extract_canonical_endpoints(cls, dereferenced_spec: dict[str, Any]) -> list[dict[str, Any]]:
        """Extracts canonical endpoint records from a dereferenced OpenAPI spec."""
        endpoints = []
        paths = dereferenced_spec.get("paths", {})

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method, op in path_item.items():
                if method.lower() not in {"get", "post", "put", "delete", "patch", "options", "head"}:
                    continue
                if not isinstance(op, dict):
                    continue

                operation_id = op.get("operationId", f"{method.lower()}_{path.replace('/', '_')}")

                # Extract request schema
                req_body = op.get("requestBody", {})
                content = req_body.get("content", {})
                app_json = content.get("application/json", {})
                req_schema = app_json.get("schema", {})

                # Extract response schemas
                responses = op.get("responses", {})
                resp_schemas = {}
                for status_code, resp_item in responses.items():
                    if isinstance(resp_item, dict):
                        resp_content = resp_item.get("content", {})
                        resp_json = resp_content.get("application/json", {})
                        if "schema" in resp_json:
                            resp_schemas[str(status_code)] = resp_json["schema"]

                endpoints.append(
                    {
                        "method": method.upper(),
                        "path_template": path,
                        "operation_id": operation_id,
                        "summary": op.get("summary", ""),
                        "request_schema": req_schema,
                        "response_schemas": resp_schemas,
                        "parameters": op.get("parameters", []),
                    }
                )

        return endpoints
