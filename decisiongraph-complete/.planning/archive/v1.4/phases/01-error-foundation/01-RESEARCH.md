# Phase 1: Error Foundation - Research

**Researched:** 2026-01-27
**Domain:** Python exception design and error handling patterns
**Confidence:** HIGH

## Summary

This research investigated Python best practices for designing a unified exception wrapper system that provides deterministic error codes to external developers. The goal is to map existing internal exceptions (ChainError, NamespaceError, GenesisError families) to 6 domain-specific codes (DG_*) while preserving traceback information and enabling JSON serialization.

The standard approach in Python is to create a base exception class with custom attributes (code, message, details) and use **exception chaining with `raise ... from e`** to preserve original tracebacks while transforming exceptions at API boundaries. This pattern is well-established in libraries like requests and frameworks like FastAPI.

**Primary recommendation:** Use inheritance-based approach where DecisionGraphError subclasses map to error codes, combined with exception chaining (`raise DecisionGraphError(...) from original_exception`) to preserve debugging context. Implement a `to_dict()` method for JSON serialization rather than relying on `__dict__` or dataclasses.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.10+ | Built-in exception system | Native exception chaining via `raise ... from`, `add_note()` method (3.11+), ExceptionGroup support |
| typing | stdlib | Type hints for exception attributes | Enables static type checking for error details structures |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | 2.x | Validation for error details | If error details need complex validation/serialization (optional, may be overkill) |
| dataclasses | stdlib | Structured error details | For typed details dictionaries (not for exception classes themselves) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Inheritance | Catch-and-wrap everywhere | More verbose, harder to maintain, but more flexible for mapping logic |
| Custom attributes | Using `.args` tuple | Less explicit, harder to access structured data |
| `to_dict()` method | `@dataclass` for exceptions | Dataclasses work but add unnecessary overhead; stdlib exceptions don't use them |

**Installation:**
```bash
# No additional packages required - stdlib only
# Optional for validation:
# pip install pydantic
```

## Architecture Patterns

### Recommended Project Structure
```
src/decisiongraph/
├── exceptions.py        # New: DecisionGraphError base + 6 code-specific subclasses
├── chain.py            # Existing: Modify to raise/chain DecisionGraphError
├── namespace.py        # Existing: Modify to raise/chain DecisionGraphError
├── genesis.py          # Existing: Modify to raise/chain DecisionGraphError
└── ...
```

### Pattern 1: Exception Hierarchy with Error Codes
**What:** Base class with code attribute, subclasses for each error code
**When to use:** When you have a fixed set of error codes (like DG_* codes)
**Example:**
```python
# Source: Python official docs + FastAPI patterns
from typing import Any, Optional, Dict

class DecisionGraphError(Exception):
    """Base exception for all DecisionGraph errors."""

    code: str = "DG_INTERNAL_ERROR"  # Default, overridden by subclasses

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ):
        self.message = message
        self.details = details or {}
        self.request_id = request_id
        super().__init__(message)  # Sets args[0]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        result = {
            "code": self.code,
            "message": self.message,
            "details": self.details
        }
        if self.request_id:
            result["request_id"] = self.request_id
        return result

class SchemaInvalidError(DecisionGraphError):
    """Raised when schema validation fails."""
    code = "DG_SCHEMA_INVALID"

class InputInvalidError(DecisionGraphError):
    """Raised when input validation fails."""
    code = "DG_INPUT_INVALID"

# ... other 4 error classes
```

### Pattern 2: Exception Chaining for Traceback Preservation
**What:** Use `raise ... from e` to preserve original exception while raising new one
**When to use:** When wrapping internal exceptions for external API consumers
**Example:**
```python
# Source: https://docs.python.org/3/tutorial/errors.html
def append(self, cell: DecisionCell) -> None:
    try:
        # ... internal validation logic
        if not cell.verify_integrity():
            raise IntegrityViolation("Cell hash mismatch")
    except IntegrityViolation as e:
        # Transform to public API exception while preserving traceback
        raise IntegrityFailError(
            message=f"Cell integrity check failed: {str(e)}",
            details={"cell_id": cell.cell_id[:16]}
        ) from e
```

### Pattern 3: Mapping Internal to External Exceptions
**What:** Centralized mapping from internal exception types to error codes
**When to use:** When you have many internal exceptions mapping to fewer external codes
**Example:**
```python
# Source: Derived from requests library pattern
# Map internal exception types to DecisionGraphError subclasses
EXCEPTION_MAP = {
    IntegrityViolation: IntegrityFailError,
    ChainBreak: IntegrityFailError,
    GenesisViolation: SchemaInvalidError,
    TemporalViolation: IntegrityFailError,
    GraphIdMismatch: IntegrityFailError,
    AccessDeniedError: UnauthorizedError,
    BridgeRequiredError: UnauthorizedError,
    BridgeApprovalError: UnauthorizedError,
    GenesisValidationError: SchemaInvalidError,
}

def map_exception(exc: Exception, **kwargs) -> DecisionGraphError:
    """Map internal exception to DecisionGraphError subclass."""
    exc_class = EXCEPTION_MAP.get(type(exc), DecisionGraphError)
    return exc_class(message=str(exc), **kwargs)
```

