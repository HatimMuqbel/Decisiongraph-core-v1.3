# DecisionGraph Architecture

## Overview

DecisionGraph is a **Universal Operating System for Deterministic Reasoning**. It provides:

1. **Cryptographic Integrity**: Every cell's ID is derived from its content
2. **Graph Isolation**: Cells are bound to specific graph instances
3. **Namespace Isolation**: Departments are isolated by hierarchical paths
4. **Complete Audit Trail**: Every cell traces back to Genesis
5. **Bitemporal Queries**: "What was true when" vs "what did we know when"

## Code Organization (v1.3)

v1.3 restructures the codebase into three physical layers:

```
decisiongraph-complete/src/
├── kernel/                    # Source of truth — domain-portable primitives
│   ├── foundation/  (11)      #   cell, chain, genesis, signing, WAL, etc.
│   ├── precedent/   (6)       #   registry, scorer, confidence, comparators
│   ├── policy/      (3)       #   simulation, regime detection
│   ├── evidence/    (2)       #   TriBool, evidence gate
│   └── calendars/   (3)       #   US federal, Ontario holidays
│
├── domains/                   # Domain-specific implementations
│   ├── banking_aml/           #   field registry, seeds, fingerprints, reason codes
│   └── insurance_claims/      #   (stub — future)
│
└── decisiongraph/             # Backward-compatible re-export shims
    └── *.py → kernel.* / domains.*
```

- **`kernel/`** contains all domain-portable decision primitives (26 modules)
- **`domains/`** contains domain-specific logic (6 banking AML modules)
- **`decisiongraph/`** contains thin re-export shims (25 files) so existing imports keep working

See `SCHEMA_V1.3.md` for the full migration record, commit history, and shim pattern.

## The Eight Layers

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 8: USER/LLM INTERFACE                                │
│           Natural language queries, chat interfaces          │
├─────────────────────────────────────────────────────────────┤
│  Layer 7: LOGIC PACKS                                       │
│           Domain-specific rules (Banking, HR, Sales, etc.)   │
├─────────────────────────────────────────────────────────────┤
│  Layer 6: PRODUCT FEATURES                                  │
│           Precedent System, Logic Pack Manager, Simulation   │
├─────────────────────────────────────────────────────────────┤
│  Layer 5: RESOLVER (The Scholar)                            │
│           Query, Traverse, Infer, Resolve conflicts          │
├─────────────────────────────────────────────────────────────┤
│  Layer 4: GOVERNANCE                                        │
│           Namespaces, Access Rules, Bridges                  │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: COMMIT GATE                                       │
│           Validates all appends to chain                     │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: CHAIN                                             │
│           Append-only log, hash-linked                       │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: DECISION-CELL                                     │
│           Atomic unit with Logic Seal                        │
└─────────────────────────────────────────────────────────────┘
```

## Layer 1: Decision-Cell

The atomic unit of DecisionGraph. A cryptographically sealed packet.

### Cell Types

| Type | Purpose |
|------|---------|
| `GENESIS` | First cell, establishes graph identity |
| `FACT` | Records a single fact (subject-predicate-object) |
| `RULE` | Defines logic/policy rules |
| `INFERENCE` | Derived fact from rule application |
| `ACCESS_RULE` | Namespace access permissions |
| `BRIDGE_RULE` | Cross-namespace access authorization |
| `RETRACTION` | Invalidates a previous cell |
| `JUDGMENT` | Sealed decision for precedent matching |
| `WITNESS_SET` | Immutable collection of related cells |

### Structure

```
DecisionCell
├── header
│   ├── version: "1.3"
│   ├── graph_id: "graph:uuid-v4"      # Binds to graph
│   ├── cell_type: CellType enum
│   ├── system_time: ISO 8601 UTC      # When recorded
│   └── prev_cell_hash: SHA256         # Chain link
├── fact
│   ├── namespace: "corp.hr.compensation"
│   ├── subject: "employee:jane_doe"
│   ├── predicate: "has_salary"
│   ├── object: "150000"
│   ├── confidence: 0.0-1.0
│   ├── source_quality: verified|self_reported|inferred
│   ├── valid_from: ISO 8601           # When fact became true
│   └── valid_to: ISO 8601 | null      # When fact stopped being true
├── logic_anchor
│   ├── rule_id: "policy:salary_bands"
│   ├── rule_logic_hash: SHA256        # Version of rule used
│   └── interpreter: "datalog:v2"
├── evidence: []
│   └── Evidence { type, cid, source, payload_hash, description }
└── proof
    ├── signer_id: "role:hr_manager"
    ├── signer_key_id: "key:..."
    ├── signature: "sig:..."
    ├── merkle_root: SHA256
    └── signature_required: bool
