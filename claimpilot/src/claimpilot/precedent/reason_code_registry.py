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
]
