"""
ClaimPilot Precedent System: Seed Generator Module

This module implements the generator for creating seed precedents from
configuration. Seed precedents provide initial training data for the
precedent system with realistic distributions of outcomes, appeals, and
decision levels.

Key components:
- SeedConfig: Configuration for generating seeds for one exclusion type
- SeedGenerator: Generates realistic seed precedents from configuration

Design Principles:
- Deterministic: Same salt + config = reproducible seeds
- Realistic: Distributions match actual claims patterns
- Transparent: source_type="seeded" for all generated precedents

Example:
    >>> generator = SeedGenerator(schema_registry, reason_registry, salt)
    >>> configs = [SeedConfig(...), ...]
    >>> precedents = generator.generate_precedents("auto", "CA-ON", configs)
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

# DecisionGraph imports are optional - the module may not be installed
try:
    from kernel.foundation.judgment import AnchorFact, JudgmentPayload, compute_case_id_hash
    DECISIONGRAPH_AVAILABLE = True
except ImportError:
    # Create stub types for when decisiongraph is not available
    AnchorFact = Any  # type: ignore
    JudgmentPayload = Any  # type: ignore
    def compute_case_id_hash(*args, **kwargs) -> str:  # type: ignore
        return hashlib.sha256(str(args).encode()).hexdigest()[:16]
    DECISIONGRAPH_AVAILABLE = False

from .fingerprint_schema import FingerprintSchemaRegistry
from .reason_code_registry import ReasonCodeRegistry


# =============================================================================
# Constants
# =============================================================================

# Decision level weights: adjuster 70%, senior 12%, manager 10%, tribunal 6%, court 2%
DECISION_LEVEL_WEIGHTS = {
    "adjuster": 0.70,
    "manager": 0.22,  # senior + manager combined since model only has 4 levels
    "tribunal": 0.06,
    "court": 0.02,
}

# Certainty weights: high 55%, medium 35%, low 10%
CERTAINTY_WEIGHTS = {
    "high": 0.55,
    "medium": 0.35,
    "low": 0.10,
}


# =============================================================================
# Exceptions
# =============================================================================

class SeedGeneratorError(Exception):
    """Base exception for seed generator errors."""
    pass


class SeedConfigError(SeedGeneratorError):
    """Raised when seed configuration is invalid."""
    pass


# =============================================================================
# Seed Configuration
# =============================================================================

@dataclass
class SeedConfig:
    """
    Configuration for generating seeds for one exclusion type.

    Attributes:
        exclusion_code: The exclusion code (e.g., "4.2.1", "RC-FLOOD")
        count: Number of precedents to generate
        deny_rate: Proportion that should be denials (0.0-1.0)
        appeal_rate: Proportion of denials that are appealed (0.0-1.0)
        upheld_rate: Proportion of appeals that are upheld (0.0-1.0)
        base_facts: Facts that are constant for all precedents
        variable_facts: Facts that vary, with possible values to choose from
        reason_codes: Optional list of reason codes (auto-generated if not provided)
        name: Human-readable name for this exclusion type
    """
    exclusion_code: str
    count: int
    deny_rate: float
    appeal_rate: float
    upheld_rate: float
    base_facts: dict[str, Any] = field(default_factory=dict)
    variable_facts: dict[str, list[Any]] = field(default_factory=dict)
    reason_codes: Optional[list[str]] = None
    name: str = ""

    def __post_init__(self) -> None:
        """Validate configuration on construction."""
        if not self.exclusion_code:
            raise SeedConfigError("exclusion_code cannot be empty")
        if self.count < 0:
            raise SeedConfigError("count must be non-negative")
        if not 0.0 <= self.deny_rate <= 1.0:
            raise SeedConfigError("deny_rate must be between 0.0 and 1.0")
        if not 0.0 <= self.appeal_rate <= 1.0:
            raise SeedConfigError("appeal_rate must be between 0.0 and 1.0")
        if not 0.0 <= self.upheld_rate <= 1.0:
            raise SeedConfigError("upheld_rate must be between 0.0 and 1.0")


@dataclass
class CleanApprovalConfig:
    """
    Configuration for generating clean approval seeds (no exclusions triggered).

    Attributes:
        count: Number of clean approvals to generate
        appeal_rate: Proportion that are appealed (typically very low)
        base_facts: Facts that are constant for all approvals
        variable_facts: Facts that vary, with possible values
    """
    count: int
    appeal_rate: float = 0.03
    base_facts: dict[str, Any] = field(default_factory=dict)
    variable_facts: dict[str, list[Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.count < 0:
            raise SeedConfigError("count must be non-negative")
        if not 0.0 <= self.appeal_rate <= 1.0:
            raise SeedConfigError("appeal_rate must be between 0.0 and 1.0")


# =============================================================================
# Seed Generator
# =============================================================================

class SeedGenerator:
    """
    Generates realistic seed precedents from configuration.

    The generator creates JudgmentPayload objects that can be loaded
    into a DecisionGraph chain as seed precedents.

    Usage:
        >>> generator = SeedGenerator(schema_registry, reason_registry, salt)
        >>> configs = [SeedConfig(exclusion_code="4.2.1", count=70, ...)]
        >>> precedents = generator.generate_precedents("auto", "CA-ON", configs)
        >>> for payload in precedents:
        ...     cell = create_judgment_cell(payload, namespace, graph_id, prev_hash)
        ...     chain.append(cell)
    """

    def __init__(
        self,
        schema_registry: Optional[FingerprintSchemaRegistry] = None,
        reason_registry: Optional[ReasonCodeRegistry] = None,
        salt: str = "",
    ) -> None:
        """
        Initialize the seed generator.

        Args:
            schema_registry: Registry for fingerprint schemas
            reason_registry: Registry for reason codes
            salt: Salt for privacy-preserving hashing
        """
        self.schema_registry = schema_registry or FingerprintSchemaRegistry()
        self.reason_registry = reason_registry or ReasonCodeRegistry()
        self.salt = salt
        self._rng: Optional[random.Random] = None

    def _init_rng(self, policy_type: str, jurisdiction: str) -> None:
        """Initialize deterministic RNG from salt and policy info."""
        seed_string = f"{self.salt}:{policy_type}:{jurisdiction}"
        seed_hash = hashlib.sha256(seed_string.encode()).digest()
        self._rng = random.Random(int.from_bytes(seed_hash[:8], "big"))

    def generate_precedents(
        self,
        policy_type: str,
        jurisdiction: str,
        configs: list[SeedConfig],
        policy_pack_id: str = "",
        policy_pack_hash: str = "",
        policy_version: str = "1.0",
        clean_approvals: Optional[CleanApprovalConfig] = None,
    ) -> list[JudgmentPayload]:
        """
        Generate precedents from configurations.

        Args:
            policy_type: Policy type (e.g., "auto", "property")
            jurisdiction: Jurisdiction code (e.g., "CA-ON")
            configs: List of SeedConfig for each exclusion type
            policy_pack_id: Policy pack identifier
            policy_pack_hash: Hash of the policy pack (auto-generated if empty)
            policy_version: Policy version string
            clean_approvals: Optional config for clean approval precedents

        Returns:
            List of JudgmentPayload objects ready for chain insertion
        """
        # Initialize deterministic RNG
        self._init_rng(policy_type, jurisdiction)

        # Auto-generate policy pack hash if not provided
        if not policy_pack_hash:
            policy_pack_hash = hashlib.sha256(
                f"{policy_pack_id}:{policy_version}".encode()
            ).hexdigest()

        # Get schema for this policy type
        schema = self.schema_registry.get_schema(policy_type, jurisdiction)

        # Get registry ID
        registry_id = f"claimpilot:{policy_type}:v1"

        precedents: list[JudgmentPayload] = []

        # Generate precedents for each exclusion config
        for config in configs:
            for i in range(config.count):
                payload = self._generate_single_precedent(
                    config=config,
                    index=i,
                    policy_type=policy_type,
                    jurisdiction=jurisdiction,
                    schema_id=schema.schema_id,
                    registry_id=registry_id,
                    policy_pack_id=policy_pack_id,
                    policy_pack_hash=policy_pack_hash,
                    policy_version=policy_version,
                    schema=schema,
                )
                precedents.append(payload)

        # Generate clean approvals if configured
        if clean_approvals:
            for i in range(clean_approvals.count):
                payload = self._generate_clean_approval(
                    config=clean_approvals,
                    index=i,
                    policy_type=policy_type,
                    jurisdiction=jurisdiction,
                    schema_id=schema.schema_id,
                    registry_id=registry_id,
                    policy_pack_id=policy_pack_id,
                    policy_pack_hash=policy_pack_hash,
                    policy_version=policy_version,
                    schema=schema,
                )
                precedents.append(payload)

        return precedents

    def _generate_single_precedent(
        self,
        config: SeedConfig,
        index: int,
        policy_type: str,
        jurisdiction: str,
        schema_id: str,
        registry_id: str,
        policy_pack_id: str,
        policy_pack_hash: str,
        policy_version: str,
        schema: Any,
    ) -> JudgmentPayload:
        """Generate a single precedent from configuration."""
        assert self._rng is not None

        # Combine base facts with selected variable facts
        facts = dict(config.base_facts)
        facts.update(self._select_variable_facts(config.variable_facts))

        # Determine outcome based on deny_rate
        is_deny = self._rng.random() < config.deny_rate
        outcome_code = "deny" if is_deny else "pay"

        # Determine appeal status
        appealed, appeal_outcome, appeal_decided_at, appeal_level = self._determine_appeal(
            config, is_deny
        )

        # Determine decision level
        decision_level = self._select_decision_level()

        # Determine certainty
        certainty = self._select_certainty()

        # Generate timestamps
        decided_at = self._generate_decided_at()

        # Generate case ID hash
        case_id = f"seed:{policy_type}:{config.exclusion_code}:{index}"
        case_id_hash = compute_case_id_hash(case_id, self.salt)

        # Compute fingerprint
        fingerprint_hash = self.schema_registry.compute_fingerprint(
            schema, facts, self.salt
        )

        # Create anchor facts
        anchor_facts = self._create_anchor_facts(facts, schema)

        # Get reason codes
        if config.reason_codes:
            reason_codes = config.reason_codes
        else:
            reason_codes = [f"RC-{config.exclusion_code}"]

        # Determine if this is a notable outcome
        outcome_notable = self._determine_notable(appealed, appeal_outcome)

        return JudgmentPayload.create(
            case_id_hash=case_id_hash,
            jurisdiction_code=jurisdiction,
            fingerprint_hash=fingerprint_hash,
            fingerprint_schema_id=schema_id,
            exclusion_codes=[config.exclusion_code] if is_deny else [],
            reason_codes=reason_codes if is_deny else ["RC-COV-CONFIRMED"],
            reason_code_registry_id=registry_id,
            outcome_code=outcome_code,
            certainty=certainty,
            anchor_facts=anchor_facts,
            policy_pack_hash=policy_pack_hash,
            policy_pack_id=policy_pack_id,
            policy_version=policy_version,
            decision_level=decision_level,
            decided_at=decided_at,
            decided_by_role=decision_level,
            appealed=appealed,
            appeal_outcome=appeal_outcome,
            appeal_decided_at=appeal_decided_at,
            appeal_level=appeal_level,
            source_type="seeded",
            outcome_notable=outcome_notable,
        )

    def _generate_clean_approval(
        self,
        config: CleanApprovalConfig,
        index: int,
        policy_type: str,
        jurisdiction: str,
        schema_id: str,
        registry_id: str,
        policy_pack_id: str,
        policy_pack_hash: str,
        policy_version: str,
        schema: Any,
    ) -> JudgmentPayload:
        """Generate a clean approval precedent (no exclusions triggered)."""
        assert self._rng is not None

        # Combine base facts with selected variable facts
        facts = dict(config.base_facts)
        facts.update(self._select_variable_facts(config.variable_facts))

        # Clean approvals always pay
        outcome_code = "pay"

        # Determine appeal status (rare for approvals)
        appealed = self._rng.random() < config.appeal_rate
        appeal_outcome = None
        appeal_decided_at = None
        appeal_level = None
        if appealed:
            appeal_outcome = "upheld"  # Approvals are typically upheld
            appeal_level = "manager"
            appeal_decided_at = self._generate_decided_at()

        # Determine decision level
        decision_level = self._select_decision_level()

        # Determine certainty (clean approvals tend to be high certainty)
        certainty = self._select_certainty()
        if self._rng.random() < 0.3:  # Boost high certainty for clean approvals
            certainty = "high"

        # Generate timestamps
        decided_at = self._generate_decided_at()

        # Generate case ID hash
        case_id = f"seed:{policy_type}:clean:{index}"
        case_id_hash = compute_case_id_hash(case_id, self.salt)

        # Compute fingerprint
        fingerprint_hash = self.schema_registry.compute_fingerprint(
            schema, facts, self.salt
        )

        # Create anchor facts
        anchor_facts = self._create_anchor_facts(facts, schema)

        return JudgmentPayload.create(
            case_id_hash=case_id_hash,
            jurisdiction_code=jurisdiction,
            fingerprint_hash=fingerprint_hash,
            fingerprint_schema_id=schema_id,
            exclusion_codes=[],
            reason_codes=["RC-COV-CONFIRMED"],
            reason_code_registry_id=registry_id,
            outcome_code=outcome_code,
            certainty=certainty,
            anchor_facts=anchor_facts,
            policy_pack_hash=policy_pack_hash,
            policy_pack_id=policy_pack_id,
            policy_version=policy_version,
            decision_level=decision_level,
            decided_at=decided_at,
            decided_by_role=decision_level,
            appealed=appealed,
            appeal_outcome=appeal_outcome,
            appeal_decided_at=appeal_decided_at,
            appeal_level=appeal_level,
            source_type="seeded",
            outcome_notable=None,
        )

    def _select_variable_facts(
        self,
        variable_facts: dict[str, list[Any]],
    ) -> dict[str, Any]:
        """Select one value for each variable fact."""
        assert self._rng is not None
        result: dict[str, Any] = {}
        for field_id, values in variable_facts.items():
            if values:
                result[field_id] = self._rng.choice(values)
        return result

    def _determine_appeal(
        self,
        config: SeedConfig,
        is_deny: bool,
    ) -> tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Determine appeal status based on configuration.

        Returns:
            Tuple of (appealed, appeal_outcome, appeal_decided_at, appeal_level)
        """
        assert self._rng is not None

        # Only denials get appealed
        if not is_deny:
            return False, None, None, None

        # Check if this denial was appealed
        if self._rng.random() >= config.appeal_rate:
            return False, None, None, None

        # This was appealed - determine outcome
        is_upheld = self._rng.random() < config.upheld_rate
        appeal_outcome = "upheld" if is_upheld else "overturned"

        # Generate appeal decision date (1-6 months after original decision)
        appeal_decided_at = self._generate_decided_at()

        # Appeal level is higher than original
        appeal_level = self._rng.choice(["manager", "tribunal"])

        return True, appeal_outcome, appeal_decided_at, appeal_level

    def _generate_decided_at(self) -> str:
        """Generate a random decision date in the past 2 years."""
        assert self._rng is not None

        # Random days in past 2 years (730 days)
        days_ago = self._rng.randint(1, 730)
        decision_date = datetime.now(timezone.utc) - timedelta(days=days_ago)

        # Add random hours/minutes for realism
        decision_date = decision_date.replace(
            hour=self._rng.randint(8, 18),
            minute=self._rng.randint(0, 59),
            second=0,
            microsecond=0,
        )

        return decision_date.isoformat()

    def _select_decision_level(self) -> str:
        """Select decision level based on weighted distribution."""
        assert self._rng is not None

        roll = self._rng.random()
        cumulative = 0.0
        for level, weight in DECISION_LEVEL_WEIGHTS.items():
            cumulative += weight
            if roll < cumulative:
                return level
        return "adjuster"  # Fallback

    def _select_certainty(self) -> str:
        """Select certainty based on weighted distribution."""
        assert self._rng is not None

        roll = self._rng.random()
        cumulative = 0.0
        for certainty, weight in CERTAINTY_WEIGHTS.items():
            cumulative += weight
            if roll < cumulative:
                return certainty
        return "medium"  # Fallback

    def _create_anchor_facts(
        self,
        facts: dict[str, Any],
        schema: Any,
    ) -> list[AnchorFact]:
        """Create AnchorFact list from facts."""
        anchor_facts: list[AnchorFact] = []

        for field_id in schema.exclusion_relevant_facts:
            if field_id in facts:
                value = facts[field_id]

                # Convert floats to strings (DecisionGraph doesn't allow floats)
                if isinstance(value, float):
                    value = str(value)

                label = field_id.replace(".", " ").replace("_", " ").title()
                anchor_facts.append(AnchorFact(
                    field_id=field_id,
                    value=value,
                    label=label,
                ))

        return anchor_facts

    def _determine_notable(
        self,
        appealed: bool,
        appeal_outcome: Optional[str],
    ) -> Optional[str]:
        """Determine if this is a notable outcome."""
        if appealed and appeal_outcome == "overturned":
            return "overturned"

        # Small chance of being a boundary case
        assert self._rng is not None
        if self._rng.random() < 0.02:  # 2% chance
            return "boundary_case"

        return None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Exceptions
    "SeedGeneratorError",
    "SeedConfigError",

    # Configuration
    "SeedConfig",
    "CleanApprovalConfig",

    # Generator
    "SeedGenerator",

    # Constants
    "DECISION_LEVEL_WEIGHTS",
    "CERTAINTY_WEIGHTS",
]
