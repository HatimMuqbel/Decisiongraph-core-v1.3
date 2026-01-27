"""
DecisionGraph Core: Test Suite (v1.3 API)

Tests for:
1. Cell creation and cell_id computation (Logic Seal)
2. Genesis cell creation and verification
3. Chain validation and integrity checking
4. All invariants from TLA+ spec

v1.3 API:
- Uses system_time instead of timestamp
- Requires graph_id in Header
- Requires namespace in Fact
- Uses fixed test times (no now() calls)
"""

import pytest
import json
from datetime import datetime, timezone

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from decisiongraph import (
    # Cell primitives
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Evidence,
    Proof,
    CellType,
    SourceQuality,
    NULL_HASH,
    compute_rule_logic_hash,
    compute_content_id,
    generate_graph_id,

    # Genesis
    create_genesis_cell,
    verify_genesis,
    GENESIS_RULE_HASH,

    # Chain
    Chain,
    create_chain,
    IntegrityViolation,
    ChainBreak,
    GenesisViolation,
    TemporalViolation
)

# Import test time constants
from test_utils import T0, T1, T2, T3, T4, T5

# Test graph_id for standalone cell tests
TEST_GRAPH_ID = "graph:00000000-0000-0000-0000-000000000001"


class TestCellIdComputation:
    """Tests for Task 3: cell_id computation (Logic Seal)"""

    def test_cell_id_is_deterministic(self):
        """Same inputs should produce same cell_id"""
        cell1 = self._create_test_cell()
        cell2 = self._create_test_cell()

        assert cell1.cell_id == cell2.cell_id

    def test_cell_id_changes_with_subject(self):
        """Changing subject should change cell_id"""
        cell1 = self._create_test_cell(subject="entity:a")
        cell2 = self._create_test_cell(subject="entity:b")

        assert cell1.cell_id != cell2.cell_id

    def test_cell_id_changes_with_predicate(self):
        """Changing predicate should change cell_id"""
        cell1 = self._create_test_cell(predicate="has_rating")
        cell2 = self._create_test_cell(predicate="has_score")

        assert cell1.cell_id != cell2.cell_id

    def test_cell_id_changes_with_object(self):
        """Changing object should change cell_id"""
        cell1 = self._create_test_cell(object_value="High")
        cell2 = self._create_test_cell(object_value="Low")

        assert cell1.cell_id != cell2.cell_id

    def test_cell_id_changes_with_rule_hash(self):
        """Changing rule_logic_hash should change cell_id"""
        cell1 = self._create_test_cell(rule_hash="abc123")
        cell2 = self._create_test_cell(rule_hash="xyz789")

        assert cell1.cell_id != cell2.cell_id

    def test_cell_id_changes_with_system_time(self):
        """Changing system_time should change cell_id"""
        cell1 = self._create_test_cell(system_time=T0)
        cell2 = self._create_test_cell(system_time=T1)

        assert cell1.cell_id != cell2.cell_id

    def test_cell_id_changes_with_prev_hash(self):
        """Changing prev_cell_hash should change cell_id"""
        cell1 = self._create_test_cell(prev_hash="a" * 64)
        cell2 = self._create_test_cell(prev_hash="b" * 64)

        assert cell1.cell_id != cell2.cell_id

    def test_cell_id_is_sha256_hex(self):
        """cell_id should be a valid SHA-256 hex string"""
        cell = self._create_test_cell()

        assert len(cell.cell_id) == 64
        assert all(c in '0123456789abcdef' for c in cell.cell_id)

    def test_verify_integrity_passes_for_valid_cell(self):
        """verify_integrity should return True for untampered cell"""
        cell = self._create_test_cell()

        assert cell.verify_integrity() is True

    def test_verify_integrity_fails_for_tampered_cell(self):
        """verify_integrity should return False if cell is tampered"""
        cell = self._create_test_cell()
        original_id = cell.cell_id

        # Tamper with the fact
        cell.fact.object = "TAMPERED"

        # cell_id still has old value, but computed hash is different
        assert cell.cell_id == original_id
        assert cell.verify_integrity() is False

    def _create_test_cell(
        self,
        subject="entity:test",
        predicate="has_value",
        object_value="TestValue",
        rule_hash="test_hash_123",
        system_time=T0,
        prev_hash=NULL_HASH,
        graph_id=TEST_GRAPH_ID,
        namespace="test"
    ):
        """Helper to create test cells with v1.3 API"""
        return DecisionCell(
            header=Header(
                version="1.3",
                graph_id=graph_id,
                cell_type=CellType.FACT,
                system_time=system_time,
                prev_cell_hash=prev_hash
            ),
            fact=Fact(
                namespace=namespace,
                subject=subject,
                predicate=predicate,
                object=object_value,
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(
                rule_id="test:rule",
                rule_logic_hash=rule_hash
            )
        )


class TestGenesisCell:
    """Tests for Task 2: Genesis cell creation"""

    def test_create_genesis_cell(self):
        """Should create a valid Genesis cell"""
        genesis = create_genesis_cell(graph_name="TestGraph")

        assert genesis.header.cell_type == CellType.GENESIS
        assert genesis.header.prev_cell_hash == NULL_HASH
        assert genesis.fact.subject == "graph:root"
        assert genesis.fact.predicate == "instance_of"
        assert genesis.fact.object == "TestGraph"

    def test_genesis_has_full_confidence(self):
        """Genesis should have confidence 1.0"""
        genesis = create_genesis_cell()

        assert genesis.fact.confidence == 1.0
        assert genesis.fact.source_quality == SourceQuality.VERIFIED

    def test_genesis_is_genesis(self):
        """is_genesis() should return True for Genesis cell"""
        genesis = create_genesis_cell()

        assert genesis.is_genesis() is True

    def test_non_genesis_is_not_genesis(self):
        """is_genesis() should return False for non-Genesis cells"""
        cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=TEST_GRAPH_ID,
                cell_type=CellType.FACT,
                system_time=T0,
                prev_cell_hash="a" * 64
            ),
            fact=Fact(
                namespace="test",
                subject="entity:test",
                predicate="test",
                object="value",
                confidence=0.9,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(
                rule_id="test:rule",
                rule_logic_hash="hash123"
            )
        )

        assert cell.is_genesis() is False

    def test_verify_genesis_passes(self):
        """verify_genesis should return (True, []) for valid Genesis"""
        genesis = create_genesis_cell()

        is_valid, errors = verify_genesis(genesis)
        assert is_valid is True
        assert len(errors) == 0

    def test_verify_genesis_fails_for_non_genesis(self):
        """verify_genesis should return (False, errors) for non-Genesis cells"""
        cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=TEST_GRAPH_ID,
                cell_type=CellType.FACT,
                system_time=T0,
                prev_cell_hash=NULL_HASH
            ),
            fact=Fact(
                namespace="test",
                subject="graph:root",
                predicate="instance_of",
                object="TestGraph",
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(
                rule_id="test:rule",
                rule_logic_hash="hash123"
            )
        )

        # Has NULL_HASH but wrong cell_type
        is_valid, errors = verify_genesis(cell)
        assert is_valid is False
        assert len(errors) > 0

    def test_genesis_has_rule_anchor(self):
        """Genesis should anchor to the boot rule"""
        genesis = create_genesis_cell()

        assert genesis.logic_anchor.rule_id == "system:genesis_boot_v1.3"
        assert genesis.logic_anchor.rule_logic_hash == GENESIS_RULE_HASH


