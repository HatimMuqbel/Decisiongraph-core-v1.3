# DecisionGraph Investigation Report — v2 Fix Spec

**Purpose:** Actionable refinements to the Investigation Report output format. Each fix is numbered, categorized, and written as an implementation instruction. No code — these are structural and semantic corrections to be applied to the report generation layer.

**Reference:** Precedent Outcome Model v2 Specification (PRECEDENT_OUTCOME_MODEL_V2.md)

**Priority Key:** P0 = regulatory exposure if not fixed. P1 = auditor would flag. P2 = quality improvement.

---

## FIX-001: Add Three-Field Canonical Outcome Block (P0)

**Problem:** The report shows disposition (EDD REQUIRED) but has no reporting field and no disposition_basis field. Under the v2 spec, every decision output must carry all three dimensions. A FINTRAC examiner would ask "What is the reporting determination?" and the report has no answer.

**Fix:** Add a dedicated Canonical Outcome section immediately after the Investigation Outcome Summary. It must always display all three fields, even when values are UNKNOWN.

**Structure:**
```
Canonical Outcome
  Disposition:        EDD_REQUIRED
  Disposition Basis:  DISCRETIONARY
  Reporting:          UNKNOWN (pending EDD completion)
```

**Rules:**
- Disposition Basis must be derived from the triggered rule context. If the trigger is a sanctions rule (AML_BLOCK_SANCTIONS), basis = MANDATORY. If the trigger is risk-based (AML_ESC_HR_COUNTRY, AML_ESC_PEP_SCREEN, etc.), basis = DISCRETIONARY. If not determinable, basis = UNKNOWN.
- Reporting must never be inferred from disposition. If no explicit reporting determination has been made (which is expected for EDD outcomes where investigation is pending), set reporting = UNKNOWN with a parenthetical reason.
- This block is the authoritative outcome record. All other sections of the report must be consistent with it.

---

## FIX-002: Reconcile Precedent Counts (P0)

**Problem:** The report contains contradictory precedent numbers that would not survive audit review:
- Deviation Signal says "35 of 35 scored comparable cases"
- Precedent Alignment Summary says "Comparable Matches (Scored): 144"
- Supporting Precedents: 35, Contrary: 0
- Scored Match Outcome Distribution shows ALLOW: 87, EDD: 57 (total: 144)

An auditor cannot determine whether the system evaluated 35 or 144 comparable cases, or what the actual outcome distribution is for the scored subset.

**Fix:** Split the precedent section into two clearly labelled tiers:

**Tier 1 — Scored Matches (Above Similarity Threshold)**
- Show only precedents that met the similarity threshold (≥60%)
- Show the count, outcome distribution, supporting/contrary/neutral breakdown
- This is the tier used for confidence scoring and deviation analysis

**Tier 2 — Broader Comparable Pool (Below Threshold)**
- Show the full comparable pool with its own outcome distribution
- Label clearly as "contextual — not used in confidence scoring or deviation analysis"
- Useful for analyst awareness but must not contaminate scored metrics

**Rename the existing fields for clarity:**
- "Comparable Matches (Scored)" → rename to "Total Comparable Pool" (the 144)
- Add "Scored Matches (Above Threshold)" as a separate field (the 35)
- The Outcome Distribution table must specify which pool it represents

**The Deviation Signal must reference the correct pool.** If the deviation is computed against the 35 scored matches, say "35 of 35 scored matches (≥60% similarity)." If it's computed against the 144, say so. Never leave ambiguity about the denominator.

---

## FIX-003: Resolve Evidence Contradiction — Jurisdiction Risk (P1)

**Problem:** The evidence section shows `risk.high_risk_jurisdiction: False` while simultaneously showing `txn.destination_country: high_risk_country` and the triggered rule is `AML_ESC_HR_COUNTRY` (FINTRAC High Risk Jurisdiction). An examiner would flag this as internally contradictory.

**Fix:** Add a scope qualifier to each evidence field so the reader can distinguish customer-level risk from transaction-level risk:

- `risk.high_risk_jurisdiction` → label as "Customer domicile jurisdiction risk" or rename to `customer.jurisdiction_risk`
- `txn.destination_country` → label as "Transaction destination jurisdiction"

Alternatively, add a short Evidence Notes section that explains: "Customer domicile is not a high-risk jurisdiction. Transaction destination is a FINTRAC-designated high-risk jurisdiction. Rule AML_ESC_HR_COUNTRY evaluates transaction-level jurisdiction, not customer domicile."

The evidence table must not contain fields that appear to contradict each other without explanation. Every field that contributed to a triggered rule should be visually linked to that rule.

---

## FIX-004: Reframe Classifier Override Narrative (P1)

