"""
ClaimPilot Precedent System: Reason Code Registry Module

This module implements the registry for reason codes used in JUDGMENT cells.
Reason codes provide standardized, auditable identifiers for decision rationales.

Key components:
- ReasonCodeDefinition: Definition of a single reason code
- ReasonCodeRegistry: Registry of reason codes by registry ID

Design Principles:
- Standardized: Codes follow consistent naming conventions
- Versioned: Registries are versioned to track code evolution
- Self-documenting: Each code includes description and policy references
- Deterministic: Code lookup and validation are predictable

Example:
    >>> registry = ReasonCodeRegistry()
    >>> defn = registry.get_definition("RC-4.2.1")
    >>> print(defn.name)
    "Commercial Use Exclusion"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional


# =============================================================================
# Exceptions
# =============================================================================

class ReasonCodeError(Exception):
    """Base exception for reason code errors."""
    pass


class ReasonCodeNotFoundError(ReasonCodeError):
    """Raised when a reason code is not found in the registry."""
    pass


class RegistryNotFoundError(ReasonCodeError):
    """Raised when a registry ID is not found."""
    pass


class InvalidReasonCodeError(ReasonCodeError):
    """Raised when a reason code is invalid."""
    pass


# =============================================================================
# Reason Code Definition
# =============================================================================

@dataclass
class ReasonCodeDefinition:
    """
    Definition of a single reason code.

    Reason codes are standardized identifiers for decision rationales.
    They enable consistent categorization and precedent matching.

    Attributes:
        code: The reason code (e.g., "RC-4.2.1", "RC-COMMERCIAL-USE")
        name: Human-readable name
        description: Detailed description of what this code means
        policy_ref: Reference to policy section (e.g., "OAP 1 Section 4.2.1")
        category: Category for grouping (e.g., "exclusion", "coverage", "procedural")
        severity: Severity level (e.g., "blocking", "warning", "informational")
        effective_from: When this code became effective
        effective_to: When this code was deprecated (None = current)
        superseded_by: Code that replaced this one (if deprecated)
    """
    code: str
    name: str
    description: str
    policy_ref: str
    category: str = "exclusion"
    severity: str = "blocking"
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    superseded_by: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate reason code definition on construction."""
        if not self.code:
            raise InvalidReasonCodeError("code cannot be empty")
        if not self.name:
            raise InvalidReasonCodeError("name cannot be empty")
        if not self.description:
            raise InvalidReasonCodeError("description cannot be empty")

    def is_effective_on(self, check_date: date) -> bool:
        """Check if this code is effective on a given date."""
        if self.effective_from and check_date < self.effective_from:
            return False
        if self.effective_to and check_date > self.effective_to:
            return False
        return True

    @property
    def is_deprecated(self) -> bool:
        """Check if this code is deprecated."""
        return self.effective_to is not None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        result: dict[str, Any] = {
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "policy_ref": self.policy_ref,
            "category": self.category,
            "severity": self.severity,
        }
        if self.effective_from:
            result["effective_from"] = self.effective_from.isoformat()
        if self.effective_to:
            result["effective_to"] = self.effective_to.isoformat()
        if self.superseded_by:
            result["superseded_by"] = self.superseded_by
        return result


# =============================================================================
# Reason Code Registry
# =============================================================================

