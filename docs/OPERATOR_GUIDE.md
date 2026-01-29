# DecisionGraph Operator Guide

## Overview

DecisionGraph is a deterministic reasoning engine for Financial Crime compliance.
It transforms case data into auditor-ready report bundles with verifiable hashes and policy citations.

**One command. Full audit trail. Verifiable output.**

```bash
./dg run-case --case bundle.json --pack packs/fincrime_canada.yaml --out results/
```

---

## Installation

```bash
# Clone repository
git clone <repo-url>
cd decisiongraph

# Verify installation
./dg --help
```

**Requirements:**
- Python 3.10+
- No external dependencies for core functionality

---

## Quick Start

### 1. Validate Your Pack

```bash
./dg validate-pack --pack packs/fincrime_canada.yaml
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

### 4. Verify Bundle Integrity

```bash
./dg verify-bundle --bundle results/AML-2026-00142/bundle.zip
```

---

## Exit Codes

Exit codes are deterministic and designed for pipeline integration:

| Code | Name | Description |
|------|------|-------------|
| 0 | PASS | Case processed, auto-archive permitted |
| 2 | REVIEW_REQUIRED | Analyst review required |
| 3 | ESCALATE | Senior/compliance escalation required |
| 4 | BLOCK | STR consideration, case blocked |
| 10 | INPUT_INVALID | Invalid input files |
| 11 | PACK_ERROR | Pack validation/loading failed |
| 12 | VERIFY_FAIL | Verification failed (integrity, determinism) |
| 20 | INTERNAL_ERROR | Unexpected internal error |

**Pipeline example:**
```bash
./dg run-case --case case.json --pack pack.yaml --out out/
case $? in
    0) echo "Auto-close permitted" ;;
    2) echo "Route to analyst queue" ;;
    3) echo "Escalate to senior/compliance" ;;
    4) echo "STR consideration - route to BSA officer" ;;
    *) echo "Error - check logs" ;;
esac
```

---

## Commands

### run-case

Process a case through the rules engine and produce bank-ready deliverables.

```bash
./dg run-case \
  --case <path>       # Case bundle JSON file (required)
  --pack <path>       # Pack YAML file (required)
  --out <dir>         # Output directory (default: ./out)
  --strict            # Strict mode: non-PASS cases marked NOT APPROVED
  --sign <keyfile>    # Sign manifest with key file
  --no-cells          # Skip cells.jsonl to reduce bundle size
```

**Strict Mode:**
When `--strict` is enabled, any case that doesn't receive PASS verdict is explicitly marked as "NOT APPROVED" in the report. Use this for automated processing environments where human review is required for non-PASS outcomes.

**Signing:**
The `--sign` option creates a `manifest.sig` file containing an HMAC or Ed25519 signature of the manifest. Provide a key file (any format) for signing.

### verify-bundle

Verify an existing bundle for integrity (auditor mode).

```bash
./dg verify-bundle \
  --bundle <path>     # Bundle zip file (required)
  --key <path>        # Public key for signature verification (optional)
