# Phase 1 Plan 2: Exception Mapping Summary

> **One-liner:** EXCEPTION_MAP with 14 mappings and wrap_internal_exception() for API boundary error translation with traceback preservation

---

## Metadata

| Field | Value |
|-------|-------|
| Phase | 01-error-foundation |
| Plan | 02 |
| Status | Complete |
| Duration | ~2 minutes |
| Completed | 2026-01-27 |

---

## What Was Built

### EXCEPTION_MAP

A dictionary mapping 14 internal exception types to external DecisionGraphError subclasses:

| Internal Exception | External Error | DG Code |
|--------------------|----------------|---------|
| IntegrityViolation | IntegrityFailError | DG_INTEGRITY_FAIL |
| ChainBreak | IntegrityFailError | DG_INTEGRITY_FAIL |
| TemporalViolation | IntegrityFailError | DG_INTEGRITY_FAIL |
| GraphIdMismatch | IntegrityFailError | DG_INTEGRITY_FAIL |
| ChainError | IntegrityFailError | DG_INTEGRITY_FAIL |
| GenesisError | SchemaInvalidError | DG_SCHEMA_INVALID |
| GenesisValidationError | SchemaInvalidError | DG_SCHEMA_INVALID |
| GenesisViolation | SchemaInvalidError | DG_SCHEMA_INVALID |
| AccessDeniedError | UnauthorizedError | DG_UNAUTHORIZED |
| BridgeRequiredError | UnauthorizedError | DG_UNAUTHORIZED |
| BridgeApprovalError | UnauthorizedError | DG_UNAUTHORIZED |
| NamespaceError | UnauthorizedError | DG_UNAUTHORIZED |
| ValueError | InputInvalidError | DG_INPUT_INVALID |
| TypeError | InputInvalidError | DG_INPUT_INVALID |

### wrap_internal_exception()

A helper function that:
- Maps internal exceptions to appropriate DecisionGraphError subclass
- Falls back to InternalError for unknown exceptions
- Preserves `internal_error` (original exception type name) in details
- Preserves `failed_checks` from GenesisValidationError
- Supports optional `default_message`, `details`, and `request_id`
- Designed for use with `raise ... from e` to preserve traceback

---

## Files Changed

| File | Change |
|------|--------|
| `src/decisiongraph/exceptions.py` | Added EXCEPTION_MAP, wrap_internal_exception, imports from chain/namespace/genesis |
| `src/decisiongraph/__init__.py` | Export EXCEPTION_MAP and wrap_internal_exception |

---

## Commits

| Commit | Description |
|--------|-------------|
| 12561da | feat(01-02): add EXCEPTION_MAP and wrap_internal_exception |
| 27d0870 | feat(01-02): export EXCEPTION_MAP and wrap_internal_exception from package |

---

## Verification Results

- [x] EXCEPTION_MAP contains 14 mappings (all 12 internal types + ValueError + TypeError)
- [x] wrap_internal_exception returns correct subclass for each internal type
- [x] Unknown exceptions fall back to InternalError
- [x] Exception chaining with `raise ... from e` preserves traceback
- [x] Original exception type included in details.internal_error
- [x] failed_checks from GenesisValidationError preserved in details
- [x] All utilities exported from package
- [x] All 69 existing tests passing

---

## Deviations from Plan

None - plan executed exactly as written.

---

## Usage Example

```python
from src.decisiongraph import wrap_internal_exception, IntegrityFailError
from src.decisiongraph.chain import IntegrityViolation

try:
    chain.append(cell)
except IntegrityViolation as e:
    # Wrap for API response while preserving traceback
    raise wrap_internal_exception(
        e,
        details={"cell_id": cell.cell_id[:16]}
    ) from e
```

---

## Next Phase Readiness

Phase 4 (RFA Processing Layer) can now use:
- `EXCEPTION_MAP` to determine error types at API boundaries
- `wrap_internal_exception()` to convert internal exceptions to DG_* error codes
- Exception chaining to preserve debugging context

---

## Dependencies Satisfied

- [x] ERR-02: Exception mapping (internal -> external error codes)
- [x] 01-01 prerequisite: DecisionGraphError hierarchy exists
