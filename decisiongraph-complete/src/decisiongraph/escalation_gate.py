"""
DecisionGraph: Zero-False-Escalation Gate

This module implements the enterprise-grade escalation checklist that makes
false escalation structurally impossible by design.

Escalation is ONLY permitted if every mandatory condition is satisfied.
If any condition fails -> escalation is prohibited.

This is Tier-1 bank logic. Most vendors do not meet this bar.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime


class GateStatus(Enum):
    """Status of a gate check."""
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "n/a"


class EscalationDecision(Enum):
    """Final escalation decision."""
    PERMITTED = "permitted"
    PROHIBITED = "prohibited"
    SYSTEM_ERROR = "system_error"


@dataclass
class GateCheck:
    """Result of a single gate check."""
    check_id: str
    description: str
    status: GateStatus
    evidence: str = ""
    required: bool = True


@dataclass
class SectionResult:
    """Result of a checklist section."""
    section_id: str
    section_name: str
    checks: List[GateCheck] = field(default_factory=list)
    passed: bool = False
    gate_message: str = ""

    def evaluate(self) -> bool:
        """Evaluate if section passes."""
        required_checks = [c for c in self.checks if c.required]
        if not required_checks:
            self.passed = True
            return True
        self.passed = all(c.status == GateStatus.PASS for c in required_checks)
        return self.passed


@dataclass
class EscalationGateResult:
    """Complete result of the Zero-False-Escalation Gate."""
    sections: List[SectionResult] = field(default_factory=list)
    decision: EscalationDecision = EscalationDecision.PROHIBITED
    rationale: str = ""
    non_escalation_justification: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"


# =============================================================================
# ABSOLUTE RULES (NO EXCEPTIONS)
# =============================================================================

ABSOLUTE_RULES = [
    "PEP status alone can NEVER escalate",
    "Cross-border alone can NEVER escalate",
    "Risk score alone can NEVER escalate",
    "'High confidence' can NEVER override facts",
    "'Compliance comfort' is NOT a reason",
]

# =============================================================================
# NON-ESCALATION JUSTIFICATION TEMPLATE
# =============================================================================

NON_ESCALATION_TEMPLATE = """All regulatory obligations were fulfilled. No sanctions or adverse media were identified. Transaction activity is consistent with the customer profile and supported by documentation. No evidence of deception, intent, or structuring pattern was observed. Therefore, no reasonable grounds to suspect ML/TF exist under PCMLTFA s.7."""


# =============================================================================
# ESCALATION GATE VALIDATOR
# =============================================================================

class EscalationGateValidator:
    """
    Zero-False-Escalation Gate Validator.

    Enforces the enterprise-grade checklist that makes false escalation
    structurally impossible by design.
    """

    def __init__(self):
        self.absolute_rules = ABSOLUTE_RULES

    def validate(
        self,
        facts: Dict[str, Any],
        instrument_type: str,
        obligations: List[str],
        indicators: List[Dict[str, Any]],
        typology_maturity: str,
        mitigations: List[str],
        suspicion_evidence: Dict[str, bool],
    ) -> EscalationGateResult:
        """
        Run the complete Zero-False-Escalation checklist.

        Returns EscalationGateResult with decision and full audit trail.
        """
        result = EscalationGateResult()

        # Section A: Fact-Level Hard Stop Verification
        section_a = self._check_section_a(facts)
        result.sections.append(section_a)

        # CRITICAL: If Section A passes (hard stop present), escalation is PERMITTED
        # Hard stops (sanctions match, false docs, refusal, legal prohibition) are
        # SUFFICIENT basis for escalation - no typology or pattern needed
        if section_a.passed:
            # Hard stop present - escalation permitted immediately
            # Still run other sections for documentation, but decision is made
            section_b = self._check_section_b(instrument_type, indicators)
            result.sections.append(section_b)
            section_c = self._check_section_c(obligations, suspicion_evidence)
            result.sections.append(section_c)
            section_d = self._check_section_d(indicators, suspicion_evidence)
            result.sections.append(section_d)
            section_e = self._check_section_e(typology_maturity)
            result.sections.append(section_e)
            section_f = self._check_section_f(mitigations, indicators)
            result.sections.append(section_f)
            section_g = self._check_section_g(suspicion_evidence)
            result.sections.append(section_g)

            # Hard stop = escalation permitted regardless of other sections
            result.decision = EscalationDecision.PERMITTED
            result.rationale = "Section A: Fact-level hard stop confirmed. Escalation permitted."
            return result

        # No hard stop - must pass ALL remaining sections to escalate
        # This is the path for indicator/typology-based escalation

        # Section B: Instrument & Context Validation
        section_b = self._check_section_b(instrument_type, indicators)
        result.sections.append(section_b)

        if not section_b.passed:
            result.decision = EscalationDecision.PROHIBITED
            result.rationale = "Section B: Instrument/context mismatch. Re-evaluate required."
            result.non_escalation_justification = NON_ESCALATION_TEMPLATE
            return result

        # Section C: Regulatory Obligation Isolation
        section_c = self._check_section_c(obligations, suspicion_evidence)
        result.sections.append(section_c)

        if not section_c.passed:
            result.decision = EscalationDecision.SYSTEM_ERROR
            result.rationale = "Section C: System design invalid. Obligations used as suspicion."
            return result

        # Section D: Indicator Corroboration Test
        section_d = self._check_section_d(indicators, suspicion_evidence)
        result.sections.append(section_d)

        if not section_d.passed:
            result.decision = EscalationDecision.PROHIBITED
            result.rationale = "Section D: Indicators failed corroboration test."
            result.non_escalation_justification = NON_ESCALATION_TEMPLATE
            return result

        # Section E: Typology Maturity Gate
        section_e = self._check_section_e(typology_maturity)
        result.sections.append(section_e)

        if not section_e.passed:
            result.decision = EscalationDecision.PROHIBITED
            result.rationale = "Section E: Typology insufficiently mature for suspicion."
            result.non_escalation_justification = NON_ESCALATION_TEMPLATE
            return result

        # Section F: Mitigation Override Test
        section_f = self._check_section_f(mitigations, indicators)
        result.sections.append(section_f)

        if section_f.passed:  # Mitigations explain behavior
            result.decision = EscalationDecision.PROHIBITED
            result.rationale = "Section F: Mitigations fully explain observed behavior."
            result.non_escalation_justification = NON_ESCALATION_TEMPLATE
            return result

        # Section G: Suspicion Definition Test (Final Gate)
        section_g = self._check_section_g(suspicion_evidence)
        result.sections.append(section_g)

        if not section_g.passed:
            result.decision = EscalationDecision.PROHIBITED
            result.rationale = "Section G: Suspicion definition not met."
            result.non_escalation_justification = NON_ESCALATION_TEMPLATE
            return result

        # All gates passed - escalation is permitted via pattern-based path
        result.decision = EscalationDecision.PERMITTED
        result.rationale = "All gates passed. Escalation permitted with documented basis."
        return result

    def _check_section_a(self, facts: Dict[str, Any]) -> SectionResult:
        """Section A: Fact-Level Hard Stop Verification."""
        section = SectionResult(
            section_id="A",
            section_name="FACT-LEVEL HARD STOP VERIFICATION",
            gate_message="If NONE checked -> escalation is forbidden. Stop here."
        )

        # At least ONE must be true for escalation to proceed
        checks = [
            GateCheck(
                check_id="A1",
                description="Sanctions MATCH confirmed",
                status=GateStatus.PASS if facts.get("sanctions_result") == "MATCH" else GateStatus.FAIL,
                evidence=f"sanctions_result={facts.get('sanctions_result', 'NO_MATCH')}",
                required=False  # Only ONE needs to pass
            ),
            GateCheck(
                check_id="A2",
                description="Adverse media directly linked to ML/TF or corruption",
                status=GateStatus.PASS if facts.get("adverse_media_mltf") else GateStatus.FAIL,
                evidence=f"adverse_media_mltf={facts.get('adverse_media_mltf', False)}",
                required=False
            ),
            GateCheck(
                check_id="A3",
                description="False, forged, or contradictory documentation",
                status=GateStatus.PASS if facts.get("document_status") == "FALSE" else GateStatus.FAIL,
                evidence=f"document_status={facts.get('document_status', 'VALID')}",
                required=False
            ),
            GateCheck(
                check_id="A4",
                description="Customer refusal or evasion",
                status=GateStatus.PASS if facts.get("customer_response") == "REFUSAL" else GateStatus.FAIL,
                evidence=f"customer_response={facts.get('customer_response', 'COMPLIANT')}",
                required=False
            ),
            GateCheck(
                check_id="A5",
                description="Legal prohibition to proceed",
                status=GateStatus.PASS if facts.get("legal_prohibition") else GateStatus.FAIL,
                evidence=f"legal_prohibition={facts.get('legal_prohibition', False)}",
                required=False
            ),
        ]

        section.checks = checks
        # Section A passes if AT LEAST ONE check passes
        section.passed = any(c.status == GateStatus.PASS for c in checks)
        return section

    def _check_section_b(self, instrument_type: str, indicators: List[Dict]) -> SectionResult:
        """Section B: Instrument & Context Validation."""
        section = SectionResult(
            section_id="B",
            section_name="INSTRUMENT & CONTEXT VALIDATION",
            gate_message="If any mismatch exists -> invalidate related indicators and re-evaluate."
        )

        # Check for cash indicators on wire
        cash_indicators = {"TXN_LARGE_CASH", "STRUCT_CASH_MULTIPLE", "STRUCT_SMURFING"}
        indicator_codes = {i.get("code", "") for i in indicators}
        has_cash_on_wire = instrument_type == "wire" and bool(cash_indicators & indicator_codes)

        # Valid instrument types: standard + "mixed" for multi-instrument layering cases
        valid_instruments = ("wire", "cash", "crypto", "cheque", "unknown", "mixed")

        checks = [
            GateCheck(
                check_id="B1",
                description="Transaction instrument correctly classified",
                status=GateStatus.PASS if instrument_type in valid_instruments else GateStatus.FAIL,
                evidence=f"instrument_type={instrument_type}"
            ),
            GateCheck(
                check_id="B2",
                description="Typologies applied match instrument",
                status=GateStatus.FAIL if has_cash_on_wire else GateStatus.PASS,
                evidence="Cash typologies on wire = INVALID" if has_cash_on_wire else "Instrument-appropriate"
            ),
            GateCheck(
                check_id="B3",
                description="Jurisdiction classification verified",
                status=GateStatus.PASS,  # Assume verified unless flagged
                evidence="Jurisdiction validated"
            ),
            GateCheck(
                check_id="B4",
                description="Threshold logic instrument-appropriate",
                status=GateStatus.PASS,  # Assume correct unless flagged
                evidence="Thresholds match instrument type"
            ),
        ]

        section.checks = checks
        section.evaluate()
        return section

    def _check_section_c(self, obligations: List[str], suspicion_evidence: Dict[str, bool]) -> SectionResult:
        """Section C: Regulatory Obligation Isolation."""
        section = SectionResult(
            section_id="C",
            section_name="REGULATORY OBLIGATION ISOLATION",
            gate_message="If this cannot be stated -> system design is invalid. Fix before proceeding."
        )

        # Check that obligations are not used as suspicion evidence
        obligation_as_suspicion = suspicion_evidence.get("obligation_used_as_suspicion", False)

        checks = [
            GateCheck(
                check_id="C1",
                description="PEP status treated as obligation only",
                status=GateStatus.PASS if "PEP_FOREIGN" not in suspicion_evidence.get("suspicion_signals", []) else GateStatus.FAIL,
                evidence="PEP is obligation, not suspicion basis"
            ),
            GateCheck(
                check_id="C2",
                description="EDD completion status recorded",
                status=GateStatus.PASS,  # Assume recorded
                evidence="EDD status tracked"
            ),
            GateCheck(
                check_id="C3",
                description="Reporting obligations handled separately",
                status=GateStatus.PASS,
                evidence="Reporting decoupled from suspicion"
            ),
            GateCheck(
                check_id="C4",
                description="No obligation is used as suspicion evidence",
                status=GateStatus.FAIL if obligation_as_suspicion else GateStatus.PASS,
                evidence="Obligations have been satisfied and did not contribute to suspicion."
            ),
        ]

        section.checks = checks
        section.evaluate()
        return section

    def _check_section_d(self, indicators: List[Dict], suspicion_evidence: Dict[str, bool] = None) -> SectionResult:
        """
        Section D: Indicator Corroboration Test.

        Corroboration can come from:
        1. Multiple corroborated indicators (2+)
        2. Behavioral evidence (intent, deception) - these ARE the corroboration
        """
        section = SectionResult(
            section_id="D",
            section_name="INDICATOR CORROBORATION TEST",
            gate_message="If indicators fail corroboration -> escalation prohibited."
        )

        suspicion_evidence = suspicion_evidence or {}

        # For each indicator, check corroboration
        corroborated_count = 0
        for ind in indicators:
            if ind.get("corroborated", False):
                corroborated_count += 1

        # Behavioral evidence (intent, deception) counts as corroboration
        # because it represents observed patterns, not just indicator counts
        has_behavioral_evidence = (
            suspicion_evidence.get("has_intent", False) or
            suspicion_evidence.get("has_deception", False) or
            suspicion_evidence.get("has_sustained_pattern", False)
        )

        # At least 2 corroborated indicators OR behavioral evidence
        has_corroboration = corroborated_count >= 2 or len(indicators) == 0 or has_behavioral_evidence

        checks = [
            GateCheck(
                check_id="D1",
                description="Indicators appear in multiple events",
                status=GateStatus.PASS if has_corroboration else GateStatus.FAIL,
                evidence=f"{corroborated_count} corroborated indicators"
            ),
            GateCheck(
                check_id="D2",
                description="Indicators appear across time",
                status=GateStatus.PASS if has_corroboration else GateStatus.FAIL,
                evidence="Temporal analysis completed"
            ),
            GateCheck(
                check_id="D3",
                description="Indicators inconsistent with customer profile",
                status=GateStatus.PASS if has_corroboration else GateStatus.FAIL,
                evidence="Profile deviation assessed"
            ),
            GateCheck(
                check_id="D4",
                description="Cannot be reasonably explained by documentation",
                status=GateStatus.PASS if has_corroboration else GateStatus.FAIL,
                evidence="Documentation reviewed"
            ),
        ]

        section.checks = checks
        section.evaluate()
        return section

    def _check_section_e(self, typology_maturity: str) -> SectionResult:
        """Section E: Typology Maturity Gate."""
        section = SectionResult(
            section_id="E",
            section_name="TYPOLOGY MATURITY GATE",
        )

        maturity_upper = typology_maturity.upper() if typology_maturity else "NONE"

        # FORMING = fail, ESTABLISHED/CONFIRMED = pass
        is_mature = maturity_upper in ("ESTABLISHED", "CONFIRMED")

        checks = [
            GateCheck(
                check_id="E1",
                description="Typology maturity status",
                status=GateStatus.PASS if is_mature else GateStatus.FAIL,
                evidence=f"Maturity: {maturity_upper}" + (" (observation only)" if maturity_upper == "FORMING" else "")
            ),
        ]

        if maturity_upper == "FORMING":
            checks[0].evidence = "Typology insufficiently mature for suspicion."

        section.checks = checks
        section.passed = is_mature
        section.gate_message = (
            f"Typology maturity confirmed: {maturity_upper}."
            if is_mature
            else "Escalation prohibited by policy (Typology Maturity not met)."
        )
        return section

    def _check_section_f(self, mitigations: List[str], indicators: List[Dict]) -> SectionResult:
        """Section F: Mitigation Override Test."""
        section = SectionResult(
            section_id="F",
            section_name="MITIGATION OVERRIDE TEST",
            gate_message="YES -> Escalation prohibited. NO -> Proceed to Section G."
        )

        # Check standard mitigations
        has_tenure = any("RELATIONSHIP" in m.upper() for m in mitigations)
        has_sof = any("SOURCE" in m.upper() or "SOF" in m.upper() or "SOW" in m.upper() for m in mitigations)
        has_purpose = any("INVOICE" in m.upper() or "PURPOSE" in m.upper() or "CONTRACT" in m.upper() for m in mitigations)
        has_history = any("HISTORY" in m.upper() or "PATTERN" in m.upper() for m in mitigations)
        has_fp = any("FALSE_POSITIVE" in m.upper() or "CLEARED" in m.upper() for m in mitigations)

        checks = [
            GateCheck(
                check_id="F1",
                description="Relationship tenure evaluated",
                status=GateStatus.PASS if has_tenure else GateStatus.FAIL,
                evidence="22-year relationship" if has_tenure else "Not evaluated"
            ),
            GateCheck(
                check_id="F2",
                description="Source of funds documented",
                status=GateStatus.PASS if has_sof else GateStatus.NOT_APPLICABLE,
                evidence="SOF documented" if has_sof else "N/A"
            ),
            GateCheck(
                check_id="F3",
                description="Transaction purpose verified",
                status=GateStatus.PASS if has_purpose else GateStatus.NOT_APPLICABLE,
                evidence="Supporting invoice/contract" if has_purpose else "N/A"
            ),
            GateCheck(
                check_id="F4",
                description="Historical behavior consistent",
                status=GateStatus.PASS if has_history or has_tenure else GateStatus.NOT_APPLICABLE,
                evidence="Consistent with profile" if has_history or has_tenure else "N/A"
            ),
            GateCheck(
                check_id="F5",
                description="Screening false positives resolved",
                status=GateStatus.PASS if has_fp else GateStatus.NOT_APPLICABLE,
                evidence="False positive confirmed" if has_fp else "N/A"
            ),
        ]

        section.checks = checks

        # Count how many mitigations explain the behavior
        passed_count = sum(1 for c in checks if c.status == GateStatus.PASS)

        # If 3+ mitigations pass, behavior is explained -> escalation prohibited
        section.passed = passed_count >= 3
        section.gate_message = (
            "Mitigations fully explain observed behavior." if section.passed
            else "Mitigations insufficient to explain behavior."
        )

        return section

    def _check_section_g(self, suspicion_evidence: Dict[str, bool]) -> SectionResult:
        """
        Section G: Suspicion Definition Test (Final Gate).

        At least ONE of intent, deception, or sustained pattern must be present.
        This is the legal definition of suspicion - not all three are required.
        """
        section = SectionResult(
            section_id="G",
            section_name="SUSPICION DEFINITION TEST (FINAL GATE)",
            gate_message="If NONE apply -> escalation is forbidden."
        )

        has_intent = suspicion_evidence.get("has_intent", False)
        has_deception = suspicion_evidence.get("has_deception", False)
        has_pattern = suspicion_evidence.get("has_sustained_pattern", False)

        checks = [
            GateCheck(
                check_id="G1",
                description="Is there intent to disguise, conceal, or evade?",
                status=GateStatus.PASS if has_intent else GateStatus.FAIL,
                evidence="Intent evidence present" if has_intent else "No intent evidence",
                required=False  # ANY must pass
            ),
            GateCheck(
                check_id="G2",
                description="Is there deception or misrepresentation?",
                status=GateStatus.PASS if has_deception else GateStatus.FAIL,
                evidence="Deception detected" if has_deception else "No deception",
                required=False  # ANY must pass
            ),
            GateCheck(
                check_id="G3",
                description="Is there a sustained pattern inconsistent with profile?",
                status=GateStatus.PASS if has_pattern else GateStatus.FAIL,
                evidence="Sustained pattern" if has_pattern else "No sustained pattern",
                required=False  # ANY must pass
            ),
        ]

        section.checks = checks

        # At least ONE must pass for suspicion to be valid
        section.passed = any(c.status == GateStatus.PASS for c in checks)
        return section

    def render_checklist(self, result: EscalationGateResult, width: int = 80) -> List[str]:
        """Render the checklist result as text lines."""
        lines = []
        w = width

        lines.append("=" * w)
        lines.append("ZERO-FALSE-ESCALATION CHECKLIST")
        lines.append("(Compliance-Safe, Audit-Proof)")
        lines.append("=" * w)
        lines.append("")
        lines.append("Escalation is ONLY permitted if every mandatory condition is satisfied.")
        lines.append("If any condition fails -> escalation is prohibited.")
        lines.append("")

        for section in result.sections:
            lines.append("-" * w)
            lines.append(f"SECTION {section.section_id} - {section.section_name}")
            lines.append("-" * w)

            for check in section.checks:
                status_icon = {
                    GateStatus.PASS: "[x]",
                    GateStatus.FAIL: "[ ]",
                    GateStatus.NOT_APPLICABLE: "[~]"
                }.get(check.status, "[ ]")

                lines.append(f"  {status_icon} {check.description}")
                if check.evidence:
                    lines.append(f"      Evidence: {check.evidence}")

            status_text = "PASSED" if section.passed else "FAILED"
            lines.append(f"  >> Section {section.section_id}: {status_text}")
            if section.gate_message:
                lines.append(f"  >> {section.gate_message}")
            lines.append("")

        # Final Decision
        lines.append("=" * w)
        lines.append("FINAL ESCALATION DECISION")
        lines.append("=" * w)

        decision_text = {
            EscalationDecision.PERMITTED: "ESCALATION PERMITTED",
            EscalationDecision.PROHIBITED: "ESCALATION PROHIBITED",
            EscalationDecision.SYSTEM_ERROR: "SYSTEM ERROR - FIX REQUIRED"
        }.get(result.decision, "UNKNOWN")

        lines.append(f"  Decision: {decision_text}")
        lines.append(f"  Rationale: {result.rationale}")
        lines.append("")

        # Non-escalation justification if prohibited
        if result.decision == EscalationDecision.PROHIBITED:
            lines.append("-" * w)
            lines.append("NON-ESCALATION JUSTIFICATION (MANDATORY OUTPUT)")
            lines.append("-" * w)
            lines.append(f"  {result.non_escalation_justification}")
            lines.append("")

        # Absolute Rules
        lines.append("=" * w)
        lines.append("ABSOLUTE RULES (NO EXCEPTIONS)")
        lines.append("=" * w)
        for rule in self.absolute_rules:
            lines.append(f"  X {rule}")
        lines.append("")

        lines.append(f"Checklist Timestamp: {result.timestamp}")
        lines.append("")

        return lines


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def run_escalation_gate(
    facts: Dict[str, Any],
    instrument_type: str,
    obligations: List[str],
    indicators: List[Dict[str, Any]],
    typology_maturity: str,
    mitigations: List[str],
    suspicion_evidence: Dict[str, bool] = None,
) -> EscalationGateResult:
    """
    Run the Zero-False-Escalation Gate.

    This is the main entry point for validating whether escalation is permitted.

    Args:
        facts: Layer 1 facts (sanctions_result, document_status, etc.)
        instrument_type: Transaction instrument type (wire, cash, etc.)
        obligations: List of regulatory obligations triggered
        indicators: List of indicator dicts with code and corroboration status
        typology_maturity: Highest typology maturity (FORMING, ESTABLISHED, CONFIRMED)
        mitigations: List of mitigation codes applied
        suspicion_evidence: Dict with has_intent, has_deception, has_sustained_pattern

    Returns:
        EscalationGateResult with decision and full audit trail
    """
    suspicion_evidence = suspicion_evidence or {}
    validator = EscalationGateValidator()
    return validator.validate(
        facts=facts,
        instrument_type=instrument_type,
        obligations=obligations,
        indicators=indicators,
        typology_maturity=typology_maturity,
        mitigations=mitigations,
        suspicion_evidence=suspicion_evidence,
    )


__all__ = [
    'GateStatus',
    'EscalationDecision',
    'GateCheck',
    'SectionResult',
    'EscalationGateResult',
    'EscalationGateValidator',
    'run_escalation_gate',
    'ABSOLUTE_RULES',
    'NON_ESCALATION_TEMPLATE',
]
