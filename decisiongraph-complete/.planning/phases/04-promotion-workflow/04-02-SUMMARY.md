---
phase: 04-promotion-workflow
plan: 02
subsystem: engine
tags: [engine, promotion, signature-collection, authorization, witness-verification, ed25519]

# Dependency graph
requires:
  - phase: 04-promotion-workflow
    plan: 01
    provides: PromotionRequest dataclass, PromotionStatus enum
  - phase: 02-witnessset-registry
    provides: WitnessRegistry.get_witness_set()
provides:
  - Engine.submit_promotion() for PRO-01
  - Engine.collect_witness_signature() for PRO-02, PRO-05, PRO-06
  - Authorization check before signature verification pattern
affects: [04-promotion-workflow, 05-witness-approval]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Authorization check BEFORE signature verification (security)"
    - "verify_signature returns bool, explicit error raising required"
    - "Status state machine: PENDING -> COLLECTING -> THRESHOLD_MET"
    - "Dict-based signature storage prevents duplicate witness signatures"

key-files:
  created:
    - tests/test_engine_promotion.py
  modified:
    - src/decisiongraph/engine.py

key-decisions:
  - "Authorization check before signature verification (PRO-05 before PRO-06)"
  - "verify_signature returns False not exception - explicit SignatureInvalidError raise"
  - "Duplicate witness signature overwrites previous (idempotent behavior)"
  - "Single-witness threshold=1 goes directly to THRESHOLD_MET (skips COLLECTING)"

patterns-established:
  - "Authorization-then-verification: check witness in WitnessSet BEFORE verifying signature"
  - "Explicit error conversion: verify_signature returns bool, caller raises SignatureInvalidError"
  - "Engine as promotion API: submit_promotion() and collect_witness_signature()"
  - "WitnessRegistry injection: Engine creates registry from chain for witness lookups"

# Metrics
duration: 3.2min
completed: 2026-01-28
---

# Phase 04 Plan 02: Signature Collection Engine Summary

**Engine.submit_promotion() creates PromotionRequest from WitnessSet threshold; Engine.collect_witness_signature() validates authorization first, then verifies Ed25519 signature, stores signature, and updates status to COLLECTING or THRESHOLD_MET**

## Performance

- **Duration:** 3.2 min
- **Started:** 2026-01-28T06:00:00Z
- **Completed:** 2026-01-28T06:03:12Z
- **Tasks:** 3
- **Files created:** 1
- **Files modified:** 1

## Accomplishments
- Engine.submit_promotion() creates PromotionRequest with threshold from WitnessSet (PRO-01)
- Engine.collect_witness_signature() validates authorization, verifies signature, updates status (PRO-02, PRO-05, PRO-06)
- Authorization check BEFORE signature verification (security pattern)
- Status transitions: PENDING -> COLLECTING (first sig) -> THRESHOLD_MET (threshold reached)
- All 707 tests pass (693 existing + 14 new engine promotion tests)

## Task Commits

Each task was committed atomically:

1. **Task 1+2: Add submit_promotion() and collect_witness_signature() to Engine** - `2f769e9` (feat)
2. **Task 3: Create comprehensive tests for Engine promotion workflow** - `d9de03e` (test)

## Files Created/Modified
- `src/decisiongraph/engine.py` - Added submit_promotion(), collect_witness_signature(), _promotions storage, _registry
- `tests/test_engine_promotion.py` - 14 comprehensive tests covering submit, collect, authorization, signature verification

## Decisions Made

**1. Authorization check BEFORE signature verification (PRO-05 before PRO-06)**
- **Rationale:** Unauthorized witnesses should be rejected without triggering signature verification
- **Security:** Prevents information leakage about signature validity for unauthorized parties
- **Pattern:** Always check authorization first, then verify credentials

**2. verify_signature returns bool, explicit SignatureInvalidError required**
- **Rationale:** verify_signature() from signing module returns False, not exception
- **Implementation:** Explicitly check `if not is_valid:` and raise SignatureInvalidError
- **Consistency:** Matches existing v1.4 signing module behavior

**3. Duplicate witness signature overwrites previous**
- **Rationale:** Idempotent behavior - same witness can resubmit without error
- **Implementation:** Dict storage: `promotion.signatures[witness_id] = signature`
- **UX:** Allows witnesses to retry with different keys if needed

**4. Single-witness threshold=1 skips COLLECTING**
- **Rationale:** When threshold=1, first signature immediately meets threshold
- **Implementation:** Both status transitions checked sequentially
- **Result:** Status goes PENDING -> THRESHOLD_MET directly

## Deviations from Plan

None - plan executed exactly as written

## Issues Encountered

**1. [Rule 3 - Blocking] create_chain() already creates Genesis**
- **Found during:** Task 3 test execution
- **Issue:** Test helper used create_chain() which already initializes with Genesis, then tried to append WitnessSet Genesis
- **Fix:** Changed test helper to use Chain() directly (empty chain) instead of create_chain()
- **Commit:** Included in test commit

## Test Coverage Summary

**TestSubmitPromotion** (5 tests)
- test_submit_promotion_returns_promotion_id: Returns valid UUID string
- test_submit_promotion_stores_request: PromotionRequest stored in _promotions
- test_submit_promotion_uses_witness_threshold: Threshold comes from WitnessSet
- test_submit_promotion_invalid_namespace: Raises InputInvalidError for invalid namespace
- test_submit_promotion_no_witness_set: Raises InputInvalidError when no WitnessSet configured

**TestCollectWitnessSignature** (9 tests)
- test_collect_signature_stores_signature: Signature stored in promotion.signatures
- test_collect_signature_updates_status_to_collecting: First sig transitions to COLLECTING
- test_collect_signature_threshold_met: Reaching threshold transitions to THRESHOLD_MET
- test_collect_signature_unauthorized_witness: Raises UnauthorizedError (PRO-05)
- test_collect_signature_invalid_signature: Raises SignatureInvalidError (PRO-06)
- test_collect_signature_promotion_not_found: Raises InputInvalidError
- test_collect_signature_duplicate_witness_overwrites: Duplicate witness overwrites previous
- test_collect_signature_single_witness_threshold_met_immediately: threshold=1 goes to THRESHOLD_MET
- test_authorization_checked_before_signature_verification: Authorization before verification

## Test Results

- **Total tests:** 707 (693 existing + 14 new)
- **All tests passing:** Yes
- **Regressions:** 0
- **Warnings:** 8 (pre-existing from test_scholar.py return statements)

## Requirements Completed

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| PRO-01 | Complete | Engine.submit_promotion() creates PromotionRequest |
| PRO-02 | Complete | Engine.collect_witness_signature() collects signatures |
| PRO-05 | Complete | UnauthorizedError when witness not in WitnessSet |
| PRO-06 | Complete | SignatureInvalidError when signature verification fails |

## Next Phase Readiness

Signature collection engine complete. Ready for Phase 4 Plan 03 (Promotion Finalization).

**Blockers:** None

**Concerns:** None

**What's ready:**
- Engine can submit promotion requests
- Engine can collect witness signatures with authorization and verification
- Status transitions track progress toward threshold
- THRESHOLD_MET status indicates promotion ready for finalization

**What's next:**
- finalize_promotion() method to create PolicyHead from THRESHOLD_MET promotion
- Atomic state transition to FINALIZED
- PolicyHead creation with promoted_rule_ids

---
*Phase: 04-promotion-workflow*
*Completed: 2026-01-28*
