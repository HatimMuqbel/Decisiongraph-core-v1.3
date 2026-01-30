"""
Integration tests for ClaimPilot Engine components.

Tests cover:
- Context resolution
- Timeline calculation
- Evidence gating
- Recommendation building
- Determinism verification
"""
import pytest
from datetime import date

from claimpilot.models import (
    ClaimantType,
    ConditionOperator,
    DispositionType,
    GateStrictness,
    LineOfBusiness,
    LossTypeTrigger,
    PrecedentHit,
    PrecedentKey,
    SimilarityWeights,
    TimelineAnchor,
    TimelineEventType,
    TriBool,
    sort_precedents,
)
from claimpilot.engine import (
    ConditionEvaluator,
    ContextResolver,
    EvidenceGate,
    RecommendationBuilder,
    TimelineCalculator,
    add_business_days,
    is_business_day,
)
from claimpilot.engine.precedent_finder import (
    compute_similarity_score,
    jaccard_similarity,
)
from claimpilot.calendars import OntarioCalendar

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
    make_timeline_rule,
)


# =============================================================================
# Context Resolver Tests
# =============================================================================

class TestContextResolver:
    """Tests for context resolution."""

    def test_resolve_triggered_coverages(self):
        """Test coverages are triggered by loss type."""
        policy = make_policy(
            coverage_sections=[
                make_coverage_section(
                    id="collision",
                    name="Collision",
                    triggers=[
                        LossTypeTrigger(
                            loss_type="collision",
                            claimant_types=[ClaimantType.INSURED],
                        ),
                    ],
                ),
            ],
            exclusions=[],
        )

        context = make_claim_context(loss_type="collision")

        resolver = ContextResolver()
        resolved = resolver.resolve(policy, context)

        assert len(resolved.triggered_coverages) == 1
        assert resolved.triggered_coverages[0].id == "collision"

    def test_resolve_no_coverage_for_wrong_loss_type(self):
        """Test no coverage for unmatched loss type."""
        policy = make_policy(
            coverage_sections=[
                make_coverage_section(
                    id="collision",
                    name="Collision",
                    triggers=[
                        LossTypeTrigger(loss_type="collision"),
                    ],
                ),
            ],
            exclusions=[],
        )

        context = make_claim_context(loss_type="theft")

        resolver = ContextResolver()
        resolved = resolver.resolve(policy, context)

        assert len(resolved.triggered_coverages) == 0

    def test_resolve_exclusion_triggered(self):
        """Test exclusion is triggered when condition matches."""
        policy = make_policy(
            coverage_sections=[
                make_coverage_section(
                    id="collision",
                    name="Collision",
                    triggers=[LossTypeTrigger(loss_type="collision")],
                ),
            ],
            exclusions=[
                make_exclusion(
                    id="commercial",
                    name="Commercial Use",
                    applies_to_coverages=["collision"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="vehicle_use",
                            value="commercial",
                        ),
                    ],
                ),
            ],
        )

        context = make_claim_context(
            loss_type="collision",
            facts={
                "vehicle_use": make_fact("vehicle_use", "commercial"),
            },
        )

        resolver = ContextResolver()
        resolved = resolver.resolve(policy, context)

        assert len(resolved.triggered_exclusions) == 1
        assert resolved.triggered_exclusions[0].id == "commercial"


# =============================================================================
# Timeline Calculator Tests
# =============================================================================

class TestTimelineCalculator:
    """Tests for timeline calculation."""

    def test_add_business_days_simple(self):
        """Test adding business days without holidays."""
        # Monday + 3 business days = Thursday
        start = date(2024, 6, 10)  # Monday
        result = add_business_days(start, 3)
        assert result == date(2024, 6, 13)  # Thursday

    def test_add_business_days_over_weekend(self):
        """Test adding business days over weekend."""
        # Friday + 3 business days = Wednesday
        start = date(2024, 6, 14)  # Friday
        result = add_business_days(start, 3)
        assert result == date(2024, 6, 19)  # Wednesday

    def test_is_business_day_weekday(self):
        """Test weekday is business day."""
        assert is_business_day(date(2024, 6, 10)) is True  # Monday

    def test_is_business_day_weekend(self):
        """Test weekend is not business day."""
        assert is_business_day(date(2024, 6, 15)) is False  # Saturday

    def test_is_business_day_holiday(self):
        """Test Ontario holiday is not business day."""
        # Canada Day 2024 falls on Monday July 1
        assert is_business_day(date(2024, 7, 1)) is False

    def test_calculate_deadline(self):
        """Test calculating a timeline deadline."""
        rule = make_timeline_rule(
            id="acknowledge",
            name="Acknowledge Claim",
            event_type=TimelineEventType.ACKNOWLEDGE,
            anchor=TimelineAnchor.REPORT_DATE,
            days_from_anchor=3,
            business_days=True,
        )

        context = make_claim_context(
            report_date=date(2024, 6, 10),  # Monday
        )

        calculator = TimelineCalculator()
        deadline = calculator.calculate_deadline(rule, context)

        assert deadline is not None
        assert deadline.deadline_date == date(2024, 6, 13)  # Thursday


