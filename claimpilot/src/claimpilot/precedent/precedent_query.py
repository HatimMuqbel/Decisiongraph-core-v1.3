"""
ClaimPilot Precedent System: Precedent Query Engine Module

This module implements the tiered query engine for precedent retrieval.
It provides the high-level API for querying precedents during claim evaluation.

Key components:
- PrecedentQueryTier: Enum defining query tiers (0, 0.5, 1)
- PrecedentQueryParams: Parameters for a precedent query
- PrecedentQueryResult: Results from a precedent query
- PrecedentMatch: A single matching precedent
- PrecedentQueryEngine: The main query engine

Query Tiers:
- Tier 0 (EXACT_FINGERPRINT): Identical banded facts
- Tier 0.5 (SAME_CODES): Same exclusion codes + same outcome
- Tier 1 (CODE_OVERLAP): Overlapping exclusion codes

Confidence Scoring (pc_v1):
    base_confidence = weighted_average(
        majority_pct * 0.30,
        upheld_rate * 0.25,
        recency_score * 0.20,
        policy_match_score * 0.15,
        decision_level_score * 0.10
    )

    overturn_penalty = compute_overturn_penalty(...)
    precedent_confidence = base_confidence - overturn_penalty

Example:
    >>> engine = PrecedentQueryEngine(chain, fingerprint_registry, salt)
    >>> result = engine.query(
    ...     facts={"driver.rideshare_app_active": True, ...},
    ...     policy_type="auto",
    ...     jurisdiction="CA-ON",
    ...     exclusion_codes=["4.2.1"],
    ...     proposed_outcome="deny"
    ... )
    >>> print(f"Confidence: {result.statistics.precedent_confidence}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING
from uuid import uuid4

from kernel.foundation.judgment import JudgmentPayload
from kernel.precedent.precedent_registry import (
    PrecedentRegistry,
    PrecedentStatistics,
    AppealStatistics,
)

from .fingerprint_schema import FingerprintSchemaRegistry

if TYPE_CHECKING:
    from kernel.foundation.chain import Chain


# =============================================================================
# Enums
# =============================================================================

class PrecedentQueryTier(str, Enum):
    """
    Query tiers for precedent matching.

    Tiers are ordered by match quality:
    - TIER_0: Exact fingerprint match (highest quality)
    - TIER_0_5: Same exclusion codes + same outcome
    - TIER_1: Overlapping exclusion codes (lowest quality)
    """
    TIER_0_EXACT_FINGERPRINT = "tier_0"
    TIER_0_5_SAME_CODES = "tier_0.5"
    TIER_1_CODE_OVERLAP = "tier_1"


# =============================================================================
# Query Parameters
# =============================================================================

@dataclass
class PrecedentQueryParams:
    """
    Parameters for a precedent query.

    These parameters are stored with the recommendation for auditability.

    Attributes:
        fingerprint_hash: The computed fingerprint hash
        fingerprint_schema_id: Schema used to compute fingerprint
        exclusion_codes: Exclusion codes being evaluated
        min_exclusion_overlap: Minimum codes that must overlap for Tier 1
        query_tier: The tier of query performed
        evaluated_at: When the query was performed (ISO 8601)
        namespace_prefix: Namespace searched
    """
    fingerprint_hash: str
    fingerprint_schema_id: str
    exclusion_codes: list[str]
    min_exclusion_overlap: int = 1
    query_tier: str = PrecedentQueryTier.TIER_0_EXACT_FINGERPRINT.value
    evaluated_at: str = ""
    namespace_prefix: str = ""

    def __post_init__(self) -> None:
        """Set default evaluated_at if not provided."""
        if not self.evaluated_at:
            self.evaluated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "fingerprint_hash": self.fingerprint_hash,
            "fingerprint_schema_id": self.fingerprint_schema_id,
            "exclusion_codes": self.exclusion_codes,
            "min_exclusion_overlap": self.min_exclusion_overlap,
            "query_tier": self.query_tier,
            "evaluated_at": self.evaluated_at,
            "namespace_prefix": self.namespace_prefix,
        }


# =============================================================================
# Precedent Match
# =============================================================================

@dataclass
class PrecedentMatch:
    """
    A single matching precedent from a query.

    Privacy Design:
    - precedent_id: Random UUID (NOT case_id) for external reference
    - case_id is NEVER exposed externally
    - Internal audit can map precedent_id -> case_id_hash if authorized

    Attributes:
        precedent_id: Random UUID for external reference
        judgment_cell_hash: Hash of the JUDGMENT cell
        match_type: Type of match (exact_fingerprint, exclusion_code, etc.)
        match_score: Computed match score (0.0-1.0)
        match_factors: What matched (list of descriptions)
        distinguish_factors: What differs (for adjuster review)
        outcome_code: The precedent's outcome
        exclusion_codes: The precedent's exclusion codes
        decided_at: When the precedent was decided
        decision_level: Authority level of the decision
        appealed: Whether it was appealed
        appeal_outcome: Outcome if appealed
        outcome_notable: Notable marker (boundary_case, landmark, overturned)
        is_caution: True if this is a caution precedent (overturned or different outcome)
    """
    precedent_id: str
    judgment_cell_hash: str
    match_type: str
    match_score: Decimal
    match_factors: list[str]
    distinguish_factors: list[str]
    outcome_code: str
    exclusion_codes: list[str]
    decided_at: str
    decision_level: str
    appealed: bool
    appeal_outcome: Optional[str] = None
    outcome_notable: Optional[str] = None
    is_caution: bool = False

    @classmethod
    def from_payload(
        cls,
        payload: JudgmentPayload,
        cell_hash: str,
        match_type: str,
        match_score: Decimal,
        match_factors: list[str],
        distinguish_factors: list[str],
        proposed_outcome: str,
    ) -> PrecedentMatch:
        """
        Create a PrecedentMatch from a JudgmentPayload.

        Args:
            payload: The JudgmentPayload to create from
            cell_hash: Hash of the JUDGMENT cell
            match_type: Type of match
            match_score: Computed match score
            match_factors: What matched
            distinguish_factors: What differs
            proposed_outcome: The proposed outcome for the current case

        Returns:
            PrecedentMatch instance
        """
        # Determine if this is a caution precedent
        is_caution = (
            payload.appeal_outcome == "overturned"
            or payload.outcome_code != proposed_outcome
        )

        return cls(
            precedent_id=payload.precedent_id,
            judgment_cell_hash=cell_hash,
            match_type=match_type,
            match_score=match_score,
            match_factors=match_factors,
            distinguish_factors=distinguish_factors,
            outcome_code=payload.outcome_code,
            exclusion_codes=payload.exclusion_codes,
            decided_at=payload.decided_at,
            decision_level=payload.decision_level,
            appealed=payload.appealed,
            appeal_outcome=payload.appeal_outcome,
            outcome_notable=payload.outcome_notable,
            is_caution=is_caution,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        result: dict[str, Any] = {
            "precedent_id": self.precedent_id,
            "judgment_cell_hash": self.judgment_cell_hash,
            "match_type": self.match_type,
            "match_score": str(self.match_score),
            "match_factors": self.match_factors,
            "distinguish_factors": self.distinguish_factors,
            "outcome_code": self.outcome_code,
            "exclusion_codes": self.exclusion_codes,
            "decided_at": self.decided_at,
            "decision_level": self.decision_level,
            "appealed": self.appealed,
            "is_caution": self.is_caution,
        }
        if self.appeal_outcome:
            result["appeal_outcome"] = self.appeal_outcome
        if self.outcome_notable:
            result["outcome_notable"] = self.outcome_notable
        return result


# =============================================================================
# Precedent Summary
# =============================================================================

@dataclass
class PrecedentSummary:
    """
    Summary of precedent query results for display.

    Provides high-level metrics for the recommendation output.

    Attributes:
        total_matched: Total number of matching precedents
        same_outcome_count: Count with same outcome as proposed
        consistency_rate: Rate of same-outcome precedents
        appeal_stats: Appeal statistics
        precedent_confidence: Computed confidence score (0.0-1.0)
        precedent_confidence_model_id: Model used for confidence calculation
    """
    total_matched: int
    same_outcome_count: int
    consistency_rate: Decimal
    appeal_stats: AppealStatistics
    precedent_confidence: Decimal
    precedent_confidence_model_id: str = "pc_v1"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "total_matched": self.total_matched,
            "same_outcome_count": self.same_outcome_count,
            "consistency_rate": str(self.consistency_rate),
            "appeal_stats": {
                "total_appealed": self.appeal_stats.total_appealed,
                "upheld": self.appeal_stats.upheld,
                "overturned": self.appeal_stats.overturned,
                "settled": self.appeal_stats.settled,
                "pending": self.appeal_stats.pending,
                "upheld_rate": self.appeal_stats.upheld_rate,
            },
            "precedent_confidence": str(self.precedent_confidence),
            "precedent_confidence_model_id": self.precedent_confidence_model_id,
        }


# =============================================================================
# Query Result
# =============================================================================

@dataclass
class PrecedentQueryResult:
    """
    Results from a precedent query.

    Contains all matches, statistics, and query parameters for auditability.

    Attributes:
        tier: The query tier that produced these results
        matches: List of PrecedentMatch
        statistics: Aggregated statistics
        overlap_count: For Tier 1, how many codes overlapped
        query_params: The parameters used for the query
        summary: Computed summary for display
    """
    tier: PrecedentQueryTier
    matches: list[PrecedentMatch]
    statistics: PrecedentStatistics
    overlap_count: int = 0
    query_params: Optional[PrecedentQueryParams] = None
    summary: Optional[PrecedentSummary] = None

    @property
    def supporting_precedents(self) -> list[PrecedentMatch]:
        """Get precedents that support the proposed outcome."""
        return [m for m in self.matches if not m.is_caution]

    @property
    def caution_precedents(self) -> list[PrecedentMatch]:
        """Get caution precedents (overturned or different outcome)."""
        return [m for m in self.matches if m.is_caution]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        result: dict[str, Any] = {
            "tier": self.tier.value,
            "matches": [m.to_dict() for m in self.matches],
            "statistics": self.statistics.to_dict(),
            "overlap_count": self.overlap_count,
        }
        if self.query_params:
            result["query_params"] = self.query_params.to_dict()
        if self.summary:
            result["summary"] = self.summary.to_dict()
        return result


# =============================================================================
# Precedent Query Engine
# =============================================================================

class PrecedentQueryEngine:
    """
    High-level query engine for precedent retrieval.

    The engine provides a unified interface for querying precedents
    across all tiers. It handles:
    - Fingerprint computation
    - Multi-tier query fallback
    - Confidence scoring
    - Result aggregation

    Usage:
        >>> engine = PrecedentQueryEngine(chain, fingerprint_registry, salt)
        >>> result = engine.query(
        ...     facts={"driver.rideshare_app_active": True},
        ...     policy_type="auto",
        ...     jurisdiction="CA-ON",
        ...     exclusion_codes=["4.2.1"],
        ...     proposed_outcome="deny"
        ... )
    """

    def __init__(
        self,
        chain: Chain,
        fingerprint_registry: Optional[FingerprintSchemaRegistry] = None,
        salt: str = "",
        namespace_prefix: str = "claims.precedents",
    ) -> None:
        """
        Initialize the query engine.

        Args:
            chain: The DecisionGraph chain to query
            fingerprint_registry: Registry for fingerprint schemas
            salt: Salt for fingerprint computation
            namespace_prefix: Default namespace prefix for queries
        """
        self.chain = chain
        self.precedent_registry = PrecedentRegistry(chain)
        self.fingerprint_registry = fingerprint_registry or FingerprintSchemaRegistry()
        self.salt = salt
        self.namespace_prefix = namespace_prefix

    def query(
        self,
        facts: dict[str, Any],
        policy_type: str,
        jurisdiction: str,
        exclusion_codes: list[str],
        proposed_outcome: str,
        min_exclusion_overlap: int = 1,
        as_of: Optional[str] = None,
    ) -> PrecedentQueryResult:
        """
        Query for precedents matching the given case.

        The query proceeds through tiers, returning results from the
        highest-quality tier that has matches.

        Args:
            facts: Dict of field_id -> value for fingerprint computation
            policy_type: Policy type (e.g., "auto")
            jurisdiction: Jurisdiction code (e.g., "CA-ON")
            exclusion_codes: Exclusion codes being evaluated
            proposed_outcome: The proposed outcome for this case
            min_exclusion_overlap: Minimum codes that must overlap for Tier 1
            as_of: Bitemporal cutoff timestamp

        Returns:
            PrecedentQueryResult with matches and statistics
        """
        # Get fingerprint schema
        schema = self.fingerprint_registry.get_schema(policy_type, jurisdiction)

        # Compute fingerprint
        fingerprint_hash = self.fingerprint_registry.compute_fingerprint(
            schema, facts, self.salt
        )

        # Create query params
        evaluated_at = as_of or datetime.now(timezone.utc).isoformat()
        query_params = PrecedentQueryParams(
            fingerprint_hash=fingerprint_hash,
            fingerprint_schema_id=schema.schema_id,
            exclusion_codes=exclusion_codes,
            min_exclusion_overlap=min_exclusion_overlap,
            evaluated_at=evaluated_at,
            namespace_prefix=self.namespace_prefix,
        )

        # Tier 0: Exact fingerprint match
        tier0_payloads = self.precedent_registry.find_by_fingerprint(
            fingerprint_hash, self.namespace_prefix, as_of
        )

        if tier0_payloads:
            query_params.query_tier = PrecedentQueryTier.TIER_0_EXACT_FINGERPRINT.value
            return self._build_result(
                tier=PrecedentQueryTier.TIER_0_EXACT_FINGERPRINT,
                payloads=tier0_payloads,
                proposed_outcome=proposed_outcome,
                query_params=query_params,
            )

        # Tier 0.5: Same exclusion codes + same outcome
        if exclusion_codes:
            tier05_results = self.precedent_registry.find_by_exclusion_codes(
                codes=exclusion_codes,
                namespace_prefix=self.namespace_prefix,
                outcome=proposed_outcome,
                min_overlap=len(exclusion_codes),  # Require ALL codes to match
                as_of=as_of,
            )

            if tier05_results:
                query_params.query_tier = PrecedentQueryTier.TIER_0_5_SAME_CODES.value
                payloads = [payload for payload, _ in tier05_results]
                return self._build_result(
                    tier=PrecedentQueryTier.TIER_0_5_SAME_CODES,
                    payloads=payloads,
                    proposed_outcome=proposed_outcome,
                    query_params=query_params,
                )

        # Tier 1: Overlapping exclusion codes
        if exclusion_codes:
            tier1_results = self.precedent_registry.find_by_exclusion_codes(
                codes=exclusion_codes,
                namespace_prefix=self.namespace_prefix,
                outcome=None,  # Any outcome
                min_overlap=min_exclusion_overlap,
                as_of=as_of,
            )

            if tier1_results:
                query_params.query_tier = PrecedentQueryTier.TIER_1_CODE_OVERLAP.value
                payloads = [payload for payload, _ in tier1_results]
                max_overlap = max(overlap for _, overlap in tier1_results)
                return self._build_result(
                    tier=PrecedentQueryTier.TIER_1_CODE_OVERLAP,
                    payloads=payloads,
                    proposed_outcome=proposed_outcome,
                    query_params=query_params,
                    overlap_count=max_overlap,
                )

        # No matches at any tier
        return PrecedentQueryResult(
            tier=PrecedentQueryTier.TIER_0_EXACT_FINGERPRINT,
            matches=[],
            statistics=PrecedentStatistics(),
            query_params=query_params,
            summary=PrecedentSummary(
                total_matched=0,
                same_outcome_count=0,
                consistency_rate=Decimal("0"),
                appeal_stats=AppealStatistics(),
                precedent_confidence=Decimal("0.5"),  # No data = neutral confidence
            ),
        )

    def _build_result(
        self,
        tier: PrecedentQueryTier,
        payloads: list[JudgmentPayload],
        proposed_outcome: str,
        query_params: PrecedentQueryParams,
        overlap_count: int = 0,
    ) -> PrecedentQueryResult:
        """Build a PrecedentQueryResult from payloads."""
        matches: list[PrecedentMatch] = []

        for payload in payloads:
            match = self._create_match(payload, tier, proposed_outcome)
            matches.append(match)

        # Sort matches: supporting first, then by match_score descending
        matches.sort(key=lambda m: (m.is_caution, -m.match_score))

        # Compute statistics
        statistics = self._compute_statistics(payloads)

        # Compute summary
        same_outcome_count = sum(1 for p in payloads if p.outcome_code == proposed_outcome)
        consistency_rate = (
            Decimal(same_outcome_count) / Decimal(len(payloads))
            if payloads else Decimal("0")
        )

        precedent_confidence = self._compute_confidence(
            payloads, proposed_outcome, statistics
        )

        summary = PrecedentSummary(
            total_matched=len(payloads),
            same_outcome_count=same_outcome_count,
            consistency_rate=consistency_rate,
            appeal_stats=statistics.appeal_stats,
            precedent_confidence=precedent_confidence,
        )

        return PrecedentQueryResult(
            tier=tier,
            matches=matches,
            statistics=statistics,
            overlap_count=overlap_count,
            query_params=query_params,
            summary=summary,
        )

    def _create_match(
        self,
        payload: JudgmentPayload,
        tier: PrecedentQueryTier,
        proposed_outcome: str,
    ) -> PrecedentMatch:
        """Create a PrecedentMatch from a payload."""
        # Determine match type
        if tier == PrecedentQueryTier.TIER_0_EXACT_FINGERPRINT:
            match_type = "exact_fingerprint"
            match_score = Decimal("1.0")
        elif tier == PrecedentQueryTier.TIER_0_5_SAME_CODES:
            match_type = "same_exclusion_codes"
            match_score = Decimal("0.9")
        else:
            match_type = "overlapping_codes"
            match_score = Decimal("0.7")

        # Compute match factors
        match_factors = self._compute_match_factors(payload, tier)

        # Compute distinguish factors
        distinguish_factors = self._compute_distinguish_factors(payload, proposed_outcome)

        return PrecedentMatch.from_payload(
            payload=payload,
            cell_hash="",  # Would need cell lookup to get this
            match_type=match_type,
            match_score=match_score,
            match_factors=match_factors,
            distinguish_factors=distinguish_factors,
            proposed_outcome=proposed_outcome,
        )

    def _compute_match_factors(
        self,
        payload: JudgmentPayload,
        tier: PrecedentQueryTier,
    ) -> list[str]:
        """Compute the factors that made this a match."""
        factors: list[str] = []

        if tier == PrecedentQueryTier.TIER_0_EXACT_FINGERPRINT:
            factors.append("Exact fingerprint match (identical banded facts)")

        if payload.exclusion_codes:
            factors.append(f"Exclusion codes: {', '.join(payload.exclusion_codes)}")

        factors.append(f"Jurisdiction: {payload.jurisdiction_code}")
        factors.append(f"Decision level: {payload.decision_level}")

        return factors

    def _compute_distinguish_factors(
        self,
        payload: JudgmentPayload,
        proposed_outcome: str,
    ) -> list[str]:
        """Compute factors that distinguish this precedent from the current case."""
        factors: list[str] = []

        if payload.outcome_code != proposed_outcome:
            factors.append(
                f"Different outcome: precedent was {payload.outcome_code}, "
                f"proposed is {proposed_outcome}"
            )

        if payload.appealed:
            factors.append(f"Was appealed: {payload.appeal_outcome}")

        if payload.outcome_notable:
            factors.append(f"Notable case: {payload.outcome_notable}")

        return factors

    def _compute_statistics(
        self,
        payloads: list[JudgmentPayload],
    ) -> PrecedentStatistics:
        """Compute aggregated statistics from payloads."""
        if not payloads:
            return PrecedentStatistics()

        stats = PrecedentStatistics(total_matched=len(payloads))

        for payload in payloads:
            # Count by outcome
            outcome = payload.outcome_code
            stats.by_outcome[outcome] = stats.by_outcome.get(outcome, 0) + 1

            # Count by decision level
            level = payload.decision_level
            stats.by_decision_level[level] = stats.by_decision_level.get(level, 0) + 1

            # Appeal statistics
            if payload.appealed:
                stats.appeal_stats.total_appealed += 1
                if payload.appeal_outcome == "upheld":
                    stats.appeal_stats.upheld += 1
                elif payload.appeal_outcome == "overturned":
                    stats.appeal_stats.overturned += 1
                elif payload.appeal_outcome == "settled":
                    stats.appeal_stats.settled += 1
                elif payload.appeal_outcome == "pending":
                    stats.appeal_stats.pending += 1

            # Track temporal range
            decided_at = payload.decided_at
            if stats.most_recent_decided_at is None or decided_at > stats.most_recent_decided_at:
                stats.most_recent_decided_at = decided_at
            if stats.oldest_decided_at is None or decided_at < stats.oldest_decided_at:
                stats.oldest_decided_at = decided_at

        return stats

    def _compute_confidence(
        self,
        payloads: list[JudgmentPayload],
        proposed_outcome: str,
        statistics: PrecedentStatistics,
    ) -> Decimal:
        """
        Compute precedent confidence score using pc_v1 model.

        Formula:
            base_confidence = weighted_average(
                majority_pct * 0.30,
                upheld_rate * 0.25,
                recency_score * 0.20,
                policy_match_score * 0.15,
                decision_level_score * 0.10
            )

            overturn_penalty = compute_overturn_penalty(...)
            precedent_confidence = base_confidence - overturn_penalty
        """
        if not payloads:
            return Decimal("0.5")  # No data = neutral confidence

        # Majority percentage (same outcome)
        same_outcome = sum(1 for p in payloads if p.outcome_code == proposed_outcome)
        majority_pct = Decimal(same_outcome) / Decimal(len(payloads))

        # Upheld rate (from appeal statistics)
        upheld_rate = Decimal(str(statistics.appeal_stats.upheld_rate))

        # Recency score (simplified - most recent decision within 2 years = 1.0)
        recency_score = Decimal("0.8")  # Default - would compute based on decided_at

        # Policy match score (always 1.0 for now - same policy pack)
        policy_match_score = Decimal("1.0")

        # Decision level score
        # court/tribunal decisions have higher weight
        court_count = statistics.by_decision_level.get("court", 0)
        tribunal_count = statistics.by_decision_level.get("tribunal", 0)
        high_authority = court_count + tribunal_count
        decision_level_score = (
            Decimal("1.0") if high_authority > 0
            else Decimal("0.7")
        )

        # Weighted average
        base_confidence = (
            majority_pct * Decimal("0.30")
            + upheld_rate * Decimal("0.25")
            + recency_score * Decimal("0.20")
            + policy_match_score * Decimal("0.15")
            + decision_level_score * Decimal("0.10")
        )

        # Overturn penalty
        overturned_count = statistics.appeal_stats.overturned
        if overturned_count > 0:
            # Each overturned case reduces confidence
            penalty = min(
                Decimal("0.3"),  # Cap at 0.3
                Decimal(overturned_count) * Decimal("0.1")
            )
            base_confidence -= penalty

        # Ensure 0.0-1.0 range
        return max(Decimal("0.0"), min(Decimal("1.0"), base_confidence))


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Enums
    "PrecedentQueryTier",

    # Data classes
    "PrecedentQueryParams",
    "PrecedentMatch",
    "PrecedentSummary",
    "PrecedentQueryResult",

    # Engine
    "PrecedentQueryEngine",
]
