"""
ClaimPilot Precedent System: Seed Loader Module

This module implements the loader for seed precedents, enabling loading
from YAML configurations into a DecisionGraph chain.

Key components:
- SeedLoader: Loads seed precedents into a DecisionGraph chain
- SeedVerificationResult: Result of seed verification

Design Principles:
- Idempotent: Safe to run multiple times (uses precedent_id for deduplication)
- Verifiable: Can verify seeds loaded correctly
- Transparent: All seeds marked with source_type="seeded"

Example:
    >>> loader = SeedLoader(chain, salt="secret")
    >>> counts = loader.load_all()
    >>> print(f"Loaded {sum(counts.values())} precedents")
    >>> result = loader.verify()
    >>> assert result.success
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from decisiongraph.judgment import (
    JudgmentPayload,
    create_judgment_cell,
    parse_judgment_payload,
    is_judgment_cell,
)

from .fingerprint_schema import FingerprintSchemaRegistry
from .reason_code_registry import ReasonCodeRegistry
from .seed_generator import SeedGenerator, SeedConfig, CleanApprovalConfig
from .seeds import load_seed_config, load_all_seed_configs, SEEDS_DIR

if TYPE_CHECKING:
    from decisiongraph.chain import Chain


# =============================================================================
# Exceptions
# =============================================================================

class SeedLoaderError(Exception):
    """Base exception for seed loader errors."""
    pass


class SeedLoadError(SeedLoaderError):
    """Raised when seed loading fails."""
    pass


class SeedVerificationError(SeedLoaderError):
    """Raised when seed verification fails."""
    pass


# =============================================================================
# Verification Result
# =============================================================================

@dataclass
class SeedVerificationResult:
    """
    Result of seed verification.

    Attributes:
        success: Whether verification passed
        total_seeds: Total number of seeds expected
        seeds_found: Number of seeds found in chain
        seeds_by_policy: Count of seeds by policy type
        errors: List of error messages
        warnings: List of warning messages
    """
    success: bool
    total_seeds: int = 0
    seeds_found: int = 0
    seeds_by_policy: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        """Human-readable summary."""
        status = "PASSED" if self.success else "FAILED"
        lines = [
            f"Seed Verification: {status}",
            f"  Total expected: {self.total_seeds}",
            f"  Found: {self.seeds_found}",
        ]
        if self.seeds_by_policy:
            lines.append("  By policy type:")
            for policy, count in sorted(self.seeds_by_policy.items()):
                lines.append(f"    {policy}: {count}")
        if self.errors:
            lines.append("  Errors:")
            for error in self.errors:
                lines.append(f"    - {error}")
        if self.warnings:
            lines.append("  Warnings:")
            for warning in self.warnings:
                lines.append(f"    - {warning}")
        return "\n".join(lines)


# =============================================================================
# Load Statistics
# =============================================================================

@dataclass
class SeedLoadStats:
    """
    Statistics from a seed loading operation.

    Attributes:
        policy_type: Policy type loaded
        total_generated: Number of precedents generated
        total_loaded: Number actually loaded to chain
        skipped_duplicate: Number skipped as duplicates
        exclusion_counts: Count by exclusion code
        clean_approvals: Number of clean approvals
    """
    policy_type: str
    total_generated: int = 0
    total_loaded: int = 0
    skipped_duplicate: int = 0
    exclusion_counts: dict[str, int] = field(default_factory=dict)
    clean_approvals: int = 0


# =============================================================================
# Seed Loader
# =============================================================================

class SeedLoader:
    """
    Loads seed precedents into a DecisionGraph chain.

    The loader reads YAML configurations, generates precedents using
    SeedGenerator, and appends them to the chain as JUDGMENT cells.

    Usage:
        >>> loader = SeedLoader(chain, salt="secret")
        >>> loader.load_from_yaml("auto_oap1")
        >>> counts = loader.load_all()
        >>> result = loader.verify()
    """

    def __init__(
        self,
        chain: Chain,
        salt: str,
        schema_registry: Optional[FingerprintSchemaRegistry] = None,
        reason_registry: Optional[ReasonCodeRegistry] = None,
        namespace: str = "claims.precedents",
    ) -> None:
        """
        Initialize the seed loader.

        Args:
            chain: The DecisionGraph chain to load seeds into
            salt: Salt for privacy-preserving hashing
            schema_registry: Optional registry for fingerprint schemas
            reason_registry: Optional registry for reason codes
            namespace: Namespace for JUDGMENT cells
        """
        self.chain = chain
        self.salt = salt
        self.namespace = namespace
        self.schema_registry = schema_registry or FingerprintSchemaRegistry()
        self.reason_registry = reason_registry or ReasonCodeRegistry()
        self.generator = SeedGenerator(
            schema_registry=self.schema_registry,
            reason_registry=self.reason_registry,
            salt=salt,
        )

    def load_from_yaml(self, config_name: str) -> SeedLoadStats:
        """
        Load seeds from a YAML configuration file.

        Args:
            config_name: Name of the config (e.g., "auto_oap1") without .yaml

        Returns:
            SeedLoadStats with loading statistics

        Raises:
            SeedLoadError: If loading fails
        """
        try:
            config = load_seed_config(config_name)
            return self._load_from_config(config, config_name)
        except Exception as e:
            raise SeedLoadError(f"Failed to load seeds from {config_name}: {e}")

    def load_all(self, seeds_dir: Optional[str] = None) -> dict[str, SeedLoadStats]:
        """
        Load all seed configurations.

        Args:
            seeds_dir: Optional directory path (uses default if not specified)

        Returns:
            Dict mapping config name to SeedLoadStats
        """
        all_configs = load_all_seed_configs()
        results: dict[str, SeedLoadStats] = {}

        for name, config in all_configs.items():
            try:
                stats = self._load_from_config(config, name)
                results[name] = stats
            except Exception as e:
                # Log error but continue with other configs
                results[name] = SeedLoadStats(
                    policy_type=name,
                    total_generated=0,
                    total_loaded=0,
                )

        return results

    def _load_from_config(
        self,
        config: dict[str, Any],
        config_name: str,
    ) -> SeedLoadStats:
        """Load seeds from a parsed configuration dictionary."""
        # Extract config values
        schema_id = config.get("schema_id", "")
        registry_id = config.get("registry_id", "")
        jurisdiction = config.get("jurisdiction", "CA-ON")
        policy_pack_id = config.get("policy_pack_id", "")
        policy_version = config.get("policy_version", "1.0")

        # Infer policy type from schema_id
        # e.g., "claimpilot:oap1:auto:v1" -> "auto"
        policy_type = self._extract_policy_type(schema_id)

        # Build SeedConfig list from exclusions
        seed_configs: list[SeedConfig] = []
        exclusion_counts: dict[str, int] = {}

        for exclusion in config.get("exclusions", []):
            seed_config = SeedConfig(
                exclusion_code=exclusion["code"],
                count=exclusion.get("count", 10),
                deny_rate=exclusion.get("deny_rate", 0.9),
                appeal_rate=exclusion.get("appeal_rate", 0.15),
                upheld_rate=exclusion.get("upheld_rate", 0.8),
                base_facts=exclusion.get("base_facts", {}),
                variable_facts=exclusion.get("variable_facts", {}),
                name=exclusion.get("name", ""),
            )
            seed_configs.append(seed_config)
            exclusion_counts[exclusion["code"]] = exclusion.get("count", 10)

        # Build clean approvals config if present
        clean_approvals: Optional[CleanApprovalConfig] = None
        clean_approval_count = 0
        if "clean_approvals" in config:
            ca_config = config["clean_approvals"]
            clean_approvals = CleanApprovalConfig(
                count=ca_config.get("count", 0),
                appeal_rate=ca_config.get("appeal_rate", 0.03),
                base_facts=ca_config.get("base_facts", {}),
                variable_facts=ca_config.get("variable_facts", {}),
            )
            clean_approval_count = clean_approvals.count

        # Generate precedents
        precedents = self.generator.generate_precedents(
            policy_type=policy_type,
            jurisdiction=jurisdiction,
            configs=seed_configs,
            policy_pack_id=policy_pack_id,
            policy_version=policy_version,
            clean_approvals=clean_approvals,
        )

        # Load precedents into chain
        loaded_count = 0
        skipped_count = 0
        existing_ids = self._get_existing_precedent_ids()

        for payload in precedents:
            if payload.precedent_id in existing_ids:
                skipped_count += 1
                continue

            try:
                cell = create_judgment_cell(
                    payload=payload,
                    namespace=self.namespace,
                    graph_id=self.chain.graph_id,
                    prev_cell_hash=self.chain.head.cell_id,
                )
                self.chain.append(cell)
                loaded_count += 1
            except Exception:
                # Skip failed cells
                skipped_count += 1

        return SeedLoadStats(
            policy_type=policy_type,
            total_generated=len(precedents),
            total_loaded=loaded_count,
            skipped_duplicate=skipped_count,
            exclusion_counts=exclusion_counts,
            clean_approvals=clean_approval_count,
        )

    def _extract_policy_type(self, schema_id: str) -> str:
        """Extract policy type from schema ID."""
        # schema_id format: "claimpilot:<product>:<type>:v<n>"
        # e.g., "claimpilot:oap1:auto:v1" -> "auto"
        # e.g., "claimpilot:ho3:property:v1" -> "property"
        parts = schema_id.split(":")
        if len(parts) >= 3:
            return parts[2]
        return "unknown"

    def _get_existing_precedent_ids(self) -> set[str]:
        """Get set of precedent IDs already in the chain."""
        existing: set[str] = set()
        for cell in self.chain.iter_cells():
            if is_judgment_cell(cell):
                try:
                    payload = parse_judgment_payload(cell)
                    existing.add(payload.precedent_id)
                except Exception:
                    pass
        return existing

    def verify(self) -> SeedVerificationResult:
        """
        Verify seeds loaded correctly.

        Checks that the expected number of seeded precedents exist
        in the chain and have correct distributions.

        Returns:
            SeedVerificationResult with verification details
        """
        # Count expected seeds from all configs
        all_configs = load_all_seed_configs()
        expected_total = 0
        expected_by_policy: dict[str, int] = {}

        for name, config in all_configs.items():
            policy_type = self._extract_policy_type(config.get("schema_id", ""))
            count = sum(e.get("count", 0) for e in config.get("exclusions", []))
            count += config.get("clean_approvals", {}).get("count", 0)
            expected_total += count
            expected_by_policy[policy_type] = (
                expected_by_policy.get(policy_type, 0) + count
            )

        # Count actual seeded precedents in chain
        found_total = 0
        found_by_policy: dict[str, int] = {}
        errors: list[str] = []
        warnings: list[str] = []

        for cell in self.chain.iter_cells():
            if not is_judgment_cell(cell):
                continue
            try:
                payload = parse_judgment_payload(cell)
                if payload.source_type == "seeded":
                    found_total += 1
                    # Extract policy from schema ID
                    policy_type = self._extract_policy_type(
                        payload.fingerprint_schema_id
                    )
                    found_by_policy[policy_type] = (
                        found_by_policy.get(policy_type, 0) + 1
                    )
            except Exception as e:
                errors.append(f"Failed to parse JUDGMENT cell: {e}")

        # Check counts match
        success = True
        if found_total < expected_total * 0.95:  # Allow 5% margin
            success = False
            errors.append(
                f"Expected at least {int(expected_total * 0.95)} seeds, "
                f"found {found_total}"
            )

        # Check per-policy counts
        for policy_type, expected in expected_by_policy.items():
            found = found_by_policy.get(policy_type, 0)
            if found < expected * 0.9:  # Allow 10% margin per policy
                warnings.append(
                    f"Policy '{policy_type}': expected ~{expected}, found {found}"
                )

        return SeedVerificationResult(
            success=success,
            total_seeds=expected_total,
            seeds_found=found_total,
            seeds_by_policy=found_by_policy,
            errors=errors,
            warnings=warnings,
        )

    def get_statistics(self) -> dict[str, Any]:
        """
        Get statistics about seeded precedents in the chain.

        Returns:
            Dict with seed statistics
        """
        stats: dict[str, Any] = {
            "total": 0,
            "by_policy_type": {},
            "by_outcome": {"pay": 0, "deny": 0, "partial": 0, "escalate": 0},
            "appealed": 0,
            "overturned": 0,
            "boundary_cases": 0,
        }

        for cell in self.chain.iter_cells():
            if not is_judgment_cell(cell):
                continue
            try:
                payload = parse_judgment_payload(cell)
                if payload.source_type != "seeded":
                    continue

                stats["total"] += 1

                # By policy type
                policy_type = self._extract_policy_type(
                    payload.fingerprint_schema_id
                )
                if policy_type not in stats["by_policy_type"]:
                    stats["by_policy_type"][policy_type] = 0
                stats["by_policy_type"][policy_type] += 1

                # By outcome
                if payload.outcome_code in stats["by_outcome"]:
                    stats["by_outcome"][payload.outcome_code] += 1

                # Appeals
                if payload.appealed:
                    stats["appealed"] += 1
                    if payload.appeal_outcome == "overturned":
                        stats["overturned"] += 1

                # Notable outcomes
                if payload.outcome_notable == "boundary_case":
                    stats["boundary_cases"] += 1

            except Exception:
                pass

        return stats


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Exceptions
    "SeedLoaderError",
    "SeedLoadError",
    "SeedVerificationError",

    # Data classes
    "SeedVerificationResult",
    "SeedLoadStats",

    # Loader
    "SeedLoader",
]
