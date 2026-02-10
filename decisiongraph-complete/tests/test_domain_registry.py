"""Tests for v3 Domain Registry and Banking Domain configuration."""

import pytest

from decisiongraph.domain_registry import (
    ComparisonFn,
    ComparabilityGate,
    ConfidenceLevel,
    DomainRegistry,
    FieldDefinition,
    FieldTier,
    FieldType,
)
from decisiongraph.banking_domain import create_banking_domain_registry
from decisiongraph.banking_field_registry import BANKING_FIELDS


# ---------------------------------------------------------------------------
# FieldDefinition
# ---------------------------------------------------------------------------

class TestFieldDefinition:
    def test_valid_construction(self):
        fd = FieldDefinition(
            name="test.field",
            label="Test Field",
            type=FieldType.BOOLEAN,
            comparison=ComparisonFn.EXACT,
            weight=0.05,
            tier=FieldTier.BEHAVIORAL,
        )
        assert fd.name == "test.field"
        assert fd.weight == 0.05
        assert fd.critical is False

    def test_weight_validation_too_high(self):
        with pytest.raises(ValueError, match="weight must be 0.0–1.0"):
            FieldDefinition(
                name="bad", label="Bad", type=FieldType.BOOLEAN,
                comparison=ComparisonFn.EXACT, weight=1.5, tier=FieldTier.BEHAVIORAL,
            )

    def test_weight_validation_negative(self):
        with pytest.raises(ValueError, match="weight must be 0.0–1.0"):
            FieldDefinition(
                name="bad", label="Bad", type=FieldType.BOOLEAN,
                comparison=ComparisonFn.EXACT, weight=-0.1, tier=FieldTier.BEHAVIORAL,
            )

    def test_equivalence_class_requires_classes(self):
        with pytest.raises(ValueError, match="requires equivalence_classes"):
            FieldDefinition(
                name="bad", label="Bad", type=FieldType.CATEGORICAL,
                comparison=ComparisonFn.EQUIVALENCE_CLASS, weight=0.05,
                tier=FieldTier.STRUCTURAL,
            )

    def test_step_requires_ordered_values(self):
        with pytest.raises(ValueError, match="requires ordered_values"):
            FieldDefinition(
                name="bad", label="Bad", type=FieldType.ORDINAL,
                comparison=ComparisonFn.STEP, weight=0.05,
                tier=FieldTier.BEHAVIORAL,
            )

    def test_frozen(self):
        fd = FieldDefinition(
            name="test", label="Test", type=FieldType.BOOLEAN,
            comparison=ComparisonFn.EXACT, weight=0.05, tier=FieldTier.BEHAVIORAL,
        )
        with pytest.raises(AttributeError):
            fd.weight = 0.99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ComparabilityGate
# ---------------------------------------------------------------------------

class TestComparabilityGate:
    def test_classify_found(self):
        gate = ComparabilityGate(
            field="customer_segment",
            equivalence_classes={
                "retail": ["individual", "personal"],
                "corporate": ["corporation", "company"],
            },
        )
        assert gate.classify("individual") == "retail"
        assert gate.classify("corporation") == "corporate"

    def test_classify_case_insensitive(self):
        gate = ComparabilityGate(
            field="jurisdiction_regime",
            equivalence_classes={"CA_FINTRAC": ["CA", "CA-ON"]},
        )
        assert gate.classify("ca") == "CA_FINTRAC"
        assert gate.classify("CA-ON") == "CA_FINTRAC"

    def test_classify_not_found(self):
        gate = ComparabilityGate(
            field="test", equivalence_classes={"a": ["x"]},
        )
        assert gate.classify("unknown") is None

    def test_classify_none(self):
        gate = ComparabilityGate(
            field="test", equivalence_classes={"a": ["x"]},
        )
        assert gate.classify(None) is None

    def test_broadest_class(self):
        gate = ComparabilityGate(
            field="test",
            equivalence_classes={
                "small": ["a"],
                "big": ["b", "c", "d"],
            },
        )
        assert gate.broadest_class() == "big"


# ---------------------------------------------------------------------------
# ConfidenceLevel ordering
# ---------------------------------------------------------------------------

