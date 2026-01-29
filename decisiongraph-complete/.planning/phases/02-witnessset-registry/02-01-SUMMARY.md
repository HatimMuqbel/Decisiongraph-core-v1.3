---
phase: 02-witnessset-registry
plan: 01
subsystem: witnessset-core
tags: [witnessset, validation, immutability, dataclass, frozen]

requires:
  - phase: 01-policyhead-foundation
    plan: 03
    provides: validate_threshold function
  - phase: existing
    provides: validate_namespace from cell.py
  - phase: existing
    provides: InputInvalidError from exceptions.py

provides:
  - WitnessSet frozen dataclass
  - Witness configuration for namespaces
  - Threshold and namespace validation
  - Immutable, hashable witness sets

affects:
  - phase: 02-witnessset-registry
    plan: 02
    reason: WitnessRegistry will use WitnessSet for lookups
  - phase: 03-submission
    reason: Submission workflow will validate against WitnessSet
  - phase: 04-collection
    reason: Collection will validate witness signatures against WitnessSet

tech-stack:
  added:
    - Python dataclasses with frozen=True
    - Tuple types for deep immutability
  patterns:
    - Frozen dataclass pattern (prevents mutation)
    - Tuple for immutable collections
    - Validation in __post_init__
    - Reuse of existing validation functions
    - InputInvalidError for validation failures

key-files:
  created:
    - src/decisiongraph/witnessset.py: "WitnessSet frozen dataclass (109 lines)"
    - tests/test_witnessset.py: "Comprehensive test suite (359 lines, 28 tests)"
  modified:
    - src/decisiongraph/__init__.py: "Added WitnessSet import and export"

decisions:
  - decision: Use frozen=True dataclass for WitnessSet
    rationale: "Prevents accidental mutation, makes WitnessSet hashable and thread-safe by design"
    alternatives: ["Regular dataclass with manual immutability", "Named tuple", "Custom class"]

  - decision: Store witnesses as tuple[str, ...] not list
    rationale: "Frozen dataclass only prevents field reassignment, not mutation of mutable field values. Tuple ensures deep immutability."
    alternatives: ["List with defensive copies", "Frozenset (loses ordering)"]

  - decision: Reuse validate_threshold from policyhead.py
    rationale: "Leverages existing Phase 1 validation logic, ensures consistency, avoids duplication"
    alternatives: ["Duplicate validation logic in WitnessSet", "Create shared validation module"]

  - decision: Raise InputInvalidError (DG_INPUT_INVALID) for validation failures
    rationale: "Consistent with existing v1.4 error code system for business logic validation failures"
    alternatives: ["ValueError", "Custom WitnessSetError"]

metrics:
  duration: "2 minutes"
  completed: "2026-01-28"
  test-count: 28
  test-coverage: "100% of WitnessSet creation, validation, immutability, equality, hashability"
  lines-added: 477
  commits: 3

checkpoints: []
auth-gates: []
---

# Phase 02 Plan 01: WitnessSet Creation Summary

**One-liner:** Immutable WitnessSet frozen dataclass with tuple witnesses, threshold validation via validate_threshold(), and comprehensive test coverage (28 tests)

## What Was Built

Created the WitnessSet frozen dataclass - the core data structure for defining witness configurations in Phase 2.

**Key accomplishments:**

1. **Immutable WitnessSet dataclass:**
   - `@dataclass(frozen=True, kw_only=True)` for immutability
   - Fields: namespace (str), witnesses (tuple[str, ...]), threshold (int)
   - Validates on construction via `__post_init__`
   - Hashable and thread-safe by design

2. **Validation reuse:**
   - Uses `validate_threshold()` from policyhead.py (Phase 1)
   - Uses `validate_namespace()` from cell.py (existing v1.3)
   - Raises `InputInvalidError` with DG_INPUT_INVALID code

3. **Deep immutability:**
   - frozen=True prevents field reassignment
   - tuple[str, ...] prevents witness list mutation
   - Together ensure true immutability

4. **Package integration:**
   - Exported from src/decisiongraph/__init__.py
   - Follows existing module structure
   - Grouped with Phase 2 (v1.5) additions

5. **Comprehensive tests:**
   - 28 tests covering all aspects
   - WIT-01: Creation (5 tests)
   - WIT-02: Validation (7 tests)
   - Immutability enforcement (4 tests)
   - Equality semantics (4 tests)
   - Hashability (3 tests)
   - Edge cases (5 tests)

## Requirements Completed

- ✅ **WIT-01**: WitnessSet creation with namespace, witnesses, threshold
- ✅ **WIT-02**: WitnessSet validation (threshold, namespace)

**Must-have truths verified:**
- ✅ User can create WitnessSet with namespace, witnesses, threshold
- ✅ WitnessSet rejects invalid threshold (0, negative, > witness count)
- ✅ WitnessSet rejects invalid namespace format
- ✅ WitnessSet is immutable (frozen dataclass)
- ✅ WitnessSet witnesses stored as tuple (not mutable list)

**Must-have artifacts delivered:**
- ✅ src/decisiongraph/witnessset.py (109 lines, exports WitnessSet)
- ✅ tests/test_witnessset.py (359 lines, 28 tests)

