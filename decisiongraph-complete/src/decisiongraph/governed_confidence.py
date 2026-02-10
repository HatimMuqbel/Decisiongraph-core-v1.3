"""
Governed Confidence Model — v3 Precedent Engine Layer 3.

Four-dimension model where the weakest dimension caps the entire score.
This prevents any single strength from masking a fundamental gap.

Dimensions:
  1. Pool Adequacy — how many precedents passed gates + floor
  2. Similarity Quality — average similarity in the scored pool
  3. Outcome Consistency — decisive agreement among terminal precedents
  4. Evidence Completeness — % of required fields present in case

Formula: final_confidence = min(all dimensions)

Spec: DecisionGraph_Precedent_Engine_v3_Specification.md Section 6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from decisiongraph.domain_registry import ConfidenceLevel, DomainRegistry


# ---------------------------------------------------------------------------
# Dimension result
# ---------------------------------------------------------------------------

@dataclass
class ConfidenceDimension:
    """Result of evaluating a single confidence dimension."""
    name: str
    value: float                        # raw numeric (0.0-1.0 or count)
    level: ConfidenceLevel
    bottleneck: bool = False            # True if this is the weakest dimension
    note: str = ""                      # explanation when relevant


# ---------------------------------------------------------------------------
# Governed confidence result
# ---------------------------------------------------------------------------

@dataclass
class GovernedConfidenceResult:
    """Complete governed confidence evaluation."""
    level: ConfidenceLevel
    numeric_value: float                # mapped from level for backward compat
    dimensions: list[ConfidenceDimension] = field(default_factory=list)
    hard_rule_applied: str | None = None  # which hard rule fired, if any
    bottleneck: str | None = None       # name of the weakest dimension


# ---------------------------------------------------------------------------
# Level → numeric mapping (for backward compatibility with v2 consumers)
# ---------------------------------------------------------------------------

_LEVEL_TO_NUMERIC = {
    ConfidenceLevel.NONE: 0.0,
    ConfidenceLevel.LOW: 0.25,
    ConfidenceLevel.MODERATE: 0.50,
    ConfidenceLevel.HIGH: 0.75,
    ConfidenceLevel.VERY_HIGH: 0.95,
}


# ---------------------------------------------------------------------------
# Dimension scoring functions
# ---------------------------------------------------------------------------

def _score_pool_adequacy(pool_size: int) -> ConfidenceDimension:
    """Score pool adequacy dimension (spec 6.2)."""
    if pool_size == 0:
        level = ConfidenceLevel.NONE
        note = "No comparable precedents above similarity threshold"
    elif pool_size <= 4:
        level = ConfidenceLevel.LOW
        note = "Precedent pool below minimum threshold"
    elif pool_size <= 14:
        level = ConfidenceLevel.MODERATE
        note = ""
    elif pool_size <= 49:
        level = ConfidenceLevel.HIGH
        note = ""
    else:
        level = ConfidenceLevel.VERY_HIGH
        note = ""

    return ConfidenceDimension(
        name="pool_adequacy",
        value=float(pool_size),
        level=level,
        note=note,
    )


def _score_similarity_quality(avg_similarity: float) -> ConfidenceDimension:
    """Score similarity quality dimension (spec 6.3)."""
    if avg_similarity < 0.50:
        level = ConfidenceLevel.LOW
        note = "No strongly comparable cases found"
    elif avg_similarity < 0.70:
        level = ConfidenceLevel.MODERATE
        note = ""
    elif avg_similarity < 0.85:
        level = ConfidenceLevel.HIGH
        note = ""
    else:
        level = ConfidenceLevel.VERY_HIGH
        note = ""

    return ConfidenceDimension(
        name="similarity_quality",
        value=avg_similarity,
        level=level,
        note=note,
    )


def _score_outcome_consistency(
    decisive_supporting: int,
    decisive_total: int,
) -> ConfidenceDimension:
    """Score outcome consistency dimension (spec 6.4).

    Returns N/A (represented as MODERATE with note) when no terminal precedents.
    """
    if decisive_total == 0:
        return ConfidenceDimension(
            name="outcome_consistency",
            value=0.0,
            level=ConfidenceLevel.MODERATE,
            note=(
                "No terminal precedents. All comparable cases are non-terminal "
                "(EDD/UNKNOWN). Confidence scoring requires resolved precedents."
            ),
        )

    agreement = decisive_supporting / decisive_total

    if agreement < 0.60:
        level = ConfidenceLevel.LOW
    elif agreement < 0.80:
        level = ConfidenceLevel.MODERATE
    elif agreement < 0.95:
        level = ConfidenceLevel.HIGH
    else:
        level = ConfidenceLevel.VERY_HIGH

    return ConfidenceDimension(
        name="outcome_consistency",
        value=agreement,
        level=level,
    )


def _score_evidence_completeness(
    domain: DomainRegistry,
    case_facts: dict[str, Any],
) -> ConfidenceDimension:
    """Score evidence completeness dimension (spec 6.5).

    Critical field override: if any critical field is missing, caps at LOW.
    """
    required_fields = [fd for fd in domain.fields.values() if fd.required]
    if not required_fields:
        return ConfidenceDimension(
            name="evidence_completeness",
            value=1.0,
            level=ConfidenceLevel.VERY_HIGH,
        )

    present = sum(1 for fd in required_fields if case_facts.get(fd.name) is not None)
    completeness = present / len(required_fields)

    # Critical field override (spec 6.5)
    missing_critical = [
        f for f in domain.critical_fields
        if case_facts.get(f) is None
    ]
    if missing_critical:
        return ConfidenceDimension(
            name="evidence_completeness",
            value=completeness,
            level=ConfidenceLevel.LOW,
            note=f"Critical fields missing: {', '.join(sorted(missing_critical))}",
        )

    if completeness < 0.80:
        level = ConfidenceLevel.LOW
        missing_count = len(required_fields) - present
        note = f"{missing_count} required fields missing"
    elif completeness < 0.90:
        level = ConfidenceLevel.MODERATE
        note = ""
    elif completeness < 0.95:
        level = ConfidenceLevel.HIGH
        note = ""
    else:
        level = ConfidenceLevel.VERY_HIGH
        note = ""

    return ConfidenceDimension(
        name="evidence_completeness",
        value=completeness,
        level=level,
        note=note,
    )


# ---------------------------------------------------------------------------
# Core: compute governed confidence (spec Section 6)
# ---------------------------------------------------------------------------

def compute_governed_confidence(
    domain: DomainRegistry,
    pool_size: int,
    avg_similarity: float,
    decisive_supporting: int,
    decisive_total: int,
    case_facts: dict[str, Any],
    non_transferable_count: int = 0,
) -> GovernedConfidenceResult:
    """Compute governed confidence using the 4-dimension min() model.

    Args:
        domain: DomainRegistry with field definitions and critical fields.
        pool_size: Number of precedents that passed gates + similarity floor.
        avg_similarity: Average similarity score across scored pool.
        decisive_supporting: Count of terminal precedents matching proposed disposition.
        decisive_total: Count of all terminal (ALLOW/BLOCK) precedents.
        case_facts: Dict of case field values for evidence completeness.
        non_transferable_count: Count of non-transferable precedents (informational).

    Returns:
        GovernedConfidenceResult with level, dimensions, and bottleneck.
    """
    # ── Compute all 4 dimensions ─────────────────────────────────
    dim_pool = _score_pool_adequacy(pool_size)
    dim_similarity = _score_similarity_quality(avg_similarity)
    dim_consistency = _score_outcome_consistency(decisive_supporting, decisive_total)
    dim_evidence = _score_evidence_completeness(domain, case_facts)

    dimensions = [dim_pool, dim_similarity, dim_consistency, dim_evidence]

    # ── Hard Rules (spec 6.7) — checked before formula ───────────
    hard_rule = None

    # Hard rule 1: 0 precedents above floor → NONE
    if pool_size == 0:
        hard_rule = "0 precedents above floor"
        final_level = ConfidenceLevel.NONE

    # Hard rule 2: all precedents < 50% similarity → capped at LOW
    elif avg_similarity < 0.50:
        hard_rule = "all precedents below 50% similarity"
        final_level = ConfidenceLevel.LOW

    # Hard rule 3: critical fields missing → capped at LOW
    elif dim_evidence.level == ConfidenceLevel.LOW and any(
        case_facts.get(f) is None for f in domain.critical_fields
    ):
        hard_rule = "critical fields missing"
        final_level = ConfidenceLevel.LOW

    # Hard rule 4: 0 decisive precedents → capped at MODERATE
    elif decisive_total == 0:
        hard_rule = "0 decisive precedents"
        final_level = min(
            ConfidenceLevel.MODERATE,
            min(d.level for d in dimensions),
        )

    # Hard rule 5: pool < 5 → capped at LOW
    elif pool_size < domain.pool_minimum:
        hard_rule = f"pool below minimum ({domain.pool_minimum})"
        final_level = min(
            ConfidenceLevel.LOW,
            min(d.level for d in dimensions),
        )

    else:
        # ── Standard formula: min(all dimensions) ────────────────
        final_level = min(d.level for d in dimensions)

    # ── Identify bottleneck ──────────────────────────────────────
    weakest = min(dimensions, key=lambda d: d.level)
    weakest.bottleneck = True
    bottleneck_name = weakest.name

    return GovernedConfidenceResult(
        level=final_level,
        numeric_value=_LEVEL_TO_NUMERIC[final_level],
        dimensions=dimensions,
        hard_rule_applied=hard_rule,
        bottleneck=bottleneck_name,
    )


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "ConfidenceDimension",
    "GovernedConfidenceResult",
    "compute_governed_confidence",
]
