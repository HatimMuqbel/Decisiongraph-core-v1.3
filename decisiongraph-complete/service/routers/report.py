"""Report generation endpoint for bank-grade AML/KYC decision reports.

Generates formal decision reports in multiple formats:
- HTML (suitable for printing/PDF)
- JSON (structured data for systems integration)
- Markdown (for documentation)

All formats produce regulator-grade, audit-safe output.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from pathlib import Path
from typing import Optional

router = APIRouter(prefix="/report", tags=["Report"])

# Setup Jinja2 templates
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# In-memory cache of recent decisions for report generation
# In production, this would be a proper cache/database
decision_cache: dict[str, dict] = {}


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
        for section_id, section_data in sections1.items():
            if isinstance(section_data, dict):
                gate1_sections.append({
                    "id": section_id,
                    "name": section_data.get("name", section_id),
                    "passed": section_data.get("passed", False),
                    "reason": section_data.get("reason", "")
                })
    elif isinstance(sections1, list):
        gate1_sections = sections1

    gate2_sections = []
    sections2 = gate2.get("sections", {}) or {}
    if isinstance(sections2, dict):
        for section_id, section_data in sections2.items():
            if isinstance(section_data, dict):
                gate2_sections.append({
                    "id": section_id,
                    "name": section_data.get("name", section_id),
                    "passed": section_data.get("passed", False),
                    "reason": section_data.get("reason", "")
                })
    elif isinstance(sections2, list):
        gate2_sections = sections2

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
    if txn.get("amount_cad"):
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
    rules_fired = eval_trace.get("rules_fired", []) or []

    # Evidence used (raw evaluation trace)
    evidence_used = eval_trace.get("evidence_used", []) or []

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

    # Safe string extraction
    decision_id = meta.get("decision_id", "") or ""
    input_hash = meta.get("input_hash", "") or ""
    policy_hash = meta.get("policy_hash", "") or ""

    domain = meta.get("domain")
    precedent_analysis = decision.get("precedent_analysis", {})
    if domain and str(domain).lower() not in {"banking_aml", "banking", "aml", "bank"}:
        precedent_analysis = {
            "available": False,
            "message": "Precedent analysis is not enabled for this domain",
        }

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

        # Input/Policy hashes
        "input_hash": input_hash,
        "input_hash_short": input_hash[:16] if input_hash else "N/A",
        "policy_hash": policy_hash,
        "policy_hash_short": policy_hash[:16] if policy_hash else "N/A",

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
    if not precedent_analysis or not precedent_analysis.get("available"):
        return ""

    # Outcome distribution rows
    outcome_rows = ""
    for outcome, count in precedent_analysis.get("outcome_distribution", {}).items():
        outcome_rows += f"| {outcome.upper()} | {count} |\n"

    # Appeal stats
    appeal = precedent_analysis.get("appeal_statistics", {})

    # Caution precedents
    caution = precedent_analysis.get("caution_precedents", [])
    caution_section = ""
    if caution:
        caution_section = "\n### Caution Precedents (Overturned Cases)\n\n"
        caution_section += f"**{len(caution)}** similar cases were later overturned on appeal:\n\n"
        for prec in caution[:5]:
            caution_section += f"- **{prec.get('case_ref', 'N/A')}** — {prec.get('outcome', 'N/A').upper()}"
            if prec.get("appeal_result"):
                caution_section += f" (Appeal: {prec['appeal_result']})"
            caution_section += "\n"
        if len(caution) > 5:
            caution_section += f"- ... and {len(caution) - 5} more\n"

    confidence_pct = int(precedent_analysis.get("precedent_confidence", 0) * 100)
    upheld_rate_pct = int(appeal.get("upheld_rate", 0) * 100)

    sample_size = precedent_analysis.get('sample_size', 50)
    neutral = precedent_analysis.get('neutral_precedents', 0)
    min_similarity_pct = precedent_analysis.get("min_similarity_pct", 50)

    sample_cases = precedent_analysis.get("sample_cases", []) or []
    exact_match_count = precedent_analysis.get("exact_match_count", 0)

    matches_md = ""
    if sample_cases:
        matches_md = "\n### Precedent Evidence (Top Matches)\n\n| Precedent | Outcome | Similarity | Decision Level | Reason Codes | Similarity Drivers |\n|---|---|---|---|---|---|\n"
        for match in sample_cases:
            outcome_label = match.get("outcome_label") or match.get("outcome", "N/A").upper()
            similarity = f"{match.get('similarity_pct', 0)}%"
            if match.get("exact_match"):
                similarity += " (EXACT)"
            reason_codes = ", ".join(match.get("reason_codes", []) or [])
            components = match.get("similarity_components", {}) or {}
            drivers = (
                f"Rules {components.get('rules_overlap', 0)}% (25%), "
                f"Gates {components.get('gate_match', 0)}% (20%), "
                f"Typologies {components.get('typology_overlap', 0)}% (15%), "
                f"Amount {components.get('amount_bucket', 0)}% (10%), "
                f"Channel {components.get('channel_method', 0)}% (7%), "
                f"Corridor {components.get('corridor_match', 0)}% (8%), "
                f"PEP {components.get('pep_match', 0)}% (6%), "
                f"Customer {components.get('customer_profile', 0)}% (5%), "
                f"Geo {components.get('geo_risk', 0)}% (4%)"
            )
            matches_md += f"| {match.get('precedent_id', 'N/A')} | {outcome_label} | {similarity} | {match.get('decision_level', 'N/A')} | {reason_codes} | {drivers} |\n"

    return f"""## Precedent Analysis

