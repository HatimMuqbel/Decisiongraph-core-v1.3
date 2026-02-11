"""
DecisionGraph Canonical JSON (RFC 8785) Module

This module implements RFC 8785 JSON Canonicalization Scheme (JCS) for
deterministic byte representation across all runtimes and platforms.

CRITICAL: This is the "byte physics" law for DecisionGraph.
All signing, hashing, and persistence MUST use these functions.

RFC 8785 Requirements:
1. Object keys sorted by UTF-8 byte values (lexicographic)
2. No whitespace between tokens
3. Numbers: specific formatting rules (no floats allowed in our impl)
4. Strings: minimal escaping (only required chars)
5. Unicode: literal UTF-8 (no unnecessary \\uXXXX escapes)

DecisionGraph Policy:
- NO FLOATS in canonical payloads (use string-encoded decimals)
- Timestamps as ISO 8601 strings
- All numeric values as int or string-encoded decimal

Usage:
    from decisiongraph.canon import canonical_json_bytes, validate_canonical_safe

    # Validate before serialization
    validate_canonical_safe(my_dict)

    # Get canonical bytes for hashing/signing
    cell_bytes = canonical_json_bytes(cell.to_canonical_dict())
    cell_id = hashlib.sha256(cell_bytes).hexdigest()
"""

import json
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union


class CanonicalEncodingError(Exception):
    """Raised when data cannot be canonically encoded."""
    pass


class FloatNotAllowedError(CanonicalEncodingError):
    """Raised when a float is detected in canonical payload."""
    pass


# Control characters that must be escaped (0x00-0x1F)
CONTROL_CHAR_MAP = {
    '\x00': '\\u0000', '\x01': '\\u0001', '\x02': '\\u0002', '\x03': '\\u0003',
    '\x04': '\\u0004', '\x05': '\\u0005', '\x06': '\\u0006', '\x07': '\\u0007',
    '\x08': '\\b',     '\x09': '\\t',     '\x0a': '\\n',     '\x0b': '\\u000b',
    '\x0c': '\\f',     '\x0d': '\\r',     '\x0e': '\\u000e', '\x0f': '\\u000f',
    '\x10': '\\u0010', '\x11': '\\u0011', '\x12': '\\u0012', '\x13': '\\u0013',
    '\x14': '\\u0014', '\x15': '\\u0015', '\x16': '\\u0016', '\x17': '\\u0017',
    '\x18': '\\u0018', '\x19': '\\u0019', '\x1a': '\\u001a', '\x1b': '\\u001b',
    '\x1c': '\\u001c', '\x1d': '\\u001d', '\x1e': '\\u001e', '\x1f': '\\u001f',
}

# Regex to find control characters
CONTROL_CHAR_PATTERN = re.compile(r'[\x00-\x1f]')


def _escape_string(s: str) -> str:
    """
    Escape a string per RFC 8785.

    Only escape:
    - Backslash (\\)
    - Double quote (")
    - Control characters (0x00-0x1F)

    All other Unicode is preserved as literal UTF-8.
    """
    result = []
    for char in s:
        if char == '\\':
            result.append('\\\\')
        elif char == '"':
            result.append('\\"')
        elif char in CONTROL_CHAR_MAP:
            result.append(CONTROL_CHAR_MAP[char])
        else:
            result.append(char)
    return ''.join(result)


