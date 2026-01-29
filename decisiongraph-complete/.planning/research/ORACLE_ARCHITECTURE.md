# Architecture Research: Oracle Layer (Counterfactual Simulation)

**Domain:** Counterfactual simulation for append-only decision ledgers
**Researched:** 2026-01-28
**Confidence:** HIGH (existing codebase) + MEDIUM (overlay patterns)

## Executive Summary

The Oracle layer adds counterfactual "what-if" simulation capability to DecisionGraph without mutating the append-only chain. This architecture introduces a **persistent overlay pattern** where shadow cells exist in an ephemeral memory layer above the base chain, allowing Scholar to query hypothetical states while maintaining absolute zero-contamination guarantees.

**Core Pattern:** Copy-on-write persistent data structure with base-before-overlay precedence. Base reality (chain) is frozen at a snapshot point; shadow reality (overlay) provides delta modifications visible only within a simulation context.

**Zero Contamination:** Chain.append() is never called for shadow cells. Shadow cells exist only in SimulationContext, which is destroyed after delta reporting.

## Existing Architecture (Integration Points)

### Chain (Immutable Base Reality)

**Location:** `src/decisiongraph/chain.py`

**Current Behavior:**
- `Chain.cells` is append-only list
- `Chain.index` maps cell_id → position
- `Chain.append(cell)` validates and adds to end
- `Chain.get_cell(cell_id)` returns cell or None

**Integration for Oracle:**
- Chain remains read-only during simulation
- Snapshot point = (valid_time, system_time) coordinates
- Chain.get_cell() must be wrapped to check overlay first
- NO changes to Chain class itself (zero mutation)

**Confidence:** HIGH (direct codebase inspection)

### Scholar (Query Resolver)

**Location:** `src/decisiongraph/scholar.py`

**Current Behavior:**
- Builds indexes from chain: `ScholarIndex.cell_by_id`, `by_namespace`, `by_key`
- `query_facts()` filters by namespace, subject, predicate, bitemporal coordinates
- Conflict resolution via `_resolve_conflicts()` using quality/confidence/recency
- Returns `QueryResult` with facts, candidates, bridges_used, resolution_events

**Integration for Oracle:**
- Scholar needs "overlay-aware" mode
- Index lookups check overlay first, then chain
- Conflict resolution must handle BASE vs SHADOW precedence
- QueryResult extended with simulation metadata

**Modification Required:** Scholar needs optional `overlay_context` parameter

**Confidence:** HIGH (direct codebase inspection)

### Engine (Entry Point)

**Location:** `src/decisiongraph/engine.py`

**Current Behavior:**
- `process_rfa(rfa_dict)` → ProofPacket
- `submit_promotion()` → promotion_id
- `finalize_promotion()` → PolicyHead cell_id

**Integration for Oracle:**
- Add `simulate_rfa(rfa_dict, hypothetical_changes)` → SimulationResult
- Hypothetical changes = list of shadow cells to inject
- Returns delta report comparing base vs shadow outcomes

**New Method Required:** `simulate_rfa()`

**Confidence:** HIGH (existing pattern extends cleanly)

### Cell (Atomic Unit)

**Location:** `src/decisiongraph/cell.py`

**Current Behavior:**
- `DecisionCell.cell_id` computed from header+fact+logic_anchor
- `compute_cell_id()` is SHA-256 of canonical fields
- `verify_integrity()` checks cell_id matches computed hash

**Integration for Oracle:**
- Shadow cells are normal DecisionCell instances
- Shadow cells have valid cell_ids (computed normally)
- Shadow cells are tagged at context level, not cell level

**No Changes Required:** Cells don't know if they're shadow or base

**Confidence:** HIGH (clean separation of concerns)

## New Components

### 1. SimulationContext (Overlay Container)

**Purpose:** Ephemeral container for shadow cells that wraps base chain

