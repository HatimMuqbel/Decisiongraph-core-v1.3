# Architecture

**Analysis Date:** 2026-01-27

## Pattern Overview

**Overall:** Append-Only Cryptographic Ledger with Namespace Isolation

**Key Characteristics:**
- **Immutable Chain of Custody** - All information stored as tamper-evident cells linked via cryptographic hashes
- **Graph-Bound Isolation** - Every cell binds to a specific `graph_id` preventing cross-graph contamination
- **Namespace Hierarchies** - Department/domain isolation via hierarchical namespace paths (e.g., `corp.hr.compensation`)
- **Bitemporal Semantics** - Dual time dimensions: `system_time` (when recorded) vs `valid_from/valid_to` (when true)
- **Self-Verifying Cells** - Each cell's integrity is mathematically provable via `cell_id = SHA256(content)`
- **Deterministic Resolution** - Conflicts resolved by quality, confidence, recency, then lexicographic hash

## Layers

**Storage Layer (Cell & Chain):**
- Purpose: Immutable, append-only ledger of decision events
- Location: `src/decisiongraph/cell.py`, `src/decisiongraph/chain.py`
- Contains: DecisionCell dataclass, Header, Fact, LogicAnchor, Evidence, Proof; Chain container with indexing
- Depends on: Standard library (hashlib, dataclasses, json)
- Used by: Genesis layer (initialization), Namespace layer (cell creation), Scholar layer (querying)

**Genesis Layer (Bootstrap):**
- Purpose: Atomic initialization of graph instances with unforgeable root cell
- Location: `src/decisiongraph/genesis.py`
- Contains: Genesis cell creation, 22-check verification routine, graph_id binding
- Depends on: Cell layer (DecisionCell, Header, Fact, LogicAnchor, compute_rule_logic_hash)
- Used by: Chain layer (validation on append), initialization code

**Governance Layer (Namespace & Access):**
- Purpose: Department isolation, access control, and cross-namespace bridges
- Location: `src/decisiongraph/namespace.py`
- Contains: NamespaceRegistry, NamespaceMetadata, Signature, Permission enums, bridge/access rule creation
- Depends on: Cell layer (DecisionCell creation), Chain layer (cell_id references)
- Used by: Scholar layer (authorization checks), applications (namespace setup)

**Reasoning Layer (Scholar/Query):**
- Purpose: Query the vault, resolve conflicts, verify authorization
- Location: `src/decisiongraph/scholar.py`
- Contains: Scholar resolver, QueryResult, ResolutionEvent, AuthorizationBasis, ScholarIndex
- Depends on: All lower layers (Cell, Chain, Genesis, Namespace)
- Used by: Applications (fact queries), audit trails (proof generation)

## Data Flow

**Writing Facts (Append Path):**

1. Application creates a `DecisionCell` with:
   - Header: version, graph_id, cell_type, system_time, prev_cell_hash
   - Fact: namespace, subject-predicate-object triple, confidence, source_quality, valid_time bounds
   - LogicAnchor: rule_id and rule_logic_hash (canonicalized)
   - Evidence: optional supporting documents with content IDs

2. Cell constructor automatically computes `cell_id = SHA256(sealed_content)`

