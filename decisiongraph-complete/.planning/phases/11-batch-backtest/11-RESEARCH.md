# Phase 11: Batch Backtest - Research

**Researched:** 2026-01-28
**Domain:** Batch simulation, backtest infrastructure, bounded batch operations, deterministic result ordering
**Confidence:** HIGH

## Summary

Phase 11 implements batch backtesting - running simulations over multiple historical RFAs to test policy changes against past decisions. This is the standard final step in policy simulation infrastructure: individual simulation (Phase 8-10) proves correctness, batch backtesting proves scalability and real-world utility. The technical domain is straightforward: iterate over input cases, call existing `engine.simulate_rfa()` per case, collect results, enforce limits, sort deterministically.

The critical insight from research is that batch operations require THREE types of limits: (1) max_cases (how many RFAs to process), (2) max_runtime_ms (total batch timeout), and (3) max_cells_touched (cumulative cell access across all simulations). These prevent DoS via large batches, slow simulations, or expensive per-case queries. Industry standard: return partial results with `backtest_incomplete=True` when any limit exceeded.

DecisionGraph's foundation makes batch backtesting exceptionally clean: `engine.simulate_rfa()` is already deterministic and immutable (Phase 8-10), so batching is just a for-loop with budget tracking. The ExecutionBudget pattern from Phase 10 extends naturally to track cumulative metrics across cases. Deterministic ordering (BAT-03) follows Scholar's existing pattern: sorted by (subject, valid_time, system_time) as primary/secondary/tertiary keys.

**Primary recommendation:** Add `engine.run_backtest(rfa_list, simulation_spec, ...)` method that iterates over RFAs with ExecutionBudget tracking for max_cases, max_runtime_ms, and max_cells_touched. Return BatchBacktestResult frozen dataclass with list of SimulationResults (sorted deterministically) plus backtest_incomplete flag. Reuse Phase 10's ExecutionBudget pattern for bounded execution.

## Standard Stack

This phase uses only Python standard library - no external dependencies.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| typing | stdlib (3.10+) | Type hints for BatchBacktestResult | Code clarity and consistency with Phase 10 |
| time | stdlib | Runtime tracking for max_runtime_ms | Standard for execution bounds (Phase 10 pattern) |
| dataclasses | stdlib | BatchBacktestResult frozen dataclass | Immutability pattern used throughout DecisionGraph |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| itertools | stdlib | islice() for bounded iteration | Early exit when max_cases reached |
| sorted() builtin | N/A | Deterministic result ordering | Multi-key sort (subject, valid_time, system_time) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| For-loop with manual limits | itertools.islice() | islice cleaner but for-loop more explicit with multiple limit types |
| Sequential processing | concurrent.futures (parallel) | Parallelization deferred to Phase 11+ for complexity; sequential sufficient for MVP |
| Manual sorting | pandas.DataFrame.sort_values() | Pandas overkill; sorted() with key= handles multi-key sort |
| Circuit breaker pattern | pybreaker library | External dependency; manual budget tracking simpler and proven (Phase 10) |

**Installation:**
No external dependencies. All components are Python stdlib.

## Architecture Patterns

### Recommended Project Structure
```
src/decisiongraph/
├── engine.py            # ADD: run_backtest() method
├── backtest.py          # NEW: BatchBacktestResult, batch-specific logic
└── anchors.py           # REUSE: ExecutionBudget pattern
```

