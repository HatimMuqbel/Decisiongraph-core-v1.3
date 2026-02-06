# Precedent Scoring Specification

**Version:** v1.1 (evaluable-component normalization)
**Source:** `service/main.py` — `query_similar_precedents()`
**Last updated:** 2026-02-06

---

## Overview

The precedent scoring system finds historically similar AML cases and computes a similarity score for each. Cases above the threshold become **scored matches**; below become **raw overlaps** (shown for analyst context only).

```
Input Case → Extract Reason Codes → Find Overlapping Precedents (raw)
                                          ↓
                                    Hard Filters (Stage A)
                                          ↓
                                    Score Components (Stage B)
                                          ↓
                                    Normalize by Evaluable Weight (Stage C)
                                          ↓
                                    Threshold Check → Scored Matches
                                          ↓
                                    Stratified Sample → Report Display
```

---

## 1. Reason Code Extraction

**Function:** `extract_reason_codes(facts, indicators, obligations)`

Maps case characteristics to `RC-*` codes used in the seed precedent registry.

| Condition | Codes Emitted |
|-----------|--------------|
| `sanctions_result == "MATCH"` | `RC-SCR-SANCTION`, `RC-SCR-OFAC` |
| `adverse_media_mltf == True` | `RC-KYC-ADVERSE-MAJOR` |
| `adverse_media == True` (no MLTF) | `RC-KYC-ADVERSE-MINOR` |
| Any obligation contains "PEP" | `RC-TXN-PEP`, `RC-TXN-PEP-EDD`, `RC-KYC-PEP-APPROVED` |
| Indicator type contains "STRUCTUR" | `RC-TXN-STRUCT`, `RC-TXN-STRUCT-MULTI` |
| Indicator type contains "LAYER" or "RAPID" | `RC-TXN-LAYER`, `RC-TXN-RAPID` |
| Indicator type contains "CRYPTO" or "VIRTUAL" | `RC-TXN-CRYPTO-UNREG`, `RC-TXN-CRYPTO-UNHOSTED` |
| Indicator type contains "UNUSUAL" or "DEVIATION" | `RC-TXN-UNUSUAL`, `RC-TXN-DEVIATION` |
| `fatf_grey` or `high_risk_jurisdiction` | `RC-TXN-FATF-GREY` |
| **No codes emitted** (fallback) | `RC-TXN-NORMAL`, `RC-TXN-PROFILE-MATCH` |

---

## 2. Schema Selection

**Function:** `_select_schema_id_for_codes(reason_codes)`

Selects the fingerprint schema based on the `RC-{FAMILY}-*` prefix:

| Prefix | Schema ID |
|--------|-----------|
| `RC-RPT-*` | `decisiongraph:aml:report:v1` |
| `RC-SCR-*` | `decisiongraph:aml:screening:v1` |
| `RC-KYC-*` | `decisiongraph:aml:kyc:v1` |
| `RC-MON-*` | `decisiongraph:aml:monitoring:v1` |
| Everything else | `decisiongraph:aml:txn:v1` |

---

## 3. Raw Overlap Discovery

**Function:** `PRECEDENT_REGISTRY.find_by_exclusion_codes(codes, namespace_prefix, min_overlap=1)`

Finds all seed precedents that share **at least 1** reason code with the case. Returns `(payload, overlap_count)` tuples sorted by overlap descending.

These are the **raw overlaps** shown in the report (e.g., "310 raw overlaps found").

---

## 4. Stage A — Hard Filters

Before scoring, each raw overlap is passed through hard filters. If any filter fails, the precedent is **skipped entirely** (not scored):

| Filter | Logic | Rationale |
|--------|-------|-----------|
| **Schema mismatch** | `payload.fingerprint_schema_id != schema_id` → skip | Only compare within same case type |
| **Jurisdiction mismatch** | Both have jurisdiction AND `_jurisdiction_weight() != 1.0` → skip | Currently requires exact match (e.g., CA == CA) |
| **Customer type mismatch** | Both have customer type AND they differ → skip | Individual ≠ Corporation |
| **Sanctions asymmetry** | Case has sanctions match but precedent does not → skip | Sanctions cases only comparable to sanctions cases |

### Jurisdiction Weight

```
Same code            → 1.0  (pass hard filter)
Same country prefix  → 0.9  (currently BLOCKED — hard filter rejects != 1.0)
Different country    → 0.85 (currently BLOCKED)
Either is null       → 1.0  (pass)
```

> **Note:** The jurisdiction hard filter currently blocks same-country sub-jurisdictions (e.g., `CA` vs `CA-ON` → 0.9 → filtered). This is intentional for now — only exact jurisdiction matches are compared.

