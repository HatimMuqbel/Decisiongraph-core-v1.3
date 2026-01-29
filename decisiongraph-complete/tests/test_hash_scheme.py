"""
Tests for Hash Scheme Migration (v2.0 foundation)

Verifies:
- Legacy cells (no hash_scheme) use string-concat method
- New cells with hash_scheme="canon:rfc8785:v1" use canonical method
- Hash scheme validation
- Backward compatibility: existing cells produce same cell_id
- Graph constitution: consistent scheme per graph
"""

import pytest

from decisiongraph.cell import (
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Proof,
    CellType,
    SourceQuality,
    NULL_HASH,
    HASH_SCHEME_LEGACY,
    HASH_SCHEME_CANONICAL,
    HASH_SCHEME_DEFAULT,
    get_current_timestamp,
)
from decisiongraph.chain import Chain, HashSchemeMismatch
from decisiongraph.genesis import create_genesis_cell


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def base_header_args():
    """Common header arguments for testing."""
    return {
        "version": "1.3",
        "graph_id": "graph:12345678-1234-4123-8123-123456789abc",
        "cell_type": CellType.FACT,
        "system_time": get_current_timestamp(),
        "prev_cell_hash": "a" * 64,
    }


@pytest.fixture
def base_fact():
    """Common fact for testing."""
    return Fact(
        namespace="test.ns",
        subject="subject",
        predicate="predicate",
        object="object",
        confidence=0.95,
        source_quality=SourceQuality.VERIFIED,
    )


@pytest.fixture
def base_logic_anchor():
    """Common logic anchor for testing."""
    return LogicAnchor(
        rule_id="rule-1",
        rule_logic_hash="b" * 64,
    )


# ============================================================================
# TEST: HASH SCHEME CONSTANTS
# ============================================================================

class TestHashSchemeConstants:
    """Verify hash scheme constant values."""

    def test_legacy_scheme_value(self):
        """Legacy scheme has expected value."""
        assert HASH_SCHEME_LEGACY == "legacy:concat:v1"

    def test_canonical_scheme_value(self):
        """Canonical scheme has expected value."""
        assert HASH_SCHEME_CANONICAL == "canon:rfc8785:v1"

    def test_default_is_legacy(self):
        """Default scheme is legacy for backward compat."""
        assert HASH_SCHEME_DEFAULT == HASH_SCHEME_LEGACY


# ============================================================================
# TEST: HEADER HASH SCHEME
# ============================================================================

