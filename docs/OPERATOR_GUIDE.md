# DecisionGraph Operator Guide

## Overview

DecisionGraph is a deterministic reasoning engine for Financial Crime compliance.
It transforms case data into auditor-ready report bundles with verifiable hashes and policy citations.

**One command. Full audit trail. Verifiable output.**

```bash
./dg run-case --case bundle.json --pack packs/fincrime_canada.yaml --out results/
```

---

## Quick Start

### 1. Validate Your Pack

```bash
./dg validate-pack --pack packs/fincrime_canada.yaml
```

Expected output:
```
[OK] Pack is valid!
Pack ID: fincrime_canada_v1
Version: 1.0.0
Signals: 22
Mitigations: 16
```

### 2. Validate Your Case Bundle

```bash
./dg validate-case --case examples/sample_aml_case.json
```

### 3. Run a Case

```bash
./dg run-case \
  --case examples/sample_aml_case.json \
  --pack packs/fincrime_canada.yaml \
  --out results/
```

---

## Input Contract

### Case Bundle JSON Schema

Export this structure from your KYC/AML case management system:

```json
{
  "meta": {
    "id": "AML-2026-00142",
    "case_type": "aml_alert",
    "case_phase": "analysis",
    "created_at": "2026-01-29T10:30:00Z",
    "jurisdiction": "CA",
    "primary_entity_type": "individual",
    "primary_entity_id": "IND-001",
    "status": "open",
    "priority": "high",
    "sensitivity": "confidential",
    "access_tags": ["aml", "fincrime"]
  },
  "individuals": [
    {
      "id": "IND-001",
      "given_name": "John",
      "family_name": "Smith",
      "date_of_birth": "1975-03-15",
      "nationality": "CA",
      "pep_status": "none",
      "risk_rating": "medium"
    }
  ],
  "organizations": [],
  "accounts": [
    {
      "id": "ACC-001",
      "account_number": "****4567",
      "account_type": "checking",
      "currency": "CAD",
      "status": "active"
    }
  ],
  "relationships": [
    {
      "id": "REL-001",
      "relationship_type": "account_holder",
      "from_entity_type": "individual",
      "from_entity_id": "IND-001",
      "to_entity_type": "individual",
      "to_entity_id": "ACC-001"
    }
  ],
  "evidence": [
    {
      "id": "EV-001",
      "evidence_type": "transaction_records",
      "description": "Wire transfer records for January 2026",
      "collected_date": "2026-01-29",
      "source": "core_banking",
      "verified": true
    }
  ],
  "events": [
    {
      "id": "TXN-001",
      "event_type": "transaction",
      "timestamp": "2026-01-15T14:30:00Z",
      "description": "International wire transfer",
      "amount": "25000.00",
      "currency": "CAD",
      "direction": "outbound",
      "counterparty_name": "Global Trading Ltd",
      "counterparty_country": "KY",
      "payment_method": "wire"
    },
    {
      "id": "ALERT-001",
      "event_type": "alert",
      "timestamp": "2026-01-28T08:00:00Z",
      "description": "Potential structuring activity detected",
      "alert_type": "structuring",
      "rule_id": "STRUCT-001"
    }
  ],
  "assertions": [
    {
      "id": "ASSERT-001",
      "subject_type": "individual",
      "subject_id": "IND-001",
      "predicate": "relationship_tenure",
      "value": "7",
      "asserted_at": "2026-01-28T08:10:00Z",
      "asserted_by": "system"
    }
  ]
}
```

### Case Types

| Type | Description |
|------|-------------|
| `kyc_onboarding` | New customer intake |
| `kyc_refresh` | Periodic review |
| `aml_alert` | Transaction monitoring alert |
| `edd_review` | Enhanced due diligence |
| `sanctions_match` | Sanctions screening hit |

### Case Phases

| Phase | Description |
|-------|-------------|
| `intake` | Case opened, awaiting triage |
| `evidence_gathering` | Collecting documents/data |
| `analysis` | Analyst review in progress |
| `decision_pending` | Awaiting senior review |
| `decided` | Decision made |
| `closed` | Case complete |
| `legal_hold` | Frozen for legal/regulatory |

---

## Output Bundle Structure

After running `dg run-case`, your output directory contains:

```
out/CASE_ID/
├── report.txt          # Deterministic report (human-readable)
├── report.sha256       # SHA256 hash of report bytes
├── manifest.json       # Report manifest with all cell IDs
├── pack.json           # Pack metadata used for this run
├── verification.json   # All verification checks (PASS/FAIL)
├── cells.jsonl         # All cells produced (JSON Lines)
└── bundle.zip          # Everything zipped for audit handoff
```

### report.txt

Deterministic, human-readable case report containing:
- Case metadata
- Verdict and risk score
- All signals fired with severity
- All mitigations applied with weights
- Entity and transaction summary
- Chain integrity status
- Policy references cited

### report.sha256

Standard checksum file for verification:
```
a1b2c3d4e5f6...  report.txt
```

Verify with:
```bash
cd out/CASE_ID && sha256sum -c report.sha256
```

### manifest.json

