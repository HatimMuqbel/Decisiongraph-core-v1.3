"""
Canonical JSON Serialization

Provides deterministic JSON serialization for hashing and comparison.
Based on RFC 8785 (JSON Canonicalization Scheme) principles:
- Sorted keys (lexicographic)
- No whitespace
- Consistent number formatting
- UTF-8 encoding

This ensures the same object always produces the same JSON string,
enabling reliable content hashing for AuthorityRef and other models.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID


def _default_serializer(obj: Any) -> Any:
    """
    Custom JSON serializer for non-standard types.

    Handles:
    - datetime/date: ISO 8601 format
    - UUID: string representation
    - Decimal: string (preserves precision)
    - Enum: value
    - dataclass: dict
    - set/frozenset: sorted list
    """
    if isinstance(obj, datetime):
        # ISO 8601 with Z suffix for UTC
        if obj.tzinfo is not None:
            return obj.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        return obj.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, Decimal):
        # Preserve exact decimal representation
        return str(obj)
    if isinstance(obj, Enum):
        return obj.value
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, (set, frozenset)):
        # Sort for determinism
        return sorted(obj, key=str)
    if isinstance(obj, bytes):
        # Hex encode bytes
        return obj.hex()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def canonical_json(obj: Any) -> str:
    """
    Serialize object to canonical JSON string.

    The output is deterministic: same input always produces same output.
    This is essential for content hashing and comparison.

    Args:
        obj: Any JSON-serializable object (including dataclasses)

    Returns:
        Canonical JSON string (sorted keys, no whitespace)

    Example:
        >>> canonical_json({"b": 1, "a": 2})
        '{"a":2,"b":1}'
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        default=_default_serializer,
        ensure_ascii=False,
    )


def canonical_json_bytes(obj: Any) -> bytes:
    """
    Serialize object to canonical JSON as UTF-8 bytes.

    Args:
        obj: Any JSON-serializable object

    Returns:
        UTF-8 encoded canonical JSON bytes
    """
    return canonical_json(obj).encode("utf-8")


def content_hash(obj: Any) -> str:
    """
    Compute SHA-256 hash of canonical JSON representation.

    This provides a stable, deterministic hash for any object.
    Useful for content addressing and change detection.

    Args:
        obj: Any JSON-serializable object

    Returns:
        Hex-encoded SHA-256 hash string (64 characters)

    Example:
        >>> content_hash({"type": "policy", "version": "1.0"})
        'a1b2c3d4...'
    """
    json_bytes = canonical_json_bytes(obj)
    return hashlib.sha256(json_bytes).hexdigest()


def content_hash_short(obj: Any, length: int = 12) -> str:
    """
    Compute truncated SHA-256 hash for display purposes.

    Args:
        obj: Any JSON-serializable object
        length: Number of hex characters to return (default 12)

    Returns:
        Truncated hex-encoded SHA-256 hash

    Example:
        >>> content_hash_short({"type": "policy"})
        'a1b2c3d4e5f6'
    """
    return content_hash(obj)[:length]


def text_hash(text: str) -> str:
    """
    Compute SHA-256 hash of text content.

    Used for hashing authority excerpts and policy wording.

    Args:
        text: Plain text string

    Returns:
        Hex-encoded SHA-256 hash string (64 characters)
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def text_hash_short(text: str, length: int = 12) -> str:
    """
    Compute truncated SHA-256 hash of text for display.

    Args:
        text: Plain text string
        length: Number of hex characters to return

    Returns:
        Truncated hex-encoded SHA-256 hash
    """
    return text_hash(text)[:length]
