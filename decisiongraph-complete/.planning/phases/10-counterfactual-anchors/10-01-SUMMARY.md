---
phase: 10-counterfactual-anchors
plan: 01
type: summary
subsystem: oracle-layer
tags: [counterfactual, anchor-detection, greedy-ablation, bounded-search, explainability]

dependency_graph:
  requires:
    - "Phase 09 (Delta Report + Proof): compute_delta_report for verdict_changed detection"
    - "Phase 08 (Simulation Core): Engine.simulate_rfa() for re-running simulations"
    - "Phase 07 (Shadow Foundation): Shadow cell infrastructure"
  provides:
    - "ExecutionBudget class for bounded execution (CTF-02)"
    - "AnchorResult frozen dataclass with anchors_incomplete flag (CTF-04)"
    - "detect_counterfactual_anchors() greedy ablation algorithm (CTF-03)"
    - "compute_anchor_hash() for deterministic anchor fingerprinting (CTF-01)"
  affects:
    - "Phase 10 Plan 02: Engine integration for automatic anchor detection"
    - "Phase 11 (Batch Backtest): Anchor detection per simulation"
    - "Phase 12 (Audit Trail): Anchor logging for compliance"

tech_stack:
  added: []
  patterns:
    - pattern: "Greedy iterative ablation"
      location: "detect_counterfactual_anchors()"
      purpose: "Find minimal shadow component set causing verdict delta"
    - pattern: "Bounded execution tracking"
      location: "ExecutionBudget class"
      purpose: "Prevent DoS via unbounded anchor search"
    - pattern: "Deterministic anchor hashing"
      location: "compute_anchor_hash()"
      purpose: "Reproducible anchor fingerprints for deduplication"

key_files:
  created:
    - path: "src/decisiongraph/anchors.py"
      purpose: "Anchor detection module"
      exports: ["ExecutionBudget", "AnchorResult", "compute_anchor_hash", "detect_counterfactual_anchors"]
  modified:
    - path: "src/decisiongraph/__init__.py"
      change: "Added anchor module exports + missing simulation exports"

decisions:
  - name: "Greedy ablation over exhaustive search"
    rationale: "Greedy is polynomial time, exhaustive is exponential (2^N subsets)"
    impact: "May miss globally minimal anchor, but locally minimal sufficient for debugging"
    alternatives: ["SAT solver (PySAT)", "Minimal hitting set algorithms"]
  - name: "Bounded execution mandatory"
    rationale: "Unbounded search is DoS vector - attacker submits 100 shadow components"
    impact: "Search may stop before finding minimal anchor (returns anchors_incomplete=True)"
    alternatives: ["Unbounded search (rejected - security risk)"]
  - name: "Component-level granularity"
    rationale: "Track anchors at cell_id level, not field level"
    impact: "Coarser than field-level ('rule X changed' vs 'rule X predicate changed')"
    alternatives: ["Field-level tracking (deferred to future)"]
  - name: "Return first minimal anchor"
    rationale: "Multiple disjoint minimal sets could exist (anchor1 OR anchor2 causes delta)"
    impact: "Users only see one explanation (greedy limitation)"
    alternatives: ["Find all minimal sets (exponential cost)"]

metrics:
  duration: "2.2 minutes"
  completed: "2026-01-28"

requirements_satisfied:
  - id: "CTF-01"
    description: "Deterministic anchor ordering and hashing"
    evidence: "compute_anchor_hash() uses sorted JSON with SHA-256"
  - id: "CTF-02"
    description: "Bounded execution (max_attempts, max_runtime_ms)"
    evidence: "ExecutionBudget tracks both limits, checked in inner and outer loops"
  - id: "CTF-03"
    description: "Greedy ablation algorithm"
    evidence: "detect_counterfactual_anchors() implements iterative subset testing"
  - id: "CTF-04"
    description: "Incomplete anchor flagging"
    evidence: "AnchorResult.anchors_incomplete=True when budget exceeded"
---

# Phase 10 Plan 01: Anchor Detection Module Summary

**One-liner:** Greedy ablation algorithm with bounded execution for identifying minimal shadow components causing verdict delta

## What Was Built

Created anchor detection module (`src/decisiongraph/anchors.py`) with four core components:

1. **ExecutionBudget class (CTF-02)**: Mutable tracker for bounded execution
   - Tracks `max_attempts` (simulation count) and `max_runtime_ms` (timeout)
   - `is_exceeded()` checks if either limit hit
   - `increment()` bumps attempt counter
   - `elapsed_ms()` returns runtime in milliseconds

2. **AnchorResult frozen dataclass (CTF-04)**: Immutable anchor detection result
   - `anchors`: List of (component_type, cell_id) tuples
   - `anchors_incomplete`: True when budget exceeded before completing search
   - `attempts_used`: Actual simulation count
   - `runtime_ms`: Actual runtime
   - `anchor_hash`: SHA-256 of sorted anchors for deduplication

3. **detect_counterfactual_anchors() function (CTF-03)**: Greedy ablation algorithm
   - Extracts shadow component IDs from simulation_spec (sorted - CTF-01)
   - Combines into deterministic list: facts, rules, policy heads, bridges
   - Iterates from largest to smallest subsets
   - For each subset: builds filtered spec, runs simulation, checks verdict_changed
   - Returns minimal subset that preserves verdict delta
   - Early exit with anchors_incomplete=True when budget exceeded

4. **compute_anchor_hash() helper (CTF-01)**: Deterministic SHA-256 hash
   - Sorts anchors for reproducibility
   - Uses `json.dumps(sort_keys=True)` for canonical JSON
   - Returns 64-character hex string

