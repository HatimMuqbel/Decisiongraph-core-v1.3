"""
Tests for DecisionGraph Rules Module (v2.0)

Tests cover:
- Fact pattern matching
- Condition evaluation
- Signal rule evaluation
- Mitigation rule evaluation
- Scoring rule computation
- Verdict rule determination
- Full engine evaluation
- Determinism guarantees
"""

import pytest
from decimal import Decimal

from decisiongraph import (
    CellType, SourceQuality, Fact, HASH_SCHEME_CANONICAL
)
from decisiongraph.rules import (
    # Exceptions
    RuleError,
    RuleDefinitionError,
    RuleEvaluationError,
    # Severity
    Severity,
    # Evidence anchoring
    DetailedEvidenceAnchor,
    # Conditions
    FactPattern,
    Condition,
    # Rules
    SignalRule,
    MitigationRule,
    ScoringRule,
    VerdictRule,
    ThresholdGate,
    # Context and results
    EvaluationContext,
    EvaluationResult,
    # Engine
    RulesEngine,
    # Helpers
    create_aml_example_engine,
)


# =============================================================================
# FACT PATTERN TESTS
# =============================================================================

class TestFactPattern:
    """Tests for FactPattern matching."""

    def _make_fact(self, **kwargs) -> Fact:
        """Create a test fact with defaults."""
        defaults = {
            "namespace": "test.ns",
            "subject": "case_001",
            "predicate": "test.predicate",
            "object": "test_value",
            "confidence": 0.95,
            "source_quality": SourceQuality.VERIFIED,
        }
        defaults.update(kwargs)
        return Fact(**defaults)

    def test_match_namespace_exact(self):
        """Test exact namespace matching."""
        pattern = FactPattern(namespace="test.ns")
        fact = self._make_fact(namespace="test.ns")
        assert pattern.matches(fact)

        fact2 = self._make_fact(namespace="other.ns")
        assert not pattern.matches(fact2)

    def test_match_namespace_prefix(self):
        """Test prefix namespace matching."""
        pattern = FactPattern(namespace="test", namespace_prefix=True)

        assert pattern.matches(self._make_fact(namespace="test"))
        assert pattern.matches(self._make_fact(namespace="test.ns"))
        assert pattern.matches(self._make_fact(namespace="test.ns.sub"))
        assert not pattern.matches(self._make_fact(namespace="testing"))
        assert not pattern.matches(self._make_fact(namespace="other"))

    def test_match_subject_exact(self):
        """Test exact subject matching."""
        pattern = FactPattern(subject="case_001")
        assert pattern.matches(self._make_fact(subject="case_001"))
        assert not pattern.matches(self._make_fact(subject="case_002"))

    def test_match_subject_regex(self):
        """Test regex subject matching."""
        pattern = FactPattern(subject_regex=r"case_\d+")
        assert pattern.matches(self._make_fact(subject="case_001"))
        assert pattern.matches(self._make_fact(subject="case_999"))
        assert not pattern.matches(self._make_fact(subject="alert_001"))

    def test_match_predicate_exact(self):
        """Test exact predicate matching."""
        pattern = FactPattern(predicate="txn.type")
        assert pattern.matches(self._make_fact(predicate="txn.type"))
        assert not pattern.matches(self._make_fact(predicate="txn.amount"))

    def test_match_predicate_regex(self):
        """Test regex predicate matching."""
        pattern = FactPattern(predicate_regex=r"txn\..+")
        assert pattern.matches(self._make_fact(predicate="txn.type"))
        assert pattern.matches(self._make_fact(predicate="txn.amount"))
        assert not pattern.matches(self._make_fact(predicate="customer.name"))

    def test_match_object_value_string(self):
        """Test object value matching for strings."""
        pattern = FactPattern(object_value="CRYPTOCURRENCY")
        assert pattern.matches(self._make_fact(object="CRYPTOCURRENCY"))
        assert not pattern.matches(self._make_fact(object="WIRE"))

    def test_match_object_contains(self):
        """Test object contains substring matching."""
        pattern = FactPattern(object_contains="CRYPTO")
        assert pattern.matches(self._make_fact(object="CRYPTOCURRENCY"))
        assert pattern.matches(self._make_fact(object="CRYPTO_EXCHANGE"))
        assert not pattern.matches(self._make_fact(object="WIRE_TRANSFER"))

    def test_match_min_confidence(self):
        """Test minimum confidence matching."""
        pattern = FactPattern(min_confidence=0.90)
        assert pattern.matches(self._make_fact(confidence=0.95))
        assert pattern.matches(self._make_fact(confidence=0.90))
        assert not pattern.matches(self._make_fact(confidence=0.85))

    def test_match_source_quality(self):
        """Test source quality matching."""
        pattern = FactPattern(source_quality=SourceQuality.VERIFIED)
        assert pattern.matches(self._make_fact(source_quality=SourceQuality.VERIFIED))
        assert not pattern.matches(self._make_fact(
            source_quality=SourceQuality.SELF_REPORTED,
            confidence=0.8  # Lower confidence for non-verified
        ))

    def test_match_multiple_criteria(self):
        """Test combining multiple matching criteria."""
        pattern = FactPattern(
            namespace="aml.txn",
            predicate="txn.type",
            object_value="CRYPTOCURRENCY",
            min_confidence=0.90
        )

        # All criteria match
        fact = self._make_fact(
            namespace="aml.txn",
            predicate="txn.type",
            object="CRYPTOCURRENCY",
            confidence=0.95
        )
        assert pattern.matches(fact)

        # One criterion fails
        fact2 = self._make_fact(
            namespace="aml.txn",
            predicate="txn.type",
            object="WIRE",  # Different
            confidence=0.95
        )
        assert not pattern.matches(fact2)


