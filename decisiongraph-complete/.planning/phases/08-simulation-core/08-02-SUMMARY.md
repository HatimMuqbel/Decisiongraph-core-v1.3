---
phase: 08-simulation-core
plan: 02
subsystem: oracle-layer
tags: [simulation, engine, rfa, overlay, contamination, bitemporal]
requires:
  - 08-01 (SimulationContext and SimulationResult)
  - 07-01 (Shadow cell creation)
  - 07-02 (OverlayContext and fork_shadow_chain)
provides:
  - simulation-entry-point
  - engine-simulate-rfa-method
  - overlay-context-builder
  - base-shadow-query-orchestration
affects:
  - 09-01 (Delta report generation)
  - 10-01 (Counterfactual anchors)
  - 11-01 (Batch backtest execution)
tech-stack:
  added: []
  patterns:
    - Entry point method pattern (simulate_rfa)
    - Builder pattern (_build_overlay_context)
    - Orchestration pattern (query base, build overlay, query shadow, package result)
    - Frozen coordinates pattern (bitemporal query consistency)
key-files:
  created:
    - tests/test_simulation.py
  modified:
    - src/decisiongraph/engine.py
decisions:
  - decision: simulate_rfa() orchestrates full simulation workflow
    rationale: Single method handles RFA validation, base query, overlay build, shadow query, result packaging
    alternatives: [Separate functions for each step, Simulation pipeline class, Fluent builder API]
    impact: Simple API - one method call for complete simulation
  - decision: _build_overlay_context() creates shadow cells from spec dict
    rationale: Converts user-friendly dict format to OverlayContext with proper shadow cells
    alternatives: [User builds OverlayContext directly, Factory class, JSON schema validation]
    impact: Flexible simulation spec format, graceful handling of missing cells
  - decision: Base and shadow queries use same frozen coordinates
    rationale: Ensures fair comparison - both queries see same temporal snapshot
    alternatives: [Different coordinates per query, Dynamic time advancement, Time range queries]
    impact: Bitemporal consistency guaranteed (SHD-05)
metrics:
  duration: 6 minutes
  tests:
    added: 19
    passing: 814 (795 existing + 19 new)
    failing: 0
  files:
    created: 1
    modified: 1
  commits: 2
  completed: 2026-01-28
---

# Phase 08 Plan 02: Simulation Engine Orchestration Summary

**One-liner:** Engine.simulate_rfa() method orchestrates base query, shadow overlay, shadow query, and result packaging with zero contamination.

## What Was Built

### Engine.simulate_rfa() Method

**src/decisiongraph/engine.py** (191 lines added)
- `simulate_rfa()` - User-facing entry point for simulation
  - Step 1: Canonicalize RFA using existing _canonicalize_rfa()
  - Step 2: Validate RFA schema and fields using existing validators
  - Step 3: Query base reality at frozen coordinates (base Scholar)
  - Step 4: Build OverlayContext from simulation_spec
  - Step 5: Run shadow query in SimulationContext (shadow Scholar)
  - Step 6: Return immutable SimulationResult

- `_build_overlay_context()` - Helper to convert simulation_spec to OverlayContext
  - Process shadow_facts list → call create_shadow_fact() for each
  - Process shadow_rules list → call create_shadow_rule() for each
  - Process shadow_policy_heads list → call create_shadow_policy_head() for each
  - Process shadow_bridges list → call create_shadow_bridge() for each
  - Gracefully handle nonexistent base_cell_id (skip silently)

**Imports added:**
- SimulationContext, SimulationResult from .simulation
- OverlayContext, create_shadow_* functions from .shadow

### Comprehensive Tests

**tests/test_simulation.py** (606 lines)
- 19 tests covering all Phase 8 requirements
- 5 test classes with full coverage
- Test fixtures for chain creation with rule and facts

**Test Coverage:**
1. **SIM-01: engine.simulate_rfa() entry point** (3 tests)
   - Returns SimulationResult with correct type and metadata
   - Empty spec returns identical base/shadow results
   - Validates RFA schema (missing fields raise SchemaInvalidError)

2. **SIM-02: Base reality frozen at coordinates** (2 tests)
   - Base query uses specified at_valid_time
   - Base query uses specified as_of_system_time

3. **SIM-03: Shadow overlay deterministic precedence** (2 tests)
   - Shadow fact override behavior
   - Shadow cells visible in shadow_chain

