"""
Precedent Scorer v3 — Three-Layer Comparability Model.

Implements Layer 2 (Causal Factor Alignment) scoring logic:
  - Registry-driven per-field comparison
  - Driver-aware asymmetric weighting (2x for drivers, 1x for context)
  - Non-transferable detection (driver mismatch/absent)
  - Per-typology similarity floor

This module is called by query_similar_precedents_v3() in main.py.

Spec: DecisionGraph_Precedent_Engine_v3_Specification.md Sections 5, 7.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from decisiongraph.domain_registry import (
    DomainRegistry,
    FieldDefinition,
    FieldTier,
)
from decisiongraph.field_comparators import compare_field


# ---------------------------------------------------------------------------
# Scoring result
# ---------------------------------------------------------------------------

@dataclass
class SimilarityResult:
    """Result of Layer 2 field-by-field similarity scoring."""
    score: float                                # normalized 0.0-1.0
    raw_score: float                            # unnormalized weighted sum
    total_weight: float                         # sum of evaluable weights
    non_transferable: bool = False
    non_transferable_reasons: list[str] = field(default_factory=list)
    matched_drivers: list[str] = field(default_factory=list)
    mismatched_drivers: list[str] = field(default_factory=list)
    matched_context: list[str] = field(default_factory=list)
    field_scores: dict[str, float] = field(default_factory=dict)
    evaluable_fields: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core scoring function (spec Section 5.4)
# ---------------------------------------------------------------------------

def score_similarity(
    domain: DomainRegistry,
    case_facts: dict[str, Any],
    precedent_facts: dict[str, Any],
    precedent_drivers: list[str] | None = None,
) -> SimilarityResult:
    """Score similarity between a case and a precedent using the domain registry.

    Args:
        domain: DomainRegistry with field definitions.
        case_facts: Dict of case field values (canonical names).
        precedent_facts: Dict of precedent field values (canonical names).
        precedent_drivers: List of field names that were decision drivers
            for the precedent. If empty/None, all fields scored at 1x weight.

    Returns:
        SimilarityResult with normalized score, non-transferable flag, and breakdown.
    """
    drivers = set(precedent_drivers or [])
    scoring_fields = domain.get_scoring_fields()

    raw_score = 0.0
    total_weight = 0.0
    field_scores: dict[str, float] = {}
    evaluable_fields: list[str] = []
    missing_fields: list[str] = []
    matched_drivers: list[str] = []
    mismatched_drivers: list[str] = []
    matched_context: list[str] = []
    non_transferable = False
    non_transferable_reasons: list[str] = []

    for fd in scoring_fields:
        case_val = case_facts.get(fd.name)
        prec_val = precedent_facts.get(fd.name)
        is_driver = fd.name in drivers

        # Both missing → skip (field not evaluable)
        if case_val is None and prec_val is None:
            missing_fields.append(fd.name)
            continue

        # Driver absent from case → non-transferable (spec 5.4)
        if is_driver and case_val is None:
            non_transferable = True
            non_transferable_reasons.append(
                f"{fd.label} was a decision driver but is missing from current case"
            )
            missing_fields.append(fd.name)
            continue

        # Precedent value missing → skip
        if prec_val is None:
            missing_fields.append(fd.name)
            continue

        # Case value missing (non-driver) → skip
        if case_val is None:
            missing_fields.append(fd.name)
            continue

        # Compute field match score
        match_score = compare_field(fd, case_val, prec_val)
        field_scores[fd.name] = match_score
        evaluable_fields.append(fd.name)

        # Driver-aware weighting: 2x for drivers, 1x for context
        multiplier = 2.0 if is_driver else 1.0

        # Driver mismatch → non-transferable (spec 5.4)
        if is_driver and match_score == 0.0:
            non_transferable = True
            non_transferable_reasons.append(
                f"{fd.label}: precedent={prec_val}, current={case_val} — driver contradiction"
            )
            mismatched_drivers.append(fd.name)
        elif is_driver and match_score > 0.0:
            matched_drivers.append(fd.name)
        elif match_score > 0.0:
            matched_context.append(fd.name)

        raw_score += fd.weight * multiplier * match_score
        total_weight += fd.weight * multiplier

    # Normalize
    normalized = raw_score / total_weight if total_weight > 0 else 0.0

    return SimilarityResult(
        score=normalized,
        raw_score=raw_score,
        total_weight=total_weight,
        non_transferable=non_transferable,
        non_transferable_reasons=non_transferable_reasons,
        matched_drivers=matched_drivers,
        mismatched_drivers=mismatched_drivers,
        matched_context=matched_context,
        field_scores=field_scores,
        evaluable_fields=evaluable_fields,
        missing_fields=missing_fields,
    )


# ---------------------------------------------------------------------------
# Match classification v3 (spec Section 7, INV-011)
# ---------------------------------------------------------------------------

def classify_match_v3(
    case_disposition: str,
    precedent_disposition: str,
    case_basis: str,
    precedent_basis: str,
    non_transferable: bool = False,
) -> str:
    """Classify a precedent match using v3 rules.

    v3 adds INV-011: non-transferable precedents cannot be "supporting".

    Returns: "supporting", "contrary", or "neutral"
    """
    # INV-003: UNKNOWN is always neutral
    if precedent_disposition == "UNKNOWN" or case_disposition == "UNKNOWN":
        return "neutral"

    # INV-005: EDD is always neutral (procedural, not terminal)
    if precedent_disposition == "EDD" or case_disposition == "EDD":
        # Exception: EDD == EDD is supporting (same disposition)
        if precedent_disposition == "EDD" and case_disposition == "EDD":
            if non_transferable:
                return "neutral"  # INV-011
            return "supporting"
        return "neutral"

    # INV-008: cross-basis is neutral
    if (case_basis not in ("UNKNOWN", "")
            and precedent_basis not in ("UNKNOWN", "")
            and case_basis != precedent_basis):
        return "neutral"

    # Same disposition → supporting (unless non-transferable)
    if precedent_disposition == case_disposition:
        if non_transferable:
            return "neutral"  # INV-011: non-transferable cannot be supporting
        return "supporting"

    # INV-004: only ALLOW vs BLOCK is contrary
    if {precedent_disposition, case_disposition} == {"ALLOW", "BLOCK"}:
        return "contrary"

    return "neutral"


# ---------------------------------------------------------------------------
# Typology detection for similarity floor overrides
# ---------------------------------------------------------------------------

def detect_primary_typology(
    reason_codes: list[str],
    case_facts: dict[str, Any] | None = None,
) -> str | None:
    """Detect the primary typology for similarity floor override.

    Returns the typology key matching DomainRegistry.similarity_floor_overrides,
    or None if no specific typology detected.
    """
    codes_upper = [c.upper() for c in (reason_codes or [])]
    facts = case_facts or {}

    # Sanctions — highest priority
    if any("SANCTION" in c or "RC-SCR" in c for c in codes_upper):
        return "sanctions"
    if facts.get("screening.sanctions_match") in (True, "true", "True"):
        return "sanctions"

    # Structuring
    if any("STRUCT" in c for c in codes_upper):
        return "structuring"
    if facts.get("flag.structuring") in (True, "true", "True"):
        return "structuring"

    # Adverse media
    if any("ADVERSE" in c for c in codes_upper):
        return "adverse_media"
    if facts.get("screening.adverse_media") in (True, "true", "True"):
        return "adverse_media"

    return None


# ---------------------------------------------------------------------------
# Helper: extract scoring facts from anchor_facts list
# ---------------------------------------------------------------------------

def anchor_facts_to_dict(anchor_facts: list) -> dict[str, Any]:
    """Convert a list of AnchorFact objects/dicts to a flat dict for scoring."""
    result: dict[str, Any] = {}
    for af in anchor_facts:
        if isinstance(af, dict):
            fid = af.get("field_id", "")
            val = af.get("value")
        else:
            fid = getattr(af, "field_id", "")
            val = getattr(af, "value", None)
        if fid:
            result[fid] = val
    return result


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "SimilarityResult",
    "score_similarity",
    "classify_match_v3",
    "detect_primary_typology",
    "anchor_facts_to_dict",
]
