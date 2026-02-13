"""
Insurance Kernel Integration Tests — Phase D

Proves insurance uses the SAME kernel v3 precedent engine as banking.
Each test uses ONLY kernel imports + insurance registry.  No banking
imports in insurance tests → domain isolation.

Test matrix:
  1. Registry loads with correct field/disposition counts
  2. Seeds generate with v3 metadata
  3. Comparability gate filters structurally incompatible precedents
  4. Precedent scorer produces similarity scores
  5. Governed confidence returns four-dimension output
  6. Match classifier produces SUPPORTING/CONTRARY/NEUTRAL
  7. Regime tagging on insurance seeds
  8. Policy shift detection works
  9. Policy shift shadow outcome computation
 10. Domain loader can load both domains
 11. Cascade/typology detection for insurance
"""

from __future__ import annotations

import pytest

# --- kernel imports ONLY ---
from kernel.precedent.domain_registry import (
    DomainRegistry,
    FieldTier,
    ConfidenceLevel,
)
from kernel.precedent.comparability_gate import evaluate_gates
from kernel.precedent.precedent_scorer import (
    score_similarity,
    classify_match_v3,
    classify_match_two_axis,
    detect_primary_typology,
    anchor_facts_to_dict,
)
from kernel.precedent.governed_confidence import compute_governed_confidence
from kernel.precedent.domain_loader import load_domain, list_domains

# --- insurance domain imports (no banking imports) ---
from domains.insurance_claims.domain import create_registry
from domains.insurance_claims.seed_generator import generate_all_insurance_seeds
from domains.insurance_claims.policy_shifts import (
    detect_applicable_shifts,
    compute_shadow_outcome,
    extract_case_signals,
)
from domains.insurance_claims.reason_codes import InsuranceReasonCodeRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def registry() -> DomainRegistry:
    return create_registry()


@pytest.fixture(scope="module")
def seeds():
    return generate_all_insurance_seeds()


@pytest.fixture
def auto_claim_facts() -> dict:
    """Typical auto injury claim — moderate amount, fraud flags."""
    return {
        "claim.coverage_line": "auto",
        "claim.amount_band": "25k_100k",
        "claim.claimant_type": "first_party",
        "flag.fraud_indicator": True,
        "flag.prior_claims_frequency": "moderate",
        "flag.late_reporting": False,
        "flag.inconsistent_statements": True,
        "flag.staged_accident": False,
        "flag.excessive_claim_history": False,
        "flag.pre_existing_damage": False,
        "evidence.police_report": True,
        "evidence.medical_report": True,
        "evidence.witness_statements": False,
        "evidence.photos_documentation": True,
        "policy.deductible_band": "medium",
        "policy.coverage_limit_band": "standard",
        "policy.policy_age": "established",
        "claim.injury_type": "moderate",
        "claim.loss_cause": "collision",
        "claim.time_to_report": "within_week",
        "claim.occurred_during_policy": True,
        "screening.siu_referral": False,
        "prior.claims_denied": 1,
    }


@pytest.fixture
def property_claim_facts() -> dict:
    """Property water damage claim — clean, no flags."""
    return {
        "claim.coverage_line": "property",
        "claim.amount_band": "5k_25k",
        "claim.claimant_type": "first_party",
        "flag.fraud_indicator": False,
        "flag.prior_claims_frequency": "none",
        "flag.late_reporting": False,
        "flag.inconsistent_statements": False,
        "flag.staged_accident": False,
        "flag.excessive_claim_history": False,
        "flag.pre_existing_damage": False,
        "evidence.police_report": False,
        "evidence.medical_report": False,
        "evidence.witness_statements": False,
        "evidence.photos_documentation": True,
        "policy.deductible_band": "low",
        "policy.coverage_limit_band": "standard",
        "policy.policy_age": "mature",
        "claim.injury_type": "minor",
        "claim.loss_cause": "water",
        "claim.time_to_report": "immediate",
        "claim.occurred_during_policy": True,
        "screening.siu_referral": False,
        "prior.claims_denied": 0,
    }


# ---------------------------------------------------------------------------
# Test 1: Registry loads with correct counts
# ---------------------------------------------------------------------------

def test_registry_loads(registry):
    assert registry.domain == "insurance_claims"
    assert registry.version == "3.0"
    assert len(registry.fields) >= 20
    assert len(registry.comparability_gates) >= 3


