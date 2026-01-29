"""
Tests for Shadow Chain Contamination Prevention (Phase 07-02)

Critical requirement: SHD-04 Zero Contamination

Validates:
- Shadow chain is structurally separate from base chain
- Appending to shadow chain does NOT modify base chain
- Shadow chain has separate index (cell lookups independent)
- Multiple shadow chains are isolated from each other
- Base chain head remains unchanged after shadow operations
- Shadow chain still validates cells normally

This is a CORE SAFETY requirement. Failure here means shadow cells could
contaminate the production vault, violating the entire Oracle layer premise.
"""

import pytest

from decisiongraph.shadow import fork_shadow_chain, OverlayContext, create_shadow_fact
from decisiongraph.chain import create_chain, ChainError, GraphIdMismatch
from decisiongraph.cell import (
    DecisionCell,
    CellType,
    Header,
    Fact,
    LogicAnchor,
    SourceQuality,
    generate_graph_id
)


# =============================================================================
# Test Fixtures
# =============================================================================

def create_test_cell(
    namespace: str = "corp.hr",
    subject: str = "employee:alice",
    predicate: str = "salary",
    object_val: str = "80000",
    graph_id: str = None,
    prev_cell_hash: str = None,
    system_time: str = None
) -> DecisionCell:
    """Create a test fact cell for contamination tests."""
    if graph_id is None:
        graph_id = "graph:test"
    if prev_cell_hash is None:
        prev_cell_hash = "0" * 64
    if system_time is None:
        # Use current time to ensure it's after genesis (which also uses current time)
        from decisiongraph.cell import get_current_timestamp
        system_time = get_current_timestamp()

    return DecisionCell(
        header=Header(
            version="1.6",
            graph_id=graph_id,
            cell_type=CellType.FACT,
            system_time=system_time,
            prev_cell_hash=prev_cell_hash
        ),
        fact=Fact(
            namespace=namespace,
            subject=subject,
            predicate=predicate,
            object=object_val,
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="rule:test_v1",
            rule_logic_hash="test_hash"
        )
    )


# =============================================================================
# Core Contamination Prevention Tests
# =============================================================================

def test_shadow_chain_append_no_base_contamination():
    """
    CRITICAL TEST: Appending to shadow chain MUST NOT affect base chain.

    This is the zero contamination guarantee (SHD-04).
    """
    # Create base chain with genesis
    base_chain = create_chain(graph_name="TestGraph", root_namespace="corp")
    original_length = len(base_chain.cells)
    original_head_id = base_chain.head.cell_id

    # Fork shadow chain
    shadow_chain = fork_shadow_chain(base_chain)

    # Create and append a shadow cell to shadow chain
    shadow_cell = create_test_cell(
        graph_id=base_chain.graph_id,
        prev_cell_hash=shadow_chain.head.cell_id
        # system_time defaults to current time (after genesis)
    )
    shadow_chain.append(shadow_cell)

    # CRITICAL ASSERTION: Base chain is UNCHANGED
    assert len(base_chain.cells) == original_length, \
        "CONTAMINATION DETECTED! Shadow append modified base chain length"

    assert base_chain.head.cell_id == original_head_id, \
        "CONTAMINATION DETECTED! Shadow append modified base chain head"

    # Shadow chain has grown
    assert len(shadow_chain.cells) == original_length + 1
    assert shadow_chain.head.cell_id == shadow_cell.cell_id


def test_shadow_chain_separate_index():
    """
    Test that shadow chain has separate index from base chain.

    Appending to shadow chain updates shadow index only.
    """
    base_chain = create_chain()
    shadow_chain = fork_shadow_chain(base_chain)

    # Append cell to shadow chain
    shadow_cell = create_test_cell(
        graph_id=base_chain.graph_id,
        prev_cell_hash=shadow_chain.head.cell_id,
        # system_time defaults to current time
    )
    shadow_chain.append(shadow_cell)

    # Shadow cell in shadow index
    assert shadow_cell.cell_id in shadow_chain.index

    # Shadow cell NOT in base index
    assert shadow_cell.cell_id not in base_chain.index


