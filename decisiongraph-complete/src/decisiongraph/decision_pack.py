"""
DecisionGraph: Decision Pack Generator

Produces structured JSON output with reproducibility metadata for audit trail.
This is the canonical output format for golden testing and regulatory compliance.

Every decision pack includes:
- engine_version: Semantic version of the decision engine
- policy_version: Semantic version of the rules pack
- input_hash: SHA-256 of canonicalized input JSON
- report_timestamp_utc: ISO 8601 timestamp

This ensures decisions are reproducible and auditable.
"""

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from .escalation_gate import EscalationGateResult, EscalationDecision
from .str_gate import STRGateResult, STRDecision


# Version constants - update these on each release
ENGINE_VERSION = "2.1.1"
POLICY_VERSION = "1.0.0"
INPUT_SCHEMA_VERSION = "1.0.0"
OUTPUT_SCHEMA_VERSION = "1.0.0"


def compute_policy_hash(engine_version: str, policy_version: str) -> str:
    """
    Compute full SHA-256 policy hash.

    decision_id = sha256(engine_version + ":" + policy_version + ":" + input_hash)

    This ensures the same input under different policy/engine versions
    yields different decision IDs.
    """
    combined = f"{engine_version}:{policy_version}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


@dataclass
class DecisionPackMeta:
    """Reproducibility metadata."""
    engine_version: str
    policy_version: str
    input_hash: str
    report_timestamp_utc: str
    case_id: str = ""
    jurisdiction: str = "CA"


@dataclass
class LayersFacts:
    """Layer 1: Hard facts."""
    hard_stop_triggered: bool
    hard_stop_reason: Optional[str]
    facts: Dict[str, Any]


@dataclass
class LayersObligations:
    """Layer 2: Regulatory obligations."""
    obligations: List[str]
    count: int
    edd_required: bool
    edd_status: str


@dataclass
class LayersIndicators:
    """Layer 3: Behavioral indicators."""
    indicators: List[Dict[str, Any]]
    corroborated_count: int
    total_count: int


@dataclass
class LayersTypologies:
    """Layer 4: ML/TF typologies."""
    typologies: List[Dict[str, Any]]
    highest_maturity: str


@dataclass
class LayersMitigations:
    """Layer 5: Mitigating factors."""
    mitigations: List[str]
    count: int
    sufficient: bool


@dataclass
class LayersSuspicion:
    """Layer 6: Suspicion determination."""
    activated: bool
    basis: str
    elements: Dict[str, bool]


@dataclass
class DecisionOutput:
    """Final decision."""
    verdict: str
    action: str
    escalation: str
    str_required: str
    path: Optional[str]
    priority: str


@dataclass
class Gate1Result:
    """Gate 1 summary."""
    decision: str
    rationale: str
    sections: Dict[str, str]


@dataclass
class Gate2Result:
    """Gate 2 summary."""
    decision: str
    rationale: str
    sections: Dict[str, str]


@dataclass
class DecisionRationale:
    """Decision rationale for audit."""
    summary: str
    str_rationale: Optional[str]
    non_escalation_justification: Optional[str]
    absolute_rules_validated: List[str]
    regulatory_citations: List[str]


@dataclass
class ComplianceDetails:
    """Regulatory compliance details."""
    jurisdiction: str
    legislation: str
    str_filing_deadline_days: Optional[int]
    lctr_required: bool
    edd_required: bool
    fintrac_indicators_matched: List[str]


