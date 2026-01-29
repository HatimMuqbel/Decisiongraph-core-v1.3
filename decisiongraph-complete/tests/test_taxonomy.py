"""
Tests for DecisionGraph 6-Layer Decision Taxonomy Module.

The taxonomy implements the constitutional decision architecture that separates:
- Facts from opinions
- Obligations from risk indicators
- Indicators from typologies
- Suspicion from everything else

Key Principle: Escalation requires Layer 6 activation.
Status alone (PEP, foreign, high-risk country) is NEVER sufficient for suspicion.
"""

import pytest
from decimal import Decimal

from decisiongraph.taxonomy import (
    DecisionLayer,
    ObligationType,
    IndicatorStrength,
    TypologyCategory,
    SuspicionBasis,
    VerdictCategory,
    LayerClassification,
    TypologyAssessment,
    SuspicionAssessment,
    TaxonomyResult,
    TaxonomyClassifier,
    OBLIGATION_SIGNALS,
    INDICATOR_SIGNALS,
    TYPOLOGY_RULES,
    TAXONOMY_TO_VERDICT,
    TAXONOMY_TO_TIER,
    TAXONOMY_AUTO_ARCHIVE,
    get_taxonomy_verdict,
)


# =============================================================================
# TESTS FOR ENUMS
# =============================================================================

class TestDecisionLayer:
    """Tests for DecisionLayer enum."""

    def test_all_layers_defined(self):
        """Test that all 6 layers are defined."""
        assert len(DecisionLayer) == 6
        assert DecisionLayer.FACTS.value == "L1_FACTS"
        assert DecisionLayer.OBLIGATIONS.value == "L2_OBLIGATIONS"
        assert DecisionLayer.INDICATORS.value == "L3_INDICATORS"
        assert DecisionLayer.TYPOLOGIES.value == "L4_TYPOLOGIES"
        assert DecisionLayer.MITIGATIONS.value == "L5_MITIGATIONS"
        assert DecisionLayer.SUSPICION.value == "L6_SUSPICION"


class TestVerdictCategory:
    """Tests for VerdictCategory enum."""

    def test_verdict_categories_defined(self):
        """Test that all verdict categories are defined."""
        assert len(VerdictCategory) == 5
        assert VerdictCategory.CLEAR.value == "CLEAR"
        assert VerdictCategory.OBLIGATION_ONLY.value == "OBLIGATION_REVIEW"
        assert VerdictCategory.INDICATOR_REVIEW.value == "INDICATOR_REVIEW"
        assert VerdictCategory.TYPOLOGY_REVIEW.value == "TYPOLOGY_REVIEW"
        assert VerdictCategory.SUSPICION_ESCALATE.value == "SUSPICION_ESCALATE"


# =============================================================================
# TESTS FOR SIGNAL CLASSIFICATION
# =============================================================================

class TestSignalClassification:
    """Tests for signal classification mappings."""

    def test_pep_signals_are_obligations(self):
        """Test that PEP signals are classified as obligations."""
        pep_codes = ["PEP_FOREIGN", "PEP_DOMESTIC", "PEP_HIO", "PEP_FAMILY_ASSOCIATE"]
        for code in pep_codes:
            assert code in OBLIGATION_SIGNALS
            assert OBLIGATION_SIGNALS[code] == ObligationType.EDD_REQUIRED

    def test_sanctions_signals_are_obligations(self):
        """Test that sanctions signals are classified as obligations."""
        assert "SCREEN_SANCTIONS_HIT" in OBLIGATION_SIGNALS
        assert "GEO_SANCTIONED_COUNTRY" in OBLIGATION_SIGNALS

    def test_transaction_indicators(self):
        """Test transaction indicator classifications."""
        txn_codes = [
            "TXN_JUST_BELOW_THRESHOLD",
            "TXN_RAPID_MOVEMENT",
            "TXN_ROUND_AMOUNT",
            "TXN_CRYPTO",
            "TXN_UNUSUAL_PATTERN",
        ]
        for code in txn_codes:
            assert code in INDICATOR_SIGNALS

    def test_indicator_strengths(self):
        """Test indicator strength assignments."""
        assert INDICATOR_SIGNALS["TXN_JUST_BELOW_THRESHOLD"] == IndicatorStrength.MODERATE
        assert INDICATOR_SIGNALS["TXN_ROUND_AMOUNT"] == IndicatorStrength.WEAK
        assert INDICATOR_SIGNALS["STRUCT_SMURFING"] == IndicatorStrength.STRONG


# =============================================================================
# TESTS FOR TAXONOMY CLASSIFIER
# =============================================================================

