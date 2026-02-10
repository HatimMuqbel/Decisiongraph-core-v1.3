"""Derive — Stage B of the Report Compiler Pipeline.

Deterministic domain logic applied on top of a NormalizedDecision.
Produces a DerivedRegulatoryModel with:
  - classification result
  - resolved typology
  - regulatory status + investigation state
  - canonical outcome (disposition + disposition_basis + reporting)
  - decision drivers
  - confidence score
  - integrity & deviation alerts
  - governance corrections (explicit, never silent)
  - defensibility check
  - EDD recommendations (risk-proportionate)
  - SLA timeline

This layer may produce "recommended corrections" but never silently
mutates the original decision; corrections are first-class objects.
"""

import re
from datetime import datetime, timedelta
from typing import Optional

from service.suspicion_classifier import classify as classify_suspicion, CLASSIFIER_VERSION

# ── TYPOLOGY CODE MAP ─────────────────────────────────────────────────────────

_TYPOLOGY_CODE_MAP: dict[str, str] = {
    "aml_inv_struct": "Structuring",
    "aml_str_layer": "Layering",
    "aml_tpr_associated": "Third-party funneling",
    "aml_round_trip": "Round-trip transactions",
    "aml_trade": "Trade-based laundering",
    "aml_shell": "Shell entity layering",
    "aml_crypto": "Virtual asset laundering",
    "sanctions_block": "Sanctions exposure",
    "structuring": "Structuring",
    "layering": "Layering",
    "round_trip": "Round-trip transactions",
    "trade_based": "Trade-based laundering",
    "shell_entity": "Shell entity layering",
    "virtual_asset": "Virtual asset laundering",
    "third_party": "Third-party funneling",
    "smurfing": "Structuring (smurfing)",
    "funnel_account": "Funnel account activity",
    "terrorist_financing": "Terrorist financing",
}

_WORKFLOW_WORDS = frozenset({
    "investigate", "escalate", "review", "monitor",
    "unknown", "pass", "fail", "hard_stop", "str",
    "no report", "edd required", "under review",
})

# Tier-1 code → typology label (used when classifier is authoritative)
_T1_CODE_TO_TYPOLOGY: dict[str, str] = {
    "STRUCTURING_PATTERN": "Structuring",
    "LAYERING": "Layering",
    "FUNNEL": "Funnel account activity",
    "THIRD_PARTY_UNEXPLAINED": "Third-party funneling",
    "FALSE_SOURCE": "False source of funds",
    "SHELL_ENTITY": "Shell entity layering",
    "EVASION_BEHAVIOR": "Evasion behavior",
    "SAR_PATTERN": "SAR pattern",
    "ROUND_TRIP": "Round-trip transactions",
    "TRADE_BASED_LAUNDERING": "Trade-based laundering",
    "VIRTUAL_ASSET_LAUNDERING": "Virtual asset laundering",
    "TERRORIST_FINANCING": "Terrorist financing",
    "SANCTIONS_SIGNAL": "Sanctions exposure",
    "ADVERSE_MEDIA_CONFIRMED": "Adverse media (confirmed)",
}


# ── Public API ────────────────────────────────────────────────────────────────

def derive_regulatory_model(normalized: dict) -> dict:
    """Main entry point.  Returns a ``DerivedRegulatoryModel`` dict."""

    # Unpack normalized fields we need
    verdict = normalized["verdict"]
    str_required = normalized["str_required"]
    gate1_passed = normalized["gate1_passed"]
    rules_fired = normalized["rules_fired"]
    evidence_used = normalized["evidence_used"]
    layer1_facts = normalized["layer1_facts"]
    layer4_typologies = normalized["layer4_typologies"]
    layer6_suspicion = normalized["layer6_suspicion"]
    precedent_analysis = normalized["precedent_analysis"]
    rationale_summary = normalized["rationale_summary"]
    classifier_override = normalized["classifier_override"]

    # ── 1. Decision status / explainer ────────────────────────────────────
    decision_status, decision_explainer = _resolve_decision_status(
        verdict, str_required, rationale_summary,
    )

    # ── 2. Regulatory status ─────────────────────────────────────────────
    regulatory_status = _resolve_regulatory_status(decision_status, str_required)
    investigation_state = _resolve_investigation_state(decision_status, str_required)

    # ── 3. Classification ─────────────────────────────────────────────────
    classification = classify_suspicion(
        evidence_used=evidence_used,
        rules_fired=rules_fired,
        layer4_typologies=layer4_typologies,
        layer6_suspicion=layer6_suspicion,
        layer1_facts=layer1_facts,
        precedent_analysis=precedent_analysis,
    )

    # ── 4. Typology (gated through classifier) ───────────────────────────
    primary_typology = _resolve_typology(
        layer4_typologies=layer4_typologies,
        rules_fired=rules_fired,
        layer6_suspicion=layer6_suspicion,
        classifier_result=classification.to_dict(),
    )

    # ── 4b. Engine vs Governed dispositions ───────────────────────────────
    # Engine disposition = what the rules/verdict originally produced.
    # Governed disposition = what the classifier sovereignty enforces.
    # All downstream alerts & narrative compare against *governed*.
    engine_disposition = _disposition_label(decision_status, str_required)

    # ── 5. Integrity alerts + governance corrections ─────────────────────
    integrity_alert, corrections = _detect_integrity_issues(
        classifier_override=classifier_override,
        classification=classification,
        str_required=str_required,
        decision_status=decision_status,
        verdict=verdict,
        gate1_passed=gate1_passed,
    )

    # Apply corrections (explicit — not hidden)
    if corrections:
        regulatory_status = corrections.get("regulatory_status", regulatory_status)
        str_required = corrections.get("str_required", str_required)
        decision_status = corrections.get("decision_status", decision_status)
        investigation_state = corrections.get("investigation_state", investigation_state)

        # FIX-020: Rebuild explainer to match corrected state.
        # The original explainer was derived from the raw verdict BEFORE corrections.
        # Without this, "No suspicious activity" appears on cases with Tier 1 signals.
        decision_explainer = _rebuild_corrected_explainer(
            decision_status, str_required, classification,
            integrity_alert, rationale_summary,
        )

    # Governed disposition is computed AFTER corrections are applied.
    governed_disposition = _disposition_label(decision_status, str_required)

    # ── 5b. FIX-022: Display verdict + governed rationale ─────────────────
    # The raw verdict ("PASS") and raw rationale ("Pass. No escalation
    # required.") must NOT appear as the primary display values when
    # corrections have changed the actual state.
    if corrections and integrity_alert:
        alert_type = integrity_alert.get("type", "")
        if alert_type == "CLASSIFICATION_DISPOSITION_CONFLICT":
            display_verdict = "PENDING_REVIEW"
        elif decision_status == "review":
            display_verdict = "EDD_REQUIRED"
        elif decision_status == "escalate" and str_required:
            display_verdict = "STR_REQUIRED"
        else:
            display_verdict = governed_disposition
        # Governed rationale replaces canned engine rationale
        governed_rationale = decision_explainer
    else:
        display_verdict = verdict
        governed_rationale = None

    # ── 6. Precedent deviation alert ──────────────────────────────────────
    deviation_alert = _detect_precedent_deviation(
        precedent_analysis=precedent_analysis,
        governed_disposition=governed_disposition,
        engine_disposition=engine_disposition,
    )

    # ── 7. Risk factors ──────────────────────────────────────────────────
    risk_factors = _build_risk_factors(normalized)

    # ── 8. Confidence ─────────────────────────────────────────────────────
    # HARD-STOP CONTRACT: When a CRITICAL integrity alert exists,
    # confidence is meaningless. Do NOT compute or overwrite.
    if integrity_alert and integrity_alert.get("severity") == "CRITICAL":
        conf_label = "Integrity Review Required"
        conf_reason = (
            "Confidence cannot be computed when a control contradiction exists. "
            "Rule outcome conflicts with suspicion classifier."
        )
        conf_score = 0
        # Intentionally skip _compute_confidence_score — not even for debug.
    else:
        conf_label, conf_reason, conf_score = _compute_confidence_score(
            rules_fired=rules_fired,
            evidence_used=evidence_used,
            precedent_analysis=precedent_analysis,
            risk_factors=risk_factors,
        )

    # ── 8b. Output validation confidence cap ───────────────────────────
    # validate_output.py may attach _confidence_cap when evidence is
    # incomplete. Respect it by clamping the confidence band.
    _cap = normalized.get("_confidence_cap")
    if _cap == "Low" and conf_label not in ("Integrity Review Required",):
        _cap_reason = precedent_analysis.get("_confidence_cap_reason", "")
        conf_label = "Low \u2014 Manual Review Required"
        conf_reason = ((_cap_reason + " " + conf_reason) if _cap_reason else conf_reason).strip()
        conf_score = min(conf_score, 39)

    # ── 9. Decision drivers ──────────────────────────────────────────────
    decision_drivers = _derive_decision_drivers(
        rules_fired=rules_fired,
        risk_factors=risk_factors,
        layer4_typologies=layer4_typologies,
        layer6_suspicion=layer6_suspicion,
        gate1_passed=gate1_passed,
        str_required=str_required,
        evidence_used=evidence_used,
        layer1_facts=layer1_facts,
        decision_status=decision_status,
    )

    # ── 9b. FIX-013: Override Justification Block ────────────────────────
    override_justification = _build_override_justification(
        integrity_alert=integrity_alert,
        classification=classification,
        gate2_sections=normalized.get("gate2_sections", []),
        gate2_decision=normalized.get("gate2_decision", ""),
        gate2_status=normalized.get("gate2_status", ""),
        str_required=str_required,
        evidence_used=evidence_used,
    )

    # ── 10. Similarity summary ────────────────────────────────────────────
    similarity_summary = _derive_similarity_summary(precedent_analysis)

    # ── 10b. FIX-018: Enhanced precedent analysis ─────────────────────────
    enhanced_precedent = _build_enhanced_precedent_analysis(
        precedent_analysis=precedent_analysis,
        governed_disposition=governed_disposition,
        deviation_alert=deviation_alert,
        classification_outcome=classification.outcome,
    )

    # ── 11. Escalation summary ────────────────────────────────────────────
    escalation_summary = _build_escalation_summary(decision_status, str_required)

    # ── 12. Regulatory position ───────────────────────────────────────────
    if str_required:
        regulatory_position = "Reporting threshold met under applicable regulatory guidance."
    else:
        regulatory_position = "Suspicion threshold not met based on available indicators."

    # ── 13. FIX-001: Canonical outcome (three-field) ─────────────────────
    disposition_basis = _derive_disposition_basis(rules_fired, governed_disposition)
    reporting, reporting_note = _derive_reporting(governed_disposition, str_required)
    canonical_outcome = {
        "disposition": governed_disposition,
        "disposition_basis": disposition_basis,
        "reporting": reporting,
        "reporting_note": reporting_note,
    }

    # ── 14. FIX-006: Defensibility check ─────────────────────────────────
    defensibility_check = _build_defensibility_check(
        reporting, reporting_note, deviation_alert,
    )

    # ── 15. FIX-007: EDD recommendations ─────────────────────────────────
    edd_recommendations = _derive_edd_recommendations(
        evidence_used=evidence_used,
        rules_fired=rules_fired,
        governed_disposition=governed_disposition,
    )

    # ── 15b. FIX-015: Decision-outcome-aware analyst actions ─────────────
    analyst_actions = _derive_analyst_actions(
        governed_disposition=governed_disposition,
        verdict=verdict,
        str_required=str_required,
        suspicion_count=classification.suspicion_count,
        investigative_count=classification.investigative_count,
        integrity_alert=integrity_alert,
    )

    # ── 15c. Output validation action constraints ──────────────────────
    # validate_output.py may pre-compute action constraints.
    _pre = normalized.get("_validation", {})
    if _pre.get("block_approve"):
        analyst_actions = [
            a for a in analyst_actions
            if "Approve" not in a.get("label", "")
            and "Confirm Clearance" not in a.get("label", "")
        ]
    if _pre.get("hard_stop"):
        _allowed = {"Acknowledge", "Request Additional Information", "Expand to Reviewer View"}
        analyst_actions = [a for a in analyst_actions if a.get("label") in _allowed]

    # ── 16. FIX-009: SLA timeline ────────────────────────────────────────
    timestamp = normalized.get("timestamp", "")
    sla_timeline = _build_sla_timeline(timestamp, governed_disposition, reporting)

    # ── 16b. FIX-016: EDD consistency check ─────────────────────────────
    # If escalation summary mentions EDD but timeline has no EDD deadline,
    # or if governed disposition is NO_REPORT/STR_REQUIRED but narrative
    # references EDD, fix the inconsistency.
    edd_consistency_alert = None
    _edd_in_narrative = "enhanced due diligence" in escalation_summary.lower()
    _edd_deadline_set = sla_timeline.get("edd_deadline", "N/A") != "N/A"

    if _edd_in_narrative and not _edd_deadline_set:
        # Narrative says EDD but deadline is N/A — force-populate deadline
        if governed_disposition in ("STR_REQUIRED",):
            # STR cases: EDD is a procedural step, populate a 7-day window
            try:
                _ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00")) if timestamp else datetime.utcnow()
            except (ValueError, AttributeError):
                _ts = datetime.utcnow()
            bd, d = 0, _ts
            while bd < 7:
                d += timedelta(days=1)
                if d.weekday() < 5:
                    bd += 1
            sla_timeline["edd_deadline"] = d.replace(hour=23, minute=59, second=59).isoformat() + "Z"
            edd_consistency_alert = {
                "type": "EDD_DEADLINE_POPULATED",
                "severity": "INFO",
                "message": "EDD deadline auto-populated to align with narrative reference.",
            }
        else:
            # Non-STR escalation: should already have deadline — force-populate
            try:
                _ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00")) if timestamp else datetime.utcnow()
            except (ValueError, AttributeError):
                _ts = datetime.utcnow()
            bd, d = 0, _ts
            while bd < 5:
                d += timedelta(days=1)
                if d.weekday() < 5:
                    bd += 1
            sla_timeline["edd_deadline"] = d.replace(hour=23, minute=59, second=59).isoformat() + "Z"
            edd_consistency_alert = {
                "type": "EDD_DEADLINE_POPULATED",
                "severity": "INFO",
                "message": "EDD deadline auto-populated to align with narrative reference.",
            }

    if not _edd_in_narrative and governed_disposition == "NO_REPORT":
        # Correct: no EDD mention for cleared cases
        pass
    elif governed_disposition == "NO_REPORT" and _edd_in_narrative:
        # Contradiction: cleared but mentions EDD
        escalation_summary = "No escalation or reporting obligation was triggered based on available indicators."
        edd_consistency_alert = {
            "type": "EDD_NARRATIVE_CORRECTED",
            "severity": "INFO",
            "message": "EDD reference removed from cleared case narrative.",
        }

    # ── 17. FIX-005: Precedent match rate ─────────────────────────────────
    _pa = precedent_analysis or {}
    scored_count = int(
        (_pa.get("supporting_precedents", 0) or 0)
        + (_pa.get("contrary_precedents", 0) or 0)
        + (_pa.get("neutral_precedents", 0) or 0)
    )
    total_pool = int(
        _pa.get("match_count", 0) or 0
    )
    precedent_match_rate = (
        int(scored_count / total_pool * 100) if total_pool > 0 else 0
    )
    # Precedent alignment: supporting_decisive / decisive_count
    _supporting = int(_pa.get("supporting_precedents", 0) or 0)
    _contrary = int(_pa.get("contrary_precedents", 0) or 0)
    decisive_count = _supporting + _contrary
    precedent_alignment_pct = (
        int(_supporting / decisive_count * 100) if decisive_count > 0 else 0
    )

    # FIX-019: Precedent minimum pool threshold
    _MIN_PRECEDENT_POOL = 5
    precedent_pool_warning = None
    _total_scored = _supporting + _contrary + int(_pa.get("neutral_precedents", 0) or 0)
    if _pa.get("available") and 0 < _total_scored < _MIN_PRECEDENT_POOL:
        precedent_pool_warning = {
            "type": "THIN_PRECEDENT_POOL",
            "severity": "WARNING",
            "pool_size": _total_scored,
            "minimum_required": _MIN_PRECEDENT_POOL,
            "message": (
                f"Precedent pool below minimum threshold (n={_total_scored}, "
                f"required ≥{_MIN_PRECEDENT_POOL}). Percentage-based confidence "
                f"metrics are unreliable at this sample size. Manual review required."
            ),
        }

    # FIX-021: Precedent-classifier consistency override
    # When classifier outcome has zero precedent support but precedents
    # unanimously agree on a different outcome, that IS a consistency concern.
    _final_consistency_alert = classification.precedent_consistency_alert
    _final_consistency_detail = classification.precedent_consistency_detail

    if (
        not _final_consistency_alert
        and _pa.get("available")
        and _total_scored > 0
        and classification.outcome in ("STR_REQUIRED",)
        and _supporting == 0
    ):
        _outcome_dist = (
            _pa.get("match_outcome_distribution")
            or _pa.get("outcome_distribution")
            or {}
        )
        if _outcome_dist:
            _dominant = max(_outcome_dist, key=_outcome_dist.get)
            _dominant_count = _outcome_dist.get(_dominant, 0)
            _dominant_label = str(_dominant).upper().replace("_", " ")
            # If ≥80% of precedents agree on one outcome that differs from classifier
            if _dominant_count > 0 and _dominant_count >= _total_scored * 0.8:
                _agrees_with_governed = (
                    str(_dominant).upper().replace(" ", "_") == governed_disposition
                )
                _final_consistency_alert = True
                _final_consistency_detail = (
                    f"All {_total_scored} comparable precedents resulted in "
                    f"{_dominant_label}. Classifier determination of "
                    f"{classification.outcome.replace('_', ' ')} has no historical "
                    f"precedent support."
                    + (
                        f" Precedents are consistent with the governed disposition "
                        f"({governed_disposition.replace('_', ' ')})."
                        if _agrees_with_governed else ""
                    )
                    + " This divergence should be reviewed by the compliance "
                    "officer as part of the STR determination."
                )

    return {
        # Classification
        "classification": classification.to_dict(),
        "classification_outcome": classification.outcome,
        "classification_reason": classification.outcome_reason,
        "tier1_signals": classification.tier1_signals,
        "tier2_signals": classification.tier2_signals,
        "suspicion_count": classification.suspicion_count,
        "investigative_count": classification.investigative_count,
        "precedent_consistency_alert": _final_consistency_alert,
        "precedent_consistency_detail": _final_consistency_detail,
        "classifier_version": CLASSIFIER_VERSION,

        # Typology
        "primary_typology": primary_typology,

        # Regulatory outcome (governed)
        "regulatory_status": regulatory_status,
        "investigation_state": investigation_state,
        "decision_status": decision_status,
        "decision_explainer": decision_explainer,
        "str_required": str_required,
        "regulatory_position": regulatory_position,
        "regulatory_obligation": (
            "STR filing required under FINTRAC guidance"
            if str_required else ""
        ),
        "escalation_summary": escalation_summary,

        # FIX-001: Canonical outcome (three-field)
        "canonical_outcome": canonical_outcome,

        # Confidence
        "decision_confidence": conf_label,
        "decision_confidence_reason": conf_reason,
        "decision_confidence_score": conf_score,

        # FIX-005: Distinct precedent metrics
        "precedent_alignment_pct": precedent_alignment_pct,
        "precedent_match_rate": precedent_match_rate,
        "scored_precedent_count": scored_count,
        "total_comparable_pool": total_pool,

        # FIX-019: Precedent pool threshold warning
        "precedent_pool_warning": precedent_pool_warning,

        # Drivers
        "decision_drivers": decision_drivers,

        # Engine vs Governed dispositions (for audit transparency)
        "engine_disposition": engine_disposition,
        "governed_disposition": governed_disposition,

        # FIX-022: Display verdict + governed rationale
        "display_verdict": display_verdict,
        "governed_rationale": governed_rationale,

        # Alerts (first-class objects)
        "decision_integrity_alert": integrity_alert,
        "override_justification": override_justification,
        "precedent_deviation_alert": deviation_alert,
        "corrections_applied": corrections or {},

        # Risk & similarity
        "risk_factors": risk_factors,
        "similarity_summary": similarity_summary,

        # FIX-018: Enhanced precedent analysis
        "enhanced_precedent": enhanced_precedent,

        # FIX-006: Defensibility check
        "defensibility_check": defensibility_check,

        # FIX-007: EDD recommendations
        "edd_recommendations": edd_recommendations,

        # FIX-009: SLA timeline
        "sla_timeline": sla_timeline,

        # FIX-013: Override justification (already added above)

        # FIX-015: Analyst actions (outcome-aware)
        "analyst_actions": analyst_actions,

        # FIX-016: EDD consistency
        "edd_consistency_alert": edd_consistency_alert,
    }