```python
@dataclass
class SimulationContext:
    """
    Ephemeral overlay for counterfactual simulation.

    Created per simulation, destroyed after results computed.
    Shadow cells never touch the base chain.
    """
    base_chain: Chain                        # Read-only reference
    base_snapshot: Tuple[str, str]           # (valid_time, system_time)
    overlay: Dict[str, DecisionCell]         # cell_id -> shadow cell
    shadow_cell_ids: Set[str]                # Tracking for proof tagging

    def get_cell(self, cell_id: str) -> Optional[DecisionCell]:
        """Overlay-before-base lookup"""
        if cell_id in self.overlay:
            return self.overlay[cell_id]
        return self.base_chain.get_cell(cell_id)

    def add_shadow_cell(self, cell: DecisionCell) -> None:
        """Add shadow cell to overlay (never touches base chain)"""
        self.overlay[cell.cell_id] = cell
        self.shadow_cell_ids.add(cell.cell_id)

    def is_shadow(self, cell_id: str) -> bool:
        """Check if cell is from shadow reality"""
        return cell_id in self.shadow_cell_ids
```

**Why This Design:**
- Overlay dictionary provides O(1) lookup
- Shadow cell tracking enables proof tagging (BASE vs SHADOW)
- No modification to base chain (zero contamination)
- Context destroyed after simulation (no persistence risk)

**Pattern Precedent:** Git's working tree vs committed history; Copy-on-write file systems

**Confidence:** HIGH (well-established persistent data structure pattern)

### 2. OverlayScholar (Context-Aware Resolver)

**Purpose:** Scholar variant that queries overlay before chain

```python
class OverlayScholar(Scholar):
    """
    Scholar that queries SimulationContext instead of raw Chain.

    All lookups check overlay first, then fall back to base chain.
    """

    def __init__(self, simulation_context: SimulationContext):
        # Don't call super().__init__ — we override everything
        self.context = simulation_context
        self.index = self._build_overlay_index()
        self.registry = build_registry_from_chain(simulation_context.base_chain.cells)

    def _build_overlay_index(self) -> ScholarIndex:
        """Build index from base + overlay cells"""
        index = ScholarIndex()

        # Index all base chain cells first
        for cell in self.context.base_chain.cells:
            if cell.header.cell_type in (CellType.FACT, CellType.RULE, ...):
                index.add_cell(cell)

        # Index overlay cells (shadows override base if same cell_id)
        for cell in self.context.overlay.values():
            if cell.header.cell_type in (CellType.FACT, CellType.RULE, ...):
                index.add_cell(cell)  # Later add wins (overlay precedence)

        return index

    def query_facts(self, ...) -> QueryResult:
        """Query with overlay precedence"""
        result = super().query_facts(...)

        # Tag facts as BASE or SHADOW in proof bundle
        for fact in result.facts:
            fact._shadow_origin = self.context.is_shadow(fact.cell_id)

        return result
```

**Why This Design:**
- Inherits all Scholar logic (conflict resolution, bridges, etc.)
- Overlay index built once, reused for multiple queries
- Scholar doesn't need to know about simulation (dependency inversion)

**Alternative Considered:** Modify Scholar.query_facts() to accept optional overlay
**Rejected Because:** Too much coupling; harder to test; pollution of base Scholar

**Confidence:** MEDIUM (requires careful index precedence handling)

### 3. SimulationResult (Delta Report)

**Purpose:** Compare base reality vs shadow reality outcomes

```python
@dataclass
class SimulationResult:
    """
    Result of a counterfactual simulation.

    Contains both base and shadow query results, plus delta analysis.
    """
    simulation_id: str                       # UUID for this simulation
    base_snapshot: Tuple[str, str]           # (valid_time, system_time)

    # Base reality results
    base_result: QueryResult
    base_facts: List[DecisionCell]

    # Shadow reality results
    shadow_result: QueryResult
    shadow_facts: List[DecisionCell]

    # Delta analysis
    facts_added: List[DecisionCell]          # In shadow, not in base
    facts_removed: List[DecisionCell]        # In base, not in shadow
    facts_changed: List[Tuple[DecisionCell, DecisionCell]]  # (base, shadow) pairs

    # Counterfactual anchors (minimal changes causing deltas)
    anchors: List[CounterfactualAnchor]

    def to_proof_bundle(self) -> Dict:
        """Generate proof bundle for simulation"""
        return {
            "simulation_id": self.simulation_id,
            "base_snapshot": {
                "valid_time": self.base_snapshot[0],
                "system_time": self.base_snapshot[1]
            },
            "base_proof": self.base_result.to_proof_bundle(),
            "shadow_proof": self.shadow_result.to_proof_bundle(),
            "delta": {
                "added": [f.cell_id for f in self.facts_added],
                "removed": [f.cell_id for f in self.facts_removed],
                "changed": [(b.cell_id, s.cell_id) for b, s in self.facts_changed]
            },
            "anchors": [a.to_dict() for a in self.anchors]
        }
```

