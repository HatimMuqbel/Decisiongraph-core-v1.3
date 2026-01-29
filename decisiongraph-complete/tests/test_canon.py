"""
Tests for RFC 8785 Canonical JSON Module

These tests verify the "byte physics" law for DecisionGraph:
- Same input always produces identical bytes
- Float values are rejected (policy)
- Key ordering is lexicographic by UTF-8 bytes
- String escaping follows RFC 8785
- Round-trip stability
"""

import pytest
import hashlib
from decimal import Decimal

from decisiongraph.canon import (
    canonical_json_bytes,
    canonical_json_string,
    validate_canonical_safe,
    canonical_hash,
    float_to_canonical_string,
    confidence_to_string,
    score_to_string,
    evidence_sort_key,
    cell_to_canonical_dict,
    rfa_to_canonical_dict,
    CanonicalEncodingError,
    FloatNotAllowedError,
)
from decisiongraph.cell import (
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Evidence,
    Proof,
    CellType,
    SourceQuality,
)


# ============================================================================
# TEST: KEY ORDERING (RFC 8785 Section 3.2.3)
# ============================================================================

class TestKeyOrdering:
    """Keys must be sorted by UTF-8 byte values."""

    def test_simple_key_ordering(self):
        """Keys sorted alphabetically for ASCII."""
        obj = {"b": 1, "a": 2, "c": 3}
        result = canonical_json_string(obj)
        assert result == '{"a":2,"b":1,"c":3}'

    def test_numeric_string_keys(self):
        """Numeric string keys sorted lexicographically, not numerically."""
        obj = {"10": "ten", "2": "two", "1": "one"}
        result = canonical_json_string(obj)
        # Lexicographic: "1" < "10" < "2"
        assert result == '{"1":"one","10":"ten","2":"two"}'

    def test_case_sensitive_ordering(self):
        """Uppercase letters sort before lowercase in UTF-8."""
        obj = {"a": 1, "B": 2, "A": 3}
        result = canonical_json_string(obj)
        # UTF-8 order: A (65) < B (66) < a (97)
        assert result == '{"A":3,"B":2,"a":1}'

    def test_unicode_key_ordering(self):
        """Unicode keys sorted by UTF-8 byte values."""
        obj = {"z": 1, "a": 2, "\u00e9": 3}  # e-acute
        result = canonical_json_string(obj)
        # UTF-8 bytes: a(97) < z(122) < e-acute (195, 169)
        assert result == '{"a":2,"z":1,"\u00e9":3}'

    def test_nested_key_ordering(self):
        """Nested objects also have sorted keys."""
        obj = {"z": {"b": 1, "a": 2}, "a": 1}
        result = canonical_json_string(obj)
        assert result == '{"a":1,"z":{"a":2,"b":1}}'


# ============================================================================
# TEST: NO WHITESPACE
# ============================================================================

class TestNoWhitespace:
    """Canonical JSON has no whitespace."""

    def test_no_spaces_in_object(self):
        """No spaces around colons or commas in objects."""
        result = canonical_json_string({"a": 1, "b": 2})
        assert ' ' not in result
        assert result == '{"a":1,"b":2}'

    def test_no_spaces_in_array(self):
        """No spaces around commas in arrays."""
        result = canonical_json_string([1, 2, 3])
        assert ' ' not in result
        assert result == '[1,2,3]'

    def test_no_newlines(self):
        """No newlines in output."""
        result = canonical_json_string({"key": "value"})
        assert '\n' not in result


# ============================================================================
# TEST: STRING ESCAPING (RFC 8785 Section 3.2.2.2)
# ============================================================================

class TestStringEscaping:
    """String escaping follows RFC 8785."""

    def test_quote_escaped(self):
        """Double quotes are escaped."""
        result = canonical_json_string({"key": 'value with "quotes"'})
        assert r'\"' in result

    def test_backslash_escaped(self):
        """Backslashes are escaped."""
        result = canonical_json_string({"key": "path\\to\\file"})
        assert r'\\' in result

    def test_control_chars_escaped(self):
        """Control characters (0x00-0x1F) are escaped."""
        result = canonical_json_string({"key": "line1\nline2"})
        assert r'\n' in result

        result = canonical_json_string({"key": "tab\there"})
        assert r'\t' in result

    def test_null_char_escaped(self):
        """Null character escaped as \\u0000."""
        result = canonical_json_string({"key": "a\x00b"})
        assert r'\u0000' in result

    def test_unicode_not_escaped(self):
        """Non-ASCII Unicode preserved as literal UTF-8."""
        result = canonical_json_string({"key": "\u00e9\u00e8\u00ea"})  # e-acute, e-grave, e-circumflex
        # Should contain literal characters, not \uXXXX escapes
        assert '\u00e9' in result
        assert r'\u00e9' not in result

    def test_emoji_preserved(self):
        """Emoji preserved as literal UTF-8."""
        result = canonical_json_string({"emoji": "\U0001F600"})  # grinning face
        assert '\U0001F600' in result


