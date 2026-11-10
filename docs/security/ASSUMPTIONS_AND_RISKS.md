# ASSUMPTIONS_AND_RISKS.md
## ChangeScope: Risk Matrix, Assumptions & Mitigation Architecture

**Document Version:** 1.0.0  
**Status:** Complete Risk Analysis  
**Author:** Principal Software Architect & Staff Engineer  

---

### Executive Summary

Building an automated semantic intelligence layer across distributed microservices presents acute technical, architectural, and operational challenges. To maintain uncompromising engineering rigor, this document identifies:
1. The boundary between **Verified Facts**, **Engineering Hypotheses**, and **Unsupported Assumptions**.
2. Critical failure modes across the static-dynamic continuum.
3. Concrete architectural mitigation strategies to guarantee system reliability in production.

---

## 1. Categorization: Facts vs. Hypotheses vs. Assumptions

| Categorization Tier | Definition | Examples in ChangeScope |
| :--- | :--- | :--- |
| **Verified Facts** | Empirically documented behavior, standards, and verified performance benchmarks. | • Tree-sitter parses Python/TypeScript in milliseconds without compiling.<br>• Neo4j executes Cypher variable-length paths across 100K nodes in sub-seconds.<br>• OpenAPI 3.1 & JSON Schema Draft 2020-12 provide deterministic schema validation rules.<br>• OpenTelemetry semantic conventions define standard HTTP/RPC span attributes.<br>• NVIDIA Auto Ontology is a Text-to-SQL framework over relational databases, not a code AST analyzer. |
| **Engineering Hypotheses** | Plausible technical models based on sound engineering theory that require empirical validation during prototyping. | • Fusing static AST routes with OTel `SPAN_KIND_CLIENT` spans yields >90% route resolution accuracy.<br>• Pre-merge semantic drift detection pre-empts >80% of cross-microservice breaking changes.<br>• Targeted test recommendations reduce CI test execution time by >50% without decreasing defect detection.<br>• LangGraph state machine can be bound deterministically to Neo4j graph nodes to eliminate LLM hallucinations. |
| **Unsupported Assumptions** | Assumptions that MUST NOT be made without explicit proof or fallback architecture. | • *Assumption: "All enterprise microservices have comprehensive OpenTelemetry instrumentation."* (FALSE: Instrumentation is often partial, missing, or misconfigured).<br>• *Assumption: "Developers always write clean static URLs."* (FALSE: Dynamic string interpolation, URL builders, and proxy routes are widespread).<br>• *Assumption: "Every team commits valid OpenAPI specs to Git."* (FALSE: Specs are frequently out of date or absent).<br>• *Assumption: "LLMs can directly calculate blast radius reliably without a graph database."* (FALSE: LLMs suffer severe reasoning degradation and hallucinations on large multi-hop graphs). |

---

## 2. Technical Risk Matrix & Mitigation Strategies

```
+---------------------------------------------------------------------------------------+
|                                    RISK SEVERITY MAP                                  |
|                                                                                       |
|   HIGH        |  [R1: OTel Gaps]           [R2: Dynamic AST]       [R4: LLM Halluc]   |
|   SEVERITY    |                                                                       |
|   MEDIUM      |  [R3: Graph Explosion]     [R5: Schema False-Pos]                     |
|   LOW         |  [R6: GitHub Rate Limits]                                             |
|               +--------------------------------------------------------------------+  |
|                  LOW                       MEDIUM                  HIGH               |
|                                         PROBABILITY                                   |
+---------------------------------------------------------------------------------------+
```

---

### Risk R1: OpenTelemetry Coverage Gaps & Traffic Sparsity
* **Risk Description:** 
  In many enterprises, OpenTelemetry is partially adopted. Some legacy microservices have no tracing; new endpoints or staging environments may have low or zero traffic, leaving the runtime evidence graph incomplete.
* **Impact:** High. If ChangeScope relies solely on runtime traces, it will miss critical un-traced downstream consumers.
* **Probability:** High.
* **Mitigation Strategy:**
  1. **Dual-Layer Fusion (Static Primary, Runtime Enrichment):** Static AST analysis (Tree-sitter) serves as the baseline ground truth for code existence. OpenTelemetry runtime evidence serves as an enrichment layer (proving real traffic and payload shapes).
  2. **Three-State Confidence Scoring:**
     * `CONFIRMED_ACTIVE`: Verified by both static AST client call and recent OTel runtime spans.
     * `STATIC_ONLY`: Discovered in code, but no trace observed in last 30 days (potential dormant code or uninstrumented service).
     * `RUNTIME_ONLY`: Observed in traces, but no static client symbol located (dynamic caller, third-party client, or unindexed repo).
  3. Never drop a consumer dependency simply because runtime trace data is absent.

---

### Risk R2: Dynamic Code Patterns & AST Resolution Blindspots
* **Risk Description:** 
  Tree-sitter performs static syntax parsing. In dynamic languages (Python, JavaScript/TypeScript), developers frequently build URLs or route strings dynamically:
  ```python
  # Dynamic patterns invisible to simple AST string matching:
  endpoint = f"{CONFIG.BASE_URL}/{api_version}/users/{user_id}"
  response = getattr(client, method.lower())(endpoint)
  ```