# ── Decision status / explainer ──────────────────────────────────────────────

def _resolve_decision_status(
    verdict: str, str_required: bool, rationale_summary: str,
) -> tuple[str, str]:
    """Map verdict to one of: pass | escalate | review + explainer text.

    v2 spec §4.2 mapping:
      PASS / APPROVE          → pass  (ALLOW)
      PASS_WITH_EDD / HOLD    → review (EDD)
      ESCALATE / HARD_STOP    → escalate (BLOCK / STR)
    """
    v = verdict.upper()

    # PASS_WITH_EDD is EDD — NOT a clearance (v2 spec §4.2)
    if v == "PASS_WITH_EDD":
        return "review", rationale_summary or "Enhanced Due Diligence required before final disposition."

    if v in ("PASS",) or v.startswith("APPROVE"):
        return "pass", "No suspicious activity indicators detected. Transaction may proceed."
    if (
        v in ("HARD_STOP", "STR", "ESCALATE")
        or v.startswith("BLOCK")
        or v.startswith("DECLINE")
        or v.startswith("ESCALATE")
        or v.startswith("INVESTIGATE")
    ):
        return "escalate", rationale_summary or "Suspicious indicators detected requiring escalation."
    if v.startswith("HOLD"):
        return "review", rationale_summary or "Transaction under enhanced due diligence review."
    return "review", rationale_summary or "Transaction under enhanced due diligence review."


def _resolve_regulatory_status(decision_status: str, str_required: bool) -> str:
    if str_required:
        return "STR REQUIRED"
    if decision_status == "escalate":
        return "ESCALATE"
    if decision_status == "pass":
        return "NO REPORT"
    return "EDD REQUIRED"


def _resolve_investigation_state(decision_status: str, str_required: bool) -> str:
    if decision_status == "pass":
        return "CLEARED"
    if str_required or decision_status == "escalate":
        return "EDD REQUIRED"
    return "UNDER REVIEW"


def _rebuild_corrected_explainer(
    decision_status: str,
    str_required: bool,
    classification,
    integrity_alert: dict | None,
    rationale_summary: str,
) -> str:
    """Rebuild decision explainer after governance corrections.

    FIX-020: The original explainer was derived from the raw verdict BEFORE
    corrections.  After corrections change decision_status, the explainer must
    reflect the corrected state — not the overridden engine output.

    Prevents "No suspicious activity" from appearing on cases with Tier 1
    suspicion indicators.
    """
    alert_type = integrity_alert.get("type", "") if integrity_alert else ""

    if alert_type == "CLASSIFICATION_DISPOSITION_CONFLICT":
        tier1_count = integrity_alert.get("tier1_count", 0)
        return (
            f"Classifier identified {tier1_count} Tier 1 suspicion indicator(s) "
            f"warranting STR review, but the engine verdict does not support "
            f"escalation. Enhanced Due Diligence with compliance officer review "
            f"is required before final regulatory determination. This case "
            f"cannot be cleared without review."
        )

    if alert_type == "CONTROL_CONTRADICTION":
        if decision_status == "review":
            return (
                "Governance correction applied: STR determination removed due to "
                "insufficient Tier 1 evidence. Enhanced Due Diligence required."
            )
        return (
            "Governance correction applied: STR determination removed due to "
            "insufficient Tier 1 evidence. Case cleared — no reporting obligation."
        )

    if alert_type == "ESCALATION_WITHOUT_SUSPICION":
        if decision_status == "review":
            return (
                "Escalation corrected: insufficient Tier 1 suspicion indicators. "
                "Enhanced Due Diligence required before final determination."
            )
        return (
            "Escalation corrected: insufficient Tier 1 suspicion indicators. "
            "Case cleared — no reporting obligation."
        )

    if alert_type == "CLASSIFIER_UPGRADE":
        return (
            "Classifier sovereignty applied: reporting obligation upgraded to STR "
            "based on Tier 1 suspicion indicators."
        )

    # Generic fallback — re-derive from corrected status
    if decision_status == "review":
        return rationale_summary or "Enhanced Due Diligence required before final disposition."
    if decision_status == "pass":
        return "No suspicious activity indicators detected. Transaction may proceed."
    if decision_status == "escalate":
        return rationale_summary or "Suspicious indicators detected requiring escalation."
    return rationale_summary or "Transaction under review."


# ── Escalation summary ──────────────────────────────────────────────────────

