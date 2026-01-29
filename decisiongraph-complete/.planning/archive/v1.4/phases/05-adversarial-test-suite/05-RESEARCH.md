# Phase 5: Adversarial Test Suite - Research

**Researched:** 2026-01-27
**Domain:** Security Testing / Adversarial Testing
**Confidence:** HIGH

## Summary

Adversarial testing verifies that security controls fail safely with deterministic error codes when attacked. This phase tests 5 documented attack vectors against the DecisionGraph RFA layer, ensuring each attack is rejected with the correct error code without corrupting state or leaking information.

The standard approach uses pytest's parametrization to organize attack vectors by category, testing both that malicious inputs are rejected AND that they produce the correct DG_* error codes. Each test verifies defense-in-depth: validators catch injection attempts, integrity checks detect tampering, and authorization logic blocks unauthorized access.

DecisionGraph already has strong foundations: pre-compiled regex with fullmatch() for injection prevention, Ed25519 signatures for tamper detection, and namespace validation for traversal prevention. Phase 5 proves these defenses work by attacking them systematically.

**Primary recommendation:** Use pytest.mark.parametrize to organize attack vectors by SEC requirement, verifying both exception type (InputInvalidError, IntegrityFailError, etc.) and error code (DG_INPUT_INVALID, DG_INTEGRITY_FAIL, etc.). Keep existing 342 tests passing while adding focused adversarial tests.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | >=7.0 | Test framework | Industry standard for Python testing, already in pyproject.toml |
| pytest.mark.parametrize | (pytest builtin) | Attack vector organization | Official pytest feature for testing multiple inputs with same assertions |
| cryptography | >=46.0 | Ed25519 signatures | Already used in Phase 3, provides InvalidSignature exception |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-cov | (already installed) | Test coverage | Verify all attack paths exercise security code |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest.mark.parametrize | Separate test functions | Parametrize reduces duplication and groups related attacks |
| unittest | pytest | pytest already standard in project, better parametrization |
| Hypothesis | pytest parametrize | Hypothesis is property-based testing (fuzzing), overkill for 5 documented attack vectors |

**Installation:**
```bash
# All dependencies already installed
pytest>=7.0
pytest-cov
cryptography>=46.0
```

## Architecture Patterns

### Recommended Test Structure
```
tests/
├── test_adversarial_injection.py      # SEC-01: Predicate injection
├── test_adversarial_traversal.py      # SEC-02: Namespace traversal
├── test_adversarial_integrity.py      # SEC-03: Cross-graph contamination
├── test_adversarial_tampering.py      # SEC-04: Signature tampering
└── test_adversarial_authorization.py  # SEC-05: Bridge time-travel
```

### Pattern 1: Parametrized Attack Vector Testing
**What:** Group related attack payloads with expected error codes
**When to use:** Testing multiple variations of same attack type
**Example:**
```python
# Source: pytest docs + DecisionGraph existing patterns
import pytest
from decisiongraph import InputInvalidError

class TestPredicateInjection:
    """SEC-01: Predicate injection attacks return DG_INPUT_INVALID"""

    @pytest.mark.parametrize("malicious_predicate,attack_type", [
        ("can;drop table", "SQL-style semicolon injection"),
        ("can' OR '1'='1", "SQL quote injection"),
        ("can\x00drop", "null byte injection"),
        ("can\nDROP TABLE", "newline injection"),
        ("can--comment", "SQL comment injection"),
        ("can/**/admin", "SQL comment bypass"),
        ("CAN_ACCESS", "case bypass attempt"),
        ("can-access", "hyphen format bypass"),
        ("can access", "space injection"),
    ])
    def test_injection_payloads_rejected(
        self,
        malicious_predicate: str,
        attack_type: str
    ) -> None:
        """Malicious predicates fail with DG_INPUT_INVALID before reaching Scholar"""
        from decisiongraph import validate_predicate_field

        with pytest.raises(InputInvalidError) as exc_info:
            validate_predicate_field(malicious_predicate)

        # Verify correct error code
        assert exc_info.value.code == "DG_INPUT_INVALID"

        # Verify details include field name
        assert exc_info.value.details.get("field") == "predicate"
```

