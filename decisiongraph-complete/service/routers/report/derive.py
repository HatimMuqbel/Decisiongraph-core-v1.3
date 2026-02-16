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


# ── Canonical disposition mapping (INV-004, INV-005) ─────────────────────────

def _to_canonical_disposition(governed_disposition: str) -> str:
    """Map governed disposition to canonical form (ALLOW/EDD/BLOCK/UNKNOWN)."""
    gd = governed_disposition.upper().replace(" ", "_")
    if "EDD" in gd or gd in ("REVIEW", "ESCALATE", "PENDING_REVIEW", "PASS_WITH_EDD"):
        return "EDD"
    if gd in ("STR_REQUIRED", "FILE_STR", "BLOCK", "HARD_STOP"):
        return "BLOCK"
    if gd in ("NO_REPORT", "CLEARED", "ALLOW", "PASS"):
        return "ALLOW"
    return "UNKNOWN"


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
    "SUSTAINED_SUSPICIOUS_PATTERN": "Sustained suspicious pattern",
}


def _clean_period(text: str) -> str:
    """Strip trailing dots from text so callers can append exactly one period."""
    return (text or "").rstrip(".")


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

    # ── Mandatory hard stop detection (sanctions, etc.) ───────────────
    is_mandatory_hard_stop = bool(layer1_facts.get("hard_stop_triggered"))
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
            gate1_sections=normalized.get("gate1_sections", []),
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
    risk_factors = _build_risk_factors(normalized, primary_typology=primary_typology)

    # ── 8. Confidence ─────────────────────────────────────────────────────
    # HARD-STOP CONTRACT: When a CRITICAL integrity alert exists,
    # confidence is meaningless. Do NOT compute or overwrite.
    if integrity_alert and integrity_alert.get("severity") == "CRITICAL":
        conf_label = "Integrity Review Required"
        conf_reason = (
            "Confidence score not applicable — active control conflict between "
            "classifier and governance requires compliance officer review."
        )
        conf_score = None  # Suppress numeric score — 0% reads as "zero confidence"
        # Intentionally skip _compute_confidence_score — not even for debug.
    elif is_mandatory_hard_stop:
        conf_label = "Certain"
        conf_reason = "Mandatory determination — no discretion applicable."
        conf_score = 100
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

    # ── 9a. Reconcile signal count in explainer with actual KEY SIGNALS ──
    # The decision_explainer may contain a stale count from validate_output
    # (using the first classifier's investigative_count). Replace it with
    # the actual number of decision drivers so the two always agree.
    # Determine correct tier label based on classifier output
    _has_tier1 = classification.suspicion_count > 0
    _correct_tier_label = "Tier 1 suspicion indicator(s)" if _has_tier1 else "Tier 2 investigative signal(s)"
    _signal_match = re.search(
        r"(\d+)\s+Tier\s+[12]\s+(?:suspicion indicator|investigative signal)\(s\)",
        decision_explainer,
    )
    if _signal_match:
        _stated = int(_signal_match.group(1))
        _actual = len(decision_drivers)
        if _stated != _actual or _signal_match.group(0) != f"{_actual} {_correct_tier_label}":
            decision_explainer = decision_explainer.replace(
                _signal_match.group(0),
                f"{_actual} {_correct_tier_label}",
            )
    # Post-reconciliation assertion: summary count must match rendered count
    _post_match = re.search(
        r"(\d+)\s+Tier\s+[12]\s+(?:suspicion indicator|investigative signal)\(s\)",
        decision_explainer,
    )
    if _post_match:
        assert int(_post_match.group(1)) == len(decision_drivers), (
            f"Signal count mismatch: summary claims {_post_match.group(1)} "
            f"but {len(decision_drivers)} decision drivers will render"
        )

    # ── 9a2. Append LOW confidence warning to decision_explainer ────────
    # The decision summary (Investigation Outcome Summary) must surface
    # the confidence bottleneck so a compliance officer doesn't miss it.
    # Skip for hard stops — mandatory determinations are not discretionary.
    _expl_conf_level = (precedent_analysis.get("confidence_level") or "").upper()
    if _expl_conf_level == "LOW" and "Terminal confidence" not in decision_explainer and not is_mandatory_hard_stop:
        _expl_bottleneck = (
            precedent_analysis.get("confidence_bottleneck", "")
            .replace("_", " ")
        )
        _expl_note = ""
        for _dim in precedent_analysis.get("confidence_dimensions", []):
            if _dim.get("bottleneck") and _dim.get("note"):
                _expl_note = _dim["note"].rstrip(".")
                break
        _expl_detail = (
            f" ({_expl_bottleneck}: {_expl_note})"
            if _expl_note
            else f" ({_expl_bottleneck})" if _expl_bottleneck else ""
        )
        decision_explainer += (
            f" Terminal confidence is LOW{_expl_detail}."
            " Senior review recommended."
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
    disposition_basis = _derive_disposition_basis(rules_fired, governed_disposition)
    enhanced_precedent = _build_enhanced_precedent_analysis(
        precedent_analysis=precedent_analysis,
        governed_disposition=governed_disposition,
        deviation_alert=deviation_alert,
        classification_outcome=classification.outcome,
        disposition_basis=disposition_basis,
        integrity_alert=integrity_alert,
    )

    # ── 11. Escalation summary ────────────────────────────────────────────
    escalation_summary = _build_escalation_summary(decision_status, str_required)

    # ── 11b. Append LOW confidence warning to summary ─────────────────────
    # Skip for hard stops — mandatory determinations are not discretionary.
    _v3_conf_level = (precedent_analysis.get("confidence_level") or "").upper()
    if _v3_conf_level == "LOW" and not is_mandatory_hard_stop:
        _v3_bottleneck = (
            precedent_analysis.get("confidence_bottleneck", "")
            .replace("_", " ")
        )
        _v3_bottleneck_note = ""
        for _dim in precedent_analysis.get("confidence_dimensions", []):
            if _dim.get("bottleneck") and _dim.get("note"):
                _v3_bottleneck_note = _dim["note"].rstrip(".")
                break
        _conf_detail = (
            f" ({_v3_bottleneck}: {_v3_bottleneck_note})"
            if _v3_bottleneck_note
            else f" ({_v3_bottleneck})" if _v3_bottleneck else ""
        )
        escalation_summary += (
            f" Terminal confidence is LOW{_conf_detail}."
            " Senior review recommended before final disposition."
        )

    # ── 12. Regulatory position ───────────────────────────────────────────
    if str_required:
        regulatory_position = "Reporting threshold met under applicable regulatory guidance."
    else:
        regulatory_position = "Suspicion threshold not met based on available indicators."

    # ── 13. FIX-001: Canonical outcome (three-field) ─────────────────────
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
        integrity_alert=integrity_alert,
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
    _neutral = int(_pa.get("neutral_precedents", 0) or 0)

    # ── Governed reclassification for consistency alert counts (INV-005) ──
    _proposed_canonical = _pa.get("proposed_canonical", {})
    _engine_canonical_disp = _proposed_canonical.get("disposition", "UNKNOWN")
    _governed_canonical_disp = _to_canonical_disposition(governed_disposition)
    if _governed_canonical_disp != _engine_canonical_disp:
        _sample_cases = _pa.get("sample_cases", []) or []
        _supporting, _contrary, _neutral = 0, 0, 0
        for _sc in _sample_cases:
            _pd = _sc.get("disposition", "UNKNOWN")
            _pb = _sc.get("disposition_basis", "UNKNOWN")
            _cb = _proposed_canonical.get("disposition_basis", "UNKNOWN")
            _nt = _sc.get("non_transferable", False)
            if _pd == "UNKNOWN" or _governed_canonical_disp == "UNKNOWN":
                _neutral += 1
            elif _governed_canonical_disp == "EDD" or _pd == "EDD":
                if _governed_canonical_disp == "EDD" and _pd == "EDD" and not _nt:
                    _supporting += 1
                else:
                    _neutral += 1
            elif (_cb not in ("UNKNOWN", "") and _pb not in ("UNKNOWN", "")
                  and _cb != _pb):
                _neutral += 1
            elif _pd == _governed_canonical_disp:
                if _nt:
                    _neutral += 1
                else:
                    _supporting += 1
            elif {_pd, _governed_canonical_disp} == {"ALLOW", "BLOCK"}:
                _contrary += 1
            else:
                _neutral += 1

    decisive_count = _supporting + _contrary
    precedent_alignment_pct = (
        int(_supporting / decisive_count * 100) if decisive_count > 0 else 0
    )

    # FIX-019: Precedent minimum pool threshold
    _MIN_PRECEDENT_POOL = 5
    precedent_pool_warning = None
    _total_scored = _supporting + _contrary + _neutral
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

    # ── Full outcome-attribution enrichment ──────────────────────────────
    # When a consistency alert is active, replace the detail text with a
    # structured attribution that names EVERY component's outcome so the
    # compliance officer sees the full picture at a glance.
    if _final_consistency_alert and _pa.get("available"):
        _clf_label = classification.outcome.replace("_", " ")
        _eng_label = engine_disposition.replace("_", " ")
        _gov_label = governed_disposition.replace("_", " ")

        # Dominant precedent outcome from scored distribution
        _outcome_dist = (
            _pa.get("match_outcome_distribution")
            or _pa.get("outcome_distribution")
            or {}
        )
        _dominant_label = ""
        if _outcome_dist:
            _dom_key = max(_outcome_dist, key=_outcome_dist.get)
            if _outcome_dist.get(_dom_key, 0) > 0:
                _dominant_label = str(_dom_key).upper().replace("_", " ")

        # Precedent breakdown line
        if _contrary > 0 and _dominant_label:
            _prec_line = (
                f"{_contrary} contrary precedents ({_dominant_label}) "
                f"vs {_supporting} supporting."
            )
        elif _contrary > 0 or _supporting > 0:
            _prec_line = (
                f"{_contrary} contrary vs {_supporting} supporting precedents."
            )
        elif _total_scored > 0 and _dominant_label:
            _prec_line = (
                f"All {_total_scored} comparable precedents resulted in "
                f"{_dominant_label}."
            )
        else:
            _prec_line = ""

        _final_consistency_detail = (
            f"Classifier recommends {_clf_label}. "
            f"Engine disposition: {_eng_label}. "
            f"Governed disposition: {_gov_label}. "
            + (_prec_line + " " if _prec_line else "")
            + "Precedent majority diverges from current disposition. "
            "Compliance officer review required."
        )

    # ── FIX-028: Gate Override Explanations ────────────────────────────
    gate_override_explanations = _build_gate_override_explanations(
        gate1_passed=gate1_passed,
        gate1_decision=normalized.get("gate1_decision", ""),
        gate1_sections=normalized.get("gate1_sections", []),
        gate2_decision=normalized.get("gate2_decision", ""),
        gate2_status=normalized.get("gate2_status", ""),
        gate2_sections=normalized.get("gate2_sections", []),
        governed_disposition=governed_disposition,
        str_required=str_required,
        integrity_alert=integrity_alert,
        rules_fired=rules_fired,
        classification_outcome=classification.outcome,
        is_mandatory_hard_stop=is_mandatory_hard_stop,
    )

    # ── FIX-029: Disposition Reconciliation ────────────────────────────
    disposition_reconciliation = _build_disposition_reconciliation(
        engine_disposition=engine_disposition,
        governed_disposition=governed_disposition,
        classification_outcome=classification.outcome,
        integrity_alert=integrity_alert,
        corrections=corrections,
        gate1_passed=gate1_passed,
        str_required=str_required,
        is_mandatory_hard_stop=is_mandatory_hard_stop,
    )

    # ── FIX-030: Precedent Divergence Narrative ────────────────────────
    precedent_divergence = _build_precedent_divergence_narrative(
        precedent_analysis=precedent_analysis,
        governed_disposition=governed_disposition,
        classification_outcome=classification.outcome,
        integrity_alert=integrity_alert,
        enhanced_precedent=enhanced_precedent,
    )

    # ── FIX-031: Unmapped Indicator Independence Check ─────────────────
    unmapped_indicator_checks = _build_unmapped_indicator_checks(
        tier1_signals=classification.tier1_signals,
        tier2_signals=classification.tier2_signals,
        governed_disposition=governed_disposition,
        rules_fired=rules_fired,
        gate1_passed=gate1_passed,
        str_required=str_required,
    )

    # ── FIX-032: Policy Regime Exception ───────────────────────────────
    policy_regime_exception = _build_policy_regime_exception(
        precedent_analysis=precedent_analysis,
        governed_disposition=governed_disposition,
        integrity_alert=integrity_alert,
        classification_outcome=classification.outcome,
    )

    # ── FIX-033: Risk Heatmap Context ──────────────────────────────────
    risk_heatmap_context = _build_risk_heatmap_context(
        risk_factors=risk_factors,
        governed_disposition=governed_disposition,
        integrity_alert=integrity_alert,
    )

    # ── FIX-034: Required Actions (dynamic) ────────────────────────────
    required_actions = _build_required_actions(
        governed_disposition=governed_disposition,
        str_required=str_required,
        sla_timeline=sla_timeline,
        edd_recommendations=edd_recommendations,
        risk_factors=risk_factors,
        evidence_used=evidence_used,
        classification=classification,
    )

    # ── FIX-035: Related Activity ──────────────────────────────────────
    related_activity = _build_related_activity(evidence_used=evidence_used)

    # ── GAP-E: Senior Summary Box ──────────────────────────────────────
    senior_summary = _build_senior_summary(
        governed_disposition=governed_disposition,
        str_required=str_required,
        classification=classification,
        decision_drivers=decision_drivers,
        risk_factors=risk_factors,
        edd_recommendations=edd_recommendations,
        sla_timeline=sla_timeline,
        integrity_alert=integrity_alert,
        defensibility_check=defensibility_check,
    )

    # ── Case Evidence Summary (synthesized narrative) ──────────────────
    case_evidence_summary = _build_case_evidence_summary(
        layer1_facts=layer1_facts,
        evidence_used=evidence_used,
        classification=classification,
    )

    # ── GAP-B: STR Decision Authority Frame ────────────────────────────
    str_decision_frame = _build_str_decision_frame(
        governed_disposition=governed_disposition,
        str_required=str_required,
        classification=classification,
        sla_timeline=sla_timeline,
        edd_recommendations=edd_recommendations,
        integrity_alert=integrity_alert,
    )

    # ── Decision Conflict Alert ─────────────────────────────────────
    decision_conflict_alert = _build_decision_conflict_alert(
        classification_outcome=classification.outcome,
        engine_disposition=engine_disposition,
        governed_disposition=governed_disposition,
        gate1_passed=gate1_passed,
        gate1_sections=normalized.get("gate1_sections", []),
        gate2_sections=normalized.get("gate2_sections", []),
        is_mandatory_hard_stop=is_mandatory_hard_stop,
    )

    # ── Decision Path Narrative Trace ────────────────────────────────
    decision_path_narrative = _build_decision_path_narrative(
        classification_outcome=classification.outcome,
        tier1_signals=classification.tier1_signals,
        tier2_signals=classification.tier2_signals,
        suspicion_count=classification.suspicion_count,
        investigative_count=classification.investigative_count,
        gate1_passed=gate1_passed,
        gate1_decision=normalized.get("gate1_decision", "N/A"),
        gate1_sections=normalized.get("gate1_sections", []),
        gate2_decision=normalized.get("gate2_decision", "N/A"),
        gate2_status=normalized.get("gate2_status", "N/A"),
        gate2_sections=normalized.get("gate2_sections", []),
        primary_typology=primary_typology,
        typology_stage=_derive_typology_stage(layer4_typologies, primary_typology),
        engine_disposition=engine_disposition,
        governed_disposition=governed_disposition,
        str_required=str_required,
        layer1_facts=layer1_facts,
        layer6_suspicion=layer6_suspicion,
        decision_conflict_alert=decision_conflict_alert,
        integrity_alert=integrity_alert,
        is_mandatory_hard_stop=is_mandatory_hard_stop,
    )

    # For mandatory hard stops, override confidence to CERTAIN (deterministic)
    if is_mandatory_hard_stop:
        enhanced_precedent["confidence_level"] = "CERTAIN"
        enhanced_precedent["confidence_bottleneck"] = None
        enhanced_precedent["confidence_hard_rule"] = None
        enhanced_precedent["confidence_dimensions"] = []

    return {
        # Mandatory hard stop (sanctions, etc.)
        "is_mandatory_hard_stop": is_mandatory_hard_stop,
        "hard_stop_reason": layer1_facts.get("hard_stop_reason", "") if is_mandatory_hard_stop else "",

        # Classification
        "classification": classification.to_dict(),
        "classification_outcome": classification.outcome,
        "classification_reason": (
            # Hard stops (sanctions, false docs, etc.) are statutory — no "preliminary" hedging.
            # The softened RGS language is correct ONLY for classifier/gate conflicts where
            # a compliance officer must make the final determination.
            f"{layer1_facts.get('hard_stop_reason', 'Mandatory determination')} "
            "establishes reporting obligation under PCMLTFA. STR filing mandatory."
            if is_mandatory_hard_stop and classification.outcome == "STR_REQUIRED"
            else classification.outcome_reason
        ),
        "tier1_signals": classification.tier1_signals,
        "tier2_signals": classification.tier2_signals,
        "suspicion_count": classification.suspicion_count,
        "investigative_count": classification.investigative_count,
        "precedent_consistency_alert": _final_consistency_alert,
        "precedent_consistency_detail": _final_consistency_detail,
        "classifier_version": CLASSIFIER_VERSION,

        # Typology
        "primary_typology": primary_typology,
        "typology_stage": _derive_typology_stage(layer4_typologies, primary_typology),

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

        # FIX-028 through FIX-035: Narrative coherence
        "gate_override_explanations": gate_override_explanations,
        "disposition_reconciliation": disposition_reconciliation,
        "precedent_divergence": precedent_divergence,
        "unmapped_indicator_checks": unmapped_indicator_checks,
        "policy_regime_exception": policy_regime_exception,
        "risk_heatmap_context": risk_heatmap_context,
        "required_actions": required_actions,
        "related_activity": related_activity,

        # Decision Conflict Alert
        "decision_conflict_alert": decision_conflict_alert,

        # Decision Path Narrative Trace
        "decision_path_narrative": decision_path_narrative,

        # GAP-E: Senior Summary
        "senior_summary": senior_summary,

        # GAP-B: STR Decision Authority
        "str_decision_frame": str_decision_frame,

        # Case Evidence Summary (synthesized narrative)
        "case_evidence_summary": case_evidence_summary,
    }


# ── GAP-E: Senior Summary ────────────────────────────────────────────────────

def _build_senior_summary(
    governed_disposition: str,
    str_required: bool,
    classification,
    decision_drivers: list[str],
    risk_factors: list[dict],
    edd_recommendations: list[dict],
    sla_timeline: dict,
    integrity_alert: dict | None,
    defensibility_check: dict,
) -> dict:
    """Build a 6-line officer summary for the top of every report."""
    # Alert trigger — first decision driver
    alert_trigger = decision_drivers[0] if decision_drivers else "No specific trigger identified"

    # Suspicious elements — Tier 1 codes
    tier1_codes = [
        s.get("code", "") for s in (classification.tier1_signals or [])
        if s.get("present", True)
    ]
    if classification.suspicion_count > 0 and tier1_codes:
        suspicious_elements = (
            f"{classification.suspicion_count} Tier 1 indicator(s): "
            + ", ".join(tier1_codes)
        )
    elif classification.investigative_count > 0:
        suspicious_elements = (
            f"{classification.investigative_count} Tier 2 investigative signal(s)"
        )
    else:
        suspicious_elements = "No suspicion indicators detected"

    # Not established — what's missing (from EDD recommendations)
    if edd_recommendations:
        not_established = "; ".join(
            r.get("action", "") for r in edd_recommendations[:2]
        )
    else:
        not_established = "No additional evidence gaps identified"

    # Current decision — governed disposition label
    current_decision = governed_disposition.replace("_", " ")

    # STR pending
    if str_required:
        str_pending = "Yes — STR filing required"
    elif governed_disposition in ("EDD_REQUIRED", "ESCALATE"):
        str_pending = "Pending EDD completion"
    else:
        str_pending = "No — threshold not met"

    # Next evidence deadline
    edd_deadline = sla_timeline.get("edd_deadline", "N/A")
    str_window = sla_timeline.get("str_filing_window", "N/A")
    if str_required and str_window != "N/A":
        next_evidence_deadline = f"STR filing: {str_window}"
    elif edd_deadline != "N/A":
        next_evidence_deadline = f"EDD due: {edd_deadline}"
    else:
        next_evidence_deadline = "No pending deadline"

    return {
        "alert_trigger": alert_trigger,
        "suspicious_elements": suspicious_elements,
        "not_established": not_established,
        "current_decision": current_decision,
        "str_pending": str_pending,
        "next_evidence_deadline": next_evidence_deadline,
    }


# ── Case Evidence Summary (synthesized narrative) ────────────────────────────

def _build_case_evidence_summary(
    layer1_facts: dict,
    evidence_used: list[dict],
    classification,
) -> str:
    """Synthesize flat evidence fields into a reviewer-readable narrative.

    Four paragraphs: customer profile, transaction details, behavioral
    indicators, screening results. Built from the same normalized fields
    the decision engine evaluated — no raw PII.
    """
    ev_map = {str(ev.get("field", "")): ev.get("value") for ev in (evidence_used or [])}
    txn = (layer1_facts or {}).get("transaction", {}) or {}
    customer = (layer1_facts or {}).get("customer", {}) or {}
    screening = (layer1_facts or {}).get("screening", {}) or {}

    def _ev(key, default=None):
        """Read a field from evidence_used first, then layer1 sub-dicts."""
        val = ev_map.get(key)
        if val is not None:
            return val
        # Try dotted path in layer1_facts (e.g. "customer.type" → layer1["customer"]["type"])
        parts = key.split(".", 1)
        if len(parts) == 2:
            section = (layer1_facts or {}).get(parts[0], {}) or {}
            val = section.get(parts[1])
            if val is not None:
                return val
        return default

    def _is_true(val) -> bool:
        return val is True or str(val).lower() in ("true", "yes", "1")

    def _is_false(val) -> bool:
        return val is False or str(val).lower() in ("false", "no", "0")

    # ── Customer profile ──────────────────────────────────────────────
    cust_type = _ev("customer.type") or customer.get("type")
    tenure = customer.get("tenure_years")
    pep = _ev("customer.pep_flag", customer.get("pep_flag"))
    residence = customer.get("residence", "")
    risk_rating = customer.get("risk_rating", "")
    parts_cust = []
    if cust_type:
        parts_cust.append(f"{str(cust_type).capitalize()} customer")
    else:
        parts_cust.append("Customer")
    if tenure is not None:
        parts_cust.append(f"with {tenure}-year relationship")
    if _is_true(pep):
        parts_cust.append("(PEP)")
    elif _is_false(pep):
        parts_cust.append("(non-PEP)")
    if residence:
        parts_cust.append(f"resident in {residence}")
    if risk_rating:
        parts_cust.append(f"({risk_rating} risk rating)")
    source_verified = _ev("customer.source_verified")
    ownership_clear = _ev("customer.ownership_clear")
    if _is_false(source_verified):
        parts_cust.append("— source of funds not verified")
    if _is_false(ownership_clear):
        parts_cust.append("— ownership structure unclear")
    # Prior history
    prior_sars = _ev("prior.sars_filed")
    prior_closures = _ev("prior.account_closures")
    if prior_sars is not None and not _is_true(prior_sars) and prior_sars in (0, "0"):
        parts_cust.append("— no prior SARs filed")
    if _is_false(prior_closures):
        parts_cust.append("— no account closures")
    customer_para = " ".join(parts_cust) + "."

    # ── Transaction details ───────────────────────────────────────────
    amount_band = _ev("txn.amount_band") or txn.get("amount_band", "")
    method = txn.get("method") or _ev("txn.method", "")
    cross_border = _ev("txn.cross_border", txn.get("cross_border"))
    destination = txn.get("destination") or _ev("txn.destination_country", "")
    dest_risk = _ev("txn.destination_country_risk", "")
    purpose = txn.get("purpose") or _ev("txn.purpose", "")
    count = _ev("txn.count", "")
    round_amount = _ev("txn.round_amount")
    same_day = _ev("txn.same_day_multiple")
    parts_txn = []
    if method:
        parts_txn.append(f"{str(method).replace('_', ' ').capitalize()}")
    if amount_band:
        band_display = str(amount_band).replace("_", "–").replace("over", ">")
        parts_txn.append(f"${band_display} band")
    if _is_true(cross_border):
        cb_note = "cross-border"
        if destination:
            cb_note += f" to {destination}"
            if dest_risk:
                cb_note += f" ({dest_risk} risk)"
        parts_txn.append(cb_note)
    elif _is_false(cross_border):
        parts_txn.append("domestic")
    if _is_true(round_amount):
        parts_txn.append("round amount")
    if _is_true(same_day):
        parts_txn.append("multiple same-day transactions")
    if purpose:
        parts_txn.append(f"stated purpose: {purpose}")
    if count:
        parts_txn.append(f"({count} transactions)")
    txn_para = (", ".join(parts_txn) + ".") if parts_txn else ""

    # ── Behavioral indicators ─────────────────────────────────────────
    # Labels are NEUTRAL — describe the indicator, not the finding.
    # "layering" not "layering detected" — so cleared list reads correctly.
    _BEHAVIORAL_FLAGS = {
        "flag.structuring_suspected": "structuring",
        "flag.structuring": "structuring",
        "flag.layering": "layering",
        "flag.rapid_movement": "rapid fund movement",
        "flag.funnel_account": "funnel account",
        "flag.shell_entity": "shell entity",
        "flag.shell_company": "shell company",
        "flag.evasion": "evasion behavior",
        "flag.unusual_for_profile": "unusual for profile",
        "flag.third_party_unexplained": "third-party involvement",
        "flag.third_party": "third-party involvement",
        "flag.false_source": "false source of funds",
        "flag.velocity_spike": "velocity spike",
        "flag.adverse_media": "adverse media",
        "flag.sanctions_proximity": "sanctions proximity",
    }
    triggered = []
    cleared = []
    seen_labels: set[str] = set()
    for flag_key, flag_label in _BEHAVIORAL_FLAGS.items():
        val = ev_map.get(flag_key)
        if val is None:
            continue
        if flag_label in seen_labels:
            continue
        seen_labels.add(flag_label)
        if _is_true(val):
            triggered.append(flag_label)
        elif _is_false(val):
            cleared.append(flag_label)

    # Layer 6 suspicion elements
    elements = (layer1_facts or {}).get("_raw", {}).get("layer6_suspicion", {}).get("elements", {}) or {}
    _ELEMENT_LABELS = {
        "has_sustained_pattern": "sustained pattern",
        "has_intent": "intent indicators",
        "has_deception": "deception indicators",
    }
    for el_key, el_label in _ELEMENT_LABELS.items():
        if elements.get(el_key) and el_label not in triggered:
            triggered.append(el_label)

    parts_behav = []
    if triggered:
        parts_behav.append(f"Behavioral indicators present: {', '.join(triggered)}.")
    if cleared:
        parts_behav.append(f"No {', '.join(cleared)} flags.")
    if not triggered and not cleared:
        parts_behav.append("No behavioral indicators evaluated.")
    behavioral_para = " ".join(parts_behav)

    # ── Screening results ─────────────────────────────────────────────
    # Read from BOTH layer1_facts.screening AND evidence_used fields
    sanctions = _ev("screening.sanctions_match", screening.get("sanctions_match"))
    adverse_media = _ev("screening.adverse_media", screening.get("adverse_media"))
    pep_match = _ev("screening.pep_match", screening.get("pep_match"))
    mltf_linked = _ev("screening.mltf_linked", screening.get("mltf_linked"))
    # Also check facts.sanctions_result (some feeds use this)
    sanctions_result = _ev("facts.sanctions_result")
    if sanctions is None and sanctions_result is not None:
        sanctions = str(sanctions_result).upper() != "NO_MATCH"
    parts_screen = []
    if _is_true(sanctions):
        parts_screen.append("sanctions match detected")
    elif _is_false(sanctions) or str(sanctions_result or "").upper() == "NO_MATCH":
        parts_screen.append("no sanctions match")
    if _is_true(adverse_media):
        parts_screen.append("adverse media flagged")
    elif _is_false(adverse_media):
        parts_screen.append("no adverse media")
    if _is_true(pep_match):
        parts_screen.append("PEP match identified")
    elif _is_false(pep_match):
        parts_screen.append("no PEP match")
    if _is_true(mltf_linked):
        parts_screen.append("ML/TF linkage identified")
    elif _is_false(mltf_linked):
        parts_screen.append("no ML/TF linkage")
    if parts_screen:
        screening_para = "Screening conducted: " + "; ".join(parts_screen) + "."
    else:
        screening_para = "No screening data in evaluation record."

    # ── Assemble ──────────────────────────────────────────────────────
    paragraphs = [p for p in [customer_para, txn_para, behavioral_para, screening_para] if p]
    return "\n\n".join(paragraphs)


# ── GAP-B: STR Decision Authority Frame ─────────────────────────────────────

def _build_str_decision_frame(
    governed_disposition: str,
    str_required: bool,
    classification,
    sla_timeline: dict,
    edd_recommendations: list[dict],
    integrity_alert: dict | None,
) -> dict:
    """Build decision authority model: who decides, what, by when, minimum evidence."""
    has_tier1 = classification.suspicion_count > 0
    alert_type = integrity_alert.get("type", "") if integrity_alert else ""

    # CCO-level: systemic control failures only (override, contradiction)
    # CLASSIFICATION_DISPOSITION_CONFLICT is a gate/classifier disagreement —
    # that's an MLRO filing determination, not a CCO control issue.
    _CCO_ALERT_TYPES = {"CLASSIFIER_OVERRIDE", "CONTROL_CONTRADICTION"}
    is_cco = alert_type in _CCO_ALERT_TYPES

    # Decision owner
    if is_cco:
        decision_owner = {
            "role": "Chief Compliance Officer (CCO)",
            "basis": f"Control integrity issue ({alert_type.replace('_', ' ').title()}) requires CCO-level review",
        }
    elif str_required or (has_tier1 and alert_type == "CLASSIFICATION_DISPOSITION_CONFLICT"):
        decision_owner = {
            "role": "MLRO (Money Laundering Reporting Officer)",
            "basis": (
                "Classifier/gate conflict — MLRO must determine STR filing obligation"
                if alert_type == "CLASSIFICATION_DISPOSITION_CONFLICT"
                else "STR filing determination under PCMLTFA s. 7"
            ),
        }
    elif governed_disposition in ("EDD_REQUIRED", "ESCALATE") and has_tier1:
        decision_owner = {
            "role": "Senior Analyst",
            "basis": "EDD case with Tier 1 suspicion indicators present",
        }
    else:
        decision_owner = {
            "role": "Tier 1 Analyst",
            "basis": "Standard review — no elevated signals",
        }

    # Decision options
    gd = governed_disposition.upper()
    if gd == "STR_REQUIRED":
        decision_options = [
            {"option": "File STR", "conditions": "Reasonable grounds to suspect ML/TF established"},
            {"option": "Request additional EDD", "conditions": "Evidence gaps identified before filing"},
            {"option": "Escalate to CCO", "conditions": "Complex case or novel typology requiring senior review"},
        ]
    elif gd in ("EDD_REQUIRED", "ESCALATE") and has_tier1:
        decision_options = [
            {"option": "File STR after EDD completion", "conditions": "EDD confirms suspicion indicators"},
            {"option": "Continue monitoring", "conditions": "Indicators inconclusive, additional observation needed"},
            {"option": "Clear with documentation", "conditions": "EDD resolves all suspicion indicators"},
        ]
    elif gd in ("EDD_REQUIRED", "ESCALATE"):
        decision_options = [
            {"option": "Complete EDD review", "conditions": "Address all identified evidence gaps"},
            {"option": "Escalate to senior analyst", "conditions": "Complexity exceeds Tier 1 authority"},
        ]
    else:
        decision_options = [
            {"option": "Confirm clearance", "conditions": "No suspicion indicators present"},
            {"option": "Reopen for monitoring", "conditions": "New information warrants further review"},
        ]

    # Deadline
    if str_required:
        decision_deadline = sla_timeline.get("str_filing_window", "30 days from suspicion formation")
    else:
        decision_deadline = sla_timeline.get("edd_deadline", "N/A")

    # Minimum evidence (first 3 EDD recommendations)
    minimum_evidence = [
        rec.get("action", "") for rec in (edd_recommendations or [])[:3]
    ]
    if not minimum_evidence:
        if str_required:
            minimum_evidence = [
                "Documented basis for reasonable grounds to suspect",
                "Transaction analysis and customer due diligence review",
                "Screening results (sanctions, PEP, adverse media)",
            ]
        else:
            minimum_evidence = ["Standard review documentation"]

    # Authority basis
    if str_required:
        authority_basis = "PCMLTFA s. 7; FINTRAC Guidance — STR filing"
    elif has_tier1:
        authority_basis = "Institutional compliance policy — Tier 1 signal protocol"
    else:
        authority_basis = "Institutional compliance policy — standard review authority"

    return {
        "decision_owner": decision_owner,
        "decision_options": decision_options,
        "decision_deadline": decision_deadline,
        "minimum_evidence": minimum_evidence,
        "authority_basis": authority_basis,
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
    gate1_sections: list | None = None,
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
        gate_basis = ""
        if gate1_sections:
            failed = [s for s in gate1_sections if not s.get("passed")]
            if failed:
                gate_name = failed[0].get("name", "Gate 1")
                gate_reason = failed[0].get("reason", "")
                gate_basis = (
                    f" Escalation blocked by Gate 1 ({gate_name})"
                    + (f" — {_clean_period(gate_reason)}." if gate_reason else ".")
                )
        return (
            f"Classifier identified {tier1_count} Tier 1 suspicion indicators "
            f"warranting STR review.{gate_basis} Enhanced Due Diligence with "
            f"compliance officer review is required before final regulatory "
            f"determination. This case cannot be cleared without review."
        )

    if alert_type == "CONTROL_CONTRADICTION":
        if decision_status == "review":
            return (
                "Governance correction applied: STR determination removed due to "
                "insufficient Tier 1 evidence. Enhanced Due Diligence required."
            )
        return (
            "Governance correction applied: STR determination removed due to "
            "insufficient Tier 1 evidence. No reporting obligation at this time."
        )

    if alert_type == "ESCALATION_WITHOUT_SUSPICION":
        if decision_status == "review":
            return (
                "Escalation corrected: insufficient Tier 1 suspicion indicators. "
                "Enhanced Due Diligence required before final determination."
            )
        return (
            "Escalation corrected: insufficient Tier 1 suspicion indicators. "
            "No reporting obligation at this time."
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
            # Check if layer4 has FORMING typology — indicators exist but
            # haven't reached suspicion threshold. Distinguish from "nothing found".
            _positional = {"primary", "secondary", "tertiary", "main", "default"}
            for _typ in (layer4_typologies.get("typologies", []) or []):
                _mat = (_typ.get("maturity") or "").upper() if isinstance(_typ, dict) else ""
                if _is_pre_established(_mat):
                    _raw_mat = _mat.lower()
                    _name = (_typ.get("name") or "") if isinstance(_typ, dict) else ""
                    _code = _name.lower().replace(" ", "_").replace("-", "_")
                    _resolved = _TYPOLOGY_CODE_MAP.get(_code, "")
                    if _resolved and _name.lower() not in _positional:
                        return f"{_resolved} (maturity: {_raw_mat})"
                    return f"Unclassified behavioral indicators (maturity: {_raw_mat})"
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


_PRE_ESTABLISHED = {"FORMING", "VALIDATING", "EMERGING"}


def _canonical_maturity(raw: str) -> str:
    """Normalise maturity labels, preserving the original name.

    CONFIRMED/VALIDATED → ESTABLISHED.  All others pass through as-is
    so that EMERGING stays EMERGING (matches evidence table).
    """
    upper = (raw or "").upper().strip()
    if upper in ("CONFIRMED", "VALIDATED"):
        return "ESTABLISHED"
    return upper  # FORMING, EMERGING, VALIDATING, ESTABLISHED, or passthrough


def _is_pre_established(stage: str) -> bool:
    """True when maturity is below ESTABLISHED (FORMING, EMERGING, VALIDATING)."""
    return (stage or "").upper().strip() in _PRE_ESTABLISHED


def _derive_typology_stage(
    layer4_typologies: dict,
    primary_typology: str,
) -> str:
    """Derive typology stage: NONE, raw maturity label, or ESTABLISHED.

    Returns the original maturity label (EMERGING, FORMING, VALIDATING)
    so the narrative matches the evidence table.
    """
    _pt_lower = primary_typology.lower()
    if "indicators present" in _pt_lower or "unclassified behavioral" in _pt_lower:
        # Extract raw maturity from primary_typology if available
        _mat_match = _pt_lower.split("(maturity: ")
        if len(_mat_match) > 1:
            return _mat_match[1].rstrip(")").upper()
        return "FORMING"
    if "(maturity:" in _pt_lower:
        _mat_match = _pt_lower.split("(maturity: ")
        if len(_mat_match) > 1:
            return _mat_match[1].rstrip(")").upper()
        return "FORMING"
    if primary_typology == "No suspicious typology identified":
        return "NONE"
    # Has a named typology → use raw maturity from layer4
    raw_highest = (layer4_typologies.get("highest_maturity") or "").upper().strip()
    highest = _canonical_maturity(raw_highest)
    if highest == "ESTABLISHED":
        return "ESTABLISHED"
    if _is_pre_established(raw_highest):
        return raw_highest  # Preserve original label (EMERGING, FORMING, VALIDATING)
    if primary_typology and primary_typology != "No suspicious typology identified":
        return "ESTABLISHED"
    return "NONE"


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
                "These outcomes are inconsistent under institutional policy. "
                "Suspicion threshold not met — STR filing not supported."
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
        original_label = _disposition_label(decision_status, str_required)
        # Corrections force to EDD — governed label reflects post-correction state
        governed_label = "EDD_REQUIRED"
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
            "pre_correction_disposition": original_label,
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
                f"consistent with preliminary Reasonable Grounds to Suspect (RGS) "
                f"assessment under PCMLTFA/FINTRAC guidance. Under the classifier "
                f"sovereignty framework, any single Tier 1 indicator supports a "
                f"preliminary STR recommendation regardless of gate evidence scoring. "
                f"Final RGS determination requires compliance officer review."
            ),
            "regulatory_basis": "PCMLTFA s. 7 — Preliminary RGS assessment (compliance officer review required)",
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
                f"Under PCMLTFA/FINTRAC guidance, STR filing requires indicators "
                f"consistent with Reasonable Grounds to Suspect — risk indicators "
                f"alone are insufficient. Disposition corrected to preserve STR "
                f"threshold integrity."
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
            "gate_deficiencies": [{"section": "STR Determination", "reason": "0 Tier 1 indicators — STR filing not supported under institutional policy"}],
            "classifier_decision": classification.outcome if hasattr(classification, "outcome") else "EDD_REQUIRED",
            "justifying_signals": [],
            "justification": (
                "Regulatory status was STR REQUIRED but Suspicion Classifier "
                "found 0 Tier 1 indicators. These outcomes are inconsistent "
                "under PCMLTFA/FINTRAC guidance. Suspicion threshold not met — corrected to "
                "prevent unsupported STR filing."
            ),
            "regulatory_basis": "PCMLTFA s. 7 — STR requires Tier 1 suspicion indicators (preliminary RGS assessment)",
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
    integrity_alert: Optional[dict] = None,
) -> dict:
    """Build the defensibility check section.

    Always present in the report (even if deferred for EDD cases).
    """
    if reporting in ("UNKNOWN", "PENDING_COMPLIANCE_REVIEW"):
        # Active classifier conflict: classifier wants STR but governance chose otherwise
        alert_type = integrity_alert.get("type", "") if integrity_alert else ""
        if alert_type == "CLASSIFICATION_DISPOSITION_CONFLICT":
            governed = integrity_alert.get("governed_disposition", "EDD_REQUIRED")
            return {
                "status": "PENDING",
                "message": (
                    "Classifier determined STR REQUIRED, governed disposition is "
                    f"{governed.replace('_', ' ')}. Deviation justified by Gate 1 "
                    "(typology maturity)."
                ),
                "action": "Final defensibility depends on compliance officer review.",
                "note": (
                    "Reporting determination pending compliance officer review. "
                    "Classifier identified reasonable grounds to suspect but gate "
                    "evaluation blocked automatic escalation."
                ),
            }
        return {
            "status": "DEFERRED",
            "message": "Reporting determination pending compliance review.",
            "action": "Defensibility Alert will be evaluated upon final disposition.",
            "note": (
                "No historical filing pattern comparison performed. Reporting "
                "obligation will be assessed when review is complete and a final "
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
    _engine_disposition = proposed_canonical.get("disposition", "UNKNOWN")
    case_disposition = _to_canonical_disposition(governed_disposition)
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

    # Apply governed reclassification to v1 fallback counts (INV-005)
    _prop_can = precedent_analysis.get("proposed_canonical", {})
    _eng_disp = _prop_can.get("disposition", "UNKNOWN")
    _gov_disp = _to_canonical_disposition(governed_disposition)
    if _gov_disp != _eng_disp:
        _sc_list = precedent_analysis.get("sample_cases", []) or []
        supporting, contrary = 0, 0
        _neutral_fb = 0
        for _sc in _sc_list:
            _pd = _sc.get("disposition", "UNKNOWN")
            _pb = _sc.get("disposition_basis", "UNKNOWN")
            _cb = _prop_can.get("disposition_basis", "UNKNOWN")
            _nt = _sc.get("non_transferable", False)
            if _pd == "UNKNOWN" or _gov_disp == "UNKNOWN":
                _neutral_fb += 1
            elif _gov_disp == "EDD" or _pd == "EDD":
                if _gov_disp == "EDD" and _pd == "EDD" and not _nt:
                    supporting += 1
                else:
                    _neutral_fb += 1
            elif (_cb not in ("UNKNOWN", "") and _pb not in ("UNKNOWN", "")
                  and _cb != _pb):
                _neutral_fb += 1
            elif _pd == _gov_disp:
                supporting += 1 if not _nt else 0
            elif {_pd, _gov_disp} == {"ALLOW", "BLOCK"}:
                contrary += 1
            else:
                _neutral_fb += 1

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
    disposition_basis: str = "",
    integrity_alert: dict | None = None,
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

    # ── Governed reclassification (INV-005) ──────────────────────────
    # Engine classified against engine verdict. When governed disposition
    # differs, reclassify all sample_cases against governed canonical.
    proposed_canonical = precedent_analysis.get("proposed_canonical", {})
    engine_canonical_disp = proposed_canonical.get("disposition", "UNKNOWN")
    governed_canonical_disp = _to_canonical_disposition(governed_disposition)

    if governed_canonical_disp != engine_canonical_disp:
        # Recount using governed canonical disposition
        supporting, contrary, neutral = 0, 0, 0
        for sc in sample_cases:
            prec_disp = sc.get("disposition", "UNKNOWN")
            prec_basis = sc.get("disposition_basis", "UNKNOWN")
            case_basis = proposed_canonical.get("disposition_basis", "UNKNOWN")
            nt = sc.get("non_transferable", False)

            # INV-003: UNKNOWN is always neutral
            if prec_disp == "UNKNOWN" or governed_canonical_disp == "UNKNOWN":
                neutral += 1
            # INV-005: EDD is always neutral (except EDD == EDD)
            elif governed_canonical_disp == "EDD" or prec_disp == "EDD":
                if governed_canonical_disp == "EDD" and prec_disp == "EDD" and not nt:
                    supporting += 1
                else:
                    neutral += 1
            # INV-008: cross-basis is neutral
            elif (case_basis not in ("UNKNOWN", "") and prec_basis not in ("UNKNOWN", "")
                  and case_basis != prec_basis):
                neutral += 1
            # Same disposition = supporting (unless non-transferable)
            elif prec_disp == governed_canonical_disp:
                if nt:
                    neutral += 1
                else:
                    supporting += 1
            # INV-004: only ALLOW vs BLOCK is contrary
            elif {prec_disp, governed_canonical_disp} == {"ALLOW", "BLOCK"}:
                contrary += 1
            else:
                neutral += 1

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

    # ── b3) Alignment Context (explain low alignment) ─────────────────
    alignment_context_lines: list[str] = []

    # Policy shift context
    ra = precedent_analysis.get("policy_regime_analysis") or precedent_analysis.get("regime_analysis")
    if ra and ra.get("shifts_detected"):
        pre_count = ra.get("pre_shift_count", 0)
        post_count = ra.get("post_shift_count", 0)
        total_pool = pre_count + post_count
        pre_pct = int(pre_count / total_pool * 100) if total_pool > 0 else 0
        shift_name = ra["shifts_detected"][0].get("name", "policy shift") if ra["shifts_detected"] else "policy shift"
        # Compute post-shift alignment
        post_dist = ra.get("post_shift_distribution", {})
        post_aligned = sum(
            v for k, v in post_dist.items()
            if str(k).upper() == _gov_canonical
            or (_gov_canonical == "EDD" and ("EDD" in str(k).upper() or "REVIEW" in str(k).upper()))
            or (_gov_canonical == "ALLOW" and str(k).upper() in ("ALLOW", "NO_REPORT", "PASS", "CLEARED"))
            or (_gov_canonical == "BLOCK" and str(k).upper() in ("BLOCK", "STR_REQUIRED", "FILE_STR"))
        )
        post_total = sum(post_dist.values())
        post_align_pct = int(post_aligned / post_total * 100) if post_total > 0 else 0
        if pre_pct > 50:
            alignment_context_lines.append(
                f"{pre_count} of {total_pool} precedents ({pre_pct}%) were decided under "
                f"superseded policy ({shift_name}). Alignment reflects policy divergence, "
                f"not decisional error. Under current policy, {post_align_pct}% align."
            )

    # Non-transferable context
    nt_count = sum(1 for sc in sample_cases if sc.get("non_transferable"))
    comparable_count = len(sample_cases)
    if comparable_count > 0 and nt_count / comparable_count > 0.5:
        transferable = [sc for sc in sample_cases if not sc.get("non_transferable")]
        t_aligned = sum(1 for sc in transferable if sc.get("classification") == "supporting")
        t_count = len(transferable)
        t_pct = int(t_aligned / t_count * 100) if t_count > 0 else 0
        alignment_context_lines.append(
            f"{nt_count} of {comparable_count} precedents are non-transferable due to "
            f"driver contradictions. Effective transferable alignment: "
            f"{t_aligned}/{t_count} ({t_pct}%)."
        )

    result["alignment_context"] = alignment_context_lines

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

        # Two-axis classification data
        two_axis = match.get("two_axis", {}) or {}
        composite_label = two_axis.get("composite_label", "")
        composite_desc = two_axis.get("composite_description", "")

        thumb = {
            "precedent_id": match.get("precedent_id", "N/A"),
            "similarity_pct": sim_pct,
            "outcome_label": outcome_label,
            "classification": classification,
            "disposition": match.get("disposition", "UNKNOWN"),
            "reporting": match.get("reporting", "UNKNOWN"),
            "reporting_rationale": match.get("reporting_rationale", ""),
            "description": description,
            "key_matches": key_matches[:3],
            "key_differences": key_diffs[:3],
            "reason_codes": reason_codes,
            # Two-axis classification
            "two_axis": two_axis,
            "composite_label": composite_label,
            "composite_description": composite_desc,
        }
        if is_v3:
            thumb["matched_drivers"] = matched_drivers
            thumb["mismatched_drivers"] = mismatched_drivers
        if match.get("non_transferable"):
            thumb["non_transferable"] = True
            thumb["non_transferable_reasons"] = match.get("non_transferable_reasons", [])
        case_thumbnails.append(thumb)
    result["case_thumbnails"] = case_thumbnails

    # Transferable pool stats
    _nt_thumb_count = sum(1 for t in case_thumbnails if t.get("non_transferable"))
    result["transferable_count"] = len(case_thumbnails) - _nt_thumb_count
    result["non_transferable_count"] = _nt_thumb_count

    # ── c2) Two-axis pool statistics & alignment split ─────────────────
    two_axis_pool = precedent_analysis.get("two_axis_pool") or {}
    ta_total = two_axis_pool.get("total", 0)
    ta_op_aligned = two_axis_pool.get("op_aligned", 0)
    ta_reg_aligned = two_axis_pool.get("reg_aligned", 0)
    ta_combined = two_axis_pool.get("combined_aligned", 0)
    ta_str_count = two_axis_pool.get("str_filing_count", 0)
    ta_str_pct = two_axis_pool.get("str_filing_rate_pct", 0)
    ta_composite_dist = two_axis_pool.get("composite_label_distribution", {})

    result["two_axis_pool"] = two_axis_pool
    result["op_alignment_count"] = ta_op_aligned
    result["op_alignment_total"] = ta_total
    result["reg_alignment_count"] = ta_reg_aligned
    result["reg_alignment_total"] = ta_total
    result["combined_alignment_count"] = ta_combined
    result["str_filing_count"] = ta_str_count
    result["str_filing_rate_pct"] = ta_str_pct

    # Suspicion posture narrative (Part 5)
    suspicion_posture_lines: list[str] = []
    if ta_total > 0:
        suspicion_posture_lines.append(
            f"Suspicion posture: Of {ta_total} comparable cases, "
            f"{ta_str_count} resulted in STR filing ({ta_str_pct}%)."
        )
        if ta_str_count == 0:
            suspicion_posture_lines.append(
                "The institution has not previously identified reasonable grounds "
                "to suspect ML/TF in comparable cases."
            )
        # First-of-kind suspicion finding
        case_reporting = (
            precedent_analysis.get("proposed_canonical", {}).get("reporting", "")
        )
        if case_reporting in ("FILE_STR", "STR", "STR_REQUIRED") and ta_str_count == 0:
            suspicion_posture_lines.append(
                "\u26a0 FIRST-OF-KIND SUSPICION FINDING: No comparable case has "
                "previously triggered STR. This determination establishes new "
                "institutional precedent for this case profile."
            )
    result["suspicion_posture"] = suspicion_posture_lines

    # Two-axis alignment narrative (Part 6)
    two_axis_alignment_narrative = ""
    if ta_total > 0:
        op_pct = round(ta_op_aligned / ta_total * 100) if ta_total > 0 else 0
        reg_pct = round(ta_reg_aligned / ta_total * 100) if ta_total > 0 else 0
        combined_pct = round(ta_combined / ta_total * 100) if ta_total > 0 else 0
        two_axis_alignment_narrative = (
            f"Operational alignment: {ta_op_aligned}/{ta_total} ({op_pct}%)\n"
            f"Regulatory alignment: {ta_reg_aligned}/{ta_total} ({reg_pct}%)\n"
            f"Combined alignment: {ta_combined}/{ta_total} ({combined_pct}%)"
        )
        # Detect all-UNDETERMINED regulatory pool
        _all_reg_pending = (
            ta_reg_aligned == 0
            and ta_composite_dist
            and all("REG_PENDING" in k for k in ta_composite_dist)
        )
        result["reg_alignment_all_undetermined"] = _all_reg_pending

        # Contextual explanation
        if _all_reg_pending:
            two_axis_alignment_narrative += (
                "\n\nRegulatory alignment is 0% \u2014 current case requires Enhanced "
                "Due Diligence before reporting determination. Comparable cases "
                "have resolved reporting, but alignment cannot be computed until "
                "this case\u2019s regulatory posture is determined."
            )
        elif op_pct >= 70 and reg_pct < 30:
            two_axis_alignment_narrative += (
                "\n\nHigh operational alignment indicates institutional consensus on "
                "adverse action. Low regulatory alignment reflects absence of STR "
                "precedent for this profile."
            )
        elif reg_pct >= 70 and op_pct < 30:
            two_axis_alignment_narrative += (
                "\n\nHigh regulatory alignment indicates consistent suspicion findings. "
                "Low operational alignment reflects divergence in operational response."
            )
    result["two_axis_alignment_narrative"] = two_axis_alignment_narrative

    # Pool-level composite label finding (Part 4)
    pool_composite_finding = ""
    if ta_total > 0 and ta_composite_dist:
        dominant_label = max(ta_composite_dist, key=ta_composite_dist.get)
        dominant_count = ta_composite_dist[dominant_label]
        if dominant_count == ta_total and ta_total > 1:
            _label_readable = dominant_label.replace("_", " ").lower()
            pool_composite_finding = (
                f"All {ta_total} comparable precedents share the same "
                f"classification: {_label_readable}."
            )
            if dominant_label == "OP_ALIGNED_REG_DIVERGENT":
                pool_composite_finding += (
                    " Adverse action was taken in every case, but no STR was filed. "
                    "The current STR determination has no direct regulatory "
                    "precedent support."
                )
            elif dominant_label in (
                "OP_ALIGNED_REG_PENDING", "PARTIAL_REG_PENDING", "OP_CONTRARY_REG_PENDING",
            ):
                pool_composite_finding += (
                    " Regulatory alignment cannot be assessed — no comparable "
                    "case has reached reporting determination."
                )
    result["pool_composite_finding"] = pool_composite_finding

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

    # ── e2) Post-shift STR gap statement ─────────────────────────────
    # When current disposition is completely absent from post-shift pool
    # outcomes, explain that determination is precedent-independent.
    regime = precedent_analysis.get("policy_regime_analysis", {})
    post_dist = regime.get("post_shift_distribution", {}) if regime else {}
    if post_dist:
        governed_canonical = _to_canonical_disposition(governed_disposition)
        post_outcomes = {_to_canonical_disposition(str(k)) for k in post_dist}
        if governed_canonical not in post_outcomes:
            if disposition_basis == "MANDATORY":
                basis = "hard stop rule"
            elif integrity_alert and integrity_alert.get("type") in (
                "CLASSIFIER_OVERRIDE", "CLASSIFIER_UPGRADE",
            ):
                basis = "classifier sovereignty"
            elif integrity_alert and integrity_alert.get("type") == "CLASSIFICATION_DISPOSITION_CONFLICT":
                basis = "gate authority constraining classifier determination"
            elif classification_outcome:
                basis = f"classifier {classification_outcome.replace('_', ' ').lower()} determination"
            else:
                basis = "current rule evaluation"
            governed_label = governed_disposition.replace("_", " ")
            result["post_shift_gap_statement"] = (
                f"No post-shift precedent exists for {governed_label} "
                f"on this case profile. Determination is based on {basis} "
                f"which operates independently of policy regime precedent."
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

    # ── Confidence dimensions (4-factor model) — always computed ──────
    # The 4-factor model (pool_adequacy, similarity_quality,
    # outcome_consistency, evidence_completeness) renders for all cases.
    result["confidence_dimensions"] = precedent_analysis.get("confidence_dimensions", [])
    result["confidence_level"] = precedent_analysis.get("confidence_level")
    result["confidence_bottleneck"] = precedent_analysis.get("confidence_bottleneck")
    result["confidence_hard_rule"] = precedent_analysis.get("confidence_hard_rule")

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

        # j2) First-impression / first-of-kind alert
        _ra = precedent_analysis.get("policy_regime_analysis") or precedent_analysis.get("regime_analysis") or {}
        _post_shift_count = _ra.get("post_shift_count", 0) if _ra else len(sample_cases)
        _fi_nt_count = sum(1 for sc in sample_cases if sc.get("non_transferable"))
        _fi_transferable_count = len(sample_cases) - _fi_nt_count
        if _post_shift_count <= 2 and _fi_transferable_count <= 2:
            result["first_impression_alert"] = (
                "Insufficient post-shift and transferable precedent to establish pattern. "
                "Treat as first-impression determination requiring senior review."
            )
        elif _ra and _post_shift_count > 0:
            # Check if post-shift pool has zero alignment for current disposition
            _ps_dist = _ra.get("post_shift_distribution", {})
            _ps_aligned = sum(
                v for k, v in _ps_dist.items()
                if str(k).upper() == _gov_canonical
                or (_gov_canonical == "EDD" and ("EDD" in str(k).upper() or "REVIEW" in str(k).upper()))
                or (_gov_canonical == "ALLOW" and str(k).upper() in ("ALLOW", "NO_REPORT", "PASS", "CLEARED"))
                or (_gov_canonical == "BLOCK" and str(k).upper() in ("BLOCK", "STR_REQUIRED", "FILE_STR"))
            )
            if _ps_aligned == 0:
                _ps_outcomes = ", ".join(f"{k}: {v}" for k, v in sorted(_ps_dist.items()))
                result["first_impression_alert"] = (
                    f"No post-shift precedent supports {governed_disposition} for this case profile. "
                    f"All {_post_shift_count} post-shift cases resolved as {_ps_outcomes}. "
                    f"This is a first-of-kind {governed_disposition} under current policy "
                    f"— senior compliance review required."
                )

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

        # l) B1.7: Regime analysis — propagate temporal partitioning
        ra = precedent_analysis.get("regime_analysis")
        if ra:
            result["regime_analysis"] = ra
            # Add regime_limited flag to case thumbnails
            for thumb in result.get("case_thumbnails", []):
                pid_prefix = thumb.get("precedent_id", "")
                for sc in sample_cases:
                    if sc.get("precedent_id") == pid_prefix and sc.get("regime_limited"):
                        thumb["regime_limited"] = True
                        break

    # GAP-D: Precedent disclaimer (backend-sourced)
    result["precedent_disclaimer"] = (
        "Precedent analysis is non-authoritative; used only for consistency "
        "review and peer comparison; never overrides gates, rules, or "
        "statutory reporting determinations. Precedent does not influence "
        "and cannot modify the Reasonable Grounds to Suspect (RGS) "
        "determination, which is a legal assessment reserved for the "
        "compliance officer."
    )

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

    # ── Spec §10.2: Non-terminal (EDD) handling ──────────────────────
    governed_canonical = _to_canonical_disposition(governed_disposition)
    _is_edd = governed_canonical == "EDD"

    if _is_edd:
        # Count terminal outcomes in the pool (ALLOW/BLOCK) for directional guidance
        terminal_allow = sum(
            v for k, v in (match_distribution or {}).items()
            if str(k).upper() in ("ALLOW", "NO_REPORT", "PASS", "CLEARED")
        )
        terminal_block = sum(
            v for k, v in (match_distribution or {}).items()
            if str(k).upper() in ("BLOCK", "STR_REQUIRED", "FILE_STR")
        )
        terminal_total = terminal_allow + terminal_block
        edd_count = sum(
            v for k, v in (match_distribution or {}).items()
            if "EDD" in str(k).upper() or "REVIEW" in str(k).upper()
        )
        # Use distribution total as pool size (may differ from sample-based total_all)
        dist_pool = sum((match_distribution or {}).values())
        pool_size = max(total_all, dist_pool)

        if terminal_total > 0:
            # Use match_distribution for terminal direction (not supporting/contrary
            # which reflect same-disposition alignment, not ALLOW vs BLOCK)
            if terminal_allow >= terminal_block:
                majority = "ALLOW"
                majority_pct = int(terminal_allow / terminal_total * 100)
            else:
                majority = "BLOCK"
                majority_pct = int(terminal_block / terminal_total * 100)
            parts.append(
                f"Of {pool_size} comparable cases (by similarity), {terminal_total} have reached "
                f"terminal resolution — {majority_pct}% resulted in "
                f"{majority.replace('_', ' ')}"
            )
            if terminal_allow > 0 and terminal_block > 0:
                minority = "BLOCK" if terminal_allow >= terminal_block else "ALLOW"
                minority_count = terminal_block if terminal_allow >= terminal_block else terminal_allow
                minority_pct = 100 - majority_pct
                parts[-1] += (
                    f", {minority_pct}% in {minority} ({minority_count} of {terminal_total})"
                )
            parts[-1] += (
                ". Current case is pending EDD; "
                "terminal guidance is directional."
            )
        elif edd_count > 0:
            parts.append(
                f"All {edd_count} comparable case(s) remain in enhanced review. "
                f"No terminal outcomes exist in the comparable pool."
            )
        else:
            parts.append(f"{total_all} comparable precedents found.")

    # Opening: how many comparable cases and what they resulted in
    elif total_decisive > 0:
        if supporting == total_decisive:
            parts.append(
                f"Of {total_all} top comparable cases (by similarity), all {total_decisive} terminal "
                f"precedents resulted in {governed_label}."
            )
        elif supporting > contrary:
            support_pct = int(supporting / total_decisive * 100)
            parts.append(
                f"Of {total_all} top comparable cases (by similarity), {support_pct}% "
                f"({supporting} of {total_decisive} terminal) resulted in "
                f"{governed_label}."
            )
        elif contrary > supporting:
            contrary_pct = int(contrary / total_decisive * 100)
            parts.append(
                f"Of {total_all} top comparable cases (by similarity), {contrary_pct}% "
                f"({contrary} of {total_decisive} terminal) resulted in a "
                f"different outcome than the current {governed_label} determination."
            )
        else:
            parts.append(
                f"Of {total_all} top comparable cases (by similarity), terminal precedents are "
                f"evenly split ({supporting} supporting, {contrary} contrary)."
            )

    if not _is_edd and neutral > 0:
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

    summary = " ".join(parts) if parts else f"{total_all} comparable precedents found."

    # Advisory-only framing — where the reviewer's eye lands
    summary += (
        " Advisory only: precedent patterns inform consistency review but do not "
        "determine, modify, or constrain the statutory reporting obligation. "
        "The RGS determination is a legal assessment made by the compliance "
        "officer independent of historical disposition patterns."
    )

    return summary


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
                f"All {neutral} comparable precedent(s) (stratified sample) resolved "
                f"through enhanced due diligence — consistent with the current "
                f"{governed_label} disposition. The bank's institutional practice "
                f"for this case profile is uniform EDD referral. No terminal "
                f"outcomes (ALLOW/BLOCK) exist in the stratified sample."
            )
        return (
            f"All {neutral} comparable precedent(s) (stratified sample) resolved "
            f"through review processes. No terminal outcomes available to "
            f"establish directional institutional posture."
        )

    support_pct = int(supporting / total_decisive * 100) if total_decisive > 0 else 0

    governed_canonical = _to_canonical_disposition(governed_disposition)
    if governed_canonical == "EDD" and supporting > 0 and contrary == 0:
        # All matches are EDD-vs-EDD supporting — not terminal
        return (
            f"All {supporting} transferable comparable precedent(s) were also "
            f"referred for enhanced due diligence — consistent with the current "
            f"{governed_label} disposition. The bank's institutional practice "
            f"for this case profile is uniform EDD referral."
        )

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

    # ── CASE 0: Hard stop — only the hard stop reason matters ───────────
    # For any hard stop (sanctions, adverse media, etc.), suspicion-flavored
    # signals are irrelevant — the hard stop is the sole decision driver.
    if facts.get("hard_stop_triggered"):
        hard_stop_reason = str(facts.get("hard_stop_reason", "")).upper()
        if "SANCTIONS" in hard_stop_reason:
            drivers = ["Sanctions screening match — immediate block"]
        elif "ADVERSE_MEDIA" in hard_stop_reason:
            drivers = ["Adverse media — confirmed MLTF link (hard stop)"]
        else:
            drivers = [f"Hard stop triggered: {facts.get('hard_stop_reason', 'mandatory rule trigger')}"]
        method = txn.get("method") or ev_map.get("txn.method") or ev_map.get("txn.type") or ""
        if method:
            drivers.append(f"{str(method).replace('_', ' ').title()} channel")
        if ev_map.get("txn.cross_border") or ev_map.get("flag.cross_border") or txn.get("cross_border"):
            drivers.append("Cross-border transaction")
        return drivers

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
        method = txn.get("method") or ev_map.get("txn.method") or ev_map.get("txn.type") or ""
        if method and str(method).lower() in {"wire", "wire_transfer", "wire_international", "wire_domestic", "swift", "eft"}:
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
    method = txn.get("method") or ev_map.get("txn.method") or ev_map.get("txn.type") or ""
    if method and str(method).lower() in {"wire", "wire_transfer", "wire_international", "wire_domestic", "swift", "eft"}:
        drivers.append(f"{trigger_prefix}Wire transfer channel ({str(method).upper()})")

    cust_type = customer.get("type") or ev_map.get("customer.type") or ""
    if cust_type and str(cust_type).lower() in {"corporation", "corporate", "business", "entity"}:
        drivers.append(f"{trigger_prefix}Corporate customer profile")
    if (customer.get("pep_flag")
            or ev_map.get("flag.pep")
            or ev_map.get("customer.pep")
            or ev_map.get("screening.pep_match")):
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

def _build_risk_factors(normalized: dict, primary_typology: str = "") -> list[dict]:
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

    _MATURITY_LABELS = {
        "FORMING": "Early-stage — pattern forming, not yet established",
        "EMERGING": "Early-stage — pattern emerging, not yet established",
        "VALIDATING": "Early-stage — pattern under validation, not yet established",
        "ESTABLISHED": "Established — sufficient corroboration, pattern validated",
    }
    _POSITIONAL_LABELS = {"primary", "secondary", "tertiary", "main", "default"}
    _NO_TYPOLOGY = "No suspicious typology identified"
    for typology in layer4_typologies.get("typologies", []) or []:
        if isinstance(typology, dict):
            name = typology.get("name") or "Typology"
            maturity = _canonical_maturity(typology.get("maturity") or "")
            mapped_name = _TYPOLOGY_CODE_MAP.get(name.lower().replace(" ", "_").replace("-", "_"), name)
            # If name is a positional label (e.g. "primary"), use resolved primary_typology
            if mapped_name.lower() in _POSITIONAL_LABELS and primary_typology:
                mapped_name = primary_typology
            # Never combine "No suspicious typology" or "Typology indicators present"
            # with redundant maturity labels — these already convey the status.
            _is_no_typology = mapped_name == _NO_TYPOLOGY
            _is_indicator_label = (
                mapped_name.startswith("Typology indicators present")
                or mapped_name.startswith("Unclassified behavioral")
                or "(maturity: forming)" in mapped_name
            )
            if (_is_no_typology or _is_indicator_label) and maturity:
                if _is_pre_established(maturity):
                    value = (
                        f"Typology indicators present — below maturity threshold "
                        f"({_MATURITY_LABELS.get(maturity.upper(), maturity)}) [{name}/{maturity}]"
                    )
                else:
                    readable_maturity = _MATURITY_LABELS.get(maturity.upper(), maturity)
                    value = f"Typology indicators ({readable_maturity}) [{name}/{maturity}]"
            elif maturity:
                readable_maturity = _MATURITY_LABELS.get(maturity.upper(), maturity)
                value = f"{mapped_name} ({readable_maturity}) [{name}/{maturity}]"
            else:
                value = mapped_name if mapped_name != name else name
            risk_factors.append({"field": "Typology", "value": value})

    _SUSPICION_ELEMENT_LABELS = {
        "has_sustained_pattern": "Sustained pattern of suspicious activity detected",
        "has_intent": "Intent indicators present in transaction behavior",
        "has_deception": "Deception indicators present in customer conduct",
    }
    elements = layer6_suspicion.get("elements", {}) or {}
    for element, active in elements.items():
        if active:
            readable = _SUSPICION_ELEMENT_LABELS.get(element, element.replace("_", " ").capitalize())
            value_display = f"{readable} [{element}]"
            risk_factors.append({"field": "Suspicion element", "value": value_display})

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


# ── Decision Conflict Alert ──────────────────────────────────────────────────

def _build_decision_conflict_alert(
    classification_outcome: str,
    engine_disposition: str,
    governed_disposition: str,
    gate1_passed: bool,
    gate1_sections: list,
    gate2_sections: list,
    is_mandatory_hard_stop: bool = False,
) -> dict | None:
    """Build at-a-glance conflict alert when classifier != engine."""
    if is_mandatory_hard_stop:
        return None  # Sanctions are not conflicts — they're terminal prohibitions
    if not classification_outcome or classification_outcome == engine_disposition:
        return None

    blocking_gates = []
    for section in gate1_sections:
        if not section.get("passed"):
            blocking_gates.append({
                "gate": "Gate 1 (Typology Maturity)",
                "reason": section.get("reason", ""),
                "name": section.get("name", ""),
            })
    # Only evaluate gate2 when gate1 passed — otherwise gate2 was never reached
    if gate1_passed:
        for section in gate2_sections:
            if not section.get("passed"):
                blocking_gates.append({
                    "gate": "Gate 2 (STR Threshold)",
                    "reason": section.get("reason", ""),
                    "name": section.get("name", ""),
                })

    if blocking_gates:
        gate_names = list(dict.fromkeys(g["gate"] for g in blocking_gates))
        resolution = (
            f"{', '.join(gate_names)} blocked escalation"
            + (f" — {_clean_period(blocking_gates[0]['reason'])}" if blocking_gates[0]['reason'] else "")
            + ". Engine followed gate logic."
        )
    elif engine_disposition != governed_disposition:
        resolution = "Governance correction applied — governed outcome is authoritative."
    else:
        resolution = "Engine disposition stands; classifier recommendation not applied."

    return {
        "classifier": classification_outcome.replace("_", " "),
        "engine": engine_disposition.replace("_", " "),
        "governed": governed_disposition.replace("_", " "),
        "resolution": resolution,
        "blocking_gates": blocking_gates,
    }


# ── Decision Path Narrative Trace ────────────────────────────────────────────

def _build_decision_path_narrative(
    *,
    classification_outcome: str,
    tier1_signals: list[dict],
    tier2_signals: list[dict],
    suspicion_count: int,
    investigative_count: int,
    gate1_passed: bool,
    gate1_decision: str,
    gate1_sections: list[dict],
    gate2_decision: str,
    gate2_status: str,
    gate2_sections: list[dict],
    primary_typology: str,
    typology_stage: str,
    engine_disposition: str,
    governed_disposition: str,
    str_required: bool,
    layer1_facts: dict,
    layer6_suspicion: dict,
    decision_conflict_alert: dict | None,
    integrity_alert: dict | None,
    is_mandatory_hard_stop: bool = False,
) -> dict:
    """Build 5-step narrative trace explaining the decision path."""

    steps: list[dict] = []

    # ── Step ① — Classifier Assessment ───────────────────────────────────
    detail_1: list[str] = []
    hard_stop = layer1_facts.get("hard_stop_triggered")
    if hard_stop:
        reason = layer1_facts.get("hard_stop_reason", "mandatory rule trigger")
        detail_1.append(f"Hard stop triggered: {reason}.")
    t1_codes = [s.get("code", "UNKNOWN") for s in tier1_signals]
    t2_count = len(tier2_signals)
    if suspicion_count > 0:
        detail_1.append(
            f"{suspicion_count} Tier 1 suspicion indicator(s) detected: "
            f"{', '.join(t1_codes)}."
        )
    else:
        detail_1.append("No Tier 1 suspicion indicators found.")
    if t2_count > 0:
        detail_1.append(f"{t2_count} Tier 2 investigative signal(s) noted.")
    arrow_1 = f"Classifier recommends: {classification_outcome.replace('_', ' ')}"
    steps.append({
        "number": 1,
        "symbol": "\u2460",
        "title": "Classifier Assessment",
        "detail_lines": detail_1,
        "arrow_line": arrow_1,
    })

    # ── Step ② — Gate 1 — Zero-False-Escalation Check ────────────────────
    detail_2: list[str] = []
    if hard_stop:
        detail_2.append("Hard stop active — Gate 1 fast-tracks (Section A passes immediately).")
    else:
        stage_upper = (typology_stage or "NONE").upper()
        if _is_pre_established(stage_upper):
            detail_2.append(
                f"Primary typology: {primary_typology} (stage: {stage_upper})."
            )
            detail_2.append(
                f"Institutional policy: Escalation not permitted absent ESTABLISHED typology. "
                f"{stage_upper} typologies require EDD before escalation determination."
            )
        elif stage_upper == "ESTABLISHED":
            detail_2.append(
                f"Primary typology: {primary_typology} (stage: ESTABLISHED)."
            )
            detail_2.append("Rule: Typology maturity confirmed at ESTABLISHED level.")
        else:
            detail_2.append("No typology pattern detected.")

    # Include first failing section reason if gate blocked
    if not gate1_passed:
        for section in gate1_sections:
            if not section.get("passed"):
                detail_2.append(
                    f"Blocking section — {section.get('name', 'Unknown')}: "
                    f"{_clean_period(section.get('reason', 'failed'))}."
                )
                break

    if gate1_passed:
        arrow_2 = f"Gate 1: PERMITTED \u2014 {gate1_decision or 'escalation allowed'}"
    else:
        fail_reason = "escalation blocked"
        for section in gate1_sections:
            if not section.get("passed") and section.get("reason"):
                fail_reason = section["reason"].rstrip(".")
                break
        arrow_2 = f"Gate 1: BLOCKED \u2014 {fail_reason}"
    steps.append({
        "number": 2,
        "symbol": "\u2461",
        "title": "Gate 1 \u2014 Zero-False-Escalation Check",
        "detail_lines": detail_2,
        "arrow_line": arrow_2,
    })

    # ── Step ③ — Gate 2 — STR Threshold ──────────────────────────────────
    detail_3: list[str] = []
    if is_mandatory_hard_stop:
        detail_3.append("Not applicable \u2014 sanctions hard stop supersedes suspicion threshold test.")
        arrow_3 = "Gate 2: NOT APPLICABLE \u2014 mandatory enforcement"
    elif not gate1_passed:
        detail_3.append("Pre-condition: Gate 1 clearance required.")
        arrow_3 = "Gate 2: NOT EVALUATED \u2014 upstream gate blocked"
    elif (gate2_status or "").upper() == "SKIPPED":
        detail_3.append("Gate 2 evaluation skipped (not required for this path).")
        arrow_3 = "Gate 2: SKIPPED \u2014 not applicable"
    else:
        for section in gate2_sections:
            status = "PASS" if section.get("passed") else "FAIL"
            detail_3.append(
                f"{section.get('name', 'Unknown')}: {status}"
                + (f" \u2014 {section.get('reason', '')}" if section.get("reason") else "")
            )
        arrow_3 = f"Gate 2: {gate2_decision or 'N/A'}"
    steps.append({
        "number": 3,
        "symbol": "\u2462",
        "title": "Gate 2 \u2014 STR Threshold",
        "detail_lines": detail_3,
        "arrow_line": arrow_3,
    })

    # ── Step ④ — Governed Resolution ─────────────────────────────────────
    detail_4: list[str] = []
    clf_label = classification_outcome.replace("_", " ")
    g1_label = "PERMITTED" if gate1_passed else "BLOCKED"
    if is_mandatory_hard_stop:
        g2_label = "NOT APPLICABLE"
    elif not gate1_passed:
        g2_label = "NOT EVALUATED"
    else:
        g2_label = gate2_decision or "N/A"
    detail_4.append(
        f"Classifier recommended {clf_label} \u2192 "
        f"Gate 1 {g1_label} \u2192 "
        f"Gate 2 {g2_label} \u2192 "
        f"Governed: {governed_disposition.replace('_', ' ')}."
    )
    if decision_conflict_alert:
        detail_4.append(
            f"Conflict resolution: {decision_conflict_alert.get('resolution', '')}"
        )
    else:
        detail_4.append(
            f"All components agree. Disposition confirmed: "
            f"{governed_disposition.replace('_', ' ')}."
        )

    arrow_4 = f"Governed disposition: {governed_disposition.replace('_', ' ')}"
    steps.append({
        "number": 4,
        "symbol": "\u2463",
        "title": "Governed Resolution",
        "detail_lines": detail_4,
        "arrow_line": arrow_4,
    })

    # ── Step ⑤ — Terminal Disposition ─────────────────────────────────────
    detail_5: list[str] = []
    gd_upper = governed_disposition.upper().replace(" ", "_")
    if gd_upper == "STR_REQUIRED" or str_required:
        detail_5.append("File STR within statutory timeframe.")
    elif gd_upper == "EDD_REQUIRED" or gd_upper in ("REVIEW", "ESCALATE", "PENDING_REVIEW", "PASS_WITH_EDD"):
        detail_5.append("Enhanced due diligence required before final determination.")
    elif gd_upper == "NO_REPORT" or gd_upper in ("CLEARED", "ALLOW", "PASS"):
        detail_5.append("No reporting obligation at this time.")
    else:
        detail_5.append("Awaiting compliance officer determination.")

    arrow_5 = f"Terminal disposition: {governed_disposition.replace('_', ' ')}"
    steps.append({
        "number": 5,
        "symbol": "\u2464",
        "title": "Terminal Disposition",
        "detail_lines": detail_5,
        "arrow_line": arrow_5,
    })

    # Original path code for cross-reference
    if gd_upper in ("STR_REQUIRED",) or str_required:
        path_code = "PATH_2_SUSPICION"
    elif hard_stop:
        path_code = "PATH_1_HARD_STOP"
    else:
        path_code = "NO_ESCALATION"

    return {
        "steps": steps,
        "path_code": path_code,
    }


# ── FIX-028: Gate Override Explanations ──────────────────────────────────────

def _build_gate_override_explanations(
    gate1_passed: bool,
    gate1_decision: str,
    gate1_sections: list,
    gate2_decision: str,
    gate2_status: str,
    gate2_sections: list,
    governed_disposition: str,
    str_required: bool,
    integrity_alert: dict | None,
    rules_fired: list,
    classification_outcome: str = "",
    is_mandatory_hard_stop: bool = False,
) -> list[dict]:
    """Build explanations for each gate whose result conflicts with final disposition."""
    final_is_escalation = governed_disposition in ("STR_REQUIRED", "ESCALATE") or str_required
    final_is_cleared = governed_disposition in ("NO_REPORT", "CLEARED")

    explanations: list[dict] = []

    # Gate 1 conflict: blocked but final is escalation
    gate1_blocked = not gate1_passed
    if gate1_blocked and final_is_escalation:
        override_mechanism = "Classifier sovereignty"
        override_basis = []
        authority = "PCMLTFA s. 7(1) — Preliminary suspicion assessment"
        if integrity_alert:
            atype = integrity_alert.get("type", "")
            if atype == "CLASSIFIER_UPGRADE":
                override_mechanism = "Classifier sovereignty — Tier 1 indicators override gate"
                override_basis.append("Classifier identified Tier 1 suspicion indicators")
            elif atype == "CLASSIFICATION_DISPOSITION_CONFLICT":
                override_mechanism = "Compliance review pending — conflict deferred"
                override_basis.append("Classifier and gate disagree; deferred to compliance officer")
            else:
                override_mechanism = f"Integrity correction ({atype})"
        for section in gate1_sections:
            if not section.get("passed"):
                override_basis.append(f"{section.get('name', 'Unknown')}: {section.get('reason', 'failed')}")
        if not override_basis:
            override_basis.append("Hard stop rule triggered — mandatory escalation")
        explanations.append({
            "gate": "Gate 1: Zero-False-Escalation Check",
            "gate_result": gate1_decision or "BLOCKED",
            "final_disposition": governed_disposition,
            "conflict": True,
            "override_mechanism": override_mechanism,
            "override_basis": override_basis,
            "authority": authority,
        })

    # Gate 1 conflict: permitted but final is cleared due to governance correction
    elif not gate1_blocked and final_is_cleared:
        if integrity_alert and integrity_alert.get("type") in (
            "CONTROL_CONTRADICTION", "ESCALATION_WITHOUT_SUSPICION",
        ):
            override_basis = ["0 Tier 1 suspicion indicators — escalation not permitted under institutional policy"]
            explanations.append({
                "gate": "Gate 1: Zero-False-Escalation Check",
                "gate_result": gate1_decision or "ALLOWED",
                "final_disposition": governed_disposition,
                "conflict": True,
                "override_mechanism": "Governance correction — escalation prohibited pending corroboration",
                "override_basis": override_basis,
                "authority": "PCMLTFA s. 7 — STR requires Tier 1 suspicion, not risk alone",
            })

    # Gate 2 conflict: skip entirely when gate1 blocked (gate2 was not evaluated)
    # or when mandatory hard stop (sanctions bypass suspicion threshold)
    if gate1_blocked or is_mandatory_hard_stop:
        if not explanations and gate1_blocked:
            classifier_wanted_str = classification_outcome in ("STR_REQUIRED",)
            governed_is_not_str = governed_disposition not in ("STR_REQUIRED", "ESCALATE")
            if classifier_wanted_str and governed_is_not_str:
                upheld_basis = []
                for section in gate1_sections:
                    if not section.get("passed"):
                        upheld_basis.append(
                            f"{section.get('name', 'Unknown')}: {section.get('reason', '')}"
                        )
                explanations.append({
                    "gate": "Gate 1: Zero-False-Escalation Check",
                    "gate_result": gate1_decision or "BLOCKED",
                    "final_disposition": governed_disposition,
                    "conflict": False,
                    "upheld": True,
                    "classifier_recommendation": classification_outcome,
                    "upheld_detail": (
                        f"Gate determination followed. Classifier recommendation "
                        f"({classification_outcome.replace('_', ' ')}) was not applied. "
                        f"Governed disposition reflects gate authority."
                    ),
                    "upheld_basis": upheld_basis,
                    "authority": "PCMLTFA s. 7 — Gate authority over classifier recommendation",
                })
        if not explanations:
            return [{"gate": "All Gates", "conflict": False, "final_disposition": governed_disposition}]
        return explanations

    gate2_says_str = "STR" in str(gate2_decision).upper() or "STR" in str(gate2_status).upper()
    gate2_says_insufficient = (
        "INSUFFICIENT" in str(gate2_decision).upper()
        or "EDD" in str(gate2_decision).upper()
        or (gate2_status and "REVIEW" in str(gate2_status).upper())
    )
    if gate2_says_insufficient and str_required:
        override_mechanism = "Classifier sovereignty"
        if integrity_alert and integrity_alert.get("type") == "CLASSIFIER_UPGRADE":
            override_mechanism = "Classifier sovereignty — Tier 1 indicators support preliminary RGS assessment"
        override_basis = []
        for section in gate2_sections:
            if not section.get("passed"):
                override_basis.append(f"{section.get('name', 'Unknown')}: {section.get('reason', 'insufficient')}")
        triggered = [
            r for r in rules_fired
            if str(r.get("result", "")).upper() in {"TRIGGERED", "ACTIVATED", "FAIL", "FAILED"}
        ]
        for rule in triggered[:3]:
            override_basis.append(f"Rule {rule.get('code', 'N/A')}: {rule.get('reason', '')}")
        explanations.append({
            "gate": "Gate 2: STR Threshold",
            "gate_result": gate2_decision or gate2_status or "INSUFFICIENT",
            "final_disposition": governed_disposition,
            "conflict": True,
            "override_mechanism": override_mechanism,
            "override_basis": override_basis or ["Classifier identified sufficient Tier 1 indicators"],
            "authority": "PCMLTFA s. 7(1) — Preliminary RGS assessment (compliance officer review required)",
        })

    # Gate 2 conflict: said STR but didn't file
    elif gate2_says_str and not str_required:
        override_basis = ["0 Tier 1 suspicion indicators — STR threshold not met"]
        if integrity_alert:
            override_basis.append(f"Integrity alert: {integrity_alert.get('type', 'N/A')}")
        explanations.append({
            "gate": "Gate 2: STR Threshold",
            "gate_result": gate2_decision or "STR_REQUIRED",
            "final_disposition": governed_disposition,
            "conflict": True,
            "override_mechanism": "Governance correction — STR threshold not satisfied",
            "override_basis": override_basis,
            "authority": "PCMLTFA s. 7 — STR requires Tier 1 suspicion indicators",
        })

    # ── Gate UPHELD: gate blocked, classifier wanted STR, governed follows gate ──
    if not explanations and gate1_blocked:
        classifier_wanted_str = classification_outcome in ("STR_REQUIRED",)
        governed_is_not_str = governed_disposition not in ("STR_REQUIRED", "ESCALATE")
        if classifier_wanted_str and governed_is_not_str:
            upheld_basis = []
            for section in gate1_sections:
                if not section.get("passed"):
                    upheld_basis.append(
                        f"{section.get('name', 'Unknown')}: {section.get('reason', '')}"
                    )
            explanations.append({
                "gate": "Gate 1: Zero-False-Escalation Check",
                "gate_result": gate1_decision or "BLOCKED",
                "final_disposition": governed_disposition,
                "conflict": False,
                "upheld": True,
                "classifier_recommendation": classification_outcome,
                "upheld_detail": (
                    f"Gate determination followed. Classifier recommendation "
                    f"({classification_outcome.replace('_', ' ')}) was not applied. "
                    f"Governed disposition reflects gate authority."
                ),
                "upheld_basis": upheld_basis,
                "authority": "PCMLTFA s. 7 — Gate authority over classifier recommendation",
            })

    if not explanations:
        return [{"gate": "All Gates", "conflict": False, "final_disposition": governed_disposition}]
    return explanations


# ── FIX-029: Disposition Reconciliation ──────────────────────────────────────

def _build_disposition_reconciliation(
    engine_disposition: str,
    governed_disposition: str,
    classification_outcome: str,
    integrity_alert: dict | None,
    corrections: dict | None,
    gate1_passed: bool,
    str_required: bool,
    is_mandatory_hard_stop: bool = False,
) -> dict:
    """Compare engine, governed, and classification dispositions.

    For each pair that differs, produce a dynamic explanation tracing
    back to the specific mechanism that produced the difference.
    """
    components = {
        "engine": engine_disposition,
        "governed": governed_disposition,
        "classification": classification_outcome,
    }
    all_same = len(set(components.values())) == 1

    if all_same:
        return {
            "consistent": True,
            "summary": "All disposition layers consistent. No override applied.",
            "differences": [],
        }

    differences: list[dict] = []

    # Engine vs Governed
    if engine_disposition != governed_disposition:
        if corrections:
            mechanism = "Governance correction"
            alert_type = integrity_alert.get("type", "") if integrity_alert else ""
            if alert_type == "CONTROL_CONTRADICTION":
                reason = "STR REQUIRED removed — 0 Tier 1 indicators; suspicion threshold not met (PCMLTFA s. 7)"
            elif alert_type == "ESCALATION_WITHOUT_SUSPICION":
                reason = "Escalation downgraded — 0 Tier 1 indicators; risk indicators alone insufficient"
            elif alert_type == "CLASSIFIER_UPGRADE":
                reason = (
                    "Reporting upgraded — sanctions screening match establishes mandatory filing obligation"
                    if is_mandatory_hard_stop
                    else "Reporting upgraded — Tier 1 suspicion indicators support preliminary RGS assessment"
                )
            elif alert_type == "CLASSIFIER_OVERRIDE":
                reason = "Rules engine overridden — classifier found insufficient suspicion basis"
            else:
                reason = "Governance correction applied per classifier sovereignty framework"
        else:
            mechanism = "Classifier sovereignty"
            reason = "Classification outcome differs from engine; governed disposition follows classifier authority"

        differences.append({
            "component_a": "Engine",
            "value_a": engine_disposition,
            "component_b": "Governed",
            "value_b": governed_disposition,
            "mechanism": mechanism,
            "reason": reason,
            "authority": "Classifier sovereignty framework — governed disposition is authoritative",
        })

    # Classification vs Governed
    if classification_outcome != governed_disposition:
        # Normalize for comparison
        _clf_norm = classification_outcome.upper().replace(" ", "_")
        _gov_norm = governed_disposition.upper().replace(" ", "_")
        if _clf_norm != _gov_norm:
            if not gate1_passed and "STR" in _clf_norm:
                reason = (
                    f"Classifier determined {classification_outcome} but Gate 1 blocked escalation — "
                    "insufficient lawful basis. Deferred to compliance officer."
                )
            elif integrity_alert and integrity_alert.get("type") == "CLASSIFICATION_DISPOSITION_CONFLICT":
                reason = (
                    f"Classifier determined {classification_outcome} but governed disposition "
                    f"is {governed_disposition}. Conflict deferred to compliance officer review."
                )
            else:
                reason = (
                    f"Classification outcome ({classification_outcome}) differs from "
                    f"governed disposition ({governed_disposition}). "
                    "Governed disposition follows gate evaluation and governance framework."
                )
            differences.append({
                "component_a": "Classification",
                "value_a": classification_outcome,
                "component_b": "Governed",
                "value_b": governed_disposition,
                "mechanism": "Gate evaluation / governance framework",
                "reason": reason,
                "authority": f"Final disposition follows governed authority per policy framework",
            })

    # Engine vs Classification — skip when Classification == Governed (already covered above)
    if engine_disposition != classification_outcome:
        _eng_norm = engine_disposition.upper().replace(" ", "_")
        _clf_norm = classification_outcome.upper().replace(" ", "_")
        _gov_norm2 = governed_disposition.upper().replace(" ", "_")
        if _eng_norm != _clf_norm and _clf_norm != _gov_norm2:
            differences.append({
                "component_a": "Engine",
                "value_a": engine_disposition,
                "component_b": "Classification",
                "value_b": classification_outcome,
                "mechanism": "Independent assessment",
                "reason": (
                    f"Engine produced {engine_disposition} from rules/gates. "
                    f"Classifier independently determined {classification_outcome} from suspicion indicators."
                ),
                "authority": "Both assessments feed into governed disposition",
            })

    return {
        "consistent": False,
        "summary": f"{len(differences)} disposition difference(s) detected between engine, classifier, and governed layers.",
        "differences": differences,
    }


# ── FIX-030: Precedent Divergence Narrative ──────────────────────────────────

def _build_precedent_divergence_narrative(
    precedent_analysis: dict,
    governed_disposition: str,
    classification_outcome: str,
    integrity_alert: dict | None,
    enhanced_precedent: dict,
) -> dict | None:
    """Build divergence narrative when precedent alignment < 50%.

    Shows pool outcome distribution and explains WHY current disposition
    diverges from historical pattern.
    """
    if not precedent_analysis or not precedent_analysis.get("available"):
        return None

    alignment_count = enhanced_precedent.get("governed_alignment_count", 0)
    alignment_total = enhanced_precedent.get("governed_alignment_total", 0)

    if alignment_total == 0:
        return None

    alignment_pct = int(alignment_count / alignment_total * 100) if alignment_total else 0

    # Get full outcome distribution
    match_distribution = (
        precedent_analysis.get("match_outcome_distribution")
        or precedent_analysis.get("outcome_distribution")
        or {}
    )
    pool_breakdown = {str(k).upper(): int(v) for k, v in match_distribution.items()}

    # Find dominant historical outcome
    dominant_outcome = ""
    dominant_count = 0
    for k, v in pool_breakdown.items():
        if v > dominant_count:
            dominant_outcome = k
            dominant_count = v

    if alignment_pct >= 50:
        return {
            "divergent": False,
            "alignment_pct": alignment_pct,
            "alignment_count": alignment_count,
            "alignment_total": alignment_total,
            "pool_breakdown": pool_breakdown,
        }

    # Alignment < 50% — build divergence reasons
    divergence_reasons: list[str] = []

    if integrity_alert:
        atype = integrity_alert.get("type", "")
        if atype == "CLASSIFIER_UPGRADE":
            divergence_reasons.append(
                "Classifier sovereignty: Tier 1 suspicion indicators triggered STR upgrade "
                "despite historical pattern favoring lower disposition."
            )
        elif atype == "CONTROL_CONTRADICTION":
            divergence_reasons.append(
                "Governance correction: STR determination removed due to 0 Tier 1 indicators, "
                "overriding historical STR pattern for this risk profile."
            )
        elif atype == "ESCALATION_WITHOUT_SUSPICION":
            divergence_reasons.append(
                "Governance correction: Escalation downgraded due to insufficient "
                "Tier 1 suspicion indicators."
            )
        elif atype == "CLASSIFICATION_DISPOSITION_CONFLICT":
            divergence_reasons.append(
                f"Classification conflict: Classifier determined {classification_outcome} "
                f"but governed disposition is {governed_disposition}. "
                "Deferred to compliance officer."
            )
        elif atype:
            divergence_reasons.append(f"Integrity alert ({atype}) may explain divergence.")

    # Check for policy regime shift
    regime = precedent_analysis.get("policy_regime_analysis", {})
    if regime and regime.get("pre_shift_count", 0) > 0:
        pre_pct = regime.get("pre_shift_pct", 0)
        if pre_pct > 30:
            divergence_reasons.append(
                f"Policy regime shift: {pre_pct}% of comparable pool was decided under "
                "prior policy. Current disposition reflects updated regulatory guidance."
            )

    # Check if case has unique risk factors not in pool
    if not divergence_reasons:
        divergence_reasons.append(
            "Current case may contain risk factor combinations not represented "
            "in the comparable precedent pool."
        )

    return {
        "divergent": True,
        "alignment_pct": alignment_pct,
        "alignment_count": alignment_count,
        "alignment_total": alignment_total,
        "dominant_historical": dominant_outcome,
        "dominant_count": dominant_count,
        "pool_breakdown": pool_breakdown,
        "divergence_reasons": divergence_reasons,
    }


# ── FIX-031: Unmapped Indicator Independence Check ───────────────────────────

def _build_unmapped_indicator_checks(
    tier1_signals: list,
    tier2_signals: list,
    governed_disposition: str,
    rules_fired: list,
    gate1_passed: bool,
    str_required: bool,
) -> list[dict]:
    """Check if any unmapped/unclassified indicator is load-bearing.

    For each unmapped indicator, determine whether MAPPED Tier 1 indicators
    independently support the outcome via hard stop or gate logic.
    Connects independence result to gate decision narrative.
    """
    def _is_unmapped(s: dict) -> bool:
        """Signal is unmapped if it has classification_gap or UNCLASSIFIED_ prefix."""
        if s.get("classification_gap"):
            return True
        code = str(s.get("code", "")).upper()
        return code.startswith("UNCLASSIFIED_")

    all_signals = list(tier1_signals or []) + list(tier2_signals or [])
    unmapped = [s for s in all_signals if _is_unmapped(s)]

    if not unmapped:
        return []

    # Mapped Tier 1 = all Tier 1 signals that are NOT unmapped
    mapped_tier1 = [s for s in (tier1_signals or []) if not _is_unmapped(s)]

    # Check for hard-stop rules that independently support the outcome
    hard_stop_triggered = any(
        str(r.get("code", "")).upper().startswith(("AML_BLOCK", "SANCTIONS", "HARD_STOP"))
        and str(r.get("result", "")).upper() in {"TRIGGERED", "ACTIVATED", "FAIL", "FAILED"}
        for r in rules_fired
    )

    results: list[dict] = []
    for signal in unmapped:
        code = signal.get("code", "UNKNOWN")
        source = signal.get("source", "")

        # Independence check: can we reach the same outcome without this indicator?
        if hard_stop_triggered:
            independent = True
            basis = "Hard stop rule independently triggers this disposition"
        elif len(mapped_tier1) >= 1 and str_required:
            independent = True
            basis = f"{len(mapped_tier1)} mapped Tier 1 indicator(s) independently meet STR threshold"
        elif len(mapped_tier1) >= 1 and governed_disposition in ("EDD_REQUIRED", "ESCALATE"):
            independent = True
            basis = f"{len(mapped_tier1)} mapped Tier 1 indicator(s) independently support escalation"
        elif governed_disposition == "NO_REPORT":
            independent = True
            basis = "Disposition is NO_REPORT — unmapped indicator does not affect clearance"
        else:
            independent = False
            basis = "No mapped Tier 1 indicators independently support this disposition"

        # Gate narrative connection
        if independent and not gate1_passed:
            gate_narrative = (
                "Gate 1 blocked automatic escalation. Independence confirmed — "
                "this unmapped indicator is not load-bearing for the gate decision."
            )
        elif independent and gate1_passed:
            gate_narrative = (
                "Gate 1 passed. Mapped indicators independently support "
                "the disposition without reliance on this unmapped signal."
            )
        elif not independent and not gate1_passed:
            gate_narrative = (
                "Gate 1 blocked escalation, but disposition may depend on "
                "this unmapped indicator. Manual classification required "
                "before final determination."
            )
        else:
            gate_narrative = (
                "Disposition may depend on this unmapped indicator. "
                "Compliance officer must reclassify before filing."
            )

        results.append({
            "indicator_code": code,
            "indicator_source": source,
            "independent": independent,
            "basis": basis,
            "gate_narrative": gate_narrative,
            "mapped_tier1_count": len(mapped_tier1),
            "hard_stop_active": hard_stop_triggered,
        })

    return results


# ── FIX-032: Policy Regime Exception ─────────────────────────────────────────

def _build_policy_regime_exception(
    precedent_analysis: dict,
    governed_disposition: str,
    integrity_alert: dict | None,
    classification_outcome: str,
) -> dict | None:
    """Check if current disposition departs from post-shift pool pattern."""
    if not precedent_analysis or not precedent_analysis.get("available"):
        return None

    regime = precedent_analysis.get("policy_regime_analysis", {})
    if not regime:
        return None

    post_shift_dist = regime.get("post_shift_distribution", {})
    if not post_shift_dist:
        return None

    # Find dominant post-shift outcome
    total_post = sum(post_shift_dist.values())
    if total_post == 0:
        return None

    dominant_key = max(post_shift_dist, key=post_shift_dist.get)
    dominant_count = post_shift_dist[dominant_key]
    dominant_pct = int(dominant_count / total_post * 100)
    dominant_label = str(dominant_key).upper().replace("_", " ")

    # Normalize for comparison
    _gov_canon = governed_disposition.upper().replace(" ", "_")
    _dom_canon = str(dominant_key).upper().replace(" ", "_")

    # Check aliases
    _GOV_ALIASES = {
        "NO_REPORT": {"NO_REPORT", "ALLOW", "CLEARED", "PASS"},
        "STR_REQUIRED": {"STR_REQUIRED", "FILE_STR", "BLOCK"},
        "EDD_REQUIRED": {"EDD_REQUIRED", "EDD", "REVIEW", "ESCALATE"},
    }
    gov_set = _GOV_ALIASES.get(_gov_canon, {_gov_canon})
    matches = _dom_canon in gov_set

    if matches:
        return {
            "exception": False,
            "summary": "Disposition consistent with post-shift institutional pattern.",
            "post_shift_dominant": dominant_label,
            "post_shift_dominant_pct": dominant_pct,
            "post_shift_total": total_post,
        }

    # Exception: disposition differs from post-shift pattern
    exception_basis = []
    if integrity_alert:
        atype = integrity_alert.get("type", "")
        if atype:
            exception_basis.append(f"Integrity alert ({atype}) applied — disposition adjusted from historical pattern.")
    if classification_outcome:
        exception_basis.append(f"Classifier determined {classification_outcome}.")
    if not exception_basis:
        exception_basis.append("Unique risk combination in current case not represented in post-shift pool.")

    return {
        "exception": True,
        "summary": (
            f"Post-shift institutional pattern: {dominant_pct}% of {total_post} cases "
            f"resolved as {dominant_label}. Current disposition ({governed_disposition.replace('_', ' ')}) "
            "departs from pattern."
        ),
        "post_shift_dominant": dominant_label,
        "post_shift_dominant_pct": dominant_pct,
        "post_shift_total": total_post,
        "exception_basis": exception_basis,
    }


# ── FIX-033: Risk Heatmap Context ────────────────────────────────────────────

_DISPOSITION_SEVERITY_MAP = {
    "STR_REQUIRED": "High", "BLOCK": "High", "FILE_STR": "High",
    "EDD_REQUIRED": "Medium", "ESCALATE": "Medium",
    "NO_REPORT": "Low", "CLEARED": "Low", "ALLOW": "Low",
}

_SEVERITY_RANK = {"High": 3, "Medium": 2, "Low": 1}


def _build_risk_heatmap_context(
    risk_factors: list,
    governed_disposition: str,
    integrity_alert: dict | None,
) -> dict | None:
    """Check if risk factor severity matches disposition severity."""
    expected_severity = _DISPOSITION_SEVERITY_MAP.get(governed_disposition, "Medium")

    # Estimate heatmap severity from risk factors
    high_risk_count = 0
    for rf in risk_factors:
        val = rf.get("value", "")
        field = rf.get("field", "")
        if any(kw in str(val).lower() for kw in ("present", "true", "yes", "high", "sanctions", "pep")):
            high_risk_count += 1
        if any(kw in str(field).lower() for kw in ("sanctions", "pep", "adverse", "layering", "structuring")):
            high_risk_count += 1

    if high_risk_count >= 3:
        heatmap_severity = "High"
    elif high_risk_count >= 1:
        heatmap_severity = "Medium"
    else:
        heatmap_severity = "Low"

    if _SEVERITY_RANK.get(heatmap_severity, 0) >= _SEVERITY_RANK.get(expected_severity, 0):
        return None  # Consistent — no note needed

    # Heatmap severity < expected — explain elevation
    mechanism = "classifier sovereignty"
    if integrity_alert:
        atype = integrity_alert.get("type", "")
        if "UPGRADE" in atype:
            mechanism = "classifier upgrade"
        elif "CORRECTION" in atype or "CONTRADICTION" in atype:
            mechanism = "governance correction"
        elif atype:
            mechanism = f"integrity correction ({atype})"

    return {
        "elevated": True,
        "heatmap_severity": heatmap_severity,
        "disposition_severity": expected_severity,
        "mechanism": mechanism,
        "note": (
            f"Pre-classification risk assessment rated {heatmap_severity}. "
            f"Final disposition elevated to {expected_severity} by {mechanism}."
        ),
    }


# ── FIX-034: Required Actions (dynamic, per disposition) ────────────────────

def _build_required_actions(
    governed_disposition: str,
    str_required: bool,
    sla_timeline: dict,
    edd_recommendations: list,
    risk_factors: list,
    evidence_used: list,
    classification,
) -> list[dict]:
    """Generate dynamic action items based on disposition + case data."""
    actions: list[dict] = []
    ev_map = {str(ev.get("field", "")).lower(): ev.get("value") for ev in (evidence_used or [])}

    pep_flag = (
        ev_map.get("customer.pep") or ev_map.get("flag.pep") or ev_map.get("customer.pep_flag")
    )
    is_pep = pep_flag is True or str(pep_flag).lower() == "true"
    prior_sars = ev_map.get("prior.sars_filed") or ev_map.get("screen.prior_sars_filed") or 0
    try:
        prior_sars = int(prior_sars)
    except (ValueError, TypeError):
        prior_sars = 0

    if str_required or governed_disposition == "STR_REQUIRED":
        str_window = sla_timeline.get("str_filing_window", "30 days per PCMLTFA s. 7")
        actions.append({"action": f"File STR by {str_window}", "priority": "MANDATORY"})
        actions.append({
            "action": "Transaction hold: ASSESS — determine if block required based on risk level",
            "priority": "REQUIRED",
        })
        # EDD completeness
        gaps = [r.get("action", "") for r in edd_recommendations if "gap" in r.get("action", "").lower()]
        if gaps:
            actions.append({"action": f"EDD status: INCOMPLETE — resolve: {'; '.join(gaps[:2])}", "priority": "REQUIRED"})
        else:
            actions.append({"action": "EDD status: COMPLETE if all evidence present", "priority": "REQUIRED"})
        if is_pep:
            actions.append({"action": "Account restriction: RECOMMENDED — PEP + STR disposition", "priority": "RECOMMENDED"})
        if is_pep or prior_sars > 0:
            actions.append({"action": "Related party review: REQUIRED", "priority": "REQUIRED"})
        else:
            actions.append({"action": "Related party review: RECOMMENDED", "priority": "RECOMMENDED"})

    elif governed_disposition in ("EDD_REQUIRED", "ESCALATE"):
        edd_deadline = sla_timeline.get("edd_deadline", "5 business days")
        actions.append({"action": f"Complete EDD by {edd_deadline}", "priority": "REQUIRED"})
        for rec in edd_recommendations[:3]:
            actions.append({"action": rec.get("action", ""), "priority": "REQUIRED"})
        if is_pep and len(risk_factors) >= 2:
            actions.append({"action": "Senior management approval: REQUIRED (PEP + elevated risk)", "priority": "REQUIRED"})
        actions.append({"action": "Re-evaluation trigger: upon EDD completion", "priority": "STANDARD"})

    elif governed_disposition == "NO_REPORT":
        actions.append({"action": "Document rationale for no-action determination", "priority": "REQUIRED"})
        if len(risk_factors) >= 2:
            actions.append({"action": "Next scheduled review: 6 months (elevated risk factors present)", "priority": "STANDARD"})
        else:
            actions.append({"action": "Next scheduled review: 12 months (standard cycle)", "priority": "STANDARD"})
        actions.append({"action": "File retention: per PCMLTFA s. 6", "priority": "STANDARD"})

    else:
        actions.append({"action": f"Review disposition ({governed_disposition}) and determine next steps", "priority": "REQUIRED"})

    return actions


# ── FIX-035: Related Activity ────────────────────────────────────────────────

def _build_related_activity(evidence_used: list) -> dict:
    """Extract related activity indicators from evidence fields."""
    ev_map = {str(ev.get("field", "")).lower(): ev.get("value") for ev in (evidence_used or [])}

    prior_sars = ev_map.get("prior.sars_filed") or ev_map.get("screen.prior_sars_filed") or 0
    try:
        prior_sars = int(prior_sars)
    except (ValueError, TypeError):
        prior_sars = 0

    account_closures = ev_map.get("prior.account_closures") or ev_map.get("screen.previous_account_closures") or False
    if isinstance(account_closures, str):
        account_closures = account_closures.lower() in ("true", "yes", "1")

    pep = ev_map.get("customer.pep") or ev_map.get("flag.pep") or ev_map.get("customer.pep_flag") or False
    if isinstance(pep, str):
        pep = pep.lower() in ("true", "yes", "1")

    sanctions = ev_map.get("screening.sanctions_match") or ev_map.get("flag.sanctions_proximity") or False
    if isinstance(sanctions, str):
        sanctions = sanctions.lower() in ("true", "yes", "1")

    pep_match = ev_map.get("screening.pep_match") or False
    if isinstance(pep_match, str):
        pep_match = pep_match.lower() in ("true", "yes", "1")

    adverse = ev_map.get("screening.adverse_media") or ev_map.get("flag.adverse_media") or False
    if isinstance(adverse, str):
        adverse = adverse.lower() in ("true", "yes", "1")

    flags: list[str] = []
    if prior_sars > 0:
        flags.append(f"Prior STR history ({prior_sars} filed) — review previous filings for pattern consistency")
    if account_closures:
        flags.append("Prior account closure on record — assess re-entry risk")

    return {
        "prior_sars_filed": prior_sars,
        "prior_account_closures": account_closures,
        "pep_status": pep,
        "screening": {
            "sanctions_match": sanctions,
            "pep_match": pep_match,
            "adverse_media": adverse,
        },
        "flags": flags,
        "connected_accounts": "Not assessed — requires manual review",
    }
