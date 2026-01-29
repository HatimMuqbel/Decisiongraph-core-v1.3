---
phase: 04-promotion-workflow
plan: 01
subsystem: promotion
tags: [promotion-request, promotion-status, dataclass, state-machine, canonical-payload, immutability]

# Dependency graph
requires:
  - phase: 01-policyhead-foundation
    provides: PolicyHead infrastructure, validate_threshold function
  - phase: 02-witnessset-registry
    provides: WitnessSet pattern for frozen vs mutable dataclasses
provides:
  - PromotionRequest dataclass with immutable rule_ids and canonical_payload
  - PromotionStatus enum with 5-state lifecycle
  - Factory pattern for deterministic promotion creation
affects: [04-promotion-workflow, 05-witness-approval]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mutable dataclass pattern (NOT frozen) for state that changes during workflow"
    - "tuple[str, ...] for immutable fields in non-frozen dataclass"
    - "Canonical payload with sorted inputs and deterministic JSON"
    - "UUID promotion_id to prevent replay attacks"

key-files:
  created:
    - src/decisiongraph/promotion.py
    - tests/test_promotion.py
  modified:
    - src/decisiongraph/__init__.py

key-decisions:
  - "PromotionRequest NOT frozen - status and signatures are mutable during collection phase"
  - "rule_ids as tuple ensures immutability despite non-frozen dataclass"
  - "canonical_payload includes promotion_id to prevent replay attacks across promotions"
  - "Sorted rule_ids in canonical_payload for order-independent signature verification"

patterns-established:
  - "Mutable dataclass pattern: NOT frozen when state changes during workflow (status, signatures)"
  - "Immutable fields via tuple: rule_ids stored as tuple[str, ...] prevents mutation"
  - "Canonical payload factory: PromotionRequest.create() ensures deterministic payload generation"
  - "Sort-then-JSON pattern: sort_keys=True, separators=(',',':') for deterministic serialization"

# Metrics
duration: 2.1min
completed: 2026-01-28
---

# Phase 04 Plan 01: PromotionRequest Data Model Summary

**PromotionRequest dataclass with immutable rule_ids (tuple), deterministic canonical_payload (sorted JSON), and mutable state for signature collection (status/signatures)**

## Performance

- **Duration:** 2.1 min
- **Started:** 2026-01-28T05:58:18Z
- **Completed:** 2026-01-28T06:00:22Z
- **Tasks:** 2
- **Files created:** 2
- **Files modified:** 1

## Accomplishments
- PromotionStatus enum with 5 states (PENDING, COLLECTING, THRESHOLD_MET, FINALIZED, REJECTED)
- PromotionRequest dataclass balancing immutability (rule_ids, canonical_payload) with mutability (status, signatures)
- Factory method create() generates UUID promotion_id and deterministic canonical_payload
- Sorted rule_ids ensure order-independent signature verification
- All 693 tests pass (682 existing + 11 new promotion tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create promotion.py with PromotionStatus enum and PromotionRequest dataclass** - `81e5c53` (feat)
2. **Task 2: Export from __init__.py and create comprehensive tests** - `83527e2` (feat)

## Files Created/Modified
- `src/decisiongraph/promotion.py` - PromotionRequest dataclass with canonical_payload factory, PromotionStatus enum
- `tests/test_promotion.py` - 11 comprehensive tests covering enum values, immutability, determinism, and state mutability
- `src/decisiongraph/__init__.py` - Export PromotionRequest and PromotionStatus

## Decisions Made

**1. PromotionRequest NOT frozen=True**
- **Rationale:** status and signatures change during the collection phase
- **Contrast with WitnessSet:** WitnessSet is frozen because it never changes after creation
- **Pattern:** Mutable dataclass for workflow state, frozen dataclass for configuration

**2. rule_ids as tuple[str, ...] (not list[str])**
- **Rationale:** Even though dataclass is not frozen, tuple prevents rule_ids mutation
- **Security:** What's being promoted cannot be changed after creation
- **Pattern:** Use tuple for immutable fields in non-frozen dataclass

**3. canonical_payload includes promotion_id**
- **Rationale:** Prevents replay attacks - signatures on one promotion can't be reused on another
- **Security:** Each promotion attempt has unique payload to sign
- **Pattern:** Include unique identifier in signed payload

**4. Sorted rule_ids in canonical_payload**
- **Rationale:** Order-independent signature verification
- **UX:** Submitters don't need to worry about rule order
- **Pattern:** Sort before serialization for determinism

## Deviations from Plan

None - plan executed exactly as written

## Issues Encountered

None

## Test Coverage Summary

**PromotionStatus enum** (1 test)
- test_promotion_status_values: All 5 states have correct string values

**PromotionRequest creation** (2 tests)
- test_promotion_request_create: Factory creates valid request with UUID
- test_promotion_request_created_at_defaults_to_current_time: Timestamp defaults if not provided

**Immutability** (1 test)
- test_promotion_request_rule_ids_immutable: rule_ids is tuple, cannot mutate

**Canonical payload determinism** (3 tests)
- test_promotion_request_canonical_payload_deterministic: Includes all fields in deterministic JSON
- test_promotion_request_canonical_payload_sorted: Different input order produces sorted output
- test_promotion_request_canonical_payload_includes_promotion_id: Includes promotion_id for replay protection

**Initial state** (2 tests)
- test_promotion_request_initial_status_pending: Status is PENDING after creation
- test_promotion_request_signatures_empty: signatures dict is empty after creation

**Mutability during collection** (2 tests)
- test_promotion_request_status_mutable: Can change status (dataclass NOT frozen)
- test_promotion_request_signatures_mutable: Can add signatures to dict

## Test Results

- **Total tests:** 693 (682 existing + 11 new)
- **All tests passing:** Yes
- **Regressions:** 0
- **Warnings:** 8 (pre-existing from test_scholar.py return statements)

## Next Phase Readiness

PromotionRequest data model complete. Ready for Phase 4 Plan 02 (Signature Collection Engine).

**Blockers:** None

**Concerns:** None

**What's ready:**
- PromotionRequest can track promotion lifecycle
- Canonical payload ready for witness signatures
- Status state machine ready for collection workflow
- Immutability guarantees in place (rule_ids cannot be changed)

---
*Phase: 04-promotion-workflow*
*Completed: 2026-01-28*
