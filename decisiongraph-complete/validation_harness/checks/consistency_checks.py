"""Consistency checks (C1-C5): Verify cross-field consistency."""
from __future__ import annotations

from ..catalog import register_check
from ..types import CheckCategory, FixSuggestion, Severity, Violation


def _pa(ctx: dict) -> dict:
    return ctx.get("precedent_analysis", {}) or {}


def _tap(ctx: dict) -> dict:
    return _pa(ctx).get("two_axis_pool", {}) or {}


# ── C1: governed_disposition maps to canonical_outcome.disposition ────────

@register_check(
    id="C1",
    category=CheckCategory.C,
    severity=Severity.ERROR,
    description="governed_disposition == canonical_outcome.disposition",
)
def check_c1(ctx: dict, case_id: str) -> list[Violation]:
    governed = ctx.get("governed_disposition", "")
    canonical = ctx.get("canonical_outcome", {}) or {}
    canonical_disp = canonical.get("disposition", "")

    if not governed or not canonical_disp:
        return []

    if governed != canonical_disp:
        return [Violation(
            check_id="C1",
            severity=Severity.ERROR,
            case_id=case_id,
            message=(
                f"governed_disposition ('{governed}') != "
                f"canonical_outcome.disposition ('{canonical_disp}')"
            ),
            current_value=governed,
            expected_value=canonical_disp,
            fix_suggestion=FixSuggestion(
                file="service/routers/report/derive.py",
                function="derive_all (canonical_outcome construction)",
                line_range="351-356",
                before_snippet='canonical_outcome = {"disposition": governed_disposition, ...}',
                after_snippet="governed_disposition should always equal canonical_outcome.disposition",
                root_cause_id="derive-canonical-consistency",
                explanation="canonical_outcome.disposition is set from governed_disposition in derive_all",
            ),
        )]
    return []


# ── C2: classification_outcome == STR_REQUIRED → str_required == True ────

@register_check(
    id="C2",
    category=CheckCategory.C,
    severity=Severity.ERROR,
    description="If classification_outcome == STR_REQUIRED then str_required == True",
)
def check_c2(ctx: dict, case_id: str) -> list[Violation]:
    classification_outcome = ctx.get("classification_outcome", "")
    str_required = ctx.get("str_required", False)
    governed = ctx.get("governed_disposition", "")

    if classification_outcome != "STR_REQUIRED" or str_required:
        return []

    # When governed disposition is EDD_REQUIRED or ESCALATE, the classifier's
    # STR_REQUIRED is acknowledged but reporting is deferred pending EDD.
    # str_required stays False — this is by design (FIX-023 pattern).
    if governed in ("EDD_REQUIRED", "ESCALATE"):
        return []

    # Only flag when governed disposition is STR_REQUIRED but str_required is False
    if governed == "STR_REQUIRED":
        return [Violation(
            check_id="C2",
            severity=Severity.ERROR,
            case_id=case_id,
            message=(
                f"governed_disposition is '{governed}' with "
                f"classification_outcome='STR_REQUIRED' but str_required is {str_required}"
            ),
            current_value=str_required,
            expected_value=True,
            fix_suggestion=FixSuggestion(
                file="service/routers/report/derive.py",
                function="derive_all (str_required derivation)",
                line_range="250-300",
                before_snippet="str_required derived from classifier + governed disposition",
                after_snippet="When governed disposition is STR_REQUIRED, str_required must be True",
                root_cause_id="derive-str-required",
                explanation="STR_REQUIRED governed disposition must set str_required=True",
            ),
        )]
    return []


# ── C3: Recount sample_cases classifications ────────────────────────────

