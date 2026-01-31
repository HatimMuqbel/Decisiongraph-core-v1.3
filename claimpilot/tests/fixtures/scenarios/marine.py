"""Marine pleasure craft claim scenarios."""
from tests.helpers.contract import Scenario, expected_pay, expected_deny
from tests.helpers.facts import facts
from tests.helpers.runner import make_context


def marine_storm_clean():
    def build():
        return make_context(
            line="marine",
            loss_type="storm_damage",
            facts=facts({
                "vessel.within_navigation_limits": True,
                "operator.pcoc_valid": True,
                "vessel.in_water": True,
                "damage.cause": "storm",
            }),
        )
    return Scenario(
        id="marine.storm.clean",
        line="marine",
        description="Storm damage within limits → PAY",
        build_context=build,
        expected=expected_pay(
            must_trigger_coverages={"hull_machinery"},
            must_not_apply_exclusions={"ex_navigation_limits", "ex_operator_unqualified"},
        ),
    )


def marine_navigation_limits():
    def build():
        return make_context(
            line="marine",
            loss_type="storm_damage",
            facts=facts({
                "vessel.within_navigation_limits": False,
                "operator.pcoc_valid": True,
                "vessel.in_water": False,
                "damage.cause": "storm",
            }),
        )
    return Scenario(
        id="marine.navigation_limits",
        line="marine",
        description="Outside navigation limits → DENY",
        build_context=build,
        expected=expected_deny(
            by_exclusion="ex_navigation_limits",
            must_not_apply_exclusions={"ex_operator_unqualified"},
        ),
    )


def marine_no_pcoc():
    def build():
        return make_context(
            line="marine",
            loss_type="collision",
            facts=facts({
                "vessel.within_navigation_limits": True,
                "operator.pcoc_valid": False,
                "vessel.in_water": False,
                "damage.cause": "collision",
            }),
        )
    return Scenario(
        id="marine.no_pcoc",
        line="marine",
        description="Operator without PCOC → DENY",
        build_context=build,
        expected=expected_deny(
            by_exclusion="ex_operator_unqualified",
            must_not_apply_exclusions={"ex_navigation_limits"},
        ),
    )


def marine_ice_damage():
    def build():
        return make_context(
            line="marine",
            loss_type="storm_damage",
            facts=facts({
                "vessel.within_navigation_limits": True,
                "operator.pcoc_valid": True,
                "vessel.in_water": True,
                "damage.cause": "ice",
            }),
        )
    return Scenario(
        id="marine.ice_damage",
        line="marine",
        description="Ice damage while in water → DENY",
        build_context=build,
        expected=expected_deny(by_exclusion="ex_ice_damage"),
    )


def all_marine_scenarios():
    return [
        marine_storm_clean(),
        marine_navigation_limits(),
        marine_no_pcoc(),
        marine_ice_damage(),
    ]
