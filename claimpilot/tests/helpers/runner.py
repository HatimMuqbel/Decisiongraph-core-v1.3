"""
Scenario execution runner.

Provides a consistent interface for running claim scenarios
through the recommendation engine.
"""
from datetime import date
from typing import TYPE_CHECKING

from claimpilot.models import (
    ClaimantType,
    ClaimContext,
    EvidenceItem,
    EvidenceStatus,
    LineOfBusiness,
    Policy,
    RecommendationRecord,
)
from claimpilot.engine import RecommendationBuilder

if TYPE_CHECKING:
    from .contract import Scenario


# =============================================================================
# Line-of-Business Configuration
# =============================================================================

LINE_CONFIG = {
    "auto": {
        "line_of_business": LineOfBusiness.AUTO,
        "jurisdiction": "CA-ON",
        "default_loss_type": "collision",
    },
    "property": {
        "line_of_business": LineOfBusiness.PROPERTY,
        "jurisdiction": "US-NY",
        "default_loss_type": "fire",
    },
    "marine": {
        "line_of_business": LineOfBusiness.MARINE,
        "jurisdiction": "CA-ON",
        "default_loss_type": "storm_damage",
    },
    "health": {
        "line_of_business": LineOfBusiness.HEALTH,
        "jurisdiction": "CA-ON",
        "default_loss_type": "prescription_drug",
    },
    "workers_comp": {
        "line_of_business": LineOfBusiness.WORKERS_COMP,
        "jurisdiction": "CA-ON",
        "default_loss_type": "work_injury",
    },
    "cgl": {
        "line_of_business": LineOfBusiness.LIABILITY,
        "jurisdiction": "US-NY",
        "default_loss_type": "bodily_injury_tp",
    },
    "eo": {
        "line_of_business": LineOfBusiness.PROFESSIONAL,
        "jurisdiction": "US-NY",
        "default_loss_type": "professional_negligence",
    },
    "travel": {
        "line_of_business": LineOfBusiness.OTHER,
        "jurisdiction": "CA-ON",
        "default_loss_type": "emergency_medical",
    },
}


# =============================================================================
# Context Builder
# =============================================================================

def make_context(
    *,
    line: str,
    facts: dict,
    claim_id: str = None,
    policy_id: str = None,
    loss_type: str = None,
    loss_date: date = None,
    report_date: date = None,
    claimant_type: ClaimantType = ClaimantType.INSURED,
    evidence: list[EvidenceItem] = None,
) -> ClaimContext:
    """
    Create a ClaimContext for a given line of business.

    Args:
        line: Line of business key ("auto", "property", etc.)
        facts: Dict of field -> Fact (from facts() helper)
        claim_id: Optional claim ID
        policy_id: Optional policy ID
        loss_type: Override default loss type for line
        loss_date: Override default loss date
        report_date: Override default report date
        claimant_type: Claimant relationship to policy
        evidence: Optional list of evidence items

    Returns:
        Configured ClaimContext
    """
    config = LINE_CONFIG.get(line, LINE_CONFIG["auto"])

    return ClaimContext(
        claim_id=claim_id or f"{line.upper()}-{hash(id(facts)) % 10000:04d}",
        policy_id=policy_id or f"{config['jurisdiction']}-{line.upper()}-2024",
        jurisdiction=config["jurisdiction"],
        line_of_business=config["line_of_business"],
        loss_type=loss_type or config["default_loss_type"],
        loss_date=loss_date or date(2024, 6, 15),
        report_date=report_date or date(2024, 6, 15),
        claimant_type=claimant_type,
        facts=facts,
        evidence=evidence or [],
    )


# =============================================================================
# Scenario Runner
# =============================================================================

# Policy registry - populated by fixtures/__init__.py
_POLICY_REGISTRY: dict[str, callable] = {}


def register_policy(line: str, policy_factory: callable):
    """Register a policy factory for a line of business."""
    _POLICY_REGISTRY[line] = policy_factory


def get_policy(line: str) -> Policy:
    """Get policy for a line of business."""
    if line not in _POLICY_REGISTRY:
        raise ValueError(
            f"No policy registered for line '{line}'. "
            f"Available: {list(_POLICY_REGISTRY.keys())}"
        )
    return _POLICY_REGISTRY[line]()


def run_scenario(
    scenario: "Scenario",
) -> tuple[Policy, ClaimContext, RecommendationRecord]:
    """
    Execute a scenario through the recommendation engine.

    Args:
        scenario: Scenario to execute

    Returns:
        Tuple of (policy, context, recommendation)
    """
    policy = get_policy(scenario.line)
    context = scenario.build_context()

    builder = RecommendationBuilder()
    recommendation = builder.build(policy, context)

    return policy, context, recommendation


def run_context(
    line: str,
    context: ClaimContext,
) -> tuple[Policy, RecommendationRecord]:
    """
    Run a context directly (without scenario wrapper).

    Args:
        line: Line of business
        context: Pre-built claim context

    Returns:
        Tuple of (policy, recommendation)
    """
    policy = get_policy(line)
    builder = RecommendationBuilder()
    recommendation = builder.build(policy, context)
    return policy, recommendation