def _build_escalation_summary(decision_status: str, str_required: bool) -> str:
    if str_required:
        return (
            "Suspicion indicators triggered reporting thresholds under FINTRAC guidance. "
            "While Enhanced Due Diligence is required to complete the investigation, "
            "the current suspicion level independently meets the reporting threshold."
        )
    if decision_status == "review":
        return "Enhanced Due Diligence is required to complete the investigation and finalize the regulatory outcome."
    if decision_status == "pass":
        return "No escalation or reporting obligation was triggered based on available indicators."
    return "Escalation is required to complete the investigation and determine any reporting obligations."


# ── Typology resolver ────────────────────────────────────────────────────────

def _resolve_typology(
    layer4_typologies: dict,
    rules_fired: list,
    layer6_suspicion: dict,
    classifier_result: dict | None = None,
) -> str:
    """Resolve primary typology from decision layers. Never from verdict.

    REGULATORY INVARIANT: Typology must only come from Tier 1 indicators.
    """
    # ── CLASSIFIER GATE ──────────────────────────────────────────────────
    if classifier_result is not None:
        tier1_count = classifier_result.get("suspicion_count", 0)
        if tier1_count == 0:
            return "No suspicious typology identified"

        tier1_codes = {
            s.get("code", "").upper()
            for s in classifier_result.get("tier1_signals", [])
        }
        for code in tier1_codes:
            if code in _T1_CODE_TO_TYPOLOGY:
                return _T1_CODE_TO_TYPOLOGY[code]
        if tier1_codes:
            first_code = next(iter(tier1_codes))
            return first_code.replace("_", " ").title()

    # ── FALLBACK: Legacy path ────────────────────────────────────────────
    typologies = layer4_typologies.get("typologies", []) or []
    for typ in typologies:
        raw = typ.get("name") if isinstance(typ, dict) else str(typ)
        if not raw:
            continue
        paren_match = re.search(r'\(([^)]+)\)', raw)
        if paren_match:
            raw = paren_match.group(1).strip()
        tokens = raw.split(None, 1)
        if tokens and tokens[0].lower() in _WORKFLOW_WORDS:
            raw = tokens[1] if len(tokens) > 1 else ""
        if raw and raw.lower() not in _WORKFLOW_WORDS:
            mapped = _TYPOLOGY_CODE_MAP.get(raw.lower().replace(" ", "_").replace("-", "_"))
            return mapped or raw

    for rule in rules_fired:
        code = str(rule.get("code", "")).lower().replace("-", "_")
        if code in _TYPOLOGY_CODE_MAP:
            return _TYPOLOGY_CODE_MAP[code]
        for key, label in _TYPOLOGY_CODE_MAP.items():
            if key in code:
                return label

    elements = layer6_suspicion.get("elements", {}) or {}
    for element, active in elements.items():
        if active:
            code = element.lower().replace(" ", "_").replace("-", "_")
            if code in _TYPOLOGY_CODE_MAP:
                return _TYPOLOGY_CODE_MAP[code]
            mapped = _map_driver_label(element)
            if mapped:
                return mapped.split(" (")[0]

    return "No suspicious typology identified"


# ── Confidence ────────────────────────────────────────────────────────────────

def _compute_confidence_score(
    rules_fired: list,
    evidence_used: list,
    precedent_analysis: dict,
    risk_factors: list,
) -> tuple[str, str, int]:
    """Deterministic confidence.  Returns (label, reason, score)."""
    score = 0

    triggered = [
        r for r in rules_fired
        if str(r.get("result", "")).upper() in {"TRIGGERED", "ACTIVATED", "FAIL", "FAILED"}
    ]
    if len(triggered) >= 3:
        score += 30
    elif len(triggered) >= 1:
        score += 20
    elif rules_fired:
        score += 10

    ev_count = len(evidence_used or [])
    if ev_count >= 10:
        score += 25
    elif ev_count >= 5:
        score += 18
    elif ev_count >= 1:
        score += 10

    if precedent_analysis and precedent_analysis.get("available"):
        # v3 governed confidence: use confidence_level directly
        if precedent_analysis.get("confidence_model_version") == "v3":
            v3_level = (precedent_analysis.get("confidence_level") or "").upper()
            if v3_level == "VERY_HIGH":
                score += 30
            elif v3_level == "HIGH":
                score += 25
            elif v3_level == "MODERATE":
                score += 15
            elif v3_level == "LOW":
                score += 5
            # NONE → 0 points
        else:
            # v2 path
            decisive_total = int(precedent_analysis.get("decisive_total", -1))
            try:
                conf = float(precedent_analysis.get("precedent_confidence", 0) or 0)
            except (TypeError, ValueError):
                conf = 0.0
            # When decisive_total == 0, confidence is a meaningless 0.5 fallback.
            # Don't inflate the score — no terminal precedents means no signal.
            if decisive_total == 0:
                score += 0  # Explicit: no precedent signal available
            elif conf >= 0.75:
                score += 30
            elif conf >= 0.45:
                score += 20
            elif conf > 0:
                score += 10

    contrary = int(precedent_analysis.get("contrary_precedents", 0) or 0) if precedent_analysis else 0
    if contrary == 0:
        score += 15
    elif contrary <= 2:
        score += 8

    score = min(100, max(0, score))

    # FIX-017: Institutional confidence thresholds
    # Bands: <40% = Low (manual review required), 40-70% = Moderate, >70% = High
    if score >= 70:
        label = "High"
        reason = "Deterministic rule activation with corroborating precedent alignment."
        threshold_note = "Above institutional confidence threshold (≥70%)."
    elif score >= 40:
        label = "Moderate"
        reason = "Deterministic rule activation with moderate precedent alignment."
        threshold_note = "Within institutional confidence band (40–70%). Standard review process applies."
    else:
        label = "Low — Manual Review Required"
        reason = (
            "Evidence completeness or precedent alignment below institutional threshold. "
            "Below institutional confidence threshold (<40%) — manual senior review required "
            "before final disposition."
        )
        threshold_note = "Below institutional confidence threshold (<40%). Manual review required."

    return label, reason, score


# ── Integrity alerts ─────────────────────────────────────────────────────────

def _detect_integrity_issues(
    classifier_override: dict,
    classification,
    str_required: bool,
    decision_status: str,
    verdict: str,
    gate1_passed: bool = True,
) -> tuple[Optional[dict], Optional[dict]]:
    """Return (alert, corrections) — corrections are explicit, never hidden."""

    # Case 1: Override already applied in main.py
    if classifier_override.get("override_applied"):
        alert = {
            "type": "CLASSIFIER_OVERRIDE",
            "severity": "CRITICAL",
            "message": (
                f"Decision Integrity Alert: Rules engine produced "
                f"{classifier_override.get('original_verdict', 'STR')} "
                f"but classifier determined {classification.outcome}. "
                "Classifier sovereignty enforced — verdict overridden."
            ),
            "original_verdict": classifier_override.get("original_verdict"),
            "classifier_outcome": classification.outcome,
            "override_reason": classifier_override.get("override_reason", ""),
        }
        return alert, None

    # Case 2: STR without Tier 1
    if classification.suspicion_count == 0 and str_required:
        has_investigative = classification.investigative_count > 0
        alert = {
            "type": "CONTROL_CONTRADICTION",
            "severity": "CRITICAL",
            "message": (
                "Decision Integrity Alert: Regulatory status is STR REQUIRED "
                "but Suspicion Classifier found 0 Tier 1 indicators. "
                "These statements cannot legally coexist. "
                "Suspicion threshold not met — STR filing would be unjustified."
            ),
            "original_verdict": verdict,
            "classifier_outcome": classification.outcome,
        }
        corrections = {
            "regulatory_status": "EDD REQUIRED" if has_investigative else "NO REPORT",
            "str_required": False,
            "decision_status": "review" if has_investigative else "pass",
            "investigation_state": "EDD REQUIRED" if has_investigative else "CLEARED",
        }
        return alert, corrections

    # Case 3: Escalation without Tier 1
    if classification.suspicion_count == 0 and decision_status == "escalate":
        has_investigative = classification.investigative_count > 0
        alert = {
            "type": "ESCALATION_WITHOUT_SUSPICION",
            "severity": "WARNING",
            "message": (
                "Decision Integrity Alert: Escalation triggered without "
                f"Tier 1 suspicion indicators (Tier 2: {classification.investigative_count}). "
                "Correct disposition: EDD REQUIRED — not escalation."
            ),
            "original_verdict": verdict,
            "classifier_outcome": classification.outcome,
        }
        corrections = {
            "regulatory_status": "EDD REQUIRED" if has_investigative else "NO REPORT",
            "str_required": False,
            "decision_status": "review" if has_investigative else "pass",
            "investigation_state": "EDD REQUIRED" if has_investigative else "CLEARED",
        }
        return alert, corrections

    # Case 4: Classifier found suspicion + escalation + gate permits
    # The classifier is sovereign — if it says STR_REQUIRED,
    # suspicion_count > 0, AND gate allows, honour that.
    if (
        classification.suspicion_count > 0
        and not str_required
        and decision_status == "escalate"
        and classification.outcome == "STR_REQUIRED"
        and gate1_passed
    ):
        alert = {
            "type": "CLASSIFIER_UPGRADE",
            "severity": "INFO",
            "message": (
                f"Classifier identified {classification.suspicion_count} Tier 1 suspicion "
                f"indicator(s) with STR_REQUIRED outcome. Reporting obligation upgraded "
                f"from UNKNOWN to FILE_STR per classifier sovereignty."
            ),
            "original_verdict": verdict,
            "classifier_outcome": classification.outcome,
        }
        corrections = {
            "str_required": True,
            "regulatory_status": "STR REQUIRED",
            "investigation_state": "STR REQUIRED",
        }
        return alert, corrections

    # Case 5: Classifier says STR_REQUIRED but disposition is not STR
    # (e.g. PASS_WITH_EDD, or gate1 blocks escalation).
    # DO NOT upgrade — generate a CONFLICT alert for compliance review.
    # Per v2 spec INV-001: STR must be determined by compliance officer,
    # not mechanically inferred when gates block.
    if (
        classification.suspicion_count > 0
        and classification.outcome == "STR_REQUIRED"
        and not str_required
        and decision_status != "escalate"
    ):
        governed_label = _disposition_label(decision_status, str_required)
        alert = {
            "type": "CLASSIFICATION_DISPOSITION_CONFLICT",
            "severity": "CRITICAL",
            "message": (
                f"Classifier identified {classification.suspicion_count} Tier 1 suspicion "
                f"indicator(s) and determined STR_REQUIRED, but governed disposition is "
                f"{governed_label}."
                + (" Gate 1 determined insufficient legal basis for escalation." if not gate1_passed else "")
                + " A compliance officer must review the Tier 1 indicators and make "
                "the final STR determination. Until reviewed, EDD applies."
            ),
            "original_verdict": verdict,
            "classifier_outcome": classification.outcome,
            "governed_disposition": governed_label,
            "tier1_count": classification.suspicion_count,
            "gate1_blocked": not gate1_passed,
        }
        # Force to EDD — do NOT leave as "pass" when Tier 1 signals exist
        corrections = {
            "decision_status": "review",
            "regulatory_status": "EDD REQUIRED",
            "investigation_state": "COMPLIANCE REVIEW REQUIRED",
        }
        return alert, corrections

    return None, None


# ── Override Justification Block (FIX-013) ───────────────────────────────────