### Pattern 1: Bounded Batch Iteration with ExecutionBudget (BAT-02)
**What:** Iterate over RFA list with cumulative limit tracking (cases, runtime, cells)
**When to use:** Always - unbounded batch is DoS vector
**Example:**
```python
# Source: Phase 10 ExecutionBudget + batch processing research
from typing import List, Dict, Any
from .anchors import ExecutionBudget
from .simulation import SimulationResult

def run_backtest(
    engine: 'Engine',
    rfa_list: List[Dict[str, Any]],
    simulation_spec: Dict[str, Any],
    at_valid_time: str,
    as_of_system_time: str,
    max_cases: int = 1000,
    max_runtime_ms: int = 60000,  # 60 seconds
    max_cells_touched: int = 100000
) -> 'BatchBacktestResult':
    """
    Run simulations over multiple RFAs (BAT-01, BAT-02, BAT-03).

    Bounded execution (BAT-02):
    - max_cases: Stop after N RFAs processed
    - max_runtime_ms: Stop after timeout exceeded
    - max_cells_touched: Stop after cumulative cell access limit

    Returns:
        BatchBacktestResult with results (sorted by subject, valid_time, system_time)
        and backtest_incomplete flag if any limit exceeded
    """
    # Create execution budget (reuse Phase 10 pattern)
    budget = ExecutionBudget(max_attempts=max_cases, max_runtime_ms=max_runtime_ms)

    results: List[SimulationResult] = []
    cells_touched = 0

    for rfa_dict in rfa_list:
        # Check execution bounds (BAT-02)
        if budget.is_exceeded():
            # Timeout or max_cases exceeded
            return BatchBacktestResult(
                results=_sort_results(results),  # BAT-03
                backtest_incomplete=True,
                cases_processed=len(results),
                runtime_ms=budget.elapsed_ms(),
                cells_touched=cells_touched
            )

        if cells_touched >= max_cells_touched:
            # Cell access limit exceeded
            return BatchBacktestResult(
                results=_sort_results(results),
                backtest_incomplete=True,
                cases_processed=len(results),
                runtime_ms=budget.elapsed_ms(),
                cells_touched=cells_touched
            )

        # Run simulation for this RFA
        sim_result = engine.simulate_rfa(
            rfa_dict=rfa_dict,
            simulation_spec=simulation_spec,
            at_valid_time=at_valid_time,
            as_of_system_time=as_of_system_time
        )

        results.append(sim_result)
        budget.increment()

        # Track cells touched (from proof_bundle metadata)
        cells_touched += _count_cells_in_simulation(sim_result)

    # All cases completed within budget
    return BatchBacktestResult(
        results=_sort_results(results),  # BAT-03
        backtest_incomplete=False,
        cases_processed=len(results),
        runtime_ms=budget.elapsed_ms(),
        cells_touched=cells_touched
    )
```

### Pattern 2: Deterministic Multi-Key Sorting (BAT-03)
**What:** Sort batch results by (subject, valid_time, system_time) for reproducibility
**When to use:** Always - deterministic ordering is requirement
**Example:**
```python
# Source: Python sorting docs + DecisionGraph determinism pattern
from typing import List
from .simulation import SimulationResult

def _sort_results(results: List[SimulationResult]) -> List[SimulationResult]:
    """
    Sort results deterministically (BAT-03).

    Primary key: subject from RFA
    Secondary key: at_valid_time
    Tertiary key: as_of_system_time

    Returns sorted list (stable sort, reproducible).
    """
    return sorted(
        results,
        key=lambda r: (
            r.rfa_dict.get('subject', ''),  # Primary: subject
            r.at_valid_time,                # Secondary: valid_time
            r.as_of_system_time             # Tertiary: system_time
        )
    )
```

### Pattern 3: Cumulative Metrics Tracking (BAT-02)
**What:** Track total cells touched across all simulations to prevent expensive batch queries
**When to use:** When batch RFAs might access large portions of chain
**Example:**
```python
# Source: Phase 9 proof_bundle structure + bounded execution research
from .simulation import SimulationResult

def _count_cells_in_simulation(sim_result: SimulationResult) -> int:
    """
    Count total cells accessed during simulation.

    Used for max_cells_touched limit (BAT-02). Counts cells in:
    - base_result proof_bundle
    - shadow_result proof_bundle

    Returns:
        Total cell count accessed
    """
    base_cells = len(sim_result.base_result.get('facts', []))
    base_cells += len(sim_result.base_result.get('rules', []))
    base_cells += len(sim_result.base_result.get('bridges', []))

    shadow_cells = len(sim_result.shadow_result.get('facts', []))
    shadow_cells += len(sim_result.shadow_result.get('rules', []))
    shadow_cells += len(sim_result.shadow_result.get('bridges', []))

    return base_cells + shadow_cells
```

