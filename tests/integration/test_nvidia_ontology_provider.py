"""Integration and Resilience Tests for NvidiaAutoOntologyProvider.

Covers:
- In-memory CircuitBreaker state transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED).
- Graceful offline fallback to LocalOntologyProvider on network failures.
- Unreachable upstream handling without crashing (Rule 4 & 10).
- Opt-in live integration test against running NVIDIA Auto-Ontology deployment.
"""

import os
import time

import pytest

from packages.shared.ontology.base import ProviderStatus
from packages.shared.ontology.nvidia_provider import CircuitBreaker, NvidiaAutoOntologyProvider


def test_circuit_breaker_lifecycle():
    """Verifies circuit breaker state transitions under failures and recovery."""
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=0.2)
    assert cb.state == "CLOSED"
    assert cb.can_execute() is True

    # Record 2 failures: still CLOSED
    cb.record_failure()
    cb.record_failure()
    assert cb.state == "CLOSED"
    assert cb.can_execute() is True

    # 3rd failure: trips to OPEN
    cb.record_failure()
    assert cb.state == "OPEN"
    assert cb.can_execute() is False

    # Wait for recovery timeout
    time.sleep(0.25)
    # Canary execution allowed, moves to HALF_OPEN
    assert cb.can_execute() is True
    assert cb.state == "HALF_OPEN"

    # Success in HALF_OPEN resets to CLOSED
    cb.record_success()
    assert cb.state == "CLOSED"
    assert cb.failure_count == 0


@pytest.mark.asyncio
async def test_nvidia_provider_offline_status():
    """Verifies that an unreachable upstream service degrades gracefully to unhealthy status."""
    # Point to an unallocated local port with very short timeout
    provider = NvidiaAutoOntologyProvider(
        api_url="http://127.0.0.1:59999",
        timeout_seconds=0.5,
        max_retries=1,
    )

    status: ProviderStatus = await provider.get_status()
    assert status.is_healthy is False
    assert status.is_available is False
    assert status.provider_name == "NvidiaAutoOntologyProvider"
    assert status.deployment_type == "remote_nvidia_auto_ontology"
    assert status.circuit_breaker is not None


@pytest.mark.asyncio
async def test_nvidia_provider_offline_fallback_discovery():
    """Verifies that discover_candidates falls back to local provider when remote is down."""
    provider = NvidiaAutoOntologyProvider(
        api_url="http://127.0.0.1:59999",
        timeout_seconds=0.5,
        max_retries=1,
    )

    tenant_id = "tenant-nvidia-fallback-01"
    # Execute discovery with raw candidate in scope
    res = await provider.discover_candidates(
        tenant_id=tenant_id,
        scope={
            "raw_candidates": [
                {
                    "candidate_type": "ENTITY",
                    "proposed_payload": {
                        "canonical_urn": "urn:cseo:service:fallback-svc",
                        "entity_type": "Service",
                        "name": "fallback-svc",
                    },
                    "source_scanner": "AST",
                    "confidence": 0.88,
                    "evidence_refs": ["ref:01"],
                }
            ]
        },
    )

    assert res.status == "COMPLETED"
    assert res.total_count >= 1
    assert any(
        c["proposed_payload"]["canonical_urn"] == "urn:cseo:service:fallback-svc" for c in res.discovered_candidates
    )


@pytest.mark.asyncio
async def test_nvidia_provider_offline_reconciliation_fallback():
    """Verifies that concept reconciliation falls back gracefully to local provider."""
    provider = NvidiaAutoOntologyProvider(
        api_url="http://127.0.0.1:59999",
        timeout_seconds=0.5,
        max_retries=1,
    )

    tenant_id = "tenant-nvidia-fallback-02"
    reconcile_res = await provider.reconcile_concepts(
        tenant_id=tenant_id,
        term_candidates=[{"term": "arbitrary_field", "field_id": "field_01"}],
    )

    # Empty concepts in tenant should return cleanly without unhandled exceptions
    assert reconcile_res.tenant_id == tenant_id
    assert isinstance(reconcile_res.reconciled_concepts, list)


# ==============================================================================
# OPT-IN LIVE INTEGRATION TESTS
# (Only runs when an active NVIDIA Auto-Ontology deployment is explicitly configured)
# ==============================================================================


NVIDIA_URL = os.getenv("CHANGESCOPE_NVIDIA_AUTO_ONTOLOGY_URL")
NVIDIA_KEY = os.getenv("CHANGESCOPE_NVIDIA_AUTO_ONTOLOGY_API_KEY")


@pytest.mark.skipif(
    not NVIDIA_URL, reason="Requires running NVIDIA Auto-Ontology deployment (CHANGESCOPE_NVIDIA_AUTO_ONTOLOGY_URL)"
)
@pytest.mark.asyncio
async def test_live_nvidia_auto_ontology_health():
    """Opt-in live verification of /api/health against running NVIDIA Auto-Ontology instance."""
    provider = NvidiaAutoOntologyProvider(
        api_url=NVIDIA_URL,
        api_key=NVIDIA_KEY,
        timeout_seconds=5.0,
    )

    status = await provider.get_status()
    assert status.is_healthy is True
    assert status.is_available is True
    assert status.latency_ms is not None
    assert status.latency_ms > 0.0


@pytest.mark.skipif(
    not NVIDIA_URL, reason="Requires running NVIDIA Auto-Ontology deployment (CHANGESCOPE_NVIDIA_AUTO_ONTOLOGY_URL)"
)
@pytest.mark.asyncio
async def test_live_nvidia_auto_ontology_model_export():
    """Opt-in live verification of /api/model/export from running NVIDIA Auto-Ontology instance."""
    provider = NvidiaAutoOntologyProvider(
        api_url=NVIDIA_URL,
        api_key=NVIDIA_KEY,
        timeout_seconds=10.0,
    )

    tenant_id = "tenant-live-nvidia-test"
    import_res = await provider.import_model(tenant_id=tenant_id, payload="remote", format="ossie_yaml")
    assert import_res.success is True
    assert import_res.format == "ossie_yaml"