# =============================================================================
# Evidence Gate Tests
# =============================================================================

class TestEvidenceGate:
    """Tests for evidence gating."""

    def test_can_recommend_with_blocking_evidence(self):
        """Test cannot recommend when BLOCKING_RECOMMENDATION missing."""
        rule = make_evidence_rule(
            id="test",
            name="Test Rule",
            required_documents=[
                make_document_requirement(
                    "photos",
                    strictness=GateStrictness.BLOCKING_RECOMMENDATION,
                ),
            ],
            applies_when=make_condition(
                op=ConditionOperator.EQ,
                field="loss_type",
                value="collision",
            ),
        )

        # Claim with no evidence
        context = make_claim_context(
            loss_type="collision",
            evidence=[],
        )

        gate = EvidenceGate()
        result = gate.evaluate([rule], context)

        assert result.can_recommend is False
        assert len(result.blocking_recommendation) == 1

    def test_can_recommend_with_evidence_present(self):
        """Test can recommend when evidence is present."""
        rule = make_evidence_rule(
            id="test",
            name="Test Rule",
            required_documents=[
                make_document_requirement(
                    "photos",
                    strictness=GateStrictness.BLOCKING_RECOMMENDATION,
                ),
            ],
            applies_when=make_condition(
                op=ConditionOperator.EQ,
                field="loss_type",
                value="collision",
            ),
        )

        # Claim with photos
        context = make_claim_context(
            loss_type="collision",
            evidence=[make_evidence("photos")],
        )

        gate = EvidenceGate()
        result = gate.evaluate([rule], context)

        assert result.can_recommend is True

    def test_can_finalize_blocking(self):
        """Test cannot finalize when BLOCKING_FINALIZATION missing."""
        rule = make_evidence_rule(
            id="test",
            name="Test Rule",
            required_documents=[
                make_document_requirement(
                    "proof_of_loss",
                    strictness=GateStrictness.BLOCKING_FINALIZATION,
                ),
            ],
            applies_when=make_condition(
                op=ConditionOperator.EQ,
                field="loss_type",
                value="collision",
            ),
        )

        context = make_claim_context(
            loss_type="collision",
            evidence=[],
        )

        gate = EvidenceGate()
        result = gate.evaluate([rule], context)

        assert result.can_recommend is True
        assert result.can_finalize is False


# =============================================================================
# Recommendation Builder Tests
# =============================================================================

