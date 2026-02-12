# Spec Alignment Audit — Precedent Engine v3

**Date:** 2026-02-12
**Scope:** Align report layer (`derive.py`) with v3 specification invariants

---

## Root Cause

The precedent engine (`precedent_scorer.py:classify_match_v3`) runs before governance
corrections. It classifies cases against the engine verdict (e.g., "PASS" -> "ALLOW").
When governance changes the outcome (e.g., to "EDD_REQUIRED"), the report layer's
supporting/contrary counts, deviation alerts, pattern summaries, and gate labels were
stale — reflecting the engine's perspective, not the governed perspective.

## Changes Applied

### Fix A: Governed Reclassification (INV-004, INV-005)

**File:** `service/routers/report/derive.py`

- Added `_to_canonical_disposition()` helper mapping governed dispositions to
  canonical form (ALLOW/EDD/BLOCK/UNKNOWN)
- Added governed reclassification in `_build_enhanced_precedent_analysis()`:
  when governed canonical differs from engine canonical, all sample_cases
  are re-counted using INV-003 (UNKNOWN neutral), INV-005 (EDD neutral except
  EDD==EDD), INV-008 (cross-basis neutral), INV-004 (only ALLOW vs BLOCK contrary)
- Applied same reclassification to consistency alert counts (lines 392-414)
- Applied same reclassification to v1-style fallback deviation check (lines 1791+)

### Fix C: Canonicalization (Spec S3.1-3.6)

**File:** `service/main.py`
- Added "edd" and "edd required" to `_EDD_TERMS` so
  `normalize_outcome_v2("edd_required")` returns EDD instead of UNKNOWN

**File:** `service/routers/report/derive.py`
- `_detect_precedent_deviation()`: Changed `case_disposition` from
  `proposed_canonical.get("disposition")` (engine) to
  `_to_canonical_disposition(governed_disposition)` (governed)
- Result: EDD cases now correctly bypass the terminal-only deviation
  guard (`case_disposition in ("ALLOW", "BLOCK")`)

### Fix D: Terminal vs Non-Terminal Handling (Spec S6.4, S10.2)

**File:** `service/routers/report/derive.py`

- `_build_pattern_summary()`: Added EDD-specific branch before terminal
  `total_decisive > 0` block. Counts terminal outcomes (ALLOW/BLOCK) in
  pool for directional guidance; uses "terminal guidance is directional"
  language instead of asserting terminal conclusions
- `_build_institutional_posture()`: Added EDD-specific early return when
  all matches are EDD-vs-EDD supporting. Returns "uniform EDD referral"
  instead of "terminal precedents resulted in the same outcome"

### Fix E: Gate Determination Labels (Spec S9)

**File:** `service/routers/report/derive.py`
- Added `classification_outcome` parameter to `_build_gate_override_explanations()`
- Added UPHELD case: when gate blocked, classifier wanted STR, but governed
  follows gate (not STR), the gate is labeled UPHELD with basis
- Updated call site to pass `classification.outcome`

**File:** `service/routers/report/render_md.py`
- Added UPHELD rendering block after conflict check

**File:** `service/templates/decision_report.html`
- Added UPHELD rendering template with gate basis list

### Fix F: Deviation Alert Scope (Spec S8.1, S8.2)

Fix C's canonicalization resolved this automatically:
- `case_disposition` is now governed canonical ("EDD" for EDD_REQUIRED cases)
- Terminal-only guard (`case_disposition in ("ALLOW", "BLOCK")`) correctly
  blocks EDD from producing disposition deviation alerts
- v1-style fallback deviation counts are now reclassified

---

## Before / After — Per Case

### shell-company-layering (EDD_REQUIRED)

| Aspect | Before | After |
|--------|--------|-------|
| Contrary count | 10 | 0 |
| Supporting count | 0 | 10 (EDD-vs-EDD) |
| Deviation alert | "current disposition is ALLOW" | None (EDD skips terminal guard) |
| Pattern summary | "all 10 terminal precedents resulted in EDD REQUIRED" | "33 have reached terminal resolution ... terminal guidance is directional" |
| Institutional posture | "All 10 comparable terminal precedents resulted in the same outcome" | "uniform EDD referral" |
| Gate label | "All gates consistent" | "Gate 1 — UPHELD" |
| Divergence justification | "10 contrary precedent(s) identified" | Not rendered (no deviation) |

### pep-legal-fees (EDD_REQUIRED / PASS_WITH_EDD)

| Aspect | Before | After |
|--------|--------|-------|
| Pattern summary | Terminal language | "terminal guidance is directional" |
| Institutional posture | Terminal language | "uniform EDD referral" |
| EDD classifications | Incorrectly contrary | Correctly neutral/supporting |

### beneficial-owner-pep (EDD_REQUIRED / PASS_WITH_EDD)

| Aspect | Before | After |
|--------|--------|-------|
| Pattern summary | Terminal language | "terminal guidance is directional" |
| Institutional posture | Terminal language | "uniform EDD referral" |
| Gate label | "All gates consistent" | "Gate 1 — UPHELD" (classifier wanted STR) |

### sanctions-hit (STR_REQUIRED / ESCALATE)

| Aspect | Before | After |
|--------|--------|-------|
| Classification | Unchanged | Unchanged |
| All counts | Unchanged | Unchanged (engine canonical matches governed) |

### high-value-explained (NO_REPORT / PASS)

| Aspect | Before | After |
|--------|--------|-------|
| Classification | Unchanged | Unchanged |
| All counts | Unchanged | Unchanged |

### cross-border-routine (NO_REPORT / PASS)

| Aspect | Before | After |
|--------|--------|-------|
| Classification | Unchanged | Unchanged |
| All counts | Unchanged | Unchanged |

### structuring-pattern (EDD_REQUIRED)

| Aspect | Before | After |
|--------|--------|-------|
| Pattern summary | Terminal language | "directional" EDD language |
| Institutional posture | Terminal language | "uniform EDD referral" |

### pep-plus-adverse-media (STR_REQUIRED / ESCALATE)

| Aspect | Before | After |
|--------|--------|-------|
| Classification | Unchanged | Unchanged (terminal case) |

### crypto-high-risk-corridor (EDD_REQUIRED)

| Aspect | Before | After |
|--------|--------|-------|
| Pattern summary | Terminal language | "directional" EDD language |
| EDD classifications | Incorrectly counted | Correctly neutral/supporting |

### velocity-spike (EDD_REQUIRED)

| Aspect | Before | After |
|--------|--------|-------|
| Pattern summary | Terminal language | "directional" EDD language |
| EDD classifications | Incorrectly counted | Correctly neutral/supporting |

---

## Invariant Verification

| Invariant | Status |
|-----------|--------|
| INV-003: UNKNOWN is always neutral | PASS — reclassification checks UNKNOWN first |
| INV-004: Only ALLOW vs BLOCK is contrary | PASS — explicit set check `{prec, gov} == {"ALLOW", "BLOCK"}` |
| INV-005: EDD is always neutral (except EDD==EDD) | PASS — EDD branch in reclassification |
| INV-007: Disposition -> Consistency; Reporting -> Defensibility | PASS — separate alert paths |
| INV-008: Cross-basis precedents excluded | PASS — basis check in reclassification |

## Files Modified

| File | Lines Changed |
|------|---------------|
| `service/main.py` | +2 (EDD terms) |
| `service/routers/report/derive.py` | +~130 (reclassification, EDD handling, gate UPHELD) |
| `service/routers/report/render_md.py` | +12 (UPHELD rendering) |
| `service/templates/decision_report.html` | +14 (UPHELD template) |
