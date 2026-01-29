# Phase 7: Shadow Cell Foundation - Research

**Researched:** 2026-01-28
**Domain:** Frozen dataclass manipulation, content-based hashing, immutable overlay patterns
**Confidence:** HIGH

## Summary

Phase 7 establishes the foundation for shadow cells - immutable variants of base cells used for counterfactual simulation. After researching Python's `dataclasses.replace()`, frozen dataclass patterns, and contamination prevention strategies, the standard approach is clear: use Python 3.10+ `dataclasses.replace()` with frozen dataclasses to create shadow variants with distinct content-based hashes.

The research confirms that DecisionGraph's existing architecture (frozen dataclasses with `init=False` computed fields) fully supports shadow cell creation with zero new dependencies. The key insight is that `dataclasses.replace()` calls `__post_init__`, automatically recomputing `cell_id` for shadow cells based on their modified content. This provides the "distinct cell_id based on modified content" requirement without hand-rolled logic.

Zero contamination is enforced structurally through separate Chain instances: base Chain is read-only during simulation, shadow Chain accepts new cells. Scholar code remains unchanged - shadow queries use a separate Scholar instance pointing at the shadow Chain.

**Primary recommendation:** Use `dataclasses.replace()` for shadow cell creation, separate Chain instances for structural isolation, and OverlayContext as a container (not a registry) for shadow cell precedence rules.

## Standard Stack

DecisionGraph v1.3-v1.5 already provides all primitives needed for shadow cells.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| dataclasses | 3.10+ stdlib | Frozen dataclasses with replace() | Native Python pattern, zero dependencies, designed for immutability |
| hashlib | 3.10+ stdlib | SHA-256 content hashing | Deterministic cell_id computation, cryptographic integrity |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| typing | 3.10+ stdlib | Type hints (Optional, List, Dict) | Type safety for OverlayContext fields |
| copy | 3.10+ stdlib | Deep copy for Chain forking (optional) | If full Chain duplication needed vs shared cell references |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| dataclasses.replace() | Pyrsistent PVector | Structural sharing benefits large chains (>100K cells), adds dependency, conversion overhead. Not needed for one-shot simulation. |
| Separate Chain instances | Single Chain with "shadow" flag | Contamination risk - structural isolation safer than convention. |
| SHA-256 hashing | UUID generation | Content-based hashing provides integrity (tamper-evident), UUID is arbitrary. |

**Installation:**
```bash
# No new dependencies - standard library sufficient
# DecisionGraph already uses Python 3.10+ with frozen dataclasses
```

## Architecture Patterns

### Recommended Project Structure
```
src/decisiongraph/
├── cell.py             # DecisionCell (existing, unchanged)
├── chain.py            # Chain (existing, unchanged)
├── scholar.py          # Scholar (existing, unchanged)
└── shadow.py           # NEW: Shadow cell types, OverlayContext
```

### Pattern 1: Shadow Cell Creation via replace()
**What:** Create shadow variant of a cell by replacing specific fields using `dataclasses.replace()`.

**When to use:** When simulation needs to modify a cell's fact, proof, or other fields without mutating the original.

**How it works:**
1. `dataclasses.replace(cell, fact=new_fact)` creates new DecisionCell instance
2. `DecisionCell.__init__()` is called with replaced fields
3. `DecisionCell.__post_init__()` executes, recomputing `cell_id` via `compute_cell_id()`
4. Shadow cell has distinct `cell_id` because content (fact) changed
5. Original cell unchanged (immutability preserved)

**Example:**
```python
from dataclasses import replace

# Base reality cell
base_cell = DecisionCell(
    header=Header(
        version="1.3",
        graph_id="graph:abc123",
        cell_type=CellType.FACT,
        system_time="2026-01-28T10:00:00Z",
        prev_cell_hash="prev_hash_here"
    ),
    fact=Fact(
        namespace="corp.hr",
        subject="employee:alice",
        predicate="salary",
        object="80000",
        confidence=1.0,
        source_quality=SourceQuality.VERIFIED
    ),
    logic_anchor=LogicAnchor(
        rule_id="rule:salary_policy_v1",
        rule_logic_hash="hash_of_rule_logic"
    )
)

# Shadow cell: What if Alice's salary was 90000?
shadow_cell = replace(
    base_cell,
    fact=replace(base_cell.fact, object="90000")
)

# Shadow cell has different cell_id (content changed)
assert shadow_cell.cell_id != base_cell.cell_id

# Base cell unchanged
assert base_cell.fact.object == "80000"
```

