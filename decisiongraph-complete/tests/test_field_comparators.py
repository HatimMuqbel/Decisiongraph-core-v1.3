"""Tests for v3 typed field comparison functions."""

import pytest

from decisiongraph.domain_registry import ComparisonFn, FieldDefinition, FieldTier, FieldType
from decisiongraph.field_comparators import (
    compare_distance_decay,
    compare_equivalence_class,
    compare_exact,
    compare_field,
    compare_jaccard,
    compare_step,
)


# ---------------------------------------------------------------------------
# compare_exact
# ---------------------------------------------------------------------------

class TestCompareExact:
    def test_bool_match(self):
        assert compare_exact(True, True) == 1.0
        assert compare_exact(False, False) == 1.0

    def test_bool_mismatch(self):
        assert compare_exact(True, False) == 0.0
        assert compare_exact(False, True) == 0.0

    def test_string_match(self):
        assert compare_exact("cash", "cash") == 1.0

    def test_string_case_insensitive(self):
        assert compare_exact("Cash", "CASH") == 1.0

    def test_string_mismatch(self):
        assert compare_exact("cash", "wire") == 0.0

    def test_int_match(self):
        assert compare_exact(3, 3) == 1.0

    def test_int_mismatch(self):
        assert compare_exact(1, 4) == 0.0

    def test_none_returns_zero(self):
        assert compare_exact(None, "x") == 0.0
        assert compare_exact("x", None) == 0.0
        assert compare_exact(None, None) == 0.0


# ---------------------------------------------------------------------------
# compare_equivalence_class
# ---------------------------------------------------------------------------

class TestCompareEquivalenceClass:
    CLASSES = {
        "electronic": ["wire_domestic", "wire_international", "eft", "ach"],
        "cash": ["cash", "cash_deposit"],
        "crypto": ["crypto", "virtual_currency"],
    }

    def test_same_class(self):
        assert compare_equivalence_class("wire_domestic", "eft", self.CLASSES) == 1.0

    def test_different_class(self):
        assert compare_equivalence_class("cash", "crypto", self.CLASSES) == 0.0

    def test_case_insensitive(self):
        assert compare_equivalence_class("Wire_Domestic", "EFT", self.CLASSES) == 1.0

    def test_unknown_value_exact_match(self):
        assert compare_equivalence_class("unknown", "unknown", self.CLASSES) == 1.0

    def test_unknown_value_no_match(self):
        assert compare_equivalence_class("unknown", "other", self.CLASSES) == 0.0

    def test_none(self):
        assert compare_equivalence_class(None, "cash", self.CLASSES) == 0.0


# ---------------------------------------------------------------------------
# compare_distance_decay
# ---------------------------------------------------------------------------

class TestCompareDistanceDecay:
    def test_same_value(self):
        assert compare_distance_decay(2, 2, max_distance=4) == 1.0

    def test_adjacent(self):
        assert compare_distance_decay(0, 1, max_distance=4) == 0.75

    def test_max_distance(self):
        assert compare_distance_decay(0, 4, max_distance=4) == 0.0

    def test_beyond_max(self):
        assert compare_distance_decay(0, 5, max_distance=4) == 0.0

    def test_floats(self):
        result = compare_distance_decay(1.0, 3.0, max_distance=4)
        assert abs(result - 0.5) < 0.01

    def test_none(self):
        assert compare_distance_decay(None, 2, max_distance=4) == 0.0

    def test_non_numeric(self):
        assert compare_distance_decay("abc", 2, max_distance=4) == 0.0


# ---------------------------------------------------------------------------
# compare_step
# ---------------------------------------------------------------------------

