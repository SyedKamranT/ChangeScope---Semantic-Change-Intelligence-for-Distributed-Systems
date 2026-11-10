// ==============================================================================
// ChangeScope Software Architecture Ontology - Neo4j Schema & Constraints
// ==============================================================================

// --- Uniqueness Constraints ---

CREATE CONSTRAINT tenant_id_unique IF NOT EXISTS
FOR (t:Tenant) REQUIRE t.id IS UNIQUE;

CREATE CONSTRAINT workspace_id_unique IF NOT EXISTS
FOR (w:Workspace) REQUIRE w.id IS UNIQUE;

CREATE CONSTRAINT service_id_unique IF NOT EXISTS
FOR (s:Service) REQUIRE s.id IS UNIQUE;

CREATE CONSTRAINT endpoint_id_unique IF NOT EXISTS
FOR (e:Endpoint) REQUIRE e.id IS UNIQUE;

CREATE CONSTRAINT contract_id_unique IF NOT EXISTS
FOR (c:Contract) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT schema_model_id_unique IF NOT EXISTS
FOR (m:SchemaModel) REQUIRE m.id IS UNIQUE;

CREATE CONSTRAINT database_table_unique IF NOT EXISTS
FOR (tbl:DatabaseTable) REQUIRE tbl.id IS UNIQUE;

CREATE CONSTRAINT event_channel_unique IF NOT EXISTS
FOR (ch:EventChannel) REQUIRE ch.id IS UNIQUE;

// --- Node Existence & Property Indexes ---

CREATE INDEX service_name_idx IF NOT EXISTS
FOR (s:Service) ON (s.tenant_id, s.name);

CREATE INDEX endpoint_path_method_idx IF NOT EXISTS
FOR (e:Endpoint) ON (e.service_id, e.method, e.path_template);

CREATE INDEX contract_version_idx IF NOT EXISTS
FOR (c:Contract) ON (c.service_id, c.contract_type, c.version);

// --- Mandatory Edge Provenance Invariants ---
// Every relationship MUST store:
//   - provenance: 'AST_STATIC' | 'CONTRACT_SPEC' | 'OTEL_RUNTIME' | 'SQL_MIGRATION'
//   - confidence: Float (0.0 to 1.0)
//   - created_at: ISO8601 Timestamp
//   - evidence: JSON string / map
