"""Backward-compatible shim. Real implementation in kernel.calendars.us_federal."""
from kernel.calendars.us_federal import *  # noqa: F401,F403
from kernel.calendars.us_federal import (  # explicit re-exports for type checkers
    US_FEDERAL_CALENDAR,
    USFederalCalendar,
    add_us_business_days,
    get_us_federal_holidays,
    is_us_business_day,
    is_us_federal_holiday,
)