def canonicalize_json(obj: Dict[str, Any]) -> str:
    """
    Canonicalize JSON for deterministic hashing.

    Rules:
    - Sort keys alphabetically
    - No whitespace
    - UTF-8 encoding
    """
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def compute_input_hash(input_data: Dict[str, Any]) -> str:
    """Compute SHA-256 hash of canonicalized input."""
    canonical = canonicalize_json(input_data)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def build_decision_pack(
    case_id: str,
    input_data: Dict[str, Any],
    facts: Dict[str, Any],
    obligations: List[str],
    indicators: List[Dict[str, Any]],
    typology_maturity: str,
    mitigations: List[str],
    suspicion_evidence: Dict[str, bool],
    esc_result: EscalationGateResult,
    str_result: STRGateResult,
    final_decision: Dict[str, Any],
    jurisdiction: str = "CA",
    fintrac_indicators: List[str] = None,
) -> Dict[str, Any]:
    """
    Build a complete decision pack with all layers and gates.

    This is the canonical JSON output for golden testing.
    """
    fintrac_indicators = fintrac_indicators or []

    # Compute reproducibility metadata
    input_hash = compute_input_hash(input_data)
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    # Determine hard stop
    hard_stop_triggered = any([
        facts.get("sanctions_result") == "MATCH",
        facts.get("document_status") == "FALSE",
        facts.get("customer_response") == "REFUSAL",
        facts.get("legal_prohibition", False),
        facts.get("adverse_media_mltf", False),
    ])

    hard_stop_reason = None
    if hard_stop_triggered:
        if facts.get("sanctions_result") == "MATCH":
            hard_stop_reason = "SANCTIONS_MATCH"
        elif facts.get("document_status") == "FALSE":
            hard_stop_reason = "FALSE_DOCUMENTS"
        elif facts.get("customer_response") == "REFUSAL":
            hard_stop_reason = "CUSTOMER_REFUSAL"
        elif facts.get("adverse_media_mltf"):
            hard_stop_reason = "ADVERSE_MEDIA_MLTF"
        elif facts.get("legal_prohibition"):
            hard_stop_reason = "LEGAL_PROHIBITION"

    # Count corroborated indicators
    corroborated_count = sum(1 for i in indicators if i.get("corroborated", False))

    # Determine EDD status
    has_pep = "PEP_FOREIGN" in obligations or "PEP_DOMESTIC" in obligations
    edd_required = has_pep
    edd_status = "SATISFIED" if edd_required else "NOT_REQUIRED"

    # Determine mitigations sufficiency
    mitigations_sufficient = len(mitigations) >= 3

    # Determine suspicion basis
    suspicion_activated = (
        hard_stop_triggered or
        suspicion_evidence.get("has_intent", False) or
        suspicion_evidence.get("has_deception", False) or
        suspicion_evidence.get("has_sustained_pattern", False)
    )

    if hard_stop_triggered:
        suspicion_basis = "HARD_STOP"
    elif suspicion_activated:
        suspicion_basis = "BEHAVIORAL"
    else:
        suspicion_basis = "NONE"

    # Determine verdict and action
    str_required = final_decision.get("str_required", False)
    escalation_permitted = esc_result.decision == EscalationDecision.PERMITTED

    if str_required:
        verdict = "STR"
        action = "FILE_STR"
        path = "PATH_1_HARD_STOP" if hard_stop_triggered else "PATH_2_SUSPICION"
    elif edd_required and not escalation_permitted:
        verdict = "PASS_WITH_EDD"
        action = "CLOSE_WITH_EDD_RECORDED"
        path = None
    elif hard_stop_triggered:
        verdict = "HARD_STOP"
        action = "BLOCK_AND_ESCALATE"
        path = "PATH_1_HARD_STOP"
    elif escalation_permitted:
        verdict = "ESCALATE"
        action = "ESCALATE_TO_ANALYST"
        path = "PATH_2_SUSPICION"
    else:
        verdict = "PASS"
        action = "CLOSE"
        path = None

    # Determine priority
    if hard_stop_triggered or str_required:
        priority = "CRITICAL"
    elif escalation_permitted:
        priority = "HIGH"
    elif edd_required:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    # Build Gate 1 sections with full details
    gate1_sections = {}
    section_names_g1 = {
        "A": ("A_fact_hard_stop", "Fact-Based Hard Stop Check"),
        "B": ("B_instrument_context", "Instrument Context Validation"),
        "C": ("C_obligation_isolation", "Obligation Isolation Check"),
        "D": ("D_indicator_corroboration", "Indicator Corroboration"),
        "E": ("E_typology_maturity", "Typology Maturity Assessment"),
        "F": ("F_mitigation_override", "Mitigation Override Check"),
        "G": ("G_suspicion_definition", "Suspicion Definition Test"),
    }
    for section in esc_result.sections:
        section_key, section_display_name = section_names_g1.get(
            section.section_id, (section.section_id, section.section_name or section.section_id)
        )
        gate1_sections[section_key] = {
            "name": section_display_name,
            "passed": section.passed,
            "reason": section.gate_message or ("Section passed" if section.passed else "Section failed"),
        }

    # Build Gate 2 sections with full details
    gate2_sections = {}
    gate2_skipped = False
    gate2_skip_reason = None

    section_names_g2 = {
        "1": ("S1_legal_suspicion", "Legal Suspicion Threshold"),
        "2": ("S2_evidence_quality", "Evidence Quality Check"),
        "3": ("S3_mitigation_failure", "Mitigation Failure Analysis"),
        "4": ("S4_typology_confirmation", "Typology Confirmation"),
        "5": ("S5_regulatory_reasonableness", "Regulatory Reasonableness"),
    }

    if str_result.decision == STRDecision.PROHIBITED and not escalation_permitted:
        # Gate 2 not evaluated - Gate 1 blocked escalation
        gate2_skipped = True
        gate2_skip_reason = "Gate 1 blocked escalation"
        for s_id, (s_key, s_name) in section_names_g2.items():
            gate2_sections[s_key] = {
                "name": s_name,
                "passed": False,
                "reason": "Not evaluated - Gate 1 blocked escalation",
            }
    else:
        for section in str_result.sections:
            section_key, section_display_name = section_names_g2.get(
                section.section_id, (section.section_id, section.section_name or section.section_id)
            )
            gate2_sections[section_key] = {
                "name": section_display_name,
                "passed": section.passed,
                "reason": section.gate_message or ("Section passed" if section.passed else "Section failed"),
            }

    # Build summary
    if str_required:
        summary = f"STR filing required. Escalation via {path}."
    elif escalation_permitted:
        summary = f"Escalation permitted via {path}. Review recommended."
    elif edd_required:
        summary = "Pass with EDD. Regulatory obligations satisfied."
    else:
        summary = "Pass. No escalation required."

    # STR rationale
    str_rationale = None
    if str_required:
        str_rationale = (
            "Based on the totality of evidence, reasonable grounds exist to suspect "
            "that the transaction(s) may be related to money laundering or terrorist "
            "financing under PCMLTFA s.7."
        )

    # Non-escalation justification
    non_escalation_justification = None
    if not escalation_permitted:
        non_escalation_justification = esc_result.non_escalation_justification

    # Absolute rules
    absolute_rules = [
        "PEP status alone can NEVER escalate",
        "Cross-border alone can NEVER escalate",
        "Risk score alone can NEVER escalate",
        "'High confidence' can NEVER override facts",
        "'Compliance comfort' is NOT a reason",
    ]

    # Regulatory citations
    citations = ["PCMLTFA s.7"]
    if str_required:
        citations.append("FINTRAC STR Guidelines")
    if edd_required:
        citations.append("PCMLTFA EDD Requirements")

    # Compute full policy hash (64 hex chars)
    policy_hash = compute_policy_hash(ENGINE_VERSION, POLICY_VERSION)

    # Compute decision_id = sha256(engine_version + policy_hash + input_hash)
    # This ensures same input under different policy versions yields different IDs
    decision_id_input = f"{ENGINE_VERSION}:{policy_hash}:{input_hash}"
    decision_id = hashlib.sha256(decision_id_input.encode('utf-8')).hexdigest()

    # Build the complete pack
    decision_pack = {
        "meta": {
            "engine_version": ENGINE_VERSION,
            "policy_version": POLICY_VERSION,
            "policy_hash": policy_hash,
            "input_schema_version": INPUT_SCHEMA_VERSION,
            "output_schema_version": OUTPUT_SCHEMA_VERSION,
            "input_hash": input_hash,
            "decision_id": decision_id,
            "report_timestamp_utc": timestamp,
            "case_id": case_id,
            "jurisdiction": jurisdiction,
        },
        "decision": {
            "verdict": verdict,
            "action": action,
            "escalation": esc_result.decision.value.upper(),
            "str_required": "YES" if str_required else "NO",
            "path": path,
            "priority": priority,
        },
        "layers": {
            "layer1_facts": {
                "hard_stop_triggered": hard_stop_triggered,
                "hard_stop_reason": hard_stop_reason,
                "facts": facts,
            },
            "layer2_obligations": {
                "obligations": obligations,
                "count": len(obligations),
                "edd_required": edd_required,
                "edd_status": edd_status,
            },
            "layer3_indicators": {
                "indicators": indicators,
                "corroborated_count": corroborated_count,
                "total_count": len(indicators),
            },
            "layer4_typologies": {
                "typologies": [{"name": "primary", "maturity": typology_maturity}],
                "highest_maturity": typology_maturity,
            },
            "layer5_mitigations": {
                "mitigations": mitigations,
                "count": len(mitigations),
                "sufficient": mitigations_sufficient,
            },
            "layer6_suspicion": {
                "activated": suspicion_activated,
                "basis": suspicion_basis,
                "elements": {
                    "has_intent": suspicion_evidence.get("has_intent", False),
                    "has_deception": suspicion_evidence.get("has_deception", False),
                    "has_sustained_pattern": suspicion_evidence.get("has_sustained_pattern", False),
                },
            },
        },
        "gates": {
            "gate1": {
                "decision": esc_result.decision.value.upper(),
                "rationale": esc_result.rationale,
                "sections": gate1_sections,
                "sections_evaluated": len([s for s in gate1_sections.values() if isinstance(s, dict)]),
                "sections_passed": len([s for s in gate1_sections.values() if isinstance(s, dict) and s.get("passed")]),
            },
            "gate2": {
                "decision": str_result.decision.value.upper(),
                "status": "SKIPPED" if gate2_skipped else "EVALUATED",
                "skip_reason": gate2_skip_reason,
                "rationale": str_result.rationale,
                "sections": gate2_sections,
                "sections_evaluated": 0 if gate2_skipped else len([s for s in gate2_sections.values() if isinstance(s, dict)]),
                "sections_passed": 0 if gate2_skipped else len([s for s in gate2_sections.values() if isinstance(s, dict) and s.get("passed")]),
            },
        },
        "evaluation_trace": {
            "rules_fired": [
                {"code": "HARD_STOP_CHECK", "result": "TRIGGERED" if hard_stop_triggered else "CLEAR", "reason": hard_stop_reason or "No hard stop conditions"},
                {"code": "PEP_ISOLATION", "result": "APPLIED" if has_pep else "NOT_APPLICABLE", "reason": "PEP status alone cannot escalate" if has_pep else "Not a PEP"},
                {"code": "SUSPICION_TEST", "result": "ACTIVATED" if suspicion_activated else "CLEAR", "reason": suspicion_basis},
            ],
            "evidence_used": [
                {"field": "facts.sanctions_result", "value": facts.get("sanctions_result", "NO_MATCH")},
                {"field": "facts.adverse_media_mltf", "value": facts.get("adverse_media_mltf", False)},
                {"field": "suspicion.has_intent", "value": suspicion_evidence.get("has_intent", False)},
                {"field": "suspicion.has_deception", "value": suspicion_evidence.get("has_deception", False)},
                {"field": "suspicion.has_sustained_pattern", "value": suspicion_evidence.get("has_sustained_pattern", False)},
                {"field": "obligations.count", "value": len(obligations)},
                {"field": "mitigations.count", "value": len(mitigations)},
                {"field": "typology.maturity", "value": typology_maturity},
            ],
            "decision_path": path or "NO_ESCALATION",
        },
        "rationale": {
            "summary": summary,
            "str_rationale": str_rationale,
            "non_escalation_justification": non_escalation_justification,
            "absolute_rules_validated": absolute_rules,
            "regulatory_citations": citations,
        },
        "compliance": {
            "jurisdiction": jurisdiction,
            "legislation": "PCMLTFA",
            "str_filing_deadline_days": 30 if str_required else None,
            "lctr_required": False,  # Determined by transaction type
            "edd_required": edd_required,
            "fintrac_indicators_matched": fintrac_indicators,
        },
    }

    return decision_pack


def normalize_for_golden(decision_pack: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize decision pack for golden testing.

    Removes non-deterministic fields:
    - report_timestamp_utc (varies per run)

    Keeps deterministic fields:
    - input_hash (based on input)
    - engine_version, policy_version (fixed per release)
    """
    normalized = json.loads(json.dumps(decision_pack))  # Deep copy

    # Remove timestamp for golden comparison
    normalized["meta"]["report_timestamp_utc"] = "NORMALIZED"

    return normalized


def format_golden_output(decision_pack: Dict[str, Any]) -> str:
    """Format decision pack as deterministic JSON for golden file."""
    normalized = normalize_for_golden(decision_pack)
    return json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=False)


__all__ = [
    'ENGINE_VERSION',
    'POLICY_VERSION',
    'compute_input_hash',
    'canonicalize_json',
    'build_decision_pack',
    'normalize_for_golden',
    'format_golden_output',
]
