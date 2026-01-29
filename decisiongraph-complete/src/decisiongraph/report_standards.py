"""
DecisionGraph Report Standards (v2.1.1)

Standardized wording, evidence templates, and instrument-specific logic
for regulator-grade report generation.

These standards ensure consistency across all generated reports and
compliance with FINTRAC / PCMLTFA requirements.
"""

from enum import Enum
from typing import Dict, List, Optional


# =============================================================================
# INSTRUMENT-SPECIFIC THRESHOLD LOGIC
# =============================================================================

class InstrumentType(str, Enum):
    """Transaction instrument types with regulatory implications."""
    CASH = "cash"
    WIRE = "wire"
    EFT = "eft"
    CHEQUE = "cheque"
    CRYPTO = "crypto"
    UNKNOWN = "unknown"


# Threshold evasion wording by instrument type
# LCTR (Large Cash Transaction Report) only applies to CASH
THRESHOLD_EVASION_WORDING = {
    InstrumentType.CASH: {
        "threshold_name": "CAD 10,000 Large Cash Transaction Report (LCTR) threshold",
        "report_type": "Large Cash Transaction Report",
        "evasion_intent": "Intent to evade statutory cash reporting requirements under PCMLTFA",
        "structuring_description": "Cash deposits structured to remain below the CAD 10,000 LCTR threshold",
    },
    InstrumentType.WIRE: {
        "threshold_name": "internal transaction monitoring thresholds",
        "report_type": "Electronic Funds Transfer Report",
        "evasion_intent": "Intent to evade internal transaction monitoring controls",
        "structuring_description": "Wire transfers structured to avoid enhanced review triggers",
    },
    InstrumentType.EFT: {
        "threshold_name": "CAD 10,000 Electronic Funds Transfer Report threshold",
        "report_type": "Electronic Funds Transfer Report",
        "evasion_intent": "Intent to evade EFT reporting requirements",
        "structuring_description": "Electronic transfers structured to remain below reporting thresholds",
    },
    InstrumentType.CRYPTO: {
        "threshold_name": "virtual currency transaction reporting thresholds",
        "report_type": "Virtual Currency Transaction Report",
        "evasion_intent": "Intent to evade virtual currency reporting requirements",
        "structuring_description": "Cryptocurrency transactions structured to avoid reporting triggers",
    },
}


def get_threshold_wording(instrument: str) -> Dict[str, str]:
    """Get instrument-appropriate threshold evasion wording."""
    try:
        inst_type = InstrumentType(instrument.lower())
    except ValueError:
        inst_type = InstrumentType.UNKNOWN

    return THRESHOLD_EVASION_WORDING.get(inst_type, {
        "threshold_name": "transaction monitoring thresholds",
        "report_type": "Suspicious Transaction Report",
        "evasion_intent": "Intent to evade transaction monitoring controls",
        "structuring_description": "Transactions structured to avoid monitoring triggers",
    })


# =============================================================================
# EVIDENCE STANDARDS
# =============================================================================

# UBO discrepancy evidence standards
UBO_DISCREPANCY_EVIDENCE = {
    "generic": "Ultimate Beneficial Ownership information contains inconsistencies",
    "detailed": "Declared UBO differs from incorporation documents or prior KYC record",
    "severe": "UBO information is materially false or deliberately misleading",
}


def get_ubo_evidence(severity: str = "detailed") -> str:
    """Get standardized UBO discrepancy evidence wording."""
    return UBO_DISCREPANCY_EVIDENCE.get(severity, UBO_DISCREPANCY_EVIDENCE["detailed"])


# =============================================================================
# SUSPICION ELEMENT STANDARDS
# =============================================================================

SUSPICION_ELEMENT_WORDING = {
    "intent": {
        "structuring": "Intent to evade statutory and internal transaction monitoring controls",
        "layering": "Intent to obscure the origin, ownership, or destination of funds",
        "concealment": "Intent to conceal or disguise the source of funds",
        "evasion": "Intent to evade regulatory reporting requirements",
    },
    "deception": {
        "ubo": "Deception through materially inconsistent beneficial ownership declarations",
        "docs": "Deception through false or fraudulent documentation",
        "explanation": "Deception through conflicting or implausible explanations",
        "identity": "Deception regarding customer identity or business purpose",
    },
    "pattern": {
        "structuring": "Sustained pattern of transactions structured below reporting thresholds",
        "velocity": "Sustained pattern of unusually high transaction velocity",
        "timing": "Sustained pattern of transactions with suspicious timing characteristics",
        "circular": "Sustained pattern of circular fund flows with no apparent business purpose",
    },
}


def get_suspicion_wording(element: str, subtype: str) -> str:
    """Get standardized suspicion element wording."""
    category = SUSPICION_ELEMENT_WORDING.get(element, {})
    return category.get(subtype, f"{element.capitalize()} evidence present")


# =============================================================================
# STR RATIONALE TEMPLATES
# =============================================================================

STR_RATIONALE_HEADER = """Based on the totality of evidence, reasonable grounds exist to suspect
that the transaction(s) may be related to money laundering or terrorist
financing. This determination is based on:"""

