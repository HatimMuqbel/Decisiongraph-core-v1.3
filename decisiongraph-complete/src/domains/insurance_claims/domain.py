"""
Insurance Claims Domain Registry — v3 Precedent Engine.

Constructs a DomainRegistry for the insurance claims domain by enriching
INSURANCE_FIELDS with v3 metadata (type, comparison function, weight,
tier, critical flag, equivalence classes).

Modeled on domains/banking_aml/domain.py.  The kernel reads this registry
generically — same data structures, same scoring engine, different vocabulary.
"""

from __future__ import annotations

from functools import lru_cache

from .registry import (
    INSURANCE_FIELDS,
    INSURANCE_DISPOSITIONS,
    INSURANCE_REPORTING,
    INSURANCE_BASIS,
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
# v3 field metadata — enrichments over INSURANCE_FIELDS
# ---------------------------------------------------------------------------

_FIELD_ENRICHMENTS: dict[str, dict] = {
    # --- CLAIM STRUCTURAL ---
    "claim.coverage_line": {
        "type": FieldType.CATEGORICAL,
        "comparison": ComparisonFn.EQUIVALENCE_CLASS,
        "weight": 0.06,
        "tier": FieldTier.STRUCTURAL,
        "critical": True,
        "equivalence_classes": {
            "auto": ["auto", "automobile"],
            "property": ["property", "homeowners"],
            "health": ["health", "medical"],
            "workers_comp": ["workers_comp", "wsib"],
            "liability": ["cgl", "commercial_general_liability"],
            "professional": ["eo", "errors_omissions"],
            "marine": ["marine", "pleasure_craft"],
            "travel": ["travel"],
        },
    },
    "claim.amount_band": {
        "type": FieldType.ORDINAL,
        "comparison": ComparisonFn.STEP,
        "weight": 0.10,
        "tier": FieldTier.STRUCTURAL,
        "critical": True,
        "ordered_values": [
            "under_5k", "5k_25k", "25k_100k", "100k_500k", "over_500k",
        ],
    },
    "claim.claimant_type": {
        "type": FieldType.CATEGORICAL,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.04,
        "tier": FieldTier.STRUCTURAL,
        "critical": True,
    },

    # --- RED FLAGS (BEHAVIORAL) ---
    "flag.fraud_indicator": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.08,
        "tier": FieldTier.BEHAVIORAL,
    },
    "flag.prior_claims_frequency": {
        "type": FieldType.ORDINAL,
        "comparison": ComparisonFn.STEP,
        "weight": 0.05,
        "tier": FieldTier.BEHAVIORAL,
        "ordered_values": ["none", "low", "moderate", "high"],
    },
    "flag.late_reporting": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.04,
        "tier": FieldTier.BEHAVIORAL,
    },
    "flag.inconsistent_statements": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.06,
        "tier": FieldTier.BEHAVIORAL,
    },
    "flag.staged_accident": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.06,
        "tier": FieldTier.BEHAVIORAL,
    },
    "flag.excessive_claim_history": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.04,
        "tier": FieldTier.BEHAVIORAL,
    },
    "flag.pre_existing_damage": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.04,
        "tier": FieldTier.BEHAVIORAL,
    },

    # --- EVIDENCE ---
    "evidence.police_report": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.03,
        "tier": FieldTier.CONTEXTUAL,
    },
    "evidence.medical_report": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.03,
        "tier": FieldTier.CONTEXTUAL,
    },
    "evidence.witness_statements": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.02,
        "tier": FieldTier.CONTEXTUAL,
    },
    "evidence.photos_documentation": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.02,
        "tier": FieldTier.CONTEXTUAL,
    },

    # --- POLICY ---
    "policy.deductible_band": {
        "type": FieldType.ORDINAL,
        "comparison": ComparisonFn.STEP,
        "weight": 0.03,
        "tier": FieldTier.CONTEXTUAL,
        "ordered_values": ["low", "medium", "high"],
    },
    "policy.coverage_limit_band": {
        "type": FieldType.ORDINAL,
        "comparison": ComparisonFn.STEP,
        "weight": 0.03,
        "tier": FieldTier.CONTEXTUAL,
        "ordered_values": ["basic", "standard", "premium", "excess"],
    },
    "policy.policy_age": {
        "type": FieldType.ORDINAL,
        "comparison": ComparisonFn.STEP,
        "weight": 0.02,
        "tier": FieldTier.CONTEXTUAL,
        "ordered_values": ["new", "established", "mature"],
    },

    # --- CONTEXTUAL ---
    "claim.injury_type": {
        "type": FieldType.ORDINAL,
        "comparison": ComparisonFn.STEP,
        "weight": 0.04,
        "tier": FieldTier.CONTEXTUAL,
        "ordered_values": ["minor", "moderate", "serious", "catastrophic"],
    },
    "claim.loss_cause": {
        "type": FieldType.CATEGORICAL,
        "comparison": ComparisonFn.EQUIVALENCE_CLASS,
        "weight": 0.04,
        "tier": FieldTier.CONTEXTUAL,
        "equivalence_classes": {
            "vehicle": ["collision", "theft"],
            "natural": ["fire", "water", "wind"],
            "human": ["vandalism", "liability"],
            "other": ["other"],
        },
    },
    "claim.time_to_report": {
        "type": FieldType.ORDINAL,
        "comparison": ComparisonFn.STEP,
        "weight": 0.03,
        "tier": FieldTier.BEHAVIORAL,
        "ordered_values": ["immediate", "within_week", "within_month", "delayed"],
    },
    "claim.occurred_during_policy": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.03,
        "tier": FieldTier.CONTEXTUAL,
    },

    # --- SCREENING ---
    "screening.siu_referral": {
        "type": FieldType.BOOLEAN,
        "comparison": ComparisonFn.EXACT,
        "weight": 0.05,
        "tier": FieldTier.BEHAVIORAL,
    },
    "prior.claims_denied": {
        "type": FieldType.NUMERIC,
        "comparison": ComparisonFn.DISTANCE_DECAY,
        "weight": 0.03,
        "tier": FieldTier.BEHAVIORAL,
        "max_distance": 4,
    },
}


