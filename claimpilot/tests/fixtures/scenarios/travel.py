"""Travel medical insurance claim scenarios."""
from tests.helpers.contract import Scenario, expected_pay, expected_deny
from tests.helpers.facts import facts
from tests.helpers.runner import make_context


def travel_emergency_clean():
    def build():
        return make_context(
            line="travel",
            loss_type="emergency_medical",
            facts=facts({
                "insured.outside_home_province": True,
                "treatment.emergency": True,
                "condition.preexisting": False,
                "condition.stable": True,
                "activity.high_risk": False,
            }),
        )
    return Scenario(
        id="travel.emergency.clean",
        line="travel",
        description="Emergency medical abroad → PAY",
        build_context=build,
        expected=expected_pay(
            must_trigger_coverages={"emergency_medical"},
            must_not_apply_exclusions={"ex_preexisting", "ex_not_emergency", "ex_high_risk"},
        ),
    )


def travel_preexisting_unstable():
    def build():
        return make_context(
            line="travel",
            loss_type="emergency_medical",
            facts=facts({
                "insured.outside_home_province": True,
                "treatment.emergency": True,
                "condition.preexisting": True,
                "condition.stable": False,
                "activity.high_risk": False,
            }),
        )
    return Scenario(
        id="travel.preexisting.unstable",
        line="travel",
        description="Pre-existing not stable → DENY",
        build_context=build,
        expected=expected_deny(by_exclusion="ex_preexisting"),
    )


def travel_elective():
    def build():
        return make_context(
            line="travel",
            loss_type="emergency_medical",
            facts=facts({
                "insured.outside_home_province": True,
                "treatment.emergency": False,
                "condition.preexisting": False,
                "condition.stable": True,
                "activity.high_risk": False,
            }),
        )
    return Scenario(
        id="travel.elective",
        line="travel",
        description="Non-emergency elective → DENY",
        build_context=build,
        expected=expected_deny(by_exclusion="ex_not_emergency"),
    )


def travel_high_risk():
    def build():
        return make_context(
            line="travel",
            loss_type="emergency_medical",
            facts=facts({
                "insured.outside_home_province": True,
                "treatment.emergency": True,
                "condition.preexisting": False,
                "condition.stable": True,
                "activity.high_risk": True,
            }),
        )
    return Scenario(
        id="travel.high_risk",
        line="travel",
        description="High-risk activity → DENY",
        build_context=build,
        expected=expected_deny(by_exclusion="ex_high_risk"),
    )


def all_travel_scenarios():
    return [
        travel_emergency_clean(),
        travel_preexisting_unstable(),
        travel_elective(),
        travel_high_risk(),
    ]
