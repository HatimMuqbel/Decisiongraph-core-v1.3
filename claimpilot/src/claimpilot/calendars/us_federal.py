"""
US Federal Holiday Calendar

Implements the US Federal holiday schedule for business day calculations.

Federal holidays:
- New Year's Day (January 1)
- Martin Luther King Jr. Day (3rd Monday in January)
- Presidents' Day (3rd Monday in February)
- Memorial Day (Last Monday in May)
- Juneteenth (June 19) - Since 2021
- Independence Day (July 4)
- Labor Day (1st Monday in September)
- Columbus Day (2nd Monday in October)
- Veterans Day (November 11)
- Thanksgiving Day (4th Thursday in November)
- Christmas Day (December 25)

Observed holidays: When a holiday falls on Saturday, it's observed on Friday.
When it falls on Sunday, it's observed on Monday.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from typing import Optional

from .base import BaseCalendar, calculate_observed_holiday


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """
    Get the nth occurrence of a weekday in a month.

    Args:
        year: Year
        month: Month (1-12)
        weekday: Day of week (0=Monday, 6=Sunday)
        n: Which occurrence (1=first, 2=second, etc.)

    Returns:
        The date of the nth weekday
    """
    # Start at the first day of the month
    first_day = date(year, month, 1)

    # Find the first occurrence of the weekday
    days_until_weekday = (weekday - first_day.weekday()) % 7
    first_occurrence = first_day + timedelta(days=days_until_weekday)

    # Add weeks to get to the nth occurrence
    return first_occurrence + timedelta(weeks=n - 1)


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    """
    Get the last occurrence of a weekday in a month.

    Args:
        year: Year
        month: Month (1-12)
        weekday: Day of week (0=Monday, 6=Sunday)

    Returns:
        The date of the last weekday
    """
    # Start at the last day of the month
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)

    # Find the last occurrence of the weekday
    days_since_weekday = (last_day.weekday() - weekday) % 7
    return last_day - timedelta(days=days_since_weekday)


@dataclass
class USFederalCalendar(BaseCalendar):
    """
    US Federal holiday calendar.

    Implements all federal holidays with proper observed day handling.
    """

    # Include Juneteenth (added as federal holiday in 2021)
    include_juneteenth: bool = True

    # Include Columbus Day (some jurisdictions don't observe)
    include_columbus_day: bool = True

    # Year to start including Juneteenth
    juneteenth_start_year: int = 2021

    # Cache for computed holidays
    _holiday_cache: dict[int, set[date]] = field(default_factory=dict, repr=False)

    def _get_fixed_holidays(self, year: int) -> list[tuple[date, str]]:
        """
        Get fixed-date holidays for a year.

        Returns list of (date, name) tuples.
        """
        holidays = [
            (date(year, 1, 1), "New Year's Day"),
            (date(year, 7, 4), "Independence Day"),
            (date(year, 11, 11), "Veterans Day"),
            (date(year, 12, 25), "Christmas Day"),
        ]

        if self.include_juneteenth and year >= self.juneteenth_start_year:
            holidays.append((date(year, 6, 19), "Juneteenth"))

        return holidays

    def _get_floating_holidays(self, year: int) -> list[tuple[date, str]]:
        """
        Get floating holidays (relative to weekday) for a year.

        Returns list of (date, name) tuples.
        """
        holidays = [
            # MLK Day: 3rd Monday in January
            (_nth_weekday_of_month(year, 1, 0, 3), "Martin Luther King Jr. Day"),
            # Presidents' Day: 3rd Monday in February
            (_nth_weekday_of_month(year, 2, 0, 3), "Presidents' Day"),
            # Memorial Day: Last Monday in May
            (_last_weekday_of_month(year, 5, 0), "Memorial Day"),
            # Labor Day: 1st Monday in September
            (_nth_weekday_of_month(year, 9, 0, 1), "Labor Day"),
            # Thanksgiving: 4th Thursday in November
            (_nth_weekday_of_month(year, 11, 3, 4), "Thanksgiving Day"),
        ]

        if self.include_columbus_day:
            # Columbus Day: 2nd Monday in October
            holidays.append(
                (_nth_weekday_of_month(year, 10, 0, 2), "Columbus Day")
            )

        return holidays

    def _compute_holidays_for_year(self, year: int) -> set[date]:
        """
        Compute all holidays for a year, including observed dates.

        Returns set of holiday dates.
        """
        holidays = set()

        # Add fixed holidays (with observed date handling)
        for holiday_date, _ in self._get_fixed_holidays(year):
            observed = calculate_observed_holiday(holiday_date, self)
            holidays.add(observed)
            # Also add actual date if different (for accuracy)
            if observed != holiday_date:
                holidays.add(holiday_date)

        # Add floating holidays (these are always on weekdays)
        for holiday_date, _ in self._get_floating_holidays(year):
            holidays.add(holiday_date)

        return holidays

    def _get_holidays_for_year(self, year: int) -> set[date]:
        """Get holidays for a year, using cache."""
        if year not in self._holiday_cache:
            self._holiday_cache[year] = self._compute_holidays_for_year(year)
        return self._holiday_cache[year]

    def is_holiday(self, d: date) -> bool:
        """Check if a date is a federal holiday."""
        return d in self._get_holidays_for_year(d.year)

    def get_holiday_name(self, d: date) -> Optional[str]:
        """
        Get the name of a holiday on a given date.

        Args:
            d: Date to check

        Returns:
            Holiday name if it's a holiday, None otherwise
        """
        # Check fixed holidays
        for holiday_date, name in self._get_fixed_holidays(d.year):
            if d == holiday_date:
                return name
            observed = calculate_observed_holiday(holiday_date, self)
            if d == observed and d != holiday_date:
                return f"{name} (Observed)"

        # Check floating holidays
        for holiday_date, name in self._get_floating_holidays(d.year):
            if d == holiday_date:
                return name

        return None

    def get_holidays_for_year(self, year: int) -> list[tuple[date, str]]:
        """
        Get all holidays for a year with names.

        Returns list of (date, name) tuples sorted by date.
        """
        holidays = []

        # Add fixed holidays
        for holiday_date, name in self._get_fixed_holidays(year):
            observed = calculate_observed_holiday(holiday_date, self)
            if observed != holiday_date:
                holidays.append((observed, f"{name} (Observed)"))
            else:
                holidays.append((holiday_date, name))

        # Add floating holidays
        holidays.extend(self._get_floating_holidays(year))

        return sorted(holidays, key=lambda x: x[0])


# Pre-configured calendar instances
US_FEDERAL_CALENDAR = USFederalCalendar()


@lru_cache(maxsize=128)
def get_us_federal_holidays(year: int) -> frozenset[date]:
    """
    Get US federal holidays for a year (cached).

    Args:
        year: Year to get holidays for

    Returns:
        Frozenset of holiday dates
    """
    return frozenset(US_FEDERAL_CALENDAR._get_holidays_for_year(year))


def is_us_federal_holiday(d: date) -> bool:
    """
    Check if a date is a US federal holiday.

    Uses the default US Federal calendar.

    Args:
        d: Date to check

    Returns:
        True if it's a federal holiday
    """
    return US_FEDERAL_CALENDAR.is_holiday(d)


def is_us_business_day(d: date) -> bool:
    """
    Check if a date is a US business day.

    A business day is a weekday that is not a federal holiday.

    Args:
        d: Date to check

    Returns:
        True if it's a business day
    """
    return US_FEDERAL_CALENDAR.is_business_day(d)


def add_us_business_days(start: date, days: int) -> date:
    """
    Add business days using US federal calendar.

    Args:
        start: Starting date
        days: Number of business days to add

    Returns:
        The resulting date
    """
    return US_FEDERAL_CALENDAR.add_business_days(start, days)
