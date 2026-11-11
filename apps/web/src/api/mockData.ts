import {
  RepositoryItem,
  ScanRunItem,
  ViolationDetail,
  TelemetryDependencyItem,
  OntologyConceptItem,
  WorkflowItem,
  AuditLogItem,
  IntegrationCredentialItem,
  TestRecommendationItem,
  SemanticDriftItem,
  EvidenceItem,
  WorkspaceItem,
} from './types'

export const DEFAULT_WORKSPACES: WorkspaceItem[] = [
  {
    id: 'ws-core',
    tenant_id: 'tenant-enterprise-primary',
    name: 'Core Platform',
    slug: 'core-platform',
    description: 'Mission-critical distributed payment and order processing topology',
    created_at: '2026-11-01T08:00:00Z',
  },
  {
    id: 'ws-data',
    tenant_id: 'tenant-enterprise-primary',
    name: 'Data Platform & ML',
    slug: 'data-platform',
    description: 'Streaming analytics and reporting pipelines',
    created_at: '2026-11-05T10:30:00Z',
  },
]

export const DEFAULT_REPOSITORIES: RepositoryItem[] = [
  {
    id: 'repo-inventory',
    tenant_id: 'tenant-enterprise-primary',
    workspace_id: 'ws-core',
    name: 'inventory-service',
    clone_url: 'https://github.com/changescope/inventory-service.git',
    default_branch: 'main',
    language: 'Python',
    tier: 'TIER_1_CRITICAL',
    last_scanned_commit: 'e89c1a4',
    created_at: '2026-11-01T09:00:00Z',
  },
  {
    id: 'repo-checkout',
    tenant_id: 'tenant-enterprise-primary',
    workspace_id: 'ws-core',
    name: 'checkout-service',
    clone_url: 'https://github.com/changescope/checkout-service.git',
    default_branch: 'main',
    language: 'TypeScript',
    tier: 'TIER_1_CRITICAL',
    last_scanned_commit: 'b45d2e1',
    created_at: '2026-11-01T09:15:00Z',
  },
  {
    id: 'repo-billing',
    tenant_id: 'tenant-enterprise-primary',
    workspace_id: 'ws-core',
    name: 'billing-ledger',
    clone_url: 'https://github.com/changescope/billing-ledger.git',
    default_branch: 'main',
    language: 'Python',
    tier: 'TIER_1_CRITICAL',
    last_scanned_commit: '7a11f9c',
    created_at: '2026-11-02T11:00:00Z',
  },
  {
    id: 'repo-analytics',
    tenant_id: 'tenant-enterprise-primary',
    workspace_id: 'ws-core',
    name: 'analytics-pipeline',
    clone_url: 'https://github.com/changescope/analytics-pipeline.git',
    default_branch: 'main',
    language: 'TypeScript',
    tier: 'TIER_2_STANDARD',
    last_scanned_commit: 'fa4209d',
    created_at: '2026-11-03T14:20:00Z',
  },
  {
    id: 'repo-gateway',
    tenant_id: 'tenant-enterprise-primary',
    workspace_id: 'ws-core',
    name: 'api-gateway',
    clone_url: 'https://github.com/changescope/api-gateway.git',
    default_branch: 'main',
    language: 'TypeScript',
    tier: 'TIER_1_CRITICAL',
    last_scanned_commit: '3c8e90a',
    created_at: '2026-11-04T16:00:00Z',
  },
]

