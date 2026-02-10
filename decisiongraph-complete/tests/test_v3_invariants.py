"""Tests for v3 invariants (INV-010 through INV-012)."""

import sys
from pathlib import Path

import pytest

# Add service to path so we can import main.py
sys.path.insert(0, str(Path(__file__).parent.parent / "service"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ---------------------------------------------------------------------------
# We test check_precedent_invariants directly with crafted dicts,
# no need to spin up the full FastAPI service.
# ---------------------------------------------------------------------------

def _import_invariant_checker():
    """Import check_precedent_invariants from main module."""
    from main import check_precedent_invariants
    return check_precedent_invariants


# ---------------------------------------------------------------------------
# INV-010: No hardcoded fallback confidence in v3
# ---------------------------------------------------------------------------

class TestINV010:
    def test_v3_confidence_0_5_not_moderate_violates(self):
        check = _import_invariant_checker()
        analysis = {
            "available": True,
            "scoring_version": "v3",
            "confidence_model_version": "v3",
            "precedent_confidence": 0.5,
            "confidence_level": "LOW",  # 0.5 maps to MODERATE, but level says LOW
            "proposed_canonical": {
                "disposition": "ALLOW",
                "disposition_basis": "DISCRETIONARY",
                "reporting": "NO_REPORT",
            },
            "sample_cases": [],
        }
        violations = check(analysis, "test-decision-001")
        inv010 = [v for v in violations if v["invariant"] == "INV-010"]
        assert len(inv010) == 1

    def test_v3_confidence_0_5_with_moderate_is_ok(self):
        check = _import_invariant_checker()
        analysis = {
            "available": True,
            "scoring_version": "v3",
            "confidence_model_version": "v3",
            "precedent_confidence": 0.5,
            "confidence_level": "MODERATE",  # 0.5 correctly maps to MODERATE
            "proposed_canonical": {
                "disposition": "ALLOW",
                "disposition_basis": "DISCRETIONARY",
                "reporting": "NO_REPORT",
            },
            "sample_cases": [],
        }
        violations = check(analysis, "test-decision-002")
        inv010 = [v for v in violations if v["invariant"] == "INV-010"]
        assert len(inv010) == 0

    def test_v2_not_checked(self):
        """v2 scoring should not trigger INV-010."""
        check = _import_invariant_checker()
        analysis = {
            "available": True,
            # No scoring_version key → v2
            "precedent_confidence": 0.5,
            "proposed_canonical": {
                "disposition": "ALLOW",
                "disposition_basis": "DISCRETIONARY",
                "reporting": "NO_REPORT",
            },
            "sample_cases": [],
        }
        violations = check(analysis, "test-decision-003")
        inv010 = [v for v in violations if v["invariant"] == "INV-010"]
        assert len(inv010) == 0


# ---------------------------------------------------------------------------
# INV-011: Non-transferable cannot be supporting
# ---------------------------------------------------------------------------

class TestINV011:
    def test_non_transferable_supporting_violates(self):
        check = _import_invariant_checker()
        analysis = {
            "available": True,
            "scoring_version": "v3",
            "proposed_canonical": {
                "disposition": "ALLOW",
                "disposition_basis": "DISCRETIONARY",
                "reporting": "NO_REPORT",
            },
            "sample_cases": [
                {
                    "precedent_id": "abc12345...",
                    "non_transferable": True,
                    "classification": "supporting",  # VIOLATION
                    "disposition": "ALLOW",
                    "disposition_basis": "DISCRETIONARY",
                },
            ],
        }
        violations = check(analysis, "test-decision-004")
        inv011 = [v for v in violations if v["invariant"] == "INV-011"]
        assert len(inv011) == 1

    def test_non_transferable_neutral_ok(self):
        check = _import_invariant_checker()
        analysis = {
            "available": True,
            "scoring_version": "v3",
            "proposed_canonical": {
                "disposition": "ALLOW",
                "disposition_basis": "DISCRETIONARY",
                "reporting": "NO_REPORT",
            },
            "sample_cases": [
                {
                    "precedent_id": "abc12345...",
                    "non_transferable": True,
                    "classification": "neutral",  # OK
                    "disposition": "ALLOW",
                    "disposition_basis": "DISCRETIONARY",
                },
            ],
        }
        violations = check(analysis, "test-decision-005")
        inv011 = [v for v in violations if v["invariant"] == "INV-011"]
        assert len(inv011) == 0


# ---------------------------------------------------------------------------
# INV-012: Below-floor precedent cannot appear in scored pool
# ---------------------------------------------------------------------------

class TestINV012:
    def test_below_floor_violates(self):
        check = _import_invariant_checker()
        analysis = {
            "available": True,
            "scoring_version": "v3",
            "similarity_floor_used": 0.60,
            "proposed_canonical": {
                "disposition": "ALLOW",
                "disposition_basis": "DISCRETIONARY",
                "reporting": "NO_REPORT",
            },
            "sample_cases": [
                {
                    "precedent_id": "abc12345...",
                    "similarity_pct": 55,  # Below 60% floor → VIOLATION
                    "classification": "supporting",
                    "disposition": "ALLOW",
                    "disposition_basis": "DISCRETIONARY",
                },
            ],
        }
        violations = check(analysis, "test-decision-006")
        inv012 = [v for v in violations if v["invariant"] == "INV-012"]
        assert len(inv012) == 1

    def test_at_floor_ok(self):
        check = _import_invariant_checker()
        analysis = {
            "available": True,
            "scoring_version": "v3",
            "similarity_floor_used": 0.60,
            "proposed_canonical": {
                "disposition": "ALLOW",
                "disposition_basis": "DISCRETIONARY",
                "reporting": "NO_REPORT",
            },
            "sample_cases": [
                {
                    "precedent_id": "abc12345...",
                    "similarity_pct": 60,  # At floor → OK
                    "classification": "supporting",
                    "disposition": "ALLOW",
                    "disposition_basis": "DISCRETIONARY",
                },
            ],
        }
        violations = check(analysis, "test-decision-007")
        inv012 = [v for v in violations if v["invariant"] == "INV-012"]
        assert len(inv012) == 0


# ---------------------------------------------------------------------------
# Existing invariants still work with v3 data
# ---------------------------------------------------------------------------

class TestExistingInvariantsWithV3:
    def test_inv003_unknown_with_v3(self):
        """UNKNOWN disposition classified as supporting → still a violation in v3."""
        check = _import_invariant_checker()
        analysis = {
            "available": True,
            "scoring_version": "v3",
            "proposed_canonical": {
                "disposition": "ALLOW",
                "disposition_basis": "DISCRETIONARY",
                "reporting": "NO_REPORT",
            },
            "sample_cases": [
                {
                    "precedent_id": "abc12345...",
                    "disposition": "UNKNOWN",
                    "classification": "supporting",
                    "disposition_basis": "DISCRETIONARY",
                },
            ],
        }
        violations = check(analysis, "test-decision-008")
        inv003 = [v for v in violations if v["invariant"] == "INV-003"]
        assert len(inv003) == 1

    def test_clean_v3_no_violations(self):
        """Well-formed v3 data should produce 0 violations."""
        check = _import_invariant_checker()
        analysis = {
            "available": True,
            "scoring_version": "v3",
            "confidence_model_version": "v3",
            "precedent_confidence": 0.75,
            "confidence_level": "HIGH",
            "similarity_floor_used": 0.60,
            "proposed_canonical": {
                "disposition": "ALLOW",
                "disposition_basis": "DISCRETIONARY",
                "reporting": "NO_REPORT",
            },
            "sample_cases": [
                {
                    "precedent_id": "abc12345...",
                    "similarity_pct": 85,
                    "classification": "supporting",
                    "disposition": "ALLOW",
                    "disposition_basis": "DISCRETIONARY",
                    "non_transferable": False,
                },
                {
                    "precedent_id": "def67890...",
                    "similarity_pct": 72,
                    "classification": "neutral",
                    "disposition": "EDD",
                    "disposition_basis": "DISCRETIONARY",
                    "non_transferable": False,
                },
            ],
        }
        violations = check(analysis, "test-decision-009")
        assert len(violations) == 0
