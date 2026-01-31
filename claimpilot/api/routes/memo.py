"""Memo generation endpoint for claim evaluation reports."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from datetime import datetime
from typing import Optional

from api.schemas.responses import EvaluateResponse

router = APIRouter(prefix="/memo", tags=["Memo"])

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


def generate_memo_html(eval_data: EvaluateResponse) -> str:
    """Generate HTML memo from evaluation response."""

    # Disposition styling
    if eval_data.recommended_disposition == "pay":
        disposition_text = "APPROVE"
        disposition_class = "disposition-approve"
        disposition_note = "Coverage applies. No exclusions triggered."
    elif eval_data.recommended_disposition == "deny":
        disposition_text = "DENY"
        disposition_class = "disposition-deny"
        disposition_note = f"Exclusion(s) triggered: {', '.join(eval_data.exclusions_triggered)}"
    else:
        disposition_text = "ADDITIONAL INFORMATION REQUIRED"
        disposition_class = "disposition-info"
        disposition_note = "Outstanding evidence required before final determination."

    # Build exclusions table
    exclusions_rows = ""
    for exc in eval_data.exclusions_evaluated:
        if exc.triggered:
            status = '<span class="status-triggered">Triggered</span>'
        elif exc.code in eval_data.exclusions_uncertain:
            status = '<span class="status-uncertain">Additional Evidence Required</span>'
        else:
            status = '<span class="status-clear">Not Applicable</span>'

        exclusions_rows += f"""
        <tr>
            <td><code>{exc.code}</code></td>
            <td>{exc.name}</td>
            <td>{status}</td>
        </tr>
        """

    # Build evidence requirements section
    evidence_section = ""
    if eval_data.exclusions_requiring_evidence:
        evidence_items = ""
        for req in eval_data.exclusions_requiring_evidence:
            items_list = "".join([f"<li>{item}</li>" for item in req.evidence_items])
            evidence_items += f"""
            <div class="evidence-requirement">
                <h4>{req.exclusion_code} — {req.exclusion_name}</h4>
                <p class="purpose">{req.purpose}</p>
                <p><strong>Required Evidence:</strong></p>
                <ul>{items_list}</ul>
                <p class="resolution">
                    <em>If applies:</em> {req.resolution_if_applies} |
                    <em>If not applicable:</em> {req.resolution_if_not_applies}
                </p>
            </div>
            """
        evidence_section = f"""
        <section class="evidence-section">
            <h3>Required Evidence to Finalize Evaluation</h3>
            {evidence_items}
        </section>
        """

    # Build reasoning chain
    reasoning_rows = ""
    for step in eval_data.reasoning_steps:
        result_class = "result-passed" if step.result == "passed" else "result-failed" if step.result == "failed" else "result-uncertain"
        reasoning_rows += f"""
        <tr>
            <td>{step.sequence}</td>
            <td>{step.step_type.replace('_', ' ').title()}</td>
            <td>{step.description}</td>
            <td class="{result_class}">{step.result.upper()}</td>
        </tr>
        """

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claim Evaluation Memorandum - {eval_data.request_id}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', system-ui, sans-serif;
            line-height: 1.6;
            color: #1a1a2e;
            background: #f8f9fa;
            padding: 2rem;
        }}
        .memo {{
            max-width: 900px;
            margin: 0 auto;
            background: white;
            padding: 3rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border-radius: 8px;
        }}
        .header {{
            border-bottom: 3px solid #1a1a2e;
            padding-bottom: 1.5rem;
            margin-bottom: 2rem;
        }}
        .header h1 {{
            font-size: 1.75rem;
            font-weight: 700;
            color: #1a1a2e;
        }}
        .header .subtitle {{
            color: #666;
            font-size: 0.9rem;
            margin-top: 0.25rem;
        }}
        .meta-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1rem;
            margin-bottom: 2rem;
            background: #f8f9fa;
            padding: 1.5rem;
            border-radius: 6px;
        }}
        .meta-item label {{
            font-size: 0.75rem;
            text-transform: uppercase;
            color: #666;
            letter-spacing: 0.05em;
        }}
        .meta-item p {{
            font-weight: 600;
            font-family: monospace;
            font-size: 0.95rem;
        }}
        .disposition {{
            padding: 1.5rem;
            border-radius: 8px;
            margin-bottom: 2rem;
        }}
        .disposition-approve {{ background: #d4edda; border-left: 4px solid #28a745; }}
        .disposition-deny {{ background: #f8d7da; border-left: 4px solid #dc3545; }}
        .disposition-info {{ background: #fff3cd; border-left: 4px solid #ffc107; }}
        .disposition h2 {{
            font-size: 1.5rem;
            margin-bottom: 0.5rem;
        }}
        .disposition p {{ color: #333; }}
        section {{ margin-bottom: 2rem; }}
        section h3 {{
            font-size: 1.1rem;
            color: #1a1a2e;
            border-bottom: 1px solid #ddd;
            padding-bottom: 0.5rem;
            margin-bottom: 1rem;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }}
        th, td {{
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        code {{
            background: #e9ecef;
            padding: 0.15rem 0.4rem;
            border-radius: 3px;
            font-size: 0.85rem;
        }}
        .status-triggered {{ color: #dc3545; font-weight: 600; }}
        .status-uncertain {{ color: #ffc107; font-weight: 600; }}
        .status-clear {{ color: #28a745; }}
        .result-passed {{ color: #28a745; font-weight: 600; }}
        .result-failed {{ color: #dc3545; font-weight: 600; }}
        .result-uncertain {{ color: #ffc107; font-weight: 600; }}
        .evidence-section {{
            background: #fff3cd;
            padding: 1.5rem;
            border-radius: 8px;
            border-left: 4px solid #ffc107;
        }}
        .evidence-requirement {{
            background: white;
            padding: 1rem;
            margin-top: 1rem;
            border-radius: 6px;
        }}
        .evidence-requirement h4 {{
            color: #856404;
            margin-bottom: 0.5rem;
        }}
        .evidence-requirement .purpose {{
            color: #666;
            font-style: italic;
            margin-bottom: 0.5rem;
        }}
        .evidence-requirement ul {{
            margin-left: 1.5rem;
            margin-bottom: 0.5rem;
        }}
        .evidence-requirement .resolution {{
            font-size: 0.85rem;
            color: #666;
        }}
        .provenance {{
            background: #f8f9fa;
            padding: 1.5rem;
            border-radius: 6px;
            margin-top: 2rem;
        }}
        .provenance h3 {{
            border: none;
            margin-bottom: 1rem;
        }}
        .provenance-grid {{
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 0.5rem 1rem;
            font-size: 0.9rem;
        }}
        .provenance-grid dt {{
            color: #666;
        }}
        .provenance-grid dd {{
            font-family: monospace;
        }}
        .determinism {{
            margin-top: 1.5rem;
            padding: 1rem;
            background: #e7f3ff;
            border-radius: 6px;
            text-align: center;
            font-size: 0.9rem;
            color: #004085;
        }}
        .footer {{
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid #ddd;
            text-align: center;
            font-size: 0.8rem;
            color: #666;
        }}
        @media print {{
            body {{ background: white; padding: 0; }}
            .memo {{ box-shadow: none; padding: 1rem; }}
        }}
    </style>
</head>
<body>
    <div class="memo">
        <header class="header">
            <h1>Claim Evaluation Memorandum</h1>
            <p class="subtitle">ClaimPilot Deterministic Evaluation Engine</p>
        </header>

        <div class="meta-grid">
            <div class="meta-item">
                <label>Request ID</label>
                <p>{eval_data.request_id}</p>
            </div>
            <div class="meta-item">
                <label>Claim ID</label>
                <p>{eval_data.claim_id}</p>
            </div>
            <div class="meta-item">
                <label>Policy ID</label>
                <p>{eval_data.policy_pack_id}</p>
            </div>
            <div class="meta-item">
                <label>Policy Version</label>
                <p>{eval_data.policy_pack_version}</p>
            </div>
            <div class="meta-item">
                <label>Evaluation Timestamp</label>
                <p>{eval_data.evaluated_at}</p>
            </div>
            <div class="meta-item">
                <label>Engine Version</label>
                <p>{eval_data.engine_version}</p>
            </div>
        </div>

        <div class="disposition {disposition_class}">
            <h2>Recommended Disposition: {disposition_text}</h2>
            <p>{eval_data.disposition_reason}</p>
        </div>

        <section>
            <h3>Exclusions Evaluated</h3>
            <table>
                <thead>
                    <tr>
                        <th>Code</th>
                        <th>Description</th>
                        <th>Evaluation Result</th>
                    </tr>
                </thead>
                <tbody>
                    {exclusions_rows}
                </tbody>
            </table>
        </section>

        {evidence_section}

        <section>
            <h3>Reasoning Chain</h3>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Step Type</th>
                        <th>Description</th>
                        <th>Result</th>
                    </tr>
                </thead>
                <tbody>
                    {reasoning_rows}
                </tbody>
            </table>
        </section>

        <div class="provenance">
            <h3>Policy Provenance</h3>
            <dl class="provenance-grid">
                <dt>Policy Pack ID</dt>
                <dd>{eval_data.policy_pack_id}</dd>
                <dt>Policy Version</dt>
                <dd>{eval_data.policy_pack_version}</dd>
                <dt>Policy Pack Hash</dt>
                <dd>{eval_data.policy_pack_hash}</dd>
            </dl>
            <div class="determinism">
                <strong>Determinism Statement:</strong> This recommendation is deterministic and reproducible.
                Re-evaluation with identical inputs will produce the same outcome.
            </div>
        </div>

        <footer class="footer">
            <p>Generated by ClaimPilot v{eval_data.engine_version} — Deterministic • Reproducible • Auditable</p>
            <p>This verification proves which policy rules were applied at evaluation time.</p>
        </footer>
    </div>
</body>
</html>
    """
    return html