```

**Verification checks:**
- Bundle extraction
- Report hash matches `report.sha256`
- Manifest structure complete
- Manifest report_hash matches computed hash
- All manifest cell_ids exist in cells.jsonl
- Signature valid (if present and key provided)
- Pack hash format valid

### validate-pack

Validate a pack YAML file.

```bash
./dg validate-pack --pack <path>
```

### validate-case

Validate a case bundle JSON file.

```bash
./dg validate-case --case <path>
```

### pack-info

Display detailed pack information.

```bash
./dg pack-info --pack <path>
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
  "individuals": [...],
  "organizations": [...],
  "accounts": [...],
  "relationships": [...],
  "evidence": [...],
  "events": [...],
  "assertions": [...]
}
```

See `examples/sample_aml_case.json` for a complete example.

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

```
out/CASE_ID/
├── report.txt          # Deterministic report (human-readable)
├── report.sha256       # SHA256 hash of report bytes
├── manifest.json       # Report manifest with all cell IDs
├── pack.json           # Pack metadata used for this run
├── verification.json   # All verification checks (PASS/FAIL)
├── cells.jsonl         # All cells in deterministic order
├── manifest.sig        # Optional signature (with --sign)
└── bundle.zip          # Everything zipped for audit handoff
```

### Cell Ordering (Deterministic)

The `cells.jsonl` file contains cells in this stable order:

1. **Case cells** (from case_loader)
   - CaseMeta → Phase → Entities → Accounts → Relationships → Evidence → Events → Assertions
2. **Policy cells** (sorted by ref_id)
3. **Signal cells** (sorted by code)
4. **Mitigation cells** (sorted by code)
5. **Score cell**
6. **Verdict cell**

This ordering enables reproducible diffs and investigations.

### manifest.json

```json
{
  "case_id": "AML-2026-00142",
  "report_hash": "a1b2c3d4e5f6...",
  "graph_id": "graph:uuid-here",
  "chain_length": 65,
  "case_cells": 15,
  "policy_cells": 22,
  "derived_cells": 28,
  "total_cells": 65,
  "cell_ids": ["cell-id-1", "cell-id-2", ...],
  "signals_fired": 20,
  "mitigations_applied": 5,
  "verdict": "STR_CONSIDERATION",
  "auto_archive_permitted": false,
  "strict_mode": false,
  "approved": false,
  "score": {
    "inherent_score": "12.75",
    "mitigation_sum": "-1.6",
    "residual_score": "11.15",
    "threshold_gate": "STR_CONSIDERATION"
  },
  "created_at": "2026-01-29T16:00:00.000Z"
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
```

### Using verify-bundle

```bash
./dg verify-bundle --bundle out/AML-2026-00142/bundle.zip
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
    computed_hash = hashlib.sha256(f.read()).hexdigest()

# Verify
assert computed_hash == manifest['report_hash']
print("Report integrity verified")
```

---

## Threshold Gates and Verdicts

| Gate | Max Score | Exit Code | Typical Action |
|------|-----------|-----------|----------------|
| AUTO_CLOSE | 0.50 | 0 | Automated closure permitted |
| ANALYST_REVIEW | 2.00 | 2 | Standard analyst review |
| SENIOR_REVIEW | 4.00 | 3 | Senior analyst required |
| COMPLIANCE_REVIEW | 6.00 | 3 | Compliance officer review |
| STR_CONSIDERATION | 999.00 | 4 | STR filing consideration |

**Scoring Formula:**
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
        --out "results/" \
        --strict

    exit_code=$?
    echo "$case_id: exit code $exit_code" >> batch_results.log
done
```

### CI/CD Integration

```yaml
# .github/workflows/run-cases.yml
name: Process Cases
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
      - name: Verify bundle
        run: ./dg verify-bundle --bundle results/AML-2026-00142/bundle.zip
      - name: Check exit code
        run: |
          if [ $? -eq 0 ]; then
            echo "Case PASS"
          else
            echo "Case requires review"
          fi
```

### Export to Case System

```python
import json

# Read outputs
with open('out/CASE_ID/manifest.json') as f:
    manifest = json.load(f)
with open('out/CASE_ID/pack.json') as f:
    pack = json.load(f)

# Update your case management system
case_update = {
    "decision_graph_verdict": manifest["verdict"],
    "decision_graph_score": manifest["score"]["residual_score"],
    "decision_graph_report_hash": manifest["report_hash"],
    "decision_graph_pack_hash": pack["pack_hash"],
    "decision_graph_approved": manifest["approved"],
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

### Verification Failures

```
[FAIL] report_hash
```
The report.txt file was modified after generation. Re-run the case.

```
[FAIL] cells_coverage
```
Some cells in manifest.json are missing from cells.jsonl. Bundle may be corrupted.

---

## Security Considerations

1. **Pack Immutability**: Never modify a pack after deployment. Create a new version instead.
2. **Report Hashing**: Always verify report hashes before relying on verdicts.
3. **Signing**: Use `--sign` with a secure key for production deployments.
4. **Strict Mode**: Enable `--strict` for automated processing to ensure human review.
5. **Audit Trail**: The `cells.jsonl` contains the complete cryptographic audit trail.
6. **Sensitive Data**: The bundle may contain PII. Protect `bundle.zip` accordingly.

---

## What to Tell Auditors

> "Every case decision is backed by a cryptographic chain of evidence. The report hash proves the report hasn't been tampered with. The pack hash proves which rules were applied. The cells file contains every fact, signal, mitigation, and judgment that went into the decision. You can re-run the same case bundle with the same pack and get byte-identical output."

---

## Support

- Documentation: See `docs/` directory
- Issues: https://github.com/your-org/decisiongraph/issues
- Pack Development: See `packs/README.md`

---

*DecisionGraph - Deterministic Reasoning for Financial Crime Compliance*
