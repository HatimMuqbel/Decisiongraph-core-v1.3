"""Tests for v3 report integration — derive.py and validate_output.py with v3 data."""

import sys
from pathlib import Path

import pytest

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent / "service"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ---------------------------------------------------------------------------
# derive.py — _compute_confidence_score with v3 data
# ---------------------------------------------------------------------------

def _import_compute_confidence():
    from routers.report.derive import _compute_confidence_score
    return _compute_confidence_score


class TestComputeConfidenceV3:
    def test_v3_very_high_adds_30(self):
        compute = _import_compute_confidence()
        label, reason, score = compute(
            rules_fired=[{"result": "TRIGGERED"}, {"result": "TRIGGERED"}, {"result": "TRIGGERED"}],
            evidence_used=list(range(10)),
            precedent_analysis={
                "available": True,
                "confidence_model_version": "v3",
                "confidence_level": "VERY_HIGH",
                "contrary_precedents": 0,
            },
            risk_factors=[],
        )
        # 30 (rules) + 25 (evidence) + 30 (v3 VERY_HIGH) + 15 (no contrary) = 100
        assert score == 100

    def test_v3_high_adds_25(self):
        compute = _import_compute_confidence()
        _, _, score = compute(
            rules_fired=[{"result": "TRIGGERED"}],
            evidence_used=list(range(5)),
            precedent_analysis={
                "available": True,
                "confidence_model_version": "v3",
                "confidence_level": "HIGH",
                "contrary_precedents": 0,
            },
            risk_factors=[],
        )
        # 20 (1 triggered) + 18 (5 evidence) + 25 (v3 HIGH) + 15 (no contrary) = 78
        assert score == 78

    def test_v3_moderate_adds_15(self):
        compute = _import_compute_confidence()
        _, _, score = compute(
            rules_fired=[{"result": "TRIGGERED"}],
            evidence_used=list(range(5)),
            precedent_analysis={
                "available": True,
                "confidence_model_version": "v3",
                "confidence_level": "MODERATE",
                "contrary_precedents": 0,
            },
            risk_factors=[],
        )
        # 20 + 18 + 15 + 15 = 68
        assert score == 68

    def test_v3_low_adds_5(self):
        compute = _import_compute_confidence()
        _, _, score = compute(
            rules_fired=[{"result": "TRIGGERED"}],
            evidence_used=list(range(5)),
            precedent_analysis={
                "available": True,
                "confidence_model_version": "v3",
                "confidence_level": "LOW",
                "contrary_precedents": 0,
            },
            risk_factors=[],
        )
        # 20 + 18 + 5 + 15 = 58
        assert score == 58

    def test_v3_none_adds_0(self):
        compute = _import_compute_confidence()
        _, _, score = compute(
            rules_fired=[{"result": "TRIGGERED"}],
            evidence_used=list(range(5)),
            precedent_analysis={
                "available": True,
                "confidence_model_version": "v3",
                "confidence_level": "NONE",
                "contrary_precedents": 0,
            },
            risk_factors=[],
        )
        # 20 + 18 + 0 + 15 = 53
        assert score == 53

    def test_v2_fallback_still_works(self):
        """Without confidence_model_version, v2 path is used."""
        compute = _import_compute_confidence()
        _, _, score = compute(
            rules_fired=[{"result": "TRIGGERED"}],
            evidence_used=list(range(5)),
            precedent_analysis={
                "available": True,
                "precedent_confidence": 0.80,
                "decisive_total": 10,
                "contrary_precedents": 0,
            },
            risk_factors=[],
        )
        # 20 + 18 + 30 (conf >= 0.75) + 15 = 83
        assert score == 83


# ---------------------------------------------------------------------------
# derive.py — _build_enhanced_precedent_analysis with v3 data
# ---------------------------------------------------------------------------

def _import_build_enhanced():
    from routers.report.derive import _build_enhanced_precedent_analysis
    return _build_enhanced_precedent_analysis


