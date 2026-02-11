"""
Insurance Claims Field Registry — Single source of truth for all field names,
types, values, and display labels across the insurance claims pipeline.

Modeled on banking_aml/field_registry.py.  All 24 fields use canonical
dot-path names consumed by the v3 precedent scorer.

The registry maps three naming worlds:
  1. website_name  - field_id as defined in YAML templates (what the form sends)
  2. canonical     - internal dot-path used inside seeds and the scorer
  3. display_name  - human-readable label for evidence tables and reports
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Master field registry
# ---------------------------------------------------------------------------

INSURANCE_FIELDS: dict[str, dict[str, Any]] = {

    # === CLAIM STRUCTURAL ===
    "claim.coverage_line": {
        "website_name": "claim.coverage_line",
        "display_name": "Coverage line",
        "type": "enum",
        "values": [
            "auto", "property", "health", "workers_comp",
            "cgl", "eo", "marine", "travel",
        ],
        "website_values": {
            "auto": "auto",
            "automobile": "auto",
            "property": "property",
            "homeowners": "property",
            "health": "health",
            "medical": "health",
            "workers_comp": "workers_comp",
            "wsib": "workers_comp",
            "cgl": "cgl",
            "commercial_general_liability": "cgl",
            "eo": "eo",
            "errors_omissions": "eo",
            "marine": "marine",
            "pleasure_craft": "marine",
            "travel": "travel",
        },
        "fingerprint": True,
        "required": True,
    },
    "claim.amount_band": {
        "website_name": "claim.amount_band",
        "display_name": "Claim amount range",
        "type": "enum",
        "values": ["under_5k", "5k_25k", "25k_100k", "100k_500k", "over_500k"],
        "website_values": {
            "under_5k": "under_5k",
            "5k_25k": "5k_25k",
            "25k_100k": "25k_100k",
            "100k_500k": "100k_500k",
            "over_500k": "over_500k",
            "100k_plus": "100k_500k",
        },
        "fingerprint": True,
        "required": True,
    },
    "claim.claimant_type": {
        "website_name": "claim.claimant_type",
        "display_name": "Claimant type",
        "type": "enum",
        "values": ["first_party", "third_party"],
        "website_values": {
            "first_party": "first_party",
            "third_party": "third_party",
            "1st_party": "first_party",
            "3rd_party": "third_party",
        },
        "fingerprint": True,
        "required": True,
    },

    # === RED FLAGS ===
    "flag.fraud_indicator": {
        "website_name": "flag.fraud_indicator",
        "display_name": "Fraud indicator present",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "flag.prior_claims_frequency": {
        "website_name": "flag.prior_claims_frequency",
        "display_name": "Prior claims frequency",
        "type": "enum",
        "values": ["none", "low", "moderate", "high"],
        "website_values": {
            "none": "none", "0": "none",
            "low": "low", "1": "low",
            "moderate": "moderate", "2-3": "moderate",
            "high": "high", "4_plus": "high",
        },
        "fingerprint": True,
        "required": True,
    },
    "flag.late_reporting": {
        "website_name": "flag.late_reporting",
        "display_name": "Late reporting indicator",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "flag.inconsistent_statements": {
        "website_name": "flag.inconsistent_statements",
        "display_name": "Inconsistent statements indicator",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "flag.staged_accident": {
        "website_name": "flag.staged_accident",
        "display_name": "Staged accident indicator",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "flag.excessive_claim_history": {
        "website_name": "flag.excessive_claim_history",
        "display_name": "Excessive claim history",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "flag.pre_existing_damage": {
        "website_name": "flag.pre_existing_damage",
        "display_name": "Pre-existing damage indicator",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },

    # === EVIDENCE ===
    "evidence.police_report": {
        "website_name": "evidence.police_report",
        "display_name": "Police report available",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "evidence.medical_report": {
        "website_name": "evidence.medical_report",
        "display_name": "Medical report available",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "evidence.witness_statements": {
        "website_name": "evidence.witness_statements",
        "display_name": "Witness statements available",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "evidence.photos_documentation": {
        "website_name": "evidence.photos_documentation",
        "display_name": "Photos / documentation available",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },

    # === POLICY ===
    "policy.deductible_band": {
        "website_name": "policy.deductible_band",
        "display_name": "Deductible band",
        "type": "enum",
        "values": ["low", "medium", "high"],
        "website_values": {
            "low": "low", "under_500": "low",
            "medium": "medium", "500_2000": "medium",
            "high": "high", "over_2000": "high",
        },
        "fingerprint": True,
        "required": True,
    },
    "policy.coverage_limit_band": {
        "website_name": "policy.coverage_limit_band",
        "display_name": "Coverage limit band",
        "type": "enum",
        "values": ["basic", "standard", "premium", "excess"],
        "website_values": {
            "basic": "basic",
            "standard": "standard",
            "premium": "premium",
            "excess": "excess",
        },
        "fingerprint": True,
        "required": True,
    },
    "policy.policy_age": {
        "website_name": "policy.policy_age",
        "display_name": "Policy age",
        "type": "enum",
        "values": ["new", "established", "mature"],
        "website_values": {
            "new": "new", "lt_1yr": "new",
            "established": "established", "1_5yr": "established",
            "mature": "mature", "gt_5yr": "mature",
        },
        "fingerprint": True,
        "required": True,
    },

    # === CONTEXTUAL ===
    "claim.injury_type": {
        "website_name": "claim.injury_type",
        "display_name": "Injury severity type",
        "type": "enum",
        "values": ["minor", "moderate", "serious", "catastrophic"],
        "website_values": {
            "minor": "minor",
            "moderate": "moderate",
            "serious": "serious",
            "catastrophic": "catastrophic",
            "none": "minor",
        },
        "fingerprint": True,
        "required": False,
    },
    "claim.loss_cause": {
        "website_name": "claim.loss_cause",
        "display_name": "Loss cause",
        "type": "enum",
        "values": [
            "collision", "theft", "fire", "water", "wind",
            "vandalism", "liability", "other",
        ],
        "website_values": {
            "collision": "collision",
            "theft": "theft",
            "fire": "fire",
            "water": "water",
            "wind": "wind",
            "vandalism": "vandalism",
            "liability": "liability",
            "other": "other",
        },
        "fingerprint": True,
        "required": False,
    },
    "claim.time_to_report": {
        "website_name": "claim.time_to_report",
        "display_name": "Time to report",
        "type": "enum",
        "values": ["immediate", "within_week", "within_month", "delayed"],
        "website_values": {
            "immediate": "immediate", "0_2_days": "immediate",
            "within_week": "within_week", "3_7_days": "within_week",
            "within_month": "within_month", "8_30_days": "within_month",
            "delayed": "delayed", "over_30_days": "delayed",
        },
        "fingerprint": True,
        "required": True,
    },
    "claim.occurred_during_policy": {
        "website_name": "claim.occurred_during_policy",
        "display_name": "Loss occurred during policy period",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },

    # === SCREENING ===
    "screening.siu_referral": {
        "website_name": "screening.siu_referral",
        "display_name": "SIU referral flag",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "prior.claims_denied": {
        "website_name": "prior.claims_denied",
        "display_name": "Prior claims denied count",
        "type": "enum",
        "values": [0, 1, 2, 3, 4],
        "website_values": {
            "0": 0, "1": 1, "2": 2, "3": 3, "4_plus": 4,
        },
        "fingerprint": True,
        "required": True,
    },
}


# ---------------------------------------------------------------------------
# Insurance-domain outcome vocabulary
# ---------------------------------------------------------------------------

INSURANCE_DISPOSITIONS = {"PAY_CLAIM", "PARTIAL_PAY", "INVESTIGATE", "REFER_SIU", "DENY_CLAIM"}
INSURANCE_REPORTING = {"NO_FILING", "FSRA_NOTICE", "FRAUD_REPORT"}
INSURANCE_BASIS = {"MANDATORY", "DISCRETIONARY"}
INSURANCE_DECISION_LEVELS = {
    "adjuster", "senior_adjuster", "examiner",
    "supervisor", "siu_investigator", "claims_manager",
}


# ---------------------------------------------------------------------------
# Derived helpers
# ---------------------------------------------------------------------------

def get_website_to_canonical_map() -> dict[str, str]:
    """Returns {website_field_name: canonical_internal_name}."""
    return {
        field["website_name"]: canonical
        for canonical, field in INSURANCE_FIELDS.items()
    }


def get_canonical_to_display_map() -> dict[str, str]:
    """Returns {canonical_name: human_readable_display_name}."""
    return {
        canonical: field["display_name"]
        for canonical, field in INSURANCE_FIELDS.items()
    }


def get_fingerprint_fields() -> list[str]:
    """Returns list of canonical field names used for fingerprint hashing."""
    return [
        name for name, field in INSURANCE_FIELDS.items()
        if field.get("fingerprint", False)
    ]


def normalize_website_value(canonical_name: str, website_value: Any) -> Any:
    """Convert a website display / form value to the internal canonical value."""
    field = INSURANCE_FIELDS.get(canonical_name)
    if not field:
        raise ValueError(f"Unknown field: {canonical_name}")
    if field["type"] == "boolean":
        if isinstance(website_value, bool):
            return website_value
        return str(website_value).lower() in ("yes", "true", "1")
    if "website_values" in field:
        normalized = field["website_values"].get(str(website_value))
        if normalized is not None:
            return normalized
    return website_value


def validate_field_value(canonical_name: str, value: Any) -> bool:
    """Validate a value against the registry. Returns True or raises."""
    field = INSURANCE_FIELDS.get(canonical_name)
    if not field:
        raise ValueError(f"Unknown field: {canonical_name}")
    if field["type"] == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{canonical_name}: expected bool, got {type(value).__name__}")
    elif field["type"] == "enum":
        if value not in field["values"]:
            raise ValueError(
                f"{canonical_name}: '{value}' not in {field['values']}"
            )
    return True


def normalize_facts_from_website(website_facts: dict[str, Any]) -> dict[str, Any]:
    """Convert a dict of website-form facts to canonical seed-style facts."""
    w2c = get_website_to_canonical_map()
    canonical: dict[str, Any] = {}

    for website_name, value in website_facts.items():
        field_canonical = w2c.get(website_name)
        if field_canonical is None:
            canonical[website_name] = value
            continue
        canonical[field_canonical] = normalize_website_value(field_canonical, value)

    return canonical


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "INSURANCE_FIELDS",
    "INSURANCE_DISPOSITIONS",
    "INSURANCE_REPORTING",
    "INSURANCE_BASIS",
    "INSURANCE_DECISION_LEVELS",
    "get_website_to_canonical_map",
    "get_canonical_to_display_map",
    "get_fingerprint_fields",
    "normalize_website_value",
    "validate_field_value",
    "normalize_facts_from_website",
]
