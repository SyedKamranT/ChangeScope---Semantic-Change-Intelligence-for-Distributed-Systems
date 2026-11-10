# AGENTS.md
## ChangeScope: Permanent Engineering Rules & Operational Invariants

This file defines the immutable engineering invariants, coding standards, and architectural rules governing all human and AI agents working on the ChangeScope platform.

---

### Mandatory Engineering Rules

1. **Never fabricate successful test results.**  
   All tests must execute against real implementations. Assertions must verify actual state transitions and side effects. Never create trivial or guaranteed-pass tests to simulate coverage.

2. **Never use mocked business data in production flows.**  
   Mocks, stubs, and synthetic fixtures are strictly restricted to isolated test environments (`tests/`). Production execution flows must evaluate real code ASTs, valid specifications, and verified OpenTelemetry traces.

3. **Never leave unfinished TODOs in completed features.**  
   Any feature marked as complete must be fully implemented, with all edge cases handled, errors managed, and accompanying tests passing. No placeholder stubs or unhandled exceptions may remain.

4. **Never silently swallow exceptions.**  
   Catch blocks must handle specific exceptions appropriately, log contextual details at the correct severity, and either recover gracefully or propagate typed domain exceptions. Never use bare `except:` or empty catch blocks.

5. **Never expose secrets or credentials in logs.**  
   API keys, JWT secrets, database passwords, OAuth tokens, and sensitive customer data must never be printed to stdout, stderr, or structured log streams. Telemetry attributes must pass through the PII scrubber prior to buffering.

6. **Never modify unrelated existing files.**  
   Changes must remain laser-focused on the assigned task or feature. Unrelated refactoring, stylistic changes, or arbitrary file updates are strictly prohibited.

7. **Never duplicate domain logic across packages.**  
   Reusable utilities, models, error conventions, and contract parsers must reside in their designated shared packages (`packages/shared`, `packages/contracts`). Applications (`apps/api`, `apps/worker`, `apps/web`) must consume shared packages rather than re-implementing logic.

8. **Every feature requires tests.**  
   No feature or bug fix may be merged without comprehensive automated tests covering positive execution, edge cases, and failure modes.

9. **Every migration must be reversible where possible.**  
   Database migrations (Alembic DDL scripts) must implement both `upgrade()` and `downgrade()` functions. Irreversible operations must be explicitly documented with rationale.

10. **Every external integration needs timeouts and error handling.**  
    All HTTP calls, database connections, Redis commands, and Neo4j queries must declare explicit connection and read timeouts, retries with exponential backoff, and circuit breakers.

11. **Every API endpoint must be authenticated and tenant-scoped where applicable.**  
    All REST and MCP endpoints (excluding `/health/live` and `/health/ready`) must enforce cryptographic token validation (OIDC / JWT) and inject the verified `tenant_id` into database sessions and graph queries.

12. **All architecture deviations must have an ADR.**  
    Any alteration to core design principles, datastore roles, communication protocols, or package boundaries requires a formal Architectural Decision Record in `docs/architecture/ADR.md`.

---

### Architectural Invariants

* **Canonical Store:** PostgreSQL 17 is the single source of truth for all business entities, accounts, and change history.
* **Graph Projection:** Neo4j is an asynchronously synchronized, fully rebuildable read projection.
* **Outbox Pattern:** All graph mutations must pass through the PostgreSQL transactional outbox.
* **Deterministic Grounding:** Contract violation detection and blast radius risk scores are computed strictly via deterministic code algorithms. Large Language Models (via LangGraph) are used exclusively for narrative formatting and must pass the Citation Verification Guard.
