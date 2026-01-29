# Generic CSV Adapter

This adapter maps generic CSV transaction exports to CaseBundle format.

## Target Audience

- Mid-market Canadian banks
- Credit unions
- In-house transaction monitoring systems
- Legacy systems with CSV exports

## Input Format

This adapter expects CSV data converted to JSON format. Use a standard
CSV-to-JSON converter before running the adapter.

### Step 1: Convert CSV to JSON

```bash
# Using Python
python -c "
import csv, json, sys
reader = csv.DictReader(open('transactions.csv'))
data = {'case': {'id': 'CASE-001'}, 'transactions': list(reader)}
json.dump(data, sys.stdout, indent=2)
" > input.json

# Or using jq + miller
mlr --csv --json cat transactions.csv | jq '{case: {id: "CASE-001"}, transactions: .}'
```

### Step 2: Run the adapter

```bash
dg map-case \
  --input input.json \
  --adapter adapters/fincrime/generic_csv/mapping.yaml \
  --out bundle.json
```

## Expected CSV Columns

### Transactions CSV

| Column | Description | Required |
|--------|-------------|----------|
| `TXN_ID` | Transaction identifier | Yes |
| `TXN_DATE` | Transaction date (ISO8601) | Yes |
| `AMOUNT` | Transaction amount | Yes |
| `CURRENCY` | Currency code (CAD, USD) | Yes |
| `DIR` | Direction (CR/DR or IN/OUT) | No |
| `CPTY_NAME` | Counterparty name | No |
| `CPTY_COUNTRY` | Counterparty country | No |
| `CHANNEL` | Payment channel | No |
| `NARRATIVE` | Transaction description | No |

### Customers CSV

| Column | Description | Required |
|--------|-------------|----------|
| `CUST_ID` | Customer identifier | Yes |
| `FIRST_NAME` | First name | Yes |
| `LAST_NAME` | Last name | No |
| `DOB` | Date of birth (YYYY-MM-DD) | No |
| `COUNTRY` | Country of residence | No |
| `PEP` | PEP indicator (Y/N) | No |
| `RISK` | Risk rating (1-5 or LOW/MEDIUM/HIGH) | No |

### Alerts CSV

| Column | Description | Required |
|--------|-------------|----------|
| `ALERT_ID` | Alert identifier | Yes |
| `ALERT_DATE` | Alert timestamp | Yes |
| `ALERT_TYPE` | Alert category | Yes |
| `RULE_ID` | Rule that triggered | No |
| `DESCRIPTION` | Alert description | No |

## Combined JSON Structure

After conversion, the JSON should have this structure:

```json
{
  "case": {
    "id": "CASE-2026-001",
    "jurisdiction": "CA",
    "customer_id": "CUST-001"
  },
  "customers": [
    {"CUST_ID": "...", "FIRST_NAME": "...", ...}
  ],
  "accounts": [
    {"ACCT_ID": "...", "ACCT_TYPE": "...", ...}
  ],
  "transactions": [
    {"TXN_ID": "...", "AMOUNT": "...", ...}
  ],
  "alerts": [
    {"ALERT_ID": "...", "ALERT_TYPE": "...", ...}
  ]
}
```

## Customization

Copy this adapter and modify the mappings to match your specific column names:

```bash
cp -r adapters/fincrime/generic_csv adapters/fincrime/my_bank
# Edit my_bank/mapping.yaml to match your columns
```

## Enum Normalization

The adapter includes transforms for common bank codes:

- Direction: `CR`/`DR`, `IN`/`OUT`, `C`/`D` → `inbound`/`outbound`
- Risk: `1-5`, `LOW/MEDIUM/HIGH` → normalized values
- PEP: `Y/N`, `YES/NO` → `foreign`/`none`
- Currency: `CAN`, `CAD$` → `CAD`
