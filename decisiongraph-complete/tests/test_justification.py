"""
Tests for DecisionGraph Justification Module (v2.0)

Tests cover:
- JustificationAnswers completeness checking
- JustificationBuilder fluent interface
- Review gate evaluation
- Auto-justification helpers
- Justification analysis
"""

import pytest

from decisiongraph import (
    DecisionCell, Header, Fact, LogicAnchor,
    CellType, SourceQuality, NULL_HASH,
    HASH_SCHEME_CANONICAL, get_current_timestamp
)
from decisiongraph.justification import (
    # Exceptions
    JustificationError,
    IncompleteJustificationError,
    GatingError,
    # Question sets
    UniversalQuestionSet,
    UNIVERSAL_QUESTIONS_V1,
    get_question_set,
    # Answers
    JustificationAnswers,
    # Builder
    JustificationBuilder,
    # Gating
    ReviewGateResult,
    GateEvaluation,
    ReviewGate,
    # Helpers
    create_signal_justification,
    create_verdict_justification,
    create_auto_justification,
    # Analysis
    JustificationSummary,
    analyze_justifications,
)


# =============================================================================
# TEST HELPERS
# =============================================================================

def make_cell_id() -> str:
    """Generate a fake cell_id (64 hex chars)."""
    return "a" * 64


def make_signal_cell(subject: str = "case_001", code: str = "TEST_SIGNAL") -> DecisionCell:
    """Create a mock SIGNAL cell for testing."""
    return DecisionCell(
        header=Header(
            version="1.0",
            graph_id="graph:test",
            cell_type=CellType.SIGNAL,
            system_time=get_current_timestamp(),
            prev_cell_hash=NULL_HASH,
            hash_scheme=HASH_SCHEME_CANONICAL
        ),
        fact=Fact(
            namespace="test",
            subject=subject,
            predicate="signal.fired",
            object={
                "schema_version": "1.0",
                "code": code,
                "severity": "MEDIUM",
                "trigger_facts": [],
                "policy_refs": []
            },
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="test_rule",
            rule_logic_hash="abc123"
        )
    )


def make_verdict_cell() -> DecisionCell:
    """Create a mock VERDICT cell for testing."""
    return DecisionCell(
        header=Header(
            version="1.0",
            graph_id="graph:test",
            cell_type=CellType.VERDICT,
            system_time=get_current_timestamp(),
            prev_cell_hash=NULL_HASH,
            hash_scheme=HASH_SCHEME_CANONICAL
        ),
        fact=Fact(
            namespace="test",
            subject="case_001",
            predicate="verdict.rendered",
            object={
                "schema_version": "1.0",
                "verdict": "CLEAR_AND_CLOSE",
                "rationale_fact_refs": [],
                "auto_archive_permitted": True
            },
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="verdict_rule",
            rule_logic_hash="def456"
        )
    )


def make_justification_cell(target_cell_id: str, answers: JustificationAnswers) -> DecisionCell:
    """Create a JUSTIFICATION cell for testing."""
    return DecisionCell(
        header=Header(
            version="1.0",
            graph_id="graph:test",
            cell_type=CellType.JUSTIFICATION,
            system_time=get_current_timestamp(),
            prev_cell_hash=NULL_HASH,
            hash_scheme=HASH_SCHEME_CANONICAL
        ),
        fact=Fact(
            namespace="test",
            subject="case_001",
            predicate="justification.recorded",
            object={
                "schema_version": "1.0",
                "target_cell_id": target_cell_id,
                "question_set_id": "universal.v1",
                "answers": answers.to_dict()
            },
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="justification:universal.v1",
            rule_logic_hash="ghi789"
        )
    )


# =============================================================================
# QUESTION SET TESTS
# =============================================================================