```

### The Logic Seal

The `cell_id` is DERIVED, not assigned:

```
cell_id = SHA256(
    header.version +
    header.graph_id +
    header.cell_type +
    header.system_time +
    header.prev_cell_hash +
    fact.namespace +
    fact.subject +
    fact.predicate +
    fact.object +
    logic_anchor.rule_id +
    logic_anchor.rule_logic_hash
)
```

**Properties**:
- Change any field → hash changes → tampering detected
- Namespace is in the seal → moving cell breaks hash
- graph_id is in the seal → cross-graph copy breaks hash

## Layer 2: Chain

Append-only log linking cells together.

```
[Genesis] ← [Cell 1] ← [Cell 2] ← [Cell 3] ← ... ← [Head]
    │           │           │           │
    └───────────┴───────────┴───────────┴── prev_cell_hash links
```

**Properties**:
- Every cell points to its predecessor
- Only Genesis has prev_cell_hash = NULL_HASH
- Timestamps must be monotonically increasing

## Layer 3: Commit Gate

The gatekeeper that validates every append.

### Rules Enforced

| Rule | Error If Violated |
|------|-------------------|
| Genesis must be first | `GenesisViolation` |
| Only one Genesis | `GenesisViolation` |
| graph_id must match | `GraphIdMismatch` |
| prev_cell_hash must exist | `ChainBreak` |
| cell_id must be valid | `IntegrityViolation` |
| system_time >= previous | `TemporalViolation` |

### Why graph_id Matters

Without graph_id binding:
```
Graph A: [Genesis_A] → [Cell_1] → [Cell_2]
Graph B: [Genesis_B] → [Cell_3] → [Cell_4]

Attack: Mix cells
[Genesis_A] → [Cell_1] → [Cell_4]  ← WRONG GRAPH!
```

With graph_id binding:
```
Cell_4.header.graph_id = "graph:B"
Chain_A.graph_id = "graph:A"
Commit Gate: REJECT (graph_id mismatch)
```

## Layer 4: Governance

### Namespaces

Hierarchical paths for department isolation:

```
corp (root)
├── hr
│   ├── compensation    (🔒 restricted)
│   ├── performance
│   └── training
├── sales
│   ├── deals
│   └── discounts
├── marketing
│   └── campaigns
└── finance
    └── budgets
```

### Access Rules

Permissions stored as cells:

```python
create_access_rule(
    role="role:hr_manager",
    namespace="corp.hr",
    permission=Permission.READ,
    granted_by="role:chro",
    graph_id=chain.graph_id,
    prev_cell_hash=chain.head.cell_id
)
```

### Bridge Rules

Cross-namespace access requires BOTH owners:

```python
create_bridge_rule(
    source_namespace="corp.sales",
    target_namespace="corp.hr.performance",
    source_owner_signature=vp_sales_sig,    # REQUIRED
    target_owner_signature=hr_director_sig,  # REQUIRED
    graph_id=chain.graph_id,
    prev_cell_hash=chain.head.cell_id,
    purpose="Discount authority based on rep performance"
)
```

**The database physically refuses the query until both signatures exist.**

## Layer 5: Resolver (The Scholar)

Implementation: `kernel/foundation/scholar.py`

The query engine that reads the vault:

```python
def resolve(
    chain: Chain,
    namespace_scope: str,      # "corp.sales.*"
    subject: str = None,
    predicate: str = None,
    valid_at: str = None,      # Point-in-time
    system_at: str = None,     # As-of query
    require_bridge: bool = True
) -> List[DecisionCell]:
    """
    Query facts with:
    - Namespace visibility (bridges checked)
    - Bitemporal filtering
    - Conflict resolution
    """
```

### Scholar Capabilities

1. **Query**: Find facts matching patterns
2. **Traverse**: Follow relationships
3. **Infer**: Derive new knowledge from rules
4. **Resolve**: Handle conflicts (confidence, recency)
5. **Time-Travel**: Query as of any timestamp
6. **Verify**: Trace inference path with citations

## Layer 6: Precedent System

The precedent system enables decision consistency tracking across the graph.

### JUDGMENT Cells

When a decision is finalized (disposition sealed), a JUDGMENT cell is created:

```
JudgmentPayload
├── Identity (privacy-preserving)
│   ├── precedent_id: UUID           # Random, NOT case_id
│   ├── case_id_hash: SHA256         # SHA256(salt + case_id)
│   └── jurisdiction_code: "CA-ON"
├── Fingerprint
│   ├── fingerprint_hash: SHA256     # SHA256(salt + banded_facts)
│   ├── fingerprint_schema_id        # e.g., "claimpilot:oap1:auto:v1"
│   └── anchor_facts: []             # Banded facts for matching
├── Decision
│   ├── exclusion_codes: []          # ["4.2.1", "4.3.3"]
│   ├── reason_codes: []             # ["RC-COMMERCIAL-USE"]
│   ├── outcome_code                 # pay, deny, partial, escalate
│   └── certainty                    # high, medium, low
├── Appeals
│   ├── appealed: bool
│   ├── appeal_outcome               # upheld, overturned, settled
│   └── appeal_level                 # internal, tribunal, court
└── Provenance
    └── authority_hashes: []         # Policy wording cited
