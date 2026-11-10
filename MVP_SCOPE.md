# MVP_SCOPE.md
## ChangeScope: Recommended MVP Scope, Phased Plan & Future Roadmap

**Document Version:** 1.0.0  
**Status:** Architecture Proposal & Scope Recommendation  
**Author:** Principal Software Architect, Staff Engineer & Technical Product Manager  

---

### Executive Summary

To achieve rapid time-to-value while delivering an undeniable competitive advantage, the **ChangeScope Minimum Viable Product (MVP)** is laser-focused on the highest-impact failure mode in modern software engineering: **detecting semantic contract violations between synchronous REST microservices, database migrations, and downstream consumers before Pull Requests merge**.

The MVP establishes the complete end-to-end loop:
$$\text{GitHub PR} \longrightarrow \text{Tree-sitter AST + OpenAPI + OTel} \longrightarrow \text{Neo4j Graph} \longrightarrow \text{Deterministic Semantic Engine} \longrightarrow \text{GitHub Check Annotations}$$

This document outlines the strict MVP boundaries, feature specifications, production deployment architecture, step-by-step implementation phases, and a future roadmap.

---

## 1. Scope Boundary: MVP vs. Future Roadmap

```
+-----------------------------------------------------------------------------------------+
|                                    SCOPE BOUNDARIES                                     |
+---------------------------------------------------+-------------------------------------+
|                  IN-SCOPE (MVP)                   |       OUT-OF-SCOPE (ROADMAP)        |
+---------------------------------------------------+-------------------------------------+
| • GitHub App Webhook Integration                  | • GitLab / Bitbucket / Azure DevOps |
| • Languages: Python & TypeScript/JavaScript       | • Languages: Go, Java, Rust, C#     |
| • Protocols: HTTP / REST (OpenAPI 3.0/3.1)       | • Async Protocols: Kafka / RabbitMQ |
| • Schemas: JSON Schema (Draft-07, 2020-12)        | • Protobuf / gRPC Wire Parsing      |
| • DB Migrations: SQL DDL (Alembic & Prisma)       | • NoSQL / Mongo / Cassandra drift   |
| • OpenTelemetry HTTP Spans (OTLP JSON/gRPC)       | • Real-time live production canaries|
| • Knowledge Graph: Neo4j LPG + Cypher             | • Automatic PR code auto-fixing     |
| • Semantic Rules: 5 Core Breaking Categories     | • Direct automated test runner      |
| • Blast Radius: Transitive multi-hop DAG          | • IDE Plugins (VS Code / JetBrains) |
| • GitHub Checks API + Markdown PR Comments        | • SOC2 Type II automated compliance |
| • Traceable Evidence Chain (PR -> AST -> OTel)    | • Self-hosted air-gapped bundles    |
+---------------------------------------------------+-------------------------------------+
```

---

## 2. MVP Feature Specifications

### Feature 1: Multi-Repo GitHub Ingestion & Webhook Handler
* **Description:** Fast, secure ingestion of PR events from GitHub via GitHub App. Performs shallow git diffs between base and head branches.
* **User Value:** Automated activation on every PR without manual developer CLI runs.
* **Implementation Complexity:** **Low-Medium**
* **Testability:** Mock webhook events and verify HMAC signature check, branch diff extraction, and job dispatching into task queue.

### Feature 2: Dual-Language AST Symbol & Route Extractor (Python & TypeScript)
* **Description:** Parses Python (FastAPI, Django, Flask) and TypeScript (Express, NestJS) using **Tree-sitter**. Extracts route definitions, URL path templates, HTTP methods, client invocation calls (`httpx`, `requests`, `axios`, `fetch`), and ORM entities (SQLAlchemy, Prisma).
* **User Value:** Zero developer configuration; extracts the technical structure directly from source code.
* **Implementation Complexity:** **Medium**
* **Testability:** Unit test suite with 40+ synthetic code snippets asserting extracted routes, line numbers, and client endpoints.

