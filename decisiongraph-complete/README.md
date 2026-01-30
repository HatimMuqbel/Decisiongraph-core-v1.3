# DecisionGraph v2.1.1

**Bank-Grade AML/KYC Decision Engine**

Zero-false-escalation by design. Every decision is reproducible, auditable, and regulator-ready.

## What This Is

DecisionGraph is a **dual-gate AML/KYC decision engine** that makes false escalation structurally impossible. It provides deterministic, auditable decisions for transaction monitoring and suspicious activity reporting under Canadian PCMLTFA regulations.

**Current Release: v2.1.1**
- Engine Version: 2.1.1
- Policy Version: 1.0.0
- Schema Version: 1.0.0

## Core Value

| Guarantee | How |
|-----------|-----|
| **Reproducible** | Same input + same policy = identical output |
| **Auditable** | Full 6-layer taxonomy breakdown with rationale |
| **Regulator-ready** | PCMLTFA s.7 compliant with FINTRAC indicator mapping |
| **Hash-locked** | Input hash, decision ID, and policy hash in every output |

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

## Quick Start

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

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v

# Run golden tests
python scripts/run_corpus.py

# Run test corpus (25 cases)
python test_corpus/run_test_corpus.py

# Start API service
uvicorn service.main:app --reload
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
- **Path 1 - HARD STOP:** Section A passes → Immediate escalation
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
    "policy_hash": "a1b2c3d4e5f6...",
    "input_schema_version": "1.0.0",
    "output_schema_version": "1.0.0",
    "input_hash": "5f2acc5c3d80a177...",
    "decision_id": "cef4491f1cca08f7...",
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
    "layer1_facts": { "hard_stop_triggered": false, "..." },
    "layer2_obligations": { "obligations": ["PEP_FOREIGN"], "..." },
    "layer3_indicators": { "corroborated_count": 0, "..." },
    "layer4_typologies": { "highest_maturity": "FORMING", "..." },
    "layer5_mitigations": { "sufficient": true, "..." },
    "layer6_suspicion": { "activated": false, "..." }
  },
  "gates": {
    "gate1": { "decision": "PROHIBITED", "sections": {...} },
    "gate2": { "decision": "PROHIBITED", "status": "SKIPPED", "..." }
  },
  "rationale": {
    "summary": "Pass with EDD. Regulatory obligations satisfied.",
    "non_escalation_justification": "...",
    "absolute_rules_validated": [...],
    "regulatory_citations": ["PCMLTFA s.7"]
  },
  "compliance": {
    "jurisdiction": "CA",
    "legislation": "PCMLTFA",
    "fintrac_indicators_matched": []
  }
}
```

## Decision Outcomes

| Verdict | Action | STR Required | Description |
|---------|--------|--------------|-------------|
| PASS | CLOSE | NO | No escalation needed |
| PASS_WITH_EDD | CLOSE_WITH_EDD_RECORDED | NO | EDD obligation satisfied |
| ESCALATE | ESCALATE_TO_ANALYST | NO | Requires analyst review |
| STR | FILE_STR | YES | Suspicious Transaction Report required |
| HARD_STOP | BLOCK_AND_ESCALATE | YES | Immediate block + STR |

## Test Corpus

| Case Type | Count | Description |
|-----------|-------|-------------|
| PAIN | 15 | False positive prevention (must NOT escalate) |
| ESCALATE | 10 | True positive detection (must escalate) |
| **Total** | **25** | Full dual-gate validation |

All 25 cases pass. Run with: `python test_corpus/run_test_corpus.py`

## Structured Logging

Every decision is logged with full audit context:

```json
{
  "timestamp": "2026-01-30T00:52:37Z",
  "level": "INFO",
  "message": "Decision complete",
  "request_id": "7c5f3fb3",
  "external_id": "PAIN-VALIDATION-001",
  "input_hash": "5f2acc5c3d80a177",
  "decision_id": "cef4491f1cca08f7",
  "verdict": "PASS_WITH_EDD",
  "policy_version": "1.0.0",
  "policy_hash": "a4091b2ffb119dd1",
  "duration_ms": 6
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DG_ENGINE_VERSION` | 2.1.1 | Engine version |
| `DG_POLICY_VERSION` | 1.0.0 | Policy pack version |
| `DG_JURISDICTION` | CA | Default jurisdiction |
| `DG_LOG_LEVEL` | INFO | Logging verbosity |
| `DG_DOCS_ENABLED` | true | Enable /docs endpoint |
| `DG_MAX_REQUEST_SIZE` | 1048576 | Max request size (bytes) |

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
│   ├── CHANGELOG.md
│   ├── runbook.md
│   ├── SBOM.spdx.json
│   └── provenance.txt
├── docker/
│   ├── Dockerfile
│   └── compose.yaml
└── validation_reports/       # Human-readable reports
```

## Foundation Layer (v1.6)

The AML/KYC engine is built on DecisionGraph's cryptographic foundation:

- **Cell/Chain/Genesis** — Append-only tamper-evident ledger
- **Namespace/Bridge** — Department isolation with dual-signature bridges
- **Scholar** — Bitemporal query resolver
- **PolicyHead** — Active policy tracking with promotion gates
- **Oracle Layer** — Counterfactual simulation
- **1432 tests passing** across 26 modules

## What's Next

- [ ] Helm chart for Kubernetes deployment
- [ ] Prometheus metrics endpoint
- [ ] Multi-jurisdiction support (UK, EU, US)
- [ ] Policy versioning with hot-reload

## License

MIT

---

*DecisionGraph v2.1.1 — Bank-grade AML/KYC decision engine*