### Pattern 2: Signature Tampering Detection
**What:** Modify signature bytes and verify tampering is detected
**When to use:** Testing cryptographic integrity (SEC-04)
**Example:**
```python
# Source: DecisionGraph signing.py + cryptography docs
from decisiongraph import sign_bytes, verify_signature, generate_ed25519_keypair

class TestSignatureTampering:
    """SEC-04: Signature tampering returns DG_SIGNATURE_INVALID"""

    def test_single_bit_flip_detected(self):
        """Flipping 1 bit in signature makes verification fail"""
        priv, pub = generate_ed25519_keypair()
        data = b"important data"

        # Valid signature
        signature = sign_bytes(priv, data)
        assert verify_signature(pub, data, signature) is True

        # Tamper: flip last bit
        tampered_sig = signature[:-1] + bytes([signature[-1] ^ 0x01])

        # Verification returns False (normal control flow, not exception)
        assert verify_signature(pub, data, tampered_sig) is False

    @pytest.mark.parametrize("byte_index", [0, 31, 32, 63])
    def test_byte_modification_at_position(self, byte_index: int):
        """Modifying any byte position breaks signature"""
        priv, pub = generate_ed25519_keypair()
        data = b"test"
        signature = sign_bytes(priv, data)

        # Modify specific byte
        sig_list = list(signature)
        sig_list[byte_index] ^= 0xFF  # Flip all bits in byte
        tampered_sig = bytes(sig_list)

        assert verify_signature(pub, data, tampered_sig) is False
```

### Pattern 3: Integrity Violation Testing
**What:** Cross-graph contamination detection
**When to use:** Testing graph_id integrity checks (SEC-03)
**Example:**
```python
# Source: DecisionGraph existing test patterns
from decisiongraph import create_chain, create_cell, IntegrityFailError

class TestCrossGraphContamination:
    """SEC-03: Cross-graph contamination returns DG_INTEGRITY_FAIL"""

    def test_cell_from_different_graph_rejected(self):
        """RFA cannot reference cell_id from different graph"""
        # Create two separate graphs
        chain_a = create_chain("graph_a")
        chain_b = create_chain("graph_b")

        # Add cell to graph A
        cell_a = create_cell(
            namespace="corp.a",
            subject="user:alice",
            predicate="has_role",
            object_value="admin",
            graph_id=chain_a.graph_id
        )
        chain_a.append(cell_a)

        # Attempt to query graph B with cell_id from graph A
        # This would happen if an attacker tries to inject cells
        # from a different graph to escalate privileges

        # Pattern: Integrity check should detect graph_id mismatch
        # and raise IntegrityFailError with code DG_INTEGRITY_FAIL
```

### Pattern 4: Authorization Bypass Testing
**What:** Test temporal and namespace authorization controls
**When to use:** Testing bridge and time-travel restrictions (SEC-05, SEC-02)
**Example:**
```python
# Source: DecisionGraph namespace.py patterns
from decisiongraph import create_chain, UnauthorizedError

class TestNamespaceTraversal:
    """SEC-02: Namespace traversal returns DG_INPUT_INVALID"""

    @pytest.mark.parametrize("malicious_namespace,attack_type", [
        ("corp..hr", "double-dot traversal"),
        ("corp/hr", "slash instead of dot"),
        ("corp/../admin", "Unix path traversal"),
        ("corp\\hr", "Windows path separator"),
        ("/etc/passwd", "absolute path injection"),
        ("corp.hr.", "trailing dot"),
        (".hr", "leading dot"),
        ("corp...", "multiple trailing dots"),
    ])
    def test_traversal_attempts_rejected(
        self,
        malicious_namespace: str,
        attack_type: str
    ) -> None:
        """Namespace traversal patterns fail validation"""
        from decisiongraph.cell import validate_namespace

        # validate_namespace returns bool, not exception
        result = validate_namespace(malicious_namespace)
        assert result is False  # Invalid format detected
```

