"""
Scenario contract types for real claim tests.

These types define what a test scenario looks like and what we expect
from the recommendation engine. Using frozen dataclasses ensures
scenarios are immutable and hashable.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from claimpilot.models import ClaimContext


@dataclass(frozen=True)
class Expected:
    """
    Expected outcome from a claim scenario.

    Defines what the recommendation should contain, including:
    - disposition (PAY, DENY, etc.)
    - which exclusions must/must-not apply
    - minimum reasoning steps
    - provenance requirements
    """
    # Core outcome
    disposition: str  # "PAY" | "DENY" | "ESCALATE" | "REQUEST_INFO" | etc.

    # Exclusion assertions (use exclusion IDs like "ex_commercial_use")
    must_apply_exclusions: frozenset[str] = field(default_factory=frozenset)
    must_not_apply_exclusions: frozenset[str] = field(default_factory=frozenset)

    # Coverage assertions (use coverage IDs)
    must_trigger_coverages: frozenset[str] = field(default_factory=frozenset)

    # Authority citations (optional, for scenarios that need specific citations)
    must_cite_sections: frozenset[str] = field(default_factory=frozenset)

    # Reasoning requirements
    min_reasoning_steps: int = 3  # Coverage, Exclusion, Disposition at minimum

    # Provenance requirements
    require_provenance: bool = True

    # Certainty (optional)
    certainty: Optional[str] = None  # "high", "medium", "low"


@dataclass(frozen=True)
class Scenario:
    """
    A complete claim scenario for testing.

    Scenarios are identified by a stable ID (e.g., "auto.collision.clean")
    and contain a builder function that creates the claim context.
    """
    id: str  # Stable ID: "auto.collision.clean", "property.flood.deny"
    line: str  # "auto", "property", "marine", etc.
    description: str  # Human-readable scenario description
    build_context: Callable[[], "ClaimContext"]  # Returns claim context
    expected: Expected

    def __repr__(self) -> str:
        return f"Scenario({self.id})"


def expected_pay(
    *,
    must_trigger_coverages: set[str] = None,
    must_not_apply_exclusions: set[str] = None,
    certainty: str = "high",
) -> Expected:
    """Helper to create an Expected for PAY scenarios."""
    return Expected(
        disposition="PAY",
        must_trigger_coverages=frozenset(must_trigger_coverages or set()),
        must_not_apply_exclusions=frozenset(must_not_apply_exclusions or set()),
        certainty=certainty,
    )


def expected_deny(
    *,
    by_exclusion: str = None,
    by_exclusions: set[str] = None,
    must_not_apply_exclusions: set[str] = None,
    must_cite_sections: set[str] = None,
    certainty: str = "high",
) -> Expected:
    """Helper to create an Expected for DENY scenarios."""
    exclusions = set()
    if by_exclusion:
        exclusions.add(by_exclusion)
    if by_exclusions:
        exclusions.update(by_exclusions)

    return Expected(
        disposition="DENY",
        must_apply_exclusions=frozenset(exclusions),
        must_not_apply_exclusions=frozenset(must_not_apply_exclusions or set()),
        must_cite_sections=frozenset(must_cite_sections or set()),
        certainty=certainty,
    )


def expected_deny_no_coverage(
    *,
    certainty: str = "high",
) -> Expected:
    """Helper for DENY due to no coverage triggered (not exclusion)."""
    return Expected(
        disposition="DENY",
        must_trigger_coverages=frozenset(),  # Explicitly empty
        must_apply_exclusions=frozenset(),  # No exclusions
        certainty=certainty,
    )
