# DecisionGraph Compliance Report — Required Fixes

## Fix 1: Typology Maturity Label Consistency

**Problem:** The Decision Summary and gate resolution text say "FORMING" but the Evidence Snapshot says "EMERGING" (or vice versa). These are different maturity stages. The mismatch appears in multiple reports.

**Rule:** The typology maturity label must be identical everywhere it appears in a single report — Decision Summary, Decision Path gates, Decision Conflict resolution text, and Evidence Snapshot. The Evidence Snapshot is the source of truth. All other sections must pull from the same value.

**Where to fix:** Whatever builds the Decision Summary text and the gate resolution text — it's using a hardcoded or incorrect maturity label instead of reading the actual typology maturity from the case data.

---

## Fix 2: Gate 2 Repeated in Decision Conflict Resolution

**Problem:** The resolution text in Decision Conflict shows Gate 2 repeated multiple times:

> "Gate 1 (Typology Maturity), Gate 2 (STR Threshold), Gate 2 (STR Threshold), Gate 2 (STR Threshold), Gate 2 (STR Threshold), Gate 2 (STR Threshold) blocked escalation"

**Rule:** Each gate should appear exactly once in the resolution text. This is a loop bug — the code is iterating over Gate 2 sub-checks (Legal Suspicion Threshold, Evidence Quality Check, Mitigation Failure Analysis, Typology Confirmation, Regulatory Reasonableness) and appending "Gate 2 (STR Threshold)" for each one instead of collecting them into a single Gate 2 reference.

**Where to fix:** The resolution text builder that concatenates gate names.

---

## Fix 3: Gate Dependencies — "PROHIBITED" vs "NOT EVALUATED"

**Problem:** When Gate 1 blocks escalation, Gate 2 currently shows as "PROHIBITED." But Gate 2 was never evaluated — it didn't independently decide to prohibit anything. Upstream blocked it.

**Rule:**
- If a gate independently evaluated the case and blocked: **BLOCKED**
- If a gate was never reached because an upstream gate blocked: **NOT EVALUATED** — with text "Upstream gate blocked — not evaluated"
- If a gate does not apply to this case type (e.g., STR threshold on a sanctions hard stop): **NOT APPLICABLE**

Never show two gates as independently PROHIBITED when only the first one actually fired. The Negative Path Search section already gets this right ("Not evaluated - Gate 1 blocked escalation") — the Decision Path and Decision Conflict sections need to match.

**Where to fix:** Gate status assignment logic and Decision Conflict resolution text.

---

## Fix 4: Sanctions Cases — Suppress Decision Conflict

**Problem:** Sanctions-hit reports show a "⚠ DECISION CONFLICT" block:

> Classifier: STR REQUIRED
> Engine: ESCALATE
> Governed: STR REQUIRED

This is not a conflict. Sanctions are deterministic hard stops — not discretionary. The engine saying "ESCALATE" vs "STR REQUIRED" is an internal vocabulary difference, not a genuine disagreement. Showing it as a conflict implies the system had to reconcile competing views. It didn't.

**Rule:** If the case has a hard stop condition (SANCTIONS_MATCH or any disqualifier), suppress the Decision Conflict section entirely. Replace with:

> **Hard Stop Enforcement — Sanctions Match**
> STR filing mandatory under regulatory obligation. No discretion.

**Where to fix:** The section renderer that decides whether to show Decision Conflict. Add a condition: if hard stop is present, skip conflict block, show hard stop enforcement instead.

---

## Fix 5: Sanctions Cases — Gate 2 Should Not Show "INSUFFICIENT"

**Problem:** On the sanctions-hit report, Gate 2 (STR Threshold) shows "INSUFFICIENT." But the final result is STR REQUIRED. This looks contradictory — the reader sees a gate saying the threshold wasn't met, yet STR is filed anyway.

Sanctions bypass suspicion threshold logic entirely. Gate 2 doesn't apply.

**Rule:** When a hard stop condition is present, gates that evaluate suspicion thresholds should show **NOT APPLICABLE** with explanation: "Sanctions hard stop supersedes suspicion threshold evaluation."

Do not show "INSUFFICIENT" for a gate that was bypassed by a hard stop.

**Where to fix:** Gate 2 status logic — check for hard stop presence before assigning a suspicion-based outcome.

---

