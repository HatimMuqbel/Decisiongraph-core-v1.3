#!/usr/bin/env python3
"""
Seed Corpus Coverage Audit — Full Pipeline

For each demo case:
  1. POST /decide to run the decision engine
  2. GET /report/{id}/json to extract the full report
  3. Extract precedent analysis: comparable count, transferable count,
     non-transferable reasons, driver contradictions
  4. Build driver coverage matrix across the seed corpus
  5. Output a comprehensive gap report

Usage:
    cd decisiongraph-complete
    python scripts/audit_seed_coverage.py
"""

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "service"))
sys.path.insert(0, str(ROOT / "src"))

os.environ["DG_PRECEDENT_VERSION"] = "v3"

from fastapi.testclient import TestClient
from service.main import app, load_precedent_seeds
from service.demo_cases import DEMO_CASES
from domains.banking_aml.seed_generator import generate_all_banking_seeds, SCENARIOS
from domains.banking_aml.field_registry import BANKING_FIELDS

# Load seeds
load_precedent_seeds()

TRANSFERABLE_TARGET = 10
TRANSFERABLE_MINIMUM = 10


# ─── Step 1: Seed Corpus Driver Coverage Matrix ─────────────────────────

def build_driver_coverage_matrix(seeds):
    """Build field × value distribution across all seeds."""
    field_values = defaultdict(Counter)

    for seed in seeds:
        facts = {af.field_id: af.value for af in seed.anchor_facts}
        for field_name, value in facts.items():
            if field_name not in BANKING_FIELDS:
                continue
            ftype = BANKING_FIELDS[field_name]["type"]
            if ftype == "boolean":
                field_values[field_name][bool(value)] += 1
            else:
                field_values[field_name][value] += 1

    return field_values


def print_driver_coverage_matrix(field_values, seeds):
    """Print the driver coverage matrix with gap detection."""
    print("\n" + "=" * 80)
    print("  STEP 3: DRIVER COVERAGE MATRIX")
    print("=" * 80)

    total = len(seeds)
    gaps = []

    # Boolean fields
    print(f"\n{'BOOLEAN FIELD':<40} {'TRUE':>8} {'FALSE':>8} {'COVERAGE':>12}")
    print("-" * 70)
    bool_fields = sorted(
        [f for f in BANKING_FIELDS if BANKING_FIELDS[f]["type"] == "boolean"],
    )
    for field in bool_fields:
        counts = field_values.get(field, Counter())
        true_count = counts.get(True, 0)
        false_count = counts.get(False, 0)
        if true_count == 0 or false_count == 0:
            coverage = "SINGLE-SIDED"
            gaps.append((field, "boolean", true_count, false_count))
        else:
            pct = min(true_count, false_count) / max(true_count, false_count) * 100
            coverage = f"BOTH ({pct:.0f}%)"
        print(f"{field:<40} {true_count:>8} {false_count:>8} {coverage:>12}")

    # Enum fields
    print(f"\n{'ENUM FIELD':<40} {'VALUES (count)':>40}")
    print("-" * 80)
    enum_fields = sorted(
        [f for f in BANKING_FIELDS if BANKING_FIELDS[f]["type"] == "enum"],
    )
    for field in enum_fields:
        counts = field_values.get(field, Counter())
        expected_values = BANKING_FIELDS[field].get("values", [])
        missing = [v for v in expected_values if counts.get(v, 0) == 0]
        value_str = ", ".join(f"{v}:{counts.get(v, 0)}" for v in expected_values)
        status = " MISSING: " + ", ".join(str(m) for m in missing) if missing else ""
        print(f"{field:<40} {value_str}")
        if missing:
            print(f"{'':>40} {'':>15} {status}")
            gaps.append((field, "enum", expected_values, missing))

    return gaps


# ─── Step 2: Per-Demo-Case Audit ────────────────────────────────────────