**Problem:** The current language reads as suppression of escalation: "Engine Output: ESCALATE → Classifier Sovereign → Governed Outcome: EDD REQUIRED." A compliance officer or examiner reading this would reasonably ask: "Why did the system suppress an escalation?" That framing creates the impression of downgrading, which is the worst possible optic in AML.

**Fix:** Reframe the narrative to emphasize false escalation prevention, not override:

**Current (problematic):**
> "Engine output differs from governed disposition. Classifier sovereignty enforced — governed outcome is authoritative."

**Revised:**
> "Rule engine triggered ESCALATE based on jurisdiction risk. Suspicion Classifier determined that Tier 1 suspicion indicators = 0, which is below the threshold required for escalation under the governance framework. Disposition corrected to EDD REQUIRED — enhanced review is warranted but escalation is not justified without suspicion indicators. This correction prevents false escalation and preserves STR threshold integrity (PCMLTFA s. 7)."

**Key principle:** The word "override" should never appear. Use "correction" or "governance adjustment." The narrative must make clear that the classifier is *protecting* the STR threshold, not suppressing a legitimate escalation.

**Move the Decision Integrity Alert.** Currently it appears at the very top of the report before the reader has context. Move it to immediately after the Investigation Outcome Summary, after the Canonical Outcome block. By that point the reader knows the disposition and can understand why the correction was applied.

---

## FIX-005: Distinguish Confidence Metrics (P1)

**Problem:** The report shows "Confidence: Elevated Review Recommended (60%)" and separately "Precedent Alignment: 30%." These are different metrics measuring different things, but the report doesn't explain the relationship. A risk committee would ask: "Is 60% the precedent confidence? Why is alignment only 30%?"

**Fix:** Label each metric distinctly and provide a one-line definition:

- **Decision Confidence (60%):** Composite score reflecting evidence completeness and rule alignment. "Elevated Review Recommended" = below the standard threshold for automated disposition.
- **Precedent Alignment (30%):** Percentage of scored precedents whose outcome matches the current disposition. Computed per v2 spec: `supporting_decisive / count(decisive_precedents)` within the same disposition basis.
- **Precedent Match Rate:** Percentage of the comparable pool that met the similarity threshold for scoring (35 / 144 = 24%).

Each metric must have a short parenthetical or footnote explaining what it measures. Never display a percentage without context.

---

## FIX-006: Add Defensibility Check Section (P1)

**Problem:** The v2 spec introduces Dual Deviation (Consistency + Defensibility). The current report has a Deviation Signal for disposition but no reporting deviation check. For EDD outcomes where reporting is UNKNOWN, the report should explicitly state the defensibility status.

**Fix:** Add a Defensibility Check section after the Precedent Intelligence section:

**For cases where reporting = UNKNOWN (pending EDD):**
```
Defensibility Check
  Status: DEFERRED — Reporting determination pending EDD completion.
  Action: Defensibility Alert will be evaluated upon final disposition.
  Note: No historical filing pattern comparison performed. Reporting
        obligation will be assessed when EDD is complete and a final
        disposition is rendered.
```

**For cases where reporting has been determined:**
- Run the reporting deviation check per v2 spec Section 9.2
- If triggered, display: "Defensibility Alert: Current proposal to NOT FILE contradicts X% historical STR filing rate for this typology."
- If not triggered, display: "Defensibility Check: No reporting deviation detected. Current reporting determination is consistent with precedent filing patterns."

This section must always appear in the report, even if deferred. Its absence would mean the report has no evidence that the defensibility check was considered.

---

## FIX-007: Specific EDD Recommendations Based on Risk Factors (P1)

**Problem:** The Recommended Actions are generic: "Complete Enhanced Due Diligence review, Obtain additional documentation as required." FINTRAC expects risk-proportionate EDD measures. This case has specific risk factors (PEP = True, cross-border wire to high-risk country, 10k-25k band) that should drive specific EDD tasks.

**Fix:** Generate EDD recommendations from the actual evidence fields and triggered rules. The recommendation engine should map risk factors to specific EDD actions:

- `risk.pep == True` → "Verify source of wealth and source of funds (PCMLTFA Regulations s. 67.1 — PEP enhanced measures)"
- `txn.cross_border == True AND txn.destination_country == high_risk_country` → "Obtain and document the stated purpose of the cross-border transfer. Verify consistency with customer profile and relationship history."
- `txn.amount_band == 10k_25k` → "Confirm whether transaction is part of a series. Assess against LCTR threshold ($10,000 cash or 24-hour rule) if applicable."
- Generic fallback: "Complete enhanced customer due diligence review per institutional policy and escalate to Senior Analyst / Compliance Officer within 5 business days."

The specific recommendations should appear first, followed by the generic escalation instruction. Include the regulatory reference for each recommendation so the analyst knows *why* the action is required, not just what to do.

---

## FIX-008: Fix Appeal Statistics Display (P2)

