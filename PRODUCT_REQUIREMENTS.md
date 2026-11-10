# PRODUCT_REQUIREMENTS.md
## ChangeScope: Semantic Change Intelligence for Distributed Systems
### Comprehensive Product Requirements Document (PRD)

**Document Version:** 1.0.0  
**Status:** Architecture & Product Specification  
**Author:** Principal Software Architect, Staff Engineer, Ontology Engineer & Technical Product Manager  

---

## 1. Vision & Core Mission

### 1.1 Mission Statement
ChangeScope identifies hidden technical dependencies, semantic contract violations, and operational blast radius before software changes reach production.

### 1.2 The Core Persona & Value Proposition
* **Staff Engineers & Architects:** Gain automated, real-time visibility into cross-repo distributed service topologies without manual catalog curation.
* **Feature Developers:** Receive instant, actionable feedback in GitHub PRs pinpointing exact lines where changes break downstream consumers, preventing high-severity production incidents.
* **Release Managers & SREs:** Eliminate production release anxiety by reviewing auditable change-impact reports and executing only targeted regression suites.

---

## 2. Core Functional Requirements (A through M)

For each requirement, we specify:
1. **Functional Specification**
2. **User Value**
3. **Implementation Complexity & Technical Rationale**
4. **Testability & Verification Strategy**

---

### Requirement A: Multi-Repository Ingestion
* **Functional Specification:**
  * Connect to GitHub organizations via a GitHub App with fine-grained permissions (`Contents: Read`, `Pull Requests: Read/Write`, `Checks: Read/Write`).
  * Support cloning and incremental synchronization of multiple polyrepo repositories and monorepos.
  * Maintain repository metadata: commit hashes, branch heads, repository ownership, primary language stacks, and dependency manifests.
* **User Value:** Organizations with 10 to 500+ microservice repositories gain a unified change-intelligence system without restructuring their codebases into monorepos.
* **Implementation Complexity:** **Medium**
  * *Rationale:* Requires robust Git cloning/shallow fetching, webhook signature validation (`X-Hub-Signature-256`), rate-limit backoff handling, and workspace sandboxing.
* **Testability:**
  * *Unit:* Mock GitHub webhook payloads, verify cryptographic signature verification and event deserialization.
  * *Integration:* Test shallow git cloning and incremental tree diffing against a local Git bare repository.
  * *E2E:* Simulate concurrent webhook deliveries across three simulated repositories.

---

### Requirement B: Multi-Language Code Parsing (Python & TypeScript/JavaScript)
* **Functional Specification:**
  * Utilize **Tree-sitter** C/Wasm bindings (`tree-sitter-python`, `tree-sitter-typescript`, `tree-sitter-javascript`) to parse Concrete Syntax Trees (CST) and ASTs.
  * Extract:
    1. **Route Handlers / Entrypoints:** FastAPI (`@app.get`, `@router.post`), Express (`app.get`, `router.post`), NestJS (`@Controller`, `@Get`), Django (`urls.py`).
    2. **HTTP Clients:** `requests`, `httpx`, `aiohttp`, `fetch`, `axios`, `got`.
    3. **Event Producers/Consumers:** Kafka (`confluent_kafka`, `kafkajs`), RabbitMQ/AMQP (`pika`, `amqplib`), AWS SDK (`boto3.sns`, `@aws-sdk/client-sns`).
    4. **ORM Models & DB Clients:** SQLAlchemy, Prisma, TypeORM, raw SQL strings.
  * Resolve symbols to file paths and line ranges.
* **User Value:** Zero developer configuration. Automatically parses code patterns without requiring language compilers, containerized environments, or heavy language server protocols (LSP).
* **Implementation Complexity:** **Medium**
  * *Rationale:* Tree-sitter grammars are fast and resilient to syntax errors, but extracting dynamic route patterns (e.g., string concatenations or helper wrappers) requires robust S-expression pattern matching.
* **Testability:**
  * *Unit:* Test Tree-sitter S-expression queries against synthetic Python and TypeScript code snippets covering all target frameworks.
  * *Integration:* Parse open-source enterprise codebases (e.g., FastAPI realworld example, NestJS microservice demo) and verify >95% route and client extraction recall.

---

