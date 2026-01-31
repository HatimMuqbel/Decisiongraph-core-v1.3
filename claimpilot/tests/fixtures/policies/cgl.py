"""
Commercial General Liability (CGL) Policy for testing.

Exclusions:
- Expected/intended injury
- Pollution
- Auto liability
"""
from functools import lru_cache

from claimpilot.models import (
    ConditionOperator,
    LineOfBusiness,
    LossTypeTrigger,
)
from tests.conftest import (
    make_condition,
    make_coverage_section,
    make_exclusion,
    make_policy,
)


@lru_cache(maxsize=1)
def policy_cgl():
    """Create CGL policy."""
    return make_policy(
        id="US-CGL-2024",
        jurisdiction="US-NY",
        line_of_business=LineOfBusiness.LIABILITY,
        product_code="CGL",
        name="Commercial General Liability",
        coverage_sections=[
            make_coverage_section(
                id="coverage_a",
                name="Bodily Injury and Property Damage",
                code="Coverage A",
                triggers=[
                    LossTypeTrigger(loss_type="bodily_injury_tp"),
                    LossTypeTrigger(loss_type="property_damage_tp"),
                ],
            ),
        ],
        exclusions=[
            make_exclusion(
                id="ex_expected_intended",
                name="Expected or Intended Injury",
                code="A-1",
                policy_wording="This insurance does not apply to bodily injury or property damage expected or intended from the standpoint of the insured.",
                policy_section_ref="Section A.1",
                applies_to_coverages=["coverage_a"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.EQ,
                        field="injury.expected_intended",
                        value=True,
                    ),
                ],
            ),
            make_exclusion(
                id="ex_pollution",
                name="Pollution",
                code="A-2",
                policy_wording="This insurance does not apply to bodily injury or property damage arising out of the discharge of pollutants.",
                policy_section_ref="Section A.2",
                applies_to_coverages=["coverage_a"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.EQ,
                        field="loss.pollution_related",
                        value=True,
                    ),
                ],
            ),
            make_exclusion(
                id="ex_auto",
                name="Automobile Liability",
                code="A-3",
                policy_wording="This insurance does not apply to bodily injury or property damage arising out of ownership or operation of an auto.",
                policy_section_ref="Section A.3",
                applies_to_coverages=["coverage_a"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.EQ,
                        field="loss.auto_involved",
                        value=True,
                    ),
                ],
            ),
        ],
    )
