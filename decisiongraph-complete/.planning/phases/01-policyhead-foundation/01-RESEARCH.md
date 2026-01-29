# Phase 1: PolicyHead Foundation - Research

**Researched:** 2026-01-27
**Domain:** Python-based immutable cell architecture with Ed25519 cryptography
**Confidence:** HIGH

## Summary

Phase 1 implements PolicyHead as a new cell type in the existing DecisionGraph v1.3 architecture. The standard approach leverages existing patterns: PolicyHead cells are DecisionCells with CellType.POLICY_HEAD, stored in the main Chain, and indexed via Scholar. The bootstrap paradox is solved by embedding initial WitnessSet data in the Genesis cell's fact.object (JSON serialization), not as a separate cell. This follows v1.3's pattern where Genesis contains system configuration rather than creating circular dependencies.

**Critical finding:** PolicyHead is NOT a separate data structure. It's a specialized DecisionCell with fact.predicate="policy_snapshot" and fact.object containing JSON-serialized policy data. This maintains v1.3's "everything is a cell" architecture and avoids duplicating chain/storage infrastructure.

**Primary recommendation:** Extend CellType enum with POLICY_HEAD, use fact.object for policy data serialization, implement get_current_policy_head() as a Scholar query pattern, and embed Genesis WitnessSet in genesis.fact.object as JSON.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.8+ | Dataclasses, typing, hashlib, json | v1.3 uses dataclasses for all structures |
| cryptography | latest | Ed25519 signing (already in v1.4) | Existing signing.py uses this for Ed25519 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | latest | Testing framework | All v1.3 tests use pytest |
| None | - | No external storage | v1.3 philosophy: "garden grows from own soil" |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Dataclass | Dict | Dataclass provides validation, type safety, and matches v1.3 patterns |
| JSON in fact.object | Custom Cell fields | JSON serialization maintains Cell schema stability |
| Chain storage | Separate PolicyHead store | Chain is the universal truth - no parallel stores |

**Installation:**
```bash
# Already available in v1.3
pip install cryptography pytest
```

## Architecture Patterns

### Recommended Project Structure
```
src/decisiongraph/
├── cell.py              # Add POLICY_HEAD to CellType enum
├── chain.py             # No changes needed (Chain.append handles all types)
├── genesis.py           # Extend to embed initial WitnessSet in fact.object
├── policyhead.py        # NEW: PolicyHead helpers (create, query, validate)
└── scholar.py           # Add get_current_policy_head() query method

tests/
├── test_policyhead.py   # NEW: PolicyHead creation, chaining, bootstrap
└── test_witness.py      # NEW: WitnessSet validation, Genesis embedding
```

### Pattern 1: PolicyHead as Specialized Cell
**What:** PolicyHead is a DecisionCell with specific structure
**When to use:** Creating policy snapshots
**Example:**
```python
# Source: Inferred from cell.py patterns + Scholar.py query patterns
from decisiongraph import DecisionCell, Header, Fact, LogicAnchor, CellType
import json

def create_policy_head(
    namespace: str,
    promoted_rule_ids: List[str],
    prev_policy_head: Optional[str],
    graph_id: str,
    prev_cell_hash: str,
    system_time: str
) -> DecisionCell:
    """Create PolicyHead cell following v1.3 DecisionCell pattern."""

    # Deterministic policy_hash (POL-02)
    sorted_ids = sorted(promoted_rule_ids)
    policy_hash = hashlib.sha256(
        json.dumps(sorted_ids, separators=(',', ':')).encode('utf-8')
    ).hexdigest()

    # Policy data as JSON in fact.object
    policy_data = {
        "policy_hash": policy_hash,
        "promoted_rule_ids": sorted_ids,
        "prev_policy_head": prev_policy_head  # None for first PolicyHead
    }

    return DecisionCell(
        header=Header(
            version="1.5",
            graph_id=graph_id,
            cell_type=CellType.POLICY_HEAD,  # NEW enum value
            system_time=system_time,
            prev_cell_hash=prev_cell_hash
        ),
        fact=Fact(
            namespace=namespace,
            subject="policy:head",
            predicate="policy_snapshot",
            object=json.dumps(policy_data, sort_keys=True),
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED,
            valid_from=system_time
        ),
        logic_anchor=LogicAnchor(
            rule_id="system:policy_promotion_v1.5",
            rule_logic_hash=compute_rule_logic_hash("POLICY_PROMOTION_RULE")
        )
    )
```

