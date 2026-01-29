"""
Test suite for WitnessSet (v1.5)

Tests WitnessSet frozen dataclass validation, immutability, equality, and hashability.

Coverage:
- WIT-01: WitnessSet creation
- WIT-02: WitnessSet validation (threshold and namespace)
- Immutability enforcement
- Equality semantics
- Hashability (for use in sets/dicts)
"""

import pytest
from dataclasses import FrozenInstanceError
from decisiongraph import WitnessSet
from decisiongraph.exceptions import InputInvalidError


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def basic_witnessset():
    """Basic WitnessSet for testing."""
    return WitnessSet(
        namespace="corp",
        witnesses=("alice", "bob"),
        threshold=2
    )


@pytest.fixture
def bootstrap_witnessset():
    """Bootstrap mode WitnessSet (1-of-1)."""
    return WitnessSet(
        namespace="test",
        witnesses=("alice",),
        threshold=1
    )


@pytest.fixture
def multi_witness_set():
    """Multi-witness WitnessSet (2-of-3)."""
    return WitnessSet(
        namespace="corp.hr",
        witnesses=("alice", "bob", "charlie"),
        threshold=2
    )


# ============================================================================
# TEST CLASS 1: WitnessSet Creation (WIT-01)
# ============================================================================

class TestWitnessSetCreation:
    """Test WitnessSet creation and basic properties."""

    def test_create_valid_witnessset(self, basic_witnessset):
        """Basic WitnessSet creation should succeed."""
        assert basic_witnessset.namespace == "corp"
        assert basic_witnessset.witnesses == ("alice", "bob")
        assert basic_witnessset.threshold == 2

    def test_create_with_single_witness(self, bootstrap_witnessset):
        """Bootstrap mode (1-of-1) should succeed."""
        assert bootstrap_witnessset.namespace == "test"
        assert bootstrap_witnessset.witnesses == ("alice",)
        assert bootstrap_witnessset.threshold == 1

    def test_create_with_multiple_witnesses(self, multi_witness_set):
        """Multi-witness 2-of-3 scenario should succeed."""
        assert multi_witness_set.namespace == "corp.hr"
        assert multi_witness_set.witnesses == ("alice", "bob", "charlie")
        assert multi_witness_set.threshold == 2

    def test_witnesses_stored_as_tuple(self, basic_witnessset):
        """Witnesses should be stored as tuple (not list)."""
        assert isinstance(basic_witnessset.witnesses, tuple)
        assert type(basic_witnessset.witnesses) is tuple

    def test_namespace_preserved(self, multi_witness_set):
        """Namespace should be preserved exactly as provided."""
        assert multi_witness_set.namespace == "corp.hr"


# ============================================================================
# TEST CLASS 2: WitnessSet Validation (WIT-02)
# ============================================================================

class TestWitnessSetValidation:
    """Test WitnessSet validation rules."""

    def test_rejects_threshold_zero(self):
        """threshold=0 should raise InputInvalidError."""
        with pytest.raises(InputInvalidError) as exc_info:
            WitnessSet(
                namespace="corp",
                witnesses=("alice",),
                threshold=0
            )
        assert "threshold must be >= 1" in str(exc_info.value)

    def test_rejects_negative_threshold(self):
        """threshold=-1 should raise InputInvalidError."""
        with pytest.raises(InputInvalidError) as exc_info:
            WitnessSet(
                namespace="corp",
                witnesses=("alice",),
                threshold=-1
            )
        assert "threshold must be >= 1" in str(exc_info.value)

    def test_rejects_threshold_exceeds_witnesses(self):
        """threshold=3 with 2 witnesses should raise InputInvalidError."""
        with pytest.raises(InputInvalidError) as exc_info:
            WitnessSet(
                namespace="corp",
                witnesses=("alice", "bob"),
                threshold=3
            )
        assert "threshold (3) cannot exceed number of witnesses (2)" in str(exc_info.value)

    def test_rejects_empty_witnesses(self):
        """Empty witnesses list should raise InputInvalidError."""
        with pytest.raises(InputInvalidError) as exc_info:
            WitnessSet(
                namespace="corp",
                witnesses=(),
                threshold=1
            )
        assert "witnesses list cannot be empty" in str(exc_info.value)

    def test_rejects_invalid_namespace(self):
        """Invalid namespace format should raise InputInvalidError."""
        with pytest.raises(InputInvalidError) as exc_info:
            WitnessSet(
                namespace="INVALID",
                witnesses=("alice",),
                threshold=1
            )
        assert "Invalid namespace format" in str(exc_info.value)

    def test_rejects_namespace_with_trailing_dot(self):
        """Namespace with trailing dot should raise InputInvalidError."""
        with pytest.raises(InputInvalidError) as exc_info:
            WitnessSet(
                namespace="corp.",
                witnesses=("alice",),
                threshold=1
            )
        assert "Invalid namespace format" in str(exc_info.value)

    def test_error_code_is_dg_input_invalid(self):
        """Error should have DG_INPUT_INVALID code."""
        with pytest.raises(InputInvalidError) as exc_info:
            WitnessSet(
                namespace="corp",
                witnesses=("alice",),
                threshold=0
            )
        assert exc_info.value.code == "DG_INPUT_INVALID"


# ============================================================================
# TEST CLASS 3: WitnessSet Immutability
# ============================================================================