def _build_override_justification(
    integrity_alert: dict | None,
    classification,
    gate2_sections: list,
    gate2_decision: str,
    gate2_status: str,
    str_required: bool,
    evidence_used: list,
) -> dict | None:
    """Generate a structured Override Justification Block when classifier
    overrides a gate decision.

    This is a defensibility-critical artifact — it explains *why* the
    classifier's sovereignty was exercised and what the gate found
    insufficient.  Must be rendered PROMINENTLY, not buried in metadata.

    Returns None if no override occurred.
    """
    if not integrity_alert:
        return None

    alert_type = integrity_alert.get("type", "")

    # Case A: CLASSIFIER_UPGRADE — Gate 2 said INSUFFICIENT but classifier
    # found Tier 1 signals and upgraded to STR_REQUIRED.
    if alert_type == "CLASSIFIER_UPGRADE":
        # Identify what Gate 2 found insufficient
        gate2_failures = []
        for section in (gate2_sections or []):
            if not section.get("passed"):
                gate2_failures.append({
                    "section": section.get("name", "Unknown"),
                    "reason": section.get("reason", "Insufficient evidence"),
                })

        # Identify the Tier 1 signals that justified the override
        tier1_signals = classification.tier1_signals if hasattr(classification, "tier1_signals") else []
        justifying_signals = []
        for sig in tier1_signals:
            justifying_signals.append({
                "code": sig.get("code", ""),
                "source": sig.get("source", ""),
                "detail": sig.get("detail", ""),
            })

        return {
            "override_type": "CLASSIFIER_UPGRADE",
            "overridden_gate": "Gate 2 (STR Threshold)",
            "gate_decision": gate2_decision or gate2_status or "INSUFFICIENT",
            "gate_deficiencies": gate2_failures or [{"section": "STR Threshold", "reason": "Evidence quality below STR threshold"}],
            "classifier_decision": "STR_REQUIRED",
            "justifying_signals": justifying_signals,
            "justification": (
                f"Gate 2 returned {gate2_decision or gate2_status or 'INSUFFICIENT'} "
                f"due to evidence quality concerns. However, the Suspicion Classifier "
                f"identified {len(justifying_signals)} Tier 1 suspicion indicator(s) "
                f"that independently meet the Reasonable Grounds to Suspect (RGS) "
                f"threshold under PCMLTFA/FINTRAC guidance. Under the classifier "
                f"sovereignty framework, any single Tier 1 indicator is sufficient "
                f"for STR determination regardless of gate evidence scoring."
            ),
            "regulatory_basis": "PCMLTFA s. 7 — Reasonable Grounds to Suspect (RGS) threshold",
            "severity": "INFO",
        }

    # Case B: CLASSIFIER_OVERRIDE — Rules engine said STR but classifier
    # found no Tier 1 signals and downgraded.
    if alert_type == "CLASSIFIER_OVERRIDE":
        original_verdict = integrity_alert.get("original_verdict", "STR")
        return {
            "override_type": "CLASSIFIER_OVERRIDE",
            "overridden_gate": "Rules Engine",
            "gate_decision": original_verdict,
            "gate_deficiencies": [{"section": "Rules Layer", "reason": f"Engine produced {original_verdict} without Tier 1 suspicion indicators"}],
            "classifier_decision": classification.outcome if hasattr(classification, "outcome") else "EDD_REQUIRED",
            "justifying_signals": [],
            "justification": (
                f"Rules engine produced {original_verdict} based on risk indicators, "
                f"but the Suspicion Classifier found 0 Tier 1 suspicion indicators. "
                f"Under PCMLTFA/FINTRAC guidance, STR filing requires Reasonable "
                f"Grounds to Suspect — risk indicators alone are insufficient. "
                f"Disposition corrected to preserve STR threshold integrity."
            ),
            "regulatory_basis": "PCMLTFA s. 7 — STR requires Tier 1 suspicion, not risk alone",
            "severity": "CRITICAL",
        }

    # Case C: CONTROL_CONTRADICTION — similar to CLASSIFIER_OVERRIDE
    if alert_type == "CONTROL_CONTRADICTION":
        return {
            "override_type": "CONTROL_CONTRADICTION",
            "overridden_gate": "Rules Engine / STR Determination",
            "gate_decision": "STR REQUIRED (engine)",
            "gate_deficiencies": [{"section": "STR Determination", "reason": "0 Tier 1 indicators — STR filing would be unjustified"}],
            "classifier_decision": classification.outcome if hasattr(classification, "outcome") else "EDD_REQUIRED",
            "justifying_signals": [],
            "justification": (
                "Regulatory status was STR REQUIRED but Suspicion Classifier "
                "found 0 Tier 1 indicators. These statements cannot legally coexist "
                "under PCMLTFA/FINTRAC. Suspicion threshold not met — corrected to "
                "prevent unjustified STR filing."
            ),
            "regulatory_basis": "PCMLTFA s. 7 — STR requires RGS threshold (Tier 1 ≥ 1)",
            "severity": "CRITICAL",
        }

    # Case D: CLASSIFICATION_DISPOSITION_CONFLICT — Classifier found Tier 1
    # signals (STR_REQUIRED) but governed disposition remains EDD_REQUIRED
    # because gate blocked or verdict was PASS_WITH_EDD.
    if alert_type == "CLASSIFICATION_DISPOSITION_CONFLICT":
        tier1_signals = classification.tier1_signals if hasattr(classification, "tier1_signals") else []
        justifying_signals = [
            {"code": sig.get("code", ""), "source": sig.get("source", ""), "detail": sig.get("detail", "")}
            for sig in tier1_signals
        ]
        governed = integrity_alert.get("governed_disposition", "EDD_REQUIRED")
        return {
            "override_type": "CLASSIFICATION_DISPOSITION_CONFLICT",
            "overridden_gate": "Classifier vs Disposition",
            "gate_decision": governed,
            "gate_deficiencies": [
                {"section": "Gate 1 / Verdict", "reason": f"Governed disposition is {governed} despite Tier 1 signals"}
            ],
            "classifier_decision": "STR_REQUIRED",
            "justifying_signals": justifying_signals,
            "justification": (
                f"Suspicion Classifier identified {len(justifying_signals)} Tier 1 "
                f"indicator(s) that would ordinarily meet the STR threshold, but the "
                f"governed disposition is {governed}."
                + (" Gate 1 determined insufficient legal basis for escalation." if integrity_alert.get("gate1_blocked") else "")
                + " A compliance officer must review the Tier 1 indicators and "
                "make the final STR/no-file determination. EDD with compliance "
                "review is the governed outcome until that determination is made."
            ),
            "regulatory_basis": "PCMLTFA s. 7 — STR determination requires compliance officer review",
            "severity": "CRITICAL",
        }

    return None


# ── Precedent deviation ──────────────────────────────────────────────────────

def _disposition_label(decision_status: str, str_required: bool) -> str:
    """Map internal decision state to a human-readable disposition label."""
    if str_required:
        return "STR_REQUIRED"
    if decision_status == "escalate":
        return "ESCALATE"
    if decision_status == "pass":
        return "NO_REPORT"
    return "EDD_REQUIRED"


# ── FIX-001: Disposition basis + reporting derivation ─────────────────────────

_MANDATORY_RULE_PREFIXES = frozenset({
    "AML_BLOCK_SANCTIONS", "SANCTIONS", "AML_BLOCK", "HARD_STOP",
})

_DISCRETIONARY_RULE_PREFIXES = frozenset({
    "AML_ESC_HR_COUNTRY", "AML_ESC_PEP_SCREEN", "AML_ESC_PEP",
    "AML_ESC_STRUCT", "AML_ESC", "AML_INV",
})


def _derive_disposition_basis(rules_fired: list, governed_disposition: str) -> str:
    """Derive disposition_basis from triggered rule context.

    FIX-023: UNKNOWN replaced with PENDING_REVIEW — compliance documents
    must never display UNKNOWN as a disposition basis.

    MANDATORY  — sanctions or hard-stop rule triggered.
    DISCRETIONARY — risk-based escalation rule triggered.
    PENDING_REVIEW — basis not determinable from triggered rules.
    """
    if governed_disposition == "NO_REPORT":
        return "DISCRETIONARY"

    triggered = [
        r for r in rules_fired
        if str(r.get("result", "")).upper() in {"TRIGGERED", "ACTIVATED", "FAIL", "FAILED", "WARN"}
    ]
    if not triggered:
        return "PENDING_REVIEW"

    for rule in triggered:
        code = str(rule.get("code", "")).upper()
        for prefix in _MANDATORY_RULE_PREFIXES:
            if code.startswith(prefix):
                return "MANDATORY"

    for rule in triggered:
        code = str(rule.get("code", "")).upper()
        for prefix in _DISCRETIONARY_RULE_PREFIXES:
            if code.startswith(prefix):
                return "DISCRETIONARY"

    return "PENDING_REVIEW"


def _derive_reporting(governed_disposition: str, str_required: bool) -> tuple[str, str]:
    """Derive reporting determination and parenthetical reason.

    Returns (reporting_value, reporting_note).
    Reporting is NEVER inferred from disposition — only from explicit signals.

    FIX-023: UNKNOWN replaced with PENDING_COMPLIANCE_REVIEW — a compliance
    report must never say UNKNOWN (auditor reads it as system failure).
    """
    if str_required:
        return "FILE_STR", ""
    if governed_disposition in ("EDD_REQUIRED", "ESCALATE"):
        return "PENDING_COMPLIANCE_REVIEW", "reporting obligation deferred to compliance officer — see Decision Integrity Alert"
    if governed_disposition == "NO_REPORT":
        return "NO_REPORT", ""
    return "PENDING_COMPLIANCE_REVIEW", "reporting obligation deferred to compliance officer"


# ── FIX-007: EDD recommendations from risk factors ───────────────────────────

def _derive_edd_recommendations(
    evidence_used: list,
    rules_fired: list,
    governed_disposition: str,
) -> list[dict]:
    """Generate risk-proportionate EDD recommendations from evidence and rules.

    Each recommendation is {action, reference} where reference is the
    regulatory citation.
    """
    if governed_disposition not in ("EDD_REQUIRED", "ESCALATE"):
        return []

    ev_map: dict[str, object] = {}
    for ev in (evidence_used or []):
        field = str(ev.get("field", "")).lower()
        ev_map[field] = ev.get("value")

    recommendations: list[dict] = []

    # PEP
    pep = ev_map.get("flag.pep") or ev_map.get("customer.pep_flag")
    if pep is True or str(pep).lower() == "true":
        recommendations.append({
            "action": "Verify source of wealth and source of funds.",
            "reference": "PCMLTFA Regulations s. 67.1 — PEP enhanced measures",
        })

    # Cross-border to high-risk country
    cross_border = ev_map.get("txn.cross_border") or ev_map.get("flag.cross_border")
    dest_country = ev_map.get("txn.destination_country") or ""
    is_cross_border = cross_border is True or str(cross_border).lower() == "true"
    is_hr_dest = "high_risk" in str(dest_country).lower()
    if is_cross_border and is_hr_dest:
        recommendations.append({
            "action": (
                "Obtain and document the stated purpose of the cross-border transfer. "
                "Verify consistency with customer profile and relationship history."
            ),
            "reference": "FINTRAC Guideline 2 — Cross-border transactions to high-risk jurisdictions",
        })
    elif is_cross_border:
        recommendations.append({
            "action": "Document the business rationale for the cross-border transfer.",
            "reference": "FINTRAC Guideline 2 — Cross-border transaction review",
        })

    # Amount band near LCTR threshold
    amount_band = str(ev_map.get("txn.amount_band") or "").lower()
    if amount_band in ("10k_25k", "10k-25k", "25k_50k", "25k-50k"):
        recommendations.append({
            "action": (
                "Confirm whether transaction is part of a series. "
                "Assess against LCTR threshold ($10,000 cash or 24-hour rule) if applicable."
            ),
            "reference": "PCMLTFA s. 7 / FINTRAC LCTR threshold guidance",
        })

    # Structuring indicators
    structuring = ev_map.get("flag.structuring_suspected")
    if structuring is True or str(structuring).lower() == "true":
        recommendations.append({
            "action": "Review 30-day transaction history for threshold-adjacent patterns.",
            "reference": "FINTRAC Guideline 3 — Structuring indicators",
        })

    # Adverse media
    adverse_media = ev_map.get("flag.adverse_media")
    if adverse_media is True or str(adverse_media).lower() == "true":
        recommendations.append({
            "action": "Obtain and review adverse media sources. Document relevance assessment.",
            "reference": "PCMLTFA Regulations s. 62(2) — Adverse media review",
        })

    # Generic fallback always appended
    recommendations.append({
        "action": (
            "Complete enhanced customer due diligence review per institutional policy "
            "and escalate to Senior Analyst / Compliance Officer within 5 business days."
        ),
        "reference": "Institutional EDD Policy",
    })

    return recommendations


# ── FIX-006: Defensibility check ─────────────────────────────────────────────

def _build_defensibility_check(
    reporting: str,
    reporting_note: str,
    precedent_deviation_alert: Optional[dict],
) -> dict:
    """Build the defensibility check section.

    Always present in the report (even if deferred for EDD cases).
    """
    if reporting == "UNKNOWN":
        return {
            "status": "DEFERRED",
            "message": "Reporting determination pending EDD completion.",
            "action": "Defensibility Alert will be evaluated upon final disposition.",
            "note": (
                "No historical filing pattern comparison performed. Reporting "
                "obligation will be assessed when EDD is complete and a final "
                "disposition is rendered."
            ),
        }

    # Check if there's a reporting deviation alert
    rd = None
    if precedent_deviation_alert:
        rd = precedent_deviation_alert.get("reporting_deviation")

    if rd:
        return {
            "status": "ALERT",
            "message": rd.get("message", "Reporting deviation detected."),
            "action": "Immediate compliance review required.",
            "note": (
                f"Current proposal to {rd.get('case_reporting', 'N/A')} contradicts "
                f"{rd.get('more_severe_pct', 0)}% historical "
                f"{rd.get('dominant_precedent_reporting', 'N/A')} filing rate "
                f"for this typology."
            ),
            # INV-009: Override without documented rationale = examination finding
            "requires_documented_rationale": True,
            "rationale_status": "PENDING",
            "inv_009_note": (
                "Per PCMLTFA s. 73/73.1 and INV-009: Overriding this "
                "Defensibility Alert without documented rationale "
                "constitutes a material examination finding."
            ),
        }

    return {
        "status": "PASS",
        "message": "No reporting deviation detected.",
        "action": "",
        "note": (
            "Current reporting determination is consistent with precedent "
            "filing patterns."
        ),
    }


