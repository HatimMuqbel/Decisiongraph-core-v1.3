# ClaimPilot Architecture

## Overview

ClaimPilot is a **product-agnostic evaluation engine (pack-driven)**. The core engine handles any insurance product without code changes — all product-specific logic lives in YAML policy packs. It provides guided workflows for adjusters (not automation — adjusters decide), surfacing policy rules, enforcing evidence requirements, and capturing reasoning at the moment of evaluation.

**Core Principle**: "The adjuster decides. ClaimPilot recommends and documents."

## Design Principles

1. **Recommendation, not decision** — ClaimPilot recommends; humans decide
2. **Line-agnostic core** — No auto/property/health code in core
3. **Data-driven rules** — All business logic in policy packs (YAML)
4. **Composable conditions** — Full AND/OR/NOT support with TriBool
5. **First-class citations** — Every recommendation cites its authorities
6. **First-class precedents** — Similar cases surfaced for context
7. **Explicit uncertainty** — "Requires judgment" is a valid output
8. **Temporal awareness** — Rules versioned, timelines calculated
9. **Deterministic** — Same inputs → same outputs, always
10. **Auditable** — Complete reasoning chain for every recommendation

## Module Structure

```
claimpilot/
├── src/claimpilot/
│   ├── __init__.py           # Package root, exports all public API
│   ├── exceptions.py         # Exception hierarchy with error codes
│   ├── canon.py              # Canonical JSON for deterministic hashing
│   │
│   ├── models/               # Domain models
│   │   ├── enums.py          # All enumerations
│   │   ├── conditions.py     # TriBool, Condition, Predicate, helpers
│   │   ├── authority.py      # AuthorityRef, AuthorityRule
│   │   ├── policy.py         # Policy, CoverageSection, Exclusion
│   │   ├── claim.py          # ClaimContext, Fact, EvidenceItem
│   │   ├── timeline.py       # TimelineRule, TimelineEvent
│   │   ├── evidence.py       # EvidenceRule, DocumentRequirement
│   │   ├── precedent.py      # PrecedentHit, PrecedentKey
│   │   ├── recommendation.py # RecommendationRecord, ReasoningStep
│   │   └── disposition.py    # FinalDisposition
│   │
│   ├── engine/               # Core services (Phase 3-4)
│   │   ├── condition_evaluator.py
│   │   ├── policy_engine.py
│   │   ├── context_resolver.py
│   │   ├── timeline_calculator.py
│   │   ├── evidence_gate.py
│   │   ├── authority_router.py
│   │   ├── precedent_finder.py
│   │   └── recommendation_builder.py
│   │
│   ├── calendars/            # Holiday calendars
│   │   ├── base.py           # HolidayCalendar protocol
│   │   ├── us_federal.py     # US Federal holidays
│   │   └── canada_ontario.py # Ontario/Canadian holidays (FSRA compliance)
│   │
│   └── packs/                # Policy pack loading (Phase 2)
│       ├── schema.py         # Pydantic validation schemas
│       └── loader.py         # YAML/JSON loader
│
├── tests/                    # Test suite (98 tests)
│   ├── conftest.py           # Pytest fixtures and factories
│   ├── test_models.py        # Model unit tests
│   ├── test_condition_evaluator.py  # Condition evaluation tests
│   ├── test_engine.py        # Integration tests for all engine components
│   └── fixtures/
│       ├── sample_policy.yaml
│       └── sample_claim.json
│
└── packs/examples/           # Example policy packs
    └── auto_insurance_v1.yaml
```

## Core Models

### Enumerations

| Enum | Purpose |
|------|---------|
| `LineOfBusiness` | Insurance lines (auto, property, health, etc.) |
| `ClaimantType` | Relationship to policy (insured, third-party, etc.) |
| `DispositionType` | Recommendation outcomes (pay, deny, escalate, etc.) |
| `RecommendationCertainty` | Confidence level (high, medium, low, requires_judgment) |
| `FactSource` | Origin of facts (policy_system, claimant_statement, etc.) |
| `FactCertainty` | Confidence in facts (confirmed, reported, disputed, etc.) |
| `EvidenceStatus` | Document status (requested, received, verified, etc.) |
| `GateStrictness` | Evidence gate levels |
| `AuthorityType` | Citation types (policy_wording, regulation, etc.) |
| `ConditionOperator` | Logical and comparison operators |
| `TimelineEventType` | Regulatory event types |