class TestConfidenceLevel:
    def test_ordering(self):
        assert ConfidenceLevel.NONE < ConfidenceLevel.LOW
        assert ConfidenceLevel.LOW < ConfidenceLevel.MODERATE
        assert ConfidenceLevel.MODERATE < ConfidenceLevel.HIGH
        assert ConfidenceLevel.HIGH < ConfidenceLevel.VERY_HIGH

    def test_min(self):
        levels = [ConfidenceLevel.HIGH, ConfidenceLevel.LOW, ConfidenceLevel.MODERATE]
        assert min(levels) == ConfidenceLevel.LOW

    def test_equality(self):
        assert ConfidenceLevel.HIGH == ConfidenceLevel.HIGH
        assert ConfidenceLevel.HIGH >= ConfidenceLevel.HIGH
        assert ConfidenceLevel.HIGH <= ConfidenceLevel.HIGH


# ---------------------------------------------------------------------------
# DomainRegistry
# ---------------------------------------------------------------------------

class TestDomainRegistry:
    def test_get_scoring_fields_excludes_structural(self):
        fd_struct = FieldDefinition(
            name="s", label="S", type=FieldType.CATEGORICAL,
            comparison=ComparisonFn.EQUIVALENCE_CLASS, weight=0.05,
            tier=FieldTier.STRUCTURAL, equivalence_classes={"a": ["x"]},
        )
        fd_behav = FieldDefinition(
            name="b", label="B", type=FieldType.BOOLEAN,
            comparison=ComparisonFn.EXACT, weight=0.10,
            tier=FieldTier.BEHAVIORAL,
        )
        reg = DomainRegistry(
            domain="test", version="1.0",
            fields={"s": fd_struct, "b": fd_behav},
            comparability_gates=[],
        )
        scoring = reg.get_scoring_fields()
        assert len(scoring) == 1
        assert scoring[0].name == "b"

    def test_total_weight(self):
        fd = FieldDefinition(
            name="a", label="A", type=FieldType.BOOLEAN,
            comparison=ComparisonFn.EXACT, weight=0.30,
            tier=FieldTier.BEHAVIORAL,
        )
        reg = DomainRegistry(
            domain="test", version="1.0",
            fields={"a": fd}, comparability_gates=[],
        )
        assert reg.total_weight() == 0.30

    def test_similarity_floor_override(self):
        reg = DomainRegistry(
            domain="test", version="1.0", fields={}, comparability_gates=[],
            similarity_floor=0.60,
            similarity_floor_overrides={"sanctions": 0.80},
        )
        assert reg.get_similarity_floor_for_typology("sanctions") == 0.80
        assert reg.get_similarity_floor_for_typology("other") == 0.60


# ---------------------------------------------------------------------------
# Banking Domain Registry
# ---------------------------------------------------------------------------

