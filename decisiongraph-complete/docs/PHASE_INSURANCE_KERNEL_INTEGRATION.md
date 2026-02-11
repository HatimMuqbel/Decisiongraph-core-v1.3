# Phase: Insurance Kernel Integration

**Goal:** Integrate ClaimPilot with the kernel layer — eliminate duplicates, redirect imports to kernel paths, and move insurance-specific modules into `domains/insurance_claims/`.

**Precondition:** Banking kernel migration complete (Phase 2, 11 commits, all 1,927 tests passing).

---

## Current State

```
claimpilot/                          # Standalone — 41 source files
├── src/claimpilot/
│   ├── canon.py                     # Duplicate of kernel.foundation.canon + insurance extras
│   ├── exceptions.py                # Insurance-specific errors (CP_*)
│   ├── models/                      # 9 files — TriBool duplicated from kernel
│   │   ├── conditions.py            #   TriBool (lines 31–156) = kernel/evidence/tribool.py
│   │   ├── policy.py, claim.py, evidence.py, authority.py, ...
│   │   └── enums.py                 #   LineOfBusiness, ClaimantType, etc.
│   ├── engine/                      # 8 files — insurance business logic
│   ├── calendars/                   # 4 files — identical logic to kernel/calendars/
│   │   ├── base.py                  #   = kernel/calendars/base.py (+ better docs)
│   │   ├── us_federal.py            #   = kernel/calendars/us_federal.py (+ better docs)
│   │   └── canada_ontario.py        #   = kernel/calendars/canada_ontario.py (+ better docs)
│   ├── packs/                       # 3 files — YAML policy pack loading
│   └── precedent/                   # 11 files — insurance precedent system
│       ├── precedent_query.py       #   imports kernel.precedent.precedent_registry
│       ├── finalization_gate.py     #   imports kernel.foundation.judgment, cell
│       ├── seed_generator.py        #   imports kernel.foundation.judgment
│       ├── seed_loader.py           #   imports kernel.foundation.judgment
│       ├── lookback_service.py      #   imports kernel.foundation.chain
│       └── ...
└── api/
    └── main.py                      # imports kernel.foundation.chain, cell, judgment

domains/insurance_claims/            # STUB — __init__.py + MANIFEST.md only
```

### Duplications Identified

| ClaimPilot Module | Kernel Module | Status |
|-------------------|---------------|--------|
| `calendars/base.py` (263 lines) | `kernel/calendars/base.py` (158 lines) | Identical logic, ClaimPilot has better docstrings |
| `calendars/us_federal.py` (283 lines) | `kernel/calendars/us_federal.py` (134 lines) | Identical logic, ClaimPilot has better docstrings |
| `calendars/canada_ontario.py` (344 lines) | `kernel/calendars/canada_ontario.py` (186 lines) | Identical logic, ClaimPilot has better docstrings |
| `models/conditions.py` lines 31–156 | `kernel/evidence/tribool.py` (148 lines) | Identical TriBool copy |
| `canon.py` (shared functions) | `kernel/foundation/canon.py` (159 lines) | Partial overlap — ClaimPilot adds `compute_policy_pack_hash`, `normalize_excerpt`, `excerpt_hash` |

### Kernel Imports (already present, 6 files)

All precedent files use `try/except` with fallback stubs — graceful degradation if kernel unavailable. Only `api/main.py` imports unconditionally.

---

## Integration Steps

### Step 1: Upgrade Kernel Calendars with ClaimPilot Docstrings

ClaimPilot's calendar implementations have identical logic but significantly better documentation. Copy the enhanced docstrings into the kernel versions.

**Files modified:**
- `kernel/calendars/base.py` — adopt ClaimPilot's docstrings
- `kernel/calendars/us_federal.py` — adopt ClaimPilot's docstrings
- `kernel/calendars/canada_ontario.py` — adopt ClaimPilot's docstrings

**Then:** Replace ClaimPilot's calendar implementations with re-export shims:

```python
# claimpilot/src/claimpilot/calendars/base.py
"""Shim. Real implementation in kernel.calendars.base."""
from kernel.calendars.base import *  # noqa: F401,F403
```

Same pattern for `us_federal.py` and `canada_ontario.py`.

**Test:** All ClaimPilot calendar tests pass with kernel imports.

---

### Step 2: Consolidate TriBool into Kernel

`kernel/evidence/tribool.py` and `claimpilot/models/conditions.py` lines 31–156 are identical. Remove the duplicate.

