# Stack Research: Oracle Layer (v1.6) — Counterfactual Simulation

**Project:** DecisionGraph v1.6 — Oracle Layer for "What-If" Simulation
**Researched:** 2026-01-28
**Confidence:** HIGH

## Executive Summary

v1.6 adds counterfactual simulation capabilities ("what-if" analysis) through a shadow overlay architecture. After researching immutable data structure libraries, copy-on-write mechanisms, and simulation frameworks in Python, **we recommend using dataclasses.replace() with the existing stack — zero new dependencies required**.

**Rationale:** DecisionGraph already uses frozen dataclasses for immutability and determinism. Python 3.13's `dataclasses.replace()` (and the new `copy.replace()`) provide efficient shallow copying for creating shadow cells. Pyrsistent would add structural sharing but at the cost of a new dependency and conversion overhead. For an in-memory simulation layer with deterministic outputs, native dataclass replacement is simpler and sufficient.

**Key insight:** Shadow cells are not modifications to existing cells — they're new cells in a parallel overlay chain. The base reality chain never mutates. This makes copy-on-write optimization unnecessary; we create new cells with modified data using `dataclasses.replace()`.

## Existing Stack (Leverage)

The following existing capabilities directly support counterfactual simulation without modification:

| Component | Capability | How Oracle Leverages It |
|-----------|-----------|--------------------------|
| **Frozen dataclasses** | Immutable cells enforced at instantiation | Shadow cells use same immutability guarantees as base cells |
| **Chain** | Append-only ledger with validation | Shadow chains mirror base chain structure, validation reused |
| **Scholar** | Bitemporal query resolver | Shadow Scholar instance queries shadow chain with same logic |
| **PolicyHead** | Policy snapshot tracking | Shadow PolicyHead cells track shadow policy changes |
| **Cell content hashing** | SHA-256 deterministic hashes | Shadow cells have distinct hashes (different content) |
| **Namespace isolation** | Bridge-based authorization | Shadow reality respects same namespace rules |
| **Ed25519 signing** | Cryptographic cell signatures | Shadow cells can optionally be unsigned (simulation-only) |
| **RFA validation** | Schema and input validation | Same validation applies to shadow fact injection |

**Confidence:** HIGH — All existing primitives work for shadow overlay without modification.

## Stack Additions: NONE

**No new dependencies required for v1.6.**

The counterfactual simulation layer leverages:
1. **Python 3.13+ `dataclasses.replace()`** — Efficient shallow copy for creating shadow cells (already available, standard library)
2. **In-memory overlay pattern** — Two Chain instances (base + shadow) in same process
3. **Delta computation via difflib** — Standard library for comparing base vs shadow state
4. **Deterministic execution** — Same inputs = same simulation outputs (existing guarantee)

### Why Not Pyrsistent?

| Criterion | dataclasses.replace() | Pyrsistent PVector/PMap |
|-----------|----------------------|-------------------------|
| **Structural sharing** | No (full shallow copy) | Yes (O(log n) path copying) |
| **Memory efficiency** | Acceptable for simulation workload | More efficient for large chains |
| **Integration complexity** | Zero (native dataclass support) | Medium (convert Cell → PVector) |
| **New dependency** | No | Yes (pyrsistent>=0.20.0) |
| **Performance** | Microseconds per copy | O(log n) operations |
| **Fits existing stack** | Perfect | Requires conversion layer |
| **Determinism** | Guaranteed | Guaranteed |

**Decision:** For an in-memory simulation layer with typically small chains (< 10,000 cells) and one-shot simulations (not long-running), the overhead of `dataclasses.replace()` is acceptable. Pyrsistent's structural sharing benefits large persistent structures with frequent modifications — not DecisionGraph's use case.

**When to reconsider:** If simulations involve chains with > 100,000 cells or require persistent shadow state across multiple simulation runs, Pyrsistent's path copying becomes valuable.