### Feature 3: API Contract & Database Migration Ingester
* **Description:** Ingests OpenAPI 3.0/3.1 files and SQL DDL migrations (Alembic Python files and Prisma SQL files). Normalizes parameters, response schemas, and altered table columns.
* **User Value:** Detects changes in declared interfaces and physical database schemas before code executes.
* **Implementation Complexity:** **Medium**
* **Testability:** Validate against real-world OpenAPI specs (Stripe, Petstore, GitHub API) and 30+ migration SQL scripts.

### Feature 4: OpenTelemetry HTTP Trace Span Aggregator
* **Description:** Ingests standard OTLP trace spans via HTTP/gRPC. Filters for `SPAN_KIND_CLIENT` and `SPAN_KIND_SERVER` containing `http.route`, `url.path`, and `http.response.status_code`. Computes rolling 7-day service call frequencies and links callers to provider endpoints.
* **User Value:** Grounds static code in empirical runtime truth, identifying real active consumers and unearthing undocumented callers.
* **Implementation Complexity:** **Medium**
* **Testability:** Ingest synthetic OTLP span JSON batches; verify aggregated edge counts and latency percentiles in Neo4j.

### Feature 5: Neo4j Software Engineering Knowledge Graph
* **Description:** Models nodes (`:Service`, `:Endpoint`, `:SchemaProperty`, `:DatabaseTable`, `:CodeSymbol`) and edges (`:EXPOSES`, `:CALLS`, `:MUTATES`, `:ASSUMES_CONTRACT`). Executes optimized Cypher queries for multi-hop blast radius traversals.
* **User Value:** Enables instant topological queries across the entire distributed microservice fleet.
* **Implementation Complexity:** **Medium**
* **Testability:** Integration tests executing Cypher queries against a Dockerized Neo4j test instance with seeded microservice topology.

### Feature 6: Deterministic Semantic Change Rule Engine
* **Description:** Analyzes diffs against downstream consumer models. Specifically flags:
  1. **Enum Narrowing:** Producer drops an enum value.
  2. **Closed-World Property Collision:** Producer adds optional property where consumer schema enforces `additionalProperties: false`.
  3. **Constraint Tightening:** Producer tightens regex `pattern` or adjusts `minimum`/`maximum`/`maxLength`.
  4. **Database Column Mutation:** DDL alters column type or adds `NOT NULL` without default on columns queried by downstream ORM entities.
  5. **Default Value Shift:** Producer changes parameter default affecting consumer query semantics.
* **User Value:** Eliminates the exact failure modes that cause silent production crashes.
* **Implementation Complexity:** **High**
* **Testability:** Comprehensive suite of unit test matrices testing every semantic violation case with guaranteed zero false negatives on verified contracts.

### Feature 7: Explainable Blast Radius & Evidence Grounding (LangGraph)
* **Description:** Calculates multi-hop impact graph in Neo4j. LangGraph agent takes deterministic graph proof nodes (PR line, AST symbol, OpenAPI property, OTel Span ID, consumer line) and synthesizes a concise, clear architectural explanation. Enforces a strict grounding validator that blocks hallucinated citations.
* **User Value:** Engineers get clear explanations of *why* their change is dangerous, backed by direct links to code and live trace IDs.
* **Implementation Complexity:** **High**
* **Testability:** Grounding evaluator asserting that 100% of generated file paths and span IDs in the output text match verified graph entities.

### Feature 8: GitHub Checks API & Actionable PR Reporter
* **Description:** Posts native GitHub Check Runs with precise inline annotations (error/warning on exact PR lines) and publishes an executive summary markdown comment detailing blast radius, affected services, and recommended regression test commands.
* **User Value:** Developers receive feedback in the pull request review interface within 60 seconds without leaving GitHub.
* **Implementation Complexity:** **Low**
* **Testability:** Mock GitHub Checks API; assert pagination handling (batches of 50 annotations) and markdown formatting.

---

## 3. Recommended Production Architecture (Modular Monolith)

