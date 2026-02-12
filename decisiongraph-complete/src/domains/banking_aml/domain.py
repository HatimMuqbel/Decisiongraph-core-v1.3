"""
Banking AML Domain Registry — v3 Precedent Engine.

Constructs a DomainRegistry for the banking AML domain by enriching
the existing BANKING_FIELDS with v3 metadata (type, comparison function,
weight, tier, critical flag, equivalence classes).

Spec reference: DecisionGraph_Precedent_Engine_v3_Specification.md
  - Section 4.2: Comparability gate equivalence classes
  - Section 5.2: Field definitions with typed comparison metadata
  - Section 5.6: Similarity floor overrides per typology
  - Appendix C: Banking AML field registry reference
"""

from __future__ import annotations

from functools import lru_cache

from .field_registry import (
    BANKING_FIELDS,
    BANKING_DISPOSITIONS,
    BANKING_REPORTING,
    BANKING_BASIS,
)
from kernel.precedent.domain_registry import (
    ComparisonFn,
    ComparabilityGate,
    DomainRegistry,
    FieldDefinition,
    FieldTier,
    FieldType,
)


# ---------------------------------------------------------------------------
# v3 field metadata — enrichments over BANKING_FIELDS
# ---------------------------------------------------------------------------
# Maps canonical field name -> (FieldType, ComparisonFn, weight, FieldTier, critical, extras)
#
# Weight distribution rationale:
#   v2 had 9 component-level weights (rules_overlap=0.30, gate_match=0.25, ...).
#   v3 distributes weight to individual fields. Fields that were part of high-weight
#   components get proportionally higher weight. Weights are normalized by the
#   engine at scoring time; absolute values express relative importance.
#
# Tier assignment rationale (from spec Appendix C):
#   STRUCTURAL — defines comparability (customer.type, txn.type)
#   BEHAVIORAL — drives similarity scoring as decision drivers (flags, screening)
#   CONTEXTUAL — stabilizes similarity without driving outcomes

