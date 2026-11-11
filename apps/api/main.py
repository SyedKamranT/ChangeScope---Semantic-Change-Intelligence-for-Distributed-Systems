"""ChangeScope API Gateway Application Entrypoint."""

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.config import settings
from packages.shared.database import close_db, get_db_session, init_db
from packages.shared.errors import (
    ChangeScopeBaseError,
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
    problem_detail_response,
)
from packages.shared.logger import configure_structured_logging, logger
from packages.shared.models import (
    OutboxEvent,
    Repository,
    RuntimeDependency,
    RuntimeTraceSpan,
    ScanRun,
    Tenant,
    Violation,
    Workspace,
)
from packages.shared.security import (
    CorrelationIdMiddleware,
    SecurityContext,
    TenantRole,
    create_access_token,
    get_correlation_id,
    get_current_security_context,
    require_role,
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
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Semantic Change Intelligence for Distributed Systems",
    lifespan=lifespan,
)

# Request Correlation ID Middleware (MUST be added first to trace all downstream handlers)
app.add_middleware(CorrelationIdMiddleware)

# Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- RFC 7807 Problem Details Exception Handlers ---


@app.exception_handler(ChangeScopeBaseError)
async def handle_changescope_base_error(request: Request, exc: ChangeScopeBaseError) -> Response:
    logger.warning(
        "domain_exception_raised", error_type=exc.error_type, status_code=exc.status_code, message=exc.message
    )
    return problem_detail_response(
        exc=exc,
        instance=str(request.url),
        request_id=get_correlation_id(),
    )


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
async def acquire_token(req: TokenRequest) -> TokenResponse:
    """Issues a cryptographically signed JWT access token for local or authenticated access."""
    tenant_id = req.tenant_id or settings.DEFAULT_TENANT_ID
    claims = {
        "sub": req.username,
        "tenant_id": tenant_id,
        "roles": [req.role.value],
        "email": f"{req.username}@changescope.local",
    }
    token = create_access_token(claims)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_minutes=settings.JWT_EXPIRE_MINUTES,
        tenant_id=tenant_id,
    )


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
    query = select(Workspace).where(Workspace.tenant_id == context.tenant_id)
    result = await db.execute(query)
    workspaces = result.scalars().all()
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
    # Ensure tenant exists
    tenant_res = await db.execute(select(Tenant).where(Tenant.id == context.tenant_id))
    tenant = tenant_res.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(
            id=context.tenant_id,
            name="Default Organization",
            slug=f"org-{context.tenant_id[:8]}",
            tier="enterprise",
        )
        db.add(tenant)
        await db.flush()

    # Check for slug collision within tenant
    existing = await db.execute(
        select(Workspace).where(
            Workspace.tenant_id == context.tenant_id,
            Workspace.slug == req.slug,
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"Workspace with slug '{req.slug}' already exists in this tenant.")

    workspace = Workspace(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        name=req.name,
        slug=req.slug,
    )
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
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
    db: AsyncSession = Depends(get_db_session),
    context: SecurityContext = Depends(get_current_security_context),
) -> list[dict[str, Any]]:
    """Lists registered repositories belonging to the authenticated tenant."""
    query = select(Repository).where(Repository.tenant_id == context.tenant_id)
    if workspace_id:
        query = query.where(Repository.workspace_id == workspace_id)
    result = await db.execute(query)
    repos = result.scalars().all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "clone_url": r.clone_url,
            "default_branch": r.default_branch,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in repos
    ]


