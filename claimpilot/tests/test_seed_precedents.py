"""
Tests for the Seed Precedent System.

Tests cover:
- Schema registration and retrieval for all 8 policy types
- Reason code validation for all registries
- Banding correctness for continuous values
- Fingerprint determinism (same facts -> same hash)
- Generator output distribution verification
- YAML config loading
"""

import pytest
from datetime import date

from claimpilot.precedent import (
    # Fingerprint schemas
    FingerprintSchemaRegistry,
    FingerprintSchema,
    BandingRule,
    SchemaNotFoundError,
    create_ontario_auto_schema_v1,
    create_property_ho3_schema_v1,
    create_marine_schema_v1,
    create_health_schema_v1,
    create_wsib_schema_v1,
    create_cgl_schema_v1,
    create_eo_schema_v1,
    create_travel_schema_v1,
    # Banding rules
    create_days_vacant_banding,
    create_coverage_months_banding,
    create_claim_amount_banding,
    create_treatment_cost_banding,
    # Reason code registry
    ReasonCodeRegistry,
    create_ontario_auto_registry_v1,
    create_property_registry_v1,
    create_marine_registry_v1,
    create_health_registry_v1,
    create_wsib_registry_v1,
    create_cgl_registry_v1,
    create_eo_registry_v1,
    create_travel_registry_v1,
    # Seed generator
    SeedGenerator,
    SeedConfig,
    CleanApprovalConfig,
    SeedConfigError,
    # Seed config loader
    list_seed_configs,
    load_seed_config,
    load_all_seed_configs,
    SeedConfigLoadError,
)


# =============================================================================
# Schema Registration Tests
# =============================================================================

class TestFingerprintSchemaRegistry:
    """Tests for fingerprint schema registration."""

    def test_all_schemas_registered(self):
        """All 8 schemas should be registered in the registry."""
        registry = FingerprintSchemaRegistry()

        # Test each policy type can be retrieved
        policy_types = [
            ("auto", "CA-ON"),
            ("property", "CA-ON"),
            ("marine", "CA-ON"),
            ("health", "CA-ON"),
            ("wsib", "CA-ON"),
            ("cgl", "CA-ON"),
            ("eo", "CA-ON"),
            ("travel", "CA-ON"),
        ]

        for policy_type, jurisdiction in policy_types:
            schema = registry.get_schema(policy_type, jurisdiction)
            assert schema is not None
            assert schema.policy_type == policy_type
            assert schema.jurisdiction == jurisdiction

    def test_schema_not_found(self):
        """Should raise SchemaNotFoundError for unknown policy type."""
        registry = FingerprintSchemaRegistry()

        with pytest.raises(SchemaNotFoundError):
            registry.get_schema("unknown", "CA-ON")

    def test_auto_schema_facts(self):
        """Auto schema should have expected facts."""
        schema = create_ontario_auto_schema_v1()

        assert "vehicle.use_at_loss" in schema.exclusion_relevant_facts
        assert "driver.rideshare_app_active" in schema.exclusion_relevant_facts
        assert "driver.bac_level" in schema.exclusion_relevant_facts

    def test_property_schema_facts(self):
        """Property schema should have expected facts."""
        schema = create_property_ho3_schema_v1()

        assert "loss.cause" in schema.exclusion_relevant_facts
        assert "water.source" in schema.exclusion_relevant_facts
        assert "dwelling.days_vacant" in schema.exclusion_relevant_facts
        assert "arson.suspected" in schema.exclusion_relevant_facts


# =============================================================================
# Banding Rules Tests
# =============================================================================

