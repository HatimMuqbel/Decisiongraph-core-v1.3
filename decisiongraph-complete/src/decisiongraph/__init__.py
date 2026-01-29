"""
DecisionGraph Core (v1.3 - Universal Base)

The Universal Operating System for Deterministic Reasoning.

Core Principle: Namespace Isolation via Cryptographic Bridges
"Departments don't have to trust; they can verify the bridge."

v1.3 CHANGES:
- graph_id binds all cells to their graph instance
- system_time vs valid_time (clear bitemporal semantics)
- Strict namespace validation with regex
- Canonicalized rule hashing (whitespace-insensitive)
"""

__version__ = "1.3.0"
__author__ = "DecisionGraph"

# Cell primitives
from .cell import (
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Evidence,
    Proof,
    CellType,
    SourceQuality,
    SensitivityLevel,
    NULL_HASH,
    NAMESPACE_PATTERN,
    ROOT_NAMESPACE_PATTERN,
    HASH_SCHEME_LEGACY,
    HASH_SCHEME_CANONICAL,
    HASH_SCHEME_DEFAULT,
    compute_rule_logic_hash,
    compute_content_id,
    compute_policy_hash,
    get_current_timestamp,
    validate_namespace,
    validate_root_namespace,
    validate_timestamp,
    get_parent_namespace,
    is_namespace_prefix,
    generate_graph_id,
    canonicalize_rule_content
)

# Genesis
from .genesis import (
    create_genesis_cell,
    verify_genesis,
    verify_genesis_strict,
    is_genesis,
    validate_graph_id,
    get_genesis_rule,
    get_genesis_rule_hash,
    get_canonicalized_genesis_rule,
    GenesisError,
    GenesisValidationError,
    GENESIS_RULE,
    GENESIS_RULE_HASH,
    DEFAULT_ROOT_NAMESPACE,
    SCHEMA_VERSION,
    GRAPH_ID_PATTERN
)

# Chain
from .chain import (
    Chain,
    ChainError,
    IntegrityViolation,
    ChainBreak,
    GenesisViolation,
    TemporalViolation,
    GraphIdMismatch,
    HashSchemeMismatch,
    ValidationResult,
    create_chain
)

# Namespace
from .namespace import (
    Permission,
    BridgeStatus,
    NamespaceMetadata,
    Signature,
    NamespaceRegistry,
    NamespaceError,
    AccessDeniedError,
    BridgeRequiredError,
    BridgeApprovalError,
    create_namespace_definition,
    create_access_rule,
    create_bridge_rule,
    create_bridge_revocation,
    build_registry_from_chain
)

# Scholar (Resolver)
from .scholar import (
    Scholar,
    create_scholar,
    QueryResult,
    VisibilityResult,
    AuthorizationBasis,
    BridgeEffectiveness,
    BridgeEffectivenessReason,
    ResolutionEvent,
    ResolutionReason,
    ScholarIndex,
    build_index_from_chain,
    is_bridge_effective
)

# Exceptions (v1.4)
from .exceptions import (
    DecisionGraphError,
    SchemaInvalidError,
    InputInvalidError,
    UnauthorizedError,
    IntegrityFailError,
    SignatureInvalidError,
    InternalError,
    EXCEPTION_MAP,
    wrap_internal_exception
)

# Signing utilities (v1.4)
from .signing import (
    sign_bytes,
    verify_signature,
    generate_ed25519_keypair
)

# Engine (v1.4)
from .engine import (
    Engine,
    process_rfa,
    verify_proof_packet
)

# PolicyHead (v1.5)
from .policyhead import (
    create_policy_head,
    get_current_policy_head,
    get_policy_head_chain,
    get_policy_head_at_time,
    parse_policy_data,
    verify_policy_hash,
    validate_policy_head_chain,
    validate_threshold,
    is_bootstrap_threshold,
    is_production_threshold,
    POLICY_PROMOTION_RULE_HASH,
    POLICYHEAD_SCHEMA_VERSION
)

# WitnessSet (v1.5)
from .witnessset import WitnessSet

