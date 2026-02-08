"""
DecisionGraph Precedent History Check Report Module

Implements precedent history checking with heat map visualization for
consistency analysis against historical decisions.

Key components:
- HeatMapEntry: Outcome distribution for a single exclusion code
- PrecedentHeatMap: Full heat map of decision patterns by code
- ConsistencyCheck: Result of consistency validation against precedents
- PrecedentHistoryReport: Complete report with history, heat map, and checks
- generate_precedent_history_report(): Main report generation function

This module works for both insurance (ClaimPilot) and banking (AML) domains
by querying the domain-agnostic PrecedentRegistry.

Usage:
    >>> from decisiongraph import PrecedentRegistry, Chain
    >>> from decisiongraph.precedent_check_report import generate_precedent_history_report
    >>>
    >>> chain = Chain()  # ... populated with precedents
    >>> registry = PrecedentRegistry(chain)
    >>>
    >>> # Generate report for an insurance claim
    >>> report = generate_precedent_history_report(
    ...     registry=registry,
    ...     namespace_prefix="claims.auto",
    ...     fingerprint_hash="abc123...",
    ...     exclusion_codes=["4.2.1", "4.3.3"],
    ...     proposed_outcome="deny",
    ... )
    >>>
    >>> # Check consistency
    >>> if report.consistency_check.is_consistent:
    ...     print("Decision aligns with precedent")
    ... else:
    ...     print(f"WARNING: {report.consistency_check.warning_message}")
    >>>
    >>> # View heat map
    >>> for entry in report.heat_map.entries:
    ...     print(f"{entry.code}: {entry.deny_rate:.0%} deny, {entry.pay_rate:.0%} pay")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING
from collections import defaultdict

from .judgment import JudgmentPayload

if TYPE_CHECKING:
    from .precedent_registry import PrecedentRegistry


# =============================================================================
# Exceptions
# =============================================================================

class PrecedentCheckError(Exception):
    """Base exception for precedent check errors."""
    pass


class InsufficientPrecedentsError(PrecedentCheckError):
    """Raised when not enough precedents exist for reliable analysis."""
    pass


# =============================================================================
# Heat Map Data Structures
# =============================================================================

@dataclass
class HeatMapEntry:
    """
    Outcome distribution for a single exclusion/reason code.

    Provides a "heat map" view of how cases with this code have been decided
    historically. Higher deny rates show "hotter" codes that typically result
    in denial.

    Attributes:
        code: The exclusion or reason code
        code_label: Human-readable label for the code
        total_count: Total precedents with this code
        pay_count: Number that resulted in pay/approve
        deny_count: Number that resulted in deny
        partial_count: Number that resulted in partial payment
        escalate_count: Number that were escalated
        appeal_count: Number that were appealed
        overturn_count: Number overturned on appeal
    """
    code: str
    code_label: str
    total_count: int
    pay_count: int = 0
    deny_count: int = 0
    partial_count: int = 0
    escalate_count: int = 0
    appeal_count: int = 0
    overturn_count: int = 0

    @property
    def pay_rate(self) -> float:
        """Rate of pay/approve outcomes (0.0-1.0)."""
        if self.total_count == 0:
            return 0.0
        return self.pay_count / self.total_count

    @property
    def deny_rate(self) -> float:
        """Rate of deny outcomes (0.0-1.0)."""
        if self.total_count == 0:
            return 0.0
        return self.deny_count / self.total_count

    @property
    def partial_rate(self) -> float:
        """Rate of partial outcomes (0.0-1.0)."""
        if self.total_count == 0:
            return 0.0
        return self.partial_count / self.total_count

    @property
    def escalate_rate(self) -> float:
        """Rate of escalation (0.0-1.0)."""
        if self.total_count == 0:
            return 0.0
        return self.escalate_count / self.total_count

    @property
    def appeal_rate(self) -> float:
        """Rate of appeals (0.0-1.0)."""
        if self.total_count == 0:
            return 0.0
        return self.appeal_count / self.total_count

    @property
    def overturn_rate(self) -> float:
        """Rate of overturns on appeal (0.0-1.0)."""
        if self.appeal_count == 0:
            return 0.0
        return self.overturn_count / self.appeal_count

    @property
    def heat_level(self) -> str:
        """
        Heat level indicator based on deny rate.

        Returns:
            "critical": >90% deny rate
            "high": 70-90% deny rate
            "medium": 40-70% deny rate
            "low": <40% deny rate
        """
        if self.deny_rate > 0.90:
            return "critical"
        elif self.deny_rate > 0.70:
            return "high"
        elif self.deny_rate > 0.40:
            return "medium"
        else:
            return "low"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "code": self.code,
            "code_label": self.code_label,
            "total_count": self.total_count,
            "pay_count": self.pay_count,
            "deny_count": self.deny_count,
            "partial_count": self.partial_count,
            "escalate_count": self.escalate_count,
            "appeal_count": self.appeal_count,
            "overturn_count": self.overturn_count,
            "pay_rate": self.pay_rate,
            "deny_rate": self.deny_rate,
            "partial_rate": self.partial_rate,
            "escalate_rate": self.escalate_rate,
            "appeal_rate": self.appeal_rate,
            "overturn_rate": self.overturn_rate,
            "heat_level": self.heat_level,
        }


@dataclass
class PrecedentHeatMap:
    """
    Complete heat map of decision patterns by code.

    Provides a visual representation of how different exclusion/reason
    codes have been decided historically. Useful for:
    - Identifying high-risk codes that typically result in denial
    - Spotting anomalies where decisions deviate from patterns
    - Training adjusters on expected outcomes

    Attributes:
        entries: List of HeatMapEntry objects, one per code
        generated_at: When the heat map was generated
        namespace_prefix: The namespace scope of the analysis
        total_precedents_analyzed: Total number of precedents analyzed
    """
    entries: list[HeatMapEntry]
    generated_at: str
    namespace_prefix: str
    total_precedents_analyzed: int

    @property
    def hottest_codes(self) -> list[HeatMapEntry]:
        """Get codes with >70% deny rate, sorted by deny rate descending."""
        return sorted(
            [e for e in self.entries if e.deny_rate > 0.70],
            key=lambda e: e.deny_rate,
            reverse=True
        )

    @property
    def most_appealed_codes(self) -> list[HeatMapEntry]:
        """Get codes with >15% appeal rate, sorted by appeal rate descending."""
        return sorted(
            [e for e in self.entries if e.appeal_rate > 0.15],
            key=lambda e: e.appeal_rate,
            reverse=True
        )

    @property
    def highest_overturn_codes(self) -> list[HeatMapEntry]:
        """Get codes with >20% overturn rate, sorted by overturn rate descending."""
        return sorted(
            [e for e in self.entries if e.overturn_rate > 0.20 and e.appeal_count >= 3],
            key=lambda e: e.overturn_rate,
            reverse=True
        )

    def get_entry_by_code(self, code: str) -> Optional[HeatMapEntry]:
        """Get heat map entry for a specific code."""
        for entry in self.entries:
            if entry.code == code:
                return entry
        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "entries": [e.to_dict() for e in self.entries],
            "generated_at": self.generated_at,
            "namespace_prefix": self.namespace_prefix,
            "total_precedents_analyzed": self.total_precedents_analyzed,
            "hottest_codes": [e.code for e in self.hottest_codes],
            "most_appealed_codes": [e.code for e in self.most_appealed_codes],
            "highest_overturn_codes": [e.code for e in self.highest_overturn_codes],
        }


# =============================================================================
# Consistency Check
# =============================================================================

@dataclass
class ConsistencyCheck:
    """
    Result of consistency check against precedent history.

    Validates whether a proposed decision aligns with historical precedents.
    Flags potential inconsistencies that may require additional justification.

    Attributes:
        proposed_outcome: The proposed decision outcome
        is_consistent: Whether the decision aligns with precedent
        consistency_score: Score from 0.0 (inconsistent) to 1.0 (perfectly consistent)
        warning_level: None, "advisory", "caution", or "critical"
        warning_message: Human-readable explanation if inconsistent
        supporting_precedents: Count of precedents supporting this outcome
        contrary_precedents: Count of precedents with different outcomes
        similar_cases_overturned: Count of similar cases that were overturned
        requires_escalation: Whether this should trigger escalation
        recommended_action: Suggested next step
    """
    proposed_outcome: str
    is_consistent: bool
    consistency_score: float
    warning_level: Optional[str] = None
    warning_message: Optional[str] = None
    supporting_precedents: int = 0
    contrary_precedents: int = 0
    similar_cases_overturned: int = 0
    requires_escalation: bool = False
    recommended_action: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "proposed_outcome": self.proposed_outcome,
            "is_consistent": self.is_consistent,
            "consistency_score": self.consistency_score,
            "warning_level": self.warning_level,
            "warning_message": self.warning_message,
            "supporting_precedents": self.supporting_precedents,
            "contrary_precedents": self.contrary_precedents,
            "similar_cases_overturned": self.similar_cases_overturned,
            "requires_escalation": self.requires_escalation,
            "recommended_action": self.recommended_action,
        }


# =============================================================================
# Precedent History Match
# =============================================================================

@dataclass
class PrecedentMatch:
    """
    A single precedent match from history.

    Attributes:
        precedent_id: ID of the matched precedent
        match_tier: Match quality (0=exact fingerprint, 0.5=same codes+outcome, 1=overlapping codes)
        overlap_score: For tier 1 matches, number of overlapping codes
        outcome_code: The outcome of this precedent
        decision_level: Authority level that decided
        decided_at: When decided
        appealed: Whether it was appealed
        appeal_outcome: Result of appeal if appealed
        anchor_facts_summary: Summary of key facts
    """
    precedent_id: str
    match_tier: float
    overlap_score: int
    outcome_code: str
    decision_level: str
    decided_at: str
    appealed: bool
    appeal_outcome: Optional[str]
    anchor_facts_summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "precedent_id": self.precedent_id,
            "match_tier": self.match_tier,
            "overlap_score": self.overlap_score,
            "outcome_code": self.outcome_code,
            "decision_level": self.decision_level,
            "decided_at": self.decided_at,
            "appealed": self.appealed,
            "appeal_outcome": self.appeal_outcome,
            "anchor_facts_summary": self.anchor_facts_summary,
        }


# =============================================================================
# Precedent History Report
# =============================================================================

@dataclass
class PrecedentHistoryReport:
    """
    Complete precedent history check report.

    Combines:
    - Direct matches from precedent query
    - Heat map of decision patterns by code
    - Consistency check for proposed decision
    - Recommendations and warnings

    Attributes:
        report_id: Unique identifier for this report
        generated_at: When the report was generated
        namespace_prefix: Namespace scope of the analysis
        fingerprint_hash: The fingerprint hash searched (if provided)
        exclusion_codes_searched: The exclusion codes searched
        proposed_outcome: The proposed decision outcome (if provided)

        tier0_matches: Exact fingerprint matches
        tier05_matches: Same codes + same outcome matches
        tier1_matches: Overlapping code matches

        heat_map: Decision pattern heat map
        consistency_check: Consistency validation result

        total_precedents_found: Total matching precedents
        has_binding_precedent: Whether a binding precedent exists
        binding_precedent_id: ID of binding precedent if exists

        warnings: List of warning messages
        recommendations: List of recommended actions
    """
    report_id: str
    generated_at: str
    namespace_prefix: str
    fingerprint_hash: Optional[str]
    exclusion_codes_searched: list[str]
    proposed_outcome: Optional[str]

    tier0_matches: list[PrecedentMatch]
    tier05_matches: list[PrecedentMatch]
    tier1_matches: list[PrecedentMatch]

    heat_map: PrecedentHeatMap
    consistency_check: Optional[ConsistencyCheck]

    total_precedents_found: int
    has_binding_precedent: bool
    binding_precedent_id: Optional[str]

    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def has_exact_match(self) -> bool:
        """Whether there is at least one exact (Tier 0) match."""
        return len(self.tier0_matches) > 0

    @property
    def match_confidence(self) -> str:
        """
        Confidence level based on matches found.

        Returns:
            "high": Exact fingerprint match exists
            "medium": Same codes + outcome matches exist
            "low": Only overlapping code matches
            "none": No matches found
        """
        if len(self.tier0_matches) > 0:
            return "high"
        elif len(self.tier05_matches) > 0:
            return "medium"
        elif len(self.tier1_matches) > 0:
            return "low"
        else:
            return "none"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "namespace_prefix": self.namespace_prefix,
            "fingerprint_hash": self.fingerprint_hash,
            "exclusion_codes_searched": self.exclusion_codes_searched,
            "proposed_outcome": self.proposed_outcome,
            "tier0_matches": [m.to_dict() for m in self.tier0_matches],
            "tier05_matches": [m.to_dict() for m in self.tier05_matches],
            "tier1_matches": [m.to_dict() for m in self.tier1_matches],
            "heat_map": self.heat_map.to_dict(),
            "consistency_check": self.consistency_check.to_dict() if self.consistency_check else None,
            "total_precedents_found": self.total_precedents_found,
            "has_binding_precedent": self.has_binding_precedent,
            "binding_precedent_id": self.binding_precedent_id,
            "has_exact_match": self.has_exact_match,
            "match_confidence": self.match_confidence,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
        }

    def format_summary(self) -> str:
        """Format a human-readable summary of the report."""
        lines = []
        lines.append("=" * 60)
        lines.append("PRECEDENT HISTORY CHECK REPORT")
        lines.append("=" * 60)
        lines.append(f"Report ID: {self.report_id}")
        lines.append(f"Generated: {self.generated_at}")
        lines.append(f"Namespace: {self.namespace_prefix}")
        lines.append("")

        # Match summary
        lines.append("PRECEDENT MATCHES")
        lines.append("-" * 40)
        lines.append(f"Tier 0 (Exact):       {len(self.tier0_matches)}")
        lines.append(f"Tier 0.5 (Same+Out):  {len(self.tier05_matches)}")
        lines.append(f"Tier 1 (Overlapping): {len(self.tier1_matches)}")
        lines.append(f"Total Found:          {self.total_precedents_found}")
        lines.append(f"Match Confidence:     {self.match_confidence.upper()}")
        lines.append("")

        # Binding precedent
        if self.has_binding_precedent:
            lines.append(f"BINDING PRECEDENT: {self.binding_precedent_id}")
            lines.append("")

        # Consistency check
        if self.consistency_check:
            lines.append("CONSISTENCY CHECK")
            lines.append("-" * 40)
            lines.append(f"Proposed Outcome:   {self.consistency_check.proposed_outcome}")
            lines.append(f"Consistent:         {'YES' if self.consistency_check.is_consistent else 'NO'}")
            lines.append(f"Consistency Score:  {self.consistency_check.consistency_score:.1%}")
            if self.consistency_check.warning_level:
                lines.append(f"Warning Level:      {self.consistency_check.warning_level.upper()}")
            if self.consistency_check.warning_message:
                lines.append(f"Warning:            {self.consistency_check.warning_message}")
            lines.append(f"Supporting:         {self.consistency_check.supporting_precedents}")
            lines.append(f"Contrary:           {self.consistency_check.contrary_precedents}")
            if self.consistency_check.requires_escalation:
                lines.append("*** ESCALATION REQUIRED ***")
            lines.append("")

        # Heat map summary
        lines.append("HEAT MAP SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Codes Analyzed:     {len(self.heat_map.entries)}")
        lines.append(f"Precedents in Map:  {self.heat_map.total_precedents_analyzed}")

        if self.heat_map.hottest_codes:
            lines.append(f"Hottest Codes:      {', '.join(e.code for e in self.heat_map.hottest_codes[:3])}")

        if self.heat_map.highest_overturn_codes:
            lines.append(f"High Overturn:      {', '.join(e.code for e in self.heat_map.highest_overturn_codes[:3])}")
        lines.append("")

        # Detailed heat map
        if self.heat_map.entries:
            lines.append("HEAT MAP DETAIL")
            lines.append("-" * 40)
            lines.append(f"{'Code':<12} {'Count':>6} {'Deny':>8} {'Pay':>8} {'Appeal':>8} {'Heat':>8}")
            lines.append("-" * 52)
            for entry in sorted(self.heat_map.entries, key=lambda e: e.deny_rate, reverse=True):
                lines.append(
                    f"{entry.code:<12} {entry.total_count:>6} "
                    f"{entry.deny_rate:>7.0%} {entry.pay_rate:>7.0%} "
                    f"{entry.appeal_rate:>7.0%} {entry.heat_level:>8}"
                )
            lines.append("")

        # Warnings
        if self.warnings:
            lines.append("WARNINGS")
            lines.append("-" * 40)
            for warning in self.warnings:
                lines.append(f"  - {warning}")
            lines.append("")

        # Recommendations
        if self.recommendations:
            lines.append("RECOMMENDATIONS")
            lines.append("-" * 40)
            for rec in self.recommendations:
                lines.append(f"  - {rec}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)


# =============================================================================
# Report Generation
# =============================================================================

def _payload_to_match(
    payload: JudgmentPayload,
    tier: float,
    overlap: int = 0,
) -> PrecedentMatch:
    """Convert a JudgmentPayload to a PrecedentMatch."""
    # Build anchor facts summary
    facts_summary = {}
    for af in payload.anchor_facts[:5]:  # Limit to 5 key facts
        facts_summary[af.field_id] = af.value

    return PrecedentMatch(
        precedent_id=payload.precedent_id,
        match_tier=tier,
        overlap_score=overlap,
        outcome_code=payload.outcome_code,
        decision_level=payload.decision_level,
        decided_at=payload.decided_at,
        appealed=payload.appealed,
        appeal_outcome=payload.appeal_outcome,
        anchor_facts_summary=facts_summary,
    )


def _build_heat_map(
    payloads: list[JudgmentPayload],
    namespace_prefix: str,
    code_labels: Optional[dict[str, str]] = None,
) -> PrecedentHeatMap:
    """Build a heat map from a list of precedent payloads."""
    from .cell import get_current_timestamp

    if code_labels is None:
        code_labels = {}

    # Aggregate by code
    code_stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "total": 0,
            "pay": 0,
            "deny": 0,
            "partial": 0,
            "escalate": 0,
            "appealed": 0,
            "overturned": 0,
        }
    )

    for payload in payloads:
        for code in payload.exclusion_codes + payload.reason_codes:
            stats = code_stats[code]
            stats["total"] += 1

            # Count by outcome
            if payload.outcome_code == "pay":
                stats["pay"] += 1
            elif payload.outcome_code == "deny":
                stats["deny"] += 1
            elif payload.outcome_code == "partial":
                stats["partial"] += 1
            elif payload.outcome_code == "escalate":
                stats["escalate"] += 1

            # Count appeals
            if payload.appealed:
                stats["appealed"] += 1
                if payload.appeal_outcome == "overturned":
                    stats["overturned"] += 1

    # Build entries
    entries = []
    for code, stats in code_stats.items():
        entries.append(HeatMapEntry(
            code=code,
            code_label=code_labels.get(code, code),
            total_count=stats["total"],
            pay_count=stats["pay"],
            deny_count=stats["deny"],
            partial_count=stats["partial"],
            escalate_count=stats["escalate"],
            appeal_count=stats["appealed"],
            overturn_count=stats["overturned"],
        ))

    # Sort by total count descending
    entries.sort(key=lambda e: e.total_count, reverse=True)

    return PrecedentHeatMap(
        entries=entries,
        generated_at=get_current_timestamp(),
        namespace_prefix=namespace_prefix,
        total_precedents_analyzed=len(payloads),
    )


def _check_consistency(
    proposed_outcome: str,
    tier0_matches: list[PrecedentMatch],
    tier05_matches: list[PrecedentMatch],
    tier1_matches: list[PrecedentMatch],
    heat_map: PrecedentHeatMap,
    exclusion_codes: list[str],
) -> ConsistencyCheck:
    """
    Check consistency of proposed outcome against precedents.

    Consistency Rules:
    1. If Tier 0 matches exist, proposed must match majority outcome
    2. If no Tier 0 but Tier 0.5 matches, strong advisory
    3. For Tier 1 only, check heat map for expected pattern
    4. High overturn codes require extra scrutiny
    """
    all_matches = tier0_matches + tier05_matches + tier1_matches

    if not all_matches:
        # No precedents - first-of-kind case
        return ConsistencyCheck(
            proposed_outcome=proposed_outcome,
            is_consistent=True,
            consistency_score=0.5,
            warning_level="advisory",
            warning_message="No precedent history found. This may be a first-of-kind case.",
            supporting_precedents=0,
            contrary_precedents=0,
            similar_cases_overturned=0,
            requires_escalation=False,
            recommended_action="Document decision rationale thoroughly for future precedent."
        )

    # Count supporting vs contrary (v2: only terminal ALLOW/BLOCK are decisive)
    # Map raw outcome_codes to canonical dispositions for v2 comparison
    _ALLOW_CODES = {"pay", "paid", "approve", "approved", "accept", "clear", "cleared", "pass", "no action", "close"}
    _BLOCK_CODES = {"deny", "denied", "decline", "declined", "reject", "block", "blocked", "refuse", "hard stop", "exit"}
    _EDD_CODES = {"review", "investigate", "escalate", "escalated", "hold", "pending", "manual review", "pass with edd"}

    def _to_canonical_disp(code: str) -> str:
        c = code.lower().strip()
        if c in _ALLOW_CODES:
            return "ALLOW"
        if c in _BLOCK_CODES:
            return "BLOCK"
        if c in _EDD_CODES:
            return "EDD"
        return "UNKNOWN"

    proposed_disp = _to_canonical_disp(proposed_outcome)

    # INV-003/INV-005: Only count terminal (ALLOW/BLOCK) outcomes in confidence
    decisive_matches = [m for m in all_matches if _to_canonical_disp(m.outcome_code) in ("ALLOW", "BLOCK")]
    supporting = sum(1 for m in decisive_matches if _to_canonical_disp(m.outcome_code) == proposed_disp)
    contrary = sum(1 for m in decisive_matches if _to_canonical_disp(m.outcome_code) != proposed_disp
                   and {_to_canonical_disp(m.outcome_code), proposed_disp} == {"ALLOW", "BLOCK"})

    # Count overturned cases with same proposed outcome
    overturned = sum(
        1 for m in all_matches
        if m.outcome_code == proposed_outcome
        and m.appealed
        and m.appeal_outcome == "overturned"
    )

    # Calculate consistency score (v2: decisive precedents only)
    if len(decisive_matches) > 0:
        consistency_score = supporting / len(decisive_matches)
    else:
        consistency_score = 0.5

    # Determine warning level
    warning_level = None
    warning_message = None
    requires_escalation = False
    recommended_action = None

    # Check Tier 0 matches (binding precedent)
    if tier0_matches:
        tier0_outcomes = [m.outcome_code for m in tier0_matches]
        majority_outcome = max(set(tier0_outcomes), key=tier0_outcomes.count)

        if proposed_outcome != majority_outcome:
            warning_level = "critical"
            warning_message = (
                f"Proposed '{proposed_outcome}' conflicts with binding precedent "
                f"(majority outcome: '{majority_outcome}')"
            )
            requires_escalation = True
            recommended_action = "Escalate to manager with justification for deviation from precedent."

    # Check Tier 0.5 matches if no Tier 0 issues
    elif tier05_matches and warning_level is None:
        tier05_outcomes = [m.outcome_code for m in tier05_matches]
        majority_outcome = max(set(tier05_outcomes), key=tier05_outcomes.count)

        if proposed_outcome != majority_outcome:
            if consistency_score < 0.3:
                warning_level = "critical"
                warning_message = (
                    f"Proposed '{proposed_outcome}' is rare for similar cases "
                    f"(only {consistency_score:.0%} consistency)"
                )
                requires_escalation = True
            else:
                warning_level = "caution"
                warning_message = (
                    f"Proposed '{proposed_outcome}' differs from common outcome "
                    f"for similar cases ({majority_outcome})"
                )
            recommended_action = "Review similar cases before finalizing decision."

    # Check heat map patterns
    if warning_level is None and exclusion_codes:
        for code in exclusion_codes:
            entry = heat_map.get_entry_by_code(code)
            if entry:
                if proposed_outcome == "pay" and entry.deny_rate > 0.85:
                    warning_level = "caution"
                    warning_message = (
                        f"Code {code} has {entry.deny_rate:.0%} historical deny rate. "
                        f"Proposed 'pay' may need additional justification."
                    )
                    recommended_action = "Document exception justification clearly."
                    break
                elif proposed_outcome == "deny" and entry.pay_rate > 0.85:
                    warning_level = "caution"
                    warning_message = (
                        f"Code {code} has {entry.pay_rate:.0%} historical pay rate. "
                        f"Proposed 'deny' may need additional justification."
                    )
                    recommended_action = "Verify exclusion applies to this specific case."
                    break

    # Check overturn history
    if overturned > 0 and warning_level is None:
        warning_level = "advisory"
        warning_message = (
            f"{overturned} similar case(s) with '{proposed_outcome}' outcome "
            f"were overturned on appeal. Review appeal reasons."
        )
        recommended_action = "Consider factors that led to previous overturns."

    # Determine if consistent
    is_consistent = warning_level not in ("critical",)

    # If still no warnings, check if reasonably consistent
    if warning_level is None and consistency_score >= 0.6:
        recommended_action = "Decision aligns with precedent. Proceed with confidence."
    elif warning_level is None and consistency_score >= 0.4:
        warning_level = "advisory"
        warning_message = "Mixed precedent history. Decision is reasonable but not strongly supported."
        recommended_action = "Consider documenting additional rationale."
    elif warning_level is None:
        warning_level = "caution"
        warning_message = f"Low consistency ({consistency_score:.0%}) with historical precedents."
        recommended_action = "Review case details carefully before proceeding."

    return ConsistencyCheck(
        proposed_outcome=proposed_outcome,
        is_consistent=is_consistent,
        consistency_score=consistency_score,
        warning_level=warning_level,
        warning_message=warning_message,
        supporting_precedents=supporting,
        contrary_precedents=contrary,
        similar_cases_overturned=overturned,
        requires_escalation=requires_escalation,
        recommended_action=recommended_action,
    )


def generate_precedent_history_report(
    registry: PrecedentRegistry,
    namespace_prefix: str,
    fingerprint_hash: Optional[str] = None,
    exclusion_codes: Optional[list[str]] = None,
    reason_codes: Optional[list[str]] = None,
    proposed_outcome: Optional[str] = None,
    code_labels: Optional[dict[str, str]] = None,
    as_of: Optional[str] = None,
    max_matches_per_tier: int = 20,
) -> PrecedentHistoryReport:
    """
    Generate a comprehensive precedent history check report.

    This function queries the precedent registry and builds a report with:
    - Matched precedents at Tier 0, 0.5, and 1
    - Heat map of decision patterns by code
    - Consistency check for proposed outcome
    - Warnings and recommendations

    Args:
        registry: The PrecedentRegistry to query
        namespace_prefix: Namespace prefix for the query (e.g., "claims.auto")
        fingerprint_hash: Optional fingerprint hash for Tier 0 matching
        exclusion_codes: Optional exclusion codes for Tier 0.5/1 matching
        reason_codes: Optional reason codes for additional matching
        proposed_outcome: Optional proposed decision to check consistency
        code_labels: Optional mapping of codes to human-readable labels
        as_of: Optional bitemporal cutoff timestamp
        max_matches_per_tier: Maximum matches to return per tier (default: 20)

    Returns:
        PrecedentHistoryReport with complete analysis

    Raises:
        PrecedentCheckError: If query parameters are invalid

    Example:
        >>> report = generate_precedent_history_report(
        ...     registry=registry,
        ...     namespace_prefix="claims.auto",
        ...     fingerprint_hash="abc123...",
        ...     exclusion_codes=["4.2.1", "4.3.3"],
        ...     proposed_outcome="deny",
        ... )
        >>> print(report.format_summary())
    """
    from uuid import uuid4
    from .cell import get_current_timestamp

    if not namespace_prefix:
        raise PrecedentCheckError("namespace_prefix is required")

    if not fingerprint_hash and not exclusion_codes and not reason_codes:
        raise PrecedentCheckError(
            "At least one of fingerprint_hash, exclusion_codes, or reason_codes is required"
        )

    tier0_matches: list[PrecedentMatch] = []
    tier05_matches: list[PrecedentMatch] = []
    tier1_matches: list[PrecedentMatch] = []
    all_payloads: list[JudgmentPayload] = []

    # Tier 0: Exact fingerprint match
    if fingerprint_hash:
        tier0_payloads = registry.find_by_fingerprint(
            fingerprint_hash=fingerprint_hash,
            namespace_prefix=namespace_prefix,
            as_of=as_of,
        )
        for payload in tier0_payloads[:max_matches_per_tier]:
            tier0_matches.append(_payload_to_match(payload, tier=0.0))
        all_payloads.extend(tier0_payloads)

    # Tier 0.5/1: Code-based matching
    all_codes = (exclusion_codes or []) + (reason_codes or [])
    if all_codes:
        # Tier 0.5: Same codes + same outcome
        if proposed_outcome:
            tier05_results = registry.find_by_exclusion_codes(
                codes=exclusion_codes or [],
                namespace_prefix=namespace_prefix,
                outcome=proposed_outcome,
                min_overlap=len(exclusion_codes) if exclusion_codes else 1,
                as_of=as_of,
            )
            for payload, overlap in tier05_results[:max_matches_per_tier]:
                if payload.precedent_id not in [m.precedent_id for m in tier0_matches]:
                    tier05_matches.append(_payload_to_match(payload, tier=0.5, overlap=overlap))
                    if payload not in all_payloads:
                        all_payloads.append(payload)

        # Tier 1: Any overlapping codes
        if exclusion_codes:
            tier1_results = registry.find_by_exclusion_codes(
                codes=exclusion_codes,
                namespace_prefix=namespace_prefix,
                min_overlap=1,
                as_of=as_of,
            )
            for payload, overlap in tier1_results[:max_matches_per_tier]:
                existing_ids = (
                    [m.precedent_id for m in tier0_matches] +
                    [m.precedent_id for m in tier05_matches]
                )
                if payload.precedent_id not in existing_ids:
                    tier1_matches.append(_payload_to_match(payload, tier=1.0, overlap=overlap))
                    if payload not in all_payloads:
                        all_payloads.append(payload)

        # Also search by reason codes
        if reason_codes:
            reason_results = registry.find_by_reason_codes(
                reason_codes=reason_codes,
                namespace_prefix=namespace_prefix,
                min_overlap=1,
                as_of=as_of,
            )
            for payload, overlap in reason_results[:max_matches_per_tier]:
                existing_ids = (
                    [m.precedent_id for m in tier0_matches] +
                    [m.precedent_id for m in tier05_matches] +
                    [m.precedent_id for m in tier1_matches]
                )
                if payload.precedent_id not in existing_ids:
                    tier1_matches.append(_payload_to_match(payload, tier=1.0, overlap=overlap))
                    if payload not in all_payloads:
                        all_payloads.append(payload)

    # Build heat map
    heat_map = _build_heat_map(all_payloads, namespace_prefix, code_labels)

    # Check consistency
    consistency_check = None
    if proposed_outcome:
        consistency_check = _check_consistency(
            proposed_outcome=proposed_outcome,
            tier0_matches=tier0_matches,
            tier05_matches=tier05_matches,
            tier1_matches=tier1_matches,
            heat_map=heat_map,
            exclusion_codes=exclusion_codes or [],
        )

    # Determine binding precedent
    has_binding = len(tier0_matches) > 0
    binding_id = tier0_matches[0].precedent_id if has_binding else None

    # Build warnings
    warnings = []
    if has_binding and consistency_check and not consistency_check.is_consistent:
        warnings.append("Proposed decision conflicts with binding precedent")
    if heat_map.highest_overturn_codes:
        warnings.append(
            f"High overturn rate for codes: {', '.join(e.code for e in heat_map.highest_overturn_codes[:3])}"
        )
    if not all_payloads:
        warnings.append("No precedent history found - first-of-kind case")

    # Build recommendations
    recommendations = []
    if consistency_check and consistency_check.recommended_action:
        recommendations.append(consistency_check.recommended_action)
    if consistency_check and consistency_check.requires_escalation:
        recommendations.append("Escalate to senior decision-maker before proceeding")
    if has_binding:
        recommendations.append(f"Review binding precedent {binding_id}")

    return PrecedentHistoryReport(
        report_id=str(uuid4()),
        generated_at=get_current_timestamp(),
        namespace_prefix=namespace_prefix,
        fingerprint_hash=fingerprint_hash,
        exclusion_codes_searched=exclusion_codes or [],
        proposed_outcome=proposed_outcome,
        tier0_matches=tier0_matches,
        tier05_matches=tier05_matches,
        tier1_matches=tier1_matches,
        heat_map=heat_map,
        consistency_check=consistency_check,
        total_precedents_found=len(tier0_matches) + len(tier05_matches) + len(tier1_matches),
        has_binding_precedent=has_binding,
        binding_precedent_id=binding_id,
        warnings=warnings,
        recommendations=recommendations,
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Exceptions
    "PrecedentCheckError",
    "InsufficientPrecedentsError",

    # Data classes
    "HeatMapEntry",
    "PrecedentHeatMap",
    "ConsistencyCheck",
    "PrecedentMatch",
    "PrecedentHistoryReport",

    # Functions
    "generate_precedent_history_report",
]