### Pattern 2: Query Current PolicyHead (Scholar Pattern)
**What:** Retrieve latest PolicyHead for namespace using Scholar index
**When to use:** Getting active policy for namespace (POL-04)
**Example:**
```python
# Source: Derived from scholar.py query_facts() pattern
def get_current_policy_head(
    chain: Chain,
    namespace: str
) -> Optional[DecisionCell]:
    """
    Query current PolicyHead for namespace.

    Follows Scholar pattern: filter cells by type and namespace,
    sort by system_time, return most recent.
    """
    # Find all POLICY_HEAD cells for namespace
    policy_heads = [
        cell for cell in chain.cells
        if cell.header.cell_type == CellType.POLICY_HEAD
        and cell.fact.namespace == namespace
    ]

    if not policy_heads:
        return None

    # Sort by system_time (most recent last)
    sorted_heads = sorted(policy_heads, key=lambda c: c.header.system_time)
    return sorted_heads[-1]
```

### Pattern 3: Genesis with Embedded WitnessSet (Bootstrap)
**What:** Solve bootstrap paradox by embedding WitnessSet in Genesis.fact.object
**When to use:** Chain initialization (BOT-01)
**Example:**
```python
# Source: Derived from genesis.py create_genesis_cell() pattern
def create_genesis_with_witness_set(
    graph_name: str,
    root_namespace: str,
    initial_witnesses: List[str],
    threshold: int,
    graph_id: Optional[str] = None,
    system_time: Optional[str] = None
) -> DecisionCell:
    """
    Create Genesis cell with embedded WitnessSet.

    Genesis.fact.object contains JSON with graph_name AND initial WitnessSet.
    This avoids circular dependency: Genesis creates the bootstrap WitnessSet.
    """

    # Validate threshold (WIT-02)
    if not (1 <= threshold <= len(initial_witnesses)):
        raise ValueError(f"Threshold {threshold} must be 1 <= t <= {len(initial_witnesses)}")

    # Genesis object contains both graph metadata and WitnessSet
    genesis_data = {
        "graph_name": graph_name,
        "initial_witness_set": {
            "namespace": root_namespace,
            "witnesses": sorted(initial_witnesses),  # Deterministic ordering
            "threshold": threshold
        }
    }

    # Use existing Genesis pattern but with enhanced object
    genesis = create_genesis_cell(
        graph_name=json.dumps(genesis_data, sort_keys=True),
        root_namespace=root_namespace,
        graph_id=graph_id,
        system_time=system_time
    )

    return genesis
```

### Pattern 4: Deterministic policy_hash Computation
**What:** SHA-256 of canonicalized promoted_rule_ids
**When to use:** Creating PolicyHead, verifying PolicyHead integrity (POL-02)
**Example:**
```python
# Source: Derived from cell.py compute_rule_logic_hash() pattern
import hashlib
import json

def compute_policy_hash(promoted_rule_ids: List[str]) -> str:
    """
    Compute deterministic policy_hash from promoted_rule_ids.

    Follows v1.3 canonicalization pattern:
    1. Sort rule IDs (deterministic ordering)
    2. JSON serialize with consistent separators
    3. SHA-256 hash
    """
    sorted_ids = sorted(promoted_rule_ids)
    # Use separators=(',', ':') for compact, deterministic JSON
    canonical_json = json.dumps(sorted_ids, separators=(',', ':'))
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
```

### Anti-Patterns to Avoid
- **Creating separate PolicyHead storage:** Chain is the universal store. PolicyHead cells go in Chain.cells like all other cells.
- **WitnessSet as promotable Rule cell:** Creates bootstrap paradox. Genesis must include initial WitnessSet inline.
- **Manual prev_policy_head tracking:** Query chain to find previous PolicyHead, don't maintain separate index.
- **Custom hash algorithms:** Use SHA-256 consistently with v1.3 patterns (cell_id, rule_logic_hash, policy_hash).

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cell storage | Custom PolicyHead database | Chain.append() | Chain handles integrity, graph_id validation, temporal ordering |
| Cell queries | Manual chain iteration | Scholar query patterns | Scholar has indexes, bitemporal filtering, resolution |
| Cryptographic hashing | Custom hash function | hashlib.sha256 | Matches v1.3 cell_id, rule_logic_hash patterns |
| Ed25519 signing | Custom crypto | signing.sign_bytes(), verify_signature() | Already implemented, tested in v1.4 |
| Deterministic serialization | Custom JSON encoder | json.dumps(sort_keys=True, separators=(',',':')) | Matches canonicalize_rule_content pattern |
| Timestamp generation | datetime.now() | get_current_timestamp() | Ensures UTC, ISO 8601, consistent format |

**Key insight:** v1.3 architecture is extensible via CellType enum. Don't create parallel infrastructure - extend what exists.

## Common Pitfalls