export const DEFAULT_SCANS: ScanRunItem[] = [
  {
    id: 'scan-142',
    repository_id: 'repo-inventory',
    repository_name: 'inventory-service',
    status: 'COMPLETED',
    risk_score: 85,
    risk_level: 'CRITICAL',
    base_commit: 'main (a902b1c)',
    head_commit: 'feat/status-refactor (e89c1a4)',
    target_branch: 'main',
    source_branch: 'feature/status-refactor',
    blocking_violations_count: 3,
    warning_violations_count: 1,
    duration_ms: 1420,
    created_at: '2026-11-11T14:32:00Z',
    completed_at: '2026-11-11T14:32:01Z',
  },
  {
    id: 'scan-141',
    repository_id: 'repo-checkout',
    repository_name: 'checkout-service',
    status: 'COMPLETED',
    risk_score: 18,
    risk_level: 'LOW',
    base_commit: 'main (0081d4e)',
    head_commit: 'refactor/cleanup (b45d2e1)',
    target_branch: 'main',
    source_branch: 'refactor/cleanup',
    blocking_violations_count: 0,
    warning_violations_count: 0,
    duration_ms: 890,
    created_at: '2026-11-11T12:15:00Z',
    completed_at: '2026-11-11T12:15:01Z',
  },
  {
    id: 'scan-140',
    repository_id: 'repo-billing',
    repository_name: 'billing-ledger',
    status: 'COMPLETED',
    risk_score: 64,
    risk_level: 'HIGH',
    base_commit: 'main (5c9120e)',
    head_commit: 'fix/currency-precision (7a11f9c)',
    target_branch: 'main',
    source_branch: 'fix/currency-precision',
    blocking_violations_count: 1,
    warning_violations_count: 2,
    duration_ms: 2110,
    created_at: '2026-11-11T09:40:00Z',
    completed_at: '2026-11-11T09:40:02Z',
  },
]

export const DEFAULT_VIOLATIONS: ViolationDetail[] = [
  {
    id: 'v1',
    rule_code: 'RULE_ENUM_NARROWED',
    severity: 'BLOCKING',
    file_path: 'src/api/schemas/order.py',
    start_line: 42,
    end_line: 48,
    message:
      "Enum narrowed: removed value 'CANCELLED'. Active downstream consumer 'checkout-service' (12.5k RPM) deserializes this status and will crash.",
    json_pointer: '/components/schemas/OrderStatus/enum',
    impacted_service: 'checkout-service',
    evidence: {
      consumer: 'checkout-service',
      observed_traffic_rpm: 12500,
      protocol: 'HTTP',
    },
  },
  {
    id: 'v2',
    rule_code: 'RULE_CLOSED_WORLD_COLLISION',
    severity: 'BLOCKING',
    file_path: 'src/api/schemas/order.py',
    start_line: 65,
    end_line: 69,
    message:
      "Producer added optional property ['warehouse_zone'], but consumer 'checkout-service' enforces strict 'additionalProperties: false'.",
    json_pointer: '/components/schemas/OrderPayload/properties/warehouse_zone',
    impacted_service: 'checkout-service',
  },
  {
    id: 'v3',
    rule_code: 'RULE_DDL_COLUMN_SHRUNK',
    severity: 'BLOCKING',
    file_path: 'migrations/versions/v2_shrink_sku.sql',
    start_line: 12,
    end_line: 14,
    message:
      "Database column 'sku' shrunk from VARCHAR(64) to VARCHAR(16). Legacy records and downstream consumers query this table directly.",
    impacted_service: 'analytics-pipeline',
  },
  {
    id: 'v4',
    rule_code: 'RULE_TIME_UNIT_SHIFT',
    severity: 'WARNING',
    file_path: 'src/api/schemas/telemetry.py',
    start_line: 88,
    end_line: 92,
    message:
      "Field 'duration' shifted from integer seconds to milliseconds. Downstream alert threshold triggers will miscalculate by a factor of 1000x.",
    json_pointer: '/components/schemas/LatencyMetric/properties/duration',
    impacted_service: 'billing-ledger',
  },
]