# =============================================================================
# CONDITION TESTS
# =============================================================================

class TestCondition:
    """Tests for Condition evaluation."""

    def _make_facts(self) -> list:
        """Create a set of test facts."""
        return [
            Fact(
                namespace="aml.txn",
                subject="case_001",
                predicate="txn.type",
                object="CRYPTOCURRENCY",
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED
            ),
            Fact(
                namespace="aml.txn",
                subject="case_001",
                predicate="txn.amount",
                object="25000",
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED
            ),
            Fact(
                namespace="aml.customer",
                subject="case_001",
                predicate="customer.risk_rating",
                object="HIGH",
                confidence=0.90,
                source_quality=SourceQuality.VERIFIED
            ),
        ]

    def test_single_pattern_match(self):
        """Test condition with single pattern."""
        condition = Condition(
            pattern=FactPattern(predicate="txn.type", object_value="CRYPTOCURRENCY")
        )
        matched, facts = condition.evaluate(self._make_facts())
        assert matched
        assert len(facts) == 1
        assert facts[0].object == "CRYPTOCURRENCY"

    def test_single_pattern_no_match(self):
        """Test condition with no matching facts."""
        condition = Condition(
            pattern=FactPattern(predicate="txn.type", object_value="WIRE")
        )
        matched, facts = condition.evaluate(self._make_facts())
        assert not matched
        assert len(facts) == 0

    def test_count_mode(self):
        """Test condition with count threshold."""
        condition = Condition(
            pattern=FactPattern(namespace="aml.txn", namespace_prefix=True),
            match_mode="count",
            min_count=2
        )
        matched, facts = condition.evaluate(self._make_facts())
        assert matched  # 2 facts in aml.txn namespace
        assert len(facts) == 2

    def test_count_mode_not_enough(self):
        """Test count condition when not enough matches."""
        condition = Condition(
            pattern=FactPattern(namespace="aml.customer"),
            match_mode="count",
            min_count=3
        )
        matched, facts = condition.evaluate(self._make_facts())
        assert not matched  # Only 1 fact in aml.customer

    def test_all_patterns_mode(self):
        """Test condition requiring all patterns to match."""
        condition = Condition(
            patterns=[
                FactPattern(predicate="txn.type"),
                FactPattern(predicate="txn.amount"),
            ],
            match_mode="all"
        )
        matched, facts = condition.evaluate(self._make_facts())
        assert matched
        assert len(facts) == 2

    def test_all_patterns_mode_partial(self):
        """Test all patterns mode when only some match."""
        condition = Condition(
            patterns=[
                FactPattern(predicate="txn.type"),
                FactPattern(predicate="nonexistent"),
            ],
            match_mode="all"
        )
        matched, facts = condition.evaluate(self._make_facts())
        assert not matched

    def test_any_patterns_mode(self):
        """Test condition requiring any pattern to match."""
        condition = Condition(
            patterns=[
                FactPattern(predicate="nonexistent"),
                FactPattern(predicate="txn.type"),
            ],
            match_mode="any"
        )
        matched, facts = condition.evaluate(self._make_facts())
        assert matched
        assert len(facts) == 1

    def test_value_comparison_gte(self):
        """Test value comparison with gte operator."""
        condition = Condition(
            pattern=FactPattern(predicate="txn.amount"),
            compare_op="gte",
            compare_value=10000
        )
        matched, facts = condition.evaluate(self._make_facts())
        assert matched  # 25000 >= 10000

    def test_value_comparison_lt(self):
        """Test value comparison with lt operator."""
        condition = Condition(
            pattern=FactPattern(predicate="txn.amount"),
            compare_op="lt",
            compare_value=10000
        )
        matched, facts = condition.evaluate(self._make_facts())
        assert not matched  # 25000 is not < 10000


