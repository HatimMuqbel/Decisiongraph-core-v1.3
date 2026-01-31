"""
Fact creation helpers for claim scenarios.

Provides a clean interface for creating facts dictionaries
without verbose Fact object construction.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from claimpilot.models import (
    Fact,
    FactCertainty,
    FactSource,
)


def facts(fact_map: dict, claim_id: str = "CLM-001") -> dict[str, Fact]:
    """
    Convert a simple key-value map to Fact objects.

    Args:
        fact_map: Dict of field -> value
        claim_id: Claim ID to associate facts with

    Returns:
        Dict of field -> Fact

    Example:
        >>> f = facts({
        ...     "policy.status": "active",
        ...     "driver.bac_level": 0.0,
        ...     "loss.racing_activity": False,
        ... })
    """
    return {
        field: _make_fact(field, value, claim_id)
        for field, value in fact_map.items()
    }


def _make_fact(
    field: str,
    value,
    claim_id: str,
    source: FactSource = FactSource.ADJUSTER_INPUT,
    certainty: FactCertainty = FactCertainty.REPORTED,
) -> Fact:
    """Create a Fact with inferred value type."""
    # Infer value type
    if isinstance(value, bool):
        value_type = "boolean"
    elif isinstance(value, (int, float)):
        value_type = "number"
    elif isinstance(value, Decimal):
        value_type = "decimal"
    elif isinstance(value, date):
        value_type = "date"
    elif isinstance(value, list):
        value_type = "list"
    else:
        value_type = "string"

    return Fact(
        id=str(uuid4()),
        claim_id=claim_id,
        field=field,
        value=value,
        value_type=value_type,
        source=source,
        certainty=certainty,
    )


# Alias for backwards compatibility
create_facts_dict = facts
