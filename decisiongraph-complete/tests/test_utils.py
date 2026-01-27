"""
Test utilities for DecisionGraph v1.3

Fixed test times to ensure deterministic, non-flaky tests.
Rule: tests must NOT call now() or get_current_timestamp().
"""

# Base test time - all tests use offsets from this
BASE_TEST_TIME = "2026-01-27T10:00:00Z"

# Sequential timestamps for ordering tests
T0 = BASE_TEST_TIME
T1 = "2026-01-27T10:00:01Z"
T2 = "2026-01-27T10:00:02Z"
T3 = "2026-01-27T10:00:03Z"
T4 = "2026-01-27T10:00:04Z"
T5 = "2026-01-27T10:00:05Z"

# Future time for valid_to tests
T_FUTURE = "2026-02-01T00:00:00Z"

# Past times for bitemporal queries
T_PAST_JAN = "2025-01-15T00:00:00Z"
T_PAST_JUN = "2025-06-01T00:00:00Z"
T_PAST_AUG = "2025-08-15T00:00:00Z"
