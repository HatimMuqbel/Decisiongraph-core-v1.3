"""Evidence checks (E1-E2): Verify sample case evidence quality."""
from __future__ import annotations

from ..catalog import register_check
from ..types import CheckCategory, FixSuggestion, Severity, Violation


def _pa(ctx: dict) -> dict:
    return ctx.get("precedent_analysis", {}) or {}


# ── E1: Every sample_case has non-empty field_scores ─────────────────────

@register_check(
    id="E1",
    category=CheckCategory.E,
    severity=Severity.WARNING,
    description="Every sample_case has non-empty field_scores",
)
def check_e1(ctx: dict, case_id: str) -> list[Violation]:
    pa = _pa(ctx)
    sample_cases = pa.get("sample_cases", []) or []
    if not sample_cases:
        return []

    violations = []
    for i, sc in enumerate(sample_cases):
        field_scores = sc.get("field_scores", {}) or {}
        if not field_scores:
            violations.append(Violation(
                check_id="E1",
                severity=Severity.WARNING,
                case_id=case_id,
                message=(
                    f"sample_case[{i}] (precedent_id={sc.get('precedent_id', '?')}) "
                    f"has empty field_scores"
                ),
                current_value={},
                expected_value="non-empty dict",
                fix_suggestion=FixSuggestion(
                    file="src/kernel/precedent/precedent_scorer.py",
                    function="score_similarity",
                    line_range="310-350",
                    before_snippet="field_scores not populated",
                    after_snippet="Ensure score_similarity always returns field_scores",
                    root_cause_id="scorer-field-scores",
                    explanation="Every scored match should have field_scores from the similarity scorer",
                ),
            ))
    return violations


# ── E2: Every sample_case similarity_pct >= threshold_used * 100 ─────────

@register_check(
    id="E2",
    category=CheckCategory.E,
    severity=Severity.ERROR,
    description="Every sample_case similarity_pct >= threshold_used * 100",
)
def check_e2(ctx: dict, case_id: str) -> list[Violation]:
    pa = _pa(ctx)
    sample_cases = pa.get("sample_cases", []) or []
    threshold_used = pa.get("threshold_used", 0) or 0
    if not sample_cases or not threshold_used:
        return []

    min_pct = threshold_used * 100

    violations = []
    for i, sc in enumerate(sample_cases):
        sim_pct = sc.get("similarity_pct", 0) or 0
        if sim_pct < min_pct:
            violations.append(Violation(
                check_id="E2",
                severity=Severity.ERROR,
                case_id=case_id,
                message=(
                    f"sample_case[{i}] (precedent_id={sc.get('precedent_id', '?')}) "
                    f"similarity_pct={sim_pct} < threshold_used*100={min_pct}"
                ),
                current_value=sim_pct,
                expected_value=f">= {min_pct}",
                fix_suggestion=FixSuggestion(
                    file="service/main.py",
                    function="check_precedent (scoring loop)",
                    line_range="3400-3430",
                    before_snippet="sample_cases[:10] from scored_matches",
                    after_snippet="scored_matches should all be >= threshold_used",
                    root_cause_id="main-threshold-filter",
                    explanation="All scored matches (and their samples) must meet the similarity threshold",
                ),
            ))
    return violations
