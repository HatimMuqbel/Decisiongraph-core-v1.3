"""
DecisionGraph Precedent System: Precedent Registry Module

This module implements the PrecedentRegistry following the WitnessRegistry pattern.
The registry provides a stateless query layer for JUDGMENT cells in the chain.

Key components:
- PrecedentStatistics: Aggregated statistics for a set of precedents
- PrecedentRegistry: Stateless chain-sourced precedent lookup

Design Principles:
- Stateless: Always rebuilds from chain state (no caching)
- Chain is source of truth
- Bitemporal: Uses header.system_time for filtering
- Namespace-scoped: Queries are scoped to namespace prefixes

Bitemporal Query Rule:
    WHERE cell.header.system_time <= :evaluated_at

This ensures we only see precedents that existed at the time of evaluation,
enabling "what would we have seen at time T" queries.

Usage Example:
    >>> from decisiongraph import Chain, PrecedentRegistry
    >>>
    >>> chain = Chain()  # ... populate with cells
    >>> registry = PrecedentRegistry(chain)
    >>>
    >>> # Find precedents by fingerprint (Tier 0)
    >>> matches = registry.find_by_fingerprint(
    ...     fingerprint_hash="abc123...",
    ...     namespace_prefix="claims",
    ...     as_of="2026-01-15T12:00:00Z"
    ... )
    >>>
    >>> # Get statistics
    >>> stats = registry.get_statistics(fingerprint_hash, "claims")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING

from kernel.foundation.cell import CellType, DecisionCell, validate_timestamp
from kernel.foundation.judgment import JudgmentPayload, parse_judgment_payload, is_judgment_cell

if TYPE_CHECKING:
    from kernel.foundation.chain import Chain


# =============================================================================
# Exceptions
# =============================================================================

class PrecedentRegistryError(Exception):
    """Base exception for precedent registry errors."""
    pass


class InvalidQueryError(PrecedentRegistryError):
    """Raised when a query is invalid."""
    pass


# =============================================================================
# Statistics
# =============================================================================

@dataclass
class AppealStatistics:
    """
    Aggregated appeal statistics for a set of precedents.

    Attributes:
        total_appealed: Number of cases that were appealed
        upheld: Number upheld on appeal
        overturned: Number overturned on appeal
        settled: Number settled on appeal
        pending: Number with pending appeals
    """
    total_appealed: int = 0
    upheld: int = 0
    overturned: int = 0
    settled: int = 0
    pending: int = 0

    @property
    def upheld_rate(self) -> float:
        """Rate of appeals that were upheld (0.0-1.0)."""
        if self.total_appealed == 0:
            return 1.0  # No appeals = perfect record
        decided = self.upheld + self.overturned + self.settled
        if decided == 0:
            return 1.0
        return self.upheld / decided


@dataclass
class PrecedentStatistics:
    """
    Aggregated statistics for a set of precedents.

    Provides high-level metrics for precedent-based confidence scoring.

    Attributes:
        total_matched: Total number of matching precedents
        by_outcome: Count by outcome code
        by_decision_level: Count by decision level
        appeal_stats: Appeal statistics
        most_recent_decided_at: Most recent decision date
        oldest_decided_at: Oldest decision date
    """
    total_matched: int = 0
    by_outcome: dict[str, int] = field(default_factory=dict)
    by_decision_level: dict[str, int] = field(default_factory=dict)
    appeal_stats: AppealStatistics = field(default_factory=AppealStatistics)
    most_recent_decided_at: Optional[str] = None
    oldest_decided_at: Optional[str] = None

    def consistency_rate(self, outcome_code: str) -> float:
        """
        Calculate consistency rate for a specific outcome.

        Args:
            outcome_code: The outcome to check consistency for

        Returns:
            Rate of precedents with the same outcome (0.0-1.0)
        """
        if self.total_matched == 0:
            return 0.0
        same_outcome = self.by_outcome.get(outcome_code, 0)
        return same_outcome / self.total_matched

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "total_matched": self.total_matched,
            "by_outcome": self.by_outcome,
            "by_decision_level": self.by_decision_level,
            "appeal_stats": {
                "total_appealed": self.appeal_stats.total_appealed,
                "upheld": self.appeal_stats.upheld,
                "overturned": self.appeal_stats.overturned,
                "settled": self.appeal_stats.settled,
                "pending": self.appeal_stats.pending,
                "upheld_rate": self.appeal_stats.upheld_rate,
            },
            "most_recent_decided_at": self.most_recent_decided_at,
            "oldest_decided_at": self.oldest_decided_at,
        }


# =============================================================================
# Precedent Registry
# =============================================================================

class PrecedentRegistry:
    """
    Stateless query layer for JUDGMENT cells in the chain.

    PrecedentRegistry follows the WitnessRegistry pattern: it provides
    query methods but does NOT cache results. All queries rebuild from
    chain state to ensure consistency.

    The registry supports three query tiers:
    - Tier 0: Exact fingerprint match
    - Tier 0.5: Same exclusion codes + same outcome
    - Tier 1: Overlapping exclusion codes

    Bitemporal queries use header.system_time for filtering, enabling
    "what would we have seen at time T" queries.

    Attributes:
        chain: The Chain instance to query (stored as reference)

    Examples:
        >>> registry = PrecedentRegistry(chain)
        >>>
        >>> # Find by fingerprint (Tier 0)
        >>> matches = registry.find_by_fingerprint(
        ...     fingerprint_hash="abc123...",
        ...     namespace_prefix="claims"
        ... )
        >>>
        >>> # Find by exclusion codes (Tier 0.5/1)
        >>> matches = registry.find_by_exclusion_codes(
        ...     codes=["4.2.1", "4.3.3"],
        ...     namespace_prefix="claims",
        ...     outcome="deny",
        ...     min_overlap=1
        ... )
        >>>
        >>> # Get statistics
        >>> stats = registry.get_statistics(fingerprint_hash, "claims")
    """

    def __init__(self, chain: Chain) -> None:
        """
        Create a PrecedentRegistry bound to a Chain.

        The registry does NOT store precedents - it rebuilds from chain state
        on each query. This ensures the registry always reflects current chain
        state without cache invalidation complexity.

        Args:
            chain: The Chain instance to query
        """
        self.chain = chain

    def find_by_fingerprint(
        self,
        fingerprint_hash: str,
        namespace_prefix: str,
        as_of: Optional[str] = None,
    ) -> list[JudgmentPayload]:
        """
        Find precedents with exact fingerprint match (Tier 0).

        This is the highest-quality match: identical banded facts produce
        identical fingerprints.

        Args:
            fingerprint_hash: The fingerprint hash to match
            namespace_prefix: Namespace prefix to search (e.g., "claims")
            as_of: Bitemporal cutoff - only return precedents where
                   header.system_time <= as_of (ISO 8601 timestamp)

        Returns:
            List of JudgmentPayload with matching fingerprint

        Raises:
            InvalidQueryError: If fingerprint_hash is invalid
        """
        if not fingerprint_hash:
            raise InvalidQueryError("fingerprint_hash cannot be empty")

        # Validate hash format
        if len(fingerprint_hash) != 64:
            raise InvalidQueryError("fingerprint_hash must be 64-character hex string")

        payloads = self._scan_judgment_cells(namespace_prefix, as_of)

        return [
            payload for payload in payloads
            if payload.fingerprint_hash == fingerprint_hash
        ]

    def find_by_exclusion_codes(
        self,
        codes: list[str],
        namespace_prefix: str,
        outcome: Optional[str] = None,
        min_overlap: int = 1,
        as_of: Optional[str] = None,
    ) -> list[tuple[JudgmentPayload, int]]:
        """
        Find precedents with overlapping exclusion codes (Tier 0.5/1).

        Tier 0.5: Same codes AND same outcome
        Tier 1: Overlapping codes (regardless of outcome)

        Args:
            codes: List of exclusion codes to match
            namespace_prefix: Namespace prefix to search
            outcome: If provided, only return precedents with this outcome (Tier 0.5)
            min_overlap: Minimum number of codes that must overlap (default: 1)
            as_of: Bitemporal cutoff timestamp

        Returns:
            List of (JudgmentPayload, overlap_count) tuples, sorted by overlap descending

        Raises:
            InvalidQueryError: If codes is empty or min_overlap is invalid
        """
        if not codes:
            raise InvalidQueryError("codes cannot be empty")
        if min_overlap < 1:
            raise InvalidQueryError("min_overlap must be at least 1")

        codes_set = set(codes)
        payloads = self._scan_judgment_cells(namespace_prefix, as_of)

        results: list[tuple[JudgmentPayload, int]] = []
        for payload in payloads:
            # Check outcome filter
            if outcome is not None and payload.outcome_code != outcome:
                continue

            # Compute overlap
            payload_codes = set(payload.exclusion_codes)
            overlap = len(codes_set & payload_codes)

            if overlap >= min_overlap:
                results.append((payload, overlap))

        # Sort by overlap descending, then by decided_at descending
        results.sort(key=lambda x: (-x[1], x[0].decided_at), reverse=False)
        results.sort(key=lambda x: x[1], reverse=True)

        return results

    def find_by_reason_codes(
        self,
        reason_codes: list[str],
        namespace_prefix: str,
        min_overlap: int = 1,
        as_of: Optional[str] = None,
    ) -> list[tuple[JudgmentPayload, int]]:
        """
        Find precedents with overlapping reason codes.

        Similar to find_by_exclusion_codes but matches on reason_codes field.

        Args:
            reason_codes: List of reason codes to match
            namespace_prefix: Namespace prefix to search
            min_overlap: Minimum number of codes that must overlap
            as_of: Bitemporal cutoff timestamp

        Returns:
            List of (JudgmentPayload, overlap_count) tuples
        """
        if not reason_codes:
            raise InvalidQueryError("reason_codes cannot be empty")
        if min_overlap < 1:
            raise InvalidQueryError("min_overlap must be at least 1")

        codes_set = set(reason_codes)
        payloads = self._scan_judgment_cells(namespace_prefix, as_of)

        results: list[tuple[JudgmentPayload, int]] = []
        for payload in payloads:
            payload_codes = set(payload.reason_codes)
            overlap = len(codes_set & payload_codes)

            if overlap >= min_overlap:
                results.append((payload, overlap))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    # Alias: banking domain uses "signal_codes" instead of "exclusion_codes"
    find_by_signal_codes = find_by_exclusion_codes

    def get_statistics(
        self,
        fingerprint_hash: str,
        namespace_prefix: str,
        as_of: Optional[str] = None,
    ) -> PrecedentStatistics:
        """
        Get aggregated statistics for precedents matching a fingerprint.

        This provides the metrics needed for confidence scoring:
        - Total matches
        - Distribution by outcome
        - Appeal statistics
        - Temporal range

        Args:
            fingerprint_hash: The fingerprint hash to match
            namespace_prefix: Namespace prefix to search
            as_of: Bitemporal cutoff timestamp

        Returns:
            PrecedentStatistics for matching precedents
        """
        matches = self.find_by_fingerprint(fingerprint_hash, namespace_prefix, as_of)

        if not matches:
            return PrecedentStatistics()

        stats = PrecedentStatistics(total_matched=len(matches))

        for payload in matches:
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

    def get_statistics_by_codes(
        self,
        exclusion_codes: list[str],
        namespace_prefix: str,
        min_overlap: int = 1,
        as_of: Optional[str] = None,
    ) -> PrecedentStatistics:
        """
        Get aggregated statistics for precedents matching exclusion codes.

        Args:
            exclusion_codes: List of exclusion codes to match
            namespace_prefix: Namespace prefix to search
            min_overlap: Minimum number of codes that must overlap
            as_of: Bitemporal cutoff timestamp

        Returns:
            PrecedentStatistics for matching precedents
        """
        matches = self.find_by_exclusion_codes(
            exclusion_codes, namespace_prefix, min_overlap=min_overlap, as_of=as_of
        )

        if not matches:
            return PrecedentStatistics()

        payloads = [payload for payload, _ in matches]
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

    def count_by_outcome(
        self,
        namespace_prefix: str,
        as_of: Optional[str] = None,
    ) -> dict[str, int]:
        """
        Count all precedents by outcome code.

        Args:
            namespace_prefix: Namespace prefix to search
            as_of: Bitemporal cutoff timestamp

        Returns:
            Dict mapping outcome_code to count
        """
        payloads = self._scan_judgment_cells(namespace_prefix, as_of)
        counts: dict[str, int] = {}
        for payload in payloads:
            outcome = payload.outcome_code
            counts[outcome] = counts.get(outcome, 0) + 1
        return counts

    def _scan_judgment_cells(
        self,
        namespace_prefix: str,
        as_of: Optional[str] = None,
    ) -> list[JudgmentPayload]:
        """
        Scan chain for JUDGMENT cells matching namespace and time constraints.

        This is the core stateless rebuild logic. It scans all cells in the
        chain and extracts JUDGMENT payloads that match the query constraints.

        Args:
            namespace_prefix: Namespace prefix to filter cells
            as_of: Bitemporal cutoff - only cells where header.system_time <= as_of

        Returns:
            List of JudgmentPayload from matching cells
        """
        # Validate as_of if provided
        if as_of is not None and not validate_timestamp(as_of):
            raise InvalidQueryError(f"Invalid as_of timestamp format: {as_of}")

        payloads: list[JudgmentPayload] = []

        # Scan all JUDGMENT cells in the chain
        for cell in self.chain.cells:
            # Check cell type
            if not is_judgment_cell(cell):
                continue

            # Check namespace prefix
            if not cell.fact.namespace.startswith(namespace_prefix):
                # Also check exact match
                if cell.fact.namespace != namespace_prefix:
                    continue

            # Check bitemporal constraint
            if as_of is not None:
                if cell.header.system_time > as_of:
                    continue

            # Parse and add payload
            try:
                payload = parse_judgment_payload(cell)
                payloads.append(payload)
            except Exception:
                # Skip malformed JUDGMENT cells
                continue

        return payloads


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Exceptions
    "PrecedentRegistryError",
    "InvalidQueryError",

    # Data classes
    "AppealStatistics",
    "PrecedentStatistics",

    # Registry
    "PrecedentRegistry",
]
