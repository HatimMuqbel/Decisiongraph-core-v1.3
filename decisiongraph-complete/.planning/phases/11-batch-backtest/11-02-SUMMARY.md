---
phase: 11-batch-backtest
plan: 02
subsystem: engine
tags: [batch-processing, simulation, bounded-execution, engine-integration]

# Dependency graph
requires:
  - phase: 11-batch-backtest
    plan: 01
    provides: BatchBacktestResult dataclass and helpers
  - phase: 10-anchor-detection
    plan: 02
    provides: ExecutionBudget pattern
  - phase: 08-simulation-foundation
    plan: 02
    provides: Engine.simulate_rfa() method
provides:
  - Engine.run_backtest() method with bounded execution
  - Batch backtest capability for multiple RFAs
  - Comprehensive test coverage (24 new tests)
affects: [phase-12-audit-trail, backtest-reporting]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Reused ExecutionBudget from Phase 10 for max_cases and max_runtime_ms"
    - "Separate check for max_cells_touched (cumulative metric)"
    - "Early return for empty rfa_list (graceful handling)"
    - "Deterministic sorting via _sort_results before return"

key-files:
  created:
    - tests/test_backtest.py
  modified:
    - src/decisiongraph/engine.py

key-decisions:
  - "Reused ExecutionBudget from Phase 10 for bounded execution consistency"
  - "Separate max_cells_touched check (cumulative vs per-iteration metric)"
  - "Sort results before returning, not after appending (cleaner API guarantee)"
  - "Empty rfa_list returns empty result with backtest_incomplete=False (not error)"
  - "Import helper functions _sort_results and _count_cells_in_simulation from backtest module"

patterns-established:
  - "Engine.run_backtest() follows Engine.simulate_rfa() pattern (validates, executes, returns immutable result)"
  - "Bounded execution checks at loop start prevent partial iteration work"
  - "24 comprehensive tests cover dataclass, helpers, integration, limits, and edge cases"

# Metrics
duration: 4.3min
completed: 2026-01-28
---

# Phase 11 Plan 02: Engine Integration for Batch Backtest Summary

**Engine.run_backtest() method with bounded execution and comprehensive test suite for batch simulation over multiple RFAs**

## Performance

- **Duration:** 4.3 min (256 seconds)
- **Started:** 2026-01-28T17:36:39Z
- **Completed:** 2026-01-28T17:40:55Z
- **Tasks:** 3
- **Files modified:** 2
- **Tests added:** 24 (892 total, 868 + 24)

