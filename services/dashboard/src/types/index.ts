// =============================================================================
// DecisionGraph Core v1.3 — TypeScript Type Definitions
// Mirrors backend schemas: JudgmentPayload, Decision Pack, Field Registry, etc.
// =============================================================================

// ── Field Registry ──────────────────────────────────────────────────────────

export type FieldType = 'boolean' | 'enum';

export interface FieldDefinition {
  website_name: string;
  display_name: string;
  type: FieldType;
  values?: (string | number)[];
  website_values?: Record<string, string | number>;
  fingerprint: boolean;
  required: boolean;
}

export type FieldRegistryMap = Record<string, FieldDefinition>;

export const FIELD_GROUPS = [
  'Customer',
  'Risk Profile',
  'Transaction',
  'Red Flags',
  'Screening',
] as const;

export type FieldGroup = (typeof FIELD_GROUPS)[number];

export function getFieldGroup(canonical: string): FieldGroup {
  if (canonical.startsWith('customer.type') || canonical.startsWith('customer.relationship'))
    return 'Customer';
  if (
    canonical.startsWith('customer.pep') ||
    canonical.startsWith('customer.high_risk') ||
    canonical.startsWith('customer.cash')
  )
    return 'Risk Profile';
  if (canonical.startsWith('txn.')) return 'Transaction';
  if (canonical.startsWith('flag.')) return 'Red Flags';
  if (canonical.startsWith('screening.') || canonical.startsWith('prior.')) return 'Screening';
  return 'Customer';
}

// ── Banking Outcome Model ───────────────────────────────────────────────────

export type Disposition = 'ALLOW' | 'EDD' | 'BLOCK' | 'UNKNOWN';
export type DispositionBasis = 'MANDATORY' | 'DISCRETIONARY' | 'UNKNOWN';
export type Reporting =
  | 'NO_REPORT'
  | 'FILE_STR'
  | 'FILE_LCTR'
  | 'FILE_TPR'
  | 'PENDING_EDD'
  | 'UNKNOWN';
export type DecisionLevel =
  | 'analyst'
  | 'senior_analyst'
  | 'manager'
  | 'cco'
  | 'senior_management';
export type Certainty = 'high' | 'medium' | 'low';

export interface CanonicalOutcome {
  disposition: Disposition;
  disposition_basis: DispositionBasis;
  reporting: Reporting;
  reporting_note?: string;
}

// ── Anchor Fact ─────────────────────────────────────────────────────────────

export interface AnchorFact {
  field_id: string;
  value: string | number | boolean;
  label: string;
}

// ── JudgmentPayload ─────────────────────────────────────────────────────────

export interface JudgmentPayload {
  precedent_id: string;
  case_id_hash: string;
  jurisdiction_code: string;
  fingerprint_hash: string;
  fingerprint_schema_id: string;
  exclusion_codes: string[];
  reason_codes: string[];
  reason_code_registry_id: string;
  outcome_code: string;
  certainty: Certainty;
  anchor_facts: AnchorFact[];
  policy_pack_hash: string;
  policy_pack_id: string;
  policy_version: string;
  decision_level: string;
  decided_at: string;
  decided_by_role: string;
  appealed: boolean;
  appeal_outcome?: string | null;
  appeal_decided_at?: string | null;
  appeal_level?: string | null;
  source_type: string;
  scenario_code?: string | null;
  seed_category?: string | null;
  outcome_notable?: string | null;
  disposition_basis: DispositionBasis;
  reporting_obligation: Reporting;
  domain: 'insurance' | 'banking';
  signal_codes: string[];
  authority_hashes: string[];
}

// ── Decision Pack ───────────────────────────────────────────────────────────

export interface DecisionMeta {
  decision_id: string;
  case_id: string;
  timestamp: string;
  jurisdiction: string;
  engine_version: string;
  policy_version: string;
  domain: string;
  input_hash: string;
  policy_hash: string;
  engine_commit: string;
  source_type: string;
  scenario_code?: string | null;
  seed_category?: string | null;
}

