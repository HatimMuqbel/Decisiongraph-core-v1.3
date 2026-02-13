"""Math checks (M1-M8): Verify numerical invariants in the report."""
from __future__ import annotations

from ..catalog import register_check
from ..types import CheckCategory, FixSuggestion, Severity, Violation


def _pa(ctx: dict) -> dict:
    return ctx.get("precedent_analysis", {}) or {}


def _ep(ctx: dict) -> dict:
    return ctx.get("enhanced_precedent", {}) or {}


def _tap(ctx: dict) -> dict:
    return _pa(ctx).get("two_axis_pool", {}) or {}


# ── M1: supporting + contrary + neutral == match_count ────────────────────

@register_check(
    id="M1",
    category=CheckCategory.M,
    severity=Severity.ERROR,
    description="supporting + contrary + neutral == sample_size (v3 counts from stratified sample)",
)
def check_m1(ctx: dict, case_id: str) -> list[Violation]:
    pa = _pa(ctx)
    if not pa.get("available"):
        return []

    supporting = int(pa.get("supporting_precedents", 0) or 0)
    contrary = int(pa.get("contrary_precedents", 0) or 0)
    neutral = int(pa.get("neutral_precedents", 0) or 0)
    # In v3, counts are from the stratified sample, not the full scored pool.
    # sample_size == len(sampled), match_count == len(scored_matches).
    sample_size = int(pa.get("sample_size", 0) or 0)

    total = supporting + contrary + neutral
    if total != sample_size:
        return [Violation(
            check_id="M1",
            severity=Severity.ERROR,
            case_id=case_id,
            message=(
                f"Classification sum mismatch: "
                f"supporting({supporting}) + contrary({contrary}) + neutral({neutral}) "
                f"= {total}, but sample_size = {sample_size}"
            ),
            current_value=total,
            expected_value=sample_size,
            fix_suggestion=FixSuggestion(
                file="service/main.py",
                function="check_precedent (response assembly)",
                line_range="3252-3256,3489-3491",
                before_snippet="counts from stratified sample; supporting + contrary + neutral != sample_size",
                after_snippet="Ensure stratified_sample counts cover all sampled matches",
                root_cause_id="main-classification-count",
                explanation="Classification counts should sum to sample_size (stratified sample in v3)",
            ),
        )]
    return []


# ── M2: Verify op_aligned via composite_label_distribution ───────────────

@register_check(
    id="M2",
    category=CheckCategory.M,
    severity=Severity.WARNING,
    description="op_aligned count consistent with composite_label_distribution",
)
def check_m2(ctx: dict, case_id: str) -> list[Violation]:
    tap = _tap(ctx)
    if not tap or tap.get("total", 0) == 0:
        return []

    op_aligned = tap.get("op_aligned", 0)
    dist = tap.get("composite_label_distribution", {}) or {}

    # op_aligned counts matches with op_alignment == "ALIGNED".
    # From _COMPOSITE_LABELS, op_alignment == "ALIGNED" produces:
    #   FULLY_SUPPORTING (ALIGNED, ALIGNED)
    #   OP_ALIGNED_REG_DIVERGENT (ALIGNED, CONTRARY)
    #   OP_ALIGNED_REG_PENDING (ALIGNED, UNDETERMINED)
    _op_aligned_labels = {"FULLY_SUPPORTING", "OP_ALIGNED_REG_DIVERGENT", "OP_ALIGNED_REG_PENDING"}
    recomputed = sum(
        v for k, v in dist.items()
        if k in _op_aligned_labels
    )

    if recomputed != op_aligned:
        return [Violation(
            check_id="M2",
            severity=Severity.WARNING,
            case_id=case_id,
            message=(
                f"op_aligned ({op_aligned}) != sum of OP_ALIGNED/FULLY_SUPPORTING labels ({recomputed}). "
                f"Distribution: {dist}"
            ),
            current_value=op_aligned,
            expected_value=recomputed,
            fix_suggestion=FixSuggestion(
                file="service/main.py",
                function="check_precedent (two-axis pool)",
                line_range="3431-3449",
                before_snippet="op_aligned counted via ta.op_alignment == 'ALIGNED'",
                after_snippet="Verify classify_match_two_axis sets op_alignment consistently with composite_label",
                root_cause_id="main-two-axis-op-aligned",
                explanation="op_aligned count should match composite labels starting with OP_ALIGNED/FULLY_SUPPORTING",
            ),
        )]
    return []


# ── M3: Verify reg_aligned via composite_label_distribution ──────────────

