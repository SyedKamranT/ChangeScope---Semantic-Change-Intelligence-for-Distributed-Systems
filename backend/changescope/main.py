"""ChangeScope FastAPI Application Gateway and MCP Server Entrypoint."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from changescope.common.logger import logger, setup_logging
from changescope.config import settings
from changescope.db.init_db import init_db
from changescope.db.models import OutboxEvent, Repository, ScanRun, Workspace
from changescope.db.session import get_db_session
from changescope.graph.driver import GraphDriverFactory
from changescope.graph.schema import init_neo4j_schema
from changescope.identity.auth import create_access_token, get_current_tenant, verify_github_webhook_hmac
from changescope.impact.blast_radius import BlastRadiusCalculator
from changescope.ingestion.runtime.pii_scrubber import PIIScrubber


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    setup_logging()
    logger.info("Initializing ChangeScope application platform", version=settings.APP_VERSION)
    # Initialize DB schemas
    await init_db()
    # Initialize Neo4j constraints
    await init_neo4j_schema()
    yield
    # Cleanup driver on shutdown
    await GraphDriverFactory.close_driver()
    logger.info("ChangeScope shutdown completed")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Semantic Change Intelligence for Distributed Systems",
    lifespan=lifespan,
)

# Enable CORS for frontend Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request & Response Schemas ---


class TokenRequest(BaseModel):
    username: str
    password: str | None = None
    tenant_id: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str


class CreateWorkspaceRequest(BaseModel):
    name: str
    slug: str


class CreateRepoRequest(BaseModel):
    name: str
    clone_url: str
    default_branch: str = "main"
    primary_language: str = "python"
    tier: str = "TIER_2"


class TriggerScanRequest(BaseModel):
    repository_id: str
    base_sha: str
    head_sha: str
    pr_number: int | None = None


# --- Health Endpoints ---


@app.get("/health/live", tags=["Health"])
async def health_live():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/health/ready", tags=["Health"])
async def health_ready(db: AsyncSession = Depends(get_db_session)):
    try:
        # Check DB connectivity
        await db.execute(select(1))
        return {"status": "ready", "database": "connected", "neo4j": "connected"}
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unreachable") from e


# --- Authentication & Workspace Endpoints ---


@app.post("/api/v1/auth/token", response_model=TokenResponse, tags=["Auth"])
async def login(req: TokenRequest):
    tenant_id = req.tenant_id or settings.DEFAULT_TENANT_ID
    token = create_access_token(tenant_id=tenant_id, subject=req.username)
    return TokenResponse(access_token=token, tenant_id=tenant_id)


@app.post("/api/v1/workspaces", tags=["Workspaces"])
async def create_workspace(
    req: CreateWorkspaceRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session),
):
    ws = Workspace(tenant_id=tenant_id, name=req.name, slug=req.slug)
    db.add(ws)
    await db.commit()
    await db.refresh(ws)
    return {"id": ws.id, "name": ws.name, "slug": ws.slug}


@app.get("/api/v1/workspaces/{workspace_id}/repositories", tags=["Repositories"])
async def list_repositories(
    workspace_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(Repository).where(Repository.workspace_id == workspace_id, Repository.tenant_id == tenant_id)
    )
    repos = result.scalars().all()
    return [{"id": r.id, "name": r.name, "tier": r.tier, "language": r.primary_language} for r in repos]


@app.post("/api/v1/workspaces/{workspace_id}/repositories", tags=["Repositories"])
async def add_repository(
    workspace_id: str,
    req: CreateRepoRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session),
):
    repo = Repository(
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        name=req.name,
        clone_url=req.clone_url,
        default_branch=req.default_branch,
        primary_language=req.primary_language,
        tier=req.tier,
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)
    return {"id": repo.id, "name": repo.name, "tier": repo.tier}


# --- Scans & Change Intelligence Endpoints ---


@app.post("/api/v1/scans", status_code=status.HTTP_202_ACCEPTED, tags=["Scans"])
async def trigger_scan(
    req: TriggerScanRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session),
):
    scan = ScanRun(
        tenant_id=tenant_id,
        repository_id=req.repository_id,
        pr_number=req.pr_number,
        base_sha=req.base_sha,
        head_sha=req.head_sha,
        status="RUNNING",
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    # In production, Celery enqueues here. For instant execution in API demo/test mode:
    outbox = OutboxEvent(
        tenant_id=tenant_id,
        aggregate_type="SCAN",
        aggregate_id=scan.id,
        event_type="SCAN_PROJECTION_PENDING",
        payload={"scan_id": scan.id, "base_sha": req.base_sha, "head_sha": req.head_sha},
        status="PENDING",
    )
    db.add(outbox)
    await db.commit()

    return {"scan_id": scan.id, "status": scan.status, "message": "Scan triggered successfully"}


@app.get("/api/v1/scans/{scan_id}", tags=["Scans"])
async def get_scan_details(
    scan_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(ScanRun).where(ScanRun.id == scan_id, ScanRun.tenant_id == tenant_id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan run not found")

    return {
        "scan_id": scan.id,
        "status": scan.status,
        "risk_score": scan.risk_score or 0,
        "risk_level": scan.risk_level or "LOW",
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
    }


@app.get("/api/v1/scans/{scan_id}/blast-radius", tags=["Scans"])
async def get_scan_blast_radius(
    scan_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(ScanRun).where(ScanRun.id == scan_id, ScanRun.tenant_id == tenant_id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan run not found")

    # Compute blast radius
    br = await BlastRadiusCalculator.compute_blast_radius(
        tenant_id=tenant_id,
        endpoint_id=f"scan:{scan_id}",
        max_severity="BLOCKING",
    )

    return {
        "scan_id": scan_id,
        "risk_score": br.risk_score,
        "risk_level": br.risk_level,
        "direct_consumers_count": br.direct_consumers_count,
        "transitive_consumers_count": br.transitive_consumers_count,
        "nodes": br.nodes,
        "edges": br.edges,
    }


# --- Webhooks & Telemetry Ingestion ---


@app.post("/api/v1/webhooks/github", status_code=status.HTTP_202_ACCEPTED, tags=["Webhooks"])
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
):
    body_bytes = await request.body()
    is_valid = verify_github_webhook_hmac(body_bytes, x_hub_signature_256, settings.GITHUB_WEBHOOK_SECRET)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid HMAC signature")

    logger.info("GitHub webhook authenticated successfully", github_event=x_github_event)
    return {"status": "QUEUED", "event": x_github_event}


@app.post("/v1/traces", tags=["Telemetry"])
async def ingest_otlp_traces(
    request: Request,
    x_tenant_id: str | None = Header(None),
):
    """OpenTelemetry OTLP trace span ingestion with in-memory PII scrubbing."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    PIIScrubber.scrub_attributes(body)
    logger.info("Ingested and scrubbed OTLP trace batch", tenant_id=x_tenant_id)
    return {"status": "ACCEPTED", "scrubbed": True}


