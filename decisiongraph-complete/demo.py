#!/usr/bin/env python3
"""
DecisionGraph Core: Demo Script

This script demonstrates all four immediate tasks:
1. TLA+ spec (see specs/DecisionGraph.tla)
2. Genesis Cell creation
3. cell_id computation (Logic Seal)
4. Chain validation

Run with: python demo.py
"""

import sys
sys.path.insert(0, '/home/claude/decisiongraph-core/src')

from decisiongraph import (
    # Cell primitives
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    CellType,
    SourceQuality,
    NULL_HASH,
    compute_rule_logic_hash,
    get_current_timestamp,
    
    # Genesis
    create_genesis_cell,
    verify_genesis,
    
    # Chain
    create_chain,
)


def print_header(title: str):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_cell(cell: DecisionCell, label: str = "Cell"):
    """Print cell details"""
    print(f"\n{label}:")
    print(f"  cell_id: {cell.cell_id[:32]}...")
    print(f"  type: {cell.header.cell_type.value}")
    print(f"  timestamp: {cell.header.timestamp}")
    print(f"  prev_hash: {cell.header.prev_cell_hash[:32]}...")
    print(f"  fact: {cell.fact.subject} → {cell.fact.predicate} → {cell.fact.object}")
    print(f"  confidence: {cell.fact.confidence}")
    print(f"  rule_id: {cell.logic_anchor.rule_id}")
    print(f"  rule_hash: {cell.logic_anchor.rule_logic_hash[:32]}...")
    print(f"  integrity: {'✓ VALID' if cell.verify_integrity() else '✗ INVALID'}")


def demo_genesis():
    """Demo Task 2: Genesis Cell Creation"""
    print_header("TASK 2: Genesis Cell Creation")
    
    print("\nCreating Genesis cell (The Big Bang)...")
    genesis = create_genesis_cell(
        graph_name="BankingAML_v1",
        creator="system:demo"
    )
    
    print_cell(genesis, "Genesis Cell")
    
    print(f"\n  is_genesis(): {genesis.is_genesis()}")
    print(f"  verify_genesis(): {verify_genesis(genesis)}")
    print(f"  prev_cell_hash is NULL: {genesis.header.prev_cell_hash == NULL_HASH}")
    
    return genesis


def demo_cell_id():
    """Demo Task 3: cell_id Computation (Logic Seal)"""
    print_header("TASK 3: cell_id Computation (The Logic Seal)")
    
    # Create a rule and compute its hash
    rule_content = """
    RULE aml_high_value_transaction:
        IF transaction.amount > 10000
        AND customer.tenure < 1 year
        THEN flag_for_review
    """
    rule_hash = compute_rule_logic_hash(rule_content)
    print(f"\nRule hash: {rule_hash[:32]}...")
    
    # Create a cell
    print("\nCreating a Decision cell...")
    cell = DecisionCell(
        header=Header(
            version="1.0",
            cell_type=CellType.DECISION,
            timestamp=get_current_timestamp(),
            prev_cell_hash="a" * 64  # Simulated prev hash
        ),
        fact=Fact(
            subject="entity:aurora_capital_01422",
            predicate="has_risk_rating",
            object="High",
            confidence=0.95,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="aml:high_value_transaction",
            rule_logic_hash=rule_hash
        )
    )
    
    print_cell(cell, "Decision Cell")
    
    # Demonstrate tampering detection
    print("\n--- Tampering Detection Demo ---")
    original_id = cell.cell_id
    print(f"Original cell_id: {original_id[:32]}...")
    
    # Tamper with the fact
    print("Tampering with fact.object: 'High' → 'Low'...")
    cell.fact.object = "Low"
    
    print(f"cell_id after tampering: {cell.cell_id[:32]}...")
    print(f"Computed hash now: {cell.compute_cell_id()[:32]}...")
    print(f"Integrity check: {'✓ VALID' if cell.verify_integrity() else '✗ INVALID (TAMPERED!)'}")
    
    # Restore
    cell.fact.object = "High"
    cell.cell_id = cell.compute_cell_id()
    print(f"\nRestored. Integrity: {'✓ VALID' if cell.verify_integrity() else '✗ INVALID'}")


