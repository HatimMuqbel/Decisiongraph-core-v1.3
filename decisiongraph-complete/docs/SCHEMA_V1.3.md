
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

---

## Repository Map

### Overview

**Repo:** `Decisiongraph-core-v1.3`
**URL:** https://github.com/HatimMuqbel/Decisiongraph-core-v1.3
**Deployed to:** Railway (Dockerfile + railway.json) → decisiongraph.pro

Monorepo containing the DecisionGraph kernel, two domain applications (banking AML + insurance claims), a React dashboard, and deployment config.

### Directory Structure

```
Decisiongraph-core-v1.3/
├── decisiongraph-complete/
│   ├── src/decisiongraph/     — Foundation layer (55 modules): cell, chain, genesis,
│   │                            namespace, scholar + banking domain engine
│   ├── service/               — FastAPI service (main.py), report pipeline,
│   │                            suspicion classifier, templates
│   ├── service/routers/       — API routes: demo, report/, verify, policy_shifts
│   ├── service/templates/     — Jinja2 HTML report templates
│   ├── tests/                 — 55 test files, 1855 tests
│   ├── validation_reports/    — Generated HTML reports for 10 demo cases
│   ├── docs/                  — Schema, precedent model, operator guide
│   └── release/               — CHANGELOG, runbook, SBOM
├── claimpilot/
│   ├── src/claimpilot/        — Insurance claims engine (41 modules)
│   │   ├── models/            — Claim, Policy, Evidence, TriBool, Disposition
│   │   ├── engine/            — Policy engine, evidence gate, precedent finder
│   │   ├── calendars/         — Ontario FSRA + US federal holiday calendars
│   │   ├── precedent/         — Seed-based precedent matching (uses foundation layer)
│   │   └── packs/             — Policy pack loader + schema
│   ├── api/                   — Separate FastAPI service
│   └── tests/                 — Insurance-specific tests
├── services/
│   └── dashboard/             — React 18 + TypeScript 5.6 + Vite 6 + Tailwind CSS
│                                44 components, TanStack Query, Recharts
├── adapters/
│   └── fincrime/              — Generic CSV adapter for FinCrime data
├── packs/                     — Policy packs (fincrime_canada.yaml)
├── poc/                       — Proof of concept implementations
├── Dockerfile                 — Production build (Python 3.12-slim, port 8000)
└── railway.json               — Railway deployment config
```

### Domain-Specific Code

#### Banking AML (decisiongraph-complete/) — ~40,000 lines

| Category | Modules |
|----------|---------|
| Decision Engine | `engine.py`, `escalation_gate.py`, `str_gate.py`, `decision_pack.py`, `rules.py`, `gates.py` |
| v3 Precedent Engine | `precedent_scorer_v3.py`, `governed_confidence.py`, `domain_registry.py`, `field_comparators.py`, `comparability_gate.py`, `precedent_registry.py`, `precedent_check_report.py` |
| AML-Specific | `aml_fingerprint.py`, `aml_reason_codes.py`, `aml_seed_generator.py`, `banking_domain.py`, `banking_field_registry.py`, `suspicion_classifier.py` |
| Reporting | `bank_report.py`, `report_standards.py`, `citations.py`, `taxonomy.py` + service report pipeline (8 modules) |
| Regulatory | PCMLTFA/FINTRAC indicators, zero-false-escalation guarantee, dual-gate system |

#### Insurance Claims (claimpilot/) — ~15,000 lines

| Category | Modules |
|----------|---------|
| Claims Engine | `policy_engine.py`, `context_resolver.py`, `condition_evaluator.py`, `recommendation_builder.py` |
| Evidence System | `evidence_gate.py` (two-stage: BLOCKING_RECOMMENDATION vs BLOCKING_FINALIZATION) |
| Precedent Matching | `precedent_finder.py`, `banding_library.py`, `fingerprint_schema.py`, `seed_generator.py`, `lookback_service.py` |
| Insurance-Specific | `models/conditions.py` (TriBool logic), `models/policy.py`, `models/claim.py`, `calendars/canada_ontario.py` |
| Regulatory | Ontario FSRA timelines, multi-line coverage (auto, property, health, workers comp, liability, marine, travel) |

#### Shared Foundation Layer (lives in src/decisiongraph/, imported by both)

| Module | Purpose |
|--------|---------|
| `cell.py` | Atomic decision unit (hash-linked) |
| `chain.py` | Append-only chain of custody |
| `genesis.py` | Genesis block creation |
| `namespace.py` | Department/domain isolation |
| `scholar.py` | Bitemporal query resolver |
| `signing.py` | Cryptographic signing |
| `wal.py` / `segmented_wal.py` | Write-ahead log |
| `judgment.py` | Judgment cell creation |
| `precedent_registry.py` | Shared precedent storage |
| `canon.py` | Canonical JSON for deterministic hashing |

ClaimPilot imports from this layer:

```python
from decisiongraph.chain import Chain
from decisiongraph.cell import NULL_HASH
from decisiongraph.precedent_registry import PrecedentRegistry
from decisiongraph.judgment import create_judgment_cell
```

### Infrastructure

| Component | Banking | Insurance |
|-----------|---------|-----------|
| API | FastAPI (`service/main.py`, 161KB) | FastAPI (`api/main.py`, 8KB) |
| Database | In-memory (no persistent DB) | In-memory |
| Frontend | React SPA at `services/dashboard/` | None (shares banking dashboard) |
| Seeds | 10 AML demo cases in `demo_cases.py` | 8 policy lines in YAML seeds (auto, property, health, CGL, E&O, marine, WSIB, travel) |
| Deployment | Dockerfile + railway.json | Bundled in same container |

### Insurance-Only vs Banking-Only

**Insurance has, banking does not:**
- Three-valued logic (TriBool: TRUE/FALSE/UNKNOWN for missing facts)
- Two-stage evidence gates (BLOCKING_RECOMMENDATION vs BLOCKING_FINALIZATION)
- Holiday calendars (Ontario FSRA, US federal)
- Multi-line policy coverage resolution (7 insurance lines)
- RecommendationRecord model (system recommends, human decides)

**Banking has, insurance does not:**
- Dual-gate system (Gate 1: zero-false-escalation, Gate 2: STR obligation)
- 6-layer taxonomy (facts, obligations, indicators, typologies, mitigations, suspicion)
- v3 Precedent Engine (3-layer comparability + 4-dimension governed confidence)
- Suspicion classifier with sovereignty model
- Full report pipeline (derive, normalize, render, sanitize, store)
- React dashboard with 44 components
- Policy shift shadow tracking

### Kernel Extraction Path

The foundation layer is already shared. Target structure for full separation:

```
decisiongraph/
├── kernel/                    — Extract from src/decisiongraph/
│   ├── cell.py, chain.py, genesis.py, namespace.py, scholar.py
│   ├── signing.py, wal.py, segmented_wal.py
│   ├── judgment.py, canon.py, precedent_registry.py
│   └── domain_registry.py    — Generalize (currently banking-specific)
├── domains/
│   ├── banking/               — Current decisiongraph-complete minus kernel
│   │   ├── engine/
│   │   ├── precedent/
│   │   ├── service/
│   │   └── seeds/
│   └── insurance/             — Current claimpilot
│       ├── engine/
│       ├── precedent/
│       ├── service/
│       └── seeds/
├── dashboard/                 — Current services/dashboard
└── adapters/                  — Current adapters/
```
