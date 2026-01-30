"""
ClaimPilot Precedent Models

Models for similar past cases (precedents).

Key components:
- PrecedentKey: Feature vector for matching
- PrecedentHit: A similar past case
- PrecedentRecord: Full precedent record for storage

Precedent matching is DETERMINISTIC (not ML/LLM):
- Exact match on key fields
- Jaccard similarity on fact signatures
- Explicit tie-breakers for stable ordering
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import uuid4

from .enums import DispositionType, LineOfBusiness, PrecedentOutcome
from ..canon import content_hash


# =============================================================================
# Precedent Key (Feature Vector)
# =============================================================================

@dataclass
class PrecedentKey:
    """
    Feature vector for precedent matching.

    This is the computed, stable representation of a case
    used for deterministic similarity matching.

    Matching uses:
    - Exact match on some fields
    - Partial overlap on others
    - Jaccard on fact signatures

    Attributes:
        jurisdiction: Applicable jurisdiction
        line_of_business: Insurance line
        loss_type: Type of loss
        coverage_ids_triggered: Coverages that were triggered
        exclusion_clause_hashes: Hashes of exclusion clauses evaluated
        disposition_type: Final disposition
        fact_signature: Sorted set of fact keys (not values)
    """
    jurisdiction: str
    line_of_business: LineOfBusiness
    loss_type: str
    coverage_ids_triggered: list[str]
    exclusion_clause_hashes: list[str]
    disposition_type: DispositionType
    fact_signature: frozenset[str]

    @classmethod
    def from_claim(
        cls,
        jurisdiction: str,
        line_of_business: LineOfBusiness,
        loss_type: str,
        coverage_ids: list[str],
        exclusion_wordings: list[str],
        disposition_type: DispositionType,
        fact_keys: set[str],
    ) -> PrecedentKey:
        """
        Create a PrecedentKey from claim data.

        Args:
            jurisdiction: Applicable jurisdiction
            line_of_business: Insurance line
            loss_type: Type of loss
            coverage_ids: IDs of triggered coverages
            exclusion_wordings: Policy wordings of evaluated exclusions
            disposition_type: Final disposition
            fact_keys: Set of fact field names (not values)

        Returns:
            PrecedentKey instance
        """
        # Hash exclusion wordings for stable comparison
        exclusion_hashes = sorted(content_hash(w)[:12] for w in exclusion_wordings)

        return cls(
            jurisdiction=jurisdiction,
            line_of_business=line_of_business,
            loss_type=loss_type,
            coverage_ids_triggered=sorted(coverage_ids),
            exclusion_clause_hashes=exclusion_hashes,
            disposition_type=disposition_type,
            fact_signature=frozenset(fact_keys),
        )

    @property
    def canonical_key(self) -> str:
        """
        Generate a canonical string key for exact matching.

        Used for fast lookup of identical cases.
        """
        parts = [
            self.jurisdiction,
            self.line_of_business.value,
            self.loss_type,
            ",".join(self.coverage_ids_triggered),
            ",".join(self.exclusion_clause_hashes),
            self.disposition_type.value,
        ]
        return "|".join(parts)


# =============================================================================
# Precedent Hit
# =============================================================================

@dataclass
class PrecedentHit:
    """
    A similar past case surfaced for context.

    NOT a directive — just information for the adjuster.

    Attributes:
        id: Unique identifier for this hit
        case_id: Reference to past claim
        case_date: Date of the precedent case
        similarity_basis: Why it's similar (human-readable)
        recommended_disposition: What was recommended
        matching_factors: What matched
        similarity_score: 0.0 to 1.0 similarity
        final_disposition: What actually happened
        outcome: How it was resolved
        notes: Additional context
        reference_ids: Links to records for drill-down
    """
    # Required fields (no defaults)
    id: str
    case_id: str
    case_date: date
    similarity_basis: str
    recommended_disposition: str

    # Optional fields (with defaults)
    matching_factors: list[str] = field(default_factory=list)
    similarity_score: Optional[Decimal] = None
    final_disposition: Optional[str] = None
    outcome: PrecedentOutcome = PrecedentOutcome.UNKNOWN
    notes: Optional[str] = None
    reference_ids: list[str] = field(default_factory=list)

    # The key used for matching (for verification)
    precedent_key: Optional[PrecedentKey] = None

    @classmethod
    def create(
        cls,
        case_id: str,
        case_date: date,
        similarity_basis: str,
        recommended_disposition: str,
        matching_factors: Optional[list[str]] = None,
        similarity_score: Optional[Decimal] = None,
    ) -> PrecedentHit:
        """Factory method to create a new PrecedentHit."""
        return cls(
            id=str(uuid4()),
            case_id=case_id,
            case_date=case_date,
            similarity_basis=similarity_basis,
            recommended_disposition=recommended_disposition,
            matching_factors=matching_factors or [],
            similarity_score=similarity_score,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        result: dict[str, Any] = {
            "id": self.id,
            "case_id": self.case_id,
            "case_date": self.case_date.isoformat(),
            "similarity_basis": self.similarity_basis,
            "matching_factors": self.matching_factors,
            "recommended_disposition": self.recommended_disposition,
            "outcome": self.outcome.value,
        }
        if self.similarity_score is not None:
            result["similarity_score"] = str(self.similarity_score)
        if self.final_disposition:
            result["final_disposition"] = self.final_disposition
        if self.notes:
            result["notes"] = self.notes
        return result


# =============================================================================
# Precedent Record (Full Storage)
# =============================================================================

@dataclass
class PrecedentRecord:
    """
    Full precedent record for storage and retrieval.

    This is what gets stored in the precedent database.

    Attributes:
        id: Unique identifier
        case_id: Original claim ID
        case_date: Date of the case
        key: The computed feature vector
        recommended_disposition: What ClaimPilot recommended
        final_disposition: What the human decided
        outcome: How it was resolved
        jurisdiction: Applicable jurisdiction
        line_of_business: Insurance line
        loss_type: Type of loss
        claim_amount: Amount claimed
        coverage_ids: Coverages that applied
        exclusion_ids: Exclusions that were evaluated
        fact_ids: Facts that were considered
        reasoning_summary: Summary of reasoning
        authority_ids: Authorities cited
        created_at: When record was created
    """
    id: str
    case_id: str
    case_date: date
    key: PrecedentKey

    # Dispositions
    recommended_disposition: DispositionType
    final_disposition: Optional[DispositionType] = None
    outcome: PrecedentOutcome = PrecedentOutcome.UNKNOWN

    # Case details
    jurisdiction: str = ""
    line_of_business: Optional[LineOfBusiness] = None
    loss_type: str = ""
    claim_amount: Optional[Decimal] = None

    # References
    coverage_ids: list[str] = field(default_factory=list)
    exclusion_ids: list[str] = field(default_factory=list)
    fact_ids: list[str] = field(default_factory=list)
    authority_ids: list[str] = field(default_factory=list)

    # Summary
    reasoning_summary: Optional[str] = None

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        case_id: str,
        case_date: date,
        key: PrecedentKey,
        recommended_disposition: DispositionType,
    ) -> PrecedentRecord:
        """Factory method to create a new PrecedentRecord."""
        return cls(
            id=str(uuid4()),
            case_id=case_id,
            case_date=case_date,
            key=key,
            recommended_disposition=recommended_disposition,
            jurisdiction=key.jurisdiction,
            line_of_business=key.line_of_business,
            loss_type=key.loss_type,
        )

    def set_final_disposition(
        self,
        disposition: DispositionType,
        outcome: PrecedentOutcome,
    ) -> None:
        """Set the final disposition and outcome."""
        self.final_disposition = disposition
        self.outcome = outcome
        self.updated_at = datetime.now(timezone.utc)


# =============================================================================
# Similarity Weights (Configuration)
# =============================================================================

@dataclass
class SimilarityWeights:
    """
    Weights for precedent similarity calculation.

    These weights determine how much each factor contributes
    to the overall similarity score.

    Default weights sum to 1.0 for easy interpretation.
    """
    coverage_type: Decimal = Decimal("0.25")
    claim_type: Decimal = Decimal("0.20")
    policy_language: Decimal = Decimal("0.20")
    jurisdiction: Decimal = Decimal("0.15")
    fact_overlap: Decimal = Decimal("0.15")
    recency: Decimal = Decimal("0.05")

    def __post_init__(self) -> None:
        """Validate weights sum to approximately 1.0."""
        total = (
            self.coverage_type
            + self.claim_type
            + self.policy_language
            + self.jurisdiction
            + self.fact_overlap
            + self.recency
        )
        if abs(total - Decimal("1.0")) > Decimal("0.001"):
            raise ValueError(f"Similarity weights must sum to 1.0, got {total}")


# =============================================================================
# Tie Breaker (For Stable Ordering)
# =============================================================================

def precedent_sort_key(hit: PrecedentHit) -> tuple:
    """
    Generate a sort key for stable precedent ordering.

    Tie-breakers (in order):
    1. similarity_score (descending - higher first)
    2. case_date (descending - newer first)
    3. case_id (ascending - lexicographic)

    Returns:
        Tuple for sorting
    """
    # Negate score for descending order (None becomes 0)
    score = -(hit.similarity_score or Decimal("0"))

    # Negate date for descending order (as ordinal)
    date_ordinal = -hit.case_date.toordinal()

    # Case ID ascending (lexicographic)
    case_id = hit.case_id

    return (score, date_ordinal, case_id)


def sort_precedents(hits: list[PrecedentHit]) -> list[PrecedentHit]:
    """
    Sort precedent hits in stable, deterministic order.

    Order:
    1. Highest similarity score first
    2. Newest case date first (tie-breaker)
    3. Case ID lexicographic (final tie-breaker)
    """
    return sorted(hits, key=precedent_sort_key)