### Pattern 4: Details Dictionary Structure
**What:** Structured details with contextual information per error type
**When to use:** Always - provides actionable debugging information
**Example:**
```python
# Source: FastAPI error handling patterns
# For DG_INTEGRITY_FAIL
details = {
    "failed_check": "hash_mismatch",
    "cell_id": "abc123...",
    "position": 42
}

# For DG_SCHEMA_INVALID
details = {
    "validation_errors": [
        {"field": "header.version", "expected": "1.3", "got": "1.2"}
    ]
}

# For DG_UNAUTHORIZED
details = {
    "namespace": "corp.hr",
    "required_permission": "can_write",
    "requester_role": "viewer"
}

# For DG_INPUT_INVALID
details = {
    "parameter": "root_namespace",
    "value": "Corp.HR",
    "constraint": "must be lowercase, no dots"
}
```

### Anti-Patterns to Avoid
- **Using `from None` to hide internal errors:** Suppresses valuable debugging information; only use when internal details are truly irrelevant or expose security vulnerabilities
- **Using dataclasses for exception classes:** Adds overhead, not idiomatic Python; stdlib exceptions use regular classes
- **Relying on `.args` tuple:** Hard to access structured data; use explicit attributes instead
- **Multiple exception inheritance:** Python docs explicitly warn against this for exceptions due to memory layout issues
- **Raising generic `DecisionGraphError`:** Always raise specific subclass with appropriate code

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Traceback preservation | Custom traceback copying | `raise ... from e` | Built into Python 3, handles all edge cases, includes implicit chaining |
| Exception notes/context | String concatenation | `exception.add_note()` (3.11+) | Proper formatting, preserves original message, stackable |
| JSON serialization | `__dict__` or dataclasses | `to_dict()` method | Control over what's serialized, handles nested objects, more explicit |
| Error aggregation | Custom lists | `ExceptionGroup` (3.11+) | Proper traceback handling, pattern matching support |
| Structured logging | String formatting | Structured logging with exception context | Preserves exception objects, integrates with log aggregation |

**Key insight:** Python's exception system is mature and handles most complexity. The main custom work is defining the exception hierarchy and mapping logic, not the preservation/serialization mechanisms.

## Common Pitfalls

### Pitfall 1: Losing Traceback When Wrapping Exceptions
**What goes wrong:** Using `raise NewException()` without `from e` loses original traceback context
**Why it happens:** Developer forgets to chain exceptions or doesn't know about `from` syntax
**How to avoid:** Always use `raise NewException(...) from original_exception` when wrapping
**Warning signs:** External users report errors without enough context to debug; tracebacks start at the wrapper location instead of the original error site

### Pitfall 2: Putting Too Much Logic in Exception `__init__`
**What goes wrong:** Exception construction becomes a point of failure
**Why it happens:** Trying to validate or transform data during exception creation
**How to avoid:** Keep `__init__` simple - just store attributes; do transformations before raising
**Warning signs:** Exceptions raised while raising exceptions; test failures in error paths

### Pitfall 3: Mutating Exception Instances After Creation
**What goes wrong:** Exception state changes after it's raised, breaking assumptions
**Why it happens:** Trying to add context in except blocks by modifying the caught exception
**How to avoid:** Use `add_note()` (3.11+) or raise a new exception with chaining; don't mutate
**Warning signs:** Flaky tests where exception messages change between catch and assertion

### Pitfall 4: Inconsistent Details Structure
**What goes wrong:** Different error types have completely different details formats
**Why it happens:** No schema or convention for details dictionary
**How to avoid:** Define TypedDict or Pydantic models for each error code's details structure
**Warning signs:** External developers complain about unpredictable error responses; docs out of sync with reality

### Pitfall 5: Not Preserving Original Exception Type Information
**What goes wrong:** Can't distinguish between different internal errors that map to same code
**Why it happens:** Wrapper doesn't include original exception class name in details
**How to avoid:** Include `original_error` or `internal_type` in details for debugging
**Warning signs:** Support requests asking "what actually failed?" when only seeing DG_INTERNAL_ERROR

### Pitfall 6: Using `except Exception` Too Broadly
**What goes wrong:** Catching and wrapping system exceptions (KeyboardInterrupt, SystemExit)
**Why it happens:** Overly broad except clause when wrapping internal exceptions
**How to avoid:** Catch specific exception types or use `except Exception` (which excludes BaseException)
**Warning signs:** Can't Ctrl+C out of tests; system signals not working properly

