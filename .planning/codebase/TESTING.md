# Testing Patterns

**Analysis Date:** 2026-01-27

## Test Framework

**Runner:**
- pytest 7.0+
- Config: `pyproject.toml` (lines 53-56)
- Python versions: 3.10, 3.11, 3.12

**Configuration:**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v"
```

**Assertion Library:**
- pytest built-in assertions (assert statements)
- pytest.raises() for exception testing

**Run Commands:**
```bash
pytest tests/                              # Run all tests with verbose output (-v)
pytest tests/test_core.py -v              # Run specific test file
pytest tests/ -k "test_cell_id"           # Run tests matching pattern
pytest tests/ --cov=decisiongraph         # Run with coverage (requires pytest-cov)
pytest -x                                  # Stop on first failure
```

## Test File Organization

**Location:**
- Test files placed in `/decisiongraph-complete/tests/` directory
- Separate from source code under `/src/decisiongraph/`
- Convention: Co-located by module name (test_core.py, test_scholar.py, test_commit_gate.py)

**Naming:**
- File: `test_<module>.py` (e.g., `test_core.py`, `test_scholar.py`, `test_commit_gate.py`)
- Class: `Test<Feature>` (e.g., `TestCellIdComputation`, `TestGenesisCell`, `TestChainValidation`)
- Method: `test_<behavior>` (e.g., `test_cell_id_is_deterministic`, `test_cell_id_changes_with_subject`)

**Structure:**
```
tests/
├── test_core.py           # Cell, Genesis, Chain tests (~648 lines)
├── test_scholar.py        # Scholar, query, resolution tests (~300+ lines)
├── test_commit_gate.py    # Chain.append() validation tests (~250+ lines)
└── test_utils.py          # Utility tests
```

**Total test lines:** ~1963 lines across 4 test files

## Test Structure

**Suite Organization:**

Tests are organized by feature/responsibility in classes:
- `TestCellIdComputation`: Tests for cell_id computation (the Logic Seal)
- `TestGenesisCell`: Tests for Genesis cell creation and verification
- `TestChainValidation`: Tests for chain initialization and validation
- `TestInvariants`: Tests for TLA+ invariants
- `TestEdgeCases`: Edge case handling
- `TestCommitGateGraphId`: Cross-graph contamination protection

**Pattern Structure from test_core.py:**

```python
class TestCellIdComputation:
    """Tests for Task 3: cell_id computation (Logic Seal)"""

    def test_cell_id_is_deterministic(self):
        """Same inputs should produce same cell_id"""
        cell1 = self._create_test_cell()
        cell2 = self._create_test_cell()

        assert cell1.cell_id == cell2.cell_id

    def _create_test_cell(
        self,
        subject="entity:test",
        predicate="has_value",
        object_value="TestValue",
        rule_hash="test_hash_123",
        timestamp="2026-01-26T12:00:00Z",
        prev_hash=NULL_HASH
    ):
        """Helper to create test cells"""
        return DecisionCell(
            header=Header(...),
            fact=Fact(...),
            logic_anchor=LogicAnchor(...)
        )
```

**Patterns:**
- Setup: Helpers create test objects (`_create_test_cell`, `_create_linked_cell`)
- Teardown: Minimal (no explicit teardown needed for pure functions)
- Assertions: Single focused assertion per test when possible (e.g., line 51-56)
- Test organization: One test class per feature area
- Test granularity: Very fine-grained, each test is 5-15 lines

## Mocking

**Framework:** No explicit mocking framework (unittest.mock not used)

**Patterns:**
- No mocking detected in codebase
- Instead: Test isolation via immutable dataclasses and factory functions
- Example from test_core.py: Tests create isolated `DecisionCell` instances with specific parameters
- Pure function testing: Functions like `compute_rule_logic_hash`, `verify_integrity` are tested directly with different inputs

**What to Mock:**
- External I/O operations (if any were present): files, network, databases
- Time-dependent operations: Could mock `get_current_timestamp()`, but tests currently use fixed timestamps (e.g., `"2026-01-26T12:00:00Z"`)

**What NOT to Mock:**
- Core domain objects (`DecisionCell`, `Chain`, etc.)
- Validation functions and business logic
- Deterministic hash/ID computations

## Fixtures and Factories

**Test Data Patterns:**
- Factory methods: Helpers return fully-constructed domain objects
- Example from test_core.py line 125-153 (`_create_test_cell`):
```python
def _create_test_cell(
    self,
    subject="entity:test",
    predicate="has_value",
    object_value="TestValue",
    rule_hash="test_hash_123",
    timestamp="2026-01-26T12:00:00Z",
    prev_hash=NULL_HASH
):
    """Helper to create test cells"""
    return DecisionCell(
        header=Header(
            version="1.0",
            cell_type=CellType.FACT,
            timestamp=timestamp,
            prev_cell_hash=prev_hash
        ),
        fact=Fact(
            subject=subject,
            predicate=predicate,
            object=object_value,
            confidence=0.95,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="test:rule",
            rule_logic_hash=rule_hash
        )
    )