def _encode_value(value: Any, path: str = "") -> str:
    """
    Encode a value to canonical JSON string.

    Args:
        value: The value to encode
        path: Current path for error messages (e.g., "fact.confidence")

    Returns:
        Canonical JSON string representation

    Raises:
        FloatNotAllowedError: If a float is encountered
        CanonicalEncodingError: If value cannot be encoded
    """
    if value is None:
        return 'null'

    if isinstance(value, bool):
        # Must check bool before int (bool is subclass of int in Python)
        return 'true' if value else 'false'

    if isinstance(value, int):
        # Integers are safe - no precision issues
        return str(value)

    if isinstance(value, float):
        # POLICY: No floats allowed
        raise FloatNotAllowedError(
            f"Float value {value} at path '{path}' not allowed in canonical JSON. "
            f"Use string-encoded decimal (e.g., '{value}' as string) or integer."
        )

    if isinstance(value, Decimal):
        # Decimals must be converted to string representation
        # This ensures exact representation without float precision issues
        raise CanonicalEncodingError(
            f"Decimal value {value} at path '{path}' must be converted to string "
            f"before canonical encoding. Use str({value})."
        )

    if isinstance(value, str):
        escaped = _escape_string(value)
        return f'"{escaped}"'

    if isinstance(value, (list, tuple)):
        elements = [_encode_value(item, f"{path}[{i}]") for i, item in enumerate(value)]
        return '[' + ','.join(elements) + ']'

    if isinstance(value, dict):
        # Validate all keys are strings first
        for key in value.keys():
            if not isinstance(key, str):
                raise CanonicalEncodingError(
                    f"Dictionary key must be string, got {type(key).__name__} at path '{path}'"
                )

        # RFC 8785: Sort keys by UTF-8 byte values
        # In Python, comparing strings directly uses Unicode code points,
        # which matches UTF-8 byte order for ASCII and is correct for general case
        sorted_keys = sorted(value.keys(), key=lambda k: k.encode('utf-8'))

        pairs = []
        for key in sorted_keys:
            key_path = f"{path}.{key}" if path else key
            encoded_key = f'"{_escape_string(key)}"'
            encoded_value = _encode_value(value[key], key_path)
            pairs.append(f'{encoded_key}:{encoded_value}')

        return '{' + ','.join(pairs) + '}'

    # Enum handling - use .value
    if hasattr(value, 'value'):
        return _encode_value(value.value, path)

    raise CanonicalEncodingError(
        f"Cannot canonically encode {type(value).__name__} at path '{path}'"
    )


def canonical_json_bytes(obj: Any) -> bytes:
    """
    Convert object to canonical JSON bytes per RFC 8785.

    This is THE function for all hashing and signing in DecisionGraph.
    Same input always produces identical bytes across all platforms.

    Args:
        obj: Python object (dict, list, or primitive)

    Returns:
        UTF-8 encoded bytes of canonical JSON

    Raises:
        FloatNotAllowedError: If any float values are found
        CanonicalEncodingError: If object cannot be encoded

    Example:
        >>> canonical_json_bytes({"b": 1, "a": 2})
        b'{"a":2,"b":1}'

        >>> canonical_json_bytes({"value": 1.5})  # Raises FloatNotAllowedError
    """
    json_str = _encode_value(obj)
    return json_str.encode('utf-8')


def canonical_json_string(obj: Any) -> str:
    """
    Convert object to canonical JSON string per RFC 8785.

    Convenience wrapper around canonical_json_bytes for debugging.
    For hashing/signing, use canonical_json_bytes directly.

    Args:
        obj: Python object (dict, list, or primitive)

    Returns:
        Canonical JSON string
    """
    return _encode_value(obj)


def validate_canonical_safe(obj: Any, path: str = "") -> None:
    """
    Validate that an object can be safely canonically encoded.

    Checks for:
    - No float values (must use string-encoded decimals)
    - No Decimal values (must convert to string first)
    - All dict keys are strings
    - All values are JSON-compatible types

    Args:
        obj: Object to validate
        path: Current path for error messages

    Raises:
        FloatNotAllowedError: If floats are found
        CanonicalEncodingError: If other encoding issues found
    """
    if obj is None or isinstance(obj, (bool, int, str)):
        return

    if isinstance(obj, float):
        raise FloatNotAllowedError(
            f"Float value {obj} at path '{path}' not allowed. "
            f"Convert to string or integer."
        )

    if isinstance(obj, Decimal):
        raise CanonicalEncodingError(
            f"Decimal value {obj} at path '{path}' must be converted to string."
        )

    if isinstance(obj, (list, tuple)):
        for i, item in enumerate(obj):
            validate_canonical_safe(item, f"{path}[{i}]")
        return

    if isinstance(obj, dict):
        for key, value in obj.items():
            if not isinstance(key, str):
                raise CanonicalEncodingError(
                    f"Dict key must be string, got {type(key).__name__} at path '{path}'"
                )
            key_path = f"{path}.{key}" if path else key
            validate_canonical_safe(value, key_path)
        return

    # Check for enum with .value
    if hasattr(obj, 'value'):
        validate_canonical_safe(obj.value, path)
        return

    raise CanonicalEncodingError(
        f"Unsupported type {type(obj).__name__} at path '{path}'"
    )