class TestRecommendationBuilder:
    """Tests for recommendation building."""

    def test_build_pay_recommendation(self):
        """Test building a PAY recommendation."""
        policy = make_policy(
            coverage_sections=[
                make_coverage_section(
                    id="collision",
                    name="Collision",
                    triggers=[
                        LossTypeTrigger(
                            loss_type="collision",
                            claimant_types=[ClaimantType.INSURED],
                        ),
                    ],
                ),
            ],
            exclusions=[],
        )

        context = make_claim_context(
            loss_type="collision",
            facts={
                "vehicle_use": make_fact("vehicle_use", "personal"),
            },
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(policy, context)

        # Coverage triggered, no exclusions
        assert recommendation.recommended_disposition == DispositionType.PAY

    def test_build_deny_recommendation_exclusion(self):
        """Test building a DENY recommendation due to exclusion."""
        policy = make_policy(
            coverage_sections=[
                make_coverage_section(
                    id="collision",
                    name="Collision",
                    triggers=[
                        LossTypeTrigger(
                            loss_type="collision",
                            claimant_types=[ClaimantType.INSURED],
                        ),
                    ],
                ),
            ],
            exclusions=[
                make_exclusion(
                    id="commercial",
                    name="Commercial Use",
                    applies_to_coverages=["collision"],
                    trigger_conditions=[
                        make_condition(
                            op=ConditionOperator.EQ,
                            field="vehicle_use",
                            value="commercial",
                        ),
                    ],
                ),
            ],
        )

        context = make_claim_context(
            loss_type="collision",
            facts={
                "vehicle_use": make_fact("vehicle_use", "commercial"),
            },
        )

        builder = RecommendationBuilder()
        recommendation = builder.build(policy, context)

        assert recommendation.recommended_disposition == DispositionType.DENY
        assert "commercial" in recommendation.exclusions_triggered


# =============================================================================
# Precedent Scoring Tests
# =============================================================================

class TestPrecedentScoring:
    """Tests for precedent scoring and sorting."""

    def test_jaccard_similarity(self):
        """Test Jaccard similarity calculation."""
        set_a = {"a", "b", "c", "d"}
        set_b = {"b", "c", "d", "e"}

        # Intersection: {b, c, d} = 3
        # Union: {a, b, c, d, e} = 5
        # Jaccard = 3/5 = 0.6
        score = jaccard_similarity(set_a, set_b)
        assert score == 0.6

    def test_jaccard_empty_sets(self):
        """Test Jaccard with empty sets."""
        assert jaccard_similarity(set(), set()) == 0.0

    def test_precedent_sort_by_similarity(self):
        """Test precedents sorted by similarity score."""
        precedents = [
            PrecedentHit(
                id="p1",
                case_id="CASE-001",
                case_date=date(2024, 1, 15),
                similarity_basis="test",
                recommended_disposition=DispositionType.PAY,
                similarity_score=0.75,
            ),
            PrecedentHit(
                id="p2",
                case_id="CASE-002",
                case_date=date(2024, 1, 15),
                similarity_basis="test",
                recommended_disposition=DispositionType.PAY,
                similarity_score=0.90,
            ),
        ]

        sorted_list = sort_precedents(precedents)

        # Higher score first
        assert sorted_list[0].similarity_score == 0.90
        assert sorted_list[1].similarity_score == 0.75

    def test_precedent_sort_tiebreaker_date(self):
        """Test date tiebreaker when scores are equal."""
        precedents = [
            PrecedentHit(
                id="p1",
                case_id="CASE-001",
                case_date=date(2024, 1, 15),  # Older
                similarity_basis="test",
                recommended_disposition=DispositionType.PAY,
                similarity_score=0.85,
            ),
            PrecedentHit(
                id="p2",
                case_id="CASE-002",
                case_date=date(2024, 6, 15),  # Newer
                similarity_basis="test",
                recommended_disposition=DispositionType.PAY,
                similarity_score=0.85,
            ),
        ]

        sorted_list = sort_precedents(precedents)

        # Newer date first when scores equal
        assert sorted_list[0].case_id == "CASE-002"


# =============================================================================
# Determinism Tests
# =============================================================================

class TestDeterminism:
    """Tests for deterministic behavior."""

    def test_condition_evaluation_deterministic(self):
        """Test condition evaluation is deterministic."""
        context = make_claim_context(
            facts={
                "vehicle_use": make_fact("vehicle_use", "personal"),
                "claim_amount": make_fact("claim_amount", 15000),
            },
        )

        condition = make_condition(
            op=ConditionOperator.AND,
            children=[
                make_condition(
                    id="c1",
                    op=ConditionOperator.EQ,
                    field="vehicle_use",
                    value="personal",
                ),
                make_condition(
                    id="c2",
                    op=ConditionOperator.GT,
                    field="claim_amount",
                    value=10000,
                ),
            ],
        )

        evaluator = ConditionEvaluator()
        results = [evaluator.evaluate(condition, context) for _ in range(50)]

        # All results should be identical
        first = results[0]
        for result in results[1:]:
            assert result.value == first.value

    def test_context_resolution_deterministic(self):
        """Test context resolution is deterministic."""
        policy = make_policy(
            coverage_sections=[
                make_coverage_section(
                    id="collision",
                    name="Collision",
                    triggers=[LossTypeTrigger(loss_type="collision")],
                ),
            ],
            exclusions=[],
        )

        context = make_claim_context(loss_type="collision")

        resolver = ContextResolver()
        results = [resolver.resolve(policy, context) for _ in range(20)]

        first_coverages = [c.id for c in results[0].triggered_coverages]
        for result in results[1:]:
            assert [c.id for c in result.triggered_coverages] == first_coverages

    def test_recommendation_deterministic(self):
        """Test recommendation building is deterministic."""
        policy = make_policy(
            coverage_sections=[
                make_coverage_section(
                    id="collision",
                    name="Collision",
                    triggers=[
                        LossTypeTrigger(
                            loss_type="collision",
                            claimant_types=[ClaimantType.INSURED],
                        ),
                    ],
                ),
            ],
            exclusions=[],
        )

        context = make_claim_context(loss_type="collision")

        builder = RecommendationBuilder()
        recommendations = [builder.build(policy, context) for _ in range(20)]

        first = recommendations[0]
        for rec in recommendations[1:]:
            assert rec.recommended_disposition == first.recommended_disposition
            assert rec.certainty == first.certainty
            assert rec.coverages_evaluated == first.coverages_evaluated
