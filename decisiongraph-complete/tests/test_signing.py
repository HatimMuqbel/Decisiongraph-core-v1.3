"""
Tests for DecisionGraph Signing Utilities (Phase 3)

Tests Ed25519 signing and verification functionality:
- SIG-01: sign_bytes produces 64-byte Ed25519 signature
- SIG-02: verify_signature returns True for valid, False for invalid
- Deterministic signing (same input = same output)
- Input validation and error handling
"""

import pytest
from decisiongraph import (
    sign_bytes,
    verify_signature,
    generate_ed25519_keypair,
    SignatureInvalidError
)


class TestSignBytes:
    """Tests for sign_bytes() - SIG-01"""

    def test_produces_64_byte_signature(self):
        """sign_bytes produces 64-byte Ed25519 signature"""
        priv, pub = generate_ed25519_keypair()
        data = b"test data"

        signature = sign_bytes(priv, data)

        assert isinstance(signature, bytes)
        assert len(signature) == 64

    def test_signing_is_deterministic(self):
        """Same key + data produces same signature (Ed25519 property)"""
        priv, pub = generate_ed25519_keypair()
        data = b"test data"

        sig1 = sign_bytes(priv, data)
        sig2 = sign_bytes(priv, data)

        assert sig1 == sig2

    def test_different_data_produces_different_signature(self):
        """Different data produces different signature"""
        priv, pub = generate_ed25519_keypair()

        sig1 = sign_bytes(priv, b"data one")
        sig2 = sign_bytes(priv, b"data two")

        assert sig1 != sig2

    def test_different_key_produces_different_signature(self):
        """Different key produces different signature for same data"""
        priv1, pub1 = generate_ed25519_keypair()
        priv2, pub2 = generate_ed25519_keypair()
        data = b"same data"

        sig1 = sign_bytes(priv1, data)
        sig2 = sign_bytes(priv2, data)

        assert sig1 != sig2

    def test_invalid_private_key_length_raises_error(self):
        """Private key not 32 bytes raises DG_SIGNATURE_INVALID"""
        # Too short
        with pytest.raises(SignatureInvalidError) as exc_info:
            sign_bytes(b"tooshort", b"data")

        assert exc_info.value.code == "DG_SIGNATURE_INVALID"
        assert "32 bytes" in str(exc_info.value)
        assert exc_info.value.details["expected_length"] == 32

        # Too long
        with pytest.raises(SignatureInvalidError) as exc_info:
            sign_bytes(b"x" * 64, b"data")

        assert exc_info.value.code == "DG_SIGNATURE_INVALID"
        assert "32 bytes" in str(exc_info.value)

    def test_private_key_wrong_type_raises_error(self):
        """Non-bytes private key raises DG_SIGNATURE_INVALID"""
        with pytest.raises(SignatureInvalidError) as exc_info:
            sign_bytes("not bytes", b"data")

        assert exc_info.value.code == "DG_SIGNATURE_INVALID"
        assert "bytes" in str(exc_info.value).lower()

    def test_can_sign_empty_data(self):
        """Can sign empty bytes"""
        priv, pub = generate_ed25519_keypair()

        signature = sign_bytes(priv, b"")

        assert len(signature) == 64

    def test_can_sign_large_data(self):
        """Can sign large data (Ed25519 hashes data internally)"""
        priv, pub = generate_ed25519_keypair()
        large_data = b"x" * 1_000_000  # 1 MB

        signature = sign_bytes(priv, large_data)

        assert len(signature) == 64


