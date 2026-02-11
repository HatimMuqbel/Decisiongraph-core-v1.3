"""
Comparability Gate Engine — v3 Precedent Engine Layer 1.

Evaluates all comparability gates defined in a DomainRegistry to determine
whether a precedent is comparable to the current case. Incomparable
precedents are excluded entirely — they are never scored.

Spec reference: DecisionGraph_Precedent_Engine_v3_Specification.md Section 4.

Gate rules:
  1. A precedent must match the case on ALL gates to enter the comparable pool.
  2. Matching uses equivalence classes — values within the same class are identical.
  3. MANDATORY and DISCRETIONARY are NEVER comparable (INV-008).
  4. Missing gate field → broadest class fallback + warning.
  5. Gates are defined in the DomainRegistry, not hardcoded.
  6. Excluded precedents do not exist for confidence calculations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from kernel.precedent.domain_registry import DomainRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gate result
# ---------------------------------------------------------------------------

@dataclass
class GateResult:
    """Result of evaluating a single comparability gate."""
    passed: bool
    gate_field: str
    case_class: str | None = None       # equivalence class the case falls into
    precedent_class: str | None = None   # equivalence class the precedent falls into
    fallback_used: bool = False          # True if missing field triggered broadest-class fallback
    warning: str | None = None


# ---------------------------------------------------------------------------
# Gate evaluation
# ---------------------------------------------------------------------------

def evaluate_gates(
    domain: DomainRegistry,
    case_facts: dict[str, Any],
    precedent_facts: dict[str, Any],
) -> tuple[bool, list[GateResult]]:
    """Evaluate all comparability gates for a case/precedent pair.

    Args:
        domain: The DomainRegistry containing gate definitions.
        case_facts: Dict of case field values (canonical names).
        precedent_facts: Dict of precedent field values (canonical names).

    Returns:
        (all_passed, results) where all_passed is True only if every gate passes.
    """
    results: list[GateResult] = []

    for gate in domain.comparability_gates:
        case_val = case_facts.get(gate.field)
        prec_val = precedent_facts.get(gate.field)

        # Classify both values
        case_class = gate.classify(case_val)
        prec_class = gate.classify(prec_val)

        fallback_used = False
        warning = None

        # Rule 4: missing field → broadest class fallback + warning
        if case_val is None and case_class is None:
            broadest = gate.broadest_class()
            case_class = broadest
            fallback_used = True
            warning = (
                f"Gate field '{gate.field}' missing from case; "
                f"using broadest class '{broadest}' as fallback"
            )
            logger.warning(warning)

        if prec_val is None and prec_class is None:
            broadest = gate.broadest_class()
            prec_class = broadest
            fallback_used = True
            w = (
                f"Gate field '{gate.field}' missing from precedent; "
                f"using broadest class '{broadest}' as fallback"
            )
            if warning:
                warning = f"{warning}; {w}"
            else:
                warning = w
            logger.warning(w)

        # Rule 2: values in the same class are identical.
        # If either side's class is still None after fallback (value present
        # but not in any equivalence class), the gate passes — we cannot
        # determine incomparability from an unclassifiable value.
        if case_class is None or prec_class is None:
            passed = True
            fallback_used = True
            w = (
                f"Gate field '{gate.field}' has unclassifiable value "
                f"(case={case_val}, prec={prec_val}); passing gate"
            )
            if warning:
                warning = f"{warning}; {w}"
            else:
                warning = w
        else:
            passed = case_class == prec_class

        results.append(GateResult(
            passed=passed,
            gate_field=gate.field,
            case_class=case_class,
            precedent_class=prec_class,
            fallback_used=fallback_used,
            warning=warning,
        ))

    # Rule 1: ALL gates must pass
    all_passed = all(r.passed for r in results)

    return all_passed, results


# ---------------------------------------------------------------------------
# Helper: extract gate-relevant facts from various input formats
# ---------------------------------------------------------------------------

def extract_gate_facts_from_case(
    case_facts: dict[str, Any],
    jurisdiction: str | None = None,
    disposition_basis: str | None = None,
) -> dict[str, Any]:
    """Build a gate-evaluation dict from case facts.

    Maps standard case fields to the virtual gate field names used by
    the banking AML comparability gates.
    """
    gate_facts: dict[str, Any] = {}

    # jurisdiction_regime — from explicit jurisdiction or case_facts
    gate_facts["jurisdiction_regime"] = (
        jurisdiction
        or case_facts.get("jurisdiction_regime")
        or case_facts.get("jurisdiction")
        or case_facts.get("jurisdiction_code")
    )

    # customer_segment — from customer.type
    gate_facts["customer_segment"] = case_facts.get("customer.type")

    # channel_family — from txn.type
    gate_facts["channel_family"] = case_facts.get("txn.type")

    # disposition_basis — explicit or from case_facts
    gate_facts["disposition_basis"] = (
        disposition_basis
        or case_facts.get("disposition_basis")
    )

    return gate_facts


def extract_gate_facts_from_precedent(
    anchor_facts: dict[str, Any],
    jurisdiction_code: str | None = None,
    disposition_basis: str | None = None,
) -> dict[str, Any]:
    """Build a gate-evaluation dict from precedent anchor facts."""
    gate_facts: dict[str, Any] = {}

    gate_facts["jurisdiction_regime"] = (
        jurisdiction_code
        or anchor_facts.get("jurisdiction_regime")
        or anchor_facts.get("jurisdiction")
        or anchor_facts.get("jurisdiction_code")
    )

    gate_facts["customer_segment"] = anchor_facts.get("customer.type")
    gate_facts["channel_family"] = anchor_facts.get("txn.type")

    gate_facts["disposition_basis"] = (
        disposition_basis
        or anchor_facts.get("disposition_basis")
    )

    return gate_facts


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "GateResult",
    "evaluate_gates",
    "extract_gate_facts_from_case",
    "extract_gate_facts_from_precedent",
]