# ============================================================================
# TEST: FLOAT REJECTION (DecisionGraph Policy)
# ============================================================================

class TestFloatRejection:
    """Floats are not allowed in canonical JSON."""

    def test_float_raises_error(self):
        """Direct float value raises FloatNotAllowedError."""
        with pytest.raises(FloatNotAllowedError) as exc_info:
            canonical_json_bytes({"value": 1.5})
        assert "Float value" in str(exc_info.value)
        assert "value" in str(exc_info.value)  # path included

    def test_float_in_nested_dict(self):
        """Float in nested dict raises error with path."""
        with pytest.raises(FloatNotAllowedError) as exc_info:
            canonical_json_bytes({"outer": {"inner": 3.14}})
        assert "outer.inner" in str(exc_info.value)

    def test_float_in_array(self):
        """Float in array raises error with index path."""
        with pytest.raises(FloatNotAllowedError) as exc_info:
            canonical_json_bytes({"values": [1, 2.5, 3]})
        assert "[1]" in str(exc_info.value)

    def test_zero_point_zero_rejected(self):
        """Even 0.0 is rejected (it's a float)."""
        with pytest.raises(FloatNotAllowedError):
            canonical_json_bytes({"value": 0.0})

    def test_validation_catches_float(self):
        """validate_canonical_safe catches floats."""
        with pytest.raises(FloatNotAllowedError):
            validate_canonical_safe({"confidence": 0.95})


# ============================================================================
# TEST: DECIMAL REJECTION
# ============================================================================

class TestDecimalRejection:
    """Decimal must be converted to string before encoding."""

    def test_decimal_raises_error(self):
        """Decimal value raises CanonicalEncodingError."""
        with pytest.raises(CanonicalEncodingError) as exc_info:
            canonical_json_bytes({"value": Decimal("1.5")})
        assert "Decimal" in str(exc_info.value)
        assert "string" in str(exc_info.value).lower()


# ============================================================================
# TEST: PRIMITIVES
# ============================================================================

class TestPrimitives:
    """Primitive values encoded correctly."""

    def test_null(self):
        """None encoded as null."""
        assert canonical_json_string(None) == 'null'

    def test_true(self):
        """True encoded as true."""
        assert canonical_json_string(True) == 'true'

    def test_false(self):
        """False encoded as false."""
        assert canonical_json_string(False) == 'false'

    def test_integer(self):
        """Integers encoded as-is."""
        assert canonical_json_string(42) == '42'
        assert canonical_json_string(-123) == '-123'
        assert canonical_json_string(0) == '0'

    def test_large_integer(self):
        """Large integers encoded correctly."""
        assert canonical_json_string(9007199254740992) == '9007199254740992'

    def test_string(self):
        """Simple strings encoded with quotes."""
        assert canonical_json_string("hello") == '"hello"'

    def test_empty_string(self):
        """Empty string encoded as empty quotes."""
        assert canonical_json_string("") == '""'


# ============================================================================
# TEST: COLLECTIONS
# ============================================================================

class TestCollections:
    """Arrays and objects encoded correctly."""

    def test_empty_array(self):
        """Empty array."""
        assert canonical_json_string([]) == '[]'

    def test_empty_object(self):
        """Empty object."""
        assert canonical_json_string({}) == '{}'

    def test_nested_structure(self):
        """Deeply nested structures."""
        obj = {
            "a": {
                "b": {
                    "c": [1, 2, {"d": 3}]
                }
            }
        }
        result = canonical_json_string(obj)
        assert result == '{"a":{"b":{"c":[1,2,{"d":3}]}}}'

    def test_tuple_as_array(self):
        """Tuples encoded as arrays."""
        assert canonical_json_string((1, 2, 3)) == '[1,2,3]'


# ============================================================================
# TEST: DETERMINISM
# ============================================================================

