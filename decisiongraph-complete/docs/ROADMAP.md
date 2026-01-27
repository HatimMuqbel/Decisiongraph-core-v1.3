# DecisionGraph Roadmap

## Current Status: v1.3 Foundation Complete

### ✅ Completed

#### Task 1: TLA+ Specification
- 14 invariants defined
- Namespace isolation invariants
- Bridge integrity invariants
- Files: `specs/DecisionGraph.tla`, `specs/DecisionGraphV2.tla`

#### Task 2: Genesis Cell
- 22 verification checks
- graph_id generation and validation
- Root namespace establishment
- Bootstrap mode for initial deployment
- File: `src/decisiongraph/genesis.py`

#### Task 3: Logic Seal (cell_id)
- SHA256 of concatenated fields
- Includes graph_id and namespace
- Canonicalized rule hashing
- File: `src/decisiongraph/cell.py`

#### Task 4: Chain & Commit Gate
- Append-only log
- Hash-linked cells
- Commit Gate enforcement:
  - Genesis must be first
  - Only one Genesis
  - graph_id must match
  - prev_cell_hash must exist
  - Integrity validation
  - Temporal ordering
- File: `src/decisiongraph/chain.py`

#### Governance Layer (v1.2+)
- Hierarchical namespaces
- Access rules as cells
- Bridge rules with dual signatures
- Namespace registry
- File: `src/decisiongraph/namespace.py`

---

## 🔜 Next Up

### Task 5: Datalog Resolver (The Scholar)

**Goal**: First real query capability

```python
def resolve(
    chain: Chain,
    namespace_scope: str,      # "corp.sales" or "corp.sales.*"
    subject: str = None,
    predicate: str = None,
    valid_at: str = None,      # Point-in-time query
    system_at: str = None,     # As-of query
    require_bridge: bool = True
) -> List[DecisionCell]
```

**Features**:
1. Namespace visibility (bridge checking)
2. Bitemporal filtering
3. Conflict resolution (confidence, recency)
4. Trace generation (path from query to facts)

**File**: `src/decisiongraph/resolver.py`

---

## 📋 Future Layers

### Layer 6: Product Features

#### A. Logic Pack Manager (The Librarian)
- Import/export domain-specific rule packs
- Versioning and compatibility
- "App Store" for decision models
- Examples: "DecisionGraph for KYC", "DecisionGraph for HR"

#### B. ZKP Generator (The Notary)
- Generate cryptographic proofs of decisions
- Merkle proofs for selective disclosure
- "Prove compliance without revealing data"
- Future: Full ZK-SNARKs

#### C. Feedback Loop (The Learning Layer)
- Track human overrides
- Detect rule drift
- Query: "Show every time automated logic was overruled"
- Enable continuous improvement

#### D. Simulation Engine (The Oracle)
- "What-if" queries
- Test rule changes before deployment
- Impact analysis

#### E. Witness Network
- Multi-signature for high-stakes decisions
- Quorum requirements
- Distributed trust

#### F. Federation Bridge
- Cross-graph queries
- B2B data sharing
- Supply chain visibility

---

### Layer 7: Logic Packs

Domain-specific implementations:

| Pack | Domain | Key Rules |
|------|--------|-----------|
| AML | Banking | SAR triggers, risk ratings, EDD |
| KYC | Compliance | Identity verification, document checks |
| HR | Human Resources | Promotions, compensation bands, PTO |
| Sales | Revenue | Discount authority, deal approval |
| Supply Chain | Logistics | Vendor approval, quality gates |

---

### Layer 8: User Interface

- Natural language queries via LLM
- Dashboard for audit trail visualization
- Alert configuration
- Report generation

---

## Technical Debt / Improvements

### Near Term
- [ ] Update `test_core.py` for v1.3 API changes
- [ ] Update demos for v1.3 (graph_id parameter)
- [ ] Add `pyproject.toml` for proper packaging
- [ ] Add type hints throughout
- [ ] Add logging

### Medium Term
- [ ] Persistence layer (JSON files, S3, SQLite)
- [ ] CLI tool for chain inspection
- [ ] Performance benchmarks
- [ ] Property-based testing

### Long Term
- [ ] Real cryptographic signatures (Ed25519)
- [ ] Key management system
- [ ] Distributed chain synchronization
- [ ] GraphQL API

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | - | Initial concept |
| v1.1 | - | Added namespace to cell_id |
| v1.2 | - | Hierarchical namespaces, bridges |
| v1.3 | 2026-01 | graph_id binding, 22-check Genesis, system_time rename, Commit Gate |

---

## Principles (Unchanging)

1. **Facts over Assertions**: Everything is a triple
2. **Law is Content-Addressed**: Rule changes = new versions
3. **Time is First-Class**: Bitemporal by default
4. **Trust through Cryptography**: Not through access control alone
5. **Append-Only**: History is immutable
6. **No External Dependencies**: Build from first principles

> "The garden grows from its own soil."
