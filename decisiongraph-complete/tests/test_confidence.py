"""
Tests for DecisionGraph Confidence Calculation Module (v2.0)

Tests cover:
- Confidence weight configuration
- Individual factor computation
- Overall confidence calculation
- Gate pass rate with different statuses
- Auto-archive eligibility
- Recommendations generation
"""

import pytest
from decimal import Decimal
from dataclasses import dataclass
from typing import List, Optional

from decisiongraph.confidence import (
    # Exceptions
    ConfidenceError,
    ConfigurationError,
    # Configuration
    ConfidenceWeights,
    ConfidenceConfig,
    # Results
    ConfidenceFactor,
    ConfidenceResult,
    # Calculator
    ConfidenceCalculator,
    # Convenience
    compute_confidence,
)
from decisiongraph.gates import GateResult, GateStatus


# =============================================================================
# MOCK CLASSES
# =============================================================================

@dataclass
class MockCitationQuality:
    """Mock CitationQuality for testing."""
    coverage_ratio: Decimal = Decimal("1.00")
    signals_with_citations: int = 10
    total_signals: int = 10


# =============================================================================
# CONFIDENCE WEIGHTS TESTS
# =============================================================================

class TestConfidenceWeights:
    """Tests for ConfidenceWeights."""

    def test_default_weights(self):
        """Test default weights sum to 1.0."""
        weights = ConfidenceWeights()

        total = (
            weights.citation_coverage +
            weights.evidence_completeness +
            weights.gate_pass_rate +
            weights.documentation_score
        )

        assert total == Decimal("1.0")

    def test_custom_weights_normalized(self):
        """Test custom weights are normalized to 1.0."""
        weights = ConfidenceWeights(
            citation_coverage=Decimal("0.50"),
            evidence_completeness=Decimal("0.50"),
            gate_pass_rate=Decimal("0.50"),
            documentation_score=Decimal("0.50"),
        )

        total = (
            weights.citation_coverage +
            weights.evidence_completeness +
            weights.gate_pass_rate +
            weights.documentation_score
        )

        assert abs(total - Decimal("1.0")) < Decimal("0.01")

    def test_weights_to_dict(self):
        """Test weights serialization."""
        weights = ConfidenceWeights()
        d = weights.to_dict()

        assert "citation_coverage" in d
        assert "evidence_completeness" in d
        assert "gate_pass_rate" in d
        assert "documentation_score" in d


# =============================================================================
# CONFIDENCE CONFIG TESTS
# =============================================================================