export const DEFAULT_TELEMETRY_DEPENDENCIES: TelemetryDependencyItem[] = [
  {
    source_service: 'api-gateway',
    target_service: 'checkout-service',
    protocol: 'HTTP',
    rpm: 18500,
    p95_latency_ms: 14.2,
    error_rate_pct: 0.02,
    last_observed_at: '2026-11-11T17:00:00Z',
    environment: 'production',
    is_verified_in_graph: true,
  },
  {
    source_service: 'checkout-service',
    target_service: 'inventory-service',
    protocol: 'HTTP',
    rpm: 12500,
    p95_latency_ms: 22.8,
    error_rate_pct: 0.05,
    last_observed_at: '2026-11-11T17:00:00Z',
    environment: 'production',
    is_verified_in_graph: true,
  },
  {
    source_service: 'checkout-service',
    target_service: 'billing-ledger',
    protocol: 'GRPC',
    rpm: 8900,
    p95_latency_ms: 31.4,
    error_rate_pct: 0.01,
    last_observed_at: '2026-11-11T17:00:00Z',
    environment: 'production',
    is_verified_in_graph: true,
  },
  {
    source_service: 'inventory-service',
    target_service: 'analytics-pipeline',
    protocol: 'KAFKA',
    rpm: 4200,
    p95_latency_ms: 5.1,
    error_rate_pct: 0.0,
    last_observed_at: '2026-11-11T17:00:00Z',
    environment: 'production',
    is_verified_in_graph: true,
  },
  {
    source_service: 'billing-ledger',
    target_service: 'postgres-ledger-db',
    protocol: 'POSTGRES',
    rpm: 9500,
    p95_latency_ms: 4.8,
    error_rate_pct: 0.0,
    last_observed_at: '2026-11-11T17:00:00Z',
    environment: 'production',
    is_verified_in_graph: true,
  },
]

export const DEFAULT_ONTOLOGY_CONCEPTS: OntologyConceptItem[] = [
  { name: 'Organization', urn_pattern: 'urn:changescope:organization:{id}', status: 'CERTIFIED_DETERMINISTIC', certification_confidence: 1.0, description: 'Top-level enterprise entity owning workspaces' },
  { name: 'Workspace', urn_pattern: 'urn:changescope:workspace:{id}', status: 'CERTIFIED_DETERMINISTIC', certification_confidence: 1.0, description: 'Logical isolation boundary for repositories' },
  { name: 'Repository', urn_pattern: 'urn:changescope:repository:{id}', status: 'CERTIFIED_DETERMINISTIC', certification_confidence: 1.0, description: 'Source code version control unit' },
  { name: 'Service', urn_pattern: 'urn:changescope:service:{id}', status: 'CERTIFIED_DETERMINISTIC', certification_confidence: 1.0, description: 'Deployable computational microservice' },
  { name: 'APIEndpoint', urn_pattern: 'urn:changescope:apiendpoint:{id}', status: 'CERTIFIED_DETERMINISTIC', certification_confidence: 1.0, description: 'Exposed HTTP or RPC contract operation' },
  { name: 'APIField', urn_pattern: 'urn:changescope:apifield:{id}', status: 'CERTIFIED_DETERMINISTIC', certification_confidence: 1.0, description: 'Individual JSON schema property or parameter' },
  { name: 'Event', urn_pattern: 'urn:changescope:event:{id}', status: 'CERTIFIED_DETERMINISTIC', certification_confidence: 1.0, description: 'Asynchronous event payload published to brokers' },
  { name: 'Database', urn_pattern: 'urn:changescope:database:{id}', status: 'CERTIFIED_DETERMINISTIC', certification_confidence: 1.0, description: 'Physical or virtual database cluster' },
  { name: 'DatabaseTable', urn_pattern: 'urn:changescope:databasetable:{id}', status: 'CERTIFIED_DETERMINISTIC', certification_confidence: 1.0, description: 'Relational storage table' },
  { name: 'DatabaseColumn', urn_pattern: 'urn:changescope:databasecolumn:{id}', status: 'CERTIFIED_DETERMINISTIC', certification_confidence: 1.0, description: 'Individual schema column with type constraint' },
  { name: 'BusinessConcept', urn_pattern: 'urn:changescope:businessconcept:{id}', status: 'NVIDIA_AUTO_ONTOLOGY_VERIFIED', certification_confidence: 0.98, description: 'Domain meaning (e.g., CurrencyAmount, AccountID)' },
  { name: 'Workflow', urn_pattern: 'urn:changescope:workflow:{id}', status: 'CERTIFIED_DETERMINISTIC', certification_confidence: 1.0, description: 'End-to-end multi-service business sequence' },
  { name: 'TraceSpan', urn_pattern: 'urn:changescope:tracespan:{id}', status: 'CERTIFIED_DETERMINISTIC', certification_confidence: 1.0, description: 'OpenTelemetry runtime execution span' },
  { name: 'Finding', urn_pattern: 'urn:changescope:finding:{id}', status: 'CERTIFIED_DETERMINISTIC', certification_confidence: 1.0, description: 'Detected change violation or drift instance' },
  { name: 'Evidence', urn_pattern: 'urn:changescope:evidence:{id}', status: 'CERTIFIED_DETERMINISTIC', certification_confidence: 1.0, description: 'Cryptographically hashed source citation' },
  { name: 'TestCase', urn_pattern: 'urn:changescope:testcase:{id}', status: 'CERTIFIED_DETERMINISTIC', certification_confidence: 1.0, description: 'Automated test safeguarding contract invariant' },
  { name: 'Recommendation', urn_pattern: 'urn:changescope:recommendation:{id}', status: 'CERTIFIED_DETERMINISTIC', certification_confidence: 1.0, description: 'Actionable remediation and migration plan' },
]

