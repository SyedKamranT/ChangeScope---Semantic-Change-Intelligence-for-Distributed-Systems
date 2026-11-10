"""Unit Tests for Python, TypeScript, JavaScript, Migration, and Config Extractors."""

from pathlib import Path

from packages.shared.ingestion.extractors.config_and_ownership_extractor import (
    ConfigAndOwnershipExtractor,
)
from packages.shared.ingestion.extractors.migration_extractor import MigrationExtractor
from packages.shared.ingestion.extractors.python_extractor import PythonExtractor
from packages.shared.ingestion.extractors.typescript_extractor import TypeScriptExtractor
from packages.shared.ingestion.sources.github_pr import GitHubPRIngestor


def test_python_extractor_fastapi_and_httpx():
    """Extracts FastAPI routes, httpx client calls, and environment variables."""
    fixture_path = Path("tests/fixtures/sample_repos/python_fastapi_service/src/main.py")
    assert fixture_path.exists()
    content = fixture_path.read_text(encoding="utf-8")

    res = PythonExtractor.extract_source(content, str(fixture_path))
    assert res["error"] is None

    # Verify routes
    routes = res["routes"]
    assert len(routes) == 2
    route_paths = {r.path_template for r in routes}
    assert "/payments/charge" in route_paths
    assert "/payments/{payment_id}" in route_paths

    charge_route = next(r for r in routes if r.path_template == "/payments/charge")
    assert charge_route.method == "POST"
    assert charge_route.handler_name == "process_charge"

    # Verify client calls
    calls = res["client_calls"]
    assert len(calls) == 1
    assert calls[0].method == "GET"
    assert calls[0].client_library == "httpx"
    assert "auth.internal" in calls[0].url_or_path

    # Verify environment variables
    env_vars = res["env_vars"]
    env_names = {ev.name for ev in env_vars}
    assert "DATABASE_URL" in env_names
    assert "SERVICE_SECRET" in env_names


def test_python_extractor_orm_models():
    """Extracts SQLAlchemy ORM model declarations and column definitions."""
    fixture_path = Path("tests/fixtures/sample_repos/python_fastapi_service/src/models.py")
    assert fixture_path.exists()
    content = fixture_path.read_text(encoding="utf-8")

    res = PythonExtractor.extract_source(content, str(fixture_path))
    assert res["error"] is None

    db_patterns = res["db_patterns"]
    assert len(db_patterns) == 1
    model = db_patterns[0]
    assert model.operation == "MODEL_DEF"
    assert model.table_or_model == "ledger_transactions"
    assert model.orm_framework == "SQLAlchemy"
    assert "account_id" in model.columns
    assert "amount_cents" in model.columns


def test_typescript_extractor_express_and_axios():
    """Extracts Express routes, axios client calls, EventEmitter triggers, and process.env."""
    fixture_path = Path("tests/fixtures/sample_repos/typescript_express_service/src/server.ts")
    assert fixture_path.exists()
    content = fixture_path.read_text(encoding="utf-8")

    extractor = TypeScriptExtractor()
    res = extractor.extract_source(content, str(fixture_path))
    assert res["error"] is None

    # Routes
    routes = res["routes"]
    assert len(routes) >= 2
    paths = {r.path_template for r in routes}
    assert "/api/v1/auth/tokens" in paths
    assert "/api/v1/users/profile" in paths

    # Client calls
    calls = res["client_calls"]
    assert len(calls) >= 1
    call = next(c for c in calls if c.client_library == "axios")
    assert call.method == "POST"
    assert "verify" in call.url_or_path

    # Events
    events = res["events"]
    assert len(events) >= 1
    ev = events[0]
    assert ev.pattern_type == "producer"
    assert ev.event_name_or_topic == "user.authenticated"

    # Environment variables
    env_vars = res["env_vars"]
    env_names = {e.name for e in env_vars}
    assert "PORT" in env_names
    assert "ORDER_SERVICE_URL" in env_names