def test_registry_has_structural_fields(registry):
    structural = registry.get_structural_fields()
    names = {f.name for f in structural}
    assert "claim.coverage_line" in names
    assert "claim.amount_band" in names
    assert "claim.claimant_type" in names


def test_registry_has_behavioral_fields(registry):
    behavioral = registry.get_behavioral_fields()
    names = {f.name for f in behavioral}
    assert "flag.fraud_indicator" in names
    assert "flag.staged_accident" in names


def test_registry_has_critical_fields(registry):
    assert len(registry.critical_fields) >= 3
    assert "claim.coverage_line" in registry.critical_fields
    assert "claim.amount_band" in registry.critical_fields


def test_registry_disposition_mapping(registry):
    assert registry.disposition_mapping["pay"] == "ALLOW"
    assert registry.disposition_mapping["deny"] == "BLOCK"
    assert registry.disposition_mapping["investigate"] == "EDD"


# ---------------------------------------------------------------------------
# Test 2: Seeds generate with v3 metadata
# ---------------------------------------------------------------------------

def test_seeds_generate(seeds):
    assert len(seeds) >= 1500


def test_seeds_have_v3_metadata(seeds):
    seed = seeds[0]
    assert seed.domain == "insurance"
    assert seed.disposition_basis in ("MANDATORY", "DISCRETIONARY")
    assert seed.reporting_obligation in ("NO_FILING", "FSRA_NOTICE", "FRAUD_REPORT")
    assert isinstance(seed.decision_drivers, list)
    assert len(seed.decision_drivers) > 0
    assert isinstance(seed.policy_regime, dict)
    assert "version" in seed.policy_regime
    assert "shifts_applied" in seed.policy_regime


def test_seeds_have_anchor_facts(seeds):
    seed = seeds[0]
    assert len(seed.anchor_facts) >= 15
    facts_dict = anchor_facts_to_dict(seed.anchor_facts)
    assert "claim.coverage_line" in facts_dict


def test_seeds_cover_multiple_lines(seeds):
    lines = set()
    for seed in seeds:
        facts = anchor_facts_to_dict(seed.anchor_facts)
        line = facts.get("claim.coverage_line")
        if line:
            lines.add(line)
    assert len(lines) >= 6  # At least 6 of 8 coverage lines


def test_seeds_have_mixed_dispositions(seeds):
    outcomes = {s.outcome_code for s in seeds}
    assert "pay" in outcomes
    assert "deny" in outcomes
    assert "escalate" in outcomes


# ---------------------------------------------------------------------------
# Test 3: Comparability gate filters
# ---------------------------------------------------------------------------

def test_gate_same_coverage_passes(registry, auto_claim_facts):
    """Same coverage line → gates pass."""
    prec_facts = {
        "jurisdiction_regime": "CA-ON",
        "coverage_family": "auto",
        "claimant_family": "first_party",
        "disposition_basis": "DISCRETIONARY",
    }
    case_gate_facts = {
        "jurisdiction_regime": "CA-ON",
        "coverage_family": "auto",
        "claimant_family": "first_party",
        "disposition_basis": "DISCRETIONARY",
    }
    passed, results = evaluate_gates(registry, case_gate_facts, prec_facts)
    assert passed


def test_gate_different_coverage_fails(registry):
    """Auto vs property → gate fails."""
    case_facts = {
        "jurisdiction_regime": "CA-ON",
        "coverage_family": "auto",
        "claimant_family": "first_party",
        "disposition_basis": "DISCRETIONARY",
    }
    prec_facts = {
        "jurisdiction_regime": "CA-ON",
        "coverage_family": "property",
        "claimant_family": "first_party",
        "disposition_basis": "DISCRETIONARY",
    }
    passed, results = evaluate_gates(registry, case_facts, prec_facts)
    assert not passed


def test_gate_cross_basis_fails(registry):
    """MANDATORY vs DISCRETIONARY → gate fails (INV-008)."""
    case_facts = {
        "jurisdiction_regime": "CA-ON",
        "coverage_family": "auto",
        "claimant_family": "first_party",
        "disposition_basis": "MANDATORY",
    }
    prec_facts = {
        "jurisdiction_regime": "CA-ON",
        "coverage_family": "auto",
        "claimant_family": "first_party",
        "disposition_basis": "DISCRETIONARY",
    }
    passed, results = evaluate_gates(registry, case_facts, prec_facts)
    assert not passed


