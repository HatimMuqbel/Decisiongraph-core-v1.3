"""
Tests for Phase B1: Regime Tagging + Temporal Partitioning

Covers:
- B1.1: JudgmentPayload policy_regime field
- B1.2: detect_applicable_shifts()
- B1.3: compute_shadow_outcome()
- B1.4: Seed tagging with policy_regime
- B1.5: SHIFT_EFFECTIVE_DATES parsing
"""

import pytest
from datetime import date

from decisiongraph.judgment import JudgmentPayload, AnchorFact
from decisiongraph.policy_shift_shadows import (
    POLICY_SHIFTS,
    SHIFT_EFFECTIVE_DATES,
    detect_applicable_shifts,
    compute_shadow_outcome,
    _case_facts_to_seed_like,
)


def _make_payload(**overrides) -> JudgmentPayload:
    """Build a minimal valid JudgmentPayload with sensible defaults."""
    defaults = dict(
        precedent_id="test-0000",
        scenario_code="test",
        outcome_code="ALLOW",
        anchor_facts=[],
        reason_codes=[],
        case_id_hash="a" * 64,
        jurisdiction_code="CA",
        fingerprint_hash="b" * 64,
        fingerprint_schema_id="decisiongraph:aml:txn_monitoring:v2",
        exclusion_codes=[],
        reason_code_registry_id="FINTRAC-2026",
        certainty="high",
        policy_pack_hash="c" * 64,
        policy_pack_id="CA-FINTRAC-AML",
        policy_version="2026.01.01",
        decision_level="analyst",
        decided_at="2026-01-15T12:00:00Z",
        decided_by_role="analyst",
        domain="banking",
    )
    defaults.update(overrides)
    return JudgmentPayload(**defaults)


# ── B1.1: JudgmentPayload policy_regime ─────────────────────────────


def test_judgment_payload_policy_regime_default():
    """policy_regime defaults to None."""
    p = _make_payload(precedent_id="test-1")
    assert p.policy_regime is None


def test_judgment_payload_policy_regime_set():
    """policy_regime can be set and round-trips through to_dict/from_dict."""
    regime = {
        "version": "2026.01.01",
        "shifts_applied": ["lctr_threshold"],
        "is_post_shift": False,
    }
    p = _make_payload(precedent_id="test-2", policy_regime=regime)
    assert p.policy_regime == regime

    d = p.to_dict()
    assert d["policy_regime"] == regime

    p2 = JudgmentPayload.from_dict(d)
    assert p2.policy_regime == regime


def test_judgment_payload_policy_regime_omitted_in_dict_when_none():
    """policy_regime should not appear in to_dict() when None."""
    p = _make_payload(precedent_id="test-3")
    d = p.to_dict()
    assert "policy_regime" not in d


# ── B1.2: detect_applicable_shifts() ────────────────────────────────


def test_detect_shifts_cash_3k_10k():
    """Cash transaction in 3k_10k band should trigger lctr_threshold."""
    facts = {
        "txn.type": "cash",
        "txn.amount_band": "3k_10k",
    }
    shifts = detect_applicable_shifts(case_facts=facts)
    ids = [s["id"] for s in shifts]
    assert "lctr_threshold" in ids


def test_detect_shifts_pep_over_25k():
    """PEP customer with ≥$25K should trigger pep_risk_appetite."""
    facts = {
        "customer.pep": True,
        "txn.amount_band": "25k_100k",
    }
    shifts = detect_applicable_shifts(case_facts=facts)
    ids = [s["id"] for s in shifts]
    assert "pep_risk_appetite" in ids


def test_detect_shifts_crypto():
    """Crypto transaction should trigger crypto_classification."""
    facts = {"txn.type": "crypto"}
    shifts = detect_applicable_shifts(case_facts=facts)
    ids = [s["id"] for s in shifts]
    assert "crypto_classification" in ids


def test_detect_shifts_structuring():
    """Just-below-threshold + multiple-same-day + no structuring flag → structuring_window."""
    facts = {
        "txn.just_below_threshold": True,
        "txn.multiple_same_day": True,
        "flag.structuring": False,
    }
    shifts = detect_applicable_shifts(case_facts=facts)
    ids = [s["id"] for s in shifts]
    assert "structuring_window" in ids


def test_detect_shifts_no_match():
    """Wire transaction with normal customer — no shifts should apply."""
    facts = {
        "txn.type": "wire_domestic",
        "txn.amount_band": "10k_25k",
        "customer.pep": False,
    }
    shifts = detect_applicable_shifts(case_facts=facts)
    assert shifts == []


def test_detect_shifts_returns_sorted_by_date():
    """Shifts should be sorted by effective_date."""
    facts = {
        "txn.type": "crypto",
        "customer.pep": True,
        "txn.amount_band": "25k_100k",
    }
    shifts = detect_applicable_shifts(case_facts=facts)
    dates = [s["effective_date"] for s in shifts]
    assert dates == sorted(dates)


# ── B1.3: compute_shadow_outcome() ──────────────────────────────────


def test_shadow_outcome_lctr():
    """LCTR shift should change reporting to FILE_LCTR."""
    facts = {"txn.type": "cash", "txn.amount_band": "3k_10k"}
    result = compute_shadow_outcome(facts, "lctr_threshold")
    assert result is not None
    assert result["reporting"] == "FILE_LCTR"


