"""
Tests for DecisionGraph Gates Module (v2.0)

Tests cover:
- Gate configuration loading
- Gate 1: Contextual Typology evaluation
- Gate 2: Inherent Risks + Mitigating Factors evaluation
- Gate 3: Residual Risk Calculation evaluation
- Gate 4: Integrity Audit evaluation
- Full gate evaluation workflow
"""

import pytest
from decimal import Decimal
from dataclasses import dataclass
from typing import List, Optional

from decisiongraph.gates import (
    # Exceptions
    GateError,
    GateConfigError,
    GateEvaluationError,
    # Enums
    GateStatus,
    GateNumber,
    # Result
    GateResult,
    # Configuration
    TypologyGateConfig,
    InherentMitigatingGateConfig,
    ResidualRiskGateConfig,
    IntegrityAuditGateConfig,
    GateConfig,
    # Evaluator
    GateEvaluator,
)


# =============================================================================
# MOCK CLASSES
# =============================================================================

@dataclass
class MockCaseType:
    value: str = "aml_alert"


@dataclass
class MockCaseMeta:
    id: str = "CASE-001"
    case_type: MockCaseType = None

    def __post_init__(self):
        if self.case_type is None:
            self.case_type = MockCaseType()


@dataclass
class MockCaseBundle:
    meta: MockCaseMeta = None

    def __post_init__(self):
        if self.meta is None:
            self.meta = MockCaseMeta()


@dataclass
class MockFact:
    object: dict


@dataclass
class MockCell:
    fact: MockFact
    cell_id: str = "cell_123"


@dataclass
class MockEvalResult:
    signals: List[MockCell] = None
    mitigations: List[MockCell] = None
    score: Optional[MockCell] = None
    verdict: Optional[MockCell] = None

    def __post_init__(self):
        if self.signals is None:
            self.signals = []
        if self.mitigations is None:
            self.mitigations = []


@dataclass
class MockValidation:
    is_valid: bool = True


class MockChain:
    def validate(self):
        return MockValidation()


class MockInvalidChain:
    def validate(self):
        return MockValidation(is_valid=False)


# =============================================================================
# GATE STATUS TESTS
# =============================================================================

class TestGateStatus:
    """Tests for GateStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert GateStatus.PASS == "PASS"
        assert GateStatus.WARN == "WARN"
        assert GateStatus.FAIL == "FAIL"
        assert GateStatus.SKIP == "SKIP"


# =============================================================================
# GATE RESULT TESTS
# =============================================================================

class TestGateResult:
    """Tests for GateResult."""

    def test_gate_result_creation(self):
        """Test creating a gate result."""
        result = GateResult(
            gate_number=1,
            gate_name="Test Gate",
            status=GateStatus.PASS,
            details={"key": "value"}
        )

        assert result.gate_number == 1
        assert result.gate_name == "Test Gate"
        assert result.status == GateStatus.PASS
        assert result.details["key"] == "value"

    def test_gate_result_passed_property(self):
        """Test passed property."""
        result = GateResult(
            gate_number=1,
            gate_name="Test",
            status=GateStatus.PASS
        )
        assert result.passed is True

        result2 = GateResult(
            gate_number=1,
            gate_name="Test",
            status=GateStatus.FAIL
        )
        assert result2.passed is False

    def test_gate_result_failed_property(self):
        """Test failed property."""
        result = GateResult(
            gate_number=1,
            gate_name="Test",
            status=GateStatus.FAIL
        )
        assert result.failed is True

    def test_gate_result_to_dict(self):
        """Test serialization."""
        result = GateResult(
            gate_number=1,
            gate_name="Test Gate",
            status=GateStatus.WARN,
            details={"count": 5},
            warnings=["Warning 1"],
            failures=[]
        )

        d = result.to_dict()
        assert d["gate_number"] == 1
        assert d["gate_name"] == "Test Gate"
        assert d["status"] == "WARN"
        assert d["warnings"] == ["Warning 1"]


# =============================================================================
# GATE CONFIG TESTS
# =============================================================================

class TestGateConfig:
    """Tests for GateConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = GateConfig()

        assert config.gate_1.name == "Contextual Typology"
        assert config.gate_2.name == "Inherent Risks + Mitigating Factors"
        assert config.gate_3.name == "Residual Risk Calculation"
        assert config.gate_4.name == "Integrity Audit"

    def test_from_pack_empty(self):
        """Test loading config from empty pack data."""
        config = GateConfig.from_pack({})

        assert config.gate_1.name == "Contextual Typology"
        assert "TECH_INVESTMENT" in config.gate_1.typology_classes

    def test_from_pack_with_gates(self):
        """Test loading config from pack with gate definitions."""
        pack_data = {
            "gates": {
                "gate_1_typology": {
                    "name": "Custom Typology",
                    "typology_classes": ["CUSTOM_TYPE"],
                    "forbidden_typologies": ["FORBIDDEN_TYPE"],
                },
                "gate_3_residual": {
                    "low_risk_threshold": "0.25",
                    "high_risk_threshold": "0.80",
                }
            }
        }

        config = GateConfig.from_pack(pack_data)

        assert config.gate_1.name == "Custom Typology"
        assert config.gate_1.typology_classes == ["CUSTOM_TYPE"]
        assert config.gate_1.forbidden_typologies == ["FORBIDDEN_TYPE"]
        assert config.gate_3.low_risk_threshold == "0.25"
        assert config.gate_3.high_risk_threshold == "0.80"

    def test_to_dict(self):
        """Test config serialization."""
        config = GateConfig()
        d = config.to_dict()

        assert "gate_1_typology" in d
        assert "gate_2_inherent_mitigating" in d
        assert "gate_3_residual" in d
        assert "gate_4_integrity" in d


