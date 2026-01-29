"""
DecisionGraph Exception Hierarchy (v1.4)

Provides domain-specific error codes for external developers integrating with DecisionGraph.
Every failure returns a deterministic, actionable error code.

Error Codes:
- DG_SCHEMA_INVALID: Schema validation failed (missing fields, wrong types)
- DG_INPUT_INVALID: Input validation failed (bad format, out of bounds)
- DG_UNAUTHORIZED: Access denied (no permission, no bridge)
- DG_INTEGRITY_FAIL: Integrity check failed (hash mismatch, chain break)
- DG_SIGNATURE_INVALID: Cryptographic signature invalid or missing
- DG_INTERNAL_ERROR: Unexpected internal error (catch-all)
"""

from typing import Any, Dict, Optional, TYPE_CHECKING
import json

# Forward declarations for type hints - actual imports happen after class definitions
# to avoid circular import issues (chain.py, namespace.py, genesis.py import from cell.py)
if TYPE_CHECKING:
    pass  # Type hints resolved at runtime via string annotations

__all__ = [
    # Exception classes
    'DecisionGraphError',
    'SchemaInvalidError',
    'InputInvalidError',
    'UnauthorizedError',
    'IntegrityFailError',
    'SignatureInvalidError',
    'InternalError',
    # Mapping utilities
    'EXCEPTION_MAP',
    'wrap_internal_exception',
]


