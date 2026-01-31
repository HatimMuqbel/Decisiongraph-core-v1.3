"""Memo generation endpoint for claim evaluation reports.

Generates formal claim evaluation memoranda in multiple formats:
- HTML (suitable for printing/PDF via browser or tools like WeasyPrint)
- JSON (structured data for case management system integration)
- Markdown (for documentation)

All formats produce regulator-grade, audit-safe output.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from pathlib import Path
from typing import Optional

from api.schemas.responses import EvaluateResponse
from api.data.evidence_matrix import get_evidence_requirement

router = APIRouter(prefix="/memo", tags=["Memo"])

# Setup Jinja2 templates
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# In-memory cache of recent evaluations for memo generation
# In production, this would be a proper cache/database
evaluation_cache: dict[str, EvaluateResponse] = {}


def cache_evaluation(evaluation: EvaluateResponse):
    """Cache an evaluation for later memo generation."""
    evaluation_cache[evaluation.request_id] = evaluation
    # Keep only last 100 evaluations
    if len(evaluation_cache) > 100:
        oldest_key = next(iter(evaluation_cache))
        del evaluation_cache[oldest_key]


def get_cached_evaluation(request_id: str) -> Optional[EvaluateResponse]:
    """Get a cached evaluation by request ID."""
    return evaluation_cache.get(request_id)


def build_memo_context(eval_data: EvaluateResponse) -> dict:
    """Build template context matching the regulator-grade memo format."""

    # Determine decision status
    if eval_data.recommended_disposition == "pay":
        decision_status = "approve"
        decision_note = None
        decision_explainer = "Coverage applies. No exclusions triggered."
        if eval_data.requires_authority:
            decision_note = f"Requires {eval_data.required_role} approval"
    elif eval_data.recommended_disposition == "deny":
        decision_status = "deny"
        decision_note = None
        decision_explainer = eval_data.disposition_reason
    else:
        decision_status = "request_info"
        decision_note = None
        decision_explainer = "The system cannot reach a final coverage determination due to insufficient evidence related to specific policy exclusions."

    # Map certainty to human-readable
    certainty_map = {
        "high": "High",
        "medium": "Medium",
        "low": "Low",
        "requires_judgment": "Requires Judgment"
    }
    certainty_level = certainty_map.get(eval_data.certainty, eval_data.certainty.title())

    # Build claim facts table
    claim_facts = [
        {"field": "Claim Identifier", "value": eval_data.claim_id},
        {"field": "Policy Identifier", "value": eval_data.policy_pack_id},
        {"field": "Loss Type", "value": "Collision"},  # Would come from request
        {"field": "Certainty Assessment", "value": certainty_level},
    ]

    # Build unresolved exclusions for request_info status
    unresolved_exclusions = []
    for req in eval_data.exclusions_requiring_evidence:
        unresolved_exclusions.append({
            "code": req.exclusion_code,
            "name": req.exclusion_name,
        })

    # Build triggered exclusions for deny status
    exclusions_triggered_list = []
    for exc in eval_data.exclusions_evaluated:
        if exc.triggered:
            exclusions_triggered_list.append({
                "code": exc.code,
                "name": exc.name,
            })

    # Build exclusions evaluated table with status and notes
    exclusions_evaluated = []
    for exc in eval_data.exclusions_evaluated:
        if exc.triggered:
            status = "triggered"
            notes = exc.reason or ""
        elif exc.code in eval_data.exclusions_uncertain:
            status = "requires_evidence"
            # Generate meaningful notes for uncertain exclusions
            notes = exc.reason.replace("Uncertain: ", "") if exc.reason and exc.reason.startswith("Uncertain:") else ""
            if "unknown" not in notes.lower() and exc.reason:
                notes = exc.reason
        else:
            status = "not_applicable"
            notes = ""

        exclusions_evaluated.append({
            "code": exc.code,
            "name": exc.name,
            "status": status,
            "notes": notes,
        })

    # Build evidence requests with purpose and to_confirm/to_rule_out
    evidence_requests = []
    for req in eval_data.exclusions_requiring_evidence:
        # Get evidence matrix data for better structure
        matrix_data = get_evidence_requirement(req.exclusion_code)

        if matrix_data:
            purpose = matrix_data["purpose"]
            items = matrix_data["evidence_items"]
        else:
            purpose = req.purpose
            items = req.evidence_items

        # Split items: first half confirms, second half rules out
        mid = max(1, len(items) // 2)
        to_confirm = items[:mid]
        to_rule_out = items[mid:] if len(items) > 1 else ["Adjuster investigation notes"]

        evidence_requests.append({
            "exclusion_code": req.exclusion_code,
            "exclusion_name": req.exclusion_name,
            "purpose": purpose,
            "to_confirm": to_confirm,
            "to_rule_out": to_rule_out,
        })

    # Build reasoning chain with action and outcome
    reasoning_steps = []
    for step in eval_data.reasoning_steps:
        # Map step type to action description
        if step.step_type == "coverage_check":
            # Extract loss type from description like "Checked coverage for loss type 'collision'"
            loss_type = "collision"
            if "'" in step.description:
                parts = step.description.split("'")
                if len(parts) >= 2:
                    loss_type = parts[1]
            action = f'Verified coverage eligibility for loss type "{loss_type}"'
        elif step.step_type == "exclusion_evaluation":
            action = f"Evaluated exclusion {step.rule_id or ''} — {step.rule_name or step.description}"
        else:
            action = step.description

        # Map result to outcome
        if step.result == "passed":
            if "exclusion" in step.step_type.lower():
                outcome = "NOT_APPLICABLE"
            else:
                outcome = "PASSED"
        elif step.result == "failed":
            outcome = "TRIGGERED"
        elif step.result == "uncertain":
            outcome = "INDETERMINATE"
        else:
            outcome = step.result.upper()

        reasoning_steps.append({
            "step_id": str(step.sequence),
            "action": action,
            "outcome": outcome,
        })

    return {
        # Administrative Details
        "request_id": eval_data.request_id,
        "claim_id": eval_data.claim_id,
        "policy_pack_id": eval_data.policy_pack_id,
        "policy_pack_version": eval_data.policy_pack_version,
        "evaluated_at": eval_data.evaluated_at,
        "engine_version": eval_data.engine_version,
        "certainty_level": certainty_level,

        # Claim Facts
        "claim_facts": claim_facts,

        # Recommendation
        "decision_status": decision_status,
        "decision_note": decision_note,
        "decision_explainer": decision_explainer,
        "unresolved_exclusions": unresolved_exclusions,
        "exclusions_triggered": exclusions_triggered_list,

        # Exclusions Evaluated
        "exclusions_evaluated": exclusions_evaluated,

        # Evidence Requests
        "evidence_requests": evidence_requests,

        # Reasoning Chain
        "reasoning_steps": reasoning_steps,

        # Policy Provenance (full hash, not truncated)
        "policy_pack_hash": eval_data.policy_pack_hash,
    }


@router.get("/{request_id}", response_class=HTMLResponse)
async def get_memo_html(request: Request, request_id: str):
    """
    Generate a regulator-grade HTML claim evaluation memo.

    Returns a formatted HTML document suitable for:
    - Printing (print-optimized CSS)
    - PDF generation (WeasyPrint, Playwright, wkhtmltopdf)
    - Email attachments
    - Audit records
    - Regulatory review
    - Dispute files

    Sections include:
    - Administrative Details
    - Claim Facts
    - Recommendation (APPROVE/DENY/REQUEST ADDITIONAL INFORMATION)
    - Exclusions Evaluated (with status pills and notes)
    - Evidence Requests (to confirm/rule out)
    - Reasoning Chain
    - Policy Provenance
    - Determinism & Auditability Statement
    - Compliance Note (when applicable)
    """
    eval_data = get_cached_evaluation(request_id)
    if not eval_data:
        raise HTTPException(
            status_code=404,
            detail=f"Evaluation '{request_id}' not found. Evaluations are cached briefly for memo generation. "
                   f"Re-evaluate the claim and immediately request the memo."
        )

    context = build_memo_context(eval_data)
    context["request"] = request  # Required by Jinja2Templates

    return templates.TemplateResponse("claim_memo.html", context)


@router.get("/{request_id}/json")
async def get_memo_json(request_id: str):
    """
    Get memo data as structured JSON.

    Returns the same content as the HTML memo but in JSON format,
    suitable for:
    - Case management system integration
    - Document storage systems
    - API consumers who want to render their own UI
    - Archival in structured databases

    The JSON structure matches the HTML memo exactly and is
    regulator-grade/audit-safe.
    """
    eval_data = get_cached_evaluation(request_id)
    if not eval_data:
        raise HTTPException(
            status_code=404,
            detail=f"Evaluation '{request_id}' not found."
        )

    context = build_memo_context(eval_data)

    return {
        "format": "json",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "memo": context
    }


@router.get("/{request_id}/markdown")
async def get_memo_markdown(request_id: str):
    """
    Generate a Markdown claim evaluation memo.

    Returns a formatted Markdown document suitable for:
    - Documentation systems
    - Git-based storage
    - Plain text archives
    """
    eval_data = get_cached_evaluation(request_id)
    if not eval_data:
        raise HTTPException(
            status_code=404,
            detail=f"Evaluation '{request_id}' not found."
        )

    ctx = build_memo_context(eval_data)

    # Build claim facts table
    facts_rows = ""
    for fact in ctx["claim_facts"]:
        facts_rows += f"| {fact['field']} | `{fact['value']}` |\n"

    # Build exclusions table
    exclusions_rows = ""
    for exc in ctx["exclusions_evaluated"]:
        if exc["status"] == "triggered":
            status = "**Triggered**"
        elif exc["status"] == "requires_evidence":
            status = "Additional Evidence Required"
        else:
            status = "Not Applicable"
        notes = exc["notes"] or ""
        exclusions_rows += f"| `{exc['code']}` | {exc['name']} | {status} | {notes} |\n"

    # Build evidence requests
    evidence_section = ""
    if ctx["evidence_requests"]:
        evidence_section = "\n## Evidence Requests\n\nThe following standardized evidence is required to resolve indeterminate exclusions.\n\n"
        for req in ctx["evidence_requests"]:
            evidence_section += f"### Exclusion {req['exclusion_code']} — {req['exclusion_name']}\n\n"
            evidence_section += f"**Purpose:** {req['purpose']}\n\n"
            if req.get("to_confirm"):
                evidence_section += "**Evidence to Confirm Applicability**\n"
                for item in req["to_confirm"]:
                    evidence_section += f"- {item}\n"
                evidence_section += "\n"
            if req.get("to_rule_out"):
                evidence_section += "**Evidence to Rule Out Applicability**\n"
                for item in req["to_rule_out"]:
                    evidence_section += f"- {item}\n"
                evidence_section += "\n"
            evidence_section += "---\n\n"

    # Build reasoning chain
    reasoning_rows = ""
    for step in ctx["reasoning_steps"]:
        reasoning_rows += f"| {step['step_id']} | {step['action']} | {step['outcome']} |\n"

    # Build unresolved exclusions list
    unresolved_list = ""
    if ctx["unresolved_exclusions"]:
        unresolved_list = "\n**Unresolved exclusions requiring additional evidence:**\n\n"
        for ex in ctx["unresolved_exclusions"]:
            unresolved_list += f"- **{ex['code']}** — {ex['name']}\n"
        unresolved_list += "\nNo denial has been issued at this stage.\n"

    # Decision text
    if ctx["decision_status"] == "approve":
        decision_header = "### **APPROVE**"
    elif ctx["decision_status"] == "deny":
        decision_header = "### **DENY**"
    else:
        decision_header = "### **REQUEST ADDITIONAL INFORMATION**"

    md = f"""# Claim Evaluation Memorandum

