"""
DecisionGraph Exception Tests (v1.4)

Comprehensive tests for the exception hierarchy and mapping system.

Test Coverage:
- ERR-01: Base class with .code, .message, .details
- ERR-02: All exception mappings from EXCEPTION_MAP
- JSON serialization (to_dict, to_json)
- Exception chaining with traceback preservation

These tests document the expected behavior of the error system and
ensure it integrates cleanly with existing code.
"""

import pytest
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from decisiongraph.exceptions import (
    # Exception classes
    DecisionGraphError,
    SchemaInvalidError,
    InputInvalidError,
    UnauthorizedError,
    IntegrityFailError,
    SignatureInvalidError,
    InternalError,
    # Mapping utilities
    EXCEPTION_MAP,
    wrap_internal_exception,
)

# Import internal exceptions for testing mapping
from decisiongraph.chain import (
    ChainError, IntegrityViolation, ChainBreak,
    GenesisViolation, TemporalViolation, GraphIdMismatch
)
from decisiongraph.namespace import (
    NamespaceError, AccessDeniedError, BridgeRequiredError, BridgeApprovalError
)
from decisiongraph.genesis import GenesisError, GenesisValidationError


# =============================================================================
# ERR-01: TestDecisionGraphError - Base class attributes
# =============================================================================

class TestDecisionGraphError:
    """Test base class DecisionGraphError with .code, .message, .details (ERR-01)"""

    def test_error_has_code(self):
        """Base exception should have a code attribute"""
        error = DecisionGraphError("Test error")
        assert hasattr(error, 'code')
        assert error.code == "DG_INTERNAL_ERROR"

    def test_error_has_message(self):
        """Base exception should have a message attribute"""
        error = DecisionGraphError("Test error message")
        assert hasattr(error, 'message')
        assert error.message == "Test error message"

    def test_error_has_details(self):
        """Base exception should have a details attribute"""
        error = DecisionGraphError("Test error", details={"key": "value"})
        assert hasattr(error, 'details')
        assert error.details == {"key": "value"}

    def test_details_defaults_to_empty_dict(self):
        """Details should default to empty dict if not provided"""
        error = DecisionGraphError("Test error")
        assert error.details == {}

    def test_error_has_request_id(self):
        """Base exception should have a request_id attribute"""
        error = DecisionGraphError("Test error", request_id="req-123")
        assert hasattr(error, 'request_id')
        assert error.request_id == "req-123"

    def test_request_id_defaults_to_none(self):
        """Request ID should default to None"""
        error = DecisionGraphError("Test error")
        assert error.request_id is None

    def test_error_inherits_from_exception(self):
        """DecisionGraphError should be a subclass of Exception"""
        error = DecisionGraphError("Test error")
        assert isinstance(error, Exception)

    def test_error_can_be_raised(self):
        """DecisionGraphError should be raisable"""
        with pytest.raises(DecisionGraphError) as exc_info:
            raise DecisionGraphError("Test error")
        assert exc_info.value.message == "Test error"

    def test_str_format(self):
        """String representation should include code and message"""
        error = DecisionGraphError("Something went wrong")
        assert str(error) == "[DG_INTERNAL_ERROR] Something went wrong"

    def test_repr_format(self):
        """Repr should show class name and key attributes"""
        error = DecisionGraphError("Test", details={"x": 1}, request_id="r1")
        repr_str = repr(error)
        assert "DecisionGraphError" in repr_str
        assert "Test" in repr_str


# =============================================================================
# ERR-01 (continued): TestErrorSubclasses - All 6 error codes
# =============================================================================