# =============================================================================
# SIGNAL RULE TESTS
# =============================================================================

class TestSignalRule:
    """Tests for SignalRule."""

    def test_signal_rule_creation(self):
        """Test creating a signal rule."""
        rule = SignalRule(
            rule_id="sig_001",
            code="HIGH_VALUE",
            name="High Value Transaction",
            severity=Severity.HIGH,
            conditions=[
                Condition(pattern=FactPattern(predicate="txn.amount"))
            ]
        )
        assert rule.rule_id == "sig_001"
        assert rule.code == "HIGH_VALUE"
        assert rule.severity == Severity.HIGH

    def test_signal_rule_missing_id(self):
        """Test signal rule requires rule_id."""
        with pytest.raises(RuleDefinitionError, match="rule_id"):
            SignalRule(
                rule_id="",
                code="TEST",
                name="Test",
                conditions=[Condition(pattern=FactPattern(predicate="test"))]
            )

    def test_signal_rule_missing_conditions(self):
        """Test signal rule requires conditions."""
        with pytest.raises(RuleDefinitionError, match="condition"):
            SignalRule(
                rule_id="sig_001",
                code="TEST",
                name="Test",
                conditions=[]
            )

    def test_signal_rule_logic_hash(self):
        """Test rule logic hash is deterministic."""
        rule1 = SignalRule(
            rule_id="sig_001",
            code="HIGH_VALUE",
            name="High Value",
            severity=Severity.HIGH,
            conditions=[Condition(pattern=FactPattern(predicate="txn.amount"))]
        )
        rule2 = SignalRule(
            rule_id="sig_001",
            code="HIGH_VALUE",
            name="High Value",
            severity=Severity.HIGH,
            conditions=[Condition(pattern=FactPattern(predicate="txn.amount"))]
        )
        assert rule1.rule_logic_hash == rule2.rule_logic_hash

    def test_signal_rule_evaluate_fires(self):
        """Test signal rule evaluation when conditions met."""
        rule = SignalRule(
            rule_id="sig_001",
            code="CRYPTO_TXN",
            name="Cryptocurrency Transaction",
            severity=Severity.MEDIUM,
            conditions=[
                Condition(pattern=FactPattern(
                    predicate="txn.type",
                    object_value="CRYPTOCURRENCY"
                ))
            ]
        )

        facts = [
            Fact(
                namespace="test",
                subject="case_001",
                predicate="txn.type",
                object="CRYPTOCURRENCY",
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED
            )
        ]

        fires, trigger_facts = rule.evaluate(facts)
        assert fires
        assert len(trigger_facts) == 1

    def test_signal_rule_evaluate_not_fires(self):
        """Test signal rule evaluation when conditions not met."""
        rule = SignalRule(
            rule_id="sig_001",
            code="CRYPTO_TXN",
            name="Cryptocurrency Transaction",
            severity=Severity.MEDIUM,
            conditions=[
                Condition(pattern=FactPattern(
                    predicate="txn.type",
                    object_value="CRYPTOCURRENCY"
                ))
            ]
        )

        facts = [
            Fact(
                namespace="test",
                subject="case_001",
                predicate="txn.type",
                object="WIRE",  # Not crypto
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED
            )
        ]

        fires, trigger_facts = rule.evaluate(facts)
        assert not fires
        assert len(trigger_facts) == 0

    def test_signal_rule_disabled(self):
        """Test disabled signal rule doesn't fire."""
        rule = SignalRule(
            rule_id="sig_001",
            code="CRYPTO_TXN",
            name="Cryptocurrency Transaction",
            severity=Severity.MEDIUM,
            enabled=False,
            conditions=[
                Condition(pattern=FactPattern(predicate="txn.type"))
            ]
        )

        facts = [
            Fact(
                namespace="test",
                subject="case_001",
                predicate="txn.type",
                object="CRYPTOCURRENCY",
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED
            )
        ]

        fires, _ = rule.evaluate(facts)
        assert not fires


