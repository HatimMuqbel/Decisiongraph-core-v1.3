"""
ClaimPilot Evidence Rules

Models for evidence requirements and gates.

Key components:
- DocumentRequirement: A specific document requirement
- EvidenceRule: Rules for what evidence is required
- EvidenceGateResult: Result of evidence gate evaluation

Two-Stage Evidence Gates:
- BLOCKING_RECOMMENDATION: Cannot recommend without this evidence
- BLOCKING_FINALIZATION: Can recommend, but human can't finalize without it
- RECOMMENDED: Proceed with warning
- OPTIONAL: Nice to have
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .enums import DispositionType, GateStrictness
from .authority import AuthorityRef
from .conditions import Condition


# =============================================================================
# Document Requirement
# =============================================================================

@dataclass
class DocumentRequirement:
    """
    A specific document requirement.

    Defines what document is needed, whether it's required,
    and what alternatives are acceptable.

    Attributes:
        doc_type: Type identifier (e.g., "police_report")
        description: Human-readable description
        strictness: How strictly this is enforced
        alternatives: Acceptable substitute documents
        condition_id: Condition for when this applies
    """
    doc_type: str
    description: str
    strictness: GateStrictness = GateStrictness.BLOCKING_FINALIZATION

    # Acceptable alternatives
    alternatives: list[str] = field(default_factory=list)

    # When does this requirement apply
    condition_id: Optional[str] = None  # Reference to condition
    applies_when: Optional[Condition] = None  # Inline condition

    @property
    def is_blocking_recommendation(self) -> bool:
        """Check if this blocks recommendation."""
        return self.strictness == GateStrictness.BLOCKING_RECOMMENDATION

    @property
    def is_blocking_finalization(self) -> bool:
        """Check if this blocks finalization."""
        return self.strictness in {
            GateStrictness.BLOCKING_RECOMMENDATION,
            GateStrictness.BLOCKING_FINALIZATION,
        }

    @property
    def is_recommended(self) -> bool:
        """Check if this is recommended but not blocking."""
        return self.strictness == GateStrictness.RECOMMENDED

    @property
    def is_optional(self) -> bool:
        """Check if this is optional."""
        return self.strictness == GateStrictness.OPTIONAL

    @property
    def acceptable_types(self) -> list[str]:
        """Get all acceptable document types (primary + alternatives)."""
        return [self.doc_type] + self.alternatives


# =============================================================================
# Evidence Rule
# =============================================================================

@dataclass
class EvidenceRule:
    """
    Defines what evidence is required for a disposition type.

    Evidence rules are evaluated based on the recommended disposition
    and claim context.

    Attributes:
        id: Unique identifier
        name: Human-readable name
        description: Detailed description
        disposition_type: What disposition this applies to
        required_documents: Documents that must be present
        recommended_documents: Documents that should be present
        authority_ref: Citation to requirement source
        applies_when: Condition for when this rule applies
    """
    id: str
    name: str
    description: str = ""

    # When does this rule apply
    disposition_type: Optional[DispositionType] = None  # None = applies to all
    applies_when: Optional[Condition] = None
    applies_when_id: Optional[str] = None

    # Document requirements
    required_documents: list[DocumentRequirement] = field(default_factory=list)
    recommended_documents: list[DocumentRequirement] = field(default_factory=list)

    # Authority citation
    authority_ref: Optional[AuthorityRef] = None

    # Scope
    jurisdiction: Optional[str] = None
    line_of_business: Optional[str] = None

    # Configuration
    enabled: bool = True
    priority: int = 0

    def get_blocking_recommendation_requirements(self) -> list[DocumentRequirement]:
        """Get requirements that block recommendation."""
        return [
            r for r in self.required_documents
            if r.is_blocking_recommendation
        ]

    def get_blocking_finalization_requirements(self) -> list[DocumentRequirement]:
        """Get requirements that block finalization."""
        return [
            r for r in self.required_documents
            if r.is_blocking_finalization
        ]

    def get_recommended_requirements(self) -> list[DocumentRequirement]:
        """Get recommended (non-blocking) requirements."""
        result = [
            r for r in self.required_documents
            if r.is_recommended
        ]
        result.extend(self.recommended_documents)
        return result


# =============================================================================
# Evidence Gate Result
# =============================================================================

@dataclass
class EvidenceGateResult:
    """
    Result of evidence gate evaluation.

    Indicates whether the gate passed and what's missing.

    Attributes:
        passed_recommendation: Can proceed with recommendation
        passed_finalization: Can proceed with finalization
        missing_for_recommendation: What blocks recommendation
        missing_for_finalization: What blocks finalization
        missing_recommended: Recommended but missing
        collected: What evidence is available
        message: Human-readable summary
    """
    passed_recommendation: bool
    passed_finalization: bool

    # What's missing
    missing_for_recommendation: list[DocumentRequirement] = field(default_factory=list)
    missing_for_finalization: list[DocumentRequirement] = field(default_factory=list)
    missing_recommended: list[DocumentRequirement] = field(default_factory=list)

    # What's available
    collected: list[str] = field(default_factory=list)  # doc_types

    # Summary
    message: str = ""

    @property
    def can_recommend(self) -> bool:
        """Check if recommendation can proceed."""
        return self.passed_recommendation

    @property
    def can_finalize(self) -> bool:
        """Check if finalization can proceed."""
        return self.passed_finalization

    @property
    def has_warnings(self) -> bool:
        """Check if there are warnings (missing recommended)."""
        return len(self.missing_recommended) > 0

    @property
    def all_satisfied(self) -> bool:
        """Check if all requirements (including recommended) are satisfied."""
        return (
            self.passed_finalization
            and len(self.missing_recommended) == 0
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "passed_recommendation": self.passed_recommendation,
            "passed_finalization": self.passed_finalization,
            "can_recommend": self.can_recommend,
            "can_finalize": self.can_finalize,
            "has_warnings": self.has_warnings,
            "missing_for_recommendation": [
                r.doc_type for r in self.missing_for_recommendation
            ],
            "missing_for_finalization": [
                r.doc_type for r in self.missing_for_finalization
            ],
            "missing_recommended": [
                r.doc_type for r in self.missing_recommended
            ],
            "collected": self.collected,
            "message": self.message,
        }


# =============================================================================
# Evidence Checklist
# =============================================================================

@dataclass
class EvidenceChecklist:
    """
    A checklist of evidence requirements for a claim.

    Generated from applicable evidence rules.
    """
    claim_id: str
    items: list[EvidenceChecklistItem] = field(default_factory=list)

    def add_item(
        self,
        doc_type: str,
        description: str,
        strictness: GateStrictness,
        rule_id: str,
    ) -> None:
        """Add an item to the checklist."""
        item = EvidenceChecklistItem(
            doc_type=doc_type,
            description=description,
            strictness=strictness,
            rule_id=rule_id,
        )
        self.items.append(item)

    def get_blocking_items(self) -> list[EvidenceChecklistItem]:
        """Get all blocking items."""
        return [
            i for i in self.items
            if i.strictness in {
                GateStrictness.BLOCKING_RECOMMENDATION,
                GateStrictness.BLOCKING_FINALIZATION,
            }
        ]

    def get_recommended_items(self) -> list[EvidenceChecklistItem]:
        """Get all recommended items."""
        return [
            i for i in self.items
            if i.strictness == GateStrictness.RECOMMENDED
        ]

    def get_incomplete_items(self) -> list[EvidenceChecklistItem]:
        """Get all incomplete items."""
        return [i for i in self.items if not i.satisfied]

    @property
    def completion_rate(self) -> float:
        """Calculate completion rate (0.0 to 1.0)."""
        if not self.items:
            return 1.0
        satisfied = sum(1 for i in self.items if i.satisfied)
        return satisfied / len(self.items)


@dataclass
class EvidenceChecklistItem:
    """
    A single item in an evidence checklist.
    """
    doc_type: str
    description: str
    strictness: GateStrictness
    rule_id: str

    # Status
    satisfied: bool = False
    evidence_id: Optional[str] = None  # ID of evidence that satisfies
    satisfied_by_alternative: bool = False
    alternative_doc_type: Optional[str] = None

    def mark_satisfied(
        self,
        evidence_id: str,
        is_alternative: bool = False,
        alternative_type: Optional[str] = None,
    ) -> None:
        """Mark this item as satisfied."""
        self.satisfied = True
        self.evidence_id = evidence_id
        self.satisfied_by_alternative = is_alternative
        self.alternative_doc_type = alternative_type
