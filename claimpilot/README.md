# ClaimPilot

**Universal Insurance Claims Decision Guidance Framework**

ClaimPilot provides guided workflows for insurance claims adjusters. It produces **recommendations**, not decisions — the human adjuster decides.

## Core Principle

> **"The adjuster decides. ClaimPilot recommends and documents."**

## Features

- **Line-of-business agnostic** — Works for auto, property, health, workers comp, liability, and more
- **Policy rule surfacing** — Surfaces applicable coverages and exclusions based on claim context
- **Evidence requirement enforcement** — Gates recommendations on required documentation
- **Reasoning capture** — Full audit trail at the moment of evaluation
- **Escalation routing** — Configurable authority rules for complex cases
- **Citation of authorities** — First-class citations to policy wording, regulations, guidelines
- **Precedent surfacing** — Deterministic matching of similar past cases

## Installation

```bash
pip install claimpilot
```

For development:

```bash
pip install claimpilot[dev]
```

## Quick Start

```python
from claimpilot import (
    # Enums
    LineOfBusiness, ClaimantType, DispositionType,
    # Conditions
    TriBool, AND, OR, EQ,
    # Models
    Policy, ClaimContext, RecommendationRecord,
)

# Three-valued logic for missing facts
result = TriBool.TRUE & TriBool.UNKNOWN  # => TriBool.UNKNOWN
result = TriBool.FALSE & TriBool.UNKNOWN  # => TriBool.FALSE (False dominates)

# Build composable conditions
condition = AND(
    EQ("claim.status", "open"),
    OR(
        EQ("claim.type", "collision"),
        EQ("claim.type", "comprehensive"),
    ),
)

# Create recommendations with full audit trail
recommendation = RecommendationRecord.create(
    claim_id="CLM-001",
    context_id="CTX-001",
    recommended_disposition=DispositionType.PAY,
    disposition_reason="Coverage confirmed, no exclusions apply",
    certainty=RecommendationCertainty.HIGH,
)
```

## Architecture

```
claimpilot/
├── src/claimpilot/
│   ├── models/           # Domain models (Policy, Claim, Recommendation, etc.)
│   ├── engine/           # Core services (PolicyEngine, ConditionEvaluator, etc.)
│   ├── calendars/        # Holiday calendars for business days
│   ├── packs/            # Schema validation and policy pack loading
│   ├── exceptions.py     # Exception hierarchy
│   └── canon.py          # Canonical JSON for deterministic hashing
├── tests/                # Comprehensive test suite
└── packs/examples/       # Example policy packs
```

## Key Models

| Model | Purpose |
|-------|---------|
| `Policy` | Coverage rules loaded from YAML |
| `ClaimContext` | Resolved context for a claim |
| `CoverageSection` | Individual coverage within policy |
| `Exclusion` | Condition that negates coverage |
| `Condition` | Composable boolean (AND/OR/NOT) |
| `TriBool` | Three-valued logic (TRUE/FALSE/UNKNOWN) |
| `Fact` | Discrete claim information |
| `EvidenceItem` | Documentation supporting evaluation |
| `AuthorityRef` | Citation to policy/regulation |
| `PrecedentHit` | Similar past case |
| `RecommendationRecord` | System recommendation |
| `FinalDisposition` | Human's actual decision |

## Three-Valued Logic (TriBool)

ClaimPilot uses Kleene three-valued logic for conditions that may have missing facts:

| AND | TRUE | FALSE | UNKNOWN |
|-----|------|-------|---------|
| TRUE | TRUE | FALSE | UNKNOWN |
| FALSE | FALSE | FALSE | FALSE |
| UNKNOWN | UNKNOWN | FALSE | UNKNOWN |

| OR | TRUE | FALSE | UNKNOWN |
|----|------|-------|---------|
| TRUE | TRUE | TRUE | TRUE |
| FALSE | TRUE | FALSE | UNKNOWN |
| UNKNOWN | TRUE | UNKNOWN | UNKNOWN |

| NOT |  |
|-----|--|
| TRUE | FALSE |
| FALSE | TRUE |
| UNKNOWN | UNKNOWN |

## Two-Stage Evidence Gates

Evidence requirements support two blocking levels:

- `BLOCKING_RECOMMENDATION` — Cannot recommend without this evidence
- `BLOCKING_FINALIZATION` — Can recommend, but human can't finalize without it
- `RECOMMENDED` — Proceed with warning
- `OPTIONAL` — Nice to have

## Deterministic Precedent Matching

Precedent matching uses weighted factors (not ML/LLM):

- Coverage type: 25%
- Claim type: 20%
- Policy language: 20%
- Jurisdiction: 15%
- Fact overlap (Jaccard): 15%
- Recency: 5%

## Ontario / FSRA Compliance

ClaimPilot includes specific support for Ontario (Canada) insurance regulation:

- **Ontario Holiday Calendar** — Business day calculations exclude Ontario statutory holidays
- **FSRA Timeline Rules** — Built-in support for Financial Services Regulatory Authority deadlines:
  - 3 business days to acknowledge claim
  - 10 business days to request additional information
  - 60 calendar days for coverage decision
  - 15 business days for payment after approval

```python
from claimpilot.calendars import OntarioCalendar
from claimpilot.engine import TimelineCalculator, add_business_days

# Use Ontario calendar for deadline calculations
calculator = TimelineCalculator(calendar=OntarioCalendar())

# Quick helper
deadline = add_business_days(date.today(), 3)  # Uses Ontario calendar by default
```

## Running Tests

```bash
pytest tests/ -v  # 98 tests
```

## Verification

```bash
# Install in development mode
pip install -e ".[dev]"

# Verify imports
python -c "from claimpilot import *; print('All imports OK')"

# Run full test suite
pytest tests/ -v --cov=claimpilot

# Type checking
mypy src/claimpilot/
```

## License

Proprietary
