"""Report router — endpoints only.

Pipeline: load → normalize → derive → view_model → render.
Router contains zero business logic.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from pathlib import Path

from .store import resolve, ALLOW_RAW_DECISION
from .normalize import normalize_decision
from .derive import derive_regulatory_model
from .view_model import build_view_model
from .render_md import render_markdown

router = APIRouter(prefix="/report", tags=["Report"])

# Templates directory: service/templates/ (three levels up from this file)
_templates_dir = Path(__file__).parent.parent.parent / "templates"
_jinja = Jinja2Templates(directory=str(_templates_dir))


def _compile(decision: dict) -> dict:
    """Run the full report compiler pipeline.  Returns a ReportViewModel."""
    normalized = normalize_decision(decision)
    derived = derive_regulatory_model(normalized)
    return build_view_model(normalized, derived)


def _redact_decision(decision: dict) -> dict:
    meta = decision.get("meta", {}) or {}
    return {
        "meta": {
            "decision_id": meta.get("decision_id"),
            "case_id": meta.get("case_id"),
            "timestamp": meta.get("timestamp"),
            "jurisdiction": meta.get("jurisdiction"),
            "engine_version": meta.get("engine_version"),
            "policy_version": meta.get("policy_version"),
            "domain": meta.get("domain"),
            "input_hash": meta.get("input_hash"),
            "policy_hash": meta.get("policy_hash"),
        },
        "decision": decision.get("decision", {}),
        "gates": decision.get("gates", {}),
        "layers": decision.get("layers", {}),
        "rationale": decision.get("rationale", {}),
        "compliance": decision.get("compliance", {}),
        "evaluation_trace": decision.get("evaluation_trace", {}),
        "redacted": True,
    }


# ── HTML ─────────────────────────────────────────────────────────────────────

@router.get("/{decision_id}", response_class=HTMLResponse)
async def get_report_html(request: Request, decision_id: str):
    """Generate a regulator-grade HTML decision report."""
    decision = resolve(decision_id)
    try:
        ctx = _compile(decision)
        ctx["request"] = request
        return _jinja.TemplateResponse("decision_report.html", ctx)
    except Exception as e:
        error_html = (
            '<!DOCTYPE html><html><head><title>Report Error</title></head>'
            '<body style="font-family:sans-serif;padding:40px;max-width:600px;margin:0 auto;">'
            '<h1>Report Generation Error</h1>'
            f'<p>Could not generate report for decision: <code>{decision_id[:16]}...</code></p>'
            f'<p><strong>Error:</strong> {e}</p>'
            '<p><a href="/">Back to Demo</a></p></body></html>'
        )
        return HTMLResponse(content=error_html, status_code=500)


# ── JSON ─────────────────────────────────────────────────────────────────────

@router.get("/{decision_id}/json")
async def get_report_json(decision_id: str, include_raw: bool = False):
    """Get decision report as structured JSON."""
    decision = resolve(decision_id)
    ctx = _compile(decision)

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


# ── Markdown ─────────────────────────────────────────────────────────────────

@router.get("/{decision_id}/markdown")
async def get_report_markdown(decision_id: str):
    """Generate a Markdown decision report."""
    decision = resolve(decision_id)
    ctx = _compile(decision)
    md = render_markdown(ctx)

    return {
        "decision_id": decision_id,
        "format": "markdown",
        "content": md,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }
