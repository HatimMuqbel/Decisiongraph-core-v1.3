"""Report generation endpoint for bank-grade AML/KYC decision reports.

Generates formal decision reports in multiple formats:
- HTML (suitable for printing/PDF)
- JSON (structured data for systems integration)
- Markdown (for documentation)

All formats produce regulator-grade, audit-safe output.
"""

# ── Module identity (visible in /health and deploy logs) ──
REPORT_MODULE_VERSION = "2026-02-05.v6"

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
import os
from pathlib import Path
from typing import Optional

router = APIRouter(prefix="/report", tags=["Report"])

# Setup Jinja2 templates
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# In-memory cache of recent decisions for report generation
# In production, this would be a proper cache/database
decision_cache: dict[str, dict] = {}
MIN_DECISION_PREFIX = int(os.getenv("DG_DECISION_PREFIX_MIN", "12"))
ALLOW_RAW_DECISION = os.getenv("DG_ALLOW_RAW_DECISION", "false").lower() == "true"


def cache_decision(decision_id: str, decision_pack: dict):
    """Cache a decision for later report generation."""
    decision_cache[decision_id] = decision_pack
    # Keep only last 100 decisions
    if len(decision_cache) > 100:
        oldest_key = next(iter(decision_cache))
        del decision_cache[oldest_key]


def get_cached_decision(decision_id: str) -> Optional[dict]:
    """Get a cached decision by ID."""
    return decision_cache.get(decision_id)


def _md_escape(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    return text.replace("\r", " ").replace("\n", " ").replace("|", "\\|").replace("`", "\\`")


def _format_component_score(value: object, weight: int) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    pct = int(round(numeric * 100)) if numeric <= 1.0 else int(round(numeric))
    if pct <= 0:
        return "Not material"
    return f"{pct}% ({weight}%)"


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
    return "Primary similarity drivers: " + ", ".join(top_labels) + "."


def _derive_decision_confidence(precedent_analysis: dict) -> tuple[Optional[str], Optional[str]]:
    if not precedent_analysis or not precedent_analysis.get("available"):
        return None, None
    confidence = precedent_analysis.get("precedent_confidence")
    if confidence is None:
        return None, None
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        return None, None
    if confidence_value >= 0.75:
        return "High", "Deterministic rule activation with strong precedent alignment."
    if confidence_value >= 0.45:
        return "Medium", "Deterministic rule activation with moderate precedent alignment."
    return "Low", "Deterministic rule activation with limited precedent alignment."


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
) -> list[str]:
    candidates: list[str] = []

    typologies = layer4_typologies.get("typologies", []) or []
    typology_names = []
    for typology in typologies:
        if isinstance(typology, dict):
            name = typology.get("name") or ""
        else:
            name = str(typology)
        if name:
            typology_names.append(name)
    for name in sorted(set(typology_names)):
        mapped = _map_driver_label(name) or f"{name} indicators"
        candidates.append(mapped)

    elements = layer6_suspicion.get("elements", {}) or {}
    for element in sorted(k for k, active in elements.items() if active):
        mapped = _map_driver_label(element) or f"Suspicion element: {element}"
        candidates.append(mapped)

    if str_required:
        candidates.append("Reporting threshold met (STR required)")
    if not gate1_passed:
        candidates.append("Escalation blocked by Gate 1 legal basis")

    triggered_rules = [
        rule for rule in rules_fired
        if str(rule.get("result", "")).upper() in {"TRIGGERED", "ACTIVATED", "FAIL", "FAILED"}
    ]
    triggered_rules = sorted(
        triggered_rules,
        key=lambda rule: str(rule.get("code", "")),
    )
    for rule in triggered_rules:
        code = str(rule.get("code", ""))
        reason = str(rule.get("reason", ""))
        mapped = _map_driver_label(code) or _map_driver_label(reason) or _map_driver_label(f"{code} {reason}")
        if mapped:
            candidates.append(mapped)

    for item in sorted(
        risk_factors,
        key=lambda entry: (str(entry.get("field", "")), str(entry.get("value", ""))),
    ):
        mapped = _map_driver_label(str(item.get("field", ""))) or _map_driver_label(str(item.get("value", "")))
        if mapped:
            candidates.append(mapped)

    deduped = []
    seen = set()
    for label in candidates:
        if label not in seen:
            deduped.append(label)
            seen.add(label)

    if not deduped:
        return ["Deterministic rule activation requiring review"]

    return deduped[:5]


