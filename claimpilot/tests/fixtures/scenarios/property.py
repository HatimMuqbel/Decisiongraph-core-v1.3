"""Property (HO-3) claim scenarios."""
from tests.helpers.contract import Scenario, expected_pay, expected_deny
from tests.helpers.facts import facts
from tests.helpers.runner import make_context


def property_fire_clean():
    def build():
        return make_context(
            line="property",
            loss_type="fire",
            facts=facts({
                "loss.cause": "cooking_accident",
                "damage.gradual": False,
                "dwelling.days_vacant": 0,
            }),
        )
    return Scenario(
        id="property.fire.clean",
        line="property",
        description="Kitchen fire, no exclusions → PAY",
        build_context=build,
        expected=expected_pay(
            must_trigger_coverages={"coverage_a"},
            must_not_apply_exclusions={"ex_flood", "ex_earthquake"},
        ),
    )


def property_flood():
    def build():
        return make_context(
            line="property",
            loss_type="fire",
            facts=facts({
                "loss.cause": "flood",
                "damage.gradual": False,
                "dwelling.days_vacant": 0,
            }),
        )
    return Scenario(
        id="property.flood",
        line="property",
        description="Flood damage → DENY",
        build_context=build,
        expected=expected_deny(
            by_exclusion="ex_flood",
            must_not_apply_exclusions={"ex_earthquake"},
        ),
    )


def property_pipe_burst():
    def build():
        return make_context(
            line="property",
            loss_type="water_damage_sudden",
            facts=facts({
                "loss.cause": "pipe_burst",
                "damage.gradual": False,
                "dwelling.days_vacant": 0,
            }),
        )
    return Scenario(
        id="property.pipe_burst",
        line="property",
        description="Sudden pipe burst → PAY",
        build_context=build,
        expected=expected_pay(must_not_apply_exclusions={"ex_wear_tear"}),
    )


def property_gradual_leak():
    def build():
        return make_context(
            line="property",
            loss_type="water_damage_sudden",
            facts=facts({
                "loss.cause": "gradual_leak",
                "damage.gradual": True,
                "dwelling.days_vacant": 0,
            }),
        )
    return Scenario(
        id="property.gradual_leak",
        line="property",
        description="Gradual leak damage → DENY",
        build_context=build,
        expected=expected_deny(by_exclusion="ex_wear_tear"),
    )


def property_vacancy():
    def build():
        return make_context(
            line="property",
            loss_type="theft",
            facts=facts({
                "loss.cause": "theft",
                "damage.gradual": False,
                "dwelling.days_vacant": 45,
            }),
        )
    return Scenario(
        id="property.vacancy",
        line="property",
        description="Property vacant > 30 days → DENY",
        build_context=build,
        expected=expected_deny(by_exclusion="ex_vacancy"),
    )


def property_earthquake():
    def build():
        return make_context(
            line="property",
            loss_type="fire",
            facts=facts({
                "loss.cause": "earthquake",
                "damage.gradual": False,
                "dwelling.days_vacant": 0,
            }),
        )
    return Scenario(
        id="property.earthquake",
        line="property",
        description="Earthquake damage → DENY",
        build_context=build,
        expected=expected_deny(by_exclusion="ex_earthquake"),
    )


def all_property_scenarios():
    return [
        property_fire_clean(),
        property_flood(),
        property_pipe_burst(),
        property_gradual_leak(),
        property_vacancy(),
        property_earthquake(),
    ]