## Fix 6: Sanctions Cases — Strip Suspicion-Flavored Signals

**Problem:** The sanctions-hit report lists these key signals:

> 1. Suspicion indicators detected
> 2. Intent indicators identified
> 3. Cross-border transaction with elevated corridor risk
> 4. Wire transfer channel (WIRE_INTERNATIONAL)
> 5. Sanctions match — immediate block required (hard stop)

"Suspicion indicators" and "intent indicators" are irrelevant for sanctions cases. Sanctions are legal prohibitions, not suspicion-based findings. Including suspicion language weakens clarity and could confuse a regulator — it implies discretion where there is none.

**Rule:** When a hard stop condition is present, filter key signals to remove suspicion and intent indicators. The sanctions match should be signal #1. Only include signals directly relevant to the hard stop (e.g., wire channel, cross-border — these describe the transaction, not suspicion).

Correct output for sanctions:
> 1. Sanctions screening match — immediate block required
> 2. Cross-border transaction with elevated corridor risk
> 3. Wire transfer channel (WIRE_INTERNATIONAL)

**Where to fix:** Key signals builder — add filtering logic for hard stop cases.

---

## Fix 7: Terminal Confidence — No Bottleneck When All Factors Are HIGH+

**Problem:** The sanctions-hit report shows:

> Terminal Confidence: HIGH
> Bottleneck: Pool Adequacy ★

But Pool Adequacy is rated HIGH. All other factors are VERY HIGH. Labeling a HIGH factor as a "bottleneck" is misleading — it implies a weakness when there isn't one.

**Rule:** Only label a bottleneck when the lowest factor is MODERATE or below. When all factors are HIGH or VERY HIGH, show:

> Terminal Confidence: HIGH
> No bottleneck — all factors HIGH or above.

**Where to fix:** Bottleneck display logic — add a threshold check before assigning the bottleneck label.

---

## Fix 8: Tier Classification vs Signal Labels

**Problem:** In the single-comparable-precedent report, the Decision Summary says "2 Tier 1 suspicion indicators" but the Key Signals section labels them as "Investigative trigger:" — which is Tier 2 language.

Tier 1 = suspicion indicators.
Tier 2 = investigative triggers.

These cannot be mixed. If the summary says Tier 1, the signals must be labeled as suspicion indicators. If the signals are investigative triggers, the summary should say Tier 2.

**Rule:** The tier classification in the Decision Summary and the signal labels in Key Signals must use the same tier vocabulary. Source of truth is the classifier output — whatever tier it assigned, both sections reference.

**Where to fix:** Either the Decision Summary text builder or the Key Signals label builder — one of them is pulling from the wrong tier classification.

---

## Fix 9: Zero Transferable Precedents — Don't Show 0% Bars

**Problem:** When all comparable precedents are non-transferable (driver contradictions disqualify them all), the report shows:

> OPERATIONAL: 0% (0/9)
> REGULATORY: 0% (0/9)
> COMBINED: 0% (0/9)

This implies the bank was wildly inconsistent — zero alignment. But the real story is there are no valid comparables. The system found 9 cases but none are transferable. 0% alignment and "no valid comparables" are very different messages.

**Rule:** When effective transferable count is 0, do not show percentage bars. Replace with:

> **No transferable precedents available.**
> [N] comparable cases identified, but all were excluded due to driver contradictions.
> Alignment cannot be calculated without valid comparables.
> See Non-Transferable Precedents below for details.

**Where to fix:** Alignment display renderer — add a condition for transferable count = 0.

---

## Fix 10: Decision Path — "Escalation prohibited by policy (Typology Maturity not met)" Double Period

**Problem:** Multiple reports show the gate text ending with a double period:

> "Escalation prohibited by policy (Typology Maturity not met).."

**Rule:** Single period. Trim trailing punctuation before appending a period, or don't append one if the source text already ends with one.

**Where to fix:** Gate resolution text builder — string cleanup.

---

## Fix 11: Terminal Confidence 4-Factor Model Missing — Replaced by Precedent Confidence

**Problem:** Some reports are showing a simplified "Precedent Confidence" block instead of the full Terminal Confidence 4-factor model:

What's rendering:
```
PRECEDENT CONFIDENCE
75%
Supporting: 24  |  Contrary: 0  |  Neutral: 4
```

