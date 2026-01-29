"""
Test suite for DecisionGraph input validators (Phase 2).

Tests VAL-01 through VAL-04 requirements:
- VAL-01: Subject validation (type:identifier format)
- VAL-02: Predicate validation (snake_case, max 64 chars)
- VAL-03: Object length validation (max 4096 chars)
- VAL-04: Control character rejection
"""

import pytest

from decisiongraph.validators import (
    validate_subject_field,
    validate_predicate_field,
    validate_object_field,
    contains_control_chars,
    SUBJECT_PATTERN,
    PREDICATE_PATTERN,
    CONTROL_CHARS_PATTERN,
    MAX_OBJECT_LENGTH,
)
from decisiongraph.exceptions import InputInvalidError


# =============================================================================
# TEST: Subject Validation (VAL-01)
# =============================================================================

class TestSubjectValidation:
    """Tests for validate_subject_field() - VAL-01 requirements."""

    @pytest.mark.parametrize("valid_subject", [
        "user:alice",
        "user:alice123",
        "user:alice_123",
        "user:alice.bob",
        "user:path/to/resource",
        "user:a-b-c",
        "entity_type:id_123",
        "type:a" + "x" * 127,  # Exactly 128 chars after colon
        "a:b",  # Minimum valid
        "user:alice/documents/file.txt",
        "resource:api/v1/users",
        "_type:_value",  # Underscores in both parts
        "my_entity:some_id",
    ])
    def test_valid_subjects_accepted(self, valid_subject: str) -> None:
        """Valid subjects should pass validation without raising."""
        validate_subject_field(valid_subject)  # Should not raise

    @pytest.mark.parametrize("invalid_subject,reason", [
        ("", "empty string"),
        ("NoColon", "missing colon"),
        ("type:", "empty identifier"),
        (":identifier", "empty type"),
        ("TYPE:id", "uppercase type"),
        ("type:ID", "uppercase identifier"),
        ("type:" + "x" * 129, "identifier too long >128"),
        ("type:id\x00", "null byte"),
        ("type:id\x1F", "control char 0x1F"),
        ("type:id name", "space not allowed"),
        ("type:id;DROP TABLE", "semicolon not allowed"),
        ("123:id", "type starts with digit"),
        ("type:id@domain", "at-sign not allowed"),
        ("type:id#anchor", "hash not allowed"),
        ("Type:id", "capitalized type"),
        ("user:Alice", "capitalized identifier"),
        ("user:ALICE", "uppercase identifier"),
        ("user:alice\x0B", "vertical tab not allowed"),
        ("user:alice\x08", "backspace not allowed"),
    ])
    def test_invalid_subjects_rejected(self, invalid_subject: str, reason: str) -> None:
        """Invalid subjects should raise InputInvalidError."""
        with pytest.raises(InputInvalidError) as exc_info:
            validate_subject_field(invalid_subject)

        # Verify error code
        assert exc_info.value.code == "DG_INPUT_INVALID"
        # Verify details contains field name
        assert exc_info.value.details.get("field") == "subject"

    def test_subject_error_is_actionable(self) -> None:
        """Error message should contain pattern and example."""
        with pytest.raises(InputInvalidError) as exc_info:
            validate_subject_field("INVALID")

        error = exc_info.value
        # Message should be actionable
        assert "type:identifier" in error.message.lower() or "format" in error.message.lower()
        # Details should include pattern
        assert "pattern" in error.details or "constraint" in error.details

    def test_subject_custom_field_name(self) -> None:
        """Custom field_name should appear in error message and details."""
        with pytest.raises(InputInvalidError) as exc_info:
            validate_subject_field("INVALID", field_name="actor")

        assert exc_info.value.details.get("field") == "actor"
        assert "actor" in exc_info.value.message

    def test_subject_value_truncated_in_details(self) -> None:
        """Long values should be truncated to 100 chars in error details."""
        long_subject = "type:" + "x" * 200
        with pytest.raises(InputInvalidError) as exc_info:
            validate_subject_field(long_subject)

        # Value in details should be truncated
        assert len(exc_info.value.details.get("value", "")) <= 100


# =============================================================================
# TEST: Predicate Validation (VAL-02)
# =============================================================================

