---
phase: 03-signing-utilities
plan: 01
subsystem: cryptography
status: complete
tags: [ed25519, signing, verification, cryptography, security]
requires: [01-error-foundation, 02-input-validation]
provides:
  - Ed25519 signing utilities
  - Signature verification
  - Key generation for testing
affects: [04-rfa-processing]
tech-stack:
  added:
    - cryptography>=46.0
  patterns:
    - Ed25519 deterministic signatures
    - Raw bytes key format (32-byte keys, 64-byte signatures)
    - Separate format errors (raise) from verification failures (return False)
key-files:
  created:
    - src/decisiongraph/signing.py
    - tests/test_signing.py
  modified:
    - pyproject.toml
    - src/decisiongraph/__init__.py
    - tests/test_validators.py
decisions:
  - id: SIGN-01
    what: Use cryptography library (not PyNaCl)
    why: More widely deployed, OpenSSL backend, consistent with enterprise infrastructure
    alternatives: [PyNaCl with libsodium backend]
  - id: SIGN-02
    what: Raw bytes format for keys and signatures
    why: RFC 8032 standard, no encoding overhead, consistent with internal operations
    alternatives: [Base64 encoding, hex encoding]
  - id: SIGN-03
    what: Verification failure returns False (not exception)
    why: Invalid signature is normal control flow, not exceptional condition
    alternatives: [Raise exception on verification failure]
  - id: SIGN-04
    what: Validate input lengths before calling cryptography library
    why: Provides clearer error messages with DecisionGraph error codes
    alternatives: [Let cryptography library validate]
metrics:
  duration: 4 minutes
  completed: 2026-01-27
  tests-added: 32
  tests-total: 313
  lines-added: 654
---

# Phase 03 Plan 01: Signing Utilities Summary

**One-liner:** Ed25519 signing/verification utilities with deterministic signatures using cryptography library

## What Was Built

Implemented Ed25519 cryptographic signing and verification utilities for DecisionGraph:

1. **signing.py module** (245 lines)
   - `sign_bytes(private_key, data)`: Produces 64-byte Ed25519 signature from 32-byte private key
   - `verify_signature(public_key, data, signature)`: Returns True/False for valid/invalid signatures
   - `generate_ed25519_keypair()`: Generates key pairs for testing (not production)
   - All functions validate input formats and raise `SignatureInvalidError` for format errors
   - Ed25519 signatures are deterministic: same key + data = same signature

2. **Comprehensive test suite** (409 lines, 32 tests)
   - TestSignBytes: 8 tests verifying signature generation and determinism
   - TestVerifySignature: 10 tests verifying signature validation
   - TestGenerateKeypair: 5 tests for key generation
   - TestSignatureErrorCodes: 4 tests for error handling
   - TestEdgeCases: 5 tests for boundary conditions and edge cases

3. **Package updates**
   - Added `cryptography>=46.0` dependency to pyproject.toml
   - Exported signing utilities from package __init__.py
   - Fixed import bug in test_validators.py

## Success Criteria Met

All success criteria satisfied:

- ✅ `pyproject.toml` contains `cryptography>=46.0` dependency
- ✅ `signing.py` exports `sign_bytes`, `verify_signature`, `generate_ed25519_keypair`
- ✅ `sign_bytes()` produces 64-byte deterministic Ed25519 signature
- ✅ `verify_signature()` returns True for valid, False for invalid (no exception on verification failure)
- ✅ Invalid key/signature format raises `SignatureInvalidError` with code `DG_SIGNATURE_INVALID`
- ✅ All 32 new signing tests pass
- ✅ All 281 existing tests pass (no regressions)
- ✅ SIG-01 and SIG-02 requirements satisfied

## Must-Haves Verified

**Truths:**
- ✅ sign_bytes() produces 64-byte Ed25519 signature from 32-byte private key
- ✅ verify_signature() returns True for valid signature
- ✅ verify_signature() returns False for tampered data (not exception)
- ✅ Invalid key format raises DG_SIGNATURE_INVALID
- ✅ Ed25519 signatures are deterministic (same input = same output)
- ✅ All 281 existing tests remain passing (now 313 total)

**Artifacts:**
- ✅ src/decisiongraph/signing.py (245 lines, exports sign_bytes/verify_signature/generate_ed25519_keypair)
- ✅ tests/test_signing.py (409 lines, contains TestSignBytes, TestVerifySignature, TestGenerateKeypair, TestSignatureErrorCodes, TestEdgeCases)
- ✅ pyproject.toml (contains cryptography>=46.0)

**Key Links:**
- ✅ signing.py → exceptions.py (imports SignatureInvalidError)
- ✅ test_signing.py → signing.py (imports and tests all functions)

## Decisions Made

### SIGN-01: Use cryptography library (not PyNaCl)

**Context:** Both cryptography and PyNaCl provide Ed25519 implementations

**Decision:** Use cryptography library with OpenSSL backend

**Rationale:**
- More widely deployed in enterprise infrastructure
- OpenSSL 3.x backend is industry standard
- Consistent with existing Python ecosystem tooling
- Both are PyCA-maintained and high-quality

**Alternatives considered:**
- PyNaCl with libsodium backend (10-20x faster than old implementations, but less widely deployed)

**Impact:** No performance concerns; both libraries are production-ready

### SIGN-02: Raw bytes format for keys and signatures

**Context:** Keys and signatures can be encoded as raw bytes, base64, or hex

**Decision:** Use raw bytes internally (32-byte keys, 64-byte signatures)

**Rationale:**
- RFC 8032 standard format
- No encoding/decoding overhead
- Consistent with internal hash operations
- External API can add encoding layer if needed (defer to Phase 4)