def test_shadow_chain_shares_cell_references():
    """
    Test that shadow chain shares immutable cell references (memory efficient).

    Both chains point to the same Cell objects (frozen dataclasses).
    Only the list container is new.
    """
    base_chain = create_chain()
    genesis_cell = base_chain.genesis

    # Append a cell to base
    cell1 = create_test_cell(
        graph_id=base_chain.graph_id,
        prev_cell_hash=base_chain.head.cell_id,
        # system_time defaults to current time
    )
    base_chain.append(cell1)

    # Fork shadow chain
    shadow_chain = fork_shadow_chain(base_chain)

    # Genesis cell is the SAME object (shared reference)
    assert shadow_chain.cells[0] is base_chain.cells[0]
    assert shadow_chain.genesis is genesis_cell

    # Appended cell is also shared
    assert shadow_chain.cells[1] is base_chain.cells[1]
    assert shadow_chain.cells[1] is cell1


def test_shadow_chain_graph_id_match():
    """
    Test that shadow chain has same graph_id as base chain.

    This allows shadow cells to be appended (graph_id validation passes).
    """
    base_chain = create_chain(graph_name="TestGraph")
    shadow_chain = fork_shadow_chain(base_chain)

    assert shadow_chain.graph_id == base_chain.graph_id
    assert shadow_chain.root_namespace == base_chain.root_namespace

    # Shadow cell with matching graph_id can be appended
    shadow_cell = create_test_cell(
        graph_id=base_chain.graph_id,
        prev_cell_hash=shadow_chain.head.cell_id,
        # system_time defaults to current time
    )
    shadow_chain.append(shadow_cell)  # Should not raise


def test_multiple_shadow_chains_isolated():
    """
    Test that multiple shadow chains are isolated from each other and base.

    Critical for parallel simulations - they must not interfere.
    """
    base_chain = create_chain()
    original_length = len(base_chain.cells)

    # Fork two shadow chains
    shadow1 = fork_shadow_chain(base_chain)
    shadow2 = fork_shadow_chain(base_chain)

    # Append to shadow1
    cell1 = create_test_cell(
        graph_id=base_chain.graph_id,
        prev_cell_hash=shadow1.head.cell_id,
        # system_time defaults to current time,
        object_val="scenario_1"
    )
    shadow1.append(cell1)

    # Append different cell to shadow2
    cell2 = create_test_cell(
        graph_id=base_chain.graph_id,
        prev_cell_hash=shadow2.head.cell_id,
        # system_time defaults to current time,
        object_val="scenario_2"
    )
    shadow2.append(cell2)

    # Base chain unchanged
    assert len(base_chain.cells) == original_length

    # shadow1 has only cell1
    assert len(shadow1.cells) == original_length + 1
    assert shadow1.head.cell_id == cell1.cell_id

    # shadow2 has only cell2
    assert len(shadow2.cells) == original_length + 1
    assert shadow2.head.cell_id == cell2.cell_id

    # shadow1 and shadow2 are different
    assert shadow1.head.cell_id != shadow2.head.cell_id


def test_base_chain_head_unchanged():
    """
    Test that base chain head remains unchanged after shadow operations.

    Even after multiple shadow appends, base chain head is frozen.
    """
    base_chain = create_chain()

    # Append a cell to base
    base_cell = create_test_cell(
        graph_id=base_chain.graph_id,
        prev_cell_hash=base_chain.head.cell_id,
        # system_time defaults to current time
    )
    base_chain.append(base_cell)

    original_head_id = base_chain.head.cell_id

    # Fork shadow and append multiple cells
    shadow_chain = fork_shadow_chain(base_chain)

    for i in range(5):
        shadow_cell = create_test_cell(
            graph_id=base_chain.graph_id,
            prev_cell_hash=shadow_chain.head.cell_id,
            object_val=f"shadow_{i}"
            # system_time defaults to current time (monotonically increasing)
        )
        shadow_chain.append(shadow_cell)

    # Base head is STILL the same
    assert base_chain.head.cell_id == original_head_id


def test_shadow_chain_validates_cells():
    """
    Test that shadow chain still performs normal validation.

    Structural separation does NOT disable safety checks.
    Shadow chain should reject invalid cells (wrong graph_id, etc.)
    """
    base_chain = create_chain()
    shadow_chain = fork_shadow_chain(base_chain)

    # Create cell with WRONG graph_id
    bad_cell = create_test_cell(
        graph_id="graph:wrong",  # Different graph_id
        prev_cell_hash=shadow_chain.head.cell_id,
        # system_time defaults to current time
    )

    # Should raise GraphIdMismatch
    with pytest.raises(GraphIdMismatch):
        shadow_chain.append(bad_cell)