class TestDeterminism:
    """Same input always produces same output."""

    def test_same_dict_same_bytes(self):
        """Same dict produces identical bytes."""
        obj = {"z": 1, "a": 2, "m": 3}
        bytes1 = canonical_json_bytes(obj)
        bytes2 = canonical_json_bytes(obj)
        assert bytes1 == bytes2

    def test_deterministic_across_calls(self):
        """Multiple calls produce identical output."""
        obj = {"key": "value", "nested": {"a": 1, "b": 2}}
        results = [canonical_json_bytes(obj) for _ in range(100)]
        assert all(r == results[0] for r in results)

    def test_hash_stability(self):
        """Hash of canonical bytes is stable."""
        obj = {"x": 1, "y": 2}
        hash1 = canonical_hash(obj)
        hash2 = canonical_hash(obj)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex


# ============================================================================
# TEST: ROUND TRIP
# ============================================================================

class TestRoundTrip:
    """bytes -> dict -> bytes produces identical bytes."""

    def test_roundtrip_simple(self):
        """Simple object round-trips correctly."""
        import json
        obj = {"a": 1, "b": "hello", "c": True, "d": None}
        bytes1 = canonical_json_bytes(obj)

        # Parse back and re-encode
        parsed = json.loads(bytes1.decode('utf-8'))
        bytes2 = canonical_json_bytes(parsed)

        assert bytes1 == bytes2

    def test_roundtrip_nested(self):
        """Nested structure round-trips correctly."""
        import json
        obj = {
            "header": {"version": "1.3", "type": "test"},
            "data": [1, 2, 3],
            "meta": {"active": True}
        }
        bytes1 = canonical_json_bytes(obj)
        parsed = json.loads(bytes1.decode('utf-8'))
        bytes2 = canonical_json_bytes(parsed)
        assert bytes1 == bytes2


# ============================================================================
# TEST: FLOAT CONVERSION HELPERS
# ============================================================================

class TestFloatConversionHelpers:
    """Helper functions for float-to-string conversion."""

    def test_float_to_string_basic(self):
        """Basic float conversion."""
        assert float_to_canonical_string(0.95) == "0.95"
        assert float_to_canonical_string(1.0) == "1.0"
        assert float_to_canonical_string(0.0) == "0.0"

    def test_float_to_string_precision(self):
        """Precision respected."""
        assert float_to_canonical_string(0.123456789, precision=4) == "0.1235"
        assert float_to_canonical_string(0.1, precision=6) == "0.1"

    def test_float_to_string_trailing_zeros(self):
        """Trailing zeros stripped except one after decimal."""
        assert float_to_canonical_string(1.0) == "1.0"
        assert float_to_canonical_string(1.5000) == "1.5"

    def test_confidence_to_string(self):
        """Confidence conversion."""
        assert confidence_to_string(0.95) == "0.95"
        assert confidence_to_string(1.0) == "1.0"
        assert confidence_to_string(0.0) == "0.0"
        assert confidence_to_string(0.9999) == "0.9999"

    def test_confidence_validation(self):
        """Confidence must be 0.0-1.0."""
        with pytest.raises(ValueError):
            confidence_to_string(1.5)
        with pytest.raises(ValueError):
            confidence_to_string(-0.1)

    def test_score_to_string(self):
        """Score conversion with 6 decimal places."""
        assert score_to_string(0.5) == "0.5"
        assert score_to_string(0.123456) == "0.123456"


# ============================================================================
# TEST: CELL TO CANONICAL DICT
# ============================================================================