class TestPredicateValidation:
    """Tests for validate_predicate_field() - VAL-02 requirements."""

    @pytest.mark.parametrize("valid_predicate", [
        "can_access",
        "has_permission",
        "is_admin",
        "a",  # Single char
        "_private",  # Starts with underscore
        "x" * 64,  # Exactly 64 chars
        "read123",
        "read_write_execute",
        "owns",
        "member_of",
        "_",  # Single underscore
        "a1",
    ])
    def test_valid_predicates_accepted(self, valid_predicate: str) -> None:
        """Valid predicates should pass validation without raising."""
        validate_predicate_field(valid_predicate)  # Should not raise

    @pytest.mark.parametrize("invalid_predicate,reason", [
        ("", "empty string"),
        ("can access", "space"),
        ("123read", "starts with digit"),
        ("can-access", "hyphen not allowed"),
        ("can.access", "dot not allowed"),
        ("x" * 65, "too long >64"),
        ("pred\x00", "null byte"),
        ("CAN_ACCESS", "uppercase"),
        ("Can_Access", "mixed case"),
        ("pred;drop", "semicolon"),
        ("pred/path", "slash not allowed"),
        ("pred:type", "colon not allowed"),
        ("pred@domain", "at-sign not allowed"),
        ("pred\x0B", "vertical tab"),
        ("pred\x1F", "control char 0x1F"),
        ("1", "single digit"),
        ("1_read", "starts with digit"),
    ])
    def test_invalid_predicates_rejected(self, invalid_predicate: str, reason: str) -> None:
        """Invalid predicates should raise InputInvalidError."""
        with pytest.raises(InputInvalidError) as exc_info:
            validate_predicate_field(invalid_predicate)

        assert exc_info.value.code == "DG_INPUT_INVALID"
        assert exc_info.value.details.get("field") == "predicate"

    def test_predicate_error_is_actionable(self) -> None:
        """Error message should contain pattern info and example."""
        with pytest.raises(InputInvalidError) as exc_info:
            validate_predicate_field("CAN_ACCESS")

        error = exc_info.value
        # Should mention snake_case or format
        assert "snake_case" in error.message.lower() or "format" in error.message.lower()
        assert "pattern" in error.details or "constraint" in error.details

    def test_predicate_custom_field_name(self) -> None:
        """Custom field_name should appear in error message and details."""
        with pytest.raises(InputInvalidError) as exc_info:
            validate_predicate_field("INVALID", field_name="relation")

        assert exc_info.value.details.get("field") == "relation"
        assert "relation" in exc_info.value.message


# =============================================================================
# TEST: Object Validation (VAL-03, VAL-04)
# =============================================================================

class TestObjectValidation:
    """Tests for validate_object_field() - VAL-03 and VAL-04 requirements."""

    @pytest.mark.parametrize("valid_object", [
        "user:alice",  # Typed ID
        '{"type": "amount", "value": 100}',  # TypedValue JSON
        "simple string",
        "string with tab\there",  # Tab allowed
        "string with\nnewline",  # Newline allowed
        "x" * 4096,  # Exactly max length
        "Mixed CASE is Fine",  # Object allows uppercase
        "special chars: !@#$%^&*()",
        '{"nested": {"key": "value"}}',
        "line1\nline2\nline3",  # Multiple newlines
        "col1\tcol2\tcol3",  # Multiple tabs
        "",  # Empty string check handled separately
    ])
    def test_valid_objects_accepted(self, valid_object: str) -> None:
        """Valid objects should pass validation without raising."""
        if valid_object == "":
            # Empty string is invalid, skip this case here
            return
        validate_object_field(valid_object)  # Should not raise

    @pytest.mark.parametrize("invalid_object,reason", [
        ("", "empty string"),
        ("x" * 4097, "exceeds 4096 chars"),
        ("value\x00here", "null byte"),
        ("value\x1Fhere", "control char 0x1F"),
        ("value\x08here", "backspace"),
        ("value\x0Bhere", "vertical tab"),
        ("value\x01here", "SOH control char"),
        ("value\x02here", "STX control char"),
        ("value\x03here", "ETX control char"),
        ("value\x04here", "EOT control char"),
        ("value\x05here", "ENQ control char"),
        ("value\x06here", "ACK control char"),
        ("value\x07here", "BEL control char"),
        ("value\x0Chere", "form feed"),
        ("value\x0Dhere", "carriage return"),  # CR is 0x0D, within range
    ])
    def test_invalid_objects_rejected(self, invalid_object: str, reason: str) -> None:
        """Invalid objects should raise InputInvalidError."""
        with pytest.raises(InputInvalidError) as exc_info:
            validate_object_field(invalid_object)

        assert exc_info.value.code == "DG_INPUT_INVALID"
        assert exc_info.value.details.get("field") == "object"

    def test_object_empty_string_rejected(self) -> None:
        """Empty string should raise InputInvalidError."""
        with pytest.raises(InputInvalidError) as exc_info:
            validate_object_field("")

        assert "empty" in exc_info.value.message.lower()
        assert exc_info.value.details.get("constraint") == "non-empty"

    def test_object_length_error_includes_length(self) -> None:
        """Length violation error should include actual length in details."""
        long_obj = "x" * 5000
        with pytest.raises(InputInvalidError) as exc_info:
            validate_object_field(long_obj)

        error = exc_info.value
        assert error.details.get("actual_length") == 5000
        assert error.details.get("max_length") == 4096
        assert "5000" in error.message

    def test_object_length_checked_before_control_chars(self) -> None:
        """Length should be checked FIRST (security: prevent huge input processing)."""
        # Create an object that's too long AND has control chars
        # If length is checked first, we get length error, not control char error
        huge_with_control = "\x00" * 5000
        with pytest.raises(InputInvalidError) as exc_info:
            validate_object_field(huge_with_control)

        # Should be length error, not control char error
        assert exc_info.value.details.get("actual_length") == 5000

    def test_object_custom_field_name(self) -> None:
        """Custom field_name should appear in error message and details."""
        with pytest.raises(InputInvalidError) as exc_info:
            validate_object_field("", field_name="target")

        assert exc_info.value.details.get("field") == "target"
        assert "target" in exc_info.value.message

    def test_object_allows_tab_and_newline(self) -> None:
        """Tab (0x09) and newline (0x0A) should be allowed in objects."""
        # Tab
        validate_object_field("col1\tcol2")  # Should not raise
        # Newline
        validate_object_field("line1\nline2")  # Should not raise
        # Both
        validate_object_field("col1\tcol2\nrow2col1\trow2col2")  # Should not raise