class TestQuestionSet:
    """Tests for question set definitions."""

    def test_universal_v1_has_required_questions(self):
        """Test V1 question set has all required questions."""
        questions = get_question_set(UniversalQuestionSet.V1)
        assert "basis_fact_ids" in questions
        assert "evidence_sufficient" in questions
        assert "missing_evidence" in questions
        assert "counterfactuals" in questions
        assert "policy_refs" in questions
        assert "needs_human_review" in questions
        assert "review_reason" in questions

    def test_universal_v1_question_types(self):
        """Test V1 question types are correct."""
        questions = get_question_set(UniversalQuestionSet.V1)
        assert questions["basis_fact_ids"]["type"] == "array:cell_id"
        assert questions["evidence_sufficient"]["type"] == "boolean"
        assert questions["needs_human_review"]["type"] == "boolean"

    def test_unknown_question_set(self):
        """Test unknown question set raises error."""
        with pytest.raises(ValueError, match="Unknown question set"):
            get_question_set("invalid.version")


# =============================================================================
# JUSTIFICATION ANSWERS TESTS
# =============================================================================

class TestJustificationAnswers:
    """Tests for JustificationAnswers."""

    def test_default_answers(self):
        """Test default values."""
        answers = JustificationAnswers()
        assert answers.basis_fact_ids == []
        assert answers.evidence_sufficient is False
        assert answers.needs_human_review is True  # Safe default

    def test_to_dict(self):
        """Test serialization."""
        answers = JustificationAnswers(
            basis_fact_ids=["a" * 64],
            evidence_sufficient=True,
            missing_evidence=[],
            counterfactuals=["If X, then Y"],
            policy_refs=["b" * 64],
            needs_human_review=False
        )
        d = answers.to_dict()
        assert d["basis_fact_ids"] == ["a" * 64]
        assert d["evidence_sufficient"] is True
        assert d["needs_human_review"] is False
        assert "review_reason" not in d  # None should be excluded

    def test_to_dict_with_review_reason(self):
        """Test serialization includes review_reason when set."""
        answers = JustificationAnswers(
            basis_fact_ids=[],
            evidence_sufficient=False,
            missing_evidence=["Document X"],
            counterfactuals=[],
            policy_refs=[],
            needs_human_review=True,
            review_reason="Missing critical document"
        )
        d = answers.to_dict()
        assert d["review_reason"] == "Missing critical document"

    def test_from_dict(self):
        """Test deserialization."""
        data = {
            "basis_fact_ids": ["c" * 64],
            "evidence_sufficient": True,
            "missing_evidence": [],
            "counterfactuals": ["Test"],
            "policy_refs": ["d" * 64],
            "needs_human_review": False
        }
        answers = JustificationAnswers.from_dict(data)
        assert answers.basis_fact_ids == ["c" * 64]
        assert answers.evidence_sufficient is True
        assert answers.needs_human_review is False

    def test_is_complete_minimal(self):
        """Test minimal complete justification."""
        answers = JustificationAnswers(
            basis_fact_ids=[],
            evidence_sufficient=True,
            missing_evidence=[],
            counterfactuals=[],
            policy_refs=[],
            needs_human_review=False
        )
        is_complete, missing = answers.is_complete()
        assert is_complete
        assert len(missing) == 0

    def test_is_complete_needs_review_reason(self):
        """Test review_reason required when needs_human_review is True."""
        answers = JustificationAnswers(
            basis_fact_ids=[],
            evidence_sufficient=True,
            missing_evidence=[],
            counterfactuals=[],
            policy_refs=[],
            needs_human_review=True,
            review_reason=None  # Missing!
        )
        is_complete, missing = answers.is_complete()
        assert not is_complete
        assert "review_reason" in missing

    def test_is_complete_with_review_reason(self):
        """Test complete when review_reason provided."""
        answers = JustificationAnswers(
            basis_fact_ids=[],
            evidence_sufficient=True,
            missing_evidence=[],
            counterfactuals=[],
            policy_refs=[],
            needs_human_review=True,
            review_reason="Needs analyst sign-off"
        )
        is_complete, missing = answers.is_complete()
        assert is_complete


