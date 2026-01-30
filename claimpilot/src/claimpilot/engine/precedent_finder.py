"""
ClaimPilot Precedent Finder

Finds similar past cases using deterministic weighted matching.

Key features:
- PrecedentKey-based matching
- Weighted factor scoring (not ML/LLM)
- Explicit tie-breakers for determinism
- Jaccard similarity on fact keys
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from ..models import (
    ClaimContext,
    DispositionType,
    PrecedentHit,
    PrecedentKey,
    SimilarityWeights,
    sort_precedents,
)


# =============================================================================
# Precedent Database (Interface)
# =============================================================================

@dataclass
class PrecedentRecord:
    """
    A historical case record for precedent matching.

    In production, these would be stored in a database.
    This dataclass represents the essential fields for matching.
    """
    id: str
    case_id: str
    case_date: date
    recommended_disposition: DispositionType

    # Key fields for matching
    jurisdiction: str
    line_of_business: str
    loss_type: str
    coverage_ids: list[str] = field(default_factory=list)
    exclusion_clause_hashes: list[str] = field(default_factory=list)
    fact_keys: set[str] = field(default_factory=set)

    # Optional context
    outcome: Optional[str] = None
    notes: Optional[str] = None

    def to_precedent_key(self) -> PrecedentKey:
        """Convert to PrecedentKey for matching."""
        return PrecedentKey.compute(
            jurisdiction=self.jurisdiction,
            line_of_business=self.line_of_business,
            loss_type=self.loss_type,
            coverage_ids=self.coverage_ids,
            exclusion_clause_hashes=self.exclusion_clause_hashes,
            disposition_type=self.recommended_disposition,
            fact_keys=self.fact_keys,
        )


# =============================================================================
# Similarity Scoring
# =============================================================================

def jaccard_similarity(set_a: set, set_b: set) -> float:
    """
    Calculate Jaccard similarity between two sets.

    Jaccard = |A ∩ B| / |A ∪ B|

    Returns 0.0 if both sets are empty.
    """
    if not set_a and not set_b:
        return 0.0

    intersection = len(set_a & set_b)
    union = len(set_a | set_b)

    return intersection / union if union > 0 else 0.0


def list_overlap_score(list_a: list, list_b: list) -> float:
    """
    Calculate overlap score for ordered lists.

    Returns proportion of items in common.
    """
    if not list_a and not list_b:
        return 1.0  # Empty lists are considered identical

    if not list_a or not list_b:
        return 0.0

    set_a = set(list_a)
    set_b = set(list_b)

    intersection = len(set_a & set_b)
    max_len = max(len(list_a), len(list_b))

    return intersection / max_len if max_len > 0 else 0.0


def compute_similarity_score(
    query: PrecedentKey,
    candidate: PrecedentKey,
    weights: SimilarityWeights,
) -> float:
    """
    Compute weighted similarity score between two PrecedentKeys.

    Scoring:
    - Exact match fields: 1.0 if equal, 0.0 if not
    - Coverage overlap: list overlap score
    - Exclusion overlap: list overlap score
    - Fact signature: Jaccard similarity

    Final score is weighted average of all factors.
    """
    scores = []
    total_weight = 0.0

    # Jurisdiction (exact match)
    if weights.jurisdiction > 0:
        score = 1.0 if query.jurisdiction == candidate.jurisdiction else 0.0
        scores.append(score * weights.jurisdiction)
        total_weight += weights.jurisdiction

    # Line of Business (exact match)
    if weights.line_of_business > 0:
        score = 1.0 if query.line_of_business == candidate.line_of_business else 0.0
        scores.append(score * weights.line_of_business)
        total_weight += weights.line_of_business

    # Loss Type (exact match)
    if weights.loss_type > 0:
        score = 1.0 if query.loss_type == candidate.loss_type else 0.0
        scores.append(score * weights.loss_type)
        total_weight += weights.loss_type

    # Coverage IDs (overlap)
    if weights.coverage_ids > 0:
        score = list_overlap_score(
            query.coverage_ids_triggered,
            candidate.coverage_ids_triggered
        )
        scores.append(score * weights.coverage_ids)
        total_weight += weights.coverage_ids

    # Exclusion Clause Hashes (overlap)
    if weights.exclusion_hashes > 0:
        score = list_overlap_score(
            query.exclusion_clause_hashes,
            candidate.exclusion_clause_hashes
        )
        scores.append(score * weights.exclusion_hashes)
        total_weight += weights.exclusion_hashes

    # Disposition Type (exact match, optional)
    if weights.disposition_type > 0:
        score = 1.0 if query.disposition_type == candidate.disposition_type else 0.0
        scores.append(score * weights.disposition_type)
        total_weight += weights.disposition_type

    # Fact Signature (Jaccard)
    if weights.fact_signature > 0:
        score = jaccard_similarity(
            query.fact_signature,
            candidate.fact_signature
        )
        scores.append(score * weights.fact_signature)
        total_weight += weights.fact_signature

    # Weighted average
    if total_weight > 0:
        return sum(scores) / total_weight
    return 0.0


# =============================================================================
# Precedent Finder
# =============================================================================

@dataclass
class PrecedentFinder:
    """
    Finds similar past cases for a claim.

    Uses deterministic weighted matching with explicit tie-breakers:
    1. similarity_score (descending)
    2. effective_date (newest first)
    3. case_id (lexicographic ascending)

    Usage:
        finder = PrecedentFinder(precedent_store=my_records)

        # Build query from current claim
        query_key = build_precedent_key(context, triggered_coverages, exclusions)

        # Find similar cases
        matches = finder.find_similar(
            query=query_key,
            limit=5,
            min_score=0.5,
        )

        for match in matches:
            print(f"{match.case_id}: {match.similarity_score:.2f}")
    """

    # Historical case records (in production, this would be a database)
    precedent_store: list[PrecedentRecord] = field(default_factory=list)

    # Similarity weights
    weights: SimilarityWeights = field(default_factory=SimilarityWeights)

    # Minimum score threshold
    min_score_threshold: float = 0.3

    def find_similar(
        self,
        query: PrecedentKey,
        limit: int = 10,
        min_score: Optional[float] = None,
        jurisdiction_filter: Optional[str] = None,
        line_of_business_filter: Optional[str] = None,
    ) -> list[PrecedentHit]:
        """
        Find similar precedent cases.

        Args:
            query: PrecedentKey to match against
            limit: Maximum number of results
            min_score: Minimum similarity score (default: min_score_threshold)
            jurisdiction_filter: Optional jurisdiction filter
            line_of_business_filter: Optional LOB filter

        Returns:
            List of PrecedentHits sorted by similarity (highest first)
        """
        min_score = min_score if min_score is not None else self.min_score_threshold
        candidates: list[PrecedentHit] = []

        for record in self.precedent_store:
            # Apply filters
            if jurisdiction_filter and record.jurisdiction != jurisdiction_filter:
                continue
            if line_of_business_filter and record.line_of_business != line_of_business_filter:
                continue

            # Convert to PrecedentKey
            candidate_key = record.to_precedent_key()

            # Compute similarity
            score = compute_similarity_score(query, candidate_key, self.weights)

            if score >= min_score:
                # Build similarity basis explanation
                basis = self._build_similarity_basis(query, candidate_key, score)

                hit = PrecedentHit(
                    id=record.id,
                    case_id=record.case_id,
                    case_date=record.case_date,
                    similarity_basis=basis,
                    recommended_disposition=record.recommended_disposition,
                    similarity_score=score,
                    jurisdiction=record.jurisdiction,
                    line_of_business=record.line_of_business,
                    outcome=record.outcome,
                )
                candidates.append(hit)

        # Sort using deterministic tie-breakers
        sorted_candidates = sort_precedents(candidates)

        # Apply limit
        return sorted_candidates[:limit]

    def _build_similarity_basis(
        self,
        query: PrecedentKey,
        candidate: PrecedentKey,
        total_score: float,
    ) -> str:
        """Build human-readable explanation of similarity."""
        factors = []

        # Check exact matches
        if query.jurisdiction == candidate.jurisdiction:
            factors.append(f"jurisdiction={query.jurisdiction}")
        if query.line_of_business == candidate.line_of_business:
            factors.append(f"lob={query.line_of_business}")
        if query.loss_type == candidate.loss_type:
            factors.append(f"loss_type={query.loss_type}")

        # Coverage overlap
        common_coverages = set(query.coverage_ids_triggered) & set(candidate.coverage_ids_triggered)
        if common_coverages:
            factors.append(f"coverages={len(common_coverages)}")

        # Exclusion overlap
        common_exclusions = set(query.exclusion_clause_hashes) & set(candidate.exclusion_clause_hashes)
        if common_exclusions:
            factors.append(f"exclusions={len(common_exclusions)}")

        # Fact overlap
        fact_overlap = jaccard_similarity(query.fact_signature, candidate.fact_signature)
        if fact_overlap > 0:
            factors.append(f"facts={fact_overlap:.0%}")

        return f"score={total_score:.2f}; " + ", ".join(factors)

    def add_precedent(self, record: PrecedentRecord) -> None:
        """Add a precedent record to the store."""
        self.precedent_store.append(record)

    def find_exact_match(
        self,
        query: PrecedentKey,
    ) -> Optional[PrecedentHit]:
        """
        Find an exact match for a PrecedentKey.

        Returns the first exact match, or None.
        """
        for record in self.precedent_store:
            candidate_key = record.to_precedent_key()

            # Check all key fields
            if (query.jurisdiction == candidate_key.jurisdiction and
                query.line_of_business == candidate_key.line_of_business and
                query.loss_type == candidate_key.loss_type and
                set(query.coverage_ids_triggered) == set(candidate_key.coverage_ids_triggered) and
                set(query.exclusion_clause_hashes) == set(candidate_key.exclusion_clause_hashes) and
                query.disposition_type == candidate_key.disposition_type and
                query.fact_signature == candidate_key.fact_signature):

                return PrecedentHit(
                    id=record.id,
                    case_id=record.case_id,
                    case_date=record.case_date,
                    similarity_basis="exact_match",
                    recommended_disposition=record.recommended_disposition,
                    similarity_score=1.0,
                    jurisdiction=record.jurisdiction,
                    line_of_business=record.line_of_business,
                    outcome=record.outcome,
                )

        return None


# =============================================================================
# Helper Functions
# =============================================================================

def build_precedent_key(
    context: ClaimContext,
    triggered_coverage_ids: list[str],
    exclusion_hashes: list[str],
    disposition: Optional[DispositionType] = None,
) -> PrecedentKey:
    """
    Build a PrecedentKey from a claim context.

    Args:
        context: The claim context
        triggered_coverage_ids: IDs of triggered coverages
        exclusion_hashes: Hashes of triggered exclusions
        disposition: Optional disposition type

    Returns:
        PrecedentKey for matching
    """
    # Extract fact keys (sorted for determinism)
    fact_keys = set(context.facts.keys())

    return PrecedentKey.compute(
        jurisdiction=context.metadata.get("jurisdiction", "unknown"),
        line_of_business=context.metadata.get("line_of_business", "unknown"),
        loss_type=context.loss_type,
        coverage_ids=triggered_coverage_ids,
        exclusion_clause_hashes=exclusion_hashes,
        disposition_type=disposition,
        fact_keys=fact_keys,
    )


def build_precedent_key_from_policy(
    context: ClaimContext,
    policy: "Policy",
    triggered_coverages: list["CoverageSection"],
    triggered_exclusions: list["Exclusion"],
    disposition: Optional[DispositionType] = None,
) -> PrecedentKey:
    """
    Build a PrecedentKey from claim context and policy objects.

    Convenience function that extracts IDs and computes hashes.
    """
    from ..canon import text_hash

    # Get coverage IDs
    coverage_ids = [c.id for c in triggered_coverages]

    # Compute exclusion hashes from policy wording
    exclusion_hashes = []
    for exc in triggered_exclusions:
        if exc.policy_wording:
            hash_value = text_hash(exc.policy_wording)
            exclusion_hashes.append(hash_value)
        else:
            # Use exclusion ID as fallback
            exclusion_hashes.append(exc.id)

    # Extract fact keys
    fact_keys = set(context.facts.keys())

    return PrecedentKey.compute(
        jurisdiction=policy.jurisdiction,
        line_of_business=policy.line_of_business.value,
        loss_type=context.loss_type,
        coverage_ids=coverage_ids,
        exclusion_clause_hashes=exclusion_hashes,
        disposition_type=disposition,
        fact_keys=fact_keys,
    )


# =============================================================================
# Convenience Functions
# =============================================================================

def find_similar_cases(
    query: PrecedentKey,
    precedent_store: list[PrecedentRecord],
    limit: int = 5,
    min_score: float = 0.3,
) -> list[PrecedentHit]:
    """
    Find similar cases from a precedent store.

    Convenience function that creates a temporary finder.
    """
    finder = PrecedentFinder(precedent_store=precedent_store)
    return finder.find_similar(query, limit=limit, min_score=min_score)


def compute_case_similarity(
    key_a: PrecedentKey,
    key_b: PrecedentKey,
    weights: Optional[SimilarityWeights] = None,
) -> float:
    """
    Compute similarity between two PrecedentKeys.

    Convenience function for direct comparison.
    """
    weights = weights or SimilarityWeights()
    return compute_similarity_score(key_a, key_b, weights)
