# KYC Onboarding POC Packet

**DecisionGraph v1.0.0** - Corporate KYC/CDD Demo

## Overview

This POC demonstrates DecisionGraph's decision engine for corporate KYC onboarding. Two realistic bank cases show the full CDD workflow: entity profiling → UBO identification → screening → identity verification → document collection → risk decision.

---

## Demo Cases

### Case 1: Clean Onboarding (ACT-KYC-2026-0001)

**Entity**: Sterling Designs Ltd (BC Corporation)
**Expected Outcome**: APPROVE (with mitigations)

```
Corporate Profile:
  Legal Name:     Sterling Designs Ltd
  Jurisdiction:   BC, Canada
  NAICS:          541410 (Interior Design Services)
  Incorporated:   2018-03-15
  Employees:      25
  Annual Revenue: $4.5M CAD

Beneficial Owners:
  ┌─────────────────────────────────────────────────────────────┐
  │ UBO-001: Marcus Sterling (60%)                              │
  │   - Canadian citizen, resident                              │
  │   - Source of Wealth: Business ownership                    │
  │   - IDV: PASS (Jumio, 98% confidence)                       │
  │   - PEP: CLEAR                                              │
  │   - Sanctions: CLEAR                                        │
  └─────────────────────────────────────────────────────────────┘
  ┌─────────────────────────────────────────────────────────────┐
  │ UBO-002: Elena Kowalski (40%)                               │
  │   - Polish citizen, CA resident                             │
  │   - Source of Wealth: Prior employment                      │
  │   - IDV: PASS (Jumio, 96% confidence)                       │
  │   - PEP: CLEAR                                              │
  │   - Sanctions: CLEAR                                        │
  └─────────────────────────────────────────────────────────────┘

Documents on File: 8/8 complete
  ✓ Certificate of Incorporation
  ✓ Articles of Incorporation
  ✓ Shareholder Register
  ✓ Audited Financial Statements (Grant Thornton)
  ✓ T2 Tax Return 2024
  ✓ Passport (Marcus Sterling)
  ✓ Passport (Elena Kowalski)
  ✓ Proof of Address (BC Hydro)

Screening Summary:
  Sanctions: 0 matches
  PEP:       0 matches
  Adverse:   0 matches
```

**Why this case should APPROVE**: Complete documentation, all UBOs verified, clean screening, low-risk industry, Canadian domestic.

---

### Case 2: Problem Onboarding (CSV-KYC-2026-0001)

**Entity**: Maple Horizons Imports Inc (ON Corporation)
**Expected Outcome**: BLOCK/ESCALATE

```
Corporate Profile:
  Legal Name:     Maple Horizons Imports Inc
  Jurisdiction:   ON, Canada
  NAICS:          418410 (Food Merchant Wholesalers)
  Incorporated:   2024-11-15 (< 90 days old!)
  Employees:      8
  Annual Revenue: $850K CAD

Beneficial Owners:
  ┌─────────────────────────────────────────────────────────────┐
  │ UBO-101: Viktor Petrov (35%)                                │
  │   - Russian citizen, CA resident                            │
  │   - Source of Wealth: Prior employment                      │
  │   - IDV: PASS (Jumio, 94% confidence)                       │
  │   - Sanctions: POSSIBLE MATCH (72%, OFAC SDN)  ⚠️           │
  │   - PEP: CLEAR                                              │
  └─────────────────────────────────────────────────────────────┘
  ┌─────────────────────────────────────────────────────────────┐
  │ UBO-102: Dmitri Volkov (40%)                                │
  │   - Russian citizen, UAE resident  ⚠️                       │
  │   - Source of Wealth: UNKNOWN  ⚠️                           │
  │   - IDV: FAIL (expired doc, liveness fail)  ❌              │
  │   - Sanctions: POSSIBLE MATCH (85%, EU List)  ⚠️            │
  │   - PEP: POSSIBLE MATCH (78%, Russia Regional)  ⚠️          │
  │   - Adverse: CONFIRMED (News Articles 2024)  ❌             │
  └─────────────────────────────────────────────────────────────┘
  ┌─────────────────────────────────────────────────────────────┐
  │ UBO-103: UNKNOWN (25%)  ❌                                  │
  │   - Identity: NOT VERIFIED                                  │
  │   - Ownership not documented                                │
  └─────────────────────────────────────────────────────────────┘

Documents on File: 5/8 incomplete
  ✓ Certificate of Incorporation
  ⚠ Articles (awaiting translation)
  ⚠ Shareholder Register (PARTIAL - missing UBO-103)
  ✓ Passport (Viktor Petrov)
  ❌ Passport (Dmitri Volkov - EXPIRED)
  ✗ Proof of Address (mismatch with registry)
  ✗ Financial Statements (not collected)
  ✗ Tax Filing (not collected)

Screening Summary:
  Sanctions: 2 POSSIBLE MATCHES (pending resolution)
  PEP:       1 POSSIBLE MATCH (pending resolution)
  Adverse:   1 CONFIRMED HIT

Registry Verification:
  ✓ Entity exists
  ❌ Directors do not match (MISMATCH)
  ❌ Address does not match (DISCREPANCY)
```

**Why this case should BLOCK**: Multiple sanctions/PEP hits pending, identity verification failure, unknown UBO, registry discrepancies, newly incorporated entity.

---

## Quick Start

```bash
# Run the demo
./poc/kyc/demo.sh

# Or run individual cases
./dg run-case \
  --case poc/kyc/mapped/ACT-KYC-2026-0001_bundle.json \
  --pack packs/fincrime_canada.yaml \
  --out /tmp/kyc_output/
```