class TestBandingRules:
    """Tests for banding rule correctness."""

    def test_days_vacant_banding(self):
        """Days vacant should band correctly."""
        rule = create_days_vacant_banding()

        assert rule.apply(0) == "occupied"
        assert rule.apply(1) == "short"
        assert rule.apply(15) == "short"
        assert rule.apply(30) == "short"
        assert rule.apply(31) == "medium"
        assert rule.apply(45) == "medium"
        assert rule.apply(60) == "medium"
        assert rule.apply(61) == "long"
        assert rule.apply(90) == "long"
        assert rule.apply(365) == "long"

    def test_coverage_months_banding(self):
        """Coverage months should band correctly."""
        rule = create_coverage_months_banding()

        assert rule.apply(0) == "new"
        assert rule.apply(1) == "new"
        assert rule.apply(3) == "new"
        assert rule.apply(4) == "waiting"
        assert rule.apply(6) == "waiting"
        assert rule.apply(11) == "waiting"
        assert rule.apply(12) == "established"
        assert rule.apply(24) == "established"
        assert rule.apply(60) == "established"

    def test_claim_amount_banding(self):
        """Claim amount should band correctly."""
        rule = create_claim_amount_banding()

        assert rule.apply(0) == "small"
        assert rule.apply(10000) == "small"
        assert rule.apply(25000) == "small"
        assert rule.apply(25001) == "medium"
        assert rule.apply(50000) == "medium"
        assert rule.apply(100000) == "medium"
        assert rule.apply(100001) == "large"
        assert rule.apply(250000) == "large"
        assert rule.apply(500000) == "large"
        assert rule.apply(500001) == "major"
        assert rule.apply(1000000) == "major"

    def test_treatment_cost_banding(self):
        """Treatment cost should band correctly."""
        rule = create_treatment_cost_banding()

        assert rule.apply(0) == "low"
        assert rule.apply(500) == "low"
        assert rule.apply(1000) == "low"
        assert rule.apply(1001) == "medium"
        assert rule.apply(5000) == "medium"
        assert rule.apply(10000) == "medium"
        assert rule.apply(10001) == "high"
        assert rule.apply(25000) == "high"
        assert rule.apply(50000) == "high"
        assert rule.apply(50001) == "critical"
        assert rule.apply(100000) == "critical"

    def test_banding_null_value(self):
        """Banding should handle null values."""
        rule = create_days_vacant_banding()
        assert rule.apply(None) == "unknown"


# =============================================================================
# Reason Code Registry Tests
# =============================================================================

class TestReasonCodeRegistry:
    """Tests for reason code registry."""

    def test_all_registries_registered(self):
        """All 8 registries should be available."""
        registry = ReasonCodeRegistry()

        expected_registries = [
            "claimpilot:auto:v1",
            "claimpilot:property:v1",
            "claimpilot:marine:v1",
            "claimpilot:health:v1",
            "claimpilot:wsib:v1",
            "claimpilot:cgl:v1",
            "claimpilot:eo:v1",
            "claimpilot:travel:v1",
        ]

        actual_registries = registry.list_registries()

        for expected in expected_registries:
            assert expected in actual_registries, f"Missing registry: {expected}"

    def test_auto_registry_codes(self):
        """Auto registry should have expected codes."""
        reg = create_ontario_auto_registry_v1()

        assert "RC-4.2.1" in reg.codes
        assert "RC-4.3.1" in reg.codes
        assert "RC-4.3.3" in reg.codes
        assert "RC-4.4.1" in reg.codes
        assert "RC-4.5.1" in reg.codes
        assert "RC-COV-CONFIRMED" in reg.codes

    def test_property_registry_codes(self):
        """Property registry should have expected codes."""
        reg = create_property_registry_v1()

        assert "RC-FLOOD" in reg.codes
        assert "RC-EARTH" in reg.codes
        assert "RC-VACANT" in reg.codes
        assert "RC-GRADUAL" in reg.codes
        assert "RC-INTENT" in reg.codes

    def test_marine_registry_codes(self):
        """Marine registry should have expected codes."""
        reg = create_marine_registry_v1()

        assert "RC-NAV" in reg.codes
        assert "RC-PCOC" in reg.codes
        assert "RC-COMM" in reg.codes
        assert "RC-RACE" in reg.codes
        assert "RC-ICE" in reg.codes

    def test_health_registry_codes(self):
        """Health registry should have expected codes."""
        reg = create_health_registry_v1()

        assert "RC-FORM" in reg.codes
        assert "RC-PRE" in reg.codes
        assert "RC-WORK" in reg.codes
        assert "RC-COSM" in reg.codes
        assert "RC-EXP" in reg.codes

    def test_wsib_registry_codes(self):
        """WSIB registry should have expected codes."""
        reg = create_wsib_registry_v1()

        assert "RC-NWR" in reg.codes
        assert "RC-PRE" in reg.codes
        assert "RC-INTOX" in reg.codes
        assert "RC-SELF" in reg.codes
        assert "RC-MISC" in reg.codes

    def test_cgl_registry_codes(self):
        """CGL registry should have expected codes."""
        reg = create_cgl_registry_v1()

        assert "RC-INTENT" in reg.codes
        assert "RC-POLL" in reg.codes
        assert "RC-AUTO" in reg.codes
        assert "RC-PROF" in reg.codes
        assert "RC-CONTRACT" in reg.codes

    def test_eo_registry_codes(self):
        """E&O registry should have expected codes."""
        reg = create_eo_registry_v1()

        assert "RC-PRIOR" in reg.codes
        assert "RC-KNOWN" in reg.codes
        assert "RC-FRAUD" in reg.codes
        assert "RC-BI" in reg.codes

    def test_travel_registry_codes(self):
        """Travel registry should have expected codes."""
        reg = create_travel_registry_v1()

        assert "RC-PRE" in reg.codes
        assert "RC-RISK" in reg.codes
        assert "RC-ADVISORY" in reg.codes
        assert "RC-ELECT" in reg.codes
        assert "RC-EMERG" in reg.codes

    def test_validate_code(self):
        """Should validate codes correctly."""
        registry = ReasonCodeRegistry()

        assert registry.validate_code("RC-4.2.1", "claimpilot:auto:v1")
        assert registry.validate_code("RC-FLOOD", "claimpilot:property:v1")
        assert not registry.validate_code("RC-INVALID", "claimpilot:auto:v1")