# WitnessRegistry (v1.5)
from .registry import WitnessRegistry

# Promotion (v1.5)
from .promotion import PromotionRequest, PromotionStatus

# Shadow Cells (v1.6)
from .shadow import (
    create_shadow_cell,
    create_shadow_fact,
    create_shadow_rule,
    create_shadow_policy_head,
    create_shadow_bridge,
    OverlayContext,
    fork_shadow_chain
)

# Simulation (v1.6)
from .simulation import (
    SimulationContext,
    SimulationResult,
    DeltaReport,
    ContaminationAttestation,
    compute_delta_report,
    tag_proof_bundle_origin,
    create_contamination_attestation,
    simulation_result_to_audit_text,
    simulation_result_to_dot
)

# Anchors (v1.6)
from .anchors import (
    ExecutionBudget,
    AnchorResult,
    compute_anchor_hash,
    detect_counterfactual_anchors
)

# Backtest (v1.6)
from .backtest import (
    BatchBacktestResult
)

# Write-Ahead Log (v2.0 foundation)
from .wal import (
    WAL_MAGIC,
    WAL_VERSION,
    HEADER_SIZE as WAL_HEADER_SIZE,
    MIN_RECORD_SIZE as WAL_MIN_RECORD_SIZE,
    MAX_RECORD_SIZE as WAL_MAX_RECORD_SIZE,
    NULL_HASH_BYTES,
    RecordFlags,
    WALError,
    WALCorruptionError,
    WALHeaderError,
    WALChainError,
    WALSequenceError,
    WALHeader,
    WALRecord,
    WALWriter,
    WALReader,
    recover_wal,
)

# Segmented WAL (v2.0 - unbounded storage)
from .segmented_wal import (
    DEFAULT_MAX_SEGMENT_BYTES,
    MANIFEST_VERSION,
    SEGMENT_NAME_FORMAT,
    SegmentedWALError,
    SegmentCorruptionError,
    ManifestError,
    SegmentMetadata,
    Manifest,
    SegmentedWALWriter,
    SegmentedWALReader,
    segment_path,
    list_segment_files,
    rebuild_manifest_from_segments,
    write_manifest_atomic,
    read_manifest,
)

# Canonical JSON - RFC 8785 (v2.0 foundation)
from .canon import (
    canonical_json_bytes,
    canonical_json_string,
    validate_canonical_safe,
    canonical_hash,
    float_to_canonical_string,
    confidence_to_string,
    score_to_string,
    evidence_sort_key,
    cell_to_canonical_dict,
    rfa_to_canonical_dict,
    simulation_spec_to_canonical_dict,
    compute_cell_id_canonical,
    CanonicalEncodingError,
    FloatNotAllowedError,
)

# Pack (v2.0 - domain configuration)
from .pack import (
    Pack,
    PackError,
    PackLoadError,
    PackValidationError,
    SchemaValidationError,
    PredicateError,
    SchemaType,
    FieldSchema,
    PayloadSchema,
    PredicateDefinition,
    load_pack,
    validate_payload,
    validate_predicate,
    create_signal_schema,
    create_mitigation_schema,
    create_score_schema,
    create_verdict_schema,
    create_justification_schema,
    create_report_run_schema,
    create_judgment_schema,
    create_universal_pack,
)

# Rules (v2.0 - deterministic evaluation)
from .rules import (
    RuleError,
    RuleDefinitionError,
    RuleEvaluationError,
    ConditionError,
    Severity,
    DetailedEvidenceAnchor,
    FactPattern,
    Condition,
    SignalRule,
    MitigationRule,
    ScoringRule,
    VerdictRule,
    ThresholdGate,
    EvaluationContext,
    EvaluationResult,
    RulesEngine,
    create_aml_example_engine,
)

# Justification (v2.0 - shadow node audit trails)
from .justification import (
    JustificationError,
    IncompleteJustificationError,
    GatingError,
    UniversalQuestionSet,
    UNIVERSAL_QUESTIONS_V1,
    get_question_set,
    JustificationAnswers,
    JustificationBuilder,
    ReviewGateResult,
    GateEvaluation,
    ReviewGate,
    create_signal_justification,
    create_verdict_justification,
    create_auto_justification,
    JustificationSummary,
    analyze_justifications,
)