---

## 5. Stage B — Component Scoring

Nine similarity components, each scored 0.0–1.0:

### 5.1 Rules Overlap (weight: 30)

```python
weighted_overlap = sum(_code_weight(code) for code in intersection)
rules_overlap    = weighted_overlap / case_code_weights
```

**Code weights** (by materiality):

| Pattern | Weight |
|---------|--------|
| `SANCTION`, `RC-SCR-*` | 1.00 |
| `RC-RPT-*`, `STR`, `TPR`, `LCTR` | 0.95 |
| `STRUCT` | 0.90 |
| `PEP` | 0.85 |
| `LAYER`, `RAPID`, `ROUNDTRIP` | 0.80 |
| `CRYPTO` | 0.75 |
| `FATF`, `CORRESP` | 0.75 |
| `SAR` | 0.70 |
| `UNUSUAL`, `DEVIATION` | 0.60 |
| Everything else | 0.50 |

### 5.2 Gate Match (weight: 25)

Compares Gate 1 (escalation permitted) and Gate 2 (STR required) between case and precedent:

```
Both gates match   → 1.0
One gate matches   → 0.5
Neither matches    → 0.0
```

Precedent gate values are inferred from outcome:
- `gate1_allowed` = outcome ≠ "deny"
- `gate2_str_required` = outcome ∈ {"escalate", "deny"}

### 5.3 Typology Overlap (weight: 15)

Jaccard similarity of typology tokens extracted from reason codes:

```python
typology_overlap = |case ∩ precedent| / |case ∪ precedent|
```

**Typology token mapping:**

| Code pattern | Token |
|-------------|-------|
| `STRUCT` | `structuring` |
| `LAYER`, `RAPID`, `ROUNDTRIP` | `layering` |
| `CRYPTO` | `crypto` |
| `FATF`, `CORRESP` | `geo_risk` |
| `PEP` | `pep` |
| `SANCTION`, `RC-SCR-*` | `sanctions` |
| `UNUSUAL`, `DEVIATION` | `unusual` |
| `ADVERSE` | `adverse_media` |

### 5.4 Amount Bucket (weight: 10)

```
Exact band match     → 1.0
Adjacent band        → 0.5
Non-adjacent / null  → 0.0
```

**Band order:** `under_3k` → `3k_10k` → `10k_25k` → `25k_50k` → `25k_100k` → `50k_plus` → `100k_500k` → `500k_1m` → `over_1m`

### 5.5 Channel/Method (weight: 7)

```
Exact match           → 1.0
Same channel group    → 0.5
Different / null      → 0.0
```

**Channel groups:** `wire` (any "wire"), `cash`, `crypto`, `ach`, `check`/`cheque`

### 5.6 Corridor Match (weight: 8)

Cross-border or destination risk comparison:

```
case.cross_border == precedent.cross_border  → 1.0
OR case.destination_risk == precedent.destination_risk → 1.0
Otherwise → 0.0
```

### 5.7 PEP Match (weight: 5)

```
Both have PEP data AND values match → 1.0
Both have PEP data AND values differ → 0.0
Either missing → 0.0
```

### 5.8 Customer Profile (weight: 5)

```
customer_type matches + relationship_length matches → 1.0
One matches → 0.5
Neither → 0.0
```

### 5.9 Geo Risk (weight: 5)

```
case.destination_country_risk == precedent.destination_country_risk → 1.0
Otherwise → 0.0
```

---

## 6. Stage C — Evaluable-Component Normalization (v1.1)

**This is the critical change in v1.1.**

Previously, the score was:

```
score = Σ (weight_i × component_i)   for ALL 9 components
```

This penalized cases with sparse facts. A case with only rules + gates data could never exceed 0.55 (= 0.30 + 0.25), failing the 0.60 threshold even with perfect matches.

**v1.1 fix:** Score is normalized by the total weight of **evaluable** components:

```
score = Σ (weight_i × component_i) / Σ weight_i    for EVALUABLE components only
```

### Evaluability Rules

| Component | Evaluable When |
|-----------|---------------|
| `rules_overlap` | **Always** (reason codes always exist) |
| `gate_match` | **Always** (gate values always derived) |
| `typology_overlap` | Either side has typology tokens |
| `amount_bucket` | Both case and precedent have amount band |
| `channel_method` | Both case and precedent have channel |
| `corridor_match` | Both sides have cross_border OR destination_risk |
| `pep_match` | Both sides have PEP data |
| `customer_profile` | Both sides have customer_type OR relationship_length |
| `geo_risk` | Both sides have destination_country_risk |