```

- Parameters: Helpers accept flexible parameters with sensible defaults
- Reuse: Same helpers used across multiple test methods (e.g., `_create_test_cell` used in 8+ test methods)
- Location: Defined as methods on test classes (not separate module)

**Constants:**
- `NULL_HASH`: Imported from cell module
- Test timestamps: Hardcoded ISO-8601 strings (e.g., `"2026-01-26T12:00:00Z"`)
- Test identifiers: Strings like `"entity:test"`, `"test:rule"`, `"test_hash_123"`

## Coverage

**Requirements:**
- None enforced (no `--cov-fail-under` in pytest config)
- Coverage package available via optional dev dependencies: `pytest-cov` (line 37 of pyproject.toml)

**View Coverage:**
```bash
pytest tests/ --cov=decisiongraph --cov-report=term-missing
pytest tests/ --cov=decisiongraph --cov-report=html
```

## Test Types

**Unit Tests:**
- Scope: Individual functions and methods
- Approach: Test deterministic behavior with fixed inputs
- Examples:
  - `test_cell_id_is_deterministic` (test_core.py line 51-56)
  - `test_verify_integrity_passes_for_valid_cell` (test_core.py line 107-111)
  - `test_validate_valid_chain` (test_core.py line 314-327)

**Integration Tests:**
- Scope: Multiple components working together
- Approach: Build chains, namespaces, and verify end-to-end behavior
- Examples:
  - `test_scholar_conflict_resolution_deterministic` (test_scholar.py line 41-175+): Creates chain, adds cells, builds scholar, queries, verifies consistency
  - `test_json_roundtrip` (test_core.py line 411-427): Serializes and deserializes chain
  - `test_trace_to_genesis` (test_core.py line 329-343): Traces cell references back to genesis

**E2E Tests:**
- Framework: Not explicitly labeled, but test_scholar.py contains full workflow tests
- Example: Scholar conflict resolution test creates graph, namespaces, facts, scholars, and validates deterministic results
- Approach: Uses print statements for visibility (e.g., `print(f"✓ Added salary fact 1...")`) typical of demonstration/acceptance tests

## Common Patterns

**Determinism Testing:**
Tests verify that same inputs produce same outputs across multiple runs (critical for consensus):
```python
def test_cell_id_is_deterministic(self):
    """Same inputs should produce same cell_id"""
    cell1 = self._create_test_cell()
    cell2 = self._create_test_cell()

    assert cell1.cell_id == cell2.cell_id
```

**Invariant Testing:**
Tests validate TLA+ formal specification invariants (test_core.py lines 459-570):
- INVARIANT 1: All cells must have valid cell_id (test_invariant_atomic_integrity)
- INVARIANT 2: Exactly one Genesis cell (test_invariant_genesis_uniqueness)
- INVARIANT 3: Chain of custody - all cells point to existing prev_cell_hash (test_invariant_chain_of_custody)
- INVARIANT 4: Only Genesis has NULL_HASH (test_invariant_null_hash_only_genesis)
- INVARIANT 6: Confidence 1.0 requires verified source (test_invariant_source_quality_ordering)

**Exception Testing:**
Uses `pytest.raises()` context manager:
```python
def test_cannot_reinitialize(self):
    """Should raise error if trying to reinitialize"""
    chain = create_chain()

    with pytest.raises(GenesisViolation):
        chain.initialize()
```

**Async Testing:**
Not applicable - pure synchronous code

**Error Testing:**
Validates error conditions and boundary cases:
```python
def test_confidence_boundaries(self):
    """Should enforce confidence bounds"""
    with pytest.raises(ValueError):
        Fact(
            subject="test",
            predicate="test",
            object="test",
            confidence=1.1,  # Invalid
            source_quality=SourceQuality.VERIFIED
        )
```

**Graph Isolation Testing:**
Critical tests for cross-graph contamination protection (test_commit_gate.py):
```python
def test_reject_cross_graph_contamination(self):
    """
    CRITICAL TEST: Cells from different graphs must be rejected.
    """
    chain = create_chain(graph_name="GraphA", root_namespace="grapha")
    graph_id_a = chain.graph_id

    graph_id_b = generate_graph_id()  # Different graph
    foreign_cell = DecisionCell(
        header=Header(
            ...
            graph_id=graph_id_b,  # WRONG GRAPH
            ...
        ),
        ...
    )

    with pytest.raises(GraphIdMismatch):
        chain.append(foreign_cell)
```

## Test Imports Pattern

**Standard import structure from test files:**
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from decisiongraph import (
    # Cell primitives
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Evidence,
    Proof,
    CellType,
    SourceQuality,
    NULL_HASH,
    compute_rule_logic_hash,

    # Genesis
    create_genesis_cell,
    verify_genesis,
    GENESIS_RULE_HASH,

    # Chain
    Chain,
    create_chain,
    IntegrityViolation,
    ChainBreak,
    GenesisViolation,
    TemporalViolation
)
```

---

*Testing analysis: 2026-01-27*
