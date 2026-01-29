# AML Monitoring POC Packet

**DecisionGraph v1.0.0** - Anti-Money Laundering Transaction Monitoring Demo

## Overview

This POC demonstrates DecisionGraph's deterministic, auditable decision engine for AML transaction monitoring cases. The system transforms vendor alerts into standardized CaseBundle format, applies Canadian PCMLTFA/FINTRAC rules, and produces cryptographically-verifiable verdicts.

## Key Differentiators

1. **Mitigations, Not Just Signals**: Other systems only flag risks. DecisionGraph applies mitigating factors to prevent over-escalation when evidence supports lower risk.

2. **Full Audit Trail**: Every decision links back to the facts that triggered it, with cryptographic chain integrity.

3. **Vendor-Agnostic**: Declarative YAML adapters transform any vendor format to CaseBundle without code changes.

4. **Deterministic**: Same input + same rules = same output. Always. Verifiable via report hash.

---

## Quick Start

```bash
# 1. Map vendor data to CaseBundle (Actimize TM example)
./dg map-case \
  --input adapters/fincrime/actimize/example_input.json \
  --adapter adapters/fincrime/actimize/mapping.yaml \
  --out /tmp/case.json

# 2. Run full decision pipeline
./dg run-case \
  --case /tmp/case.json \
  --pack packs/fincrime_canada.yaml \
  --out /tmp/output/

# 3. Verify bundle integrity
./dg verify-bundle /tmp/output/<case_id>/
```

---

## Demo Cases

### Case 1: Actimize TM Alert (High Risk)

**Source**: NICE Actimize Transaction Monitoring export
**Case ID**: ACT-2026-00789

```
Customer:     Maria Rodriguez (CUST-12345)
Transactions: 4 ($14,500 wire from HK, $9,900 cash, $9,800 cash, $32,000 wire to Panama)
Alerts:       Structuring, High-Risk Jurisdiction
Screening:    Sanctions list match (confirmed false positive)
```

**Result**:
```
VERDICT: STR_CONSIDERATION
Inherent Score:  12.25
Mitigations:     -0.50 (False positive screening match)
Residual Score:  11.75

Signals (19):
  - TXN_JUST_BELOW_THRESHOLD (x2 cash deposits just under $10K)
  - GEO_HIGH_RISK_COUNTRY (Hong Kong counterparty)
  - GEO_TAX_HAVEN (Panama wire transfer)
  - STRUCT_CASH_MULTIPLE (structuring alert)
  - SCREEN_SANCTIONS_HIT (confirmed FP)
  ... and 14 more

Mitigations (1):
  - MF_SCREEN_FALSE_POSITIVE (-0.50)
```

### Case 2: Generic CSV Import (Mid-Market Bank)

**Source**: CSV export converted to JSON
**Case ID**: CSV-2026-001

```
Customer:     Sarah Johnson (CUST-001)
Transactions: 3 ($8,500 wire, $9,800 cash, $15,000 wire to Panama)
Alerts:       Structuring
```

**Result**:
```
VERDICT: STR_CONSIDERATION
Inherent Score:  9.75
Residual Score:  9.75 (no mitigations available)
```

---

## Architecture

```
┌──────────────────┐    ┌──────────────┐    ┌──────────────────┐
│  Vendor Export   │───▶│   Adapter    │───▶│   CaseBundle     │
│  (Actimize/CSV)  │    │  (mapping)   │    │  (standardized)  │
└──────────────────┘    └──────────────┘    └────────┬─────────┘
                                                      │
                                                      ▼
┌──────────────────┐    ┌──────────────┐    ┌──────────────────┐
│  Output Bundle   │◀───│  Rule Pack   │◀───│ Decision Chain   │
│  (bundle.zip)    │    │  (PCMLTFA)   │    │   (DAG cells)    │
└──────────────────┘    └──────────────┘    └──────────────────┘
```

## Output Bundle Contents

Each case produces a cryptographically-sealed bundle:

```
output/<case_id>/
├── bundle.zip          # All files, signed (for transport)
├── cells.jsonl         # Complete decision chain (JSON Lines)
├── manifest.json       # Metadata, hashes, provenance
├── pack.json           # Rule pack metadata
├── report.txt          # Human-readable report
├── report.sha256       # Report hash for integrity
└── verification.json   # Verification check results
```

### Manifest Structure (Bank Compliance)

```json
{
  "case_id": "ACT-2026-00789",
  "report_hash": "b69107bb270616ff...",
  "verdict": "STR_CONSIDERATION",
  "score": {
    "inherent_score": "12.25",
    "mitigation_sum": "-0.5",
    "residual_score": "11.75",
    "threshold_gate": "STR_CONSIDERATION"
  },
  "signals_fired": 19,
  "mitigations_applied": 1,
  "chain_length": 59,
  "retention": {
    "retention_class": "10y",
    "legal_hold": false
  },
  "environment": {
    "engine_version": "1.0.0",
    "python_version": "3.12.1",
    "git_commit": "7fc501b"
  }
}
```

