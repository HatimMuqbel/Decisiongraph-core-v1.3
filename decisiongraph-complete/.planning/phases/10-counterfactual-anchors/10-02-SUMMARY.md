---
phase: 10-counterfactual-anchors
plan: 02
type: summary
subsystem: oracle-layer
tags: [engine-integration, anchor-detection, testing, ctf-requirements]

dependency_graph:
  requires:
    - "Phase 10 Plan 01: Anchor detection module (detect_counterfactual_anchors)"
    - "Phase 09 (Delta Report): DeltaReport.verdict_changed for conditional anchor detection"
    - "Phase 08 (Simulation Core): Engine.simulate_rfa() orchestration"
  provides:
    - "Engine.simulate_rfa() with anchor detection on verdict_changed=True"
    - "max_anchor_attempts and max_runtime_ms parameters for bounded execution"
    - "SimulationResult.anchors populated with anchor_result.to_dict()"
    - "Comprehensive anchor test suite (22 tests covering all CTF requirements)"
  affects:
    - "Phase 11 (Batch Backtest): Anchors available per simulation"
    - "Phase 12 (Audit Trail): Anchor logging for compliance"
    - "All future simulation consumers: anchors now available in results"

tech_stack:
  added: []
  patterns:
    - pattern: "Conditional anchor detection"
      location: "Engine.simulate_rfa() Step 9.5"
      purpose: "Only run expensive anchor search when verdict actually changed"
    - pattern: "Comprehensive test fixtures"
      location: "tests/test_anchors.py"
      purpose: "22 tests covering ExecutionBudget, AnchorResult, compute_anchor_hash, detect_counterfactual_anchors, Engine integration"

key_files:
  created:
    - path: "tests/test_anchors.py"
      purpose: "Comprehensive anchor detection test suite (22 tests)"
      coverage: "CTF-01 (determinism), CTF-02 (bounded execution), CTF-03 (minimal anchors), CTF-04 (incomplete flag)"
  modified:
    - path: "src/decisiongraph/engine.py"
      change: "Added anchor detection integration in simulate_rfa() with Step 9.5"
    - path: "tests/test_simulation.py"
      change: "Updated test_simulate_rfa_anchors_is_empty_dict for new anchor structure"

decisions:
  - name: "Conditional anchor detection (only when verdict_changed=True)"
    rationale: "Avoid expensive anchor search when shadow doesn't change verdict"
    impact: "anchors is empty dict when verdict_changed=False, performance optimization"
    alternatives: ["Always run anchor detection (wasteful for no-change scenarios)"]
  - name: "Empty anchor structure when no verdict change"
    rationale: "Consistent API - always return anchor dict, but with empty anchors list"
    impact: "Callers can always access anchors fields without checking if key exists"
    alternatives: ["Return null/None when no verdict change (inconsistent API)"]
  - name: "Default bounded execution limits"
    rationale: "max_anchor_attempts=100, max_runtime_ms=5000 balance performance vs completeness"
    impact: "Most simulations complete within defaults, large specs may hit limits"
    alternatives: ["Lower limits (faster but more incomplete)", "Higher limits (slower but more complete)"]

metrics:
  duration: "8 minutes"
  completed: "2026-01-28"

requirements_satisfied:
  - id: "CTF-01"
    description: "Deterministic anchor ordering and hashing"
    evidence: "Tests verify compute_anchor_hash() determinism (test_anchor_hash_deterministic, test_anchor_hash_same_for_reordered_anchors)"
  - id: "CTF-02"
    description: "Bounded execution (max_attempts, max_runtime_ms)"
    evidence: "Engine.simulate_rfa() passes max_anchor_attempts and max_runtime_ms; tests verify budget enforcement"
  - id: "CTF-03"
    description: "Minimal shadow components causing verdict delta"
    evidence: "Engine calls detect_counterfactual_anchors(); tests verify minimal anchor detection (test_minimal_anchor_found)"
  - id: "CTF-04"
    description: "anchors_incomplete flag when budget exceeded"
    evidence: "Tests verify anchors_incomplete=True for low limits (test_anchors_incomplete_when_attempts_exceeded, test_anchors_incomplete_when_timeout_exceeded)"
---

# Phase 10 Plan 02: Engine Integration for Anchor Detection Summary

**One-liner:** Engine.simulate_rfa() now calls detect_counterfactual_anchors() when verdict changes, with comprehensive test coverage for all CTF requirements

## What Was Built