### TriBool (Three-Valued Logic)

```python
from claimpilot import TriBool

# Kleene three-valued logic
result = TriBool.TRUE & TriBool.UNKNOWN   # => UNKNOWN
result = TriBool.FALSE & TriBool.UNKNOWN  # => FALSE (False dominates)
result = TriBool.TRUE | TriBool.UNKNOWN   # => TRUE (True dominates)
result = ~TriBool.UNKNOWN                 # => UNKNOWN
```

**Truth Tables:**

```
AND    | TRUE    FALSE   UNKNOWN
-------|------------------------
TRUE   | TRUE    FALSE   UNKNOWN
FALSE  | FALSE   FALSE   FALSE
UNKNOWN| UNKNOWN FALSE   UNKNOWN

OR     | TRUE    FALSE   UNKNOWN
-------|------------------------
TRUE   | TRUE    TRUE    TRUE
FALSE  | TRUE    FALSE   UNKNOWN
UNKNOWN| TRUE    UNKNOWN UNKNOWN

NOT:   TRUE → FALSE, FALSE → TRUE, UNKNOWN → UNKNOWN
```

### Composable Conditions

```python
from claimpilot import AND, OR, NOT, EQ, GT, IN

# Build conditions declaratively
condition = AND(
    EQ("claim.status", "open"),
    GT("claim.amount", 5000),
    OR(
        EQ("claim.type", "collision"),
        EQ("claim.type", "comprehensive"),
    ),
    NOT(EQ("claim.fraud_flag", True)),
)

# Check structure
assert condition.is_logical
assert len(condition.children) == 4
```

### Policy Pack

```python
from claimpilot import Policy, CoverageSection, Exclusion

policy = Policy.create(
    jurisdiction="US-CA",
    line_of_business=LineOfBusiness.AUTO,
    product_code="PAP",
    name="Personal Auto Policy",
    version="2024.1",
    effective_date=date(2024, 1, 1),
)

coverage = CoverageSection(
    id="collision",
    code="Part A",
    name="Collision Coverage",
    description="Covers collision damage",
    limits=CoverageLimits(per_occurrence=Decimal("50000")),
)
policy.coverage_sections.append(coverage)
```

### Authority References (Citations)

```python
from claimpilot import AuthorityRef, AuthorityType

auth = AuthorityRef.create(
    authority_type=AuthorityType.POLICY_WORDING,
    title="Ontario Automobile Policy",
    section="Section 4.2.1",
    source_name="OAP 1",
    quote_excerpt="The insurer shall not pay...",
    full_text="The insurer shall not pay for loss or damage...",
    jurisdiction="CA-ON",
    effective_date=date(2024, 1, 1),
)

# Content hash for verification
assert auth.content_hash is not None
assert auth.verify_content("The insurer shall not pay for loss or damage...")
```

### Recommendation Record

```python
from claimpilot import RecommendationRecord, DispositionType, RecommendationCertainty

recommendation = RecommendationRecord.create(
    claim_id="CLM-001",
    context_id="CTX-001",
    recommended_disposition=DispositionType.PAY,
    disposition_reason="Coverage confirmed, no exclusions apply",
    certainty=RecommendationCertainty.HIGH,
)

# Add citations
recommendation.cite_authority(auth)

# Add reasoning steps
recommendation.add_reasoning_step(ReasoningStep.create(
    sequence=1,
    step_type=ReasoningStepType.COVERAGE_CHECK,
    description="Collision coverage applies",
    result=ReasoningStepResult.PASSED,
))
```

### Final Disposition (Human Decision)

```python
from claimpilot import FinalDisposition

disposition = FinalDisposition.create(
    claim_id="CLM-001",
    recommendation_id=recommendation.id,
    disposition=DispositionType.PAY,
    disposition_reason="Approved per recommendation",
    followed_recommendation=True,
    finalizer_id="USR-001",
    finalizer_role="adjuster",
)

# Seal for audit
disposition.seal()
assert disposition.is_sealed
assert disposition.verify_seal()
```

## Evidence Gates

ClaimPilot separates "block recommendation" from "block finalization":