class DecisionGraphError(Exception):
    """
    Base exception for all DecisionGraph errors.

    Provides a consistent interface for error handling with:
    - code: A deterministic error code (DG_*)
    - message: Human-readable error description
    - details: Additional context as a dictionary
    - request_id: Optional request identifier for tracing

    All errors can be serialized to dict or JSON for API responses.
    """

    code: str = "DG_INTERNAL_ERROR"

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> None:
        """
        Initialize a DecisionGraphError.

        Args:
            message: Human-readable error description
            details: Additional context (defaults to empty dict)
            request_id: Optional request identifier for tracing
        """
        super().__init__(message)
        self.message = message
        self.details = details if details is not None else {}
        self.request_id = request_id

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize error to a dictionary.

        Returns:
            Dictionary with code, message, details, and optionally request_id
        """
        result: Dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }
        if self.request_id is not None:
            result["request_id"] = self.request_id
        return result

    def to_json(self, indent: Optional[int] = None) -> str:
        """
        Serialize error to a JSON string.

        Args:
            indent: Optional indentation level for pretty-printing

        Returns:
            JSON string representation of the error
        """
        return json.dumps(self.to_dict(), indent=indent)

    def __str__(self) -> str:
        """Return formatted error string with code prefix."""
        return f"[{self.code}] {self.message}"

    def __repr__(self) -> str:
        """Return developer-friendly representation."""
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"details={self.details!r}, "
            f"request_id={self.request_id!r})"
        )


class SchemaInvalidError(DecisionGraphError):
    """
    Schema validation failed.

    Raised when input does not conform to expected schema:
    - Missing required fields
    - Wrong field types
    - Invalid field values according to schema constraints
    """

    code: str = "DG_SCHEMA_INVALID"


class InputInvalidError(DecisionGraphError):
    """
    Input validation failed.

    Raised when input fails business logic validation:
    - Bad format (e.g., invalid namespace pattern)
    - Out of bounds values
    - Constraint violations beyond schema
    """

    code: str = "DG_INPUT_INVALID"


class UnauthorizedError(DecisionGraphError):
    """
    Access denied.

    Raised when an operation is not permitted:
    - No permission to access namespace
    - No bridge established for cross-namespace access
    - Bridge revoked or expired
    """

    code: str = "DG_UNAUTHORIZED"


class IntegrityFailError(DecisionGraphError):
    """
    Integrity check failed.

    Raised when data integrity cannot be verified:
    - Hash mismatch (content changed)
    - Chain break (prev_hash doesn't match)
    - Graph ID mismatch
    """

    code: str = "DG_INTEGRITY_FAIL"


class SignatureInvalidError(DecisionGraphError):
    """
    Cryptographic signature invalid or missing.

    Raised when signature verification fails:
    - Missing required signature
    - Invalid signature format
    - Signature does not match content
    - Unknown or untrusted signing key
    """

    code: str = "DG_SIGNATURE_INVALID"


class InternalError(DecisionGraphError):
    """
    Unexpected internal error.

    Catch-all for errors that don't fit other categories:
    - Unexpected state
    - Implementation bugs
    - Resource exhaustion

    This is the default error code for DecisionGraphError base class.
    """

    code: str = "DG_INTERNAL_ERROR"


# =============================================================================
# EXCEPTION MAPPING
# =============================================================================

# Import internal exceptions for mapping
# These are imported here (after class definitions) to build the mapping;
# they remain the canonical exceptions used internally.
# DecisionGraphError wraps them at API boundaries.
from .chain import (
    ChainError, IntegrityViolation, ChainBreak,
    GenesisViolation, TemporalViolation, GraphIdMismatch
)
from .namespace import (
    NamespaceError, AccessDeniedError, BridgeRequiredError, BridgeApprovalError
)
from .genesis import GenesisError, GenesisValidationError

# Exception mapping: internal exceptions -> external error codes
# Used by wrap_internal_exception() at API boundaries
EXCEPTION_MAP: Dict[type, type] = {
    # Chain errors -> DG_INTEGRITY_FAIL
    IntegrityViolation: IntegrityFailError,
    ChainBreak: IntegrityFailError,
    TemporalViolation: IntegrityFailError,
    GraphIdMismatch: IntegrityFailError,

    # Genesis errors -> DG_SCHEMA_INVALID
    GenesisError: SchemaInvalidError,
    GenesisValidationError: SchemaInvalidError,
    GenesisViolation: SchemaInvalidError,

    # Namespace/access errors -> DG_UNAUTHORIZED
    AccessDeniedError: UnauthorizedError,
    BridgeRequiredError: UnauthorizedError,
    BridgeApprovalError: UnauthorizedError,

    # Base classes map to their category (fallback)
    ChainError: IntegrityFailError,
    NamespaceError: UnauthorizedError,

    # ValueError (from cell.py) -> DG_INPUT_INVALID
    ValueError: InputInvalidError,

    # TypeError -> DG_INPUT_INVALID
    TypeError: InputInvalidError,
}


def wrap_internal_exception(
    exc: Exception,
    default_message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> DecisionGraphError:
    """
    Wrap an internal exception as a DecisionGraphError.

    Automatically maps known exception types to appropriate error codes
    using EXCEPTION_MAP. Unknown exceptions map to InternalError.

    IMPORTANT: Use with exception chaining to preserve traceback:
        try:
            internal_operation()
        except SomeInternalError as e:
            raise wrap_internal_exception(e, details={...}) from e

    Args:
        exc: The internal exception to wrap
        default_message: Override message (uses str(exc) if None)
        details: Additional structured details to include
        request_id: Optional request ID for tracing

    Returns:
        Appropriate DecisionGraphError subclass instance

    Example:
        try:
            chain.append(cell)
        except IntegrityViolation as e:
            raise wrap_internal_exception(
                e,
                details={"cell_id": cell.cell_id[:16]}
            ) from e
    """
    # Find the appropriate error class
    error_class = EXCEPTION_MAP.get(type(exc), InternalError)

    # Build details dict, including original error type for debugging
    error_details = details.copy() if details else {}
    error_details["internal_error"] = type(exc).__name__

    # If the original exception has additional context, include it
    if hasattr(exc, 'failed_checks'):
        error_details["failed_checks"] = exc.failed_checks

    # Create wrapper exception
    return error_class(
        message=default_message or str(exc),
        details=error_details,
        request_id=request_id
    )