# =============================================================================
# MITIGATION RULE TESTS
# =============================================================================

class TestMitigationRule:
    """Tests for MitigationRule."""

    def test_mitigation_rule_creation(self):
        """Test creating a mitigation rule."""
        rule = MitigationRule(
            rule_id="mit_001",
            code="DOC_COMPLETE",
            name="Documentation Complete",
            weight="-0.30",
            conditions=[Condition(pattern=FactPattern(predicate="doc.status"))],
            applies_to_signals=["HIGH_VALUE"]
        )
        assert rule.code == "DOC_COMPLETE"
        assert rule.weight == "-0.30"

    def test_mitigation_rule_invalid_weight(self):
        """Test mitigation rule rejects invalid weight."""
        with pytest.raises(RuleDefinitionError, match="weight"):
            MitigationRule(
                rule_id="mit_001",
                code="TEST",
                name="Test",
                weight="not-a-number",
                conditions=[Condition(pattern=FactPattern(predicate="test"))]
            )

    def test_mitigation_rule_evaluate_applies(self):
        """Test mitigation rule applies when conditions met."""
        rule = MitigationRule(
            rule_id="mit_001",
            code="DOC_COMPLETE",
            name="Documentation Complete",
            weight="-0.30",
            applies_to_signals=["HIGH_VALUE"],
            conditions=[
                Condition(pattern=FactPattern(
                    predicate="doc.status",
                    object_value="COMPLETE"
                ))
            ]
        )

        facts = [
            Fact(
                namespace="test",
                subject="case_001",
                predicate="doc.status",
                object="COMPLETE",
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED
            )
        ]

        applies, anchors, mitigated = rule.evaluate(facts, ["HIGH_VALUE"])
        assert applies
        assert len(anchors) == 1
        assert "HIGH_VALUE" in mitigated

    def test_mitigation_rule_no_applicable_signals(self):
        """Test mitigation doesn't apply without applicable signals."""
        rule = MitigationRule(
            rule_id="mit_001",
            code="DOC_COMPLETE",
            name="Documentation Complete",
            weight="-0.30",
            applies_to_signals=["HIGH_VALUE"],  # Only applies to HIGH_VALUE
            conditions=[
                Condition(pattern=FactPattern(predicate="doc.status"))
            ]
        )

        facts = [
            Fact(
                namespace="test",
                subject="case_001",
                predicate="doc.status",
                object="COMPLETE",
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED
            )
        ]

        # No HIGH_VALUE signal fired
        applies, _, _ = rule.evaluate(facts, ["OTHER_SIGNAL"])
        assert not applies


