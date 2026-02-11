
# DecisionGraph Schema v1.3

## Cell Types

```python
class CellType(str, Enum):
    GENESIS = "genesis"
    FACT = "fact"
    RULE = "rule"
    DECISION = "decision"
    EVIDENCE = "evidence"
    OVERRIDE = "override"
    ACCESS_RULE = "access_rule"
    BRIDGE_RULE = "bridge_rule"
    NAMESPACE_DEF = "namespace_def"
```

## Source Quality

```python
class SourceQuality(str, Enum):
    VERIFIED = "verified"       # Confirmed from authoritative source
    SELF_REPORTED = "self_reported"  # User-provided, not verified
    INFERRED = "inferred"       # Derived from other facts
```

## Complete Cell Schema

```json
{
  "cell_id": "string (SHA256 hex, 64 chars)",
  
  "header": {
    "version": "string (e.g., '1.3')",
    "graph_id": "string (format: 'graph:<uuid-v4>')",
    "cell_type": "string (CellType enum value)",
    "system_time": "string (ISO 8601 UTC, must end with 'Z')",
    "prev_cell_hash": "string (SHA256 hex, 64 chars or NULL_HASH for Genesis)"
  },
  
  "fact": {
    "namespace": "string (lowercase, dots for hierarchy, e.g., 'corp.hr.compensation')",
    "subject": "string (entity identifier, e.g., 'employee:jane_doe')",
    "predicate": "string (relationship, e.g., 'has_salary')",
    "object": "string (value or entity)",
    "confidence": "number (0.0 to 1.0)",
    "source_quality": "string (SourceQuality enum value)",
    "valid_from": "string (ISO 8601 UTC) | null",
    "valid_to": "string (ISO 8601 UTC) | null (null = forever)"
  },
  
  "logic_anchor": {
    "rule_id": "string (rule identifier, e.g., 'policy:salary_bands_v1')",
    "rule_logic_hash": "string (SHA256 hex of canonicalized rule content)",
    "interpreter": "string (optional, e.g., 'datalog:v2', 'dmn:1.3')"
  },
  
  "evidence": [
    {
      "type": "string (e.g., 'document_blob', 'api_response', 'approval')",
      "cid": "string (content ID, optional)",
      "source": "string (optional)",
      "payload_hash": "string (optional)",
      "description": "string (optional)"
    }
  ],
  
  "proof": {
    "signer_id": "string (who signed, e.g., 'role:hr_manager')",
    "signer_key_id": "string (key reference, optional)",
    "signature": "string (cryptographic signature, optional in bootstrap mode)",
    "merkle_root": "string (optional)",
    "signature_required": "boolean (default false)"
  }
}
```

## cell_id Computation (Logic Seal)

```python
def compute_cell_id(cell) -> str:
    seal_string = (
        cell.header.version +
        cell.header.graph_id +
        cell.header.cell_type.value +
        cell.header.system_time +
        cell.header.prev_cell_hash +
        cell.fact.namespace +
        cell.fact.subject +
        cell.fact.predicate +
        str(cell.fact.object) +
        cell.logic_anchor.rule_id +
        cell.logic_anchor.rule_logic_hash
    )
    return hashlib.sha256(seal_string.encode('utf-8')).hexdigest()
```

## Validation Rules

### Namespace

```python
# Pattern: lowercase letter, then alphanumeric/underscore, dots for hierarchy
NAMESPACE_PATTERN = r'^[a-z][a-z0-9_]{0,63}(\.[a-z][a-z0-9_]{0,63})*$'

# Root namespace (no dots)
ROOT_NAMESPACE_PATTERN = r'^[a-z][a-z0-9_]{1,63}$'
```

Valid: `corp`, `corp.hr`, `acme.sales.discounts`, `my_company.dept_1`
Invalid: ``, `.corp`, `corp.`, `Corp.HR`, `123corp`, `corp/hr`

### graph_id

```python
# Format: graph:<uuid-v4>
GRAPH_ID_PATTERN = r'^graph:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
```

Valid: `graph:a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d`
Invalid: `a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d` (missing prefix)

### Timestamp

```python
# ISO 8601 with UTC timezone (must end with 'Z')
ISO_TIMESTAMP_PATTERN = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$'
```

