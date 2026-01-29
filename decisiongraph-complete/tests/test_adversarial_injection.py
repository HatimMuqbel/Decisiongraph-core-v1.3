"""
Adversarial Test Suite: Injection Attacks (SEC-01)

Tests that predicate and subject injection payloads return DG_INPUT_INVALID
before reaching the Scholar query engine.

Purpose:
- Verify that malicious injection attempts are caught at the validation layer
- Ensure attackers cannot bypass input filters to inject malicious data
- Confirm deterministic error codes (DG_INPUT_INVALID) for all attack vectors
"""

import pytest
from decisiongraph import (
    InputInvalidError,
    create_chain,
    process_rfa
)
from decisiongraph.validators import (
    validate_predicate_field,
    validate_subject_field
)


# =============================================================================
# TEST: Predicate Injection Attacks
# =============================================================================

class TestPredicateInjection:
    """
    Tests for predicate injection attack vectors.

    Attack goal: Inject malicious syntax into predicate field to:
    - Bypass validation logic
    - Execute SQL-like commands if backend uses SQL
    - Inject control characters to break parsing
    - Use case variations to bypass filters
    """

    @pytest.mark.parametrize("malicious_predicate,attack_type", [
        # SQL-style injection attempts
        ("can;drop table", "SQL semicolon terminator"),
        ("can' OR '1'='1", "SQL quote injection"),
        ("can--comment", "SQL comment injection"),
        ("can/**/admin", "SQL comment bypass"),
        ("can' OR 1=1--", "SQL authentication bypass"),
        ("can'; DROP TABLE users; --", "SQL command injection"),

        # Null byte injection (attempt to truncate)
        ("can\x00drop", "null byte truncation"),
        ("valid\x00; DROP TABLE", "null byte with command"),

        # Newline injection (multiline bypass)
        ("can\nDROP TABLE", "newline command injection"),
        ("can\rADMIN", "carriage return injection"),

        # Space injection (bypass snake_case requirement)
        ("can access", "space instead of underscore"),
        ("has permission", "space in predicate"),

        # Case bypass attempts
        ("CAN_ACCESS", "uppercase bypass"),
        ("Can_Access", "mixed case bypass"),
        ("cAn_AcCeSs", "random case bypass"),

        # Hyphen (slug format instead of snake_case)
        ("can-access", "hyphen instead of underscore"),
        ("has-permission", "slug format"),

        # Special characters
        ("can@admin", "at-sign injection"),
        ("can#anchor", "hash injection"),
        ("can$var", "dollar sign injection"),
        ("can/path", "slash injection"),
        ("can\\escape", "backslash injection"),
        ("can:type", "colon injection"),
        ("can.access", "dot injection"),
        ("can,access", "comma injection"),
        ("can|pipe", "pipe injection"),
        ("can&and", "ampersand injection"),
        ("can=equals", "equals injection"),

        # Control characters
        ("can\x01admin", "SOH control char"),
        ("can\x1Fadmin", "unit separator"),
        ("can\x0Badmin", "vertical tab"),
        ("can\x08admin", "backspace"),
    ])
    def test_predicate_injection_rejected_at_validator(
        self,
        malicious_predicate: str,
        attack_type: str
    ) -> None:
        """
        Malicious predicate payloads should be rejected at validation layer.

        This test verifies that injection attempts fail with:
        1. InputInvalidError exception
        2. DG_INPUT_INVALID error code
        3. Field name in error details

        Attack vectors include SQL injection, null bytes, control chars,
        case variations, and special characters.
        """
        with pytest.raises(InputInvalidError) as exc_info:
            validate_predicate_field(malicious_predicate)

        # Verify error code is deterministic
        assert exc_info.value.code == "DG_INPUT_INVALID", \
            f"Expected DG_INPUT_INVALID, got {exc_info.value.code} for {attack_type}"

        # Verify field name in details
        assert exc_info.value.details.get("field") == "predicate", \
            f"Expected field='predicate' in details for {attack_type}"

    def test_predicate_injection_error_is_actionable(self) -> None:
        """
        Predicate injection errors should provide actionable guidance.

        Error message should explain:
        - What format is expected (snake_case)
        - Example of valid format
        - Pattern constraint
        """
        with pytest.raises(InputInvalidError) as exc_info:
            validate_predicate_field("can;drop table")

        error = exc_info.value

        # Message should mention format requirements
        assert "snake_case" in error.message.lower() or "format" in error.message.lower(), \
            "Error message should mention snake_case format"

        # Details should include pattern or constraint
        assert "pattern" in error.details or "constraint" in error.details, \
            "Error details should include pattern or constraint"


