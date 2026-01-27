# Genesis Verification Checklist (22 Checks)

Genesis is the root of all trust in a DecisionGraph. These 22 checks ensure it's valid.

## Important Boundary

**`verify_genesis()` validates STRUCTURE only.**

These constraints are enforced by the **Commit Gate** (`Chain.append()`):
- Genesis must be the first cell
- Only one Genesis per graph
- All subsequent cells must have matching `graph_id`

## The 22 Checks

### HEADER (1-5)

| # | Check | Expected | Error Message |
|---|-------|----------|---------------|
| 1 | `cell_type` | `GENESIS` | `[1] header.cell_type: expected 'genesis', got '...'` |
| 2 | `prev_cell_hash` | `NULL_HASH` (64 zeros) | `[2] header.prev_cell_hash: expected NULL_HASH...` |
| 3 | `version` | `SCHEMA_VERSION` ("1.3") | `[3] header.version: expected '1.3', got '...'` |
| 4 | `graph_id` | Valid format `graph:<uuid-v4>` | `[4] header.graph_id: invalid format...` |
| 5 | `system_time` | ISO 8601 UTC ending with 'Z' | `[5] header.system_time: must be ISO 8601 UTC...` |

### FACT (6-14)

| # | Check | Expected | Error Message |
|---|-------|----------|---------------|
| 6 | `namespace` | Valid root (no dots) | `[6] fact.namespace: '...' is not a valid root namespace` |
| 7 | `subject` | `"graph:root"` | `[7] fact.subject: expected 'graph:root', got '...'` |
| 8 | `predicate` | `"instance_of"` | `[8] fact.predicate: expected 'instance_of', got '...'` |
| 9 | `object` | Non-empty (graph name) | `[9] fact.object: graph_name cannot be empty` |
| 10 | `confidence` | `1.0` | `[10] fact.confidence: expected 1.0, got ...` |
| 11 | `source_quality` | `"verified"` | `[11] fact.source_quality: expected 'verified', got '...'` |
| 12 | `valid_from` | ISO 8601 UTC ending with 'Z' | `[12] fact.valid_from: must be ISO 8601 UTC...` |
| 13 | `valid_to` | `None` (open-ended) | `[13] fact.valid_to: expected None (open-ended), got '...'` |
| 14 | `valid_from == system_time` | Must match | `[14] fact.valid_from: must match system_time for Genesis` |

### LOGIC ANCHOR (15-17)

| # | Check | Expected | Error Message |
|---|-------|----------|---------------|
| 15 | `rule_id` | `"system:genesis_boot_v1.3"` (exact) | `[15] logic_anchor.rule_id: expected '...', got '...'` |
| 16 | `rule_logic_hash` | `GENESIS_RULE_HASH` | `[16] logic_anchor.rule_logic_hash: expected '...', got '...'` |
| 17 | `interpreter` | `"system:v1.3"` (exact) | `[17] logic_anchor.interpreter: expected '...', got '...'` |

### STRUCTURE (18)

| # | Check | Expected | Error Message |
|---|-------|----------|---------------|
| 18 | `evidence` | `[]` (empty list) | `[18] evidence: Genesis must have no evidence (got N items)` |

### PROOF (19-21, Conditional)

**If `strict_signature=True`:**

| # | Check | Expected | Error Message |
|---|-------|----------|---------------|
| 19 | `signer_key_id` | Present | `[19] proof.signer_key_id: required in strict mode but not present` |
| 20 | `signature` | Present | `[20] proof.signature: required in strict mode but not present` |

**If `strict_signature=False` (bootstrap mode):**

| # | Check | Expected | Error Message |
|---|-------|----------|---------------|
| 21 | Consistent state | signature is None OR signature_required is False | `[21] proof: in bootstrap mode, if signature is present, signature_required must be False` |

### INTEGRITY (22)

| # | Check | Expected | Error Message |
|---|-------|----------|---------------|
| 22 | `verify_integrity()` | `True` | `[22] integrity: cell_id does not match computed hash (cell may be tampered)` |

## Usage

```python
from decisiongraph import create_genesis_cell, verify_genesis, verify_genesis_strict

# Create genesis
genesis = create_genesis_cell(
    graph_name="MyGraph",
    root_namespace="mygraph",
    creator="system:init"
)

# Verify (returns tuple)
is_valid, failed_checks = verify_genesis(genesis)
if not is_valid:
    for check in failed_checks:
        print(check)

# Verify strict (raises exception)
try:
    verify_genesis_strict(genesis, require_signature=True)
except GenesisValidationError as e:
    print(f"Failed: {e.failed_checks}")
```

## Why These Checks?

| Check | Why It Matters |
|-------|----------------|
| Cell type | Ensures we're actually validating a Genesis |
| prev_cell_hash = NULL | Genesis has no predecessor |
| Version | Schema compatibility |
| graph_id format | Prevents malformed IDs that break partitioning |
| system_time UTC | Consistent global ordering |
| Root namespace | No dots = truly a root |
| subject = graph:root | Standard Genesis identity |
| predicate = instance_of | Standard Genesis relationship |
| object non-empty | Must have a graph name |
| confidence = 1.0 | Genesis is certain |
| source_quality = verified | Genesis is authoritative |
| valid_from UTC | Consistent time format |
| valid_to = None | Genesis never expires |
| valid_from = system_time | Creation moment = record moment |
| rule_id exact | No variations for Genesis |
| rule_hash | Proves correct boot rule |
| interpreter exact | No variations for Genesis |
| evidence empty | Genesis is pure, no smuggled claims |
| Proof checks | Bootstrap vs production mode |
| Integrity | Tamper detection |

## The Genesis Rule

```
-- DecisionGraph Genesis Rule v1.3
-- This rule defines the creation of a new DecisionGraph instance
-- with a unique graph_id and root namespace

CREATE GRAPH:
  WHEN no_cells_exist
  THEN create_genesis_cell
  WITH prev_cell_hash = NULL_HASH
  AND cell_type = "genesis"
  AND graph_id = generate_graph_id()
  AND namespace = root_namespace (no dots, lowercase alphanumeric)
  AND subject = "graph:root"
  AND predicate = "instance_of"
  AND confidence = 1.0
  AND source_quality = "verified"
  AND valid_to = None (open-ended)

TIME MODEL:
  header.system_time = when engine recorded this cell (ISO 8601 UTC)
  fact.valid_from = when fact became true (same as system_time for genesis)
  fact.valid_to = when fact stops being true (None = forever)
```

This rule is canonicalized before hashing to ensure whitespace doesn't affect the hash.