# =============================================================================
# JUSTIFICATION BUILDER TESTS
# =============================================================================

class TestJustificationBuilder:
    """Tests for JustificationBuilder."""

    def test_builder_fluent_interface(self):
        """Test fluent interface returns self."""
        builder = JustificationBuilder()
        result = builder.set_target("a" * 64)
        assert result is builder

    def test_builder_set_all_fields(self):
        """Test setting all fields."""
        builder = JustificationBuilder()
        builder.set_target("a" * 64)
        builder.set_basis_facts(["b" * 64])
        builder.set_evidence_sufficient(True)
        builder.set_missing_evidence([])
        builder.set_counterfactuals(["If X"])
        builder.set_policy_refs(["c" * 64])
        builder.set_needs_human_review(False)

        is_valid, errors = builder.validate()
        assert is_valid
        assert len(errors) == 0

    def test_builder_add_methods(self):
        """Test add methods for lists."""
        builder = JustificationBuilder()
        builder.set_target("a" * 64)
        builder.add_basis_fact("b" * 64)
        builder.add_basis_fact("c" * 64)
        builder.add_counterfactual("If X")
        builder.add_policy_ref("d" * 64)
        builder.set_evidence_sufficient(True)
        builder.set_needs_human_review(False)

        assert len(builder.answers.basis_fact_ids) == 2
        assert len(builder.answers.counterfactuals) == 1
        assert len(builder.answers.policy_refs) == 1

    def test_builder_validate_missing_target(self):
        """Test validation requires target."""
        builder = JustificationBuilder()
        builder.set_evidence_sufficient(True)
        builder.set_needs_human_review(False)

        is_valid, errors = builder.validate()
        assert not is_valid
        assert any("target" in e.lower() for e in errors)

    def test_builder_validate_incomplete_answers(self):
        """Test validation catches incomplete answers."""
        builder = JustificationBuilder()
        builder.set_target("a" * 64)
        builder.set_needs_human_review(True)
        # Missing review_reason

        is_valid, errors = builder.validate()
        assert not is_valid
        assert any("review_reason" in e for e in errors)

    def test_builder_build_success(self):
        """Test building a justification cell."""
        builder = JustificationBuilder()
        builder.set_target("a" * 64)
        builder.set_basis_facts(["b" * 64])
        builder.set_evidence_sufficient(True)
        builder.set_missing_evidence([])
        builder.set_counterfactuals(["If X"])
        builder.set_policy_refs([])
        builder.set_needs_human_review(False)

        cell = builder.build(
            graph_id="graph:test",
            namespace="test.ns",
            subject="case_001",
            prev_cell_hash=NULL_HASH
        )

        assert cell.header.cell_type == CellType.JUSTIFICATION
        assert cell.fact.object["target_cell_id"] == "a" * 64
        assert cell.fact.object["question_set_id"] == "universal.v1"
        assert "answers" in cell.fact.object

    def test_builder_build_incomplete_raises(self):
        """Test building incomplete justification raises error."""
        builder = JustificationBuilder()
        builder.set_target("a" * 64)
        # Missing required answers

        with pytest.raises(IncompleteJustificationError):
            builder.build(
                graph_id="graph:test",
                namespace="test.ns",
                subject="case_001",
                prev_cell_hash=NULL_HASH
            )

    def test_builder_uses_canonical_scheme(self):
        """Test built cells use canonical hash scheme."""
        builder = JustificationBuilder()
        builder.set_target("a" * 64)
        builder.set_basis_facts([])
        builder.set_evidence_sufficient(True)
        builder.set_counterfactuals(["If X"])
        builder.set_policy_refs([])
        builder.set_needs_human_review(False)

        cell = builder.build(
            graph_id="graph:test",
            namespace="test.ns",
            subject="case_001",
            prev_cell_hash=NULL_HASH
        )

        assert cell.header.hash_scheme == HASH_SCHEME_CANONICAL


