"""
Tests for ClaimPilot Condition Evaluator

Tests cover:
- Field path resolution
- Comparison operators
- TriBool evaluation with Kleene logic
- Missing fact tracking
- Nested condition evaluation
"""
import pytest
from datetime import date
from decimal import Decimal

from claimpilot.models import (
    Condition,
    ConditionOperator,
    Predicate,
    TriBool,
)
from claimpilot.engine.condition_evaluator import (
    ConditionEvaluator,
    check_condition,
    compare_values,
    evaluate_condition,
    get_fact_value,
    resolve_field_path,
)

from tests.conftest import make_claim_context, make_fact, make_condition


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def basic_context():
    """Create a basic claim context for testing."""
    return make_claim_context(
        facts={
            "claim_amount": make_fact("claim_amount", 25000),
            "vehicle_use": make_fact("vehicle_use", "personal"),
            "fault_percentage": make_fact("fault_percentage", 30),
            "is_total_loss": make_fact("is_total_loss", False),
        },
        metadata={
            "jurisdiction": "CA-ON",
            "adjuster_id": "ADJ-123",
        },
    )


@pytest.fixture
def evaluator():
    """Create a condition evaluator."""
    return ConditionEvaluator()


# =============================================================================
# Field Path Resolution Tests
# =============================================================================

class TestFieldPathResolution:
    """Tests for resolve_field_path function."""

    def test_resolve_simple_attribute(self, basic_context):
        """Test resolving a simple attribute."""
        value, found = resolve_field_path(basic_context, "claim_id")
        assert found is True
        assert value == "CLM-001"

    def test_resolve_nested_attribute(self, basic_context):
        """Test resolving nested attributes."""
        value, found = resolve_field_path(basic_context, "report_date")
        assert found is True
        assert value == date(2024, 6, 15)

    def test_resolve_from_facts(self, basic_context):
        """Test resolving from facts dictionary."""
        value, found = resolve_field_path(
            basic_context,
            "facts.claim_amount",
            basic_context.facts
        )
        assert found is True
        assert value == 25000

    def test_resolve_from_metadata(self, basic_context):
        """Test resolving from metadata."""
        value, found = resolve_field_path(basic_context, "metadata.jurisdiction")
        assert found is True
        assert value == "CA-ON"

    def test_resolve_missing_path(self, basic_context):
        """Test resolving a missing path."""
        value, found = resolve_field_path(basic_context, "nonexistent.field")
        assert found is False
        assert value is None

    def test_get_fact_value_direct(self, basic_context):
        """Test getting fact value directly."""
        value, found, fact_id = get_fact_value(basic_context, "claim_amount")
        assert found is True
        assert value == 25000
        assert fact_id is not None

    def test_get_fact_value_missing(self, basic_context):
        """Test getting missing fact value."""
        value, found, fact_id = get_fact_value(basic_context, "missing_fact")
        assert found is False
        assert value is None
        assert fact_id is None


# =============================================================================
# Comparison Operator Tests
# =============================================================================

