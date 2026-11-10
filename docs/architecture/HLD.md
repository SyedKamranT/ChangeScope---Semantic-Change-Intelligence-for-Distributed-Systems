# HLD.md
## ChangeScope: High-Level Design (HLD)

**Document Version:** 1.0.0  
**Status:** Approved High-Level Architecture  
**Author:** Principal Software Architect & Staff Engineer  

---

### Executive Summary

This document presents the High-Level Design (HLD) of **ChangeScope**, illustrating the system context, container boundaries, component interactions, and end-to-end operational sequences. ChangeScope operates as a hybrid static-dynamic change intelligence platform where **PostgreSQL 17 serves as the canonical transaction store** and **Neo4j acts as an asynchronously synchronized, rebuildable graph projection**.

---

## 1. System Context Diagram (C4 Level 1)

The System Context diagram describes ChangeScope's boundaries and interactions with external actors, source control systems, and observability platforms.

```mermaid
flowchart TD
    User["Software Engineer / Tech Lead"]
    GH["GitHub / GitLab SCM\n(Webhooks & Pull Requests)"]
    OTelCollector["OpenTelemetry Collector\n(OTLP Traces)"]
    NVIDIA_MCP["NVIDIA Auto Ontology\n(MCP Semantic Grounding)"]

    subgraph ChangeScopeSystem ["ChangeScope Change Intelligence Platform"]
        CS["ChangeScope Core Platform\n(FastAPI Gateway, Celery Workers,\nPostgreSQL & Neo4j)"]
    end

    GH -->|1. Deliver PR Webhook Event| CS
    OTelCollector -->|2. Stream Runtime Trace Spans| CS
    User -->|3. View Dashboards & Blast Radius Graph| CS
    CS -->|4. Post GitHub Checks & PR Annotations| GH
    CS <-->|5. Semantic Layer Queries (MCP)| NVIDIA_MCP
    User -->|6. Review Pre-Merge Explanations| GH
```

---

## 2. Container Diagram (C4 Level 2)

The Container diagram details the high-level deployable units comprising the ChangeScope modular monolith:

```mermaid
flowchart TD
    subgraph ClientBoundary ["Client Layer"]
        SPA["Single Page App (React 19 + Vite)\nTailwind CSS, shadcn/ui, @xyflow/react"]
        SCM["GitHub / GitLab Webhook Dispatcher"]
        OTelAgent["OTel Ingestion Agent"]
    end

    subgraph ChangeScopePlatform ["ChangeScope Application Platform"]
        API["FastAPI Gateway & MCP Server\n(Python 3.12, Uvicorn, Port 8000)"]
        
        subgraph WorkerFleet ["Celery Worker Fleet (Python 3.12)"]
            W_Ingest["Worker: Ingestion & Static Parser\n(Tree-sitter, Git, OAS, DDL)"]
            W_Outbox["Worker: Graph Outbox Projector\n(Reconciliation & Neo4j Sync)"]
            W_Reason["Worker: Change Reasoning & Rules\n(Deterministic Rules & Blast Radius)"]
            W_Report["Worker: Reporting & LangGraph\n(Evidence Grounding & GitHub Checks)"]
        end

        RedisQueue[("Redis 7\n(Task Broker, Cache & Trace Buffer)")]
        PG[("PostgreSQL 17\n(Canonical Relational Database)")]
        NEO[("Neo4j 5+\n(Rebuildable Graph Projection)")]
        TmpFS["Ephemeral tmpfs Workspace\n(/tmp/changescope_workspaces)"]
    end

    SPA -->|REST API / SSE| API
    SCM -->|POST /api/v1/webhooks/github| API
    OTelAgent -->|POST /v1/traces (OTLP)| API

    API -->|Authenticate & Route| PG
    API -->|Enqueue Work Items| RedisQueue
    API -->|Direct Graph Reads for UI| NEO

    RedisQueue --> W_Ingest
    RedisQueue --> W_Outbox
    RedisQueue --> W_Reason
    RedisQueue --> W_Report

    W_Ingest -->|Shallow Git Clone / Parse| TmpFS
    W_Ingest -->|Write Commits, Diffs, Outbox| PG
    W_Outbox -->|Poll Outbox Events| PG
    W_Outbox -->|Apply Cypher Projections| NEO
    W_Reason -->|Read Diffs & Graph Topology| NEO
    W_Reason -->|Write Violations & Scores| PG
    W_Report -->|Fetch Evidence Chain| NEO
    W_Report -->|Post Annotations & Comments| SCM
```