# ── FIX-009: SLA timeline ────────────────────────────────────────────────────

def _build_sla_timeline(
    timestamp: str,
    governed_disposition: str,
    reporting: str,
) -> dict:
    """Build SLA / timeline tracking section."""
    try:
        case_created = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        case_created = datetime.utcnow()

    # 5 business days for EDD (skip weekends naively)
    edd_deadline = None
    if governed_disposition in ("EDD_REQUIRED", "ESCALATE"):
        bd = 0
        d = case_created
        while bd < 5:
            d += timedelta(days=1)
            if d.weekday() < 5:  # Mon-Fri
                bd += 1
        edd_deadline = d.replace(hour=23, minute=59, second=59).isoformat() + "Z"

    str_filing_window = "N/A (no STR determination)"
    if reporting == "FILE_STR":
        str_deadline = case_created + timedelta(days=30)
        str_filing_window = f"{str_deadline.isoformat()}Z (30 days per PCMLTFA s. 7)"
    elif reporting == "FILE_LCTR":
        lctr_deadline = case_created + timedelta(days=15)
        str_filing_window = f"{lctr_deadline.isoformat()}Z (15 days per PCMLTFA s. 12)"

    return {
        "case_created": case_created.isoformat() + "Z",
        "edd_deadline": edd_deadline or "N/A",
        "final_disposition_due": "Populated when EDD completes",
        "str_filing_window": str_filing_window,
    }


# ── FIX-015: Analyst Actions (decision-outcome-aware) ────────────────────────

def _derive_analyst_actions(
    governed_disposition: str,
    verdict: str,
    str_required: bool,
    suspicion_count: int = 0,
    investigative_count: int = 0,
    integrity_alert: dict | None = None,
) -> list[dict]:
    """Generate decision-outcome-aware action options for analyst views.

    FIX-025: Actions are driven by governed_disposition FIRST, not raw verdict.
    Governance rule: HARD_STOP / BLOCK decisions must NEVER offer "Approve".
    EDD with Tier 1 signals must use "Confirm with EDD Conditions" (not "Approve").
    PENDING_REVIEW (integrity conflict) must NEVER offer "Approve" or "Confirm Clearance".
    Each action has a label and a role restriction.
    """
    v = verdict.upper()
    is_hard_stop = v in ("HARD_STOP",) or "HARD_STOP" in v
    is_block = v.startswith("BLOCK") or v.startswith("DECLINE") or governed_disposition == "STR_REQUIRED"

    # FIX-025: If integrity alert exists with corrections, governed disposition
    # is authoritative — never offer clearance/approve actions.
    has_conflict = (
        integrity_alert is not None
        and integrity_alert.get("type") in (
            "CLASSIFICATION_DISPOSITION_CONFLICT",
            "CONTROL_CONTRADICTION",
            "ESCALATION_WITHOUT_SUSPICION",
        )
    )

    if has_conflict:
        # Conflict case: compliance officer must review before any clearance
        return [
            {"label": "Escalate to Compliance Officer", "role": "tier1_analyst", "primary": True},
            {"label": "Confirm with EDD Conditions", "role": "tier1_analyst", "primary": False},
            {"label": "Request Additional Information", "role": "tier1_analyst", "primary": False},
        ]

    if is_hard_stop:
        return [
            {"label": "Acknowledge", "role": "tier1_analyst", "primary": True},
            {"label": "Request Additional Information", "role": "tier1_analyst", "primary": False},
            {"label": "Expand to Reviewer View", "role": "tier1_analyst", "primary": False},
        ]

    if is_block and not str_required:
        return [
            {"label": "Acknowledge", "role": "tier1_analyst", "primary": True},
            {"label": "Request Additional Information", "role": "tier1_analyst", "primary": False},
            {"label": "Expand to Reviewer View", "role": "tier1_analyst", "primary": False},
        ]

    if governed_disposition in ("STR_REQUIRED",) or str_required:
        return [
            {"label": "Acknowledge STR Filing", "role": "tier1_analyst", "primary": True},
            {"label": "Request Additional Information", "role": "tier1_analyst", "primary": False},
            {"label": "Expand to Reviewer View", "role": "tier1_analyst", "primary": False},
            {"label": "Escalate to Compliance Officer", "role": "tier1_analyst", "primary": False},
        ]

    if governed_disposition == "ESCALATE":
        return [
            {"label": "Approve Escalation", "role": "tier1_analyst", "primary": True},
            {"label": "Request Additional Information", "role": "tier1_analyst", "primary": False},
            {"label": "Return to Queue", "role": "tier1_analyst", "primary": False},
        ]

    if governed_disposition == "EDD_REQUIRED":
        # High-risk EDD: Tier 1 signals present or many investigative signals
        # → must acknowledge EDD conditions, not just "Begin EDD"
        if suspicion_count > 0 or investigative_count >= 3:
            return [
                {"label": "Confirm with EDD Conditions", "role": "tier1_analyst", "primary": True},
                {"label": "Escalate to Compliance Officer", "role": "tier1_analyst", "primary": False},
                {"label": "Request Additional Information", "role": "tier1_analyst", "primary": False},
            ]
        return [
            {"label": "Begin EDD Review", "role": "tier1_analyst", "primary": True},
            {"label": "Request Additional Information", "role": "tier1_analyst", "primary": False},
            {"label": "Escalate", "role": "tier1_analyst", "primary": False},
        ]

    # NO_REPORT / APPROVED / PASS
    return [
        {"label": "Confirm Clearance", "role": "tier1_analyst", "primary": True},
        {"label": "Request Additional Information", "role": "tier1_analyst", "primary": False},
        {"label": "Escalate", "role": "tier1_analyst", "primary": False},
    ]


def _detect_precedent_deviation(
    precedent_analysis: dict,
    governed_disposition: str,
    engine_disposition: str,
) -> Optional[dict]:
    """Detect deviation using v2 dual deviation model.

    Implements Section 9 of PRECEDENT_OUTCOME_MODEL_V2.md.

    Returns a deviation alert dict with one or both of:
    - Disposition Deviation (Consistency Warning) — Section 9.1
    - Reporting Deviation (Defensibility Alert) — Section 9.2

    RULE: Only same-basis precedents participate.
    INV-007: Disposition → Consistency; Reporting → Defensibility.
    INV-008: Cross-basis precedents excluded.
    """
    if not precedent_analysis or not precedent_analysis.get("available"):
        return None

    sample_cases = precedent_analysis.get("sample_cases", []) or []
    if len(sample_cases) < 3:
        return None  # too few to signal deviation

    proposed_canonical = precedent_analysis.get("proposed_canonical", {})
    case_basis = proposed_canonical.get("disposition_basis", "UNKNOWN")
    case_disposition = proposed_canonical.get("disposition", "UNKNOWN")
    case_reporting = proposed_canonical.get("reporting", "UNKNOWN")

    # ── Disposition Deviation (Consistency Check) ─────────────────────
    # Filter to same-basis, terminal-outcome precedents (INV-008)
    comparable_dispositions = []
    for sc in sample_cases:
        prec_basis = sc.get("disposition_basis", "UNKNOWN")
        prec_disp = sc.get("disposition", "UNKNOWN")

        # INV-008: skip cross-basis
        if case_basis != "UNKNOWN" and prec_basis != "UNKNOWN" and case_basis != prec_basis:
            continue
        # Only terminal dispositions matter for consistency (ALLOW/BLOCK)
        if prec_disp in ("ALLOW", "BLOCK"):
            comparable_dispositions.append(prec_disp)

    disposition_alert = None
    if len(comparable_dispositions) >= 3 and case_disposition in ("ALLOW", "BLOCK"):
        from collections import Counter
        disp_counts = Counter(comparable_dispositions)
        majority_disp = disp_counts.most_common(1)[0][0]
        majority_count = disp_counts[majority_disp]
        total = len(comparable_dispositions)
        majority_pct = int(majority_count / total * 100)

        if case_disposition != majority_disp and majority_pct >= 60:
            disposition_alert = {
                "type": "DISPOSITION_DEVIATION",
                "alert_class": "Consistency Warning",
                "severity": "WARNING",
                "message": (
                    f"{majority_pct}% of comparable {case_basis} precedents "
                    f"resulted in {majority_disp} while the current disposition "
                    f"is {case_disposition}."
                ),
                "case_disposition": case_disposition,
                "majority_disposition": majority_disp,
                "majority_pct": majority_pct,
                "comparable_count": total,
                "evaluated_disposition": governed_disposition,
            }
            if engine_disposition != governed_disposition:
                disposition_alert["engine_note"] = (
                    f"Engine disposition ({engine_disposition}) differs from "
                    f"governed disposition ({governed_disposition})."
                )

    # ── Reporting Deviation (Defensibility Check) ─────────────────────
    # Severity ordering: FILE_STR > FILE_TPR > FILE_LCTR > NO_REPORT
    _REPORTING_SEVERITY = {
        "FILE_STR": 4,
        "FILE_TPR": 3,
        "FILE_LCTR": 2,
        "NO_REPORT": 1,
        "UNKNOWN": 0,
    }

    comparable_reporting = []
    for sc in sample_cases:
        prec_basis = sc.get("disposition_basis", "UNKNOWN")
        prec_reporting = sc.get("reporting", "UNKNOWN")
        # INV-008: skip cross-basis
        if case_basis != "UNKNOWN" and prec_basis != "UNKNOWN" and case_basis != prec_basis:
            continue
        if prec_reporting != "UNKNOWN":
            comparable_reporting.append(prec_reporting)

    reporting_alert = None
    if len(comparable_reporting) >= 3 and case_reporting != "UNKNOWN":
        case_severity = _REPORTING_SEVERITY.get(case_reporting, 0)
        # Count how many comparable precedents have MORE SEVERE reporting
        more_severe = [r for r in comparable_reporting if _REPORTING_SEVERITY.get(r, 0) > case_severity]
        if len(more_severe) >= len(comparable_reporting) * 0.6:
            from collections import Counter
            reporting_counts = Counter(more_severe)
            dominant_report = reporting_counts.most_common(1)[0][0]
            pct = int(len(more_severe) / len(comparable_reporting) * 100)

            if dominant_report in ("FILE_STR", "FILE_TPR"):
                reporting_alert = {
                    "type": "REPORTING_DEVIATION",
                    "alert_class": "Defensibility Alert",
                    "severity": "CRITICAL",
                    "message": (
                        f"Current proposal to {case_reporting} contradicts "
                        f"{pct}% historical {dominant_report} filing rate "
                        f"for this typology."
                    ),
                    "case_reporting": case_reporting,
                    "dominant_precedent_reporting": dominant_report,
                    "more_severe_pct": pct,
                    "comparable_count": len(comparable_reporting),
                }

    # ── Build combined deviation result ───────────────────────────────
    if disposition_alert or reporting_alert:
        result = {
            "type": "DUAL_DEVIATION",
            "severity": "CRITICAL" if reporting_alert else "WARNING",
        }
        if disposition_alert:
            result["disposition_deviation"] = disposition_alert
            result["type"] = disposition_alert["type"]
            result["severity"] = disposition_alert["severity"]
            result["message"] = disposition_alert["message"]
            result["supporting"] = int(precedent_analysis.get("supporting_precedents", 0) or 0)
            result["contrary"] = int(precedent_analysis.get("contrary_precedents", 0) or 0)
            result["evaluated_disposition"] = governed_disposition
        if reporting_alert:
            result["reporting_deviation"] = reporting_alert
            if not disposition_alert:
                result["type"] = reporting_alert["type"]
                result["message"] = reporting_alert["message"]
            result["severity"] = "CRITICAL"  # reporting deviation always critical
        return result

    # ── Fallback: v1-style supporting/contrary check ──────────────────
    supporting = int(precedent_analysis.get("supporting_precedents", 0) or 0)
    contrary = int(precedent_analysis.get("contrary_precedents", 0) or 0)
    total = supporting + contrary

    if total < 3:
        return None

    is_escalation = governed_disposition in ("STR_REQUIRED", "ESCALATE", "STR REQUIRED")

    if is_escalation and contrary > supporting:
        deviation_pct = int(contrary / total * 100)
        alert = {
            "type": "OVER_ESCALATION_RISK",
            "severity": "WARNING",
            "message": (
                f"Deviation vs GOVERNED outcome ({governed_disposition}): "
                f"{deviation_pct}% of scored comparable cases "
                f"({contrary} of {total}) did NOT result in escalation/STR. "
                "This pattern divergence warrants consistency review."
            ),
            "supporting": supporting,
            "contrary": contrary,
            "evaluated_disposition": governed_disposition,
        }
        if engine_disposition != governed_disposition:
            alert["engine_note"] = (
                f"Engine disposition ({engine_disposition}) differs from "
                f"governed disposition ({governed_disposition})."
            )
        return alert

    if not is_escalation and contrary > supporting:
        # Contrary > supporting with non-escalation governed disposition:
        # precedent majority disagrees with the governed outcome.
        alert = {
            "type": "UNDER_ESCALATION_RISK",
            "severity": "INFO",
            "message": (
                f"Deviation vs GOVERNED outcome ({governed_disposition}): "
                f"{contrary} of {total} scored comparable cases "
                f"resulted in a different outcome than {governed_disposition}. "
                "Consistency review may be warranted."
            ),
            "supporting": supporting,
            "contrary": contrary,
            "evaluated_disposition": governed_disposition,
        }
        if engine_disposition != governed_disposition:
            alert["engine_note"] = (
                f"Engine disposition ({engine_disposition}) differs from "
                f"governed disposition ({governed_disposition})."
            )
        return alert

    return None


