// ==============================================================================
// ChangeScope Software Engineering Ontology (CSEO) - Neo4j LPG Schema
// ==============================================================================

// --- Uniqueness Constraints across all 26 Entities ---

CREATE CONSTRAINT c_org_id IF NOT EXISTS FOR (o:Organization) REQUIRE (o.tenant_id, o.id) IS UNIQUE;
CREATE CONSTRAINT c_workspace_id IF NOT EXISTS FOR (w:Workspace) REQUIRE (w.tenant_id, w.id) IS UNIQUE;
CREATE CONSTRAINT c_repo_id IF NOT EXISTS FOR (r:Repository) REQUIRE (r.tenant_id, r.id) IS UNIQUE;
CREATE CONSTRAINT c_repo_version_id IF NOT EXISTS FOR (rv:RepositoryVersion) REQUIRE (rv.tenant_id, rv.id) IS UNIQUE;
CREATE CONSTRAINT c_commit_sha IF NOT EXISTS FOR (c:Commit) REQUIRE (c.tenant_id, c.sha) IS UNIQUE;
CREATE CONSTRAINT c_changeset_id IF NOT EXISTS FOR (cs:ChangeSet) REQUIRE (cs.tenant_id, cs.id) IS UNIQUE;
CREATE CONSTRAINT c_service_id IF NOT EXISTS FOR (s:Service) REQUIRE (s.tenant_id, s.id) IS UNIQUE;
CREATE CONSTRAINT c_module_id IF NOT EXISTS FOR (m:Module) REQUIRE (m.tenant_id, m.id) IS UNIQUE;
CREATE CONSTRAINT c_function_id IF NOT EXISTS FOR (f:Function) REQUIRE (f.tenant_id, f.id) IS UNIQUE;
CREATE CONSTRAINT c_endpoint_id IF NOT EXISTS FOR (e:APIEndpoint) REQUIRE (e.tenant_id, e.id) IS UNIQUE;
CREATE CONSTRAINT c_field_id IF NOT EXISTS FOR (fld:APIField) REQUIRE (fld.tenant_id, fld.id) IS UNIQUE;
CREATE CONSTRAINT c_event_id IF NOT EXISTS FOR (ev:Event) REQUIRE (ev.tenant_id, ev.id) IS UNIQUE;
CREATE CONSTRAINT c_eventschema_id IF NOT EXISTS FOR (es:EventSchema) REQUIRE (es.tenant_id, es.id) IS UNIQUE;
CREATE CONSTRAINT c_database_id IF NOT EXISTS FOR (db:Database) REQUIRE (db.tenant_id, db.id) IS UNIQUE;
CREATE CONSTRAINT c_table_id IF NOT EXISTS FOR (t:DatabaseTable) REQUIRE (t.tenant_id, t.id) IS UNIQUE;
CREATE CONSTRAINT c_column_id IF NOT EXISTS FOR (col:DatabaseColumn) REQUIRE (col.tenant_id, col.id) IS UNIQUE;
CREATE CONSTRAINT c_concept_urn IF NOT EXISTS FOR (bc:BusinessConcept) REQUIRE (bc.tenant_id, bc.urn) IS UNIQUE;
CREATE CONSTRAINT c_workflow_id IF NOT EXISTS FOR (wf:Workflow) REQUIRE (wf.tenant_id, wf.id) IS UNIQUE;
CREATE CONSTRAINT c_permission_id IF NOT EXISTS FOR (p:Permission) REQUIRE (p.tenant_id, p.id) IS UNIQUE;
CREATE CONSTRAINT c_owner_id IF NOT EXISTS FOR (own:Owner) REQUIRE (own.tenant_id, own.id) IS UNIQUE;
CREATE CONSTRAINT c_trace_id IF NOT EXISTS FOR (tr:Trace) REQUIRE (tr.tenant_id, tr.trace_id) IS UNIQUE;
CREATE CONSTRAINT c_span_id IF NOT EXISTS FOR (sp:TraceSpan) REQUIRE (sp.tenant_id, sp.span_id) IS UNIQUE;
CREATE CONSTRAINT c_dependency_id IF NOT EXISTS FOR (dep:Dependency) REQUIRE (dep.tenant_id, dep.id) IS UNIQUE;
CREATE CONSTRAINT c_finding_id IF NOT EXISTS FOR (fi:Finding) REQUIRE (fi.tenant_id, fi.id) IS UNIQUE;
CREATE CONSTRAINT c_evidence_id IF NOT EXISTS FOR (evi:Evidence) REQUIRE (evi.tenant_id, evi.id) IS UNIQUE;
CREATE CONSTRAINT c_testcase_id IF NOT EXISTS FOR (tc:TestCase) REQUIRE (tc.tenant_id, tc.id) IS UNIQUE;
CREATE CONSTRAINT c_recommendation_id IF NOT EXISTS FOR (rec:Recommendation) REQUIRE (rec.tenant_id, rec.id) IS UNIQUE;

// --- Performance Composite Indexes ---

CREATE INDEX idx_endpoint_route IF NOT EXISTS FOR (e:APIEndpoint) ON (e.tenant_id, e.method, e.path_template);
CREATE INDEX idx_service_name IF NOT EXISTS FOR (s:Service) ON (s.tenant_id, s.name);
CREATE INDEX idx_concept_category IF NOT EXISTS FOR (bc:BusinessConcept) ON (bc.tenant_id, bc.category);
CREATE INDEX idx_table_name IF NOT EXISTS FOR (t:DatabaseTable) ON (t.tenant_id, t.name);

// --- Multi-Hop Traversal Projections ---
// Supported relationship types:
// - [:CALLS]
// - [:IMPORTS]
// - [:PRODUCES]
// - [:CONSUMES]
// - [:MAPS_TO]
// - [:READS]
// - [:WRITES]
// - [:PERSISTS_AS]
// - [:PUBLISHES]
// - [:SUBSCRIBES_TO]
// - [:PART_OF_WORKFLOW]
// - [:OWNED_BY]
// - [:REQUIRES_PERMISSION]
// - [:DEPENDS_ON]
// - [:TRANSFORMS_INTO]
// Every edge carries: id, tenant_id, provenance, confidence, valid_from, valid_to, status.