# =============================================================================
# TEST: Subject Injection Attacks
# =============================================================================

class TestSubjectInjection:
    """
    Tests for subject injection attack vectors.

    Attack goal: Inject malicious syntax into subject field to:
    - Access unauthorized entities
    - Bypass type:identifier format validation
    - Inject path traversal sequences
    """

    @pytest.mark.parametrize("malicious_subject,attack_type", [
        # SQL-style injection
        ("user:alice;DROP TABLE", "SQL semicolon injection"),
        ("user:alice' OR '1'='1", "SQL quote injection"),
        # Note: user:alice-- is VALID (hyphens allowed in identifier per VAL-01)

        # Null byte injection
        ("user:alice\x00admin", "null byte privilege escalation"),
        ("user:\x00root", "null byte in identifier"),

        # Case bypass (type and identifier must be lowercase)
        ("USER:alice", "uppercase type"),
        ("user:ALICE", "uppercase identifier"),
        ("User:Alice", "mixed case"),

        # Missing colon (invalid format)
        ("useralice", "missing colon separator"),
        ("user:", "empty identifier"),
        (":alice", "empty type"),

        # Space injection
        ("user:alice bob", "space in identifier"),
        ("user type:alice", "space in type"),

        # Special characters not in allowed set
        ("user:alice;admin", "semicolon in identifier"),
        ("user:alice@domain", "at-sign in identifier"),
        ("user:alice#anchor", "hash in identifier"),
        ("user:alice$var", "dollar sign in identifier"),

        # Control characters
        ("user:alice\x00", "null byte at end"),
        ("user:alice\x1F", "unit separator"),
        ("user:alice\x0B", "vertical tab"),
        ("user:alice\x08", "backspace"),

        # Type injection (invalid type format)
        ("123:alice", "type starts with digit"),
        ("user-type:alice", "hyphen in type"),
        ("user.type:alice", "dot in type (invalid for type)"),

        # Identifier length attack (>128 chars after colon)
        ("user:" + "a" * 129, "identifier exceeds 128 chars"),
        ("user:" + "x" * 200, "extremely long identifier"),
    ])
    def test_subject_injection_rejected_at_validator(
        self,
        malicious_subject: str,
        attack_type: str
    ) -> None:
        """
        Malicious subject payloads should be rejected at validation layer.

        Verifies that injection attempts fail with:
        1. InputInvalidError exception
        2. DG_INPUT_INVALID error code
        3. Field name in error details
        """
        with pytest.raises(InputInvalidError) as exc_info:
            validate_subject_field(malicious_subject)

        # Verify error code
        assert exc_info.value.code == "DG_INPUT_INVALID", \
            f"Expected DG_INPUT_INVALID, got {exc_info.value.code} for {attack_type}"

        # Verify field name
        assert exc_info.value.details.get("field") == "subject", \
            f"Expected field='subject' in details for {attack_type}"

    def test_subject_injection_error_is_actionable(self) -> None:
        """
        Subject injection errors should provide actionable guidance.

        Error message should explain type:identifier format.
        """
        with pytest.raises(InputInvalidError) as exc_info:
            validate_subject_field("USER:ALICE")

        error = exc_info.value

        # Message should mention format
        assert "type:identifier" in error.message.lower() or "format" in error.message.lower(), \
            "Error message should explain type:identifier format"

        # Should include pattern or example
        assert "pattern" in error.details or "constraint" in error.details, \
            "Error details should include pattern or constraint"


# =============================================================================
# TEST: End-to-End Injection via process_rfa()
# =============================================================================