# Report (v2.0 - frozen reproducible reports)
from .report import (
    ReportError,
    IncompleteReportError,
    JudgmentError,
    ReportVerificationError,
    JudgmentAction,
    ReportStatus,
    ReportManifest,
    JudgmentData,
    ReportSummary,
    ReportBuilder,
    JudgmentBuilder,
    verify_report_artifact,
    verify_report_cells_included,
    get_report_status,
    analyze_report,
    compute_artifact_hash,
    create_approval_judgment,
    create_rejection_judgment,
    create_escalation_judgment,
)

# Template (v2.0 - declarative report templates)
from .template import (
    TemplateError,
    TemplateValidationError,
    RenderError,
    SectionLayout,
    Alignment,
    ColumnDefinition,
    SectionDefinition,
    CitationFormat,
    ScoreGridFormat,
    ReportTemplate,
    filter_cells_for_section,
    sort_cells_deterministic,
    render_report,
    render_report_text,
    render_section,
    render_integrity_section,
    create_aml_alert_template,
    template_to_dict,
    template_from_dict,
)

# Citations (v2.0 - policy citation infrastructure)
from .citations import (
    CitationError,
    CitationNotFoundError,
    PolicyCitation,
    CitationCompact,
    CitationQuality,
    CitationRegistry,
    compute_citation_hash,
    build_registry_from_pack,
    format_citation_for_report,
    format_citations_section,
    format_citation_quality_section,
)

# Bank Report (v2.0 - 4-gate protocol bank-grade reports)
from .bank_report import (
    BankReportError,
    TypologyClass,
    ReportConfig,
    EvidenceAnchor,
    EvidenceAnchorGrid,
    FeedbackScores,
    RequiredAction,
    BankReportRenderer,
    render_bank_report,
)

# Taxonomy (v2.1 - 6-layer constitutional decision framework with fixes)
from .taxonomy import (
    DecisionLayer,
    ObligationType,
    IndicatorStrength,
    TypologyCategory,
    TypologyMaturity,
    InstrumentType,
    HardStopType,
    SuspicionBasis,
    VerdictCategory,
    LayerClassification,
    TypologyAssessment,
    HardStopAssessment,
    SuspicionAssessment,
    TaxonomyResult,
    TaxonomyClassifier,
    OBLIGATION_SIGNALS,
    INDICATOR_SIGNALS,
    CASH_ONLY_SIGNALS,
    HARD_STOP_FACT_SIGNALS,
    TYPOLOGY_RULES,
    WIRE_TYPOLOGY_RULES,
    TAXONOMY_TO_VERDICT,
    TAXONOMY_TO_TIER,
    TAXONOMY_AUTO_ARCHIVE,
    get_taxonomy_verdict,
)

# Gates (v2.0 - 4-gate protocol evaluation engine)
from .gates import (
    GateError,
    GateConfigError,
    GateEvaluationError,
    GateStatus,
    GateNumber,
    GateResult,
    TypologyGateConfig,
    InherentMitigatingGateConfig,
    ResidualRiskGateConfig,
    IntegrityAuditGateConfig,
    GateConfig,
    GateEvaluator,
)

# Confidence (v2.0 - weighted confidence calculation)
from .confidence import (
    ConfidenceError,
    ConfigurationError,
    ConfidenceWeights,
    ConfidenceConfig,
    ConfidenceFactor,
    ConfidenceResult,
    ConfidenceCalculator,
    compute_confidence,
)

# Actions (v2.0 - required actions with SLA)
from .actions import (
    ActionError,
    TriggerParseError,
    ActionConfigError,
    TriggerType,
    ActionPriority,
    ActionRule,
    GeneratedAction,
    ActionConfig,
    TriggerEvaluator,
    ActionGenerator,
    generate_required_actions,
    format_actions_for_report,
)

