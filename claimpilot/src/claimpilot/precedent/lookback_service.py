"""
ClaimPilot Precedent System: Temporal Look-Back Service

This module implements jurisdiction-aware temporal look-back for cumulative
rule enforcement. Critical for Ontario HTA 48.3 "warn range" escalation.

Key Concept:
Some regulatory violations are cumulative - the Nth occurrence within a
look-back window triggers different (harsher) consequences than the 1st.

Ontario Example (HTA 48.3 - BAC Warn Range 0.05-0.079):
- 1st occurrence: 3-day suspension, $250 fine → ESCALATE
- 2nd occurrence (10yr): 7-day suspension, $550 fine → ESCALATE
- 3rd occurrence (10yr): 30-day + Ignition Interlock → DENY
  (Driver loses authority under OAP1:4.1.2 if no interlock installed)

Design Principles:
- Privacy-preserving: Uses hashed subject IDs, never raw PII
- Jurisdiction-aware: Different provinces/states have different windows
- Deterministic: Same query always returns same count
- Auditable: Returns full history, not just count
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from decisiongraph.chain import Chain


# =============================================================================
# Jurisdiction Look-Back Rules
# =============================================================================

class LookbackWindow(Enum):
    """Standard look-back windows used across jurisdictions."""
    YEARS_3 = timedelta(days=365 * 3)
    YEARS_5 = timedelta(days=365 * 5)
    YEARS_7 = timedelta(days=365 * 7)
    YEARS_10 = timedelta(days=365 * 10)
    LIFETIME = timedelta(days=365 * 100)  # Effectively lifetime


@dataclass
class JurisdictionLookbackRule:
    """
    Defines look-back rules for a specific violation type in a jurisdiction.

    Attributes:
        jurisdiction: Jurisdiction code (e.g., "CA-ON")
        violation_type: Type of violation (e.g., "bac_warn_range")
        reason_codes: Reason codes to count as strikes
        window: Look-back time window
        strike_thresholds: Dict mapping strike count to outcome
        description: Human-readable description
    """
    jurisdiction: str
    violation_type: str
    reason_codes: list[str]
    window: timedelta
    strike_thresholds: dict[int, str]  # {count: outcome}
    description: str = ""

    def get_outcome_for_strikes(self, strike_count: int) -> str:
        """
        Determine outcome based on cumulative strike count.

        Returns highest threshold that strike_count meets or exceeds.
        """
        applicable_outcome = "escalate"  # Default
        for threshold, outcome in sorted(self.strike_thresholds.items()):
            if strike_count >= threshold:
                applicable_outcome = outcome
        return applicable_outcome


# =============================================================================
# Ontario (CA-ON) Look-Back Rules
# =============================================================================

ONTARIO_LOOKBACK_RULES: dict[str, JurisdictionLookbackRule] = {
    "bac_warn_range": JurisdictionLookbackRule(
        jurisdiction="CA-ON",
        violation_type="bac_warn_range",
        reason_codes=[
            "RC-OAP1-4.3.3-WARN",
            "AUTO_ESCALATE_BAC_WARN",
        ],
        window=LookbackWindow.YEARS_10.value,
        strike_thresholds={
            1: "escalate",    # 1st: 3-day suspension, review
            2: "escalate",    # 2nd: 7-day suspension, review
            3: "deny",        # 3rd: 30-day + Interlock = DENY (4.1.2)
        },
        description="Ontario HTA 48.3 - BAC Warn Range (0.05-0.079) cumulative"
    ),

    "impaired_operation": JurisdictionLookbackRule(
        jurisdiction="CA-ON",
        violation_type="impaired_operation",
        reason_codes=[
            "RC-OAP1-4.3.3-FAIL",
            "AUTO_DENY_IMPAIRED_BAC",
            "AUTO_DENY_IMPAIRED_INDICATED",
        ],
        window=LookbackWindow.YEARS_10.value,
        strike_thresholds={
            1: "deny",        # Even 1st impaired is deny
            2: "deny",        # But history affects severity
        },
        description="Ontario Criminal Code impaired operation"
    ),

    "license_suspension": JurisdictionLookbackRule(
        jurisdiction="CA-ON",
        violation_type="license_suspension",
        reason_codes=[
            "AUTO_DENY_UNLICENSED",
            "RC-OAP1-4.1.2-SUSPENDED",
        ],
        window=LookbackWindow.YEARS_5.value,
        strike_thresholds={
            1: "deny",
            2: "deny",  # Multiple = SIU referral consideration
        },
        description="Ontario license status violations"
    ),
}


# All jurisdiction rules indexed by jurisdiction code
JURISDICTION_LOOKBACK_RULES: dict[str, dict[str, JurisdictionLookbackRule]] = {
    "CA-ON": ONTARIO_LOOKBACK_RULES,
    # Add other jurisdictions as needed:
    # "CA-BC": BRITISH_COLUMBIA_LOOKBACK_RULES,
    # "US-NY": NEW_YORK_LOOKBACK_RULES,
}


# =============================================================================
# Look-Back Query Results
# =============================================================================

@dataclass
class PriorIncident:
    """A single prior incident found in look-back query."""
    incident_date: datetime
    reason_code: str
    outcome: str
    judgment_cell_id: str
    fingerprint_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_date": self.incident_date.isoformat(),
            "reason_code": self.reason_code,
            "outcome": self.outcome,
            "judgment_cell_id": self.judgment_cell_id,
        }


@dataclass
class LookbackResult:
    """
    Result of a temporal look-back query.

    Attributes:
        subject_hash: Hashed subject identifier
        jurisdiction: Jurisdiction queried
        violation_type: Type of violation checked
        window_days: Look-back window in days
        strike_count: Total incidents found (including current)
        prior_incidents: List of prior incidents
        current_is_strike: Whether current incident counts as strike
        cumulative_outcome: Outcome based on cumulative count
        threshold_hit: Which threshold was triggered (if any)
        requires_interlock: Ontario-specific: Ignition Interlock required
    """
    subject_hash: str
    jurisdiction: str
    violation_type: str
    window_days: int
    strike_count: int
    prior_incidents: list[PriorIncident] = field(default_factory=list)
    current_is_strike: bool = True
    cumulative_outcome: str = "escalate"
    threshold_hit: Optional[int] = None
    requires_interlock: bool = False

    @property
    def total_with_current(self) -> int:
        """Total strikes including current incident."""
        return self.strike_count + (1 if self.current_is_strike else 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_hash": self.subject_hash[:8] + "...",  # Truncate for display
            "jurisdiction": self.jurisdiction,
            "violation_type": self.violation_type,
            "window_days": self.window_days,
            "strike_count": self.strike_count,
            "total_with_current": self.total_with_current,
            "prior_incidents": [p.to_dict() for p in self.prior_incidents],
            "cumulative_outcome": self.cumulative_outcome,
            "threshold_hit": self.threshold_hit,
            "requires_interlock": self.requires_interlock,
        }

    def format_history_for_memo(self) -> str:
        """Format incident history for Section 6 of memorandum."""
        lines = [
            f"**Occurrence Count:** {self.total_with_current} "
            f"(Within {self.window_days // 365}-year {self.jurisdiction} look-back)",
            "**History:**"
        ]

        for i, incident in enumerate(self.prior_incidents, 1):
            ordinal = self._ordinal(i)
            lines.append(
                f"  * `{incident.incident_date.strftime('%Y-%m-%d')}`: "
                f"{incident.reason_code} ({ordinal} Strike)"
            )

        if self.current_is_strike:
            ordinal = self._ordinal(self.total_with_current)
            lines.append(f"  * **Current Case**: ({ordinal} Strike)")

        return "\n".join(lines)

    @staticmethod
    def _ordinal(n: int) -> str:
        """Convert number to ordinal (1st, 2nd, 3rd, etc.)."""
        if 11 <= n <= 13:
            return f"{n}th"
        return f"{n}{['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]}"


# =============================================================================
# Look-Back Service
# =============================================================================

class LookbackService:
    """
    Service for querying temporal look-back history.

    Uses the precedent chain to find prior incidents for a subject
    within a jurisdiction-specific time window.

    Usage:
        >>> service = LookbackService(chain, salt="secret")
        >>> result = service.evaluate_driver_strikes(
        ...     driver_id="D123456",
        ...     jurisdiction="CA-ON",
        ...     violation_type="bac_warn_range",
        ...     current_incident_date=datetime.now()
        ... )
        >>> if result.cumulative_outcome == "deny":
        ...     print(f"3rd strike! {result.threshold_hit} threshold hit")
    """

    def __init__(
        self,
        chain: Optional[Chain] = None,
        salt: str = "",
    ) -> None:
        """
        Initialize the look-back service.

        Args:
            chain: DecisionGraph chain to query for precedents
            salt: Salt for hashing subject IDs
        """
        self.chain = chain
        self.salt = salt

    def _hash_subject_id(self, subject_id: str) -> str:
        """Hash a subject ID for privacy-preserving lookup."""
        import hashlib
        return hashlib.sha256(
            f"{subject_id}:{self.salt}".encode()
        ).hexdigest()

    def get_lookback_rule(
        self,
        jurisdiction: str,
        violation_type: str,
    ) -> Optional[JurisdictionLookbackRule]:
        """Get the look-back rule for a jurisdiction and violation type."""
        jurisdiction_rules = JURISDICTION_LOOKBACK_RULES.get(jurisdiction, {})
        return jurisdiction_rules.get(violation_type)

    def evaluate_driver_strikes(
        self,
        driver_id: str,
        jurisdiction: str,
        violation_type: str,
        current_incident_date: Optional[datetime] = None,
    ) -> LookbackResult:
        """
        Evaluate cumulative strikes for a driver.

        This is the main entry point for the Ontario BAC warn-range logic.

        Args:
            driver_id: Raw driver ID (will be hashed)
            jurisdiction: Jurisdiction code (e.g., "CA-ON")
            violation_type: Type of violation (e.g., "bac_warn_range")
            current_incident_date: Date of current incident (default: now)

        Returns:
            LookbackResult with strike count and cumulative outcome
        """
        if current_incident_date is None:
            current_incident_date = datetime.now(timezone.utc)

        # Get jurisdiction rule
        rule = self.get_lookback_rule(jurisdiction, violation_type)
        if rule is None:
            # No cumulative rule for this jurisdiction/violation
            return LookbackResult(
                subject_hash=self._hash_subject_id(driver_id),
                jurisdiction=jurisdiction,
                violation_type=violation_type,
                window_days=0,
                strike_count=0,
                cumulative_outcome="escalate",  # Default to escalate
            )

        # Hash driver ID
        driver_hash = self._hash_subject_id(driver_id)

        # Query prior incidents
        prior_incidents = self._query_prior_incidents(
            subject_hash=driver_hash,
            jurisdiction=jurisdiction,
            reason_codes=rule.reason_codes,
            window=rule.window,
            before_date=current_incident_date,
        )

        # Calculate total strikes (prior + current)
        strike_count = len(prior_incidents)
        total_with_current = strike_count + 1  # Current counts as a strike

        # Determine outcome based on cumulative count
        cumulative_outcome = rule.get_outcome_for_strikes(total_with_current)

        # Find which threshold was hit
        threshold_hit = None
        for threshold in sorted(rule.strike_thresholds.keys(), reverse=True):
            if total_with_current >= threshold:
                threshold_hit = threshold
                break

        # Ontario-specific: Check if Ignition Interlock is required
        requires_interlock = (
            jurisdiction == "CA-ON" and
            violation_type == "bac_warn_range" and
            total_with_current >= 3
        )

        return LookbackResult(
            subject_hash=driver_hash,
            jurisdiction=jurisdiction,
            violation_type=violation_type,
            window_days=rule.window.days,
            strike_count=strike_count,
            prior_incidents=prior_incidents,
            current_is_strike=True,
            cumulative_outcome=cumulative_outcome,
            threshold_hit=threshold_hit,
            requires_interlock=requires_interlock,
        )

    def _query_prior_incidents(
        self,
        subject_hash: str,
        jurisdiction: str,
        reason_codes: list[str],
        window: timedelta,
        before_date: datetime,
    ) -> list[PriorIncident]:
        """
        Query the chain for prior incidents matching criteria.

        In production, this queries the DecisionGraph chain.
        Returns empty list if chain is not available (testing/demo mode).
        """
        if self.chain is None:
            return []

        prior_incidents: list[PriorIncident] = []
        cutoff_date = before_date - window

        # Walk the chain looking for matching JUDGMENT cells
        try:
            for cell in self.chain.iter_cells():
                # Skip non-JUDGMENT cells
                if not hasattr(cell, 'payload') or cell.payload is None:
                    continue

                payload = cell.payload

                # Check if this is a relevant judgment
                if not hasattr(payload, 'case_id_hash'):
                    continue

                # Match subject hash
                if payload.case_id_hash != subject_hash:
                    continue

                # Match jurisdiction
                if hasattr(payload, 'jurisdiction_code'):
                    if payload.jurisdiction_code != jurisdiction:
                        continue

                # Check if within time window
                if hasattr(payload, 'decided_at'):
                    decided_at = payload.decided_at
                    if isinstance(decided_at, str):
                        decided_at = datetime.fromisoformat(
                            decided_at.replace('Z', '+00:00')
                        )

                    if decided_at < cutoff_date:
                        continue
                    if decided_at >= before_date:
                        continue  # Don't include current or future

                # Check if reason codes match
                matching_codes = []
                if hasattr(payload, 'reason_codes'):
                    matching_codes = [
                        rc for rc in payload.reason_codes
                        if rc in reason_codes
                    ]
                if hasattr(payload, 'exclusion_codes'):
                    matching_codes.extend([
                        ec for ec in payload.exclusion_codes
                        if ec in reason_codes
                    ])

                if not matching_codes:
                    continue

                # Found a matching prior incident
                prior_incidents.append(PriorIncident(
                    incident_date=decided_at if isinstance(decided_at, datetime)
                                  else datetime.now(timezone.utc),
                    reason_code=matching_codes[0],
                    outcome=getattr(payload, 'outcome_code', 'unknown'),
                    judgment_cell_id=cell.cell_id,
                    fingerprint_hash=getattr(payload, 'fingerprint_hash', ''),
                ))

        except Exception:
            # If chain iteration fails, return empty list
            pass

        # Sort by date (oldest first)
        prior_incidents.sort(key=lambda x: x.incident_date)

        return prior_incidents

    def evaluate_with_mock_history(
        self,
        driver_id: str,
        jurisdiction: str,
        violation_type: str,
        mock_prior_dates: list[datetime],
        current_incident_date: Optional[datetime] = None,
    ) -> LookbackResult:
        """
        Evaluate strikes with mock prior incident dates (for testing).

        Args:
            driver_id: Driver ID
            jurisdiction: Jurisdiction code
            violation_type: Violation type
            mock_prior_dates: List of prior incident dates to simulate
            current_incident_date: Current incident date

        Returns:
            LookbackResult as if those prior incidents existed
        """
        if current_incident_date is None:
            current_incident_date = datetime.now(timezone.utc)

        rule = self.get_lookback_rule(jurisdiction, violation_type)
        if rule is None:
            return LookbackResult(
                subject_hash=self._hash_subject_id(driver_id),
                jurisdiction=jurisdiction,
                violation_type=violation_type,
                window_days=0,
                strike_count=0,
                cumulative_outcome="escalate",
            )

        driver_hash = self._hash_subject_id(driver_id)
        cutoff_date = current_incident_date - rule.window

        # Filter mock dates to those within window
        valid_dates = [
            d for d in mock_prior_dates
            if cutoff_date <= d < current_incident_date
        ]
        valid_dates.sort()

        # Create mock prior incidents
        prior_incidents = [
            PriorIncident(
                incident_date=d,
                reason_code=rule.reason_codes[0],
                outcome="escalate",
                judgment_cell_id=f"mock-{i}",
                fingerprint_hash=f"mock-fp-{i}",
            )
            for i, d in enumerate(valid_dates)
        ]

        strike_count = len(prior_incidents)
        total_with_current = strike_count + 1
        cumulative_outcome = rule.get_outcome_for_strikes(total_with_current)

        threshold_hit = None
        for threshold in sorted(rule.strike_thresholds.keys(), reverse=True):
            if total_with_current >= threshold:
                threshold_hit = threshold
                break

        requires_interlock = (
            jurisdiction == "CA-ON" and
            violation_type == "bac_warn_range" and
            total_with_current >= 3
        )

        return LookbackResult(
            subject_hash=driver_hash,
            jurisdiction=jurisdiction,
            violation_type=violation_type,
            window_days=rule.window.days,
            strike_count=strike_count,
            prior_incidents=prior_incidents,
            current_is_strike=True,
            cumulative_outcome=cumulative_outcome,
            threshold_hit=threshold_hit,
            requires_interlock=requires_interlock,
        )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Enums
    "LookbackWindow",

    # Data classes
    "JurisdictionLookbackRule",
    "PriorIncident",
    "LookbackResult",

    # Rules
    "ONTARIO_LOOKBACK_RULES",
    "JURISDICTION_LOOKBACK_RULES",

    # Service
    "LookbackService",
]
