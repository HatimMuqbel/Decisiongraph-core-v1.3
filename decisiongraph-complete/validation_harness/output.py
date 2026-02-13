"""Terminal matrix formatter + JSON serializer."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .catalog import get_enabled_checks
from .types import Severity, ValidationReport, Violation


def print_matrix(report: ValidationReport) -> None:
    """Print a terminal matrix: case (row) x check (col).

    Legend: .=PASS  X=ERROR  w=WARNING  i=INFO  -=EXCEPTION
    """
    check_ids = sorted({v.check_id for v in report.violations})
    # Also include all registered checks for complete columns
    for cd in get_enabled_checks():
        if cd.id not in check_ids:
            check_ids.append(cd.id)
    check_ids = sorted(set(check_ids))

    if not check_ids:
        print("  No checks registered.")
        return

    case_ids = sorted(report.matrix.keys())
    if not case_ids:
        print("  No cases validated.")
        return

    # Build excepted set
    excepted = {(c, ck) for c, ck, _ in report.exceptions_applied}

    # Header
    max_case_len = max(len(c) for c in case_ids)
    header = " " * (max_case_len + 2)
    for cid in check_ids:
        header += f" {cid:>4s}"
    print(header)
    print(" " * (max_case_len + 2) + "-" * (len(check_ids) * 5))

    for case_id in case_ids:
        row = f"  {case_id:<{max_case_len}s}"
        for check_id in check_ids:
            if (case_id, check_id) in excepted:
                row += "    -"
            else:
                cell = report.matrix.get(case_id, {}).get(check_id, ".")
                row += f"    {cell}"
        print(row)

    # Legend
    print()
    print("  Legend: .=PASS  X=ERROR  w=WARNING  i=INFO  -=EXCEPTION")
    error_count = sum(1 for v in report.violations if v.severity == Severity.ERROR)
    warn_count = sum(1 for v in report.violations if v.severity == Severity.WARNING)
    print(f"  Total: {report.cases_validated} cases, {report.checks_run} checks, "
          f"{error_count} errors, {warn_count} warnings, "
          f"{len(report.exceptions_applied)} exceptions")


def print_violations(violations: list[Violation]) -> None:
    """Print violations grouped by severity."""
    if not violations:
        print("  All checks passed.")
        return

    errors = [v for v in violations if v.severity == Severity.ERROR]
    warnings = [v for v in violations if v.severity == Severity.WARNING]
    infos = [v for v in violations if v.severity == Severity.INFO]

    for label, group in [("ERRORS", errors), ("WARNINGS", warnings), ("INFO", infos)]:
        if not group:
            continue
        print(f"\n  {label} ({len(group)}):")
        for v in group:
            print(f"    [{v.check_id}] {v.message}")
            if v.current_value is not None or v.expected_value is not None:
                print(f"      current={v.current_value}  expected={v.expected_value}")


def print_root_causes(report: ValidationReport) -> None:
    """Print root causes grouped with fix suggestions."""
    if not report.root_causes:
        print("  No root causes identified.")
        return

    print(f"\n  ROOT CAUSES ({len(report.root_causes)}):")
    for rc in report.root_causes:
        print(f"\n  [{rc.root_cause_id}] {rc.file}:{rc.function}")
        print(f"    Violations: {rc.violation_count} across {len(rc.affected_cases)} cases")
        print(f"    Explanation: {rc.explanation}")
        if rc.fix_suggestion:
            print(f"    Fix: {rc.fix_suggestion.file} lines {rc.fix_suggestion.line_range}")
            if rc.fix_suggestion.before_snippet:
                print(f"    Before: {rc.fix_suggestion.before_snippet[:120]}")
            if rc.fix_suggestion.after_snippet:
                print(f"    After:  {rc.fix_suggestion.after_snippet[:120]}")


def write_json_report(report: ValidationReport, path: str | Path) -> None:
    """Write full validation report as JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "cases_validated": report.cases_validated,
        "checks_run": report.checks_run,
        "violation_count": len(report.violations),
        "error_count": sum(1 for v in report.violations if v.severity == Severity.ERROR),
        "warning_count": sum(1 for v in report.violations if v.severity == Severity.WARNING),
        "exceptions_applied": len(report.exceptions_applied),
        "matrix": report.matrix,
        "violations": [_violation_to_dict(v) for v in report.violations],
        "root_causes": [asdict(rc) for rc in report.root_causes],
    }

    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"\n  JSON report written to: {path}")


def _violation_to_dict(v: Violation) -> dict:
    d = {
        "check_id": v.check_id,
        "severity": v.severity.value,
        "case_id": v.case_id,
        "message": v.message,
    }
    if v.current_value is not None:
        d["current_value"] = v.current_value
    if v.expected_value is not None:
        d["expected_value"] = v.expected_value
    if v.fix_suggestion is not None:
        d["fix_suggestion"] = asdict(v.fix_suggestion)
    return d
