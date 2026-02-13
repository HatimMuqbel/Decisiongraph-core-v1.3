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

from kernel.precedent.domain_registry import (
    DomainRegistry,
    FieldDefinition,
    FieldTier,
)
from kernel.precedent.field_comparators import compare_field


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
    assert 0.0 <= normalized <= 1.0, (
        f"Similarity score {normalized:.4f} out of bounds "
        f"(raw={raw_score:.4f}, weight={total_weight:.4f})"
    )

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
# Two-axis classification (Operational Disposition × Regulatory Suspicion)
# ---------------------------------------------------------------------------

# Suspicion-positive reporting values (STR filed or required)
_SUSPICION_POSITIVE: frozenset[str] = frozenset({
    "FILE_STR", "STR", "STR_REQUIRED",
})

# Suspicion-negative reporting values (no ML/TF suspicion)
_SUSPICION_NEGATIVE: frozenset[str] = frozenset({
    "NO_REPORT", "FILE_LCTR", "FILE_TPR",
})

# Undetermined reporting values (EDD not yet resolved)
_SUSPICION_UNDETERMINED: frozenset[str] = frozenset({
    "PENDING_EDD", "UNDETERMINED", "UNKNOWN", "",
})


def _normalize_reporting(reporting: str) -> str:
    """Map raw reporting value to suspicion posture: STR, NO_STR, or UNDETERMINED."""
    val = (reporting or "").upper().strip()
    if val in _SUSPICION_POSITIVE:
        return "STR"
    if val in _SUSPICION_NEGATIVE:
        return "NO_STR"
    return "UNDETERMINED"


def _op_alignment(case_disp: str, prec_disp: str) -> str:
    """Compare operational dispositions → ALIGNED, PARTIAL, or CONTRARY."""
    if case_disp == prec_disp:
        return "ALIGNED"
    # Adjacent tiers: EDD is adjacent to both ALLOW and BLOCK
    if "EDD" in (case_disp, prec_disp):
        return "PARTIAL"
    # ALLOW vs BLOCK is contrary
    if {case_disp, prec_disp} == {"ALLOW", "BLOCK"}:
        return "CONTRARY"
    # Fallback (shouldn't happen with standard dispositions)
    return "PARTIAL"


def _suspicion_alignment(case_reporting: str, prec_reporting: str) -> str:
    """Compare regulatory suspicion postures → ALIGNED, CONTRARY, or UNDETERMINED."""
    case_susp = _normalize_reporting(case_reporting)
    prec_susp = _normalize_reporting(prec_reporting)
    if case_susp == "UNDETERMINED" or prec_susp == "UNDETERMINED":
        return "UNDETERMINED"
    if case_susp == prec_susp:
        return "ALIGNED"
    return "CONTRARY"


# Composite label lookup: (op_alignment, suspicion_alignment) → label
_COMPOSITE_LABELS: dict[tuple[str, str], str] = {
    ("ALIGNED", "ALIGNED"): "FULLY_SUPPORTING",
    ("ALIGNED", "CONTRARY"): "OP_ALIGNED_REG_DIVERGENT",
    ("ALIGNED", "UNDETERMINED"): "OP_ALIGNED_REG_PENDING",
    ("PARTIAL", "ALIGNED"): "PARTIALLY_SUPPORTING",
    ("PARTIAL", "CONTRARY"): "PARTIAL_WITH_DIVERGENCE",
    ("PARTIAL", "UNDETERMINED"): "PARTIAL_REG_PENDING",
    ("CONTRARY", "ALIGNED"): "OP_CONTRARY_REG_ALIGNED",
    ("CONTRARY", "CONTRARY"): "FULLY_CONTRARY",
    ("CONTRARY", "UNDETERMINED"): "OP_CONTRARY_REG_PENDING",
}

# Human-readable descriptions for each composite label
_COMPOSITE_DESCRIPTIONS: dict[str, str] = {
    "FULLY_SUPPORTING": "Operationally and regulatorily aligned.",
    "OP_ALIGNED_REG_DIVERGENT": "Same operational action, different suspicion finding.",
    "OP_ALIGNED_REG_PENDING": "Same operational action, reporting pending.",
    "PARTIALLY_SUPPORTING": "Different operational tier, same suspicion posture.",
    "PARTIAL_WITH_DIVERGENCE": "Different operational tier and suspicion posture.",
    "PARTIAL_REG_PENDING": "Different operational tier, reporting pending.",
    "OP_CONTRARY_REG_ALIGNED": "Opposite operational action, same suspicion finding.",
    "FULLY_CONTRARY": "Operationally and regulatorily divergent.",
    "OP_CONTRARY_REG_PENDING": "Opposite operational action, reporting pending.",
}


@dataclass(frozen=True)
class TwoAxisClassification:
    """Two-axis classification result for a precedent match."""
    op_alignment: str           # ALIGNED | PARTIAL | CONTRARY
    suspicion_alignment: str    # ALIGNED | CONTRARY | UNDETERMINED
    composite_label: str        # e.g. FULLY_SUPPORTING
    composite_description: str  # Human-readable description
    case_suspicion: str         # Normalized: STR | NO_STR | UNDETERMINED
    precedent_suspicion: str    # Normalized: STR | NO_STR | UNDETERMINED

    def to_dict(self) -> dict:
        return {
            "op_alignment": self.op_alignment,
            "suspicion_alignment": self.suspicion_alignment,
            "composite_label": self.composite_label,
            "composite_description": self.composite_description,
            "case_suspicion": self.case_suspicion,
            "precedent_suspicion": self.precedent_suspicion,
        }


def classify_match_two_axis(
    case_disposition: str,
    precedent_disposition: str,
    case_reporting: str,
    precedent_reporting: str,
    non_transferable: bool = False,
) -> TwoAxisClassification:
    """Classify a precedent match on two axes: operational disposition and regulatory suspicion.

    Returns a TwoAxisClassification with independent op and suspicion alignment,
    plus a composite label combining both.
    """
    # Normalize dispositions
    c_disp = (case_disposition or "UNKNOWN").upper()
    p_disp = (precedent_disposition or "UNKNOWN").upper()

    # UNKNOWN dispositions → fully neutral
    if c_disp == "UNKNOWN" or p_disp == "UNKNOWN":
        return TwoAxisClassification(
            op_alignment="PARTIAL",
            suspicion_alignment="UNDETERMINED",
            composite_label="PARTIAL_REG_PENDING",
            composite_description=_COMPOSITE_DESCRIPTIONS["PARTIAL_REG_PENDING"],
            case_suspicion=_normalize_reporting(case_reporting),
            precedent_suspicion=_normalize_reporting(precedent_reporting),
        )

    op = _op_alignment(c_disp, p_disp)
    susp = _suspicion_alignment(case_reporting, precedent_reporting)

    composite = _COMPOSITE_LABELS.get((op, susp), "PARTIAL_REG_PENDING")
    description = _COMPOSITE_DESCRIPTIONS.get(composite, "")

    return TwoAxisClassification(
        op_alignment=op,
        suspicion_alignment=susp,
        composite_label=composite,
        composite_description=description,
        case_suspicion=_normalize_reporting(case_reporting),
        precedent_suspicion=_normalize_reporting(precedent_reporting),
    )


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
    "TwoAxisClassification",
    "classify_match_two_axis",
    "detect_primary_typology",
    "anchor_facts_to_dict",
]