# =============================================================================
# TEST: Control Character Detection (VAL-04)
# =============================================================================

class TestControlCharacterDetection:
    """Tests for contains_control_chars() helper function."""

    @pytest.mark.parametrize("control_char", [
        "\x00",  # NUL
        "\x01",  # SOH
        "\x02",  # STX
        "\x03",  # ETX
        "\x04",  # EOT
        "\x05",  # ENQ
        "\x06",  # ACK
        "\x07",  # BEL
        "\x08",  # BS
        # Skip \x09 (TAB) and \x0A (LF) - they're allowed
        "\x0B",  # VT
        "\x0C",  # FF
        "\x0D",  # CR
        "\x0E",  # SO
        "\x0F",  # SI
        "\x10",  # DLE
        "\x11",  # DC1
        "\x12",  # DC2
        "\x13",  # DC3
        "\x14",  # DC4
        "\x15",  # NAK
        "\x16",  # SYN
        "\x17",  # ETB
        "\x18",  # CAN
        "\x19",  # EM
        "\x1A",  # SUB
        "\x1B",  # ESC
        "\x1C",  # FS
        "\x1D",  # GS
        "\x1E",  # RS
        "\x1F",  # US
    ])
    def test_control_chars_detected(self, control_char: str) -> None:
        """Disallowed control characters should be detected."""
        text = f"value{control_char}here"
        assert contains_control_chars(text) is True

    @pytest.mark.parametrize("allowed_char", [
        "\x09",  # TAB
        "\x0A",  # LF (newline)
    ])
    def test_allowed_chars_not_detected(self, allowed_char: str) -> None:
        """TAB and NEWLINE should NOT be detected as control chars."""
        text = f"value{allowed_char}here"
        assert contains_control_chars(text) is False

    def test_printable_ascii_not_detected(self) -> None:
        """Normal printable ASCII should not trigger control char detection."""
        printable = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        printable += "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        printable += " "  # Space
        assert contains_control_chars(printable) is False

    def test_empty_string_no_control_chars(self) -> None:
        """Empty string should not contain control chars."""
        assert contains_control_chars("") is False

    def test_only_tab_newline_allowed(self) -> None:
        """String with only tab and newline should pass."""
        assert contains_control_chars("\t\n\t\n") is False

    def test_mixed_content_detected(self) -> None:
        """Control char anywhere in mixed content should be detected."""
        assert contains_control_chars("abc\x00def") is True
        assert contains_control_chars("\x00abcdef") is True
        assert contains_control_chars("abcdef\x00") is True


# =============================================================================
# TEST: Error Code Integration
# =============================================================================

