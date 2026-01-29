"""
DecisionGraph Core: Anchor Detection Module (v1.6)

Counterfactual anchor detection for identifying minimal shadow modifications
causing verdict delta.

Purpose:
- Detect minimal set of shadow components that cause simulation outcome to change
- Use bounded greedy ablation algorithm to prevent DoS (CTF-02)
- Return incomplete results when execution budget exceeded (CTF-04)
- Provide deterministic anchor hashing for reproducibility (CTF-01)

Key Components:
1. ExecutionBudget: Mutable tracker for bounded execution (attempts + time)
2. AnchorResult: Frozen dataclass for immutable anchor detection results
3. compute_anchor_hash(): Deterministic SHA-256 hash of anchor set
4. detect_counterfactual_anchors(): Greedy ablation algorithm for anchor detection

Architecture:
- Greedy iterative ablation: Start with all components, remove one at a time
- Test each subset via engine.simulate_rfa() to check if verdict delta persists
- Stop when budget exceeded (max_attempts or max_runtime_ms)
- Return minimal subset that still causes verdict delta

Example:
    >>> budget = ExecutionBudget(max_attempts=100, max_runtime_ms=5000)
    >>>
    >>> for subset in generate_subsets(components):
    ...     if budget.is_exceeded():
    ...         return AnchorResult(anchors=current_best, anchors_incomplete=True, ...)
    ...     test_result = engine.simulate_rfa(...)
    ...     budget.increment()
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, TYPE_CHECKING
import time
import json
import hashlib
import itertools
import copy

if TYPE_CHECKING:
    from .engine import Engine


class ExecutionBudget:
    """
    Mutable tracker for bounded execution (CTF-02).

    Tracks both attempt count and elapsed time to prevent DoS via
    unbounded anchor search. Search stops when either limit exceeded.

    Attributes:
        max_attempts: Maximum simulation attempts allowed
        max_runtime_ms: Maximum runtime in milliseconds
        attempts: Current attempt count (incremented via increment())
        start_time: Timestamp when budget created (time.time())

    Usage:
        budget = ExecutionBudget(max_attempts=100, max_runtime_ms=5000)

        for subset in generate_subsets(components):
            if budget.is_exceeded():
                return partial_results(anchors_incomplete=True)

            result = test_subset(subset)
            budget.increment()
    """

    def __init__(self, max_attempts: int, max_runtime_ms: int):
        """
        Initialize ExecutionBudget.

        Args:
            max_attempts: Maximum number of simulation attempts
            max_runtime_ms: Maximum runtime in milliseconds
        """
        self.max_attempts = max_attempts
        self.max_runtime_ms = max_runtime_ms
        self.attempts = 0
        self.start_time = time.time()

    def is_exceeded(self) -> bool:
        """
        Check if execution budget exceeded.

        Returns True if either:
        - attempts >= max_attempts
        - elapsed_ms() >= max_runtime_ms

        Returns:
            True if budget exceeded, False otherwise
        """
        if self.attempts >= self.max_attempts:
            return True

        if self.elapsed_ms() >= self.max_runtime_ms:
            return True

        return False

    def increment(self):
        """Increment attempt counter."""
        self.attempts += 1

    def elapsed_ms(self) -> float:
        """
        Get elapsed time since budget created.

        Returns:
            Elapsed time in milliseconds
        """
        return (time.time() - self.start_time) * 1000


@dataclass(frozen=True)
class AnchorResult:
    """
    Immutable counterfactual anchor detection result (CTF-03, CTF-04).

    Contains minimal set of shadow modifications that cause verdict delta,
    along with metadata about the search process.

    Attributes:
        anchors: List of (component_type, cell_id) tuples representing minimal set
        anchors_incomplete: True if budget exceeded before completing search (CTF-04)
        attempts_used: Number of simulations run during anchor detection
        runtime_ms: Actual runtime in milliseconds
        anchor_hash: SHA-256 hash of sorted anchors for deduplication (CTF-01)

    Usage:
        result = AnchorResult(
            anchors=[('rule', 'cell-abc'), ('fact', 'cell-xyz')],
            anchors_incomplete=False,
            attempts_used=42,
            runtime_ms=1234.5,
            anchor_hash="abc123..."
        )

        # Convert to serializable dict
        dict_result = result.to_dict()
    """
    anchors: List[Tuple[str, str]]  # [(component_type, cell_id), ...]
    anchors_incomplete: bool        # True if budget exceeded (CTF-04)
    attempts_used: int              # Simulations run during search
    runtime_ms: float               # Actual runtime
    anchor_hash: str                # SHA-256 of sorted anchors (CTF-01)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to serializable dict.

        Returns:
            Dict with all fields, anchors expanded to dicts with component_type and cell_id
        """
        return {
            'anchors': [
                {'component_type': ctype, 'cell_id': cid}
                for (ctype, cid) in self.anchors
            ],
            'anchors_incomplete': self.anchors_incomplete,
            'attempts_used': self.attempts_used,
            'runtime_ms': self.runtime_ms,
            'anchor_hash': self.anchor_hash
        }