class TestCellToCanonicalDict:
    """cell_to_canonical_dict produces correct structure."""

    @pytest.fixture
    def sample_cell(self):
        """Create sample DecisionCell."""
        return DecisionCell(
            header=Header(
                version="1.3",
                graph_id="graph:test-123",
                cell_type=CellType.FACT,
                system_time="2026-01-28T12:00:00.000Z",
                prev_cell_hash="a" * 64,
            ),
            fact=Fact(
                namespace="test.ns",
                subject="subj",
                predicate="pred",
                object="obj",
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED,
                valid_from="2026-01-01T00:00:00.000Z",
                valid_to=None,
            ),
            logic_anchor=LogicAnchor(
                rule_id="rule-1",
                rule_logic_hash="b" * 64,
                interpreter="datalog:v2",
            ),
            evidence=[
                Evidence(
                    type="document_blob",
                    cid="sha256:abc",
                    source="test",
                    payload_hash=None,
                    description="Test evidence",
                )
            ],
            proof=Proof(
                signer_id="signer-1",
                signer_key_id="key-1",
                signature="sig-placeholder",
                merkle_root="merkle-placeholder",
                signature_required=True,
            ),
        )

    def test_canonical_dict_structure(self, sample_cell):
        """Canonical dict has correct structure."""
        result = cell_to_canonical_dict(sample_cell)

        assert "header" in result
        assert "fact" in result
        assert "logic_anchor" in result
        assert "evidence" in result
        assert "proof" in result

    def test_cell_id_excluded(self, sample_cell):
        """cell_id is not in canonical dict."""
        result = cell_to_canonical_dict(sample_cell)
        assert "cell_id" not in result

    def test_confidence_is_string(self, sample_cell):
        """Confidence converted to string."""
        result = cell_to_canonical_dict(sample_cell)
        assert result["fact"]["confidence"] == "0.95"
        assert isinstance(result["fact"]["confidence"], str)

    def test_signature_excluded(self, sample_cell):
        """Signature and merkle_root excluded from proof."""
        result = cell_to_canonical_dict(sample_cell)
        assert "signature" not in result["proof"]
        assert "merkle_root" not in result["proof"]

    def test_signature_required_included(self, sample_cell):
        """signature_required is included."""
        result = cell_to_canonical_dict(sample_cell)
        assert result["proof"]["signature_required"] is True

    def test_enum_values_as_strings(self, sample_cell):
        """Enum values converted to strings."""
        result = cell_to_canonical_dict(sample_cell)
        assert result["header"]["cell_type"] == "fact"
        assert result["fact"]["source_quality"] == "verified"

    def test_canonical_dict_encodes_without_error(self, sample_cell):
        """Canonical dict can be encoded to bytes."""
        result = cell_to_canonical_dict(sample_cell)
        # Should not raise FloatNotAllowedError
        bytes_result = canonical_json_bytes(result)
        assert len(bytes_result) > 0

    def test_canonical_dict_deterministic(self, sample_cell):
        """Same cell produces identical canonical bytes."""
        dict1 = cell_to_canonical_dict(sample_cell)
        dict2 = cell_to_canonical_dict(sample_cell)
        bytes1 = canonical_json_bytes(dict1)
        bytes2 = canonical_json_bytes(dict2)
        assert bytes1 == bytes2


# ============================================================================
# TEST: RFA TO CANONICAL DICT
# ============================================================================

class TestRfaToCanonicalDict:
    """rfa_to_canonical_dict converts floats to strings."""

    def test_float_converted(self):
        """Float values converted to strings."""
        rfa = {"confidence": 0.95, "name": "test"}
        result = rfa_to_canonical_dict(rfa)
        assert result["confidence"] == "0.95"
        assert result["name"] == "test"

    def test_nested_float_converted(self):
        """Nested floats converted."""
        rfa = {"data": {"score": 0.5}}
        result = rfa_to_canonical_dict(rfa)
        assert result["data"]["score"] == "0.5"

    def test_float_in_list_converted(self):
        """Floats in lists converted."""
        rfa = {"values": [0.1, 0.2, 0.3]}
        result = rfa_to_canonical_dict(rfa)
        assert result["values"] == ["0.1", "0.2", "0.3"]

    def test_rfa_encodes_after_conversion(self):
        """Converted RFA can be encoded."""
        rfa = {"confidence": 0.95, "score": 1.5}
        result = rfa_to_canonical_dict(rfa)
        # Should not raise
        bytes_result = canonical_json_bytes(result)
        assert len(bytes_result) > 0


# ============================================================================
# TEST: CANONICAL HASH
# ============================================================================

class TestCanonicalHash:
    """canonical_hash produces consistent SHA-256."""

    def test_hash_format(self):
        """Hash is 64 hex characters."""
        result = canonical_hash({"key": "value"})
        assert len(result) == 64
        assert all(c in '0123456789abcdef' for c in result)

    def test_hash_deterministic(self):
        """Same input produces same hash."""
        obj = {"a": 1, "b": 2}
        hash1 = canonical_hash(obj)
        hash2 = canonical_hash(obj)
        assert hash1 == hash2

    def test_hash_changes_with_content(self):
        """Different content produces different hash."""
        hash1 = canonical_hash({"a": 1})
        hash2 = canonical_hash({"a": 2})
        assert hash1 != hash2

    def test_hash_independent_of_key_order(self):
        """Key order in input doesn't affect hash (keys are sorted)."""
        # Python dicts maintain insertion order, but our canonicalization sorts
        hash1 = canonical_hash({"a": 1, "b": 2})
        hash2 = canonical_hash({"b": 2, "a": 1})
        assert hash1 == hash2


