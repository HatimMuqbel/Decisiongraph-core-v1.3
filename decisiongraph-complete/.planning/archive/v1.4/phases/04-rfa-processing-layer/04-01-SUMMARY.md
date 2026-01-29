---
phase: 04-rfa-processing-layer
plan: 01
title: "Engine with process_rfa() Entry Point"
subsystem: rfa-layer
tags: [engine, rfa, validation, schema, canonicalization, proof-packet]
duration: 6 minutes
completed: 2026-01-27

# Dependency graph
requires:
  - 01-01  # Error foundation (DecisionGraphError subclasses)
  - 02-01  # Input validation (validators.py)
  - 03-01  # Signing utilities (for future packet signing)
provides:
  - engine-class
  - process-rfa-method
  - proof-packet-structure
  - rfa-canonicalization
  - rfa-schema-validation
affects:
  - 04-02  # Will need Engine for packet signing
  - 05-*   # Adversarial tests will target Engine entry point

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "7-step RFA processing pipeline"
    - "Canonicalization before validation"
    - "ProofPacket wrapper for Scholar results"
    - "Convenience function pattern"

# File tracking
key-files:
  created:
    - src/decisiongraph/engine.py
    - tests/test_engine.py
  modified:
    - src/decisiongraph/__init__.py

# Decisions made
decisions:
  - decision: "ProofPacket signature field is None for now (Plan 02 handles signing)"
    rationale: "Decouple RFA processing from cryptographic signing; allows testing query pipeline independently"
    phase: "04-01"

  - decision: "Canonicalization uses json.dumps(sort_keys=True) + strip + remove None"
    rationale: "Ensures deterministic processing; prevents whitespace variations from affecting validation"
    phase: "04-01"

  - decision: "Access denial returns ProofPacket with authorization.allowed=False (not exception)"
    rationale: "Maintains audit trail; authorization failures are normal flow, not errors"
    phase: "04-01"

  - decision: "Schema validation happens before field validation"
    rationale: "Fail fast on structural issues before expensive field validation"
    phase: "04-01"

# Metrics
metrics:
  tests-added: 16
  tests-total: 329
  files-created: 2
  files-modified: 1
  loc-added: 847
---

# Phase 4 Plan 1: Engine with process_rfa() Entry Point Summary

**One-liner:** Single validated entry point for DecisionGraph queries, wrapping Scholar results in ProofPackets with canonicalized RFA input

## What Was Built

Implemented the Engine class providing `process_rfa()` - a validated entry point that:

1. **Canonicalizes RFA input** (RFA-03):
   - Sorts keys alphabetically using `json.dumps(sort_keys=True)`
   - Strips whitespace from string values
   - Removes None values
   - Ensures deterministic processing regardless of input formatting

2. **Validates schema** (RFA-02):
   - Checks required fields: `namespace`, `requester_namespace`, `requester_id`
   - Validates field types (all must be strings)
   - Raises `SchemaInvalidError` (DG_SCHEMA_INVALID) on failure

3. **Validates field formats** (VAL-01/02/03):
   - Namespace: hierarchical format (corp.hr, corp.sales, etc.)
   - Subject: type:identifier format (user:alice)
   - Predicate: snake_case format (has_salary)
   - Object: length and control character constraints
   - Raises `InputInvalidError` (DG_INPUT_INVALID) on failure

4. **Queries Scholar** for facts using validated parameters

5. **Generates ProofPacket** with:
   - `packet_version`: "1.4"
   - `packet_id`: Unique UUID
   - `generated_at`: ISO-8601 timestamp
   - `graph_id`: From chain
   - `proof_bundle`: Canonical proof from Scholar (includes facts, authorization, resolution events)
   - `signature`: None (signing handled in Plan 02)

6. **Convenience function** `process_rfa()` for one-off queries without creating Engine instance

### Key Files

**src/decisiongraph/engine.py** (361 lines):
- Engine class with 7-step pipeline
- Helper methods: `_canonicalize_rfa()`, `_validate_rfa_schema()`, `_validate_rfa_fields()`
- Exception handling: wraps internal exceptions using `wrap_internal_exception()`
- Exported: `Engine`, `process_rfa`

**tests/test_engine.py** (486 lines):
- 4 test classes, 16 tests total
- TestEngineHappyPath: Valid RFA returns ProofPacket
- TestEngineSchemaValidation: Missing/wrong type raises SchemaInvalidError
- TestEngineFieldValidation: Invalid formats raise InputInvalidError
- TestEngineCanonicalization: RFA normalization works correctly
- TestProcessRfaConvenience: Convenience function works

