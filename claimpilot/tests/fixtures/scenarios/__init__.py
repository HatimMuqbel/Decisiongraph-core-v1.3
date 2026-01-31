"""
Scenario definitions for real claim tests.

Each LOB module defines scenarios as functions that return Scenario objects.
The registry collects all scenarios for parametrized testing.
"""
from .registry import all_scenarios, scenarios_by_line

__all__ = [
    "all_scenarios",
    "scenarios_by_line",
]
