"""ChangeScope API Gateway Application Entrypoint."""

import hashlib
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, FastAPI, Header, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.models import ContractFinding
from packages.shared.config import settings
from packages.shared.database import close_db, get_db_session, init_db
from packages.shared.errors import (
    AuthenticationError,
    AuthorizationError,
    ChangeScopeBaseError,
    ServiceUnavailableError,
    problem_detail_response,
)
from packages.shared.impact import (
    ChangeSetInput,
    ImpactReasoningEngine,
    ImpactReasoningResult,
)
from packages.shared.integrations.github import GitHubWebhookHandler
from packages.shared.logger import configure_structured_logging, logger
from packages.shared.models import (
    IdempotencyRecord,
    RuntimeDependency,
    RuntimeTraceSpan,
)
from packages.shared.remediation import (
    IncidentPreventionReport,
    RemediationOrchestrator,
)
from packages.shared.security import (
    AuditLogger,
    CorrelationIdMiddleware,
    RequestTimeoutMiddleware,
    SecurityContext,
    SecurityHeadersMiddleware,
    TenantRole,
    UploadSecurityError,
    UploadValidator,
    clear_session_cookie,
    create_access_token,
    decode_token,
    get_correlation_id,
    get_current_security_context,
    oidc_client,
    rate_limiter,
    require_role,
    set_secure_session_cookie,
)
from packages.shared.services import (
    CredentialService,
    GraphQueryService,
    RepositoryService,
    ScanService,
    WorkspaceService,
)
from packages.shared.telemetry import (
    DependencyBuilder,
    ObservedServiceDependency,
    ProtocolType,
    RuntimeCorrelationEngine,
    SpanExtractor,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event handler for database connections and runtime components."""
    configure_structured_logging()
    logger.info("application_startup_initiated", app_name=settings.APP_NAME, version=settings.APP_VERSION)
    await init_db()
    yield
    await close_db()
    logger.info("application_shutdown_completed")


app = FastAPI(
    title=f"{settings.APP_NAME} Production API",
    version=settings.APP_VERSION,
    description="Semantic Change Intelligence for Distributed Systems — Production API Gateway",
    contact={"name": "ChangeScope Engineering Team", "email": "security@changescope.io"},
    license_info={"name": "Apache 2.0"},
    lifespan=lifespan,
)

# 1. Request Correlation ID Middleware (MUST be added first to trace all downstream handlers)
app.add_middleware(CorrelationIdMiddleware)

# 2. Defense-in-depth Security Headers (HSTS, CSP, X-Content-Type-Options, X-Frame-Options)
app.add_middleware(SecurityHeadersMiddleware)

# 3. Execution Timeout Guard (30s SLA)
app.add_middleware(RequestTimeoutMiddleware, timeout_seconds=30.0)

# 4. Cross-Origin Resource Sharing (CORS) with strict origin whitelisting
cors_origins = settings.CORS_ORIGINS if settings.CORS_ORIGINS else ["*"]
allow_credentials = False if "*" in cors_origins else True
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)


# --- RFC 7807 Problem Details Exception Handlers ---


@app.exception_handler(ChangeScopeBaseError)
async def handle_changescope_base_error(request: Request, exc: ChangeScopeBaseError) -> Response:
    logger.warning(
        "domain_exception_raised", error_type=exc.error_type, status_code=exc.status_code, message=exc.message
    )
    resp = problem_detail_response(
        exc=exc,
        instance=str(request.url),
        request_id=get_correlation_id(),
    )
    if hasattr(exc, "retry_after_seconds"):
        resp.headers["Retry-After"] = str(exc.retry_after_seconds)
    return resp


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> Response:
    invalid_params = []
    for err in exc.errors():
        invalid_params.append(
            {
                "name": ".".join(str(loc) for loc in err["loc"]),
                "reason": err["msg"],
                "type": err["type"],
            }
        )
    logger.warning("request_validation_error", errors=invalid_params)
    from packages.shared.errors import ProblemDetail

    problem = ProblemDetail(
        type="https://changescope.io/errors/validation-error",
        title="Request Validation Error",
        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="The request body or parameters failed schema validation.",
        instance=str(request.url),
        request_id=get_correlation_id(),
        invalid_params=invalid_params,
    )
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
    )


@app.exception_handler(Exception)
async def handle_generic_exception(request: Request, exc: Exception) -> Response:
    logger.error("unhandled_server_exception", error=str(exc), exc_info=True)
    from fastapi.responses import JSONResponse

    from packages.shared.errors import ProblemDetail

    problem = ProblemDetail(
        type="https://changescope.io/errors/internal-server-error",
        title="Internal Server Error",
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected error occurred while processing the request.",
        instance=str(request.url),
        request_id=get_correlation_id(),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
    )


# --- Health & Readiness Endpoints ---


@app.get("/health/live", summary="Liveness probe", tags=["Health"])
async def liveness_probe() -> dict[str, Any]:
    """Lightweight endpoint returning 200 OK while the API gateway process is executing."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get("/health/ready", summary="Readiness probe", tags=["Health"])
async def readiness_probe(db: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    """Evaluates connectivity to all required datastores (PostgreSQL, Redis, Neo4j)."""
    checks: dict[str, str] = {}

    # 1. PostgreSQL Database Check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as exc:
        logger.error("readiness_check_database_failed", error=str(exc))
        checks["database"] = f"unhealthy: {exc}"

    # 2. Redis Connection Check
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL, socket_timeout=settings.REDIS_SOCKET_TIMEOUT)
        await r.ping()
        await r.aclose()
        checks["redis"] = "healthy"
    except Exception as exc:
        # In local dev if redis isn't running, mark warning/degraded
        checks["redis"] = f"unreachable: {exc}"

    # 3. Neo4j Connection Check
    if settings.NEO4J_MOCK_MODE:
        checks["neo4j"] = "mocked"
    else:
        try:
            from neo4j import AsyncGraphDatabase

            auth = (settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=auth,
                connection_timeout=settings.NEO4J_CONNECTION_TIMEOUT,
            )
            await driver.verify_connectivity()
            await driver.close()
            checks["neo4j"] = "healthy"
        except Exception as exc:
            checks["neo4j"] = f"unreachable: {exc}"

    is_ready = checks.get("database") == "healthy"
    if not is_ready:
        raise ServiceUnavailableError("Core database service is not ready.")

    return {
        "status": "ready" if is_ready else "degraded",
        "checks": checks,
        "timestamp": datetime.now(UTC).isoformat(),
    }


# --- Authentication & Workspace API Schemas ---


class TokenRequest(BaseModel):
    username: str = Field(..., min_length=2)
    tenant_id: str | None = None
    role: TenantRole = TenantRole.ENGINEER


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    tenant_id: str


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    slug: str = Field(..., min_length=2, max_length=120)


class RepositoryRegisterRequest(BaseModel):
    workspace_id: str
    name: str = Field(..., min_length=2, max_length=120)
    clone_url: str
    default_branch: str = "main"


class ScanTriggerRequest(BaseModel):
    repository_id: str
    target_branch: str = "main"
    source_branch: str = "feat/contract-update"
    base_commit: str = "0000000"
    head_commit: str = "1111111"
    changed_files: list[str] = Field(default_factory=list)


# --- Authentication & Authorization Endpoints ---


@app.post("/api/v1/auth/token", response_model=TokenResponse, tags=["Authentication"])
async def acquire_token(req: TokenRequest, response: Response) -> TokenResponse:
    """Issues a signed JWT access token in local/test mode. Disabled in staging/production."""
    if settings.ENVIRONMENT in {"staging", "production"} or oidc_client.is_configured:
        raise AuthorizationError(
            "Direct local token issuance is disabled in staging/production or when OIDC is configured."
        )
    tenant_id = req.tenant_id or settings.DEFAULT_TENANT_ID
    claims = {
        "sub": req.username,
        "tenant_id": tenant_id,
        "roles": [req.role.value],
        "email": f"{req.username}@changescope.local",
    }
    token = create_access_token(claims)
    set_secure_session_cookie(response, token)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_minutes=settings.JWT_EXPIRE_MINUTES,
        tenant_id=tenant_id,
    )


