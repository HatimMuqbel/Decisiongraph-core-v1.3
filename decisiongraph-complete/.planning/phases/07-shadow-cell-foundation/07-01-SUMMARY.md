---
phase: 07-shadow-cell-foundation
plan: 01
subsystem: oracle-layer
tags: [shadow-cells, dataclasses, immutability, simulation, oracle]
requires:
  - 01-policyhead-foundation
  - 02-witnessset-registry
  - frozen-dataclass-infrastructure
provides:
  - shadow-cell-creation-api
  - immutable-variant-pattern
  - content-based-hashing
  - zero-dependency-replace
affects:
  - 07-02 (Overlay context construction)
  - 08-01 (Simulation engine orchestration)
  - 09-01 (Delta report generation)
tech-stack:
  added: []
  patterns:
    - dataclasses.replace() for frozen dataclass field replacement
    - Nested replace() for modifying fields in nested dataclasses
    - __post_init__ automatic cell_id recomputation
    - Convenience functions for common shadow patterns
key-files:
  created:
    - src/decisiongraph/shadow.py
    - tests/test_shadow_cells.py
  modified:
    - src/decisiongraph/__init__.py
decisions:
  - decision: Use dataclasses.replace() for shadow cell creation
    rationale: Zero new dependencies, standard library pattern, automatically calls __post_init__ for cell_id recomputation
    alternatives: [Custom copy logic, Pyrsistent immutable structures, Manual field copying]
    impact: Shadow cells guaranteed to have correct cell_id via __post_init__ mechanism
  - decision: cell_id excluded from replace() (init=False)
    rationale: cell_id is computed, not assigned - must be recomputed after any content change
    alternatives: [Manual cell_id computation, Allow cell_id override]
    impact: Shadow cells automatically get distinct cell_id when content changes, no manual hashing needed
  - decision: Confidence not part of cell_id computation
    rationale: Existing DecisionGraph design - cell_id based on fact object, not confidence metadata
    alternatives: [Include all fact fields in cell_id]
    impact: Confidence changes alone don't create new cell_id (by design)
metrics:
  duration: 3.5 minutes
  tests:
    added: 18
    passing: 786
    failing: 0
  files:
    created: 2
    modified: 1
  commits: 3
  completed: 2026-01-28
---

# Phase 07 Plan 01: Shadow Cell Creation Summary

**One-liner:** Implement shadow cell creation using dataclasses.replace() with automatic cell_id recomputation via __post_init__.

## What Was Built

### Core Infrastructure

**shadow.py module** (298 lines)
- `create_shadow_cell()` - Core function using dataclasses.replace() with optional fact/header/logic_anchor replacement
- `create_shadow_fact()` - Convenience function for modifying fact fields (object, confidence, valid_from, valid_to)
- `create_shadow_rule()` - Convenience function for modifying rule_logic_hash
- `create_shadow_policy_head()` - Convenience function for modifying promoted_rule_ids with automatic policy_hash recomputation
- `create_shadow_bridge()` - Convenience function for modifying bridge target namespace
- `_replace_fact_fields()` - Helper for nested Fact field replacement with None filtering

**Key pattern:** Shadow cells leverage frozen dataclass architecture - replace() creates new instance, __post_init__ recomputes cell_id automatically.

### Test Coverage

**test_shadow_cells.py** (505 lines, 18 tests)
- Core shadow cell behavior: distinct cell_id, base unchanged, integrity verification
- Convenience functions: fact, rule, policy head, bridge
- Edge cases: no modifications (same cell_id), evidence/proof preservation, multiple shadows from same base
- Multi-field modifications: object + confidence + valid_from simultaneously

**Test fixtures:**
- `create_base_fact_cell()` - Standard fact cell for testing
- `create_base_rule_cell()` - Rule cell with logic hash
- `create_base_policy_head()` - PolicyHead with promoted rules
- `create_base_bridge_cell()` - Bridge cell with target namespace

### Integration

**Package exports** (src/decisiongraph/__init__.py)
- Added shadow module imports
- Exported all 5 shadow creation functions
- Functions available via `from decisiongraph import create_shadow_cell, create_shadow_fact`

## How It Works

### Shadow Cell Creation Flow

