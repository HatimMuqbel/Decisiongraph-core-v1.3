"""
Travel Medical Insurance Policy for testing.

Exclusions:
- Pre-existing condition (not stable)
- Non-emergency treatment
- High-risk activity
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
def policy_travel():
    """Create travel insurance policy."""
    return make_policy(
        id="CA-TRAVEL-2024",
        jurisdiction="CA-ON",
        line_of_business=LineOfBusiness.OTHER,
        product_code="TRAVEL",
        name="Travel Medical Insurance",
        coverage_sections=[
            make_coverage_section(
                id="emergency_medical",
                name="Emergency Medical",
                code="Section A",
                triggers=[
                    LossTypeTrigger(loss_type="emergency_medical"),
                ],
                preconditions=[
                    make_condition(
                        op=ConditionOperator.EQ,
                        field="insured.outside_home_province",
                        value=True,
                    ),
                ],
            ),
        ],
        exclusions=[
            make_exclusion(
                id="ex_preexisting",
                name="Pre-existing Condition",
                code="E-1",
                policy_wording="We do not cover claims arising from pre-existing conditions that were not stable for 90 days prior to departure.",
                policy_section_ref="Section E.1",
                applies_to_coverages=["emergency_medical"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.AND,
                        children=[
                            make_condition(
                                op=ConditionOperator.EQ,
                                field="condition.preexisting",
                                value=True,
                            ),
                            make_condition(
                                op=ConditionOperator.EQ,
                                field="condition.stable",
                                value=False,
                            ),
                        ],
                    ),
                ],
            ),
            make_exclusion(
                id="ex_not_emergency",
                name="Non-Emergency Treatment",
                code="E-2",
                policy_wording="We do not cover elective or non-emergency treatment.",
                policy_section_ref="Section E.2",
                applies_to_coverages=["emergency_medical"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.EQ,
                        field="treatment.emergency",
                        value=False,
                    ),
                ],
            ),
            make_exclusion(
                id="ex_high_risk",
                name="High Risk Activity",
                code="E-3",
                policy_wording="We do not cover injuries from high-risk activities without specific endorsement.",
                policy_section_ref="Section E.3",
                applies_to_coverages=["emergency_medical"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.EQ,
                        field="activity.high_risk",
                        value=True,
                    ),
                ],
            ),
        ],
    )
