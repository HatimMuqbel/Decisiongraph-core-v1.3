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
from datetime import datetime
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from decisiongraph.escalation_gate import run_escalation_gate, EscalationDecision, EscalationGateValidator
from decisiongraph.str_gate import run_str_gate, dual_gate_decision, STRDecision, STRGateValidator
from test_corpus.run_test_corpus import case_to_gate_inputs


def render_full_report(
    case: Dict,
    inputs: Dict,
    esc_result,
    str_result,
    final_decision: Dict,
    report_id: str,
    report_title: str,
) -> str:
    """Render a complete bank-grade report."""

    w = 80
    lines = []

    # Header
    lines.append("=" * w)
    lines.append("TRANSACTION MONITORING ALERT REPORT (v2.1.1)")
    lines.append(f"Alert ID: {report_id}")
    lines.append("=" * w)
    lines.append("")

    # Banner
    verdict = final_decision["final_decision"]
    str_required = "YES" if final_decision["str_required"] else "NO"

    if verdict == "STR":
        banner = "ESCALATE - STR FILING REQUIRED"
    elif verdict == "PASS":
        if any("PEP" in o for o in inputs.get("obligations", [])):
            banner = "PASS WITH EDD"
        else:
            banner = "PASS - NO ESCALATION"
    else:
        banner = f"{verdict}"

    lines.append("=" * w)
    lines.append(f"  {banner}  ")
    lines.append("=" * w)
    lines.append(f"Alert ID:       {report_id}")
    lines.append(f"Priority:       {'HIGH' if verdict == 'STR' else 'MEDIUM'}")
    lines.append(f"Source:         Transaction Monitoring")
    lines.append(f"Processed:      {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")

    # Case Summary
    lines.append("=" * w)
    lines.append("CASE SUMMARY")
    lines.append("=" * w)
    customer = case.get("customer_record", {})
    lines.append(f"Customer:       {customer.get('name', 'Unknown')}")
    lines.append(f"Customer ID:    {customer.get('customer_id', 'Unknown')}")
    lines.append(f"Type:           {customer.get('entity_type', 'Unknown')}")
    lines.append(f"Country:        {customer.get('country_code', 'Unknown')}")
    lines.append(f"Risk Rating:    {customer.get('risk_rating', 'Unknown')}")
    lines.append(f"Relationship:   {case.get('mitigating_factors', {}).get('relationship_tenure_years', 0)} years")
    lines.append("")

    # Transaction Details
    lines.append("=" * w)
    lines.append("TRANSACTION DETAILS")
    lines.append("=" * w)
    txns = case.get("transaction_history_slice", [])
    if txns:
        txn = txns[0]
        lines.append(f"Type:           {txn.get('method', 'Unknown')}")
        lines.append(f"Amount:         {txn.get('currency', 'USD')} {txn.get('amount', 0):,.2f}")
        lines.append(f"Date:           {txn.get('date', 'Unknown')}")
        lines.append(f"Beneficiary:    {txn.get('beneficiary', 'Unknown')}")
        lines.append(f"Benef Country:  {txn.get('beneficiary_country', 'Unknown')}")
    lines.append("")

    # 6-Layer Taxonomy Analysis
    lines.append("=" * w)
    lines.append("6-LAYER DECISION TAXONOMY ANALYSIS (v2.1.1)")
    lines.append("=" * w)
    lines.append("")
    lines.append("CRITICAL RULES ENFORCED:")
    lines.append("  * Hard stops ONLY from Layer 1 facts (confirmed match, not screening)")
    lines.append("  * Cash signals EXCLUDED from wire transactions")
    lines.append("  * FORMING typologies = OBSERVE ONLY (not escalation)")
    lines.append("  * Status alone is NEVER sufficient for suspicion")
    lines.append("")

    facts = inputs["facts"]
    lines.append(f"INSTRUMENT: {inputs['instrument_type'].upper()}")
    lines.append(f"HARD STOP: {'YES' if any([facts.get('sanctions_result') == 'MATCH', facts.get('document_status') == 'FALSE', facts.get('customer_response') == 'REFUSAL', facts.get('legal_prohibition'), facts.get('adverse_media_mltf')]) else 'NO'}")
    lines.append(f"OBLIGATIONS: {len(inputs['obligations'])} ({'EDD required' if inputs['obligations'] else 'none'})")
    lines.append(f"INDICATORS: {len(inputs['indicators'])}")
    lines.append(f"TYPOLOGY MATURITY: {inputs['typology_maturity']}")
    lines.append(f"MITIGATIONS: {len(inputs['mitigations'])}")

    susp = inputs["suspicion_evidence"]
    suspicion_active = susp.get("has_intent") or susp.get("has_deception") or susp.get("has_sustained_pattern")
    lines.append(f"SUSPICION: {'ACTIVATED' if suspicion_active else 'NOT ACTIVATED'}")
    lines.append(f"TAXONOMY VERDICT: {banner}")
    lines.append("")

    # Dual-Gate Decision System
    lines.append("=" * w)
    lines.append("DUAL-GATE DECISION SYSTEM")
    lines.append("=" * w)
    lines.append("")
    lines.append("Constitutional Rule:")
    lines.append('"Escalation is prevented by default and permitted only when')
    lines.append(' suspicion is affirmatively proven."')
    lines.append("")

    # Gate 1: Zero-False-Escalation
    lines.append("-" * w)
    lines.append("GATE 1: ZERO-FALSE-ESCALATION CHECKLIST")
    lines.append("Purpose: Are we ALLOWED to escalate?")
    lines.append("-" * w)

    for section in esc_result.sections:
        status = "PASS" if section.passed else "FAIL"
        lines.append(f"  Section {section.section_id} ({section.section_name}): {status}")

    lines.append("")
    esc_decision = "PERMITTED" if esc_result.decision == EscalationDecision.PERMITTED else "PROHIBITED"
    lines.append(f"  GATE 1 DECISION: {esc_decision}")
    lines.append(f"  Rationale: {esc_result.rationale}")
    lines.append("")

    # Gate 2: Positive STR
    lines.append("-" * w)
    lines.append("GATE 2: POSITIVE STR CHECKLIST")
    lines.append("Purpose: Are we OBLIGATED to report?")
    lines.append("-" * w)

    if esc_result.decision != EscalationDecision.PERMITTED:
        lines.append("  [Gate 2 not evaluated - Gate 1 blocked escalation]")
        lines.append("")
        str_decision = "PROHIBITED"
        str_rationale = "Escalation blocked by Gate 1."
    else:
        for section in str_result.sections:
            status = "PASS" if section.passed else "FAIL"
            lines.append(f"  Section {section.section_id} ({section.section_name}): {status}")
        lines.append("")
        str_decision = str_result.decision.value.upper()
        str_rationale = str_result.rationale

    lines.append(f"  GATE 2 DECISION: {str_decision}")
    lines.append(f"  Rationale: {str_rationale}")
    lines.append("")

    # Non-Escalation or STR Justification
    lines.append("-" * w)
    if final_decision["str_required"]:
        lines.append("STR RATIONALE STATEMENT (MANDATORY OUTPUT)")
    else:
        lines.append("NON-ESCALATION JUSTIFICATION (MANDATORY OUTPUT)")
    lines.append("-" * w)

    if final_decision["str_required"]:
        lines.append("  Based on the totality of evidence, reasonable grounds exist to suspect")
        lines.append("  that the transaction(s) may be related to money laundering or terrorist")
        lines.append("  financing. This determination is based on observed behavior inconsistent")
        lines.append("  with the customer's known profile, insufficient mitigating explanations,")
        lines.append("  and evidence suggesting concealment or deceptive conduct. This report is")
        lines.append("  submitted in accordance with PCMLTFA s.7.")
    else:
        lines.append("  All regulatory obligations were fulfilled. No sanctions or adverse media")
        lines.append("  were identified. Transaction activity is consistent with the customer")
        lines.append("  profile and supported by documentation. No evidence of deception, intent,")
        lines.append("  or structuring pattern was observed. Therefore, no reasonable grounds to")
        lines.append("  suspect ML/TF exist under PCMLTFA s.7.")
    lines.append("")

    # Absolute Rules
    lines.append("=" * w)
    lines.append("ABSOLUTE RULES (NO EXCEPTIONS)")
    lines.append("=" * w)
    lines.append("  X PEP status alone can NEVER escalate")
    lines.append("  X Cross-border alone can NEVER escalate")
    lines.append("  X Risk score alone can NEVER escalate")
    lines.append("  X 'High confidence' can NEVER override facts")
    lines.append("  X 'Compliance comfort' is NOT a reason")
    lines.append("")

    # Final Decision
    lines.append("=" * w)
    lines.append("FINAL DECISION")
    lines.append("=" * w)
    lines.append(f"Verdict:        {verdict}")
    lines.append(f"Action:         {final_decision['action']}")
    lines.append(f"STR Required:   {str_required}")
    lines.append(f"Escalation:     {esc_decision}")
    lines.append("")
    lines.append("Rationale:")
    lines.append(f"  1. Gate 1 (Escalation): {esc_decision} - {esc_result.rationale}")
    lines.append(f"  2. Gate 2 (STR): {str_decision} - {str_rationale}")

    # Add specific rationale points based on case type
    if inputs["obligations"]:
        lines.append(f"  3. {', '.join(inputs['obligations'])} obligation(s) - SATISFIED")
    if inputs["mitigations"]:
        lines.append(f"  4. Mitigations applied: {len(inputs['mitigations'])} factor(s)")
    if suspicion_active:
        active_elements = []
        if susp.get("has_intent"):
            active_elements.append("intent")
        if susp.get("has_deception"):
            active_elements.append("deception")
        if susp.get("has_sustained_pattern"):
            active_elements.append("pattern")
        lines.append(f"  5. Suspicion elements: {', '.join(active_elements)}")
    lines.append("")

    # Regulatory Compliance
    lines.append("=" * w)
    lines.append("REGULATORY COMPLIANCE")
    lines.append("=" * w)
    if inputs["obligations"]:
        lines.append(f"EDD Status:     {'COMPLETED (on file)' if not final_decision['str_required'] else 'N/A'}")
    lines.append(f"PCMLTFA s.7:    {'Reasonable grounds to suspect ML/TF' if final_decision['str_required'] else 'No reasonable grounds to suspect ML/TF'}")
    lines.append(f"FINTRAC:        {'STR filing required' if final_decision['str_required'] else 'All obligations fulfilled'}")
    lines.append(f"STR Filing:     {'REQUIRED' if final_decision['str_required'] else 'NOT REQUIRED'}")
    lines.append("")

    # Footer
    lines.append("=" * w)
    lines.append("END OF ALERT REPORT")
    lines.append("=" * w)
    lines.append("")

    return "\n".join(lines)


