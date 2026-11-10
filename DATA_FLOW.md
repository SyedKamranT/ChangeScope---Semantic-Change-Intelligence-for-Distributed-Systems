# DATA_FLOW.md
## ChangeScope: Data Pipelines, Ingestion Flows & Projection Architecture

**Document Version:** 1.0.0  
**Status:** Approved Data Architecture  
**Author:** Principal Software Architect & Data Platform Engineer  

---

### Executive Summary

ChangeScope orchestrates five distinct, high-throughput data pipelines to bridge static source code, API/DB contracts, runtime observability, and graph projections. This document specifies the exact flow of data across systems, serialization formats, state transitions, and reconciliation checkpoints.

---

## 1. End-to-End Data Pipeline Architecture

```mermaid
flowchart TD
    subgraph IngestionSources ["Ingestion Sources"]
        SRC_GH["GitHub Pull Request Webhooks"]
        SRC_OTEL["OTel Collector (OTLP Traces)"]
        SRC_MIG["SQL DDL Migration Files"]
        SRC_OAS["OpenAPI / AsyncAPI Files"]
    end

    subgraph Pipeline1 ["Pipeline 1: Static Code & Contract Ingestion"]
        P1_WH["Webhook Verification & Ephemeral Clone"]
        P1_TS["Tree-sitter AST Symbol Extractor"]
        P1_OAS["Contract Canonicalizer & Normalizer"]
        P1_DDL["SQL DDL AST Parser (sqlglot)"]
    end

    subgraph Pipeline2 ["Pipeline 2: Runtime Evidence Aggregation"]
        P2_REC["OTLP Trace Receiver"]
        P2_SCRUB["PII Attribute Sanitizer"]
        P2_BUF["Redis Trace Buffer"]
        P2_AGG["Service Graph Aggregator"]
    end

    subgraph CanonicalStorage ["Canonical Persistence (PostgreSQL 17)"]
        PG_SCAN["scan_runs & raw_diffs"]
        PG_ENT["services, endpoints, schemas, tables"]
        PG_OUTBOX["outbox_events (Transactional Outbox)"]
        PG_DEP["runtime_dependencies"]
    end

    subgraph Pipeline3 ["Pipeline 3: Graph Projection (Neo4j)"]
        P3_OUT["Outbox Projection Worker"]
        P3_CYPHER["Batch Idempotent Cypher UPSERTs"]
        NEO_GRAPH[("Neo4j 5+ Software Knowledge Graph")]
    end

    subgraph Pipeline4 ["Pipeline 4: Reasoning & Impact Analysis"]
        P4_DIFF["Base vs Head Schema Diff Engine"]
        P4_RULES["Deterministic Semantic Rule Engine"]
        P4_BLAST["Cypher Multi-Hop Blast Radius Traversal"]
    end

    subgraph Pipeline5 ["Pipeline 5: Grounded Reporting & Feedback"]
        P5_LG["LangGraph Grounded Explainer"]
        P5_GUARD["Citation Verification Guard"]
        P5_GH["GitHub Checks API & PR Comments"]
        P5_UI["React 19 SPA (SSE Stream)"]
    end

    SRC_GH --> P1_WH
    P1_WH --> P1_TS
    SRC_OAS --> P1_OAS
    SRC_MIG --> P1_DDL

    P1_TS --> PG_SCAN
    P1_TS --> PG_ENT
    P1_OAS --> PG_ENT
    P1_DDL --> PG_ENT
    PG_ENT --> PG_OUTBOX

    SRC_OTEL --> P2_REC
    P2_REC --> P2_SCRUB
    P2_SCRUB --> P2_BUF
    P2_BUF --> P2_AGG
    P2_AGG --> PG_DEP
    PG_DEP --> PG_OUTBOX

    PG_OUTBOX --> P3_OUT
    P3_OUT --> P3_CYPHER
    P3_CYPHER --> NEO_GRAPH

    PG_SCAN --> P4_DIFF
    P4_DIFF --> P4_RULES
    P4_RULES --> P4_BLAST
    P4_BLAST <--> NEO_GRAPH

    P4_BLAST --> P5_LG
    P5_LG --> P5_GUARD
    P5_GUARD --> P5_GH
    P5_GUARD --> P5_UI
```

