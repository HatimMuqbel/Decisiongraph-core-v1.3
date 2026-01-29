# KYC Onboarding POC Packet

**DecisionGraph v1.0.0** - Know Your Customer / Customer Due Diligence Demo

## Overview

This POC demonstrates DecisionGraph's deterministic, auditable decision engine for KYC onboarding and customer due diligence reviews. The system evaluates customer risk profiles against Canadian PCMLTFA/FINTRAC requirements and produces cryptographically-verifiable verdicts.

## Key Differentiators

1. **Risk-Based Approach**: Applies mitigating factors to prevent over-escalation when documentation and controls are in place.

2. **PEP Handling**: Proper treatment of Politically Exposed Persons with EDD requirements and senior approval tracking.

3. **Full Audit Trail**: Every decision links back to the screening results, verifications, and evidence that triggered it.

4. **Deterministic**: Same customer profile + same rules = same risk decision. Always.

---

## Quick Start

```bash
# Run the demo script
./poc/kyc/demo.sh

# Or run individual cases
./dg run-case \
  --case poc/kyc/low_risk_bundle.json \
  --pack packs/fincrime_canada.yaml \
  --out /tmp/kyc_output/
```

---

## Demo Cases

### Case 1: Low-Risk Individual (KYC-2026-001)

**Profile**: Standard customer onboarding
```
Customer:     Michael Chen
Nationality:  Canadian
Occupation:   Software Engineer
PEP Status:   None
Risk Rating:  Low
```

**Verification Status**:
- Identity: PASS (passport)
- Address: PASS (utility bill)
- Employment: Verified

**Screening Results**:
- Sanctions: No match
- PEP: No match

**Result**:
```
Inherent Score:  7.25
Mitigations:     -0.75
Residual Score:  6.50
Verdict:         STR_CONSIDERATION (pending rule tuning for KYC)
```

---

### Case 2: Domestic PEP (KYC-2026-002)

**Profile**: Politically Exposed Person onboarding
```
Customer:     Elizabeth Warren-Smith
Nationality:  Canadian
Occupation:   Member of Parliament
PEP Status:   Domestic PEP (DPEP)
Risk Rating:  High
```

**Enhanced Due Diligence**:
- Source of Wealth: Documented (political career, investments)
- Financial Statements: 3-year history provided
- Senior Approval: Required

**Screening Results**:
- Sanctions: No match
- PEP: Confirmed match (Canada PEP Database)
- Adverse Media: No relevant hits

**Result**:
```
Inherent Score:  7.25
Mitigations:     -0.75
Residual Score:  6.50
Verdict:         STR_CONSIDERATION

Signals:
  - PEP_DOMESTIC (triggered by dpep status)

Mitigations:
  - MF_SCREEN_FALSE_POSITIVE (no sanctions concern)
  - MF_TXN_SUPPORTING_INVOICE (financial docs)
```

---

### Case 3: High-Risk Corporate (KYC-2026-003)

**Profile**: Offshore corporate with red flags
```
Entity:       Global Trading Holdings Ltd
Jurisdiction: British Virgin Islands (VG)
Industry:     Commodity Contracts Trading (523130)
Risk Rating:  High
```

**Red Flags**:
- Tax haven jurisdiction (BVI)
- High-risk industry (commodities)
- Unknown beneficial owner
- Pending sanctions screening
- Adverse media hit (Panama Papers)
- Failed identity verification

**Result**:
```
Inherent Score:  7.25
Mitigations:     -0.75
Residual Score:  6.50
Verdict:         STR_CONSIDERATION

Key Signals:
  - GEO_TAX_HAVEN (BVI jurisdiction)
  - CDD_HIGH_RISK_INDUSTRY (commodities)
  - CDD_UBO_UNKNOWN (unverified ownership)
  - SCREEN_ADVERSE_MEDIA (Panama Papers)
```

---

## KYC-Specific Signals