4. **SHD-05: Bitemporal simulation respects coordinates** (2 tests)
   - Coordinates passed to SimulationResult
   - Base and shadow queries use same frozen coordinates

5. **Zero Contamination** (2 tests)
   - Base chain length unchanged after simulation
   - Base chain head unchanged after simulation

6. **SimulationContext** (4 tests)
   - Context manager creates shadow chain on enter
   - Context manager cleans up on exit
   - Context manager cleans up on exception
   - Shadow cells appended to shadow_chain

7. **SimulationResult** (2 tests)
   - Result is frozen (modification raises exception)
   - to_dict() returns serializable dict

8. **Edge Cases** (2 tests)
   - Gracefully handles nonexistent base_cell_id
   - Handles empty simulation_spec keys

## How It Works

### simulate_rfa() Workflow

```python
result = engine.simulate_rfa(
    rfa_dict={"namespace": "corp", "requester_namespace": "corp", "requester_id": "analyst"},
    simulation_spec={"shadow_facts": [{"base_cell_id": "abc123...", "object": "90000"}]},
    at_valid_time="2025-01-15T00:00:00Z",
    as_of_system_time="2025-01-15T00:00:00Z"
)
```

**Step-by-step execution:**

1. **Canonicalize RFA** - Sort keys, strip whitespace, remove None values
2. **Validate RFA** - Check schema and field formats (reuse existing validators)
3. **Query base reality** - Use base Scholar with frozen coordinates → base_result
4. **Build OverlayContext** - Convert simulation_spec dict to OverlayContext with shadow cells
5. **Enter SimulationContext** - Fork shadow chain, append shadow cells, create shadow Scholar
6. **Query shadow reality** - Use shadow Scholar with same frozen coordinates → shadow_result
7. **Exit SimulationContext** - Cleanup shadow resources (shadow_chain, shadow_scholar set to None)
8. **Package result** - Create immutable SimulationResult with both results and metadata

### _build_overlay_context() Process

**Input:** simulation_spec dict
```python
{
    "shadow_facts": [{"base_cell_id": "abc123", "object": "new_value"}],
    "shadow_rules": [{"base_cell_id": "def456", "rule_logic_hash": "hash789"}],
    ...
}
```

**Processing:**
- For each shadow_facts entry:
  - Get base_cell from chain
  - Call create_shadow_fact(base_cell, **modifications)
  - Add to OverlayContext via ctx.add_shadow_fact()
- Repeat for shadow_rules, shadow_policy_heads, shadow_bridges
- Skip silently if base_cell_id not found (graceful degradation)

**Output:** Populated OverlayContext ready for SimulationContext

### Frozen Coordinates Pattern

**Both queries use identical temporal coordinates:**
- at_valid_time: Valid time coordinate (when facts are true)
- as_of_system_time: System time coordinate (when facts were recorded)

**Why this matters (SHD-05):**
- Fair comparison: Both queries see same temporal snapshot
- No temporal drift between base and shadow queries
- Bitemporal consistency guaranteed

## Deviations from Plan

None - plan executed exactly as written. All must-haves delivered.

## Learnings

### Technical Insights

1. **Zero contamination verification** - Base chain length and head remain unchanged after simulation. Structural isolation via fork_shadow_chain() prevents any possibility of contamination.

2. **Context manager cleanup** - SimulationContext.__exit__ ALWAYS runs, even on exception. Shadow resources guaranteed to be released.

3. **Graceful degradation** - _build_overlay_context() skips nonexistent base_cell_id entries silently. Simulation continues with available shadow cells.

4. **Test fixture complexity** - Creating DecisionCells directly requires careful attention to:
   - Graph ID must match chain.graph_id
   - System time must be >= previous cell system_time
   - Confidence 1.0 requires SourceQuality.VERIFIED
   - Header version, prev_cell_hash, all required fields

### Design Validation

- Single entry point (simulate_rfa) simplifies user API
- Reusing existing RFA validation (_canonicalize_rfa, _validate_rfa_schema, _validate_rfa_fields) ensures consistency
- SimulationContext from 08-01 handles all resource lifecycle
- OverlayContext from 07-02 organizes shadow cells cleanly

## Next Phase Readiness

### Unblocks

- **09-01 (Delta Report)** - Can call engine.simulate_rfa() and process result.base_result vs result.shadow_result
- **10-01 (Counterfactual Anchors)** - Can run simulations and analyze results for anchor creation
- **11-01 (Batch Backtest)** - Can orchestrate multiple simulate_rfa() calls

### Provides

