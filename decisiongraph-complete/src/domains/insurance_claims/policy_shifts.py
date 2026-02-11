"""
Insurance Claims Policy Shift Projections
==========================================
Re-evaluates existing insurance seeds under 3 policy changes
and produces shadow records showing before/after outcomes.

Modeled on domains/banking_aml/policy_shifts.py.

Shifts:
  1. FSRA Minor Injury Cap Increase ($3,500 → $5,000)
  2. Fraud Ring Detection Tightened (mandatory SIU referral)
  3. Climate Event Coverage Expansion (expedited processing)
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date as _date
from typing import Any
from uuid import uuid4


# ---------------------------------------------------------------------------
# Helper: deterministic SHA-256 hash
# ---------------------------------------------------------------------------

def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Helper: extract an anchor-fact value from a seed
# ---------------------------------------------------------------------------

def _seed_fact(seed: dict, field_id: str) -> Any:
    """Return ``value`` for *field_id* in *seed* anchor_facts, or ``None``."""
    for f in seed.get("anchor_facts", []):
        if f.get("field_id") == field_id:
            return f.get("value")
    return None


# ---------------------------------------------------------------------------
# Affect predicates
# ---------------------------------------------------------------------------

def _affects_fsra_threshold(seed: dict) -> bool:
    """Auto injury claim with minor injury type."""
    coverage = _seed_fact(seed, "claim.coverage_line")
    injury = _seed_fact(seed, "claim.injury_type")
    return coverage == "auto" and injury == "minor"


def _affects_fraud_ring(seed: dict) -> bool:
    """Staged accident or fraud indicator with inconsistent statements."""
    staged = _seed_fact(seed, "flag.staged_accident")
    fraud = _seed_fact(seed, "flag.fraud_indicator")
    inconsistent = _seed_fact(seed, "flag.inconsistent_statements")
    return staged is True or (fraud is True and inconsistent is True)


def _affects_climate_event(seed: dict) -> bool:
    """Property claim with natural disaster cause (water/wind/fire)."""
    coverage = _seed_fact(seed, "claim.coverage_line")
    cause = _seed_fact(seed, "claim.loss_cause")
    return coverage == "property" and cause in ("water", "wind", "fire")


# ---------------------------------------------------------------------------
# New-outcome derivers
# ---------------------------------------------------------------------------

def _new_outcome_fsra(
    _seed: dict, old_outcome: dict
) -> tuple[dict, str | None]:
    """FSRA minor injury cap raised → more claims qualify for PAY_CLAIM."""
    new = {**old_outcome, "disposition": "PAY_CLAIM", "reporting": "NO_FILING"}
    return new, None


def _new_outcome_fraud_ring(
    _seed: dict, old_outcome: dict
) -> tuple[dict, str]:
    """Fraud ring tightened → mandatory SIU referral."""
    new = {
        "disposition": "REFER_SIU",
        "disposition_basis": "MANDATORY",
        "reporting": "FRAUD_REPORT",
    }
    return new, "siu_investigator"


def _new_outcome_climate(
    _seed: dict, old_outcome: dict
) -> tuple[dict, str | None]:
    """Climate event → expedited PAY_CLAIM processing."""
    new = {**old_outcome, "disposition": "PAY_CLAIM", "reporting": "FSRA_NOTICE"}
    return new, None


# ---------------------------------------------------------------------------
# Signal extraction — domain-portable signal names from case facts
# ---------------------------------------------------------------------------

def extract_case_signals(case_facts: dict) -> list[str]:
    """Extract domain-portable signal names from insurance case facts."""
    signals: list[str] = []

    coverage = case_facts.get("claim.coverage_line", "")
    injury = case_facts.get("claim.injury_type", "")
    cause = case_facts.get("claim.loss_cause", "")

    # Auto injury signals
    if coverage == "auto" and injury == "minor":
        signals.append("AUTO_INJURY_CLAIM")
        signals.append("MINOR_INJURY")

    # Fraud signals
    if case_facts.get("flag.staged_accident"):
        signals.append("STAGED_ACCIDENT")
    if case_facts.get("flag.fraud_indicator") and case_facts.get("flag.inconsistent_statements"):
        signals.append("FRAUD_RING_LINK")

    # Climate signals
    if coverage == "property" and cause in ("water", "wind", "fire"):
        signals.append("CLIMATE_EVENT")
        signals.append("PROPERTY_DAMAGE")

    # SIU signals
    if case_facts.get("screening.siu_referral"):
        signals.append("SIU_REFERRAL")

    # High value
    if case_facts.get("claim.amount_band") in ("100k_500k", "over_500k"):
        signals.append("HIGH_VALUE_CLAIM")

    return signals


# ---------------------------------------------------------------------------
# Policy Shift Definitions
# ---------------------------------------------------------------------------

POLICY_SHIFTS: list[dict[str, Any]] = [
    {
        "id": "fsra_minor_injury_cap",
        "name": "FSRA Minor Injury Cap Increase",
        "description": "$3,500 → $5,000 minor injury cap",
        "policy_version": "2026.04.01",
        "citation": "FSRA Bulletin 2026-A01",
        "trigger_signals": ["AUTO_INJURY_CLAIM", "MINOR_INJURY"],
        "rule_change": {
            "rule_id": "MINOR_INJURY_CAP",
            "before": {"minor_injury_cap": 3500},
            "after": {"minor_injury_cap": 5000},
        },
        "_affects": _affects_fsra_threshold,
        "_new_outcome": _new_outcome_fsra,
    },
    {
        "id": "fraud_ring_detection",
        "name": "Fraud Ring Detection Tightened",
        "description": "Mandatory SIU referral for fraud ring patterns",
        "policy_version": "2026.06.01",
        "citation": "IBC Fraud Prevention Directive 2026-FP-03",
        "trigger_signals": ["FRAUD_RING_LINK", "STAGED_ACCIDENT"],
        "rule_change": {
            "rule_id": "FRAUD_RING_SIU",
            "before": {"fraud_pattern_action": "investigate"},
            "after": {"fraud_pattern_action": "mandatory_siu_referral"},
        },
        "_affects": _affects_fraud_ring,
        "_new_outcome": _new_outcome_fraud_ring,
    },
    {
        "id": "climate_event_coverage",
        "name": "Climate Event Coverage Expansion",
        "description": "Expedited processing for declared climate events",
        "policy_version": "2026.07.01",
        "citation": "FSRA Climate Adaptation Framework 2026-CA-01",
        "trigger_signals": ["CLIMATE_EVENT", "PROPERTY_DAMAGE"],
        "rule_change": {
            "rule_id": "CLIMATE_EVENT_PROCESSING",
            "before": {"climate_processing": "standard"},
            "after": {"climate_processing": "expedited", "coverage_limit_boost": True},
        },
        "_affects": _affects_climate_event,
        "_new_outcome": _new_outcome_climate,
    },
]

# ---------------------------------------------------------------------------
# Parsed effective dates for temporal partitioning
# ---------------------------------------------------------------------------

SHIFT_EFFECTIVE_DATES: dict[str, _date] = {
    shift["id"]: _date(*[int(p) for p in shift["policy_version"].split(".")])
    for shift in POLICY_SHIFTS
}


# ---------------------------------------------------------------------------
# Public helpers for regime detection
# ---------------------------------------------------------------------------

def _case_facts_to_seed_like(case_facts: dict) -> dict:
    """Convert flat ``{field_id: value}`` dict to seed-like format for _affects_* predicates."""
    return {
        "anchor_facts": [
            {"field_id": k, "value": v}
            for k, v in case_facts.items()
        ]
    }


def detect_applicable_shifts(
    case_signals: list[str] | None = None,
    case_facts: dict | None = None,
) -> list[dict]:
    """Return serializable metadata for each shift that affects the case."""
    seed_like = _case_facts_to_seed_like(case_facts) if case_facts else None
    applicable = []

    for shift in POLICY_SHIFTS:
        trigger_signals = shift.get("trigger_signals", [])

        if case_signals is not None and trigger_signals:
            if not any(sig in case_signals for sig in trigger_signals):
                continue
            if seed_like is not None and not shift["_affects"](seed_like):
                continue
        elif seed_like is not None:
            if not shift["_affects"](seed_like):
                continue
        else:
            continue

        meta = {k: v for k, v in shift.items() if not k.startswith("_")}
        meta["effective_date"] = SHIFT_EFFECTIVE_DATES[shift["id"]].isoformat()
        applicable.append(meta)

    applicable.sort(key=lambda s: s["effective_date"])
    return applicable


def compute_shadow_outcome(case_facts: dict, shift_id: str) -> dict | None:
    """Compute post-shift outcome for *case_facts* under *shift_id*."""
    seed_like = _case_facts_to_seed_like(case_facts)
    for shift in POLICY_SHIFTS:
        if shift["id"] != shift_id:
            continue
        if not shift["_affects"](seed_like):
            return None
        old_outcome: dict = {}
        new_outcome, new_level = shift["_new_outcome"](seed_like, old_outcome)
        result = dict(new_outcome)
        if new_level:
            result["decision_level"] = new_level
        return result
    return None


# ---------------------------------------------------------------------------
# Change-type classification
# ---------------------------------------------------------------------------

_DISP_SEVERITY = {"PAY_CLAIM": 0, "PARTIAL_PAY": 1, "INVESTIGATE": 2, "REFER_SIU": 3, "DENY_CLAIM": 4}


def _determine_change_type(outcome_before: dict, outcome_after: dict) -> str:
    d_before = _DISP_SEVERITY.get(outcome_before.get("disposition", ""), 0)
    d_after = _DISP_SEVERITY.get(outcome_after.get("disposition", ""), 0)
    if d_after > d_before:
        return "escalation"
    if d_after < d_before:
        return "de_escalation"
    if outcome_before.get("reporting") != outcome_after.get("reporting"):
        return "reporting_change"
    return "decision_level_change"


# ---------------------------------------------------------------------------
# Shadow-record builder
# ---------------------------------------------------------------------------

def _build_shadow(seed: dict, shift: dict, outcome_after: dict, decision_level_after: str) -> dict:
    outcome_before = seed.get("outcome", {})
    decision_level_before = seed.get("decision_level", "adjuster")

    return {
        "shadow_id": str(uuid4()),
        "original_precedent_id": seed.get("precedent_id"),
        "policy_shift_id": shift["id"],
        "policy_version_before": "2026.01.01",
        "policy_version_after": shift["policy_version"],
        "rule_id_changed": shift["rule_change"]["rule_id"],
        "rule_hash_before": _sha256(json.dumps(shift["rule_change"]["before"], sort_keys=True)),
        "rule_hash_after": _sha256(json.dumps(shift["rule_change"]["after"], sort_keys=True)),
        "outcome_before": deepcopy(outcome_before),
        "outcome_after": deepcopy(outcome_after),
        "decision_level_before": decision_level_before,
        "decision_level_after": decision_level_after,
        "change_type": _determine_change_type(outcome_before, outcome_after),
        "change_description": shift["description"],
        "citation": shift["citation"],
        "shadow": True,
        "namespace": "shadow/policy_impact",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_policy_shift_shadows(seeds: list[dict]) -> dict[str, list[dict]]:
    """Apply all 3 policy shifts against *seeds* and return shadow records."""
    result: dict[str, list[dict]] = {}

    for shift in POLICY_SHIFTS:
        shift_id = shift["id"]
        affects_fn = shift["_affects"]
        outcome_fn = shift["_new_outcome"]
        shadows: list[dict] = []

        for seed in seeds:
            if not affects_fn(seed):
                continue
            old_outcome = seed.get("outcome", {})
            new_outcome, new_level = outcome_fn(seed, old_outcome)
            if new_level is None:
                new_level = seed.get("decision_level", "adjuster")
            shadow = _build_shadow(seed, shift, new_outcome, new_level)
            shadows.append(shadow)

        result[shift_id] = shadows

    return result


def get_shift_metadata(shift_id: str) -> dict | None:
    for shift in POLICY_SHIFTS:
        if shift["id"] == shift_id:
            return {k: v for k, v in shift.items() if not k.startswith("_")}
    return None


__all__ = [
    "POLICY_SHIFTS",
    "SHIFT_EFFECTIVE_DATES",
    "extract_case_signals",
    "detect_applicable_shifts",
    "compute_shadow_outcome",
    "generate_policy_shift_shadows",
    "get_shift_metadata",
]
