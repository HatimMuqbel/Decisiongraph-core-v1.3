"""Group health claim scenarios."""
from tests.helpers.contract import Scenario, expected_pay, expected_deny
from tests.helpers.facts import facts
from tests.helpers.runner import make_context


def health_formulary_clean():
    def build():
        return make_context(
            line="health",
            loss_type="prescription_drug",
            facts=facts({
                "drug.on_formulary": True,
                "drug.prior_auth_approved": False,
                "condition.preexisting": False,
                "member.coverage_months": 24,
                "claim.work_related": False,
            }),
        )
    return Scenario(
        id="health.formulary.clean",
        line="health",
        description="Formulary drug → PAY",
        build_context=build,
        expected=expected_pay(
            must_trigger_coverages={"drug_coverage"},
            must_not_apply_exclusions={"ex_non_formulary", "ex_preexisting"},
        ),
    )


def health_non_formulary():
    def build():
        return make_context(
            line="health",
            loss_type="prescription_drug",
            facts=facts({
                "drug.on_formulary": False,
                "drug.prior_auth_approved": False,
                "condition.preexisting": False,
                "member.coverage_months": 24,
                "claim.work_related": False,
            }),
        )
    return Scenario(
        id="health.non_formulary",
        line="health",
        description="Non-formulary without prior auth → DENY",
        build_context=build,
        expected=expected_deny(by_exclusion="ex_non_formulary"),
    )


def health_preexisting():
    def build():
        return make_context(
            line="health",
            loss_type="prescription_drug",
            facts=facts({
                "drug.on_formulary": True,
                "drug.prior_auth_approved": False,
                "condition.preexisting": True,
                "member.coverage_months": 3,
                "claim.work_related": False,
            }),
        )
    return Scenario(
        id="health.preexisting",
        line="health",
        description="Pre-existing within 12 months → DENY",
        build_context=build,
        expected=expected_deny(by_exclusion="ex_preexisting"),
    )


def health_work_related():
    def build():
        return make_context(
            line="health",
            loss_type="prescription_drug",
            facts=facts({
                "drug.on_formulary": True,
                "drug.prior_auth_approved": False,
                "condition.preexisting": False,
                "member.coverage_months": 24,
                "claim.work_related": True,
            }),
        )
    return Scenario(
        id="health.work_related",
        line="health",
        description="Work-related injury → DENY",
        build_context=build,
        expected=expected_deny(by_exclusion="ex_work_related"),
    )


def all_health_scenarios():
    return [
        health_formulary_clean(),
        health_non_formulary(),
        health_preexisting(),
        health_work_related(),
    ]
