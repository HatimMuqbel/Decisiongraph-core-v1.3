# Phase 5 Plan 01: Policy Integrity Checks Summary

**Completed:** 2026-01-28
**Duration:** ~10 minutes
**Outcome:** SUCCESS

## One-liner

Namespace validation (INT-03) and policy_hash verification (INT-02) with concurrent promotion race detection via prev_policy_head comparison.

## What Was Built

### INT-03: Namespace Validation in submit_promotion()
Added fail-fast validation that ensures all rule_ids belong to the target namespace:

1. **Rule existence check**: For each rule_id, look up via `chain.get_cell(rule_id)`. If None, raise `InputInvalidError("Rule {rule_id} not found")`.

2. **Namespace match check**: Verify `rule_cell.fact.namespace == namespace`. If mismatch, raise `InputInvalidError("Rule {rule_id} is from namespace {rule_cell.fact.namespace}, expected {namespace}")`.

This validation happens BEFORE creating PromotionRequest, preventing wasted witness signatures on invalid promotions.

### INT-02: policy_hash Verification in finalize_promotion()
Added call to `verify_policy_hash(policy_head)` after PolicyHead creation and before chain append:

```python
if not verify_policy_hash(policy_head):
    raise IntegrityFailError(
        message="PolicyHead policy_hash verification failed",
        details={"promotion_id": promotion_id, "cell_id": policy_head.cell_id}
    )
```

This catches any tampering between PolicyHead creation and append.

### Race Condition Detection
Added concurrent promotion detection via prev_policy_head comparison:

1. **At submit time**: Store expected prev_policy_head in `self._expected_prev_policy_head[promotion_id]`
2. **At finalize time**: Compare current policy head to expected
3. **If mismatch**: Raise `InputInvalidError("Concurrent promotion detected...")`
4. **Edge cases handled**:
   - First promotion (expected=None, current=None): NOT a race
   - Expected None but current exists: Race detected (another promotion finalized first)

### Test Coverage
Added `TestPolicyIntegrity` class with 9 new tests:

| Test | Validates |
|------|-----------|
| test_submit_promotion_rule_not_found | Rule ID not in chain raises InputInvalidError |
| test_submit_promotion_rule_wrong_namespace | Rule from wrong namespace raises InputInvalidError |
| test_submit_promotion_mixed_namespaces | Mixed namespace rules rejected |
| test_submit_promotion_all_rules_correct_namespace | Happy path succeeds |
| test_concurrent_promotion_race_detected | Concurrent promotion via prev_policy_head mismatch |
| test_first_promotion_no_race_false_positive | First promotion succeeds (no false positive) |
| test_sequential_promotions_no_race | Sequential promotions work correctly |
| test_race_detected_when_no_prev_becomes_some | Race when expected=None but policy exists |
| test_finalize_verifies_policy_hash_implicit | Hash verification passes for valid promotion |

Also updated all existing tests to use actual rule cells via `create_rule_cell()` helper.

## Files Modified

| File | Changes |
|------|---------|
| `src/decisiongraph/engine.py` | Added namespace validation in submit_promotion(), race detection and policy_hash verification in finalize_promotion(), new _expected_prev_policy_head dict, imported verify_policy_hash and IntegrityFailError |
| `tests/test_engine_promotion.py` | Added TestPolicyIntegrity class (9 tests), create_rule_cell() helper, updated all existing tests to use real rule cells |

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 553f9dd | feat(05-01) | Add policy integrity checks (INT-02, INT-03) |

## Test Results

```
tests/test_engine_promotion.py: 31 passed
Full suite: 724 passed, 8 warnings (pre-existing)
```

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Namespace validation at submit time | Fail fast - prevents wasted witness signatures |
| Store expected prev in dict on Engine | Simpler than modifying PromotionRequest dataclass |
| Clean up expected prev after finalize | Prevents memory leak for long-running engines |
| create_rule_cell() uses get_current_timestamp() | Ensures temporal ordering after genesis |

## Deviations from Plan

### [Rule 3 - Blocking] Fixed test helper timestamps

- **Found during:** Task 3 test execution
- **Issue:** Fixed timestamps (T1, T2, etc. from 2026-01-15) caused TemporalViolation when appending rule cells after Genesis (which uses current time)
- **Fix:** Changed `create_rule_cell()` to use `get_current_timestamp()` by default instead of fixed T1 timestamp
- **Files modified:** tests/test_engine_promotion.py
- **Commit:** Included in main commit

## Requirements Status

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| INT-02 | COMPLETE | verify_policy_hash() called in finalize_promotion() |
| INT-03 | COMPLETE | Namespace validation in submit_promotion() |
| INT-04 | ALREADY COMPLETE | Threshold check already in finalize_promotion() |

## Next Phase Readiness

**Phase 5 Plan 02** ready to proceed:
- INT-01 (PolicyHead signature verification) is the remaining integrity requirement
- Will need to store witness signatures in PolicyHead or create verification utility
- All infrastructure in place from this plan
