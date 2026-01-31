"""
Homeowners Policy (HO-3) for testing.

Standard HO-3 with common exclusions:
- Flood
- Wear and tear / gradual damage
- Vacancy
- Earthquake
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
def policy_property_ho3():
    """Create HO-3 property policy with standard exclusions."""
    return make_policy(
        id="US-HO3-2024",
        jurisdiction="US-NY",
        line_of_business=LineOfBusiness.PROPERTY,
        product_code="HO3",
        name="Homeowners Policy",
        coverage_sections=[
            make_coverage_section(
                id="coverage_a",
                name="Dwelling Coverage",
                code="Coverage A",
                triggers=[
                    LossTypeTrigger(loss_type="fire"),
                    LossTypeTrigger(loss_type="water_damage_sudden"),
                    LossTypeTrigger(loss_type="wind"),
                    LossTypeTrigger(loss_type="hail"),
                ],
            ),
            make_coverage_section(
                id="coverage_c",
                name="Personal Property",
                code="Coverage C",
                triggers=[
                    LossTypeTrigger(loss_type="theft"),
                ],
            ),
        ],
        exclusions=[
            make_exclusion(
                id="ex_flood",
                name="Flood",
                code="E-1",
                policy_wording="We do not cover loss caused by flood, surface water, waves, tidal water, overflow of a body of water.",
                policy_section_ref="Section E.1",
                applies_to_coverages=["coverage_a"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.EQ,
                        field="loss.cause",
                        value="flood",
                    ),
                ],
            ),
            make_exclusion(
                id="ex_wear_tear",
                name="Wear and Tear",
                code="E-2",
                policy_wording="We do not cover loss caused by wear and tear, marring, deterioration, or gradual damage.",
                policy_section_ref="Section E.2",
                applies_to_coverages=["coverage_a"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.EQ,
                        field="damage.gradual",
                        value=True,
                    ),
                ],
            ),
            make_exclusion(
                id="ex_vacancy",
                name="Vacancy",
                code="E-3",
                policy_wording="We do not cover loss if the dwelling has been vacant for more than 30 consecutive days.",
                policy_section_ref="Section E.3",
                applies_to_coverages=["coverage_a", "coverage_c"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.GT,
                        field="dwelling.days_vacant",
                        value=30,
                    ),
                ],
            ),
            make_exclusion(
                id="ex_earthquake",
                name="Earthquake",
                code="E-4",
                policy_wording="We do not cover loss caused by earthquake.",
                policy_section_ref="Section E.4",
                applies_to_coverages=["coverage_a"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.EQ,
                        field="loss.cause",
                        value="earthquake",
                    ),
                ],
            ),
        ],
    )
