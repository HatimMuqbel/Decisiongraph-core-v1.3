# AML/KYC Decision Report

**Deterministic Regulatory Decision Engine (Zero LLM)**

---

## Administrative Details

| Field | Value |
|-------|-------|
| Decision ID | `a4804a5c5df2e005...` |
| Case ID | `TEST-E-08` |
| Timestamp | `2026-02-13T04:39:12.187898` |
| Jurisdiction | CA |
| Engine Version | `2.1.1` |
| Policy Version | `1.0.0` |
| Report Schema | `DecisionReportSchema v1` |

---

## Investigation Outcome Summary

### Disposition Ladder

| | |
|---|---|
| **Final Disposition (Classifier Sovereign)** | **EDD REQUIRED** |
| Engine Output (Rules Layer) | STR REQUIRED — FILE_STR |

> Engine output differs from governed disposition. Governance correction applied — governed outcome is authoritative. This correction prevents false escalation and preserves STR threshold integrity.

| Field | Value |
|-------|-------|
| Investigation State | EDD REQUIRED |
| Primary Typology | No suspicious typology identified |
| Regulatory Obligation |  |
| Regulatory Position | Suspicion threshold not met based on available indicators. |
| STR Required | No |

Governance correction applied: STR determination removed due to insufficient Tier 1 evidence. Enhanced Due Diligence required.

### Case Facts

| Field | Value |
|-------|-------|
| Case ID | `TEST-E-08` |
| Jurisdiction | `CA` |


---

## Canonical Outcome

*Authoritative three-field outcome record per v2 specification. All other sections must be consistent with these values.*

| Field | Value |
|-------|-------|
| Disposition | **EDD_REQUIRED** |
| Disposition Basis | **PENDING_REVIEW** |
| Reporting | **PENDING_COMPLIANCE_REVIEW (reporting obligation deferred to compliance officer — see Decision Integrity Alert)** |


---


> 🚨 **DECISION INTEGRITY ALERT**
>
> Decision Integrity Alert: Regulatory status is STR REQUIRED but Suspicion Classifier found 0 Tier 1 indicators. These statements cannot legally coexist. Suspicion threshold not met — STR filing would be unjustified.
>
> Original verdict: `STR` → Classifier outcome: `EDD_REQUIRED`




## 🚨 Override Justification

**Override Type:** CONTROL_CONTRADICTION

| | |
|---|---|
| Gate Overridden | **Rules Engine / STR Determination** |
| Gate Decision | `STR REQUIRED (engine)` |
| Classifier Decision | `EDD_REQUIRED` |
| Regulatory Basis | PCMLTFA s. 7 — STR requires RGS threshold (Tier 1 ≥ 1) |

### Gate Deficiency Detail

- **STR Determination**: 0 Tier 1 indicators — STR filing would be unjustified

### Justification

> Regulatory status was STR REQUIRED but Suspicion Classifier found 0 Tier 1 indicators. These statements cannot legally coexist under PCMLTFA/FINTRAC. Suspicion threshold not met — corrected to prevent unjustified STR filing.

---



## Required Actions

1. **[REQUIRED]** Complete EDD by 2026-02-20T23:59:59.187744Z
2. **[REQUIRED]** Complete enhanced customer due diligence review per institutional policy and escalate to Senior Analyst / Compliance Officer within 5 business days.
3. **[STANDARD]** Re-evaluation trigger: upon EDD completion



---

## Case Classification

| Field | Value |
|-------|-------|
| Source | Production |
| Seed Category | N/A |
| Scenario Code | `N/A` |



---

## Regulatory Determination

### **EDD_REQUIRED** — Enhanced Due Diligence Required

*Engine originally suggested: STR REQUIRED. Classifier sovereignty applied — governed outcome is authoritative.*

Governance correction applied: STR determination removed due to insufficient Tier 1 evidence. Enhanced Due Diligence required.

**STR Required:** No

### Regulatory Escalation Summary

Enhanced Due Diligence is required to complete the investigation and finalize the regulatory outcome.

### Confidence Metrics

| Metric | Value | Definition |
|--------|-------|------------|
| Decision Confidence | Integrity Review Required (0%) | Composite score reflecting evidence completeness and rule alignment |
| Institutional Threshold | Below Threshold — Manual Review Required | Bands: ≥70% High, 40–70% Moderate, <40% Low (manual review) |
| Precedent Alignment | 0% | supporting_decisive / count(decisive_precedents) within same basis |
| Precedent Match Rate | 0% (0 / 0) | Percentage of comparable pool meeting similarity threshold |

Confidence cannot be computed when a control contradiction exists. Rule outcome conflicts with suspicion classifier.

> **LOW CONFIDENCE FLAG:** Decision confidence (0%) is below the institutional threshold of 40%. This decision requires senior analyst or compliance officer review before final disposition.


## Disposition Reconciliation

