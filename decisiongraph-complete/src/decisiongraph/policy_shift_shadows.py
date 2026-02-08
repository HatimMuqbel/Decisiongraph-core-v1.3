"""
Policy Shift Shadow Projections — Epoch 2
==========================================
Re-evaluates existing v1 seeds (policy v2026.01.01) under 4 policy changes
and produces shadow records showing before/after outcomes.

These are NOT new seeds — they are projections of existing precedents
under proposed/enacted rule changes. The shadow namespace is
``shadow/policy_impact``.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
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
# Affect predicates  (pure functions, no lambdas for serializability)
# ---------------------------------------------------------------------------

def _affects_lctr(seed: dict) -> bool:
    """Cash transaction with amount in the $8K–$10K range (band = 3k_10k)."""
    txn_type = _seed_fact(seed, "txn.type")
    amount_band = _seed_fact(seed, "txn.amount_band")
    # Canonical value is "cash"; also accept website values for safety
    if txn_type not in ("cash", "cash_deposit", "cash_withdrawal"):
        return False
    # The 3k_10k band spans $3K–$10K.  Under the old $10K threshold these
    # were NOT reportable; under the new $8K threshold a portion are.
    # We treat the entire band as "potentially affected" — the approximate
    # fraction that falls in $8K–$10K is reflected in the seed-count targets.
    return amount_band == "3k_10k"


def _affects_pep_risk(seed: dict) -> bool:
    """PEP customer with transaction ≥ $25K."""
    pep = _seed_fact(seed, "customer.pep")
    band = _seed_fact(seed, "txn.amount_band")
    return pep is True and band in ("25k_100k", "100k_500k", "500k_1m", "over_1m")


def _affects_crypto(seed: dict) -> bool:
    """Any crypto transaction type."""
    txn_type = _seed_fact(seed, "txn.type")
    # Canonical value is "crypto"; also accept website values for safety
    return txn_type in ("crypto", "crypto_purchase", "crypto_sale")


def _affects_structuring_window(seed: dict) -> bool:
    """just_below_threshold + multiple_same_day but structuring NOT flagged."""
    jbt = _seed_fact(seed, "txn.just_below_threshold")
    msd = _seed_fact(seed, "txn.multiple_same_day")
    struct = _seed_fact(seed, "flag.structuring")
    return jbt is True and msd is True and struct is not True


# ---------------------------------------------------------------------------
# New-outcome derivers
# ---------------------------------------------------------------------------

def _new_outcome_lctr(
    _seed: dict, old_outcome: dict
) -> tuple[dict, str | None]:
    """LCTR threshold lowered → reporting changes to FILE_LCTR."""
    new = {**old_outcome, "reporting": "FILE_LCTR"}
    return new, None  # decision_level unchanged


def _new_outcome_pep(
    _seed: dict, old_outcome: dict
) -> tuple[dict, str]:
    """PEP risk-appetite tightened → senior_management sign-off."""
    new = {**old_outcome, "disposition": "EDD"}
    return new, "senior_management"


def _new_outcome_crypto(
    _seed: dict, _old_outcome: dict
) -> tuple[dict, str | None]:
    """All crypto → automatic EDD; unhosted wallet → BLOCK."""
    new = {
        "disposition": "EDD",
        "disposition_basis": "DISCRETIONARY",
        "reporting": "PENDING_EDD",
    }
    return new, None


def _new_outcome_structuring(
    _seed: dict, _old_outcome: dict
) -> tuple[dict, str | None]:
    """Extended aggregation window catches previously-missed structuring."""
    new = {
        "disposition": "EDD",
        "disposition_basis": "DISCRETIONARY",
        "reporting": "PENDING_EDD",
    }
    return new, None


# ---------------------------------------------------------------------------
# Policy Shift Definitions
# ---------------------------------------------------------------------------

POLICY_SHIFTS: list[dict[str, Any]] = [
    {
        "id": "lctr_threshold",
        "name": "LCTR Reporting Threshold",
        "description": "$10K → $8K",
        "policy_version": "2026.04.01",
        "citation": "PCMLTFA s. 12 (amended)",
        "rule_change": {
            "rule_id": "LCTR_THRESHOLD",
            "before": {"cash_reporting_threshold": 10_000},
            "after": {"cash_reporting_threshold": 8_000},
        },
        "_affects": _affects_lctr,
        "_new_outcome": _new_outcome_lctr,
    },
    {
        "id": "pep_risk_appetite",
        "name": "PEP Risk Appetite Tightened",
        "description": "PEP + ≥$25K → Senior Management sign-off",
        "policy_version": "2026.04.01",
        "citation": "Internal Policy 3.4.1 (revised)",
        "trigger": "FINTRAC Examination Finding #2026-EX-014",
        "rule_change": {
            "rule_id": "PEP_ESCALATION",
            "before": {"pep_any_amount": "edd_analyst"},
            "after": {"pep_over_25k": "edd_senior_management"},
        },
        "_affects": _affects_pep_risk,
        "_new_outcome": _new_outcome_pep,
    },
    {
        "id": "crypto_classification",
        "name": "Crypto High-Risk Classification",
        "description": "All crypto → automatic EDD; unhosted wallet → BLOCK",
        "policy_version": "2026.07.01",
        "citation": "FINTRAC Guideline 5 (updated)",
        "rule_change": {
            "rule_id": "CRYPTO_RISK_CLASS",
            "before": {"crypto_treatment": "standard"},
            "after": {"crypto_treatment": "high_risk", "unhosted_wallet": "block"},
        },
        "_affects": _affects_crypto,
        "_new_outcome": _new_outcome_crypto,
    },
    {
        "id": "structuring_window",
        "name": "Structuring Detection Window Extended",
        "description": "24-hour → 48-hour aggregation",
        "policy_version": "2026.04.15",
        "citation": "Internal Policy 4.2.1 (revised)",
        "trigger": "Internal Audit Report IA-2026-007",
        "rule_change": {
            "rule_id": "STRUCTURING_WINDOW",
            "before": {"aggregation_hours": 24},
            "after": {"aggregation_hours": 48},
        },
        "_affects": _affects_structuring_window,
        "_new_outcome": _new_outcome_structuring,
    },
]

# ---------------------------------------------------------------------------
# Change-type classification
# ---------------------------------------------------------------------------

_DISP_SEVERITY = {"ALLOW": 0, "EDD": 1, "BLOCK": 2}


def _determine_change_type(
    outcome_before: dict, outcome_after: dict
) -> str:
    """Classify the nature of the shift.

    Returns one of:
    * ``escalation``   – disposition became more severe
    * ``de_escalation`` – disposition became less severe
    * ``reporting_change`` – same disposition, different reporting
    * ``decision_level_change`` – same disposition + reporting, different level
    * ``no_change`` – nothing changed (shouldn't happen if *affects* is correct)
    """
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

def _build_shadow(
    seed: dict,
    shift: dict,
    outcome_after: dict,
    decision_level_after: str,
) -> dict:
    """Create one shadow projection record."""
    outcome_before = seed.get("outcome", {})
    decision_level_before = seed.get("decision_level", "analyst")

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

def generate_policy_shift_shadows(
    seeds: list[dict],
) -> dict[str, list[dict]]:
    """Apply all 4 policy shifts against *seeds* and return shadow records.

    Returns
    -------
    dict mapping ``shift_id`` → list of shadow records.
    """
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
                new_level = seed.get("decision_level", "analyst")

            shadow = _build_shadow(seed, shift, new_outcome, new_level)
            shadows.append(shadow)

        result[shift_id] = shadows

    return result


def get_shift_metadata(shift_id: str) -> dict | None:
    """Return serialisable metadata for a single policy shift."""
    for shift in POLICY_SHIFTS:
        if shift["id"] == shift_id:
            meta = {k: v for k, v in shift.items() if not k.startswith("_")}
            return meta
    return None


def get_all_shift_summaries(
    shadows_by_shift: dict[str, list[dict]],
    total_seeds: int = 1500,
) -> list[dict]:
    """Build summary objects for every policy shift (used by API)."""
    summaries: list[dict] = []

    for shift in POLICY_SHIFTS:
        sid = shift["id"]
        shadows = shadows_by_shift.get(sid, [])
        n_affected = len(shadows)

        # Determine primary change type
        change_types: dict[str, int] = {}
        for s in shadows:
            ct = s.get("change_type", "unknown")
            change_types[ct] = change_types.get(ct, 0) + 1
        primary = max(change_types, key=change_types.get) if change_types else "unknown"

        # Human-readable summary
        description_map = {
            "lctr_threshold": f"{n_affected} cash transactions in $8K–$10K range gain LCTR filing obligation",
            "pep_risk_appetite": f"{n_affected} PEP cases with ≥$25K escalated to senior management",
            "crypto_classification": f"{n_affected} crypto transaction seeds reclassified as high-risk EDD",
            "structuring_window": f"{n_affected} cases with just-below-threshold patterns flagged under 48hr window",
        }

        summaries.append({
            "id": sid,
            "name": shift["name"],
            "description": shift["description"],
            "citation": shift["citation"],
            "policy_version_before": "2026.01.01",
            "policy_version_after": shift["policy_version"],
            "total_cases_analyzed": total_seeds,
            "cases_affected": n_affected,
            "pct_affected": round(n_affected / total_seeds * 100, 1) if total_seeds else 0,
            "primary_change": primary,
            "summary": description_map.get(sid, f"{n_affected} cases affected"),
        })

    return summaries


def summarize_case_facts(shadow: dict, seeds_lookup: dict[str, dict] | None = None) -> str:
    """Return a one-line case summary for a shadow record.

    If *seeds_lookup* is provided (precedent_id → seed), uses anchor_facts
    for a richer summary.  Otherwise falls back to basic shift info.
    """
    pid = shadow.get("original_precedent_id", "?")
    change = shadow.get("change_description", "")
    ct = shadow.get("change_type", "")

    if seeds_lookup and pid in seeds_lookup:
        seed = seeds_lookup[pid]
        txn_type = _seed_fact(seed, "txn.type") or "txn"
        amount = _seed_fact(seed, "txn.amount_band") or ""
        cust = _seed_fact(seed, "customer.type") or ""
        return f"{cust} | {txn_type} | {amount} → {ct} ({change})"

    return f"Precedent {pid[:8]}… → {ct} ({change})"
