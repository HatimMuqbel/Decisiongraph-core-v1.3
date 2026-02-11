"""
US Federal Holiday Calendar

Implements the US Federal holiday schedule for business day calculations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from typing import Optional

from kernel.calendars.base import BaseCalendar, calculate_observed_holiday


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """Get the nth occurrence of a weekday in a month."""
    first_day = date(year, month, 1)
    days_until_weekday = (weekday - first_day.weekday()) % 7
    first_occurrence = first_day + timedelta(days=days_until_weekday)
    return first_occurrence + timedelta(weeks=n - 1)


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    """Get the last occurrence of a weekday in a month."""
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    days_since_weekday = (last_day.weekday() - weekday) % 7
    return last_day - timedelta(days=days_since_weekday)


@dataclass
class USFederalCalendar(BaseCalendar):
    """US Federal holiday calendar."""

    include_juneteenth: bool = True
    include_columbus_day: bool = True
    juneteenth_start_year: int = 2021
    _holiday_cache: dict[int, set[date]] = field(default_factory=dict, repr=False)

    def _get_fixed_holidays(self, year: int) -> list[tuple[date, str]]:
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
        holidays = [
            (_nth_weekday_of_month(year, 1, 0, 3), "Martin Luther King Jr. Day"),
            (_nth_weekday_of_month(year, 2, 0, 3), "Presidents' Day"),
            (_last_weekday_of_month(year, 5, 0), "Memorial Day"),
            (_nth_weekday_of_month(year, 9, 0, 1), "Labor Day"),
            (_nth_weekday_of_month(year, 11, 3, 4), "Thanksgiving Day"),
        ]
        if self.include_columbus_day:
            holidays.append(
                (_nth_weekday_of_month(year, 10, 0, 2), "Columbus Day")
            )
        return holidays

    def _compute_holidays_for_year(self, year: int) -> set[date]:
        holidays = set()
        for holiday_date, _ in self._get_fixed_holidays(year):
            observed = calculate_observed_holiday(holiday_date, self)
            holidays.add(observed)
            if observed != holiday_date:
                holidays.add(holiday_date)
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
            observed = calculate_observed_holiday(holiday_date, self)
            if d == observed and d != holiday_date:
                return f"{name} (Observed)"
        for holiday_date, name in self._get_floating_holidays(d.year):
            if d == holiday_date:
                return name
        return None

    def get_holidays_for_year(self, year: int) -> list[tuple[date, str]]:
        holidays = []
        for holiday_date, name in self._get_fixed_holidays(year):
            observed = calculate_observed_holiday(holiday_date, self)
            if observed != holiday_date:
                holidays.append((observed, f"{name} (Observed)"))
            else:
                holidays.append((holiday_date, name))
        holidays.extend(self._get_floating_holidays(year))
        return sorted(holidays, key=lambda x: x[0])


# Pre-configured calendar instances
US_FEDERAL_CALENDAR = USFederalCalendar()


@lru_cache(maxsize=128)
def get_us_federal_holidays(year: int) -> frozenset[date]:
    """Get US federal holidays for a year (cached)."""
    return frozenset(US_FEDERAL_CALENDAR._get_holidays_for_year(year))


def is_us_federal_holiday(d: date) -> bool:
    """Check if a date is a US federal holiday."""
    return US_FEDERAL_CALENDAR.is_holiday(d)


def is_us_business_day(d: date) -> bool:
    """Check if a date is a US business day."""
    return US_FEDERAL_CALENDAR.is_business_day(d)


def add_us_business_days(start: date, days: int) -> date:
    """Add business days using US federal calendar."""
    return US_FEDERAL_CALENDAR.add_business_days(start, days)
