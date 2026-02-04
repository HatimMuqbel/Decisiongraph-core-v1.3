# Banking/AML Seed Precedents Specification

## Overview

Generate 3,000 seed precedents for DecisionGraph Banking/AML — full enterprise coverage for:
- Transaction monitoring
- KYC onboarding
- Reporting decisions
- Sanctions/screening
- Ongoing monitoring

---

## Volume Summary

| Category | Precedents |
|----------|------------|
| Transaction Monitoring | 1,050 |
| KYC Onboarding | 675 |
| Reporting | 300 |
| Sanctions/Screening | 525 |
| Ongoing Monitoring | 450 |
| **Total** | **3,000** |

---

## Combined Totals (Insurance + Banking)

| Product | Precedents |
|---------|------------|
| ClaimPilot (Insurance) | 2,150 |
| DecisionGraph (Banking) | 3,000 |
| **Grand Total** | **5,150** |

---

## Distribution Pattern

| Appeal Status | % |
|---------------|---|
| Not appealed | 82% |
| Appealed - upheld | 12% |
| Appealed - overturned | 4% |
| Appealed - settled | 2% |

| Decision Level | % |
|----------------|---|
| Analyst | 45% |
| Senior Analyst | 25% |
| Manager | 15% |
| Compliance Officer | 10% |
| MLRO/BSA Officer | 3% |
| Regulator Review | 2% |

---

## Expansion Addendum (v3,000)

The tables below reflect the original v2,000 baseline. The following scenarios were added to reach 3,000 total precedents while preserving AML audit balance and decision weighting.

### Additional Scenarios (Delta +1,000)

**Transaction Monitoring (+350)**
- TXN-CORRESP — Correspondent Banking Risk (80)
- TXN-ROUNDTRIP — Round‑Trip Transactions (60)
- TXN-CRYPTO-MIX — Crypto Mixer Indicators (60)
- TXN-SAR-HIST — Prior SAR History (50)
- TXN-PRIOR-CLOSURE — Prior Account Closure (50)
- TXN-PEP-RCA — PEP Related Party (50)

**KYC Onboarding (+225)**
- KYC-ID-EXPIRED — Expired/Missing ID (60)
- KYC-SOW-PENDING — Source of Wealth Pending (50)
- KYC-APPETITE — Outside Risk Appetite (40)
- KYC-PEP-DECLINE — PEP Declined (35)
- KYC-SAR-HIST — Prior SAR History (40)

**Reporting (+100)**
- RPT-STR-LAYER — STR Layering (50)
- RPT-STR-3RD — STR Third‑Party (30)
- RPT-APPROVE — Approve with Reporting (20)

**Sanctions/Screening (+175)**
- SCR-ALIAS — Alias/Partial Match (70)
- SCR-ADVERSE — Adverse Media Screening (55)
- SCR-CLEAR — Cleared After Review (50)

**Ongoing Monitoring (+150)**
- MON-NEW-JURIS — New Jurisdiction Activity (50)
- MON-REVIEW-DOWN — Review Downgrade (40)
- MON-KYC-REFRESH — KYC Refresh Needed (40)
- MON-EXIT-REG — Exit Regulatory (20)

These additions expand coverage for correspondent banking, round‑trip flows, crypto mixing, prior SAR history, enhanced KYC deficiencies, AML reporting nuances, alias screening, and monitoring escalation triggers.

---

## 1. Transaction Monitoring — 700 Precedents

### Scenarios

