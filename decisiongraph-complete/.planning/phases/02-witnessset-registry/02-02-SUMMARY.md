---
phase: 02-witnessset-registry
plan: 02
type: summary
status: complete
completed: 2026-01-28

# Dependency Graph
requires: ["01-03", "02-01"]  # Genesis WitnessSet embedding, WitnessSet dataclass
provides:
  - WitnessRegistry stateless query layer
  - Genesis WitnessSet extraction at runtime
  - Foundation for WitnessSet change tracking
affects: ["02-03", "02-04", "03-*"]  # Future WitnessSet operations, promotion gate

# Tech Stack
tech-stack:
  added: []  # No new dependencies
  patterns:
    - "Stateless query layer (rebuild from chain state)"
    - "TYPE_CHECKING to avoid circular imports"
    - "Optional[T] for missing namespace lookups"

# Key Files
key-files:
  created:
    - src/decisiongraph/registry.py
    - tests/test_registry.py
  modified:
    - src/decisiongraph/__init__.py

# Decisions
decisions:
  - id: DEC-02-02-01
    title: "Stateless registry design (no caching)"
    rationale: "Prevents cache/chain divergence, Chain is source of truth"
    alternatives: "In-memory cache with invalidation"
    chosen: "Always rebuild from Chain state"
  - id: DEC-02-02-02
    title: "TYPE_CHECKING for Chain import"
    rationale: "Avoids circular dependency between registry.py and chain.py"
    pattern: "if TYPE_CHECKING: from .chain import Chain"
  - id: DEC-02-02-03
    title: "Single responsibility: Genesis extraction only"
    rationale: "WIT-04 (WitnessSet changes) is future phase, keep scope minimal"
    extension_point: "_build_registry() will be extended for PolicyHead scanning"

# Subsystem
subsystem: witnessset-registry

# Tags
tags: [witnessset, registry, genesis, stateless, query-layer, WIT-03]

# Metrics
metrics:
  duration: "2.5 minutes"
  tests-added: 25
  tests-total: 671
  files-created: 2
  files-modified: 1
  lines-added: 587
---

# Phase 2 Plan 02: WitnessRegistry Summary

**One-liner:** Stateless query layer extracting Genesis WitnessSet via parse_genesis_witness_set, foundation for WIT-04

---

## What Was Built

Created **WitnessRegistry**, a stateless query layer for namespace to WitnessSet lookups.

### Core Components

**1. WitnessRegistry Class** (`src/decisiongraph/registry.py`)
- `__init__(chain: Chain)` - Bind registry to Chain instance
- `get_witness_set(namespace) -> Optional[WitnessSet]` - Get WitnessSet for namespace
- `get_all_witness_sets() -> dict[str, WitnessSet]` - Get all configured WitnessSets
- `has_witness_set(namespace) -> bool` - Check if namespace has WitnessSet
- `_build_registry() -> dict[str, WitnessSet]` - Rebuild from Chain state

**2. Genesis WitnessSet Extraction** (WIT-03 Runtime)
- Uses `parse_genesis_witness_set(genesis)` from genesis.py
- Uses `has_witness_set(genesis)` to check for embedded WitnessSet
- Extracts namespace, witnesses, threshold from Genesis cell
- Returns None for legacy Genesis without WitnessSet

**3. Stateless Design**
- NO caching - rebuilds from Chain state on each query
- Chain is single source of truth
- Prevents cache invalidation complexity
- Always reflects current chain state

### Architecture

```
WitnessRegistry (stateless query layer)
    |
    ├─> Chain (source of truth)
    |       |
    |       └─> Genesis cell
    |               |
    |               └─> fact.object (JSON with witness_set)
    |
    └─> WitnessSet (immutable result)
            ├─> namespace: str
            ├─> witnesses: tuple[str, ...]
            └─> threshold: int
```

### Usage Example

```python
from decisiongraph import Chain, WitnessRegistry
from decisiongraph.genesis import create_genesis_cell_with_witness_set

# Create chain with Genesis that has WitnessSet
chain = Chain()
genesis = create_genesis_cell_with_witness_set(
    graph_name="ProdGraph",
    root_namespace="corp",
    witnesses=["alice", "bob", "charlie"],
    threshold=2
)
chain.append(genesis)

# Query the registry
registry = WitnessRegistry(chain)
ws = registry.get_witness_set("corp")
print(f"Namespace: {ws.namespace}, Threshold: {ws.threshold}")
print(f"Witnesses: {ws.witnesses}")

# Get all WitnessSets
all_ws = registry.get_all_witness_sets()
for namespace, ws in all_ws.items():
    print(f"{namespace}: {ws.threshold}-of-{len(ws.witnesses)}")

# Check if namespace has WitnessSet
if registry.has_witness_set("corp"):
    # Process WitnessSet
    pass
```

---

## Test Coverage

**Total: 25 tests across 6 test classes**

### Test Classes

1. **TestRegistryCreation** (2 tests)
   - Basic construction with Chain
   - Chain reference stored correctly