def audit_demo_case(client, case):
    """Run a demo case through the engine and extract precedent stats."""
    case_id = case["id"]

    payload = {
        "case_id": case_id,
        "facts": [{"field": f["field"], "value": f["value"]} for f in case["facts"]],
    }

    # POST /decide
    resp = client.post("/decide", json=payload)
    if resp.status_code != 200:
        return {
            "case_id": case_id,
            "error": f"decide returned {resp.status_code}",
        }

    decision = resp.json()
    decision_id = decision.get("meta", {}).get("decision_id", "")

    # GET /report/{id}/json
    report_resp = client.get(f"/report/{decision_id}/json")
    if report_resp.status_code != 200:
        return {
            "case_id": case_id,
            "error": f"report returned {report_resp.status_code}",
        }

    report = report_resp.json().get("report", {})

    # Extract precedent analysis
    pa = report.get("precedent_analysis", {})
    ep = report.get("enhanced_precedent", {})
    sample_cases = pa.get("sample_cases", [])

    # Count transferable / non-transferable
    total_comparable = len(sample_cases)
    non_transferable_list = [
        sc for sc in sample_cases if sc.get("non_transferable", False)
    ]
    transferable_list = [
        sc for sc in sample_cases if not sc.get("non_transferable", False)
    ]
    nt_count = len(non_transferable_list)
    transferable_count = len(transferable_list)

    # Collect non-transferable reasons
    nt_reasons = Counter()
    for sc in non_transferable_list:
        for reason in sc.get("non_transferable_reasons", []):
            nt_reasons[reason] += 1

    # Collect mismatched drivers
    mismatched_drivers = Counter()
    for sc in non_transferable_list:
        for driver in sc.get("mismatched_drivers", []):
            mismatched_drivers[driver] += 1

    # Alignment data
    governed_disposition = report.get("governed_disposition", "")
    confidence_level = ep.get("confidence_level") or pa.get("confidence_level", "N/A")
    confidence_bottleneck = ep.get("confidence_bottleneck") or pa.get("confidence_bottleneck", "N/A")
    pool_warning = pa.get("pool_warning") or pa.get("message", "")

    # Two-axis alignment
    alignment = ep.get("governed_alignment_count", "?")
    alignment_total = ep.get("governed_alignment_total", "?")

    return {
        "case_id": case_id,
        "name": case.get("name", ""),
        "category": case.get("category", ""),
        "disposition": governed_disposition,
        "total_comparable": total_comparable,
        "transferable_count": transferable_count,
        "non_transferable_count": nt_count,
        "nt_rate": f"{nt_count/total_comparable*100:.0f}%" if total_comparable > 0 else "N/A",
        "confidence_level": confidence_level,
        "confidence_bottleneck": confidence_bottleneck,
        "pool_warning": pool_warning,
        "alignment": f"{alignment}/{alignment_total}",
        "nt_reasons": dict(nt_reasons.most_common(5)),
        "mismatched_drivers": dict(mismatched_drivers.most_common(5)),
    }


# ─── Step 4: Scenario → Driver Mapping ──────────────────────────────────

def print_scenario_driver_mapping():
    """Show which scenarios cover which driver field values."""
    print("\n" + "=" * 80)
    print("  SCENARIO → DECISION DRIVER MAPPING")
    print("=" * 80)

    for scenario in SCENARIOS:
        drivers = scenario.get("decision_drivers", [])
        base = scenario.get("base_facts", {})
        driver_values = {d: base.get(d, "NOT SET") for d in drivers}
        weight_pct = scenario["weight"] * 100
        count = max(1, round(1500 * scenario["weight"]))
        print(f"\n  {scenario['name']} (weight={weight_pct:.0f}%, ~{count} seeds)")
        print(f"    outcome: {scenario['outcome']}")
        print(f"    drivers: {driver_values}")


# ─── Main ────────────────────────────────────────────────────────────────