_FIELD_ENRICHMENTS: dict[str, dict] = {
    # --- CUSTOMER ---
    "customer.type": {
        "type": FieldType.CATEGORICAL,
        "comparison": ComparisonFn.EQUIVALENCE_CLASS,
        "weight": 0.05,
        "tier": FieldTier.STRUCTURAL,
        "critical": True,
        "equivalence_classes": {
            "retail": ["individual", "personal", "retail"],
            "corporate": ["corporation", "institutional", "company"],
        },
    },
    "customer.relationship_length": {
        "type": FieldType.ORDINAL,
        "comparison": ComparisonFn.STEP,
        "weight": 0.03,
        "tier": FieldTier.CONTEXTUAL,
        "ordered_values": ["new", "recent", "established"],
    },

    # --- RISK PROFILE ---
    "customer.pep": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.05,
        "tier": FieldTier.BEHAVIORAL,
    },
    "customer.high_risk_jurisdiction": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.04,
        "tier": FieldTier.BEHAVIORAL,
    },
    "customer.high_risk_industry": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.03,
        "tier": FieldTier.BEHAVIORAL,
    },
    "customer.cash_intensive": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.02,
        "tier": FieldTier.CONTEXTUAL,
    },

    # --- TRANSACTION ---
    "txn.type": {
        "type": FieldType.CATEGORICAL,
        "comparison": ComparisonFn.EQUIVALENCE_CLASS,
        "weight": 0.07,
        "tier": FieldTier.STRUCTURAL,
        "critical": True,
        "equivalence_classes": {
            "cash": ["cash", "cash_deposit", "cash_withdrawal"],
            "electronic": ["wire_domestic", "wire_international", "eft", "ach", "swift", "domestic_wire"],
            "crypto": ["crypto", "virtual_currency", "digital_asset", "crypto_purchase", "crypto_sale"],
            "cheque": ["cheque", "check"],
            "trade": ["trade_finance", "lc", "documentary_credit"],
        },
    },
    "txn.amount_band": {
        "type": FieldType.ORDINAL,
        "comparison": ComparisonFn.STEP,
        "weight": 0.10,
        "tier": FieldTier.BEHAVIORAL,
        "critical": True,
        "ordered_values": [
            "under_3k", "3k_10k", "10k_25k", "25k_100k",
            "100k_500k", "500k_1m", "over_1m",
        ],
    },
    "txn.cross_border": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.06,
        "tier": FieldTier.BEHAVIORAL,
    },
    "txn.destination_country_risk": {
        "type": FieldType.ORDINAL,
        "comparison": ComparisonFn.STEP,
        "weight": 0.05,
        "tier": FieldTier.BEHAVIORAL,
        "ordered_values": ["low", "medium", "high"],
    },
    "txn.round_amount": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.02,
        "tier": FieldTier.CONTEXTUAL,
    },
    "txn.just_below_threshold": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.04,
        "tier": FieldTier.BEHAVIORAL,
    },
    "txn.multiple_same_day": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.03,
        "tier": FieldTier.BEHAVIORAL,
    },
    "txn.pattern_matches_profile": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.03,
        "tier": FieldTier.CONTEXTUAL,
    },
    "txn.source_of_funds_clear": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.02,
        "tier": FieldTier.CONTEXTUAL,
    },
    "txn.stated_purpose": {
        "type": FieldType.CATEGORICAL,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.02,
        "tier": FieldTier.CONTEXTUAL,
    },

    # --- RED FLAGS ---
    "flag.structuring": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.06,
        "tier": FieldTier.BEHAVIORAL,
    },
    "flag.rapid_movement": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.04,
        "tier": FieldTier.BEHAVIORAL,
    },
    "flag.layering": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.05,
        "tier": FieldTier.BEHAVIORAL,
    },
    "flag.unusual_for_profile": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.04,
        "tier": FieldTier.BEHAVIORAL,
    },
    "flag.third_party": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.03,
        "tier": FieldTier.BEHAVIORAL,
    },
    "flag.shell_company": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.03,
        "tier": FieldTier.BEHAVIORAL,
    },

    # --- SCREENING ---
    "screening.sanctions_match": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.06,
        "tier": FieldTier.BEHAVIORAL,
    },
    "screening.pep_match": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.04,
        "tier": FieldTier.BEHAVIORAL,
    },
    "screening.adverse_media_level": {
        "type": FieldType.ORDINAL,
        "comparison": ComparisonFn.STEP,
        "weight": 0.04,
        "tier": FieldTier.BEHAVIORAL,
        "ordered_values": ["none", "unconfirmed", "confirmed", "confirmed_mltf"],
    },
    "screening.adverse_media": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.00,
        "tier": FieldTier.CONTEXTUAL,
    },
    "prior.sars_filed": {
        "type": FieldType.NUMERIC,
        "comparison": ComparisonFn.DISTANCE_DECAY,
        "weight": 0.03,
        "tier": FieldTier.BEHAVIORAL,
        "max_distance": 4,
    },
    "prior.account_closures": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.02,
        "tier": FieldTier.BEHAVIORAL,
    },

    # --- TRADE FINANCE ---
    "trade.goods_description": {
        "type": FieldType.ORDINAL,
        "comparison": ComparisonFn.STEP,
        "weight": 0.05,
        "tier": FieldTier.BEHAVIORAL,
        "ordered_values": ["detailed", "adequate", "vague", "missing"],
    },
    "trade.pricing_consistent": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.04,
        "tier": FieldTier.BEHAVIORAL,
    },
    "trade.is_letter_of_credit": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.02,
        "tier": FieldTier.CONTEXTUAL,
    },
}


# ---------------------------------------------------------------------------
# Comparability gates (spec Section 4.2)
# ---------------------------------------------------------------------------