@register_check(
    id="M3",
    category=CheckCategory.M,
    severity=Severity.WARNING,
    description="reg_aligned count consistent with composite_label_distribution",
)
def check_m3(ctx: dict, case_id: str) -> list[Violation]:
    tap = _tap(ctx)
    if not tap or tap.get("total", 0) == 0:
        return []

    reg_aligned = tap.get("reg_aligned", 0)
    dist = tap.get("composite_label_distribution", {}) or {}

    # reg_aligned counts matches with suspicion_alignment == "ALIGNED".
    # From _COMPOSITE_LABELS, suspicion_alignment == "ALIGNED" produces:
    #   FULLY_SUPPORTING (ALIGNED, ALIGNED)
    #   PARTIALLY_SUPPORTING (PARTIAL, ALIGNED)
    #   OP_CONTRARY_REG_ALIGNED (CONTRARY, ALIGNED)
    _reg_aligned_labels = {"FULLY_SUPPORTING", "PARTIALLY_SUPPORTING", "OP_CONTRARY_REG_ALIGNED"}
    recomputed = sum(
        v for k, v in dist.items()
        if k in _reg_aligned_labels
    )

    if recomputed != reg_aligned:
        return [Violation(
            check_id="M3",
            severity=Severity.WARNING,
            case_id=case_id,
            message=(
                f"reg_aligned ({reg_aligned}) != sum of *REG_ALIGNED*/FULLY_SUPPORTING labels ({recomputed}). "
                f"Distribution: {dist}"
            ),
            current_value=reg_aligned,
            expected_value=recomputed,
            fix_suggestion=FixSuggestion(
                file="service/main.py",
                function="check_precedent (two-axis pool)",
                line_range="3431-3449",
                before_snippet="reg_aligned counted via ta.suspicion_alignment == 'ALIGNED'",
                after_snippet="Verify classify_match_two_axis sets suspicion_alignment consistently with composite_label",
                root_cause_id="main-two-axis-reg-aligned",
                explanation="reg_aligned count should match composite labels containing REG_ALIGNED/FULLY_SUPPORTING",
            ),
        )]
    return []


# ── M4: combined_aligned <= min(op_aligned, reg_aligned) ─────────────────

@register_check(
    id="M4",
    category=CheckCategory.M,
    severity=Severity.ERROR,
    description="combined_aligned <= min(op_aligned, reg_aligned)",
)
def check_m4(ctx: dict, case_id: str) -> list[Violation]:
    tap = _tap(ctx)
    if not tap or tap.get("total", 0) == 0:
        return []

    op_aligned = tap.get("op_aligned", 0)
    reg_aligned = tap.get("reg_aligned", 0)
    combined = tap.get("combined_aligned", 0)

    upper_bound = min(op_aligned, reg_aligned)
    if combined > upper_bound:
        return [Violation(
            check_id="M4",
            severity=Severity.ERROR,
            case_id=case_id,
            message=(
                f"combined_aligned ({combined}) > min(op_aligned={op_aligned}, "
                f"reg_aligned={reg_aligned}) = {upper_bound}"
            ),
            current_value=combined,
            expected_value=f"<= {upper_bound}",
            fix_suggestion=FixSuggestion(
                file="service/main.py",
                function="check_precedent (two-axis pool)",
                line_range="3443-3444",
                before_snippet="if ta.op_alignment == 'ALIGNED' and ta.suspicion_alignment == 'ALIGNED'",
                after_snippet="combined_aligned should be intersection of op and reg aligned",
                root_cause_id="main-two-axis-combined",
                explanation="combined_aligned is the intersection and must be <= min of both axes",
            ),
        )]
    return []


# ── M5: str_filing_rate_pct == round(str_filing_count / total * 100) ─────

@register_check(
    id="M5",
    category=CheckCategory.M,
    severity=Severity.WARNING,
    description="str_filing_rate_pct == round(str_filing_count / total * 100)",
)
def check_m5(ctx: dict, case_id: str) -> list[Violation]:
    tap = _tap(ctx)
    if not tap or tap.get("total", 0) == 0:
        return []

    total = tap["total"]
    str_count = tap.get("str_filing_count", 0)
    reported_pct = tap.get("str_filing_rate_pct", 0)
    expected_pct = int(round(str_count / total * 100))

    if reported_pct != expected_pct:
        return [Violation(
            check_id="M5",
            severity=Severity.WARNING,
            case_id=case_id,
            message=(
                f"str_filing_rate_pct ({reported_pct}) != "
                f"round({str_count}/{total}*100) = {expected_pct}"
            ),
            current_value=reported_pct,
            expected_value=expected_pct,
            fix_suggestion=FixSuggestion(
                file="service/main.py",
                function="check_precedent (two-axis pool)",
                line_range="3457-3460",
                before_snippet="int(round(str_filing_count / two_axis_total * 100))",
                after_snippet="Ensure rounding is consistent",
                root_cause_id="main-str-rate-pct",
                explanation="STR filing rate percentage should be round(count/total*100)",
            ),
        )]
    return []


# ── M6: precedent_alignment_pct consistency ──────────────────────────────

