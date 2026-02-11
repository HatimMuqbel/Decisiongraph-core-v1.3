"""
Kernel Holiday Calendar Base

Provides the protocol and base implementation for holiday calendars
used in business day calculations.

The calendar system is pluggable — different jurisdictions can have
different holiday rules.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Protocol, runtime_checkable


@runtime_checkable
class HolidayCalendar(Protocol):
    """
    Protocol for holiday calendars.

    Implementations must provide methods to check if a date is a holiday
    or business day. This enables jurisdiction-specific business day
    calculations.
    """

    def is_holiday(self, d: date) -> bool:
        ...

    def is_business_day(self, d: date) -> bool:
        ...

    def get_holidays_in_range(self, start: date, end: date) -> list[date]:
        ...


@dataclass
class BaseCalendar(ABC):
    """
    Abstract base class for holiday calendars.

    Provides common functionality for business day calculations.
    Subclasses must implement `is_holiday()`.
    """

    # Weekend days (0=Monday, 6=Sunday)
    weekend_days: frozenset[int] = field(default_factory=lambda: frozenset({5, 6}))

    @abstractmethod
    def is_holiday(self, d: date) -> bool:
        """Check if a date is a holiday."""
        ...

    def is_weekend(self, d: date) -> bool:
        """Check if a date is a weekend day."""
        return d.weekday() in self.weekend_days

    def is_business_day(self, d: date) -> bool:
        """A business day is a weekday that is not a holiday."""
        if self.is_weekend(d):
            return False
        return not self.is_holiday(d)

    def get_holidays_in_range(self, start: date, end: date) -> list[date]:
        """Get all holidays within a date range."""
        holidays = []
        current = start
        while current <= end:
            if self.is_holiday(current):
                holidays.append(current)
            current += timedelta(days=1)
        return holidays

    def add_business_days(self, start: date, days: int) -> date:
        """Add business days to a date."""
        if days == 0:
            return start

        direction = 1 if days > 0 else -1
        remaining = abs(days)
        current = start

        while remaining > 0:
            current += timedelta(days=direction)
            if self.is_business_day(current):
                remaining -= 1

        return current

    def subtract_business_days(self, start: date, days: int) -> date:
        """Subtract business days from a date."""
        return self.add_business_days(start, -days)

    def business_days_between(self, start: date, end: date) -> int:
        """Count business days between two dates (start exclusive, end inclusive)."""
        if start >= end:
            return 0

        count = 0
        current = start + timedelta(days=1)

        while current <= end:
            if self.is_business_day(current):
                count += 1
            current += timedelta(days=1)

        return count

    def next_business_day(self, d: date) -> date:
        """Get the next business day on or after a date."""
        current = d
        while not self.is_business_day(current):
            current += timedelta(days=1)
        return current

    def previous_business_day(self, d: date) -> date:
        """Get the previous business day on or before a date."""
        current = d
        while not self.is_business_day(current):
            current -= timedelta(days=1)
        return current


@dataclass
class NoHolidayCalendar(BaseCalendar):
    """A calendar with no holidays. Only weekends are non-business days."""

    def is_holiday(self, d: date) -> bool:
        return False


@dataclass
class FixedHolidayCalendar(BaseCalendar):
    """A calendar with a fixed set of holiday dates."""

    holidays: frozenset[date] = field(default_factory=frozenset)

    def is_holiday(self, d: date) -> bool:
        return d in self.holidays

    @classmethod
    def from_dates(cls, *dates: date) -> FixedHolidayCalendar:
        """Create a calendar from a list of holiday dates."""
        return cls(holidays=frozenset(dates))


def calculate_observed_holiday(holiday: date, calendar: BaseCalendar) -> date:
    """Calculate the observed date for a holiday.

    Saturday holidays observed on Friday, Sunday on Monday.
    """
    if holiday.weekday() == 5:  # Saturday
        return holiday - timedelta(days=1)
    elif holiday.weekday() == 6:  # Sunday
        return holiday + timedelta(days=1)
    return holiday