- engine.simulate_rfa() method (complete simulation entry point)
- _build_overlay_context() helper (simulation_spec → OverlayContext)
- Base/shadow query orchestration (frozen coordinates)
- Zero contamination guarantee (verified in tests)

### Dependencies for Next Phase

Phase 09-01 (Delta Report) needs:
- Delta computation between base_result and shadow_result
- Diff generation for added/removed/changed facts
- Proof bundle comparison and validation
- Delta report serialization format

No blockers - Engine.simulate_rfa() complete and tested.

## Files Modified

### Created

1. **tests/test_simulation.py**
   - Lines: 606
   - Classes: 8 (7 test classes + fixtures)
   - Tests: 19
   - Coverage: SIM-01, SIM-02, SIM-03, SHD-05, zero contamination, edge cases

### Modified

1. **src/decisiongraph/engine.py**
   - Lines added: 191
   - Methods added: simulate_rfa(), _build_overlay_context()
   - Imports added: SimulationContext, SimulationResult, OverlayContext, create_shadow_*

## Test Results

### Summary
- Tests added: 19
- Total tests: 814 (795 existing + 19 new)
- Passing: 814
- Failing: 0
- Warnings: 8 (pre-existing, not related to simulation)
- Duration: 0.99s (all tests)

### Test Breakdown

**SIM-01 tests (3):**
- test_simulate_rfa_returns_simulation_result ✅
- test_simulate_rfa_with_empty_spec_returns_identical_results ✅
- test_simulate_rfa_validates_rfa_schema ✅

**SIM-02 tests (2):**
- test_base_result_uses_specified_valid_time ✅
- test_base_result_uses_specified_system_time ✅

**SIM-03 tests (2):**
- test_shadow_fact_overrides_base_fact ✅
- test_shadow_cells_visible_in_shadow_chain ✅

**SHD-05 tests (2):**
- test_simulation_coordinates_passed_to_result ✅
- test_both_queries_use_same_coordinates ✅

**Zero Contamination tests (2):**
- test_base_chain_length_unchanged ✅
- test_base_chain_head_unchanged ✅

**SimulationContext tests (4):**
- test_context_manager_creates_shadow_chain ✅
- test_context_manager_cleans_up_on_exit ✅
- test_context_manager_cleans_up_on_exception ✅
- test_context_manager_appends_shadow_cells ✅

**SimulationResult tests (2):**
- test_result_is_frozen ✅
- test_result_to_dict ✅

**Edge Case tests (2):**
- test_simulate_with_nonexistent_base_cell ✅
- test_simulate_with_empty_simulation_spec_keys ✅

### Regression Testing
All 795 existing tests pass - no regressions from engine.simulate_rfa() addition.

### Zero Contamination Verification
Manual verification script confirms:
- Base chain length unchanged after simulation
- Base chain head unchanged after simulation
- Shadow cells never appended to base chain

## Commits

1. **7259186** - feat(08-02): add Engine.simulate_rfa() method
   - Added simulate_rfa() to Engine class
   - Implemented 6-step workflow (canonicalize, validate, base query, build overlay, shadow query, package)
   - Added _build_overlay_context() helper
   - Imported simulation and shadow modules
   - Zero contamination guaranteed via SimulationContext

2. **06dfb08** - test(08-02): add comprehensive simulation tests
   - Created test_simulation.py with 19 tests
   - Covered SIM-01, SIM-02, SIM-03, SHD-05 requirements
   - Tested zero contamination guarantee
   - Tested SimulationContext and SimulationResult
   - Tested edge cases
   - All tests passing

## Verification

### Must-Haves Delivered

**Truths:**
- ✅ User can call engine.simulate_rfa() with RFA, simulation_spec, and bitemporal coordinates
- ✅ Base reality is queried at frozen coordinates before any shadow operations
- ✅ Shadow overlay injection uses OverlayContext with deterministic precedence
- ✅ Context manager ensures shadow chain cleanup after simulation
- ✅ SimulationResult contains both base_result and shadow_result

**Artifacts:**
- ✅ src/decisiongraph/engine.py provides Engine.simulate_rfa() method
- ✅ Contains "def simulate_rfa"
- ✅ tests/test_simulation.py created (606 lines, 200+ line requirement met)
- ✅ Contains "test_simulate_rfa"

**Key Links:**
- ✅ engine.py imports SimulationContext, SimulationResult from simulation module
- ✅ Pattern: "from \.simulation import" (line 20)
- ✅ engine.py imports OverlayContext from shadow module
- ✅ Pattern: "OverlayContext" used in _build_overlay_context