def _find_decision_or_raise(decision_id: str) -> dict:
    if decision_id in decision_cache:
        return decision_cache[decision_id]

    if len(decision_id) < MIN_DECISION_PREFIX:
        raise HTTPException(
            status_code=400,
            detail=f"Decision id prefix must be at least {MIN_DECISION_PREFIX} characters.",
        )

    matches = [
        cached_decision
        for cached_id, cached_decision in decision_cache.items()
        if cached_id.startswith(decision_id)
    ]

    if not matches:
        raise HTTPException(
            status_code=404,
            detail=f"Decision '{decision_id}' not found. Decisions are cached briefly. "
                   f"Re-run the decision and immediately request the report.",
        )
    if len(matches) > 1:
        raise HTTPException(
            status_code=409,
            detail="Decision id prefix is ambiguous. Provide a longer prefix or the full id.",
        )

    return matches[0]


def _redact_decision(decision: dict) -> dict:
    meta = decision.get("meta", {}) or {}
    decision_data = decision.get("decision", {}) or {}
    gates = decision.get("gates", {}) or {}
    layers = decision.get("layers", {}) or {}
    rationale = decision.get("rationale", {}) or {}
    compliance = decision.get("compliance", {}) or {}
    eval_trace = decision.get("evaluation_trace", {}) or {}

    redacted_meta = {
        "decision_id": meta.get("decision_id"),
        "case_id": meta.get("case_id"),
        "timestamp": meta.get("timestamp"),
        "jurisdiction": meta.get("jurisdiction"),
        "engine_version": meta.get("engine_version"),
        "policy_version": meta.get("policy_version"),
        "domain": meta.get("domain"),
        "input_hash": meta.get("input_hash"),
        "policy_hash": meta.get("policy_hash"),
    }

    return {
        "meta": redacted_meta,
        "decision": decision_data,
        "gates": gates,
        "layers": layers,
        "rationale": rationale,
        "compliance": compliance,
        "evaluation_trace": eval_trace,
        "redacted": True,
    }