# =============================================================================
# SCORING RULE TESTS
# =============================================================================

class TestScoringRule:
    """Tests for ScoringRule."""

    def test_scoring_rule_creation(self):
        """Test creating a scoring rule."""
        rule = ScoringRule(
            rule_id="score_001",
            name="Risk Score",
            signal_weights={
                "HIGH_VALUE": "0.50",
                "HIGH_RISK_COUNTRY": "0.75"
            },
            threshold_gates=[
                ThresholdGate("CLEAR", "0.30"),
                ThresholdGate("REVIEW", "0.60"),
            ]
        )
        assert rule.rule_id == "score_001"
        assert len(rule.threshold_gates) == 2

    def test_scoring_rule_unordered_gates(self):
        """Test scoring rule rejects unordered threshold gates."""
        with pytest.raises(RuleDefinitionError, match="ordered"):
            ScoringRule(
                rule_id="score_001",
                name="Risk Score",
                threshold_gates=[
                    ThresholdGate("HIGH", "0.60"),
                    ThresholdGate("LOW", "0.30"),  # Lower than previous
                ]
            )

    def test_compute_score_single_signal(self):
        """Test score computation with single signal."""
        rule = ScoringRule(
            rule_id="score_001",
            name="Risk Score",
            signal_weights={"HIGH_VALUE": "0.50"},
            threshold_gates=[
                ThresholdGate("CLEAR", "0.30"),
                ThresholdGate("REVIEW", "0.60"),
            ]
        )

        inherent, mit_sum, residual, gate = rule.compute_score(
            ["HIGH_VALUE"],
            []  # No mitigations
        )

        assert inherent == "0.5"
        assert mit_sum == "0.0"
        assert residual == "0.5"
        assert gate == "REVIEW"  # 0.5 >= 0.30 but < 0.60

    def test_compute_score_with_mitigations(self):
        """Test score computation with mitigations."""
        rule = ScoringRule(
            rule_id="score_001",
            name="Risk Score",
            signal_weights={"HIGH_VALUE": "0.50"},
            threshold_gates=[
                ThresholdGate("CLEAR", "0.30"),
                ThresholdGate("REVIEW", "0.60"),
            ]
        )

        inherent, mit_sum, residual, gate = rule.compute_score(
            ["HIGH_VALUE"],
            ["-0.30"]  # Mitigation reduces by 0.30
        )

        assert inherent == "0.5"
        assert mit_sum == "-0.3"
        assert residual == "0.2"
        assert gate == "CLEAR"  # 0.2 < 0.30

    def test_compute_score_floor_at_zero(self):
        """Test score doesn't go negative."""
        rule = ScoringRule(
            rule_id="score_001",
            name="Risk Score",
            signal_weights={"LOW_RISK": "0.10"},
            threshold_gates=[
                ThresholdGate("CLEAR", "0.30"),
            ]
        )

        _, _, residual, _ = rule.compute_score(
            ["LOW_RISK"],
            ["-0.50"]  # Would be -0.40 without floor
        )

        assert residual == "0.0"


# =============================================================================
# VERDICT RULE TESTS
# =============================================================================