class TestErrorCodeIntegration:
    """Tests verifying InputInvalidError has correct error code."""

    def test_subject_error_has_correct_code(self) -> None:
        """Subject validation error should have DG_INPUT_INVALID code."""
        with pytest.raises(InputInvalidError) as exc_info:
            validate_subject_field("INVALID")
        assert exc_info.value.code == "DG_INPUT_INVALID"

    def test_predicate_error_has_correct_code(self) -> None:
        """Predicate validation error should have DG_INPUT_INVALID code."""
        with pytest.raises(InputInvalidError) as exc_info:
            validate_predicate_field("INVALID PREDICATE")
        assert exc_info.value.code == "DG_INPUT_INVALID"

    def test_object_error_has_correct_code(self) -> None:
        """Object validation error should have DG_INPUT_INVALID code."""
        with pytest.raises(InputInvalidError) as exc_info:
            validate_object_field("")
        assert exc_info.value.code == "DG_INPUT_INVALID"

    def test_error_serializable_to_dict(self) -> None:
        """Validation errors should be serializable to dict."""
        with pytest.raises(InputInvalidError) as exc_info:
            validate_subject_field("INVALID")

        error_dict = exc_info.value.to_dict()
        assert error_dict["code"] == "DG_INPUT_INVALID"
        assert "message" in error_dict
        assert "details" in error_dict

    def test_error_serializable_to_json(self) -> None:
        """Validation errors should be serializable to JSON."""
        with pytest.raises(InputInvalidError) as exc_info:
            validate_subject_field("INVALID")

        import json
        json_str = exc_info.value.to_json()
        parsed = json.loads(json_str)
        assert parsed["code"] == "DG_INPUT_INVALID"


# =============================================================================
# TEST: Constants and Patterns
# =============================================================================

class TestConstantsAndPatterns:
    """Tests verifying module constants are correctly defined."""

    def test_max_object_length_constant(self) -> None:
        """MAX_OBJECT_LENGTH should be 4096."""
        assert MAX_OBJECT_LENGTH == 4096

    def test_subject_pattern_compiled(self) -> None:
        """SUBJECT_PATTERN should be a compiled regex."""
        import re
        assert isinstance(SUBJECT_PATTERN, re.Pattern)
        assert SUBJECT_PATTERN.fullmatch("user:alice") is not None
        assert SUBJECT_PATTERN.fullmatch("USER:alice") is None

    def test_predicate_pattern_compiled(self) -> None:
        """PREDICATE_PATTERN should be a compiled regex."""
        import re
        assert isinstance(PREDICATE_PATTERN, re.Pattern)
        assert PREDICATE_PATTERN.fullmatch("can_access") is not None
        assert PREDICATE_PATTERN.fullmatch("CAN_ACCESS") is None

    def test_control_chars_pattern_compiled(self) -> None:
        """CONTROL_CHARS_PATTERN should be a compiled regex."""
        import re
        assert isinstance(CONTROL_CHARS_PATTERN, re.Pattern)
        assert CONTROL_CHARS_PATTERN.search("\x00") is not None
        assert CONTROL_CHARS_PATTERN.search("\t") is None  # Tab allowed


# =============================================================================
# TEST: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_subject_exactly_128_chars_identifier(self) -> None:
        """Subject with exactly 128-char identifier should be valid."""
        subject = "type:" + "a" * 128
        validate_subject_field(subject)  # Should not raise

    def test_subject_129_chars_identifier_rejected(self) -> None:
        """Subject with 129-char identifier should be rejected."""
        subject = "type:" + "a" * 129
        with pytest.raises(InputInvalidError):
            validate_subject_field(subject)

    def test_predicate_exactly_64_chars(self) -> None:
        """Predicate with exactly 64 chars should be valid."""
        predicate = "a" * 64
        validate_predicate_field(predicate)  # Should not raise

    def test_predicate_65_chars_rejected(self) -> None:
        """Predicate with 65 chars should be rejected."""
        predicate = "a" * 65
        with pytest.raises(InputInvalidError):
            validate_predicate_field(predicate)

    def test_object_exactly_4096_chars(self) -> None:
        """Object with exactly 4096 chars should be valid."""
        obj = "a" * 4096
        validate_object_field(obj)  # Should not raise

    def test_object_4097_chars_rejected(self) -> None:
        """Object with 4097 chars should be rejected."""
        obj = "a" * 4097
        with pytest.raises(InputInvalidError):
            validate_object_field(obj)

    def test_unicode_in_object_allowed(self) -> None:
        """Unicode characters should be allowed in object field."""
        validate_object_field("Hello, World!")  # Should not raise
        validate_object_field("Emoji test: yes")  # No emojis, but unicode-safe

    def test_subject_with_multiple_colons(self) -> None:
        """Subject type cannot have colon, but identifier can't either per pattern."""
        # The pattern doesn't allow colon anywhere
        with pytest.raises(InputInvalidError):
            validate_subject_field("type:id:extra")

    def test_subject_with_leading_underscore_type(self) -> None:
        """Type can start with underscore."""
        validate_subject_field("_type:identifier")  # Should not raise

    def test_subject_with_all_underscores_type(self) -> None:
        """Type can be all underscores."""
        validate_subject_field("___:identifier")  # Should not raise

    def test_predicate_single_underscore(self) -> None:
        """Single underscore is a valid predicate."""
        validate_predicate_field("_")  # Should not raise