---

## 3. Component Diagram (C4 Level 3)

The Component diagram breaks down the internal architecture of the FastAPI Gateway and the Celery Worker process, mapping the 11 Core Services into clear domain boundaries:

```mermaid
flowchart TD
    subgraph GatewayComponents ["FastAPI Gateway & MCP Server Process"]
        R_Auth["Auth & Tenant Router"]
        R_Webhooks["Webhook Ingestion Router"]
        R_OTLP["OTLP Receiver Router"]
        R_Graph["Graph & Impact Query Router"]
        MCP_Server["NVIDIA Auto Ontology MCP Client & Server"]
        
        MW_Tenant["Tenant Isolation Middleware"]
        MW_RateLimit["Rate Limiting Middleware"]
    end

    subgraph ServiceModules ["11 Core Service Modules"]
        S1["1. Identity & Workspace"]
        S2["2. Repo Ingestion"]
        S3["3. Static Analysis"]
        S4["4. Contract Analysis"]
        S5["5. Runtime Evidence"]
        S6["6. Ontology Provider"]
        S7["7. Knowledge Graph"]
        S8["8. Change Reasoning"]
        S9["9. Impact Analysis"]
        S10["10. Recommendation"]
        S11["11. Reporting Service"]
    end

    R_Auth --> S1
    R_Webhooks --> S2
    R_OTLP --> S5
    R_Graph --> S9
    MCP_Server --> S6

    S2 --> S3
    S2 --> S4
    S3 --> S7
    S4 --> S7
    S5 --> S7
    S6 --> S7
    S7 --> S8
    S8 --> S9
    S9 --> S10
    S10 --> S11
```

---

## 4. End-to-End Sequence Diagrams

### 4.1 Pull Request Change Analysis Sequence (Core Pipeline)
This sequence traces the complete execution lifecycle when a developer opens or updates a Pull Request on GitHub.

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer
    participant GH as GitHub API / Webhook
    participant API as FastAPI Gateway
    participant Q as Redis Queue
    participant W as Celery Worker Fleet
    participant PG as PostgreSQL 17 (Canonical)
    participant NEO as Neo4j (Graph Projection)
    participant LG as LangGraph Explainer

    Dev->>GH: Open / Update Pull Request (Base: main, Head: feature)
    GH->>API: POST /api/v1/webhooks/github (X-Hub-Signature-256)
    API->>API: Verify HMAC Signature & Extract PR Metadata
    API->>PG: Record Scan Execution (Status: PENDING)
    API->>Q: Enqueue ScanTask(scan_id, repo_id, base_sha, head_sha)
    API-->>GH: HTTP 202 Accepted (Check Run Queued)

    Q->>W: Dequeue ScanTask
    W->>PG: Update Scan Status: RUNNING
    W->>W: Ephemeral Git Shallow Clone to tmpfs (/tmp/workspace)
    W->>W: Tree-sitter AST Parse (Python / TypeScript Route Handlers & Clients)
    W->>W: Parse OpenAPI / AsyncAPI / DDL Migrations
    W->>PG: Commit Canonical Scan Entities & Append to outbox_events (Atomic TX)
    W->>W: Wipe tmpfs workspace directory cleanly

    W->>PG: Read outbox_events (IDEMPOTENT_GRAPH_SYNC)
    W->>NEO: Execute Batch Cypher Projections (UPSERT Nodes & Edges with Provenance)
    W->>PG: Mark outbox_events as PROCESSED

    W->>W: Execute Deterministic Change Reasoning Engine (Diff Evaluator)
    Note over W: Checks Enum Narrowing, additionalProperties: false,<br/>Regex Tightening, DDL Mutations
    W->>NEO: Execute Multi-Hop Blast Radius Traversal (Cypher)
    NEO-->>W: Return Impacted Consumer DAG & Trace Evidence
    W->>W: Compute Deterministic Risk Score (0 - 100)
    W->>PG: Persist Violations, Impact Paths, Risk Score

    W->>LG: Invoke LangGraph (Input: Verified Proof Chain IDs)
    LG->>NEO: Fetch Grounded Symbols & Trace IDs
    LG->>LG: Synthesize Markdown Explanations & Test Recommendations
    LG->>LG: Run Citation Verification Guard (Zero Hallucination Check)
    LG-->>W: Return Verified Narrative Report

    W->>GH: POST /repos/.../check-runs (Status: COMPLETED, Conclusion: ACTION_REQUIRED / SUCCESS)
    W->>GH: Add Inline Annotations (File, Line Range, Severity)
    W->>GH: POST PR Markdown Comment (Executive Summary Table)
    W->>PG: Update Scan Status: COMPLETED
