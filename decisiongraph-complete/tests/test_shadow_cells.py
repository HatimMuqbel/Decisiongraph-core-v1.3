"""
Tests for Shadow Cell Creation (v1.6 - Oracle Layer Foundation)

Test coverage:
- Shadow cells have distinct cell_id when content changes
- Base cells remain unchanged (immutability verification)
- Shadow cells pass verify_integrity()
- Convenience functions for facts, rules, policies, bridges
- Edge cases: no modifications, evidence/proof preservation
"""

import json
import pytest

from decisiongraph import (
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Evidence,
    Proof,
    CellType,
    SourceQuality,
    compute_policy_hash
)

from decisiongraph.shadow import (
    create_shadow_cell,
    create_shadow_fact,
    create_shadow_rule,
    create_shadow_policy_head,
    create_shadow_bridge
)


# ============================================================================
# TEST FIXTURES
# ============================================================================

def create_base_fact_cell() -> DecisionCell:
    """Create a standard fact cell for testing."""
    return DecisionCell(
        header=Header(
            version="1.3",
            graph_id="graph:test",
            cell_type=CellType.FACT,
            system_time="2026-01-28T10:00:00Z",
            prev_cell_hash="0" * 64
        ),
        fact=Fact(
            namespace="corp.hr",
            subject="employee:alice",
            predicate="salary",
            object="80000",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED,
            valid_from="2026-01-01T00:00:00Z",
            valid_to=None
        ),
        logic_anchor=LogicAnchor(
            rule_id="rule:salary_v1",
            rule_logic_hash="abc123" + "0" * 58  # 64-char hash
        )
    )


def create_base_rule_cell() -> DecisionCell:
    """Create a rule cell for testing."""
    return DecisionCell(
        header=Header(
            version="1.3",
            graph_id="graph:test",
            cell_type=CellType.RULE,
            system_time="2026-01-28T10:00:00Z",
            prev_cell_hash="0" * 64
        ),
        fact=Fact(
            namespace="corp.hr",
            subject="rule:salary_cap",
            predicate="rule_definition",
            object="salary <= 200000",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="rule:salary_cap_v1",
            rule_logic_hash="def456" + "0" * 58
        )
    )


def create_base_policy_head() -> DecisionCell:
    """Create a PolicyHead cell for testing."""
    promoted_rule_ids = ["rule:salary_v1", "rule:benefits_v1"]
    policy_hash = compute_policy_hash(promoted_rule_ids)

    policy_data = {
        "policy_hash": policy_hash,
        "promoted_rule_ids": sorted(promoted_rule_ids),
        "prev_policy_head": None,
        "witness_signatures": {},
        "canonical_payload": None
    }

    return DecisionCell(
        header=Header(
            version="1.5",
            graph_id="graph:test",
            cell_type=CellType.POLICY_HEAD,
            system_time="2026-01-28T10:00:00Z",
            prev_cell_hash="0" * 64
        ),
        fact=Fact(
            namespace="corp.hr",
            subject="policy:head",
            predicate="policy_snapshot",
            object=json.dumps(policy_data, separators=(',', ':'), sort_keys=True),
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="system:policy_promotion_v1.5",
            rule_logic_hash="policy_hash_" + "0" * 52
        )
    )


def create_base_bridge_cell() -> DecisionCell:
    """Create a bridge cell for testing."""
    return DecisionCell(
        header=Header(
            version="1.3",
            graph_id="graph:test",
            cell_type=CellType.BRIDGE_RULE,
            system_time="2026-01-28T10:00:00Z",
            prev_cell_hash="0" * 64
        ),
        fact=Fact(
            namespace="corp",
            subject="corp.hr",
            predicate="bridge_to",
            object="corp.finance",  # Target namespace
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="bridge:hr_to_finance",
            rule_logic_hash="bridge_hash_" + "0" * 52
        )
    )


# ============================================================================
# CORE SHADOW CELL TESTS
# ============================================================================

def test_shadow_cell_distinct_id():
    """Shadow cells have distinct cell_id when content changes."""
    base = create_base_fact_cell()
    original_cell_id = base.cell_id

    # Create shadow with modified fact.object
    shadow = create_shadow_fact(base, object="90000")

    # Shadow has different cell_id
    assert shadow.cell_id != base.cell_id
    assert shadow.cell_id != original_cell_id

    # Shadow has modified value
    assert shadow.fact.object == "90000"

    # Base unchanged
    assert base.fact.object == "80000"
    assert base.cell_id == original_cell_id


