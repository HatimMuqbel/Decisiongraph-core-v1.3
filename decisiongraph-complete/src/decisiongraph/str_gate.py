"""
DecisionGraph: Positive STR Checklist

This module implements the affirmative STR filing gate that proves
necessity for suspicious transaction reporting.

An STR may be considered ONLY if ALL mandatory conditions are satisfied.
If any condition fails -> STR is prohibited.

Constitutional Rule:
"Escalation is prevented by default and permitted only when suspicion
is affirmatively proven."

This checklist is intentionally SHORT. STR filing is binary and legal,
not analytical. More complexity = weaker defensibility.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime


class STRDecision(Enum):
    """Final STR filing decision."""
    REQUIRED = "required"           # STR must be filed
    PROHIBITED = "prohibited"       # STR filing not warranted
    INSUFFICIENT = "insufficient"   # Evidence insufficient for STR


@dataclass
class STRCheck:
    """Result of a single STR check."""
    check_id: str
    description: str
    satisfied: bool
    evidence: str = ""
    required: bool = True


@dataclass
class STRSectionResult:
    """Result of an STR checklist section."""
    section_id: str
    section_name: str
    checks: List[STRCheck] = field(default_factory=list)
    passed: bool = False
    gate_message: str = ""
    logic: str = "all"  # "all" = all must pass, "any" = at least one must pass


@dataclass
class STRGateResult:
    """Complete result of the Positive STR Gate."""
    sections: List[STRSectionResult] = field(default_factory=list)
    decision: STRDecision = STRDecision.PROHIBITED
    rationale: str = ""
    str_rationale_statement: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat() + "Z"


# =============================================================================
# STR RATIONALE TEMPLATE (MANDATORY OUTPUT)
# =============================================================================

STR_RATIONALE_TEMPLATE = """Based on the totality of evidence, reasonable grounds exist to suspect that the transaction(s) may be related to money laundering or terrorist financing. This determination is based on observed behavior inconsistent with the customer's known profile, insufficient mitigating explanations, and evidence suggesting concealment or deceptive conduct. This report is submitted in accordance with PCMLTFA s.7."""

NO_STR_RATIONALE_TEMPLATE = """After thorough review, no reasonable grounds exist to suspect money laundering or terrorist financing. All regulatory obligations have been fulfilled, mitigating factors adequately explain the observed activity, and no evidence of intent, deception, or sustained unexplained pattern was identified. STR filing is not warranted under PCMLTFA s.7."""


# =============================================================================
# STR GATE VALIDATOR
# =============================================================================

