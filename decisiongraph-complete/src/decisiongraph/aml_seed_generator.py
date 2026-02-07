"""
DecisionGraph Banking/AML Seed Generator — Demo Edition

Generates seed precedents for the precedent intelligence system.
Each scenario is a resolved case type with explicit v2 outcome fields.

Design philosophy: these are the bank's historical resolved cases.
Simple data, explicit outcomes, no mapping layers.

All seeds comply with v2 three-field canonicalization
(see docs/PRECEDENT_OUTCOME_MODEL_V2.md):
  disposition:       ALLOW | EDD | BLOCK
  disposition_basis: MANDATORY | DISCRETIONARY
  reporting:         NO_REPORT | FILE_STR | FILE_LCTR | FILE_TPR

Total: ~4,000 seeds across 5 schema families.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from .judgment import JudgmentPayload, AnchorFact


# ─── Amount bands and channels for variety across copies ──────────────────

AMOUNT_BANDS = ["under_10k", "10k_50k", "50k_100k", "100k_500k", "over_500k"]
CHANNELS = ["wire", "cash", "eft", "cheque", "crypto"]


# ─── Schema selection (mirrors service/main.py _select_schema_id_for_codes) ──

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


# ─── The scenarios ───────────────────────────────────────────────────────────
# Each dict = one type of resolved case from the bank's history.
# Fields:
#   name      — human label (becomes scenario_code)
#   codes     — reason codes (determines schema + matching overlap)
#   outcome   — pay | deny | escalate  (valid JudgmentPayload codes)
#   basis     — MANDATORY | DISCRETIONARY
#   reporting — NO_REPORT | FILE_STR | FILE_LCTR | FILE_TPR
#   facts     — anchor facts for similarity scoring
#   count     — how many historical cases of this type

SCENARIOS = [
    # ━━━ TXN: Normal transactions ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {
        "name": "normal_approved",
        "codes": ["RC-TXN-NORMAL", "RC-TXN-PROFILE-MATCH"],
        "outcome": "pay",
        "basis": "DISCRETIONARY",
        "reporting": "NO_REPORT",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "customer.relationship_length": "established",
            "screening.sanctions_match": False,
            "txn.cross_border": False,
            "txn.destination_country_risk": "low",
        },
        "count": 400,
    },
    {
        "name": "normal_approved_corporate",
        "codes": ["RC-TXN-NORMAL", "RC-TXN-PROFILE-MATCH"],
        "outcome": "pay",
        "basis": "DISCRETIONARY",
        "reporting": "NO_REPORT",
        "facts": {
            "customer.type": "corporation",
            "customer.pep": False,
            "customer.relationship_length": "established",
            "screening.sanctions_match": False,
            "txn.cross_border": False,
            "txn.destination_country_risk": "low",
        },
        "count": 200,
    },

    # ━━━ TXN: Structuring ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {
        "name": "structuring_blocked_str",
        "codes": ["RC-TXN-STRUCT", "RC-TXN-STRUCT-MULTI"],
        "outcome": "deny",
        "basis": "DISCRETIONARY",
        "reporting": "FILE_STR",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "screening.sanctions_match": False,
            "txn.cross_border": False,
        },
        "count": 150,
    },
    {
        "name": "structuring_edd",
        "codes": ["RC-TXN-STRUCT", "RC-TXN-STRUCT-MULTI"],
        "outcome": "escalate",
        "basis": "DISCRETIONARY",
        "reporting": "NO_REPORT",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "screening.sanctions_match": False,
        },
        "count": 100,
    },

    # ━━━ TXN: PEP ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {
        "name": "pep_approved",
        "codes": ["RC-TXN-PEP", "RC-TXN-PEP-EDD"],
        "outcome": "pay",
        "basis": "DISCRETIONARY",
        "reporting": "NO_REPORT",
        "facts": {
            "customer.type": "individual",
            "customer.pep": True,
            "customer.relationship_length": "established",
            "screening.sanctions_match": False,
            "txn.destination_country_risk": "low",
        },
        "count": 200,
    },
    {
        "name": "pep_edd",
        "codes": ["RC-TXN-PEP", "RC-TXN-PEP-EDD"],
        "outcome": "escalate",
        "basis": "DISCRETIONARY",
        "reporting": "NO_REPORT",
        "facts": {
            "customer.type": "individual",
            "customer.pep": True,
            "customer.relationship_length": "new",
            "screening.sanctions_match": False,
            "txn.destination_country_risk": "medium",
        },
        "count": 200,
    },
    {
        "name": "pep_blocked_str",
        "codes": ["RC-TXN-PEP", "RC-TXN-PEP-EDD"],
        "outcome": "deny",
        "basis": "DISCRETIONARY",
        "reporting": "FILE_STR",
        "facts": {
            "customer.type": "individual",
            "customer.pep": True,
            "customer.relationship_length": "new",
            "screening.sanctions_match": False,
            "txn.destination_country_risk": "high",
        },
        "count": 100,
    },

    # ━━━ TXN: Large cash + LCTR ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {
        "name": "large_cash_lctr",
        "codes": ["RC-TXN-NORMAL", "RC-TXN-PROFILE-MATCH"],
        "outcome": "pay",
        "basis": "DISCRETIONARY",
        "reporting": "FILE_LCTR",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "screening.sanctions_match": False,
            "txn.type": "cash",
            "txn.amount_band": "10k_50k",
            "txn.cross_border": False,
        },
        "count": 200,
    },

    # ━━━ TXN: FATF high-risk jurisdiction ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {
        "name": "fatf_grey_blocked",
        "codes": ["RC-TXN-FATF-GREY"],
        "outcome": "deny",
        "basis": "DISCRETIONARY",
        "reporting": "FILE_STR",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "screening.sanctions_match": False,
            "txn.cross_border": True,
            "txn.destination_country_risk": "high",
        },
        "count": 100,
    },
    {
        "name": "fatf_grey_edd",
        "codes": ["RC-TXN-FATF-GREY"],
        "outcome": "escalate",
        "basis": "DISCRETIONARY",
        "reporting": "NO_REPORT",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "screening.sanctions_match": False,
            "txn.cross_border": True,
            "txn.destination_country_risk": "high",
        },
        "count": 150,
    },

    # ━━━ TXN: Layering / Rapid movement ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {
        "name": "layering_blocked_str",
        "codes": ["RC-TXN-LAYER", "RC-TXN-RAPID"],
        "outcome": "deny",
        "basis": "DISCRETIONARY",
        "reporting": "FILE_STR",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "screening.sanctions_match": False,
        },
        "count": 100,
    },
    {
        "name": "layering_edd",
        "codes": ["RC-TXN-LAYER", "RC-TXN-RAPID"],
        "outcome": "escalate",
        "basis": "DISCRETIONARY",
        "reporting": "NO_REPORT",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "screening.sanctions_match": False,
        },
        "count": 100,
    },

    # ━━━ TXN: Crypto ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {
        "name": "crypto_edd",
        "codes": ["RC-TXN-CRYPTO-UNREG", "RC-TXN-CRYPTO-UNHOSTED"],
        "outcome": "escalate",
        "basis": "DISCRETIONARY",
        "reporting": "NO_REPORT",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "screening.sanctions_match": False,
            "txn.type": "crypto",
        },
        "count": 100,
    },
    {
        "name": "crypto_blocked",
        "codes": ["RC-TXN-CRYPTO-UNREG", "RC-TXN-CRYPTO-UNHOSTED"],
        "outcome": "deny",
        "basis": "DISCRETIONARY",
        "reporting": "FILE_STR",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "screening.sanctions_match": False,
            "txn.type": "crypto",
        },
        "count": 50,
    },

    # ━━━ TXN: Unusual activity ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {
        "name": "unusual_edd",
        "codes": ["RC-TXN-UNUSUAL", "RC-TXN-DEVIATION"],
        "outcome": "escalate",
        "basis": "DISCRETIONARY",
        "reporting": "NO_REPORT",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "screening.sanctions_match": False,
        },
        "count": 150,
    },

    # ━━━ KYC: Onboarding & due diligence ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {
        "name": "kyc_pep_approved",
        "codes": ["RC-KYC-PEP-APPROVED", "RC-TXN-PEP"],
        "outcome": "pay",
        "basis": "DISCRETIONARY",
        "reporting": "NO_REPORT",
        "facts": {
            "customer.type": "individual",
            "customer.pep": True,
            "customer.relationship_length": "established",
            "screening.sanctions_match": False,
        },
        "count": 200,
    },
    {
        "name": "kyc_adverse_minor",
        "codes": ["RC-KYC-ADVERSE-MINOR"],
        "outcome": "escalate",
        "basis": "DISCRETIONARY",
        "reporting": "NO_REPORT",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "screening.sanctions_match": False,
        },
        "count": 100,
    },
    {
        "name": "kyc_adverse_major",
        "codes": ["RC-KYC-ADVERSE-MAJOR"],
        "outcome": "deny",
        "basis": "DISCRETIONARY",
        "reporting": "FILE_STR",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "screening.sanctions_match": False,
        },
        "count": 50,
    },
    {
        "name": "kyc_new_customer",
        "codes": ["RC-KYC-ONBOARD", "RC-KYC-NEW"],
        "outcome": "pay",
        "basis": "DISCRETIONARY",
        "reporting": "NO_REPORT",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "customer.relationship_length": "new",
            "screening.sanctions_match": False,
        },
        "count": 200,
    },

    # ━━━ Screening: Sanctions ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {
        "name": "sanctions_confirmed",
        "codes": ["RC-SCR-SANCTION", "RC-SCR-OFAC"],
        "outcome": "deny",
        "basis": "MANDATORY",
        "reporting": "FILE_STR",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "screening.sanctions_match": True,
        },
        "count": 200,
    },
    {
        "name": "sanctions_false_positive",
        "codes": ["RC-SCR-SANCTION", "RC-SCR-OFAC"],
        "outcome": "pay",
        "basis": "DISCRETIONARY",
        "reporting": "NO_REPORT",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "screening.sanctions_match": False,
        },
        "count": 200,
    },

    # ━━━ Monitoring: Ongoing alerts ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {
        "name": "monitoring_alert_edd",
        "codes": ["RC-MON-ALERT", "RC-MON-UNUSUAL"],
        "outcome": "escalate",
        "basis": "DISCRETIONARY",
        "reporting": "NO_REPORT",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "screening.sanctions_match": False,
        },
        "count": 200,
    },
    {
        "name": "monitoring_velocity",
        "codes": ["RC-MON-VELOCITY", "RC-MON-ALERT"],
        "outcome": "escalate",
        "basis": "DISCRETIONARY",
        "reporting": "NO_REPORT",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "screening.sanctions_match": False,
        },
        "count": 100,
    },

    # ━━━ Reporting: Filed reports ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {
        "name": "str_filed",
        "codes": ["RC-RPT-STR", "RC-RPT-SAR"],
        "outcome": "pay",
        "basis": "DISCRETIONARY",
        "reporting": "FILE_STR",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "screening.sanctions_match": False,
        },
        "count": 100,
    },
    {
        "name": "lctr_filed",
        "codes": ["RC-RPT-LCTR"],
        "outcome": "pay",
        "basis": "DISCRETIONARY",
        "reporting": "FILE_LCTR",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "screening.sanctions_match": False,
            "txn.type": "cash",
        },
        "count": 100,
    },
    {
        "name": "tpr_filed",
        "codes": ["RC-RPT-TPR"],
        "outcome": "deny",
        "basis": "MANDATORY",
        "reporting": "FILE_TPR",
        "facts": {
            "customer.type": "individual",
            "customer.pep": False,
            "screening.sanctions_match": True,
        },
        "count": 50,
    },
]


# ─── Generator ───────────────────────────────────────────────────────────────

def _build_anchor_facts(facts: dict, idx: int) -> list[AnchorFact]:
    """Turn a flat dict into AnchorFact list, adding variety for amount/channel."""
    result = []
    for field_id, value in facts.items():
        result.append(AnchorFact(
            field_id=field_id,
            value=value,
            label=field_id.replace(".", " ").replace("_", " ").title(),
        ))

    # Add amount band variety if not pinned by the scenario
    if "txn.amount_band" not in facts:
        band = AMOUNT_BANDS[idx % len(AMOUNT_BANDS)]
        result.append(AnchorFact(field_id="txn.amount_band", value=band, label="Txn Amount Band"))

    # Add channel variety if not pinned by the scenario
    if "txn.type" not in facts:
        channel = CHANNELS[idx % len(CHANNELS)]
        result.append(AnchorFact(field_id="txn.type", value=channel, label="Txn Type"))

    return result


def _make_seed(scenario: dict, idx: int, salt: str) -> JudgmentPayload:
    """Create one JudgmentPayload from a scenario dict + index."""
    precedent_id = str(uuid4())
    case_id = f"SEED-{scenario['name']}-{idx:04d}"
    case_id_hash = hashlib.sha256(f"{salt}:{case_id}".encode()).hexdigest()

    anchor_facts = _build_anchor_facts(scenario["facts"], idx)
    facts_str = "|".join(f"{af.field_id}={af.value}" for af in anchor_facts)
    fingerprint_hash = hashlib.sha256(f"{salt}:{facts_str}".encode()).hexdigest()

    # Spread decided_at over the last 12 months for recency variety
    days_ago = (idx * 7) % 365
    decided_at = (
        datetime.now(timezone.utc) - timedelta(days=days_ago)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    return JudgmentPayload(
        precedent_id=precedent_id,
        case_id_hash=case_id_hash,
        jurisdiction_code="CA-ON",
        fingerprint_hash=fingerprint_hash,
        fingerprint_schema_id=_schema_for_codes(scenario["codes"]),
        exclusion_codes=list(scenario["codes"]),
        reason_codes=list(scenario["codes"]),
        reason_code_registry_id="decisiongraph:aml:reason_codes:v1",
        outcome_code=scenario["outcome"],
        certainty="high",
        anchor_facts=anchor_facts,
        policy_pack_hash=hashlib.sha256(b"fincrime_canada_v2026").hexdigest()[:16],
        policy_pack_id="fincrime_canada",
        policy_version="2026.02.01",
        decision_level="manager",
        decided_at=decided_at,
        decided_by_role="aml_analyst",
        source_type="seed",
        scenario_code=scenario["name"],
        seed_category="aml",
        disposition_basis=scenario["basis"],
        reporting_obligation=scenario["reporting"],
    )


def generate_all_banking_seeds(
    salt: str = "decisiongraph-banking-seed-v1",
    random_seed: int = 42,
) -> list[JudgmentPayload]:
    """Generate all banking seed precedents.

    Returns ~4,000 JudgmentPayload objects covering every AML
    scenario the BYOC system can produce.
    """
    seeds = []
    for scenario in SCENARIOS:
        for i in range(scenario["count"]):
            seeds.append(_make_seed(scenario, i, salt))
    return seeds


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
]
