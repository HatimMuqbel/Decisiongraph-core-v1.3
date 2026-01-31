"""
ClaimPilot Model Tests

Tests for all domain models in the ClaimPilot framework.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from claimpilot import (
    # Enums
    AuthorityType,
    ClaimantType,
    ConditionOperator,
    DispositionType,
    EvidenceStatus,
    FactCertainty,
    FactSource,
    GateStrictness,
    LineOfBusiness,
    PrecedentOutcome,
    ReasoningStepResult,
    ReasoningStepType,
    RecommendationCertainty,
    TimelineAnchor,
    TimelineEventType,
    # Conditions
    AND,
    BETWEEN,
    CONTAINS,
    EQ,
    GT,
    GTE,
    IN,
    IS_NOT_NULL,
    IS_NULL,
    LT,
    LTE,
    NE,
    NOT,
    NOT_IN,
    OR,
    PRED,
    Condition,
    EvaluationResult,
    Predicate,
    TriBool,
    # Authority
    AuthorityRef,
    AuthorityRegistry,
    AuthorityRule,
    # Policy
    CoverageLimits,
    CoverageSection,
    Deductibles,
    Exclusion,
    LossTypeTrigger,
    Policy,
    # Claim
    ClaimContext,
    EvidenceItem,
    Fact,
    FactSet,
    # Timeline
    TimelineEvent,
    TimelineRule,
    TimelineSummary,
    # Evidence
    DocumentRequirement,
    EvidenceChecklist,
    EvidenceGateResult,
    EvidenceRule,
    # Precedent
    PrecedentHit,
    PrecedentKey,
    PrecedentRecord,
    SimilarityWeights,
    sort_precedents,
    # Recommendation
    ReasoningStep,
    RecommendationMemo,
    RecommendationRecord,
    # Disposition
    DispositionApproval,
    FinalDisposition,
    # Utils
    canonical_json,
    content_hash,
    text_hash,
)


# =============================================================================
# TriBool Tests
# =============================================================================

class TestTriBool:
    """Test three-valued boolean logic."""

    def test_and_truth_table(self) -> None:
        """Test AND truth table (Kleene logic)."""
        # TRUE AND X
        assert (TriBool.TRUE & TriBool.TRUE) == TriBool.TRUE
        assert (TriBool.TRUE & TriBool.FALSE) == TriBool.FALSE
        assert (TriBool.TRUE & TriBool.UNKNOWN) == TriBool.UNKNOWN

        # FALSE AND X (False dominates)
        assert (TriBool.FALSE & TriBool.TRUE) == TriBool.FALSE
        assert (TriBool.FALSE & TriBool.FALSE) == TriBool.FALSE
        assert (TriBool.FALSE & TriBool.UNKNOWN) == TriBool.FALSE

        # UNKNOWN AND X
        assert (TriBool.UNKNOWN & TriBool.TRUE) == TriBool.UNKNOWN
        assert (TriBool.UNKNOWN & TriBool.FALSE) == TriBool.FALSE
        assert (TriBool.UNKNOWN & TriBool.UNKNOWN) == TriBool.UNKNOWN

    def test_or_truth_table(self) -> None:
        """Test OR truth table (Kleene logic)."""
        # TRUE OR X (True dominates)
        assert (TriBool.TRUE | TriBool.TRUE) == TriBool.TRUE
        assert (TriBool.TRUE | TriBool.FALSE) == TriBool.TRUE
        assert (TriBool.TRUE | TriBool.UNKNOWN) == TriBool.TRUE

        # FALSE OR X
        assert (TriBool.FALSE | TriBool.TRUE) == TriBool.TRUE
        assert (TriBool.FALSE | TriBool.FALSE) == TriBool.FALSE
        assert (TriBool.FALSE | TriBool.UNKNOWN) == TriBool.UNKNOWN

        # UNKNOWN OR X
        assert (TriBool.UNKNOWN | TriBool.TRUE) == TriBool.TRUE
        assert (TriBool.UNKNOWN | TriBool.FALSE) == TriBool.UNKNOWN
        assert (TriBool.UNKNOWN | TriBool.UNKNOWN) == TriBool.UNKNOWN

    def test_not_truth_table(self) -> None:
        """Test NOT truth table (Unknown stays Unknown)."""
        assert (~TriBool.TRUE) == TriBool.FALSE
        assert (~TriBool.FALSE) == TriBool.TRUE
        assert (~TriBool.UNKNOWN) == TriBool.UNKNOWN

    def test_from_bool(self) -> None:
        """Test conversion from Python bool."""
        assert TriBool.from_bool(True) == TriBool.TRUE
        assert TriBool.from_bool(False) == TriBool.FALSE
        assert TriBool.from_bool(None) == TriBool.UNKNOWN

    def test_is_methods(self) -> None:
        """Test is_* methods."""
        assert TriBool.TRUE.is_true()
        assert not TriBool.TRUE.is_false()
        assert TriBool.TRUE.is_known()

        assert TriBool.FALSE.is_false()
        assert not TriBool.FALSE.is_true()
        assert TriBool.FALSE.is_known()

        assert TriBool.UNKNOWN.is_unknown()
        assert not TriBool.UNKNOWN.is_known()

    def test_bool_conversion_raises_for_unknown(self) -> None:
        """Test that converting UNKNOWN to bool raises ValueError."""
        with pytest.raises(ValueError, match="Cannot convert"):
            bool(TriBool.UNKNOWN)


# =============================================================================
# Condition Tests
# =============================================================================

class TestCondition:
    """Test composable conditions."""

    def test_simple_predicate(self) -> None:
        """Test simple EQ predicate."""
        cond = EQ("claim.status", "open")
        assert not cond.is_logical
        assert cond.is_leaf
        assert cond.predicate is not None
        assert cond.predicate.field == "claim.status"
        assert cond.predicate.value == "open"

    def test_and_condition(self) -> None:
        """Test AND composition."""
        cond = AND(
            EQ("claim.status", "open"),
            GT("claim.amount", 1000),
        )
        assert cond.is_logical
        assert cond.op == ConditionOperator.AND
        assert len(cond.children) == 2

    def test_or_condition(self) -> None:
        """Test OR composition."""
        cond = OR(
            EQ("claim.type", "collision"),
            EQ("claim.type", "comprehensive"),
        )
        assert cond.is_logical
        assert cond.op == ConditionOperator.OR
        assert len(cond.children) == 2

    def test_not_condition(self) -> None:
        """Test NOT composition."""
        cond = NOT(EQ("claim.fraud", True))
        assert cond.is_logical
        assert cond.op == ConditionOperator.NOT
        assert len(cond.children) == 1

    def test_nested_condition(self) -> None:
        """Test nested conditions."""
        cond = AND(
            EQ("claim.status", "open"),
            OR(
                EQ("claim.type", "collision"),
                EQ("claim.type", "comprehensive"),
            ),
            NOT(EQ("claim.fraud_flag", True)),
        )
        assert cond.is_logical
        assert len(cond.children) == 3

    def test_predicate_with_logical_operator_raises(self) -> None:
        """Test that Predicate cannot use logical operators."""
        with pytest.raises(ValueError, match="cannot use logical operator"):
            Predicate("field", ConditionOperator.AND, "value")

    def test_all_comparison_helpers(self) -> None:
        """Test all comparison helper functions."""
        assert EQ("f", 1).predicate.operator == ConditionOperator.EQ
        assert NE("f", 1).predicate.operator == ConditionOperator.NE
        assert GT("f", 1).predicate.operator == ConditionOperator.GT
        assert GTE("f", 1).predicate.operator == ConditionOperator.GTE
        assert LT("f", 1).predicate.operator == ConditionOperator.LT
        assert LTE("f", 1).predicate.operator == ConditionOperator.LTE
        assert IN("f", [1, 2]).predicate.operator == ConditionOperator.IN
        assert NOT_IN("f", [1, 2]).predicate.operator == ConditionOperator.NOT_IN
        assert IS_NULL("f").predicate.operator == ConditionOperator.IS_NULL
        assert IS_NOT_NULL("f").predicate.operator == ConditionOperator.IS_NOT_NULL
        assert CONTAINS("f", "x").predicate.operator == ConditionOperator.CONTAINS
        assert BETWEEN("f", 1, 10).predicate.operator == ConditionOperator.BETWEEN


# =============================================================================
# EvaluationResult Tests
# =============================================================================

class TestEvaluationResult:
    """Test evaluation results."""

    def test_and_combination(self) -> None:
        """Test combining results with AND."""
        r1 = EvaluationResult(TriBool.TRUE, "first")
        r2 = EvaluationResult(TriBool.TRUE, "second")
        combined = r1 & r2
        assert combined.value == TriBool.TRUE

        r3 = EvaluationResult(TriBool.FALSE, "third")
        combined2 = r1 & r3
        assert combined2.value == TriBool.FALSE

    def test_or_combination(self) -> None:
        """Test combining results with OR."""
        r1 = EvaluationResult(TriBool.FALSE, "first")
        r2 = EvaluationResult(TriBool.TRUE, "second")
        combined = r1 | r2
        assert combined.value == TriBool.TRUE

    def test_not_combination(self) -> None:
        """Test negating results."""
        r1 = EvaluationResult(TriBool.TRUE, "original")
        negated = ~r1
        assert negated.value == TriBool.FALSE

    def test_missing_facts_propagate(self) -> None:
        """Test that missing facts propagate through combinations."""
        r1 = EvaluationResult(TriBool.UNKNOWN, "first", missing_fact_keys=["field1"])
        r2 = EvaluationResult(TriBool.TRUE, "second", missing_fact_keys=["field2"])
        combined = r1 & r2
        assert "field1" in combined.missing_fact_keys
        assert "field2" in combined.missing_fact_keys


# =============================================================================
# Authority Tests
# =============================================================================

class TestAuthorityRef:
    """Test authority references."""

    def test_create_authority(self) -> None:
        """Test creating an authority reference."""
        auth = AuthorityRef.create(
            authority_type=AuthorityType.POLICY_WORDING,
            title="Ontario Automobile Policy",
            section="Section 4.2.1",
            source_name="OAP 1",
            quote_excerpt="The insurer shall not pay...",
            full_text="The insurer shall not pay for loss or damage...",
            jurisdiction="CA-ON",
        )
        assert auth.id is not None
        assert auth.authority_type == AuthorityType.POLICY_WORDING
        assert auth.content_hash is not None

    def test_content_hash_verification(self) -> None:
        """Test content hash verification."""
        text = "The insurer shall not pay for loss or damage..."
        auth = AuthorityRef.create(
            authority_type=AuthorityType.POLICY_WORDING,
            title="Test Policy",
            section="1.1",
            source_name="Test",
            full_text=text,
        )
        assert auth.verify_content(text)
        assert not auth.verify_content("Different text")

    def test_effective_date_check(self) -> None:
        """Test effective date checking."""
        auth = AuthorityRef(
            id="test",
            authority_type=AuthorityType.REGULATION,
            title="Test Reg",
            section="1",
            source_name="Test",
            effective_date=date(2024, 1, 1),
            expiry_date=date(2024, 12, 31),
        )
        assert auth.is_effective_on(date(2024, 6, 15))
        assert not auth.is_effective_on(date(2023, 6, 15))
        assert not auth.is_effective_on(date(2025, 6, 15))


# =============================================================================
# Policy Tests
# =============================================================================

class TestPolicy:
    """Test policy models."""

    def test_create_policy(self) -> None:
        """Test creating a policy."""
        policy = Policy.create(
            jurisdiction="US-CA",
            line_of_business=LineOfBusiness.AUTO,
            product_code="PAP",
            name="Personal Auto Policy",
            version="2024.1",
            effective_date=date(2024, 1, 1),
        )
        assert policy.id == "US-CA-PAP-2024.1"
        assert policy.is_currently_effective

    def test_coverage_section(self) -> None:
        """Test coverage section."""
        coverage = CoverageSection(
            id="collision",
            code="Part A",
            name="Collision Coverage",
            description="Covers collision damage",
            triggers=[
                LossTypeTrigger("collision", [ClaimantType.INSURED]),
            ],
            limits=CoverageLimits(per_occurrence=Decimal("50000")),
        )
        assert coverage.is_triggered_by("collision", ClaimantType.INSURED)
        assert not coverage.is_triggered_by("theft", ClaimantType.INSURED)

    def test_exclusion(self) -> None:
        """Test exclusion."""
        exclusion = Exclusion(
            id="racing",
            code="4.2.1",
            name="Racing Exclusion",
            description="Racing activities excluded",
            policy_wording="Coverage does not apply while racing...",
            policy_section_ref="Section 4.2.1",
            applies_to_coverages=["collision", "comprehensive"],
        )
        assert exclusion.applies_to_coverage("collision")
        assert not exclusion.applies_to_coverage("liability")


# =============================================================================
# Claim Tests
# =============================================================================

class TestClaim:
    """Test claim models."""

    def test_create_fact(self) -> None:
        """Test creating a fact."""
        fact = Fact.create(
            claim_id="CLM-001",
            field="vehicle_use_type",
            value="personal",
            source=FactSource.CLAIMANT_STATEMENT,
            certainty=FactCertainty.REPORTED,
        )
        assert fact.id is not None
        assert fact.value_type == "string"
        assert fact.certainty == FactCertainty.REPORTED

    def test_fact_type_inference(self) -> None:
        """Test fact value type inference."""
        assert Fact.create("c", "f", "text", FactSource.ADJUSTER_INPUT).value_type == "string"
        assert Fact.create("c", "f", 100, FactSource.ADJUSTER_INPUT).value_type == "number"
        assert Fact.create("c", "f", True, FactSource.ADJUSTER_INPUT).value_type == "boolean"
        assert Fact.create("c", "f", date.today(), FactSource.ADJUSTER_INPUT).value_type == "date"
        assert Fact.create("c", "f", [1, 2], FactSource.ADJUSTER_INPUT).value_type == "list"

    def test_evidence_item(self) -> None:
        """Test evidence item."""
        evidence = EvidenceItem.create(
            claim_id="CLM-001",
            doc_type="police_report",
            description="Police report for accident",
        )
        assert evidence.status == EvidenceStatus.REQUESTED
        assert not evidence.is_available

        evidence.mark_received()
        assert evidence.status == EvidenceStatus.RECEIVED
        assert evidence.is_available

    def test_claim_context(self) -> None:
        """Test claim context."""
        context = ClaimContext(
            claim_id="CLM-001",
            policy_id="POL-001",
            jurisdiction="US-CA",
            line_of_business=LineOfBusiness.AUTO,
            loss_type="collision",
            loss_date=date(2024, 1, 15),
            report_date=date(2024, 1, 16),
            claimant_type=ClaimantType.INSURED,
        )
        assert context.days_since_loss == 1
        assert context.claim_id == "CLM-001"


# =============================================================================
# Timeline Tests
# =============================================================================

class TestTimeline:
    """Test timeline models."""

    def test_timeline_event_status(self) -> None:
        """Test timeline event status calculation."""
        event = TimelineEvent(
            rule_id="r1",
            event_type=TimelineEventType.ACKNOWLEDGE,
            due_date=date.today(),
            anchor_date=date.today(),
            anchor_type=TimelineAnchor.REPORT_DATE,
        )
        assert event.days_until_due == 0
        assert event.is_urgent

    def test_timeline_summary(self) -> None:
        """Test timeline summary."""
        summary = TimelineSummary(claim_id="CLM-001")
        # Add events with various statuses
        summary.events.append(TimelineEvent(
            rule_id="r1",
            event_type=TimelineEventType.ACKNOWLEDGE,
            due_date=date.today(),
            anchor_date=date.today(),
            anchor_type=TimelineAnchor.REPORT_DATE,
        ))
        assert summary.next_due_event is not None


# =============================================================================
# Precedent Tests
# =============================================================================

class TestPrecedent:
    """Test precedent models."""

    def test_precedent_key(self) -> None:
        """Test precedent key generation."""
        key = PrecedentKey.from_claim(
            jurisdiction="US-CA",
            line_of_business=LineOfBusiness.AUTO,
            loss_type="collision",
            coverage_ids=["collision", "comprehensive"],
            exclusion_wordings=["Racing exclusion text"],
            disposition_type=DispositionType.PAY,
            fact_keys={"vehicle_use", "driver_license"},
        )
        assert key.jurisdiction == "US-CA"
        assert len(key.coverage_ids_triggered) == 2
        assert len(key.exclusion_clause_hashes) == 1

    def test_precedent_sorting(self) -> None:
        """Test precedent sorting is deterministic."""
        hits = [
            PrecedentHit(
                id="1",
                case_id="A",
                case_date=date(2024, 1, 1),
                similarity_basis="Test",
                recommended_disposition="pay",
                similarity_score=Decimal("0.5"),
            ),
            PrecedentHit(
                id="2",
                case_id="B",
                case_date=date(2024, 6, 1),
                similarity_basis="Test",
                recommended_disposition="pay",
                similarity_score=Decimal("0.8"),
            ),
            PrecedentHit(
                id="3",
                case_id="C",
                case_date=date(2024, 3, 1),
                similarity_basis="Test",
                recommended_disposition="pay",
                similarity_score=Decimal("0.8"),
            ),
        ]
        sorted_hits = sort_precedents(hits)

        # Higher score first
        assert sorted_hits[0].case_id == "B"  # 0.8, newer
        assert sorted_hits[1].case_id == "C"  # 0.8, older
        assert sorted_hits[2].case_id == "A"  # 0.5


# =============================================================================
# Recommendation Tests
# =============================================================================

class TestRecommendation:
    """Test recommendation models."""

    def test_create_recommendation(self) -> None:
        """Test creating a recommendation."""
        rec = RecommendationRecord.create(
            claim_id="CLM-001",
            context_id="CTX-001",
            recommended_disposition=DispositionType.PAY,
            disposition_reason="All coverage requirements met",
            certainty=RecommendationCertainty.HIGH,
        )
        assert rec.id is not None
        assert rec.recommended_disposition == DispositionType.PAY
        assert not rec.has_uncertainty

    def test_recommendation_with_uncertainty(self) -> None:
        """Test recommendation with uncertainty."""
        rec = RecommendationRecord.create(
            claim_id="CLM-001",
            context_id="CTX-001",
            recommended_disposition=DispositionType.HOLD,
            disposition_reason="Missing facts",
            certainty=RecommendationCertainty.LOW,
        )
        rec.unknown_facts = ["vehicle_use_at_loss"]
        assert rec.has_uncertainty

    def test_recommendation_memo(self) -> None:
        """Test recommendation memo generation."""
        rec = RecommendationRecord.create(
            claim_id="CLM-001",
            context_id="CTX-001",
            recommended_disposition=DispositionType.PAY,
            disposition_reason="Coverage confirmed",
            certainty=RecommendationCertainty.HIGH,
        )
        memo = RecommendationMemo.from_recommendation(rec, "Coverage confirmed for collision claim")
        assert memo.claim_id == "CLM-001"
        assert memo.recommended_action == DispositionType.PAY

        # Test markdown generation
        md = memo.to_markdown()
        assert "# Recommendation Memo" in md
        assert "PAY" in md


# =============================================================================
# Disposition Tests
# =============================================================================

class TestDisposition:
    """Test disposition models."""

    def test_create_disposition(self) -> None:
        """Test creating a disposition."""
        disp = FinalDisposition.create(
            claim_id="CLM-001",
            recommendation_id="REC-001",
            disposition=DispositionType.PAY,
            disposition_reason="Approved per policy",
            followed_recommendation=True,
            finalizer_id="USR-001",
            finalizer_role="adjuster",
        )
        assert disp.id is not None
        assert disp.followed_recommendation
        assert not disp.is_override

    def test_disposition_override(self) -> None:
        """Test disposition override."""
        disp = FinalDisposition.create(
            claim_id="CLM-001",
            recommendation_id="REC-001",
            disposition=DispositionType.DENY,
            disposition_reason="Additional evidence revealed fraud",
            followed_recommendation=False,
            override_reason="Fraud indicators found",
            finalizer_id="USR-001",
            finalizer_role="supervisor",
        )
        assert disp.is_override
        assert disp.override_reason == "Fraud indicators found"

    def test_disposition_sealing(self) -> None:
        """Test disposition sealing."""
        disp = FinalDisposition.create(
            claim_id="CLM-001",
            recommendation_id="REC-001",
            disposition=DispositionType.PAY,
            disposition_reason="Approved",
            followed_recommendation=True,
            finalizer_id="USR-001",
            finalizer_role="adjuster",
        )
        assert not disp.is_sealed
        disp.seal()
        assert disp.is_sealed
        assert disp.content_hash is not None
        assert disp.verify_seal()


# =============================================================================
# Canonical JSON Tests
# =============================================================================

class TestCanonicalJson:
    """Test canonical JSON utilities."""

    def test_sorted_keys(self) -> None:
        """Test that keys are sorted."""
        data = {"z": 1, "a": 2, "m": 3}
        result = canonical_json(data)
        assert result == '{"a":2,"m":3,"z":1}'

    def test_no_whitespace(self) -> None:
        """Test that there's no whitespace."""
        data = {"key": "value"}
        result = canonical_json(data)
        assert " " not in result
        assert "\n" not in result

    def test_deterministic_hash(self) -> None:
        """Test that same input produces same hash."""
        data = {"b": 1, "a": 2}
        hash1 = content_hash(data)
        hash2 = content_hash(data)
        assert hash1 == hash2

    def test_different_input_different_hash(self) -> None:
        """Test that different input produces different hash."""
        hash1 = content_hash({"a": 1})
        hash2 = content_hash({"a": 2})
        assert hash1 != hash2

    def test_text_hash(self) -> None:
        """Test text hashing."""
        text = "The insurer shall not pay..."
        hash1 = text_hash(text)
        hash2 = text_hash(text)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex


# =============================================================================
# Policy Provenance Tests
# =============================================================================

class TestPolicyProvenance:
    """Test policy provenance features."""

    def test_normalize_excerpt(self) -> None:
        """Test excerpt normalization for consistent hashing."""
        from claimpilot.canon import normalize_excerpt

        # Collapse whitespace
        text1 = "  The insurer\n  shall not pay...  "
        text2 = "The insurer shall not pay..."
        assert normalize_excerpt(text1) == normalize_excerpt(text2)

        # Preserves case (no lowercasing - legal text fidelity)
        assert normalize_excerpt("HELLO") == "HELLO"
        assert normalize_excerpt("Hello World") == "Hello World"

    def test_excerpt_hash_consistency(self) -> None:
        """Test that excerpt hash is consistent regardless of whitespace formatting."""
        from claimpilot.canon import excerpt_hash

        # Same text with different whitespace formatting
        text1 = "The insurer shall not pay for loss or damage."
        text2 = "  The insurer  shall not pay for loss or damage.  "

        # Whitespace-different texts should produce same hash
        assert excerpt_hash(text1) == excerpt_hash(text2)

        # But different case produces different hash (preserves legal text)
        text3 = "THE INSURER SHALL NOT PAY FOR LOSS OR DAMAGE."
        assert excerpt_hash(text1) != excerpt_hash(text3)

    def test_authority_citation_from_ref(self) -> None:
        """Test creating AuthorityCitation from AuthorityRef."""
        from claimpilot.models import AuthorityCitation, AuthorityRef, AuthorityType

        ref = AuthorityRef(
            id="auth-001",
            authority_type=AuthorityType.POLICY_WORDING,
            title="Ontario Automobile Policy",
            section="Section 4.2.1",
            source_name="OAP 1",
            quote_excerpt="The insurer shall not pay for loss or damage",
            effective_date=date(2024, 1, 1),
        )

        citation = AuthorityCitation.from_authority_ref(ref)

        assert citation.authority_ref_id == "auth-001"
        assert citation.authority_type == AuthorityType.POLICY_WORDING
        assert citation.section_ref == "Section 4.2.1"
        assert citation.excerpt == "The insurer shall not pay for loss or damage"
        assert len(citation.excerpt_hash) == 64  # SHA-256 hex

    def test_authority_citation_verify_excerpt(self) -> None:
        """Test verifying excerpt against hash."""
        from claimpilot.models import AuthorityCitation, AuthorityRef, AuthorityType

        ref = AuthorityRef(
            id="auth-001",
            authority_type=AuthorityType.POLICY_WORDING,
            title="Test Policy",
            section="1.1",
            source_name="Test",
            quote_excerpt="Original text",
        )

        citation = AuthorityCitation.from_authority_ref(ref)

        # Should verify same text (with different whitespace formatting)
        assert citation.verify_excerpt("Original text")
        assert citation.verify_excerpt("  Original text  ")  # Whitespace is normalized
        assert citation.verify_excerpt("Original\n  text")   # Line breaks normalized too

        # Should fail for different text
        assert not citation.verify_excerpt("Modified text")

        # Case is preserved for legal text fidelity - different case = different hash
        assert not citation.verify_excerpt("ORIGINAL TEXT")
        assert not citation.verify_excerpt("original text")

    def test_compute_policy_pack_hash(self) -> None:
        """Test computing policy pack hash."""
        from claimpilot.canon import compute_policy_pack_hash
        from claimpilot.models import Policy, LineOfBusiness

        policy = Policy(
            id="CA-ON-OAP1-2024",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.AUTO,
            product_code="OAP1",
            name="Ontario Automobile Policy",
            version="2024.1",
            effective_date=date(2024, 1, 1),
        )

        hash1 = compute_policy_pack_hash(policy)
        hash2 = compute_policy_pack_hash(policy)

        # Should be deterministic
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex

    def test_policy_pack_hash_changes_with_content(self) -> None:
        """Test that policy pack hash changes when content changes."""
        from claimpilot.canon import compute_policy_pack_hash
        from claimpilot.models import Policy, LineOfBusiness

        policy1 = Policy(
            id="CA-ON-OAP1-2024",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.AUTO,
            product_code="OAP1",
            name="Ontario Automobile Policy",
            version="2024.1",
            effective_date=date(2024, 1, 1),
        )

        policy2 = Policy(
            id="CA-ON-OAP1-2024",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.AUTO,
            product_code="OAP1",
            name="Ontario Automobile Policy",
            version="2024.2",  # Changed version
            effective_date=date(2024, 1, 1),
        )

        hash1 = compute_policy_pack_hash(policy1)
        hash2 = compute_policy_pack_hash(policy2)

        # Hashes should be different
        assert hash1 != hash2

    def test_recommendation_record_has_provenance_fields(self) -> None:
        """Test that RecommendationRecord has policy provenance fields."""
        from claimpilot.models import (
            RecommendationRecord,
            DispositionType,
            RecommendationCertainty,
        )

        rec = RecommendationRecord.create(
            claim_id="CLM-001",
            context_id="CTX-001",
            recommended_disposition=DispositionType.PAY,
            disposition_reason="Coverage confirmed",
            certainty=RecommendationCertainty.HIGH,
        )

        # Should have policy provenance fields
        assert hasattr(rec, 'policy_pack_id')
        assert hasattr(rec, 'policy_pack_version')
        assert hasattr(rec, 'policy_pack_hash')
        assert hasattr(rec, 'authority_hashes')

        # Should have engine provenance fields
        assert hasattr(rec, 'policy_pack_loaded_at')
        assert hasattr(rec, 'evaluated_at')
        assert hasattr(rec, 'engine_version')

        # Default values
        assert rec.policy_pack_id == ""
        assert rec.policy_pack_version == ""
        assert rec.policy_pack_hash == ""
        assert rec.authority_hashes == []
        assert rec.engine_version == ""

    def test_policy_pack_hash_ordering_stability(self) -> None:
        """
        Policy pack hash should be stable regardless of insertion order.
        Lists are sorted by 'id' during serialization.
        """
        from claimpilot.canon import compute_policy_pack_hash
        from claimpilot.models import (
            Policy,
            CoverageSection,
            Exclusion,
            LineOfBusiness,
        )

        # Create two policies with same content but different insertion order
        coverage_a = CoverageSection(
            id="cov_a", code="A", name="Coverage A", description="First"
        )
        coverage_b = CoverageSection(
            id="cov_b", code="B", name="Coverage B", description="Second"
        )

        exclusion_x = Exclusion(
            id="ex_x",
            code="X",
            name="Exclusion X",
            description="First",
            policy_wording="Wording X",
            policy_section_ref="Section X",
        )
        exclusion_y = Exclusion(
            id="ex_y",
            code="Y",
            name="Exclusion Y",
            description="Second",
            policy_wording="Wording Y",
            policy_section_ref="Section Y",
        )

        # Policy 1: A before B, X before Y
        policy1 = Policy(
            id="TEST-001",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.AUTO,
            product_code="TEST",
            name="Test Policy",
            version="1.0",
            effective_date=date(2024, 1, 1),
            coverage_sections=[coverage_a, coverage_b],
            exclusions=[exclusion_x, exclusion_y],
        )

        # Policy 2: B before A, Y before X (different insertion order)
        policy2 = Policy(
            id="TEST-001",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.AUTO,
            product_code="TEST",
            name="Test Policy",
            version="1.0",
            effective_date=date(2024, 1, 1),
            coverage_sections=[coverage_b, coverage_a],  # Reversed
            exclusions=[exclusion_y, exclusion_x],  # Reversed
        )

        # Hashes should be identical (sorted by id during serialization)
        hash1 = compute_policy_pack_hash(policy1)
        hash2 = compute_policy_pack_hash(policy2)

        assert hash1 == hash2, "Policy pack hash should be stable regardless of list ordering"

    def test_normalize_excerpt_preserves_case(self) -> None:
        """Test that normalize_excerpt does NOT lowercase text (preserves legal fidelity)."""
        from claimpilot.canon import normalize_excerpt

        text = "The Insurer SHALL NOT pay for Loss or Damage"
        normalized = normalize_excerpt(text)

        # Should preserve case
        assert "SHALL NOT" in normalized
        assert "Insurer" in normalized
        assert normalized != normalized.lower()