| Scenario | Code | Count | Appealed | Overturned |
|----------|------|-------|----------|------------|
| **Normal Approvals** | | 200 | 8 | 0 |
| └─ Domestic wire | TXN-WIRE-DOM | 50 | 2 | 0 |
| └─ International wire | TXN-WIRE-INT | 40 | 2 | 0 |
| └─ ACH transfer | TXN-ACH | 40 | 1 | 0 |
| └─ Check deposit | TXN-CHECK | 35 | 2 | 0 |
| └─ Cash deposit (under threshold) | TXN-CASH-LOW | 35 | 1 | 0 |
| **Structuring** | | 120 | 24 | 3 |
| └─ Just below $10K | TXN-STRUCT-10K | 50 | 10 | 1 |
| └─ Multiple same-day | TXN-STRUCT-MULTI | 40 | 8 | 1 |
| └─ Round amounts pattern | TXN-STRUCT-ROUND | 30 | 6 | 1 |
| **High-Risk Jurisdiction** | | 100 | 18 | 2 |
| └─ FATF blacklist | TXN-FATF-BLACK | 30 | 5 | 0 |
| └─ FATF greylist | TXN-FATF-GREY | 35 | 7 | 1 |
| └─ Correspondent banking | TXN-CORRESP | 35 | 6 | 1 |
| **PEP Transactions** | | 80 | 16 | 2 |
| └─ Domestic PEP | TXN-PEP-DOM | 30 | 5 | 1 |
| └─ Foreign PEP | TXN-PEP-FOR | 30 | 7 | 1 |
| └─ PEP family/associate | TXN-PEP-RCA | 20 | 4 | 0 |
| **Crypto/Virtual Currency** | | 70 | 14 | 2 |
| └─ Exchange transfer | TXN-CRYPTO-EX | 25 | 5 | 1 |
| └─ P2P/unhosted wallet | TXN-CRYPTO-P2P | 20 | 4 | 1 |
| └─ Mixer/tumbler indicators | TXN-CRYPTO-MIX | 15 | 3 | 0 |
| └─ NFT high value | TXN-CRYPTO-NFT | 10 | 2 | 0 |
| **Layering/Movement** | | 60 | 10 | 1 |
| └─ Rapid in-out | TXN-LAYER-RAPID | 25 | 4 | 0 |
| └─ Multiple jurisdictions | TXN-LAYER-MULTI | 20 | 4 | 1 |
| └─ Round-trip | TXN-LAYER-ROUND | 15 | 2 | 0 |
| **Unusual Patterns** | | 40 | 8 | 1 |
| └─ Deviation from profile | TXN-UNUSUAL-DEV | 20 | 4 | 1 |
| └─ Inconsistent with stated purpose | TXN-UNUSUAL-PURP | 20 | 4 | 0 |
| **Trade-Based ML** | | 30 | 6 | 1 |
| └─ Over/under invoicing | TXN-TRADE-INV | 15 | 3 | 1 |
| └─ Phantom shipments | TXN-TRADE-PHANTOM | 15 | 3 | 0 |
| **Total** | | **700** | **104** | **12** |

### Fingerprint Schema

```yaml
schema_id: decisiongraph:aml:txn:v1
fields:
  # Transaction details
  - txn.type                    # wire_domestic, wire_international, ach, cash, check, crypto
  - txn.amount_band
  - txn.cross_border
  - txn.destination_country_risk
  - txn.originator_country_risk
  - txn.round_amount
  - txn.just_below_threshold
  - txn.multiple_same_day
  - txn.rapid_movement          # in-out within 24-72 hours
  - txn.pattern_matches_profile
  - txn.third_party_involved
  
  # Customer context
  - customer.type               # individual, corporate, trust, msbv
  - customer.risk_level
  - customer.pep
  - customer.pep_type           # domestic, foreign, rca
  - customer.high_risk_industry
  - customer.relationship_length
  
  # Crypto specific
  - crypto.exchange_regulated
  - crypto.wallet_type          # hosted, unhosted
  - crypto.mixer_indicators
  
  # Screening
  - screening.sanctions_match
  - screening.adverse_media

banding_rules:
  txn.amount:
    0-2999: "under_3k"
    3000-9999: "3k_10k"
    9000-9999: "just_below_10k"
    10000-24999: "10k_25k"
    25000-99999: "25k_100k"
    100000-499999: "100k_500k"
    500000-999999: "500k_1m"
    1000000+: "over_1m"
  
  customer.relationship_months:
    0-3: "new"
    4-12: "recent"
    13-36: "established"
    37+: "long_term"
  
  txn.hours_in_account:
    0-24: "immediate"
    25-72: "rapid"
    73-168: "short"
    169+: "normal"
```

### Reason Codes

