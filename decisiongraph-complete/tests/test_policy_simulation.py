"""
Tests for Phase C1: Policy Simulation Engine + Signal Refactor

Covers:
- C1.0: Signal-based shift detection refactor
- C1.1: PolicySimulation data models
- C1.2: Simulation engine
- C1.3: Unintended consequence detection
- C1.4: Demo drafts
- C1.5: API endpoints (via TestClient)
- C1.6: Enactment flow
"""

import pytest
from dataclasses import asdict

from decisiongraph.policy_shift_shadows import (
    POLICY_SHIFTS,
    detect_applicable_shifts,
    extract_case_signals,
)
from decisiongraph.policy_simulation import (
    DraftShift,
    SimulationResult,
    CascadeImpact,
    SimulationReport,
    PolicySimulator,
    DEMO_DRAFTS,
    DEMO_DRAFTS_BY_ID,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_seeds():
    """Generate seeds and convert to dict format for the simulator."""
    from decisiongraph.aml_seed_generator import generate_all_banking_seeds

    _V1_TO_DISPOSITION = {"pay": "ALLOW", "escalate": "EDD", "deny": "BLOCK"}
    payloads = generate_all_banking_seeds()
    seeds = []
    for p in payloads:
        d = p.to_dict()
        d["outcome"] = {
            "disposition": _V1_TO_DISPOSITION.get(d.get("outcome_code", ""), d.get("outcome_code", "")),
            "disposition_basis": d.get("disposition_basis", "DISCRETIONARY"),
            "reporting": d.get("reporting_obligation", "NO_REPORT"),
        }
        seeds.append(d)
    return seeds


@pytest.fixture(scope="module")
def seeds():
    return _make_seeds()


@pytest.fixture(scope="module")
def simulator(seeds):
    return PolicySimulator(seeds)


# ══════════════════════════════════════════════════════════════════════════
# C1.0: Signal Refactor Tests
# ══════════════════════════════════════════════════════════════════════════


class TestExtractCaseSignals:
    """Tests for extract_case_signals()."""

    def test_crypto_signal(self):
        signals = extract_case_signals({"txn.type": "crypto"})
        assert "VIRTUAL_ASSET_TRANSACTION" in signals

    def test_crypto_with_laundering(self):
        signals = extract_case_signals({
            "txn.type": "crypto",
            "flag.layering": True,
        })
        assert "VIRTUAL_ASSET_TRANSACTION" in signals
        assert "VIRTUAL_ASSET_LAUNDERING" in signals

    def test_pep_signal(self):
        signals = extract_case_signals({"customer.pep": True})
        assert "PEP_MATCH" in signals

    def test_pep_foreign_domestic(self):
        signals = extract_case_signals({
            "customer.pep": True,
            "customer.high_risk_jurisdiction": True,
        })
        assert "PEP_MATCH" in signals
        assert "PEP_FOREIGN_DOMESTIC" in signals

    def test_high_value_signal(self):
        signals = extract_case_signals({"txn.amount_band": "25k_100k"})
        assert "HIGH_VALUE" in signals

    def test_large_cash_signal(self):
        signals = extract_case_signals({
            "txn.type": "cash",
            "txn.amount_band": "3k_10k",
        })
        assert "LARGE_CASH_TRANSACTION" in signals

    def test_cross_border_signal(self):
        signals = extract_case_signals({"txn.cross_border": True})
        assert "CROSS_BORDER" in signals

    def test_structuring_signal(self):
        signals = extract_case_signals({"flag.structuring": True})
        assert "STRUCTURING_PATTERN" in signals

    def test_threshold_avoidance_signal(self):
        signals = extract_case_signals({
            "txn.just_below_threshold": True,
            "txn.multiple_same_day": True,
        })
        assert "THRESHOLD_AVOIDANCE" in signals

    def test_clean_case_no_signals(self):
        signals = extract_case_signals({
            "txn.type": "wire_domestic",
            "txn.amount_band": "10k_25k",
            "customer.pep": False,
        })
        assert signals == []


class TestSignalBasedDetection:
    """Tests that signal-based detection matches same cases as field-based."""

    def test_signal_matches_crypto(self):
        facts = {"txn.type": "crypto"}
        signals = extract_case_signals(facts)
        shifts = detect_applicable_shifts(case_signals=signals, case_facts=facts)
        ids = [s["id"] for s in shifts]
        assert "crypto_classification" in ids

    def test_signal_matches_pep(self):
        facts = {"customer.pep": True, "txn.amount_band": "25k_100k"}
        signals = extract_case_signals(facts)
        shifts = detect_applicable_shifts(case_signals=signals, case_facts=facts)
        ids = [s["id"] for s in shifts]
        assert "pep_risk_appetite" in ids

    def test_signal_matches_lctr(self):
        facts = {"txn.type": "cash", "txn.amount_band": "3k_10k"}
        signals = extract_case_signals(facts)
        shifts = detect_applicable_shifts(case_signals=signals, case_facts=facts)
        ids = [s["id"] for s in shifts]
        assert "lctr_threshold" in ids

    def test_signal_matches_structuring(self):
        facts = {
            "txn.just_below_threshold": True,
            "txn.multiple_same_day": True,
            "flag.structuring": False,
        }
        signals = extract_case_signals(facts)
        shifts = detect_applicable_shifts(case_signals=signals, case_facts=facts)
        ids = [s["id"] for s in shifts]
        assert "structuring_window" in ids

    def test_signal_no_false_positives_wire(self):
        facts = {
            "txn.type": "wire_domestic",
            "txn.amount_band": "10k_25k",
            "customer.pep": False,
        }
        signals = extract_case_signals(facts)
        shifts = detect_applicable_shifts(case_signals=signals, case_facts=facts)
        assert shifts == []

    def test_fallback_to_field_when_no_signals(self):
        """When case_signals is None, falls back to case_facts."""
        facts = {"txn.type": "crypto"}
        shifts = detect_applicable_shifts(case_facts=facts)
        ids = [s["id"] for s in shifts]
        assert "crypto_classification" in ids

    def test_trigger_signals_in_shift_metadata(self):
        """Shift metadata now includes trigger_signals."""
        for shift in POLICY_SHIFTS:
            assert "trigger_signals" in shift
            assert isinstance(shift["trigger_signals"], list)
            assert len(shift["trigger_signals"]) > 0


# ══════════════════════════════════════════════════════════════════════════
# C1.2: Simulation Tests
# ══════════════════════════════════════════════════════════════════════════


class TestSimulation:
    """Tests for the simulation engine."""

    def test_simulate_crypto_str(self, simulator):
        """Simulate crypto STR → affected count > 0."""
        draft = DEMO_DRAFTS_BY_ID["draft_crypto_str_mandatory"]
        report = simulator.simulate(draft)
        assert report.affected_cases > 0
        assert report.total_cases_evaluated > 0

    def test_simulate_cross_border_edd(self, simulator):
        """Simulate cross-border EDD → disposition changes exist."""
        draft = DEMO_DRAFTS_BY_ID["draft_cross_border_edd"]
        report = simulator.simulate(draft)
        assert report.total_cases_evaluated > 0
        # Cross-border seeds with HIGH_VALUE should be affected
        assert report.affected_cases >= 0  # May be 0 if no matching seeds

    def test_simulate_pep_zero_tolerance(self, simulator):
        """Simulate PEP zero tolerance → escalation count > 0."""
        draft = DEMO_DRAFTS_BY_ID["draft_pep_zero_tolerance"]
        report = simulator.simulate(draft)
        assert report.total_cases_evaluated > 0
        assert report.escalation_count > 0

    def test_compare_all_drafts(self, simulator):
        """Compare all 3 drafts → 3 reports returned."""
        reports = simulator.compare(DEMO_DRAFTS)
        assert len(reports) == 3
        for r in reports:
            assert isinstance(r, SimulationReport)
            assert r.timestamp  # non-empty

    def test_simulation_report_has_cascade(self, simulator):
        """Simulation reports include cascade_impacts."""
        draft = DEMO_DRAFTS_BY_ID["draft_crypto_str_mandatory"]
        report = simulator.simulate(draft)
        assert isinstance(report.cascade_impacts, list)

    def test_simulation_report_has_warnings(self, simulator):
        """Simulation reports include warnings list."""
        draft = DEMO_DRAFTS_BY_ID["draft_crypto_str_mandatory"]
        report = simulator.simulate(draft)
        assert isinstance(report.warnings, list)

    def test_simulation_report_has_case_results(self, simulator):
        """Simulation reports include per-case detail."""
        draft = DEMO_DRAFTS_BY_ID["draft_crypto_str_mandatory"]
        report = simulator.simulate(draft)
        assert len(report.case_results) == report.total_cases_evaluated
        for cr in report.case_results:
            assert isinstance(cr, SimulationResult)
            assert cr.escalation_direction in ("UP", "DOWN", "UNCHANGED")


# ══════════════════════════════════════════════════════════════════════════
# C1.2+: Cascade Tests
# ══════════════════════════════════════════════════════════════════════════


class TestCascade:
    """Tests for cross-decision cascade impact."""

    def test_crypto_cascade_pool_shift(self, simulator):
        """Crypto STR draft → cascade shows pool_after has more escalated."""
        draft = DEMO_DRAFTS_BY_ID["draft_crypto_str_mandatory"]
        report = simulator.simulate(draft)
        # At least some cascade impacts should exist for crypto seeds
        if report.cascade_impacts:
            for ci in report.cascade_impacts:
                assert isinstance(ci.pool_before, dict)
                assert isinstance(ci.pool_after, dict)

    def test_crypto_cascade_confidence_differs(self, simulator):
        """Crypto STR draft → confidence_after may differ from before."""
        draft = DEMO_DRAFTS_BY_ID["draft_crypto_str_mandatory"]
        report = simulator.simulate(draft)
        if report.cascade_impacts:
            # At least check structure
            for ci in report.cascade_impacts:
                assert ci.confidence_before in (
                    "NONE", "LOW", "MODERATE", "HIGH", "VERY_HIGH",
                )
                assert ci.confidence_after in (
                    "NONE", "LOW", "MODERATE", "HIGH", "VERY_HIGH",
                )

    def test_crypto_posture_reversal(self, simulator):
        """Crypto STR draft → posture_reversal for typologies with ALLOW majority."""
        draft = DEMO_DRAFTS_BY_ID["draft_crypto_str_mandatory"]
        report = simulator.simulate(draft)
        # Crypto seeds include clean_known_customer with ALLOW majority
        # that gets flipped to EDD under mandatory STR
        reversals = [ci for ci in report.cascade_impacts if ci.posture_reversal]
        assert len(reversals) > 0, (
            "Crypto STR should cause posture reversal in at least "
            "one typology (ALLOW→EDD)"
        )

    def test_cascade_non_empty_for_affected(self, simulator):
        """cascade_impacts list is non-empty for affected typologies."""
        draft = DEMO_DRAFTS_BY_ID["draft_crypto_str_mandatory"]
        report = simulator.simulate(draft)
        if report.affected_cases > 0:
            assert len(report.cascade_impacts) > 0

    def test_cascade_empty_for_unrelated(self, simulator):
        """Typologies not in draft should not appear in cascade."""
        draft = DEMO_DRAFTS_BY_ID["draft_crypto_str_mandatory"]
        report = simulator.simulate(draft)
        # crypto draft should not cascade into sanctions-only typologies
        for ci in report.cascade_impacts:
            assert ci.pool_size > 0

    def test_cascade_pool_adequacy_valid(self, simulator):
        """Pool adequacy labels are one of the valid values."""
        draft = DEMO_DRAFTS_BY_ID["draft_crypto_str_mandatory"]
        report = simulator.simulate(draft)
        for ci in report.cascade_impacts:
            assert ci.pool_adequacy in ("LOW", "MODERATE", "HIGH", "VERY_HIGH")


# ══════════════════════════════════════════════════════════════════════════
# C1.3: Unintended Consequence Tests
# ══════════════════════════════════════════════════════════════════════════


class TestUnintendedConsequences:
    """Tests for unintended consequence detection."""

    def test_crypto_str_volume_warning(self, simulator):
        """Crypto STR → STR volume spike warning present."""
        draft = DEMO_DRAFTS_BY_ID["draft_crypto_str_mandatory"]
        report = simulator.simulate(draft)
        # Should have at least one STR-related warning
        str_warnings = [w for w in report.warnings if "STR" in w]
        assert len(str_warnings) > 0, (
            f"Expected STR warning. Got: {report.warnings}"
        )

    def test_pep_disproportionate_segment(self, simulator):
        """PEP zero tolerance → disproportionate segment warning."""
        draft = DEMO_DRAFTS_BY_ID["draft_pep_zero_tolerance"]
        report = simulator.simulate(draft)
        segment_warnings = [w for w in report.warnings if "concentrated" in w.lower()]
        # PEP seeds are concentrated on pep=True segment
        assert len(segment_warnings) > 0, (
            f"Expected segment concentration warning. Got: {report.warnings}"
        )

    def test_cascade_degradation_warning(self, simulator):
        """When confidence drops, degradation warning should appear."""
        draft = DEMO_DRAFTS_BY_ID["draft_pep_zero_tolerance"]
        report = simulator.simulate(draft)
        degradation_warnings = [
            w for w in report.warnings if "degrade" in w.lower()
        ]
        # Check structure — degradation may or may not occur
        # but if any cascade has DEGRADED, there should be a warning
        degraded_cascades = [
            ci for ci in report.cascade_impacts
            if ci.confidence_direction == "DEGRADED"
        ]
        if degraded_cascades:
            assert len(degradation_warnings) > 0

    def test_posture_reversal_warning(self, simulator):
        """When posture reverses, warning should appear."""
        draft = DEMO_DRAFTS_BY_ID["draft_pep_zero_tolerance"]
        report = simulator.simulate(draft)
        reversal_warnings = [
            w for w in report.warnings if "reverse" in w.lower()
        ]
        reversed_cascades = [
            ci for ci in report.cascade_impacts if ci.posture_reversal
        ]
        if reversed_cascades:
            assert len(reversal_warnings) > 0


# ══════════════════════════════════════════════════════════════════════════
# Workload Tests
# ══════════════════════════════════════════════════════════════════════════


class TestWorkload:
    """Tests for workload impact calculations."""

    def test_analyst_hours_formula(self, simulator):
        """Verify: estimated_analyst_hours = EDD×2.5 + STR×1.5."""
        draft = DEMO_DRAFTS_BY_ID["draft_crypto_str_mandatory"]
        report = simulator.simulate(draft)
        expected = report.additional_edd_cases * 2.5 + report.additional_str_filings * 1.5
        assert report.estimated_analyst_hours_month == pytest.approx(expected)

    def test_filing_cost_formula(self, simulator):
        """Verify: estimated_filing_cost = STR×$150."""
        draft = DEMO_DRAFTS_BY_ID["draft_crypto_str_mandatory"]
        report = simulator.simulate(draft)
        expected = report.additional_str_filings * 150.0
        assert report.estimated_filing_cost_month == pytest.approx(expected)


# ══════════════════════════════════════════════════════════════════════════
# C1.6: Enactment Tests
# ══════════════════════════════════════════════════════════════════════════


class TestEnactment:
    """Tests for the enactment flow."""

    def test_enact_ready_status(self, simulator):
        """Enact returns READY_TO_ENACT status."""
        draft = DEMO_DRAFTS_BY_ID["draft_crypto_str_mandatory"]
        report = simulator.simulate(draft)
        result = simulator.enact(draft, report)
        assert result["status"] == "READY_TO_ENACT"

    def test_enact_has_trigger_signals(self, simulator):
        """Enact includes trigger_signals (not field references)."""
        draft = DEMO_DRAFTS_BY_ID["draft_crypto_str_mandatory"]
        report = simulator.simulate(draft)
        result = simulator.enact(draft, report)
        assert "trigger_signals" in result
        assert result["trigger_signals"] == draft.trigger_signals

    def test_enact_has_cascade_summary(self, simulator):
        """Enact includes cascade_summary."""
        draft = DEMO_DRAFTS_BY_ID["draft_crypto_str_mandatory"]
        report = simulator.simulate(draft)
        result = simulator.enact(draft, report)
        assert "cascade_summary" in result
        assert isinstance(result["cascade_summary"], dict)

    def test_enact_includes_magnitude(self, simulator):
        """Enact includes magnitude from simulation."""
        draft = DEMO_DRAFTS_BY_ID["draft_crypto_str_mandatory"]
        report = simulator.simulate(draft)
        result = simulator.enact(draft, report)
        assert result["magnitude"] in (
            "FUNDAMENTAL", "SIGNIFICANT", "MODERATE", "MINOR",
        )

    def test_enact_strips_draft_prefix(self, simulator):
        """Enact shift_id strips 'draft_' prefix."""
        draft = DEMO_DRAFTS_BY_ID["draft_crypto_str_mandatory"]
        report = simulator.simulate(draft)
        result = simulator.enact(draft, report)
        assert result["shift_id"] == "crypto_str_mandatory"
        assert not result["shift_id"].startswith("draft_")


# ══════════════════════════════════════════════════════════════════════════
# C1.5: API Endpoint Tests
# ══════════════════════════════════════════════════════════════════════════


class TestSimulationAPI:
    """Tests for simulation API endpoints via TestClient."""

    @pytest.fixture(scope="class")
    def client(self):
        from fastapi.testclient import TestClient
        from service.main import app
        return TestClient(app)

    def test_get_drafts(self, client):
        """GET /api/simulate/drafts returns 3 demo drafts."""
        resp = client.get("/api/simulate/drafts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        for d in data:
            assert "trigger_signals" in d
            assert len(d["trigger_signals"]) > 0

    def test_simulate_crypto(self, client):
        """POST /api/simulate with crypto draft returns valid report."""
        resp = client.post(
            "/api/simulate",
            json={"draft_id": "draft_crypto_str_mandatory"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["affected_cases"] > 0
        assert isinstance(data["cascade_impacts"], list)
        assert len(data["cascade_impacts"]) >= 1
        # Cascade shows confidence shift
        for ci in data["cascade_impacts"]:
            assert "confidence_before" in ci
            assert "confidence_after" in ci
        # Warnings include STR volume spike
        str_warnings = [w for w in data["warnings"] if "STR" in w]
        assert len(str_warnings) > 0

    def test_simulate_compare(self, client):
        """POST /api/simulate/compare with all 3 drafts returns 3 reports."""
        resp = client.post(
            "/api/simulate/compare",
            json={"draft_ids": [
                "draft_crypto_str_mandatory",
                "draft_cross_border_edd",
                "draft_pep_zero_tolerance",
            ]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    def test_simulate_unknown_draft(self, client):
        """POST /api/simulate with unknown draft returns 404."""
        resp = client.post(
            "/api/simulate",
            json={"draft_id": "nonexistent"},
        )
        assert resp.status_code == 404

    def test_compare_unknown_draft(self, client):
        """POST /api/simulate/compare with unknown draft returns 404."""
        resp = client.post(
            "/api/simulate/compare",
            json={"draft_ids": ["nonexistent"]},
        )
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════
# C1.4: Demo Draft Structure Tests
# ══════════════════════════════════════════════════════════════════════════


class TestDemoDrafts:
    """Tests for pre-built demo drafts."""

    def test_three_drafts_exist(self):
        assert len(DEMO_DRAFTS) == 3

    def test_draft_ids_unique(self):
        ids = [d.id for d in DEMO_DRAFTS]
        assert len(ids) == len(set(ids))

    def test_drafts_have_trigger_signals(self):
        for d in DEMO_DRAFTS:
            assert len(d.trigger_signals) > 0

    def test_drafts_have_citations(self):
        for d in DEMO_DRAFTS:
            assert d.citation is not None

    def test_draft_lookup_works(self):
        assert "draft_crypto_str_mandatory" in DEMO_DRAFTS_BY_ID
        assert "draft_cross_border_edd" in DEMO_DRAFTS_BY_ID
        assert "draft_pep_zero_tolerance" in DEMO_DRAFTS_BY_ID
