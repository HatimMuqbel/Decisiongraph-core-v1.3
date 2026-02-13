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
  citation_ref?: string;
  citation_text?: string;
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
  // v3 fields
  field_scores?: Record<string, number>;
  matched_drivers?: string[];
  mismatched_drivers?: string[];
  non_transferable?: boolean;
  non_transferable_reasons?: string[];
  // B1 regime fields
  regime_limited?: boolean;
}

export interface AppealStatistics {
  total_appealed: number;
  upheld: number;
  overturned: number;
  upheld_rate: number;
}

// ── v3 Precedent Engine Types ─────────────────────────────────────────────

export interface ConfidenceDimension {
  name: string;
  level: string;
  value: number;
  bottleneck: boolean;
  note?: string;
}

// ── Regime Analysis Types (Phase B1/B2) ──────────────────────────────────

export interface RegimeShiftDetected {
  id: string;
  name: string;
  description: string;
  effective_date: string;
}

export interface RegimeAnalysis {
  shifts_detected: RegimeShiftDetected[];
  total_pool: number;
  pre_shift_count: number;
  post_shift_count: number;
  regime_limited_count: number;
  pct_regime_limited: number;
  magnitude: string;
  guidance: string;
  pre_shift_distribution: Record<string, number>;
  post_shift_distribution: Record<string, number>;
  effective_pool_size: number;
}

export interface EnhancedPrecedent {
  confidence_level?: string;
  confidence_dimensions?: ConfidenceDimension[];
  confidence_bottleneck?: string;
  confidence_hard_rule?: string;
  governed_alignment_count?: number;
  governed_alignment_total?: number;
  alignment_context?: string[];
  first_impression_alert?: string;
  transferable_count?: number;
  non_transferable_count?: number;
  institutional_posture?: string;
  pattern_summary?: string;
  case_thumbnails?: SampleCase[];
  driver_causality?: {
    shared_drivers: string[];
    divergent_drivers: string[];
  };
  divergence_justification?: {
    diverges_from_majority: boolean;
    contrary_count: number;
    total_decisive: number;
    contrary_details: Array<{
      precedent_id: string;
      outcome: string;
      similarity_pct: number;
      distinguishing_factors: string;
    }>;
    statement: string;
  } | null;
  non_transferable_explanations?: Array<{
    precedent_id: string;
    reasons: string[];
    mismatched_drivers: string[];
  }>;
  feature_comparison_matrix?: unknown[];
  override_statement?: string | null;
  outcome_distribution?: Record<string, number>;
  temporal_context?: unknown[];
  regime_analysis?: RegimeAnalysis;
  post_shift_gap_statement?: string;
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
  message?: string;
  // v3 fields
  confidence_level?: string;
  confidence_dimensions?: ConfidenceDimension[];
  confidence_bottleneck?: string;
  confidence_hard_rule?: string;
  confidence_model_version?: string;
  scoring_version?: string;
  governed_alignment_count?: number;
  governed_alignment_total?: number;
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

// ── Report View Model (mirrors backend view_model.py) ───────────────────────

export interface ReportGateSection {
  id: string;
  name: string;
  passed: boolean;
  reason: string;
}

export interface ReportTier1Signal {
  code: string;
  source: string;
  field?: string;
  detail: string;
}

export interface ReportTier2Signal {
  code: string;
  source: string;
  field?: string;
  detail: string;
}

export interface DecisionIntegrityAlert {
  type: string;
  severity: string;
  original_verdict: string;
  classifier_outcome: string;
  message: string;
}

export interface PrecedentDeviationAlert {
  type: string;
  message: string;
}

export interface DefensibilityCheck {
  status: string;
  message: string;
  action?: string;
  note?: string;
}

export interface EddRecommendation {
  action: string;
  reference?: string;
}

export interface SlaTimeline {
  case_created: string;
  edd_deadline: string;
  final_disposition_due: string;
  str_filing_window: string;
}

export interface ReportViewModel {
  // Administrative
  decision_id: string;
  decision_id_short: string;
  case_id: string;
  timestamp: string;
  jurisdiction: string;
  engine_version: string;
  policy_version: string;
  domain: string;
  report_schema_version?: string;
  narrative_compiler_version?: string;
  classifier_version?: string;
  report_sections?: string[];