class TestHeaderHashScheme:
    """Header hash_scheme field behavior."""

    def test_hash_scheme_optional(self, base_header_args):
        """hash_scheme is optional (defaults to None)."""
        header = Header(**base_header_args)
        assert header.hash_scheme is None

    def test_hash_scheme_legacy_valid(self, base_header_args):
        """Legacy scheme is valid."""
        header = Header(**base_header_args, hash_scheme=HASH_SCHEME_LEGACY)
        assert header.hash_scheme == HASH_SCHEME_LEGACY

    def test_hash_scheme_canonical_valid(self, base_header_args):
        """Canonical scheme is valid."""
        header = Header(**base_header_args, hash_scheme=HASH_SCHEME_CANONICAL)
        assert header.hash_scheme == HASH_SCHEME_CANONICAL

    def test_invalid_hash_scheme_rejected(self, base_header_args):
        """Invalid hash scheme raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Header(**base_header_args, hash_scheme="invalid:scheme")
        assert "Invalid hash_scheme" in str(exc_info.value)

    def test_get_effective_hash_scheme_none(self, base_header_args):
        """None hash_scheme returns default (legacy)."""
        header = Header(**base_header_args)
        assert header.get_effective_hash_scheme() == HASH_SCHEME_LEGACY

    def test_get_effective_hash_scheme_explicit(self, base_header_args):
        """Explicit hash_scheme returned as-is."""
        header = Header(**base_header_args, hash_scheme=HASH_SCHEME_CANONICAL)
        assert header.get_effective_hash_scheme() == HASH_SCHEME_CANONICAL


# ============================================================================
# TEST: HEADER SERIALIZATION
# ============================================================================

class TestHeaderSerialization:
    """Header to_dict includes hash_scheme correctly."""

    def test_to_dict_excludes_none_hash_scheme(self, base_header_args):
        """to_dict excludes hash_scheme when None (backward compat)."""
        header = Header(**base_header_args)
        d = header.to_dict()
        assert "hash_scheme" not in d

    def test_to_dict_includes_explicit_hash_scheme(self, base_header_args):
        """to_dict includes hash_scheme when set."""
        header = Header(**base_header_args, hash_scheme=HASH_SCHEME_CANONICAL)
        d = header.to_dict()
        assert d["hash_scheme"] == HASH_SCHEME_CANONICAL


# ============================================================================
# TEST: LEGACY CELL ID COMPUTATION
# ============================================================================

class TestLegacyCellId:
    """Legacy (None or explicit legacy) hash scheme uses string-concat."""

    def test_none_scheme_uses_legacy(self, base_header_args, base_fact, base_logic_anchor):
        """Cell with hash_scheme=None uses legacy method."""
        header = Header(**base_header_args, hash_scheme=None)
        cell = DecisionCell(header=header, fact=base_fact, logic_anchor=base_logic_anchor)

        # Compute expected legacy cell_id manually
        import hashlib
        seal_string = (
            header.version +
            header.graph_id +
            header.cell_type.value +
            header.system_time +
            header.prev_cell_hash +
            base_fact.namespace +
            base_fact.subject +
            base_fact.predicate +
            str(base_fact.object) +
            base_logic_anchor.rule_id +
            base_logic_anchor.rule_logic_hash
        )
        expected_id = hashlib.sha256(seal_string.encode('utf-8')).hexdigest()

        assert cell.cell_id == expected_id

    def test_explicit_legacy_scheme_same_as_none(self, base_header_args, base_fact, base_logic_anchor):
        """Explicit legacy scheme produces same cell_id as None."""
        header_none = Header(**base_header_args, hash_scheme=None)
        header_legacy = Header(**base_header_args, hash_scheme=HASH_SCHEME_LEGACY)

        cell_none = DecisionCell(header=header_none, fact=base_fact, logic_anchor=base_logic_anchor)
        cell_legacy = DecisionCell(header=header_legacy, fact=base_fact, logic_anchor=base_logic_anchor)

        assert cell_none.cell_id == cell_legacy.cell_id


# ============================================================================
# TEST: CANONICAL CELL ID COMPUTATION
# ============================================================================

class TestCanonicalCellId:
    """Canonical hash scheme uses RFC 8785 method."""

    def test_canonical_scheme_produces_different_id(self, base_header_args, base_fact, base_logic_anchor):
        """Canonical scheme produces different cell_id than legacy."""
        header_legacy = Header(**base_header_args, hash_scheme=None)
        header_canon = Header(**base_header_args, hash_scheme=HASH_SCHEME_CANONICAL)

        cell_legacy = DecisionCell(header=header_legacy, fact=base_fact, logic_anchor=base_logic_anchor)
        cell_canon = DecisionCell(header=header_canon, fact=base_fact, logic_anchor=base_logic_anchor)

        # Different schemes should produce different IDs
        assert cell_legacy.cell_id != cell_canon.cell_id

    def test_canonical_scheme_uses_canonical_bytes(self, base_header_args, base_fact, base_logic_anchor):
        """Canonical scheme uses canonical_json_bytes."""
        from decisiongraph.canon import cell_to_canonical_dict, canonical_json_bytes
        import hashlib

        header = Header(**base_header_args, hash_scheme=HASH_SCHEME_CANONICAL)
        cell = DecisionCell(header=header, fact=base_fact, logic_anchor=base_logic_anchor)

        # Manually compute expected canonical cell_id
        canonical_dict = cell_to_canonical_dict(cell)
        expected_id = hashlib.sha256(canonical_json_bytes(canonical_dict)).hexdigest()

        assert cell.cell_id == expected_id

    def test_canonical_cell_id_deterministic(self, base_header_args, base_fact, base_logic_anchor):
        """Same cell produces same canonical cell_id across calls."""
        header = Header(**base_header_args, hash_scheme=HASH_SCHEME_CANONICAL)
        cell = DecisionCell(header=header, fact=base_fact, logic_anchor=base_logic_anchor)

        # Recompute should give same result
        recomputed = cell.compute_cell_id()
        assert cell.cell_id == recomputed


# ============================================================================
# TEST: CELL SERIALIZATION ROUNDTRIP
# ============================================================================

class TestCellSerializationRoundtrip:
    """Cell serialization preserves hash_scheme."""

    def test_roundtrip_none_scheme(self, base_header_args, base_fact, base_logic_anchor):
        """Cell with None hash_scheme roundtrips correctly."""
        header = Header(**base_header_args, hash_scheme=None)
        cell = DecisionCell(header=header, fact=base_fact, logic_anchor=base_logic_anchor)

        # Serialize and deserialize
        d = cell.to_dict()
        cell2 = DecisionCell.from_dict(d)

        assert cell2.header.hash_scheme is None
        assert cell2.cell_id == cell.cell_id

    def test_roundtrip_legacy_scheme(self, base_header_args, base_fact, base_logic_anchor):
        """Cell with legacy hash_scheme roundtrips correctly."""
        header = Header(**base_header_args, hash_scheme=HASH_SCHEME_LEGACY)
        cell = DecisionCell(header=header, fact=base_fact, logic_anchor=base_logic_anchor)

        d = cell.to_dict()
        cell2 = DecisionCell.from_dict(d)

        assert cell2.header.hash_scheme == HASH_SCHEME_LEGACY
        assert cell2.cell_id == cell.cell_id

    def test_roundtrip_canonical_scheme(self, base_header_args, base_fact, base_logic_anchor):
        """Cell with canonical hash_scheme roundtrips correctly."""
        header = Header(**base_header_args, hash_scheme=HASH_SCHEME_CANONICAL)
        cell = DecisionCell(header=header, fact=base_fact, logic_anchor=base_logic_anchor)

        d = cell.to_dict()
        cell2 = DecisionCell.from_dict(d)

        assert cell2.header.hash_scheme == HASH_SCHEME_CANONICAL
        assert cell2.cell_id == cell.cell_id


# ============================================================================
# TEST: INTEGRITY VERIFICATION
# ============================================================================

class TestIntegrityVerification:
    """verify_integrity works with both schemes."""

    def test_legacy_integrity_passes(self, base_header_args, base_fact, base_logic_anchor):
        """Legacy cell passes integrity check."""
        header = Header(**base_header_args, hash_scheme=None)
        cell = DecisionCell(header=header, fact=base_fact, logic_anchor=base_logic_anchor)
        assert cell.verify_integrity() is True

    def test_canonical_integrity_passes(self, base_header_args, base_fact, base_logic_anchor):
        """Canonical cell passes integrity check."""
        header = Header(**base_header_args, hash_scheme=HASH_SCHEME_CANONICAL)
        cell = DecisionCell(header=header, fact=base_fact, logic_anchor=base_logic_anchor)
        assert cell.verify_integrity() is True


# ============================================================================
# TEST: BACKWARD COMPATIBILITY
# ============================================================================

class TestBackwardCompatibility:
    """Existing cells without hash_scheme work unchanged."""

    def test_old_cell_dict_without_hash_scheme(self, base_header_args, base_fact, base_logic_anchor):
        """Can load old cell dict without hash_scheme field."""
        # Create a cell, then remove hash_scheme from serialized form
        header = Header(**base_header_args, hash_scheme=None)
        cell = DecisionCell(header=header, fact=base_fact, logic_anchor=base_logic_anchor)

        d = cell.to_dict()
        # hash_scheme should not be in dict when None
        assert "hash_scheme" not in d["header"]

        # Should load successfully
        cell2 = DecisionCell.from_dict(d)
        assert cell2.header.hash_scheme is None
        assert cell2.cell_id == cell.cell_id

    def test_legacy_cell_id_stable(self):
        """Legacy cell_id computation hasn't changed from v1.3."""
        # Create cell with known values
        header = Header(
            version="1.3",
            graph_id="graph:00000000-0000-4000-8000-000000000000",
            cell_type=CellType.FACT,
            system_time="2026-01-28T12:00:00.000Z",
            prev_cell_hash="0" * 64,
            hash_scheme=None,
        )
        fact = Fact(
            namespace="test",
            subject="s",
            predicate="p",
            object="o",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED,
        )
        logic_anchor = LogicAnchor(
            rule_id="r",
            rule_logic_hash="1" * 64,
        )
        cell = DecisionCell(header=header, fact=fact, logic_anchor=logic_anchor)

        # This is the expected cell_id for this exact cell
        # If this test fails after changes, legacy compatibility is broken
        import hashlib
        seal_string = (
            "1.3" +
            "graph:00000000-0000-4000-8000-000000000000" +
            "fact" +
            "2026-01-28T12:00:00.000Z" +
            "0" * 64 +
            "test" +
            "s" +
            "p" +
            "o" +
            "r" +
            "1" * 64
        )
        expected_id = hashlib.sha256(seal_string.encode('utf-8')).hexdigest()

        assert cell.cell_id == expected_id


