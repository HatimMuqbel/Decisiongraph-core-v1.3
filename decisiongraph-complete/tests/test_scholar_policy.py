#!/usr/bin/env python3
"""
DecisionGraph Core: Scholar Policy-Mode Tests (v1.5)

Tests for policy-aware queries:
- SCH-01: Query with policy_mode="promoted_only"
- SCH-02: Bitemporal policy lookup via as_of_system_time
- SCH-03: QueryResult includes policy_head_id
- SCH-04: Unpromoted rules filtered when policy_mode="promoted_only"

Uses fixed test times (T0-T5) for deterministic, non-flaky tests.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from decisiongraph import (
    # Chain & Cell
    create_chain,
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Proof,
    CellType,
    SourceQuality,

    # Namespace
    create_namespace_definition,

    # Scholar
    Scholar,
    create_scholar,
    QueryResult,

    # PolicyHead
    create_policy_head,
    parse_policy_data,
)

from test_utils import T0, T1, T2, T3, T4, T5


def _create_fact_cell(
    graph_id: str,
    prev_cell_hash: str,
    namespace: str,
    subject: str,
    predicate: str,
    object_value: str,
    rule_id: str,
    system_time: str
) -> DecisionCell:
    """Helper to create a fact cell with specific rule_id."""
    return DecisionCell(
        header=Header(
            version="1.5",
            graph_id=graph_id,
            cell_type=CellType.FACT,
            system_time=system_time,
            prev_cell_hash=prev_cell_hash
        ),
        fact=Fact(
            namespace=namespace,
            subject=subject,
            predicate=predicate,
            object=object_value,
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED,
            valid_from=system_time,
            valid_to=None
        ),
        logic_anchor=LogicAnchor(
            rule_id=rule_id,
            rule_logic_hash="test_hash",
            interpreter="test:v1"
        ),
        evidence=[],
        proof=Proof(
            signer_id="test",
            signer_key_id=None,
            signature=None,
            merkle_root=None,
            signature_required=False
        )
    )


# ===========================================================================
# SCH-01: Query with policy_mode="promoted_only"
# ===========================================================================

def test_policy_mode_promoted_only_returns_only_promoted_rule_facts():
    """SCH-01: policy_mode='promoted_only' filters to facts from promoted rules only."""
    # Setup chain
    chain = create_chain("TestGraph", "corp", "test", system_time=T0)
    graph_id = chain.graph_id

    # Create namespace
    ns = create_namespace_definition(
        namespace="corp.hr",
        owner="role:chro",
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        system_time=T1
    )
    chain.append(ns)

    # Create two facts with different rule_ids
    fact_v1 = _create_fact_cell(
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        namespace="corp.hr",
        subject="employee:jane",
        predicate="has_salary",
        object_value="100000",
        rule_id="rule:salary_v1",
        system_time=T2
    )
    chain.append(fact_v1)

    fact_v2 = _create_fact_cell(
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        namespace="corp.hr",
        subject="employee:bob",
        predicate="has_salary",
        object_value="120000",
        rule_id="rule:salary_v2",
        system_time=T3
    )
    chain.append(fact_v2)

    # Create PolicyHead that only promotes rule:salary_v2
    policy_head = create_policy_head(
        namespace="corp.hr",
        promoted_rule_ids=["rule:salary_v2"],
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        prev_policy_head=None,
        system_time=T4
    )
    chain.append(policy_head)

    scholar = create_scholar(chain)

    # Query with policy_mode="promoted_only"
    result = scholar.query_facts(
        requester_namespace="corp.hr",
        namespace="corp.hr",
        at_valid_time=T5,
        as_of_system_time=T5,
        policy_mode="promoted_only"
    )

    # Should only return fact from promoted rule (rule:salary_v2)
    assert len(result.facts) == 1
    assert result.facts[0].logic_anchor.rule_id == "rule:salary_v2"
    assert result.facts[0].fact.subject == "employee:bob"
    print("PASS: policy_mode='promoted_only' returns only promoted rule facts")


def test_policy_mode_all_returns_all_facts():
    """SCH-01: policy_mode='all' (default) returns all facts regardless of promotion."""
    # Setup chain
    chain = create_chain("TestGraph", "corp", "test", system_time=T0)
    graph_id = chain.graph_id

    # Create namespace
    ns = create_namespace_definition(
        namespace="corp.hr",
        owner="role:chro",
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        system_time=T1
    )
    chain.append(ns)

    # Create two facts with different rule_ids
    fact_v1 = _create_fact_cell(
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        namespace="corp.hr",
        subject="employee:jane",
        predicate="has_salary",
        object_value="100000",
        rule_id="rule:salary_v1",
        system_time=T2
    )
    chain.append(fact_v1)

    fact_v2 = _create_fact_cell(
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        namespace="corp.hr",
        subject="employee:bob",
        predicate="has_salary",
        object_value="120000",
        rule_id="rule:salary_v2",
        system_time=T3
    )
    chain.append(fact_v2)

    # Create PolicyHead that only promotes rule:salary_v2
    policy_head = create_policy_head(
        namespace="corp.hr",
        promoted_rule_ids=["rule:salary_v2"],
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        prev_policy_head=None,
        system_time=T4
    )
    chain.append(policy_head)

    scholar = create_scholar(chain)

    # Query with policy_mode="all" (default)
    result = scholar.query_facts(
        requester_namespace="corp.hr",
        namespace="corp.hr",
        at_valid_time=T5,
        as_of_system_time=T5,
        policy_mode="all"
    )

    # Should return both facts (policy not applied)
    assert len(result.facts) == 2
    rule_ids = {f.logic_anchor.rule_id for f in result.facts}
    assert rule_ids == {"rule:salary_v1", "rule:salary_v2"}
    assert result.policy_head_id is None  # No policy tracking in "all" mode
    print("PASS: policy_mode='all' returns all facts")


# ===========================================================================
# SCH-02: Bitemporal policy lookup via as_of_system_time
# ===========================================================================

def test_bitemporal_policy_lookup_uses_as_of_system_time():
    """SCH-02: Query at as_of_system_time uses PolicyHead active at that time."""
    # Setup chain
    chain = create_chain("TestGraph", "corp", "test", system_time=T0)
    graph_id = chain.graph_id

    # Create namespace
    ns = create_namespace_definition(
        namespace="corp.hr",
        owner="role:chro",
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        system_time=T1
    )
    chain.append(ns)

    # Create fact with rule:salary_v1
    fact_v1 = _create_fact_cell(
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        namespace="corp.hr",
        subject="employee:jane",
        predicate="has_salary",
        object_value="100000",
        rule_id="rule:salary_v1",
        system_time=T2
    )
    chain.append(fact_v1)

    # Create PolicyHead v1 at T3 that promotes only rule:salary_v1
    policy_head_v1 = create_policy_head(
        namespace="corp.hr",
        promoted_rule_ids=["rule:salary_v1"],
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        prev_policy_head=None,
        system_time=T3
    )
    chain.append(policy_head_v1)

    # Create fact with rule:salary_v2
    fact_v2 = _create_fact_cell(
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        namespace="corp.hr",
        subject="employee:bob",
        predicate="has_salary",
        object_value="120000",
        rule_id="rule:salary_v2",
        system_time=T4
    )
    chain.append(fact_v2)

    # Create PolicyHead v2 at T5 that promotes both rules
    policy_head_v2 = create_policy_head(
        namespace="corp.hr",
        promoted_rule_ids=["rule:salary_v1", "rule:salary_v2"],
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        prev_policy_head=policy_head_v1.cell_id,
        system_time=T5
    )
    chain.append(policy_head_v2)

    scholar = create_scholar(chain)

    # Query at T4 (after PolicyHead v1, before v2)
    result_at_t4 = scholar.query_facts(
        requester_namespace="corp.hr",
        namespace="corp.hr",
        at_valid_time=T4,
        as_of_system_time=T4,
        policy_mode="promoted_only"
    )

    # Should use PolicyHead v1, which only promotes rule:salary_v1
    assert result_at_t4.policy_head_id == policy_head_v1.cell_id
    assert len(result_at_t4.facts) == 1
    assert result_at_t4.facts[0].logic_anchor.rule_id == "rule:salary_v1"

    # Query at T5 (after PolicyHead v2)
    result_at_t5 = scholar.query_facts(
        requester_namespace="corp.hr",
        namespace="corp.hr",
        at_valid_time=T5,
        as_of_system_time=T5,
        policy_mode="promoted_only"
    )

    # Should use PolicyHead v2, which promotes both rules
    assert result_at_t5.policy_head_id == policy_head_v2.cell_id
    assert len(result_at_t5.facts) == 2

    print("PASS: Bitemporal policy lookup uses as_of_system_time correctly")


# ===========================================================================
# SCH-03: QueryResult includes policy_head_id
# ===========================================================================

def test_query_result_includes_policy_head_id():
    """SCH-03: QueryResult.policy_head_id is set when policy_mode='promoted_only'."""
    # Setup chain
    chain = create_chain("TestGraph", "corp", "test", system_time=T0)
    graph_id = chain.graph_id

    # Create namespace
    ns = create_namespace_definition(
        namespace="corp.hr",
        owner="role:chro",
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        system_time=T1
    )
    chain.append(ns)

    # Create fact
    fact = _create_fact_cell(
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        namespace="corp.hr",
        subject="employee:jane",
        predicate="has_salary",
        object_value="100000",
        rule_id="rule:salary_v1",
        system_time=T2
    )
    chain.append(fact)

    # Create PolicyHead
    policy_head = create_policy_head(
        namespace="corp.hr",
        promoted_rule_ids=["rule:salary_v1"],
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        prev_policy_head=None,
        system_time=T3
    )
    chain.append(policy_head)

    scholar = create_scholar(chain)

    # Query with policy_mode="promoted_only"
    result = scholar.query_facts(
        requester_namespace="corp.hr",
        namespace="corp.hr",
        at_valid_time=T4,
        as_of_system_time=T4,
        policy_mode="promoted_only"
    )

    # policy_head_id should match the PolicyHead we created
    assert result.policy_head_id == policy_head.cell_id
    assert result.policy_head_id is not None
    print("PASS: QueryResult includes policy_head_id")


def test_query_result_policy_head_id_in_proof_bundle():
    """SCH-03: QueryResult.to_proof_bundle() includes policy info."""
    # Setup chain
    chain = create_chain("TestGraph", "corp", "test", system_time=T0)
    graph_id = chain.graph_id

    # Create namespace
    ns = create_namespace_definition(
        namespace="corp.hr",
        owner="role:chro",
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        system_time=T1
    )
    chain.append(ns)

    # Create fact
    fact = _create_fact_cell(
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        namespace="corp.hr",
        subject="employee:jane",
        predicate="has_salary",
        object_value="100000",
        rule_id="rule:salary_v1",
        system_time=T2
    )
    chain.append(fact)

    # Create PolicyHead
    policy_head = create_policy_head(
        namespace="corp.hr",
        promoted_rule_ids=["rule:salary_v1"],
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        prev_policy_head=None,
        system_time=T3
    )
    chain.append(policy_head)

    scholar = create_scholar(chain)

    # Query with policy_mode="promoted_only"
    result = scholar.query_facts(
        requester_namespace="corp.hr",
        namespace="corp.hr",
        at_valid_time=T4,
        as_of_system_time=T4,
        policy_mode="promoted_only"
    )

    # Check proof bundle includes policy info
    bundle = result.to_proof_bundle()
    assert "policy" in bundle
    assert bundle["policy"]["mode"] == "promoted_only"
    assert bundle["policy"]["policy_head_id"] == policy_head.cell_id
    print("PASS: QueryResult.to_proof_bundle() includes policy info")


def test_query_result_policy_head_id_in_audit_text():
    """SCH-03: QueryResult.to_audit_text() includes Policy section."""
    # Setup chain
    chain = create_chain("TestGraph", "corp", "test", system_time=T0)
    graph_id = chain.graph_id

    # Create namespace
    ns = create_namespace_definition(
        namespace="corp.hr",
        owner="role:chro",
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        system_time=T1
    )
    chain.append(ns)

    # Create fact
    fact = _create_fact_cell(
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        namespace="corp.hr",
        subject="employee:jane",
        predicate="has_salary",
        object_value="100000",
        rule_id="rule:salary_v1",
        system_time=T2
    )
    chain.append(fact)

    # Create PolicyHead
    policy_head = create_policy_head(
        namespace="corp.hr",
        promoted_rule_ids=["rule:salary_v1"],
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        prev_policy_head=None,
        system_time=T3
    )
    chain.append(policy_head)

    scholar = create_scholar(chain)

    # Query with policy_mode="promoted_only"
    result = scholar.query_facts(
        requester_namespace="corp.hr",
        namespace="corp.hr",
        at_valid_time=T4,
        as_of_system_time=T4,
        policy_mode="promoted_only"
    )

    # Check audit text includes Policy section
    audit_text = result.to_audit_text()
    assert "Policy:" in audit_text
    assert "Mode: promoted_only" in audit_text
    assert "PolicyHead:" in audit_text
    print("PASS: QueryResult.to_audit_text() includes Policy section")


# ===========================================================================
# SCH-04: Unpromoted rules filtered when policy_mode="promoted_only"
# ===========================================================================

def test_unpromoted_rules_filtered():
    """SCH-04: Facts from unpromoted rules are excluded when policy_mode='promoted_only'."""
    # Setup chain
    chain = create_chain("TestGraph", "corp", "test", system_time=T0)
    graph_id = chain.graph_id

    # Create namespace
    ns = create_namespace_definition(
        namespace="corp.hr",
        owner="role:chro",
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        system_time=T1
    )
    chain.append(ns)

    # Create three facts with different rule_ids
    rules = ["rule:salary_v1", "rule:salary_v2", "rule:salary_v3"]
    for i, rule_id in enumerate(rules):
        fact = _create_fact_cell(
            graph_id=graph_id,
            prev_cell_hash=chain.head.cell_id,
            namespace="corp.hr",
            subject=f"employee:person_{i}",
            predicate="has_salary",
            object_value=str(100000 + i * 10000),
            rule_id=rule_id,
            system_time=T2
        )
        chain.append(fact)

    # Create PolicyHead that only promotes rules v1 and v3 (not v2)
    policy_head = create_policy_head(
        namespace="corp.hr",
        promoted_rule_ids=["rule:salary_v1", "rule:salary_v3"],
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        prev_policy_head=None,
        system_time=T3
    )
    chain.append(policy_head)

    scholar = create_scholar(chain)

    # Query with policy_mode="promoted_only"
    result = scholar.query_facts(
        requester_namespace="corp.hr",
        namespace="corp.hr",
        at_valid_time=T4,
        as_of_system_time=T4,
        policy_mode="promoted_only"
    )

    # Should return 2 facts (v1 and v3), not v2
    assert len(result.facts) == 2
    rule_ids = {f.logic_anchor.rule_id for f in result.facts}
    assert rule_ids == {"rule:salary_v1", "rule:salary_v3"}
    assert "rule:salary_v2" not in rule_ids
    print("PASS: Unpromoted rules are filtered")


# ===========================================================================
# Edge Cases
# ===========================================================================

def test_no_policy_head_returns_empty_result():
    """Edge case: No PolicyHead for namespace returns empty result with reason."""
    # Setup chain
    chain = create_chain("TestGraph", "corp", "test", system_time=T0)
    graph_id = chain.graph_id

    # Create namespace
    ns = create_namespace_definition(
        namespace="corp.hr",
        owner="role:chro",
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        system_time=T1
    )
    chain.append(ns)

    # Create fact (no PolicyHead created)
    fact = _create_fact_cell(
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        namespace="corp.hr",
        subject="employee:jane",
        predicate="has_salary",
        object_value="100000",
        rule_id="rule:salary_v1",
        system_time=T2
    )
    chain.append(fact)

    scholar = create_scholar(chain)

    # Query with policy_mode="promoted_only" (no PolicyHead exists)
    result = scholar.query_facts(
        requester_namespace="corp.hr",
        namespace="corp.hr",
        at_valid_time=T3,
        as_of_system_time=T3,
        policy_mode="promoted_only"
    )

    # Should return empty result with authorization.reason="no_policy_head"
    assert len(result.facts) == 0
    assert result.authorization.reason == "no_policy_head"
    assert result.policy_head_id is None
    print("PASS: No PolicyHead returns empty result with reason")


def test_empty_promoted_rule_ids_returns_no_facts():
    """Edge case: PolicyHead with empty promoted_rule_ids returns no facts."""
    # Setup chain
    chain = create_chain("TestGraph", "corp", "test", system_time=T0)
    graph_id = chain.graph_id

    # Create namespace
    ns = create_namespace_definition(
        namespace="corp.hr",
        owner="role:chro",
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        system_time=T1
    )
    chain.append(ns)

    # Create fact
    fact = _create_fact_cell(
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        namespace="corp.hr",
        subject="employee:jane",
        predicate="has_salary",
        object_value="100000",
        rule_id="rule:salary_v1",
        system_time=T2
    )
    chain.append(fact)

    # Create PolicyHead with empty promoted_rule_ids
    policy_head = create_policy_head(
        namespace="corp.hr",
        promoted_rule_ids=[],  # Empty - no rules promoted
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        prev_policy_head=None,
        system_time=T3
    )
    chain.append(policy_head)

    scholar = create_scholar(chain)

    # Query with policy_mode="promoted_only"
    result = scholar.query_facts(
        requester_namespace="corp.hr",
        namespace="corp.hr",
        at_valid_time=T4,
        as_of_system_time=T4,
        policy_mode="promoted_only"
    )

    # Should return no facts (no rules are promoted)
    assert len(result.facts) == 0
    assert result.policy_head_id == policy_head.cell_id
    print("PASS: Empty promoted_rule_ids returns no facts")


def test_scholar_refresh_picks_up_new_policy_head():
    """Success Criteria 5: Scholar auto-refreshes after PolicyHead append."""
    # Setup chain
    chain = create_chain("TestGraph", "corp", "test", system_time=T0)
    graph_id = chain.graph_id

    # Create namespace
    ns = create_namespace_definition(
        namespace="corp.hr",
        owner="role:chro",
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        system_time=T1
    )
    chain.append(ns)

    # Create fact
    fact = _create_fact_cell(
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        namespace="corp.hr",
        subject="employee:jane",
        predicate="has_salary",
        object_value="100000",
        rule_id="rule:salary_v1",
        system_time=T2
    )
    chain.append(fact)

    scholar = create_scholar(chain)

    # First query without PolicyHead
    result1 = scholar.query_facts(
        requester_namespace="corp.hr",
        namespace="corp.hr",
        at_valid_time=T3,
        as_of_system_time=T3,
        policy_mode="promoted_only"
    )
    assert len(result1.facts) == 0  # No PolicyHead yet

    # Add PolicyHead
    policy_head = create_policy_head(
        namespace="corp.hr",
        promoted_rule_ids=["rule:salary_v1"],
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        prev_policy_head=None,
        system_time=T3
    )
    chain.append(policy_head)

    # Refresh scholar (simulates auto-refresh pattern)
    scholar.refresh()

    # Query again - should now find PolicyHead
    result2 = scholar.query_facts(
        requester_namespace="corp.hr",
        namespace="corp.hr",
        at_valid_time=T4,
        as_of_system_time=T4,
        policy_mode="promoted_only"
    )
    assert len(result2.facts) == 1
    assert result2.policy_head_id == policy_head.cell_id
    print("PASS: Scholar.refresh() picks up new PolicyHead")


def test_policy_mode_with_different_namespaces():
    """Edge case: PolicyHead is namespace-specific, doesn't affect other namespaces."""
    # Setup chain
    chain = create_chain("TestGraph", "corp", "test", system_time=T0)
    graph_id = chain.graph_id

    # Create two namespaces
    ns_hr = create_namespace_definition(
        namespace="corp.hr",
        owner="role:chro",
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        system_time=T1
    )
    chain.append(ns_hr)

    ns_finance = create_namespace_definition(
        namespace="corp.finance",
        owner="role:cfo",
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        system_time=T1
    )
    chain.append(ns_finance)

    # Create fact in corp.hr
    fact_hr = _create_fact_cell(
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        namespace="corp.hr",
        subject="employee:jane",
        predicate="has_salary",
        object_value="100000",
        rule_id="rule:salary_v1",
        system_time=T2
    )
    chain.append(fact_hr)

    # Create fact in corp.finance
    fact_finance = _create_fact_cell(
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        namespace="corp.finance",
        subject="budget:2026",
        predicate="has_amount",
        object_value="1000000",
        rule_id="rule:budget_v1",
        system_time=T2
    )
    chain.append(fact_finance)

    # Create PolicyHead ONLY for corp.hr
    policy_head_hr = create_policy_head(
        namespace="corp.hr",
        promoted_rule_ids=["rule:salary_v1"],
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        prev_policy_head=None,
        system_time=T3
    )
    chain.append(policy_head_hr)

    scholar = create_scholar(chain)

    # Query corp.hr with policy_mode="promoted_only" - should work
    result_hr = scholar.query_facts(
        requester_namespace="corp.hr",
        namespace="corp.hr",
        at_valid_time=T4,
        as_of_system_time=T4,
        policy_mode="promoted_only"
    )
    assert len(result_hr.facts) == 1
    assert result_hr.policy_head_id == policy_head_hr.cell_id

    # Query corp.finance with policy_mode="promoted_only" - no PolicyHead
    result_finance = scholar.query_facts(
        requester_namespace="corp.finance",
        namespace="corp.finance",
        at_valid_time=T4,
        as_of_system_time=T4,
        policy_mode="promoted_only"
    )
    assert len(result_finance.facts) == 0  # No PolicyHead for finance
    assert result_finance.authorization.reason == "no_policy_head"

    print("PASS: PolicyHead is namespace-specific")


# ===========================================================================
# Main
# ===========================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  SCHOLAR POLICY-MODE TESTS (v1.5)")
    print("=" * 70)

    # SCH-01
    test_policy_mode_promoted_only_returns_only_promoted_rule_facts()
    test_policy_mode_all_returns_all_facts()

    # SCH-02
    test_bitemporal_policy_lookup_uses_as_of_system_time()

    # SCH-03
    test_query_result_includes_policy_head_id()
    test_query_result_policy_head_id_in_proof_bundle()
    test_query_result_policy_head_id_in_audit_text()

    # SCH-04
    test_unpromoted_rules_filtered()

    # Edge cases
    test_no_policy_head_returns_empty_result()
    test_empty_promoted_rule_ids_returns_no_facts()
    test_scholar_refresh_picks_up_new_policy_head()
    test_policy_mode_with_different_namespaces()

    print("\n" + "=" * 70)
    print("  ALL SCHOLAR POLICY-MODE TESTS PASSED")
    print("=" * 70)
