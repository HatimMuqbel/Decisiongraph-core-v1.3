---
phase: 08-simulation-core
plan: 01
subsystem: oracle-layer
tags: [simulation, context-manager, cleanup, shadow-chain, scholar]
requires:
  - 07-01 (Shadow cell creation)
  - 07-02 (OverlayContext and fork_shadow_chain)
provides:
  - simulation-context-manager
  - simulation-result-dataclass
  - shadow-chain-lifecycle
  - guaranteed-cleanup-pattern
affects:
  - 08-02 (Simulation engine orchestration)
  - 09-01 (Delta report generation)
  - 10-01 (Counterfactual anchors)
tech-stack:
  added: []
  patterns:
    - Context manager pattern (__enter__/__exit__)
    - Frozen dataclass for immutable results
    - Resource cleanup guarantee (even on exception)
    - Shadow cell injection before scholar creation
key-files:
  created:
    - src/decisiongraph/simulation.py
  modified:
    - src/decisiongraph/__init__.py
decisions:
  - decision: Shadow cells appended BEFORE scholar creation (in __enter__)
    rationale: Scholar queries the chain it's given - by appending shadow cells first, Scholar sees them during query execution
    alternatives: [Scholar-aware overlay, Runtime cell merging, Query-time injection]
    impact: Scholar sees base + shadow cells without modification to Scholar code
  - decision: Context manager pattern for resource cleanup
    rationale: Guarantees shadow_chain and shadow_scholar cleanup even on exception
    alternatives: [Manual cleanup, try/finally, Cleanup callback]
    impact: Impossible to leak shadow resources, automatic cleanup on with block exit
  - decision: Frozen dataclass for SimulationResult
    rationale: Immutable results prevent accidental modification, type-level enforcement
    alternatives: [Regular dataclass, Dict, Named tuple]
    impact: Simulation results immutable by design, no runtime checks needed
metrics:
  duration: 2 minutes
  tests:
    added: 0 (manual verification only - integration tests in 08-02)
    passing: 795
    failing: 0
  files:
    created: 1
    modified: 1
  commits: 1
  completed: 2026-01-28
---

# Phase 08 Plan 01: SimulationContext and SimulationResult Summary

**One-liner:** Context manager for safe simulation with shadow chain forking, shadow cell injection, and guaranteed cleanup.

## What Was Built

### Core Infrastructure

**simulation.py module** (251 lines)
- `SimulationContext` - Context manager implementing __enter__/__exit__ protocol
- `__init__()` - Store base_chain, overlay_context, temporal coordinates, initialize shadow resources to None
- `__enter__()` - Fork shadow chain, append all shadow cells from OverlayContext, create shadow_scholar, return self
- `__exit__()` - Set shadow_chain and shadow_scholar to None (cleanup), return False (propagate exceptions)
- `SimulationResult` - Frozen dataclass with simulation_id, rfa_dict, simulation_spec, base_result, shadow_result, temporal coordinates
- `to_dict()` - Convert SimulationResult to serializable dictionary

**Key pattern:** Context manager ensures shadow resources are always cleaned up (even on exception). Shadow cells appended to shadow_chain BEFORE creating shadow_scholar ensures Scholar sees them during query.

### Integration

**Package exports** (src/decisiongraph/__init__.py)
- Added simulation module imports
- Exported SimulationContext and SimulationResult
- Functions available via `from decisiongraph import SimulationContext, SimulationResult`

## How It Works

### SimulationContext Lifecycle

1. **Initialization** (`__init__`)
   - Store base_chain, overlay_context, temporal coordinates
   - Initialize shadow_chain = None, shadow_scholar = None

2. **Enter Context** (`__enter__`)
   - Step 1: `shadow_chain = fork_shadow_chain(base_chain)` - Structural isolation
   - Step 2: Append shadow cells from OverlayContext:
     - Iterate over shadow_facts.values(), append each cell
     - Iterate over shadow_rules.values(), append each cell
     - Iterate over shadow_policy_heads.values(), append each cell
     - Iterate over shadow_bridges.values(), append each cell
   - Step 3: `shadow_scholar = create_scholar(shadow_chain)` - AFTER shadow cells appended
   - Return self

3. **Simulation Execution** (with block body)
   - User code accesses sim.shadow_chain and sim.shadow_scholar
   - Scholar queries shadow_chain (sees base + shadow cells)