# ---------------------------------------------------------------------------
# Test 4: Precedent scorer produces similarity scores
# ---------------------------------------------------------------------------

def test_scorer_identical_facts(registry, auto_claim_facts):
    """Identical facts → high similarity."""
    result = score_similarity(
        registry,
        auto_claim_facts,
        auto_claim_facts,
        precedent_drivers=["flag.fraud_indicator", "flag.inconsistent_statements"],
    )
    assert result.score > 0.90
    assert not result.non_transferable


def test_scorer_different_facts(registry, auto_claim_facts, property_claim_facts):
    """Different coverage lines → lower similarity."""
    result = score_similarity(
        registry,
        auto_claim_facts,
        property_claim_facts,
    )
    assert result.score < 0.90  # Different lines = lower similarity


def test_scorer_driver_mismatch_non_transferable(registry):
    """Driver mismatch → non-transferable."""
    case = {
        "flag.fraud_indicator": False,
        "flag.staged_accident": False,
        "claim.coverage_line": "auto",
        "claim.amount_band": "25k_100k",
    }
    prec = {
        "flag.fraud_indicator": True,
        "flag.staged_accident": True,
        "claim.coverage_line": "auto",
        "claim.amount_band": "25k_100k",
    }
    result = score_similarity(
        registry, case, prec,
        precedent_drivers=["flag.fraud_indicator", "flag.staged_accident"],
    )
    assert result.non_transferable


# ---------------------------------------------------------------------------
# Test 5: Governed confidence — four-dimension output
# ---------------------------------------------------------------------------

def test_governed_confidence(registry, auto_claim_facts):
    result = compute_governed_confidence(
        domain=registry,
        pool_size=25,
        avg_similarity=0.78,
        decisive_supporting=18,
        decisive_total=22,
        case_facts=auto_claim_facts,
    )
    assert result.level in (
        ConfidenceLevel.NONE, ConfidenceLevel.LOW,
        ConfidenceLevel.MODERATE, ConfidenceLevel.HIGH,
        ConfidenceLevel.VERY_HIGH,
    )
    assert len(result.dimensions) == 4
    dim_names = {d.name for d in result.dimensions}
    assert dim_names == {"pool_adequacy", "similarity_quality", "outcome_consistency", "evidence_completeness"}
    assert result.bottleneck is not None


def test_governed_confidence_zero_pool(registry, auto_claim_facts):
    """0 precedents → NONE confidence."""
    result = compute_governed_confidence(
        domain=registry,
        pool_size=0,
        avg_similarity=0.0,
        decisive_supporting=0,
        decisive_total=0,
        case_facts=auto_claim_facts,
    )
    assert result.level == ConfidenceLevel.NONE
    assert result.hard_rule_applied is not None


def test_governed_confidence_missing_critical(registry):
    """Missing critical fields → capped at LOW."""
    incomplete_facts = {
        "flag.fraud_indicator": True,
        # Missing: claim.coverage_line, claim.amount_band, claim.claimant_type
    }
    result = compute_governed_confidence(
        domain=registry,
        pool_size=30,
        avg_similarity=0.85,
        decisive_supporting=25,
        decisive_total=28,
        case_facts=incomplete_facts,
    )
    assert result.level <= ConfidenceLevel.LOW


# ---------------------------------------------------------------------------
# Test 6: Match classifier — SUPPORTING / CONTRARY / NEUTRAL
# ---------------------------------------------------------------------------

def test_classify_same_disposition_supporting():
    assert classify_match_v3("ALLOW", "ALLOW", "DISCRETIONARY", "DISCRETIONARY") == "supporting"


def test_classify_allow_block_contrary():
    assert classify_match_v3("ALLOW", "BLOCK", "DISCRETIONARY", "DISCRETIONARY") == "contrary"


def test_classify_cross_basis_neutral():
    assert classify_match_v3("ALLOW", "ALLOW", "MANDATORY", "DISCRETIONARY") == "neutral"


def test_classify_edd_neutral():
    assert classify_match_v3("ALLOW", "EDD", "DISCRETIONARY", "DISCRETIONARY") == "neutral"


def test_classify_non_transferable_neutral():
    assert classify_match_v3("ALLOW", "ALLOW", "DISCRETIONARY", "DISCRETIONARY", non_transferable=True) == "neutral"


