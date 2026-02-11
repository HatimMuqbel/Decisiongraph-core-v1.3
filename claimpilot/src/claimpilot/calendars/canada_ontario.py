"""Backward-compatible shim. Real implementation in kernel.calendars.canada_ontario."""
from kernel.calendars.canada_ontario import *  # noqa: F401,F403
from kernel.calendars.canada_ontario import (  # explicit re-exports for type checkers
    ONTARIO_CALENDAR,
    OntarioCalendar,
    add_ontario_business_days,
    get_ontario_holidays,
    is_ontario_business_day,
    is_ontario_holiday,
    ontario_business_days_between,
)