### Pitfall 1: Bootstrap Paradox - WitnessSet as Cell
**What goes wrong:** Creating WitnessSet as a promotable Rule cell creates circular dependency: who promotes the first WitnessSet?
**Why it happens:** Naive thinking "everything should be a cell with signatures"
**How to avoid:** Embed initial WitnessSet in Genesis.fact.object as JSON. Genesis is the trusted bootstrap root.
**Warning signs:** If you need a WitnessSet to promote the first WitnessSet, you've created a circular dependency.

### Pitfall 2: Threshold Validation Off-by-One Errors
**What goes wrong:** Edge cases like threshold=0, threshold=len(witnesses)+1, or threshold with empty witness list
**Why it happens:** Integer math edge cases, inclusive vs exclusive ranges
**How to avoid:** Test boundary conditions FIRST:
```python
# Test cases to write BEFORE implementation:
- threshold=1, witnesses=1 (bootstrap mode) ✓ valid
- threshold=0, witnesses=N ✗ invalid
- threshold=N+1, witnesses=N ✗ invalid
- threshold=N, witnesses=N (unanimous) ✓ valid
- threshold=2, witnesses=1 ✗ invalid
```
**Warning signs:** Any threshold calculation without explicit tests for 0, 1, N, N+1 cases.

### Pitfall 3: Non-Deterministic policy_hash
**What goes wrong:** Different orderings of promoted_rule_ids produce different hashes
**Why it happens:** Python dict/set iteration order varies, JSON serialization order differs
**How to avoid:** ALWAYS sort before hashing: `sorted_ids = sorted(promoted_rule_ids)`. Test with reversed order.
**Warning signs:** policy_hash changes when rule_ids are provided in different order but contain same values.

### Pitfall 4: prev_policy_head as Foreign Key Assumption
**What goes wrong:** Assuming prev_policy_head exists in chain, causing lookup failures
**Why it happens:** SQL database mindset - expecting foreign key constraints
**How to avoid:** prev_policy_head is None for first PolicyHead in namespace. Validate existence only when non-None.
**Warning signs:** KeyError or None dereference when querying prev_policy_head.

### Pitfall 5: CellType Enum Extension Breaking Existing Code
**What goes wrong:** Adding POLICY_HEAD to CellType enum breaks Scholar filters or Chain validation
**Why it happens:** Existing code may have exhaustive CellType switches or type filters
**How to avoid:**
- Check all CellType usage in codebase (grep "CellType\.")
- Scholar.build_index_from_chain() has explicit CellType filter - add POLICY_HEAD if it should be indexed
- Test that existing functionality still works after enum addition
**Warning signs:** Scholar queries return empty after adding CellType.POLICY_HEAD.

### Pitfall 6: Genesis fact.object Size Assumptions
**What goes wrong:** Code assumes fact.object is a simple string, breaks when it's JSON
**Why it happens:** Genesis currently uses graph_name as simple string
**How to avoid:** Parse Genesis.fact.object as JSON in new code, maintain backward compatibility for old Genesis cells
**Warning signs:** JSON parse errors when reading Genesis.fact.object from old chains.

## Code Examples

Verified patterns from official sources:

### Adding CellType Enum Value
```python
# Source: src/decisiongraph/cell.py lines 32-42
class CellType(str, Enum):
    """Valid cell types in DecisionGraph"""
    GENESIS = "genesis"
    FACT = "fact"
    RULE = "rule"
    DECISION = "decision"
    EVIDENCE = "evidence"
    OVERRIDE = "override"
    ACCESS_RULE = "access_rule"
    BRIDGE_RULE = "bridge_rule"
    NAMESPACE_DEF = "namespace_def"
    POLICY_HEAD = "policy_head"  # NEW for v1.5
```

### Chain.append() Validation Pattern
```python
# Source: src/decisiongraph/chain.py lines 219-338
# Chain.append() already handles:
# 1. Genesis uniqueness check
# 2. Cell integrity verification (cell.verify_integrity())
# 3. graph_id validation (cell.header.graph_id == self.graph_id)
# 4. Chain link validation (prev_cell_hash exists)
# 5. Temporal validation (system_time >= prev.system_time)
#
# PolicyHead cells get ALL these validations for free.
# No custom append logic needed.

chain.append(policy_head_cell)  # Just works!
```

### Scholar Index Pattern (for get_current_policy_head)
```python
# Source: src/decisiongraph/scholar.py lines 405-488
# Scholar indexes cells by type, namespace, and (namespace, subject, predicate)
# Pattern to follow:

def get_current_policy_head(
    chain: Chain,
    namespace: str
) -> Optional[DecisionCell]:
    """
    Get current PolicyHead for namespace.

    Uses Chain directly (not Scholar) because PolicyHead is
    system metadata, not queryable fact data.
    """
    # Filter by type and namespace
    policy_heads = chain.find_by_type(CellType.POLICY_HEAD)
    namespace_heads = [
        ph for ph in policy_heads
        if ph.fact.namespace == namespace
    ]

    if not namespace_heads:
        return None

    # Most recent by system_time
    namespace_heads.sort(key=lambda c: c.header.system_time)
    return namespace_heads[-1]
```

