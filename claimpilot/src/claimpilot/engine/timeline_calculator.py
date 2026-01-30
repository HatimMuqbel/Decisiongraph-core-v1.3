"""
ClaimPilot Timeline Calculator

Calculates deadline dates based on timeline rules and business day calendars.

Key features:
- Business day calculation with holiday calendars
- Multiple anchor types (report_date, loss_date, etc.)
- Deadline tracking and status
- Ontario/Canadian calendar support
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from ..calendars import HolidayCalendar, OntarioCalendar
from ..exceptions import TimelineCalculationError
from ..models import (
    ClaimContext,
    TimelineAnchor,
    TimelineEvent,
    TimelineEventType,
    TimelineRule,
    TimelineSummary,
)


# =============================================================================
# Deadline Status
# =============================================================================

class DeadlineStatus(str, Enum):
    """Status of a deadline relative to current date."""
    NOT_STARTED = "not_started"    # Anchor date not yet set
    PENDING = "pending"            # Deadline in future
    DUE_TODAY = "due_today"        # Deadline is today
    DUE_SOON = "due_soon"          # Within warning threshold
    OVERDUE = "overdue"            # Past deadline
    COMPLETED = "completed"        # Event has occurred


@dataclass
class CalculatedDeadline:
    """
    A calculated deadline from a timeline rule.

    Includes the rule, calculated date, and current status.
    """
    rule: TimelineRule
    anchor_date: date
    deadline_date: date
    status: DeadlineStatus
    days_remaining: int
    business_days_remaining: int
    completion_date: Optional[date] = None
    is_overdue: bool = False
    warning_threshold_days: int = 3


# =============================================================================
# Timeline Calculator
# =============================================================================

@dataclass
class TimelineCalculator:
    """
    Calculates deadlines based on timeline rules and business calendars.

    Handles:
    - Business day vs calendar day calculation
    - Holiday calendar integration
    - Multiple anchor types
    - Deadline status tracking

    Usage:
        calculator = TimelineCalculator()

        # Calculate single deadline
        deadline = calculator.calculate_deadline(
            rule=acknowledge_rule,
            context=claim_context,
        )
        print(f"Due: {deadline.deadline_date}, Status: {deadline.status}")

        # Calculate all deadlines for a claim
        deadlines = calculator.calculate_all_deadlines(
            rules=timeline_rules,
            context=claim_context,
        )
    """

    # Calendar for business day calculation
    calendar: HolidayCalendar = field(default_factory=OntarioCalendar)

    # Warning threshold (days before deadline to flag as "due soon")
    warning_threshold_days: int = 3

    # Reference date for status calculation (defaults to today)
    reference_date: Optional[date] = None

    def calculate_deadline(
        self,
        rule: TimelineRule,
        context: ClaimContext,
        completions: Optional[dict[str, date]] = None,
    ) -> Optional[CalculatedDeadline]:
        """
        Calculate deadline for a single timeline rule.

        Args:
            rule: The timeline rule to calculate
            context: Claim context with dates
            completions: Dict of event_type -> completion_date

        Returns:
            CalculatedDeadline or None if anchor not available
        """
        completions = completions or {}

        # Get anchor date
        anchor_date = self._get_anchor_date(rule.anchor, context, completions)
        if anchor_date is None:
            return None

        # Calculate deadline date
        if rule.business_days:
            deadline_date = self._add_business_days(
                anchor_date,
                rule.days_from_anchor
            )
        else:
            deadline_date = anchor_date + timedelta(days=rule.days_from_anchor)

        # Determine reference date
        ref_date = self.reference_date or date.today()

        # Check completion
        completion_date = completions.get(rule.event_type.value)

        # Calculate status
        status = self._determine_status(
            deadline_date=deadline_date,
            reference_date=ref_date,
            completion_date=completion_date,
        )

        # Calculate days remaining
        days_remaining = (deadline_date - ref_date).days
        business_days_remaining = self._count_business_days(ref_date, deadline_date)

        return CalculatedDeadline(
            rule=rule,
            anchor_date=anchor_date,
            deadline_date=deadline_date,
            status=status,
            days_remaining=days_remaining,
            business_days_remaining=business_days_remaining,
            completion_date=completion_date,
            is_overdue=status == DeadlineStatus.OVERDUE,
            warning_threshold_days=self.warning_threshold_days,
        )

    def calculate_all_deadlines(
        self,
        rules: list[TimelineRule],
        context: ClaimContext,
        completions: Optional[dict[str, date]] = None,
    ) -> list[CalculatedDeadline]:
        """
        Calculate deadlines for multiple timeline rules.

        Args:
            rules: List of timeline rules
            context: Claim context
            completions: Dict of event_type -> completion_date

        Returns:
            List of calculated deadlines (rules without anchors are excluded)
        """
        deadlines: list[CalculatedDeadline] = []

        # Sort rules by priority for deterministic order
        sorted_rules = sorted(
            rules,
            key=lambda r: (-r.priority, r.id)
        )

        for rule in sorted_rules:
            if not rule.enabled:
                continue

            deadline = self.calculate_deadline(rule, context, completions)
            if deadline is not None:
                deadlines.append(deadline)

        return deadlines

    def get_timeline_summary(
        self,
        rules: list[TimelineRule],
        context: ClaimContext,
        completions: Optional[dict[str, date]] = None,
    ) -> TimelineSummary:
        """
        Generate a summary of all timeline deadlines.

        Args:
            rules: Timeline rules to evaluate
            context: Claim context
            completions: Completion dates by event type

        Returns:
            TimelineSummary with aggregated information
        """
        deadlines = self.calculate_all_deadlines(rules, context, completions)

        # Convert to TimelineEvents
        events: list[TimelineEvent] = []
        for dl in deadlines:
            event = TimelineEvent(
                rule_id=dl.rule.id,
                event_type=dl.rule.event_type,
                anchor_type=dl.rule.anchor,
                anchor_date=dl.anchor_date,
                due_date=dl.deadline_date,
                completed=dl.completion_date is not None,
                completed_at=datetime.combine(dl.completion_date, datetime.min.time()).replace(tzinfo=timezone.utc) if dl.completion_date else None,
                overdue=dl.is_overdue,
                rule_name=dl.rule.name,
                rule_description=dl.rule.description,
            )
            events.append(event)

        # Find next deadline and overdue count
        ref_date = self.reference_date or date.today()
        pending = [d for d in deadlines if d.status in {
            DeadlineStatus.PENDING,
            DeadlineStatus.DUE_TODAY,
            DeadlineStatus.DUE_SOON,
        }]
        overdue = [d for d in deadlines if d.status == DeadlineStatus.OVERDUE]

        return TimelineSummary(
            claim_id=context.claim_id,
            events=events,
        )

    def _get_anchor_date(
        self,
        anchor: TimelineAnchor,
        context: ClaimContext,
        completions: dict[str, date],
    ) -> Optional[date]:
        """Get the anchor date for a timeline rule."""
        if anchor == TimelineAnchor.REPORT_DATE:
            return context.report_date

        elif anchor == TimelineAnchor.LOSS_DATE:
            return context.loss_date

        elif anchor == TimelineAnchor.COVERAGE_DECISION_DATE:
            return completions.get("coverage_decision")

        elif anchor == TimelineAnchor.CLAIM_SUBMISSION_DATE:
            # Could be same as report_date or from metadata
            return context.metadata.get("submission_date") or context.report_date

        elif anchor == TimelineAnchor.EVIDENCE_RECEIVED_DATE:
            return completions.get("evidence_received")

        elif anchor == TimelineAnchor.POLICY_EFFECTIVE_DATE:
            return context.policy_effective_date

        elif anchor == TimelineAnchor.POLICY_EXPIRY_DATE:
            return context.policy_expiry_date

        else:
            # Unknown anchor type
            return None

    def _determine_status(
        self,
        deadline_date: date,
        reference_date: date,
        completion_date: Optional[date],
    ) -> DeadlineStatus:
        """Determine the status of a deadline."""
        if completion_date is not None:
            return DeadlineStatus.COMPLETED

        days_until = (deadline_date - reference_date).days

        if days_until < 0:
            return DeadlineStatus.OVERDUE
        elif days_until == 0:
            return DeadlineStatus.DUE_TODAY
        elif days_until <= self.warning_threshold_days:
            return DeadlineStatus.DUE_SOON
        else:
            return DeadlineStatus.PENDING

    def _add_business_days(self, start_date: date, days: int) -> date:
        """
        Add business days to a date, skipping weekends and holidays.

        Args:
            start_date: Starting date
            days: Number of business days to add

        Returns:
            Resulting date
        """
        if days == 0:
            return start_date

        current = start_date
        remaining = abs(days)
        direction = 1 if days > 0 else -1

        while remaining > 0:
            current += timedelta(days=direction)
            if self._is_business_day(current):
                remaining -= 1

        return current

    def _count_business_days(self, start_date: date, end_date: date) -> int:
        """
        Count business days between two dates.

        Args:
            start_date: Start date (exclusive)
            end_date: End date (inclusive)

        Returns:
            Number of business days
        """
        if start_date >= end_date:
            return 0

        count = 0
        current = start_date + timedelta(days=1)

        while current <= end_date:
            if self._is_business_day(current):
                count += 1
            current += timedelta(days=1)

        return count

    def _is_business_day(self, d: date) -> bool:
        """Check if a date is a business day."""
        # Weekend check
        if d.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False

        # Holiday check
        if self.calendar.is_holiday(d):
            return False

        return True

    def get_next_business_day(self, d: date) -> date:
        """
        Get the next business day on or after a date.

        If the date is a business day, returns it.
        Otherwise, returns the next business day.
        """
        while not self._is_business_day(d):
            d += timedelta(days=1)
        return d

    def get_previous_business_day(self, d: date) -> date:
        """
        Get the previous business day on or before a date.

        If the date is a business day, returns it.
        Otherwise, returns the previous business day.
        """
        while not self._is_business_day(d):
            d -= timedelta(days=1)
        return d


# =============================================================================
# FSRA-Specific Timeline Helpers
# =============================================================================

@dataclass
class FSRATimelineChecker:
    """
    Helper for checking FSRA (Financial Services Regulatory Authority)
    compliance timelines specific to Ontario insurance.

    FSRA requires:
    - Acknowledge claim within 3 business days
    - Request additional info within 10 business days
    - Coverage decision within 60 calendar days
    - Payment within 15 business days of approval
    - Denial notice within 5 business days of denial
    """

    calculator: TimelineCalculator = field(
        default_factory=lambda: TimelineCalculator(calendar=OntarioCalendar())
    )

    def check_acknowledgment_deadline(
        self,
        report_date: date,
        acknowledged_date: Optional[date] = None,
    ) -> CalculatedDeadline:
        """Check the 3 business day acknowledgment deadline."""
        rule = TimelineRule(
            id="fsra-acknowledge",
            name="Acknowledge Claim Receipt",
            event_type=TimelineEventType.ACKNOWLEDGE,
            anchor=TimelineAnchor.REPORT_DATE,
            days_from_anchor=3,
            business_days=True,
            description="Acknowledge receipt of claim within 3 business days",
        )

        # Create minimal context
        from ..models import ClaimContext
        context = ClaimContext(
            claim_id="check",
            policy_id="check",
            report_date=report_date,
            loss_type="check",
        )

        completions = {}
        if acknowledged_date:
            completions["acknowledge"] = acknowledged_date

        return self.calculator.calculate_deadline(rule, context, completions)

    def check_coverage_decision_deadline(
        self,
        report_date: date,
        decision_date: Optional[date] = None,
    ) -> CalculatedDeadline:
        """Check the 60 calendar day coverage decision deadline."""
        rule = TimelineRule(
            id="fsra-decision",
            name="Coverage Decision",
            event_type=TimelineEventType.COVERAGE_DECISION_DUE,
            anchor=TimelineAnchor.REPORT_DATE,
            days_from_anchor=60,
            business_days=False,  # Calendar days
            description="Make coverage decision within 60 calendar days",
        )

        from ..models import ClaimContext
        context = ClaimContext(
            claim_id="check",
            policy_id="check",
            report_date=report_date,
            loss_type="check",
        )

        completions = {}
        if decision_date:
            completions["coverage_decision"] = decision_date

        return self.calculator.calculate_deadline(rule, context, completions)

    def is_compliant(self, deadlines: list[CalculatedDeadline]) -> bool:
        """Check if all FSRA deadlines are being met."""
        for deadline in deadlines:
            if deadline.is_overdue:
                return False
        return True

    def get_compliance_report(
        self,
        deadlines: list[CalculatedDeadline],
    ) -> dict[str, any]:
        """Generate FSRA compliance report."""
        overdue = [d for d in deadlines if d.is_overdue]
        due_soon = [d for d in deadlines if d.status == DeadlineStatus.DUE_SOON]

        return {
            "compliant": len(overdue) == 0,
            "total_deadlines": len(deadlines),
            "overdue_count": len(overdue),
            "due_soon_count": len(due_soon),
            "overdue_items": [
                {
                    "rule": d.rule.name,
                    "deadline": d.deadline_date.isoformat(),
                    "days_overdue": abs(d.days_remaining),
                }
                for d in overdue
            ],
            "upcoming_items": [
                {
                    "rule": d.rule.name,
                    "deadline": d.deadline_date.isoformat(),
                    "days_remaining": d.days_remaining,
                }
                for d in due_soon
            ],
        }


# =============================================================================
# Convenience Functions
# =============================================================================

def calculate_deadline(
    rule: TimelineRule,
    context: ClaimContext,
    calendar: Optional[HolidayCalendar] = None,
) -> Optional[CalculatedDeadline]:
    """
    Calculate a single deadline.

    Convenience function that creates a temporary calculator.
    """
    calc = TimelineCalculator(calendar=calendar or OntarioCalendar())
    return calc.calculate_deadline(rule, context)


def add_business_days(
    start_date: date,
    days: int,
    calendar: Optional[HolidayCalendar] = None,
) -> date:
    """
    Add business days to a date.

    Convenience function for quick calculations.
    """
    calc = TimelineCalculator(calendar=calendar or OntarioCalendar())
    return calc._add_business_days(start_date, days)


def is_business_day(
    d: date,
    calendar: Optional[HolidayCalendar] = None,
) -> bool:
    """
    Check if a date is a business day.

    Convenience function for quick checks.
    """
    calc = TimelineCalculator(calendar=calendar or OntarioCalendar())
    return calc._is_business_day(d)