| Metric | Value |
|--------|-------|
| Similar Cases Found | {precedent_analysis.get('match_count', 0)} |
| Sample Size Analyzed | {sample_size} (≥{min_similarity_pct}% similarity — rules+gates weighted) |
| Precedent Confidence | {confidence_pct}% |
| Exact Matches | {exact_match_count} |
| Supporting Precedents | {precedent_analysis.get('supporting_precedents', 0)} |
| Contrary Precedents | {precedent_analysis.get('contrary_precedents', 0)} |
| Neutral Precedents | {neutral} |

*Neutral indicates precedents where the outcome is a review/escalation state rather than a final pay/deny decision.*

### Outcome Distribution

| Outcome | Count |
|---------|-------|
{outcome_rows or "| No data | - |"}

### Appeal Statistics

| Metric | Value |
|--------|-------|
| Total Appealed | {appeal.get('total_appealed', 0)} |
| Upheld | {appeal.get('upheld', 0)} |
| Overturned | {appeal.get('overturned', 0)} |
| Upheld Rate | {upheld_rate_pct}% |
{caution_section}
{matches_md}
---

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
    # Try short ID match first
    decision = None
    for cached_id, cached_decision in decision_cache.items():
        if cached_id.startswith(decision_id) or decision_id in cached_id:
            decision = cached_decision
            break

    if not decision:
        raise HTTPException(
            status_code=404,
            detail=f"Decision '{decision_id}' not found. Decisions are cached briefly. "
                   f"Re-run the decision and immediately request the report."
        )

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
async def get_report_json(decision_id: str):
    """
    Get decision report as structured JSON.

    Returns the same content as the HTML report but in JSON format,
    suitable for systems integration.
    """
    decision = None
    for cached_id, cached_decision in decision_cache.items():
        if cached_id.startswith(decision_id) or decision_id in cached_id:
            decision = cached_decision
            break

    if not decision:
        raise HTTPException(
            status_code=404,
            detail=f"Decision '{decision_id}' not found."
        )

    ctx = build_report_context(decision)

    return {
        "format": "json",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "report": ctx,
        "raw_decision": decision
    }