### Example: Sparse Facts Case

Case has only reason codes + gate values (no amount, channel, PEP, etc.):

| Component | Score | Weight | Evaluable? |
|-----------|-------|--------|-----------|
| rules_overlap | 1.00 | 0.30 | ✅ Yes |
| gate_match | 1.00 | 0.25 | ✅ Yes |
| typology_overlap | 0.00 | 0.15 | ❌ No (no tokens) |
| amount_bucket | 0.00 | 0.10 | ❌ No (no data) |
| channel_method | 0.00 | 0.07 | ❌ No |
| corridor_match | 0.00 | 0.08 | ❌ No |
| pep_match | 0.00 | 0.05 | ❌ No |
| customer_profile | 0.00 | 0.05 | ❌ No |
| geo_risk | 0.00 | 0.05 | ❌ No |

```
evaluable_weight = 0.30 + 0.25 = 0.55
raw_score        = 0.30 × 1.0 + 0.25 × 1.0 = 0.55
similarity_score = 0.55 / 0.55 = 1.00   ← PASSES threshold (≥ 0.60)
```

### Example: Rich Facts Case

Case has all data fields populated:

| Component | Score | Weight | Evaluable? |
|-----------|-------|--------|-----------|
| rules_overlap | 0.80 | 0.30 | ✅ Yes |
| gate_match | 1.00 | 0.25 | ✅ Yes |
| typology_overlap | 0.50 | 0.15 | ✅ Yes |
| amount_bucket | 1.00 | 0.10 | ✅ Yes |
| channel_method | 0.50 | 0.07 | ✅ Yes |
| corridor_match | 1.00 | 0.08 | ✅ Yes |
| pep_match | 1.00 | 0.05 | ✅ Yes |
| customer_profile | 0.50 | 0.05 | ✅ Yes |
| geo_risk | 1.00 | 0.05 | ✅ Yes |

```
evaluable_weight = 1.00
raw_score        = 0.24 + 0.25 + 0.075 + 0.10 + 0.035 + 0.08 + 0.05 + 0.025 + 0.05 = 0.905
similarity_score = 0.905 / 1.00 = 0.905   ← high match
```

---

## 7. Rank-Ordering Modifiers

After the threshold check, the final display score is adjusted by two modifiers that affect **ordering only** (they do NOT affect threshold eligibility):

### Decision Level Weight

| Level | Weight |
|-------|--------|
| Adjuster | 0.90 |
| Manager | 1.00 |
| Tribunal | 1.10 |
| Court | 1.15 |
| Unknown/null | 1.00 |

### Recency Weight

Exponential decay with ~1-year half-life:

```
recency = 0.5 + 0.5 × e^(-age_days / 365)
```

| Age | Weight |
|-----|--------|
| Today | 1.00 |
| 6 months | ~0.80 |
| 1 year | ~0.68 |
| 2 years | ~0.57 |
| 5 years | ~0.51 |

### Combined Score (for ranking + display)

```
combined = similarity_score × decision_weight × recency_weight
```

The `similarity_pct` shown in the report = `round(combined × 100)`.

---

## 8. Thresholds

| Mode | Threshold | Env Var |
|------|-----------|---------|
| **prod** | 0.60 (60%) | `DG_PRECEDENT_THRESHOLD_PROD` |
| **demo** | 0.50 (50%) | `DG_PRECEDENT_THRESHOLD_DEMO` |

Mode is determined by `DG_MODE` env var (default: `prod`).

Matches **above** threshold → scored matches (used for confidence, alignment, deviation).
Matches **below** threshold → shown as "below threshold" with dashed border and label.

---

## 9. Outcome Normalization (v2 — Three-Field Model)

**Function:** `normalize_outcome_v2(raw, reason_codes, case_facts)` — **single source of truth**

> See `docs/PRECEDENT_OUTCOME_MODEL_V2.md` for full specification.

Every outcome is decomposed into three independent dimensions:

| Field | Values |
|-------|--------|
| **disposition** | ALLOW, EDD, BLOCK, UNKNOWN |
| **disposition_basis** | MANDATORY, DISCRETIONARY, UNKNOWN |
| **reporting** | NO_REPORT, FILE_STR, FILE_LCTR, FILE_TPR, UNKNOWN |

### Disposition mapping

| Canonical | Raw inputs |
|-----------|-----------|
| **ALLOW** | pay, paid, approve, approved, accept, accepted, clear, cleared, covered, eligible, pass, passed, no report, close, closed, no action |
| **EDD** | review, investigate, investigation, hold, pending, manual review, needs info, request more info, pass with edd, escalate, escalated |
| **BLOCK** | deny, denied, decline, declined, reject, rejected, block, blocked, refuse, refused, hard stop, exit, de-risk |

