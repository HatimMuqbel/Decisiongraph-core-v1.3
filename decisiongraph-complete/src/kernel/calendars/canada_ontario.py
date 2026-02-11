"""
Ontario (Canada) Holiday Calendar

Implements Ontario statutory holidays for business day calculations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from typing import Optional

from kernel.calendars.base import BaseCalendar


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """Get the nth occurrence of a weekday in a month."""
    first_day = date(year, month, 1)
    days_until_weekday = (weekday - first_day.weekday()) % 7
    first_occurrence = first_day + timedelta(days=days_until_weekday)
    return first_occurrence + timedelta(weeks=n - 1)


def _monday_before_date(year: int, month: int, day: int) -> date:
    """Get the Monday on or before a specific date."""
    target = date(year, month, day)
    days_since_monday = target.weekday()
    return target - timedelta(days=days_since_monday)


def _calculate_easter(year: int) -> date:
    """Calculate Easter Sunday using the Anonymous Gregorian algorithm."""
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
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
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
    """Ontario (Canada) statutory holiday calendar."""

    include_civic_holiday: bool = True
    include_boxing_day: bool = True
    family_day_start_year: int = 2008
    _holiday_cache: dict[int, set[date]] = field(default_factory=dict, repr=False)

    def _get_fixed_holidays(self, year: int) -> list[tuple[date, str]]:
        holidays = [
            (date(year, 1, 1), "New Year's Day"),
            (date(year, 7, 1), "Canada Day"),
            (date(year, 12, 25), "Christmas Day"),
        ]
        if self.include_boxing_day:
            holidays.append((date(year, 12, 26), "Boxing Day"))
        return holidays

    def _get_floating_holidays(self, year: int) -> list[tuple[date, str]]:
        holidays = [
            (_good_friday(year), "Good Friday"),
            (_monday_before_date(year, 5, 25), "Victoria Day"),
            (_nth_weekday_of_month(year, 9, 0, 1), "Labour Day"),
            (_nth_weekday_of_month(year, 10, 0, 2), "Thanksgiving Day"),
        ]
        if year >= self.family_day_start_year:
            holidays.append(
                (_nth_weekday_of_month(year, 2, 0, 3), "Family Day")
            )
        if self.include_civic_holiday:
            holidays.append(
                (_nth_weekday_of_month(year, 8, 0, 1), "Civic Holiday")
            )
        return holidays

    def _calculate_observed(self, holiday: date) -> date:
        """In Ontario, weekend holidays observed on next Monday."""
        if holiday.weekday() == 5:  # Saturday
            return holiday + timedelta(days=2)
        elif holiday.weekday() == 6:  # Sunday
            return holiday + timedelta(days=1)
        return holiday

    def _compute_holidays_for_year(self, year: int) -> set[date]:
        holidays = set()
        for holiday_date, _ in self._get_fixed_holidays(year):
            holidays.add(holiday_date)
            observed = self._calculate_observed(holiday_date)
            if observed != holiday_date:
                holidays.add(observed)

        # Handle Christmas/Boxing Day overlap
        christmas = date(year, 12, 25)
        boxing_day = date(year, 12, 26)
        if self.include_boxing_day:
            if christmas.weekday() == 5:
                holidays.add(date(year, 12, 27))
                holidays.add(date(year, 12, 28))
            elif christmas.weekday() == 6:
                holidays.add(date(year, 12, 26))
                holidays.add(date(year, 12, 27))
            elif christmas.weekday() == 4:
                holidays.add(date(year, 12, 28))

        for holiday_date, _ in self._get_floating_holidays(year):
            holidays.add(holiday_date)
        return holidays

    def _get_holidays_for_year(self, year: int) -> set[date]:
        if year not in self._holiday_cache:
            self._holiday_cache[year] = self._compute_holidays_for_year(year)
        return self._holiday_cache[year]

    def is_holiday(self, d: date) -> bool:
        return d in self._get_holidays_for_year(d.year)

    def get_holiday_name(self, d: date) -> Optional[str]:
        for holiday_date, name in self._get_fixed_holidays(d.year):
            if d == holiday_date:
                return name
            observed = self._calculate_observed(holiday_date)
            if d == observed and d != holiday_date:
                return f"{name} (Observed)"
        for holiday_date, name in self._get_floating_holidays(d.year):
            if d == holiday_date:
                return name
        return None

    def get_holidays_for_year(self, year: int) -> list[tuple[date, str]]:
        holidays = []
        for holiday_date, name in self._get_fixed_holidays(year):
            observed = self._calculate_observed(holiday_date)
            if observed != holiday_date:
                holidays.append((holiday_date, name))
                holidays.append((observed, f"{name} (Observed)"))
            else:
                holidays.append((holiday_date, name))
        holidays.extend(self._get_floating_holidays(year))
        return sorted(holidays, key=lambda x: x[0])


# Pre-configured calendar instances
ONTARIO_CALENDAR = OntarioCalendar()


@lru_cache(maxsize=128)
def get_ontario_holidays(year: int) -> frozenset[date]:
    """Get Ontario statutory holidays for a year (cached)."""
    return frozenset(ONTARIO_CALENDAR._get_holidays_for_year(year))


def is_ontario_holiday(d: date) -> bool:
    """Check if a date is an Ontario statutory holiday."""
    return ONTARIO_CALENDAR.is_holiday(d)


def is_ontario_business_day(d: date) -> bool:
    """Check if a date is an Ontario business day."""
    return ONTARIO_CALENDAR.is_business_day(d)


def add_ontario_business_days(start: date, days: int) -> date:
    """Add business days using Ontario calendar."""
    return ONTARIO_CALENDAR.add_business_days(start, days)


def ontario_business_days_between(start: date, end: date) -> int:
    """Count business days between two dates using Ontario calendar."""
    return ONTARIO_CALENDAR.business_days_between(start, end)