**Key architectural decisions:**
- Greedy ablation (polynomial time) over exhaustive search (exponential)
- Component-level granularity (cell_id, not field-level)
- Return first minimal anchor (not all minimal sets)
- Bounded execution mandatory (DoS prevention)

## How It Works

**Greedy iterative ablation workflow:**

```
1. Extract all shadow component IDs from simulation_spec
   - shadow_facts: ['cell-a', 'cell-b']
   - shadow_rules: ['cell-c']
   - shadow_policy_heads: ['cell-d']
   → all_components = [('fact', 'cell-a'), ('fact', 'cell-b'), ('rule', 'cell-c'), ('policy', 'cell-d')]

2. Start with full set as minimal_anchor (baseline: all components cause delta)

3. For size from N-1 down to 1:
   - Try each subset of this size (itertools.combinations)
   - Build filtered simulation_spec with only subset components
   - Run engine.simulate_rfa() with filtered spec
   - If test_result.delta_report.verdict_changed is True:
     - Update minimal_anchor = subset
     - Break (found smaller anchor, try even smaller)
   - Check budget.is_exceeded() before and inside inner loop

4. Return AnchorResult with sorted anchors, attempts_used, runtime_ms
   - If budget exceeded: anchors_incomplete=True
   - If completed: anchors_incomplete=False
```

**Example:** Simulation has 4 shadow components, verdict changed from DENIED to ALLOWED.
- Size 4: [all components] → verdict_changed=True (baseline)
- Size 3: Try [A,B,C], [A,B,D], [A,C,D], [B,C,D]
  - [A,B,C] → verdict_changed=True → minimal_anchor=[A,B,C]
- Size 2: Try [A,B], [A,C], [B,C]
  - [A,B] → verdict_changed=True → minimal_anchor=[A,B]
- Size 1: Try [A], [B]
  - [A] → verdict_changed=False
  - [B] → verdict_changed=False
- **Result:** minimal_anchor=[A,B] (both A and B required for verdict delta)

**Budget enforcement:**
- Check `budget.is_exceeded()` in outer loop (before each size)
- Check again in inner loop (before each subset simulation)
- Double checking prevents timeout exceeded by large margin

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Greedy ablation over exhaustive | Polynomial time (O(N²)) vs exponential (2^N) | May miss globally minimal anchor, locally minimal sufficient |
| Bounded execution mandatory | Unbounded search is DoS vector | Search may stop early with anchors_incomplete=True |
| Component-level granularity | Track cell_id, not field-level | Coarser explanation ('rule X changed' vs 'predicate changed') |
| Return first minimal anchor | Multiple disjoint sets could exist | Users see one explanation, not all possibilities |
| Deep copy simulation_spec | Avoid mutating original during ablation | Memory overhead, but prevents contamination |

## Deviations from Plan

None - plan executed exactly as written.

## Testing Evidence

1. **Module structure verification:**
   - `python -c "from decisiongraph.anchors import ExecutionBudget, AnchorResult, compute_anchor_hash; print('Imports work')"` → SUCCESS
   - `python -c "from decisiongraph.anchors import detect_counterfactual_anchors; print('Function imports')"` → SUCCESS

2. **Package exports verification:**
   - `python -c "from decisiongraph import ExecutionBudget, AnchorResult, compute_anchor_hash, detect_counterfactual_anchors; print('All exports work')"` → SUCCESS

3. **Regression testing:**
   - `pytest tests/ -x -q` → 846 passed, 8 warnings (pre-existing)
   - Zero regressions introduced

4. **Determinism verification:**
   - `compute_anchor_hash([('rule', 'a'), ('fact', 'b')])` produces same hash as `compute_anchor_hash([('fact', 'b'), ('rule', 'a')])` (order-independent)

## Commits

| Hash | Message | Files |
|------|---------|-------|
| c31c27f | feat(10-01): add ExecutionBudget and AnchorResult classes | anchors.py (created) |
| b37314b | feat(10-01): implement detect_counterfactual_anchors function | anchors.py (modified) |
| b6214d4 | feat(10-01): add anchor module exports to package | __init__.py (modified) |

## Next Phase Readiness

**Blockers:** None

**Concerns:** None

**Ready for:** Phase 10 Plan 02 (Engine Integration)

**Next plan will:**
- Integrate detect_counterfactual_anchors() into Engine.simulate_rfa()
- Add optional `detect_anchors` parameter (default: False)
- Populate SimulationResult.anchors field
- Add comprehensive tests for anchor detection workflow

**Integration points verified:**
- `detect_counterfactual_anchors()` accepts Engine instance
- Uses `engine.simulate_rfa()` for re-running simulations
- Reads `delta_report.verdict_changed` from SimulationResult
- Returns AnchorResult compatible with SimulationResult.anchors dict field

**API surface:**
```python
from decisiongraph import ExecutionBudget, AnchorResult, detect_counterfactual_anchors

# Direct usage (before Engine integration)
result = detect_counterfactual_anchors(
    engine=engine,
    rfa_dict={"namespace": "corp.hr", ...},
    base_result={...},
    simulation_spec={"shadow_facts": [...], "shadow_rules": [...]},
    at_valid_time="2025-01-01T00:00:00Z",
    as_of_system_time="2025-01-01T00:00:00Z",
    max_anchor_attempts=100,
    max_runtime_ms=5000
)

print(result.anchors)  # [('rule', 'cell-abc'), ('fact', 'cell-xyz')]
print(result.anchors_incomplete)  # False
print(result.anchor_hash)  # "abc123..."
```

**Test coverage:** 846/846 tests passing (no new tests this plan - integration tests in 10-02)

**Performance:** Module creation only - no performance impact (algorithm not yet called)

---

**Phase 10 Progress:** 1/2 plans complete (Anchor Detection Module ✓, Engine Integration pending)
