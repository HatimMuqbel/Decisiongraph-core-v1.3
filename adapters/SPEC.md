# Adapter Mapping Schema v1

## Overview

Adapters transform vendor-specific case exports into the canonical CaseBundle format.
They are **pure mappings** with no business logic, no rules, and no scoring.

One question only: *"How do I turn your export into our CaseBundle?"*

## Design Principles

1. **Declarative** - YAML-based, no code
2. **JSONPath** - Standard syntax banks already understand
3. **Deterministic** - Same input always produces same output
4. **No logic** - Pure field mapping, no transformations
5. **Fail loudly** - Missing required fields cause hard errors

## Schema Structure

```yaml
# ============================================================================
# ADAPTER METADATA
# ============================================================================
adapter:
  name: string          # Unique adapter identifier (e.g., actimize_tm_v1)
  vendor: string        # Vendor name (e.g., NICE Actimize)
  version: string       # Adapter version (semver: 1.0.0)
  input_format: string  # json | csv | xml
  description: string   # Human-readable description

# ============================================================================
# ROOT SELECTORS
# ============================================================================
# JSONPath expressions to locate data arrays in the source document.
# These define where to find each entity type.

roots:
  case: string          # JSONPath to case metadata object
  customers: string     # JSONPath to customer array
  accounts: string      # JSONPath to accounts array
  transactions: string  # JSONPath to transactions array
  alerts: string        # JSONPath to alerts array
  screenings: string    # JSONPath to screenings array (optional)
  evidence: string      # JSONPath to evidence array (optional)

# ============================================================================
# FIELD MAPPINGS
# ============================================================================
# Maps CaseBundle fields to source document paths.
# Format: CaseBundle.path: JSONPath
#
# Supported CaseBundle targets:
#   CaseMeta.*
#   Individual.*
#   Organization.*
#   Account.*
#   Relationship.*
#   TransactionEvent.*
#   AlertEvent.*
#   ScreeningEvent.*
#   EvidenceItem.*
#   Assertion.*

mappings:
  # Case metadata
  CaseMeta.case_id: string
  CaseMeta.case_type: string | literal
  CaseMeta.case_phase: string | literal
  CaseMeta.jurisdiction: string | literal
  CaseMeta.created_at: string
  CaseMeta.primary_entity_type: string | literal
  CaseMeta.primary_entity_id: string
  CaseMeta.priority: string | literal
  CaseMeta.sensitivity: string | literal

  # Individuals (from customers root)
  Individual.id: string
  Individual.given_name: string
  Individual.family_name: string
  Individual.date_of_birth: string
  Individual.nationality: string
  Individual.country_of_residence: string
  Individual.pep_status: string | literal
  Individual.risk_rating: string | literal

  # Accounts (from accounts root)
  Account.id: string
  Account.account_number: string
  Account.account_type: string
  Account.currency: string
  Account.status: string | literal

  # Transactions (from transactions root)
  TransactionEvent.id: string
  TransactionEvent.timestamp: string
  TransactionEvent.amount: string
  TransactionEvent.currency: string
  TransactionEvent.direction: string
  TransactionEvent.counterparty_name: string
  TransactionEvent.counterparty_country: string
  TransactionEvent.payment_method: string | literal

  # Alerts (from alerts root)
  AlertEvent.id: string
  AlertEvent.timestamp: string
  AlertEvent.alert_type: string
  AlertEvent.rule_id: string
  AlertEvent.description: string

  # Screenings (from screenings root)
  ScreeningEvent.id: string
  ScreeningEvent.timestamp: string
  ScreeningEvent.screening_type: string
  ScreeningEvent.vendor: string
  ScreeningEvent.disposition: string

# ============================================================================
# VALUE TRANSFORMS (optional, limited)
# ============================================================================
# Simple value mappings for enum normalization.
# No complex logic allowed.

transforms:
  # Map source values to CaseBundle enum values
  case_type:
    "SAR": "aml_alert"
    "TM_ALERT": "aml_alert"
    "KYC": "kyc_refresh"
    "SANCTIONS": "sanctions_match"

  direction:
    "CR": "inbound"
    "DR": "outbound"
    "CREDIT": "inbound"
    "DEBIT": "outbound"

  pep_status:
    "Y": "foreign"
    "N": "none"
    "D": "domestic"

# ============================================================================
# DEFAULTS (optional)
# ============================================================================
# Default values for fields not present in source.

defaults:
  CaseMeta.sensitivity: "confidential"
  CaseMeta.access_tags: ["aml"]
  Individual.sensitivity: "confidential"
  Account.sensitivity: "internal"
```

## JSONPath Syntax

Standard JSONPath expressions:

| Expression | Description |
|------------|-------------|
| `$.field` | Root-level field |
| `$.parent.child` | Nested field |
| `$[*]` | All array elements |
| `$.array[0]` | First array element |
| `$.array[*].field` | Field from all array elements |

## Literal Values

Use `!literal` prefix for hardcoded values:

```yaml
CaseMeta.case_type: "!literal aml_alert"
CaseMeta.sensitivity: "!literal confidential"
```

## Required Fields

These fields MUST be mapped or defaulted:

### CaseMeta (required)
- `case_id`
- `case_type`
- `case_phase`
- `jurisdiction`
- `primary_entity_type`
- `primary_entity_id`

### Individual (if present)
- `id`
- `given_name` OR `full_name`

### Account (if present)
- `id`
- `account_type`

### TransactionEvent (if present)
- `id`
- `timestamp`
- `amount`
- `currency`

### AlertEvent (if present)
- `id`
- `timestamp`
- `alert_type`

## Validation

The mapper validates:

1. **Adapter schema** - Required fields present
2. **JSONPath syntax** - Valid expressions
3. **Required mappings** - All required CaseBundle fields mapped
4. **Transform coverage** - Transform values match expected enums
5. **Output completeness** - Mapped bundle passes CaseBundle validation

## CLI Usage

```bash
# Map a vendor export to CaseBundle
dg map-case \
  --input actimize_export.json \
  --adapter adapters/fincrime/actimize/mapping.yaml \
  --out bundle.json

# Validate an adapter without running it
dg validate-adapter --adapter adapters/fincrime/actimize/mapping.yaml
```

## Creating a New Adapter

1. Create directory: `adapters/fincrime/{vendor}/`
2. Create `mapping.yaml` following this spec
3. Add `example_input.json` with sample vendor export
4. Add `expected_bundle.json` with expected output
5. Run validation: `dg validate-adapter --adapter mapping.yaml`
6. Test end-to-end: `dg map-case --input example_input.json --adapter mapping.yaml --out test.json`

## Testing

Each adapter should have:

```
adapters/fincrime/{vendor}/
  mapping.yaml          # The adapter definition
  example_input.json    # Sample vendor export
  expected_bundle.json  # Expected CaseBundle output
```

Golden test:
1. Map `example_input.json` using `mapping.yaml`
2. Compare output to `expected_bundle.json`
3. Assert byte-identical match

## Versioning

- Adapter versions use semver
- Breaking changes require major version bump
- New optional fields are minor version
- Bug fixes are patch version

## What Adapters Do NOT Do

- No scoring
- No risk calculation
- No rule evaluation
- No policy application
- No business logic
- No conditional mapping based on values
- No data enrichment
- No external lookups

All intelligence happens AFTER the adapter, in the rules engine.
