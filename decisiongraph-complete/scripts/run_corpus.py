#!/usr/bin/env python3
"""
DecisionGraph: Golden Test Runner

Runs all cases in test corpus and compares against golden outputs.
This is the regression safety net for releases.

Usage:
    python scripts/run_corpus.py                    # Run all tests
    python scripts/run_corpus.py --update-goldens  # Update golden files
    python scripts/run_corpus.py --verbose         # Show details

Exit codes:
    0 - All tests pass
    1 - Some tests fail
    2 - System error
"""

import argparse
import json
import sys
from pathlib import Path

# Add src and cli to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))
sys.path.insert(0, str(repo_root))

from decisiongraph.decision_pack import normalize_for_golden, ENGINE_VERSION, POLICY_VERSION
from cli.replay import run_case, load_case


def run_golden_tests(
    cases_dir: Path,
    golden_dir: Path,
    update_goldens: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Run all cases and compare against golden outputs.

    Returns results dict with pass/fail counts.
    """
    results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "errors": [],
        "details": [],
    }

    case_files = sorted(cases_dir.glob("*.json"))

    if not case_files:
        print(f"No case files found in {cases_dir}")
        return results

    print(f"Running {len(case_files)} test cases...")
    print(f"Engine: v{ENGINE_VERSION}, Policy: v{POLICY_VERSION}")
    print("=" * 60)

    for case_file in case_files:
        case_id = case_file.stem
        golden_file = golden_dir / f"{case_id}.golden.json"
        results["total"] += 1

        try:
            # Load and run case
            case_data = load_case(case_file)
            decision_pack = run_case(case_data)

            # Normalize for comparison
            actual = normalize_for_golden(decision_pack)
            actual_str = json.dumps(actual, sort_keys=True, indent=2)

            if update_goldens:
                # Update golden file
                golden_dir.mkdir(parents=True, exist_ok=True)
                with open(golden_file, "w") as f:
                    f.write(actual_str)
                print(f"  UPDATED {case_id}")
                results["passed"] += 1
                continue

            if not golden_file.exists():
                results["failed"] += 1
                results["errors"].append(f"{case_id}: Golden file not found")
                print(f"  MISSING {case_id}")
                continue

            # Load and compare golden
            with open(golden_file) as f:
                expected = json.load(f)

            expected_normalized = normalize_for_golden(expected)
            expected_str = json.dumps(expected_normalized, sort_keys=True, indent=2)

            if actual_str == expected_str:
                results["passed"] += 1
                if verbose:
                    verdict = decision_pack["decision"]["verdict"]
                    str_req = decision_pack["decision"]["str_required"]
                    print(f"  PASS {case_id}: {verdict}, STR={str_req}")
                else:
                    print(f"  PASS {case_id}")
            else:
                results["failed"] += 1
                # Find first difference
                actual_lines = actual_str.splitlines()
                expected_lines = expected_str.splitlines()
                diff_line = None
                for i, (a, e) in enumerate(zip(actual_lines, expected_lines)):
                    if a != e:
                        diff_line = i + 1
                        break

                error_msg = f"{case_id}: Mismatch at line {diff_line}"
                results["errors"].append(error_msg)
                print(f"  FAIL {case_id}")
                if verbose:
                    print(f"       First diff at line {diff_line}")

            results["details"].append({
                "case_id": case_id,
                "verdict": decision_pack["decision"]["verdict"],
                "str_required": decision_pack["decision"]["str_required"],
                "escalation": decision_pack["decision"]["escalation"],
            })

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{case_id}: {str(e)}")
            print(f"  ERROR {case_id}: {e}")

    print("=" * 60)
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Run golden tests for decision corpus"
    )
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=repo_root / "test_corpus" / "cases",
        help="Directory containing test case JSON files"
    )
    parser.add_argument(
        "--golden-dir",
        type=Path,
        default=repo_root / "test_corpus" / "golden",
        help="Directory containing golden output files"
    )
    parser.add_argument(
        "--update-goldens",
        action="store_true",
        help="Update golden files instead of comparing"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    # Create directories if they don't exist
    args.cases_dir.mkdir(parents=True, exist_ok=True)
    args.golden_dir.mkdir(parents=True, exist_ok=True)

    results = run_golden_tests(
        cases_dir=args.cases_dir,
        golden_dir=args.golden_dir,
        update_goldens=args.update_goldens,
        verbose=args.verbose,
    )

    # Print summary
    print(f"\nSUMMARY: {results['passed']}/{results['total']} passed")

    if results["failed"] > 0:
        print(f"\nFailed ({results['failed']}):")
        for error in results["errors"]:
            print(f"  - {error}")
        return 1

    if results["passed"] == results["total"] and results["total"] > 0:
        print("\n ALL GOLDEN TESTS PASSED - Release candidate approved")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
