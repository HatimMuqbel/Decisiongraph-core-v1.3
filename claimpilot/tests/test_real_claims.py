"""
Real Claim Scenario Tests

End-to-end tests that simulate realistic claims across all policy lines.
Each scenario tests the full evaluation pipeline:

1. Create claim with realistic facts
2. Resolve context (which rules apply)
3. Evaluate exclusions
4. Check evidence gates
5. Route authority if needed
6. Generate recommendation with full provenance
7. Verify recommendation is correct and defensible

Success Criteria:
- Correct disposition (PAY/DENY/ESCALATE/etc.)
- Correct exclusions triggered
- Correct authority routing
- Provenance present (policy_pack_hash, authorities_cited)
- Reasoning chain documented
- Evidence gates enforced

Test Scenarios:
- Auto (OAP1): collision clean, rideshare, impaired, unlicensed, racing, theft
- Property (HO-3): fire clean, flood excluded, vacant, business use
- Marine: storm clean, racing excluded, negligent navigation
- Health: formulary clean, non-formulary, preexisting, work-related
- Workers Comp (WSIB): work injury clean, not work-related, preexisting, intoxication
- CGL: slip-fall clean, intentional, pollution, auto
- E&O: negligence clean, prior acts, fraud
- Travel: emergency clean, preexisting, elective, high-risk activity
"""
import pytest

# Import fixtures to trigger policy registration
import tests.fixtures  # noqa: F401

from tests.fixtures.scenarios import all_scenarios
from tests.helpers.runner import run_scenario
from tests.helpers.assertions import assert_contract


@pytest.mark.parametrize("scenario", all_scenarios(), ids=lambda s: s.id)
def test_real_claim_scenario(scenario):
    """
    Execute a real claim scenario and verify the contract.

    Each scenario specifies:
    - Facts representing a realistic claim situation
    - Expected disposition (PAY/DENY/etc.)
    - Exclusions that must/must-not apply
    - Coverages that must trigger
    - Minimum reasoning depth
    - Provenance requirements
    """
    _policy, _ctx, rec = run_scenario(scenario)
    assert_contract(rec, scenario.expected)
