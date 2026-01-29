"""
DecisionGraph Core: WitnessSet Module (v1.5)

WitnessSet defines the witness configuration for a namespace:
- Who can approve policy promotions (witnesses)
- How many approvals are needed (threshold)
- Which namespace this configuration applies to

Key properties:
- WitnessSet is immutable (frozen=True dataclass)
- Witnesses stored as tuple (deep immutability, hashable)
- Validates threshold and namespace on construction
- Reuses existing validation functions from Phase 1
- Used by WitnessRegistry for namespace-based lookups

Immutability design:
- frozen=True prevents field reassignment: ws.threshold = 2 → FrozenInstanceError
- tuple[str, ...] prevents witness list mutation: ws.witnesses.append('x') → AttributeError
- Together these ensure WitnessSet is truly immutable and hashable

Validation reuse:
- validate_threshold() from policyhead.py (Phase 1 function)
- validate_namespace() from cell.py (existing v1.3 function)
"""

from dataclasses import dataclass
from typing import Tuple

from .policyhead import validate_threshold
from .cell import validate_namespace
from .exceptions import InputInvalidError


@dataclass(frozen=True, kw_only=True)
class WitnessSet:
    """
    Immutable witness configuration for a namespace.

    WitnessSet defines who can approve policy promotions and how many
    approvals are required. This is the core configuration for the
    promotion gate mechanism in v1.5.

    Attributes:
        namespace: Target namespace (hierarchical, e.g., "corp.hr")
        witnesses: Tuple of witness identifiers (immutable)
        threshold: Number of approvals required (must be 1 <= threshold <= len(witnesses))

    Immutability:
        - frozen=True: Prevents field reassignment
        - tuple type: Prevents mutation of witness list
        - Together: Makes WitnessSet hashable and thread-safe

    Examples:
        >>> # Bootstrap mode (1-of-1)
        >>> ws = WitnessSet(
        ...     namespace="corp",
        ...     witnesses=("alice",),
        ...     threshold=1
        ... )

        >>> # Production mode (2-of-3)
        >>> ws = WitnessSet(
        ...     namespace="corp.hr",
        ...     witnesses=("alice", "bob", "charlie"),
        ...     threshold=2
        ... )

        >>> # Invalid threshold raises InputInvalidError
        >>> ws = WitnessSet(
        ...     namespace="corp",
        ...     witnesses=("alice",),
        ...     threshold=0
        ... )
        InputInvalidError: threshold must be >= 1, got 0
    """

    namespace: str
    witnesses: Tuple[str, ...]
    threshold: int

    def __post_init__(self):
        """
        Validate WitnessSet configuration on construction.

        Validates:
        1. Threshold is valid for the witness set
        2. Namespace follows hierarchical format

        Raises:
            InputInvalidError: If threshold or namespace validation fails
        """
        # Threshold validation - check boolean return explicitly
        is_valid, error_msg = validate_threshold(self.threshold, list(self.witnesses))
        if not is_valid:
            raise InputInvalidError(error_msg)

        # Namespace validation - check boolean return explicitly
        is_valid_ns = validate_namespace(self.namespace)
        if not is_valid_ns:
            raise InputInvalidError(
                f"Invalid namespace format: '{self.namespace}'. "
                f"Must be lowercase alphanumeric/underscore segments separated by dots."
            )


# Export public interface
__all__ = [
    'WitnessSet',
]