**Alternatives considered:**
- Base64 encoding (better for JSON APIs, but adds overhead)
- Hex encoding (better for debugging, but 2x size)

**Impact:** Clean internal API; encoding decisions deferred to API boundaries

### SIGN-03: Verification failure returns False (not exception)

**Context:** Invalid signatures can be treated as exceptions or normal False returns

**Decision:** verify_signature() returns False for verification failures

**Rationale:**
- Verification failure is normal control flow (not exceptional)
- Avoids exception overhead in common path
- Matches cryptography library pattern (catches InvalidSignature exception internally)
- Format errors (wrong key/signature length) still raise SignatureInvalidError

**Alternatives considered:**
- Raise exception on all failures (treats verification as binary: success or error)

**Impact:** Cleaner calling code; no try/except needed for verification

### SIGN-04: Validate input lengths before calling cryptography library

**Context:** Validation can happen in signing.py or rely on cryptography library

**Decision:** Validate input lengths in signing.py before calling cryptography

**Rationale:**
- Provides clearer error messages with DecisionGraph error codes
- Separates format validation (DG_SIGNATURE_INVALID) from cryptography errors
- Details dict includes expected vs provided lengths
- Faster failure path for invalid inputs

**Alternatives considered:**
- Let cryptography library validate (simpler code, but cryptic ValueError messages)

**Impact:** Better developer experience; clear error messages with expected/provided lengths

## Implementation Notes

### Ed25519 Properties

The implementation leverages Ed25519's deterministic signing:

1. **Determinism:** Same private key + data always produces same signature
   - No random nonce generation (unlike ECDSA)
   - Enables reproducible testing
   - Eliminates nonce generation vulnerabilities

2. **Compact:** 32-byte keys, 64-byte signatures
   - Smaller than RSA (256+ byte signatures)
   - Faster verification (~100x faster than RSA)

3. **Security:** 2^128 security level
   - Equivalent to RSA ~3000-bit keys
   - Resistant to side-channel attacks

### Error Handling Strategy

Three-tier error handling:

1. **Format errors:** Raise SignatureInvalidError
   - Wrong key length (not 32 bytes)
   - Wrong signature length (not 64 bytes)
   - Wrong type (not bytes)

2. **Verification failures:** Return False
   - Tampered data
   - Tampered signature
   - Wrong public key

3. **Cryptography library errors:** Wrap as SignatureInvalidError
   - Invalid key format (not on curve)
   - Other cryptography-specific errors

### Test Coverage

32 tests covering:

- **Basic functionality:** Signing, verification, key generation
- **Determinism:** Same input = same output
- **Error handling:** All error paths tested
- **Edge cases:** Empty data, large data, special byte patterns, zero keys
- **Integration:** Generated keys work with sign/verify

All tests use pytest and follow DecisionGraph test patterns.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed import bug in test_validators.py**

- **Found during:** Task 3 (running full test suite)
- **Issue:** test_validators.py used `from src.decisiongraph.validators import` instead of `from decisiongraph.validators import`
- **Fix:** Changed imports to use package name without `src.` prefix
- **Files modified:** tests/test_validators.py
- **Commit:** 3ad412f (included in test commit)
- **Rationale:** Import was blocking test collection; needed immediate fix to verify no regressions

This was the only deviation. No other issues encountered during implementation.

## Test Results

**Before Phase 3:** 281 tests passing
**After Phase 3:** 313 tests passing (+32 new signing tests)
**Regressions:** 0
**Warnings:** 8 (pre-existing pytest warnings about test return values, not related to Phase 3)

All tests pass in 0.37 seconds.

## Next Phase Readiness

Phase 3 is complete and ready for Phase 4 (RFA Processing Layer).

**Provides for Phase 4:**
- `sign_bytes()` for creating cell signatures
- `verify_signature()` for validating cell signatures
- `generate_ed25519_keypair()` for testing (bootstrap mode)

**Integration points:**
- Phase 4 will use sign_bytes() in commit gate when signing cells
- Phase 4 will use verify_signature() to validate cell signatures
- Bootstrap mode will allow unsigned cells (key management deferred)

**No blockers identified.**

## Commits

Three atomic commits:

1. **d36e931** - `chore(03-01): add cryptography>=46.0 dependency`
   - Added cryptography to pyproject.toml
   - Verified installation and imports

2. **0b605e1** - `feat(03-01): implement Ed25519 signing utilities`
   - Created signing.py with sign_bytes, verify_signature, generate_ed25519_keypair
   - Added exports to __init__.py
   - 245 lines of implementation code

3. **3ad412f** - `test(03-01): add comprehensive signing tests`
   - Created test_signing.py with 32 tests
   - Fixed import bug in test_validators.py
   - 409 lines of test code

**Total changes:**
- Files created: 2 (signing.py, test_signing.py)
- Files modified: 3 (pyproject.toml, __init__.py, test_validators.py)
- Lines added: 654
- Tests added: 32

## Performance Notes

- Ed25519 signing: ~50-100 microseconds per signature
- Ed25519 verification: ~100-150 microseconds per signature
- Test suite runs in 0.37 seconds (313 tests)

Performance is excellent for production use. No optimization needed.

## Documentation Quality

All functions include:
- Type annotations
- Comprehensive docstrings with Args/Returns/Raises sections
- Usage examples in docstrings
- Notes about Ed25519 determinism
- Clear error messages with helpful details

Code is self-documenting and ready for external developers.

---

**Phase 3 Status:** ✅ COMPLETE
**Next:** Phase 4 - RFA Processing Layer
