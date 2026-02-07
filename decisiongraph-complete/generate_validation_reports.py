#!/usr/bin/env python3
"""
Generate Full E2E Validation Reports for the 3 Critical Test Cases

1. PAIN CASE: Foreign PEP + Legal Fees (Elena Moretti baseline)
   - Validates: No false escalation, obligation != suspicion

2. HARD STOP CASE: Confirmed Sanctions Match
   - Validates: Path 1 override, immediate escalation

3. BEHAVIORAL STR CASE: Conflicting Explanations
   - Validates: Path 2 activation, STR filing warranted
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from decisiongraph.escalation_gate import run_escalation_gate, EscalationDecision
from decisiongraph.str_gate import run_str_gate, dual_gate_decision
from decisiongraph.decision_pack import build_decision_pack
from service.routers.report.pipeline import compile_report
from test_corpus.run_test_corpus import case_to_gate_inputs


def generate_report_for_case(case_id: str) -> str:
    """Generate a v2 pipeline report for a specific test case."""

    # Load test corpus
    corpus_path = Path(__file__).parent / "test_corpus" / "dual_gate_test_cases.json"
    with open(corpus_path, "r") as f:
        corpus = json.load(f)

    # Find the case
    case = None
    for c in corpus["cases"]:
        if c["alert_details"]["external_id"] == case_id:
            case = c
            break

    if not case:
        raise ValueError(f"Case {case_id} not found in test corpus")

    # Extract inputs
    inputs = case_to_gate_inputs(case)

    # Run Gate 1
    esc_result = run_escalation_gate(
        facts=inputs["facts"],
        instrument_type=inputs["instrument_type"],
        obligations=inputs["obligations"],
        indicators=inputs["indicators"],
        typology_maturity=inputs["typology_maturity"],
        mitigations=inputs["mitigations"],
        suspicion_evidence=inputs["suspicion_evidence"],
    )

    # Run Gate 2
    str_result = run_str_gate(
        suspicion_evidence=inputs["suspicion_evidence"],
        evidence_quality=inputs["evidence_quality"],
        mitigation_status=inputs["mitigation_status"],
        typology_confirmed=inputs["typology_confirmed"],
        facts=inputs["facts"],
    )

    # Combine
    final_decision = dual_gate_decision(
        escalation_allowed=(esc_result.decision == EscalationDecision.PERMITTED),
        str_result=str_result,
    )

    # Build decision pack
    input_data = {k: inputs[k] for k in (
        "facts", "obligations", "indicators", "typology_maturity",
        "mitigations", "suspicion_evidence", "instrument_type",
    )}
    decision_pack = build_decision_pack(
        case_id=case_id,
        input_data=input_data,
        facts=inputs["facts"],
        obligations=inputs["obligations"],
        indicators=inputs["indicators"],
        typology_maturity=inputs["typology_maturity"],
        mitigations=inputs["mitigations"],
        suspicion_evidence=inputs["suspicion_evidence"],
        esc_result=esc_result,
        str_result=str_result,
        final_decision=final_decision,
        jurisdiction=case.get("jurisdiction", "CA"),
    )

    # Enrich with customer/transaction data from the case
    customer_record = case.get("customer_record", {})
    txns = case.get("transaction_history_slice", [])
    txn = txns[0] if txns else {}

    evidence = decision_pack.setdefault("evaluation_trace", {}).setdefault("evidence_used", [])
    evidence.extend([
        {"field": "customer.pep_flag", "value": bool(customer_record.get("pep_status"))},
        {"field": "customer.type", "value": customer_record.get("entity_type", "INDIVIDUAL")},
        {"field": "risk.high_risk_jurisdiction", "value": False},
    ])
    if txn.get("amount"):
        amt = txn["amount"]
        band = "100K+" if amt >= 100_000 else "50K-100K" if amt >= 50_000 else "10K-50K" if amt >= 10_000 else "<10K"
        evidence.append({"field": "txn.amount_band", "value": band})
    if txn.get("method"):
        evidence.append({"field": "txn.method", "value": txn["method"]})
    if txn.get("beneficiary_country"):
        evidence.append({"field": "txn.destination_country", "value": txn["beneficiary_country"]})
    evidence.append({"field": "txn.cross_border", "value": txn.get("cross_border", False)})

    layer1 = decision_pack.setdefault("layers", {}).setdefault("layer1_facts", {})
    facts_dict = layer1.setdefault("facts", {})
    facts_dict["customer"] = {
        "pep_flag": bool(customer_record.get("pep_status")),
        "type": customer_record.get("entity_type", "INDIVIDUAL"),
        "residence": customer_record.get("country_code", "CA"),
    }
    facts_dict["transaction"] = {
        "amount_cad": txn.get("amount", 0),
        "method": txn.get("method", "unknown"),
        "destination": txn.get("beneficiary_country", ""),
    }

    # One pipeline, one path
    return compile_report(decision_pack)


def main():
    """Generate all 3 validation reports."""

    output_dir = Path(__file__).parent / "validation_reports"
    output_dir.mkdir(exist_ok=True)

    cases = [
        ("TEST-P-01", "01_PAIN_CASE_PEP_Legal_Fees.md",
         "PAIN CASE (Foreign PEP + Legal Fees)",
         "Expected: PASS_WITH_EDD, STR=NO"),
        ("TEST-E-01", "02_HARD_STOP_Sanctions_Match.md",
         "HARD STOP CASE (Sanctions Match)",
         "Expected: ESCALATE, STR=YES"),
        ("TEST-E-08", "03_BEHAVIORAL_STR_Conflicting_Explanations.md",
         "BEHAVIORAL STR CASE (Conflicting Explanations)",
         "Expected: ESCALATE, STR=YES"),
    ]

    for i, (case_id, filename, title, expected) in enumerate(cases, 1):
        print(f"Generating Report {i}: {title}...")
        report = generate_report_for_case(case_id)
        path = output_dir / filename
        with open(path, "w") as f:
            f.write(report)
        print(f"  Written to: validation_reports/{filename}")
        print(f"  {expected}")

    print("\n" + "=" * 60)
    print("ALL 3 VALIDATION REPORTS GENERATED")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
