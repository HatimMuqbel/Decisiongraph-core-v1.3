---
phase: 01-error-foundation
plan: 01
subsystem: exceptions
tags: [error-handling, exceptions, api-contract]
dependency-graph:
  requires: []
  provides: [DecisionGraphError, SchemaInvalidError, InputInvalidError, UnauthorizedError, IntegrityFailError, SignatureInvalidError, InternalError]
  affects: [01-02, 01-03, 02-01, 03-01, 04-01]
tech-stack:
  added: []
  patterns: [exception-hierarchy, error-codes, json-serialization]
key-files:
  created:
    - src/decisiongraph/exceptions.py
  modified:
    - src/decisiongraph/__init__.py
decisions:
  - id: ERR-01
    decision: "6 domain-specific error codes (DG_*) instead of HTTP status codes"
    rationale: "More actionable for external developers; maps to specific failure modes"
metrics:
  duration: "2 minutes"
  completed: "2026-01-27"
---

# Phase 1 Plan 1: Exception Hierarchy Summary

**One-liner:** DecisionGraphError base class with 6 DG_* error codes and JSON serialization for deterministic API responses.

## What Was Built

### Exception Hierarchy

Created `/workspaces/Decisiongraph-core-v1.3/decisiongraph-complete/src/decisiongraph/exceptions.py`:

1. **DecisionGraphError** (base class)
   - Attributes: `code`, `message`, `details`, `request_id`
   - Methods: `to_dict()`, `to_json()`, `__str__`, `__repr__`
   - Default code: `DG_INTERNAL_ERROR`

2. **Six subclasses** with distinct codes:
   | Class | Code | Purpose |
   |-------|------|---------|
   | `SchemaInvalidError` | `DG_SCHEMA_INVALID` | Missing fields, wrong types |
   | `InputInvalidError` | `DG_INPUT_INVALID` | Bad format, out of bounds |
   | `UnauthorizedError` | `DG_UNAUTHORIZED` | No permission, no bridge |
   | `IntegrityFailError` | `DG_INTEGRITY_FAIL` | Hash mismatch, chain break |
   | `SignatureInvalidError` | `DG_SIGNATURE_INVALID` | Invalid/missing signature |
   | `InternalError` | `DG_INTERNAL_ERROR` | Unexpected internal error |

### Public Exports

Updated `/workspaces/Decisiongraph-core-v1.3/decisiongraph-complete/src/decisiongraph/__init__.py`:
- All 7 exception classes exported via `from .exceptions import ...`
- Added to `__all__` list for explicit public API

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create exceptions.py with DecisionGraphError hierarchy | `6de9a43` | `src/decisiongraph/exceptions.py` |
| 2 | Export exceptions from package __init__.py | `6a87e54` | `src/decisiongraph/__init__.py` |

## Verification Results

- All 69 existing tests pass
- Exception hierarchy imports correctly from package
- `to_dict()` returns JSON-compatible dict with code, message, details
- `to_json()` returns valid JSON string
- `request_id` included in serialization when provided

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| ERR-01 | Use 6 domain-specific error codes | More actionable than HTTP codes; each maps to specific failure mode |

## Next Phase Readiness

**Ready for:** 01-02-PLAN.md (Exception Mapping)

**Dependencies provided:**
- `DecisionGraphError` base class for wrapping existing chain errors
- All 6 subclasses ready for mapping from Chain module errors

**No blockers.**