# ============================================================================
# TEST: EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Edge cases and error handling."""

    def test_non_string_dict_key_rejected(self):
        """Dict keys must be strings."""
        with pytest.raises(CanonicalEncodingError) as exc_info:
            canonical_json_bytes({1: "value"})
        assert "string" in str(exc_info.value).lower()

    def test_unsupported_type_rejected(self):
        """Unsupported types raise error."""
        with pytest.raises(CanonicalEncodingError):
            canonical_json_bytes({"date": object()})

    def test_enum_with_value(self):
        """Enums encoded via .value attribute."""
        result = canonical_json_string({"type": CellType.FACT})
        assert '"type":"fact"' in result

    def test_very_deep_nesting(self):
        """Deep nesting handled (within recursion limits)."""
        obj = {"a": {"b": {"c": {"d": {"e": 1}}}}}
        result = canonical_json_bytes(obj)
        assert b'"e":1' in result

    def test_empty_evidence_list(self):
        """Empty evidence list encoded as []."""
        result = canonical_json_string({"evidence": []})
        assert '"evidence":[]' in result


# ============================================================================
# TEST: UTF-8 BYTES OUTPUT
# ============================================================================

class TestUtf8Output:
    """Output is valid UTF-8."""

    def test_output_is_bytes(self):
        """canonical_json_bytes returns bytes."""
        result = canonical_json_bytes({"key": "value"})
        assert isinstance(result, bytes)

    def test_output_is_valid_utf8(self):
        """Output can be decoded as UTF-8."""
        result = canonical_json_bytes({"key": "\u00e9"})
        decoded = result.decode('utf-8')
        assert isinstance(decoded, str)

    def test_unicode_in_output(self):
        """Unicode characters preserved in output."""
        result = canonical_json_bytes({"key": "\u00e9\u00e8"})
        decoded = result.decode('utf-8')
        assert '\u00e9' in decoded
        assert '\u00e8' in decoded


# ============================================================================
# TEST: CONFIDENCE FORMATTING TABLE (LOCKED CONTRACT)
# ============================================================================

class TestConfidenceFormattingTable:
    """
    LOCKED CONTRACT: These tests define the canonical confidence format.

    DO NOT CHANGE these expected values without a migration plan.
    Any change affects all existing cell_id hashes in canonical mode.

    Format rules:
    1. Always includes decimal point (never "1" or "0")
    2. At least one digit after decimal (1.0 not 1.)
    3. Trailing zeros stripped beyond the minimum (0.95 not 0.9500)
    4. Max 4 decimal places for confidence (precision=4)
    5. Rounding applies at precision boundary
    """

    @pytest.mark.parametrize("value,expected", [
        # Boundary values - CRITICAL
        (0.0, "0.0"),
        (1.0, "1.0"),

        # Common confidence values
        (0.5, "0.5"),
        (0.95, "0.95"),
        (0.9, "0.9"),
        (0.99, "0.99"),
        (0.999, "0.999"),
        (0.9999, "0.9999"),

        # Low confidence values
        (0.1, "0.1"),
        (0.01, "0.01"),
        (0.001, "0.001"),
        (0.0001, "0.0001"),

        # Values that require rounding (precision=4)
        # Note: Python uses IEEE 754 float representation. Rounding behavior
        # depends on exact binary representation, which may differ from decimal intuition.
        # The key guarantee: DETERMINISTIC - same input always produces same output.
        (0.33333, "0.3333"),      # Truncated at 4 decimals
        (0.99999, "1.0"),         # Rounds up to 1.0
        (0.00001, "0.0"),         # Rounds down to 0.0
        (0.12345, "0.1235"),      # Rounds up (float representation slightly > 0.123445)
        (0.55555, "0.5555"),      # Rounds down (float representation slightly < 0.555555)
        (0.55565, "0.5556"),      # Rounds down (float representation effect)

        # Typical business values
        (0.75, "0.75"),
        (0.25, "0.25"),
        (0.85, "0.85"),
        (0.65, "0.65"),
    ])
    def test_confidence_formatting_table(self, value: float, expected: str):
        """
        LOCKED: confidence_to_string canonical format.

        This test locks down the string representation of confidence values.
        These formats are part of the cell_id hash computation in canonical mode.
        """
        assert confidence_to_string(value) == expected

    def test_confidence_format_never_omits_decimal(self):
        """Confidence always has decimal point."""
        for value in [0.0, 0.5, 1.0]:
            result = confidence_to_string(value)
            assert '.' in result, f"{value} → {result} missing decimal"

    def test_confidence_format_no_scientific_notation(self):
        """Confidence never uses scientific notation."""
        for value in [0.0001, 0.00001]:
            # Note: 0.00001 rounds to 0.0 at precision=4, but should not be "1e-05"
            result = confidence_to_string(value) if 0.0 <= value <= 1.0 else None
            if result:
                assert 'e' not in result.lower(), f"{value} → {result} has scientific notation"

    def test_confidence_format_no_leading_zeros_except_fractional(self):
        """No leading zeros except for 0.X format."""
        result = confidence_to_string(0.5)
        assert result == "0.5"
        assert not result.startswith("00")