@dataclass
class ReasonCodeRegistryDefinition:
    """
    Definition of a reason code registry (collection of codes).

    Attributes:
        registry_id: Unique identifier (e.g., "claimpilot:auto:v1")
        name: Human-readable name
        description: Description of this registry
        policy_type: Policy type this registry applies to
        jurisdiction: Jurisdiction this registry applies to
        version: Version of this registry
        codes: Dict mapping code to ReasonCodeDefinition
    """
    registry_id: str
    name: str
    description: str
    policy_type: str
    jurisdiction: str
    version: str
    codes: dict[str, ReasonCodeDefinition] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate registry on construction."""
        if not self.registry_id:
            raise ReasonCodeError("registry_id cannot be empty")
        if not self.name:
            raise ReasonCodeError("name cannot be empty")


class ReasonCodeRegistry:
    """
    Registry of reason codes organized by registry ID.

    The registry provides lookup and validation of reason codes used
    in JUDGMENT cells for consistent precedent matching.

    Usage:
        >>> registry = ReasonCodeRegistry()
        >>> defn = registry.get_definition("RC-4.2.1", "claimpilot:auto:v1")
        >>> is_valid = registry.validate_code("RC-4.2.1", "claimpilot:auto:v1")
    """

    def __init__(self) -> None:
        """Initialize with built-in registries."""
        self._registries: dict[str, ReasonCodeRegistryDefinition] = {}
        self._register_builtin_registries()

    def _register_builtin_registries(self) -> None:
        """Register built-in reason code registries."""
        self.register_registry(create_ontario_auto_registry_v1())
        self.register_registry(create_property_registry_v1())
        self.register_registry(create_marine_registry_v1())
        self.register_registry(create_health_registry_v1())
        self.register_registry(create_wsib_registry_v1())
        self.register_registry(create_cgl_registry_v1())
        self.register_registry(create_eo_registry_v1())
        self.register_registry(create_travel_registry_v1())

    def register_registry(self, registry: ReasonCodeRegistryDefinition) -> None:
        """
        Register a reason code registry.

        Args:
            registry: The ReasonCodeRegistryDefinition to register
        """
        self._registries[registry.registry_id] = registry

    def get_registry(self, registry_id: str) -> ReasonCodeRegistryDefinition:
        """
        Get a registry by ID.

        Args:
            registry_id: The registry ID

        Returns:
            The ReasonCodeRegistryDefinition

        Raises:
            RegistryNotFoundError: If registry not found
        """
        if registry_id not in self._registries:
            raise RegistryNotFoundError(f"Registry not found: {registry_id}")
        return self._registries[registry_id]

    def get_definition(
        self,
        code: str,
        registry_id: Optional[str] = None,
    ) -> ReasonCodeDefinition:
        """
        Get a reason code definition.

        If registry_id is not specified, searches all registries.

        Args:
            code: The reason code
            registry_id: Optional registry ID to search in

        Returns:
            The ReasonCodeDefinition

        Raises:
            ReasonCodeNotFoundError: If code not found
            RegistryNotFoundError: If specified registry not found
        """
        if registry_id:
            registry = self.get_registry(registry_id)
            if code not in registry.codes:
                raise ReasonCodeNotFoundError(
                    f"Code '{code}' not found in registry '{registry_id}'"
                )
            return registry.codes[code]

        # Search all registries
        for registry in self._registries.values():
            if code in registry.codes:
                return registry.codes[code]

        raise ReasonCodeNotFoundError(f"Code '{code}' not found in any registry")

    def validate_code(
        self,
        code: str,
        registry_id: Optional[str] = None,
    ) -> bool:
        """
        Validate that a reason code exists.

        Args:
            code: The reason code to validate
            registry_id: Optional registry ID to check in

        Returns:
            True if code exists, False otherwise
        """
        try:
            self.get_definition(code, registry_id)
            return True
        except (ReasonCodeNotFoundError, RegistryNotFoundError):
            return False

    def validate_codes(
        self,
        codes: list[str],
        registry_id: str,
    ) -> tuple[list[str], list[str]]:
        """
        Validate a list of reason codes.

        Args:
            codes: List of reason codes to validate
            registry_id: Registry ID to check in

        Returns:
            Tuple of (valid_codes, invalid_codes)
        """
        valid: list[str] = []
        invalid: list[str] = []

        for code in codes:
            if self.validate_code(code, registry_id):
                valid.append(code)
            else:
                invalid.append(code)

        return valid, invalid

    def get_codes_by_category(
        self,
        category: str,
        registry_id: str,
    ) -> list[ReasonCodeDefinition]:
        """
        Get all codes in a category.

        Args:
            category: The category to filter by
            registry_id: The registry ID to search in

        Returns:
            List of ReasonCodeDefinitions in the category
        """
        registry = self.get_registry(registry_id)
        return [
            defn for defn in registry.codes.values()
            if defn.category == category
        ]

    def list_registries(self) -> list[str]:
        """List all registered registry IDs."""
        return list(self._registries.keys())


# =============================================================================
# Built-in Registries
# =============================================================================

def create_ontario_auto_registry_v1() -> ReasonCodeRegistryDefinition:
    """
    Create the Ontario Auto (OAP 1) v1 reason code registry.

    This registry contains reason codes for Ontario auto insurance
    exclusion decisions under the OAP 1 policy form.
    """
    codes: dict[str, ReasonCodeDefinition] = {}

    # Commercial Use Exclusions (Section 4.2)
    codes["RC-4.2.1"] = ReasonCodeDefinition(
        code="RC-4.2.1",
        name="Commercial Use Exclusion",
        description="Vehicle was being used for commercial purposes at the time of loss, "
                   "which is excluded from coverage under the policy.",
        policy_ref="OAP 1 Section 4.2.1",
        category="exclusion",
        severity="blocking",
    )

    codes["RC-COMMERCIAL-USE"] = ReasonCodeDefinition(
        code="RC-COMMERCIAL-USE",
        name="Commercial Use - General",
        description="General commercial use exclusion where specific section not determined.",
        policy_ref="OAP 1 Section 4.2",
        category="exclusion",
        severity="blocking",
    )

    # Rideshare/TNP Exclusions
    codes["RC-4.2.1-RIDESHARE"] = ReasonCodeDefinition(
        code="RC-4.2.1-RIDESHARE",
        name="Rideshare/TNP Exclusion",
        description="Vehicle was being used for transportation network purposes (rideshare) "
                   "at the time of loss without appropriate endorsement.",
        policy_ref="OAP 1 Section 4.2.1",
        category="exclusion",
        severity="blocking",
    )

    # Impairment Exclusions (Section 4.3)
    codes["RC-4.3.1"] = ReasonCodeDefinition(
        code="RC-4.3.1",
        name="Impairment - Alcohol Exclusion",
        description="Driver was impaired by alcohol at the time of loss.",
        policy_ref="OAP 1 Section 4.3.1",
        category="exclusion",
        severity="blocking",
    )

    codes["RC-4.3.2"] = ReasonCodeDefinition(
        code="RC-4.3.2",
        name="Impairment - Drugs Exclusion",
        description="Driver was impaired by drugs at the time of loss.",
        policy_ref="OAP 1 Section 4.3.2",
        category="exclusion",
        severity="blocking",
    )

    codes["RC-4.3.3"] = ReasonCodeDefinition(
        code="RC-4.3.3",
        name="Impairment - Combined Exclusion",
        description="Driver was impaired by combination of alcohol and drugs at the time of loss.",
        policy_ref="OAP 1 Section 4.3.3",
        category="exclusion",
        severity="blocking",
    )

    # Racing/Competition Exclusions (Section 4.4)
    codes["RC-4.4.1"] = ReasonCodeDefinition(
        code="RC-4.4.1",
        name="Racing Exclusion",
        description="Vehicle was being used in a race or speed test at the time of loss.",
        policy_ref="OAP 1 Section 4.4.1",
        category="exclusion",
        severity="blocking",
    )

    # License Status (Section 4.5)
    codes["RC-4.5.1"] = ReasonCodeDefinition(
        code="RC-4.5.1",
        name="Unlicensed Driver Exclusion",
        description="Driver did not hold a valid driver's license at the time of loss.",
        policy_ref="OAP 1 Section 4.5.1",
        category="exclusion",
        severity="blocking",
    )

    codes["RC-4.5.2"] = ReasonCodeDefinition(
        code="RC-4.5.2",
        name="Suspended License Exclusion",
        description="Driver's license was suspended at the time of loss.",
        policy_ref="OAP 1 Section 4.5.2",
        category="exclusion",
        severity="blocking",
    )

    # Coverage Reason Codes
    codes["RC-COV-CONFIRMED"] = ReasonCodeDefinition(
        code="RC-COV-CONFIRMED",
        name="Coverage Confirmed",
        description="All coverage requirements are met and no exclusions apply.",
        policy_ref="OAP 1",
        category="coverage",
        severity="informational",
    )

    codes["RC-COV-PARTIAL"] = ReasonCodeDefinition(
        code="RC-COV-PARTIAL",
        name="Partial Coverage",
        description="Some coverages apply but others may be excluded or limited.",
        policy_ref="OAP 1",
        category="coverage",
        severity="warning",
    )

    # Procedural Reason Codes
    codes["RC-PROC-ESCALATE"] = ReasonCodeDefinition(
        code="RC-PROC-ESCALATE",
        name="Escalation Required",
        description="Case requires escalation to higher authority for decision.",
        policy_ref="Internal Guidelines",
        category="procedural",
        severity="informational",
    )

    codes["RC-PROC-INFO-NEEDED"] = ReasonCodeDefinition(
        code="RC-PROC-INFO-NEEDED",
        name="Additional Information Required",
        description="Cannot make determination without additional information.",
        policy_ref="Internal Guidelines",
        category="procedural",
        severity="warning",
    )

    return ReasonCodeRegistryDefinition(
        registry_id="claimpilot:auto:v1",
        name="ClaimPilot Ontario Auto Reason Codes v1",
        description="Reason codes for Ontario auto insurance decisions under OAP 1",
        policy_type="auto",
        jurisdiction="CA-ON",
        version="1.0",
        codes=codes,
    )


def create_property_registry_v1() -> ReasonCodeRegistryDefinition:
    """
    Create the Property (HO-3) v1 reason code registry.

    This registry contains reason codes for property insurance
    exclusion decisions under HO-3 style policy forms.
    """
    codes: dict[str, ReasonCodeDefinition] = {}

    # Flood Exclusion
    codes["RC-FLOOD"] = ReasonCodeDefinition(
        code="RC-FLOOD",
        name="Flood Exclusion",
        description="Loss caused by flood, which is excluded from coverage.",
        policy_ref="HO-3 Exclusions - Water",
        category="exclusion",
        severity="blocking",
    )

    # Earthquake Exclusion
    codes["RC-EARTH"] = ReasonCodeDefinition(
        code="RC-EARTH",
        name="Earth Movement Exclusion",
        description="Loss caused by earthquake, landslide, or other earth movement.",
        policy_ref="HO-3 Exclusions - Earth Movement",
        category="exclusion",
        severity="blocking",
    )

    # Vacancy Exclusion
    codes["RC-VACANT"] = ReasonCodeDefinition(
        code="RC-VACANT",
        name="Vacancy Exclusion",
        description="Loss occurred while property was vacant beyond policy limits.",
        policy_ref="HO-3 Vacancy Provisions",
        category="exclusion",
        severity="blocking",
    )

    # Gradual Deterioration
    codes["RC-GRADUAL"] = ReasonCodeDefinition(
        code="RC-GRADUAL",
        name="Gradual Deterioration Exclusion",
        description="Loss caused by gradual deterioration, wear and tear, or maintenance neglect.",
        policy_ref="HO-3 Exclusions - Maintenance",
        category="exclusion",
        severity="blocking",
    )

    # Intentional Loss
    codes["RC-INTENT"] = ReasonCodeDefinition(
        code="RC-INTENT",
        name="Intentional Loss Exclusion",
        description="Loss was intentionally caused by an insured.",
        policy_ref="HO-3 Exclusions - Intentional Acts",
        category="exclusion",
        severity="blocking",
    )

    # Coverage codes
    codes["RC-COV-CONFIRMED"] = ReasonCodeDefinition(
        code="RC-COV-CONFIRMED",
        name="Coverage Confirmed",
        description="All coverage requirements are met and no exclusions apply.",
        policy_ref="HO-3",
        category="coverage",
        severity="informational",
    )

    return ReasonCodeRegistryDefinition(
        registry_id="claimpilot:property:v1",
        name="ClaimPilot Property Reason Codes v1",
        description="Reason codes for property insurance decisions under HO-3",
        policy_type="property",
        jurisdiction="CA-ON",
        version="1.0",
        codes=codes,
    )


def create_marine_registry_v1() -> ReasonCodeRegistryDefinition:
    """
    Create the Marine v1 reason code registry.

    This registry contains reason codes for marine insurance
    exclusion decisions.
    """
    codes: dict[str, ReasonCodeDefinition] = {}

    # Navigation Limits
    codes["RC-NAV"] = ReasonCodeDefinition(
        code="RC-NAV",
        name="Navigation Limits Exclusion",
        description="Vessel was outside covered navigation limits at time of loss.",
        policy_ref="Marine Policy - Navigation Warranty",
        category="exclusion",
        severity="blocking",
    )

    # PCOC (Pleasure Craft Operator Card)
    codes["RC-PCOC"] = ReasonCodeDefinition(
        code="RC-PCOC",
        name="Invalid PCOC Exclusion",
        description="Operator did not hold valid Pleasure Craft Operator Card.",
        policy_ref="Marine Policy - Operator Requirements",
        category="exclusion",
        severity="blocking",
    )

    # Commercial Use
    codes["RC-COMM"] = ReasonCodeDefinition(
        code="RC-COMM",
        name="Commercial Use Exclusion",
        description="Vessel was being used for commercial purposes without endorsement.",
        policy_ref="Marine Policy - Use Restrictions",
        category="exclusion",
        severity="blocking",
    )

    # Racing
    codes["RC-RACE"] = ReasonCodeDefinition(
        code="RC-RACE",
        name="Racing Exclusion",
        description="Loss occurred while vessel was engaged in racing.",
        policy_ref="Marine Policy - Racing Exclusion",
        category="exclusion",
        severity="blocking",
    )

    # Ice Damage
    codes["RC-ICE"] = ReasonCodeDefinition(
        code="RC-ICE",
        name="Ice Damage Exclusion",
        description="Loss caused by ice damage during off-season storage period.",
        policy_ref="Marine Policy - Seasonal Exclusions",
        category="exclusion",
        severity="blocking",
    )

    # Coverage codes
    codes["RC-COV-CONFIRMED"] = ReasonCodeDefinition(
        code="RC-COV-CONFIRMED",
        name="Coverage Confirmed",
        description="All coverage requirements are met and no exclusions apply.",
        policy_ref="Marine Policy",
        category="coverage",
        severity="informational",
    )

    return ReasonCodeRegistryDefinition(
        registry_id="claimpilot:marine:v1",
        name="ClaimPilot Marine Reason Codes v1",
        description="Reason codes for marine insurance decisions",
        policy_type="marine",
        jurisdiction="CA-ON",
        version="1.0",
        codes=codes,
    )


def create_health_registry_v1() -> ReasonCodeRegistryDefinition:
    """
    Create the Health v1 reason code registry.

    This registry contains reason codes for health insurance
    exclusion decisions.
    """
    codes: dict[str, ReasonCodeDefinition] = {}

    # Formulary Exclusion
    codes["RC-FORM"] = ReasonCodeDefinition(
        code="RC-FORM",
        name="Non-Formulary Drug Exclusion",
        description="Drug is not on the approved formulary list.",
        policy_ref="Health Policy - Drug Coverage",
        category="exclusion",
        severity="blocking",
    )

    # Pre-existing Condition
    codes["RC-PRE"] = ReasonCodeDefinition(
        code="RC-PRE",
        name="Pre-existing Condition Exclusion",
        description="Condition existed prior to coverage effective date.",
        policy_ref="Health Policy - Pre-existing Conditions",
        category="exclusion",
        severity="blocking",
    )

    # Work-Related
    codes["RC-WORK"] = ReasonCodeDefinition(
        code="RC-WORK",
        name="Work-Related Condition Exclusion",
        description="Condition is work-related and should be covered by workers' compensation.",
        policy_ref="Health Policy - Coordination of Benefits",
        category="exclusion",
        severity="blocking",
    )

    # Cosmetic
    codes["RC-COSM"] = ReasonCodeDefinition(
        code="RC-COSM",
        name="Cosmetic Procedure Exclusion",
        description="Procedure is considered cosmetic and not medically necessary.",
        policy_ref="Health Policy - Cosmetic Exclusions",
        category="exclusion",
        severity="blocking",
    )

    # Experimental
    codes["RC-EXP"] = ReasonCodeDefinition(
        code="RC-EXP",
        name="Experimental Treatment Exclusion",
        description="Treatment is experimental or investigational.",
        policy_ref="Health Policy - Experimental Exclusions",
        category="exclusion",
        severity="blocking",
    )

    # Coverage codes
    codes["RC-COV-CONFIRMED"] = ReasonCodeDefinition(
        code="RC-COV-CONFIRMED",
        name="Coverage Confirmed",
        description="All coverage requirements are met and no exclusions apply.",
        policy_ref="Health Policy",
        category="coverage",
        severity="informational",
    )

    return ReasonCodeRegistryDefinition(
        registry_id="claimpilot:health:v1",
        name="ClaimPilot Health Reason Codes v1",
        description="Reason codes for health insurance decisions",
        policy_type="health",
        jurisdiction="CA-ON",
        version="1.0",
        codes=codes,
    )


def create_wsib_registry_v1() -> ReasonCodeRegistryDefinition:
    """
    Create the WSIB v1 reason code registry.

    This registry contains reason codes for WSIB (workers' compensation)
    benefit decisions.
    """
    codes: dict[str, ReasonCodeDefinition] = {}

    # Not Work Related
    codes["RC-NWR"] = ReasonCodeDefinition(
        code="RC-NWR",
        name="Not Work Related",
        description="Injury did not occur in the course of employment.",
        policy_ref="WSIA s. 13",
        category="exclusion",
        severity="blocking",
    )

    # Pre-existing Condition
    codes["RC-PRE"] = ReasonCodeDefinition(
        code="RC-PRE",
        name="Pre-existing Condition",
        description="Condition existed prior to claimed workplace injury.",
        policy_ref="WSIA s. 13",
        category="exclusion",
        severity="blocking",
    )

    # Intoxication
    codes["RC-INTOX"] = ReasonCodeDefinition(
        code="RC-INTOX",
        name="Intoxication Exclusion",
        description="Injury caused solely by worker's intoxication.",
        policy_ref="WSIA s. 17",
        category="exclusion",
        severity="blocking",
    )

    # Self-Inflicted
    codes["RC-SELF"] = ReasonCodeDefinition(
        code="RC-SELF",
        name="Self-Inflicted Injury",
        description="Injury was willfully and intentionally self-inflicted.",
        policy_ref="WSIA s. 17",
        category="exclusion",
        severity="blocking",
    )

    # Serious and Willful Misconduct
    codes["RC-MISC"] = ReasonCodeDefinition(
        code="RC-MISC",
        name="Serious Misconduct",
        description="Injury resulted from worker's serious and willful misconduct.",
        policy_ref="WSIA s. 17",
        category="exclusion",
        severity="blocking",
    )

    # Coverage codes
    codes["RC-COV-CONFIRMED"] = ReasonCodeDefinition(
        code="RC-COV-CONFIRMED",
        name="Entitlement Confirmed",
        description="All entitlement requirements are met and no exclusions apply.",
        policy_ref="WSIA",
        category="coverage",
        severity="informational",
    )

    return ReasonCodeRegistryDefinition(
        registry_id="claimpilot:wsib:v1",
        name="ClaimPilot WSIB Reason Codes v1",
        description="Reason codes for WSIB benefit decisions",
        policy_type="wsib",
        jurisdiction="CA-ON",
        version="1.0",
        codes=codes,
    )


def create_cgl_registry_v1() -> ReasonCodeRegistryDefinition:
    """
    Create the CGL (Commercial General Liability) v1 reason code registry.

    This registry contains reason codes for CGL insurance
    exclusion decisions.
    """
    codes: dict[str, ReasonCodeDefinition] = {}

    # Expected/Intended Injury
    codes["RC-INTENT"] = ReasonCodeDefinition(
        code="RC-INTENT",
        name="Expected/Intended Injury Exclusion",
        description="Bodily injury or property damage expected or intended by insured.",
        policy_ref="CGL Coverage A Exclusion a.",
        category="exclusion",
        severity="blocking",
    )

    # Pollution
    codes["RC-POLL"] = ReasonCodeDefinition(
        code="RC-POLL",
        name="Pollution Exclusion",
        description="Loss arising from actual, alleged or threatened discharge of pollutants.",
        policy_ref="CGL Coverage A Exclusion f.",
        category="exclusion",
        severity="blocking",
    )

    # Auto Exclusion
    codes["RC-AUTO"] = ReasonCodeDefinition(
        code="RC-AUTO",
        name="Automobile Exclusion",
        description="Loss arising from ownership, operation or use of an automobile.",
        policy_ref="CGL Coverage A Exclusion g.",
        category="exclusion",
        severity="blocking",
    )

    # Professional Services
    codes["RC-PROF"] = ReasonCodeDefinition(
        code="RC-PROF",
        name="Professional Services Exclusion",
        description="Loss arising from rendering or failure to render professional services.",
        policy_ref="CGL Coverage A Exclusion",
        category="exclusion",
        severity="blocking",
    )

    # Contractual Liability
    codes["RC-CONTRACT"] = ReasonCodeDefinition(
        code="RC-CONTRACT",
        name="Contractual Liability Exclusion",
        description="Loss for which insured assumed liability under contract.",
        policy_ref="CGL Coverage A Exclusion b.",
        category="exclusion",
        severity="blocking",
    )

    # Coverage codes
    codes["RC-COV-CONFIRMED"] = ReasonCodeDefinition(
        code="RC-COV-CONFIRMED",
        name="Coverage Confirmed",
        description="All coverage requirements are met and no exclusions apply.",
        policy_ref="CGL Policy",
        category="coverage",
        severity="informational",
    )

    return ReasonCodeRegistryDefinition(
        registry_id="claimpilot:cgl:v1",
        name="ClaimPilot CGL Reason Codes v1",
        description="Reason codes for commercial general liability decisions",
        policy_type="cgl",
        jurisdiction="CA-ON",
        version="1.0",
        codes=codes,
    )


def create_eo_registry_v1() -> ReasonCodeRegistryDefinition:
    """
    Create the E&O (Errors & Omissions) v1 reason code registry.

    This registry contains reason codes for E&O insurance
    exclusion decisions.
    """
    codes: dict[str, ReasonCodeDefinition] = {}

    # Prior Acts
    codes["RC-PRIOR"] = ReasonCodeDefinition(
        code="RC-PRIOR",
        name="Prior Acts Exclusion",
        description="Wrongful act occurred before retroactive date.",
        policy_ref="E&O Policy - Prior Acts",
        category="exclusion",
        severity="blocking",
    )

    # Known Circumstances
    codes["RC-KNOWN"] = ReasonCodeDefinition(
        code="RC-KNOWN",
        name="Known Circumstances Exclusion",
        description="Insured knew of circumstances likely to give rise to claim before policy inception.",
        policy_ref="E&O Policy - Known Circumstances",
        category="exclusion",
        severity="blocking",
    )

    # Fraud/Dishonesty
    codes["RC-FRAUD"] = ReasonCodeDefinition(
        code="RC-FRAUD",
        name="Fraud/Dishonesty Exclusion",
        description="Claim arising from fraudulent, dishonest or criminal acts.",
        policy_ref="E&O Policy - Dishonesty Exclusion",
        category="exclusion",
        severity="blocking",
    )

    # Bodily Injury
    codes["RC-BI"] = ReasonCodeDefinition(
        code="RC-BI",
        name="Bodily Injury Exclusion",
        description="Claim for bodily injury, which is excluded from E&O coverage.",
        policy_ref="E&O Policy - BI Exclusion",
        category="exclusion",
        severity="blocking",
    )

    # Intentional Acts
    codes["RC-INTENT"] = ReasonCodeDefinition(
        code="RC-INTENT",
        name="Intentional Acts Exclusion",
        description="Loss arising from intentional or willful violation of law.",
        policy_ref="E&O Policy - Intentional Acts",
        category="exclusion",
        severity="blocking",
    )

    # Coverage codes
    codes["RC-COV-CONFIRMED"] = ReasonCodeDefinition(
        code="RC-COV-CONFIRMED",
        name="Coverage Confirmed",
        description="All coverage requirements are met and no exclusions apply.",
        policy_ref="E&O Policy",
        category="coverage",
        severity="informational",
    )

    return ReasonCodeRegistryDefinition(
        registry_id="claimpilot:eo:v1",
        name="ClaimPilot E&O Reason Codes v1",
        description="Reason codes for errors & omissions insurance decisions",
        policy_type="eo",
        jurisdiction="CA-ON",
        version="1.0",
        codes=codes,
    )


def create_travel_registry_v1() -> ReasonCodeRegistryDefinition:
    """
    Create the Travel v1 reason code registry.

    This registry contains reason codes for travel insurance
    exclusion decisions.
    """
    codes: dict[str, ReasonCodeDefinition] = {}

    # Pre-existing Condition
    codes["RC-PRE"] = ReasonCodeDefinition(
        code="RC-PRE",
        name="Pre-existing Condition Exclusion",
        description="Claim relates to condition that was not stable for required period.",
        policy_ref="Travel Policy - Pre-existing Conditions",
        category="exclusion",
        severity="blocking",
    )

    # High-Risk Activity
    codes["RC-RISK"] = ReasonCodeDefinition(
        code="RC-RISK",
        name="High-Risk Activity Exclusion",
        description="Loss occurred during excluded high-risk activity.",
        policy_ref="Travel Policy - Activity Exclusions",
        category="exclusion",
        severity="blocking",
    )

    # Travel Advisory
    codes["RC-ADVISORY"] = ReasonCodeDefinition(
        code="RC-ADVISORY",
        name="Travel Advisory Exclusion",
        description="Travel was to destination under government advisory against travel.",
        policy_ref="Travel Policy - Advisory Exclusions",
        category="exclusion",
        severity="blocking",
    )

    # Elective Treatment
    codes["RC-ELECT"] = ReasonCodeDefinition(
        code="RC-ELECT",
        name="Elective Treatment Exclusion",
        description="Treatment was elective or could have waited until return home.",
        policy_ref="Travel Policy - Elective Procedures",
        category="exclusion",
        severity="blocking",
    )

    # Non-Emergency
    codes["RC-EMERG"] = ReasonCodeDefinition(
        code="RC-EMERG",
        name="Non-Emergency Exclusion",
        description="Treatment was not emergency medical care.",
        policy_ref="Travel Policy - Emergency Definition",
        category="exclusion",
        severity="blocking",
    )

    # Coverage codes
    codes["RC-COV-CONFIRMED"] = ReasonCodeDefinition(
        code="RC-COV-CONFIRMED",
        name="Coverage Confirmed",
        description="All coverage requirements are met and no exclusions apply.",
        policy_ref="Travel Policy",
        category="coverage",
        severity="informational",
    )

    return ReasonCodeRegistryDefinition(
        registry_id="claimpilot:travel:v1",
        name="ClaimPilot Travel Reason Codes v1",
        description="Reason codes for travel insurance decisions",
        policy_type="travel",
        jurisdiction="CA-ON",
        version="1.0",
        codes=codes,
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Exceptions
    "ReasonCodeError",
    "ReasonCodeNotFoundError",
    "RegistryNotFoundError",
    "InvalidReasonCodeError",

    # Data classes
    "ReasonCodeDefinition",
    "ReasonCodeRegistryDefinition",

    # Registry
    "ReasonCodeRegistry",

    # Built-in registries
    "create_ontario_auto_registry_v1",
    "create_property_registry_v1",
    "create_marine_registry_v1",
    "create_health_registry_v1",
    "create_wsib_registry_v1",
    "create_cgl_registry_v1",
    "create_eo_registry_v1",
    "create_travel_registry_v1",
]
