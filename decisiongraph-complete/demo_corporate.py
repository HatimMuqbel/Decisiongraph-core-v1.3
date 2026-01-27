#!/usr/bin/env python3
"""
DecisionGraph Core: Corporate Governance Demo (v1.3)

This script demonstrates the Hierarchical Governance system:
- Namespaces for department isolation
- Access rules for permission control
- Bridge rules for cross-department queries
- The "Corporate Game of Thrones" solution

Run with: python demo_corporate.py
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from decisiongraph import (
    # Cell primitives
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    CellType,
    SourceQuality,
    compute_rule_logic_hash,
    get_current_timestamp,
    
    # Genesis & Chain
    create_chain,
    
    # Namespace
    Permission,
    Signature,
    NamespaceRegistry,
    create_namespace_definition,
    create_access_rule,
    create_bridge_rule,
    build_registry_from_chain,
    is_namespace_prefix,
    get_parent_namespace
)


def print_header(title: str):
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_cell(cell: DecisionCell, label: str = "Cell"):
    """Print cell details"""
    print(f"\n{label}:")
    print(f"  cell_id:   {cell.cell_id[:24]}...")
    print(f"  type:      {cell.header.cell_type.value}")
    print(f"  namespace: {cell.fact.namespace}")
    obj_display = str(cell.fact.object)[:50]
    print(f"  fact:      {cell.fact.subject} → {cell.fact.predicate} → {obj_display}")
    print(f"  integrity: {'✓ VALID' if cell.verify_integrity() else '✗ INVALID'}")


def demo_corporate_vault():
    """Demo the complete corporate governance system"""
    
    print_header("DECISIONGRAPH v1.2: CORPORATE GOVERNANCE DEMO")
    print("\nCore Principle: Namespace Isolation via Cryptographic Bridges")
    print("'Departments don't have to trust; they can verify the bridge.'")
    
    # =========================================================================
    # PHASE 1: Create the Corporate Vault
    # =========================================================================
    print_header("PHASE 1: Creating Corporate Vault (Genesis)")
    
    chain = create_chain(
        graph_name="AcmeCorp_DecisionGraph",
        root_namespace="acme",
        creator="system:initializer"
    )
    
    print(f"\n✓ Genesis created")
    print(f"  Root namespace: {chain.genesis.fact.namespace}")
    print(f"  Graph name: {chain.genesis.fact.object}")
    print(f"  cell_id: {chain.genesis.cell_id[:32]}...")
    
    # =========================================================================
    # PHASE 2: Define Department Namespaces
    # =========================================================================
    print_header("PHASE 2: Defining Department Namespaces")
    
    # HR namespace
    hr_ns = create_namespace_definition(
        namespace="acme.hr",
        owner="role:chro",
        sensitivity="confidential",
        parent_signer="role:ceo",
        prev_cell_hash=chain.head.cell_id,
        description="Human Resources department"
    )
    chain.append(hr_ns)
    print_cell(hr_ns, "HR Namespace")
    
    # HR Compensation (sensitive)
    hr_comp_ns = create_namespace_definition(
        namespace="acme.hr.compensation",
        owner="role:chro",
        sensitivity="restricted",
        parent_signer="role:chro",
        prev_cell_hash=chain.head.cell_id,
        description="Salary and compensation data"
    )
    chain.append(hr_comp_ns)
    print_cell(hr_comp_ns, "HR Compensation Namespace")
    
    # HR Performance
    hr_perf_ns = create_namespace_definition(
        namespace="acme.hr.performance",
        owner="role:hr_director",
        sensitivity="confidential",
        parent_signer="role:chro",
        prev_cell_hash=chain.head.cell_id,
        description="Performance review data"
    )
    chain.append(hr_perf_ns)
    print_cell(hr_perf_ns, "HR Performance Namespace")
    
    # Sales namespace
    sales_ns = create_namespace_definition(
        namespace="acme.sales",
        owner="role:vp_sales",
        sensitivity="internal",
        parent_signer="role:ceo",
        prev_cell_hash=chain.head.cell_id,
        description="Sales department"
    )
    chain.append(sales_ns)
    print_cell(sales_ns, "Sales Namespace")
    
    # Sales Discounts
    sales_disc_ns = create_namespace_definition(
        namespace="acme.sales.discounts",
        owner="role:vp_sales",
        sensitivity="confidential",
        parent_signer="role:vp_sales",
        prev_cell_hash=chain.head.cell_id,
        description="Discount approvals"
    )
    chain.append(sales_disc_ns)
    print_cell(sales_disc_ns, "Sales Discounts Namespace")
    
    # Marketing namespace
    marketing_ns = create_namespace_definition(
        namespace="acme.marketing",
        owner="role:cmo",
        sensitivity="internal",
        parent_signer="role:ceo",
        prev_cell_hash=chain.head.cell_id,
        description="Marketing department"
    )
    chain.append(marketing_ns)
    print_cell(marketing_ns, "Marketing Namespace")
    
    print("\n\nNamespace Hierarchy Created:")
    print("""
    acme (root)
    ├── hr (CHRO)
    │   ├── compensation (🔒 restricted)
    │   └── performance
    ├── sales (VP Sales)
    │   └── discounts
    └── marketing (CMO)
    """)
    
    # =========================================================================
    # PHASE 3: Add Access Rules
    # =========================================================================
    print_header("PHASE 3: Defining Access Rules")
    
    # Sales reps can read sales data
    sales_rep_access = create_access_rule(
        role="role:sales_rep",
        namespace="acme.sales",
        permission=Permission.READ,
        granted_by="role:vp_sales",
        prev_cell_hash=chain.head.cell_id
    )
    chain.append(sales_rep_access)
    print(f"\n✓ Sales reps can READ acme.sales.*")
    
    # HR managers can read HR data
    hr_manager_access = create_access_rule(
        role="role:hr_manager",
        namespace="acme.hr",
        permission=Permission.READ,
        granted_by="role:chro",
        prev_cell_hash=chain.head.cell_id
    )
    chain.append(hr_manager_access)
    print(f"✓ HR managers can READ acme.hr.*")
    
    # Only CHRO can read compensation
    chro_comp_access = create_access_rule(
        role="role:chro",
        namespace="acme.hr.compensation",
        permission=Permission.ADMIN,
        granted_by="role:ceo",
        prev_cell_hash=chain.head.cell_id
    )
    chain.append(chro_comp_access)
    print(f"✓ CHRO has ADMIN on acme.hr.compensation")
    
    # =========================================================================
    # PHASE 4: Add Business Facts
    # =========================================================================
    print_header("PHASE 4: Adding Business Facts")
    
    # HR Performance fact
    perf_fact = DecisionCell(
        header=Header(
            version="1.2",
            cell_type=CellType.FACT,
            timestamp=get_current_timestamp(),
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="acme.hr.performance",
            subject="employee:john_smith",
            predicate="performance_rating",
            object="2.5",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="source:hcm_system",
            rule_logic_hash=compute_rule_logic_hash("HCM Performance Export v3")
        )
    )
    chain.append(perf_fact)
    print_cell(perf_fact, "Performance Fact (HR)")
    
    # Sales discount request
    discount_fact = DecisionCell(
        header=Header(
            version="1.2",
            cell_type=CellType.FACT,
            timestamp=get_current_timestamp(),
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="acme.sales.discounts",
            subject="deal:acme_2026_001",
            predicate="discount_requested",
            object="0.30",
            confidence=1.0,
            source_quality=SourceQuality.SELF_REPORTED
        ),
        logic_anchor=LogicAnchor(
            rule_id="source:crm_system",
            rule_logic_hash=compute_rule_logic_hash("CRM Deal Export")
        )
    )
    chain.append(discount_fact)
    print_cell(discount_fact, "Discount Request (Sales)")
    
    # Sales rep assignment
    rep_fact = DecisionCell(
        header=Header(
            version="1.2",
            cell_type=CellType.FACT,
            timestamp=get_current_timestamp(),
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="acme.sales",
            subject="deal:acme_2026_001",
            predicate="assigned_rep",
            object="employee:john_smith",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="source:crm_system",
            rule_logic_hash=compute_rule_logic_hash("CRM Assignment")
        )
    )
    chain.append(rep_fact)
    print_cell(rep_fact, "Rep Assignment (Sales)")
    
    # =========================================================================
    # PHASE 5: Create Cross-Department Bridge
    # =========================================================================
    print_header("PHASE 5: Creating Cross-Department Bridge")
    
    print("\nSCENARIO: VP Sales wants to check rep performance before")
    print("          approving large discounts.")
    print("\nWithout bridge: ❌ ACCESS DENIED")
    print("Sales cannot see HR data.")
    
    # Build registry to check access
    registry = build_registry_from_chain(chain.cells)
    
    can_access, reason = registry.can_query_namespace(
        "acme.sales.discounts",
        "acme.hr.performance"
    )
    print(f"\nBefore bridge: can_query? {can_access} ({reason})")
    
    # Create the bridge with BOTH signatures
    print("\nCreating bridge with dual approval...")
    print("  • VP Sales (source owner) signs ✓")
    print("  • HR Director (target owner) signs ✓")
    
    vp_sales_sig = Signature(
        signer_id="role:vp_sales",
        signature="sig_vp_sales_abc123",
        timestamp=get_current_timestamp(),
        role="Source namespace owner"
    )
    
    hr_director_sig = Signature(
        signer_id="role:hr_director",
        signature="sig_hr_director_xyz789",
        timestamp=get_current_timestamp(),
        role="Target namespace owner"
    )
    
    bridge = create_bridge_rule(
        source_namespace="acme.sales",
        target_namespace="acme.hr.performance",
        source_owner_signature=vp_sales_sig,
        target_owner_signature=hr_director_sig,
        prev_cell_hash=chain.head.cell_id,
        purpose="Allow discount authority check based on rep performance"
    )
    chain.append(bridge)
    print_cell(bridge, "Bridge Rule")
    
    print("\nBridge Evidence (approvals sealed in cell):")
    for ev in bridge.evidence:
        print(f"  • {ev.description}")
    
    # Rebuild registry with bridge
    registry = build_registry_from_chain(chain.cells)
    
    can_access, reason = registry.can_query_namespace(
        "acme.sales.discounts",
        "acme.hr.performance"
    )
    print(f"\nAfter bridge: can_query? {can_access} ({reason})")
    
    # =========================================================================
    # PHASE 6: Cross-Department Query
    # =========================================================================
    print_header("PHASE 6: Cross-Department Query (The Payoff)")
    
    print("\nQUERY: 'Find deals where discount > 25% AND rep rating < 3.0'")
    print("\nThis requires crossing the bridge:")
    print("  1. Read discount requests from acme.sales.discounts")
    print("  2. Read rep assignments from acme.sales")
    print("  3. Cross bridge to acme.hr.performance")
    print("  4. Read performance ratings")
    print("  5. Join and filter")
    
    # Simulate the query logic
    print("\nQuery execution:")
    print("  ✓ acme.sales.discounts: deal:acme_2026_001 discount=0.30")
    print("  ✓ acme.sales: deal:acme_2026_001 rep=employee:john_smith")
    print("  ✓ Bridge check: acme.sales → acme.hr.performance = ALLOWED")
    print("  ✓ acme.hr.performance: employee:john_smith rating=2.5")
    print("  ✓ Filter: 0.30 > 0.25 AND 2.5 < 3.0 = TRUE")
    
    print("\n" + "─" * 50)
    print("  RESULT: deal:acme_2026_001 FLAGGED")
    print("  REASON: High discount (30%) + Low performer (2.5)")
    print("  ACTION: Requires VP Sales override")
    print("─" * 50)
    
    # =========================================================================
    # PHASE 7: Demonstrate Namespace Movement Protection
    # =========================================================================
    print_header("PHASE 7: Namespace Tamper Protection")
    
    print("\nATTACK: Try to move HR data to Sales namespace")
    print("        (to bypass access controls)")
    
    # Create a cell
    original_cell = DecisionCell(
        header=Header(
            version="1.2",
            cell_type=CellType.FACT,
            timestamp=get_current_timestamp(),
            prev_cell_hash=chain.head.cell_id
        ),
        fact=Fact(
            namespace="acme.hr.compensation",  # Original: HR
            subject="employee:jane_doe",
            predicate="has_salary",
            object="150000",
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="source:hcm_system",
            rule_logic_hash=compute_rule_logic_hash("HCM Payroll Export")
        )
    )
    
    original_id = original_cell.cell_id
    print(f"\nOriginal cell_id: {original_id[:32]}...")
    print(f"Original namespace: {original_cell.fact.namespace}")
    
    # Try to tamper with namespace
    print("\nTampering: changing namespace to 'acme.sales'...")
    original_cell.fact.namespace = "acme.sales"
    
    # Check integrity
    computed_id = original_cell.compute_cell_id()
    print(f"\nAfter tampering:")
    print(f"  Stored cell_id:   {original_id[:32]}...")
    print(f"  Computed cell_id: {computed_id[:32]}...")
    print(f"  Match: {original_id == computed_id}")
    print(f"  Integrity: {'✓ VALID' if original_cell.verify_integrity() else '✗ INVALID - TAMPERED!'}")
    
    print("\n🛡️ PROTECTION: Namespace is part of the Logic Seal.")
    print("   Moving a cell to a different namespace breaks the hash.")
    print("   The vault physically refuses tampered cells.")
    
    # =========================================================================
    # PHASE 8: Chain Validation
    # =========================================================================
    print_header("PHASE 8: Full Chain Validation")
    
    result = chain.validate()
    
    print(f"\nChain Statistics:")
    print(f"  Total cells: {chain.length}")
    print(f"  Valid: {'✓ YES' if result.is_valid else '✗ NO'}")
    print(f"  Errors: {len(result.errors)}")
    print(f"  Warnings: {len(result.warnings)}")
    
    print(f"\nCells by Type:")
    for cell_type in CellType:
        count = len(chain.find_by_type(cell_type))
        if count > 0:
            print(f"  {cell_type.value}: {count}")
    
    print(f"\nCells by Namespace:")
    namespaces = {}
    for cell in chain.cells:
        ns = cell.fact.namespace
        namespaces[ns] = namespaces.get(ns, 0) + 1
    for ns, count in sorted(namespaces.items()):
        print(f"  {ns}: {count}")
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    print_header("SUMMARY: The Corporate Constitution")
    
    print("""
    What we built:
    
    1. NAMESPACE ISOLATION
       • Each department owns its namespace
       • HR data stays in HR, Sales in Sales
       • No accidental data leakage
    
    2. ACCESS CONTROL AS CELLS
       • Permissions are auditable
       • Who granted what, when, to whom
       • All sealed in the vault
    
    3. CRYPTOGRAPHIC BRIDGES
       • Cross-department access requires BOTH owners
       • VP Sales AND HR Director must sign
       • The bridge itself is a tamper-proof cell
    
    4. NAMESPACE IN THE SEAL
       • Moving data breaks the hash
       • Location is as important as content
       • Physical protection, not just policy
    
    5. COMPLETE AUDIT TRAIL
       • Every fact, rule, decision, bridge
       • All traceable to Genesis
       • "Who knew what when" has an answer
    
    The Result:
    ─────────────────────────────────────────────────────────
    Departments don't have to TRUST each other.
    They can VERIFY the bridge.
    
    The database IS the constitution.
    ─────────────────────────────────────────────────────────
    """)
    
    return chain


def main():
    """Run the corporate governance demo"""
    chain = demo_corporate_vault()
    
    print_header("NEXT STEPS")
    print("""
    1. Task 5: Build the Datalog Resolver (The Scholar)
       - Namespace-aware queries
       - Bridge verification before cross-namespace reads
       - Full trace generation
    
    2. Implement v1.3 refinements:
       - graph_id binding (prevents cross-graph contamination)
       - system_time vs valid_time (clear bitemporal semantics)
       - Strict namespace regex validation
       - Canonicalized rule hashing
    
    3. Build first Logic Pack (Banking AML)
       - Rules as cells
       - Signals as facts
       - Decisions with traces
    """)


if __name__ == "__main__":
    main()
