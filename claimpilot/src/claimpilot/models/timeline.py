"""
ClaimPilot Timeline Models

Models for regulatory and policy-driven timeline requirements.

Key components:
- TimelineRule: Definition of a timeline requirement
- TimelineEvent: Computed event for a specific claim

Timelines can be based on:
- Calendar days
- Business days (with holiday calendar)
- Various anchor points (loss date, report date, etc.)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

from .enums import TimelineAnchor, TimelineEventType
from .authority import AuthorityRef
from .conditions import Condition


# =============================================================================
# Timeline Rule
# =============================================================================

@dataclass
class TimelineRule:
    """
    A regulatory or policy-driven timeline requirement.

    Defines when certain events must occur relative to an anchor point.

    Attributes:
        id: Unique identifier
        event_type: Type of event
        anchor: Reference point for calculation
        days_from_anchor: Days from anchor (can be negative)
        business_days: True = business days, False = calendar days
        description: Human-readable description
        penalty_description: What happens if missed
        authority_ref: Citation to regulatory requirement
        applies_when: Condition for when this rule applies
        jurisdiction: Applicable jurisdiction
        line_of_business: Applicable line (if specific)
    """
    id: str
    event_type: TimelineEventType
    anchor: TimelineAnchor
    days_from_anchor: int
    business_days: bool = False

    # Metadata
    name: Optional[str] = None
    description: str = ""
    penalty_description: Optional[str] = None

    # Authority citation
    authority_ref: Optional[AuthorityRef] = None

    # Conditions (when does this rule apply)
    applies_when: Optional[Condition] = None
    applies_when_id: Optional[str] = None  # Reference to condition by ID

    # Scope
    jurisdiction: Optional[str] = None
    line_of_business: Optional[str] = None

    # Configuration
    enabled: bool = True
    priority: int = 0  # Higher priority rules take precedence

    @property
    def is_business_days(self) -> bool:
        """Check if rule uses business days."""
        return self.business_days

    @property
    def is_calendar_days(self) -> bool:
        """Check if rule uses calendar days."""
        return not self.business_days

    @property
    def display_days(self) -> str:
        """Get human-readable days description."""
        day_type = "business days" if self.business_days else "calendar days"
        return f"{abs(self.days_from_anchor)} {day_type}"


# =============================================================================
# Timeline Event
# =============================================================================

@dataclass
class TimelineEvent:
    """
    A computed timeline event for a specific claim.

    Created by the TimelineCalculator from TimelineRules.

    Attributes:
        rule_id: Reference to the TimelineRule
        event_type: Type of event
        due_date: Calculated due date
        anchor_date: The date used as anchor
        anchor_type: Type of anchor used
        completed: Whether event has occurred
        completed_at: When event was completed
        overdue: Whether event is overdue
        authority_ref: Citation (from rule)
        claim_id: Associated claim
    """
    rule_id: str
    event_type: TimelineEventType
    due_date: date
    anchor_date: date
    anchor_type: TimelineAnchor

    # Status
    completed: bool = False
    completed_at: Optional[datetime] = None
    overdue: bool = False

    # Authority citation (copied from rule)
    authority_ref: Optional[AuthorityRef] = None

    # Association
    claim_id: Optional[str] = None

    # Metadata
    rule_name: Optional[str] = None
    rule_description: Optional[str] = None
    penalty_description: Optional[str] = None

    def mark_completed(self) -> None:
        """Mark event as completed."""
        self.completed = True
        self.completed_at = datetime.now(timezone.utc)
        self.overdue = False

    def check_overdue(self, as_of: Optional[date] = None) -> bool:
        """
        Check if event is overdue as of a given date.

        Args:
            as_of: Date to check against (defaults to today)

        Returns:
            True if overdue, False otherwise
        """
        if self.completed:
            return False
        check_date = as_of or date.today()
        is_overdue = check_date > self.due_date
        self.overdue = is_overdue
        return is_overdue

    @property
    def days_until_due(self) -> int:
        """
        Calculate days until due (negative if overdue).

        Uses today's date for calculation.
        """
        return (self.due_date - date.today()).days

    @property
    def days_overdue(self) -> int:
        """Calculate days overdue (0 if not overdue)."""
        days = -self.days_until_due
        return max(0, days)

    @property
    def is_upcoming(self) -> bool:
        """Check if event is upcoming (due in next 7 days)."""
        return 0 <= self.days_until_due <= 7 and not self.completed

    @property
    def is_urgent(self) -> bool:
        """Check if event is urgent (due in next 2 days)."""
        return 0 <= self.days_until_due <= 2 and not self.completed

    @property
    def status(self) -> str:
        """Get human-readable status."""
        if self.completed:
            return "completed"
        if self.overdue or self.days_until_due < 0:
            return "overdue"
        if self.is_urgent:
            return "urgent"
        if self.is_upcoming:
            return "upcoming"
        return "pending"

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "rule_id": self.rule_id,
            "event_type": self.event_type.value,
            "due_date": self.due_date.isoformat(),
            "anchor_date": self.anchor_date.isoformat(),
            "anchor_type": self.anchor_type.value,
            "completed": self.completed,
            "overdue": self.overdue,
            "status": self.status,
            "days_until_due": self.days_until_due,
        }


# =============================================================================
# Timeline Summary
# =============================================================================

@dataclass
class TimelineSummary:
    """
    Summary of timeline events for a claim.

    Provides quick access to critical timeline information.
    """
    claim_id: str
    events: list[TimelineEvent] = field(default_factory=list)

    @property
    def overdue_events(self) -> list[TimelineEvent]:
        """Get all overdue events."""
        return [e for e in self.events if e.overdue or e.days_until_due < 0]

    @property
    def upcoming_events(self) -> list[TimelineEvent]:
        """Get all upcoming events (due in next 7 days)."""
        return [e for e in self.events if e.is_upcoming]

    @property
    def urgent_events(self) -> list[TimelineEvent]:
        """Get all urgent events (due in next 2 days)."""
        return [e for e in self.events if e.is_urgent]

    @property
    def completed_events(self) -> list[TimelineEvent]:
        """Get all completed events."""
        return [e for e in self.events if e.completed]

    @property
    def pending_events(self) -> list[TimelineEvent]:
        """Get all pending (not completed, not overdue) events."""
        return [
            e for e in self.events
            if not e.completed and not e.overdue and e.days_until_due >= 0
        ]

    @property
    def has_overdue(self) -> bool:
        """Check if any events are overdue."""
        return len(self.overdue_events) > 0

    @property
    def next_due_event(self) -> Optional[TimelineEvent]:
        """Get the next event due (excluding completed)."""
        pending = [e for e in self.events if not e.completed]
        if not pending:
            return None
        return min(pending, key=lambda e: e.due_date)

    @property
    def most_urgent_event(self) -> Optional[TimelineEvent]:
        """Get the most urgent event (overdue or soonest due)."""
        overdue = self.overdue_events
        if overdue:
            return max(overdue, key=lambda e: e.days_overdue)
        return self.next_due_event

    def get_events_by_type(self, event_type: TimelineEventType) -> list[TimelineEvent]:
        """Get all events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def get_events_due_before(self, check_date: date) -> list[TimelineEvent]:
        """Get all events due before a specific date."""
        return [
            e for e in self.events
            if not e.completed and e.due_date < check_date
        ]

    def get_events_due_between(
        self,
        start_date: date,
        end_date: date,
    ) -> list[TimelineEvent]:
        """Get all events due within a date range."""
        return [
            e for e in self.events
            if not e.completed and start_date <= e.due_date <= end_date
        ]

    def to_dict(self) -> dict:
        """Serialize summary to dictionary."""
        return {
            "claim_id": self.claim_id,
            "total_events": len(self.events),
            "overdue_count": len(self.overdue_events),
            "upcoming_count": len(self.upcoming_events),
            "completed_count": len(self.completed_events),
            "has_overdue": self.has_overdue,
            "events": [e.to_dict() for e in self.events],
        }
