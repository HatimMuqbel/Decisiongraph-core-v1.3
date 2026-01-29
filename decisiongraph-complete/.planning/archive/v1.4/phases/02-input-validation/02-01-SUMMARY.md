---
phase: 02-input-validation
plan: 01
subsystem: validation
tags: [security, input-validation, regex, pytest]

# Dependency graph
requires:
  - 01-01 (InputInvalidError from error codes)
provides:
  - Input validation functions for RFA layer
  - Subject/predicate/object field validation
  - Control character detection
  - Pre-compiled regex patterns for performance
affects:
  - Phase 4 (RFA Processing Layer uses these validators)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Pre-compiled regex at module level for performance
    - fullmatch() instead of match() for security (complete string match)
    - Length checks before pattern matching (security: prevent huge input processing)
    - Actionable error messages with pattern/example/constraint info

# File tracking
key-files:
  created:
    - src/decisiongraph/validators.py
    - tests/test_validators.py
  modified: []

# Decisions
decisions:
  - id: control-chars-allowed
    choice: "Allow TAB (0x09) and NEWLINE (0x0A) in object field"
    reason: "Common in multi-line values and structured text; other control chars blocked"
  - id: length-check-first
    choice: "Check length before control chars for object validation"
    reason: "Security: prevent processing huge inputs before regex matching"
  - id: fullmatch-not-match
    choice: "Use re.fullmatch() instead of re.match()"
    reason: "Security: ensures entire string matches pattern, not just prefix"

# Metrics
metrics:
  duration: "2m 15s"
  completed: "2026-01-27"
  tests_added: 154
  total_tests: 281
  lines_added: 762
---

# Phase 2 Plan 1: Input Validation Summary

**One-liner:** Pre-compiled regex validators for subject/predicate/object fields with 154 parametrized tests covering VAL-01 through VAL-04 requirements.

## What Was Built

### Validation Module: src/decisiongraph/validators.py (262 lines)

**Module-level Constants:**
- `SUBJECT_PATTERN` - `^[a-z_]+:[a-z0-9_./-]{1,128}$` (VAL-01)
- `PREDICATE_PATTERN` - `^[a-z_][a-z0-9_]{0,63}$` (VAL-02)
- `CONTROL_CHARS_PATTERN` - `[\x00-\x08\x0B-\x1F]` (VAL-04)
- `MAX_OBJECT_LENGTH` - 4096 (VAL-03)

**Functions:**
1. `contains_control_chars(text)` - Helper to detect disallowed control chars
2. `validate_subject_field(subject, field_name)` - VAL-01 validation
3. `validate_predicate_field(predicate, field_name)` - VAL-02 validation
4. `validate_object_field(obj, field_name)` - VAL-03/VAL-04 validation

**Error Format:**
All validation errors raise `InputInvalidError` with:
- Error code: `DG_INPUT_INVALID`
- Actionable message: "does not match required format... Example: 'user:alice_123'"
- Details dict: `{field, value, pattern, constraint}`

### Test Suite: tests/test_validators.py (500 lines, 154 tests)

**Test Classes:**

1. **TestSubjectValidation** (24 tests)
   - 13 valid cases: user:alice, paths, dots, hyphens, underscores
   - 19 invalid cases: empty, no colon, uppercase, too long, control chars
   - Actionable error message validation
   - Custom field_name support
   - Value truncation in error details

2. **TestPredicateValidation** (21 tests)
   - 12 valid cases: snake_case, underscores, digits, single char
   - 17 invalid cases: uppercase, spaces, hyphens, dots, too long
   - Error message format validation

3. **TestObjectValidation** (19 tests)
   - 12 valid cases: typed IDs, JSON, tabs, newlines
   - 14 invalid cases: empty, too long, control chars
   - Length check priority verification
   - Custom field_name support

4. **TestControlCharacterDetection** (37 tests)
   - All 30 disallowed chars (0x00-0x08, 0x0B-0x1F) detected
   - TAB (0x09) and NEWLINE (0x0A) allowed
   - Mixed content detection

5. **TestErrorCodeIntegration** (5 tests)
   - DG_INPUT_INVALID code on all validation errors
   - to_dict() and to_json() serialization

6. **TestConstantsAndPatterns** (4 tests)
   - Constants have correct values
   - Patterns are compiled regex objects

7. **TestEdgeCases** (11 tests)
   - Boundary conditions: 128/129 chars, 64/65 chars, 4096/4097 chars
   - Unicode handling, multiple colons, underscore edge cases

## Verification Results

```
========== 281 tests collected ==========
- 127 original tests: PASSED
- 154 new validator tests: PASSED
- Total: 281 passed, 8 warnings
```

Requirements verified:
- VAL-01: Subject `user:alice_123` passes; `USER:Alice` raises DG_INPUT_INVALID
- VAL-02: Predicate `can_access` passes; `can access` raises DG_INPUT_INVALID
- VAL-03: Object >4096 chars raises DG_INPUT_INVALID
- VAL-04: Control char `\x00` raises DG_INPUT_INVALID; tab/newline allowed

## Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Regex compilation | Module-level pre-compilation | Performance: avoid recompilation per call |
| Pattern matching | fullmatch() not match() | Security: ensure entire string matches |
| Length check order | Check length FIRST | Security: prevent huge input regex processing |
| Control chars | Allow 0x09/0x0A only | Tab and newline common in structured text |
| Error truncation | Truncate value to 100 chars | Security: prevent huge values in error logs |

## Deviations from Plan

None - plan executed exactly as written.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| f3957ee | feat | Add input validation module |
| 0546d38 | test | Add comprehensive validator test suite |

## Files Changed

```
src/decisiongraph/validators.py  (created, 262 lines)
tests/test_validators.py         (created, 500 lines)
```

## Success Criteria Met

| Criteria | Status |
|----------|--------|
| validators.py exists with all validation functions | PASSED |
| All 4 VAL requirements implemented | PASSED |
| Validation errors raise InputInvalidError with DG_INPUT_INVALID | PASSED |
| Error messages are actionable | PASSED |
| Test suite covers valid and invalid cases | PASSED (154 tests) |
| All 127+ existing tests remain passing | PASSED (127/127) |
| New tests pass | PASSED (154/154) |

## Phase 2 Progress

With this plan complete:
- Plan 02-01: Input Validation COMPLETE

**Phase 2 Input Validation: COMPLETE** (1/1 plans)

Ready for Phase 3: Signing Utilities
