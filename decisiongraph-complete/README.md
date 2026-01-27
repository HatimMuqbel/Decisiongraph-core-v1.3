# DecisionGraph Core v1.3

**The Universal Operating System for Deterministic Reasoning**

DecisionGraph is a cryptographically-sealed, namespace-isolated decision engine. Every fact is anchored to its source. Every decision is married to its law. Every chain is traceable to Genesis.

## Core Principle

> "Departments don't have to trust; they can verify the bridge."

## What This Is

A **Bank Vault for Corporate Truth** - an append-only, tamper-evident log where:
- Every cell has a cryptographic seal (cell_id = SHA256 of content)
- Every cell is bound to a specific graph (graph_id)
- Namespaces isolate departments (HR can't see Sales without a bridge)
- Cross-namespace access requires dual signatures
- Complete audit trail from any cell back to Genesis

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PRODUCT LAYER (Future)                   │
│   Logic Pack Manager • ZKP Generator • Simulation Engine    │
├─────────────────────────────────────────────────────────────┤
│                    REASONING LAYER (Task 5)                 │
│              DATALOG RESOLVER (The Scholar)                 │
│         Query • Traverse • Infer • Bridge-Check             │
├─────────────────────────────────────────────────────────────┤
│                    GOVERNANCE LAYER (v1.2+)                 │
│   Hierarchical Namespaces • Access Rules • Bridges          │
├─────────────────────────────────────────────────────────────┤
│                    STORAGE LAYER (Tasks 1-4) ✓              │
│   Genesis • Decision-Cell • Chain • Commit Gate             │
└─────────────────────────────────────────────────────────────┘
```

## Installation

```bash
cd decisiongraph-core
pip install -e .
# or just add src/ to PYTHONPATH
export PYTHONPATH=$PWD/src
```

## Quick Start

```python
from decisiongraph import (
    create_chain,
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    CellType,
    SourceQuality,
    get_current_timestamp,
    compute_rule_logic_hash
)

# Create a new graph
chain = create_chain(
    graph_name="AcmeCorp",
    root_namespace="acme",
    creator="system:init"
)

print(f"Graph ID: {chain.graph_id}")
print(f"Root namespace: {chain.root_namespace}")

# Add a fact
ts = get_current_timestamp()
fact_cell = DecisionCell(
    header=Header(
        version="1.3",
        graph_id=chain.graph_id,
        cell_type=CellType.FACT,
        system_time=ts,
        prev_cell_hash=chain.head.cell_id
    ),
    fact=Fact(
        namespace="acme.hr",
        subject="employee:jane_doe",
        predicate="has_role",
        object="Senior Engineer",
        confidence=1.0,
        source_quality=SourceQuality.VERIFIED,
        valid_from=ts
    ),
    logic_anchor=LogicAnchor(
        rule_id="source:hris_system",
        rule_logic_hash=compute_rule_logic_hash("HRIS Export v2")
    )
)

chain.append(fact_cell)
print(f"Chain length: {chain.length}")
```

## Core Concepts

### Decision-Cell (The DNA)

Every piece of information is a sealed cell:

```json
{
  "cell_id": "sha256:...",
  "header": {
    "version": "1.3",
    "graph_id": "graph:uuid-v4",
    "cell_type": "fact|rule|decision|...",
    "system_time": "2026-01-27T12:00:00Z",
    "prev_cell_hash": "sha256:..."
  },
  "fact": {
    "namespace": "corp.hr.compensation",
    "subject": "employee:jane_doe",
    "predicate": "has_salary",
    "object": "150000",
    "confidence": 1.0,
    "source_quality": "verified",
    "valid_from": "2026-01-01T00:00:00Z",
    "valid_to": null
  },
  "logic_anchor": {
    "rule_id": "policy:salary_bands_v1",
    "rule_logic_hash": "sha256:..."
  }
}
```

### The Logic Seal

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

**Change ANY field → cell_id breaks → tampering detected**

### Genesis (The Big Bang)

Every graph starts with a Genesis cell that establishes:
- The `graph_id` (all cells must match)
- The root namespace
- The boot rule anchor

Genesis has 22 verification checks. See `verify_genesis()`.

### Namespaces (Department Isolation)

Hierarchical paths like filesystem:
```
acme (root)
├── hr
│   ├── compensation (🔒 restricted)
│   └── performance
├── sales
│   └── discounts
└── marketing
```

### Bridges (Cross-Department Access)

To query across namespaces, you need a **Bridge Rule** signed by BOTH namespace owners:

```python
bridge = create_bridge_rule(
    source_namespace="acme.sales",
    target_namespace="acme.hr.performance",
    source_owner_signature=vp_sales_sig,
    target_owner_signature=hr_director_sig,
    graph_id=chain.graph_id,
    prev_cell_hash=chain.head.cell_id,
    purpose="Check rep performance for discount authority"
)
```

### Commit Gate (Chain.append)

The gatekeeper enforces:
1. Genesis must be first
2. Only one Genesis allowed
3. `graph_id` must match (no cross-graph contamination)
4. `prev_cell_hash` must exist
5. Integrity must be valid
6. Timestamps must be monotonic

## Cell Types

| Type | Purpose |
|------|---------|
| `genesis` | Root of graph, establishes graph_id and namespace |
| `fact` | A piece of information (subject-predicate-object) |
| `rule` | Business logic definition |
| `decision` | Outcome of applying rules to facts |
| `evidence` | Supporting documentation |
| `override` | Human override of automated decision |
| `access_rule` | Permission grant |
| `bridge_rule` | Cross-namespace access |
| `namespace_def` | Namespace definition |

## Bitemporal Model

Two time dimensions:
- **system_time** (header): When the engine recorded this cell
- **valid_from/valid_to** (fact): When this fact is true in the real world

This enables:
- "What did we know on Jan 1?" (system_time query)
- "What was true on Jan 1?" (valid_time query)
- "What did we think was true on Jan 1, as of Feb 1?" (both)

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_commit_gate.py -v

# Run demos
python demo.py
python demo_corporate.py
```

## Project Structure

```
decisiongraph-core/
├── README.md
├── docs/
│   ├── ARCHITECTURE.md      # Detailed architecture
│   ├── GENESIS_CHECKLIST.md # 22 verification checks
│   ├── SCHEMA_V1.3.md       # Complete schema spec
│   └── ROADMAP.md           # What's next
├── specs/
│   ├── DecisionGraph.tla    # TLA+ formal spec
│   └── DecisionGraphV2.tla  # With namespace invariants
├── src/decisiongraph/
│   ├── __init__.py
│   ├── cell.py              # DecisionCell, Header, Fact, etc.
│   ├── genesis.py           # Genesis creation & verification
│   ├── chain.py             # Chain & Commit Gate
│   └── namespace.py         # Namespaces, Access, Bridges
├── tests/
│   ├── test_core.py
│   └── test_commit_gate.py
├── demo.py
└── demo_corporate.py
```

## What's Complete (v1.3)

- [x] Task 1: TLA+ Specification (14 invariants)
- [x] Task 2: Genesis Cell (22 verification checks)
- [x] Task 3: Logic Seal (cell_id computation with graph_id + namespace)
- [x] Task 4: Chain Validation (Commit Gate with graph_id enforcement)
- [x] Hierarchical Namespaces
- [x] Access Rules as Cells
- [x] Bridge Rules (dual signature)
- [x] Namespace Registry

## What's Next

- [ ] Task 5: Datalog Resolver (The Scholar)
- [ ] Logic Pack Manager
- [ ] ZKP Generator (Merkle proofs)
- [ ] Simulation Engine (what-if queries)

## License

MIT

## Philosophy

> "The garden grows from its own soil."

No external dependencies for core functionality. DecisionGraph IS the solution - not a wrapper around other databases.
