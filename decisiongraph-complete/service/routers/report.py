"""Report generation endpoint for bank-grade AML/KYC decision reports.

Generates formal decision reports in multiple formats:
- HTML (suitable for printing/PDF)
- JSON (structured data for systems integration)
- Markdown (for documentation)

All formats produce regulator-grade, audit-safe output.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/report", tags=["Report"])

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
    meta = decision.get("meta", {})
    dec = decision.get("decision", {})
    gates = decision.get("gates", {})
    layers = decision.get("layers", {})
    rationale = decision.get("rationale", {})
    compliance = decision.get("compliance", {})

    # Determine verdict styling
    verdict = dec.get("verdict", "UNKNOWN")
    if verdict in ["PASS", "PASS_WITH_EDD"]:
        verdict_class = "pass"
        verdict_icon = "✓"
    elif verdict in ["HARD_STOP", "STR"]:
        verdict_class = "escalate"
        verdict_icon = "⚠"
    else:
        verdict_class = "review"
        verdict_icon = "?"

    # Build gate results
    gate1 = gates.get("gate1", {})
    gate2 = gates.get("gate2", {})

    gate1_sections = []
    for section_id, section_data in gate1.get("sections", {}).items():
        gate1_sections.append({
            "id": section_id,
            "name": section_data.get("name", section_id),
            "passed": section_data.get("passed", False),
            "reason": section_data.get("reason", "")
        })

    gate2_sections = []
    for section_id, section_data in gate2.get("sections", {}).items():
        gate2_sections.append({
            "id": section_id,
            "name": section_data.get("name", section_id),
            "passed": section_data.get("passed", False),
            "reason": section_data.get("reason", "")
        })

    # Build layer summaries
    layer_summaries = []
    layer_names = {
        "layer1_facts": "L1: Facts",
        "layer2_obligations": "L2: Obligations",
        "layer3_indicators": "L3: Indicators",
        "layer4_typologies": "L4: Typologies",
        "layer5_mitigations": "L5: Mitigations",
        "layer6_suspicion": "L6: Suspicion"
    }
    for layer_key, layer_name in layer_names.items():
        layer_data = layers.get(layer_key, {})
        layer_summaries.append({
            "name": layer_name,
            "data": layer_data
        })

    return {
        # Meta
        "decision_id": meta.get("decision_id", ""),
        "decision_id_short": meta.get("decision_id", "")[:16],
        "case_id": meta.get("case_id", ""),
        "input_hash": meta.get("input_hash", ""),
        "input_hash_short": meta.get("input_hash", "")[:16],
        "policy_hash": meta.get("policy_hash", ""),
        "policy_hash_short": meta.get("policy_hash", "")[:16],
        "engine_version": meta.get("engine_version", ""),
        "policy_version": meta.get("policy_version", ""),
        "jurisdiction": meta.get("jurisdiction", "CA"),
        "timestamp": meta.get("timestamp", datetime.utcnow().isoformat()),

        # Decision
        "verdict": verdict,
        "verdict_class": verdict_class,
        "verdict_icon": verdict_icon,
        "action": dec.get("action", ""),
        "escalation": dec.get("escalation", ""),
        "str_required": dec.get("str_required", "NO"),
        "path": dec.get("path"),
        "priority": dec.get("priority", ""),

        # Gates
        "gate1_decision": gate1.get("decision", ""),
        "gate1_sections": gate1_sections,
        "gate2_decision": gate2.get("decision", ""),
        "gate2_status": gate2.get("status", ""),
        "gate2_sections": gate2_sections,

        # Layers
        "layer_summaries": layer_summaries,

        # Rationale
        "summary": rationale.get("summary", ""),
        "non_escalation_justification": rationale.get("non_escalation_justification", ""),
        "absolute_rules_validated": rationale.get("absolute_rules_validated", []),
        "regulatory_citations": rationale.get("regulatory_citations", []),

        # Compliance
        "legislation": compliance.get("legislation", "PCMLTFA"),
        "fintrac_indicators": compliance.get("fintrac_indicators_matched", []),
    }


REPORT_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DecisionGraph - AML/KYC Decision Report</title>
  <style>
    :root {
      --fg: #111827; --muted: #6b7280; --border: #e5e7eb; --bg: #ffffff;
      --pass: #065f46; --pass-bg: #ecfdf5; --pass-border: #a7f3d0;
      --escalate: #991b1b; --escalate-bg: #fef2f2; --escalate-border: #fecaca;
      --review: #92400e; --review-bg: #fffbeb; --review-border: #fcd34d;
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      --sans: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
    }
    * { box-sizing: border-box; }
    body { margin: 0; padding: 24px; font-family: var(--sans); color: var(--fg); background: var(--bg); }
    .page { max-width: 900px; margin: 0 auto; }
    .header { text-align: center; padding-bottom: 20px; border-bottom: 2px solid var(--fg); margin-bottom: 24px; }
    .header h1 { font-size: 24px; margin: 0 0 4px 0; }
    .header .subtitle { color: var(--muted); font-size: 14px; }
    h2 { font-size: 16px; margin: 24px 0 12px 0; padding-bottom: 6px; border-bottom: 1px solid var(--border); }
    h3 { font-size: 14px; margin: 16px 0 8px 0; }
    .card { border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 16px; }
    .kv { display: grid; grid-template-columns: 180px 1fr; gap: 8px 16px; font-size: 14px; }
    .kv .label { color: var(--muted); }
    .kv .value { font-weight: 600; }
    .kv .value.mono { font-family: var(--mono); font-size: 13px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; margin: 12px 0; }
    th, td { text-align: left; padding: 10px 12px; border: 1px solid var(--border); vertical-align: top; }
    th { background: #f9fafb; font-size: 12px; color: var(--muted); text-transform: uppercase; }

    .verdict-box { border-radius: 12px; padding: 20px; margin: 16px 0; text-align: center; }
    .verdict-box.pass { background: var(--pass-bg); border: 2px solid var(--pass-border); }
    .verdict-box.escalate { background: var(--escalate-bg); border: 2px solid var(--escalate-border); }
    .verdict-box.review { background: var(--review-bg); border: 2px solid var(--review-border); }
    .verdict-box h2 { margin: 0 0 8px 0; border: none; padding: 0; font-size: 28px; }
    .verdict-box.pass h2 { color: var(--pass); }
    .verdict-box.escalate h2 { color: var(--escalate); }
    .verdict-box.review h2 { color: var(--review); }
    .verdict-box p { margin: 4px 0; font-size: 14px; }

    .pill { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; margin: 2px; }
    .pill.pass { background: var(--pass-bg); color: var(--pass); }
    .pill.fail { background: var(--escalate-bg); color: var(--escalate); }
    .pill.na { background: #f3f4f6; color: #374151; }

    .gate-section { background: #f9fafb; border-radius: 8px; padding: 12px; margin: 8px 0; }
    .gate-section .section-header { display: flex; align-items: center; gap: 8px; font-weight: 600; }
    .gate-section .section-reason { font-size: 13px; color: var(--muted); margin-top: 4px; }

    .provenance { background: #f9fafb; border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
    .provenance .hash { word-break: break-all; font-size: 12px; font-family: var(--mono); }
    .statement { background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 16px; margin: 16px 0; font-size: 14px; }
    .foot { margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--border); color: var(--muted); font-size: 12px; text-align: center; }

    @media print {
      body { padding: 12px; }
      .page { max-width: 100%; }
    }
  </style>
</head>
<body>
  <div class="page">
    <div class="header">
      <h1>AML/KYC Decision Report</h1>
      <div class="subtitle">DecisionGraph — Bank-Grade Dual-Gate Engine</div>
    </div>

    <h2>Decision Summary</h2>
    <div class="verdict-box {verdict_class}">
      <h2>{verdict_icon} {verdict}</h2>
      <p><strong>Action:</strong> {action}</p>
      <p><strong>STR Required:</strong> {str_required}</p>
      {path_html}
    </div>

    <h2>Administrative Details</h2>
    <div class="card">
      <div class="kv">
        <div class="label">Decision ID</div>
        <div class="value mono">{decision_id_short}...</div>
        <div class="label">Case ID</div>
        <div class="value mono">{case_id}</div>
        <div class="label">Timestamp</div>
        <div class="value mono">{timestamp}</div>
        <div class="label">Jurisdiction</div>
        <div class="value">{jurisdiction}</div>
        <div class="label">Engine Version</div>
        <div class="value mono">{engine_version}</div>
        <div class="label">Policy Version</div>
        <div class="value mono">{policy_version}</div>
      </div>
    </div>

    <h2>Gate 1: Zero-False-Escalation</h2>
    <div class="card">
      <p><strong>Decision:</strong> <span class="pill {gate1_class}">{gate1_decision}</span></p>
      {gate1_sections_html}
    </div>

    <h2>Gate 2: Positive STR</h2>
    <div class="card">
      <p><strong>Decision:</strong> <span class="pill {gate2_class}">{gate2_decision}</span> ({gate2_status})</p>
      {gate2_sections_html}
    </div>

    <h2>Rationale</h2>
    <div class="card">
      <p><strong>Summary:</strong> {summary}</p>
      {justification_html}
      {rules_html}
      {citations_html}
    </div>

    <h2>Provenance</h2>
    <div class="provenance">
      <div class="kv">
        <div class="label">Decision Hash</div>
        <div class="value mono hash">{decision_id}</div>
        <div class="label">Input Hash</div>
        <div class="value mono hash">{input_hash}</div>
        <div class="label">Policy Hash</div>
        <div class="value mono hash">{policy_hash}</div>
      </div>
      <p style="margin-top: 12px; font-size: 12px; color: var(--muted);">
        This decision is cryptographically bound to the exact input and policy evaluated.
      </p>
    </div>

    <div class="statement">
      <strong>Determinism & Auditability Statement</strong><br><br>
      This decision was produced by a deterministic rule engine.
      Re-evaluation using identical inputs and the same policy version will produce identical results.<br><br>
      The decision may be independently verified using the <code>/verify</code> endpoint.
    </div>

    <div class="foot">
      <strong>DecisionGraph</strong> — Bank-Grade AML/KYC Decision Engine<br>
      Generated {timestamp}
    </div>
  </div>
</body>
</html>
"""