3. Application calls `chain.append(cell)` which validates:
   - Genesis exists and is first
   - Cell integrity (cell_id matches computed hash)
   - Chain link (prev_cell_hash references existing cell)
   - Temporal consistency (system_time >= previous cell)
   - Graph binding (graph_id matches chain's graph_id)

4. Cell is added to `chain.cells` list and indexed by `cell_id`

**Querying Facts (Read Path):**

1. Application calls `scholar.query(namespace, subject, predicate, valid_time, system_time, requester_id)`

2. Scholar builds `ScholarIndex` from chain (caching candidate facts)

3. For each matching namespace/subject/predicate combination:
   - Filter by time bounds (valid_time + system_time)
   - Check authorization (requester can access namespace + bridges)
   - Collect all candidates in conflict set

4. Conflict resolution (if multiple candidates):
   - Quality ranking: verified > self_reported > inferred
   - Confidence: higher wins
   - Recency: later system_time wins
   - Tiebreak: lexicographically smallest cell_id

5. Return `QueryResult` with:
   - Winning facts (effective truth)
   - All candidates (for audit)
   - Bridges used (authorization proof)
   - Resolution events (why conflicts resolved)
   - Authorization basis (WHY access granted)

**State Management:**

- **Chain State**: Single source of truth; immutable cells list + in-memory index
- **Authorization State**: NamespaceRegistry built from access_rule and bridge_rule cells in chain
- **Query Index**: ScholarIndex built fresh from chain (no separate DB needed)
- **No mutable updates**: Changes require appending new cells, never modifying existing

## Key Abstractions

**DecisionCell:**
- Purpose: Atomic unit of information - single fact + proof
- Examples: `src/decisiongraph/cell.py` lines 354-515
- Pattern: Immutable dataclass with `@post_init__` computing self-verifying `cell_id`
- Invariant: Changing ANY field invalidates the cell (cell_id won't match)

**Chain:**
- Purpose: Container for ordered cells with integrity guarantees
- Examples: `src/decisiongraph/chain.py` lines 102-530
- Pattern: Dataclass with `cells` list and `index` dict (O(1) lookup by cell_id)
- Methods: `append()` (validates before adding), `validate()` (checks all invariants), `trace_to_genesis()` (audit trail)
- Invariant: Every cell except first points to a predecessor; no duplicates; monotonic timestamps; graph_id binding

**Header:**
- Purpose: Metadata + chain link for each cell
- Examples: `src/decisiongraph/cell.py` lines 206-237
- Pattern: Immutable dataclass with validation on `__post_init__`
- Contains: `version`, `graph_id` (NEW in v1.3), `cell_type`, `system_time`, `prev_cell_hash`

**Fact:**
- Purpose: Subject-Predicate-Object triple with temporal + quality semantics
- Examples: `src/decisiongraph/cell.py` lines 239-293
- Pattern: Namespace-scoped truth claim with confidence bounds
- Contains: `namespace`, `subject`, `predicate`, `object`, `confidence`, `source_quality`, `valid_from/valid_to`
- Validation: Namespace must match regex; confidence in [0, 1]; confidence=1.0 requires source_quality=verified

**LogicAnchor:**
- Purpose: Bind fact to the rule/law that produced it
- Examples: `src/decisiongraph/cell.py` lines 295-308
- Pattern: Simple link to rule provenance with canonicalized hash
- Contains: `rule_id`, `rule_logic_hash` (computed via `canonicalize_rule_content()` + SHA256), `interpreter` (optional)

**NamespaceRegistry:**
- Purpose: Access control matrix: who can read/write/admin which namespaces
- Examples: `src/decisiongraph/namespace.py` lines 103-300+
- Pattern: Built from access_rule and bridge_rule cells in chain
- Invariant: Parents can't override children; bridges require dual signatures; all changes auditable

**Scholar:**
- Purpose: Query resolver with authorization enforcement
- Examples: `src/decisiongraph/scholar.py` lines 200+
- Pattern: Index-based query with deterministic conflict resolution
- Methods: `query()` (facts), `visibility()` (what requester can see), `find_rule_mismatches()` (compliance check)

## Entry Points

**Chain Initialization:**
- Location: `src/decisiongraph/chain.py` lines 532-554 (`create_chain()` function)
- Triggers: Application bootstrap
- Responsibilities: Create Chain container, call `chain.initialize()` to create Genesis, return ready chain
- Signature: `create_chain(graph_name: str, root_namespace: str, creator: Optional[str]) -> Chain`

**Chain Appending (Commit Gate):**
- Location: `src/decisiongraph/chain.py` lines 216-289 (`Chain.append()` method)
- Triggers: Application wants to add a cell
- Responsibilities: Validate cell integrity, chain link, temporal consistency, graph binding, then add to list
- Raises: `IntegrityViolation`, `ChainBreak`, `TemporalViolation`, `GraphIdMismatch`, `GenesisViolation`

**Genesis Creation:**
- Location: `src/decisiongraph/genesis.py` lines 120-200+ (`create_genesis_cell()` function)
- Triggers: Chain initialization
- Responsibilities: Generate unique graph_id, create Genesis cell with canonical rule hash, return sealed cell
- Returns: DecisionCell with cell_type=GENESIS, prev_cell_hash=NULL_HASH

**Querying Facts:**
- Location: `src/decisiongraph/scholar.py` lines 200+
- Triggers: Application requests facts
- Responsibilities: Build index, filter by namespace + time, check authorization, resolve conflicts
- Returns: `QueryResult` with winning facts, candidates, bridges used, authorization basis

**Cell Deserialization:**
- Location: `src/decisiongraph/cell.py` lines 454-515 (`DecisionCell.from_dict()`)
- Triggers: Loading cells from JSON/database
- Responsibilities: Reconstruct DecisionCell from dict, verify cell_id matches to detect tampering
- Raises: `ValueError` if cell_id mismatch

## Error Handling

**Strategy:** Explicit exception hierarchy; validation at every layer; fail-fast on invariant violation

**Exception Classes:**

`ChainError` (base for chain issues):
- `IntegrityViolation`: cell_id doesn't match computed hash (tampering detected)
- `ChainBreak`: prev_cell_hash points to non-existent cell
- `GenesisViolation`: Genesis missing, duplicate, or invalid
- `TemporalViolation`: Timestamps not monotonic
- `GraphIdMismatch`: Cell bound to different graph

`NamespaceError` (base for governance issues):
- `AccessDeniedError`: Requester lacks permission for namespace
- `BridgeRequiredError`: Cross-namespace access needs bridge
- `BridgeApprovalError`: Bridge missing required signature

`GenesisError` (base for bootstrap issues):
- `GenesisValidationError`: Genesis structure invalid

**Patterns:**

1. **Validation-then-action**: Every `append()` validates before modifying state
2. **No partial states**: If validation fails, chain unchanged (transactional)
3. **Detailed error messages**: Include computed vs expected values for debugging
4. **Return validation objects**: `ValidationResult` with `is_valid`, `errors`, `warnings` (not exceptions for batch validation)

## Cross-Cutting Concerns

**Logging:**
- Currently console-based via print statements in demo/test code
- Recommended pattern: Add logger initialization to `__init__.py` for library users
- Key events to log: Genesis creation, cell appends, validation failures, bridge approvals

**Validation:**
- Happens at 3 levels: (1) Dataclass `__post_init__` (field-level), (2) `Chain.append()` (cell-level), (3) `Chain.validate()` (chain-level)
- Namespace validation: Regex `NAMESPACE_PATTERN` enforces lowercase, dots, max 64-char segments
- Timestamp validation: ISO 8601 with timezone required
- Confidence validation: Must be in [0.0, 1.0]; 1.0 requires verified source

**Authentication/Authorization:**
- No built-in cryptographic verification (future feature)
- Currently: Signature fields in Proof and Signature dataclasses (placeholder for future)
- Authorization enforced by Scholar via NamespaceRegistry (access rules + bridges)
- Bridge requirement: Both source and target namespace owners must sign

**Canonicalization (v1.3):**
- Rule content normalized before hashing: strip whitespace, remove empty lines, join with `\n`
- Function: `canonicalize_rule_content()` in `src/decisiongraph/cell.py` lines 156-173
- Purpose: Whitespace variations in rules don't create different hashes
- Used by: `compute_rule_logic_hash()` and Genesis bootstrap

---

*Architecture analysis: 2026-01-27*
