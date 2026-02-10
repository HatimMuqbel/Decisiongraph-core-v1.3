"""Tests for v3 Comparability Gate engine."""

import pytest

from decisiongraph.banking_domain import create_banking_domain_registry
from decisiongraph.comparability_gate import (
    GateResult,
    evaluate_gates,
    extract_gate_facts_from_case,
    extract_gate_facts_from_precedent,
)
from decisiongraph.domain_registry import ComparabilityGate, DomainRegistry


# ---------------------------------------------------------------------------
# evaluate_gates — basic tests
# ---------------------------------------------------------------------------

class TestEvaluateGates:
    @pytest.fixture
    def simple_domain(self) -> DomainRegistry:
        return DomainRegistry(
            domain="test",
            version="1.0",
            fields={},
            comparability_gates=[
                ComparabilityGate(
                    field="jurisdiction",
                    equivalence_classes={
                        "CA": ["CA", "CA-ON"],
                        "US": ["US", "US-NY"],
                    },
                ),
                ComparabilityGate(
                    field="segment",
                    equivalence_classes={
                        "retail": ["individual", "personal"],
                        "corporate": ["corporation"],
                    },
                ),
            ],
        )

    def test_all_pass(self, simple_domain):
        passed, results = evaluate_gates(
            simple_domain,
            {"jurisdiction": "CA", "segment": "individual"},
            {"jurisdiction": "CA-ON", "segment": "personal"},
        )
        assert passed is True
        assert len(results) == 2
        assert all(r.passed for r in results)

    def test_one_fails(self, simple_domain):
        passed, results = evaluate_gates(
            simple_domain,
            {"jurisdiction": "CA", "segment": "individual"},
            {"jurisdiction": "US", "segment": "personal"},
        )
        assert passed is False
        # jurisdiction fails, segment passes
        assert results[0].passed is False
        assert results[1].passed is True

    def test_all_fail(self, simple_domain):
        passed, results = evaluate_gates(
            simple_domain,
            {"jurisdiction": "CA", "segment": "individual"},
            {"jurisdiction": "US", "segment": "corporation"},
        )
        assert passed is False

    def test_missing_field_fallback(self, simple_domain):
        """Missing gate field uses broadest class as fallback."""
        passed, results = evaluate_gates(
            simple_domain,
            {"segment": "individual"},  # jurisdiction missing
            {"jurisdiction": "CA", "segment": "personal"},
        )
        # Fallback to broadest class — jurisdiction has CA=[CA,CA-ON] (2 members)
        # and US=[US,US-NY] (2 members). Both are tied, so max() picks one.
        # Regardless, the precedent's CA class may or may not match the fallback.
        assert any(r.fallback_used for r in results)
        assert any(r.warning for r in results)

    def test_classes_in_result(self, simple_domain):
        _, results = evaluate_gates(
            simple_domain,
            {"jurisdiction": "CA", "segment": "individual"},
            {"jurisdiction": "CA-ON", "segment": "personal"},
        )
        assert results[0].case_class == "CA"
        assert results[0].precedent_class == "CA"
        assert results[1].case_class == "retail"
        assert results[1].precedent_class == "retail"


# ---------------------------------------------------------------------------
# evaluate_gates — banking domain
# ---------------------------------------------------------------------------

