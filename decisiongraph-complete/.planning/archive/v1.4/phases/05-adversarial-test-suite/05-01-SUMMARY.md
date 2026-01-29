---
phase: 05-adversarial-test-suite
plan: 01
subsystem: security-testing
status: complete
completed: 2026-01-27

one_liner: "SEC-01/SEC-02 adversarial tests for injection and traversal attacks with DG_INPUT_INVALID verification"

tags:
  - adversarial-testing
  - input-validation
  - security
  - injection-prevention
  - traversal-prevention

requires:
  - "02-input-validation (validators module)"
  - "04-03-commit-gate (process_rfa entry point)"

provides:
  - "SEC-01 predicate/subject injection tests"
  - "SEC-02 namespace traversal tests"
  - "Parametrized attack vector organization"

affects:
  - "Phase 6: Lineage Visualizer (test suite provides security baseline)"

dependencies:
  tech-stack:
    added: []
    patterns:
      - "pytest.mark.parametrize for attack vector organization"
      - "Both exception type AND error code verification"
      - "End-to-end testing via process_rfa()"

key-files:
  created:
    - "tests/test_adversarial_injection.py"
    - "tests/test_adversarial_traversal.py"
  modified: []

decisions:
  - id: "parametrized-attack-vectors"
    what: "Use pytest.mark.parametrize to organize 60+ attack vectors"
    why: "Reduces test duplication, groups related attacks, provides clear failure messages"
    alternatives: "Separate test functions (more verbose, harder to maintain)"

  - id: "verify-error-code-and-type"
    what: "All tests verify both InputInvalidError exception AND DG_INPUT_INVALID code"
    why: "Exception type ensures proper error hierarchy, code ensures external API contract"
    alternatives: "Check only exception type (misses API contract verification)"

  - id: "end-to-end-rfa-tests"
    what: "Include process_rfa() tests alongside validator tests"
    why: "Validates full attack path from entry point to rejection"
    alternatives: "Test only validators (misses integration issues)"

metrics:
  duration: "4 minutes"
  tests_added: 114
  files_created: 2
  commits: 2
---

# Phase 05 Plan 01: Input Validation Adversarial Tests Summary

**Objective:** Create adversarial test files for SEC-01 predicate/subject injection and SEC-02 namespace traversal attack vectors.

## What Was Built

### SEC-01: Predicate/Subject Injection Tests (64 tests)

Created `tests/test_adversarial_injection.py` with comprehensive injection attack coverage:

**TestPredicateInjection (32 tests):**
- SQL-style injection: `can;drop table`, `can' OR '1'='1`, `can--comment`, `can/**/admin`
- Null byte injection: `can\x00drop`, `valid\x00; DROP TABLE`
- Newline injection: `can\nDROP TABLE`, `can\rADMIN`
- Space injection: `can access`, `has permission` (bypassing snake_case)
- Case bypass: `CAN_ACCESS`, `Can_Access`, `cAn_AcCeSs`
- Special characters: `can@admin`, `can#anchor`, `can$var`, `can/path`, `can:type`
- Control characters: `can\x01admin`, `can\x1Fadmin`, `can\x0Badmin`

**TestSubjectInjection (26 tests):**
- SQL injection: `user:alice;DROP TABLE`, `user:alice' OR '1'='1`
- Null byte: `user:alice\x00admin`, `user:\x00root`
- Case bypass: `USER:alice`, `user:ALICE`, `User:Alice`
- Format violations: `useralice`, `user:`, `:alice`
- Special characters: `user:alice;admin`, `user:alice@domain`
- Length attacks: `user:` + 129 chars, `user:` + 200 chars

**TestInjectionAtEngineLevel (6 tests):**
- End-to-end injection through `process_rfa()`
- Verifies validation happens BEFORE Scholar query
- Tests multiple simultaneous attack vectors
- Confirms success criteria: "can access" (space) fails with DG_INPUT_INVALID

### SEC-02: Namespace Traversal Tests (50 tests)

Created `tests/test_adversarial_traversal.py` with traversal attack coverage:

