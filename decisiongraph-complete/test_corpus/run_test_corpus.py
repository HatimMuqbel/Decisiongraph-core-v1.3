#!/usr/bin/env python3
"""
DecisionGraph Test Corpus Runner

Validates all 25 test cases against the dual-gate decision system.
Any mismatch between expected and actual verdict = FAIL.
"""

import json
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from decisiongraph.escalation_gate import run_escalation_gate, EscalationDecision
from decisiongraph.str_gate import run_str_gate, STRDecision, dual_gate_decision


@dataclass
class TestResult:
    """Result of a single test case."""
    case_id: str
    test_family: str
    description: str
    expected_verdict: str
    actual_verdict: str
    expected_str: str
    actual_str: str
    gate_1_expected: str
    gate_1_actual: str
    gate_2_expected: str
    gate_2_actual: str
    passed: bool
    failure_reason: str = ""


def case_to_gate_inputs(case: Dict) -> Dict:
    """Convert a test case JSON to gate input parameters."""

    # Extract facts
    screening = case.get("screening_payload", {})
    top_match = screening.get("top_match") or {}
    mitigations = case.get("mitigating_factors", {})

    # Check for sanctions match
    sanctions_match = top_match.get("confirmed_sanctions_match", False)

    # Check for document fraud (could be bool or string description)
    doc_fraud = mitigations.get("document_fraud_detected")
    has_doc_fraud = bool(doc_fraud) and doc_fraud not in (False, "FALSE", "false", "")

    # Check for customer refusal (could be bool or string description)
    cust_refusal = mitigations.get("customer_refusal")
    has_refusal = bool(cust_refusal) and cust_refusal not in (False, "FALSE", "false", "")

    # Check for adverse media linked to ML/TF
    adverse_media = top_match.get("adverse_media")
    has_adverse_media = bool(adverse_media)

    # Check for regulator instruction
    reg_instruction = mitigations.get("regulator_instruction")
    has_reg_instruction = bool(reg_instruction) and reg_instruction not in (False, "FALSE", "false", "")

    facts = {
        "sanctions_result": "MATCH" if sanctions_match else "NO_MATCH",
        "document_status": "FALSE" if has_doc_fraud else "VALID",
        "customer_response": "REFUSAL" if has_refusal else "COMPLIANT",
        "adverse_media_mltf": has_adverse_media,
        "legal_prohibition": has_reg_instruction,
    }

    # Detect instrument type
    transactions = case.get("transaction_history_slice", [])
    instrument_type = "unknown"
    for tx in transactions:
        method = tx.get("method", "").upper()
        if "WIRE" in method or "SWIFT" in method:
            instrument_type = "wire"
            break
        if "CASH" in method:
            instrument_type = "cash"
            break
        if "EFT" in method:
            instrument_type = "wire"
            break

    # Get obligations
    customer = case.get("customer_record", {})
    obligations = []
    if customer.get("pep_flag") == "Y":
        obligations.append("PEP_FOREIGN")

    # Get hit rules for later use
    alert = case.get("alert_details", {})
    hit_rules = alert.get("hit_rule_ids", [])

    # Get mitigations list
    mitigation_list = []
    if mitigations.get("relationship_tenure_years", 0) >= 10:
        mitigation_list.append("MF_ESTABLISHED_RELATIONSHIP")
    if mitigations.get("documentation_complete"):
        mitigation_list.append("MF_DOCUMENTATION_COMPLETE")
    if mitigations.get("supporting_invoice"):
        mitigation_list.append("MF_TXN_SUPPORTING_INVOICE")
    if mitigations.get("screening_false_positive_confirmed"):
        mitigation_list.append("MF_SCREEN_FALSE_POSITIVE")
    if mitigations.get("source_of_funds_verified"):
        mitigation_list.append("MF_SOURCE_OF_FUNDS")

    # Build suspicion evidence - check for any non-empty string values
    structuring = mitigations.get("structuring_pattern_detected")
    layering = mitigations.get("layering_detected")
    timing = mitigations.get("timing_concern")
    conflicting = mitigations.get("conflicting_explanations")
    prof_abuse = mitigations.get("professional_abuse_indicators")

    has_structuring = bool(structuring) and structuring not in (False, "FALSE", "false", "")
    has_layering = bool(layering) and layering not in (False, "FALSE", "false", "")
    has_timing = bool(timing) and timing not in (False, "FALSE", "false", "")
    has_conflicting = bool(conflicting) and conflicting not in (False, "FALSE", "false", "")
    has_prof_abuse = bool(prof_abuse) and prof_abuse not in (False, "FALSE", "false", "")

    has_intent = bool(
        has_structuring or
        has_layering or
        has_doc_fraud or
        has_prof_abuse
    )
    has_deception = bool(
        has_conflicting or
        has_doc_fraud
    )
    has_pattern = bool(
        has_structuring or
        has_layering or
        (has_timing and has_adverse_media)
    )

    # Build indicators with corroboration status
    # Corroboration is TRUE when we have multi-event, time-based patterns
    # (structuring, layering, professional abuse, conflicting explanations = corroborated by definition)
    has_corroboration = bool(
        has_structuring or
        has_layering or
        has_prof_abuse or
        has_conflicting or
        has_adverse_media
    )
    indicators = [{"code": r, "corroborated": has_corroboration} for r in hit_rules]

    # Determine typology maturity (after has_* variables are defined)
    # CONFIRMED: Explicit pattern detection (structuring, layering)
    # ESTABLISHED: Professional abuse, conflicting explanations, or typology-related rules
    # FORMING: Multiple indicators but no pattern yet
    typology_maturity = "NONE"
    if has_structuring or has_layering:
        typology_maturity = "CONFIRMED"
    elif has_prof_abuse or has_conflicting:
        # Professional abuse and conflicting explanations indicate established typology
        typology_maturity = "ESTABLISHED"
    elif any("STRUCT" in r or "LAYER" in r for r in hit_rules):
        typology_maturity = "ESTABLISHED"
    elif len(hit_rules) >= 2:
        typology_maturity = "FORMING"

    suspicion_evidence = {
        "has_intent": has_intent,
        "has_deception": has_deception,
        "has_sustained_pattern": has_pattern,
    }

    # Evidence quality for STR gate
    has_hard_stop = (
        facts["sanctions_result"] == "MATCH" or
        facts["document_status"] == "FALSE" or
        facts["customer_response"] == "REFUSAL" or
        facts["legal_prohibition"]
    )

    evidence_quality = {
        "is_fact_based": has_hard_stop or has_intent or has_deception or has_adverse_media,
        "is_specific": has_intent or has_deception or has_pattern or has_hard_stop,
        "is_reproducible": True,
        "is_regulator_clear": True,
    }

    # Mitigation status for STR gate
    # Note: Deception (conflicting explanations) means the customer's own statements
    # contradict each other - this IS a mitigation failure regardless of history
    mitigation_status = {
        "explanation_insufficient": bool(
            has_refusal or
            has_conflicting or
            not mitigations.get("source_of_funds_verified", True)
        ),
        "docs_unsupportive": bool(
            has_doc_fraud or
            not mitigations.get("documentation_complete", True)
        ),
        "history_misaligned": bool(
            has_structuring or
            has_layering or
            has_timing or
            has_prof_abuse or
            has_conflicting  # Conflicting explanations = behavior doesn't align
        ),
    }

    return {
        "facts": facts,
        "instrument_type": instrument_type,
        "obligations": obligations,
        "indicators": indicators,
        "typology_maturity": typology_maturity,
        "mitigations": mitigation_list,
        "suspicion_evidence": suspicion_evidence,
        "evidence_quality": evidence_quality,
        "mitigation_status": mitigation_status,
        "typology_confirmed": typology_maturity == "CONFIRMED",
    }