4. **Exit Context** (`__exit__`)
   - Set shadow_chain = None
   - Set shadow_scholar = None
   - Return False (propagate exceptions)

### Why Order Matters (SIM-03)

**Shadow cells MUST be appended BEFORE creating shadow_scholar:**
- Scholar queries the chain it's given at creation time
- By appending shadow cells to shadow_chain first, the Scholar's query methods will see shadow cells
- Shadow cells are valid DecisionCells (no special marking needed)
- No changes needed to Scholar code (works with any Chain)

### SimulationResult Immutability

**Frozen dataclass ensures:**
- Results cannot be modified after creation
- Modification attempts raise FrozenInstanceError
- Type-level enforcement (no runtime checks)
- to_dict() for serialization to JSON/storage

## Deviations from Plan

None - plan executed exactly as written.

## Learnings

### Technical Insights

1. **Context manager cleanup is GUARANTEED** - Even if exception raised during simulation, __exit__ ALWAYS runs. This prevents shadow resource leaks.

2. **Shadow cell injection before Scholar creation** - Scholar code unchanged. By appending shadow cells to the chain before creating Scholar, the Scholar naturally sees shadow cells during query execution.

3. **Frozen dataclass immutability** - SimulationResult frozen=True prevents field reassignment at type level. No runtime validation needed.

### Design Validation

- Context manager pattern perfect fit for resource lifecycle management
- fork_shadow_chain() from Phase 7 provides structural isolation
- OverlayContext from Phase 7 provides organized shadow cell access
- Scholar code requires zero modifications (just uses different Chain instance)

## Next Phase Readiness

### Unblocks

- **08-02 (Simulation Engine)** - Can now use SimulationContext to orchestrate simulations safely
- **09-01 (Delta Reports)** - Can access base_result and shadow_result from SimulationResult
- **10-01 (Counterfactual Anchors)** - Can run simulations with guaranteed cleanup

### Provides

- SimulationContext context manager (safe simulation lifecycle)
- SimulationResult frozen dataclass (immutable results)
- Shadow chain lifecycle management (fork → populate → cleanup)
- Guaranteed cleanup pattern (even on exception)

### Dependencies for Next Phase

Phase 08-02 (Simulation Engine) needs:
- run_simulation() function that orchestrates SimulationContext
- Query execution against base and shadow scholars
- Delta computation (base vs shadow results)
- Proof bundle extraction and comparison

No blockers - SimulationContext and SimulationResult complete and ready.

## Files Modified

### Created

1. **src/decisiongraph/simulation.py**
   - Lines: 251
   - Classes: SimulationContext, SimulationResult
   - Methods: __init__, __enter__, __exit__, at_valid_time (property), as_of_system_time (property), to_dict
   - Exports: SimulationContext, SimulationResult

### Modified

1. **src/decisiongraph/__init__.py**
   - Added: simulation module imports (4 lines)
   - Added: simulation class exports to __all__ (1 line)

## Test Results

### Summary
- Tests added: 0 (integration tests deferred to 08-02)
- Total tests: 795 (unchanged)
- Passing: 795
- Failing: 0
- Warnings: 8 (pre-existing, not related to simulation module)
- Duration: 1.09s

### Verification
- Manual verification performed:
  - Module imports work (from decisiongraph.simulation import ...)
  - Package exports work (from decisiongraph import SimulationContext, SimulationResult)
  - Context manager protocol works (__enter__ creates resources, __exit__ cleans up)
  - Shadow cells appended to shadow_chain correctly
  - SimulationResult frozen (modification raises FrozenInstanceError)
  - to_dict() method works

### Regression Testing
All 795 existing tests pass - no regressions from simulation module addition.

## Commits

1. **305c987** - feat(08-01): implement SimulationContext and SimulationResult
   - Created simulation.py with SimulationContext context manager
   - Implemented __enter__ (fork, append shadow cells, create scholar)
   - Implemented __exit__ (cleanup shadow resources)
   - Created SimulationResult frozen dataclass with to_dict()
   - Exported from decisiongraph package

## Verification

### Must-Haves Delivered

**Truths:**
- ✅ SimulationContext can be used as context manager (with statement)
- ✅ SimulationContext creates shadow chain from base chain on enter
- ✅ SimulationContext appends shadow cells from OverlayContext to shadow chain
- ✅ SimulationContext cleans up shadow chain on exit (even on exception)
- ✅ SimulationResult is immutable (frozen dataclass)
- ✅ SimulationResult contains base_result, shadow_result, and coordinates

