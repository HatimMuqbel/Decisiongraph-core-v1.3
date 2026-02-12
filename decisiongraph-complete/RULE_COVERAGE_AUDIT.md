# Rule Coverage Audit — DecisionGraph v1.3

**Date:** 2026-02-12
**Classifier Version:** SuspicionClassifier v1
**Engine Version:** DecisionGraph v3 Precedent Engine

---

## 1. Classifier Rule Inventory

### Tier 1 — Suspicion Indicators (STR-Capable)

Any single Tier 1 signal meets the Reasonable Grounds to Suspect (RGS) threshold
under PCMLTFA/FINTRAC guidance. STR filing required unless verified mitigation applies.

| Code | Source | Trigger Condition | FINTRAC Typology |
|------|--------|-------------------|------------------|
| STRUCTURING_PATTERN | evidence/typology/rule | `flag.structuring_suspected`, `flag.structuring`, or structuring typology | Structuring/Smurfing |
| LAYERING | evidence/typology | `flag.layering` or layering typology | Layering |
| EVASION_BEHAVIOR | evidence/suspicion | `flag.rapid_movement`, `flag.unusual_for_profile`, or evasion element | Professional ML |
| FUNNEL | typology | Funnel account typology | Layering |
| THIRD_PARTY_UNEXPLAINED | evidence/rule | `flag.third_party_unexplained`, `flag.third_party` | Professional ML |
| FALSE_SOURCE | evidence/suspicion | `flag.false_source` | Professional ML |
| SANCTIONS_SIGNAL | evidence/rule | `screening.sanctions_match`, `flag.sanctions_proximity`, sanctions rule | Sanctions |
| ADVERSE_MEDIA_CONFIRMED | evidence/suspicion | `screening.adverse_media_level` = "confirmed" | Corruption/PEP |
| ADVERSE_MEDIA_MLTF | evidence | `screening.adverse_media_level` = "confirmed_mltf" | Corruption/PEP |
| SHELL_ENTITY | evidence/typology | `flag.shell_entity`, `flag.shell_company`, shell typology | Layering |
| SAR_PATTERN | evidence | `flag.sar_pattern` | (Cross-typology) |
| TERRORIST_FINANCING | typology/suspicion | Terrorist financing typology or suspicion element | TF |
| TRADE_BASED_LAUNDERING | composite | Both `trade.goods_description` in (vague, missing) AND `trade.pricing_consistent` = False | TBML |
| VIRTUAL_ASSET_LAUNDERING | typology/rule | Virtual asset typology or crypto rule | Virtual Asset ML |
| ROUND_TRIP | rule | Round-trip rule triggered | Layering |
| PEP_ANOMALY | composite | PEP flag = True AND any other Tier 1 signal present | Corruption/PEP |
| COMBO_HIGH_RISK_MULTI_FLAG | composite | 3+ red flags AND prior issues (SARs filed or account closures) | (Cross-typology) |

**Red flags tracked for combinatorial rules:**
`flag.structuring`, `flag.layering`, `flag.rapid_movement`, `flag.shell_company`,
`flag.third_party`, `flag.unusual_for_profile`

### Tier 2 — Investigative Signals (EDD Only)

Tier 2 signals do NOT justify STR alone. They require Enhanced Due Diligence.

| Code | Source | Trigger Condition | Notes |
|------|--------|-------------------|-------|
| CROSS_BORDER | evidence/facts | `flag.cross_border` or `txn.cross_border` | Contextual |
| PEP_EXPOSURE | facts | `customer.pep_flag` = True (without Tier 1 co-signal) | Standalone PEP |
| CRYPTO | evidence/facts | `flag.crypto` or crypto payment method | Contextual |
| HIGH_VALUE | evidence | `txn.amount_band` in (100k_500k, 500k_1m, over_1m) | Threshold: 100K+ only |
| NEW_ACCOUNT | evidence | `flag.new_account` | Contextual |
| CASH_INTENSIVE | evidence | `flag.cash_intensive` | Contextual |
| DORMANT_REACTIVATED | evidence | `flag.dormant_reactivated` | Contextual |
| ENTITY_TYPE | evidence | `customer.type` (corporate entities) | Contextual |
| HIGH_RISK_COUNTRY | facts | Destination matches FATF high-risk list | Contextual |
| ADVERSE_MEDIA_UNCONFIRMED | evidence | `screening.adverse_media_level` = "unconfirmed" | Must-investigate |
| TRADE_FINANCE_SUSPICIOUS | composite | Either `trade.goods_description` in (vague, missing) OR `trade.pricing_consistent` = False (not both) | Must-investigate |
| COMBO_MODERATE_MULTI_FLAG | composite | 2+ red flags AND `flag.unusual_for_profile` active | Must-investigate |
| UNCLASSIFIED_* | suspicion element | Unmapped suspicion element (requires manual review) | Safety net |

### Must-Investigate Tier 2 Signals

These Tier 2 signals force EDD even when the engine verdict is PASS:

| Code | Rationale |
|------|-----------|
| ADVERSE_MEDIA_UNCONFIRMED | News article mentions investigation — cannot clear without verification |
| TRADE_FINANCE_SUSPICIOUS | Single TBML indicator requires trade documentation review |
| COMBO_MODERATE_MULTI_FLAG | Multiple red flags with unusual profile warrant investigation |

### Mitigation (Safety Valve)

Verified mitigations can downgrade all Tier 1 signals to Tier 2:
- `source_of_funds_confirmed`
- `legitimate_business_purpose`
- `regulatory_exemption`
- `compliance_officer_override`

---

## 2. Gate Architecture

### Gate 1: Zero-False-Escalation Gate (7 Sections)

| Section | Name | Purpose |
|---------|------|---------|
| A | Fact-Level Hard Stop Verification | Sanctions match, false docs, refusal to provide info |
| B | Instrument & Context Validation | Payment method, channel, amount thresholds |
| C | Regulatory Obligation Isolation | Mandatory reporting obligations (LCTR, EFT, etc.) |
| D | Indicator Corroboration Test | Multiple independent indicators required |
| E | Typology Maturity Gate | CONFIRMED/EMERGING/SPECULATIVE classification |
| F | Mitigation Override Test | Whether mitigations reduce risk sufficiently |
| G | Suspicion Definition Test (Final Gate) | `has_intent` behavioral check — key behavioral gate |

**Gate 1 rule:** ALL sections must pass for escalation to be PERMITTED.
Any single section failure = PROHIBITED.

### Gate 2: Positive STR Gate

| Decision | Condition |
|----------|-----------|
| REQUIRED | Behavioral suspicion + evidence quality + typology confirmed |
| PROHIBITED | Evidence quality insufficient for STR |
| INSUFFICIENT | Analyst review required |

### Dual-Gate Decision Flow

| Gate 1 | Gate 2 | Final Decision |
|--------|--------|----------------|
| PROHIBITED | (any) | PASS (with EDD recorded) |
| PERMITTED | REQUIRED | STR |
| PERMITTED | PROHIBITED | PASS (enhanced monitoring) |
| PERMITTED | INSUFFICIENT | REVIEW (analyst required) |

### Classifier Sovereignty Overrides

| Priority | Condition | Action |
|----------|-----------|--------|
| 1 | Tier 1 = 0, engine says STR | Block STR → EDD or NO_REPORT |
| 2 | Tier 1 = 0, escalation PERMITTED, no STR | Downgrade to EDD |
| 3 | Tier 1 = 0, engine PASS, must-investigate T2 | Upgrade PASS → EDD |

---

## 3. FINTRAC ML/TF Typology Coverage

### Coverage Matrix

| # | Typology | Tier 1 Codes | Tier 2 Codes | Seeds | Demo Cases | Coverage |
|---|----------|-------------|-------------|-------|------------|----------|
| 1 | **Structuring/Smurfing** | STRUCTURING_PATTERN | HIGH_VALUE, CASH_INTENSIVE | Yes (3 scenarios) | structuring-pattern, structuring-three-deposits, cash-intensive-lctr | FULL |
| 2 | **Layering** | LAYERING, SHELL_ENTITY, FUNNEL, ROUND_TRIP | CROSS_BORDER | Yes (3 scenarios) | shell-company-layering, velocity-spike | FULL |
| 3 | **Trade-Based ML** | TRADE_BASED_LAUNDERING | TRADE_FINANCE_SUSPICIOUS | Yes (2 scenarios) | trade-finance-unusual-docs | FULL |
| 4 | **Corruption/PEP** | PEP_ANOMALY, ADVERSE_MEDIA_CONFIRMED, ADVERSE_MEDIA_MLTF | PEP_EXPOSURE, ADVERSE_MEDIA_UNCONFIRMED | Yes (2 scenarios) | pep-legal-fees, pep-plus-adverse-media, domestic-pep-routine, beneficial-owner-pep, pep-foreign-large-wire-clean, adverse-media-unconfirmed | FULL |
| 5 | **Terrorist Financing** | TERRORIST_FINANCING, SANCTIONS_SIGNAL | HIGH_RISK_COUNTRY | Yes (1 scenario) | sanctions-hit, sanctions-exact-match | CODE + SEEDS |
| 6 | **Professional ML** | EVASION_BEHAVIOR, THIRD_PARTY_UNEXPLAINED, FALSE_SOURCE | DORMANT_REACTIVATED | Yes (3 scenarios) | multiple-flags-commercial-exit, dormant-account-reactivation | FULL |
| 7 | **Virtual Asset ML** | VIRTUAL_ASSET_LAUNDERING | CRYPTO | Yes (1 scenario) | crypto-high-risk-corridor | FULL |

### Cross-Typology Rules

