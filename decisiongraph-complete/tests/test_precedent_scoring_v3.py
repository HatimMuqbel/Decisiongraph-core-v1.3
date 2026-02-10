"""Tests for v3 Precedent Scoring — Layer 2 field-by-field scoring."""

import pytest

from decisiongraph.banking_domain import create_banking_domain_registry
from decisiongraph.domain_registry import DomainRegistry
from decisiongraph.precedent_scorer_v3 import (
    SimilarityResult,
    anchor_facts_to_dict,
    classify_match_v3,
    detect_primary_typology,
    score_similarity,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def registry() -> DomainRegistry:
    return create_banking_domain_registry()


@pytest.fixture
def base_case_facts() -> dict:
    """A typical retail cash case."""
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
    }


@pytest.fixture
def matching_precedent_facts() -> dict:
    """Precedent that closely matches base_case_facts."""
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
    }


@pytest.fixture
def divergent_precedent_facts() -> dict:
    """Precedent that diverges significantly from base_case_facts."""
    return {
        "customer.type": "corporation",
        "txn.type": "wire_domestic",
        "txn.amount_band": "100k_500k",
        "txn.cross_border": True,
        "txn.destination_country_risk": "high",
        "txn.frequency_band": "high",
        "txn.source_of_funds_clear": False,
        "txn.stated_purpose": "trade",
        "customer.pep": True,
        "customer.relationship_length": "new",
        "screening.sanctions_match": True,
        "screening.adverse_media": True,
        "flag.structuring": False,
        "flag.rapid_movement": True,
        "flag.round_amounts": False,
    }


# ---------------------------------------------------------------------------
# score_similarity — basic tests
# ---------------------------------------------------------------------------

class TestScoreSimilarity:
    def test_perfect_match(self, registry, base_case_facts, matching_precedent_facts):
        result = score_similarity(
            registry, base_case_facts, matching_precedent_facts,
        )
        assert isinstance(result, SimilarityResult)
        assert result.score == 1.0
        assert result.non_transferable is False
        assert len(result.evaluable_fields) > 0
        # Fields missing from BOTH sides are skipped (not penalized)
        # so missing_fields may be non-zero for fields not in fixtures
        assert all(
            f.field_scores.get(f_name, 1.0) == 1.0
            for f_name in result.evaluable_fields
            for f in [result]
        )

    def test_divergent_low_score(self, registry, base_case_facts, divergent_precedent_facts):
        result = score_similarity(
            registry, base_case_facts, divergent_precedent_facts,
        )
        assert result.score < 0.5

    def test_returns_field_scores(self, registry, base_case_facts, matching_precedent_facts):
        result = score_similarity(
            registry, base_case_facts, matching_precedent_facts,
        )
        # Should have field-level breakdown
        assert len(result.field_scores) > 0
        for field_name, score in result.field_scores.items():
            assert 0.0 <= score <= 1.0

    def test_empty_case_facts(self, registry, matching_precedent_facts):
        result = score_similarity(registry, {}, matching_precedent_facts)
        assert result.score == 0.0
        assert len(result.missing_fields) > 0

    def test_empty_precedent_facts(self, registry, base_case_facts):
        result = score_similarity(registry, base_case_facts, {})
        assert result.score == 0.0


# ---------------------------------------------------------------------------
# score_similarity — driver-aware weighting
# ---------------------------------------------------------------------------

class TestDriverAwareWeighting:
    def test_driver_match_boosts_score(self, registry, base_case_facts):
        """When drivers match, they should be in matched_drivers."""
        prec_facts = dict(base_case_facts)
        drivers = ["flag.structuring", "txn.amount_band"]
        result = score_similarity(
            registry, base_case_facts, prec_facts,
            precedent_drivers=drivers,
        )
        assert result.score == 1.0  # all fields match, drivers just get 2x
        assert "flag.structuring" in result.matched_drivers
        assert "txn.amount_band" in result.matched_drivers
        assert len(result.mismatched_drivers) == 0

    def test_driver_mismatch_non_transferable(self, registry, base_case_facts):
        """Driver field with 0.0 match → non-transferable."""
        prec_facts = dict(base_case_facts)
        prec_facts["flag.structuring"] = not base_case_facts["flag.structuring"]
        drivers = ["flag.structuring"]
        result = score_similarity(
            registry, base_case_facts, prec_facts,
            precedent_drivers=drivers,
        )
        assert result.non_transferable is True
        assert "flag.structuring" in result.mismatched_drivers
        assert len(result.non_transferable_reasons) > 0

    def test_driver_absent_from_case_non_transferable(self, registry):
        """Driver field missing from case → non-transferable."""
        case = {"txn.type": "cash"}
        prec = {"txn.type": "cash", "flag.structuring": True}
        drivers = ["flag.structuring"]
        result = score_similarity(
            registry, case, prec,
            precedent_drivers=drivers,
        )
        assert result.non_transferable is True
        assert any("missing" in r.lower() for r in result.non_transferable_reasons)

    def test_no_drivers_all_1x(self, registry, base_case_facts, matching_precedent_facts):
        """No drivers → all fields at 1x weight."""
        result_no_drivers = score_similarity(
            registry, base_case_facts, matching_precedent_facts,
            precedent_drivers=None,
        )
        result_empty_drivers = score_similarity(
            registry, base_case_facts, matching_precedent_facts,
            precedent_drivers=[],
        )
        # Both should produce identical scores (1x for all)
        assert result_no_drivers.score == result_empty_drivers.score


# ---------------------------------------------------------------------------
# classify_match_v3 — INV-011 tests
# ---------------------------------------------------------------------------

