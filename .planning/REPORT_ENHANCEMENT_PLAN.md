# Report Enhancement Plan: Bank-Grade Reports

## Goal
Transform the current simple report into a comprehensive, auditable report matching the target format with 4-gate protocol, policy citations, evidence anchoring, and evaluation metrics.

---

## Phase 1: Policy Citation Infrastructure

### 1.1 Enhance Pack Schema
Add structured citations to signals and mitigations in pack YAML:

```yaml
signals:
  - code: HIGH_VALUE_TRANSACTION
    name: High-Value Transaction
    severity: MEDIUM
    policy_refs:
      - authority: FINTRAC
        document: "Proceeds of Crime (Money Laundering) Act"
        section: "3. Reporting requirements - Large cash transactions"
        url: "https://www.fintrac-canafe.gc.ca/guidance..."
        citation_hash: null  # Auto-computed
```

### 1.2 Create Citation Registry
New module: `decisiongraph/citations.py`

```python
@dataclass
class PolicyCitation:
    authority: str           # FINTRAC, FATF, EU, etc.
    document: str            # Full document name
    section: str             # Section reference
    url: Optional[str]       # Source URL
    citation_hash: str       # SHA256 of (authority + section)

class CitationRegistry:
    def get_citations_for_signal(self, signal_code: str) -> list[PolicyCitation]
    def compute_citation_quality(self, signals: list, citations: dict) -> float
```

### 1.3 Embed Citations in Cells
When signal cells are created, attach citation metadata:

```python
signal_cell = Cell(
    cell_type=CellType.SIGNAL,
    predicate="signal.fired",
    object={
        "code": "HIGH_VALUE_TRANSACTION",
        "severity": "MEDIUM",
        "citations": [
            {"authority": "FINTRAC", "section": "3.1", "hash": "584..."}
        ]
    }
)
```

---

## Phase 2: Evidence Anchoring

### 2.1 Link Mitigations to Evidence
When mitigations fire, capture the source evidence:

```python
mitigation_cell = Cell(
    cell_type=CellType.MITIGATION,
    predicate="mitigation.applied",
    object={
        "code": "MF_TXN_002",
        "name": "Tier-1 VASP Provenance",
        "weight": "-0.50",
        "evidence_anchors": [
            {
                "field": "crypto_source",
                "value": "KRAKEN",
                "source": "case_evidence.crypto_source",
                "cell_id": "abc123..."
            }
        ],
        "citation_hash": "5bf53cbbb5e73b51..."
    }
)
```

### 2.2 Evidence Anchor Grid
Build a summary grid for the report:

```
Offset Type              Data Anchor              Weight
------------------------------------------------------------
Inherent Risk            All Signals              +1.00
Proactive Transparency   ubo_proactive_disclosu   -0.20
Tax Compliance           tax_compliance           -0.15
Tier-1 VASP Provenance   crypto_source            -0.50
------------------------------------------------------------
RESIDUAL SCORE                                    0.10
```

---

## Phase 3: Multi-Gate Protocol

### 3.1 Gate Definitions
Add to pack schema:

```yaml
gates:
  gate_1_typology:
    name: "Contextual Typology"
    description: "Classify case into typology"
    typology_classes:
      - TECH_INVESTMENT
      - TRADE_BASED_ML
      - REAL_ESTATE_ML
      - SHELL_COMPANY
    forbidden_typologies:
      - MARITIME_DECEPTION
      - HUMAN_TRAFFICKING

  gate_2_inherent_mitigating:
    name: "Inherent Risks + Mitigating Factors"
    description: "Identify risks and apply mitigations"

  gate_3_residual:
    name: "Residual Risk Calculation"
    description: "Compute final score with evidence grid"

  gate_4_integrity:
    name: "Integrity Audit"
    checks:
      - typology_match
      - verdict_alignment
      - language_audit
```

### 3.2 Gate Evaluation Engine
New module: `decisiongraph/gates.py`

```python
class GateEvaluator:
    def evaluate_gate_1(self, case: CaseBundle) -> GateResult
    def evaluate_gate_2(self, signals: list, mitigations: list) -> GateResult
    def evaluate_gate_3(self, inherent: Decimal, mitigations: list) -> GateResult
    def evaluate_gate_4(self, verdict: str, score: Decimal, typology: str) -> GateResult
```

---

## Phase 4: Enhanced Report Template

### 4.1 Report Sections
Create new report template with all sections:

```python
REPORT_SECTIONS = [
    "header",                    # Alert ID, Priority, Source
    "case_summary",              # Customer profile
    "transaction_details",       # Amount, beneficiary, bank
    "beneficial_ownership",      # UBO table with PEP status
    "corporate_structure",       # Ownership chain
    "screening_results",         # Sanctions, PEP, Adverse, SOW, Crypto
    "documentation_status",      # Checklist with score
    "risk_indicators",           # Numbered signal list
    "section_10b_mitigating",    # 4-GATE PROTOCOL
    "policy_citations",          # Per-signal citations
    "citation_quality",          # Coverage summary
    "decision",                  # Action, Confidence, Tier
    "required_actions",          # Generated actions with SLA
    "feedback_scores",           # Evaluation metrics
    "audit_trail",               # Timestamps
    "case_integrity",            # Hashes
    "regulatory_references",     # Applicable regulations
]
```

### 4.2 Template Engine
New module: `decisiongraph/report_template.py`

```python
class ReportTemplate:
    def __init__(self, template_name: str = "full"):
        self.sections = REPORT_SECTIONS

    def render(self,
               case: CaseBundle,
               eval_result: EvalResult,
               gates: list[GateResult],
               citations: CitationRegistry) -> str
```

### 4.3 CLI Flag
Add template selection:

```bash
./dg run-case --case case.json --pack pack.yaml --template full
./dg run-case --case case.json --pack pack.yaml --template summary
```

---

## Phase 5: Evaluation Metrics

### 5.1 Confidence Calculation
```python
def compute_confidence(eval_result: EvalResult) -> Decimal:
    factors = [
        ("citation_coverage", 0.25),    # % signals with citations
        ("evidence_completeness", 0.25), # % evidence anchors
        ("gate_pass_rate", 0.25),        # % gates passed
        ("documentation_score", 0.25),   # % docs on file
    ]
    return weighted_average(factors)
```

### 5.2 Feedback Scores (Opik-style)
```python
@dataclass
class FeedbackScores:
    confidence: Decimal
    citation_quality: Decimal      # signals with citations / total signals
    signal_coverage: Decimal       # signals evaluated / total pack signals
    evidence_completeness: Decimal # evidence with anchors / total evidence
    decision_clarity: Decimal      # 1.0 if auto-archive, 0.5 if needs review
    documentation_completeness: Decimal  # docs on file / required docs
```

---

## Phase 6: Required Actions Generator

### 6.1 Action Rules
Add to pack:

```yaml
required_actions:
  - trigger: verdict == "ANALYST_REVIEW"
    actions:
      - "Complete case review and document findings"
      - "Update customer risk rating if warranted"
    sla_hours: 168

  - trigger: signal == "SANCTIONS_POSSIBLE_MATCH"
    actions:
      - "Escalate to Sanctions Compliance"
      - "Obtain additional documentation from customer"
    sla_hours: 24
```

### 6.2 Action Generator
```python
def generate_required_actions(verdict: str, signals: list, pack: Pack) -> list[Action]:
    actions = []
    for rule in pack.required_actions:
        if eval_trigger(rule.trigger, verdict, signals):
            actions.extend(rule.actions)
    return actions
```

---

## Implementation Order

| Phase | Deliverable | Effort | Priority |
|-------|------------|--------|----------|
| 1.1 | Pack schema for citations | 2h | HIGH |
| 1.2 | CitationRegistry class | 3h | HIGH |
| 4.1 | Report section definitions | 2h | HIGH |
| 4.2 | ReportTemplate class | 4h | HIGH |
| 2.1 | Evidence anchoring in cells | 3h | MEDIUM |
| 2.2 | Evidence Anchor Grid renderer | 2h | MEDIUM |
| 3.1 | Gate definitions in pack | 2h | MEDIUM |
| 3.2 | GateEvaluator class | 4h | MEDIUM |
| 5.1 | Confidence calculation | 2h | MEDIUM |
| 5.2 | FeedbackScores class | 2h | MEDIUM |
| 6.1 | Required actions in pack | 1h | LOW |
| 6.2 | Action generator | 2h | LOW |

**Total estimated effort: ~29 hours**

---

## Files to Create/Modify

### New Files
```
decisiongraph/
├── citations.py          # PolicyCitation, CitationRegistry
├── gates.py              # GateEvaluator, GateResult
├── report_template.py    # ReportTemplate, section renderers
├── feedback.py           # FeedbackScores, confidence calculation
└── actions.py            # RequiredAction, ActionGenerator
```

### Modified Files
```
decisiongraph/
├── cli.py                # Add --template flag, use ReportTemplate
├── pack.py               # Add citations, gates, required_actions
└── rules.py              # Attach citations when signals fire
```