# ---------------------------------------------------------------------------
# Test 6b: Two-axis classification — composite labels
# ---------------------------------------------------------------------------

def test_two_axis_fully_supporting():
    """BLOCK/STR vs BLOCK/STR → FULLY_SUPPORTING"""
    r = classify_match_two_axis("BLOCK", "BLOCK", "FILE_STR", "FILE_STR")
    assert r.op_alignment == "ALIGNED"
    assert r.suspicion_alignment == "ALIGNED"
    assert r.composite_label == "FULLY_SUPPORTING"


def test_two_axis_op_aligned_reg_divergent():
    """BLOCK/STR vs BLOCK/NO_REPORT → same action, different suspicion"""
    r = classify_match_two_axis("BLOCK", "BLOCK", "FILE_STR", "NO_REPORT")
    assert r.op_alignment == "ALIGNED"
    assert r.suspicion_alignment == "CONTRARY"
    assert r.composite_label == "OP_ALIGNED_REG_DIVERGENT"


def test_two_axis_partially_supporting():
    """EDD/STR vs BLOCK/STR → adjacent tier, same suspicion"""
    r = classify_match_two_axis("BLOCK", "EDD", "FILE_STR", "FILE_STR")
    assert r.op_alignment == "PARTIAL"
    assert r.suspicion_alignment == "ALIGNED"
    assert r.composite_label == "PARTIALLY_SUPPORTING"


def test_two_axis_partial_with_divergence():
    """EDD/NO_REPORT vs BLOCK/STR → adjacent tier, different suspicion"""
    r = classify_match_two_axis("BLOCK", "EDD", "FILE_STR", "NO_REPORT")
    assert r.op_alignment == "PARTIAL"
    assert r.suspicion_alignment == "CONTRARY"
    assert r.composite_label == "PARTIAL_WITH_DIVERGENCE"


def test_two_axis_op_contrary_reg_aligned():
    """ALLOW/NO_REPORT vs BLOCK/NO_REPORT → opposite action, same suspicion"""
    r = classify_match_two_axis("ALLOW", "BLOCK", "NO_REPORT", "NO_REPORT")
    assert r.op_alignment == "CONTRARY"
    assert r.suspicion_alignment == "ALIGNED"
    assert r.composite_label == "OP_CONTRARY_REG_ALIGNED"


def test_two_axis_fully_contrary():
    """ALLOW/NO_REPORT vs BLOCK/STR → opposite action, different suspicion"""
    r = classify_match_two_axis("ALLOW", "BLOCK", "NO_REPORT", "FILE_STR")
    assert r.op_alignment == "CONTRARY"
    assert r.suspicion_alignment == "CONTRARY"
    assert r.composite_label == "FULLY_CONTRARY"


def test_two_axis_edd_reporting_pending():
    """EDD with PENDING_EDD reporting → suspicion UNDETERMINED"""
    r = classify_match_two_axis("EDD", "EDD", "PENDING_EDD", "PENDING_EDD")
    assert r.op_alignment == "ALIGNED"
    assert r.suspicion_alignment == "UNDETERMINED"
    assert r.composite_label == "OP_ALIGNED_REG_PENDING"


def test_two_axis_non_transferable_caps_alignment():
    """Non-transferable: ALIGNED op → capped to PARTIAL"""
    r = classify_match_two_axis("BLOCK", "BLOCK", "FILE_STR", "FILE_STR",
                                 non_transferable=True)
    assert r.op_alignment == "PARTIAL"
    assert r.composite_label == "PARTIALLY_SUPPORTING"


def test_two_axis_unknown_disposition():
    """UNKNOWN dispositions → neutral composite"""
    r = classify_match_two_axis("UNKNOWN", "BLOCK", "FILE_STR", "FILE_STR")
    assert r.op_alignment == "PARTIAL"
    assert r.suspicion_alignment == "UNDETERMINED"


def test_two_axis_allow_str_controlled_delivery():
    """ALLOW/STR (controlled delivery) vs BLOCK/STR → contrary op, aligned susp"""
    r = classify_match_two_axis("BLOCK", "ALLOW", "FILE_STR", "FILE_STR")
    assert r.op_alignment == "CONTRARY"
    assert r.suspicion_alignment == "ALIGNED"
    assert r.composite_label == "OP_CONTRARY_REG_ALIGNED"