class TestScoreFormattingTable:
    """
    LOCKED CONTRACT: score_to_string format (6 decimal places).

    Used for score_delta and similar fields that need more precision.
    """

    @pytest.mark.parametrize("value,expected", [
        # Boundaries
        (0.0, "0.0"),
        (1.0, "1.0"),

        # High precision values
        (0.123456, "0.123456"),
        (0.1234567, "0.123457"),  # Rounds at 6th decimal
        (0.000001, "0.000001"),
        (0.0000001, "0.0"),       # Rounds to zero

        # Negative values (scores can be negative)
        (-0.5, "-0.5"),
        (-0.123456, "-0.123456"),

        # Large values
        (100.5, "100.5"),
        (999.999999, "999.999999"),
    ])
    def test_score_formatting_table(self, value: float, expected: str):
        """LOCKED: score_to_string canonical format."""
        assert score_to_string(value) == expected


class TestFloatFormattingConsistency:
    """Test that formatting is consistent across the codebase."""

    def test_cell_confidence_uses_canonical_format(self):
        """cell_to_canonical_dict uses confidence_to_string."""
        cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id="graph:test",
                cell_type=CellType.FACT,
                system_time="2026-01-28T12:00:00.000Z",
                prev_cell_hash="a" * 64,
            ),
            fact=Fact(
                namespace="test.ns",
                subject="s",
                predicate="p",
                object="o",
                confidence=0.333333,  # Will be formatted
                source_quality=SourceQuality.VERIFIED,
                valid_from="2026-01-01T00:00:00.000Z",
                valid_to=None,
            ),
            logic_anchor=LogicAnchor(
                rule_id="r1",
                rule_logic_hash="b" * 64,
                interpreter="datalog:v2",
            ),
            evidence=[],
            proof=Proof(
                signer_id="s1",
                signer_key_id="k1",
                signature=None,
                merkle_root=None,
                signature_required=False,
            ),
        )

        canonical_dict = cell_to_canonical_dict(cell)
        assert canonical_dict["fact"]["confidence"] == "0.3333"  # Locked format

    def test_same_confidence_same_bytes(self):
        """Same confidence value produces identical canonical bytes."""
        confidence = 0.95

        # Create two cells with same confidence
        def make_cell(conf: float) -> DecisionCell:
            return DecisionCell(
                header=Header(
                    version="1.3",
                    graph_id="graph:test",
                    cell_type=CellType.FACT,
                    system_time="2026-01-28T12:00:00.000Z",
                    prev_cell_hash="a" * 64,
                ),
                fact=Fact(
                    namespace="test.ns",
                    subject="s",
                    predicate="p",
                    object="o",
                    confidence=conf,
                    source_quality=SourceQuality.VERIFIED,
                    valid_from="2026-01-01T00:00:00.000Z",
                    valid_to=None,
                ),
                logic_anchor=LogicAnchor(
                    rule_id="r1",
                    rule_logic_hash="b" * 64,
                    interpreter="datalog:v2",
                ),
                evidence=[],
                proof=Proof(
                    signer_id="s1",
                    signer_key_id="k1",
                    signature=None,
                    merkle_root=None,
                    signature_required=False,
                ),
            )

        cell1 = make_cell(confidence)
        cell2 = make_cell(confidence)

        bytes1 = canonical_json_bytes(cell_to_canonical_dict(cell1))
        bytes2 = canonical_json_bytes(cell_to_canonical_dict(cell2))

        assert bytes1 == bytes2

    def test_different_but_equivalent_floats_same_format(self):
        """Floats that round to same value produce same string."""
        # These should all round to "0.95" at 4 decimal precision
        values = [0.95, 0.9500, 0.95000, 0.9499999999]
        results = [confidence_to_string(v) for v in values]
        assert all(r == "0.95" for r in results), f"Got different results: {results}"


# ============================================================================
# TEST: EVIDENCE ORDERING (LOCKED CONTRACT)
# ============================================================================

