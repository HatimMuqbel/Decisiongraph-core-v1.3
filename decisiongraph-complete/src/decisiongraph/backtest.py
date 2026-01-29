"""
DecisionGraph Core: Batch Backtest Module (v1.6)

BatchBacktestResult dataclass and helpers for batch backtest infrastructure.

Purpose:
- Store immutable results from batch backtesting operations (BAT-01)
- Track execution budget compliance (max_cases, max_runtime_ms, max_cells_touched) (BAT-02)
- Provide deterministic sorting and cell counting utilities (BAT-03)

Key Components:
1. BatchBacktestResult: Frozen dataclass containing batch backtest results
2. _sort_results(): Deterministic sorting by (subject, valid_time, system_time)
3. _count_cells_in_simulation(): Count cells from base and shadow proof bundles

Architecture:
- Follows SimulationResult pattern for immutability (frozen=True)
- Results list is deterministically sorted for reproducibility (BAT-03)
- Execution budget tracking prevents DoS (max_cases, max_runtime_ms, max_cells_touched)
- backtest_incomplete flag signals when limits exceeded (BAT-02)

Example:
    >>> result = BatchBacktestResult(
    ...     results=[sim1, sim2, sim3],
    ...     backtest_incomplete=False,
    ...     cases_processed=3,
    ...     runtime_ms=1234.5,
    ...     cells_touched=150
    ... )
    >>> dict_result = result.to_dict()
"""

from dataclasses import dataclass
from typing import List, Dict, Any

from .simulation import SimulationResult


@dataclass(frozen=True)
class BatchBacktestResult:
    """Immutable batch backtest result (BAT-01, BAT-02, BAT-03).

    Contains list of SimulationResults plus metadata about execution budget.
    Results are deterministically sorted by (subject, valid_time, system_time).

    Attributes:
        results: List of SimulationResults (sorted deterministically - BAT-03)
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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dict."""
        return {
            'results': [r.to_dict() for r in self.results],
            'backtest_incomplete': self.backtest_incomplete,
            'cases_processed': self.cases_processed,
            'runtime_ms': self.runtime_ms,
            'cells_touched': self.cells_touched
        }


def _sort_results(results: List[SimulationResult]) -> List[SimulationResult]:
    """Sort results deterministically (BAT-03).

    Primary key: subject from rfa_dict
    Secondary key: at_valid_time
    Tertiary key: as_of_system_time

    Handles missing subject (defaults to empty string for consistent sorting).

    Args:
        results: List of SimulationResults to sort

    Returns:
        Sorted list (stable sort, reproducible)
    """
    return sorted(
        results,
        key=lambda r: (
            r.rfa_dict.get('subject', ''),  # Primary: subject (default '' if None)
            r.at_valid_time,                # Secondary: valid_time
            r.as_of_system_time             # Tertiary: system_time
        )
    )


def _count_cells_in_simulation(sim_result: SimulationResult) -> int:
    """Count total cells accessed during simulation (BAT-02).

    Used for max_cells_touched limit. Counts cells in:
    - base_result proof_bundle (facts, rules, bridges)
    - shadow_result proof_bundle (facts, rules, bridges)

    Args:
        sim_result: SimulationResult to count cells from

    Returns:
        Total cell count accessed (base + shadow)
    """
    # Count base result cells
    base_results = sim_result.base_result.get('results', {})
    base_cells = len(base_results.get('fact_cell_ids', []))

    base_proof = sim_result.base_result.get('proof', {})
    base_cells += len(base_proof.get('candidate_cell_ids', []))
    base_cells += len(base_proof.get('bridges_used', []))

    # Count shadow result cells
    shadow_results = sim_result.shadow_result.get('results', {})
    shadow_cells = len(shadow_results.get('fact_cell_ids', []))

    shadow_proof = sim_result.shadow_result.get('proof', {})
    shadow_cells += len(shadow_proof.get('candidate_cell_ids', []))
    shadow_cells += len(shadow_proof.get('bridges_used', []))

    return base_cells + shadow_cells


# Export public interface
__all__ = [
    'BatchBacktestResult',
]