class TestClassifyMatchV3:
    def test_same_disposition_supporting(self):
        assert classify_match_v3("ALLOW", "ALLOW", "DISCRETIONARY", "DISCRETIONARY") == "supporting"

    def test_allow_vs_block_contrary(self):
        assert classify_match_v3("ALLOW", "BLOCK", "DISCRETIONARY", "DISCRETIONARY") == "contrary"

    def test_block_vs_allow_contrary(self):
        assert classify_match_v3("BLOCK", "ALLOW", "DISCRETIONARY", "DISCRETIONARY") == "contrary"

    def test_unknown_always_neutral(self):
        assert classify_match_v3("UNKNOWN", "ALLOW", "DISCRETIONARY", "DISCRETIONARY") == "neutral"
        assert classify_match_v3("ALLOW", "UNKNOWN", "DISCRETIONARY", "DISCRETIONARY") == "neutral"

    def test_edd_vs_terminal_neutral(self):
        assert classify_match_v3("EDD", "ALLOW", "DISCRETIONARY", "DISCRETIONARY") == "neutral"
        assert classify_match_v3("ALLOW", "EDD", "DISCRETIONARY", "DISCRETIONARY") == "neutral"

    def test_edd_vs_edd_supporting(self):
        assert classify_match_v3("EDD", "EDD", "DISCRETIONARY", "DISCRETIONARY") == "supporting"

    def test_cross_basis_neutral_inv008(self):
        assert classify_match_v3("ALLOW", "ALLOW", "MANDATORY", "DISCRETIONARY") == "neutral"

    def test_inv011_non_transferable_not_supporting(self):
        """INV-011: non-transferable precedent cannot be supporting."""
        result = classify_match_v3(
            "ALLOW", "ALLOW", "DISCRETIONARY", "DISCRETIONARY",
            non_transferable=True,
        )
        assert result == "neutral"

    def test_inv011_non_transferable_contrary_unchanged(self):
        """INV-011 only affects supporting → contrary is unaffected."""
        result = classify_match_v3(
            "ALLOW", "BLOCK", "DISCRETIONARY", "DISCRETIONARY",
            non_transferable=True,
        )
        assert result == "contrary"

    def test_inv011_edd_edd_non_transferable(self):
        """EDD==EDD with non-transferable → neutral."""
        result = classify_match_v3(
            "EDD", "EDD", "DISCRETIONARY", "DISCRETIONARY",
            non_transferable=True,
        )
        assert result == "neutral"


# ---------------------------------------------------------------------------
# detect_primary_typology
# ---------------------------------------------------------------------------

class TestDetectPrimaryTypology:
    def test_sanctions_from_codes(self):
        assert detect_primary_typology(["RC-SCR-001"]) == "sanctions"
        assert detect_primary_typology(["SANCTION-LIST"]) == "sanctions"

    def test_sanctions_from_facts(self):
        assert detect_primary_typology([], {"screening.sanctions_match": True}) == "sanctions"
        assert detect_primary_typology([], {"screening.sanctions_match": "true"}) == "sanctions"

    def test_structuring_from_codes(self):
        assert detect_primary_typology(["RC-MON-STRUCT-001"]) == "structuring"

    def test_structuring_from_facts(self):
        assert detect_primary_typology([], {"flag.structuring": True}) == "structuring"

    def test_adverse_media_from_codes(self):
        assert detect_primary_typology(["ADVERSE-MEDIA-MATCH"]) == "adverse_media"

    def test_adverse_media_from_facts(self):
        assert detect_primary_typology([], {"screening.adverse_media": True}) == "adverse_media"

    def test_no_typology(self):
        assert detect_primary_typology(["RC-MON-001"]) is None
        assert detect_primary_typology([]) is None

    def test_sanctions_takes_priority(self):
        """Sanctions > structuring > adverse_media."""
        result = detect_primary_typology(["SANCTION-001", "STRUCT-001", "ADVERSE-001"])
        assert result == "sanctions"


# ---------------------------------------------------------------------------
# anchor_facts_to_dict
# ---------------------------------------------------------------------------

class TestAnchorFactsToDict:
    def test_dict_input(self):
        facts = [
            {"field_id": "txn.type", "value": "cash"},
            {"field_id": "customer.type", "value": "individual"},
        ]
        result = anchor_facts_to_dict(facts)
        assert result == {"txn.type": "cash", "customer.type": "individual"}

    def test_object_input(self):
        class FakeAnchorFact:
            def __init__(self, field_id, value):
                self.field_id = field_id
                self.value = value

        facts = [FakeAnchorFact("txn.type", "wire"), FakeAnchorFact("customer.pep", True)]
        result = anchor_facts_to_dict(facts)
        assert result == {"txn.type": "wire", "customer.pep": True}

    def test_empty_list(self):
        assert anchor_facts_to_dict([]) == {}

    def test_skips_empty_field_id(self):
        facts = [{"field_id": "", "value": "x"}, {"field_id": "a", "value": "b"}]
        result = anchor_facts_to_dict(facts)
        assert result == {"a": "b"}


# ---------------------------------------------------------------------------
# SimilarityResult — structure tests
# ---------------------------------------------------------------------------

class TestSimilarityResult:
    def test_defaults(self):
        sr = SimilarityResult(score=0.75, raw_score=3.0, total_weight=4.0)
        assert sr.non_transferable is False
        assert sr.non_transferable_reasons == []
        assert sr.matched_drivers == []
        assert sr.mismatched_drivers == []
        assert sr.matched_context == []
        assert sr.field_scores == {}
        assert sr.evaluable_fields == []
        assert sr.missing_fields == []
