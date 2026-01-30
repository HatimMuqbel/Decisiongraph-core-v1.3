"""
ClaimPilot Condition Evaluator

Evaluates composable conditions against claim facts using three-valued logic.

Key features:
- TriBool evaluation (TRUE, FALSE, UNKNOWN)
- Field path resolution (e.g., "claim.vehicle.use_type")
- Stable evaluation order for determinism
- Tracks missing facts for UNKNOWN results
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional, Union

from ..exceptions import ConditionEvaluationError, FieldPathError
from ..models import (
    ClaimContext,
    Condition,
    ConditionOperator,
    EvaluationResult,
    Fact,
    Predicate,
    TriBool,
)


# =============================================================================
# Field Path Resolution
# =============================================================================

def resolve_field_path(
    obj: Any,
    path: str,
    facts: Optional[dict[str, Fact]] = None,
) -> tuple[Any, bool]:
    """
    Resolve a dot-notation field path to a value.

    Supports:
    - Object attributes: "claim.loss_type"
    - Dictionary keys: "metadata.custom_field"
    - Nested paths: "claim.vehicle.use_type"
    - Fact lookup: "facts.vehicle_use" (looks up in facts dict)

    Args:
        obj: The root object to resolve from
        path: Dot-notation path (e.g., "claim.vehicle.use_type")
        facts: Optional facts dictionary for fact lookups

    Returns:
        Tuple of (resolved_value, found). If not found, returns (None, False).
    """
    parts = path.split(".")
    current = obj

    for i, part in enumerate(parts):
        # Special handling for "facts" prefix
        if i == 0 and part == "facts" and facts is not None:
            if len(parts) > 1:
                fact_key = ".".join(parts[1:])
                fact = facts.get(fact_key)
                if fact is not None:
                    return (fact.value, True)
                # Try just the next part
                fact = facts.get(parts[1])
                if fact is not None:
                    return (fact.value, True)
            return (None, False)

        # Try attribute access
        if hasattr(current, part):
            current = getattr(current, part)
        # Try dictionary access
        elif isinstance(current, dict):
            if part in current:
                current = current[part]
            else:
                return (None, False)
        # Try facts dictionary if at root level
        elif i == 0 and facts is not None and part in facts:
            current = facts[part].value
        else:
            return (None, False)

    return (current, True)


def get_fact_value(
    context: ClaimContext,
    field: str,
) -> tuple[Any, bool, Optional[str]]:
    """
    Get a fact value from the claim context.

    Tries multiple resolution strategies:
    1. Direct fact lookup by field name
    2. Field path resolution on context object
    3. Metadata lookup

    Args:
        context: The claim context
        field: Field name or path

    Returns:
        Tuple of (value, found, fact_id). fact_id is set if from a Fact object.
    """
    # Try direct fact lookup first
    if field in context.facts:
        fact = context.facts[field]
        return (fact.value, True, fact.id)

    # Try resolving on the context object
    value, found = resolve_field_path(context, field, context.facts)
    if found:
        return (value, True, None)

    # Try metadata
    if field in context.metadata:
        return (context.metadata[field], True, None)

    return (None, False, None)


# =============================================================================
# Comparison Operators
# =============================================================================

def compare_values(
    actual: Any,
    operator: ConditionOperator,
    expected: Any,
) -> TriBool:
    """
    Compare two values using the specified operator.

    Args:
        actual: The actual value from the claim
        operator: Comparison operator
        expected: The expected value to compare against

    Returns:
        TriBool result of the comparison
    """
    # Handle null checks first
    if operator == ConditionOperator.IS_NULL:
        return TriBool.TRUE if actual is None else TriBool.FALSE

    if operator == ConditionOperator.IS_NOT_NULL:
        return TriBool.TRUE if actual is not None else TriBool.FALSE

    # If actual is None for other operators, we can't compare
    if actual is None:
        return TriBool.UNKNOWN

    # Handle empty checks
    if operator == ConditionOperator.IS_EMPTY:
        if isinstance(actual, (str, list, dict, set)):
            return TriBool.TRUE if len(actual) == 0 else TriBool.FALSE
        return TriBool.FALSE

    if operator == ConditionOperator.IS_NOT_EMPTY:
        if isinstance(actual, (str, list, dict, set)):
            return TriBool.TRUE if len(actual) > 0 else TriBool.FALSE
        return TriBool.TRUE

    # Type coercion for numeric comparisons
    if operator in {
        ConditionOperator.GT, ConditionOperator.GTE,
        ConditionOperator.LT, ConditionOperator.LTE,
        ConditionOperator.BETWEEN,
    }:
        actual = _coerce_numeric(actual)
        if isinstance(expected, tuple):
            expected = tuple(_coerce_numeric(v) for v in expected)
        else:
            expected = _coerce_numeric(expected)

    try:
        if operator == ConditionOperator.EQ:
            return TriBool.TRUE if actual == expected else TriBool.FALSE

        elif operator == ConditionOperator.NE:
            return TriBool.TRUE if actual != expected else TriBool.FALSE

        elif operator == ConditionOperator.GT:
            return TriBool.TRUE if actual > expected else TriBool.FALSE

        elif operator == ConditionOperator.GTE:
            return TriBool.TRUE if actual >= expected else TriBool.FALSE

        elif operator == ConditionOperator.LT:
            return TriBool.TRUE if actual < expected else TriBool.FALSE

        elif operator == ConditionOperator.LTE:
            return TriBool.TRUE if actual <= expected else TriBool.FALSE

        elif operator == ConditionOperator.IN:
            if isinstance(expected, (list, tuple, set, frozenset)):
                return TriBool.TRUE if actual in expected else TriBool.FALSE
            return TriBool.FALSE

        elif operator == ConditionOperator.NOT_IN:
            if isinstance(expected, (list, tuple, set, frozenset)):
                return TriBool.TRUE if actual not in expected else TriBool.FALSE
            return TriBool.TRUE

        elif operator == ConditionOperator.CONTAINS:
            if isinstance(actual, str) and isinstance(expected, str):
                return TriBool.TRUE if expected in actual else TriBool.FALSE
            elif isinstance(actual, (list, tuple, set)):
                return TriBool.TRUE if expected in actual else TriBool.FALSE
            return TriBool.FALSE

        elif operator == ConditionOperator.STARTS_WITH:
            if isinstance(actual, str) and isinstance(expected, str):
                return TriBool.TRUE if actual.startswith(expected) else TriBool.FALSE
            return TriBool.FALSE

        elif operator == ConditionOperator.ENDS_WITH:
            if isinstance(actual, str) and isinstance(expected, str):
                return TriBool.TRUE if actual.endswith(expected) else TriBool.FALSE
            return TriBool.FALSE

        elif operator == ConditionOperator.MATCHES:
            if isinstance(actual, str) and isinstance(expected, str):
                pattern = re.compile(expected)
                return TriBool.TRUE if pattern.search(actual) else TriBool.FALSE
            return TriBool.FALSE

        elif operator == ConditionOperator.BETWEEN:
            if isinstance(expected, (list, tuple)) and len(expected) == 2:
                low, high = expected
                return TriBool.TRUE if low <= actual <= high else TriBool.FALSE
            return TriBool.FALSE

        else:
            # Unknown operator
            return TriBool.UNKNOWN

    except (TypeError, ValueError):
        # Comparison failed (incompatible types)
        return TriBool.UNKNOWN


def _coerce_numeric(value: Any) -> Union[int, float, Decimal]:
    """Coerce a value to numeric type for comparison."""
    if isinstance(value, (int, float, Decimal)):
        return value
    if isinstance(value, str):
        try:
            if "." in value:
                return Decimal(value)
            return int(value)
        except (ValueError, TypeError):
            return value
    return value


# =============================================================================
# Condition Evaluator
# =============================================================================

@dataclass
class ConditionEvaluator:
    """
    Evaluates composable conditions against claim context.

    Supports:
    - Logical operators (AND, OR, NOT) with Kleene three-valued logic
    - Comparison operators (EQ, NE, GT, LT, IN, CONTAINS, etc.)
    - Nested conditions
    - Field path resolution
    - Missing fact tracking

    Usage:
        evaluator = ConditionEvaluator()
        result = evaluator.evaluate(condition, context)

        if result.value == TriBool.TRUE:
            print("Condition satisfied")
        elif result.value == TriBool.UNKNOWN:
            print(f"Missing facts: {result.missing_fact_keys}")
    """

    # Track evaluation for debugging
    debug: bool = False
    _evaluation_log: list[str] = field(default_factory=list)

    def evaluate(
        self,
        condition: Condition,
        context: ClaimContext,
    ) -> EvaluationResult:
        """
        Evaluate a condition against a claim context.

        Args:
            condition: The condition to evaluate
            context: The claim context with facts

        Returns:
            EvaluationResult with TriBool value and metadata
        """
        self._evaluation_log.clear()
        return self._evaluate_condition(condition, context)

    def _evaluate_condition(
        self,
        condition: Condition,
        context: ClaimContext,
    ) -> EvaluationResult:
        """Recursively evaluate a condition."""
        if condition.is_logical:
            return self._evaluate_logical(condition, context)
        else:
            return self._evaluate_predicate(condition, context)

    def _evaluate_logical(
        self,
        condition: Condition,
        context: ClaimContext,
    ) -> EvaluationResult:
        """Evaluate a logical condition (AND/OR/NOT)."""
        op = condition.op

        if op == ConditionOperator.AND:
            return self._evaluate_and(condition.children, context)
        elif op == ConditionOperator.OR:
            return self._evaluate_or(condition.children, context)
        elif op == ConditionOperator.NOT:
            child_result = self._evaluate_condition(condition.children[0], context)
            return ~child_result
        else:
            raise ConditionEvaluationError(
                message=f"Unknown logical operator: {op}",
                details={"operator": op.value},
            )

    def _evaluate_and(
        self,
        children: list[Condition],
        context: ClaimContext,
    ) -> EvaluationResult:
        """
        Evaluate AND condition with Kleene logic.

        Truth table:
        - FALSE & X = FALSE (False dominates)
        - TRUE & TRUE = TRUE
        - TRUE & UNKNOWN = UNKNOWN
        - UNKNOWN & UNKNOWN = UNKNOWN
        """
        # Sort children by ID for deterministic evaluation order
        sorted_children = sorted(
            children,
            key=lambda c: c.id or c.description or str(id(c))
        )

        result = EvaluationResult(
            value=TriBool.TRUE,
            explanation="AND",
            missing_fact_keys=[],
            evaluated_predicates=[],
            supporting_fact_ids=[],
        )

        for child in sorted_children:
            child_result = self._evaluate_condition(child, context)

            # Combine results
            result = result & child_result

            # Short-circuit on FALSE (False dominates in AND)
            if result.value == TriBool.FALSE:
                break

        return result

    def _evaluate_or(
        self,
        children: list[Condition],
        context: ClaimContext,
    ) -> EvaluationResult:
        """
        Evaluate OR condition with Kleene logic.

        Truth table:
        - TRUE | X = TRUE (True dominates)
        - FALSE | FALSE = FALSE
        - FALSE | UNKNOWN = UNKNOWN
        - UNKNOWN | UNKNOWN = UNKNOWN
        """
        # Sort children by ID for deterministic evaluation order
        sorted_children = sorted(
            children,
            key=lambda c: c.id or c.description or str(id(c))
        )

        result = EvaluationResult(
            value=TriBool.FALSE,
            explanation="OR",
            missing_fact_keys=[],
            evaluated_predicates=[],
            supporting_fact_ids=[],
        )

        for child in sorted_children:
            child_result = self._evaluate_condition(child, context)

            # Combine results
            result = result | child_result

            # Short-circuit on TRUE (True dominates in OR)
            if result.value == TriBool.TRUE:
                break

        return result

    def _evaluate_predicate(
        self,
        condition: Condition,
        context: ClaimContext,
    ) -> EvaluationResult:
        """Evaluate a leaf predicate condition."""
        predicate = condition.predicate
        if predicate is None:
            raise ConditionEvaluationError(
                message="Predicate condition missing predicate",
                details={"condition_id": condition.id},
            )

        # Get the actual value from context
        actual_value, found, fact_id = get_fact_value(context, predicate.field)

        # Build result metadata
        missing_facts: list[str] = []
        supporting_facts: list[str] = []

        if not found:
            missing_facts.append(predicate.field)

        if fact_id:
            supporting_facts.append(fact_id)

        # Compare values
        result_value = compare_values(actual_value, predicate.operator, predicate.value)

        # If not found and not a null check, result is UNKNOWN
        if not found and predicate.operator not in {
            ConditionOperator.IS_NULL,
            ConditionOperator.IS_NOT_NULL,
        }:
            result_value = TriBool.UNKNOWN

        # Build explanation
        if result_value == TriBool.TRUE:
            explanation = f"{predicate.field} {predicate.operator.value} {predicate.value}: PASSED"
        elif result_value == TriBool.FALSE:
            explanation = f"{predicate.field} {predicate.operator.value} {predicate.value}: FAILED (actual: {actual_value})"
        else:
            explanation = f"{predicate.field} {predicate.operator.value} {predicate.value}: UNKNOWN (missing fact)"

        if self.debug:
            self._evaluation_log.append(explanation)

        return EvaluationResult(
            value=result_value,
            explanation=explanation,
            missing_fact_keys=missing_facts,
            evaluated_predicates=[predicate.field],
            supporting_fact_ids=supporting_facts,
        )

    def get_required_facts(self, condition: Condition) -> set[str]:
        """
        Get all fact fields required by a condition.

        Useful for determining what facts are needed before evaluation.

        Args:
            condition: The condition to analyze

        Returns:
            Set of field names referenced by the condition
        """
        fields: set[str] = set()
        self._collect_fields(condition, fields)
        return fields

    def _collect_fields(self, condition: Condition, fields: set[str]) -> None:
        """Recursively collect field names from a condition."""
        if condition.is_logical:
            for child in condition.children:
                self._collect_fields(child, fields)
        elif condition.predicate:
            fields.add(condition.predicate.field)


# =============================================================================
# Convenience Functions
# =============================================================================

def evaluate_condition(
    condition: Condition,
    context: ClaimContext,
) -> EvaluationResult:
    """
    Evaluate a condition against a claim context.

    Convenience function that creates a temporary evaluator.

    Args:
        condition: The condition to evaluate
        context: The claim context

    Returns:
        EvaluationResult
    """
    evaluator = ConditionEvaluator()
    return evaluator.evaluate(condition, context)


def check_condition(
    condition: Condition,
    context: ClaimContext,
) -> bool:
    """
    Check if a condition is satisfied (TRUE).

    Returns False for both FALSE and UNKNOWN results.
    Use evaluate_condition() for full TriBool handling.

    Args:
        condition: The condition to evaluate
        context: The claim context

    Returns:
        True if condition is satisfied, False otherwise
    """
    result = evaluate_condition(condition, context)
    return result.value == TriBool.TRUE
