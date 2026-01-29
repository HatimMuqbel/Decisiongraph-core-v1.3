"""
DecisionGraph Input Validation Module (v1.4)

Provides input validation functions for the RFA (Request-For-Access) layer.
All validation happens at entry points before data reaches the core engine.

Requirements implemented:
- VAL-01: Subject validation (type:identifier format, lowercase, max 128 chars after colon)
- VAL-02: Predicate validation (snake_case, max 64 chars)
- VAL-03: Object length validation (max 4096 chars)
- VAL-04: Control character rejection (0x00-0x08, 0x0B-0x1F blocked; tab/newline allowed)

All validation failures raise InputInvalidError with:
- Error code: DG_INPUT_INVALID
- Actionable message: Describes what's wrong and expected format
- Details dict: Field name, truncated value, pattern/constraint info
"""

import re
from typing import Optional

from .exceptions import InputInvalidError

__all__ = [
    # Constants
    'SUBJECT_PATTERN',
    'PREDICATE_PATTERN',
    'CONTROL_CHARS_PATTERN',
    'MAX_OBJECT_LENGTH',
    # Functions
    'contains_control_chars',
    'validate_subject_field',
    'validate_predicate_field',
    'validate_object_field',
]

# =============================================================================
# PRE-COMPILED REGEX PATTERNS (module-level for performance)
# =============================================================================

# VAL-01: Subject format - type:identifier
# - Type: lowercase letters and underscores only
# - Identifier: lowercase letters, digits, underscores, dots, slashes, hyphens (1-128 chars)
SUBJECT_PATTERN = re.compile(r'^[a-z_]+:[a-z0-9_./-]{1,128}$')

# VAL-02: Predicate format - snake_case identifier
# - Starts with lowercase letter or underscore
# - Contains only lowercase letters, digits, and underscores
# - Max 64 characters
PREDICATE_PATTERN = re.compile(r'^[a-z_][a-z0-9_]{0,63}$')

# VAL-04: Control characters to reject
# - 0x00-0x08: NUL through BACKSPACE
# - 0x0B-0x1F: VERTICAL TAB through UNIT SEPARATOR
# - Excludes 0x09 (TAB) and 0x0A (NEWLINE) which are allowed
CONTROL_CHARS_PATTERN = re.compile(r'[\x00-\x08\x0B-\x1F]')

# VAL-03: Maximum object length
MAX_OBJECT_LENGTH = 4096


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def contains_control_chars(text: str) -> bool:
    """
    Check if text contains disallowed control characters.

    Disallowed characters: 0x00-0x08, 0x0B-0x1F
    Allowed special characters: TAB (0x09), NEWLINE (0x0A)

    Args:
        text: String to check for control characters

    Returns:
        True if text contains any disallowed control characters, False otherwise
    """
    return CONTROL_CHARS_PATTERN.search(text) is not None


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_subject_field(subject: str, field_name: str = "subject") -> None:
    """
    Validate a subject field against VAL-01 requirements.

    Subject format: type:identifier
    - Type: lowercase letters and underscores only (e.g., 'user', 'resource', 'entity_type')
    - Identifier: lowercase letters, digits, underscores, dots, slashes, hyphens (1-128 chars)

    Valid examples: 'user:alice', 'resource:doc/readme', 'entity_type:id_123'
    Invalid examples: 'USER:alice', 'user:Alice', 'user:', ':id', 'nocolon'

    Args:
        subject: The subject string to validate
        field_name: Name of the field for error messages (default: "subject")

    Raises:
        InputInvalidError: If validation fails, with actionable message and details
    """
    # Check for empty string
    if not subject:
        raise InputInvalidError(
            message=f"Invalid {field_name}: cannot be empty. "
                    f"Expected format: 'type:identifier' (e.g., 'user:alice')",
            details={
                "field": field_name,
                "value": "",
                "constraint": "non-empty",
                "pattern": "^[a-z_]+:[a-z0-9_./-]{1,128}$",
            }
        )

    # Check for control characters (security: reject before pattern matching)
    if contains_control_chars(subject):
        raise InputInvalidError(
            message=f"Invalid {field_name}: contains disallowed control characters. "
                    f"Control characters (0x00-0x08, 0x0B-0x1F) are not permitted.",
            details={
                "field": field_name,
                "value": subject[:100],  # Truncate for safety
                "constraint": "no control characters",
            }
        )

    # Check against pattern using fullmatch() for complete string match
    if not SUBJECT_PATTERN.fullmatch(subject):
        raise InputInvalidError(
            message=f"Invalid {field_name}: '{subject[:50]}' does not match required format. "
                    f"Expected: 'type:identifier' where type is lowercase letters/underscores, "
                    f"identifier is lowercase alphanumeric/underscores/dots/slashes/hyphens (1-128 chars). "
                    f"Example: 'user:alice_123'",
            details={
                "field": field_name,
                "value": subject[:100],
                "pattern": "^[a-z_]+:[a-z0-9_./-]{1,128}$",
                "constraint": "type:identifier format, lowercase only",
            }
        )