1. **User calls convenience function** (e.g., `create_shadow_fact(base, object="90000")`)
2. **Helper creates new Fact** via `replace(base.fact, object="90000")`
3. **Core function creates new DecisionCell** via `replace(base_cell, fact=new_fact)`
4. **__post_init__ automatically runs**, calling `compute_cell_id()`
5. **cell_id recomputed** based on new content (SHA-256 hash)
6. **Shadow cell returned** with distinct cell_id

### Key Insight

cell_id field is `init=False`, so it's excluded from replace() arguments and automatically recomputed. This guarantees shadow cells have correct hashes without manual computation.

### Nested Field Replacement Pattern

For modifying nested dataclass fields:
```python
# Wrong: replace(base_cell, fact.object="90000")  # Syntax error

# Right: Nested replace()
new_fact = replace(base_cell.fact, object="90000")
shadow = replace(base_cell, fact=new_fact)

# Or inline:
shadow = replace(base_cell, fact=replace(base_cell.fact, object="90000"))
```

## Deviations from Plan

None - plan executed exactly as written.

## Learnings

### Technical Insights

1. **cell_id computation excludes confidence** - By design, only fact.object (not confidence) affects cell_id. This is intentional DecisionGraph behavior - confidence changes don't create new cells.

2. **Frozen dataclasses enforce immutability at type level** - No runtime checks needed, Python enforces at dataclass construction.

3. **replace() automatically calls __post_init__** - This is the key pattern that makes shadow cells work - no manual hash computation needed.

### Design Validation

- Zero new dependencies confirmed - dataclasses.replace() sufficient for all shadow cell patterns
- Frozen dataclass architecture from v1.3 perfectly supports shadow cells
- No changes needed to existing cell.py, chain.py, scholar.py code

## Next Phase Readiness

### Unblocks

- **07-02 (Overlay Context)** - Can now construct OverlayContext with shadow cells created via these functions
- **08-01 (Simulation Engine)** - Can inject shadow cells into shadow chain
- **09-01 (Delta Reports)** - Can compare base vs shadow cells via cell_id

### Provides

- Shadow cell creation API (5 functions)
- Immutable variant pattern (replace + __post_init__)
- Content-based hashing (automatic via cell_id)
- Zero-dependency solution (stdlib only)

### Dependencies for Next Phase

Phase 07-02 (Overlay Context) needs:
- OverlayContext dataclass definition
- Shadow cell indexing by (namespace, subject, predicate)
- Precedence rules (shadow overrides base for same fact key)
- Context construction from shadow cell list

No blockers - shadow cell creation complete and tested.

## Files Modified

### Created

1. **src/decisiongraph/shadow.py**
   - Lines: 298
   - Functions: 5 public + 1 helper
   - Exports: create_shadow_cell, create_shadow_fact, create_shadow_rule, create_shadow_policy_head, create_shadow_bridge

2. **tests/test_shadow_cells.py**
   - Lines: 505
   - Tests: 18
   - Fixtures: 4 (base_fact_cell, base_rule_cell, base_policy_head, base_bridge_cell)

### Modified

1. **src/decisiongraph/__init__.py**
   - Added: shadow module imports (7 lines)
   - Added: shadow function exports to __all__ (3 lines)

## Test Results

### Summary
- Tests added: 18
- Total tests: 786 (753 existing + 18 new shadow + 15 other)
- Passing: 786
- Failing: 0
- Warnings: 8 (pre-existing, not related to shadow cells)
- Duration: 1.24s

### Coverage
- Shadow cell distinct cell_id: Covered
- Base cell immutability: Covered
- Shadow cell integrity verification: Covered
- Convenience functions: Covered (fact, rule, policy, bridge)
- Edge cases: Covered (no-change, evidence/proof preservation, multiple shadows)
- Multi-field modifications: Covered

### Regression Testing
All 753 existing tests pass - no regressions from shadow cell addition.

## Commits

1. **dc4202f** - feat(07-01): implement shadow cell creation functions
   - Created shadow.py with 5 creation functions
   - Nested replace() for fact field modification
   - Automatic cell_id recomputation via __post_init__

2. **6820e96** - test(07-01): add comprehensive shadow cell tests
   - 18 tests covering creation, immutability, integrity
   - Test fixtures for fact, rule, policy, bridge cells
   - Edge case coverage (no-change, preservation, multiple shadows)

3. **92e1ca9** - feat(07-01): export shadow cell functions from decisiongraph package
   - Updated __init__.py with shadow module imports
   - Added functions to __all__ export list
   - Verified 786 tests pass with no regressions

## Verification

### Must-Haves Delivered