Valid: `2026-01-27T12:00:00Z`, `2026-01-27T12:00:00.123Z`
Invalid: `2026-01-27T12:00:00`, `2026-01-27T12:00:00+00:00`

### Confidence

- Range: 0.0 to 1.0
- If confidence = 1.0, source_quality must be "verified"

## NULL_HASH

The special hash for Genesis:

```python
NULL_HASH = "0" * 64  # 64 zeros
```

Only Genesis may have `prev_cell_hash = NULL_HASH`.

## Constants

```python
SCHEMA_VERSION = "1.3"
DEFAULT_ROOT_NAMESPACE = "corp"
```

## Examples

### Genesis Cell

```json
{
  "cell_id": "a1b2c3...",
  "header": {
    "version": "1.3",
    "graph_id": "graph:12345678-1234-4123-8123-123456789abc",
    "cell_type": "genesis",
    "system_time": "2026-01-27T12:00:00Z",
    "prev_cell_hash": "0000000000000000000000000000000000000000000000000000000000000000"
  },
  "fact": {
    "namespace": "acme",
    "subject": "graph:root",
    "predicate": "instance_of",
    "object": "AcmeCorp_DecisionGraph",
    "confidence": 1.0,
    "source_quality": "verified",
    "valid_from": "2026-01-27T12:00:00Z",
    "valid_to": null
  },
  "logic_anchor": {
    "rule_id": "system:genesis_boot_v1.3",
    "rule_logic_hash": "abc123...",
    "interpreter": "system:v1.3"
  },
  "evidence": [],
  "proof": {
    "signer_id": "system:genesis",
    "signature_required": false
  }
}
```

### Fact Cell

```json
{
  "cell_id": "def456...",
  "header": {
    "version": "1.3",
    "graph_id": "graph:12345678-1234-4123-8123-123456789abc",
    "cell_type": "fact",
    "system_time": "2026-01-27T12:01:00Z",
    "prev_cell_hash": "a1b2c3..."
  },
  "fact": {
    "namespace": "acme.hr.compensation",
    "subject": "employee:jane_doe",
    "predicate": "has_salary",
    "object": "150000",
    "confidence": 1.0,
    "source_quality": "verified",
    "valid_from": "2026-01-01T00:00:00Z",
    "valid_to": null
  },
  "logic_anchor": {
    "rule_id": "source:hris_export",
    "rule_logic_hash": "xyz789...",
    "interpreter": null
  },
  "evidence": [
    {
      "type": "document_blob",
      "cid": "sha256:...",
      "description": "HRIS payroll export"
    }
  ],
  "proof": {
    "signer_id": "role:hr_manager"
  }
}
```

### Bridge Rule Cell

```json
{
  "cell_id": "ghi789...",
  "header": {
    "version": "1.3",
    "graph_id": "graph:12345678-1234-4123-8123-123456789abc",
    "cell_type": "bridge_rule",
    "system_time": "2026-01-27T12:02:00Z",
    "prev_cell_hash": "def456..."
  },
  "fact": {
    "namespace": "system.bridges",
    "subject": "acme.sales",
    "predicate": "can_query",
    "object": "acme.hr.performance",
    "confidence": 1.0,
    "source_quality": "verified",
    "valid_from": "2026-01-27T12:02:00Z",
    "valid_to": null
  },
  "logic_anchor": {
    "rule_id": "system:bridge_creation",
    "rule_logic_hash": "...",
    "interpreter": null
  },
  "evidence": [
    {
      "type": "approval",
      "description": "Source owner approval: role:vp_sales",
      "payload_hash": "sig_vp_sales_..."
    },
    {
      "type": "approval",
      "description": "Target owner approval: role:hr_director",
      "payload_hash": "sig_hr_director_..."
    },
    {
      "type": "purpose",
      "description": "Check rep performance for discount authority"
    }
  ],
  "proof": {
    "signer_id": "role:vp_sales,role:hr_director",
    "signature": "sig1|sig2"
  }
}
```

---

## Kernel Migration (v1.3)

v1.3 restructures the codebase into three layers:

1. **`kernel/`** — Domain-portable decision primitives (single source of truth)
2. **`domains/`** — Domain-specific implementations (banking AML, insurance claims)
3. **`decisiongraph/`** — Backward-compatible re-export shims (thin wrappers)

