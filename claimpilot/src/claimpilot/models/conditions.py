"""
ClaimPilot Composable Conditions

Provides three-valued logic (TriBool) and composable condition trees
for evaluating coverage rules, exclusions, and evidence requirements.

Key components:
- TriBool: Three-valued logic (TRUE, FALSE, UNKNOWN) with Kleene algebra
- Predicate: Leaf-level comparison against facts
- Condition: Composable AND/OR/NOT tree structure
- Helper functions: AND(), OR(), NOT(), PRED() for building conditions

Truth Tables (Kleene Logic):
    AND: False dominates, Unknown propagates
    OR: True dominates, Unknown propagates
    NOT: Unknown stays Unknown
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from kernel.evidence.tribool import TriBool  # noqa: F401 — re-exported

from .enums import ConditionOperator


# =============================================================================
# Evaluation Result
# =============================================================================

@dataclass
class EvaluationResult:
    """
    Result of evaluating a condition.

    Includes the TriBool result plus metadata about what was evaluated
    and what facts were missing (if result is UNKNOWN).
    """
    value: TriBool
    explanation: str
    missing_fact_keys: list[str] = field(default_factory=list)
    evaluated_predicates: list[str] = field(default_factory=list)
    supporting_fact_ids: list[str] = field(default_factory=list)

    @property
    def is_satisfied(self) -> bool:
        """Check if condition is satisfied (TRUE)."""
        return self.value == TriBool.TRUE

    @property
    def is_not_satisfied(self) -> bool:
        """Check if condition is not satisfied (FALSE)."""
        return self.value == TriBool.FALSE

    @property
    def is_uncertain(self) -> bool:
        """Check if result is uncertain (UNKNOWN)."""
        return self.value == TriBool.UNKNOWN

    def __and__(self, other: EvaluationResult) -> EvaluationResult:
        """Combine two results with AND logic."""
        return EvaluationResult(
            value=self.value & other.value,
            explanation=f"({self.explanation}) AND ({other.explanation})",
            missing_fact_keys=list(set(self.missing_fact_keys + other.missing_fact_keys)),
            evaluated_predicates=self.evaluated_predicates + other.evaluated_predicates,
            supporting_fact_ids=list(set(self.supporting_fact_ids + other.supporting_fact_ids)),
        )

    def __or__(self, other: EvaluationResult) -> EvaluationResult:
        """Combine two results with OR logic."""
        return EvaluationResult(
            value=self.value | other.value,
            explanation=f"({self.explanation}) OR ({other.explanation})",
            missing_fact_keys=list(set(self.missing_fact_keys + other.missing_fact_keys)),
            evaluated_predicates=self.evaluated_predicates + other.evaluated_predicates,
            supporting_fact_ids=list(set(self.supporting_fact_ids + other.supporting_fact_ids)),
        )

    def __invert__(self) -> EvaluationResult:
        """Negate the result with NOT logic."""
        return EvaluationResult(
            value=~self.value,
            explanation=f"NOT ({self.explanation})",
            missing_fact_keys=self.missing_fact_keys.copy(),
            evaluated_predicates=self.evaluated_predicates.copy(),
            supporting_fact_ids=self.supporting_fact_ids.copy(),
        )


# =============================================================================
# Predicate (Leaf Condition)
# =============================================================================

@dataclass
class Predicate:
    """
    A leaf-level comparison in a condition tree.

    Predicates compare a field from the claim context against a value
    using a comparison operator.

    Attributes:
        field: Dot-notation path to field (e.g., "claim.vehicle.use_type")
        operator: Comparison operator (eq, ne, gt, lt, in, etc.)
        value: Value to compare against
        description: Optional human-readable description
    """
    field: str
    operator: ConditionOperator
    value: Any
    description: Optional[str] = None

    def __post_init__(self) -> None:
        # Validate operator is a comparison operator, not logical
        logical_ops = {ConditionOperator.AND, ConditionOperator.OR, ConditionOperator.NOT}
        if self.operator in logical_ops:
            raise ValueError(
                f"Predicate cannot use logical operator '{self.operator}'. "
                f"Use Condition for AND/OR/NOT."
            )

    @property
    def field_path(self) -> list[str]:
        """Split field into path components."""
        return self.field.split(".")


# =============================================================================
# Condition (Composable Tree)
# =============================================================================

@dataclass
class Condition:
    """
    A composable condition that can be nested (AND/OR/NOT).

    For logical operators (AND, OR, NOT), use `children`.
    For comparison operators, use `predicate`.

    Examples:
        # Simple predicate
        Condition(
            op=ConditionOperator.EQ,
            predicate=Predicate("claim.status", ConditionOperator.EQ, "open")
        )

        # AND composition
        Condition(
            op=ConditionOperator.AND,
            children=[condition1, condition2]
        )

        # NOT
        Condition(
            op=ConditionOperator.NOT,
            children=[condition_to_negate]
        )
    """
    op: ConditionOperator

    # For logical composition (AND, OR, NOT)
    children: list[Condition] = field(default_factory=list)

    # For leaf predicates (comparisons)
    predicate: Optional[Predicate] = None

    # Optional metadata
    id: Optional[str] = None
    description: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate condition structure."""
        logical_ops = {ConditionOperator.AND, ConditionOperator.OR, ConditionOperator.NOT}

        if self.op in logical_ops:
            # Logical operators require children
            if not self.children:
                raise ValueError(f"Logical operator '{self.op}' requires children")
            if self.predicate is not None:
                raise ValueError(f"Logical operator '{self.op}' cannot have predicate")
            if self.op == ConditionOperator.NOT and len(self.children) != 1:
                raise ValueError("NOT operator must have exactly one child")
        else:
            # Comparison operators require predicate
            if self.predicate is None:
                raise ValueError(f"Comparison operator '{self.op}' requires predicate")
            if self.children:
                raise ValueError(f"Comparison operator '{self.op}' cannot have children")

    @property
    def is_logical(self) -> bool:
        """Check if this is a logical operation (AND/OR/NOT)."""
        return self.op in {ConditionOperator.AND, ConditionOperator.OR, ConditionOperator.NOT}

    @property
    def is_leaf(self) -> bool:
        """Check if this is a leaf predicate."""
        return not self.is_logical


