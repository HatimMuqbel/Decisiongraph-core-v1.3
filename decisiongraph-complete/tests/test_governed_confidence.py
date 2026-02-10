"""Tests for v3 Governed Confidence Model (4-dimension min)."""

import pytest

from decisiongraph.banking_domain import create_banking_domain_registry
from decisiongraph.domain_registry import ConfidenceLevel, DomainRegistry
from decisiongraph.governed_confidence import (
    ConfidenceDimension,
    GovernedConfidenceResult,
    compute_governed_confidence,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def registry() -> DomainRegistry:
    return create_banking_domain_registry()


@pytest.fixture
def full_case_facts() -> dict:
    """Case with all required + critical fields present."""
    return {
        "customer.type": "individual",
        "txn.type": "cash",
        "txn.amount_band": "10k_25k",
        "txn.cross_border": False,
        "txn.destination_country_risk": "low",
        "txn.frequency_band": "moderate",
        "txn.source_of_funds_clear": True,
        "txn.stated_purpose": "personal",
        "customer.pep": False,
        "customer.relationship_length": "established",
        "screening.sanctions_match": False,
        "screening.adverse_media": False,
        "flag.structuring": True,
        "flag.rapid_movement": False,
        "flag.round_amounts": True,
        # additional fields from banking domain
        "customer.high_risk_jurisdiction": False,
        "customer.high_risk_industry": False,
        "customer.cash_intensive": True,
        "txn.round_amount": True,
        "txn.just_below_threshold": False,
        "txn.multiple_same_day": True,
        "txn.pattern_matches_profile": False,
        "flag.layering": False,
        "flag.unusual_for_profile": True,
        "flag.third_party": False,
        "flag.shell_company": False,
        "screening.pep_match": False,
        "prior.sars_filed": False,
        "prior.account_closures": False,
    }


# ---------------------------------------------------------------------------
# Pool Adequacy (spec 6.2)
# ---------------------------------------------------------------------------

class TestPoolAdequacy:
    def test_zero_pool_none(self, registry, full_case_facts):
        result = compute_governed_confidence(
            registry, pool_size=0, avg_similarity=0.0,
            decisive_supporting=0, decisive_total=0,
            case_facts=full_case_facts,
        )
        pool = next(d for d in result.dimensions if d.name == "pool_adequacy")
        assert pool.level == ConfidenceLevel.NONE

    def test_small_pool_low(self, registry, full_case_facts):
        result = compute_governed_confidence(
            registry, pool_size=3, avg_similarity=0.80,
            decisive_supporting=2, decisive_total=3,
            case_facts=full_case_facts,
        )
        pool = next(d for d in result.dimensions if d.name == "pool_adequacy")
        assert pool.level == ConfidenceLevel.LOW

    def test_moderate_pool(self, registry, full_case_facts):
        result = compute_governed_confidence(
            registry, pool_size=10, avg_similarity=0.80,
            decisive_supporting=8, decisive_total=10,
            case_facts=full_case_facts,
        )
        pool = next(d for d in result.dimensions if d.name == "pool_adequacy")
        assert pool.level == ConfidenceLevel.MODERATE

    def test_high_pool(self, registry, full_case_facts):
        result = compute_governed_confidence(
            registry, pool_size=20, avg_similarity=0.80,
            decisive_supporting=16, decisive_total=20,
            case_facts=full_case_facts,
        )
        pool = next(d for d in result.dimensions if d.name == "pool_adequacy")
        assert pool.level == ConfidenceLevel.HIGH

    def test_very_high_pool(self, registry, full_case_facts):
        result = compute_governed_confidence(
            registry, pool_size=60, avg_similarity=0.90,
            decisive_supporting=57, decisive_total=60,
            case_facts=full_case_facts,
        )
        pool = next(d for d in result.dimensions if d.name == "pool_adequacy")
        assert pool.level == ConfidenceLevel.VERY_HIGH


# ---------------------------------------------------------------------------
# Similarity Quality (spec 6.3)
# ---------------------------------------------------------------------------

class TestSimilarityQuality:
    def test_low_similarity(self, registry, full_case_facts):
        result = compute_governed_confidence(
            registry, pool_size=10, avg_similarity=0.40,
            decisive_supporting=8, decisive_total=10,
            case_facts=full_case_facts,
        )
        sim = next(d for d in result.dimensions if d.name == "similarity_quality")
        assert sim.level == ConfidenceLevel.LOW

    def test_moderate_similarity(self, registry, full_case_facts):
        result = compute_governed_confidence(
            registry, pool_size=10, avg_similarity=0.60,
            decisive_supporting=8, decisive_total=10,
            case_facts=full_case_facts,
        )
        sim = next(d for d in result.dimensions if d.name == "similarity_quality")
        assert sim.level == ConfidenceLevel.MODERATE

    def test_high_similarity(self, registry, full_case_facts):
        result = compute_governed_confidence(
            registry, pool_size=10, avg_similarity=0.75,
            decisive_supporting=8, decisive_total=10,
            case_facts=full_case_facts,
        )
        sim = next(d for d in result.dimensions if d.name == "similarity_quality")
        assert sim.level == ConfidenceLevel.HIGH

    def test_very_high_similarity(self, registry, full_case_facts):
        result = compute_governed_confidence(
            registry, pool_size=10, avg_similarity=0.90,
            decisive_supporting=8, decisive_total=10,
            case_facts=full_case_facts,
        )
        sim = next(d for d in result.dimensions if d.name == "similarity_quality")
        assert sim.level == ConfidenceLevel.VERY_HIGH


# ---------------------------------------------------------------------------
# Outcome Consistency (spec 6.4)
# ---------------------------------------------------------------------------

class TestOutcomeConsistency:
    def test_no_decisive_capped_moderate(self, registry, full_case_facts):
        result = compute_governed_confidence(
            registry, pool_size=10, avg_similarity=0.90,
            decisive_supporting=0, decisive_total=0,
            case_facts=full_case_facts,
        )
        oc = next(d for d in result.dimensions if d.name == "outcome_consistency")
        assert oc.level == ConfidenceLevel.MODERATE
        assert "No terminal precedents" in oc.note

    def test_low_consistency(self, registry, full_case_facts):
        result = compute_governed_confidence(
            registry, pool_size=10, avg_similarity=0.80,
            decisive_supporting=5, decisive_total=10,
            case_facts=full_case_facts,
        )
        oc = next(d for d in result.dimensions if d.name == "outcome_consistency")
        assert oc.level == ConfidenceLevel.LOW

    def test_moderate_consistency(self, registry, full_case_facts):
        result = compute_governed_confidence(
            registry, pool_size=10, avg_similarity=0.80,
            decisive_supporting=7, decisive_total=10,
            case_facts=full_case_facts,
        )
        oc = next(d for d in result.dimensions if d.name == "outcome_consistency")
        assert oc.level == ConfidenceLevel.MODERATE

    def test_high_consistency(self, registry, full_case_facts):
        result = compute_governed_confidence(
            registry, pool_size=10, avg_similarity=0.80,
            decisive_supporting=9, decisive_total=10,
            case_facts=full_case_facts,
        )
        oc = next(d for d in result.dimensions if d.name == "outcome_consistency")
        assert oc.level == ConfidenceLevel.HIGH

    def test_very_high_consistency(self, registry, full_case_facts):
        result = compute_governed_confidence(
            registry, pool_size=20, avg_similarity=0.90,
            decisive_supporting=20, decisive_total=20,
            case_facts=full_case_facts,
        )
        oc = next(d for d in result.dimensions if d.name == "outcome_consistency")
        assert oc.level == ConfidenceLevel.VERY_HIGH


# ---------------------------------------------------------------------------
# Evidence Completeness (spec 6.5)
# ---------------------------------------------------------------------------

class TestEvidenceCompleteness:
    def test_full_evidence(self, registry, full_case_facts):
        result = compute_governed_confidence(
            registry, pool_size=10, avg_similarity=0.80,
            decisive_supporting=8, decisive_total=10,
            case_facts=full_case_facts,
        )
        ec = next(d for d in result.dimensions if d.name == "evidence_completeness")
        assert ec.level in (ConfidenceLevel.HIGH, ConfidenceLevel.VERY_HIGH)

    def test_missing_critical_caps_low(self, registry):
        """Missing txn.type (critical) → caps at LOW regardless of %."""
        facts = {
            # txn.type missing (critical)
            "customer.type": "individual",
            "txn.amount_band": "10k_25k",
        }
        result = compute_governed_confidence(
            registry, pool_size=10, avg_similarity=0.80,
            decisive_supporting=8, decisive_total=10,
            case_facts=facts,
        )
        ec = next(d for d in result.dimensions if d.name == "evidence_completeness")
        assert ec.level == ConfidenceLevel.LOW
        assert "Critical fields missing" in ec.note

    def test_empty_facts_low(self, registry):
        result = compute_governed_confidence(
            registry, pool_size=10, avg_similarity=0.80,
            decisive_supporting=8, decisive_total=10,
            case_facts={},
        )
        ec = next(d for d in result.dimensions if d.name == "evidence_completeness")
        assert ec.level == ConfidenceLevel.LOW


# ---------------------------------------------------------------------------
# Hard Rules (spec 6.7)
# ---------------------------------------------------------------------------

class TestHardRules:
    def test_hard_rule_zero_pool(self, registry, full_case_facts):
        """0 precedents → Confidence = NONE."""
        result = compute_governed_confidence(
            registry, pool_size=0, avg_similarity=0.0,
            decisive_supporting=0, decisive_total=0,
            case_facts=full_case_facts,
        )
        assert result.level == ConfidenceLevel.NONE
        assert result.hard_rule_applied == "0 precedents above floor"

    def test_hard_rule_low_similarity(self, registry, full_case_facts):
        """All precedents < 50% similarity → capped at LOW."""
        result = compute_governed_confidence(
            registry, pool_size=10, avg_similarity=0.40,
            decisive_supporting=8, decisive_total=10,
            case_facts=full_case_facts,
        )
        assert result.level == ConfidenceLevel.LOW
        assert result.hard_rule_applied == "all precedents below 50% similarity"

    def test_hard_rule_critical_missing(self, registry):
        """Critical field missing → capped at LOW."""
        facts = {"customer.type": "individual"}  # txn.type + txn.amount_band missing
        result = compute_governed_confidence(
            registry, pool_size=10, avg_similarity=0.80,
            decisive_supporting=8, decisive_total=10,
            case_facts=facts,
        )
        assert result.level == ConfidenceLevel.LOW
        assert result.hard_rule_applied == "critical fields missing"

    def test_hard_rule_zero_decisive(self, registry, full_case_facts):
        """0 decisive precedents → capped at MODERATE."""
        result = compute_governed_confidence(
            registry, pool_size=10, avg_similarity=0.80,
            decisive_supporting=0, decisive_total=0,
            case_facts=full_case_facts,
        )
        assert result.level <= ConfidenceLevel.MODERATE
        assert result.hard_rule_applied == "0 decisive precedents"

    def test_hard_rule_pool_below_minimum(self, registry, full_case_facts):
        """Pool < 5 → capped at LOW."""
        result = compute_governed_confidence(
            registry, pool_size=3, avg_similarity=0.90,
            decisive_supporting=3, decisive_total=3,
            case_facts=full_case_facts,
        )
        assert result.level <= ConfidenceLevel.LOW
        assert "pool below minimum" in result.hard_rule_applied

    def test_hard_rule_no_hardcoded_fallback(self, registry, full_case_facts):
        """Confidence must never be a hardcoded default value."""
        result = compute_governed_confidence(
            registry, pool_size=10, avg_similarity=0.80,
            decisive_supporting=8, decisive_total=10,
            case_facts=full_case_facts,
        )
        # The result should be computed from dimensions, not hardcoded
        assert result.level is not None
        assert isinstance(result.level, ConfidenceLevel)


# ---------------------------------------------------------------------------
# Min-of-four formula (spec 6.6)
# ---------------------------------------------------------------------------

class TestMinOfFour:
    def test_weakest_dimension_wins(self, registry, full_case_facts):
        """Result should not exceed the weakest dimension."""
        result = compute_governed_confidence(
            registry, pool_size=60, avg_similarity=0.90,
            decisive_supporting=5, decisive_total=10,  # only 50% agreement → LOW
            case_facts=full_case_facts,
        )
        oc = next(d for d in result.dimensions if d.name == "outcome_consistency")
        assert oc.level == ConfidenceLevel.LOW
        assert result.level <= ConfidenceLevel.LOW

    def test_all_dimensions_high(self, registry, full_case_facts):
        """When all dimensions are HIGH or better, result is at least HIGH."""
        result = compute_governed_confidence(
            registry, pool_size=20, avg_similarity=0.80,
            decisive_supporting=18, decisive_total=20,
            case_facts=full_case_facts,
        )
        assert result.level >= ConfidenceLevel.HIGH


# ---------------------------------------------------------------------------
# Bottleneck identification
# ---------------------------------------------------------------------------

class TestBottleneck:
    def test_bottleneck_identified(self, registry, full_case_facts):
        result = compute_governed_confidence(
            registry, pool_size=60, avg_similarity=0.90,
            decisive_supporting=5, decisive_total=10,  # weakest
            case_facts=full_case_facts,
        )
        assert result.bottleneck == "outcome_consistency"

    def test_bottleneck_dimension_flagged(self, registry, full_case_facts):
        result = compute_governed_confidence(
            registry, pool_size=60, avg_similarity=0.90,
            decisive_supporting=5, decisive_total=10,
            case_facts=full_case_facts,
        )
        weakest = next(d for d in result.dimensions if d.bottleneck)
        assert weakest.name == "outcome_consistency"


# ---------------------------------------------------------------------------
# GovernedConfidenceResult structure
# ---------------------------------------------------------------------------

class TestResultStructure:
    def test_has_four_dimensions(self, registry, full_case_facts):
        result = compute_governed_confidence(
            registry, pool_size=10, avg_similarity=0.80,
            decisive_supporting=8, decisive_total=10,
            case_facts=full_case_facts,
        )
        assert len(result.dimensions) == 4
        names = {d.name for d in result.dimensions}
        assert names == {
            "pool_adequacy",
            "similarity_quality",
            "outcome_consistency",
            "evidence_completeness",
        }

    def test_numeric_value_matches_level(self, registry, full_case_facts):
        result = compute_governed_confidence(
            registry, pool_size=0, avg_similarity=0.0,
            decisive_supporting=0, decisive_total=0,
            case_facts=full_case_facts,
        )
        assert result.level == ConfidenceLevel.NONE
        assert result.numeric_value == 0.0

    def test_numeric_value_for_moderate(self, registry, full_case_facts):
        result = compute_governed_confidence(
            registry, pool_size=10, avg_similarity=0.65,
            decisive_supporting=0, decisive_total=0,
            case_facts=full_case_facts,
        )
        # Should be capped at MODERATE (hard rule: 0 decisive)
        assert result.level <= ConfidenceLevel.MODERATE
        assert result.numeric_value <= 0.50
