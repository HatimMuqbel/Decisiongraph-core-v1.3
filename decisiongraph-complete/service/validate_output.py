"""Output Validation Layer — Self-Validating Pipeline.

Runs AFTER every decision is generated, BEFORE it is cached/returned.
Any input — demo case, seed, JSON, API call — goes through this same
validation. No special cases, no demo mode.

Called from main.py after check_precedent_invariants().
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("decisiongraph.validate")

# ── Imports from engine layer (no circular dep risk) ───────────────────────
from decisiongraph.banking_field_registry import BANKING_FIELDS
from decisiongraph.aml_seed_generator import SCENARIOS

# ── Constants ──────────────────────────────────────────────────────────────

CRITICAL_EVIDENCE_FIELDS = frozenset({"txn.type", "txn.amount_band", "customer.type"})
TOTAL_REGISTRY_FIELDS = len(BANKING_FIELDS)  # 27

# Seed scenario expected outcomes (name → {disposition, disposition_basis, reporting})
_SCENARIO_EXPECTED: dict[str, dict] = {
    s["name"]: s["outcome"] for s in SCENARIOS
}

# Engine verdict → seed disposition vocabulary
_VERDICT_TO_DISPOSITION = {
    "PASS": "ALLOW",
    "PASS_WITH_EDD": "EDD",
    "ESCALATE": "EDD",
    "STR": "BLOCK",
    "HARD_STOP": "BLOCK",
    "BLOCK": "BLOCK",
    "REVIEW": "EDD",
    "EDD": "EDD",
    "ALLOW": "ALLOW",
}

# Known truncation fragments observed in pipeline output
_TRUNCATION_MARKERS = [
    "detecte", "pendin", "determina", "indicat", "transacti",
    "investiga", "escala", "complia", "regulato", "identif",
    "classif", "reportin", "suspicio",
]


# ── Main entry point ──────────────────────────────────────────────────────

def validate_decision_output(decision_pack: dict) -> dict:
    """Validate a completed decision_pack for internal consistency.

    Mutates decision_pack in-place:
      - May regenerate ``rationale.summary`` if inconsistent
      - May attach ``precedent_analysis._confidence_cap``
      - Attaches ``_validation`` dict (action pre-constraints)
      - Attaches ``_output_validation`` (full validation results)

    Returns the (possibly mutated) decision_pack.
    """
    warnings: list[dict] = []

    warnings.extend(_check_summary_signals(decision_pack))
    warnings.extend(_check_confidence_evidence(decision_pack))
    warnings.extend(_check_precedent_quality(decision_pack))
    warnings.extend(_check_disposition_labels(decision_pack))
    warnings.extend(_check_narrative_consistency(decision_pack))
    warnings.extend(_check_action_constraints(decision_pack))
    warnings.extend(_check_seed_expected(decision_pack))

    result = {
        "validated": True,
        "check_count": 7,
        "warning_count": len(warnings),
        "error_count": sum(1 for w in warnings if w.get("severity") == "ERROR"),
        "auto_corrections": [w for w in warnings if w.get("auto_corrected")],
        "warnings": warnings,
    }
    decision_pack["_output_validation"] = result

    decision_id = decision_pack.get("meta", {}).get("decision_id", "unknown")
    if result["error_count"]:
        logger.error(
            "Output validation: %d error(s), %d warning(s)",
            result["error_count"],
            result["warning_count"],
            extra={"decision_id": decision_id},
        )
    elif result["warning_count"]:
        logger.info(
            "Output validation: %d warning(s), %d auto-correction(s)",
            result["warning_count"],
            len(result["auto_corrections"]),
            extra={"decision_id": decision_id},
        )

    return decision_pack


# ── Helpers ────────────────────────────────────────────────────────────────

def _extract_prior_sars(evidence_used: list[dict]) -> int:
    """Extract prior.sars_filed count from evidence list."""
    for ev in evidence_used:
        field = str(ev.get("field", ""))
        if field == "prior.sars_filed":
            val = ev.get("value", 0)
            if isinstance(val, (int, float)):
                return int(val)
    return 0


def _regenerate_summary(pack: dict) -> str:
    """Build a fact-grounded summary from actual decision fields.

    Replaces canned templates that may contradict classifier signals.
    """
    verdict = pack.get("decision", {}).get("verdict", "UNKNOWN").upper()
    classifier = pack.get("classifier", {}) or {}
    evidence_used = pack.get("evaluation_trace", {}).get("evidence_used", []) or []
    layer4 = pack.get("layers", {}).get("layer4_typologies", {}) or {}
    path = pack.get("decision", {}).get("path") or ""
    str_required_raw = pack.get("decision", {}).get("str_required", "NO")
    str_required = str_required_raw in (True, "YES", "yes", "Y")

    suspicion_count = int(classifier.get("suspicion_count", 0) or
                          classifier.get("tier_1_count", 0) or 0)
    investigative_count = int(classifier.get("investigative_count", 0) or
                              classifier.get("tier_2_count", 0) or 0)
    prior_sars = _extract_prior_sars(evidence_used)
    highest_maturity = (layer4.get("highest_maturity") or "none").lower()

    parts: list[str] = []

    # Opening statement based on verdict
    if verdict in ("STR",) or str_required:
        parts.append(f"STR filing required. Escalation via {path}." if path
                     else "STR filing required.")
    elif verdict == "HARD_STOP":
        parts.append("Hard stop triggered. Immediate escalation required.")
    elif verdict == "BLOCK":
        parts.append("Transaction blocked. Mandatory escalation.")
    elif verdict == "ESCALATE":
        parts.append(f"Escalation permitted via {path}. Review recommended." if path
                     else "Escalation permitted. Review recommended.")
    elif verdict == "PASS_WITH_EDD":
        parts.append("Enhanced Due Diligence required before final disposition.")
    elif verdict == "PASS":
        if suspicion_count > 0:
            parts.append("Case requires review despite initial clearance indicators.")
        else:
            parts.append("No escalation required based on available indicators.")
    else:
        parts.append(f"Verdict: {verdict}. Review recommended.")

    # Signal-grounded additions
    if suspicion_count > 0:
        parts.append(
            f"{suspicion_count} Tier 1 suspicion indicator(s) identified."
        )
    elif investigative_count > 0:
        parts.append(
            f"{investigative_count} Tier 2 investigative signal(s) identified."
        )

    if prior_sars > 0:
        parts.append(f"Customer has {prior_sars} prior SAR(s) on record.")

    if highest_maturity not in ("none", ""):
        parts.append(f"Typology indicators present (maturity: {highest_maturity}).")

    return " ".join(parts)


# ── Check 1: Summary-Signal Consistency ────────────────────────────────────

def _check_summary_signals(pack: dict) -> list[dict]:
    warnings: list[dict] = []
    summary = (pack.get("rationale", {}).get("summary") or "").lower()
    classifier = pack.get("classifier", {}) or {}
    evidence_used = pack.get("evaluation_trace", {}).get("evidence_used", []) or []
    verdict = pack.get("decision", {}).get("verdict", "UNKNOWN").upper()
    layer4 = pack.get("layers", {}).get("layer4_typologies", {}) or {}

    suspicion_count = int(classifier.get("suspicion_count", 0) or
                          classifier.get("tier_1_count", 0) or 0)
    prior_sars = _extract_prior_sars(evidence_used)
    highest_maturity = (layer4.get("highest_maturity") or "none").lower()

    needs_regen = False

    # 1a: suspicion signals but summary says "no suspicious"
    if suspicion_count > 0 and "no suspicious" in summary:
        warnings.append({
            "check": "SUMMARY_CONTRADICTS_SUSPICION",
            "severity": "ERROR",
            "message": (
                f"Summary says 'no suspicious activity' but classifier found "
                f"{suspicion_count} Tier 1 indicator(s)"
            ),
            "auto_corrected": True,
        })
        needs_regen = True

    # 1b: prior SARs exist but summary doesn't mention
    if prior_sars > 0:
        if "prior" not in summary and "sar" not in summary and "history" not in summary:
            warnings.append({
                "check": "SUMMARY_MISSING_PRIOR_HISTORY",
                "severity": "WARNING",
                "message": (
                    f"Evidence shows {prior_sars} prior SAR(s) but summary "
                    f"does not reference prior filing history"
                ),
                "auto_corrected": True,
            })
            needs_regen = True

    # 1c: typology maturity present but summary doesn't mention
    if highest_maturity not in ("none", ""):
        typology_terms = ("typolog", "structur", "layer", "launder", "evasion")
        if not any(t in summary for t in typology_terms):
            warnings.append({
                "check": "SUMMARY_MISSING_TYPOLOGY",
                "severity": "WARNING",
                "message": (
                    f"Typology maturity is '{highest_maturity}' but summary "
                    f"does not reference typology indicators"
                ),
                "auto_corrected": True,
            })
            needs_regen = True

    # 1d: verdict is not PASS but summary says "may proceed" or "no escalation"
    if verdict not in ("PASS",):
        if "may proceed" in summary or "no escalation required" in summary:
            warnings.append({
                "check": "SUMMARY_VERDICT_CONFLICT",
                "severity": "ERROR",
                "message": (
                    f"Summary says 'no escalation required' but verdict is {verdict}"
                ),
                "auto_corrected": True,
            })
            needs_regen = True

    if needs_regen:
        pack["rationale"]["summary"] = _regenerate_summary(pack)

    return warnings


# ── Check 2: Confidence-Evidence Consistency ───────────────────────────────

def _check_confidence_evidence(pack: dict) -> list[dict]:
    warnings: list[dict] = []
    evidence_used = pack.get("evaluation_trace", {}).get("evidence_used", []) or []
    precedent_analysis = pack.get("precedent_analysis", {}) or {}

    # Build set of registry fields present with meaningful values
    populated_fields: set[str] = set()
    for ev in evidence_used:
        field = str(ev.get("field", ""))
        value = ev.get("value")
        # Count field as populated if it's a registry field with a real value
        if field in BANKING_FIELDS and value is not None:
            populated_fields.add(field)

    present_count = len(populated_fields)
    completeness_pct = (
        int(present_count / TOTAL_REGISTRY_FIELDS * 100)
        if TOTAL_REGISTRY_FIELDS > 0 else 100
    )

    # Critical fields check
    missing_critical = CRITICAL_EVIDENCE_FIELDS - populated_fields

    cap_reasons: list[str] = []
    if completeness_pct < 80:
        cap_reasons.append(
            f"evidence completeness {completeness_pct}% ({present_count}/{TOTAL_REGISTRY_FIELDS})"
        )
    if missing_critical:
        cap_reasons.append(
            f"missing critical fields: {', '.join(sorted(missing_critical))}"
        )

    if cap_reasons:
        warnings.append({
            "check": "CONFIDENCE_EVIDENCE_GAP",
            "severity": "WARNING",
            "message": f"Confidence capped at Low — {'; '.join(cap_reasons)}",
            "evidence_completeness_pct": completeness_pct,
            "missing_critical": sorted(missing_critical),
        })
        # Attach cap for derive.py to read via normalize.py
        precedent_analysis["_confidence_cap"] = "Low"
        precedent_analysis["_confidence_cap_reason"] = (
            f"Output validation: {'; '.join(cap_reasons)}"
        )

    return warnings


# ── Check 3: Precedent Quality Gate ────────────────────────────────────────

def _check_precedent_quality(pack: dict) -> list[dict]:
    warnings: list[dict] = []
    pa = pack.get("precedent_analysis", {}) or {}

    if not pa.get("available"):
        return warnings

    sample_cases = pa.get("sample_cases", []) or []
    supporting = int(pa.get("supporting_precedents", 0) or 0)
    contrary = int(pa.get("contrary_precedents", 0) or 0)
    neutral = int(pa.get("neutral_precedents", 0) or 0)
    total_scored = supporting + contrary + neutral
    confidence = float(pa.get("precedent_confidence", 0) or 0)

    # Compute max and avg similarity
    max_sim = 0.0
    total_sim = 0.0
    for sc in sample_cases:
        sim = float(
            sc.get("fingerprint_similarity_pct", 0) or
            sc.get("similarity", 0) or
            sc.get("combined_score", 0) or 0
        )
        # Normalize: if it's a percentage (0-100), convert to 0-1
        if sim > 1.0:
            sim = sim / 100.0
        max_sim = max(max_sim, sim)
        total_sim += sim
    avg_sim = (total_sim / len(sample_cases)) if sample_cases else 0.0

    # 3a: No strongly comparable cases
    if sample_cases and max_sim < 0.50:
        warnings.append({
            "check": "PRECEDENT_NO_STRONG_MATCH",
            "severity": "WARNING",
            "message": (
                f"No strongly comparable cases found — max similarity "
                f"{max_sim:.0%}. Confidence metrics unreliable."
            ),
            "max_similarity": round(max_sim, 3),
        })

    # 3b: Pool below minimum threshold
    if 0 < total_scored < 5:
        warnings.append({
            "check": "PRECEDENT_THIN_POOL",
            "severity": "WARNING",
            "message": (
                f"Precedent pool below minimum threshold "
                f"(n={total_scored}, required >= 5)"
            ),
            "pool_size": total_scored,
        })

    # 3c: Perfect confidence but poor similarity
    if confidence >= 1.0 and sample_cases and avg_sim < 0.50:
        warnings.append({
            "check": "PRECEDENT_UNRELIABLE_CONFIDENCE",
            "severity": "WARNING",
            "message": (
                f"precedent_confidence={confidence:.2f} but avg similarity "
                f"is {avg_sim:.0%} — metric unreliable"
            ),
            "avg_similarity": round(avg_sim, 3),
        })

    # 3d: Confidence is fallback when no decisive precedents
    decisive_total = int(pa.get("decisive_total", -1))
    if decisive_total == 0 and confidence == 0.5:
        warnings.append({
            "check": "PRECEDENT_NO_DECISIVE",
            "severity": "INFO",
            "message": (
                f"All precedents are non-terminal (EDD/review). "
                f"Confidence 0.50 is a neutral fallback, not a calculated value. "
                f"Terminal outcomes (ALLOW/BLOCK) required for meaningful confidence."
            ),
            "decisive_total": 0,
        })

    return warnings


# ── Check 4: Disposition-Label Consistency ─────────────────────────────────

def _check_disposition_labels(pack: dict) -> list[dict]:
    warnings: list[dict] = []
    verdict = pack.get("decision", {}).get("verdict", "UNKNOWN").upper()
    classifier = pack.get("classifier", {}) or {}
    compliance = pack.get("compliance", {}) or {}
    str_required_raw = pack.get("decision", {}).get("str_required", False)
    str_required = str_required_raw in (True, "YES", "yes", "Y")

    # 4a: Classifier override applied but verdict still PASS
    if classifier.get("override_applied") and verdict == "PASS":
        warnings.append({
            "check": "DISPOSITION_OVERRIDE_PASS",
            "severity": "ERROR",
            "message": (
                "Classifier override applied but verdict remains PASS — "
                "integrity conflict expected"
            ),
        })

    # 4b: Suspicion signals present but verdict is PASS (not overridden)
    suspicion_count = int(classifier.get("suspicion_count", 0) or
                          classifier.get("tier_1_count", 0) or 0)
    if suspicion_count > 0 and verdict == "PASS" and not classifier.get("override_applied"):
        warnings.append({
            "check": "DISPOSITION_SUSPICION_PASS",
            "severity": "WARNING",
            "message": (
                f"{suspicion_count} Tier 1 signal(s) present but verdict "
                f"is PASS — classifier sovereignty should trigger review"
            ),
        })

    # 4c: EDD required but no filing deadline populated
    edd_required = compliance.get("edd_required", False)
    if edd_required and not compliance.get("str_filing_deadline_days"):
        warnings.append({
            "check": "EDD_NO_DEADLINE",
            "severity": "INFO",
            "message": (
                "EDD required but no deadline in compliance block — "
                "derive layer will populate SLA timeline"
            ),
        })

    return warnings


# ── Check 5: Narrative Consistency ─────────────────────────────────────────

def _check_narrative_consistency(pack: dict) -> list[dict]:
    warnings: list[dict] = []
    rationale = pack.get("rationale", {}) or {}
    verdict = pack.get("decision", {}).get("verdict", "UNKNOWN").upper()

    fields_to_scan = {
        "summary": rationale.get("summary") or "",
        "non_escalation_justification": rationale.get("non_escalation_justification") or "",
        "str_rationale": rationale.get("str_rationale") or "",
    }

    for field_name, text in fields_to_scan.items():
        if not text:
            continue
        text_stripped = text.rstrip()

        # 5a: Check for truncation at end of string
        for marker in _TRUNCATION_MARKERS:
            if text_stripped.lower().endswith(marker):
                warnings.append({
                    "check": "NARRATIVE_TRUNCATED",
                    "severity": "ERROR",
                    "field": field_name,
                    "message": (
                        f"Field '{field_name}' appears truncated "
                        f"(ends with '{marker}')"
                    ),
                    "auto_corrected": True,
                })
                # Auto-correct: regenerate summary; for other fields, append ellipsis
                if field_name == "summary":
                    pack["rationale"]["summary"] = _regenerate_summary(pack)
                else:
                    pack["rationale"][field_name] = text_stripped + "ed."
                break

    # 5b: Summary says "cannot be cleared" but verdict is PASS
    summary_lower = (rationale.get("summary") or "").lower()
    if "cannot be cleared" in summary_lower and verdict == "PASS":
        warnings.append({
            "check": "NARRATIVE_VERDICT_CONFLICT",
            "severity": "ERROR",
            "message": "Summary says 'cannot be cleared' but verdict is PASS",
            "auto_corrected": True,
        })
        pack["rationale"]["summary"] = _regenerate_summary(pack)

    return warnings


# ── Check 6: Action Constraints ────────────────────────────────────────────

def _check_action_constraints(pack: dict) -> list[dict]:
    warnings: list[dict] = []
    classifier = pack.get("classifier", {}) or {}
    verdict = pack.get("decision", {}).get("verdict", "UNKNOWN").upper()
    str_required_raw = pack.get("decision", {}).get("str_required", False)
    str_required = str_required_raw in (True, "YES", "yes", "Y")

    suspicion_count = int(classifier.get("suspicion_count", 0) or
                          classifier.get("tier_1_count", 0) or 0)
    classifier_outcome = str(classifier.get("outcome", "")).upper()

    validation: dict[str, Any] = {}

    # 6a: Classifier override active → block approve buttons
    if classifier.get("override_applied"):
        validation["block_approve"] = True
        validation["block_approve_reason"] = (
            "Classifier override active — approval blocked pending review"
        )

    # 6b: Hard stop → only acknowledge permitted
    if verdict == "HARD_STOP":
        validation["hard_stop"] = True
        validation["hard_stop_reason"] = (
            "Hard stop verdict — only acknowledge and information request permitted"
        )

    # 6c: Tier 1 suspicion + STR outcome but verdict not escalated
    if (
        suspicion_count > 0
        and classifier_outcome == "STR_REQUIRED"
        and not str_required
        and verdict in ("PASS", "PASS_WITH_EDD", "REVIEW")
    ):
        validation["require_escalation"] = True
        validation["require_escalation_reason"] = (
            f"Tier 1 suspicion detected ({suspicion_count} signals) but "
            f"disposition not escalated — primary action must be escalation"
        )

    if validation:
        pack["_validation"] = validation
        constraint_keys = ", ".join(sorted(validation.keys()))
        warnings.append({
            "check": "ACTION_CONSTRAINTS_SET",
            "severity": "INFO",
            "message": f"Action pre-validation constraints set: {constraint_keys}",
            "constraints": list(validation.keys()),
        })

    return warnings


# ── Check 7: Seed-Expected Outcome ─────────────────────────────────────────

def _check_seed_expected(pack: dict) -> list[dict]:
    warnings: list[dict] = []
    meta = pack.get("meta", {}) or {}
    source_type = str(meta.get("source_type", "")).lower()
    scenario_code = meta.get("scenario_code")

    # Only applies to seed inputs
    if source_type not in ("seed", "seeded") or not scenario_code:
        return warnings

    # Normalize scenario code
    normalized_code = (
        str(scenario_code).lower().strip().replace("-", "_").replace(" ", "_")
    )
    expected = _SCENARIO_EXPECTED.get(normalized_code)

    if not expected:
        # Unknown scenario — could be a custom seed, not necessarily a problem
        return warnings

    # Map engine verdict to seed disposition vocabulary
    verdict = pack.get("decision", {}).get("verdict", "UNKNOWN").upper()
    engine_disposition = _VERDICT_TO_DISPOSITION.get(verdict, "EDD")
    expected_disposition = expected.get("disposition", "")

    if engine_disposition != expected_disposition:
        warnings.append({
            "check": "SEED_OUTCOME_MISMATCH",
            "severity": "WARNING",
            "message": (
                f"Seed scenario '{normalized_code}' expected disposition "
                f"'{expected_disposition}' but engine produced '{verdict}' "
                f"(mapped to '{engine_disposition}')"
            ),
            "expected_disposition": expected_disposition,
            "actual_verdict": verdict,
            "actual_disposition": engine_disposition,
        })

    return warnings