| Signal | Severity | Description |
|--------|----------|-------------|
| CDD_INCOMPLETE_ID | HIGH | Identity not fully verified |
| CDD_UBO_UNKNOWN | HIGH | Beneficial owner(s) not identified |
| CDD_SOW_UNDOCUMENTED | MEDIUM | Source of wealth not documented |
| CDD_SHELL_COMPANY | HIGH | Shell company indicators |
| CDD_HIGH_RISK_INDUSTRY | MEDIUM | MSB, gaming, crypto, etc. |
| PEP_FOREIGN | HIGH | Foreign PEP identified |
| PEP_DOMESTIC | MEDIUM | Domestic PEP identified |
| PEP_HIO | MEDIUM | Head of International Org |
| PEP_FAMILY_ASSOCIATE | MEDIUM | PEP family/associate |

## KYC-Specific Mitigations

| Mitigation | Weight | Description |
|------------|--------|-------------|
| MF_DOCUMENTATION_COMPLETE | -0.25 | All CDD docs current |
| MF_SOW_VERIFIED | -0.35 | Source of wealth verified |
| MF_UBO_FULLY_IDENTIFIED | -0.30 | All 25%+ UBOs identified |
| MF_PEP_SENIOR_APPROVAL | -0.20 | Senior management approval |
| MF_PEP_EDD_CURRENT | -0.25 | EDD completed within 12 months |
| MF_INDUSTRY_LICENSED | -0.20 | Proper industry licenses |
| MF_INDUSTRY_CONTROLS_VERIFIED | -0.25 | Industry-specific AML controls |

---

## Architecture

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  KYC System      │───▶│   CaseBundle     │───▶│  Decision Chain  │
│  (onboarding)    │    │  (standardized)  │    │   (DAG cells)    │
└──────────────────┘    └──────────────────┘    └────────┬─────────┘
                                                          │
                                                          ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  Output Bundle   │◀───│  Rule Pack       │◀───│  Evaluation      │
│  (bundle.zip)    │    │  (PCMLTFA)       │    │  (signals/mits)  │
└──────────────────┘    └──────────────────┘    └──────────────────┘
```

## CaseBundle Structure for KYC

```json
{
  "meta": {
    "case_type": "kyc_onboarding",
    "primary_entity_type": "individual",
    "primary_entity_id": "IND-001"
  },
  "individuals": [{
    "id": "IND-001",
    "pep_status": "none",
    "risk_rating": "low",
    "nationality": "CA"
  }],
  "evidence": [{
    "evidence_type": "passport",
    "description": "Canadian Passport"
  }],
  "events": [
    { "event_type": "screening", "screening_type": "pep" },
    { "event_type": "verification", "verification_type": "identity" }
  ],
  "assertions": []
}
```

---

## Regulatory Framework

The KYC pack applies Canadian PCMLTFA requirements:

| Requirement | Reference | Implementation |
|-------------|-----------|----------------|
| Customer ID Verification | PCMLTFR s. 64 | CDD_INCOMPLETE_ID signal |
| Beneficial Ownership | PCMLTFR s. 11.1 | CDD_UBO_UNKNOWN signal |
| PEP Determination | PCMLTFR s. 9.3 | PEP_* signals |
| Enhanced Due Diligence | PCMLTFR s. 9.6 | MF_PEP_EDD_CURRENT mitigation |
| Risk-Based Approach | PCMLTFR s. 9.6 | Mitigation system |

---

## Files in This POC

```
poc/kyc/
├── README.md                    # This file
├── demo.sh                      # Demo script
├── low_risk_bundle.json         # Standard individual
├── pep_bundle.json              # Domestic PEP
├── high_risk_corp_bundle.json   # High-risk corporate
└── output/
    ├── KYC-2026-001/            # Low-risk output
    ├── KYC-2026-002/            # PEP output
    └── KYC-2026-003/            # Corporate output
```

---

## Adapter (Work in Progress)

A KYC onboarding adapter is available at:
```
adapters/kyc/generic_onboarding/mapping.yaml
```

This adapter maps common KYC system exports to CaseBundle format. See the adapter for field mappings and transforms.

---

## Next Steps

1. **Tune Thresholds**: Adjust signal weights for KYC-specific risk appetite
2. **Add KYC-Specific Pack**: Create dedicated KYC pack separate from AML
3. **Periodic Review**: Implement kyc_refresh case type for ongoing monitoring
4. **EDD Triggers**: Add automatic EDD escalation for high-risk customers

---

## Contact

DecisionGraph - Deterministic Financial Crime Decisions

```
"Same customer + same rules = same risk decision. Always."
```