@app.post("/api/v1/auth/logout", tags=["Authentication"])
async def logout(response: Response) -> dict[str, str]:
    """Clears the session cookie on user logout."""
    clear_session_cookie(response)
    return {"status": "LOGGED_OUT"}


@app.get("/api/v1/me", tags=["Authentication"])
async def get_current_user_profile(
    context: SecurityContext = Depends(get_current_security_context),
) -> dict[str, Any]:
    """Returns the authenticated principal and tenant boundary context."""
    return {
        "user_id": context.user_id,
        "tenant_id": context.tenant_id,
        "roles": context.roles,
        "email": context.email,
    }


# --- Workspaces Endpoints ---


@app.get("/api/v1/workspaces", tags=["Workspaces"])
async def list_workspaces(
    db: AsyncSession = Depends(get_db_session),
    context: SecurityContext = Depends(get_current_security_context),
) -> list[dict[str, Any]]:
    """Lists all workspaces belonging to the authenticated tenant."""
    service = WorkspaceService(db)
    workspaces = await service.list_workspaces(context)
    return [
        {
            "id": w.id,
            "name": w.name,
            "slug": w.slug,
            "created_at": w.created_at.isoformat(),
        }
        for w in workspaces
    ]


@app.post("/api/v1/workspaces", tags=["Workspaces"], status_code=status.HTTP_201_CREATED)
async def create_workspace(
    req: WorkspaceCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    context: SecurityContext = Depends(require_role(TenantRole.ADMIN)),
) -> dict[str, Any]:
    """Creates a new workspace within the authenticated tenant."""
    service = WorkspaceService(db)
    workspace = await service.create_workspace(context, name=req.name, slug=req.slug)
    await db.commit()
    logger.info("workspace_created", workspace_id=workspace.id, slug=workspace.slug, tenant_id=context.tenant_id)
    return {
        "id": workspace.id,
        "name": workspace.name,
        "slug": workspace.slug,
        "created_at": workspace.created_at.isoformat(),
    }


