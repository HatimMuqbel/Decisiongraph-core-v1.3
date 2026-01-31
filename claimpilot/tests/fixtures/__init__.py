"""
Test fixtures for ClaimPilot real claim scenario tests.

Structure:
- policies/: Policy factories for each line of business
- scenarios/: Scenario definitions for each line of business
"""
# Register all policies with the runner
from .policies import register_all_policies

# Initialize on import
register_all_policies()
