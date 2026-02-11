# DecisionGraph Schema v1.3 — Complete Reference

> Authoritative schema for the DecisionGraph kernel, v3 precedent engine,
> and both registered domains (Banking AML, Insurance Claims).
>
> Source of truth: `kernel/`, `domains/`, and `kernel/precedent/domain_registry.py`.

---

## Table of Contents

1. [Cell Schema](#1-cell-schema)
2. [Chain](#2-chain)
3. [v3 Precedent Engine](#3-v3-precedent-engine)
4. [Domain Registry Protocol](#4-domain-registry-protocol)
5. [Banking AML Domain](#5-banking-aml-domain)
6. [Insurance Claims Domain](#6-insurance-claims-domain)
7. [JudgmentPayload](#7-judgmentpayload)
8. [Governed Confidence](#8-governed-confidence)
9. [Match Classification](#9-match-classification)
10. [Invariants](#10-invariants)
11. [ClaimPilot Service Layer](#11-claimpilot-service-layer)
12. [Module Map](#12-module-map)

---

## 1. Cell Schema

Source: `kernel/foundation/cell.py`

### 1.1 CellType

```python
class CellType(str, Enum):
    # Core (v1.0)
    GENESIS         = "genesis"
    FACT            = "fact"
    RULE            = "rule"
    DECISION        = "decision"
    EVIDENCE        = "evidence"
    OVERRIDE        = "override"
    # Namespace (v1.3)
    ACCESS_RULE     = "access_rule"
    BRIDGE_RULE     = "bridge_rule"
    NAMESPACE_DEF   = "namespace_def"
    # Policy (v1.5)
    POLICY_HEAD     = "policy_head"
    # Reasoning output (v2.0)
    SIGNAL          = "signal"
    MITIGATION      = "mitigation"
    SCORE           = "score"
    VERDICT         = "verdict"
    # Audit/justification (v2.0)
    JUSTIFICATION   = "justification"
    POLICY_REF      = "policy_ref"
    POLICY_CITATION = "policy_citation"
    REPORT_RUN      = "report_run"
    JUDGMENT        = "judgment"
```

### 1.2 SourceQuality

```python
class SourceQuality(str, Enum):
    VERIFIED       = "verified"        # Confirmed from authoritative source
    SELF_REPORTED  = "self_reported"   # User-provided, not verified
    INFERRED       = "inferred"        # Derived from other facts
```

### 1.3 SensitivityLevel

```python
class SensitivityLevel(str, Enum):
    PUBLIC         = "public"
    INTERNAL       = "internal"
    CONFIDENTIAL   = "confidential"
    RESTRICTED     = "restricted"
```

### 1.4 Complete Cell JSON

```json
{
  "cell_id": "string (SHA256 hex, 64 chars)",

  "header": {
    "version":        "string ('1.3' | '2.0')",
    "graph_id":       "string (format: 'graph:<uuid-v4>')",
    "cell_type":      "string (CellType enum value)",
    "system_time":    "string (ISO 8601 UTC, must end with 'Z')",
    "prev_cell_hash": "string (SHA256 hex, 64 chars | NULL_HASH for Genesis)",
    "hash_scheme":    "string | null ('canon:rfc8785:v1' for structured payloads)"
  },

  "fact": {
    "namespace":      "string (lowercase, dots for hierarchy)",
    "subject":        "string (entity identifier)",
    "predicate":      "string (relationship)",
    "object":         "string | dict | list  (v2.0: structured payloads allowed)",
    "confidence":     "number (0.0 to 1.0)",
    "source_quality": "string (SourceQuality enum value)",
    "valid_from":     "string (ISO 8601 UTC) | null",
    "valid_to":       "string (ISO 8601 UTC) | null (null = forever)"
  },

  "logic_anchor": {
    "rule_id":          "string (rule identifier)",
    "rule_logic_hash":  "string (SHA256 hex of canonicalized rule content)",
    "interpreter":      "string | null (e.g. 'datalog:v2', 'precedent:v1')"
  },

  "evidence": [
    {
      "type":           "string (e.g. 'document_blob', 'api_response')",
      "cid":            "string | null (content ID)",
      "source":         "string | null",
      "payload_hash":   "string | null",
      "description":    "string | null"
    }
  ],

  "proof": {
    "signer_id":          "string | null",
    "signer_key_id":      "string | null",
    "signature":          "string | null",
    "merkle_root":        "string | null",
    "signature_required": "boolean (default false)"
  }
}
```

### 1.5 cell_id Computation (Logic Seal)

Two hash schemes:

**Legacy** (`legacy:concat:v1`, default):
```python
cell_id = SHA256(
    header.version
    + header.graph_id
    + header.cell_type
    + header.system_time
    + header.prev_cell_hash
    + fact.namespace
    + fact.subject
    + fact.predicate
    + str(fact.object)           # object must be a string
    + logic_anchor.rule_id
    + logic_anchor.rule_logic_hash
)
```

**Canonical** (`canon:rfc8785:v1`, required for structured payloads):
```python
cell_id = SHA256(rfc8785_canonical_json(cell_dict))
```

Constraint: structured `fact.object` (dict/list) requires `hash_scheme = "canon:rfc8785:v1"`.
No floats allowed in structured payloads.

### 1.6 Constants

```python
NULL_HASH             = "0" * 64
HASH_SCHEME_LEGACY    = "legacy:concat:v1"
HASH_SCHEME_CANONICAL = "canon:rfc8785:v1"
HASH_SCHEME_DEFAULT   = HASH_SCHEME_LEGACY
```

### 1.7 Validation Rules

| Rule | Pattern / Constraint |
|------|---------------------|
| Namespace | `^[a-z][a-z0-9_]{0,63}(\.[a-z][a-z0-9_]{0,63})*$` |
| graph_id | `^graph:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$` |
| system_time | `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$` |
| confidence | 0.0-1.0; 1.0 requires `source_quality = "verified"` |
| prev_cell_hash | `NULL_HASH` only for Genesis |

---

## 2. Chain

Source: `kernel/foundation/chain.py`

Append-only hash-linked log of `DecisionCell` instances.

```
[Genesis] <-- [Cell 1] <-- [Cell 2] <-- ... <-- [Head]
     |            |            |
     +------------+------------+--- prev_cell_hash links
```

### 2.1 Append Rules

| # | Rule | Error |
|---|------|-------|
| 1 | Genesis must be first cell | `GenesisViolation` |
| 2 | Only one Genesis per chain | `GenesisViolation` |
| 3 | cell_id must recompute correctly | `IntegrityViolation` |
| 4 | prev_cell_hash must point to existing cell | `ChainBreak` |
| 5 | system_time >= previous cell's system_time | `TemporalViolation` |
| 6 | graph_id must match chain's graph_id | `GraphIdMismatch` |
| 7 | hash_scheme must match chain's hash_scheme (v2.0) | `HashSchemeMismatch` |

### 2.2 ValidationResult

```python
@dataclass
class ValidationResult:
    is_valid:       bool
    cells_checked:  int
    graph_id:       str | None
    root_namespace: str | None
    errors:         list[str]
    warnings:       list[str]
```

---

## 3. v3 Precedent Engine

The engine evaluates in three layers. Each layer reads the `DomainRegistry` — no domain-specific code in the kernel.

```
                          Case Facts
                              |
                    +---------v-----------+
          Layer 1   | Comparability Gate  |   gates filter incomparable
                    | (all gates must     |   precedents out entirely
                    |  pass)              |
                    +---------+-----------+
                              |
                    +---------v-----------+
          Layer 2   | Causal Factor       |   weighted field-by-field
                    | Alignment / Scorer  |   similarity scoring
                    +---------+-----------+
                              |
                    +---------v-----------+
          Layer 3   | Governed Confidence |   four-dimension min()
                    | + Match Classifier  |   with hard rules
                    +---------------------+
```

### 3.1 Layer 1 — Comparability Gate

Source: `kernel/precedent/comparability_gate.py`

ALL gates must pass for a precedent to enter the scoring pool.
Each gate classifies both the case value and the precedent value into equivalence classes.
Same class = pass. Different class = filter out.

```python
@dataclass
class GateResult:
    passed:          bool
    gate_field:      str
    case_class:      str | None
    precedent_class: str | None
    fallback_used:   bool = False    # broadest-class fallback was used
    warning:         str | None = None
```

Fallback logic:
- Missing field -> broadest class + warning
- Unclassifiable value -> gate passes (cannot determine incomparability)

### 3.2 Layer 2 — Field Comparators

Source: `kernel/precedent/field_comparators.py`

Five comparison primitives, all returning `float` in [0.0, 1.0]:

| ComparisonFn | Formula | Notes |
|-------------|---------|-------|
| `EXACT` | `1.0` if equal, `0.0` otherwise | Case-insensitive for strings |
| `EQUIVALENCE_CLASS` | `1.0` if same class, `0.0` otherwise | Falls back to EXACT for unknown values |
| `DISTANCE_DECAY` | `1.0 - (|a - b| / max_distance)` clamped to [0.0, 1.0] | For numeric fields |
| `STEP` | `1.0 - (step_diff / max_steps)` | Ordinal distance on ordered_values |
| `JACCARD` | `|intersection| / |union|` | Both empty = 1.0 |

### 3.3 Layer 2 — Scoring

Source: `kernel/precedent/precedent_scorer.py`

```python
@dataclass
class SimilarityResult:
    score:                    float         # normalized 0.0-1.0
    raw_score:                float         # unnormalized weighted sum
    total_weight:             float         # sum of evaluable weights
    non_transferable:         bool          # driver mismatch flag
    non_transferable_reasons: list[str]
    matched_drivers:          list[str]     # BEHAVIORAL fields that matched
    mismatched_drivers:       list[str]     # BEHAVIORAL fields that differed
    matched_context:          list[str]     # CONTEXTUAL fields that matched
    field_scores:             dict[str, float]
    evaluable_fields:         list[str]
    missing_fields:           list[str]
```

Scoring rules:
- BEHAVIORAL fields scored at **2x weight** when listed as decision_drivers
- CONTEXTUAL fields scored at **1x weight** (stabilizers)
- STRUCTURAL fields do not participate in scoring (handled by Layer 1 gates)
- Score = `sum(field_score * weight) / sum(weights)`, normalized to [0.0, 1.0]

---

## 4. Domain Registry Protocol

Source: `kernel/precedent/domain_registry.py`

The engine is domain-agnostic. Every domain provides a `DomainRegistry` via a factory function.

### 4.1 Enums

```python
class FieldType(str, Enum):
    BOOLEAN      = "BOOLEAN"
    CATEGORICAL  = "CATEGORICAL"
    NUMERIC      = "NUMERIC"
    ORDINAL      = "ORDINAL"
    SET          = "SET"

class ComparisonFn(str, Enum):
    EXACT              = "EXACT"
    EQUIVALENCE_CLASS  = "EQUIVALENCE_CLASS"
    DISTANCE_DECAY     = "DISTANCE_DECAY"
    STEP               = "STEP"
    JACCARD            = "JACCARD"

class FieldTier(str, Enum):
    STRUCTURAL   = "STRUCTURAL"    # Layer 1: comparability gate filter
    BEHAVIORAL   = "BEHAVIORAL"    # Layer 2: scored at 2x when driver
    CONTEXTUAL   = "CONTEXTUAL"    # Layer 2: scored at 1x, stabilizer

class ConfidenceLevel(str, Enum):
    NONE       = "NONE"            # numeric: 0.00
    LOW        = "LOW"             # numeric: 0.25
    MODERATE   = "MODERATE"        # numeric: 0.50
    HIGH       = "HIGH"            # numeric: 0.75
    VERY_HIGH  = "VERY_HIGH"       # numeric: 0.95
```

### 4.2 FieldDefinition

```python
@dataclass(frozen=True)
class FieldDefinition:
    name:                str                         # canonical dot-path
    label:               str                         # human-readable
    type:                FieldType
    comparison:          ComparisonFn
    weight:              float                       # 0.0-1.0
    tier:                FieldTier
    required:            bool = True
    critical:            bool = False                # absence caps confidence at LOW
    equivalence_classes: dict[str, list[str]] = {}   # for EQUIVALENCE_CLASS
    ordered_values:      list[str] = []              # for STEP
    max_distance:        int = 4                     # for DISTANCE_DECAY
    domain:              str = "banking_aml"
```

Validation:
- `weight` must be 0.0-1.0
- `EQUIVALENCE_CLASS` requires non-empty `equivalence_classes`
- `STEP` requires non-empty `ordered_values`

### 4.3 ComparabilityGate

```python
@dataclass(frozen=True)
class ComparabilityGate:
    field:               str                         # may be virtual (e.g. "jurisdiction_regime")
    equivalence_classes: dict[str, list[str]]        # class_name -> [raw values]
```

Methods: `classify(value) -> str | None`, `broadest_class() -> str`

### 4.4 DomainRegistry

```python
@dataclass
class DomainRegistry:
    domain:                    str
    version:                   str
    fields:                    dict[str, FieldDefinition]
    comparability_gates:       list[ComparabilityGate]
    similarity_floor:          float = 0.60
    similarity_floor_overrides: dict[str, float] = {}   # typology -> floor
    pool_minimum:              int = 5
    critical_fields:           frozenset[str] = frozenset()
    disposition_mapping:       dict[str, str] = {}      # raw -> canonical
    reporting_mapping:         dict[str, str] = {}
    basis_mapping:             dict[str, str] = {}
```

### 4.5 Domain Loader

Source: `kernel/precedent/domain_loader.py`

```python
DOMAINS = {
    "banking_aml":      "domains.banking_aml.domain",
    "insurance_claims": "domains.insurance_claims.domain",
}

load_domain(domain_id: str) -> DomainRegistry
list_domains() -> list[str]
register_domain(domain_id: str, module_path: str) -> None
```

Each domain module exposes `create_registry() -> DomainRegistry`.

---

## 5. Banking AML Domain

Source: `domains/banking_aml/`

### 5.1 Registry Configuration

| Parameter | Value |
|-----------|-------|
| domain | `banking_aml` |
| version | `3.0` |
| total fields | 27 |
| similarity_floor | 0.60 |
| pool_minimum | 5 |
| critical_fields | `customer.type`, `txn.type`, `txn.amount_band` |

Similarity floor overrides:

| Typology | Floor |
|----------|-------|
| sanctions | 0.80 |
| structuring | 0.65 |
| adverse_media | 0.55 |

### 5.2 Field Definitions (27 fields)

#### Customer (6)

| Field | Type | Comparison | Weight | Tier | Critical |
|-------|------|-----------|--------|------|----------|
| `customer.type` | CATEGORICAL | EQUIVALENCE_CLASS | 0.05 | STRUCTURAL | yes |
| `customer.relationship_length` | ORDINAL | STEP | 0.03 | CONTEXTUAL | |
| `customer.pep` | BOOLEAN | EXACT | 0.05 | BEHAVIORAL | |
| `customer.high_risk_jurisdiction` | BOOLEAN | EXACT | 0.04 | BEHAVIORAL | |
| `customer.high_risk_industry` | BOOLEAN | EXACT | 0.03 | BEHAVIORAL | |
| `customer.cash_intensive` | BOOLEAN | EXACT | 0.02 | CONTEXTUAL | |

`customer.type` equivalence classes:
- retail: individual, personal, retail
- corporate: corporation, institutional, company

`customer.relationship_length` ordered values: new, recent, established

#### Transaction (10)

| Field | Type | Comparison | Weight | Tier | Critical |
|-------|------|-----------|--------|------|----------|
| `txn.type` | CATEGORICAL | EQUIVALENCE_CLASS | 0.07 | STRUCTURAL | yes |
| `txn.amount_band` | ORDINAL | STEP | 0.10 | BEHAVIORAL | yes |
| `txn.cross_border` | BOOLEAN | EXACT | 0.06 | BEHAVIORAL | |
| `txn.destination_country_risk` | ORDINAL | STEP | 0.05 | BEHAVIORAL | |
| `txn.round_amount` | BOOLEAN | EXACT | 0.02 | CONTEXTUAL | |
| `txn.just_below_threshold` | BOOLEAN | EXACT | 0.04 | BEHAVIORAL | |
| `txn.multiple_same_day` | BOOLEAN | EXACT | 0.03 | BEHAVIORAL | |
| `txn.pattern_matches_profile` | BOOLEAN | EXACT | 0.03 | CONTEXTUAL | |
| `txn.source_of_funds_clear` | BOOLEAN | EXACT | 0.02 | CONTEXTUAL | |
| `txn.stated_purpose` | CATEGORICAL | EXACT | 0.02 | CONTEXTUAL | |

`txn.type` equivalence classes:
- cash: cash, cash_deposit, cash_withdrawal
- electronic: wire_domestic, wire_international, eft, ach, swift, domestic_wire
- crypto: crypto, virtual_currency, digital_asset, crypto_purchase, crypto_sale
- cheque: cheque, check
- trade: trade_finance, lc, documentary_credit

`txn.amount_band` ordered values: under_3k, 3k_10k, 10k_25k, 25k_100k, 100k_500k, 500k_1m, over_1m

#### Red Flags (6)

| Field | Type | Comparison | Weight | Tier |
|-------|------|-----------|--------|------|
| `flag.structuring` | BOOLEAN | EXACT | 0.06 | BEHAVIORAL |
| `flag.rapid_movement` | BOOLEAN | EXACT | 0.04 | BEHAVIORAL |
| `flag.layering` | BOOLEAN | EXACT | 0.05 | BEHAVIORAL |
| `flag.unusual_for_profile` | BOOLEAN | EXACT | 0.04 | BEHAVIORAL |
| `flag.third_party` | BOOLEAN | EXACT | 0.03 | BEHAVIORAL |
| `flag.shell_company` | BOOLEAN | EXACT | 0.03 | BEHAVIORAL |

#### Screening & Prior History (5)

| Field | Type | Comparison | Weight | Tier |
|-------|------|-----------|--------|------|
| `screening.sanctions_match` | BOOLEAN | EXACT | 0.06 | BEHAVIORAL |
| `screening.pep_match` | BOOLEAN | EXACT | 0.04 | BEHAVIORAL |
| `screening.adverse_media` | BOOLEAN | EXACT | 0.04 | BEHAVIORAL |
| `prior.sars_filed` | NUMERIC | DISTANCE_DECAY | 0.03 | BEHAVIORAL |
| `prior.account_closures` | BOOLEAN | EXACT | 0.02 | BEHAVIORAL |

`prior.sars_filed` max_distance: 4

### 5.3 Comparability Gates (4)

| Gate Field | Equivalence Classes |
|-----------|-------------------|
| `jurisdiction_regime` | CA_FINTRAC: [CA, CA-ON, CA-QC, CA-BC, CA-AB], US_FinCEN: [US, US-NY, US-CA, US-FL, US-TX], UK_FCA: [UK, GB, GB-ENG, GB-SCT] |
| `customer_segment` | retail: [individual, personal, retail, sole_prop], SME: [sme, small_business], corporate: [corporate, institutional, company, corporation, partnership, trust, non_profit], FI: [bank, fi, financial_institution] |
| `channel_family` | cash: [cash, cash_deposit, cash_withdrawal], electronic: [wire_domestic, wire_international, wire, eft, ach, swift, domestic_wire], crypto: [crypto, virtual_currency, digital_asset, crypto_purchase, crypto_sale], cheque: [cheque, check], trade: [trade_finance, lc, documentary_credit] |
| `disposition_basis` | MANDATORY: [MANDATORY], DISCRETIONARY: [DISCRETIONARY] |

### 5.4 Outcome Vocabulary

```python
BANKING_DISPOSITIONS    = {"ALLOW", "EDD", "BLOCK"}
BANKING_REPORTING       = {"NO_REPORT", "FILE_STR", "FILE_LCTR", "FILE_TPR", "PENDING_EDD"}
BANKING_BASIS           = {"MANDATORY", "DISCRETIONARY"}
BANKING_DECISION_LEVELS = {"analyst", "senior_analyst", "manager", "cco", "senior_management"}
```

### 5.5 Disposition Mapping (raw -> canonical)

| Canonical | Raw Values |
|-----------|-----------|
| ALLOW | approve, approved, accept, accepted, pay, paid, pass, passed, clear, cleared, covered, eligible, no report, no action, close, closed |
| EDD | review, investigate, investigation, hold, pending, manual review, needs info, request more info, pass with edd, escalate, escalated |
| BLOCK | deny, denied, decline, declined, reject, rejected, block, blocked, refuse, refused, hard stop, exit, de-risk |

### 5.6 Reporting Mapping

| Canonical | Raw Values |
|-----------|-----------|
| FILE_STR | str, report str, suspicious transaction, suspicious activity |
| FILE_LCTR | lctr, large cash, large cash transaction |
| FILE_TPR | tpr, terrorist property, terrorist property report |
| NO_REPORT | no report, no filing required |

### 5.7 Basis Mapping

| Canonical | Raw Values |
|-----------|-----------|
| MANDATORY | sanctions, sanction, sema, una, listed entity, court order, statutory, criminal code |
| DISCRETIONARY | risk appetite, policy violation, commercial exit, fraud risk, reputational concern, credit decision |

### 5.8 Seed Pool

Source: `domains/banking_aml/seed_generator.py`

- 20 scenarios, 1,500 seeds
- Salt: `decisiongraph-banking-seed-v2`
- Policy: `CA-FINTRAC-AML` v2026.01.01
- ~10% noise (minority-outcome variants)
- 4 policy shifts with post-shift seeds

### 5.9 Policy Shifts (4)

Source: `domains/banking_aml/policy_shifts.py`

| Shift ID | Description | Effective |
|----------|------------|-----------|
| `fintrac_threshold_2025` | LCTR threshold $10k -> $3k | 2026.04.01 |
| `crypto_travel_rule` | FATF travel rule for crypto >$1k | 2026.06.01 |
| `beneficial_ownership_2025` | 25% -> 10% BO threshold | 2026.07.01 |
| `pep_screening_expanded` | Domestic PEP screening expansion | 2026.09.01 |

### 5.10 Reason Codes

Source: `domains/banking_aml/reason_codes.py`

~92 reason codes across 5 registries:
- `decisiongraph:aml:monitoring:v1` — Transaction monitoring
- `decisiongraph:aml:kyc:v1` — KYC/CDD
- `decisiongraph:aml:screening:v1` — Sanctions/PEP screening
- `decisiongraph:aml:reporting:v1` — Regulatory reporting
- `decisiongraph:aml:risk:v1` — Risk assessment

---

## 6. Insurance Claims Domain

Source: `domains/insurance_claims/`

### 6.1 Registry Configuration

| Parameter | Value |
|-----------|-------|
| domain | `insurance_claims` |
| version | `3.0` |
| total fields | 23 |
| similarity_floor | 0.55 |
| pool_minimum | 5 |
| critical_fields | `claim.coverage_line`, `claim.amount_band`, `claim.claimant_type` |

Similarity floor overrides:

| Typology | Floor |
|----------|-------|
| fraud | 0.75 |
| siu_referral | 0.70 |
| catastrophic_injury | 0.50 |

### 6.2 Field Definitions (23 fields)

#### Claim Structural (3)

| Field | Type | Comparison | Weight | Tier | Critical |
|-------|------|-----------|--------|------|----------|
| `claim.coverage_line` | CATEGORICAL | EQUIVALENCE_CLASS | 0.06 | STRUCTURAL | yes |
| `claim.amount_band` | ORDINAL | STEP | 0.10 | STRUCTURAL | yes |
| `claim.claimant_type` | CATEGORICAL | EXACT | 0.04 | STRUCTURAL | yes |

`claim.coverage_line` equivalence classes:
- auto: auto, automobile
- property: property, homeowners
- health: health, medical
- workers_comp: workers_comp, wsib
- liability: cgl, commercial_general_liability
- professional: eo, errors_omissions
- marine: marine, pleasure_craft
- travel: travel

`claim.amount_band` ordered values: under_5k, 5k_25k, 25k_100k, 100k_500k, over_500k

#### Red Flags (7)

| Field | Type | Comparison | Weight | Tier |
|-------|------|-----------|--------|------|
| `flag.fraud_indicator` | BOOLEAN | EXACT | 0.08 | BEHAVIORAL |
| `flag.prior_claims_frequency` | ORDINAL | STEP | 0.05 | BEHAVIORAL |
| `flag.late_reporting` | BOOLEAN | EXACT | 0.04 | BEHAVIORAL |
| `flag.inconsistent_statements` | BOOLEAN | EXACT | 0.06 | BEHAVIORAL |
| `flag.staged_accident` | BOOLEAN | EXACT | 0.06 | BEHAVIORAL |
| `flag.excessive_claim_history` | BOOLEAN | EXACT | 0.04 | BEHAVIORAL |
| `flag.pre_existing_damage` | BOOLEAN | EXACT | 0.04 | BEHAVIORAL |

`flag.prior_claims_frequency` ordered values: none, low, moderate, high

#### Evidence (4)

| Field | Type | Comparison | Weight | Tier |
|-------|------|-----------|--------|------|
| `evidence.police_report` | BOOLEAN | EXACT | 0.03 | CONTEXTUAL |
| `evidence.medical_report` | BOOLEAN | EXACT | 0.03 | CONTEXTUAL |
| `evidence.witness_statements` | BOOLEAN | EXACT | 0.02 | CONTEXTUAL |
| `evidence.photos_documentation` | BOOLEAN | EXACT | 0.02 | CONTEXTUAL |

#### Policy (3)

| Field | Type | Comparison | Weight | Tier |
|-------|------|-----------|--------|------|
| `policy.deductible_band` | ORDINAL | STEP | 0.03 | CONTEXTUAL |
| `policy.coverage_limit_band` | ORDINAL | STEP | 0.03 | CONTEXTUAL |
| `policy.policy_age` | ORDINAL | STEP | 0.02 | CONTEXTUAL |

`policy.deductible_band` ordered values: low, medium, high
`policy.coverage_limit_band` ordered values: basic, standard, premium, excess
`policy.policy_age` ordered values: new, established, mature

#### Contextual (4)

| Field | Type | Comparison | Weight | Tier |
|-------|------|-----------|--------|------|
| `claim.injury_type` | ORDINAL | STEP | 0.04 | CONTEXTUAL |
| `claim.loss_cause` | CATEGORICAL | EQUIVALENCE_CLASS | 0.04 | CONTEXTUAL |
| `claim.time_to_report` | ORDINAL | STEP | 0.03 | BEHAVIORAL |
| `claim.occurred_during_policy` | BOOLEAN | EXACT | 0.03 | CONTEXTUAL |

`claim.injury_type` ordered values: minor, moderate, serious, catastrophic
`claim.loss_cause` equivalence classes:
- vehicle: collision, theft
- natural: fire, water, wind
- human: vandalism, liability
- other: other

`claim.time_to_report` ordered values: immediate, within_week, within_month, delayed

`claim.injury_type` and `claim.loss_cause` have `required = False`.

#### Screening & Prior History (3)

| Field | Type | Comparison | Weight | Tier |
|-------|------|-----------|--------|------|
| `screening.siu_referral` | BOOLEAN | EXACT | 0.05 | BEHAVIORAL |
| `prior.claims_denied` | NUMERIC | DISTANCE_DECAY | 0.03 | BEHAVIORAL |

`prior.claims_denied` max_distance: 4

### 6.3 Comparability Gates (4)

| Gate Field | Equivalence Classes |
|-----------|-------------------|
| `jurisdiction_regime` | CA_FSRA: [CA, CA-ON, CA-QC, CA-BC, CA-AB], US_STATE: [US, US-NY, US-CA, US-FL, US-TX], UK_FCA: [UK, GB] |
| `coverage_family` | auto: [auto, automobile], property: [property, homeowners], health: [health, medical], workers_comp: [workers_comp, wsib], liability: [cgl, commercial_general_liability, eo, errors_omissions], specialty: [marine, pleasure_craft, travel] |
| `claimant_family` | first_party: [first_party, 1st_party, insured], third_party: [third_party, 3rd_party, claimant] |
| `disposition_basis` | MANDATORY: [MANDATORY], DISCRETIONARY: [DISCRETIONARY] |

### 6.4 Outcome Vocabulary

```python
INSURANCE_DISPOSITIONS    = {"PAY_CLAIM", "PARTIAL_PAY", "INVESTIGATE", "REFER_SIU", "DENY_CLAIM"}
INSURANCE_REPORTING       = {"NO_FILING", "FSRA_NOTICE", "FRAUD_REPORT"}
INSURANCE_BASIS           = {"MANDATORY", "DISCRETIONARY"}
INSURANCE_DECISION_LEVELS = {"adjuster", "senior_adjuster", "examiner",
                             "supervisor", "siu_investigator", "claims_manager"}
```

### 6.5 Disposition Mapping (raw -> canonical)

| Canonical | Raw Values |
|-----------|-----------|
| ALLOW | pay, pay_claim, approve, approved, covered, eligible, partial, partial_pay, subrogation |
| EDD | investigate, investigation, refer_siu, siu_referral, hold, pending, escalate, reserve_only, request_info |
| BLOCK | deny, deny_claim, denied, decline, declined, close_no_pay, reject |

### 6.6 Reporting Mapping

| Canonical | Raw Values |
|-----------|-----------|
| NO_FILING | no_filing, none |
| FSRA_NOTICE | fsra_notice, regulatory_notice |
| FRAUD_REPORT | fraud_report, siu_report |

### 6.7 Basis Mapping

| Canonical | Raw Values |
|-----------|-----------|
| MANDATORY | policy_exclusion, regulatory, statutory, excluded_peril, outside_policy_period |
| DISCRETIONARY | claims_assessment, risk_judgment, adjuster_discretion, coverage_interpretation |

### 6.8 Seed Pool

Source: `domains/insurance_claims/seed_generator.py`

- 22 scenarios across 8 coverage lines, ~1,618 seeds
- Salt: `decisiongraph-insurance-seed-v1`
- Policy: `CA-FSRA-INSURANCE` v2026.01.01
- Coverage lines: auto, property, health, workers_comp, cgl, eo, marine, travel
- ~10% noise (minority-outcome variants)
- 3 policy shifts with post-shift seeds
- Outcome distribution: ~57% pay, ~31% escalate, ~12% deny

#### Scenario-Specific Deny Seeds

Two scenario-specific deny scenarios ensure meaningful precedent support for
denial cases that correspond to common policy exclusions:

| Scenario | Weight | Coverage | Key Facts | Basis |
|----------|--------|----------|-----------|-------|
| `auto_impairment_deny` | 3% (~48 seeds) | auto | `fraud_indicator=True`, `loss_cause=collision`, `injury_type=moderate`, `police_report=True` | DISCRETIONARY |
| `property_vacancy_deny` | 2% (~32 seeds) | property | `occurred_during_policy=True`, first_party | DISCRETIONARY |

Both use DISCRETIONARY basis to avoid INV-008 cross-basis neutralization against
demo cases (which default to DISCRETIONARY). Decision drivers are chosen to avoid
non-transferable classification (INV-011) — e.g. vacancy deny uses
`coverage_line` + `occurred_during_policy` rather than `loss_cause` since vacancy
denial is about duration, not loss type.

Weight budget: `clean_auto_claim` reduced 15% → 12%, `clean_property_claim`
reduced 10% → 8% to accommodate the new scenarios (total weights sum to 1.00).

### 6.9 Policy Shifts (3)

Source: `domains/insurance_claims/policy_shifts.py`

| Shift ID | Description | Effective |
|----------|------------|-----------|
| `fsra_minor_injury_cap` | FSRA minor injury cap $3,500 -> $5,000 | 2026.04.01 |
| `fraud_ring_detection` | Mandatory SIU referral for fraud ring patterns | 2026.06.01 |
| `climate_event_coverage` | Expedited processing for declared climate events | 2026.07.01 |

### 6.10 Reason Codes

Source: `domains/insurance_claims/reason_codes.py`

51 reason codes across 5 registries:
- `decisiongraph:insurance:fraud:v1` — Fraud indicators (~12 codes, prefix `RC-FRD-`)
- `decisiongraph:insurance:coverage:v1` — Coverage/exclusion (~12 codes, prefix `RC-COV-`)
- `decisiongraph:insurance:evidence:v1` — Documentation gaps (~8 codes, prefix `RC-EVD-`)
- `decisiongraph:insurance:regulatory:v1` — Regulatory requirements (~8 codes, prefix `RC-REG-`)
- `decisiongraph:insurance:siu:v1` — SIU referral reasons (~8 codes, prefix `RC-SIU-`)

---

## 7. JudgmentPayload

Source: `kernel/foundation/judgment.py`

Sealed as JUDGMENT cells on the chain. This is the precedent record.

### 7.1 Constants

```python
JUDGMENT_RULE_ID     = "judgment:precedent:v1"
JUDGMENT_RULE_HASH   = SHA256("judgment:precedent:v1")
JUDGMENT_INTERPRETER = "precedent:v1"
```

### 7.2 AnchorFact

```python
@dataclass
class AnchorFact:
    field_id: str     # e.g. "customer.type"
    value:    Any     # JSON-serializable, no floats
    label:    str     # human-readable
```

### 7.3 JudgmentPayload Fields

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| **Identity** | | | |
| `precedent_id` | str | required | Random UUID |
| `case_id_hash` | str | required | SHA256 hex, 64 chars |
| `jurisdiction_code` | str | required | e.g. `"CA-ON"` |
| **Fingerprint** | | | |
| `fingerprint_hash` | str | required | SHA256 hex, 64 chars |
| `fingerprint_schema_id` | str | required | e.g. `"claimpilot:oap1:auto:v1"` |
| `anchor_facts` | list[AnchorFact] | required | Banded facts for matching |
| **Decision** | | | |
| `exclusion_codes` | list[str] | required | e.g. `["4.2.1"]` |
| `reason_codes` | list[str] | required | e.g. `["RC-FRD-STAGED"]` |
| `reason_code_registry_id` | str | required | Registry identifier |
| `outcome_code` | str | required | `{pay, deny, partial, escalate}` |
| `certainty` | str | required | `{high, medium, low}` |
| **Policy** | | | |
| `policy_pack_hash` | str | required | SHA256 hex, 64 chars |
| `policy_pack_id` | str | required | e.g. `"CA-FSRA-INSURANCE"` |
| `policy_version` | str | required | e.g. `"2026.01.01"` |
| **Decision Authority** | | | |
| `decision_level` | str | required | Banking: analyst/senior_analyst/manager/cco/senior_management. Insurance: adjuster/manager/tribunal/court |
| `decided_at` | str | required | ISO 8601 with timezone |
| `decided_by_role` | str | required | Role (never name) |
| **Appeals** | | | |
| `appealed` | bool | `False` | |
| `appeal_outcome` | str\|None | `None` | `{upheld, overturned, settled, pending}` |
| `appeal_decided_at` | str\|None | `None` | ISO 8601 |
| `appeal_level` | str\|None | `None` | |
| **Provenance** | | | |
| `source_type` | str | `"system_generated"` | `{seed, seeded, system_generated, prod, byoc, imported, tribunal}` |
| `scenario_code` | str\|None | `None` | |
| `seed_category` | str\|None | `None` | |
| `outcome_notable` | str\|None | `None` | `{boundary_case, landmark, overturned}` |
| **v3 Three-Field Outcome** | | | |
| `disposition_basis` | str | `"UNKNOWN"` | `{MANDATORY, DISCRETIONARY, UNKNOWN}` |
| `reporting_obligation` | str | `"UNKNOWN"` | `{NO_REPORT, FILE_STR, FILE_LCTR, FILE_TPR, PENDING_EDD, UNKNOWN}` |
| `domain` | str | `"insurance"` | `{insurance, banking}` |
| `signal_codes` | list[str] | `[]` | Banking equivalent of exclusion_codes |
| **v3 Driver Metadata** | | | |
| `decision_drivers` | list[str] | `[]` | Which fields drove the outcome |
| `driver_typology` | str | `""` | e.g. `"sanctions"`, `"structuring"` |
| `authority_hashes` | list[str] | `[]` | SHA256 hex, 64 chars each |
| `policy_regime` | dict\|None | `None` | `{"version": ..., "shifts_applied": [...], "is_post_shift": bool}` |

---

## 8. Governed Confidence

Source: `kernel/precedent/governed_confidence.py`

Four-dimension model. Final confidence = `min(all dimensions)` unless a hard rule fires first.

### 8.1 Output Structures

```python
@dataclass
class ConfidenceDimension:
    name:       str
    value:      float              # raw numeric (0.0-1.0 or count)
    level:      ConfidenceLevel
    bottleneck: bool = False
    note:       str = ""

@dataclass
class GovernedConfidenceResult:
    level:             ConfidenceLevel
    numeric_value:     float             # mapped from level
    dimensions:        list[ConfidenceDimension]
    hard_rule_applied: str | None = None
    bottleneck:        str | None = None
```

### 8.2 Dimension Thresholds

**pool_adequacy** (pool_size):

| Pool Size | Level |
|-----------|-------|
| 0 | NONE |
| 1-4 | LOW |
| 5-14 | MODERATE |
| 15-49 | HIGH |
| 50+ | VERY_HIGH |

**similarity_quality** (avg_similarity):

| Avg Similarity | Level |
|---------------|-------|
| < 0.50 | LOW |
| 0.50-0.69 | MODERATE |
| 0.70-0.84 | HIGH |
| 0.85+ | VERY_HIGH |

**outcome_consistency** (decisive_supporting / decisive_total):

| Agreement | Level |
|-----------|-------|
| 0 decisive | MODERATE (note: "No terminal precedents") |
| < 0.60 | LOW |
| 0.60-0.79 | MODERATE |
| 0.80-0.94 | HIGH |
| 0.95+ | VERY_HIGH |

**evidence_completeness** (% required fields present):

| Completeness | Level |
|-------------|-------|
| critical field missing | capped at LOW |
| < 0.80 | LOW |
| 0.80-0.89 | MODERATE |
| 0.90-0.94 | HIGH |
| 0.95+ | VERY_HIGH |

### 8.3 Hard Rules (checked before formula)

| # | Condition | Result |
|---|----------|--------|
| 1 | 0 precedents above similarity floor | NONE |
| 2 | avg_similarity < 0.50 | capped at LOW |
| 3 | Critical fields missing | capped at LOW |
| 4 | 0 decisive precedents | capped at MODERATE |
| 5 | pool < pool_minimum | capped at LOW |

### 8.4 Level-to-Numeric Mapping

| Level | Numeric |
|-------|---------|
| NONE | 0.00 |
| LOW | 0.25 |
| MODERATE | 0.50 |
| HIGH | 0.75 |
| VERY_HIGH | 0.95 |

---

## 9. Match Classification

Source: `kernel/precedent/precedent_scorer.py`

`classify_match_v3()` returns one of: `"supporting"`, `"contrary"`, `"neutral"`.

### 9.1 Classification Rules (evaluated in order)

| Rule | Condition | Result |
|------|----------|--------|
| INV-003 | UNKNOWN disposition | `"neutral"` |
| INV-005 | EDD disposition (except EDD==EDD without non_transferable) | `"neutral"` |
| INV-008 | Cross-basis (MANDATORY vs DISCRETIONARY) | `"neutral"` |
| — | Same disposition, not non_transferable | `"supporting"` |
| INV-011 | Same disposition, but non_transferable | `"neutral"` |
| INV-004 | ALLOW vs BLOCK or BLOCK vs ALLOW | `"contrary"` |
| — | Everything else | `"neutral"` |

### 9.2 Typology Detection

`detect_primary_typology()` returns: `"sanctions"`, `"structuring"`, `"adverse_media"`, or `None`.

---

## 10. Invariants

From the v3 Precedent Engine Specification.

| ID | Invariant | Basis |
|----|-----------|-------|
| INV-001 | STR obligation must never be inferred from disposition | PCMLTFA s. 7 |
| INV-002 | Disposition, disposition basis, and reporting stored/evaluated independently | Architectural |
| INV-003 | UNKNOWN outcomes excluded from confidence denominators | Statistical integrity |
| INV-004 | Only ALLOW vs. BLOCK constitutes contrary precedent | Regulatory semantics |
| INV-005 | EDD classified as Neutral in all precedent comparisons | Regulatory semantics |
| INV-006 | Gate logic derives from reporting, never from disposition/workflow state | PCMLTFA s. 7 |
| INV-007 | Disposition deviation -> Consistency Alerts; Reporting deviation -> Defensibility Alerts | Examination readiness |
| INV-008 | MANDATORY and DISCRETIONARY dispositions never compared | SEMA / UNA / Criminal Code s. 83.08 |
| INV-009 | Defensibility Alerts overridden without rationale = examination finding | PCMLTFA s. 73 |
| INV-010 | Confidence never uses hardcoded fallback values | Statistical integrity |
| INV-011 | Non-transferable precedents cannot be classified as supporting | Causal integrity |
| INV-012 | Precedents below similarity floor excluded from all calculations | Statistical integrity |
| INV-013 | All five report sections render for every case | Audit completeness |

---

## 11. ClaimPilot Service Layer

Source: `claimpilot/api/`

The ClaimPilot API exposes the insurance domain through the same React dashboard
consumed by the banking service. The service layer sits on top of the kernel and
insurance domain modules.

### 11.1 Architecture

```
React Dashboard (shared SPA)
        |
        v
claimpilot/api/routes/dashboard.py   <-- 11 dashboard endpoints
        |
        v
claimpilot/api/report_builder.py     <-- v3 pipeline adapter
        |
        +--> kernel.precedent.*       <-- domain-agnostic engine
        +--> domains.insurance_claims.*
```

### 11.2 Dashboard API Contract (11 endpoints)

| Method | Path | Response | Notes |
|--------|------|----------|-------|
| GET | `/api/domain` | `{domain, name, terminology}` | Insurance terminology |
| GET | `/api/stats` | `{total_seeds, demo_cases, policy_shifts, registry_fields, engine_version}` | Dashboard header stats |
| GET | `/api/cases` | `[{id, name, description, category, expected_verdict, key_levers, tags, facts}]` | 31 demo cases |
| GET | `/api/cases/{case_id}` | Single case object | 404 if not found |
| GET | `/api/report/{case_id}/json` | `{format, generated_at, report: ReportViewModel}` | Full v3 precedent report |
| GET | `/api/audit` | Filtered case list | Query params: `q`, `outcome`, `scenario` |
| GET | `/api/policy-shifts` | `[{id, name, description, citation, cases_affected, pct_affected, magnitude}]` | 3 insurance shifts |
| GET | `/api/policy-shifts/{shift_id}/cases` | `{shift_id, shift_name, total_affected, cases: [...]}` | Shadow records per shift |
| GET | `/api/simulate/drafts` | `[{id, name, description, parameter, old_value, new_value, trigger_signals}]` | Available draft shifts |
| POST | `/api/simulate` | `{draft, timestamp, total_cases_evaluated, affected_cases, disposition_changes, magnitude}` | Body: `{draft_id}` |
| POST | `/api/simulate/compare` | `[{draft, affected_cases, disposition_changes, magnitude}]` | Body: `{draft_ids: [...]}` |

### 11.3 Domain Detection

`GET /api/domain` returns the insurance domain context:

```json
{
  "domain": "insurance_claims",
  "name": "ClaimPilot",
  "terminology": {
    "entity": "claim",
    "institution": "insurer",
    "decision_maker": "claims adjuster",
    "review_process": "investigation",
    "escalation_target": "Special Investigations Unit",
    "filing_authority": "FSRA"
  }
}
```

The dashboard uses this to adapt labels (e.g. "transaction" -> "claim",
"compliance officer" -> "claims adjuster").

### 11.4 Report Builder Pipeline

Source: `claimpilot/api/report_builder.py`

`build_report(case, seeds, registry) -> dict` runs a case through the full
v3 engine and returns a `ReportViewModel` dict:

```
1. Map expected_outcome -> proposed disposition (see 11.4.1)
2. Enrich case facts (policy-specific -> standardized registry fields)
3. Layer 1: evaluate_gates()      -- filter to comparable seeds
4. Layer 2: score_similarity()    -- rank seeds, apply floor
5. Layer 2: classify_match_v3()   -- supporting / contrary / neutral
6. Layer 3: compute_governed_confidence() -- four-dimension min()
7. Compute alignment (see 11.4.2)
8. Detect applicable policy shifts
9. Assemble ReportViewModel dict (~40 fields)
```

#### 11.4.1 Disposition Mapping (expected_outcome -> proposed)

The demo case `expected_outcome` string is mapped to an insurance disposition,
then to a v3 canonical disposition for precedent comparison:

```
expected_outcome  ->  proposed_disp_raw     ->  v3 canonical
─────────────────────────────────────────────────────────────
pay               ->  PAY_CLAIM             ->  ALLOW
deny              ->  DENY_CLAIM            ->  BLOCK
investigate       ->  INVESTIGATE           ->  EDD
escalate          ->  INVESTIGATE           ->  EDD
partial           ->  PARTIAL_PAY           ->  ALLOW
request_info      ->  INVESTIGATE           ->  EDD
(default)         ->  PAY_CLAIM             ->  ALLOW
```

#### 11.4.2 Alignment Calculation

Alignment percentage is computed differently for EDD vs terminal dispositions:

- **Terminal (ALLOW / BLOCK)**: `alignment = decisive_supporting / decisive_total * 100`
  where "decisive" means classified as `supporting` or `contrary` (excludes `neutral`).
- **EDD (investigate / escalate / request_info)**: `alignment = investigate_pool / pool_size * 100`
  where `investigate_pool` counts seeds with `v3_disposition == "EDD"`. This avoids
  the 0% problem: INV-005 makes all non-EDD seeds neutral, so `decisive_total` would
  always be 0 and the normal formula would yield 0%.

#### ReportViewModel Shape

| Section | Key Fields |
|---------|-----------|
| Identity | `decision_id`, `case_id`, `timestamp`, `jurisdiction`, `domain`, `engine_version`, `policy_version` |
| Decision | `verdict`, `action`, `decision_status`, `decision_explainer`, `canonical_outcome` |
| Classification | `primary_typology`, `regulatory_status`, `investigation_state` |
| Confidence | `decision_confidence` (Low/Moderate/High), `decision_confidence_score` (0-100), `decision_confidence_reason` |
| Precedent Metrics | `precedent_alignment_pct`, `precedent_match_rate`, `scored_precedent_count`, `total_comparable_pool` |
| Enhanced Precedent (v3) | `confidence_dimensions[]`, `sample_cases[]`, `driver_causality`, `outcome_distribution`, `regime_analysis`, `institutional_posture` |
| Precedent Analysis | `supporting_precedents`, `contrary_precedents`, `neutral_precedents`, `precedent_confidence` |
| Facts | `transaction_facts[]`, `risk_factors[]`, `decision_drivers[]` |
| Escalation | `escalation_summary` |

### 11.5 Fact Enrichment Layer

Demo cases use policy-specific field IDs (e.g. `vehicle.use_at_loss`,
`driver.bac_level`, `dwelling.habitable`) that do not overlap with the 23
standardized registry fields used by seeds. The report builder includes an
enrichment function that derives standardized fields from raw case facts:

| Standardized Field | Derived From |
|-------------------|-------------|
| `claim.coverage_line` | `case.line_of_business` (auto, property, marine, etc.) |
| `claim.claimant_type` | Default `first_party` |
| `claim.amount_band` | `claim.reserve_amount` (banded: 0_5k / 5k_25k / 25k_100k / 100k_500k / over_500k) |
| `claim.occurred_during_policy` | `occurrence.during_policy_period` or `policy.status == "active"` |
| `claim.loss_cause` | `loss.cause` or `loss.primary_cause` or `loss.type`; **auto-derived**: `"collision"` when `driver.impairment_indicated`, `driver.bac_level > 0.05`, `vehicle.use_at_loss ∈ {delivery, rideshare}`, or `loss.racing_activity` |
| `claim.injury_type` | Direct passthrough; **auto-derived**: `"moderate"` for auto coverage line when absent |
| `flag.fraud_indicator` | `loss.intentional_indicators` or `flag.staged_accident` or `injury.self_inflicted` or `driver.bac_level > 0.05` |
| `flag.staged_accident` | Direct passthrough |
| `flag.late_reporting` | Direct passthrough |
| `flag.inconsistent_statements` | Direct passthrough |
| `flag.pre_existing_damage` | `flag.pre_existing_damage` or `condition.preexisting` |
| `screening.siu_referral` | Direct passthrough |
| `evidence.police_report` | `police_report.impaired_charges` |
| `evidence.medical_report` | `condition.last_treatment_date` or `treatment.type` |

Enriched fields are only set when absent — explicit demo case values take
precedence.

### 11.6 Case Categories

Demo cases are classified for the dashboard:

| Category | Mapped From |
|----------|------------|
| `PASS` | `pay`, `deny` outcomes |
| `ESCALATE` | `escalate`, `request_info` outcomes |
| `EDGE` | Name contains "edge", "fraud", "threshold", "boundary" |

### 11.7 SPA Serving

The React dashboard (shared with banking) is served from the same FastAPI
instance:

- `/` — React SPA `index.html`
- `/assets/*` — Static JS/CSS bundles
- `/{path}` — Catch-all for SPA client-side routes (`/cases`, `/seeds`, `/policy-shifts`, `/sandbox`, `/audit`, `/registry`, `/reports`)

API routes are NOT intercepted by the catch-all — only known SPA routes serve `index.html`.

### 11.8 Deployment

```
Dockerfile.claimpilot (repo root)
├── COPY kernel/ + domains/    -> /app/kernel/, /app/domains/
├── COPY claimpilot/           -> /app/claimpilot/
├── COPY dashboard/dist/       -> /app/claimpilot/api/static/dashboard/
└── CMD uvicorn api.main:app --app-dir /app/claimpilot
```

Railway config:
- Root Directory: `/` (blank — repo root)
- Builder: Dockerfile
- Dockerfile Path: `Dockerfile.claimpilot`
- Health check: `/health`

---

## 12. Module Map

### Kernel (27 modules)

```
kernel/
├── foundation/   (12 modules)
│   ├── cell.py              DecisionCell, hashing, CellType enum
│   ├── chain.py             Append-only hash-linked chain
│   ├── genesis.py           Genesis cell creation + 22 checks
│   ├── namespace.py         Hierarchical namespace validation
│   ├── scholar.py           Precedent search and ranking
│   ├── signing.py           Ed25519 signing and verification
│   ├── wal.py               Write-ahead log for crash recovery
│   ├── segmented_wal.py     Segment-based WAL with compaction
│   ├── judgment.py          JudgmentPayload, AnchorFact
│   ├── canon.py             Canonical JSON serialization (RFC 8785)
│   ├── exceptions.py        Exception hierarchy
│   └── policyhead.py        Policy head management
│
├── precedent/   (7 modules)
│   ├── domain_registry.py   FieldDefinition, ComparabilityGate, DomainRegistry
│   ├── domain_loader.py     Dynamic domain discovery
│   ├── precedent_registry.py PrecedentRegistry with temporal queries
│   ├── precedent_scorer.py  v3 similarity scoring + match classification
│   ├── governed_confidence.py Four-dimension confidence model
│   ├── field_comparators.py Five comparison primitives
│   └── comparability_gate.py Gate evaluation engine
│
├── policy/      (3 modules)
│   ├── regime_partitioner.py Signal extraction, shift detection
│   ├── policy_simulation.py PolicySimulator with draft comparison
│   └── shift_tracker.py     Stub for future shift tracking
│
├── evidence/    (2 modules)
│   ├── tribool.py           TriBool (TRUE/FALSE/UNKNOWN)
│   └── evidence_gate.py     Gate stub
│
└── calendars/   (3 modules)
    ├── base.py              HolidayCalendar protocol, BaseCalendar ABC
    ├── us_federal.py        USFederalCalendar
    └── canada_ontario.py    OntarioCalendar
```

### Domains

```
domains/
├── banking_aml/
│   ├── field_registry.py    27 canonical field definitions
│   ├── domain.py            DomainRegistry factory + create_registry alias
│   ├── seed_generator.py    20 scenarios, 1,500 seeds
│   ├── fingerprint.py       Privacy-preserving fingerprint schemas
│   ├── reason_codes.py      ~92 reason codes (5 registries)
│   └── policy_shifts.py     4 policy shifts + shadow projections
│
└── insurance_claims/
    ├── registry.py          24 canonical field definitions
    ├── domain.py            DomainRegistry factory + create_registry alias
    ├── seed_generator.py    22 scenarios, ~1,618 seeds
    ├── reason_codes.py      51 reason codes (5 registries)
    └── policy_shifts.py     3 policy shifts + shadow projections
```

### ClaimPilot Service

```
claimpilot/
├── api/
│   ├── main.py                FastAPI app, lifespan, CORS, SPA serving
│   ├── report_builder.py      v3 pipeline adapter (764 lines)
│   ├── demo_cases.py          31 demo cases across 8 coverage lines
│   ├── template_loader.py     Case template YAML loader
│   └── routes/
│       ├── dashboard.py       11 dashboard endpoints (495 lines)
│       ├── policies.py        Policy CRUD
│       ├── evaluate.py        Claim evaluation
│       ├── demo.py            Demo case routes
│       ├── verify.py          Chain verification
│       ├── memo.py            Memo endpoints
│       └── templates.py       Template routes
├── packs/                     8 policy packs (YAML)
├── precedent/
│   └── cli.py                 Seed generation (2,150 seeds)
├── src/claimpilot/
│   ├── models.py              Pydantic models
│   └── packs/loader.py        PolicyPackLoader
└── templates/                 8 case templates
```

### Backward-Compatible Shims

```
decisiongraph/
├── cell.py                → kernel.foundation.cell
├── chain.py               → kernel.foundation.chain
├── genesis.py             → kernel.foundation.genesis
├── namespace.py           → kernel.foundation.namespace
├── scholar.py             → kernel.foundation.scholar
├── signing.py             → kernel.foundation.signing
├── wal.py                 → kernel.foundation.wal
├── segmented_wal.py       → kernel.foundation.segmented_wal
├── judgment.py            → kernel.foundation.judgment
├── canon.py               → kernel.foundation.canon
├── exceptions.py          → kernel.foundation.exceptions
├── policyhead.py          → kernel.foundation.policyhead
├── precedent_registry.py  → kernel.precedent.precedent_registry
├── precedent_scorer_v3.py → kernel.precedent.precedent_scorer
├── governed_confidence.py → kernel.precedent.governed_confidence
├── field_comparators.py   → kernel.precedent.field_comparators
├── comparability_gate.py  → kernel.precedent.comparability_gate
├── domain_registry.py     → kernel.precedent.domain_registry
├── policy_simulation.py   → kernel.policy.policy_simulation
├── banking_field_registry.py → domains.banking_aml.field_registry
├── banking_domain.py      → domains.banking_aml.domain
├── aml_seed_generator.py  → domains.banking_aml.seed_generator
├── aml_fingerprint.py     → domains.banking_aml.fingerprint
├── aml_reason_codes.py    → domains.banking_aml.reason_codes
└── policy_shift_shadows.py → domains.banking_aml.policy_shifts
```
