"""Ontario WSIB workers compensation scenarios."""
from tests.helpers.contract import Scenario, Expected, expected_pay, expected_deny, expected_deny_no_coverage
from tests.helpers.facts import facts
from tests.helpers.runner import make_context


def wsib_work_injury_clean():
    def build():
        return make_context(
            line="workers_comp",
            loss_type="work_injury",
            facts=facts({
                "injury.work_related": True,
                "employer.wsib_registered": True,
                "condition.preexisting": False,
                "condition.aggravated_by_work": False,
                "injury.intoxication_sole_cause": False,
            }),
        )
    return Scenario(
        id="wsib.work_injury.clean",
        line="workers_comp",
        description="Clear work injury → PAY",
        build_context=build,
        expected=expected_pay(
            must_trigger_coverages={"loss_of_earnings"},
            must_not_apply_exclusions={"ex_preexisting", "ex_intoxication"},
        ),
    )


def wsib_not_work_related():
    """Not work-related fails coverage precondition (DENY due to no coverage)."""
    def build():
        return make_context(
            line="workers_comp",
            loss_type="work_injury",
            facts=facts({
                "injury.work_related": False,
                "employer.wsib_registered": True,
                "condition.preexisting": False,
                "condition.aggravated_by_work": False,
                "injury.intoxication_sole_cause": False,
            }),
        )
    return Scenario(
        id="wsib.not_work_related",
        line="workers_comp",
        description="Not work-related (no coverage) → DENY",
        build_context=build,
        expected=expected_deny_no_coverage(),
    )


def wsib_preexisting_not_aggravated():
    def build():
        return make_context(
            line="workers_comp",
            loss_type="work_injury",
            facts=facts({
                "injury.work_related": True,
                "employer.wsib_registered": True,
                "condition.preexisting": True,
                "condition.aggravated_by_work": False,
                "injury.intoxication_sole_cause": False,
            }),
        )
    return Scenario(
        id="wsib.preexisting.not_aggravated",
        line="workers_comp",
        description="Pre-existing not aggravated → DENY",
        build_context=build,
        expected=expected_deny(by_exclusion="ex_preexisting"),
    )


def wsib_intoxication():
    def build():
        return make_context(
            line="workers_comp",
            loss_type="work_injury",
            facts=facts({
                "injury.work_related": True,
                "employer.wsib_registered": True,
                "condition.preexisting": False,
                "condition.aggravated_by_work": False,
                "injury.intoxication_sole_cause": True,
            }),
        )
    return Scenario(
        id="wsib.intoxication",
        line="workers_comp",
        description="Intoxication sole cause → DENY",
        build_context=build,
        expected=expected_deny(by_exclusion="ex_intoxication"),
    )


def all_wsib_scenarios():
    return [
        wsib_work_injury_clean(),
        wsib_not_work_related(),
        wsib_preexisting_not_aggravated(),
        wsib_intoxication(),
    ]