class TestBankingGates:
    @pytest.fixture
    def registry(self) -> DomainRegistry:
        return create_banking_domain_registry()

    def test_same_regime_same_segment(self, registry):
        """CA retail wire vs CA retail eft — should pass all gates."""
        case = {
            "jurisdiction_regime": "CA",
            "customer_segment": "individual",
            "channel_family": "wire_domestic",
            "disposition_basis": "DISCRETIONARY",
        }
        prec = {
            "jurisdiction_regime": "CA-ON",
            "customer_segment": "personal",
            "channel_family": "eft",
            "disposition_basis": "DISCRETIONARY",
        }
        passed, results = evaluate_gates(registry, case, prec)
        assert passed is True

    def test_cross_regime_blocked(self, registry):
        """CA vs US — jurisdiction gate blocks."""
        case = {
            "jurisdiction_regime": "CA",
            "customer_segment": "individual",
            "channel_family": "cash",
            "disposition_basis": "DISCRETIONARY",
        }
        prec = {
            "jurisdiction_regime": "US",
            "customer_segment": "individual",
            "channel_family": "cash",
            "disposition_basis": "DISCRETIONARY",
        }
        passed, _ = evaluate_gates(registry, case, prec)
        assert passed is False

    def test_cross_basis_blocked_inv008(self, registry):
        """MANDATORY vs DISCRETIONARY — INV-008: never comparable."""
        case = {
            "jurisdiction_regime": "CA",
            "customer_segment": "individual",
            "channel_family": "cash",
            "disposition_basis": "MANDATORY",
        }
        prec = {
            "jurisdiction_regime": "CA",
            "customer_segment": "individual",
            "channel_family": "cash",
            "disposition_basis": "DISCRETIONARY",
        }
        passed, results = evaluate_gates(registry, case, prec)
        assert passed is False
        # The disposition_basis gate should be the one that failed
        basis_result = next(r for r in results if r.gate_field == "disposition_basis")
        assert basis_result.passed is False

    def test_cross_segment_blocked(self, registry):
        """Retail vs corporate — customer segment gate blocks."""
        case = {
            "jurisdiction_regime": "CA",
            "customer_segment": "individual",
            "channel_family": "cash",
            "disposition_basis": "DISCRETIONARY",
        }
        prec = {
            "jurisdiction_regime": "CA",
            "customer_segment": "corporation",
            "channel_family": "cash",
            "disposition_basis": "DISCRETIONARY",
        }
        passed, _ = evaluate_gates(registry, case, prec)
        assert passed is False

    def test_cross_channel_blocked(self, registry):
        """Cash vs crypto — channel family gate blocks."""
        case = {
            "jurisdiction_regime": "CA",
            "customer_segment": "individual",
            "channel_family": "cash",
            "disposition_basis": "DISCRETIONARY",
        }
        prec = {
            "jurisdiction_regime": "CA",
            "customer_segment": "individual",
            "channel_family": "crypto",
            "disposition_basis": "DISCRETIONARY",
        }
        passed, _ = evaluate_gates(registry, case, prec)
        assert passed is False

    def test_same_channel_family_different_types(self, registry):
        """wire_domestic and eft are both electronic — should pass."""
        case = {
            "jurisdiction_regime": "CA",
            "customer_segment": "individual",
            "channel_family": "wire_domestic",
            "disposition_basis": "DISCRETIONARY",
        }
        prec = {
            "jurisdiction_regime": "CA",
            "customer_segment": "individual",
            "channel_family": "eft",
            "disposition_basis": "DISCRETIONARY",
        }
        passed, _ = evaluate_gates(registry, case, prec)
        assert passed is True


# ---------------------------------------------------------------------------
# extract_gate_facts helpers
# ---------------------------------------------------------------------------

class TestExtractGateFacts:
    def test_case_extraction(self):
        facts = extract_gate_facts_from_case(
            {"customer.type": "individual", "txn.type": "cash"},
            jurisdiction="CA",
            disposition_basis="DISCRETIONARY",
        )
        assert facts["jurisdiction_regime"] == "CA"
        assert facts["customer_segment"] == "individual"
        assert facts["channel_family"] == "cash"
        assert facts["disposition_basis"] == "DISCRETIONARY"

    def test_precedent_extraction(self):
        facts = extract_gate_facts_from_precedent(
            {"customer.type": "corporation", "txn.type": "wire_domestic"},
            jurisdiction_code="CA-ON",
            disposition_basis="MANDATORY",
        )
        assert facts["jurisdiction_regime"] == "CA-ON"
        assert facts["customer_segment"] == "corporation"
        assert facts["channel_family"] == "wire_domestic"
        assert facts["disposition_basis"] == "MANDATORY"

    def test_fallback_to_case_facts(self):
        facts = extract_gate_facts_from_case(
            {"customer.type": "individual", "txn.type": "eft", "jurisdiction": "CA"},
        )
        assert facts["jurisdiction_regime"] == "CA"
