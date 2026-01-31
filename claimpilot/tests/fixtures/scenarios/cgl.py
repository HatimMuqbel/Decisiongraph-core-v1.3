"""Commercial General Liability (CGL) claim scenarios."""
from tests.helpers.contract import Scenario, expected_pay, expected_deny
from tests.helpers.facts import facts
from tests.helpers.runner import make_context


def cgl_slip_fall_clean():
    def build():
        return make_context(
            line="cgl",
            loss_type="bodily_injury_tp",
            facts=facts({
                "injury.expected_intended": False,
                "loss.pollution_related": False,
                "loss.auto_involved": False,
            }),
        )
    return Scenario(
        id="cgl.slip_fall.clean",
        line="cgl",
        description="Slip and fall on premises → PAY",
        build_context=build,
        expected=expected_pay(
            must_trigger_coverages={"coverage_a"},
            must_not_apply_exclusions={"ex_expected_intended", "ex_pollution", "ex_auto"},
        ),
    )


def cgl_intentional():
    def build():
        return make_context(
            line="cgl",
            loss_type="bodily_injury_tp",
            facts=facts({
                "injury.expected_intended": True,
                "loss.pollution_related": False,
                "loss.auto_involved": False,
            }),
        )
    return Scenario(
        id="cgl.intentional",
        line="cgl",
        description="Intentional injury → DENY",
        build_context=build,
        expected=expected_deny(
            by_exclusion="ex_expected_intended",
            must_not_apply_exclusions={"ex_pollution", "ex_auto"},
        ),
    )


def cgl_pollution():
    def build():
        return make_context(
            line="cgl",
            loss_type="bodily_injury_tp",
            facts=facts({
                "injury.expected_intended": False,
                "loss.pollution_related": True,
                "loss.auto_involved": False,
            }),
        )
    return Scenario(
        id="cgl.pollution",
        line="cgl",
        description="Pollution-related injury → DENY",
        build_context=build,
        expected=expected_deny(by_exclusion="ex_pollution"),
    )


def cgl_auto():
    def build():
        return make_context(
            line="cgl",
            loss_type="bodily_injury_tp",
            facts=facts({
                "injury.expected_intended": False,
                "loss.pollution_related": False,
                "loss.auto_involved": True,
            }),
        )
    return Scenario(
        id="cgl.auto",
        line="cgl",
        description="Auto-related injury → DENY",
        build_context=build,
        expected=expected_deny(by_exclusion="ex_auto"),
    )


def all_cgl_scenarios():
    return [
        cgl_slip_fall_clean(),
        cgl_intentional(),
        cgl_pollution(),
        cgl_auto(),
    ]