@router.get("/{decision_id}", response_class=HTMLResponse)
async def get_report_html(decision_id: str):
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

    ctx = build_report_context(decision)

    # Build dynamic HTML parts
    path_html = f"<p><strong>Path:</strong> {ctx['path']}</p>" if ctx['path'] else ""

    gate1_class = "pass" if ctx['gate1_decision'] == "PROHIBITED" else "fail"
    gate2_class = "pass" if ctx['gate2_decision'] == "PROHIBITED" else "fail"

    # Gate 1 sections
    gate1_sections_html = ""
    for section in ctx['gate1_sections']:
        status = "✓" if section['passed'] else "✗"
        status_class = "pass" if section['passed'] else "fail"
        gate1_sections_html += f"""
        <div class="gate-section">
          <div class="section-header">
            <span class="pill {status_class}">{status}</span>
            <span>{section['id']}: {section['name']}</span>
          </div>
          <div class="section-reason">{section['reason']}</div>
        </div>
        """

    # Gate 2 sections
    gate2_sections_html = ""
    for section in ctx['gate2_sections']:
        status = "✓" if section['passed'] else "✗"
        status_class = "pass" if section['passed'] else "fail"
        gate2_sections_html += f"""
        <div class="gate-section">
          <div class="section-header">
            <span class="pill {status_class}">{status}</span>
            <span>{section['id']}: {section['name']}</span>
          </div>
          <div class="section-reason">{section['reason']}</div>
        </div>
        """

    # Rationale parts
    justification_html = ""
    if ctx['non_escalation_justification']:
        justification_html = f"<p><strong>Non-Escalation Justification:</strong> {ctx['non_escalation_justification']}</p>"

    rules_html = ""
    if ctx['absolute_rules_validated']:
        rules_html = "<p><strong>Absolute Rules Validated:</strong></p><ul>"
        for rule in ctx['absolute_rules_validated']:
            rules_html += f"<li>{rule}</li>"
        rules_html += "</ul>"

    citations_html = ""
    if ctx['regulatory_citations']:
        citations_html = f"<p><strong>Regulatory Citations:</strong> {', '.join(ctx['regulatory_citations'])}</p>"

    # Format the template
    html = REPORT_HTML_TEMPLATE.format(
        **ctx,
        path_html=path_html,
        gate1_class=gate1_class,
        gate2_class=gate2_class,
        gate1_sections_html=gate1_sections_html or "<p>No sections evaluated</p>",
        gate2_sections_html=gate2_sections_html or "<p>No sections evaluated</p>",
        justification_html=justification_html,
        rules_html=rules_html,
        citations_html=citations_html,
    )

    return HTMLResponse(content=html)


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

    # Build gate sections
    gate1_md = ""
    for section in ctx['gate1_sections']:
        status = "✓" if section['passed'] else "✗"
        gate1_md += f"| {section['id']} | {section['name']} | {status} | {section['reason']} |\n"

    gate2_md = ""
    for section in ctx['gate2_sections']:
        status = "✓" if section['passed'] else "✗"
        gate2_md += f"| {section['id']} | {section['name']} | {status} | {section['reason']} |\n"

    md = f"""# AML/KYC Decision Report

**DecisionGraph — Bank-Grade Dual-Gate Engine**

---

## Decision Summary

### **{ctx['verdict']}**

| Field | Value |
|-------|-------|
| Action | {ctx['action']} |
| STR Required | {ctx['str_required']} |
| Escalation | {ctx['escalation']} |
| Priority | {ctx['priority']} |

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

## Gate 1: Zero-False-Escalation

**Decision:** {ctx['gate1_decision']}

| Section | Name | Status | Reason |
|---------|------|--------|--------|
{gate1_md}

---

## Gate 2: Positive STR

**Decision:** {ctx['gate2_decision']} ({ctx['gate2_status']})

| Section | Name | Status | Reason |
|---------|------|--------|--------|
{gate2_md}

---

## Rationale

**Summary:** {ctx['summary']}

{f"**Non-Escalation Justification:** {ctx['non_escalation_justification']}" if ctx['non_escalation_justification'] else ""}

**Regulatory Citations:** {', '.join(ctx['regulatory_citations']) if ctx['regulatory_citations'] else 'N/A'}

---

## Provenance

| Field | Value |
|-------|-------|
| Decision Hash | `{ctx['decision_id']}` |
| Input Hash | `{ctx['input_hash']}` |
| Policy Hash | `{ctx['policy_hash']}` |

This decision is cryptographically bound to the exact input and policy evaluated.

---

## Determinism & Auditability Statement

This decision was produced by a deterministic rule engine.
Re-evaluation using identical inputs and the same policy version will produce identical results.

---

*DecisionGraph — Bank-Grade AML/KYC Decision Engine*

*Generated {ctx['timestamp']}*
"""

    return {
        "decision_id": decision_id,
        "format": "markdown",
        "content": md,
        "generated_at": datetime.utcnow().isoformat() + "Z"
    }