**Why This Design:**
- Self-contained delta report (all simulation context in one object)
- Proof bundles from both realities enable verification
- Counterfactual anchors identify causality

**Confidence:** HIGH (straightforward comparison logic)

### 4. CounterfactualAnchor (Causality Tracker)

**Purpose:** Identify which shadow cells caused specific deltas

```python
@dataclass
class CounterfactualAnchor:
    """
    Identifies a shadow cell that caused a delta in outcomes.

    "If we change X, then Y changes" — this is the X.
    """
    shadow_cell_id: str                      # The hypothetical change
    affected_facts: List[str]                # Facts that changed as a result
    delta_type: str                          # "added" | "removed" | "changed"
    reasoning_chain: List[str]               # Cell IDs in causal path

    def to_dict(self) -> Dict:
        return {
            "anchor_cell": self.shadow_cell_id,
            "affected": self.affected_facts,
            "delta_type": self.delta_type,
            "reasoning_chain": self.reasoning_chain
        }
```

**Why This Design:**
- Enables "why did the outcome change?" analysis
- Reasoning chain shows transitive dependencies
- Minimal structure (can be extended later)

**Confidence:** MEDIUM (causality tracking is complex, this is MVP)

### 5. ShadowCellBuilder (Factory)

**Purpose:** Create valid shadow cells with proper linking

```python
class ShadowCellBuilder:
    """
    Factory for creating shadow cells that link correctly to base chain.

    Shadow cells need valid prev_cell_hash, system_time, graph_id from base.
    """

    def __init__(self, base_chain: Chain):
        self.base_chain = base_chain

    def create_shadow_fact(
        self,
        namespace: str,
        subject: str,
        predicate: str,
        object: str,
        rule_id: str,
        confidence: float = 1.0,
        source_quality: SourceQuality = SourceQuality.VERIFIED,
        valid_from: Optional[str] = None
    ) -> DecisionCell:
        """
        Create a shadow fact cell linked to base chain.

        Uses base chain head as prev_cell_hash (proper linking).
        Uses base graph_id (stays in same graph).
        """
        # Get linking info from base
        prev_cell_hash = self.base_chain.head.cell_id
        graph_id = self.base_chain.graph_id
        system_time = get_current_timestamp()  # Shadow "recorded now"

        # Get rule for logic anchor
        rule_cell = self.base_chain.get_cell(rule_id)
        if not rule_cell:
            raise ValueError(f"Rule {rule_id} not found in base chain")

        # Create shadow cell (normal DecisionCell)
        shadow = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=graph_id,
                cell_type=CellType.FACT,
                system_time=system_time,
                prev_cell_hash=prev_cell_hash
            ),
            fact=Fact(
                namespace=namespace,
                subject=subject,
                predicate=predicate,
                object=object,
                confidence=confidence,
                source_quality=source_quality,
                valid_from=valid_from or system_time,
                valid_to=None
            ),
            logic_anchor=LogicAnchor(
                rule_id=rule_id,
                rule_logic_hash=rule_cell.logic_anchor.rule_logic_hash
            )
        )

        return shadow
```

**Why This Design:**
- Shadow cells are indistinguishable from base cells structurally
- Proper linking enables integrity verification
- Factory ensures consistency (no manual header construction)

**Confidence:** HIGH (follows existing cell creation pattern)

## Data Flow: simulate_rfa()

**High-level pipeline:**