export const DEFAULT_WORKFLOWS: WorkflowItem[] = [
  {
    id: 'wf-checkout',
    name: 'Customer Checkout & Payment Flow',
    criticality: 'TIER_1_CRITICAL',
    owner: 'checkout-platform-team',
    steps: [
      { step_index: 1, service: 'api-gateway', operation: 'POST /v1/checkout' },
      { step_index: 2, service: 'checkout-service', operation: 'VerifyCart' },
      { step_index: 3, service: 'inventory-service', operation: 'ReserveStock' },
      { step_index: 4, service: 'billing-ledger', operation: 'AuthorizePayment' },
      { step_index: 5, service: 'analytics-pipeline', operation: 'PublishOrderCreated' },
    ],
    disrupted_by_recent_scans: true,
    disruption_reason: 'Enum narrowing on inventory-service status breaks checkout-service deserializer at Step 3.',
  },
  {
    id: 'wf-fulfillment',
    name: 'Warehouse Order Fulfillment',
    criticality: 'TIER_1_CRITICAL',
    owner: 'logistics-ops',
    steps: [
      { step_index: 1, service: 'order-service', operation: 'ProcessFulfillment' },
      { step_index: 2, service: 'inventory-service', operation: 'DeductWarehouseZone' },
      { step_index: 3, service: 'shipping-service', operation: 'GenerateWaybill' },
    ],
    disrupted_by_recent_scans: true,
    disruption_reason: 'Closed-world schema collision on warehouse_zone property at Step 2.',
  },
  {
    id: 'wf-analytics-sync',
    name: 'Nightly Financial Analytics Sync',
    criticality: 'TIER_2_STANDARD',
    owner: 'data-infra',
    steps: [
      { step_index: 1, service: 'analytics-pipeline', operation: 'IngestKafkaEvents' },
      { step_index: 2, service: 'bi-warehouse', operation: 'QueryInventoryTable' },
    ],
    disrupted_by_recent_scans: true,
    disruption_reason: 'Database column sku shrunk from VARCHAR(64) to VARCHAR(16).',
  },
]