class TestWitnessSetImmutability:
    """Test that WitnessSet is truly immutable."""

    def test_cannot_modify_namespace(self, basic_witnessset):
        """Attempting to modify namespace should raise FrozenInstanceError."""
        with pytest.raises(FrozenInstanceError):
            basic_witnessset.namespace = "new_namespace"

    def test_cannot_modify_threshold(self, basic_witnessset):
        """Attempting to modify threshold should raise FrozenInstanceError."""
        with pytest.raises(FrozenInstanceError):
            basic_witnessset.threshold = 3

    def test_cannot_modify_witnesses(self, basic_witnessset):
        """Attempting to modify witnesses should raise FrozenInstanceError."""
        with pytest.raises(FrozenInstanceError):
            basic_witnessset.witnesses = ("eve",)

    def test_witnesses_tuple_prevents_append(self, basic_witnessset):
        """Tuple witnesses should prevent append operation."""
        with pytest.raises(AttributeError):
            basic_witnessset.witnesses.append("eve")


# ============================================================================
# TEST CLASS 4: WitnessSet Equality
# ============================================================================

class TestWitnessSetEquality:
    """Test WitnessSet equality semantics."""

    def test_equal_witnesssets_are_equal(self):
        """Two WitnessSets with same values should be equal."""
        ws1 = WitnessSet(
            namespace="corp",
            witnesses=("alice", "bob"),
            threshold=2
        )
        ws2 = WitnessSet(
            namespace="corp",
            witnesses=("alice", "bob"),
            threshold=2
        )
        assert ws1 == ws2

    def test_different_namespaces_not_equal(self):
        """WitnessSets with different namespaces should not be equal."""
        ws1 = WitnessSet(
            namespace="corp",
            witnesses=("alice", "bob"),
            threshold=2
        )
        ws2 = WitnessSet(
            namespace="acme",
            witnesses=("alice", "bob"),
            threshold=2
        )
        assert ws1 != ws2

    def test_different_witnesses_not_equal(self):
        """WitnessSets with different witnesses should not be equal."""
        ws1 = WitnessSet(
            namespace="corp",
            witnesses=("alice", "bob"),
            threshold=2
        )
        ws2 = WitnessSet(
            namespace="corp",
            witnesses=("alice", "charlie"),
            threshold=2
        )
        assert ws1 != ws2

    def test_different_thresholds_not_equal(self):
        """WitnessSets with different thresholds should not be equal."""
        ws1 = WitnessSet(
            namespace="corp",
            witnesses=("alice", "bob"),
            threshold=1
        )
        ws2 = WitnessSet(
            namespace="corp",
            witnesses=("alice", "bob"),
            threshold=2
        )
        assert ws1 != ws2


# ============================================================================
# TEST CLASS 5: WitnessSet Hashable
# ============================================================================

class TestWitnessSetHashable:
    """Test that WitnessSet is hashable (can be used in sets/dicts)."""

    def test_witnessset_is_hashable(self, basic_witnessset):
        """WitnessSet should be hashable."""
        # Should not raise TypeError
        hash_value = hash(basic_witnessset)
        assert isinstance(hash_value, int)

    def test_can_use_in_set(self):
        """WitnessSet should be usable in a set."""
        ws1 = WitnessSet(
            namespace="corp",
            witnesses=("alice", "bob"),
            threshold=2
        )
        ws2 = WitnessSet(
            namespace="acme",
            witnesses=("charlie",),
            threshold=1
        )
        # Should not raise TypeError
        witness_set = {ws1, ws2}
        assert len(witness_set) == 2
        assert ws1 in witness_set
        assert ws2 in witness_set

    def test_equal_witnesssets_same_hash(self):
        """Equal WitnessSets should have the same hash."""
        ws1 = WitnessSet(
            namespace="corp",
            witnesses=("alice", "bob"),
            threshold=2
        )
        ws2 = WitnessSet(
            namespace="corp",
            witnesses=("alice", "bob"),
            threshold=2
        )
        assert ws1 == ws2
        assert hash(ws1) == hash(ws2)


# ============================================================================
# ADDITIONAL EDGE CASE TESTS
# ============================================================================

class TestWitnessSetEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_witness_max_threshold(self):
        """1-of-1 threshold should be valid."""
        ws = WitnessSet(
            namespace="test",
            witnesses=("alice",),
            threshold=1
        )
        assert ws.threshold == 1
        assert len(ws.witnesses) == 1

    def test_all_witnesses_required(self):
        """Threshold equal to witness count should be valid (unanimous)."""
        ws = WitnessSet(
            namespace="corp",
            witnesses=("alice", "bob", "charlie"),
            threshold=3
        )
        assert ws.threshold == 3
        assert len(ws.witnesses) == 3

    def test_hierarchical_namespace(self):
        """Deep hierarchical namespace should be valid."""
        ws = WitnessSet(
            namespace="corp.dept.subdept.team",
            witnesses=("alice", "bob"),
            threshold=2
        )
        assert ws.namespace == "corp.dept.subdept.team"

    def test_witnesses_with_underscores(self):
        """Witness identifiers can be any string."""
        ws = WitnessSet(
            namespace="corp",
            witnesses=("alice_smith", "bob_jones", "charlie_brown"),
            threshold=2
        )
        assert "alice_smith" in ws.witnesses
        assert "bob_jones" in ws.witnesses

    def test_namespace_with_numbers(self):
        """Namespace can contain numbers."""
        ws = WitnessSet(
            namespace="corp2.dept1",
            witnesses=("alice",),
            threshold=1
        )
        assert ws.namespace == "corp2.dept1"