def test_javascript_extractor_routes_and_fetch():
    """Extracts JavaScript routes and fetch client calls."""
    fixture_path = Path("tests/fixtures/sample_repos/javascript_service/index.js")
    assert fixture_path.exists()
    content = fixture_path.read_text(encoding="utf-8")

    extractor = TypeScriptExtractor()
    res = extractor.extract_source(content, str(fixture_path))
    assert res["error"] is None

    routes = res["routes"]
    route_paths = {r.path_template for r in routes}
    assert "/health" in route_paths
    assert "/metrics/dispatch" in route_paths

    calls = res["client_calls"]
    fetch_call = next(c for c in calls if c.client_library == "fetch")
    assert fetch_call is not None
    assert (
        "METRICS_ENDPOINT" in fetch_call.url_or_path
        or "${" in fetch_call.url_or_path
        or "metrics.internal" in fetch_call.url_or_path
    )


def test_migration_extractor_alembic_and_sql():
    """Extracts schema evolution events from Alembic Python scripts and SQL DDL scripts."""
    # Alembic
    alembic_path = Path("tests/fixtures/sample_repos/python_fastapi_service/migrations/versions/0001_initial.py")
    assert alembic_path.exists()
    alembic_content = alembic_path.read_text(encoding="utf-8")

    mig1 = MigrationExtractor.extract_migration(alembic_content, str(alembic_path))
    assert mig1 is not None
    assert mig1.migration_type == "alembic"
    assert "ledger_transactions" in mig1.tables_created

    # Prisma / SQL DDL
    sql_path = Path(
        "tests/fixtures/sample_repos/typescript_express_service/prisma/migrations/20261111_init/migration.sql"
    )
    assert sql_path.exists()
    sql_content = sql_path.read_text(encoding="utf-8")

    mig2 = MigrationExtractor.extract_migration(sql_content, str(sql_path))
    assert mig2 is not None
    assert "users" in mig2.tables_created or "users" in mig2.tables_altered


def test_codeowners_and_config_extractor():
    """Extracts file ownership candidate rules and project dependency manifests."""
    # CODEOWNERS
    codeowners_path = Path("tests/fixtures/sample_repos/python_fastapi_service/.github/CODEOWNERS")
    assert codeowners_path.exists()
    content = codeowners_path.read_text(encoding="utf-8")

    rules = ConfigAndOwnershipExtractor.extract_codeowners(content, str(codeowners_path))
    assert len(rules) == 3
    assert rules[0].pattern == "*"
    assert "@platform-core" in rules[0].owners

    # package.json
    pkg_path = Path("tests/fixtures/sample_repos/typescript_express_service/package.json")
    pkg_content = pkg_path.read_text(encoding="utf-8")
    cfg1 = ConfigAndOwnershipExtractor.extract_config(pkg_content, str(pkg_path))
    assert cfg1 is not None
    assert "express" in cfg1.dependencies
    assert "axios" in cfg1.dependencies

    # requirements.txt
    req_path = Path("tests/fixtures/sample_repos/python_fastapi_service/requirements.txt")
    req_content = req_path.read_text(encoding="utf-8")
    cfg2 = ConfigAndOwnershipExtractor.extract_config(req_content, str(req_path))
    assert cfg2 is not None
    assert "fastapi" in cfg2.dependencies
    assert "httpx" in cfg2.dependencies


def test_github_pr_patch_parsing():
    """Parses unified diff hunks into line numbers in the modified file."""
    sample_patch = """@@ -10,6 +10,8 @@ def checkout():
     print("start checkout")
+    user_id = req.user_id
+    validate_user(user_id)
     return {"status": "ok"}
"""
    lines = GitHubPRIngestor.parse_patch_lines(sample_patch)
    assert 11 in lines
    assert 12 in lines
    assert len(lines) == 2