```
1. Engine.simulate_rfa(rfa_dict, hypothetical_changes)
2. Create SimulationContext with base snapshot
3. Build shadow cells via ShadowCellBuilder
4. Add shadows to overlay (never touch chain)
5. Create OverlayScholar(context)
6. Query base Scholar (baseline)
7. Query OverlayScholar (hypothetical)
8. Compare results → SimulationResult
9. Destroy context (zero persistence)
10. Return SimulationResult
```

**Detailed walkthrough:**

```python
def simulate_rfa(
    self,
    rfa_dict: dict,
    hypothetical_changes: List[Dict]
) -> SimulationResult:
    """
    Simulate RFA with hypothetical changes.

    Args:
        rfa_dict: Standard RFA (namespace, requester_namespace, requester_id, ...)
        hypothetical_changes: List of shadow cell specs:
            [
                {
                    "namespace": "corp.hr",
                    "subject": "user:bob",
                    "predicate": "has_salary",
                    "object": "120000",
                    "rule_id": "rule:salary_policy_v3"
                },
                ...
            ]

    Returns:
        SimulationResult with base vs shadow comparison
    """
    # Step 1: Snapshot base reality
    base_snapshot = (
        rfa_dict.get('at_valid_time', get_current_timestamp()),
        rfa_dict.get('as_of_system_time', get_current_timestamp())
    )

    # Step 2: Create simulation context
    context = SimulationContext(
        base_chain=self.chain,
        base_snapshot=base_snapshot,
        overlay={},
        shadow_cell_ids=set()
    )

    # Step 3: Build shadow cells
    builder = ShadowCellBuilder(self.chain)
    for change in hypothetical_changes:
        shadow_cell = builder.create_shadow_fact(
            namespace=change['namespace'],
            subject=change['subject'],
            predicate=change['predicate'],
            object=change['object'],
            rule_id=change['rule_id']
        )
        context.add_shadow_cell(shadow_cell)

    # Step 4: Query base reality (normal Scholar)
    base_result = self.scholar.query_facts(
        requester_namespace=rfa_dict['requester_namespace'],
        namespace=rfa_dict['namespace'],
        subject=rfa_dict.get('subject'),
        predicate=rfa_dict.get('predicate'),
        at_valid_time=base_snapshot[0],
        as_of_system_time=base_snapshot[1],
        requester_id=rfa_dict['requester_id']
    )

    # Step 5: Query shadow reality (OverlayScholar)
    overlay_scholar = OverlayScholar(context)
    shadow_result = overlay_scholar.query_facts(
        requester_namespace=rfa_dict['requester_namespace'],
        namespace=rfa_dict['namespace'],
        subject=rfa_dict.get('subject'),
        predicate=rfa_dict.get('predicate'),
        at_valid_time=base_snapshot[0],
        as_of_system_time=base_snapshot[1],
        requester_id=rfa_dict['requester_id']
    )

    # Step 6: Delta analysis
    base_ids = {f.cell_id for f in base_result.facts}
    shadow_ids = {f.cell_id for f in shadow_result.facts}

    facts_added = [f for f in shadow_result.facts if f.cell_id not in base_ids]
    facts_removed = [f for f in base_result.facts if f.cell_id not in shadow_ids]

    # Step 7: Identify anchors (which shadow cells caused deltas)
    anchors = self._compute_anchors(context, facts_added, facts_removed)

    # Step 8: Build result
    result = SimulationResult(
        simulation_id=str(uuid4()),
        base_snapshot=base_snapshot,
        base_result=base_result,
        base_facts=base_result.facts,
        shadow_result=shadow_result,
        shadow_facts=shadow_result.facts,
        facts_added=facts_added,
        facts_removed=facts_removed,
        facts_changed=[],  # TODO: implement change detection
        anchors=anchors
    )

    # Step 9: Context destroyed (Python GC)
    # No need to explicitly clean up — context goes out of scope

    return result
```

**Confidence:** HIGH (straightforward orchestration)

## Zero Contamination Pattern

**Guarantee:** Base chain is never mutated during simulation.

**Enforcement mechanisms:**

### 1. Never Call Chain.append()

Shadow cells are added to `SimulationContext.overlay` only:

```python
# CORRECT (overlay only)
context.add_shadow_cell(shadow_cell)

# NEVER DO THIS (would contaminate base)
self.chain.append(shadow_cell)  # FORBIDDEN
```

