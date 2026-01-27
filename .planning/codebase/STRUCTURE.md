# Codebase Structure

**Analysis Date:** 2026-01-27

## Directory Layout

```
decisiongraph-complete/
├── README.md                    # Quick start and overview
├── pyproject.toml              # Package metadata, build config, pytest/black config
├── docs/
│   ├── ARCHITECTURE.md         # Detailed architecture documentation
│   ├── GENESIS_CHECKLIST.md    # 22-point Genesis verification checklist
│   ├── SCHEMA_V1.3.md          # Complete schema specification
│   └── ROADMAP.md              # Future development plan
├── specs/
│   ├── DecisionGraph.tla       # TLA+ formal specification (14 invariants)
│   └── DecisionGraphV2.tla     # TLA+ spec with namespace invariants
├── src/
│   └── decisiongraph/
│       ├── __init__.py         # Public API exports (all module-level symbols)
│       ├── cell.py             # Cell primitives (DecisionCell, Header, Fact, etc.)
│       ├── genesis.py          # Genesis creation and verification
│       ├── chain.py            # Chain container and Commit Gate
│       ├── namespace.py        # Namespace registry and access rules
│       └── scholar.py          # Query resolver and conflict resolution
├── tests/
│   ├── test_core.py            # Cell ID, Genesis, integrity tests
│   ├── test_scholar.py         # Query resolver tests
│   ├── test_commit_gate.py     # Chain validation tests
│   └── test_utils.py           # Utility function tests
├── demo.py                      # Basic demonstration of all 4 tasks
└── demo_corporate.py            # Corporate use case with namespaces
```

## Directory Purposes

**`src/decisiongraph/`:**
- Purpose: Core library code - production-ready modules
- Contains: Five modules implementing storage, governance, and reasoning layers
- Key files: `cell.py` (400+ lines), `chain.py` (568 lines), `genesis.py` (630 lines), `namespace.py` (335 lines), `scholar.py` (630+ lines)

**`tests/`:**
- Purpose: Test suite for all modules
- Contains: Unit tests covering cell creation, Genesis verification, chain validation, query resolution
- Key files: `test_core.py` (cell/Genesis tests), `test_commit_gate.py` (chain validation), `test_scholar.py` (query logic)
- Pattern: pytest framework; conftest available for fixtures; CLI: `pytest tests/ -v`

**`docs/`:**
- Purpose: Reference documentation beyond code
- Contains: Detailed architecture notes, Genesis checklist, complete schema, roadmap
- Usage: Referenced by maintainers and consumers for understanding design decisions

**`specs/`:**
- Purpose: Formal specification in TLA+ (temporal logic)
- Contains: 14 invariants for Task 1 (v1 spec); namespace invariants for v2
- Usage: Reference for verification; not executable in this repo (TLA+ is language, not code)

**`demo.py`:**
- Purpose: Minimal demonstration of core functionality
- Location: `/workspaces/Decisiongraph-core-v1.3/decisiongraph-complete/demo.py`
- Usage: Run with `python demo.py` from repo root to see Genesis creation, cell ID computation, chain validation

**`demo_corporate.py`:**
- Purpose: Corporate use case with namespace hierarchies and bridges
- Location: `/workspaces/Decisiongraph-core-v1.3/decisiongraph-complete/demo_corporate.py`
- Usage: Demonstrates multi-department setup with cross-namespace access

## Key File Locations

**Entry Points:**

- `src/decisiongraph/__init__.py`: Public API - all exported classes, functions, constants (lines 1-138)
- `src/decisiongraph/chain.py:create_chain()`: Factory for new chains (lines 532-554)
- `src/decisiongraph/genesis.py:create_genesis_cell()`: Factory for Genesis (lines 120-180+)

**Configuration:**

- `pyproject.toml`: Python version (>=3.10), dependencies, pytest settings, black line length (100 chars)
- No environment variables or .env files used; configuration via function parameters

**Core Logic:**

- `src/decisiongraph/cell.py`: Cell definition, hashing, validation (lines 206-515)
- `src/decisiongraph/chain.py`: Chain container, append validation (lines 102-530)
- `src/decisiongraph/genesis.py`: Bootstrap with 22-point verification (lines 80-300+)
- `src/decisiongraph/namespace.py`: Access control, bridge rules (lines 100-335)
- `src/decisiongraph/scholar.py`: Query resolver, conflict resolution (lines 200-630+)

**Testing:**

- `tests/test_core.py`: Cell integrity, Genesis creation, temporal validation
- `tests/test_scholar.py`: Query logic, authorization checks, conflict resolution
- `tests/test_commit_gate.py`: Chain validation, invariant enforcement
- `tests/test_utils.py`: Utility functions (namespace validation, hashing)

## Naming Conventions

**Files:**

