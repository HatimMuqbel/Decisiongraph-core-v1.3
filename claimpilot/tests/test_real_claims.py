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
"""
import pytest
from datetime import date
from decimal import Decimal

from claimpilot.models import (
    ClaimantType,
    ClaimContext,
    Condition,
    ConditionOperator,
    CoverageSection,
    DispositionType,
    DocumentRequirement,
    EvidenceItem,
    EvidenceRule,
    EvidenceStatus,
    Exclusion,
    Fact,
    FactCertainty,
    FactSource,
    GateStrictness,
    LineOfBusiness,
    LossTypeTrigger,
    Policy,
    Predicate,
    RecommendationCertainty,
)
from claimpilot.engine import (
    ContextResolver,
    EvidenceGate,
    RecommendationBuilder,
)

from tests.conftest import (
    make_claim_context,
    make_condition,
    make_coverage_section,
    make_document_requirement,
    make_evidence,
    make_evidence_rule,
    make_exclusion,
    make_fact,
    make_policy,
)


# =============================================================================
# Shared Helpers
# =============================================================================

def create_facts_dict(facts_map: dict) -> dict[str, Fact]:
    """Convert a simple key-value map to Fact objects."""
    return {
        field: make_fact(field, value)
        for field, value in facts_map.items()
    }


# =============================================================================
# AUTO SCENARIOS (Ontario OAP 1)
# =============================================================================

class TestAutoScenarios:
    """Ontario Auto (OAP 1) claim scenarios."""

    @pytest.fixture
    def auto_policy(self):
        """Create Ontario Auto policy with real exclusions."""
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

    # -------------------------------------------------------------------------
    # A1: Standard Collision - APPROVE
    # -------------------------------------------------------------------------
    def test_auto_standard_collision_approve(self, auto_policy):
        """
        Standard collision claim with no exclusions.
        Should recommend PAY with HIGH certainty.
        """
        facts = create_facts_dict({
            "policy.status": "active",
            "vehicle.use_at_loss": "personal",
            "driver.rideshare_app_active": False,
            "driver.bac_level": 0.0,
            "driver.impairment_indicated": False,
            "driver.license_status": "valid",
            "loss.racing_activity": False,
            "loss.intentional_indicators": False,
            "claim.reserve_amount": 8500.00,
        })

        context = make_claim_context(
            claim_id="AUTO-2024-001",
            policy_id="CA-ON-OAP1-2024",
            loss_type="collision",
            loss_date=date(2024, 6, 15),
            report_date=date(2024, 6, 15),
            claimant_type=ClaimantType.INSURED,
            facts=facts,
            evidence=[
                make_evidence("police_report", status=EvidenceStatus.VERIFIED),
                make_evidence("damage_estimate", status=EvidenceStatus.VERIFIED),
            ],
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(auto_policy, context)

        # Core assertions
        assert recommendation.recommended_disposition == DispositionType.PAY
        assert recommendation.certainty == RecommendationCertainty.HIGH
        assert len(recommendation.exclusions_triggered) == 0
        assert "section_c_collision" in recommendation.coverages_evaluated

        # Provenance assertions
        assert recommendation.policy_pack_hash != ""
        assert recommendation.policy_pack_id == "CA-ON-OAP1-2024"

    # -------------------------------------------------------------------------
    # A2: Rideshare Delivery - DENY (Commercial Use)
    # -------------------------------------------------------------------------
    def test_auto_rideshare_delivery_deny(self, auto_policy):
        """
        Driver was using Uber Eats at time of collision.
        Commercial use exclusion (4.2.1) applies.
        Should recommend DENY.
        """
        facts = create_facts_dict({
            "policy.status": "active",
            "vehicle.use_at_loss": "delivery",  # KEY: Commercial use
            "driver.rideshare_app_active": True,  # KEY: App was active
            "driver.bac_level": 0.0,
            "driver.impairment_indicated": False,
            "driver.license_status": "valid",
            "loss.racing_activity": False,
            "loss.intentional_indicators": False,
        })

        context = make_claim_context(
            claim_id="AUTO-2024-002",
            policy_id="CA-ON-OAP1-2024",
            loss_type="collision",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(auto_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_commercial_use" in recommendation.exclusions_triggered
        # Should cite the exclusion policy wording
        assert len(recommendation.authorities_cited) > 0

    # -------------------------------------------------------------------------
    # A3: Impaired Driver - DENY
    # -------------------------------------------------------------------------
    def test_auto_impaired_driver_deny(self, auto_policy):
        """
        Driver had BAC of 0.12.
        Impaired operation exclusion (4.3.3) applies.
        Should recommend DENY.
        """
        facts = create_facts_dict({
            "policy.status": "active",
            "vehicle.use_at_loss": "personal",
            "driver.rideshare_app_active": False,
            "driver.bac_level": 0.12,  # KEY: Over 0.08
            "driver.impairment_indicated": True,  # KEY: Impaired
            "driver.license_status": "valid",
            "loss.racing_activity": False,
            "loss.intentional_indicators": False,
        })

        context = make_claim_context(
            claim_id="AUTO-2024-003",
            loss_type="collision",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(auto_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_impaired" in recommendation.exclusions_triggered

    # -------------------------------------------------------------------------
    # A4: Unlicensed Driver - DENY
    # -------------------------------------------------------------------------
    def test_auto_unlicensed_driver_deny(self, auto_policy):
        """
        Driver's license was suspended.
        Unlicensed driver exclusion (4.1.2) applies.
        """
        facts = create_facts_dict({
            "policy.status": "active",
            "vehicle.use_at_loss": "personal",
            "driver.rideshare_app_active": False,
            "driver.bac_level": 0.0,
            "driver.impairment_indicated": False,
            "driver.license_status": "suspended",  # KEY: Suspended
            "loss.racing_activity": False,
            "loss.intentional_indicators": False,
        })

        context = make_claim_context(
            claim_id="AUTO-2024-004",
            loss_type="collision",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(auto_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_unlicensed" in recommendation.exclusions_triggered

    # -------------------------------------------------------------------------
    # A5: Racing - DENY
    # -------------------------------------------------------------------------
    def test_auto_racing_deny(self, auto_policy):
        """
        Vehicle was at a track day event.
        Racing exclusion (4.5.1) applies.
        """
        facts = create_facts_dict({
            "policy.status": "active",
            "vehicle.use_at_loss": "personal",
            "driver.rideshare_app_active": False,
            "driver.bac_level": 0.0,
            "driver.impairment_indicated": False,
            "driver.license_status": "valid",
            "loss.racing_activity": True,  # KEY: Racing
            "loss.intentional_indicators": False,
        })

        context = make_claim_context(
            claim_id="AUTO-2024-005",
            loss_type="collision",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(auto_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_racing" in recommendation.exclusions_triggered

    # -------------------------------------------------------------------------
    # A6: Intentional Loss - DENY
    # -------------------------------------------------------------------------
    def test_auto_intentional_loss_deny(self, auto_policy):
        """
        Indicators suggest intentional damage.
        Intentional loss exclusion (4.6.1) applies.
        """
        facts = create_facts_dict({
            "policy.status": "active",
            "vehicle.use_at_loss": "personal",
            "driver.rideshare_app_active": False,
            "driver.bac_level": 0.0,
            "driver.impairment_indicated": False,
            "driver.license_status": "valid",
            "loss.racing_activity": False,
            "loss.intentional_indicators": True,  # KEY: Intentional
        })

        context = make_claim_context(
            claim_id="AUTO-2024-006",
            loss_type="collision",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(auto_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_intentional" in recommendation.exclusions_triggered

    # -------------------------------------------------------------------------
    # A7: Theft Claim - APPROVE (Comprehensive)
    # -------------------------------------------------------------------------
    def test_auto_theft_approve(self, auto_policy):
        """
        Vehicle stolen - comprehensive coverage.
        No exclusions apply.
        """
        # Must provide all facts that exclusions check to avoid UNKNOWN
        facts = create_facts_dict({
            "policy.status": "active",
            "vehicle.use_at_loss": "personal",
            "driver.rideshare_app_active": False,
            "driver.bac_level": 0.0,
            "driver.impairment_indicated": False,
            "driver.license_status": "valid",
            "loss.racing_activity": False,
            "loss.intentional_indicators": False,
        })

        context = make_claim_context(
            claim_id="AUTO-2024-007",
            loss_type="theft",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(auto_policy, context)

        assert recommendation.recommended_disposition == DispositionType.PAY
        assert "section_c_comprehensive" in recommendation.coverages_evaluated


# =============================================================================
# PROPERTY SCENARIOS (Homeowners HO-3)
# =============================================================================

class TestPropertyScenarios:
    """Homeowners (HO-3) property claim scenarios."""

    @pytest.fixture
    def property_policy(self):
        """Create property policy with standard exclusions."""
        return make_policy(
            id="US-HO3-2024",
            jurisdiction="US-NY",
            line_of_business=LineOfBusiness.PROPERTY,
            product_code="HO3",
            name="Homeowners Policy",
            coverage_sections=[
                make_coverage_section(
                    id="coverage_a",
                    name="Dwelling Coverage",
                    code="Coverage A",
                    triggers=[
                        LossTypeTrigger(loss_type="fire"),
                        LossTypeTrigger(loss_type="water_damage_sudden"),
                        LossTypeTrigger(loss_type="wind"),
                        LossTypeTrigger(loss_type="hail"),
                    ],
                ),
                make_coverage_section(
                    id="coverage_c",
                    name="Personal Property",
                    code="Coverage C",
                    triggers=[
                        LossTypeTrigger(loss_type="theft"),
                    ],
                ),
            ],
            exclusions=[
                # Flood
                make_exclusion(
                    id="ex_flood",
                    name="Flood",
                    code="E-1",
                    policy_wording="We do not cover loss caused by flood, surface water, waves, tidal water, overflow of a body of water.",
                    policy_section_ref="Section E.1",
                    applies_to_coverages=["coverage_a"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="loss.cause",
                            value="flood",
                        ),
                    ],
                ),
                # Wear and Tear / Gradual
                make_exclusion(
                    id="ex_wear_tear",
                    name="Wear and Tear",
                    code="E-2",
                    policy_wording="We do not cover loss caused by wear and tear, marring, deterioration, or gradual damage.",
                    policy_section_ref="Section E.2",
                    applies_to_coverages=["coverage_a"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="damage.gradual",
                            value=True,
                        ),
                    ],
                ),
                # Vacancy
                make_exclusion(
                    id="ex_vacancy",
                    name="Vacancy",
                    code="E-3",
                    policy_wording="We do not cover loss if the dwelling has been vacant for more than 30 consecutive days.",
                    policy_section_ref="Section E.3",
                    applies_to_coverages=["coverage_a", "coverage_c"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.GT,
                            field="dwelling.days_vacant",
                            value=30,
                        ),
                    ],
                ),
                # Earthquake
                make_exclusion(
                    id="ex_earthquake",
                    name="Earthquake",
                    code="E-4",
                    policy_wording="We do not cover loss caused by earthquake.",
                    policy_section_ref="Section E.4",
                    applies_to_coverages=["coverage_a"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="loss.cause",
                            value="earthquake",
                        ),
                    ],
                ),
            ],
        )

    # -------------------------------------------------------------------------
    # P1: Fire Damage - APPROVE
    # -------------------------------------------------------------------------
    def test_property_fire_approve(self, property_policy):
        """
        Kitchen fire caused by cooking accident.
        Clear covered peril under Coverage A.
        """
        facts = create_facts_dict({
            "loss.cause": "cooking_accident",
            "damage.gradual": False,
            "dwelling.days_vacant": 0,
        })

        context = make_claim_context(
            claim_id="PROP-2024-001",
            policy_id="US-HO3-2024",
            jurisdiction="US-NY",
            line_of_business=LineOfBusiness.PROPERTY,
            loss_type="fire",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(property_policy, context)

        assert recommendation.recommended_disposition == DispositionType.PAY
        assert "coverage_a" in recommendation.coverages_evaluated
        assert len(recommendation.exclusions_triggered) == 0

    # -------------------------------------------------------------------------
    # P2: Flood Damage - DENY
    # -------------------------------------------------------------------------
    def test_property_flood_deny(self, property_policy):
        """
        Basement flooded during heavy rain.
        Flood exclusion applies.
        """
        facts = create_facts_dict({
            "loss.cause": "flood",  # KEY: Flood cause
            "damage.gradual": False,
            "dwelling.days_vacant": 0,
        })

        context = make_claim_context(
            claim_id="PROP-2024-002",
            jurisdiction="US-NY",
            line_of_business=LineOfBusiness.PROPERTY,
            loss_type="fire",  # Will be checked but flood exclusion catches cause
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(property_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_flood" in recommendation.exclusions_triggered

    # -------------------------------------------------------------------------
    # P3: Sudden Pipe Burst - APPROVE
    # -------------------------------------------------------------------------
    def test_property_sudden_pipe_burst_approve(self, property_policy):
        """
        Sudden pipe burst is covered (sudden and accidental).
        """
        facts = create_facts_dict({
            "loss.cause": "pipe_burst",
            "damage.gradual": False,  # KEY: Not gradual
            "dwelling.days_vacant": 0,
        })

        context = make_claim_context(
            claim_id="PROP-2024-003",
            jurisdiction="US-NY",
            line_of_business=LineOfBusiness.PROPERTY,
            loss_type="water_damage_sudden",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(property_policy, context)

        assert recommendation.recommended_disposition == DispositionType.PAY

    # -------------------------------------------------------------------------
    # P4: Gradual Leak - DENY
    # -------------------------------------------------------------------------
    def test_property_gradual_leak_deny(self, property_policy):
        """
        Gradual water damage is excluded (wear and tear).
        """
        facts = create_facts_dict({
            "loss.cause": "gradual_leak",
            "damage.gradual": True,  # KEY: Gradual
            "dwelling.days_vacant": 0,
        })

        context = make_claim_context(
            claim_id="PROP-2024-004",
            jurisdiction="US-NY",
            line_of_business=LineOfBusiness.PROPERTY,
            loss_type="water_damage_sudden",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(property_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_wear_tear" in recommendation.exclusions_triggered

    # -------------------------------------------------------------------------
    # P5: Vacant Property - DENY
    # -------------------------------------------------------------------------
    def test_property_vacancy_deny(self, property_policy):
        """
        Property vacant > 30 days. Vacancy exclusion applies.
        """
        facts = create_facts_dict({
            "loss.cause": "theft",
            "damage.gradual": False,
            "dwelling.days_vacant": 45,  # KEY: Over 30 days
        })

        context = make_claim_context(
            claim_id="PROP-2024-005",
            jurisdiction="US-NY",
            line_of_business=LineOfBusiness.PROPERTY,
            loss_type="theft",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(property_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_vacancy" in recommendation.exclusions_triggered

    # -------------------------------------------------------------------------
    # P6: Earthquake - DENY
    # -------------------------------------------------------------------------
    def test_property_earthquake_deny(self, property_policy):
        """
        Earthquake damage excluded unless endorsed.
        """
        facts = create_facts_dict({
            "loss.cause": "earthquake",  # KEY: Earthquake
            "damage.gradual": False,
            "dwelling.days_vacant": 0,
        })

        context = make_claim_context(
            claim_id="PROP-2024-006",
            jurisdiction="US-NY",
            line_of_business=LineOfBusiness.PROPERTY,
            loss_type="fire",  # Coverage A
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(property_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_earthquake" in recommendation.exclusions_triggered


# =============================================================================
# MARINE SCENARIOS (Pleasure Craft)
# =============================================================================

class TestMarineScenarios:
    """Marine pleasure craft claim scenarios."""

    @pytest.fixture
    def marine_policy(self):
        """Create marine pleasure craft policy."""
        return make_policy(
            id="CA-ON-MARINE-2024",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.MARINE,
            product_code="PLEASURE",
            name="Pleasure Craft Policy",
            coverage_sections=[
                make_coverage_section(
                    id="hull_machinery",
                    name="Hull and Machinery",
                    code="Section A",
                    triggers=[
                        LossTypeTrigger(loss_type="storm_damage"),
                        LossTypeTrigger(loss_type="collision"),
                        LossTypeTrigger(loss_type="sinking"),
                    ],
                ),
            ],
            exclusions=[
                # Navigation Limits
                make_exclusion(
                    id="ex_navigation_limits",
                    name="Outside Navigation Limits",
                    code="E-1",
                    policy_wording="We do not cover loss outside approved navigation limits.",
                    policy_section_ref="Section E.1",
                    applies_to_coverages=["hull_machinery"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="vessel.within_navigation_limits",
                            value=False,
                        ),
                    ],
                ),
                # Operator Unqualified
                make_exclusion(
                    id="ex_operator_unqualified",
                    name="Operator Unqualified",
                    code="E-2",
                    policy_wording="We do not cover loss while operated by a person without a valid Pleasure Craft Operator Card.",
                    policy_section_ref="Section E.2",
                    applies_to_coverages=["hull_machinery"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="operator.pcoc_valid",
                            value=False,
                        ),
                    ],
                ),
                # Ice Damage
                make_exclusion(
                    id="ex_ice_damage",
                    name="Ice Damage",
                    code="E-3",
                    policy_wording="We do not cover loss caused by ice while the vessel is in water.",
                    policy_section_ref="Section E.3",
                    applies_to_coverages=["hull_machinery"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.AND,
                            children=[
                                make_condition(
                                    op=ConditionOperator.EQ,
                                    field="damage.cause",
                                    value="ice",
                                ),
                                make_condition(
                                    op=ConditionOperator.EQ,
                                    field="vessel.in_water",
                                    value=True,
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

    # -------------------------------------------------------------------------
    # M1: Storm Damage in Navigation Limits - APPROVE
    # -------------------------------------------------------------------------
    def test_marine_storm_approve(self, marine_policy):
        """
        Storm damage within navigation limits - covered.
        """
        facts = create_facts_dict({
            "vessel.within_navigation_limits": True,
            "operator.pcoc_valid": True,
            "vessel.in_water": True,
            "damage.cause": "storm",
        })

        context = make_claim_context(
            claim_id="MARINE-2024-001",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.MARINE,
            loss_type="storm_damage",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(marine_policy, context)

        assert recommendation.recommended_disposition == DispositionType.PAY

    # -------------------------------------------------------------------------
    # M2: Outside Navigation Limits - DENY
    # -------------------------------------------------------------------------
    def test_marine_navigation_limits_deny(self, marine_policy):
        """
        Loss occurred outside navigation limits.
        """
        # Provide all facts to avoid UNKNOWN status on other exclusions
        facts = create_facts_dict({
            "vessel.within_navigation_limits": False,  # KEY: Triggers exclusion
            "operator.pcoc_valid": True,
            "vessel.in_water": False,  # Not in water to avoid ice exclusion path
            "damage.cause": "storm",  # Not ice
        })

        context = make_claim_context(
            claim_id="MARINE-2024-002",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.MARINE,
            loss_type="storm_damage",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(marine_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_navigation_limits" in recommendation.exclusions_triggered

    # -------------------------------------------------------------------------
    # M3: No Operator License - DENY
    # -------------------------------------------------------------------------
    def test_marine_no_pcoc_deny(self, marine_policy):
        """
        Operator without valid PCOC - excluded.
        """
        # Provide all facts to avoid UNKNOWN status on other exclusions
        facts = create_facts_dict({
            "vessel.within_navigation_limits": True,
            "operator.pcoc_valid": False,  # KEY: Triggers exclusion
            "vessel.in_water": False,  # Not in water to avoid ice exclusion path
            "damage.cause": "collision",  # Not ice
        })

        context = make_claim_context(
            claim_id="MARINE-2024-003",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.MARINE,
            loss_type="collision",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(marine_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_operator_unqualified" in recommendation.exclusions_triggered

    # -------------------------------------------------------------------------
    # M4: Ice Damage While in Water - DENY
    # -------------------------------------------------------------------------
    def test_marine_ice_damage_deny(self, marine_policy):
        """
        Ice damage while in water is excluded.
        """
        facts = create_facts_dict({
            "vessel.within_navigation_limits": True,
            "operator.pcoc_valid": True,
            "vessel.in_water": True,  # KEY
            "damage.cause": "ice",  # KEY
        })

        context = make_claim_context(
            claim_id="MARINE-2024-004",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.MARINE,
            loss_type="storm_damage",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(marine_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_ice_damage" in recommendation.exclusions_triggered


# =============================================================================
# HEALTH SCENARIOS (Group Health)
# =============================================================================

class TestHealthScenarios:
    """Group health insurance claim scenarios."""

    @pytest.fixture
    def health_policy(self):
        """Create group health policy."""
        return make_policy(
            id="CA-ON-GROUP-HEALTH-2024",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.HEALTH,
            product_code="GROUP",
            name="Group Health Benefits",
            coverage_sections=[
                make_coverage_section(
                    id="drug_coverage",
                    name="Prescription Drug Coverage",
                    code="Section A",
                    triggers=[
                        LossTypeTrigger(loss_type="prescription_drug"),
                    ],
                ),
                make_coverage_section(
                    id="paramedical",
                    name="Paramedical Services",
                    code="Section B",
                    triggers=[
                        LossTypeTrigger(loss_type="paramedical"),
                    ],
                ),
            ],
            exclusions=[
                # Non-Formulary
                make_exclusion(
                    id="ex_non_formulary",
                    name="Non-Formulary Drug",
                    code="E-1",
                    policy_wording="We do not cover drugs not on the approved formulary without prior authorization.",
                    policy_section_ref="Section E.1",
                    applies_to_coverages=["drug_coverage"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.AND,
                            children=[
                                make_condition(
                                    op=ConditionOperator.EQ,
                                    field="drug.on_formulary",
                                    value=False,
                                ),
                                make_condition(
                                    op=ConditionOperator.EQ,
                                    field="drug.prior_auth_approved",
                                    value=False,
                                ),
                            ],
                        ),
                    ],
                ),
                # Pre-existing
                make_exclusion(
                    id="ex_preexisting",
                    name="Pre-existing Condition",
                    code="E-2",
                    policy_wording="We do not cover treatment for conditions diagnosed or treated within 12 months prior to coverage effective date.",
                    policy_section_ref="Section E.2",
                    applies_to_coverages=["drug_coverage", "paramedical"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.AND,
                            children=[
                                make_condition(
                                    op=ConditionOperator.EQ,
                                    field="condition.preexisting",
                                    value=True,
                                ),
                                make_condition(
                                    op=ConditionOperator.LT,
                                    field="member.coverage_months",
                                    value=12,
                                ),
                            ],
                        ),
                    ],
                ),
                # Work-Related
                make_exclusion(
                    id="ex_work_related",
                    name="Work-Related Injury",
                    code="E-3",
                    policy_wording="We do not cover injuries arising from employment, which are covered by WSIB.",
                    policy_section_ref="Section E.3",
                    applies_to_coverages=["drug_coverage", "paramedical"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="claim.work_related",
                            value=True,
                        ),
                    ],
                ),
            ],
        )

    # -------------------------------------------------------------------------
    # H1: Formulary Drug - APPROVE
    # -------------------------------------------------------------------------
    def test_health_formulary_drug_approve(self, health_policy):
        """
        Formulary drug with valid prescription - covered.
        """
        facts = create_facts_dict({
            "drug.on_formulary": True,
            "drug.prior_auth_approved": False,  # Not needed for formulary
            "condition.preexisting": False,
            "member.coverage_months": 24,
            "claim.work_related": False,
        })

        context = make_claim_context(
            claim_id="HEALTH-2024-001",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.HEALTH,
            loss_type="prescription_drug",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(health_policy, context)

        assert recommendation.recommended_disposition == DispositionType.PAY

    # -------------------------------------------------------------------------
    # H2: Non-Formulary No Prior Auth - DENY
    # -------------------------------------------------------------------------
    def test_health_non_formulary_deny(self, health_policy):
        """
        Non-formulary drug without prior auth - excluded.
        """
        facts = create_facts_dict({
            "drug.on_formulary": False,  # KEY
            "drug.prior_auth_approved": False,  # KEY
            "condition.preexisting": False,
            "member.coverage_months": 24,
            "claim.work_related": False,
        })

        context = make_claim_context(
            claim_id="HEALTH-2024-002",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.HEALTH,
            loss_type="prescription_drug",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(health_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_non_formulary" in recommendation.exclusions_triggered

    # -------------------------------------------------------------------------
    # H3: Pre-existing (New Member) - DENY
    # -------------------------------------------------------------------------
    def test_health_preexisting_deny(self, health_policy):
        """
        Pre-existing condition within 12-month lookback.
        """
        facts = create_facts_dict({
            "drug.on_formulary": True,
            "drug.prior_auth_approved": False,
            "condition.preexisting": True,  # KEY
            "member.coverage_months": 3,  # KEY: Less than 12
            "claim.work_related": False,
        })

        context = make_claim_context(
            claim_id="HEALTH-2024-003",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.HEALTH,
            loss_type="prescription_drug",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(health_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_preexisting" in recommendation.exclusions_triggered

    # -------------------------------------------------------------------------
    # H4: Work-Related - DENY
    # -------------------------------------------------------------------------
    def test_health_work_related_deny(self, health_policy):
        """
        Work-related injuries covered by WSIB, not group health.
        """
        facts = create_facts_dict({
            "drug.on_formulary": True,
            "drug.prior_auth_approved": False,
            "condition.preexisting": False,
            "member.coverage_months": 24,
            "claim.work_related": True,  # KEY
        })

        context = make_claim_context(
            claim_id="HEALTH-2024-004",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.HEALTH,
            loss_type="prescription_drug",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(health_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_work_related" in recommendation.exclusions_triggered


# =============================================================================
# WORKERS COMP SCENARIOS (Ontario WSIB)
# =============================================================================

class TestWorkersCompScenarios:
    """Ontario WSIB workers compensation scenarios."""

    @pytest.fixture
    def wsib_policy(self):
        """Create WSIB policy."""
        return make_policy(
            id="CA-ON-WSIB-2024",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.WORKERS_COMP,
            product_code="WSIB",
            name="WSIB Entitlement",
            coverage_sections=[
                make_coverage_section(
                    id="loss_of_earnings",
                    name="Loss of Earnings",
                    code="Section 43",
                    triggers=[
                        LossTypeTrigger(loss_type="work_injury"),
                    ],
                    preconditions=[
                        make_condition(
                            op=ConditionOperator.AND,
                            children=[
                                make_condition(
                                    op=ConditionOperator.EQ,
                                    field="injury.work_related",
                                    value=True,
                                ),
                                make_condition(
                                    op=ConditionOperator.EQ,
                                    field="employer.wsib_registered",
                                    value=True,
                                ),
                            ],
                        ),
                    ],
                ),
            ],
            exclusions=[
                # Not Work Related
                make_exclusion(
                    id="ex_not_work_related",
                    name="Not Work Related",
                    code="E-1",
                    policy_wording="Entitlement is limited to injuries arising out of and in the course of employment.",
                    policy_section_ref="Section 13",
                    applies_to_coverages=["loss_of_earnings"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="injury.work_related",
                            value=False,
                        ),
                    ],
                ),
                # Pre-existing Not Aggravated
                make_exclusion(
                    id="ex_preexisting",
                    name="Pre-existing Not Aggravated",
                    code="E-2",
                    policy_wording="Pre-existing conditions are only covered if significantly aggravated by work.",
                    policy_section_ref="Section 15",
                    applies_to_coverages=["loss_of_earnings"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.AND,
                            children=[
                                make_condition(
                                    op=ConditionOperator.EQ,
                                    field="condition.preexisting",
                                    value=True,
                                ),
                                make_condition(
                                    op=ConditionOperator.EQ,
                                    field="condition.aggravated_by_work",
                                    value=False,
                                ),
                            ],
                        ),
                    ],
                ),
                # Intoxication
                make_exclusion(
                    id="ex_intoxication",
                    name="Intoxication Sole Cause",
                    code="E-3",
                    policy_wording="Entitlement is not available if intoxication was the sole cause of the injury.",
                    policy_section_ref="Section 17",
                    applies_to_coverages=["loss_of_earnings"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="injury.intoxication_sole_cause",
                            value=True,
                        ),
                    ],
                ),
            ],
        )

    # -------------------------------------------------------------------------
    # W1: Work Injury - APPROVE
    # -------------------------------------------------------------------------
    def test_wsib_work_injury_approve(self, wsib_policy):
        """
        Clear work-related injury - entitled.
        """
        facts = create_facts_dict({
            "injury.work_related": True,
            "employer.wsib_registered": True,
            "condition.preexisting": False,
            "condition.aggravated_by_work": False,
            "injury.intoxication_sole_cause": False,
        })

        context = make_claim_context(
            claim_id="WSIB-2024-001",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.WORKERS_COMP,
            loss_type="work_injury",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(wsib_policy, context)

        assert recommendation.recommended_disposition == DispositionType.PAY

    # -------------------------------------------------------------------------
    # W2: Not Work Related - DENY
    # -------------------------------------------------------------------------
    def test_wsib_not_work_related_deny(self, wsib_policy):
        """
        Injury not work-related - not entitled.

        Note: When injury.work_related is False, the coverage precondition
        fails (WSIB coverage requires work-relatedness). This means NO coverage
        is triggered, resulting in DENY due to "no coverage" rather than
        due to exclusion. This is correct WSIB behavior - if it's not work-related,
        WSIB doesn't cover it at all.
        """
        facts = create_facts_dict({
            "injury.work_related": False,  # KEY: Fails coverage precondition
            "employer.wsib_registered": True,
            "condition.preexisting": False,
            "condition.aggravated_by_work": False,
            "injury.intoxication_sole_cause": False,
        })

        context = make_claim_context(
            claim_id="WSIB-2024-002",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.WORKERS_COMP,
            loss_type="work_injury",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(wsib_policy, context)

        # DENY because no coverage triggered (not because of exclusion)
        assert recommendation.recommended_disposition == DispositionType.DENY
        # No coverages should be evaluated since precondition failed
        assert len(recommendation.coverages_evaluated) == 0
        # Reasoning should indicate "no coverage triggered"
        assert any("No coverage" in step.result_reason for step in recommendation.reasoning_steps)

    # -------------------------------------------------------------------------
    # W3: Pre-existing Not Aggravated - DENY
    # -------------------------------------------------------------------------
    def test_wsib_preexisting_not_aggravated_deny(self, wsib_policy):
        """
        Pre-existing condition not aggravated by work.
        """
        facts = create_facts_dict({
            "injury.work_related": True,
            "employer.wsib_registered": True,
            "condition.preexisting": True,  # KEY
            "condition.aggravated_by_work": False,  # KEY
            "injury.intoxication_sole_cause": False,
        })

        context = make_claim_context(
            claim_id="WSIB-2024-003",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.WORKERS_COMP,
            loss_type="work_injury",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(wsib_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_preexisting" in recommendation.exclusions_triggered

    # -------------------------------------------------------------------------
    # W4: Intoxication Sole Cause - DENY
    # -------------------------------------------------------------------------
    def test_wsib_intoxication_deny(self, wsib_policy):
        """
        Intoxication as sole cause - not entitled.
        """
        facts = create_facts_dict({
            "injury.work_related": True,
            "employer.wsib_registered": True,
            "condition.preexisting": False,
            "condition.aggravated_by_work": False,
            "injury.intoxication_sole_cause": True,  # KEY
        })

        context = make_claim_context(
            claim_id="WSIB-2024-004",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.WORKERS_COMP,
            loss_type="work_injury",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(wsib_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_intoxication" in recommendation.exclusions_triggered


# =============================================================================
# CGL SCENARIOS (Commercial General Liability)
# =============================================================================

class TestCGLScenarios:
    """Commercial General Liability claim scenarios."""

    @pytest.fixture
    def cgl_policy(self):
        """Create CGL policy."""
        return make_policy(
            id="US-CGL-2024",
            jurisdiction="US-NY",
            line_of_business=LineOfBusiness.LIABILITY,
            product_code="CGL",
            name="Commercial General Liability",
            coverage_sections=[
                make_coverage_section(
                    id="coverage_a",
                    name="Bodily Injury and Property Damage",
                    code="Coverage A",
                    triggers=[
                        LossTypeTrigger(loss_type="bodily_injury_tp"),
                        LossTypeTrigger(loss_type="property_damage_tp"),
                    ],
                ),
            ],
            exclusions=[
                # Expected/Intended
                make_exclusion(
                    id="ex_expected_intended",
                    name="Expected or Intended Injury",
                    code="A-1",
                    policy_wording="This insurance does not apply to bodily injury or property damage expected or intended from the standpoint of the insured.",
                    policy_section_ref="Section A.1",
                    applies_to_coverages=["coverage_a"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="injury.expected_intended",
                            value=True,
                        ),
                    ],
                ),
                # Pollution
                make_exclusion(
                    id="ex_pollution",
                    name="Pollution",
                    code="A-2",
                    policy_wording="This insurance does not apply to bodily injury or property damage arising out of the discharge of pollutants.",
                    policy_section_ref="Section A.2",
                    applies_to_coverages=["coverage_a"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="loss.pollution_related",
                            value=True,
                        ),
                    ],
                ),
                # Auto
                make_exclusion(
                    id="ex_auto",
                    name="Automobile Liability",
                    code="A-3",
                    policy_wording="This insurance does not apply to bodily injury or property damage arising out of ownership or operation of an auto.",
                    policy_section_ref="Section A.3",
                    applies_to_coverages=["coverage_a"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="loss.auto_involved",
                            value=True,
                        ),
                    ],
                ),
            ],
        )

    # -------------------------------------------------------------------------
    # C1: Slip and Fall - APPROVE
    # -------------------------------------------------------------------------
    def test_cgl_slip_fall_approve(self, cgl_policy):
        """
        Premises liability - third party BI.
        """
        facts = create_facts_dict({
            "injury.expected_intended": False,
            "loss.pollution_related": False,
            "loss.auto_involved": False,
            "occurrence.during_policy_period": True,
        })

        context = make_claim_context(
            claim_id="CGL-2024-001",
            jurisdiction="US-NY",
            line_of_business=LineOfBusiness.LIABILITY,
            loss_type="bodily_injury_tp",
            claimant_type=ClaimantType.THIRD_PARTY,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(cgl_policy, context)

        assert recommendation.recommended_disposition == DispositionType.PAY

    # -------------------------------------------------------------------------
    # C2: Intentional Act - DENY
    # -------------------------------------------------------------------------
    def test_cgl_intentional_deny(self, cgl_policy):
        """
        Intentional act - excluded.
        """
        facts = create_facts_dict({
            "injury.expected_intended": True,  # KEY
            "loss.pollution_related": False,
            "loss.auto_involved": False,
        })

        context = make_claim_context(
            claim_id="CGL-2024-002",
            jurisdiction="US-NY",
            line_of_business=LineOfBusiness.LIABILITY,
            loss_type="bodily_injury_tp",
            claimant_type=ClaimantType.THIRD_PARTY,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(cgl_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_expected_intended" in recommendation.exclusions_triggered

    # -------------------------------------------------------------------------
    # C3: Pollution - DENY
    # -------------------------------------------------------------------------
    def test_cgl_pollution_deny(self, cgl_policy):
        """
        Pollution liability excluded under standard CGL.
        """
        facts = create_facts_dict({
            "injury.expected_intended": False,
            "loss.pollution_related": True,  # KEY
            "loss.auto_involved": False,
        })

        context = make_claim_context(
            claim_id="CGL-2024-003",
            jurisdiction="US-NY",
            line_of_business=LineOfBusiness.LIABILITY,
            loss_type="bodily_injury_tp",
            claimant_type=ClaimantType.THIRD_PARTY,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(cgl_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_pollution" in recommendation.exclusions_triggered

    # -------------------------------------------------------------------------
    # C4: Auto Involved - DENY
    # -------------------------------------------------------------------------
    def test_cgl_auto_deny(self, cgl_policy):
        """
        Auto liability excluded from CGL.
        """
        facts = create_facts_dict({
            "injury.expected_intended": False,
            "loss.pollution_related": False,
            "loss.auto_involved": True,  # KEY
        })

        context = make_claim_context(
            claim_id="CGL-2024-004",
            jurisdiction="US-NY",
            line_of_business=LineOfBusiness.LIABILITY,
            loss_type="bodily_injury_tp",
            claimant_type=ClaimantType.THIRD_PARTY,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(cgl_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_auto" in recommendation.exclusions_triggered


# =============================================================================
# E&O SCENARIOS (Professional Liability)
# =============================================================================

class TestEOScenarios:
    """Professional E&O (Errors & Omissions) claim scenarios."""

    @pytest.fixture
    def eo_policy(self):
        """Create E&O policy (claims-made)."""
        return make_policy(
            id="US-EO-2024",
            jurisdiction="US-NY",
            line_of_business=LineOfBusiness.PROFESSIONAL,
            product_code="EO",
            name="Professional Liability E&O",
            coverage_sections=[
                make_coverage_section(
                    id="professional_services",
                    name="Professional Services Coverage",
                    code="Section A",
                    triggers=[
                        LossTypeTrigger(loss_type="professional_negligence"),
                    ],
                    preconditions=[
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="claim.first_made_during_policy",
                            value=True,
                        ),
                    ],
                ),
            ],
            exclusions=[
                # Prior Acts
                make_exclusion(
                    id="ex_prior_acts",
                    name="Prior Acts",
                    code="E-1",
                    policy_wording="This policy does not cover claims arising from wrongful acts occurring before the retroactive date.",
                    policy_section_ref="Section E.1",
                    applies_to_coverages=["professional_services"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="wrongful_act.before_retro_date",
                            value=True,
                        ),
                    ],
                ),
                # Intentional/Dishonest
                make_exclusion(
                    id="ex_intentional",
                    name="Intentional or Dishonest Acts",
                    code="E-2",
                    policy_wording="This policy does not cover claims arising from fraudulent, dishonest, or intentional acts.",
                    policy_section_ref="Section E.2",
                    applies_to_coverages=["professional_services"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="act.fraudulent",
                            value=True,
                        ),
                    ],
                ),
            ],
        )

    # -------------------------------------------------------------------------
    # E1: Professional Negligence - COVERED
    # -------------------------------------------------------------------------
    def test_eo_negligence_covered(self, eo_policy):
        """
        Professional negligence within coverage.
        """
        facts = create_facts_dict({
            "claim.first_made_during_policy": True,
            "wrongful_act.before_retro_date": False,
            "act.fraudulent": False,
        })

        context = make_claim_context(
            claim_id="EO-2024-001",
            jurisdiction="US-NY",
            line_of_business=LineOfBusiness.PROFESSIONAL,
            loss_type="professional_negligence",
            claimant_type=ClaimantType.THIRD_PARTY,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(eo_policy, context)

        assert recommendation.recommended_disposition == DispositionType.PAY

    # -------------------------------------------------------------------------
    # E2: Prior Acts - DENY
    # -------------------------------------------------------------------------
    def test_eo_prior_acts_deny(self, eo_policy):
        """
        Act before retroactive date - excluded.
        """
        facts = create_facts_dict({
            "claim.first_made_during_policy": True,
            "wrongful_act.before_retro_date": True,  # KEY
            "act.fraudulent": False,
        })

        context = make_claim_context(
            claim_id="EO-2024-002",
            jurisdiction="US-NY",
            line_of_business=LineOfBusiness.PROFESSIONAL,
            loss_type="professional_negligence",
            claimant_type=ClaimantType.THIRD_PARTY,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(eo_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_prior_acts" in recommendation.exclusions_triggered

    # -------------------------------------------------------------------------
    # E3: Fraud - DENY
    # -------------------------------------------------------------------------
    def test_eo_fraud_deny(self, eo_policy):
        """
        Fraudulent acts excluded.
        """
        facts = create_facts_dict({
            "claim.first_made_during_policy": True,
            "wrongful_act.before_retro_date": False,
            "act.fraudulent": True,  # KEY
        })

        context = make_claim_context(
            claim_id="EO-2024-003",
            jurisdiction="US-NY",
            line_of_business=LineOfBusiness.PROFESSIONAL,
            loss_type="professional_negligence",
            claimant_type=ClaimantType.THIRD_PARTY,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(eo_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_intentional" in recommendation.exclusions_triggered


# =============================================================================
# TRAVEL SCENARIOS
# =============================================================================

class TestTravelScenarios:
    """Travel insurance claim scenarios."""

    @pytest.fixture
    def travel_policy(self):
        """Create travel insurance policy."""
        return make_policy(
            id="CA-TRAVEL-2024",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.OTHER,  # No specific travel LOB
            product_code="TRAVEL",
            name="Travel Medical Insurance",
            coverage_sections=[
                make_coverage_section(
                    id="emergency_medical",
                    name="Emergency Medical",
                    code="Section A",
                    triggers=[
                        LossTypeTrigger(loss_type="emergency_medical"),
                    ],
                    preconditions=[
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="insured.outside_home_province",
                            value=True,
                        ),
                    ],
                ),
            ],
            exclusions=[
                # Pre-existing Not Stable
                make_exclusion(
                    id="ex_preexisting",
                    name="Pre-existing Condition",
                    code="E-1",
                    policy_wording="We do not cover claims arising from pre-existing conditions that were not stable for 90 days prior to departure.",
                    policy_section_ref="Section E.1",
                    applies_to_coverages=["emergency_medical"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.AND,
                            children=[
                                make_condition(
                                    op=ConditionOperator.EQ,
                                    field="condition.preexisting",
                                    value=True,
                                ),
                                make_condition(
                                    op=ConditionOperator.EQ,
                                    field="condition.stable",
                                    value=False,
                                ),
                            ],
                        ),
                    ],
                ),
                # Not Emergency
                make_exclusion(
                    id="ex_not_emergency",
                    name="Non-Emergency Treatment",
                    code="E-2",
                    policy_wording="We do not cover elective or non-emergency treatment.",
                    policy_section_ref="Section E.2",
                    applies_to_coverages=["emergency_medical"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="treatment.emergency",
                            value=False,
                        ),
                    ],
                ),
                # High Risk Activity
                make_exclusion(
                    id="ex_high_risk",
                    name="High Risk Activity",
                    code="E-3",
                    policy_wording="We do not cover injuries from high-risk activities without specific endorsement.",
                    policy_section_ref="Section E.3",
                    applies_to_coverages=["emergency_medical"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="activity.high_risk",
                            value=True,
                        ),
                    ],
                ),
            ],
        )

    # -------------------------------------------------------------------------
    # T1: Emergency Medical Abroad - APPROVE
    # -------------------------------------------------------------------------
    def test_travel_emergency_approve(self, travel_policy):
        """
        Emergency medical abroad - covered.
        """
        facts = create_facts_dict({
            "insured.outside_home_province": True,
            "treatment.emergency": True,
            "condition.preexisting": False,
            "condition.stable": True,
            "activity.high_risk": False,
        })

        context = make_claim_context(
            claim_id="TRAVEL-2024-001",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.OTHER,
            loss_type="emergency_medical",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(travel_policy, context)

        assert recommendation.recommended_disposition == DispositionType.PAY

    # -------------------------------------------------------------------------
    # T2: Pre-existing Not Stable - DENY
    # -------------------------------------------------------------------------
    def test_travel_preexisting_unstable_deny(self, travel_policy):
        """
        Pre-existing condition not stable - excluded.
        """
        facts = create_facts_dict({
            "insured.outside_home_province": True,
            "treatment.emergency": True,
            "condition.preexisting": True,  # KEY
            "condition.stable": False,  # KEY
            "activity.high_risk": False,
        })

        context = make_claim_context(
            claim_id="TRAVEL-2024-002",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.OTHER,
            loss_type="emergency_medical",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(travel_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_preexisting" in recommendation.exclusions_triggered

    # -------------------------------------------------------------------------
    # T3: Elective Treatment - DENY
    # -------------------------------------------------------------------------
    def test_travel_elective_deny(self, travel_policy):
        """
        Non-emergency elective treatment - excluded.
        """
        facts = create_facts_dict({
            "insured.outside_home_province": True,
            "treatment.emergency": False,  # KEY: Not emergency
            "condition.preexisting": False,
            "condition.stable": True,
            "activity.high_risk": False,
        })

        context = make_claim_context(
            claim_id="TRAVEL-2024-003",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.OTHER,
            loss_type="emergency_medical",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(travel_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_not_emergency" in recommendation.exclusions_triggered

    # -------------------------------------------------------------------------
    # T4: High Risk Activity - DENY
    # -------------------------------------------------------------------------
    def test_travel_high_risk_deny(self, travel_policy):
        """
        High-risk activity without endorsement - excluded.
        """
        facts = create_facts_dict({
            "insured.outside_home_province": True,
            "treatment.emergency": True,
            "condition.preexisting": False,
            "condition.stable": True,
            "activity.high_risk": True,  # KEY
        })

        context = make_claim_context(
            claim_id="TRAVEL-2024-004",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.OTHER,
            loss_type="emergency_medical",
            claimant_type=ClaimantType.INSURED,
            facts=facts,
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(travel_policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "ex_high_risk" in recommendation.exclusions_triggered


# =============================================================================
# CROSS-CUTTING TESTS
# =============================================================================

class TestProvenanceAndAuditTrail:
    """Tests for provenance and audit trail across all scenarios."""

    def test_recommendation_has_provenance(self):
        """Every recommendation should have full provenance."""
        policy = make_policy(
            id="TEST-POL-001",
            coverage_sections=[
                make_coverage_section(
                    id="collision",
                    name="Collision",
                    triggers=[LossTypeTrigger(loss_type="collision")],
                ),
            ],
            exclusions=[],
        )

        context = make_claim_context(
            claim_id="TEST-001",
            loss_type="collision",
            facts={},
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(policy, context)

        # Provenance fields
        assert recommendation.policy_pack_id == "TEST-POL-001"
        assert recommendation.policy_pack_version is not None
        assert recommendation.policy_pack_hash != ""
        assert len(recommendation.policy_pack_hash) == 64  # SHA-256 hex
        assert recommendation.evaluated_at is not None
        assert recommendation.engine_version is not None

    def test_reasoning_steps_documented(self):
        """Every recommendation should have documented reasoning."""
        policy = make_policy(
            id="TEST-POL-002",
            coverage_sections=[
                make_coverage_section(
                    id="collision",
                    name="Collision",
                    triggers=[LossTypeTrigger(loss_type="collision")],
                ),
            ],
            exclusions=[],
        )

        context = make_claim_context(
            claim_id="TEST-002",
            loss_type="collision",
            facts={},
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(policy, context)

        # Must have reasoning steps
        assert len(recommendation.reasoning_steps) >= 3  # Coverage, Exclusion, Disposition at minimum

        # Each step must have required fields
        for step in recommendation.reasoning_steps:
            assert step.id is not None
            assert step.sequence > 0
            assert step.step_type is not None
            assert step.description is not None
            assert step.result is not None

    def test_exclusion_citations_present(self):
        """Triggered exclusions should cite their authorities."""
        policy = make_policy(
            id="TEST-POL-003",
            coverage_sections=[
                make_coverage_section(
                    id="collision",
                    name="Collision",
                    triggers=[LossTypeTrigger(loss_type="collision")],
                ),
            ],
            exclusions=[
                make_exclusion(
                    id="ex_test",
                    name="Test Exclusion",
                    code="4.1",
                    policy_wording="Test exclusion wording.",
                    policy_section_ref="Section 4.1",
                    applies_to_coverages=["collision"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="test.trigger",
                            value=True,
                        ),
                    ],
                ),
            ],
        )

        context = make_claim_context(
            claim_id="TEST-003",
            loss_type="collision",
            facts=create_facts_dict({"test.trigger": True}),
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert len(recommendation.authorities_cited) > 0

        # Citation should reference the exclusion
        sections = [a.section for a in recommendation.authorities_cited]
        assert any("4.1" in s or "Section 4.1" in s for s in sections)


class TestDeterminismAcrossLines:
    """Verify determinism across all lines of business."""

    @pytest.mark.parametrize("line,loss_type", [
        (LineOfBusiness.AUTO, "collision"),
        (LineOfBusiness.PROPERTY, "fire"),
        (LineOfBusiness.MARINE, "storm_damage"),
        (LineOfBusiness.HEALTH, "prescription_drug"),
        (LineOfBusiness.WORKERS_COMP, "work_injury"),
        (LineOfBusiness.LIABILITY, "bodily_injury_tp"),
    ])
    def test_deterministic_recommendations(self, line, loss_type):
        """Same inputs → same outputs across all lines."""
        policy = make_policy(
            id=f"TEST-{line.value}",
            line_of_business=line,
            coverage_sections=[
                make_coverage_section(
                    id=f"{line.value}_cov",
                    name=f"{line.value} Coverage",
                    triggers=[LossTypeTrigger(loss_type=loss_type)],
                ),
            ],
            exclusions=[],
        )

        context = make_claim_context(
            claim_id=f"TEST-{line.value}-001",
            line_of_business=line,
            loss_type=loss_type,
            facts={},
        )

        builder = RecommendationBuilder()

        # Run 10 times
        recommendations = [builder.build(policy, context) for _ in range(10)]

        # All should match first
        first = recommendations[0]
        for rec in recommendations[1:]:
            assert rec.recommended_disposition == first.recommended_disposition
            assert rec.certainty == first.certainty
            assert rec.coverages_evaluated == first.coverages_evaluated
            assert rec.exclusions_triggered == first.exclusions_triggered
            assert rec.policy_pack_hash == first.policy_pack_hash
