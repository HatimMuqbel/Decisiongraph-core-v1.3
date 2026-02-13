"""Narrative checks (N1-N5): Verify narrative text consistency with data."""
from __future__ import annotations

import re

from ..catalog import register_check
from ..types import CheckCategory, FixSuggestion, Severity, Violation


def _pa(ctx: dict) -> dict:
    return ctx.get("precedent_analysis", {}) or {}


def _ep(ctx: dict) -> dict:
    return ctx.get("enhanced_precedent", {}) or {}


def _tap(ctx: dict) -> dict:
    return _pa(ctx).get("two_axis_pool", {}) or {}


# ── N1: pattern_summary mentions correct pool size ───────────────────────

@register_check(
    id="N1",
    category=CheckCategory.N,
    severity=Severity.WARNING,
    description="pattern_summary mentions correct pool size (match_count)",
)
def check_n1(ctx: dict, case_id: str) -> list[Violation]:
    ep = _ep(ctx)
    pattern_summary = ep.get("pattern_summary", "") or ""
    if not pattern_summary:
        return []

    pa = _pa(ctx)
    match_count = int(pa.get("match_count", 0) or 0)
    if match_count == 0:
        return []

    # Extract numbers from pattern_summary — look for "Of N " or "N comparable"
    numbers = re.findall(r"(?:Of|of)\s+(\d+)\s+(?:top\s+)?comparable", pattern_summary)
    if not numbers:
        # Also try "N comparable precedents"
        numbers = re.findall(r"(\d+)\s+comparable\s+(?:precedent|case)", pattern_summary)

    if not numbers:
        return []  # No number found — can't verify

    # The pattern summary should reference the sample size (supporting+contrary+neutral),
    # which equals match_count. But _build_pattern_summary receives total_all which is
    # the post-governed-reclassification sum (supporting + contrary + neutral).
    # After governed reclassification this should still equal match_count.
    for num_str in numbers:
        found_num = int(num_str)
        if found_num != match_count:
            # Check if it matches total_all from enhanced_precedent
            ep_outcome = ep.get("outcome_distribution", {}) or {}
            ep_total = ep_outcome.get("total", 0)
            if found_num == ep_total:
                continue  # Matches ep total, acceptable

            return [Violation(
                check_id="N1",
                severity=Severity.WARNING,
                case_id=case_id,
                message=(
                    f"pattern_summary mentions {found_num} cases but "
                    f"match_count={match_count}"
                ),
                current_value=found_num,
                expected_value=match_count,
                fix_suggestion=FixSuggestion(
                    file="service/routers/report/derive.py",
                    function="_build_pattern_summary",
                    line_range="2739-2907",
                    before_snippet="f'Of {total_all} top comparable cases'",
                    after_snippet="total_all should equal match_count",
                    root_cause_id="derive-pattern-summary-count",
                    explanation="Pattern summary pool size should match match_count",
                ),
            )]
    return []


# ── N2: institutional_posture percentage matches precedent_alignment_pct ──

@register_check(
    id="N2",
    category=CheckCategory.N,
    severity=Severity.WARNING,
    description="institutional_posture percentage matches precedent_alignment_pct",
)
def check_n2(ctx: dict, case_id: str) -> list[Violation]:
    ep = _ep(ctx)
    posture = ep.get("institutional_posture", "") or ""
    if not posture:
        return []

    alignment_pct = ctx.get("precedent_alignment_pct", 0)

    # Extract percentage from posture text
    pct_matches = re.findall(r"(\d+)%\s+of\s+comparable\s+terminal\s+precedents", posture)
    if not pct_matches:
        return []

    for pct_str in pct_matches:
        found_pct = int(pct_str)
        if found_pct != alignment_pct and found_pct != (100 - alignment_pct):
            # The posture may use support_pct or contrary_pct = 100-support_pct
            # Both are acceptable — just check neither matches
            return [Violation(
                check_id="N2",
                severity=Severity.WARNING,
                case_id=case_id,
                message=(
                    f"institutional_posture mentions {found_pct}% but "
                    f"precedent_alignment_pct={alignment_pct}%"
                ),
                current_value=found_pct,
                expected_value=alignment_pct,
                fix_suggestion=FixSuggestion(
                    file="service/routers/report/derive.py",
                    function="_build_institutional_posture",
                    line_range="2910-3011",
                    before_snippet="support_pct = int(supporting / total_decisive * 100)",
                    after_snippet="Percentage should match precedent_alignment_pct",
                    root_cause_id="derive-posture-pct",
                    explanation="Institutional posture percentage should be consistent with alignment pct",
                ),
            )]
    return []


# ── N3: suspicion_posture STR count matches str_filing_count ─────────────