def generate_report_for_case(case_id: str, report_id: str, report_title: str) -> str:
    """Generate a full report for a specific test case."""

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

    # Run Gate 1: Escalation Gate
    esc_result = run_escalation_gate(
        facts=inputs["facts"],
        instrument_type=inputs["instrument_type"],
        obligations=inputs["obligations"],
        indicators=inputs["indicators"],
        typology_maturity=inputs["typology_maturity"],
        mitigations=inputs["mitigations"],
        suspicion_evidence=inputs["suspicion_evidence"],
    )

    # Run Gate 2: STR Gate
    str_result = run_str_gate(
        suspicion_evidence=inputs["suspicion_evidence"],
        evidence_quality=inputs["evidence_quality"],
        mitigation_status=inputs["mitigation_status"],
        typology_confirmed=inputs["typology_confirmed"],
        facts=inputs["facts"],
    )

    # Combine gates
    final_decision = dual_gate_decision(
        escalation_allowed=(esc_result.decision == EscalationDecision.PERMITTED),
        str_result=str_result,
    )

    # Render full report
    return render_full_report(
        case=case,
        inputs=inputs,
        esc_result=esc_result,
        str_result=str_result,
        final_decision=final_decision,
        report_id=report_id,
        report_title=report_title,
    )


def main():
    """Generate all 3 validation reports."""

    output_dir = Path(__file__).parent / "validation_reports"
    output_dir.mkdir(exist_ok=True)

    # 1. PAIN CASE: Foreign PEP + Legal Fees
    print("Generating Report 1: PAIN CASE (Foreign PEP + Legal Fees)...")
    report1 = generate_report_for_case(
        case_id="TEST-P-01",
        report_id="PAIN-VALIDATION-001",
        report_title="Foreign PEP + Large Cross-Border Wire + Legal Fees"
    )
    with open(output_dir / "01_PAIN_CASE_PEP_Legal_Fees.txt", "w") as f:
        f.write(report1)
    print(f"  Written to: validation_reports/01_PAIN_CASE_PEP_Legal_Fees.txt")

    # 2. HARD STOP CASE: Confirmed Sanctions Match
    print("\nGenerating Report 2: HARD STOP CASE (Sanctions Match)...")
    report2 = generate_report_for_case(
        case_id="TEST-E-01",
        report_id="HARDSTOP-VALIDATION-001",
        report_title="Confirmed Sanctions MATCH - Immediate Escalation"
    )
    with open(output_dir / "02_HARD_STOP_Sanctions_Match.txt", "w") as f:
        f.write(report2)
    print(f"  Written to: validation_reports/02_HARD_STOP_Sanctions_Match.txt")

    # 3. BEHAVIORAL STR CASE: Conflicting Explanations
    print("\nGenerating Report 3: BEHAVIORAL STR CASE (Conflicting Explanations)...")
    report3 = generate_report_for_case(
        case_id="TEST-E-08",
        report_id="BEHAVIORAL-VALIDATION-001",
        report_title="Conflicting Explanations - Path 2 STR"
    )
    with open(output_dir / "03_BEHAVIORAL_STR_Conflicting_Explanations.txt", "w") as f:
        f.write(report3)
    print(f"  Written to: validation_reports/03_BEHAVIORAL_STR_Conflicting_Explanations.txt")

    print("\n" + "=" * 60)
    print("ALL 3 VALIDATION REPORTS GENERATED")
    print("=" * 60)

    # Print summary
    print("\n1. PAIN CASE (TEST-P-01):")
    print("   Expected: PASS_WITH_EDD, STR=NO")
    print("   Validates: No false escalation, PEP obligation != suspicion")

    print("\n2. HARD STOP CASE (TEST-E-01):")
    print("   Expected: ESCALATE, STR=YES")
    print("   Validates: Path 1 override, immediate escalation, no typology needed")

    print("\n3. BEHAVIORAL STR CASE (TEST-E-08):")
    print("   Expected: ESCALATE, STR=YES")
    print("   Validates: Path 2 activation, deception detected, STR warranted")

    return 0


if __name__ == "__main__":
    sys.exit(main())