The migration was executed in two phases across 15 steps, with all 1,927
tests passing after every step.

### Phase 1 — Create Kernel & Domain Structure (Steps 1-7)

#### Step 1: `kernel/foundation/` (10 core modules)

Copied the domain-portable decision primitives into the kernel.

| Module | Lines | Purpose |
|--------|-------|---------|
| `cell.py` | 673 | DecisionCell, hashing, timestamps, CellType enum |
| `chain.py` | 658 | Append-only hash-linked chain with integrity verification |
| `genesis.py` | 369 | Genesis cell creation and validation |
| `namespace.py` | 160 | Hierarchical namespace validation |
| `scholar.py` | 433 | Precedent search and ranking |
| `signing.py` | 215 | Ed25519 signing and verification |
| `wal.py` | 383 | Write-ahead log for crash recovery |
| `segmented_wal.py` | 529 | Segment-based WAL with compaction |
| `judgment.py` | 589 | JudgmentPayload, AnchorFact, scenario codes |
| `canon.py` | 159 | Canonical JSON serialization |
| `exceptions.py` | 141 | Exception hierarchy |
| `policyhead.py` | 1,043 | Policy head management and verification |

**Commit:** `25c01ee`

#### Step 2: `kernel/precedent/` (6 modules)

Copied the precedent matching engine into the kernel.

| Module | Lines | Purpose |
|--------|-------|---------|
| `precedent_registry.py` | 510 | PrecedentRegistry with temporal queries |
| `precedent_scorer.py` | 579 | v3 similarity scoring (renamed from `precedent_scorer_v3`) |
| `governed_confidence.py` | 242 | Domain-governed confidence computation |
| `field_comparators.py` | 336 | Typed field comparison functions |
| `comparability_gate.py` | 231 | Gate-based precedent filtering |
| `domain_registry.py` | 321 | DomainRegistry protocol and field metadata |

**Commit:** `5bf1aa7`

#### Step 3: `kernel/evidence/` (2 modules)

| Module | Lines | Purpose |
|--------|-------|---------|
| `tribool.py` | ~80 | TriBool (TRUE/FALSE/UNKNOWN) with logic operators |
| `evidence_gate.py` | ~30 | Gate stub (placeholder for evidence gating) |

**Commit:** `8d625de`

#### Step 4: `kernel/policy/` (3 modules)

| Module | Lines | Purpose |
|--------|-------|---------|
| `regime_partitioner.py` | ~200 | Universal signal extraction, parameterized shift detection |
| `policy_simulation.py` | ~750 | PolicySimulator with draft comparison |
| `shift_tracker.py` | ~20 | Stub for future shift tracking |

#### Step 5: `kernel/calendars/` (3 modules)

| Module | Lines | Purpose |
|--------|-------|---------|
| `base.py` | ~150 | HolidayCalendar protocol, BaseCalendar ABC, NoHolidayCalendar |
| `us_federal.py` | ~100 | USFederalCalendar with floating holidays |
| `canada_ontario.py` | ~100 | OntarioCalendar with provincial holidays |

#### Step 6: `domains/banking_aml/` (stub)

Created domain directory with `__init__.py` and `MANIFEST.md`.

#### Step 7: `domains/insurance_claims/` (stub)

Created domain directory with `__init__.py` and `MANIFEST.md`.

**Steps 4-7 Commit:** `fc6667d`

### Test Infrastructure Fix (between phases)

Resolved 27 pre-existing test failures (19 fails + 5 errors + 3
collection errors) that predated the migration:

- **Root cause 1:** 3 test files used `from src.decisiongraph import ...`
  instead of `from decisiongraph import ...`
- **Root cause 2:** 24 tests failed because `service/` parent wasn't on
  `sys.path`
- **Fix:** Created `tests/conftest.py` with proper `sys.path` setup;
  fixed 3 test files' import paths

**Commit:** `25841d5`

### Phase 2 — Move Imports to Kernel Paths (Steps 1-8)

#### Step 1: Import Mapping

Catalogued 229 imports across the codebase to identify which could be
redirected to kernel paths.

#### Step 2: Foundation Modules to Re-export Shims (12 files)