  // Hashes
  input_hash: string;
  input_hash_short?: string;
  policy_hash: string;
  policy_hash_short?: string;

  // Case classification
  source_type: string;
  seed_category?: string;
  scenario_code?: string;
  is_seed: boolean;
  escalation_summary?: string;
  decision_confidence?: string;
  decision_confidence_reason?: string;
  decision_confidence_score?: number;
  similarity_summary?: string;
  decision_drivers: string[];

  // Transaction facts
  transaction_facts: EvidenceUsed[];

  // Decision (Governed)
  verdict: string;
  action: string;
  decision_status?: string;
  decision_explainer?: string;
  str_required: boolean;
  escalation_reasons?: string[];
  regulatory_status?: string;
  investigation_state?: string;
  primary_typology?: string;
  regulatory_obligation?: string;
  regulatory_position?: string;

  // Engine vs Governed
  engine_disposition: string;
  governed_disposition: string;

  // Canonical
  canonical_outcome: CanonicalOutcome;

  // Gates
  gate1_passed: boolean;
  gate1_decision: string;
  gate1_sections: ReportGateSection[];
  gate2_decision: string;
  gate2_status: string;
  gate2_sections: ReportGateSection[];

  // Evaluation Trace
  rules_fired: RuleFired[];
  evidence_used: EvidenceUsed[];
  risk_factors: { field: string; value: string }[];
  decision_path_trace: string;

  // Rationale
  summary: string;

  // Precedent Analysis
  precedent_analysis: PrecedentAnalysis;

  // Enhanced Precedent (v3)
  enhanced_precedent?: EnhancedPrecedent;

  // Suspicion Classification
  classification?: Record<string, unknown>;
  classification_outcome?: string;
  classification_reason?: string;
  tier1_signals: ReportTier1Signal[];
  tier2_signals: ReportTier2Signal[];
  suspicion_count?: number;
  investigative_count?: number;
  precedent_consistency_alert?: boolean;
  precedent_consistency_detail?: string;

  // Decision Integrity & Governance
  decision_integrity_alert?: DecisionIntegrityAlert | null;
  precedent_deviation_alert?: PrecedentDeviationAlert | null;
  corrections_applied?: Record<string, unknown>;
  classifier_is_sovereign?: boolean;

  // Precedent Metrics
  precedent_alignment_pct?: number;
  precedent_match_rate?: number;
  scored_precedent_count?: number;
  total_comparable_pool?: number;

  // Decision Conflict Alert
  decision_conflict_alert?: {
    classifier: string;
    engine: string;
    governed: string;
    resolution: string;
    blocking_gates: Array<{ gate: string; reason: string; name: string }>;
  };

  // Defensibility
  defensibility_check?: DefensibilityCheck;

  // EDD
  edd_recommendations?: EddRecommendation[];

