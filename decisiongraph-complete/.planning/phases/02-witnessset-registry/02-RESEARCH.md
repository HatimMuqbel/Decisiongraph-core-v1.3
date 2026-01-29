# Phase 2: WitnessSet Registry - Research

**Researched:** 2026-01-28
**Domain:** Registry/lookup data structures for namespace-based WitnessSet management
**Confidence:** HIGH

## Summary

Phase 2 builds a **WitnessSet Registry** that provides namespace → WitnessSet lookup. The registry enables namespaces to have configurable witness sets with threshold rules governing promotion approval.

**Key findings:**
- Python's built-in `dict` is optimal for namespace → WitnessSet lookup (80% faster than OrderedDict for basic lookups)
- WitnessSet should be a frozen dataclass (immutable, hashable, deterministic)
- Phase 1 already provides threshold validation and Genesis WitnessSet embedding - Phase 2 extends this with runtime lookup
- Registry must be append-only and derived from Chain state (not in-memory cache)
- Bootstrap paradox is already solved: Genesis embeds initial WitnessSet

**Primary recommendation:** Implement WitnessRegistry as a stateless query layer over Chain, using `dict` for O(1) namespace lookups. WitnessSet changes append new cells to Chain; registry rebuilds from Chain on demand.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| dataclasses | Python 3.10+ stdlib | Define immutable WitnessSet | Built-in, frozen support, zero dependencies |
| typing | Python 3.10+ stdlib | Type hints for registry interfaces | Native Python type safety |
| dict | Python 3.10+ stdlib | Namespace → WitnessSet lookup | 80% faster than OrderedDict, guaranteed insertion order in Python 3.7+ |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 7.4+ | Unit testing | Already in project (618 tests passing) |
| json | stdlib | WitnessSet serialization | Already used in Genesis (fact.object) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| dict | OrderedDict | Explicit ordering but 80% slower for lookups; unnecessary since dict preserves insertion order in Python 3.7+ |
| dict | Custom registry class | More complexity; dict is sufficient for namespace keys |
| Mutable class | Frozen dataclass | Mutable allows tampering; frozen ensures immutability and hashability |

**Installation:**
```bash
# No additional dependencies needed - all stdlib
# Project already has pytest for testing
```

## Architecture Patterns

### Recommended Project Structure
```
src/decisiongraph/
├── witnessset.py        # WitnessSet dataclass + validation
├── registry.py          # WitnessRegistry (namespace → WitnessSet lookup)
├── policyhead.py        # (exists) threshold validation functions
├── genesis.py           # (exists) Genesis WitnessSet embedding
└── chain.py             # (exists) append-only storage
```

### Pattern 1: Immutable WitnessSet Value Object
**What:** WitnessSet as frozen dataclass with validation in __post_init__
**When to use:** Always - ensures WitnessSet cannot be modified after creation

**Example:**
```python
# Source: Python dataclasses best practices 2026
# https://docs.python.org/3/library/dataclasses.html
# https://realpython.com/python-data-classes/

from dataclasses import dataclass
from typing import List

@dataclass(frozen=True, kw_only=True)
class WitnessSet:
    """Immutable witness configuration for a namespace."""
    namespace: str
    witnesses: tuple[str, ...]  # Tuple (immutable) not list
    threshold: int

    def __post_init__(self):
        """Validate on construction."""
        # Use existing validate_threshold from policyhead.py
        from .policyhead import validate_threshold
        is_valid, error_msg = validate_threshold(self.threshold, list(self.witnesses))
        if not is_valid:
            from .exceptions import InputInvalidError
            raise InputInvalidError(
                f"Invalid WitnessSet for namespace '{self.namespace}': {error_msg}",
                details={"namespace": self.namespace, "threshold": self.threshold}
            )
```

**Why frozen:**
- Immutability prevents accidental modification
- Hashable (can be used in sets/dicts if needed)
- Thread-safe by design
- Enforces "change via new cell" pattern

**Performance note:** Frozen dataclasses are ~2.4x slower to instantiate than mutable, but this is negligible for WitnessSet registry operations (not created in tight loops).

### Pattern 2: Registry as Stateless Query Layer
**What:** WitnessRegistry queries Chain state, doesn't maintain in-memory cache
**When to use:** Always - prevents registry/chain state divergence