class TestCompareStep:
    AMOUNT_BANDS = ["under_3k", "3k_10k", "10k_25k", "25k_100k", "100k_500k", "500k_1m", "over_1m"]
    REL_LENGTH = ["new", "recent", "established"]

    def test_exact_match(self):
        assert compare_step("under_3k", "under_3k", self.AMOUNT_BANDS) == 1.0

    def test_adjacent_band(self):
        # 1 step out of 6 max
        result = compare_step("under_3k", "3k_10k", self.AMOUNT_BANDS)
        expected = 1.0 - 1 / 6
        assert abs(result - expected) < 0.01

    def test_far_band(self):
        # 6 steps out of 6 max
        result = compare_step("under_3k", "over_1m", self.AMOUNT_BANDS)
        assert result == 0.0

    def test_relationship_exact(self):
        assert compare_step("new", "new", self.REL_LENGTH) == 1.0

    def test_relationship_adjacent(self):
        result = compare_step("new", "recent", self.REL_LENGTH)
        assert abs(result - 0.5) < 0.01

    def test_relationship_extreme(self):
        assert compare_step("new", "established", self.REL_LENGTH) == 0.0

    def test_case_insensitive(self):
        assert compare_step("Under_3k", "UNDER_3K", self.AMOUNT_BANDS) == 1.0

    def test_unknown_value_fallback(self):
        assert compare_step("unknown", "unknown", self.AMOUNT_BANDS) == 1.0
        assert compare_step("unknown", "under_3k", self.AMOUNT_BANDS) == 0.0

    def test_none(self):
        assert compare_step(None, "new", self.REL_LENGTH) == 0.0

    def test_empty_ordered_values(self):
        assert compare_step("a", "a", []) == 1.0
        assert compare_step("a", "b", []) == 0.0


# ---------------------------------------------------------------------------
# compare_jaccard
# ---------------------------------------------------------------------------

class TestCompareJaccard:
    def test_identical(self):
        assert compare_jaccard({"a", "b", "c"}, {"a", "b", "c"}) == 1.0

    def test_disjoint(self):
        assert compare_jaccard({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial(self):
        result = compare_jaccard({"a", "b", "c"}, {"a", "b", "d"})
        assert abs(result - 2 / 4) < 0.01

    def test_empty_both(self):
        assert compare_jaccard(set(), set()) == 1.0

    def test_list_input(self):
        assert compare_jaccard(["a", "b"], ["a", "b"]) == 1.0

    def test_none(self):
        assert compare_jaccard(None, {"a"}) == 0.0


# ---------------------------------------------------------------------------
# compare_field (dispatcher)
# ---------------------------------------------------------------------------

class TestCompareField:
    def test_dispatches_exact(self):
        fd = FieldDefinition(
            name="test", label="Test", type=FieldType.BOOLEAN,
            comparison=ComparisonFn.EXACT, weight=0.05, tier=FieldTier.BEHAVIORAL,
        )
        assert compare_field(fd, True, True) == 1.0
        assert compare_field(fd, True, False) == 0.0

    def test_dispatches_equivalence_class(self):
        fd = FieldDefinition(
            name="test", label="Test", type=FieldType.CATEGORICAL,
            comparison=ComparisonFn.EQUIVALENCE_CLASS, weight=0.05,
            tier=FieldTier.STRUCTURAL,
            equivalence_classes={"group": ["a", "b"]},
        )
        assert compare_field(fd, "a", "b") == 1.0
        assert compare_field(fd, "a", "c") == 0.0

    def test_dispatches_distance_decay(self):
        fd = FieldDefinition(
            name="test", label="Test", type=FieldType.NUMERIC,
            comparison=ComparisonFn.DISTANCE_DECAY, weight=0.05,
            tier=FieldTier.BEHAVIORAL, max_distance=4,
        )
        assert compare_field(fd, 0, 0) == 1.0
        assert compare_field(fd, 0, 4) == 0.0

    def test_dispatches_step(self):
        fd = FieldDefinition(
            name="test", label="Test", type=FieldType.ORDINAL,
            comparison=ComparisonFn.STEP, weight=0.05,
            tier=FieldTier.BEHAVIORAL,
            ordered_values=["low", "medium", "high"],
        )
        assert compare_field(fd, "low", "low") == 1.0
        assert compare_field(fd, "low", "high") == 0.0

    def test_dispatches_jaccard(self):
        fd = FieldDefinition(
            name="test", label="Test", type=FieldType.SET,
            comparison=ComparisonFn.JACCARD, weight=0.05,
            tier=FieldTier.BEHAVIORAL,
        )
        assert compare_field(fd, {"a", "b"}, {"a", "b"}) == 1.0

    def test_none_returns_zero(self):
        fd = FieldDefinition(
            name="test", label="Test", type=FieldType.BOOLEAN,
            comparison=ComparisonFn.EXACT, weight=0.05, tier=FieldTier.BEHAVIORAL,
        )
        assert compare_field(fd, None, True) == 0.0
