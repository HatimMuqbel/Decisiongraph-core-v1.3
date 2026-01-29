"""
Adversarial Test Suite: Signature Tampering (SEC-04)

Tests that signature tampering is detected. Modified signatures or data
must fail verification (return False, not exception for invalid signatures).

Requirements tested:
- SEC-04: ProofPacket with 1 byte modified fails verification
- Signature tampering detected by verify_signature() (returns False)
- ProofPacket tampering detected by verify_proof_packet() (returns False)
- Single bit flip detected
- Various byte modifications at different positions detected

Attack vectors:
1. Flip single bit in signature
2. Modify byte at various positions
3. Modify data while keeping signature
4. Tamper with ProofPacket signature
5. Modify proof_bundle content
6. Truncate/append bytes to signature
"""

import pytest
import base64

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from decisiongraph import (
    create_chain,
    process_rfa,
    sign_bytes,
    verify_signature,
    generate_ed25519_keypair,
    SignatureInvalidError,
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Proof,
    CellType,
    SourceQuality,
    get_current_timestamp
)
from decisiongraph.engine import verify_proof_packet
from test_utils import T0, T1, T2


class TestSignatureTampering:
    """SEC-04: Signature tampering detection"""

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
        data = b"test data for verification"
        signature = sign_bytes(priv, data)

        # Verify original is valid
        assert verify_signature(pub, data, signature) is True

        # Modify specific byte
        sig_list = list(signature)
        sig_list[byte_index] ^= 0xFF  # Flip all bits in byte
        tampered_sig = bytes(sig_list)

        # Verification fails
        assert verify_signature(pub, data, tampered_sig) is False

    def test_data_modification_detected(self):
        """Modifying data after signing breaks verification"""
        priv, pub = generate_ed25519_keypair()
        original_data = b"original data"
        modified_data = b"modified data"

        # Sign original data
        signature = sign_bytes(priv, original_data)

        # Verify with original data - should pass
        assert verify_signature(pub, original_data, signature) is True

        # Verify with modified data - should fail
        assert verify_signature(pub, modified_data, signature) is False

    def test_multiple_bit_flips_detected(self):
        """Multiple bit flips in signature detected"""
        priv, pub = generate_ed25519_keypair()
        data = b"test"
        signature = sign_bytes(priv, data)

        # Flip multiple bits at different positions
        tampered_sig = bytearray(signature)
        tampered_sig[0] ^= 0x01  # Flip bit in first byte
        tampered_sig[31] ^= 0x02  # Flip bit in middle byte
        tampered_sig[63] ^= 0x04  # Flip bit in last byte

        # Verification fails
        assert verify_signature(pub, data, bytes(tampered_sig)) is False

    def test_signature_from_different_key_rejected(self):
        """Signature from different key pair rejected"""
        priv1, pub1 = generate_ed25519_keypair()
        priv2, pub2 = generate_ed25519_keypair()
        data = b"data"

        # Sign with key1
        sig1 = sign_bytes(priv1, data)

        # Verify with key1 - should pass
        assert verify_signature(pub1, data, sig1) is True

        # Verify with key2 - should fail (different key)
        assert verify_signature(pub2, data, sig1) is False

    def test_truncated_signature_raises_error(self):
        """Truncated signature raises SignatureInvalidError (format error)"""
        priv, pub = generate_ed25519_keypair()
        data = b"data"
        signature = sign_bytes(priv, data)

        # Truncate signature (not 64 bytes)
        truncated_sig = signature[:32]

        # Format error raises exception (not normal control flow)
        with pytest.raises(SignatureInvalidError) as exc_info:
            verify_signature(pub, data, truncated_sig)

        assert exc_info.value.code == "DG_SIGNATURE_INVALID"
        assert "64 bytes" in str(exc_info.value)

    def test_extended_signature_raises_error(self):
        """Extended signature raises SignatureInvalidError (format error)"""
        priv, pub = generate_ed25519_keypair()
        data = b"data"
        signature = sign_bytes(priv, data)

        # Extend signature (more than 64 bytes)
        extended_sig = signature + b"\x00"

        # Format error raises exception
        with pytest.raises(SignatureInvalidError) as exc_info:
            verify_signature(pub, data, extended_sig)

        assert exc_info.value.code == "DG_SIGNATURE_INVALID"
        assert "64 bytes" in str(exc_info.value)

    def test_deterministic_signing_same_signature(self):
        """Ed25519 is deterministic: same key + data = same signature"""
        priv, pub = generate_ed25519_keypair()
        data = b"deterministic test"

        sig1 = sign_bytes(priv, data)
        sig2 = sign_bytes(priv, data)

        # Same signature every time
        assert sig1 == sig2

        # Both verify correctly
        assert verify_signature(pub, data, sig1) is True
        assert verify_signature(pub, data, sig2) is True


