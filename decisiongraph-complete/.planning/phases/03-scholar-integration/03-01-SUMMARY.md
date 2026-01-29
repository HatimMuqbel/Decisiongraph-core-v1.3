---
phase: 03-scholar-integration
plan: 01
subsystem: query-resolver
tags: [scholar, policyhead, bitemporal, policy-filtering, promoted-rules]

# Dependency graph
requires:
  - phase: 01-policyhead-foundation
    provides: PolicyHead cells, get_policy_head_at_time(), parse_policy_data()
  - phase: 02-witnessset-registry
    provides: WitnessSet infrastructure for policy approval workflows
provides:
  - QueryResult with optional policy_head_id field
  - Scholar.query_facts() with policy_mode parameter
  - Policy-aware query filtering by promoted rules
  - Bitemporal "what policy was active when?" query capability
affects:
  - 03-scholar-integration-02 (will use policy_mode="promoted_only" for querying)
  - Future auditing and compliance features requiring policy snapshots

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Optional policy filtering via parameter (backward compatible)"
    - "Fail-closed on missing PolicyHead (return empty result)"
    - "Bitemporal policy lookup using as_of_system_time"

key-files:
  created: []
  modified:
    - src/decisiongraph/scholar.py

key-decisions:
  - "policy_mode='all' as default preserves backward compatibility"
  - "Fail-closed approach: no PolicyHead returns empty result with reason='no_policy_head'"
  - "Filter by logic_anchor.rule_id (canonical promoted rule reference)"

patterns-established:
  - "Policy filtering integrates into existing query pipeline without breaking changes"
  - "QueryResult extensions remain backward compatible via optional fields with None defaults"
  - "Output methods (to_proof_bundle, to_audit_text, to_dot) conditionally include policy information"

# Metrics
duration: 3min
completed: 2026-01-28
---

# Phase 03 Plan 01: Scholar Integration Summary

**Scholar.query_facts() now supports policy-aware filtering by promoted rules using bitemporal PolicyHead lookup**

## Performance

- **Duration:** 3 min
- **Started:** 2026-01-28T05:32:03Z
- **Completed:** 2026-01-28T05:34:38Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Extended QueryResult with optional policy_head_id field for policy tracking
- Added policy_mode parameter to query_facts() ("all" or "promoted_only")
- Integrated bitemporal PolicyHead lookup using get_policy_head_at_time()
- Filter candidates by logic_anchor.rule_id in promoted_rule_ids
- All 671 existing tests pass (100% backward compatibility)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend QueryResult with policy_head_id field** - `9cd3d77` (feat)
   - Added optional policy_head_id field to QueryResult dataclass
   - Updated to_proof_bundle() to include policy section when present
   - Updated to_audit_text() to include Policy section when present
   - Updated to_dot() to include PolicyHead node when present

2. **Task 2: Add policy_mode parameter to query_facts()** - `f886381` (feat)
   - Imported get_policy_head_at_time and parse_policy_data from policyhead
   - Added policy_mode parameter with "all" (default) or "promoted_only"
   - Policy lookup after time defaults, before visibility check
   - Filter candidates by promoted_rule_ids when policy_mode="promoted_only"
   - Return empty result with reason="no_policy_head" if no policy exists
   - Include policy_head_id in QueryResult return

## Files Created/Modified

- `src/decisiongraph/scholar.py` - Extended QueryResult and query_facts() with policy-aware filtering

## Decisions Made

**1. policy_mode="all" as default preserves v1.4 behavior**
- Rationale: Backward compatibility is critical. Existing 671 tests must pass without modification. Default "all" means existing code continues working identically to v1.4.

**2. Fail-closed on missing PolicyHead**
- Rationale: When policy_mode="promoted_only" but no PolicyHead exists for namespace, return empty result rather than falling back to "all" mode. This is safer for compliance: if caller requests policy filtering, absence of policy means "no facts allowed" not "all facts allowed".

**3. Filter by logic_anchor.rule_id**
- Rationale: logic_anchor.rule_id is the canonical reference to the rule that produced a fact. Promoted_rule_ids in PolicyHead are rule IDs, so filtering by logic_anchor.rule_id is the natural join point.

**4. Bitemporal policy lookup using as_of_system_time**
- Rationale: Scholar query has two time coordinates: valid_time (when facts were true) and system_time (what was known). Policy lookup must use system_time to answer "what policy was active at the time of this query?"

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - implementation straightforward, all tests passed on first run.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for Phase 03 Plan 02:**
- Scholar.query_facts() policy filtering is functional and tested
- All 671 existing tests pass (0 regressions)
- policy_head_id tracking available in QueryResult
- Bitemporal policy lookup working correctly

**Foundation complete for:**
- SCH-02: Integration tests for policy-aware queries
- SCH-03: Commit gate integration with policy filtering
- SCH-04: Multi-witness promotion workflows

**No blockers identified.**

---
*Phase: 03-scholar-integration*
*Completed: 2026-01-28*