```

---

### 4.2 Runtime Evidence Ingestion Sequence
This sequence details how OpenTelemetry trace spans are ingested, buffered, aggregated, and projected onto graph relationships:

```mermaid
sequenceDiagram
    autonumber
    participant App as Instrumented Microservice
    participant Collector as OTel Collector
    participant API as FastAPI OTLP Receiver
    participant Redis as Redis Trace Buffer
    participant AggWorker as Celery Aggregator Worker
    participant PG as PostgreSQL 17
    participant NEO as Neo4j Graph Projection

    App->>Collector: Send Trace Spans via OTLP (gRPC / HTTP)
    Collector->>API: POST /v1/traces (Protobuf / JSON)
    API->>API: Sanitize & Scrub PII from Span Attributes
    API->>Redis: LPUSH otel:raw_spans (Span Kind, http.route, peer.service, status_code)
    API-->>Collector: HTTP 200 OK

    loop Every 60 Seconds
        AggWorker->>Redis: RPOPLPUSH / Batch Read Spans
        AggWorker->>AggWorker: Aggregate Service-to-Service Calls (Frequency, p95 Latency)
        AggWorker->>PG: Upsert runtime_service_dependencies & outbox_events
        AggWorker->>NEO: Cypher UPSERT Edge: (c)-[:CALLS {is_observed: true, call_count, p95_latency}]->(p)
    end
```

---

### 4.3 Knowledge Graph Disaster Recovery & Full Rebuild Sequence
Demonstrating that **Neo4j is an asynchronously derived, 100% rebuildable projection**:

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Platform Admin / Disaster Recovery
    participant CLI as ChangeScope Admin CLI
    participant Rebuilder as Graph Rebuilder Service
    participant PG as PostgreSQL 17 (Canonical Source)
    participant NEO as Neo4j (Projection)

    Admin->>CLI: changescope-admin graph rebuild --tenant-id=<UUID>
    CLI->>Rebuilder: Trigger Rebuild Job
    Rebuilder->>NEO: MATCH (n {tenant_id: $tenant_id}) DETACH DELETE n
    Rebuilder->>NEO: Re-create Unique Constraints & Indices
    
    Rebuilder->>PG: Stream Services, Endpoints, Schemas, Tables for Tenant
    loop In Batches of 1,000 Nodes
        PG-->>Rebuilder: Entity Batch
        Rebuilder->>NEO: UNWIND Batch MERGE (n:Node ...)
    end

    Rebuilder->>PG: Stream Canonical Static Dependencies & Runtime Evidence
    loop In Batches of 5,000 Edges
        PG-->>Rebuilder: Edge Batch with Provenance & Timestamps
        Rebuilder->>NEO: UNWIND Batch MERGE (a)-[r:RELATIONSHIP]->(b)
    end

    Rebuilder-->>CLI: Graph Rebuild Complete (Nodes: X, Edges: Y, Parity: 100%)
```

---

