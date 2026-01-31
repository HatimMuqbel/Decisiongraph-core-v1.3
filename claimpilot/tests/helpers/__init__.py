"""
Test helpers for ClaimPilot real claim scenario tests.

Modules:
- contract: Scenario and Expected dataclasses
- facts: Fact creation helpers
- runner: Engine execution wrapper
- assertions: Contract verification helpers
"""
from .contract import Expected, Scenario
from .facts import facts, create_facts_dict
from .runner import run_scenario, make_context
from .assertions import (
    assert_contract,
    assert_disposition,
    assert_exclusions,
    assert_provenance,
    assert_reasoning,
)

__all__ = [
    # Contract
    "Expected",
    "Scenario",
    # Facts
    "facts",
    "create_facts_dict",
    # Runner
    "run_scenario",
    "make_context",
    # Assertions
    "assert_contract",
    "assert_disposition",
    "assert_exclusions",
    "assert_provenance",
    "assert_reasoning",
]