# =============================================================================
# REVIEW GATE TESTS
# =============================================================================

class TestReviewGate:
    """Tests for ReviewGate."""

    def test_gate_pass_with_complete_justifications(self):
        """Test gate passes when all justifications complete."""
        gate = ReviewGate(
            gate_id="gate_001",
            name="Test Gate"
        )

        signal = make_signal_cell()
        answers = JustificationAnswers(
            basis_fact_ids=["b" * 64],
            evidence_sufficient=True,
            missing_evidence=[],
            counterfactuals=["If X"],
            policy_refs=[],
            needs_human_review=False
        )
        justification = make_justification_cell(signal.cell_id, answers)

        result = gate.evaluate([signal], [justification])

        assert result.result == ReviewGateResult.PASS
        assert result.can_auto_proceed

    def test_gate_review_required_missing_justification(self):
        """Test gate requires review when justification missing."""
        gate = ReviewGate(
            gate_id="gate_001",
            name="Test Gate"
        )

        signal = make_signal_cell()
        # No justification provided

        result = gate.evaluate([signal], [])

        assert result.result == ReviewGateResult.REVIEW_REQUIRED
        assert signal.cell_id in result.missing_justifications
        assert not result.can_auto_proceed

    def test_gate_review_required_incomplete_justification(self):
        """Test gate requires review when justification incomplete."""
        gate = ReviewGate(
            gate_id="gate_001",
            name="Test Gate"
        )

        signal = make_signal_cell()
        answers = JustificationAnswers(
            basis_fact_ids=[],
            evidence_sufficient=True,
            missing_evidence=[],
            counterfactuals=[],
            policy_refs=[],
            needs_human_review=True,
            review_reason=None  # Missing!
        )
        justification = make_justification_cell(signal.cell_id, answers)

        result = gate.evaluate([signal], [justification])

        assert result.result == ReviewGateResult.REVIEW_REQUIRED
        assert signal.cell_id in result.incomplete_justifications

    def test_gate_review_required_human_review_needed(self):
        """Test gate requires review when justification says so."""
        gate = ReviewGate(
            gate_id="gate_001",
            name="Test Gate"
        )

        signal = make_signal_cell()
        answers = JustificationAnswers(
            basis_fact_ids=[],
            evidence_sufficient=True,
            missing_evidence=[],
            counterfactuals=["If X"],
            policy_refs=[],
            needs_human_review=True,
            review_reason="Analyst must verify"
        )
        justification = make_justification_cell(signal.cell_id, answers)

        result = gate.evaluate([signal], [justification])

        assert result.result == ReviewGateResult.REVIEW_REQUIRED
        assert any("Analyst must verify" in r for r in result.reasons)

    def test_gate_review_required_insufficient_evidence(self):
        """Test gate requires review when evidence insufficient."""
        gate = ReviewGate(
            gate_id="gate_001",
            name="Test Gate",
            block_on_insufficient_evidence=True
        )

        signal = make_signal_cell()
        answers = JustificationAnswers(
            basis_fact_ids=[],
            evidence_sufficient=False,  # Not sufficient
            missing_evidence=["Bank statement"],
            counterfactuals=["If X"],
            policy_refs=[],
            needs_human_review=False
        )
        justification = make_justification_cell(signal.cell_id, answers)

        result = gate.evaluate([signal], [justification])

        assert result.result == ReviewGateResult.REVIEW_REQUIRED
        assert any("Insufficient evidence" in r for r in result.reasons)

    def test_gate_review_required_no_counterfactuals(self):
        """Test gate requires review when counterfactuals missing."""
        gate = ReviewGate(
            gate_id="gate_001",
            name="Test Gate",
            require_counterfactuals=True
        )

        signal = make_signal_cell()
        answers = JustificationAnswers(
            basis_fact_ids=[],
            evidence_sufficient=True,
            missing_evidence=[],
            counterfactuals=[],  # Empty!
            policy_refs=[],
            needs_human_review=False
        )
        justification = make_justification_cell(signal.cell_id, answers)

        result = gate.evaluate([signal], [justification])

        assert result.result == ReviewGateResult.REVIEW_REQUIRED
        assert any("counterfactual" in r.lower() for r in result.reasons)

    def test_gate_requires_minimum_policy_refs(self):
        """Test gate enforces minimum policy refs."""
        gate = ReviewGate(
            gate_id="gate_001",
            name="Test Gate",
            min_policy_refs=2
        )

        signal = make_signal_cell()
        answers = JustificationAnswers(
            basis_fact_ids=[],
            evidence_sufficient=True,
            missing_evidence=[],
            counterfactuals=["If X"],
            policy_refs=["a" * 64],  # Only 1, need 2
            needs_human_review=False
        )
        justification = make_justification_cell(signal.cell_id, answers)

        result = gate.evaluate([signal], [justification])

        assert result.result == ReviewGateResult.REVIEW_REQUIRED
        assert any("policy ref" in r.lower() for r in result.reasons)

    def test_gate_ignores_non_required_cell_types(self):
        """Test gate ignores cell types not in requires_justification_for."""
        gate = ReviewGate(
            gate_id="gate_001",
            name="Test Gate",
            requires_justification_for=[CellType.VERDICT]  # Only VERDICT
        )

        signal = make_signal_cell()  # SIGNAL - not required
        # No justification for signal

        result = gate.evaluate([signal], [])

        # Should pass because SIGNAL doesn't require justification
        assert result.result == ReviewGateResult.PASS