class TestTaxonomyClassifier:
    """Tests for TaxonomyClassifier."""

    def test_classify_pep_signal_as_obligation(self):
        """Test that PEP signals are classified as Layer 2 obligations."""
        classifier = TaxonomyClassifier()
        result = classifier.classify_signal("PEP_FOREIGN")

        assert result.layer == DecisionLayer.OBLIGATIONS
        assert result.obligation_type == ObligationType.EDD_REQUIRED
        assert "obligation" in result.description.lower()

    def test_classify_transaction_signal_as_indicator(self):
        """Test that transaction signals are classified as Layer 3 indicators."""
        classifier = TaxonomyClassifier()
        result = classifier.classify_signal("TXN_JUST_BELOW_THRESHOLD")

        assert result.layer == DecisionLayer.INDICATORS
        assert result.indicator_strength == IndicatorStrength.MODERATE

    def test_classify_unknown_signal_as_weak_indicator(self):
        """Test that unknown signals default to weak indicators."""
        classifier = TaxonomyClassifier()
        result = classifier.classify_signal("UNKNOWN_SIGNAL")

        assert result.layer == DecisionLayer.INDICATORS
        assert result.indicator_strength == IndicatorStrength.WEAK

    def test_assess_structuring_typology(self):
        """Test structuring typology detection."""
        classifier = TaxonomyClassifier()
        signals = ["TXN_JUST_BELOW_THRESHOLD", "STRUCT_CASH_MULTIPLE", "STRUCT_SMURFING"]

        assessments = classifier.assess_typologies(signals)

        # Should detect structuring typology forming
        structuring = next(
            (a for a in assessments if a.typology == TypologyCategory.STRUCTURING),
            None
        )
        assert structuring is not None
        assert structuring.is_forming is True
        assert structuring.confidence == 1.0  # 3/3 signals match

    def test_assess_partial_typology(self):
        """Test partial typology detection (not forming)."""
        classifier = TaxonomyClassifier()
        signals = ["TXN_JUST_BELOW_THRESHOLD"]  # Only 1 of 3 required

        assessments = classifier.assess_typologies(signals)

        structuring = next(
            (a for a in assessments if a.typology == TypologyCategory.STRUCTURING),
            None
        )
        assert structuring is not None
        assert structuring.is_forming is False  # Not enough signals


# =============================================================================
# TESTS FOR SUSPICION ASSESSMENT
# =============================================================================

class TestSuspicionAssessment:
    """Tests for Layer 6 suspicion assessment."""

    def test_hard_stop_activates_suspicion(self):
        """Test that hard stops always activate suspicion."""
        classifier = TaxonomyClassifier()
        result = classifier.assess_suspicion(
            typologies=[],
            has_hard_stop=True
        )

        assert result.is_activated is True
        assert result.basis == SuspicionBasis.HARD_STOP

    def test_deception_activates_suspicion(self):
        """Test that deception activates suspicion."""
        classifier = TaxonomyClassifier()
        result = classifier.assess_suspicion(
            typologies=[],
            has_deception=True
        )

        assert result.is_activated is True
        assert result.basis == SuspicionBasis.DECEPTION

    def test_intent_activates_suspicion(self):
        """Test that intent evidence activates suspicion."""
        classifier = TaxonomyClassifier()
        result = classifier.assess_suspicion(
            typologies=[],
            has_intent_evidence=True
        )

        assert result.is_activated is True
        assert result.basis == SuspicionBasis.INTENT

    def test_unmitigated_typology_activates_suspicion(self):
        """Test that forming typology without mitigation activates suspicion."""
        classifier = TaxonomyClassifier()
        typology = TypologyAssessment(
            typology=TypologyCategory.STRUCTURING,
            matching_signals=["TXN_JUST_BELOW_THRESHOLD", "STRUCT_CASH_MULTIPLE"],
            confidence=0.67,
            is_forming=True
        )

        result = classifier.assess_suspicion(
            typologies=[typology],
            mitigations_applied=0
        )

        assert result.is_activated is True
        assert result.basis == SuspicionBasis.TYPOLOGY_MATCH

    def test_mitigated_typology_does_not_activate_suspicion(self):
        """Test that forming typology WITH mitigation does NOT activate suspicion."""
        classifier = TaxonomyClassifier()
        typology = TypologyAssessment(
            typology=TypologyCategory.STRUCTURING,
            matching_signals=["TXN_JUST_BELOW_THRESHOLD", "STRUCT_CASH_MULTIPLE"],
            confidence=0.67,
            is_forming=True
        )

        result = classifier.assess_suspicion(
            typologies=[typology],
            mitigations_applied=2  # Has mitigations
        )

        assert result.is_activated is False  # Mitigated!

    def test_status_alone_never_activates_suspicion(self):
        """KEY TEST: Status alone is NEVER sufficient for suspicion."""
        classifier = TaxonomyClassifier()

        # PEP status alone - no suspicion
        result = classifier.assess_suspicion(
            typologies=[],
            has_hard_stop=False,
            has_deception=False,
            has_intent_evidence=False
        )

        assert result.is_activated is False
        assert "status alone" in result.reasoning.lower() or "insufficient" in result.reasoning.lower()