**Example:**
```python
# Source: Python registry pattern best practices
# https://charlesreid1.github.io/python-patterns-the-registry.html
# Avoid global state pitfalls: https://www.geeksforgeeks.org/system-design/registry-pattern/

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .chain import Chain

class WitnessRegistry:
    """Stateless query layer for namespace → WitnessSet lookups."""

    def __init__(self, chain: 'Chain'):
        """Registry is bound to a Chain, not independent state."""
        self.chain = chain

    def get_witness_set(self, namespace: str) -> Optional[WitnessSet]:
        """
        Get current WitnessSet for namespace.

        Returns:
            Current WitnessSet or None if namespace has no WitnessSet
        """
        # Build registry from chain state
        registry = self._build_registry()
        return registry.get(namespace)

    def _build_registry(self) -> dict[str, WitnessSet]:
        """
        Build namespace → WitnessSet mapping from Chain.

        Scans chain for:
        1. Genesis WitnessSet (bootstrap)
        2. WitnessSet change cells (promoted via existing witness set)

        Returns latest WitnessSet per namespace.
        """
        registry: dict[str, WitnessSet] = {}

        # 1. Extract Genesis WitnessSet (if exists)
        genesis = self.chain.genesis
        if genesis and has_witness_set(genesis):
            ws_data = parse_genesis_witness_set(genesis)
            root_ns = genesis.fact.namespace
            registry[root_ns] = WitnessSet(
                namespace=root_ns,
                witnesses=tuple(ws_data['witnesses']),
                threshold=ws_data['threshold']
            )

        # 2. Process WitnessSet change cells (temporal order)
        # TODO: Phase 2 implementation - scan for WitnessSet update cells
        # Latest update wins (overwrites previous)

        return registry
```

**Why stateless:**
- Chain is source of truth, not registry
- Avoids cache invalidation complexity
- Deterministic: same chain state = same registry state
- No race conditions between registry updates and chain appends

### Pattern 3: WitnessSet Changes via Promotion
**What:** Changing WitnessSet requires approval from existing WitnessSet (prevents unauthorized rotation)
**When to use:** Every WitnessSet change after Genesis

**Flow:**
```
1. User proposes new WitnessSet for namespace
2. Proposal requires approval from current WitnessSet witnesses
3. Once threshold met, new WitnessSet cell appended to Chain
4. Registry rebuild reflects new WitnessSet
```