```yaml
registry_id: decisiongraph:aml:txn:v1

codes:
  # Approvals
  RC-TXN-NORMAL:
    name: "Normal Transaction"
    description: "Transaction consistent with customer profile and risk level"
    
  RC-TXN-VERIFIED:
    name: "Source Verified"
    description: "Source of funds verified and documented"
    
  RC-TXN-PROFILE-MATCH:
    name: "Profile Consistent"
    description: "Activity matches expected customer behavior"
  
  # Structuring
  RC-TXN-STRUCT:
    name: "Structuring Indicators"
    description: "Pattern suggests intentional threshold avoidance"
    regulation_ref: "PCMLTFA Guidelines 3.1"
    red_flags: ["just_below_threshold", "multiple_same_day", "round_amounts"]
    
  RC-TXN-STRUCT-MULTI:
    name: "Multiple Transaction Structuring"
    description: "Multiple transactions same day avoiding threshold"
    regulation_ref: "FINTRAC Guidance FIN-2023-G01"
    
  # High-risk jurisdiction
  RC-TXN-FATF-BLACK:
    name: "FATF Blacklist Country"
    description: "Transaction involves FATF high-risk jurisdiction"
    regulation_ref: "PCMLTFA Guidelines 4.2"
    
  RC-TXN-FATF-GREY:
    name: "FATF Greylist Country"
    description: "Transaction involves FATF increased monitoring jurisdiction"
    regulation_ref: "PCMLTFA Guidelines 4.2"
    
  RC-TXN-CORRESP:
    name: "Correspondent Banking Risk"
    description: "Transaction through high-risk correspondent relationship"
    regulation_ref: "PCMLTFA Section 9.4"
    
  # PEP
  RC-TXN-PEP:
    name: "PEP Transaction"
    description: "Transaction by Politically Exposed Person"
    regulation_ref: "PCMLTFA Section 9.6"
    
  RC-TXN-PEP-EDD:
    name: "PEP - EDD Complete"
    description: "PEP transaction with completed enhanced due diligence"
    
  RC-TXN-PEP-RCA:
    name: "PEP Related Party"
    description: "Transaction by PEP family member or close associate"
    regulation_ref: "PCMLTFA Section 9.6(3)"
    
  # Crypto
  RC-TXN-CRYPTO-UNREG:
    name: "Unregulated Crypto Exchange"
    description: "Funds from/to unregulated virtual currency exchange"
    regulation_ref: "PCMLTFA Part 1.1"
    
  RC-TXN-CRYPTO-UNHOSTED:
    name: "Unhosted Wallet"
    description: "Transaction involves unhosted/private wallet"
    
  RC-TXN-CRYPTO-MIX:
    name: "Mixer/Tumbler Indicators"
    description: "Transaction shows signs of mixing service usage"
    
  # Layering
  RC-TXN-LAYER:
    name: "Layering Indicators"
    description: "Pattern suggests layering to obscure origin"
    red_flags: ["rapid_movement", "multiple_jurisdictions", "no_business_purpose"]
    
  RC-TXN-RAPID:
    name: "Rapid Movement"
    description: "Funds moved through account within 24-72 hours"
    
  RC-TXN-ROUNDTRIP:
    name: "Round-Trip Transaction"
    description: "Funds returned to origin with no apparent purpose"
    
  # Unusual
  RC-TXN-UNUSUAL:
    name: "Unusual Pattern"
    description: "Activity inconsistent with stated purpose or profile"
    
  RC-TXN-DEVIATION:
    name: "Profile Deviation"
    description: "Significant deviation from established transaction pattern"
    
  # Trade-based
  RC-TXN-TRADE-ML:
    name: "Trade-Based ML Indicators"
    description: "Transaction shows trade-based money laundering patterns"
    red_flags: ["over_invoicing", "under_invoicing", "phantom_shipment"]
    
  # Blocks
  RC-TXN-SANCTION:
    name: "Sanctions Match"
    description: "Party matches sanctioned entity"
    regulation_ref: "SEMA, UN Act, JMLSG"
    
  RC-TXN-BLOCK-RISK:
    name: "Unacceptable Risk"
    description: "Transaction risk exceeds acceptable threshold"
```

---

## 2. KYC Onboarding — 450 Precedents

### Scenarios

| Scenario | Code | Count | Appealed | Overturned |
|----------|------|-------|----------|------------|
| **Standard Approvals** | | 150 | 6 | 0 |
| └─ Individual - low risk | KYC-IND-LOW | 60 | 2 | 0 |
| └─ Individual - medium risk | KYC-IND-MED | 40 | 2 | 0 |
| └─ Corporate - standard | KYC-CORP-STD | 30 | 1 | 0 |
| └─ Trust - simple | KYC-TRUST-SIM | 20 | 1 | 0 |
| **PEP Handling** | | 80 | 16 | 2 |
| └─ Domestic PEP - approved | KYC-PEP-DOM-APP | 25 | 4 | 1 |
| └─ Foreign PEP - approved | KYC-PEP-FOR-APP | 20 | 5 | 1 |
| └─ PEP - hold for EDD | KYC-PEP-HOLD | 20 | 4 | 0 |
| └─ PEP - declined | KYC-PEP-DEC | 15 | 3 | 0 |
| **High-Risk Industry** | | 70 | 14 | 2 |
| └─ Money service business | KYC-MSB | 20 | 4 | 1 |
| └─ Crypto/virtual asset | KYC-CRYPTO | 15 | 4 | 1 |
| └─ Gaming/casino | KYC-GAMING | 15 | 3 | 0 |
| └─ Real estate | KYC-REALESTATE | 10 | 2 | 0 |
| └─ Precious metals | KYC-PRECIOUS | 10 | 1 | 0 |
| **Missing Documentation** | | 50 | 10 | 2 |
| └─ Missing ID | KYC-MISS-ID | 20 | 4 | 1 |
| └─ Missing address proof | KYC-MISS-ADDR | 15 | 3 | 1 |
| └─ Missing beneficial owner | KYC-MISS-BO | 15 | 3 | 0 |
| **Adverse Media** | | 50 | 12 | 3 |
| └─ Minor - approved | KYC-ADV-MINOR | 15 | 3 | 1 |
| └─ Moderate - conditional | KYC-ADV-MOD | 15 | 4 | 1 |
| └─ Severe - declined | KYC-ADV-SEV | 20 | 5 | 1 |
| **Shell Company Indicators** | | 30 | 8 | 2 |
| └─ Nominee directors | KYC-SHELL-NOM | 12 | 3 | 1 |
| └─ Registered agent only | KYC-SHELL-RA | 10 | 3 | 1 |
| └─ No physical presence | KYC-SHELL-VIRT | 8 | 2 | 0 |
| **Sanctions Decline** | | 20 | 2 | 0 |
| └─ Direct match | KYC-SANC-DIR | 15 | 1 | 0 |
| └─ Ownership >50% | KYC-SANC-OWN | 5 | 1 | 0 |
| **Total** | | **450** | **68** | **11** |