class TestCompareValues:
    """Tests for compare_values function."""

    def test_eq_true(self):
        """Test equality comparison - true."""
        result = compare_values("personal", ConditionOperator.EQ, "personal")
        assert result == TriBool.TRUE

    def test_eq_false(self):
        """Test equality comparison - false."""
        result = compare_values("personal", ConditionOperator.EQ, "commercial")
        assert result == TriBool.FALSE

    def test_ne_true(self):
        """Test not equal comparison - true."""
        result = compare_values("personal", ConditionOperator.NE, "commercial")
        assert result == TriBool.TRUE

    def test_gt_true(self):
        """Test greater than comparison - true."""
        result = compare_values(100, ConditionOperator.GT, 50)
        assert result == TriBool.TRUE

    def test_gt_false(self):
        """Test greater than comparison - false."""
        result = compare_values(50, ConditionOperator.GT, 100)
        assert result == TriBool.FALSE

    def test_gte_equal(self):
        """Test greater than or equal - equal case."""
        result = compare_values(100, ConditionOperator.GTE, 100)
        assert result == TriBool.TRUE

    def test_lt_true(self):
        """Test less than comparison - true."""
        result = compare_values(50, ConditionOperator.LT, 100)
        assert result == TriBool.TRUE

    def test_in_true(self):
        """Test IN operator - true."""
        result = compare_values("collision", ConditionOperator.IN, ["collision", "theft"])
        assert result == TriBool.TRUE

    def test_in_false(self):
        """Test IN operator - false."""
        result = compare_values("vandalism", ConditionOperator.IN, ["collision", "theft"])
        assert result == TriBool.FALSE

    def test_contains_string(self):
        """Test CONTAINS with strings."""
        result = compare_values("collision damage", ConditionOperator.CONTAINS, "collision")
        assert result == TriBool.TRUE

    def test_starts_with(self):
        """Test STARTS_WITH operator."""
        result = compare_values("CA-ON-AUTO", ConditionOperator.STARTS_WITH, "CA-ON")
        assert result == TriBool.TRUE

    def test_between_true(self):
        """Test BETWEEN operator - true."""
        result = compare_values(75, ConditionOperator.BETWEEN, (50, 100))
        assert result == TriBool.TRUE

    def test_is_null_true(self):
        """Test IS_NULL - true."""
        result = compare_values(None, ConditionOperator.IS_NULL, None)
        assert result == TriBool.TRUE

    def test_is_not_null_true(self):
        """Test IS_NOT_NULL - true."""
        result = compare_values("value", ConditionOperator.IS_NOT_NULL, None)
        assert result == TriBool.TRUE

    def test_null_comparison_unknown(self):
        """Test comparison with null returns UNKNOWN."""
        result = compare_values(None, ConditionOperator.GT, 100)
        assert result == TriBool.UNKNOWN


# =============================================================================
# Condition Evaluator Tests
# =============================================================================