**Enforcement:** Code review + testing that asserts chain length unchanged

### 2. SimulationContext is Ephemeral

```python
def simulate_rfa(self, rfa_dict, hypothetical_changes):
    context = SimulationContext(...)  # Created
    # ... use context ...
    return result  # Context destroyed by GC

# No persistence of context
# No reference kept in Engine
# Overlay dictionary discarded after return
```

**Enforcement:** No instance variables storing context; all local scope

### 3. Shadow Cells Are Indistinguishable Structurally

Shadow cells are normal `DecisionCell` instances with valid cell_ids. The "shadow" nature is context-level, not cell-level:

```python
# Shadow cell
shadow = DecisionCell(
    header=Header(...),
    fact=Fact(...),
    logic_anchor=LogicAnchor(...)
)

# Has valid cell_id (computed normally)
assert shadow.verify_integrity()

# But tracked in context
context.shadow_cell_ids.add(shadow.cell_id)
```

**Why:** Enables normal Scholar logic to work without modification; shadow cells follow all validation rules

**Enforcement:** No `is_shadow` flag on cells; tracking in context only

### 4. Read-Only Chain Access

```python
class SimulationContext:
    base_chain: Chain  # Reference, not copy

    def get_cell(self, cell_id: str):
        # Check overlay first (write layer)
        if cell_id in self.overlay:
            return self.overlay[cell_id]
        # Fall back to base (read-only)
        return self.base_chain.get_cell(cell_id)
```

**Enforcement:** No calls to chain mutation methods (append, etc.)

### 5. Proof Bundle Tagging

All facts in shadow reality are tagged in proof bundles:

```python
{
    "proof_bundle": {
        "results": {
            "facts": [
                {
                    "cell_id": "abc123...",
                    "origin": "BASE"  # From base chain
                },
                {
                    "cell_id": "def456...",
                    "origin": "SHADOW"  # From overlay
                }
            ]
        }
    }
}
```

**Why:** Auditors can distinguish real vs hypothetical facts

**Enforcement:** OverlayScholar tags during query_facts()

**Confidence:** HIGH (proven pattern from copy-on-write file systems)

## Build Order (Suggested Phase Sequence)

### Phase 1: Context Foundation
**Goal:** Overlay container with zero-mutation guarantee

**Components:**
- SimulationContext class
- Basic get_cell() overlay-before-base logic
- Unit tests proving chain unchanged

**Success Criteria:**
- Can add shadow cells to context
- Can retrieve cells from overlay
- Chain.cells length unchanged after context destruction

**Estimated Complexity:** Low
**No Dependencies:** Uses existing Chain, Cell

---

### Phase 2: Shadow Cell Factory
**Goal:** Create valid shadow cells linked to base

**Components:**
- ShadowCellBuilder class
- create_shadow_fact() method
- Validation that shadows have valid cell_ids

**Success Criteria:**
- Shadow cells pass verify_integrity()
- Shadow cells link to base chain head
- Shadow cells use base graph_id

**Estimated Complexity:** Low
**Depends On:** Phase 1 (SimulationContext)

---

### Phase 3: Overlay Scholar
**Goal:** Query overlay with base fallback

**Components:**
- OverlayScholar class (inherits Scholar)
- _build_overlay_index() method
- Proof bundle tagging (BASE vs SHADOW)

**Success Criteria:**
- Overlay facts take precedence over base
- Conflict resolution works with mixed BASE/SHADOW
- Query results include origin tags

**Estimated Complexity:** Medium (index precedence is subtle)
**Depends On:** Phase 2 (shadow cells), existing Scholar

---

### Phase 4: Delta Analysis
**Goal:** Compare base vs shadow outcomes

**Components:**
- SimulationResult class
- Delta computation (added/removed/changed)
- Proof bundle generation for both realities

**Success Criteria:**
- Can identify facts added in shadow
- Can identify facts removed in shadow
- Delta report is deterministic

**Estimated Complexity:** Low (set operations)
**Depends On:** Phase 3 (OverlayScholar)

---

### Phase 5: Engine Integration
**Goal:** Public API for simulation