def main():
    client = TestClient(app)

    # ── Step 1: Identify all demo cases ──────────────────────────────
    print("=" * 80)
    print("  SEED CORPUS COVERAGE AUDIT")
    print(f"  {len(DEMO_CASES)} demo cases × ~1500 seeds")
    print("=" * 80)

    # ── Step 2: Audit each demo case ─────────────────────────────────
    print("\n" + "=" * 80)
    print("  STEP 2: PER-CASE TRANSFERABILITY AUDIT")
    print("=" * 80)

    results = []
    flagged = []

    for i, case in enumerate(DEMO_CASES):
        sys.stdout.write(f"\r  Auditing {i+1}/{len(DEMO_CASES)}: {case['id']:<50}")
        sys.stdout.flush()
        result = audit_demo_case(client, case)
        results.append(result)

        if result.get("error"):
            flagged.append(result)
        elif result["transferable_count"] < TRANSFERABLE_TARGET:
            flagged.append(result)

    print("\r" + " " * 80)

    # Print summary table
    print(f"\n{'CASE ID':<45} {'COMP':>5} {'TRANS':>6} {'NT':>4} {'NT%':>5} {'CONF':>12} {'BOTTLENECK':>20}")
    print("-" * 105)
    for r in results:
        if r.get("error"):
            print(f"{r['case_id']:<45} ERROR: {r['error']}")
            continue
        marker = " ***" if r["transferable_count"] < TRANSFERABLE_TARGET else ""
        print(
            f"{r['case_id']:<45} {r['total_comparable']:>5} "
            f"{r['transferable_count']:>6} {r['non_transferable_count']:>4} "
            f"{r['nt_rate']:>5} {r['confidence_level']:>12} "
            f"{r['confidence_bottleneck']:<20}{marker}"
        )

    # ── Flagged cases ────────────────────────────────────────────────
    print(f"\n{'='*80}")
    print(f"  FLAGGED CASES (transferable < {TRANSFERABLE_TARGET})")
    print(f"{'='*80}")

    if not flagged:
        print("  None! All demo cases have sufficient transferable precedents.")
    else:
        for r in flagged:
            print(f"\n  {r['case_id']} ({r.get('category', '')})")
            if r.get("error"):
                print(f"    ERROR: {r['error']}")
                continue
            print(f"    Comparable: {r['total_comparable']}, Transferable: {r['transferable_count']}, NT: {r['non_transferable_count']}")
            print(f"    Confidence: {r['confidence_level']}, Bottleneck: {r['confidence_bottleneck']}")
            if r.get("nt_reasons"):
                print(f"    Top NT reasons:")
                for reason, count in r["nt_reasons"].items():
                    print(f"      [{count}x] {reason}")
            if r.get("mismatched_drivers"):
                print(f"    Top mismatched drivers:")
                for driver, count in r["mismatched_drivers"].items():
                    print(f"      [{count}x] {driver}")

    # ── Step 3: Driver coverage matrix ───────────────────────────────
    print("\n  Generating seed corpus...")
    seeds = generate_all_banking_seeds()
    print(f"  Total seeds: {len(seeds)}")

    field_values = build_driver_coverage_matrix(seeds)
    matrix_gaps = print_driver_coverage_matrix(field_values, seeds)

    if matrix_gaps:
        print(f"\n  DRIVER COVERAGE GAPS: {len(matrix_gaps)}")
        for gap in matrix_gaps:
            field, ftype = gap[0], gap[1]
            if ftype == "boolean":
                true_c, false_c = gap[2], gap[3]
                side = "TRUE" if true_c == 0 else "FALSE"
                print(f"    {field}: missing {side} side ({true_c} True, {false_c} False)")
            else:
                expected, missing = gap[2], gap[3]
                print(f"    {field}: missing values {missing}")
    else:
        print("\n  No driver coverage gaps found!")

    # ── Step 4: Scenario → Driver mapping ────────────────────────────
    print_scenario_driver_mapping()

    # ── Summary ──────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("  AUDIT SUMMARY")
    print("=" * 80)
    total = len(results)
    errored = sum(1 for r in results if r.get("error"))
    passing = sum(1 for r in results if not r.get("error") and r["transferable_count"] >= TRANSFERABLE_TARGET)
    failing = total - errored - passing

    print(f"  Total demo cases:     {total}")
    print(f"  Passing (≥{TRANSFERABLE_TARGET} trans.): {passing}")
    print(f"  Failing (<{TRANSFERABLE_TARGET} trans.): {failing}")
    print(f"  Errors:               {errored}")
    print(f"  Driver coverage gaps: {len(matrix_gaps)}")
    print(f"  Seed corpus size:     {len(seeds)}")

    # Write JSON report
    output_path = ROOT / "scripts" / "audit_seed_coverage_report.json"
    with open(output_path, "w") as f:
        json.dump({
            "summary": {
                "total_demo_cases": total,
                "passing": passing,
                "failing": failing,
                "errors": errored,
                "driver_coverage_gaps": len(matrix_gaps),
                "seed_corpus_size": len(seeds),
            },
            "per_case_results": results,
            "flagged_cases": [r["case_id"] for r in flagged if not r.get("error")],
            "driver_coverage_gaps": [
                {"field": g[0], "type": g[1], "detail": str(g[2:])}
                for g in matrix_gaps
            ],
        }, f, indent=2)
    print(f"\n  JSON report: {output_path}")


if __name__ == "__main__":
    main()
