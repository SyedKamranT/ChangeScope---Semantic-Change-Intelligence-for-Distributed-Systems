# ChangeScope Scientific Benchmark Specification
## Rigorous Empirical Evaluation Framework for Semantic Change Intelligence in Distributed Systems

---

## 1. Executive Overview & Design Philosophy

Modern enterprise software systems are organized as deeply connected, heterogeneous microservices communicating via synchronous RPC/HTTP APIs, asynchronous message brokers (Kafka, SQS, RabbitMQ), and shared transactional datastores. In such distributed architectures, pull requests frequently introduce changes that appear syntactically backward-compatible to traditional schema linters (e.g., OpenAPI diff, Protobuf buf linter, TypeScript compiler) but induce catastrophic runtime failures in production.

These silent failures arise from four structural blind spots:
1. **Semantic Concept Shifts:** Modifying the domain interpretation of identical data types (e.g., changing monetary representations from cents to dollars, switching timestamps from epoch seconds to milliseconds, or altering UUID concept semantics from `customer_id` to `account_id`).
2. **Hidden & Transitive Consumers:** Multi-hop blast radii ($A \to B \to C \to D$) where an upstream schema or field modification triggers deserialization or assertion failures three services downstream.
3. **Runtime-Only Dependencies:** Decoupled event streams, dynamic RPC bindings, service meshes, and reflection-based invocations that leave zero static import traces in the source repository AST.
4. **Behavioral & Permission Incompatibilities:** Unannounced event ordering assumption violations or tightened OAuth2 scope requirements rejected at runtime authorization filters.

The **ChangeScope Benchmark Suite** provides a scientific, reproducible, and verifiable evaluation platform to measure the efficacy of distributed change intelligence systems. It establishes a golden dataset of 52 seeded change scenarios across 15 canonical failure categories, evaluates three independent baselines, and quantifies performance using mathematically rigorous criteria.

---

## 2. The 15 Canonical Change Categories

The benchmark seeds realistic distributed system changes spanning the following 15 distinct categories:

| ID | Category | Definition | Ground Truth Risk |
| :-: | :--- | :--- | :-: |
| 1 | **FIELD_RENAME** | Renaming an existing contract or payload property without backward-compatible alias support. | BLOCKING |
| 2 | **FIELD_REMOVAL** | Removing a property previously consumed by downstream services or workflows. | BLOCKING |
| 3 | **TYPE_INCOMPATIBILITY** | Altering a property type (e.g., integer to string, scalar to list) without consumer adaptation. | BLOCKING |
| 4 | **MONETARY_UNIT_CHANGE** | Changing currency denomination or unit (e.g., integer cents to decimal dollars) with identical primitive type. | BLOCKING |
| 5 | **TIMESTAMP_INTERPRETATION_CHANGE** | Shifting time representations between epoch seconds, epoch milliseconds, ISO-8601 UTC, or localized strings. | BLOCKING |
| 6 | **IDENTIFIER_SEMANTIC_DRIFT** | Reinterpreting an identifier's business entity (e.g., user account identifier vs. billing customer identifier). | BLOCKING |
| 7 | **ENUM_SEMANTIC_CHANGES** | Altering allowed enum states, dropping existing enum values, or reordering workflow lifecycle transitions. | BLOCKING / WARNING |
| 8 | **EVENT_SCHEMA_EVOLUTION** | Modifying asynchronous messaging payload contracts published to event brokers (Kafka, SQS, EventBridge). | BLOCKING |
| 9 | **EVENT_ORDERING_ISSUES** | Removing partitioning keys or shifting from FIFO/sequential streams to unordered delivery. | BLOCKING |
| 10 | **DATABASE_MIGRATION_IMPACT** | DDL migration scripts dropping columns, altering column types, or adding non-nullable columns without defaults. | BLOCKING |
| 11 | **HIDDEN_DOWNSTREAM_CONSUMERS** | Upstream contract modifications breaking consumers that consume payloads via reflection, dynamic JSON queries, or decoupled clients. | BLOCKING |
| 12 | **TRANSITIVE_SERVICE_DEPENDENCIES** | Multi-hop ripple effects ($Service_A \to Service_B \to Service_C$) where intermediate services pass unvalidated payloads downstream. | BLOCKING |
| 13 | **RUNTIME_ONLY_DEPENDENCIES** | Service communications discoverable strictly via OpenTelemetry distributed traces that lack static codebase references. | BLOCKING |
| 14 | **PERMISSION_CHANGES** | Tightening API route permission requirements (e.g., adding `admin:write` scope) breaking existing client tokens. | BLOCKING |
| 15 | **UNRELATED_CHANGES (Negative Controls)** | Harmless changes (README documentation, internal private helper refactoring, unit tests, CI configurations, optional field additions) that must NOT trigger breaking alarms. | NONE (FPR = 0.0%) |