class TestConfidenceConfig:
    """Tests for ConfidenceConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ConfidenceConfig()

        assert config.auto_archive_threshold == Decimal("0.80")
        assert config.warn_penalty == Decimal("0.50")
        assert config.precision == 2

    def test_from_pack_empty(self):
        """Test loading from empty pack data."""
        config = ConfidenceConfig.from_pack({})

        assert config.auto_archive_threshold == Decimal("0.80")

    def test_from_pack_with_confidence(self):
        """Test loading from pack with confidence section."""
        pack_data = {
            "confidence": {
                "auto_archive_threshold": "0.90",
                "warn_penalty": "0.75",
                "weights": {
                    "citation_coverage": "0.30",
                    "evidence_completeness": "0.30",
                    "gate_pass_rate": "0.20",
                    "documentation_score": "0.20",
                }
            }
        }

        config = ConfidenceConfig.from_pack(pack_data)

        assert config.auto_archive_threshold == Decimal("0.90")
        assert config.warn_penalty == Decimal("0.75")


# =============================================================================
# CONFIDENCE FACTOR TESTS
# =============================================================================

class TestConfidenceFactor:
    """Tests for ConfidenceFactor."""

    def test_factor_creation(self):
        """Test creating a factor."""
        factor = ConfidenceFactor(
            name="test_factor",
            raw_value=Decimal("0.80"),
            weight=Decimal("0.25"),
            weighted_value=Decimal("0.20"),
            description="Test factor description"
        )

        assert factor.name == "test_factor"
        assert factor.raw_value == Decimal("0.80")
        assert factor.weighted_value == Decimal("0.20")

    def test_factor_to_dict(self):
        """Test factor serialization."""
        factor = ConfidenceFactor(
            name="test",
            raw_value=Decimal("0.50"),
            weight=Decimal("0.25"),
            weighted_value=Decimal("0.125")
        )

        d = factor.to_dict()
        assert d["name"] == "test"
        assert d["raw_value"] == "0.50"


# =============================================================================
# CONFIDENCE RESULT TESTS
# =============================================================================

class TestConfidenceResult:
    """Tests for ConfidenceResult."""

    def test_result_creation(self):
        """Test creating a result."""
        result = ConfidenceResult(
            overall_confidence=Decimal("0.85"),
            factors=[],
            citation_quality=Decimal("1.00"),
            evidence_completeness=Decimal("0.80"),
            gate_pass_rate=Decimal("1.00"),
            documentation_score=Decimal("0.60"),
            decision_clarity=Decimal("1.00"),
            auto_archive_eligible=True,
            recommendations=[]
        )

        assert result.overall_confidence == Decimal("0.85")
        assert result.auto_archive_eligible is True

    def test_confidence_percentage(self):
        """Test confidence percentage property."""
        result = ConfidenceResult(
            overall_confidence=Decimal("0.78"),
            factors=[],
            citation_quality=Decimal("0.80"),
            evidence_completeness=Decimal("0.75"),
            gate_pass_rate=Decimal("0.80"),
            documentation_score=Decimal("0.77"),
            decision_clarity=Decimal("0.50"),
            auto_archive_eligible=False
        )

        assert result.confidence_percentage == 78

    def test_result_to_dict(self):
        """Test result serialization."""
        result = ConfidenceResult(
            overall_confidence=Decimal("0.75"),
            factors=[],
            citation_quality=Decimal("0.80"),
            evidence_completeness=Decimal("0.70"),
            gate_pass_rate=Decimal("0.75"),
            documentation_score=Decimal("0.75"),
            decision_clarity=Decimal("0.50"),
            auto_archive_eligible=False,
            recommendations=["Add citations"]
        )

        d = result.to_dict()
        assert d["overall_confidence"] == "0.75"
        assert d["recommendations"] == ["Add citations"]


# =============================================================================
# CONFIDENCE CALCULATOR TESTS
# =============================================================================

class TestConfidenceCalculator:
    """Tests for ConfidenceCalculator."""

    def test_default_calculator(self):
        """Test creating calculator with defaults."""
        calculator = ConfidenceCalculator()
        assert calculator.config is not None

    def test_custom_config(self):
        """Test calculator with custom config."""
        config = ConfidenceConfig()
        config.warn_penalty = Decimal("0.75")

        calculator = ConfidenceCalculator(config)
        assert calculator.config.warn_penalty == Decimal("0.75")


class TestCitationCoverage:
    """Tests for citation coverage factor."""

    def test_full_coverage(self):
        """Test 100% citation coverage."""
        calculator = ConfidenceCalculator()
        citation_quality = MockCitationQuality(coverage_ratio=Decimal("1.00"))

        result = calculator.compute(citation_quality=citation_quality)

        assert result.citation_quality == Decimal("1.00")

    def test_partial_coverage(self):
        """Test partial citation coverage."""
        calculator = ConfidenceCalculator()
        citation_quality = MockCitationQuality(
            coverage_ratio=Decimal("0.50"),
            signals_with_citations=5,
            total_signals=10
        )

        result = calculator.compute(citation_quality=citation_quality)

        assert result.citation_quality == Decimal("0.50")
        assert any("citations" in r.lower() for r in result.recommendations)

    def test_no_citation_quality(self):
        """Test with no citation quality data."""
        calculator = ConfidenceCalculator()

        result = calculator.compute(citation_quality=None)

        assert result.citation_quality == Decimal("0.00")


class TestEvidenceCompleteness:
    """Tests for evidence completeness factor."""

    def test_full_evidence(self):
        """Test 100% evidence completeness."""
        calculator = ConfidenceCalculator()

        result = calculator.compute(evidence_anchored=5, total_evidence=5)

        assert result.evidence_completeness == Decimal("1.00")

    def test_partial_evidence(self):
        """Test partial evidence completeness."""
        calculator = ConfidenceCalculator()

        result = calculator.compute(evidence_anchored=3, total_evidence=6)

        assert result.evidence_completeness == Decimal("0.50")
        assert any("evidence" in r.lower() for r in result.recommendations)

    def test_no_evidence_needed(self):
        """Test when no evidence is required."""
        calculator = ConfidenceCalculator()

        result = calculator.compute(evidence_anchored=0, total_evidence=0)

        assert result.evidence_completeness == Decimal("1.00")


class TestGatePassRate:
    """Tests for gate pass rate factor."""

    def test_all_gates_pass(self):
        """Test 100% gate pass rate."""
        calculator = ConfidenceCalculator()
        gates = [
            GateResult(gate_number=1, gate_name="G1", status=GateStatus.PASS),
            GateResult(gate_number=2, gate_name="G2", status=GateStatus.PASS),
            GateResult(gate_number=3, gate_name="G3", status=GateStatus.PASS),
            GateResult(gate_number=4, gate_name="G4", status=GateStatus.PASS),
        ]

        result = calculator.compute(gate_results=gates)

        assert result.gate_pass_rate == Decimal("1.00")

    def test_some_gates_warn(self):
        """Test gate pass rate with warnings."""
        calculator = ConfidenceCalculator()
        gates = [
            GateResult(gate_number=1, gate_name="G1", status=GateStatus.PASS),
            GateResult(gate_number=2, gate_name="G2", status=GateStatus.WARN),
            GateResult(gate_number=3, gate_name="G3", status=GateStatus.PASS),
            GateResult(gate_number=4, gate_name="G4", status=GateStatus.PASS),
        ]

        result = calculator.compute(gate_results=gates)

        # With default warn_penalty=0.5: (1 + 0.5 + 1 + 1) / 4 = 0.875
        assert result.gate_pass_rate == Decimal("0.88")

    def test_gate_fail(self):
        """Test gate pass rate with failure."""
        calculator = ConfidenceCalculator()
        gates = [
            GateResult(gate_number=1, gate_name="G1", status=GateStatus.PASS),
            GateResult(gate_number=2, gate_name="G2", status=GateStatus.FAIL),
            GateResult(gate_number=3, gate_name="G3", status=GateStatus.PASS),
            GateResult(gate_number=4, gate_name="G4", status=GateStatus.PASS),
        ]

        result = calculator.compute(gate_results=gates)

        # (1 + 0 + 1 + 1) / 4 = 0.75
        assert result.gate_pass_rate == Decimal("0.75")

    def test_no_gates(self):
        """Test when no gates are evaluated."""
        calculator = ConfidenceCalculator()

        result = calculator.compute(gate_results=None)

        assert result.gate_pass_rate == Decimal("1.00")

    def test_custom_warn_penalty(self):
        """Test custom warn penalty."""
        config = ConfidenceConfig()
        config.warn_penalty = Decimal("0.75")
        calculator = ConfidenceCalculator(config)

        gates = [
            GateResult(gate_number=1, gate_name="G1", status=GateStatus.WARN),
            GateResult(gate_number=2, gate_name="G2", status=GateStatus.WARN),
        ]

        result = calculator.compute(gate_results=gates)

        # (0.75 + 0.75) / 2 = 0.75
        assert result.gate_pass_rate == Decimal("0.75")


class TestDocumentationScore:
    """Tests for documentation score factor."""

    def test_full_documentation(self):
        """Test 100% documentation score."""
        calculator = ConfidenceCalculator()

        result = calculator.compute(docs_on_file=10, docs_required=10)

        assert result.documentation_score == Decimal("1.00")

    def test_partial_documentation(self):
        """Test partial documentation score."""
        calculator = ConfidenceCalculator()

        result = calculator.compute(docs_on_file=6, docs_required=10)

        assert result.documentation_score == Decimal("0.60")
        assert any("document" in r.lower() for r in result.recommendations)

    def test_no_documentation_required(self):
        """Test when no documentation is required."""
        calculator = ConfidenceCalculator()

        result = calculator.compute(docs_on_file=0, docs_required=0)

        assert result.documentation_score == Decimal("1.00")


class TestOverallConfidence:
    """Tests for overall confidence calculation."""

    def test_perfect_confidence(self):
        """Test perfect confidence score."""
        calculator = ConfidenceCalculator()
        citation_quality = MockCitationQuality(coverage_ratio=Decimal("1.00"))
        gates = [
            GateResult(gate_number=1, gate_name="G1", status=GateStatus.PASS),
            GateResult(gate_number=2, gate_name="G2", status=GateStatus.PASS),
            GateResult(gate_number=3, gate_name="G3", status=GateStatus.PASS),
            GateResult(gate_number=4, gate_name="G4", status=GateStatus.PASS),
        ]

        result = calculator.compute(
            citation_quality=citation_quality,
            gate_results=gates,
            evidence_anchored=5,
            total_evidence=5,
            docs_on_file=10,
            docs_required=10,
            auto_archive=True
        )

        assert result.overall_confidence == Decimal("1.00")
        assert result.auto_archive_eligible is True

    def test_mixed_confidence(self):
        """Test mixed confidence score."""
        calculator = ConfidenceCalculator()
        citation_quality = MockCitationQuality(coverage_ratio=Decimal("0.80"))
        gates = [
            GateResult(gate_number=1, gate_name="G1", status=GateStatus.PASS),
            GateResult(gate_number=2, gate_name="G2", status=GateStatus.WARN),
        ]

        result = calculator.compute(
            citation_quality=citation_quality,
            gate_results=gates,
            evidence_anchored=3,
            total_evidence=5,
            docs_on_file=6,
            docs_required=10,
        )

        # Should be between 0 and 1
        assert Decimal("0") < result.overall_confidence < Decimal("1")
        assert result.auto_archive_eligible is False

    def test_auto_archive_threshold(self):
        """Test auto-archive eligibility threshold."""
        config = ConfidenceConfig()
        config.auto_archive_threshold = Decimal("0.90")
        calculator = ConfidenceCalculator(config)

        citation_quality = MockCitationQuality(coverage_ratio=Decimal("1.00"))
        gates = [
            GateResult(gate_number=1, gate_name="G1", status=GateStatus.PASS),
        ]

        # High confidence but below threshold
        result = calculator.compute(
            citation_quality=citation_quality,
            gate_results=gates,
            evidence_anchored=4,
            total_evidence=5,
            docs_on_file=8,
            docs_required=10,
            auto_archive=True
        )

        # Even with auto_archive=True, if confidence < threshold, not eligible
        # Also needs 100% gate pass rate


class TestConvenienceFunction:
    """Tests for compute_confidence convenience function."""

    def test_compute_confidence_function(self):
        """Test the convenience function."""
        result = compute_confidence(
            evidence_anchored=5,
            total_evidence=5,
            docs_on_file=10,
            docs_required=10,
        )

        assert isinstance(result, ConfidenceResult)
        assert result.overall_confidence >= Decimal("0")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