# =============================================================================
# Condition Definition (Named, Reusable)
# =============================================================================

@dataclass
class ConditionDefinition:
    """
    A named, reusable condition definition.

    Used in policy packs to define conditions that can be referenced
    by coverages, exclusions, and other rules.
    """
    id: str
    name: str
    description: str
    condition: Condition


# =============================================================================
# Helper Functions for Building Conditions
# =============================================================================

def AND(*conditions: Condition) -> Condition:
    """
    Create an AND condition from multiple child conditions.

    Example:
        condition = AND(
            PRED("claim.amount", ConditionOperator.GT, 1000),
            PRED("claim.status", ConditionOperator.EQ, "open")
        )
    """
    return Condition(
        op=ConditionOperator.AND,
        children=list(conditions),
        description=f"AND of {len(conditions)} conditions",
    )


def OR(*conditions: Condition) -> Condition:
    """
    Create an OR condition from multiple child conditions.

    Example:
        condition = OR(
            PRED("claim.type", ConditionOperator.EQ, "collision"),
            PRED("claim.type", ConditionOperator.EQ, "comprehensive")
        )
    """
    return Condition(
        op=ConditionOperator.OR,
        children=list(conditions),
        description=f"OR of {len(conditions)} conditions",
    )


def NOT(condition: Condition) -> Condition:
    """
    Create a NOT condition (negation).

    Example:
        condition = NOT(
            PRED("claim.fraud_flag", ConditionOperator.EQ, True)
        )
    """
    return Condition(
        op=ConditionOperator.NOT,
        children=[condition],
        description=f"NOT ({condition.description or 'condition'})",
    )


def PRED(
    field: str,
    operator: ConditionOperator,
    value: Any,
    description: Optional[str] = None,
) -> Condition:
    """
    Create a predicate condition (leaf).

    Example:
        condition = PRED("claim.amount", ConditionOperator.GTE, 5000)
    """
    predicate = Predicate(
        field=field,
        operator=operator,
        value=value,
        description=description,
    )
    return Condition(
        op=operator,
        predicate=predicate,
        description=description or f"{field} {operator.value} {value}",
    )


# =============================================================================
# Convenience Predicate Builders
# =============================================================================

def EQ(field: str, value: Any, description: Optional[str] = None) -> Condition:
    """Create an equality predicate: field == value"""
    return PRED(field, ConditionOperator.EQ, value, description)


def NE(field: str, value: Any, description: Optional[str] = None) -> Condition:
    """Create a not-equal predicate: field != value"""
    return PRED(field, ConditionOperator.NE, value, description)


def GT(field: str, value: Any, description: Optional[str] = None) -> Condition:
    """Create a greater-than predicate: field > value"""
    return PRED(field, ConditionOperator.GT, value, description)


def GTE(field: str, value: Any, description: Optional[str] = None) -> Condition:
    """Create a greater-than-or-equal predicate: field >= value"""
    return PRED(field, ConditionOperator.GTE, value, description)


def LT(field: str, value: Any, description: Optional[str] = None) -> Condition:
    """Create a less-than predicate: field < value"""
    return PRED(field, ConditionOperator.LT, value, description)


def LTE(field: str, value: Any, description: Optional[str] = None) -> Condition:
    """Create a less-than-or-equal predicate: field <= value"""
    return PRED(field, ConditionOperator.LTE, value, description)


def IN(field: str, values: list[Any], description: Optional[str] = None) -> Condition:
    """Create an IN predicate: field in [values]"""
    return PRED(field, ConditionOperator.IN, values, description)


def NOT_IN(field: str, values: list[Any], description: Optional[str] = None) -> Condition:
    """Create a NOT IN predicate: field not in [values]"""
    return PRED(field, ConditionOperator.NOT_IN, values, description)


def IS_NULL(field: str, description: Optional[str] = None) -> Condition:
    """Create an IS NULL predicate: field is None"""
    return PRED(field, ConditionOperator.IS_NULL, None, description)


def IS_NOT_NULL(field: str, description: Optional[str] = None) -> Condition:
    """Create an IS NOT NULL predicate: field is not None"""
    return PRED(field, ConditionOperator.IS_NOT_NULL, None, description)


def CONTAINS(field: str, value: Any, description: Optional[str] = None) -> Condition:
    """Create a CONTAINS predicate: value in field (for strings/lists)"""
    return PRED(field, ConditionOperator.CONTAINS, value, description)


def BETWEEN(
    field: str,
    low: Any,
    high: Any,
    description: Optional[str] = None,
) -> Condition:
    """Create a BETWEEN predicate: low <= field <= high"""
    return PRED(field, ConditionOperator.BETWEEN, (low, high), description)
