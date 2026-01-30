"""
ClaimPilot Policy Engine

Loads, manages, and queries policy packs.

Key features:
- Load policy packs from YAML/JSON files
- Cache policies and related rules
- Query policies by jurisdiction, line of business, date
- Version-aware policy selection
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional, Union

from ..exceptions import PolicyLoadError, PolicyNotFoundError
from ..models import (
    AuthorityRef,
    AuthorityRule,
    EvidenceRule,
    LineOfBusiness,
    Policy,
    TimelineRule,
)
from ..packs import PolicyPackLoader


@dataclass
class PolicyEngine:
    """
    Loads and manages policy packs.

    The PolicyEngine is the central point for accessing policy rules.
    It handles loading, caching, and querying policies.

    Usage:
        engine = PolicyEngine()

        # Load policies
        engine.load_policy("packs/ontario_auto.yaml")
        engine.load_policies_from_directory("packs/")

        # Get a specific policy
        policy = engine.get_policy("CA-ON-OAP1-2024")

        # Get policy effective on a date
        policy = engine.get_policy_as_of("CA-ON-OAP1", date(2024, 6, 15))

        # Query policies
        auto_policies = engine.list_policies(
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.AUTO
        )
    """

    # Internal loader
    _loader: PolicyPackLoader = field(default_factory=PolicyPackLoader)

    # Caches
    _policies: dict[str, Policy] = field(default_factory=dict)
    _policies_by_product: dict[str, list[Policy]] = field(default_factory=dict)
    _authorities: dict[str, AuthorityRef] = field(default_factory=dict)
    _timeline_rules: dict[str, TimelineRule] = field(default_factory=dict)
    _evidence_rules: dict[str, EvidenceRule] = field(default_factory=dict)
    _authority_rules: dict[str, AuthorityRule] = field(default_factory=dict)

    def load_policy(self, path: Union[str, Path]) -> Policy:
        """
        Load a policy pack from a file.

        Args:
            path: Path to YAML or JSON file

        Returns:
            Loaded Policy

        Raises:
            PolicyLoadError: If file cannot be loaded
            PolicyValidationError: If validation fails
        """
        policy = self._loader.load(path)

        # Cache the policy
        self._policies[policy.id] = policy

        # Index by product code for version lookups
        product_key = f"{policy.jurisdiction}-{policy.product_code}"
        if product_key not in self._policies_by_product:
            self._policies_by_product[product_key] = []
        self._policies_by_product[product_key].append(policy)

        # Sort by effective date (newest first)
        self._policies_by_product[product_key].sort(
            key=lambda p: p.effective_date,
            reverse=True
        )

        # Copy cached items from loader
        self._authorities.update({
            k: v for k, v in self._loader._authorities.items()
        })
        self._timeline_rules.update({
            k: v for k, v in self._loader._timeline_rules.items()
        })
        self._evidence_rules.update({
            k: v for k, v in self._loader._evidence_rules.items()
        })
        self._authority_rules.update({
            k: v for k, v in self._loader._authority_rules.items()
        })

        return policy

    def load_policies_from_directory(
        self,
        directory: Union[str, Path],
        pattern: str = "*.yaml",
    ) -> list[Policy]:
        """
        Load all policy packs from a directory.

        Args:
            directory: Directory path
            pattern: Glob pattern for files (default: "*.yaml")

        Returns:
            List of loaded policies
        """
        directory = Path(directory)
        if not directory.is_dir():
            raise PolicyLoadError(
                message=f"Directory not found: {directory}",
                details={"path": str(directory)},
            )

        policies = []
        for path in sorted(directory.glob(pattern)):
            if path.is_file():
                try:
                    policy = self.load_policy(path)
                    policies.append(policy)
                except Exception as e:
                    # Log but continue loading other policies
                    if hasattr(self, "_load_errors"):
                        self._load_errors.append((path, e))

        # Also try JSON files
        if pattern == "*.yaml":
            for path in sorted(directory.glob("*.json")):
                if path.is_file():
                    try:
                        policy = self.load_policy(path)
                        policies.append(policy)
                    except Exception:
                        pass

        return policies

    def get_policy(self, policy_id: str) -> Optional[Policy]:
        """
        Get a policy by its exact ID.

        Args:
            policy_id: Policy ID (e.g., "CA-ON-OAP1-2024")

        Returns:
            Policy if found, None otherwise
        """
        return self._policies.get(policy_id)

    def get_policy_or_raise(self, policy_id: str) -> Policy:
        """
        Get a policy by ID, raising if not found.

        Args:
            policy_id: Policy ID

        Returns:
            Policy

        Raises:
            PolicyNotFoundError: If policy not found
        """
        policy = self.get_policy(policy_id)
        if policy is None:
            raise PolicyNotFoundError(
                message=f"Policy not found: {policy_id}",
                details={"policy_id": policy_id, "available": list(self._policies.keys())},
            )
        return policy

    def get_policy_as_of(
        self,
        jurisdiction: str,
        product_code: str,
        as_of: date,
    ) -> Optional[Policy]:
        """
        Get the policy version effective on a specific date.

        Args:
            jurisdiction: Jurisdiction code (e.g., "CA-ON")
            product_code: Product code (e.g., "OAP1")
            as_of: Date to check

        Returns:
            Policy effective on that date, or None if not found
        """
        product_key = f"{jurisdiction.upper()}-{product_code.upper()}"
        policies = self._policies_by_product.get(product_key, [])

        for policy in policies:
            if policy.is_effective_on(as_of):
                return policy

        return None

    def list_policies(
        self,
        jurisdiction: Optional[str] = None,
        line_of_business: Optional[LineOfBusiness] = None,
        effective_on: Optional[date] = None,
    ) -> list[Policy]:
        """
        List policies with optional filters.

        Args:
            jurisdiction: Filter by jurisdiction
            line_of_business: Filter by line of business
            effective_on: Filter by effective date

        Returns:
            List of matching policies
        """
        results = []

        for policy in self._policies.values():
            # Apply filters
            if jurisdiction and policy.jurisdiction.upper() != jurisdiction.upper():
                continue
            if line_of_business and policy.line_of_business != line_of_business:
                continue
            if effective_on and not policy.is_effective_on(effective_on):
                continue

            results.append(policy)

        # Sort by jurisdiction, then product code, then version
        results.sort(key=lambda p: (p.jurisdiction, p.product_code, p.version))

        return results

    def get_authority(self, authority_id: str) -> Optional[AuthorityRef]:
        """Get an authority reference by ID."""
        return self._authorities.get(authority_id)

    def get_timeline_rule(self, rule_id: str) -> Optional[TimelineRule]:
        """Get a timeline rule by ID."""
        return self._timeline_rules.get(rule_id)

    def get_timeline_rules_for_policy(self, policy: Policy) -> list[TimelineRule]:
        """Get all timeline rules for a policy."""
        return [
            self._timeline_rules[rule_id]
            for rule_id in policy.timeline_rule_ids
            if rule_id in self._timeline_rules
        ]

    def get_evidence_rule(self, rule_id: str) -> Optional[EvidenceRule]:
        """Get an evidence rule by ID."""
        return self._evidence_rules.get(rule_id)

    def get_evidence_rules_for_policy(self, policy: Policy) -> list[EvidenceRule]:
        """Get all evidence rules for a policy."""
        return [
            self._evidence_rules[rule_id]
            for rule_id in policy.evidence_rule_ids
            if rule_id in self._evidence_rules
        ]

    def get_authority_rule(self, rule_id: str) -> Optional[AuthorityRule]:
        """Get an authority/escalation rule by ID."""
        return self._authority_rules.get(rule_id)

    def get_authority_rules_for_policy(self, policy: Policy) -> list[AuthorityRule]:
        """Get all authority rules for a policy."""
        return [
            self._authority_rules[rule_id]
            for rule_id in policy.authority_rule_ids
            if rule_id in self._authority_rules
        ]

    @property
    def policy_count(self) -> int:
        """Get the number of loaded policies."""
        return len(self._policies)

    @property
    def policy_ids(self) -> list[str]:
        """Get list of all loaded policy IDs."""
        return list(self._policies.keys())

    def clear(self) -> None:
        """Clear all cached policies and rules."""
        self._policies.clear()
        self._policies_by_product.clear()
        self._authorities.clear()
        self._timeline_rules.clear()
        self._evidence_rules.clear()
        self._authority_rules.clear()
        # Reset loader
        self._loader = PolicyPackLoader()


# =============================================================================
# Module-level Engine Instance
# =============================================================================

_default_engine: Optional[PolicyEngine] = None


def get_default_engine() -> PolicyEngine:
    """Get or create the default policy engine instance."""
    global _default_engine
    if _default_engine is None:
        _default_engine = PolicyEngine()
    return _default_engine


def load_policy(path: Union[str, Path]) -> Policy:
    """
    Load a policy using the default engine.

    Convenience function for simple use cases.
    """
    return get_default_engine().load_policy(path)


def get_policy(policy_id: str) -> Optional[Policy]:
    """
    Get a policy from the default engine.

    Convenience function for simple use cases.
    """
    return get_default_engine().get_policy(policy_id)
