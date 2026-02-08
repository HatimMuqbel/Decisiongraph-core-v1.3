"""
Policy Shift API — /api/policy-shifts
======================================
Two endpoints exposing policy shift impact analysis:

* ``GET /api/policy-shifts``               — summary of all 4 shifts
* ``GET /api/policy-shifts/{shift_id}/cases`` — affected cases with before/after
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from decisiongraph.aml_seed_generator import generate_all_banking_seeds
from decisiongraph.policy_shift_shadows import (
    POLICY_SHIFTS,
    generate_policy_shift_shadows,
    get_all_shift_summaries,
    get_shift_metadata,
    summarize_case_facts,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/policy-shifts", tags=["Policy Shifts"])

# ---------------------------------------------------------------------------
# Module-level cache (generated once on first request)
# ---------------------------------------------------------------------------

_cache: dict[str, Any] = {}


_V1_TO_DISPOSITION = {"pay": "ALLOW", "escalate": "EDD", "deny": "BLOCK"}


def _payload_to_shadow_dict(payload) -> dict:
    """Convert a JudgmentPayload dataclass to the dict format expected by
    the policy-shift shadow module.

    JudgmentPayload stores outcome as flat fields (outcome_code,
    disposition_basis, reporting_obligation).  The shadow module expects
    a nested ``outcome`` dict with keys ``disposition``, ``disposition_basis``,
    and ``reporting``.
    """
    d = payload.to_dict()
    # Reconstruct the three-field outcome dict
    d["outcome"] = {
        "disposition": _V1_TO_DISPOSITION.get(d.get("outcome_code", ""), d.get("outcome_code", "")),
        "disposition_basis": d.get("disposition_basis", "DISCRETIONARY"),
        "reporting": d.get("reporting_obligation", "NO_REPORT"),
    }
    return d


def _ensure_shadows() -> tuple[list[dict], dict[str, list[dict]], dict[str, dict]]:
    """Lazily generate seeds + shadows and cache them."""
    if "seeds" not in _cache:
        logger.info("Generating banking seeds for policy shift analysis …")
        payloads = generate_all_banking_seeds()
        logger.info("Generated %d seeds — computing shadows …", len(payloads))

        # Convert JudgmentPayload dataclass objects to dicts
        seeds = [_payload_to_shadow_dict(p) for p in payloads]

        shadows_by_shift = generate_policy_shift_shadows(seeds)
        total = sum(len(v) for v in shadows_by_shift.values())
        logger.info("Generated %d shadow records across %d shifts", total, len(shadows_by_shift))

        # Build lookup: precedent_id → seed  (for case summaries)
        seeds_lookup = {s["precedent_id"]: s for s in seeds}

        _cache["seeds"] = seeds
        _cache["shadows"] = shadows_by_shift
        _cache["seeds_lookup"] = seeds_lookup

    return _cache["seeds"], _cache["shadows"], _cache["seeds_lookup"]


# ---------------------------------------------------------------------------
# GET /api/policy-shifts
# ---------------------------------------------------------------------------

@router.get("")
async def list_policy_shifts():
    """Returns summary of all 4 policy shift scenarios with impact stats."""
    seeds, shadows_by_shift, _ = _ensure_shadows()
    summaries = get_all_shift_summaries(shadows_by_shift, total_seeds=len(seeds))
    return summaries


# ---------------------------------------------------------------------------
# GET /api/policy-shifts/{shift_id}/cases
# ---------------------------------------------------------------------------

@router.get("/{shift_id}/cases")
async def get_policy_shift_cases(shift_id: str):
    """Returns affected cases with before/after comparison for a single shift."""
    # Validate shift_id
    valid_ids = {s["id"] for s in POLICY_SHIFTS}
    if shift_id not in valid_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown policy shift '{shift_id}'. Valid IDs: {sorted(valid_ids)}",
        )

    seeds, shadows_by_shift, seeds_lookup = _ensure_shadows()
    shadows = shadows_by_shift.get(shift_id, [])
    meta = get_shift_metadata(shift_id)

    cases = [
        {
            "precedent_id": s["original_precedent_id"],
            "case_summary": summarize_case_facts(s, seeds_lookup),
            "outcome_before": s["outcome_before"],
            "outcome_after": s["outcome_after"],
            "decision_level_before": s["decision_level_before"],
            "decision_level_after": s["decision_level_after"],
            "change_type": s["change_type"],
            "rule_hash_before": s["rule_hash_before"],
            "rule_hash_after": s["rule_hash_after"],
        }
        for s in shadows
    ]

    return {
        "shift": meta,
        "total_cases": len(cases),
        "cases": cases,
    }