def float_to_canonical_string(value: float, precision: int = 6) -> str:
    """
    Convert a float to a canonical string representation.

    Use this to prepare float values before canonical encoding.
    The result is a string that can be safely included in canonical JSON.

    Args:
        value: Float value to convert
        precision: Decimal places (default 6, max meaningful for float64)

    Returns:
        String representation with consistent formatting

    Example:
        >>> float_to_canonical_string(0.95)
        "0.95"
        >>> float_to_canonical_string(1.0)
        "1.0"
        >>> float_to_canonical_string(0.123456789)
        "0.123457"  # Rounded to precision
    """
    if precision < 0 or precision > 15:
        raise ValueError("Precision must be between 0 and 15")

    # Format with specified precision, then strip trailing zeros
    # but keep at least one decimal place for clarity
    formatted = f"{value:.{precision}f}"

    # Remove trailing zeros but keep at least ".X"
    if '.' in formatted:
        formatted = formatted.rstrip('0')
        if formatted.endswith('.'):
            formatted += '0'

    return formatted


def confidence_to_string(confidence: float) -> str:
    """
    Convert confidence value (0.0-1.0) to canonical string.

    Specialized function for the common confidence field.
    Uses 4 decimal places which is sufficient for 0.0001 precision.

    Args:
        confidence: Float between 0.0 and 1.0

    Returns:
        String like "0.95", "1.0", "0.0"
    """
    if not 0.0 <= confidence <= 1.0:
        raise ValueError(f"Confidence must be 0.0-1.0, got {confidence}")
    return float_to_canonical_string(confidence, precision=4)


def score_to_string(score: float) -> str:
    """
    Convert score/delta value to canonical string.

    Specialized function for score_delta and similar fields.
    Uses 6 decimal places for fine-grained comparison.

    Args:
        score: Numeric score value

    Returns:
        String representation
    """
    return float_to_canonical_string(score, precision=6)


# ============================================================================
# EVIDENCE ORDERING
# ============================================================================

def evidence_sort_key(evidence: 'Evidence') -> tuple:
    """
    Compute deterministic sort key for Evidence.

    LOCKED CONTRACT: This sort order is part of the canonical byte representation.
    Changing it will invalidate all canonical cell_ids with multiple evidence items.

    Sort order:
    1. type (required string)
    2. cid (None sorts before strings)
    3. source (None sorts before strings)
    4. payload_hash (None sorts before strings)
    5. description (None sorts before strings)

    Returns tuple for comparison where None is represented as empty string
    to ensure consistent ordering (empty string < any non-empty string).
    """
    return (
        evidence.type,
        evidence.cid or "",
        evidence.source or "",
        evidence.payload_hash or "",
        evidence.description or "",
    )


# ============================================================================
# CANONICAL DICT BUILDERS
# ============================================================================