export interface RuleFired {
  code: string;
  result: string;
  reason: string;
}

export interface EvidenceUsed {
  field: string;
  value: string | number | boolean;
}

export interface SimilarityComponents {
  rules_overlap: number;
  gate_match: number;
  typology_overlap: number;
  amount_bucket: number;
  channel_method: number;
  corridor_match: number;
  pep_match: number;
  customer_profile: number;
  geo_risk: number;
}

export interface SampleCase {
  precedent_id: string;
  decision_level: string;
  decided_at: string;
  classification: 'supporting' | 'contrary' | 'neutral';
  overlap: number;
  similarity_pct: number;
  exact_match: boolean;
  outcome: string;
  outcome_normalized: string;
  outcome_label: string;
  disposition: string;
  disposition_basis: string;
  reporting: string;
  reason_codes: string[];
  appealed: boolean;
  appeal_outcome?: string | null;
  code_similarity_pct: number;
  fingerprint_similarity_pct: number;
  similarity_components: SimilarityComponents;
}

export interface AppealStatistics {
  total_appealed: number;
  upheld: number;
  overturned: number;
  upheld_rate: number;
}

export interface PrecedentAnalysis {
  available: boolean;
  match_count: number;
  sample_size: number;
  raw_overlap_count: number;
  overlap_outcome_distribution: Record<string, number>;
  match_outcome_distribution: Record<string, number>;
  appeal_statistics: AppealStatistics;
  precedent_confidence: number;
  supporting_precedents: number;
  contrary_precedents: number;
  neutral_precedents: number;
  exact_match_count: number;
  caution_precedents: CautionPrecedent[];
  sample_cases: SampleCase[];
  reason_codes_searched: string[];
  proposed_outcome_normalized: string;
  proposed_outcome_label: string;
  proposed_canonical: CanonicalOutcome;
  outcome_model_version: string;
  min_similarity_pct: number;
  threshold_used: number;
  threshold_mode: string;
  precedent_scoring_version: string;
  weights_version: string;
  similarity_summary?: string;
  why_low_match?: string[];
  avg_top_k_similarity?: number;
}

export interface CautionPrecedent {
  precedent_id: string;
  outcome: string;
  disposition: string;
  classification: string;
}

export interface Tier1Signal {
  element: string;
  present: boolean;
  reason: string;
}

export interface Tier2Signal {
  indicator: string;
  present: boolean;
  reason: string;
}

export interface GateSection {
  name: string;
  decision: string;
  reason: string;
}

export interface DecisionPack {
  meta: DecisionMeta;
  decision: {
    verdict: string;
    action: string;
    str_required: boolean | string;
    classifier_override?: boolean;
  };
  gates: {
    gate1: { decision: string; sections: Record<string, unknown> };
    gate2: { decision: string; status: string; sections: Record<string, unknown> };
  };
  rationale: {
    summary: string;
    str_rationale?: string | null;
    absolute_rules_validated: string[];
  };
  evaluation_trace: {
    rules_fired: RuleFired[];
    evidence_used: EvidenceUsed[];
    decision_path: string;
  };
  classifier: {
    sovereign: boolean;
    suspicion_count: number;
    investigative_count: number;
    outcome: string;
    outcome_reason: string;
    tier1_signals: Tier1Signal[];
    tier2_signals: Tier2Signal[];
    override_applied: boolean;
    original_verdict: string;
  };
  precedent_analysis: PrecedentAnalysis;
}

// ── Report View Model ───────────────────────────────────────────────────────

