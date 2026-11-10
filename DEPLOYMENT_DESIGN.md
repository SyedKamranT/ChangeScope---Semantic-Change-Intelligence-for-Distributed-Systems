# DEPLOYMENT_DESIGN.md
## ChangeScope: Deployment Architecture, Local Docker Compose & Kubernetes

**Document Version:** 1.0.0  
**Status:** Approved Deployment Architecture  
**Author:** Principal Infrastructure Architect & Staff SRE  

---

### Executive Summary

ChangeScope is designed for seamless portability between **zero-friction local development (Docker Compose)** and **high-availability production environments (Kubernetes / Managed Cloud)**. The deployment architecture guarantees high throughput, horizontal worker scaling via KEDA, sub-second failure recovery, and comprehensive self-instrumented observability.

---

## 1. Local Development Environment (Docker Compose)

The entire ChangeScope platform runs locally with a single command:
```bash
docker compose up -d
```

```mermaid
flowchart TD
    subgraph HostPorts ["Host Port Mappings"]
        P_UI["Port 5173: Frontend (React 19 SPA)"]
        P_API["Port 8000: FastAPI Gateway & MCP"]
        P_NEO_HTTP["Port 7474: Neo4j Browser"]
        P_NEO_BOLT["Port 7687: Neo4j Bolt"]
        P_PG["Port 5432: PostgreSQL 17"]
        P_REDIS["Port 6379: Redis 7"]
    end

    subgraph ComposeNetwork ["Docker Compose Bridge Network (changescope-net)"]
        FE["frontend: React 19 + Vite"]
        API["api: FastAPI + Uvicorn"]
        WORKER["worker: Celery Worker Fleet"]
        PG[("postgres: PostgreSQL 17")]
        NEO[("neo4j: Neo4j 5.20 (APOC Enabled)")]
        REDIS[("redis: Redis 7 (Alpine)")]
    end

    P_UI --> FE
    P_API --> API
    P_NEO_HTTP --> NEO
    P_NEO_BOLT --> NEO
    P_PG --> PG
    P_REDIS --> REDIS

    FE -->|Proxy /api| API
    API --> PG
    API --> NEO
    API --> REDIS
    WORKER --> PG
    WORKER --> NEO
    WORKER --> REDIS
```

### 1.1 Complete Local `docker-compose.yml` Specification

```yaml
version: "3.9"

networks:
  changescope-net:
    driver: bridge

volumes:
  pg_data:
  neo4j_data:
  neo4j_logs:
  redis_data:

services:
  postgres:
    image: postgres:17-alpine
    container_name: changescope-postgres
    networks:
      - changescope-net
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: changescope_dev
      POSTGRES_USER: changescope_user
      POSTGRES_PASSWORD: changescope_password
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U changescope_user -d changescope_dev"]
      interval: 5s
      timeout: 5s
      retries: 5

  neo4j:
    image: neo4j:5.20.0-community
    container_name: changescope-neo4j
    networks:
      - changescope-net
    ports:
      - "7474:7474" # HTTP Browser
      - "7687:7687" # Bolt Protocol
    environment:
      NEO4J_AUTH: neo4j/changescope_password
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_dbms_security_procedures_unrestricted: apoc.*
      NEO4J_server_memory_heap_initial__size: 512m
      NEO4J_server_memory_heap_max__size: 1G
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
    healthcheck:
      test: ["CMD-SHELL", "cypher-shell -u neo4j -p changescope_password 'RETURN 1' || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: changescope-redis
    networks:
      - changescope-net
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  api:
    build:
      context: ../backend
      dockerfile: ../docker/Dockerfile.backend
    container_name: changescope-api
    networks:
      - changescope-net
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://changescope_user:changescope_password@postgres:5432/changescope_dev
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: changescope_password
      REDIS_URL: redis://redis:6379/0
      ENVIRONMENT: local
    depends_on:
      postgres:
        condition: service_healthy
      neo4j:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn changescope.main:app --host 0.0.0.0 --port 8000 --reload

  worker:
    build:
      context: ../backend
      dockerfile: ../docker/Dockerfile.backend
    container_name: changescope-worker
    networks:
      - changescope-net
    environment:
      DATABASE_URL: postgresql+asyncpg://changescope_user:changescope_password@postgres:5432/changescope_dev
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: changescope_password
      REDIS_URL: redis://redis:6379/0
      ENVIRONMENT: local
    depends_on:
      postgres:
        condition: service_healthy
      neo4j:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A changescope.workers.app worker --loglevel=info -Q scans,outbox,otel,default --concurrency=4

  frontend:
    build:
      context: ../frontend
      dockerfile: ../docker/Dockerfile.frontend
    container_name: changescope-frontend
    networks:
      - changescope-net
    ports:
      - "5173:5173"
    environment:
      VITE_API_URL: http://localhost:8000
    depends_on:
      - api
```

---

## 2. Production Kubernetes Architecture

In enterprise production deployments, the modular monolith deploys as horizontally scalable container workloads on Kubernetes:

```mermaid
flowchart TD
    Ingress["Kubernetes Ingress (NGINX / AWS ALB)\nTLS Termination via cert-manager"]
    
    subgraph K8sCluster ["ChangeScope Production Kubernetes Namespace"]
        subgraph GatewayPods ["FastAPI Gateway Deployment (Stateless)"]
            GW1["Gateway Pod 1"]
            GW2["Gateway Pod 2"]
            GW3["Gateway Pod N (HPA Scaled)"]
        end

        subgraph CeleryPods ["Celery Worker Deployment (KEDA Scaled)"]
            W_Scan["Scan Workers (Queue: scans)"]
            W_Outbox["Outbox Workers (Queue: outbox)"]
            W_OTel["Trace Aggregators (Queue: otel)"]
        end

        KEDA["KEDA Autoscaler\n(Monitors Redis Queue Lengths)"]
    end

    subgraph ManagedDataPlane ["Managed Cloud Persistence Tier"]
        RDS[("Amazon Aurora PostgreSQL 17\n(Multi-AZ with Read Replicas)")]
        AuraDB[("Neo4j Enterprise / AuraDB\n(Clustered Graph Engine)")]
        ElastiCache[("Redis 7 Cluster\n(In-Memory Broker & Cache)")]
    end

    Ingress --> GW1 & GW2 & GW3
    GW1 & GW2 & GW3 --> ElastiCache
    GW1 & GW2 & GW3 --> RDS
    GW1 & GW2 & GW3 --> AuraDB

    ElastiCache --> W_Scan & W_Outbox & W_OTel
    KEDA -->|Scale Workers on Queue Depth| CeleryPods

    W_Scan --> RDS
    W_Outbox --> AuraDB
    W_Outbox --> RDS
    W_OTel --> RDS
    W_OTel --> AuraDB
```

---

## 3. Worker Concurrency & Queue Topology

To prevent long-running repository clones from starving fast outbox graph updates or OTel telemetry batches, the Celery worker fleet is split into **dedicated priority queues**:

| Queue Name | Primary Task Types | Concurrency Model | Autoscaling Metric (KEDA) | Failure Policy |
| :--- | :--- | :--- | :--- | :--- |
| `scans` | Git shallow clones, Tree-sitter AST parsing, schema diffing | Multi-process (`fork`, concurrency: 4 per pod) | Scale when queue depth $> 5$ | 3 retries, exponential backoff (10s, 30s, 90s) |
| `outbox` | Polling `outbox_events` and executing batch Cypher MERGEs in Neo4j | Multi-threaded (`gevent` or `threads`, concurrency: 8) | Scale when outbox lag $> 500$ events | 5 retries; dead-letter to `outbox_dlq` on syntax error |
| `otel` | Ingestion of raw OTLP spans, 60-second window aggregations | Memory-optimized process | Scale on Redis buffer length $> 10,000$ | Drop invalid protobuf, preserve valid aggregates |
| `reports` | LangGraph reasoning, GitHub Checks API posting, PR comments | Async I/O worker (`asyncio`) | Scale on queue depth $> 10$ | 3 retries with jitter |

### 3.1 Worker Reliability Invariant: Late Acknowledgement
All Celery tasks enforce `acks_late=True` and `reject_on_worker_lost=True`. If a worker pod is killed by the Kubernetes OOM killer during a scan, the task is immediately re-queued and reassigned to an available worker.

---

## 4. Observability & Health Architecture

ChangeScope instruments itself using the OpenTelemetry Python SDK and exposes native Prometheus metrics:

```mermaid
flowchart LR
    API["ChangeScope Gateway / Workers"] -->|/metrics (Scrape)| Prom["Prometheus Server"]
    API -->|OTLP Traces| Jaeger["OpenTelemetry Collector / Jaeger"]
    API -->|JSON Logs| Loki["Grafana Loki / CloudWatch"]
    Prom --> Grafana["Grafana Operational Dashboard"]
    Jaeger --> Grafana
    Loki --> Grafana
```

### 4.1 Golden Signals & Key Metrics
* `changescope_pr_scans_total{status="completed|failed"}`: Counter of total scans.
* `changescope_scan_duration_seconds`: Histogram of end-to-end PR processing turnaround (P95 SLA: $<60$s).
* `changescope_outbox_lag_count`: Gauge of unprocessed outbox events awaiting Neo4j projection.
* `changescope_violations_detected_total{rule_code, severity}`: Counter of breaking contract changes flagged.
* `changescope_neo4j_query_duration_seconds{query="blast_radius"}`: Latency histogram for Cypher multi-hop traversals.

### 4.2 Health Endpoints
* **Liveness (`GET /health/live`):** Returns HTTP 200 if the FastAPI application process is responsive.
* **Readiness (`GET /health/ready`):** Returns HTTP 200 only if PostgreSQL, Neo4j, and Redis connections are active and responsive. If Neo4j is temporarily reconnecting, returns HTTP 503 to prevent Kubernetes traffic routing.

---

## 5. Failure Recovery & Self-Healing Scenarios

| Failure Scenario | Immediate Detection Mechanism | Self-Healing & Recovery Action |
| :--- | :--- | :--- |
| **Worker OOM during Git Clone** | Celery worker process terminates abruptly; Redis task heartbeats fail. | Task is rejected back to Redis (`reject_on_worker_lost=True`); another worker picks it up; task logs flag oversized repository for admin review. |
| **Neo4j Graph Database Disconnection** | Cypher execution throws `ServiceUnavailable` or `SessionExpired`. | Outbox projector pauses execution; outbox events remain safely buffered in PostgreSQL `outbox_events`; projector retries with exponential backoff until Neo4j recovers. |
| **GitHub API Rate Limiting (HTTP 403 / 429)** | GitHub Checks publisher receives `x-ratelimit-remaining: 0`. | Worker pauses task execution and schedules a delayed Celery retry based on the `x-ratelimit-reset` epoch header. |
| **Corrupted Graph Projection** | Administrator or data auditor reports graph topological discrepancies. | Operator triggers `changescope graph rebuild --tenant-id=<UUID>` to re-project the entire graph cleanly from PostgreSQL in < 60s. |
