"""
ClaimPilot - Universal Insurance Claims Decision Guidance Framework

ClaimPilot provides guided workflows for insurance claims adjusters.
It produces RECOMMENDATIONS, not decisions — the human adjuster decides.

Core Principle: "The adjuster decides. ClaimPilot recommends and documents."

Key Features:
- Line-of-business agnostic (auto, property, health, workers comp, etc.)
- Policy rule surfacing based on claim context
- Evidence requirement enforcement
- Reasoning capture at the moment of evaluation
- Escalation/authority routing
- Citation of authorities (policy wording, regulations)
- Precedent surfacing (similar past cases)

Quick Start:
    from claimpilot.models import (
        Policy, ClaimContext, RecommendationRecord,
        TriBool, AND, OR, EQ,
    )
    from claimpilot.engine import (
        PolicyEngine, ContextResolver, RecommendationBuilder,
    )

    # Load policy pack
    engine = PolicyEngine()
    policy = engine.load_policy("packs/auto_insurance.yaml")

    # Resolve claim context
    resolver = ContextResolver(engine)
    context = resolver.resolve(claim_id="CLM-001", ...)

    # Build recommendation
    builder = RecommendationBuilder(context)
    recommendation = builder.build()

Version: 0.1.0
"""
from __future__ import annotations

__version__ = "0.1.0"
__author__ = "ClaimPilot Team"

# =============================================================================
# Core Models (Re-exported for convenience)
# =============================================================================
from .models import (
    # Enums
    AuthorityType,
    ClaimantType,
    ConditionOperator,
    DispositionType,
    EvidenceStatus,
    FactCertainty,
    FactSource,
    GateStrictness,
    LineOfBusiness,
    PrecedentOutcome,
    ReasoningStepResult,
    ReasoningStepType,
    RecommendationCertainty,
    SealStatus,
    TimelineAnchor,
    TimelineEventType,
    # Conditions
    TriBool,
    EvaluationResult,
    Predicate,
    Condition,
    ConditionDefinition,
    AND,
    OR,
    NOT,
    PRED,
    EQ,
    NE,
    GT,
    GTE,
    LT,
    LTE,
    IN,
    NOT_IN,
    IS_NULL,
    IS_NOT_NULL,
    CONTAINS,
    BETWEEN,
    # Authority
    AuthorityRef,
    AuthorityRule,
    AuthorityRegistry,
    # Policy
    CoverageLimits,
    Deductibles,
    LossTypeTrigger,
    CoverageSection,
    Exclusion,
    Policy,
    # Claim
    Fact,
    EvidenceItem,
    ClaimContext,
    FactSet,
    # Timeline
    TimelineRule,
    TimelineEvent,
    TimelineSummary,
    # Evidence
    DocumentRequirement,
    EvidenceRule,
    EvidenceGateResult,
    EvidenceChecklist,
    EvidenceChecklistItem,
    # Precedent
    PrecedentKey,
    PrecedentHit,
    PrecedentRecord,
    SimilarityWeights,
    precedent_sort_key,
    sort_precedents,
    # Recommendation
    AuthorityCitation,
    ReasoningStep,
    RecommendationRecord,
    RecommendationMemo,
    # Disposition
    FinalDisposition,
    DispositionApproval,
    DispositionAuditEntry,
)

# =============================================================================
# Utilities
# =============================================================================
from .canon import (
    canonical_json,
    canonical_json_bytes,
    content_hash,
    content_hash_short,
    text_hash,
    text_hash_short,
    normalize_excerpt,
    excerpt_hash,
    compute_policy_pack_hash,
)

# =============================================================================
# Exceptions
# =============================================================================
from .exceptions import (
    ClaimPilotError,
    PolicyLoadError,
    PolicyValidationError,
    PolicyVersionMismatch,
    PolicyNotFoundError,
    ClaimContextError,
    MissingFactError,
    FactConflictError,
    InvalidFactValueError,
    ConditionEvaluationError,
    InvalidConditionError,
    FieldPathError,
    EvidenceGateError,
    MissingEvidenceError,
    TimelineCalculationError,
    DeadlineExceededError,
    InvalidCalendarError,
    AuthorityNotFoundError,
    AuthorityHashMismatch,
    PrecedentMatchError,
    PrecedentNotFoundError,
    RecommendationError,
    RecommendationIncompleteError,
    DispositionError,
    DispositionSealedError,
    EscalationRequiredError,
)

# =============================================================================
# Public API
# =============================================================================
__all__ = [
    # Version
    "__version__",
    # Enums
    "AuthorityType",
    "ClaimantType",
    "ConditionOperator",
    "DispositionType",
    "EvidenceStatus",
    "FactCertainty",
    "FactSource",
    "GateStrictness",
    "LineOfBusiness",
    "PrecedentOutcome",
    "ReasoningStepResult",
    "ReasoningStepType",
    "RecommendationCertainty",
    "SealStatus",
    "TimelineAnchor",
    "TimelineEventType",
    # Conditions
    "TriBool",
    "EvaluationResult",
    "Predicate",
    "Condition",
    "ConditionDefinition",
    "AND",
    "OR",
    "NOT",
    "PRED",
    "EQ",
    "NE",
    "GT",
    "GTE",
    "LT",
    "LTE",
    "IN",
    "NOT_IN",
    "IS_NULL",
    "IS_NOT_NULL",
    "CONTAINS",
    "BETWEEN",
    # Authority
    "AuthorityRef",
    "AuthorityRule",
    "AuthorityRegistry",
    # Policy
    "CoverageLimits",
    "Deductibles",
    "LossTypeTrigger",
    "CoverageSection",
    "Exclusion",
    "Policy",
    # Claim
    "Fact",
    "EvidenceItem",
    "ClaimContext",
    "FactSet",
    # Timeline
    "TimelineRule",
    "TimelineEvent",
    "TimelineSummary",
    # Evidence
    "DocumentRequirement",
    "EvidenceRule",
    "EvidenceGateResult",
    "EvidenceChecklist",
    "EvidenceChecklistItem",
    # Precedent
    "PrecedentKey",
    "PrecedentHit",
    "PrecedentRecord",
    "SimilarityWeights",
    "precedent_sort_key",
    "sort_precedents",
    # Recommendation
    "AuthorityCitation",
    "ReasoningStep",
    "RecommendationRecord",
    "RecommendationMemo",
    # Disposition
    "FinalDisposition",
    "DispositionApproval",
    "DispositionAuditEntry",
    # Utilities
    "canonical_json",
    "canonical_json_bytes",
    "content_hash",
    "content_hash_short",
    "text_hash",
    "text_hash_short",
    "normalize_excerpt",
    "excerpt_hash",
    "compute_policy_pack_hash",
    # Exceptions
    "ClaimPilotError",
    "PolicyLoadError",
    "PolicyValidationError",
    "PolicyVersionMismatch",
    "PolicyNotFoundError",
    "ClaimContextError",
    "MissingFactError",
    "FactConflictError",
    "InvalidFactValueError",
    "ConditionEvaluationError",
    "InvalidConditionError",
    "FieldPathError",
    "EvidenceGateError",
    "MissingEvidenceError",
    "TimelineCalculationError",
    "DeadlineExceededError",
    "InvalidCalendarError",
    "AuthorityNotFoundError",
    "AuthorityHashMismatch",
    "PrecedentMatchError",
    "PrecedentNotFoundError",
    "RecommendationError",
    "RecommendationIncompleteError",
    "DispositionError",
    "DispositionSealedError",
    "EscalationRequiredError",
]