@router.get("/{decision_id}/markdown")
async def get_report_markdown(decision_id: str):
    """
    Generate a Markdown decision report.
    """
    decision = None
    for cached_id, cached_decision in decision_cache.items():
        if cached_id.startswith(decision_id) or decision_id in cached_id:
            decision = cached_decision
            break

    if not decision:
        raise HTTPException(
            status_code=404,
            detail=f"Decision '{decision_id}' not found."
        )

    ctx = build_report_context(decision)

    # Build transaction facts table
    facts_rows = ""
    for fact in ctx.get('transaction_facts', []):
        facts_rows += f"| {fact['field']} | `{fact['value']}` |\n"

    # Build gate1 sections
    gate1_rows = ""
    for section in ctx.get('gate1_sections', []):
        status = "PASS" if section.get('passed') else "FAIL"
        gate1_rows += f"| {section.get('name', 'N/A')} | {status} | {section.get('reason', '')} |\n"

    # Build gate2 sections
    gate2_rows = ""
    for section in ctx.get('gate2_sections', []):
        status = "PASS" if section.get('passed') else "REVIEW"
        gate2_rows += f"| {section.get('name', 'N/A')} | {status} | {section.get('reason', '')} |\n"

    # Build rules fired table
    rules_rows = ""
    for rule in ctx.get('rules_fired', []):
        rules_rows += f"| `{rule.get('code', 'N/A')}` | {rule.get('result', 'N/A')} | {rule.get('reason', '')} |\n"

    # Build evidence table
    evidence_rows = ""
    for ev in ctx.get('evidence_used', []):
        value = ev.get('value', 'N/A')
        if isinstance(value, bool):
            value = "Yes" if value else "No"
        evidence_rows += f"| `{ev.get('field', 'N/A')}` | {value} |\n"

    # Decision header
    if ctx['decision_status'] == "pass":
        decision_header = "### **PASS** — Transaction Allowed"
    elif ctx['decision_status'] == "escalate":
        decision_header = f"### **ESCALATE** — {ctx['action']}"
    else:
        decision_header = "### **REVIEW REQUIRED**"

    md = f"""# AML/KYC Decision Report

**Bank-Grade Dual-Gate Engine (Zero LLM)**

---

## Administrative Details

| Field | Value |
|-------|-------|
| Decision ID | `{ctx['decision_id_short']}...` |
| Case ID | `{ctx['case_id']}` |
| Timestamp | `{ctx['timestamp']}` |
| Jurisdiction | {ctx['jurisdiction']} |
| Engine Version | `{ctx['engine_version']}` |
| Policy Version | `{ctx['policy_version']}` |

---

## Transaction Facts

| Field | Value |
|-------|-------|
{facts_rows}

---

## Decision

{decision_header}

{ctx['decision_explainer']}

**STR Required:** {'Yes' if ctx['str_required'] else 'No'}

---

## Gate 1: Zero-False-Escalation

**Decision:** {'ALLOWED' if ctx['gate1_passed'] else 'BLOCKED'}

| Section | Status | Reason |
|---------|--------|--------|
{gate1_rows or "| No sections evaluated | - | - |"}

---

## Gate 2: STR Threshold

**STR Required:** {'Yes' if ctx['str_required'] else 'No'}

| Section | Status | Reason |
|---------|--------|--------|
{gate2_rows or "| No sections evaluated | - | - |"}

---

## Rules Evaluated

| Rule Code | Result | Reason |
|-----------|--------|--------|
{rules_rows or "| No rules evaluated | - | - |"}

---

{_build_precedent_markdown(ctx.get('precedent_analysis', {}))}

## Evidence Considered

| Field | Value |
|-------|-------|
{evidence_rows or "| No evidence recorded | - |"}

---

## Decision Provenance

| Field | Value |
|-------|-------|
| Decision Hash | `{ctx['decision_id']}` |
| Input Hash | `{ctx['input_hash']}` |
| Policy Hash | `{ctx['policy_hash']}` |
| Decision Path | `{ctx['decision_path_trace'] or 'N/A'}` |

This decision is cryptographically bound to the exact input and policy evaluated.

---

## Determinism & Auditability Statement

This decision was produced by a deterministic rule engine.
Re-evaluation using identical inputs and the same policy version will produce identical results.

The decision may be independently verified using the `/verify` endpoint.

---

{"## Regulatory Note" + chr(10) + chr(10) + "A Suspicious Transaction Report (STR) is required under PCMLTFA/FINTRAC guidelines." + chr(10) + "This report must be filed within 30 days of the suspicion being formed." + chr(10) + chr(10) + "---" + chr(10) if ctx['str_required'] else ''}

*DecisionGraph — Deterministic - Reproducible - Auditable*

*Generated {ctx['timestamp']}*
"""

    return {
        "decision_id": decision_id,
        "format": "markdown",
        "content": md,
        "generated_at": datetime.utcnow().isoformat() + "Z"
    }