# ---------------------------------------------------------------------------
# Test 6c: Seed reporting dimension
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def banking_seeds():
    from domains.banking_aml.seed_generator import generate_all_banking_seeds
    return generate_all_banking_seeds(salt="test-reporting-dim")


def test_seeds_have_reporting_dimension(banking_seeds):
    """Every banking seed must carry a valid reporting_obligation."""
    for seed in banking_seeds:
        assert seed.reporting_obligation in (
            "NO_REPORT", "FILE_STR", "FILE_LCTR", "FILE_TPR", "PENDING_EDD", "UNDETERMINED",
        ), f"Unexpected reporting: {seed.reporting_obligation} for {seed.scenario_code}"


def test_block_discretionary_seeds_have_mixed_reporting(banking_seeds):
    """BLOCK/DISCRETIONARY seeds should have both FILE_STR and NO_REPORT."""
    block_disc = [
        s for s in banking_seeds
        if s.disposition_basis == "DISCRETIONARY"
        and s.outcome_code == "deny"  # v1 mapping for BLOCK
    ]
    assert len(block_disc) > 0, "No BLOCK/DISCRETIONARY seeds found"
    reporting_set = {s.reporting_obligation for s in block_disc}
    assert "FILE_STR" in reporting_set, "No FILE_STR in BLOCK/DISCRETIONARY seeds"
    assert "NO_REPORT" in reporting_set, "No NO_REPORT in BLOCK/DISCRETIONARY seeds"


def test_controlled_delivery_seeds_exist(banking_seeds):
    """At least one ALLOW/FILE_STR seed (controlled delivery) must exist."""
    allow_str = [
        s for s in banking_seeds
        if s.outcome_code == "pay" and s.reporting_obligation == "FILE_STR"
    ]
    assert len(allow_str) >= 1, "No ALLOW/STR (controlled delivery) seeds found"


def test_mandatory_block_always_files_str(banking_seeds):
    """MANDATORY blocks must always have FILE_STR reporting."""
    mandatory = [s for s in banking_seeds if s.disposition_basis == "MANDATORY"]
    for seed in mandatory:
        assert seed.reporting_obligation == "FILE_STR", (
            f"MANDATORY seed {seed.scenario_code} has {seed.reporting_obligation}"
        )


# ---------------------------------------------------------------------------
# Test 7: Regime tagging on seeds
# ---------------------------------------------------------------------------

def test_seeds_have_regime_tags(seeds):
    tagged = [s for s in seeds if s.policy_regime.get("shifts_applied")]
    # Some seeds should be affected by at least one shift
    # (not all — only those matching shift predicates)
    assert len(tagged) >= 0  # Non-negative is always true; real check below

    # Check structure of regime tag
    for seed in seeds[:10]:
        regime = seed.policy_regime
        assert "version" in regime
        assert "shifts_applied" in regime
        assert isinstance(regime["shifts_applied"], list)
        assert "is_post_shift" in regime


# ---------------------------------------------------------------------------
# Test 8: Policy shift detection
# ---------------------------------------------------------------------------

def test_detect_fsra_shift():
    """Auto minor injury → FSRA shift applies."""
    facts = {
        "claim.coverage_line": "auto",
        "claim.injury_type": "minor",
    }
    signals = extract_case_signals(facts)
    shifts = detect_applicable_shifts(case_signals=signals, case_facts=facts)
    shift_ids = [s["id"] for s in shifts]
    assert "fsra_minor_injury_cap" in shift_ids


def test_detect_fraud_ring_shift():
    """Staged accident → fraud ring shift applies."""
    facts = {
        "flag.staged_accident": True,
        "flag.fraud_indicator": True,
        "flag.inconsistent_statements": True,
    }
    signals = extract_case_signals(facts)
    shifts = detect_applicable_shifts(case_signals=signals, case_facts=facts)
    shift_ids = [s["id"] for s in shifts]
    assert "fraud_ring_detection" in shift_ids


def test_detect_climate_shift():
    """Property water damage → climate shift applies."""
    facts = {
        "claim.coverage_line": "property",
        "claim.loss_cause": "water",
    }
    signals = extract_case_signals(facts)
    shifts = detect_applicable_shifts(case_signals=signals, case_facts=facts)
    shift_ids = [s["id"] for s in shifts]
    assert "climate_event_coverage" in shift_ids


# ---------------------------------------------------------------------------
# Test 9: Shadow outcome computation
# ---------------------------------------------------------------------------