def run_test_case(case: Dict) -> TestResult:
    """Run a single test case through the dual-gate system."""

    case_id = case["alert_details"]["external_id"]
    expected = case["expected_outcome"]

    # Convert case to gate inputs
    inputs = case_to_gate_inputs(case)

    # Run Gate 1: Zero-False-Escalation
    esc_result = run_escalation_gate(
        facts=inputs["facts"],
        instrument_type=inputs["instrument_type"],
        obligations=inputs["obligations"],
        indicators=inputs["indicators"],
        typology_maturity=inputs["typology_maturity"],
        mitigations=inputs["mitigations"],
        suspicion_evidence=inputs["suspicion_evidence"],
    )

    gate_1_actual = "PERMITTED" if esc_result.decision == EscalationDecision.PERMITTED else "PROHIBITED"

    # Run Gate 2: Positive STR
    # Pass facts so STR gate can recognize hard stops as valid legal basis
    str_result = run_str_gate(
        suspicion_evidence=inputs["suspicion_evidence"],
        evidence_quality=inputs["evidence_quality"],
        mitigation_status=inputs["mitigation_status"],
        typology_confirmed=inputs["typology_confirmed"],
        facts=inputs["facts"],
    )

    gate_2_actual = str_result.decision.value.upper()

    # Dual-gate decision
    final = dual_gate_decision(
        escalation_allowed=(esc_result.decision == EscalationDecision.PERMITTED),
        str_result=str_result,
    )

    # Map final decision to expected format
    if final["final_decision"] == "STR":
        actual_verdict = "ESCALATE"
    elif final["final_decision"] == "PASS":
        # Check if EDD was required
        if inputs["obligations"]:
            actual_verdict = "PASS_WITH_EDD"
        else:
            actual_verdict = "PASS"
    else:
        actual_verdict = "REVIEW"

    actual_str = "YES" if final["str_required"] else "NO"

    # Check if test passed
    expected_verdict = expected["expected_verdict"]
    expected_str = expected["expected_str"]

    # Verdict match (PASS and PASS_WITH_EDD are both acceptable for non-escalate cases)
    verdict_match = False
    if expected_verdict == "ESCALATE":
        verdict_match = actual_verdict == "ESCALATE"
    elif expected_verdict in ("PASS", "PASS_WITH_EDD"):
        verdict_match = actual_verdict in ("PASS", "PASS_WITH_EDD")

    str_match = actual_str == expected_str
    passed = verdict_match and str_match

    failure_reason = ""
    if not verdict_match:
        failure_reason = f"Verdict mismatch: expected {expected_verdict}, got {actual_verdict}"
    elif not str_match:
        failure_reason = f"STR mismatch: expected {expected_str}, got {actual_str}"

    return TestResult(
        case_id=case_id,
        test_family=expected["test_family"],
        description=expected["test_description"],
        expected_verdict=expected_verdict,
        actual_verdict=actual_verdict,
        expected_str=expected_str,
        actual_str=actual_str,
        gate_1_expected=expected.get("gate_1_expected", ""),
        gate_1_actual=gate_1_actual,
        gate_2_expected=expected.get("gate_2_expected", ""),
        gate_2_actual=gate_2_actual,
        passed=passed,
        failure_reason=failure_reason,
    )