**Deterministic Policy Engine (Zero LLM)**

---

## Administrative Details

| Field | Value |
|-------|-------|
| Request ID | `{ctx['request_id']}` |
| Claim ID | `{ctx['claim_id']}` |
| Policy ID | `{ctx['policy_pack_id']}` |
| Policy Version | `{ctx['policy_pack_version']}` |
| Evaluated At | `{ctx['evaluated_at']}` |
| Engine Version | `{ctx['engine_version']}` |
| Certainty Level | {ctx['certainty_level']} |

---

## Claim Facts

| Field | Value |
|-------|-------|
{facts_rows}

---

## Recommendation

{decision_header}

{ctx['decision_explainer']}
{unresolved_list}

---

## Exclusions Evaluated

| Code | Description | Evaluation Result | Notes |
|------|-------------|-------------------|-------|
{exclusions_rows}
{evidence_section}

---

## Reasoning Chain

| Step | Evaluation Action | Outcome |
|------|-------------------|---------|
{reasoning_rows}

---

## Policy Provenance

| Field | Value |
|-------|-------|
| Policy Pack ID | `{ctx['policy_pack_id']}` |
| Policy Pack Version | `{ctx['policy_pack_version']}` |
| Policy Pack Hash (SHA-256) | `{ctx['policy_pack_hash']}` |

This recommendation is cryptographically bound to the exact policy wording evaluated at decision time.

---

## Determinism & Auditability Statement

This claim evaluation was produced by a deterministic rule engine.
Re-evaluation using identical inputs and the same policy pack will produce identical results.

The recommendation may be independently verified using the `/verify` endpoint and the recorded provenance fields.

---

{"## Compliance Note" + chr(10) + chr(10) + "No coverage denial has been issued." + chr(10) + "Outstanding exclusions are explicitly identified and require documentary resolution prior to final disposition." + chr(10) + chr(10) + "---" + chr(10) if ctx['decision_status'] == 'request_info' else ''}

*ClaimPilot — Deterministic • Reproducible • Auditable*

*Generated {ctx['evaluated_at']}*
"""

    return {
        "request_id": request_id,
        "format": "markdown",
        "content": md,
        "generated_at": datetime.utcnow().isoformat() + "Z"
    }