*2 disposition difference(s) detected between engine, classifier, and governed layers.*

**Engine** determined `STR_REQUIRED` — **Governed** overrode to `EDD_REQUIRED`

> STR REQUIRED removed — 0 Tier 1 indicators; STR filing would be unjustified (PCMLTFA s. 7)

> Authority: Classifier sovereignty framework — governed disposition is authoritative

**Engine** determined `STR_REQUIRED` — **Classification** overrode to `EDD_REQUIRED`

> Engine produced STR_REQUIRED from rules/gates. Classifier independently determined EDD_REQUIRED from suspicion indicators.

> Authority: Both assessments feed into governed disposition



### ⚠ DECISION CONFLICT

| | |
|---|---|
| Classifier | **EDD REQUIRED** |
| Engine | **STR REQUIRED** |
| Governed | **EDD REQUIRED** |

> **Resolution:** Gate 1 (Typology Maturity) blocked escalation — Mitigations insufficient to explain behavior. Engine followed gate logic.



---

## Suspicion Classification

| Field | Value |
|-------|-------|
| Classifier Outcome | **EDD_REQUIRED** |
| Suspicion Indicators (Tier 1) | 0 |
| Investigative Signals (Tier 2) | 1 |
| Classifier Version | `SuspicionClassifier v1` |

1 investigative signal(s) detected. Suspicion threshold not met. Enhanced Due Diligence required to determine regulatory outcome.



### Tier 2 — Investigative Signals (EDD Triggers)

| Code | Source | Detail |
|------|--------|--------|
| `UNCLASSIFIED_HAS_DECEPTION` | suspicion_element | Suspicion element 'has_deception' could not be mapped to a known Tier 1 indicator code. Classified as Tier 2 (investigative) pending manual review. If this element represents genuine suspicion, a compliance officer must explicitly reclassify it. |




---

## Decision Drivers

- Deceptive conduct indicators

---

## Gate Evaluation

### Gate 1: Zero-False-Escalation

**Decision:** ALLOWED

| Section | Status | Reason |
|---------|--------|--------|
| Fact-Based Hard Stop Check | PASS | No hard stop conditions detected |
| Instrument Context Validation | PASS | If any mismatch exists -> invalidate related indicators and re-evaluate. |
| Obligation Isolation Check | PASS | If this cannot be stated -> system design is invalid. Fix before proceeding. |
| Indicator Corroboration | PASS | If indicators fail corroboration -> escalation prohibited. |
| Typology Maturity Assessment | PASS | Escalation prohibited by policy (Typology Maturity not met). |
| Mitigation Override Check | FAIL | Mitigations insufficient to explain behavior. |
| Suspicion Definition Test | PASS | If NONE apply -> escalation is forbidden. |



### Gate 2: STR Threshold

**STR Required:** No

| Section | Status | Reason |
|---------|--------|--------|
| Legal Suspicion Threshold | PASS | If none apply -> NO STR (stop here) |
| Evidence Quality Check | PASS | If any fail -> NO STR |
| Mitigation Failure Analysis | PASS | Mitigating factors were considered and found insufficient to explain the suspicious activity. |
| Typology Confirmation | PASS | Typology is supporting, not required. STRs may exist without a named typology. |
| Regulatory Reasonableness | PASS | If any answer = NO -> NO STR |


### Gate Override Analysis

> All gates consistent with final disposition.



---

## Rules Evaluated

| Rule Code | Result | Reason |
|-----------|--------|--------|
| `HARD_STOP_CHECK` | CLEAR | No hard stop conditions |
| `PEP_ISOLATION` | NOT_APPLICABLE | Not a PEP |
| `SUSPICION_TEST` | ACTIVATED | BEHAVIORAL |


---

## Precedent Intelligence

*Precedent analysis is advisory and does not override the deterministic engine verdict.*
*Absence of precedent matches does not imply the recommendation is incorrect.*

### Tier 1 — Scored Matches (≥50% Similarity)

*Used for confidence scoring and deviation analysis.*

| Metric | Value |
|--------|-------|
| Scored Matches (Above Threshold) | 0 |
| Supporting Precedents | 0 |
| Contrary Precedents | 0 |
| Neutral Precedents | 0 |
| Precedent Confidence | 0% |
| Exact Matches | 0 |



#### Scored Match Outcome Distribution

| Outcome | Count |
|---------|-------|
| No data | - |

### Tier 2 — Broader Comparable Pool

*Contextual — not used in confidence scoring or deviation analysis.*

| Metric | Value |
|--------|-------|
| Total Comparable Pool | 0 |
| Raw Overlaps Found | 0 |
| Candidates Scored | 0 (≥50% similarity required; mode: prod) |





### Appeal Statistics

| Metric | Value |
|--------|-------|
| Total Appealed | 0 |
| Upheld | 0 |
| Overturned | 0 |
| Upheld Rate | N/A — No appeals filed |