### Fingerprint Schema

```yaml
schema_id: decisiongraph:aml:kyc:v1
fields:
  # Customer type
  - customer.type               # individual, sole_prop, corporation, partnership, trust, non_profit
  - customer.risk_level         # low, medium, high, prohibited
  - customer.jurisdiction
  - customer.tax_residency
  
  # PEP status
  - customer.pep
  - customer.pep_type           # domestic, foreign, international_org
  - customer.pep_level          # head_of_state, senior_official, judge, military, soe_executive
  - customer.rca                # related/close associate
  
  # Industry
  - customer.high_risk_industry
  - customer.industry_type      # msb, crypto, gaming, real_estate, precious_metals, arms, adult
  - customer.cash_intensive
  
  # KYC status
  - kyc.id_verified
  - kyc.id_type                 # passport, drivers_license, national_id, other
  - kyc.id_expired
  - kyc.address_verified
  - kyc.address_proof_type
  
  # Corporate specific
  - kyc.beneficial_owners_identified
  - kyc.ubo_over_25_pct
  - kyc.source_of_wealth_documented
  - kyc.source_of_funds_documented
  - kyc.business_activity_verified
  
  # Shell indicators
  - shell.nominee_directors
  - shell.registered_agent_only
  - shell.no_physical_presence
  - shell.complex_structure
  
  # EDD
  - edd.required
  - edd.complete
  - edd.senior_approval
  
  # Screening
  - screening.sanctions_match
  - screening.pep_match
  - screening.adverse_media
  - screening.adverse_media_severity

banding_rules:
  screening.adverse_media_age_years:
    0-2: "recent"
    3-5: "moderate"
    6+: "old"
```

### Reason Codes

```yaml
registry_id: decisiongraph:aml:kyc:v1

codes:
  # Approvals
  RC-KYC-COMPLETE:
    name: "KYC Complete"
    description: "All KYC requirements satisfied"
    
  RC-KYC-LOW-RISK:
    name: "Low Risk Customer"
    description: "Customer meets low-risk criteria"
    
  RC-KYC-EDD-COMPLETE:
    name: "EDD Complete"
    description: "Enhanced due diligence satisfactorily completed"
    
  RC-KYC-SENIOR-APPROVED:
    name: "Senior Management Approval"
    description: "High-risk relationship approved by senior management"
    regulation_ref: "PCMLTFA Section 9.6(4)"
    
  # Holds
  RC-KYC-PENDING-EDD:
    name: "Pending EDD"
    description: "Enhanced due diligence required before approval"
    regulation_ref: "PCMLTFA Section 9.6"
    
  RC-KYC-PENDING-ID:
    name: "Pending ID Verification"
    description: "Identity verification incomplete"
    
  RC-KYC-PENDING-BO:
    name: "Pending Beneficial Owner"
    description: "Beneficial ownership verification incomplete"
    regulation_ref: "PCMLTFA Section 11.1"
    
  RC-KYC-PENDING-SOW:
    name: "Pending Source of Wealth"
    description: "Source of wealth documentation required"
    
  # PEP specific
  RC-KYC-PEP-APPROVED:
    name: "PEP Approved"
    description: "PEP relationship approved with controls"
    
  RC-KYC-PEP-DECLINED:
    name: "PEP Declined"
    description: "PEP relationship outside risk appetite"
    
  # High-risk industry
  RC-KYC-MSB:
    name: "Money Service Business"
    description: "MSB requiring enhanced controls"
    regulation_ref: "PCMLTFA Section 5"
    
  RC-KYC-CRYPTO-VASP:
    name: "Virtual Asset Service Provider"
    description: "Crypto business requiring enhanced controls"
    regulation_ref: "PCMLTFA Part 1.1"
    
  # Shell company
  RC-KYC-SHELL:
    name: "Shell Company Indicators"
    description: "Entity shows shell company characteristics"
    red_flags: ["nominee_directors", "registered_agent_only", "no_physical_presence"]
    
  # Adverse media
  RC-KYC-ADVERSE-MINOR:
    name: "Minor Adverse Media"
    description: "Adverse media - low severity, mitigated"
    
  RC-KYC-ADVERSE-MAJOR:
    name: "Major Adverse Media"
    description: "Significant adverse media requiring decline"
    
  # Declines
  RC-KYC-MISSING-ID:
    name: "Missing ID"
    description: "Required identification not provided"
    
  RC-KYC-SANCTION:
    name: "Sanctions Match"
    description: "Customer matches sanctioned entity"
    regulation_ref: "SEMA"
    
  RC-KYC-OUTSIDE-APPETITE:
    name: "Outside Risk Appetite"
    description: "Customer risk exceeds institutional appetite"
```

---

## 3. Reporting — 200 Precedents

### Scenarios

| Scenario | Code | Count | Appealed | Overturned |
|----------|------|-------|----------|------------|
| **LCTR (Large Cash)** | | 60 | 3 | 0 |
| └─ Standard cash >$10K | RPT-LCTR-STD | 30 | 1 | 0 |
| └─ Multiple cash same day | RPT-LCTR-MULTI | 15 | 1 | 0 |
| └─ Casino disbursement | RPT-LCTR-CASINO | 15 | 1 | 0 |
| **STR (Suspicious)** | | 100 | 15 | 3 |
| └─ Structuring | RPT-STR-STRUCT | 25 | 4 | 1 |
| └─ Unusual activity | RPT-STR-UNUSUAL | 25 | 4 | 1 |
| └─ Third party | RPT-STR-3RD | 20 | 3 | 1 |
| └─ Layering | RPT-STR-LAYER | 15 | 2 | 0 |
| └─ Source of funds | RPT-STR-SOF | 15 | 2 | 0 |
| **Terrorist Property** | | 20 | 2 | 0 |
| └─ Listed entity | RPT-TPR-LIST | 15 | 1 | 0 |
| └─ Associated entity | RPT-TPR-ASSOC | 5 | 1 | 0 |
| **No Report (Boundary)** | | 20 | 4 | 1 |
| └─ Explained unusual | RPT-NONE-EXPL | 10 | 2 | 1 |
| └─ Below threshold | RPT-NONE-THRESH | 10 | 2 | 0 |
| **Total** | | **200** | **24** | **4** |

### Fingerprint Schema

```yaml
schema_id: decisiongraph:aml:report:v1
fields:
  # Transaction context
  - txn.type
  - txn.amount_band
  - txn.cash_involved
  - txn.cash_amount_band
  
  # Suspicious indicators
  - suspicious.indicator_count
  - suspicious.structuring
  - suspicious.unusual_pattern
  - suspicious.third_party
  - suspicious.layering
  - suspicious.source_unclear
  - suspicious.purpose_unclear
  
  # Terrorist financing
  - terrorist.property_indicators
  - terrorist.listed_entity
  - terrorist.associated_entity
  
  # History
  - prior.sars_filed
  - prior.lctr_filed
  - prior.account_closures

banding_rules:
  suspicious.indicator_count:
    0: "none"
    1: "single"
    2-3: "multiple"
    4+: "many"
    
  prior.sars_filed:
    0: "none"
    1: "one"
    2-4: "few"
    5+: "many"
```

### Reason Codes

```yaml
registry_id: decisiongraph:aml:report:v1

codes:
  # LCTR
  RC-RPT-LCTR:
    name: "LCTR Required"
    description: "Large cash transaction over $10,000"
    regulation_ref: "PCMLTFA Section 9"
    
  RC-RPT-LCTR-MULTI:
    name: "LCTR - Multiple Transactions"
    description: "Multiple cash transactions totaling over $10,000"
    regulation_ref: "PCMLTFA Section 9(1)"
    
  # STR
  RC-RPT-STR:
    name: "STR Required"
    description: "Reasonable grounds to suspect ML/TF"
    regulation_ref: "PCMLTFA Section 7"
    
  RC-RPT-STR-STRUCT:
    name: "STR - Structuring"
    description: "Suspected structuring to avoid reporting"
    
  RC-RPT-STR-UNUSUAL:
    name: "STR - Unusual Activity"
    description: "Activity unusual for customer profile"
    
  RC-RPT-STR-3RD:
    name: "STR - Third Party"
    description: "Suspected third party involvement"
    
  RC-RPT-STR-LAYER:
    name: "STR - Layering"
    description: "Suspected layering activity"
    
  # TPR
  RC-RPT-TPR:
    name: "Terrorist Property Report"
    description: "Property of listed terrorist entity"
    regulation_ref: "Criminal Code Section 83.1"
    
  # No report
  RC-RPT-NONE:
    name: "No Report Required"
    description: "No reporting threshold met"
    
  RC-RPT-NONE-EXPLAINED:
    name: "Unusual Activity Explained"
    description: "Initially unusual activity satisfactorily explained"
```

---

## 4. Sanctions/Screening — 350 Precedents

### Scenarios