def build_report_context(decision: dict) -> dict:
    """Build template context from decision pack."""
    meta = decision.get("meta", {}) or {}
    dec = decision.get("decision", {}) or {}
    gates = decision.get("gates", {}) or {}
    layers = decision.get("layers", {}) or {}
    rationale = decision.get("rationale", {}) or {}
    compliance = decision.get("compliance", {}) or {}
    eval_trace = decision.get("evaluation_trace", {}) or {}

    # Determine verdict and status
    verdict = dec.get("verdict", "UNKNOWN") or "UNKNOWN"
    action = dec.get("action", "") or "N/A"

    if verdict in ["PASS", "PASS_WITH_EDD"]:
        decision_status = "pass"
        decision_explainer = "No suspicious activity indicators detected. Transaction may proceed."
    elif verdict in ["HARD_STOP", "STR", "ESCALATE"]:
        decision_status = "escalate"
        decision_explainer = rationale.get("summary", "") or "Suspicious indicators detected requiring escalation."
    else:
        decision_status = "review"
        decision_explainer = "Additional review required before final determination."

    # Handle str_required - convert bool to proper format
    str_required_raw = dec.get("str_required", False)
    if isinstance(str_required_raw, bool):
        str_required = str_required_raw
    elif str_required_raw in ["YES", "yes", "Y", "y", True]:
        str_required = True
    else:
        str_required = False

    # Build gate results
    gate1 = gates.get("gate1", {}) or {}
    gate2 = gates.get("gate2", {}) or {}

    gate1_passed = gate1.get("decision") != "PROHIBITED"

    gate1_sections = []
    sections1 = gate1.get("sections", {}) or {}
    if isinstance(sections1, dict):
        for section_id in sorted(sections1.keys()):
            section_data = sections1.get(section_id, {})
            if isinstance(section_data, dict):
                gate1_sections.append({
                    "id": section_id,
                    "name": section_data.get("name", section_id),
                    "passed": section_data.get("passed", False),
                    "reason": section_data.get("reason", "")
                })
    elif isinstance(sections1, list):
        gate1_sections = sorted(
            sections1,
            key=lambda section: (
                str(section.get("name", "")),
                str(section.get("id", "")),
            ),
        )

    gate2_sections = []
    sections2 = gate2.get("sections", {}) or {}
    if isinstance(sections2, dict):
        for section_id in sorted(sections2.keys()):
            section_data = sections2.get(section_id, {})
            if isinstance(section_data, dict):
                gate2_sections.append({
                    "id": section_id,
                    "name": section_data.get("name", section_id),
                    "passed": section_data.get("passed", False),
                    "reason": section_data.get("reason", "")
                })
    elif isinstance(sections2, list):
        gate2_sections = sorted(
            sections2,
            key=lambda section: (
                str(section.get("name", "")),
                str(section.get("id", "")),
            ),
        )

    # Build transaction facts from layers
    transaction_facts = []
    layer1 = layers.get("layer1_facts", {}) or {}

    # Customer facts
    customer = layer1.get("customer", {}) or {}
    if customer.get("pep_flag") is not None:
        transaction_facts.append({"field": "PEP Status", "value": "Yes" if customer.get("pep_flag") else "No"})
    if customer.get("type"):
        transaction_facts.append({"field": "Customer Type", "value": customer.get("type")})
    if customer.get("residence"):
        transaction_facts.append({"field": "Residence Country", "value": customer.get("residence")})

    # Transaction facts
    txn = layer1.get("transaction", {}) or {}
    if txn.get("amount_cad") is not None:
        transaction_facts.append({"field": "Amount (CAD)", "value": f"${txn.get('amount_cad'):,.2f}"})
    if txn.get("method"):
        transaction_facts.append({"field": "Payment Method", "value": txn.get("method")})
    if txn.get("destination"):
        transaction_facts.append({"field": "Destination", "value": txn.get("destination")})

    # Screening facts
    screening = layer1.get("screening", {}) or {}
    if screening.get("match_score") is not None:
        transaction_facts.append({"field": "Match Score", "value": f"{screening.get('match_score')}%"})
    if screening.get("list_type"):
        transaction_facts.append({"field": "List Type", "value": screening.get("list_type")})

    # If no structured facts, add basic info
    if not transaction_facts:
        transaction_facts = [
            {"field": "Case ID", "value": meta.get("case_id", "N/A")},
            {"field": "Jurisdiction", "value": meta.get("jurisdiction", "CA")},
        ]

    # Escalation reasons
    escalation_reasons = []
    if rationale.get("absolute_rules_validated"):
        for rule in rationale.get("absolute_rules_validated", []):
            if "triggered" in str(rule).lower() or "failed" in str(rule).lower():
                escalation_reasons.append(rule)
    if dec.get("path"):
        escalation_reasons.append(f"Decision path: {dec.get('path')}")

    # Rules fired
    rules_fired = sorted(
        eval_trace.get("rules_fired", []) or [],
        key=lambda rule: str(rule.get("code", "")),
    )

    # Evidence used (raw evaluation trace)
    evidence_used = sorted(
        eval_trace.get("evidence_used", []) or [],
        key=lambda ev: str(ev.get("field", "")),
    )

    # Risk factor assessment (derived from decision layers)
    risk_factors = []
    layer1_facts = layers.get("layer1_facts", {}) or {}
    layer2_obligations = layers.get("layer2_obligations", {}) or {}
    layer3_indicators = layers.get("layer3_indicators", {}) or {}
    layer4_typologies = layers.get("layer4_typologies", {}) or {}
    layer6_suspicion = layers.get("layer6_suspicion", {}) or {}

    if layer1_facts.get("hard_stop_triggered"):
        risk_factors.append({
            "field": "Hard stop",
            "value": layer1_facts.get("hard_stop_reason") or "Triggered",
        })

    for obligation in layer2_obligations.get("obligations", []) or []:
        risk_factors.append({
            "field": "Regulatory obligation",
            "value": obligation,
        })

    for indicator in layer3_indicators.get("indicators", []) or []:
        if isinstance(indicator, dict):
            code = indicator.get("code") or indicator.get("name") or "Indicator"
            status = "Corroborated" if indicator.get("corroborated") else "Uncorroborated"
            evidence = indicator.get("evidence")
            value = f"{status}" + (f" — {evidence}" if evidence else "")
            risk_factors.append({
                "field": code,
                "value": value,
            })
        else:
            risk_factors.append({
                "field": "Indicator",
                "value": str(indicator),
            })

    for typology in layer4_typologies.get("typologies", []) or []:
        if isinstance(typology, dict):
            name = typology.get("name") or "Typology"
            maturity = typology.get("maturity")
            value = f"{name}" + (f" ({maturity})" if maturity else "")
            risk_factors.append({
                "field": "Typology",
                "value": value,
            })

    elements = layer6_suspicion.get("elements", {}) or {}
    for element, active in elements.items():
        if active:
            risk_factors.append({
                "field": "Suspicion element",
                "value": element,
            })

    if not risk_factors:
        triggered = [
            rule for rule in rules_fired
            if str(rule.get("result", "")).upper() in {"TRIGGERED", "ACTIVATED", "FAIL", "FAILED"}
        ]
        for rule in triggered:
            code = rule.get("code") or "Rule"
            reason = rule.get("reason") or "Triggered"
            risk_factors.append({
                "field": code,
                "value": reason,
            })

    if not risk_factors and escalation_reasons:
        for reason in escalation_reasons[:3]:
            risk_factors.append({
                "field": "Escalation driver",
                "value": reason,
            })

    if not risk_factors and dec.get("path"):
        risk_factors.append({
            "field": "Decision path",
            "value": dec.get("path"),
        })

    if not risk_factors:
        risk_factors.append({
            "field": "Regulatory indicators",
            "value": "Indicators not captured in this record",
        })

    # Safe string extraction
    decision_id = meta.get("decision_id", "") or ""
    input_hash = meta.get("input_hash", "") or ""
    policy_hash = meta.get("policy_hash", "") or ""

    source_type_raw = meta.get("source_type") or "prod"
    source_type = str(source_type_raw).lower()
    source_labels = {
        "seed": "Seed",
        "seeded": "Seed",
        "byoc": "BYOC",
        "prod": "Production",
        "system_generated": "System",
        "imported": "Imported",
        "tribunal": "Tribunal",
    }
    source_label = source_labels.get(source_type, source_type.title())
    seed_category = meta.get("seed_category") or "N/A"
    scenario_code = meta.get("scenario_code") or "N/A"

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

    similarity_summary = _derive_similarity_summary(precedent_analysis)
    confidence_label, confidence_reason = _derive_decision_confidence(precedent_analysis)
    if similarity_summary:
        precedent_analysis = dict(precedent_analysis)
        precedent_analysis["similarity_summary"] = similarity_summary

    escalation_summary = ""
    if str_required:
        escalation_summary = (
            "Suspicion indicators triggered reporting thresholds under FINTRAC guidance. "
            "While Enhanced Due Diligence is required to complete the investigation, "
            "the current suspicion level independently meets the reporting threshold."
        )
    elif decision_status == "review":
        escalation_summary = (
            "Enhanced Due Diligence is required to complete the investigation and finalize the regulatory outcome."
        )
    elif decision_status == "pass":
        escalation_summary = "No escalation or reporting obligation was triggered based on available indicators."
    else:
        escalation_summary = (
            "Escalation is required to complete the investigation and determine any reporting obligations."
        )

    decision_drivers = _derive_decision_drivers(
        rules_fired=rules_fired,
        risk_factors=risk_factors,
        layer4_typologies=layer4_typologies,
        layer6_suspicion=layer6_suspicion,
        gate1_passed=gate1_passed,
        str_required=str_required,
    )

    report_sections = [
        "Administrative Details",
        "Investigation Outcome Summary",
        "Case Classification",
        "Regulatory Determination",
        "Decision Drivers",
        "Gate Evaluation",
        "Rules Evaluated",
        "Precedent Intelligence",
        "Risk Factors",
        "Evidence Considered",
        "Auditability & Governance",
    ]

    return {
        # Administrative Details
        "decision_id": decision_id,
        "decision_id_short": decision_id[:16] if decision_id else "N/A",
        "case_id": meta.get("case_id", "") or "N/A",
        "timestamp": meta.get("timestamp", "") or datetime.utcnow().isoformat(),
        "jurisdiction": meta.get("jurisdiction", "CA") or "CA",
        "engine_version": meta.get("engine_version", "") or "N/A",
        "policy_version": meta.get("policy_version", "") or "N/A",
        "domain": domain or "unknown",
        "report_schema_version": "DecisionReportSchema v1",
        "report_sections": report_sections,

        # Input/Policy hashes
        "input_hash": input_hash,
        "input_hash_short": input_hash[:16] if input_hash else "N/A",
        "policy_hash": policy_hash,
        "policy_hash_short": policy_hash[:16] if policy_hash else "N/A",

        # Case classification
        "source_type": source_label,
        "seed_category": seed_category,
        "scenario_code": scenario_code,
        "is_seed": source_type in {"seed", "seeded"},
        "escalation_summary": escalation_summary,
        "decision_confidence": confidence_label,
        "decision_confidence_reason": confidence_reason,
        "similarity_summary": similarity_summary,
        "decision_drivers": decision_drivers,

        # Transaction Facts
        "transaction_facts": transaction_facts,

        # Decision
        "verdict": verdict,
        "action": action,
        "decision_status": decision_status,
        "decision_explainer": decision_explainer,
        "str_required": str_required,
        "escalation_reasons": escalation_reasons,

        # Gates
        "gate1_passed": gate1_passed,
        "gate1_decision": gate1.get("decision", "") or "N/A",
        "gate1_sections": gate1_sections,
        "gate2_decision": gate2.get("decision", "") or "N/A",
        "gate2_status": gate2.get("status", "") or "N/A",
        "gate2_sections": gate2_sections,

        # Evaluation trace
        "rules_fired": rules_fired,
        "evidence_used": evidence_used,
        "risk_factors": risk_factors,
        "decision_path_trace": eval_trace.get("decision_path", "") or "",

        # Rationale
        "summary": rationale.get("summary", "") or "No summary available",

        # Precedent Analysis
        "precedent_analysis": precedent_analysis,
    }