```

### PrecedentRegistry

Chain-sourced, stateless registry (follows WitnessRegistry pattern):

```python
registry = PrecedentRegistry(chain)

# Find by exact fingerprint
matches = registry.find_by_fingerprint(
    fingerprint_hash="abc...",
    namespace_prefix="/precedents/auto/",
    as_of="2026-01-01T00:00:00Z"  # Bitemporal
)

# Find by exclusion codes
matches = registry.find_by_exclusion_codes(
    codes=["4.2.1"],
    namespace_prefix="/precedents/",
    outcome="deny",
    min_overlap=1
)

# Get statistics
stats = registry.get_statistics(fingerprint_hash, namespace_prefix)
# → total_count, outcome_counts, appeal_stats
```

### Query Tiers

Three-tier matching for flexibility:

| Tier | Name | Matching Criteria |
|------|------|-------------------|
| 0 | Exact Fingerprint | Identical banded facts |
| 0.5 | Same Codes | Same exclusion codes + outcome |
| 1 | Code Overlap | Overlapping exclusion codes |

### Confidence Scoring (pc_v1)

```python
base_confidence = weighted_average(
    majority_pct * 0.30,      # Same outcome rate
    upheld_rate * 0.25,       # Appeal success
    recency_score * 0.20,     # Recent decisions weighted
    policy_match_score * 0.15,# Policy version match
    decision_level_score * 0.10
)

# Overturned precedents apply penalty
precedent_confidence = base_confidence - overturn_penalty
```

### Fingerprint Banding

Continuous values are banded for stable matching:

```python
# BAC level bands
banding_rules = {
    "driver.bac_level": [
        (0.0, 0.05, "under_limit"),
        (0.05, 0.08, "warn_level"),
        (0.08, float("inf"), "over_limit"),
    ]
}

# Facts with bac=0.12 → banded to "over_limit"
# All bac>0.08 cases match each other
```

## Bitemporal Model

Two independent time dimensions:

| Dimension | Field | Question Answered |
|-----------|-------|-------------------|
| System Time | `header.system_time` | "When did we record this?" |
| Valid Time | `fact.valid_from/to` | "When was this true in reality?" |

### Query Examples

```python
# What do we currently know about Jane's salary?
resolve(subject="employee:jane_doe", predicate="has_salary")

# What was Jane's salary on Jan 1, 2026?
resolve(subject="employee:jane_doe", predicate="has_salary",
        valid_at="2026-01-01T00:00:00Z")

# What did we think Jane's salary was, as recorded before Feb 1?
resolve(subject="employee:jane_doe", predicate="has_salary",
        system_at="2026-02-01T00:00:00Z")
```

## Genesis: The Root of Trust

Genesis establishes:
- `graph_id`: Unique identifier for this graph instance
- `root_namespace`: The root of the namespace hierarchy
- `boot_rule`: The law that created the graph

### 22 Verification Checks

See `docs/GENESIS_CHECKLIST.md` for complete list.

Categories:
- **Header** (5 checks): type, prev_hash, version, graph_id format, system_time format
- **Fact** (9 checks): namespace, subject, predicate, object, confidence, quality, valid_from, valid_to, time match
- **Logic Anchor** (3 checks): rule_id, rule_hash, interpreter
- **Structure** (1 check): no evidence
- **Proof** (3 checks): signature requirements based on mode
- **Integrity** (1 check): cell_id matches computed hash

## Use Cases

### Banking AML (`domains/banking_aml/`)
```
namespace: bank.compliance.aml
facts: customer risk ratings, transaction flags
rules: SAR filing thresholds, enhanced due diligence triggers
decisions: "File SAR" with complete audit trail
modules: field_registry, seed_generator, fingerprint, reason_codes, policy_shifts
```

### Insurance Claims (`claimpilot/`)
```
namespace: insurance.claims
facts: policy terms, claim details, evidence documents
rules: coverage eligibility, exclusion matching, FSRA timelines
decisions: "Pay claim" / "Deny claim" with precedent-backed confidence
modules: policy_engine, evidence_gate, precedent_finder, calendars
```

### HR Performance (example)
```
namespace: corp.hr.performance
facts: employee ratings, certifications, tenure
rules: promotion eligibility criteria
decisions: "Eligible for promotion" with evidence chain
```

### Sales Discounts (example)
```
namespace: corp.sales.discounts
facts: deal size, customer tier, rep assignment
rules: discount authority limits
bridge: sales → hr.performance (check rep rating)
decisions: "Approve 25% discount" or "Escalate to VP"
```

## Design Principles

1. **Facts over Assertions**: Everything is a triple (subject-predicate-object)
2. **Law is Content-Addressed**: Rule changes create new versions
3. **Time is First-Class**: Bitemporal by default
4. **Trust through Cryptography**: Not through access control alone
5. **Append-Only**: History is immutable
6. **No External Dependencies**: The garden grows from its own soil