## Code Examples

Verified patterns from official sources:

### Exception Chaining with Full Traceback
```python
# Source: https://docs.python.org/3/tutorial/errors.html
try:
    # Internal operation
    if cell.header.graph_id != self.graph_id:
        raise GraphIdMismatch(
            f"Cell graph_id '{cell.header.graph_id}' does not match "
            f"chain graph_id '{self.graph_id}'"
        )
except GraphIdMismatch as e:
    # Wrap for external API
    raise IntegrityFailError(
        message="Graph ID validation failed",
        details={
            "cell_graph_id": cell.header.graph_id,
            "expected_graph_id": self.graph_id,
            "internal_error": type(e).__name__
        }
    ) from e
```

### Complete Exception Class Implementation
```python
# Source: Derived from Python stdlib patterns and FastAPI
from typing import Any, Optional, Dict
import json

class DecisionGraphError(Exception):
    """
    Base exception for all DecisionGraph errors.

    All DecisionGraph exceptions include:
    - code: Machine-readable error code (DG_*)
    - message: Human-readable error message
    - details: Structured additional information
    - request_id: Optional request identifier for tracing
    """

    code: str = "DG_INTERNAL_ERROR"

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ):
        self.message = message
        self.details = details or {}
        self.request_id = request_id
        # Set args[0] for compatibility with stdlib exception handling
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize exception to JSON-compatible dictionary.

        Returns:
            Dict with code, message, details, and optional request_id
        """
        result = {
            "code": self.code,
            "message": self.message,
            "details": self.details
        }
        if self.request_id:
            result["request_id"] = self.request_id
        return result

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def __str__(self) -> str:
        """String representation showing code and message."""
        return f"[{self.code}] {self.message}"

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return (
            f"{self.__class__.__name__}("
            f"code={self.code!r}, "
            f"message={self.message!r}, "
            f"details={self.details!r})"
        )
```

### Mapping Function with Exception Chaining
```python
# Source: Derived from requests library exception pattern
def wrap_internal_exception(
    exc: Exception,
    default_message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> DecisionGraphError:
    """
    Wrap an internal exception as a DecisionGraphError.

    Automatically maps known exception types to appropriate error codes.
    Preserves original exception via chaining.

    Args:
        exc: The internal exception to wrap
        default_message: Override message (uses str(exc) if None)
        details: Additional structured details
        request_id: Optional request ID for tracing

    Returns:
        Appropriate DecisionGraphError subclass instance

    Example:
        try:
            chain.append(cell)
        except IntegrityViolation as e:
            raise wrap_internal_exception(
                e,
                details={"cell_id": cell.cell_id}
            ) from e
    """
    # Map exception type to error class
    error_class = EXCEPTION_MAP.get(type(exc), DecisionGraphError)

    # Prepare details with original error info
    error_details = details or {}
    error_details["internal_error"] = type(exc).__name__

    # Create wrapper exception
    return error_class(
        message=default_message or str(exc),
        details=error_details,
        request_id=request_id
    )
```

