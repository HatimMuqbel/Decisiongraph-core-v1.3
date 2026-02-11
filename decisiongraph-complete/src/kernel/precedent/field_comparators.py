"""
Typed Field Comparison Functions — v3 Precedent Engine.

Implements the five comparison primitives from spec Section 5.3:
  EXACT, EQUIVALENCE_CLASS, DISTANCE_DECAY, STEP, JACCARD

Each function compares a case value to a precedent value and returns
a similarity score in [0.0, 1.0].

The dispatcher compare_field() reads a FieldDefinition and routes
to the correct comparison function automatically.
"""

from __future__ import annotations

from typing import Any

from kernel.precedent.domain_registry import ComparisonFn, FieldDefinition


# ---------------------------------------------------------------------------
# Comparison primitives
# ---------------------------------------------------------------------------

def compare_exact(case_value: Any, prec_value: Any) -> float:
    """EXACT: 1.0 if values are equal, 0.0 otherwise.

    Handles bool, str, int. Case-insensitive for strings.
    """
    if case_value is None or prec_value is None:
        return 0.0
    if isinstance(case_value, bool) and isinstance(prec_value, bool):
        return 1.0 if case_value == prec_value else 0.0
    if isinstance(case_value, str) and isinstance(prec_value, str):
        return 1.0 if case_value.lower().strip() == prec_value.lower().strip() else 0.0
    return 1.0 if case_value == prec_value else 0.0


def compare_equivalence_class(
    case_value: Any,
    prec_value: Any,
    classes: dict[str, list[str]],
) -> float:
    """EQUIVALENCE_CLASS: 1.0 if both values fall in the same class, 0.0 otherwise.

    Example: wire_domestic and eft are both "electronic" -> 1.0
    """
    if case_value is None or prec_value is None:
        return 0.0
    case_str = str(case_value).lower().strip()
    prec_str = str(prec_value).lower().strip()

    case_class = None
    prec_class = None
    for class_name, members in classes.items():
        lower_members = [str(m).lower().strip() for m in members]
        if case_str in lower_members:
            case_class = class_name
        if prec_str in lower_members:
            prec_class = class_name

    if case_class is None or prec_class is None:
        # Unknown value — fall back to exact match
        return 1.0 if case_str == prec_str else 0.0

    return 1.0 if case_class == prec_class else 0.0


def compare_distance_decay(
    case_value: Any,
    prec_value: Any,
    max_distance: int = 4,
) -> float:
    """DISTANCE_DECAY: 1.0 - (|a - b| / max_distance), clamped to [0.0, 1.0].

    For numeric fields like prior.sars_filed (0..4).
    """
    if case_value is None or prec_value is None:
        return 0.0
    try:
        a = float(case_value)
        b = float(prec_value)
    except (TypeError, ValueError):
        return 0.0
    if max_distance <= 0:
        return 1.0 if a == b else 0.0
    return max(0.0, 1.0 - abs(a - b) / max_distance)


def compare_step(
    case_value: Any,
    prec_value: Any,
    ordered_values: list[str],
) -> float:
    """STEP: 1.0 - (step_difference / max_steps).

    For ordinal fields like txn.amount_band or customer.relationship_length.
    Exact match = 1.0, adjacent = 1 - 1/max_steps, etc.
    """
    if case_value is None or prec_value is None:
        return 0.0
    if not ordered_values:
        return 1.0 if case_value == prec_value else 0.0

    lower_ordered = [str(v).lower().strip() for v in ordered_values]
    case_str = str(case_value).lower().strip()
    prec_str = str(prec_value).lower().strip()

    try:
        case_idx = lower_ordered.index(case_str)
        prec_idx = lower_ordered.index(prec_str)
    except ValueError:
        # Value not in ordered list — fall back to exact match
        return 1.0 if case_str == prec_str else 0.0

    max_steps = len(ordered_values) - 1
    if max_steps <= 0:
        return 1.0
    return max(0.0, 1.0 - abs(case_idx - prec_idx) / max_steps)


def compare_jaccard(
    case_values: Any,
    prec_values: Any,
) -> float:
    """JACCARD: |intersection| / |union|.

    For SET fields. Accepts sets, lists, or tuples.
    """
    if case_values is None or prec_values is None:
        return 0.0
    case_set = set(case_values) if not isinstance(case_values, set) else case_values
    prec_set = set(prec_values) if not isinstance(prec_values, set) else prec_values

    if not case_set and not prec_set:
        return 1.0  # Both empty = identical
    union = case_set | prec_set
    if not union:
        return 0.0
    return len(case_set & prec_set) / len(union)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def compare_field(
    field_def: FieldDefinition,
    case_value: Any,
    prec_value: Any,
) -> float:
    """Route to the correct comparison function based on field_def.comparison.

    Returns a similarity score in [0.0, 1.0].
    Returns 0.0 if either value is None (field not evaluable).
    """
    if case_value is None or prec_value is None:
        return 0.0

    fn = field_def.comparison

    if fn == ComparisonFn.EXACT:
        return compare_exact(case_value, prec_value)

    if fn == ComparisonFn.EQUIVALENCE_CLASS:
        return compare_equivalence_class(
            case_value, prec_value, field_def.equivalence_classes,
        )

    if fn == ComparisonFn.DISTANCE_DECAY:
        return compare_distance_decay(
            case_value, prec_value, field_def.max_distance,
        )

    if fn == ComparisonFn.STEP:
        return compare_step(
            case_value, prec_value, field_def.ordered_values,
        )

    if fn == ComparisonFn.JACCARD:
        return compare_jaccard(case_value, prec_value)

    raise ValueError(f"Unknown comparison function: {fn} for field {field_def.name}")


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "compare_exact",
    "compare_equivalence_class",
    "compare_distance_decay",
    "compare_step",
    "compare_jaccard",
    "compare_field",
]
