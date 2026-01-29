# Adapter Mapping Specification v2.0

## Purpose

This document specifies the declarative adapter format used to transform
vendor-specific case exports into the canonical CaseBundle format.

**Design principle:** We don't integrate by code. We integrate by mapping.

---

## 1. Adapter Metadata

Every adapter MUST declare identification metadata:

```yaml
adapter:
  name: string          # Unique adapter identifier (e.g., actimize_tm_v1)
  vendor: string        # Vendor name (e.g., NICE Actimize)
  version: string       # Adapter version (semver: 1.0.0)
  input_format: string  # json | csv | xml
  description: string   # Human-readable description
```

### Adapter Hash

The system computes a deterministic `adapter_hash` (SHA256) from the
canonical JSON representation of the adapter YAML. This hash:

- Is recorded in every mapped bundle's metadata
- Enables audit trail: "what mapping was used?"
- Allows governance review before deployment

```json
{
  "provenance": {
    "adapter_name": "actimize_tm_v1",
    "adapter_version": "1.0.0",
    "adapter_hash": "a1b2c3d4..."
  }
}
```

---

## 2. Root Selectors

JSONPath expressions that locate data arrays in the source document:

```yaml
roots:
  case: $.alertCase                      # Case metadata object (required)
  customers: $.alertCase.involvedParties[*]
  accounts: $.alertCase.accounts[*]
  transactions: $.alertCase.transactions[*]
  alerts: $.alertCase.alerts[*]
  screenings: $.alertCase.screeningResults[*]
```

The `case` root is REQUIRED. All others are optional.

---

## 3. Field Mapping Rules

### Basic Mapping

Maps CaseBundle fields to source document paths:

```yaml
mappings:
  CaseMeta.case_id: $.case.id
  CaseMeta.jurisdiction: $.case.jurisdiction
  Individual.given_name: $.firstName
```

### Literal Values

Use `!literal` prefix for hardcoded values:

```yaml
CaseMeta.case_type: "!literal aml_alert"
CaseMeta.case_phase: "!literal analysis"
```

### Required Fields and Missing Value Handling

Each mapping MAY specify:

```yaml
field_options:
  CaseMeta.case_id:
    required: true
    on_missing: ERROR           # ERROR | DEFAULT | NULL | SKIP_RECORD

  TransactionEvent.purpose:
    required: false
    on_missing: DEFAULT
    default_value: "Not specified"

  Individual.middle_name:
    required: false
    on_missing: NULL            # Field omitted from output
```

| on_missing | Behavior |
|------------|----------|
| `ERROR` | Fail mapping with error (default for required fields) |
| `DEFAULT` | Use `default_value` from field_options or defaults section |
| `NULL` | Include field with null value |
| `SKIP_RECORD` | Skip entire record (transaction, alert, etc.) |

**Required fields for CaseMeta:**
- `case_id`
- `case_type`
- `jurisdiction`
- `primary_entity_id`

---

## 4. Value Transforms (Enum Normalization)

Banks use internal codes. Adapters normalize them:

```yaml
transforms:
  # Case type normalization
  case_type:
    "SAR": "aml_alert"
    "TM_ALERT": "aml_alert"
    "KYC_REVIEW": "kyc_refresh"
    "SANCTIONS_HIT": "sanctions_match"

  # Transaction direction
  direction:
    "CR": "inbound"
    "DR": "outbound"
    "C": "inbound"
    "D": "outbound"
    "CREDIT": "inbound"
    "DEBIT": "outbound"

  # Channel/payment method
  payment_method:
    "ABM": "atm"
    "ATM": "atm"
    "EFTCR": "eft"
    "EFTDR": "eft"
    "WIRE": "wire"
    "CASH": "cash"

  # Currency normalization
  currency:
    "CAD$": "CAD"
    "USD$": "USD"
    "CAN": "CAD"

  # PEP status
  pep_status:
    "Y": "foreign"
    "N": "none"
    "DOMESTIC": "domestic"
    "FOREIGN": "foreign"

  # Risk rating
  risk_rating:
    "1": "low"
    "2": "low"
    "3": "medium"
    "4": "high"
    "5": "high"
    "LOW": "low"
    "MEDIUM": "medium"
    "HIGH": "high"
```