STR_RATIONALE_FOOTER = """This report is submitted in accordance with PCMLTFA s.7."""

NON_STR_RATIONALE = """All regulatory obligations were fulfilled. No sanctions or adverse media
were identified. Transaction activity is consistent with the customer
profile and supported by documentation. No evidence of deception, intent,
or structuring pattern was observed. Therefore, no reasonable grounds to
suspect ML/TF exist under PCMLTFA s.7."""


def build_str_rationale(
    instrument: str,
    has_structuring: bool = False,
    has_ubo_discrepancy: bool = False,
    has_new_account: bool = False,
    has_high_risk_profile: bool = False,
    transaction_details: Optional[str] = None,
    additional_factors: Optional[List[str]] = None,
) -> str:
    """Build a standardized STR rationale with proper wording."""

    lines = [STR_RATIONALE_HEADER, ""]

    point_num = 1
    wording = get_threshold_wording(instrument)

    if has_structuring:
        lines.append(f"  {point_num}. STRUCTURING PATTERN: {wording['structuring_description']}")
        if transaction_details:
            lines.append(f"     {transaction_details}")
        lines.append("")
        point_num += 1

        lines.append(f"  {point_num}. INTENT TO EVADE: {wording['evasion_intent']}.")
        lines.append("")
        point_num += 1

    if has_ubo_discrepancy:
        lines.append(f"  {point_num}. UBO DISCREPANCY: {get_ubo_evidence('detailed')}.")
        lines.append("")
        point_num += 1

    if has_new_account:
        lines.append(f"  {point_num}. NEW ACCOUNT: Customer relationship is recently established,")
        lines.append("     with no pattern of legitimate activity to establish baseline.")
        lines.append("")
        point_num += 1

    if has_high_risk_profile:
        lines.append(f"  {point_num}. HIGH-RISK PROFILE: Customer operates in a high-risk industry")
        lines.append("     with elevated inherent ML/TF risk and insufficient mitigating controls.")
        lines.append("")
        point_num += 1

    if additional_factors:
        for factor in additional_factors:
            lines.append(f"  {point_num}. {factor}")
            lines.append("")
            point_num += 1

    lines.append(STR_RATIONALE_FOOTER)

    return "\n".join(lines)


# =============================================================================
# FINTRAC INDICATOR MAPPING
# =============================================================================

FINTRAC_INDICATORS = {
    "structuring_cash": [
        "Transactions structured to avoid Large Cash Transaction Report requirements",
        "Multiple cash transactions in a single day just below CAD 10,000 threshold",
        "Pattern of cash deposits designed to circumvent reporting obligations",
    ],
    "structuring_eft": [
        "Transactions structured to avoid Electronic Funds Transfer Report requirements",
        "Multiple EFTs designed to remain below reporting thresholds",
    ],
    "structuring_internal": [
        "Transactions structured to avoid internal monitoring thresholds",
        "Pattern of transactions designed to evade enhanced review triggers",
    ],
    "new_account": [
        "New customer with limited or no transaction history",
        "Account opened recently with immediate high-value activity",
    ],
    "ubo_discrepancy": [
        "Beneficial ownership information contains discrepancies",
        "Declared UBO inconsistent with corporate records",
    ],
    "high_risk_industry": [
        "Customer operates in high-risk industry sector",
        "Business type associated with elevated ML/TF risk",
    ],
}


def get_fintrac_indicators(
    instrument: str,
    has_structuring: bool = False,
    has_new_account: bool = False,
    has_ubo_discrepancy: bool = False,
    has_high_risk_profile: bool = False,
) -> List[str]:
    """Get applicable FINTRAC indicators for a case."""

    indicators = []

    if has_structuring:
        if instrument.lower() == "cash":
            indicators.extend(FINTRAC_INDICATORS["structuring_cash"][:2])
        elif instrument.lower() in ("wire", "eft"):
            indicators.extend(FINTRAC_INDICATORS["structuring_eft"][:1])
            indicators.extend(FINTRAC_INDICATORS["structuring_internal"][:1])
        else:
            indicators.extend(FINTRAC_INDICATORS["structuring_internal"][:2])

    if has_new_account:
        indicators.extend(FINTRAC_INDICATORS["new_account"][:1])

    if has_ubo_discrepancy:
        indicators.extend(FINTRAC_INDICATORS["ubo_discrepancy"][:1])

    if has_high_risk_profile:
        indicators.extend(FINTRAC_INDICATORS["high_risk_industry"][:1])

    return indicators


__all__ = [
    'InstrumentType',
    'THRESHOLD_EVASION_WORDING',
    'get_threshold_wording',
    'UBO_DISCREPANCY_EVIDENCE',
    'get_ubo_evidence',
    'SUSPICION_ELEMENT_WORDING',
    'get_suspicion_wording',
    'STR_RATIONALE_HEADER',
    'STR_RATIONALE_FOOTER',
    'NON_STR_RATIONALE',
    'build_str_rationale',
    'FINTRAC_INDICATORS',
    'get_fintrac_indicators',
]