**Files modified:**
- `claimpilot/src/claimpilot/models/conditions.py` — replace inline TriBool with:
  ```python
  from kernel.evidence.tribool import TriBool
  ```
  Keep the rest of conditions.py (EvaluationResult, Predicate, Condition, helper functions).

**Test:** All ClaimPilot tests using TriBool pass.

---

### Step 3: Consolidate Canon

ClaimPilot's `canon.py` contains:
- **Shared:** `canonical_json_bytes`, `content_hash`, `text_hash` — duplicates of `kernel.foundation.canon`
- **Insurance-specific:** `compute_policy_pack_hash`, `normalize_excerpt`, `excerpt_hash`

**Action:**
- Import shared functions from kernel
- Keep insurance-specific functions in ClaimPilot's `canon.py`

```python
# claimpilot/src/claimpilot/canon.py
"""Insurance-specific canonicalization. Shared primitives from kernel."""
from kernel.foundation.canon import canonical_json_bytes, content_hash, text_hash  # noqa: F401

# Insurance-specific (not in kernel)
def compute_policy_pack_hash(pack_data: dict) -> str: ...
def normalize_excerpt(text: str) -> str: ...
def excerpt_hash(text: str) -> str: ...
```

**Test:** All ClaimPilot canon consumers pass.

---

### Step 4: Remove Try/Except Guards from Kernel Imports

5 ClaimPilot precedent files wrap kernel imports in `try/except` with fallback stubs. Now that kernel is the established source of truth, remove the guards and import unconditionally.

**Files modified (5):**
- `precedent/precedent_query.py`
- `precedent/finalization_gate.py`
- `precedent/seed_generator.py`
- `precedent/seed_loader.py`
- `precedent/lookback_service.py`

**Before:**
```python
try:
    from kernel.foundation.judgment import AnchorFact, JudgmentPayload
except ImportError:
    AnchorFact = None  # stub
    JudgmentPayload = None  # stub
```

**After:**
```python
from kernel.foundation.judgment import AnchorFact, JudgmentPayload
```

**Test:** All ClaimPilot precedent tests pass.

---

### Step 5: Move Insurance Modules to `domains/insurance_claims/`

Move insurance-specific implementations from `claimpilot/src/claimpilot/` into `domains/insurance_claims/`, following the same pattern as banking AML migration.

**Modules to move:**

| Source | Destination | Lines |
|--------|-------------|-------|
| `engine/policy_engine.py` | `domains/insurance_claims/engine/policy_engine.py` | ~400 |
| `engine/context_resolver.py` | `domains/insurance_claims/engine/context_resolver.py` | ~300 |
| `engine/condition_evaluator.py` | `domains/insurance_claims/engine/condition_evaluator.py` | ~350 |
| `engine/recommendation_builder.py` | `domains/insurance_claims/engine/recommendation_builder.py` | ~600 |
| `engine/evidence_gate.py` | `domains/insurance_claims/engine/evidence_gate.py` | ~400 |
| `engine/authority_router.py` | `domains/insurance_claims/engine/authority_router.py` | ~250 |
| `engine/timeline_calculator.py` | `domains/insurance_claims/engine/timeline_calculator.py` | ~300 |
| `engine/precedent_finder.py` | `domains/insurance_claims/engine/precedent_finder.py` | ~200 |
| `models/*.py` (8 files, not conditions.py TriBool) | `domains/insurance_claims/models/` | ~2,000 |
| `packs/loader.py` | `domains/insurance_claims/packs/loader.py` | ~300 |
| `packs/schema.py` | `domains/insurance_claims/packs/schema.py` | ~200 |
| `precedent/fingerprint_schema.py` | `domains/insurance_claims/precedent/fingerprint_schema.py` | ~734 |
| `precedent/reason_code_registry.py` | `domains/insurance_claims/precedent/reason_code_registry.py` | ~1,064 |
| `precedent/banding_library.py` | `domains/insurance_claims/precedent/banding_library.py` | ~1,095 |
| `precedent/lookback_service.py` | `domains/insurance_claims/precedent/lookback_service.py` | ~575 |
| `precedent/seed_generator.py` | `domains/insurance_claims/precedent/seed_generator.py` | ~586 |
| `precedent/seed_loader.py` | `domains/insurance_claims/precedent/seed_loader.py` | ~498 |
| `precedent/finalization_gate.py` | `domains/insurance_claims/precedent/finalization_gate.py` | ~479 |
| `precedent/precedent_query.py` | `domains/insurance_claims/precedent/precedent_query.py` | ~768 |
| `exceptions.py` | `domains/insurance_claims/exceptions.py` | ~100 |

