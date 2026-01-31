"""
Group Health Policy for testing.

Exclusions:
- Non-formulary drug (without prior auth)
- Pre-existing condition
- Work-related injury
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
def policy_health_group():
    """Create group health policy."""
    return make_policy(
        id="CA-ON-GROUP-HEALTH-2024",
        jurisdiction="CA-ON",
        line_of_business=LineOfBusiness.HEALTH,
        product_code="GROUP",
        name="Group Health Benefits",
        coverage_sections=[
            make_coverage_section(
                id="drug_coverage",
                name="Prescription Drug Coverage",
                code="Section A",
                triggers=[
                    LossTypeTrigger(loss_type="prescription_drug"),
                ],
            ),
            make_coverage_section(
                id="paramedical",
                name="Paramedical Services",
                code="Section B",
                triggers=[
                    LossTypeTrigger(loss_type="paramedical"),
                ],
            ),
        ],
        exclusions=[
            make_exclusion(
                id="ex_non_formulary",
                name="Non-Formulary Drug",
                code="E-1",
                policy_wording="We do not cover drugs not on the approved formulary without prior authorization.",
                policy_section_ref="Section E.1",
                applies_to_coverages=["drug_coverage"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.AND,
                        children=[
                            make_condition(
                                op=ConditionOperator.EQ,
                                field="drug.on_formulary",
                                value=False,
                            ),
                            make_condition(
                                op=ConditionOperator.EQ,
                                field="drug.prior_auth_approved",
                                value=False,
                            ),
                        ],
                    ),
                ],
            ),
            make_exclusion(
                id="ex_preexisting",
                name="Pre-existing Condition",
                code="E-2",
                policy_wording="We do not cover treatment for conditions diagnosed or treated within 12 months prior to coverage effective date.",
                policy_section_ref="Section E.2",
                applies_to_coverages=["drug_coverage", "paramedical"],
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
                                op=ConditionOperator.LT,
                                field="member.coverage_months",
                                value=12,
                            ),
                        ],
                    ),
                ],
            ),
            make_exclusion(
                id="ex_work_related",
                name="Work-Related Injury",
                code="E-3",
                policy_wording="We do not cover injuries arising from employment, which are covered by WSIB.",
                policy_section_ref="Section E.3",
                applies_to_coverages=["drug_coverage", "paramedical"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.EQ,
                        field="claim.work_related",
                        value=True,
                    ),
                ],
            ),
        ],
    )
