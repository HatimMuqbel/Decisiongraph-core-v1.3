"""
ClaimPilot Models

All domain models for the ClaimPilot insurance claims guidance framework.

Exports all models organized by category for convenient imports:

    from claimpilot.models import (
        # Enums
        LineOfBusiness, ClaimantType, DispositionType,
        # Conditions
        TriBool, Condition, Predicate, AND, OR, NOT, PRED,
        # Authority
        AuthorityRef, AuthorityRule,
        # Policy
        Policy, CoverageSection, Exclusion,
        # Claim
        ClaimContext, Fact, EvidenceItem,
        # Timeline
        TimelineRule, TimelineEvent,
        # Evidence
        EvidenceRule, DocumentRequirement,
        # Precedent
        PrecedentHit, PrecedentKey,
        # Recommendation
        RecommendationRecord, ReasoningStep, RecommendationMemo,
        # Disposition
        FinalDisposition,
    )
"""
from __future__ import annotations

# =============================================================================
# Enums
# =============================================================================
from .enums import (
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
)

# =============================================================================
# Conditions (TriBool + Composable Conditions)
# =============================================================================
from .conditions import (
    # Core types
    TriBool,
    EvaluationResult,
    Predicate,
    Condition,
    ConditionDefinition,
    # Helper functions
    AND,
    OR,
    NOT,
    PRED,
    # Convenience predicates
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
)

# =============================================================================
# Authority
# =============================================================================
from .authority import (
    AuthorityRef,
    AuthorityRule,
    AuthorityRegistry,
)

# =============================================================================
# Policy
# =============================================================================
from .policy import (
    CoverageLimits,
    Deductibles,
    LossTypeTrigger,
    CoverageSection,
    Exclusion,
    Policy,
)

# =============================================================================
# Claim
# =============================================================================
from .claim import (
    Fact,
    EvidenceItem,
    ClaimContext,
    FactSet,
)

# =============================================================================
# Timeline
# =============================================================================
from .timeline import (
    TimelineRule,
    TimelineEvent,
    TimelineSummary,
)

# =============================================================================
# Evidence
# =============================================================================
from .evidence import (
    DocumentRequirement,
    EvidenceRule,
    EvidenceGateResult,
    EvidenceChecklist,
    EvidenceChecklistItem,
)

# =============================================================================
# Precedent
# =============================================================================
from .precedent import (
    PrecedentKey,
    PrecedentHit,
    PrecedentRecord,
    SimilarityWeights,
    precedent_sort_key,
    sort_precedents,
)

# =============================================================================
# Recommendation
# =============================================================================
from .recommendation import (
    AuthorityCitation,
    ReasoningStep,
    RecommendationRecord,
    RecommendationMemo,
    # Precedent support (v2.0)
    AppealStats,
    PrecedentSummaryRecord,
    PrecedentMatchRecord,
    PrecedentQueryParamsRecord,
)

# =============================================================================
# Disposition
# =============================================================================
from .disposition import (
    FinalDisposition,
    DispositionApproval,
    DispositionAuditEntry,
)

# =============================================================================
# Public API
# =============================================================================
__all__ = [
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
    # Precedent support (v2.0)
    "AppealStats",
    "PrecedentSummaryRecord",
    "PrecedentMatchRecord",
    "PrecedentQueryParamsRecord",
    # Disposition
    "FinalDisposition",
    "DispositionApproval",
    "DispositionAuditEntry",
]