---

## Adapters

### Available Adapters

| Vendor | Format | Adapter Path |
|--------|--------|--------------|
| NICE Actimize | JSON | `adapters/fincrime/actimize/mapping.yaml` |
| Generic CSV | JSON | `adapters/fincrime/generic_csv/mapping.yaml` |

### Creating New Adapters

Adapters are pure YAML declarations - no code required:

```yaml
adapter:
  name: my_vendor_v1
  vendor: "My Vendor"
  version: "1.0.0"
  input_format: json

roots:
  case: "$.case"
  customers: "$.customers[*]"
  transactions: "$.transactions[*]"

mappings:
  CaseMeta.case_id: "$.case.id"
  CaseMeta.case_type: "!literal aml_alert"
  Individual.id: "$.customer_id"
  Individual.given_name: "$.first_name"
  TransactionEvent.amount: "$.amount"

transforms:
  direction:
    CR: inbound
    DR: outbound
```

See `adapters/SPEC.md` for full specification.

---

## Rule Pack: Canadian FinCrime (PCMLTFA)

The `fincrime_canada.yaml` pack includes:

### Signals (22)
- **Transaction**: Large cash, threshold avoidance, rapid movement, crypto
- **Geographic**: High-risk countries, sanctioned jurisdictions, tax havens
- **PEP**: Foreign, domestic, HIO, family/associates
- **Structuring**: Multiple deposits, smurfing patterns
- **Screening**: Sanctions hits, adverse media
- **CDD**: Incomplete ID, unknown UBO, shell company indicators

### Mitigations (16)
- Established relationship (5+ years)
- Known customer pattern
- Documentation complete
- Source of wealth verified
- PEP senior approval
- False positive screening
- Legitimate business nexus
- And more...

### Threshold Gates
| Gate | Max Score | Action |
|------|-----------|--------|
| AUTO_CLOSE | 0.25 | Auto-archive with audit trail |
| ANALYST_REVIEW | 0.50 | L1 analyst review |
| SENIOR_REVIEW | 0.75 | Supervisor review |
| COMPLIANCE_REVIEW | 1.00 | Compliance officer review |
| STR_CONSIDERATION | 999.00 | STR filing determination |

---

## Verification

Every bundle includes verification checks:

```bash
$ ./dg verify-bundle output/ACT-2026-00789/

Verification Results:
  [PASS] report_hash      - Report content matches stored hash
  [PASS] chain_integrity  - All cell references valid
  [PASS] determinism      - Re-evaluation produces same result
  [PASS] policy_coverage  - All signals have policy references
  [PASS] gate_consistency - Score matches verdict gate
  [PASS] manifest_hash    - Manifest unchanged

OVERALL: PASS
```

---

## Governance Chain

Complete provenance tracking:

```
Adapter Hash ─────────┐
                      ├──▶ Provenance ──▶ manifest.json
Source File Hash ─────┘

Pack Hash ────────────┐
                      ├──▶ Decision Chain ──▶ cells.jsonl
Case Bundle ──────────┘

Report Hash ──────────┬──▶ verification.json
Environment Stamp ────┘
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | AUTO_CLOSE (can auto-archive) |
| 1 | ANALYST_REVIEW |
| 2 | SENIOR_REVIEW |
| 3 | COMPLIANCE_REVIEW |
| 4 | STR_CONSIDERATION |
| 10+ | Error conditions |

---

## Files in This POC

```
poc/aml/
├── README.md                    # This file
├── demo.sh                      # Demo script
├── actimize_bundle.json         # Mapped CaseBundle (Actimize)
├── generic_csv_bundle.json      # Mapped CaseBundle (Generic CSV)
└── output/
    ├── ACT-2026-00789/          # Full output bundle
    │   ├── bundle.zip
    │   ├── cells.jsonl
    │   ├── manifest.json
    │   ├── pack.json
    │   ├── report.txt
    │   ├── report.sha256
    │   └── verification.json
    └── CSV-2026-001/            # Full output bundle
        └── ...
```

---

## Next Steps

1. **Custom Adapter**: Create adapter for your transaction monitoring system
2. **Pack Customization**: Adjust signal weights and thresholds for your risk appetite
3. **Integration**: Connect to case management system via bundle.zip output
4. **Legal Hold**: Use `--legal-hold` flag for litigation holds

---

## Contact

DecisionGraph - Deterministic Financial Crime Decisions

```
"Same input + same rules = same output. Always."
```