class STRGateValidator:
    """
    Positive STR Checklist Validator.

    Proves necessity for STR filing. An STR may be considered ONLY if
    ALL mandatory conditions are satisfied.

    This is the companion to the Zero-False-Escalation Gate:
    - Negative Gate: "Are we ALLOWED to escalate?"
    - Positive Gate: "Are we OBLIGATED to report?"
    """

    def validate(
        self,
        suspicion_evidence: Dict[str, Any],
        evidence_quality: Dict[str, bool],
        mitigation_status: Dict[str, bool],
        typology_confirmed: bool = False,
        facts: Dict[str, Any] = None,
    ) -> STRGateResult:
        """
        Run the complete Positive STR Checklist.

        Args:
            suspicion_evidence: Dict with has_intent, has_deception, has_pattern
            evidence_quality: Dict with is_fact_based, is_specific, is_reproducible, is_regulator_clear
            mitigation_status: Dict with explanation_insufficient, docs_unsupportive, history_misaligned
            typology_confirmed: Whether a confirmed ML/TF typology is present
            facts: Dict with fact-level hard stops (sanctions_result, document_status, etc.)

        Returns:
            STRGateResult with decision and full audit trail
        """
        result = STRGateResult()
        facts = facts or {}

        # Section 1: Legal Suspicion Threshold (at least ONE must be true)
        # INCLUDES hard stops - they are a legal basis independent of behavioral suspicion
        section_1 = self._check_section_1(suspicion_evidence, facts)
        result.sections.append(section_1)

        if not section_1.passed:
            result.decision = STRDecision.PROHIBITED
            result.rationale = "Section 1: No legal suspicion basis present. STR prohibited."
            result.str_rationale_statement = NO_STR_RATIONALE_TEMPLATE
            return result

        # Section 2: Evidence Quality Test (ALL must be true)
        section_2 = self._check_section_2(evidence_quality)
        result.sections.append(section_2)

        if not section_2.passed:
            result.decision = STRDecision.INSUFFICIENT
            result.rationale = "Section 2: Evidence quality insufficient for STR."
            result.str_rationale_statement = NO_STR_RATIONALE_TEMPLATE
            return result

        # Check if we have a hard stop (mitigations are irrelevant for hard stops)
        has_hard_stop = (
            facts.get("sanctions_result") == "MATCH" or
            facts.get("document_status") == "FALSE" or
            facts.get("customer_response") == "REFUSAL" or
            facts.get("legal_prohibition", False) or
            facts.get("adverse_media_mltf", False)
        )

        # Section 3: Mitigation Failure Confirmation (ALL must be true)
        # BYPASS for hard stops: legal prohibitions stand regardless of mitigations
        section_3 = self._check_section_3(mitigation_status, has_hard_stop)
        result.sections.append(section_3)

        if not section_3.passed:
            result.decision = STRDecision.PROHIBITED
            result.rationale = "Section 3: Mitigations explain behavior. STR prohibited."
            result.str_rationale_statement = NO_STR_RATIONALE_TEMPLATE
            return result

        # Section 4: Typology Confirmation (OPTIONAL - strengthens case)
        section_4 = self._check_section_4(typology_confirmed)
        result.sections.append(section_4)
        # Section 4 doesn't block - it's supporting evidence

        # Section 5: Regulatory Reasonableness Test (ALL must be YES)
        section_5 = self._check_section_5(suspicion_evidence, mitigation_status, facts)
        result.sections.append(section_5)

        if not section_5.passed:
            result.decision = STRDecision.PROHIBITED
            result.rationale = "Section 5: Regulatory reasonableness not met. STR prohibited."
            result.str_rationale_statement = NO_STR_RATIONALE_TEMPLATE
            return result

        # All mandatory sections passed - STR is warranted
        result.decision = STRDecision.REQUIRED
        result.rationale = "All mandatory sections passed. STR filing is warranted."
        result.str_rationale_statement = STR_RATIONALE_TEMPLATE

        return result

    def _check_section_1(self, suspicion_evidence: Dict[str, Any], facts: Dict[str, Any] = None) -> STRSectionResult:
        """
        Section 1: Legal Suspicion Threshold - at least ONE must be true.

        TWO VALID PATHS TO STR:
        1. HARD STOP (legal, no typology required) - sanctions match, false docs, refusal
        2. BEHAVIORAL SUSPICION (typology required) - intent, deception, sustained pattern

        Hard stops override typology requirements because they represent
        legal prohibitions, not behavioral assessments.
        """
        section = STRSectionResult(
            section_id="1",
            section_name="LEGAL SUSPICION THRESHOLD",
            gate_message="If none apply -> NO STR (stop here)",
            logic="any"
        )

        facts = facts or {}

        # Check for hard stops (legal basis independent of behavioral suspicion)
        has_sanctions_match = facts.get("sanctions_result") == "MATCH"
        has_false_docs = facts.get("document_status") == "FALSE"
        has_refusal = facts.get("customer_response") == "REFUSAL"
        has_legal_prohibition = facts.get("legal_prohibition", False)
        has_adverse_media_mltf = facts.get("adverse_media_mltf", False)

        has_hard_stop = has_sanctions_match or has_false_docs or has_refusal or has_legal_prohibition or has_adverse_media_mltf

        # Build hard stop evidence string
        hard_stop_reasons = []
        if has_sanctions_match:
            hard_stop_reasons.append("confirmed sanctions match")
        if has_false_docs:
            hard_stop_reasons.append("false/fraudulent documents")
        if has_refusal:
            hard_stop_reasons.append("customer refusal to provide information")
        if has_legal_prohibition:
            hard_stop_reasons.append("regulator instruction/legal prohibition")
        if has_adverse_media_mltf:
            hard_stop_reasons.append("adverse media directly linked to ML/TF")
        hard_stop_evidence = ", ".join(hard_stop_reasons) if hard_stop_reasons else "No hard stop"

        # Check for behavioral suspicion
        has_intent = suspicion_evidence.get("has_intent", False)
        has_deception = suspicion_evidence.get("has_deception", False)
        has_pattern = suspicion_evidence.get("has_sustained_pattern", False)

        checks = [
            STRCheck(
                check_id="1.0",
                description="Fact-level hard stop present (sanctions match, false docs, refusal, legal prohibition)",
                satisfied=has_hard_stop,
                evidence=f"Hard stop: {hard_stop_evidence}" if has_hard_stop else "No hard stop",
                required=False  # ANY must pass
            ),
            STRCheck(
                check_id="1.1",
                description="Intent to conceal or disguise source, ownership, or movement of funds",
                satisfied=has_intent,
                evidence="Intent evidence present" if has_intent else "No intent evidence",
                required=False  # ANY must pass
            ),
            STRCheck(
                check_id="1.2",
                description="Deception or misrepresentation by the customer",
                satisfied=has_deception,
                evidence="Deception detected" if has_deception else "No deception evidence",
                required=False
            ),
            STRCheck(
                check_id="1.3",
                description="Sustained unexplained pattern inconsistent with known profile",
                satisfied=has_pattern,
                evidence="Sustained pattern present" if has_pattern else "No sustained pattern",
                required=False
            ),
        ]

        section.checks = checks
        # At least ONE must be satisfied
        section.passed = any(c.satisfied for c in checks)
        return section

    def _check_section_2(self, evidence_quality: Dict[str, bool]) -> STRSectionResult:
        """Section 2: Evidence Quality Test - ALL must be true."""
        section = STRSectionResult(
            section_id="2",
            section_name="EVIDENCE QUALITY TEST",
            gate_message="If any fail -> NO STR",
            logic="all"
        )

        checks = [
            STRCheck(
                check_id="2.1",
                description="Evidence is fact-based, not score-based",
                satisfied=evidence_quality.get("is_fact_based", False),
                evidence="Fact-based evidence" if evidence_quality.get("is_fact_based") else "Score-based only"
            ),
            STRCheck(
                check_id="2.2",
                description="Evidence is specific, not generic (not 'PEP', not 'high-risk country')",
                satisfied=evidence_quality.get("is_specific", False),
                evidence="Specific evidence" if evidence_quality.get("is_specific") else "Generic indicators only"
            ),
            STRCheck(
                check_id="2.3",
                description="Evidence is reproducible and documented",
                satisfied=evidence_quality.get("is_reproducible", False),
                evidence="Documented and reproducible" if evidence_quality.get("is_reproducible") else "Not reproducible"
            ),
            STRCheck(
                check_id="2.4",
                description="Evidence would be understandable by a third-party regulator",
                satisfied=evidence_quality.get("is_regulator_clear", False),
                evidence="Regulator-clear" if evidence_quality.get("is_regulator_clear") else "Unclear to regulator"
            ),
        ]

        section.checks = checks
        section.passed = all(c.satisfied for c in checks)
        return section

    def _check_section_3(self, mitigation_status: Dict[str, bool], hard_stop_bypass: bool = False) -> STRSectionResult:
        """
        Section 3: Mitigation Failure Confirmation - ALL must be true.

        EXCEPTION: When a hard stop is present, mitigations are IRRELEVANT.
        Legal prohibitions (sanctions, fraud, refusal) stand regardless of explanations.
        """
        section = STRSectionResult(
            section_id="3",
            section_name="MITIGATION FAILURE CONFIRMATION",
            gate_message="If this cannot be stated honestly -> NO STR",
            logic="all"
        )

        # Hard stop bypass: legal prohibitions override mitigations
        if hard_stop_bypass:
            checks = [
                STRCheck(
                    check_id="3.0",
                    description="Hard stop present - mitigations are irrelevant for legal prohibitions",
                    satisfied=True,
                    evidence="Hard stop bypasses mitigation review"
                ),
            ]
            section.checks = checks
            section.passed = True
            section.gate_message = "Hard stop present. Mitigations do not apply to legal prohibitions."
            return section

        checks = [
            STRCheck(
                check_id="3.1",
                description="Customer explanation does not reasonably account for behavior",
                satisfied=mitigation_status.get("explanation_insufficient", False),
                evidence="Explanation insufficient" if mitigation_status.get("explanation_insufficient") else "Explanation accepted"
            ),
            STRCheck(
                check_id="3.2",
                description="Documentation does not support transaction purpose",
                satisfied=mitigation_status.get("docs_unsupportive", False),
                evidence="Docs unsupportive" if mitigation_status.get("docs_unsupportive") else "Docs support purpose"
            ),
            STRCheck(
                check_id="3.3",
                description="Historical behavior does not align with activity",
                satisfied=mitigation_status.get("history_misaligned", False),
                evidence="History misaligned" if mitigation_status.get("history_misaligned") else "History aligns"
            ),
        ]

        section.checks = checks
        section.passed = all(c.satisfied for c in checks)

        if section.passed:
            section.gate_message = "Mitigating factors were considered and found insufficient to explain the suspicious activity."
        else:
            section.gate_message = "Mitigations explain the observed behavior. STR not warranted."

        return section

    def _check_section_4(self, typology_confirmed: bool) -> STRSectionResult:
        """Section 4: Typology Confirmation - OPTIONAL but strengthens case."""
        section = STRSectionResult(
            section_id="4",
            section_name="TYPOLOGY CONFIRMATION (OPTIONAL)",
            gate_message="Typology is supporting, not required. STRs may exist without a named typology.",
            logic="any"
        )

        checks = [
            STRCheck(
                check_id="4.1",
                description="Confirmed ML/TF typology present (structuring, corruption, trade-based ML, etc.)",
                satisfied=typology_confirmed,
                evidence="Typology confirmed" if typology_confirmed else "No confirmed typology",
                required=False  # Optional
            ),
        ]

        section.checks = checks
        section.passed = True  # Section 4 always "passes" - it's optional
        return section

    def _check_section_5(self, suspicion_evidence: Dict[str, Any], mitigation_status: Dict[str, bool], facts: Dict[str, Any] = None) -> STRSectionResult:
        """
        Section 5: Regulatory Reasonableness Test - ALL must be YES.

        EXCEPTION: Hard stops automatically satisfy regulatory reasonableness.
        A regulator would absolutely expect an STR for sanctions matches, fraud, etc.
        """
        section = STRSectionResult(
            section_id="5",
            section_name="REGULATORY REASONABLENESS TEST (FINAL)",
            gate_message="If any answer = NO -> NO STR",
            logic="all"
        )

        facts = facts or {}

        # Check for hard stops (including adverse media linked to ML/TF)
        has_hard_stop = (
            facts.get("sanctions_result") == "MATCH" or
            facts.get("document_status") == "FALSE" or
            facts.get("customer_response") == "REFUSAL" or
            facts.get("legal_prohibition", False) or
            facts.get("adverse_media_mltf", False)
        )

        # Hard stops automatically satisfy regulatory reasonableness
        if has_hard_stop:
            checks = [
                STRCheck(
                    check_id="5.0",
                    description="Hard stop present - regulatory reporting is mandatory",
                    satisfied=True,
                    evidence="Hard stop mandates regulatory reporting"
                ),
                STRCheck(
                    check_id="5.1",
                    description="Would a regulator expect an STR if this were reviewed later?",
                    satisfied=True,
                    evidence="Yes - hard stop mandates STR"
                ),
                STRCheck(
                    check_id="5.2",
                    description="Would NOT filing create defensibility risk?",
                    satisfied=True,
                    evidence="Yes - failure to report hard stop is indefensible"
                ),
                STRCheck(
                    check_id="5.3",
                    description="Is the STR about suspicion, not compliance anxiety?",
                    satisfied=True,
                    evidence="Yes - legal prohibition, not anxiety"
                ),
            ]
            section.checks = checks
            section.passed = True
            section.gate_message = "Hard stop mandates regulatory reporting."
            return section

        # These are derived from the overall case assessment
        has_basis = any([
            suspicion_evidence.get("has_intent", False),
            suspicion_evidence.get("has_deception", False),
            suspicion_evidence.get("has_sustained_pattern", False)
        ])

        mitigations_failed = all([
            mitigation_status.get("explanation_insufficient", False),
            mitigation_status.get("docs_unsupportive", False),
            mitigation_status.get("history_misaligned", False)
        ])

        # Would regulator expect STR if reviewed later?
        regulator_would_expect = has_basis and mitigations_failed

        # Would NOT filing create defensibility risk?
        defensibility_risk = has_basis and mitigations_failed

        # Is STR about suspicion, not compliance anxiety?
        about_suspicion = has_basis and not suspicion_evidence.get("compliance_anxiety_only", False)

        checks = [
            STRCheck(
                check_id="5.1",
                description="Would a regulator expect an STR if this were reviewed later?",
                satisfied=regulator_would_expect,
                evidence="Regulator would expect STR" if regulator_would_expect else "Regulator would not expect STR"
            ),
            STRCheck(
                check_id="5.2",
                description="Would NOT filing create defensibility risk?",
                satisfied=defensibility_risk,
                evidence="Defensibility risk exists" if defensibility_risk else "No defensibility risk"
            ),
            STRCheck(
                check_id="5.3",
                description="Is the STR about suspicion, not compliance anxiety?",
                satisfied=about_suspicion,
                evidence="About genuine suspicion" if about_suspicion else "Compliance anxiety only"
            ),
        ]

        section.checks = checks
        section.passed = all(c.satisfied for c in checks)
        return section

    def render_checklist(self, result: STRGateResult, width: int = 80) -> List[str]:
        """Render the STR checklist result as text lines."""
        lines = []
        w = width

        lines.append("=" * w)
        lines.append("POSITIVE STR CHECKLIST")
        lines.append("(Escalate Only If This Is True)")
        lines.append("=" * w)
        lines.append("")
        lines.append("An STR may be considered ONLY if ALL mandatory conditions are satisfied.")
        lines.append("If any condition fails -> STR is prohibited.")
        lines.append("")
        lines.append("This checklist is intentionally SHORT.")
        lines.append("STR filing is binary and legal, not analytical.")
        lines.append("")

        for section in result.sections:
            lines.append("-" * w)
            lines.append(f"SECTION {section.section_id} - {section.section_name}")
            lines.append("-" * w)

            logic_note = "(at least ONE must be YES)" if section.logic == "any" else "(ALL must be YES)"
            lines.append(f"  {logic_note}")
            lines.append("")

            for check in section.checks:
                icon = "[x]" if check.satisfied else "[ ]"
                lines.append(f"  {icon} {check.description}")
                if check.evidence:
                    lines.append(f"      Evidence: {check.evidence}")

            status_text = "PASSED" if section.passed else "FAILED"
            lines.append(f"  >> Section {section.section_id}: {status_text}")
            if section.gate_message:
                lines.append(f"  >> {section.gate_message}")
            lines.append("")

        # Final Decision
        lines.append("=" * w)
        lines.append("STR GATE DECISION")
        lines.append("=" * w)

        decision_text = {
            STRDecision.REQUIRED: "STR FILING REQUIRED",
            STRDecision.PROHIBITED: "STR FILING PROHIBITED",
            STRDecision.INSUFFICIENT: "EVIDENCE INSUFFICIENT FOR STR"
        }.get(result.decision, "UNKNOWN")

        lines.append(f"  Decision: {decision_text}")
        lines.append(f"  Rationale: {result.rationale}")
        lines.append("")

        # Required output statement
        lines.append("-" * w)
        if result.decision == STRDecision.REQUIRED:
            lines.append("STR RATIONALE STATEMENT (MANDATORY OUTPUT)")
        else:
            lines.append("NON-STR RATIONALE STATEMENT")
        lines.append("-" * w)
        lines.append(f"  {result.str_rationale_statement}")
        lines.append("")

        return lines


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def run_str_gate(
    suspicion_evidence: Dict[str, Any],
    evidence_quality: Dict[str, bool] = None,
    mitigation_status: Dict[str, bool] = None,
    typology_confirmed: bool = False,
    facts: Dict[str, Any] = None,
) -> STRGateResult:
    """
    Run the Positive STR Gate.

    This is the companion to run_escalation_gate:
    - Negative Gate (escalation_gate): "Are we ALLOWED to escalate?"
    - Positive Gate (str_gate): "Are we OBLIGATED to report?"

    TWO VALID PATHS TO STR:
    1. HARD STOP (legal, no typology required) - sanctions match, false docs, refusal
    2. BEHAVIORAL SUSPICION (typology required) - intent, deception, sustained pattern

    Args:
        suspicion_evidence: Dict with has_intent, has_deception, has_sustained_pattern
        evidence_quality: Dict with is_fact_based, is_specific, is_reproducible, is_regulator_clear
        mitigation_status: Dict with explanation_insufficient, docs_unsupportive, history_misaligned
        typology_confirmed: Whether a confirmed ML/TF typology is present
        facts: Dict with fact-level hard stops (sanctions_result, document_status, etc.)

    Returns:
        STRGateResult with decision and full audit trail
    """
    evidence_quality = evidence_quality or {
        "is_fact_based": False,
        "is_specific": False,
        "is_reproducible": False,
        "is_regulator_clear": False,
    }
    mitigation_status = mitigation_status or {
        "explanation_insufficient": False,
        "docs_unsupportive": False,
        "history_misaligned": False,
    }
    facts = facts or {}

    validator = STRGateValidator()
    return validator.validate(
        suspicion_evidence=suspicion_evidence,
        evidence_quality=evidence_quality,
        mitigation_status=mitigation_status,
        typology_confirmed=typology_confirmed,
        facts=facts,
    )