class TestBankingDomainRegistry:
    @pytest.fixture
    def registry(self) -> DomainRegistry:
        return create_banking_domain_registry()

    def test_domain_and_version(self, registry: DomainRegistry):
        assert registry.domain == "banking_aml"
        assert registry.version == "3.0"

    def test_all_banking_fields_covered(self, registry: DomainRegistry):
        """Every field in BANKING_FIELDS must have a v3 FieldDefinition."""
        for canonical_name in BANKING_FIELDS:
            assert canonical_name in registry.fields, (
                f"BANKING_FIELDS[{canonical_name!r}] missing from v3 registry"
            )

    def test_field_count_matches(self, registry: DomainRegistry):
        assert len(registry.fields) == len(BANKING_FIELDS)

    def test_labels_match_legacy(self, registry: DomainRegistry):
        """v3 labels must match legacy display_name."""
        for name, fd in registry.fields.items():
            legacy = BANKING_FIELDS[name]
            assert fd.label == legacy["display_name"], (
                f"Label mismatch for {name}: {fd.label!r} vs {legacy['display_name']!r}"
            )

    def test_critical_fields(self, registry: DomainRegistry):
        assert registry.critical_fields == frozenset({
            "txn.type", "txn.amount_band", "customer.type",
        })

    def test_similarity_floor_defaults(self, registry: DomainRegistry):
        assert registry.similarity_floor == 0.60
        assert registry.similarity_floor_overrides["sanctions"] == 0.80
        assert registry.similarity_floor_overrides["structuring"] == 0.65
        assert registry.similarity_floor_overrides["adverse_media"] == 0.55

    def test_pool_minimum(self, registry: DomainRegistry):
        assert registry.pool_minimum == 5

    def test_four_gates(self, registry: DomainRegistry):
        gate_fields = registry.get_gate_fields()
        assert "jurisdiction_regime" in gate_fields
        assert "customer_segment" in gate_fields
        assert "channel_family" in gate_fields
        assert "disposition_basis" in gate_fields
        assert len(gate_fields) == 4

    def test_gate_jurisdiction_classes(self, registry: DomainRegistry):
        jgate = next(g for g in registry.comparability_gates if g.field == "jurisdiction_regime")
        assert jgate.classify("CA") == "CA_FINTRAC"
        assert jgate.classify("US") == "US_FinCEN"
        assert jgate.classify("UK") == "UK_FCA"
        assert jgate.classify("GB") == "UK_FCA"

    def test_gate_customer_segment(self, registry: DomainRegistry):
        cgate = next(g for g in registry.comparability_gates if g.field == "customer_segment")
        assert cgate.classify("individual") == "retail"
        assert cgate.classify("corporation") == "corporate"
        assert cgate.classify("sole_prop") == "retail"
        assert cgate.classify("bank") == "FI"

    def test_gate_channel_family(self, registry: DomainRegistry):
        chgate = next(g for g in registry.comparability_gates if g.field == "channel_family")
        assert chgate.classify("wire_domestic") == "electronic"
        assert chgate.classify("cash") == "cash"
        assert chgate.classify("crypto") == "crypto"
        assert chgate.classify("cheque") == "cheque"

    def test_gate_disposition_basis(self, registry: DomainRegistry):
        bgate = next(g for g in registry.comparability_gates if g.field == "disposition_basis")
        assert bgate.classify("MANDATORY") == "MANDATORY"
        assert bgate.classify("DISCRETIONARY") == "DISCRETIONARY"
        assert bgate.classify("UNKNOWN") is None

    def test_structural_fields(self, registry: DomainRegistry):
        structural = {f.name for f in registry.get_structural_fields()}
        assert "customer.type" in structural
        assert "txn.type" in structural

    def test_behavioral_fields_include_flags(self, registry: DomainRegistry):
        behavioral = {f.name for f in registry.get_behavioral_fields()}
        assert "flag.structuring" in behavioral
        assert "flag.layering" in behavioral
        assert "screening.sanctions_match" in behavioral

    def test_contextual_fields(self, registry: DomainRegistry):
        contextual = {f.name for f in registry.get_contextual_fields()}
        assert "txn.source_of_funds_clear" in contextual
        assert "txn.stated_purpose" in contextual
        assert "customer.cash_intensive" in contextual

    def test_weights_sum_reasonable(self, registry: DomainRegistry):
        """Total weight across all scoring fields should be in a reasonable range."""
        total = sum(f.weight for f in registry.fields.values())
        assert 0.8 <= total <= 1.2, f"Total field weight {total} outside expected range"

    def test_disposition_mapping(self, registry: DomainRegistry):
        assert registry.disposition_mapping["approve"] == "ALLOW"
        assert registry.disposition_mapping["deny"] == "BLOCK"
        assert registry.disposition_mapping["escalate"] == "EDD"

    def test_reporting_mapping(self, registry: DomainRegistry):
        assert registry.reporting_mapping["str"] == "FILE_STR"
        assert registry.reporting_mapping["lctr"] == "FILE_LCTR"
        assert registry.reporting_mapping["tpr"] == "FILE_TPR"

    def test_basis_mapping(self, registry: DomainRegistry):
        assert registry.basis_mapping["sanctions"] == "MANDATORY"
        assert registry.basis_mapping["risk appetite"] == "DISCRETIONARY"

    def test_comparison_types_correct(self, registry: DomainRegistry):
        """Spot-check comparison function assignments."""
        assert registry.fields["customer.type"].comparison == ComparisonFn.EQUIVALENCE_CLASS
        assert registry.fields["txn.amount_band"].comparison == ComparisonFn.STEP
        assert registry.fields["flag.structuring"].comparison == ComparisonFn.EXACT
        assert registry.fields["prior.sars_filed"].comparison == ComparisonFn.DISTANCE_DECAY
        assert registry.fields["customer.relationship_length"].comparison == ComparisonFn.STEP

    def test_cached(self):
        """create_banking_domain_registry() should return the same object (cached)."""
        r1 = create_banking_domain_registry()
        r2 = create_banking_domain_registry()
        assert r1 is r2
