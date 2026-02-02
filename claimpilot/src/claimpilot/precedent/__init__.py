"""
ClaimPilot Precedent System

Precedent-aware decision support for insurance claims processing.

This package provides:
- Privacy-preserving fingerprint computation for case matching
- Reason code registry for standardized decision rationales
- Tiered precedent query engine (Tier 0, 0.5, 1)
- Finalization gate for creating JUDGMENT cells on disposition seal
- Seed generation and loading for initial precedent data

Key Components:
- FingerprintSchema: Defines which facts matter for matching
- FingerprintSchemaRegistry: Registry of schemas by policy type
- ReasonCodeRegistry: Standardized reason code definitions
- PrecedentQueryEngine: High-level query interface
- FinalizationGate: Creates JUDGMENT cells on seal
- SeedGenerator: Generates seed precedents from configuration
- SeedLoader: Loads seed precedents into a chain

Design Principles:
- Deterministic: Precedent retrieval and scoring are auditable
- Privacy-preserving: Case IDs are hashed, never stored raw
- LLMs as rendering layer only: Core logic is deterministic
- Transparent seeding: All seeds marked with source_type="seeded"

Example Usage:
    >>> from claimpilot.precedent import (
    ...     FingerprintSchemaRegistry,
    ...     PrecedentQueryEngine,
    ...     FinalizationGate,
    ...     SeedLoader,
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
    >>>
    >>> # Load seed precedents
    >>> loader = SeedLoader(chain, salt="secret")
    >>> stats = loader.load_all()
    >>> print(f"Loaded seeds: {sum(s.total_loaded for s in stats.values())}")
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
    # Banding rule factories
    create_days_vacant_banding,
    create_coverage_months_banding,
    create_claim_amount_banding,
    create_treatment_cost_banding,
    # Schema factories
    create_ontario_auto_schema_v1,
    create_property_ho3_schema_v1,
    create_marine_schema_v1,
    create_health_schema_v1,
    create_wsib_schema_v1,
    create_cgl_schema_v1,
    create_eo_schema_v1,
    create_travel_schema_v1,
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
    create_property_registry_v1,
    create_marine_registry_v1,
    create_health_registry_v1,
    create_wsib_registry_v1,
    create_cgl_registry_v1,
    create_eo_registry_v1,
    create_travel_registry_v1,
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

# Seed Generator
from .seed_generator import (
    SeedGeneratorError,
    SeedConfigError,
    SeedConfig,
    CleanApprovalConfig,
    SeedGenerator,
    DECISION_LEVEL_WEIGHTS,
    CERTAINTY_WEIGHTS,
)

# Seed Loader
from .seed_loader import (
    SeedLoaderError,
    SeedLoadError,
    SeedVerificationError,
    SeedVerificationResult,
    SeedLoadStats,
    SeedLoader,
)

# Seed Configuration Utilities
from .seeds import (
    SeedConfigLoadError,
    list_seed_configs,
    load_seed_config,
    load_all_seed_configs,
    get_seed_config_path,
    SEEDS_DIR,
)

# Master Banding Library
from .banding_library import (
    BandingLibrary,
    BandingRule as MasterBandingRule,
    # Universal bands
    RegimeBand,
    AuthorityBand,
    ConflictBand,
    # Auto bands
    AutoBACBand,
    AutoLicenseClassBand,
    AutoLicenseStatusBand,
    AutoVehicleUseBand,
    AutoVehicleValueBand,
    AutoFaultBand,
    AutoSpeedingBand,
    # Marine bands
    MarineNavigationBand,
    MarineJurisdictionBand,
    MarineLayupBand,
    MarineMaintenanceBand,
    # CGL bands
    CGLBusinessTypeBand,
    CGLRevenueBand,
    CGLInjuryTypeBand,
    CGLNegligenceBand,
    # Property bands
    PropertyLossCauseBand,
    PropertyVacancyBand,
    PropertyClaimAmountBand,
    # Banking bands
    BankingAmountBand,
    BankingVelocityBand,
    BankingJurisdictionBand,
    BankingPEPBand,
    BankingRiskScoreBand,
    # Banding functions
    band_bac_level,
    band_claim_amount,
    band_vacancy_days,
    band_transaction_amount,
    band_risk_score,
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

    # Reason Code Registry
    "ReasonCodeError",
    "ReasonCodeNotFoundError",
    "RegistryNotFoundError",
    "InvalidReasonCodeError",
    "ReasonCodeDefinition",
    "ReasonCodeRegistryDefinition",
    "ReasonCodeRegistry",
    "create_ontario_auto_registry_v1",
    "create_property_registry_v1",
    "create_marine_registry_v1",
    "create_health_registry_v1",
    "create_wsib_registry_v1",
    "create_cgl_registry_v1",
    "create_eo_registry_v1",
    "create_travel_registry_v1",

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

    # Seed Generator
    "SeedGeneratorError",
    "SeedConfigError",
    "SeedConfig",
    "CleanApprovalConfig",
    "SeedGenerator",
    "DECISION_LEVEL_WEIGHTS",
    "CERTAINTY_WEIGHTS",

    # Seed Loader
    "SeedLoaderError",
    "SeedLoadError",
    "SeedVerificationError",
    "SeedVerificationResult",
    "SeedLoadStats",
    "SeedLoader",

    # Seed Configuration Utilities
    "SeedConfigLoadError",
    "list_seed_configs",
    "load_seed_config",
    "load_all_seed_configs",
    "get_seed_config_path",
    "SEEDS_DIR",

    # Master Banding Library
    "BandingLibrary",
    "MasterBandingRule",
    # Universal bands
    "RegimeBand",
    "AuthorityBand",
    "ConflictBand",
    # Auto bands
    "AutoBACBand",
    "AutoLicenseClassBand",
    "AutoLicenseStatusBand",
    "AutoVehicleUseBand",
    "AutoVehicleValueBand",
    "AutoFaultBand",
    "AutoSpeedingBand",
    # Marine bands
    "MarineNavigationBand",
    "MarineJurisdictionBand",
    "MarineLayupBand",
    "MarineMaintenanceBand",
    # CGL bands
    "CGLBusinessTypeBand",
    "CGLRevenueBand",
    "CGLInjuryTypeBand",
    "CGLNegligenceBand",
    # Property bands
    "PropertyLossCauseBand",
    "PropertyVacancyBand",
    "PropertyClaimAmountBand",
    # Banking bands
    "BankingAmountBand",
    "BankingVelocityBand",
    "BankingJurisdictionBand",
    "BankingPEPBand",
    "BankingRiskScoreBand",
    # Banding functions
    "band_bac_level",
    "band_claim_amount",
    "band_vacancy_days",
    "band_transaction_amount",
    "band_risk_score",
]