class TestErrorSubclasses:
    """Test that all 6 error codes are distinct and correctly defined"""

    def test_six_distinct_error_codes(self):
        """All 6 error codes should be unique"""
        codes = [
            SchemaInvalidError.code,
            InputInvalidError.code,
            UnauthorizedError.code,
            IntegrityFailError.code,
            SignatureInvalidError.code,
            InternalError.code,
        ]
        assert len(codes) == len(set(codes)), "Error codes must be unique"

    def test_schema_invalid_error_code(self):
        """SchemaInvalidError should have DG_SCHEMA_INVALID code"""
        error = SchemaInvalidError("Schema error")
        assert error.code == "DG_SCHEMA_INVALID"

    def test_input_invalid_error_code(self):
        """InputInvalidError should have DG_INPUT_INVALID code"""
        error = InputInvalidError("Input error")
        assert error.code == "DG_INPUT_INVALID"

    def test_unauthorized_error_code(self):
        """UnauthorizedError should have DG_UNAUTHORIZED code"""
        error = UnauthorizedError("Access denied")
        assert error.code == "DG_UNAUTHORIZED"

    def test_integrity_fail_error_code(self):
        """IntegrityFailError should have DG_INTEGRITY_FAIL code"""
        error = IntegrityFailError("Integrity error")
        assert error.code == "DG_INTEGRITY_FAIL"

    def test_signature_invalid_error_code(self):
        """SignatureInvalidError should have DG_SIGNATURE_INVALID code"""
        error = SignatureInvalidError("Signature error")
        assert error.code == "DG_SIGNATURE_INVALID"

    def test_internal_error_code(self):
        """InternalError should have DG_INTERNAL_ERROR code"""
        error = InternalError("Internal error")
        assert error.code == "DG_INTERNAL_ERROR"

    def test_all_subclasses_inherit_from_base(self):
        """All error subclasses should inherit from DecisionGraphError"""
        subclasses = [
            SchemaInvalidError,
            InputInvalidError,
            UnauthorizedError,
            IntegrityFailError,
            SignatureInvalidError,
            InternalError,
        ]
        for cls in subclasses:
            assert issubclass(cls, DecisionGraphError), f"{cls.__name__} must inherit from DecisionGraphError"

    def test_subclasses_preserve_base_functionality(self):
        """Subclasses should preserve base class functionality"""
        error = IntegrityFailError(
            "Hash mismatch",
            details={"expected": "abc", "got": "xyz"},
            request_id="req-456"
        )
        assert error.message == "Hash mismatch"
        assert error.details == {"expected": "abc", "got": "xyz"}
        assert error.request_id == "req-456"
        assert error.code == "DG_INTEGRITY_FAIL"


# =============================================================================
# TestErrorSerialization - to_dict() and to_json()
# =============================================================================

class TestErrorSerialization:
    """Test error serialization to dict and JSON"""

    def test_to_dict_basic(self):
        """to_dict should return dict with code, message, details"""
        error = DecisionGraphError("Test message")
        result = error.to_dict()

        assert isinstance(result, dict)
        assert "code" in result
        assert "message" in result
        assert "details" in result
        assert result["code"] == "DG_INTERNAL_ERROR"
        assert result["message"] == "Test message"
        assert result["details"] == {}

    def test_to_dict_with_details(self):
        """to_dict should include details when provided"""
        error = DecisionGraphError("Error", details={"field": "name", "reason": "required"})
        result = error.to_dict()

        assert result["details"] == {"field": "name", "reason": "required"}

    def test_to_dict_includes_request_id_when_present(self):
        """to_dict should include request_id only when provided"""
        error = DecisionGraphError("Error", request_id="req-abc")
        result = error.to_dict()

        assert "request_id" in result
        assert result["request_id"] == "req-abc"

    def test_to_dict_excludes_request_id_when_none(self):
        """to_dict should not include request_id when None"""
        error = DecisionGraphError("Error")
        result = error.to_dict()

        assert "request_id" not in result

    def test_to_json_produces_valid_json(self):
        """to_json should produce valid JSON string"""
        error = DecisionGraphError("Test", details={"key": "value"})
        json_str = error.to_json()

        # Should be parseable
        parsed = json.loads(json_str)
        assert parsed["code"] == "DG_INTERNAL_ERROR"
        assert parsed["message"] == "Test"
        assert parsed["details"] == {"key": "value"}

    def test_to_json_with_indent(self):
        """to_json should support indentation for pretty-printing"""
        error = DecisionGraphError("Test")
        json_str = error.to_json(indent=2)

        # Should contain newlines when indented
        assert "\n" in json_str

    def test_json_roundtrip(self):
        """JSON serialization should be roundtrip-able"""
        error = IntegrityFailError(
            "Chain break detected",
            details={"position": 5, "expected_hash": "abc123"},
            request_id="req-xyz"
        )

        # Serialize to JSON and back
        json_str = error.to_json()
        parsed = json.loads(json_str)

        assert parsed["code"] == "DG_INTEGRITY_FAIL"
        assert parsed["message"] == "Chain break detected"
        assert parsed["details"]["position"] == 5
        assert parsed["request_id"] == "req-xyz"

    def test_all_subclasses_serialize_correctly(self):
        """All error subclasses should serialize with their own codes"""
        errors = [
            SchemaInvalidError("schema"),
            InputInvalidError("input"),
            UnauthorizedError("auth"),
            IntegrityFailError("integrity"),
            SignatureInvalidError("signature"),
            InternalError("internal"),
        ]

        expected_codes = [
            "DG_SCHEMA_INVALID",
            "DG_INPUT_INVALID",
            "DG_UNAUTHORIZED",
            "DG_INTEGRITY_FAIL",
            "DG_SIGNATURE_INVALID",
            "DG_INTERNAL_ERROR",
        ]

        for error, expected_code in zip(errors, expected_codes):
            result = error.to_dict()
            assert result["code"] == expected_code