# ── FIX-018: Enhanced precedent analysis ─────────────────────────────────────

_SIMILARITY_FEATURE_LABELS: dict[str, str] = {
    "rules_overlap": "Rule activation",
    "gate_match": "Gate outcomes",
    "typology_overlap": "Typology overlap",
    "amount_bucket": "Amount band",
    "channel_method": "Channel/method",
    "corridor_match": "Corridor risk",
    "pep_match": "PEP status",
    "customer_profile": "Customer profile",
    "geo_risk": "Geographic risk",
}

# v3 field-level labels — maps canonical field names from the banking domain
# registry to human-readable labels for report rendering.
_V3_FIELD_LABELS: dict[str, str] = {
    "customer.type": "Customer type",
    "customer.relationship_length": "Relationship length",
    "customer.pep": "PEP status",
    "customer.high_risk_jurisdiction": "High-risk jurisdiction",
    "customer.high_risk_industry": "High-risk industry",
    "customer.cash_intensive": "Cash-intensive business",
    "txn.type": "Transaction type",
    "txn.amount_band": "Amount band",
    "txn.cross_border": "Cross-border",
    "txn.destination_country_risk": "Destination risk",
    "txn.round_amount": "Round amount",
    "txn.just_below_threshold": "Below threshold",
    "txn.multiple_same_day": "Same-day multiples",
    "txn.pattern_matches_profile": "Profile consistency",
    "txn.source_of_funds_clear": "Source of funds",
    "txn.stated_purpose": "Stated purpose",
    "flag.structuring": "Structuring",
    "flag.rapid_movement": "Rapid movement",
    "flag.layering": "Layering",
    "flag.unusual_for_profile": "Unusual activity",
    "flag.third_party": "Third-party payment",
    "flag.shell_company": "Shell company",
    "screening.sanctions_match": "Sanctions match",
    "screening.pep_match": "PEP screening",
    "screening.adverse_media": "Adverse media",
    "prior.sars_filed": "Prior SARs",
    "prior.account_closures": "Account closures",
}


def _build_enhanced_precedent_analysis(
    precedent_analysis: dict,
    governed_disposition: str,
    deviation_alert: dict | None,
    classification_outcome: str = "",
) -> dict:
    """Build enhanced precedent analysis with institutional learning features.

    FIX-027: Rebuilt for institutional knowledge transfer per audit feedback.
    Precedent analysis must teach, not just list.

    Returns a dict consumed by the renderer with:
      - pattern_summary: natural language institutional knowledge
      - case_thumbnails: readable precedent summaries
      - outcome_distribution: counts
      - feature_comparison_matrix: top 5 precedent feature comparison
      - institutional_posture: auto-generated from pattern data
      - divergence_justification
      - temporal_context
      - override_statement
    """
    if not precedent_analysis or not precedent_analysis.get("available"):
        return {}

    sample_cases = precedent_analysis.get("sample_cases", []) or []
    supporting = int(precedent_analysis.get("supporting_precedents", 0) or 0)
    contrary = int(precedent_analysis.get("contrary_precedents", 0) or 0)
    neutral = int(precedent_analysis.get("neutral_precedents", 0) or 0)
    total_decisive = supporting + contrary
    total_all = supporting + contrary + neutral

    # Get outcome distribution for pattern analysis — prefer matched, fall
    # back to raw overlap pool for broader context when matches are sparse.
    match_distribution = (
        precedent_analysis.get("match_outcome_distribution")
        or precedent_analysis.get("outcome_distribution")
        or {}
    )
    raw_overlap_count = int(precedent_analysis.get("raw_overlap_count", 0) or 0)
    raw_distribution = precedent_analysis.get("raw_outcome_distribution") or {}

    result: dict = {}

    # ── a) Pattern Summary (the headline — institutional knowledge) ───
    # Natural language: what the bank's collective experience says
    pattern_summary = _build_pattern_summary(
        total_all=total_all,
        supporting=supporting,
        contrary=contrary,
        neutral=neutral,
        governed_disposition=governed_disposition,
        classification_outcome=classification_outcome,
        match_distribution=match_distribution,
        sample_cases=sample_cases,
        raw_overlap_count=raw_overlap_count,
        raw_distribution=raw_distribution,
    )
    result["pattern_summary"] = pattern_summary

    # ── b) Outcome Distribution Summary ──────────────────────────────
    result["outcome_distribution"] = {
        "supporting": supporting,
        "contrary": contrary,
        "neutral": neutral,
        "total": total_all,
        "typical_outcome": (
            governed_disposition if supporting >= contrary
            else "CONTRARY (majority diverges from current decision)"
        ),
    }

    # ── b2) Governed Disposition Alignment ─────────────────────────────
    # How many precedents in the scored pool match the governed disposition?
    # Maps governed disposition label to canonical distribution keys.
    _gov_canonical = (
        "EDD" if "EDD" in governed_disposition.upper()
        else "BLOCK" if any(k in governed_disposition.upper() for k in ("BLOCK", "STR"))
        else "ALLOW"
    )
    _gov_match = sum(
        v for k, v in match_distribution.items()
        if str(k).upper() == _gov_canonical
        or (_gov_canonical == "EDD" and ("EDD" in str(k).upper() or "REVIEW" in str(k).upper()))
        or (_gov_canonical == "ALLOW" and str(k).upper() in ("ALLOW", "NO_REPORT", "PASS", "CLEARED"))
        or (_gov_canonical == "BLOCK" and str(k).upper() in ("BLOCK", "STR_REQUIRED", "FILE_STR"))
    )
    _gov_total = sum(match_distribution.values()) if match_distribution else 0
    result["governed_alignment_count"] = _gov_match
    result["governed_alignment_total"] = _gov_total

    # ── c) Case Thumbnails (readable precedent summaries) ─────────────
    # FIX-027: Replace cryptic hashes with readable summaries
    is_v3 = precedent_analysis.get("scoring_version") == "v3"
    case_thumbnails: list[dict] = []
    for match in sample_cases[:5]:
        sim_pct = int(match.get("similarity_pct", 0) or 0)
        outcome_label = match.get("outcome_label") or str(match.get("outcome", "N/A")).upper()
        classification = match.get("classification", "neutral")
        reason_codes = match.get("reason_codes", []) or []

        # Build a readable thumbnail from available data
        thumbnail_parts = []
        # Customer type from reason codes
        for rc in reason_codes:
            rc_upper = str(rc).upper()
            if "PEP" in rc_upper:
                thumbnail_parts.append("PEP customer")
            if "SANCTION" in rc_upper:
                thumbnail_parts.append("sanctions exposure")
            if "STRUCT" in rc_upper:
                thumbnail_parts.append("structuring pattern")
            if "LAYER" in rc_upper:
                thumbnail_parts.append("layering indicators")
            if "SHELL" in rc_upper:
                thumbnail_parts.append("shell entity")
            if "ADVERSE" in rc_upper:
                thumbnail_parts.append("adverse media")
            if "VELOCITY" in rc_upper or "EVASION" in rc_upper:
                thumbnail_parts.append("evasion behavior")

        # Key differentiators — v3 reads field_scores, v2 reads similarity_components
        key_matches = []
        key_diffs = []
        matched_drivers: list[str] = []
        mismatched_drivers: list[str] = []
        if is_v3:
            field_scores = match.get("field_scores", {}) or {}
            m_drivers = set(match.get("matched_drivers", []) or [])
            mm_drivers = set(match.get("mismatched_drivers", []) or [])
            for key, label in _V3_FIELD_LABELS.items():
                score = field_scores.get(key)
                if score is None:
                    continue
                try:
                    score = float(score)
                except (TypeError, ValueError):
                    continue
                tag = ""
                if key in m_drivers:
                    tag = " (driver)"
                    matched_drivers.append(label)
                elif key in mm_drivers:
                    tag = " (driver mismatch)"
                    mismatched_drivers.append(label)
                if score >= 70:
                    key_matches.append(f"{label}{tag}")
                elif 0 < score < 50:
                    key_diffs.append(f"{label}{tag}")
        else:
            components = match.get("similarity_components", {}) or {}
            for key, label in _SIMILARITY_FEATURE_LABELS.items():
                score = components.get(key, 0) or 0
                try:
                    score = float(score)
                except (TypeError, ValueError):
                    score = 0.0
                if score >= 70:
                    key_matches.append(label)
                elif 0 < score < 50:
                    key_diffs.append(label)

        # Build description — always aim for a meaningful sentence
        if thumbnail_parts:
            description = f"{outcome_label}. Key factors: {', '.join(thumbnail_parts[:3])}."
        elif key_matches:
            description = f"{outcome_label}. Similar on: {', '.join(key_matches[:3])}."
        else:
            description = f"{outcome_label}. {sim_pct}% similarity to current case profile."
        if key_diffs:
            description += f" Key difference from current case: {', '.join(key_diffs[:2])}."

        thumb = {
            "precedent_id": match.get("precedent_id", "N/A"),
            "similarity_pct": sim_pct,
            "outcome_label": outcome_label,
            "classification": classification,
            "disposition": match.get("disposition", "UNKNOWN"),
            "description": description,
            "key_matches": key_matches[:3],
            "key_differences": key_diffs[:3],
            "reason_codes": reason_codes,
        }
        if is_v3:
            thumb["matched_drivers"] = matched_drivers
            thumb["mismatched_drivers"] = mismatched_drivers
        case_thumbnails.append(thumb)
    result["case_thumbnails"] = case_thumbnails

    # ── d) Feature Comparison Matrix ─────────────────────────────────
    comparison_matrix: list[dict] = []
    for match in sample_cases[:5]:
        sim_pct = int(match.get("similarity_pct", 0) or 0)
        classification = match.get("classification", "neutral")

        matching_features = []
        differing_features = []
        matched_drv = []
        mismatched_drv = []
        if is_v3:
            field_scores = match.get("field_scores", {}) or {}
            m_drivers = set(match.get("matched_drivers", []) or [])
            mm_drivers = set(match.get("mismatched_drivers", []) or [])
            for key, label in _V3_FIELD_LABELS.items():
                score = field_scores.get(key)
                if score is None:
                    continue
                try:
                    score = float(score)
                except (TypeError, ValueError):
                    continue
                driver_tag = ""
                if key in m_drivers:
                    driver_tag = " \u2605"  # ★ driver marker
                    matched_drv.append(label)
                elif key in mm_drivers:
                    driver_tag = " \u2606"  # ☆ mismatched driver
                    mismatched_drv.append(label)
                if score >= 70:
                    matching_features.append(f"{label}{driver_tag}")
                elif 0 < score < 50:
                    differing_features.append(f"{label} ({int(score)}%){driver_tag}")
        else:
            components = match.get("similarity_components", {}) or {}
            for key, label in _SIMILARITY_FEATURE_LABELS.items():
                score = components.get(key, 0) or 0
                try:
                    score = float(score)
                except (TypeError, ValueError):
                    score = 0.0
                if score >= 70:
                    matching_features.append(label)
                elif score > 0 and score < 50:
                    differing_features.append(f"{label} ({int(score)}%)")

        entry = {
            "precedent_id": match.get("precedent_id", "N/A"),
            "similarity_pct": sim_pct,
            "outcome": match.get("outcome_label") or str(match.get("outcome", "N/A")).upper(),
            "classification": classification,
            "matching_features": matching_features,
            "differing_features": differing_features,
        }
        if is_v3:
            entry["matched_drivers"] = matched_drv
            entry["mismatched_drivers"] = mismatched_drv
        comparison_matrix.append(entry)
    result["feature_comparison_matrix"] = comparison_matrix

    # ── e) Institutional Posture Statement ────────────────────────────
    # FIX-027: Auto-generated from pattern data — what the bank's
    # historical practice says about this case profile.
    result["institutional_posture"] = _build_institutional_posture(
        total_all=total_all,
        supporting=supporting,
        contrary=contrary,
        neutral=neutral,
        governed_disposition=governed_disposition,
        classification_outcome=classification_outcome,
        match_distribution=match_distribution,
        raw_overlap_count=raw_overlap_count,
        raw_distribution=raw_distribution,
    )

    # ── f) Divergence Justification ──────────────────────────────────
    has_deviation = deviation_alert is not None
    contrary_cases = [
        m for m in sample_cases
        if m.get("classification") == "contrary"
    ]

    divergence_justification = None
    if has_deviation and contrary_cases:
        contrary_details = []
        for cc in contrary_cases[:5]:
            diffs = []
            if is_v3:
                field_scores = cc.get("field_scores", {}) or {}
                mm_drivers = set(cc.get("mismatched_drivers", []) or [])
                for key, label in _V3_FIELD_LABELS.items():
                    score = field_scores.get(key)
                    if score is None:
                        continue
                    try:
                        score = float(score)
                    except (TypeError, ValueError):
                        continue
                    if 0 < score < 60:
                        tag = " (driver)" if key in mm_drivers else ""
                        diffs.append(f"{label} ({int(score)}%){tag}")
            else:
                components = cc.get("similarity_components", {}) or {}
                for key, label in _SIMILARITY_FEATURE_LABELS.items():
                    score = components.get(key, 0) or 0
                    try:
                        score = float(score)
                    except (TypeError, ValueError):
                        score = 0.0
                    if 0 < score < 60:
                        diffs.append(f"{label} ({int(score)}%)")
            contrary_details.append({
                "precedent_id": cc.get("precedent_id", "N/A"),
                "outcome": cc.get("outcome_label") or str(cc.get("outcome", "N/A")).upper(),
                "similarity_pct": int(cc.get("similarity_pct", 0) or 0),
                "distinguishing_factors": diffs or ["No clear differentiating factor identified"],
            })

        divergence_justification = {
            "diverges_from_majority": contrary > supporting,
            "contrary_count": len(contrary_cases),
            "total_decisive": total_decisive,
            "contrary_details": contrary_details,
            "statement": (
                f"Decision diverges from precedent majority. "
                f"{len(contrary_cases)} contrary precedent(s) identified "
                f"out of {total_decisive} terminal comparisons. "
                f"Override justified by classifier sovereignty and "
                f"current case-specific Tier 1 indicators."
            ),
        }
    result["divergence_justification"] = divergence_justification

    # ── g) Temporal Context ──────────────────────────────────────────
    temporal_notes = []
    for sc in sample_cases[:10]:
        ts = sc.get("timestamp") or sc.get("decided_at") or sc.get("created_at")
        if ts:
            temporal_notes.append({
                "precedent_id": sc.get("precedent_id", "N/A"),
                "timestamp": ts,
                "classification": sc.get("classification", "neutral"),
            })
    result["temporal_context"] = temporal_notes

    # ── h) Precedent Override Statement ──────────────────────────────
    override_statement = None
    if has_deviation and contrary > supporting:
        override_statement = (
            f"I acknowledge that the current decision ({governed_disposition}) "
            f"diverges from the majority of scored precedents "
            f"({contrary} contrary vs {supporting} supporting). "
            f"This divergence is justified based on the following "
            f"case-specific factors that distinguish it from the "
            f"historical pattern. The distinguishing factors are "
            f"documented in the Feature Comparison Matrix above."
        )
    result["override_statement"] = override_statement

    # ── v3 enhancements (only when scoring_version == "v3") ──────
    if precedent_analysis.get("scoring_version") == "v3":
        # i) Non-transferable explanations
        nt_explanations = []
        for sc in sample_cases:
            if sc.get("non_transferable"):
                nt_explanations.append({
                    "precedent_id": sc.get("precedent_id", "N/A"),
                    "reasons": sc.get("non_transferable_reasons", []),
                    "mismatched_drivers": sc.get("mismatched_drivers", []),
                })
        result["non_transferable_explanations"] = nt_explanations

        # j) Confidence dimensions (4-bar breakdown data)
        result["confidence_dimensions"] = precedent_analysis.get("confidence_dimensions", [])
        result["confidence_level"] = precedent_analysis.get("confidence_level")
        result["confidence_bottleneck"] = precedent_analysis.get("confidence_bottleneck")
        result["confidence_hard_rule"] = precedent_analysis.get("confidence_hard_rule")

        # k) Driver causality — shared vs divergent drivers
        shared_drivers = set()
        divergent_drivers = set()
        for sc in sample_cases:
            for d in sc.get("matched_drivers", []):
                shared_drivers.add(d)
            for d in sc.get("mismatched_drivers", []):
                divergent_drivers.add(d)
        result["driver_causality"] = {
            "shared_drivers": sorted(shared_drivers),
            "divergent_drivers": sorted(divergent_drivers),
        }

    return result


