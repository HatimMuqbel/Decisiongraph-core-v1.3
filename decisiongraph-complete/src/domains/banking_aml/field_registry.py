"""
Banking Field Registry - Single source of truth for all field names,
types, values, and display labels across the entire pipeline.

Website (YAML template) -> API -> Seeds -> Fingerprint -> Scorer -> Evidence Table
All use THIS registry. No hardcoded field lists anywhere else.

The registry maps three naming worlds:
  1. website_name  - field_id as defined in dg_txn_monitoring.yaml (what the form sends)
  2. canonical     - internal dot-path used inside seeds and the scorer
  3. display_name  - human-readable label for evidence tables and reports

When a field's website_name differs from its canonical name, template_loader.py
normalizes incoming facts before they reach the scorer.  The seed generator
always uses canonical names directly.
"""

from __future__ import annotations

from typing import Any, Optional


# ---------------------------------------------------------------------------
# Master field registry
# ---------------------------------------------------------------------------
# Keys are the CANONICAL internal field names used in seeds and the scorer.
# website_name is the field_id as it arrives from the YAML template / form.
# website_values maps UI option labels -> internal canonical values.

BANKING_FIELDS: dict[str, dict[str, Any]] = {

    # === CUSTOMER ===
    "customer.type": {
        "website_name": "customer.type",
        "display_name": "Customer entity type",
        "type": "enum",
        "values": ["individual", "corporation"],
        "website_values": {
            "individual": "individual",
            "sole_prop": "individual",
            "corporation": "corporation",
            "partnership": "corporation",
            "trust": "corporation",
            "non_profit": "corporation",
        },
        "fingerprint": True,
        "required": True,
    },
    "customer.relationship_length": {
        "website_name": "customer.relationship_length",
        "display_name": "Customer relationship duration",
        "type": "enum",
        "values": ["new", "recent", "established"],
        "website_values": {
            "new_lt_6mo": "new",
            "established_6mo_2yr": "recent",
            "long_term_2yr_plus": "established",
        },
        "fingerprint": True,
        "required": True,
    },

    # === RISK PROFILE ===
    "customer.pep": {
        "website_name": "risk.pep",
        "display_name": "Politically Exposed Person status",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "customer.high_risk_jurisdiction": {
        "website_name": "risk.high_risk_jurisdiction",
        "display_name": "High-risk jurisdiction indicator",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "customer.high_risk_industry": {
        "website_name": "risk.high_risk_industry",
        "display_name": "High-risk industry indicator",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "customer.cash_intensive": {
        "website_name": "risk.cash_intensive_business",
        "display_name": "Cash-intensive business indicator",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },

    # === TRANSACTION ===
    "txn.type": {
        "website_name": "txn.type",
        "display_name": "Transaction type",
        "type": "enum",
        "values": [
            "wire_domestic", "wire_international", "cash",
            "cheque", "eft", "crypto",
        ],
        "website_values": {
            "wire_transfer": "wire_domestic",
            "cash_deposit": "cash",
            "cash_withdrawal": "cash",
            "check": "cheque",
            "ach_eft": "eft",
            "crypto_purchase": "crypto",
            "crypto_sale": "crypto",
            "international_transfer": "wire_international",
        },
        "fingerprint": True,
        "required": True,
    },
    "txn.amount_band": {
        "website_name": "txn.amount_band",
        "display_name": "Transaction amount range",
        "type": "enum",
        "values": [
            "under_3k", "3k_10k", "10k_25k",
            "25k_100k", "100k_500k", "500k_1m", "over_1m",
        ],
        "website_values": {
            "under_3k": "under_3k",
            "3k_10k": "3k_10k",
            "10k_25k": "10k_25k",
            "25k_100k": "25k_100k",
            "100k_plus": "100k_500k",
        },
        "fingerprint": True,
        "required": True,
    },
    "txn.cross_border": {
        "website_name": "txn.cross_border",
        "display_name": "Cross-border transaction indicator",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "txn.destination_country_risk": {
        "website_name": "txn.destination_country",
        "display_name": "Destination country risk level",
        "type": "enum",
        "values": ["low", "medium", "high"],
        "website_values": {
            "canada": "low",
            "usa": "low",
            "uk": "low",
            "high_risk_country": "high",
        },
        "fingerprint": True,
        "required": True,
    },
    "txn.round_amount": {
        "website_name": "txn.round_amount",
        "display_name": "Round amount indicator",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "txn.just_below_threshold": {
        "website_name": "txn.just_below_10k",
        "display_name": "Transaction just below reporting threshold",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "txn.multiple_same_day": {
        "website_name": "txn.multiple_same_day_txns",
        "display_name": "Multiple same-day transactions",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "txn.pattern_matches_profile": {
        "website_name": "txn.pattern_matches_profile",
        "display_name": "Transaction pattern consistent with customer profile",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "txn.source_of_funds_clear": {
        "website_name": "txn.source_of_funds_clear",
        "display_name": "Source of funds clarity",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "txn.stated_purpose": {
        "website_name": "txn.stated_purpose",
        "display_name": "Stated transaction purpose",
        "type": "enum",
        "values": ["personal", "business", "investment", "gift", "unclear"],
        "website_values": {
            "personal": "personal",
            "business": "business",
            "investment": "investment",
            "gift": "gift",
            "unclear": "unclear",
        },
        "fingerprint": True,
        "required": True,
    },

    # === RED FLAGS ===
    "flag.structuring": {
        "website_name": "flag.structuring_suspected",
        "display_name": "Structuring indicators present",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "flag.rapid_movement": {
        "website_name": "flag.rapid_movement",
        "display_name": "Rapid fund movement indicator",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "flag.layering": {
        "website_name": "flag.layering_indicators",
        "display_name": "Layering indicators present",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "flag.unusual_for_profile": {
        "website_name": "flag.unusual_for_profile",
        "display_name": "Activity unusual for customer profile",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "flag.third_party": {
        "website_name": "flag.third_party_payment",
        "display_name": "Third-party payment indicator",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "flag.shell_company": {
        "website_name": "flag.shell_company_indicators",
        "display_name": "Shell company indicators present",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },

    # === SCREENING ===
    "screening.sanctions_match": {
        "website_name": "screen.sanctions_match",
        "display_name": "Sanctions screening match",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "screening.pep_match": {
        "website_name": "screen.pep_match",
        "display_name": "PEP screening match",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "screening.adverse_media": {
        "website_name": "screen.adverse_media",
        "display_name": "Adverse media indicator",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "prior.sars_filed": {
        "website_name": "screen.prior_sars_filed",
        "display_name": "Prior Suspicious Activity Reports filed",
        "type": "enum",
        "values": [0, 1, 2, 3, 4],
        "website_values": {
            "0": 0,
            "1": 1,
            "2": 2,
            "3": 3,
            "4_plus": 4,
        },
        "fingerprint": True,
        "required": True,
    },
    "prior.account_closures": {
        "website_name": "screen.previous_account_closures",
        "display_name": "Previous account closures on record",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
}


# ---------------------------------------------------------------------------
# Banking-domain outcome vocabulary
# ---------------------------------------------------------------------------

BANKING_DISPOSITIONS = {"ALLOW", "EDD", "BLOCK"}
BANKING_REPORTING = {"NO_REPORT", "FILE_STR", "FILE_LCTR", "FILE_TPR", "PENDING_EDD"}
BANKING_BASIS = {"MANDATORY", "DISCRETIONARY"}
BANKING_DECISION_LEVELS = {"analyst", "senior_analyst", "manager", "cco", "senior_management"}


# ---------------------------------------------------------------------------
# Derived helpers
# ---------------------------------------------------------------------------

def get_website_to_canonical_map() -> dict[str, str]:
    """Returns {website_field_name: canonical_internal_name}."""
    return {
        field["website_name"]: canonical
        for canonical, field in BANKING_FIELDS.items()
    }


def get_canonical_to_display_map() -> dict[str, str]:
    """Returns {canonical_name: human_readable_display_name}."""
    return {
        canonical: field["display_name"]
        for canonical, field in BANKING_FIELDS.items()
    }


def get_fingerprint_fields() -> list[str]:
    """Returns list of canonical field names used for fingerprint hashing."""
    return [
        name for name, field in BANKING_FIELDS.items()
        if field.get("fingerprint", False)
    ]


def normalize_website_value(canonical_name: str, website_value: Any) -> Any:
    """Convert a website display / form value to the internal canonical value."""
    field = BANKING_FIELDS.get(canonical_name)
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
    field = BANKING_FIELDS.get(canonical_name)
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
    """Convert a dict of website-form facts to canonical seed-style facts.

    Handles all the normalization currently duplicated in template_loader.py:
      - customer.type grouping (sole_prop -> individual, partnership -> corporation)
      - customer.pep aliasing from risk.pep / screen.pep_match
      - relationship_length shortening
      - screen.* -> screening.* namespace
      - txn.destination_country -> txn.destination_country_risk derivation
      - txn.amount_band 100k_plus -> 100k_500k
      - txn.type grouping (cash_deposit -> cash, crypto_purchase -> crypto, etc.)
      - wire_transfer conditional split by cross_border
    """
    w2c = get_website_to_canonical_map()
    canonical: dict[str, Any] = {}

    for website_name, value in website_facts.items():
        field_canonical = w2c.get(website_name)
        if field_canonical is None:
            # Pass through any unrecognised field as-is (e.g. gate flags)
            canonical[website_name] = value
            continue
        canonical[field_canonical] = normalize_website_value(field_canonical, value)

    # --- txn.type conditional split: wire_transfer + cross_border ---
    if website_facts.get("txn.type") == "wire_transfer":
        if canonical.get("txn.cross_border") in (True, "true", "True", "yes"):
            canonical["txn.type"] = "wire_international"
        else:
            canonical["txn.type"] = "wire_domestic"

    return canonical


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "BANKING_FIELDS",
    "BANKING_DISPOSITIONS",
    "BANKING_REPORTING",
    "BANKING_BASIS",
    "BANKING_DECISION_LEVELS",
    "get_website_to_canonical_map",
    "get_canonical_to_display_map",
    "get_fingerprint_fields",
    "normalize_website_value",
    "validate_field_value",
    "normalize_facts_from_website",
]
