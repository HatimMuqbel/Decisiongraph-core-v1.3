#!/usr/bin/env python3
"""CLI: Validate all 20 demo reports and print matrix + root cause groups.

Usage:
    python validate_all_reports.py
    python validate_all_reports.py --json   # also write JSON report
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "service"))
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("DG_PRECEDENT_VERSION", "v3")


def main():
    write_json = "--json" in sys.argv

    # Import harness (triggers check registration)
    import validation_harness.checks  # noqa: F401
    from validation_harness.batch import run_all_cases
    from validation_harness.output import (
        print_matrix,
        print_root_causes,
        print_violations,
        write_json_report,
    )

    exceptions_path = ROOT / "validation_exceptions.yml"

    print("\n  VALIDATION HARNESS — ALL DEMO CASES")
    print(f"  {'=' * 60}")

    report = run_all_cases(
        exceptions_path=exceptions_path if exceptions_path.exists() else None,
    )

    print(f"\n  {'=' * 60}")
    print("  VALIDATION MATRIX")
    print(f"  {'=' * 60}\n")
    print_matrix(report)

    if report.violations:
        print(f"\n  {'=' * 60}")
        print("  ALL VIOLATIONS")
        print(f"  {'=' * 60}")
        print_violations(report.violations)

    print(f"\n  {'=' * 60}")
    print("  ROOT CAUSE ANALYSIS")
    print(f"  {'=' * 60}")
    print_root_causes(report)

    if write_json:
        json_path = ROOT / "validation_reports" / "v3" / "validation_results.json"
        write_json_report(report, json_path)

    error_count = sum(1 for v in report.violations if v.severity.value == "ERROR")
    print(f"\n  Overall: {'FAIL' if error_count else 'PASS'}")
    sys.exit(1 if error_count else 0)


if __name__ == "__main__":
    main()