# ============================================================================
# TEST: CANON MODULE INTEGRATION
# ============================================================================

class TestCanonModuleIntegration:
    """cell_to_canonical_dict includes hash_scheme."""

    def test_canonical_dict_includes_hash_scheme(self, base_header_args, base_fact, base_logic_anchor):
        """cell_to_canonical_dict includes hash_scheme field."""
        from decisiongraph.canon import cell_to_canonical_dict

        header = Header(**base_header_args, hash_scheme=HASH_SCHEME_CANONICAL)
        cell = DecisionCell(header=header, fact=base_fact, logic_anchor=base_logic_anchor)

        canonical = cell_to_canonical_dict(cell)
        assert canonical["header"]["hash_scheme"] == HASH_SCHEME_CANONICAL

    def test_canonical_dict_includes_none_hash_scheme(self, base_header_args, base_fact, base_logic_anchor):
        """cell_to_canonical_dict includes hash_scheme even when None."""
        from decisiongraph.canon import cell_to_canonical_dict

        header = Header(**base_header_args, hash_scheme=None)
        cell = DecisionCell(header=header, fact=base_fact, logic_anchor=base_logic_anchor)

        canonical = cell_to_canonical_dict(cell)
        assert "hash_scheme" in canonical["header"]
        assert canonical["header"]["hash_scheme"] is None


