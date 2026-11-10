"""Unit test for canonical database models using an in-memory SQLite database."""

import pytest
from changescope.db.models import (
    Base,
    OutboxEvent,
    Repository,
    ScanRun,
    Tenant,
    Workspace,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def test_session():
    # Use SQLite in-memory for lightning fast, dependency-free test execution
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_create_tenant_and_workspace(test_session: AsyncSession):
    tenant = Tenant(name="Acme Corp", slug="acme-corp")
    test_session.add(tenant)
    await test_session.commit()
    await test_session.refresh(tenant)

    assert tenant.id is not None

    workspace = Workspace(tenant_id=tenant.id, name="Core Platform", slug="core-platform")
    test_session.add(workspace)
    await test_session.commit()
    await test_session.refresh(workspace)

    assert workspace.id is not None
    assert workspace.tenant_id == tenant.id


@pytest.mark.asyncio
async def test_scan_run_and_outbox_event(test_session: AsyncSession):
    tenant = Tenant(name="Alpha Corp", slug="alpha-corp")
    test_session.add(tenant)
    await test_session.flush()

    workspace = Workspace(tenant_id=tenant.id, name="Payments", slug="payments")
    test_session.add(workspace)
    await test_session.flush()

    repo = Repository(
        workspace_id=workspace.id,
        tenant_id=tenant.id,
        name="payment-service",
        clone_url="https://github.com/alpha/payment-service.git",
        primary_language="python",
        tier="TIER_1",
    )
    test_session.add(repo)
    await test_session.flush()

    scan = ScanRun(
        tenant_id=tenant.id,
        repository_id=repo.id,
        pr_number=42,
        base_sha="a" * 40,
        head_sha="b" * 40,
        status="RUNNING",
    )
    test_session.add(scan)
    await test_session.flush()

    # Create Outbox Event in same transaction
    outbox = OutboxEvent(
        tenant_id=tenant.id,
        aggregate_type="SCAN",
        aggregate_id=scan.id,
        event_type="SCAN_PROJECTION_PENDING",
        payload={"scan_id": scan.id, "base_sha": scan.base_sha, "head_sha": scan.head_sha},
        status="PENDING",
    )
    test_session.add(outbox)
    await test_session.commit()

    # Query outbox
    result = await test_session.execute(select(OutboxEvent).where(OutboxEvent.status == "PENDING"))
    events = result.scalars().all()
    assert len(events) == 1
    assert events[0].aggregate_id == scan.id
    assert events[0].payload["head_sha"] == "b" * 40