@register_check(
    id="N3",
    category=CheckCategory.N,
    severity=Severity.WARNING,
    description="suspicion_posture STR count matches str_filing_count",
)
def check_n3(ctx: dict, case_id: str) -> list[Violation]:
    ep = _ep(ctx)
    posture_lines = ep.get("suspicion_posture", []) or []
    if not posture_lines:
        return []

    tap = _tap(ctx)
    str_count = tap.get("str_filing_count", 0)

    # Extract STR count from suspicion_posture text
    posture_text = " ".join(posture_lines)
    matches = re.findall(r"(\d+)\s+resulted\s+in\s+STR\s+filing", posture_text)

    if not matches:
        return []

    for num_str in matches:
        found = int(num_str)
        if found != str_count:
            return [Violation(
                check_id="N3",
                severity=Severity.WARNING,
                case_id=case_id,
                message=(
                    f"suspicion_posture mentions {found} STR filings but "
                    f"str_filing_count={str_count}"
                ),
                current_value=found,
                expected_value=str_count,
                fix_suggestion=FixSuggestion(
                    file="service/routers/report/derive.py",
                    function="_build_enhanced_precedent_analysis",
                    line_range="2386-2408",
                    before_snippet="f'{ta_str_count} resulted in STR filing'",
                    after_snippet="ta_str_count should equal two_axis_pool.str_filing_count",
                    root_cause_id="derive-suspicion-posture-str",
                    explanation="Suspicion posture STR count should match two_axis_pool.str_filing_count",
                ),
            )]
    return []


# ── N4: LOW confidence → escalation_summary mentions bottleneck ──────────

@register_check(
    id="N4",
    category=CheckCategory.N,
    severity=Severity.INFO,
    description="LOW confidence → escalation_summary mentions bottleneck dimension",
)
def check_n4(ctx: dict, case_id: str) -> list[Violation]:
    ep = _ep(ctx)
    confidence_level = ep.get("confidence_level") or _pa(ctx).get("confidence_level")
    bottleneck = ep.get("confidence_bottleneck") or _pa(ctx).get("confidence_bottleneck")
    escalation_summary = ctx.get("escalation_summary", "") or ""

    if confidence_level != "LOW" or not bottleneck:
        return []

    if not escalation_summary:
        return []

    # Check if bottleneck dimension is mentioned in escalation summary
    # Normalize both for case-insensitive comparison
    bn_lower = bottleneck.lower().replace("_", " ")
    es_lower = escalation_summary.lower()

    if bn_lower not in es_lower and bottleneck.lower() not in es_lower:
        return [Violation(
            check_id="N4",
            severity=Severity.INFO,
            case_id=case_id,
            message=(
                f"confidence_level is LOW with bottleneck='{bottleneck}' but "
                f"escalation_summary does not mention the bottleneck dimension"
            ),
            current_value=f"bottleneck '{bottleneck}' not found in escalation_summary",
            expected_value=f"mention of '{bottleneck}' in escalation_summary",
        )]
    return []


# ── N5: No narrative mentions "0% alignment" when actual alignment > 0 ──

@register_check(
    id="N5",
    category=CheckCategory.N,
    severity=Severity.ERROR,
    description="No narrative mentions '0% alignment' when actual alignment > 0",
)
def check_n5(ctx: dict, case_id: str) -> list[Violation]:
    alignment_pct = ctx.get("precedent_alignment_pct", 0)
    if alignment_pct == 0:
        return []

    # Check all narrative fields for "0% alignment"
    narrative_fields = [
        ("pattern_summary", _ep(ctx).get("pattern_summary", "")),
        ("institutional_posture", _ep(ctx).get("institutional_posture", "")),
        ("two_axis_alignment_narrative", _ep(ctx).get("two_axis_alignment_narrative", "")),
        ("escalation_summary", ctx.get("escalation_summary", "")),
        ("decision_explainer", ctx.get("decision_explainer", "")),
    ]

    violations = []
    for field_name, text in narrative_fields:
        if not text:
            continue
        # Look for "0% alignment" or "0 % alignment"
        if re.search(r"\b0\s*%\s*alignment", text, re.IGNORECASE):
            violations.append(Violation(
                check_id="N5",
                severity=Severity.ERROR,
                case_id=case_id,
                message=(
                    f"'{field_name}' says '0% alignment' but "
                    f"precedent_alignment_pct={alignment_pct}%"
                ),
                current_value="0% alignment in narrative",
                expected_value=f"{alignment_pct}% alignment",
                fix_suggestion=FixSuggestion(
                    file="service/routers/report/derive.py",
                    function="_build_enhanced_precedent_analysis",
                    line_range="2090-2736",
                    before_snippet="Narrative mentions 0% alignment",
                    after_snippet="Use governed reclassification alignment percentage",
                    root_cause_id="derive-zero-alignment-narrative",
                    explanation="Narrative should not claim 0% alignment when governed alignment > 0%",
                ),
            ))
    return violations