| Scenario | Code | Count | Appealed | Overturned |
|----------|------|-------|----------|------------|
| **True Positive** | | 60 | 5 | 0 |
| └─ OFAC SDN list | SCR-TP-OFAC | 25 | 2 | 0 |
| └─ UN sanctions | SCR-TP-UN | 20 | 2 | 0 |
| └─ Canadian SEMA | SCR-TP-SEMA | 15 | 1 | 0 |
| **False Positive** | | 120 | 20 | 8 |
| └─ Common name | SCR-FP-NAME | 50 | 8 | 4 |
| └─ Similar DOB | SCR-FP-DOB | 30 | 5 | 2 |
| └─ Partial match | SCR-FP-PARTIAL | 25 | 4 | 1 |
| └─ Alias confusion | SCR-FP-ALIAS | 15 | 3 | 1 |
| **Ownership Chain** | | 60 | 12 | 3 |
| └─ Direct >50% | SCR-OWN-DIRECT | 25 | 4 | 1 |
| └─ Indirect >50% | SCR-OWN-INDIRECT | 20 | 5 | 1 |
| └─ Aggregated >50% | SCR-OWN-AGG | 15 | 3 | 1 |
| **De-listed Entities** | | 40 | 8 | 2 |
| └─ Recently de-listed | SCR-DELIST-REC | 20 | 4 | 1 |
| └─ Long de-listed | SCR-DELIST-OLD | 20 | 4 | 1 |
| **Secondary Sanctions** | | 40 | 6 | 1 |
| └─ Iran related | SCR-SEC-IRAN | 20 | 3 | 1 |
| └─ Russia related | SCR-SEC-RUS | 15 | 2 | 0 |
| └─ North Korea related | SCR-SEC-DPRK | 5 | 1 | 0 |
| **PEP Screening** | | 30 | 5 | 1 |
| └─ PEP confirmed | SCR-PEP-CONF | 15 | 2 | 0 |
| └─ PEP false positive | SCR-PEP-FP | 15 | 3 | 1 |
| **Total** | | **350** | **56** | **15** |

### Fingerprint Schema

```yaml
schema_id: decisiongraph:aml:screening:v1
fields:
  # Match details
  - match.type                  # sanctions, pep, adverse_media
  - match.list_source          # ofac, un, eu, uk, ca_sema
  - match.score_band
  - match.name_match_type      # exact, fuzzy, alias, partial
  - match.secondary_identifiers # dob, nationality, address matched
  
  # Entity details
  - entity.type                # individual, corporate, vessel, aircraft
  - entity.jurisdiction
  
  # Ownership
  - ownership.direct_pct_band
  - ownership.indirect_pct_band
  - ownership.aggregated_over_50
  - ownership.chain_depth
  
  # De-listing
  - delisted.status
  - delisted.date_band
  
  # Secondary sanctions
  - secondary.exposure
  - secondary.jurisdiction

banding_rules:
  match.score:
    0-69: "low"
    70-84: "medium"
    85-94: "high"
    95-100: "exact"
    
  ownership.direct_pct:
    0-24: "minority"
    25-49: "significant"
    50-100: "controlling"
    
  delisted.months_since:
    0-6: "recent"
    7-24: "moderate"
    25+: "old"
```

### Reason Codes

```yaml
registry_id: decisiongraph:aml:screening:v1

codes:
  # True positive
  RC-SCR-SANCTION:
    name: "Sanctions Match Confirmed"
    description: "Entity confirmed on sanctions list"
    regulation_ref: "SEMA, OFAC, UN"
    
  RC-SCR-OFAC:
    name: "OFAC SDN Match"
    description: "Match to OFAC Specially Designated Nationals list"
    
  RC-SCR-UN:
    name: "UN Sanctions Match"
    description: "Match to UN consolidated sanctions list"
    
  RC-SCR-SEMA:
    name: "Canadian SEMA Match"
    description: "Match to Canadian sanctions under SEMA"
    
  # False positive
  RC-SCR-FP:
    name: "False Positive"
    description: "Screening match determined to be false positive"
    
  RC-SCR-FP-NAME:
    name: "False Positive - Common Name"
    description: "Match due to common name, different person confirmed"
    
  RC-SCR-FP-DOB:
    name: "False Positive - DOB Mismatch"
    description: "Name similar but date of birth does not match"
    
  # Ownership
  RC-SCR-OWN-50:
    name: "Sanctioned Ownership >50%"
    description: "Entity >50% owned by sanctioned party"
    regulation_ref: "OFAC 50% Rule"
    
  RC-SCR-OWN-CLEAR:
    name: "Ownership Below Threshold"
    description: "Sanctioned ownership below 50% threshold"
    
  # De-listed
  RC-SCR-DELIST-CLEAR:
    name: "De-listed - Clear"
    description: "Entity removed from sanctions list, cleared"
    
  RC-SCR-DELIST-MONITOR:
    name: "De-listed - Enhanced Monitoring"
    description: "Recently de-listed, enhanced monitoring applied"
    
  # Secondary
  RC-SCR-SECONDARY:
    name: "Secondary Sanctions Exposure"
    description: "Transaction may trigger secondary sanctions"
    
  # PEP
  RC-SCR-PEP-CONF:
    name: "PEP Status Confirmed"
    description: "Politically exposed person status confirmed"
    
  RC-SCR-PEP-FP:
    name: "PEP False Positive"
    description: "PEP screening match is false positive"
```

---

## 5. Ongoing Monitoring — 300 Precedents

### Scenarios