# =============================================================================
# ERR-02: TestExceptionMapping - EXCEPTION_MAP correctness
# =============================================================================

class TestExceptionMapping:
    """Test EXCEPTION_MAP has correct mappings (ERR-02)"""

    def test_exception_map_exists(self):
        """EXCEPTION_MAP should exist and be a dict"""
        assert isinstance(EXCEPTION_MAP, dict)

    def test_chain_errors_map_to_integrity_fail(self):
        """Chain-related errors should map to IntegrityFailError"""
        assert EXCEPTION_MAP[IntegrityViolation] == IntegrityFailError
        assert EXCEPTION_MAP[ChainBreak] == IntegrityFailError
        assert EXCEPTION_MAP[TemporalViolation] == IntegrityFailError
        assert EXCEPTION_MAP[GraphIdMismatch] == IntegrityFailError
        assert EXCEPTION_MAP[ChainError] == IntegrityFailError

    def test_genesis_errors_map_to_schema_invalid(self):
        """Genesis-related errors should map to SchemaInvalidError"""
        assert EXCEPTION_MAP[GenesisError] == SchemaInvalidError
        assert EXCEPTION_MAP[GenesisValidationError] == SchemaInvalidError
        assert EXCEPTION_MAP[GenesisViolation] == SchemaInvalidError

    def test_namespace_errors_map_to_unauthorized(self):
        """Namespace/access errors should map to UnauthorizedError"""
        assert EXCEPTION_MAP[AccessDeniedError] == UnauthorizedError
        assert EXCEPTION_MAP[BridgeRequiredError] == UnauthorizedError
        assert EXCEPTION_MAP[BridgeApprovalError] == UnauthorizedError
        assert EXCEPTION_MAP[NamespaceError] == UnauthorizedError

    def test_value_error_maps_to_input_invalid(self):
        """ValueError should map to InputInvalidError"""
        assert EXCEPTION_MAP[ValueError] == InputInvalidError

    def test_type_error_maps_to_input_invalid(self):
        """TypeError should map to InputInvalidError"""
        assert EXCEPTION_MAP[TypeError] == InputInvalidError

    def test_all_mapped_types_are_exception_subclasses(self):
        """All keys in EXCEPTION_MAP should be Exception subclasses"""
        for exc_type in EXCEPTION_MAP.keys():
            assert issubclass(exc_type, Exception), f"{exc_type} is not an Exception subclass"

    def test_all_target_types_are_decisiongraph_errors(self):
        """All values in EXCEPTION_MAP should be DecisionGraphError subclasses"""
        for target_type in EXCEPTION_MAP.values():
            assert issubclass(target_type, DecisionGraphError), f"{target_type} is not a DecisionGraphError subclass"

    def test_map_has_expected_entry_count(self):
        """EXCEPTION_MAP should have 14 entries as documented"""
        # 5 chain errors + 3 genesis errors + 4 namespace errors + 2 builtin (ValueError, TypeError)
        assert len(EXCEPTION_MAP) == 14


# =============================================================================
# ERR-02 (continued): TestWrapInternalException
# =============================================================================