**Truths:**
- ✅ User can create shadow variant of any DecisionCell using create_shadow_cell()
- ✅ Shadow cells have distinct cell_id from base cells (content changed = different hash)
- ✅ Base cell remains unchanged after creating shadow variant (immutability preserved)
- ✅ Shadow cells are valid DecisionCells passing verify_integrity()

**Artifacts:**
- ✅ src/decisiongraph/shadow.py exists (298 lines, 80+ line requirement met)
- ✅ Exports: create_shadow_cell, create_shadow_fact, create_shadow_rule, create_shadow_policy_head, create_shadow_bridge
- ✅ tests/test_shadow_cells.py exists (505 lines, 100+ line requirement met)
- ✅ Contains test_shadow_cell_distinct_id test

**Key Links:**
- ✅ shadow.py imports dataclasses.replace (line 28)
- ✅ shadow.py imports DecisionCell from cell.py (line 31-36)

### Success Criteria

- ✅ src/decisiongraph/shadow.py exists with create_shadow_cell and convenience functions
- ✅ Shadow cells have distinct cell_id when content changes
- ✅ Base cells remain unchanged (immutability verified)
- ✅ Shadow cells pass verify_integrity()
- ✅ All 753 existing tests pass (no regressions)
- ✅ New shadow cell tests pass (18/18)
- ✅ Functions exported from decisiongraph package

## Architectural Notes

### Design Patterns Used

1. **Frozen Dataclass Immutability**
   - Pattern: dataclasses with frozen=True
   - Benefit: Type-level immutability enforcement, no runtime checks
   - Source: Existing DecisionGraph cell.py architecture

2. **Computed Field Pattern**
   - Pattern: field(init=False) + __post_init__ for derived values
   - Benefit: cell_id automatically recomputed, impossible to get out of sync
   - Source: Existing DecisionCell.cell_id implementation

3. **Convenience Function Facade**
   - Pattern: Specialized functions calling core function with specific patterns
   - Benefit: API clarity (create_shadow_fact vs generic create_shadow_cell)
   - Source: Standard Python API design

### Integration Points

**Upstream dependencies:**
- cell.py (DecisionCell, Fact, Header, LogicAnchor, compute_policy_hash)
- Python 3.10+ dataclasses.replace()

**Downstream consumers (future phases):**
- 07-02: OverlayContext construction
- 08-01: Oracle simulation engine
- 09-01: Delta report generation
- 10-01: Counterfactual anchor creation

### Performance Characteristics

- **Memory:** Shallow copy of cell data (frozen dataclasses share immutable references)
- **CPU:** SHA-256 hash recomputation per shadow cell (deterministic, fast)
- **Scalability:** O(1) per shadow cell creation, no indexing overhead at creation time

### Security Considerations

- Shadow cells inherit security properties from base cells (frozen, tamper-evident)
- cell_id recomputation prevents hash collision attacks
- No new attack surface - uses existing DecisionCell validation

## Documentation

### User-Facing

Functions documented with:
- Purpose and use case
- Parameter descriptions with types
- Return value specification
- Example code snippets
- Gotchas (e.g., nested replace() for nested fields)

### Developer-Facing

Module docstring explains:
- Shadow cell purpose (counterfactual simulation)
- Architecture (replace + __post_init__)
- Key properties (distinct cell_id, immutability, integrity)
- Integration pattern (separate Chain instances)

### Examples in Tests

test_shadow_cells.py serves as executable documentation:
- Fixture functions show cell creation patterns
- Test assertions demonstrate expected behavior
- Comments explain design decisions (e.g., confidence not in cell_id)

## Known Limitations

None identified. Shadow cell creation is complete as designed.

## Future Enhancements

Potential improvements for future phases (not blockers):

1. **Shadow cell signing** - Should shadow cells have empty proof or simulation-specific signatures? Defer to Phase 8.

2. **Batch shadow creation** - API for creating multiple shadow cells at once with shared timestamps? Evaluate in Phase 8 based on usage patterns.

3. **Shadow cell metadata** - Should shadow cells track their base cell_id? Not needed for correctness, but could aid debugging. Defer to Phase 9 (delta reports).

## Phase Completion

**Status:** ✅ Complete

**Date:** 2026-01-28

**Duration:** 3.5 minutes

**Quality:** All tests pass, no regressions, must-haves delivered

**Ready for:** Phase 07-02 (Overlay Context)