| Scenario | Code | Count | Appealed | Overturned |
|----------|------|-------|----------|------------|
| **Activity Triggers** | | 80 | 12 | 2 |
| └─ Volume spike | MON-SPIKE-VOL | 30 | 5 | 1 |
| └─ Value spike | MON-SPIKE-VAL | 25 | 4 | 1 |
| └─ New pattern | MON-NEW-PAT | 25 | 3 | 0 |
| **Periodic Review** | | 70 | 8 | 1 |
| └─ Annual - no change | MON-ANN-NC | 30 | 2 | 0 |
| └─ Annual - risk upgrade | MON-ANN-UP | 20 | 3 | 1 |
| └─ Annual - risk downgrade | MON-ANN-DOWN | 20 | 3 | 0 |
| **Profile Changes** | | 60 | 10 | 2 |
| └─ Address change | MON-CHG-ADDR | 20 | 3 | 1 |
| └─ Beneficial owner change | MON-CHG-BO | 20 | 4 | 1 |
| └─ Industry change | MON-CHG-IND | 20 | 3 | 0 |
| **Dormant Reactivation** | | 50 | 10 | 2 |
| └─ Clean reactivation | MON-DORM-CLEAN | 25 | 4 | 1 |
| └─ Suspicious reactivation | MON-DORM-SUSP | 25 | 6 | 1 |
| **Exit Decisions** | | 40 | 8 | 2 |
| └─ Risk-based exit | MON-EXIT-RISK | 20 | 4 | 1 |
| └─ SAR-related exit | MON-EXIT-SAR | 10 | 2 | 1 |
| └─ Regulatory exit | MON-EXIT-REG | 10 | 2 | 0 |
| **Total** | | **300** | **48** | **9** |

### Fingerprint Schema

```yaml
schema_id: decisiongraph:aml:monitoring:v1
fields:
  # Trigger type
  - trigger.type                # activity_spike, periodic, profile_change, dormant, exit
  
  # Activity triggers
  - activity.volume_change_band
  - activity.value_change_band
  - activity.new_pattern
  - activity.new_jurisdiction
  - activity.new_counterparty_type
  
  # Periodic review
  - review.type                 # annual, trigger_based, regulatory
  - review.risk_change          # unchanged, upgraded, downgraded
  - review.kyc_refresh_needed
  
  # Profile changes
  - profile.address_change
  - profile.bo_change
  - profile.industry_change
  - profile.jurisdiction_change
  
  # Dormant
  - dormant.months_inactive
  - dormant.reactivation_pattern
  
  # Exit
  - exit.reason                 # risk, sar, regulatory, commercial
  - exit.sar_related

banding_rules:
  activity.volume_change_pct:
    0-50: "minor"
    51-100: "moderate"
    101-300: "significant"
    301+: "extreme"
    
  dormant.months_inactive:
    6-12: "short"
    13-24: "medium"
    25-60: "long"
    61+: "very_long"
```

### Reason Codes

```yaml
registry_id: decisiongraph:aml:monitoring:v1

codes:
  # Activity triggers
  RC-MON-SPIKE:
    name: "Activity Spike"
    description: "Significant increase in transaction activity"
    
  RC-MON-NEW-PATTERN:
    name: "New Transaction Pattern"
    description: "Previously unseen transaction behavior"
    
  RC-MON-NEW-JURIS:
    name: "New Jurisdiction"
    description: "Transactions to previously unseen jurisdiction"
    
  # Periodic review
  RC-MON-REVIEW-CLEAR:
    name: "Periodic Review - Clear"
    description: "Annual review completed, no concerns"
    
  RC-MON-REVIEW-UPGRADE:
    name: "Risk Upgrade"
    description: "Customer risk rating increased"
    
  RC-MON-REVIEW-DOWNGRADE:
    name: "Risk Downgrade"
    description: "Customer risk rating decreased"
    
  RC-MON-KYC-REFRESH:
    name: "KYC Refresh Required"
    description: "Customer due for KYC information update"
    
  # Profile changes
  RC-MON-PROFILE-CHG:
    name: "Profile Change Review"
    description: "Customer profile change requires review"
    
  RC-MON-BO-CHG:
    name: "Beneficial Owner Change"
    description: "Change in beneficial ownership structure"
    
  # Dormant
  RC-MON-DORM-REACT:
    name: "Dormant Reactivation"
    description: "Previously dormant account reactivated"
    
  RC-MON-DORM-SUSP:
    name: "Suspicious Reactivation"
    description: "Dormant account reactivation shows suspicious patterns"
    
  # Exit
  RC-MON-EXIT:
    name: "Relationship Exit"
    description: "Decision to terminate customer relationship"
    
  RC-MON-EXIT-RISK:
    name: "Risk-Based Exit"
    description: "Exit due to unacceptable risk level"
    
  RC-MON-EXIT-SAR:
    name: "SAR-Related Exit"
    description: "Exit following suspicious activity reporting"
```

---

## Regime IDs (Banking)