### Success Criteria

- ✅ Engine.simulate_rfa() method implemented with full functionality
- ✅ Method accepts RFA dict, simulation_spec, at_valid_time, as_of_system_time
- ✅ Method returns SimulationResult with base_result and shadow_result
- ✅ _build_overlay_context() helper method creates OverlayContext from spec
- ✅ tests/test_simulation.py created with comprehensive tests
- ✅ Tests cover SIM-01, SIM-02, SIM-03, SHD-05 requirements
- ✅ Zero contamination verified (base chain unchanged after simulation)
- ✅ Context manager cleanup verified
- ✅ Shadow cells appended to shadow_chain verified
- ✅ All simulation tests pass (19/19)
- ✅ All 814 tests pass (no regressions)

## Architectural Notes

### Design Patterns Used

1. **Entry Point Method**
   - Pattern: Single method exposes complete workflow
   - Benefit: Simple API, one call for full simulation
   - Source: Existing Engine.process_rfa() pattern

2. **Builder Pattern**
   - Pattern: _build_overlay_context() constructs OverlayContext from spec
   - Benefit: Flexible spec format, graceful degradation
   - Source: Standard builder pattern

3. **Orchestration Pattern**
   - Pattern: simulate_rfa() coordinates multiple subsystems (validation, query, simulation)
   - Benefit: Clear separation of concerns, reusable components
   - Source: Standard orchestration pattern

4. **Frozen Coordinates Pattern**
   - Pattern: Same at_valid_time and as_of_system_time for both queries
   - Benefit: Bitemporal consistency, fair comparison
   - Source: Requirement SHD-05

### Integration Points

**Upstream dependencies:**
- simulation.py (SimulationContext, SimulationResult) - from 08-01
- shadow.py (OverlayContext, create_shadow_*) - from 07-01, 07-02
- scholar.py (Scholar, query_facts) - existing
- engine.py validators (_canonicalize_rfa, _validate_rfa_schema, _validate_rfa_fields) - existing

**Downstream consumers (future phases):**
- 09-01: Delta report generation (processes SimulationResult)
- 10-01: Counterfactual anchors (runs simulations, analyzes results)
- 11-01: Batch backtest (orchestrates multiple simulate_rfa calls)

### Performance Characteristics

- **Memory:** Shadow chain shared cell references (memory-efficient fork)
- **CPU:** Two Scholar queries per simulation (base + shadow)
- **I/O:** None (all in-memory)
- **Scalability:** Linear with fact count, constant overhead per simulation

### Security Considerations

- RFA validation reuses existing validators (consistent security)
- Zero contamination verified (structural isolation)
- Shadow resources automatically cleaned up (no leaks)
- Exception propagation preserved (errors not suppressed)

## Documentation

### User-Facing

Engine.simulate_rfa() documented with:
- Purpose: "what-if" simulation entry point
- Args: RFA dict, simulation_spec format, temporal coordinates
- Returns: SimulationResult with base/shadow comparison
- Raises: Schema/input errors
- Example: Full simulation with shadow fact modification

### Developer-Facing

_build_overlay_context() documented with:
- Purpose: Convert simulation_spec dict to OverlayContext
- Args: simulation_spec structure
- Returns: Populated OverlayContext
- Process: Iterates shadow_facts/rules/policy_heads/bridges, creates shadow cells

### Examples in Module

engine.py includes:
- Full docstring example showing simulate_rfa() usage
- Comments explaining each step of workflow
- Edge case handling notes

## Known Limitations

None identified. Engine.simulate_rfa() is complete as designed.

## Future Enhancements

Potential improvements for future phases (not blockers):

1. **Simulation caching** - Cache SimulationResult for repeated queries with same spec. Defer to Phase 11 (batch backtest).

2. **Parallel shadow queries** - Run multiple simulations in parallel. Defer to Phase 11 (batch backtest).

3. **Simulation spec validation** - JSON schema for simulation_spec format. Defer to Phase 9 (when format stabilizes).

4. **Shadow cell conflict resolution** - Multiple shadow cells for same key. Defer to Phase 10 (counterfactual anchors).

## Phase Completion

**Status:** ✅ Complete

**Date:** 2026-01-28

**Duration:** 6 minutes

**Quality:** All tests pass, no regressions, must-haves delivered, zero contamination verified

**Ready for:** Phase 09 (Delta Report and Proof)
