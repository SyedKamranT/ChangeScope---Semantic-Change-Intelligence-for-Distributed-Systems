---
name: engineering-standards
description: Enforces ChangeScope permanent engineering rules and architectural invariants across all code modifications.
trigger: always_on
---

# ChangeScope Engineering Rules

All code authored in this repository must comply with the 12 mandatory rules defined in `AGENTS.md`:

1. Never fabricate successful test results.
2. Never use mocked business data in production flows.
3. Never leave unfinished TODOs in completed features.
4. Never silently swallow exceptions.
5. Never expose secrets or credentials in logs.
6. Never modify unrelated existing files.
7. Never duplicate domain logic across packages.
8. Every feature requires tests.
9. Every migration must be reversible where possible.
10. Every external integration needs timeouts and error handling.
11. Every API endpoint must be authenticated and tenant-scoped where applicable.
12. All architecture deviations must have an ADR.