What should also be rendering:
```
TERMINAL CONFIDENCE
[LEVEL]
Bottleneck: [factor] (only if lowest factor is MODERATE or below)

Pool Adequacy        [LEVEL]    ⓘ
Similarity Quality   [LEVEL]    ⓘ
Outcome Consistency  [LEVEL]    ⓘ
Evidence Completeness [LEVEL]   ⓘ
```

These measure different things:
- **Precedent Confidence** = vote count. How many precedents agree/disagree. Quick read.
- **Terminal Confidence** = diagnostic. Four independent dimensions — pool adequacy, similarity quality, outcome consistency, evidence completeness — where the minimum caps the whole score. Tells you *why* you should or shouldn't trust the precedent intelligence.

**Rule:** Both sections must render. They are complementary, not interchangeable.

The 4-factor model is defined as:
```
final_confidence = min(pool_adequacy, similarity_quality, outcome_consistency, evidence_completeness)
```

| Factor | What It Measures |
|--------|-----------------|
| Pool Adequacy | How many precedents passed gate + similarity floor (0=NONE, 1-4=LOW, 5-14=MODERATE, 15-49=HIGH, 50+=VERY HIGH) |
| Similarity Quality | Average similarity of scored pool (<0.50=LOW, 0.50-0.69=MODERATE, 0.70-0.84=HIGH, 0.85+=VERY HIGH) |
| Outcome Consistency | Among terminal precedents, % agreeing with majority disposition (<0.60=LOW, 0.60-0.79=MODERATE, 0.80-0.94=HIGH, 0.95+=VERY HIGH) |
| Evidence Completeness | % of required fields present in current case (<0.80=LOW, 0.80-0.89=MODERATE, 0.90-0.94=HIGH, 0.95+=VERY HIGH) |

Hard rules:
- 0 precedents above floor → confidence = NONE
- All precedents < 50% similarity → capped at LOW
- Critical fields missing → capped at LOW
- 0 decisive (terminal) precedents → capped at MODERATE
- Pool < 5 → capped at LOW

**Where to fix:** Check the report renderer — there's likely a conditional that shows one or the other instead of both. The Terminal Confidence calculation is still running (other reports show it). This case's renderer is either hitting an edge case that skips it, or a recent change replaced it.

**Check these:**
- Is the `ConfidenceResult` object being returned correctly for this case?
- Is there a template conditional that switches between Precedent Confidence and Terminal Confidence based on case type?
- Did a recent change introduce Precedent Confidence as a replacement instead of an addition?

---

## Fix 12: Precedent Confidence and Terminal Confidence — Display Order

**Rule:** Both sections render in this order within Precedent Intelligence:

1. **Governed Disposition Alignment** — the three-axis percentages (Operational / Regulatory / Combined)
2. **Precedent Confidence** — the quick vote count (Supporting / Contrary / Neutral with overall %)
3. **Terminal Confidence** — the 4-factor diagnostic with bottleneck flag and ⓘ tooltips

This gives the reader a progression: alignment scores → quick confidence read → detailed confidence breakdown.

---

## Summary of All Fixes

| # | Fix | Severity | Area |
|---|-----|----------|------|
| 1 | Typology maturity label consistency | High — regulator-facing defect | Text builder |
| 2 | Gate 2 repeated in conflict resolution | Medium — obvious bug | Loop in resolution text |
| 3 | PROHIBITED vs NOT EVALUATED for blocked gates | High — misleading | Gate status logic |
| 4 | Suppress Decision Conflict for sanctions | High — confusing for regulators | Section renderer |
| 5 | Gate 2 NOT APPLICABLE for sanctions | High — contradictory display | Gate status logic |
| 6 | Strip suspicion signals from sanctions | Medium — clarity | Key signals builder |
| 7 | No bottleneck label when all HIGH+ | Low — cosmetic | Confidence display |
| 8 | Tier classification matches signal labels | Medium — inconsistency | Text builder |
| 9 | No 0% bars when zero transferable | High — misleading | Alignment renderer |
| 10 | Double period in gate text | Low — cosmetic | String cleanup |
| 11 | Terminal Confidence 4-factor model missing / replaced by Precedent Confidence | High — core feature missing | Report renderer |
| 12 | Both confidence sections must render in correct order | Medium — display order | Report renderer |
