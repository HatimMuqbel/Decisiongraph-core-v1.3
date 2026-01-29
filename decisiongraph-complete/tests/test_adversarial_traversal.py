"""
Adversarial Test Suite: Namespace Traversal (SEC-02)

Tests that namespace traversal patterns return DG_INPUT_INVALID
at the RFA entry point.

Purpose:
- Verify that path traversal attacks are caught at validation layer
- Ensure attackers cannot access unauthorized namespaces via traversal
- Confirm deterministic error codes (DG_INPUT_INVALID) for all attack vectors
"""

import pytest
from decisiongraph import (
    InputInvalidError,
    create_chain,
    process_rfa
)
from decisiongraph.cell import validate_namespace


# =============================================================================
# TEST: Namespace Traversal Pattern Validation
# =============================================================================

class TestNamespaceTraversalPatterns:
    """
    Tests that validate_namespace() rejects traversal patterns.

    Attack goal: Traverse namespace hierarchy to access unauthorized data:
    - Use double-dot (..) to access parent namespaces
    - Use slashes instead of dots to confuse validation
    - Use absolute paths to bypass hierarchy
    - Use Windows-style backslashes
    - Use trailing/leading dots to hide traversal
    """

    @pytest.mark.parametrize("malicious_namespace,attack_type", [
        # Double-dot traversal (from success criteria)
        ("corp..hr", "double-dot traversal"),
        ("corp..admin", "double-dot to sibling namespace"),
        ("sales..finance", "double-dot lateral movement"),
        ("a..b..c", "multiple double-dot segments"),

        # Slash instead of dot (from success criteria)
        ("corp/hr", "Unix path separator"),
        ("corp/hr/payroll", "Unix nested path"),
        ("sales/reports", "slash traversal"),

        # Unix-style path traversal
        ("corp/../admin", "Unix parent directory traversal"),
        ("../etc/passwd", "Unix absolute traversal"),
        ("../../root", "Unix multi-level traversal"),
        ("corp/./hr", "Unix current directory"),

        # Windows-style traversal
        ("corp\\hr", "Windows path separator"),
        ("corp\\..\\admin", "Windows parent traversal"),
        ("C:\\corp\\hr", "Windows absolute path"),

        # Absolute paths
        ("/etc/passwd", "Unix absolute path"),
        ("/corp/hr", "absolute path with slash"),
        ("/admin", "absolute single segment"),

        # Trailing/leading dots
        ("corp.hr.", "trailing dot"),
        (".hidden", "leading dot"),
        ("..hidden", "leading double-dot"),
        (".corp.hr", "leading dot with hierarchy"),

        # Multiple dots
        ("corp...hr", "triple-dot"),
        ("corp....hr", "quad-dot"),
        ("a...b...c", "multiple triple-dot segments"),

        # Null byte injection (attempt to truncate)
        ("corp.hr\x00admin", "null byte traversal"),
        ("corp\x00/../admin", "null byte with traversal"),

        # Semicolon (command separator)
        ("corp.hr;admin", "semicolon separator"),
        ("corp;DROP TABLE", "semicolon command injection"),

        # Empty segments
        ("corp..hr", "empty segment via double-dot"),  # Duplicate for emphasis
        (".corp", "leading empty segment"),
        ("corp.", "trailing empty segment"),

        # Mixed attack vectors
        ("corp/hr;admin", "slash with semicolon"),
        ("corp\\hr\x00", "backslash with null byte"),
        ("../corp.hr;DROP", "traversal with injection"),
    ])
    def test_traversal_pattern_rejected_by_validate_namespace(
        self,
        malicious_namespace: str,
        attack_type: str
    ) -> None:
        """
        Namespace traversal patterns should be rejected by validate_namespace().

        Returns False (not raise exception) for invalid namespaces.
        The validate_namespace() function returns bool, not raises.
        """
        result = validate_namespace(malicious_namespace)

        assert result is False, \
            f"Namespace '{malicious_namespace}' should be invalid ({attack_type})"

    def test_valid_hierarchical_namespaces_accepted(self) -> None:
        """
        Valid hierarchical namespaces should be accepted (sanity check).

        Ensures that strict validation doesn't reject legitimate namespaces.
        """
        valid_namespaces = [
            "corp",
            "corp.hr",
            "corp.hr.compensation",
            "acme",
            "acme.sales.discounts",
            "my_company",
            "my_company.dept_1",
            "a.b.c.d.e.f",
        ]

        for namespace in valid_namespaces:
            result = validate_namespace(namespace)
            assert result is True, \
                f"Namespace '{namespace}' should be valid"

    def test_empty_namespace_rejected(self) -> None:
        """
        Empty string should be rejected as invalid namespace.
        """
        result = validate_namespace("")
        assert result is False, "Empty namespace should be invalid"

    def test_namespace_case_sensitive_lowercase_only(self) -> None:
        """
        Namespaces with uppercase should be rejected.

        Namespace validation requires lowercase only.
        """
        uppercase_namespaces = [
            "Corp",
            "CORP",
            "corp.HR",
            "Corp.Hr.Payroll",
        ]

        for namespace in uppercase_namespaces:
            result = validate_namespace(namespace)
            assert result is False, \
                f"Namespace '{namespace}' should be invalid (uppercase not allowed)"