**Must-have key links established:**
- ✅ witnessset.py imports validate_threshold from policyhead.py
- ✅ witnessset.py imports InputInvalidError from exceptions.py
- ✅ __init__.py imports WitnessSet from witnessset.py

## Technical Implementation

**WitnessSet structure:**
```python
@dataclass(frozen=True, kw_only=True)
class WitnessSet:
    namespace: str
    witnesses: Tuple[str, ...]
    threshold: int

    def __post_init__(self):
        # Validate threshold
        is_valid, error_msg = validate_threshold(self.threshold, list(self.witnesses))
        if not is_valid:
            raise InputInvalidError(error_msg)

        # Validate namespace
        is_valid_ns = validate_namespace(self.namespace)
        if not is_valid_ns:
            raise InputInvalidError(...)
```

**Immutability enforcement:**
- frozen=True: `ws.threshold = 2` → FrozenInstanceError
- tuple witnesses: `ws.witnesses.append('x')` → AttributeError
- Hashable: Can be used in sets/dicts

**Validation integration:**
- Reuses validate_threshold() from Phase 1
- Checks: threshold >= 1, threshold <= len(witnesses)
- Reuses validate_namespace() from v1.3
- Checks: lowercase, alphanumeric, dots, no trailing dot

## Test Coverage

**28 tests, 100% pass rate:**

1. **TestWitnessSetCreation (5 tests):**
   - Basic creation, bootstrap mode (1-of-1), multi-witness (2-of-3)
   - Verify witnesses stored as tuple
   - Verify namespace preserved

2. **TestWitnessSetValidation (7 tests):**
   - Reject threshold=0, negative, exceeds witnesses
   - Reject empty witnesses, invalid namespace, trailing dot
   - Verify error code is DG_INPUT_INVALID

3. **TestWitnessSetImmutability (4 tests):**
   - Cannot modify namespace, threshold, witnesses
   - Tuple prevents append operation

4. **TestWitnessSetEquality (4 tests):**
   - Equal WitnessSets are equal
   - Different namespace/witnesses/threshold not equal

5. **TestWitnessSetHashable (3 tests):**
   - WitnessSet is hashable
   - Can use in set
   - Equal WitnessSets have same hash

6. **TestWitnessSetEdgeCases (5 tests):**
   - Single witness max threshold (1-of-1)
   - All witnesses required (unanimous)
   - Hierarchical namespace, witnesses with underscores, namespace with numbers

**No regressions:** All 618 existing tests pass + 28 new = 646 total

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

**1. Frozen dataclass over regular dataclass:**
- **Why:** Immutability by default, hashable, thread-safe
- **Trade-off:** Cannot modify after creation (this is the goal)
- **Impact:** WitnessSet can be used in sets/dicts, safe for concurrent access

**2. Tuple not list for witnesses:**
- **Why:** frozen=True only prevents field reassignment, not list mutation
- **Example:** With list: `ws.witnesses = []` fails, but `ws.witnesses.append()` succeeds
- **Solution:** Tuple prevents both field reassignment and mutation
- **Impact:** True deep immutability

**3. Reuse existing validation functions:**
- **Why:** DRY principle, consistency with Phase 1
- **Functions reused:** validate_threshold() from policyhead.py, validate_namespace() from cell.py
- **Impact:** Same validation rules across PolicyHead and WitnessSet

**4. InputInvalidError for validation failures:**
- **Why:** Consistent with v1.4 error code system
- **Code:** DG_INPUT_INVALID
- **Category:** Business logic validation (not schema, not security)

## Next Phase Readiness

**Ready for 02-02 (WitnessRegistry):**
- ✅ WitnessSet dataclass complete
- ✅ Validation integrated
- ✅ Immutability enforced
- ✅ Hashability confirmed (can be used as dict key/set member)

**WitnessRegistry can now:**
- Store WitnessSet instances by namespace
- Use namespace as lookup key
- Validate threshold configurations
- Ensure immutable witness configurations

**No blockers for Phase 2 continuation.**

## Performance Notes

**Duration:** ~2 minutes
- Task 1: Create WitnessSet (~30 seconds)
- Task 2: Export from package (~15 seconds)
- Task 3: Create tests (~45 seconds)
- Verification: All tests pass in 0.89s

**Test performance:**
- 28 new tests: 0.08s
- Full regression suite (646 tests): 0.89s
- No performance degradation

## Files Modified

**Created:**
- `src/decisiongraph/witnessset.py` (109 lines)
- `tests/test_witnessset.py` (359 lines)

**Modified:**
- `src/decisiongraph/__init__.py` (+5 lines)

**Total:** +473 lines (implementation + tests)

## Commits

1. **ceecd95** - feat(02-01): create WitnessSet frozen dataclass
   - Immutable WitnessSet with frozen=True and tuple witnesses
   - Validates threshold and namespace on construction

2. **916d226** - feat(02-01): export WitnessSet from package root
   - Added WitnessSet import and export to __init__.py
   - Follows existing module structure

3. **a7de307** - test(02-01): add comprehensive WitnessSet test suite
   - 28 tests covering creation, validation, immutability, equality, hashability
   - 100% pass rate, no regressions

---

**Phase 02 Plan 01: COMPLETE** ✅

WitnessSet frozen dataclass operational with comprehensive validation and test coverage.
Ready for WitnessRegistry implementation (Plan 02-02).
