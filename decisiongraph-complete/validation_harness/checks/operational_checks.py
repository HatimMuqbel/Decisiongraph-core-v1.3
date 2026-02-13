"""Operational checks (O1-O3): Verify operational correctness of report outputs."""
from __future__ import annotations

from ..catalog import register_check
from ..types import CheckCategory, FixSuggestion, Severity, Violation


# ── O1: EDD disposition → edd_recommendations non-empty ──────────────────

@register_check(
    id="O1",
    category=CheckCategory.O,
    severity=Severity.WARNING,
    description="EDD disposition implies non-empty edd_recommendations",
)
def check_o1(ctx: dict, case_id: str) -> list[Violation]:
    governed = ctx.get("governed_disposition", "")
    edd_recs = ctx.get("edd_recommendations", []) or []

    # EDD dispositions
    is_edd = governed in ("EDD_REQUIRED", "PASS_WITH_EDD", "ESCALATE")
    # HARD_STOP and STR_REQUIRED may skip EDD — not checked here
    if governed in ("HARD_STOP", "STR_REQUIRED", "NO_REPORT"):
        return []

    if is_edd and not edd_recs:
        return [Violation(
            check_id="O1",
            severity=Severity.WARNING,
            case_id=case_id,
            message=(
                f"governed_disposition is '{governed}' (EDD) but "
                f"edd_recommendations is empty"
            ),
            current_value=[],
            expected_value="non-empty list",
            fix_suggestion=FixSuggestion(
                file="service/routers/report/derive.py",
                function="_derive_edd_recommendations",
                line_range="363-368",
                before_snippet="edd_recommendations = _derive_edd_recommendations(...)",
                after_snippet="Should produce recommendations for EDD dispositions",
                root_cause_id="derive-edd-recs",
                explanation="EDD dispositions should always have at least one EDD recommendation",
            ),
        )]
    return []


# ── O2: STR disposition → str_required == True ───────────────────────────

@register_check(
    id="O2",
    category=CheckCategory.O,
    severity=Severity.ERROR,
    description="STR disposition implies str_required == True",
)
def check_o2(ctx: dict, case_id: str) -> list[Violation]:
    governed = ctx.get("governed_disposition", "")
    str_required = ctx.get("str_required", False)

    if governed == "STR_REQUIRED" and not str_required:
        return [Violation(
            check_id="O2",
            severity=Severity.ERROR,
            case_id=case_id,
            message=(
                f"governed_disposition is 'STR_REQUIRED' but str_required is {str_required}"
            ),
            current_value=str_required,
            expected_value=True,
            fix_suggestion=FixSuggestion(
                file="service/routers/report/derive.py",
                function="derive_all",
                line_range="250-300",
                before_snippet="str_required derived from disposition + classifier",
                after_snippet="STR_REQUIRED disposition must set str_required=True",
                root_cause_id="derive-str-required",
                explanation="When governed_disposition is STR_REQUIRED, str_required must be True",
            ),
        )]
    return []


# ── O3: Analyst actions appropriate for governed disposition ─────────────

@register_check(
    id="O3",
    category=CheckCategory.O,
    severity=Severity.ERROR,
    description="No 'Approve' or 'Confirm Clearance' for STR/BLOCK/HARD_STOP cases",
)
def check_o3(ctx: dict, case_id: str) -> list[Violation]:
    governed = ctx.get("governed_disposition", "")
    analyst_actions = ctx.get("analyst_actions", []) or []

    if not analyst_actions:
        return []

    # STR/BLOCK/HARD_STOP should never offer "Approve" or "Confirm Clearance"
    blocked_dispositions = ("STR_REQUIRED", "HARD_STOP")
    if governed not in blocked_dispositions:
        return []

    violations = []
    forbidden_labels = {"Approve", "Confirm Clearance"}

    for action in analyst_actions:
        label = action.get("label", "")
        if label in forbidden_labels:
            violations.append(Violation(
                check_id="O3",
                severity=Severity.ERROR,
                case_id=case_id,
                message=(
                    f"Analyst action '{label}' offered for {governed} disposition"
                ),
                current_value=label,
                expected_value=f"not '{label}' for {governed}",
                fix_suggestion=FixSuggestion(
                    file="service/routers/report/derive.py",
                    function="_derive_analyst_actions",
                    line_range="1698-1786",
                    before_snippet=f"Action '{label}' in analyst_actions",
                    after_snippet=f"Remove '{label}' for {governed} dispositions",
                    root_cause_id="derive-analyst-actions",
                    explanation="STR/HARD_STOP dispositions must never offer clearance actions",
                ),
            ))
    return violations