__all__ = [
    '__version__',
    # Cell
    'DecisionCell', 'Header', 'Fact', 'LogicAnchor', 'Evidence', 'Proof',
    'CellType', 'SourceQuality', 'SensitivityLevel', 'NULL_HASH',
    'NAMESPACE_PATTERN', 'ROOT_NAMESPACE_PATTERN',
    'HASH_SCHEME_LEGACY', 'HASH_SCHEME_CANONICAL', 'HASH_SCHEME_DEFAULT',
    'compute_rule_logic_hash', 'compute_content_id', 'compute_policy_hash', 'get_current_timestamp',
    'validate_namespace', 'validate_root_namespace', 'validate_timestamp',
    'get_parent_namespace', 'is_namespace_prefix',
    'generate_graph_id', 'canonicalize_rule_content',
    # Genesis
    'create_genesis_cell', 'verify_genesis', 'verify_genesis_strict', 'is_genesis',
    'validate_graph_id',
    'get_genesis_rule', 'get_genesis_rule_hash', 'get_canonicalized_genesis_rule',
    'GenesisError', 'GenesisValidationError',
    'GENESIS_RULE', 'GENESIS_RULE_HASH', 'DEFAULT_ROOT_NAMESPACE', 'SCHEMA_VERSION',
    'GRAPH_ID_PATTERN',
    # Chain
    'Chain', 'ChainError', 'IntegrityViolation', 'ChainBreak',
    'GenesisViolation', 'TemporalViolation', 'GraphIdMismatch', 'HashSchemeMismatch',
    'ValidationResult', 'create_chain',
    # Namespace
    'Permission', 'BridgeStatus', 'NamespaceMetadata', 'Signature', 'NamespaceRegistry',
    'NamespaceError', 'AccessDeniedError', 'BridgeRequiredError', 'BridgeApprovalError',
    'create_namespace_definition', 'create_access_rule', 'create_bridge_rule',
    'create_bridge_revocation', 'build_registry_from_chain',
    # Scholar
    'Scholar', 'create_scholar', 'QueryResult', 'VisibilityResult',
    'AuthorizationBasis', 'BridgeEffectiveness', 'BridgeEffectivenessReason',
    'ResolutionEvent', 'ResolutionReason',
    'ScholarIndex', 'build_index_from_chain', 'is_bridge_effective',
    # Exceptions (v1.4)
    'DecisionGraphError', 'SchemaInvalidError', 'InputInvalidError',
    'UnauthorizedError', 'IntegrityFailError', 'SignatureInvalidError',
    'InternalError',
    # Exception mapping utilities (v1.4)
    'EXCEPTION_MAP', 'wrap_internal_exception',
    # Signing utilities (v1.4)
    'sign_bytes', 'verify_signature', 'generate_ed25519_keypair',
    # Engine (v1.4)
    'Engine', 'process_rfa', 'verify_proof_packet',
    # PolicyHead (v1.5)
    'create_policy_head', 'get_current_policy_head', 'get_policy_head_chain',
    'get_policy_head_at_time', 'parse_policy_data', 'verify_policy_hash',
    'validate_policy_head_chain', 'validate_threshold',
    'is_bootstrap_threshold', 'is_production_threshold',
    'POLICY_PROMOTION_RULE_HASH', 'POLICYHEAD_SCHEMA_VERSION',
    # WitnessSet (v1.5)
    'WitnessSet',
    # WitnessRegistry (v1.5)
    'WitnessRegistry',
    # Promotion (v1.5)
    'PromotionRequest', 'PromotionStatus',
    # Shadow Cells (v1.6)
    'create_shadow_cell', 'create_shadow_fact', 'create_shadow_rule',
    'create_shadow_policy_head', 'create_shadow_bridge',
    # OverlayContext and contamination prevention (v1.6)
    'OverlayContext', 'fork_shadow_chain',
    # Simulation (v1.6)
    'SimulationContext', 'SimulationResult',
    'DeltaReport', 'ContaminationAttestation',
    'compute_delta_report', 'tag_proof_bundle_origin', 'create_contamination_attestation',
    'simulation_result_to_audit_text', 'simulation_result_to_dot',
    # Anchors (v1.6)
    'ExecutionBudget', 'AnchorResult', 'compute_anchor_hash', 'detect_counterfactual_anchors',
    # Backtest (v1.6)
    'BatchBacktestResult',
    # Write-Ahead Log (v2.0 foundation)
    'WAL_MAGIC',
    'WAL_VERSION',
    'WAL_HEADER_SIZE',
    'WAL_MIN_RECORD_SIZE',
    'WAL_MAX_RECORD_SIZE',
    'NULL_HASH_BYTES',
    'RecordFlags',
    'WALError',
    'WALCorruptionError',
    'WALHeaderError',
    'WALChainError',
    'WALSequenceError',
    'WALHeader',
    'WALRecord',
    'WALWriter',
    'WALReader',
    'recover_wal',
    # Segmented WAL (v2.0 - unbounded storage)
    'DEFAULT_MAX_SEGMENT_BYTES',
    'MANIFEST_VERSION',
    'SEGMENT_NAME_FORMAT',
    'SegmentedWALError',
    'SegmentCorruptionError',
    'ManifestError',
    'SegmentMetadata',
    'Manifest',
    'SegmentedWALWriter',
    'SegmentedWALReader',
    'segment_path',
    'list_segment_files',
    'rebuild_manifest_from_segments',
    'write_manifest_atomic',
    'read_manifest',
    # Canonical JSON - RFC 8785 (v2.0 foundation)
    'canonical_json_bytes',
    'canonical_json_string',
    'validate_canonical_safe',
    'canonical_hash',
    'float_to_canonical_string',
    'confidence_to_string',
    'score_to_string',
    'evidence_sort_key',
    'cell_to_canonical_dict',
    'rfa_to_canonical_dict',
    'simulation_spec_to_canonical_dict',
    'compute_cell_id_canonical',
    'CanonicalEncodingError',
    'FloatNotAllowedError',
    # Pack (v2.0 - domain configuration)
    'Pack',
    'PackError',
    'PackLoadError',
    'PackValidationError',
    'SchemaValidationError',
    'PredicateError',
    'SchemaType',
    'FieldSchema',
    'PayloadSchema',
    'PredicateDefinition',
    'load_pack',
    'validate_payload',
    'validate_predicate',
    'create_signal_schema',
    'create_mitigation_schema',
    'create_score_schema',
    'create_verdict_schema',
    'create_justification_schema',
    'create_report_run_schema',
    'create_judgment_schema',
    'create_universal_pack',
    # Rules (v2.0 - deterministic evaluation)
    'RuleError',
    'RuleDefinitionError',
    'RuleEvaluationError',
    'ConditionError',
    'Severity',
    'FactPattern',
    'Condition',
    'SignalRule',
    'MitigationRule',
    'ScoringRule',
    'VerdictRule',
    'ThresholdGate',
    'EvaluationContext',
    'EvaluationResult',
    'RulesEngine',
    'create_aml_example_engine',
    # Justification (v2.0 - shadow node audit trails)
    'JustificationError',
    'IncompleteJustificationError',
    'GatingError',
    'UniversalQuestionSet',
    'UNIVERSAL_QUESTIONS_V1',
    'get_question_set',
    'JustificationAnswers',
    'JustificationBuilder',
    'ReviewGateResult',
    'GateEvaluation',
    'ReviewGate',
    'create_signal_justification',
    'create_verdict_justification',
    'create_auto_justification',
    'JustificationSummary',
    'analyze_justifications',
    # Report (v2.0 - frozen reproducible reports)
    'ReportError',
    'IncompleteReportError',
    'JudgmentError',
    'ReportVerificationError',
    'JudgmentAction',
    'ReportStatus',
    'ReportManifest',
    'JudgmentData',
    'ReportSummary',
    'ReportBuilder',
    'JudgmentBuilder',
    'verify_report_artifact',
    'verify_report_cells_included',
    'get_report_status',
    'analyze_report',
    'compute_artifact_hash',
    'create_approval_judgment',
    'create_rejection_judgment',
    'create_escalation_judgment',
    # Template (v2.0 - declarative report templates)
    'TemplateError',
    'TemplateValidationError',
    'RenderError',
    'SectionLayout',
    'Alignment',
    'ColumnDefinition',
    'SectionDefinition',
    'CitationFormat',
    'ScoreGridFormat',
    'ReportTemplate',
    'filter_cells_for_section',
    'sort_cells_deterministic',
    'render_report',
    'render_report_text',
    'render_section',
    'render_integrity_section',
    'create_aml_alert_template',
    'template_to_dict',
    'template_from_dict',
    # Citations (v2.0 - policy citation infrastructure)
    'CitationError',
    'CitationNotFoundError',
    'PolicyCitation',
    'CitationCompact',
    'CitationQuality',
    'CitationRegistry',
    'compute_citation_hash',
    'build_registry_from_pack',
    'format_citation_for_report',
    'format_citations_section',
    'format_citation_quality_section',
    # Bank Report (v2.0 - 4-gate protocol bank-grade reports)
    'BankReportError',
    'TypologyClass',
    'GateStatus',
    'ReportConfig',
    'EvidenceAnchor',
    'EvidenceAnchorGrid',
    'FeedbackScores',
    'RequiredAction',
    'GateResult',
    'BankReportRenderer',
    'render_bank_report',
    # Taxonomy (v2.1 - 6-layer constitutional decision framework with fixes)
    'DecisionLayer',
    'ObligationType',
    'IndicatorStrength',
    'TypologyCategory',
    'TypologyMaturity',
    'InstrumentType',
    'HardStopType',
    'SuspicionBasis',
    'VerdictCategory',
    'LayerClassification',
    'TypologyAssessment',
    'HardStopAssessment',
    'SuspicionAssessment',
    'TaxonomyResult',
    'TaxonomyClassifier',
    'OBLIGATION_SIGNALS',
    'INDICATOR_SIGNALS',
    'CASH_ONLY_SIGNALS',
    'HARD_STOP_FACT_SIGNALS',
    'TYPOLOGY_RULES',
    'WIRE_TYPOLOGY_RULES',
    'TAXONOMY_TO_VERDICT',
    'TAXONOMY_TO_TIER',
    'TAXONOMY_AUTO_ARCHIVE',
    'get_taxonomy_verdict',
    # Case Schema (Financial Crime)
    'CaseType',
    'CasePhase',
    'Sensitivity',
    'CaseMeta',
    'CaseBundle',
    # Case Loader (Financial Crime)
    'load_case_bundle',
    'load_case_bundle_to_chain',
    # Pack Loader (Financial Crime)
    'load_pack_yaml',
    'load_pack_dict',
    'validate_pack',
    'compile_pack',
    'compute_pack_hash',
    'PackRuntime',
    'PackLoaderError',
    'PackValidationError',
    'PackCompilationError',
]