# =============================================================================
# DUAL-GATE DECISION FLOW
# =============================================================================

def dual_gate_decision(
    escalation_allowed: bool,
    str_result: STRGateResult,
) -> Dict[str, Any]:
    """
    Combine both gates into final decision.

    Constitutional Rule:
    "Escalation is prevented by default and permitted only when
    suspicion is affirmatively proven."

    Args:
        escalation_allowed: Result from Zero-False-Escalation Gate
        str_result: Result from Positive STR Gate

    Returns:
        Dict with final_decision, rationale, and action
    """
    if not escalation_allowed:
        return {
            "final_decision": "PASS",
            "rationale": "Escalation prohibited by Zero-False-Escalation Gate",
            "action": "CLOSE_WITH_EDD_RECORDED",
            "str_required": False,
        }

    if str_result.decision == STRDecision.REQUIRED:
        return {
            "final_decision": "STR",
            "rationale": "Escalation permitted AND STR criteria met",
            "action": "FILE_STR",
            "str_required": True,
        }

    if str_result.decision == STRDecision.PROHIBITED:
        return {
            "final_decision": "PASS",
            "rationale": "Escalation permitted but STR criteria not met",
            "action": "CLOSE_WITH_ENHANCED_MONITORING",
            "str_required": False,
        }

    # INSUFFICIENT
    return {
        "final_decision": "REVIEW",
        "rationale": "Evidence insufficient - requires analyst review",
        "action": "ANALYST_REVIEW_REQUIRED",
        "str_required": False,
    }


__all__ = [
    'STRDecision',
    'STRCheck',
    'STRSectionResult',
    'STRGateResult',
    'STRGateValidator',
    'run_str_gate',
    'dual_gate_decision',
    'STR_RATIONALE_TEMPLATE',
    'NO_STR_RATIONALE_TEMPLATE',
]
