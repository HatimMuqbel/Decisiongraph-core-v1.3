"""
Adversarial Test Suite: Cross-Graph Integrity (SEC-03)

Tests that cells from different graphs cannot contaminate each other.
Cross-graph operations must fail with DG_INTEGRITY_FAIL.

Requirements tested:
- SEC-03: RFA referencing cell_id from different graph fails with DG_INTEGRITY_FAIL
- Graph isolation: Cells from graph_a cannot be appended to graph_b
- Integrity checks: graph_id mismatch detected by Chain.append()

Attack vectors:
1. Direct cross-graph cell injection
2. Modifying graph_id after cell creation
3. Bypassing integrity checks
"""

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from decisiongraph import (
    create_chain,
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Proof,
    CellType,
    SourceQuality,
    IntegrityFailError,
    get_current_timestamp,
    NULL_HASH,
    wrap_internal_exception
)
from decisiongraph.chain import GraphIdMismatch
from test_utils import T0, T1, T2


class TestCrossGraphContamination:
    """SEC-03: Cross-graph contamination attacks"""

    def test_cell_with_different_graph_id_rejected(self):
        """Cell from different graph_id rejected by Chain.append()"""
        # Create two separate graphs
        chain_a = create_chain("graph_a", system_time=T0)
        chain_b = create_chain("graph_b", system_time=T0)

        # Create a cell for graph_a
        cell_a = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain_a.graph_id,  # graph_a's ID
                cell_type=CellType.FACT,
                system_time=T1,
                prev_cell_hash=chain_a.cells[-1].cell_id
            ),
            fact=Fact(
                namespace="corp.hr",
                subject="user:alice",
                predicate="has_salary",
                object="75000",
                source_quality=SourceQuality.VERIFIED,
                confidence=1.0,
                valid_from=T1,
                valid_to=None
            ),
            logic_anchor=LogicAnchor(
                rule_id="manual:entry",
                rule_logic_hash=""
            ),
            proof=Proof()
        )

        # Append to graph_a - should succeed
        chain_a.append(cell_a)

        # Attempt to append same cell to graph_b - should fail
        # because graph_id doesn't match
        with pytest.raises(GraphIdMismatch) as exc_info:
            chain_b.append(cell_a)

        # Verify error mentions graph_id
        assert "graph_id" in str(exc_info.value)
        assert chain_a.graph_id in str(exc_info.value)
        assert chain_b.graph_id in str(exc_info.value)

    def test_cell_graph_id_mismatch_wraps_to_integrity_fail(self):
        """GraphIdMismatch wraps to DG_INTEGRITY_FAIL at API boundary"""
        # Create two graphs
        chain_a = create_chain("graph_a", system_time=T0)
        chain_b = create_chain("graph_b", system_time=T0)

        # Create cell for graph_a
        cell_a = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain_a.graph_id,
                cell_type=CellType.FACT,
                system_time=T1,
                prev_cell_hash=chain_a.cells[-1].cell_id
            ),
            fact=Fact(
                namespace="corp.hr",
                subject="user:bob",
                predicate="has_role",
                object="admin",
                source_quality=SourceQuality.VERIFIED,
                confidence=1.0,
                valid_from=T1,
                valid_to=None
            ),
            logic_anchor=LogicAnchor(
                rule_id="manual:entry",
                rule_logic_hash=""
            ),
            proof=Proof()
        )

        # Simulate API boundary: catch GraphIdMismatch and wrap
        try:
            chain_b.append(cell_a)
            pytest.fail("Expected GraphIdMismatch but append succeeded")
        except GraphIdMismatch as e:
            # Wrap using the exception wrapper
            wrapped = wrap_internal_exception(e, details={
                "operation": "cross_graph_contamination_test"
            })

            # Verify wrapped error has correct code
            assert isinstance(wrapped, IntegrityFailError)
            assert wrapped.code == "DG_INTEGRITY_FAIL"
            assert "graph_id" in str(wrapped).lower() or "integrity" in str(wrapped).lower()

    def test_multiple_graphs_remain_isolated(self):
        """Multiple graphs with same namespace remain isolated"""
        # Create three graphs, all with corp.hr namespace
        chain_1 = create_chain("graph_1", root_namespace="corp", system_time=T0)
        chain_2 = create_chain("graph_2", root_namespace="corp", system_time=T0)
        chain_3 = create_chain("graph_3", root_namespace="corp", system_time=T0)

        # Add facts to each graph
        for i, chain in enumerate([chain_1, chain_2, chain_3], 1):
            cell = DecisionCell(
                header=Header(
                    version="1.3",
                    graph_id=chain.graph_id,
                    cell_type=CellType.FACT,
                    system_time=T1,
                    prev_cell_hash=chain.cells[-1].cell_id
                ),
                fact=Fact(
                    namespace="corp.hr",
                    subject=f"user:employee{i}",
                    predicate="has_salary",
                    object=f"{50000 + i * 1000}",
                    source_quality=SourceQuality.VERIFIED,
                    confidence=1.0,
                    valid_from=T1,
                    valid_to=None
                ),
                logic_anchor=LogicAnchor(
                    rule_id="manual:entry",
                    rule_logic_hash=""
                ),
                proof=Proof()
            )
            chain.append(cell)

        # Verify each graph has exactly 2 cells (genesis + 1 fact)
        assert len(chain_1.cells) == 2
        assert len(chain_2.cells) == 2
        assert len(chain_3.cells) == 2

        # Verify graph_ids are distinct
        assert chain_1.graph_id != chain_2.graph_id
        assert chain_2.graph_id != chain_3.graph_id
        assert chain_1.graph_id != chain_3.graph_id

        # Attempt cross-contamination: cell from chain_1 to chain_2
        cell_from_1 = chain_1.cells[1]
        with pytest.raises(GraphIdMismatch):
            chain_2.append(cell_from_1)