| Gate Level | Behavior |
|------------|----------|
| `BLOCKING_RECOMMENDATION` | Cannot recommend without this evidence |
| `BLOCKING_FINALIZATION` | Can recommend, but human can't finalize without it |
| `RECOMMENDED` | Proceed with warning |
| `OPTIONAL` | Nice to have |

This supports real workflow:
- Adjusters start early ("likely exclusion, pending proof")
- Finalization requires complete documentation

## Precedent Matching

Precedent matching is **deterministic** (not ML/LLM):

**Feature Vector (PrecedentKey):**
- `jurisdiction`
- `line_of_business`
- `loss_type`
- `coverage_ids_triggered`
- `exclusion_clause_hashes`
- `disposition_type`
- `fact_signature` (sorted set of fact keys)

**Similarity Weights:**
- Coverage type: 25%
- Claim type: 20%
- Policy language: 20%
- Jurisdiction: 15%
- Fact overlap (Jaccard): 15%
- Recency: 5%

**Tie-breakers (explicit, stable):**
1. `similarity_score` (descending)
2. `effective_date` (newest first)
3. `case_id` (lexicographic)

## Policy Provenance

Policy packs remain **human-editable YAML** — no sealing required. But each recommendation includes **provenance hashes** proving which exact rules were applied.

**RecommendationRecord fields:**
- `policy_pack_id` — which policy was used (e.g., "CA-ON-OAP1-2024")
- `policy_pack_version` — human-readable version string (e.g., "2024.1")
- `policy_pack_hash` — SHA-256 of canonical JSON rendering
- `authority_hashes` — per-citation hashes for each policy clause cited
- `policy_pack_loaded_at` — when the policy pack was loaded
- `evaluated_at` — when the recommendation was generated
- `engine_version` — ClaimPilot version (git SHA or semver)

**AuthorityCitation:**
```python
@dataclass
class AuthorityCitation:
    authority_ref_id: str
    authority_type: AuthorityType
    section_ref: str
    excerpt: str
    excerpt_hash: str           # SHA-256 of normalized excerpt
    effective_as_of: date
    cited_at: datetime
```

**Hash computation:**
```python
from claimpilot import compute_policy_pack_hash, excerpt_hash, normalize_excerpt

# Hash entire policy pack
policy_hash = compute_policy_pack_hash(policy)

# Hash individual excerpt (normalized for consistency)
# Normalization: Unicode NFKC, whitespace collapse, strip — NO lowercasing
normalized = normalize_excerpt("  The Insurer\n  shall not pay...  ")
# -> "The Insurer shall not pay..."  (case preserved for legal text fidelity)
hash = excerpt_hash("The Insurer shall not pay...")
```