def compute_anchor_hash(anchors: List[Tuple[str, str]]) -> str:
    """
    Compute deterministic SHA-256 hash of anchor set (CTF-01).

    Uses sorted JSON representation to ensure same anchors always
    produce same hash (reproducibility). Anchors in any order will
    produce identical hash.

    Args:
        anchors: List of (component_type, cell_id) tuples

    Returns:
        SHA-256 hash as 64-character hex string

    Example:
        >>> anchors1 = [('rule', 'cell-abc'), ('fact', 'cell-xyz')]
        >>> anchors2 = [('fact', 'cell-xyz'), ('rule', 'cell-abc')]
        >>> compute_anchor_hash(anchors1) == compute_anchor_hash(anchors2)
        True
    """
    # Sort anchors deterministically
    sorted_anchors = sorted(anchors)

    # Canonical JSON with sorted keys
    canonical_json = json.dumps(sorted_anchors, sort_keys=True)

    # SHA-256 hash
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()


def _build_simulation_spec_from_subset(
    original_spec: Dict[str, Any],
    subset_components: List[Tuple[str, str]]
) -> Dict[str, Any]:
    """
    Build simulation spec containing only subset components.

    Helper for iterative ablation - filters original_spec to include
    only components in subset_components. Deep copies to avoid mutating
    original spec.

    Args:
        original_spec: Full simulation spec with all shadow modifications
        subset_components: List of (component_type, cell_id) to keep

    Returns:
        New simulation spec with only subset components
    """
    # Deep copy to avoid mutating original
    subset_spec = copy.deepcopy(original_spec)

    # Build lookup set for fast filtering
    subset_ids = {cid for (ctype, cid) in subset_components}

    # Filter shadow_facts
    subset_spec['shadow_facts'] = [
        f for f in subset_spec.get('shadow_facts', [])
        if f['base_cell_id'] in subset_ids
    ]

    # Filter shadow_rules
    subset_spec['shadow_rules'] = [
        r for r in subset_spec.get('shadow_rules', [])
        if r['base_cell_id'] in subset_ids
    ]

    # Filter shadow_policy_heads
    subset_spec['shadow_policy_heads'] = [
        p for p in subset_spec.get('shadow_policy_heads', [])
        if p['base_cell_id'] in subset_ids
    ]

    # Filter shadow_bridges
    subset_spec['shadow_bridges'] = [
        b for b in subset_spec.get('shadow_bridges', [])
        if b['base_cell_id'] in subset_ids
    ]

    return subset_spec


