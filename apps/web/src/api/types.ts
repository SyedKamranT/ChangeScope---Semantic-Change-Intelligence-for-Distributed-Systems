/**
 * ChangeScope Domain Data Types & DTOs
 */

export type RiskLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN'
export type ViolationSeverity = 'BLOCKING' | 'WARNING' | 'INFO'
export type ScanStatus = 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED'
export type TenantRole = 'ORGANIZATION_OWNER' | 'ADMINISTRATOR' | 'ANALYST' | 'VIEWER'

export interface UserProfile {
  id: string
  username: string
  tenant_id: string
  roles: TenantRole[]
}

export interface WorkspaceItem {
  id: string
  tenant_id: string
  name: string
  slug: string
  description?: string
  created_at: string
}

export interface RepositoryItem {
  id: string
  tenant_id: string
  workspace_id: string
  name: string
  clone_url: string
  default_branch: string
  language: string
  tier: 'TIER_1_CRITICAL' | 'TIER_2_STANDARD' | 'TIER_3_INTERNAL'
  last_scanned_commit?: string
  created_at: string
}

export interface ScanRunItem {
  id: string
  repository_id: string
  repository_name?: string
  status: ScanStatus
  risk_score: number | null
  risk_level: RiskLevel | null
  base_commit: string
  head_commit: string
  target_branch: string
  source_branch: string
  blocking_violations_count: number
  warning_violations_count: number
  duration_ms: number
  created_at: string
  completed_at: string | null
}

export interface ViolationDetail {
  id: string
  rule_code: string
  severity: ViolationSeverity
  file_path: string
  start_line: number
  end_line: number
  message: string
  json_pointer?: string
  impacted_service?: string
  evidence?: Record<string, unknown>
}

export interface TelemetryDependencyItem {
  source_service: string
  target_service: string
  protocol: 'HTTP' | 'GRPC' | 'KAFKA' | 'AMQP' | 'POSTGRES'
  rpm: number
  p95_latency_ms: number
  error_rate_pct: number
  last_observed_at: string
  environment: string
  is_verified_in_graph: boolean
}

export interface OntologyConceptItem {
  name: string
  urn_pattern: string
  status: 'CERTIFIED_DETERMINISTIC' | 'NVIDIA_AUTO_ONTOLOGY_VERIFIED' | 'CANDIDATE'
  certification_confidence: number
  description?: string
}

export interface WorkflowItem {
  id: string
  name: string
  criticality: 'TIER_1_CRITICAL' | 'TIER_2_STANDARD'
  owner: string
  steps: {
    step_index: number
    service: string
    operation: string
  }[]
  disrupted_by_recent_scans: boolean
  disruption_reason?: string
}

export interface AuditLogItem {
  id: string
  actor_id: string
  actor_role: string
  event_type: string
  resource_type: string
  resource_id?: string
  client_ip?: string
  status: 'SUCCESS' | 'DENIED' | 'FAILED'
  details: Record<string, unknown>
  created_at: string
}

export interface IntegrationCredentialItem {
  id: string
  name: string
  provider: 'GITHUB' | 'GITLAB' | 'BITBUCKET' | 'SLACK'
  scopes: string[]
  encryption_status: 'AES_256_GCM_ENCRYPTED'
  created_at: string
}

export interface TestRecommendationItem {
  id: string
  test_name: string
  target_service: string
  preconditions: string
  test_code: string
  runtime: 'pytest' | 'vitest' | 'npm'
  review_status: 'PENDING_HUMAN_REVIEW' | 'APPROVED' | 'DISMISSED'
  confidence: number
  relevant_finding: string
}

export interface SemanticDriftItem {
  id: string
  entity_urn: string
  before_definition: string
  after_definition: string
  difference_type: 'ENUM_NARROWED' | 'UNIT_SHIFT' | 'POLYSEMY_COLLISION' | 'NULLABILITY_REVOKED' | 'FORMAT_SHIFT'
  business_concept: string
  confidence: number
  detected_at: string
  impact_summary: string
}

export interface EvidenceItem {
  id: string
  category: 'TREE_SITTER_AST' | 'OPENAPI_SPEC' | 'ASYNCAPI_TOPIC' | 'OTEL_SPAN'
  identifier: string
  file_path: string
  line_number?: number
  sha256: string
  pii_scrubbed: boolean
  observed_at: string
}
