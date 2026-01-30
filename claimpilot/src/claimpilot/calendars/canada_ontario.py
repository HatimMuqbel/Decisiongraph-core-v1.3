"""
Ontario (Canada) Holiday Calendar

Implements Ontario statutory holidays for business day calculations.

Ontario Statutory Holidays:
- New Year's Day (January 1)
- Family Day (3rd Monday in February) - Ontario specific since 2008
- Good Friday (Friday before Easter Sunday)
- Victoria Day (Monday before May 25)
- Canada Day (July 1)
- Civic Holiday (1st Monday in August) - Not statutory but widely observed
- Labour Day (1st Monday in September)
- Thanksgiving Day (2nd Monday in October)
- Christmas Day (December 25)
- Boxing Day (December 26)

Observed holidays: When a statutory holiday falls on a weekend,
the next business day is typically the observed day off.

Reference: Ontario Employment Standards Act, 2000
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from typing import Optional

from .base import BaseCalendar


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
    first_day = date(year, month, 1)
    days_until_weekday = (weekday - first_day.weekday()) % 7
    first_occurrence = first_day + timedelta(days=days_until_weekday)
    return first_occurrence + timedelta(weeks=n - 1)


def _monday_before_date(year: int, month: int, day: int) -> date:
    """
    Get the Monday on or before a specific date.

    Used for Victoria Day (Monday before May 25).
    """
    target = date(year, month, day)
    # Find the Monday on or before the target
    days_since_monday = target.weekday()  # 0=Monday
    return target - timedelta(days=days_since_monday)


def _calculate_easter(year: int) -> date:
    """
    Calculate Easter Sunday using the Anonymous Gregorian algorithm.

    This is the standard algorithm for calculating Easter in Western Christianity.
    """
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _good_friday(year: int) -> date:
    """Calculate Good Friday (2 days before Easter Sunday)."""
    easter = _calculate_easter(year)
    return easter - timedelta(days=2)


@dataclass
class OntarioCalendar(BaseCalendar):
    """
    Ontario (Canada) statutory holiday calendar.

    Implements Ontario's Employment Standards Act holiday schedule
    with proper observed day handling for insurance/regulatory timelines.
    """

    # Include Civic Holiday (August) - not statutory but widely observed
    include_civic_holiday: bool = True

    # Include Boxing Day - statutory in Ontario
    include_boxing_day: bool = True

    # Year Family Day started (2008 in Ontario)
    family_day_start_year: int = 2008

    # Cache for computed holidays
    _holiday_cache: dict[int, set[date]] = field(default_factory=dict, repr=False)

    def _get_fixed_holidays(self, year: int) -> list[tuple[date, str]]:
        """
        Get fixed-date holidays for a year.

        Returns list of (date, name) tuples.
        """
        holidays = [
            (date(year, 1, 1), "New Year's Day"),
            (date(year, 7, 1), "Canada Day"),
            (date(year, 12, 25), "Christmas Day"),
        ]

        if self.include_boxing_day:
            holidays.append((date(year, 12, 26), "Boxing Day"))

        return holidays

    def _get_floating_holidays(self, year: int) -> list[tuple[date, str]]:
        """
        Get floating holidays (relative to weekday/Easter) for a year.

        Returns list of (date, name) tuples.
        """
        holidays = [
            # Good Friday: Friday before Easter
            (_good_friday(year), "Good Friday"),
            # Victoria Day: Monday before May 25
            (_monday_before_date(year, 5, 25), "Victoria Day"),
            # Labour Day: 1st Monday in September
            (_nth_weekday_of_month(year, 9, 0, 1), "Labour Day"),
            # Thanksgiving: 2nd Monday in October
            (_nth_weekday_of_month(year, 10, 0, 2), "Thanksgiving Day"),
        ]

        # Family Day: 3rd Monday in February (since 2008)
        if year >= self.family_day_start_year:
            holidays.append(
                (_nth_weekday_of_month(year, 2, 0, 3), "Family Day")
            )

        # Civic Holiday: 1st Monday in August (not statutory but observed)
        if self.include_civic_holiday:
            holidays.append(
                (_nth_weekday_of_month(year, 8, 0, 1), "Civic Holiday")
            )

        return holidays

    def _calculate_observed(self, holiday: date) -> date:
        """
        Calculate observed date for Ontario holidays.

        In Ontario, if a statutory holiday falls on a weekend,
        the employee gets a substitute day off (typically the next Monday).
        For regulatory purposes, we observe on the next business day.
        """
        if holiday.weekday() == 5:  # Saturday
            return holiday + timedelta(days=2)  # Monday
        elif holiday.weekday() == 6:  # Sunday
            return holiday + timedelta(days=1)  # Monday
        return holiday

    def _compute_holidays_for_year(self, year: int) -> set[date]:
        """
        Compute all holidays for a year, including observed dates.
        """
        holidays = set()

        # Add fixed holidays with observed handling
        for holiday_date, _ in self._get_fixed_holidays(year):
            holidays.add(holiday_date)
            observed = self._calculate_observed(holiday_date)
            if observed != holiday_date:
                holidays.add(observed)

        # Handle Christmas/Boxing Day overlap specially
        christmas = date(year, 12, 25)
        boxing_day = date(year, 12, 26)

        if self.include_boxing_day:
            # If Christmas is Saturday: Christmas observed Mon, Boxing Day observed Tue
            if christmas.weekday() == 5:
                holidays.add(date(year, 12, 27))  # Monday for Christmas
                holidays.add(date(year, 12, 28))  # Tuesday for Boxing Day
            # If Christmas is Sunday: Christmas observed Mon, Boxing Day observed Tue
            elif christmas.weekday() == 6:
                holidays.add(date(year, 12, 26))  # Monday for Christmas
                holidays.add(date(year, 12, 27))  # Tuesday for Boxing Day
            # If Christmas is Friday: Boxing Day Saturday, observed Mon
            elif christmas.weekday() == 4:
                holidays.add(date(year, 12, 28))  # Monday for Boxing Day

        # Add floating holidays (these are already on weekdays)
        for holiday_date, _ in self._get_floating_holidays(year):
            holidays.add(holiday_date)

        return holidays

    def _get_holidays_for_year(self, year: int) -> set[date]:
        """Get holidays for a year, using cache."""
        if year not in self._holiday_cache:
            self._holiday_cache[year] = self._compute_holidays_for_year(year)
        return self._holiday_cache[year]

    def is_holiday(self, d: date) -> bool:
        """Check if a date is an Ontario statutory holiday."""
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
            observed = self._calculate_observed(holiday_date)
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
            observed = self._calculate_observed(holiday_date)
            if observed != holiday_date:
                holidays.append((holiday_date, name))
                holidays.append((observed, f"{name} (Observed)"))
            else:
                holidays.append((holiday_date, name))

        # Add floating holidays
        holidays.extend(self._get_floating_holidays(year))

        return sorted(holidays, key=lambda x: x[0])


# Pre-configured calendar instances
ONTARIO_CALENDAR = OntarioCalendar()


@lru_cache(maxsize=128)
def get_ontario_holidays(year: int) -> frozenset[date]:
    """
    Get Ontario statutory holidays for a year (cached).

    Args:
        year: Year to get holidays for

    Returns:
        Frozenset of holiday dates
    """
    return frozenset(ONTARIO_CALENDAR._get_holidays_for_year(year))


def is_ontario_holiday(d: date) -> bool:
    """
    Check if a date is an Ontario statutory holiday.

    Uses the default Ontario calendar.

    Args:
        d: Date to check

    Returns:
        True if it's a statutory holiday
    """
    return ONTARIO_CALENDAR.is_holiday(d)


def is_ontario_business_day(d: date) -> bool:
    """
    Check if a date is an Ontario business day.

    A business day is a weekday that is not a statutory holiday.

    Args:
        d: Date to check

    Returns:
        True if it's a business day
    """
    return ONTARIO_CALENDAR.is_business_day(d)


def add_ontario_business_days(start: date, days: int) -> date:
    """
    Add business days using Ontario calendar.

    Args:
        start: Starting date
        days: Number of business days to add

    Returns:
        The resulting date
    """
    return ONTARIO_CALENDAR.add_business_days(start, days)


def ontario_business_days_between(start: date, end: date) -> int:
    """
    Count business days between two dates using Ontario calendar.

    Args:
        start: Start date (exclusive)
        end: End date (inclusive)

    Returns:
        Number of business days
    """
    return ONTARIO_CALENDAR.business_days_between(start, end)