# =============================================================================
# TESTS FOR COMPLETE ANALYSIS
# =============================================================================

class TestTaxonomyAnalysis:
    """Tests for complete taxonomy analysis."""

    def test_analyze_pep_case_without_suspicion(self):
        """Test that PEP case alone does NOT trigger suspicion escalation."""
        classifier = TaxonomyClassifier()
        result = classifier.analyze(
            signal_codes=["PEP_FOREIGN", "TXN_ROUND_AMOUNT"],
            mitigation_codes=["MF_ESTABLISHED_RELATIONSHIP"]
        )

        # Should have obligations
        assert result.obligation_count == 1
        assert result.obligations[0].signal_code == "PEP_FOREIGN"

        # Should have weak indicator
        assert result.indicator_count == 1

        # Should NOT activate suspicion (status alone is insufficient)
        assert result.suspicion_activated is False

        # Verdict should be OBLIGATION_REVIEW, not escalation
        assert result.verdict_category == VerdictCategory.OBLIGATION_ONLY

    def test_analyze_structuring_case_with_suspicion(self):
        """Test that structuring pattern triggers suspicion escalation."""
        classifier = TaxonomyClassifier()
        result = classifier.analyze(
            signal_codes=[
                "TXN_JUST_BELOW_THRESHOLD",
                "STRUCT_CASH_MULTIPLE",
                "STRUCT_SMURFING"
            ],
            mitigation_codes=[]  # No mitigations!
        )

        # Should detect typology
        assert result.typology_match is True

        # Should activate suspicion (unmitigated typology)
        assert result.suspicion_activated is True
        assert result.suspicion.basis == SuspicionBasis.TYPOLOGY_MATCH

        # Verdict should be SUSPICION_ESCALATE
        assert result.verdict_category == VerdictCategory.SUSPICION_ESCALATE

    def test_analyze_clear_case(self):
        """Test clear case with no signals."""
        classifier = TaxonomyClassifier()
        result = classifier.analyze(
            signal_codes=[],
            mitigation_codes=[]
        )

        assert result.obligation_count == 0
        assert result.indicator_count == 0
        assert result.suspicion_activated is False
        assert result.verdict_category == VerdictCategory.CLEAR

    def test_analyze_indicator_review_case(self):
        """Test case with multiple indicators but no typology."""
        classifier = TaxonomyClassifier()
        result = classifier.analyze(
            signal_codes=[
                "TXN_ROUND_AMOUNT",
                "GEO_HIGH_RISK_COUNTRY",
                "TXN_RAPID_MOVEMENT",
                "GEO_TAX_HAVEN"
            ],
            mitigation_codes=[]
        )

        # Multiple weak indicators
        assert result.indicator_count >= 3

        # No suspicion (no typology, no hard stops)
        assert result.suspicion_activated is False

        # Should be INDICATOR_REVIEW due to indicator count
        assert result.verdict_category == VerdictCategory.INDICATOR_REVIEW


# =============================================================================
# TESTS FOR VERDICT DETERMINATION
# =============================================================================

class TestVerdictDetermination:
    """Tests for verdict determination based on layer activation."""

    def test_suspicion_activated_overrides_all(self):
        """Test that Layer 6 activation always results in SUSPICION_ESCALATE."""
        classifier = TaxonomyClassifier()
        result = TaxonomyResult()
        result.suspicion_activated = True

        verdict = classifier.determine_verdict(result)
        assert verdict == VerdictCategory.SUSPICION_ESCALATE

    def test_typology_match_without_suspicion_is_typology_review(self):
        """Test that typology match (mitigated) is TYPOLOGY_REVIEW."""
        classifier = TaxonomyClassifier()
        result = TaxonomyResult()
        result.typology_match = True
        result.suspicion_activated = False

        verdict = classifier.determine_verdict(result)
        assert verdict == VerdictCategory.TYPOLOGY_REVIEW

    def test_obligations_only_is_obligation_review(self):
        """Test that obligations alone is OBLIGATION_REVIEW."""
        classifier = TaxonomyClassifier()
        result = TaxonomyResult()
        result.obligation_count = 1
        result.indicator_count = 0
        result.suspicion_activated = False

        verdict = classifier.determine_verdict(result)
        assert verdict == VerdictCategory.OBLIGATION_ONLY


# =============================================================================
# TESTS FOR VERDICT MAPPINGS
# =============================================================================

