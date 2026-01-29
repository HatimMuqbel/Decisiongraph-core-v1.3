#!/usr/bin/env python3
"""
DecisionGraph CLI: Replay Tool

Replay a case by ID or JSON payload and reproduce the decision.
Used for audit, debugging, and regression testing.

Usage:
    python -m cli.replay --case PAIN-VALIDATION-001
    python -m cli.replay --file test_corpus/cases/PAIN-VALIDATION-001.json
    python -m cli.replay --file case.json --golden expected.json
"""

import argparse
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from decisiongraph.decision_pack import (
    build_decision_pack,
    format_golden_output,
    normalize_for_golden,
    compute_input_hash,
    ENGINE_VERSION,
    POLICY_VERSION,
)
from decisiongraph.escalation_gate import run_escalation_gate, EscalationDecision
from decisiongraph.str_gate import run_str_gate, dual_gate_decision


def load_case(case_path: Path) -> dict:
    """Load case from JSON file."""
    with open(case_path) as f:
        return json.load(f)


def find_case_by_id(case_id: str) -> Path:
    """Find case file by ID in test corpus."""
    corpus_dir = Path(__file__).parent.parent / "test_corpus" / "cases"
    case_file = corpus_dir / f"{case_id}.json"
    if case_file.exists():
        return case_file

    # Try with different extensions/patterns
    for pattern in [f"{case_id}.json", f"{case_id.lower()}.json", f"{case_id.upper()}.json"]:
        matches = list(corpus_dir.glob(pattern))
        if matches:
            return matches[0]

    raise FileNotFoundError(f"Case not found: {case_id}")


def run_case(case_data: dict) -> dict:
    """Run the decision engine on a case and return decision pack."""
    # Extract case metadata
    case_id = case_data.get("alert_details", {}).get("external_id", "UNKNOWN")

    # Map case data to engine inputs
    facts = extract_facts(case_data)
    obligations = extract_obligations(case_data)
    indicators = extract_indicators(case_data)
    typology_maturity = case_data.get("typology_maturity", "FORMING")
    mitigations = extract_mitigations(case_data)
    suspicion_evidence = extract_suspicion_evidence(case_data)
    instrument_type = extract_instrument_type(case_data)
    evidence_quality = case_data.get("evidence_quality", {})
    mitigation_status = case_data.get("mitigation_status", {})
    typology_confirmed = case_data.get("typology_confirmed", False)

    # Run Gate 1
    esc_result = run_escalation_gate(
        facts=facts,
        instrument_type=instrument_type,
        obligations=obligations,
        indicators=indicators,
        typology_maturity=typology_maturity,
        mitigations=mitigations,
        suspicion_evidence=suspicion_evidence,
    )

    # Run Gate 2
    str_result = run_str_gate(
        suspicion_evidence=suspicion_evidence,
        evidence_quality=evidence_quality,
        mitigation_status=mitigation_status,
        typology_confirmed=typology_confirmed,
        facts=facts,
    )

    # Combine decisions
    final_decision = dual_gate_decision(
        escalation_allowed=(esc_result.decision == EscalationDecision.PERMITTED),
        str_result=str_result,
    )

    # Build decision pack
    decision_pack = build_decision_pack(
        case_id=case_id,
        input_data=case_data,
        facts=facts,
        obligations=obligations,
        indicators=indicators,
        typology_maturity=typology_maturity,
        mitigations=mitigations,
        suspicion_evidence=suspicion_evidence,
        esc_result=esc_result,
        str_result=str_result,
        final_decision=final_decision,
        jurisdiction=case_data.get("jurisdiction", "CA"),
        fintrac_indicators=case_data.get("fintrac_indicators", []),
    )

    return decision_pack


def extract_facts(case_data: dict) -> dict:
    """Extract Layer 1 facts from case data."""
    screening = case_data.get("screening_payload", {})
    top_match = screening.get("top_match", {})

    # Determine sanctions result
    sanctions_result = "NO_MATCH"
    if top_match and top_match.get("list_type", "").startswith(("OFAC", "UN_", "EU_", "UK_", "CA_")):
        if top_match.get("match_score", 0) >= 90:
            sanctions_result = "MATCH"

    # Check for adverse media linked to ML/TF
    adverse_media = screening.get("adverse_media", {})
    adverse_media_mltf = adverse_media.get("mltf_linked", False)

    return case_data.get("facts", {
        "sanctions_result": sanctions_result,
        "document_status": "VALID",
        "customer_response": "COMPLIANT",
        "adverse_media_mltf": adverse_media_mltf,
        "legal_prohibition": False,
    })