**Artifacts:**
- ✅ src/decisiongraph/simulation.py exists (251 lines, 100+ line requirement met)
- ✅ Exports: SimulationContext, SimulationResult

**Key Links:**
- ✅ simulation.py imports fork_shadow_chain from shadow.py (line 28)
- ✅ simulation.py imports create_scholar from scholar.py (line 29)
- ✅ SimulationContext.__enter__ appends shadow cells to shadow_chain (lines 129-144)
- ✅ shadow_chain.append() called for each shadow cell type

### Success Criteria

- ✅ src/decisiongraph/simulation.py created with SimulationContext and SimulationResult
- ✅ SimulationContext implements __enter__ and __exit__ correctly
- ✅ SimulationContext creates shadow chain on enter
- ✅ SimulationContext appends shadow cells from OverlayContext to shadow_chain in __enter__
- ✅ SimulationContext creates shadow_scholar AFTER shadow cells appended
- ✅ SimulationContext cleans up on exit
- ✅ SimulationResult is frozen dataclass with all required fields
- ✅ SimulationResult has to_dict() method
- ✅ Both classes exported from decisiongraph package
- ✅ All 795 existing tests still pass (no regressions)

## Architectural Notes

### Design Patterns Used

1. **Context Manager Pattern**
   - Pattern: __enter__/__exit__ protocol
   - Benefit: Automatic resource cleanup, guaranteed even on exception
   - Source: Python standard pattern (with statement)

2. **Frozen Dataclass Immutability**
   - Pattern: dataclasses with frozen=True
   - Benefit: Type-level immutability enforcement, no runtime checks
   - Source: Existing DecisionGraph cell.py architecture

3. **Structural Isolation via Fork**
   - Pattern: fork_shadow_chain creates separate Chain instance
   - Benefit: Impossible to contaminate base chain (different objects)
   - Source: Phase 7 contamination prevention design

### Integration Points

**Upstream dependencies:**
- shadow.py (fork_shadow_chain, OverlayContext)
- scholar.py (create_scholar, Scholar)
- chain.py (Chain)

**Downstream consumers (future phases):**
- 08-02: Simulation engine orchestration
- 09-01: Delta report generation
- 10-01: Counterfactual anchor creation
- 11-01: Batch backtest execution

### Performance Characteristics

- **Memory:** Shadow chain shares cell references (memory-efficient)
- **CPU:** Scholar creation overhead per simulation run (one-time)
- **Cleanup:** O(1) - just sets references to None (garbage collection handles rest)
- **Scalability:** No resource leaks due to guaranteed cleanup

### Security Considerations

- Shadow resources automatically cleaned up (no resource leaks)
- Exception propagation preserved (return False in __exit__)
- Shadow chain isolated from base chain (structural isolation)
- No new attack surface - uses existing Chain/Scholar validation

## Documentation

### User-Facing

Classes documented with:
- Purpose and use case (safe simulation with cleanup)
- Usage pattern (with statement)
- Attribute descriptions with types
- Example code snippets
- Why order matters (SIM-03 explanation)

### Developer-Facing

Module docstring explains:
- SimulationContext and SimulationResult purpose
- Context manager lifecycle (fork → populate → query → cleanup)
- Why shadow cells appended before Scholar creation
- Cleanup guarantee (even on exception)

### Examples in Module

simulation.py includes:
- Docstring example showing full simulation pattern
- Comments explaining critical ordering (shadow cells before Scholar)
- Property accessors for temporal coordinates

## Known Limitations

None identified. SimulationContext and SimulationResult are complete as designed.

## Future Enhancements

Potential improvements for future phases (not blockers):

1. **Exception context preservation** - Should __exit__ capture exc_info for logging? Defer to Phase 8 simulation engine.

2. **Nested simulation support** - Can simulations be nested? Not a current requirement, but structurally possible (each has own shadow_chain).

3. **Simulation result caching** - Should SimulationResult support serialization to disk for later retrieval? Defer to Phase 11 (batch backtest).

## Phase Completion

**Status:** ✅ Complete

**Date:** 2026-01-28

**Duration:** 2 minutes

**Quality:** All tests pass, no regressions, must-haves delivered

**Ready for:** Phase 08-02 (Simulation Engine Orchestration)