### Deterministic Hashing Pattern
```python
# Source: src/decisiongraph/cell.py lines 156-188
# v1.3 uses canonicalization before hashing

def canonicalize_policy_data(promoted_rule_ids: List[str]) -> str:
    """Canonicalize for deterministic hashing."""
    sorted_ids = sorted(promoted_rule_ids)
    # Use compact JSON (no whitespace)
    return json.dumps(sorted_ids, separators=(',', ':'))

def compute_policy_hash(promoted_rule_ids: List[str]) -> str:
    """Compute SHA-256 of canonicalized rule IDs."""
    canonical = canonicalize_policy_data(promoted_rule_ids)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
```

### Ed25519 Signature Pattern (for future use)
```python
# Source: src/decisiongraph/signing.py lines 36-98
from decisiongraph.signing import sign_bytes, verify_signature, generate_ed25519_keypair

# Generate witness keypair
priv_key, pub_key = generate_ed25519_keypair()

# Sign promotion payload
payload = json.dumps({
    "namespace": namespace,
    "promoted_rule_ids": sorted(rule_ids),
    "policy_hash": policy_hash
}, sort_keys=True).encode('utf-8')

signature = sign_bytes(priv_key, payload)

# Verify
is_valid = verify_signature(pub_key, payload, signature)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom Cell classes | CellType enum + DecisionCell | v1.3 | All cells share same structure, storage, validation |
| Separate stores per type | Single Chain for all cells | v1.3 | Unified integrity, simpler architecture |
| Timestamp (ambiguous) | system_time + valid_from/valid_to | v1.3 | Bitemporal queries, clear semantics |
| Implicit namespace | Explicit namespace in Fact | v1.3 | Namespace isolation enforced at cell level |
| Optional graph_id | Required graph_id in Header | v1.3 | Prevents cross-graph contamination |

**Deprecated/outdated:**
- Creating custom Cell subclasses: Use CellType enum instead
- Direct cell creation without Chain.append(): Bypasses validation
- Manual cell_id computation: Let DecisionCell.__post_init__ compute it
- Hardcoded timestamp strings: Use get_current_timestamp()

## Open Questions

Things that couldn't be fully resolved:

1. **Should PolicyHead be indexed by Scholar?**
   - What we know: Scholar.build_index_from_chain() explicitly filters CellType (lines 476-487)
   - What's unclear: PolicyHead is metadata, not query data. Should it be in Scholar index?
   - Recommendation: NO. PolicyHead queries use Chain.find_by_type() directly. Keep Scholar for fact/rule/decision queries only. Add `get_current_policy_head()` as Chain method or standalone function.

2. **Genesis backward compatibility with embedded WitnessSet**
   - What we know: Genesis.fact.object currently stores graph_name as simple string
   - What's unclear: How to read old Genesis cells vs new ones with JSON object?
   - Recommendation: Parse Genesis.fact.object - if JSON parse succeeds, extract graph_name from JSON; if fails, treat as legacy simple string. Write migration note in docs.

3. **prev_policy_head chain traversal efficiency**
   - What we know: Chain can be large, linear scan to find prev PolicyHead could be slow
   - What's unclear: Should we build a PolicyHead-specific index?
   - Recommendation: Start simple with linear scan. Optimize only if profiling shows it's a bottleneck. PolicyHead updates are infrequent (policy changes), not hot path.

## Sources

### Primary (HIGH confidence)
- `src/decisiongraph/cell.py` - CellType enum, DecisionCell structure, compute_rule_logic_hash pattern
- `src/decisiongraph/chain.py` - Chain.append() validation, find_by_type() queries
- `src/decisiongraph/genesis.py` - Genesis creation pattern, bootstrap approach
- `src/decisiongraph/scholar.py` - Query patterns, index structure, deterministic ordering
- `src/decisiongraph/signing.py` - Ed25519 sign/verify implementation
- `.planning/ROADMAP.md` - Phase 1 requirements and success criteria

### Secondary (MEDIUM confidence)
- `README.md` - v1.3 architecture overview, Cell examples
- `tests/test_core.py` - Cell creation patterns, test structure
- `docs/ROADMAP.md` - v1.3 completion status

### Tertiary (LOW confidence)
- None - all findings verified with source code

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in use by v1.3
- Architecture: HIGH - Verified from existing cell.py, chain.py, genesis.py implementation
- Pitfalls: HIGH - Derived from v1.3 patterns and explicit ROADMAP.md warnings

**Research date:** 2026-01-27
**Valid until:** 60 days (stable Python architecture, minimal churn expected)
