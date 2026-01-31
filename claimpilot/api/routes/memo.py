"""Memo generation endpoint for claim evaluation reports.

Generates formal claim evaluation memoranda in multiple formats:
- HTML (suitable for printing/PDF via browser or tools like WeasyPrint)
- JSON (structured data for case management system integration)
- Markdown (for documentation)
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from pathlib import Path
from typing import Optional

from api.schemas.responses import EvaluateResponse

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
    """Build template context from evaluation response."""

    # Determine decision status
    if eval_data.recommended_disposition == "pay":
        decision_status = "approve"
        decision_note = None
        if eval_data.requires_authority:
            decision_note = f"Requires {eval_data.required_role} approval"
    elif eval_data.recommended_disposition == "deny":
        decision_status = "deny"
        decision_note = None
    else:
        decision_status = "request_info"
        decision_note = "Outstanding evidence required"

    # Build claim facts list
    claim_facts = []
    for step in eval_data.reasoning_steps:
        if step.step_type == "coverage_check":
            claim_facts.append({"key": "coverage_check", "value": step.result})

    return {
        "request_id": eval_data.request_id,
        "claim_id": eval_data.claim_id,
        "evaluated_at": eval_data.evaluated_at,
        "engine_version": eval_data.engine_version,
        "memo_title": f"Claim Evaluation — {eval_data.claim_id}",
        "policy_pack_id": eval_data.policy_pack_id,
        "policy_pack_version": eval_data.policy_pack_version,
        "policy_pack_hash": eval_data.policy_pack_hash,
        "loss_type": "Collision",  # Would come from request in full implementation
        "claim_facts": claim_facts,
        "decision_status": decision_status,
        "decision_note": decision_note,
        "decision_explainer": eval_data.disposition_reason,
        "exclusions_evaluated": [exc.model_dump() for exc in eval_data.exclusions_evaluated],
        "exclusions_uncertain": eval_data.exclusions_uncertain,
        "exclusions_requiring_evidence": [req.model_dump() for req in eval_data.exclusions_requiring_evidence],
        "reasoning_steps": [step.model_dump() for step in eval_data.reasoning_steps],
        "authorities_cited": [auth.model_dump() for auth in eval_data.authorities_cited],
        "verification": None,  # Would be populated if pre-verified
    }


@router.get("/{request_id}", response_class=HTMLResponse)
async def get_memo_html(request: Request, request_id: str):
    """
    Generate an HTML claim evaluation memo using Jinja2 template.

    Returns a formatted HTML document suitable for:
    - Printing (print-optimized CSS)
    - PDF generation (WeasyPrint, Playwright, wkhtmltopdf)
    - Email attachments
    - Audit records

    The template follows regulator-style formatting with:
    - Clear decision status (APPROVE/DENY/ADDITIONAL INFO REQUIRED)
    - Exclusions evaluated with status pills
    - Evidence requirements for uncertain exclusions
    - Reasoning chain
    - Policy provenance with hash verification
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

    The JSON structure matches the HTML memo exactly.
    """
    eval_data = get_cached_evaluation(request_id)
    if not eval_data:
        raise HTTPException(
            status_code=404,
            detail=f"Evaluation '{request_id}' not found."
        )

    context = build_memo_context(eval_data)
    # Remove request object (not serializable)
    context.pop("request", None)

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

    # Build exclusions table
    exclusions_rows = ""
    for exc in ctx["exclusions_evaluated"]:
        if exc["triggered"]:
            status = "**TRIGGERED**"
        elif exc["code"] in ctx["exclusions_uncertain"]:
            status = "NEEDS EVIDENCE"
        else:
            status = "Not Applicable"
        exclusions_rows += f"| `{exc['code']}` | {exc['name']} | {status} |\n"

    # Build evidence requirements
    evidence_section = ""
    if ctx["exclusions_requiring_evidence"]:
        evidence_section = "\n## Required Evidence to Finalize Evaluation\n\n"
        for req in ctx["exclusions_requiring_evidence"]:
            items = "\n".join([f"- {item}" for item in req["evidence_items"]])
            evidence_section += f"""
### {req['exclusion_code']} — {req['exclusion_name']}

*{req['purpose']}*

{items}

**Resolution:** If applies → {req['resolution_if_applies']} | If not applicable → {req['resolution_if_not_applies']}

---
"""

    # Build reasoning chain
    reasoning_rows = ""
    for step in ctx["reasoning_steps"]:
        reasoning_rows += f"| {step['sequence']} | {step['description']} | {step['result'].upper()} |\n"

    md = f"""# Claim Evaluation Memorandum

**ClaimPilot — Deterministic Policy Engine (Zero LLM)**

---

## Claim Identification

| Field | Value |
|-------|-------|
| Request ID | `{ctx['request_id']}` |
| Claim ID | `{ctx['claim_id']}` |
| Policy ID | `{ctx['policy_pack_id']}` |
| Policy Version | `{ctx['policy_pack_version']}` |
| Evaluation Timestamp | `{ctx['evaluated_at']}` |
| Engine Version | `{ctx['engine_version']}` |

---

## Recommended Disposition

**{ctx['decision_status'].upper()}**{f" — {ctx['decision_note']}" if ctx['decision_note'] else ""}

{ctx['decision_explainer']}

---

## Exclusions Evaluated

| Code | Description | Result |
|------|-------------|--------|
{exclusions_rows}
{evidence_section}

---

## Reasoning Chain

| Step | Description | Result |
|------|-------------|--------|
{reasoning_rows}

---

## Policy Provenance

| Field | Value |
|-------|-------|
| Policy Pack ID | `{ctx['policy_pack_id']}` |
| Policy Version | `{ctx['policy_pack_version']}` |
| Policy Pack Hash | `{ctx['policy_pack_hash']}` |

### Determinism Statement

This recommendation is **deterministic and reproducible**.
Re-evaluating with identical inputs produces identical outputs.

---

### Regulatory Alignment

Controls align with:
- **OSFI E-23** — Model risk management
- **FSRA** — Fair consumer outcome expectations
- **NAIC** — AI governance principles

---

*Generated by ClaimPilot {ctx['engine_version']} — Deterministic • Reproducible • Auditable*

*This verification proves which policy rules were applied at evaluation time.*
"""

    return {
        "request_id": request_id,
        "format": "markdown",
        "content": md,
        "generated_at": datetime.utcnow().isoformat() + "Z"
    }