def detect_counterfactual_anchors(
    engine: 'Engine',
    rfa_dict: Dict[str, Any],
    base_result: Dict[str, Any],
    simulation_spec: Dict[str, Any],
    at_valid_time: str,
    as_of_system_time: str,
    max_anchor_attempts: int = 100,
    max_runtime_ms: int = 5000
) -> AnchorResult:
    """
    Detect minimal set of shadow modifications causing verdict delta (CTF-03).

    Algorithm: Greedy iterative ablation
    1. Extract all shadow component IDs from simulation_spec (sorted - CTF-01)
    2. For each subset (largest to smallest):
       - Create modified simulation_spec with only that subset
       - Re-run simulation via engine.simulate_rfa()
       - If verdict still changes, this is a potential anchor
       - If verdict doesn't change, this subset is not an anchor
    3. Return minimal subset that preserves verdict delta

    Bounded execution (CTF-02, CTF-04):
    - max_anchor_attempts: Stop after N simulation attempts
    - max_runtime_ms: Stop after timeout exceeded
    - Return anchors_incomplete=True if budget exceeded

    Args:
        engine: Engine instance for re-running simulations
        rfa_dict: Original RFA dict
        base_result: Original base query result (for comparison)
        simulation_spec: Original simulation spec with all shadow modifications
        at_valid_time: Valid time coordinate (ISO 8601 UTC)
        as_of_system_time: System time coordinate (ISO 8601 UTC)
        max_anchor_attempts: Max simulation attempts before giving up (CTF-02)
        max_runtime_ms: Max runtime in milliseconds before timeout (CTF-02)

    Returns:
        AnchorResult with:
        - anchors: List of (component_type, cell_id) tuples
        - anchors_incomplete: True if budget exceeded (CTF-04)
        - attempts_used: Number of simulations run
        - runtime_ms: Actual runtime
        - anchor_hash: SHA-256 of sorted anchors (CTF-01)

    Example:
        >>> result = detect_counterfactual_anchors(
        ...     engine=engine,
        ...     rfa_dict={"namespace": "corp.hr", ...},
        ...     base_result={...},
        ...     simulation_spec={"shadow_facts": [...], "shadow_rules": [...]},
        ...     at_valid_time="2025-01-01T00:00:00Z",
        ...     as_of_system_time="2025-01-01T00:00:00Z"
        ... )
        >>> print(result.anchors)
        [('rule', 'cell-abc'), ('fact', 'cell-xyz')]
        >>> print(result.anchors_incomplete)
        False
    """
    # Create execution budget tracker
    budget = ExecutionBudget(max_anchor_attempts, max_runtime_ms)

    # Extract shadow component IDs (sorted for determinism - CTF-01)
    shadow_facts = sorted(
        [f['base_cell_id'] for f in simulation_spec.get('shadow_facts', [])]
    )
    shadow_rules = sorted(
        [r['base_cell_id'] for r in simulation_spec.get('shadow_rules', [])]
    )
    shadow_policy_heads = sorted(
        [p['base_cell_id'] for p in simulation_spec.get('shadow_policy_heads', [])]
    )
    shadow_bridges = sorted(
        [b['base_cell_id'] for b in simulation_spec.get('shadow_bridges', [])]
    )

    # Combine all shadow components (deterministic order)
    all_components = (
        [('fact', cid) for cid in shadow_facts] +
        [('rule', cid) for cid in shadow_rules] +
        [('policy', cid) for cid in shadow_policy_heads] +
        [('bridge', cid) for cid in shadow_bridges]
    )

    # Edge case: No shadow modifications = no anchors
    if not all_components:
        return AnchorResult(
            anchors=[],
            anchors_incomplete=False,
            attempts_used=0,
            runtime_ms=0.0,
            anchor_hash=compute_anchor_hash([])
        )

    # Greedy search: Start with full set, remove components until delta disappears
    # Try subsets from largest to smallest (more likely to preserve delta)
    minimal_anchor = all_components.copy()

    for size in range(len(all_components) - 1, 0, -1):
        # Check execution bounds (CTF-02, CTF-04)
        if budget.is_exceeded():
            # Timeout - return partial results with anchors_incomplete=True
            return AnchorResult(
                anchors=sorted(minimal_anchor),
                anchors_incomplete=True,
                attempts_used=budget.attempts,
                runtime_ms=budget.elapsed_ms(),
                anchor_hash=compute_anchor_hash(sorted(minimal_anchor))
            )

        # Try removing one component at a time
        for subset in itertools.combinations(all_components, size):
            # Check bounds again (inner loop can be long)
            if budget.is_exceeded():
                return AnchorResult(
                    anchors=sorted(minimal_anchor),
                    anchors_incomplete=True,
                    attempts_used=budget.attempts,
                    runtime_ms=budget.elapsed_ms(),
                    anchor_hash=compute_anchor_hash(sorted(minimal_anchor))
                )

            # Build simulation spec with only this subset
            test_spec = _build_simulation_spec_from_subset(
                simulation_spec, list(subset)
            )

            # Re-run simulation
            test_result = engine.simulate_rfa(
                rfa_dict, test_spec, at_valid_time, as_of_system_time
            )
            budget.increment()

            # Check if verdict still changes
            if test_result.delta_report.verdict_changed:
                # This smaller subset still causes delta - update minimal_anchor
                minimal_anchor = list(subset)
                break  # Found smaller anchor, try even smaller

    # Return minimal anchor (deterministic, sorted)
    sorted_anchors = sorted(minimal_anchor)
    return AnchorResult(
        anchors=sorted_anchors,
        anchors_incomplete=False,
        attempts_used=budget.attempts,
        runtime_ms=budget.elapsed_ms(),
        anchor_hash=compute_anchor_hash(sorted_anchors)
    )


# Export public interface
__all__ = [
    'ExecutionBudget',
    'AnchorResult',
    'compute_anchor_hash',
    'detect_counterfactual_anchors',
]