2. **TestGenesisWitnessSetExtraction** (5 tests) - **WIT-03 Runtime**
   - Extract WitnessSet from Genesis
   - Witnesses extracted correctly
   - Threshold extracted correctly
   - Namespace matches root namespace
   - Legacy Genesis returns None

3. **TestRegistryQueries** (8 tests)
   - get_witness_set for existing namespace
   - get_witness_set returns None for nonexistent
   - get_all_witness_sets returns dict
   - get_all_witness_sets includes Genesis WitnessSet
   - get_all_witness_sets empty for legacy Genesis
   - has_witness_set returns True/False correctly

4. **TestRegistryStateless** (2 tests)
   - Registry rebuilds on each query
   - No internal cache attribute

5. **TestRegistryWithEmptyChain** (3 tests)
   - Empty chain returns None
   - Empty chain get_all returns empty dict
   - Empty chain has_witness_set returns False

6. **TestRegistryIntegration** (5 tests)
   - WitnessSet usable after extraction (frozen, hashable)
   - Deterministic ordering (same witnesses = same WitnessSet)
   - Bootstrap mode (1-of-1)
   - Production mode (3-of-5)
   - Multiple queries return equivalent results

### Test Results

```
$ pytest tests/test_registry.py -v
============================== 25 passed in 0.12s ===============================

$ pytest tests/ -v
======================= 671 passed, 8 warnings in 0.81s ========================
```

**No regressions:** All 646 existing tests still pass.

---

## Requirements Satisfied

### WIT-03: Genesis WitnessSet Extraction ✓

**Requirement:** Runtime extraction of initial WitnessSet from Genesis

**Implementation:**
- `_build_registry()` calls `has_witness_set(genesis)`
- Calls `parse_genesis_witness_set(genesis)` to extract data
- Creates WitnessSet from extracted witnesses/threshold
- Returns None for legacy Genesis without WitnessSet

**Verification:**
```python
registry = WitnessRegistry(chain)
ws = registry.get_witness_set("corp")
# ws.namespace == "corp"
# ws.witnesses == ("alice", "bob", "charlie")
# ws.threshold == 2
```

### WIT-04 Foundation: WitnessSet Change Tracking (Partial) ✓

**Phase 2 Scope:** Foundation only
- `_build_registry()` structure supports extension
- Comment indicates future PolicyHead scanning
- Current: Genesis extraction only
- Future: Scan PolicyHead cells for WitnessSet changes

**Extension Point:**
```python
def _build_registry(self) -> Dict[str, WitnessSet]:
    # Current: Genesis extraction
    # Future: for cell in self.chain.find_by_type(CellType.POLICYHEAD):
    #             if is_witnessset_change(cell):
    #                 ws = extract_witnessset_from_policyhead(cell)
    #                 witness_sets[ws.namespace] = ws
```

---

## Deviations from Plan

**None** - Plan executed exactly as written.

All tasks completed:
1. ✓ Create WitnessRegistry stateless query layer
2. ✓ Export WitnessRegistry from package
3. ✓ Create comprehensive WitnessRegistry tests (25 tests, 6 classes)

---

## Decisions Made

### Decision 1: Stateless Registry Design

**Context:** How to ensure registry reflects current Chain state?

**Options:**
1. In-memory cache with invalidation
2. Stateless rebuild from Chain on each query

**Chosen:** Stateless rebuild

**Rationale:**
- Chain is already append-only (fast iteration)
- No cache invalidation complexity
- Always consistent with Chain state
- Simple mental model (Chain is source of truth)

**Trade-offs:**
- Rebuild cost on each query (acceptable: Genesis scan is O(1))
- Future: may need caching for large chains with many WitnessSet changes
- For now: only Genesis extraction, so rebuild is trivial

### Decision 2: TYPE_CHECKING for Chain Import

**Context:** registry.py needs Chain type hint, but importing causes circular dependency

**Pattern:**
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .chain import Chain

class WitnessRegistry:
    def __init__(self, chain: 'Chain'):  # String annotation
        self.chain = chain
```

**Rationale:**
- Avoids circular import at runtime
- Provides type hints for IDE/type checkers
- Standard Python pattern for circular type hints

### Decision 3: Extension Point for WIT-04

**Context:** WIT-04 (WitnessSet changes) is future phase

**Approach:** Add comment in `_build_registry()` indicating extension point

**Rationale:**
- Documents future enhancement clearly
- Keeps current implementation minimal (YAGNI)
- Structure supports extension without refactoring

---

## Integration Points

### Imports WitnessRegistry Uses

**From witnessset.py:**
- `WitnessSet` - Result type

**From genesis.py:**
- `parse_genesis_witness_set` - Extract WitnessSet data from Genesis
- `has_witness_set` - Check if Genesis has embedded WitnessSet

**From chain.py (TYPE_CHECKING):**
- `Chain` - Type hint for registry binding

### Exports to Package Root

**Added to `__init__.py`:**
```python
# WitnessRegistry (v1.5)
from .registry import WitnessRegistry

