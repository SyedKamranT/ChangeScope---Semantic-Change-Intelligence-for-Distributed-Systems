# ChangeScope: Semantic Change Intelligence for Distributed Systems

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![React 19](https://img.shields.io/badge/react-19.0.0-61dafb.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL 17](https://img.shields.io/badge/PostgreSQL-17-336791.svg)](https://www.postgresql.org/)
[![Neo4j 5.20](https://img.shields.io/badge/Neo4j-5.20+-008CC1.svg)](https://neo4j.com/)
[![Tests Passing](https://img.shields.io/badge/tests-240%2B%20offline%20suite-brightgreen.svg)]()
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

> **Mission:** Identify hidden technical dependencies, semantic contract violations, and operational blast radius before software changes reach production.

---

## Executive Overview

Modern engineering organizations run hundreds of distributed microservices across polyrepos. Despite unit tests, API linters, and APM tools, **outages still happen regularly**. The root cause is the **semantic blindspot**:
* **API Linters (`oasdiff`, Optic):** Inspect schemas in isolation; pass breaking changes as "compatible" (e.g., adding an optional field that crashes closed-world `additionalProperties: false` consumers, or changing default values and enum ranges).
* **Static Code Analyzers (Semgrep, CodeQL):** Great within a single repo; blind to network boundaries, message queues, and cross-repo downstream consumers.
* **Distributed Tracing (Datadog, Dynatrace):** Purely reactive; alerts only *after* broken code is deployed to production and customer traffic fails.
* **Contract Testing (Pact):** Massive manual friction; >85% of enterprise microservices lack maintained Pact contracts.

**ChangeScope solves this** by constructing a unified, queryable software knowledge graph linking **Git PR Diffs $\rightarrow$ Tree-sitter Code AST $\rightarrow$ OpenAPI/AsyncAPI Contracts $\rightarrow$ SQL DDL Migrations $\rightarrow$ OpenTelemetry Runtime Evidence $\rightarrow$ LangGraph Grounded Explanations**.

```
                      +-----------------------------+
                      |       GitHub Webhook /      |
                      |         Developer UI        |
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      |   FastAPI Gateway & MCP     |
                      +--------------+--------------+
                                     |
                                     v (Enqueues Tasks)
                      +-----------------------------+
                      |        Redis Queue          |
                      +--------------+--------------+
                                     |
                                     v
               +-------------------------------------------+
               |           ChangeScope Worker              |
               |                                           |
               |  +-------------------------------------+  |
               |  | 1. Git & AST Ingestion (Tree-sitter) |  |
               |  +-------------------------------------+  |
               |  | 2. Contract Engine (OAS / DDL)       |  |
               |  +-------------------------------------+  |
               |  | 3. OTel Trace Linker                 |  |
               |  +-------------------------------------+  |
               |  | 4. Semantic Rule Checker             |  |
               |  +-------------------------------------+  |
               |  | 5. LangGraph Evidence Synthesizer    |  |
               |  +-------------------------------------+  |
               +-------+--------------------+--------------+
                       |                    |
                       v                    v
              +-----------------+   +------------------+
              |    Neo4j LPG    |   |  PostgreSQL 17   |
              | (Software Graph)|   |  (Audit & State) |
              +-----------------+   +------------------+
```

---

## Architectural Invariants

1. **PostgreSQL 17 is Canonical:** All accounts, scans, raw diffs, and contracts are persisted in PostgreSQL.
2. **Neo4j is an Asynchronous, Rebuildable Projection:** Neo4j stores the Labeled Property Graph (LPG) for multi-hop graph traversal. Wiping Neo4j and replaying the outbox restores 100% parity.
3. **Transactional Outbox Pattern:** Graph mutations are written to `outbox_events` in the same database transaction as scan metadata, guaranteeing consistency.
4. **Strict Edge Provenance:** Every graph relationship requires verified `provenance` (`STATIC_AST`, `OTEL_TRACE`), `confidence` ($0.0 \le c \le 1.0$), and `evidence_ref`. No relationship may ever be created based on an LLM guess.
5. **Deterministic Ground Truth:** The Blast Radius Score ($0-100$) and semantic violations are calculated via deterministic algorithms. LLMs (via LangGraph) are strictly restricted to narrative formatting.
6. **Zero-Hallucination Citation Guard:** The LangGraph explainer enforces a strict citation guard; any hallucinated file path or trace ID is intercepted and replaced by a deterministic template.
7. **Zero-Source-Code-Retention Policy:** Clones live in ephemeral `tmpfs` RAM and are securely unlinked immediately after AST extraction.

---

## Approved Architectural Documentation

| Document | Description |
| :--- | :--- |
| [ARCHITECTURE.md](file:///c:/Users/unity/Downloads/ChangeScope---Semantic-Change-Intelligence-for-Distributed-Systems/ARCHITECTURE.md) | Platform architecture, invariants, modular monolith topology, and implementation milestones. |
| [HLD.md](file:///c:/Users/unity/Downloads/ChangeScope---Semantic-Change-Intelligence-for-Distributed-Systems/HLD.md) | High-Level Design: C4 diagrams, sequence diagrams, rebuildable graph projection, and trade-offs. |
| [LLD.md](file:///c:/Users/unity/Downloads/ChangeScope---Semantic-Change-Intelligence-for-Distributed-Systems/LLD.md) | Low-Level Design: PostgreSQL SQLAlchemy schema, Neo4j Cypher constraints, Tree-sitter S-expressions, and rule algorithms. |
| [DATA_FLOW.md](file:///c:/Users/unity/Downloads/ChangeScope---Semantic-Change-Intelligence-for-Distributed-Systems/DATA_FLOW.md) | 5 end-to-end data pipelines: static AST, OTel aggregation, outbox projection, blast radius, and reporting. |
| [SECURITY_ARCHITECTURE.md](file:///c:/Users/unity/Downloads/ChangeScope---Semantic-Change-Intelligence-for-Distributed-Systems/SECURITY_ARCHITECTURE.md) | STRIDE threat model, GitHub App JWT/HMAC auth, PostgreSQL RLS, tmpfs zero-retention, and PII scrubbing. |
| [ADR.md](file:///c:/Users/unity/Downloads/ChangeScope---Semantic-Change-Intelligence-for-Distributed-Systems/ADR.md) | 8 Architectural Decision Records detailing context, choices, alternatives rejected, and failure recovery. |
| [DEPLOYMENT_DESIGN.md](file:///c:/Users/unity/Downloads/ChangeScope---Semantic-Change-Intelligence-for-Distributed-Systems/DEPLOYMENT_DESIGN.md) | Docker Compose specification, production Kubernetes architecture, Celery worker concurrency, and metrics. |
| [API_DESIGN.md](file:///c:/Users/unity/Downloads/ChangeScope---Semantic-Change-Intelligence-for-Distributed-Systems/API_DESIGN.md) | OpenAPI 3.1 RESTful contracts and Model Context Protocol (MCP) tool interfaces. |
| [PRODUCT_REQUIREMENTS.md](file:///c:/Users/unity/Downloads/ChangeScope---Semantic-Change-Intelligence-for-Distributed-Systems/PRODUCT_REQUIREMENTS.md) | Complete PRD detailing requirements A through M with complexity and testability. |
| [COMPETITIVE_ANALYSIS.md](file:///c:/Users/unity/Downloads/ChangeScope---Semantic-Change-Intelligence-for-Distributed-Systems/COMPETITIVE_ANALYSIS.md) | Analysis across 5 competitor categories and formulation of the core industry problem. |
| [RESEARCH_REFERENCES.md](file:///c:/Users/unity/Downloads/ChangeScope---Semantic-Change-Intelligence-for-Distributed-Systems/RESEARCH_REFERENCES.md) | NVIDIA Auto Ontology inspection, specifications, and verified facts vs. engineering hypotheses. |
| [ASSUMPTIONS_AND_RISKS.md](file:///c:/Users/unity/Downloads/ChangeScope---Semantic-Change-Intelligence-for-Distributed-Systems/ASSUMPTIONS_AND_RISKS.md) | Technical risk matrix, mitigation strategies, and architectural guardrails. |
| [MVP_SCOPE.md](file:///c:/Users/unity/Downloads/ChangeScope---Semantic-Change-Intelligence-for-Distributed-Systems/MVP_SCOPE.md) | In-scope vs. out-of-scope boundaries, phased execution plan, and future roadmap. |

---

## Quickstart Guide

### 1. Run the End-to-End Pipeline Demo (CLI)
Experience the complete change-intelligence lifecycle (AST parsing, contract dereferencing, DDL parsing, semantic rule evaluation, blast radius calculation, LangGraph citation verification, and GitHub Checks annotation):
```powershell
.\.venv\Scripts\python.exe demo_pipeline.py
```

### 2. Run the Automated Test Suite (244+ Pytest + 11 Playwright E2E)
ChangeScope runs 100% offline without live external API keys:
```powershell
.\.venv\Scripts\pytest.exe -v tests/
```

### 3. Start the FastAPI Production Gateway
```powershell
.\.venv\Scripts\uvicorn.exe apps.api.main:app --host 0.0.0.0 --port 8000 --reload
```
* Interactive OpenAPI Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
* Liveness / Readiness Probes: [http://localhost:8000/health/live](http://localhost:8000/health/live), [http://localhost:8000/health/ready](http://localhost:8000/health/ready)

### 4. Start the React 19 Frontend Dashboard
```powershell
cd apps/web
pnpm dev
```
* Dashboard URL: [http://localhost:5173](http://localhost:5173)

### 5. Full Containerized Deployment (Docker Compose)
```powershell
docker compose -f infrastructure/docker/docker-compose.yml up -d
```
Spins up PostgreSQL 17, Neo4j 5.20 (with APOC), Redis 7, Celery Worker, FastAPI Gateway, and React 19 SPA.

---

## Model Context Protocol (MCP) Server

ChangeScope exposes an official MCP interface over JSON-RPC 2.0 at `/mcp` enabling AI agent harnesses (Claude Desktop, Cursor, LangChain) to query the knowledge graph with strict grounding:

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `query_blast_radius` | `endpoint_id: str`, `tenant_id: str` | Computes the multi-hop transitive DAG and deterministic risk score. |
| `search_services` | `query: str` | Searches registered microservices and their operational tiers. |
| `get_endpoint_dependencies` | `service_name: str`, `endpoint_path: str`, `method: str` | Returns direct static and observed runtime callers of an endpoint. |
| `explain_violation` | `violation_id: str` | Retrieves the cryptographic evidence chain for a semantic violation. |

---

## Technology Baseline

* **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (Async), Alembic, Pydantic v2, Structlog.
* **Storage:** PostgreSQL 17 (Canonical Source), Neo4j 5.20 (Rebuildable Graph Projection), Redis 7 (Queue & Cache).
* **Intelligence:** NVIDIA Auto Ontology MCP client, Custom Software Ontology, LangGraph StateGraph with Citation Guard.
* **Analysis:** Tree-sitter (Python, TypeScript, JavaScript), OpenAPI 3.1, `sqlglot` (SQL DDL), OpenTelemetry OTLP.
* **Frontend:** React 19, Vite 6, TypeScript, Tailwind CSS, TanStack Query, `@xyflow/react`.
* **Testing:** Pytest, pytest-asyncio, aiosqlite, Testcontainers.

---

## License

Distributed under the Apache 2.0 License. See `LICENSE` for details.
