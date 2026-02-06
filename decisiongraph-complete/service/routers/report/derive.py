"""Derive — Stage B of the Report Compiler Pipeline.

Deterministic domain logic applied on top of a NormalizedDecision.
Produces a DerivedRegulatoryModel with:
  - classification result
  - resolved typology
  - regulatory status + investigation state
  - decision drivers
  - confidence score
  - integrity & deviation alerts
  - governance corrections (explicit, never silent)

This layer may produce "recommended corrections" but never silently
mutates the original decision; corrections are first-class objects.
"""

import re
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
    )

    # Apply corrections (explicit — not hidden)
    if corrections:
        regulatory_status = corrections.get("regulatory_status", regulatory_status)
        str_required = corrections.get("str_required", str_required)
        decision_status = corrections.get("decision_status", decision_status)
        investigation_state = corrections.get("investigation_state", investigation_state)

    # Governed disposition is computed AFTER corrections are applied.
    governed_disposition = _disposition_label(decision_status, str_required)

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
    )

    # ── 10. Similarity summary ────────────────────────────────────────────
    similarity_summary = _derive_similarity_summary(precedent_analysis)

    # ── 11. Escalation summary ────────────────────────────────────────────
    escalation_summary = _build_escalation_summary(decision_status, str_required)

    # ── 12. Regulatory position ───────────────────────────────────────────
    if str_required:
        regulatory_position = "Reporting threshold met under applicable regulatory guidance."
    else:
        regulatory_position = "Suspicion threshold not met based on available indicators."

    return {
        # Classification
        "classification": classification.to_dict(),
        "classification_outcome": classification.outcome,
        "classification_reason": classification.outcome_reason,
        "tier1_signals": classification.tier1_signals,
        "tier2_signals": classification.tier2_signals,
        "suspicion_count": classification.suspicion_count,
        "investigative_count": classification.investigative_count,
        "precedent_consistency_alert": classification.precedent_consistency_alert,
        "precedent_consistency_detail": classification.precedent_consistency_detail,
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

        # Confidence
        "decision_confidence": conf_label,
        "decision_confidence_reason": conf_reason,
        "decision_confidence_score": conf_score,

        # Drivers
        "decision_drivers": decision_drivers,

        # Engine vs Governed dispositions (for audit transparency)
        "engine_disposition": engine_disposition,
        "governed_disposition": governed_disposition,

        # Alerts (first-class objects)
        "decision_integrity_alert": integrity_alert,
        "precedent_deviation_alert": deviation_alert,
        "corrections_applied": corrections or {},

        # Risk & similarity
        "risk_factors": risk_factors,
        "similarity_summary": similarity_summary,
    }


# ── Decision status / explainer ──────────────────────────────────────────────

def _resolve_decision_status(
    verdict: str, str_required: bool, rationale_summary: str,
) -> tuple[str, str]:
    """Map verdict to one of: pass | escalate | review + explainer text."""
    v = verdict.upper()
    if v in ("PASS", "PASS_WITH_EDD") or v.startswith("APPROVE"):
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
        try:
            conf = float(precedent_analysis.get("precedent_confidence", 0) or 0)
        except (TypeError, ValueError):
            conf = 0.0
        if conf >= 0.75:
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

    if score >= 90:
        return "High", "Deterministic rule activation with corroborating precedent alignment.", score
    if score >= 70:
        return "Moderate", "Deterministic rule activation with moderate precedent alignment.", score
    return "Elevated Review Recommended", "Evidence completeness or precedent alignment below standard threshold.", score


# ── Integrity alerts ─────────────────────────────────────────────────────────

def _detect_integrity_issues(
    classifier_override: dict,
    classification,
    str_required: bool,
    decision_status: str,
    verdict: str,
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

    return None, None


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


def _detect_precedent_deviation(
    precedent_analysis: dict,
    governed_disposition: str,
    engine_disposition: str,
) -> Optional[dict]:
    """Detect deviation between governed outcome and precedent distribution.

    RULE: The deviation signal always evaluates the *governed* disposition
    (the official regulatory position after classifier sovereignty).
    If engine disposition differs from governed, that is noted separately.
    """
    if not precedent_analysis or not precedent_analysis.get("available"):
        return None

    supporting = int(precedent_analysis.get("supporting_precedents", 0) or 0)
    contrary = int(precedent_analysis.get("contrary_precedents", 0) or 0)
    total = supporting + contrary

    if total < 3:
        return None  # too few scored matches to signal deviation

    is_escalation = governed_disposition in ("STR_REQUIRED", "ESCALATE")

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

    if not is_escalation and supporting > contrary:
        alert = {
            "type": "UNDER_ESCALATION_RISK",
            "severity": "INFO",
            "message": (
                f"Deviation vs GOVERNED outcome ({governed_disposition}): "
                f"{supporting} of {total} scored comparable cases "
                "resulted in escalation, but governed outcome is non-escalation. "
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
    lowered = text.lower()
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

    # ── CASE A: STR required ─────────────────────────────────────────────
    if str_required:
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

    if not gate1_passed:
        drivers.append("Escalation blocked by Gate 1 legal basis")

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
