"""
ClaimPilot Claim Models

Models for claim context, facts, and evidence.

Key components:
- ClaimContext: Resolved context for a specific claim
- Fact: A discrete piece of information about a claim
- EvidenceItem: Documentation supporting claim evaluation

The separation between Facts and Evidence is intentional:
- Facts are assertions (what we believe to be true)
- Evidence is documentation (proof supporting facts)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import uuid4

from .enums import (
    ClaimantType,
    EvidenceStatus,
    FactCertainty,
    FactSource,
    LineOfBusiness,
)
from .policy import CoverageSection, Exclusion


# =============================================================================
# Fact
# =============================================================================

@dataclass
class Fact:
    """
    A discrete piece of information about a claim.

    Facts are the inputs to condition evaluation. They have provenance
    (where they came from) and certainty (how confident we are).

    Attributes:
        id: Unique identifier
        claim_id: Associated claim
        field: Field name (e.g., "vehicle_use_at_loss")
        value: The value
        value_type: Type hint for the value
        source: Where this fact came from
        source_reference: Reference to source (document ID, etc.)
        recorded_by: User ID who recorded the fact
        recorded_at: When the fact was recorded
        certainty: Confidence level
        effective_as_of: When was this fact true
        supersedes: ID of fact this replaces
    """
    id: str
    claim_id: str
    field: str
    value: Any
    value_type: str  # "string", "number", "boolean", "date", "list", "decimal"

    # Provenance
    source: FactSource
    source_reference: Optional[str] = None
    recorded_by: Optional[str] = None
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Confidence
    certainty: FactCertainty = FactCertainty.REPORTED

    # Temporal
    effective_as_of: Optional[date] = None
    supersedes: Optional[str] = None  # ID of fact this replaces

    # Notes
    notes: Optional[str] = None

    @classmethod
    def create(
        cls,
        claim_id: str,
        field: str,
        value: Any,
        source: FactSource,
        source_reference: Optional[str] = None,
        certainty: FactCertainty = FactCertainty.REPORTED,
    ) -> Fact:
        """Factory method to create a new Fact."""
        # Infer value type
        if isinstance(value, bool):
            value_type = "boolean"
        elif isinstance(value, (int, float)):
            value_type = "number"
        elif isinstance(value, Decimal):
            value_type = "decimal"
        elif isinstance(value, date):
            value_type = "date"
        elif isinstance(value, list):
            value_type = "list"
        else:
            value_type = "string"

        return cls(
            id=str(uuid4()),
            claim_id=claim_id,
            field=field,
            value=value,
            value_type=value_type,
            source=source,
            source_reference=source_reference,
            certainty=certainty,
        )

    @property
    def is_confirmed(self) -> bool:
        """Check if fact is confirmed."""
        return self.certainty == FactCertainty.CONFIRMED

    @property
    def is_disputed(self) -> bool:
        """Check if fact is disputed."""
        return self.certainty == FactCertainty.DISPUTED

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "claim_id": self.claim_id,
            "field": self.field,
            "value": self.value,
            "value_type": self.value_type,
            "source": self.source.value,
            "certainty": self.certainty.value,
        }


# =============================================================================
# Evidence Item
# =============================================================================

@dataclass
class EvidenceItem:
    """
    A piece of documentation supporting a claim evaluation.

    Evidence items are separate from facts — they are the documentation
    that supports the facts.

    Attributes:
        id: Unique identifier
        claim_id: Associated claim
        doc_type: Type of document
        description: Human-readable description
        status: Current status
        external_reference: Document ID in DMS
        file_path: Path to file if stored locally
        requested_at: When evidence was requested
        received_at: When evidence was received
        verified_at: When evidence was verified
        verified_by: User who verified
        supports_facts: Fact IDs this evidence supports
    """
    id: str
    claim_id: str
    doc_type: str  # e.g., "police_report", "medical_record"
    description: str

    # Status tracking
    status: EvidenceStatus = EvidenceStatus.REQUESTED

    # References
    external_reference: Optional[str] = None  # Document ID in DMS
    file_path: Optional[str] = None

    # Timestamps
    requested_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None

    # What facts does this evidence support?
    supports_facts: list[str] = field(default_factory=list)  # Fact IDs

    # Notes
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None

    @classmethod
    def create(
        cls,
        claim_id: str,
        doc_type: str,
        description: str,
        status: EvidenceStatus = EvidenceStatus.REQUESTED,
    ) -> EvidenceItem:
        """Factory method to create a new EvidenceItem."""
        return cls(
            id=str(uuid4()),
            claim_id=claim_id,
            doc_type=doc_type,
            description=description,
            status=status,
            requested_at=datetime.now(timezone.utc) if status == EvidenceStatus.REQUESTED else None,
        )

    def mark_received(self) -> None:
        """Mark evidence as received."""
        self.status = EvidenceStatus.RECEIVED
        self.received_at = datetime.now(timezone.utc)

    def mark_verified(self, verified_by: str) -> None:
        """Mark evidence as verified."""
        self.status = EvidenceStatus.VERIFIED
        self.verified_at = datetime.now(timezone.utc)
        self.verified_by = verified_by

    def mark_rejected(self, reason: str) -> None:
        """Mark evidence as rejected."""
        self.status = EvidenceStatus.REJECTED
        self.rejection_reason = reason

    @property
    def is_available(self) -> bool:
        """Check if evidence is available for evaluation."""
        return self.status in {
            EvidenceStatus.RECEIVED,
            EvidenceStatus.UNDER_REVIEW,
            EvidenceStatus.VERIFIED,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "claim_id": self.claim_id,
            "doc_type": self.doc_type,
            "description": self.description,
            "status": self.status.value,
        }


# =============================================================================
# Claim Context
# =============================================================================

@dataclass
class ClaimContext:
    """
    Resolved context for a specific claim.

    Given basic claim information, this represents what rules apply:
    - Which coverages potentially apply
    - Which exclusions need evaluation
    - What timeline rules apply

    The context is created by the ContextResolver and used by the
    RecommendationBuilder to evaluate the claim.

    Attributes:
        claim_id: Unique claim identifier
        policy_id: Associated policy
        jurisdiction: Applicable jurisdiction
        line_of_business: Insurance line
        loss_type: Type of loss
        loss_date: Date of loss
        report_date: Date claim was reported
        claimant_type: Relationship of claimant to policy
        claim_amount: Claimed amount (if known)
        applicable_coverages: Coverages that may apply
        applicable_exclusions: Exclusions to evaluate
        applicable_timeline_rules: Timeline requirements
        facts: Known facts about the claim
        evidence: Available evidence
        resolved_at: When context was resolved
        policy_version_used: Version of policy pack used
    """
    claim_id: str
    policy_id: str

    # Claim basics
    jurisdiction: str
    line_of_business: LineOfBusiness
    loss_type: str
    loss_date: date
    report_date: date
    claimant_type: ClaimantType

    # Optional claim details
    claim_amount: Optional[Decimal] = None
    claim_description: Optional[str] = None

    # Resolved at context creation time
    applicable_coverages: list[CoverageSection] = field(default_factory=list)
    applicable_exclusions: list[Exclusion] = field(default_factory=list)
    applicable_timeline_rule_ids: list[str] = field(default_factory=list)

    # Facts and evidence
    facts: dict[str, Fact] = field(default_factory=dict)  # field -> Fact
    evidence: list[EvidenceItem] = field(default_factory=list)

    # Metadata
    resolved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    policy_version_used: Optional[str] = None

    # Additional context (flexible key-value)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_fact(self, field: str) -> Optional[Fact]:
        """Get a fact by field name."""
        return self.facts.get(field)

    def get_fact_value(self, field: str) -> Any:
        """Get a fact's value by field name, or None if not found."""
        fact = self.facts.get(field)
        return fact.value if fact else None

    def has_fact(self, field: str) -> bool:
        """Check if a fact exists."""
        return field in self.facts

    def add_fact(self, fact: Fact) -> None:
        """Add a fact to the context."""
        self.facts[fact.field] = fact

    def get_evidence_by_type(self, doc_type: str) -> list[EvidenceItem]:
        """Get all evidence of a specific type."""
        return [e for e in self.evidence if e.doc_type == doc_type]

    def has_evidence(self, doc_type: str) -> bool:
        """Check if any evidence of a type is available."""
        return any(
            e.is_available and e.doc_type == doc_type
            for e in self.evidence
        )

    @property
    def days_since_loss(self) -> int:
        """Calculate days between loss and report."""
        return (self.report_date - self.loss_date).days

    @property
    def coverage_ids(self) -> list[str]:
        """Get IDs of applicable coverages."""
        return [c.id for c in self.applicable_coverages]

    @property
    def exclusion_ids(self) -> list[str]:
        """Get IDs of applicable exclusions."""
        return [e.id for e in self.applicable_exclusions]

    @property
    def fact_keys(self) -> set[str]:
        """Get all fact field names (sorted for determinism)."""
        return set(sorted(self.facts.keys()))

    def to_dict(self) -> dict[str, Any]:
        """Serialize context summary to dictionary."""
        return {
            "claim_id": self.claim_id,
            "policy_id": self.policy_id,
            "jurisdiction": self.jurisdiction,
            "line_of_business": self.line_of_business.value,
            "loss_type": self.loss_type,
            "loss_date": self.loss_date.isoformat(),
            "report_date": self.report_date.isoformat(),
            "claimant_type": self.claimant_type.value,
            "coverage_count": len(self.applicable_coverages),
            "exclusion_count": len(self.applicable_exclusions),
            "fact_count": len(self.facts),
            "evidence_count": len(self.evidence),
        }