# =============================================================================
# TEST: Namespace Traversal via process_rfa()
# =============================================================================

class TestNamespaceTraversalAtRFALevel:
    """
    Tests that namespace traversal through process_rfa() raises InputInvalidError.

    These tests verify that validation happens BEFORE Scholar query,
    preventing traversal attacks from reaching the authorization layer.
    """

    def test_double_dot_traversal_in_namespace_field(self) -> None:
        """
        Double-dot traversal in namespace field should fail with DG_INPUT_INVALID.

        From success criteria: Namespace "corp..hr" fails with DG_INPUT_INVALID
        """
        chain = create_chain("test_graph")

        malicious_rfa = {
            "namespace": "corp..hr",  # Double-dot traversal
            "requester_namespace": "corp",
            "requester_id": "attacker:eve"
        }

        with pytest.raises(InputInvalidError) as exc_info:
            process_rfa(chain, malicious_rfa)

        # Verify error code
        assert exc_info.value.code == "DG_INPUT_INVALID", \
            "Double-dot traversal should fail with DG_INPUT_INVALID"

        # Verify namespace field is identified
        assert "namespace" in exc_info.value.message.lower() or \
               exc_info.value.details.get("field") == "namespace", \
            "Error should identify namespace as the problem field"

    def test_slash_traversal_in_namespace_field(self) -> None:
        """
        Slash instead of dot in namespace should fail with DG_INPUT_INVALID.

        From success criteria: Namespace "corp/hr" fails with DG_INPUT_INVALID
        """
        chain = create_chain("test_graph")

        malicious_rfa = {
            "namespace": "corp/hr",  # Slash instead of dot
            "requester_namespace": "corp",
            "requester_id": "attacker:eve"
        }

        with pytest.raises(InputInvalidError) as exc_info:
            process_rfa(chain, malicious_rfa)

        # Verify error code
        assert exc_info.value.code == "DG_INPUT_INVALID", \
            "Slash traversal should fail with DG_INPUT_INVALID"

        # Verify namespace field is identified
        assert "namespace" in exc_info.value.message.lower() or \
               exc_info.value.details.get("field") == "namespace", \
            "Error should identify namespace as the problem field"

    def test_unix_parent_traversal_in_namespace_field(self) -> None:
        """
        Unix parent directory traversal should fail with DG_INPUT_INVALID.

        Attack: corp/../admin attempts to escape corp namespace
        """
        chain = create_chain("test_graph")

        malicious_rfa = {
            "namespace": "corp/../admin",
            "requester_namespace": "corp",
            "requester_id": "attacker:eve"
        }

        with pytest.raises(InputInvalidError) as exc_info:
            process_rfa(chain, malicious_rfa)

        assert exc_info.value.code == "DG_INPUT_INVALID", \
            "Unix parent traversal should fail with DG_INPUT_INVALID"

    def test_double_dot_traversal_in_requester_namespace_field(self) -> None:
        """
        Traversal in requester_namespace field should also be rejected.

        Attackers might try to spoof their namespace to gain access.
        """
        chain = create_chain("test_graph")

        malicious_rfa = {
            "namespace": "corp",
            "requester_namespace": "corp..admin",  # Attacker tries to appear as admin
            "requester_id": "attacker:eve"
        }

        with pytest.raises(InputInvalidError) as exc_info:
            process_rfa(chain, malicious_rfa)

        # Verify error code
        assert exc_info.value.code == "DG_INPUT_INVALID", \
            "Double-dot in requester_namespace should fail with DG_INPUT_INVALID"

        # Verify requester_namespace field is identified
        assert "requester_namespace" in exc_info.value.message.lower() or \
               exc_info.value.details.get("field") == "requester_namespace", \
            "Error should identify requester_namespace as the problem field"

    def test_slash_traversal_in_requester_namespace_field(self) -> None:
        """
        Slash traversal in requester_namespace should be rejected.
        """
        chain = create_chain("test_graph")

        malicious_rfa = {
            "namespace": "corp",
            "requester_namespace": "corp/admin",  # Slash traversal
            "requester_id": "attacker:eve"
        }

        with pytest.raises(InputInvalidError) as exc_info:
            process_rfa(chain, malicious_rfa)

        assert exc_info.value.code == "DG_INPUT_INVALID", \
            "Slash in requester_namespace should fail with DG_INPUT_INVALID"

    def test_windows_traversal_rejected(self) -> None:
        """
        Windows-style backslash traversal should be rejected.
        """
        chain = create_chain("test_graph")

        malicious_rfa = {
            "namespace": "corp\\hr",  # Windows path separator
            "requester_namespace": "corp",
            "requester_id": "attacker:eve"
        }

        with pytest.raises(InputInvalidError) as exc_info:
            process_rfa(chain, malicious_rfa)

        assert exc_info.value.code == "DG_INPUT_INVALID", \
            "Windows backslash should fail with DG_INPUT_INVALID"

    def test_absolute_path_rejected(self) -> None:
        """
        Absolute paths (leading slash) should be rejected.
        """
        chain = create_chain("test_graph")

        malicious_rfa = {
            "namespace": "/etc/passwd",  # Absolute path
            "requester_namespace": "corp",
            "requester_id": "attacker:eve"
        }

        with pytest.raises(InputInvalidError) as exc_info:
            process_rfa(chain, malicious_rfa)

        assert exc_info.value.code == "DG_INPUT_INVALID", \
            "Absolute path should fail with DG_INPUT_INVALID"

    def test_null_byte_traversal_rejected(self) -> None:
        """
        Null byte injection in namespace should be rejected.

        Attack: Attacker tries to truncate namespace string at null byte.
        """
        chain = create_chain("test_graph")

        malicious_rfa = {
            "namespace": "corp.hr\x00admin",  # Null byte
            "requester_namespace": "corp",
            "requester_id": "attacker:eve"
        }

        with pytest.raises(InputInvalidError) as exc_info:
            process_rfa(chain, malicious_rfa)

        assert exc_info.value.code == "DG_INPUT_INVALID", \
            "Null byte in namespace should fail with DG_INPUT_INVALID"

    def test_semicolon_separator_rejected(self) -> None:
        """
        Semicolon as separator should be rejected.

        Attack: Attacker tries to inject command after namespace.
        """
        chain = create_chain("test_graph")

        malicious_rfa = {
            "namespace": "corp.hr;admin",  # Semicolon
            "requester_namespace": "corp",
            "requester_id": "attacker:eve"
        }

        with pytest.raises(InputInvalidError) as exc_info:
            process_rfa(chain, malicious_rfa)

        assert exc_info.value.code == "DG_INPUT_INVALID", \
            "Semicolon in namespace should fail with DG_INPUT_INVALID"

    def test_trailing_dot_rejected(self) -> None:
        """
        Trailing dot in namespace should be rejected.

        Attack: "corp.hr." might be normalized to "corp.hr" in some systems.
        """
        chain = create_chain("test_graph")

        malicious_rfa = {
            "namespace": "corp.hr.",  # Trailing dot
            "requester_namespace": "corp",
            "requester_id": "attacker:eve"
        }

        with pytest.raises(InputInvalidError) as exc_info:
            process_rfa(chain, malicious_rfa)

        assert exc_info.value.code == "DG_INPUT_INVALID", \
            "Trailing dot should fail with DG_INPUT_INVALID"

    def test_leading_dot_rejected(self) -> None:
        """
        Leading dot in namespace should be rejected.

        Attack: ".hidden" or ".corp" might bypass visibility checks.
        """
        chain = create_chain("test_graph")

        malicious_rfa = {
            "namespace": ".hidden",  # Leading dot
            "requester_namespace": "corp",
            "requester_id": "attacker:eve"
        }

        with pytest.raises(InputInvalidError) as exc_info:
            process_rfa(chain, malicious_rfa)

        assert exc_info.value.code == "DG_INPUT_INVALID", \
            "Leading dot should fail with DG_INPUT_INVALID"

    def test_valid_hierarchical_namespace_still_works(self) -> None:
        """
        Valid hierarchical namespace should pass validation (sanity check).

        Ensures that strict traversal prevention doesn't break legitimate use.
        """
        chain = create_chain("test_graph")

        valid_rfa = {
            "namespace": "corp.hr.compensation",  # Valid hierarchical namespace
            "requester_namespace": "corp.audit",
            "requester_id": "auditor:alice"
        }

        # Should not raise - returns ProofPacket
        result = process_rfa(chain, valid_rfa)

        # Verify it's a valid ProofPacket
        assert "packet_version" in result, \
            "Valid namespace should return ProofPacket"
        assert "proof_bundle" in result, \
            "ProofPacket should contain proof_bundle"

    def test_traversal_error_message_is_actionable(self) -> None:
        """
        Traversal error should provide actionable guidance.

        Error message should explain valid namespace format.
        """
        chain = create_chain("test_graph")

        malicious_rfa = {
            "namespace": "corp..hr",
            "requester_namespace": "corp",
            "requester_id": "attacker:eve"
        }

        with pytest.raises(InputInvalidError) as exc_info:
            process_rfa(chain, malicious_rfa)

        error = exc_info.value

        # Message should mention format or pattern
        assert "format" in error.message.lower() or \
               "pattern" in error.message.lower() or \
               "lowercase" in error.message.lower(), \
            "Error message should explain valid namespace format"

        # Details should include pattern or constraint
        assert "pattern" in error.details or "constraint" in error.details, \
            "Error details should include pattern or constraint"
