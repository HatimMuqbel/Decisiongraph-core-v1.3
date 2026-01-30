"""
ClaimPilot Final Disposition Models

Models for the human's actual decision (separate from recommendation).

Key components:
- FinalDisposition: What the human decided
- DispositionApproval: Approval chain for escalated decisions

Core Principle: "The adjuster decides. ClaimPilot recommends and documents."
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from .enums import DispositionType, SealStatus
from ..canon import canonical_json_bytes


# =============================================================================
# Final Disposition
# =============================================================================

@dataclass
class FinalDisposition:
    """
    The human's final decision on a claim.

    May match or differ from the recommendation.

    Attributes:
        id: Unique identifier
        claim_id: Associated claim
        recommendation_id: The recommendation this responds to
        disposition: The final decision
        disposition_reason: Why this decision
        followed_recommendation: Did they follow the recommendation
        override_reason: If not followed, why
        finalizer_id: User ID who made the decision
        finalizer_role: Role of the finalizer
        finalized_at: When decision was made
        approved_by_id: Approver if escalated
        approved_by_role: Approver's role
        approved_at: When approved
        approval_comments: Approver's comments
        sealed_at: When record was sealed
        content_hash: SHA-256 of record
        signature: Ed25519 signature
    """
    id: str
    claim_id: str
    recommendation_id: str

    # The decision
    disposition: DispositionType
    disposition_reason: str

    # Did they follow the recommendation?
    followed_recommendation: bool
    override_reason: Optional[str] = None

    # Who decided
    finalizer_id: str = ""
    finalizer_role: str = ""  # "adjuster", "supervisor", "manager"
    finalized_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Approval chain (if escalated)
    approved_by_id: Optional[str] = None
    approved_by_role: Optional[str] = None
    approved_at: Optional[datetime] = None
    approval_comments: Optional[str] = None

    # Additional approvers (for multi-level approval)
    additional_approvals: list[DispositionApproval] = field(default_factory=list)

    # Sealing (for audit)
    seal_status: SealStatus = SealStatus.UNSEALED
    sealed_at: Optional[datetime] = None
    content_hash: Optional[str] = None
    signature: Optional[str] = None

    # Notes
    internal_notes: Optional[str] = None
    external_notes: Optional[str] = None  # For claimant communication

    @classmethod
    def create(
        cls,
        claim_id: str,
        recommendation_id: str,
        disposition: DispositionType,
        disposition_reason: str,
        followed_recommendation: bool,
        finalizer_id: str,
        finalizer_role: str,
        override_reason: Optional[str] = None,
    ) -> FinalDisposition:
        """Factory method to create a new FinalDisposition."""
        return cls(
            id=str(uuid4()),
            claim_id=claim_id,
            recommendation_id=recommendation_id,
            disposition=disposition,
            disposition_reason=disposition_reason,
            followed_recommendation=followed_recommendation,
            override_reason=override_reason,
            finalizer_id=finalizer_id,
            finalizer_role=finalizer_role,
        )

    @property
    def is_override(self) -> bool:
        """Check if this is an override of the recommendation."""
        return not self.followed_recommendation

    @property
    def is_approved(self) -> bool:
        """Check if disposition has been approved (if needed)."""
        return self.approved_by_id is not None

    @property
    def is_sealed(self) -> bool:
        """Check if record is sealed."""
        return self.seal_status in {SealStatus.SEALED, SealStatus.VERIFIED}

    def add_approval(
        self,
        approver_id: str,
        approver_role: str,
        comments: Optional[str] = None,
    ) -> None:
        """
        Add an approval to the chain.

        The first approval sets the primary approved_by fields.
        Subsequent approvals go into additional_approvals.
        """
        if not self.approved_by_id:
            # First approval
            self.approved_by_id = approver_id
            self.approved_by_role = approver_role
            self.approved_at = datetime.now(timezone.utc)
            self.approval_comments = comments
        else:
            # Additional approval
            approval = DispositionApproval(
                approver_id=approver_id,
                approver_role=approver_role,
                approved_at=datetime.now(timezone.utc),
                comments=comments,
            )
            self.additional_approvals.append(approval)

    def seal(self) -> None:
        """
        Seal the record for audit.

        Once sealed, the record should not be modified.
        The content_hash can be used to verify integrity.
        """
        if self.is_sealed:
            raise ValueError("Record is already sealed")

        # Compute content hash
        self.content_hash = self._compute_content_hash()
        self.sealed_at = datetime.now(timezone.utc)
        self.seal_status = SealStatus.SEALED

    def verify_seal(self) -> bool:
        """
        Verify the seal is intact.

        Returns True if content hash matches, False otherwise.
        """
        if not self.content_hash:
            return False
        return self._compute_content_hash() == self.content_hash

    def _compute_content_hash(self) -> str:
        """Compute SHA-256 hash of the record content."""
        # Include all fields that affect the decision
        content = {
            "claim_id": self.claim_id,
            "recommendation_id": self.recommendation_id,
            "disposition": self.disposition.value,
            "disposition_reason": self.disposition_reason,
            "followed_recommendation": self.followed_recommendation,
            "override_reason": self.override_reason,
            "finalizer_id": self.finalizer_id,
            "finalizer_role": self.finalizer_role,
            "finalized_at": self.finalized_at.isoformat(),
            "approved_by_id": self.approved_by_id,
            "approved_by_role": self.approved_by_role,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
        }
        content_bytes = canonical_json_bytes(content)
        return hashlib.sha256(content_bytes).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        result: dict[str, Any] = {
            "id": self.id,
            "claim_id": self.claim_id,
            "recommendation_id": self.recommendation_id,
            "disposition": self.disposition.value,
            "disposition_reason": self.disposition_reason,
            "followed_recommendation": self.followed_recommendation,
            "finalizer_id": self.finalizer_id,
            "finalizer_role": self.finalizer_role,
            "finalized_at": self.finalized_at.isoformat(),
            "seal_status": self.seal_status.value,
        }
        if self.override_reason:
            result["override_reason"] = self.override_reason
        if self.approved_by_id:
            result["approved_by_id"] = self.approved_by_id
            result["approved_by_role"] = self.approved_by_role
            result["approved_at"] = self.approved_at.isoformat() if self.approved_at else None
        if self.content_hash:
            result["content_hash"] = self.content_hash
        return result


# =============================================================================
# Disposition Approval
# =============================================================================

@dataclass
class DispositionApproval:
    """
    An approval in the disposition approval chain.

    Used for multi-level approvals when a disposition requires
    sign-off from multiple parties.
    """
    approver_id: str
    approver_role: str
    approved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    comments: Optional[str] = None

    # Approval level (1 = first level, 2 = second level, etc.)
    level: int = 1

    # Status
    is_final: bool = False  # True if this is the final approval

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "approver_id": self.approver_id,
            "approver_role": self.approver_role,
            "approved_at": self.approved_at.isoformat(),
            "comments": self.comments,
            "level": self.level,
            "is_final": self.is_final,
        }


# =============================================================================
# Disposition Audit Entry
# =============================================================================

@dataclass
class DispositionAuditEntry:
    """
    An entry in the disposition audit trail.

    Records any changes or events related to a disposition.
    """
    id: str
    disposition_id: str
    event_type: str  # "created", "approved", "sealed", "verified"
    event_description: str
    actor_id: str
    actor_role: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Before/after values for changes
    before_value: Optional[str] = None
    after_value: Optional[str] = None

    @classmethod
    def create(
        cls,
        disposition_id: str,
        event_type: str,
        event_description: str,
        actor_id: str,
        actor_role: str,
    ) -> DispositionAuditEntry:
        """Factory method to create a new audit entry."""
        return cls(
            id=str(uuid4()),
            disposition_id=disposition_id,
            event_type=event_type,
            event_description=event_description,
            actor_id=actor_id,
            actor_role=actor_role,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        result: dict[str, Any] = {
            "id": self.id,
            "disposition_id": self.disposition_id,
            "event_type": self.event_type,
            "event_description": self.event_description,
            "actor_id": self.actor_id,
            "actor_role": self.actor_role,
            "occurred_at": self.occurred_at.isoformat(),
        }
        if self.before_value:
            result["before_value"] = self.before_value
        if self.after_value:
            result["after_value"] = self.after_value
        return result