__all__ = [
    # ... existing exports ...
    'WitnessRegistry',
]
```

**Enables:**
```python
from decisiongraph import WitnessRegistry
```

---

## Next Phase Readiness

### Phase 2 Plan 03-04: Ready ✓

**WitnessRegistry complete** - Foundation for:
- Plan 03: WitnessSet query operations
- Plan 04: WitnessSet validation integration

### Phase 3 (Promotion Gate): Ready ✓

**WitnessRegistry provides:**
- Runtime lookup: "Which witnesses control namespace X?"
- Foundation for signature verification (Phase 3)
- Will be used by promotion gate to validate approvals

**Example future usage:**
```python
# Phase 3: Check if signature set meets threshold
registry = WitnessRegistry(chain)
ws = registry.get_witness_set(namespace)
if len(signatures) >= ws.threshold:
    # Promotion approved
```

### Blockers

**None.**

All dependencies satisfied:
- ✓ Genesis WitnessSet embedding (01-03)
- ✓ WitnessSet dataclass (02-01)

---

## Performance Notes

**Execution Time:** 2.5 minutes (150 seconds)
- Task 1: Create registry.py (60s)
- Task 2: Export from __init__.py (10s)
- Task 3: Create tests (80s)

**Test Performance:**
- 25 registry tests: 0.12s
- 671 total tests: 0.81s

**Stateless Design Impact:**
- Current: Genesis scan is O(1) (always first cell)
- Future: WitnessSet changes scan is O(N) where N = PolicyHead cells
- Acceptable for Phase 2 scope

**Optimization Opportunities:**
- Add caching when WitnessSet changes become common
- Index PolicyHead cells by namespace for faster lookup
- Not needed yet (YAGNI principle)

---

## Code Quality

### Module Structure

**registry.py:**
- 248 lines
- Comprehensive docstrings (module, class, methods)
- Usage examples in docstrings
- Clear extension points documented
- TYPE_CHECKING pattern for circular imports

**test_registry.py:**
- 339 lines
- 6 test classes, 25 tests
- Fixtures for common setups
- Integration tests verify determinism
- Edge cases (empty chain, legacy Genesis)

### Documentation Quality

**Module docstring includes:**
- Purpose and design principles
- Usage example
- Extension point for WIT-04
- Stateless design rationale

**Method docstrings include:**
- Current implementation behavior
- Future extensions (WIT-04)
- Parameter descriptions
- Return types
- Usage examples

---

## Risks and Mitigations

### Risk 1: Performance with Many WitnessSet Changes

**Risk:** Stateless rebuild may be slow when WitnessSet changes frequently

**Mitigation:**
- Not a concern for Phase 2 (Genesis only)
- WIT-04 will add caching if needed
- Chain iteration is already optimized

**Status:** Deferred to WIT-04

### Risk 2: Circular Import Registry ↔ Chain

**Risk:** registry.py needs Chain type, chain.py might need registry

**Mitigation:**
- Used TYPE_CHECKING pattern (runtime import avoided)
- Chain does NOT import registry (clean separation)
- Registry only imports Chain for type hints

**Status:** Resolved

---

## Lessons Learned

### What Went Well

1. **Stateless design simplicity**
   - No cache invalidation complexity
   - Clear mental model (Chain is source of truth)
   - Easy to test (deterministic)

2. **TYPE_CHECKING pattern**
   - Avoided circular import cleanly
   - Provides type safety for IDEs
   - Standard Python pattern

3. **Extension point documentation**
   - Future WIT-04 work clearly marked
   - No premature implementation
   - Structure supports extension

### What Could Be Improved

1. **Performance measurement**
   - Could add benchmarks for rebuild time
   - Not critical yet (Genesis-only is trivial)
   - Defer to WIT-04 when scanning PolicyHead cells

2. **Caching strategy**
   - No caching implemented (YAGNI)
   - May need LRU cache for future
   - Monitor performance in Phase 3-4

---

## Files Changed

### Created

**src/decisiongraph/registry.py** (248 lines)
- WitnessRegistry class
- Stateless query layer
- Genesis WitnessSet extraction
- Extension point for WIT-04

**tests/test_registry.py** (339 lines)
- 6 test classes
- 25 tests
- Fixtures for common setups
- Integration tests

### Modified

**src/decisiongraph/__init__.py** (+5 lines)
- Import WitnessRegistry
- Add to __all__ list

---

## Git History

```
2458e02 test(02-02): add comprehensive WitnessRegistry tests
e8cc24d feat(02-02): export WitnessRegistry from package
2e033de feat(02-02): create WitnessRegistry stateless query layer
```

**Commits:** 3
**Atomic:** Yes (one commit per task)
**Revertable:** Yes (each task independently revertable)

---

## Verification Checklist

- [x] WitnessRegistry class exists in src/decisiongraph/registry.py
- [x] Registry extracts WitnessSet from Genesis (WIT-03 runtime)
- [x] Registry returns None for namespace without WitnessSet
- [x] Registry is stateless (rebuilds from Chain each query)
- [x] WitnessRegistry exported from package root
- [x] All 25 registry tests pass
- [x] No regressions (671 total tests pass)
- [x] WIT-03 complete
- [x] WIT-04 foundation in place

---

**Status:** ✅ COMPLETE

**Next:** Phase 2 Plan 03 (WitnessSet query operations)