class TestVerdictRule:
    """Tests for VerdictRule."""

    def test_verdict_rule_creation(self):
        """Test creating a verdict rule."""
        rule = VerdictRule(
            rule_id="verdict_001",
            name="AML Verdict",
            gate_verdicts={
                "CLEAR": ("CLOSE_CASE", True),
                "REVIEW": ("ANALYST_REVIEW", False),
            }
        )
        assert rule.rule_id == "verdict_001"

    def test_determine_verdict_mapped(self):
        """Test verdict determination for mapped gate."""
        rule = VerdictRule(
            rule_id="verdict_001",
            name="AML Verdict",
            gate_verdicts={
                "CLEAR": ("CLOSE_CASE", True),
                "REVIEW": ("ANALYST_REVIEW", False),
            }
        )

        verdict, auto_archive = rule.determine_verdict("CLEAR")
        assert verdict == "CLOSE_CASE"
        assert auto_archive is True

    def test_determine_verdict_default(self):
        """Test verdict determination for unmapped gate."""
        rule = VerdictRule(
            rule_id="verdict_001",
            name="AML Verdict",
            gate_verdicts={
                "CLEAR": ("CLOSE_CASE", True),
            },
            default_verdict="MANUAL_REVIEW",
            default_auto_archive=False
        )

        verdict, auto_archive = rule.determine_verdict("UNKNOWN_GATE")
        assert verdict == "MANUAL_REVIEW"
        assert auto_archive is False


# =============================================================================
# RULES ENGINE TESTS
# =============================================================================

class TestRulesEngine:
    """Tests for RulesEngine."""

    def _make_context(self) -> EvaluationContext:
        """Create a test evaluation context."""
        return EvaluationContext(
            graph_id="graph:test-123",
            namespace="aml.cases",
            case_id="case_001",
            system_time="2026-01-28T12:00:00Z"
        )

    def _make_facts(self) -> list:
        """Create test facts."""
        return [
            Fact(
                namespace="aml.txn",
                subject="case_001",
                predicate="txn.type",
                object="CRYPTOCURRENCY",
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED
            ),
            Fact(
                namespace="aml.txn",
                subject="case_001",
                predicate="txn.amount",
                object="25000",
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED
            ),
            Fact(
                namespace="aml.doc",
                subject="case_001",
                predicate="doc.status",
                object="COMPLETE",
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED
            ),
        ]

    def test_engine_creation(self):
        """Test creating an engine."""
        engine = RulesEngine()
        assert engine.signal_rules == []
        assert engine.mitigation_rules == []

    def test_engine_add_rules(self):
        """Test adding rules to engine."""
        engine = RulesEngine()

        engine.add_signal_rule(SignalRule(
            rule_id="sig_001",
            code="TEST",
            name="Test Signal",
            conditions=[Condition(pattern=FactPattern(predicate="test"))]
        ))

        engine.add_mitigation_rule(MitigationRule(
            rule_id="mit_001",
            code="TEST_MIT",
            name="Test Mitigation",
            weight="-0.10",
            conditions=[Condition(pattern=FactPattern(predicate="test"))]
        ))

        assert len(engine.signal_rules) == 1
        assert len(engine.mitigation_rules) == 1

    def test_engine_evaluate_signals(self):
        """Test engine evaluates signals correctly."""
        engine = RulesEngine()

        engine.add_signal_rule(SignalRule(
            rule_id="sig_001",
            code="CRYPTO_TXN",
            name="Crypto Transaction",
            severity=Severity.MEDIUM,
            conditions=[
                Condition(pattern=FactPattern(
                    predicate="txn.type",
                    object_value="CRYPTOCURRENCY"
                ))
            ]
        ))

        result = engine.evaluate(self._make_facts(), self._make_context())

        assert result.signals_fired == 1
        assert len(result.signals) == 1
        assert result.signals[0].header.cell_type == CellType.SIGNAL
        assert result.signals[0].fact.object["code"] == "CRYPTO_TXN"

    def test_engine_evaluate_full_pipeline(self):
        """Test full evaluation pipeline."""
        engine = create_aml_example_engine()

        facts = [
            Fact(
                namespace="aml.txn",
                subject="case_001",
                predicate="txn.type",
                object="CRYPTOCURRENCY",
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED
            ),
            Fact(
                namespace="aml.txn",
                subject="case_001",
                predicate="txn.amount",
                object="25000",
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED
            ),
            Fact(
                namespace="aml.doc",
                subject="case_001",
                predicate="documentation.status",
                object="COMPLETE",
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED
            ),
        ]

        result = engine.evaluate(facts, self._make_context())

        # Should have signals, mitigations, score, verdict
        assert result.signals_fired >= 1
        assert result.score is not None
        assert result.verdict is not None

        # Check score cell
        assert result.score.header.cell_type == CellType.SCORE
        assert "inherent_score" in result.score.fact.object
        assert "residual_score" in result.score.fact.object

        # Check verdict cell
        assert result.verdict.header.cell_type == CellType.VERDICT
        assert "verdict" in result.verdict.fact.object

    def test_engine_evaluate_deterministic(self):
        """Test evaluation is deterministic."""
        engine = create_aml_example_engine()
        facts = self._make_facts()
        context = self._make_context()

        result1 = engine.evaluate(facts, context)
        result2 = engine.evaluate(facts, context)

        # Same inputs should produce same outputs
        assert len(result1.signals) == len(result2.signals)
        for s1, s2 in zip(result1.signals, result2.signals):
            assert s1.cell_id == s2.cell_id

        if result1.score and result2.score:
            assert result1.score.cell_id == result2.score.cell_id

        if result1.verdict and result2.verdict:
            assert result1.verdict.cell_id == result2.verdict.cell_id

    def test_engine_cells_use_canonical_scheme(self):
        """Test all produced cells use canonical hash scheme."""
        engine = create_aml_example_engine()

        facts = [
            Fact(
                namespace="aml.txn",
                subject="case_001",
                predicate="txn.type",
                object="CRYPTOCURRENCY",
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED
            ),
        ]

        result = engine.evaluate(facts, self._make_context())

        for cell in result.all_cells:
            assert cell.header.hash_scheme == HASH_SCHEME_CANONICAL

    def test_engine_cells_chain_correctly(self):
        """Test produced cells chain via prev_cell_hash."""
        engine = create_aml_example_engine()

        facts = [
            Fact(
                namespace="aml.txn",
                subject="case_001",
                predicate="txn.type",
                object="CRYPTOCURRENCY",
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED
            ),
        ]

        result = engine.evaluate(facts, self._make_context())
        cells = result.all_cells

        # Each cell should point to the previous one
        for i in range(1, len(cells)):
            assert cells[i].header.prev_cell_hash == cells[i-1].cell_id


