"""
ClaimPilot Exception Hierarchy

Domain-specific exceptions for insurance claims guidance.
All exceptions include error codes for tracking and logging.

Exception codes follow the pattern: CP_<CATEGORY>_<SPECIFIC>
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ClaimPilotError(Exception):
    """
    Base exception for all ClaimPilot errors.

    Attributes:
        message: Human-readable error description
        code: Machine-readable error code (CP_*)
        details: Additional context about the error
        claim_id: Associated claim ID if applicable
    """
    message: str
    code: str = "CP_INTERNAL_ERROR"
    details: dict[str, Any] = field(default_factory=dict)
    claim_id: Optional[str] = None

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def __str__(self) -> str:
        parts = [f"[{self.code}] {self.message}"]
        if self.claim_id:
            parts.append(f"(claim: {self.claim_id})")
        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Serialize exception for logging/API responses."""
        result: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        if self.claim_id:
            result["claim_id"] = self.claim_id
        return result


# =============================================================================
# Policy/Pack Errors
# =============================================================================

@dataclass
class PolicyLoadError(ClaimPilotError):
    """Failed to load policy pack from file."""
    code: str = "CP_POLICY_LOAD_ERROR"


@dataclass
class PolicyValidationError(ClaimPilotError):
    """Policy pack schema validation failed."""
    code: str = "CP_POLICY_VALIDATION_ERROR"


@dataclass
class PolicyVersionMismatch(ClaimPilotError):
    """Policy version doesn't match expected version."""
    code: str = "CP_POLICY_VERSION_MISMATCH"


@dataclass
class PolicyNotFoundError(ClaimPilotError):
    """Requested policy pack not found."""
    code: str = "CP_POLICY_NOT_FOUND"


# =============================================================================
# Claim Context Errors
# =============================================================================

@dataclass
class ClaimContextError(ClaimPilotError):
    """Claim context is invalid or incomplete."""
    code: str = "CP_CLAIM_CONTEXT_ERROR"


@dataclass
class MissingFactError(ClaimPilotError):
    """Required fact is missing from claim context."""
    code: str = "CP_MISSING_FACT"


@dataclass
class FactConflictError(ClaimPilotError):
    """Facts contain conflicting information."""
    code: str = "CP_FACT_CONFLICT"


@dataclass
class InvalidFactValueError(ClaimPilotError):
    """Fact value is invalid for its declared type."""
    code: str = "CP_INVALID_FACT_VALUE"


# =============================================================================
# Condition Evaluation Errors
# =============================================================================

@dataclass
class ConditionEvaluationError(ClaimPilotError):
    """Condition evaluation failed."""
    code: str = "CP_CONDITION_EVAL_ERROR"


@dataclass
class InvalidConditionError(ClaimPilotError):
    """Condition structure is invalid."""
    code: str = "CP_INVALID_CONDITION"


@dataclass
class FieldPathError(ClaimPilotError):
    """Field path resolution failed."""
    code: str = "CP_FIELD_PATH_ERROR"


# =============================================================================
# Evidence Gate Errors
# =============================================================================

@dataclass
class EvidenceGateError(ClaimPilotError):
    """Evidence gate blocked recommendation or finalization."""
    code: str = "CP_EVIDENCE_GATE_BLOCKED"


@dataclass
class MissingEvidenceError(ClaimPilotError):
    """Required evidence is missing."""
    code: str = "CP_MISSING_EVIDENCE"


# =============================================================================
# Timeline Errors
# =============================================================================

@dataclass
class TimelineCalculationError(ClaimPilotError):
    """Timeline calculation failed."""
    code: str = "CP_TIMELINE_ERROR"


@dataclass
class DeadlineExceededError(ClaimPilotError):
    """Claim deadline has been exceeded."""
    code: str = "CP_DEADLINE_EXCEEDED"


@dataclass
class InvalidCalendarError(ClaimPilotError):
    """Holiday calendar configuration is invalid."""
    code: str = "CP_INVALID_CALENDAR"


# =============================================================================
# Authority/Citation Errors
# =============================================================================

@dataclass
class AuthorityNotFoundError(ClaimPilotError):
    """Referenced authority not found."""
    code: str = "CP_AUTHORITY_NOT_FOUND"


@dataclass
class AuthorityHashMismatch(ClaimPilotError):
    """Authority content hash doesn't match expected value."""
    code: str = "CP_AUTHORITY_HASH_MISMATCH"


# =============================================================================
# Precedent Errors
# =============================================================================

@dataclass
class PrecedentMatchError(ClaimPilotError):
    """Precedent matching failed."""
    code: str = "CP_PRECEDENT_MATCH_ERROR"


@dataclass
class PrecedentNotFoundError(ClaimPilotError):
    """No matching precedents found."""
    code: str = "CP_PRECEDENT_NOT_FOUND"


# =============================================================================
# Recommendation Errors
# =============================================================================

@dataclass
class RecommendationError(ClaimPilotError):
    """Recommendation generation failed."""
    code: str = "CP_RECOMMENDATION_ERROR"


@dataclass
class RecommendationIncompleteError(ClaimPilotError):
    """Recommendation cannot be completed due to missing information."""
    code: str = "CP_RECOMMENDATION_INCOMPLETE"


# =============================================================================
# Disposition Errors
# =============================================================================

@dataclass
class DispositionError(ClaimPilotError):
    """Final disposition recording failed."""
    code: str = "CP_DISPOSITION_ERROR"


@dataclass
class DispositionSealedError(ClaimPilotError):
    """Cannot modify sealed disposition."""
    code: str = "CP_DISPOSITION_SEALED"


@dataclass
class EscalationRequiredError(ClaimPilotError):
    """Action requires escalation to higher authority."""
    code: str = "CP_ESCALATION_REQUIRED"