def test_shadow_outcome_pep():
    """PEP shift should escalate to EDD with senior_management."""
    facts = {"customer.pep": True, "txn.amount_band": "25k_100k"}
    result = compute_shadow_outcome(facts, "pep_risk_appetite")
    assert result is not None
    assert result["disposition"] == "EDD"
    assert result["decision_level"] == "senior_management"


def test_shadow_outcome_crypto():
    """Crypto shift should set disposition to EDD."""
    facts = {"txn.type": "crypto"}
    result = compute_shadow_outcome(facts, "crypto_classification")
    assert result is not None
    assert result["disposition"] == "EDD"
    assert result["reporting"] == "PENDING_EDD"


def test_shadow_outcome_structuring():
    """Structuring shift should set EDD with PENDING_EDD reporting."""
    facts = {
        "txn.just_below_threshold": True,
        "txn.multiple_same_day": True,
        "flag.structuring": False,
    }
    result = compute_shadow_outcome(facts, "structuring_window")
    assert result is not None
    assert result["disposition"] == "EDD"


def test_shadow_outcome_unaffected():
    """Wire transaction should not be affected by lctr_threshold."""
    facts = {"txn.type": "wire_domestic", "txn.amount_band": "10k_25k"}
    result = compute_shadow_outcome(facts, "lctr_threshold")
    assert result is None


def test_shadow_outcome_unknown_shift():
    """Unknown shift_id should return None."""
    facts = {"txn.type": "crypto"}
    result = compute_shadow_outcome(facts, "nonexistent_shift")
    assert result is None


# ── B1.5: SHIFT_EFFECTIVE_DATES ─────────────────────────────────────


def test_shift_effective_dates_parsed():
    """All 4 shifts should have parsed date objects."""
    assert len(SHIFT_EFFECTIVE_DATES) == 4
    for sid, d in SHIFT_EFFECTIVE_DATES.items():
        assert isinstance(d, date), f"{sid} should be a date"


def test_shift_effective_dates_values():
    """Spot-check specific effective dates."""
    assert SHIFT_EFFECTIVE_DATES["lctr_threshold"] == date(2026, 4, 1)
    assert SHIFT_EFFECTIVE_DATES["pep_risk_appetite"] == date(2026, 4, 1)
    assert SHIFT_EFFECTIVE_DATES["crypto_classification"] == date(2026, 7, 1)
    assert SHIFT_EFFECTIVE_DATES["structuring_window"] == date(2026, 4, 15)


# ── B1.4: Seed tagging ──────────────────────────────────────────────


def test_seeds_have_policy_regime():
    """All generated seeds should have a policy_regime dict."""
    from decisiongraph.aml_seed_generator import generate_all_banking_seeds

    seeds = generate_all_banking_seeds(salt="test-regime-check")
    for seed in seeds:
        pr = seed.policy_regime
        assert pr is not None, f"Seed {seed.precedent_id[:8]} missing policy_regime"
        assert "version" in pr
        assert "shifts_applied" in pr
        assert "is_post_shift" in pr
        assert isinstance(pr["shifts_applied"], list)
        assert isinstance(pr["is_post_shift"], bool)


def test_seeds_include_post_shift():
    """Some seeds should be marked as post-shift."""
    from decisiongraph.aml_seed_generator import generate_all_banking_seeds

    seeds = generate_all_banking_seeds(salt="test-post-shift")
    post_shift = [s for s in seeds if s.policy_regime and s.policy_regime.get("is_post_shift")]
    pre_shift = [s for s in seeds if s.policy_regime and not s.policy_regime.get("is_post_shift")]
    # We should have some of each
    assert len(post_shift) > 0, "Expected some post-shift seeds"
    assert len(pre_shift) > 0, "Expected some pre-shift seeds"


def test_post_shift_seeds_have_future_dates():
    """Post-shift seeds with shift_applied should have decided_at after effective date."""
    from decisiongraph.aml_seed_generator import generate_all_banking_seeds
    from datetime import datetime as dt

    seeds = generate_all_banking_seeds(salt="test-future-dates")
    for seed in seeds:
        pr = seed.policy_regime
        if not pr or not pr.get("is_post_shift") or not pr.get("shifts_applied"):
            continue
        decided = dt.fromisoformat(seed.decided_at.replace("Z", "+00:00")).date()
        for sid in pr["shifts_applied"]:
            eff = SHIFT_EFFECTIVE_DATES[sid]
            assert decided >= eff, (
                f"Post-shift seed {seed.precedent_id[:8]} decided_at {decided} "
                f"before effective date {eff} for shift {sid}"
            )


# ── Adapter: _case_facts_to_seed_like ────────────────────────────────


def test_case_facts_to_seed_like():
    """Adapter should convert flat dict to anchor_facts format."""
    facts = {"txn.type": "cash", "customer.pep": True}
    seed_like = _case_facts_to_seed_like(facts)
    assert "anchor_facts" in seed_like
    af_dict = {f["field_id"]: f["value"] for f in seed_like["anchor_facts"]}
    assert af_dict["txn.type"] == "cash"
    assert af_dict["customer.pep"] is True
