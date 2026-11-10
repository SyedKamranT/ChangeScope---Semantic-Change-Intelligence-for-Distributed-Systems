"""Unit tests for GraphProjector and edge provenance invariants."""

import pytest
from changescope.common.exceptions import InvalidProvenanceError
from changescope.graph.projector import GraphProjector


@pytest.mark.asyncio
async def test_project_scan_valid():
    payload = {
        "service": {"id": "srv-order", "name": "order-service", "tier": "TIER_1"},
        "endpoints": [{"id": "ep-order-create", "method": "POST", "path_template": "/api/v1/orders"}],
        "dependencies": [
            {
                "caller_service_id": "srv-checkout",
                "caller_service_name": "checkout-service",
                "target_endpoint_id": "ep-order-create",
                "provenance": "STATIC_AST",
                "confidence": 1.0,
                "is_observed": False,
                "evidence_ref": "ast_symbol:12345",
            }
        ],
    }
    # Should execute cleanly without error
    await GraphProjector.project_scan(tenant_id="tenant-test-01", payload=payload)


@pytest.mark.asyncio
async def test_project_scan_rejects_missing_provenance():
    payload = {
        "service": {"id": "srv-order", "name": "order-service", "tier": "TIER_1"},
        "dependencies": [
            {
                "caller_service_id": "srv-checkout",
                "target_endpoint_id": "ep-order-create",
                "provenance": "INVALID_GUESS",  # Not an allowed provenance!
                "confidence": 1.0,
                "evidence_ref": "ast_symbol:12345",
            }
        ],
    }
    with pytest.raises(InvalidProvenanceError) as exc_info:
        await GraphProjector.project_scan(tenant_id="tenant-test-01", payload=payload)

    assert "Invalid edge provenance" in str(exc_info.value)


@pytest.mark.asyncio
async def test_project_scan_rejects_invalid_confidence():
    payload = {
        "service": {"id": "srv-order", "name": "order-service", "tier": "TIER_1"},
        "dependencies": [
            {
                "caller_service_id": "srv-checkout",
                "target_endpoint_id": "ep-order-create",
                "provenance": "OTEL_TRACE",
                "confidence": 1.5,  # Invalid: > 1.0
                "evidence_ref": "trace_span:999",
            }
        ],
    }
    with pytest.raises(InvalidProvenanceError) as exc_info:
        await GraphProjector.project_scan(tenant_id="tenant-test-01", payload=payload)

    assert "Invalid edge confidence" in str(exc_info.value)