### Anti-Patterns to Avoid
- **Testing only happy path:** Adversarial tests MUST include malicious inputs, not just valid ones
- **Catching generic Exception:** Always verify specific exception type (InputInvalidError, IntegrityFailError, etc.)
- **Not checking error codes:** Verify .code == "DG_INPUT_INVALID", not just that exception was raised
- **Modifying existing tests:** Add NEW adversarial tests, keep existing 342 tests passing
- **Testing implementation details:** Test external behavior (error codes), not internal regex patterns

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SQL injection payloads | Custom attack strings | OWASP/SQLiDetector patterns | Community-tested payloads cover edge cases like encoding bypasses |
| Path traversal patterns | Manual ../ variants | OWASP Testing Guide patterns | Comprehensive list including OS-specific variations |
| Signature tampering | Random bit flips | Targeted byte positions | Test specific attack vectors (flip first byte, last byte, middle) |
| Test organization | Separate files per payload | pytest.mark.parametrize | Reduces duplication, groups related attacks |

**Key insight:** Security testing has well-documented attack patterns (OWASP, CVE databases). Use established payloads rather than inventing attacks, as community patterns cover real-world bypasses.

## Common Pitfalls

### Pitfall 1: Testing Wrong Layer
**What goes wrong:** Testing that validator rejects input, but not that it's called before Scholar
**Why it happens:** Unit tests validate individual functions, miss integration gaps
**How to avoid:** Test end-to-end through Engine.process_rfa() to verify defense layers
**Warning signs:** Validator has tests that pass, but injection succeeds in integration

### Pitfall 2: Not Verifying Error Codes
**What goes wrong:** Test checks exception is raised, but not the .code attribute
**Why it happens:** pytest.raises verifies exception type, easy to forget .code check
**How to avoid:** Always assert exc_info.value.code == "DG_INPUT_INVALID" after pytest.raises
**Warning signs:** Tests pass but external developers get wrong error codes

### Pitfall 3: Signature Verification Exception vs. Boolean
**What goes wrong:** Expecting verify_signature to raise exception on invalid signature
**Why it happens:** Cryptography library raises InvalidSignature, but DecisionGraph wraps it
**How to avoid:** DecisionGraph's verify_signature() returns False for invalid signatures (normal control flow), only raises SignatureInvalidError for format errors (wrong key/signature length)
**Warning signs:** Tests expect exception but get False return value

### Pitfall 4: Breaking Existing Tests
**What goes wrong:** Adding adversarial tests changes behavior, breaks existing 342 tests
**Why it happens:** Modifying validators or error handling affects all callers
**How to avoid:** Run full test suite (pytest tests/) before and after adding adversarial tests
**Warning signs:** "342 tests remain passing" requirement fails

### Pitfall 5: Incomplete Attack Coverage
**What goes wrong:** Test covers SQL injection but not null byte injection
**Why it happens:** Focus on obvious attacks, miss encoding-based bypasses
**How to avoid:** Use parametrize with comprehensive attack list from OWASP/CVE sources
**Warning signs:** Real-world attack succeeds despite passing tests

## Code Examples

Verified patterns from official sources:

### Testing Input Validation with Multiple Attack Vectors
```python
# Source: pytest docs + DecisionGraph test_validators.py patterns
import pytest
from decisiongraph import validate_subject_field, InputInvalidError

class TestSubjectInjection:
    """SEC-01 variant: Subject field injection protection"""

    @pytest.mark.parametrize("malicious_subject,reason", [
        ("user:alice;DROP TABLE", "semicolon injection"),
        ("user:alice\x00admin", "null byte injection"),
        ("user:alice' OR '1'='1", "SQL quote injection"),
        ("user:alice\nAND 1=1", "newline injection"),
        ("user:alice--comment", "SQL comment"),
        ("user:alice/**/admin", "comment bypass"),
        ("USER:alice", "case bypass"),
        ("user:alice@domain", "forbidden character @"),
        ("user:alice#anchor", "forbidden character #"),
    ])
    def test_injection_rejected_with_correct_code(
        self,
        malicious_subject: str,
        reason: str
    ) -> None:
        """Malicious subjects return DG_INPUT_INVALID"""
        with pytest.raises(InputInvalidError) as exc_info:
            validate_subject_field(malicious_subject)

        # Verify error code (CRITICAL for external developers)
        assert exc_info.value.code == "DG_INPUT_INVALID"

        # Verify error is actionable
        assert "field" in exc_info.value.details
        assert exc_info.value.details["field"] == "subject"
```

