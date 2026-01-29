# DecisionGraph Operational Runbook

## Overview

DecisionGraph is a bank-grade AML/KYC decision engine implementing a dual-gate
architecture for transaction monitoring and suspicious activity reporting.

**Current Version:** 2.1.1
**Policy Version:** 1.0.0
**Jurisdiction:** Canada (PCMLTFA)

---

## Quick Reference

### Decision Outcomes

| Verdict | Action | STR Required | Description |
|---------|--------|--------------|-------------|
| PASS | CLOSE | NO | No escalation needed |
| PASS_WITH_EDD | CLOSE_WITH_EDD_RECORDED | NO | EDD obligation satisfied |
| ESCALATE | ESCALATE_TO_ANALYST | NO | Requires analyst review |
| STR | FILE_STR | YES | Suspicious Transaction Report required |
| HARD_STOP | BLOCK_AND_ESCALATE | YES | Immediate block + STR |

### Escalation Paths

- **Path 1 - Hard Stop:** Sanctions match, false docs, refusal, legal prohibition, adverse media
- **Path 2 - Behavioral:** Confirmed typology + (intent OR deception OR pattern) + failed mitigations

---

## Deployment

### Prerequisites

- Python 3.10+
- Docker (optional)
- 512MB RAM minimum

### Local Deployment

```bash
# Clone and install
git clone https://github.com/decisiongraph/core.git
cd decisiongraph-complete
pip install -r requirements.txt

# Run tests
python test_corpus/run_test_corpus.py

# Run golden tests
python scripts/run_corpus.py
```

### Docker Deployment

```bash
# Build image
docker build -t decisiongraph:2.1.1 -f docker/Dockerfile .

# Run container
docker run -p 8000:8000 decisiongraph:2.1.1

# Health check
curl http://localhost:8000/health
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DG_ENGINE_VERSION` | 2.1.1 | Engine version (override for testing) |
| `DG_POLICY_VERSION` | 1.0.0 | Policy pack version |
| `DG_JURISDICTION` | CA | Default jurisdiction |
| `DG_LOG_LEVEL` | INFO | Logging verbosity |

---

## Operations

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Version info
curl http://localhost:8000/version

# Run self-test
python -m cli.replay --case PAIN-VALIDATION-001
```

### Replay a Case

```bash
# By case ID
python -m cli.replay --case LAYER-CRYPTO-001

# From file
python -m cli.replay --file case.json --pretty

# Compare with golden
python -m cli.replay --file case.json --golden expected.json
```

### Validate Schemas

```bash
# Validate input
python -m cli.validate --input case.json

# Validate output
python -m cli.validate --output report.json

# Validate corpus
python -m cli.validate --corpus test_corpus/cases/
```

### Update Golden Outputs

```bash
# Regenerate all golden files
python scripts/run_corpus.py --update-goldens

# Review changes
git diff test_corpus/golden/
```

---

## Monitoring

### Key Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `decisions_total` | Total decisions made | N/A |
| `decisions_str_required` | STR decisions | > 10% in 1h |
| `decisions_hard_stop` | Hard stop decisions | Any |
| `decision_latency_ms` | Decision time | > 100ms p99 |
| `golden_test_failures` | Regression failures | > 0 |

### Log Patterns

```
# Normal decision
INFO decision_complete case_id=XXX verdict=PASS duration_ms=15

# STR required
WARN str_required case_id=XXX path=PATH_2_SUSPICION

# Hard stop
ERROR hard_stop_triggered case_id=XXX reason=SANCTIONS_MATCH

# Validation error
ERROR input_validation_failed field=customer_record.pep_flag
```

---

## Troubleshooting

### Common Issues

#### Case fails with "Instrument type invalid"
- Cause: Unknown instrument type in input
- Fix: Use valid types: `wire`, `cash`, `crypto`, `cheque`, `mixed`, `unknown`

#### Golden test mismatch
- Cause: Engine behavior changed
- Fix: Review diff, update goldens if intentional

#### Schema validation fails
- Cause: Input missing required fields
- Fix: Check input against `schemas/input.case.schema.json`

### Debug Mode

```bash
# Verbose replay
python -m cli.replay --case CASE-ID --verbose --pretty

# Check gate sections
jq '.gates' output.json
```

---

## Incident Response

### STR Filing Failure

1. Check case ID in logs
2. Replay case: `python -m cli.replay --case CASE-ID --pretty`
3. Verify decision pack against golden
4. If mismatch, escalate to engineering

### False Positive Reported

1. Document case ID and reporter
2. Replay case with verbose output
3. Check which gate section caused escalation
4. Review mitigations and indicators
5. If engine error, file bug with decision pack

### Rollback Procedure

1. Stop current container
2. Deploy previous version: `docker run decisiongraph:2.1.0`
3. Run golden tests: `python scripts/run_corpus.py`
4. Verify all 25 cases pass
5. Resume operations

---

## Compliance

### Regulatory Requirements

- **PCMLTFA s.7:** Reasonable grounds to suspect ML/TF
- **FINTRAC:** STR filing within 30 days
- **LCTR:** CAD 10,000 threshold for cash

### Audit Trail

Every decision includes:
- `input_hash`: SHA-256 of input (reproducibility)
- `engine_version`: Semantic version
- `policy_version`: Rules pack version
- `report_timestamp_utc`: ISO 8601 timestamp

### Record Retention

- Decision packs: 7 years minimum
- Input cases: 7 years minimum
- Audit logs: 7 years minimum

---

## Support

- GitHub Issues: https://github.com/decisiongraph/core/issues
- Documentation: https://docs.decisiongraph.io
- Email: support@decisiongraph.io
