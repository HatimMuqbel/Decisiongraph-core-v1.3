# DecisionGraph v2.1.1 Release Manifest

**Release Date:** 2026-01-30
**Status:** ✅ APPROVED FOR PILOT (Bank + Insurance Ready)

## Governance Bundle

All governance assets are included in this repository under the following paths:

### Schema Contracts

| Asset | Path | Version | SHA-256 |
|-------|------|---------|---------|
| Input Schema | `schemas/input.case.schema.json` | 1.0.0 | `cd474845ea42ea06...` |
| Output Schema | `schemas/output.report.schema.json` | 1.0.0 | `a42bb7afeaa91e46...` |

### Golden Outputs (3 Canonical Cases)

| Case | Path | Verdict |
|------|------|---------|
| PAIN-VALIDATION-001 | `test_corpus/golden/PAIN-VALIDATION-001.golden.json` | PASS_WITH_EDD |
| ESCALATE-HARD-STOP-001 | `test_corpus/golden/ESCALATE-HARD-STOP-001.golden.json` | STR (Path 1) |
| ESCALATE-BEHAVIORAL-001 | `test_corpus/golden/ESCALATE-BEHAVIORAL-001.golden.json` | STR (Path 2) |

### Corpus Regression (25 Cases)

| Type | Count | Path |
|------|-------|------|
| PAIN (false positive prevention) | 15 | `test_corpus/cases/TEST-P-*.json` |
| ESCALATE (true positive detection) | 10 | `test_corpus/cases/TEST-E-*.json` |
| **Total** | **25/25 passing** | |

### Compliance & Operations

| Asset | Path | Purpose |
|-------|------|---------|
| SBOM | `release/SBOM.spdx.json` | Software Bill of Materials |
| Provenance | `release/provenance.txt` | Build attestation |
| Runbook | `release/runbook.md` | Operational procedures |
| Changelog | `release/CHANGELOG.md` | Version history |
| Config Example | `release/config.example.yaml` | Deployment template |

## Version Information

```
ENGINE_VERSION=2.1.1
POLICY_VERSION=1.0.0
POLICY_HASH=7dbc3567f93ab289f74b45b386f045aadce3328d08be59268642a56b98b0fcfe
INPUT_SCHEMA_VERSION=1.0.0
OUTPUT_SCHEMA_VERSION=1.0.0
GIT_COMMIT=8d06189a9e182aa2d36749b96c70d3b8f8a5458d
```

## Verification

```bash
# Clone and checkout release
git clone https://github.com/HatimMuqbel/Decisiongraph-core-v1.3.git
cd Decisiongraph-core-v1.3/decisiongraph-complete
git checkout v2.1.1

# Run golden tests (must pass 3/3)
python scripts/run_corpus.py

# Run corpus regression (must pass 25/25)
python test_corpus/run_test_corpus.py

# Build Docker image
docker build -t decisiongraph:2.1.1 \
  --build-arg GIT_SHA=$(git rev-parse --short HEAD) \
  -f docker/Dockerfile .

# Verify endpoints
docker run -d -p 8000:8000 decisiongraph:2.1.1
curl http://localhost:8000/ready
curl http://localhost:8000/version
```

## Absolute Rules (Hardcoded - No Exceptions)

```
✗ PEP status alone can NEVER escalate
✗ Cross-border alone can NEVER escalate
✗ Risk score alone can NEVER escalate
✗ "High confidence" can NEVER override facts
✗ "Compliance comfort" is NOT a reason
```

## Support

- **Issues:** https://github.com/HatimMuqbel/Decisiongraph-core-v1.3/issues
- **Documentation:** See `README.md` and `.planning/PROJECT.md`