# =============================================================================
# Fingerprint Determinism Tests
# =============================================================================

class TestFingerprintDeterminism:
    """Tests for fingerprint hash determinism."""

    def test_same_facts_same_fingerprint(self):
        """Same facts should produce same fingerprint hash."""
        registry = FingerprintSchemaRegistry()
        schema = registry.get_schema("auto", "CA-ON")
        salt = "test-salt-12345"

        facts = {
            "vehicle.use_at_loss": "personal",
            "driver.rideshare_app_active": False,
            "driver.bac_level": 0.0,
            "driver.license_status": "valid",
            "driver.impairment_indicated": False,
            "loss.racing_activity": False,
        }

        fp1 = registry.compute_fingerprint(schema, facts, salt)
        fp2 = registry.compute_fingerprint(schema, facts, salt)

        assert fp1 == fp2
        assert len(fp1) == 64  # SHA-256 hex

    def test_different_facts_different_fingerprint(self):
        """Different facts should produce different fingerprint hash."""
        registry = FingerprintSchemaRegistry()
        schema = registry.get_schema("auto", "CA-ON")
        salt = "test-salt-12345"

        facts1 = {
            "vehicle.use_at_loss": "personal",
            "driver.bac_level": 0.0,
        }

        facts2 = {
            "vehicle.use_at_loss": "commercial",
            "driver.bac_level": 0.0,
        }

        fp1 = registry.compute_fingerprint(schema, facts1, salt)
        fp2 = registry.compute_fingerprint(schema, facts2, salt)

        assert fp1 != fp2

    def test_different_salt_different_fingerprint(self):
        """Different salt should produce different fingerprint hash."""
        registry = FingerprintSchemaRegistry()
        schema = registry.get_schema("auto", "CA-ON")

        facts = {
            "vehicle.use_at_loss": "personal",
            "driver.bac_level": 0.0,
        }

        fp1 = registry.compute_fingerprint(schema, facts, "salt-1")
        fp2 = registry.compute_fingerprint(schema, facts, "salt-2")

        assert fp1 != fp2


# =============================================================================
# Seed Generator Tests
# =============================================================================

