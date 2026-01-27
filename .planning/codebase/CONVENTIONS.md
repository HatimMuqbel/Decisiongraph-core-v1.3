# Coding Conventions

**Analysis Date:** 2026-01-27

## Naming Patterns

**Files:**
- Module files: `snake_case.py` (e.g., `cell.py`, `genesis.py`, `chain.py`, `namespace.py`, `scholar.py`)
- Test files: `test_<module>.py` (e.g., `test_core.py`, `test_scholar.py`, `test_commit_gate.py`)
- One module per file, clear responsibility separation

**Functions:**
- Function names: `snake_case` (e.g., `validate_namespace`, `create_genesis_cell`, `verify_integrity`)
- Factory functions: `create_<entity>` (e.g., `create_genesis_cell`, `create_chain`, `create_scholar`)
- Verification functions: `verify_<entity>` (e.g., `verify_genesis`, `verify_integrity`)
- Validation functions: `validate_<entity>` (e.g., `validate_namespace`, `validate_timestamp`)
- Predicate/query functions: `is_<state>` or `get_<data>` (e.g., `is_genesis`, `get_current_timestamp`, `get_parent_namespace`)
- Computation functions: `compute_<value>` (e.g., `compute_cell_id`, `compute_rule_logic_hash`, `compute_content_id`)

**Variables:**
- Variable names: `snake_case` (e.g., `prev_cell_hash`, `system_time`, `source_quality`)
- Constants: `UPPER_CASE` (e.g., `NULL_HASH`, `NAMESPACE_PATTERN`, `GENESIS_RULE_HASH`)
- Private attributes: Prefixed with underscore for internal methods (e.g., `_create_test_cell`)
- Iteration variables: Use descriptive names or single letters for range loops (e.g., `for i in range(5)`, `for cell in chain`)

**Types:**
- Dataclasses: `PascalCase` (e.g., `DecisionCell`, `Header`, `Fact`, `LogicAnchor`, `Evidence`, `Proof`)
- Enums: `PascalCase` (e.g., `CellType`, `SourceQuality`, `SensitivityLevel`, `ResolutionReason`, `Permission`, `BridgeStatus`)
- Exception classes: `PascalCase` ending with `Error` or `Exception` (e.g., `ChainError`, `GenesisError`, `IntegrityViolation`, `ChainBreak`, `GraphIdMismatch`)
- Type hints: Full module imports (e.g., `Optional[str]`, `List[DecisionCell]`, `Dict[str, str]`)

## Code Style

**Formatting:**
- Tool: Black (configured in `pyproject.toml`)
- Line length: 100 characters
- Python version targets: 3.10, 3.11, 3.12

**Linting:**
- Tool: Configured for mypy in `pyproject.toml`
- Strictness: `warn_return_any = true`, `warn_unused_configs = true`
- Type checking: Full type hints expected on function signatures and class attributes

**Configuration in `pyproject.toml`:**
```toml
[tool.black]
line-length = 100
target-version = ['py310', 'py311', 'py312']

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
```

## Import Organization

**Order:**
1. Standard library imports (hashlib, json, re, uuid, dataclasses, datetime, enum, typing)
2. Third-party imports (none in core)
3. Relative imports from local modules (from .cell import ..., from .chain import ...)

**Pattern:**
- Use explicit imports, not wildcard imports
- Group by category with blank lines between groups
- Example from `cell.py`:
```python
import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any
```

- Example from `genesis.py`:
```python
import re
from typing import Optional, Tuple, List

from .cell import (
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Proof,
    CellType,
    SourceQuality,
    NULL_HASH,
    get_current_timestamp,
    compute_rule_logic_hash,
    generate_graph_id,
    validate_root_namespace,
    validate_timestamp,
    canonicalize_rule_content
)
```

**Path Aliases:**
- No path aliases defined; uses standard relative imports (`.module`)
- Cross-module imports use explicit single-dot relative imports

## Error Handling

**Patterns:**
- Custom exception hierarchy: Define module-specific exceptions that inherit from `Exception` or `ChainError`
- Validation errors: Raise `ValueError` for invalid input (e.g., `ValueError("Invalid namespace format...")`)
- Operational errors: Raise custom exceptions (e.g., `GenesisViolation`, `ChainBreak`, `IntegrityViolation`)
- Exceptions include descriptive messages with context (see `cell.py` line 224-227)
- Strict validation in `__post_init__` for dataclasses to catch errors at construction time

**Exception Examples from codebase:**
- `cell.py` line 224-227: Timestamp validation with detailed error message
- `cell.py` line 264-268: Namespace validation with example
- `cell.py` line 509-513: Cell integrity verification with tampering detection
- `chain.py` line 39-66: Custom exception hierarchy for chain operations
- `genesis.py` line 100-109: Custom `GenesisValidationError` with detailed checks

## Logging

**Framework:** None detected - no logging framework used

**Patterns:**
- No formal logging (no imports of `logging` module observed)
- Testing uses `print()` for debug output (e.g., test_scholar.py line 46-48, 102)
- Production code relies on exceptions for error reporting
- Note: This is a library; callers are expected to implement their own logging

## Comments

**When to Comment:**
- Module-level docstrings: Always present, explain purpose and key concepts
- Function docstrings: Always present for public functions, use triple quotes with description, args, returns, raises
- Class docstrings: Always present for dataclasses and custom classes
- Inline comments: Used for complex logic or non-obvious code (e.g., `cell.py` line 406-418 for cell_id computation)
- Section dividers: Used to organize large modules into logical sections (e.g., `# ============================================================================`)

**JSDoc/TSDoc:**
- Python uses docstrings (not JSDoc)
- Format: Triple-quoted strings with description, Args/Returns/Raises sections
- Example from `cell.py`:
```python
def verify_integrity(self) -> bool:
    """
    Verify that the cell_id matches the computed hash.

    Returns True if cell is valid, False if tampered.
    """
    return self.cell_id == self.compute_cell_id()
```

## Function Design

**Size:** Functions are kept focused on a single responsibility
- Most validation/factory functions: 10-30 lines
- Complex functions with multiple steps: Up to 50-60 lines (e.g., `verify_genesis` in genesis.py)
- Test helper methods: 5-20 lines

**Parameters:**
- Parameters use clear, descriptive names
- Optional parameters use `Optional[Type]` with defaults (e.g., `system_time: Optional[str] = None`)
- Factory functions accept multiple keyword args for configuration (e.g., `create_genesis_cell`)
- Parameters ordered: required first, optional with defaults last

**Return Values:**
- Single return value: Return directly
- Multiple related values: Return dataclass or tuple (e.g., `verify_genesis()` returns `Tuple[bool, List[str]]`)
- Success/failure: Return bool for simple cases, custom type with metadata for complex cases
- Query results: Return custom dataclass with metadata (e.g., `QueryResult` in scholar.py)

## Module Design

**Exports:**
- Explicit `__all__` list at end of each module defining public API
- Examples:
  - `cell.py` lines 519-557: Exports primitives, enums, validation functions, utilities
  - `__init__.py` lines 108-138: Re-exports all public symbols for unified API
  - Only public functions/classes exported; internal helpers remain unprefixed but not in `__all__`

**Barrel Files:**
- `__init__.py` (line 108-138): Central barrel file that re-exports from submodules
- Pattern: Import from submodules, add to `__all__`, makes entire API available as `from decisiongraph import X`
- Groups exports by category with comments (Cell, Genesis, Chain, Namespace, Scholar)

---

*Convention analysis: 2026-01-27*
