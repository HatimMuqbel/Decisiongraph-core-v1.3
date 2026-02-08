# AML/KYC Decision Report

**Deterministic Regulatory Decision Engine (Zero LLM)**

---

## Administrative Details

| Field | Value |
|-------|-------|
| Decision ID | `092aa8c212099734...` |
| Case ID | `PAIN-VALIDATION-002` |
| Timestamp | `2026-02-07T23:56:07.265547` |
| Jurisdiction | CA |
| Engine Version | `2.1.1` |
| Policy Version | `1.0.0` |
| Report Schema | `DecisionReportSchema v1` |

---

## Investigation Outcome Summary

### Disposition Ladder

| | |
|---|---|
| **Final Disposition (Classifier Sovereign)** | **NO REPORT** |
| Engine Output (Rules Layer) | NO REPORT — CLOSE_WITH_EDD_RECORDED |

| Field | Value |
|-------|-------|
| Investigation State | CLEARED |
| Primary Typology | No suspicious typology identified |
| Regulatory Obligation |  |
| Regulatory Position | Suspicion threshold not met based on available indicators. |
| STR Required | No |

No suspicious activity indicators detected. Transaction may proceed.

### Case Facts

| Field | Value |
|-------|-------|
| Case ID | `PAIN-VALIDATION-002` |
| Jurisdiction | `CA` |


---

## Canonical Outcome

*Authoritative three-field outcome record per v2 specification. All other sections must be consistent with these values.*

| Field | Value |
|-------|-------|
| Disposition | **NO_REPORT** |
| Disposition Basis | **DISCRETIONARY** |
| Reporting | **NO_REPORT** |


---



---

## Case Classification

| Field | Value |
|-------|-------|
| Source | Production |
| Seed Category | N/A |
| Scenario Code | `N/A` |



---

## Regulatory Determination

### **NO_REPORT** — Alert Cleared

No suspicious activity indicators detected. Transaction may proceed.

**STR Required:** No

### Regulatory Escalation Summary

No escalation or reporting obligation was triggered based on available indicators.

### Confidence Metrics

| Metric | Value | Definition |
|--------|-------|------------|
| Decision Confidence | Elevated Review Recommended (50%) | Composite score reflecting evidence completeness and rule alignment |
| Precedent Alignment | 0% | supporting_decisive / count(decisive_precedents) within same basis |
| Precedent Match Rate | 0% (0 / 0) | Percentage of comparable pool meeting similarity threshold |

Evidence completeness or precedent alignment below standard threshold.

---

## Suspicion Classification

| Field | Value |
|-------|-------|
| Classifier Outcome | **EDD_REQUIRED** |
| Suspicion Indicators (Tier 1) | 0 |
| Investigative Signals (Tier 2) | 2 |
| Classifier Version | `SuspicionClassifier v1` |

2 investigative signal(s) detected. Suspicion threshold not met. Enhanced Due Diligence required to determine regulatory outcome.



### Tier 2 — Investigative Signals (EDD Triggers)

| Code | Source | Detail |
|------|--------|--------|
| `HIGH_VALUE` | evidence | Amount band: 100K+ |
| `CROSS_BORDER` | evidence | Evidence flag txn.cross_border = True |




---

## Decision Drivers

- No indicators meeting suspicion threshold identified
- Investigative trigger: Cross-border transfer with elevated corridor risk
- Escalation blocked by Gate 1 legal basis

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



---

## Rules Evaluated

| Rule Code | Result | Reason |
|-----------|--------|--------|
| `HARD_STOP_CHECK` | CLEAR | No hard stop conditions |
| `PEP_ISOLATION` | APPLIED | PEP status alone cannot escalate |
| `SUSPICION_TEST` | CLEAR | NONE |


---

## Precedent Intelligence

> Precedent analysis missing from decision cache. Re-run the decision and refresh the report.




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
| PEP_FOREIGN | Uncorroborated |
| CROSS_BORDER | Uncorroborated |
| Typology | primary (FORMING) |

---

## Evidence Considered

*Evidence fields reflect the normalized investigation record used for rule evaluation (booleans and buckets). Raw customer identifiers are not included in this report.*

| Field | Scope | Value |
|-------|-------|-------|
| `customer.pep_flag` | Customer PEP status | Yes |
| `customer.type` | Customer entity type | INDIVIDUAL |
| `facts.adverse_media_mltf` | facts.adverse_media_mltf | No |
| `facts.sanctions_result` | facts.sanctions_result | NO_MATCH |
| `mitigations.count` | mitigations.count | 5 |
| `obligations.count` | obligations.count | 1 |
| `risk.high_risk_jurisdiction` | Customer domicile jurisdiction risk | No |
| `suspicion.has_deception` | suspicion.has_deception | No |
| `suspicion.has_intent` | suspicion.has_intent | No |
| `suspicion.has_sustained_pattern` | suspicion.has_sustained_pattern | No |
| `txn.amount_band` | Transaction amount band | 100K+ |
| `txn.cross_border` | Transaction cross-border indicator | Yes |
| `txn.destination_country` | Transaction destination jurisdiction | IT |
| `txn.method` | Payment method | SWIFT Wire Transfer |
| `typology.maturity` | typology.maturity | FORMING |


---



## Timeline

| Field | Value |
|-------|-------|
| Case Created | `2026-02-07T23:56:07.265150Z` |
| EDD Deadline | `N/A` |
| Final Disposition Due | Populated when EDD completes |
| STR Filing Window | N/A (no STR determination) |



## Auditability & Governance

### Decision Provenance

| Field | Value |
|-------|-------|
| Decision Hash | `092aa8c212099734630b3766b76200b375b6a3d1d7f9050612bca46843da1f53` |
| Input Hash | `e2dd6351a1e1fce8e6bbdcd20ba3deb575e57686a5c5c5d51f360756c56ae1fa` |
| Policy Hash | `7dbc3567f93ab289f74b45b386f045aadce3328d08be59268642a56b98b0fcfe` |
| Decision Path | `NO_ESCALATION` |
| Engine Trigger (Rules) | `CLOSE_WITH_EDD_RECORDED` |
| Engine Disposition | `NO_REPORT` |
| Governed Disposition | `NO_REPORT` |

This decision is cryptographically bound to the exact input and policy evaluated.

### Determinism & Auditability Statement

This decision was produced by a deterministic rule engine.
Re-evaluation using identical inputs and the same policy version will produce identical results.

The decision may be independently verified using the `/verify` endpoint. Complete decision lineage, rule sequencing, and evidentiary artifacts are preserved within the immutable audit record and available for supervisory review.



---

*DecisionGraph — Deterministic - Reproducible - Auditable*

*Generated 2026-02-07T23:56:07.265547*