**Components:**
- Engine.simulate_rfa() method
- Hypothetical change parsing
- End-to-end orchestration

**Success Criteria:**
- simulate_rfa() returns SimulationResult
- Base chain unchanged after simulation
- Can run multiple simulations without interference

**Estimated Complexity:** Medium (orchestration complexity)
**Depends On:** Phase 4 (SimulationResult)

---

### Phase 6: Counterfactual Anchors (Optional/Future)
**Goal:** Identify causality of deltas

**Components:**
- CounterfactualAnchor class
- _compute_anchors() method
- Reasoning chain tracking

**Success Criteria:**
- Can trace which shadow cells caused deltas
- Reasoning chains show transitive dependencies

**Estimated Complexity:** High (causality analysis)
**Depends On:** Phase 5 (full simulation pipeline)

**Note:** This phase may be deferred to v1.7 if MVP doesn't require causality tracking

## Anti-Patterns to Avoid

### Anti-Pattern 1: Shadow Flags on Cells

**Bad:**
```python
@dataclass
class DecisionCell:
    is_shadow: bool = False  # DON'T DO THIS
```

**Why Bad:** Pollutes cell structure; makes cells context-dependent; breaks cell immutability

**Instead:** Track shadow status in SimulationContext.shadow_cell_ids

---

### Anti-Pattern 2: Modifying Scholar Directly

**Bad:**
```python
class Scholar:
    def query_facts(self, overlay=None):  # DON'T DO THIS
        if overlay:
            # ... special logic ...
```

**Why Bad:** Couples Scholar to simulation; makes base case more complex; harder to test

**Instead:** Create OverlayScholar subclass that overrides behavior

---

### Anti-Pattern 3: Persisting SimulationContext

**Bad:**
```python
class Engine:
    def __init__(self):
        self._active_simulations = {}  # DON'T DO THIS
```

**Why Bad:** Risk of shadow cells leaking into base queries; memory leak; unclear lifetime

**Instead:** Context is local to simulate_rfa(), destroyed on return

---

### Anti-Pattern 4: Mutating Base Chain for Convenience

**Bad:**
```python
def simulate_rfa(self, ...):
    # Add shadows to chain temporarily
    for shadow in shadows:
        self.chain.append(shadow)  # DON'T DO THIS

    # Query
    result = self.scholar.query_facts(...)

    # Remove shadows
    self.chain.cells = self.chain.cells[:-len(shadows)]
```

**Why Bad:** Race conditions; violates append-only invariant; breaks chain validation

**Instead:** Use overlay dictionary, never touch chain

---

### Anti-Pattern 5: Reusing Overlay Between Simulations

**Bad:**
```python
# Simulation 1
context.add_shadow_cell(shadow1)
result1 = simulate(context)

# Simulation 2 (reuses context)
context.add_shadow_cell(shadow2)  # DON'T DO THIS
result2 = simulate(context)  # Contaminated with shadow1
```

**Why Bad:** Simulations interfere; non-deterministic results; hard to debug

**Instead:** Create fresh SimulationContext per simulate_rfa() call

## Alternative Architectures Considered

### Alternative 1: Clone Chain Per Simulation

**Approach:** Copy entire chain, mutate copy, compare

**Pros:** Simple conceptually; no overlay complexity

**Cons:**
- O(n) memory per simulation (chain copy)
- Slow for large chains
- Violates "never mutate chain" principle (even a copy)

**Rejected Because:** Doesn't scale; violates zero-mutation guarantee

---

### Alternative 2: Separate Shadow Chain

**Approach:** Create second Chain instance for shadows

**Pros:** Clean separation; both chains are valid

**Cons:**
- How to link shadow to base? (orphaned chain)
- Scholar needs to query two chains (complexity)
- Bridge authorization breaks (two different namespaces)

**Rejected Because:** Breaks namespace isolation logic; too much rework

---

### Alternative 3: Time-Travel Branches (Git-like)

**Approach:** Chain has branches; shadow is a branch

**Pros:** Natural Git-like semantics; powerful

**Cons:**
- Requires branching logic in Chain (major change)
- Merge semantics unclear
- Overkill for ephemeral simulation