## 5. Rebuildable Graph Projection & Outbox Architecture

### 5.1 Why Neo4j is a Projection (Not the Canonical Store)
1. **Transaction Integrity & Compliance:** Software governance requires ACID compliance, immutable audit logs, row-level tenant partitioning, and Point-in-Time Recovery (PITR). PostgreSQL provides enterprise-grade reliability, foreign key constraints, and mature backup tooling.
2. **Graph Optimization:** Neo4j excels at index-free adjacency and deep transitive traversals (`CALLS*1..5`). By treating Neo4j as an index projection, graph schema changes or corruption never endanger canonical data.
3. **Disaster Recovery:** If Neo4j becomes corrupt or out-of-sync, the entire graph can be rebuilt deterministically from PostgreSQL within minutes without data loss.

### 5.2 Transactional Outbox Pattern Details
Whenever a scan or trace aggregation modifies the canonical data in PostgreSQL:
1. **Single Transaction Boundary:**
   ```sql
   BEGIN TRANSACTION;
   -- 1. Insert or update scan results
   INSERT INTO scan_runs (...) VALUES (...);
   -- 2. Insert outbox projection event
   INSERT INTO outbox_events (id, tenant_id, event_type, payload, status)
   VALUES (gen_random_uuid(), 'tenant-123', 'SCAN_PROJECTION_PENDING', '{...}', 'PENDING');
   COMMIT;
   ```
2. **Asynchronous Projector:** A Celery worker polls pending outbox records with `SELECT ... FOR UPDATE SKIP LOCKED`, generates the corresponding Cypher statements, executes them within Neo4j transactions, and updates the outbox status to `PROCESSED`.
3. **Idempotent Cypher Mutations:** All projection Cypher queries utilize `MERGE` statements with deterministic composite keys (`tenant_id`, `id`) to ensure that replaying an outbox event produces zero duplicate nodes or relationships.

---

## 6. Alternatives Rejected & Architectural Trade-offs

| Architectural Decision | Alternative Considered | Why Rejected | Chosen Approach |
| :--- | :--- | :--- | :--- |
| **System Packaging** | Independent Microservices per Module (11 separate microservices) | **High Operational Overhead:** Increases network hops, distributed transaction complexity, serialization cost, and local developer setup friction. | **Modular Monolith:** Single deployable container fleet with strict Python package boundaries and shared relational connection pools. |
| **Primary Persistence** | Neo4j as Canonical Store | **Data Loss & ACID Risk:** Graph databases lack mature relational constraints, strict foreign keys, point-in-time backup tooling, and fine-grained row-level security. | **PostgreSQL 17 as Canonical Store; Neo4j as Rebuildable Projection.** |
| **AST Extraction** | Language Server Protocol (LSP) / Native Compilers | **Heavy & Fragile:** Requires full compiler toolchains, package installations (`npm install`, `pip install`), and memory-intensive LSP daemons in CI. | **Tree-sitter:** High-speed, fault-tolerant C/Wasm parsing in-memory without compiling or resolving dependencies. |
| **Risk Scoring** | LLM-Generated Risk Score (Prompting an LLM: "Rate this PR risk 1-100") | **Non-Deterministic & Hallucinatory:** Same PR receives different scores; cannot explain mathematical derivation; un-auditable. | **Deterministic Formula:** $R = \min(100, \text{Severity} \times (\text{Depth} + \log(\text{Volume})))$ with verified proof chains. |
| **Contract Ingestion** | Dynamic Traffic Recording Only | **Misses Inactive & Rare Paths:** Staging environments often lack traffic for edge-case endpoints; changes merge undetected. | **Hybrid Static-Dynamic:** Ingest static OpenAPI/AsyncAPI files first, enrich with live OTel spans. |
| **Agent Framework** | Autonomous ReAct Loop (AutoGPT style) | **Unpredictable Latency & Runaway Loops:** Agent may execute 50 iterative tool calls, blowing past the 60-second CI timeout. | **LangGraph StateGraph:** Deterministic acyclic/cyclical state machine with hard timeouts and strict grounding guards. |
