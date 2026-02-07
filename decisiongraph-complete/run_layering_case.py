#!/usr/bin/env python3
"""
E2E Report: LAYERING CASE - Multi-Instrument Pattern

Northern Apex Consulting Inc.
- Crypto liquidation (2.45 BTC → CAD 162,000)
- Structured cash withdrawals (3 x just under CAD 10K = CAD 29,100)
- Wire to offshore entity (Estonia)
- No clear business rationale

Expected: ESCALATE, STR=YES via Path 2 (Behavioral Suspicion)
Typology: CONFIRMED (Layering - Crypto/Cash/Wire chain)
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
    """Build inputs for the layering case."""

    # Facts (Layer 1) - NO hard stops but suspicious behavior
    facts = {
        "sanctions_result": "NO_MATCH",
        "document_status": "VALID",
        "customer_response": "COMPLIANT",
        "adverse_media_mltf": False,
        "legal_prohibition": False,
    }

    # Layering pattern = clear intent + pattern
    # Crypto → Cash structuring → Wire to offshore
    suspicion_evidence = {
        "has_intent": True,  # Layering = intent to obscure
        "has_deception": False,  # No direct deception (yet)
        "has_sustained_pattern": True,  # Multi-step, multi-instrument
    }

    # Indicators - all corroborated by transaction chain
    indicators = [
        {"code": "LAYER_CRYPTO_CASH", "corroborated": True},
        {"code": "STRUCT_CASH_MULTIPLE", "corroborated": True},
        {"code": "LAYER_CASH_WIRE", "corroborated": True},
        {"code": "OFFSHORE_TRANSFER", "corroborated": True},
        {"code": "BUSINESS_MISMATCH", "corroborated": True},
    ]

    # Typology maturity - CONFIRMED (clear layering chain)
    typology_maturity = "CONFIRMED"

    # Limited mitigations
    mitigations = [
        "MF_DOCUMENTATION_COMPLETE",  # Basic docs on file
    ]
    # Note: No established relationship (8 months)
    # Note: No source of funds for crypto
    # Note: No business rationale for offshore wire

    # Obligations - none (not PEP, no special status)
    obligations = []

    # Evidence quality - fact-based (transaction pattern)
    evidence_quality = {
        "is_fact_based": True,  # Transaction chain is factual
        "is_specific": True,  # Specific layering pattern
        "is_reproducible": True,  # Transaction records
        "is_regulator_clear": True,  # Classic layering
    }

    # Mitigation status - mitigations FAIL to explain
    mitigation_status = {
        "explanation_insufficient": True,  # "Consulting services" doesn't explain crypto→cash→wire
        "docs_unsupportive": True,  # No contract for Baltic trade
        "history_misaligned": True,  # No prior crypto activity, sudden offshore wire
    }

    return {
        "facts": facts,
        "instrument_type": "mixed",  # Crypto + Cash + Wire
        "obligations": obligations,
        "indicators": indicators,
        "typology_maturity": typology_maturity,
        "mitigations": mitigations,
        "suspicion_evidence": suspicion_evidence,
        "evidence_quality": evidence_quality,
        "mitigation_status": mitigation_status,
        "typology_confirmed": True,
    }


def main():
    """Run the E2E report for the layering case."""

    print("=" * 60)
    print("RUNNING E2E: LAYERING CASE - Crypto/Cash/Wire Chain")
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
        case_id="CAN-2026-003",
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
        {"field": "txn.amount_band", "value": "100K+"},
        {"field": "txn.method", "value": "Crypto/Cash/Wire"},
        {"field": "txn.destination_country", "value": "EE"},
        {"field": "txn.cross_border", "value": True},
    ])
    layer1 = decision_pack.setdefault("layers", {}).setdefault("layer1_facts", {})
    facts_dict = layer1.setdefault("facts", {})
    facts_dict["customer"] = {"pep_flag": False, "type": "CORPORATE", "residence": "CA"}
    facts_dict["transaction"] = {"amount_cad": 162_000, "method": "Crypto/Cash/Wire", "destination": "EE"}

    # One pipeline, one path
    report = compile_report(decision_pack)

    # Save
    output_dir = Path(__file__).parent / "validation_reports"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "06_LAYERING_Crypto_Cash_Wire.md"
    with open(output_path, "w") as f:
        f.write(report)

    print(f"Report saved to: {output_path}")
    print()
    print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
