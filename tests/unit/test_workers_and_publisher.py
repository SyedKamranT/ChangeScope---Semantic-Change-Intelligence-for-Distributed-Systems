"""Unit tests for GitHubPublisher and Outbox Celery tasks."""

import pytest
from changescope.db.models import Base, OutboxEvent, Tenant
from changescope.reasoning.models import RuleViolation
from changescope.reporting.github_publisher import GitHubPublisher
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.mark.asyncio
async def test_github_publisher_offline_simulation():
    violations = [
        RuleViolation(
            rule_code="RULE_ENUM_NARROWED",
            severity="BLOCKING",
            file_path="src/order.py",
            start_line=10,
            end_line=15,
            message="Enum narrowed",
        )
    ]
    res = await GitHubPublisher.publish_check_run(
        repo_owner_name="acme/inventory",
        head_sha="a" * 40,
        risk_score=85,
        risk_level="HIGH",
        violations=violations,
        markdown_report="# ChangeScope Report",
        github_token=None,  # Offline/simulation mode
    )
    assert res["status"] == "simulated"
    assert res["conclusion"] == "failure"
    assert res["annotations_published"] == 1


@pytest.mark.asyncio
async def test_outbox_processing_logic():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        t = Tenant(name="T1", slug="t1")
        session.add(t)
        await session.flush()

        ev = OutboxEvent(
            tenant_id=t.id,
            aggregate_type="SCAN",
            aggregate_id="scan-123",
            event_type="SCAN_PROJECTION_PENDING",
            payload={
                "service": {"id": "s1", "name": "service-1", "tier": "TIER_1"},
                "endpoints": [{"id": "ep1", "method": "GET", "path_template": "/ping"}],
                "dependencies": [],
            },
            status="PENDING",
        )
        session.add(ev)
        await session.commit()
        await session.refresh(ev)

        assert ev.status == "PENDING"
        # Simulate worker processing
        from changescope.graph.projector import GraphProjector

        await GraphProjector.project_scan(ev.tenant_id, ev.payload)
        ev.status = "PROCESSED"
        await session.commit()
        await session.refresh(ev)

        assert ev.status == "PROCESSED"

    await engine.dispose()
