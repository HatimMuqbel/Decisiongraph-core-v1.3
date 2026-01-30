# DecisionGraph v2.1.1 — Bank-Grade AML/KYC Decision Engine

## What This Is

DecisionGraph is a **bank-grade AML/KYC decision engine** implementing a dual-gate architecture that makes false escalation structurally impossible. It provides deterministic, auditable decisions for transaction monitoring and suspicious activity reporting under Canadian PCMLTFA regulations.

**Current Release: v2.1.1**
- Engine Version: 2.1.1
- Policy Version: 1.0.0
- Schema Version: 1.0.0

## Core Value

**Zero-false-escalation by design.** Every decision is:
- **Reproducible** — Same input + same policy = identical output
- **Auditable** — Full 6-layer taxonomy breakdown with rationale
- **Regulator-ready** — PCMLTFA s.7 compliant with FINTRAC indicator mapping
- **Hash-locked** — Input hash, decision ID, and policy hash in every output

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      API SERVICE (FastAPI)                          │
│  /decide • /health • /ready • /version • /policy • /schemas         │
├─────────────────────────────────────────────────────────────────────┤
│                      DUAL-GATE DECISION SYSTEM                      │
│  ┌─────────────────────────┐  ┌─────────────────────────┐          │
│  │ GATE 1: Zero-False-Esc  │  │ GATE 2: Positive STR    │          │
│  │ "Are we ALLOWED?"       │→ │ "Are we OBLIGATED?"     │          │
│  │ Sections A-G            │  │ Sections 1-5            │          │
│  └─────────────────────────┘  └─────────────────────────┘          │
├─────────────────────────────────────────────────────────────────────┤
│                      6-LAYER DECISION TAXONOMY                      │
│  L1:FACTS → L2:OBLIGATIONS → L3:INDICATORS → L4:TYPOLOGIES →       │
│  L5:MITIGATIONS → L6:SUSPICION                                      │
├─────────────────────────────────────────────────────────────────────┤
│                      CORE ENGINE (Python)                           │
│  escalation_gate.py • str_gate.py • decision_pack.py                │
└─────────────────────────────────────────────────────────────────────┘
```

## Dual-Gate Decision System

### Gate 1: Zero-False-Escalation Checklist
**Purpose:** "Are we ALLOWED to escalate?"

| Section | Name | Rule |
|---------|------|------|
| A | Fact-Level Hard Stop | Sanctions MATCH, false docs, refusal, adverse media ML/TF |
| B | Instrument & Context | Instrument correctly classified, no mismatched typologies |
| C | Obligation Isolation | Obligations (PEP, EDD) NOT used as suspicion |
| D | Indicator Corroboration | 2+ corroborated indicators OR behavioral evidence |
| E | Typology Maturity | ESTABLISHED or CONFIRMED (not FORMING) |
| F | Mitigation Override | If 3+ mitigations explain behavior → BLOCK |
| G | Suspicion Definition | Intent OR deception OR sustained pattern |

**Two Escalation Paths:**
- **Path 1 - HARD STOP:** Section A passes → Immediate escalation (sanctions, false docs)
- **Path 2 - BEHAVIORAL:** Sections B-G all pass → Behavioral suspicion confirmed

### Gate 2: Positive STR Checklist
**Purpose:** "Are we OBLIGATED to report?"

| Section | Name | Requirement |
|---------|------|-------------|
| 1 | Legal Suspicion Threshold | Intent + deception OR pattern present |
| 2 | Evidence Quality | Fact-based, specific, reproducible |
| 3 | Mitigation Failure | Mitigations fail to explain behavior |
| 4 | Typology Confirmation | (Optional) Typology CONFIRMED |
| 5 | Regulatory Reasonableness | Regulator would expect STR |

### Absolute Rules (NO EXCEPTIONS)
```
✗ PEP status alone can NEVER escalate
✗ Cross-border alone can NEVER escalate
✗ Risk score alone can NEVER escalate
✗ "High confidence" can NEVER override facts
✗ "Compliance comfort" is NOT a reason
```

## Decision Outcomes

| Verdict | Action | STR Required | Description |
|---------|--------|--------------|-------------|
| PASS | CLOSE | NO | No escalation needed |
| PASS_WITH_EDD | CLOSE_WITH_EDD_RECORDED | NO | EDD obligation satisfied |
| ESCALATE | ESCALATE_TO_ANALYST | NO | Requires analyst review |
| STR | FILE_STR | YES | Suspicious Transaction Report required |
| HARD_STOP | BLOCK_AND_ESCALATE | YES | Immediate block + STR |

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Liveness probe (process alive) |
| `/ready` | GET | Readiness probe (schemas + policy loaded) |
| `/version` | GET | Version info with commit + policy hash |
| `/policy` | GET | Policy info with absolute rules |
| `/schemas` | GET | Schema versions (optionally with content) |
| `/decide` | POST | Run decision engine, returns Decision Pack |
| `/validate` | POST | Validate input against schema |

## Decision Pack Output

Every `/decide` response includes:

```json
{
  "meta": {
    "engine_version": "2.1.1",
    "policy_version": "1.0.0",
    "engine_commit": "e37d49e",
    "policy_hash": "a4091b2ffb119dd1",
    "input_hash": "5f2acc5c3d80a177...",
    "decision_id": "cef4491f1cca08f7",
    "case_id": "PAIN-VALIDATION-001",
    "jurisdiction": "CA"
  },
  "decision": {
    "verdict": "PASS_WITH_EDD",
    "action": "CLOSE_WITH_EDD_RECORDED",
    "escalation": "PROHIBITED",
    "str_required": "NO",
    "path": null,
    "priority": "MEDIUM"
  },
  "layers": {
    "layer1_facts": { ... },
    "layer2_obligations": { ... },
    "layer3_indicators": { ... },
    "layer4_typologies": { ... },
    "layer5_mitigations": { ... },
    "layer6_suspicion": { ... }
  },
  "gates": {
    "gate1": { "decision": "PROHIBITED", "sections": {...} },
    "gate2": { "decision": "PROHIBITED", "sections": {...} }
  },
  "rationale": {
    "summary": "Pass with EDD. Regulatory obligations satisfied.",
    "str_rationale": null,
    "non_escalation_justification": "...",
    "absolute_rules_validated": [...],
    "regulatory_citations": ["PCMLTFA s.7"]
  },
  "compliance": {
    "jurisdiction": "CA",
    "legislation": "PCMLTFA",
    "str_filing_deadline_days": null,
    "fintrac_indicators_matched": []
  }
}
```

## Release Infrastructure

```
release/
├── CHANGELOG.md           # Version history + rollback procedures
├── runbook.md             # Operational documentation
├── config.example.yaml    # Configuration template
├── SBOM.spdx.json         # Software bill of materials
├── provenance.txt         # Build attestation
├── input_schema.json      # Locked input contract
├── output_schema.json     # Locked output contract
├── golden/                # Expected outputs for regression
└── test_corpus/           # Pinned test cases
```

## Golden Test Harness

```bash
# Run golden tests (must pass for release)
python scripts/run_corpus.py