### Pack Updates
```
packs/
└── fincrime_canada.yaml  # Add structured citations to all signals
```

---

## Sample Output After Enhancement

```
================================================================================
TRANSACTION MONITORING ALERT REPORT
Alert ID: AML-2026-00789
================================================================================

================================================================================
CASE SUMMARY
================================================================================
Customer:       Maria Rodriguez
Customer ID:    CUST-12345
Type:           INDIVIDUAL
Country:        CA
Risk Rating:    MEDIUM

================================================================================
SECTION 10B: MITIGATING FACTORS ANALYSIS
================================================================================

GATE 1: CONTEXTUAL TYPOLOGY
--------------------------------------------------------------------------------
   Typology Class: STRUCTURING_POTENTIAL
   Forbidden Typologies: NONE DETECTED

GATE 2: INHERENT RISKS DETECTED
--------------------------------------------------------------------------------
   TXN-01: Transaction just below threshold ($9,900)
   GEO-01: High-risk jurisdiction (Panama)
   STR-01: Multiple cash deposits

GATE 2: MITIGATING FACTORS (Pause & Pivot)
--------------------------------------------------------------------------------
   MF_SCREEN_FALSE_POSITIVE: Confirmed False Positive
      Data: screening.disposition: false_positive (source: SCR-2026-001)
      Impact: -0.50 Risk Weight applied
      Citation: 5bf53cbbb5e73b51...

GATE 3: RESIDUAL RISK CALCULATION
--------------------------------------------------------------------------------
   EVIDENCE ANCHOR GRID:
   ------------------------------------------------------------
   Offset Type              Data Anchor              Weight
   ------------------------------------------------------------
   Inherent Risk            All Signals              +12.25
   False Positive Screen    screening.disposition    -0.50
   ------------------------------------------------------------
   RESIDUAL SCORE                                    11.75

   Residual Score: 11.75 (HIGH)
   Threshold Gate: STR_CONSIDERATION

GATE 4: INTEGRITY AUDIT
--------------------------------------------------------------------------------
   Typology Match:     PASS
   Verdict Alignment:  PASS (Score 11.75 → STR_CONSIDERATION)
   Language Audit:     PASS
   Overall Integrity:  PASS

================================================================================
POLICY CITATIONS
================================================================================
Signal: TXN_JUST_BELOW_THRESHOLD (1 citation)
--------------------------------------------------------------------------------
1. FINTRAC
   Section: Guideline 2 - Structuring indicators
   SHA256: a1b2c3d4...

Signal: GEO_TAX_HAVEN (1 citation)
--------------------------------------------------------------------------------
1. FINTRAC
   Section: Guideline 6 - High-risk jurisdictions
   SHA256: e5f6g7h8...

================================================================================
CITATION QUALITY SUMMARY
================================================================================
Total Citations:    19
Signals Covered:    19/19
Citation Quality:   100%

================================================================================
DECISION
================================================================================
Action:         STR_CONSIDERATION
Confidence:     78%
Tier:           3
Escalate To:    COMPLIANCE_OFFICER

Rationale:
  1. Residual risk 11.75 exceeds STR threshold (1.00)
  2. Multiple structuring indicators detected
  3. High-risk jurisdiction exposure (Panama)
  4. STR filing determination required per PCMLTFR s. 9

================================================================================
REQUIRED ACTIONS
================================================================================
  1. Formal STR determination required
  2. Document grounds for reasonable suspicion
  3. Escalate to Compliance Officer within 5 business days

SLA: 120 hours

================================================================================
FEEDBACK SCORES
================================================================================
  Score                          Value    Assessment
  ------------------------------ -------- --------------------------
  confidence                     0.78     Navigation confidence
  citation_quality               1.00     19/19 signals cited
  signal_coverage                1.00     All signals evaluated
  evidence_completeness          0.85     Most evidence anchored
  decision_clarity               0.50     Needs human review
  documentation_completeness     0.75     6/8 documents on file

================================================================================
AUDIT TRAIL
================================================================================
Case Created:     2026-01-28T14:30:00Z
Report Generated: 2026-01-29T16:52:06Z
Engine Version:   1.0.0
Pack Version:     1.0.0
Pack Hash:        390c23d3d389fb48...
Report Hash:      b69107bb270616ff...

================================================================================
END OF REPORT
================================================================================
```

---

## Next Step

Ready to implement? Start with Phase 1 (Policy Citations) + Phase 4 (Report Template) as they provide the most visible improvement.
