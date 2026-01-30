"""
ClaimPilot Calendars

Holiday calendars for business day calculations.

Primary focus: Ontario, Canada statutory holidays for insurance regulatory timelines.

Provides:
- HolidayCalendar protocol for custom implementations
- BaseCalendar with common business day logic
- OntarioCalendar for Ontario statutory holidays (primary)
- USFederalCalendar for US federal holidays
- Utility functions for quick checks

Usage:
    from claimpilot.calendars import (
        OntarioCalendar,
        is_ontario_business_day,
        add_ontario_business_days,
    )

    # Use the default Ontario calendar
    if is_ontario_business_day(date.today()):
        print("It's a business day!")

    # Calculate a regulatory deadline (e.g., 15 business days)
    deadline = add_ontario_business_days(date.today(), 15)

    # Count business days between dates
    days = ontario_business_days_between(start_date, end_date)

    # Custom calendar configuration
    calendar = OntarioCalendar(include_civic_holiday=False)
"""
from __future__ import annotations

from .base import (
    BaseCalendar,
    FixedHolidayCalendar,
    HolidayCalendar,
    NoHolidayCalendar,
    calculate_observed_holiday,
)
from .canada_ontario import (
    ONTARIO_CALENDAR,
    OntarioCalendar,
    add_ontario_business_days,
    get_ontario_holidays,
    is_ontario_business_day,
    is_ontario_holiday,
    ontario_business_days_between,
)
from .us_federal import (
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
    # Ontario (Canada) - Primary
    "OntarioCalendar",
    "ONTARIO_CALENDAR",
    "get_ontario_holidays",
    "is_ontario_holiday",
    "is_ontario_business_day",
    "add_ontario_business_days",
    "ontario_business_days_between",
    # US Federal - Secondary
    "USFederalCalendar",
    "US_FEDERAL_CALENDAR",
    "get_us_federal_holidays",
    "is_us_federal_holiday",
    "is_us_business_day",
    "add_us_business_days",
]