def _build_precedent_markdown(precedent_analysis: dict) -> str:
    """Build markdown section for precedent analysis."""
    if not precedent_analysis:
        return ""
    if not precedent_analysis.get("available"):
        message = precedent_analysis.get("message") or precedent_analysis.get("error") or "Precedent analysis unavailable."
        return f"""> {message}\n\n"""

    def _label(value: object) -> str:
        return str(value).upper() if value is not None else "N/A"

    def _pct(value: object) -> int:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0
        pct = int(round(numeric * 100)) if numeric <= 1.0 else int(round(numeric))
        return max(0, min(100, pct))

    # Outcome distribution rows
    match_distribution = (
        precedent_analysis.get("match_outcome_distribution")
        or precedent_analysis.get("outcome_distribution", {})
        or {}
    )
    overlap_distribution = (
        precedent_analysis.get("raw_outcome_distribution")
        or precedent_analysis.get("overlap_outcome_distribution", {})
        or {}
    )

    match_rows = ""
    for outcome, count in sorted(match_distribution.items(), key=lambda item: str(item[0])):
        match_rows += f"| {_label(outcome)} | {count} |\n"

    overlap_rows = ""
    for outcome, count in sorted(overlap_distribution.items(), key=lambda item: str(item[0])):
        overlap_rows += f"| {_label(outcome)} | {count} |\n"

    # Appeal stats
    appeal = precedent_analysis.get("appeal_statistics", {})

    # Caution precedents
    caution = precedent_analysis.get("caution_precedents", [])
    caution_section = ""
    if caution:
        caution_section = "\n### Caution Precedents (Overturned Cases)\n\n"
        caution_section += f"**{len(caution)}** similar cases were later overturned on appeal:\n\n"
        for prec in caution[:5]:
            caution_section += f"- **{prec.get('case_ref', 'N/A')}** — {_label(prec.get('outcome'))}"
            if prec.get("appeal_result"):
                caution_section += f" (Appeal: {prec['appeal_result']})"
            caution_section += "\n"
        if len(caution) > 5:
            caution_section += f"- ... and {len(caution) - 5} more\n"

    confidence_pct = int((precedent_analysis.get("precedent_confidence", 0) or 0) * 100)
    upheld_rate_pct = int((appeal.get("upheld_rate", 0) or 0) * 100)

    sample_size = int(precedent_analysis.get("sample_size", 0) or 0)
    neutral = int(precedent_analysis.get("neutral_precedents", 0) or 0)
    min_similarity_pct = int(precedent_analysis.get("min_similarity_pct", 50) or 50)
    raw_overlap_count = (
        precedent_analysis.get("raw_overlap_count")
        or precedent_analysis.get("overlap_count")
        or precedent_analysis.get("raw_count")
        or 0
    )
    raw_overlap_count = int(raw_overlap_count or 0)

    sample_cases = precedent_analysis.get("sample_cases", []) or []
    exact_match_count = int(precedent_analysis.get("exact_match_count", 0) or 0)
    match_count = int(precedent_analysis.get("match_count", 0) or 0)
    weights = precedent_analysis.get("weights", {}) or {}

    def _weight(key: str, default: int) -> int:
        value = weights.get(key, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    matches_md = ""
    if sample_cases:
        matches_md = "\n### Precedent Evidence (Top Matches)\n\n| Precedent | Outcome | Similarity | Decision Level | Reason Codes | Similarity Drivers |\n|---|---|---|---|---|---|\n"
        for match in sample_cases:
            outcome_label = match.get("outcome_label") or _label(match.get("outcome"))
            similarity = f"{int(match.get('similarity_pct', 0) or 0)}%"
            if match.get("exact_match"):
                similarity += " (EXACT)"
            reason_codes = ", ".join(match.get("reason_codes", []) or [])
            components = match.get("similarity_components", {}) or {}
            drivers = (
                f"Rules {_format_component_score(components.get('rules_overlap'), _weight('rules_overlap', 25))}, "
                f"Gates {_format_component_score(components.get('gate_match'), _weight('gate_match', 20))}, "
                f"Typologies {_format_component_score(components.get('typology_overlap'), _weight('typology_overlap', 15))}, "
                f"Amount {_format_component_score(components.get('amount_bucket'), _weight('amount_bucket', 10))}, "
                f"Channel {_format_component_score(components.get('channel_method'), _weight('channel_method', 7))}, "
                f"Corridor {_format_component_score(components.get('corridor_match'), _weight('corridor_match', 8))}, "
                f"PEP {_format_component_score(components.get('pep_match'), _weight('pep_match', 6))}, "
                f"Customer {_format_component_score(components.get('customer_profile'), _weight('customer_profile', 5))}, "
                f"Geo {_format_component_score(components.get('geo_risk'), _weight('geo_risk', 4))}"
            )
            matches_md += (
                f"| {_md_escape(match.get('precedent_id', 'N/A'))} | {_md_escape(outcome_label)} | {similarity} | "
                f"{_md_escape(match.get('decision_level', 'N/A'))} | {_md_escape(reason_codes)} | {_md_escape(drivers)} |\n"
            )

    note_md = ""
    if raw_overlap_count > 0 and match_count == 0 and not sample_cases:
        note_md = (
            "\n> Raw overlaps were found based on limited features, "
            "but no precedents met the similarity threshold. "
            "Provide transaction shape and customer profile facts (amount bucket, channel, corridor, customer type, "
            "relationship length, PEP) to enable scoring.\n"
            "> Raw overlaps reflect cases sharing one or more structural indicators but not meeting the "
            "similarity threshold required for scored comparison.\n"
        )
    elif raw_overlap_count > 0:
        note_md = (
            "\n> Raw overlaps reflect cases sharing one or more structural indicators but not meeting the "
            "similarity threshold required for scored comparison.\n"
        )

    candidates_scored = int(precedent_analysis.get("candidates_scored", sample_size) or 0)
    threshold_mode = precedent_analysis.get("threshold_mode", "prod")
    threshold_pct = int(round((precedent_analysis.get("threshold_used") or 0) * 100))
    show_overlap = bool(overlap_distribution) and overlap_distribution != match_distribution

    overlap_section = ""
    if show_overlap:
        overlap_section = f"""
### Raw Overlap Outcome Distribution

| Outcome | Count |
|---------|-------|
{overlap_rows or "| No data | - |"}
"""

    return f"""*Precedent analysis is advisory and does not override the deterministic engine verdict.*
*Absence of precedent matches does not imply the recommendation is incorrect.*

| Metric | Value |
|--------|-------|
| Comparable Matches (Scored) | {match_count} |
| Raw Overlaps Found | {raw_overlap_count} |
| Candidates Scored | {candidates_scored} (≥{threshold_pct or min_similarity_pct}% similarity required; mode: {threshold_mode}) |
| Precedent Confidence | {confidence_pct}% |
| Exact Matches | {exact_match_count} |
| Supporting Precedents | {precedent_analysis.get('supporting_precedents', 0)} |
| Contrary Precedents | {precedent_analysis.get('contrary_precedents', 0)} |
| Neutral Precedents | {neutral} |

*Neutral indicates precedents where the outcome is a review/escalation state rather than a final pay/deny decision.*

{_md_escape(precedent_analysis.get("similarity_summary", ""))}

### Scored Match Outcome Distribution

| Outcome | Count |
|---------|-------|
{match_rows or "| No data | - |"}

{overlap_section}

{note_md}

### Appeal Statistics

| Metric | Value |
|--------|-------|
| Total Appealed | {appeal.get('total_appealed', 0)} |
| Upheld | {appeal.get('upheld', 0)} |
| Overturned | {appeal.get('overturned', 0)} |
| Upheld Rate | {upheld_rate_pct}% |
{caution_section}
{matches_md}
"""


@router.get("/{decision_id}", response_class=HTMLResponse)
async def get_report_html(request: Request, decision_id: str):
    """
    Generate a regulator-grade HTML decision report.

    Returns a formatted HTML document suitable for:
    - Printing (print-optimized CSS)
    - PDF generation
    - Audit records
    - Regulatory review
    """
    decision = _find_decision_or_raise(decision_id)

    try:
        context = build_report_context(decision)
        context["request"] = request  # Required by Jinja2Templates

        return templates.TemplateResponse("decision_report.html", context)

    except Exception as e:
        # Return a simple error page instead of 500
        error_html = f"""<!DOCTYPE html>
<html><head><title>Report Error</title></head>
<body style="font-family: sans-serif; padding: 40px; max-width: 600px; margin: 0 auto;">
<h1>Report Generation Error</h1>
<p>Could not generate report for decision: <code>{decision_id[:16]}...</code></p>
<p><strong>Error:</strong> {str(e)}</p>
<p><a href="/">Back to Demo</a></p>
</body></html>"""
        return HTMLResponse(content=error_html, status_code=500)


@router.get("/{decision_id}/json")
async def get_report_json(decision_id: str, include_raw: bool = False):
    """
    Get decision report as structured JSON.

    Returns the same content as the HTML report but in JSON format,
    suitable for systems integration.
    """
    decision = _find_decision_or_raise(decision_id)

    ctx = build_report_context(decision)

    response = {
        "format": "json",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "report": ctx,
    }

    if include_raw:
        if not ALLOW_RAW_DECISION:
            raise HTTPException(
                status_code=403,
                detail="Raw decision output is disabled in this environment.",
            )
        response["raw_decision"] = _redact_decision(decision)

    return response


@router.get("/{decision_id}/markdown")
async def get_report_markdown(decision_id: str):
    """
    Generate a Markdown decision report.
    """
    decision = _find_decision_or_raise(decision_id)

    ctx = build_report_context(decision)

    # Build transaction facts table
    facts_rows = ""
    for fact in ctx.get('transaction_facts', []):
        facts_rows += f"| {_md_escape(fact['field'])} | `{_md_escape(fact['value'])}` |\n"

    # Build gate1 sections
    gate1_rows = ""
    for section in ctx.get('gate1_sections', []):
        status = "PASS" if section.get('passed') else "FAIL"
        gate1_rows += f"| {_md_escape(section.get('name', 'N/A'))} | {status} | {_md_escape(section.get('reason', ''))} |\n"

    # Build gate2 sections
    gate2_rows = ""
    for section in ctx.get('gate2_sections', []):
        status = "PASS" if section.get('passed') else "REVIEW"
        gate2_rows += f"| {_md_escape(section.get('name', 'N/A'))} | {status} | {_md_escape(section.get('reason', ''))} |\n"

    # Build rules fired table
    rules_rows = ""
    for rule in ctx.get('rules_fired', []):
        rules_rows += f"| `{_md_escape(rule.get('code', 'N/A'))}` | {_md_escape(rule.get('result', 'N/A'))} | {_md_escape(rule.get('reason', ''))} |\n"

    # Build evidence table
    evidence_rows = ""
    for ev in ctx.get('evidence_used', []):
        value = ev.get('value', 'N/A')
        if isinstance(value, bool):
            value = "Yes" if value else "No"
        evidence_rows += f"| `{_md_escape(ev.get('field', 'N/A'))}` | {_md_escape(value)} |\n"

    # Decision header
    if ctx['decision_status'] == "pass":
        decision_header = "### **PASS** — Transaction Allowed"
    elif ctx['decision_status'] == "escalate":
        decision_header = f"### **ESCALATE** — {ctx['action']}"
    else:
        decision_header = "### **REVIEW REQUIRED**"

    safe_path = _md_escape(ctx['decision_path_trace'] or 'N/A')
    decision_confidence_block = ""
    if ctx.get('decision_confidence'):
        decision_confidence_block = (
            f"Decision Confidence: {ctx['decision_confidence']}\n\n"
            f"{ctx['decision_confidence_reason']}"
        )
    decision_drivers_md = "\n".join(
        [f"- {_md_escape(driver)}" for driver in ctx.get('decision_drivers', [])]
    ) or "- Decision drivers derived from rule evaluation were not available in this record."
    risk_factors_md = "\n".join(
        [
            f"| {_md_escape(item.get('field', 'N/A'))} | {_md_escape(item.get('value', 'N/A'))} |"
            for item in ctx.get('risk_factors', [])
        ]
    ) or "| No risk factors recorded | - |"
    governance_note = ""
    if ctx['str_required']:
        governance_note = (
            "### Governance Note\n\n"
            "A Suspicious Transaction Report (STR) is required under PCMLTFA/FINTRAC guidelines.\n"
            "This report must be filed within 30 days of the suspicion being formed.\n"
        )
    seed_notice = "> Synthetic training case (seeded)." if ctx.get("is_seed") else ""
    str_required_label = "Yes" if ctx.get("str_required") else "No"
    gate1_label = "ALLOWED" if ctx.get("gate1_passed") else "BLOCKED"
    gate1_rows_output = gate1_rows or "| No sections evaluated | - | - |"
    gate2_rows_output = gate2_rows or "| No sections evaluated | - | - |"
    rules_rows_output = rules_rows or "| No rules evaluated | - | - |"
    evidence_rows_output = evidence_rows or "| No evidence recorded | - |"
    precedent_markdown = _build_precedent_markdown(ctx.get("precedent_analysis", {}))

    md_template = """# AML/KYC Decision Report

**Deterministic Regulatory Decision Engine (Zero LLM)**

---

## Administrative Details

| Field | Value |
|-------|-------|
| Decision ID | `{decision_id_short}...` |
| Case ID | `{case_id}` |
| Timestamp | `{timestamp}` |
| Jurisdiction | {jurisdiction} |
| Engine Version | `{engine_version}` |
| Policy Version | `{policy_version}` |
| Report Schema | `{report_schema_version}` |

---

## Investigation Outcome Summary

| Field | Value |
|-------|-------|
| Verdict | {verdict} |
| Action | {action} |
| STR Required | {str_required_label} |
| Decision Status | {decision_status_upper} |

{decision_explainer}

### Case Facts

| Field | Value |
|-------|-------|
{facts_rows}

---

## Case Classification

| Field | Value |
|-------|-------|
| Source | {source_type} |
| Seed Category | {seed_category} |
| Scenario Code | `{scenario_code}` |

{seed_notice}

---

## Regulatory Determination

{decision_header}

{decision_explainer}

**STR Required:** {str_required_label}

### Regulatory Escalation Summary

{escalation_summary}

{decision_confidence_block}

---

## Decision Drivers

{decision_drivers_md}

---

## Gate Evaluation

### Gate 1: Zero-False-Escalation

**Decision:** {gate1_label}

| Section | Status | Reason |
|---------|--------|--------|
{gate1_rows_output}


### Gate 2: STR Threshold

**STR Required:** {str_required_label}

| Section | Status | Reason |
|---------|--------|--------|
{gate2_rows_output}


---

## Rules Evaluated

| Rule Code | Result | Reason |
|-----------|--------|--------|
{rules_rows_output}


## Precedent Intelligence

{precedent_markdown}

## Risk Factors

| Field | Value |
|-------|-------|
{risk_factors_md}

---

## Evidence Considered

| Field | Value |
|-------|-------|
{evidence_rows_output}

---

## Auditability & Governance

### Decision Provenance

| Field | Value |
|-------|-------|
| Decision Hash | `{decision_id}` |
| Input Hash | `{input_hash}` |
| Policy Hash | `{policy_hash}` |
| Decision Path | `{safe_path}` |

This decision is cryptographically bound to the exact input and policy evaluated.

### Determinism & Auditability Statement

This decision was produced by a deterministic rule engine.
Re-evaluation using identical inputs and the same policy version will produce identical results.

The decision may be independently verified using the `/verify` endpoint. Complete decision lineage, rule sequencing, and evidentiary artifacts are preserved within the immutable audit record and available for supervisory review.

{governance_note}

---

*DecisionGraph — Deterministic - Reproducible - Auditable*

*Generated {timestamp}*
"""

    md = md_template.format(
        action=ctx.get("action"),
        case_id=ctx.get("case_id"),
        decision_explainer=ctx.get("decision_explainer"),
        decision_header=decision_header,
        decision_id=ctx.get("decision_id"),
        decision_id_short=ctx.get("decision_id_short"),
        decision_status_upper=ctx.get("decision_status", "").upper(),
        decision_confidence_block=decision_confidence_block,
        decision_drivers_md=decision_drivers_md,
        engine_version=ctx.get("engine_version"),
        evidence_rows_output=evidence_rows_output,
        facts_rows=facts_rows,
        gate1_label=gate1_label,
        gate1_rows_output=gate1_rows_output,
        gate2_rows_output=gate2_rows_output,
        governance_note=governance_note,
        input_hash=ctx.get("input_hash"),
        jurisdiction=ctx.get("jurisdiction"),
        policy_hash=ctx.get("policy_hash"),
        policy_version=ctx.get("policy_version"),
        precedent_markdown=precedent_markdown,
        report_schema_version=ctx.get("report_schema_version"),
        risk_factors_md=risk_factors_md,
        rules_rows_output=rules_rows_output,
        safe_path=safe_path,
        scenario_code=_md_escape(ctx.get("scenario_code")),
        seed_category=ctx.get("seed_category"),
        seed_notice=seed_notice,
        source_type=ctx.get("source_type"),
        str_required_label=str_required_label,
        timestamp=ctx.get("timestamp"),
        verdict=ctx.get("verdict"),
        escalation_summary=ctx.get("escalation_summary"),
    )

    return {
        "decision_id": decision_id,
        "format": "markdown",
        "content": md,
        "generated_at": datetime.utcnow().isoformat() + "Z"
    }