def generate_memo_markdown(eval_data: EvaluateResponse) -> str:
    """Generate Markdown memo from evaluation response."""

    # Disposition text
    if eval_data.recommended_disposition == "pay":
        disposition_text = "**APPROVE**"
    elif eval_data.recommended_disposition == "deny":
        disposition_text = "**DENY**"
    else:
        disposition_text = "**ADDITIONAL INFORMATION REQUIRED**"

    # Build exclusions table
    exclusions_rows = ""
    for exc in eval_data.exclusions_evaluated:
        if exc.triggered:
            status = "Triggered"
        elif exc.code in eval_data.exclusions_uncertain:
            status = "Additional Evidence Required"
        else:
            status = "Not Applicable"
        exclusions_rows += f"| `{exc.code}` | {exc.name} | {status} |\n"

    # Build evidence requirements
    evidence_section = ""
    if eval_data.exclusions_requiring_evidence:
        evidence_section = "\n### Required Evidence to Finalize Evaluation\n\n"
        for req in eval_data.exclusions_requiring_evidence:
            items = "\n".join([f"- {item}" for item in req.evidence_items])
            evidence_section += f"""
**{req.exclusion_code} — {req.exclusion_name}**

*{req.purpose}*

{items}

*Resolution:* If applies → {req.resolution_if_applies} | If not applicable → {req.resolution_if_not_applies}

---
"""

    md = f"""# Claim Evaluation Memorandum

## Claim Identification

| Field | Value |
|-------|-------|
| Request ID | `{eval_data.request_id}` |
| Claim ID | `{eval_data.claim_id}` |
| Policy ID | `{eval_data.policy_pack_id}` |
| Policy Version | `{eval_data.policy_pack_version}` |
| Evaluation Timestamp | `{eval_data.evaluated_at}` |
| Engine Version | `{eval_data.engine_version}` |

---

## Recommended Disposition

{disposition_text}

{eval_data.disposition_reason}

---

## Exclusions Evaluated

| Code | Description | Evaluation Result |
|------|-------------|-------------------|
{exclusions_rows}
{evidence_section}

---

## Policy Provenance

| Field | Value |
|-------|-------|
| Policy Pack ID | `{eval_data.policy_pack_id}` |
| Policy Version | `{eval_data.policy_pack_version}` |
| Policy Pack Hash | `{eval_data.policy_pack_hash}` |

### Determinism Statement

This recommendation is deterministic and reproducible.
Re-evaluation with identical inputs will produce the same outcome.

---

*Generated by ClaimPilot v{eval_data.engine_version} — Deterministic • Reproducible • Auditable*

*This verification proves which policy rules were applied at evaluation time.*
"""
    return md


@router.get("/{request_id}", response_class=HTMLResponse)
async def get_memo_html(request_id: str):
    """
    Generate an HTML claim evaluation memo.

    Returns a formatted HTML document suitable for:
    - Printing
    - PDF generation
    - Email attachments
    - Audit records
    """
    eval_data = get_cached_evaluation(request_id)
    if not eval_data:
        raise HTTPException(
            status_code=404,
            detail=f"Evaluation '{request_id}' not found. Evaluations are cached briefly for memo generation."
        )

    return generate_memo_html(eval_data)


@router.get("/{request_id}/markdown")
async def get_memo_markdown(request_id: str):
    """
    Generate a Markdown claim evaluation memo.

    Returns a formatted Markdown document.
    """
    eval_data = get_cached_evaluation(request_id)
    if not eval_data:
        raise HTTPException(
            status_code=404,
            detail=f"Evaluation '{request_id}' not found. Evaluations are cached briefly for memo generation."
        )

    return {
        "request_id": request_id,
        "format": "markdown",
        "content": generate_memo_markdown(eval_data),
        "generated_at": datetime.utcnow().isoformat() + "Z"
    }
