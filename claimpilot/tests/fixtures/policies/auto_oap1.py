"""
Ontario Auto Policy (OAP 1) for testing.

Based on actual OAP 1 structure with common exclusions:
- Commercial use (rideshare/delivery)
- Impaired operation
- Unlicensed driver
- Racing
- Intentional loss
"""
from functools import lru_cache

from claimpilot.models import (
    ClaimantType,
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
def policy_auto_oap1():
    """
    Create Ontario Auto Policy with real exclusions.

    Cached for performance - only built once per test session.
    """
    return make_policy(
        id="CA-ON-OAP1-2024",
        jurisdiction="CA-ON",
        line_of_business=LineOfBusiness.AUTO,
        product_code="OAP1",
        name="Ontario Automobile Policy",
        coverage_sections=[
            # Section C - Collision
            make_coverage_section(
                id="section_c_collision",
                name="Collision Coverage",
                code="Section C",
                triggers=[
                    LossTypeTrigger(
                        loss_type="collision",
                        claimant_types=[ClaimantType.INSURED, ClaimantType.NAMED_INSURED],
                    ),
                ],
                preconditions=[
                    make_condition(
                        op=ConditionOperator.EQ,
                        field="policy.status",
                        value="active",
                    ),
                ],
            ),
            # Section C - Comprehensive
            make_coverage_section(
                id="section_c_comprehensive",
                name="Comprehensive Coverage",
                code="Section C",
                triggers=[
                    LossTypeTrigger(loss_type="theft"),
                    LossTypeTrigger(loss_type="vandalism"),
                    LossTypeTrigger(loss_type="fire"),
                ],
            ),
        ],
        exclusions=[
            # Commercial Use (4.2.1)
            make_exclusion(
                id="ex_commercial_use",
                name="Commercial Use",
                code="4.2.1",
                policy_wording="We do not cover loss or damage that occurs while the automobile is used as a taxicab, bus, livery vehicle, or to carry passengers for compensation.",
                policy_section_ref="Section 4.2.1",
                applies_to_coverages=["section_c_collision", "section_c_comprehensive"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.OR,
                        children=[
                            make_condition(
                                op=ConditionOperator.IN,
                                field="vehicle.use_at_loss",
                                value=["rideshare", "delivery", "taxi", "livery"],
                            ),
                            make_condition(
                                op=ConditionOperator.EQ,
                                field="driver.rideshare_app_active",
                                value=True,
                            ),
                        ],
                    ),
                ],
            ),
            # Impaired Operation (4.3.3)
            make_exclusion(
                id="ex_impaired",
                name="Impaired Operation",
                code="4.3.3",
                policy_wording="We do not cover loss or damage that occurs while the automobile is operated by any person while under the influence of intoxicating liquor or drugs.",
                policy_section_ref="Section 4.3.3",
                applies_to_coverages=["section_c_collision", "section_c_comprehensive"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.OR,
                        children=[
                            make_condition(
                                op=ConditionOperator.GT,
                                field="driver.bac_level",
                                value=0.08,
                            ),
                            make_condition(
                                op=ConditionOperator.EQ,
                                field="driver.impairment_indicated",
                                value=True,
                            ),
                        ],
                    ),
                ],
            ),
            # Unlicensed Driver (4.1.2)
            make_exclusion(
                id="ex_unlicensed",
                name="Unlicensed Driver",
                code="4.1.2",
                policy_wording="We do not cover loss or damage that occurs while the automobile is operated by any person who is not authorized by law to drive.",
                policy_section_ref="Section 4.1.2",
                applies_to_coverages=["section_c_collision", "section_c_comprehensive"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.IN,
                        field="driver.license_status",
                        value=["suspended", "revoked", "expired", "none"],
                    ),
                ],
            ),
            # Racing (4.5.1)
            make_exclusion(
                id="ex_racing",
                name="Racing",
                code="4.5.1",
                policy_wording="We do not cover loss or damage that occurs while the automobile is used in any race, speed test, or other contest.",
                policy_section_ref="Section 4.5.1",
                applies_to_coverages=["section_c_collision", "section_c_comprehensive"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.EQ,
                        field="loss.racing_activity",
                        value=True,
                    ),
                ],
            ),
            # Intentional Loss (4.6.1)
            make_exclusion(
                id="ex_intentional",
                name="Intentional Loss",
                code="4.6.1",
                policy_wording="We do not cover loss or damage caused by an intentional act of the insured.",
                policy_section_ref="Section 4.6.1",
                applies_to_coverages=["section_c_collision", "section_c_comprehensive"],
                trigger_conditions=[
                    make_condition(
                        op=ConditionOperator.EQ,
                        field="loss.intentional_indicators",
                        value=True,
                    ),
                ],
            ),
        ],
    )
