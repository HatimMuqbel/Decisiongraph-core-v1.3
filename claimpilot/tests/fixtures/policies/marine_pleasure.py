"""
Marine Pleasure Craft Policy for testing.

Exclusions:
- Navigation limits
- Operator unqualified (no PCOC)
- Ice damage while in water
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
def policy_marine_pleasure():
    """Create marine pleasure craft policy."""
    return make_policy(
        id="CA-ON-MARINE-2024",
        jurisdiction="CA-ON",
        line_of_business=LineOfBusiness.MARINE,
        product_code="PLEASURE",
        name="Pleasure Craft Policy",
        coverage_sections=[
            make_coverage_section(
                id="hull_machinery",
                name="Hull and Machinery",
                code="Section A",
                triggers=[
                    LossTypeTrigger(loss_type="storm_damage"),
                    LossTypeTrigger(loss_type="collision"),
                    LossTypeTrigger(loss_type="sinking"),
                ],
            ),
        ],
        exclusions=[
            make_exclusion(
                id="ex_navigation_limits",
                name="Outside Navigation Limits",
                code="E-1",
                policy_wording="We do not cover loss outside approved navigation limits.",
                policy_section_ref="Section E.1",
                applies_to_coverages=["hull_machinery"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.EQ,
                        field="vessel.within_navigation_limits",
                        value=False,
                    ),
                ],
            ),
            make_exclusion(
                id="ex_operator_unqualified",
                name="Operator Unqualified",
                code="E-2",
                policy_wording="We do not cover loss while operated by a person without a valid Pleasure Craft Operator Card.",
                policy_section_ref="Section E.2",
                applies_to_coverages=["hull_machinery"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.EQ,
                        field="operator.pcoc_valid",
                        value=False,
                    ),
                ],
            ),
            make_exclusion(
                id="ex_ice_damage",
                name="Ice Damage",
                code="E-3",
                policy_wording="We do not cover loss caused by ice while the vessel is in water.",
                policy_section_ref="Section E.3",
                applies_to_coverages=["hull_machinery"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.AND,
                        children=[
                            make_condition(
                                op=ConditionOperator.EQ,
                                field="damage.cause",
                                value="ice",
                            ),
                            make_condition(
                                op=ConditionOperator.EQ,
                                field="vessel.in_water",
                                value=True,
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