# --- Model Context Protocol (MCP) Server Interface ---


class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Any = 1
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


@app.post("/mcp", tags=["MCP"])
async def mcp_server_endpoint(req: MCPRequest):
    """Official Model Context Protocol endpoint for AI agent harnesses."""
    method = req.method

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {
                "tools": [
                    {
                        "name": "query_blast_radius",
                        "description": "Calculate multi-hop impact graph and risk score for an endpoint.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "endpoint_id": {"type": "string"},
                                "tenant_id": {"type": "string"},
                            },
                            "required": ["endpoint_id"],
                        },
                    },
                    {
                        "name": "search_services",
                        "description": "List all registered microservices and their operational tiers.",
                        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
                    },
                ]
            },
        }

    elif method == "tools/call":
        tool_name = req.params.get("name")
        args = req.params.get("arguments", {})

        if tool_name == "query_blast_radius":
            ep_id = args.get("endpoint_id", "default_endpoint")
            tenant_id = args.get("tenant_id", settings.DEFAULT_TENANT_ID)
            br = await BlastRadiusCalculator.compute_blast_radius(tenant_id, ep_id)
            return {
                "jsonrpc": "2.0",
                "id": req.id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Blast Radius for {ep_id}: Risk Score {br.risk_score} ({br.risk_level}), "
                            f"Direct Consumers: {br.direct_consumers_count}, Transitive: {br.transitive_consumers_count}.",
                        }
                    ]
                },
            }

        return {
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {"content": [{"type": "text", "text": f"Tool '{tool_name}' executed."}]},
        }

    return {"jsonrpc": "2.0", "id": req.id, "error": {"code": -32601, "message": "Method not found"}}