**Problem:** "Total Appealed: 0, Upheld: 0, Overturned: 0, Upheld Rate: 100%." Zero divided by zero is not 100%.

**Fix:** When Total Appealed = 0, display Upheld Rate as "N/A — No appeals filed." Do not compute a percentage from an empty set.

---

## FIX-009: Add SLA / Timeline Tracking (P1)

**Problem:** The report says "Escalate to Senior Analyst / Compliance Officer within 5 business days" but there is no field recording when the clock started or when the EDD must be completed. If this report is pulled 30 days later and EDD hasn't been completed, there's no system-level evidence of the timeline.

**Fix:** Add a Timeline section to the report:

```
Timeline
  Case Created:          2026-02-07T19:44:50Z
  EDD Deadline:          2026-02-14T23:59:59Z (5 business days)
  Final Disposition Due:  [populated when EDD completes]
  STR Filing Window:     N/A (no STR determination)
```

**Rules:**
- EDD Deadline is computed from Case Created + the SLA defined in policy (currently 5 business days).
- If reporting = FILE_STR, populate STR Filing Window with the 30-day deadline per PCMLTFA s. 7.
- If reporting = FILE_LCTR, populate with 15-day deadline per PCMLTFA s. 12.
- This section provides the auditable evidence that the institution tracked its regulatory timelines.

---

## FIX-010: Rename BYOC Source Label (P2)

**Problem:** "BYOC" (Build Your Own Case) reads as a testing harness. If an examiner sees "Source: BYOC" in a production report, they will question whether the case originated from the transaction monitoring system or was artificially constructed.

**Fix:** For production use, rename the source label to reflect the actual intake channel:
- Manual referral by analyst → `ANALYST_REFERRAL`
- Manual referral by branch → `BRANCH_REFERRAL`
- Ad hoc investigation → `MANUAL_INVESTIGATION`
- Keep `BYOC` only for development/testing environments and ensure it never appears in production report output. Add a validation check: if environment = production and source = BYOC, log a warning.

---

## FIX-011: Add Dual Deviation Signal with Correct Framing (P0)

**Problem:** The existing Deviation Signal conflates disposition deviation with a general "consistency review" recommendation. Under v2, deviation must be bifurcated into Consistency (disposition) and Defensibility (reporting).

**Fix:** Replace the current single Deviation Signal with two clearly labelled signals:

**Disposition Deviation (Consistency Check):**
```
Consistency Check
  Current Disposition:     EDD_REQUIRED (DISCRETIONARY)
  Scored Precedent Majority: ESCALATE (if applicable) or EDD (if applicable)
  Deviation Detected:      [YES/NO]
  Alert:                   [Consistency Warning message or "No deviation detected"]
```

**Reporting Deviation (Defensibility Check):**
- See FIX-006. For EDD cases with UNKNOWN reporting, this is deferred.

**The current Deviation Signal text is misleading.** It says: "35 of 35 scored comparable cases resulted in escalation, but governed outcome is non-escalation." This frames the classifier correction as a deviation, when it's actually a governance adjustment. The Deviation Signal should compare the *governed* outcome against precedent, not the *engine* outcome. If the governed outcome is EDD and the precedent majority is also EDD, there is no deviation — the system is consistent.

---

## FIX-012: Link Triggered Rules to Evidence Fields (P2)

**Problem:** The Rules Evaluated table shows which rules fired but doesn't show which evidence fields triggered them. The Evidence Considered table shows all fields but doesn't indicate which ones were relevant to the decision. An analyst has to mentally cross-reference two separate tables.

**Fix:** For each triggered rule (result = "warn" or "fail"), add a "Triggered By" column or sub-row listing the specific evidence fields that activated it:

```
AML_ESC_HR_COUNTRY: FINTRAC:HighRiskJurisdiction
  Result: warn
  Triggered By: txn.destination_country = high_risk_country,
                txn.cross_border = True
```

For rules that passed (not triggered), no additional detail is needed — the current format is fine.

This gives analysts the complete causal chain: evidence → rule → disposition, without needing to reverse-engineer it.

---

## Implementation Order

**Phase 1 (Regulatory exposure — do first):**
- FIX-001 (Three-field canonical outcome)
- FIX-002 (Reconcile precedent counts)
- FIX-011 (Dual deviation signal)

**Phase 2 (Auditor findings — do next):**
- FIX-004 (Reframe classifier override)
- FIX-005 (Distinguish confidence metrics)
- FIX-006 (Defensibility check section)
- FIX-007 (Specific EDD recommendations)
- FIX-009 (SLA / timeline tracking)

**Phase 3 (Quality — do when stable):**
- FIX-003 (Evidence contradiction)
- FIX-008 (Appeal statistics)
- FIX-010 (BYOC label)
- FIX-012 (Rule-evidence linking)