def _build_pattern_summary(
    total_all: int,
    supporting: int,
    contrary: int,
    neutral: int,
    governed_disposition: str,
    classification_outcome: str,
    match_distribution: dict,
    sample_cases: list,
    raw_overlap_count: int = 0,
    raw_distribution: dict | None = None,
) -> str:
    """Build natural language pattern summary for institutional learning.

    FIX-027: A new hire should read this and understand the bank's posture.
    """
    if total_all == 0:
        # No matched precedents — use raw overlap pool for broader context
        if raw_overlap_count > 0 and raw_distribution:
            dominant = max(raw_distribution, key=raw_distribution.get)
            dominant_count = raw_distribution[dominant]
            dom_label = str(dominant).upper().replace("_", " ")
            dom_pct = int(dominant_count / raw_overlap_count * 100)
            return (
                f"No precedents met the similarity threshold for direct comparison. "
                f"Broader institutional pool ({raw_overlap_count} cases) shows "
                f"{dom_pct}% resulted in {dom_label}. "
                f"This case profile appears novel in the bank's experience."
            )
        return "No comparable precedents available for pattern analysis."

    governed_label = governed_disposition.replace("_", " ")
    total_decisive = supporting + contrary

    # Find dominant outcome from distribution
    dominant_outcome = ""
    dominant_count = 0
    if match_distribution:
        dominant_outcome = max(match_distribution, key=match_distribution.get)
        dominant_count = match_distribution.get(dominant_outcome, 0)
    dominant_label = str(dominant_outcome).upper().replace("_", " ") if dominant_outcome else governed_label

    # Build the story
    parts = []

    # Opening: how many comparable cases and what they resulted in
    if total_decisive > 0:
        if supporting == total_decisive:
            parts.append(
                f"Of {total_all} comparable cases, all {total_decisive} terminal "
                f"precedents resulted in {governed_label}."
            )
        elif supporting > contrary:
            support_pct = int(supporting / total_decisive * 100)
            parts.append(
                f"Of {total_all} comparable cases, {support_pct}% "
                f"({supporting} of {total_decisive} terminal) resulted in "
                f"{governed_label}."
            )
        elif contrary > supporting:
            contrary_pct = int(contrary / total_decisive * 100)
            parts.append(
                f"Of {total_all} comparable cases, {contrary_pct}% "
                f"({contrary} of {total_decisive} terminal) resulted in a "
                f"different outcome than the current {governed_label} determination."
            )
        else:
            parts.append(
                f"Of {total_all} comparable cases, terminal precedents are "
                f"evenly split ({supporting} supporting, {contrary} contrary)."
            )

    if neutral > 0:
        parts.append(
            f"{neutral} case(s) resolved through enhanced review "
            f"processes (EDD/review states) rather than immediate determination."
        )

    # Escalation history
    escalation_outcomes = {
        k: v for k, v in (match_distribution or {}).items()
        if str(k).upper() in ("STR_REQUIRED", "ESCALATE", "FILE_STR")
    }
    edd_outcomes = {
        k: v for k, v in (match_distribution or {}).items()
        if "EDD" in str(k).upper() or "REVIEW" in str(k).upper()
    }
    no_report_outcomes = {
        k: v for k, v in (match_distribution or {}).items()
        if str(k).upper() in ("NO_REPORT", "PASS", "CLEARED")
    }

    total_str = sum(escalation_outcomes.values())
    total_edd = sum(edd_outcomes.values())
    total_clear = sum(no_report_outcomes.values())

    if governed_disposition == "EDD_REQUIRED" and total_str == 0 and total_all > 0:
        parts.append(
            "The bank has never escalated a comparable case to STR at the pre-EDD stage."
        )
    elif total_str > 0 and governed_disposition != "STR_REQUIRED":
        str_pct = int(total_str / total_all * 100) if total_all > 0 else 0
        parts.append(
            f"{str_pct}% of comparable cases ({total_str} of {total_all}) "
            f"were escalated to STR."
        )

    # Classifier divergence note
    if classification_outcome and classification_outcome != governed_disposition:
        classifier_label = classification_outcome.replace("_", " ")
        parts.append(
            f"Classifier determination of {classifier_label} diverges from "
            f"the governed disposition of {governed_label}."
        )

    return " ".join(parts) if parts else f"{total_all} comparable precedents found."


def _build_institutional_posture(
    total_all: int,
    supporting: int,
    contrary: int,
    neutral: int,
    governed_disposition: str,
    classification_outcome: str,
    match_distribution: dict,
    raw_overlap_count: int = 0,
    raw_distribution: dict | None = None,
) -> str:
    """Auto-generated institutional posture statement from pattern data.

    FIX-027: What the bank's historical practice says about this case profile.
    """
    if total_all == 0:
        if raw_overlap_count > 0 and raw_distribution:
            governed_label = governed_disposition.replace("_", " ")
            dominant = max(raw_distribution, key=raw_distribution.get)
            dom_label = str(dominant).upper().replace("_", " ")
            return (
                f"No directly comparable precedents available. "
                f"Broader institutional pool ({raw_overlap_count} cases) "
                f"predominantly resolved as {dom_label}. "
                f"Current disposition of {governed_label} is consistent with "
                f"institutional practice for low-risk profiles."
            )
        return "Insufficient precedent data to establish institutional posture."

    governed_label = governed_disposition.replace("_", " ")
    total_decisive = supporting + contrary

    if total_decisive == 0:
        governed_label = governed_disposition.replace("_", " ")
        edd_count = sum(
            v for k, v in match_distribution.items()
            if "EDD" in str(k).upper() or "REVIEW" in str(k).upper()
        )
        if edd_count > 0 and governed_disposition in ("EDD_REQUIRED", "PASS_WITH_EDD"):
            return (
                f"All {neutral} comparable precedent(s) resolved through enhanced "
                f"due diligence — consistent with the current {governed_label} "
                f"disposition. The bank's institutional practice for this case "
                f"profile is uniform EDD referral. No terminal outcomes "
                f"(ALLOW/BLOCK) exist in the comparable pool."
            )
        return (
            f"All {neutral} comparable precedent(s) resolved through review "
            f"processes. No terminal outcomes available to establish "
            f"directional institutional posture."
        )

    support_pct = int(supporting / total_decisive * 100) if total_decisive > 0 else 0

    if support_pct == 100:
        posture = (
            f"Institutional precedent strongly supports {governed_label} "
            f"as the appropriate disposition for this case profile. "
            f"All {total_decisive} comparable terminal precedents resulted "
            f"in the same outcome."
        )
    elif support_pct >= 80:
        posture = (
            f"Institutional precedent supports {governed_label}. "
            f"{support_pct}% of comparable terminal precedents "
            f"({supporting} of {total_decisive}) resulted in the same outcome."
        )
    elif support_pct >= 50:
        posture = (
            f"Institutional precedent is mixed but leans toward {governed_label}. "
            f"{support_pct}% of comparable terminal precedents support the current disposition."
        )
    else:
        contrary_pct = 100 - support_pct
        posture = (
            f"Institutional precedent diverges from {governed_label}. "
            f"{contrary_pct}% of comparable terminal precedents resulted "
            f"in a different outcome. Senior compliance review is recommended."
        )

    # Add classifier conflict note
    if (
        classification_outcome
        and classification_outcome != governed_disposition
        and classification_outcome == "STR_REQUIRED"
    ):
        posture += (
            f" Classifier's {classification_outcome.replace('_', ' ')} determination "
            f"has {'no' if supporting == 0 else 'limited'} historical precedent support."
        )

    return posture


