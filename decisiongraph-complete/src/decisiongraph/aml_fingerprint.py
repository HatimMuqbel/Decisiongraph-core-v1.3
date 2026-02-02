"""
DecisionGraph Banking/AML Precedent System: Fingerprint Schema Module

This module implements fingerprint computation for privacy-preserving
precedent matching in AML/Banking decision workflows.

Key components:
- AMLFingerprintSchema: Defines which facts matter for matching and how to band them
- AMLFingerprintSchemaRegistry: Registry of schemas by decision category
- compute_fingerprint(): Compute fingerprint hash from facts

Design Principles:
- Deterministic: Same facts + same schema = same fingerprint hash
- Privacy-preserving: Salt prevents reverse engineering
- Banding: Continuous values converted to categorical for stable matching
- Schema versioning: Compatible schemas can match across versions

Schemas Defined:
- decisiongraph:aml:txn:v1 - Transaction Monitoring (700 precedents)
- decisiongraph:aml:kyc:v1 - KYC Onboarding (450 precedents)
- decisiongraph:aml:report:v1 - Reporting (200 precedents)
- decisiongraph:aml:screening:v1 - Sanctions/Screening (350 precedents)
- decisiongraph:aml:monitoring:v1 - Ongoing Monitoring (300 precedents)

Example:
    >>> registry = AMLFingerprintSchemaRegistry()
    >>> schema = registry.get_schema("txn", "CA")
    >>> banded = apply_aml_banding(facts, schema)
    >>> fingerprint = registry.compute_fingerprint(schema, facts, salt)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from .canon import canonical_json_bytes


# =============================================================================
# Exceptions
# =============================================================================

class AMLFingerprintSchemaError(Exception):
    """Base exception for AML fingerprint schema errors."""
    pass


class AMLSchemaNotFoundError(AMLFingerprintSchemaError):
    """Raised when a schema is not found in the registry."""
    pass


class AMLBandingError(AMLFingerprintSchemaError):
    """Raised when banding fails for a fact value."""
    pass


# =============================================================================
# Banding Rules
# =============================================================================

@dataclass
class AMLBandingRule:
    """
    Rule for banding a continuous value to a categorical band.

    Banding converts continuous values (e.g., transaction amount $15,000)
    to categorical bands (e.g., "10k_25k") for stable matching.

    Attributes:
        field_id: The fact field this rule applies to
        bands: List of (upper_bound, band_label) tuples, sorted ascending
               The value is assigned to the first band where value <= upper_bound
               Use None as upper_bound for the final "catch-all" band
    """
    field_id: str
    bands: list[tuple[Optional[float], str]]

    def apply(self, value: Any) -> str:
        """
        Apply banding to a value.

        Args:
            value: The numeric value to band

        Returns:
            The band label

        Raises:
            AMLBandingError: If value cannot be banded
        """
        if value is None:
            return "unknown"

        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            raise AMLBandingError(
                f"Cannot band non-numeric value '{value}' for field '{self.field_id}'"
            )

        for upper_bound, label in self.bands:
            if upper_bound is None or numeric_value <= upper_bound:
                return label

        # Should not reach here if bands are properly defined
        raise AMLBandingError(
            f"No band matched for value {numeric_value} in field '{self.field_id}'"
        )


# =============================================================================
# Fingerprint Schema
# =============================================================================

@dataclass
class AMLFingerprintSchema:
    """
    Schema for computing fingerprints for a specific AML decision category.

    The schema defines:
    - Which facts are relevant for matching (relevant_facts)
    - How to band continuous values (banding_rules)
    - Which older schema versions are compatible (compatible_with)

    Attributes:
        schema_id: Unique identifier (e.g., "decisiongraph:aml:txn:v1")
        category: Decision category (e.g., "txn", "kyc", "screening")
        jurisdiction: Jurisdiction code (e.g., "CA" for Canada)
        relevant_facts: Field IDs that matter for matching
        banding_rules: Dict mapping field_id to AMLBandingRule
        compatible_with: List of older schema IDs this schema can match against
        effective_from: When this schema became effective
        effective_to: When this schema was superseded (None = current)
    """
    schema_id: str
    category: str
    jurisdiction: str
    relevant_facts: list[str]
    banding_rules: dict[str, AMLBandingRule] = field(default_factory=dict)
    compatible_with: list[str] = field(default_factory=list)
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None

    def __post_init__(self) -> None:
        """Validate schema on construction."""
        if not self.schema_id:
            raise AMLFingerprintSchemaError("schema_id cannot be empty")
        if not self.category:
            raise AMLFingerprintSchemaError("category cannot be empty")
        if not self.jurisdiction:
            raise AMLFingerprintSchemaError("jurisdiction cannot be empty")
        if not self.relevant_facts:
            raise AMLFingerprintSchemaError("relevant_facts cannot be empty")

    def is_effective_on(self, check_date: date) -> bool:
        """Check if this schema is effective on a given date."""
        if self.effective_from and check_date < self.effective_from:
            return False
        if self.effective_to and check_date > self.effective_to:
            return False
        return True

    def is_compatible_with(self, other_schema_id: str) -> bool:
        """Check if this schema can match against another schema."""
        return (
            other_schema_id == self.schema_id
            or other_schema_id in self.compatible_with
        )


# =============================================================================
# Fingerprint Schema Registry
# =============================================================================

class AMLFingerprintSchemaRegistry:
    """
    Registry of AML fingerprint schemas by category and jurisdiction.

    The registry provides schema lookup and fingerprint computation.

    Usage:
        >>> registry = AMLFingerprintSchemaRegistry()
        >>> schema = registry.get_schema("txn", "CA")
        >>> fingerprint = registry.compute_fingerprint(schema, facts, salt)
    """

    def __init__(self) -> None:
        """Initialize with built-in schemas."""
        self._schemas: dict[str, AMLFingerprintSchema] = {}
        self._by_category_jurisdiction: dict[tuple[str, str], list[str]] = {}
        self._register_builtin_schemas()

    def _register_builtin_schemas(self) -> None:
        """Register built-in AML schemas."""
        # Transaction Monitoring v1
        self.register_schema(create_txn_monitoring_schema_v1())

        # KYC Onboarding v1
        self.register_schema(create_kyc_onboarding_schema_v1())

        # Reporting v1
        self.register_schema(create_reporting_schema_v1())

        # Sanctions/Screening v1
        self.register_schema(create_screening_schema_v1())

        # Ongoing Monitoring v1
        self.register_schema(create_ongoing_monitoring_schema_v1())

    def register_schema(self, schema: AMLFingerprintSchema) -> None:
        """
        Register a schema in the registry.

        Args:
            schema: The AMLFingerprintSchema to register
        """
        self._schemas[schema.schema_id] = schema

        # Index by category + jurisdiction
        key = (schema.category, schema.jurisdiction)
        if key not in self._by_category_jurisdiction:
            self._by_category_jurisdiction[key] = []
        self._by_category_jurisdiction[key].append(schema.schema_id)

    def get_schema(
        self,
        category: str,
        jurisdiction: str,
        as_of: Optional[date] = None,
    ) -> AMLFingerprintSchema:
        """
        Get the effective schema for a category and jurisdiction.

        Args:
            category: Decision category (e.g., "txn", "kyc", "screening")
            jurisdiction: Jurisdiction code (e.g., "CA")
            as_of: Date to check effectiveness (defaults to today)

        Returns:
            The effective AMLFingerprintSchema

        Raises:
            AMLSchemaNotFoundError: If no schema matches
        """
        key = (category, jurisdiction)
        schema_ids = self._by_category_jurisdiction.get(key, [])

        if not schema_ids:
            raise AMLSchemaNotFoundError(
                f"No schema found for category='{category}', "
                f"jurisdiction='{jurisdiction}'"
            )

        check_date = as_of or date.today()

        # Find effective schema
        for schema_id in schema_ids:
            schema = self._schemas[schema_id]
            if schema.is_effective_on(check_date):
                return schema

        # No effective schema found, return most recent
        return self._schemas[schema_ids[-1]]

    def get_schema_by_id(self, schema_id: str) -> AMLFingerprintSchema:
        """
        Get a schema by its ID.

        Args:
            schema_id: The schema ID

        Returns:
            The AMLFingerprintSchema

        Raises:
            AMLSchemaNotFoundError: If schema not found
        """
        if schema_id not in self._schemas:
            raise AMLSchemaNotFoundError(f"Schema not found: {schema_id}")
        return self._schemas[schema_id]

    def list_schemas(self) -> list[str]:
        """Return list of all registered schema IDs."""
        return list(self._schemas.keys())

    def compute_fingerprint(
        self,
        schema: AMLFingerprintSchema,
        facts: dict[str, Any],
        salt: str,
    ) -> str:
        """
        Compute fingerprint hash from facts using a schema.

        Args:
            schema: The AMLFingerprintSchema to use
            facts: Dict of field_id -> value
            salt: Salt for privacy-preserving hashing

        Returns:
            64-character lowercase hex string (SHA-256)
        """
        if not salt:
            raise AMLFingerprintSchemaError("salt cannot be empty")

        # Apply banding to get categorical facts
        banded = apply_aml_banding(facts, schema)

        # Create canonical representation
        # Sort by field_id for deterministic ordering
        canonical_facts = {
            field_id: banded.get(field_id, "unknown")
            for field_id in sorted(schema.relevant_facts)
        }

        # Include schema_id in fingerprint for version tracking
        fingerprint_data = {
            "schema_id": schema.schema_id,
            "facts": canonical_facts,
        }

        # Compute hash with salt prefix
        content = canonical_json_bytes(fingerprint_data)
        salted = salt.encode("utf-8") + content
        return hashlib.sha256(salted).hexdigest()


# =============================================================================
# Banding Functions
# =============================================================================

def apply_aml_banding(
    facts: dict[str, Any],
    schema: AMLFingerprintSchema,
) -> dict[str, Any]:
    """
    Apply banding rules to convert continuous values to categorical.

    Args:
        facts: Dict of field_id -> value
        schema: The AMLFingerprintSchema with banding rules

    Returns:
        Dict of field_id -> banded_value
    """
    result: dict[str, Any] = {}

    for field_id in schema.relevant_facts:
        value = facts.get(field_id)

        if field_id in schema.banding_rules:
            # Apply banding rule
            rule = schema.banding_rules[field_id]
            result[field_id] = rule.apply(value)
        elif value is None:
            result[field_id] = "unknown"
        elif isinstance(value, bool):
            result[field_id] = "true" if value else "false"
        elif isinstance(value, str):
            # String values pass through as-is
            result[field_id] = value
        else:
            # Other values converted to string
            result[field_id] = str(value)

    return result


# =============================================================================
# Common Banding Rules
# =============================================================================

def create_txn_amount_banding() -> AMLBandingRule:
    """
    Banding rule for transaction amounts (CAD).

    Bands:
    - 0-2999: "under_3k"
    - 3000-9999: "3k_10k"
    - 10000-24999: "10k_25k"
    - 25000-99999: "25k_100k"
    - 100000-499999: "100k_500k"
    - 500000-999999: "500k_1m"
    - 1000000+: "over_1m"
    """
    return AMLBandingRule(
        field_id="txn.amount",
        bands=[
            (2999, "under_3k"),
            (9999, "3k_10k"),
            (24999, "10k_25k"),
            (99999, "25k_100k"),
            (499999, "100k_500k"),
            (999999, "500k_1m"),
            (None, "over_1m"),
        ],
    )


def create_relationship_months_banding() -> AMLBandingRule:
    """
    Banding rule for customer relationship duration in months.

    Bands:
    - 0-3: "new"
    - 4-12: "recent"
    - 13-36: "established"
    - 37+: "long_term"
    """
    return AMLBandingRule(
        field_id="customer.relationship_months",
        bands=[
            (3, "new"),
            (12, "recent"),
            (36, "established"),
            (None, "long_term"),
        ],
    )


def create_hours_in_account_banding() -> AMLBandingRule:
    """
    Banding rule for hours funds remain in account (rapid movement detection).

    Bands:
    - 0-24: "immediate"
    - 25-72: "rapid"
    - 73-168: "short"
    - 169+: "normal"
    """
    return AMLBandingRule(
        field_id="txn.hours_in_account",
        bands=[
            (24, "immediate"),
            (72, "rapid"),
            (168, "short"),
            (None, "normal"),
        ],
    )


def create_match_score_banding() -> AMLBandingRule:
    """
    Banding rule for screening match scores.

    Bands:
    - 0-69: "low"
    - 70-84: "medium"
    - 85-94: "high"
    - 95-100: "exact"
    """
    return AMLBandingRule(
        field_id="match.score",
        bands=[
            (69, "low"),
            (84, "medium"),
            (94, "high"),
            (None, "exact"),
        ],
    )


def create_ownership_pct_banding() -> AMLBandingRule:
    """
    Banding rule for ownership percentage.

    Bands:
    - 0-24: "minority"
    - 25-49: "significant"
    - 50-100: "controlling"
    """
    return AMLBandingRule(
        field_id="ownership.direct_pct",
        bands=[
            (24, "minority"),
            (49, "significant"),
            (None, "controlling"),
        ],
    )


def create_delisted_months_banding() -> AMLBandingRule:
    """
    Banding rule for months since delisting.

    Bands:
    - 0-6: "recent"
    - 7-24: "moderate"
    - 25+: "old"
    """
    return AMLBandingRule(
        field_id="delisted.months_since",
        bands=[
            (6, "recent"),
            (24, "moderate"),
            (None, "old"),
        ],
    )


def create_volume_change_pct_banding() -> AMLBandingRule:
    """
    Banding rule for activity volume change percentage.

    Bands:
    - 0-50: "minor"
    - 51-100: "moderate"
    - 101-300: "significant"
    - 301+: "extreme"
    """
    return AMLBandingRule(
        field_id="activity.volume_change_pct",
        bands=[
            (50, "minor"),
            (100, "moderate"),
            (300, "significant"),
            (None, "extreme"),
        ],
    )


def create_dormant_months_banding() -> AMLBandingRule:
    """
    Banding rule for months of account dormancy.

    Bands:
    - 6-12: "short"
    - 13-24: "medium"
    - 25-60: "long"
    - 61+: "very_long"
    """
    return AMLBandingRule(
        field_id="dormant.months_inactive",
        bands=[
            (12, "short"),
            (24, "medium"),
            (60, "long"),
            (None, "very_long"),
        ],
    )


def create_indicator_count_banding() -> AMLBandingRule:
    """
    Banding rule for suspicious indicator count.

    Bands:
    - 0: "none"
    - 1: "single"
    - 2-3: "multiple"
    - 4+: "many"
    """
    return AMLBandingRule(
        field_id="suspicious.indicator_count",
        bands=[
            (0, "none"),
            (1, "single"),
            (3, "multiple"),
            (None, "many"),
        ],
    )


def create_prior_sars_banding() -> AMLBandingRule:
    """
    Banding rule for prior SARs filed count.

    Bands:
    - 0: "none"
    - 1: "one"
    - 2-4: "few"
    - 5+: "many"
    """
    return AMLBandingRule(
        field_id="prior.sars_filed",
        bands=[
            (0, "none"),
            (1, "one"),
            (4, "few"),
            (None, "many"),
        ],
    )


def create_adverse_media_age_banding() -> AMLBandingRule:
    """
    Banding rule for adverse media age in years.

    Bands:
    - 0-2: "recent"
    - 3-5: "moderate"
    - 6+: "old"
    """
    return AMLBandingRule(
        field_id="screening.adverse_media_age_years",
        bands=[
            (2, "recent"),
            (5, "moderate"),
            (None, "old"),
        ],
    )


# =============================================================================
# Built-in Schemas
# =============================================================================

def create_txn_monitoring_schema_v1() -> AMLFingerprintSchema:
    """
    Create the Transaction Monitoring v1 fingerprint schema.

    This schema defines facts relevant for AML transaction monitoring
    decisions in Canada.

    Relevant facts:
    - txn.type: Transaction type (wire, cash, ach, crypto)
    - txn.amount_band: Banded transaction amount
    - txn.cross_border: Whether transaction is cross-border
    - txn.destination_country_risk: Risk level of destination country
    - txn.round_amount: Whether amount is suspiciously round
    - txn.just_below_threshold: Whether just below reporting threshold
    - txn.multiple_same_day: Multiple same-day transactions
    - txn.rapid_movement: Funds moved rapidly through account
    - txn.pattern_matches_profile: Consistent with customer profile
    - txn.third_party_involved: Third party in transaction
    - customer.type: Customer type (individual, corporate, etc.)
    - customer.risk_level: Customer risk rating
    - customer.pep: Whether customer is PEP
    - customer.pep_type: Type of PEP (domestic, foreign, rca)
    - customer.high_risk_industry: High-risk industry flag
    - customer.relationship_length: Banded relationship duration
    - crypto.exchange_regulated: Whether crypto exchange is regulated
    - crypto.wallet_type: Type of crypto wallet (hosted, unhosted)
    - crypto.mixer_indicators: Signs of mixer/tumbler usage
    - screening.sanctions_match: Sanctions screening result
    - screening.adverse_media: Adverse media flag
    """
    return AMLFingerprintSchema(
        schema_id="decisiongraph:aml:txn:v1",
        category="txn",
        jurisdiction="CA",
        relevant_facts=[
            # Transaction details
            "txn.type",
            "txn.amount_band",
            "txn.cross_border",
            "txn.destination_country_risk",
            "txn.originator_country_risk",
            "txn.round_amount",
            "txn.just_below_threshold",
            "txn.multiple_same_day",
            "txn.rapid_movement",
            "txn.pattern_matches_profile",
            "txn.third_party_involved",
            # Customer context
            "customer.type",
            "customer.risk_level",
            "customer.pep",
            "customer.pep_type",
            "customer.high_risk_industry",
            "customer.relationship_length",
            # Crypto specific
            "crypto.exchange_regulated",
            "crypto.wallet_type",
            "crypto.mixer_indicators",
            # Screening
            "screening.sanctions_match",
            "screening.adverse_media",
        ],
        banding_rules={
            "txn.amount": create_txn_amount_banding(),
            "customer.relationship_months": create_relationship_months_banding(),
            "txn.hours_in_account": create_hours_in_account_banding(),
        },
        compatible_with=[],
    )


def create_kyc_onboarding_schema_v1() -> AMLFingerprintSchema:
    """
    Create the KYC Onboarding v1 fingerprint schema.

    This schema defines facts relevant for KYC onboarding decisions
    in Canada under FINTRAC requirements.

    Relevant facts:
    - customer.type: Customer type (individual, corporate, trust, etc.)
    - customer.risk_level: Calculated risk level
    - customer.jurisdiction: Customer jurisdiction
    - customer.pep: PEP status
    - customer.pep_type: Type of PEP
    - customer.pep_level: Level of PEP (head_of_state, senior_official, etc.)
    - customer.rca: Related or close associate
    - customer.high_risk_industry: High-risk industry flag
    - customer.industry_type: Specific high-risk industry
    - customer.cash_intensive: Cash-intensive business
    - kyc.id_verified: ID verification status
    - kyc.id_type: Type of ID document
    - kyc.id_expired: Whether ID is expired
    - kyc.address_verified: Address verification status
    - kyc.beneficial_owners_identified: UBO identification status
    - kyc.ubo_over_25_pct: UBO >25% identified
    - kyc.source_of_wealth_documented: SOW documentation
    - kyc.source_of_funds_documented: SOF documentation
    - shell.nominee_directors: Shell company indicator
    - shell.registered_agent_only: Shell company indicator
    - shell.no_physical_presence: Shell company indicator
    - edd.required: Whether EDD is required
    - edd.complete: Whether EDD is complete
    - edd.senior_approval: Whether senior approval obtained
    - screening.sanctions_match: Sanctions screening result
    - screening.pep_match: PEP screening result
    - screening.adverse_media: Adverse media flag
    - screening.adverse_media_severity: Severity of adverse media
    """
    return AMLFingerprintSchema(
        schema_id="decisiongraph:aml:kyc:v1",
        category="kyc",
        jurisdiction="CA",
        relevant_facts=[
            # Customer type
            "customer.type",
            "customer.risk_level",
            "customer.jurisdiction",
            "customer.tax_residency",
            # PEP status
            "customer.pep",
            "customer.pep_type",
            "customer.pep_level",
            "customer.rca",
            # Industry
            "customer.high_risk_industry",
            "customer.industry_type",
            "customer.cash_intensive",
            # KYC status
            "kyc.id_verified",
            "kyc.id_type",
            "kyc.id_expired",
            "kyc.address_verified",
            "kyc.address_proof_type",
            # Corporate specific
            "kyc.beneficial_owners_identified",
            "kyc.ubo_over_25_pct",
            "kyc.source_of_wealth_documented",
            "kyc.source_of_funds_documented",
            "kyc.business_activity_verified",
            # Shell indicators
            "shell.nominee_directors",
            "shell.registered_agent_only",
            "shell.no_physical_presence",
            "shell.complex_structure",
            # EDD
            "edd.required",
            "edd.complete",
            "edd.senior_approval",
            # Screening
            "screening.sanctions_match",
            "screening.pep_match",
            "screening.adverse_media",
            "screening.adverse_media_severity",
        ],
        banding_rules={
            "screening.adverse_media_age_years": create_adverse_media_age_banding(),
        },
        compatible_with=[],
    )


def create_reporting_schema_v1() -> AMLFingerprintSchema:
    """
    Create the Reporting v1 fingerprint schema.

    This schema defines facts relevant for AML reporting decisions
    (LCTR, STR, TPR) in Canada.

    Relevant facts:
    - txn.type: Transaction type
    - txn.amount_band: Banded transaction amount
    - txn.cash_involved: Whether cash is involved
    - txn.cash_amount_band: Banded cash amount
    - suspicious.indicator_count: Number of suspicious indicators
    - suspicious.structuring: Structuring indicators
    - suspicious.unusual_pattern: Unusual pattern indicators
    - suspicious.third_party: Third party involvement
    - suspicious.layering: Layering indicators
    - suspicious.source_unclear: Source of funds unclear
    - suspicious.purpose_unclear: Purpose unclear
    - terrorist.property_indicators: TPR indicators
    - terrorist.listed_entity: Listed terrorist entity
    - terrorist.associated_entity: Associated entity
    - prior.sars_filed: Number of prior SARs
    - prior.lctr_filed: Number of prior LCTRs
    - prior.account_closures: Prior account closures
    """
    return AMLFingerprintSchema(
        schema_id="decisiongraph:aml:report:v1",
        category="report",
        jurisdiction="CA",
        relevant_facts=[
            # Transaction context
            "txn.type",
            "txn.amount_band",
            "txn.cash_involved",
            "txn.cash_amount_band",
            # Suspicious indicators
            "suspicious.indicator_count",
            "suspicious.structuring",
            "suspicious.unusual_pattern",
            "suspicious.third_party",
            "suspicious.layering",
            "suspicious.source_unclear",
            "suspicious.purpose_unclear",
            # Terrorist financing
            "terrorist.property_indicators",
            "terrorist.listed_entity",
            "terrorist.associated_entity",
            # History
            "prior.sars_filed",
            "prior.lctr_filed",
            "prior.account_closures",
        ],
        banding_rules={
            "suspicious.indicator_count": create_indicator_count_banding(),
            "prior.sars_filed": create_prior_sars_banding(),
        },
        compatible_with=[],
    )


def create_screening_schema_v1() -> AMLFingerprintSchema:
    """
    Create the Sanctions/Screening v1 fingerprint schema.

    This schema defines facts relevant for sanctions and PEP screening
    decisions globally.

    Relevant facts:
    - match.type: Type of match (sanctions, pep, adverse_media)
    - match.list_source: Source list (ofac, un, eu, uk, ca_sema)
    - match.score_band: Banded match score
    - match.name_match_type: Type of name match (exact, fuzzy, alias)
    - match.secondary_identifiers: Secondary identifiers matched
    - entity.type: Entity type (individual, corporate, vessel, aircraft)
    - entity.jurisdiction: Entity jurisdiction
    - ownership.direct_pct_band: Banded direct ownership %
    - ownership.indirect_pct_band: Banded indirect ownership %
    - ownership.aggregated_over_50: Whether aggregated >50%
    - ownership.chain_depth: Depth of ownership chain
    - delisted.status: Delisting status
    - delisted.date_band: Banded time since delisting
    - secondary.exposure: Secondary sanctions exposure
    - secondary.jurisdiction: Secondary sanctions jurisdiction
    """
    return AMLFingerprintSchema(
        schema_id="decisiongraph:aml:screening:v1",
        category="screening",
        jurisdiction="GLOBAL",
        relevant_facts=[
            # Match details
            "match.type",
            "match.list_source",
            "match.score_band",
            "match.name_match_type",
            "match.secondary_identifiers",
            # Entity details
            "entity.type",
            "entity.jurisdiction",
            # Ownership
            "ownership.direct_pct_band",
            "ownership.indirect_pct_band",
            "ownership.aggregated_over_50",
            "ownership.chain_depth",
            # De-listing
            "delisted.status",
            "delisted.date_band",
            # Secondary sanctions
            "secondary.exposure",
            "secondary.jurisdiction",
        ],
        banding_rules={
            "match.score": create_match_score_banding(),
            "ownership.direct_pct": create_ownership_pct_banding(),
            "delisted.months_since": create_delisted_months_banding(),
        },
        compatible_with=[],
    )


def create_ongoing_monitoring_schema_v1() -> AMLFingerprintSchema:
    """
    Create the Ongoing Monitoring v1 fingerprint schema.

    This schema defines facts relevant for ongoing customer monitoring
    decisions in Canada.

    Relevant facts:
    - trigger.type: Type of monitoring trigger
    - activity.volume_change_band: Banded volume change
    - activity.value_change_band: Banded value change
    - activity.new_pattern: New pattern detected
    - activity.new_jurisdiction: New jurisdiction detected
    - activity.new_counterparty_type: New counterparty type
    - review.type: Type of review (annual, trigger_based, regulatory)
    - review.risk_change: Risk level change (unchanged, upgraded, downgraded)
    - review.kyc_refresh_needed: Whether KYC refresh needed
    - profile.address_change: Address change detected
    - profile.bo_change: Beneficial owner change
    - profile.industry_change: Industry change
    - profile.jurisdiction_change: Jurisdiction change
    - dormant.months_inactive: Months of inactivity
    - dormant.reactivation_pattern: Reactivation pattern
    - exit.reason: Exit reason (risk, sar, regulatory, commercial)
    - exit.sar_related: Whether exit is SAR-related
    """
    return AMLFingerprintSchema(
        schema_id="decisiongraph:aml:monitoring:v1",
        category="monitoring",
        jurisdiction="CA",
        relevant_facts=[
            # Trigger type
            "trigger.type",
            # Activity triggers
            "activity.volume_change_band",
            "activity.value_change_band",
            "activity.new_pattern",
            "activity.new_jurisdiction",
            "activity.new_counterparty_type",
            # Periodic review
            "review.type",
            "review.risk_change",
            "review.kyc_refresh_needed",
            # Profile changes
            "profile.address_change",
            "profile.bo_change",
            "profile.industry_change",
            "profile.jurisdiction_change",
            # Dormant
            "dormant.months_inactive",
            "dormant.reactivation_pattern",
            # Exit
            "exit.reason",
            "exit.sar_related",
        ],
        banding_rules={
            "activity.volume_change_pct": create_volume_change_pct_banding(),
            "dormant.months_inactive": create_dormant_months_banding(),
        },
        compatible_with=[],
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Exceptions
    "AMLFingerprintSchemaError",
    "AMLSchemaNotFoundError",
    "AMLBandingError",

    # Data classes
    "AMLBandingRule",
    "AMLFingerprintSchema",

    # Registry
    "AMLFingerprintSchemaRegistry",

    # Functions
    "apply_aml_banding",

    # Banding rule factories
    "create_txn_amount_banding",
    "create_relationship_months_banding",
    "create_hours_in_account_banding",
    "create_match_score_banding",
    "create_ownership_pct_banding",
    "create_delisted_months_banding",
    "create_volume_change_pct_banding",
    "create_dormant_months_banding",
    "create_indicator_count_banding",
    "create_prior_sars_banding",
    "create_adverse_media_age_banding",

    # Schema factories
    "create_txn_monitoring_schema_v1",
    "create_kyc_onboarding_schema_v1",
    "create_reporting_schema_v1",
    "create_screening_schema_v1",
    "create_ongoing_monitoring_schema_v1",
]
