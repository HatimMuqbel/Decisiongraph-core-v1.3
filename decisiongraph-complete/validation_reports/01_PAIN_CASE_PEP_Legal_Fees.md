# AML/KYC Decision Report

**Deterministic Regulatory Decision Engine (Zero LLM)**

---

## Administrative Details

| Field | Value |
|-------|-------|
| Decision ID | `69db025dc2a49e3d...` |
| Case ID | `TEST-P-01` |
| Timestamp | `2026-02-13T04:39:12.184784` |
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
| Engine Output (Rules Layer) | EDD REQUIRED — CLOSE_WITH_EDD_RECORDED |

| Field | Value |
|-------|-------|
| Investigation State | UNDER REVIEW |
| Primary Typology | Unclassified behavioral indicators (maturity: forming) |
| Regulatory Obligation |  |
| Regulatory Position | Suspicion threshold not met based on available indicators. |
| STR Required | No |

Pass with EDD. Regulatory obligations satisfied.

### Case Facts

| Field | Value |
|-------|-------|
| Case ID | `TEST-P-01` |
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





## Required Actions

1. **[REQUIRED]** Complete EDD by 2026-02-20T23:59:59.184307Z
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

Pass with EDD. Regulatory obligations satisfied.

**STR Required:** No

### Regulatory Escalation Summary

Enhanced Due Diligence is required to complete the investigation and finalize the regulatory outcome.

### Confidence Metrics

| Metric | Value | Definition |
|--------|-------|------------|
| Decision Confidence | Moderate (50%) | Composite score reflecting evidence completeness and rule alignment |
| Institutional Threshold | Within Band | Bands: ≥70% High, 40–70% Moderate, <40% Low (manual review) |
| Precedent Alignment | 0% | supporting_decisive / count(decisive_precedents) within same basis |
| Precedent Match Rate | 0% (0 / 0) | Percentage of comparable pool meeting similarity threshold |

Deterministic rule activation with moderate precedent alignment.

## Disposition Reconciliation

*2 disposition difference(s) detected between engine, classifier, and governed layers.*

**Classification** determined `NO_REPORT` — **Governed** overrode to `EDD_REQUIRED`

> Classification outcome (NO_REPORT) differs from governed disposition (EDD_REQUIRED). Governed disposition follows gate evaluation and governance framework.

> Authority: Final disposition follows governed authority per policy framework

**Engine** determined `EDD_REQUIRED` — **Classification** overrode to `NO_REPORT`

> Engine produced EDD_REQUIRED from rules/gates. Classifier independently determined NO_REPORT from suspicion indicators.

> Authority: Both assessments feed into governed disposition



### ⚠ DECISION CONFLICT

| | |
|---|---|
| Classifier | **NO REPORT** |
| Engine | **EDD REQUIRED** |
| Governed | **EDD REQUIRED** |

> **Resolution:** Gate 1 (Typology Maturity), Gate 2 (STR Threshold), Gate 2 (STR Threshold), Gate 2 (STR Threshold), Gate 2 (STR Threshold), Gate 2 (STR Threshold) blocked escalation — If indicators fail corroboration -> escalation prohibited. Engine followed gate logic.



---

## Suspicion Classification

| Field | Value |
|-------|-------|
| Classifier Outcome | **NO_REPORT** |
| Suspicion Indicators (Tier 1) | 0 |
| Investigative Signals (Tier 2) | 0 |
| Classifier Version | `SuspicionClassifier v1` |

No suspicion or investigative signals detected. Transaction does not meet reporting or escalation thresholds.







---

## Decision Drivers

- Deterministic rule activation requiring review

---

## Gate Evaluation

### Gate 1: Zero-False-Escalation

**Decision:** BLOCKED

| Section | Status | Reason |
|---------|--------|--------|
| Fact-Based Hard Stop Check | PASS | No hard stop conditions detected |
| Instrument Context Validation | PASS | If any mismatch exists -> invalidate related indicators and re-evaluate. |
| Obligation Isolation Check | PASS | If this cannot be stated -> system design is invalid. Fix before proceeding. |
| Indicator Corroboration | FAIL | If indicators fail corroboration -> escalation prohibited. |



### Gate 2: STR Threshold

**STR Required:** No