export interface ReportViewModel {
  decision_id: string;
  decision_id_short: string;
  case_id: string;
  timestamp: string;
  jurisdiction: string;
  engine_version: string;
  policy_version: string;
  domain: string;
  input_hash: string;
  policy_hash: string;
  source_type: string;
  seed_category?: string;
  scenario_code?: string;
  is_seed: boolean;
  verdict: string;
  action: string;
  str_required: boolean;
  engine_disposition: string;
  governed_disposition: string;
  canonical_outcome: CanonicalOutcome;
  transaction_facts: EvidenceUsed[];
  gate1_passed: boolean;
  gate1_decision: string;
  gate1_sections: GateSection[];
  gate2_decision: string;
  gate2_status: string;
  gate2_sections: GateSection[];
  rules_fired: RuleFired[];
  evidence_used: EvidenceUsed[];
  risk_factors: { field: string; value: string }[];
  decision_path_trace: string;
  summary: string;
  precedent_analysis: PrecedentAnalysis;
  tier1_signals: Tier1Signal[];
  tier2_signals: Tier2Signal[];
  decision_confidence?: {
    score: number;
    label: string;
    reason: string;
  };
  defensibility_check?: {
    defensible: boolean;
    reasons: string[];
  };
  edd_recommendations?: string[];
  sla_timeline?: {
    sla_hours: number;
    priority: string;
  };
  decision_drivers: string[];
  escalation_summary?: string;
}

// ── Demo Cases ──────────────────────────────────────────────────────────────

export interface DemoCase {
  id: string;
  name: string;
  description: string;
  category: 'PASS' | 'ESCALATE' | 'EDGE';
  expected_verdict: string;
  key_levers: string[];
  tags: string[];
  facts: AnchorFact[];
}

// ── Policy Shifts ───────────────────────────────────────────────────────────

export interface PolicyShiftSummary {
  id: string;
  name: string;
  description: string;
  citation: string;
  policy_version_before: string;
  policy_version_after: string;
  total_cases_analyzed: number;
  cases_affected: number;
  pct_affected: number;
  primary_change: string;
  summary: string;
}

export interface PolicyShiftCase {
  precedent_id: string;
  case_summary: string;
  outcome_before: CanonicalOutcome;
  outcome_after: CanonicalOutcome;
  decision_level_before: string;
  decision_level_after: string;
  change_type: string;
  rule_hash_before: string;
  rule_hash_after: string;
}

export interface PolicyShiftDetail {
  shift: {
    id: string;
    name: string;
    description: string;
    policy_version: string;
    citation: string;
    rule_change: {
      rule_id: string;
      before: Record<string, unknown>;
      after: Record<string, unknown>;
    };
  };
  total_cases: number;
  cases: PolicyShiftCase[];
}

// ── Seed Scenarios ──────────────────────────────────────────────────────────

export interface SeedScenario {
  name: string;
  description: string;
  base_facts: Record<string, string | number | boolean>;
  outcome: {
    disposition: Disposition;
    disposition_basis: DispositionBasis;
    reporting: Reporting;
  };
  decision_level: DecisionLevel;
  weight: number;
}

// ── API Responses ───────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  timestamp: string;
  engine_version: string;
  policy_version: string;
  narrative_compiler: string;
  suspicion_classifier: string;
}

export interface ReadyResponse {
  status: string;
  timestamp: string;
  checks: Record<string, boolean>;
  engine_version: string;
  policy_version: string;
  policy_hash: string;
  input_schema_version: string;
  output_schema_version: string;
  engine_commit: string;
}

export interface VersionResponse {
  engine_version: string;
  policy_version: string;
  engine_commit: string;
  policy_hash: string;
  input_schema_version: string;
  output_schema_version: string;
  jurisdiction: string;
}

export interface TemplateInfo {
  template_id: string;
  title: string;
  domain: string;
  version: string;
  policy_pack_id: string;
}

export interface TemplateDetail extends TemplateInfo {
  fields: Record<string, unknown>[];
  field_groups: Record<string, unknown>[];
  visibility_rules: Record<string, unknown>;
  evidence: Record<string, unknown>;
}

export interface ReportJsonResponse {
  format: 'json';
  generated_at: string;
  report: ReportViewModel;
  raw_decision?: DecisionPack;
}

// ── Dashboard Stats (computed client-side from demo cases + seeds) ─────────

export interface DashboardStats {
  totalDecisions: number;
  totalSeeds: number;
  scenarioCount: number;
  policyShiftCount: number;
  approvalRate: number;
  avgConfidence: number;
}