* **Impact:** High. Failure to extract static URLs breaks the link between caller and provider.
* **Probability:** High.
* **Mitigation Strategy:**
  1. **Partial Path & Prefix Matching:** Parse string template literals into regex patterns (`/users/*`).
  2. **Symbolic Constant Propagation:** Implement a lightweight local symbol evaluator for file-level constants and configuration dictionaries.
  3. **OTel Trace Fallback:** When static AST encounters a dynamic expression, flag the AST node as `DYNAMIC_DISPATCH` and resolve the destination endpoint using the matching `SPAN_KIND_CLIENT` trace spans originating from that file/function.

---

### Risk R3: Knowledge Graph Explosion & Cypher Query Latency
* **Risk Description:** 
  If ChangeScope ingests every local variable, abstract syntax node, and individual trace span into Neo4j, the graph will explode to tens of millions of nodes, causing Cypher traversal latencies to degrade from milliseconds to minutes.
* **Impact:** Medium. CI/CD PR checks must finish within 60 seconds; slow graph queries cause pipeline timeouts.
* **Probability:** Medium.
* **Mitigation Strategy:**
  1. **Ontological Abstraction Boundary:** Do not store full ASTs in Neo4j. Ingest only **Architectural Boundary Nodes**: Services, Route Handlers, Exported Symbols, API Endpoints, Message Channels, and Database Tables.
  2. **Trace Aggregation Pre-Processing:** Do not store raw individual trace spans in Neo4j. An aggregation worker computes aggregated edges: `(:Service)-[:CALLS {calls_per_min: 1200, p95_ms: 45}]->(:Endpoint)` updated periodically.
  3. **Graph Partitioning & Pruning:** Enforce Neo4j composite indexes on `(Service.id, Endpoint.path_template)` and prune inactive historical edges older than 90 days.

---

### Risk R4: LLM Hallucination in Impact Explanations
* **Risk Description:** 
  Using Large Language Models (LLMs) to reason about code changes often leads to fabricated file paths, imaginary contract violations, or hallucinated line numbers, destroying developer trust.
* **Impact:** High. A developer receiving false alerts will quickly disable the GitHub Check.
* **Probability:** High (if LLM is used unconstrained).
* **Mitigation Strategy:**
  1. **Deterministic Rule Engine First:** The detection of breaking contract changes (enum narrowing, `additionalProperties: false` hazards, DDL column drops) is performed **100% by deterministic code algorithms**, not an LLM.
  2. **Constrained State Graph (LangGraph):** LangGraph is used *only* for natural-language synthesis of pre-verified facts. The state graph passes verified IDs:
     ```python
     class ViolationState(TypedDict):
         violation_id: str
         rule_code: str               # e.g., "RULE_ENUM_NARROWED"
         provider_symbol: CodeSymbol  # Verified Neo4j Node
         consumer_symbol: CodeSymbol  # Verified Neo4j Node
         schema_diff_path: str        # Verified JSON Pointer
         trace_evidence: TraceSpanRef # Verified OTel Span ID
         explanation: str             # Generated by LLM
     ```
  3. **Zero-Hallucination Citation Verification:** A post-processing guard verifies that every file link, line number, and identifier in the LLM's generated markdown matches an entity in the input state. If validation fails, the output reverts to a deterministic template.

---

### Risk R5: Schema Drift False Positives & Alert Fatigue
* **Risk Description:** 
  Flagging every minor schema change (e.g., adding an optional field that *could* theoretically break a consumer that *might* use closed-world validation) causes alert fatigue if consumers actually tolerate the change.
* **Impact:** Medium. Developers will ignore alerts if 90% of them are non-consequential.
* **Probability:** Medium.
* **Mitigation Strategy:**
  1. **Severity Stratification:**
     * **BLOCKING (Error):** Proven violation (e.g., consumer schema has explicit `additionalProperties: false`, or producer removed an enum value actively consumed).
     * **WARNING:** Potential violation (e.g., undocumented consumer detected with unknown validation mode).
     * **INFO:** Safe backward-compatible change (e.g., optional field added, all consumers verified open-world).
  2. **Configurable Team Thresholds:** Allow teams to tune rules via `.changescope.yml` (e.g., ignore enum warnings for internal staging services).

---

### Risk R6: GitHub API Rate Limits & Webhook Storms
* **Risk Description:** 
  Large enterprises with hundreds of developers can trigger hundreds of PR updates simultaneously, exhausting GitHub REST API rate limits (5,000 requests/hour per installation).
* **Impact:** Low to Medium. PR checks could get delayed or dropped.
* **Probability:** Medium.
* **Mitigation Strategy:**
  1. **GitHub App Installation Tokens:** GitHub Apps have higher rate limits that scale per repository (up to 12,500 requests/hour).
  2. **Git Smart Fetching:** Instead of cloning repositories via REST API, use shallow Git over HTTPS (`git fetch --depth=1`) with worker-level credential caching.
  3. **Asynchronous Task Queue (Redis/Celery):** Webhook endpoints immediately acknowledge with HTTP 202 and buffer tasks in Redis with exponential backoff and rate-limit throttling.

---

## 3. Production Deployment Architectural Guardrails

To ensure ChangeScope remains robust in enterprise environments, the following hard architectural guardrails are established:

1. **Deterministic Core / Generative Shell:** No database state modification or violation decision may ever be made by an LLM prompt. Deterministic algorithms compute graph paths; LLMs merely format the explanation.
2. **Ephemeral Code Lifecycle:** Source code is never retained. It is parsed in-memory or on tmpfs, indexed into abstract symbols, and wiped immediately.
3. **Graceful Degradation:** If OpenTelemetry is down, ChangeScope functions in static-only mode. If Neo4j is temporarily unreachable, PR checks fall back to single-repo AST diffing and report a warning rather than blocking developer merges.