# =============================================================================
# AUTO-JUSTIFICATION HELPER TESTS
# =============================================================================

class TestAutoJustificationHelpers:
    """Tests for auto-justification helper functions."""

    def test_create_signal_justification(self):
        """Test creating signal justification."""
        signal = make_signal_cell(code="SIGNAL")
        trigger = make_signal_cell(code="TRIGGER")
        policy = make_signal_cell(code="POLICY")

        builder = create_signal_justification(
            signal_cell=signal,
            trigger_facts=[trigger],
            policy_refs=[policy],
            counterfactuals=["If trigger not present"],
            evidence_sufficient=True
        )

        assert builder.target_cell_id == signal.cell_id
        assert trigger.cell_id in builder.answers.basis_fact_ids
        assert policy.cell_id in builder.answers.policy_refs
        assert builder.answers.evidence_sufficient is True

    def test_create_verdict_justification(self):
        """Test creating verdict justification."""
        verdict = make_verdict_cell()
        supporting = make_signal_cell()

        builder = create_verdict_justification(
            verdict_cell=verdict,
            supporting_cells=[supporting],
            policy_refs=[],
            counterfactuals=["If score higher"],
            needs_human_review=True,
            review_reason="High-value case"
        )

        assert builder.target_cell_id == verdict.cell_id
        assert supporting.cell_id in builder.answers.basis_fact_ids
        assert builder.answers.needs_human_review is True
        assert builder.answers.review_reason == "High-value case"

    def test_create_auto_justification(self):
        """Test creating minimal auto-justification."""
        signal = make_signal_cell()

        builder = create_auto_justification(
            target_cell=signal,
            basis_facts=["a" * 64],
            policy_refs=["b" * 64]
        )

        assert builder.target_cell_id == signal.cell_id
        assert builder.answers.evidence_sufficient is True
        assert builder.answers.needs_human_review is False
        assert len(builder.answers.counterfactuals) == 1  # Default


# =============================================================================
# JUSTIFICATION ANALYSIS TESTS
# =============================================================================