Transforms are applied AFTER extraction, BEFORE output.

---

## 5. Default Values

Values for fields not present in source:

```yaml
defaults:
  CaseMeta.sensitivity: "confidential"
  CaseMeta.access_tags: ["aml", "fincrime"]
  Individual.sensitivity: "confidential"
  Account.sensitivity: "internal"
  TransactionEvent.sensitivity: "confidential"
```

Defaults are applied ONLY when:
- Field is not mapped, OR
- Mapped path returns null/missing AND `on_missing: DEFAULT`

---

## 6. Provenance Stamping

Every mapped bundle includes provenance metadata:

```yaml
provenance:
  enabled: true                    # default: true
  source_system: "NICE Actimize"   # from adapter.vendor
  include_file_hash: true          # SHA256 of input file
  include_timestamp: true          # ISO8601 ingestion timestamp
```

Output bundle metadata includes:

```json
{
  "provenance": {
    "adapter_name": "actimize_tm_v1",
    "adapter_version": "1.0.0",
    "adapter_hash": "a1b2c3d4e5f6...",
    "source_system": "NICE Actimize",
    "source_file_hash": "b2c3d4e5f6a1...",
    "ingested_at": "2026-01-29T16:30:00Z"
  }
}
```

This enables:
- Audit: "Where did this data come from?"
- Disputes: "What was the source file?"
- Governance: "Which adapter version?"

---

## 7. Error Handling

### Error Collection Mode

For batch processing, use error collection instead of fail-fast:

```bash
dg map-case \
  --input export.json \
  --adapter mapping.yaml \
  --out bundle.json \
  --max-errors 100 \
  --error-file mapping_errors.jsonl
```

Error file format (JSONL):

```json
{"record_type": "transaction", "record_index": 42, "field": "amount", "error": "required field missing", "source_path": "$.transactions[42].amount"}
{"record_type": "individual", "record_index": 0, "field": "date_of_birth", "error": "invalid date format", "source_path": "$.customers[0].dob", "raw_value": "1982/07/22"}
```

### Error Reporting

Mapping summary includes:

```json
{
  "mapping_summary": {
    "records_processed": 5000,
    "records_mapped": 4985,
    "records_skipped": 15,
    "errors": 15,
    "error_file": "mapping_errors.jsonl"
  }
}
```

---

## 8. Determinism Guarantees

Adapters MUST produce deterministic output:

1. **Same input + same adapter = same bundle bytes**
2. **Adapter hash is stable** (canonical JSON normalization)
3. **Record ordering preserved** (input order maintained)
4. **No timestamps in mapped data** (except provenance.ingested_at)

Verification:

```bash
# Map twice, compare hashes
dg map-case --input a.json --adapter m.yaml --out b1.json
dg map-case --input a.json --adapter m.yaml --out b2.json
sha256sum b1.json b2.json  # Must match
```

---

## 9. Security and PII

**Data stays local.** The mapper:

- Does NOT send data externally
- Does NOT log PII
- Does NOT cache sensitive fields
- Processes in-memory only

Adapters should document:

```yaml
security:
  pii_fields:
    - Individual.given_name
    - Individual.family_name
    - Individual.date_of_birth
    - Account.account_number
  redaction_in_errors: true    # Redact PII in error messages
```

---

## 10. JSONPath Reference

Supported expressions:

| Expression | Description | Example |
|------------|-------------|---------|
| `$.field` | Root-level field | `$.caseId` |
| `$.parent.child` | Nested field | `$.case.meta.id` |
| `$[0]` | Array index | `$.items[0]` |
| `$[*]` | All array elements | `$.transactions[*]` |
| `$[*].field` | Field from all elements | `$.transactions[*].amount` |