class TestVerdictMappings:
    """Tests for verdict mapping to canonical codes."""

    def test_taxonomy_to_verdict_mapping(self):
        """Test that all verdict categories have canonical mappings."""
        for category in VerdictCategory:
            assert category in TAXONOMY_TO_VERDICT

        assert TAXONOMY_TO_VERDICT[VerdictCategory.CLEAR] == "CLEAR_AND_CLOSE"
        assert TAXONOMY_TO_VERDICT[VerdictCategory.OBLIGATION_ONLY] == "OBLIGATION_REVIEW"
        assert TAXONOMY_TO_VERDICT[VerdictCategory.SUSPICION_ESCALATE] == "STR_CONSIDERATION"

    def test_taxonomy_to_tier_mapping(self):
        """Test that all verdict categories have tier mappings."""
        for category in VerdictCategory:
            assert category in TAXONOMY_TO_TIER

        assert TAXONOMY_TO_TIER[VerdictCategory.CLEAR] == 0
        assert TAXONOMY_TO_TIER[VerdictCategory.SUSPICION_ESCALATE] == 3

    def test_taxonomy_auto_archive_mapping(self):
        """Test auto-archive permissions by verdict."""
        assert TAXONOMY_AUTO_ARCHIVE[VerdictCategory.CLEAR] is True
        assert TAXONOMY_AUTO_ARCHIVE[VerdictCategory.OBLIGATION_ONLY] is False
        assert TAXONOMY_AUTO_ARCHIVE[VerdictCategory.SUSPICION_ESCALATE] is False


# =============================================================================
# TESTS FOR CONVENIENCE FUNCTION
# =============================================================================

class TestGetTaxonomyVerdict:
    """Tests for get_taxonomy_verdict convenience function."""

    def test_get_verdict_for_pep_case(self):
        """Test getting verdict for PEP case."""
        verdict_code, tier, auto_archive, result = get_taxonomy_verdict(
            signal_codes=["PEP_FOREIGN"],
            mitigation_codes=["MF_ESTABLISHED_RELATIONSHIP"]
        )

        assert verdict_code == "OBLIGATION_REVIEW"
        assert tier == 1
        assert auto_archive is False
        assert result.verdict_category == VerdictCategory.OBLIGATION_ONLY

    def test_get_verdict_for_hard_stop(self):
        """Test getting verdict for hard stop case."""
        verdict_code, tier, auto_archive, result = get_taxonomy_verdict(
            signal_codes=["SCREEN_SANCTIONS_HIT"],
            has_hard_stop=True
        )

        assert verdict_code == "STR_CONSIDERATION"
        assert tier == 3
        assert auto_archive is False
        assert result.suspicion_activated is True


# =============================================================================
# KEY PRINCIPLE TESTS
# =============================================================================

class TestKeyPrinciple:
    """Tests that verify the key principle:
    'Escalation requires Layer 6 activation. Status alone is NEVER sufficient.'
    """

    def test_foreign_pep_alone_is_not_suspicion(self):
        """Foreign PEP status alone does NOT escalate to STR consideration."""
        _, _, _, result = get_taxonomy_verdict(
            signal_codes=["PEP_FOREIGN"]
        )
        assert result.verdict_category != VerdictCategory.SUSPICION_ESCALATE
        assert result.suspicion_activated is False

    def test_high_risk_country_alone_is_not_suspicion(self):
        """High-risk country alone does NOT escalate to STR consideration."""
        _, _, _, result = get_taxonomy_verdict(
            signal_codes=["GEO_HIGH_RISK_COUNTRY"]
        )
        assert result.verdict_category != VerdictCategory.SUSPICION_ESCALATE
        assert result.suspicion_activated is False

    def test_combination_without_pattern_is_not_suspicion(self):
        """Combination of status signals without pattern is NOT suspicion."""
        _, _, _, result = get_taxonomy_verdict(
            signal_codes=[
                "PEP_FOREIGN",
                "GEO_HIGH_RISK_COUNTRY",
                "TXN_ROUND_AMOUNT"
            ],
            mitigation_codes=["MF_ESTABLISHED_RELATIONSHIP"]
        )
        assert result.verdict_category != VerdictCategory.SUSPICION_ESCALATE
        assert result.suspicion_activated is False

    def test_pep_with_structuring_pattern_is_suspicion(self):
        """PEP with structuring pattern (unmitigated) IS suspicion."""
        _, _, _, result = get_taxonomy_verdict(
            signal_codes=[
                "PEP_FOREIGN",
                "TXN_JUST_BELOW_THRESHOLD",
                "STRUCT_CASH_MULTIPLE"
            ],
            mitigation_codes=[]  # No mitigations
        )
        assert result.verdict_category == VerdictCategory.SUSPICION_ESCALATE
        assert result.suspicion_activated is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
