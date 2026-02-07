#!/usr/bin/env python3
"""
E2E Report: PAIN CASE - Foreign PEP with Established Relationship

Hon. Marco DeLuca - Former Deputy Minister of Transport (Italy)
- 14 year relationship (ESTABLISHED)
- Foreign PEP status (EDD obligation, NOT suspicion)
- Large cross-border wire (legitimate purpose)
- Full documentation on file

Expected: PASS_WITH_EDD, STR=NO
Validates: PEP status alone CANNOT escalate
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from decisiongraph.escalation_gate import run_escalation_gate, EscalationDecision
from decisiongraph.str_gate import run_str_gate, dual_gate_decision
from decisiongraph.decision_pack import build_decision_pack
from service.routers.report.pipeline import compile_report


def build_case_inputs():
    """Build inputs for the PEP PAIN case."""

    # Facts (Layer 1) - NO hard stops
    facts = {
        "sanctions_result": "NO_MATCH",
        "document_status": "VALID",
        "customer_response": "COMPLIANT",
        "adverse_media_mltf": False,
        "legal_prohibition": False,
    }

    # NO suspicious behavior
    suspicion_evidence = {
        "has_intent": False,
        "has_deception": False,
        "has_sustained_pattern": False,
    }

    # Indicators - some triggered but NOT corroborated
    indicators = [
        {"code": "PEP_FOREIGN", "corroborated": False},  # Status, not behavior
        {"code": "CROSS_BORDER", "corroborated": False},  # Normal for PEP
    ]

    # Typology - FORMING at best (no confirmed pattern)
    typology_maturity = "FORMING"

    # Strong mitigations
    mitigations = [
        "MF_ESTABLISHED_RELATIONSHIP",  # 14 years
        "MF_DOCUMENTATION_COMPLETE",
        "MF_SOURCE_OF_FUNDS",
        "MF_TXN_SUPPORTING_INVOICE",
        "MF_SCREEN_FALSE_POSITIVE",
    ]

    # Obligations - PEP triggers EDD
    obligations = ["PEP_FOREIGN"]

    # Evidence quality - NOT fact-based (only status)
    evidence_quality = {
        "is_fact_based": False,  # PEP status is not suspicion
        "is_specific": False,  # Generic status indicator
        "is_reproducible": True,
        "is_regulator_clear": True,
    }

    # Mitigation status - mitigations EXPLAIN behavior
    mitigation_status = {
        "explanation_insufficient": False,  # Explanation provided
        "docs_unsupportive": False,  # Docs support purpose
        "history_misaligned": False,  # 14 years of consistent behavior
    }

    return {
        "facts": facts,
        "instrument_type": "wire",
        "obligations": obligations,
        "indicators": indicators,
        "typology_maturity": typology_maturity,
        "mitigations": mitigations,
        "suspicion_evidence": suspicion_evidence,
        "evidence_quality": evidence_quality,
        "mitigation_status": mitigation_status,
        "typology_confirmed": False,
    }


def main():
    """Run the E2E report for the PEP PAIN case."""

    print("=" * 60)
    print("RUNNING E2E: PAIN CASE - Foreign PEP (Marco DeLuca)")
    print("=" * 60)
    print()

    # Build inputs
    inputs = build_case_inputs()

    # Run Gate 1
    print("Running Gate 1 (Zero-False-Escalation)...")
    esc_result = run_escalation_gate(
        facts=inputs["facts"],
        instrument_type=inputs["instrument_type"],
        obligations=inputs["obligations"],
        indicators=inputs["indicators"],
        typology_maturity=inputs["typology_maturity"],
        mitigations=inputs["mitigations"],
        suspicion_evidence=inputs["suspicion_evidence"],
    )
    print(f"  Decision: {esc_result.decision}")

    # Run Gate 2
    print("Running Gate 2 (Positive STR)...")
    str_result = run_str_gate(
        suspicion_evidence=inputs["suspicion_evidence"],
        evidence_quality=inputs["evidence_quality"],
        mitigation_status=inputs["mitigation_status"],
        typology_confirmed=inputs["typology_confirmed"],
        facts=inputs["facts"],
    )
    print(f"  Decision: {str_result.decision}")

    # Combine
    final_decision = dual_gate_decision(
        escalation_allowed=(esc_result.decision == EscalationDecision.PERMITTED),
        str_result=str_result,
    )
    print(f"  Final: {final_decision['final_decision']}, STR={final_decision['str_required']}")
    print()

    # Build decision pack
    input_data = {k: inputs[k] for k in (
        "facts", "obligations", "indicators", "typology_maturity",
        "mitigations", "suspicion_evidence", "instrument_type",
    )}
    decision_pack = build_decision_pack(
        case_id="PAIN-VALIDATION-002",
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
        jurisdiction="CA",
    )

    # Enrich with customer / transaction data so evidence table is complete
    evidence = decision_pack.setdefault("evaluation_trace", {}).setdefault("evidence_used", [])
    evidence.extend([
        {"field": "customer.pep_flag", "value": True},
        {"field": "customer.type", "value": "INDIVIDUAL"},
        {"field": "risk.high_risk_jurisdiction", "value": False},
        {"field": "txn.amount_band", "value": "100K+"},
        {"field": "txn.method", "value": "SWIFT Wire Transfer"},
        {"field": "txn.destination_country", "value": "IT"},
        {"field": "txn.cross_border", "value": True},
    ])
    layer1 = decision_pack.setdefault("layers", {}).setdefault("layer1_facts", {})
    facts_dict = layer1.setdefault("facts", {})
    facts_dict["customer"] = {"pep_flag": True, "type": "INDIVIDUAL", "residence": "IT"}
    facts_dict["transaction"] = {"amount_cad": 265_000, "method": "SWIFT Wire Transfer", "destination": "IT"}

    # One pipeline, one path
    report = compile_report(decision_pack)

    # Save
    output_dir = Path(__file__).parent / "validation_reports"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "05_PAIN_PEP_Marco_DeLuca.md"
    with open(output_path, "w") as f:
        f.write(report)

    print(f"Report saved to: {output_path}")
    print()
    print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