class TestChainValidation:
    """Tests for Task 4: Chain validation"""

    def test_create_empty_chain(self):
        """Should create empty chain"""
        chain = Chain()

        assert chain.is_empty()
        assert chain.length == 0

    def test_initialize_chain(self):
        """Should initialize chain with Genesis"""
        chain = Chain()
        genesis = chain.initialize(graph_name="TestGraph")

        assert chain.has_genesis()
        assert chain.length == 1
        assert chain.genesis == genesis

    def test_create_chain_helper(self):
        """create_chain should create initialized chain"""
        chain = create_chain(graph_name="TestGraph", system_time=T0)

        assert chain.has_genesis()
        assert chain.genesis.fact.object == "TestGraph"

    def test_cannot_reinitialize(self):
        """Should raise error if trying to reinitialize"""
        chain = create_chain(system_time=T0)

        with pytest.raises(GenesisViolation):
            chain.initialize()

    def test_append_cell_to_chain(self):
        """Should append valid cell"""
        chain = create_chain(system_time=T0)

        cell = self._create_linked_cell(chain, chain.head.cell_id, T1)
        chain.append(cell)

        assert chain.length == 2
        assert chain.head == cell

    def test_cannot_append_before_genesis(self):
        """Should raise error if appending before Genesis"""
        chain = Chain()

        cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=TEST_GRAPH_ID,
                cell_type=CellType.FACT,
                system_time=T0,
                prev_cell_hash="some_hash"
            ),
            fact=Fact(
                namespace="test",
                subject="entity:test",
                predicate="has_value",
                object="TestValue",
                confidence=0.9,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(
                rule_id="test:rule",
                rule_logic_hash="test_hash"
            )
        )

        with pytest.raises(GenesisViolation):
            chain.append(cell)

    def test_cannot_append_second_genesis(self):
        """Should raise error if appending second Genesis"""
        chain = create_chain(system_time=T0)
        genesis2 = create_genesis_cell(graph_name="Second")

        with pytest.raises(GenesisViolation):
            chain.append(genesis2)

    def test_cannot_append_broken_chain(self):
        """Should raise error if prev_cell_hash doesn't exist"""
        chain = create_chain(system_time=T0)

        cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.FACT,
                system_time=T1,
                prev_cell_hash="nonexistent_hash"
            ),
            fact=Fact(
                namespace="test",
                subject="entity:test",
                predicate="has_value",
                object="TestValue",
                confidence=0.9,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(
                rule_id="test:rule",
                rule_logic_hash="test_hash"
            )
        )

        with pytest.raises(ChainBreak):
            chain.append(cell)

    def test_validate_valid_chain(self):
        """Should validate clean chain"""
        chain = create_chain(system_time=T0)

        # Add some cells with incrementing times
        times = [T1, T2, T3, T4, T5]
        for i, t in enumerate(times):
            cell = self._create_linked_cell(chain, chain.head.cell_id, t)
            chain.append(cell)

        result = chain.validate()

        assert result.is_valid
        assert result.cells_checked == 6
        assert len(result.errors) == 0

    def test_trace_to_genesis(self):
        """Should trace cell back to Genesis"""
        chain = create_chain(system_time=T0)

        # Add chain of cells
        times = [T1, T2, T3, T4, T5]
        for t in times:
            cell = self._create_linked_cell(chain, chain.head.cell_id, t)
            chain.append(cell)

        # Trace from head back to genesis
        path = chain.trace_to_genesis(chain.head.cell_id)

        assert len(path) == 6
        assert path[0] == chain.head
        assert path[-1] == chain.genesis

    def test_find_by_type(self):
        """Should find cells by type"""
        chain = create_chain(system_time=T0)

        # Add fact cell
        fact_cell = self._create_linked_cell(
            chain,
            chain.head.cell_id,
            T1,
            cell_type=CellType.FACT
        )
        chain.append(fact_cell)

        # Add decision cell
        decision_cell = self._create_linked_cell(
            chain,
            chain.head.cell_id,
            T2,
            cell_type=CellType.DECISION
        )
        chain.append(decision_cell)

        facts = chain.find_by_type(CellType.FACT)
        decisions = chain.find_by_type(CellType.DECISION)

        assert len(facts) == 1
        assert len(decisions) == 1

    def test_find_by_subject(self):
        """Should find cells by subject"""
        chain = create_chain(system_time=T0)

        cell1 = self._create_linked_cell(
            chain,
            chain.head.cell_id,
            T1,
            subject="entity:customer_123"
        )
        chain.append(cell1)

        cell2 = self._create_linked_cell(
            chain,
            chain.head.cell_id,
            T2,
            subject="entity:customer_456"
        )
        chain.append(cell2)

        results = chain.find_by_subject("entity:customer_123")

        assert len(results) == 1
        assert results[0].fact.subject == "entity:customer_123"

    def test_find_decisions_with_rule_mismatch(self):
        """Should find decisions with wrong rule hash"""
        chain = create_chain(system_time=T0)

        # Add decision with old rule hash
        decision = self._create_linked_cell(
            chain,
            chain.head.cell_id,
            T1,
            cell_type=CellType.DECISION,
            rule_id="policy:risk",
            rule_hash="old_hash_123"
        )
        chain.append(decision)

        # Current rules have different hash
        current_rules = {"policy:risk": "new_hash_456"}

        mismatches = chain.find_decisions_with_rule_mismatch(current_rules)

        assert len(mismatches) == 1
        assert mismatches[0] == decision

    def test_json_roundtrip(self):
        """Should serialize and deserialize chain"""
        chain = create_chain(graph_name="TestGraph", system_time=T0)

        times = [T1, T2, T3]
        for t in times:
            cell = self._create_linked_cell(chain, chain.head.cell_id, t)
            chain.append(cell)

        # Serialize
        json_str = chain.to_json()

        # Deserialize
        restored = Chain.from_json(json_str)

        assert restored.length == chain.length
        assert restored.genesis.cell_id == chain.genesis.cell_id
        assert restored.head.cell_id == chain.head.cell_id

    def _create_linked_cell(
        self,
        chain,
        prev_hash,
        system_time,
        cell_type=CellType.FACT,
        subject="entity:test",
        rule_id="test:rule",
        rule_hash="test_hash",
        namespace="test"
    ):
        """Helper to create cells linked to prev_hash with v1.3 API"""
        return DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=cell_type,
                system_time=system_time,
                prev_cell_hash=prev_hash
            ),
            fact=Fact(
                namespace=namespace,
                subject=subject,
                predicate="has_value",
                object="TestValue",
                confidence=0.9,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(
                rule_id=rule_id,
                rule_logic_hash=rule_hash
            )
        )


