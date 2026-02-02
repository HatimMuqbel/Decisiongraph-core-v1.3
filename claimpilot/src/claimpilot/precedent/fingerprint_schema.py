"""
ClaimPilot Precedent System: Fingerprint Schema Module

This module implements fingerprint computation for privacy-preserving
precedent matching. Fingerprints enable Tier 0 (exact) matching without
exposing raw fact values.

Key components:
- FingerprintSchema: Defines which facts matter for matching and how to band them
- FingerprintSchemaRegistry: Registry of schemas by policy type and jurisdiction
- compute_fingerprint(): Compute fingerprint hash from facts

Design Principles:
- Deterministic: Same facts + same schema = same fingerprint hash
- Privacy-preserving: Salt prevents reverse engineering
- Banding: Continuous values converted to categorical for stable matching
- Schema versioning: Compatible schemas can match across versions

Salt Handling:
- Salt is stored in namespace config, NEVER in JUDGMENT cells
- No salt rotation in v1 (rotation would require schema epoch tracking)

Example:
    >>> registry = FingerprintSchemaRegistry()
    >>> schema = registry.get_schema("auto", "CA-ON")
    >>> banded = apply_banding(facts, schema)
    >>> fingerprint = registry.compute_fingerprint(schema, facts, salt)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from ..canon import canonical_json_bytes


# =============================================================================
# Exceptions
# =============================================================================

class FingerprintSchemaError(Exception):
    """Base exception for fingerprint schema errors."""
    pass


class SchemaNotFoundError(FingerprintSchemaError):
    """Raised when a schema is not found in the registry."""
    pass


class BandingError(FingerprintSchemaError):
    """Raised when banding fails for a fact value."""
    pass


# =============================================================================
# Banding Rules
# =============================================================================

@dataclass
class BandingRule:
    """
    Rule for banding a continuous value to a categorical band.

    Banding converts continuous values (e.g., BAC 0.08) to categorical
    bands (e.g., "legal_limit") for stable matching.

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
            BandingError: If value cannot be banded
        """
        if value is None:
            return "unknown"

        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as e:
            raise BandingError(
                f"Cannot band non-numeric value '{value}' for field '{self.field_id}'"
            )

        for upper_bound, label in self.bands:
            if upper_bound is None or numeric_value <= upper_bound:
                return label

        # Should not reach here if bands are properly defined
        raise BandingError(
            f"No band matched for value {numeric_value} in field '{self.field_id}'"
        )


# =============================================================================
# Fingerprint Schema
# =============================================================================

@dataclass
class FingerprintSchema:
    """
    Schema for computing fingerprints for a specific policy type and jurisdiction.

    The schema defines:
    - Which facts are relevant for matching (exclusion_relevant_facts)
    - How to band continuous values (banding_rules)
    - Which older schema versions are compatible (compatible_with)

    Attributes:
        schema_id: Unique identifier (e.g., "claimpilot:oap1:auto:v1")
        policy_type: Policy type (e.g., "auto")
        jurisdiction: Jurisdiction code (e.g., "CA-ON")
        exclusion_relevant_facts: Field IDs that matter for matching
        banding_rules: Dict mapping field_id to BandingRule
        compatible_with: List of older schema IDs this schema can match against
        effective_from: When this schema became effective
        effective_to: When this schema was superseded (None = current)
    """
    schema_id: str
    policy_type: str
    jurisdiction: str
    exclusion_relevant_facts: list[str]
    banding_rules: dict[str, BandingRule] = field(default_factory=dict)
    compatible_with: list[str] = field(default_factory=list)
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None

    def __post_init__(self) -> None:
        """Validate schema on construction."""
        if not self.schema_id:
            raise FingerprintSchemaError("schema_id cannot be empty")
        if not self.policy_type:
            raise FingerprintSchemaError("policy_type cannot be empty")
        if not self.jurisdiction:
            raise FingerprintSchemaError("jurisdiction cannot be empty")
        if not self.exclusion_relevant_facts:
            raise FingerprintSchemaError("exclusion_relevant_facts cannot be empty")

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

class FingerprintSchemaRegistry:
    """
    Registry of fingerprint schemas by policy type and jurisdiction.

    The registry provides schema lookup and fingerprint computation.

    Usage:
        >>> registry = FingerprintSchemaRegistry()
        >>> schema = registry.get_schema("auto", "CA-ON")
        >>> fingerprint = registry.compute_fingerprint(schema, facts, salt)
    """

    def __init__(self) -> None:
        """Initialize with built-in schemas."""
        self._schemas: dict[str, FingerprintSchema] = {}
        self._by_policy_jurisdiction: dict[tuple[str, str], list[str]] = {}
        self._register_builtin_schemas()

    def _register_builtin_schemas(self) -> None:
        """Register built-in schemas."""
        # Ontario Auto (OAP 1) v1
        self.register_schema(create_ontario_auto_schema_v1())

        # Property (HO-3) v1
        self.register_schema(create_property_ho3_schema_v1())

        # Marine v1
        self.register_schema(create_marine_schema_v1())

        # Health v1
        self.register_schema(create_health_schema_v1())

        # WSIB v1
        self.register_schema(create_wsib_schema_v1())

        # CGL v1
        self.register_schema(create_cgl_schema_v1())

        # E&O v1
        self.register_schema(create_eo_schema_v1())

        # Travel v1
        self.register_schema(create_travel_schema_v1())

    def register_schema(self, schema: FingerprintSchema) -> None:
        """
        Register a schema in the registry.

        Args:
            schema: The FingerprintSchema to register
        """
        self._schemas[schema.schema_id] = schema

        # Index by policy_type + jurisdiction
        key = (schema.policy_type, schema.jurisdiction)
        if key not in self._by_policy_jurisdiction:
            self._by_policy_jurisdiction[key] = []
        self._by_policy_jurisdiction[key].append(schema.schema_id)

    def get_schema(
        self,
        policy_type: str,
        jurisdiction: str,
        as_of: Optional[date] = None,
    ) -> FingerprintSchema:
        """
        Get the effective schema for a policy type and jurisdiction.

        Args:
            policy_type: Policy type (e.g., "auto")
            jurisdiction: Jurisdiction code (e.g., "CA-ON")
            as_of: Date to check effectiveness (defaults to today)

        Returns:
            The effective FingerprintSchema

        Raises:
            SchemaNotFoundError: If no schema matches
        """
        key = (policy_type, jurisdiction)
        schema_ids = self._by_policy_jurisdiction.get(key, [])

        if not schema_ids:
            raise SchemaNotFoundError(
                f"No schema found for policy_type='{policy_type}', "
                f"jurisdiction='{jurisdiction}'"
            )

        check_date = as_of or date.today()

        # Find effective schema
        for schema_id in schema_ids:
            schema = self._schemas[schema_id]
            if schema.is_effective_on(check_date):
                return schema

        # No effective schema found, return most recent
        # (for backward compatibility with cases before schema existed)
        return self._schemas[schema_ids[-1]]

    def get_schema_by_id(self, schema_id: str) -> FingerprintSchema:
        """
        Get a schema by its ID.

        Args:
            schema_id: The schema ID

        Returns:
            The FingerprintSchema

        Raises:
            SchemaNotFoundError: If schema not found
        """
        if schema_id not in self._schemas:
            raise SchemaNotFoundError(f"Schema not found: {schema_id}")
        return self._schemas[schema_id]

    def compute_fingerprint(
        self,
        schema: FingerprintSchema,
        facts: dict[str, Any],
        salt: str,
    ) -> str:
        """
        Compute fingerprint hash from facts using a schema.

        Args:
            schema: The FingerprintSchema to use
            facts: Dict of field_id -> value
            salt: Salt for privacy-preserving hashing

        Returns:
            64-character lowercase hex string (SHA-256)
        """
        if not salt:
            raise FingerprintSchemaError("salt cannot be empty")

        # Apply banding to get categorical facts
        banded = apply_banding(facts, schema)

        # Create canonical representation
        # Sort by field_id for deterministic ordering
        canonical_facts = {
            field_id: banded.get(field_id, "unknown")
            for field_id in sorted(schema.exclusion_relevant_facts)
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

def apply_banding(
    facts: dict[str, Any],
    schema: FingerprintSchema,
) -> dict[str, Any]:
    """
    Apply banding rules to convert continuous values to categorical.

    Args:
        facts: Dict of field_id -> value
        schema: The FingerprintSchema with banding rules

    Returns:
        Dict of field_id -> banded_value
    """
    result: dict[str, Any] = {}

    for field_id in schema.exclusion_relevant_facts:
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

def create_days_vacant_banding() -> BandingRule:
    """
    Banding rule for dwelling vacancy days.

    Bands:
    - 0: "occupied"
    - 1-30: "short"
    - 31-60: "medium"
    - 61+: "long"
    """
    return BandingRule(
        field_id="dwelling.days_vacant",
        bands=[
            (0, "occupied"),
            (30, "short"),
            (60, "medium"),
            (None, "long"),
        ],
    )


def create_coverage_months_banding() -> BandingRule:
    """
    Banding rule for member coverage duration in months.

    Bands:
    - 0-3: "new"
    - 4-11: "waiting"
    - 12+: "established"
    """
    return BandingRule(
        field_id="member.coverage_months",
        bands=[
            (3, "new"),
            (11, "waiting"),
            (None, "established"),
        ],
    )


def create_claim_amount_banding() -> BandingRule:
    """
    Banding rule for claim amounts.

    Bands:
    - 0-25k: "small"
    - 25k-100k: "medium"
    - 100k-500k: "large"
    - 500k+: "major"
    """
    return BandingRule(
        field_id="claim.amount",
        bands=[
            (25000, "small"),
            (100000, "medium"),
            (500000, "large"),
            (None, "major"),
        ],
    )


def create_treatment_cost_banding() -> BandingRule:
    """
    Banding rule for treatment costs.

    Bands:
    - 0-1k: "low"
    - 1k-10k: "medium"
    - 10k-50k: "high"
    - 50k+: "critical"
    """
    return BandingRule(
        field_id="treatment.cost",
        bands=[
            (1000, "low"),
            (10000, "medium"),
            (50000, "high"),
            (None, "critical"),
        ],
    )


# =============================================================================
# Built-in Schemas
# =============================================================================

def create_ontario_auto_schema_v1() -> FingerprintSchema:
    """
    Create the Ontario Auto (OAP 1) v1 fingerprint schema.

    This schema defines the facts relevant for auto insurance exclusion
    matching in Ontario, Canada.

    Relevant facts:
    - vehicle.use_at_loss: How vehicle was being used
    - driver.rideshare_app_active: Whether rideshare app was active
    - driver.bac_level_band: Blood alcohol content band
    - driver.license_status: License status at time of loss
    - driver.impairment_indicated: Whether impairment was indicated
    - loss.racing_activity: Whether racing was involved
    """
    # BAC banding rule
    bac_rule = BandingRule(
        field_id="driver.bac_level",
        bands=[
            (0.0, "none"),
            (0.05, "warning"),
            (0.08, "legal_limit"),
            (0.16, "elevated"),
            (None, "extreme"),
        ],
    )

    return FingerprintSchema(
        schema_id="claimpilot:oap1:auto:v1",
        policy_type="auto",
        jurisdiction="CA-ON",
        exclusion_relevant_facts=[
            "vehicle.use_at_loss",
            "driver.rideshare_app_active",
            "driver.bac_level",
            "driver.license_status",
            "driver.impairment_indicated",
            "loss.racing_activity",
        ],
        banding_rules={
            "driver.bac_level": bac_rule,
        },
        compatible_with=[],
    )


def create_property_ho3_schema_v1() -> FingerprintSchema:
    """
    Create the Property (HO-3) v1 fingerprint schema for Ontario.

    This schema defines facts relevant for property insurance exclusion
    matching in Ontario, Canada.

    Relevant facts:
    - loss.cause: Primary cause of loss (fire, water, wind, etc.)
    - water.source: Source of water damage if applicable
    - dwelling.days_vacant: Days property was vacant
    - arson.suspected: Whether arson is suspected
    """
    return FingerprintSchema(
        schema_id="claimpilot:ho3:property:v1",
        policy_type="property",
        jurisdiction="CA-ON",
        exclusion_relevant_facts=[
            "loss.cause",
            "water.source",
            "dwelling.days_vacant",
            "arson.suspected",
        ],
        banding_rules={
            "dwelling.days_vacant": create_days_vacant_banding(),
        },
        compatible_with=[],
    )


def create_marine_schema_v1() -> FingerprintSchema:
    """
    Create the Marine v1 fingerprint schema for Ontario.

    This schema defines facts relevant for marine insurance exclusion
    matching in Ontario, Canada.

    Relevant facts:
    - vessel.within_navigation_limits: Whether vessel was within covered area
    - operator.pcoc_valid: Whether operator had valid PCOC
    - vessel.commercial_use: Whether vessel was used commercially
    """
    return FingerprintSchema(
        schema_id="claimpilot:marine:v1",
        policy_type="marine",
        jurisdiction="CA-ON",
        exclusion_relevant_facts=[
            "vessel.within_navigation_limits",
            "operator.pcoc_valid",
            "vessel.commercial_use",
        ],
        banding_rules={},
        compatible_with=[],
    )


def create_health_schema_v1() -> FingerprintSchema:
    """
    Create the Health v1 fingerprint schema for Ontario.

    This schema defines facts relevant for health insurance exclusion
    matching in Ontario, Canada.

    Relevant facts:
    - drug.on_formulary: Whether drug is on formulary
    - condition.preexisting: Whether condition is pre-existing
    - member.coverage_months: Duration of coverage in months
    """
    return FingerprintSchema(
        schema_id="claimpilot:health:v1",
        policy_type="health",
        jurisdiction="CA-ON",
        exclusion_relevant_facts=[
            "drug.on_formulary",
            "condition.preexisting",
            "member.coverage_months",
        ],
        banding_rules={
            "member.coverage_months": create_coverage_months_banding(),
        },
        compatible_with=[],
    )


def create_wsib_schema_v1() -> FingerprintSchema:
    """
    Create the WSIB v1 fingerprint schema for Ontario.

    This schema defines facts relevant for WSIB (workers' compensation)
    exclusion matching in Ontario, Canada.

    Relevant facts:
    - injury.work_related: Whether injury occurred at work
    - injury.arose_out_of_employment: Whether injury arose from employment
    - injury.intoxication_sole_cause: Whether intoxication was sole cause
    """
    return FingerprintSchema(
        schema_id="claimpilot:wsib:v1",
        policy_type="wsib",
        jurisdiction="CA-ON",
        exclusion_relevant_facts=[
            "injury.work_related",
            "injury.arose_out_of_employment",
            "injury.intoxication_sole_cause",
        ],
        banding_rules={},
        compatible_with=[],
    )


def create_cgl_schema_v1() -> FingerprintSchema:
    """
    Create the CGL (Commercial General Liability) v1 fingerprint schema.

    This schema defines facts relevant for CGL insurance exclusion
    matching in Ontario, Canada.

    Relevant facts:
    - injury.expected_intended: Whether injury was expected/intended
    - loss.pollution_related: Whether loss involved pollution
    - loss.auto_involved: Whether an automobile was involved
    """
    return FingerprintSchema(
        schema_id="claimpilot:cgl:v1",
        policy_type="cgl",
        jurisdiction="CA-ON",
        exclusion_relevant_facts=[
            "injury.expected_intended",
            "loss.pollution_related",
            "loss.auto_involved",
        ],
        banding_rules={},
        compatible_with=[],
    )


def create_eo_schema_v1() -> FingerprintSchema:
    """
    Create the E&O (Errors & Omissions) v1 fingerprint schema.

    This schema defines facts relevant for E&O insurance exclusion
    matching in Ontario, Canada.

    Relevant facts:
    - claim.first_made_during_policy: Whether claim was first made during policy
    - wrongful_act.before_retro_date: Whether wrongful act was before retro date
    """
    return FingerprintSchema(
        schema_id="claimpilot:eo:v1",
        policy_type="eo",
        jurisdiction="CA-ON",
        exclusion_relevant_facts=[
            "claim.first_made_during_policy",
            "wrongful_act.before_retro_date",
        ],
        banding_rules={},
        compatible_with=[],
    )


def create_travel_schema_v1() -> FingerprintSchema:
    """
    Create the Travel v1 fingerprint schema for Ontario.

    This schema defines facts relevant for travel insurance exclusion
    matching in Ontario, Canada.

    Relevant facts:
    - location.outside_home_province: Whether treatment was outside home province
    - treatment.emergency: Whether treatment was emergency
    - condition.stable_90_days: Whether condition was stable for 90 days
    """
    return FingerprintSchema(
        schema_id="claimpilot:travel:v1",
        policy_type="travel",
        jurisdiction="CA-ON",
        exclusion_relevant_facts=[
            "location.outside_home_province",
            "treatment.emergency",
            "condition.stable_90_days",
        ],
        banding_rules={},
        compatible_with=[],
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Exceptions
    "FingerprintSchemaError",
    "SchemaNotFoundError",
    "BandingError",

    # Data classes
    "BandingRule",
    "FingerprintSchema",

    # Registry
    "FingerprintSchemaRegistry",

    # Functions
    "apply_banding",

    # Banding rule factories
    "create_days_vacant_banding",
    "create_coverage_months_banding",
    "create_claim_amount_banding",
    "create_treatment_cost_banding",

    # Schema factories
    "create_ontario_auto_schema_v1",
    "create_property_ho3_schema_v1",
    "create_marine_schema_v1",
    "create_health_schema_v1",
    "create_wsib_schema_v1",
    "create_cgl_schema_v1",
    "create_eo_schema_v1",
    "create_travel_schema_v1",
]