@register_check(
    id="C3",
    category=CheckCategory.C,
    severity=Severity.WARNING,
    description="Recount sample_cases classifications matches pa[supporting/contrary/neutral]",
)
def check_c3(ctx: dict, case_id: str) -> list[Violation]:
    pa = _pa(ctx)
    if not pa.get("available"):
        return []

    sample_cases = pa.get("sample_cases", []) or []
    if not sample_cases:
        return []

    # Recount from sample_cases classification field
    supporting = 0
    contrary = 0
    neutral = 0
    for sc in sample_cases:
        cls = sc.get("classification", "neutral")
        if cls == "supporting":
            supporting += 1
        elif cls == "contrary":
            contrary += 1
        else:
            neutral += 1

    # Compare against PA counts — but note: PA counts may reflect governed
    # reclassification which updates counts but not sample_case.classification fields.
    # Also, pa counts cover the full match pool (match_count), not just sample.
    # So we only compare if sample_size == match_count (no sampling).
    pa_supporting = int(pa.get("supporting_precedents", 0) or 0)
    pa_contrary = int(pa.get("contrary_precedents", 0) or 0)
    pa_neutral = int(pa.get("neutral_precedents", 0) or 0)
    match_count = int(pa.get("match_count", 0) or 0)
    sample_size = int(pa.get("sample_size", 0) or 0)

    # Only check if the actual sample_cases array covers the full sample.
    # PA response truncates sample_cases to 10 (line 3498: sample_cases[:10]),
    # so we can only validate when sample_size <= 10 AND sample_size == match_count.
    actual_samples = len(sample_cases)
    if sample_size != match_count or actual_samples < sample_size:
        return []

    violations = []
    if supporting != pa_supporting:
        violations.append(Violation(
            check_id="C3",
            severity=Severity.WARNING,
            case_id=case_id,
            message=(
                f"sample_cases supporting recount ({supporting}) != "
                f"pa.supporting_precedents ({pa_supporting})"
            ),
            current_value=supporting,
            expected_value=pa_supporting,
        ))
    if contrary != pa_contrary:
        violations.append(Violation(
            check_id="C3",
            severity=Severity.WARNING,
            case_id=case_id,
            message=(
                f"sample_cases contrary recount ({contrary}) != "
                f"pa.contrary_precedents ({pa_contrary})"
            ),
            current_value=contrary,
            expected_value=pa_contrary,
        ))
    if neutral != pa_neutral:
        violations.append(Violation(
            check_id="C3",
            severity=Severity.WARNING,
            case_id=case_id,
            message=(
                f"sample_cases neutral recount ({neutral}) != "
                f"pa.neutral_precedents ({pa_neutral})"
            ),
            current_value=neutral,
            expected_value=pa_neutral,
        ))
    return violations


# ── C4: two_axis_pool.total == match_count ───────────────────────────────

@register_check(
    id="C4",
    category=CheckCategory.C,
    severity=Severity.ERROR,
    description="two_axis_pool.total == match_count",
)
def check_c4(ctx: dict, case_id: str) -> list[Violation]:
    pa = _pa(ctx)
    if not pa.get("available"):
        return []

    match_count = int(pa.get("match_count", 0) or 0)
    tap = _tap(ctx)
    pool_total = tap.get("total", 0)

    if pool_total != match_count:
        return [Violation(
            check_id="C4",
            severity=Severity.ERROR,
            case_id=case_id,
            message=(
                f"two_axis_pool.total ({pool_total}) != match_count ({match_count})"
            ),
            current_value=pool_total,
            expected_value=match_count,
            fix_suggestion=FixSuggestion(
                file="service/main.py",
                function="check_precedent (two-axis pool)",
                line_range="3436,3455",
                before_snippet="two_axis_total = len(scored_matches)",
                after_snippet="Pool total should equal len(scored_matches) == match_count",
                root_cause_id="main-pool-total",
                explanation="two_axis_pool iterates over scored_matches, same set as match_count",
            ),
        )]
    return []


# ── C5: sum(composite_label_distribution) == two_axis_pool.total ─────────

@register_check(
    id="C5",
    category=CheckCategory.C,
    severity=Severity.ERROR,
    description="sum(composite_label_distribution.values()) == two_axis_pool.total",
)
def check_c5(ctx: dict, case_id: str) -> list[Violation]:
    tap = _tap(ctx)
    if not tap or tap.get("total", 0) == 0:
        return []

    dist = tap.get("composite_label_distribution", {}) or {}
    dist_sum = sum(dist.values())
    pool_total = tap["total"]

    if dist_sum != pool_total:
        return [Violation(
            check_id="C5",
            severity=Severity.ERROR,
            case_id=case_id,
            message=(
                f"sum(composite_label_distribution) ({dist_sum}) != "
                f"two_axis_pool.total ({pool_total}). Distribution: {dist}"
            ),
            current_value=dist_sum,
            expected_value=pool_total,
            fix_suggestion=FixSuggestion(
                file="service/main.py",
                function="check_precedent (two-axis pool)",
                line_range="3437-3449",
                before_snippet="composite_label_counts accumulated over scored_matches",
                after_snippet="Every scored_match gets exactly one composite_label",
                root_cause_id="main-composite-dist-sum",
                explanation="Every scored_match has exactly one composite_label, so distribution must sum to total",
            ),
        )]
    return []