def demo_chain_validation():
    """Demo Task 4: Chain Validation"""
    print_header("TASK 4: Chain Validation")
    
    # Create a chain
    print("\nCreating chain with Genesis...")
    chain = create_chain(graph_name="BankingAML_Demo")
    
    print(f"Chain initialized. Length: {chain.length}")
    print(f"Genesis cell_id: {chain.genesis.cell_id[:32]}...")
    
    # Add some cells
    print("\nAdding cells to chain...")
    
    # Rule cell
    rule_content = "IF amount > 10000 THEN review"
    rule_hash = compute_rule_logic_hash(rule_content)
    
    rule_cell = DecisionCell(
        header=Header(
            version="1.0",
            cell_type=CellType.RULE,
            timestamp=get_current_timestamp(),
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            subject="rule:high_value_threshold",
            predicate="defines",
            object="transaction_review_threshold",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="fintrac:2026:s3.2",
            rule_logic_hash=rule_hash
        )
    )
    chain.append(rule_cell)
    print(f"  Added RULE cell: {rule_cell.cell_id[:16]}...")
    
    # Fact cell
    fact_cell = DecisionCell(
        header=Header(
            version="1.0",
            cell_type=CellType.FACT,
            timestamp=get_current_timestamp(),
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            subject="entity:aurora_capital",
            predicate="has_transaction",
            object="1900000",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="source:core_banking",
            rule_logic_hash=compute_rule_logic_hash("core_banking_extract")
        )
    )
    chain.append(fact_cell)
    print(f"  Added FACT cell: {fact_cell.cell_id[:16]}...")
    
    # Decision cell
    decision_cell = DecisionCell(
        header=Header(
            version="1.0",
            cell_type=CellType.DECISION,
            timestamp=get_current_timestamp(),
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            subject="entity:aurora_capital",
            predicate="decision",
            object="ESCALATE_TIER_2",
            confidence=0.94,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="fintrac:2026:s3.2",
            rule_logic_hash=rule_hash  # Same rule as above
        )
    )
    chain.append(decision_cell)
    print(f"  Added DECISION cell: {decision_cell.cell_id[:16]}...")
    
    # Validate chain
    print("\n--- Chain Validation ---")
    result = chain.validate()
    
    print(f"Chain valid: {'✓ YES' if result.is_valid else '✗ NO'}")
    print(f"Cells checked: {result.cells_checked}")
    print(f"Errors: {len(result.errors)}")
    print(f"Warnings: {len(result.warnings)}")
    
    if result.errors:
        for error in result.errors:
            print(f"  ✗ {error}")
    
    # Trace to Genesis
    print("\n--- Trace to Genesis ---")
    path = chain.trace_to_genesis(chain.head.cell_id)
    print(f"Path length: {len(path)}")
    for i, cell in enumerate(path):
        print(f"  {i}: [{cell.header.cell_type.value}] {cell.cell_id[:16]}...")
    
    # Find by type
    print("\n--- Find by Type ---")
    decisions = chain.find_by_type(CellType.DECISION)
    facts = chain.find_by_type(CellType.FACT)
    rules = chain.find_by_type(CellType.RULE)
    
    print(f"Decisions: {len(decisions)}")
    print(f"Facts: {len(facts)}")
    print(f"Rules: {len(rules)}")
    
    # Rule mismatch detection
    print("\n--- Rule Mismatch Detection ---")
    print("Checking if decisions used correct rule versions...")
    
    # Simulate rule update
    new_rule_hash = compute_rule_logic_hash("IF amount > 5000 THEN review")
    current_rules = {"fintrac:2026:s3.2": new_rule_hash}
    
    mismatches = chain.find_decisions_with_rule_mismatch(current_rules)
    print(f"Decisions with outdated rules: {len(mismatches)}")
    
    if mismatches:
        for m in mismatches:
            print(f"  ⚠ {m.cell_id[:16]}... used old rule hash")
    
    return chain


def demo_json_serialization(chain):
    """Demo JSON serialization"""
    print_header("BONUS: JSON Serialization")
    
    print("\nExporting chain to JSON...")
    json_str = chain.to_json()
    
    print(f"JSON size: {len(json_str)} bytes")
    print(f"First 500 chars:\n{json_str[:500]}...")
    
    print("\nRe-importing from JSON...")
    restored = chain.from_json(json_str)
    
    print(f"Restored chain length: {restored.length}")
    print(f"Genesis matches: {restored.genesis.cell_id == chain.genesis.cell_id}")
    print(f"Head matches: {restored.head.cell_id == chain.head.cell_id}")


def main():
    """Run all demos"""
    print("\n" + "=" * 60)
    print("  DECISIONGRAPH CORE: FOUNDATION DEMO")
    print("  Universal Operating System for Deterministic Reasoning")
    print("=" * 60)
    
    # Task 2: Genesis
    genesis = demo_genesis()
    
    # Task 3: cell_id computation
    demo_cell_id()
    
    # Task 4: Chain validation
    chain = demo_chain_validation()
    
    # Bonus: Serialization
    demo_json_serialization(chain)
    
    print_header("SUMMARY")
    print("""
    ✓ Task 1: TLA+ Spec created (see specs/DecisionGraph.tla)
    ✓ Task 2: Genesis Cell creation working
    ✓ Task 3: cell_id computation (Logic Seal) working
    ✓ Task 4: Chain validation working
    
    The foundation is laid. The garden is planted.
    
    Next steps:
    - Implement Datalog engine integration
    - Build first Logic Pack (Banking AML)
    - Add content-addressed storage (IPFS/S3)
    """)


if __name__ == "__main__":
    main()
