"""
Kernel Calendars — jurisdiction-portable business day calculations.

Provides pluggable holiday calendars for regulatory deadline computation
across all decision domains.

Re-exports from base, Ontario (Canada), and US Federal calendars.
"""
from __future__ import annotations

from kernel.calendars.base import (
    BaseCalendar,
    FixedHolidayCalendar,
    HolidayCalendar,
    NoHolidayCalendar,
    calculate_observed_holiday,
)
from kernel.calendars.canada_ontario import (
    ONTARIO_CALENDAR,
    OntarioCalendar,
    add_ontario_business_days,
    get_ontario_holidays,
    is_ontario_business_day,
    is_ontario_holiday,
    ontario_business_days_between,
)
from kernel.calendars.us_federal import (
    US_FEDERAL_CALENDAR,
    USFederalCalendar,
    add_us_business_days,
    get_us_federal_holidays,
    is_us_business_day,
    is_us_federal_holiday,
)

__all__ = [
    # Protocols and base classes
    "HolidayCalendar",
    "BaseCalendar",
    "NoHolidayCalendar",
    "FixedHolidayCalendar",
    "calculate_observed_holiday",
    # Ontario (Canada)
    "OntarioCalendar",
    "ONTARIO_CALENDAR",
    "get_ontario_holidays",
    "is_ontario_holiday",
    "is_ontario_business_day",
    "add_ontario_business_days",
    "ontario_business_days_between",
    # US Federal
    "USFederalCalendar",
    "US_FEDERAL_CALENDAR",
    "get_us_federal_holidays",
    "is_us_federal_holiday",
    "is_us_business_day",
    "add_us_business_days",
]