class TestInjectionAtEngineLevel:
    """
    Tests that injection attacks are blocked when submitted through
    the Engine's process_rfa() entry point.

    These tests verify that validation happens BEFORE Scholar query,
    preventing malicious input from reaching the core engine.
    """

    def test_predicate_injection_blocked_at_rfa_entry(self) -> None:
        """
        Predicate injection through process_rfa() should fail at validation layer.

        Attack vector: Inject SQL-style command in predicate field.
        Expected: InputInvalidError with DG_INPUT_INVALID before Scholar query.
        """
        chain = create_chain("test_graph")

        malicious_rfa = {
            "namespace": "corp",
            "requester_namespace": "corp",
            "requester_id": "attacker:eve",
            "predicate": "can;drop table"  # Malicious predicate
        }

        with pytest.raises(InputInvalidError) as exc_info:
            process_rfa(chain, malicious_rfa)

        # Verify error code
        assert exc_info.value.code == "DG_INPUT_INVALID", \
            "Predicate injection should fail with DG_INPUT_INVALID"

        # Verify it's a validation error (not a query error)
        # The error should reference the predicate field
        assert "predicate" in exc_info.value.message.lower() or \
               exc_info.value.details.get("field") == "predicate", \
            "Error should identify predicate as the problem field"

    def test_subject_injection_blocked_at_rfa_entry(self) -> None:
        """
        Subject injection through process_rfa() should fail at validation layer.

        Attack vector: Inject uppercase/special chars in subject field.
        Expected: InputInvalidError with DG_INPUT_INVALID before Scholar query.
        """
        chain = create_chain("test_graph")

        malicious_rfa = {
            "namespace": "corp",
            "requester_namespace": "corp",
            "requester_id": "attacker:eve",
            "subject": "USER:ALICE"  # Uppercase not allowed
        }

        with pytest.raises(InputInvalidError) as exc_info:
            process_rfa(chain, malicious_rfa)

        # Verify error code
        assert exc_info.value.code == "DG_INPUT_INVALID", \
            "Subject injection should fail with DG_INPUT_INVALID"

        # Verify it's a validation error for subject field
        assert "subject" in exc_info.value.message.lower() or \
               exc_info.value.details.get("field") == "subject", \
            "Error should identify subject as the problem field"

    def test_multiple_injection_vectors_in_single_rfa(self) -> None:
        """
        RFA with multiple malicious fields should fail on first validation error.

        Attack vector: Multiple injection attempts in same request.
        Expected: First validation error encountered (field validation order).
        """
        chain = create_chain("test_graph")

        malicious_rfa = {
            "namespace": "corp",
            "requester_namespace": "corp",
            "requester_id": "attacker:eve",
            "subject": "USER:ALICE",  # Invalid (uppercase)
            "predicate": "can;drop table",  # Invalid (semicolon)
            "object": "\x00malicious"  # Invalid (null byte)
        }

        # Should fail with InputInvalidError
        with pytest.raises(InputInvalidError) as exc_info:
            process_rfa(chain, malicious_rfa)

        # Any field validation error is acceptable
        # (order depends on validation implementation)
        assert exc_info.value.code == "DG_INPUT_INVALID", \
            "Multiple injection vectors should fail with DG_INPUT_INVALID"

    def test_space_in_predicate_specifically_rejected(self) -> None:
        """
        Predicate with space (from success criteria) should be rejected.

        This is a specific test case from the plan's success criteria:
        "Predicate 'can access' (space) fails with DG_INPUT_INVALID"
        """
        chain = create_chain("test_graph")

        rfa_with_space = {
            "namespace": "corp",
            "requester_namespace": "corp",
            "requester_id": "user:alice",
            "predicate": "can access"  # Space not allowed in snake_case
        }

        with pytest.raises(InputInvalidError) as exc_info:
            process_rfa(chain, rfa_with_space)

        # Verify error code
        assert exc_info.value.code == "DG_INPUT_INVALID", \
            "Predicate 'can access' should fail with DG_INPUT_INVALID"

        # Verify predicate field is identified
        assert exc_info.value.details.get("field") == "predicate", \
            "Error should identify predicate field"

    def test_valid_rfa_still_works(self) -> None:
        """
        Valid RFA should pass validation (sanity check).

        Ensures that strict validation doesn't reject legitimate requests.
        """
        chain = create_chain("test_graph")

        valid_rfa = {
            "namespace": "corp",
            "requester_namespace": "corp",
            "requester_id": "user:alice",
            "subject": "user:bob",
            "predicate": "can_access"
        }

        # Should not raise - returns ProofPacket
        result = process_rfa(chain, valid_rfa)

        # Verify it's a valid ProofPacket structure
        assert "packet_version" in result, \
            "Valid RFA should return ProofPacket"
        assert "proof_bundle" in result, \
            "ProofPacket should contain proof_bundle"