@register_check(
    id="M6",
    category=CheckCategory.M,
    severity=Severity.ERROR,
    description="precedent_alignment_pct == round(supporting/(supporting+contrary)*100)",
)
def check_m6(ctx: dict, case_id: str) -> list[Violation]:
    pa = _pa(ctx)
    if not pa.get("available"):
        return []

    supporting = int(pa.get("supporting_precedents", 0) or 0)
    contrary = int(pa.get("contrary_precedents", 0) or 0)
    reported_pct = ctx.get("precedent_alignment_pct", 0)

    decisive = supporting + contrary
    if decisive == 0:
        expected_pct = 0
    else:
        expected_pct = int(round(supporting / decisive * 100))

    if reported_pct != expected_pct:
        return [Violation(
            check_id="M6",
            severity=Severity.ERROR,
            case_id=case_id,
            message=(
                f"precedent_alignment_pct ({reported_pct}) != "
                f"round({supporting}/({supporting}+{contrary})*100) = {expected_pct}"
            ),
            current_value=reported_pct,
            expected_value=expected_pct,
            fix_suggestion=FixSuggestion(
                file="service/routers/report/derive.py",
                function="_build_enhanced_precedent_analysis",
                line_range="2090-2200",
                before_snippet="precedent_alignment_pct derived from supporting/(supporting+contrary)",
                after_snippet="Ensure governed reclassification updates alignment pct",
                root_cause_id="derive-alignment-pct",
                explanation="precedent_alignment_pct must reflect governed (not engine) classification",
            ),
        )]
    return []


# ── M7: Bottleneck dimension consistency ─────────────────────────────────

@register_check(
    id="M7",
    category=CheckCategory.M,
    severity=Severity.WARNING,
    description="Bottleneck dimension has bottleneck:true AND confidence_level matches bottleneck dim level",
)
def check_m7(ctx: dict, case_id: str) -> list[Violation]:
    ep = _ep(ctx)
    dims = ep.get("confidence_dimensions", [])
    if not dims:
        return []

    confidence_level = ep.get("confidence_level") or _pa(ctx).get("confidence_level")
    confidence_bottleneck = ep.get("confidence_bottleneck") or _pa(ctx).get("confidence_bottleneck")

    if not confidence_level or not confidence_bottleneck:
        return []

    # Check hard rule override — when a hard rule caps confidence, the bottleneck
    # dimension relationship may not hold
    hard_rule = ep.get("confidence_hard_rule") or _pa(ctx).get("confidence_hard_rule")
    if hard_rule:
        return []  # Hard rule overrides bottleneck logic

    violations = []

    # Find bottleneck dimension
    bottleneck_dims = [d for d in dims if d.get("bottleneck")]
    if not bottleneck_dims:
        violations.append(Violation(
            check_id="M7",
            severity=Severity.WARNING,
            case_id=case_id,
            message=f"confidence_bottleneck='{confidence_bottleneck}' but no dimension has bottleneck:true",
            current_value="no bottleneck dim",
            expected_value=f"one dim with bottleneck:true matching '{confidence_bottleneck}'",
        ))
        return violations

    for bd in bottleneck_dims:
        if bd.get("name") != confidence_bottleneck:
            continue
        # Bottleneck dim level should match overall confidence_level
        bd_level = bd.get("level")
        if bd_level and bd_level != confidence_level:
            violations.append(Violation(
                check_id="M7",
                severity=Severity.WARNING,
                case_id=case_id,
                message=(
                    f"confidence_level='{confidence_level}' but bottleneck dim "
                    f"'{confidence_bottleneck}' has level='{bd_level}'"
                ),
                current_value=confidence_level,
                expected_value=bd_level,
            ))

    return violations


# ── M8: sample_size <= match_count ───────────────────────────────────────

@register_check(
    id="M8",
    category=CheckCategory.M,
    severity=Severity.ERROR,
    description="sample_size <= match_count",
)
def check_m8(ctx: dict, case_id: str) -> list[Violation]:
    pa = _pa(ctx)
    if not pa.get("available"):
        return []

    sample_size = int(pa.get("sample_size", 0) or 0)
    match_count = int(pa.get("match_count", 0) or 0)

    if sample_size > match_count:
        return [Violation(
            check_id="M8",
            severity=Severity.ERROR,
            case_id=case_id,
            message=f"sample_size ({sample_size}) > match_count ({match_count})",
            current_value=sample_size,
            expected_value=f"<= {match_count}",
            fix_suggestion=FixSuggestion(
                file="service/main.py",
                function="check_precedent (response assembly)",
                line_range="3476-3477",
                before_snippet="sample_size: len(sampled), match_count: len(scored_matches)",
                after_snippet="sampled is a subset of scored_matches",
                root_cause_id="main-sample-size",
                explanation="sample_size (stratified sample) must be <= match_count (full scored pool)",
            ),
        )]
    return []