To ensure high performance, maintainability, and operational simplicity, ChangeScope is structured as a **Modular Monolith**:

```
+---------------------------------------------------------------------------------------------------+
|                                     CHANGESCOPE PLATFORM                                          |
|                                                                                                   |
|  +---------------------------+   +----------------------------+   +----------------------------+  |
|  |     FastAPI Gateway       |   |       MCP Server           |   |       OTLP Receiver        |  |
|  |  • GitHub Webhooks        |   |  • Query Graph Tools       |   |  • OpenTelemetry Spans     |  |
|  |  • REST APIs & Auth       |   |  • Agent Context Provider  |   |  • Span Aggregator         |  |
|  +-------------+-------------+   +--------------+-------------+   +--------------+-------------+  |
|                |                                |                                |                |
|                +--------------------------------+--------------------------------+                |
|                                                 |                                                 |
|                                                 v                                                 |
|                                     +-----------------------+                                     |
|                                     |  Redis Task Queue     |                                     |
|                                     +-----------+-----------+                                     |
|                                                 |                                                 |
|                                                 v                                                 |
|  +---------------------------------------------------------------------------------------------+  |
|  |                                  Celery Worker Cluster                                      |  |
|  |                                                                                             |  |
|  |  [Module 1: Git Ingestion]          [Module 2: Tree-sitter Parser (Python & TS)]            |  |
|  |  [Module 3: Contract Parser (OAS)]   [Module 4: DDL Migration Parser (sqlglot)]              |  |
|  |  [Module 5: Semantic Rule Engine]   [Module 6: Blast Radius Calculator (Cypher)]            |  |
|  |  [Module 7: LangGraph Grounding]    [Module 8: GitHub Checks Dispatcher]                    |  |
|  +------------------------------+------------------------------------+-------------------------+  |
|                                 |                                    |                            |
+---------------------------------|------------------------------------|----------------------------+
                                  |                                    |
                                  v                                    v
                     +--------------------------+         +--------------------------+
                     |    Neo4j Database 5+     |         |     PostgreSQL 16        |
                     |  • Software LPG Graph    |         |  • Accounts & Auth       |
                     |  • Cypher Traversal      |         |  • GitHub Installations  |
                     |  • Blast Radius Index    |         |  • Audit & Run Logs      |
                     +--------------------------+         +--------------------------+
```

### Components:
1. **Application Runtime:** Python 3.12+ / FastAPI for webhooks, APIs, and Model Context Protocol (MCP) server.
2. **Worker & Queue:** Celery with Redis for asynchronous git fetching, parsing, and graph synchronizations.
3. **Graph Storage:** Neo4j 5.x Community or Enterprise edition for the software engineering ontology.
4. **Relational Storage:** PostgreSQL 16 for installation metadata, user accounts, and immutable audit logs.
5. **LLM Orchestration:** LangGraph with structured state graphs, utilizing any OpenAI-compatible or Anthropic API (or NVIDIA NIM Nemotron).

---

## 4. Phase-by-Phase MVP Execution Plan

```
Phase 1: Ontology & Graph Model (Weeks 1-2)
  └── Phase 2: Static Parsing & Contract Engine (Weeks 3-4)
        └── Phase 3: Runtime Trace Ingestion (Weeks 5-6)
              └── Phase 4: Semantic Change Rule Engine (Weeks 7-8)
                    └── Phase 5: Blast Radius & LangGraph Explainer (Weeks 9-10)
                          └── Phase 6: GitHub App & MVP E2E Validation (Weeks 11-12)
```

### Phase 1: Core Ontology & Graph Persistence
* Formalize Neo4j LPG schema (`Service`, `Endpoint`, `SchemaProperty`, `DatabaseTable`, `CodeSymbol`).
* Establish Cypher constraints, indexes, and database migration routines.
* Build internal graph repository service in Python using `neo4j-python-driver`.