class TestWrapInternalException:
    """Test wrap_internal_exception function works correctly"""

    def test_wraps_mapped_exception(self):
        """wrap_internal_exception should use EXCEPTION_MAP for known types"""
        internal_exc = IntegrityViolation("Cell hash mismatch")
        wrapped = wrap_internal_exception(internal_exc)

        assert isinstance(wrapped, IntegrityFailError)
        assert wrapped.code == "DG_INTEGRITY_FAIL"

    def test_uses_exception_message(self):
        """Wrapped exception should preserve original message"""
        internal_exc = ChainBreak("Chain link broken at position 5")
        wrapped = wrap_internal_exception(internal_exc)

        assert wrapped.message == "Chain link broken at position 5"

    def test_overrides_message_when_provided(self):
        """Should use custom message when provided"""
        internal_exc = IntegrityViolation("original message")
        wrapped = wrap_internal_exception(
            internal_exc,
            default_message="Custom message for API"
        )

        assert wrapped.message == "Custom message for API"

    def test_includes_internal_error_type_in_details(self):
        """Details should include original exception type for debugging"""
        internal_exc = TemporalViolation("Timestamp out of order")
        wrapped = wrap_internal_exception(internal_exc)

        assert "internal_error" in wrapped.details
        assert wrapped.details["internal_error"] == "TemporalViolation"

    def test_preserves_provided_details(self):
        """Custom details should be preserved"""
        internal_exc = GraphIdMismatch("Graph ID mismatch")
        wrapped = wrap_internal_exception(
            internal_exc,
            details={"cell_id": "abc123", "expected_graph": "graph:xyz"}
        )

        assert wrapped.details["cell_id"] == "abc123"
        assert wrapped.details["expected_graph"] == "graph:xyz"
        assert wrapped.details["internal_error"] == "GraphIdMismatch"

    def test_includes_request_id_when_provided(self):
        """Request ID should be passed through"""
        internal_exc = AccessDeniedError("Access denied")
        wrapped = wrap_internal_exception(internal_exc, request_id="req-789")

        assert wrapped.request_id == "req-789"

    def test_unknown_exception_maps_to_internal_error(self):
        """Unknown exceptions should map to InternalError"""
        unknown_exc = RuntimeError("Something unexpected")
        wrapped = wrap_internal_exception(unknown_exc)

        assert isinstance(wrapped, InternalError)
        assert wrapped.code == "DG_INTERNAL_ERROR"
        assert wrapped.details["internal_error"] == "RuntimeError"

    def test_includes_failed_checks_from_genesis_validation_error(self):
        """Should include failed_checks from GenesisValidationError"""
        internal_exc = GenesisValidationError(
            "Genesis validation failed",
            failed_checks=["[1] wrong cell_type", "[2] wrong prev_hash"]
        )
        wrapped = wrap_internal_exception(internal_exc)

        assert "failed_checks" in wrapped.details
        assert wrapped.details["failed_checks"] == ["[1] wrong cell_type", "[2] wrong prev_hash"]

    def test_wrap_value_error(self):
        """ValueError should wrap to InputInvalidError"""
        internal_exc = ValueError("Invalid input format")
        wrapped = wrap_internal_exception(internal_exc)

        assert isinstance(wrapped, InputInvalidError)
        assert wrapped.code == "DG_INPUT_INVALID"

    def test_wrap_type_error(self):
        """TypeError should wrap to InputInvalidError"""
        internal_exc = TypeError("Expected string, got int")
        wrapped = wrap_internal_exception(internal_exc)

        assert isinstance(wrapped, InputInvalidError)
        assert wrapped.code == "DG_INPUT_INVALID"


# =============================================================================
# TestExceptionChaining - traceback preservation
# =============================================================================