**Bootstrap case:**
- Genesis embeds initial WitnessSet (no approval needed - it's the trust anchor)
- First WitnessSet change requires approval from Genesis WitnessSet

### Anti-Patterns to Avoid
- **In-memory cache without chain sync:** Registry state diverges from chain, violates append-only guarantee
- **Mutable WitnessSet:** Allows tampering, breaks immutability contract
- **Global singleton registry:** Tight coupling, hard to test, prevents multiple chains in one process
- **List for witnesses:** Mutable sequence; use tuple for immutability
- **Threshold validation in multiple places:** DRY violation; use existing validate_threshold from policyhead.py

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Threshold validation | Custom range checking | `validate_threshold()` from policyhead.py | Already handles edge cases: threshold=0, threshold>witnesses, empty witnesses list, witness ID validation |
| Immutability enforcement | Manual __setattr__ blocking | `@dataclass(frozen=True)` | Built-in, tested, generates __hash__, handles edge cases |
| Genesis WitnessSet parsing | Custom JSON parsing | `parse_genesis_witness_set()` from genesis.py | Already handles backward compatibility with legacy Genesis |
| Error codes | Custom exceptions | `InputInvalidError` from exceptions.py | Project uses standard DG_INPUT_INVALID code |
| Namespace validation | Custom regex | `validate_namespace()` from cell.py | Already validates hierarchical namespaces (corp.hr.rules) |

**Key insight:** Phase 1 built the foundation (threshold validation, Genesis embedding). Phase 2 extends it with runtime lookup. Reuse existing validation logic to maintain consistency and avoid divergence.

## Common Pitfalls

### Pitfall 1: Registry as In-Memory Cache
**What goes wrong:** Registry maintains dict in memory, updated on WitnessSet changes, but becomes out of sync with Chain if multiple processes or Chain rebuilds from storage

**Why it happens:** Tempting to cache for performance, but violates "chain is source of truth" principle

**How to avoid:** Make registry stateless - rebuild from chain on every query. For performance, caller can cache if needed (explicit caching better than implicit)

**Warning signs:**
- Registry constructor takes initial WitnessSet list (not Chain)
- Registry has `add_witness_set()` or `update_witness_set()` methods
- Tests don't verify registry matches chain state

### Pitfall 2: Witnesses as List Instead of Tuple
**What goes wrong:** Witnesses stored as `List[str]` allows mutation: `ws.witnesses.append("eve")` silently modifies WitnessSet

**Why it happens:** Dataclass frozen only prevents assignment to fields, not mutation of mutable field values

**How to avoid:** Use `tuple[str, ...]` for witnesses field. Tuples are immutable.

**Warning signs:**
```python
# BAD - mutable despite frozen=True
@dataclass(frozen=True)
class WitnessSet:
    witnesses: List[str]  # List is mutable!

ws = WitnessSet(witnesses=["alice", "bob"], ...)
ws.witnesses.append("eve")  # Works! But shouldn't!

# GOOD - truly immutable
@dataclass(frozen=True)
class WitnessSet:
    witnesses: tuple[str, ...]  # Tuple is immutable

ws = WitnessSet(witnesses=("alice", "bob"), ...)
ws.witnesses.append("eve")  # AttributeError: 'tuple' has no 'append'
```

### Pitfall 3: Threshold Validation Duplication
**What goes wrong:** Phase 2 reimplements threshold validation instead of reusing policyhead.py's `validate_threshold()`, leading to divergent validation logic

**Why it happens:** Developer doesn't realize validation already exists

**How to avoid:** Import and use `validate_threshold()` in WitnessSet.__post_init__. Single source of truth.

**Warning signs:**
- Tests have different threshold validation edge cases than test_bootstrap.py
- WitnessSet validation doesn't check for witness ID format (validate_threshold does)
- Error messages differ from policyhead.py validation

### Pitfall 4: Registry Concurrency Issues
**What goes wrong:** Multiple threads/processes modify registry dict concurrently, causing race conditions

**Why it happens:** Shared mutable state without synchronization

**How to avoid:** Make registry stateless (rebuild from chain). Chain handles concurrency via append-only semantics. If caching needed, use read-only caching with invalidation.

**Warning signs:**
- Registry instance shared across threads
- Tests don't verify concurrent access
- Global registry singleton

### Pitfall 5: Bootstrap Paradox Confusion
**What goes wrong:** Developer tries to create initial WitnessSet via promotion, creating circular dependency

**Why it happens:** Doesn't understand Genesis embedding solves bootstrap

**How to avoid:** Document clearly: Genesis embeds initial WitnessSet (already implemented in Phase 1). All subsequent changes go through promotion.

**Warning signs:**
- Code tries to "bootstrap" WitnessSet after Genesis
- Tests don't verify Genesis WitnessSet extraction
- Registry doesn't check Genesis for initial WitnessSet

## Code Examples

Verified patterns from official sources and existing codebase:

### Creating WitnessSet (Immutable)
```python
# Source: Phase 1 policyhead.py threshold validation
# Source: Python dataclasses docs

from dataclasses import dataclass
from typing import TYPE_CHECKING
from .policyhead import validate_threshold
from .exceptions import InputInvalidError

@dataclass(frozen=True, kw_only=True)
class WitnessSet:
    """
    Immutable witness configuration for a namespace.

    Attributes:
        namespace: Target namespace (hierarchical, e.g., "corp.hr")
        witnesses: Tuple of witness identifiers (immutable)
        threshold: Number of approvals required (1 <= threshold <= len(witnesses))

    Raises:
        InputInvalidError: If threshold is invalid for witness set
    """
    namespace: str
    witnesses: tuple[str, ...]
    threshold: int

    def __post_init__(self):
        """Validate threshold on construction."""
        # Reuse existing validation from Phase 1
        is_valid, error_msg = validate_threshold(self.threshold, list(self.witnesses))
        if not is_valid:
            raise InputInvalidError(
                f"Invalid WitnessSet for namespace '{self.namespace}': {error_msg}",
                details={
                    "namespace": self.namespace,
                    "threshold": self.threshold,
                    "witness_count": len(self.witnesses)
                }
            )

        # Validate namespace format (reuse existing)
        from .cell import validate_namespace
        if not validate_namespace(self.namespace):
            raise InputInvalidError(
                f"Invalid namespace format: '{self.namespace}'",
                details={"namespace": self.namespace}
            )

# Usage:
ws = WitnessSet(
    namespace="corp.hr",
    witnesses=("alice", "bob", "charlie"),
    threshold=2
)
# ws is immutable - cannot change fields
# ws.threshold = 3  # Raises FrozenInstanceError
```

### Registry Lookup (Stateless)
```python
# Source: Existing chain.py query patterns (get_current_policy_head)
# Pattern: Scan chain, filter by criteria, return latest

from typing import Optional, TYPE_CHECKING
from .genesis import parse_genesis_witness_set, has_witness_set

if TYPE_CHECKING:
    from .chain import Chain

class WitnessRegistry:
    """
    Stateless registry for namespace → WitnessSet lookups.

    Builds registry from Chain state on each query.
    Chain is source of truth, not in-memory cache.
    """

    def __init__(self, chain: 'Chain'):
        self.chain = chain

    def get_witness_set(self, namespace: str) -> Optional[WitnessSet]:
        """
        Get current WitnessSet for a namespace.

        Args:
            namespace: Namespace to query (e.g., "corp.hr")

        Returns:
            Current WitnessSet or None if namespace has no WitnessSet

        Example:
            >>> registry = WitnessRegistry(chain)
            >>> ws = registry.get_witness_set("corp")
            >>> if ws:
            ...     print(f"Threshold: {ws.threshold}/{len(ws.witnesses)}")
        """
        # Build fresh registry from chain
        reg = self._build_registry()
        return reg.get(namespace)

    def _build_registry(self) -> dict[str, WitnessSet]:
        """
        Build namespace → WitnessSet mapping from Chain state.

        Process:
        1. Extract Genesis WitnessSet (initial trust anchor)
        2. Process WitnessSet update cells in temporal order
        3. Latest update per namespace wins

        Returns:
            Dict mapping namespace to current WitnessSet
        """
        registry: dict[str, WitnessSet] = {}

        # 1. Genesis WitnessSet (bootstrap)
        genesis = self.chain.genesis
        if genesis and has_witness_set(genesis):
            ws_data = parse_genesis_witness_set(genesis)
            root_ns = genesis.fact.namespace
            registry[root_ns] = WitnessSet(
                namespace=root_ns,
                witnesses=tuple(sorted(ws_data['witnesses'])),  # Deterministic order
                threshold=ws_data['threshold']
            )

        # 2. WitnessSet update cells (future: Phase 2 implementation)
        # Scan chain for CellType.WITNESS_SET_UPDATE or similar
        # Latest update overwrites previous

        return registry
```

### Serialization to Chain (JSON)
```python
# Source: Existing genesis.py WitnessSet embedding pattern
# Pattern: JSON in fact.object with deterministic key ordering

import json
from .cell import DecisionCell, Fact

def serialize_witness_set_to_fact(ws: WitnessSet) -> str:
    """
    Serialize WitnessSet to JSON for storage in DecisionCell fact.object.

    Uses deterministic ordering (sorted keys, sorted witnesses) for
    reproducible hashing.
    """
    data = {
        "namespace": ws.namespace,
        "witnesses": sorted(ws.witnesses),  # Deterministic order
        "threshold": ws.threshold
    }
    return json.dumps(data, sort_keys=True)

def parse_witness_set_from_fact(fact_object: str) -> WitnessSet:
    """Parse WitnessSet from DecisionCell fact.object JSON."""
    data = json.loads(fact_object)
    return WitnessSet(
        namespace=data["namespace"],
        witnesses=tuple(data["witnesses"]),
        threshold=data["threshold"]
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| OrderedDict for registries | Plain dict | Python 3.7 (2018) | Dicts preserve insertion order; OrderedDict unnecessary for basic registries |
| Mutable dataclasses | Frozen dataclasses | Python 3.7 (2018) | Frozen ensures immutability, generates __hash__, prevents accidental mutation |
| Manual registry caching | Stateless rebuild from source | 2025+ best practice | Eliminates cache invalidation bugs; source of truth pattern |
| Global singleton registry | Dependency injection | 2020+ best practice | Testable, supports multiple graphs, no hidden state |

**Deprecated/outdated:**
- **OrderedDict for basic lookup**: Dict has guaranteed order since Python 3.7, OrderedDict only needed for `move_to_end()` or order-sensitive equality
- **Mutable witness lists**: Use tuple for immutability (frozen dataclass doesn't prevent list mutation)
- **In-memory registry without chain sync**: Violates append-only chain guarantee

## Open Questions

Things that couldn't be fully resolved:

1. **WitnessSet change cell type**
   - What we know: Need a cell type for WitnessSet updates (after Genesis)
   - What's unclear: Should this be a new CellType.WITNESS_SET_UPDATE, or reuse existing type?
   - Recommendation: Propose new CellType.WITNESS_SET_UPDATE in Phase 2 plan for clarity. Similar to CellType.POLICY_HEAD pattern.

2. **Namespace inheritance of WitnessSet**
   - What we know: Namespaces are hierarchical ("corp.hr.payroll")
   - What's unclear: Does "corp.hr.payroll" inherit "corp.hr" WitnessSet if not explicitly set?
   - Recommendation: Phase 2 scope is explicit WitnessSet per namespace. Inheritance is future enhancement (Phase 3+).

3. **Performance optimization for large registries**
   - What we know: Rebuilding registry from chain on every query is O(n) where n = chain length
   - What's unclear: When does this become a bottleneck? Need profiling.
   - Recommendation: Start with stateless rebuild (correctness first). Add caching only if profiling shows bottleneck. Premature optimization risk.

4. **WitnessSet rotation approval workflow**
   - What we know: Changing WitnessSet requires approval from existing witnesses (WIT-04)
   - What's unclear: Is approval tracked in evidence[] of WitnessSet update cell? Or separate approval cells?
   - Recommendation: Follow PolicyHead promotion pattern - approval tracked in evidence[], threshold met before append.

## Sources

### Primary (HIGH confidence)
- Python official documentation - dataclasses: https://docs.python.org/3/library/dataclasses.html
- Real Python - Data Classes Guide (2026): https://realpython.com/python-data-classes/
- Python official documentation - collections: https://docs.python.org/3/library/collections.html
- Real Python - OrderedDict vs dict (2026): https://realpython.com/python-ordereddict/
- Existing codebase - policyhead.py (validate_threshold, threshold validation logic)
- Existing codebase - genesis.py (WitnessSet embedding, parse_genesis_witness_set)
- Existing codebase - exceptions.py (InputInvalidError, DG_INPUT_INVALID)

### Secondary (MEDIUM confidence)
- GeeksforGeeks - Registry Pattern: https://www.geeksforgeeks.org/system-design/registry-pattern/
- DEV Community - Python Registry Pattern: https://dev.to/dentedlogic/stop-writing-giant-if-else-chains-master-the-python-registry-pattern-ldm
- Python Patterns - The Registry: https://charlesreid1.github.io/python-patterns-the-registry.html
- Frozen dataclass best practices: https://codereview.doctor/features/python/best-practice/frozen-dataclass-immutable
- Statically enforcing frozen dataclasses: https://rednafi.com/python/statically-enforcing-frozen-dataclasses/

### Tertiary (LOW confidence)
- Multisig HMAC PyPI (threshold signature concept validation): https://pypi.org/project/multisig-hmac/
- Python performance comparison (dict vs OrderedDict): https://switowski.com/blog/ordered-dictionaries/

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Python stdlib dataclasses, dict, typing are well-documented and stable
- Architecture: HIGH - Patterns verified in existing Phase 1 codebase (policyhead.py, genesis.py query patterns)
- Pitfalls: HIGH - Based on official Python docs warnings and existing codebase patterns

**Research date:** 2026-01-28
**Valid until:** 2026-02-28 (30 days - stable domain, Python 3.10+ stdlib)

**Key assumptions:**
- Python 3.10+ (project constraint)
- No external dependencies preferred (project constraint)
- Chain is append-only and source of truth (project architecture)
- Bootstrap mode already implemented (Phase 1 complete)
