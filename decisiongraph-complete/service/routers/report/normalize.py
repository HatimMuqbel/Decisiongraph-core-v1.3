"""Normalize — Stage A of the Report Compiler Pipeline.

Normalizes a raw decision pack into a predictable, typed shape.
Pure data, no formatting strings, no narrative text.

Input:  raw decision dict (as stored in DecisionStore)
Output: NormalizedDecision (plain dict with guaranteed keys / shapes)
"""


def normalize_decision(decision: dict) -> dict:
    """Turn a raw decision pack into a stable, guaranteed-shape dict.

    Responsibilities:
    - normalize booleans (str_required)
    - normalize verdict/action
    - normalize gates/sections into consistent list shape
    - normalize evidence/rules ordering
    - extract layer dicts with safe defaults
    - NO narrative text, NO currency formatting
    """
    meta = decision.get("meta", {}) or {}
    dec = decision.get("decision", {}) or {}
    gates = decision.get("gates", {}) or {}
    layers = decision.get("layers", {}) or {}
    rationale = decision.get("rationale", {}) or {}
    compliance = decision.get("compliance", {}) or {}
    eval_trace = decision.get("evaluation_trace", {}) or {}

    # ── Verdict / Action ──────────────────────────────────────────────────
    verdict = dec.get("verdict", "UNKNOWN") or "UNKNOWN"
    action = dec.get("action", "") or "N/A"

    # ── str_required boolean ──────────────────────────────────────────────
    str_required_raw = dec.get("str_required", False)
    if isinstance(str_required_raw, bool):
        str_required = str_required_raw
    elif str_required_raw in ("YES", "yes", "Y", "y", True):
        str_required = True
    else:
        str_required = False

    # ── Gates ─────────────────────────────────────────────────────────────
    gate1 = gates.get("gate1", {}) or {}
    gate2 = gates.get("gate2", {}) or {}

    gate1_passed = gate1.get("decision") != "PROHIBITED"

    gate1_sections = _normalize_sections(gate1.get("sections", {}) or {})
    gate2_sections = _normalize_sections(gate2.get("sections", {}) or {})

    # ── Layers (safe extraction) ──────────────────────────────────────────
    layer1_facts = layers.get("layer1_facts", {}) or {}
    layer2_obligations = layers.get("layer2_obligations", {}) or {}
    layer3_indicators = layers.get("layer3_indicators", {}) or {}
    layer4_typologies = layers.get("layer4_typologies", {}) or {}
    layer6_suspicion = layers.get("layer6_suspicion", {}) or {}

    # ── Rules / Evidence (sorted for determinism) ─────────────────────────
    rules_fired = sorted(
        eval_trace.get("rules_fired", []) or [],
        key=lambda rule: str(rule.get("code", "")),
    )
    evidence_used = sorted(
        eval_trace.get("evidence_used", []) or [],
        key=lambda ev: str(ev.get("field", "")),
    )

    # ── Precedent analysis ────────────────────────────────────────────────
    domain = meta.get("domain")
    precedent_analysis = decision.get("precedent_analysis", {}) or {}
    domain_allowed = str(domain).lower() in {"banking_aml", "banking", "aml", "bank"} if domain else True
    if not domain_allowed:
        precedent_analysis = {
            "available": False,
            "message": "Precedent analysis is not enabled for this domain",
        }
    elif not precedent_analysis:
        precedent_analysis = {
            "available": False,
            "message": "Precedent analysis missing from decision cache. Re-run the decision and refresh the report.",
        }

    # ── Source classification ─────────────────────────────────────────────
    source_type_raw = str(meta.get("source_type") or "prod").lower()
    source_labels = {
        "seed": "Seed", "seeded": "Seed", "byoc": "BYOC",
        "prod": "Production", "system_generated": "System",
        "imported": "Imported", "tribunal": "Tribunal",
    }
    source_label = source_labels.get(source_type_raw, source_type_raw.title())

    # ── Classifier override data (if main.py applied one) ────────────────
    classifier_override = decision.get("classifier", {}) or {}

    return {
        # Meta
        "decision_id": meta.get("decision_id", "") or "",
        "case_id": meta.get("case_id", "") or "N/A",
        "timestamp": meta.get("timestamp", "") or "",
        "jurisdiction": meta.get("jurisdiction", "CA") or "CA",
        "engine_version": meta.get("engine_version", "") or "N/A",
        "policy_version": meta.get("policy_version", "") or "N/A",
        "domain": domain or "unknown",
        "input_hash": meta.get("input_hash", "") or "",
        "policy_hash": meta.get("policy_hash", "") or "",
        "source_type_raw": source_type_raw,
        "source_label": source_label,
        "seed_category": meta.get("seed_category") or "N/A",
        "scenario_code": meta.get("scenario_code") or "N/A",
        "is_seed": source_type_raw in {"seed", "seeded"},

        # Decision
        "verdict": verdict,
        "action": action,
        "str_required": str_required,
        "decision_path": dec.get("path", ""),

        # Gates
        "gate1_passed": gate1_passed,
        "gate1_decision": gate1.get("decision", "") or "N/A",
        "gate1_sections": gate1_sections,
        "gate2_decision": gate2.get("decision", "") or "N/A",
        "gate2_status": gate2.get("status", "") or "N/A",
        "gate2_sections": gate2_sections,

        # Layers
        "layer1_facts": layer1_facts,
        "layer2_obligations": layer2_obligations,
        "layer3_indicators": layer3_indicators,
        "layer4_typologies": layer4_typologies,
        "layer6_suspicion": layer6_suspicion,

        # Evaluation trace
        "rules_fired": rules_fired,
        "evidence_used": evidence_used,
        "decision_path_trace": eval_trace.get("decision_path", "") or "",

        # Rationale
        "rationale_summary": rationale.get("summary", "") or "No summary available",
        "absolute_rules_validated": rationale.get("absolute_rules_validated", []) or [],

        # Precedent
        "precedent_analysis": precedent_analysis,

        # Classifier override (from main.py)
        "classifier_override": classifier_override,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_sections(sections) -> list[dict]:
    """Normalize gate sections from either dict or list form to a sorted list."""
    if isinstance(sections, dict):
        result = []
        for section_id in sorted(sections.keys()):
            section_data = sections.get(section_id, {})
            if isinstance(section_data, dict):
                result.append({
                    "id": section_id,
                    "name": section_data.get("name", section_id),
                    "passed": section_data.get("passed", False),
                    "reason": section_data.get("reason", ""),
                })
        return result
    if isinstance(sections, list):
        return sorted(
            sections,
            key=lambda s: (str(s.get("name", "")), str(s.get("id", ""))),
        )
    return []