# Case Schema (Financial Crime)
from .case_schema import (
    CaseType,
    CasePhase,
    Sensitivity,
    CaseMeta,
    CaseBundle,
)

# Case Loader (Financial Crime)
from .case_loader import load_case_bundle, load_case_bundle_to_chain

# Pack Loader (Financial Crime)
from .pack_loader import (
    load_pack_yaml,
    load_pack_dict,
    validate_pack,
    compile_pack,
    compute_pack_hash,
    PackRuntime,
    PackLoaderError,
    PackValidationError,
    PackCompilationError,
)

# Escalation Gate (Zero-False-Escalation Checklist)
from .escalation_gate import (
    GateStatus as EscalationGateStatus,
    EscalationDecision,
    GateCheck,
    SectionResult,
    EscalationGateResult,
    EscalationGateValidator,
    run_escalation_gate,
    ABSOLUTE_RULES,
    NON_ESCALATION_TEMPLATE,
)

# STR Gate (Positive STR Checklist)
from .str_gate import (
    STRDecision,
    STRCheck,
    STRSectionResult,
    STRGateResult,
    STRGateValidator,
    run_str_gate,
    dual_gate_decision,
    STR_RATIONALE_TEMPLATE,
    NO_STR_RATIONALE_TEMPLATE,
)
