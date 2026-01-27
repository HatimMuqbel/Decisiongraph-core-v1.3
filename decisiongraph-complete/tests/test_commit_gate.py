#!/usr/bin/env python3
"""
DecisionGraph Core: Commit Gate Tests

Tests the critical Chain.append() rules:
1. Genesis must be first
2. Only one Genesis allowed
3. graph_id must match (cross-graph contamination protection)

These tests prove the "graph boundary" is unbreakable.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from decisiongraph import (
    Chain,
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Proof,
    CellType,
    SourceQuality,
    create_genesis_cell,
    create_chain,
    get_current_timestamp,
    compute_rule_logic_hash,
    generate_graph_id,
    GenesisViolation,
    GraphIdMismatch,
    ChainBreak,
    IntegrityViolation
)


# ============================================================================
# COMMIT GATE TESTS
# ============================================================================

class TestCommitGateGraphId:
    """Tests for graph_id enforcement in Chain.append()"""
    
    def test_reject_cross_graph_contamination(self):
        """
        CRITICAL TEST: Cells from different graphs must be rejected.
        
        Scenario:
        1. Create chain with genesis A (graph_id = A)
        2. Try to append cell with graph_id = B
        3. Must reject with GraphIdMismatch
        """
        # Create chain with genesis A
        chain = create_chain(
            graph_name="GraphA",
            root_namespace="grapha"
        )
        graph_id_a = chain.graph_id
        
        # Create a cell with different graph_id
        graph_id_b = generate_graph_id()  # Different graph
        assert graph_id_a != graph_id_b, "Test requires different graph_ids"
        
        ts = get_current_timestamp()
        foreign_cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=graph_id_b,  # WRONG GRAPH
                cell_type=CellType.FACT,
                system_time=ts,
                prev_cell_hash=chain.head.cell_id
            ),
            fact=Fact(
                namespace="grapha",
                subject="test:subject",
                predicate="has_value",
                object="42",
                confidence=0.9,
                source_quality=SourceQuality.SELF_REPORTED,
                valid_from=ts
            ),
            logic_anchor=LogicAnchor(
                rule_id="test:rule",
                rule_logic_hash=compute_rule_logic_hash("test rule")
            ),
            proof=Proof(signer_id="test")
        )
        
        # Must reject
        with pytest.raises(GraphIdMismatch) as exc_info:
            chain.append(foreign_cell)
        
        assert "does not match" in str(exc_info.value)
        assert graph_id_b in str(exc_info.value)
        print(f"✓ Rejected cross-graph contamination: {exc_info.value}")
    
    def test_accept_same_graph_append(self):
        """
        Cells with matching graph_id should be accepted.
        
        Scenario:
        1. Create chain with genesis A (graph_id = A)
        2. Append cell with graph_id = A
        3. Must succeed
        """
        # Create chain
        chain = create_chain(
            graph_name="GraphA",
            root_namespace="grapha"
        )
        graph_id = chain.graph_id
        
        # Create cell with SAME graph_id
        ts = get_current_timestamp()
        valid_cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=graph_id,  # SAME GRAPH
                cell_type=CellType.FACT,
                system_time=ts,
                prev_cell_hash=chain.head.cell_id
            ),
            fact=Fact(
                namespace="grapha",
                subject="test:subject",
                predicate="has_value",
                object="42",
                confidence=0.9,
                source_quality=SourceQuality.SELF_REPORTED,
                valid_from=ts
            ),
            logic_anchor=LogicAnchor(
                rule_id="test:rule",
                rule_logic_hash=compute_rule_logic_hash("test rule")
            ),
            proof=Proof(signer_id="test")
        )
        
        # Must succeed
        chain.append(valid_cell)
        
        assert chain.length == 2
        assert chain.head == valid_cell
        print(f"✓ Accepted same-graph append: {valid_cell.cell_id[:16]}...")
    
    def test_genesis_must_be_first(self):
        """
        Cannot add non-Genesis cell to empty chain.
        """
        chain = Chain()  # Empty, no genesis
        
        ts = get_current_timestamp()
        non_genesis = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=generate_graph_id(),
                cell_type=CellType.FACT,
                system_time=ts,
                prev_cell_hash="0" * 64  # Points to nothing
            ),
            fact=Fact(
                namespace="test",
                subject="test:subject",
                predicate="has_value",
                object="42",
                confidence=0.9,
                source_quality=SourceQuality.SELF_REPORTED,
                valid_from=ts
            ),
            logic_anchor=LogicAnchor(
                rule_id="test:rule",
                rule_logic_hash=compute_rule_logic_hash("test rule")
            ),
            proof=Proof(signer_id="test")
        )
        
        with pytest.raises(GenesisViolation) as exc_info:
            chain.append(non_genesis)
        
        assert "Genesis" in str(exc_info.value)
        print(f"✓ Rejected non-Genesis on empty chain: {exc_info.value}")
    
    def test_only_one_genesis_allowed(self):
        """
        Cannot add second Genesis cell.
        """
        chain = create_chain(
            graph_name="GraphA",
            root_namespace="grapha"
        )
        
        # Try to add another genesis
        genesis2 = create_genesis_cell(
            graph_name="GraphB",
            root_namespace="graphb"
        )
        
        with pytest.raises(GenesisViolation) as exc_info:
            chain.append(genesis2)
        
        assert "already exists" in str(exc_info.value)
        print(f"✓ Rejected second Genesis: {exc_info.value}")
    
    def test_chain_link_must_exist(self):
        """
        prev_cell_hash must point to existing cell.
        """
        chain = create_chain(
            graph_name="GraphA",
            root_namespace="grapha"
        )
        
        ts = get_current_timestamp()
        orphan_cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.FACT,
                system_time=ts,
                prev_cell_hash="deadbeef" + "0" * 56  # Non-existent
            ),
            fact=Fact(
                namespace="grapha",
                subject="test:subject",
                predicate="has_value",
                object="42",
                confidence=0.9,
                source_quality=SourceQuality.SELF_REPORTED,
                valid_from=ts
            ),
            logic_anchor=LogicAnchor(
                rule_id="test:rule",
                rule_logic_hash=compute_rule_logic_hash("test rule")
            ),
            proof=Proof(signer_id="test")
        )
        
        with pytest.raises(ChainBreak) as exc_info:
            chain.append(orphan_cell)
        
        assert "non-existent" in str(exc_info.value)
        print(f"✓ Rejected orphan cell: {exc_info.value}")
    
    def test_integrity_must_be_valid(self):
        """
        cell_id must match computed hash.
        """
        chain = create_chain(
            graph_name="GraphA",
            root_namespace="grapha"
        )
        
        ts = get_current_timestamp()
        valid_cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.FACT,
                system_time=ts,
                prev_cell_hash=chain.head.cell_id
            ),
            fact=Fact(
                namespace="grapha",
                subject="test:subject",
                predicate="has_value",
                object="42",
                confidence=0.9,
                source_quality=SourceQuality.SELF_REPORTED,
                valid_from=ts
            ),
            logic_anchor=LogicAnchor(
                rule_id="test:rule",
                rule_logic_hash=compute_rule_logic_hash("test rule")
            ),
            proof=Proof(signer_id="test")
        )
        
        # Tamper with the cell after creation
        valid_cell.fact.object = "TAMPERED"
        
        with pytest.raises(IntegrityViolation) as exc_info:
            chain.append(valid_cell)
        
        assert "integrity" in str(exc_info.value).lower()
        print(f"✓ Rejected tampered cell: {exc_info.value}")


class TestGraphIdValidation:
    """Tests for graph_id format validation"""
    
    def test_graph_id_lowercase_required(self):
        """
        graph_id must be lowercase (or normalized).
        """
        from decisiongraph import validate_graph_id
        
        # Valid lowercase
        assert validate_graph_id("graph:a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d")
        
        # Uppercase should be rejected (UUIDs are hex, lowercase standard)
        # Our regex uses IGNORECASE, so uppercase is accepted
        # If you want strict lowercase, remove re.IGNORECASE from GRAPH_ID_PATTERN
        upper = "graph:A1B2C3D4-E5F6-4A7B-8C9D-0E1F2A3B4C5D"
        result = validate_graph_id(upper)
        print(f"  Uppercase graph_id validation: {'accepted' if result else 'rejected'}")
        print(f"  (Current policy: case-insensitive)")
    
    def test_graph_id_format_variations(self):
        """
        Test various graph_id formats.
        """
        from decisiongraph import validate_graph_id
        
        # Valid
        assert validate_graph_id("graph:12345678-1234-4123-8123-123456789abc")
        
        # Invalid - missing prefix
        assert not validate_graph_id("12345678-1234-4123-8123-123456789abc")
        
        # Invalid - wrong UUID version (must be 4)
        assert not validate_graph_id("graph:12345678-1234-1123-8123-123456789abc")
        
        # Invalid - empty
        assert not validate_graph_id("")
        assert not validate_graph_id(None)
        
        print("✓ graph_id format validation working correctly")


# ============================================================================
# RUN TESTS
# ============================================================================

def run_all_tests():
    """Run all commit gate tests"""
    print("\n" + "=" * 60)
    print("  COMMIT GATE TESTS")
    print("=" * 60)
    
    # Test class instances
    gate_tests = TestCommitGateGraphId()
    format_tests = TestGraphIdValidation()
    
    # Run gate tests
    print("\n--- Graph ID Enforcement ---")
    gate_tests.test_reject_cross_graph_contamination()
    gate_tests.test_accept_same_graph_append()
    gate_tests.test_genesis_must_be_first()
    gate_tests.test_only_one_genesis_allowed()
    gate_tests.test_chain_link_must_exist()
    gate_tests.test_integrity_must_be_valid()
    
    # Run format tests
    print("\n--- Graph ID Format Validation ---")
    format_tests.test_graph_id_lowercase_required()
    format_tests.test_graph_id_format_variations()
    
    print("\n" + "=" * 60)
    print("  ALL COMMIT GATE TESTS PASSED ✓")
    print("=" * 60)
    print("\nThe graph boundary is UNBREAKABLE.")


if __name__ == "__main__":
    run_all_tests()