# =============================================================================
# GATE EVALUATOR TESTS
# =============================================================================

class TestGateEvaluator:
    """Tests for GateEvaluator."""

    def test_default_evaluator(self):
        """Test creating evaluator with defaults."""
        evaluator = GateEvaluator()
        assert evaluator.config is not None

    def test_custom_config_evaluator(self):
        """Test creating evaluator with custom config."""
        config = GateConfig()
        config.gate_1.forbidden_typologies = ["CUSTOM_FORBIDDEN"]

        evaluator = GateEvaluator(config)
        assert "CUSTOM_FORBIDDEN" in evaluator.config.gate_1.forbidden_typologies


class TestGate1Evaluation:
    """Tests for Gate 1: Contextual Typology."""

    def test_gate_1_pass(self):
        """Test Gate 1 passes for valid typology."""
        evaluator = GateEvaluator()
        case = MockCaseBundle()

        result = evaluator.evaluate_gate_1(case, "TECH_INVESTMENT")

        assert result.status == GateStatus.PASS
        assert result.details["typology"] == "TECH_INVESTMENT"
        assert result.details["forbidden"] is False

    def test_gate_1_fail_forbidden(self):
        """Test Gate 1 fails for forbidden typology."""
        config = GateConfig()
        config.gate_1.forbidden_typologies = ["TERRORISM_FINANCING"]
        evaluator = GateEvaluator(config)

        case = MockCaseBundle()
        result = evaluator.evaluate_gate_1(case, "TERRORISM_FINANCING")

        assert result.status == GateStatus.FAIL
        assert result.details["forbidden"] is True
        assert len(result.failures) > 0

    def test_gate_1_default_typology(self):
        """Test Gate 1 uses default when none detected."""
        evaluator = GateEvaluator()

        result = evaluator.evaluate_gate_1(None, None)

        assert result.status == GateStatus.PASS
        assert result.details["typology"] == "UNKNOWN"
        assert len(result.warnings) > 0


class TestGate2Evaluation:
    """Tests for Gate 2: Inherent Risks + Mitigating Factors."""

    def test_gate_2_pass_no_signals(self):
        """Test Gate 2 passes with no signals."""
        evaluator = GateEvaluator()
        eval_result = MockEvalResult()

        result = evaluator.evaluate_gate_2(eval_result)

        assert result.status == GateStatus.PASS
        assert result.details["signals_count"] == 0

    def test_gate_2_pass_with_signals(self):
        """Test Gate 2 passes with signals below threshold."""
        evaluator = GateEvaluator()
        eval_result = MockEvalResult(signals=[
            MockCell(fact=MockFact(object={"code": "SIG_1"})),
            MockCell(fact=MockFact(object={"code": "SIG_2"})),
        ])

        result = evaluator.evaluate_gate_2(eval_result)

        assert result.status == GateStatus.PASS
        assert result.details["signals_count"] == 2

    def test_gate_2_warn_high_signals(self):
        """Test Gate 2 warns with high signal count."""
        config = GateConfig()
        config.gate_2.high_signal_threshold = 3
        evaluator = GateEvaluator(config)

        eval_result = MockEvalResult(signals=[
            MockCell(fact=MockFact(object={"code": "SIG_1"})),
            MockCell(fact=MockFact(object={"code": "SIG_2"})),
            MockCell(fact=MockFact(object={"code": "SIG_3"})),
            MockCell(fact=MockFact(object={"code": "SIG_4"})),
        ])

        result = evaluator.evaluate_gate_2(eval_result)

        assert result.status == GateStatus.WARN
        assert len(result.warnings) > 0