class TestInvariants:
    """Tests for TLA+ invariants"""

    def test_invariant_atomic_integrity(self):
        """INVARIANT 1: All cells must have valid cell_id"""
        chain = create_chain(system_time=T0)

        times = [T1, T2, T3, T4, T5]
        for i, t in enumerate(times):
            cell = DecisionCell(
                header=Header(
                    version="1.3",
                    graph_id=chain.graph_id,
                    cell_type=CellType.FACT,
                    system_time=t,
                    prev_cell_hash=chain.head.cell_id
                ),
                fact=Fact(
                    namespace="test",
                    subject=f"entity:test_{i}",
                    predicate="has_value",
                    object=f"Value_{i}",
                    confidence=0.9,
                    source_quality=SourceQuality.VERIFIED
                ),
                logic_anchor=LogicAnchor(
                    rule_id="test:rule",
                    rule_logic_hash="hash"
                )
            )
            chain.append(cell)

        # All cells should have valid integrity
        for cell in chain:
            assert cell.verify_integrity()

    def test_invariant_genesis_uniqueness(self):
        """INVARIANT 2: Exactly one Genesis cell"""
        chain = create_chain(system_time=T0)

        genesis_count = sum(1 for c in chain if c.is_genesis())
        assert genesis_count == 1

    def test_invariant_chain_of_custody(self):
        """INVARIANT 3: All cells point to existing prev_cell_hash"""
        chain = create_chain(system_time=T0)

        times = [T1, T2, T3, T4, T5]
        for i, t in enumerate(times):
            cell = DecisionCell(
                header=Header(
                    version="1.3",
                    graph_id=chain.graph_id,
                    cell_type=CellType.FACT,
                    system_time=t,
                    prev_cell_hash=chain.head.cell_id
                ),
                fact=Fact(
                    namespace="test",
                    subject=f"entity:test_{i}",
                    predicate="has_value",
                    object=f"Value_{i}",
                    confidence=0.9,
                    source_quality=SourceQuality.VERIFIED
                ),
                logic_anchor=LogicAnchor(
                    rule_id="test:rule",
                    rule_logic_hash="hash"
                )
            )
            chain.append(cell)

        # All non-genesis cells should point to existing cells
        for cell in chain:
            if not cell.is_genesis():
                assert chain.cell_exists(cell.header.prev_cell_hash)

    def test_invariant_null_hash_only_genesis(self):
        """INVARIANT 4: Only Genesis has NULL_HASH"""
        chain = create_chain(system_time=T0)

        times = [T1, T2, T3, T4, T5]
        for i, t in enumerate(times):
            cell = DecisionCell(
                header=Header(
                    version="1.3",
                    graph_id=chain.graph_id,
                    cell_type=CellType.FACT,
                    system_time=t,
                    prev_cell_hash=chain.head.cell_id
                ),
                fact=Fact(
                    namespace="test",
                    subject=f"entity:test_{i}",
                    predicate="has_value",
                    object=f"Value_{i}",
                    confidence=0.9,
                    source_quality=SourceQuality.VERIFIED
                ),
                logic_anchor=LogicAnchor(
                    rule_id="test:rule",
                    rule_logic_hash="hash"
                )
            )
            chain.append(cell)

        for cell in chain:
            if cell.header.prev_cell_hash == NULL_HASH:
                assert cell.is_genesis()

    def test_invariant_source_quality_ordering(self):
        """INVARIANT 6: Confidence 1.0 requires verified"""
        # This should raise ValueError
        with pytest.raises(ValueError):
            Fact(
                namespace="test",
                subject="test",
                predicate="test",
                object="test",
                confidence=1.0,
                source_quality=SourceQuality.INFERRED
            )


