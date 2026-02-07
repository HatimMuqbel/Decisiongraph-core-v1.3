#!/usr/bin/env python3
"""
E2E Report: Corporate Structuring Case CAN-2026-002

Maple Leaf Global Trading Ltd.
- 2 CASH deposits just under $10K within 24 hours = $18,700 total
- New customer (2 months tenure)
- UBO discrepancy detected
- No sanctions, no adverse media

Expected: Path 2 activation → ESCALATE, STR=YES

REFINEMENTS APPLIED:
- Instrument: CASH (not wire) for LCTR threshold evasion logic
- UBO evidence: Specific wording per report_standards
- Intent wording: Standardized per FINTRAC expectations
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
    """Build inputs from the YAML case specification."""

    # Facts (Layer 1)
    facts = {
        "sanctions_result": "NO_MATCH",
        "document_status": "VALID",  # Business license provided
        "customer_response": "COMPLIANT",
        "adverse_media_mltf": False,
        "legal_prohibition": False,
        # Additional facts for str_basis audit trail
        "multiple_same_day_txns": True,
        "just_below_threshold": True,
        "ubo_discrepancy": True,
        "high_risk_industry": True,
    }

    # Structuring detected: 2 transactions just under $10K in 24 hours
    # $9,500 + $9,200 = $18,700 total
    has_structuring = True  # Just-under-threshold pattern
    has_ubo_discrepancy = True  # UBO discrepancy = potential deception

    # Suspicion evidence
    suspicion_evidence = {
        "has_intent": True,  # Structuring = intent to evade threshold
        "has_deception": True,  # UBO discrepancy = deception
        "has_sustained_pattern": True,  # Multiple same-day transactions
    }

    # Indicators
    indicators = [
        {"code": "SIG_CAN_STR_24H", "corroborated": True},  # Structuring pattern
        {"code": "SIG_CAN_ISC_GAP", "corroborated": True},  # UBO discrepancy
        {"code": "SIG_NEW_ACCOUNT", "corroborated": True},  # 2 month tenure
    ]

    # Typology maturity - CONFIRMED due to clear structuring pattern
    typology_maturity = "CONFIRMED"

    # Mitigations (limited due to new account)
    mitigations = [
        "MF_DOCUMENTATION_COMPLETE",  # Business license provided
    ]
    # Note: No MF_ESTABLISHED_RELATIONSHIP (only 2 months)
    # Note: No MF_SOURCE_OF_FUNDS (not verified)

    # Evidence quality
    evidence_quality = {
        "is_fact_based": True,  # Transaction pattern is factual
        "is_specific": True,  # Specific structuring behavior
        "is_reproducible": True,  # Transaction records
        "is_regulator_clear": True,  # Classic structuring pattern
    }

    # Mitigation status - mitigations FAIL to explain
    mitigation_status = {
        "explanation_insufficient": True,  # No explanation for just-under-threshold
        "docs_unsupportive": True,  # Docs don't explain transaction pattern
        "history_misaligned": True,  # New account, structuring from day 1
    }

    return {
        "facts": facts,
        "instrument_type": "cash",  # CASH for LCTR threshold evasion
        "obligations": [],  # No PEP, no special obligations
        "indicators": indicators,
        "typology_maturity": typology_maturity,
        "mitigations": mitigations,
        "suspicion_evidence": suspicion_evidence,
        "evidence_quality": evidence_quality,
        "mitigation_status": mitigation_status,
        "typology_confirmed": True,
    }


def main():
    """Run the E2E report for the structuring case."""

    print("=" * 60)
    print("RUNNING E2E: Corporate Structuring Case CAN-2026-002")
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
        case_id="CAN-2026-002",
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

    # Enrich with customer / transaction data
    evidence = decision_pack.setdefault("evaluation_trace", {}).setdefault("evidence_used", [])
    evidence.extend([
        {"field": "customer.pep_flag", "value": False},
        {"field": "customer.type", "value": "CORPORATE"},
        {"field": "risk.high_risk_jurisdiction", "value": False},
        {"field": "txn.amount_band", "value": "10K-50K"},
        {"field": "txn.method", "value": "Cash Deposit"},
        {"field": "txn.destination_country", "value": "CA"},
        {"field": "txn.cross_border", "value": False},
    ])
    layer1 = decision_pack.setdefault("layers", {}).setdefault("layer1_facts", {})
    facts_dict = layer1.setdefault("facts", {})
    facts_dict["customer"] = {"pep_flag": False, "type": "CORPORATE", "residence": "CA"}
    facts_dict["transaction"] = {"amount_cad": 18_700, "method": "Cash Deposit", "destination": "CA"}

    # One pipeline, one path
    report = compile_report(decision_pack)

    # Save
    output_dir = Path(__file__).parent / "validation_reports"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "04_STRUCTURING_Maple_Leaf_Corp.md"
    with open(output_path, "w") as f:
        f.write(report)

    print(f"Report saved to: {output_path}")
    print()
    print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