class TestJustificationAnalysis:
    """Tests for justification analysis."""

    def test_analyze_empty(self):
        """Test analysis with no targets."""
        summary = analyze_justifications([], [])
        assert summary.total_targets == 0
        assert summary.completion_rate == 1.0  # Vacuously complete

    def test_analyze_all_justified(self):
        """Test analysis when all targets justified."""
        signal = make_signal_cell()
        answers = JustificationAnswers(
            basis_fact_ids=[],
            evidence_sufficient=True,
            missing_evidence=[],
            counterfactuals=["If X"],
            policy_refs=["a" * 64],
            needs_human_review=False
        )
        justification = make_justification_cell(signal.cell_id, answers)

        summary = analyze_justifications([signal], [justification])

        assert summary.total_targets == 1
        assert summary.justified == 1
        assert summary.missing == 0
        assert summary.is_complete
        assert summary.can_auto_close

    def test_analyze_missing_justification(self):
        """Test analysis with missing justification."""
        signal = make_signal_cell()

        summary = analyze_justifications([signal], [])

        assert summary.total_targets == 1
        assert summary.missing == 1
        assert not summary.is_complete
        assert not summary.can_auto_close

    def test_analyze_needs_review(self):
        """Test analysis tracks review requirements."""
        signal = make_signal_cell()
        answers = JustificationAnswers(
            basis_fact_ids=[],
            evidence_sufficient=True,
            missing_evidence=[],
            counterfactuals=["If X"],
            policy_refs=[],
            needs_human_review=True,
            review_reason="Analyst check"
        )
        justification = make_justification_cell(signal.cell_id, answers)

        summary = analyze_justifications([signal], [justification])

        assert summary.needs_review == 1
        assert not summary.can_auto_close  # Can't auto-close if review needed

    def test_analyze_evidence_gaps(self):
        """Test analysis collects evidence gaps."""
        signal = make_signal_cell()
        answers = JustificationAnswers(
            basis_fact_ids=[],
            evidence_sufficient=False,
            missing_evidence=["Bank statement", "ID verification"],
            counterfactuals=["If X"],
            policy_refs=[],
            needs_human_review=False
        )
        justification = make_justification_cell(signal.cell_id, answers)

        summary = analyze_justifications([signal], [justification])

        assert "Bank statement" in summary.evidence_gaps
        assert "ID verification" in summary.evidence_gaps

    def test_analyze_policy_coverage(self):
        """Test analysis calculates policy coverage."""
        signal1 = make_signal_cell(code="SIGNAL_1")
        signal2 = make_signal_cell(code="SIGNAL_2")

        answers1 = JustificationAnswers(
            basis_fact_ids=[],
            evidence_sufficient=True,
            missing_evidence=[],
            counterfactuals=["If X"],
            policy_refs=["a" * 64],  # Has policy ref
            needs_human_review=False
        )
        answers2 = JustificationAnswers(
            basis_fact_ids=[],
            evidence_sufficient=True,
            missing_evidence=[],
            counterfactuals=["If Y"],
            policy_refs=[],  # No policy ref
            needs_human_review=False
        )

        j1 = make_justification_cell(signal1.cell_id, answers1)
        j2 = make_justification_cell(signal2.cell_id, answers2)

        summary = analyze_justifications([signal1, signal2], [j1, j2])

        assert summary.policy_coverage == 0.5  # 1 of 2 has policy refs

    def test_analyze_filters_by_cell_type(self):
        """Test analysis respects required_cell_types filter."""
        signal = make_signal_cell()
        verdict = make_verdict_cell()

        # Only provide justification for signal
        answers = JustificationAnswers(
            basis_fact_ids=[],
            evidence_sufficient=True,
            missing_evidence=[],
            counterfactuals=["If X"],
            policy_refs=[],
            needs_human_review=False
        )
        j = make_justification_cell(signal.cell_id, answers)

        # Only require justification for SIGNAL
        summary = analyze_justifications(
            [signal, verdict],
            [j],
            required_cell_types=[CellType.SIGNAL]
        )

        # Should be complete - VERDICT not required
        assert summary.total_targets == 1
        assert summary.justified == 1
        assert summary.is_complete
