"""
ClaimPilot Policy Packs

Schema validation and loading for policy packs.

Policy packs are YAML or JSON files that define coverage rules,
exclusions, timeline requirements, and evidence rules for a
specific insurance product in a specific jurisdiction.

Focus: Ontario, Canada (FSRA regulated)

Usage:
    from claimpilot.packs import load_policy_pack, PolicyPackLoader

    # Load a single policy pack
    policy = load_policy_pack("path/to/ontario_auto.yaml")

    # Use a loader for multiple packs (caches authorities, rules)
    loader = PolicyPackLoader()
    policy1 = loader.load("path/to/auto.yaml")
    policy2 = loader.load("path/to/property.yaml")

    # Get cached authorities
    auth = loader.get_authority("fsra-guideline-1")
"""
from __future__ import annotations

from .loader import (
    PolicyPackLoader,
    load_policy_pack,
    load_policy_pack_from_string,
)
from .schema import (
    SCHEMA_VERSION,
    AuthorityRefSchema,
    AuthorityRuleSchema,
    ConditionSchema,
    CoverageLimitsSchema,
    CoverageSectionSchema,
    DeductiblesSchema,
    DocumentRequirementSchema,
    EvidenceRuleSchema,
    ExclusionSchema,
    LossTypeTriggerSchema,
    PolicyPackSchema,
    PredicateSchema,
    TimelineRuleSchema,
    check_schema_version,
    validate_policy_pack,
)

__all__ = [
    # Version
    "SCHEMA_VERSION",
    # Loader
    "PolicyPackLoader",
    "load_policy_pack",
    "load_policy_pack_from_string",
    # Validation
    "validate_policy_pack",
    "check_schema_version",
    # Schemas (for advanced usage)
    "PolicyPackSchema",
    "ConditionSchema",
    "PredicateSchema",
    "AuthorityRefSchema",
    "AuthorityRuleSchema",
    "CoverageSectionSchema",
    "CoverageLimitsSchema",
    "DeductiblesSchema",
    "LossTypeTriggerSchema",
    "ExclusionSchema",
    "TimelineRuleSchema",
    "EvidenceRuleSchema",
    "DocumentRequirementSchema",
]
