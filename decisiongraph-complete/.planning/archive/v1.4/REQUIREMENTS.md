# Requirements — DecisionGraph v1.4

## v1 Requirements

### RFA Layer

- [x] **RFA-01**: User can call `engine.process_rfa(rfa_dict)` and receive a ProofPacket on success or DecisionGraphError on failure
- [x] **RFA-02**: RFA pipeline validates schema (required fields present) before processing
- [x] **RFA-03**: RFA canonicalizes input to deterministic JSON before validation

### Error Codes

- [x] **ERR-01**: `DecisionGraphError` base class exists with `.code`, `.message`, `.details` attributes
- [x] **ERR-02**: Existing exceptions (ChainError, NamespaceError, etc.) map to one of 6 DG_* codes

### Input Validation

- [x] **VAL-01**: Subject field validated against regex `^[a-z_]+:[a-z0-9_./-]{1,128}$`
- [x] **VAL-02**: Predicate field validated against regex `^[a-z_][a-z0-9_]{0,63}$`
- [x] **VAL-03**: Object field validated as typed ID, TypedValue, or bounded string (max 4096 chars)
- [x] **VAL-04**: Control characters (0x00-0x1F except tab/newline) rejected in all fields

### Signatures

- [x] **SIG-01**: `sign_bytes(private_key, data)` signs data using Ed25519 and returns signature
- [x] **SIG-02**: `verify_signature(public_key, data, signature)` verifies Ed25519 signature
- [x] **SIG-03**: Commit Gate optionally verifies cell signatures when `signature_required=True`
- [x] **SIG-04**: ProofPacket can be signed by engine and verified by external parties

### Security Tests

- [x] **SEC-01**: Predicate containing spaces/operators/semicolons returns `DG_INPUT_INVALID`
- [x] **SEC-02**: Namespace like `corp..hr` or `corp/hr` returns `DG_INPUT_INVALID`
- [x] **SEC-03**: RFA referencing cell_ids from different graph returns `DG_INTEGRITY_FAIL`
- [x] **SEC-04**: Modified byte in signed packet/cell returns `DG_SIGNATURE_INVALID`
- [x] **SEC-05**: Query with `as_of_system_time` before bridge exists returns `DG_UNAUTHORIZED`

### Visualizer

- [x] **VIS-01**: `proof_bundle.to_audit_text()` produces deterministic human-readable report
- [x] **VIS-02**: `proof_bundle.to_dot()` produces Graphviz DOT output for lineage visualization

---

## v2 Requirements (Deferred)

- Oracle fact injection (external data sources)
- Promotion workflows (staging -> production)
- Frontend UI visualization
- Persistent storage layer

---

## Out of Scope

- **HTTP API layer** — This milestone produces Python interface only
- **Key management** — Keys passed in, not managed by engine
- **Rate limiting** — No throttling in core engine
- **Audit log persistence** — Proof bundles returned, not stored

---

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| ERR-01 | Phase 1 | Complete |
| ERR-02 | Phase 1 | Complete |
| VAL-01 | Phase 2 | Complete |
| VAL-02 | Phase 2 | Complete |
| VAL-03 | Phase 2 | Complete |
| VAL-04 | Phase 2 | Complete |
| SIG-01 | Phase 3 | Complete |
| SIG-02 | Phase 3 | Complete |
| RFA-01 | Phase 4 | Complete |
| RFA-02 | Phase 4 | Complete |
| RFA-03 | Phase 4 | Complete |
| SIG-03 | Phase 4 | Complete |
| SIG-04 | Phase 4 | Complete |
| SEC-01 | Phase 5 | Complete |
| SEC-02 | Phase 5 | Complete |
| SEC-03 | Phase 5 | Complete |
| SEC-04 | Phase 5 | Complete |
| SEC-05 | Phase 5 | Complete |
| VIS-01 | Phase 6 | Complete |
| VIS-02 | Phase 6 | Complete |

---

*Last updated: 2026-01-27*
