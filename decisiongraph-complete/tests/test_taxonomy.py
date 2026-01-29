"""
Tests for DecisionGraph 6-Layer Decision Taxonomy Module (v2.1 - Fixed).

The taxonomy implements the constitutional decision architecture that separates:
- Facts from opinions
- Obligations from risk indicators
- Indicators from typologies
- Suspicion from everything else

Key Principle: Escalation requires Layer 6 activation.
Status alone (PEP, foreign, high-risk country) is NEVER sufficient for suspicion.

v2.1 FIXES TESTED:
1. Hard stops ONLY from Layer 1 facts (not signals)
2. Cash signals EXCLUDED from wire transactions
3. FORMING typologies do NOT trigger suspicion
"""

import pytest
from decimal import Decimal

from decisiongraph.taxonomy import (
    DecisionLayer,
    ObligationType,
    IndicatorStrength,
    TypologyCategory,
    TypologyMaturity,
    InstrumentType,
    HardStopType,
    SuspicionBasis,
    VerdictCategory,
    LayerClassification,
    TypologyAssessment,
    HardStopAssessment,
    SuspicionAssessment,
    TaxonomyResult,
    TaxonomyClassifier,
    OBLIGATION_SIGNALS,
    INDICATOR_SIGNALS,
    CASH_ONLY_SIGNALS,
    HARD_STOP_FACT_SIGNALS,
    TYPOLOGY_RULES,
    WIRE_TYPOLOGY_RULES,
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
        """Test that all verdict categories are defined (v2.1: includes TYPOLOGY_FORMING)."""
        assert len(VerdictCategory) == 6  # Added TYPOLOGY_FORMING in v2.1
        assert VerdictCategory.CLEAR.value == "CLEAR"
        assert VerdictCategory.OBLIGATION_ONLY.value == "OBLIGATION_REVIEW"
        assert VerdictCategory.INDICATOR_REVIEW.value == "INDICATOR_REVIEW"
        assert VerdictCategory.TYPOLOGY_FORMING.value == "TYPOLOGY_FORMING"  # v2.1
        assert VerdictCategory.TYPOLOGY_REVIEW.value == "TYPOLOGY_REVIEW"
        assert VerdictCategory.SUSPICION_ESCALATE.value == "SUSPICION_ESCALATE"


class TestTypologyMaturity:
    """Tests for TypologyMaturity enum (v2.1 fix)."""

    def test_maturity_states_defined(self):
        """Test that all maturity states are defined."""
        assert len(TypologyMaturity) == 3
        assert TypologyMaturity.FORMING.value == "forming"
        assert TypologyMaturity.ESTABLISHED.value == "established"
        assert TypologyMaturity.CONFIRMED.value == "confirmed"


class TestInstrumentType:
    """Tests for InstrumentType enum (v2.1 fix)."""

    def test_instrument_types_defined(self):
        """Test that instrument types are defined."""
        assert InstrumentType.CASH.value == "cash"
        assert InstrumentType.WIRE.value == "wire"


# =============================================================================
# TESTS FOR SIGNAL CLASSIFICATION (v2.1)
# =============================================================================

class TestSignalClassification:
    """Tests for signal classification mappings."""

    def test_pep_signals_are_obligations(self):
        """Test that PEP signals are classified as obligations."""
        pep_codes = ["PEP_FOREIGN", "PEP_DOMESTIC", "PEP_HIO", "PEP_FAMILY_ASSOCIATE"]
        for code in pep_codes:
            assert code in OBLIGATION_SIGNALS
            assert OBLIGATION_SIGNALS[code] == ObligationType.EDD_REQUIRED

    def test_sanctions_screening_is_obligation_not_hard_stop(self):
        """Test that GEO_SANCTIONED_COUNTRY triggers obligation, not hard stop."""
        # v2.1: SCREEN_SANCTIONS_HIT is NOT an obligation - it's just a screening signal
        # The disposition determines if it's a hard stop
        assert "GEO_SANCTIONED_COUNTRY" in OBLIGATION_SIGNALS
        assert OBLIGATION_SIGNALS["GEO_SANCTIONED_COUNTRY"] == ObligationType.SANCTIONS_SCREENING
        # SCREEN_SANCTIONS_HIT is intentionally NOT in obligations
        assert "SCREEN_SANCTIONS_HIT" not in OBLIGATION_SIGNALS

    def test_cash_only_signals_defined(self):
        """Test that cash-only signals are defined (v2.1 fix)."""
        assert "TXN_LARGE_CASH" in CASH_ONLY_SIGNALS
        assert "STRUCT_CASH_MULTIPLE" in CASH_ONLY_SIGNALS
        assert "STRUCT_SMURFING" in CASH_ONLY_SIGNALS

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

    def test_detect_wire_instrument(self):
        """Test instrument detection for wire transfers."""
        classifier = TaxonomyClassifier()
        result = classifier.detect_instrument_type([], instrument_hint="swift_wire")
        assert result == InstrumentType.WIRE

    def test_filter_cash_signals_from_wire(self):
        """Test that cash signals are excluded from wire transactions (v2.1 fix)."""
        classifier = TaxonomyClassifier()
        signals = ["TXN_LARGE_CASH", "TXN_RAPID_MOVEMENT", "STRUCT_CASH_MULTIPLE"]

        valid, excluded = classifier.filter_signals_by_instrument(signals, InstrumentType.WIRE)

        assert "TXN_LARGE_CASH" not in valid
        assert "STRUCT_CASH_MULTIPLE" not in valid
        assert "TXN_RAPID_MOVEMENT" in valid
        assert len(excluded) == 2

    def test_assess_structuring_typology(self):
        """Test structuring typology detection with maturity."""
        classifier = TaxonomyClassifier()
        signals = ["TXN_JUST_BELOW_THRESHOLD", "STRUCT_CASH_MULTIPLE", "STRUCT_SMURFING"]

        assessments = classifier.assess_typologies(signals, InstrumentType.CASH)

        # Should detect structuring typology
        structuring = next(
            (a for a in assessments if a.typology == TypologyCategory.STRUCTURING),
            None
        )
        assert structuring is not None
        assert structuring.maturity == TypologyMaturity.CONFIRMED  # 100% match


# =============================================================================
# TESTS FOR HARD STOP ASSESSMENT (v2.1 FIX #1)
# =============================================================================

class TestHardStopAssessment:
    """Tests for Layer 1 hard stop detection (v2.1 fix)."""

    def test_no_hard_stop_without_confirmed_match(self):
        """Test that screening signals alone do NOT create hard stops."""
        classifier = TaxonomyClassifier()

        # Signal says screening occurred, but facts say no match
        result = classifier.assess_hard_stop(
            signal_codes=["SCREEN_SANCTIONS_HIT"],
            facts={"sanctions_result": "NO_MATCH"}
        )

        assert result.has_hard_stop is False
        assert "screening" in result.reasoning.lower()

    def test_hard_stop_with_confirmed_match(self):
        """Test that confirmed sanctions match creates hard stop."""
        classifier = TaxonomyClassifier()

        result = classifier.assess_hard_stop(
            signal_codes=[],
            facts={"sanctions_result": "MATCH"}
        )

        assert result.has_hard_stop is True
        assert result.hard_stop_type == HardStopType.SANCTIONS_CONFIRMED

    def test_hard_stop_with_false_documents(self):
        """Test that false documents create hard stop."""
        classifier = TaxonomyClassifier()

        result = classifier.assess_hard_stop(
            signal_codes=[],
            facts={"document_status": "FORGED"}
        )

        assert result.has_hard_stop is True
        assert result.hard_stop_type == HardStopType.FALSE_DOCUMENTATION

    def test_hard_stop_with_customer_refusal(self):
        """Test that customer refusal creates hard stop."""
        classifier = TaxonomyClassifier()

        result = classifier.assess_hard_stop(
            signal_codes=[],
            facts={"customer_response": "REFUSED"}
        )

        assert result.has_hard_stop is True
        assert result.hard_stop_type == HardStopType.REFUSAL


# =============================================================================
# TESTS FOR SUSPICION ASSESSMENT
# =============================================================================

class TestSuspicionAssessment:
    """Tests for Layer 6 suspicion assessment."""

    def test_hard_stop_activates_suspicion(self):
        """Test that fact-level hard stops activate suspicion."""
        classifier = TaxonomyClassifier()
        hard_stop = HardStopAssessment(
            has_hard_stop=True,
            hard_stop_type=HardStopType.SANCTIONS_CONFIRMED,
            reasoning="Confirmed match",
            fact_evidence=["sanctions_result=MATCH"]
        )

        result = classifier.assess_suspicion(
            typologies=[],
            hard_stop=hard_stop
        )

        assert result.is_activated is True
        assert result.basis == SuspicionBasis.HARD_STOP

    def test_deception_activates_suspicion(self):
        """Test that deception activates suspicion."""
        classifier = TaxonomyClassifier()
        hard_stop = HardStopAssessment(has_hard_stop=False, reasoning="No hard stop")

        result = classifier.assess_suspicion(
            typologies=[],
            hard_stop=hard_stop,
            has_deception=True
        )

        assert result.is_activated is True
        assert result.basis == SuspicionBasis.DECEPTION

    def test_forming_typology_does_not_activate_suspicion(self):
        """Test that FORMING typology does NOT activate suspicion (v2.1 fix)."""
        classifier = TaxonomyClassifier()
        hard_stop = HardStopAssessment(has_hard_stop=False, reasoning="No hard stop")

        typology = TypologyAssessment(
            typology=TypologyCategory.STRUCTURING,
            matching_signals=["TXN_JUST_BELOW_THRESHOLD", "STRUCT_CASH_MULTIPLE"],
            confidence=0.67,
            maturity=TypologyMaturity.FORMING  # FORMING, not ESTABLISHED
        )

        result = classifier.assess_suspicion(
            typologies=[typology],
            hard_stop=hard_stop,
            mitigations_applied=0
        )

        # FORMING should NOT activate suspicion
        assert result.is_activated is False
        assert "forming" in result.reasoning.lower() or "observe" in result.reasoning.lower()

    def test_established_typology_activates_suspicion_when_unmitigated(self):
        """Test that ESTABLISHED typology activates suspicion when unmitigated."""
        classifier = TaxonomyClassifier()
        hard_stop = HardStopAssessment(has_hard_stop=False, reasoning="No hard stop")

        typology = TypologyAssessment(
            typology=TypologyCategory.STRUCTURING,
            matching_signals=["TXN_JUST_BELOW_THRESHOLD", "STRUCT_CASH_MULTIPLE", "STRUCT_SMURFING"],
            confidence=1.0,
            maturity=TypologyMaturity.ESTABLISHED
        )

        result = classifier.assess_suspicion(
            typologies=[typology],
            hard_stop=hard_stop,
            mitigations_applied=0  # No mitigations
        )

        assert result.is_activated is True
        assert result.basis == SuspicionBasis.TYPOLOGY_ESTABLISHED

    def test_established_typology_mitigated_does_not_activate_suspicion(self):
        """Test that mitigated ESTABLISHED typology does NOT activate suspicion."""
        classifier = TaxonomyClassifier()
        hard_stop = HardStopAssessment(has_hard_stop=False, reasoning="No hard stop")

        typology = TypologyAssessment(
            typology=TypologyCategory.STRUCTURING,
            matching_signals=["TXN_JUST_BELOW_THRESHOLD", "STRUCT_CASH_MULTIPLE"],
            confidence=0.75,
            maturity=TypologyMaturity.ESTABLISHED
        )

        result = classifier.assess_suspicion(
            typologies=[typology],
            hard_stop=hard_stop,
            mitigations_applied=3  # Has mitigations
        )

        assert result.is_activated is False  # Mitigated!

    def test_status_alone_never_activates_suspicion(self):
        """KEY TEST: Status alone is NEVER sufficient for suspicion."""
        classifier = TaxonomyClassifier()
        hard_stop = HardStopAssessment(has_hard_stop=False, reasoning="No hard stop")

        # No typologies, no hard stops, no deception - just status
        result = classifier.assess_suspicion(
            typologies=[],
            hard_stop=hard_stop,
            has_deception=False,
            has_intent_evidence=False
        )

        assert result.is_activated is False


# =============================================================================
# TESTS FOR COMPLETE ANALYSIS
# =============================================================================

class TestTaxonomyAnalysis:
    """Tests for complete taxonomy analysis."""

    def test_analyze_pep_wire_case_without_suspicion(self):
        """Test that PEP wire case does NOT trigger suspicion (v2.1 fix)."""
        classifier = TaxonomyClassifier()
        result = classifier.analyze(
            signal_codes=["PEP_FOREIGN", "TXN_ROUND_AMOUNT", "TXN_LARGE_CASH"],
            mitigation_codes=["MF_ESTABLISHED_RELATIONSHIP"],
            facts={"sanctions_result": "NO_MATCH"},
            instrument_hint="wire"
        )

        # Cash signals should be excluded on wire
        assert len(result.excluded_signals) > 0

        # Should have obligations
        assert result.obligation_count >= 1

        # Should NOT activate suspicion (status alone is insufficient)
        assert result.suspicion_activated is False

        # Verdict should be OBLIGATION_REVIEW or less
        assert result.verdict_category in (
            VerdictCategory.OBLIGATION_ONLY,
            VerdictCategory.INDICATOR_REVIEW,
            VerdictCategory.TYPOLOGY_FORMING
        )

    def test_analyze_confirmed_sanctions_case_with_suspicion(self):
        """Test that confirmed sanctions match triggers suspicion."""
        classifier = TaxonomyClassifier()
        result = classifier.analyze(
            signal_codes=["SCREEN_SANCTIONS_HIT"],
            mitigation_codes=[],
            facts={"sanctions_result": "MATCH"}  # CONFIRMED match
        )

        # Should activate suspicion (hard stop)
        assert result.suspicion_activated is True
        assert result.hard_stop.has_hard_stop is True

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

    def test_established_typology_without_suspicion_is_typology_review(self):
        """Test that ESTABLISHED typology WITHOUT mitigations is TYPOLOGY_REVIEW."""
        classifier = TaxonomyClassifier()
        result = TaxonomyResult()
        result.typology_established = True
        result.suspicion_activated = False
        result.mitigations = []  # No mitigations

        verdict = classifier.determine_verdict(result)
        assert verdict == VerdictCategory.TYPOLOGY_REVIEW

    def test_established_typology_with_mitigations_downgrades_to_obligation(self):
        """v2.1.1 FIX: ESTABLISHED typology WITH sufficient mitigations downgrades to OBLIGATION_ONLY."""
        classifier = TaxonomyClassifier()
        result = TaxonomyResult()
        result.typology_established = True
        result.suspicion_activated = False
        result.obligation_count = 1  # Has obligations
        result.mitigations = ["MF_1", "MF_2", "MF_3"]  # 3+ mitigations

        verdict = classifier.determine_verdict(result)
        # With mitigations, should downgrade to OBLIGATION_ONLY
        assert verdict == VerdictCategory.OBLIGATION_ONLY

    def test_forming_typology_is_typology_forming_not_escalation(self):
        """Test that FORMING typology results in TYPOLOGY_FORMING (observe only)."""
        classifier = TaxonomyClassifier()
        result = TaxonomyResult()
        result.typology_forming = True
        result.typology_established = False
        result.suspicion_activated = False

        verdict = classifier.determine_verdict(result)
        assert verdict == VerdictCategory.TYPOLOGY_FORMING

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
        assert TAXONOMY_TO_VERDICT[VerdictCategory.OBLIGATION_ONLY] == "PASS_WITH_EDD"
        assert TAXONOMY_TO_VERDICT[VerdictCategory.TYPOLOGY_FORMING] == "OBSERVE_ENHANCED"
        assert TAXONOMY_TO_VERDICT[VerdictCategory.SUSPICION_ESCALATE] == "STR_CONSIDERATION"

    def test_taxonomy_to_tier_mapping(self):
        """Test that all verdict categories have tier mappings."""
        for category in VerdictCategory:
            assert category in TAXONOMY_TO_TIER

        assert TAXONOMY_TO_TIER[VerdictCategory.CLEAR] == 0
        assert TAXONOMY_TO_TIER[VerdictCategory.OBLIGATION_ONLY] == 0  # Pass with EDD
        assert TAXONOMY_TO_TIER[VerdictCategory.SUSPICION_ESCALATE] == 3

    def test_taxonomy_auto_archive_mapping(self):
        """Test auto-archive permissions by verdict."""
        assert TAXONOMY_AUTO_ARCHIVE[VerdictCategory.CLEAR] is True
        assert TAXONOMY_AUTO_ARCHIVE[VerdictCategory.OBLIGATION_ONLY] is True  # Can archive after EDD
        assert TAXONOMY_AUTO_ARCHIVE[VerdictCategory.SUSPICION_ESCALATE] is False


# =============================================================================
# TESTS FOR CONVENIENCE FUNCTION
# =============================================================================

class TestGetTaxonomyVerdict:
    """Tests for get_taxonomy_verdict convenience function."""

    def test_get_verdict_for_pep_case(self):
        """Test getting verdict for PEP case (should pass with EDD)."""
        verdict_code, tier, auto_archive, result = get_taxonomy_verdict(
            signal_codes=["PEP_FOREIGN"],
            mitigation_codes=["MF_ESTABLISHED_RELATIONSHIP"],
            facts={"sanctions_result": "NO_MATCH"}
        )

        assert verdict_code == "PASS_WITH_EDD"
        assert tier == 0  # Pass tier
        assert auto_archive is True  # Can archive after EDD recorded
        assert result.verdict_category == VerdictCategory.OBLIGATION_ONLY

    def test_get_verdict_for_confirmed_hard_stop(self):
        """Test getting verdict for confirmed hard stop case."""
        verdict_code, tier, auto_archive, result = get_taxonomy_verdict(
            signal_codes=["SCREEN_SANCTIONS_HIT"],
            facts={"sanctions_result": "MATCH"}  # Confirmed match
        )

        assert verdict_code == "STR_CONSIDERATION"
        assert tier == 3
        assert auto_archive is False
        assert result.suspicion_activated is True


# =============================================================================
# KEY PRINCIPLE TESTS (v2.1)
# =============================================================================

class TestKeyPrinciple:
    """Tests that verify the key principles:
    1. Escalation requires Layer 6 activation
    2. Status alone is NEVER sufficient
    3. Hard stops ONLY from Layer 1 facts
    4. Cash signals don't apply to wires
    5. FORMING typologies don't trigger suspicion
    """

    def test_foreign_pep_alone_is_not_suspicion(self):
        """Foreign PEP status alone does NOT escalate to STR consideration."""
        _, _, _, result = get_taxonomy_verdict(
            signal_codes=["PEP_FOREIGN"],
            facts={"sanctions_result": "NO_MATCH"}
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

    def test_sanctions_screening_signal_without_match_is_not_hard_stop(self):
        """SCREEN_SANCTIONS_HIT without confirmed match is NOT a hard stop (v2.1 fix)."""
        _, _, _, result = get_taxonomy_verdict(
            signal_codes=["SCREEN_SANCTIONS_HIT"],
            facts={"sanctions_result": "NO_MATCH"}  # Screening occurred but no match
        )
        assert result.hard_stop.has_hard_stop is False
        assert result.suspicion_activated is False

    def test_wire_transaction_excludes_cash_signals(self):
        """Wire transactions exclude cash signals (v2.1 fix)."""
        _, _, _, result = get_taxonomy_verdict(
            signal_codes=["TXN_LARGE_CASH", "STRUCT_CASH_MULTIPLE", "TXN_RAPID_MOVEMENT"],
            instrument_hint="wire"
        )
        # Cash signals should be excluded
        excluded_codes = [e.signal_code for e in result.excluded_signals]
        assert "TXN_LARGE_CASH" in excluded_codes
        assert "STRUCT_CASH_MULTIPLE" in excluded_codes

    def test_pep_with_forming_pattern_is_not_suspicion(self):
        """PEP with FORMING pattern (not established) is NOT suspicion (v2.1 fix)."""
        _, _, _, result = get_taxonomy_verdict(
            signal_codes=[
                "PEP_FOREIGN",
                "TXN_UNUSUAL_PATTERN",  # 1 of 3 for PEP_CORRUPTION
            ],
            mitigation_codes=["MF_ESTABLISHED_RELATIONSHIP"],
            facts={"sanctions_result": "NO_MATCH"}
        )
        # Should NOT escalate - no established typology, no hard stop
        assert result.verdict_category != VerdictCategory.SUSPICION_ESCALATE
        assert result.suspicion_activated is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