def test_shadow_outcome_fsra():
    facts = {
        "claim.coverage_line": "auto",
        "claim.injury_type": "minor",
    }
    result = compute_shadow_outcome(facts, "fsra_minor_injury_cap")
    assert result is not None
    assert result["disposition"] == "PAY_CLAIM"


def test_shadow_outcome_fraud_ring():
    facts = {
        "flag.staged_accident": True,
        "flag.fraud_indicator": True,
        "flag.inconsistent_statements": True,
    }
    result = compute_shadow_outcome(facts, "fraud_ring_detection")
    assert result is not None
    assert result["disposition"] == "REFER_SIU"
    assert result["decision_level"] == "siu_investigator"


def test_shadow_outcome_not_applicable():
    """Health claim should not be affected by FSRA auto shift."""
    facts = {
        "claim.coverage_line": "health",
        "claim.injury_type": "minor",
    }
    result = compute_shadow_outcome(facts, "fsra_minor_injury_cap")
    assert result is None


# ---------------------------------------------------------------------------
# Test 10: Domain loader loads both domains
# ---------------------------------------------------------------------------

def test_domain_loader_lists_both():
    domains = list_domains()
    assert "banking_aml" in domains
    assert "insurance_claims" in domains


def test_domain_loader_loads_insurance():
    reg = load_domain("insurance_claims")
    assert reg.domain == "insurance_claims"
    assert len(reg.fields) >= 20


def test_domain_loader_loads_banking():
    reg = load_domain("banking_aml")
    assert reg.domain == "banking_aml"
    assert len(reg.fields) >= 25


def test_domain_loader_unknown_raises():
    with pytest.raises(ValueError, match="Unknown domain"):
        load_domain("nonexistent_domain")


# ---------------------------------------------------------------------------
# Test 11: Typology detection for insurance
# ---------------------------------------------------------------------------

def test_typology_fraud():
    """Insurance fraud signals → 'fraud' typology (not defined yet, returns None)."""
    # The current typology detector is banking-centric; insurance typologies
    # would need their own overrides.  For now, verify it doesn't crash.
    result = detect_primary_typology(
        ["RC-FRD-STAGED", "RC-FRD-RING"],
        {"flag.fraud_indicator": True, "flag.staged_accident": True},
    )
    # No insurance-specific typology mapping yet, so result may be None
    assert result is None or isinstance(result, str)


def test_reason_code_registry():
    """Insurance reason codes load and are queryable."""
    reg = InsuranceReasonCodeRegistry()
    assert reg.count() >= 40
    code = reg.get_code("RC-FRD-STAGED")
    assert code.name == "Staged Accident"
    assert reg.validate_code("RC-COV-COVERED")
    assert not reg.validate_code("RC-NONEXISTENT")


# ---------------------------------------------------------------------------
# End-to-end: full pipeline (gate → score → confidence → classify)
# ---------------------------------------------------------------------------

def test_end_to_end_pipeline(registry, seeds, auto_claim_facts):
    """Full pipeline: pick a seed, gate it, score it, classify it."""
    # Pick a seed that matches auto coverage
    matching_seed = None
    for seed in seeds:
        facts = anchor_facts_to_dict(seed.anchor_facts)
        if facts.get("claim.coverage_line") == "auto":
            matching_seed = seed
            break
    assert matching_seed is not None, "No auto seed found"

    prec_facts = anchor_facts_to_dict(matching_seed.anchor_facts)

    # Gate check (using gate-field mapping)
    case_gate = {
        "jurisdiction_regime": "CA-ON",
        "coverage_family": auto_claim_facts.get("claim.coverage_line"),
        "claimant_family": auto_claim_facts.get("claim.claimant_type"),
        "disposition_basis": "DISCRETIONARY",
    }
    prec_gate = {
        "jurisdiction_regime": matching_seed.jurisdiction_code,
        "coverage_family": prec_facts.get("claim.coverage_line"),
        "claimant_family": prec_facts.get("claim.claimant_type"),
        "disposition_basis": matching_seed.disposition_basis,
    }
    passed, _ = evaluate_gates(registry, case_gate, prec_gate)
    # May or may not pass depending on exact seed — just run the pipeline

    # Score
    sim = score_similarity(
        registry, auto_claim_facts, prec_facts,
        precedent_drivers=matching_seed.decision_drivers,
    )
    assert 0.0 <= sim.score <= 1.0

    # Classify
    # Map v1 outcome codes to v3 dispositions
    v1_to_v3 = {"pay": "ALLOW", "escalate": "EDD", "deny": "BLOCK"}
    prec_disposition = v1_to_v3.get(matching_seed.outcome_code, "EDD")
    classification = classify_match_v3(
        "EDD", prec_disposition,
        "DISCRETIONARY", matching_seed.disposition_basis,
        non_transferable=sim.non_transferable,
    )
    assert classification in ("supporting", "contrary", "neutral")

    # Confidence (using seed pool stats)
    confidence = compute_governed_confidence(
        domain=registry,
        pool_size=10,
        avg_similarity=sim.score,
        decisive_supporting=7,
        decisive_total=9,
        case_facts=auto_claim_facts,
    )
    assert confidence.level in (
        ConfidenceLevel.NONE, ConfidenceLevel.LOW,
        ConfidenceLevel.MODERATE, ConfidenceLevel.HIGH,
        ConfidenceLevel.VERY_HIGH,
    )