---

## 3. Mathematical Metric Definitions

Evaluation metrics are computed deterministically over scenario predictions and ground-truth annotations:

### 3.1 Confusion Matrix & Classification Metrics
For a dataset split $\mathcal{S}$ of scenarios:
* **True Positive (TP):** Scenario is breaking in ground truth ($y = 1$) and flagged as breaking by the engine ($\hat{y} = 1$).
* **False Positive (FP):** Scenario is harmless ($y = 0$) but erroneously flagged as breaking ($\hat{y} = 1$).
* **True Negative (TN):** Scenario is harmless ($y = 0$) and correctly classified as non-breaking ($\hat{y} = 0$).
* **False Negative (FN):** Scenario is breaking ($y = 1$) but missed by the engine ($\hat{y} = 0$).

$$\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}}$$

$$\text{Recall} = \frac{\text{TP}}{\text{TP} + \text{FN}}$$

$$\text{F1-Score} = 2 \cdot \frac{\text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$$

$$\text{Accuracy} = \frac{\text{TP} + \text{TN}}{\text{TP} + \text{TN} + \text{FP} + \text{FN}}$$

$$\text{False Positive Rate (FPR)} = \frac{\text{FP}}{\text{FP} + \text{TN}}$$

$$\text{False Negative Rate (FNR)} = \frac{\text{FN}}{\text{FN} + \text{TP}}$$

### 3.2 Semantic Drift Detection Rate
Measures the system's sensitivity to pure semantic alterations (Categories 4, 5, 6, 7) that exhibit zero structural syntax diffs:

$$\text{Semantic Drift Detection Rate} = \frac{\sum_{s \in \mathcal{S}_{\text{semantic}}} \mathbf{1}(\hat{y}_{s,\text{semantic}} = 1)}{|\mathcal{S}_{\text{semantic}}|}$$

### 3.3 Consumer Discovery Accuracy (Jaccard Overlap)
Quantifies the exactness of the discovered downstream impacted consumers compared to ground truth:

$$J(E_{\text{expected}}, E_{\text{predicted}}) = \begin{cases} 
1.0 & \text{if } E_{\text{expected}} = \emptyset \land E_{\text{predicted}} = \emptyset \\
0.0 & \text{if } E_{\text{expected}} = \emptyset \oplus E_{\text{predicted}} = \emptyset \\
\frac{|E_{\text{expected}} \cap E_{\text{predicted}}|}{|E_{\text{expected}} \cup E_{\text{predicted}}|} & \text{otherwise}
\end{cases}$$

$$\text{Consumer Discovery Accuracy} = \frac{1}{|\mathcal{S}|} \sum_{s \in \mathcal{S}} J(E_{s,\text{expected}}, E_{s,\text{predicted}})$$

### 3.4 Impact Path Accuracy
Measures the engine's ability to reconstruct the exact causal chain of service hops:

$$\text{Path Accuracy} = \frac{\text{Matched Impact Paths}}{\text{Total Expected Impact Paths}}$$

### 3.5 Latency & Cost Metrics
* **Deterministic Execution Latency:** $\text{Latency}_{\text{deterministic}} = t_{\text{end, graph}} - t_{\text{start}}$ (Target: $< 250\text{ms}$ SLA).
* **P95 Latency:** 95th percentile of per-scenario execution times.
* **Cost Per Analysis:** Evaluated as $\$0.00$ utilizing local quantized models (`qwen3:4b` via Ollama) with zero external API calls.

---

## 4. Evaluation Baselines

The benchmark compares three distinct operational paradigms:

### Baseline A: Structural Schema Diff Only
* **Mechanism:** Traditional OpenAPI / JSON Schema / SQL DDL comparative diff (akin to `oasdiff` or standard CI schema checks).
* **Scope:** Evaluates top-level and nested properties, required arrays, column drops, and HTTP path keys.
* **Inherent Blind Spots:** Zero dependency graph knowledge; blind to transitive blast radius, runtime consumers, and semantic concept shifts.

### Baseline B: Static Dependency Analysis
* **Mechanism:** Structural schema diff combined with static AST import and function call graph traversal (similar to static code analyzers like CodeQL or Dependency-Track).
* **Scope:** Identifies direct static consumers matching `STATIC_CALL`, `STATIC_IMPORT`, or direct client bindings.
* **Inherent Blind Spots:** Cannot observe dynamic reflection, decoupled asynchronous message consumers, runtime-discovered proxy routings, or semantic unit mutations.

### Baseline C: Full ChangeScope Platform
* **Mechanism:** Unified multi-layered change intelligence pipeline:
  1. *Deterministic AST & Contract Intelligence:* Semantic diff across OpenAPI 3.x, AsyncAPI, and SQL DDL.
  2. *Semantic Ontology Reconciliation:* Concept mapping layer identifying monetary unit, temporal format, and entity concept mutations.
  3. *OpenTelemetry Runtime Evidence Correlation:* Dynamically ingests trace attributes, span relationships, and traffic frequencies.
  4. *Transitive Blast Radius Graph Reasoning:* Traverses the multi-hop dependency graph up to depth $k=5$ with uncertainty penalization.
  5. *Local Quantized Explainability:* Synthesizes narrative summaries using local Ollama (`qwen3:4b`), strictly guarded by the `CitationVerificationGuard`.

---

## 5. Dataset Partitioning & Anti-Overfitting Protocol

To guarantee scientific validity and prevent accidental overfitting of heuristics to test cases, the 52 scenarios are strictly partitioned into two quarantined splits:

1. **Development Split (35 Scenarios):** Representative change cases used during system tuning, rule authoring, and heuristic calibration.
2. **Holdout Split (17 Scenarios):** Quarantined test cases evaluating novel microservice architectures, unobserved domain concepts, and multi-tier topologies. Performance metrics on the Holdout split must demonstrate an F1-score delta $\le 0.05$ relative to Development.
3. **Negative Controls (7 Scenarios):** Quarantined non-breaking PRs (Category 15) to verify false alarm rejection.

---

## 6. Stress Testing & Boundary Conditions

The benchmark subjects ChangeScope to five adversarial operational stress tests:
1. **Missing Telemetry Stress Test:** Simulates an uninstrumented service or cold-start environment. ChangeScope must gracefully fall back to static AST graph edges while applying an uncertainty penalty to multi-hop paths.
2. **Incomplete Ontology Stress Test:** Simulates proprietary domain concepts unmapped in the ontology. ChangeScope must safely flag findings with `UNCERTAIN` without crashing.
3. **Conflicting Semantic Mappings:** Contradictory OpenAPI vs. AsyncAPI contracts. ChangeScope must resolve conflicts deterministically, prioritizing runtime-confirmed evidence.
4. **Uncertain Inference Guard:** Relationships with low heuristic confidence ($< 0.75$) must automatically flag `requires_human_review = True`.
5. **Graph Scalability Across Scale Tiers:** Evaluates traversal latency on synthetic topologies of 100, 500, and 1,000 nodes, enforcing a strict $< 100\text{ms}$ traversal SLA.

---

## 7. Execution Commands & Reproducibility

The entire evaluation suite is 100% automated and reproducible via the following command:

```bash
# Execute complete evaluation suite across all 52 scenarios and baselines
python scripts/run_benchmark.py

# Optional parameters
python scripts/run_benchmark.py --scenarios dev
python scripts/run_benchmark.py --scenarios holdout
python scripts/run_benchmark.py --baseline c
python scripts/run_benchmark.py --no-stress-tests
python scripts/run_benchmark.py --ollama-samples 3 --ollama-model qwen3:4b
```