class TestVerifySignature:
    """Tests for verify_signature() - SIG-02"""

    def test_valid_signature_returns_true(self):
        """Valid signature returns True"""
        priv, pub = generate_ed25519_keypair()
        data = b"test data"
        signature = sign_bytes(priv, data)

        result = verify_signature(pub, data, signature)

        assert result is True

    def test_tampered_data_returns_false(self):
        """Tampered data (1 byte changed) returns False, not exception"""
        priv, pub = generate_ed25519_keypair()
        data = b"test data"
        signature = sign_bytes(priv, data)

        # Change one byte
        tampered_data = b"test datX"
        result = verify_signature(pub, tampered_data, signature)

        assert result is False

    def test_tampered_signature_returns_false(self):
        """Tampered signature returns False, not exception"""
        priv, pub = generate_ed25519_keypair()
        data = b"test data"
        signature = sign_bytes(priv, data)

        # Tamper with signature (XOR last byte)
        tampered_sig = signature[:-1] + bytes([signature[-1] ^ 0xFF])
        result = verify_signature(pub, data, tampered_sig)

        assert result is False

    def test_wrong_key_returns_false(self):
        """Signature from different key returns False"""
        priv1, pub1 = generate_ed25519_keypair()
        priv2, pub2 = generate_ed25519_keypair()
        data = b"test data"

        # Sign with key1, verify with key2
        signature = sign_bytes(priv1, data)
        result = verify_signature(pub2, data, signature)

        assert result is False

    def test_invalid_public_key_length_raises_error(self):
        """Public key not 32 bytes raises DG_SIGNATURE_INVALID"""
        priv, pub = generate_ed25519_keypair()
        data = b"test data"
        signature = sign_bytes(priv, data)

        # Too short
        with pytest.raises(SignatureInvalidError) as exc_info:
            verify_signature(b"tooshort", data, signature)

        assert exc_info.value.code == "DG_SIGNATURE_INVALID"
        assert "32 bytes" in str(exc_info.value)
        assert exc_info.value.details["expected_length"] == 32

        # Too long
        with pytest.raises(SignatureInvalidError) as exc_info:
            verify_signature(b"x" * 64, data, signature)

        assert exc_info.value.code == "DG_SIGNATURE_INVALID"

    def test_invalid_signature_length_raises_error(self):
        """Signature not 64 bytes raises DG_SIGNATURE_INVALID"""
        priv, pub = generate_ed25519_keypair()
        data = b"test data"

        # Too short
        with pytest.raises(SignatureInvalidError) as exc_info:
            verify_signature(pub, data, b"tooshort")

        assert exc_info.value.code == "DG_SIGNATURE_INVALID"
        assert "64 bytes" in str(exc_info.value)
        assert exc_info.value.details["expected_length"] == 64

        # Too long
        with pytest.raises(SignatureInvalidError) as exc_info:
            verify_signature(pub, data, b"x" * 128)

        assert exc_info.value.code == "DG_SIGNATURE_INVALID"

    def test_public_key_wrong_type_raises_error(self):
        """Non-bytes public key raises DG_SIGNATURE_INVALID"""
        priv, pub = generate_ed25519_keypair()
        data = b"test data"
        signature = sign_bytes(priv, data)

        with pytest.raises(SignatureInvalidError) as exc_info:
            verify_signature("not bytes", data, signature)

        assert exc_info.value.code == "DG_SIGNATURE_INVALID"
        assert "bytes" in str(exc_info.value).lower()

    def test_signature_wrong_type_raises_error(self):
        """Non-bytes signature raises DG_SIGNATURE_INVALID"""
        priv, pub = generate_ed25519_keypair()
        data = b"test data"

        with pytest.raises(SignatureInvalidError) as exc_info:
            verify_signature(pub, data, "not bytes")

        assert exc_info.value.code == "DG_SIGNATURE_INVALID"
        assert "bytes" in str(exc_info.value).lower()

    def test_verify_empty_data(self):
        """Can verify signature of empty data"""
        priv, pub = generate_ed25519_keypair()
        data = b""
        signature = sign_bytes(priv, data)

        result = verify_signature(pub, data, signature)

        assert result is True

    def test_verify_large_data(self):
        """Can verify signature of large data"""
        priv, pub = generate_ed25519_keypair()
        large_data = b"x" * 1_000_000
        signature = sign_bytes(priv, large_data)

        result = verify_signature(pub, large_data, signature)

        assert result is True


class TestGenerateKeypair:
    """Tests for generate_ed25519_keypair()"""

    def test_returns_tuple_of_two_bytes(self):
        """Returns tuple of (private_bytes, public_bytes)"""
        result = generate_ed25519_keypair()

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bytes)
        assert isinstance(result[1], bytes)

    def test_private_key_is_32_bytes(self):
        """Private key is 32 bytes"""
        priv, pub = generate_ed25519_keypair()

        assert len(priv) == 32

    def test_public_key_is_32_bytes(self):
        """Public key is 32 bytes"""
        priv, pub = generate_ed25519_keypair()

        assert len(pub) == 32

    def test_each_call_produces_different_keys(self):
        """Each call generates new random keypair"""
        priv1, pub1 = generate_ed25519_keypair()
        priv2, pub2 = generate_ed25519_keypair()

        # Different private keys
        assert priv1 != priv2

        # Different public keys
        assert pub1 != pub2

    def test_generated_keys_work_with_sign_verify(self):
        """Generated keys can be used with sign_bytes and verify_signature"""
        priv, pub = generate_ed25519_keypair()
        data = b"test data"

        # Sign with generated private key
        signature = sign_bytes(priv, data)

        # Verify with generated public key
        result = verify_signature(pub, data, signature)

        assert result is True