### Requirement C: API Contract Ingestion (OpenAPI, AsyncAPI & JSON Schema)
* **Functional Specification:**
  * Ingest OpenAPI Specification (OAS 3.0.x and 3.1.x) in YAML and JSON formats.
  * Ingest AsyncAPI Specification (v2.x and v3.x) in YAML and JSON formats.
  * Ingest standalone JSON Schema (Draft-07, Draft 2019-09, Draft 2020-12).
  * Build an internal canonical schema model representing:
    * Paths, methods, parameters (path, query, header), request bodies, response codes, and schemas.
    * Async channels, operations (publish, subscribe), message headers, and payload schemas.
    * Constraint bounds: `type`, `format`, `enum`, `minimum`, `maximum`, `pattern`, `required`, `additionalProperties`.
* **User Value:** Unifies synchronous REST APIs, asynchronous event streams, and validation schemas under a single contract reasoning engine.
* **Implementation Complexity:** **Medium**
  * *Rationale:* OpenAPI 3.1 integrates JSON Schema 2020-12, requiring resolution of `$ref` pointers (internal and external file references) and circular references.
* **Testability:**
  * *Unit:* Parse canonical OpenAPI and AsyncAPI reference test suites; verify schema resolution and circular ref handling.
  * *Integration:* Diff synthetically modified specs (e.g., OAS 3.0 vs 3.1) and ensure property normalization.

---

### Requirement D: Database Migration Ingestion
* **Functional Specification:**
  * Ingest versioned SQL DDL migration files across major migration frameworks:
    * Python: **Alembic** (`versions/*.py`)
    * TypeScript/Node: **Prisma** (`migrations/*/migration.sql`), **TypeORM** (`migrations/*.ts`)
    * Universal: **Flyway** (`V*__*.sql`), **Liquibase** (XML/YAML/SQL DDL).
  * Parse SQL DDL statements: `CREATE TABLE`, `ALTER TABLE`, `ADD COLUMN`, `DROP COLUMN`, `RENAME COLUMN`, `ALTER COLUMN TYPE`, `ADD CONSTRAINT` (Foreign Key, Not Null, Unique, Check).
  * Map modified database tables and columns to application ORM entities extracted in Requirement B.
* **User Value:** Bridges the classic operational gap where database schema changes break application microservices reading from shared or replicated databases.
* **Implementation Complexity:** **Medium**
  * *Rationale:* SQL DDL varies across dialects (PostgreSQL, MySQL). Utilizing a dedicated SQL AST parser (such as `sqlglot`) enables dialect-agnostic parsing of DDL modifications.
* **Testability:**
  * *Unit:* Parse 50+ diverse DDL migration scripts covering column renames, type changes, constraint additions, and drops across Postgres and MySQL dialects.
  * *Integration:* Verify that an Alembic DDL column change correctly updates the corresponding database entity node in the graph.

---

### Requirement E: Static Dependency Extraction
* **Functional Specification:**
  * Construct intra-service and inter-service static dependency graphs:
    * Link HTTP client calls (`POST /api/v1/payments`) to known provider route handlers.
    * Link event publisher calls (`kafka.send("orders.created")`) to subscriber listeners (`@KafkaListener("orders.created")`).
    * Link ORM queries (`User.query.filter_by(...)`) to database table nodes.
  * Account for base URL configurations, environment variables, and route prefixes.
* **User Value:** Maps the intended technical wiring of distributed applications directly from the source code.
* **Implementation Complexity:** **High**
  * *Rationale:* Static analysis alone struggles with dynamic route generation (e.g., `url = f"{BASE_URL}/{resource_id}"`). Requires fallback heuristic resolution and string interpolation normalization.
* **Testability:**
  * *Unit:* Test URL path normalization algorithms (`/users/{id}` vs `/users/:id` vs `/users/{userId}`).
  * *Integration:* Run static dependency extraction on a multi-repo testbed; verify edge creation between client and server repositories.

---

### Requirement F: OpenTelemetry Runtime Evidence Ingestion
* **Functional Specification:**
  * Expose an OpenTelemetry Protocol (OTLP/gRPC and OTLP/HTTP) receiver endpoint or ingest traces from storage (ClickHouse, Jaeger, Elasticsearch).
  * Extract and aggregate trace span relationships:
    * `SPAN_KIND_CLIENT` $\rightarrow$ `SPAN_KIND_SERVER` (Caller service $\rightarrow$ Callee service, URL route, HTTP status code, call volume, error rate).
    * `SPAN_KIND_PRODUCER` $\rightarrow$ `SPAN_KIND_CONSUMER` (Publishing service $\rightarrow$ Message topic $\rightarrow$ Consuming service).
  * Annotate static graph edges with empirical runtime metrics:
    * `last_observed_timestamp`
    * `p95_latency_ms`
    * `call_frequency_per_minute`
    * `observed_payload_keys`
