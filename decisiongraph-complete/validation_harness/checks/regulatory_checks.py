"""Regulatory checks (R1-R3, R7-R8): Verify regulatory determination consistency."""
from __future__ import annotations

from ..catalog import register_check
from ..types import CheckCategory, FixSuggestion, Severity, Violation


def _pa(ctx: dict) -> dict:
    return ctx.get("precedent_analysis", {}) or {}


def _ep(ctx: dict) -> dict:
    return ctx.get("enhanced_precedent", {}) or {}


def _tap(ctx: dict) -> dict:
    return _pa(ctx).get("two_axis_pool", {}) or {}


# ── R1: reg_alignment_all_undetermined iff all sample suspicion_alignment == UNDETERMINED

@register_check(
    id="R1",
    category=CheckCategory.R,
    severity=Severity.WARNING,
    description="reg_alignment_all_undetermined == True iff all pool entries have REG_PENDING",
)
def check_r1(ctx: dict, case_id: str) -> list[Violation]:
    ep = _ep(ctx)
    reported_flag = ep.get("reg_alignment_all_undetermined")
    if reported_flag is None:
        return []

    tap = _tap(ctx)
    dist = tap.get("composite_label_distribution", {}) or {}
    if not dist:
        return []

    # All entries have REG_PENDING if every label contains REG_PENDING
    all_pending = all("REG_PENDING" in k for k in dist)

    if reported_flag != all_pending:
        return [Violation(
            check_id="R1",
            severity=Severity.WARNING,
            case_id=case_id,
            message=(
                f"reg_alignment_all_undetermined={reported_flag} but "
                f"composite_label_distribution {'all' if all_pending else 'not all'} "
                f"contain REG_PENDING. Labels: {list(dist.keys())}"
            ),
            current_value=reported_flag,
            expected_value=all_pending,
            fix_suggestion=FixSuggestion(
                file="service/routers/report/derive.py",
                function="_build_enhanced_precedent_analysis",
                line_range="2421-2427",
                before_snippet='all("REG_PENDING" in k for k in ta_composite_dist)',
                after_snippet="Verify all-undetermined detection matches composite labels",
                root_cause_id="derive-reg-undetermined",
                explanation="reg_alignment_all_undetermined should be True iff all labels have REG_PENDING",
            ),
        )]
    return []


# ── R2: str_filing_count consistency with composite labels ───────────────

@register_check(
    id="R2",
    category=CheckCategory.R,
    severity=Severity.WARNING,
    description="str_filing_count self-consistent with pool (verify via composite labels containing STR)",
)
def check_r2(ctx: dict, case_id: str) -> list[Violation]:
    tap = _tap(ctx)
    if not tap or tap.get("total", 0) == 0:
        return []

    str_count = tap.get("str_filing_count", 0)
    # str_filing_count is counted via ta.precedent_suspicion == "STR" in main.py.
    # We cannot recompute from composite labels alone since composite labels
    # encode op+reg alignment, not suspicion directly. But we can sanity-check:
    # str_count should be <= total
    total = tap["total"]

    violations = []
    if str_count > total:
        violations.append(Violation(
            check_id="R2",
            severity=Severity.WARNING,
            case_id=case_id,
            message=f"str_filing_count ({str_count}) > total ({total})",
            current_value=str_count,
            expected_value=f"<= {total}",
        ))

    # Cross-check: if reg_aligned > 0 and str_count == 0, that's surprising
    # but not necessarily wrong (reg_aligned could be from non-STR suspicion alignment)
    # So we skip this cross-check.

    return violations


# ── R3: Classifier sovereign + STR_REQUIRED → canonical_outcome.reporting reflects STR