class TestSeedGenerator:
    """Tests for seed generator."""

    def test_generate_precedents_count(self):
        """Generator should produce correct number of precedents."""
        generator = SeedGenerator(salt="test-salt")

        configs = [
            SeedConfig(
                exclusion_code="4.2.1",
                count=10,
                deny_rate=0.9,
                appeal_rate=0.2,
                upheld_rate=0.8,
                base_facts={"policy.status": "active"},
            ),
        ]

        precedents = generator.generate_precedents(
            policy_type="auto",
            jurisdiction="CA-ON",
            configs=configs,
            policy_pack_id="TEST-001",
        )

        assert len(precedents) == 10

    def test_generate_with_clean_approvals(self):
        """Generator should include clean approvals."""
        generator = SeedGenerator(salt="test-salt")

        configs = [
            SeedConfig(
                exclusion_code="4.2.1",
                count=5,
                deny_rate=0.9,
                appeal_rate=0.2,
                upheld_rate=0.8,
            ),
        ]

        clean = CleanApprovalConfig(count=3, appeal_rate=0.05)

        precedents = generator.generate_precedents(
            policy_type="auto",
            jurisdiction="CA-ON",
            configs=configs,
            policy_pack_id="TEST-001",
            clean_approvals=clean,
        )

        assert len(precedents) == 8  # 5 + 3

    def test_precedent_has_required_fields(self):
        """Generated precedents should have all required fields."""
        generator = SeedGenerator(salt="test-salt")

        configs = [
            SeedConfig(
                exclusion_code="4.2.1",
                count=1,
                deny_rate=1.0,  # Always deny
                appeal_rate=0.0,
                upheld_rate=0.0,
            ),
        ]

        precedents = generator.generate_precedents(
            policy_type="auto",
            jurisdiction="CA-ON",
            configs=configs,
            policy_pack_id="TEST-001",
        )

        p = precedents[0]

        assert p.precedent_id
        assert p.case_id_hash
        assert p.jurisdiction_code == "CA-ON"
        assert p.fingerprint_hash
        assert p.fingerprint_schema_id == "claimpilot:oap1:auto:v1"
        assert p.outcome_code in ["pay", "deny", "partial", "escalate"]
        assert p.certainty in ["high", "medium", "low"]
        assert p.decision_level in ["adjuster", "manager", "tribunal", "court"]
        assert p.source_type == "seeded"

    def test_deny_rate_distribution(self):
        """Deny rate should approximately match configuration."""
        generator = SeedGenerator(salt="distribution-test")

        configs = [
            SeedConfig(
                exclusion_code="4.2.1",
                count=100,
                deny_rate=0.8,
                appeal_rate=0.0,
                upheld_rate=0.0,
            ),
        ]

        precedents = generator.generate_precedents(
            policy_type="auto",
            jurisdiction="CA-ON",
            configs=configs,
            policy_pack_id="TEST-001",
        )

        denials = sum(1 for p in precedents if p.outcome_code == "deny")

        # Allow some variance (70-90 out of 100)
        assert 70 <= denials <= 90

    def test_source_type_is_seeded(self):
        """All generated precedents should have source_type=seeded."""
        generator = SeedGenerator(salt="test-salt")

        configs = [
            SeedConfig(
                exclusion_code="4.2.1",
                count=5,
                deny_rate=0.5,
                appeal_rate=0.5,
                upheld_rate=0.5,
            ),
        ]

        precedents = generator.generate_precedents(
            policy_type="auto",
            jurisdiction="CA-ON",
            configs=configs,
            policy_pack_id="TEST-001",
        )

        for p in precedents:
            assert p.source_type == "seeded"

    def test_deterministic_generation(self):
        """Same salt and config should produce same results."""
        configs = [
            SeedConfig(
                exclusion_code="4.2.1",
                count=10,
                deny_rate=0.5,
                appeal_rate=0.2,
                upheld_rate=0.8,
            ),
        ]

        gen1 = SeedGenerator(salt="determinism-test")
        gen2 = SeedGenerator(salt="determinism-test")

        precedents1 = gen1.generate_precedents(
            policy_type="auto",
            jurisdiction="CA-ON",
            configs=configs,
            policy_pack_id="TEST-001",
        )

        precedents2 = gen2.generate_precedents(
            policy_type="auto",
            jurisdiction="CA-ON",
            configs=configs,
            policy_pack_id="TEST-001",
        )

        # Same outcomes
        outcomes1 = [p.outcome_code for p in precedents1]
        outcomes2 = [p.outcome_code for p in precedents2]
        assert outcomes1 == outcomes2

        # Same fingerprints
        fps1 = [p.fingerprint_hash for p in precedents1]
        fps2 = [p.fingerprint_hash for p in precedents2]
        assert fps1 == fps2


# =============================================================================
# Seed Config Tests
# =============================================================================

class TestSeedConfig:
    """Tests for seed configuration validation."""

    def test_valid_config(self):
        """Valid config should create successfully."""
        config = SeedConfig(
            exclusion_code="4.2.1",
            count=10,
            deny_rate=0.9,
            appeal_rate=0.2,
            upheld_rate=0.8,
        )
        assert config.count == 10

    def test_invalid_deny_rate(self):
        """Deny rate outside 0-1 should fail."""
        with pytest.raises(SeedConfigError):
            SeedConfig(
                exclusion_code="4.2.1",
                count=10,
                deny_rate=1.5,  # Invalid
                appeal_rate=0.2,
                upheld_rate=0.8,
            )

    def test_invalid_appeal_rate(self):
        """Appeal rate outside 0-1 should fail."""
        with pytest.raises(SeedConfigError):
            SeedConfig(
                exclusion_code="4.2.1",
                count=10,
                deny_rate=0.9,
                appeal_rate=-0.1,  # Invalid
                upheld_rate=0.8,
            )

    def test_empty_exclusion_code(self):
        """Empty exclusion code should fail."""
        with pytest.raises(SeedConfigError):
            SeedConfig(
                exclusion_code="",  # Invalid
                count=10,
                deny_rate=0.9,
                appeal_rate=0.2,
                upheld_rate=0.8,
            )


# =============================================================================
# YAML Config Loader Tests
# =============================================================================

