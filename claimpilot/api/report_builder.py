"""
Report Builder -- runs an insurance case through the kernel v3 precedent
engine and returns a report dict matching the React dashboard ReportViewModel.

This is the core intelligence module.  No Flask/FastAPI code here -- just the
pure computation that converts a demo case + seed pool into the structured
report the dashboard consumes.

Pipeline:
  1. Convert case facts to flat dict
  2. Evaluate comparability gates (Layer 1) -- filter seeds
  3. Score similarity (Layer 2) -- rank seeds, apply floor
  4. Governed confidence (Layer 3) -- four-dimension min() model
  5. Classify matches (v3 supporting/contrary/neutral)
  6. Detect applicable policy shifts
  7. Assemble dashboard-shaped report dict
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kernel.precedent.comparability_gate import evaluate_gates
from kernel.precedent.precedent_scorer import score_similarity, classify_match_v3
from kernel.precedent.governed_confidence import compute_governed_confidence
from kernel.precedent.domain_registry import ConfidenceLevel, DomainRegistry
from domains.insurance_claims.domain import create_insurance_domain_registry
from domains.insurance_claims.policy_shifts import (
    extract_case_signals,
    detect_applicable_shifts,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_POLICY_VERSION = "2026.01.01"
_ENGINE_VERSION = "3.0"

# Map ConfidenceLevel enum to dashboard display strings
_CONFIDENCE_DISPLAY: dict[ConfidenceLevel, str] = {
    ConfidenceLevel.NONE: "Low",
    ConfidenceLevel.LOW: "Low",
    ConfidenceLevel.MODERATE: "Moderate",
    ConfidenceLevel.HIGH: "High",
    ConfidenceLevel.VERY_HIGH: "High",
}

# Map ConfidenceLevel enum to 0-100 numeric score
_CONFIDENCE_SCORE: dict[ConfidenceLevel, int] = {
    ConfidenceLevel.NONE: 0,
    ConfidenceLevel.LOW: 25,
    ConfidenceLevel.MODERATE: 50,
    ConfidenceLevel.HIGH: 75,
    ConfidenceLevel.VERY_HIGH: 95,
}

# Insurance disposition -> canonical v3 disposition used by classify_match_v3
_INSURANCE_TO_V3_DISPOSITION: dict[str, str] = {
    "PAY_CLAIM": "ALLOW",
    "PARTIAL_PAY": "ALLOW",
    "APPROVE": "ALLOW",
    "INVESTIGATE": "EDD",
    "REFER_SIU": "EDD",
    "HOLD": "EDD",
    "DENY_CLAIM": "BLOCK",
    "DECLINE": "BLOCK",
    "REJECT": "BLOCK",
}

# v1 outcome_code -> canonical v3 disposition
_V1_OUTCOME_TO_V3: dict[str, str] = {
    "pay": "ALLOW",
    "partial": "ALLOW",
    "escalate": "EDD",
    "deny": "BLOCK",
}

# Disposition to decision_status for the dashboard
_DISPOSITION_TO_STATUS: dict[str, str] = {
    "PAY_CLAIM": "approve",
    "PARTIAL_PAY": "approve",
    "INVESTIGATE": "investigate",
    "REFER_SIU": "investigate",
    "DENY_CLAIM": "deny",
}

# Disposition to action string
_DISPOSITION_TO_ACTION: dict[str, str] = {
    "PAY_CLAIM": "PAY_CLAIM",
    "PARTIAL_PAY": "PARTIAL_PAY",
    "INVESTIGATE": "INVESTIGATE",
    "REFER_SIU": "REFER_SIU",
    "DENY_CLAIM": "DENY_CLAIM",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _case_facts_to_flat(case: dict) -> dict[str, Any]:
    """Convert case ``facts`` list to a flat ``{field_id: value}`` dict,
    then enrich with standardized registry fields derived from the raw facts."""
    facts_list = case.get("facts", [])
    flat: dict[str, Any] = {}
    for f in facts_list:
        fid = f.get("field_id", "")
        if fid:
            flat[fid] = f.get("value")
    # Enrich with standardized fields the registry/seeds expect
    _enrich_standardized_fields(flat, case)
    return flat


def _enrich_standardized_fields(flat: dict[str, Any], case: dict) -> None:
    """Derive the 23 standardized registry fields from policy-specific demo
    case facts so that similarity scoring has shared dimensions.

    Only sets a field if it is not already present.
    """
    def _set(key: str, val: Any) -> None:
        if key not in flat:
            flat[key] = val

    # --- claim.coverage_line (from line_of_business or known prefixes) ---
    lob = case.get("line_of_business", "")
    _lob_map = {
        "auto": "auto", "property": "property", "marine": "marine",
        "health": "health", "workers_comp": "workers_comp",
        "liability": "cgl", "travel": "travel",
    }
    if lob:
        _set("claim.coverage_line", _lob_map.get(lob, lob))

    # --- claim.claimant_type ---
    # Most demo cases are first-party unless field explicitly says otherwise
    _set("claim.claimant_type", "first_party")

    # --- claim.amount_band (from claim.reserve_amount) ---
    reserve = flat.get("claim.reserve_amount")
    if reserve is not None:
        try:
            amt = float(reserve)
            if amt < 5000:
                _set("claim.amount_band", "0_5k")
            elif amt < 25000:
                _set("claim.amount_band", "5k_25k")
            elif amt < 100000:
                _set("claim.amount_band", "25k_100k")
            elif amt < 500000:
                _set("claim.amount_band", "100k_500k")
            else:
                _set("claim.amount_band", "over_500k")
        except (ValueError, TypeError):
            pass

    # --- claim.occurred_during_policy ---
    if flat.get("occurrence.during_policy_period") is not None:
        _set("claim.occurred_during_policy", flat["occurrence.during_policy_period"])
    elif flat.get("policy.status") == "active":
        _set("claim.occurred_during_policy", True)

    # --- claim.loss_cause ---
    for key in ("loss.cause", "loss.primary_cause", "loss.type"):
        if flat.get(key):
            _set("claim.loss_cause", flat[key])
            break

    # --- claim.injury_type ---
    if flat.get("claim.injury_type") is None:
        if flat.get("injury.work_related") or flat.get("injury.arose_out_of_employment"):
            _set("claim.injury_type", "moderate")

    # --- claim.time_to_report ---
    # Default to reasonable value when not explicit
    _set("claim.time_to_report", "1_7_days")

    # --- flag fields ---
    # fraud_indicator: true if any fraud-like signals present
    fraud = (
        flat.get("flag.fraud_indicator")
        or flat.get("loss.intentional_indicators")
        or flat.get("flag.staged_accident")
        or flat.get("injury.self_inflicted")
    )
    _set("flag.fraud_indicator", bool(fraud))

    # staged_accident
    _set("flag.staged_accident", bool(flat.get("flag.staged_accident", False)))

    # late_reporting
    _set("flag.late_reporting", bool(flat.get("flag.late_reporting", False)))

    # inconsistent_statements
    _set("flag.inconsistent_statements", bool(flat.get("flag.inconsistent_statements", False)))

    # excessive_claim_history
    _set("flag.excessive_claim_history", bool(flat.get("flag.excessive_claim_history", False)))

    # pre_existing_damage
    pre_existing = flat.get("flag.pre_existing_damage") or flat.get("condition.preexisting")
    _set("flag.pre_existing_damage", bool(pre_existing))

    # prior_claims_frequency
    _set("flag.prior_claims_frequency", "none")

    # --- screening.siu_referral ---
    _set("screening.siu_referral", bool(flat.get("screening.siu_referral", False)))

    # --- evidence fields ---
    _set("evidence.police_report", bool(flat.get("police_report.impaired_charges", False)))
    _set("evidence.medical_report", bool(
        flat.get("evidence.medical_report")
        or flat.get("condition.last_treatment_date")
        or flat.get("treatment.type")
    ))
    _set("evidence.photos_documentation", bool(flat.get("evidence.photos_documentation", False)))
    _set("evidence.witness_statements", bool(flat.get("evidence.witness_statements", False)))

    # --- prior.claims_denied ---
    _set("prior.claims_denied", flat.get("prior.claims_denied", 0))

    # --- policy fields ---
    _set("policy.deductible_band", "low")
    _set("policy.coverage_limit_band", "mid")
    _set("policy.policy_age", "1_3_years")

    # --- impairment → fraud linkage (auto-specific) ---
    if flat.get("driver.impairment_indicated") or flat.get("driver.bac_level", 0) > 0.05:
        flat["flag.fraud_indicator"] = True


def _seed_facts_to_flat(seed: Any) -> dict[str, Any]:
    """Extract anchor_facts from a seed (JudgmentPayload or dict) to flat dict."""
    if hasattr(seed, "anchor_facts"):
        anchor_facts = seed.anchor_facts
    elif isinstance(seed, dict):
        anchor_facts = seed.get("anchor_facts", [])
    else:
        return {}

    flat: dict[str, Any] = {}
    for af in anchor_facts:
        if hasattr(af, "field_id"):
            flat[af.field_id] = af.value
        elif isinstance(af, dict):
            fid = af.get("field_id", "")
            if fid:
                flat[fid] = af.get("value")
    return flat


def _seed_attr(seed: Any, attr: str, default: Any = None) -> Any:
    """Read an attribute from a seed (JudgmentPayload dataclass or dict)."""
    if hasattr(seed, attr):
        return getattr(seed, attr)
    if isinstance(seed, dict):
        return seed.get(attr, default)
    return default


def _seed_disposition(seed: Any) -> str:
    """Derive the canonical v3 disposition for a seed.

    Seeds store outcome info in several places depending on format:
      - ``outcome.disposition``  (dict seeds from scenarios)
      - ``outcome_code``         (JudgmentPayload -- v1 pay/deny/escalate)
      - ``disposition_basis``    is on the seed directly (JudgmentPayload)
    """
    # Try outcome dict first (scenario-style seeds)
    outcome = _seed_attr(seed, "outcome")
    if isinstance(outcome, dict) and outcome.get("disposition"):
        raw = outcome["disposition"]
        return _INSURANCE_TO_V3_DISPOSITION.get(raw, raw)

    # Fall back to outcome_code (JudgmentPayload v1 code)
    oc = _seed_attr(seed, "outcome_code", "")
    return _V1_OUTCOME_TO_V3.get(oc, "UNKNOWN")


def _seed_basis(seed: Any) -> str:
    """Extract disposition_basis from a seed."""
    outcome = _seed_attr(seed, "outcome")
    if isinstance(outcome, dict) and outcome.get("disposition_basis"):
        return outcome["disposition_basis"]
    return _seed_attr(seed, "disposition_basis", "UNKNOWN")


def _seed_reporting(seed: Any) -> str:
    """Extract reporting obligation from a seed."""
    outcome = _seed_attr(seed, "outcome")
    if isinstance(outcome, dict) and outcome.get("reporting"):
        return outcome["reporting"]
    return _seed_attr(seed, "reporting_obligation", "NO_FILING")


def _seed_raw_disposition(seed: Any) -> str:
    """Return the raw insurance disposition (not mapped to v3)."""
    outcome = _seed_attr(seed, "outcome")
    if isinstance(outcome, dict) and outcome.get("disposition"):
        return outcome["disposition"]
    # Reverse-map v1 outcome_code to insurance disposition
    oc = _seed_attr(seed, "outcome_code", "pay")
    return {"pay": "PAY_CLAIM", "deny": "DENY_CLAIM", "escalate": "INVESTIGATE"}.get(
        oc, "PAY_CLAIM"
    )


def _extract_gate_facts(case_facts: dict[str, Any]) -> dict[str, Any]:
    """Build comparability gate facts dict from flat case facts.

    The insurance comparability gates use four virtual fields:
      jurisdiction_regime, coverage_family, claimant_family, disposition_basis
    """
    return {
        "jurisdiction_regime": (
            case_facts.get("jurisdiction_regime")
            or case_facts.get("jurisdiction")
            or "CA-ON"
        ),
        "coverage_family": case_facts.get("claim.coverage_line", ""),
        "claimant_family": case_facts.get("claim.claimant_type", ""),
        "disposition_basis": case_facts.get("disposition_basis", "DISCRETIONARY"),
    }


def _extract_seed_gate_facts(seed_facts: dict[str, Any], seed: Any) -> dict[str, Any]:
    """Build comparability gate facts for a seed."""
    return {
        "jurisdiction_regime": (
            seed_facts.get("jurisdiction_regime")
            or _seed_attr(seed, "jurisdiction_code", "CA")
        ),
        "coverage_family": seed_facts.get("claim.coverage_line", ""),
        "claimant_family": seed_facts.get("claim.claimant_type", ""),
        "disposition_basis": _seed_basis(seed),
    }


def _compute_explainer(
    disposition: str,
    confidence_display: str,
    supporting: int,
    total_pool: int,
    coverage_line: str,
) -> str:
    """Build the human-readable decision explanation string."""
    coverage_desc = coverage_line.replace("_", " ") if coverage_line else "claim"

    if disposition in ("PAY_CLAIM", "PARTIAL_PAY"):
        return (
            f"Based on {confidence_display.lower()} confidence analysis of "
            f"{total_pool} comparable cases, this {coverage_desc} claim aligns "
            f"with prior payment decisions. {supporting} of {total_pool} comparable "
            f"cases resulted in claim payment under similar circumstances."
        )
    if disposition in ("INVESTIGATE", "REFER_SIU"):
        return (
            f"Based on {confidence_display.lower()} confidence analysis of "
            f"{total_pool} comparable cases, this {coverage_desc} claim warrants "
            f"further investigation. Pattern analysis identified indicators "
            f"consistent with cases referred for Special Investigations Unit review."
        )
    # DENY_CLAIM
    return (
        f"Based on {confidence_display.lower()} confidence analysis of "
        f"{total_pool} comparable cases, this {coverage_desc} claim matches "
        f"patterns associated with claim denial. {supporting} of {total_pool} "
        f"comparable cases were denied under similar conditions."
    )


def _build_posture_statement(
    alignment_pct: int,
    disposition: str,
    coverage_line: str,
) -> str:
    """Build the institutional posture statement for the enhanced precedent panel."""
    coverage_desc = coverage_line.replace("_", " ") if coverage_line else "general"
    return (
        f"The insurer's prior treatment of comparable cases shows "
        f"{alignment_pct}% alignment with {disposition} for similar "
        f"{coverage_desc} claims."
    )


# ---------------------------------------------------------------------------
# Core report builder
# ---------------------------------------------------------------------------

def build_report(case: dict, seeds: list, registry: DomainRegistry | None = None) -> dict:
    """Run an insurance case through the v3 precedent engine and return a
    report dict matching the React dashboard ReportViewModel shape.

    Args:
        case: Demo case dict with ``id``, ``name``, ``facts`` (list of
              ``{field_id, value, label}`` dicts).
        seeds: List of seed precedents (JudgmentPayload objects or dicts).
        registry: Optional pre-built DomainRegistry.  If *None*, the
                  insurance registry is created automatically.

    Returns:
        Dict matching the dashboard ReportViewModel contract.
    """
    iso_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if registry is None:
        registry = create_insurance_domain_registry()

    # ------------------------------------------------------------------
    # 1. Convert case facts to flat dict
    # ------------------------------------------------------------------
    case_facts = _case_facts_to_flat(case)

    # Determine the proposed disposition for this case
    expected_verdict = case.get("expected_verdict", "pay")
    proposed_disp_raw = {
        "pay": "PAY_CLAIM",
        "deny": "DENY_CLAIM",
        "investigate": "INVESTIGATE",
        "escalate": "INVESTIGATE",
        "partial": "PARTIAL_PAY",
    }.get(expected_verdict, "PAY_CLAIM")

    proposed_v3 = _INSURANCE_TO_V3_DISPOSITION.get(proposed_disp_raw, "ALLOW")
    proposed_basis = case_facts.get("disposition_basis", "DISCRETIONARY")
    coverage_line = case_facts.get("claim.coverage_line", "")

    # ------------------------------------------------------------------
    # 2. Prepare gate facts for the case
    # ------------------------------------------------------------------
    case_gate_facts = _extract_gate_facts(case_facts)

    # ------------------------------------------------------------------
    # 3. Layer 1: Evaluate comparability gates -- filter to passing seeds
    # ------------------------------------------------------------------
    passing_seeds: list[tuple[Any, dict[str, Any]]] = []

    for seed in seeds:
        seed_facts = _seed_facts_to_flat(seed)
        seed_gate = _extract_seed_gate_facts(seed_facts, seed)
        all_passed, _gate_results = evaluate_gates(registry, case_gate_facts, seed_gate)
        if all_passed:
            passing_seeds.append((seed, seed_facts))

    # ------------------------------------------------------------------
    # 4. Layer 2: Score similarity -- apply floor
    # ------------------------------------------------------------------
    similarity_floor = registry.similarity_floor

    scored_pool: list[dict[str, Any]] = []

    for seed, seed_facts in passing_seeds:
        drivers = _seed_attr(seed, "decision_drivers") or []
        sim_result = score_similarity(registry, case_facts, seed_facts, drivers)

        if sim_result.score < similarity_floor:
            continue

        # Classify match (v3 rules)
        seed_v3_disp = _seed_disposition(seed)
        seed_basis_val = _seed_basis(seed)
        classification = classify_match_v3(
            case_disposition=proposed_v3,
            precedent_disposition=seed_v3_disp,
            case_basis=proposed_basis,
            precedent_basis=seed_basis_val,
            non_transferable=sim_result.non_transferable,
        )

        scored_pool.append({
            "seed": seed,
            "seed_facts": seed_facts,
            "similarity": sim_result,
            "classification": classification,
            "v3_disposition": seed_v3_disp,
            "raw_disposition": _seed_raw_disposition(seed),
            "basis": seed_basis_val,
            "reporting": _seed_reporting(seed),
        })

    # Sort by similarity descending
    scored_pool.sort(key=lambda e: e["similarity"].score, reverse=True)

    pool_size = len(scored_pool)

    # ------------------------------------------------------------------
    # 5. Layer 3: Governed confidence
    # ------------------------------------------------------------------
    avg_similarity = (
        sum(e["similarity"].score for e in scored_pool) / pool_size
        if pool_size > 0
        else 0.0
    )

    # Count supporting / contrary / neutral among decisive (ALLOW/BLOCK) seeds
    supporting_count = sum(1 for e in scored_pool if e["classification"] == "supporting")
    contrary_count = sum(1 for e in scored_pool if e["classification"] == "contrary")
    neutral_count = sum(1 for e in scored_pool if e["classification"] == "neutral")

    # Decisive = terminal outcomes only (ALLOW/BLOCK, not EDD/UNKNOWN)
    decisive_entries = [
        e for e in scored_pool
        if e["v3_disposition"] in ("ALLOW", "BLOCK")
    ]
    decisive_supporting = sum(
        1 for e in decisive_entries if e["classification"] == "supporting"
    )
    decisive_total = len(decisive_entries)

    non_transferable_count = sum(
        1 for e in scored_pool if e["similarity"].non_transferable
    )

    confidence_result = compute_governed_confidence(
        domain=registry,
        pool_size=pool_size,
        avg_similarity=avg_similarity,
        decisive_supporting=decisive_supporting,
        decisive_total=decisive_total,
        case_facts=case_facts,
        non_transferable_count=non_transferable_count,
    )

    confidence_display = _CONFIDENCE_DISPLAY.get(confidence_result.level, "Low")
    confidence_score = _CONFIDENCE_SCORE.get(confidence_result.level, 0)

    # Confidence reason
    if confidence_result.hard_rule_applied:
        confidence_reason = f"Hard rule: {confidence_result.hard_rule_applied}"
    elif confidence_result.bottleneck:
        confidence_reason = (
            f"Bottleneck: {confidence_result.bottleneck.replace('_', ' ')}"
        )
    else:
        confidence_reason = "All confidence dimensions adequate"

    # ------------------------------------------------------------------
    # 6. Detect applicable policy shifts
    # ------------------------------------------------------------------
    case_signals = extract_case_signals(case_facts)
    applicable_shifts = detect_applicable_shifts(
        case_signals=case_signals,
        case_facts=case_facts,
    )

    # ------------------------------------------------------------------
    # 7. Build precedent alignment metrics
    # ------------------------------------------------------------------
    alignment_pct = (
        round(decisive_supporting / decisive_total * 100)
        if decisive_total > 0
        else 0
    )
    match_rate = round(avg_similarity * 100) if pool_size > 0 else 0

    # ------------------------------------------------------------------
    # 8. Build sample_cases for precedent analysis (top 10)
    # ------------------------------------------------------------------
    sample_cases: list[dict[str, Any]] = []
    for entry in scored_pool[:10]:
        seed = entry["seed"]
        sim = entry["similarity"]
        sample_cases.append({
            "precedent_id": _seed_attr(seed, "precedent_id", ""),
            "decision_level": _seed_attr(seed, "decision_level", "adjuster"),
            "decided_at": _seed_attr(seed, "decided_at", ""),
            "classification": entry["classification"],
            "similarity_pct": round(sim.score * 100),
            "outcome": {
                "disposition": entry["raw_disposition"],
                "disposition_basis": entry["basis"],
                "reporting": entry["reporting"],
            },
            "matched_drivers": list(sim.matched_drivers),
            "field_scores": dict(sim.field_scores),
        })

    # ------------------------------------------------------------------
    # 9. Build confidence dimensions for enhanced precedent panel
    # ------------------------------------------------------------------
    confidence_dimensions: list[dict[str, Any]] = []
    for dim in confidence_result.dimensions:
        confidence_dimensions.append({
            "name": dim.name,
            "value": round(dim.value, 4) if isinstance(dim.value, float) else dim.value,
            "level": dim.level.value,
            "bottleneck": dim.bottleneck,
            "note": dim.note,
        })

    # ------------------------------------------------------------------
    # 10. Build outcome distribution
    # ------------------------------------------------------------------
    outcome_dist: dict[str, int] = {}
    for entry in scored_pool:
        raw_disp = entry["raw_disposition"]
        outcome_dist[raw_disp] = outcome_dist.get(raw_disp, 0) + 1

    # ------------------------------------------------------------------
    # 11. Build driver causality analysis
    # ------------------------------------------------------------------
    shared_drivers: dict[str, int] = {}
    divergent_drivers: dict[str, int] = {}
    for entry in scored_pool:
        sim = entry["similarity"]
        for d in sim.matched_drivers:
            shared_drivers[d] = shared_drivers.get(d, 0) + 1
        for d in sim.mismatched_drivers:
            divergent_drivers[d] = divergent_drivers.get(d, 0) + 1

    shared_list = [
        {"field": k, "count": v}
        for k, v in sorted(shared_drivers.items(), key=lambda x: -x[1])
    ]
    divergent_list = [
        {"field": k, "count": v}
        for k, v in sorted(divergent_drivers.items(), key=lambda x: -x[1])
    ]

    # ------------------------------------------------------------------
    # 12. Build risk factors and decision drivers
    # ------------------------------------------------------------------
    risk_factors: list[dict[str, str]] = []
    decision_drivers_list: list[dict[str, str]] = []

    # Derive risk factors from case facts (flag fields that are True)
    _flag_labels = {
        "flag.fraud_indicator": "Fraud indicator detected",
        "flag.late_reporting": "Late reporting of claim",
        "flag.inconsistent_statements": "Inconsistent statements from claimant",
        "flag.staged_accident": "Staged accident indicators",
        "flag.excessive_claim_history": "Excessive prior claim history",
        "flag.pre_existing_damage": "Pre-existing damage detected",
        "screening.siu_referral": "Special Investigations Unit referral triggered",
    }
    for field_id, label in _flag_labels.items():
        if case_facts.get(field_id) is True:
            risk_factors.append({"field_id": field_id, "label": label, "severity": "high"})

    # Decision drivers from the highest-similarity comparable case
    if scored_pool:
        top_sim = scored_pool[0]["similarity"]
        for driver_field in top_sim.matched_drivers:
            fd = registry.fields.get(driver_field)
            driver_label = fd.label if fd else driver_field.replace(".", " ").replace("_", " ").title()
            decision_drivers_list.append({
                "field_id": driver_field,
                "label": driver_label,
                "impact": "aligned",
            })
        for driver_field in top_sim.mismatched_drivers:
            fd = registry.fields.get(driver_field)
            driver_label = fd.label if fd else driver_field.replace(".", " ").replace("_", " ").title()
            decision_drivers_list.append({
                "field_id": driver_field,
                "label": driver_label,
                "impact": "divergent",
            })

    # ------------------------------------------------------------------
    # 13. Build regime analysis from applicable shifts
    # ------------------------------------------------------------------
    regime_analysis: dict[str, Any] | None = None
    if applicable_shifts:
        regime_analysis = {
            "applicable_shifts": applicable_shifts,
            "shift_count": len(applicable_shifts),
            "earliest_effective": applicable_shifts[0].get("effective_date", ""),
        }

    # ------------------------------------------------------------------
    # 14. Build transaction facts for display
    # ------------------------------------------------------------------
    transaction_facts: list[dict[str, str]] = []
    for f in case.get("facts", []):
        transaction_facts.append({
            "label": f.get("label", f.get("field_id", "")),
            "value": str(f.get("value", "")),
            "field_id": f.get("field_id", ""),
        })

    # ------------------------------------------------------------------
    # 15. Determine escalation summary
    # ------------------------------------------------------------------
    escalation_parts: list[str] = []
    if risk_factors:
        escalation_parts.append(
            f"{len(risk_factors)} risk factor(s) identified"
        )
    if contrary_count > 0:
        escalation_parts.append(
            f"{contrary_count} contrary comparable case(s) found"
        )
    if applicable_shifts:
        escalation_parts.append(
            f"{len(applicable_shifts)} pending policy shift(s) may affect outcome"
        )
    if confidence_display == "Low":
        escalation_parts.append("Low confidence -- claims adjuster review recommended")
    escalation_summary = "; ".join(escalation_parts) if escalation_parts else "No escalation factors"

    # ------------------------------------------------------------------
    # 16. Build the primary typology
    # ------------------------------------------------------------------
    primary_typology: str | None = None
    if case_facts.get("flag.staged_accident"):
        primary_typology = "staged_accident"
    elif case_facts.get("flag.fraud_indicator"):
        primary_typology = "fraud"
    elif case_facts.get("screening.siu_referral"):
        primary_typology = "siu_referral"
    elif case_facts.get("claim.injury_type") == "catastrophic":
        primary_typology = "catastrophic_injury"

    # ------------------------------------------------------------------
    # 17. Determine regulatory and investigation status
    # ------------------------------------------------------------------
    regulatory_status = "clear"
    investigation_state = "none"

    if proposed_disp_raw == "REFER_SIU":
        regulatory_status = "siu_referral"
        investigation_state = "referred"
    elif proposed_disp_raw == "INVESTIGATE":
        investigation_state = "pending"
    elif proposed_disp_raw == "DENY_CLAIM":
        regulatory_status = "denial"

    if applicable_shifts:
        for shift in applicable_shifts:
            if "fraud" in shift.get("id", "").lower():
                regulatory_status = "fraud_review"

    # ------------------------------------------------------------------
    # 18. Build pattern summary
    # ------------------------------------------------------------------
    if pool_size > 0:
        dominant_outcome = max(outcome_dist.items(), key=lambda x: x[1])
        pattern_summary = (
            f"Among {pool_size} comparable cases, {dominant_outcome[1]} "
            f"({round(dominant_outcome[1] / pool_size * 100)}%) resulted in "
            f"{dominant_outcome[0].replace('_', ' ').lower()}. "
            f"Average similarity to comparable pool is {match_rate}%."
        )
    else:
        pattern_summary = "No comparable cases found in the precedent pool."

    # ------------------------------------------------------------------
    # 19. Assemble the report
    # ------------------------------------------------------------------
    decision_status = _DISPOSITION_TO_STATUS.get(proposed_disp_raw, "investigate")
    action = _DISPOSITION_TO_ACTION.get(proposed_disp_raw, proposed_disp_raw)

    posture = _build_posture_statement(alignment_pct, proposed_disp_raw, coverage_line)

    report: dict[str, Any] = {
        # Identity
        "decision_id": case["id"],
        "case_id": case["id"],
        "timestamp": iso_now,
        "jurisdiction": case_facts.get("jurisdiction_regime", "CA-ON"),
        "domain": "insurance_claims",
        "engine_version": _ENGINE_VERSION,
        "policy_version": _POLICY_VERSION,

        # Decision
        "verdict": expected_verdict,
        "action": action,
        "decision_status": decision_status,
        "decision_explainer": _compute_explainer(
            proposed_disp_raw, confidence_display,
            supporting_count, pool_size, coverage_line,
        ),
        "str_required": False,

        # Canonical outcome
        "canonical_outcome": {
            "disposition": proposed_disp_raw,
            "disposition_basis": proposed_basis,
            "reporting": _seed_reporting_for_case(case_facts, proposed_disp_raw),
        },

        # Classification
        "primary_typology": primary_typology,
        "regulatory_status": regulatory_status,
        "investigation_state": investigation_state,

        # Confidence
        "decision_confidence": confidence_display,
        "decision_confidence_score": confidence_score,
        "decision_confidence_reason": confidence_reason,

        # Precedent metrics
        "precedent_alignment_pct": alignment_pct,
        "precedent_match_rate": match_rate,
        "scored_precedent_count": pool_size,
        "total_comparable_pool": len(passing_seeds),

        # Enhanced precedent (v3 panel)
        "enhanced_precedent": {
            "confidence_level": confidence_result.level.value,
            "confidence_dimensions": confidence_dimensions,
            "confidence_bottleneck": confidence_result.bottleneck,
            "governed_alignment_count": decisive_supporting,
            "governed_alignment_total": decisive_total,
            "institutional_posture": posture,
            "pattern_summary": pattern_summary,
            "sample_cases": sample_cases,
            "driver_causality": {
                "shared": shared_list,
                "divergent": divergent_list,
            },
            "outcome_distribution": outcome_dist,
            "regime_analysis": regime_analysis,
        },

        # Precedent analysis
        "precedent_analysis": {
            "available": pool_size > 0,
            "match_count": pool_size,
            "sample_size": len(seeds),
            "supporting_precedents": supporting_count,
            "contrary_precedents": contrary_count,
            "neutral_precedents": neutral_count,
            "precedent_confidence": round(confidence_result.numeric_value, 4),
            "sample_cases": sample_cases,
            "overlap_outcome_distribution": outcome_dist,
        },

        # Facts display
        "transaction_facts": transaction_facts,

        # Gate results
        "gate1_passed": True,
        "gate1_decision": (
            f"Comparability gates passed: {len(passing_seeds)} of {len(seeds)} "
            f"seeds are comparable to this case"
        ),

        # Risk factors
        "risk_factors": risk_factors,
        "decision_drivers": decision_drivers_list,

        # Escalation
        "escalation_summary": escalation_summary,

        # Insurance-specific
        "source_type": "demo",
        "is_seed": False,
    }

    return report


# ---------------------------------------------------------------------------
# Internal helper for canonical_outcome reporting field
# ---------------------------------------------------------------------------

def _seed_reporting_for_case(case_facts: dict[str, Any], disposition: str) -> str:
    """Determine the reporting obligation for the case based on disposition
    and case signals.

    Insurance claims use NO_FILING / FSRA_NOTICE / FRAUD_REPORT.
    """
    if disposition in ("REFER_SIU",):
        return "FRAUD_REPORT"
    if disposition == "DENY_CLAIM" and case_facts.get("flag.fraud_indicator"):
        return "FRAUD_REPORT"
    if case_facts.get("claim.amount_band") in ("100k_500k", "over_500k"):
        return "FSRA_NOTICE"
    return "NO_FILING"


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "build_report",
]