def test_shadow_cell_base_unchanged():
    """Base cell remains unchanged after creating shadow variant."""
    base = create_base_fact_cell()
    original_cell_id = base.cell_id
    original_object = base.fact.object

    # Create shadow
    shadow = create_shadow_fact(base, object="90000")

    # Base cell completely unchanged
    assert base.cell_id == original_cell_id
    assert base.fact.object == original_object
    assert base.fact.namespace == "corp.hr"
    assert base.fact.subject == "employee:alice"
    assert base.fact.predicate == "salary"

    # Base cell still passes integrity check
    assert base.verify_integrity() is True


def test_shadow_cell_valid_integrity():
    """Shadow cells pass verify_integrity() check."""
    base = create_base_fact_cell()
    shadow = create_shadow_fact(base, object="90000")

    # Shadow cell is valid
    assert shadow.verify_integrity() is True

    # Shadow cell_id matches computed hash
    assert shadow.cell_id == shadow.compute_cell_id()


def test_shadow_cell_no_modification_same_id():
    """Shadow with no changes has same cell_id as base (content identical)."""
    base = create_base_fact_cell()

    # Create shadow with no changes (all kwargs None)
    shadow = create_shadow_cell(base)

    # Same content = same cell_id
    assert shadow.cell_id == base.cell_id

    # Still different object instances
    assert shadow is not base


def test_shadow_fact_convenience():
    """create_shadow_fact() convenience function modifies fact.object."""
    base = create_base_fact_cell()

    shadow = create_shadow_fact(base, object="90000")

    # Modified value
    assert shadow.fact.object == "90000"

    # Different cell_id
    assert shadow.cell_id != base.cell_id

    # Base unchanged
    assert base.fact.object == "80000"


def test_shadow_fact_confidence():
    """create_shadow_fact() can modify confidence value."""
    base = create_base_fact_cell()
    assert base.fact.confidence == 1.0

    # Note: confidence is NOT part of cell_id computation (by design)
    # To get different cell_id, also change object
    shadow = create_shadow_fact(base, object="90000", confidence=0.9)

    # Modified confidence
    assert shadow.fact.confidence == 0.9

    # Different cell_id (because object changed)
    assert shadow.cell_id != base.cell_id

    # Base unchanged
    assert base.fact.confidence == 1.0


def test_shadow_rule_logic_hash():
    """create_shadow_rule() modifies rule_logic_hash."""
    base = create_base_rule_cell()
    original_hash = base.logic_anchor.rule_logic_hash

    new_hash = "fedcba" + "0" * 58
    shadow = create_shadow_rule(base, rule_logic_hash=new_hash)

    # Modified hash
    assert shadow.logic_anchor.rule_logic_hash == new_hash

    # Different cell_id
    assert shadow.cell_id != base.cell_id

    # Base unchanged
    assert base.logic_anchor.rule_logic_hash == original_hash


def test_shadow_policy_head_new_rules():
    """create_shadow_policy_head() modifies promoted_rule_ids and recomputes policy_hash."""
    base = create_base_policy_head()
    base_data = json.loads(base.fact.object)
    assert base_data["promoted_rule_ids"] == ["rule:benefits_v1", "rule:salary_v1"]

    # Create shadow with different promoted rules
    new_rules = ["rule:new_v1", "rule:new_v2"]
    shadow = create_shadow_policy_head(base, promoted_rule_ids=new_rules)

    # Parse shadow policy data
    shadow_data = json.loads(shadow.fact.object)

    # Promoted rules updated (sorted)
    assert shadow_data["promoted_rule_ids"] == ["rule:new_v1", "rule:new_v2"]

    # Policy hash recomputed correctly
    expected_hash = compute_policy_hash(new_rules)
    assert shadow_data["policy_hash"] == expected_hash

    # Different cell_id
    assert shadow.cell_id != base.cell_id

    # Base unchanged
    base_data_after = json.loads(base.fact.object)
    assert base_data_after["promoted_rule_ids"] == ["rule:benefits_v1", "rule:salary_v1"]


def test_shadow_bridge_target():
    """create_shadow_bridge() modifies target namespace."""
    base = create_base_bridge_cell()
    assert base.fact.object == "corp.finance"

    shadow = create_shadow_bridge(base, object="corp.sales")

    # Modified target
    assert shadow.fact.object == "corp.sales"

    # Different cell_id
    assert shadow.cell_id != base.cell_id

    # Base unchanged
    assert base.fact.object == "corp.finance"


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

def test_shadow_cell_preserves_evidence():
    """Shadow cells preserve evidence list."""
    base = create_base_fact_cell()

    # Add evidence to base cell (manually construct new cell with evidence)
    from dataclasses import replace
    evidence = [
        Evidence(
            type="document_blob",
            cid="sha256:abc123",
            description="Salary approval document"
        )
    ]
    base_with_evidence = replace(base, evidence=evidence)

    # Create shadow
    shadow = create_shadow_fact(base_with_evidence, object="90000")

    # Evidence preserved
    assert len(shadow.evidence) == 1
    assert shadow.evidence[0].type == "document_blob"
    assert shadow.evidence[0].cid == "sha256:abc123"


