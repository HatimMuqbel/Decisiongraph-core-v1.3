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
    """Build template context matching the canonical Jinja2 template structure."""

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

    # Build claim facts list from unknown facts and evidence
    claim_facts = [
        {"key": "claim_id", "value": eval_data.claim_id},
        {"key": "policy_id", "value": eval_data.policy_pack_id},
        {"key": "certainty", "value": eval_data.certainty},
    ]
    if eval_data.unknown_facts:
        for fact in eval_data.unknown_facts[:3]:
            claim_facts.append({"key": fact, "value": "(unknown)"})

    # Build exclusions_requiring_evidence with .code for template chips
    exclusions_requiring_evidence = []
    for req in eval_data.exclusions_requiring_evidence:
        exclusions_requiring_evidence.append({
            "code": req.exclusion_code,
            "name": req.exclusion_name,
        })

    # Build exclusions_evaluated with .status for template pills
    exclusions_evaluated = []
    for exc in eval_data.exclusions_evaluated:
        if exc.triggered:
            status = "triggered"
        elif exc.code in eval_data.exclusions_uncertain:
            status = "requires_evidence"
        else:
            status = "not_applicable"

        exclusions_evaluated.append({
            "code": exc.code,
            "name": exc.name,
            "status": status,
            "reason": exc.reason if exc.triggered or exc.code in eval_data.exclusions_uncertain else None,
        })

    # Build evidence_requests with to_confirm/to_rule_out structure
    evidence_requests = []
    for req in eval_data.exclusions_requiring_evidence:
        # Split evidence items into confirm vs rule out
        # First half for confirm, second half for rule out (simplified logic)
        items = req.evidence_items
        mid = len(items) // 2 or 1
        evidence_requests.append({
            "exclusion_code": req.exclusion_code,
            "to_confirm": items[:mid],
            "to_rule_out": items[mid:] if len(items) > mid else [],
        })

    # Build reasoning_steps with step_id and outcome
    reasoning_steps = []
    for step in eval_data.reasoning_steps:
        reasoning_steps.append({
            "step_id": str(step.sequence),
            "description": step.description,
            "outcome": step.result.upper(),
        })

    # Build authority_citations with expected fields
    authority_citations = []
    for auth in eval_data.authorities_cited:
        authority_citations.append({
            "section_ref": auth.section,
            "authority_ref_id": f"{auth.authority_type}:{auth.title}",
            "excerpt_hash": auth.excerpt_hash or "N/A",
            "excerpt": auth.excerpt,
        })

    return {
        "request_id": eval_data.request_id,
        "evaluated_at": eval_data.evaluated_at,
        "engine_version": eval_data.engine_version,
        "memo_title": f"Claim Evaluation — {eval_data.claim_id}",
        "claim_facts": claim_facts,
        "decision_status": decision_status,
        "decision_note": decision_note,
        "decision_explainer": eval_data.disposition_reason,
        "exclusions_requiring_evidence": exclusions_requiring_evidence,
        "exclusions_evaluated": exclusions_evaluated,
        "evidence_requests": evidence_requests,
        "reasoning_steps": reasoning_steps,
        "authority_citations": authority_citations,
        "policy_pack_id": eval_data.policy_pack_id,
        "policy_pack_version": eval_data.policy_pack_version,
        "policy_pack_hash": eval_data.policy_pack_hash,
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
    - Clear decision status (APPROVE/DENY/REQUEST INFO)
    - Exclusions evaluated with status pills
    - Evidence requests (to confirm / to rule out)
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
        if exc["status"] == "triggered":
            status = "**TRIGGERED**"
        elif exc["status"] == "requires_evidence":
            status = "NEEDS EVIDENCE"
        else:
            status = "Not Applicable"
        exclusions_rows += f"| `{exc['code']}` | {exc['name']} | {status} |\n"

    # Build evidence requirements
    evidence_section = ""
    if ctx["evidence_requests"]:
        evidence_section = "\n## Evidence Requests\n\n"
        for req in ctx["evidence_requests"]:
            evidence_section += f"### {req['exclusion_code']}\n\n"
            if req.get("to_confirm"):
                evidence_section += "**To confirm:**\n"
                for item in req["to_confirm"]:
                    evidence_section += f"- {item}\n"
            if req.get("to_rule_out"):
                evidence_section += "\n**To rule out:**\n"
                for item in req["to_rule_out"]:
                    evidence_section += f"- {item}\n"
            evidence_section += "\n---\n"

    # Build reasoning chain
    reasoning_rows = ""
    for step in ctx["reasoning_steps"]:
        reasoning_rows += f"| {step['step_id']} | {step['description']} | {step['outcome']} |\n"

    md = f"""# Claim Evaluation Memorandum

**ClaimPilot — Deterministic Policy Engine (Zero LLM)**

---

| Field | Value |
|-------|-------|
| Request ID | `{ctx['request_id']}` |
| Evaluated At | `{ctx['evaluated_at']}` |
| Engine Version | `{ctx['engine_version']}` |

---

## Recommendation

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

| Step | Description | Outcome |
|------|-------------|---------|
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

*Generated by ClaimPilot {ctx['engine_version']} — Deterministic • Reproducible • Auditable*
"""

    return {
        "request_id": request_id,
        "format": "markdown",
        "content": md,
        "generated_at": datetime.utcnow().isoformat() + "Z"
    }