### Pattern 4: BatchBacktestResult Frozen Dataclass
**What:** Immutable result container for batch backtest
**When to use:** Always - consistency with SimulationResult, AnchorResult patterns
**Example:**
```python
# Source: Phase 9 SimulationResult, Phase 10 AnchorResult patterns
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class BatchBacktestResult:
    """
    Immutable batch backtest result (BAT-01, BAT-02, BAT-03).

    Contains list of SimulationResults plus metadata about execution budget.

    Attributes:
        results: List of SimulationResults (sorted by subject, valid_time, system_time)
        backtest_incomplete: True if any limit exceeded (max_cases, max_runtime_ms, max_cells_touched)
        cases_processed: Number of RFAs processed before stopping
        runtime_ms: Actual batch runtime in milliseconds
        cells_touched: Cumulative cells accessed across all simulations
    """
    results: List[SimulationResult]
    backtest_incomplete: bool
    cases_processed: int
    runtime_ms: float
    cells_touched: int

    def to_dict(self) -> dict:
        """Convert to serializable dict."""
        return {
            'results': [r.to_dict() for r in self.results],
            'backtest_incomplete': self.backtest_incomplete,
            'cases_processed': self.cases_processed,
            'runtime_ms': self.runtime_ms,
            'cells_touched': self.cells_touched
        }
```

### Anti-Patterns to Avoid
- **Unbounded batch iteration:** Always enforce max_cases, max_runtime_ms, max_cells_touched (DoS vector)
- **Non-deterministic result ordering:** Always sort by (subject, valid_time, system_time) for reproducibility
- **Parallel execution without bounds:** Sequential first; parallelization adds complexity (defer to later phase)
- **Mutating simulation_spec during batch:** Deep copy per case if allowing per-case modifications
- **Ignoring backtest_incomplete flag:** Always return flag when limits exceeded (honesty requirement)

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-key sorting | Manual comparisons | sorted() with key= lambda | Stable, handles ties correctly, proven |
| Bounded iteration | Manual counter + break | ExecutionBudget from Phase 10 | Already tested, handles multiple limit types |
| Early exit on timeout | signal.alarm() | time.time() checks | Cross-platform (Windows), thread-safe |
| Batch result aggregation | Manual loops | List comprehension + sorted() | Pythonic, readable, efficient |
| Execution budget tracking | Custom class | Reuse ExecutionBudget | Proven in Phase 10, DRY principle |

**Key insight:** Batch backtesting is simpler than it appears because DecisionGraph already has deterministic simulation (Phase 8-10). The "batch" layer is just iteration + budget tracking + sorting. Don't over-engineer with job queues, worker pools, or retry logic - sequential for-loop with ExecutionBudget is sufficient and maintainable.

## Common Pitfalls

### Pitfall 1: Not tracking cumulative cells_touched (DoS vector)
**What goes wrong:** Batch of 100 RFAs where each touches 10K cells = 1M cell accesses, overwhelming system
**Why it happens:** Only tracking case count and runtime, not per-case resource usage
**How to avoid:** Track cumulative cells_touched, enforce max_cells_touched limit (BAT-02)
**Warning signs:** Batch hangs on large historical datasets, memory pressure, slow queries

### Pitfall 2: Non-deterministic sorting when subjects have None
**What goes wrong:** RFAs without subject field produce inconsistent ordering across runs
**Why it happens:** Python sort treats None unpredictably when comparing with strings
**How to avoid:** Use `r.rfa_dict.get('subject', '')` to default None → empty string
**Warning signs:** Flaky tests, different result order across runs, subject=None RFAs

### Pitfall 3: Forgetting backtest_incomplete flag on any limit
**What goes wrong:** Partial results presented as complete, users don't realize backtest stopped early
**Why it happens:** Only checking timeout, forgetting max_cases or max_cells_touched
**How to avoid:** Set backtest_incomplete=True for ANY limit exceeded (BAT-02 requirement)
**Warning signs:** Users complain results don't match expected case count, silent truncation