def main():
    """Run all test cases and report results."""

    # Load test corpus
    corpus_path = Path(__file__).parent / "dual_gate_test_cases.json"
    with open(corpus_path, "r") as f:
        corpus = json.load(f)

    cases = corpus["cases"]
    results: List[TestResult] = []

    print("=" * 80)
    print("DECISIONGRAPH DUAL-GATE TEST CORPUS")
    print(f"Running {len(cases)} test cases...")
    print("=" * 80)
    print()

    # Run all tests
    pain_results = []
    escalate_results = []

    for case in cases:
        result = run_test_case(case)
        results.append(result)

        if result.test_family == "PAIN":
            pain_results.append(result)
        else:
            escalate_results.append(result)

    # Report PAIN cases
    print("PAIN CASES (must NOT escalate)")
    print("-" * 80)
    for r in pain_results:
        status = "PASS" if r.passed else "FAIL"
        icon = "✓" if r.passed else "✗"
        print(f"  {icon} {r.case_id}: {r.description}")
        print(f"      Expected: {r.expected_verdict}, STR={r.expected_str}")
        print(f"      Actual:   {r.actual_verdict}, STR={r.actual_str}")
        if not r.passed:
            print(f"      FAILURE: {r.failure_reason}")
        print()

    # Report ESCALATE cases
    print("ESCALATE CASES (must escalate)")
    print("-" * 80)
    for r in escalate_results:
        status = "PASS" if r.passed else "FAIL"
        icon = "✓" if r.passed else "✗"
        print(f"  {icon} {r.case_id}: {r.description}")
        print(f"      Expected: {r.expected_verdict}, STR={r.expected_str}")
        print(f"      Actual:   {r.actual_verdict}, STR={r.actual_str}")
        if not r.passed:
            print(f"      FAILURE: {r.failure_reason}")
        print()

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    pain_passed = sum(1 for r in pain_results if r.passed)
    pain_failed = len(pain_results) - pain_passed

    escalate_passed = sum(1 for r in escalate_results if r.passed)
    escalate_failed = len(escalate_results) - escalate_passed

    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"  Total:     {passed}/{total} passed")
    print(f"  PAIN:      {pain_passed}/{len(pain_results)} passed (false positive prevention)")
    print(f"  ESCALATE:  {escalate_passed}/{len(escalate_results)} passed (true positive detection)")
    print()

    if failed == 0:
        print("✓ ALL TESTS PASSED - Dual-gate system is working correctly")
        return 0
    else:
        print(f"✗ {failed} TESTS FAILED - Review failures above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