**Rejected Because:** Too complex for use case; simulation is throwaway, not persistent

---

### Alternative 4: Database Transactions (Rollback)

**Approach:** Begin transaction, add shadows, rollback

**Pros:** Standard database pattern

**Cons:**
- Requires transaction system (not in DecisionGraph)
- Rollback = mutation (violates append-only)
- Persistence risk if commit called accidentally

**Rejected Because:** Requires persistence layer; against append-only principle

## Integration Patterns from Other Systems

### Git's Working Tree vs Index vs HEAD

**Pattern:** Three layers — HEAD (committed), index (staged), working tree (uncommitted)

**Relevance:** SimulationContext.overlay = working tree; base chain = HEAD

**Lesson:** Clear separation prevents accidental commits

**Confidence:** HIGH (proven pattern)

---

### Copy-on-Write File Systems (ZFS, Btrfs)

**Pattern:** Base snapshot is immutable; writes go to new blocks

**Relevance:** Shadow cells are "new blocks"; base chain is frozen snapshot

**Lesson:** Structural sharing (don't copy unchanged parts)

**Confidence:** HIGH (decades of production use)

**Source:** [Shadow Paging - Wikipedia](https://en.wikipedia.org/wiki/Shadow_paging)

---

### Persistent Data Structures (Clojure, Haskell)

**Pattern:** Immutable base; new version shares unmodified parts

**Relevance:** OverlayScholar index shares base cells, adds overlay cells

**Lesson:** Persistent data structures enable efficient "forking"

**Confidence:** HIGH (functional programming staple)

**Source:** [Persistent data structure - Wikipedia](https://en.wikipedia.org/wiki/Persistent_data_structure)

---

### Event Sourcing + Projection

**Pattern:** Event log is immutable; projections can be rebuilt

**Relevance:** Base chain = event log; OverlayScholar = projection with extra events

**Lesson:** Replayability enables what-if analysis

**Confidence:** MEDIUM (similar pattern, different domain)

**Source:** [Immutable Databases: the Evolution of Data Integrity?](https://www.navicat.com/en/company/aboutus/blog/3347-immutable-databases-the-evolution-of-data-integrity)

---

### Temporal Database Bitemporal Queries

**Pattern:** Valid time vs transaction time; query as-of both

**Relevance:** Base snapshot = (valid_time, system_time); shadow adds hypothetical facts at same snapshot

**Lesson:** Bitemporal coordinates isolate simulation time

**Confidence:** MEDIUM (DecisionGraph already has bitemporal semantics)

**Source:** [Temporal database - Wikipedia](https://en.wikipedia.org/wiki/Temporal_database)

## Scalability Considerations

### At 1K Cells in Chain

**Performance:**
- Chain.get_cell(): O(1) via index
- Context.get_cell(): O(1) overlay + O(1) fallback
- Overlay index build: O(n) where n = base cells + shadow cells
- Single simulation: <10ms

**Memory:**
- Base chain: ~1KB per cell = 1MB
- Shadow cells: 10-100 per simulation = 10-100KB
- Context overhead: ~1KB

**Recommendation:** No optimization needed

---

### At 100K Cells in Chain

**Performance:**
- Overlay index build: ~100ms (one-time per simulation)
- Multiple simulations: Rebuild index each time
- Query performance: Same as base Scholar (index-backed)

**Memory:**
- Base chain: 100MB
- Shadow cells: 10-100KB (unchanged)
- Context overhead: ~1KB

**Optimization Opportunity:** Cache base Scholar index, only add overlay cells

**Recommendation:** Consider index caching if >10 simulations/sec

---

### At 1M Cells in Chain

**Performance:**
- Overlay index build: ~1s (significant overhead)
- Multiple simulations: Index rebuild dominates

**Memory:**
- Base chain: 1GB
- Shadow cells: 10-100KB (unchanged)

**Optimization Required:**
- Reuse base Scholar index across simulations
- Only build overlay portion of index
- Consider sparse indexing (only namespaces involved)

**Recommendation:** Phase 3 should include index reuse optimization

---

### At 10M Cells in Chain

**Performance:**
- Full index rebuild: ~10s (unacceptable)

**Memory:**
- Base chain: 10GB

**Optimization Required:**
- Must reuse base Scholar index
- Must use sparse namespace filtering
- Consider async simulation (don't block on index build)

**Recommendation:** Add performance requirements flag at v1.6 planning

## Risk Assessment

### Risk 1: Shadow Cells Leak into Base Queries

**Probability:** Medium (if OverlayScholar passed to wrong code)

**Impact:** High (contamination of base reality results)

**Mitigation:**
- Type safety: OverlayScholar is separate class
- Testing: Assert base Scholar never sees shadow cells
- Code review: simulate_rfa() uses local scope only

**Confidence:** MEDIUM (needs careful implementation)

---

### Risk 2: Index Precedence Bugs

**Probability:** Medium (overlay index logic is subtle)

**Impact:** Medium (wrong facts win conflict resolution)

**Mitigation:**
- Unit tests: Multiple scenarios (overlay wins, base wins, no conflict)
- Property tests: Commutativity of index builds
- Integration tests: End-to-end with mixed BASE/SHADOW

**Confidence:** MEDIUM (requires thorough testing)

---

### Risk 3: Memory Leak via Persistent Context

**Probability:** Low (Python GC should handle)

**Impact:** High (memory grows unbounded)

**Mitigation:**
- No instance variables storing context
- Explicit `del context` if needed
- Memory profiling during testing

**Confidence:** HIGH (standard Python memory management)

---

### Risk 4: Bridge Authorization Breaks with Overlay

**Probability:** Low (bridges are in base chain, not overlay)

**Impact:** Medium (cross-namespace queries fail)

**Mitigation:**
- OverlayScholar uses base chain bridges (no shadow bridges)
- Test cross-namespace simulation explicitly

**Confidence:** HIGH (bridges are base reality, unchanged)

---

### Risk 5: Performance Degrades with Many Shadows

**Probability:** Medium (1000+ shadow cells per simulation)

**Impact:** Medium (simulation slows to seconds)

**Mitigation:**
- Limit shadow cells per simulation (e.g., 100 max)
- Document performance characteristics
- Optimize index build in Phase 3 if needed

**Confidence:** MEDIUM (depends on use case)

## Sources

### Architectural Patterns (HIGH Confidence)
- [Persistent data structure - Wikipedia](https://en.wikipedia.org/wiki/Persistent_data_structure)
- [Shadow paging - Wikipedia](https://en.wikipedia.org/wiki/Shadow_paging)
- [Write-ahead logging - Wikipedia](https://en.wikipedia.org/wiki/Write-ahead_logging)
- [Persistent data structures in functional programming | SoftwareMill](https://softwaremill.com/persistent-data-structures-in-functional-programming/)

### Database & Immutability (MEDIUM Confidence)
- [Immutable Databases: the Evolution of Data Integrity?](https://www.navicat.com/en/company/aboutus/blog/3347-immutable-databases-the-evolution-of-data-integrity)
- [Temporal database - Wikipedia](https://en.wikipedia.org/wiki/Temporal_database)
- [Bi-Temporal Data Modeling: An Overview | Medium](https://contact-rajeshvinayagam.medium.com/bi-temporal-data-modeling-an-overview-cbba335d1947)

### Simulation & Counterfactuals (LOW Confidence — domain-specific)
- [Generating Efficiently Realistic Counterfactual Explanations | Machine Learning](https://link.springer.com/article/10.1007/s10994-025-06947-2)
- [Counterfactual Simulation](https://counterfactualsimulation.github.io/)

### DecisionGraph Codebase (HIGH Confidence — direct inspection)
- `src/decisiongraph/chain.py` — Chain class, append-only semantics
- `src/decisiongraph/scholar.py` — Scholar query resolution, ScholarIndex
- `src/decisiongraph/engine.py` — Engine.process_rfa() pattern
- `src/decisiongraph/cell.py` — DecisionCell structure, cell_id computation

---

**Research completed:** 2026-01-28
**Confidence level:** HIGH (existing integration points) + MEDIUM (overlay implementation details)
**Recommended next steps:** Validate build order with engineering team; prototype Phase 1 to confirm zero-contamination pattern
