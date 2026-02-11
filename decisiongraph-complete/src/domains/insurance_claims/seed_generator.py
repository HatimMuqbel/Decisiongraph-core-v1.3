"""
DecisionGraph Insurance Claims Seed Generator v1

Generates 1,600 seed precedents using ALL 24 fields from the insurance field
registry.  Every seed uses three-field insurance outcomes (disposition /
disposition_basis / reporting) -- no banking vocabulary.

Design:
- 20 scenarios with base_facts that define the pattern
- Each scenario has a weight that determines how many seeds to generate
- Remaining fields are filled with realistic random values
- ~10 % noise: minority-outcome variants per scenario

All seeds use canonical field names from insurance_claims/registry.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import uuid4

from .registry import (
    INSURANCE_FIELDS,
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

SEED_SALT = "decisiongraph-insurance-seed-v1"
POLICY_VERSION = "2026.01.01"
POLICY_PACK_ID = "CA-FSRA-INSURANCE"
POLICY_PACK_HASH = hashlib.sha256(b"CA-FSRA-INSURANCE-v2026.01.01").hexdigest()
TOTAL_SEEDS = 1600
FINGERPRINT_SCHEMA = "decisiongraph:insurance:claims:v1"

# Coverage line groupings
COVERAGE_LINES = ["auto", "property", "health", "workers_comp", "cgl", "eo", "marine", "travel"]
AMOUNT_BANDS = ["under_5k", "5k_25k", "25k_100k", "100k_500k", "over_500k"]

# Reason code prefixes by scenario type
_SCENARIO_REASON_CODES: dict[str, list[str]] = {
    "clean_auto_claim":         ["RC-CLM-NORMAL", "RC-CLM-PROFILE-MATCH"],
    "clean_property_claim":     ["RC-CLM-NORMAL", "RC-CLM-PROFILE-MATCH"],
    "auto_injury_minor":        ["RC-CLM-NORMAL", "RC-INJ-MINOR"],
    "auto_injury_serious":      ["RC-INJ-SERIOUS", "RC-INJ-MEDICAL"],
    "property_water_damage":    ["RC-CLM-NORMAL", "RC-CAUSE-WATER"],
    "property_fire_arson":      ["RC-CAUSE-FIRE", "RC-FRD-ARSON-SUSPECTED"],
    "workers_comp_injury":      ["RC-CLM-NORMAL", "RC-INJ-MODERATE"],
    "health_formulary":         ["RC-CLM-NORMAL", "RC-CLM-HEALTH"],
    "health_preexisting":       ["RC-FLG-PREEXISTING", "RC-CLM-HEALTH"],
    "marine_vessel":            ["RC-CLM-NORMAL", "RC-CAUSE-COLLISION"],
    "travel_emergency":         ["RC-CLM-NORMAL", "RC-CLM-TRAVEL"],
    "cgl_liability":            ["RC-CLM-LIABILITY", "RC-CLM-THIRD-PARTY"],
    "eo_professional":          ["RC-CLM-PROFESSIONAL", "RC-CLM-THIRD-PARTY"],
    "fraud_staged_accident":    ["RC-FRD-STAGED", "RC-FRD-INCONSISTENT"],
    "fraud_excessive_history":  ["RC-FRD-EXCESSIVE", "RC-PRIOR-DENIED"],
    "late_reporting_suspicious": ["RC-FLG-LATE-REPORT", "RC-FRD-INCONSISTENT"],
    "high_value_claim":         ["RC-CLM-HIGH-VALUE", "RC-CLM-REVIEW"],
    "siu_referral_pattern":     ["RC-SIU-REFERRAL", "RC-FRD-INDICATOR"],
    "policy_exclusion_deny":    ["RC-POL-EXCLUSION", "RC-POL-OUTSIDE-PERIOD"],
    "auto_impairment_deny":     ["RC-POL-EXCLUSION", "RC-FRD-INDICATOR"],
    "property_vacancy_deny":    ["RC-POL-EXCLUSION", "RC-CLM-PROPERTY"],
    "prior_denied_multiple":    ["RC-PRIOR-DENIED", "RC-PRIOR-MULTIPLE"],
}


# ---------------------------------------------------------------------------
# Schema selection (mirrors banking _schema_for_codes)
# ---------------------------------------------------------------------------

def _schema_for_codes(codes: list[str]) -> str:
    """Pick fingerprint schema from reason code prefixes."""
    prefixes = {c.split("-")[1].upper() for c in codes if c.startswith("RC-") and "-" in c}
    if "SIU" in prefixes:
        return "decisiongraph:insurance:siu:v1"
    if "FRD" in prefixes:
        return "decisiongraph:insurance:fraud:v1"
    if "INJ" in prefixes:
        return "decisiongraph:insurance:injury:v1"
    if "POL" in prefixes:
        return "decisiongraph:insurance:policy:v1"
    return "decisiongraph:insurance:claims:v1"


# ---------------------------------------------------------------------------
# Decision-level mapping — the JudgmentPayload validator accepts a limited
# set of insurance levels {adjuster, manager, tribunal, court}.  We map the
# scenario-specific role names to the nearest valid level so seeds pass
# validation while retaining the conceptual authority hierarchy.
# ---------------------------------------------------------------------------

_DECISION_LEVEL_MAP: dict[str, str] = {
    "adjuster": "adjuster",
    "senior_adjuster": "adjuster",
    "examiner": "adjuster",
    "supervisor": "manager",
    "siu_investigator": "manager",
    "claims_manager": "manager",
}


# ---------------------------------------------------------------------------
# 20 scenarios  (matches task spec)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Clean defaults -- every scenario starts from this base; scenario-specific
# overrides are applied on top.  This ensures ALL 24 fields are populated
# with coherent values rather than random noise, which is critical for v3
# field-by-field similarity scoring.
# ---------------------------------------------------------------------------

# Boolean / flag defaults only.  The high-variation enum fields
# (claim.coverage_line, claim.amount_band, claim.claimant_type,
# claim.injury_type, claim.loss_cause, etc.) are intentionally omitted
# so _random_realistic_value() fills them with weighted distributions, giving
# natural variety across seeds.
_CLEAN_PROFILE: dict[str, Any] = {
    # Red flags — all off
    "flag.fraud_indicator": False,
    "flag.late_reporting": False,
    "flag.inconsistent_statements": False,
    "flag.staged_accident": False,
    "flag.excessive_claim_history": False,
    "flag.pre_existing_damage": False,
    # Evidence — all available
    "evidence.police_report": True,
    "evidence.medical_report": True,
    "evidence.witness_statements": True,
    "evidence.photos_documentation": True,
    # Policy context
    "claim.occurred_during_policy": True,
    # Screening
    "screening.siu_referral": False,
    "prior.claims_denied": 0,
}


SCENARIOS = [
    # == PAY_CLAIM ==
    {
        "name": "clean_auto_claim",
        "description": "Clean auto claim, first party, small amount, no flags",
        "base_facts": {
            **_CLEAN_PROFILE,
            "claim.coverage_line": "auto",
            "claim.claimant_type": "first_party",
            "claim.amount_band": "under_5k",
        },
        "outcome": {"disposition": "PAY_CLAIM", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "adjuster",
        "weight": 0.12,
        "decision_drivers": ["claim.coverage_line", "claim.amount_band", "claim.claimant_type"],
        "driver_typology": "",
    },
    {
        "name": "clean_property_claim",
        "description": "Clean property claim, first party, small amount",
        "base_facts": {
            **_CLEAN_PROFILE,
            "claim.coverage_line": "property",
            "claim.claimant_type": "first_party",
            "claim.amount_band": "under_5k",
        },
        "outcome": {"disposition": "PAY_CLAIM", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "adjuster",
        "weight": 0.08,
        "decision_drivers": ["claim.coverage_line", "claim.amount_band"],
        "driver_typology": "",
    },
    {
        "name": "auto_injury_minor",
        "description": "Auto claim with minor injury",
        "base_facts": {
            **_CLEAN_PROFILE,
            "claim.coverage_line": "auto",
            "claim.injury_type": "minor",
            "claim.loss_cause": "collision",
        },
        "outcome": {"disposition": "PAY_CLAIM", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "adjuster",
        "weight": 0.08,
        "decision_drivers": ["claim.injury_type", "claim.coverage_line"],
        "driver_typology": "",
    },

    # == PARTIAL_PAY (EDD in v3 mapping) ==
    {
        "name": "auto_injury_serious",
        "description": "Auto claim with serious injury, medical report required",
        "base_facts": {
            **_CLEAN_PROFILE,
            "claim.coverage_line": "auto",
            "claim.injury_type": "serious",
            "claim.loss_cause": "collision",
            "evidence.medical_report": True,
            "claim.amount_band": "25k_100k",
        },
        "outcome": {"disposition": "PARTIAL_PAY", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "examiner",
        "weight": 0.06,
        "decision_drivers": ["claim.injury_type", "evidence.medical_report", "claim.amount_band"],
        "driver_typology": "injury",
    },

    # == PAY_CLAIM (continued) ==
    {
        "name": "property_water_damage",
        "description": "Property claim, water damage cause",
        "base_facts": {
            **_CLEAN_PROFILE,
            "claim.coverage_line": "property",
            "claim.loss_cause": "water",
        },
        "outcome": {"disposition": "PAY_CLAIM", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "adjuster",
        "weight": 0.06,
        "decision_drivers": ["claim.loss_cause", "claim.coverage_line"],
        "driver_typology": "",
    },

    # == INVESTIGATE (EDD) ==
    {
        "name": "property_fire_arson",
        "description": "Property claim, fire cause, arson suspected",
        "base_facts": {
            **_CLEAN_PROFILE,
            "claim.coverage_line": "property",
            "claim.loss_cause": "fire",
            "flag.fraud_indicator": True,
            "flag.inconsistent_statements": True,
        },
        "outcome": {"disposition": "INVESTIGATE", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "examiner",
        "weight": 0.04,
        "decision_drivers": ["claim.loss_cause", "flag.fraud_indicator", "flag.inconsistent_statements"],
        "driver_typology": "arson",
    },

    # == PAY_CLAIM (continued) ==
    {
        "name": "workers_comp_injury",
        "description": "Workers comp claim, moderate injury",
        "base_facts": {
            **_CLEAN_PROFILE,
            "claim.coverage_line": "workers_comp",
            "claim.injury_type": "moderate",
            "claim.loss_cause": "other",
        },
        "outcome": {"disposition": "PAY_CLAIM", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "adjuster",
        "weight": 0.05,
        "decision_drivers": ["claim.coverage_line", "claim.injury_type"],
        "driver_typology": "",
    },
    {
        "name": "health_formulary",
        "description": "Health claim, minor, formulary covered",
        "base_facts": {
            **_CLEAN_PROFILE,
            "claim.coverage_line": "health",
            "claim.injury_type": "minor",
            "claim.amount_band": "under_5k",
        },
        "outcome": {"disposition": "PAY_CLAIM", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "adjuster",
        "weight": 0.04,
        "decision_drivers": ["claim.coverage_line", "claim.injury_type"],
        "driver_typology": "",
    },

    # == INVESTIGATE (EDD) ==
    {
        "name": "health_preexisting",
        "description": "Health claim with pre-existing damage indicator",
        "base_facts": {
            **_CLEAN_PROFILE,
            "claim.coverage_line": "health",
            "flag.pre_existing_damage": True,
            "claim.injury_type": "moderate",
        },
        "outcome": {"disposition": "INVESTIGATE", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "examiner",
        "weight": 0.03,
        "decision_drivers": ["flag.pre_existing_damage", "claim.coverage_line"],
        "driver_typology": "pre_existing",
    },

    # == PAY_CLAIM (continued) ==
    {
        "name": "marine_vessel",
        "description": "Marine claim, collision cause",
        "base_facts": {
            **_CLEAN_PROFILE,
            "claim.coverage_line": "marine",
            "claim.loss_cause": "collision",
        },
        "outcome": {"disposition": "PAY_CLAIM", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "adjuster",
        "weight": 0.03,
        "decision_drivers": ["claim.coverage_line", "claim.loss_cause"],
        "driver_typology": "",
    },
    {
        "name": "travel_emergency",
        "description": "Travel claim, serious emergency",
        "base_facts": {
            **_CLEAN_PROFILE,
            "claim.coverage_line": "travel",
            "claim.injury_type": "serious",
        },
        "outcome": {"disposition": "PAY_CLAIM", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "adjuster",
        "weight": 0.03,
        "decision_drivers": ["claim.coverage_line", "claim.injury_type"],
        "driver_typology": "",
    },

    # == INVESTIGATE (EDD) — liability lines ==
    {
        "name": "cgl_liability",
        "description": "CGL claim, third party, liability cause",
        "base_facts": {
            **_CLEAN_PROFILE,
            "claim.coverage_line": "cgl",
            "claim.claimant_type": "third_party",
            "claim.loss_cause": "liability",
            "claim.amount_band": "25k_100k",
        },
        "outcome": {"disposition": "INVESTIGATE", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "senior_adjuster",
        "weight": 0.04,
        "decision_drivers": ["claim.coverage_line", "claim.claimant_type", "claim.loss_cause"],
        "driver_typology": "liability",
    },
    {
        "name": "eo_professional",
        "description": "E&O professional liability claim, third party",
        "base_facts": {
            **_CLEAN_PROFILE,
            "claim.coverage_line": "eo",
            "claim.claimant_type": "third_party",
            "claim.loss_cause": "liability",
        },
        "outcome": {"disposition": "INVESTIGATE", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "senior_adjuster",
        "weight": 0.03,
        "decision_drivers": ["claim.coverage_line", "claim.claimant_type"],
        "driver_typology": "professional_liability",
    },

    # == REFER_SIU (EDD) — fraud ==
    {
        "name": "fraud_staged_accident",
        "description": "Auto claim, staged accident indicators, fraud flags, inconsistent statements",
        "base_facts": {
            **_CLEAN_PROFILE,
            "claim.coverage_line": "auto",
            "flag.staged_accident": True,
            "flag.fraud_indicator": True,
            "flag.inconsistent_statements": True,
            "evidence.witness_statements": False,
        },
        "outcome": {"disposition": "REFER_SIU", "disposition_basis": "DISCRETIONARY", "reporting": "FRAUD_REPORT"},
        "decision_level": "siu_investigator",
        "weight": 0.04,
        "decision_drivers": ["flag.staged_accident", "flag.fraud_indicator", "flag.inconsistent_statements"],
        "driver_typology": "staged_accident",
    },

    # == DENY_CLAIM (BLOCK) — excessive history ==
    {
        "name": "fraud_excessive_history",
        "description": "Excessive claim history, prior denials",
        "base_facts": {
            **_CLEAN_PROFILE,
            "flag.excessive_claim_history": True,
            "flag.fraud_indicator": True,
            "flag.prior_claims_frequency": "high",
            "prior.claims_denied": 3,
        },
        "outcome": {"disposition": "DENY_CLAIM", "disposition_basis": "DISCRETIONARY", "reporting": "FRAUD_REPORT"},
        "decision_level": "claims_manager",
        "weight": 0.03,
        "decision_drivers": ["flag.excessive_claim_history", "prior.claims_denied", "flag.prior_claims_frequency"],
        "driver_typology": "excessive_history",
    },

    # == INVESTIGATE (EDD) — late reporting ==
    {
        "name": "late_reporting_suspicious",
        "description": "Delayed reporting with inconsistent statements",
        "base_facts": {
            **_CLEAN_PROFILE,
            "flag.late_reporting": True,
            "flag.inconsistent_statements": True,
            "claim.time_to_report": "delayed",
        },
        "outcome": {"disposition": "INVESTIGATE", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "examiner",
        "weight": 0.04,
        "decision_drivers": ["flag.late_reporting", "flag.inconsistent_statements", "claim.time_to_report"],
        "driver_typology": "late_reporting",
    },

    # == INVESTIGATE (EDD) — high value ==
    {
        "name": "high_value_claim",
        "description": "Large claim amount, over 500K, requires review",
        "base_facts": {
            **_CLEAN_PROFILE,
            "claim.amount_band": "over_500k",
        },
        "outcome": {"disposition": "INVESTIGATE", "disposition_basis": "DISCRETIONARY", "reporting": "FSRA_NOTICE"},
        "decision_level": "claims_manager",
        "weight": 0.04,
        "decision_drivers": ["claim.amount_band"],
        "driver_typology": "high_value",
    },

    # == REFER_SIU (EDD) — SIU referral pattern ==
    {
        "name": "siu_referral_pattern",
        "description": "SIU referral with fraud indicators",
        "base_facts": {
            **_CLEAN_PROFILE,
            "screening.siu_referral": True,
            "flag.fraud_indicator": True,
        },
        "outcome": {"disposition": "REFER_SIU", "disposition_basis": "DISCRETIONARY", "reporting": "FRAUD_REPORT"},
        "decision_level": "siu_investigator",
        "weight": 0.04,
        "decision_drivers": ["screening.siu_referral", "flag.fraud_indicator"],
        "driver_typology": "siu_referral",
    },

    # == DENY_CLAIM (BLOCK) — mandatory policy exclusion ==
    {
        "name": "policy_exclusion_deny",
        "description": "Loss not during policy period, mandatory denial",
        "base_facts": {
            **_CLEAN_PROFILE,
            "claim.occurred_during_policy": False,
        },
        "outcome": {"disposition": "DENY_CLAIM", "disposition_basis": "MANDATORY", "reporting": "NO_FILING"},
        "decision_level": "adjuster",
        "weight": 0.04,
        "decision_drivers": ["claim.occurred_during_policy"],
        "driver_typology": "policy_exclusion",
    },

    # == DENY_CLAIM (BLOCK) — driver impairment exclusion ==
    {
        "name": "auto_impairment_deny",
        "description": "Auto claim denied due to driver impairment (alcohol/drugs), policy exclusion triggered",
        "base_facts": {
            **_CLEAN_PROFILE,
            "claim.coverage_line": "auto",
            "claim.claimant_type": "first_party",
            "claim.loss_cause": "collision",
            "claim.injury_type": "moderate",
            "flag.fraud_indicator": True,
            "evidence.police_report": True,
        },
        "outcome": {"disposition": "DENY_CLAIM", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "adjuster",
        "weight": 0.03,
        "decision_drivers": ["flag.fraud_indicator", "claim.coverage_line", "evidence.police_report"],
        "driver_typology": "impairment",
    },

    # == DENY_CLAIM (BLOCK) — property vacancy exclusion ==
    {
        "name": "property_vacancy_deny",
        "description": "Property claim denied due to vacancy exceeding policy limit",
        "base_facts": {
            **_CLEAN_PROFILE,
            "claim.coverage_line": "property",
            "claim.claimant_type": "first_party",
            "claim.occurred_during_policy": True,
        },
        "outcome": {"disposition": "DENY_CLAIM", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "adjuster",
        "weight": 0.02,
        "decision_drivers": ["claim.coverage_line", "claim.occurred_during_policy"],
        "driver_typology": "vacancy_exclusion",
    },

    # == INVESTIGATE (EDD) — prior denials ==
    {
        "name": "prior_denied_multiple",
        "description": "3+ prior claim denials, escalate for investigation",
        "base_facts": {
            **_CLEAN_PROFILE,
            "prior.claims_denied": 3,
            "flag.prior_claims_frequency": "high",
        },
        "outcome": {"disposition": "INVESTIGATE", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "supervisor",
        "weight": 0.03,
        "decision_drivers": ["prior.claims_denied", "flag.prior_claims_frequency"],
        "driver_typology": "prior_denials",
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
    disposition = scenario["outcome"]["disposition"]
    is_pay = disposition in ("PAY_CLAIM", "PARTIAL_PAY")
    is_investigate = disposition in ("INVESTIGATE", "REFER_SIU")

    if field_def["type"] == "boolean":
        # Flag fields — low probability on clean claims
        if field_name.startswith("flag.") and is_pay:
            return rng.random() < 0.03
        if field_name.startswith("screening.") and is_pay:
            return rng.random() < 0.02
        if field_name.startswith("flag.") and is_investigate:
            return rng.random() < 0.15

        # Evidence fields — high probability on clean claims
        if field_name.startswith("evidence.") and is_pay:
            return rng.random() < 0.90
        if field_name.startswith("evidence.") and is_investigate:
            return rng.random() < 0.60

        # claim.occurred_during_policy — almost always true except deny
        if field_name == "claim.occurred_during_policy":
            if disposition == "DENY_CLAIM":
                return rng.random() < 0.30
            return rng.random() < 0.97

        return rng.random() < 0.20

    if field_def["type"] == "enum":
        values = field_def["values"]

        if field_name == "claim.coverage_line":
            # weighted toward auto and property
            return rng.choices(values, weights=[30, 25, 15, 10, 7, 5, 4, 4])[0]

        if field_name == "claim.amount_band":
            if is_pay:
                return rng.choices(values, weights=[35, 30, 20, 10, 5])[0]
            return rng.choices(values, weights=[15, 20, 25, 25, 15])[0]

        if field_name == "claim.claimant_type":
            return rng.choices(values, weights=[70, 30])[0]

        if field_name == "flag.prior_claims_frequency":
            if is_pay:
                return rng.choices(values, weights=[60, 25, 10, 5])[0]
            return rng.choices(values, weights=[20, 30, 30, 20])[0]

        if field_name == "policy.deductible_band":
            return rng.choices(values, weights=[40, 40, 20])[0]

        if field_name == "policy.coverage_limit_band":
            if is_pay:
                return rng.choices(values, weights=[15, 45, 30, 10])[0]
            return rng.choices(values, weights=[10, 30, 35, 25])[0]

        if field_name == "policy.policy_age":
            if is_pay:
                return rng.choices(values, weights=[15, 35, 50])[0]
            return rng.choices(values, weights=[35, 35, 30])[0]

        if field_name == "claim.injury_type":
            if is_pay:
                return rng.choices(values, weights=[40, 35, 20, 5])[0]
            return rng.choices(values, weights=[15, 25, 35, 25])[0]

        if field_name == "claim.loss_cause":
            return rng.choices(values, weights=[25, 10, 10, 15, 10, 8, 15, 7])[0]

        if field_name == "claim.time_to_report":
            if is_pay:
                return rng.choices(values, weights=[40, 35, 20, 5])[0]
            return rng.choices(values, weights=[15, 25, 30, 30])[0]

        if field_name == "prior.claims_denied":
            if is_pay:
                return rng.choices(values, weights=[80, 12, 5, 2, 1])[0]
            return rng.choices(values, weights=[30, 25, 20, 15, 10])[0]

        return rng.choice(values)

    return None


def _derive_signal_codes(facts: dict[str, Any], scenario: dict) -> list[str]:
    """Derive signal codes from facts and scenario context."""
    codes: list[str] = list(_SCENARIO_REASON_CODES.get(scenario["name"], []))

    if facts.get("flag.fraud_indicator") and "RC-FRD-INDICATOR" not in codes:
        codes.append("RC-FRD-INDICATOR")
    if facts.get("flag.staged_accident") and "RC-FRD-STAGED" not in codes:
        codes.append("RC-FRD-STAGED")
    if facts.get("flag.inconsistent_statements") and "RC-FRD-INCONSISTENT" not in codes:
        codes.append("RC-FRD-INCONSISTENT")
    if facts.get("flag.late_reporting") and "RC-FLG-LATE-REPORT" not in codes:
        codes.append("RC-FLG-LATE-REPORT")
    if facts.get("flag.excessive_claim_history") and "RC-FRD-EXCESSIVE" not in codes:
        codes.append("RC-FRD-EXCESSIVE")
    if facts.get("flag.pre_existing_damage") and "RC-FLG-PREEXISTING" not in codes:
        codes.append("RC-FLG-PREEXISTING")
    if facts.get("screening.siu_referral") and "RC-SIU-REFERRAL" not in codes:
        codes.append("RC-SIU-REFERRAL")
    if not facts.get("claim.occurred_during_policy") and "RC-POL-OUTSIDE-PERIOD" not in codes:
        codes.append("RC-POL-OUTSIDE-PERIOD")
    if facts.get("claim.amount_band") == "over_500k" and "RC-CLM-HIGH-VALUE" not in codes:
        codes.append("RC-CLM-HIGH-VALUE")

    return list(dict.fromkeys(codes))


# v1 outcome backward compatibility mapping
_DISPOSITION_TO_V1 = {
    "PAY_CLAIM": "pay",
    "PARTIAL_PAY": "pay",
    "INVESTIGATE": "escalate",
    "REFER_SIU": "escalate",
    "DENY_CLAIM": "deny",
}


# ---------------------------------------------------------------------------
# Seed builder
# ---------------------------------------------------------------------------

def _build_anchor_facts(facts: dict, idx: int) -> list[AnchorFact]:
    """Turn a flat dict into AnchorFact list."""
    result = []
    for field_id, value in facts.items():
        label = INSURANCE_FIELDS[field_id]["display_name"] if field_id in INSURANCE_FIELDS else field_id
        result.append(AnchorFact(field_id=field_id, value=value, label=label))
    return result


def _generate_seed(
    scenario: dict,
    variation: int,
    rng: random.Random,
    salt: str = SEED_SALT,
) -> JudgmentPayload:
    """Generate one seed with ALL 24 fields populated."""
    facts: dict[str, Any] = {}

    # 1. Set base facts from scenario
    for field_name, value in scenario["base_facts"].items():
        facts[field_name] = value

    # 2. Fill ALL remaining fields with realistic random values
    for field_name, field_def in INSURANCE_FIELDS.items():
        if field_name not in facts:
            facts[field_name] = _random_realistic_value(field_name, field_def, scenario, rng)

    # 3. Validate every field
    for field_name, value in facts.items():
        if field_name in INSURANCE_FIELDS:
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

    # -- Regime tagging (B1.1) --
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

    # v1 backward compat: map insurance disposition to pay/deny/escalate
    outcome_code_v1 = _DISPOSITION_TO_V1.get(scenario["outcome"]["disposition"], "escalate")

    # Map decision level to JudgmentPayload-valid level
    raw_level = scenario.get("decision_level", "adjuster")
    valid_level = _DECISION_LEVEL_MAP.get(raw_level, "adjuster")

    return JudgmentPayload(
        precedent_id=precedent_id,
        case_id_hash=case_id_hash,
        jurisdiction_code="CA",
        fingerprint_hash=fingerprint_hash,
        fingerprint_schema_id=schema_id,
        exclusion_codes=list(signal_codes),
        reason_codes=list(reason_codes),
        reason_code_registry_id="decisiongraph:insurance:reason_codes:v1",
        outcome_code=outcome_code_v1,
        certainty="high",
        anchor_facts=anchor_facts,
        policy_pack_hash=POLICY_PACK_HASH,
        policy_pack_id=POLICY_PACK_ID,
        policy_version=POLICY_VERSION,
        decision_level=valid_level,
        decided_at=decided_at,
        decided_by_role="claims_adjuster",
        source_type="seed",
        scenario_code=scenario["name"],
        seed_category="insurance",
        disposition_basis=scenario["outcome"]["disposition_basis"],
        reporting_obligation=scenario["outcome"]["reporting"],
        domain="insurance",
        signal_codes=list(signal_codes),
        decision_drivers=scenario.get("decision_drivers", []),
        driver_typology=scenario.get("driver_typology", ""),
        policy_regime=policy_regime,
    )


# ---------------------------------------------------------------------------
# Noise: minority-outcome variants (~10%)
# ---------------------------------------------------------------------------

_NOISE_OUTCOMES: dict[str, dict] = {
    "property_fire_arson": {
        "outcome": {"disposition": "PAY_CLAIM", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "senior_adjuster",
    },
    "health_preexisting": {
        "outcome": {"disposition": "PAY_CLAIM", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "examiner",
    },
    "cgl_liability": {
        "outcome": {"disposition": "PAY_CLAIM", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "senior_adjuster",
    },
    "high_value_claim": {
        "outcome": {"disposition": "PAY_CLAIM", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "claims_manager",
    },
    "late_reporting_suspicious": {
        "outcome": {"disposition": "DENY_CLAIM", "disposition_basis": "DISCRETIONARY", "reporting": "FRAUD_REPORT"},
        "decision_level": "claims_manager",
    },
    "siu_referral_pattern": {
        "outcome": {"disposition": "DENY_CLAIM", "disposition_basis": "DISCRETIONARY", "reporting": "FRAUD_REPORT"},
        "decision_level": "claims_manager",
    },
    "auto_impairment_deny": {
        "outcome": {"disposition": "INVESTIGATE", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "examiner",
    },
    "property_vacancy_deny": {
        "outcome": {"disposition": "INVESTIGATE", "disposition_basis": "DISCRETIONARY", "reporting": "NO_FILING"},
        "decision_level": "examiner",
    },
}


def generate_all_insurance_seeds(
    salt: str = SEED_SALT,
    random_seed: int = 42,
    total: int = TOTAL_SEEDS,
) -> list[JudgmentPayload]:
    """Generate all insurance seed precedents.

    Returns ~1,600 JudgmentPayload objects covering all 20 insurance claims
    scenarios with full 24-field coverage.
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
                    "decision_level": noise.get("decision_level", scenario.get("decision_level", "adjuster")),
                }
                seeds.append(_generate_seed(noisy_scenario, i, rng, salt))
            else:
                seeds.append(_generate_seed(scenario, i, rng, salt))

    # -- Post-shift seeds (B1.1) --
    post_shift = _generate_post_shift_seeds(seeds, rng, salt)
    seeds.extend(post_shift)

    return seeds


