"""
Policy Simulation API — /api/simulate
======================================
Simulate-before-enact endpoints:

* ``GET  /api/simulate/drafts``    — list available demo drafts
* ``POST /api/simulate``           — simulate a single draft
* ``POST /api/simulate/compare``   — compare multiple drafts side-by-side
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from decisiongraph.aml_seed_generator import generate_all_banking_seeds
from kernel.policy.policy_simulation import (
    DEMO_DRAFTS,
    DEMO_DRAFTS_BY_ID,
    PolicySimulator,
    SimulationReport,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulate", tags=["Policy Simulation"])

# ---------------------------------------------------------------------------
# Module-level cache (seeds generated once on first request)
# ---------------------------------------------------------------------------

_cache: dict[str, Any] = {}

_V1_TO_DISPOSITION = {"pay": "ALLOW", "escalate": "EDD", "deny": "BLOCK"}


def _payload_to_seed_dict(payload) -> dict:
    """Convert JudgmentPayload to the dict format used by the simulator."""
    d = payload.to_dict()
    d["outcome"] = {
        "disposition": _V1_TO_DISPOSITION.get(
            d.get("outcome_code", ""), d.get("outcome_code", ""),
        ),
        "disposition_basis": d.get("disposition_basis", "DISCRETIONARY"),
        "reporting": d.get("reporting_obligation", "NO_REPORT"),
    }
    return d


def _get_simulator() -> PolicySimulator:
    """Lazily create the simulator with generated seeds."""
    if "simulator" not in _cache:
        logger.info("Generating banking seeds for policy simulation …")
        payloads = generate_all_banking_seeds()
        seeds = [_payload_to_seed_dict(p) for p in payloads]
        logger.info("Created simulator with %d seeds", len(seeds))
        _cache["simulator"] = PolicySimulator(seeds)
    return _cache["simulator"]


def _report_to_dict(report: SimulationReport) -> dict:
    """Serialize a SimulationReport to JSON-safe dict."""
    d = asdict(report)
    # Replace DraftShift dataclass with its dict
    d["draft"] = asdict(report.draft)
    return d


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class SimulateRequest(BaseModel):
    draft_id: str


class CompareRequest(BaseModel):
    draft_ids: list[str]


# ---------------------------------------------------------------------------
# GET /api/simulate/drafts
# ---------------------------------------------------------------------------

@router.get("/drafts")
async def list_drafts():
    """Return list of available demo draft shifts."""
    return [
        {
            "id": d.id,
            "name": d.name,
            "description": d.description,
            "parameter": d.parameter,
            "old_value": d.old_value,
            "new_value": d.new_value,
            "trigger_signals": d.trigger_signals,
            "affected_typologies": d.affected_typologies,
            "citation": d.citation,
        }
        for d in DEMO_DRAFTS
    ]


# ---------------------------------------------------------------------------
# POST /api/simulate
# ---------------------------------------------------------------------------

@router.post("")
async def simulate(req: SimulateRequest):
    """Simulate a single draft shift against the precedent pool."""
    draft = DEMO_DRAFTS_BY_ID.get(req.draft_id)
    if not draft:
        valid = sorted(DEMO_DRAFTS_BY_ID.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Unknown draft '{req.draft_id}'. Valid: {valid}",
        )

    simulator = _get_simulator()
    report = simulator.simulate(draft)
    return _report_to_dict(report)


# ---------------------------------------------------------------------------
# POST /api/simulate/compare
# ---------------------------------------------------------------------------

@router.post("/compare")
async def compare(req: CompareRequest):
    """Compare multiple draft shifts side-by-side."""
    drafts = []
    for did in req.draft_ids:
        d = DEMO_DRAFTS_BY_ID.get(did)
        if not d:
            valid = sorted(DEMO_DRAFTS_BY_ID.keys())
            raise HTTPException(
                status_code=404,
                detail=f"Unknown draft '{did}'. Valid: {valid}",
            )
        drafts.append(d)

    simulator = _get_simulator()
    reports = simulator.compare(drafts)
    return [_report_to_dict(r) for r in reports]