---

## Folder Structure

```
poc/kyc/
├── README.md                           # This file
├── demo.sh                             # Demo script
├── inputs/
│   ├── actimize_kyc_packet.json        # Actimize-style input (Case 1)
│   └── generic_csv/
│       ├── customer.csv                # Customer profile
│       ├── ubo.csv                     # Beneficial ownership
│       ├── screening.csv               # Screening results
│       ├── documents.csv               # Document inventory
│       └── verification.csv            # IDV/verification results
├── mapped/
│   ├── ACT-KYC-2026-0001_bundle.json   # Mapped CaseBundle (clean)
│   └── CSV-KYC-2026-0001_bundle.json   # Mapped CaseBundle (problem)
└── output/
    ├── ACT-KYC-2026-0001/              # Decision output
    └── CSV-KYC-2026-0001/              # Decision output
```

---

## KYC-Specific Signals (Roadmap)

The current pack uses general Financial Crime signals. A production KYC pack would add:

| Signal | Severity | Trigger |
|--------|----------|---------|
| `KYC_IDV_FAILED` | HIGH | Identity verification failed |
| `KYC_IDV_LIVENESS_FAIL` | HIGH | Liveness check failed |
| `KYC_DOC_EXPIRED` | MEDIUM | Document expired |
| `KYC_UBO_UNVERIFIED` | HIGH | UBO not verified |
| `KYC_UBO_MISSING` | CRITICAL | UBO not identified (>25%) |
| `KYC_REGISTRY_MISMATCH` | HIGH | Registry data doesn't match |
| `KYC_DIRECTOR_MISMATCH` | HIGH | Directors don't match registry |
| `KYC_ADDRESS_DISCREPANCY` | MEDIUM | Address doesn't match |
| `KYC_NEWLY_INCORPORATED` | MEDIUM | Entity < 1 year old |
| `KYC_DOCS_INCOMPLETE` | MEDIUM | Required docs missing |
| `KYC_SANCTIONS_PENDING` | CRITICAL | Sanctions hit pending resolution |
| `KYC_PEP_PENDING` | HIGH | PEP hit pending resolution |

## KYC-Specific Mitigations (Roadmap)

| Mitigation | Weight | Condition |
|------------|--------|-----------|
| `MIT_DOCS_COMPLETE` | -0.30 | All required docs on file |
| `MIT_AUDITED_FINANCIALS` | -0.25 | Audit report present |
| `MIT_TAX_COMPLIANT` | -0.20 | Tax filings verified |
| `MIT_ALL_UBOS_VERIFIED` | -0.35 | 100% UBO verification |
| `MIT_REGISTRY_VERIFIED` | -0.20 | Registry match confirmed |
| `MIT_IDV_HIGH_CONFIDENCE` | -0.25 | IDV score > 95% |
| `MIT_ESTABLISHED_ENTITY` | -0.20 | Entity > 3 years old |
| `MIT_LOW_RISK_INDUSTRY` | -0.15 | NAICS in approved list |

---

## What the Report Should Show (Future Enhancement)

A production KYC report would include these sections:

```
========================================================================
DECISIONGRAPH KYC CASE REPORT
========================================================================

1. CUSTOMER & BUSINESS PROFILE
   - Legal name, trading name, registration
   - Industry (NAICS), years in business
   - Expected activity profile

2. IDENTITY VERIFICATION RESULTS
   - Per-UBO: document type, result, confidence
   - Liveness check results
   - Device/session risk (if applicable)

3. OWNERSHIP & CONTROL (UBO GRAPH)
   - Visual representation of ownership chain
   - Verification status per UBO
   - Total verified ownership %

4. SCREENING SUMMARY
   - Sanctions: hits, dispositions, pending
   - PEP: matches, status
   - Adverse media: hits, severity

5. DOCUMENTS ON FILE
   - Document inventory with verification status
   - Completeness score (e.g., 8/10 = 80%)
   - Missing/expired documents

6. RISK DRIVERS (by pillar)
   - Identity Risk: signals + evidence
   - Ownership Risk: signals + evidence
   - Geographic Risk: signals + evidence
   - Screening Risk: signals + evidence

7. MITIGATIONS APPLIED
   - Each mitigation with evidence anchor

8. EDD REQUIREMENTS (if applicable)
   - What additional info is needed
   - Deadline for collection

9. DECISION & REQUIRED ACTIONS
   - Verdict
   - Required signoffs
   - Next steps

10. AUDIT TRAIL
    - Pack hash, adapter hash, report hash
    - Timestamp, engine version
========================================================================
```

---

## Adapters

### Available

| Adapter | Path | Status |
|---------|------|--------|
| Actimize KYC | `adapters/kyc/actimize_onboarding/mapping.yaml` | Ready |
| Generic CSV | `adapters/kyc/generic_onboarding/mapping.yaml` | Ready |

### Adding New Adapters

Create a YAML mapping from your onboarding system's export format to CaseBundle. See `adapters/SPEC.md` for the full specification.

---

## Next Steps

1. **KYC-Specific Pack**: Create `packs/kyc_canada.yaml` with the signals/mitigations listed above
2. **Enhanced Report Template**: Implement the 10-section KYC report format
3. **EDD Workflow**: Add triggered EDD case type for high-risk customers
4. **Periodic Review**: Implement `kyc_refresh` for ongoing monitoring

---

## Contact

DecisionGraph - Deterministic Financial Crime Decisions

```
"Complete CDD. Every time. Documented."
```