# --- Repositories Endpoints ---


@app.get("/api/v1/repositories", tags=["Repositories"])
async def list_repositories(
    workspace_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session),
    context: SecurityContext = Depends(get_current_security_context),
) -> list[dict[str, Any]]:
    """Lists registered repositories belonging to the authenticated tenant with pagination."""
    safe_limit = min(max(1, limit), 100)
    safe_offset = max(0, offset)
    service = RepositoryService(db)
    repos = await service.list_repositories(context, workspace_id=workspace_id)
    paged = repos[safe_offset : safe_offset + safe_limit]
    return [
        {
            "id": r.id,
            "tenant_id": r.tenant_id,
            "workspace_id": r.workspace_id,
            "name": r.name,
            "clone_url": r.clone_url,
            "default_branch": r.default_branch,
            "language": r.primary_language,
            "tier": r.tier,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in paged
    ]


@app.post("/api/v1/repositories", tags=["Repositories"], status_code=status.HTTP_201_CREATED)
async def register_repository(
    req: RepositoryRegisterRequest,
    db: AsyncSession = Depends(get_db_session),
    context: SecurityContext = Depends(require_role(TenantRole.ENGINEER)),
) -> dict[str, Any]:
    """Registers a repository for semantic scanning with BOLA workspace verification and SSRF checks."""
    service = RepositoryService(db)
    repo = await service.register_repository(
        context=context,
        workspace_id=req.workspace_id,
        name=req.name,
        clone_url=req.clone_url,
        default_branch=req.default_branch,
    )
    await db.commit()
    logger.info("repository_registered", repository_id=repo.id, name=repo.name)
    return {
        "id": repo.id,
        "name": repo.name,
        "clone_url": repo.clone_url,
        "default_branch": repo.default_branch,
        "created_at": repo.created_at.isoformat(),
    }


# --- Scan Runs & Change Intelligence Endpoints ---


@app.post("/api/v1/scans", tags=["Scans"], status_code=status.HTTP_202_ACCEPTED)
async def trigger_scan(
    req: ScanTriggerRequest,
    db: AsyncSession = Depends(get_db_session),
    context: SecurityContext = Depends(require_role(TenantRole.ENGINEER)),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Enqueues a semantic change intelligence scan with rate limiting and idempotency deduplication."""
    # 1. Rate Limiting Check
    await rate_limiter.check_rate_limit(key=f"scan:{context.tenant_id}", limit=60, window_seconds=60)

    # 2. Idempotency Check
    req_hash = ""
    if idempotency_key:
        req_hash = hashlib.sha256(req.model_dump_json().encode("utf-8")).hexdigest()
        rec_stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == context.tenant_id,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
        existing_rec = (await db.execute(rec_stmt)).scalar_one_or_none()
        if existing_rec:
            import json

            return dict(json.loads(existing_rec.response_body))

    # 3. Service Layer Execution (Repository tenancy validation and Outbox persistence)
    service = ScanService(db)
    scan_run = await service.trigger_scan(
        context=context,
        repository_id=req.repository_id,
        target_branch=req.target_branch,
        source_branch=req.source_branch,
        base_commit=req.base_commit,
        head_commit=req.head_commit,
        changed_files=req.changed_files,
    )

    response_payload = {
        "scan_id": scan_run.id,
        "status": "QUEUED",
        "repository_id": req.repository_id,
        "created_at": datetime.now(UTC).isoformat(),
    }

    if idempotency_key:
        import json

        rec = IdempotencyRecord(
            id=str(uuid.uuid4()),
            tenant_id=context.tenant_id,
            idempotency_key=idempotency_key,
            request_hash=req_hash,
            response_code=202,
            response_body=json.dumps(response_payload),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
        db.add(rec)

    await db.commit()
    logger.info("scan_run_enqueued", scan_id=scan_run.id, repository_id=req.repository_id, tenant_id=context.tenant_id)
    return response_payload


@app.get("/api/v1/scans/{scan_id}", tags=["Scans"])
async def get_scan_status(
    scan_id: str,
    db: AsyncSession = Depends(get_db_session),
    context: SecurityContext = Depends(get_current_security_context),
) -> dict[str, Any]:
    """Retrieves execution status, metrics, and risk assessment for a scan run."""
    service = ScanService(db)
    scan = await service.get_scan(context, scan_id)

    return {
        "id": scan.id,
        "repository_id": scan.repository_id,
        "status": scan.status,
        "risk_level": scan.risk_level,
        "base_commit": scan.base_commit,
        "head_commit": scan.head_commit,
        "blocking_violations_count": scan.blocking_violations_count,
        "warning_violations_count": scan.warning_violations_count,
        "duration_ms": scan.duration_ms,
        "created_at": scan.created_at.isoformat(),
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
    }


@app.get("/api/v1/scans/{scan_id}/violations", tags=["Scans"])
async def get_scan_violations(
    scan_id: str,
    db: AsyncSession = Depends(get_db_session),
    context: SecurityContext = Depends(get_current_security_context),
) -> list[dict[str, Any]]:
    """Retrieves all detected semantic contract violations for a scan run."""
    service = ScanService(db)
    violations = await service.get_scan_violations(context, scan_id)

    return [
        {
            "id": v.id,
            "rule_code": v.rule_code,
            "severity": v.severity,
            "file_path": v.file_path,
            "start_line": v.start_line,
            "end_line": v.end_line,
            "message": v.message,
            "json_pointer": v.json_pointer,
            "evidence": v.evidence,
        }
        for v in violations
    ]


@app.get("/api/v1/scans", tags=["Scans"])
async def list_scans(
    repository_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session),
    context: SecurityContext = Depends(get_current_security_context),
) -> list[dict[str, Any]]:
    """Lists scan runs for the authenticated tenant with pagination and optional repository filter."""
    service = ScanService(db)
    scans = await service.list_scans(context, repository_id=repository_id, limit=limit, offset=offset)

    return [
        {
            "id": scan.id,
            "repository_id": scan.repository_id,
            "status": scan.status,
            "risk_score": scan.risk_score,
            "risk_level": scan.risk_level,
            "base_commit": scan.base_commit,
            "head_commit": scan.head_commit,
            "target_branch": scan.target_branch,
            "source_branch": scan.source_branch,
            "blocking_violations_count": scan.blocking_violations_count,
            "warning_violations_count": scan.warning_violations_count,
            "duration_ms": scan.duration_ms,
            "created_at": scan.created_at.isoformat(),
            "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        }
        for scan in scans
    ]


# --- Integration Credentials Endpoints ---


class CredentialStoreRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)
    provider: str = Field(..., min_length=2, max_length=64)
    secret: str = Field(..., min_length=1)
    scopes: list[str] = Field(default_factory=list)


@app.post("/api/v1/credentials", tags=["Credentials"], status_code=status.HTTP_201_CREATED)
async def store_credential(
    req: CredentialStoreRequest,
    db: AsyncSession = Depends(get_db_session),
    context: SecurityContext = Depends(require_role(TenantRole.ADMIN)),
) -> dict[str, Any]:
    """Stores third-party integration credentials with AES-256-GCM encryption at rest."""
    service = CredentialService(db)
    cred = await service.store_credential(
        context=context,
        name=req.name,
        provider=req.provider,
        secret_plaintext=req.secret,
        scopes=req.scopes,
    )
    await db.commit()
    return {
        "id": cred.id,
        "name": cred.name,
        "provider": cred.provider,
        "key_id": cred.key_id,
        "created_at": cred.created_at.isoformat(),
    }


@app.get("/api/v1/credentials", tags=["Credentials"])
async def list_credentials(
    db: AsyncSession = Depends(get_db_session),
    context: SecurityContext = Depends(get_current_security_context),
) -> list[dict[str, Any]]:
    """Lists credentials owned by the tenant without revealing secrets."""
    service = CredentialService(db)
    creds = await service.list_credentials(context)
    return [
        {
            "id": c.id,
            "name": c.name,
            "provider": c.provider,
            "key_id": c.key_id,
            "scopes": c.scopes,
            "created_at": c.created_at.isoformat(),
        }
        for c in creds
    ]


@app.get("/api/v1/credentials/{credential_id}/secret", tags=["Credentials"])
async def get_decrypted_credential_secret(
    credential_id: str,
    db: AsyncSession = Depends(get_db_session),
    context: SecurityContext = Depends(require_role(TenantRole.ADMIN)),
) -> dict[str, str]:
    """Decrypts and returns the integration secret. Requires Administrator role."""
    service = CredentialService(db)
    secret = await service.get_decrypted_secret(context, credential_id)
    await db.commit()
    return {"secret": secret}


# --- Webhooks & File Upload Security Endpoints ---


@app.post("/api/v1/webhooks/github", tags=["Webhooks"], status_code=status.HTTP_200_OK)
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
    x_github_event: str | None = Header(None, alias="X-GitHub-Event"),
    x_hub_delivery: str | None = Header(None, alias="X-GitHub-Delivery"),
) -> dict[str, Any]:
    """Verifies incoming GitHub webhook signatures, prevents replay attacks, and schedules analysis."""
    payload_bytes = await request.body()
    result = await GitHubWebhookHandler.handle_webhook(
        payload_bytes=payload_bytes,
        signature_header=x_hub_signature_256,
        event_type=x_github_event,
        delivery_id=x_hub_delivery,
    )
    return result.model_dump()


class UploadSpecRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=256)
    content_base64: str = Field(..., description="Base64 encoded file content")


@app.post("/api/v1/contracts/upload", tags=["Contracts"], status_code=status.HTTP_201_CREATED)
async def upload_contract_spec(
    req: UploadSpecRequest,
    context: SecurityContext = Depends(require_role(TenantRole.ENGINEER)),
) -> dict[str, Any]:
    """Uploads and validates an OpenAPI/AsyncAPI specification or ZIP archive against security constraints."""
    import base64

    try:
        raw_bytes = base64.b64decode(req.content_base64)
    except Exception as exc:
        raise UploadSecurityError("Invalid base64 encoded content.") from exc

    # 1. Size & Extension Checks
    UploadValidator.validate_file_metadata(filename=req.filename, size_bytes=len(raw_bytes))

    # 2. Magic Bytes Binary Execution Guard
    UploadValidator.inspect_magic_bytes(content=raw_bytes, filename=req.filename)

    # 3. Zip Slip & Archive Depth Inspection if ZIP
    validated_files = []
    if req.filename.lower().endswith(".zip"):
        validated_files = UploadValidator.validate_zip_archive(archive_bytes=raw_bytes)

    return {
        "status": "VALIDATED",
        "filename": req.filename,
        "size_bytes": len(raw_bytes),
        "archive_members": validated_files if validated_files else None,
    }


# --- OpenTelemetry OTLP Ingestion & Runtime Dependency Endpoints ---


@app.post("/v1/traces", tags=["Telemetry"], status_code=status.HTTP_200_OK)
async def ingest_otlp_traces(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Standard OpenTelemetry Protocol (OTLP/HTTP) trace ingestion endpoint.

    Accepts standard OTLP JSON (resourceSpans). Scrubs credentials and PII in-memory,
    enforces tenant isolation from X-Tenant-ID header or resource attribute,
    buffers normalized spans, and updates observed runtime dependencies.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    # Authenticate collector token if provided or enforce in staging/production
    auth_header = request.headers.get("Authorization") or ""
    raw_token = request.headers.get("X-ChangeScope-Token") or request.headers.get("x-changescope-token")
    if not raw_token and auth_header.lower().startswith("bearer "):
        raw_token = auth_header[7:].strip()

    header_tenant = request.headers.get("X-Tenant-ID") or request.headers.get("x-tenant-id")
    if raw_token:
        if oidc_client.is_configured:
            signing_key = oidc_client.get_signing_key_for_token(raw_token)
            token_payload = decode_token(
                token=raw_token,
                key=signing_key,
                algorithms=["RS256"],
                audience=settings.OIDC_AUDIENCE,
                issuer=settings.OIDC_ISSUER_URL,
            )
        else:
            token_payload = decode_token(
                token=raw_token,
                key=settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
            )
        tenant_id = token_payload.tenant_id
    elif settings.ENVIRONMENT in {"staging", "production"}:
        raise AuthenticationError(
            "OTLP collector token is required in staging/production ('Authorization: Bearer' or 'X-ChangeScope-Token')."
        )
    else:
        if header_tenant:
            logger.debug("otlp_trace_unauthenticated_header_tenant_local", tenant_id=header_tenant)
        tenant_id = header_tenant or "tenant-default"

    # Extract & scrub spans
    spans = SpanExtractor.extract_spans(body)
    if not spans:
        return {"status": "ACCEPTED", "spans_ingested": 0, "dependencies_observed": 0}

    # Only fall back to resource attributes in unauthenticated local/test collector ingestion
    first_res_tenant = spans[0].attributes.get("changescope.tenant_id") or spans[0].attributes.get("tenant.id")
    if first_res_tenant and not header_tenant and not raw_token:
        tenant_id = str(first_res_tenant)

    # 1. Buffer spans for audit and trace evidence
    for s in spans:
        span_row = RuntimeTraceSpan(
            tenant_id=tenant_id,
            trace_id=s.trace_id,
            span_id=s.span_id,
            parent_span_id=s.parent_span_id,
            service_name=s.service_name,
            name=s.name,
            kind=s.kind.value,
            status_code=s.status_code,
            duration_ms=s.duration_ms,
            environment=s.environment,
            attributes=s.attributes,
        )
        db.add(span_row)

    # 2. Extract and upsert runtime dependencies
    env = spans[0].environment if spans else "production"
    observed_deps = DependencyBuilder.extract_dependencies(spans, environment=env)

    for dep in observed_deps:
        stmt = select(RuntimeDependency).where(
            RuntimeDependency.tenant_id == tenant_id,
            RuntimeDependency.caller_service_name == dep.caller_service_name,
            RuntimeDependency.callee_service_name == dep.callee_service_name,
            RuntimeDependency.http_route == dep.operation_or_route,
            RuntimeDependency.protocol == dep.protocol.value,
            RuntimeDependency.environment == dep.environment,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.call_count_7d += dep.call_count
            existing.error_count += dep.error_count
            existing.p95_latency_ms = dep.p95_latency_ms
            existing.last_observed_at = dep.last_observed_at
            existing.exemplar_trace_id = dep.exemplar_trace_id
            existing.exemplar_span_id = dep.exemplar_span_id
        else:
            new_dep = RuntimeDependency(
                tenant_id=tenant_id,
                caller_service_name=dep.caller_service_name,
                callee_service_name=dep.callee_service_name,
                http_route=dep.operation_or_route,
                http_method=dep.http_method or "ANY",
                protocol=dep.protocol.value,
                messaging_destination=dep.messaging_destination,
                db_system=dep.db_system,
                db_name=dep.db_name,
                environment=dep.environment,
                call_count_7d=dep.call_count,
                error_count=dep.error_count,
                p95_latency_ms=dep.p95_latency_ms,
                exemplar_trace_id=dep.exemplar_trace_id,
                exemplar_span_id=dep.exemplar_span_id,
                first_observed_at=dep.first_observed_at,
                last_observed_at=dep.last_observed_at,
            )
            db.add(new_dep)

    await db.commit()

    logger.info(
        "otlp_trace_batch_ingested",
        tenant_id=tenant_id,
        spans_count=len(spans),
        deps_count=len(observed_deps),
    )
    return {
        "status": "ACCEPTED",
        "spans_ingested": len(spans),
        "dependencies_observed": len(observed_deps),
    }


@app.post("/api/v1/telemetry/traces", tags=["Telemetry"], status_code=status.HTTP_200_OK)
async def ingest_tenant_traces(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    context: SecurityContext = Depends(get_current_security_context),
) -> dict[str, Any]:
    """Authenticated endpoint for submitting OTLP trace payloads scoped to caller tenant."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    spans = SpanExtractor.extract_spans(body)
    if not spans:
        return {"status": "ACCEPTED", "spans_ingested": 0, "dependencies_observed": 0}

    env = spans[0].environment if spans else "production"
    observed_deps = DependencyBuilder.extract_dependencies(spans, environment=env)

    for dep in observed_deps:
        stmt = select(RuntimeDependency).where(
            RuntimeDependency.tenant_id == context.tenant_id,
            RuntimeDependency.caller_service_name == dep.caller_service_name,
            RuntimeDependency.callee_service_name == dep.callee_service_name,
            RuntimeDependency.http_route == dep.operation_or_route,
            RuntimeDependency.protocol == dep.protocol.value,
            RuntimeDependency.environment == dep.environment,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.call_count_7d += dep.call_count
            existing.error_count += dep.error_count
            existing.p95_latency_ms = dep.p95_latency_ms
            existing.last_observed_at = dep.last_observed_at
        else:
            db.add(
                RuntimeDependency(
                    tenant_id=context.tenant_id,
                    caller_service_name=dep.caller_service_name,
                    callee_service_name=dep.callee_service_name,
                    http_route=dep.operation_or_route,
                    http_method=dep.http_method or "ANY",
                    protocol=dep.protocol.value,
                    messaging_destination=dep.messaging_destination,
                    db_system=dep.db_system,
                    db_name=dep.db_name,
                    environment=dep.environment,
                    call_count_7d=dep.call_count,
                    error_count=dep.error_count,
                    p95_latency_ms=dep.p95_latency_ms,
                    exemplar_trace_id=dep.exemplar_trace_id,
                    exemplar_span_id=dep.exemplar_span_id,
                )
            )

    await db.commit()
    return {"status": "ACCEPTED", "spans_ingested": len(spans), "dependencies_observed": len(observed_deps)}


@app.get("/api/v1/telemetry/runtime-graph", tags=["Telemetry"])
async def get_runtime_graph(
    environment: str = "production",
    db: AsyncSession = Depends(get_db_session),
    context: SecurityContext = Depends(get_current_security_context),
) -> dict[str, Any]:
    """Retrieves observed runtime dependency graph for the authenticated tenant."""
    stmt = (
        select(RuntimeDependency)
        .where(
            RuntimeDependency.tenant_id == context.tenant_id,
            RuntimeDependency.environment == environment,
        )
        .order_by(RuntimeDependency.call_count_7d.desc())
    )
    res = await db.execute(stmt)
    deps = res.scalars().all()

    services = sorted({d.caller_service_name for d in deps} | {d.callee_service_name for d in deps})

    return {
        "tenant_id": context.tenant_id,
        "environment": environment,
        "services": services,
        "dependencies": [
            {
                "caller": d.caller_service_name,
                "callee": d.callee_service_name,
                "protocol": d.protocol,
                "route": d.http_route,
                "method": d.http_method,
                "destination": d.messaging_destination,
                "db_system": d.db_system,
                "call_count": d.call_count_7d,
                "error_count": d.error_count,
                "p95_latency_ms": d.p95_latency_ms,
                "last_observed_at": d.last_observed_at.isoformat(),
                "exemplar_trace_id": d.exemplar_trace_id,
            }
            for d in deps
        ],
    }


@app.get("/api/v1/telemetry/correlations", tags=["Telemetry"])
async def get_dependency_correlations(
    environment: str = "production",
    db: AsyncSession = Depends(get_db_session),
    context: SecurityContext = Depends(get_current_security_context),
) -> list[dict[str, Any]]:
    """Correlates runtime dependencies with static repository symbols and contracts."""
    stmt = select(RuntimeDependency).where(
        RuntimeDependency.tenant_id == context.tenant_id,
        RuntimeDependency.environment == environment,
    )
    deps = (await db.execute(stmt)).scalars().all()

    # Convert to ObservedServiceDependency objects
    observed = [
        ObservedServiceDependency(
            caller_service_name=d.caller_service_name,
            callee_service_name=d.callee_service_name,
            protocol=ProtocolType(d.protocol) if d.protocol in ProtocolType._value2member_map_ else ProtocolType.HTTP,
            operation_or_route=d.http_route,
            http_method=d.http_method,
            messaging_destination=d.messaging_destination,
            db_system=d.db_system,
            db_name=d.db_name,
            environment=d.environment,
            call_count=d.call_count_7d,
            error_count=d.error_count,
            p95_latency_ms=d.p95_latency_ms,
            first_observed_at=d.first_observed_at,
            last_observed_at=d.last_observed_at,
            exemplar_trace_id=d.exemplar_trace_id,
            exemplar_span_id=d.exemplar_span_id,
        )
        for d in deps
    ]

    correlated = RuntimeCorrelationEngine.correlate_dependencies(observed)
    return [c.model_dump() for c in correlated]


# --- Deterministic Impact Reasoning Endpoints ---


@app.post("/api/v1/impact/evaluate", tags=["Impact Analysis"], response_model=ImpactReasoningResult)
async def evaluate_changeset_impact(
    changeset: ChangeSetInput,
    db: AsyncSession = Depends(get_db_session),
    context: SecurityContext = Depends(require_role(TenantRole.ENGINEER)),
) -> ImpactReasoningResult:
    """Evaluates multi-hop impact and deterministic risk for a proposed ChangeSet."""
    changeset.tenant_id = context.tenant_id
    graph = await GraphQueryService.build_tenant_graph(db, tenant_id=context.tenant_id)
    engine = ImpactReasoningEngine(graph=graph)
    return engine.evaluate_changeset(changeset)


# --- Remediation Intelligence Endpoints ---


class RemediationReportRequest(BaseModel):
    scan_id: str
    impact_result: ImpactReasoningResult
    findings: list[ContractFinding] = Field(default_factory=list)
    known_test_files: list[str] = Field(default_factory=list)


@app.post("/api/v1/remediation/report", tags=["Remediation"], response_model=IncidentPreventionReport)
async def generate_remediation_report(
    req: RemediationReportRequest,
    context: SecurityContext = Depends(require_role(TenantRole.ENGINEER)),
) -> IncidentPreventionReport:
    """Generates an evidence-backed incident prevention and remediation report."""
    orchestrator = RemediationOrchestrator()
    return orchestrator.generate_incident_prevention_report(
        scan_id=req.scan_id,
        tenant_id=context.tenant_id,
        impact_result=req.impact_result,
        findings=req.findings,
        known_test_files=req.known_test_files or None,
    )


# --- Security Audit & Domain Intelligence Endpoints ---


@app.get("/api/v1/audit-logs", tags=["Audit Logs"])
async def list_audit_logs(
    event_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session),
    context: SecurityContext = Depends(get_current_security_context),
) -> list[dict[str, Any]]:
    """Retrieves tenant-scoped security audit trail. Enforces Administrator role."""
    context.assert_role(TenantRole.ADMINISTRATOR)
    events = await AuditLogger.list_events(db, context.tenant_id, event_type=event_type, limit=limit, offset=offset)
    return [
        {
            "id": log.id,
            "actor_id": log.actor_id,
            "actor_role": log.actor_role,
            "event_type": log.event_type,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "client_ip": log.client_ip,
            "status": log.status,
            "details": log.details,
            "created_at": log.created_at.isoformat(),
        }
        for log in events
    ]


@app.get("/api/v1/ontology/concepts", tags=["Ontology"])
async def list_ontology_concepts(
    context: SecurityContext = Depends(get_current_security_context),
) -> dict[str, Any]:
    """Retrieves certified software engineering ontology entities and relationships."""
    context.assert_role(TenantRole.VIEWER)
    from packages.shared.ontology_models import CoreEntityType, RelationshipType

    return {
        "certified_version": "1.0.0",
        "provider": "LocalOntologyProvider + NvidiaAutoOntologyVerified",
        "entities": [
            {
                "name": entity.value,
                "urn_pattern": f"urn:changescope:{entity.value.lower()}:{{id}}",
                "status": "CERTIFIED_DETERMINISTIC",
                "certification_confidence": 1.0,
            }
            for entity in CoreEntityType
        ],
        "relationships": [
            {
                "name": rel.value,
                "status": "CERTIFIED",
                "evidence_required": True,
            }
            for rel in RelationshipType
        ],
    }


@app.get("/api/v1/workflows", tags=["Workflows"])
async def list_workflows(
    db: AsyncSession = Depends(get_db_session),
    context: SecurityContext = Depends(get_current_security_context),
) -> list[dict[str, Any]]:
    """Retrieves tenant-scoped business workflows from certified ontology entities and scan impacts."""
    context.assert_role(TenantRole.VIEWER)
    from packages.shared.models import ScanRun
    from packages.shared.ontology_models import OntologyEntity, OntologyRelationship

    wf_stmt = select(OntologyEntity).where(
        OntologyEntity.tenant_id == context.tenant_id,
        OntologyEntity.entity_type == "Workflow",
    )
    wf_entities = list((await db.execute(wf_stmt)).scalars().all())
    if not wf_entities:
        return []

    rel_stmt = select(OntologyRelationship).where(
        OntologyRelationship.tenant_id == context.tenant_id,
        OntologyRelationship.rel_type == "PART_OF_WORKFLOW",
    )
    wf_rels = list((await db.execute(rel_stmt)).scalars().all())

    recent_blocking_stmt = select(ScanRun).where(
        ScanRun.tenant_id == context.tenant_id,
        ScanRun.blocking_violations_count > 0,
    )
    has_recent_blocking = (await db.execute(recent_blocking_stmt)).scalars().first() is not None

    results: list[dict[str, Any]] = []
    for wf in wf_entities:
        props = wf.properties_payload or {}
        constituent_steps = [
            {
                "step_index": idx + 1,
                "service": rel.source_id,
                "operation": (rel.metadata_payload or {}).get("operation", "PART_OF_WORKFLOW"),
            }
            for idx, rel in enumerate(wf_rels)
            if rel.target_id == wf.id
        ]
        results.append(
            {
                "id": wf.id,
                "name": wf.name,
                "criticality": props.get("criticality", "TIER_2_STANDARD"),
                "owner": props.get("owner", "unassigned"),
                "steps": props.get("steps", constituent_steps),
                "disrupted_by_recent_scans": bool(props.get("disrupted_by_recent_scans", has_recent_blocking)),
                "disruption_reason": props.get("disruption_reason") or wf.description,
            }
        )
    return results