class TestSeedConfigLoader:
    """Tests for YAML seed config loading."""

    def test_list_seed_configs(self):
        """Should list all available seed configs."""
        configs = list_seed_configs()

        expected = [
            "auto_oap1",
            "property_ho3",
            "marine",
            "health",
            "wsib",
            "cgl",
            "eo",
            "travel",
        ]

        for name in expected:
            assert name in configs, f"Missing config: {name}"

    def test_load_auto_config(self):
        """Should load auto_oap1 config."""
        config = load_seed_config("auto_oap1")

        assert config["schema_id"] == "claimpilot:oap1:auto:v1"
        assert config["jurisdiction"] == "CA-ON"
        assert "exclusions" in config
        assert len(config["exclusions"]) > 0
        assert "clean_approvals" in config

    def test_load_property_config(self):
        """Should load property_ho3 config."""
        config = load_seed_config("property_ho3")

        assert config["schema_id"] == "claimpilot:ho3:property:v1"
        assert "exclusions" in config

    def test_load_all_configs(self):
        """Should load all configs."""
        all_configs = load_all_seed_configs()

        assert len(all_configs) >= 8
        assert "auto_oap1" in all_configs
        assert "property_ho3" in all_configs

    def test_load_nonexistent_config(self):
        """Should raise error for nonexistent config."""
        with pytest.raises(SeedConfigLoadError):
            load_seed_config("nonexistent_policy")

    def test_config_exclusion_structure(self):
        """Exclusion configs should have required fields."""
        config = load_seed_config("auto_oap1")

        for exclusion in config["exclusions"]:
            assert "code" in exclusion
            assert "count" in exclusion
            assert "deny_rate" in exclusion
            assert "appeal_rate" in exclusion
            assert "upheld_rate" in exclusion


# =============================================================================
# Cross-Schema Isolation Tests
# =============================================================================

class TestCrossSchemaIsolation:
    """Tests for cross-schema isolation."""

    def test_auto_fingerprint_different_from_property(self):
        """Auto and property fingerprints should be different for same facts."""
        registry = FingerprintSchemaRegistry()
        salt = "isolation-test"

        # Use common facts that exist in both schemas (conceptually)
        auto_schema = registry.get_schema("auto", "CA-ON")
        property_schema = registry.get_schema("property", "CA-ON")

        # Auto facts
        auto_facts = {
            "vehicle.use_at_loss": "personal",
        }

        # Property facts
        property_facts = {
            "loss.cause": "fire",
        }

        auto_fp = registry.compute_fingerprint(auto_schema, auto_facts, salt)
        property_fp = registry.compute_fingerprint(property_schema, property_facts, salt)

        # Different schemas produce different fingerprints
        assert auto_fp != property_fp

    def test_schema_ids_are_unique(self):
        """All schema IDs should be unique."""
        schemas = [
            create_ontario_auto_schema_v1(),
            create_property_ho3_schema_v1(),
            create_marine_schema_v1(),
            create_health_schema_v1(),
            create_wsib_schema_v1(),
            create_cgl_schema_v1(),
            create_eo_schema_v1(),
            create_travel_schema_v1(),
        ]

        schema_ids = [s.schema_id for s in schemas]
        assert len(schema_ids) == len(set(schema_ids)), "Duplicate schema IDs found"


# =============================================================================
# Seed Volume Verification Tests
# =============================================================================

class TestSeedVolumeVerification:
    """Tests to verify planned seed volumes."""

    def test_auto_seed_volume(self):
        """Auto should produce ~500 seeds from config."""
        config = load_seed_config("auto_oap1")

        exclusion_count = sum(e["count"] for e in config["exclusions"])
        clean_count = config.get("clean_approvals", {}).get("count", 0)
        total = exclusion_count + clean_count

        # Should be approximately 500
        assert 450 <= total <= 550

    def test_property_seed_volume(self):
        """Property should produce ~300 seeds from config."""
        config = load_seed_config("property_ho3")

        exclusion_count = sum(e["count"] for e in config["exclusions"])
        clean_count = config.get("clean_approvals", {}).get("count", 0)
        total = exclusion_count + clean_count

        # Should be approximately 300
        assert 270 <= total <= 330

    def test_total_insurance_seed_volume(self):
        """Total insurance seeds should be ~2150."""
        all_configs = load_all_seed_configs()

        total = 0
        for name, config in all_configs.items():
            exclusion_count = sum(e.get("count", 0) for e in config.get("exclusions", []))
            clean_count = config.get("clean_approvals", {}).get("count", 0)
            total += exclusion_count + clean_count

        # Should be approximately 2150
        assert 2000 <= total <= 2300