# =============================================================================
# SEVERITY TESTS
# =============================================================================

class TestSeverity:
    """Tests for Severity enum."""

    def test_severity_values(self):
        """Test severity enum values."""
        assert Severity.LOW.value == "LOW"
        assert Severity.MEDIUM.value == "MEDIUM"
        assert Severity.HIGH.value == "HIGH"
        assert Severity.CRITICAL.value == "CRITICAL"

    def test_severity_weights(self):
        """Test severity default weights."""
        assert Severity.LOW.weight == "0.25"
        assert Severity.MEDIUM.weight == "0.50"
        assert Severity.HIGH.weight == "0.75"
        assert Severity.CRITICAL.weight == "1.00"


# =============================================================================
# EXAMPLE ENGINE TESTS
# =============================================================================

class TestAMLExampleEngine:
    """Tests for the AML example engine."""

    def test_example_engine_has_rules(self):
        """Test example engine has expected rules."""
        engine = create_aml_example_engine()

        assert len(engine.signal_rules) >= 2
        assert len(engine.mitigation_rules) >= 1
        assert engine.scoring_rule is not None
        assert engine.verdict_rule is not None

    def test_example_engine_signal_codes(self):
        """Test example engine has expected signal codes."""
        engine = create_aml_example_engine()
        codes = [r.code for r in engine.signal_rules]

        assert "HIGH_VALUE_CRYPTO" in codes
        assert "HIGH_RISK_JURISDICTION" in codes


# =============================================================================
# DETAILED EVIDENCE ANCHOR TESTS
# =============================================================================