# ── Similarity summary ───────────────────────────────────────────────────────

def _derive_similarity_summary(precedent_analysis: dict) -> str:
    sample_cases = precedent_analysis.get("sample_cases", []) or []
    if not sample_cases:
        return ""
    top = sample_cases[0]
    components = top.get("similarity_components", {}) or {}
    labels = {
        "rules_overlap": "rule activation",
        "gate_match": "gate outcomes",
        "typology_overlap": "typology overlap",
        "amount_bucket": "amount band",
        "channel_method": "channel/method",
        "corridor_match": "corridor risk",
        "pep_match": "PEP status",
        "customer_profile": "customer profile",
        "geo_risk": "geographic risk",
    }
    scored = []
    for key, label in labels.items():
        try:
            value = float(components.get(key, 0) or 0)
        except (TypeError, ValueError):
            value = 0.0
        if value > 0:
            scored.append((value, label))
    if not scored:
        return ""
    scored.sort(key=lambda item: (-item[0], item[1]))
    top_labels = [label for _value, label in scored[:3]]
    return "Primary similarity features: " + ", ".join(top_labels) + "."


# ── Decision drivers ─────────────────────────────────────────────────────────

def _map_driver_label(text: str) -> str:
    if not text:
        return ""
    lowered = text.lower().replace("_", " ")
    if "structur" in lowered or "threshold" in lowered:
        return "Structuring indicators (threshold-adjacent pattern)"
    if "round" in lowered and "trip" in lowered:
        return "Round-trip transaction pattern"
    if "layer" in lowered or "rapid" in lowered:
        return "Layering behavior (rapid movement pattern)"
    if "crypto" in lowered or "virtual asset" in lowered:
        return "Virtual asset exposure"
    if "sanction" in lowered:
        return "Sanctions screening proximity"
    if "pep" in lowered:
        return "PEP exposure"
    if "corridor" in lowered or "fatf" in lowered or "high-risk jurisdiction" in lowered:
        return "High-risk corridor exposure"
    if "trade" in lowered:
        return "Trade-based laundering indicators"
    if "shell" in lowered:
        return "Shell entity indicators"
    if "adverse media" in lowered:
        return "Adverse media exposure"
    if "unusual" in lowered or "deviation" in lowered:
        return "Unusual activity pattern"
    if "intent" in lowered:
        return "Intent indicators identified"
    if "deception" in lowered:
        return "Deceptive conduct indicators"
    if "sustained" in lowered and "pattern" in lowered:
        return "Sustained pattern of suspicious activity"
    return ""


def _derive_decision_drivers(
    rules_fired: list,
    risk_factors: list,
    layer4_typologies: dict,
    layer6_suspicion: dict,
    gate1_passed: bool,
    str_required: bool,
    evidence_used: list | None = None,
    layer1_facts: dict | None = None,
    decision_status: str = "",
) -> list[str]:
    """Generate 3–5 decision driver bullets. Ordered by regulatory weight."""
    ev_map: dict[str, object] = {}
    for ev in (evidence_used or []):
        field = str(ev.get("field", "")).lower()
        ev_map[field] = ev.get("value")

    facts = layer1_facts or {}
    txn = facts.get("transaction", {}) or {}
    customer = facts.get("customer", {}) or {}

    typologies = layer4_typologies.get("typologies", []) or []
    elements = layer6_suspicion.get("elements", {}) or {}

    # ── CASE A: STR required OR hard-stop / mandatory escalation ────────
    # When decision_status is "escalate" (HARD_STOP, BLOCK, etc.), treat
    # as affirmative case even if str_required is technically False.
    if str_required or decision_status == "escalate":
        drivers: list[str] = []
        for typ in typologies:
            name = typ.get("name") if isinstance(typ, dict) else str(typ)
            if name:
                mapped = _map_driver_label(name)
                if mapped:
                    drivers.append(mapped)
        if not drivers:
            drivers.append("Suspicion indicators detected")

        for element in sorted(k for k, active in elements.items() if active):
            mapped = _map_driver_label(element)
            if mapped and mapped not in drivers:
                drivers.append(mapped)

        if ev_map.get("txn.cross_border") or ev_map.get("flag.cross_border") or txn.get("cross_border"):
            drivers.append("Cross-border transaction with elevated corridor risk")
        method = txn.get("method") or ev_map.get("txn.method") or ""
        if method and str(method).lower() in {"wire", "wire_transfer", "swift", "eft"}:
            drivers.append(f"Wire transfer channel ({str(method).upper()})")

        cust_type = customer.get("type") or ev_map.get("customer.type") or ""
        if cust_type and str(cust_type).lower() in {"corporation", "corporate", "business", "entity"}:
            drivers.append("Corporate customer profile")

        # PEP exposure from evidence
        if customer.get("pep_flag") or ev_map.get("customer.pep") or ev_map.get("screening.pep_match"):
            pep_label = "PEP exposure"
            if pep_label not in drivers:
                drivers.append(pep_label)

        # Hard stop reason
        if facts.get("hard_stop_triggered"):
            reason = facts.get("hard_stop_reason", "")
            if reason and "ADVERSE_MEDIA" in str(reason).upper() and "Adverse media exposure" not in drivers:
                drivers.append("Adverse media — confirmed MLTF link (hard stop)")
            elif reason and "SANCTIONS" in str(reason).upper() and "Sanctions screening proximity" not in drivers:
                drivers.append("Sanctions match — immediate block required (hard stop)")

        drivers.append("No mitigating evidence sufficient to negate suspicion threshold")
        return _dedupe_drivers(drivers, cap=5)

    # ── CASE B: No STR ───────────────────────────────────────────────────
    drivers = []
    for typ in typologies:
        name = typ.get("name") if isinstance(typ, dict) else str(typ)
        if name:
            mapped = _map_driver_label(name)
            if mapped:
                drivers.append(mapped)

    for element in sorted(k for k, active in elements.items() if active):
        mapped = _map_driver_label(element)
        if mapped and mapped not in drivers:
            drivers.append(mapped)

    if not drivers:
        drivers.append("No indicators meeting suspicion threshold identified")

    # When Tier 1 = 0, frame remaining items as investigative triggers
    # (Tier 2 context) — not suspicion indicators.
    tier1_empty = not any(
        _map_driver_label(typ.get("name") if isinstance(typ, dict) else str(typ))
        for typ in typologies
    ) and not any(
        _map_driver_label(element)
        for element, active in elements.items() if active
    )
    trigger_prefix = "Investigative trigger: " if tier1_empty else ""

    if ev_map.get("txn.cross_border") or ev_map.get("flag.cross_border") or txn.get("cross_border"):
        drivers.append(f"{trigger_prefix}Cross-border transfer with elevated corridor risk")
    method = txn.get("method") or ev_map.get("txn.method") or ""
    if method and str(method).lower() in {"wire", "wire_transfer", "swift", "eft"}:
        drivers.append(f"{trigger_prefix}Wire transfer channel ({str(method).upper()})")

    cust_type = customer.get("type") or ev_map.get("customer.type") or ""
    if cust_type and str(cust_type).lower() in {"corporation", "corporate", "business", "entity"}:
        drivers.append(f"{trigger_prefix}Corporate customer profile")
    if customer.get("pep_flag") or ev_map.get("flag.pep"):
        drivers.append(f"{trigger_prefix}PEP exposure")

    # NOTE: Gate 1 blocking is a system action, not a case signal.
    # It is communicated in the Gate Evaluation section, not in Key Signals.

    return _dedupe_drivers(drivers, cap=5)


def _dedupe_drivers(drivers: list[str], cap: int = 5) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for label in drivers:
        if label not in seen:
            deduped.append(label)
            seen.add(label)
    return deduped[:cap] if deduped else ["Deterministic rule activation requiring review"]


# ── Risk factors ─────────────────────────────────────────────────────────────

def _build_risk_factors(normalized: dict) -> list[dict]:
    """Build risk-factor list from normalized layers."""
    layer1_facts = normalized["layer1_facts"]
    layer2_obligations = normalized["layer2_obligations"]
    layer3_indicators = normalized["layer3_indicators"]
    layer4_typologies = normalized["layer4_typologies"]
    layer6_suspicion = normalized["layer6_suspicion"]
    rules_fired = normalized["rules_fired"]
    evidence_used = normalized["evidence_used"]
    decision_path = normalized.get("decision_path", "")
    escalation_reasons: list[str] = []
    for rule_text in normalized.get("absolute_rules_validated", []):
        if "triggered" in str(rule_text).lower() or "failed" in str(rule_text).lower():
            escalation_reasons.append(rule_text)
    if decision_path:
        escalation_reasons.append(f"Decision path: {decision_path}")

    risk_factors: list[dict] = []

    if layer1_facts.get("hard_stop_triggered"):
        risk_factors.append({
            "field": "Hard stop",
            "value": layer1_facts.get("hard_stop_reason") or "Triggered",
        })

    for obligation in layer2_obligations.get("obligations", []) or []:
        risk_factors.append({"field": "Regulatory obligation", "value": obligation})

    for indicator in layer3_indicators.get("indicators", []) or []:
        if isinstance(indicator, dict):
            code = indicator.get("code") or indicator.get("name") or "Indicator"
            status = "Corroborated" if indicator.get("corroborated") else "Uncorroborated"
            evidence = indicator.get("evidence")
            value = f"{status}" + (f" — {evidence}" if evidence else "")
            risk_factors.append({"field": code, "value": value})
        else:
            risk_factors.append({"field": "Indicator", "value": str(indicator)})

    for typology in layer4_typologies.get("typologies", []) or []:
        if isinstance(typology, dict):
            name = typology.get("name") or "Typology"
            maturity = typology.get("maturity")
            value = f"{name}" + (f" ({maturity})" if maturity else "")
            risk_factors.append({"field": "Typology", "value": value})

    elements = layer6_suspicion.get("elements", {}) or {}
    for element, active in elements.items():
        if active:
            risk_factors.append({"field": "Suspicion element", "value": element})

    if not risk_factors:
        triggered = [
            rule for rule in rules_fired
            if str(rule.get("result", "")).upper() in {"TRIGGERED", "ACTIVATED", "FAIL", "FAILED"}
        ]
        for rule in triggered:
            code = rule.get("code") or "Rule"
            reason = rule.get("reason") or "Triggered"
            risk_factors.append({"field": code, "value": reason})

    if not risk_factors and escalation_reasons:
        for reason in escalation_reasons[:3]:
            risk_factors.append({"field": "Escalation driver", "value": reason})

    if not risk_factors and decision_path:
        risk_factors.append({"field": "Decision path", "value": decision_path})

    # Fallback: mine evidence_used for risk-relevant booleans
    if not risk_factors:
        _flag_labels = {
            "flag.structuring_suspected": "Structuring indicators",
            "flag.cross_border": "Cross-border transaction",
            "flag.pep": "PEP exposure",
            "flag.sanctions_proximity": "Sanctions screening proximity",
            "flag.adverse_media": "Adverse media exposure",
            "flag.rapid_movement": "Rapid fund movement",
            "flag.shell_entity": "Shell entity indicators",
        }
        _value_labels = {
            "txn.cross_border": ("Cross-border wire transfer", lambda v: v is True or str(v).lower() == "true"),
            "txn.amount_band": ("Amount band", lambda v: bool(v)),
            "customer.type": ("Customer type", lambda v: bool(v)),
            "txn.method": ("Payment method", lambda v: bool(v)),
        }
        for ev in evidence_used:
            field = str(ev.get("field", ""))
            value = ev.get("value")
            if field in _flag_labels and (value is True or str(value).lower() == "true"):
                risk_factors.append({"field": _flag_labels[field], "value": "Present"})
            elif field in _value_labels:
                label, predicate = _value_labels[field]
                if predicate(value):
                    display = str(value).replace("_", "\u2013") if "band" in field else str(value)
                    risk_factors.append({"field": label, "value": display})

    if not risk_factors:
        risk_factors.append({
            "field": "Assessment",
            "value": "No material risk indicators identified in evaluated evidence",
        })

    return risk_factors