| Code | Applies To | Description |
|------|-----------|-------------|
| COMBO_HIGH_RISK_MULTI_FLAG | All | 3+ flags from any typology + prior issues → Tier 1 |
| COMBO_MODERATE_MULTI_FLAG | All | 2+ flags + unusual profile → Tier 2 (must-investigate) |
| SAR_PATTERN | All | Prior SAR pattern detected |

### Coverage Summary

| Status | Count | Typologies |
|--------|-------|-----------|
| FULL | 6 | Structuring, Layering, TBML, Corruption/PEP, Professional ML, Virtual Asset ML |
| CODE + SEEDS | 1 | Terrorist Financing (no dedicated TF demo case — covered by sanctions cases) |

### Remaining Gaps

| Gap | Severity | Description |
|-----|----------|-------------|
| Real Estate ML | LOW | No dedicated real estate laundering rules. Partially covered by structuring + layering rules when applied to real estate transactions. Consider adding `property.purchase_price` and `property.financing_source` fields in future version. |
| TF Demo Case | LOW | Terrorist financing has code + seeds but no dedicated demo case. Sanctions cases (sanctions-hit, sanctions-exact-match) exercise the TF pathway indirectly. |
| PEP PASS Cases | INFORMATIONAL | pep-legal-fees and domestic-pep-routine expect PASS but produce EDD_REQUIRED. PEP triggers escalation PERMITTED → classifier sovereignty downgrades to EDD (correct behavior — PEP always warrants investigation). Demo case `expected_outcome` field could be updated. |

---

## 4. Reason Code Mapping

| Reason Code | Trigger | Typology |
|-------------|---------|----------|
| RC-TXN-STRUCT | Structuring flag or rule | Structuring |
| RC-TXN-STRUCT-MULTI | Structuring flag or rule | Structuring |
| RC-TXN-PEP | PEP flag or rule | Corruption/PEP |
| RC-TXN-PEP-EDD | PEP flag or rule | Corruption/PEP |
| RC-SCR-SANCTION | Sanctions match | Sanctions/TF |
| RC-SCR-OFAC | Sanctions match | Sanctions/TF |
| RC-TXN-FATF-GREY | High-risk jurisdiction | Cross-typology |
| RC-TXN-LAYER | Layering indicators | Layering |
| RC-TXN-RAPID | Rapid movement | Professional ML |
| RC-TXN-UNUSUAL | Unusual for profile | Professional ML |
| RC-TXN-TBML | Both trade indicators | TBML |
| RC-TXN-TRADE-SUSPICIOUS | Single trade indicator | TBML |
| RC-KYC-ADVERSE-MAJOR | Confirmed adverse media | Corruption/PEP |
| RC-KYC-ADVERSE-MINOR | Unconfirmed adverse media | Corruption/PEP |
| RC-TXN-NORMAL | No risk indicators | (Clean) |
| RC-TXN-PROFILE-MATCH | No risk indicators | (Clean) |

---

## 5. Changes in This Release

### New Rules Added

| Rule | Tier | Gap | Description |
|------|------|-----|-------------|
| ADVERSE_MEDIA_MLTF | T1 | Gap 1 | Confirmed ML/TF-linked adverse media → STR |
| ADVERSE_MEDIA_CONFIRMED | T1 | Gap 1 | Confirmed adverse media (charges/action) → STR |
| ADVERSE_MEDIA_UNCONFIRMED | T2 | Gap 1 | Unconfirmed adverse media → EDD (must-investigate) |
| COMBO_HIGH_RISK_MULTI_FLAG | T1 | Gap 2 | 3+ red flags + prior issues → STR |
| COMBO_MODERATE_MULTI_FLAG | T2 | Gap 2 | 2+ flags + unusual profile → EDD (must-investigate) |
| TRADE_BASED_LAUNDERING | T1 | Gap 3 | Both TBML indicators → STR |
| TRADE_FINANCE_SUSPICIOUS | T2 | Gap 3 | Single TBML indicator → EDD (must-investigate) |

### Fields Added

| Field | Type | Comparison | Gap |
|-------|------|------------|-----|
| screening.adverse_media_level | enum (none/unconfirmed/confirmed/confirmed_mltf) | ORDINAL, STEP | Gap 1 |
| trade.goods_description | enum (detailed/adequate/vague/missing) | ORDINAL, STEP | Gap 3 |
| trade.pricing_consistent | boolean | EXACT | Gap 3 |
| trade.is_letter_of_credit | boolean | EXACT | Gap 3 |

### Classifier Tuning (Gap 4)

| Change | Before | After |
|--------|--------|-------|
| HIGH_VALUE threshold | All amount bands trigger Tier 2 | Only 100K+ bands trigger Tier 2 |
| Must-investigate enforcement | Engine PASS not overridden for must-investigate T2 | PASS → EDD when must-investigate T2 signals present |

### Seed Scenarios Added

| Scenario | Outcome | Gap |
|----------|---------|-----|
| trade_based_ml | BLOCK | Gap 3 |
| trade_finance_clean | ALLOW | Gap 3 |

**Total scenarios:** 28 (generating ~1,500 seeds)