# ---------------------------------------------------------------------------
# Comparability gates (spec Section 4.2)
# ---------------------------------------------------------------------------

_INSURANCE_GATES = [
    ComparabilityGate(
        field="jurisdiction_regime",
        equivalence_classes={
            "CA_FSRA": ["CA", "CA-ON", "CA-QC", "CA-BC", "CA-AB"],
            "US_STATE": ["US", "US-NY", "US-CA", "US-FL", "US-TX"],
            "UK_FCA": ["UK", "GB"],
        },
    ),
    ComparabilityGate(
        field="coverage_family",
        equivalence_classes={
            "auto": ["auto", "automobile"],
            "property": ["property", "homeowners"],
            "health": ["health", "medical"],
            "workers_comp": ["workers_comp", "wsib"],
            "liability": ["cgl", "commercial_general_liability", "eo", "errors_omissions"],
            "specialty": ["marine", "pleasure_craft", "travel"],
        },
    ),
    ComparabilityGate(
        field="claimant_family",
        equivalence_classes={
            "first_party": ["first_party", "1st_party", "insured"],
            "third_party": ["third_party", "3rd_party", "claimant"],
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
    # ALLOW (pay)
    "pay": "ALLOW", "pay_claim": "ALLOW", "approve": "ALLOW",
    "approved": "ALLOW", "covered": "ALLOW", "eligible": "ALLOW",
    "partial": "ALLOW", "partial_pay": "ALLOW",
    "subrogation": "ALLOW",
    # EDD (investigate)
    "investigate": "EDD", "investigation": "EDD",
    "refer_siu": "EDD", "siu_referral": "EDD",
    "hold": "EDD", "pending": "EDD", "escalate": "EDD",
    "reserve_only": "EDD", "request_info": "EDD",
    # BLOCK (deny)
    "deny": "BLOCK", "deny_claim": "BLOCK", "denied": "BLOCK",
    "decline": "BLOCK", "declined": "BLOCK",
    "close_no_pay": "BLOCK", "reject": "BLOCK",
}

_REPORTING_MAPPING: dict[str, str] = {
    "no_filing": "NO_FILING", "none": "NO_FILING",
    "fsra_notice": "FSRA_NOTICE", "regulatory_notice": "FSRA_NOTICE",
    "fraud_report": "FRAUD_REPORT", "siu_report": "FRAUD_REPORT",
}

_BASIS_MAPPING: dict[str, str] = {
    "policy_exclusion": "MANDATORY", "regulatory": "MANDATORY",
    "statutory": "MANDATORY", "excluded_peril": "MANDATORY",
    "outside_policy_period": "MANDATORY",
    "claims_assessment": "DISCRETIONARY", "risk_judgment": "DISCRETIONARY",
    "adjuster_discretion": "DISCRETIONARY", "coverage_interpretation": "DISCRETIONARY",
}


# ---------------------------------------------------------------------------
# Registry constructor
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def create_insurance_domain_registry() -> DomainRegistry:
    """Construct the insurance claims DomainRegistry.

    Reads INSURANCE_FIELDS and enriches each with v3 metadata from
    _FIELD_ENRICHMENTS.  Every field in INSURANCE_FIELDS is represented.
    """
    fields: dict[str, FieldDefinition] = {}

    for canonical_name, legacy_meta in INSURANCE_FIELDS.items():
        enrichment = _FIELD_ENRICHMENTS.get(canonical_name)
        if enrichment is None:
            raise ValueError(
                f"No v3 enrichment defined for insurance field: {canonical_name}. "
                f"Add an entry to _FIELD_ENRICHMENTS in domain.py."
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
            domain="insurance_claims",
        )

    critical = frozenset(
        name for name, fd in fields.items() if fd.critical
    )

    return DomainRegistry(
        domain="insurance_claims",
        version="3.0",
        fields=fields,
        comparability_gates=_INSURANCE_GATES,
        similarity_floor=0.55,
        similarity_floor_overrides={
            "fraud": 0.75,
            "siu_referral": 0.70,
            "catastrophic_injury": 0.50,
        },
        pool_minimum=5,
        critical_fields=critical,
        disposition_mapping=_DISPOSITION_MAPPING,
        reporting_mapping=_REPORTING_MAPPING,
        basis_mapping=_BASIS_MAPPING,
    )


# Convenience alias matching banking pattern
create_registry = create_insurance_domain_registry


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "create_insurance_domain_registry",
    "create_registry",
]