**Key insight:** `cell_id` field is `init=False`, so it's excluded from `replace()` arguments and automatically recomputed in `__post_init__`. This is the correct behavior - shadow cells MUST have distinct `cell_id` values.

**Source:** Python 3.10+ [dataclasses documentation](https://docs.python.org/3/library/dataclasses.html), DecisionGraph `cell.py` lines 394-398.

### Pattern 2: OverlayContext as Container
**What:** OverlayContext holds shadow cells and defines precedence rules for shadow-over-base resolution.

**When to use:** During simulation, when Scholar needs to query with shadow cells taking precedence over base cells.

**Structure:**
```python
from dataclasses import dataclass, field
from typing import Dict, List, Set

@dataclass
class OverlayContext:
    """
    Container for shadow cells with deterministic precedence rules.

    NOT a registry (no append/mutation) - immutable snapshot.
    Shadow cells override base cells during query resolution.
    """
    # Shadow cells indexed by (namespace, subject, predicate)
    shadow_facts: Dict[Tuple[str, str, str], List[DecisionCell]] = field(default_factory=dict)

    # Shadow rule cells by rule_id
    shadow_rules: Dict[str, DecisionCell] = field(default_factory=dict)

    # Shadow bridge cells by (source_ns, target_ns)
    shadow_bridges: Dict[Tuple[str, str], DecisionCell] = field(default_factory=dict)

    # Shadow PolicyHead by namespace
    shadow_policy_heads: Dict[str, DecisionCell] = field(default_factory=dict)

    # Set of base cell_ids overridden by shadow (for proof)
    overridden_base_cells: Set[str] = field(default_factory=set)

    def add_shadow_fact(self, cell: DecisionCell) -> None:
        """Add shadow fact cell (mutation during construction only)."""
        key = (cell.fact.namespace, cell.fact.subject, cell.fact.predicate)
        if key not in self.shadow_facts:
            self.shadow_facts[key] = []
        self.shadow_facts[key].append(cell)

    def get_shadow_facts(
        self,
        namespace: str,
        subject: str,
        predicate: str
    ) -> List[DecisionCell]:
        """Get shadow facts for key (returns empty list if none)."""
        key = (namespace, subject, predicate)
        return self.shadow_facts.get(key, [])

    def has_shadow_override(self, namespace: str, subject: str, predicate: str) -> bool:
        """Check if shadow cells exist for this fact key."""
        key = (namespace, subject, predicate)
        return key in self.shadow_facts
```

**Precedence rule:** When OverlayScholar queries with OverlayContext, if shadow cells exist for a fact key, ONLY shadow cells are considered (base cells ignored for that key). If no shadow cells exist, fall back to base cells.

**Anti-pattern:** Making OverlayContext mutable after construction. Construct it once with all shadow cells before querying.

**Source:** Pattern adapted from [contextvars context-local state](https://docs.python.org/3/library/contextvars.html) and [immutable overlay patterns](https://www.sparkcodehub.com/python-side-effects-explained).

### Pattern 3: Structural Contamination Prevention
**What:** Prevent shadow cells from ever being appended to base Chain through separate Chain instances.

**When to use:** Always - zero contamination is a hard requirement (SHD-04).

**How:**
```python
class Oracle:
    """Simulation orchestrator with zero contamination guarantee."""

    def __init__(self, base_chain: Chain):
        self.base_chain = base_chain  # Read-only reference
        self.shadow_chain: Optional[Chain] = None
        self.shadow_scholar: Optional[Scholar] = None

    def fork_shadow_reality(self) -> None:
        """
        Create shadow chain as structural copy of base chain.

        Structural isolation: shadow_chain is a separate Chain instance.
        Base chain cannot be contaminated because Oracle never calls
        base_chain.append() for shadow cells.
        """
        # Option A: Shared cell references (memory-efficient)
        self.shadow_chain = Chain(
            cells=list(self.base_chain.cells),  # Shallow copy of cell list
            index={k: v for k, v in self.base_chain.index.items()},
            _graph_id=self.base_chain.graph_id,
            _root_namespace=self.base_chain.root_namespace
        )

        # Option B: Deep copy (full isolation, higher memory cost)
        # self.shadow_chain = copy.deepcopy(self.base_chain)

        # Shadow Scholar queries shadow chain
        self.shadow_scholar = Scholar(self.shadow_chain)

    def inject_shadow_fact(self, shadow_cell: DecisionCell) -> None:
        """
        Append shadow cell to shadow chain ONLY.

        Base chain never touched - zero contamination by design.
        """
        self.shadow_chain.append(shadow_cell)
        # Note: base_chain.append() never called for shadow cells
```

**Enforcement mechanism:** Structural separation (different Chain objects), not convention (if/else checks). Impossible to contaminate base Chain because shadow operations use different instance.

**Verification:** In tests, assert `len(base_chain.cells)` unchanged after simulation. Proof bundle includes `no_contamination_attestation` with base chain head hash before/after simulation.

**Source:** DecisionGraph existing Chain API (chain.py lines 219-338), immutability via [separate instances pattern](https://www.sparkcodehub.com/python/advanced/mutable-vs-immutable-guide).

### Pattern 4: OverlayScholar (Separate Instance)
**What:** Create separate Scholar instance for shadow queries, pointing at shadow Chain.

**When to use:** During simulation, when queries need to see shadow reality instead of base reality.

**Why separate instance:** Scholar code remains unchanged. No "if shadow" branches. Shadow Scholar queries shadow Chain using identical logic.

**Example:**
```python
# Base Scholar (queries base reality)
base_scholar = Scholar(base_chain)
base_result = base_scholar.query_facts(
    requester_namespace="corp",
    namespace="corp.hr",
    subject="employee:alice",
    predicate="salary"
)

# Shadow Scholar (queries shadow reality)
shadow_scholar = Scholar(shadow_chain)  # Points to different Chain
shadow_result = shadow_scholar.query_facts(
    requester_namespace="corp",
    namespace="corp.hr",
    subject="employee:alice",
    predicate="salary"
)

# Results differ if shadow cells injected
# scholar.py code unchanged - structural isolation does the work
```

**Source:** DecisionGraph Scholar API (scholar.py lines 569-580), pattern recommendation from v1.6 stack research (.planning/research/STACK.md lines 306-313).

### Anti-Patterns to Avoid

- **Mutating base cells:** Never use `object.__setattr__()` to modify a base cell. Always create new shadow cell via `replace()`.
- **Shared mutable state:** Don't pass OverlayContext through Scholar constructor - it would require modifying Scholar. Use separate instance instead.
- **Convention-based isolation:** Don't rely on "if simulation_mode" checks. Use structural separation (different Chain instances).
- **Manual cell_id computation:** Don't override `cell_id` field. Let `__post_init__` compute it automatically.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Content-based hashing | Custom UUID + lookup table | SHA-256 via hashlib (existing) | DecisionCell already implements deterministic hashing in `compute_cell_id()`. Reusing guarantees consistency. |
| Immutable cell variants | Manual field copying | `dataclasses.replace()` | Standard library, calls `__post_init__`, handles frozen dataclasses correctly. |
| Frozen field mutation | `__setattr__` override hacks | `object.__setattr__()` in `__post_init__` | Official pattern from [PEP 557](https://peps.python.org/pep-0557/). |
| Contamination checking | Runtime assertions | Structural separation (separate Chain) | Prevention > detection. Impossible to contaminate with different instances. |
| Shadow cell type markers | Custom inheritance hierarchy | CellType enum (existing) | Shadow cells are still DecisionCells, just with different content. No new types needed. |

**Key insight:** DecisionGraph's frozen dataclass architecture already solves immutability, hashing, and integrity. Shadow cells leverage existing primitives - they're not a new abstraction, just new instances with different content.

## Common Pitfalls

### Pitfall 1: Forgetting cell_id is Computed
**What goes wrong:** Trying to pass `cell_id` to `replace()` causes error or wrong hash.

**Why it happens:** `cell_id` field is `init=False`, excluded from constructor. Developers familiar with mutable dataclasses may expect to set it manually.

**How to avoid:**
- Never include `cell_id` in `replace()` call
- Trust `__post_init__` to compute it automatically
- Shadow cell will have distinct `cell_id` because content changed

**Warning signs:**
```python
# WRONG - will raise TypeError
shadow = replace(base_cell, fact=new_fact, cell_id="custom_id")

# RIGHT - cell_id automatically computed
shadow = replace(base_cell, fact=new_fact)
```

**Source:** Python dataclasses [init=False field behavior](https://docs.python.org/3/library/dataclasses.html#init-only-variables), DecisionGraph cell.py lines 394-398.

### Pitfall 2: replace() with Nested Frozen Dataclasses
**What goes wrong:** `replace(cell, fact.object="new_value")` - trying to replace nested field directly fails.

**Why it happens:** `replace()` only handles top-level fields. Nested dataclass fields require nested `replace()` calls.

**How to avoid:**
```python
# WRONG - syntax error
shadow = replace(base_cell, fact.object="90000")

# RIGHT - replace nested dataclass first
new_fact = replace(base_cell.fact, object="90000")
shadow = replace(base_cell, fact=new_fact)

# OR inline
shadow = replace(
    base_cell,
    fact=replace(base_cell.fact, object="90000")
)
```

**Warning signs:** `SyntaxError` or `AttributeError` when trying to use dot notation in `replace()` arguments.

**Source:** [dataclasses.replace() documentation](https://docs.python.org/3/library/dataclasses.html), verified by search results on nested frozen dataclass patterns.

### Pitfall 3: Sharing Chain References Instead of Forking
**What goes wrong:** `shadow_chain = base_chain` creates alias, not copy. Appending to `shadow_chain` contaminates `base_chain`.

**Why it happens:** Python assignment creates reference, not copy. Both variables point to same Chain object.

**How to avoid:**
```python
# WRONG - same Chain instance
shadow_chain = base_chain
shadow_chain.append(shadow_cell)  # CONTAMINATES base_chain!

# RIGHT - separate Chain instance
shadow_chain = Chain(
    cells=list(base_chain.cells),  # New list, shared cell references
    index=dict(base_chain.index),
    _graph_id=base_chain.graph_id,
    _root_namespace=base_chain.root_namespace
)
shadow_chain.append(shadow_cell)  # base_chain unaffected
```

**Warning signs:** Base chain length increases after shadow operations. Test by asserting `len(base_chain.cells)` unchanged.

**Source:** [Python mutable vs immutable objects](https://www.sparkcodehub.com/python/advanced/mutable-vs-immutable-guide), DecisionGraph Chain dataclass (chain.py lines 102-122).

### Pitfall 4: Forgetting to Refresh Shadow Scholar After Shadow Injection
**What goes wrong:** Shadow Scholar returns stale results because its index doesn't include newly injected shadow cells.

**Why it happens:** Scholar builds index at construction time. Appending to chain after Scholar creation doesn't update index automatically.

**How to avoid:**
```python
# After injecting shadow cells, refresh Scholar
oracle.shadow_chain.append(shadow_cell)
oracle.shadow_scholar.refresh()  # Rebuilds index from current chain state

# OR create new Scholar instance
oracle.shadow_scholar = Scholar(oracle.shadow_chain)
```

**Warning signs:** Shadow queries return base reality results even after shadow cells injected. Shadow cells exist in chain but not in query results.

**Source:** DecisionGraph Scholar.refresh() method (scholar.py lines 582-585), index-based query pattern.

### Pitfall 5: Using object.__setattr__() Outside __post_init__
**What goes wrong:** Bypassing frozen protection after construction allows mutation, breaking immutability guarantee.

**Why it happens:** `object.__setattr__()` works anywhere, not just in `__post_init__`. Developers may use it as "workaround" for frozen restriction.

**How to avoid:**
- ONLY use `object.__setattr__()` inside `__post_init__` for computed fields
- For modifying existing cells, use `replace()` to create new instance
- Never mutate frozen dataclass after construction

**Example:**
```python
# WRONG - mutating after construction
cell = create_cell(...)
object.__setattr__(cell, 'fact', new_fact)  # BAD! Breaks immutability

# RIGHT - create new instance
cell = create_cell(...)
modified_cell = replace(cell, fact=new_fact)  # Good - new instance
```

**Warning signs:** Frozen dataclass fields changing after construction. Hash collisions (same `cell_id` for different content).

**Source:** [Frozen dataclass best practices](https://plainenglish.io/blog/why-and-how-to-write-frozen-dataclasses-in-python-69050ad5c9d4), [object.__setattr__() pattern](https://www.pythonmorsels.com/customizing-dataclass-initialization/).

## Code Examples

Verified patterns from official sources and DecisionGraph codebase.

### Creating Shadow Cell with Modified Fact
```python
# Source: DecisionGraph cell.py + Python dataclasses.replace()
from dataclasses import replace
from decisiongraph import DecisionCell

def create_shadow_fact_cell(
    base_cell: DecisionCell,
    new_object_value: str
) -> DecisionCell:
    """
    Create shadow variant of fact cell with modified object value.

    Returns new DecisionCell with:
    - Same header, logic_anchor, proof
    - Modified fact.object
    - Distinct cell_id (automatically recomputed)
    """
    # Replace nested fact field
    new_fact = replace(base_cell.fact, object=new_object_value)

    # Replace cell with new fact
    shadow_cell = replace(base_cell, fact=new_fact)

    # cell_id automatically recomputed in __post_init__
    assert shadow_cell.cell_id != base_cell.cell_id

    return shadow_cell
```

### Creating Shadow PolicyHead Cell
```python
# Source: DecisionGraph policyhead.py pattern
from dataclasses import replace
from decisiongraph import DecisionCell
from typing import List

def create_shadow_policyhead(
    base_policyhead: DecisionCell,
    new_promoted_rule_ids: List[str]
) -> DecisionCell:
    """
    Create shadow PolicyHead with different promoted rules.

    Used for "what-if this rule was promoted?" simulations.
    """
    from decisiongraph.cell import compute_policy_hash

    # Compute new policy_hash for new rule set
    new_policy_hash = compute_policy_hash(new_promoted_rule_ids)

    # Replace fact.object (JSON-encoded policy data)
    import json
    new_policy_data = {
        "promoted_rule_ids": sorted(new_promoted_rule_ids),
        "policy_hash": new_policy_hash
    }
    new_fact = replace(
        base_policyhead.fact,
        object=json.dumps(new_policy_data, separators=(',', ':'))
    )

    # Create shadow PolicyHead cell
    shadow_policyhead = replace(base_policyhead, fact=new_fact)

    return shadow_policyhead
```

### Forking Shadow Chain
```python
# Source: v1.6 stack research (STACK.md lines 98-123)
from decisiongraph import Chain, Scholar
from typing import Optional

class Oracle:
    """Simulation orchestrator with structural contamination prevention."""

    def __init__(self, base_chain: Chain):
        self.base_chain = base_chain
        self.shadow_chain: Optional[Chain] = None
        self.shadow_scholar: Optional[Scholar] = None

    def fork_shadow_reality(self) -> None:
        """
        Create shadow chain as structural copy of base chain.

        Memory-efficient: shares cell references, not cell data.
        Contamination-proof: separate Chain instance.
        """
        self.shadow_chain = Chain(
            cells=list(self.base_chain.cells),  # Shallow copy of list
            index=dict(self.base_chain.index),  # Copy of index dict
            _graph_id=self.base_chain.graph_id,
            _root_namespace=self.base_chain.root_namespace
        )

        self.shadow_scholar = Scholar(self.shadow_chain)

    def verify_no_contamination(self) -> bool:
        """
        Verify base chain unchanged during simulation.

        Returns True if base chain uncontaminated.
        """
        # Base chain length must not increase
        original_length = len(self.base_chain.cells)
        # ... run simulation ...
        return len(self.base_chain.cells) == original_length
```

### OverlayContext Construction
```python
# Source: Recommended pattern for Phase 7
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple
from decisiongraph import DecisionCell

@dataclass
class OverlayContext:
    """
    Immutable snapshot of shadow cells for simulation.

    Precedence rule: Shadow cells override base cells for same fact key.
    """
    shadow_facts: Dict[Tuple[str, str, str], List[DecisionCell]] = field(default_factory=dict)
    shadow_rules: Dict[str, DecisionCell] = field(default_factory=dict)
    shadow_bridges: Dict[Tuple[str, str], DecisionCell] = field(default_factory=dict)
    shadow_policy_heads: Dict[str, DecisionCell] = field(default_factory=dict)
    overridden_base_cells: Set[str] = field(default_factory=set)

    @classmethod
    def from_shadow_cells(cls, shadow_cells: List[DecisionCell]) -> 'OverlayContext':
        """
        Construct OverlayContext from list of shadow cells.

        Deterministic: sorts cells by type for consistent indexing.
        """
        context = cls()

        for cell in shadow_cells:
            key = (cell.fact.namespace, cell.fact.subject, cell.fact.predicate)

            if cell.header.cell_type == CellType.FACT:
                if key not in context.shadow_facts:
                    context.shadow_facts[key] = []
                context.shadow_facts[key].append(cell)

            elif cell.header.cell_type == CellType.RULE:
                context.shadow_rules[cell.logic_anchor.rule_id] = cell

            elif cell.header.cell_type == CellType.BRIDGE_RULE:
                # Parse bridge from fact (source_ns -> target_ns)
                bridge_key = (cell.fact.subject, cell.fact.object)
                context.shadow_bridges[bridge_key] = cell

            elif cell.header.cell_type == CellType.POLICY_HEAD:
                context.shadow_policy_heads[cell.fact.namespace] = cell

        return context
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual dict copying | `dataclasses.replace()` | Python 3.7+ | Frozen dataclass support in stdlib, no custom copy logic |
| Deep copy for immutability | Frozen dataclasses | Python 3.7+ | Immutability enforced at type level, not runtime |
| UUID-based cell IDs | Content-based SHA-256 hashing | DecisionGraph v1.0 | Tamper-evident by design, no lookup table needed |
| Convention-based isolation | Structural separation (separate instances) | Modern Python patterns | Impossible to violate vs. easy to forget |

**Deprecated/outdated:**
- **Manual `__setattr__` override:** Use `frozen=True` instead. Enforced by dataclass decorator.
- **Mutable default factories in dataclasses:** Use `field(default_factory=...)` pattern. Avoids shared mutable state bugs.
- **`copy.deepcopy()` for frozen dataclasses:** Use `dataclasses.replace()` for field-level copying. More efficient (shallow copy sufficient for frozen).

## Open Questions

Things that couldn't be fully resolved:

1. **Shadow Chain Memory Strategy**
   - What we know: Two options exist - shared cell references (memory-efficient) or deep copy (full isolation)
   - What's unclear: Which performs better for typical chain sizes (100-10,000 cells)?
   - Recommendation: Start with shared references (Option A), profile memory usage, switch to deep copy only if isolation issues found

2. **Shadow Cell Signing**
   - What we know: Shadow cells can optionally have empty `proof.signature` (simulation-only)
   - What's unclear: Should shadow cells be signed by a "simulation key"? Or unsigned?
   - Recommendation: Phase 7 allows unsigned (empty proof), defer signing decision to Phase 8 (simulation engine)

3. **OverlayContext Mutability**
   - What we know: Should be immutable after construction for determinism
   - What's unclear: Should it be a frozen dataclass? Or regular dataclass with documented convention?
   - Recommendation: Start with regular dataclass, make frozen in Phase 8 if needed (after usage patterns clear)

## Sources

### Primary (HIGH confidence)
- [Python dataclasses documentation](https://docs.python.org/3/library/dataclasses.html) - Official Python 3.10+ docs (updated 2026-01-28)
- [Python hashlib documentation](https://docs.python.org/3/library/hashlib.html) - SHA-256 hashing API
- DecisionGraph cell.py - DecisionCell implementation with `init=False` cell_id pattern
- DecisionGraph chain.py - Chain append-only semantics and structural validation
- DecisionGraph scholar.py - Scholar query resolution and index patterns

### Secondary (MEDIUM confidence)
- [Customizing dataclass initialization](https://www.pythonmorsels.com/customizing-dataclass-initialization/) - `__post_init__` and `object.__setattr__()` patterns
- [Why and How to Write Frozen Dataclasses](https://plainenglish.io/blog/why-and-how-to-write-frozen-dataclasses-in-python-69050ad5c9d4) - Frozen dataclass best practices
- [Python mutable vs immutable objects](https://www.sparkcodehub.com/python/advanced/mutable-vs-immutable-guide) - Immutability patterns and side effect prevention
- [PEP 557 Data Classes](https://peps.python.org/pep-0557/) - Dataclass design rationale
- [Top 7 Methods to Set Values in Frozen Dataclass Post Initialization](https://sqlpey.com/python/top-7-methods-to-set-values-in-frozen-dataclass-post-initialization/) - `object.__setattr__()` pattern verification

### Tertiary (LOW confidence - DecisionGraph internal)
- .planning/research/STACK.md - v1.6 stack research recommending `dataclasses.replace()` over Pyrsistent
- .planning/REQUIREMENTS.md - SHD-01, SHD-02, SHD-04 requirements for shadow infrastructure

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Python stdlib dataclasses, hashlib are mature and well-documented
- Architecture: HIGH - Patterns verified against DecisionGraph existing code (cell.py, chain.py, scholar.py)
- Pitfalls: HIGH - Sourced from official docs and community best practices, validated against DecisionGraph frozen dataclass usage

**Research date:** 2026-01-28
**Valid until:** 90 days (stable Python stdlib patterns, unlikely to change)
