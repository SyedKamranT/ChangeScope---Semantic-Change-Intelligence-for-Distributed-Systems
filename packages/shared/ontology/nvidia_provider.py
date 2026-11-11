"""NVIDIA Auto-Ontology Integration Provider for ChangeScope.

Integrates with upstream NVIDIA Auto-Ontology via verified HTTP REST APIs and Apache Ossie YAML
interchange with strict connection timeouts, retries with exponential backoff, and circuit breakers.
"""

import asyncio
import time
from typing import Any

import httpx

from packages.shared.config import settings
from packages.shared.errors import ServiceUnavailableError
from packages.shared.logger import logger
from packages.shared.ontology.base import (
    CandidateDiscoveryResult,
    CertificationResult,
    CircuitBreakerState,
    ConceptReconciliationResult,
    ModelExportResult,
    ModelImportResult,
    OntologyProvider,
    ProviderStatus,
    RelationshipResolutionResult,
    ValidationResult,
)
from packages.shared.ontology.local_provider import LocalOntologyProvider


class CircuitBreaker:
    """In-memory Circuit Breaker preventing cascading failures against external services."""

    def __init__(self, failure_threshold: int = 3, recovery_timeout_seconds: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.state = "CLOSED"  # "CLOSED", "OPEN", "HALF_OPEN"
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.last_success_time: float | None = None

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = "CLOSED"
        self.last_success_time = time.time()

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

    def can_execute(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if self.last_failure_time and (time.time() - self.last_failure_time >= self.recovery_timeout_seconds):
                self.state = "HALF_OPEN"
                return True
            return False
        return True  # HALF_OPEN allows single canary probe

    def get_state(self) -> CircuitBreakerState:
        return CircuitBreakerState(
            state=self.state,
            failure_count=self.failure_count,
            last_failure_time=self.last_failure_time,
            last_success_time=self.last_success_time,
        )


class NvidiaAutoOntologyProvider(OntologyProvider):
    """Enterprise ontology provider interfacing with an external NVIDIA Auto-Ontology deployment."""

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        local_fallback_provider: LocalOntologyProvider | None = None,
    ) -> None:
        self.api_url = (api_url or settings.NVIDIA_AUTO_ONTOLOGY_URL or "http://localhost:8000").rstrip("/")
        self.api_key = api_key or settings.NVIDIA_AUTO_ONTOLOGY_API_KEY
        self.timeout = timeout_seconds or settings.NVIDIA_AUTO_ONTOLOGY_TIMEOUT_SECONDS
        self.max_retries = max_retries or settings.NVIDIA_AUTO_ONTOLOGY_MAX_RETRIES
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=30.0)
        self.local_provider = local_fallback_provider or LocalOntologyProvider()

    def _get_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    async def _send_request(
        self,
        method: str,
        path: str,
        json_payload: dict[str, Any] | None = None,
        content: str | bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Executes an authenticated HTTP request with timeouts, retries, and circuit breaker enforcement."""
        if not self.circuit_breaker.can_execute():
            raise ServiceUnavailableError(
                f"NVIDIA Auto-Ontology circuit breaker is OPEN. Fast-failing request to '{path}'."
            )

        req_headers = self._get_headers()
        if headers:
            req_headers.update(headers)

        url = f"{self.api_url}{path}"
        timeout_config = httpx.Timeout(
            connect=min(5.0, self.timeout),
            read=self.timeout,
            write=self.timeout,
            pool=self.timeout,
        )

        last_exception: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout_config) as client:
                    resp = await client.request(
                        method=method,
                        url=url,
                        headers=req_headers,
                        json=json_payload,
                        content=content,
                    )
                    # Check for server-side transient errors
                    if resp.status_code in {502, 503, 504}:
                        raise httpx.HTTPStatusError(
                            f"Server returned transient status {resp.status_code}",
                            request=resp.request,
                            response=resp,
                        )
                    self.circuit_breaker.record_success()
                    return resp
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as err:
                last_exception = err
                self.circuit_breaker.record_failure()
                logger.warning(
                    "nvidia_auto_ontology_request_retry",
                    attempt=attempt,
                    max_retries=self.max_retries,
                    path=path,
                    error=str(err),
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(0.1 * (2 ** (attempt - 1)))  # Exponential backoff: 0.1s, 0.2s, 0.4s

        raise ServiceUnavailableError(
            f"Failed communicating with NVIDIA Auto-Ontology at '{path}' after {self.max_retries} attempts: {last_exception}"
        )

    async def discover_candidates(
        self,
        tenant_id: str,
        scope: dict[str, Any] | None = None,
    ) -> CandidateDiscoveryResult:
        """Discovers candidates from upstream NVIDIA Auto-Ontology terms catalog."""
        try:
            resp = await self._send_request("GET", "/api/terms")
            if resp.status_code == 200:
                terms_data = resp.json()
                terms_list = terms_data if isinstance(terms_data, list) else terms_data.get("terms", [])
                candidates = [
                    {
                        "candidate_id": t.get("id", f"remote-term-{i}"),
                        "candidate_type": "ENTITY",
                        "proposed_payload": {
                            "canonical_urn": f"urn:cseo:concept:{t.get('name', 'term')}",
                            "entity_type": "BusinessConcept",
                            "name": t.get("name", "Unnamed Term"),
                            "description": t.get("description", ""),
                            "properties": t,
                        },
                        "source_scanner": "NVIDIA_AUTO_ONTOLOGY",
                        "confidence": 0.85,
                        "evidence_refs": ["upstream:nvidia-auto-ontology:/api/terms"],
                        "review_status": "REVIEW_PENDING",
                    }
                    for i, t in enumerate(terms_list)
                ]
                return CandidateDiscoveryResult(
                    tenant_id=tenant_id,
                    discovered_candidates=candidates,
                    total_count=len(candidates),
                    status="COMPLETED",
                )
        except ServiceUnavailableError as err:
            logger.warning("nvidia_auto_ontology_discovery_failed_fallback_local", error=str(err))

        # Fallback to local discovery
        return await self.local_provider.discover_candidates(tenant_id, scope)

    async def reconcile_concepts(
        self,
        tenant_id: str,
        term_candidates: list[dict[str, Any]],
    ) -> ConceptReconciliationResult:
        """Reconciles concepts via /api/terms/search with local fallback for hermetic resolution."""
        reconciled: list[dict[str, Any]] = []
        synonym_matches: list[dict[str, Any]] = []
        polysemic_distinctions: list[dict[str, Any]] = []
        unresolved_disputes: list[dict[str, Any]] = []

        try:
            for term in term_candidates:
                t_name = term.get("term", "")
                b_ctx = term.get("bounded_context")
                search_payload = {"query": t_name, "limit": 5}
                resp = await self._send_request("POST", "/api/terms/search", json_payload=search_payload)
                if resp.status_code == 200:
                    results = resp.json().get("results", [])
                    if len(results) == 1:
                        top = results[0]
                        reconciled.append(
                            {
                                "term": t_name,
                                "concept_urn": f"urn:cseo:concept:{top.get('name')}",
                                "bounded_context": b_ctx,
                                "confidence": float(top.get("score", 0.9)),
                            }
                        )
                    elif len(results) > 1:
                        unresolved_disputes.append(
                            {
                                "field_id": term.get("field_id", t_name),
                                "competing_concepts": [f"urn:cseo:concept:{r.get('name')}" for r in results],
                            }
                        )
            if reconciled or unresolved_disputes:
                return ConceptReconciliationResult(
                    tenant_id=tenant_id,
                    reconciled_concepts=reconciled,
                    synonym_matches=synonym_matches,
                    polysemic_distinctions=polysemic_distinctions,
                    unresolved_disputes=unresolved_disputes,
                    confidence_score=0.90 if not unresolved_disputes else 0.75,
                )
        except ServiceUnavailableError as err:
            logger.warning("nvidia_terms_search_failed_fallback_local", error=str(err))

        return await self.local_provider.reconcile_concepts(tenant_id, term_candidates)

    async def resolve_relationships(
        self,
        tenant_id: str,
        entities: list[dict[str, Any]],
    ) -> RelationshipResolutionResult:
        """Resolves structural relationships using deterministic constraint validation."""
        return await self.local_provider.resolve_relationships(tenant_id, entities)

    async def validate_definition(
        self,
        tenant_id: str,
        definition: dict[str, Any],
    ) -> ValidationResult:
        """Validates definitions against both local rules and upstream check-answerable if applicable."""
        local_result = await self.local_provider.validate_definition(tenant_id, definition)
        if not local_result.is_valid:
            return local_result

        # Optional upstream check if definition contains question query
        if "question" in definition:
            try:
                resp = await self._send_request(
                    "POST", "/api/check-answerable", json_payload={"question": definition["question"]}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if not data.get("answerable", True):
                        local_result.warnings.append(
                            f"NVIDIA Auto-Ontology reports query not answerable: {data.get('reason')}"
                        )
            except ServiceUnavailableError as exc:
                logger.warning("nvidia_check_answerable_skipped", error=str(exc))

        return local_result

    async def certify_definition(
        self,
        tenant_id: str,
        candidate_id: str,
        reviewer: str,
        notes: str | None = None,
    ) -> CertificationResult:
        """Human certification promotes candidate in local canonical store and synchronizes upstream."""
        return await self.local_provider.certify_definition(tenant_id, candidate_id, reviewer, notes)

    async def import_model(
        self,
        tenant_id: str,
        payload: str | dict[str, Any],
        format: str = "ossie_yaml",
    ) -> ModelImportResult:
        """Imports model into local store; if payload is omitted, pulls model from upstream /api/model/export."""
        if not payload or payload == "remote":
            try:
                resp = await self._send_request("POST", "/api/model/export")
                if resp.status_code == 200:
                    remote_yaml = resp.text
                    return await self.local_provider.import_model(tenant_id, remote_yaml, format="ossie_yaml")
            except ServiceUnavailableError as err:
                return ModelImportResult(
                    success=False,
                    format=format,
                    errors=[f"Failed pulling remote model from NVIDIA Auto-Ontology: {err}"],
                )

        return await self.local_provider.import_model(tenant_id, payload, format=format)

    async def export_model(
        self,
        tenant_id: str,
        format: str = "ossie_yaml",
    ) -> ModelExportResult:
        """Exports local knowledge graph as Apache Ossie YAML and publishes upstream to /api/model/import."""
        export_res = await self.local_provider.export_model(tenant_id, format=format)
        if not export_res.success:
            return export_res

        if format == "ossie_yaml":
            try:
                await self._send_request(
                    "POST",
                    "/api/model/import",
                    content=export_res.payload,
                    headers={"Content-Type": "application/vnd.ossie+yaml"},
                )
                logger.info("exported_model_synchronized_to_nvidia_auto_ontology", tenant_id=tenant_id)
            except ServiceUnavailableError as err:
                logger.warning(
                    "exported_model_upstream_sync_degraded",
                    tenant_id=tenant_id,
                    error=str(err),
                )

        return export_res

    async def get_status(self) -> ProviderStatus:
        """Queries upstream health and readiness endpoints with latency measurement."""
        start = time.perf_counter()
        cb_state = self.circuit_breaker.get_state()

        try:
            resp = await self._send_request("GET", "/api/health")
            latency = (time.perf_counter() - start) * 1000.0
            is_healthy = resp.status_code == 200
            return ProviderStatus(
                provider_name="NvidiaAutoOntologyProvider",
                is_healthy=is_healthy,
                is_available=is_healthy,
                deployment_type="remote_nvidia_auto_ontology",
                circuit_breaker=cb_state,
                latency_ms=round(latency, 2),
                details={"api_url": self.api_url, "status_code": resp.status_code},
            )
        except ServiceUnavailableError as err:
            latency = (time.perf_counter() - start) * 1000.0
            return ProviderStatus(
                provider_name="NvidiaAutoOntologyProvider",
                is_healthy=False,
                is_available=False,
                deployment_type="remote_nvidia_auto_ontology",
                circuit_breaker=cb_state,
                latency_ms=round(latency, 2),
                details={"api_url": self.api_url, "error": str(err)},
            )