**Confidence:** HIGH — Based on [Pyrsistent documentation](https://github.com/tobgu/pyrsistent) and Python 3.13 [copy.replace() feature](https://medium.com/@bnln/python-3-13s-new-copy-replace-24bf61c37be7).

## Recommended Patterns

### 1. Shadow Cell Creation Pattern

Use `dataclasses.replace()` to create shadow cells from base cells with modified fields.

```python
from dataclasses import replace

# Base reality cell
base_cell = DecisionCell(
    header=Header(...),
    fact=Fact(namespace="corp.hr", subject="employee:alice", predicate="salary", object="80000"),
    logic_anchor=LogicAnchor(...),
    proof=Proof(...)
)

# Shadow cell: What if Alice's salary was 90000?
shadow_cell = replace(
    base_cell,
    fact=replace(base_cell.fact, object="90000"),
    # Note: cell_id will differ (different content hash)
)
```

**Why this works:**
- `replace()` creates new instance (satisfies immutability)
- Shallow copy is sufficient (no nested mutable fields in Cell dataclass)
- Content hash automatically recomputes (different cell_id)
- Original base_cell unchanged (zero contamination guarantee)

**Performance:** `dataclasses.replace()` is microseconds per call, not milliseconds like `copy.deepcopy()` ([Codeflash analysis](https://www.codeflash.ai/blog-posts/why-pythons-deepcopy-can-be-so-slow-and-how-to-avoid-it)).

**Confidence:** HIGH — Standard pattern from Python 3.13+ documentation.

### 2. Overlay Chain Pattern

Maintain two separate Chain instances: base reality and shadow reality.

```python
class Oracle:
    """Layer 5: Counterfactual simulation orchestrator."""

    def __init__(self, base_chain: Chain):
        self.base_chain = base_chain  # Read-only reference
        self.shadow_chain: Optional[Chain] = None  # Created during simulation
        self.shadow_scholar: Optional[Scholar] = None

    def fork_shadow_reality(self) -> None:
        """Create shadow chain as copy of base chain."""
        # Option 1: Deep copy entire chain (simple, memory-intensive)
        self.shadow_chain = copy.deepcopy(self.base_chain)

        # Option 2: Shallow copy with shared cells (efficient)
        self.shadow_chain = Chain(
            cells=list(self.base_chain.cells),  # Share cell references
            graph_id=self.base_chain.graph_id,
            root_namespace=self.base_chain.root_namespace
        )

        # Shadow Scholar queries shadow chain
        self.shadow_scholar = create_scholar(self.shadow_chain)

    def inject_counterfactual_fact(
        self,
        namespace: str,
        subject: str,
        predicate: str,
        counterfactual_value: str
    ) -> str:
        """Inject hypothetical fact into shadow reality."""
        # Create shadow fact cell
        shadow_fact = create_fact_cell(
            namespace=namespace,
            subject=subject,
            predicate=predicate,
            object=counterfactual_value,
            # ... other fields
        )

        # Append to shadow chain only
        self.shadow_chain.append(shadow_fact)
        return shadow_fact.header.cell_id

    def compute_delta(self) -> DeltaReport:
        """Compare base vs shadow reality outcomes."""
        base_result = self.base_chain.scholar.query_facts(...)
        shadow_result = self.shadow_scholar.query_facts(...)

        return DeltaReport(
            base_facts=base_result.facts,
            shadow_facts=shadow_result.facts,
            diff=compute_fact_diff(base_result, shadow_result)
        )
```

**Key principles:**
1. **Structural isolation** — Base and shadow are separate Chain instances
2. **Shared genesis** — Shadow chain includes all base cells at fork time
3. **Divergence point** — Shadow mutations only affect shadow chain
4. **Zero contamination** — Base chain is read-only during simulation

**Confidence:** HIGH — Standard overlay pattern from [bitemporal simulation research](https://github.com/1123/bitemporaldb).

### 3. Delta Computation Pattern

Use Python's `difflib` (standard library) for computing differences between base and shadow states.

```python
import difflib
from dataclasses import dataclass
from typing import List

@dataclass
class FactDiff:
    """Difference between base and shadow fact."""
    subject: str
    predicate: str
    base_value: Optional[str]
    shadow_value: Optional[str]
    diff_type: str  # "added" | "removed" | "modified" | "unchanged"

def compute_fact_diff(
    base_facts: List[Fact],
    shadow_facts: List[Fact]
) -> List[FactDiff]:
    """Compute delta between base and shadow fact lists."""
    # Convert to comparable format
    base_dict = {(f.subject, f.predicate): f.object for f in base_facts}
    shadow_dict = {(f.subject, f.predicate): f.object for f in shadow_facts}

    diffs = []

    # Added facts (in shadow, not in base)
    for key in shadow_dict.keys() - base_dict.keys():
        diffs.append(FactDiff(
            subject=key[0],
            predicate=key[1],
            base_value=None,
            shadow_value=shadow_dict[key],
            diff_type="added"
        ))

    # Removed facts (in base, not in shadow)
    for key in base_dict.keys() - shadow_dict.keys():
        diffs.append(FactDiff(
            subject=key[0],
            predicate=key[1],
            base_value=base_dict[key],
            shadow_value=None,
            diff_type="removed"
        ))

    # Modified facts (different values)
    for key in base_dict.keys() & shadow_dict.keys():
        if base_dict[key] != shadow_dict[key]:
            diffs.append(FactDiff(
                subject=key[0],
                predicate=key[1],
                base_value=base_dict[key],
                shadow_value=shadow_dict[key],
                diff_type="modified"
            ))

    return diffs
```

**Why difflib is sufficient:**
- Standard library (no dependency)
- Designed for sequence comparison
- Works with any hashable/comparable objects
- Used for text diffs, can adapt for fact diffs

**Confidence:** HIGH — [Python difflib documentation](https://docs.python.org/3/library/difflib.html) (updated 2026-01-26).

### 4. Deterministic Simulation Pattern

Ensure same inputs always produce same simulation outputs.

```python
@dataclass
class SimulationRequest:
    """Deterministic simulation input."""
    base_chain_hash: str  # Hash of base chain state
    counterfactual_facts: List[Tuple[str, str, str, str]]  # (ns, subj, pred, obj)
    query_params: Dict[str, Any]  # namespace, policy_mode, as_of times
    simulation_id: str  # For auditing/reproducibility

def simulate_counterfactual(request: SimulationRequest) -> SimulationResult:
    """
    Run deterministic simulation.

    Determinism guarantees:
    1. Same base_chain_hash + counterfactual_facts = same shadow_chain
    2. Same shadow_chain + query_params = same QueryResult
    3. Same QueryResult = same DeltaReport

    No randomness, no timestamps (use request times), no external I/O.
    """
    # Validate base chain hasn't changed
    if compute_chain_hash(base_chain) != request.base_chain_hash:
        raise SimulationError("Base chain mutated during simulation")

    # Fork shadow reality
    oracle.fork_shadow_reality()

    # Inject counterfactual facts (deterministic order)
    for ns, subj, pred, obj in sorted(request.counterfactual_facts):
        oracle.inject_counterfactual_fact(ns, subj, pred, obj)

    # Query shadow reality
    shadow_result = oracle.shadow_scholar.query_facts(**request.query_params)

    # Compute delta
    base_result = oracle.base_chain.scholar.query_facts(**request.query_params)
    delta = compute_delta(base_result, shadow_result)

    return SimulationResult(
        simulation_id=request.simulation_id,
        base_facts=base_result.facts,
        shadow_facts=shadow_result.facts,
        delta=delta,
        reproducible=True  # Guaranteed by deterministic execution
    )
```

**Key guarantees:**
1. **No clock reads** — Use request timestamps, not `get_current_timestamp()`
2. **Sorted inputs** — Process counterfactual facts in deterministic order
3. **No external I/O** — Pure in-memory computation
4. **Chain integrity** — Validate base chain unchanged during simulation

**Confidence:** HIGH — Existing DecisionGraph constraint, extended to simulation layer.

## Integration Points

### Chain Integration

**Shadow Chain Creation:**
- `Chain.__init__()` already accepts list of cells → no modification needed
- Shadow chain uses same validation logic as base chain
- Fork operation: `shadow_chain = Chain(cells=list(base_chain.cells), ...)`

**Zero modification required.**

### Scholar Integration

**Shadow Scholar Instantiation:**
- `create_scholar(chain)` already works with any Chain instance
- Shadow Scholar queries shadow chain with identical logic
- Bitemporal queries work as-is (valid_time and system_time)

**Zero modification required.**

### PolicyHead Integration

**Shadow PolicyHead:**
- Shadow reality can have different active policies than base reality
- PolicyHead cells in shadow chain track shadow policy state
- Scholar's `policy_mode="promoted_only"` works for shadow queries

**Zero modification required.**

### Engine Integration

**Oracle as Layer 5:**
- Engine (Layer 4) provides RFA processing
- Oracle (Layer 5) wraps Engine with simulation capabilities
- `Oracle.inject_counterfactual_fact()` uses same cell creation as Engine
- Simulation results returned to caller; base chain never touched

**New component, no modification to Engine.**

## Not Adding

### 1. Pyrsistent Library

**What:** Persistent/immutable/functional data structures for Python with structural sharing.

**Why not:**
- Adds dependency (pyrsistent>=0.20.0)
- Requires conversion layer (DecisionCell → PVector)
- Structural sharing benefits large, long-lived structures
- DecisionGraph simulations are one-shot, in-memory, typically small chains
- `dataclasses.replace()` is sufficient and zero-dependency

**When to reconsider:** If simulations involve chains > 100K cells or persistent shadow state.

**Confidence:** HIGH — [Pyrsistent GitHub](https://github.com/tobgu/pyrsistent) shows O(log n) benefits for persistent modifications, not one-shot simulations.

### 2. CARLA / DiCE / Action-Rules Libraries

**What:** Counterfactual explanation libraries for ML model interpretability.

**Why not:**
- Designed for ML model explainability ("why did model predict X?")
- DecisionGraph is a decision engine, not an ML model
- These libraries optimize for finding minimal counterfactual changes
- DecisionGraph simulations explicitly specify counterfactual facts

**Different domain:** ML interpretability vs decision engine simulation.

**Confidence:** HIGH — [CARLA documentation](https://carla-counterfactual-and-recourse-library.readthedocs.io/) and [DiCE GitHub](https://github.com/interpretml/DiCE) focus on ML models.

### 3. Temporal Database Libraries (temporal.io, bitemporaldb)

**What:** Temporal.io is a workflow orchestration platform; bitemporaldb is a Scala bitemporal ORM.

**Why not:**
- DecisionGraph already implements bitemporal semantics (valid_time + system_time)
- Temporal.io is for distributed workflow orchestration (different problem)
- bitemporaldb targets SQL databases, not in-memory decision graphs

**Already solved:** Scholar provides bitemporal queries natively.

**Confidence:** HIGH — [Temporal.io Python SDK](https://python.temporal.io/) is for workflow orchestration; [bitemporaldb](https://github.com/1123/bitemporaldb) targets ORM use cases.

### 4. Shadow Copy Windows API

**What:** Windows Volume Shadow Copy Service for filesystem snapshots.

**Why not:**
- OS-level filesystem snapshots, not Python data structures
- DecisionGraph is cross-platform (Linux, macOS, Windows)
- In-memory simulation, not filesystem persistence

**Wrong abstraction layer.**

**Confidence:** HIGH — [Wikipedia Shadow Copy](https://en.wikipedia.org/wiki/Shadow_Copy) describes OS-level backup service.

### 5. Copy-on-Write Optimization Libraries

**What:** Libraries that optimize memory usage via lazy copying.

**Why not:**
- Python's GC and reference counting already handle shared immutable objects
- Shadow cells are *new* cells with different content, not copies of existing cells
- `dataclasses.replace()` creates new instances (correct semantics for simulation)

**Not needed:** Shadow cells are semantically distinct, not optimized copies.

**Confidence:** MEDIUM — No specific Python CoW library found; concept more relevant to systems programming.

## Installation

No new dependencies required. Existing stack sufficient:

```bash
# Already in pyproject.toml from v1.3-1.5
cryptography>=46.0

# Standard library (built-in)
dataclasses, copy, difflib, typing, hashlib, json
```

**Python version requirement remains:** `>=3.10` (3.13+ recommended for `copy.replace()`, but `dataclasses.replace()` works on 3.10+).

## Implementation Roadmap Implications

Based on stack decisions, recommended phase structure:

1. **Phase 1: Shadow Cell Creation**
   - Implement shadow cell factory using `dataclasses.replace()`
   - Validate immutability and deterministic hashing
   - LOW complexity (standard library pattern)

2. **Phase 2: Oracle Fork/Overlay**
   - Implement `Oracle.fork_shadow_reality()`
   - Create shadow Chain and shadow Scholar instances
   - Test structural isolation (base unchanged)
   - MEDIUM complexity (Chain/Scholar instantiation)

3. **Phase 3: Counterfactual Injection**
   - Implement `Oracle.inject_counterfactual_fact()`
   - Validate shadow chain accepts new facts
   - Ensure base chain never mutated
   - LOW complexity (reuses existing cell creation)

4. **Phase 4: Delta Computation**
   - Implement fact diff using set operations
   - Create DeltaReport with base vs shadow comparison
   - MEDIUM complexity (state comparison logic)

5. **Phase 5: Deterministic Simulation**
   - Implement `SimulationRequest` and `SimulationResult`
   - Validate determinism (same input = same output)
   - Add reproducibility guarantees
   - MEDIUM complexity (input validation, hashing)

6. **Phase 6: Shadow PolicyHead Integration**
   - Test shadow policy promotion
   - Validate shadow Scholar respects shadow PolicyHead
   - LOW complexity (existing PolicyHead logic works)

## Research Gaps

1. **Shadow Chain Memory Optimization:** Should shadow chain share cell references with base chain, or deep copy? Needs memory profiling for large chains.

2. **Counterfactual Anchor Algorithm:** How to compute "minimal change explanation" (which facts changed to cause delta)? Needs algorithm design.

3. **Simulation Rollback:** Can multiple simulations reuse same shadow chain, or one-shot only? Needs lifecycle management decision.

4. **Shadow Signature Validation:** Should shadow cells be signed? Or unsigned (simulation-only)? Needs security model clarification.

## Sources

### Python Copy Mechanisms
- [Python 3.13 copy.replace()](https://medium.com/@bnln/python-3-13s-new-copy-replace-24bf61c37be7) — New standard library feature
- [dataclasses.replace() documentation](https://docs.python.org/3/library/dataclasses.html) — Official Python docs (updated 2026-01-28)
- [Shallow vs Deep Copy Performance](https://www.codeflash.ai/blog-posts/why-pythons-deepcopy-can-be-so-slow-and-how-to-avoid-it) — Performance analysis
- [Real Python: Copy Objects Guide](https://realpython.com/python-copy/) — Comprehensive tutorial

### Immutable Data Structures
- [Pyrsistent GitHub](https://github.com/tobgu/pyrsistent) — Persistent data structures for Python
- [Pyrsistent Documentation](https://pyrsistent.readthedocs.io/en/latest/intro.html) — API and concepts
- [Frozen Dataclasses Guide](https://plainenglish.io/blog/why-and-how-to-write-frozen-dataclasses-in-python-69050ad5c9d4) — Immutability patterns

### Bitemporal and Simulation Patterns
- [bitemporaldb GitHub](https://github.com/1123/bitemporaldb) — Bitemporal database architecture
- [XTDB Bitemporality](https://v1-docs.xtdb.com/concepts/bitemporality/) — Two-dimensional time queries
- [Snowflake Bitemporal Modeling (2026)](https://medium.com/@joshirish/modeling-bi-temporality-and-using-temporal-joins-asof-join-in-snowflake-db-d2b871f4934a) — Recent temporal patterns
- [SurrealDB VART](https://surrealdb.com/blog/vart-a-persistent-data-structure-for-snapshot-isolation) — Snapshot isolation data structures

### Delta Computation
- [Python difflib](https://docs.python.org/3/library/difflib.html) — Standard library diff utilities (updated 2026-01-26)
- [deltas PyPI](https://pypi.org/project/deltas/) — Experimental diff library

### Counterfactual Explanation (ML Context)
- [CARLA Library](https://carla-counterfactual-and-recourse-library.readthedocs.io/) — Counterfactual benchmarking
- [DiCE GitHub](https://github.com/interpretml/DiCE) — Diverse counterfactual explanations
- [Counterfactual Simulation Research](https://counterfactualsimulation.github.io/) — Academic perspective

---

**Last updated:** 2026-01-28
**Confidence:** HIGH (Core recommendations), MEDIUM (Memory optimization strategies)
**Ready for:** Roadmap creation