class TestDetailedEvidenceAnchor:
    """Tests for DetailedEvidenceAnchor."""

    def test_evidence_anchor_creation(self):
        """Test creating an evidence anchor."""
        anchor = DetailedEvidenceAnchor(
            field="crypto_source",
            value="KRAKEN",
            source="case.evidence.crypto_source",
            cell_id="cell_123"
        )

        assert anchor.field == "crypto_source"
        assert anchor.value == "KRAKEN"
        assert anchor.source == "case.evidence.crypto_source"
        assert anchor.cell_id == "cell_123"

    def test_evidence_anchor_to_dict(self):
        """Test serializing anchor to dict."""
        anchor = DetailedEvidenceAnchor(
            field="tenure_years",
            value="7",
            source="case.customer.tenure_years",
            cell_id="cell_456"
        )

        d = anchor.to_dict()
        assert d["field"] == "tenure_years"
        assert d["value"] == "7"
        assert d["source"] == "case.customer.tenure_years"
        assert d["cell_id"] == "cell_456"

    def test_evidence_anchor_to_dict_no_cell_id(self):
        """Test serializing anchor without cell_id."""
        anchor = DetailedEvidenceAnchor(
            field="amount",
            value="50000",
            source="txn.amount"
        )

        d = anchor.to_dict()
        assert d["field"] == "amount"
        assert "cell_id" not in d

    def test_evidence_anchor_from_fact(self):
        """Test creating anchor from a Fact."""
        fact = Fact(
            namespace="aml_case",
            subject="TXN-001",
            predicate="customer.tenure_years",
            object="5",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        )

        anchor = DetailedEvidenceAnchor.from_fact(fact, "cell_789")

        assert anchor.field == "tenure_years"
        assert anchor.value == "5"
        assert anchor.source == "aml_case.customer.tenure_years"
        assert anchor.cell_id == "cell_789"

    def test_evidence_anchor_from_fact_dict_object(self):
        """Test creating anchor from fact with dict object."""
        fact = Fact(
            namespace="screening",
            subject="CUS-001",
            predicate="disposition",
            object={"status": "false_positive", "reason": "name mismatch"},
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        )

        anchor = DetailedEvidenceAnchor.from_fact(fact)

        assert anchor.field == "disposition"
        assert "false_positive" in anchor.value or "status" in anchor.value
        assert anchor.source == "screening.disposition"


class TestMitigationEvidenceAnchors:
    """Tests for evidence anchoring in mitigation cells."""

    def test_mitigation_cell_has_evidence_anchors(self):
        """Test that mitigation cells include evidence anchors."""
        engine = RulesEngine()

        engine.add_signal_rule(SignalRule(
            rule_id="sig_test",
            code="TEST_SIGNAL",
            name="Test Signal",
            severity=Severity.MEDIUM,
            conditions=[
                Condition(
                    pattern=FactPattern(
                        predicate="test.indicator",
                        object_value="FLAGGED"
                    )
                )
            ]
        ))

        engine.add_mitigation_rule(MitigationRule(
            rule_id="mit_test",
            code="MF_TEST",
            name="Test Mitigation",
            weight="-0.25",
            applies_to_signals=["TEST_SIGNAL"],
            conditions=[
                Condition(
                    pattern=FactPattern(
                        predicate="test.mitigator",
                        object_value="SAFE"
                    )
                )
            ]
        ))

        facts = [
            Fact(
                namespace="test",
                subject="CASE-001",
                predicate="test.indicator",
                object="FLAGGED",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED
            ),
            Fact(
                namespace="test",
                subject="CASE-001",
                predicate="test.mitigator",
                object="SAFE",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED
            ),
        ]

        context = EvaluationContext(
            graph_id="graph:test",
            namespace="test",
            case_id="CASE-001"
        )

        result = engine.evaluate(facts, context)

        # Should have one mitigation
        assert len(result.mitigations) == 1
        mit_cell = result.mitigations[0]

        # Check evidence anchors in payload
        payload = mit_cell.fact.object
        assert "evidence_anchors" in payload
        assert len(payload["evidence_anchors"]) > 0

        # First anchor should have field, value, source
        anchor = payload["evidence_anchors"][0]
        assert "field" in anchor
        assert "value" in anchor
        assert "source" in anchor