**TestNamespaceTraversalPatterns (37 tests):**
- Double-dot traversal: `corp..hr`, `corp..admin`, `sales..finance`
- Slash traversal: `corp/hr`, `corp/hr/payroll`, `sales/reports`
- Unix parent traversal: `corp/../admin`, `../etc/passwd`, `../../root`
- Windows traversal: `corp\hr`, `corp\..\admin`, `C:\corp\hr`
- Absolute paths: `/etc/passwd`, `/corp/hr`, `/admin`
- Trailing/leading dots: `corp.hr.`, `.hidden`, `..hidden`, `.corp.hr`
- Multiple dots: `corp...hr`, `corp....hr`, `a...b...c`
- Null byte: `corp.hr\x00admin`, `corp\x00/../admin`
- Semicolon: `corp.hr;admin`, `corp;DROP TABLE`
- Mixed attacks: `corp/hr;admin`, `corp\hr\x00`, `../corp.hr;DROP`

**TestNamespaceTraversalAtRFALevel (13 tests):**
- End-to-end traversal through `process_rfa()`
- Tests both `namespace` and `requester_namespace` fields
- Confirms success criteria: `corp..hr` and `corp/hr` fail with DG_INPUT_INVALID
- Verifies actionable error messages

## Key Implementation Details

### Attack Vector Organization

Used `pytest.mark.parametrize` extensively:

```python
@pytest.mark.parametrize("malicious_predicate,attack_type", [
    ("can;drop table", "SQL semicolon terminator"),
    ("can' OR '1'='1", "SQL quote injection"),
    # ... 30+ more attack vectors
])
def test_predicate_injection_rejected_at_validator(
    self, malicious_predicate: str, attack_type: str
) -> None:
    with pytest.raises(InputInvalidError) as exc_info:
        validate_predicate_field(malicious_predicate)

    # Verify error code is deterministic
    assert exc_info.value.code == "DG_INPUT_INVALID"
    assert exc_info.value.details.get("field") == "predicate"
```

### Dual Verification Pattern

Every test verifies BOTH:
1. **Exception type**: `InputInvalidError` (proper error hierarchy)
2. **Error code**: `DG_INPUT_INVALID` (external API contract)

This ensures:
- Internal error handling is correct (exception type)
- External developers get deterministic error codes (API contract)

### End-to-End Testing

Injection and traversal tests include end-to-end scenarios:

```python
def test_predicate_injection_blocked_at_rfa_entry(self) -> None:
    chain = create_chain("test_graph")

    malicious_rfa = {
        "namespace": "corp",
        "requester_namespace": "corp",
        "requester_id": "attacker:eve",
        "predicate": "can;drop table"  # Malicious predicate
    }

    with pytest.raises(InputInvalidError) as exc_info:
        process_rfa(chain, malicious_rfa)

    assert exc_info.value.code == "DG_INPUT_INVALID"
```

This verifies that validation happens at the RFA entry point, BEFORE Scholar query.

## Test Results

### Full Suite Verification

```bash
$ pytest tests/ -q --tb=no
======================= 488 passed, 8 warnings in 0.63s ========================
```

**Breakdown:**
- Existing baseline: 374 tests (342 from STATE.md + 32 from other Phase 5 plans)
- SEC-01 injection tests: 64 tests
- SEC-02 traversal tests: 50 tests
- **Total new tests from this plan: 114**
- **Total test suite: 488 tests (all passing)**

### Success Criteria Verification

All success criteria met:

- ✅ test_adversarial_injection.py created with SEC-01 tests
- ✅ test_adversarial_traversal.py created with SEC-02 tests
- ✅ Predicate injection attacks return DG_INPUT_INVALID (not passed to Scholar)
- ✅ Namespace traversal attacks return DG_INPUT_INVALID (no path traversal)
- ✅ All tests verify both exception type AND error code
- ✅ Existing tests remain passing (no regressions)
- ✅ Total test count increased from 374 → 488

### Specific Attack Verification

From plan success criteria:

```python
# Predicate "can access" (space) fails with DG_INPUT_INVALID
def test_space_in_predicate_specifically_rejected(self) -> None:
    rfa_with_space = {
        "namespace": "corp",
        "requester_namespace": "corp",
        "requester_id": "user:alice",
        "predicate": "can access"  # Space not allowed
    }

    with pytest.raises(InputInvalidError) as exc_info:
        process_rfa(chain, rfa_with_space)

    assert exc_info.value.code == "DG_INPUT_INVALID"
```