def extract_obligations(case_data: dict) -> list:
    """Extract Layer 2 obligations from case data."""
    if "obligations" in case_data:
        return case_data["obligations"]

    obligations = []
    customer = case_data.get("customer_record", {})

    if customer.get("pep_flag") == "Y":
        category = customer.get("pep_category_code", "FOREIGN")
        obligations.append(f"PEP_{category}")

    return obligations


def extract_indicators(case_data: dict) -> list:
    """Extract Layer 3 indicators from case data."""
    return case_data.get("indicators", [])


def extract_mitigations(case_data: dict) -> list:
    """Extract Layer 5 mitigations from case data."""
    return case_data.get("mitigations", [])


def extract_suspicion_evidence(case_data: dict) -> dict:
    """Extract Layer 6 suspicion evidence from case data."""
    return case_data.get("suspicion_evidence", {
        "has_intent": False,
        "has_deception": False,
        "has_sustained_pattern": False,
    })


def extract_instrument_type(case_data: dict) -> str:
    """Extract instrument type from transactions."""
    if "instrument_type" in case_data:
        return case_data["instrument_type"]

    transactions = case_data.get("transaction_history_slice", [])
    if not transactions:
        return "unknown"

    methods = set(t.get("method", "").lower() for t in transactions)
    if len(methods) > 1:
        return "mixed"

    method = methods.pop() if methods else "unknown"
    return {
        "wire": "wire",
        "cash": "cash",
        "crypto": "crypto",
        "cheque": "cheque",
    }.get(method, "unknown")


def compare_with_golden(actual: dict, golden_path: Path) -> tuple:
    """Compare actual output with golden file. Returns (matches, diff)."""
    with open(golden_path) as f:
        expected = json.load(f)

    actual_normalized = normalize_for_golden(actual)
    expected_normalized = normalize_for_golden(expected)

    actual_str = json.dumps(actual_normalized, sort_keys=True, indent=2)
    expected_str = json.dumps(expected_normalized, sort_keys=True, indent=2)

    matches = actual_str == expected_str

    if not matches:
        # Generate simple diff
        actual_lines = actual_str.splitlines()
        expected_lines = expected_str.splitlines()
        diff = []
        for i, (a, e) in enumerate(zip(actual_lines, expected_lines)):
            if a != e:
                diff.append(f"Line {i+1}:")
                diff.append(f"  Expected: {e}")
                diff.append(f"  Actual:   {a}")
        return False, "\n".join(diff[:30])  # First 30 lines of diff

    return True, None


def main():
    parser = argparse.ArgumentParser(
        description="Replay a case and reproduce the decision"
    )
    parser.add_argument(
        "--case",
        help="Case ID to replay from test corpus"
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Path to case JSON file"
    )
    parser.add_argument(
        "--golden",
        type=Path,
        help="Path to golden output file for comparison"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Path to write output JSON"
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty print output"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    if not args.case and not args.file:
        parser.error("Either --case or --file is required")

    # Load case
    if args.case:
        case_path = find_case_by_id(args.case)
    else:
        case_path = args.file

    if args.verbose:
        print(f"Loading case from: {case_path}")

    case_data = load_case(case_path)

    # Run case
    if args.verbose:
        print(f"Running case with engine v{ENGINE_VERSION}, policy v{POLICY_VERSION}")

    decision_pack = run_case(case_data)

    # Compare with golden if provided
    if args.golden:
        matches, diff = compare_with_golden(decision_pack, args.golden)
        if matches:
            print("MATCH - Output matches golden file")
        else:
            print("MISMATCH - Output differs from golden file")
            print(diff)
            return 1

    # Output
    if args.output:
        with open(args.output, "w") as f:
            json.dump(decision_pack, f, indent=2, sort_keys=True)
        if args.verbose:
            print(f"Output written to: {args.output}")
    else:
        if args.pretty:
            print(json.dumps(decision_pack, indent=2, sort_keys=True))
        else:
            # Print summary
            print(f"Case:       {decision_pack['meta']['case_id']}")
            print(f"Input Hash: {decision_pack['meta']['input_hash'][:16]}...")
            print(f"Verdict:    {decision_pack['decision']['verdict']}")
            print(f"STR:        {decision_pack['decision']['str_required']}")
            print(f"Escalation: {decision_pack['decision']['escalation']}")
            print(f"Path:       {decision_pack['decision']['path'] or 'N/A'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