class TestGate3Evaluation:
    """Tests for Gate 3: Residual Risk Calculation."""

    def test_gate_3_pass_low_risk(self):
        """Test Gate 3 passes for low risk score."""
        evaluator = GateEvaluator()

        result = evaluator.evaluate_gate_3(None, Decimal("0.10"))

        assert result.status == GateStatus.PASS
        assert result.details["risk_level"] == "LOW"

    def test_gate_3_warn_medium_risk(self):
        """Test Gate 3 warns for medium risk score."""
        evaluator = GateEvaluator()

        result = evaluator.evaluate_gate_3(None, Decimal("0.50"))

        assert result.status == GateStatus.WARN
        assert result.details["risk_level"] == "MEDIUM"

    def test_gate_3_warn_high_risk(self):
        """Test Gate 3 warns for high risk score."""
        evaluator = GateEvaluator()

        result = evaluator.evaluate_gate_3(None, Decimal("0.90"))

        assert result.status == GateStatus.WARN
        assert result.details["risk_level"] == "HIGH"

    def test_gate_3_custom_thresholds(self):
        """Test Gate 3 with custom thresholds."""
        config = GateConfig()
        config.gate_3.low_risk_threshold = "0.20"
        config.gate_3.high_risk_threshold = "0.60"
        evaluator = GateEvaluator(config)

        # 0.25 is between 0.20 and 0.60, so MEDIUM
        result = evaluator.evaluate_gate_3(None, Decimal("0.25"))

        assert result.details["risk_level"] == "MEDIUM"


class TestGate4Evaluation:
    """Tests for Gate 4: Integrity Audit."""

    def test_gate_4_pass_valid_chain(self):
        """Test Gate 4 passes with valid chain."""
        evaluator = GateEvaluator()
        chain = MockChain()

        result = evaluator.evaluate_gate_4(None, chain)

        assert result.status == GateStatus.PASS
        assert result.details["check_results"]["chain_integrity"] is True

    def test_gate_4_fail_invalid_chain(self):
        """Test Gate 4 fails with invalid chain."""
        evaluator = GateEvaluator()
        chain = MockInvalidChain()

        result = evaluator.evaluate_gate_4(None, chain)

        assert result.status == GateStatus.FAIL
        assert result.details["check_results"]["chain_integrity"] is False
        assert len(result.failures) > 0

    def test_gate_4_pass_no_chain(self):
        """Test Gate 4 passes with no chain (skips check)."""
        evaluator = GateEvaluator()

        result = evaluator.evaluate_gate_4(None, None)

        assert result.status == GateStatus.PASS


class TestEvaluateAll:
    """Tests for evaluate_all method."""

    def test_evaluate_all_returns_4_results(self):
        """Test evaluate_all returns 4 gate results."""
        evaluator = GateEvaluator()
        case = MockCaseBundle()
        eval_result = MockEvalResult()
        chain = MockChain()

        results = evaluator.evaluate_all(
            case_bundle=case,
            eval_result=eval_result,
            chain=chain,
            detected_typology="TECH_INVESTMENT",
            residual_score=Decimal("0.25")
        )

        assert len(results) == 4
        assert results[0].gate_number == GateNumber.TYPOLOGY
        assert results[1].gate_number == GateNumber.INHERENT_MITIGATING
        assert results[2].gate_number == GateNumber.RESIDUAL_RISK
        assert results[3].gate_number == GateNumber.INTEGRITY_AUDIT

    def test_overall_status_all_pass(self):
        """Test overall status when all pass."""
        evaluator = GateEvaluator()
        results = [
            GateResult(gate_number=1, gate_name="G1", status=GateStatus.PASS),
            GateResult(gate_number=2, gate_name="G2", status=GateStatus.PASS),
            GateResult(gate_number=3, gate_name="G3", status=GateStatus.PASS),
            GateResult(gate_number=4, gate_name="G4", status=GateStatus.PASS),
        ]

        assert evaluator.overall_status(results) == GateStatus.PASS

    def test_overall_status_one_warn(self):
        """Test overall status when one warns."""
        evaluator = GateEvaluator()
        results = [
            GateResult(gate_number=1, gate_name="G1", status=GateStatus.PASS),
            GateResult(gate_number=2, gate_name="G2", status=GateStatus.WARN),
            GateResult(gate_number=3, gate_name="G3", status=GateStatus.PASS),
            GateResult(gate_number=4, gate_name="G4", status=GateStatus.PASS),
        ]

        assert evaluator.overall_status(results) == GateStatus.WARN

    def test_overall_status_one_fail(self):
        """Test overall status when one fails."""
        evaluator = GateEvaluator()
        results = [
            GateResult(gate_number=1, gate_name="G1", status=GateStatus.PASS),
            GateResult(gate_number=2, gate_name="G2", status=GateStatus.PASS),
            GateResult(gate_number=3, gate_name="G3", status=GateStatus.FAIL),
            GateResult(gate_number=4, gate_name="G4", status=GateStatus.PASS),
        ]

        assert evaluator.overall_status(results) == GateStatus.FAIL


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
