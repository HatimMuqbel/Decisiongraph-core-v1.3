"""
Tests for OverlayContext container (Phase 07-02)

Validates:
- OverlayContext initialization and add/get methods
- Deterministic lookup by fact key (namespace, subject, predicate)
- Multiple shadow facts with same key (list accumulation)
- Shadow rule/bridge/policy_head indexing
- Factory method from_shadow_cells
- Empty context behavior
"""

import json
import pytest

from decisiongraph.shadow import OverlayContext
from decisiongraph.cell import (
    DecisionCell,
    CellType,
    Header,
    Fact,
    LogicAnchor,
    SourceQuality,
    compute_policy_hash
)


# =============================================================================
# Test Fixtures
# =============================================================================

def create_test_fact_cell(
    namespace: str,
    subject: str,
    predicate: str,
    object_val: str,
    graph_id: str = "graph:test"
) -> DecisionCell:
    """Create a test fact cell."""
    return DecisionCell(
        header=Header(
            version="1.6",
            graph_id=graph_id,
            cell_type=CellType.FACT,
            system_time="2026-01-28T10:00:00Z",
            prev_cell_hash="0" * 64
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


def create_test_rule_cell(rule_id: str, graph_id: str = "graph:test") -> DecisionCell:
    """Create a test rule cell."""
    return DecisionCell(
        header=Header(
            version="1.6",
            graph_id=graph_id,
            cell_type=CellType.RULE,
            system_time="2026-01-28T10:00:00Z",
            prev_cell_hash="0" * 64
        ),
        fact=Fact(
            namespace="corp",
            subject=rule_id,
            predicate="rule_content",
            object="if condition then action",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id=rule_id,
            rule_logic_hash="rule_hash_123"
        )
    )


def create_test_bridge_cell(
    source_ns: str,
    target_ns: str,
    graph_id: str = "graph:test"
) -> DecisionCell:
    """Create a test bridge cell."""
    return DecisionCell(
        header=Header(
            version="1.6",
            graph_id=graph_id,
            cell_type=CellType.BRIDGE_RULE,
            system_time="2026-01-28T10:00:00Z",
            prev_cell_hash="0" * 64
        ),
        fact=Fact(
            namespace="corp",
            subject=source_ns,
            predicate="bridge",
            object=target_ns,
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="bridge:test",
            rule_logic_hash="bridge_hash"
        )
    )


def create_test_policy_head_cell(
    namespace: str,
    rule_ids: list,
    graph_id: str = "graph:test"
) -> DecisionCell:
    """Create a test PolicyHead cell."""
    policy_hash = compute_policy_hash(rule_ids)
    policy_data = {
        "promoted_rule_ids": sorted(rule_ids),
        "policy_hash": policy_hash
    }

    return DecisionCell(
        header=Header(
            version="1.6",
            graph_id=graph_id,
            cell_type=CellType.POLICY_HEAD,
            system_time="2026-01-28T10:00:00Z",
            prev_cell_hash="0" * 64
        ),
        fact=Fact(
            namespace=namespace,
            subject="policy_head",
            predicate="promoted_rules",
            object=json.dumps(policy_data, separators=(',', ':')),
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="policy:system",
            rule_logic_hash="policy_hash"
        )
    )


# =============================================================================
# OverlayContext Initialization Tests
# =============================================================================

def test_overlay_context_empty():
    """Test that OverlayContext initializes with empty dicts."""
    ctx = OverlayContext()

    assert ctx.shadow_facts == {}
    assert ctx.shadow_rules == {}
    assert ctx.shadow_bridges == {}
    assert ctx.shadow_policy_heads == {}
    assert ctx.overridden_base_cells == set()


def test_overlay_context_add_shadow_fact():
    """Test adding a shadow fact cell."""
    ctx = OverlayContext()
    cell = create_test_fact_cell("corp.hr", "employee:alice", "salary", "90000")

    ctx.add_shadow_fact(cell)

    facts = ctx.get_shadow_facts("corp.hr", "employee:alice", "salary")
    assert len(facts) == 1
    assert facts[0].cell_id == cell.cell_id
    assert facts[0].fact.object == "90000"


def test_overlay_context_add_shadow_fact_with_base_id():
    """Test adding shadow fact with base cell override tracking."""
    ctx = OverlayContext()
    cell = create_test_fact_cell("corp.hr", "employee:alice", "salary", "90000")

    ctx.add_shadow_fact(cell, base_cell_id="abc123")

    assert "abc123" in ctx.overridden_base_cells
    facts = ctx.get_shadow_facts("corp.hr", "employee:alice", "salary")
    assert len(facts) == 1


def test_overlay_context_multiple_facts_same_key():
    """Test adding multiple shadow facts with same key (list accumulation)."""
    ctx = OverlayContext()

    cell1 = create_test_fact_cell("corp.hr", "employee:alice", "salary", "90000")
    cell2 = create_test_fact_cell("corp.hr", "employee:alice", "salary", "95000")

    ctx.add_shadow_fact(cell1)
    ctx.add_shadow_fact(cell2)

    facts = ctx.get_shadow_facts("corp.hr", "employee:alice", "salary")
    assert len(facts) == 2
    assert facts[0].fact.object == "90000"
    assert facts[1].fact.object == "95000"


# =============================================================================
# Shadow Rule Tests
# =============================================================================

def test_overlay_context_add_shadow_rule():
    """Test adding a shadow rule cell."""
    ctx = OverlayContext()
    cell = create_test_rule_cell("rule:shadow_v1")

    ctx.add_shadow_rule(cell)

    rule = ctx.get_shadow_rule("rule:shadow_v1")
    assert rule is not None
    assert rule.cell_id == cell.cell_id
    assert rule.logic_anchor.rule_id == "rule:shadow_v1"


def test_overlay_context_add_shadow_rule_with_base_id():
    """Test adding shadow rule with base cell override tracking."""
    ctx = OverlayContext()
    cell = create_test_rule_cell("rule:shadow_v1")

    ctx.add_shadow_rule(cell, base_cell_id="rule_base_123")

    assert "rule_base_123" in ctx.overridden_base_cells
    rule = ctx.get_shadow_rule("rule:shadow_v1")
    assert rule is not None


# =============================================================================
# Shadow Bridge Tests
# =============================================================================

def test_overlay_context_add_shadow_bridge():
    """Test adding a shadow bridge cell."""
    ctx = OverlayContext()
    cell = create_test_bridge_cell("corp.hr", "corp.finance")

    ctx.add_shadow_bridge(cell)

    bridge = ctx.get_shadow_bridge("corp.hr", "corp.finance")
    assert bridge is not None
    assert bridge.cell_id == cell.cell_id
    assert bridge.fact.subject == "corp.hr"
    assert bridge.fact.object == "corp.finance"


def test_overlay_context_add_shadow_bridge_with_base_id():
    """Test adding shadow bridge with base cell override tracking."""
    ctx = OverlayContext()
    cell = create_test_bridge_cell("corp.hr", "corp.finance")

    ctx.add_shadow_bridge(cell, base_cell_id="bridge_base_123")

    assert "bridge_base_123" in ctx.overridden_base_cells
    bridge = ctx.get_shadow_bridge("corp.hr", "corp.finance")
    assert bridge is not None


# =============================================================================
# Shadow PolicyHead Tests
# =============================================================================

def test_overlay_context_add_shadow_policy_head():
    """Test adding a shadow PolicyHead cell."""
    ctx = OverlayContext()
    cell = create_test_policy_head_cell("corp.hr", ["rule:v1", "rule:v2"])

    ctx.add_shadow_policy_head(cell)

    policy = ctx.get_shadow_policy_head("corp.hr")
    assert policy is not None
    assert policy.cell_id == cell.cell_id
    assert policy.fact.namespace == "corp.hr"


def test_overlay_context_add_shadow_policy_head_with_base_id():
    """Test adding shadow PolicyHead with base cell override tracking."""
    ctx = OverlayContext()
    cell = create_test_policy_head_cell("corp.hr", ["rule:v1"])

    ctx.add_shadow_policy_head(cell, base_cell_id="policy_base_123")

    assert "policy_base_123" in ctx.overridden_base_cells
    policy = ctx.get_shadow_policy_head("corp.hr")
    assert policy is not None


# =============================================================================
# Shadow Override Check Tests
# =============================================================================

def test_overlay_context_has_shadow_override():
    """Test checking for shadow override existence."""
    ctx = OverlayContext()

    # No shadow yet
    assert not ctx.has_shadow_override("corp.hr", "employee:alice", "salary")

    # Add shadow
    cell = create_test_fact_cell("corp.hr", "employee:alice", "salary", "90000")
    ctx.add_shadow_fact(cell)

    # Now shadow exists
    assert ctx.has_shadow_override("corp.hr", "employee:alice", "salary")

    # Different key has no shadow
    assert not ctx.has_shadow_override("corp.hr", "employee:bob", "salary")


# =============================================================================
# Factory Method Tests
# =============================================================================

def test_overlay_context_from_shadow_cells():
    """Test creating OverlayContext from list of shadow cells."""
    fact_cell = create_test_fact_cell("corp.hr", "employee:alice", "salary", "90000")
    rule_cell = create_test_rule_cell("rule:shadow_v1")
    bridge_cell = create_test_bridge_cell("corp.hr", "corp.finance")
    policy_cell = create_test_policy_head_cell("corp.hr", ["rule:v1"])

    shadow_cells = [fact_cell, rule_cell, bridge_cell, policy_cell]

    ctx = OverlayContext.from_shadow_cells(shadow_cells)

    # Verify each type was indexed correctly
    facts = ctx.get_shadow_facts("corp.hr", "employee:alice", "salary")
    assert len(facts) == 1

    rule = ctx.get_shadow_rule("rule:shadow_v1")
    assert rule is not None

    bridge = ctx.get_shadow_bridge("corp.hr", "corp.finance")
    assert bridge is not None

    policy = ctx.get_shadow_policy_head("corp.hr")
    assert policy is not None


def test_overlay_context_from_shadow_cells_ignores_genesis():
    """Test that from_shadow_cells ignores non-shadow cell types."""
    # Create a Genesis cell (should be ignored)
    genesis = DecisionCell(
        header=Header(
            version="1.6",
            graph_id="graph:test",
            cell_type=CellType.GENESIS,
            system_time="2026-01-28T10:00:00Z",
            prev_cell_hash="0" * 64
        ),
        fact=Fact(
            namespace="corp",
            subject="genesis",
            predicate="initialized",
            object="true",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="genesis:init",
            rule_logic_hash="genesis_hash"
        )
    )

    fact_cell = create_test_fact_cell("corp.hr", "employee:alice", "salary", "90000")

    ctx = OverlayContext.from_shadow_cells([genesis, fact_cell])

    # Only fact should be indexed
    facts = ctx.get_shadow_facts("corp.hr", "employee:alice", "salary")
    assert len(facts) == 1

    # No other types indexed
    assert len(ctx.shadow_rules) == 0
    assert len(ctx.shadow_bridges) == 0
    assert len(ctx.shadow_policy_heads) == 0


# =============================================================================
# Empty/Nonexistent Query Tests
# =============================================================================

def test_overlay_context_get_nonexistent_returns_empty():
    """Test that querying nonexistent keys returns empty/None."""
    ctx = OverlayContext()

    # Empty list for facts
    facts = ctx.get_shadow_facts("corp.hr", "employee:alice", "salary")
    assert facts == []

    # None for single-value lookups
    rule = ctx.get_shadow_rule("rule:nonexistent")
    assert rule is None

    bridge = ctx.get_shadow_bridge("corp.hr", "corp.finance")
    assert bridge is None

    policy = ctx.get_shadow_policy_head("corp.hr")
    assert policy is None


def test_overlay_context_has_shadow_override_false_for_empty():
    """Test that has_shadow_override returns False for empty context."""
    ctx = OverlayContext()

    assert not ctx.has_shadow_override("corp.hr", "employee:alice", "salary")
    assert not ctx.has_shadow_override("corp.finance", "budget", "amount")