# ============================================================================
# TEST: GENESIS HASH SCHEME
# ============================================================================

class TestGenesisHashScheme:
    """Genesis cell declares graph's hash scheme."""

    def test_genesis_default_hash_scheme_none(self):
        """Genesis without hash_scheme has None (legacy)."""
        genesis = create_genesis_cell(
            graph_name="Test",
            root_namespace="test"
        )
        assert genesis.header.hash_scheme is None

    def test_genesis_explicit_legacy_scheme(self):
        """Genesis can explicitly set legacy scheme."""
        genesis = create_genesis_cell(
            graph_name="Test",
            root_namespace="test",
            hash_scheme=HASH_SCHEME_LEGACY
        )
        assert genesis.header.hash_scheme == HASH_SCHEME_LEGACY

    def test_genesis_canonical_scheme(self):
        """Genesis can set canonical scheme."""
        genesis = create_genesis_cell(
            graph_name="Test",
            root_namespace="test",
            hash_scheme=HASH_SCHEME_CANONICAL
        )
        assert genesis.header.hash_scheme == HASH_SCHEME_CANONICAL

    def test_genesis_canonical_uses_canonical_cell_id(self):
        """Genesis with canonical scheme uses canonical cell_id computation."""
        from decisiongraph.canon import cell_to_canonical_dict, canonical_json_bytes
        import hashlib

        genesis = create_genesis_cell(
            graph_name="Test",
            root_namespace="test",
            hash_scheme=HASH_SCHEME_CANONICAL
        )

        # Verify cell_id was computed using canonical method
        canonical_dict = cell_to_canonical_dict(genesis)
        expected_id = hashlib.sha256(canonical_json_bytes(canonical_dict)).hexdigest()
        assert genesis.cell_id == expected_id


# ============================================================================
# TEST: CHAIN HASH SCHEME PROPERTY
# ============================================================================

class TestChainHashScheme:
    """Chain exposes graph's hash scheme."""

    def test_empty_chain_hash_scheme_none(self):
        """Empty chain has None hash_scheme."""
        chain = Chain()
        assert chain.hash_scheme is None

    def test_chain_inherits_genesis_hash_scheme(self):
        """Chain hash_scheme comes from Genesis."""
        chain = Chain()
        chain.initialize(
            graph_name="Test",
            root_namespace="test",
            hash_scheme=HASH_SCHEME_CANONICAL
        )
        assert chain.hash_scheme == HASH_SCHEME_CANONICAL

    def test_chain_initialize_default_hash_scheme(self):
        """Chain.initialize without hash_scheme uses None (legacy)."""
        chain = Chain()
        chain.initialize(graph_name="Test", root_namespace="test")
        assert chain.hash_scheme is None


# ============================================================================
# TEST: COMMIT GATE HASH SCHEME ENFORCEMENT
# ============================================================================