class TestIntegrityViolationDetection:
    """Integrity violation detection for various tampering attempts"""

    def test_modified_cell_id_rejected(self):
        """Cell with modified cell_id fails integrity check"""
        chain = create_chain("test_graph", system_time=T0)

        # Create valid cell
        cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.FACT,
                system_time=T1,
                prev_cell_hash=chain.cells[-1].cell_id
            ),
            fact=Fact(
                namespace="corp.hr",
                subject="user:alice",
                predicate="has_salary",
                object="80000",
                source_quality=SourceQuality.VERIFIED,
                confidence=1.0,
                valid_from=T1,
                valid_to=None
            ),
            logic_anchor=LogicAnchor(
                rule_id="manual:entry",
                rule_logic_hash=""
            ),
            proof=Proof()
        )

        # Verify cell integrity before tampering
        assert cell.verify_integrity()

        # Tamper: manually modify cell_id (bypass normal construction)
        # Note: DecisionCell is a dataclass, so we can modify fields
        original_cell_id = cell.cell_id
        tampered_cell_id = "tampered_" + cell.cell_id[9:]

        # Use object.__setattr__ to bypass frozen dataclass if needed
        object.__setattr__(cell, 'cell_id', tampered_cell_id)

        # Integrity check should fail
        assert not cell.verify_integrity()

        # Chain.append should reject
        from decisiongraph.chain import IntegrityViolation
        with pytest.raises(IntegrityViolation) as exc_info:
            chain.append(cell)

        assert "integrity" in str(exc_info.value).lower()

    def test_modified_prev_cell_hash_breaks_chain(self):
        """Cell pointing to wrong prev_cell_hash breaks chain"""
        chain = create_chain("test_graph", system_time=T0)

        # Create cell with wrong prev_cell_hash
        wrong_hash = "0" * 64  # Invalid hash
        cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.FACT,
                system_time=T1,
                prev_cell_hash=wrong_hash  # Points to non-existent cell
            ),
            fact=Fact(
                namespace="corp.hr",
                subject="user:bob",
                predicate="has_salary",
                object="90000",
                source_quality=SourceQuality.VERIFIED,
                confidence=1.0,
                valid_from=T1,
                valid_to=None
            ),
            logic_anchor=LogicAnchor(
                rule_id="manual:entry",
                rule_logic_hash=""
            ),
            proof=Proof()
        )

        # Append should fail - chain break
        from decisiongraph.chain import ChainBreak
        with pytest.raises(ChainBreak) as exc_info:
            chain.append(cell)

        assert "prev_cell_hash" in str(exc_info.value).lower() or "not found" in str(exc_info.value).lower()

    @pytest.mark.parametrize("tamper_field,tamper_value", [
        ("namespace", "corp.tampered"),
        ("subject", "user:tampered"),
        ("predicate", "tampered_predicate"),
        ("object", "tampered_value"),
    ])
    def test_content_modification_after_creation(self, tamper_field, tamper_value):
        """Modifying cell content after creation invalidates cell_id"""
        chain = create_chain("test_graph", system_time=T0)

        # Create valid cell
        cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.FACT,
                system_time=T1,
                prev_cell_hash=chain.cells[-1].cell_id
            ),
            fact=Fact(
                namespace="corp.hr",
                subject="user:charlie",
                predicate="has_salary",
                object="70000",
                source_quality=SourceQuality.VERIFIED,
                confidence=1.0,
                valid_from=T1,
                valid_to=None
            ),
            logic_anchor=LogicAnchor(
                rule_id="manual:entry",
                rule_logic_hash=""
            ),
            proof=Proof()
        )

        # Verify initial integrity
        assert cell.verify_integrity()

        # Tamper with fact content
        object.__setattr__(cell.fact, tamper_field, tamper_value)

        # Integrity check should fail (cell_id no longer matches content)
        assert not cell.verify_integrity()

        # Chain should reject
        from decisiongraph.chain import IntegrityViolation
        with pytest.raises(IntegrityViolation):
            chain.append(cell)

    def test_chain_validation_detects_graph_id_mismatch(self):
        """Chain.validate() detects cells with mismatched graph_id"""
        chain = create_chain("test_graph", system_time=T0)

        # Add a valid cell first
        valid_cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.FACT,
                system_time=T1,
                prev_cell_hash=chain.cells[-1].cell_id
            ),
            fact=Fact(
                namespace="corp.hr",
                subject="user:david",
                predicate="has_role",
                object="developer",
                source_quality=SourceQuality.VERIFIED,
                confidence=1.0,
                valid_from=T1,
                valid_to=None
            ),
            logic_anchor=LogicAnchor(
                rule_id="manual:entry",
                rule_logic_hash=""
            ),
            proof=Proof()
        )
        chain.append(valid_cell)

        # Now bypass append() and directly manipulate chain.cells
        # to simulate a corrupted chain with wrong graph_id
        tampered_cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id="different_graph_id",  # Wrong graph_id
                cell_type=CellType.FACT,
                system_time=T2,
                prev_cell_hash=chain.cells[-1].cell_id
            ),
            fact=Fact(
                namespace="corp.hr",
                subject="user:eve",
                predicate="has_role",
                object="manager",
                source_quality=SourceQuality.VERIFIED,
                confidence=1.0,
                valid_from=T2,
                valid_to=None
            ),
            logic_anchor=LogicAnchor(
                rule_id="manual:entry",
                rule_logic_hash=""
            ),
            proof=Proof()
        )

        # Bypass normal append to inject tampered cell
        chain.cells.append(tampered_cell)
        chain.index[tampered_cell.cell_id] = len(chain.cells) - 1

        # Validate should detect the mismatch
        result = chain.validate()
        assert not result.is_valid
        assert any("graph" in err.lower() and "mismatch" in err.lower()
                   for err in result.errors)
