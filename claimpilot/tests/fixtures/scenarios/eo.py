"""Professional E&O (Errors & Omissions) claim scenarios."""
from tests.helpers.contract import Scenario, expected_pay, expected_deny
from tests.helpers.facts import facts
from tests.helpers.runner import make_context


def eo_negligence_clean():
    def build():
        return make_context(
            line="eo",
            loss_type="professional_negligence",
            facts=facts({
                "claim.first_made_during_policy": True,
                "wrongful_act.before_retro_date": False,
                "act.fraudulent": False,
            }),
        )
    return Scenario(
        id="eo.negligence.clean",
        line="eo",
        description="Professional negligence within coverage → PAY",
        build_context=build,
        expected=expected_pay(
            must_trigger_coverages={"professional_services"},
            must_not_apply_exclusions={"ex_prior_acts", "ex_intentional"},
        ),
    )


def eo_prior_acts():
    def build():
        return make_context(
            line="eo",
            loss_type="professional_negligence",
            facts=facts({
                "claim.first_made_during_policy": True,
                "wrongful_act.before_retro_date": True,
                "act.fraudulent": False,
            }),
        )
    return Scenario(
        id="eo.prior_acts",
        line="eo",
        description="Act before retroactive date → DENY",
        build_context=build,
        expected=expected_deny(by_exclusion="ex_prior_acts"),
    )


def eo_fraud():
    def build():
        return make_context(
            line="eo",
            loss_type="professional_negligence",
            facts=facts({
                "claim.first_made_during_policy": True,
                "wrongful_act.before_retro_date": False,
                "act.fraudulent": True,
            }),
        )
    return Scenario(
        id="eo.fraud",
        line="eo",
        description="Fraudulent act → DENY",
        build_context=build,
        expected=expected_deny(by_exclusion="ex_intentional"),
    )


def all_eo_scenarios():
    return [
        eo_negligence_clean(),
        eo_prior_acts(),
        eo_fraud(),
    ]