def cell_to_canonical_dict(cell: 'DecisionCell') -> Dict[str, Any]:
    """
    Convert a DecisionCell to canonical dict for hashing.

    This defines THE canonical representation of a cell.

    Included fields (these form the signed payload):
    - header: version, graph_id, cell_type, system_time, prev_cell_hash, hash_scheme
    - fact: namespace, subject, predicate, object, confidence*, source_quality,
            valid_from, valid_to
    - logic_anchor: rule_id, rule_logic_hash, interpreter
    - evidence: list of evidence dicts
    - proof: signer_id, signer_key_id, signature_required
            (signature and merkle_root excluded - computed separately)

    Excluded fields:
    - cell_id (it's the hash output, not input)
    - proof.signature (signed separately)
    - proof.merkle_root (computed from chain)

    *confidence is converted from float to string

    Args:
        cell: DecisionCell instance

    Returns:
        Dict safe for canonical_json_bytes()
    """
    # Import here to avoid circular dependency
    from .cell import DecisionCell

    return {
        "header": {
            "version": cell.header.version,
            "graph_id": cell.header.graph_id,
            "cell_type": cell.header.cell_type.value,
            "system_time": cell.header.system_time,
            "prev_cell_hash": cell.header.prev_cell_hash,
            "hash_scheme": cell.header.hash_scheme,  # Included even if None (canonical form)
        },
        "fact": {
            "namespace": cell.fact.namespace,
            "subject": cell.fact.subject,
            "predicate": cell.fact.predicate,
            "object": cell.fact.object,
            "confidence": confidence_to_string(cell.fact.confidence),
            "source_quality": cell.fact.source_quality.value,
            "valid_from": cell.fact.valid_from,
            "valid_to": cell.fact.valid_to,
        },
        "logic_anchor": {
            "rule_id": cell.logic_anchor.rule_id,
            "rule_logic_hash": cell.logic_anchor.rule_logic_hash,
            "interpreter": cell.logic_anchor.interpreter,
        },
        # Evidence MUST be sorted for deterministic canonical bytes
        # Sort order defined by evidence_sort_key (type, cid, source, payload_hash, description)
        "evidence": [
            {
                "type": e.type,
                "cid": e.cid,
                "source": e.source,
                "payload_hash": e.payload_hash,
                "description": e.description,
            }
            for e in sorted(cell.evidence, key=evidence_sort_key)
        ],
        "proof": {
            "signer_id": cell.proof.signer_id,
            "signer_key_id": cell.proof.signer_key_id,
            "signature_required": cell.proof.signature_required,
            # NOTE: signature and merkle_root excluded from canonical form
        },
    }


def rfa_to_canonical_dict(rfa: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert RFA dict to canonical form.

    Ensures all fields are string-safe for canonical encoding.
    Float fields are converted to strings.

    Args:
        rfa: RFA dictionary

    Returns:
        Dict safe for canonical_json_bytes()
    """
    # Deep copy to avoid mutation
    result = {}

    for key, value in rfa.items():
        if isinstance(value, float):
            result[key] = float_to_canonical_string(value)
        elif isinstance(value, dict):
            result[key] = rfa_to_canonical_dict(value)
        elif isinstance(value, list):
            result[key] = [
                rfa_to_canonical_dict(item) if isinstance(item, dict)
                else float_to_canonical_string(item) if isinstance(item, float)
                else item
                for item in value
            ]
        else:
            result[key] = value

    return result


def simulation_spec_to_canonical_dict(spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert simulation_spec to canonical form.

    Same logic as RFA - convert floats to strings recursively.
    """
    return rfa_to_canonical_dict(spec)  # Same transformation rules


# ============================================================================
# HASH HELPERS
# ============================================================================

def canonical_hash(obj: Any) -> str:
    """
    Compute SHA-256 hash of canonical JSON bytes.

    This is the standard hash function for all DecisionGraph objects.

    Args:
        obj: Object to hash

    Returns:
        64-character lowercase hex string
    """
    import hashlib
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


def compute_cell_id_canonical(cell: 'DecisionCell') -> str:
    """
    Compute cell_id using canonical JSON (RFC 8785).

    This replaces the string-concatenation approach in cell.compute_cell_id().

    Args:
        cell: DecisionCell instance

    Returns:
        64-character hex cell_id
    """
    canonical_dict = cell_to_canonical_dict(cell)
    return canonical_hash(canonical_dict)


# Export public interface
__all__ = [
    # Exceptions
    'CanonicalEncodingError',
    'FloatNotAllowedError',

    # Core functions
    'canonical_json_bytes',
    'canonical_json_string',
    'validate_canonical_safe',
    'canonical_hash',

    # Float conversion helpers
    'float_to_canonical_string',
    'confidence_to_string',
    'score_to_string',

    # Evidence ordering
    'evidence_sort_key',

    # Canonical dict builders
    'cell_to_canonical_dict',
    'rfa_to_canonical_dict',
    'simulation_spec_to_canonical_dict',

    # Cell ID computation
    'compute_cell_id_canonical',
]