### Pitfall 4: Sorting after limit exceeded (wasted work)
**What goes wrong:** Batch hits timeout, then spends seconds sorting 10K results before returning
**Why it happens:** Sort happens unconditionally at end, even when budget exceeded
**How to avoid:** Sort results in return statement (lazy evaluation), or sort incrementally
**Warning signs:** Batch timeout exceeded by large margin (60s timeout but 75s runtime)

### Pitfall 5: Not handling empty rfa_list gracefully
**What goes wrong:** Batch crashes or returns confusing error when given empty list
**Why it happens:** No early return check for len(rfa_list) == 0
**How to avoid:** Early return with backtest_incomplete=False, cases_processed=0
**Warning signs:** IndexError or unexpected behavior on empty input

### Pitfall 6: Reusing same simulation_spec reference across iterations
**What goes wrong:** If simulation_spec modified per-case, mutations leak across iterations
**Why it happens:** Python passes dicts by reference, mutations visible to later iterations
**How to avoid:** Deep copy simulation_spec if allowing per-case modifications (or use immutable pattern)
**Warning signs:** Later cases show unexpected shadow modifications from earlier cases

## Code Examples

Verified patterns from official sources and existing codebase:

### ExecutionBudget Reuse from Phase 10
```python
# Source: Phase 10 anchors.py ExecutionBudget
from .anchors import ExecutionBudget

# Create budget with max_cases as max_attempts
budget = ExecutionBudget(max_attempts=max_cases, max_runtime_ms=max_runtime_ms)

for rfa_dict in rfa_list:
    if budget.is_exceeded():
        # Either max_cases (attempts) or max_runtime_ms exceeded
        return partial_results(backtest_incomplete=True)

    # Process RFA
    result = engine.simulate_rfa(...)
    budget.increment()
```

### Multi-Key Deterministic Sort
```python
# Source: Python sorting docs - stable sort with tuple key
results_sorted = sorted(
    results,
    key=lambda r: (
        r.rfa_dict.get('subject', ''),  # Primary key (defaults None → '')
        r.at_valid_time,                # Secondary key
        r.as_of_system_time             # Tertiary key
    )
)
# Same results + same key → identical order (deterministic)
```

### Bounded Iteration with Multiple Limit Types
```python
# Source: Batch processing research + Phase 10 bounded execution
import time

start_time = time.time()
cases_processed = 0
cells_touched = 0

for rfa in rfa_list:
    # Check all three limits (BAT-02)
    elapsed_ms = (time.time() - start_time) * 1000

    if cases_processed >= max_cases:
        return partial_results(backtest_incomplete=True)

    if elapsed_ms >= max_runtime_ms:
        return partial_results(backtest_incomplete=True)

    if cells_touched >= max_cells_touched:
        return partial_results(backtest_incomplete=True)

    # Process case
    result = process_rfa(rfa)
    cases_processed += 1
    cells_touched += count_cells(result)
```

