"""
ClaimPilot Engine

Core services for claim evaluation and recommendation building.

Services:
- PolicyEngine: Load and manage policy packs
- ContextResolver: Resolve what rules apply to a claim
- ConditionEvaluator: Evaluate composable conditions
- TimelineCalculator: Calculate regulatory timelines
- EvidenceGate: Enforce evidence requirements
- AuthorityRouter: Route escalations
- PrecedentFinder: Find similar past cases
- RecommendationBuilder: Build recommendations

Usage:
    from claimpilot.engine import (
        PolicyEngine,
        ContextResolver,
        ConditionEvaluator,
        TimelineCalculator,
        EvidenceGate,
        AuthorityRouter,
        PrecedentFinder,
        RecommendationBuilder,
    )
"""
from __future__ import annotations

# Phase 3: Core Engine
from .condition_evaluator import (
    ConditionEvaluator,
    check_condition,
    compare_values,
    evaluate_condition,
    get_fact_value,
    resolve_field_path,
)
from .context_resolver import (
    ContextResolver,
    CoverageMatch,
    ExclusionMatch,
    FullContextResolver,
    ResolvedContext,
    get_applicable_exclusions,
    get_triggered_coverages,
    resolve_context,
)
from .policy_engine import (
    PolicyEngine,
    get_default_engine,
    get_policy,
    load_policy,
)
from .timeline_calculator import (
    CalculatedDeadline,
    DeadlineStatus,
    FSRATimelineChecker,
    TimelineCalculator,
    add_business_days,
    calculate_deadline,
    is_business_day,
)

# Phase 4: Recommendation Flow
from .authority_router import (
    AuthorityRouter,
    AuthorityRoutingResult,
    RoleRequirement,
    SIUReferralResult,
    check_siu_referral,
    get_required_role,
    requires_escalation,
    route_authority,
)
from .evidence_gate import (
    DocumentStatus,
    EvidenceChecklist,
    EvidenceGate,
    EvidenceGateResult,
    check_evidence_complete,
    evaluate_evidence,
    generate_evidence_checklist,
)
from .precedent_finder import (
    PrecedentFinder,
    PrecedentRecord,
    build_precedent_key,
    build_precedent_key_from_policy,
    compute_case_similarity,
    compute_similarity_score,
    find_similar_cases,
    jaccard_similarity,
)
from .recommendation_builder import (
    RecommendationBuilder,
    build_recommendation,
    quick_recommendation,
)

__all__ = [
    # Condition Evaluator
    "ConditionEvaluator",
    "evaluate_condition",
    "check_condition",
    "compare_values",
    "get_fact_value",
    "resolve_field_path",
    # Context Resolver
    "ContextResolver",
    "FullContextResolver",
    "ResolvedContext",
    "CoverageMatch",
    "ExclusionMatch",
    "resolve_context",
    "get_triggered_coverages",
    "get_applicable_exclusions",
    # Policy Engine
    "PolicyEngine",
    "get_default_engine",
    "load_policy",
    "get_policy",
    # Timeline Calculator
    "TimelineCalculator",
    "CalculatedDeadline",
    "DeadlineStatus",
    "FSRATimelineChecker",
    "calculate_deadline",
    "add_business_days",
    "is_business_day",
    # Evidence Gate
    "EvidenceGate",
    "EvidenceGateResult",
    "DocumentStatus",
    "EvidenceChecklist",
    "evaluate_evidence",
    "check_evidence_complete",
    "generate_evidence_checklist",
    # Authority Router
    "AuthorityRouter",
    "AuthorityRoutingResult",
    "RoleRequirement",
    "SIUReferralResult",
    "route_authority",
    "get_required_role",
    "requires_escalation",
    "check_siu_referral",
    # Precedent Finder
    "PrecedentFinder",
    "PrecedentRecord",
    "build_precedent_key",
    "build_precedent_key_from_policy",
    "find_similar_cases",
    "compute_similarity_score",
    "compute_case_similarity",
    "jaccard_similarity",
    # Recommendation Builder
    "RecommendationBuilder",
    "build_recommendation",
    "quick_recommendation",
]
