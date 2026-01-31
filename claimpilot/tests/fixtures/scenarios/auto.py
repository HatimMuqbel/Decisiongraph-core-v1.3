"""
Auto insurance (OAP 1) claim scenarios.

Each scenario function returns a Scenario object with:
- id: Stable identifier
- description: Human-readable summary
- build_context: Function to create the claim context
- expected: Expected outcome with must/must-not assertions
"""
from tests.helpers.contract import Scenario, expected_pay, expected_deny
from tests.helpers.facts import facts
from tests.helpers.runner import make_context


def auto_collision_clean():
    """Standard collision, all facts clean, no exclusions."""
    def build():
        return make_context(
            line="auto",
            loss_type="collision",
            facts=facts({
                "policy.status": "active",
                "vehicle.use_at_loss": "personal",
                "driver.rideshare_app_active": False,
                "driver.bac_level": 0.0,
                "driver.impairment_indicated": False,
                "driver.license_status": "valid",
                "loss.racing_activity": False,
                "loss.intentional_indicators": False,
            }),
        )

    return Scenario(
        id="auto.collision.clean",
        line="auto",
        description="Standard collision with no exclusions → PAY",
        build_context=build,
        expected=expected_pay(
            must_trigger_coverages={"section_c_collision"},
            must_not_apply_exclusions={
                "ex_commercial_use",
                "ex_impaired",
                "ex_unlicensed",
                "ex_racing",
                "ex_intentional",
            },
            certainty="high",
        ),
    )


def auto_rideshare_active():
    """Driver using rideshare app at time of loss."""
    def build():
        return make_context(
            line="auto",
            loss_type="collision",
            facts=facts({
                "policy.status": "active",
                "vehicle.use_at_loss": "delivery",
                "driver.rideshare_app_active": True,  # KEY
                "driver.bac_level": 0.0,
                "driver.impairment_indicated": False,
                "driver.license_status": "valid",
                "loss.racing_activity": False,
                "loss.intentional_indicators": False,
            }),
        )

    return Scenario(
        id="auto.rideshare.active",
        line="auto",
        description="Rideshare app active at time of collision → DENY",
        build_context=build,
        expected=expected_deny(
            by_exclusion="ex_commercial_use",
            must_not_apply_exclusions={"ex_impaired", "ex_racing"},
        ),
    )


def auto_impaired():
    """Driver was impaired (BAC > 0.08)."""
    def build():
        return make_context(
            line="auto",
            loss_type="collision",
            facts=facts({
                "policy.status": "active",
                "vehicle.use_at_loss": "personal",
                "driver.rideshare_app_active": False,
                "driver.bac_level": 0.12,  # KEY: Over 0.08
                "driver.impairment_indicated": True,
                "driver.license_status": "valid",
                "loss.racing_activity": False,
                "loss.intentional_indicators": False,
            }),
        )

    return Scenario(
        id="auto.impaired",
        line="auto",
        description="Driver impaired (BAC 0.12) → DENY",
        build_context=build,
        expected=expected_deny(
            by_exclusion="ex_impaired",
            must_not_apply_exclusions={"ex_commercial_use", "ex_racing"},
        ),
    )


def auto_unlicensed():
    """Driver's license was suspended."""
    def build():
        return make_context(
            line="auto",
            loss_type="collision",
            facts=facts({
                "policy.status": "active",
                "vehicle.use_at_loss": "personal",
                "driver.rideshare_app_active": False,
                "driver.bac_level": 0.0,
                "driver.impairment_indicated": False,
                "driver.license_status": "suspended",  # KEY
                "loss.racing_activity": False,
                "loss.intentional_indicators": False,
            }),
        )

    return Scenario(
        id="auto.unlicensed",
        line="auto",
        description="Driver license suspended → DENY",
        build_context=build,
        expected=expected_deny(
            by_exclusion="ex_unlicensed",
            must_not_apply_exclusions={"ex_impaired", "ex_commercial_use"},
        ),
    )


def auto_racing():
    """Vehicle used in racing activity."""
    def build():
        return make_context(
            line="auto",
            loss_type="collision",
            facts=facts({
                "policy.status": "active",
                "vehicle.use_at_loss": "personal",
                "driver.rideshare_app_active": False,
                "driver.bac_level": 0.0,
                "driver.impairment_indicated": False,
                "driver.license_status": "valid",
                "loss.racing_activity": True,  # KEY
                "loss.intentional_indicators": False,
            }),
        )

    return Scenario(
        id="auto.racing",
        line="auto",
        description="Vehicle in racing activity → DENY",
        build_context=build,
        expected=expected_deny(
            by_exclusion="ex_racing",
            must_not_apply_exclusions={"ex_impaired", "ex_commercial_use"},
        ),
    )


def auto_intentional():
    """Intentional damage indicators present."""
    def build():
        return make_context(
            line="auto",
            loss_type="collision",
            facts=facts({
                "policy.status": "active",
                "vehicle.use_at_loss": "personal",
                "driver.rideshare_app_active": False,
                "driver.bac_level": 0.0,
                "driver.impairment_indicated": False,
                "driver.license_status": "valid",
                "loss.racing_activity": False,
                "loss.intentional_indicators": True,  # KEY
            }),
        )

    return Scenario(
        id="auto.intentional",
        line="auto",
        description="Intentional damage indicators → DENY",
        build_context=build,
        expected=expected_deny(
            by_exclusion="ex_intentional",
            must_not_apply_exclusions={"ex_commercial_use", "ex_racing"},
        ),
    )


def auto_theft_clean():
    """Vehicle theft - comprehensive coverage, no exclusions."""
    def build():
        return make_context(
            line="auto",
            loss_type="theft",
            facts=facts({
                "policy.status": "active",
                "vehicle.use_at_loss": "personal",
                "driver.rideshare_app_active": False,
                "driver.bac_level": 0.0,
                "driver.impairment_indicated": False,
                "driver.license_status": "valid",
                "loss.racing_activity": False,
                "loss.intentional_indicators": False,
            }),
        )

    return Scenario(
        id="auto.theft.clean",
        line="auto",
        description="Vehicle theft, no exclusions → PAY",
        build_context=build,
        expected=expected_pay(
            must_trigger_coverages={"section_c_comprehensive"},
            must_not_apply_exclusions={"ex_intentional"},
        ),
    )


def all_auto_scenarios():
    """Return all auto scenarios."""
    return [
        auto_collision_clean(),
        auto_rideshare_active(),
        auto_impaired(),
        auto_unlicensed(),
        auto_racing(),
        auto_intentional(),
        auto_theft_clean(),
    ]