### Empty Input Handling
```python
# Source: Defensive programming best practices
def run_backtest(rfa_list, ...):
    # Early return for empty input (BAT-01 edge case)
    if not rfa_list:
        return BatchBacktestResult(
            results=[],
            backtest_incomplete=False,
            cases_processed=0,
            runtime_ms=0.0,
            cells_touched=0
        )

    # Proceed with batch processing
    ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Unbounded batch processing | Bounded with max_cases, max_runtime_ms, max_cells_touched | 2020s (DoS awareness) | Prevents resource exhaustion attacks |
| Non-deterministic result ordering | Sorted by (subject, time, time) | 2025+ (reproducibility) | Enables verification, audit trail |
| Synchronous blocking batches | Async/parallel batch processing | 2022+ (cloud scale) | Faster backtests, but adds complexity |
| Single limit type (timeout only) | Multiple limit types (cases, time, cells) | 2024+ (fine-grained control) | Prevents multiple DoS vectors |

**Deprecated/outdated:**
- Unbounded for-loops: Use ExecutionBudget with max_cases/max_runtime_ms/max_cells_touched
- Non-deterministic result order: Use sorted() with multi-key tuple
- Parallel-by-default: Use sequential first, parallelize only when proven bottleneck

## Open Questions

Things that couldn't be fully resolved:

1. **Parallel vs sequential execution**
   - What we know: Sequential is simpler, safer, sufficient for MVP (100-1000 cases)
   - What's unclear: When does parallelization become necessary?
   - Recommendation: Start sequential; parallelize in Phase 11+ if benchmarks show need

2. **Default execution bounds**
   - What we know: Industry uses max_cases=100-10000, max_runtime_ms=10000-600000
   - What's unclear: What's right for DecisionGraph's typical batch size?
   - Recommendation: Conservative defaults (max_cases=1000, max_runtime_ms=60000, max_cells_touched=100000), make configurable

3. **Cells_touched counting granularity**
   - What we know: Can count cells in proof_bundle (facts + rules + bridges)
   - What's unclear: Should anchors count toward cells_touched? What about shadow cells?
   - Recommendation: Count all cells in base_result + shadow_result proof bundles; anchors are metadata (don't count)

4. **Result aggregation statistics**
   - What we know: BatchBacktestResult contains list of SimulationResults
   - What's unclear: Should we compute aggregate statistics (avg score_delta, verdict_changed percentage)?
   - Recommendation: Defer aggregation to Phase 12 (audit trail); Phase 11 returns raw results

5. **Partial batch on error vs skip failed cases**
   - What we know: Limit exceeded → return partial results with backtest_incomplete=True
   - What's unclear: If individual RFA simulation fails, should batch stop or skip that case?
   - Recommendation: Propagate exceptions (don't swallow errors); caller decides retry policy

## Sources

### Primary (HIGH confidence)
- Python stdlib documentation - sorted(), time.time(), dataclasses
- Phase 10 anchors.py - ExecutionBudget pattern (existing codebase)
- Phase 9 simulation.py - SimulationResult pattern (existing codebase)
- Phase 8 engine.py - simulate_rfa() method (existing codebase)
- [Python Sorting Techniques](https://docs.python.org/3/howto/sorting.html) - Multi-key stable sort
- [NautilusTrader Backtesting](https://nautilustrader.io/docs/latest/concepts/backtesting/) - Deterministic batch processing
- [Sort Python Dictionaries (TheLinuxCode 2026)](https://thelinuxcode.com/sort-python-dictionaries-by-key-or-value-practical-guide-2026/) - Deterministic ordering best practices

### Secondary (MEDIUM confidence)
- [AWS Lambda Powertools Batch Processing](https://docs.powertools.aws.dev/lambda/python/latest/utilities/batch/) - Partial failure patterns
- [Python Batch Processing (Hevo)](https://hevodata.com/learn/python-batch-processing/) - Bounded iteration patterns
- [Backtesting.py](https://kernc.github.io/backtesting.py/) - Historical data batch simulation
- [Python Batch Processing with Joblib (2026)](https://johal.in/python-batch-processing-with-joblib-parallel-loky-backends-scheduling-2026/) - Budget exceeded pattern

### Tertiary (LOW confidence)
- [pybreaker Circuit Breaker](https://github.com/danielfm/pybreaker) - Alternative to manual budget tracking (external dependency, not recommended)
- [itertools.batched()](https://www.tutorialspoint.com/python/python_itertools_batched_function.htm) - Fixed-size batch chunking (not needed for Phase 11)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Python stdlib only, no external dependencies
- Architecture: HIGH - Simple extension of Phase 10 ExecutionBudget pattern
- Pitfalls: HIGH - DoS vectors and non-determinism well-understood from Phase 10 research

**Research date:** 2026-01-28
**Valid until:** 2026-02-28 (30 days - stable algorithms, stdlib-based, builds on Phase 10)