class TestEvidenceOrdering:
    """
    LOCKED CONTRACT: Evidence ordering for canonical representation.

    DO NOT CHANGE the sort key without a migration plan.
    Any change affects all existing cell_id hashes in canonical mode
    for cells with multiple evidence items.

    Sort order: (type, cid, source, payload_hash, description)
    None values sort before non-None (represented as empty string).
    """

    def test_evidence_sort_key_basic(self):
        """evidence_sort_key returns correct tuple."""
        e = Evidence(
            type="document_blob",
            cid="sha256:abc",
            source="test-source",
            payload_hash="def123",
            description="Test evidence",
        )
        key = evidence_sort_key(e)
        assert key == ("document_blob", "sha256:abc", "test-source", "def123", "Test evidence")

    def test_evidence_sort_key_none_values(self):
        """None values become empty strings in sort key."""
        e = Evidence(
            type="approval",
            cid=None,
            source=None,
            payload_hash=None,
            description=None,
        )
        key = evidence_sort_key(e)
        assert key == ("approval", "", "", "", "")

    def test_evidence_sorted_by_type_first(self):
        """Evidence sorted by type as primary key."""
        e1 = Evidence(type="approval", cid="cid1", source=None)
        e2 = Evidence(type="document_blob", cid="cid2", source=None)
        e3 = Evidence(type="api_response", cid="cid3", source=None)

        sorted_evidence = sorted([e1, e2, e3], key=evidence_sort_key)
        types = [e.type for e in sorted_evidence]
        assert types == ["api_response", "approval", "document_blob"]

    def test_evidence_sorted_by_cid_second(self):
        """Same type sorts by cid."""
        e1 = Evidence(type="document_blob", cid="z-cid", source=None)
        e2 = Evidence(type="document_blob", cid="a-cid", source=None)
        e3 = Evidence(type="document_blob", cid=None, source=None)

        sorted_evidence = sorted([e1, e2, e3], key=evidence_sort_key)
        cids = [e.cid for e in sorted_evidence]
        # None ("") sorts before "a-cid" and "z-cid"
        assert cids == [None, "a-cid", "z-cid"]

    def test_evidence_sorted_by_source_third(self):
        """Same type+cid sorts by source."""
        e1 = Evidence(type="approval", cid="cid1", source="zenith")
        e2 = Evidence(type="approval", cid="cid1", source="alpha")
        e3 = Evidence(type="approval", cid="cid1", source=None)

        sorted_evidence = sorted([e1, e2, e3], key=evidence_sort_key)
        sources = [e.source for e in sorted_evidence]
        assert sources == [None, "alpha", "zenith"]

    def test_cell_canonical_dict_sorts_evidence(self):
        """cell_to_canonical_dict sorts evidence deterministically."""
        # Create evidence in reverse order
        evidence_list = [
            Evidence(type="document_blob", cid="cid-z", source="src1"),
            Evidence(type="api_response", cid="cid-y", source="src2"),
            Evidence(type="approval", cid="cid-x", source="src3"),
        ]

        cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id="graph:test",
                cell_type=CellType.FACT,
                system_time="2026-01-28T12:00:00.000Z",
                prev_cell_hash="a" * 64,
            ),
            fact=Fact(
                namespace="test.ns",
                subject="s",
                predicate="p",
                object="o",
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED,
                valid_from="2026-01-01T00:00:00.000Z",
                valid_to=None,
            ),
            logic_anchor=LogicAnchor(
                rule_id="r1",
                rule_logic_hash="b" * 64,
                interpreter="datalog:v2",
            ),
            evidence=evidence_list,  # Unsorted order
            proof=Proof(
                signer_id="s1",
                signer_key_id="k1",
                signature=None,
                merkle_root=None,
                signature_required=False,
            ),
        )

        canonical_dict = cell_to_canonical_dict(cell)
        evidence_types = [e["type"] for e in canonical_dict["evidence"]]

        # Should be sorted: api_response < approval < document_blob
        assert evidence_types == ["api_response", "approval", "document_blob"]

    def test_evidence_order_affects_canonical_bytes(self):
        """Different evidence order in input produces same canonical bytes."""
        evidence_a = Evidence(type="approval", cid="cid1", source="src1")
        evidence_b = Evidence(type="document_blob", cid="cid2", source="src2")

        def make_cell(evidence_list):
            return DecisionCell(
                header=Header(
                    version="1.3",
                    graph_id="graph:test",
                    cell_type=CellType.FACT,
                    system_time="2026-01-28T12:00:00.000Z",
                    prev_cell_hash="a" * 64,
                ),
                fact=Fact(
                    namespace="test.ns",
                    subject="s",
                    predicate="p",
                    object="o",
                    confidence=0.95,
                    source_quality=SourceQuality.VERIFIED,
                    valid_from="2026-01-01T00:00:00.000Z",
                    valid_to=None,
                ),
                logic_anchor=LogicAnchor(
                    rule_id="r1",
                    rule_logic_hash="b" * 64,
                    interpreter="datalog:v2",
                ),
                evidence=evidence_list,
                proof=Proof(
                    signer_id="s1",
                    signer_key_id="k1",
                    signature=None,
                    merkle_root=None,
                    signature_required=False,
                ),
            )

        # Same evidence, different input order
        cell1 = make_cell([evidence_a, evidence_b])
        cell2 = make_cell([evidence_b, evidence_a])

        bytes1 = canonical_json_bytes(cell_to_canonical_dict(cell1))
        bytes2 = canonical_json_bytes(cell_to_canonical_dict(cell2))

        # CRITICAL: Same canonical bytes regardless of input order
        assert bytes1 == bytes2

    def test_empty_evidence_list(self):
        """Empty evidence list produces empty array."""
        cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id="graph:test",
                cell_type=CellType.FACT,
                system_time="2026-01-28T12:00:00.000Z",
                prev_cell_hash="a" * 64,
            ),
            fact=Fact(
                namespace="test.ns",
                subject="s",
                predicate="p",
                object="o",
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED,
                valid_from="2026-01-01T00:00:00.000Z",
                valid_to=None,
            ),
            logic_anchor=LogicAnchor(
                rule_id="r1",
                rule_logic_hash="b" * 64,
                interpreter="datalog:v2",
            ),
            evidence=[],  # Empty list
            proof=Proof(
                signer_id="s1",
                signer_key_id="k1",
                signature=None,
                merkle_root=None,
                signature_required=False,
            ),
        )

        canonical_dict = cell_to_canonical_dict(cell)
        assert canonical_dict["evidence"] == []

    def test_single_evidence_unchanged(self):
        """Single evidence item maintains structure."""
        evidence = Evidence(
            type="document_blob",
            cid="sha256:test",
            source="test-source",
            payload_hash="hash123",
            description="Test doc",
        )

        cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id="graph:test",
                cell_type=CellType.FACT,
                system_time="2026-01-28T12:00:00.000Z",
                prev_cell_hash="a" * 64,
            ),
            fact=Fact(
                namespace="test.ns",
                subject="s",
                predicate="p",
                object="o",
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED,
                valid_from="2026-01-01T00:00:00.000Z",
                valid_to=None,
            ),
            logic_anchor=LogicAnchor(
                rule_id="r1",
                rule_logic_hash="b" * 64,
                interpreter="datalog:v2",
            ),
            evidence=[evidence],
            proof=Proof(
                signer_id="s1",
                signer_key_id="k1",
                signature=None,
                merkle_root=None,
                signature_required=False,
            ),
        )

        canonical_dict = cell_to_canonical_dict(cell)
        assert len(canonical_dict["evidence"]) == 1
        assert canonical_dict["evidence"][0]["type"] == "document_blob"
        assert canonical_dict["evidence"][0]["cid"] == "sha256:test"

    def test_duplicate_evidence_preserved(self):
        """Duplicate evidence items are preserved (not deduplicated)."""
        evidence = Evidence(type="approval", cid="cid1", source="src1")

        cell = DecisionCell(
            header=Header(
                version="1.3",
                graph_id="graph:test",
                cell_type=CellType.FACT,
                system_time="2026-01-28T12:00:00.000Z",
                prev_cell_hash="a" * 64,
            ),
            fact=Fact(
                namespace="test.ns",
                subject="s",
                predicate="p",
                object="o",
                confidence=0.95,
                source_quality=SourceQuality.VERIFIED,
                valid_from="2026-01-01T00:00:00.000Z",
                valid_to=None,
            ),
            logic_anchor=LogicAnchor(
                rule_id="r1",
                rule_logic_hash="b" * 64,
                interpreter="datalog:v2",
            ),
            evidence=[evidence, evidence, evidence],  # Same evidence 3 times
            proof=Proof(
                signer_id="s1",
                signer_key_id="k1",
                signature=None,
                merkle_root=None,
                signature_required=False,
            ),
        )

        canonical_dict = cell_to_canonical_dict(cell)
        # Duplicates preserved (not our job to deduplicate)
        assert len(canonical_dict["evidence"]) == 3