class TestConditionEvaluator:
    """Tests for ConditionEvaluator class."""

    def test_evaluate_simple_predicate_true(self, evaluator, basic_context):
        """Test evaluating a simple predicate that is true."""
        condition = make_condition(
            op=ConditionOperator.EQ,
            field="vehicle_use",
            value="personal",
        )
        result = evaluator.evaluate(condition, basic_context)
        assert result.value == TriBool.TRUE

    def test_evaluate_simple_predicate_false(self, evaluator, basic_context):
        """Test evaluating a simple predicate that is false."""
        condition = make_condition(
            op=ConditionOperator.EQ,
            field="vehicle_use",
            value="commercial",
        )
        result = evaluator.evaluate(condition, basic_context)
        assert result.value == TriBool.FALSE

    def test_evaluate_missing_fact_unknown(self, evaluator, basic_context):
        """Test evaluating with missing fact returns UNKNOWN."""
        condition = make_condition(
            op=ConditionOperator.EQ,
            field="missing_fact",
            value="something",
        )
        result = evaluator.evaluate(condition, basic_context)
        assert result.value == TriBool.UNKNOWN
        assert "missing_fact" in result.missing_fact_keys

    def test_evaluate_and_all_true(self, evaluator, basic_context):
        """Test AND with all true children."""
        condition = make_condition(
            op=ConditionOperator.AND,
            children=[
                make_condition(
                    id="c1",
                    op=ConditionOperator.EQ,
                    field="vehicle_use",
                    value="personal",
                ),
                make_condition(
                    id="c2",
                    op=ConditionOperator.LT,
                    field="fault_percentage",
                    value=50,
                ),
            ],
        )
        result = evaluator.evaluate(condition, basic_context)
        assert result.value == TriBool.TRUE

    def test_evaluate_and_one_false(self, evaluator, basic_context):
        """Test AND with one false child."""
        condition = make_condition(
            op=ConditionOperator.AND,
            children=[
                make_condition(
                    id="c1",
                    op=ConditionOperator.EQ,
                    field="vehicle_use",
                    value="personal",
                ),
                make_condition(
                    id="c2",
                    op=ConditionOperator.GT,
                    field="fault_percentage",
                    value=50,  # fault_percentage is 30, so this is false
                ),
            ],
        )
        result = evaluator.evaluate(condition, basic_context)
        assert result.value == TriBool.FALSE

    def test_evaluate_and_with_unknown(self, evaluator, basic_context):
        """Test AND with unknown (missing fact)."""
        condition = make_condition(
            op=ConditionOperator.AND,
            children=[
                make_condition(
                    id="c1",
                    op=ConditionOperator.EQ,
                    field="vehicle_use",
                    value="personal",
                ),
                make_condition(
                    id="c2",
                    op=ConditionOperator.EQ,
                    field="missing_fact",
                    value="something",
                ),
            ],
        )
        result = evaluator.evaluate(condition, basic_context)
        assert result.value == TriBool.UNKNOWN

    def test_evaluate_or_one_true(self, evaluator, basic_context):
        """Test OR with one true child."""
        condition = make_condition(
            op=ConditionOperator.OR,
            children=[
                make_condition(
                    id="c1",
                    op=ConditionOperator.EQ,
                    field="vehicle_use",
                    value="commercial",  # false
                ),
                make_condition(
                    id="c2",
                    op=ConditionOperator.LT,
                    field="fault_percentage",
                    value=50,  # true
                ),
            ],
        )
        result = evaluator.evaluate(condition, basic_context)
        assert result.value == TriBool.TRUE

    def test_evaluate_not_true(self, evaluator, basic_context):
        """Test NOT of false is true."""
        condition = make_condition(
            op=ConditionOperator.NOT,
            children=[
                make_condition(
                    op=ConditionOperator.EQ,
                    field="vehicle_use",
                    value="commercial",  # false
                ),
            ],
        )
        result = evaluator.evaluate(condition, basic_context)
        assert result.value == TriBool.TRUE

    def test_get_required_facts(self, evaluator):
        """Test extracting required facts from a condition."""
        condition = make_condition(
            op=ConditionOperator.AND,
            children=[
                make_condition(
                    op=ConditionOperator.EQ,
                    field="vehicle_use",
                    value="personal",
                ),
                make_condition(
                    op=ConditionOperator.OR,
                    children=[
                        make_condition(
                            op=ConditionOperator.GT,
                            field="claim_amount",
                            value=10000,
                        ),
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="is_total_loss",
                            value=True,
                        ),
                    ],
                ),
            ],
        )
        required = evaluator.get_required_facts(condition)
        assert required == {"vehicle_use", "claim_amount", "is_total_loss"}


# =============================================================================
# Convenience Function Tests
# =============================================================================

class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_evaluate_condition_function(self, basic_context):
        """Test evaluate_condition convenience function."""
        condition = make_condition(
            op=ConditionOperator.EQ,
            field="vehicle_use",
            value="personal",
        )
        result = evaluate_condition(condition, basic_context)
        assert result.value == TriBool.TRUE

    def test_check_condition_true(self, basic_context):
        """Test check_condition returns True."""
        condition = make_condition(
            op=ConditionOperator.EQ,
            field="vehicle_use",
            value="personal",
        )
        assert check_condition(condition, basic_context) is True

    def test_check_condition_false(self, basic_context):
        """Test check_condition returns False for FALSE."""
        condition = make_condition(
            op=ConditionOperator.EQ,
            field="vehicle_use",
            value="commercial",
        )
        assert check_condition(condition, basic_context) is False

    def test_check_condition_unknown_returns_false(self, basic_context):
        """Test check_condition returns False for UNKNOWN."""
        condition = make_condition(
            op=ConditionOperator.EQ,
            field="missing_fact",
            value="something",
        )
        # UNKNOWN is treated as False by check_condition
        assert check_condition(condition, basic_context) is False