Machine-readable report manifest:
```json
{
  "case_id": "AML-2026-00142",
  "report_hash": "a1b2c3d4e5f6...",
  "graph_id": "graph:uuid-here",
  "chain_length": 43,
  "signals_fired": 20,
  "mitigations_applied": 5,
  "verdict": "STR_CONSIDERATION",
  "score": {
    "inherent_score": "12.75",
    "mitigation_sum": "-1.6",
    "residual_score": "11.15",
    "threshold_gate": "STR_CONSIDERATION"
  },
  "cell_ids": ["cell-id-1", "cell-id-2", ...]
}
```

### pack.json

Pack metadata for audit trail:
```json
{
  "pack_id": "fincrime_canada_v1",
  "name": "Canadian Financial Crime Pack",
  "version": "1.0.0",
  "pack_hash": "390c23d3d389fb48...",
  "domain": "financial_crime",
  "jurisdiction": "CA",
  "signals_count": 22,
  "mitigations_count": 16,
  "regulatory_framework": {
    "primary_legislation": "PCMLTFA",
    "regulator": "FINTRAC"
  }
}
```

### verification.json

All verification checks:
```json
{
  "case_id": "AML-2026-00142",
  "overall": "PASS",
  "checks": [
    {"name": "report_hash", "status": "PASS", "hash": "..."},
    {"name": "chain_integrity", "status": "PASS"},
    {"name": "determinism", "status": "PASS"},
    {"name": "policy_coverage", "status": "PASS"},
    {"name": "gate_consistency", "status": "PASS"}
  ]
}
```

---

## Verifying Report Hashes

### Command Line

```bash
# Navigate to case output
cd out/AML-2026-00142

# Verify report hash
sha256sum -c report.sha256
# Expected: report.txt: OK

# Or compute manually
sha256sum report.txt
# Compare with content of report.sha256
```

### Programmatic

```python
import hashlib
import json

# Read manifest
with open('out/CASE_ID/manifest.json') as f:
    manifest = json.load(f)

# Read and hash report
with open('out/CASE_ID/report.txt', 'rb') as f:
    report_bytes = f.read()
    computed_hash = hashlib.sha256(report_bytes).hexdigest()

# Verify
assert computed_hash == manifest['report_hash']
print("Report integrity verified")
```

---

## Threshold Gates and Verdicts

The pack defines threshold gates that map scores to verdicts:

| Gate | Max Score | Typical Action |
|------|-----------|----------------|
| AUTO_CLOSE | 0.50 | Automated closure permitted |
| ANALYST_REVIEW | 2.00 | Standard analyst review |
| SENIOR_REVIEW | 4.00 | Senior analyst required |
| COMPLIANCE_REVIEW | 6.00 | Compliance officer review |
| STR_CONSIDERATION | 999.00 | STR filing consideration |

**Formula:**
```
residual_score = inherent_score + sum(mitigation_weights)
```

Mitigations have **negative weights** (reduce risk):
- `MF_ESTABLISHED_RELATIONSHIP`: -0.25
- `MF_SOW_VERIFIED`: -0.35
- `MF_SCREEN_FALSE_POSITIVE`: -0.50

---

## Integration Examples

### Batch Processing

```bash
#!/bin/bash
for case_file in cases/*.json; do
    case_id=$(basename "$case_file" .json)
    ./dg run-case \
        --case "$case_file" \
        --pack packs/fincrime_canada.yaml \
        --out "results/$case_id"
done
```

### CI/CD Integration

```yaml
# .github/workflows/run-cases.yml
name: Run Cases
on: [push]
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run test case
        run: |
          ./dg run-case \
            --case examples/sample_aml_case.json \
            --pack packs/fincrime_canada.yaml \
            --out results/
      - name: Verify output
        run: |
          cd results/AML-2026-00142
          sha256sum -c report.sha256
```

### Export to Your Case System

```python
import json

# Read manifest
with open('out/CASE_ID/manifest.json') as f:
    manifest = json.load(f)

# Update your case management system
case_update = {
    "decision_graph_verdict": manifest["verdict"],
    "decision_graph_score": manifest["score"]["residual_score"],
    "decision_graph_report_hash": manifest["report_hash"],
    "decision_graph_pack_hash": pack_meta["pack_hash"],
}

your_case_system.update(case_id, case_update)
```

---

## Troubleshooting

### Pack Validation Errors

```
[ERROR] Validation failed: float not allowed
```
All weights must be quoted strings: `"-0.25"` not `-0.25`

```
[ERROR] Unknown signal reference: NONEXISTENT
```
Mitigations reference undefined signals. Check `applies_to` arrays.

### Case Validation Errors

```
[WARN] Primary entity not found
```
The `primary_entity_id` in meta doesn't match any entity in the bundle.

### Chain Integrity Errors

```
[FAIL] chain_integrity
```
Internal error - cells don't chain correctly. Report this issue.

---

## Security Considerations

1. **Pack Immutability**: Never modify a pack after deployment. Create a new version instead.
2. **Report Hashing**: Always verify report hashes before relying on verdicts.
3. **Audit Trail**: The `cells.jsonl` contains the complete cryptographic audit trail.
4. **Sensitive Data**: The bundle may contain PII. Protect `bundle.zip` accordingly.

---

## Support

- Documentation: See `docs/` directory
- Issues: https://github.com/your-org/decisiongraph/issues
- Pack Development: See `packs/README.md`

---

*DecisionGraph - Deterministic Reasoning for Financial Crime Compliance*