# =============================================================================
# Fact Set (Collection with Helpers)
# =============================================================================

@dataclass
class FactSet:
    """
    A collection of facts with helper methods.

    Used for batch operations on facts.
    """
    facts: dict[str, Fact] = field(default_factory=dict)

    def add(self, fact: Fact) -> None:
        """Add a fact, replacing any existing fact for the same field."""
        self.facts[fact.field] = fact

    def get(self, field: str) -> Optional[Fact]:
        """Get a fact by field name."""
        return self.facts.get(field)

    def get_value(self, field: str, default: Any = None) -> Any:
        """Get a fact's value, or default if not found."""
        fact = self.facts.get(field)
        return fact.value if fact else default

    def has(self, field: str) -> bool:
        """Check if a fact exists."""
        return field in self.facts

    def get_by_source(self, source: FactSource) -> list[Fact]:
        """Get all facts from a specific source."""
        return [f for f in self.facts.values() if f.source == source]

    def get_by_certainty(self, certainty: FactCertainty) -> list[Fact]:
        """Get all facts with a specific certainty level."""
        return [f for f in self.facts.values() if f.certainty == certainty]

    def get_disputed(self) -> list[Fact]:
        """Get all disputed facts."""
        return self.get_by_certainty(FactCertainty.DISPUTED)

    def get_confirmed(self) -> list[Fact]:
        """Get all confirmed facts."""
        return self.get_by_certainty(FactCertainty.CONFIRMED)

    def keys(self) -> set[str]:
        """Get all fact field names."""
        return set(self.facts.keys())

    def __len__(self) -> int:
        return len(self.facts)

    def __iter__(self):
        return iter(self.facts.values())

    def __contains__(self, field: str) -> bool:
        return field in self.facts