### Testing Signature Tampering Detection
```python
# Source: DecisionGraph signing.py + test_signing.py
import pytest
from decisiongraph import (
    sign_bytes,
    verify_signature,
    generate_ed25519_keypair,
    process_rfa,
    create_chain,
    SignatureInvalidError
)

class TestProofPacketTampering:
    """SEC-04: ProofPacket signature tampering detection"""

    def test_single_byte_modification_detected(self):
        """Modifying 1 byte in signature breaks verification"""
        # Generate signed ProofPacket
        chain = create_chain("test_graph")
        priv, pub = generate_ed25519_keypair()

        rfa = {
            "namespace": "corp.hr",
            "requester_namespace": "corp.audit",
            "requester_id": "auditor:alice"
        }

        packet = process_rfa(chain, rfa, signing_key=priv, public_key=pub)

        # Verify original packet
        from decisiongraph import verify_proof_packet
        assert verify_proof_packet(packet, pub) is True

        # Tamper: modify 1 byte in signature
        sig_b64 = packet["signature"]["signature"]
        import base64
        sig_bytes = base64.b64decode(sig_b64)
        tampered_bytes = sig_bytes[:-1] + bytes([sig_bytes[-1] ^ 0xFF])
        packet["signature"]["signature"] = base64.b64encode(tampered_bytes).decode()

        # Verification fails (returns False, not exception)
        assert verify_proof_packet(packet, pub) is False

    @pytest.mark.parametrize("modification", [
        "flip_first_byte",
        "flip_last_byte",
        "flip_middle_byte",
        "truncate_signature",
        "append_byte"
    ])
    def test_various_tampering_methods(self, modification: str):
        """Different tampering methods all fail verification"""
        # Pattern: Generate valid packet, apply modification, verify failure
        pass  # Implementation follows single_byte pattern above
```

### Testing Namespace Traversal Prevention
```python
# Source: OWASP Path Traversal patterns + DecisionGraph validators
import pytest
from decisiongraph import create_chain, process_rfa, InputInvalidError

class TestNamespaceTraversal:
    """SEC-02: Namespace traversal attacks return DG_INPUT_INVALID"""

    @pytest.mark.parametrize("malicious_namespace", [
        "corp..hr",           # Double-dot (path traversal)
        "corp/hr",            # Slash instead of dot
        "corp/../admin",      # Unix traversal
        "corp\\hr",           # Windows separator
        "/etc/passwd",        # Absolute path
        "corp.hr.",           # Trailing dot
        ".hidden",            # Leading dot
        "corp...hr",          # Multiple dots
        "corp.hr\x00admin",   # Null byte injection
        "corp.hr;admin",      # Semicolon injection
    ])
    def test_traversal_rejected_at_entry_point(self, malicious_namespace: str):
        """Namespace traversal fails at RFA entry point"""
        chain = create_chain("test")

        rfa = {
            "namespace": malicious_namespace,  # Attack vector
            "requester_namespace": "corp.audit",
            "requester_id": "auditor:alice"
        }

        # Should raise InputInvalidError at validation layer
        with pytest.raises(InputInvalidError) as exc_info:
            process_rfa(chain, rfa)

        assert exc_info.value.code == "DG_INPUT_INVALID"
        assert "namespace" in str(exc_info.value).lower()
```

### Testing Cross-Graph Integrity
```python
# Source: DecisionGraph chain.py + existing integrity tests
import pytest
from decisiongraph import create_chain, create_cell, IntegrityFailError

class TestCrossGraphContamination:
    """SEC-03: Cross-graph contamination returns DG_INTEGRITY_FAIL"""

    def test_cell_from_different_graph_rejected(self):
        """Cannot append cell with mismatched graph_id"""
        chain_a = create_chain("graph_a")
        chain_b = create_chain("graph_b")

        # Create cell with graph_a's ID
        cell_a = create_cell(
            namespace="corp.hr",
            subject="user:alice",
            predicate="has_salary",
            object_value="100000",
            graph_id=chain_a.graph_id
        )

        # Attempt to append to graph_b (different graph_id)
        with pytest.raises(IntegrityFailError) as exc_info:
            chain_b.append(cell_a)

        assert exc_info.value.code == "DG_INTEGRITY_FAIL"
        assert "graph_id" in exc_info.value.details
```