### Institutional Pattern Summary

> No comparable precedents available for pattern analysis.

### Institutional Posture

> *Insufficient precedent data to establish institutional posture.*


### Outcome Distribution Summary

| Category | Count |
|----------|-------|
| Supporting (same outcome) | 0 |
| Contrary (different outcome) | 0 |
| Neutral | 0 |
| **Total Decisive** | **0** |
| Typical Outcome for Cluster | EDD_REQUIRED |








### Consistency Check (Disposition Deviation)

> No disposition deviation detected. Current governed outcome is consistent with scored precedent patterns.



### Defensibility Check

| | |
|---|---|
| Status | ✅ **PASS** — No reporting deviation detected. |
| Note | Current reporting determination is consistent with precedent filing patterns. |



### Unmapped Indicator Independence Check

**UNCLASSIFIED_HAS_DECEPTION**: DEFENSIBILITY WARNING: Disposition DEPENDS on unmapped indicator. No mapped Tier 1 indicators independently support this disposition. Manual classification required before filing.



---

## Risk Factors

| Field | Value |
|-------|-------|
| CONFLICT_001 | Corroborated |
| Typology | Typology indicators (ESTABLISHED) [primary/ESTABLISHED] |
| Suspicion element | Deception indicators present in customer conduct [has_deception] |


---

## Evidence Considered

*Evidence fields reflect the normalized investigation record used for rule evaluation (booleans and buckets). Raw customer identifiers are not included in this report.*

| Field | Scope | Value |
|-------|-------|-------|
| `customer.pep_flag` | customer.pep_flag | No |
| `customer.type` | Customer entity type | INDIVIDUAL |
| `facts.adverse_media_mltf` | Adverse media ML/TF relevance indicator | No |
| `facts.sanctions_result` | Sanctions screening determination | NO_MATCH |
| `mitigations.count` | Count of mitigating factors identified | 1 |
| `obligations.count` | Count of regulatory obligations triggered | 0 |
| `risk.high_risk_jurisdiction` | Customer domicile jurisdiction risk | No |
| `suspicion.has_deception` | Suspicion element: deception indicators present | Yes |
| `suspicion.has_intent` | Suspicion element: intent indicators present | No |
| `suspicion.has_sustained_pattern` | Suspicion element: sustained transaction pattern | No |
| `txn.cross_border` | Cross-border transaction indicator | No |
| `txn.method` | txn.method | SWIFT_WIRE |
| `typology.maturity` | Typology assessment maturity level | ESTABLISHED |


---

## Recommended Actions

1. **Complete enhanced customer due diligence review per institutional policy and escalate to Senior Analyst / Compliance Officer within 5 business days.**
   *Ref: Institutional EDD Policy*



## Analyst Actions

*Actions available for governed disposition: **EDD_REQUIRED***

- **[PRIMARY]** Escalate to Compliance Officer
- Confirm with EDD Conditions
- Request Additional Information



## Timeline

| Field | Value |
|-------|-------|
| Case Created | `2026-02-13T04:39:12.187744Z` |
| EDD Deadline | `2026-02-20T23:59:59.187744Z` |
| Final Disposition Due | Populated when EDD completes |
| STR Filing Window | N/A (no STR determination) |



## Related Activity

| Field | Value |
|-------|-------|
| Prior STRs Filed | 0 |
| Prior Account Closures | No |
| PEP Status | No |
| Sanctions Match | No |
| PEP Screening | No |
| Adverse Media | No |

Connected accounts: Not assessed — requires manual review



## Auditability & Governance

### Decision Provenance

| Field | Value |
|-------|-------|
| Decision Hash | `a4804a5c5df2e00557559cc8823ca4678ddfd612120d22161ad1ec9567216b0e` |
| Input Hash | `ce4b2ac67834a7276939731d125c2b192c472c8a403ec45728c1c55c66498c36` |
| Policy Hash | `7dbc3567f93ab289f74b45b386f045aadce3328d08be59268642a56b98b0fcfe` |
| Decision Path | `PATH_2_SUSPICION` |
| Engine Verdict (Raw) | `STR` |
| Governed Verdict | **EDD_REQUIRED** |
| Engine Disposition | `STR_REQUIRED` |
| Governed Disposition | **EDD_REQUIRED** |

This decision is cryptographically bound to the exact input and policy evaluated.

### Determinism & Auditability Statement

This decision was produced by a deterministic rule engine.
Re-evaluation using identical inputs and the same policy version will produce identical results.

The decision may be independently verified using the `/verify` endpoint. Complete decision lineage, rule sequencing, and evidentiary artifacts are preserved within the immutable audit record and available for supervisory review.



---

*DecisionGraph — Deterministic - Reproducible - Auditable*

*Generated 2026-02-13T04:39:12.187898*
