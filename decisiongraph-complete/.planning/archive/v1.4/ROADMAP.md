# Roadmap — DecisionGraph v1.4

## Overview

This roadmap delivers the RFA (Request for Authorization) layer and security hardening for DecisionGraph v1.4. The milestone wraps the existing v1.3 engine (Scholar, Chain, Namespace) with a single validated entry point, standardized error codes, input validation, cryptographic signatures, adversarial testing, and audit visualization. Phases follow the user's recommended implementation order: foundation first (errors), then validation, then signing, then integration, then attack-proofing, then visualization.

---

## Phases

### Phase 1: Error Foundation

**Goal:** External developers receive deterministic, actionable error codes from any DecisionGraph failure.

**Dependencies:** None (foundation phase)

**Requirements:**
- ERR-01: `DecisionGraphError` base class with `.code`, `.message`, `.details`
- ERR-02: Existing exceptions map to 6 DG_* codes

**Success Criteria:**
1. Raising any internal exception (ChainError, NamespaceError, etc.) produces a DecisionGraphError with correct DG_* code
2. DecisionGraphError serializes to JSON with `code`, `message`, and `details` fields
3. All 6 error codes (DG_SCHEMA_INVALID, DG_INPUT_INVALID, DG_UNAUTHORIZED, DG_INTEGRITY_FAIL, DG_SIGNATURE_INVALID, DG_INTERNAL_ERROR) are defined and documented
4. Existing 69 tests remain passing

**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md — Create DecisionGraphError hierarchy with 6 subclasses
- [x] 01-02-PLAN.md — Create EXCEPTION_MAP and wrap_internal_exception
- [x] 01-03-PLAN.md — Add comprehensive tests for exception system

---

### Phase 2: Input Validation

**Goal:** Malformed or malicious input is rejected before reaching the core engine.

**Dependencies:** Phase 1 (errors needed for rejection responses)

**Requirements:**
- VAL-01: Subject field validated against regex `^[a-z_]+:[a-z0-9_./-]{1,128}$`
- VAL-02: Predicate field validated against regex `^[a-z_][a-z0-9_]{0,63}$`
- VAL-03: Object field validated as typed ID, TypedValue, or bounded string (max 4096 chars)
- VAL-04: Control characters (0x00-0x1F except tab/newline) rejected

**Success Criteria:**
1. Valid subject `user:alice_123` passes; invalid `USER:Alice` fails with DG_INPUT_INVALID
2. Valid predicate `can_access` passes; invalid `can access` (space) fails with DG_INPUT_INVALID
3. Object exceeding 4096 chars fails with DG_INPUT_INVALID
4. Control character `\x00` in any field fails with DG_INPUT_INVALID
5. Existing 127 tests remain passing

**Plans:** 1 plan

Plans:
- [x] 02-01-PLAN.md — Create validators.py with input validation functions and comprehensive tests

---

### Phase 3: Signing Utilities

**Goal:** DecisionGraph can sign and verify data using Ed25519 cryptography.

**Dependencies:** Phase 1 (errors for signature failures)

**Requirements:**
- SIG-01: `sign_bytes(private_key, data)` signs using Ed25519
- SIG-02: `verify_signature(public_key, data, signature)` verifies Ed25519 signature

**Success Criteria:**
1. `sign_bytes()` produces 64-byte Ed25519 signature from private key and data
2. `verify_signature()` returns True for valid signature, False for invalid
3. Tampered data (1 byte changed) fails verification
4. Invalid key format raises DG_SIGNATURE_INVALID
5. Existing 281 tests remain passing

**Plans:** 1 plan

Plans:
- [x] 03-01-PLAN.md — Create Ed25519 signing utilities (sign_bytes, verify_signature, generate_ed25519_keypair) with tests

---

### Phase 4: RFA Processing Layer

**Goal:** External callers interact with DecisionGraph through a single validated entry point.

**Dependencies:** Phase 1 (errors), Phase 2 (validation), Phase 3 (signing)

**Requirements:**
- RFA-01: `engine.process_rfa(rfa_dict)` returns ProofPacket or DecisionGraphError
- RFA-02: RFA pipeline validates schema before processing
- RFA-03: RFA canonicalizes input to deterministic JSON before validation
- SIG-03: Commit Gate optionally verifies cell signatures when `signature_required=True`
- SIG-04: ProofPacket can be signed by engine and verified externally

