"""
Dashboard API Router
====================
Serves the endpoints the React dashboard expects.

Endpoints:
  GET  /api/domain                     - Insurance domain info
  GET  /api/stats                      - Dashboard statistics
  GET  /api/cases                      - Demo cases in dashboard format
  GET  /api/cases/{case_id}            - Single case
  GET  /api/report/{case_id}/json      - Full precedent report for a case
  GET  /api/audit                      - Filtered cases (search, outcome, scenario)
  GET  /api/policy-shifts              - Policy shifts with affected-case counts
  GET  /api/policy-shifts/{shift_id}/cases - Affected cases for a shift
  GET  /api/simulate/drafts            - Draft shifts for simulation
  POST /api/simulate                   - Run a single-shift simulation
  POST /api/simulate/compare           - Compare multiple shift simulations
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.demo_cases import get_demo_cases, get_demo_case
from api.report_builder import build_report
from domains.insurance_claims.policy_shifts import (
    POLICY_SHIFTS,
    generate_policy_shift_shadows,
    get_shift_metadata,
    SHIFT_EFFECTIVE_DATES,
    extract_case_signals,
    detect_applicable_shifts,
    compute_shadow_outcome,
)
from domains.insurance_claims.seed_generator import generate_all_insurance_seeds
from domains.insurance_claims.domain import create_insurance_domain_registry


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(tags=["Dashboard"])


# ---------------------------------------------------------------------------
# Lazy cache for seeds and registry
# ---------------------------------------------------------------------------

_cache: dict = {}


def _get_seeds():
    if "seeds" not in _cache:
        _cache["seeds"] = generate_all_insurance_seeds()
    return _cache["seeds"]


def _get_registry():
    if "registry" not in _cache:
        _cache["registry"] = create_insurance_domain_registry()
    return _cache["registry"]


# ---------------------------------------------------------------------------
# v1 outcome_code -> insurance disposition mapping
# ---------------------------------------------------------------------------

_V1_TO_DISPOSITION = {"pay": "PAY_CLAIM", "escalate": "INVESTIGATE", "deny": "DENY_CLAIM"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _map_outcome_to_category(expected_outcome: str) -> str:
    """Map a demo-case expected_outcome to a dashboard category."""
    if expected_outcome in ("pay", "deny"):
        return "PASS"
    if expected_outcome in ("escalate", "request_info"):
        return "ESCALATE"
    # Catch-all for anything with fraud/edge/threshold connotations
    return "EDGE"


def _transform_case(case: dict) -> dict:
    """Transform a raw demo case dict into the dashboard shape."""
    name_lower = case.get("name", "").lower()
    category = _map_outcome_to_category(case["expected_outcome"])
    # Override to EDGE if the name implies an edge/threshold/fraud scenario
    if any(kw in name_lower for kw in ("edge", "fraud", "threshold", "boundary")):
        category = "EDGE"

    return {
        "id": case["id"],
        "name": case["name"],
        "description": case["description"],
        "category": category,
        "expected_verdict": case["expected_outcome"],
        "key_levers": case.get("key_facts", []),
        "tags": [case.get("line_of_business", "")],
        "facts": [
            {"field_id": f["field"], "value": f["value"], "label": f["field"]}
            for f in case["facts"]
        ],
    }


def _seeds_to_shadow_dicts(seeds) -> list[dict]:
    """Convert JudgmentPayload seeds to plain dicts for shadow generation.

    generate_policy_shift_shadows expects dicts with 'anchor_facts' (list of
    dicts with field_id/value), 'outcome', 'decision_level', 'precedent_id'.
    """
    result: list[dict] = []
    for seed in seeds:
        # Build anchor_facts list from JudgmentPayload
        if hasattr(seed, "anchor_facts"):
            af_list = [
                {"field_id": af.field_id, "value": af.value}
                for af in seed.anchor_facts
            ]
        elif isinstance(seed, dict):
            af_list = seed.get("anchor_facts", [])
        else:
            af_list = []

        # Build outcome dict
        outcome_code = getattr(seed, "outcome_code", None)
        if isinstance(seed, dict):
            outcome_code = seed.get("outcome_code", "pay")
        disposition = _V1_TO_DISPOSITION.get(outcome_code or "pay", "PAY_CLAIM")

        basis = getattr(seed, "disposition_basis", None)
        if basis is None and isinstance(seed, dict):
            basis = seed.get("disposition_basis", "DISCRETIONARY")

        reporting = getattr(seed, "reporting_obligation", None)
        if reporting is None and isinstance(seed, dict):
            reporting = seed.get("reporting_obligation", "NO_FILING")

        decision_level = getattr(seed, "decision_level", None)
        if decision_level is None and isinstance(seed, dict):
            decision_level = seed.get("decision_level", "adjuster")

        precedent_id = getattr(seed, "precedent_id", None)
        if precedent_id is None and isinstance(seed, dict):
            precedent_id = seed.get("precedent_id", "")

        result.append({
            "anchor_facts": af_list,
            "outcome": {
                "disposition": disposition,
                "disposition_basis": basis or "DISCRETIONARY",
                "reporting": reporting or "NO_FILING",
            },
            "decision_level": decision_level or "adjuster",
            "precedent_id": precedent_id or "",
        })
    return result


def _classify_magnitude(affected: int, total: int) -> str:
    """Classify the magnitude of a policy shift impact."""
    if total == 0:
        return "MINOR"
    pct = affected / total * 100
    if pct < 1:
        return "MINOR"
    if pct < 5:
        return "MODERATE"
    if pct < 15:
        return "SIGNIFICANT"
    return "FUNDAMENTAL"


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class SimulateRequest(BaseModel):
    draft_id: str


class CompareRequest(BaseModel):
    draft_ids: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/domain")
async def get_domain():
    """Return insurance domain info."""
    return {
        "domain": "insurance_claims",
        "name": "ClaimPilot",
        "terminology": {
            "entity": "claim",
            "institution": "insurer",
            "decision_maker": "claims adjuster",
            "review_process": "investigation",
            "escalation_target": "Special Investigations Unit",
            "filing_authority": "FSRA",
        },
    }


@router.get("/api/stats")
async def get_stats():
    """Return dashboard statistics."""
    seeds = _get_seeds()
    demo_cases = get_demo_cases()
    registry = _get_registry()
    seed_count = len(seeds)

    return {
        "total_seeds": len(seeds),
        "demo_cases": len(demo_cases),
        "policy_shifts": 3,
        "registry_fields": len(registry.fields),
        "precedents_loaded": seed_count,
        "engine_version": "3.0",
        "policy_version": "2026.01.01",
    }


@router.get("/api/cases")
async def get_cases():
    """Return demo cases in dashboard format."""
    demo_cases = get_demo_cases()
    return [_transform_case(c) for c in demo_cases]


@router.get("/api/cases/{case_id}")
async def get_case(case_id: str):
    """Return a single case in dashboard format."""
    case = get_demo_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    return _transform_case(case)


@router.get("/api/report/{case_id}/json")
async def get_report_json(case_id: str):
    """Run a demo case through the precedent engine and return the report."""
    case = get_demo_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    # Generate seeds (lazy cached)
    seeds = _get_seeds()
    registry = _get_registry()

    # Transform demo case facts to report_builder expected format
    # report_builder expects facts as [{field_id, value, label}]
    report_case = {
        "id": case["id"],
        "name": case["name"],
        "description": case.get("description", ""),
        "expected_verdict": case.get("expected_outcome", "pay"),
        "line_of_business": case.get("line_of_business", ""),
        "facts": [
            {
                "field_id": f["field"],
                "value": f["value"],
                "label": f["field"],
            }
            for f in case["facts"]
        ],
    }

    report = build_report(report_case, seeds, registry)

    iso_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "format": "json",
        "generated_at": iso_now,
        "report": report,
    }


@router.get("/api/audit")
async def get_audit(
    q: str = Query(default="", description="Search term"),
    outcome: str = Query(default="", description="Filter by expected outcome"),
    scenario: str = Query(default="", description="Filter by scenario/line of business"),
):
    """Return filtered cases for audit view."""
    demo_cases = get_demo_cases()
    results = demo_cases

    # Filter by outcome
    if outcome:
        results = [c for c in results if c.get("expected_outcome") == outcome]

    # Filter by scenario / line of business
    if scenario:
        results = [c for c in results if c.get("line_of_business") == scenario]

    # Search filter (name, description, id)
    if q:
        q_lower = q.lower()
        results = [
            c for c in results
            if q_lower in c.get("name", "").lower()
            or q_lower in c.get("description", "").lower()
            or q_lower in c.get("id", "").lower()
        ]

    return [_transform_case(c) for c in results]


@router.get("/api/policy-shifts")
async def get_policy_shifts():
    """Return policy shifts with affected-case counts."""
    seeds = _get_seeds()
    seed_dicts = _seeds_to_shadow_dicts(seeds)
    total_seeds = len(seed_dicts)

    # Generate all shadow records at once
    all_shadows = generate_policy_shift_shadows(seed_dicts)

    shifts_out: list[dict[str, Any]] = []
    for shift in POLICY_SHIFTS:
        shift_id = shift["id"]
        shadows = all_shadows.get(shift_id, [])
        meta = get_shift_metadata(shift_id) or {}

        shifts_out.append({
            "id": shift_id,
            "name": meta.get("name", shift.get("name", "")),
            "description": meta.get("description", shift.get("description", "")),
            "citation": meta.get("citation", shift.get("citation", "")),
            "policy_version_before": "2026.01.01",
            "policy_version_after": shift["policy_version"],
            "total_cases_analyzed": total_seeds,
            "cases_affected": len(shadows),
            "pct_affected": round(len(shadows) / total_seeds * 100, 1) if total_seeds > 0 else 0.0,
            "primary_change": shift["description"],
            "summary": f"{len(shadows)} of {total_seeds} cases affected",
        })

    return shifts_out


@router.get("/api/policy-shifts/{shift_id}/cases")
async def get_policy_shift_cases(shift_id: str):
    """Return the affected cases for a specific policy shift."""
    meta = get_shift_metadata(shift_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Shift '{shift_id}' not found")

    seeds = _get_seeds()
    seed_dicts = _seeds_to_shadow_dicts(seeds)

    all_shadows = generate_policy_shift_shadows(seed_dicts)
    shadows = all_shadows.get(shift_id, [])

    return {
        "shift_id": shift_id,
        "shift_name": meta.get("name", ""),
        "total_affected": len(shadows),
        "cases": [
            {
                "shadow_id": s.get("shadow_id"),
                "original_precedent_id": s.get("original_precedent_id"),
                "outcome_before": s.get("outcome_before", {}),
                "outcome_after": s.get("outcome_after", {}),
                "decision_level_before": s.get("decision_level_before", ""),
                "decision_level_after": s.get("decision_level_after", ""),
                "change_type": s.get("change_type", ""),
                "change_description": s.get("change_description", ""),
                "citation": s.get("citation", ""),
            }
            for s in shadows
        ],
    }


@router.get("/api/simulate/drafts")
async def get_simulate_drafts():
    """Return insurance draft shifts for simulation."""
    drafts: list[dict[str, Any]] = []
    for shift in POLICY_SHIFTS:
        drafts.append({
            "id": shift["id"],
            "name": shift["name"],
            "description": shift["description"],
            "parameter": shift["rule_change"]["rule_id"],
            "old_value": str(shift["rule_change"]["before"]),
            "new_value": str(shift["rule_change"]["after"]),
            "trigger_signals": shift.get("trigger_signals", []),
            "affected_typologies": [],
            "citation": shift.get("citation", ""),
        })
    return drafts


@router.post("/api/simulate")
async def simulate(request: SimulateRequest):
    """Simulate a single policy shift against all seeds."""
    draft_id = request.draft_id

    meta = get_shift_metadata(draft_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Draft shift '{draft_id}' not found")

    seeds = _get_seeds()
    seed_dicts = _seeds_to_shadow_dicts(seeds)
    total = len(seed_dicts)

    all_shadows = generate_policy_shift_shadows(seed_dicts)
    shadows = all_shadows.get(draft_id, [])
    affected = len(shadows)

    # Build disposition change breakdown
    disposition_changes: dict[str, int] = {}
    for s in shadows:
        before_disp = s.get("outcome_before", {}).get("disposition", "UNKNOWN")
        after_disp = s.get("outcome_after", {}).get("disposition", "UNKNOWN")
        key = f"{before_disp} -> {after_disp}"
        disposition_changes[key] = disposition_changes.get(key, 0) + 1

    iso_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "draft": meta,
        "timestamp": iso_now,
        "total_cases_evaluated": total,
        "affected_cases": affected,
        "unaffected_cases": total - affected,
        "disposition_changes": disposition_changes,
        "magnitude": _classify_magnitude(affected, total),
        "pct_affected": round(affected / total * 100, 1) if total > 0 else 0.0,
        "shadows": [
            {
                "shadow_id": s.get("shadow_id"),
                "original_precedent_id": s.get("original_precedent_id"),
                "outcome_before": s.get("outcome_before", {}),
                "outcome_after": s.get("outcome_after", {}),
                "change_type": s.get("change_type", ""),
            }
            for s in shadows[:50]  # Limit to first 50 for response size
        ],
    }


@router.post("/api/simulate/compare")
async def simulate_compare(request: CompareRequest):
    """Compare multiple shift simulations side by side."""
    seeds = _get_seeds()
    seed_dicts = _seeds_to_shadow_dicts(seeds)
    total = len(seed_dicts)

    all_shadows = generate_policy_shift_shadows(seed_dicts)
    iso_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    results: list[dict[str, Any]] = []
    for draft_id in request.draft_ids:
        meta = get_shift_metadata(draft_id)
        if meta is None:
            results.append({
                "draft_id": draft_id,
                "error": f"Draft shift '{draft_id}' not found",
            })
            continue

        shadows = all_shadows.get(draft_id, [])
        affected = len(shadows)

        disposition_changes: dict[str, int] = {}
        for s in shadows:
            before_disp = s.get("outcome_before", {}).get("disposition", "UNKNOWN")
            after_disp = s.get("outcome_after", {}).get("disposition", "UNKNOWN")
            key = f"{before_disp} -> {after_disp}"
            disposition_changes[key] = disposition_changes.get(key, 0) + 1

        results.append({
            "draft": meta,
            "timestamp": iso_now,
            "total_cases_evaluated": total,
            "affected_cases": affected,
            "unaffected_cases": total - affected,
            "disposition_changes": disposition_changes,
            "magnitude": _classify_magnitude(affected, total),
            "pct_affected": round(affected / total * 100, 1) if total > 0 else 0.0,
        })

    return results