  // SLA
  sla_timeline?: SlaTimeline;
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

// ── Report Viewer ───────────────────────────────────────────────────────────

export type ReportTier = 1 | 2 | 3;

export interface AutoEscalationReason {
  tier: ReportTier;
  reason: string;
}

/** Determine minimum tier based on risk signals in the report. */
export function computeAutoEscalation(report: ReportViewModel): AutoEscalationReason[] {
  const reasons: AutoEscalationReason[] = [];

  // Tier 2 triggers
  const tier1Signals = report.tier1_signals ?? [];
  const hasMandatoryEscalation = tier1Signals.some(
    (s) => s.code === 'MANDATORY_ESCALATION' || s.code === 'SAR_PATTERN',
  );
  if (hasMandatoryEscalation) reasons.push({ tier: 2, reason: 'Mandatory escalation signal present' });

  const amount = report.evidence_used?.find(
    (e) => e.field === 'txn.amount_band',
  );
  if (amount && ['25k_100k', '100k_500k', '500k_1m', 'over_1m'].includes(String(amount.value))) {
    reasons.push({ tier: 2, reason: 'Transaction amount exceeds $25,000 threshold' });
  }

  const priorSars = report.evidence_used?.find((e) => e.field === 'prior.sars_filed');
  if (priorSars && Number(priorSars.value) >= 2) {
    reasons.push({ tier: 2, reason: 'Prior suspicious activity reports >= 2' });
  }

  // Tier 3 triggers
  const hasDisqualifier = tier1Signals.some(
    (s) => s.code === 'SANCTIONS_SIGNAL' || s.code === 'TERRORIST_FINANCING',
  );
  if (hasDisqualifier) reasons.push({ tier: 3, reason: 'Disqualifier signal present' });

  if (report.verdict === 'HARD_STOP' || report.verdict === 'BLOCK') {
    reasons.push({ tier: 3, reason: 'Decision is BLOCK / HARD_STOP' });
  }

  if (report.str_required) {
    reasons.push({ tier: 3, reason: 'STR filing required' });
  }

  if (
    amount &&
    ['100k_500k', '500k_1m', 'over_1m'].includes(String(amount.value))
  ) {
    reasons.push({ tier: 3, reason: 'Transaction amount exceeds $100,000' });
  }

  if (report.decision_integrity_alert) {
    reasons.push({ tier: 3, reason: 'Decision integrity alert present' });
  }

  return reasons;
}

/** Get the minimum required tier for a report. */
export function getMinimumTier(report: ReportViewModel): ReportTier {
  const reasons = computeAutoEscalation(report);
  if (reasons.some((r) => r.tier === 3)) return 3;
  if (reasons.some((r) => r.tier === 2)) return 2;
  return 1;
}

// =============================================================================
// Policy Simulation Types (Phase C1/C2)
// =============================================================================

export interface DraftShift {
  id: string;
  name: string;
  description: string;
  parameter: string;
  old_value: unknown;
  new_value: unknown;
  trigger_signals: string[];
  affected_typologies: string[];
  citation: string | null;
}

export interface SimulationResult {
  case_id: string;
  original_disposition: string;
  simulated_disposition: string;
  original_reporting: string;
  simulated_reporting: string;
  disposition_changed: boolean;
  reporting_changed: boolean;
  escalation_direction: 'UP' | 'DOWN' | 'UNCHANGED';
}

export interface CascadeImpact {
  typology: string;
  pool_before: Record<string, number>;
  pool_after: Record<string, number>;
  pool_size: number;
  confidence_before: string;
  confidence_after: string;
  confidence_direction: 'IMPROVED' | 'DEGRADED' | 'UNCHANGED';
  posture_before: string;
  posture_after: string;
  posture_reversal: boolean;
  post_shift_pool_size: number;
  pool_adequacy: string;
}

export interface SimulationReport {
  draft: DraftShift;
  timestamp: string;
  total_cases_evaluated: number;
  affected_cases: number;
  unaffected_cases: number;
  disposition_changes: Record<string, number>;
  escalation_count: number;
  de_escalation_count: number;
  reporting_changes: Record<string, number>;
  new_str_filings: number;
  new_lctr_filings: number;
  risk_before: Record<string, number>;
  risk_after: Record<string, number>;
  magnitude: string;
  additional_edd_cases: number;
  additional_str_filings: number;
  estimated_analyst_hours_month: number;
  estimated_filing_cost_month: number;
  cascade_impacts: CascadeImpact[];
  warnings: string[];
  case_results: SimulationResult[];
}
