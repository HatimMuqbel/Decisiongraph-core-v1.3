# DecisionGraph Changelog

All notable changes to DecisionGraph will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.1] - 2026-01-29

### Added
- Multi-instrument support for layering cases (`instrument_type: "mixed"`)
- Decision pack JSON output with reproducibility metadata
- Golden test harness for regression testing
- CLI tools: `replay.py` and `validate.py`
- JSON Schema contracts for input/output (v1.0.0)
- SBOM generation script
- Release bundle structure

### Changed
- Section G now uses ANY logic (intent OR deception OR pattern)
- Section D accepts behavioral evidence as corroboration
- Report standards module for instrument-specific wording

### Fixed
- Section B instrument validation for multi-instrument cases
- Hard stop bypass in STR gate for adverse media

## [2.1.0] - 2026-01-28

### Added
- Dual-gate decision system (Gate 1 + Gate 2)
- 6-Layer Decision Taxonomy
- 25-case test corpus (15 PAIN, 10 ESCALATE)
- Two escalation paths: Hard Stop vs Behavioral Suspicion

### Changed
- Gate 1 sections A-G with explicit pass/fail logic
- Gate 2 sections 1-5 for STR determination

## [2.0.0] - 2026-01-27

### Added
- Zero-False-Escalation Gate (Gate 1)
- Positive STR Checklist (Gate 2)
- PCMLTFA s.7 compliance
- FINTRAC indicator mapping

### Breaking Changes
- New decision output schema
- Typology maturity states: FORMING → ESTABLISHED → CONFIRMED
- Hard stop precedence model

---

## Release Compatibility Matrix

| Engine Version | Policy Version | Input Schema | Output Schema |
|----------------|----------------|--------------|---------------|
| 2.1.1          | 1.0.0          | 1.0.0        | 1.0.0         |
| 2.1.0          | 1.0.0          | 1.0.0        | 1.0.0         |
| 2.0.0          | 1.0.0          | 1.0.0        | 1.0.0         |

## Rollback Procedures

### From 2.1.1 to 2.1.0
1. No data migration required
2. Revert container image tag
3. Multi-instrument cases will fail validation (use single instrument)

### From 2.1.x to 2.0.0
1. No data migration required
2. Revert container image tag
3. Test corpus format unchanged