export const DEFAULT_TEST_RECOMMENDATIONS: TestRecommendationItem[] = [
  {
    id: 'test-rec-1',
    test_name: 'test_checkout_handles_legacy_cancelled_status',
    target_service: 'checkout-service',
    preconditions: 'Inventory item in state CANCELLED received via webhook or RPC call.',
    runtime: 'pytest',
    review_status: 'PENDING_HUMAN_REVIEW',
    confidence: 0.96,
    relevant_finding: 'RULE_ENUM_NARROWED in src/api/schemas/order.py',
    test_code: `import pytest
import httpx

@pytest.mark.asyncio
async def test_checkout_handles_legacy_cancelled_status():
    """Verify consumer does not crash when deserializing CANCELLED order."""
    payload = {
        "order_id": "ord_998811",
        "status": "CANCELLED",
        "total_cents": 4500
    }
    async with httpx.AsyncClient(base_url="http://checkout-service:8080") as client:
        response = await client.post("/internal/orders/process", json=payload)
        assert response.status_code in [200, 422], "Consumer crashed on removed enum value!"
`,
  },
  {
    id: 'test-rec-2',
    test_name: 'test_consumer_ignores_additional_warehouse_zone',
    target_service: 'checkout-service',
    preconditions: 'Producer emits optional field warehouse_zone in order payload.',
    runtime: 'pytest',
    review_status: 'PENDING_HUMAN_REVIEW',
    confidence: 0.94,
    relevant_finding: 'RULE_CLOSED_WORLD_COLLISION in src/api/schemas/order.py',
    test_code: `import pytest
import httpx

@pytest.mark.asyncio
async def test_consumer_ignores_additional_warehouse_zone():
    """Verify checkout-service safely accepts warehouse_zone in open-world model."""
    payload = {
        "order_id": "ord_998812",
        "status": "CONFIRMED",
        "warehouse_zone": "ZONE_WEST_4"
    }
    async with httpx.AsyncClient(base_url="http://checkout-service:8080") as client:
        response = await client.post("/internal/orders/process", json=payload)
        assert response.status_code == 200, "additionalProperties: false triggered validation failure!"
`,
  },
]

export const DEFAULT_SEMANTIC_DRIFT: SemanticDriftItem[] = [
  {
    id: 'drift-1',
    entity_urn: 'urn:changescope:apifield:inventory-service:order:status',
    before_definition: 'enum: ["PENDING", "CONFIRMED", "SHIPPED", "CANCELLED", "REFUNDED"]',
    after_definition: 'enum: ["PENDING", "CONFIRMED", "SHIPPED", "REFUNDED"]',
    difference_type: 'ENUM_NARROWED',
    business_concept: 'OrderLifecycleState',
    confidence: 1.0,
    detected_at: '2026-11-11T14:32:00Z',
    impact_summary: "Removal of 'CANCELLED' breaks checkout-service deserialization and historical audit replay.",
  },
  {
    id: 'drift-2',
    entity_urn: 'urn:changescope:apifield:billing-ledger:payment:amount',
    before_definition: 'type: integer, unit: cents, format: int64',
    after_definition: 'type: number, unit: dollars, format: float',
    difference_type: 'UNIT_SHIFT',
    business_concept: 'MonetaryAmount',
    confidence: 0.97,
    detected_at: '2026-11-11T09:40:00Z',
    impact_summary: 'Float dollars vs integer cents causes 100x discrepancy if uncoordinated.',
  },
  {
    id: 'drift-3',
    entity_urn: 'urn:changescope:databasecolumn:inventory_db:items:sku',
    before_definition: 'VARCHAR(64) NOT NULL',
    after_definition: 'VARCHAR(16) NOT NULL',
    difference_type: 'NULLABILITY_REVOKED',
    business_concept: 'StockKeepingUnit',
    confidence: 1.0,
    detected_at: '2026-11-11T14:32:00Z',
    impact_summary: 'Truncation risk for 4,200 existing catalog items exceeding 16 characters.',
  },
]

