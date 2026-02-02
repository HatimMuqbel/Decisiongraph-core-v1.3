"""
ClaimPilot Precedent System

Precedent-aware decision support for insurance claims processing.

This package provides:
- Privacy-preserving fingerprint computation for case matching
- Reason code registry for standardized decision rationales
- Tiered precedent query engine (Tier 0, 0.5, 1)
- Finalization gate for creating JUDGMENT cells on disposition seal

Key Components:
- FingerprintSchema: Defines which facts matter for matching
- FingerprintSchemaRegistry: Registry of schemas by policy type
- ReasonCodeRegistry: Standardized reason code definitions
- PrecedentQueryEngine: High-level query interface
- FinalizationGate: Creates JUDGMENT cells on seal

Design Principles:
- Deterministic: Precedent retrieval and scoring are auditable
- Privacy-preserving: Case IDs are hashed, never stored raw
- LLMs as rendering layer only: Core logic is deterministic

Example Usage:
    >>> from claimpilot.precedent import (
    ...     FingerprintSchemaRegistry,
    ...     PrecedentQueryEngine,
    ...     FinalizationGate,
    ... )
    >>>
    >>> # Query precedents
    >>> engine = PrecedentQueryEngine(chain, salt="secret")
    >>> result = engine.query(
    ...     facts={"driver.rideshare_app_active": True},
    ...     policy_type="auto",
    ...     jurisdiction="CA-ON",
    ...     exclusion_codes=["4.2.1"],
    ...     proposed_outcome="deny"
    ... )
    >>> print(f"Matched {result.summary.total_matched} precedents")
    >>> print(f"Confidence: {result.summary.precedent_confidence}")
"""

# Fingerprint Schema
from .fingerprint_schema import (
    FingerprintSchemaError,
    SchemaNotFoundError,
    BandingError,
    BandingRule,
    FingerprintSchema,
    FingerprintSchemaRegistry,
    apply_banding,
    create_ontario_auto_schema_v1,
)

# Reason Code Registry
from .reason_code_registry import (
    ReasonCodeError,
    ReasonCodeNotFoundError,
    RegistryNotFoundError,
    InvalidReasonCodeError,
    ReasonCodeDefinition,
    ReasonCodeRegistryDefinition,
    ReasonCodeRegistry,
    create_ontario_auto_registry_v1,
)

# Precedent Query Engine
from .precedent_query import (
    PrecedentQueryTier,
    PrecedentQueryParams,
    PrecedentMatch,
    PrecedentSummary,
    PrecedentQueryResult,
    PrecedentQueryEngine,
)

# Finalization Gate
from .finalization_gate import (
    FinalizationError,
    DispositionNotSealedError,
    FinalizationDataError,
    FinalizationResult,
    FinalizationGate,
)


__all__ = [
    # Fingerprint Schema
    "FingerprintSchemaError",
    "SchemaNotFoundError",
    "BandingError",
    "BandingRule",
    "FingerprintSchema",
    "FingerprintSchemaRegistry",
    "apply_banding",
    "create_ontario_auto_schema_v1",

    # Reason Code Registry
    "ReasonCodeError",
    "ReasonCodeNotFoundError",
    "RegistryNotFoundError",
    "InvalidReasonCodeError",
    "ReasonCodeDefinition",
    "ReasonCodeRegistryDefinition",
    "ReasonCodeRegistry",
    "create_ontario_auto_registry_v1",

    # Precedent Query Engine
    "PrecedentQueryTier",
    "PrecedentQueryParams",
    "PrecedentMatch",
    "PrecedentSummary",
    "PrecedentQueryResult",
    "PrecedentQueryEngine",

    # Finalization Gate
    "FinalizationError",
    "DispositionNotSealedError",
    "FinalizationDataError",
    "FinalizationResult",
    "FinalizationGate",
]