**Success Criteria:**
1. `process_rfa()` with valid RFA returns a ProofPacket containing decision and proof bundle
2. `process_rfa()` with missing required field returns DG_SCHEMA_INVALID
3. `process_rfa()` with invalid subject/predicate/object returns DG_INPUT_INVALID
4. ProofPacket can be signed and verified by external party
5. When `signature_required=True`, unsigned cells are rejected with DG_SIGNATURE_INVALID
6. Existing 313 tests remain passing

**Plans:** 3 plans

Plans:
- [x] 04-01-PLAN.md — Create Engine class with process_rfa() pipeline (RFA-01, RFA-02, RFA-03)
- [x] 04-02-PLAN.md — Implement ProofPacket signing and verify_proof_packet() (SIG-04)
- [x] 04-03-PLAN.md — Add optional signature verification to Chain.append() (SIG-03)

---

### Phase 5: Adversarial Test Suite

**Goal:** Documented attack vectors are proven to fail with deterministic error codes.

**Dependencies:** Phase 4 (RFA layer must exist to attack)

**Requirements:**
- SEC-01: Predicate injection returns DG_INPUT_INVALID
- SEC-02: Namespace traversal returns DG_INPUT_INVALID
- SEC-03: Cross-graph contamination returns DG_INTEGRITY_FAIL
- SEC-04: Signature tampering returns DG_SIGNATURE_INVALID
- SEC-05: Bridge time-travel returns DG_UNAUTHORIZED

**Success Criteria:**
1. Predicate `can;drop table` fails with DG_INPUT_INVALID (not passed to Scholar)
2. Namespace `corp..hr` or `corp/hr` fails with DG_INPUT_INVALID (no traversal)
3. RFA referencing cell_id from different graph fails with DG_INTEGRITY_FAIL
4. ProofPacket with 1 byte modified fails verification with DG_SIGNATURE_INVALID
5. Query with `as_of_system_time` before bridge creation fails with DG_UNAUTHORIZED
6. Existing 342 tests remain passing

**Plans:** 2 plans

Plans:
- [x] 05-01-PLAN.md — Input validation adversarial tests (SEC-01, SEC-02)
- [x] 05-02-PLAN.md — Security layer adversarial tests (SEC-03, SEC-04, SEC-05)

---

### Phase 6: Lineage Visualizer

**Goal:** Proof bundles can be exported as human-readable audit reports and visual graphs.

**Dependencies:** Phase 4 (ProofBundle must exist to visualize)

**Requirements:**
- VIS-01: `proof_bundle.to_audit_text()` produces deterministic report
- VIS-02: `proof_bundle.to_dot()` produces Graphviz DOT output

**Success Criteria:**
1. `to_audit_text()` returns string containing decision, timestamp, and supporting cells
2. Same ProofBundle always produces identical audit text (deterministic)
3. `to_dot()` returns valid DOT syntax parseable by Graphviz
4. DOT output shows cell lineage with edges representing dependencies
5. Existing 497 tests remain passing

**Plans:** 1 plan

Plans:
- [x] 06-01-PLAN.md — Implement to_audit_text() and to_dot() methods on QueryResult with tests

---

## Progress

| Phase | Name | Requirements | Status |
|-------|------|--------------|--------|
| 1 | Error Foundation | ERR-01, ERR-02 | Complete |
| 2 | Input Validation | VAL-01, VAL-02, VAL-03, VAL-04 | Complete |
| 3 | Signing Utilities | SIG-01, SIG-02 | Complete |
| 4 | RFA Processing Layer | RFA-01, RFA-02, RFA-03, SIG-03, SIG-04 | Complete |
| 5 | Adversarial Test Suite | SEC-01, SEC-02, SEC-03, SEC-04, SEC-05 | Complete |
| 6 | Lineage Visualizer | VIS-01, VIS-02 | Complete |

---

## Coverage

**Total v1 Requirements:** 20
**Mapped:** 20/20

| Category | Count | Phase |
|----------|-------|-------|
| ERR | 2 | Phase 1 |
| VAL | 4 | Phase 2 |
| SIG (utilities) | 2 | Phase 3 |
| RFA + SIG (integration) | 5 | Phase 4 |
| SEC | 5 | Phase 5 |
| VIS | 2 | Phase 6 |

No orphaned requirements. 100% coverage validated.

---

*Last updated: 2026-01-27*
