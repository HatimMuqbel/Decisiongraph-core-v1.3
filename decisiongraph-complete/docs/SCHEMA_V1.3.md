# DecisionGraph Schema v1.3

## Cell Types

```python
class CellType(str, Enum):
    GENESIS = "genesis"
    FACT = "fact"
    RULE = "rule"
    DECISION = "decision"
    EVIDENCE = "evidence"
    OVERRIDE = "override"
    ACCESS_RULE = "access_rule"
    BRIDGE_RULE = "bridge_rule"
    NAMESPACE_DEF = "namespace_def"
```

## Source Quality

```python
class SourceQuality(str, Enum):
    VERIFIED = "verified"       # Confirmed from authoritative source
    SELF_REPORTED = "self_reported"  # User-provided, not verified
    INFERRED = "inferred"       # Derived from other facts
```

## Complete Cell Schema

```json
{
  "cell_id": "string (SHA256 hex, 64 chars)",
  
  "header": {
    "version": "string (e.g., '1.3')",
    "graph_id": "string (format: 'graph:<uuid-v4>')",
    "cell_type": "string (CellType enum value)",
    "system_time": "string (ISO 8601 UTC, must end with 'Z')",
    "prev_cell_hash": "string (SHA256 hex, 64 chars or NULL_HASH for Genesis)"
  },
  
  "fact": {
    "namespace": "string (lowercase, dots for hierarchy, e.g., 'corp.hr.compensation')",
    "subject": "string (entity identifier, e.g., 'employee:jane_doe')",
    "predicate": "string (relationship, e.g., 'has_salary')",
    "object": "string (value or entity)",
    "confidence": "number (0.0 to 1.0)",
    "source_quality": "string (SourceQuality enum value)",
    "valid_from": "string (ISO 8601 UTC) | null",
    "valid_to": "string (ISO 8601 UTC) | null (null = forever)"
  },
  
  "logic_anchor": {
    "rule_id": "string (rule identifier, e.g., 'policy:salary_bands_v1')",
    "rule_logic_hash": "string (SHA256 hex of canonicalized rule content)",
    "interpreter": "string (optional, e.g., 'datalog:v2', 'dmn:1.3')"
  },
  
  "evidence": [
    {
      "type": "string (e.g., 'document_blob', 'api_response', 'approval')",
      "cid": "string (content ID, optional)",
      "source": "string (optional)",
      "payload_hash": "string (optional)",
      "description": "string (optional)"
    }
  ],
  
  "proof": {
    "signer_id": "string (who signed, e.g., 'role:hr_manager')",
    "signer_key_id": "string (key reference, optional)",
    "signature": "string (cryptographic signature, optional in bootstrap mode)",
    "merkle_root": "string (optional)",
    "signature_required": "boolean (default false)"
  }
}
```

## cell_id Computation (Logic Seal)

```python
def compute_cell_id(cell) -> str:
    seal_string = (
        cell.header.version +
        cell.header.graph_id +
        cell.header.cell_type.value +
        cell.header.system_time +
        cell.header.prev_cell_hash +
        cell.fact.namespace +
        cell.fact.subject +
        cell.fact.predicate +
        str(cell.fact.object) +
        cell.logic_anchor.rule_id +
        cell.logic_anchor.rule_logic_hash
    )
    return hashlib.sha256(seal_string.encode('utf-8')).hexdigest()
```

## Validation Rules

### Namespace

```python
# Pattern: lowercase letter, then alphanumeric/underscore, dots for hierarchy
NAMESPACE_PATTERN = r'^[a-z][a-z0-9_]{0,63}(\.[a-z][a-z0-9_]{0,63})*$'

# Root namespace (no dots)
ROOT_NAMESPACE_PATTERN = r'^[a-z][a-z0-9_]{1,63}$'
```

Valid: `corp`, `corp.hr`, `acme.sales.discounts`, `my_company.dept_1`
Invalid: ``, `.corp`, `corp.`, `Corp.HR`, `123corp`, `corp/hr`

### graph_id

```python
# Format: graph:<uuid-v4>
GRAPH_ID_PATTERN = r'^graph:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
```

Valid: `graph:a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d`
Invalid: `a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d` (missing prefix)

