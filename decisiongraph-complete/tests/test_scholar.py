#!/usr/bin/env python3
"""
DecisionGraph Core: Scholar Tests

The Definition of Done test:
> Given two conflicting salary facts for Jane in `corp.hr.compensation`, 
> the Scholar returns the same winning fact for the same `(valid_time, system_time)` 
> every run, and returns the bridge cell_id when querying across namespaces.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import time
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
    get_current_timestamp,
    compute_rule_logic_hash,
    
    # Namespace
    Signature,
    create_namespace_definition,
    create_bridge_rule,
    
    # Scholar
    Scholar,
    create_scholar,
    ResolutionReason
)


def test_scholar_conflict_resolution_deterministic():
    """
    DEFINITION OF DONE TEST:
    Two conflicting salary facts for Jane -> Scholar returns same winner every time
    """
    print("\n" + "=" * 60)
    print("  TEST: Deterministic Conflict Resolution")
    print("=" * 60)
    
    # Create chain
    chain = create_chain(
        graph_name="TestCorp",
        root_namespace="corp",
        creator="test"
    )
    graph_id = chain.graph_id
    
    # Create HR namespace
    hr_ns = create_namespace_definition(
        namespace="corp.hr",
        owner="role:chro",
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id
    )
    chain.append(hr_ns)
    
    # Create compensation namespace
    comp_ns = create_namespace_definition(
        namespace="corp.hr.compensation",
        owner="role:chro",
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id
    )
    chain.append(comp_ns)
    
    # Add first salary fact (self_reported, confidence 0.8)
    ts1 = get_current_timestamp()
    salary_fact_1 = DecisionCell(
        header=Header(
            version="1.3",
            graph_id=graph_id,
            cell_type=CellType.FACT,
            system_time=ts1,
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="corp.hr.compensation",
            subject="employee:jane_doe",
            predicate="has_salary",
            object="140000",
            confidence=0.8,
            source_quality=SourceQuality.SELF_REPORTED,
            valid_from=ts1
        ),
        logic_anchor=LogicAnchor(
            rule_id="source:employee_portal",
            rule_logic_hash=compute_rule_logic_hash("Employee self-service")
        ),
        proof=Proof(signer_id="employee:jane_doe")
    )
    chain.append(salary_fact_1)
    print(f"\n✓ Added salary fact 1: $140,000 (self_reported, confidence 0.8)")
    
    # Small delay to ensure different timestamp
    time.sleep(0.01)
    
    # Add second salary fact (verified, confidence 1.0) - should win
    ts2 = get_current_timestamp()
    salary_fact_2 = DecisionCell(
        header=Header(
            version="1.3",
            graph_id=graph_id,
            cell_type=CellType.FACT,
            system_time=ts2,
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="corp.hr.compensation",
            subject="employee:jane_doe",
            predicate="has_salary",
            object="150000",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED,
            valid_from=ts2
        ),
        logic_anchor=LogicAnchor(
            rule_id="source:hris_system",
            rule_logic_hash=compute_rule_logic_hash("HRIS Export")
        ),
        proof=Proof(signer_id="system:hris")
    )
    chain.append(salary_fact_2)
    print(f"✓ Added salary fact 2: $150,000 (verified, confidence 1.0)")
    
    # Create Scholar
    scholar = create_scholar(chain)
    
    # Query - should consistently return the verified fact
    results = []
    for i in range(5):
        result = scholar.query_facts(
            requester_namespace="corp.hr.compensation",
            namespace="corp.hr.compensation",
            subject="employee:jane_doe",
            predicate="has_salary"
        )
        results.append(result)
    
    # All results should be identical
    print(f"\n--- Query Results (5 runs) ---")
    print(f"  Candidates: {results[0].candidates.__len__()}")
    print(f"  Winners: {results[0].facts.__len__()}")
    
    # Check determinism
    winner_ids = [r.facts[0].cell_id if r.facts else None for r in results]
    assert len(set(winner_ids)) == 1, "Non-deterministic results!"
    print(f"  Winner cell_id: {winner_ids[0][:24]}... (same all 5 runs)")
    
    # Check winner is the verified one
    winner = results[0].facts[0]
    assert winner.fact.object == "150000", f"Wrong winner: {winner.fact.object}"
    assert winner.fact.source_quality == SourceQuality.VERIFIED
    print(f"  Winner value: ${winner.fact.object}")
    print(f"  Winner quality: {winner.fact.source_quality.value}")
    
    # Check resolution reason
    resolution = results[0].resolution_events[0]
    assert resolution.reason == ResolutionReason.QUALITY_WIN
    print(f"  Resolution reason: {resolution.reason.value}")
    
    print("\n✓ TEST PASSED: Conflict resolution is deterministic")
    return True


def test_scholar_bridge_enforcement():
    """
    DEFINITION OF DONE TEST:
    Cross-namespace query returns bridge cell_id in proof
    """
    print("\n" + "=" * 60)
    print("  TEST: Bridge Enforcement")
    print("=" * 60)
    
    # Create chain
    chain = create_chain(
        graph_name="TestCorp",
        root_namespace="corp",
        creator="test"
    )
    graph_id = chain.graph_id
    
    # Create HR namespace
    hr_ns = create_namespace_definition(
        namespace="corp.hr",
        owner="role:chro",
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id
    )
    chain.append(hr_ns)
    
    # Create HR performance namespace
    perf_ns = create_namespace_definition(
        namespace="corp.hr.performance",
        owner="role:hr_director",
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id
    )
    chain.append(perf_ns)
    
    # Create Sales namespace
    sales_ns = create_namespace_definition(
        namespace="corp.sales",
        owner="role:vp_sales",
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id
    )
    chain.append(sales_ns)
    
    # Add performance fact in HR
    ts = get_current_timestamp()
    perf_fact = DecisionCell(
        header=Header(
            version="1.3",
            graph_id=graph_id,
            cell_type=CellType.FACT,
            system_time=ts,
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="corp.hr.performance",
            subject="employee:john_smith",
            predicate="performance_rating",
            object="2.5",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED,
            valid_from=ts
        ),
        logic_anchor=LogicAnchor(
            rule_id="source:hcm_system",
            rule_logic_hash=compute_rule_logic_hash("HCM Export")
        ),
        proof=Proof(signer_id="system:hcm")
    )
    chain.append(perf_fact)
    print(f"\n✓ Added performance fact for John: rating 2.5")
    
    # Create Scholar
    scholar = create_scholar(chain)
    
    # Query WITHOUT bridge - should fail
    result_no_bridge = scholar.query_facts(
        requester_namespace="corp.sales",
        namespace="corp.hr.performance",
        subject="employee:john_smith",
        predicate="performance_rating"
    )
    
    print(f"\n--- Query WITHOUT Bridge ---")
    print(f"  Results: {len(result_no_bridge.facts)}")
    assert len(result_no_bridge.facts) == 0, "Should not see HR data without bridge!"
    print(f"  ✓ Access denied (no bridge)")
    
    # Create bridge
    bridge = create_bridge_rule(
        source_namespace="corp.sales",
        target_namespace="corp.hr.performance",
        source_owner_signature=Signature(
            signer_id="role:vp_sales",
            signature="sig_vp_sales",
            timestamp=ts
        ),
        target_owner_signature=Signature(
            signer_id="role:hr_director",
            signature="sig_hr_director",
            timestamp=ts
        ),
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id,
        purpose="Check performance for discount authority"
    )
    chain.append(bridge)
    print(f"\n✓ Created bridge: corp.sales -> corp.hr.performance")
    print(f"  Bridge cell_id: {bridge.cell_id[:24]}...")
    
    # Refresh Scholar
    scholar.refresh()
    
    # Query WITH bridge - should succeed and include bridge in proof
    result_with_bridge = scholar.query_facts(
        requester_namespace="corp.sales",
        namespace="corp.hr.performance",
        subject="employee:john_smith",
        predicate="performance_rating"
    )
    
    print(f"\n--- Query WITH Bridge ---")
    print(f"  Results: {len(result_with_bridge.facts)}")
    assert len(result_with_bridge.facts) == 1, "Should see HR data with bridge!"
    
    print(f"  Bridges used: {len(result_with_bridge.bridges_used)}")
    assert len(result_with_bridge.bridges_used) == 1, "Should have bridge in proof!"
    assert result_with_bridge.bridges_used[0] == bridge.cell_id
    print(f"  Bridge cell_id in proof: {result_with_bridge.bridges_used[0][:24]}...")
    
    # Get the fact
    fact = result_with_bridge.facts[0]
    print(f"  Fact: {fact.fact.subject} {fact.fact.predicate} = {fact.fact.object}")
    
    print("\n✓ TEST PASSED: Bridge enforcement with proof")
    return True


def test_scholar_bitemporal_query():
    """
    Test bitemporal queries (valid_time + system_time)
    """
    print("\n" + "=" * 60)
    print("  TEST: Bitemporal Queries")
    print("=" * 60)
    
    chain = create_chain(
        graph_name="TestCorp",
        root_namespace="corp",
        creator="test"
    )
    graph_id = chain.graph_id
    
    # Create HR namespace
    hr_ns = create_namespace_definition(
        namespace="corp.hr",
        owner="role:chro",
        graph_id=graph_id,
        prev_cell_hash=chain.head.cell_id
    )
    chain.append(hr_ns)
    
    # First fact: Jane's title is "Engineer" (valid from past, ends in future)
    ts1 = get_current_timestamp()
    title_jan = DecisionCell(
        header=Header(
            version="1.3",
            graph_id=graph_id,
            cell_type=CellType.FACT,
            system_time=ts1,
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="corp.hr",
            subject="employee:jane_doe",
            predicate="has_title",
            object="Engineer",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED,
            valid_from="2025-01-01T00:00:00Z",  # Valid from Jan 2025
            valid_to="2025-06-01T00:00:00Z"     # Until June 2025
        ),
        logic_anchor=LogicAnchor(
            rule_id="source:hris",
            rule_logic_hash=compute_rule_logic_hash("HRIS")
        ),
        proof=Proof(signer_id="system:hris")
    )
    chain.append(title_jan)
    print(f"\n✓ Added: Jane = Engineer (valid Jan-May 2025)")
    
    time.sleep(0.01)
    
    # Second fact: Jane promoted to "Senior Engineer" (valid from June 2025)
    ts2 = get_current_timestamp()
    title_feb = DecisionCell(
        header=Header(
            version="1.3",
            graph_id=graph_id,
            cell_type=CellType.FACT,
            system_time=ts2,
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="corp.hr",
            subject="employee:jane_doe",
            predicate="has_title",
            object="Senior Engineer",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED,
            valid_from="2025-06-01T00:00:00Z",  # Valid from June 2025
            valid_to=None  # Still valid (forever)
        ),
        logic_anchor=LogicAnchor(
            rule_id="source:hris",
            rule_logic_hash=compute_rule_logic_hash("HRIS")
        ),
        proof=Proof(signer_id="system:hris")
    )
    chain.append(title_feb)
    print(f"✓ Added: Jane = Senior Engineer (valid June 2025 onwards)")
    
    scholar = create_scholar(chain)
    
    # Query for March 2025 - should return "Engineer"
    result_mar = scholar.query_facts(
        requester_namespace="corp.hr",
        namespace="corp.hr",
        subject="employee:jane_doe",
        predicate="has_title",
        at_valid_time="2025-03-15T00:00:00Z"
    )
    
    print(f"\n--- Query: What was Jane's title in March 2025? ---")
    assert len(result_mar.facts) == 1, f"Expected 1 fact, got {len(result_mar.facts)}"
    assert result_mar.facts[0].fact.object == "Engineer"
    print(f"  Result: {result_mar.facts[0].fact.object}")
    
    # Query for August 2025 - should return "Senior Engineer"
    result_aug = scholar.query_facts(
        requester_namespace="corp.hr",
        namespace="corp.hr",
        subject="employee:jane_doe",
        predicate="has_title",
        at_valid_time="2025-08-15T00:00:00Z"
    )
    
    print(f"\n--- Query: What is Jane's title in August 2025? ---")
    assert len(result_aug.facts) == 1, f"Expected 1 fact, got {len(result_aug.facts)}"
    assert result_aug.facts[0].fact.object == "Senior Engineer"
    print(f"  Result: {result_aug.facts[0].fact.object}")
    
    print("\n✓ TEST PASSED: Bitemporal queries work correctly")
    return True


def test_scholar_proof_bundle():
    """
    Test proof bundle generation
    """
    print("\n" + "=" * 60)
    print("  TEST: Proof Bundle Generation")
    print("=" * 60)

    chain = create_chain(
        graph_name="TestCorp",
        root_namespace="corp",
        creator="test"
    )
    graph_id = chain.graph_id

    # Add a fact
    ts = get_current_timestamp()
    fact = DecisionCell(
        header=Header(
            version="1.3",
            graph_id=graph_id,
            cell_type=CellType.FACT,
            system_time=ts,
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="corp",
            subject="company:acme",
            predicate="has_employee_count",
            object="500",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED,
            valid_from=ts
        ),
        logic_anchor=LogicAnchor(
            rule_id="source:hr_report",
            rule_logic_hash=compute_rule_logic_hash("HR Report")
        ),
        proof=Proof(signer_id="system:hr")
    )
    chain.append(fact)

    scholar = create_scholar(chain)

    result = scholar.query_facts(
        requester_namespace="corp",
        namespace="corp",
        subject="company:acme",
        predicate="has_employee_count",
        requester_id="user:auditor"
    )

    # Generate proof bundle
    proof_bundle = result.to_proof_bundle()

    print(f"\n--- Proof Bundle ---")
    print(f"  Query namespace: {proof_bundle['query']['namespace_scope']}")
    print(f"  Requester: {proof_bundle['query']['requester_id']}")
    print(f"  Facts returned: {proof_bundle['results']['fact_count']}")
    print(f"  Candidates considered: {proof_bundle['proof']['candidates_considered']}")
    print(f"  Bridges used: {len(proof_bundle['proof']['bridges_used'])}")
    print(f"  Scholar version: {proof_bundle['scholar_version']}")
    print(f"  Authorization: {proof_bundle['authorization_basis']['reason']}")

    assert proof_bundle['query']['requester_id'] == 'user:auditor'
    assert proof_bundle['results']['fact_count'] == 1
    assert proof_bundle['scholar_version'] == '1.0'
    assert 'authorization_basis' in proof_bundle

    print("\n✓ TEST PASSED: Proof bundle generated")
    return True


def test_tiebreak_quality():
    """
    Test that higher source_quality wins when all else is equal.
    Two facts, same confidence/time/cell_id prefix, different source_quality.
    """
    print("\n" + "=" * 60)
    print("  TEST: Tiebreak by Source Quality")
    print("=" * 60)

    chain = create_chain(
        graph_name="TestCorp",
        root_namespace="corp",
        creator="test"
    )
    graph_id = chain.graph_id

    # Use current timestamp so chain temporal ordering is respected
    fixed_ts = get_current_timestamp()

    # Fact 1: INFERRED quality (lower)
    fact_inferred = DecisionCell(
        header=Header(
            version="1.3",
            graph_id=graph_id,
            cell_type=CellType.FACT,
            system_time=fixed_ts,
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="corp",
            subject="entity:test",
            predicate="score",
            object="100",
            confidence=0.9,
            source_quality=SourceQuality.INFERRED,
            valid_from=fixed_ts
        ),
        logic_anchor=LogicAnchor(
            rule_id="rule:test",
            rule_logic_hash=compute_rule_logic_hash("test")
        ),
        proof=Proof(signer_id="system:test")
    )
    chain.append(fact_inferred)

    # Fact 2: VERIFIED quality (higher) - same confidence, time
    fact_verified = DecisionCell(
        header=Header(
            version="1.3",
            graph_id=graph_id,
            cell_type=CellType.FACT,
            system_time=fixed_ts,
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="corp",
            subject="entity:test",
            predicate="score",
            object="200",
            confidence=0.9,
            source_quality=SourceQuality.VERIFIED,
            valid_from=fixed_ts
        ),
        logic_anchor=LogicAnchor(
            rule_id="rule:test",
            rule_logic_hash=compute_rule_logic_hash("test")
        ),
        proof=Proof(signer_id="system:test")
    )
    chain.append(fact_verified)

    scholar = create_scholar(chain)
    result = scholar.query_facts(
        requester_namespace="corp",
        namespace="corp",
        subject="entity:test",
        predicate="score"
    )

    print(f"\n  Candidates: {len(result.candidates)}")
    print(f"  Winner value: {result.facts[0].fact.object}")
    print(f"  Winner quality: {result.facts[0].fact.source_quality.value}")
    print(f"  Resolution reason: {result.resolution_events[0].reason.value}")

    assert len(result.facts) == 1
    assert result.facts[0].fact.object == "200"
    assert result.facts[0].fact.source_quality == SourceQuality.VERIFIED
    assert result.resolution_events[0].reason == ResolutionReason.QUALITY_WIN

    print("\n✓ TEST PASSED: Higher quality wins")
    return True


def test_tiebreak_confidence():
    """
    Test that higher confidence wins when quality is equal.
    Two facts, same quality/time/cell_id prefix, different confidence.
    """
    print("\n" + "=" * 60)
    print("  TEST: Tiebreak by Confidence")
    print("=" * 60)

    chain = create_chain(
        graph_name="TestCorp",
        root_namespace="corp",
        creator="test"
    )
    graph_id = chain.graph_id

    fixed_ts = get_current_timestamp()

    # Fact 1: lower confidence
    fact_low = DecisionCell(
        header=Header(
            version="1.3",
            graph_id=graph_id,
            cell_type=CellType.FACT,
            system_time=fixed_ts,
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="corp",
            subject="entity:conf",
            predicate="value",
            object="low",
            confidence=0.7,
            source_quality=SourceQuality.VERIFIED,
            valid_from=fixed_ts
        ),
        logic_anchor=LogicAnchor(
            rule_id="rule:test",
            rule_logic_hash=compute_rule_logic_hash("test")
        ),
        proof=Proof(signer_id="system:test")
    )
    chain.append(fact_low)

    # Fact 2: higher confidence (same quality, time)
    fact_high = DecisionCell(
        header=Header(
            version="1.3",
            graph_id=graph_id,
            cell_type=CellType.FACT,
            system_time=fixed_ts,
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="corp",
            subject="entity:conf",
            predicate="value",
            object="high",
            confidence=0.95,
            source_quality=SourceQuality.VERIFIED,
            valid_from=fixed_ts
        ),
        logic_anchor=LogicAnchor(
            rule_id="rule:test",
            rule_logic_hash=compute_rule_logic_hash("test")
        ),
        proof=Proof(signer_id="system:test")
    )
    chain.append(fact_high)

    scholar = create_scholar(chain)
    result = scholar.query_facts(
        requester_namespace="corp",
        namespace="corp",
        subject="entity:conf",
        predicate="value"
    )

    print(f"\n  Candidates: {len(result.candidates)}")
    print(f"  Winner value: {result.facts[0].fact.object}")
    print(f"  Winner confidence: {result.facts[0].fact.confidence}")
    print(f"  Resolution reason: {result.resolution_events[0].reason.value}")

    assert len(result.facts) == 1
    assert result.facts[0].fact.object == "high"
    assert result.facts[0].fact.confidence == 0.95
    assert result.resolution_events[0].reason == ResolutionReason.CONFIDENCE_WIN

    print("\n✓ TEST PASSED: Higher confidence wins")
    return True


def test_tiebreak_recency():
    """
    Test that later system_time wins when quality and confidence are equal.
    Two facts, same quality/confidence/cell_id prefix, different system_time.
    """
    print("\n" + "=" * 60)
    print("  TEST: Tiebreak by Recency (system_time)")
    print("=" * 60)

    chain = create_chain(
        graph_name="TestCorp",
        root_namespace="corp",
        creator="test"
    )
    graph_id = chain.graph_id

    # Fact 1: earlier timestamp
    early_ts = get_current_timestamp()
    fact_early = DecisionCell(
        header=Header(
            version="1.3",
            graph_id=graph_id,
            cell_type=CellType.FACT,
            system_time=early_ts,
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="corp",
            subject="entity:time",
            predicate="status",
            object="old",
            confidence=0.9,
            source_quality=SourceQuality.VERIFIED,
            valid_from=early_ts
        ),
        logic_anchor=LogicAnchor(
            rule_id="rule:test",
            rule_logic_hash=compute_rule_logic_hash("test")
        ),
        proof=Proof(signer_id="system:test")
    )
    chain.append(fact_early)

    # Small delay to ensure different timestamp
    time.sleep(0.01)

    # Fact 2: later timestamp (same quality, confidence)
    late_ts = get_current_timestamp()
    fact_late = DecisionCell(
        header=Header(
            version="1.3",
            graph_id=graph_id,
            cell_type=CellType.FACT,
            system_time=late_ts,
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="corp",
            subject="entity:time",
            predicate="status",
            object="new",
            confidence=0.9,
            source_quality=SourceQuality.VERIFIED,
            valid_from=late_ts
        ),
        logic_anchor=LogicAnchor(
            rule_id="rule:test",
            rule_logic_hash=compute_rule_logic_hash("test")
        ),
        proof=Proof(signer_id="system:test")
    )
    chain.append(fact_late)

    scholar = create_scholar(chain)
    result = scholar.query_facts(
        requester_namespace="corp",
        namespace="corp",
        subject="entity:time",
        predicate="status"
    )

    print(f"\n  Candidates: {len(result.candidates)}")
    print(f"  Winner value: {result.facts[0].fact.object}")
    print(f"  Winner system_time: {result.facts[0].header.system_time}")
    print(f"  Resolution reason: {result.resolution_events[0].reason.value}")

    assert len(result.facts) == 1
    assert result.facts[0].fact.object == "new"
    assert result.facts[0].header.system_time == late_ts
    assert result.resolution_events[0].reason == ResolutionReason.RECENCY_WIN

    print("\n✓ TEST PASSED: Later system_time wins")
    return True


def test_tiebreak_cell_id():
    """
    Test that lexicographically smaller cell_id wins when all else is equal.
    Two facts, same quality/confidence/time, different cell_id.
    """
    print("\n" + "=" * 60)
    print("  TEST: Tiebreak by Cell ID (lexicographic)")
    print("=" * 60)

    chain = create_chain(
        graph_name="TestCorp",
        root_namespace="corp",
        creator="test"
    )
    graph_id = chain.graph_id

    fixed_ts = get_current_timestamp()

    # We'll create two facts with same quality/confidence/time
    # The cell_id is computed from content, so we need different objects
    # but we'll verify which cell_id is smaller and that one should win

    fact_a = DecisionCell(
        header=Header(
            version="1.3",
            graph_id=graph_id,
            cell_type=CellType.FACT,
            system_time=fixed_ts,
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="corp",
            subject="entity:cellid",
            predicate="data",
            object="value_a",
            confidence=0.9,
            source_quality=SourceQuality.VERIFIED,
            valid_from=fixed_ts
        ),
        logic_anchor=LogicAnchor(
            rule_id="rule:test",
            rule_logic_hash=compute_rule_logic_hash("test")
        ),
        proof=Proof(signer_id="system:test")
    )
    chain.append(fact_a)

    fact_b = DecisionCell(
        header=Header(
            version="1.3",
            graph_id=graph_id,
            cell_type=CellType.FACT,
            system_time=fixed_ts,
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="corp",
            subject="entity:cellid",
            predicate="data",
            object="value_b",
            confidence=0.9,
            source_quality=SourceQuality.VERIFIED,
            valid_from=fixed_ts
        ),
        logic_anchor=LogicAnchor(
            rule_id="rule:test",
            rule_logic_hash=compute_rule_logic_hash("test")
        ),
        proof=Proof(signer_id="system:test")
    )
    chain.append(fact_b)

    # Determine which cell_id is smaller
    expected_winner = fact_a if fact_a.cell_id < fact_b.cell_id else fact_b

    scholar = create_scholar(chain)
    result = scholar.query_facts(
        requester_namespace="corp",
        namespace="corp",
        subject="entity:cellid",
        predicate="data"
    )

    print(f"\n  Candidates: {len(result.candidates)}")
    print(f"  Fact A cell_id: {fact_a.cell_id[:32]}...")
    print(f"  Fact B cell_id: {fact_b.cell_id[:32]}...")
    print(f"  Winner cell_id: {result.facts[0].cell_id[:32]}...")
    print(f"  Expected winner: {expected_winner.fact.object}")
    print(f"  Resolution reason: {result.resolution_events[0].reason.value}")

    assert len(result.facts) == 1
    assert result.facts[0].cell_id == expected_winner.cell_id
    assert result.resolution_events[0].reason == ResolutionReason.HASH_TIEBREAK

    print("\n✓ TEST PASSED: Lexicographically smaller cell_id wins")
    return True


def run_all_tests():
    """Run all Scholar tests"""
    print("\n" + "=" * 60)
    print("  SCHOLAR (RESOLVER) TESTS")
    print("=" * 60)

    tests = [
        test_scholar_conflict_resolution_deterministic,
        test_scholar_bridge_enforcement,
        test_scholar_bitemporal_query,
        test_scholar_proof_bundle,
        # Tiebreaker tests
        test_tiebreak_quality,
        test_tiebreak_confidence,
        test_tiebreak_recency,
        test_tiebreak_cell_id,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"\n✗ TEST FAILED: {test.__name__}")
            print(f"  Error: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"  RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("\n  THE SCHOLAR IS REAL. ✓")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