class TestCommitGateHashSchemeEnforcement:
    """Commit Gate enforces consistent hash scheme per graph."""

    def test_accept_matching_none_scheme(self):
        """Accept cell with None scheme when graph has None scheme."""
        chain = Chain()
        chain.initialize(graph_name="Test", root_namespace="test", hash_scheme=None)

        # Create cell with matching scheme
        cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.FACT,
                system_time=get_current_timestamp(),
                prev_cell_hash=chain.head.cell_id,
                hash_scheme=None
            ),
            fact=Fact(
                namespace="test",
                subject="s",
                predicate="p",
                object="o",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(rule_id="r", rule_logic_hash="a" * 64)
        )

        # Should not raise
        chain.append(cell)
        assert chain.length == 2

    def test_accept_matching_canonical_scheme(self):
        """Accept cell with canonical scheme when graph has canonical scheme."""
        chain = Chain()
        chain.initialize(
            graph_name="Test",
            root_namespace="test",
            hash_scheme=HASH_SCHEME_CANONICAL
        )

        # Create cell with matching scheme
        cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.FACT,
                system_time=get_current_timestamp(),
                prev_cell_hash=chain.head.cell_id,
                hash_scheme=HASH_SCHEME_CANONICAL
            ),
            fact=Fact(
                namespace="test",
                subject="s",
                predicate="p",
                object="o",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(rule_id="r", rule_logic_hash="a" * 64)
        )

        # Should not raise
        chain.append(cell)
        assert chain.length == 2

    def test_reject_canonical_cell_in_legacy_graph(self):
        """Reject cell with canonical scheme in legacy graph."""
        chain = Chain()
        chain.initialize(graph_name="Test", root_namespace="test", hash_scheme=None)

        # Create cell with canonical scheme (mismatched)
        cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.FACT,
                system_time=get_current_timestamp(),
                prev_cell_hash=chain.head.cell_id,
                hash_scheme=HASH_SCHEME_CANONICAL
            ),
            fact=Fact(
                namespace="test",
                subject="s",
                predicate="p",
                object="o",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(rule_id="r", rule_logic_hash="a" * 64)
        )

        with pytest.raises(HashSchemeMismatch) as exc_info:
            chain.append(cell)
        assert "hash_scheme" in str(exc_info.value).lower()

    def test_reject_legacy_cell_in_canonical_graph(self):
        """Reject cell with legacy scheme in canonical graph."""
        chain = Chain()
        chain.initialize(
            graph_name="Test",
            root_namespace="test",
            hash_scheme=HASH_SCHEME_CANONICAL
        )

        # Create cell with legacy scheme (mismatched)
        cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.FACT,
                system_time=get_current_timestamp(),
                prev_cell_hash=chain.head.cell_id,
                hash_scheme=None  # Legacy
            ),
            fact=Fact(
                namespace="test",
                subject="s",
                predicate="p",
                object="o",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(rule_id="r", rule_logic_hash="a" * 64)
        )

        with pytest.raises(HashSchemeMismatch) as exc_info:
            chain.append(cell)
        assert "hash_scheme" in str(exc_info.value).lower()

    def test_none_and_explicit_legacy_equivalent_in_legacy_graph(self):
        """None and explicit legacy are equivalent in legacy graph."""
        chain = Chain()
        chain.initialize(graph_name="Test", root_namespace="test", hash_scheme=None)

        # Cell with explicit legacy scheme
        cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.FACT,
                system_time=get_current_timestamp(),
                prev_cell_hash=chain.head.cell_id,
                hash_scheme=HASH_SCHEME_LEGACY  # Explicit legacy
            ),
            fact=Fact(
                namespace="test",
                subject="s",
                predicate="p",
                object="o",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(rule_id="r", rule_logic_hash="a" * 64)
        )

        # Should not raise - None and explicit legacy are equivalent
        chain.append(cell)
        assert chain.length == 2

    def test_explicit_legacy_graph_accepts_none_cells(self):
        """Graph with explicit legacy accepts cells with None scheme."""
        chain = Chain()
        chain.initialize(
            graph_name="Test",
            root_namespace="test",
            hash_scheme=HASH_SCHEME_LEGACY  # Explicit legacy
        )

        # Cell with None scheme
        cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.FACT,
                system_time=get_current_timestamp(),
                prev_cell_hash=chain.head.cell_id,
                hash_scheme=None  # None
            ),
            fact=Fact(
                namespace="test",
                subject="s",
                predicate="p",
                object="o",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(rule_id="r", rule_logic_hash="a" * 64)
        )

        # Should not raise - None and explicit legacy are equivalent
        chain.append(cell)
        assert chain.length == 2