### Timestamp

```python
# ISO 8601 with UTC timezone (must end with 'Z')
ISO_TIMESTAMP_PATTERN = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$'
```

Valid: `2026-01-27T12:00:00Z`, `2026-01-27T12:00:00.123Z`
Invalid: `2026-01-27T12:00:00`, `2026-01-27T12:00:00+00:00`

### Confidence

- Range: 0.0 to 1.0
- If confidence = 1.0, source_quality must be "verified"

## NULL_HASH

The special hash for Genesis:

```python
NULL_HASH = "0" * 64  # 64 zeros
```

Only Genesis may have `prev_cell_hash = NULL_HASH`.

## Constants

```python
SCHEMA_VERSION = "1.3"
DEFAULT_ROOT_NAMESPACE = "corp"
```

## Examples

### Genesis Cell

```json
{
  "cell_id": "a1b2c3...",
  "header": {
    "version": "1.3",
    "graph_id": "graph:12345678-1234-4123-8123-123456789abc",
    "cell_type": "genesis",
    "system_time": "2026-01-27T12:00:00Z",
    "prev_cell_hash": "0000000000000000000000000000000000000000000000000000000000000000"
  },
  "fact": {
    "namespace": "acme",
    "subject": "graph:root",
    "predicate": "instance_of",
    "object": "AcmeCorp_DecisionGraph",
    "confidence": 1.0,
    "source_quality": "verified",
    "valid_from": "2026-01-27T12:00:00Z",
    "valid_to": null
  },
  "logic_anchor": {
    "rule_id": "system:genesis_boot_v1.3",
    "rule_logic_hash": "abc123...",
    "interpreter": "system:v1.3"
  },
  "evidence": [],
  "proof": {
    "signer_id": "system:genesis",
    "signature_required": false
  }
}
```

### Fact Cell

```json
{
  "cell_id": "def456...",
  "header": {
    "version": "1.3",
    "graph_id": "graph:12345678-1234-4123-8123-123456789abc",
    "cell_type": "fact",
    "system_time": "2026-01-27T12:01:00Z",
    "prev_cell_hash": "a1b2c3..."
  },
  "fact": {
    "namespace": "acme.hr.compensation",
    "subject": "employee:jane_doe",
    "predicate": "has_salary",
    "object": "150000",
    "confidence": 1.0,
    "source_quality": "verified",
    "valid_from": "2026-01-01T00:00:00Z",
    "valid_to": null
  },
  "logic_anchor": {
    "rule_id": "source:hris_export",
    "rule_logic_hash": "xyz789...",
    "interpreter": null
  },
  "evidence": [
    {
      "type": "document_blob",
      "cid": "sha256:...",
      "description": "HRIS payroll export"
    }
  ],
  "proof": {
    "signer_id": "role:hr_manager"
  }
}
```

### Bridge Rule Cell

```json
{
  "cell_id": "ghi789...",
  "header": {
    "version": "1.3",
    "graph_id": "graph:12345678-1234-4123-8123-123456789abc",
    "cell_type": "bridge_rule",
    "system_time": "2026-01-27T12:02:00Z",
    "prev_cell_hash": "def456..."
  },
  "fact": {
    "namespace": "system.bridges",
    "subject": "acme.sales",
    "predicate": "can_query",
    "object": "acme.hr.performance",
    "confidence": 1.0,
    "source_quality": "verified",
    "valid_from": "2026-01-27T12:02:00Z",
    "valid_to": null
  },
  "logic_anchor": {
    "rule_id": "system:bridge_creation",
    "rule_logic_hash": "...",
    "interpreter": null
  },
  "evidence": [
    {
      "type": "approval",
      "description": "Source owner approval: role:vp_sales",
      "payload_hash": "sig_vp_sales_..."
    },
    {
      "type": "approval",
      "description": "Target owner approval: role:hr_director",
      "payload_hash": "sig_hr_director_..."
    },
    {
      "type": "purpose",
      "description": "Check rep performance for discount authority"
    }
  ],
  "proof": {
    "signer_id": "role:vp_sales,role:hr_director",
    "signature": "sig1|sig2"
  }
}
```
