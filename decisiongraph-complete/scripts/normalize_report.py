#!/usr/bin/env python3
"""
DecisionGraph: Report Normalizer

Normalizes decision pack JSON for golden testing.
Strips non-deterministic fields (timestamps) and sorts keys.

Usage:
    python scripts/normalize_report.py report.json
    python scripts/normalize_report.py report.json --output normalized.json
"""

import argparse
import json
import sys
from pathlib import Path


def normalize_report(report: dict) -> dict:
    """
    Normalize report for deterministic comparison.

    Removes/normalizes:
    - report_timestamp_utc (varies per run)

    Preserves:
    - input_hash (deterministic)
    - engine_version, policy_version (fixed per release)
    """
    normalized = json.loads(json.dumps(report))  # Deep copy

    # Normalize timestamp
    if "meta" in normalized:
        normalized["meta"]["report_timestamp_utc"] = "NORMALIZED"

    return normalized


def main():
    parser = argparse.ArgumentParser(
        description="Normalize decision pack for golden testing"
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Input JSON file"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file (default: stdout)"
    )
    parser.add_argument(
        "--in-place",
        "-i",
        action="store_true",
        help="Modify file in place"
    )

    args = parser.parse_args()

    # Load input
    with open(args.input) as f:
        report = json.load(f)

    # Normalize
    normalized = normalize_report(report)

    # Format with sorted keys
    output = json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=False)

    # Write output
    if args.in_place:
        with open(args.input, "w") as f:
            f.write(output)
    elif args.output:
        with open(args.output, "w") as f:
            f.write(output)
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