- Module files: lowercase with underscores (e.g., `cell.py`, `namespace.py`)
- Test files: `test_*.py` pattern (e.g., `test_core.py`)
- Demo files: `demo*.py` pattern (e.g., `demo_corporate.py`)
- Config: `pyproject.toml` (setuptools standard)
- Docs: UPPERCASE.md (e.g., `ARCHITECTURE.md`)

**Directories:**

- Package: lowercase (e.g., `src/decisiongraph/`)
- Test directory: `tests/` (plural)
- Docs: `docs/`, `specs/` (plural)
- Build output: `build/`, `dist/` (generated, not committed)

**Python Symbols:**

- **Classes**: PascalCase (e.g., `DecisionCell`, `Header`, `Chain`, `Scholar`)
- **Functions**: snake_case (e.g., `create_chain()`, `verify_genesis()`, `compute_rule_logic_hash()`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `NULL_HASH`, `NAMESPACE_PATTERN`, `GENESIS_RULE`)
- **Enums**: PascalCase class, UPPER_SNAKE_CASE values (e.g., `class CellType(str, Enum)`, `CellType.GENESIS`)
- **Private**: Single underscore prefix (e.g., `_graph_id`, `_root_namespace` in Chain)
- **Type hints**: Used throughout; Optional, List, Dict, Tuple imported from typing

## Where to Add New Code

**New Feature (e.g., Simulation Engine):**
- Primary code: `src/decisiongraph/simulator.py` (new module in same package)
- Tests: `tests/test_simulator.py` (follow existing pattern)
- Exports: Add to `__init__.py` __all__ list
- Documentation: Add to `docs/ARCHITECTURE.md` with new layer description

**New Cell Type:**
- Add enum value to `CellType` in `src/decisiongraph/cell.py` (line 32-42)
- Add verification logic to `genesis.py` if Genesis-specific
- Add test in `tests/test_core.py` for new cell type
- Update `README.md` cell types table (line 203-215)

**New Access Control Feature:**
- Primary code: `src/decisiongraph/namespace.py` (extend NamespaceRegistry, Permission, or Signature)
- Add cell type to `CellType` enum if new cell type needed
- Add tests to `tests/test_scholar.py` for authorization logic
- Update narrative in `docs/ARCHITECTURE.md`

**Utility Functions:**
- Shared helpers: `src/decisiongraph/cell.py` if cell-related (e.g., `compute_rule_logic_hash()` at line 176)
- Or new module `src/decisiongraph/utils.py` if independent
- Test in corresponding `test_` file

**Database/Persistence (Future):**
- Do NOT add to `src/decisiongraph/` (violates "garden grows from own soil" philosophy)
- Create separate package `decisiongraph-storage` with adapters (JSON, SQLite, etc.)
- Implement `Chain.to_json()` / `Chain.from_json()` pattern (already exists at line 511-529)

## Special Directories

**`src/decisiongraph/__pycache__/`:**
- Purpose: Python compiled bytecode cache
- Generated: Yes (automatic by Python)
- Committed: No (.gitignore excludes)

**`build/`, `dist/`:**
- Purpose: Package build artifacts
- Generated: Yes (`python -m build`)
- Committed: No (.gitignore excludes)

**`.tox/`, `.pytest_cache/`:**
- Purpose: Test runner caches
- Generated: Yes (pytest, tox create automatically)
- Committed: No (.gitignore excludes)

**`*.egg-info/`:**
- Purpose: Package metadata created by setuptools
- Generated: Yes (automatic during `pip install -e .`)
- Committed: No (.gitignore excludes)

## Module Dependencies (Import Graph)

```
__init__.py (public API facade)
├─→ cell.py (primitives: DecisionCell, Header, Fact, etc.)
├─→ genesis.py (uses: cell, NULL_HASH, compute_rule_logic_hash)
├─→ chain.py (uses: cell, genesis, DecisionCell)
├─→ namespace.py (uses: cell, validate_namespace, DecisionCell)
└─→ scholar.py (uses: cell, chain, namespace, NamespaceRegistry)
```

**No Circular Dependencies**: Each module only imports from modules listed above it.

**External Dependencies**: None for core functionality (pure Python standard library).

**Optional Dependencies** (dev only): pytest, black, mypy (in pyproject.toml).

## Module-to-File Mapping

| Public Name | File | Lines | Primary Content |
|-------------|------|-------|-----------------|
| `DecisionCell`, `Header`, `Fact` | `cell.py` | 1-557 | Core data structures + hashing |
| `Chain`, `create_chain` | `chain.py` | 1-569 | Container + append validation |
| `create_genesis_cell`, `verify_genesis` | `genesis.py` | 1-630+ | Bootstrap + verification |
| `NamespaceRegistry`, `Permission` | `namespace.py` | 1-335 | Access control + bridges |
| `Scholar`, `QueryResult` | `scholar.py` | 1-630+ | Query resolver + conflict logic |

---

*Structure analysis: 2026-01-27*