### Testing Bridge Time-Travel Prevention
```python
# Source: DecisionGraph namespace authorization logic
import pytest
from decisiongraph import create_chain, UnauthorizedError

class TestBridgeTimeTravelAttack:
    """SEC-05: Bridge time-travel returns DG_UNAUTHORIZED"""

    def test_query_before_bridge_creation_fails(self):
        """Query with as_of_system_time before bridge creation is unauthorized"""
        # This test verifies that an attacker cannot use as_of_system_time
        # to query data from before a bridge was established, bypassing
        # authorization controls that were added later

        # Pattern: Create bridge at time T1, attempt query at time T0 < T1
        # Expected: UnauthorizedError with code DG_UNAUTHORIZED

        # Implementation requires understanding bridge temporal logic
        # from Phase 4 RFA processing layer
        pass  # Implement based on bridge creation timestamp logic
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Regex without fullmatch() | Regex with fullmatch() | Phase 2 (Input Validation) | Prevents suffix injection attacks |
| Generic Exception | Specific error codes | Phase 1 (Error Foundation) | External developers get deterministic codes |
| Boolean validation only | Exception-based validation | Phase 2 | Stack traces show where validation failed |
| verify_signature raises exception | verify_signature returns bool | Phase 3 (Signing) | Invalid signature is normal control flow, not error |

**Deprecated/outdated:**
- **Manual string checking:** Phase 2 introduced pre-compiled regex patterns at module level
- **Ad-hoc validation:** Phase 2 centralized validation in validators.py
- **Generic error messages:** Phase 1 introduced actionable messages with details dict

## Open Questions

Things that couldn't be fully resolved:

1. **Bridge time-travel attack mechanics**
   - What we know: SEC-05 requires "Query with as_of_system_time before bridge creation fails with DG_UNAUTHORIZED"
   - What's unclear: Exact timestamp comparison logic in bridge authorization
   - Recommendation: Review Phase 4 RFA processing for bridge temporal checks, then implement test

2. **Cross-graph contamination attack vector**
   - What we know: SEC-03 requires "RFA referencing cell_id from different graph fails with DG_INTEGRITY_FAIL"
   - What's unclear: How RFA would reference cell_id (is cell_id exposed in RFA schema?)
   - Recommendation: Review RFA schema and Scholar query logic to understand cell_id exposure

3. **Test count verification**
   - What we know: "Existing 342 tests remain passing" is success criteria
   - What's unclear: Current test count (need to verify baseline)
   - Recommendation: Run `pytest --collect-only | grep "test session starts"` to confirm baseline

## Sources

### Primary (HIGH confidence)
- pytest official documentation - https://docs.pytest.org/en/stable/how-to/parametrize.html
- PyCA Cryptography Ed25519 docs - https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/
- DecisionGraph source code:
  - /src/decisiongraph/validators.py (VAL-01/02/03/04 implementation)
  - /src/decisiongraph/exceptions.py (Error code definitions)
  - /src/decisiongraph/signing.py (Ed25519 signature verification)
  - /tests/test_validators.py (Existing test patterns)
  - /tests/test_signing.py (Signature testing patterns)

### Secondary (MEDIUM confidence)
- OWASP Path Traversal guide - https://owasp.org/www-community/attacks/Path_Traversal (January 2026 current)
- OWASP Testing Directory Traversal - https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/05-Authorization_Testing/01-Testing_Directory_Traversal_File_Include
- Ed25519 Spec Check (test vectors) - https://github.com/novifinancial/ed25519-speccheck
- SQLiDetector patterns - https://github.com/eslam3kl/SQLiDetector (152 regex patterns for injection testing)

### Tertiary (LOW confidence)
- Python security best practices articles (2026 web search results) - general guidance only
- Stack Overflow pytest patterns - verified against official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest and parametrization are official, documented features already in use
- Architecture: HIGH - Patterns derived from existing DecisionGraph tests and official pytest docs
- Pitfalls: HIGH - Based on actual DecisionGraph implementation (verify_signature returns bool, not exception)

**Research date:** 2026-01-27
**Valid until:** 2026-02-27 (30 days - pytest and cryptography are stable)