* **User Value:** Turns theoretical static code links into proven runtime reality. Eliminates false positives on dead code and catches dynamic calls invisible to static analysis.
* **Implementation Complexity:** **Medium**
  * *Rationale:* OTLP specifications are well-defined. High trace volume requires an aggregation worker that processes spans in memory or reads pre-aggregated service graph metrics rather than storing raw trace dumps.
* **Testability:**
  * *Unit:* Ingest synthetic OTLP span batches containing HTTP and messaging spans; verify extracted attributes and metrics aggregation.
  * *Integration:* Stream spans from a live OpenTelemetry demo application and verify graph edge enrichment in Neo4j.

---

### Requirement G: Software Engineering Ontology Model
* **Functional Specification:**
  * Formalize an explicit software engineering ontology stored in **Neo4j** as a Labeled Property Graph (LPG).
  * **Entity Nodes:**
    * `:Service` (id, name, repo_url, tier, owner)
    * `:Endpoint` (id, method, path_template, protocol)
    * `:Operation` (id, operation_id, type)
    * `:Schema` (id, name, version, format, validation_mode)
    * `:SchemaProperty` (id, name, type, format, required, enum_values, default_value, constraints)
    * `:MessageChannel` (id, name, system, routing_key)
    * `:DatabaseTable` (id, schema_name, table_name)
    * `:DatabaseColumn` (id, name, data_type, is_nullable, is_unique)
    * `:CodeSymbol` (id, file_path, start_line, end_line, symbol_type, name)
    * `:MigrationScript` (id, version, filename, dialect)
  * **Relationship Edges:**
    * `(:Service)-[:EXPOSES]->(:Endpoint)`
    * `(:Endpoint)-[:ACCEPTS_SCHEMA]->(:Schema)`
    * `(:Endpoint)-[:RETURNS_SCHEMA]->(:Schema)`
    * `(:Service)-[:CALLS {frequency, p95_latency, static_source_line}]->(:Endpoint)`
    * `(:Service)-[:PUBLISHES_TO]->(:MessageChannel)`
    * `(:Service)-[:SUBSCRIBES_TO]->(:MessageChannel)`
    * `(:CodeSymbol)-[:IMPLEMENTS]->(:Endpoint)`
    * `(:CodeSymbol)-[:INVOKES_CLIENT]->(:Endpoint)`
    * `(:CodeSymbol)-[:QUERIES]->(:DatabaseTable)`
    * `(:MigrationScript)-[:MUTATES]->(:DatabaseTable)`
    * `(:Schema)-[:CONTAINS_PROPERTY]->(:SchemaProperty)`
    * `(:ConsumerService)-[:ASSUMES_CONTRACT {validation_mode}]->(:Schema)`
* **User Value:** Provides a mathematically rigorous, queryable graph representation of the entire software ecosystem that can be inspected via Cypher or Model Context Protocol (MCP).
* **Implementation Complexity:** **Medium**
  * *Rationale:* Designing the ontology schema requires rigorous semantic boundaries to ensure graph queries remain sub-second without node explosion.
* **Testability:**
  * *Unit:* Validate Cypher schema constraints, uniqueness constraints, and index creations.
  * *Integration:* Execute standard graph queries (`find_consumers_of_endpoint`, `trace_database_dependents`) and verify query execution plans and performance.

---

### Requirement H: Semantic Change Detection (Structurally Compatible yet Dangerous)
* **Functional Specification:**
  * Implement a deterministic rule engine analyzing differences between Git Base (target branch) and Git Head (PR branch).
  * Evaluate the following semantic failure modes:
    1. **Enum Narrowing:** Producer removes an allowable value from an enum.
    2. **Optional Field Addition with Closed-World Consumer:** Producer adds an optional property where a consumer schema enforces `additionalProperties: false` or `unevaluatedProperties: false`.
    3. **Constraint Tightening:** Producer increases `minimum`, decreases `maximum`, increases `minLength`, or restricts a `pattern` (regex).
    4. **Default Value Shifting:** Producer changes default value of an optional parameter or payload field.
    5. **Type Mutation / Widening on Consumer:** Consumer narrows expected type while producer widens.
    6. **Status Code Drift:** Changing HTTP response code semantics (e.g. `200` with empty body to `204`, or `400 Bad Request` to `422 Unprocessable Entity`).
    7. **Database Column Mutation:** DDL alters column size (e.g. `VARCHAR(64)` $\rightarrow$ `VARCHAR(32)`), adds `NOT NULL` without default, or drops a column still referenced in a downstream service's ORM model.
