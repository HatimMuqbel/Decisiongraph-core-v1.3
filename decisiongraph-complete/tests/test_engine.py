"""
Test suite for DecisionGraph Engine (Phase 4).

Tests for the Engine class and process_rfa() method:
- Happy path: Valid RFA returns ProofPacket with proof_bundle
- Schema validation: Missing fields or wrong types raise SchemaInvalidError
- Field validation: Invalid formats raise InputInvalidError
- Canonicalization: Input normalized before validation

Requirements tested:
- RFA-01: Single validated entry point
- RFA-02: Schema validation (required fields)
- RFA-03: Input canonicalization
"""

import pytest
from uuid import UUID

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from decisiongraph import (
    # Core
    create_chain,
    create_genesis_cell,
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Proof,
    CellType,
    SourceQuality,
    # Engine
    Engine,
    process_rfa,
    # Exceptions
    SchemaInvalidError,
    InputInvalidError,
    # Signing
    generate_ed25519_keypair,
)
from decisiongraph.engine import verify_proof_packet
from test_utils import T0, T1, T2, T3


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def test_keypair():
    """Generate a test Ed25519 keypair."""
    return generate_ed25519_keypair()


@pytest.fixture
def test_chain():
    """Create a test chain with genesis and some fact cells for testing."""
    # Create chain with genesis at T0
    chain = create_chain("test_graph", system_time=T0)

    # Add some facts to corp.hr namespace
    fact1 = DecisionCell(
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
    chain.append(fact1)

    # Add another fact
    fact2 = DecisionCell(
        header=Header(
            version="1.3",
            graph_id=chain.graph_id,
            cell_type=CellType.FACT,
            system_time=T2,
            prev_cell_hash=chain.cells[-1].cell_id
        ),
        fact=Fact(
            namespace="corp.hr",
            subject="user:bob",
            predicate="has_department",
            object="engineering",
            source_quality=SourceQuality.VERIFIED,
            confidence=1.0,
            valid_from=T2,
            valid_to=None
        ),
        logic_anchor=LogicAnchor(
            rule_id="manual:entry",
            rule_logic_hash=""
        ),
        proof=Proof()
    )
    chain.append(fact2)

    return chain


@pytest.fixture
def test_engine(test_chain):
    """Engine without signing key."""
    return Engine(test_chain)


@pytest.fixture
def test_engine_with_key(test_chain, test_keypair):
    """Engine with signing key."""
    priv, pub = test_keypair
    return Engine(test_chain, signing_key=priv, public_key=pub)


@pytest.fixture
def valid_rfa():
    """Valid RFA for testing."""
    return {
        "namespace": "corp.hr",
        "requester_namespace": "corp.hr",
        "requester_id": "admin:alice"
    }


def create_test_chain_with_facts():
    """Create a test chain with genesis and some fact cells for testing."""
    # Create chain with genesis at T0
    chain = create_chain("test_graph", system_time=T0)

    # Add some facts to corp.hr namespace
    fact1 = DecisionCell(
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
    chain.append(fact1)

    # Add another fact
    fact2 = DecisionCell(
        header=Header(
            version="1.3",
            graph_id=chain.graph_id,
            cell_type=CellType.FACT,
            system_time=T2,
            prev_cell_hash=chain.cells[-1].cell_id
        ),
        fact=Fact(
            namespace="corp.hr",
            subject="user:bob",
            predicate="has_department",
            object="engineering",
            source_quality=SourceQuality.VERIFIED,
            confidence=1.0,
            valid_from=T2,
            valid_to=None
        ),
        logic_anchor=LogicAnchor(
            rule_id="manual:entry",
            rule_logic_hash=""
        ),
        proof=Proof()
    )
    chain.append(fact2)

    return chain


# =============================================================================
# TEST: Happy Path
# =============================================================================

class TestEngineHappyPath:
    """Tests for successful RFA processing."""

    def test_process_rfa_valid_query_returns_proof_packet(self):
        """Valid RFA should return ProofPacket with required fields."""
        chain = create_test_chain_with_facts()
        engine = Engine(chain)

        rfa = {
            "namespace": "corp.hr",
            "requester_namespace": "corp.hr",
            "requester_id": "admin:alice"
        }

        packet = engine.process_rfa(rfa)

        # Verify ProofPacket structure
        assert "packet_version" in packet
        assert packet["packet_version"] == "1.4"

        assert "packet_id" in packet
        # Verify packet_id is valid UUID
        UUID(packet["packet_id"])

        assert "generated_at" in packet
        assert isinstance(packet["generated_at"], str)

        assert "graph_id" in packet
        assert packet["graph_id"] == chain.graph_id

        assert "proof_bundle" in packet
        assert isinstance(packet["proof_bundle"], dict)

        assert "signature" in packet
        assert packet["signature"] is None  # Not signed yet (Plan 02)

    def test_process_rfa_includes_scholar_results(self):
        """ProofPacket should include facts and authorization from Scholar."""
        chain = create_test_chain_with_facts()
        engine = Engine(chain)

        rfa = {
            "namespace": "corp.hr",
            "requester_namespace": "corp.hr",
            "requester_id": "admin:alice",
            "subject": "user:alice",
            "predicate": "has_salary"
        }

        packet = engine.process_rfa(rfa)
        proof_bundle = packet["proof_bundle"]

        # Verify proof_bundle contains Scholar query result
        assert "results" in proof_bundle
        assert "fact_count" in proof_bundle["results"]
        assert proof_bundle["results"]["fact_count"] == 1

        assert "fact_cell_ids" in proof_bundle["results"]
        assert len(proof_bundle["results"]["fact_cell_ids"]) == 1

        # Verify authorization basis
        assert "authorization_basis" in proof_bundle
        assert "allowed" in proof_bundle["authorization_basis"]
        assert proof_bundle["authorization_basis"]["allowed"] is True
        assert "reason" in proof_bundle["authorization_basis"]
        assert proof_bundle["authorization_basis"]["reason"] == "same_namespace"

    def test_process_rfa_unsigned_packet_has_null_signature(self):
        """When Engine has no signing key, signature field should be None."""
        chain = create_test_chain_with_facts()
        engine = Engine(chain)  # No signing key

        rfa = {
            "namespace": "corp.hr",
            "requester_namespace": "corp.hr",
            "requester_id": "admin:alice"
        }

        packet = engine.process_rfa(rfa)

        assert packet["signature"] is None

    def test_process_rfa_deterministic_proof_bundle(self):
        """Same RFA should produce identical proof_bundle (excluding packet_id/generated_at)."""
        chain = create_test_chain_with_facts()
        engine = Engine(chain)

        rfa = {
            "namespace": "corp.hr",
            "requester_namespace": "corp.hr",
            "requester_id": "admin:alice",
            "subject": "user:alice"
        }

        packet1 = engine.process_rfa(rfa)
        packet2 = engine.process_rfa(rfa)

        # packet_id and generated_at will differ
        assert packet1["packet_id"] != packet2["packet_id"]

        # But proof_bundle should be identical
        assert packet1["proof_bundle"] == packet2["proof_bundle"]


# =============================================================================
# TEST: Schema Validation
# =============================================================================

class TestEngineSchemaValidation:
    """Tests for RFA schema validation (RFA-02)."""

    def test_process_rfa_missing_namespace_raises_schema_invalid(self):
        """Missing 'namespace' should raise SchemaInvalidError."""
        chain = create_test_chain_with_facts()
        engine = Engine(chain)

        rfa = {
            # Missing 'namespace'
            "requester_namespace": "corp.hr",
            "requester_id": "admin:alice"
        }

        with pytest.raises(SchemaInvalidError) as exc_info:
            engine.process_rfa(rfa)

        error = exc_info.value
        assert error.code == "DG_SCHEMA_INVALID"
        assert "namespace" in error.message.lower()
        assert "missing_fields" in error.details
        assert "namespace" in error.details["missing_fields"]

    def test_process_rfa_missing_requester_namespace_raises_schema_invalid(self):
        """Missing 'requester_namespace' should raise SchemaInvalidError."""
        chain = create_test_chain_with_facts()
        engine = Engine(chain)

        rfa = {
            "namespace": "corp.hr",
            # Missing 'requester_namespace'
            "requester_id": "admin:alice"
        }

        with pytest.raises(SchemaInvalidError) as exc_info:
            engine.process_rfa(rfa)

        error = exc_info.value
        assert error.code == "DG_SCHEMA_INVALID"
        assert "requester_namespace" in error.message.lower()
        assert "missing_fields" in error.details
        assert "requester_namespace" in error.details["missing_fields"]

    def test_process_rfa_missing_requester_id_raises_schema_invalid(self):
        """Missing 'requester_id' should raise SchemaInvalidError."""
        chain = create_test_chain_with_facts()
        engine = Engine(chain)

        rfa = {
            "namespace": "corp.hr",
            "requester_namespace": "corp.hr"
            # Missing 'requester_id'
        }

        with pytest.raises(SchemaInvalidError) as exc_info:
            engine.process_rfa(rfa)

        error = exc_info.value
        assert error.code == "DG_SCHEMA_INVALID"
        assert "requester_id" in error.message.lower()
        assert "missing_fields" in error.details
        assert "requester_id" in error.details["missing_fields"]

    def test_process_rfa_wrong_type_raises_schema_invalid(self):
        """Integer for 'namespace' should raise SchemaInvalidError."""
        chain = create_test_chain_with_facts()
        engine = Engine(chain)

        rfa = {
            "namespace": 12345,  # Wrong type (should be string)
            "requester_namespace": "corp.hr",
            "requester_id": "admin:alice"
        }

        with pytest.raises(SchemaInvalidError) as exc_info:
            engine.process_rfa(rfa)

        error = exc_info.value
        assert error.code == "DG_SCHEMA_INVALID"
        assert "namespace" in error.message.lower()
        assert "string" in error.message.lower()
        assert "field" in error.details
        assert error.details["field"] == "namespace"


# =============================================================================
# TEST: Field Validation
# =============================================================================

class TestEngineFieldValidation:
    """Tests for RFA field format validation (VAL-01/02/03)."""

    def test_process_rfa_invalid_subject_raises_input_invalid(self):
        """Subject 'USER:alice' (uppercase) should raise InputInvalidError."""
        chain = create_test_chain_with_facts()
        engine = Engine(chain)

        rfa = {
            "namespace": "corp.hr",
            "requester_namespace": "corp.hr",
            "requester_id": "admin:alice",
            "subject": "USER:alice"  # Invalid: uppercase
        }

        with pytest.raises(InputInvalidError) as exc_info:
            engine.process_rfa(rfa)

        error = exc_info.value
        assert error.code == "DG_INPUT_INVALID"
        assert "subject" in error.message.lower()
        assert "field" in error.details
        assert error.details["field"] == "subject"

    def test_process_rfa_invalid_predicate_raises_input_invalid(self):
        """Predicate 'has salary' (space) should raise InputInvalidError."""
        chain = create_test_chain_with_facts()
        engine = Engine(chain)

        rfa = {
            "namespace": "corp.hr",
            "requester_namespace": "corp.hr",
            "requester_id": "admin:alice",
            "predicate": "has salary"  # Invalid: space
        }

        with pytest.raises(InputInvalidError) as exc_info:
            engine.process_rfa(rfa)

        error = exc_info.value
        assert error.code == "DG_INPUT_INVALID"
        assert "predicate" in error.message.lower()
        assert "field" in error.details
        assert error.details["field"] == "predicate"

    def test_process_rfa_invalid_object_raises_input_invalid(self):
        """Object with control character should raise InputInvalidError."""
        chain = create_test_chain_with_facts()
        engine = Engine(chain)

        rfa = {
            "namespace": "corp.hr",
            "requester_namespace": "corp.hr",
            "requester_id": "admin:alice",
            "object": "value\x00here"  # Invalid: null byte control char
        }

        with pytest.raises(InputInvalidError) as exc_info:
            engine.process_rfa(rfa)

        error = exc_info.value
        assert error.code == "DG_INPUT_INVALID"
        assert "object" in error.message.lower()
        assert "control" in error.message.lower()
        assert "field" in error.details
        assert error.details["field"] == "object"

    def test_process_rfa_invalid_namespace_raises_input_invalid(self):
        """Namespace 'CORP.HR' (uppercase) should raise InputInvalidError."""
        chain = create_test_chain_with_facts()
        engine = Engine(chain)

        rfa = {
            "namespace": "CORP.HR",  # Invalid: uppercase
            "requester_namespace": "corp.hr",
            "requester_id": "admin:alice"
        }

        with pytest.raises(InputInvalidError) as exc_info:
            engine.process_rfa(rfa)

        error = exc_info.value
        assert error.code == "DG_INPUT_INVALID"
        assert "namespace" in error.message.lower()
        assert "field" in error.details
        assert error.details["field"] == "namespace"


# =============================================================================
# TEST: Canonicalization
# =============================================================================

class TestEngineCanonicalization:
    """Tests for RFA canonicalization (RFA-03)."""

    def test_canonicalize_rfa_sorts_keys(self):
        """Output dict should have alphabetically sorted keys."""
        chain = create_test_chain_with_facts()
        engine = Engine(chain)

        rfa = {
            "requester_id": "admin:alice",
            "namespace": "corp.hr",
            "requester_namespace": "corp.hr"
        }

        canonical = engine._canonicalize_rfa(rfa)

        # Get keys as list
        keys = list(canonical.keys())

        # Verify they're sorted
        assert keys == sorted(keys)

    def test_canonicalize_rfa_strips_whitespace(self):
        """Leading/trailing whitespace should be removed from string values."""
        chain = create_test_chain_with_facts()
        engine = Engine(chain)

        rfa = {
            "namespace": "  corp.hr  ",
            "requester_namespace": "\tcorp.hr\n",
            "requester_id": " admin:alice "
        }

        canonical = engine._canonicalize_rfa(rfa)

        assert canonical["namespace"] == "corp.hr"
        assert canonical["requester_namespace"] == "corp.hr"
        assert canonical["requester_id"] == "admin:alice"

    def test_canonicalize_rfa_removes_none_values(self):
        """None values should be removed from output."""
        chain = create_test_chain_with_facts()
        engine = Engine(chain)

        rfa = {
            "namespace": "corp.hr",
            "requester_namespace": "corp.hr",
            "requester_id": "admin:alice",
            "subject": None,
            "predicate": None
        }

        canonical = engine._canonicalize_rfa(rfa)

        assert "subject" not in canonical
        assert "predicate" not in canonical
        assert "namespace" in canonical
        assert "requester_namespace" in canonical
        assert "requester_id" in canonical


# =============================================================================
# TEST: Convenience Function
# =============================================================================

class TestProcessRfaConvenience:
    """Tests for the convenience process_rfa() function."""

    def test_process_rfa_function_works(self):
        """process_rfa() convenience function should work without creating Engine."""
        chain = create_test_chain_with_facts()

        rfa = {
            "namespace": "corp.hr",
            "requester_namespace": "corp.hr",
            "requester_id": "admin:alice"
        }

        packet = process_rfa(chain, rfa)

        # Should return valid ProofPacket
        assert "packet_version" in packet
        assert packet["packet_version"] == "1.4"
        assert "proof_bundle" in packet


# =============================================================================
# TEST: Signature Support
# =============================================================================

class TestEngineSignatures:
    """Tests for SIG-04: ProofPacket signing and verification."""

    def test_process_rfa_signed_packet_when_key_provided(self, test_engine_with_key, valid_rfa):
        """ProofPacket.signature is populated when Engine has signing key."""
        packet = test_engine_with_key.process_rfa(valid_rfa)

        assert packet["signature"] is not None
        assert packet["signature"]["algorithm"] == "Ed25519"
        assert "public_key" in packet["signature"]
        assert "signature" in packet["signature"]
        assert "signed_at" in packet["signature"]

    def test_verify_proof_packet_valid_signature(self, test_engine_with_key, valid_rfa, test_keypair):
        """verify_proof_packet() returns True for valid signature."""
        _, pub = test_keypair
        packet = test_engine_with_key.process_rfa(valid_rfa)

        assert verify_proof_packet(packet, pub) is True

    def test_verify_proof_packet_tampered_data(self, test_engine_with_key, valid_rfa, test_keypair):
        """verify_proof_packet() returns False when proof_bundle tampered."""
        _, pub = test_keypair
        packet = test_engine_with_key.process_rfa(valid_rfa)

        # Tamper with proof_bundle
        packet["proof_bundle"]["tampered_field"] = "evil_value"

        assert verify_proof_packet(packet, pub) is False

    def test_verify_proof_packet_wrong_key(self, test_engine_with_key, valid_rfa):
        """verify_proof_packet() returns False with wrong public key."""
        packet = test_engine_with_key.process_rfa(valid_rfa)

        # Generate different keypair
        _, wrong_pub = generate_ed25519_keypair()

        assert verify_proof_packet(packet, wrong_pub) is False

    def test_verify_proof_packet_unsigned_packet(self, test_engine, valid_rfa, test_keypair):
        """verify_proof_packet() returns False for unsigned packet."""
        _, pub = test_keypair
        packet = test_engine.process_rfa(valid_rfa)

        # Packet is unsigned (Engine has no key)
        assert packet["signature"] is None
        assert verify_proof_packet(packet, pub) is False

    def test_verify_proof_packet_signature_base64_encoded(self, test_engine_with_key, valid_rfa):
        """Signature fields are base64 encoded strings (JSON-safe)."""
        packet = test_engine_with_key.process_rfa(valid_rfa)

        sig = packet["signature"]
        # Should be strings (base64), not bytes
        assert isinstance(sig["public_key"], str)
        assert isinstance(sig["signature"], str)
        # Should be valid base64
        import base64
        base64.b64decode(sig["public_key"])  # Should not raise
        base64.b64decode(sig["signature"])   # Should not raise