_BANKING_GATES = [
    ComparabilityGate(
        field="jurisdiction_regime",
        equivalence_classes={
            "CA_FINTRAC": ["CA", "CA-ON", "CA-QC", "CA-BC", "CA-AB"],
            "US_FinCEN": ["US", "US-NY", "US-CA", "US-FL", "US-TX"],
            "UK_FCA": ["UK", "GB", "GB-ENG", "GB-SCT"],
        },
    ),
    ComparabilityGate(
        field="customer_segment",
        equivalence_classes={
            "retail": ["individual", "personal", "retail", "sole_prop"],
            "SME": ["sme", "small_business"],
            "corporate": ["corporate", "institutional", "company", "corporation",
                          "partnership", "trust", "non_profit"],
            "FI": ["bank", "fi", "financial_institution"],
        },
    ),
    ComparabilityGate(
        field="channel_family",
        equivalence_classes={
            "cash": ["cash", "cash_deposit", "cash_withdrawal"],
            "electronic": ["wire_domestic", "wire_international", "wire",
                           "eft", "ach", "swift", "domestic_wire"],
            "crypto": ["crypto", "virtual_currency", "digital_asset",
                       "crypto_purchase", "crypto_sale"],
            "cheque": ["cheque", "check"],
            "trade": ["trade_finance", "lc", "documentary_credit"],
        },
    ),
    ComparabilityGate(
        field="disposition_basis",
        equivalence_classes={
            "MANDATORY": ["MANDATORY"],
            "DISCRETIONARY": ["DISCRETIONARY"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Disposition / Reporting / Basis mappings (spec Section 3.2-3.4)
# ---------------------------------------------------------------------------

_DISPOSITION_MAPPING: dict[str, str] = {
    # ALLOW
    "approve": "ALLOW", "approved": "ALLOW", "accept": "ALLOW", "accepted": "ALLOW",
    "pay": "ALLOW", "paid": "ALLOW", "pass": "ALLOW", "passed": "ALLOW",
    "clear": "ALLOW", "cleared": "ALLOW", "covered": "ALLOW", "eligible": "ALLOW",
    "no report": "ALLOW", "no action": "ALLOW", "close": "ALLOW", "closed": "ALLOW",
    # EDD
    "review": "EDD", "investigate": "EDD", "investigation": "EDD",
    "hold": "EDD", "pending": "EDD", "manual review": "EDD",
    "needs info": "EDD", "request more info": "EDD", "pass with edd": "EDD",
    "escalate": "EDD", "escalated": "EDD",
    # BLOCK
    "deny": "BLOCK", "denied": "BLOCK", "decline": "BLOCK", "declined": "BLOCK",
    "reject": "BLOCK", "rejected": "BLOCK", "block": "BLOCK", "blocked": "BLOCK",
    "refuse": "BLOCK", "refused": "BLOCK", "hard stop": "BLOCK",
    "exit": "BLOCK", "de-risk": "BLOCK",
}

_REPORTING_MAPPING: dict[str, str] = {
    "str": "FILE_STR", "report str": "FILE_STR",
    "suspicious transaction": "FILE_STR", "suspicious activity": "FILE_STR",
    "lctr": "FILE_LCTR", "large cash": "FILE_LCTR",
    "large cash transaction": "FILE_LCTR",
    "tpr": "FILE_TPR", "terrorist property": "FILE_TPR",
    "terrorist property report": "FILE_TPR",
    "no report": "NO_REPORT", "no filing required": "NO_REPORT",
}

_BASIS_MAPPING: dict[str, str] = {
    "sanctions": "MANDATORY", "sanction": "MANDATORY", "sema": "MANDATORY",
    "una": "MANDATORY", "listed entity": "MANDATORY", "court order": "MANDATORY",
    "statutory": "MANDATORY", "criminal code": "MANDATORY",
    "risk appetite": "DISCRETIONARY", "policy violation": "DISCRETIONARY",
    "commercial exit": "DISCRETIONARY", "fraud risk": "DISCRETIONARY",
    "reputational concern": "DISCRETIONARY", "credit decision": "DISCRETIONARY",
}


# ---------------------------------------------------------------------------
# Registry constructor
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def create_banking_domain_registry() -> DomainRegistry:
    """Construct the banking AML DomainRegistry.

    Reads BANKING_FIELDS and enriches each with v3 metadata from
    _FIELD_ENRICHMENTS. Every field in BANKING_FIELDS is represented.
    """
    fields: dict[str, FieldDefinition] = {}

    for canonical_name, legacy_meta in BANKING_FIELDS.items():
        enrichment = _FIELD_ENRICHMENTS.get(canonical_name)
        if enrichment is None:
            raise ValueError(
                f"No v3 enrichment defined for banking field: {canonical_name}. "
                f"Add an entry to _FIELD_ENRICHMENTS in banking_domain.py."
            )

        fields[canonical_name] = FieldDefinition(
            name=canonical_name,
            label=legacy_meta["display_name"],
            type=enrichment["type"],
            comparison=enrichment["comparison"],
            weight=enrichment["weight"],
            tier=enrichment["tier"],
            required=legacy_meta.get("required", True),
            critical=enrichment.get("critical", False),
            equivalence_classes=enrichment.get("equivalence_classes", {}),
            ordered_values=enrichment.get("ordered_values", []),
            max_distance=enrichment.get("max_distance", 4),
            domain="banking_aml",
        )

    critical = frozenset(
        name for name, fd in fields.items() if fd.critical
    )

    return DomainRegistry(
        domain="banking_aml",
        version="3.0",
        fields=fields,
        comparability_gates=_BANKING_GATES,
        similarity_floor=0.60,
        similarity_floor_overrides={
            "sanctions": 0.80,
            "structuring": 0.65,
            "adverse_media": 0.55,
        },
        pool_minimum=5,
        critical_fields=critical,
        disposition_mapping=_DISPOSITION_MAPPING,
        reporting_mapping=_REPORTING_MAPPING,
        basis_mapping=_BASIS_MAPPING,
    )


# Convenience alias for domain_loader generic discovery
create_registry = create_banking_domain_registry


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "create_banking_domain_registry",
    "create_registry",
]
