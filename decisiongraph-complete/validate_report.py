#!/usr/bin/env python3
"""CLI: Validate a single demo report.

Usage:
    python validate_report.py <case_id>

Example:
    python validate_report.py pep-legal-fees
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "service"))
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("DG_PRECEDENT_VERSION", "v3")


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_report.py <case_id>")
        print("\nAvailable case IDs:")
        from service.demo_cases import DEMO_CASES
        for c in DEMO_CASES:
            print(f"  {c['id']:<35s} {c['name']}")
        sys.exit(1)

    case_id = sys.argv[1]

    # Import harness (triggers check registration via checks/__init__.py)
    import validation_harness.checks  # noqa: F401
    from validation_harness.runner import validate_single_report
    from validation_harness.output import print_violations

    print(f"\n  Validating: {case_id}")
    print(f"  {'=' * 50}")

    violations = validate_single_report(case_id)
    print_violations(violations)

    error_count = sum(1 for v in violations if v.severity.value == "ERROR")
    print(f"\n  Result: {'FAIL' if error_count else 'PASS'} "
          f"({len(violations)} violations, {error_count} errors)")
    sys.exit(1 if error_count else 0)


if __name__ == "__main__":
    main()
