# Technology Stack

**Analysis Date:** 2026-01-27

## Languages

**Primary:**
- Python 3.10+ - Core deterministic reasoning engine; all source code in `src/decisiongraph/`

## Runtime

**Environment:**
- Python 3.10, 3.11, 3.12 (specified in pyproject.toml)

**Package Manager:**
- pip / setuptools
- Lockfile: Not present (uses pinned versions in pyproject.toml optional-dependencies)

## Frameworks

**Core:**
- DecisionGraph (custom) - Deterministic reasoning engine with blockchain-like append-only chain (`src/decisiongraph/`)
- dataclasses (stdlib) - Core data structures (DecisionCell, Header, Fact, LogicAnchor, Evidence, Proof)

**Testing:**
- pytest 7.0+ - Test runner
- pytest-cov - Coverage reporting

**Code Quality:**
- black - Code formatting (line-length: 100)
- mypy - Static type checking (Python 3.10+)

**Build/Dev:**
- setuptools 61.0+ - Package building and distribution
- wheel - Binary package format

## Key Dependencies

**No External APIs or Third-Party Libraries:**

The codebase uses only Python standard library modules:
- `hashlib` - SHA-256 hashing for cell_id computation
- `json` - Cell serialization/deserialization (cell.to_dict(), Chain.to_json())
- `re` - Namespace and timestamp validation with regex patterns
- `uuid` - Graph ID generation (generate_graph_id())
- `dataclasses` - Sealed data structures for DecisionCell, Header, Fact, LogicAnchor, Evidence, Proof
- `datetime` - ISO 8601 timestamp handling (system_time, valid_time)
- `enum` - Cell types and quality levels (CellType, SourceQuality, SensitivityLevel)
- `typing` - Type hints throughout (List, Dict, Optional, Tuple, Set, Any)

## Configuration

**Environment:**
- Environment variables: Not required for core functionality
- Configuration via Python function parameters (chain.initialize(), create_chain())

**Build:**
- `pyproject.toml` - Single source of truth for configuration
  - Package metadata (name: "decisiongraph", version: "1.3.0")
  - Build system (setuptools + wheel)
  - Dev dependencies (pytest, pytest-cov, black, mypy)
  - Tool configurations (pytest, black, mypy)
  - Test paths: `tests/`
  - Source paths: `src/`

**File Configuration:**
- `setup.py` - Not present (uses PEP 660 pyproject.toml instead)
- `.env` files - Not used

## Platform Requirements

**Development:**
- Python 3.10+ with standard library
- pip for package installation
- pytest for running test suite

**Production:**
- Python 3.10+ runtime
- No external service dependencies
- No database required (in-memory Chain, optional JSON serialization)
- Can run in any environment with Python 3.10+

## Architecture Overview

**Self-Contained Design:**
- No external API integrations required
- No database dependencies
- In-memory data structures (Chain, ScholarIndex)
- JSON serialization for persistence (optional)
- Pure Python cryptographic hashing (SHA-256 via hashlib)

**Core Module Structure:**
- `src/decisiongraph/cell.py` - Atomic decision unit with cryptographic sealing
- `src/decisiongraph/chain.py` - Append-only log of cells (Chain of Custody)
- `src/decisiongraph/genesis.py` - Graph initialization (Genesis cell)
- `src/decisiongraph/namespace.py` - Namespace isolation and bridge rules
- `src/decisiongraph/scholar.py` - Query/resolver layer with bitemporal semantics
- `src/decisiongraph/__init__.py` - Public API exports

---

*Stack analysis: 2026-01-27*