---

## 11. Creating a New Adapter

### Directory Structure

```
adapters/fincrime/{vendor}/
  mapping.yaml          # Adapter definition
  example_input.json    # Sample vendor export
  expected_bundle.json  # Expected CaseBundle output
  README.md             # Vendor-specific notes
```

### Validation Checklist

1. `dg validate-adapter --adapter mapping.yaml`
2. Map example input: `dg map-case --input example_input.json --adapter mapping.yaml --out test.json`
3. Compare to expected: `diff test.json expected_bundle.json`
4. Run through full pipeline: `dg run-case --case test.json --pack pack.yaml`
5. Verify bundle: `dg verify-bundle --bundle results/*/bundle.zip`

### Golden Test

```bash
# Deterministic mapping test
dg map-case --input example_input.json --adapter mapping.yaml --out /tmp/test.json
sha256sum /tmp/test.json expected_bundle.json
# Hashes must match
```

---

## 12. Supported Input Formats

### JSON (Primary)

Standard JSON with JSONPath selectors.

### CSV (Planned)

For CSV input, adapters use column selectors:

```yaml
adapter:
  input_format: csv
  csv_options:
    delimiter: ","
    quote_char: '"'
    has_header: true
    encoding: utf-8

roots:
  transactions: $rows    # Each row is a record

mappings:
  TransactionEvent.id: $col.TRANSACTION_ID
  TransactionEvent.amount: $col.AMOUNT
  TransactionEvent.currency: $col.CURRENCY
```

---

## 13. Versioning

- Adapter versions use semver (MAJOR.MINOR.PATCH)
- **MAJOR**: Breaking changes to output structure
- **MINOR**: New optional fields, new transforms
- **PATCH**: Bug fixes, documentation

Banks should pin adapter versions in production.

---

## 14. Compliance Statement

This adapter specification ensures:

1. **Traceability**: Every field maps to a documented source
2. **Reproducibility**: Same input always produces same output
3. **Auditability**: Adapter hash and provenance recorded
4. **Governance**: Adapters can be reviewed before deployment
5. **Data locality**: No external transmission of case data

---

## Appendix A: CaseBundle Target Fields

### CaseMeta
| Field | Required | Description |
|-------|----------|-------------|
| case_id | Yes | Unique case identifier |
| case_type | Yes | aml_alert, kyc_refresh, etc. |
| case_phase | No | analysis, decision_pending, etc. |
| jurisdiction | Yes | Two-letter country code |
| created_at | No | ISO8601 timestamp |
| primary_entity_type | Yes | individual, organization |
| primary_entity_id | Yes | ID of primary subject |
| status | No | open, closed, etc. |
| priority | No | low, medium, high, critical |
| sensitivity | No | internal, confidential, restricted |

### Individual
| Field | Required | Description |
|-------|----------|-------------|
| id | Yes | Unique identifier |
| given_name | Yes | First name |
| family_name | No | Last name |
| date_of_birth | No | YYYY-MM-DD |
| nationality | No | Two-letter country code |
| pep_status | No | none, domestic, foreign, hio |
| risk_rating | No | low, medium, high |

### TransactionEvent
| Field | Required | Description |
|-------|----------|-------------|
| id | Yes | Transaction identifier |
| timestamp | Yes | ISO8601 timestamp |
| amount | Yes | Decimal amount |
| currency | Yes | Three-letter currency code |
| direction | No | inbound, outbound |
| counterparty_name | No | Name of other party |
| counterparty_country | No | Two-letter country code |
| payment_method | No | wire, cash, eft, etc. |

### AlertEvent
| Field | Required | Description |
|-------|----------|-------------|
| id | Yes | Alert identifier |
| timestamp | Yes | ISO8601 timestamp |
| alert_type | Yes | Alert category |
| rule_id | No | Rule that triggered alert |
| description | No | Alert description |

---

## Appendix B: Example Adapter

See `adapters/fincrime/actimize/mapping.yaml` for a complete example.