```yaml
regimes:
  CA-FINTRAC-V2024:
    name: "FINTRAC 2024 Guidelines"
    status: current
    effective_from: "2024-01-01"
    regulations:
      - PCMLTFA
      - PCMLTFR
      - FINTRAC Guidelines
      - FINTRAC Guidance FIN-2023-G01
    
  CA-FINTRAC-V2023:
    name: "FINTRAC 2023 Guidelines"
    status: superseded
    effective_from: "2023-01-01"
    superseded_by: CA-FINTRAC-V2024
    breaking_changes:
      - "Virtual currency reporting thresholds changed"
      - "Travel rule requirements expanded"
      - "Beneficial ownership threshold clarified"
    
  CA-FINTRAC-V2022:
    name: "FINTRAC 2022 Guidelines"
    status: superseded
    effective_from: "2022-01-01"
    superseded_by: CA-FINTRAC-V2023
```

---

## Namespace Structure

```
/precedents/decisiongraph/
├── txn/
│   └── CA/
│       ├── normal_approvals.yaml
│       ├── structuring.yaml
│       ├── high_risk_country.yaml
│       ├── pep_transactions.yaml
│       ├── crypto.yaml
│       ├── layering.yaml
│       ├── unusual_patterns.yaml
│       └── trade_based.yaml
├── kyc/
│   └── CA/
│       ├── standard_approvals.yaml
│       ├── pep_handling.yaml
│       ├── high_risk_industry.yaml
│       ├── missing_docs.yaml
│       ├── adverse_media.yaml
│       ├── shell_company.yaml
│       └── sanctions.yaml
├── reporting/
│   └── CA/
│       ├── lctr.yaml
│       ├── str.yaml
│       ├── tpr.yaml
│       └── no_report.yaml
├── screening/
│   └── GLOBAL/
│       ├── true_positive.yaml
│       ├── false_positive.yaml
│       ├── ownership_chain.yaml
│       ├── delisted.yaml
│       ├── secondary_sanctions.yaml
│       └── pep_screening.yaml
└── monitoring/
    └── CA/
        ├── activity_triggers.yaml
        ├── periodic_review.yaml
        ├── profile_changes.yaml
        ├── dormant.yaml
        └── exit_decisions.yaml
```

---

## Implementation Order

### 1. Create Fingerprint Schemas (5)

```
decisiongraph:aml:txn:v1
decisiongraph:aml:kyc:v1
decisiongraph:aml:report:v1
decisiongraph:aml:screening:v1
decisiongraph:aml:monitoring:v1
```

### 2. Create Reason Code Registries (5)

```
decisiongraph:aml:txn:v1
decisiongraph:aml:kyc:v1
decisiongraph:aml:report:v1
decisiongraph:aml:screening:v1
decisiongraph:aml:monitoring:v1
```

### 3. Create Seed Configs

Config files for each category with scenario definitions.

### 4. Generate Seeds

```bash
python -m decisiongraph.precedent.seed_generator \
  --domain banking \
  --all-categories \
  --output seeds/decisiongraph/
```

### 5. Load and Verify

```bash
python -m decisiongraph.precedent.seed_loader \
  --input seeds/decisiongraph/ \
  --namespace /precedents/decisiongraph/
```

---

## Verification

### Expected Results

```python
stats = registry.get_statistics(namespace="/precedents/decisiongraph/")

# Expected:
# Total precedents: 2,000
# Transaction monitoring: 700
# KYC onboarding: 450
# Reporting: 200
# Screening: 350
# Ongoing monitoring: 300

# Appeal stats:
# Total appealed: ~300 (15%)
# Total overturned: ~51 (2.5%)
```

### Query Tests

```python
# Structuring cases
results = registry.find_by_reason_codes(["RC-TXN-STRUCT"])
assert len(results) >= 100

# False positive screening
results = registry.find_by_reason_codes(["RC-SCR-FP"])
assert len(results) >= 100

# Exit decisions
results = registry.find_by_reason_codes(["RC-MON-EXIT"])
assert len(results) >= 35

# Boundary cases
results = registry.find_overturned()
assert len(results) >= 50
```

---

## Banking Summary

| Category | Precedents | Appealed | Overturned |
|----------|------------|----------|------------|
| Transaction Monitoring | 700 | 104 | 12 |
| KYC Onboarding | 450 | 68 | 11 |
| Reporting | 200 | 24 | 4 |
| Sanctions/Screening | 350 | 56 | 15 |
| Ongoing Monitoring | 300 | 48 | 9 |
| **Total** | **2,000** | **300** | **51** |

| Metric | Value |
|--------|-------|
| Appeal Rate | 15% |
| Overturn Rate | 2.5% |
| Fingerprint Schemas | 5 |
| Reason Code Registries | 5 |
| Unique Reason Codes | ~85 |
| Boundary Cases | 51 |

---

## Grand Total (Insurance + Banking)

| Product | Precedents |
|---------|------------|
| ClaimPilot (Insurance) | 2,150 |
| DecisionGraph (Banking) | 2,000 |
| **Grand Total** | **4,150** |

This provides enterprise-grade precedent coverage for both products.