### Phase 2: Static Code & Contract Ingestion Pipeline
* Implement Tree-sitter AST parser for Python (FastAPI, Flask, Django) and TypeScript (Express, NestJS).
* Implement OpenAPI 3.0/3.1 YAML/JSON resolver with `$ref` handling.
* Implement SQL DDL migration parser using `sqlglot` for Alembic and Prisma migrations.
* Integrate into Neo4j graph updater.

### Phase 3: OpenTelemetry Runtime Evidence Fusion
* Deploy OTLP trace receiver endpoint (`/v1/traces`).
* Build in-memory trace aggregator extracting caller-callee pairs, route templates, and call counts.
* Enrich existing Neo4j static graph edges with `last_observed` and `call_frequency` runtime properties.

### Phase 4: Deterministic Semantic Change Rule Engine
* Implement Git commit tree differ comparing PR branch against base branch.
* Build deterministic rule evaluator for:
  * Enum narrowing
  * `additionalProperties: false` conflict detection
  * Constraint tightening (regex, numeric range, string length)
  * Database column mutation & ORM incompatibility
* Generate structured `ViolationEvidence` records.

### Phase 5: Blast Radius Calculation & LangGraph Grounding
* Implement Cypher multi-hop graph traversal calculating transitive downstream consumers.
* Implement Blast Radius Scoring algorithm (0-100 scale).
* Build LangGraph state machine to synthesize human-readable explanations strictly grounded by verified graph node IDs.
* Implement Citation Verification guard to eliminate hallucinations.

### Phase 6: GitHub App Integration & End-to-End Validation
* Package GitHub App with webhook event listeners (`pull_request.opened`, `pull_request.synchronize`).
* Implement GitHub Checks API publisher posting inline annotations and PR summary comment.
* Validate on a live 5-repository distributed microservice testbed.

---

## 5. Future Product Roadmap

### Version 1.1: Asynchronous Event-Driven Architecture Expansion
* **AsyncAPI v2 & v3 Deep Support:** Ingest AsyncAPI event specifications across Kafka, RabbitMQ, and AWS SQS/SNS.
* **Message Payload Schema Validation:** Detect event schema breaking changes across asynchronous decoupled workers.
* **Dead Letter Queue (DLQ) Risk Modeling:** Alert when consumer lacks a DLQ for potentially unprocessable event schemas.

### Version 1.5: Automated Targeted Regression Testing
* **Targeted Test Runner Dispatcher:** Automatically trigger GitHub Actions workflow dispatches running *only* the affected downstream test suites.
* **Synthetic Test Stub Generation:** Generate runnable Pytest / Jest test stubs that downstream teams can execute to verify compatibility against proposed upstream changes.

### Version 2.0: Continuous Intelligence & Self-Hosted Enterprise
* **Live Production Canary Monitoring:** Continuously compare live canary OTel traces against baseline graph to detect real-time semantic drift post-deployment.
* **Continuous Contract Synthesis:** Automatically reverse-engineer OpenAPI and AsyncAPI contracts from pure runtime traffic when repositories lack formal specs.
* **Self-Hosted Enterprise Distribution:** Single-tenant Helm charts supporting air-gapped VPCs, SAML/SSO, and native AWS Secrets Manager / HashiCorp Vault integrations.

---

## 6. MVP Success Criteria & Review Gate

The MVP will be considered successful and production-ready when it achieves:
1. **Turnaround Time:** $< 60$ seconds total processing time from PR webhook to GitHub Check Run completion.
2. **Detection Recall:** $100\%$ detection of verified breaking semantic changes (enum narrowing, `additionalProperties: false` collision, DDL column type reduction) on benchmark testbeds.
3. **Zero False Hallucinations:** $100\%$ of links, line numbers, and trace citations in the generated report resolve to real repository lines and OTel traces.
4. **Developer Adoption:** Clean, unobtrusive GitHub Checks UI with clear explainability, eliminating developer resistance.

> [!IMPORTANT]
> **Implementation Review Gate:** In accordance with user instructions, no production or prototype code will be written until this research, competitive analysis, product requirements, risk matrix, and MVP scope are reviewed and approved.