```python
# Namespace "corp..hr" fails with DG_INPUT_INVALID
def test_double_dot_traversal_in_namespace_field(self) -> None:
    malicious_rfa = {
        "namespace": "corp..hr",  # Double-dot traversal
        "requester_namespace": "corp",
        "requester_id": "attacker:eve"
    }

    with pytest.raises(InputInvalidError) as exc_info:
        process_rfa(chain, malicious_rfa)

    assert exc_info.value.code == "DG_INPUT_INVALID"
```

```python
# Namespace "corp/hr" fails with DG_INPUT_INVALID
def test_slash_traversal_in_namespace_field(self) -> None:
    malicious_rfa = {
        "namespace": "corp/hr",  # Slash instead of dot
        "requester_namespace": "corp",
        "requester_id": "attacker:eve"
    }

    with pytest.raises(InputInvalidError) as exc_info:
        process_rfa(chain, malicious_rfa)

    assert exc_info.value.code == "DG_INPUT_INVALID"
```

## Deviations from Plan

None - plan executed exactly as written.

## Security Insights

### Defense-in-Depth Validated

Tests confirm multi-layer security:

1. **Validator layer**: `validate_predicate_field()`, `validate_subject_field()`, `validate_namespace()`
2. **Engine layer**: `process_rfa()` calls validators before Scholar query
3. **Error handling**: All failures produce deterministic DG_INPUT_INVALID code

### Attack Surface Coverage

**Injection attacks blocked:**
- SQL injection (semicolons, quotes, comments)
- Null byte injection (string truncation)
- Control character injection (0x00-0x1F except tab/newline)
- Case bypass attempts (uppercase, mixed case)
- Special character injection (@, #, $, /, \, :, etc.)

**Traversal attacks blocked:**
- Double-dot traversal (corp..hr)
- Slash/backslash separators (corp/hr, corp\hr)
- Unix path traversal (corp/../admin, ../etc/passwd)
- Windows path traversal (corp\..\admin, C:\corp\hr)
- Absolute paths (/etc/passwd)
- Empty segment attacks (.corp, corp., corp..hr)
- Null byte truncation (corp.hr\x00admin)

### Validation Strength

Pre-compiled regex with `fullmatch()` provides:
- **No partial matches**: Entire string must match pattern
- **Length limits enforced**: Predicate max 64 chars, subject identifier max 128 chars
- **Strict character sets**: Lowercase only, specific allowed characters
- **Control char rejection**: Blocks 0x00-0x1F except tab/newline

## Next Phase Readiness

### Blockers

None.

### Concerns

None. All tests passing, no regressions.

### Recommendations

1. **Phase 5 remaining plans**: Continue with SEC-03 (integrity tests) and SEC-04 (tampering tests) if not already complete
2. **Phase 6**: Lineage visualizer can rely on this security baseline (488 passing tests)
3. **Future security testing**: Consider adding fuzzing tests with Hypothesis for additional coverage

## Artifacts

### Files Created

1. **tests/test_adversarial_injection.py** (389 lines)
   - 3 test classes
   - 64 tests total
   - Covers SEC-01 requirements

2. **tests/test_adversarial_traversal.py** (453 lines)
   - 2 test classes
   - 50 tests total
   - Covers SEC-02 requirements

### Commits

1. **c10bb0a**: "test(05-01): add SEC-01 predicate/subject injection tests"
   - Created test_adversarial_injection.py
   - 64 parametrized tests for injection attack vectors

2. **4534ff7**: "test(05-01): add SEC-02 namespace traversal tests"
   - Created test_adversarial_traversal.py
   - 50 tests for namespace traversal attack vectors

### Test Coverage

**SEC-01 Predicate/Subject Injection:**
- Predicate field: 32 attack vectors
- Subject field: 26 attack vectors
- End-to-end via process_rfa(): 6 integration tests

**SEC-02 Namespace Traversal:**
- Direct validation: 37 attack patterns
- End-to-end via process_rfa(): 13 integration tests

**Total:** 114 new tests, all passing