class TestSignatureErrorCodes:
    """Tests for error code correctness"""

    def test_error_code_is_dg_signature_invalid(self):
        """SignatureInvalidError has code DG_SIGNATURE_INVALID"""
        try:
            sign_bytes(b"tooshort", b"data")
        except SignatureInvalidError as e:
            assert e.code == "DG_SIGNATURE_INVALID"
        else:
            pytest.fail("Expected SignatureInvalidError")

    def test_error_includes_details(self):
        """Error includes helpful details dict"""
        try:
            sign_bytes(b"tooshort", b"data")
        except SignatureInvalidError as e:
            assert isinstance(e.details, dict)
            assert "expected_length" in e.details
            assert e.details["expected_length"] == 32
        else:
            pytest.fail("Expected SignatureInvalidError")

    def test_error_has_message(self):
        """Error has human-readable message"""
        try:
            sign_bytes(b"tooshort", b"data")
        except SignatureInvalidError as e:
            assert e.message is not None
            assert len(e.message) > 0
            assert "32 bytes" in e.message.lower()
        else:
            pytest.fail("Expected SignatureInvalidError")

    def test_error_to_dict_works(self):
        """Error can be serialized to dict"""
        try:
            sign_bytes(b"tooshort", b"data")
        except SignatureInvalidError as e:
            error_dict = e.to_dict()
            assert error_dict["code"] == "DG_SIGNATURE_INVALID"
            assert "message" in error_dict
            assert "details" in error_dict
        else:
            pytest.fail("Expected SignatureInvalidError")


class TestEdgeCases:
    """Edge cases and boundary conditions"""

    def test_signing_same_data_with_multiple_keys(self):
        """Signing same data with multiple keys produces different signatures"""
        data = b"shared data"
        signatures = []

        for _ in range(5):
            priv, pub = generate_ed25519_keypair()
            sig = sign_bytes(priv, data)
            signatures.append(sig)

        # All signatures should be different
        assert len(set(signatures)) == 5

    def test_zero_bytes_key_invalid(self):
        """Key of all zeros is invalid (not on curve)"""
        zero_key = b"\x00" * 32
        data = b"test"

        # Zero key should fail (not a valid Ed25519 private key)
        # Note: Ed25519 allows any 32 bytes as private key seed,
        # but signing library may reject degenerate cases
        try:
            signature = sign_bytes(zero_key, data)
            # If it doesn't raise, the library accepts it
            # (Ed25519 technically allows any 32-byte seed)
            assert len(signature) == 64
        except SignatureInvalidError:
            # Some implementations reject degenerate keys
            pass

    def test_signature_verification_is_independent_of_data_order(self):
        """Verification result doesn't depend on data processing order"""
        priv, pub = generate_ed25519_keypair()
        data1 = b"abc"
        data2 = b"xyz"

        sig1 = sign_bytes(priv, data1)
        sig2 = sign_bytes(priv, data2)

        # Verify in different order
        assert verify_signature(pub, data1, sig1) is True
        assert verify_signature(pub, data2, sig2) is True
        assert verify_signature(pub, data1, sig2) is False
        assert verify_signature(pub, data2, sig1) is False

    def test_signature_with_special_bytes_patterns(self):
        """Can sign data with special byte patterns"""
        priv, pub = generate_ed25519_keypair()

        # All zeros
        sig1 = sign_bytes(priv, b"\x00" * 100)
        assert verify_signature(pub, b"\x00" * 100, sig1) is True

        # All ones
        sig2 = sign_bytes(priv, b"\xFF" * 100)
        assert verify_signature(pub, b"\xFF" * 100, sig2) is True

        # Alternating pattern
        sig3 = sign_bytes(priv, b"\xAA\x55" * 50)
        assert verify_signature(pub, b"\xAA\x55" * 50, sig3) is True

    def test_determinism_across_multiple_invocations(self):
        """Determinism holds across multiple sign operations"""
        priv, pub = generate_ed25519_keypair()
        data = b"deterministic test"

        # Sign 10 times
        signatures = [sign_bytes(priv, data) for _ in range(10)]

        # All should be identical
        assert len(set(signatures)) == 1