@register_check(
    id="R3",
    category=CheckCategory.R,
    severity=Severity.ERROR,
    description="When classifier is sovereign + STR_REQUIRED, canonical_outcome.reporting reflects STR",
)
def check_r3(ctx: dict, case_id: str) -> list[Violation]:
    classifier_sovereign = ctx.get("classifier_is_sovereign", False)
    classification_outcome = ctx.get("classification_outcome", "")
    canonical = ctx.get("canonical_outcome", {}) or {}
    reporting = canonical.get("reporting", "")
    governed = ctx.get("governed_disposition", "")

    if not classifier_sovereign or classification_outcome != "STR_REQUIRED":
        return []

    # When governed disposition is EDD_REQUIRED or ESCALATE, reporting is
    # correctly deferred to PENDING_COMPLIANCE_REVIEW even if classifier
    # says STR_REQUIRED. The EDD process must complete first (FIX-023).
    if governed in ("EDD_REQUIRED", "ESCALATE"):
        # Reporting should be PENDING_COMPLIANCE_REVIEW for EDD cases
        if reporting != "PENDING_COMPLIANCE_REVIEW":
            return [Violation(
                check_id="R3",
                severity=Severity.WARNING,
                case_id=case_id,
                message=(
                    f"EDD disposition with classifier STR_REQUIRED: "
                    f"expected PENDING_COMPLIANCE_REVIEW but got '{reporting}'"
                ),
                current_value=reporting,
                expected_value="PENDING_COMPLIANCE_REVIEW",
            )]
        return []

    # When governed disposition is STR_REQUIRED, reporting must be FILE_STR
    if governed == "STR_REQUIRED":
        str_reportings = ("FILE_STR", "STR_REQUIRED", "STR")
        if reporting not in str_reportings:
            return [Violation(
                check_id="R3",
                severity=Severity.ERROR,
                case_id=case_id,
                message=(
                    f"Governed disposition is STR_REQUIRED but "
                    f"canonical_outcome.reporting='{reporting}' "
                    f"(expected one of {str_reportings})"
                ),
                current_value=reporting,
                expected_value=str_reportings,
                fix_suggestion=FixSuggestion(
                    file="service/routers/report/derive.py",
                    function="_derive_reporting",
                    line_range="1490-1505",
                    before_snippet="reporting = _derive_reporting(governed_disposition, str_required)",
                    after_snippet="When STR_REQUIRED: reporting should be FILE_STR",
                    root_cause_id="derive-reporting-str",
                    explanation="STR_REQUIRED governed disposition must produce STR reporting status",
                ),
            )]
    return []


# ── R7: No UNDETERMINED in two_axis_pool composite labels ────────────────

@register_check(
    id="R7",
    category=CheckCategory.R,
    severity=Severity.ERROR,
    description="No *_REG_PENDING composite labels when all seeds have terminal reporting",
)
def check_r7(ctx: dict, case_id: str) -> list[Violation]:
    tap = _tap(ctx)
    if not tap or tap.get("total", 0) == 0:
        return []

    dist = tap.get("composite_label_distribution", {}) or {}
    pending_labels = {k: v for k, v in dist.items() if "REG_PENDING" in k}

    if pending_labels:
        pending_total = sum(pending_labels.values())
        return [Violation(
            check_id="R7",
            severity=Severity.ERROR,
            case_id=case_id,
            message=(
                f"Pool contains {pending_total} precedents with REG_PENDING "
                f"composite labels: {pending_labels}. All seeds should have "
                f"terminal reporting (STR or NO_REPORT)."
            ),
            current_value=pending_labels,
            expected_value="no REG_PENDING labels",
            fix_suggestion=FixSuggestion(
                file="src/domains/banking_aml/seed_generator.py",
                function="_apply_edd_reporting_determination",
                line_range="976-998",
                before_snippet="UNDETERMINED seeds produce REG_PENDING composite labels",
                after_snippet="All EDD seeds must resolve to FILE_STR or NO_REPORT",
                root_cause_id="seed-undetermined-reporting",
                explanation="Seeds with UNDETERMINED reporting_obligation poison the regulatory axis",
            ),
        )]
    return []


# ── R8: Every sample_case has terminal reporting (STR or NO_REPORT) ──────

@register_check(
    id="R8",
    category=CheckCategory.R,
    severity=Severity.ERROR,
    description="Every sample_case reporting is terminal (not UNDETERMINED/PENDING_EDD)",
)
def check_r8(ctx: dict, case_id: str) -> list[Violation]:
    pa = _pa(ctx)
    sample_cases = pa.get("sample_cases", []) or []
    if not sample_cases:
        return []

    _TERMINAL = {"FILE_STR", "NO_REPORT", "FILE_LCTR", "FILE_TPR", "STR", "NO_STR"}
    violations = []
    for sc in sample_cases:
        reporting = sc.get("reporting", "")
        if reporting and reporting not in _TERMINAL:
            violations.append(Violation(
                check_id="R8",
                severity=Severity.ERROR,
                case_id=case_id,
                message=(
                    f"sample_case {sc.get('precedent_id', '?')} has "
                    f"non-terminal reporting='{reporting}'"
                ),
                current_value=reporting,
                expected_value="one of FILE_STR, NO_REPORT, FILE_LCTR",
                fix_suggestion=FixSuggestion(
                    file="src/domains/banking_aml/seed_generator.py",
                    function="_apply_edd_reporting_determination",
                    line_range="976-998",
                    before_snippet="UNDETERMINED seeds leak into sample_cases",
                    after_snippet="All seeds must have terminal reporting_obligation",
                    root_cause_id="seed-undetermined-reporting",
                    explanation="Historical seeds must have completed reporting determination",
                ),
            ))
    return violations