Replaced 12 foundation implementation files (~8,259 lines) in
`decisiongraph/` with thin re-export shims (~108 lines total).

**Shim pattern:**
```python
"""Backward-compatible shim. Real implementation in kernel.foundation.cell."""
import kernel.foundation.cell as _mod  # noqa: E402
from kernel.foundation.cell import *  # noqa: F401,F403

# Re-export ALL public names (not just __all__)
_names = [_n for _n in dir(_mod) if not _n.startswith("_")]
for _n in _names:
    globals()[_n] = getattr(_mod, _n)
del _names, _n, _mod
```

The `globals()` injection is necessary because `from X import *` only
exports names in `__all__`, but many consumers import names not listed
there (e.g., `HashSchemeMismatch`, `SignatureInvalidError`).

**Files shimmed:** `cell.py`, `chain.py`, `genesis.py`, `namespace.py`,
`scholar.py`, `signing.py`, `wal.py`, `segmented_wal.py`, `judgment.py`,
`canon.py`, `exceptions.py`, `policyhead.py`

**Commit:** `7508a19`

#### Step 3: Precedent Modules to Re-export Shims (6 files)

Replaced 6 precedent implementation files (~1,739 lines) with shims.

Note: `precedent_scorer_v3.py` re-exports from `kernel.precedent.precedent_scorer`
(renamed in kernel — the `_v3` suffix was dropped).

**Commit:** `4c6cac7`

#### Step 4: Policy Simulation to Re-export Shim (1 file)

Replaced `policy_simulation.py` (~749 lines) with a shim pointing to
`kernel.policy.policy_simulation`.

**Commit:** `ccc7078`

#### Step 5: ClaimPilot Imports to Kernel Paths (6 files, 14 imports)

Updated ClaimPilot's internal imports to use kernel paths directly.

Note: ClaimPilot's `canon.py` was NOT deleted — it is an
insurance-specific module (`compute_policy_pack_hash`, `normalize_excerpt`,
`excerpt_hash`) unrelated to `kernel.foundation.canon`.

**Commit:** `87baeaa`

#### Step 6: Service Imports to Kernel Paths (3 files, 8 import groups)

Updated the main service entry points to import from kernel directly.
Banking-specific imports (`aml_*`, `banking_*`, `policy_shift_shadows`)
left at `decisiongraph.*` pending Step 7.

**Commit:** `53d5a61`

#### Step 7: Banking Modules to `domains/banking_aml/` (6 modules)

Moved banking-specific implementations out of `decisiongraph/` into
`domains/banking_aml/`, with re-export shims at old locations:

| Old Location | New Location | Lines |
|-------------|-------------|-------|
| `banking_field_registry.py` | `domains/banking_aml/field_registry.py` | 417 |
| `banking_domain.py` | `domains/banking_aml/domain.py` | 400 |
| `aml_seed_generator.py` | `domains/banking_aml/seed_generator.py` | 887 |
| `aml_fingerprint.py` | `domains/banking_aml/fingerprint.py` | 1,009 |
| `aml_reason_codes.py` | `domains/banking_aml/reason_codes.py` | 930 |
| `policy_shift_shadows.py` | `domains/banking_aml/policy_shifts.py` | 502 |

**Commit:** `baa6a35`

#### Step 8: Final Verification

All tests passing. Structure validated.

### Final Architecture