* **User Value:** Eliminates the "silent killers" of distributed systems that pass standard linters and unit tests but detonate at runtime.
* **Implementation Complexity:** **High**
  * *Rationale:* Requires pairing producer diffs with consumer validation schemas and AST ORM mappings, evaluating recursive subschema constraints.
* **Testability:**
  * *Unit:* Create isolated test cases for all 7 semantic violation categories; verify 100% detection accuracy.
  * *Integration:* Test a complete PR simulation where an enum is removed in Service A and verify the violation flags Service B's consumer code.

---

### Requirement I: Undocumented Downstream Consumer Discovery
* **Functional Specification:**
  * Automatically identify consumers of an endpoint or event channel that:
    1. Are not registered in any service catalog (e.g., Backstage).
    2. Have no formal Pact contract written.
    3. Are discovered either via OpenTelemetry `SPAN_KIND_CLIENT` runtime spans or cross-repo AST client calls.
  * Flag undocumented consumers in the change report, assigning an "Orphan Dependency" warning score.
* **User Value:** Uncovers shadow dependencies and legacy consumers before they are broken by an upstream refactor.
* **Implementation Complexity:** **Medium**
  * *Rationale:* Straightforward graph query matching `(:Service)-[:CALLS]->(e:Endpoint)` where the caller has no formal contract edge to the endpoint's schema.
* **Testability:**
  * *Unit:* Test graph traversal query isolating un-contracted caller nodes.
  * *Integration:* Populate graph with 5 services, 2 with registered contracts, 3 without; verify discovery of the 3 undocumented consumers.

---

### Requirement J: Explainable Blast Radius Calculation
* **Functional Specification:**
  * Calculate the multi-hop blast radius when a code symbol, endpoint, or database table changes:
    * Level 1: Direct consumers (services calling the modified endpoint/channel/table).
    * Level 2..N: Transitive consumers (services depending on Level 1 services that propagate the affected data).
  * Compute an **Operational Blast Radius Score (0 to 100)** incorporating:
    * *Depth:* Number of transitive hops.
    * *Traffic Volume:* Aggregate requests per minute (from OTel).
    * *Service Tier / Criticality:* Priority rating of affected services (e.g., Tier 1 Checkout vs Tier 4 Internal Analytics).
    * *Semantic Severity:* High (breaking type/enum change) vs Medium (default value change) vs Low (purely internal refactor).
* **User Value:** Provides engineering leadership and developers with an instant, objective risk score for every pull request.
* **Implementation Complexity:** **Medium**
  * *Rationale:* Neo4j Cypher path algorithms (`allShortestPaths`, variable-length relationships) efficiently compute multi-hop DAGs. The scoring formula is deterministic.
* **Testability:**
  * *Unit:* Test scoring algorithm with deterministic graph fixtures of varying depth, traffic, and severity.
  * *Integration:* Execute blast radius calculations on a 50-service synthetic microservice topology in <100ms.

---

### Requirement K: Traceable Evidence Explanation
* **Functional Specification:**
  * Every reported violation must provide an **unbroken, auditable evidence trail**:
    1. **PR Diff Anchor:** Exact file and line range in the PR commit diff.
    2. **AST Symbol:** The specific function, class, or route handler modified.
    3. **Contract Diff:** The exact JSON Pointer path in the OpenAPI/AsyncAPI spec (e.g., `/paths/~1orders/post/requestBody/content/application~1json/schema/properties/status`).
    4. **Runtime Trace Evidence:** Sample OpenTelemetry Trace ID, Span ID, timestamp, and observed caller service name.
    5. **Consumer Impact Anchor:** The exact file and line in the downstream consumer repository where the payload is consumed or validated.
  * Orchestrated via **LangGraph**: LangGraph takes the deterministic graph proof path and synthesizes human-readable, context-aware architectural explanations without fabricating facts.
* **User Value:** Developers never get generic or unverifiable warnings. Every alert links directly to code lines, OpenAPI schemas, and real trace IDs.
* **Implementation Complexity:** **High**
  * *Rationale:* Requires rigorous data plumbing to pass graph node IDs into the LangGraph state machine, enforcing strict grounding verification so the LLM cannot hallucinate citations.
* **Testability:**
  * *Unit:* Verify evidence chain serialization and JSON Pointer resolution.
  * *Integration:* Run LangGraph grounding evaluator ensuring that 100% of generated markdown links resolve to valid mock repository files and trace spans.

---

