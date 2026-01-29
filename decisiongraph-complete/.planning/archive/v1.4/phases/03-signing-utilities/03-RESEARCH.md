# Phase 3: Signing Utilities - Research

**Researched:** 2026-01-27
**Domain:** Ed25519 cryptographic signatures in Python (sign/verify utilities)
**Confidence:** HIGH

## Summary

This research investigated Python libraries and best practices for implementing Ed25519 digital signatures for signing and verifying data. The goal is to provide two simple utility functions (`sign_bytes()` and `verify_signature()`) that work with Ed25519 keys and produce deterministic 64-byte signatures.

Ed25519 is a modern elliptic curve signature algorithm specified in [RFC 8032](https://datatracker.ietf.org/doc/html/rfc8032). It is **deterministic** (same input + key = same signature), fast, and has a 2^128 security target. The signature scheme is widely adopted and was added to FIPS 186-5 in 2023.

The standard approach in Python is to use either the **cryptography** library (PyCA, uses OpenSSL) or **PyNaCl** (PyCA, uses libsodium). Both are maintained by the Python Cryptographic Authority and provide high-quality Ed25519 implementations. For DecisionGraph's needs (simple sign/verify, no key derivation), the **cryptography** library is recommended as it's more widely deployed and uses the industry-standard OpenSSL backend.

**Primary recommendation:** Use the `cryptography` library with `Ed25519PrivateKey` and `Ed25519PublicKey` classes. Implement two functions: `sign_bytes(private_key, data)` returns 64-byte signature, `verify_signature(public_key, data, signature)` returns True/False. Raise `SignatureInvalidError` for invalid keys or verification failures.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| cryptography | 46.x+ | Ed25519 signing and verification | Industry-standard, PyCA-maintained, uses OpenSSL 3.x backend, supports Python 3.8+ |
| typing | stdlib | Type hints for function signatures | Enables static type checking for key/signature types |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyNaCl | 1.6.x | Alternative Ed25519 implementation | If you prefer libsodium backend or need additional NaCl features like secret boxes |
| base64 | stdlib | Encoding signatures for storage/display | If signatures need to be stored as base64 strings instead of raw bytes |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| cryptography | PyNaCl | Both are PyCA-maintained; PyNaCl uses libsodium (10-20x faster than old python-ed25519) but cryptography is more widely deployed |
| cryptography | python-ed25519 | python-ed25519 is deprecated; documentation recommends PyNaCl for new projects |
| cryptography | hashlib.sha256 + manual signing | Never hand-roll crypto; Ed25519 has complex math (scalar multiplication, point encoding) |
| External service | In-process library | External signing adds latency and violates "self-contained" constraint |

**Installation:**
```bash
pip install cryptography>=46.0
# OR
pip install PyNaCl>=1.6.0
```

## Architecture Patterns

### Recommended Project Structure
```
src/decisiongraph/
├── exceptions.py        # Already exists: SignatureInvalidError
├── signing.py          # NEW: Ed25519 sign/verify utilities
├── cell.py             # Existing: Has Proof class with signature field
├── namespace.py        # Existing: Has Signature class for bridge approvals
└── ...
```

### Pattern 1: Simple Sign/Verify Functions (Cryptography Library)
**What:** Two pure functions for signing and verification using Ed25519
**When to use:** When you need deterministic signatures without key management complexity
**Example:**
```python
# Source: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/
from cryptography.hazmat.primitives.asymmetric import ed25519
from typing import bytes as Bytes

def sign_bytes(private_key: bytes, data: bytes) -> bytes:
    """
    Sign data using Ed25519 and return 64-byte signature.

    Args:
        private_key: 32-byte Ed25519 private key seed
        data: Data to sign (any bytes)

    Returns:
        64-byte Ed25519 signature

    Raises:
        SignatureInvalidError: If private_key is invalid format

    Note:
        Ed25519 signatures are deterministic: same key + data = same signature
    """
    try:
        # Load private key from 32-byte seed
        key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key)

        # Sign and return 64-byte signature
        signature = key.sign(data)
        return signature

    except ValueError as e:
        from .exceptions import SignatureInvalidError
        raise SignatureInvalidError(
            message=f"Invalid private key format: {str(e)}",
            details={"key_length": len(private_key), "expected": 32}
        ) from e


def verify_signature(public_key: bytes, data: bytes, signature: bytes) -> bool:
    """
    Verify Ed25519 signature.

    Args:
        public_key: 32-byte Ed25519 public key
        data: Data that was signed
        signature: 64-byte Ed25519 signature to verify

    Returns:
        True if signature is valid, False otherwise

    Raises:
        SignatureInvalidError: If public_key or signature format is invalid

    Note:
        Does NOT raise on verification failure (returns False).
        Only raises if keys/signatures are malformed.
    """
    try:
        # Load public key from 32 bytes
        key = ed25519.Ed25519PublicKey.from_public_bytes(public_key)

        # Verify signature (raises InvalidSignature on failure)
        key.verify(signature, data)
        return True

    except ValueError as e:
        from .exceptions import SignatureInvalidError
        raise SignatureInvalidError(
            message=f"Invalid key or signature format: {str(e)}",
            details={
                "public_key_length": len(public_key),
                "signature_length": len(signature),
                "expected_key": 32,
                "expected_sig": 64
            }
        ) from e

    except ed25519.InvalidSignature:
        # Verification failed - return False, don't raise
        return False
```

**Why this pattern:**
- Uses cryptography library's high-level API (not "hazmat" layer)
- Accepts raw bytes (32-byte keys, 64-byte signatures) per RFC 8032
- Separates format errors (raise SignatureInvalidError) from verification failures (return False)
- Deterministic: same key + data always produces same signature

### Pattern 2: Key Generation (For Testing)
**What:** Helper function to generate Ed25519 key pairs for testing
**When to use:** In test suite, NOT in production code (keys are passed in)
**Example:**
```python
# Source: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/
from cryptography.hazmat.primitives.asymmetric import ed25519
from typing import Tuple

def generate_ed25519_keypair() -> Tuple[bytes, bytes]:
    """
    Generate a new Ed25519 key pair for testing.

    Returns:
        Tuple of (private_key_bytes, public_key_bytes)
        - private_key_bytes: 32-byte seed
        - public_key_bytes: 32-byte public key

    Note:
        For testing only. Production keys should be managed externally.
    """
    private_key = ed25519.Ed25519PrivateKey.generate()

    # Extract raw bytes
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )

    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )

    return (private_bytes, public_bytes)
```

**Why this pattern:**
- Only for test suite, not exposed in main API
- Uses cryptography's key generation (cryptographically secure random)
- Returns raw bytes for compatibility with sign_bytes/verify_signature

### Pattern 3: Signature Verification in Commit Gate (Future Phase 4)
**What:** Optional signature verification when cells are committed to chain
**When to use:** When `signature_required=True` on a cell's Proof
**Example:**
```python
# Source: Derived from DecisionGraph architecture
# This is for Phase 4, but shows how signing utilities integrate

def commit_cell(cell: DecisionCell, require_signature: bool = False) -> None:
    """
    Commit cell to chain with optional signature verification.

    Args:
        cell: The cell to commit
        require_signature: If True, verify cell.proof.signature

    Raises:
        SignatureInvalidError: If signature required but invalid
    """
    # If signature is required (bootstrap_mode=False)
    if require_signature or cell.proof.signature_required:
        if not cell.proof.signature:
            raise SignatureInvalidError(
                message="Signature required but not present",
                details={"cell_id": cell.cell_id[:16]}
            )

        # Get public key for signer_key_id (from registry or config)
        public_key = get_public_key_for_signer(cell.proof.signer_key_id)

        # Compute canonical bytes for cell (excluding signature field)
        cell_bytes = compute_canonical_cell_bytes(cell)

        # Verify signature
        is_valid = verify_signature(public_key, cell_bytes, cell.proof.signature)

        if not is_valid:
            raise SignatureInvalidError(
                message="Cell signature verification failed",
                details={
                    "cell_id": cell.cell_id[:16],
                    "signer_key_id": cell.proof.signer_key_id
                }
            )

    # Continue with chain append...
```

**Why this pattern:**
- Signature verification is OPTIONAL (bootstrap mode allows unsigned cells)
- Verification happens at commit gate (before chain append)
- Uses canonical cell bytes (deterministic serialization)
- Raises SignatureInvalidError (not generic ValueError)

### Pattern 4: Canonical Bytes Computation
**What:** Deterministic serialization of data structure for signing
**When to use:** Before signing or verifying any structured data (cells, packets)
**Example:**
```python
# Source: Derived from existing DecisionGraph canonicalization patterns
import json
from typing import Dict, Any

def compute_canonical_cell_bytes(cell: DecisionCell) -> bytes:
    """
    Compute canonical byte representation of cell for signing.

    The signature field is EXCLUDED from the bytes being signed
    (otherwise signature would depend on itself).

    Args:
        cell: The cell to serialize

    Returns:
        UTF-8 encoded canonical JSON bytes

    Note:
        Uses same canonicalization as cell_id computation:
        - Sorted keys
        - No whitespace
        - Deterministic encoding
    """
    # Convert cell to dict
    cell_dict = cell.to_dict()

    # IMPORTANT: Remove signature field before signing
    if "proof" in cell_dict and "signature" in cell_dict["proof"]:
        cell_dict["proof"]["signature"] = None

    # Canonical JSON: sorted keys, no whitespace, deterministic
    canonical_json = json.dumps(
        cell_dict,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=True
    )

    return canonical_json.encode('utf-8')
```

**Why this pattern:**
- Signature field excluded (would create circular dependency)
- Uses same canonicalization as existing cell_id computation
- Deterministic: same cell always produces same bytes
- UTF-8 encoding is standard for JSON bytes

### Anti-Patterns to Avoid
- **Using ECDSA instead of Ed25519:** ECDSA requires careful nonce generation; Ed25519 is deterministic and safer
- **Hand-rolling Ed25519 math:** Never implement curve25519 scalar multiplication yourself; use vetted libraries
- **Signing mutable data structures:** Always serialize to canonical bytes first
- **Including signature field in signed data:** Signature can't sign itself; exclude it
- **Using `verify()` exceptions for control flow:** Catch InvalidSignature, return False (verification failure is not exceptional)
- **Storing keys as strings without encoding:** Always specify base64/hex encoding explicitly
- **Using deprecated python-ed25519:** Use cryptography or PyNaCl instead

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Ed25519 signing | Manual curve25519 math | cryptography library | Ed25519 requires constant-time scalar multiplication, point compression, and careful modular arithmetic |
| Key generation | Random bytes | `Ed25519PrivateKey.generate()` | Needs cryptographically secure random source; library handles this |
| Signature format | Custom binary packing | RFC 8032 format (R \|\| s) | Ed25519 signatures are (R, s) where R is compressed point (32 bytes), s is scalar (32 bytes) = 64 bytes total |
| Key serialization | String concatenation | serialization.Encoding.Raw | Proper key encoding handles point compression and format standards |
| Constant-time comparison | `==` operator | `hmac.compare_digest()` | Signature verification must be constant-time to prevent timing attacks (library handles this) |

**Key insight:** Ed25519 is simple to USE but complex to IMPLEMENT. The cryptography library provides a safe, performant implementation with proper side-channel protections. Never implement elliptic curve operations yourself.

## Common Pitfalls

### Pitfall 1: Not Excluding Signature Field When Computing Signed Bytes
**What goes wrong:** Signature computation includes the signature field, creating circular dependency
**Why it happens:** Forgetting that signature is part of the data structure being signed
**How to avoid:** Always set signature field to None/null before computing canonical bytes
**Warning signs:** Signature verification always fails; signature changes every time you re-sign

### Pitfall 2: Using Non-Deterministic Serialization
**What goes wrong:** Same cell produces different bytes each time, breaking signature verification
**Why it happens:** JSON dict ordering is not guaranteed in Python < 3.7; whitespace varies
**How to avoid:** Use `json.dumps()` with `sort_keys=True` and fixed separators
**Warning signs:** Intermittent signature verification failures; signature doesn't match on different machines

### Pitfall 3: Raising Exceptions on Verification Failure
**What goes wrong:** Code treats invalid signatures as exceptional errors instead of normal False return
**Why it happens:** Misunderstanding the difference between format errors and verification failures
**How to avoid:** Raise SignatureInvalidError for format problems; return False for verification failures
**Warning signs:** Exceptions in normal control flow; try/except blocks around every verify call

### Pitfall 4: Not Validating Key/Signature Lengths Before Verification
**What goes wrong:** Library raises cryptic errors for wrong-length inputs
**Why it happens:** Assuming all byte strings are valid keys/signatures
**How to avoid:** Check lengths (32 bytes for keys, 64 bytes for signatures) and raise InputInvalidError early
**Warning signs:** ValueError exceptions with messages like "key must be 32 bytes"

### Pitfall 5: Storing Keys as Hex Strings Without Clear Encoding Convention
**What goes wrong:** Key confusion between hex, base64, raw bytes leads to verification failures
**Why it happens:** Different parts of codebase use different encodings
**How to avoid:** Choose ONE encoding (recommend raw bytes internally, base64 for external APIs) and document it
**Warning signs:** Signature verification fails with "invalid key format"; keys have wrong length

### Pitfall 6: Not Using Constant-Time Verification
**What goes wrong:** Timing attacks can leak information about signatures
**Why it happens:** Using `==` to compare signatures instead of library's verify method
**How to avoid:** Always use library's `verify()` method, which implements constant-time comparison
**Warning signs:** Security audits flag timing vulnerabilities; manual signature comparison code

## Code Examples

Verified patterns from official sources:

### Complete Sign/Verify Implementation (Cryptography Library)
```python
# Source: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature
from typing import bytes as Bytes

from .exceptions import SignatureInvalidError


def sign_bytes(private_key: bytes, data: bytes) -> bytes:
    """
    Sign data using Ed25519.

    Args:
        private_key: 32-byte Ed25519 private key seed
        data: Data to sign

    Returns:
        64-byte Ed25519 signature (deterministic)

    Raises:
        SignatureInvalidError: If private_key is invalid format

    Example:
        >>> private_key = generate_ed25519_keypair()[0]
        >>> signature = sign_bytes(private_key, b"hello world")
        >>> len(signature)
        64
        >>> # Deterministic: same input produces same signature
        >>> sign_bytes(private_key, b"hello world") == signature
        True
    """
    if not isinstance(private_key, bytes) or len(private_key) != 32:
        raise SignatureInvalidError(
            message="Private key must be 32 bytes",
            details={
                "provided_length": len(private_key) if isinstance(private_key, bytes) else None,
                "expected_length": 32
            }
        )

    try:
        key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key)
        signature = key.sign(data)
        return signature

    except (ValueError, TypeError) as e:
        raise SignatureInvalidError(
            message=f"Invalid private key format: {str(e)}",
            details={"error": type(e).__name__}
        ) from e


def verify_signature(public_key: bytes, data: bytes, signature: bytes) -> bool:
    """
    Verify Ed25519 signature.

    Args:
        public_key: 32-byte Ed25519 public key
        data: Data that was signed
        signature: 64-byte Ed25519 signature

    Returns:
        True if signature is valid, False otherwise

    Raises:
        SignatureInvalidError: If public_key or signature format is invalid

    Example:
        >>> priv, pub = generate_ed25519_keypair()
        >>> sig = sign_bytes(priv, b"hello")
        >>> verify_signature(pub, b"hello", sig)
        True
        >>> verify_signature(pub, b"goodbye", sig)
        False
        >>> # Tampering detected
        >>> verify_signature(pub, b"hello", sig[:-1] + b'\\x00')
        False
    """
    # Validate input formats
    if not isinstance(public_key, bytes) or len(public_key) != 32:
        raise SignatureInvalidError(
            message="Public key must be 32 bytes",
            details={
                "provided_length": len(public_key) if isinstance(public_key, bytes) else None,
                "expected_length": 32
            }
        )

    if not isinstance(signature, bytes) or len(signature) != 64:
        raise SignatureInvalidError(
            message="Signature must be 64 bytes",
            details={
                "provided_length": len(signature) if isinstance(signature, bytes) else None,
                "expected_length": 64
            }
        )

    try:
        key = ed25519.Ed25519PublicKey.from_public_bytes(public_key)
        key.verify(signature, data)
        return True

    except (ValueError, TypeError) as e:
        raise SignatureInvalidError(
            message=f"Invalid public key format: {str(e)}",
            details={"error": type(e).__name__}
        ) from e

    except InvalidSignature:
        # Verification failed - this is NOT an error, just invalid signature
        return False
```

### Key Generation for Testing
```python
# Source: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from typing import Tuple


def generate_ed25519_keypair() -> Tuple[bytes, bytes]:
    """
    Generate Ed25519 key pair for testing.

    Returns:
        Tuple of (private_key_bytes, public_key_bytes)
        Both are raw bytes (32 bytes each)

    Example:
        >>> priv, pub = generate_ed25519_keypair()
        >>> len(priv), len(pub)
        (32, 32)
        >>> # Public key can be derived from private key
        >>> priv2, pub2 = generate_ed25519_keypair()
        >>> priv != priv2  # Different keys each time
        True
    """
    # Generate private key
    private_key = ed25519.Ed25519PrivateKey.generate()

    # Extract raw bytes (32 bytes)
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )

    # Extract public key raw bytes (32 bytes)
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )

    return (private_bytes, public_bytes)
```

### Testing Signature Utilities
```python
# Source: Python unittest/pytest patterns + Ed25519 properties
import pytest


class TestSigningUtilities:
    """Tests for Phase 3: Signing Utilities"""

    def test_sign_produces_64_byte_signature(self):
        """SIG-01: sign_bytes produces 64-byte Ed25519 signature"""
        priv, pub = generate_ed25519_keypair()
        data = b"test data"

        signature = sign_bytes(priv, data)

        assert isinstance(signature, bytes)
        assert len(signature) == 64

    def test_verify_accepts_valid_signature(self):
        """SIG-02: verify_signature returns True for valid signature"""
        priv, pub = generate_ed25519_keypair()
        data = b"test data"
        signature = sign_bytes(priv, data)

        result = verify_signature(pub, data, signature)

        assert result is True

    def test_verify_rejects_tampered_data(self):
        """SIG-02: Tampered data fails verification"""
        priv, pub = generate_ed25519_keypair()
        data = b"test data"
        signature = sign_bytes(priv, data)

        # Change one byte
        tampered_data = b"test datX"
        result = verify_signature(pub, tampered_data, signature)

        assert result is False

    def test_verify_rejects_tampered_signature(self):
        """SIG-02: Tampered signature fails verification"""
        priv, pub = generate_ed25519_keypair()
        data = b"test data"
        signature = sign_bytes(priv, data)

        # Change one byte in signature
        tampered_sig = signature[:-1] + bytes([signature[-1] ^ 0xFF])
        result = verify_signature(pub, data, tampered_sig)

        assert result is False

    def test_signing_is_deterministic(self):
        """Ed25519 signatures are deterministic"""
        priv, pub = generate_ed25519_keypair()
        data = b"test data"

        sig1 = sign_bytes(priv, data)
        sig2 = sign_bytes(priv, data)

        assert sig1 == sig2

    def test_invalid_key_length_raises_error(self):
        """Invalid key format raises DG_SIGNATURE_INVALID"""
        with pytest.raises(SignatureInvalidError) as exc_info:
            sign_bytes(b"tooshort", b"data")

        assert exc_info.value.code == "DG_SIGNATURE_INVALID"
        assert "32 bytes" in str(exc_info.value)

    def test_invalid_signature_length_raises_error(self):
        """Invalid signature format raises DG_SIGNATURE_INVALID"""
        priv, pub = generate_ed25519_keypair()

        with pytest.raises(SignatureInvalidError) as exc_info:
            verify_signature(pub, b"data", b"tooshort")

        assert exc_info.value.code == "DG_SIGNATURE_INVALID"
        assert "64 bytes" in str(exc_info.value)
```

### Alternative Implementation (PyNaCl)
```python
# Source: https://pynacl.readthedocs.io/en/1.0.1/signing/
# Alternative if you prefer PyNaCl over cryptography
from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError

from .exceptions import SignatureInvalidError


def sign_bytes_nacl(private_key: bytes, data: bytes) -> bytes:
    """Sign data using Ed25519 (PyNaCl implementation)"""
    try:
        signing_key = SigningKey(private_key)
        signed_message = signing_key.sign(data)
        # Extract just the signature (not the signed message)
        return signed_message.signature

    except (ValueError, TypeError) as e:
        raise SignatureInvalidError(
            message=f"Invalid private key: {str(e)}",
            details={"error": type(e).__name__}
        ) from e


def verify_signature_nacl(public_key: bytes, data: bytes, signature: bytes) -> bool:
    """Verify Ed25519 signature (PyNaCl implementation)"""
    try:
        verify_key = VerifyKey(public_key)
        # PyNaCl expects signature + message concatenated
        verify_key.verify(data, signature)
        return True

    except BadSignatureError:
        return False

    except (ValueError, TypeError) as e:
        raise SignatureInvalidError(
            message=f"Invalid key or signature: {str(e)}",
            details={"error": type(e).__name__}
        ) from e
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ECDSA with random nonce | Ed25519 with deterministic nonce | 2011 (Ed25519 published) | Eliminates nonce generation vulnerabilities; deterministic signing |
| python-ed25519 library | cryptography or PyNaCl | 2020+ (python-ed25519 deprecated) | Better maintained, faster (10-20x), integrated with PyCA ecosystem |
| Manual constant-time comparison | Library-provided verify() | Always standard | Prevents timing attacks; library handles side-channel protections |
| NIST P-256 (ECDSA) | Ed25519 | 2011+ (ongoing adoption) | Simpler implementation, deterministic, no known patents, similar security level |
| Random key generation | Deterministic from seed | RFC 8032 (2017) | Enables reproducible key derivation for testing |

**Deprecated/outdated:**
- **python-ed25519**: Deprecated; use cryptography or PyNaCl instead
- **Manual curve25519 implementations**: Use vetted libraries; hand-rolled crypto has subtle bugs
- **RSA for new systems**: Ed25519 is faster and has smaller keys/signatures for equivalent security
- **Using SHA-256 + RSA**: Ed25519 includes hash function internally (SHA-512 in signing algorithm)

## Standards and Specifications

### RFC 8032: Edwards-Curve Digital Signature Algorithm (EdDSA)
- **URL:** [RFC 8032](https://datatracker.ietf.org/doc/html/rfc8032)
- **Status:** Informational (January 2017)
- **Key points:**
  - Ed25519 signatures are 64 bytes (512 bits)
  - Public keys are 32 bytes (256 bits)
  - Private keys are 32 bytes (256 bits) seeds
  - Deterministic signing: signature = (R, s) where R and s are computed from hash of private key + message
  - Signature format: R (32 bytes) || s (32 bytes)

### FIPS 186-5: Digital Signature Standard
- **Status:** Final version (2023) includes Ed25519
- **Significance:** Ed25519 is now federally approved for government use
- **Security level:** 2^128 (equivalent to RSA ~3000-bit keys or NIST P-256)

### Ed25519 Properties
- **Deterministic:** Same message + key = same signature (no random nonce)
- **Fast:** ~100x faster than RSA for verification
- **Compact:** 64-byte signatures vs 256+ bytes for RSA
- **Side-channel resistant:** Immune to cache-timing and branch-prediction attacks
- **No known patents:** Public domain algorithm

## Open Questions

Things that couldn't be fully resolved:

1. **Should we use cryptography or PyNaCl?**
   - What we know: Both are PyCA-maintained, high-quality, widely used
   - What's unclear: Which one is preferred for DecisionGraph's ecosystem
   - Recommendation: Use **cryptography** library (more widely deployed, OpenSSL backend, consistent with enterprise infrastructure)
   - Fallback: Either works; pick one and document it

2. **Should keys be stored as raw bytes, hex, or base64?**
   - What we know: Internal functions should use raw bytes for performance
   - What's unclear: External API representation (when keys are passed to/from engine)
   - Recommendation: Internal = raw bytes, external API = base64 (standard for binary in JSON)
   - Rationale: Base64 is URL-safe and widely supported

3. **Where should key-to-signer_key_id mapping be stored?**
   - What we know: Cells reference `signer_key_id`, not full public key
   - What's unclear: How to resolve signer_key_id → public_key for verification
   - Recommendation: Defer to Phase 4 (RFA Processing); for Phase 3, just implement sign/verify utilities
   - Note: Tests can use in-memory dict mapping

4. **Should we support key serialization formats (PEM, SSH)?**
   - What we know: RFC 8032 uses raw bytes; cryptography supports PEM/SSH formats
   - What's unclear: Whether DecisionGraph needs to interoperate with external key formats
   - Recommendation: Start with raw bytes only; add serialization formats if needed
   - Rationale: YAGNI - wait for actual requirement

5. **How should we handle bootstrap mode in signing utilities?**
   - What we know: Genesis cells can be unsigned in bootstrap mode
   - What's unclear: Whether sign_bytes() should accept None keys or if caller handles bootstrap mode
   - Recommendation: sign_bytes() always requires valid key; caller (Commit Gate) handles bootstrap logic
   - Rationale: Utilities stay simple; bootstrap complexity belongs in integration layer

## Sources

### Primary (HIGH confidence)
- [Ed25519 signing - Cryptography 47.0.0.dev1 documentation](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/) - Official cryptography library Ed25519 API
- [RFC 8032 - Edwards-Curve Digital Signature Algorithm (EdDSA)](https://datatracker.ietf.org/doc/html/rfc8032) - Official IETF specification
- [EdDSA and Ed25519 | Practical Cryptography for Developers](https://cryptobook.nakov.com/digital-signatures/eddsa-and-ed25519) - Ed25519 overview and properties
- [PyNaCl - Digital Signatures](https://pynacl.readthedocs.io/en/1.0.1/signing/) - PyNaCl Ed25519 API documentation
- [PyNaCl · PyPI](https://pypi.org/project/PyNaCl/) - PyNaCl library updates and status

### Secondary (MEDIUM confidence)
- [EdDSA - Wikipedia](https://en.wikipedia.org/wiki/EdDSA) - Ed25519 history and standardization
- [Ed25519 official site](https://ed25519.cr.yp.to/) - Original Ed25519 specification by djb
- [python-ed25519 README](https://github.com/warner/python-ed25519/blob/master/README.md) - Deprecation notice, recommendation to use PyNaCl
- [Frequently asked questions - Cryptography](https://cryptography.io/en/latest/faq/) - PyCA library comparison
- [Top Crypto Libraries for Python Developers in 2025](https://www.analyticsinsight.net/programming/top-crypto-libraries-for-python-developers-in-2025) - Library ecosystem overview

### Tertiary (LOW confidence)
- [piptrends.com - pynacl vs cryptography](https://piptrends.com/compare/pynacl-vs-cryptography) - Library adoption trends
- [Top 6 Python Cryptography Libraries](https://jsschools.com/python/top-6-python-cryptography-libraries-a-developers/) - General cryptography library guide

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Based on official PyCA documentation and RFC 8032
- Architecture: HIGH - Patterns verified in cryptography library examples and DecisionGraph existing structure
- Pitfalls: HIGH - Common issues documented in RFC 8032 and cryptographic engineering literature

**Research date:** 2026-01-27
**Valid until:** 2026-07-27 (180 days - cryptographic standards change slowly; Ed25519 is mature and stable)

**Notes:**
- Ed25519 is a mature, standardized algorithm with wide adoption
- The cryptography library is PyCA's flagship project and actively maintained
- Implementation is straightforward: two functions, deterministic behavior, clear error handling
- Phase 3 is self-contained; integration with Commit Gate happens in Phase 4
- Existing test suite has 281 tests; Phase 3 will add signature-specific tests