Integrated anchor detection into Engine.simulate_rfa() pipeline and created comprehensive test suite:

### 1. Engine Integration (src/decisiongraph/engine.py)

**Import addition:**
```python
from .anchors import detect_counterfactual_anchors, AnchorResult
```

**Updated signature:**
```python
def simulate_rfa(
    self, rfa_dict, simulation_spec, at_valid_time, as_of_system_time,
    max_anchor_attempts: int = 100,
    max_runtime_ms: int = 5000
) -> SimulationResult:
```

**Step 9.5 added (after delta_report computation):**
```python
if delta_report.verdict_changed:
    anchor_result = detect_counterfactual_anchors(
        engine=self, rfa_dict=canonical_rfa, base_result=base_result,
        simulation_spec=simulation_spec, at_valid_time=at_valid_time,
        as_of_system_time=as_of_system_time,
        max_anchor_attempts=max_anchor_attempts,
        max_runtime_ms=max_runtime_ms
    )
    anchors_dict = anchor_result.to_dict()
else:
    # No verdict change = no anchors to detect
    anchors_dict = {
        'anchors': [], 'anchors_incomplete': False,
        'attempts_used': 0, 'runtime_ms': 0.0, 'anchor_hash': ''
    }
```

**SimulationResult population:**
```python
return SimulationResult(
    ...
    anchors=anchors_dict,  # Populated from Step 9.5
    ...
)
```

### 2. Comprehensive Test Suite (tests/test_anchors.py)

**22 tests organized in 5 categories:**

**ExecutionBudget tests (5 tests - CTF-02):**
- test_execution_budget_tracks_attempts
- test_execution_budget_tracks_time
- test_execution_budget_exceeded_by_attempts
- test_execution_budget_exceeded_by_time
- test_execution_budget_not_exceeded

**AnchorResult tests (3 tests):**
- test_anchor_result_frozen (immutability)
- test_anchor_result_to_dict (serialization)
- test_anchor_result_with_incomplete_flag (CTF-04)

**compute_anchor_hash tests (3 tests - CTF-01):**
- test_anchor_hash_deterministic
- test_anchor_hash_different_for_different_anchors
- test_anchor_hash_same_for_reordered_anchors (sorted canonicalization)

**detect_counterfactual_anchors tests (7 tests - CTF-02/03/04):**
- test_no_shadow_components_returns_empty_anchors
- test_single_shadow_fact_is_anchor
- test_minimal_anchor_found (greedy ablation - CTF-03)
- test_anchors_incomplete_when_attempts_exceeded (CTF-04)
- test_anchors_incomplete_when_timeout_exceeded (CTF-04)
- test_anchor_detection_deterministic (CTF-01)
- test_no_anchors_when_verdict_unchanged

**Engine integration tests (4 tests):**
- test_simulate_rfa_populates_anchors_when_verdict_changed
- test_simulate_rfa_empty_anchors_when_verdict_unchanged
- test_simulate_rfa_respects_max_anchor_attempts (CTF-02)
- test_simulate_rfa_respects_max_runtime_ms (CTF-02)

### 3. Test Fixture Updates

**Updated test_simulation.py:**
- Modified `test_simulate_rfa_anchors_is_empty_dict` to expect new anchor structure
- Changed assertion from `assert result.anchors == {}` to structured validation
- Validates all anchor dict fields: anchors, anchors_incomplete, attempts_used, runtime_ms, anchor_hash

## Test Results

**Total tests:** 868 (846 existing + 22 new anchor tests)
**Pass rate:** 100% (868/868)
**Regressions:** 0 (all existing tests pass)

**CTF requirement coverage:**
- **CTF-01 (Determinism):** 3 tests for compute_anchor_hash, 1 for detect_counterfactual_anchors
- **CTF-02 (Bounded execution):** 5 ExecutionBudget tests + 2 Engine integration tests
- **CTF-03 (Minimal anchors):** 3 detect_counterfactual_anchors tests
- **CTF-04 (Incomplete flag):** 3 tests (AnchorResult, attempts exceeded, timeout exceeded)

## Implementation Highlights

### Conditional Anchor Detection

Anchor detection only runs when verdict changes, avoiding expensive computation for no-change scenarios:

```python
if delta_report.verdict_changed:
    # Run anchor detection
else:
    # Return empty anchor structure
```

This optimization is crucial because:
- Many simulations don't change verdict (e.g., confidence-only changes)
- Greedy ablation requires O(N²) simulations in worst case
- Bounded execution limits prevent DoS, but still expensive

