"""Batch demo report generator — runs all demo cases through the v3 pipeline.

Usage:
    python generate_demo_reports.py

Outputs HTML reports to validation_reports/v3/ and prints a confidence summary.
"""

import json
import os
import sys
from pathlib import Path

# Ensure service and src are importable
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "service"))
sys.path.insert(0, str(ROOT / "src"))

# Force v3 before anything imports main
os.environ["DG_PRECEDENT_VERSION"] = "v3"

from fastapi.testclient import TestClient

# Import after env is set
from service.main import app, load_precedent_seeds  # noqa: E402
from service.demo_cases import DEMO_CASES  # noqa: E402

OUTPUT_DIR = ROOT / "validation_reports" / "v3"

# Explicitly load precedent seeds (startup event may not fire in TestClient)
load_precedent_seeds()


def _extract_v3_confidence(report_json: dict) -> dict:
    """Pull v3 confidence fields from the report context JSON."""
    ep = report_json.get("report", {}).get("enhanced_precedent", {})
    pa = report_json.get("report", {}).get("precedent_analysis", {})
    return {
        "confidence_level": ep.get("confidence_level") or pa.get("confidence_level", "N/A"),
        "confidence_bottleneck": ep.get("confidence_bottleneck") or pa.get("confidence_bottleneck", "N/A"),
        "confidence_hard_rule": ep.get("confidence_hard_rule"),
        "confidence_dimensions": ep.get("confidence_dimensions", []),
        "driver_causality": ep.get("driver_causality"),
        "non_transferable_count": len(ep.get("non_transferable_explanations", [])),
        "governed_alignment": f"{ep.get('governed_alignment_count', '?')}/{ep.get('governed_alignment_total', '?')}",
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = TestClient(app)

    results = []
    for case in DEMO_CASES:
        case_id = case["id"]
        case_name = case["name"]
        print(f"\n{'='*60}")
        print(f"  {case_id}: {case_name}")
        print(f"{'='*60}")

        # Build the demo-format payload
        payload = {
            "case_id": case_id,
            "facts": [{"field": f["field"], "value": f["value"]} for f in case["facts"]],
        }

        # POST /decide
        resp = client.post("/decide", json=payload)
        if resp.status_code != 200:
            print(f"  ERROR: /decide returned {resp.status_code}")
            print(f"  {resp.text[:200]}")
            results.append({"case_id": case_id, "name": case_name, "error": resp.status_code})
            continue

        decision = resp.json()
        decision_id = decision.get("meta", {}).get("decision_id", "")
        print(f"  Decision ID: {decision_id[:16]}...")

        # GET /report/{id} (HTML)
        html_resp = client.get(f"/report/{decision_id}")
        if html_resp.status_code == 200:
            html_path = OUTPUT_DIR / f"{case_id}.html"
            html_path.write_text(html_resp.text, encoding="utf-8")
            print(f"  HTML report: {html_path}")
        else:
            print(f"  WARNING: HTML report returned {html_resp.status_code}")

        # GET /report/{id}/json (structured context)
        json_resp = client.get(f"/report/{decision_id}/json")
        if json_resp.status_code == 200:
            report_json = json_resp.json()
            v3_info = _extract_v3_confidence(report_json)
            print(f"  Confidence Level:     {v3_info['confidence_level']}")
            print(f"  Bottleneck:           {v3_info['confidence_bottleneck']}")
            if v3_info["confidence_hard_rule"]:
                print(f"  Hard Rule:            {v3_info['confidence_hard_rule']}")
            print(f"  Governed Alignment:   {v3_info['governed_alignment']}")
            if v3_info["driver_causality"]:
                dc = v3_info["driver_causality"]
                print(f"  Shared Drivers:       {', '.join(dc.get('shared_drivers', [])) or 'none'}")
                print(f"  Divergent Drivers:    {', '.join(dc.get('divergent_drivers', [])) or 'none'}")
            if v3_info["non_transferable_count"]:
                print(f"  Non-Transferable:     {v3_info['non_transferable_count']}")
            dims = v3_info["confidence_dimensions"]
            if dims:
                print(f"  Dimensions:")
                for d in dims:
                    mark = " *" if d.get("bottleneck") else ""
                    note = f" ({d['note']})" if d.get("note") else ""
                    print(f"    {d['name']:25s} {d['level']:10s}{mark}{note}")

            results.append({
                "case_id": case_id,
                "name": case_name,
                "category": case.get("category", "?"),
                **v3_info,
            })
        else:
            print(f"  WARNING: JSON report returned {json_resp.status_code}")
            results.append({"case_id": case_id, "name": case_name, "error": json_resp.status_code})

    # Summary table
    print(f"\n\n{'='*80}")
    print(f"  V3 CONFIDENCE SUMMARY — ALL {len(results)} DEMO CASES")
    print(f"{'='*80}")
    print(f"  {'Case':<30s} {'Cat':<10s} {'Confidence':<12s} {'Bottleneck':<25s} {'Align':<8s}")
    print(f"  {'-'*30} {'-'*10} {'-'*12} {'-'*25} {'-'*8}")
    for r in results:
        if "error" in r:
            print(f"  {r['case_id']:<30s} {'ERROR':<10s}")
            continue
        print(
            f"  {r['case_id']:<30s} "
            f"{r.get('category', '?'):<10s} "
            f"{r.get('confidence_level', 'N/A'):<12s} "
            f"{r.get('confidence_bottleneck', 'N/A'):<25s} "
            f"{r.get('governed_alignment', '?'):<8s}"
        )

    # Save summary JSON
    summary_path = OUTPUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\n  Summary JSON: {summary_path}")
    print(f"  HTML reports: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
