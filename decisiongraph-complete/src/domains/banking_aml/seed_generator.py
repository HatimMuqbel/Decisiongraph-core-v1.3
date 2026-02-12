"""
DecisionGraph Banking/AML Seed Generator v2

Generates 1,500 seed precedents using ALL 28 fields from the banking field
registry.  Every seed uses three-field banking outcomes (disposition /
disposition_basis / reporting) -- no insurance vocabulary.

Design:
- 26 scenarios with base_facts that define the pattern
- Each scenario has a weight that determines how many seeds to generate
- Remaining fields are filled with realistic random values
- ~10 % noise: minority-outcome variants per scenario

All seeds use canonical field names from banking_field_registry.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import uuid4

from .field_registry import (
    BANKING_FIELDS,
    validate_field_value,
)
from kernel.foundation.judgment import JudgmentPayload, AnchorFact
from .policy_shifts import (
    POLICY_SHIFTS,
    SHIFT_EFFECTIVE_DATES,
    _case_facts_to_seed_like,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEED_SALT = "decisiongraph-banking-seed-v2"
POLICY_VERSION = "2026.01.01"
POLICY_PACK_ID = "CA-FINTRAC-AML"
POLICY_PACK_HASH = hashlib.sha256(b"CA-FINTRAC-AML-v2026.01.01").hexdigest()
TOTAL_SEEDS = 1500
FINGERPRINT_SCHEMA = "decisiongraph:aml:txn_monitoring:v2"

# Must match apply_aml_banding / create_txn_amount_banding() band names
AMOUNT_BANDS = ["under_3k", "3k_10k", "10k_25k", "25k_100k", "100k_500k", "500k_1m", "over_1m"]
CHANNELS = ["wire_domestic", "wire_international", "cash", "cheque", "eft", "crypto"]

# Reason code prefixes by scenario type
_SCENARIO_REASON_CODES: dict[str, list[str]] = {
    "clean_known_customer":     ["RC-TXN-NORMAL", "RC-TXN-PROFILE-MATCH"],
    "new_customer_large_clear": ["RC-TXN-NORMAL", "RC-RPT-LCTR"],
    "structuring_suspected":    ["RC-TXN-STRUCT", "RC-TXN-STRUCT-MULTI"],
    "round_amount_reporting":   ["RC-TXN-STRUCT", "RC-TXN-UNUSUAL"],
    "source_of_funds_unclear":  ["RC-TXN-UNUSUAL", "RC-TXN-DEVIATION"],
    "stated_purpose_unclear":   ["RC-TXN-UNUSUAL", "RC-TXN-DEVIATION"],
    "adverse_media":            ["RC-KYC-ADVERSE-MINOR", "RC-KYC-ADVERSE-MAJOR"],
    "rapid_movement":           ["RC-TXN-RAPID", "RC-TXN-LAYER"],
    "profile_deviation":        ["RC-TXN-UNUSUAL", "RC-TXN-DEVIATION"],
    "third_party":              ["RC-TXN-UNUSUAL"],
    "layering_shell":           ["RC-TXN-LAYER", "RC-TXN-RAPID"],
    "high_risk_country":        ["RC-TXN-FATF-GREY"],
    "cash_intensive_large":     ["RC-TXN-UNUSUAL", "RC-RPT-LCTR"],
    "pep_large_amount":         ["RC-TXN-PEP", "RC-TXN-PEP-EDD", "RC-KYC-PEP-APPROVED"],
    "pep_screening_match":      ["RC-TXN-PEP", "RC-TXN-PEP-EDD", "RC-KYC-PEP-APPROVED"],
    "sanctions_match":          ["RC-SCR-SANCTION", "RC-SCR-OFAC"],
    "one_prior_sar":            ["RC-TXN-NORMAL", "RC-MON-ALERT"],
    "multiple_prior_sars":      ["RC-MON-ALERT", "RC-MON-VELOCITY"],
    "heavy_sar_history":        ["RC-MON-VELOCITY", "RC-MON-ALERT"],
    "previous_closure":         ["RC-MON-ALERT", "RC-MON-UNUSUAL"],
    "pep_adverse_media_block":  ["RC-TXN-PEP", "RC-KYC-ADVERSE-MAJOR", "RC-KYC-PEP-APPROVED"],
    "layering_high_value_block": ["RC-TXN-LAYER", "RC-TXN-RAPID", "RC-TXN-UNUSUAL"],
    "shell_entity_cleared":     ["RC-TXN-LAYER", "RC-TXN-UNUSUAL", "RC-TXN-NORMAL"],
    "crypto_corridor_cleared":  ["RC-TXN-FATF-GREY", "RC-TXN-UNUSUAL", "RC-TXN-NORMAL"],
    "velocity_spike_cleared":   ["RC-TXN-RAPID", "RC-TXN-UNUSUAL", "RC-TXN-NORMAL"],
    "structuring_cleared":      ["RC-TXN-STRUCT", "RC-TXN-UNUSUAL", "RC-TXN-NORMAL"],
}


# ---------------------------------------------------------------------------
# Schema selection (mirrors service/main.py _select_schema_id_for_codes)
# ---------------------------------------------------------------------------

def _schema_for_codes(codes: list[str]) -> str:
    """Pick fingerprint schema from reason code prefixes."""
    prefixes = {c.split("-")[1].upper() for c in codes if c.startswith("RC-") and "-" in c}
    if "RPT" in prefixes:
        return "decisiongraph:aml:report:v1"
    if "SCR" in prefixes:
        return "decisiongraph:aml:screening:v1"
    if "KYC" in prefixes:
        return "decisiongraph:aml:kyc:v1"
    if "MON" in prefixes:
        return "decisiongraph:aml:monitoring:v1"
    return "decisiongraph:aml:txn:v1"


# ---------------------------------------------------------------------------
# 28 scenarios  (26 original + 2 trade finance)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Clean defaults — every scenario starts from this base; scenario-specific
# overrides are applied on top.  This ensures ALL 27 fields are populated
# with coherent values rather than random noise, which is critical for v3
# field-by-field similarity scoring.  Includes 3 trade finance fields.
# ---------------------------------------------------------------------------

# Boolean / flag defaults only.  The 6 high-variation enum fields
# (customer.type, customer.relationship_length, txn.type, txn.amount_band,
# txn.destination_country_risk, txn.stated_purpose) are intentionally omitted
# so _random_realistic_value() fills them with weighted distributions, giving
# natural variety across seeds (gate coverage for corporate / retail, different
# channels, amount bands, etc.).
_CLEAN_PROFILE: dict[str, Any] = {
    "customer.pep": False,
    "customer.high_risk_jurisdiction": False,
    "customer.high_risk_industry": False,
    "customer.cash_intensive": False,
    "txn.cross_border": False,
    "txn.round_amount": False,
    "txn.just_below_threshold": False,
    "txn.multiple_same_day": False,
    "txn.pattern_matches_profile": True,
    "txn.source_of_funds_clear": True,
    "flag.structuring": False,
    "flag.rapid_movement": False,
    "flag.layering": False,
    "flag.unusual_for_profile": False,
    "flag.third_party": False,
    "flag.shell_company": False,
    "screening.sanctions_match": False,
    "screening.pep_match": False,
    "screening.adverse_media_level": "none",
    "screening.adverse_media": False,
    "prior.sars_filed": 0,
    "prior.account_closures": False,
    "trade.goods_description": "detailed",
    "trade.pricing_consistent": True,
    "trade.is_letter_of_credit": False,
}


SCENARIOS = [
    # ── APPROVE ──
    {
        "name": "clean_known_customer",
        "description": "Known customer, normal pattern, under $10K",
        "base_facts": {
            **_CLEAN_PROFILE,
        },
        "outcome": {"disposition": "ALLOW", "disposition_basis": "DISCRETIONARY", "reporting": "NO_REPORT"},
        "decision_level": "analyst",
        "weight": 0.17,
        "decision_drivers": ["txn.pattern_matches_profile", "txn.source_of_funds_clear"],
        "driver_typology": "",
    },
    {
        "name": "new_customer_large_clear",
        "description": "New customer, >$10K, source clear, LCTR required",
        "base_facts": {
            **_CLEAN_PROFILE,
            "customer.relationship_length": "new",
            "txn.amount_band": "10k_25k",
        },
        "outcome": {"disposition": "ALLOW", "disposition_basis": "DISCRETIONARY", "reporting": "FILE_LCTR"},
        "decision_level": "analyst",
        "weight": 0.06,
        "decision_drivers": ["txn.amount_band", "txn.source_of_funds_clear"],
        "driver_typology": "",
    },

    # ── INVESTIGATE (EDD) ──
    {
        "name": "structuring_suspected",
        "description": "Just below $10K, multiple same day",
        "base_facts": {
            **_CLEAN_PROFILE,
            "txn.amount_band": "3k_10k",
            "txn.just_below_threshold": True,
            "txn.multiple_same_day": True,
            "flag.structuring": True,
            "txn.round_amount": True,
            "txn.pattern_matches_profile": False,
            "txn.source_of_funds_clear": False,
        },
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "analyst",
        "weight": 0.06,
        "decision_drivers": ["flag.structuring", "txn.just_below_threshold", "txn.multiple_same_day"],
        "driver_typology": "structuring",
    },
    {
        "name": "round_amount_reporting",
        "description": "Round amount in reporting range",
        "base_facts": {
            **_CLEAN_PROFILE,
            "txn.amount_band": "10k_25k",
            "txn.round_amount": True,
            "txn.pattern_matches_profile": False,
        },
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "analyst",
        "weight": 0.03,
        "decision_drivers": ["txn.round_amount", "txn.amount_band", "txn.pattern_matches_profile"],
        "driver_typology": "structuring",
    },
    {
        "name": "source_of_funds_unclear",
        "description": "Source of funds unclear",
        "base_facts": {
            **_CLEAN_PROFILE,
            "txn.source_of_funds_clear": False,
            "txn.stated_purpose": "unclear",
            "txn.pattern_matches_profile": False,
        },
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "analyst",
        "weight": 0.04,
        "decision_drivers": ["txn.source_of_funds_clear", "txn.stated_purpose"],
        "driver_typology": "",
    },
    {
        "name": "stated_purpose_unclear",
        "description": "Stated purpose unclear",
        "base_facts": {
            **_CLEAN_PROFILE,
            "txn.stated_purpose": "unclear",
            "txn.pattern_matches_profile": False,
        },
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "analyst",
        "weight": 0.04,
        "decision_drivers": ["txn.stated_purpose", "txn.pattern_matches_profile"],
        "driver_typology": "",
    },
    {
        "name": "adverse_media",
        "description": "Adverse media match",
        "base_facts": {
            **_CLEAN_PROFILE,
            "screening.adverse_media_level": "confirmed",
            "screening.adverse_media": True,
            "txn.pattern_matches_profile": False,
        },
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "analyst",
        "weight": 0.04,
        "decision_drivers": ["screening.adverse_media_level"],
        "driver_typology": "adverse_media",
    },
    {
        "name": "rapid_movement",
        "description": "Rapid in/out movement",
        "base_facts": {
            **_CLEAN_PROFILE,
            "flag.rapid_movement": True,
            "txn.pattern_matches_profile": False,
            "flag.unusual_for_profile": True,
        },
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "analyst",
        "weight": 0.04,
        "decision_drivers": ["flag.rapid_movement", "flag.unusual_for_profile"],
        "driver_typology": "",
    },
    {
        "name": "profile_deviation",
        "description": "Activity unusual for customer profile",
        "base_facts": {
            **_CLEAN_PROFILE,
            "flag.unusual_for_profile": True,
            "txn.pattern_matches_profile": False,
            "txn.amount_band": "100k_500k",
        },
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "analyst",
        "weight": 0.04,
        "decision_drivers": ["flag.unusual_for_profile", "txn.pattern_matches_profile"],
        "driver_typology": "",
    },
    {
        "name": "third_party",
        "description": "Third-party payment",
        "base_facts": {
            **_CLEAN_PROFILE,
            "flag.third_party": True,
            "txn.pattern_matches_profile": False,
        },
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "analyst",
        "weight": 0.03,
        "decision_drivers": ["flag.third_party"],
        "driver_typology": "",
    },
    {
        "name": "layering_shell",
        "description": "Layering / shell company indicators",
        "base_facts": {
            **_CLEAN_PROFILE,
            "customer.type": "corporation",
            "flag.layering": True,
            "flag.shell_company": True,
            "txn.cross_border": True,
            "txn.destination_country_risk": "medium",
            "txn.pattern_matches_profile": False,
            "txn.source_of_funds_clear": False,
        },
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "analyst",
        "weight": 0.04,
        "decision_drivers": ["flag.layering", "flag.shell_company", "txn.cross_border"],
        "driver_typology": "",
    },

    # ── ESCALATE (to senior/compliance) ──
    {
        "name": "high_risk_country",
        "description": "High-risk country destination",
        "base_facts": {
            **_CLEAN_PROFILE,
            "txn.cross_border": True,
            "txn.destination_country_risk": "high",
            "customer.high_risk_jurisdiction": True,
            "txn.amount_band": "25k_100k",
        },
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "senior_analyst",
        "weight": 0.04,
        "decision_drivers": ["txn.destination_country_risk", "customer.high_risk_jurisdiction", "txn.cross_border"],
        "driver_typology": "",
    },
    {
        "name": "cash_intensive_large",
        "description": "Cash-intensive business, large amount",
        "base_facts": {
            **_CLEAN_PROFILE,
            "customer.type": "corporation",
            "customer.cash_intensive": True,
            "txn.amount_band": "25k_100k",
            "txn.type": "cash",
        },
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "senior_analyst",
        "weight": 0.04,
        "decision_drivers": ["customer.cash_intensive", "txn.amount_band", "txn.type"],
        "driver_typology": "",
    },
    {
        "name": "pep_large_amount",
        "description": "PEP, large amount",
        "base_facts": {
            **_CLEAN_PROFILE,
            "customer.pep": True,
            "screening.pep_match": True,
            "txn.amount_band": "25k_100k",
            "txn.cross_border": True,
            "txn.destination_country_risk": "medium",
        },
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "senior_analyst",
        "weight": 0.04,
        "decision_drivers": ["customer.pep", "screening.pep_match", "txn.amount_band"],
        "driver_typology": "",
    },
    {
        "name": "pep_screening_match",
        "description": "PEP screening match",
        "base_facts": {
            **_CLEAN_PROFILE,
            "screening.pep_match": True,
            "customer.pep": True,
        },
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "senior_analyst",
        "weight": 0.03,
        "decision_drivers": ["screening.pep_match", "customer.pep"],
        "driver_typology": "",
    },

    # ── BLOCK ──
    {
        "name": "sanctions_match",
        "description": "Sanctions match - mandatory block",
        "base_facts": {
            **_CLEAN_PROFILE,
            "screening.sanctions_match": True,
            "txn.cross_border": True,
            "txn.destination_country_risk": "high",
            "customer.high_risk_jurisdiction": True,
        },
        "outcome": {"disposition": "BLOCK", "disposition_basis": "MANDATORY", "reporting": "FILE_STR"},
        "decision_level": "manager",
        "weight": 0.03,
        "decision_drivers": ["screening.sanctions_match"],
        "driver_typology": "sanctions",
    },

    # ── MONITORING / SAR HISTORY ──
    {
        "name": "one_prior_sar",
        "description": "1 prior SAR - normal processing with monitoring",
        "base_facts": {
            **_CLEAN_PROFILE,
            "prior.sars_filed": 1,
        },
        "outcome": {"disposition": "ALLOW", "disposition_basis": "DISCRETIONARY", "reporting": "NO_REPORT"},
        "decision_level": "analyst",
        "weight": 0.03,
        "decision_drivers": ["prior.sars_filed"],
        "driver_typology": "",
    },
    {
        "name": "multiple_prior_sars",
        "description": "2-3 prior SARs - escalate",
        "base_facts": {
            **_CLEAN_PROFILE,
            "prior.sars_filed": 3,
            "txn.pattern_matches_profile": False,
            "flag.unusual_for_profile": True,
        },
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "senior_analyst",
        "weight": 0.03,
        "decision_drivers": ["prior.sars_filed", "flag.unusual_for_profile"],
        "driver_typology": "",
    },
    {
        "name": "heavy_sar_history",
        "description": "4+ prior SARs - block for exit review",
        "base_facts": {
            **_CLEAN_PROFILE,
            "prior.sars_filed": 4,
            "txn.pattern_matches_profile": False,
            "flag.unusual_for_profile": True,
        },
        "outcome": {"disposition": "BLOCK", "disposition_basis": "DISCRETIONARY", "reporting": "FILE_STR"},
        "decision_level": "manager",
        "weight": 0.02,
        "decision_drivers": ["prior.sars_filed"],
        "driver_typology": "",
    },
    {
        "name": "previous_closure",
        "description": "Previous account closure - escalate",
        "base_facts": {
            **_CLEAN_PROFILE,
            "prior.account_closures": True,
            "txn.pattern_matches_profile": False,
        },
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "senior_analyst",
        "weight": 0.03,
        "decision_drivers": ["prior.account_closures"],
        "driver_typology": "",
    },

    # ── BLOCK (discretionary — corroborated risk) ──
    {
        "name": "pep_adverse_media_block",
        "description": "PEP + adverse media (confirmed ML/TF) + cross-border → block for STR",
        "base_facts": {
            **_CLEAN_PROFILE,
            "customer.pep": True,
            "screening.adverse_media_level": "confirmed_mltf",
            "screening.adverse_media": True,
            "screening.pep_match": True,
            "txn.cross_border": True,
            "customer.high_risk_jurisdiction": True,
            "txn.amount_band": "100k_500k",
            "txn.pattern_matches_profile": False,
            "txn.source_of_funds_clear": False,
        },
        "outcome": {"disposition": "BLOCK", "disposition_basis": "DISCRETIONARY", "reporting": "FILE_STR"},
        "decision_level": "manager",
        "weight": 0.02,
        "decision_drivers": ["customer.pep", "screening.adverse_media_level", "screening.pep_match"],
        "driver_typology": "pep_adverse_media",
    },
    {
        "name": "layering_high_value_block",
        "description": "Shell + layering + high value → block for STR",
        "base_facts": {
            **_CLEAN_PROFILE,
            "flag.shell_company": True,
            "flag.layering": True,
            "txn.cross_border": True,
            "txn.destination_country_risk": "high",
            "customer.type": "corporation",
            "txn.amount_band": "500k_1m",
            "txn.pattern_matches_profile": False,
            "txn.source_of_funds_clear": False,
        },
        "outcome": {"disposition": "BLOCK", "disposition_basis": "DISCRETIONARY", "reporting": "FILE_STR"},
        "decision_level": "manager",
        "weight": 0.02,
        "decision_drivers": ["flag.layering", "flag.shell_company", "txn.amount_band"],
        "driver_typology": "layering",
    },

    # ── ALLOW (cleared after investigation) ──
    {
        "name": "shell_entity_cleared",
        "description": "Shell company flags but cleared — source of funds verified",
        "base_facts": {
            **_CLEAN_PROFILE,
            "flag.shell_company": True,
            "flag.layering": True,
            "txn.cross_border": True,
            "customer.type": "corporation",
            "txn.pattern_matches_profile": False,
            "txn.source_of_funds_clear": True,
        },
        "outcome": {"disposition": "ALLOW", "disposition_basis": "DISCRETIONARY", "reporting": "NO_REPORT"},
        "decision_level": "senior_analyst",
        "weight": 0.02,
        "decision_drivers": ["flag.shell_company", "txn.cross_border", "txn.source_of_funds_clear"],
        "driver_typology": "",
    },
    {
        "name": "crypto_corridor_cleared",
        "description": "Crypto high-risk corridor but cleared — funds verified",
        "base_facts": {
            **_CLEAN_PROFILE,
            "txn.type": "crypto",
            "txn.cross_border": True,
            "txn.destination_country_risk": "high",
            "flag.unusual_for_profile": True,
            "txn.pattern_matches_profile": False,
            "txn.source_of_funds_clear": True,
        },
        "outcome": {"disposition": "ALLOW", "disposition_basis": "DISCRETIONARY", "reporting": "NO_REPORT"},
        "decision_level": "senior_analyst",
        "weight": 0.02,
        "decision_drivers": ["txn.type", "txn.destination_country_risk", "txn.source_of_funds_clear"],
        "driver_typology": "",
    },
    {
        "name": "velocity_spike_cleared",
        "description": "Rapid movement cleared — funds verified",
        "base_facts": {
            **_CLEAN_PROFILE,
            "flag.rapid_movement": True,
            "flag.unusual_for_profile": True,
            "txn.amount_band": "25k_100k",
            "txn.pattern_matches_profile": False,
            "txn.source_of_funds_clear": True,
        },
        "outcome": {"disposition": "ALLOW", "disposition_basis": "DISCRETIONARY", "reporting": "NO_REPORT"},
        "decision_level": "senior_analyst",
        "weight": 0.02,
        "decision_drivers": ["flag.rapid_movement", "flag.unusual_for_profile", "txn.source_of_funds_clear"],
        "driver_typology": "",
    },
    {
        "name": "structuring_cleared",
        "description": "Structuring pattern cleared — below threshold, funds verified",
        "base_facts": {
            **_CLEAN_PROFILE,
            "txn.just_below_threshold": True,
            "txn.multiple_same_day": True,
            "flag.structuring": True,
            "txn.round_amount": True,
            "txn.pattern_matches_profile": False,
            "txn.source_of_funds_clear": True,
        },
        "outcome": {"disposition": "ALLOW", "disposition_basis": "DISCRETIONARY", "reporting": "NO_REPORT"},
        "decision_level": "senior_analyst",
        "weight": 0.02,
        "decision_drivers": ["flag.structuring", "txn.source_of_funds_clear"],
        "driver_typology": "structuring",
    },

    # ── TRADE FINANCE ──
    {
        "name": "trade_based_ml",
        "description": "Trade-based ML: vague goods, inconsistent pricing, LC to high-risk destination",
        "base_facts": {
            **_CLEAN_PROFILE,
            "customer.type": "corporation",
            "txn.cross_border": True,
            "txn.source_of_funds_clear": False,
            "txn.pattern_matches_profile": False,
            "trade.goods_description": "vague",
            "trade.pricing_consistent": False,
            "trade.is_letter_of_credit": True,
        },
        "outcome": {"disposition": "BLOCK", "disposition_basis": "DISCRETIONARY", "reporting": "FILE_STR"},
        "decision_level": "manager",
        "weight": 0.03,
        "decision_drivers": ["trade.goods_description", "trade.pricing_consistent"],
        "driver_typology": "trade_based",
    },
    {
        "name": "trade_finance_clean",
        "description": "Legitimate trade finance: detailed goods, consistent pricing, established importer",
        "base_facts": {
            **_CLEAN_PROFILE,
            "customer.type": "corporation",
            "customer.relationship_length": "established",
            "txn.cross_border": True,
            "txn.source_of_funds_clear": True,
            "txn.pattern_matches_profile": True,
            "trade.goods_description": "detailed",
            "trade.pricing_consistent": True,
            "trade.is_letter_of_credit": True,
        },
        "outcome": {"disposition": "ALLOW", "disposition_basis": "DISCRETIONARY", "reporting": "NO_REPORT"},
        "decision_level": "analyst",
        "weight": 0.03,
        "decision_drivers": ["trade.goods_description", "trade.pricing_consistent"],
        "driver_typology": "trade_based",
    },
]


# ---------------------------------------------------------------------------
# Realistic random value generators
# ---------------------------------------------------------------------------

def _random_realistic_value(
    field_name: str,
    field_def: dict[str, Any],
    scenario: dict,
    rng: random.Random,
) -> Any:
    """Generate a realistic random value for a field not pinned by the scenario."""
    is_clean = scenario["outcome"]["disposition"] == "ALLOW"
    is_edd = scenario["outcome"]["disposition"] == "EDD"

    if field_def["type"] == "boolean":
        if field_name.startswith("flag.") and is_clean:
            return rng.random() < 0.03
        if field_name.startswith("screening.") and is_clean:
            return rng.random() < 0.02
        if field_name == "prior.account_closures" and is_clean:
            return rng.random() < 0.02
        if field_name == "trade.is_letter_of_credit":
            return rng.random() < 0.08  # ~8% of seeds are LC transactions
        if field_name == "trade.pricing_consistent":
            if is_clean:
                return rng.random() < 0.92  # mostly consistent for clean cases
            return rng.random() < 0.40  # often inconsistent for suspicious
        if field_name.startswith("flag.") and is_edd:
            return rng.random() < 0.15
        return rng.random() < 0.20

    if field_def["type"] == "enum":
        values = field_def["values"]

        if field_name == "customer.type":
            return rng.choices(values, weights=[70, 30])[0]
        if field_name == "customer.relationship_length":
            if is_clean:
                return rng.choices(values, weights=[10, 30, 60])[0]
            return rng.choices(values, weights=[30, 40, 30])[0]
        if field_name == "txn.amount_band":
            if is_clean:
                return rng.choices(values, weights=[25, 30, 20, 15, 7, 2, 1])[0]
            return rng.choices(values, weights=[10, 20, 25, 25, 12, 5, 3])[0]
        if field_name == "txn.type":
            # [wire_domestic, wire_international, cash, cheque, eft, crypto, trade_finance]
            return rng.choices(values, weights=[23, 18, 18, 9, 14, 10, 8])[0]
        if field_name == "txn.destination_country_risk":
            if is_clean:
                return rng.choices(values, weights=[80, 15, 5])[0]
            return rng.choices(values, weights=[40, 30, 30])[0]
        if field_name == "txn.stated_purpose":
            if is_clean:
                return rng.choices(values, weights=[35, 30, 20, 10, 5])[0]
            return rng.choices(values, weights=[20, 20, 15, 10, 35])[0]
        if field_name == "screening.adverse_media_level":
            # [none, unconfirmed, confirmed, confirmed_mltf]
            if is_clean:
                return rng.choices(values, weights=[95, 3, 1.5, 0.5])[0]
            if is_edd:
                return rng.choices(values, weights=[60, 20, 15, 5])[0]
            return rng.choices(values, weights=[40, 15, 25, 20])[0]
        if field_name == "prior.sars_filed":
            if is_clean:
                return rng.choices(values, weights=[85, 10, 3, 1, 1])[0]
            return rng.choices(values, weights=[40, 25, 20, 10, 5])[0]
        if field_name == "trade.goods_description":
            # [detailed, adequate, vague, missing]
            if is_clean:
                return rng.choices(values, weights=[50, 35, 12, 3])[0]
            if is_edd:
                return rng.choices(values, weights=[15, 25, 40, 20])[0]
            return rng.choices(values, weights=[5, 15, 45, 35])[0]
        return rng.choice(values)

    return None


def _derive_signal_codes(facts: dict[str, Any], scenario: dict) -> list[str]:
    """Derive signal codes from facts and scenario context."""
    codes: list[str] = list(_SCENARIO_REASON_CODES.get(scenario["name"], []))

    if facts.get("flag.structuring") and "RC-TXN-STRUCT" not in codes:
        codes.append("RC-TXN-STRUCT")
    if facts.get("flag.layering") and "RC-TXN-LAYER" not in codes:
        codes.append("RC-TXN-LAYER")
    if facts.get("flag.rapid_movement") and "RC-TXN-RAPID" not in codes:
        codes.append("RC-TXN-RAPID")
    if facts.get("screening.sanctions_match") and "RC-SCR-SANCTION" not in codes:
        codes.extend(["RC-SCR-SANCTION", "RC-SCR-OFAC"])
    if (facts.get("customer.pep") or facts.get("screening.pep_match")) and "RC-TXN-PEP" not in codes:
        codes.append("RC-TXN-PEP")
    if facts.get("screening.adverse_media") and "RC-KYC-ADVERSE-MINOR" not in codes:
        codes.append("RC-KYC-ADVERSE-MINOR")
    if (facts.get("customer.high_risk_jurisdiction") or facts.get("txn.destination_country_risk") == "high") and "RC-TXN-FATF-GREY" not in codes:
        codes.append("RC-TXN-FATF-GREY")
    if facts.get("flag.unusual_for_profile") and "RC-TXN-UNUSUAL" not in codes:
        codes.append("RC-TXN-UNUSUAL")

    return list(dict.fromkeys(codes))


# v1 outcome backward compatibility mapping
_DISPOSITION_TO_V1 = {"ALLOW": "pay", "EDD": "escalate", "BLOCK": "deny"}


# ---------------------------------------------------------------------------
# Seed builder
# ---------------------------------------------------------------------------

def _build_anchor_facts(facts: dict, idx: int) -> list[AnchorFact]:
    """Turn a flat dict into AnchorFact list."""
    result = []
    for field_id, value in facts.items():
        label = BANKING_FIELDS[field_id]["display_name"] if field_id in BANKING_FIELDS else field_id
        result.append(AnchorFact(field_id=field_id, value=value, label=label))
    return result


def _generate_seed(
    scenario: dict,
    variation: int,
    rng: random.Random,
    salt: str = SEED_SALT,
) -> JudgmentPayload:
    """Generate one seed with ALL 28 fields populated."""
    facts: dict[str, Any] = {}

    # 1. Set base facts from scenario
    for field_name, value in scenario["base_facts"].items():
        facts[field_name] = value

    # 2. Fill ALL remaining fields with realistic random values
    for field_name, field_def in BANKING_FIELDS.items():
        if field_name not in facts:
            facts[field_name] = _random_realistic_value(field_name, field_def, scenario, rng)

    # 2b. Keep derived boolean in sync with level field
    _am_level = facts.get("screening.adverse_media_level", "none")
    facts["screening.adverse_media"] = _am_level not in ("none", None, False, "")

    # 2c. LC transactions → trade_finance channel for comparability gate
    if facts.get("trade.is_letter_of_credit"):
        facts["txn.type"] = "trade_finance"

    # 3. Validate every field
    for field_name, value in facts.items():
        if field_name in BANKING_FIELDS:
            validate_field_value(field_name, value)

    # 4. Derive codes
    signal_codes = _derive_signal_codes(facts, scenario)
    reason_codes = list(signal_codes)
    schema_id = _schema_for_codes(reason_codes)

    # 5. Build anchor facts
    anchor_facts = _build_anchor_facts(facts, variation)

    # 6. Compute hashes
    precedent_id = str(uuid4())
    case_id = f"SEED-{scenario['name']}-{variation:04d}"
    case_id_hash = hashlib.sha256(f"{salt}:{case_id}".encode()).hexdigest()

    facts_str = "|".join(f"{af.field_id}={af.value}" for af in anchor_facts)
    fingerprint_hash = hashlib.sha256(f"{salt}:{facts_str}".encode()).hexdigest()

    # Spread decided_at over the last 12 months
    days_ago = (variation * 7) % 365
    decided_at = (
        datetime.now(timezone.utc) - timedelta(days=days_ago)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ── Regime tagging (B1.1) ─────────────────────────────────────────
    seed_like = _case_facts_to_seed_like(facts)
    decided_date = datetime.fromisoformat(decided_at.replace("Z", "+00:00")).date()
    affected_shift_ids = [
        shift["id"] for shift in POLICY_SHIFTS
        if shift["_affects"](seed_like)
    ]
    if affected_shift_ids:
        all_effective = all(
            decided_date >= SHIFT_EFFECTIVE_DATES[sid]
            for sid in affected_shift_ids
        )
        policy_regime = {
            "version": POLICY_VERSION,
            "shifts_applied": affected_shift_ids,
            "is_post_shift": all_effective,
        }
    else:
        policy_regime = {
            "version": POLICY_VERSION,
            "shifts_applied": [],
            "is_post_shift": True,
        }

    # v1 backward compat: map banking disposition to pay/deny/escalate
    outcome_code_v1 = _DISPOSITION_TO_V1.get(scenario["outcome"]["disposition"], "escalate")

    return JudgmentPayload(
        precedent_id=precedent_id,
        case_id_hash=case_id_hash,
        jurisdiction_code="CA",
        fingerprint_hash=fingerprint_hash,
        fingerprint_schema_id=schema_id,
        exclusion_codes=list(signal_codes),
        reason_codes=list(reason_codes),
        reason_code_registry_id="decisiongraph:aml:reason_codes:v1",
        outcome_code=outcome_code_v1,
        certainty="high",
        anchor_facts=anchor_facts,
        policy_pack_hash=POLICY_PACK_HASH,
        policy_pack_id=POLICY_PACK_ID,
        policy_version=POLICY_VERSION,
        decision_level=scenario.get("decision_level", "analyst"),
        decided_at=decided_at,
        decided_by_role="aml_analyst",
        source_type="seed",
        scenario_code=scenario["name"],
        seed_category="aml",
        disposition_basis=scenario["outcome"]["disposition_basis"],
        reporting_obligation=scenario["outcome"]["reporting"],
        domain="banking",
        signal_codes=list(signal_codes),
        decision_drivers=scenario.get("decision_drivers", []),
        driver_typology=scenario.get("driver_typology", ""),
        policy_regime=policy_regime,
    )


# ---------------------------------------------------------------------------
# Noise: minority-outcome variants (~10%)
# ---------------------------------------------------------------------------

_NOISE_OUTCOMES: dict[str, dict] = {
    "structuring_suspected": {
        "outcome": {"disposition": "ALLOW", "disposition_basis": "DISCRETIONARY", "reporting": "NO_REPORT"},
        "decision_level": "senior_analyst",
    },
    "adverse_media": {
        "outcome": {"disposition": "ALLOW", "disposition_basis": "DISCRETIONARY", "reporting": "NO_REPORT"},
        "decision_level": "senior_analyst",
    },
    "pep_large_amount": {
        "outcome": {"disposition": "ALLOW", "disposition_basis": "DISCRETIONARY", "reporting": "NO_REPORT"},
        "decision_level": "manager",
    },
    "high_risk_country": {
        "outcome": {"disposition": "ALLOW", "disposition_basis": "DISCRETIONARY", "reporting": "NO_REPORT"},
        "decision_level": "senior_analyst",
    },
    "profile_deviation": {
        "outcome": {"disposition": "BLOCK", "disposition_basis": "DISCRETIONARY", "reporting": "FILE_STR"},
        "decision_level": "manager",
    },
    "rapid_movement": {
        "outcome": {"disposition": "BLOCK", "disposition_basis": "DISCRETIONARY", "reporting": "FILE_STR"},
        "decision_level": "manager",
    },
    "pep_adverse_media_block": {
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "senior_analyst",
    },
    "layering_high_value_block": {
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "senior_analyst",
    },
    "shell_entity_cleared": {
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "senior_analyst",
    },
    "crypto_corridor_cleared": {
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "senior_analyst",
    },
    "velocity_spike_cleared": {
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "senior_analyst",
    },
    "structuring_cleared": {
        "outcome": {"disposition": "EDD", "disposition_basis": "DISCRETIONARY", "reporting": "PENDING_EDD"},
        "decision_level": "senior_analyst",
    },
}


def generate_all_banking_seeds(
    salt: str = SEED_SALT,
    random_seed: int = 42,
    total: int = TOTAL_SEEDS,
) -> list[JudgmentPayload]:
    """Generate all banking seed precedents.

    Returns ~1,500 JudgmentPayload objects covering all 26 AML
    scenarios with full 28-field coverage.
    """
    rng = random.Random(random_seed)
    seeds: list[JudgmentPayload] = []

    for scenario in SCENARIOS:
        count = max(1, round(total * scenario["weight"]))
        noise_eligible = scenario["name"] in _NOISE_OUTCOMES
        noise_count = max(1, round(count * 0.10)) if noise_eligible else 0

        for i in range(count):
            if noise_eligible and i < noise_count:
                noise = _NOISE_OUTCOMES[scenario["name"]]
                noisy_scenario = {
                    **scenario,
                    "outcome": noise["outcome"],
                    "decision_level": noise.get("decision_level", scenario.get("decision_level", "analyst")),
                }
                seeds.append(_generate_seed(noisy_scenario, i, rng, salt))
            else:
                seeds.append(_generate_seed(scenario, i, rng, salt))

    # ── Post-shift seeds (B1.1) ─────────────────────────────────────
    post_shift = _generate_post_shift_seeds(seeds, rng, salt)
    seeds.extend(post_shift)

    return seeds


# ---------------------------------------------------------------------------
# Post-shift seed generation (B1.1)
# ---------------------------------------------------------------------------

_V1_TO_DISPOSITION_INV = {"pay": "ALLOW", "escalate": "EDD", "deny": "BLOCK"}


def _generate_post_shift_seeds(
    base_seeds: list[JudgmentPayload],
    rng: random.Random,
    salt: str = SEED_SALT,
) -> list[JudgmentPayload]:
    """Generate ~4-8 post-shift seeds per policy shift.

    Clones affected base seeds, moves decided_at past the shift effective date,
    and applies the new outcome dictated by the shift.
    """
    post_shift_seeds: list[JudgmentPayload] = []

    for shift in POLICY_SHIFTS:
        shift_id = shift["id"]
        effective_date = SHIFT_EFFECTIVE_DATES[shift_id]
        affects_fn = shift["_affects"]
        outcome_fn = shift["_new_outcome"]

        # Find base seeds affected by this shift
        affected_bases = []
        for seed in base_seeds:
            facts_dict = {af.field_id: af.value for af in seed.anchor_facts}
            seed_like = _case_facts_to_seed_like(facts_dict)
            if affects_fn(seed_like):
                affected_bases.append(seed)

        target_count = min(rng.randint(4, 8), len(affected_bases))
        if target_count == 0:
            continue
        selected = rng.sample(affected_bases, target_count)

        for i, base in enumerate(selected):
            facts_dict = {af.field_id: af.value for af in base.anchor_facts}
            seed_like = _case_facts_to_seed_like(facts_dict)
            old_outcome = {
                "disposition": _V1_TO_DISPOSITION_INV.get(base.outcome_code, base.outcome_code),
                "disposition_basis": base.disposition_basis,
                "reporting": base.reporting_obligation,
            }
            new_outcome, new_level = outcome_fn(seed_like, old_outcome)
            if new_level is None:
                new_level = base.decision_level

            # decided_at: effective_date + i days
            post_date = datetime(
                effective_date.year, effective_date.month, effective_date.day,
                tzinfo=timezone.utc,
            ) + timedelta(days=i + 1)
            new_decided_at = post_date.strftime("%Y-%m-%dT%H:%M:%SZ")

            new_disposition = new_outcome.get(
                "disposition",
                old_outcome.get("disposition", "EDD"),
            )
            new_outcome_code = _DISPOSITION_TO_V1.get(new_disposition, "escalate")

            new_precedent_id = str(uuid4())
            case_id = f"SEED-POSTSHIFT-{shift_id}-{i:04d}"
            case_id_hash = hashlib.sha256(f"{salt}:{case_id}".encode()).hexdigest()
            facts_str = "|".join(
                f"{af.field_id}={af.value}" for af in base.anchor_facts
            )
            fingerprint_hash = hashlib.sha256(
                f"{salt}:ps:{facts_str}".encode()
            ).hexdigest()

            post_seed = JudgmentPayload(
                precedent_id=new_precedent_id,
                case_id_hash=case_id_hash,
                jurisdiction_code=base.jurisdiction_code,
                fingerprint_hash=fingerprint_hash,
                fingerprint_schema_id=base.fingerprint_schema_id,
                exclusion_codes=list(base.exclusion_codes),
                reason_codes=list(base.reason_codes),
                reason_code_registry_id=base.reason_code_registry_id,
                outcome_code=new_outcome_code,
                certainty=base.certainty,
                anchor_facts=list(base.anchor_facts),
                policy_pack_hash=POLICY_PACK_HASH,
                policy_pack_id=POLICY_PACK_ID,
                policy_version=shift["policy_version"],
                decision_level=new_level,
                decided_at=new_decided_at,
                decided_by_role=base.decided_by_role,
                source_type="seed",
                scenario_code=base.scenario_code,
                seed_category="aml_post_shift",
                disposition_basis=new_outcome.get(
                    "disposition_basis", base.disposition_basis,
                ),
                reporting_obligation=new_outcome.get(
                    "reporting", base.reporting_obligation,
                ),
                domain="banking",
                signal_codes=list(base.signal_codes),
                decision_drivers=list(base.decision_drivers),
                driver_typology=base.driver_typology,
                policy_regime={
                    "version": shift["policy_version"],
                    "shifts_applied": [shift_id],
                    "is_post_shift": True,
                },
            )
            post_shift_seeds.append(post_seed)

    return post_shift_seeds


# Backward-compat stubs for imports that reference old class names
class SeedGeneratorError(Exception):
    pass

class SeedConfigError(SeedGeneratorError):
    pass

class SeedLoadError(SeedGeneratorError):
    pass

SeedScenario = dict
SeedConfig = dict
SeedGenerator = None


def create_txn_monitoring_seed_config():
    return None

def create_kyc_onboarding_seed_config():
    return None

def create_reporting_seed_config():
    return None

def create_screening_seed_config():
    return None

def create_monitoring_seed_config():
    return None


__all__ = [
    "SeedGeneratorError",
    "SeedConfigError",
    "SeedLoadError",
    "SeedScenario",
    "SeedConfig",
    "SeedGenerator",
    "create_txn_monitoring_seed_config",
    "create_kyc_onboarding_seed_config",
    "create_reporting_seed_config",
    "create_screening_seed_config",
    "create_monitoring_seed_config",
    "generate_all_banking_seeds",
    "SCENARIOS",
    "SEED_SALT",
    "TOTAL_SEEDS",
    "AMOUNT_BANDS",
    "CHANNELS",
]