### Testing Exception Behavior
```python
# Source: Python unittest/pytest patterns
import pytest
import json

def test_exception_preserves_traceback():
    """Verify exception chaining preserves original traceback."""
    chain = Chain()
    chain.initialize()

    with pytest.raises(IntegrityFailError) as exc_info:
        try:
            # Internal error
            raise IntegrityViolation("Hash mismatch")
        except IntegrityViolation as e:
            # Wrap it
            raise IntegrityFailError(
                message="Integrity check failed",
                details={"reason": "hash_mismatch"}
            ) from e

    # Verify chaining
    assert exc_info.value.__cause__.__class__.__name__ == "IntegrityViolation"
    assert "Hash mismatch" in str(exc_info.value.__cause__)

def test_exception_serialization():
    """Verify exceptions serialize to expected JSON structure."""
    error = SchemaInvalidError(
        message="Invalid version",
        details={"expected": "1.3", "got": "1.2"},
        request_id="req_123"
    )

    error_dict = error.to_dict()
    assert error_dict["code"] == "DG_SCHEMA_INVALID"
    assert error_dict["message"] == "Invalid version"
    assert error_dict["details"]["expected"] == "1.3"
    assert error_dict["request_id"] == "req_123"

    # Verify JSON serialization
    error_json = error.to_json()
    parsed = json.loads(error_json)
    assert parsed == error_dict
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual traceback copy with `sys.exc_info()` | `raise ... from e` syntax | Python 3.0 (2008) | Automatic traceback chaining, simpler code |
| String concatenation for context | `exception.add_note()` | Python 3.11 (2022) | Cleaner way to augment exceptions with context |
| Multiple catch-and-wrap blocks | `ExceptionGroup` for multiple errors | Python 3.11 (2022) | Better handling of concurrent/batch failures |
| `from None` to hide details | Explicit chaining with selective details | Ongoing best practice | Better debugging while maintaining clean API |
| Dataclass exceptions | Regular classes with `to_dict()` | Never standard | Exceptions remain simple, serialization is explicit |

**Deprecated/outdated:**
- `.message` attribute on exceptions: Removed in Python 3.0; use `str(exc)` or custom attribute
- Inheriting from `BaseException` for custom exceptions: Should inherit from `Exception` unless truly system-level
- Using `args` tuple for structured data: Use explicit named attributes instead
- `raise Exception, args` syntax: Python 2 syntax; use `raise Exception(args)` in Python 3

## Open Questions

Things that couldn't be fully resolved:

1. **Should we use Python 3.11+ features like `add_note()` and `ExceptionGroup`?**
   - What we know: These are powerful features for adding context and handling multiple errors
   - What's unclear: Minimum Python version requirement for DecisionGraph; adoption timeline
   - Recommendation: Design for 3.10+ but add note in docs about 3.11+ features for enhanced error handling

2. **How granular should the details dictionary be?**
   - What we know: Should include actionable debugging information
   - What's unclear: Balance between useful details and exposing internal implementation
   - Recommendation: Start with high-level info (cell_id, position, failed_check), expand based on user feedback

3. **Should we provide helper methods on DecisionGraphError for common operations?**
   - What we know: `to_dict()` and `to_json()` are clearly needed
   - What's unclear: Whether to add `log()`, `format_for_cli()`, etc.
   - Recommendation: Start minimal (just serialization), add helpers if patterns emerge in usage

4. **How to handle signature validation errors?**
   - What we know: There's a DG_SIGNATURE_INVALID code planned
   - What's unclear: Current codebase doesn't seem to do signature validation yet
   - Recommendation: Define the error class now, map it when signature validation is implemented

5. **Should exception mapping happen at boundary or inline?**
   - What we know: Can wrap at raise site or at API boundary (e.g., function decorators)
   - What's unclear: Which leads to cleaner code for this codebase
   - Recommendation: Start with inline wrapping where exceptions are raised; if pattern is repetitive, extract to decorator

## Sources

### Primary (HIGH confidence)
- [Python 3.14 Official Tutorial - Errors and Exceptions](https://docs.python.org/3/tutorial/errors.html) - Exception chaining, custom exceptions, traceback preservation
- [Python 3.14 Built-in Exceptions](https://docs.python.org/3/library/exceptions.html) - Exception hierarchy, BaseException vs Exception
- [FastAPI Error Handling](https://fastapi.tiangolo.com/tutorial/handling-errors/) - HTTPException detail structure, JSON serialization patterns
- [Requests Library Exception Source](https://requests.readthedocs.io/en/latest/_modules/requests/exceptions/) - Real-world exception design with request/response attributes

### Secondary (MEDIUM confidence)
- [Jerry Ng - Python Exception Handling Patterns and Best Practices](https://jerrynsh.com/python-exception-handling-patterns-and-best-practices/) - Four exception patterns, when to use each
- [Real Python - Inheritance and Composition](https://realpython.com/inheritance-composition-python/) - When to use inheritance vs composition for exceptions
- [Python Official - Multiple Inheritance Warning](https://docs.python.org/3/library/exceptions.html) - Don't subclass multiple exception types
- [Medium - Why Python Dataclasses Beat Regular Classes](https://medium.com/pyzilla/python-dataclass-vs-class-advantages-c621b73955d5) - Dataclass performance and use cases
- [GeeksforGeeks - Exception Handling in Requests](https://www.geeksforgeeks.org/python/exception-handling-of-python-requests-module/) - Real-world HTTP exception patterns

### Tertiary (LOW confidence)
- [OpenStax - Multiple Inheritance and Mixin Classes](https://openstax.org/books/introduction-python-programming/pages/13-5-multiple-inheritance-and-mixin-classes) - Mixin patterns for exceptions
- [GitHub - Kombu Issue #573](https://github.com/celery/kombu/issues/573) - JSON serialization challenges with exceptions

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Based on official Python documentation and mature libraries
- Architecture: HIGH - Patterns verified in Python stdlib and popular frameworks (requests, FastAPI)
- Pitfalls: HIGH - Documented in official Python docs and battle-tested articles

**Research date:** 2026-01-27
**Valid until:** 2026-03-27 (60 days - stable domain with infrequent changes)

**Notes:**
- Exception handling in Python is a mature domain with stable best practices
- Main evolution is in Python 3.11+ features (`add_note`, `ExceptionGroup`) which are optional enhancements
- The patterns recommended here work across Python 3.8+ and will remain valid
- Codebase currently uses Python 3.10+ features (dataclasses, typing), so 3.10 is safe baseline