### Requirement L: Targeted Regression Test Recommendations
* **Functional Specification:**
  * Given the calculated blast radius, determine the minimal sufficient test subset:
    * Downstream consumer integration test files (e.g., `tests/integration/test_payment_client.py`).
    * Specific test function names targeting the modified endpoint.
    * End-to-end (E2E) workflow test suites exercising the affected path.
  * Optionally generate executable test stubs (Pytest, Jest, Playwright) mocking the new contract behavior for downstream teams.
* **User Value:** Cuts CI test suite execution time by up to 80% by running only relevant tests, while preventing untested breaking changes from slipping through.
* **Implementation Complexity:** **Medium**
  * *Rationale:* Mapping affected graph nodes to test files requires matching AST test function decorators and file naming conventions.
* **Testability:**
  * *Unit:* Test test-mapping parser against diverse test directory structures (`/tests`, `/spec`, `__tests__`).
  * *Integration:* Verify that changing Endpoint `/checkout` outputs the exact test path `tests/test_checkout_flow.py` in downstream consumer repo.

---

### Requirement M: Auditable Change-Impact Report Generation
* **Functional Specification:**
  * **GitHub Checks API Integration:** Post native GitHub Check Runs with granular inline annotations on the exact lines of code triggering violations.
  * **Pull Request Markdown Comment:** Publish a structured, executive summary table containing:
    * Blast Radius Risk Score (e.g., `85/100 - HIGH RISK`).
    * Direct & Transitive Affected Services breakdown.
    * Detailed Semantic Violations table with code links.
    * Trace Evidence links (OTel Trace IDs).
    * Recommended Regression Test commands.
  * **Export Formats:** Generate machine-readable JSON and SARIF (Static Analysis Results Interchange Format) reports for enterprise compliance and release gates.
* **User Value:** Seamless developer experience inside the GitHub UI; security and audit compliance teams get permanent change records.
* **Implementation Complexity:** **Low**
  * *Rationale:* Standard GitHub REST API integration and template-based markdown/SARIF generation.
* **Testability:**
  * *Unit:* Validate SARIF schema compliance using the official SARIF validator.
  * *Integration:* Mock GitHub Checks API endpoint and verify payload structure, annotation limits (GitHub restricts annotations to 50 per call), and pagination.

---

## 3. Non-Functional & Architecture Requirements

### 3.1 Architecture: The Realistic Modular Monolith
To ensure production reliability, ease of deployment, and avoid unnecessary distributed microservice operational overhead:
* **ChangeScope Core Architecture:** A **Modular Monolith** in Python:
  * **API & Webhook Ingestion Gateway:** FastAPI service handling GitHub webhooks, REST queries, and MCP server requests.
  * **Task & Job Queue:** **Celery / Redis** managing background asynchronous analysis tasks (cloning repos, AST parsing, graph updates).
  * **Knowledge Graph Persistence:** **Neo4j 5+** (Enterprise or Community) storing the software engineering ontology and executing Cypher blast-radius traversals.
  * **Relational State Store:** **PostgreSQL 16** storing user accounts, GitHub App installations, audit logs, and analysis run history.
  * **Trace Ingest Cache:** Redis or ClickHouse buffer for aggregating OpenTelemetry trace spans into service-to-service communication edges.
  * **Agent Reasoning Engine:** **LangGraph** running in-process within the worker containers to synthesize evidence trails.

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
              |    Neo4j LPG    |   |  PostgreSQL 16   |
              | (Software Graph)|   |  (Audit & State) |
              +-----------------+   +------------------+
```

### 3.2 Performance & SLA Requirements
* **Webhook Processing Turnaround:** Total analysis time from GitHub PR event to GitHub Check Run completion must be **$< 60$ seconds** for repositories with up to 100,000 lines of code and 100 downstream service nodes.
* **Graph Traversal Latency:** Multi-hop Cypher queries must execute in **$< 150$ milliseconds** at 50,000 graph nodes.
* **Tree-sitter Parse Throughput:** Greater than **5,000 lines of code per second** per worker core.

### 3.3 Security, Privacy & Compliance
* **Zero Source Code Retention:** Source code clones are kept in ephemeral worker tmpfs volumes and wiped immediately after AST symbol extraction.
* **Code Privacy:** ChangeScope only writes metadata (symbols, paths, routes, schemas) to Neo4j. Proprietary business logic code is never stored in the database.
* **OTel PII Scrubbing:** All trace span attributes are filtered through a PII scrubber before ingestion to eliminate passwords, authorization tokens, credit cards, or personal customer data.
* **GitHub Credential Security:** GitHub App private keys and installation tokens are stored in secure secrets managers (e.g., AWS Secrets Manager, HashiCorp Vault) and rotated automatically.