```
decisiongraph-complete/src/
├── kernel/                          # 26 modules — single source of truth
│   ├── foundation/   (11 modules)   # Decision primitives
│   ├── precedent/    (6 modules)    # Precedent matching engine
│   ├── policy/       (3 modules)    # Policy simulation & regime detection
│   ├── evidence/     (2 modules)    # Three-valued logic & evidence gating
│   └── calendars/    (3 modules)    # Jurisdiction-portable business days
│
├── domains/                         # 6 modules — domain-specific
│   ├── banking_aml/                 # Banking AML domain
│   │   ├── field_registry.py        #   28 canonical field definitions
│   │   ├── domain.py                #   DomainRegistry factory
│   │   ├── seed_generator.py        #   1,500 seed precedents (20 scenarios)
│   │   ├── fingerprint.py           #   Privacy-preserving fingerprint schemas
│   │   ├── reason_codes.py          #   ~92 reason codes with regulatory refs
│   │   └── policy_shifts.py         #   Policy shift shadow projections
│   └── insurance_claims/            # (stub — future)
│
└── decisiongraph/                   # 25 re-export shims — backward compat
    ├── cell.py          → kernel.foundation.cell
    ├── chain.py         → kernel.foundation.chain
    ├── genesis.py       → kernel.foundation.genesis
    ├── namespace.py     → kernel.foundation.namespace
    ├── scholar.py       → kernel.foundation.scholar
    ├── signing.py       → kernel.foundation.signing
    ├── wal.py           → kernel.foundation.wal
    ├── segmented_wal.py → kernel.foundation.segmented_wal
    ├── judgment.py      → kernel.foundation.judgment
    ├── canon.py         → kernel.foundation.canon
    ├── exceptions.py    → kernel.foundation.exceptions
    ├── policyhead.py    → kernel.foundation.policyhead
    ├── precedent_registry.py   → kernel.precedent.precedent_registry
    ├── precedent_scorer_v3.py  → kernel.precedent.precedent_scorer
    ├── governed_confidence.py  → kernel.precedent.governed_confidence
    ├── field_comparators.py    → kernel.precedent.field_comparators
    ├── comparability_gate.py   → kernel.precedent.comparability_gate
    ├── domain_registry.py      → kernel.precedent.domain_registry
    ├── policy_simulation.py    → kernel.policy.policy_simulation
    ├── banking_field_registry.py → domains.banking_aml.field_registry
    ├── banking_domain.py         → domains.banking_aml.domain
    ├── aml_seed_generator.py     → domains.banking_aml.seed_generator
    ├── aml_fingerprint.py        → domains.banking_aml.fingerprint
    ├── aml_reason_codes.py       → domains.banking_aml.reason_codes
    └── policy_shift_shadows.py   → domains.banking_aml.policy_shifts
```

### Migration Stats

| Metric | Count |
|--------|-------|
| Kernel modules | 26 |
| Domain modules | 6 |
| Re-export shims | 25 |
| Tests passing | 1,927 |
| Test failures | 0 |
| Commits (Phase 1) | 4 |
| Commits (Phase 2) | 6 |
| Commits (test fix) | 1 |

### Commit History

| Hash | Message |
|------|---------|
| `25c01ee` | feat: kernel migration step 1 — create kernel/foundation/ with 10 core modules |
| `5bf1aa7` | feat: kernel migration step 2 — create kernel/precedent/ with 6 modules |
| `8d625de` | feat: kernel migration step 3 — create kernel/evidence/ with TriBool + gate stub |
| `fc6667d` | feat: kernel migration steps 4-7 — policy, calendars, and domain stubs |
| `25841d5` | fix: resolve 27 test failures — add conftest.py and fix imports |
| `7508a19` | refactor: foundation modules -> kernel re-export shims |
| `4c6cac7` | refactor: precedent modules -> kernel re-export shims |
| `ccc7078` | refactor: policy simulation -> kernel re-export shim |
| `87baeaa` | refactor: ClaimPilot imports -> kernel paths |
| `53d5a61` | refactor: service imports -> kernel paths |
| `baa6a35` | refactor: move 6 banking modules to domains/banking_aml/ |

### Design Decisions

1. **Copy, don't move:** Source of truth moved to `kernel/` and `domains/`,
   old paths become shims. Zero breaking changes.

2. **`globals()` injection in shims:** `from X import *` only exports names
   in `__all__`. The shim uses `globals()[name] = getattr(module, name)` to
   re-export ALL public names, preserving full backward compatibility.

3. **`precedent_scorer_v3` renamed:** In kernel, the `_v3` suffix was
   dropped (`kernel.precedent.precedent_scorer`). The old shim maps the
   legacy name to the new location.

4. **ClaimPilot `canon.py` retained:** It is an insurance-specific module
   (policy pack hashing, excerpt normalization) — NOT a duplicate of
   `kernel.foundation.canon`.

5. **Banking modules not moved:** `engine.py`, `escalation_gate.py`,
   `str_gate.py`, `decision_pack.py` remain in `decisiongraph/` as they
   contain domain-portable logic that may move to kernel in a future phase.