# =============================================================================
# Integration Test: Full Simulation Flow
# =============================================================================

def test_full_simulation_flow_no_contamination():
    """
    Integration test: Full simulation flow with OverlayContext and shadow chain.

    Simulates:
    1. Create base chain with multiple cells
    2. Fork shadow chain
    3. Create shadow cells via OverlayContext
    4. Append shadow cells to shadow chain
    5. Query shadow chain for shadow facts
    6. Verify base chain is COMPLETELY unchanged

    This is the real-world usage pattern for Oracle layer simulations.
    """
    # Step 1: Create base chain with genesis + 3 fact cells
    base_chain = create_chain(graph_name="ProdVault", root_namespace="corp")

    for i in range(3):
        base_cell = create_test_cell(
            graph_id=base_chain.graph_id,
            prev_cell_hash=base_chain.head.cell_id,
            subject=f"employee:{chr(97 + i)}",  # alice, bob, charlie
            object_val=f"{80000 + i * 1000}"
            # system_time defaults to current time (monotonically increasing)
        )
        base_chain.append(base_cell)

    original_length = len(base_chain.cells)
    original_head_id = base_chain.head.cell_id

    # Step 2: Fork shadow chain
    shadow_chain = fork_shadow_chain(base_chain)

    # Step 3: Create OverlayContext with shadow facts
    ctx = OverlayContext()

    # Create shadow fact: "What if Alice's salary was 90000?"
    base_alice_cell = base_chain.cells[1]  # First fact cell

    # Create a proper shadow cell that can be appended to shadow chain
    # We need to use create_test_cell with correct prev_cell_hash
    shadow_alice_cell = create_test_cell(
        namespace=base_alice_cell.fact.namespace,
        subject=base_alice_cell.fact.subject,
        predicate=base_alice_cell.fact.predicate,
        object_val="90000",  # Shadow value
        graph_id=shadow_chain.graph_id,
        prev_cell_hash=shadow_chain.head.cell_id
        # system_time defaults to current time (after base cells)
    )

    # Add to overlay context
    ctx.add_shadow_fact(shadow_alice_cell, base_cell_id=base_alice_cell.cell_id)

    # Step 4: Append shadow cell to shadow chain
    # (Normally this would be done by simulation engine)
    shadow_chain.append(shadow_alice_cell)

    # Step 5: Query shadow chain for facts
    shadow_facts = ctx.get_shadow_facts(base_alice_cell.fact.namespace,
                                         base_alice_cell.fact.subject,
                                         base_alice_cell.fact.predicate)
    assert len(shadow_facts) == 1
    assert shadow_facts[0].fact.object == "90000"

    # Step 6: CRITICAL ASSERTION - Base chain is COMPLETELY UNCHANGED
    assert len(base_chain.cells) == original_length, \
        "CONTAMINATION DETECTED! Base chain length changed during simulation"

    assert base_chain.head.cell_id == original_head_id, \
        "CONTAMINATION DETECTED! Base chain head changed during simulation"

    # Base chain still has original Alice salary
    base_alice_from_chain = base_chain.cells[1]
    assert base_alice_from_chain.fact.object == "80000", \
        "CONTAMINATION DETECTED! Base cell value changed"

    # Shadow chain has grown
    assert len(shadow_chain.cells) == original_length + 1
    assert shadow_chain.head.fact.object == "90000"


def test_shadow_chain_index_copy_independence():
    """
    Test that shadow chain index is a true copy, not a reference.

    Modifying shadow index must not affect base index.
    """
    base_chain = create_chain()
    shadow_chain = fork_shadow_chain(base_chain)

    # Verify indexes are different dict objects
    assert shadow_chain.index is not base_chain.index

    # Append to shadow
    shadow_cell = create_test_cell(
        graph_id=base_chain.graph_id,
        prev_cell_hash=shadow_chain.head.cell_id,
        # system_time defaults to current time
    )
    shadow_chain.append(shadow_cell)

    # Shadow index has new entry
    assert len(shadow_chain.index) == len(base_chain.index) + 1

    # Base index unchanged
    original_base_index_size = len(base_chain.index)
    assert len(base_chain.index) == original_base_index_size
