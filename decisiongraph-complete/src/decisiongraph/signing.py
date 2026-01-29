"""
DecisionGraph Signing Utilities (v1.4)

Ed25519 cryptographic signing and verification for DecisionGraph.

Provides simple utilities for signing arbitrary data and verifying signatures
using Ed25519 (RFC 8032). Used by the RFA layer for cell signatures and
ProofPacket signing.

Key properties:
- Deterministic: Same key + data always produces same signature
- Fast: ~100x faster than RSA for verification
- Compact: 64-byte signatures, 32-byte keys
- Secure: 2^128 security level (equivalent to RSA ~3000-bit)

Functions:
- sign_bytes: Sign data with Ed25519 private key
- verify_signature: Verify Ed25519 signature
- generate_ed25519_keypair: Generate key pair for testing
"""

from typing import Tuple
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

from .exceptions import SignatureInvalidError

__all__ = [
    'sign_bytes',
    'verify_signature',
    'generate_ed25519_keypair',
]


def sign_bytes(private_key: bytes, data: bytes) -> bytes:
    """
    Sign data using Ed25519 and return 64-byte signature.

    Ed25519 signatures are deterministic: signing the same data with the
    same key always produces the same signature. This property is important
    for reproducibility and testing.

    Args:
        private_key: 32-byte Ed25519 private key seed
        data: Data to sign (any bytes)

    Returns:
        64-byte Ed25519 signature

    Raises:
        SignatureInvalidError: If private_key is not exactly 32 bytes or
            has invalid format

    Example:
        >>> priv, pub = generate_ed25519_keypair()
        >>> signature = sign_bytes(priv, b"hello world")
        >>> len(signature)
        64
        >>> # Deterministic: same input produces same signature
        >>> sign_bytes(priv, b"hello world") == signature
        True
    """
    # Validate input format BEFORE calling cryptography library
    # This provides clearer error messages
    if not isinstance(private_key, bytes):
        raise SignatureInvalidError(
            message="Private key must be bytes",
            details={
                "provided_type": type(private_key).__name__,
                "expected_type": "bytes"
            }
        )

    if len(private_key) != 32:
        raise SignatureInvalidError(
            message="Private key must be exactly 32 bytes",
            details={
                "provided_length": len(private_key),
                "expected_length": 32
            }
        )

    try:
        # Load private key from 32-byte seed
        key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key)

        # Sign and return 64-byte signature
        signature = key.sign(data)
        return signature

    except (ValueError, TypeError) as e:
        # Catch any additional validation errors from cryptography library
        raise SignatureInvalidError(
            message=f"Invalid private key format: {str(e)}",
            details={"internal_error": type(e).__name__}
        ) from e


def verify_signature(public_key: bytes, data: bytes, signature: bytes) -> bool:
    """
    Verify Ed25519 signature.

    Returns True if the signature is valid, False if verification fails.
    Note: Verification failure (wrong signature, tampered data) returns False,
    not an exception. Only format errors (wrong key/signature length) raise
    SignatureInvalidError.

    Args:
        public_key: 32-byte Ed25519 public key
        data: Data that was signed
        signature: 64-byte Ed25519 signature to verify

    Returns:
        True if signature is valid, False otherwise

    Raises:
        SignatureInvalidError: If public_key is not 32 bytes or signature
            is not 64 bytes

    Example:
        >>> priv, pub = generate_ed25519_keypair()
        >>> sig = sign_bytes(priv, b"hello")
        >>> verify_signature(pub, b"hello", sig)
        True
        >>> verify_signature(pub, b"goodbye", sig)
        False
        >>> # Tampering detected
        >>> tampered_sig = sig[:-1] + bytes([sig[-1] ^ 0xFF])
        >>> verify_signature(pub, b"hello", tampered_sig)
        False
    """
    # Validate public key format
    if not isinstance(public_key, bytes):
        raise SignatureInvalidError(
            message="Public key must be bytes",
            details={
                "provided_type": type(public_key).__name__,
                "expected_type": "bytes"
            }
        )

    if len(public_key) != 32:
        raise SignatureInvalidError(
            message="Public key must be exactly 32 bytes",
            details={
                "provided_length": len(public_key),
                "expected_length": 32
            }
        )

    # Validate signature format
    if not isinstance(signature, bytes):
        raise SignatureInvalidError(
            message="Signature must be bytes",
            details={
                "provided_type": type(signature).__name__,
                "expected_type": "bytes"
            }
        )

    if len(signature) != 64:
        raise SignatureInvalidError(
            message="Signature must be exactly 64 bytes",
            details={
                "provided_length": len(signature),
                "expected_length": 64
            }
        )

    try:
        # Load public key from 32 bytes
        key = ed25519.Ed25519PublicKey.from_public_bytes(public_key)

        # Verify signature (raises InvalidSignature on failure)
        key.verify(signature, data)
        return True

    except (ValueError, TypeError) as e:
        # Format error in key or signature
        raise SignatureInvalidError(
            message=f"Invalid public key format: {str(e)}",
            details={"internal_error": type(e).__name__}
        ) from e

    except InvalidSignature:
        # Verification failed - this is NOT an error, just invalid signature
        # Verification failure is a normal control flow outcome
        return False


def generate_ed25519_keypair() -> Tuple[bytes, bytes]:
    """
    Generate Ed25519 key pair for testing.

    Uses cryptographically secure random generation. Returns raw bytes
    in the format expected by sign_bytes() and verify_signature().

    WARNING: This is for testing only. Production keys should be managed
    externally and securely stored.

    Returns:
        Tuple of (private_key_bytes, public_key_bytes)
        - private_key_bytes: 32-byte private key seed
        - public_key_bytes: 32-byte public key

    Example:
        >>> priv, pub = generate_ed25519_keypair()
        >>> len(priv), len(pub)
        (32, 32)
        >>> # Each call generates new random keypair
        >>> priv2, pub2 = generate_ed25519_keypair()
        >>> priv != priv2
        True
        >>> # Generated keys work with sign/verify
        >>> sig = sign_bytes(priv, b"test")
        >>> verify_signature(pub, b"test", sig)
        True
    """
    # Generate private key using cryptographically secure random
    private_key = ed25519.Ed25519PrivateKey.generate()

    # Extract raw bytes (32 bytes) from private key
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