def validate_predicate_field(predicate: str, field_name: str = "predicate") -> None:
    """
    Validate a predicate field against VAL-02 requirements.

    Predicate format: snake_case identifier
    - Starts with lowercase letter or underscore
    - Contains only lowercase letters, digits, and underscores
    - Maximum 64 characters

    Valid examples: 'can_access', 'has_permission', 'is_admin', '_private'
    Invalid examples: 'CAN_ACCESS', 'can-access', 'can access', '123read'

    Args:
        predicate: The predicate string to validate
        field_name: Name of the field for error messages (default: "predicate")

    Raises:
        InputInvalidError: If validation fails, with actionable message and details
    """
    # Check for empty string
    if not predicate:
        raise InputInvalidError(
            message=f"Invalid {field_name}: cannot be empty. "
                    f"Expected format: snake_case identifier (e.g., 'can_access')",
            details={
                "field": field_name,
                "value": "",
                "constraint": "non-empty",
                "pattern": "^[a-z_][a-z0-9_]{0,63}$",
            }
        )

    # Check for control characters
    if contains_control_chars(predicate):
        raise InputInvalidError(
            message=f"Invalid {field_name}: contains disallowed control characters. "
                    f"Control characters (0x00-0x08, 0x0B-0x1F) are not permitted.",
            details={
                "field": field_name,
                "value": predicate[:100],
                "constraint": "no control characters",
            }
        )

    # Check against pattern
    if not PREDICATE_PATTERN.fullmatch(predicate):
        raise InputInvalidError(
            message=f"Invalid {field_name}: '{predicate[:50]}' does not match required format. "
                    f"Expected: snake_case identifier (lowercase letters, digits, underscores). "
                    f"Must start with letter or underscore, max 64 chars. "
                    f"Example: 'can_access'",
            details={
                "field": field_name,
                "value": predicate[:100],
                "pattern": "^[a-z_][a-z0-9_]{0,63}$",
                "constraint": "snake_case, max 64 chars",
            }
        )


def validate_object_field(obj: str, field_name: str = "object") -> None:
    """
    Validate an object field against VAL-03 and VAL-04 requirements.

    Object validation:
    - Cannot be empty
    - Maximum 4096 characters (checked FIRST for security - prevent huge input processing)
    - No control characters (except TAB and NEWLINE which are allowed)

    Valid examples: 'user:alice', '{"type": "amount", "value": 100}', 'plain string'
    Invalid examples: '', 'x' * 4097, 'value\\x00here'

    Args:
        obj: The object string to validate
        field_name: Name of the field for error messages (default: "object")

    Raises:
        InputInvalidError: If validation fails, with actionable message and details
    """
    # Check for empty string
    if not obj:
        raise InputInvalidError(
            message=f"Invalid {field_name}: cannot be empty. "
                    f"Expected: typed ID, JSON value, or plain string (max 4096 chars)",
            details={
                "field": field_name,
                "value": "",
                "constraint": "non-empty",
                "max_length": MAX_OBJECT_LENGTH,
            }
        )

    # Check length FIRST (security: prevent processing huge inputs)
    if len(obj) > MAX_OBJECT_LENGTH:
        raise InputInvalidError(
            message=f"Invalid {field_name}: exceeds maximum length of {MAX_OBJECT_LENGTH} characters. "
                    f"Actual length: {len(obj)} characters.",
            details={
                "field": field_name,
                "value": obj[:100],  # Truncate for safety
                "actual_length": len(obj),
                "max_length": MAX_OBJECT_LENGTH,
                "constraint": f"max {MAX_OBJECT_LENGTH} characters",
            }
        )

    # Check for control characters
    if contains_control_chars(obj):
        raise InputInvalidError(
            message=f"Invalid {field_name}: contains disallowed control characters. "
                    f"Control characters (0x00-0x08, 0x0B-0x1F) are not permitted. "
                    f"Note: TAB and NEWLINE are allowed.",
            details={
                "field": field_name,
                "value": obj[:100],
                "constraint": "no control characters (except TAB/NEWLINE)",
            }
        )