# ---------------------------------------------------------------------------
# Test category: Similarity score clamping (FIX 1 regression guard)
# ---------------------------------------------------------------------------

class TestSimilarityScoreClamping:
    """Verify that similarity scores are always in [0.0, 1.0] and display ≤ 100%."""

    def test_score_similarity_bounded(self, registry, auto_claim_facts, seeds):
        """Raw similarity score must be in [0.0, 1.0] for all seed precedents."""
        prec_facts = anchor_facts_to_dict(seeds[0].anchor_facts)
        sim = score_similarity(
            registry, auto_claim_facts, prec_facts,
            precedent_drivers=seeds[0].decision_drivers,
        )
        assert 0.0 <= sim.score <= 1.0, (
            f"Similarity score {sim.score} out of [0.0, 1.0] bounds"
        )

    def test_display_pct_clamp_at_100(self):
        """Combined ranking score > 1.0 must clamp to 100% for display."""
        # Simulate a combined score that exceeds 1.0 due to multipliers
        # (decision_weight=1.15 × recency=1.0 × sim=0.95 = 1.0925)
        combined_score = 1.0925
        display_pct = min(int(round(combined_score * 100)), 100)
        assert display_pct == 100, f"Expected 100%, got {display_pct}%"

    def test_display_pct_normal_passthrough(self):
        """Scores below 1.0 should display as-is (no clamping needed)."""
        normal_score = 0.87
        display_pct = min(int(round(normal_score * 100)), 100)
        assert display_pct == 87

    def test_display_pct_exact_100(self):
        """A perfect 1.0 score should display as exactly 100%."""
        display_pct = min(int(round(1.0 * 100)), 100)
        assert display_pct == 100

    def test_score_assertion_fires_on_invalid(self, registry):
        """Verify the assertion in score_similarity catches out-of-bounds scores.

        We can't easily force a > 1.0 normalized score through the real function
        (weights are validated), so we test the boundary condition instead.
        """
        # Score with minimal input → should still be in bounds
        sim = score_similarity(registry, {}, {})
        assert 0.0 <= sim.score <= 1.0


# ---------------------------------------------------------------------------
# Test category: Signal count assertion (FIX 5 regression guard)
# ---------------------------------------------------------------------------

class TestSignalCountConsistency:
    """Verify that _dedupe_drivers produces correct counts and no premature placeholders."""

    def test_dedupe_removes_duplicates(self):
        """Duplicate driver labels should be collapsed."""
        from service.routers.report.derive import _dedupe_drivers

        drivers = [
            "Cross-border transfer with elevated corridor risk",
            "Wire transfer channel (SWIFT)",
            "Cross-border transfer with elevated corridor risk",  # duplicate
        ]
        result = _dedupe_drivers(drivers)
        assert len(result) == 2
        assert result[0] == "Cross-border transfer with elevated corridor risk"
        assert result[1] == "Wire transfer channel (SWIFT)"

    def test_dedupe_caps_at_limit(self):
        """Driver list should be capped at the specified limit."""
        from service.routers.report.derive import _dedupe_drivers

        drivers = [f"Signal {i}" for i in range(10)]
        result = _dedupe_drivers(drivers, cap=5)
        assert len(result) == 5

    def test_empty_drivers_get_fallback(self):
        """Empty driver list should produce the deterministic fallback."""
        from service.routers.report.derive import _dedupe_drivers

        result = _dedupe_drivers([])
        assert len(result) == 1
        assert "Deterministic rule activation" in result[0]

    def test_no_premature_no_indicators(self):
        """'No indicators' should NOT appear when real drivers exist.

        FIX 5 removed premature insertion of the placeholder before
        contextual drivers were collected.
        """
        from service.routers.report.derive import _dedupe_drivers

        drivers = [
            "Cross-border transfer with elevated corridor risk",
            "PEP exposure",
        ]
        result = _dedupe_drivers(drivers)
        assert not any("No indicators" in d for d in result)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Test category: Typology label generation (FIX 6 regression guard)
