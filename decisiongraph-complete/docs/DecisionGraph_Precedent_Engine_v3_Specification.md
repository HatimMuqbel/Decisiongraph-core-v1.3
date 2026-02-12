


**Three-Layer Comparability Model with Governed Confidence for Regulated Decision Intelligence**

| Field | Value |
|-------|-------|
| Classification | CONFIDENTIAL — Internal Use Only |
| Regulatory Framework | PCMLTFA, FINTRAC Guidelines, OSFI Guideline B-10 |
| Applicable Jurisdiction | Canada (federal reporting entity obligations) |
| Version | 3.0 |
| Date | February 2026 |
| Status | Specification — Authoritative |
| Supersedes | Precedent Outcome Model v2 (Three-Field Canonicalization) |

---

## Table of Contents

1. [Purpose and Scope](#1-purpose-and-scope)
2. [Architecture Overview](#2-architecture-overview)
3. [Foundation: Three-Field Canonicalization](#3-foundation-three-field-canonicalization)
   - 3.1 Canonical Outcome Structure
   - 3.2 Disposition Mapping
   - 3.3 Disposition Basis Mapping
   - 3.4 Reporting Mapping
   - 3.5 Unknown Handling
   - 3.6 Regulatory Status Label Derivation
4. [Layer 1: Comparability Gate](#4-layer-1-comparability-gate)
   - 4.1 Purpose
   - 4.2 Equivalence Classes
   - 4.3 Gate Rules
5. [Layer 2: Causal Factor Alignment](#5-layer-2-causal-factor-alignment)
   - 5.1 Domain Registry Model
   - 5.2 Field Definitions
   - 5.3 Typed Comparison Functions
   - 5.4 Driver-Aware Asymmetric Scoring
   - 5.5 Non-Transferable Precedents
   - 5.6 Similarity Floor
6. [Layer 3: Governed Confidence](#6-layer-3-governed-confidence)
   - 6.1 Four-Dimension Model
   - 6.2 Pool Adequacy
   - 6.3 Similarity Quality
   - 6.4 Outcome Consistency
   - 6.5 Evidence Completeness
   - 6.6 Confidence Resolution
   - 6.7 Hard Rules
7. [Precedent Match Classification](#7-precedent-match-classification)
   - 7.1 Supporting Precedents
   - 7.2 Contrary Precedents
   - 7.3 Neutral Precedents
8. [Dual Deviation Model](#8-dual-deviation-model)
   - 8.1 Disposition Deviation (Consistency Check)
   - 8.2 Reporting Deviation (Defensibility Check)
   - 8.3 Deviation Summary Matrix
9. [Gate Inference Rules](#9-gate-inference-rules)
10. [Precedent Report Output](#10-precedent-report-output)
    - 10.1 Section 1: Governed Disposition Alignment
    - 10.2 Section 2: Terminal Confidence
    - 10.3 Section 3: Distinguishing Factor Analysis
    - 10.4 Section 4: Divergence Justification
    - 10.5 Section 5: Institutional Posture Statement
11. [Domain Portability](#11-domain-portability)
    - 11.1 Domain Registry Structure
    - 11.2 Adding a New Domain
12. [Invariants and Governance Principles](#12-invariants-and-governance-principles)
13. [Output Validation Layer](#13-output-validation-layer)
14. [Auditor Expectations and Examination Readiness](#14-auditor-expectations-and-examination-readiness)
    - 14.1 FINTRAC Examination Considerations
    - 14.2 OSFI Guideline B-10 Alignment
    - 14.3 What This Model Prevents
- [Appendix A — FINTRAC Reporting Obligation Reference](#appendix-a--fintrac-reporting-obligation-reference)
- [Appendix B — PCMLTFA Statutory Cross-References](#appendix-b--pcmltfa-statutory-cross-references)
- [Appendix C — Banking AML Field Registry Reference](#appendix-c--banking-aml-field-registry-reference)
- [Appendix D — Deficiency Analysis of Prior Models](#appendix-d--deficiency-analysis-of-prior-models)

---

## 1. Purpose and Scope

This specification defines the complete precedent intelligence system for DecisionGraph Core. It is the single authoritative document governing how precedents are stored, compared, scored, and reported.

This specification incorporates and supersedes:

- **v1 model** (single-axis outcomes) — replaced entirely
- **v2 model** (three-field canonicalization with dual deviation) — retained as the foundation (Section 3), extended with the Three-Layer Comparability Model (Sections 4–6) and Governed Confidence (Section 6)

The system addresses three fundamental questions for every decision:

1. **What does the bank usually do in cases like this?** (Governed Disposition Alignment)
2. **When the bank made a final decision, how consistent was it?** (Terminal Confidence)
3. **If this decision diverges from precedent, why is the divergence justified?** (Divergence Justification)

The architecture is domain-portable. Sections 3–10 define domain-agnostic mechanisms. Section 11 defines the registry pattern that adapts the engine to any regulated domain (banking AML, insurance, corporate governance) without code changes.

---

## 2. Architecture Overview

```
INPUT (any source: demo, seed, JSON, API)
          │
          ▼
┌─────────────────────────────────────────────┐
│  LAYER 1: COMPARABILITY GATE                │
│  Hard filter using equivalence classes      │
│  Incomparable cases are excluded entirely   │
│  Driven by: Domain Registry gate fields     │
└─────────────────┬───────────────────────────┘
                  │ Comparable pool
                  ▼
┌─────────────────────────────────────────────┐
│  LAYER 2: CAUSAL FACTOR ALIGNMENT           │
│  Typed similarity with driver awareness     │
│  Non-transferable detection                 │
│  Driven by: Domain Registry field defs      │
└─────────────────┬───────────────────────────┘
                  │ Scored + classified pool
                  ▼
┌─────────────────────────────────────────────┐
│  LAYER 3: GOVERNED CONFIDENCE               │
│  Four-dimension min() model                 │
│  No hardcoded fallbacks                     │
│  Driven by: Domain Registry thresholds      │
└─────────────────┬───────────────────────────┘
                  │ Complete analysis
                  ▼
┌─────────────────────────────────────────────┐
│  OUTPUT: Five-Section Precedent Report       │
│  Governed Alignment │ Terminal Confidence    │
│  Distinguishing Factors │ Divergence Just.  │
│  Institutional Posture                      │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  VALIDATION LAYER                            │
│  Checks output consistency before render    │
│  Auto-corrects fixable issues               │
│  Flags issues requiring human review        │
└─────────────────────────────────────────────┘
```

---

## 3. Foundation: Three-Field Canonicalization

Under the Proceeds of Crime (Money Laundering) and Terrorist Financing Act (PCMLTFA) and its attendant regulations, Canadian reporting entities are subject to two distinct categories of obligation that arise independently:

**Disposition:** The business decision regarding a transaction, account, or relationship. Dispositions may be legally compelled (mandatory) or risk-based (discretionary) — a distinction that affects precedent comparability.

**Reporting:** The regulatory filing obligation triggered by objective criteria defined in PCMLTFA ss. 7, 7.1, 9, 12, and FINTRAC guidance.

These obligations are orthogonal. A transaction may be approved and still require an LCTR filing. A relationship may be maintained while an STR is filed. A block may be compelled by sanctions law with no suspicion of money laundering.

> **GOVERNANCE PRINCIPLE:** Disposition drives precedent classification. Disposition basis determines comparability. Reporting drives regulatory obligation. These three dimensions must never be conflated in matching logic, confidence scoring, or deviation analysis.

### 3.1 Canonical Outcome Structure

Every precedent outcome normalizes into three independent fields:

```
CanonicalOutcome:
    disposition:        ALLOW | EDD | BLOCK | UNKNOWN
    disposition_basis:  MANDATORY | DISCRETIONARY | UNKNOWN
    reporting:          NO_REPORT | FILE_STR | FILE_LCTR | FILE_TPR | UNKNOWN
```

Reference scenarios:

| Scenario | Disposition | Basis | Reporting | Regulatory Basis |
|----------|-------------|-------|-----------|-----------------|
| Approve + LCTR filed | **ALLOW** | N/A | **FILE_LCTR** | *PCMLTFA s. 12* |
| STR filed, account maintained | **ALLOW** | N/A | **FILE_STR** | *PCMLTFA s. 7* |
| Blocked due to sanctions match | **BLOCK** | **MANDATORY** | **FILE_STR** | *SEMA / Criminal Code s. 83.08* |
| EDD initiated, no filing yet | **EDD** | N/A | **NO_REPORT** | *OSFI B-10* |
| Denied for credit risk, no suspicion | **BLOCK** | **DISCRETIONARY** | **NO_REPORT** | *Commercial decision* |
| TPR filed, assets frozen | **BLOCK** | **MANDATORY** | **FILE_TPR** | *PCMLTFA s. 7.1 / UNA* |

If reporting obligations cannot be determined from source data, the value must be set to `UNKNOWN`. A safe default must never be assumed. Under-reporting is a PCMLTFA offence (s. 73); over-reporting erodes intelligence quality and may constitute a deficiency under FINTRAC examination.

### 3.2 Disposition Mapping

| Raw Input Values | Canonical Disposition |
|-----------------|----------------------|
| approve, approved, accept, pass, cleared, eligible, no action | **ALLOW** |
| review, investigate, hold, pending, manual review, needs info, pass with edd | **EDD** |
| deny, decline, reject, blocked, refuse, exit, hard stop, de-risk | **BLOCK** |
| missing, ambiguous, contradictory, or not determinable | **UNKNOWN** |

### 3.3 Disposition Basis Mapping

| Raw Input / Context | Canonical Basis | Nature |
|--------------------|-----------------|--------|
| sanctions match, SEMA, UNA, Criminal Code s. 83.08, listed entity, court order, statutory prohibition | **MANDATORY** | *No institutional discretion* |
| risk appetite, policy violation, commercial exit, fraud risk, reputational concern, credit decision | **DISCRETIONARY** | *Institutional judgment* |
| not specified, not determinable, ambiguous | **UNKNOWN** | *N/A* |

> **MATCHING CONSTRAINT — Basis Comparability:** Precedents with `disposition_basis == MANDATORY` must not be used as contrary precedents against `DISCRETIONARY` dispositions, and vice versa. A sanctions-compelled BLOCK and a risk-appetite ALLOW are not comparable decisions — the institution had no choice in the former. Cross-basis comparisons are excluded from deviation analysis and confidence scoring. They may appear in precedent listings as informational context only, with the basis mismatch clearly flagged.

### 3.4 Reporting Mapping

| Raw Input Values | Canonical Reporting | Statutory Ref. |
|-----------------|--------------------:|----------------|
| str, report str, suspicious transaction, suspicious activity | **FILE_STR** | *PCMLTFA s. 7* |
| lctr, large cash, large cash transaction | **FILE_LCTR** | *PCMLTFA s. 12* |
| tpr, terrorist property, terrorist property report | **FILE_TPR** | *PCMLTFA s. 7.1* |
| explicitly stated: no report, no filing required | **NO_REPORT** | *N/A* |
| not specified, not determinable | **UNKNOWN** | *N/A* |

> **REGULATORY INVARIANT — STR Inference Prohibition:** An STR obligation must never be inferred from escalation or denial. Under PCMLTFA s. 7, the filing threshold is "reasonable grounds to suspect" that a transaction is related to a money laundering or terrorist financing offence. Escalation indicates investigation is required. Denial indicates a risk-based business action. Neither establishes the statutory suspicion threshold. Only an explicit reporting determination, typically made by a designated compliance officer, satisfies the STR trigger.

### 3.5 Unknown Handling

Unknown outcomes remain `UNKNOWN`. They are excluded from supporting counts, contrary counts, and the confidence denominator. They appear in precedent listings as informational references only. This prevents silent statistical distortion.

### 3.6 Regulatory Status Label Derivation

Labels are derived deterministically from the three-field model:

| Condition | Display Label | Regulatory Meaning |
|-----------|--------------|-------------------|
| `reporting == FILE_STR` | **STR REQUIRED** | *PCMLTFA s. 7 obligation confirmed* |
| `disposition == BLOCK AND reporting != FILE_STR` | **BLOCKED — NO STR** | *Risk-based exit without suspicion finding* |
| `disposition == EDD` | **EDD REQUIRED** | *Enhanced due diligence pending* |
| `disposition == ALLOW AND reporting == NO_REPORT` | **NO REPORT** | *Transaction cleared, no filing obligation* |
| `disposition == ALLOW AND reporting == FILE_LCTR` | **LCTR + ALLOW** | *Approved with large cash filing* |
| `disposition == ALLOW AND reporting == FILE_TPR` | **TPR + ALLOW** | *Approved with terrorist property filing* |

---

## 4. Layer 1: Comparability Gate

### 4.1 Purpose

Before any similarity calculation, filter precedents by comparability. Incomparable precedents do not exist for the current case. This is a yes/no gate, not a score.

The gate prevents false analogies — comparing a sanctions-compelled block to a risk-appetite decision, or a retail cash transaction to a corporate trade finance deal. These are not "low similarity" — they are incomparable, like comparing a murder case to a parking ticket.

### 4.2 Equivalence Classes

Gates use policy-defined equivalence classes, not exact field matches. A wire and an ACH are both "electronic" — the policy says they're comparable.

```
ComparabilityGate:
    field:              str           # registry field name
    equivalence_classes: dict         # maps class name → list of raw values
```

Banking AML default gates:

| Gate Field | Equivalence Classes |
|-----------|-------------------|
| `jurisdiction_regime` | CA_FINTRAC: [CA] · US_FinCEN: [US] · UK_FCA: [UK, GB] |
| `customer_segment` | retail: [individual, personal, retail] · SME: [sme, small_business] · corporate: [corporate, institutional, company] · FI: [bank, fi, financial_institution] |
| `channel_family` | cash: [cash, cash_deposit, cash_withdrawal] · electronic: [wire, ach, eft, swift, domestic_wire] · crypto: [crypto, virtual_currency, digital_asset] · trade: [trade_finance, lc, documentary_credit] |
| `disposition_basis` | MANDATORY: [MANDATORY] · DISCRETIONARY: [DISCRETIONARY] |

### 4.3 Gate Rules

1. A precedent must match the current case on ALL gates to enter the comparable pool.
2. Matching uses equivalence classes — values within the same class are treated as identical.
3. MANDATORY and DISCRETIONARY disposition bases are NEVER comparable (INV-008).
4. If a gate field is missing from the current case, log a warning but do not exclude all precedents — use the broadest equivalence class as fallback.
5. Gates are defined in the Domain Registry, not hardcoded in the engine.
6. Precedents excluded by gates are not scored, not displayed, and do not exist for confidence calculations.

---

## 5. Layer 2: Causal Factor Alignment

### 5.1 Domain Registry Model

All comparison behavior is driven by a domain registry. The comparison engine is domain-agnostic — it reads the registry and adapts.

```
DomainRegistry:
    domain:                     str                 # "banking_aml"
    fields:                     list[FieldDefinition]
    comparability_gates:        list[str]           # field names for Layer 1
    similarity_floor:           float               # default 0.60
    similarity_floor_overrides: dict                # per typology: {"sanctions": 0.80}
    confidence_thresholds:      ConfidenceScale
    pool_minimum:               int                 # min for reliable metrics (5)
    critical_fields:            list[str]           # absence caps confidence
```

### 5.2 Field Definitions

Every field in the registry carries comparison metadata:

```
FieldDefinition:
    name:                 str           # "flag.layering"
    label:                str           # "Layering indicators present"
    type:                 FieldType     # BOOLEAN | CATEGORICAL | NUMERIC | ORDINAL | SET
    comparison:           ComparisonFn  # EXACT | EQUIVALENCE_CLASS | DISTANCE_DECAY | STEP | JACCARD
    weight:               float         # 0.0–1.0, domain-specific importance
    tier:                 FieldTier     # STRUCTURAL | BEHAVIORAL | CONTEXTUAL
    required:             bool          # must be present for valid comparison
    critical:             bool          # absence caps confidence at LOW
    equivalence_classes:  dict          # for CATEGORICAL: {"electronic": ["wire", "ach"]}
    domain:               list[str]     # ["banking_aml"]
```

**Field Types:**

| Type | Description | Example |
|------|-------------|---------|
| BOOLEAN | True/false flag | flag.layering, screening.sanctions_match |
| CATEGORICAL | Discrete category | txn.type, customer.type |
| NUMERIC | Continuous or banded value | txn.amount, txn.frequency_30d |
| ORDINAL | Ordered discrete value | risk_level (low/medium/high) |
| SET | Multiple values | triggered_rules, active_flags |

**Field Tiers:**

| Tier | Purpose | Used In |
|------|---------|---------|
| STRUCTURAL | Defines comparability | Layer 1 gate filter |
| BEHAVIORAL | Drives similarity scoring as decision drivers | Layer 2 scoring (2x weight when driver) |
| CONTEXTUAL | Stabilizes similarity without driving outcomes | Layer 2 scoring (1x weight) |

### 5.3 Typed Comparison Functions

| ComparisonFn | Logic | Example |
|-------------|-------|---------|
| EXACT | Boolean: 0.0 or 1.0 | true vs true → 1.0, true vs false → 0.0 |
| EQUIVALENCE_CLASS | Same class → 1.0, different → 0.0 | wire vs ACH → 1.0 (both "electronic") |
| DISTANCE_DECAY | 1.0 − (abs(a−b) / max_range), floored at 0.0 | 500K vs 750K → 0.8, vs 5M → 0.2 |
| STEP | 1.0 − (step_diff / max_steps) | high vs medium → 0.5, vs low → 0.0 |
| JACCARD | intersection / union | {A,B,C} vs {A,B,D} → 0.67 |

### 5.4 Driver-Aware Asymmetric Scoring

Every precedent stores which features drove its outcome (decision drivers) versus which were merely present (context). Scoring is asymmetric:

- **Driver match** (present in precedent AND current case, values agree): full weight × 2.0
- **Context match** (non-driver, values agree): full weight × 1.0
- **Driver mismatch** (present in both, values contradict): triggers non-transferable flag (see 5.5)
- **Driver absent** (present in precedent, missing in current case): triggers non-transferable flag
- **Context mismatch**: weight × 0.0 (neutral, does not penalize)

```
similarity(case, precedent, registry):
    score = 0.0
    total_weight = 0.0
    non_transferable = false
    non_transferable_reasons = []

    for field in registry.fields where tier != STRUCTURAL:
        case_val = case[field.name]
        prec_val = precedent[field.name]
        is_driver = field.name in precedent.decision_drivers

        if case_val is missing or prec_val is missing:
            if is_driver and case_val is missing:
                non_transferable = true
                reason: "{field.label} was a decision driver but is missing"
            continue

        match_score = compare(field, case_val, prec_val)
        multiplier = 2.0 if is_driver else 1.0

        if is_driver and match_score == 0.0:
            non_transferable = true
            reason: "{field.label}: precedent={prec_val}, current={case_val} — driver contradiction"

        score += field.weight × multiplier × match_score
        total_weight += field.weight × multiplier

    return SimilarityResult(
        score = score / total_weight if total_weight > 0 else 0.0,
        non_transferable = non_transferable,
        non_transferable_reasons = non_transferable_reasons,
        matched_drivers = [...],
        mismatched_drivers = [...],
        matched_context = [...]
    )
```

### 5.5 Non-Transferable Precedents

A precedent is flagged **non-transferable** when a decision driver contradicts the current case or is absent from it. The precedent's reasoning chain does not apply because the inputs that caused its outcome are different.

**Rules:**
- Non-transferable precedents CANNOT be classified as "supporting" regardless of overall similarity score.
- They may be classified as "contrary" if the disposition conflict exists (ALLOW vs BLOCK).
- Otherwise they are excluded from confidence scoring.
- They may appear in the report's Distinguishing Factor Analysis with an explicit explanation of why the outcome does not transfer.
- Non-transferable is a principled mechanism — it replaces arbitrary numeric penalties.

### 5.6 Similarity Floor

```
Default: 0.60

Typology overrides (banking AML):
    sanctions:      0.80
    structuring:    0.65
    adverse_media:  0.55
```

Below the floor → precedent is discarded from the scored pool. "No comparable precedents found" is a valid and honest output. It is better than showing weak matches with misleading confidence metrics.

Discarded precedents may be stored separately for "research mode" display if needed, clearly labeled as below threshold.

---

## 6. Layer 3: Governed Confidence

Confidence is NOT a similarity score. It answers: "Given the precedents found, how reliable is the institutional guidance?"

### 6.1 Four-Dimension Model

```
final_confidence = min(pool_adequacy, similarity_quality, outcome_consistency, evidence_completeness)
```

One weak dimension caps the entire score. This prevents any single strength from masking a fundamental gap.

### 6.2 Pool Adequacy

How many precedents passed Layer 1 gate AND Layer 2 similarity floor.

| Count | Level |
|-------|-------|
| 0 | NONE — "No comparable precedents above similarity threshold" |
| 1–4 | LOW — "Precedent pool below minimum threshold" |
| 5–14 | MODERATE |
| 15–49 | HIGH |
| 50+ | VERY_HIGH |

### 6.3 Similarity Quality

Average similarity score of precedents in the scored pool.

| Average Similarity | Level |
|-------------------|-------|
| < 0.50 | LOW — "No strongly comparable cases found" |
| 0.50–0.69 | MODERATE |
| 0.70–0.84 | HIGH |
| 0.85+ | VERY_HIGH |

### 6.4 Outcome Consistency

Among terminal (decisive) precedents only — those with disposition ALLOW or BLOCK.

```
decisive = pool WHERE disposition IN {ALLOW, BLOCK}

if count(decisive) == 0:
    outcome_consistency = N/A
    note: "No terminal precedents. All comparable cases are non-terminal (EDD/UNKNOWN).
           Confidence scoring requires resolved precedents."
    → caps confidence at MODERATE

else:
    majority = mode(decisive.disposition)
    agreement = count(decisive WHERE disposition == majority) / count(decisive)

    | Agreement | Level |
    |-----------|-------|
    | < 0.60    | LOW   |
    | 0.60–0.79 | MODERATE |
    | 0.80–0.94 | HIGH |
    | 0.95+     | VERY_HIGH |
```

### 6.5 Evidence Completeness

Percentage of required fields present in the current case.

| Completeness | Level |
|-------------|-------|
| < 0.80 | LOW — "X required fields missing" |
| 0.80–0.89 | MODERATE |
| 0.90–0.94 | HIGH |
| 0.95+ | VERY_HIGH |

**Critical field override:** If any field marked `critical: true` in the registry is missing, evidence completeness is capped at LOW regardless of percentage. Critical fields are those whose absence makes any comparison unreliable (e.g., `txn.type`, `txn.amount_band`, `customer.type` in banking AML).

### 6.6 Confidence Resolution

```
levels = [pool_adequacy, similarity_quality, evidence_completeness]

if outcome_consistency != N/A:
    levels.append(outcome_consistency)
else:
    levels.append(MODERATE)  # No terminal precedents caps here

LEVEL_ORDER = [NONE, LOW, MODERATE, HIGH, VERY_HIGH]
final_confidence = min(levels)
```

### 6.7 Hard Rules

These are inviolable. No override, no fallback, no exception.

| Rule | Effect |
|------|--------|
| 0 precedents above floor | Confidence = NONE with explanation |
| All precedents < 50% similarity | Confidence capped at LOW |
| Critical fields missing | Confidence capped at LOW |
| 0 decisive precedents | Confidence capped at MODERATE |
| Pool < 5 | Confidence capped at LOW |
| NEVER show a percentage when formula has no valid inputs | Display "N/A" with explanation |
| NEVER fall back to a hardcoded value | No default 50%, no default "Moderate" |

---

## 7. Precedent Match Classification

Classification uses disposition as the primary axis. Reporting differences inform obligation analysis but do not affect match classification.

### 7.1 Supporting Precedents

```
precedent.disposition == case.disposition
AND NOT non_transferable
```

Reporting differences do not invalidate support. A precedent with disposition EDD and reporting FILE_STR still supports a current EDD disposition — the escalation path is consistent; the reporting obligation is a separate dimension.

### 7.2 Contrary Precedents

Reserved exclusively for terminal disposition conflicts:

```
ALLOW vs. BLOCK
BLOCK vs. ALLOW
```

These are the only true decision contradictions. One institution approved what another blocked under comparable circumstances. Cross-basis comparisons (MANDATORY vs DISCRETIONARY) are excluded — they are not comparable (INV-008).

### 7.3 Neutral Precedents

All other combinations:

```
EDD vs. ALLOW      → Neutral
EDD vs. BLOCK      → Neutral
ANY vs. UNKNOWN    → Neutral
UNKNOWN vs. ANY    → Neutral
Non-transferable   → Neutral (unless ALLOW vs BLOCK conflict)
```

**Regulatory justification:** EDD is a procedural state — "investigation required before final determination." It cannot logically contradict either ALLOW or BLOCK because it has not yet resolved. Treating EDD as contrary artificially deflates confidence and generates misleading deviation alerts.

> **CLASSIFICATION PRINCIPLE:** Only terminal outcomes can contradict. EDD cannot contradict anything — it delays resolution.

---

## 8. Dual Deviation Model

Deviation analysis addresses two distinct regulatory risks: inconsistency (unfairness) and defensibility (failure to report). Each requires its own alert type, threshold, and remediation path.

### 8.1 Disposition Deviation (Consistency Check)

Identifies cases where the current business action diverges from comparable precedent majority.

**Trigger:**

```
case.disposition != majority(comparable_precedents.disposition)
AND comparable_precedents filtered to same disposition_basis
```

**Alert Type:** Consistency Warning

**Example:** "92% of comparable DISCRETIONARY precedents resulted in BLOCK while the current disposition is ALLOW."

**Goal:** Prevent internal unfairness, risk appetite violations, and inconsistent treatment. Compares only within the same basis category.

### 8.2 Reporting Deviation (Defensibility Check)

Identifies cases where the current reporting decision is less severe than historical filing patterns.

**Trigger:**

```
case.reporting severity < majority(comparable_precedents.reporting severity)

Severity: FILE_STR > NO_REPORT, FILE_TPR > NO_REPORT
LCTR gaps are arithmetic errors (threshold-based), handled separately.
```

**Alert Type:** Defensibility Alert

**Example:** "Current proposal to NOT FILE contradicts 90% historical STR filing rate for this typology."

**Goal:** Prevent systemic under-reporting and PCMLTFA s. 73 violations.

> **DEFENSIBILITY NOTE — s. 73 Exposure:** A Defensibility Alert does not create a filing obligation by itself. The determination of reasonable grounds to suspect must still be made by a designated officer. However, a pattern of Defensibility Alerts overridden without documented rationale constitutes a material examination finding (INV-009).

### 8.3 Deviation Summary Matrix

| Deviation Type | Alert Class | Description | Regulatory Basis |
|---------------|-------------|-------------|-----------------|
| **Disposition deviation** | Consistency Warning | Action divergence from comparable precedents | *Risk appetite / fairness* |
| **Reporting deviation (STR/TPR)** | Defensibility Alert | Filing rate below comparable precedent history | *PCMLTFA s. 73 / s. 73.1* |
| **LCTR gap** | Threshold Alert | Missing LCTR where $10,000+ cash received | *PCMLTFA s. 12 (objective)* |
| **Cross-basis comparison** | Informational Only | MANDATORY vs. DISCRETIONARY basis mismatch | *Not scored* |

---

## 9. Gate Inference Rules

```
gate2_str_required = reporting == FILE_STR
```

Gate logic must attach to the explicit regulatory obligation, not to disposition or workflow state. Under PCMLTFA s. 7, the STR obligation arises from a determination of reasonable grounds to suspect — not from the business action taken on the transaction or relationship.

**Removed:** `gate2_str_required = outcome IN {"escalate", "deny"}` — this inferred STR from workflow state, which has no statutory basis.

---

## 10. Precedent Report Output

Every decision's precedent analysis produces five sections. All five sections must render in every report, for every case, regardless of input source.

### 10.1 Section 1: Governed Disposition Alignment

The practical answer for the analyst: "What does the bank usually do?"

Count ALL precedents matching the governed disposition, including non-terminal:

```
Example: "15/15 comparable precedents match the governed disposition
(EDD_REQUIRED). The bank has consistently applied EDD to this case profile."
```

Always show this, even when terminal confidence is N/A. This is the most actionable information for the analyst.

### 10.2 Section 2: Terminal Confidence

The statistical answer: "When the bank made a final decision, how consistent was it?"

Show the four-dimension breakdown and identify the bottleneck:

```
Example: "Terminal confidence: HIGH
Pool: 11 resolved cases (HIGH) · Similarity: avg 68% (MODERATE) ·
Consistency: 8/11 support ALLOW (HIGH) · Evidence: 93% complete (HIGH)
Bottleneck: Similarity quality"
```

When no terminal precedents exist:

```
Example: "Terminal confidence: N/A
No resolved precedents in comparable pool. All 15 comparable cases are
non-terminal (EDD). Institutional guidance is directional only."
```

### 10.3 Section 3: Distinguishing Factor Analysis

For the top 3–5 precedents by similarity, show what matches and what differs, with specific attention to decision drivers:

```
Example: "Precedent 30e4a3 (EDD, 72% similar):
  Matches: channel_family (electronic), cross_border (true), amount_band (100K–500K)
  Differs: flag.unusual_for_profile (false in precedent, true in current)
  Driver impact: unusual_for_profile was NOT a driver in this precedent —
  difference does not affect outcome transferability."
```

For non-transferable precedents, explain why:

```
Example: "Precedent 904634d9 (ALLOW, 80% similar) — NON-TRANSFERABLE:
  screening.adverse_media was the primary driver (false in precedent, true
  in current case). The precedent's ALLOW outcome was predicated on clean
  media screening, which does not apply here."
```

### 10.4 Section 4: Divergence Justification

Only when the engine outcome diverges from precedent majority. Auto-generated from driver comparison between current case and contrary precedents:

```
Example: "Decision diverges from precedent majority. 2 contrary precedents
resulted in ALLOW; current decision is BLOCK. Divergence justified by:
(1) Confirmed adverse media with MLTF link — not present in contrary cases
(2) Cross-border to sanctioned jurisdiction — not present in contrary cases
These factors constitute hard-stop conditions independent of precedent."
```

Must be present on every divergent decision. This is what the compliance officer signs off on.

### 10.5 Section 5: Institutional Posture Statement

The learning tool for new analysts and the governance answer for auditors:

```
Example: "Historical practice: Of 15 comparable cases, 87% cleared after EDD,
13% escalated to STR upon EDD findings. Common escalation trigger: undisclosed
beneficial ownership. Average EDD resolution: 4.2 business days.

Institutional precedent strongly supports EDD as the appropriate disposition
for this case profile."
```

Includes:
- Post-EDD outcome history (% cleared, % escalated, escalation triggers)
- Average resolution time where available
- Clear institutional guidance statement
- Pattern of reporting decisions for this case profile

---

## 11. Domain Portability

### 11.1 Domain Registry Structure

```
DomainRegistry:
    domain:                     str
    version:                    str
    fields:                     list[FieldDefinition]
    comparability_gates:        list[ComparabilityGate]
    similarity_floor:           float
    similarity_floor_overrides: dict[str, float]    # per typology
    confidence_thresholds:      ConfidenceScale
    pool_minimum:               int
    critical_fields:            list[str]
    disposition_mapping:        dict                # raw → canonical
    reporting_mapping:          dict                # raw → canonical
    basis_mapping:              dict                # raw → canonical
```

### 11.2 Adding a New Domain

To add a new domain (e.g., insurance claims, corporate governance):

1. Create a new registry file defining fields, types, weights, tiers, gates, and thresholds.
2. Populate precedent data with three-field canonical outcomes.
3. The comparison engine, confidence calculator, narrator, and validation layer work without code changes — they read the registry.

No engine code changes. The registry is the only domain-specific artifact.

---

## 12. Invariants and Governance Principles

Any code path that violates these invariants constitutes a compliance defect requiring immediate remediation.

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
| **INV-010** | Confidence must never use hardcoded fallback values — every score must be derived from the four-dimension model | *Statistical integrity* |
| **INV-011** | Non-transferable precedents cannot be classified as supporting | *Causal integrity* |
| **INV-012** | Precedents below similarity floor are excluded from all calculations and displays | *Statistical integrity* |
| **INV-013** | All five precedent report sections must render for every case regardless of input source | *Audit completeness* |

---

## 13. Output Validation Layer

A `validate_decision_output()` function runs AFTER every decision is generated, BEFORE the report is rendered. It is impossible to render a report that fails these checks.

| Check | Rule | Auto-Fix |
|-------|------|----------|
| Summary-Signal Consistency | If suspicion_count > 0, summary cannot say "no suspicious activity" | Regenerate summary from findings |
| Confidence-Evidence Consistency | If evidence < 90%, confidence cannot be HIGH | Cap confidence per formula |
| Precedent Quality Gate | If max_similarity < 50%, flag as unreliable | Add warning to output |
| Disposition-Label Consistency | If COMPLIANCE REVIEW REQUIRED, label cannot be PASS | Override label to PENDING_REVIEW |
| Narrative Consistency | Full Rationale must match Decision Summary | Regenerate rationale |
| Truncation Check | Scan all narrative fields for mid-word truncation | Append missing characters |
| Action Button Consistency | Integrity alert → no Approve button | Override action set |
| Invariant Check | Validate INV-001 through INV-013 | Log CRITICAL, attach violations |

---

## 14. Auditor Expectations and Examination Readiness

### 14.1 FINTRAC Examination Considerations

Under PCMLTFA s. 62, FINTRAC has authority to examine a reporting entity's compliance program, including transaction monitoring systems and models underlying decision-making. An examiner reviewing DecisionGraph would assess:

- **Separation of obligations:** Disposition vs. reporting independence.
- **Mandatory vs. discretionary distinction:** Sanctions-compelled actions properly segregated.
- **STR threshold integrity:** STR determinations based on documented RGS, not inferred from disposition.
- **Defensibility of no-file decisions:** Alerts when no-file contradicts historical patterns; overrides documented.
- **Confidence metric validity:** Scores reflect terminal outcome consistency within same basis, not distorted by non-decisive data.
- **Comparability governance:** Equivalence classes are policy-defined, not arbitrary.
- **Audit trail completeness:** Every match includes all three dimensions with full provenance.

### 14.2 OSFI Guideline B-10 Alignment

OSFI Guideline B-10 requires risk-based decision systems to demonstrate consistent, defensible outputs. The three-layer model supports this by ensuring EDD is not conflated with terminal actions, mandatory obligations are distinguished from discretionary, and confidence reflects actual institutional history.

### 14.3 What This Model Prevents

| Finding Category | How v3 Prevents It |
|-----------------|-------------------|
| False confidence (50% fallback) | Four-dimension min() model with no hardcoded values |
| Weak-match high-confidence | Similarity quality dimension caps confidence when matches are weak |
| False STR alignment | Reporting is independent; disposition match does not imply reporting match |
| Spurious deviation alerts | Dual deviation separates action consistency from filing defensibility |
| Confidence distortion | Non-terminal and cross-basis excluded from denominator |
| EDD contradiction errors | EDD always Neutral — cannot deflate confidence |
| Cross-basis false contradictions | MANDATORY vs DISCRETIONARY never compared |
| Non-transferable precedent support | Driver contradictions flagged and excluded from supporting |
| Thin-pool false confidence | Pool < 5 caps at LOW; pool = 0 caps at NONE |
| Missing-evidence false confidence | Critical fields missing caps at LOW |
| Canned narrative contradictions | Validation layer checks summary vs findings before render |
| Report/UI label mismatches | Labels derived deterministically from three-field model |
| Governance inconsistency | 13 invariants with statutory basis, runtime-checked |

---

## Appendix A — FINTRAC Reporting Obligation Reference

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
| **PCMLTFA s. 9.3** | PEP/HIO determination requirements |
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

## Appendix C — Banking AML Field Registry Reference

The banking AML domain registry defines the following field categories. Full field definitions with types, weights, tiers, and comparison functions are maintained in the registry implementation file.

| Category | Fields | Tier |
|----------|--------|------|
| **Customer Profile** | customer.type, customer.relationship_length, customer.pep, customer.high_risk_jurisdiction, customer.high_risk_industry, customer.cash_intensive | STRUCTURAL (type, segment) · BEHAVIORAL (risk indicators) |
| **Transaction** | txn.type, txn.amount_band, txn.cross_border, txn.destination_country_risk, txn.round_amount, txn.just_below_threshold, txn.multiple_same_day, txn.pattern_matches_profile, txn.source_of_funds_clear, txn.stated_purpose | STRUCTURAL (type, channel) · BEHAVIORAL (risk signals) |
| **Flags** | flag.structuring, flag.rapid_movement, flag.layering, flag.unusual_for_profile, flag.third_party, flag.shell_company | BEHAVIORAL (all are potential drivers) |
| **Screening** | screening.sanctions_match, screening.pep_match, screening.adverse_media | BEHAVIORAL (high weight, potential hard-stop drivers) |
| **History** | prior.sars_filed, prior.account_closures | BEHAVIORAL (institutional history) |
| **Optional** | txn.frequency_30d, customer.source_of_wealth, customer.occupation, txn.correspondent_bank, customer.beneficial_owner_known | CONTEXTUAL |

Critical fields (absence caps confidence at LOW): `txn.type`, `txn.amount_band`, `customer.type`.

---

## Appendix D — Deficiency Analysis of Prior Models

### D.1 v1 Model Deficiencies

| Deficiency | Regulatory Impact |
|-----------|-------------------|
| STR inferred from denial | Violation of PCMLTFA s. 7 threshold requirements |
| EDD treated as terminal | Artificial confidence deflation, spurious deviation alerts |
| Unknown mapped to "escalate" | Statistical contamination of confidence denominators |
| Gate logic from workflow state | Over-reporting and under-reporting exposure |
| Single-axis outcomes | Logical contradictions in disposition vs reporting |

### D.2 v2 Model Deficiencies (addressed in v3)

| Deficiency | v3 Fix |
|-----------|--------|
| Flat similarity (all fields equal weight) | Typed comparisons with domain weights and driver awareness |
| No comparability gates | Layer 1 equivalence-class filtering |
| Hardcoded confidence fallbacks (50%) | Four-dimension min() model, no defaults |
| No driver-aware scoring | Asymmetric scoring with non-transferable detection |
| No similarity floor | Configurable floor per typology |
| Weak-pool false confidence | Pool adequacy dimension caps confidence |
| Missing-evidence not reflected | Evidence completeness dimension with critical field override |
| Single confidence number | Four named dimensions with bottleneck identification |
| Incomplete report output | Five mandatory sections for every case |

---

*— End of Specification —*
