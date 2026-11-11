"""AsyncAPI Specification Differ for Event-Driven Microservices."""

from typing import Any

from packages.contracts.asyncapi_parser import AsyncAPIParser
from packages.contracts.diff.schema_differ import SchemaDiffer
from packages.contracts.models import (
    ChangeCategory,
    ConsumerContractProfile,
    ContractFinding,
    FindingSeverity,
)


class AsyncAPIDiffer:
    """Evaluates differences between base and head AsyncAPI specifications."""

    @classmethod
    def diff_specs(
        cls,
        base_spec: str | dict[str, Any],
        head_spec: str | dict[str, Any],
        consumers: list[ConsumerContractProfile] | None = None,
        file_path: str = "asyncapi.yaml",
    ) -> list[ContractFinding]:
        """Compares two AsyncAPI specifications and flags event and schema evolution incompatibilities."""
        findings: list[ContractFinding] = []
        active_consumers = consumers or []

        base_dict = (
            AsyncAPIParser.parse_spec(base_spec)
            if isinstance(base_spec, str)
            else AsyncAPIParser._dereference_spec(base_spec)
        )
        head_dict = (
            AsyncAPIParser.parse_spec(head_spec)
            if isinstance(head_spec, str)
            else AsyncAPIParser._dereference_spec(head_spec)
        )

        base_ops = {f"{op.channel_name}:{op.action}": op for op in AsyncAPIParser.extract_operations(base_dict)}
        head_ops = {f"{op.channel_name}:{op.action}": op for op in AsyncAPIParser.extract_operations(head_dict)}

        base_channels = set(base_ops.keys())
        head_channels = set(head_ops.keys())

        # 1. Channel / Operation Removals
        removed_channels = base_channels - head_channels
        for c_key in sorted(removed_channels):
            op = base_ops[c_key]
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.EVENT,
                    change_type="CHANNEL_REMOVED",
                    severity=FindingSeverity.BLOCKING,
                    confidence=1.0,
                    before_state={"channel": op.channel_name, "action": op.action, "operation_id": op.operation_id},
                    after_state={},
                    affected_entities=[op.channel_name],
                    supporting_evidence={"channel": op.channel_name, "action": op.action},
                    recommended_verification=f"Event channel '{op.channel_name}' ({op.action}) removed. Downstream subscribers will miss events.",
                    json_pointer=f"/channels/{op.channel_name}",
                    file_path=file_path,
                )
            )

        # 2. Channel Additions
        added_channels = head_channels - base_channels
        for c_key in sorted(added_channels):
            op = head_ops[c_key]
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.EVENT,
                    change_type="CHANNEL_ADDED",
                    severity=FindingSeverity.INFO,
                    confidence=1.0,
                    before_state={},
                    after_state={"channel": op.channel_name, "action": op.action},
                    affected_entities=[op.channel_name],
                    supporting_evidence={"channel": op.channel_name},
                    recommended_verification=f"New event channel '{op.channel_name}' added.",
                    json_pointer=f"/channels/{op.channel_name}",
                    file_path=file_path,
                )
            )

        # 3. Common Operations: Payload Schemas, Ordering, Versioning, Delivery Assumptions
        common_channels = base_channels & head_channels
        for c_key in sorted(common_channels):
            b_op = base_ops[c_key]
            h_op = head_ops[c_key]
            channel = b_op.channel_name
            action = b_op.action
            op_ptr = f"/channels/{channel}/{action}"

            # 3.1 Event Ordering Assumptions
            b_bindings = b_op.bindings
            h_bindings = h_op.bindings
            b_ordering = b_bindings.get("ordering") or b_op.payload_schema.get("x-ordering", "none")
            h_ordering = h_bindings.get("ordering") or h_op.payload_schema.get("x-ordering", "none")

            if b_ordering in {"strict", "fifo", "ordered"} and h_ordering not in {"strict", "fifo", "ordered"}:
                findings.append(
                    ContractFinding(
                        change_category=ChangeCategory.EVENT,
                        change_type="EVENT_ORDERING_SHIFT",
                        severity=FindingSeverity.BLOCKING,
                        confidence=0.95,
                        before_state={"ordering": b_ordering},
                        after_state={"ordering": h_ordering},
                        affected_entities=[channel],
                        supporting_evidence={
                            "channel": channel,
                            "old_ordering": b_ordering,
                            "new_ordering": h_ordering,
                        },
                        uncertainty_explanation="Message ordering relaxation may lead to out-of-order state mutations in downstream event consumers.",
                        recommended_verification=f"Strict event ordering was dropped on channel '{channel}'. Verify event consumers can handle out-of-order delivery.",
                        json_pointer=f"{op_ptr}/bindings",
                        file_path=file_path,
                    )
                )

            # 3.2 Delivery Assumptions (at-least-once -> at-most-once)
            b_delivery = b_bindings.get("delivery_guarantee") or b_bindings.get("kafka", {}).get("acks", "all")
            h_delivery = h_bindings.get("delivery_guarantee") or h_bindings.get("kafka", {}).get("acks", "all")
            if (b_delivery in {"at-least-once", "exactly-once", "all", -1}) and (
                h_delivery in {"at-most-once", "none", "0", 0}
            ):
                findings.append(
                    ContractFinding(
                        change_category=ChangeCategory.EVENT,
                        change_type="DELIVERY_ASSUMPTION_CHANGED",
                        severity=FindingSeverity.BLOCKING,
                        confidence=0.90,
                        before_state={"delivery": b_delivery},
                        after_state={"delivery": h_delivery},
                        affected_entities=[channel],
                        supporting_evidence={
                            "channel": channel,
                            "old_delivery": b_delivery,
                            "new_delivery": h_delivery,
                        },
                        uncertainty_explanation="Delivery guarantee downgraded; silent event loss may occur.",
                        recommended_verification=f"Delivery guarantee altered on '{channel}'. Downstream services must not assume guaranteed delivery.",
                        json_pointer=f"{op_ptr}/bindings",
                        file_path=file_path,
                    )
                )

            # 3.3 Message Payload Schema Evolution
            b_payload = b_op.payload_schema
            h_payload = h_op.payload_schema
            if b_payload or h_payload:
                schema_findings = SchemaDiffer.diff_schemas(
                    b_payload,
                    h_payload,
                    pointer_prefix=f"{op_ptr}/message/payload",
                    consumers=active_consumers,
                    is_response=True,  # For events, subscribers are analogous to response consumers
                    file_path=file_path,
                )

                # Convert structural findings to EVENT category
                has_breaking_changes = False
                for sf in schema_findings:
                    sf.change_category = ChangeCategory.EVENT
                    if sf.severity == FindingSeverity.BLOCKING:
                        has_breaking_changes = True
                    findings.append(sf)

                # 3.4 Event Versioning Check
                # If there are breaking changes but channel or event name did NOT increment version
                if has_breaking_changes:
                    is_versioned_channel = any(v in channel.lower() for v in ["/v2", "/v3", ".v2", ".v3", "-v2", "-v3"])
                    if not is_versioned_channel:
                        findings.append(
                            ContractFinding(
                                change_category=ChangeCategory.EVENT,
                                change_type="UNVERSIONED_BREAKING_EVOLUTION",
                                severity=FindingSeverity.BLOCKING,
                                confidence=0.95,
                                before_state={"channel": channel},
                                after_state={"channel": channel},
                                affected_entities=[channel],
                                supporting_evidence={"channel": channel, "breaking_change_count": len(schema_findings)},
                                uncertainty_explanation="Breaking payload changes introduced to unversioned event topic without semantic version bump.",
                                recommended_verification=f"Breaking schema modifications on unversioned channel '{channel}'. Introduce versioned topic (e.g. {channel}.v2).",
                                json_pointer=f"/channels/{channel}",
                                file_path=file_path,
                            )
                        )

        return findings
