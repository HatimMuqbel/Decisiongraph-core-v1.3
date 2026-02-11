"""
Three-Valued Boolean Logic (TriBool) — Kleene Algebra.

Domain-portable implementation for decision systems where facts
may be missing or uncertain.  Extracted from the ClaimPilot
condition evaluation subsystem for use across all domains.

Truth Tables (Kleene Logic):
    AND: False dominates, Unknown propagates
    OR:  True dominates, Unknown propagates
    NOT: Unknown stays Unknown
"""
from __future__ import annotations

from enum import Enum
from typing import Optional


class TriBool(Enum):
    """
    Three-valued Boolean logic (Kleene logic).

    Used when facts may be missing or uncertain. Supports:
    - TRUE: Condition is definitely satisfied
    - FALSE: Condition is definitely not satisfied
    - UNKNOWN: Cannot determine (missing facts)

    Truth Tables:

    AND:
        AND    | TRUE    FALSE   UNKNOWN
        -------|------------------------
        TRUE   | TRUE    FALSE   UNKNOWN
        FALSE  | FALSE   FALSE   FALSE
        UNKNOWN| UNKNOWN FALSE   UNKNOWN

    OR:
        OR     | TRUE    FALSE   UNKNOWN
        -------|------------------------
        TRUE   | TRUE    TRUE    TRUE
        FALSE  | TRUE    FALSE   UNKNOWN
        UNKNOWN| TRUE    UNKNOWN UNKNOWN

    NOT:
        NOT TRUE = FALSE
        NOT FALSE = TRUE
        NOT UNKNOWN = UNKNOWN
    """
    TRUE = True
    FALSE = False
    UNKNOWN = None

    def __and__(self, other: TriBool) -> TriBool:
        """
        Kleene AND: False dominates, Unknown propagates.

        Examples:
            TRUE & TRUE = TRUE
            TRUE & FALSE = FALSE
            TRUE & UNKNOWN = UNKNOWN
            FALSE & UNKNOWN = FALSE
        """
        if not isinstance(other, TriBool):
            return NotImplemented

        # False dominates everything
        if self == TriBool.FALSE or other == TriBool.FALSE:
            return TriBool.FALSE
        # Unknown propagates if no False
        if self == TriBool.UNKNOWN or other == TriBool.UNKNOWN:
            return TriBool.UNKNOWN
        # Both must be True
        return TriBool.TRUE

    def __or__(self, other: TriBool) -> TriBool:
        """
        Kleene OR: True dominates, Unknown propagates.

        Examples:
            TRUE | FALSE = TRUE
            TRUE | UNKNOWN = TRUE
            FALSE | UNKNOWN = UNKNOWN
            FALSE | FALSE = FALSE
        """
        if not isinstance(other, TriBool):
            return NotImplemented

        # True dominates everything
        if self == TriBool.TRUE or other == TriBool.TRUE:
            return TriBool.TRUE
        # Unknown propagates if no True
        if self == TriBool.UNKNOWN or other == TriBool.UNKNOWN:
            return TriBool.UNKNOWN
        # Both must be False
        return TriBool.FALSE

    def __invert__(self) -> TriBool:
        """
        Kleene NOT: Unknown stays Unknown.

        Examples:
            ~TRUE = FALSE
            ~FALSE = TRUE
            ~UNKNOWN = UNKNOWN
        """
        if self == TriBool.UNKNOWN:
            return TriBool.UNKNOWN
        return TriBool.FALSE if self == TriBool.TRUE else TriBool.TRUE

    def __bool__(self) -> bool:
        """
        Convert to bool for Python if statements.

        Raises ValueError for UNKNOWN to force explicit handling.
        """
        if self == TriBool.UNKNOWN:
            raise ValueError(
                "Cannot convert TriBool.UNKNOWN to bool. "
                "Handle UNKNOWN explicitly in your logic."
            )
        return self == TriBool.TRUE

    @classmethod
    def from_bool(cls, value: Optional[bool]) -> TriBool:
        """Convert Python bool/None to TriBool."""
        if value is None:
            return cls.UNKNOWN
        return cls.TRUE if value else cls.FALSE

    def is_known(self) -> bool:
        """Check if value is known (not UNKNOWN)."""
        return self != TriBool.UNKNOWN

    def is_true(self) -> bool:
        """Check if value is TRUE."""
        return self == TriBool.TRUE

    def is_false(self) -> bool:
        """Check if value is FALSE."""
        return self == TriBool.FALSE

    def is_unknown(self) -> bool:
        """Check if value is UNKNOWN."""
        return self == TriBool.UNKNOWN


__all__ = ["TriBool"]