# ---------------------------------------------------------------------------
# Post-shift seed generation (B1.1)
# ---------------------------------------------------------------------------

_V1_TO_DISPOSITION_INV = {
    "pay": "PAY_CLAIM",
    "escalate": "INVESTIGATE",
    "deny": "DENY_CLAIM",
}


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
                old_outcome.get("disposition", "INVESTIGATE"),
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

            # Map new_level through the decision-level map
            valid_new_level = _DECISION_LEVEL_MAP.get(new_level, new_level)

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
                decision_level=valid_new_level,
                decided_at=new_decided_at,
                decided_by_role=base.decided_by_role,
                source_type="seed",
                scenario_code=base.scenario_code,
                seed_category="insurance_post_shift",
                disposition_basis=new_outcome.get(
                    "disposition_basis", base.disposition_basis,
                ),
                reporting_obligation=new_outcome.get(
                    "reporting", base.reporting_obligation,
                ),
                domain="insurance",
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


def create_auto_claims_seed_config():
    return None

def create_property_claims_seed_config():
    return None

def create_liability_claims_seed_config():
    return None

def create_health_claims_seed_config():
    return None

def create_fraud_investigation_seed_config():
    return None


__all__ = [
    "SeedGeneratorError",
    "SeedConfigError",
    "SeedLoadError",
    "SeedScenario",
    "SeedConfig",
    "SeedGenerator",
    "create_auto_claims_seed_config",
    "create_property_claims_seed_config",
    "create_liability_claims_seed_config",
    "create_health_claims_seed_config",
    "create_fraud_investigation_seed_config",
    "generate_all_insurance_seeds",
    "SCENARIOS",
    "SEED_SALT",
    "TOTAL_SEEDS",
    "COVERAGE_LINES",
    "AMOUNT_BANDS",
]