def test_shadow_cell_preserves_proof():
    """Shadow cells preserve proof data."""
    base = create_base_fact_cell()

    # Add proof to base cell (manually construct new cell with proof)
    from dataclasses import replace
    proof = Proof(
        signer_id="alice",
        signature="signature_bytes",
        merkle_root="merkle_root_hash"
    )
    base_with_proof = replace(base, proof=proof)

    # Create shadow
    shadow = create_shadow_fact(base_with_proof, object="90000")

    # Proof preserved
    assert shadow.proof.signer_id == "alice"
    assert shadow.proof.signature == "signature_bytes"
    assert shadow.proof.merkle_root == "merkle_root_hash"


def test_multiple_shadows_from_same_base():
    """Multiple shadows from same base have different cell_ids."""
    base = create_base_fact_cell()

    # Create two shadows with different modifications
    shadow1 = create_shadow_fact(base, object="90000")
    shadow2 = create_shadow_fact(base, object="100000")

    # All three have different cell_ids
    assert base.cell_id != shadow1.cell_id
    assert base.cell_id != shadow2.cell_id
    assert shadow1.cell_id != shadow2.cell_id

    # Base unchanged after both shadows
    assert base.fact.object == "80000"

    # Shadows have correct values
    assert shadow1.fact.object == "90000"
    assert shadow2.fact.object == "100000"


def test_shadow_fact_multiple_fields():
    """create_shadow_fact() can modify multiple fields at once."""
    base = create_base_fact_cell()

    shadow = create_shadow_fact(
        base,
        object="95000",
        confidence=0.8,
        valid_from="2026-02-01T00:00:00Z"
    )

    # All modified fields
    assert shadow.fact.object == "95000"
    assert shadow.fact.confidence == 0.8
    assert shadow.fact.valid_from == "2026-02-01T00:00:00Z"

    # Unmodified field preserved
    assert shadow.fact.valid_to is None  # Same as base

    # Different cell_id
    assert shadow.cell_id != base.cell_id

    # Base unchanged
    assert base.fact.object == "80000"
    assert base.fact.confidence == 1.0
    assert base.fact.valid_from == "2026-01-01T00:00:00Z"


def test_shadow_cell_core_function():
    """create_shadow_cell() core function with nested replace()."""
    base = create_base_fact_cell()

    # Use core function with nested replace() for fact modification
    from dataclasses import replace
    new_fact = replace(base.fact, object="105000")
    shadow = create_shadow_cell(base, fact=new_fact)

    # Modified value
    assert shadow.fact.object == "105000"

    # Different cell_id
    assert shadow.cell_id != base.cell_id

    # Base unchanged
    assert base.fact.object == "80000"


def test_shadow_rule_no_change():
    """create_shadow_rule() with no change returns cell with same cell_id."""
    base = create_base_rule_cell()

    shadow = create_shadow_rule(base, rule_logic_hash=None)

    # Same cell_id (no change)
    assert shadow.cell_id == base.cell_id


def test_shadow_policy_head_no_change():
    """create_shadow_policy_head() with no change returns cell with same cell_id."""
    base = create_base_policy_head()

    shadow = create_shadow_policy_head(base, promoted_rule_ids=None)

    # Same cell_id (no change)
    assert shadow.cell_id == base.cell_id


def test_shadow_bridge_no_change():
    """create_shadow_bridge() with no change returns cell with same cell_id."""
    base = create_base_bridge_cell()

    shadow = create_shadow_bridge(base, object=None)

    # Same cell_id (no change)
    assert shadow.cell_id == base.cell_id


def test_shadow_cell_all_fields():
    """create_shadow_cell() can replace header, fact, and logic_anchor."""
    from dataclasses import replace
    base = create_base_fact_cell()

    # Create new header, fact, and logic_anchor
    new_header = replace(base.header, system_time="2026-01-29T10:00:00Z")
    new_fact = replace(base.fact, object="110000")
    new_logic_anchor = replace(base.logic_anchor, rule_id="rule:salary_v2")

    shadow = create_shadow_cell(
        base,
        header=new_header,
        fact=new_fact,
        logic_anchor=new_logic_anchor
    )

    # All fields modified
    assert shadow.header.system_time == "2026-01-29T10:00:00Z"
    assert shadow.fact.object == "110000"
    assert shadow.logic_anchor.rule_id == "rule:salary_v2"

    # Different cell_id
    assert shadow.cell_id != base.cell_id

    # Base unchanged
    assert base.header.system_time == "2026-01-28T10:00:00Z"
    assert base.fact.object == "80000"
    assert base.logic_anchor.rule_id == "rule:salary_v1"


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
