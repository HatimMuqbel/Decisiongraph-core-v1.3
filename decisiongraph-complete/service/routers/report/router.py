"""Report router — endpoints only.

Pipeline: load → normalize → derive → view_model → render.
Router contains zero business logic.
"""

import re
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from datetime import datetime
from pathlib import Path

from .store import resolve, ALLOW_RAW_DECISION
from .pipeline import compile_report, compile_report_context

router = APIRouter(prefix="/report", tags=["Report"])

# Templates directory: service/templates/ (three levels up from this file)
_templates_dir = Path(__file__).parent.parent.parent / "templates"
_jinja = Jinja2Templates(directory=str(_templates_dir))
_jinja.env.auto_reload = True


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
        ctx = compile_report_context(decision)
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
    ctx = compile_report_context(decision)

    response = {
        "format": "json",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "report": ctx,
    }

    if include_raw and ALLOW_RAW_DECISION:
        response["raw_decision"] = _redact_decision(decision)

    return response


# ── Markdown ─────────────────────────────────────────────────────────────────

@router.get("/{decision_id}/markdown")
async def get_report_markdown(decision_id: str):
    """Generate a Markdown decision report."""
    decision = resolve(decision_id)
    md = compile_report(decision)

    return {
        "decision_id": decision_id,
        "format": "markdown",
        "content": md,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


# ── HTML Export (self-contained downloadable file) ────────────────────────────

_PRINT_BUTTON_HTML = (
    '<div style="position:fixed;bottom:20px;right:20px;z-index:9999;" class="no-print">'
    '<button onclick="window.print()" style="padding:10px 20px;border-radius:6px;'
    'border:1px solid #1f2937;background:#1f2937;color:#fff;font-size:13px;'
    'font-weight:600;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.15);">'
    'Print / Save PDF</button></div>'
)

_EXPORT_PRINT_CSS = (
    '<style class="export-print">'
    '@media print { .no-print { display:none !important; } }'
    '</style>'
)


@router.get("/{decision_id}/export-html")
async def export_html(request: Request, decision_id: str):
    """Download a self-contained HTML decision report file."""
    decision = resolve(decision_id)
    try:
        ctx = compile_report_context(decision)
        ctx["request"] = request
        template = _jinja.get_template("decision_report.html")
        html = template.render(ctx)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")

    # Strip the export toolbar (not useful inside a downloaded file)
    html = re.sub(
        r'<div class="export-bar">.*?</div>\s*',
        '',
        html,
        count=1,
        flags=re.DOTALL,
    )

    # Inject self-contained print button + print-hide CSS before </body>
    html = html.replace(
        '</body>',
        f'{_PRINT_BUTTON_HTML}\n{_EXPORT_PRINT_CSS}\n</body>',
    )

    # Build filename
    id_short = decision_id[:16] if decision_id else "unknown"
    ts = ctx.get("timestamp", "")
    date_part = ts[:10] if ts and len(ts) >= 10 else datetime.utcnow().strftime("%Y-%m-%d")
    filename = f"decision-report-{id_short}-{date_part}.html"

    return Response(
        content=html,
        media_type="text/html",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