@app.post("/api/v1/repositories", tags=["Repositories"], status_code=status.HTTP_201_CREATED)
async def register_repository(
    req: RepositoryRegisterRequest,
    db: AsyncSession = Depends(get_db_session),
    context: SecurityContext = Depends(require_role(TenantRole.ENGINEER)),
) -> dict[str, Any]:
    """Registers a repository for semantic scanning."""
    repo_id = str(uuid.uuid4())
    repo = Repository(
        id=repo_id,
        tenant_id=context.tenant_id,
        workspace_id=req.workspace_id,
        name=req.name,
        clone_url=req.clone_url,
        default_branch=req.default_branch,
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)
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
) -> dict[str, Any]:
    """Enqueues an asynchronous semantic change intelligence scan and writes an Outbox event."""
    # Verify repository exists and belongs to the authenticated tenant
    repo_res = await db.execute(
        select(Repository).where(
            Repository.id == req.repository_id,
            Repository.tenant_id == context.tenant_id,
        )
    )
    repo = repo_res.scalar_one_or_none()
    if not repo:
        raise NotFoundError(f"Repository '{req.repository_id}' not found in tenant.")

    scan_id = str(uuid.uuid4())
    scan_run = ScanRun(
        id=scan_id,
        tenant_id=context.tenant_id,
        repository_id=req.repository_id,
        target_branch=req.target_branch,
        source_branch=req.source_branch,
        base_sha=req.base_commit,
        head_sha=req.head_commit,
        status="QUEUED",
    )
    db.add(scan_run)

    # Outbox Pattern: Emit durable transactional outbox event
    outbox_event = OutboxEvent(
        id=str(uuid.uuid4()),
        tenant_id=context.tenant_id,
        aggregate_type="ScanRun",
        aggregate_id=scan_id,
        event_type="SCAN_ENQUEUED",
        payload={
            "scan_id": scan_id,
            "repository_id": req.repository_id,
            "base_commit": req.base_commit,
            "head_commit": req.head_commit,
            "changed_files": req.changed_files,
            "tenant_id": context.tenant_id,
        },
    )
    db.add(outbox_event)
    await db.commit()

    logger.info("scan_run_enqueued", scan_id=scan_id, repository_id=req.repository_id, tenant_id=context.tenant_id)
    return {
        "scan_id": scan_id,
        "status": "QUEUED",
        "repository_id": req.repository_id,
        "created_at": datetime.now(UTC).isoformat(),
    }


@app.get("/api/v1/scans/{scan_id}", tags=["Scans"])
async def get_scan_status(
    scan_id: str,
    db: AsyncSession = Depends(get_db_session),
    context: SecurityContext = Depends(get_current_security_context),
) -> dict[str, Any]:
    """Retrieves execution status, metrics, and risk assessment for a scan run."""
    res = await db.execute(
        select(ScanRun).where(
            ScanRun.id == scan_id,
            ScanRun.tenant_id == context.tenant_id,
        )
    )
    scan = res.scalar_one_or_none()
    if not scan:
        raise NotFoundError(f"Scan run '{scan_id}' not found.")

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
    # Ensure scan exists and tenant has access
    scan_res = await db.execute(
        select(ScanRun).where(
            ScanRun.id == scan_id,
            ScanRun.tenant_id == context.tenant_id,
        )
    )
    if not scan_res.scalar_one_or_none():
        raise NotFoundError(f"Scan run '{scan_id}' not found.")

    query = select(Violation).where(
        Violation.scan_id == scan_id,
        Violation.tenant_id == context.tenant_id,
    )
    result = await db.execute(query)
    violations = result.scalars().all()

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

    # Resolve tenant from header or fallback
    header_tenant = request.headers.get("X-Tenant-ID") or request.headers.get("x-tenant-id")
    tenant_id = header_tenant or "tenant-default"

    # Extract & scrub spans
    spans = SpanExtractor.extract_spans(body)
    if not spans:
        return {"status": "ACCEPTED", "spans_ingested": 0, "dependencies_observed": 0}

    # If spans specify changescope.tenant_id in resource attributes, honor it
    first_res_tenant = spans[0].attributes.get("changescope.tenant_id") or spans[0].attributes.get("tenant.id")
    if first_res_tenant and not header_tenant:
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

    services = sorted(
        {d.caller_service_name for d in deps} | {d.callee_service_name for d in deps}
    )

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
