"""
Ontario WSIB Workers Compensation Policy for testing.

Exclusions:
- Not work related
- Pre-existing not aggravated
- Intoxication as sole cause
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
def policy_wsib_ontario():
    """Create WSIB policy."""
    return make_policy(
        id="CA-ON-WSIB-2024",
        jurisdiction="CA-ON",
        line_of_business=LineOfBusiness.WORKERS_COMP,
        product_code="WSIB",
        name="WSIB Entitlement",
        coverage_sections=[
            make_coverage_section(
                id="loss_of_earnings",
                name="Loss of Earnings",
                code="Section 43",
                triggers=[
                    LossTypeTrigger(loss_type="work_injury"),
                ],
                preconditions=[
                    make_condition(
                        op=ConditionOperator.AND,
                        children=[
                            make_condition(
                                op=ConditionOperator.EQ,
                                field="injury.work_related",
                                value=True,
                            ),
                            make_condition(
                                op=ConditionOperator.EQ,
                                field="employer.wsib_registered",
                                value=True,
                            ),
                        ],
                    ),
                ],
            ),
        ],
        exclusions=[
            make_exclusion(
                id="ex_not_work_related",
                name="Not Work Related",
                code="E-1",
                policy_wording="Entitlement is limited to injuries arising out of and in the course of employment.",
                policy_section_ref="Section 13",
                applies_to_coverages=["loss_of_earnings"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.EQ,
                        field="injury.work_related",
                        value=False,
                    ),
                ],
            ),
            make_exclusion(
                id="ex_preexisting",
                name="Pre-existing Not Aggravated",
                code="E-2",
                policy_wording="Pre-existing conditions are only covered if significantly aggravated by work.",
                policy_section_ref="Section 15",
                applies_to_coverages=["loss_of_earnings"],
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
                                field="condition.aggravated_by_work",
                                value=False,
                            ),
                        ],
                    ),
                ],
            ),
            make_exclusion(
                id="ex_intoxication",
                name="Intoxication Sole Cause",
                code="E-3",
                policy_wording="Entitlement is not available if intoxication was the sole cause of the injury.",
                policy_section_ref="Section 17",
                applies_to_coverages=["loss_of_earnings"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.EQ,
                        field="injury.intoxication_sole_cause",
                        value=True,
                    ),
                ],
            ),
        ],
    )