class TestExceptionChaining:
    """Test exception chaining preserves traceback"""

    def test_exception_chaining_preserves_cause(self):
        """Using 'raise from' should preserve the original exception"""
        internal_exc = IntegrityViolation("Cell integrity failed")

        try:
            try:
                raise internal_exc
            except IntegrityViolation as e:
                raise wrap_internal_exception(e) from e
        except DecisionGraphError as caught:
            assert caught.__cause__ is internal_exc

    def test_chained_exception_has_traceback(self):
        """Chained exception should have accessible traceback"""
        internal_exc = ChainBreak("Chain link broken")

        try:
            try:
                raise internal_exc
            except ChainBreak as e:
                raise wrap_internal_exception(e, details={"position": 5}) from e
        except DecisionGraphError as caught:
            assert caught.__cause__ is not None
            assert caught.__cause__.__traceback__ is not None

    def test_can_catch_by_base_class(self):
        """Should be able to catch any DecisionGraphError by base class"""
        exceptions_to_test = [
            SchemaInvalidError("schema"),
            InputInvalidError("input"),
            UnauthorizedError("auth"),
            IntegrityFailError("integrity"),
            SignatureInvalidError("signature"),
            InternalError("internal"),
        ]

        for exc in exceptions_to_test:
            caught = False
            try:
                raise exc
            except DecisionGraphError:
                caught = True
            assert caught, f"Failed to catch {type(exc).__name__} as DecisionGraphError"

    def test_can_catch_specific_error_types(self):
        """Should be able to catch specific error types"""
        try:
            raise IntegrityFailError("test")
        except IntegrityFailError as e:
            assert e.code == "DG_INTEGRITY_FAIL"

    def test_exception_chaining_in_realistic_scenario(self):
        """Test exception chaining in a realistic use case"""
        def internal_operation():
            raise IntegrityViolation("Cell hash does not match")

        def api_boundary():
            try:
                internal_operation()
            except IntegrityViolation as e:
                raise wrap_internal_exception(
                    e,
                    details={"cell_id": "abc123"},
                    request_id="req-test"
                ) from e

        with pytest.raises(IntegrityFailError) as exc_info:
            api_boundary()

        error = exc_info.value
        assert error.code == "DG_INTEGRITY_FAIL"
        assert error.message == "Cell hash does not match"
        assert error.details["cell_id"] == "abc123"
        assert error.details["internal_error"] == "IntegrityViolation"
        assert error.request_id == "req-test"
        assert isinstance(error.__cause__, IntegrityViolation)


# =============================================================================
# TestErrorCodeConsistency - Additional edge cases
# =============================================================================

class TestErrorCodeConsistency:
    """Test error code consistency and edge cases"""

    def test_error_code_is_class_attribute(self):
        """Error code should be accessible without instantiation"""
        assert DecisionGraphError.code == "DG_INTERNAL_ERROR"
        assert SchemaInvalidError.code == "DG_SCHEMA_INVALID"

    def test_instance_code_matches_class_code(self):
        """Instance code should match class code"""
        error = IntegrityFailError("test")
        assert error.code == IntegrityFailError.code

    def test_subclass_does_not_affect_parent_code(self):
        """Subclass code should not affect parent class code"""
        _ = SchemaInvalidError("test")
        assert DecisionGraphError.code == "DG_INTERNAL_ERROR"

    def test_error_codes_are_strings(self):
        """All error codes should be strings"""
        codes = [
            DecisionGraphError.code,
            SchemaInvalidError.code,
            InputInvalidError.code,
            UnauthorizedError.code,
            IntegrityFailError.code,
            SignatureInvalidError.code,
            InternalError.code,
        ]
        for code in codes:
            assert isinstance(code, str), f"{code} is not a string"

    def test_error_codes_follow_naming_convention(self):
        """All error codes should follow DG_* naming convention"""
        codes = [
            DecisionGraphError.code,
            SchemaInvalidError.code,
            InputInvalidError.code,
            UnauthorizedError.code,
            IntegrityFailError.code,
            SignatureInvalidError.code,
            InternalError.code,
        ]
        for code in codes:
            assert code.startswith("DG_"), f"{code} does not follow DG_* convention"

    def test_empty_details_serializes_as_empty_dict(self):
        """Empty details should serialize as {} not null"""
        error = DecisionGraphError("test")
        result = error.to_dict()
        assert result["details"] == {}

        json_result = json.loads(error.to_json())
        assert json_result["details"] == {}

    def test_complex_details_serialize_correctly(self):
        """Complex nested details should serialize correctly"""
        details = {
            "field": "namespace",
            "violations": [
                {"check": "format", "expected": "lowercase"},
                {"check": "length", "max": 64}
            ],
            "metadata": {"line": 10, "column": 5}
        }
        error = SchemaInvalidError("Validation failed", details=details)

        json_str = error.to_json()
        parsed = json.loads(json_str)

        assert parsed["details"]["violations"][0]["check"] == "format"
        assert parsed["details"]["metadata"]["line"] == 10