### Bounded Execution Default Values

**max_anchor_attempts=100:**
- Allows testing up to 100 shadow component subsets
- For N components, greedy tests ≤ N² subsets (worst case)
- 100 attempts handles ~10 shadow components comfortably

**max_runtime_ms=5000 (5 seconds):**
- Balances user experience (avoid long waits) vs completeness
- Most simulations complete in <1 second
- Timeout prevents infinite loops or extremely slow queries

### Empty Anchor Structure Design

When verdict doesn't change, return consistent structure:

```python
{
    'anchors': [],              # Empty list (no anchors)
    'anchors_incomplete': False, # Search didn't run, so not incomplete
    'attempts_used': 0,         # No search attempts
    'runtime_ms': 0.0,          # No runtime
    'anchor_hash': ''           # Empty hash
}
```

**Benefits:**
- Callers can always access `result.anchors['anchors']` without checking existence
- Consistent API regardless of verdict_changed status
- Clear signal: empty list = no anchors found (vs incomplete = search stopped early)

## Pipeline Integration

Engine.simulate_rfa() now has 13 steps (Step 9.5 added):

1. Capture chain head BEFORE simulation (SHD-06)
2. Canonicalize RFA
3. Validate RFA schema and fields
4. Query base reality at frozen coordinates (SIM-02)
5. Build OverlayContext from simulation_spec
6. Run shadow query in context manager (SIM-03)
7. Capture chain head AFTER simulation (SHD-06)
8. Generate simulation_id
9. Compute delta report (SIM-04)
**9.5. Detect counterfactual anchors if verdict changed (CTF-02/03/04)** ← NEW
10. Tag proof bundles with origin (SIM-05)
11. Create contamination attestation (SHD-06)
12. Assemble proof_bundle
13. Create immutable SimulationResult

## Deviations from Plan

None - plan executed exactly as written.

## Next Phase Readiness

**Phase 10 complete. Ready for Phase 11 (Batch Backtest).**

**Anchors available for:**
- Batch simulation: Each simulation result includes anchors (if verdict changed)
- Audit trail: Anchor data ready for logging (Phase 12)
- Analysis tools: External tools can parse anchors from SimulationResult

**Phase 11 considerations:**
- Batch operations may generate many anchors (one per simulation)
- May need anchor aggregation (e.g., "most common anchors across 100 sims")
- Bounded execution critical for batch (100 sims × 100 anchor attempts = 10,000 re-simulations worst case)

## Performance Notes

**Anchor detection cost:**
- Best case: O(N) - single shadow component causes delta
- Average case: O(N²) - greedy ablation tests subsets from largest to smallest
- Worst case: O(N² × sim_cost) - each subset requires re-simulation

**For typical scenarios:**
- 1-5 shadow components: <100ms anchor detection
- 10 shadow components: <1 second
- 20+ shadow components: May hit max_anchor_attempts limit

**Optimization opportunities (future):**
- Cache simulation results for common subsets
- Parallelize subset testing (concurrent simulations)
- Heuristic ordering (test most likely anchors first)

## Learnings

**New (10-02):**
- Conditional expensive operations crucial for performance (only run when needed)
- Consistent API structure better than null/None (always return anchor dict)
- Test fixture timestamps must use current time for bitemporal queries (get_current_timestamp)
- Shadow fact replacement doesn't change fact_count (replaces base, not adds)
- Comprehensive test categories organize validation well (budget, result, hash, algorithm, integration)

## Files Modified This Plan

**Created:**
- tests/test_anchors.py (846 lines, 22 tests)

**Modified:**
- src/decisiongraph/engine.py (+42 lines, -8 lines)
  - Import detect_counterfactual_anchors, AnchorResult
  - Updated simulate_rfa signature with anchor parameters
  - Added Step 9.5 for conditional anchor detection
  - Updated docstring with anchor documentation
  - Updated SimulationResult construction to use anchors_dict
- tests/test_simulation.py (+7 lines, -2 lines)
  - Updated test_simulate_rfa_anchors_is_empty_dict for new structure

**Commits:**
- 2cc2495: feat(10-02): integrate anchor detection into Engine.simulate_rfa()
- 669f3b7: test(10-02): create comprehensive anchor detection tests
- fe99f24: fix(10-02): update Phase 9 test for new anchor structure

---

**Phase 10 Status:** COMPLETE (Plans 01/02 done)
**Next:** Phase 11 (Batch Backtest) - run multiple simulations efficiently
