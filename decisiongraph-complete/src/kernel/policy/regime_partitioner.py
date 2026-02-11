"""
Regime Partitioner — universal signal extraction and shift detection.
=====================================================================
Extracted from decisiongraph.policy_shift_shadows: only the domain-portable
logic for signal extraction and applicable-shift detection.

Domain-specific shift definitions (POLICY_SHIFTS, _affects predicates, etc.)
remain in their respective domain modules.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Disposition severity — universal across all decision domains
# ---------------------------------------------------------------------------

DISP_SEVERITY: dict[str, int] = {"ALLOW": 0, "EDD": 1, "BLOCK": 2}


# ---------------------------------------------------------------------------
# Signal extraction — domain-portable signal names from case facts
# ---------------------------------------------------------------------------

def extract_case_signals(case_facts: dict) -> list[str]:
    """Extract domain-portable signal names from case facts.

    These signals form the universal language for policy shift matching.
    Banking signals trigger banking shifts; insurance signals (future)
    would trigger insurance shifts — the kernel mechanism is identical.
    """
    signals: list[str] = []
    txn_type = case_facts.get("txn.type", "")
    amount_band = case_facts.get("txn.amount_band", "")

    # Virtual asset signals
    if txn_type in ("crypto", "crypto_purchase", "crypto_sale"):
        signals.append("VIRTUAL_ASSET_TRANSACTION")
        if case_facts.get("flag.layering") or case_facts.get("flag.structuring"):
            signals.append("VIRTUAL_ASSET_LAUNDERING")

    # PEP signals
    if case_facts.get("customer.pep") or case_facts.get("screening.pep_match"):
        signals.append("PEP_MATCH")
        if (case_facts.get("customer.high_risk_jurisdiction")
                or case_facts.get("txn.destination_country_risk") == "high"):
            signals.append("PEP_FOREIGN_DOMESTIC")

    # Value signals
    if amount_band in ("25k_100k", "100k_500k", "500k_1m", "over_1m"):
        signals.append("HIGH_VALUE")

    # Cash signals
    if txn_type in ("cash", "cash_deposit", "cash_withdrawal"):
        if amount_band == "3k_10k":
            signals.append("LARGE_CASH_TRANSACTION")

    # Cross-border signal
    if case_facts.get("txn.cross_border"):
        signals.append("CROSS_BORDER")

    # Structuring signals
    if case_facts.get("flag.structuring"):
        signals.append("STRUCTURING_PATTERN")
    if (case_facts.get("txn.just_below_threshold")
            and case_facts.get("txn.multiple_same_day")):
        signals.append("THRESHOLD_AVOIDANCE")

    return signals


# ---------------------------------------------------------------------------
# Helper: convert flat facts to seed-like format for _affects predicates
# ---------------------------------------------------------------------------

def _case_facts_to_seed_like(case_facts: dict) -> dict:
    """Convert flat ``{field_id: value}`` dict to seed-like format."""
    return {
        "anchor_facts": [
            {"field_id": k, "value": v}
            for k, v in case_facts.items()
        ]
    }


# ---------------------------------------------------------------------------
# Universal shift detection — domain-portable mechanism
# ---------------------------------------------------------------------------

def detect_applicable_shifts(
    shifts: list[dict[str, Any]],
    shift_effective_dates: dict[str, Any],
    case_signals: list[str] | None = None,
    case_facts: dict | None = None,
) -> list[dict]:
    """Return serializable metadata for each shift that affects the case.

    Uses signal-based matching when *case_signals* provided (domain-portable).
    Falls back to field-based matching via *case_facts* (backward compat).
    When both are provided, signal matching is primary with field validation.

    Parameters
    ----------
    shifts : list[dict]
        Domain-specific shift definitions (e.g. banking POLICY_SHIFTS).
    shift_effective_dates : dict[str, date]
        Mapping of shift_id → effective date.
    case_signals : list[str] | None
        Signal names extracted from case facts.
    case_facts : dict | None
        Raw case facts for fallback field-based matching.
    """
    seed_like = _case_facts_to_seed_like(case_facts) if case_facts else None
    applicable = []

    for shift in shifts:
        trigger_signals = shift.get("trigger_signals", [])

        if case_signals is not None and trigger_signals:
            # Signal-based matching (domain-portable)
            if not any(sig in case_signals for sig in trigger_signals):
                continue
            # When case_facts also provided, validate with _affects for precision
            if seed_like is not None and not shift["_affects"](seed_like):
                continue
        elif seed_like is not None:
            # Fallback: field-based matching only (backward compat)
            if not shift["_affects"](seed_like):
                continue
        else:
            continue

        meta = {k: v for k, v in shift.items() if not k.startswith("_")}
        meta["effective_date"] = shift_effective_dates[shift["id"]].isoformat()
        applicable.append(meta)

    applicable.sort(key=lambda s: s["effective_date"])
    return applicable


# ---------------------------------------------------------------------------
# Change-type classification — universal across all domains
# ---------------------------------------------------------------------------

def determine_change_type(
    outcome_before: dict, outcome_after: dict,
) -> str:
    """Classify the nature of a policy shift.

    Returns one of:
    * ``escalation``   – disposition became more severe
    * ``de_escalation`` – disposition became less severe
    * ``reporting_change`` – same disposition, different reporting
    * ``decision_level_change`` – same disposition + reporting, different level
    * ``no_change`` – nothing changed
    """
    d_before = DISP_SEVERITY.get(outcome_before.get("disposition", ""), 0)
    d_after = DISP_SEVERITY.get(outcome_after.get("disposition", ""), 0)
    if d_after > d_before:
        return "escalation"
    if d_after < d_before:
        return "de_escalation"
    if outcome_before.get("reporting") != outcome_after.get("reporting"):
        return "reporting_change"
    return "decision_level_change"


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "DISP_SEVERITY",
    "extract_case_signals",
    "detect_applicable_shifts",
    "determine_change_type",
]