**What the hash proves:**
- Which exact policy text was loaded at recommendation time
- Whitespace-invariant comparison (formatting changes don't break verification)
- Deterministic: same policy rules → same hash (RFC 8785 canonical JSON)

**What the hash does NOT prove:**
- That the policy file hasn't been modified since (no file signing)
- That the policy was the "official" version (no PKI chain)
- Tamper-proofing against malicious actors (lightweight provenance, not cryptographic sealing)

**Design rationale:** This provides "defensible byproduct" — enough to prove what was relied upon during audit — without turning policy editing into a cryptographic ceremony. For stronger guarantees, integrate with external signing/versioning systems.

This ensures recommendations remain verifiable even if policy packs evolve.

## Exception Hierarchy

```
ClaimPilotError (CP_INTERNAL_ERROR)
├── PolicyLoadError (CP_POLICY_LOAD_ERROR)
├── PolicyValidationError (CP_POLICY_VALIDATION_ERROR)
├── PolicyVersionMismatch (CP_POLICY_VERSION_MISMATCH)
├── ClaimContextError (CP_CLAIM_CONTEXT_ERROR)
├── MissingFactError (CP_MISSING_FACT)
├── FactConflictError (CP_FACT_CONFLICT)
├── ConditionEvaluationError (CP_CONDITION_EVAL_ERROR)
├── EvidenceGateError (CP_EVIDENCE_GATE_BLOCKED)
├── TimelineCalculationError (CP_TIMELINE_ERROR)
├── DeadlineExceededError (CP_DEADLINE_EXCEEDED)
├── AuthorityNotFoundError (CP_AUTHORITY_NOT_FOUND)
├── PrecedentMatchError (CP_PRECEDENT_MATCH_ERROR)
├── RecommendationError (CP_RECOMMENDATION_ERROR)
├── DispositionError (CP_DISPOSITION_ERROR)
└── EscalationRequiredError (CP_ESCALATION_REQUIRED)
```

## Canonical JSON

For deterministic hashing and comparison:

```python
from claimpilot import canonical_json, content_hash

data = {"b": 1, "a": 2}
json_str = canonical_json(data)  # '{"a":2,"b":1}' (sorted keys, no whitespace)
hash_value = content_hash(data)  # SHA-256 hex string
```

## Engineering Hygiene

- **UUIDs**: `uuid.UUID` internally, serialize as `str`
- **Timestamps**: `datetime` timezone-aware UTC always
- **Determinism**: Same inputs → same outputs (verified by tests)

## Audit Guarantees

ClaimPilot is designed to withstand scrutiny from regulators, legal, and compliance.

### Schema Strictness

- All schemas use `extra="forbid"` to reject unknown fields at load time
- Misspelled fields caught immediately (no silent data loss)
- Reference integrity validated: exclusions must reference existing coverages
- Duplicate IDs rejected at load time

### Deterministic Hashing

- Lists sorted by `id` for stable ordering (RFC 8785 canonical JSON)
- Whitespace normalized (not lowercased) for excerpt hashing
- Same policy content → same hash, regardless of insertion order

### What the Hash Proves

- Recommendation was generated using specific policy pack version
- Exact policy text was loaded at recommendation time
- Any content change (wording, rules, version) produces different hash
- Tampering is cryptographically detectable

### What the Hash Does NOT Prove

- Archive integrity (requires WORM/object lock storage)
- Time of creation (use `evaluated_at` timestamp with trusted clock)
- That the policy was the "official" version (no PKI chain)

### Audit Trail Fields

```python
RecommendationRecord:
    policy_pack_id          # Which policy was used
    policy_pack_version     # Human-readable version
    policy_pack_hash        # SHA-256 of canonical policy
    policy_pack_loaded_at   # When policy was loaded
    evaluated_at            # When recommendation generated
    engine_version          # ClaimPilot version (git SHA)
    authority_hashes        # Per-citation excerpt hashes
```

## Implementation Status

### Phase 1: Models ✅
- All 14 model files implemented
- Full type hints and docstrings
- TriBool with Kleene logic truth tables
- Composable conditions (AND/OR/NOT)
- First-class versioned citations (AuthorityRef)
- Precedent matching with deterministic scoring

### Phase 2: Schema & Loader ✅
- Pydantic schemas for YAML validation
- Policy pack loader (YAML/JSON)
- Holiday calendars:
  - `HolidayCalendar` protocol
  - US Federal holidays
  - Ontario/Canadian holidays (FSRA compliance)

### Phase 3: Core Engine ✅
- `ConditionEvaluator` — Field path resolution, TriBool evaluation
- `PolicyEngine` — Load and manage policy packs
- `ContextResolver` — Resolve applicable coverages/exclusions
- `TimelineCalculator` — Business day calculation, FSRA deadlines

### Phase 4: Recommendation Flow ✅
- `EvidenceGate` — Two-stage gates (blocking recommendation vs finalization)
- `AuthorityRouter` — Escalation routing based on rules
- `PrecedentFinder` — Deterministic weighted similarity matching
- `RecommendationBuilder` — Full recommendation with reasoning chain

### Phase 5: Testing ✅
- 105 tests passing
- Model unit tests (TriBool, Condition, Authority, Policy, Claim, Timeline, Precedent, Recommendation, Disposition)
- Condition evaluator tests (field paths, operators, TriBool evaluation, missing facts)
- Engine integration tests (ContextResolver, TimelineCalculator, EvidenceGate, RecommendationBuilder)
- Precedent scoring tests (Jaccard similarity, sorting, tie-breakers)
- Determinism verification (conditions, context resolution, recommendations)

### Phase 6: Documentation ✅
- `README.md` — Quick start and overview
- `CLAIMPILOT.md` — Architecture documentation
- `pyproject.toml` — Project configuration with dev tools
