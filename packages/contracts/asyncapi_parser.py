"""AsyncAPI v2 and v3 Specification Parser for Event-Driven Microservices."""

import json
from dataclasses import dataclass, field
from typing import Any

import yaml

from packages.shared.errors import ParseError


@dataclass
class AsyncOperation:
    """An asynchronous messaging operation (publish or subscribe)."""

    channel_name: str
    action: str  # 'publish' (send) or 'subscribe' (receive)
    operation_id: str
    message_name: str | None = None
    payload_schema: dict[str, Any] = field(default_factory=dict)
    bindings: dict[str, Any] = field(default_factory=dict)


class AsyncAPIParser:
    """Parses AsyncAPI 2.x and 3.x specifications and normalizes channels, operations, and payload schemas."""

    @classmethod
    def parse_spec(cls, content: str) -> dict[str, Any]:
        """Parses YAML or JSON AsyncAPI document."""
        try:
            if content.strip().startswith("{"):
                spec = json.loads(content)
            else:
                spec = yaml.safe_load(content)
        except Exception as e:
            raise ParseError(f"Failed to parse AsyncAPI document: {str(e)}") from e

        if not isinstance(spec, dict) or "asyncapi" not in spec:
            raise ParseError("Document is not a valid AsyncAPI specification (missing 'asyncapi' root field).")

        return cls._dereference_spec(spec)

    @classmethod
    def _dereference_spec(cls, spec: dict[str, Any]) -> dict[str, Any]:
        """Resolves internal $ref references within the AsyncAPI document."""

        def resolve_ref(ref_str: str, root: dict[str, Any]) -> Any:
            if not ref_str.startswith("#/"):
                return {"type": "object", "description": f"External ref: {ref_str}"}
            parts = ref_str.lstrip("#/").split("/")
            curr = root
            for part in parts:
                part = part.replace("~1", "/").replace("~0", "~")
                if isinstance(curr, dict) and part in curr:
                    curr = curr[part]
                else:
                    return {"type": "object", "description": f"Dangling ref: {ref_str}"}
            return curr

        def walk(node: Any, root: dict[str, Any], depth: int = 0) -> Any:
            if depth > 50:
                return {"type": "object", "description": "Circular reference"}

            if isinstance(node, dict):
                if "$ref" in node and isinstance(node["$ref"], str):
                    target = resolve_ref(node["$ref"], root)
                    resolved = {k: v for k, v in node.items() if k != "$ref"}
                    resolved_target = walk(target, root, depth + 1)
                    if isinstance(resolved_target, dict):
                        return {**resolved_target, **resolved}
                    return resolved_target
                return {k: walk(v, root, depth + 1) for k, v in node.items()}
            elif isinstance(node, list):
                return [walk(item, root, depth + 1) for item in node]
            return node

        result = walk(spec, spec)
        return result if isinstance(result, dict) else {}

    @classmethod
    def extract_operations(cls, dereferenced_spec: dict[str, Any]) -> list[AsyncOperation]:
        """Extracts canonical asynchronous messaging operations across v2 and v3 versions."""
        version = dereferenced_spec.get("asyncapi", "2.0.0")
        if version.startswith("3."):
            return cls._extract_v3_operations(dereferenced_spec)
        return cls._extract_v2_operations(dereferenced_spec)

    @classmethod
    def _extract_v2_operations(cls, spec: dict[str, Any]) -> list[AsyncOperation]:
        """Extracts operations from AsyncAPI 2.x (channels -> publish/subscribe)."""
        operations = []
        channels = spec.get("channels", {})

        for channel_name, channel_item in channels.items():
            if not isinstance(channel_item, dict):
                continue

            for action in ["publish", "subscribe"]:
                if action in channel_item and isinstance(channel_item[action], dict):
                    op_data = channel_item[action]
                    op_id = op_data.get("operationId", f"{action}_{channel_name.replace('/', '_')}")

                    # Extract message payload schema
                    message = op_data.get("message", {})
                    payload_schema = message.get("payload", {}) if isinstance(message, dict) else {}
                    message_name = message.get("name") if isinstance(message, dict) else None

                    channel_bindings = (
                        channel_item.get("bindings", {}) if isinstance(channel_item.get("bindings"), dict) else {}
                    )
                    op_bindings = op_data.get("bindings", {}) if isinstance(op_data.get("bindings"), dict) else {}
                    combined_bindings = {**channel_bindings, **op_bindings}

                    operations.append(
                        AsyncOperation(
                            channel_name=channel_name,
                            action=action,
                            operation_id=op_id,
                            message_name=message_name,
                            payload_schema=payload_schema,
                            bindings=combined_bindings,
                        )
                    )

        return operations

    @classmethod
    def _extract_v3_operations(cls, spec: dict[str, Any]) -> list[AsyncOperation]:
        """Extracts operations from AsyncAPI 3.x (operations -> action -> channel)."""
        operations = []
        ops_dict = spec.get("operations", {})

        for op_id, op_item in ops_dict.items():
            if not isinstance(op_item, dict):
                continue

            action = op_item.get("action", "send")  # 'send' or 'receive'
            canonical_action = "publish" if action == "send" else "subscribe"

            # Resolve channel reference or object
            channel_ref = op_item.get("channel", {})
            channel_name = "unknown_channel"
            if isinstance(channel_ref, dict):
                val = channel_ref.get("address", channel_ref.get("title", "unknown_channel"))
                if val:
                    channel_name = str(val)

            # Extract message payload
            messages = op_item.get("messages", [])
            payload_schema = {}
            msg_name = None
            if messages and isinstance(messages[0], dict):
                msg = messages[0]
                msg_name = msg.get("name")
                payload_schema = msg.get("payload", {})

            operations.append(
                AsyncOperation(
                    channel_name=channel_name,
                    action=canonical_action,
                    operation_id=op_id,
                    message_name=msg_name,
                    payload_schema=payload_schema,
                    bindings=op_item.get("bindings", {}),
                )
            )

        return operations