**src/decisiongraph/__init__.py** (modified):
- Added Engine and process_rfa imports
- Added to __all__ exports

## Implementation Decisions

### 1. ProofPacket Structure
**Decision:** ProofPacket is a dict with standardized fields, signature=None for now

**Why:**
- Keeps RFA processing separate from cryptographic operations
- Allows testing query pipeline independently
- Signature will be added in Plan 02

**Impact:** External developers get predictable response structure

### 2. Canonicalization Strategy
**Decision:** Sort keys + strip whitespace + remove None in single pass

**Why:**
- Prevents whitespace-based variations from causing different validation results
- Ensures deterministic processing (same logical input = same result)
- Simple implementation using standard json module

**Impact:** Clients can submit RFA with inconsistent formatting without issues

### 3. Access Denial Handling
**Decision:** Return ProofPacket with `authorization.allowed=False` instead of raising exception

**Why:**
- Maintains audit trail (every query gets a ProofPacket)
- Authorization failures are normal flow, not exceptional conditions
- Allows tracking who tried to access what

**Impact:** Clients must check `authorization.allowed` field in response

### 4. Validation Order
**Decision:** Schema → Fields → Query (fail fast)

**Why:**
- Structural issues (missing fields) should fail before expensive field validation
- Field validation before Scholar query prevents invalid data from reaching core
- Clear separation of concerns

**Impact:** Better error messages, faster failure on malformed input

## Test Coverage

16 tests covering:
- ✅ Happy path: Valid RFA returns ProofPacket with all required fields
- ✅ Schema validation: Missing/wrong type raises SchemaInvalidError
- ✅ Field validation: Invalid formats raise InputInvalidError
- ✅ Canonicalization: Keys sorted, whitespace stripped, None removed
- ✅ Deterministic output: Same RFA produces identical proof_bundle
- ✅ Convenience function: Works without creating Engine instance

All tests pass. No regressions detected (329 total tests).

## Deviations from Plan

None - plan executed exactly as written.

## Next Phase Readiness

**Blockers:** None

**Concerns:** None

**Ready for:**
- Plan 04-02: Packet signing (add signature to ProofPacket)
- Plan 05-*: Adversarial testing (Engine is the attack surface)

**Dependencies satisfied:**
- ✅ Error foundation (Phase 1) provides DecisionGraphError subclasses
- ✅ Input validation (Phase 2) provides field validators
- ✅ Signing utilities (Phase 3) available for Plan 02

**Dependencies created:**
- Future adversarial tests will target process_rfa() as primary attack vector
- Packet signing will extend Engine to add cryptographic signatures
- Client libraries will wrap process_rfa() for language-specific APIs

## Requirements Satisfied

- ✅ **RFA-01**: Single validated entry point (process_rfa method)
- ✅ **RFA-02**: Schema validation (required fields checked)
- ✅ **RFA-03**: Input canonicalization (sorted keys, stripped whitespace, removed None)
- ✅ **VAL-01**: Subject validation integrated
- ✅ **VAL-02**: Predicate validation integrated
- ✅ **VAL-03**: Object validation integrated

## Commits

1. `b629312` - feat(04-01): implement Engine class with process_rfa() pipeline
2. `d611c12` - test(04-01): add comprehensive Engine tests
3. `e0dfed1` - feat(04-01): export Engine and process_rfa from package

## Performance Notes

- Canonicalization adds minimal overhead (single json round-trip)
- Validation is fast (regex pre-compiled at module level)
- Scholar query dominates processing time
- No caching yet (Plan 06 optimization)

## Future Work

**Immediate (Plan 04-02):**
- Add packet signing using signing utilities from Phase 3
- Verify signatures if `verify_cell_signatures=True`

**Later:**
- Rate limiting on process_rfa() (security)
- Request ID tracking (observability)
- Caching for repeated queries (performance)
- Batch RFA processing (efficiency)

## Notes

- Access denial is NOT an exception - returns ProofPacket with `authorization.allowed=False` for auditing
- ProofPacket structure is deterministic except for `packet_id` and `generated_at`
- Canonicalization ensures same logical RFA produces identical `proof_bundle`
- All validation happens before Scholar query (fail fast principle)