---

## 2. Pipeline 1: Static Code & Contract Ingestion Flow

### 2.1 Trigger & Ephemeral Lifecycle
1. GitHub delivers `pull_request.opened` or `pull_request.synchronize` payload with HMAC-SHA256 signature in header `X-Hub-Signature-256`.
2. The Gateway authenticates the webhook and enqueues a `RepoIngestTask` to Redis.
3. The Celery worker clones the repository to an isolated, in-memory directory: `/tmp/workspaces/{tenant_id}/{scan_id}` with `--depth=2` to fetch both `base_sha` and `head_sha`.
4. **Zero-Retention Guarantee:** Immediately upon completion of AST symbol and contract extraction, the entire tmpfs workspace is securely unlinked.

### 2.2 AST & Symbol Processing Flow
```mermaid
sequenceDiagram
    participant Worker as Ingestion Worker
    participant TS as Tree-sitter Parser
    participant PG as PostgreSQL 17

    Worker->>Worker: git diff --name-only base_sha head_sha
    loop For Each Changed Source File (.py, .ts, .js)
        Worker->>TS: Parse file CST into S-expression AST
        TS-->>Worker: Route Handlers, Endpoints, HTTP Calls, ORM Models
    end
    Worker->>PG: Batch INSERT INTO ast_symbols (file_path, line_range, symbol_type)
    Worker->>PG: Append to outbox_events (Type: AST_PARSED)
```

---

## 3. Pipeline 2: Runtime Evidence Ingestion Flow (OpenTelemetry)

### 3.1 Trace Ingestion & Sanitization
OpenTelemetry trace spans arrive via OTLP/HTTP or OTLP/gRPC at `/v1/traces`. To guarantee privacy and compliance, all spans pass through a high-throughput **PII Scrubbing Filter** prior to buffering:

```mermaid
flowchart LR
    OTLP["Raw OTLP Spans"] --> Filter{"PII Scrubber"}
    Filter -->|Sanitized Metadata| Buffer[("Redis Buffer List\notel:raw_spans")]
    Filter -->|Dropped/Redacted| Redact["Auth Headers, Tokens, Passwords, PII"]
    Buffer --> Aggregator["Aggregator Worker (60s Window)"]
    Aggregator --> PG[("PostgreSQL\nruntime_dependencies")]
```

### 3.2 Extracted Attributes
ChangeScope filters only for spans with network boundary semantics:
* `SPAN_KIND_SERVER`: Identifies provider endpoints.
  * Extracted: `service.name`, `http.route`, `http.request.method`, `http.response.status_code`, `rpc.method`.
* `SPAN_KIND_CLIENT`: Identifies consumer invocation calls.
  * Extracted: `service.name` (caller), `peer.service` (target), `url.path`, `http.status_code`.
* `SPAN_KIND_PRODUCER` / `SPAN_KIND_CONSUMER`: Identifies event stream messaging.
  * Extracted: `service.name`, `messaging.system` (Kafka, RabbitMQ), `messaging.destination.name`.

### 3.3 Aggregation Window & Upsert
Every 60 seconds, the Aggregator computes rolling 7-day metrics:
* $\text{Call Volume} = \sum \text{Spans in 7-day window}$
* $\text{p95 Latency} = \text{Percentile}_{95}(\text{duration\_ms})$
* Writes aggregated summary to `runtime_dependencies` and emits `TRACES_ENRICHED` outbox event.

---

## 4. Pipeline 3: Graph Outbox Reconciliation & Projection Flow

To satisfy the invariant that **PostgreSQL is canonical and Neo4j is a rebuildable projection**, all graph mutations pass through the transactional outbox:

```mermaid
sequenceDiagram
    autonumber
    participant App as Analysis Worker
    participant PG as PostgreSQL 17
    participant OutboxWorker as Celery Outbox Projector
    participant NEO as Neo4j Graph Database

    App->>PG: BEGIN TRANSACTION
    App->>PG: Update scan_runs & entities
    App->>PG: INSERT INTO outbox_events (aggregate_id, event_type, payload, status='PENDING')
    App->>PG: COMMIT

    loop Every 500ms (or on Redis Signal)
        OutboxWorker->>PG: SELECT * FROM outbox_events WHERE status = 'PENDING' FOR UPDATE SKIP LOCKED LIMIT 100
        OutboxWorker->>NEO: Execute Batch Parameterized Cypher MERGE Queries
        NEO-->>OutboxWorker: Projections Applied Successfully
        OutboxWorker->>PG: UPDATE outbox_events SET status = 'PROCESSED', processed_at = NOW() WHERE id IN (...)
    end
```

### 4.1 Sample Outbox Event Payload
```json
{
  "event_id": "c1f7b8e0-4a82-4f3e-9081-123456789abc",
  "tenant_id": "80084afc-fdd9-4b0f-8aca-cd5a2615bf86",
  "event_type": "SCAN_PROJECTION_PENDING",
  "payload": {
    "scan_id": "scan-9901",
    "service": {
      "id": "srv-inventory",
      "name": "inventory-service",
      "tier": "TIER_1"
    },
    "endpoints": [
      {
        "id": "ep-inv-check",
        "method": "POST",
        "path_template": "/api/v1/inventory/check",
        "request_schema_id": "sch-inv-req-v2",
        "response_schema_id": "sch-inv-res-v2"
      }
    ],
    "dependencies": [
      {
        "caller_service_id": "srv-checkout",
        "target_endpoint_id": "ep-inv-check",
        "provenance": "OTEL_TRACE",
        "confidence": 0.95,
        "is_observed": true,
        "call_count_7d": 845000,
        "p95_latency_ms": 32.4
      }
    ]
  }
}
```

---

## 5. Pipeline 4: Semantic Change Evaluation & Blast Radius Flow

```mermaid
flowchart TD
    Start["Diff Ingestion (Base vs Head)"] --> ASTDiff["Compute Contract & AST Diffs"]
    ASTDiff --> Rules["Execute Deterministic Semantic Rules"]
    
    subgraph RuleExecution ["Deterministic Checks"]
        R1["Check 1: Enum Narrowing"]
        R2["Check 2: Closed-World Collision"]
        R3["Check 3: Constraint Tightening"]
        R4["Check 4: Database DDL Incompatibility"]
        R5["Check 5: Default Value Shifts"]
    end
    
    Rules --> R1 & R2 & R3 & R4 & R5
    R1 & R2 & R3 & R4 & R5 --> Violations["Synthesize Violations List"]
    
    Violations --> NeoQuery["Execute Cypher Multi-Hop Blast Radius Query"]
    NeoQuery --> DAG["Compute Impacted Consumer DAG (1 to 5 Hops)"]
    DAG --> CalcScore["Compute Deterministic Blast Radius Score (0 - 100)"]
    CalcScore --> OutState["Emit VerifiedProofState to LangGraph"]
```

---

## 6. Pipeline 5: Grounded Reporting & Feedback Flow

```mermaid
sequenceDiagram
    autonumber
    participant Reason as Change Reasoning Engine
    participant LG as LangGraph StateMachine
    participant Guard as Citation Verification Guard
    participant GH as GitHub API (Checks & Comments)
    participant UI as React 19 Frontend (SSE)

    Reason->>LG: VerifiedProofState (Violations, Impacted Services, Node IDs, Trace IDs)
    LG->>LG: Generate Narrative Explanation with Structured Markdown
    LG->>Guard: Validate Synthesized Markdown
    
    alt Citations Contain Hallucinations
        Guard->>Guard: Citation Mismatch Detected! Reject LLM Markdown.
        Guard->>Guard: Render Deterministic Jinja2 Markdown Template
    else Citations Verified 100%
        Guard->>Guard: Citations Verified. Keep LLM Narrative.
    end

    Guard->>GH: POST /repos/.../check-runs (Annotate exact lines in PR)
    Guard->>GH: POST /repos/.../issues/.../comments (Markdown Impact Table)
    Guard->>UI: Emit SSE Event `scan:completed` with Blast Radius JSON
```