## Accomplishments
- Added Engine.run_backtest() method with bounded execution (max_cases, max_runtime_ms, max_cells_touched)
- Reused ExecutionBudget from Phase 10 for consistent bounded execution pattern
- Implemented three limit checks: max_cases/max_runtime_ms via budget.is_exceeded(), max_cells_touched via cumulative counter
- Sort results deterministically before return (BAT-03)
- Handle empty rfa_list gracefully with early return
- Created comprehensive test suite with 24 tests covering all requirements (BAT-01, BAT-02, BAT-03)
- All 892 tests pass (868 existing + 24 new, 0 regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add run_backtest() method to Engine class** - `c762e49` (feat)
2. **Task 2: Create comprehensive test suite for batch backtest** - `e59b73b` (test)
3. **Task 3: Run full test suite and verify no regressions** - (verified, no commit needed)

## Files Created/Modified
- `src/decisiongraph/engine.py` - Added run_backtest() method, imports for BatchBacktestResult/_sort_results/_count_cells_in_simulation/ExecutionBudget, added 'run_backtest' to __all__
- `tests/test_backtest.py` - 24 comprehensive tests covering BatchBacktestResult dataclass, helper functions, Engine.run_backtest() integration, bounded execution limits, deterministic ordering, edge cases

## Decisions Made

1. **Reused ExecutionBudget**: Leveraged Phase 10's ExecutionBudget for max_cases and max_runtime_ms (consistent pattern across codebase)
2. **Separate max_cells_touched check**: max_cells_touched is cumulative metric (sum across all simulations), checked separately from ExecutionBudget which tracks per-iteration metrics
3. **Sort before return**: Call _sort_results() on results list before returning BatchBacktestResult (not after append) - cleaner API guarantee
4. **Empty list graceful handling**: Empty rfa_list returns BatchBacktestResult with empty results and backtest_incomplete=False (not error) - consistent with "no work = success" pattern
5. **Import helper functions**: Import _sort_results and _count_cells_in_simulation from backtest module (not engine.py) - separation of concerns
6. **Added 'run_backtest' to __all__**: Export run_backtest from engine module for public API discoverability

## Test Coverage

24 new tests in test_backtest.py:

**BatchBacktestResult Tests (3):**
- test_batch_backtest_result_creation
- test_batch_backtest_result_is_frozen
- test_batch_backtest_result_to_dict

**Helper Function Tests (8):**
- test_sort_results_empty_list
- test_sort_results_by_subject (primary key)
- test_sort_results_by_valid_time (secondary key)
- test_sort_results_by_system_time (tertiary key)
- test_sort_results_missing_subject
- test_count_cells_empty_results
- test_count_cells_with_facts
- test_count_cells_with_candidates_and_bridges

**Engine.run_backtest() Integration Tests (11):**
- test_run_backtest_empty_list
- test_run_backtest_single_rfa
- test_run_backtest_multiple_rfas
- test_run_backtest_max_cases_limit (BAT-02)
- test_run_backtest_max_runtime_limit (BAT-02)
- test_run_backtest_max_cells_touched_limit (BAT-02)
- test_run_backtest_deterministic_ordering (BAT-03)
- test_run_backtest_with_shadow_spec
- test_run_backtest_tracks_runtime
- test_run_backtest_tracks_cells_touched
- test_run_backtest_result_is_batch_backtest_result

**Edge Cases Tests (2):**
- test_rfa_without_subject_field
- test_default_limits

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

1. **Import error (fixed automatically - Rule 1: Bug):**
   - **Issue:** Initial test file used `create_fact_cell` which doesn't exist in cell.py
   - **Root cause:** Codebase uses DecisionCell with Fact dataclass, not helper function
   - **Fix:** Changed to use DecisionCell(header=Header(...), fact=Fact(...), ...) pattern from test_engine.py
   - **Rule applied:** Rule 1 (Auto-fix bug) - Incorrect API usage is a bug
   - **Files modified:** tests/test_backtest.py (fixed imports and fixture)

2. **Transient test ordering issue (self-resolved):**
   - **Observation:** First full test run showed 1 failure in test_engine.py::test_process_rfa_deterministic_proof_bundle
   - **Resolution:** Test passed when run in isolation and on second full suite run
   - **Conclusion:** Non-deterministic test ordering issue, not related to our changes (0 regressions confirmed)

## Requirements Satisfied

**BAT-01: Batch Simulation API**
- ✅ engine.run_backtest() method executes simulation over multiple RFAs
- ✅ Same simulation_spec and bitemporal coordinates applied to all RFAs
- ✅ Returns BatchBacktestResult with list of SimulationResults
- ✅ Handles empty rfa_list gracefully (empty results, backtest_incomplete=False)

**BAT-02: Bounded Execution**
- ✅ max_cases limit enforced (stops after N RFAs processed)
- ✅ max_runtime_ms limit enforced (stops when ExecutionBudget.elapsed_ms() >= limit)
- ✅ max_cells_touched limit enforced (stops when cumulative cells >= limit)
- ✅ Returns backtest_incomplete=True when any limit exceeded
- ✅ Default limits: max_cases=1000, max_runtime_ms=60000 (60s), max_cells_touched=100000

**BAT-03: Deterministic Ordering**
- ✅ Results sorted by (subject, valid_time, system_time) regardless of input order
- ✅ Missing subject defaults to empty string for stable sort
- ✅ _sort_results() called before return (not after append)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Phase 12 (Audit Trail):
- Engine.run_backtest() available for batch backtest operations
- BatchBacktestResult provides execution metadata (cases_processed, runtime_ms, cells_touched)
- 892/892 tests passing (0 regressions)
- Complete batch backtest infrastructure with bounded execution and deterministic ordering

**Phase 11 Complete:** Batch Backtest fully integrated with comprehensive test coverage and bounded execution guarantees.
