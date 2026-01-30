"""
ClaimPilot Policy Models

Policy packs define coverage rules for specific insurance products.
Loaded from YAML/JSON at runtime — not hardcoded.

Key components:
- Policy: Top-level container for an insurance product
- CoverageSection: Individual coverage within a policy
- Exclusion: Condition that negates coverage
- Coverage limits and deductibles
- Loss type triggers

Policies are line-of-business agnostic — the same models work for
auto, property, health, workers comp, etc.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import uuid4

from .enums import ClaimantType, LineOfBusiness
from .conditions import Condition
from .authority import AuthorityRef


# =============================================================================
# Coverage Limits and Deductibles
# =============================================================================

@dataclass
class CoverageLimits:
    """
    Coverage limits for a coverage section.

    All monetary values use Decimal for precision.
    """
    per_occurrence: Optional[Decimal] = None
    per_person: Optional[Decimal] = None
    per_accident: Optional[Decimal] = None
    aggregate: Optional[Decimal] = None
    property_damage: Optional[Decimal] = None
    bodily_injury: Optional[Decimal] = None
    currency: str = "USD"

    def get_applicable_limit(self, limit_type: str) -> Optional[Decimal]:
        """Get limit by type name."""
        return getattr(self, limit_type, None)


@dataclass
class Deductibles:
    """
    Deductible configuration for a coverage section.

    All monetary values use Decimal for precision.
    """
    standard: Optional[Decimal] = None
    collision: Optional[Decimal] = None
    comprehensive: Optional[Decimal] = None
    per_claim: Optional[Decimal] = None
    per_occurrence: Optional[Decimal] = None
    annual_aggregate: Optional[Decimal] = None
    currency: str = "USD"

    def get_applicable_deductible(self, deductible_type: str) -> Optional[Decimal]:
        """Get deductible by type name."""
        return getattr(self, deductible_type, None)


# =============================================================================
# Loss Type Trigger
# =============================================================================

@dataclass
class LossTypeTrigger:
    """
    Defines what loss types activate a coverage.

    A coverage is triggered when the claim's loss type matches
    and the claimant type is in the allowed list.
    """
    loss_type: str  # e.g., "collision", "fire", "slip_and_fall"
    claimant_types: list[ClaimantType] = field(default_factory=list)  # Empty = all

    def matches(self, claim_loss_type: str, claimant_type: ClaimantType) -> bool:
        """Check if this trigger matches the claim."""
        if self.loss_type != claim_loss_type:
            return False
        if self.claimant_types and claimant_type not in self.claimant_types:
            return False
        return True


# =============================================================================
# Coverage Section
# =============================================================================

@dataclass
class CoverageSection:
    """
    A section of coverage within a policy.

    Represents a specific type of coverage (e.g., Collision, Comprehensive,
    Bodily Injury Liability) with its own triggers, preconditions, limits,
    and deductibles.

    Attributes:
        id: Unique identifier within the policy
        code: Short code (e.g., "Section A", "Part 1")
        name: Human-readable name
        description: Detailed description of the coverage
        triggers: Loss types that activate this coverage
        preconditions: Conditions that must be true for coverage to apply
        limits: Coverage limits
        deductibles: Deductible amounts
        authority_ref: Citation to policy wording
    """
    id: str
    code: str
    name: str
    description: str

    # When this coverage is triggered
    triggers: list[LossTypeTrigger] = field(default_factory=list)

    # What must be true for coverage to apply
    preconditions: list[Condition] = field(default_factory=list)

    # Coverage details
    limits: Optional[CoverageLimits] = None
    deductibles: Optional[Deductibles] = None

    # Citation to policy wording
    authority_ref: Optional[AuthorityRef] = None

    # Optional: exclusions specific to this coverage
    exclusion_ids: list[str] = field(default_factory=list)

    # Metadata
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    enabled: bool = True

    def is_triggered_by(self, loss_type: str, claimant_type: ClaimantType) -> bool:
        """Check if any trigger matches the claim."""
        if not self.triggers:
            return True  # No triggers = always triggered
        return any(t.matches(loss_type, claimant_type) for t in self.triggers)

    def is_effective_on(self, check_date: date) -> bool:
        """Check if coverage is effective on a given date."""
        if self.effective_date and check_date < self.effective_date:
            return False
        if self.expiry_date and check_date > self.expiry_date:
            return False
        return True


# =============================================================================
# Exclusion
# =============================================================================

@dataclass
class Exclusion:
    """
    An exclusion that may negate coverage.

    Exclusions are evaluated after coverage is triggered. If the
    exclusion's conditions are satisfied, coverage is denied.

    Attributes:
        id: Unique identifier
        code: Policy reference code (e.g., "4.2.1")
        name: Human-readable name (e.g., "Commercial Use")
        description: Detailed description
        policy_wording: Actual text from the policy
        policy_section_ref: Reference to policy section
        applies_to_coverages: Coverage IDs this exclusion can negate
        trigger_conditions: When to evaluate this exclusion
        evaluation_questions: Questions for adjuster guidance
        evidence_to_confirm: Evidence needed to confirm exclusion applies
        evidence_to_rule_out: Evidence needed to rule out exclusion
        authority_ref: Citation to the exclusion text
    """
    id: str
    code: str
    name: str
    description: str

    # The actual policy language
    policy_wording: str
    policy_section_ref: str

    # Which coverages this exclusion can negate
    applies_to_coverages: list[str] = field(default_factory=list)  # Coverage IDs

    # When to evaluate this exclusion
    trigger_conditions: list[Condition] = field(default_factory=list)

    # Guidance for adjuster
    evaluation_questions: list[str] = field(default_factory=list)

    # What evidence is needed
    evidence_to_confirm: list[str] = field(default_factory=list)
    evidence_to_rule_out: list[str] = field(default_factory=list)

    # Citation
    authority_ref: Optional[AuthorityRef] = None

    # Metadata
    severity: str = "standard"  # "standard", "strict", "absolute"
    enabled: bool = True

    def applies_to_coverage(self, coverage_id: str) -> bool:
        """Check if this exclusion applies to a specific coverage."""
        if not self.applies_to_coverages:
            return True  # Empty = applies to all
        return coverage_id in self.applies_to_coverages


# =============================================================================
# Policy
# =============================================================================

@dataclass
class Policy:
    """
    A policy pack defining coverage rules for an insurance product.

    Loaded from YAML/JSON at runtime. Contains all the rules needed
    to evaluate claims for a specific insurance product.

    Attributes:
        id: Unique identifier (e.g., "ON-OAP1-2024")
        jurisdiction: Applicable jurisdiction (e.g., "CA-ON", "US-NY")
        line_of_business: Insurance line (auto, property, etc.)
        product_code: Product identifier (e.g., "OAP1", "HO-3")
        name: Human-readable name
        version: Version string (e.g., "2024.1")
        effective_date: When this policy version becomes effective
        expiry_date: When this policy version expires
        coverage_sections: List of coverages
        exclusions: List of exclusions
        conditions: Reusable condition definitions
        evidence_rules: Evidence requirements
        authority_rules: Escalation rules
        timeline_rules: Regulatory timeline requirements
    """
    id: str
    jurisdiction: str
    line_of_business: LineOfBusiness
    product_code: str
    name: str
    version: str
    effective_date: date

    # Optional expiry
    expiry_date: Optional[date] = None

    # Coverage and exclusions
    coverage_sections: list[CoverageSection] = field(default_factory=list)
    exclusions: list[Exclusion] = field(default_factory=list)

    # Reusable conditions (referenced by ID)
    conditions: dict[str, Condition] = field(default_factory=dict)

    # Rules (references to other models - resolved at load time)
    evidence_rule_ids: list[str] = field(default_factory=list)
    authority_rule_ids: list[str] = field(default_factory=list)
    timeline_rule_ids: list[str] = field(default_factory=list)

    # Metadata
    description: Optional[str] = None
    issuer: Optional[str] = None  # Insurance company
    regulatory_body: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_effective_on(self, check_date: date) -> bool:
        """Check if this policy version is effective on a given date."""
        if check_date < self.effective_date:
            return False
        if self.expiry_date and check_date > self.expiry_date:
            return False
        return True

    @property
    def is_currently_effective(self) -> bool:
        """Check if policy is currently effective."""
        return self.is_effective_on(date.today())

    def get_coverage(self, coverage_id: str) -> Optional[CoverageSection]:
        """Get a coverage section by ID."""
        for coverage in self.coverage_sections:
            if coverage.id == coverage_id:
                return coverage
        return None

    def get_exclusion(self, exclusion_id: str) -> Optional[Exclusion]:
        """Get an exclusion by ID."""
        for exclusion in self.exclusions:
            if exclusion.id == exclusion_id:
                return exclusion
        return None

    def get_condition(self, condition_id: str) -> Optional[Condition]:
        """Get a reusable condition by ID."""
        return self.conditions.get(condition_id)

    def get_applicable_coverages(
        self,
        loss_type: str,
        claimant_type: ClaimantType,
        loss_date: date,
    ) -> list[CoverageSection]:
        """
        Get all coverages that might apply to a claim.

        Filters by:
        - Coverage is enabled
        - Coverage is effective on loss date
        - Coverage is triggered by loss type and claimant type
        """
        return [
            c for c in self.coverage_sections
            if c.enabled
            and c.is_effective_on(loss_date)
            and c.is_triggered_by(loss_type, claimant_type)
        ]

    def get_applicable_exclusions(self, coverage_id: str) -> list[Exclusion]:
        """Get all exclusions that apply to a specific coverage."""
        return [
            e for e in self.exclusions
            if e.enabled and e.applies_to_coverage(coverage_id)
        ]

    @classmethod
    def create(
        cls,
        jurisdiction: str,
        line_of_business: LineOfBusiness,
        product_code: str,
        name: str,
        version: str,
        effective_date: date,
    ) -> Policy:
        """Factory method to create a new Policy with auto-generated ID."""
        policy_id = f"{jurisdiction}-{product_code}-{version}".upper()
        return cls(
            id=policy_id,
            jurisdiction=jurisdiction,
            line_of_business=line_of_business,
            product_code=product_code,
            name=name,
            version=version,
            effective_date=effective_date,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize policy metadata to dictionary (not full pack)."""
        return {
            "id": self.id,
            "jurisdiction": self.jurisdiction,
            "line_of_business": self.line_of_business.value,
            "product_code": self.product_code,
            "name": self.name,
            "version": self.version,
            "effective_date": self.effective_date.isoformat(),
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "coverage_count": len(self.coverage_sections),
            "exclusion_count": len(self.exclusions),
        }