export const DEFAULT_EVIDENCE: EvidenceItem[] = [
  {
    id: 'evi-1',
    category: 'TREE_SITTER_AST',
    identifier: 'OrderStatusEnumDefinition',
    file_path: 'src/api/schemas/order.py',
    line_number: 42,
    sha256: '9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b',
    pii_scrubbed: true,
    observed_at: '2026-11-11T14:32:00Z',
  },
  {
    id: 'evi-2',
    category: 'OPENAPI_SPEC',
    identifier: 'POST /v1/orders Schema Component',
    file_path: 'docs/api/openapi.json',
    line_number: 145,
    sha256: 'f1e2d3c4b5a69788796a5b4c3d2e1f0a9b8c7d6e',
    pii_scrubbed: true,
    observed_at: '2026-11-11T14:32:00Z',
  },
  {
    id: 'evi-3',
    category: 'OTEL_SPAN',
    identifier: 'HTTP POST /orders [checkout-service -> inventory-service]',
    file_path: 'trace://span-0099881122',
    line_number: 1,
    sha256: '778899aabbccddeeff00112233445566778899aa',
    pii_scrubbed: true,
    observed_at: '2026-11-11T17:00:00Z',
  },
]

export const DEFAULT_CREDENTIALS: IntegrationCredentialItem[] = [
  {
    id: 'cred-gh-1',
    name: 'GitHub Enterprise Production App',
    provider: 'GITHUB',
    scopes: ['repo:read', 'pull_requests:read', 'pull_requests:write'],
    encryption_status: 'AES_256_GCM_ENCRYPTED',
    created_at: '2026-11-01T10:00:00Z',
  },
  {
    id: 'cred-slack-1',
    name: 'Slack Incident Alerts Webhook',
    provider: 'SLACK',
    scopes: ['incoming-webhook'],
    encryption_status: 'AES_256_GCM_ENCRYPTED',
    created_at: '2026-11-03T11:20:00Z',
  },
]

export const DEFAULT_AUDIT_LOGS: AuditLogItem[] = [
  {
    id: 'audit-001',
    actor_id: 'user_analyst_01',
    actor_role: 'ANALYST',
    event_type: 'SCAN_TRIGGERED',
    resource_type: 'ScanRun',
    resource_id: 'scan-142',
    client_ip: '10.0.4.12',
    status: 'SUCCESS',
    details: { repository: 'inventory-service', branch: 'feat/status-refactor' },
    created_at: '2026-11-11T14:32:00Z',
  },
  {
    id: 'audit-002',
    actor_id: 'user_malicious_probe',
    actor_role: 'ANALYST',
    event_type: 'BOLA_ATTEMPT_TRIGGER_SCAN',
    resource_type: 'Repository',
    resource_id: 'repo-cross-tenant-secret',
    client_ip: '198.51.100.42',
    status: 'DENIED',
    details: { target_tenant: 'tenant-competitor-xyz', reason: 'Cross-tenant boundary enforced' },
    created_at: '2026-11-11T13:45:00Z',
  },
  {
    id: 'audit-003',
    actor_id: 'user_admin_01',
    actor_role: 'ADMINISTRATOR',
    event_type: 'CREDENTIAL_CREATED',
    resource_type: 'IntegrationCredential',
    resource_id: 'cred-gh-1',
    client_ip: '10.0.1.5',
    status: 'SUCCESS',
    details: { provider: 'GITHUB', algorithm: 'AES-256-GCM' },
    created_at: '2026-11-01T10:00:00Z',
  },
  {
    id: 'audit-004',
    actor_id: 'user_viewer_02',
    actor_role: 'VIEWER',
    event_type: 'VERTICAL_PRIVILEGE_ATTEMPT',
    resource_type: 'IntegrationCredential',
    resource_id: 'cred-gh-1',
    client_ip: '10.0.8.22',
    status: 'DENIED',
    details: { required_role: 'ORGANIZATION_OWNER', actor_role: 'VIEWER' },
    created_at: '2026-11-10T16:20:00Z',
  },
]
