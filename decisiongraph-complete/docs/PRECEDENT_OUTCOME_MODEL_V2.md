# DecisionGraph Core — Precedent Outcome Model v2 Specification

**Three-Field Canonicalization with Dual Deviation for Canadian AML/ATF Compliance**

| Field | Value |
|-------|-------|
| Classification | CONFIDENTIAL — Internal Use Only |
| Regulatory Framework | PCMLTFA, FINTRAC Guidelines, OSFI Guideline B-10 |
| Applicable Jurisdiction | Canada (federal reporting entity obligations) |
| Version | 2.0 |
| Date | February 2026 |
| Status | Specification — Pending Implementation Review |

---

## Table of Contents

1. [Purpose and Regulatory Rationale](#1-purpose-and-regulatory-rationale)
2. [Deficiency Analysis of v1 Model](#2-deficiency-analysis-of-v1-model)
3. [Three-Field Canonicalization Model](#3-three-field-canonicalization-model)
4. [Section 9 — Outcome Canonicalization (v2)](#4-section-9--outcome-canonicalization-v2)
   - 4.1 Canonical Outcome Structure (with Disposition Basis)
   - 4.2 Disposition Mapping
   - 4.3 Disposition Basis Mapping
   - 4.4 Reporting Mapping
   - 4.5 Unknown Handling
5. [Section 10 — Precedent Match Classification (v2)](#5-section-10--precedent-match-classification-v2)
6. [Confidence Formula Adjustment](#6-confidence-formula-adjustment)
7. [Gate Inference Correction](#7-gate-inference-correction)
8. [Regulatory Status Label Derivation](#8-regulatory-status-label-derivation)
9. [Precedent Deviation Logic (Dual Deviation Model)](#9-precedent-deviation-logic-dual-deviation-model)
   - 9.1 Disposition Deviation (Consistency Check)
   - 9.2 Reporting Deviation (Defensibility Check)
   - 9.3 Deviation Summary Matrix
10. [Invariants and Governance Principles](#10-invariants-and-governance-principles)
11. [Auditor Expectations and Examination Readiness](#11-auditor-expectations-and-examination-readiness)
- [Appendix A — FINTRAC Reporting Obligation Reference](#appendix-a--fintrac-reporting-obligation-reference)
- [Appendix B — PCMLTFA Statutory Cross-References](#appendix-b--pcmltfa-statutory-cross-references)

---

## 1. Purpose and Regulatory Rationale

This specification defines a corrected outcome model for DecisionGraph Core's precedent intelligence system. The revision addresses a fundamental architectural flaw: the conflation of disposition actions with regulatory reporting obligations into a single decision axis.

Under the Proceeds of Crime (Money Laundering) and Terrorist Financing Act (PCMLTFA) and its attendant regulations, Canadian reporting entities are subject to two distinct categories of obligation that arise independently:

**Disposition:** The business decision regarding a transaction, account, or relationship (e.g., approve, escalate for enhanced due diligence, block or exit). Dispositions may be legally compelled (mandatory) or risk-based (discretionary) — a distinction that affects precedent comparability.

**Reporting:** The regulatory filing obligation triggered by objective criteria defined in PCMLTFA ss. 7, 7.1, 9, 12, and FINTRAC guidance (e.g., Suspicious Transaction Report, Large Cash Transaction Report, Terrorist Property Report).

These obligations are orthogonal. A transaction may be approved and still require an LCTR filing. A relationship may be maintained while an STR is filed. A block may be compelled by sanctions law with no suspicion of money laundering. Collapsing these dimensions produces logical contradictions that would not survive regulatory examination.

---

## 2. Deficiency Analysis of v1 Model

The v1 precedent model encoded outcomes on a single axis (e.g., "pay", "escalate", "deny") and derived reporting obligations inferentially from disposition. The following deficiencies have been identified:

| Deficiency | Regulatory Impact |
|-----------|-------------------|
| **STR Inference from Denial** | v1 assumed that denial implies STR obligation. Under PCMLTFA s. 7, an STR is triggered by reasonable grounds to suspect that a transaction is related to the commission or attempted commission of a money laundering or terrorist activity financing offence. Denial alone does not establish this threshold. A transaction may be denied for commercial risk reasons with no suspicion of criminal activity. |
| **EDD Treated as Terminal** | Enhanced Due Diligence is a procedural state, not a final disposition. v1 treated EDD as contrary to ALLOW and BLOCK, artificially deflating confidence scores and generating spurious deviation alerts. |
| **Unknown Outcome Handling** | v1 mapped unknown outcomes to "escalate," causing statistical contamination. Precedents with indeterminate outcomes were counted in the confidence denominator, distorting alignment metrics. |
| **Gate Logic Error** | STR gate requirements were derived from workflow state (escalation or denial) rather than from explicit reporting obligation, creating potential for both over-reporting and under-reporting — both of which constitute PCMLTFA compliance failures. |

---

## 3. Three-Field Canonicalization Model

The corrected model separates every precedent outcome into three independent dimensions. This reflects the actual structure of Canadian AML/ATF regulatory obligations and eliminates the logical contradictions present in v1.

| Scenario | Disposition | Basis | Reporting | Regulatory Basis |
|----------|-------------|-------|-----------|-----------------|
| Approve + LCTR filed | **ALLOW** | N/A | **FILE_LCTR** | *PCMLTFA s. 12* |
| STR filed, account maintained | **ALLOW** | N/A | **FILE_STR** | *PCMLTFA s. 7* |
| Blocked due to sanctions match | **BLOCK** | **MANDATORY** | **FILE_STR** | *SEMA / Criminal Code s. 83.08* |
| EDD initiated, no filing yet | **EDD** | N/A | **NO_REPORT** | *OSFI B-10* |
| Denied for credit risk, no suspicion | **BLOCK** | **DISCRETIONARY** | **NO_REPORT** | *Commercial decision* |
| TPR filed, assets frozen | **BLOCK** | **MANDATORY** | **FILE_TPR** | *PCMLTFA s. 7.1 / UNA* |

> **GOVERNANCE PRINCIPLE:** Disposition drives precedent classification. Disposition basis determines comparability. Reporting drives regulatory obligation. These three dimensions must never be conflated in matching logic, confidence scoring, or deviation analysis.

---

## 4. Section 9 — Outcome Canonicalization (v2)

### 4.1 Canonical Outcome Structure

Every precedent outcome normalizes into the following three-field structure:

```
CanonicalOutcome:
    disposition:        ALLOW | EDD | BLOCK | UNKNOWN
    disposition_basis:  MANDATORY | DISCRETIONARY | UNKNOWN
    reporting:          NO_REPORT | FILE_STR | FILE_LCTR | FILE_TPR | UNKNOWN
```

If reporting obligations cannot be determined from source data, the value must be set to `UNKNOWN`. A safe default must never be assumed. Under-reporting is a PCMLTFA offence (s. 73); over-reporting erodes intelligence quality and may constitute a deficiency under FINTRAC examination.

#### Disposition Basis Definitions

**MANDATORY:** Actions compelled by law where the institution has no discretion. This includes sanctions matches under the Special Economic Measures Act (SEMA), the United Nations Act (UNA), and Criminal Code s. 83.08 (terrorist financing), as well as court orders and statutory prohibitions. A mandatory block is a legal obligation, not a risk decision.

**DISCRETIONARY:** Actions based on the institution's risk appetite, internal policy, or commercial judgment. This includes exits for policy violations, fraud risk, reputational concerns, or commercial credit decisions. The institution chose to act; the law did not compel it.

**UNKNOWN:** The legal basis for the disposition cannot be determined from available data.

> ⚠️ **MATCHING CONSTRAINT — Basis Comparability**
>
> Precedents with `disposition_basis == MANDATORY` must not be used as contrary precedents against `DISCRETIONARY` dispositions, and vice versa. A sanctions-compelled BLOCK and a risk-appetite ALLOW are not comparable decisions — the institution had no choice in the former. Cross-basis comparisons are excluded from deviation analysis and confidence scoring. They may appear in precedent listings as informational context only, with the basis mismatch clearly flagged.

### 4.2 Disposition Mapping

| Raw Input Values | Canonical Disposition |
|-----------------|----------------------|
| approve, approved, accept, pass, cleared, eligible, no action | **ALLOW** |
| review, investigate, hold, pending, manual review, needs info, pass with edd | **EDD** |
| deny, decline, reject, blocked, refuse, exit, hard stop, de-risk | **BLOCK** |
| missing, ambiguous, contradictory, or not determinable | **UNKNOWN** |

### 4.3 Disposition Basis Mapping

| Raw Input / Context | Canonical Basis | Nature |
|--------------------|-----------------|--------|
| sanctions match, SEMA, UNA, Criminal Code s. 83.08, listed entity, court order, statutory prohibition | **MANDATORY** | *No institutional discretion* |
| risk appetite, policy violation, commercial exit, fraud risk, reputational concern, credit decision | **DISCRETIONARY** | *Institutional judgment* |
| not specified, not determinable, ambiguous | **UNKNOWN** | *N/A* |

### 4.4 Reporting Mapping

| Raw Input Values | Canonical Reporting | Statutory Ref. |
|-----------------|--------------------:|----------------|
| str, report str, suspicious transaction, suspicious activity | **FILE_STR** | *PCMLTFA s. 7* |
| lctr, large cash, large cash transaction | **FILE_LCTR** | *PCMLTFA s. 12* |
| tpr, terrorist property, terrorist property report | **FILE_TPR** | *PCMLTFA s. 7.1* |
| explicitly stated: no report, no filing required | **NO_REPORT** | *N/A* |
| not specified, not determinable | **UNKNOWN** | *N/A* |

> 🚨 **REGULATORY INVARIANT — STR Inference Prohibition**
>
> An STR obligation must never be inferred from escalation or denial. Under PCMLTFA s. 7, the filing threshold is "reasonable grounds to suspect" that a transaction is related to a money laundering or terrorist financing offence. Escalation indicates investigation is required. Denial indicates a risk-based business action. Neither establishes the statutory suspicion threshold. Only an explicit reporting determination, typically made by a designated compliance officer, satisfies the STR trigger. Violating this invariant creates direct audit exposure under FINTRAC's Administrative Monetary Penalties regime.

### 4.5 Unknown Handling

**v1 Behaviour (Removed):** Unknown outcomes were mapped to "escalate," causing them to be counted as EDD dispositions and contaminating confidence calculations.

**v2 Behaviour:** Unknown outcomes remain `UNKNOWN`. They are excluded from supporting counts, contrary counts, and the confidence denominator. They appear in precedent listings as informational references only.

This prevents silent statistical distortion. A precedent with an unknown outcome provides context but cannot influence a decision's confidence score or deviation analysis.

---

## 5. Section 10 — Precedent Match Classification (v2)

Precedent classification uses disposition as the primary axis. Reporting differences inform obligation analysis but do not affect match classification.

### 5.1 Supporting Precedents

A precedent is classified as **Supporting** when its disposition matches the current case disposition:

```
precedent.disposition == case.disposition
```

Reporting differences do not invalidate support. For example, if the current case disposition is EDD and a matched precedent has disposition EDD with reporting FILE_STR, the precedent is still Supporting. The escalation path is consistent; the reporting obligation is a separate analytical dimension.

### 5.2 Contrary Precedents

Contrary classification is reserved exclusively for terminal disposition conflicts:

```
ALLOW vs. BLOCK
BLOCK vs. ALLOW
```

These are the only true decision contradictions in AML compliance. One institution approved what another blocked under comparable circumstances. This is the signal that auditors and examiners look for when assessing consistency.

### 5.3 Neutral Precedents

All other disposition combinations are classified as **Neutral**:

```
EDD vs. ALLOW     → Neutral
EDD vs. BLOCK     → Neutral
ANY vs. UNKNOWN   → Neutral
UNKNOWN vs. ANY   → Neutral
```

**Regulatory justification:** EDD is a procedural state meaning "investigation required before final determination." It is not a terminal decision. It cannot logically contradict either ALLOW or BLOCK because it has not yet resolved into either. Treating EDD as contrary to terminal dispositions artificially deflates confidence scores and generates misleading deviation alerts that erode examiner trust in the system.

> **CLASSIFICATION PRINCIPLE:** Only terminal outcomes can contradict. EDD cannot contradict anything — it delays resolution. This single rule stabilizes confidence scoring and aligns precedent intelligence with how FINTRAC examiners evaluate institutional consistency.

---

## 6. Confidence Formula Adjustment

### 6.1 Previous Formula (v1)

```
confidence = supporting / (supporting + contrary)
```

This denominator included EDD and UNKNOWN outcomes, which diluted confidence with non-decisive data and answered the wrong question.

### 6.2 Corrected Formula (v2)

```
comparable = precedents WHERE disposition_basis == case.disposition_basis
decisive_precedents = comparable WHERE disposition IN {ALLOW, BLOCK}
supporting_decisive = decisive_precedents WHERE disposition == case.disposition
confidence = supporting_decisive / count(decisive_precedents)
```

The confidence score now answers the correct regulatory question: "When institutions made a final, terminal decision in comparable cases with the same disposition basis, how consistent were those decisions with the current disposition?"

This is materially different from asking how many cases were still under investigation — a metric that has no regulatory value for disposition confidence.

> ⚠️ **EXAMINER NOTE**
>
> FINTRAC examiners evaluating a reporting entity's transaction monitoring system will assess whether the system's confidence metrics reflect actual decision consistency. A confidence score inflated or deflated by including non-terminal outcomes (EDD, UNKNOWN) or cross-basis precedents (MANDATORY vs. DISCRETIONARY) would be identified as a control weakness during a compliance examination under PCMLTFA s. 62.

---

## 7. Gate Inference Correction

### 7.1 Previous Gate Logic (v1 — Removed)

```
gate2_str_required = outcome IN {"escalate", "deny"}
```

This logic inferred STR obligation from workflow state, which has no statutory basis.

### 7.2 Corrected Gate Logic (v2)

```
gate2_str_required = reporting == FILE_STR
```

Gate logic must attach to the explicit regulatory obligation, not to disposition or workflow state. Under PCMLTFA s. 7, the STR obligation arises from a determination of reasonable grounds to suspect — not from the business action taken on the transaction or relationship.

---

## 8. Regulatory Status Label Derivation

The following table replaces the v1 report label mapping in its entirety. Labels are derived from the combination of disposition and reporting values, ensuring every displayed status is logically correct and free of regulatory contradiction.

| Condition | Display Label | Regulatory Meaning |
|-----------|--------------|-------------------|
| `reporting == FILE_STR` | **STR REQUIRED** | *PCMLTFA s. 7 obligation confirmed* |
| `disposition == BLOCK AND reporting != FILE_STR` | **BLOCKED — NO STR** | *Risk-based exit without suspicion finding* |
| `disposition == EDD` | **EDD REQUIRED** | *Enhanced due diligence pending* |
| `disposition == ALLOW AND reporting == NO_REPORT` | **NO REPORT** | *Transaction cleared, no filing obligation* |
| `disposition == ALLOW AND reporting == FILE_LCTR` | **LCTR + ALLOW** | *Approved with large cash filing* |
| `disposition == ALLOW AND reporting == FILE_TPR` | **TPR + ALLOW** | *Approved with terrorist property filing* |

---

## 9. Precedent Deviation Logic (Dual Deviation Model)

Deviation analysis is bifurcated to address the two distinct regulatory risks that arise from precedent divergence: inconsistency (unfairness in decisioning) and defensibility (failure to meet reporting obligations). Each risk requires its own alert type, threshold logic, and remediation path.

### 9.1 Disposition Deviation (Consistency Check)

Disposition deviation identifies cases where the current business action diverges from the majority of comparable precedent dispositions. This is the consistency signal that examiners and auditors look for when assessing whether an institution applies its risk appetite uniformly.

**Trigger Condition:**

```
case.disposition != majority(comparable_precedents.disposition)
AND comparable_precedents filtered to same disposition_basis
```

**Alert Type:** Consistency Warning

**Example Message:**

```
"92% of comparable DISCRETIONARY precedents resulted in BLOCK while the current disposition is ALLOW."
```

**Goal:** Prevent internal unfairness, risk appetite violations, and inconsistent treatment of comparable counterparties. Note that disposition deviation compares only within the same basis category — MANDATORY precedents are never compared against DISCRETIONARY decisions, as the institution had no choice in the former.

### 9.2 Reporting Deviation (Defensibility Check)

Reporting deviation identifies cases where the current reporting decision is less severe than the historical filing pattern for comparable cases. This is the defensibility signal that protects against PCMLTFA s. 73 failure-to-report findings.

**Trigger Condition:**

```
case.reporting severity < majority(comparable_precedents.reporting severity)

Severity ordering for judgment-based filings:
  FILE_STR > NO_REPORT
  FILE_TPR > NO_REPORT

Note: LCTR is threshold-based (objective $10,000 trigger),
not judgment-based. LCTR gaps are arithmetic errors, not
defensibility failures, and are handled separately.
```

**Alert Type:** Defensibility Alert

**Example Message:**

```
"Current proposal to NOT FILE contradicts 90% historical STR filing rate for this typology."
```

**Goal:** Prevent systemic under-reporting and PCMLTFA s. 73 violations. Under FINTRAC's Administrative Monetary Penalties regime, a pattern of non-filing where comparable cases resulted in STRs constitutes strong evidence of a compliance program deficiency. This alert ensures the Chief Compliance Officer has visibility into reporting divergence before a no-file decision is finalized.

> 🚨 **DEFENSIBILITY NOTE — s. 73 Exposure**
>
> PCMLTFA s. 73 makes it an offence for a reporting entity to fail to file a required report. A Defensibility Alert does not create a filing obligation by itself — the determination of reasonable grounds to suspect must still be made by a designated officer. However, a pattern of Defensibility Alerts that are overridden without documented rationale would constitute a material examination finding.

### 9.3 Deviation Summary Matrix

| Deviation Type | Alert Class | Description | Regulatory Basis |
|---------------|-------------|-------------|-----------------|
| **Disposition deviation** | Consistency Warning | Action divergence from comparable precedents | *Risk appetite / fairness* |
| **Reporting deviation (STR/TPR)** | Defensibility Alert | Filing rate below comparable precedent history | *PCMLTFA s. 73 / s. 73.1* |
| **LCTR gap** | Threshold Alert | Missing LCTR where $10,000+ cash received | *PCMLTFA s. 12 (objective)* |
| **Cross-basis comparison** | Informational Only | MANDATORY vs. DISCRETIONARY basis mismatch | *Not scored* |

---

## 10. Invariants and Governance Principles

The following invariants must be enforced at the system level. Any code path that violates these invariants constitutes a compliance defect requiring immediate remediation.

| ID | Invariant | Basis |
|----|-----------|-------|
| **INV-001** | STR obligation must never be inferred from disposition | *PCMLTFA s. 7* |
| **INV-002** | Disposition, disposition basis, and reporting must be stored and evaluated as independent dimensions | *Architectural* |
| **INV-003** | UNKNOWN outcomes must be excluded from confidence denominators | *Statistical integrity* |
| **INV-004** | Only ALLOW vs. BLOCK constitutes a contrary precedent | *Regulatory semantics* |
| **INV-005** | EDD must be classified as Neutral in all precedent comparisons | *Regulatory semantics* |
| **INV-006** | Gate logic must derive from reporting, never from disposition or workflow state | *PCMLTFA s. 7* |
| **INV-007** | Disposition deviation triggers Consistency Alerts; Reporting deviation triggers Defensibility Alerts | *Examination readiness* |
| **INV-008** | MANDATORY and DISCRETIONARY dispositions must not be compared in deviation analysis or confidence scoring | *SEMA / UNA / Criminal Code s. 83.08* |
| **INV-009** | Defensibility Alerts overridden without documented rationale constitute an examination finding | *PCMLTFA s. 73 / s. 73.1* |

---

## 11. Auditor Expectations and Examination Readiness

This section addresses the specific concerns a FINTRAC examiner or external auditor would raise when reviewing a precedent-based decision engine deployed within a Canadian reporting entity.

### 11.1 FINTRAC Examination Considerations

Under PCMLTFA s. 62, FINTRAC has authority to examine a reporting entity's compliance program, including its transaction monitoring systems and the models underlying automated or semi-automated decision-making. An examiner reviewing DecisionGraph would specifically assess:

**Separation of obligations:** Whether the system correctly distinguishes between business decisions and regulatory filing obligations, and whether one is ever improperly derived from the other.

**Mandatory vs. discretionary distinction:** Whether sanctions-compelled actions are properly segregated from risk-appetite decisions in precedent matching, ensuring that legal obligations are not conflated with business judgment.

**STR threshold integrity:** Whether STR determinations are based on a documented finding of reasonable grounds to suspect, or whether they are mechanically inferred from transaction blocking or escalation.

**Defensibility of no-file decisions:** Whether the system generates alerts when a no-file decision contradicts historical filing patterns, and whether overrides of Defensibility Alerts are documented with rationale.

**Confidence metric validity:** Whether confidence scores reflect actual decision consistency among terminal outcomes within the same disposition basis, or whether they are distorted by including non-decisive or cross-basis precedents.

**Audit trail completeness:** Whether each precedent match includes disposition, disposition basis, and reporting dimensions with full provenance, enabling post-hoc reconstruction of any decision path.

### 11.2 OSFI Guideline B-10 Alignment

OSFI Guideline B-10 (Third-Party Risk Management, applicable to federally regulated financial institutions) and the related AML/ATF expectations require that risk-based decision-making systems demonstrate consistent, defensible outputs. The three-field model supports this by ensuring that EDD escalations are not conflated with terminal risk actions, that mandatory legal obligations are distinguished from discretionary risk decisions, and that precedent-based confidence reflects the institution's actual decisioning history.

### 11.3 What This Model Prevents

The v2 three-field canonicalization model with dual deviation automatically eliminates the following categories of audit findings:

| Finding Category | How v2 Prevents It |
|-----------------|-------------------|
| **False STR precedent alignment** | Precedents no longer appear to support STR filing when only disposition (not reporting) matched. |
| **Spurious deviation alerts** | Dual deviation model separates action consistency from filing defensibility, eliminating false positives. |
| **Confidence score distortion** | Non-terminal outcomes are excluded from the denominator, producing scores that reflect actual institutional consistency. |
| **Escalation contradiction errors** | EDD is correctly treated as procedural, not contrary, preventing artificial deflation of confidence. |
| **Cross-basis false contradictions** | Sanctions-compelled BLOCKs are never compared against discretionary ALLOWs, preventing incomparable precedent matching. |
| **Systemic under-reporting** | Defensibility Alerts flag cases where the no-file decision contradicts historical STR/TPR filing patterns for the typology. |
| **Report/UI label mismatches** | Display labels are derived deterministically from the three-field model, eliminating contradictory status displays. |
| **Governance inconsistency** | Every label, alert, and confidence score traces to a documented invariant with statutory or regulatory basis. |

---

## Appendix A — FINTRAC Reporting Obligation Reference

The following table summarizes the primary reporting obligations under PCMLTFA applicable to the DecisionGraph reporting model. This is not exhaustive; reporting entities should consult FINTRAC guidance for complete obligation details including prescribed timelines.

| Report Type | Statute | Trigger | Filing Deadline |
|------------|---------|---------|----------------|
| **Suspicious Transaction Report (STR)** | *PCMLTFA s. 7* | Reasonable grounds to suspect ML/TF | 30 days from determination |
| **Large Cash Transaction Report (LCTR)** | *PCMLTFA s. 12* | Cash receipt of $10,000+ (single or 24-hr rule) | 15 calendar days |
| **Terrorist Property Report (TPR)** | *PCMLTFA s. 7.1* | Property owned/controlled by listed entity | Without delay |
| **Electronic Funds Transfer Report (EFTR)** | *PCMLTFA s. 12* | International EFT of $10,000+ | 5 business days |
| **Casino Disbursement Report (CDR)** | *PCMLTFA s. 12* | Casino disbursement of $10,000+ | 15 calendar days |

---

## Appendix B — PCMLTFA Statutory Cross-References

| Reference | Description |
|-----------|-------------|
| **PCMLTFA s. 7** | STR filing obligation for reporting entities |
| **PCMLTFA s. 7.1** | Terrorist property reporting obligation |
| **PCMLTFA s. 9** | Record-keeping requirements |
| **PCMLTFA s. 9.6** | Compliance program requirements |
| **PCMLTFA s. 12** | Large cash and EFT reporting |
| **PCMLTFA s. 62** | FINTRAC examination authority |
| **PCMLTFA s. 73** | Offence provisions (failure to report) |
| **PCMLTFA s. 73.1** | Administrative monetary penalties |
| **OSFI Guideline B-10** | Third-Party Risk Management |
| **SEMA** | Special Economic Measures Act (sanctions) |
| **UNA** | United Nations Act (international sanctions) |
| **Criminal Code s. 83.08** | Terrorist financing prohibition |
| **Criminal Code s. 462.31** | Money laundering offence |

---

*— End of Specification —*
