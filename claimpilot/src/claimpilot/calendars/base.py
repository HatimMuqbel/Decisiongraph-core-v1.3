"""Backward-compatible shim. Real implementation in kernel.calendars.base."""
from kernel.calendars.base import *  # noqa: F401,F403
from kernel.calendars.base import (  # explicit re-exports for type checkers
    BaseCalendar,
    FixedHolidayCalendar,
    HolidayCalendar,
    NoHolidayCalendar,
    calculate_observed_holiday,
)