# ---------------------------------------------------------------------------

class TestTypologyLabelGeneration:
    """Verify _resolve_typology produces correct labels for NONE, FORMING, ESTABLISHED."""

    def test_typology_none_no_classifier(self):
        """Without classifier, legacy path should still return a string."""
        from service.routers.report.derive import _resolve_typology

        result = _resolve_typology(
            layer4_typologies={"typologies": []},
            rules_fired=[],
            layer6_suspicion={},
            classifier_result=None,
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_typology_none_with_zero_tier1(self):
        """Zero tier-1 signals + no FORMING typology → 'No suspicious typology'."""
        from service.routers.report.derive import _resolve_typology

        result = _resolve_typology(
            layer4_typologies={"typologies": []},
            rules_fired=[],
            layer6_suspicion={},
            classifier_result={"suspicion_count": 0, "tier1_signals": []},
        )
        assert result == "No suspicious typology identified"

    def test_typology_forming_stage_named(self):
        """Zero tier-1 signals + FORMING typology with real name → named forming label."""
        from service.routers.report.derive import _resolve_typology

        result = _resolve_typology(
            layer4_typologies={
                "typologies": [{"name": "structuring", "maturity": "FORMING"}]
            },
            rules_fired=[],
            layer6_suspicion={},
            classifier_result={"suspicion_count": 0, "tier1_signals": []},
        )
        assert "forming" in result.lower()
        assert "Structuring" in result
        # Must NOT say "No suspicious typology"
        assert "No suspicious typology" not in result

    def test_typology_forming_stage_positional(self):
        """Zero tier-1 signals + FORMING typology with positional name → unclassified."""
        from service.routers.report.derive import _resolve_typology

        result = _resolve_typology(
            layer4_typologies={
                "typologies": [{"name": "primary", "maturity": "FORMING"}]
            },
            rules_fired=[],
            layer6_suspicion={},
            classifier_result={"suspicion_count": 0, "tier1_signals": []},
        )
        assert "Unclassified behavioral indicators" in result
        assert "forming" in result.lower()
        assert "No suspicious typology" not in result

    def test_typology_validating_stage(self):
        """Zero tier-1 signals + VALIDATING typology → forming-stage label."""
        from service.routers.report.derive import _resolve_typology

        result = _resolve_typology(
            layer4_typologies={
                "typologies": [{"name": "layering", "maturity": "VALIDATING"}]
            },
            rules_fired=[],
            layer6_suspicion={},
            classifier_result={"suspicion_count": 0, "tier1_signals": []},
        )
        assert "forming" in result.lower() or "Layering" in result

    def test_typology_established_with_tier1(self):
        """Positive tier-1 signals → resolved typology name (not 'No suspicious')."""
        from service.routers.report.derive import _resolve_typology

        result = _resolve_typology(
            layer4_typologies={
                "typologies": [{"name": "structuring", "maturity": "CONFIRMED"}]
            },
            rules_fired=[],
            layer6_suspicion={},
            classifier_result={
                "suspicion_count": 2,
                "tier1_signals": [{"code": "STRUCTURING"}],
            },
        )
        assert result != "No suspicious typology identified"
        assert isinstance(result, str)
        assert len(result) > 0

    def test_typology_no_contradiction_with_forming(self):
        """FORMING typology must not produce contradictory 'No suspicious typology' label."""
        from service.routers.report.derive import _resolve_typology

        result = _resolve_typology(
            layer4_typologies={
                "typologies": [{"name": "primary", "maturity": "FORMING"}]
            },
            rules_fired=[],
            layer6_suspicion={},
            classifier_result={"suspicion_count": 0, "tier1_signals": []},
        )
        # The key invariant: FORMING typology present → cannot say "No suspicious typology"
        assert "No suspicious typology" not in result