Compound outcomes (`report str`, `report lctr`, `report tpr`) → disposition `ALLOW` with explicit reporting.

Default (unknown) → `UNKNOWN` (excluded from scoring — INV-003).

### Report label derivation

| Condition | Display Label |
|-----------|--------------|
| `reporting == FILE_STR` | STR REQUIRED |
| `disposition == BLOCK AND reporting != FILE_STR` | BLOCKED — NO STR |
| `disposition == EDD` | EDD REQUIRED |
| `disposition == ALLOW AND reporting == NO_REPORT` | NO REPORT |
| `disposition == ALLOW AND reporting == FILE_LCTR` | LCTR + ALLOW |
| `disposition == ALLOW AND reporting == FILE_TPR` | TPR + ALLOW |

**Backward compatibility:** `normalize_outcome(raw)` delegates to v2 and maps ALLOW→pay, EDD→escalate, BLOCK→deny.

---

## 10. Precedent Match Classification (v2)

| Case Disposition | Precedent Disposition | Classification | Basis |
|-----------------|----------------------|---------------|-------|
| ALLOW | ALLOW | **Supporting** | Same terminal outcome |
| BLOCK | BLOCK | **Supporting** | Same terminal outcome |
| ALLOW | BLOCK (or vice versa) | **Contrary** | Only true contradiction (INV-004) |
| EDD | Any | **Neutral** | Procedural, not terminal (INV-005) |
| Any | UNKNOWN | **Neutral** | Excluded from scoring (INV-003) |
| Cross-basis | Any | **Neutral** | MANDATORY vs DISCRETIONARY not comparable (INV-008) |

---

## 11. Stratified Sampling

**Function:** `stratified_precedent_sample(matches, proposed_outcome)`

Limits per bucket:
- **Supporting:** max 35
- **Contrary:** max 10
- **Neutral:** max 15
- **Total:** max 50

Sorted by combined score (highest first) for deterministic ordering.

---

## 12. Confidence Score (v2)

```python
# v2: only terminal outcomes (ALLOW/BLOCK) within same disposition_basis
# INV-003: UNKNOWN excluded from denominator
# INV-008: cross-basis excluded from denominator

comparable = [p for p in scored_matches
              if p.disposition in ("ALLOW", "BLOCK")
              and (case_basis == "UNKNOWN" or p.basis == "UNKNOWN"
                   or p.basis == case_basis)]

decisive_total = len(comparable)
decisive_supporting = len([p for p in comparable
                           if p.disposition == case.disposition])

if scored_matches == 0:
    confidence = 0.0
elif decisive_total > 0:
    consistency_rate = decisive_supporting / decisive_total
    upheld_rate = appeal_stats.upheld_rate or 1.0
    confidence = (consistency_rate × 0.7) + (upheld_rate × 0.3)
else:
    confidence = 0.5
```

**Key v2 change:** Only terminal outcomes (ALLOW/BLOCK) count in the denominator. EDD and UNKNOWN are excluded. Cross-basis precedents (MANDATORY vs DISCRETIONARY) are excluded per INV-008.

---

## 13. "Why Low Match" Diagnostics

When matches = 0 or confidence < 0.4, the report shows diagnostic info:

| Category | Trigger |
|----------|---------|
| `missing_features` | Case missing: amount_bucket, channel, corridor, customer_type, relationship_length, pep |
| `gate_mismatch` | Gate 1 or Gate 2 values are null |
| `rule_mismatch` | No reason codes extracted |
| `typology_mismatch` | No typology tokens derived |

---

## 14. Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DG_MODE` | `prod` | `prod` or `demo` — affects threshold |
| `DG_PRECEDENT_THRESHOLD_PROD` | `0.60` | Prod similarity threshold |
| `DG_PRECEDENT_THRESHOLD_DEMO` | `0.50` | Demo similarity threshold |
| `DG_PRECEDENT_MIN_SCORE` | `0.60` | Floor score (unused in current flow) |
| `DG_JURISDICTION` | `CA` | Case jurisdiction for comparison |
| `DG_PRECEDENT_SALT` | `decisiongraph-banking-seed-v1` | Salt for seed generation |

---

## 15. Version History

| Version | Date | Change |
|---------|------|--------|
| v1 | 2026-01 | Initial 9-component weighted scoring |
| v1.1 | 2026-02-06 | Evaluable-component normalization — missing data no longer penalizes score; score = raw / evaluable_weight |