class TestEnhancedPrecedentV3:
    def _make_v3_analysis(self):
        return {
            "available": True,
            "scoring_version": "v3",
            "match_count": 10,
            "supporting_precedents": 7,
            "contrary_precedents": 2,
            "neutral_precedents": 1,
            "match_outcome_distribution": {"ALLOW": 7, "BLOCK": 2, "EDD": 1},
            "raw_overlap_count": 20,
            "raw_outcome_distribution": {"ALLOW": 12, "BLOCK": 5, "EDD": 3},
            "confidence_dimensions": [
                {"name": "pool_adequacy", "value": 10, "level": "MODERATE", "bottleneck": False, "note": ""},
                {"name": "similarity_quality", "value": 0.78, "level": "HIGH", "bottleneck": False, "note": ""},
                {"name": "outcome_consistency", "value": 0.80, "level": "HIGH", "bottleneck": False, "note": ""},
                {"name": "evidence_completeness", "value": 0.65, "level": "LOW", "bottleneck": True, "note": "3 required fields missing"},
            ],
            "confidence_level": "LOW",
            "confidence_bottleneck": "evidence_completeness",
            "confidence_hard_rule": None,
            "non_transferable_count": 1,
            "sample_cases": [
                {
                    "precedent_id": "abc12345...",
                    "similarity_pct": 85,
                    "classification": "supporting",
                    "outcome": "allow",
                    "outcome_label": "ALLOW — NO REPORT",
                    "disposition": "ALLOW",
                    "disposition_basis": "DISCRETIONARY",
                    "reporting": "NO_REPORT",
                    "reason_codes": ["RC-MON-001"],
                    "appealed": False,
                    "appeal_outcome": None,
                    "code_similarity_pct": 80,
                    "fingerprint_similarity_pct": 70,
                    "field_scores": {"txn.type": 100, "customer.type": 100},
                    "non_transferable": False,
                    "non_transferable_reasons": [],
                    "matched_drivers": ["txn.type"],
                    "mismatched_drivers": [],
                },
                {
                    "precedent_id": "def67890...",
                    "similarity_pct": 62,
                    "classification": "neutral",
                    "outcome": "edd",
                    "outcome_label": "EDD — FURTHER REVIEW",
                    "disposition": "EDD",
                    "disposition_basis": "DISCRETIONARY",
                    "reporting": "UNKNOWN",
                    "reason_codes": ["RC-MON-002"],
                    "appealed": False,
                    "appeal_outcome": None,
                    "code_similarity_pct": 60,
                    "fingerprint_similarity_pct": 50,
                    "field_scores": {"txn.type": 100, "customer.type": 0},
                    "non_transferable": True,
                    "non_transferable_reasons": ["customer.type was a decision driver but is missing from current case"],
                    "matched_drivers": [],
                    "mismatched_drivers": ["customer.type"],
                },
            ],
        }

    def test_v3_includes_confidence_dimensions(self):
        build = _import_build_enhanced()
        analysis = self._make_v3_analysis()
        result = build(analysis, "ALLOW — NO REPORT", None)
        assert "confidence_dimensions" in result
        assert len(result["confidence_dimensions"]) == 4
        assert result["confidence_level"] == "LOW"
        assert result["confidence_bottleneck"] == "evidence_completeness"

    def test_v3_includes_non_transferable_explanations(self):
        build = _import_build_enhanced()
        analysis = self._make_v3_analysis()
        result = build(analysis, "ALLOW — NO REPORT", None)
        assert "non_transferable_explanations" in result
        assert len(result["non_transferable_explanations"]) == 1
        nt = result["non_transferable_explanations"][0]
        assert nt["precedent_id"] == "def67890..."
        assert len(nt["reasons"]) > 0

    def test_v3_includes_driver_causality(self):
        build = _import_build_enhanced()
        analysis = self._make_v3_analysis()
        result = build(analysis, "ALLOW — NO REPORT", None)
        assert "driver_causality" in result
        dc = result["driver_causality"]
        assert "txn.type" in dc["shared_drivers"]
        assert "customer.type" in dc["divergent_drivers"]

    def test_v2_data_no_v3_keys(self):
        """v2 analysis should NOT include v3-specific keys."""
        build = _import_build_enhanced()
        analysis = {
            "available": True,
            # No scoring_version → v2
            "match_count": 5,
            "supporting_precedents": 3,
            "contrary_precedents": 1,
            "neutral_precedents": 1,
            "match_outcome_distribution": {"ALLOW": 3, "BLOCK": 1, "EDD": 1},
            "raw_overlap_count": 10,
            "raw_outcome_distribution": {"ALLOW": 5, "BLOCK": 3, "EDD": 2},
            "sample_cases": [
                {
                    "precedent_id": "abc12345...",
                    "similarity_pct": 80,
                    "classification": "supporting",
                    "outcome": "allow",
                    "outcome_label": "ALLOW",
                    "disposition": "ALLOW",
                    "disposition_basis": "DISCRETIONARY",
                    "reporting": "NO_REPORT",
                    "reason_codes": ["RC-MON-001"],
                    "appealed": False,
                    "appeal_outcome": None,
                    "code_similarity_pct": 75,
                    "fingerprint_similarity_pct": 70,
                    "similarity_components": {"rules_overlap": 80, "gate_match": 100},
                },
            ],
        }
        result = build(analysis, "ALLOW — NO REPORT", None)
        # confidence_dimensions is now always present (4-factor model renders for all cases)
        assert result.get("confidence_dimensions") == []
        assert result.get("confidence_level") is None
        assert "non_transferable_explanations" not in result
        assert "driver_causality" not in result