class TestProofPacketTampering:
    """SEC-04: ProofPacket signature tampering detection"""

    def test_proof_packet_signature_byte_flip(self):
        """Modifying 1 byte in ProofPacket signature fails verification"""
        # Create chain and keypair
        chain = create_chain("test_graph", system_time=T0)
        priv, pub = generate_ed25519_keypair()

        # Add a fact to the chain
        fact = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.FACT,
                system_time=T1,
                prev_cell_hash=chain.cells[-1].cell_id
            ),
            fact=Fact(
                namespace="corp.hr",
                subject="user:alice",
                predicate="has_salary",
                object="75000",
                source_quality=SourceQuality.VERIFIED,
                confidence=1.0,
                valid_from=T1,
                valid_to=None
            ),
            logic_anchor=LogicAnchor(
                rule_id="manual:entry",
                rule_logic_hash=""
            ),
            proof=Proof()
        )
        chain.append(fact)

        # Create signed ProofPacket
        rfa = {
            "namespace": "corp.hr",
            "requester_namespace": "corp.audit",
            "requester_id": "auditor:alice"
        }
        packet = process_rfa(chain, rfa, signing_key=priv, public_key=pub)

        # Verify original packet
        assert verify_proof_packet(packet, pub) is True

        # Tamper: decode signature, flip 1 byte, re-encode
        sig_b64 = packet["signature"]["signature"]
        sig_bytes = base64.b64decode(sig_b64)

        # Flip last byte
        tampered_bytes = sig_bytes[:-1] + bytes([sig_bytes[-1] ^ 0xFF])
        packet["signature"]["signature"] = base64.b64encode(tampered_bytes).decode()

        # Verification fails (returns False, not exception)
        assert verify_proof_packet(packet, pub) is False

    def test_proof_packet_proof_bundle_modification(self):
        """Modifying proof_bundle invalidates signature"""
        chain = create_chain("test_graph", system_time=T0)
        priv, pub = generate_ed25519_keypair()

        # Add fact
        fact = DecisionCell(
            header=Header(
                version="1.3",
                graph_id=chain.graph_id,
                cell_type=CellType.FACT,
                system_time=T1,
                prev_cell_hash=chain.cells[-1].cell_id
            ),
            fact=Fact(
                namespace="corp.hr",
                subject="user:bob",
                predicate="has_role",
                object="developer",
                source_quality=SourceQuality.VERIFIED,
                confidence=1.0,
                valid_from=T1,
                valid_to=None
            ),
            logic_anchor=LogicAnchor(
                rule_id="manual:entry",
                rule_logic_hash=""
            ),
            proof=Proof()
        )
        chain.append(fact)

        # Create signed packet
        rfa = {
            "namespace": "corp.hr",
            "requester_namespace": "corp.audit",
            "requester_id": "auditor:bob"
        }
        packet = process_rfa(chain, rfa, signing_key=priv, public_key=pub)

        # Verify original
        assert verify_proof_packet(packet, pub) is True

        # Tamper: modify proof_bundle (add extra field or change existing value)
        # Modify the query field which should always be present
        packet["proof_bundle"]["query"]["requester_id"] = "attacker:eve"

        # Verification fails (signature no longer matches)
        assert verify_proof_packet(packet, pub) is False

    @pytest.mark.parametrize("tampering_method", [
        "flip_first_byte",
        "flip_last_byte",
        "flip_middle_byte",
        "modify_multiple_bytes",
    ])
    def test_various_tampering_methods(self, tampering_method: str):
        """Different tampering methods all fail verification"""
        chain = create_chain("test_graph", system_time=T0)
        priv, pub = generate_ed25519_keypair()

        # Create signed packet
        rfa = {
            "namespace": "corp",
            "requester_namespace": "corp",
            "requester_id": "user:test"
        }
        packet = process_rfa(chain, rfa, signing_key=priv, public_key=pub)

        # Verify original
        assert verify_proof_packet(packet, pub) is True

        # Apply tampering
        sig_b64 = packet["signature"]["signature"]
        sig_bytes = base64.b64decode(sig_b64)
        sig_array = bytearray(sig_bytes)

        if tampering_method == "flip_first_byte":
            sig_array[0] ^= 0x01
        elif tampering_method == "flip_last_byte":
            sig_array[-1] ^= 0x01
        elif tampering_method == "flip_middle_byte":
            sig_array[32] ^= 0xFF
        elif tampering_method == "modify_multiple_bytes":
            sig_array[0] ^= 0x01
            sig_array[31] ^= 0x02
            sig_array[63] ^= 0x04

        # Re-encode tampered signature
        packet["signature"]["signature"] = base64.b64encode(bytes(sig_array)).decode()

        # All tampering methods fail verification
        assert verify_proof_packet(packet, pub) is False

    def test_unsigned_packet_fails_verification(self):
        """Packet without signature fails verification"""
        chain = create_chain("test_graph", system_time=T0)
        priv, pub = generate_ed25519_keypair()

        # Create unsigned packet (no signing_key)
        rfa = {
            "namespace": "corp",
            "requester_namespace": "corp",
            "requester_id": "user:test"
        }
        packet = process_rfa(chain, rfa)  # No signing_key

        # Verify signature is None
        assert packet["signature"] is None

        # Verification returns False for unsigned packets
        assert verify_proof_packet(packet, pub) is False

    def test_wrong_public_key_fails_verification(self):
        """Verifying with different public key fails"""
        chain = create_chain("test_graph", system_time=T0)
        priv1, pub1 = generate_ed25519_keypair()
        priv2, pub2 = generate_ed25519_keypair()

        # Create packet signed with key1
        rfa = {
            "namespace": "corp",
            "requester_namespace": "corp",
            "requester_id": "user:test"
        }
        packet = process_rfa(chain, rfa, signing_key=priv1, public_key=pub1)

        # Verify with key1 - should pass
        assert verify_proof_packet(packet, pub1) is True

        # Verify with key2 - should fail (different key)
        assert verify_proof_packet(packet, pub2) is False

    def test_signature_field_missing_fails_verification(self):
        """Packet with missing signature field fails verification"""
        chain = create_chain("test_graph", system_time=T0)
        priv, pub = generate_ed25519_keypair()

        # Create signed packet
        rfa = {
            "namespace": "corp",
            "requester_namespace": "corp",
            "requester_id": "user:test"
        }
        packet = process_rfa(chain, rfa, signing_key=priv, public_key=pub)

        # Verify original
        assert verify_proof_packet(packet, pub) is True

        # Remove signature field
        del packet["signature"]["signature"]

        # Verification handles missing field gracefully (returns False)
        assert verify_proof_packet(packet, pub) is False

    def test_malformed_base64_signature_fails_verification(self):
        """Malformed base64 in signature fails verification"""
        chain = create_chain("test_graph", system_time=T0)
        priv, pub = generate_ed25519_keypair()

        # Create signed packet
        rfa = {
            "namespace": "corp",
            "requester_namespace": "corp",
            "requester_id": "user:test"
        }
        packet = process_rfa(chain, rfa, signing_key=priv, public_key=pub)

        # Replace signature with invalid base64
        packet["signature"]["signature"] = "not-valid-base64!!!"

        # Verification handles decode error gracefully (returns False)
        assert verify_proof_packet(packet, pub) is False

    def test_packet_metadata_modification_detected(self):
        """Modifying packet metadata doesn't affect signature verification"""
        chain = create_chain("test_graph", system_time=T0)
        priv, pub = generate_ed25519_keypair()

        # Create signed packet
        rfa = {
            "namespace": "corp",
            "requester_namespace": "corp",
            "requester_id": "user:test"
        }
        packet = process_rfa(chain, rfa, signing_key=priv, public_key=pub)

        # Verify original
        assert verify_proof_packet(packet, pub) is True

        # Modify metadata (not signed - signature is over proof_bundle only)
        packet["packet_id"] = "tampered_id"
        packet["generated_at"] = "2026-01-01T00:00:00Z"

        # Verification still passes (signature is over proof_bundle, not metadata)
        assert verify_proof_packet(packet, pub) is True
