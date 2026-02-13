"""Batch runner + root cause grouping."""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from .catalog import get_enabled_checks
from .exceptions import is_excepted, load_exceptions
from .runner import generate_report_context, validate_single_report
from .types import RootCause, Severity, ValidationReport, Violation

ROOT = Path(__file__).parent.parent


def run_all_cases(
    exceptions_path: str | Path | None = None,
) -> ValidationReport:
    """Run all 20 demo cases through all enabled checks.

    Returns a ValidationReport with matrix, violations, and root causes.
    """
    from service.demo_cases import DEMO_CASES

    exceptions = []
    if exceptions_path:
        exceptions = load_exceptions(exceptions_path)

    checks = get_enabled_checks()
    check_ids = sorted(cd.id for cd in checks)

    all_violations: list[Violation] = []
    matrix: dict[str, dict[str, str]] = {}
    exceptions_applied: list[tuple[str, str, str]] = []

    for case in DEMO_CASES:
        case_id = case["id"]
        print(f"  Validating {case_id}...", end="", flush=True)

        ctx = generate_report_context(case)
        if ctx is None:
            print(" ERROR (generation failed)")
            all_violations.append(Violation(
                check_id="RUNNER",
                severity=Severity.ERROR,
                case_id=case_id,
                message=f"Failed to generate report for {case_id}",
            ))
            continue

        case_violations = validate_single_report(case_id, pre_generated_ctx=ctx)

        # Apply exceptions
        filtered: list[Violation] = []
        case_matrix: dict[str, str] = {}

        for v in case_violations:
            reason = is_excepted(case_id, v.check_id, exceptions)
            if reason:
                exceptions_applied.append((case_id, v.check_id, reason))
                case_matrix[v.check_id] = "-"
            else:
                filtered.append(v)
                sym = _severity_symbol(v.severity)
                # Keep worst severity per check
                existing = case_matrix.get(v.check_id, ".")
                if _severity_rank(sym) > _severity_rank(existing):
                    case_matrix[v.check_id] = sym

        # Fill in passing checks
        for cid in check_ids:
            if cid not in case_matrix:
                case_matrix[cid] = "."

        all_violations.extend(filtered)
        matrix[case_id] = case_matrix

        error_count = sum(1 for v in filtered if v.severity == Severity.ERROR)
        warn_count = sum(1 for v in filtered if v.severity == Severity.WARNING)
        if error_count or warn_count:
            print(f" {error_count}E {warn_count}W")
        else:
            print(" OK")

    root_causes = _group_root_causes(all_violations)

    return ValidationReport(
        cases_validated=len(DEMO_CASES),
        checks_run=len(checks),
        matrix=matrix,
        violations=all_violations,
        root_causes=root_causes,
        exceptions_applied=exceptions_applied,
    )


def _group_root_causes(violations: list[Violation]) -> list[RootCause]:
    """Group violations by root_cause_id from their fix suggestions."""
    groups: dict[str, list[Violation]] = defaultdict(list)

    for v in violations:
        if v.fix_suggestion and v.fix_suggestion.root_cause_id:
            groups[v.fix_suggestion.root_cause_id].append(v)

    root_causes = []
    for rc_id, group in sorted(groups.items()):
        first = group[0].fix_suggestion
        root_causes.append(RootCause(
            root_cause_id=rc_id,
            file=first.file if first else "",
            function=first.function if first else "",
            violation_count=len(group),
            affected_cases=sorted(set(v.case_id for v in group)),
            explanation=first.explanation if first else "",
            fix_suggestion=first,
        ))

    return root_causes


def _severity_symbol(severity: Severity) -> str:
    return {"ERROR": "X", "WARNING": "w", "INFO": "i"}.get(severity.value, "?")


def _severity_rank(symbol: str) -> int:
    return {"X": 3, "w": 2, "i": 1, ".": 0, "-": -1}.get(symbol, 0)