| Section | Status | Reason |
|---------|--------|--------|
| Legal Suspicion Threshold | REVIEW | Not evaluated - Gate 1 blocked escalation |
| Evidence Quality Check | REVIEW | Not evaluated - Gate 1 blocked escalation |
| Mitigation Failure Analysis | REVIEW | Not evaluated - Gate 1 blocked escalation |
| Typology Confirmation | REVIEW | Not evaluated - Gate 1 blocked escalation |
| Regulatory Reasonableness | REVIEW | Not evaluated - Gate 1 blocked escalation |


### Gate Override Analysis

> All gates consistent with final disposition.



---

## Rules Evaluated

| Rule Code | Result | Reason |
|-----------|--------|--------|
| `HARD_STOP_CHECK` | CLEAR | No hard stop conditions |
| `PEP_ISOLATION` | APPLIED | PEP status alone cannot escalate |
| `SUSPICION_TEST` | CLEAR | NONE |


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





---

## Risk Factors

| Field | Value |
|-------|-------|
| Regulatory obligation | PEP_FOREIGN |
| RULE_772 | Uncorroborated |
| GEO_009 | Uncorroborated |
| Typology | Typology indicators present — below maturity threshold (Early-stage — pattern forming, not yet established) [primary/FORMING] |


---

## Evidence Considered

*Evidence fields reflect the normalized investigation record used for rule evaluation (booleans and buckets). Raw customer identifiers are not included in this report.*

| Field | Scope | Value |
|-------|-------|-------|
| `customer.pep_flag` | customer.pep_flag | No |
| `customer.type` | Customer entity type | INDIVIDUAL |
| `facts.adverse_media_mltf` | Adverse media ML/TF relevance indicator | No |
| `facts.sanctions_result` | Sanctions screening determination | NO_MATCH |
| `mitigations.count` | Count of mitigating factors identified | 5 |
| `obligations.count` | Count of regulatory obligations triggered | 1 |
| `risk.high_risk_jurisdiction` | Customer domicile jurisdiction risk | No |
| `suspicion.has_deception` | Suspicion element: deception indicators present | No |
| `suspicion.has_intent` | Suspicion element: intent indicators present | No |
| `suspicion.has_sustained_pattern` | Suspicion element: sustained transaction pattern | No |
| `txn.cross_border` | Cross-border transaction indicator | No |
| `txn.method` | txn.method | SWIFT_WIRE |
| `typology.maturity` | Typology assessment maturity level | FORMING |


---

## Recommended Actions

1. **Complete enhanced customer due diligence review per institutional policy and escalate to Senior Analyst / Compliance Officer within 5 business days.**
   *Ref: Institutional EDD Policy*



## Analyst Actions

*Actions available for governed disposition: **EDD_REQUIRED***

- **[PRIMARY]** Begin EDD Review
- Request Additional Information
- Escalate



## Timeline

| Field | Value |
|-------|-------|
| Case Created | `2026-02-13T04:39:12.184307Z` |
| EDD Deadline | `2026-02-20T23:59:59.184307Z` |
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
| Decision Hash | `69db025dc2a49e3d5802404534508cf31c94ec69d344ab0b97b58f6d2728a402` |
| Input Hash | `2d48bcf3ea4637401ff4eeee1bb50290a60b628c5f3d19596ad64671f1daf90f` |
| Policy Hash | `7dbc3567f93ab289f74b45b386f045aadce3328d08be59268642a56b98b0fcfe` |
| Decision Path | `NO_ESCALATION` |
| Engine Verdict (Raw) | `PASS_WITH_EDD` |
| Governed Verdict | **PASS_WITH_EDD** |
| Engine Disposition | `EDD_REQUIRED` |
| Governed Disposition | **EDD_REQUIRED** |

This decision is cryptographically bound to the exact input and policy evaluated.

### Determinism & Auditability Statement

This decision was produced by a deterministic rule engine.
Re-evaluation using identical inputs and the same policy version will produce identical results.

The decision may be independently verified using the `/verify` endpoint. Complete decision lineage, rule sequencing, and evidentiary artifacts are preserved within the immutable audit record and available for supervisory review.



---

*DecisionGraph — Deterministic - Reproducible - Auditable*

*Generated 2026-02-13T04:39:12.184784*