# Update goldens after intentional changes
python scripts/run_corpus.py --update-goldens

# Validate schemas
python -m cli.validate --corpus test_corpus/cases/
```

**Current Status:** 3/3 golden tests passing
- PAIN-VALIDATION-001: PASS_WITH_EDD
- ESCALATE-HARD-STOP-001: STR (Path 1)
- ESCALATE-BEHAVIORAL-001: STR (Path 2)

## Deployment

### Docker

```bash
# Build
docker build -t decisiongraph:2.1.1 -f docker/Dockerfile .

# Run
docker run -d -p 8000:8000 decisiongraph:2.1.1

# Health check
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DG_ENGINE_VERSION` | 2.1.1 | Engine version |
| `DG_POLICY_VERSION` | 1.0.0 | Policy pack version |
| `DG_JURISDICTION` | CA | Default jurisdiction |
| `DG_LOG_LEVEL` | INFO | Logging verbosity |
| `DG_DOCS_ENABLED` | true | Enable /docs endpoint |
| `DG_MAX_REQUEST_SIZE` | 1048576 | Max request size (bytes) |

## Observability

### Structured JSON Logging

Every decision logged with:
```json
{
  "timestamp": "2026-01-30T00:46:18Z",
  "level": "INFO",
  "message": "Decision complete",
  "request_id": "263f8702",
  "external_id": "PAIN-VALIDATION-001",
  "input_hash": "5f2acc5c3d80a177",
  "decision_id": "cef4491f1cca08f7",
  "verdict": "PASS_WITH_EDD",
  "duration_ms": 7
}
```

### Response Headers
- `X-Request-ID` — Unique request identifier for tracing

## Test Corpus

| Case Type | Count | Description |
|-----------|-------|-------------|
| PAIN | 15 | False positive prevention (must NOT escalate) |
| ESCALATE | 10 | True positive detection (must escalate) |
| **Total** | **25** | Full dual-gate validation |

All 25 cases pass in `test_corpus/run_test_corpus.py`.

## Validation Reports

Human-readable E2E reports in `validation_reports/`:
1. `01_PAIN_CASE_PEP_Legal_Fees.txt` — PEP + cross-border, no suspicion
2. `02_HARD_STOP_Sanctions_Match.txt` — Path 1 escalation
3. `03_BEHAVIORAL_STR_Conflicting_Explanations.txt` — Path 2 escalation
4. `04_STRUCTURING_Maple_Leaf_Corp.txt` — Cash structuring
5. `05_PAIN_PEP_Marco_DeLuca.txt` — Foreign PEP, EDD satisfied
6. `06_LAYERING_Crypto_Cash_Wire.txt` — Multi-instrument layering

## Project Structure

```
decisiongraph-complete/
├── src/decisiongraph/
│   ├── escalation_gate.py    # Gate 1: Zero-False-Escalation
│   ├── str_gate.py           # Gate 2: Positive STR
│   ├── decision_pack.py      # JSON output generator
│   └── report_standards.py   # FINTRAC indicators, wording
├── service/
│   └── main.py               # FastAPI service
├── cli/
│   ├── replay.py             # Case replay tool
│   └── validate.py           # Schema validation
├── schemas/
│   ├── input.case.schema.json
│   └── output.report.schema.json
├── test_corpus/
│   ├── cases/                # Input cases
│   ├── golden/               # Expected outputs
│   └── run_test_corpus.py    # 25-case validator
├── release/                  # Release bundle
├── docker/
│   ├── Dockerfile
│   └── compose.yaml
└── validation_reports/       # Human-readable reports
```

## Completed Milestones

### v2.1.1: Bank-Grade Release Infrastructure (Current)
- ✅ JSON Schema contracts (input + output)
- ✅ Decision Pack with reproducibility metadata
- ✅ Golden test harness (3 cases)
- ✅ CLI tools (replay, validate)
- ✅ FastAPI service with /health, /ready, /version, /policy, /schemas
- ✅ Structured JSON logging
- ✅ Docker deployment
- ✅ Release bundle (SBOM, runbook, changelog)

### v2.1.0: Dual-Gate Decision System
- ✅ Gate 1: Zero-False-Escalation (Sections A-G)
- ✅ Gate 2: Positive STR Checklist (Sections 1-5)
- ✅ Two escalation paths (Hard Stop vs Behavioral)
- ✅ 6-Layer Decision Taxonomy
- ✅ 25-case test corpus (15 PAIN, 10 ESCALATE)

### v2.0.0: Core Engine
- ✅ Dual-gate architecture
- ✅ PCMLTFA s.7 compliance
- ✅ FINTRAC indicator mapping
- ✅ Instrument-specific logic (LCTR for cash only)

## What's Next

- [ ] Helm chart for Kubernetes deployment
- [ ] Prometheus metrics endpoint
- [ ] Decision replay persistence (optional)
- [ ] Multi-jurisdiction support (UK, EU, US)
- [ ] Policy versioning with hot-reload

---

## Foundation Layer (v1.6)

The AML/KYC engine is built on DecisionGraph's cryptographic foundation:

- **Cell/Chain/Genesis** — Append-only tamper-evident ledger
- **Namespace/Bridge** — Department isolation with dual-signature bridges
- **Scholar** — Bitemporal query resolver
- **PolicyHead** — Active policy tracking with promotion gates
- **Oracle Layer** — Counterfactual simulation (v1.6)
- **1432 tests passing** across 26 modules

---

*Last updated: 2026-01-30 — v2.1.1 bank-grade release*