# ---------------------------------------------------------------------------
# validate_output.py — v3 checks
# ---------------------------------------------------------------------------

def _import_check_precedent_quality():
    from validate_output import _check_precedent_quality
    return _check_precedent_quality


class TestValidateOutputV3:
    def test_hard_rule_warning(self):
        check = _import_check_precedent_quality()
        pack = {
            "precedent_analysis": {
                "available": True,
                "confidence_model_version": "v3",
                "confidence_level": "NONE",
                "confidence_hard_rule": "0 precedents above floor",
                "confidence_bottleneck": "pool_adequacy",
                "precedent_confidence": 0.0,
                "supporting_precedents": 0,
                "contrary_precedents": 0,
                "neutral_precedents": 0,
                "non_transferable_count": 0,
                "sample_cases": [],
            },
        }
        warnings = check(pack)
        hard_rule_warnings = [w for w in warnings if w["check"] == "PRECEDENT_HARD_RULE"]
        assert len(hard_rule_warnings) == 1
        assert "0 precedents above floor" in hard_rule_warnings[0]["message"]

    def test_non_transferable_info(self):
        check = _import_check_precedent_quality()
        pack = {
            "precedent_analysis": {
                "available": True,
                "confidence_model_version": "v3",
                "confidence_level": "HIGH",
                "confidence_hard_rule": None,
                "precedent_confidence": 0.75,
                "supporting_precedents": 5,
                "contrary_precedents": 0,
                "neutral_precedents": 2,
                "non_transferable_count": 3,
                "sample_cases": [],
            },
        }
        warnings = check(pack)
        nt_warnings = [w for w in warnings if w["check"] == "PRECEDENT_NON_TRANSFERABLE"]
        assert len(nt_warnings) == 1
        assert "3 precedent(s)" in nt_warnings[0]["message"]

    def test_v2_no_v3_checks(self):
        """v2 data should not trigger v3-specific checks."""
        check = _import_check_precedent_quality()
        pack = {
            "precedent_analysis": {
                "available": True,
                # No confidence_model_version → v2
                "precedent_confidence": 0.80,
                "decisive_total": 10,
                "supporting_precedents": 8,
                "contrary_precedents": 1,
                "neutral_precedents": 1,
                "sample_cases": [
                    {"similarity_pct": 85, "fingerprint_similarity_pct": 80},
                ],
            },
        }
        warnings = check(pack)
        v3_checks = [w for w in warnings if w["check"] in ("PRECEDENT_HARD_RULE", "PRECEDENT_NON_TRANSFERABLE")]
        assert len(v3_checks) == 0