**Not moved** (stays in `claimpilot/`):
- `canon.py` — hybrid (kernel imports + insurance-specific functions)
- `models/conditions.py` — TriBool imports from kernel, Condition/Predicate are portable
- `precedent/cli.py` — CLI tooling, not domain logic
- `api/` — API layer stays as service entry point

**Internal imports updated** within moved files to use `domains.insurance_claims.*` paths.

---

### Step 6: Create Re-export Shims in ClaimPilot

Replace moved files with thin shims so existing `claimpilot.*` imports keep working.

**Shim pattern** (same as banking migration):
```python
"""Backward-compatible shim. Real implementation in domains.insurance_claims.engine.policy_engine."""
import domains.insurance_claims.engine.policy_engine as _mod  # noqa: E402
from domains.insurance_claims.engine.policy_engine import *  # noqa: F401,F403

_names = [_n for _n in dir(_mod) if not _n.startswith("_")]
for _n in _names:
    globals()[_n] = getattr(_mod, _n)
del _names, _n, _mod
```

**Test:** All existing `from claimpilot.engine import ...` imports still work.

---

### Step 7: Update API Imports

Update `claimpilot/api/main.py` and `api/routes/*.py` to import from `domains.insurance_claims.*` and `kernel.*` directly where practical.

---

### Step 8: Final Verification

- All ClaimPilot tests pass
- All banking tests pass (no regressions)
- No duplicate source-of-truth files remain
- `domains/insurance_claims/` contains insurance-specific logic
- `kernel/` remains domain-portable
- `claimpilot/` shims preserve backward compatibility

---

## Dependency After Integration

```
kernel/                              # Source of truth — domain-portable
├── foundation/  (11 modules)
├── precedent/   (6 modules)
├── policy/      (3 modules)
├── evidence/    (2 modules)         # TriBool used by both domains
└── calendars/   (3 modules)         # Enhanced with ClaimPilot docstrings

domains/
├── banking_aml/     (6 modules)     # Banking AML — imports kernel.*
└── insurance_claims/                # Insurance Claims — imports kernel.*
    ├── engine/      (8 modules)     #   policy engine, evidence gate, etc.
    ├── models/      (8 modules)     #   claim, policy, evidence, etc.
    ├── packs/       (2 modules)     #   YAML policy pack loading
    ├── precedent/   (9 modules)     #   fingerprints, banding, seeds, etc.
    └── exceptions.py

claimpilot/                          # Re-export shims + API layer
├── src/claimpilot/
│   ├── canon.py                     # Hybrid: kernel imports + insurance extras
│   ├── models/conditions.py         # TriBool from kernel + Condition/Predicate
│   ├── engine/*.py                  # Shims → domains.insurance_claims.engine.*
│   ├── models/*.py                  # Shims → domains.insurance_claims.models.*
│   ├── packs/*.py                   # Shims → domains.insurance_claims.packs.*
│   ├── precedent/*.py               # Shims → domains.insurance_claims.precedent.*
│   └── calendars/*.py               # Shims → kernel.calendars.*
└── api/                             # FastAPI service (not moved)
```

## Risk Notes

1. **ClaimPilot precedent ≠ kernel precedent.** The kernel precedent system (6 modules, 1.7K LOC) provides low-level matching primitives. ClaimPilot's precedent system (10 modules, 6.5K LOC) is a high-level insurance-specific decision support layer built on top. They are complementary, not duplicates.

2. **TriBool consumers.** `conditions.py` re-exports TriBool and builds on it (EvaluationResult, Predicate, Condition). After Step 2, verify all `from claimpilot.models.conditions import TriBool` still resolves.

3. **Canon partial overlap.** ClaimPilot's `canon.py` keeps insurance-specific functions (`compute_policy_pack_hash`, `normalize_excerpt`, `excerpt_hash`). These must NOT be deleted — only the shared primitives redirect to kernel.

4. **sys.path requirements.** Both `kernel/` and `domains/` must be on `sys.path`. Verify `conftest.py` or `PYTHONPATH` covers this for ClaimPilot tests.

5. **Step ordering matters.** Steps 1–4 (consolidate duplicates, clean imports) must complete before Step 5 (move files). Moving files before cleaning imports creates circular dependency risk.
