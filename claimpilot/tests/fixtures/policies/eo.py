"""
Professional Liability E&O Policy for testing.

Claims-made policy with exclusions:
- Prior acts (before retro date)
- Intentional/dishonest acts
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
def policy_eo():
    """Create E&O policy (claims-made)."""
    return make_policy(
        id="US-EO-2024",
        jurisdiction="US-NY",
        line_of_business=LineOfBusiness.PROFESSIONAL,
        product_code="EO",
        name="Professional Liability E&O",
        coverage_sections=[
            make_coverage_section(
                id="professional_services",
                name="Professional Services Coverage",
                code="Section A",
                triggers=[
                    LossTypeTrigger(loss_type="professional_negligence"),
                ],
                preconditions=[
                    make_condition(
                        op=ConditionOperator.EQ,
                        field="claim.first_made_during_policy",
                        value=True,
                    ),
                ],
            ),
        ],
        exclusions=[
            make_exclusion(
                id="ex_prior_acts",
                name="Prior Acts",
                code="E-1",
                policy_wording="This policy does not cover claims arising from wrongful acts occurring before the retroactive date.",
                policy_section_ref="Section E.1",
                applies_to_coverages=["professional_services"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.EQ,
                        field="wrongful_act.before_retro_date",
                        value=True,
                    ),
                ],
            ),
            make_exclusion(
                id="ex_intentional",
                name="Intentional or Dishonest Acts",
                code="E-2",
                policy_wording="This policy does not cover claims arising from fraudulent, dishonest, or intentional acts.",
                policy_section_ref="Section E.2",
                applies_to_coverages=["professional_services"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.EQ,
                        field="act.fraudulent",
                        value=True,
                    ),
                ],
            ),
        ],
    )