class TestEdgeCases:
    """Edge case tests"""

    def test_cell_with_special_characters(self):
        """Should handle special characters in facts"""
        cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=TEST_GRAPH_ID,
                cell_type=CellType.FACT,
                system_time=T0,
                prev_cell_hash=NULL_HASH
            ),
            fact=Fact(
                namespace="test",
                subject="entity:日本語",  # Japanese
                predicate="has_value",
                object="émoji: 🎉",
                confidence=0.9,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(
                rule_id="test:rule",
                rule_logic_hash="hash"
            )
        )

        assert cell.verify_integrity()

    def test_cell_with_empty_strings(self):
        """Should handle empty strings"""
        cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=TEST_GRAPH_ID,
                cell_type=CellType.FACT,
                system_time=T0,
                prev_cell_hash=NULL_HASH
            ),
            fact=Fact(
                namespace="test",
                subject="",
                predicate="",
                object="",
                confidence=0.5,
                source_quality=SourceQuality.INFERRED
            ),
            logic_anchor=LogicAnchor(
                rule_id="",
                rule_logic_hash=""
            )
        )

        assert cell.verify_integrity()

    def test_confidence_boundaries(self):
        """Should enforce confidence bounds"""
        with pytest.raises(ValueError):
            Fact(
                namespace="test",
                subject="test",
                predicate="test",
                object="test",
                confidence=1.1,  # Invalid
                source_quality=SourceQuality.VERIFIED
            )

        with pytest.raises(ValueError):
            Fact(
                namespace="test",
                subject="test",
                predicate="test",
                object="test",
                confidence=-0.1,  # Invalid
                source_quality=SourceQuality.VERIFIED
            )


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
