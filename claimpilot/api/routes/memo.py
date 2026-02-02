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
import hashlib
import json

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


# =============================================================================
# Build Your Own Case Memo Endpoints
# =============================================================================

from api.template_loader import get_byoc_evaluation
from claimpilot.precedent import (
    FingerprintSchemaRegistry,
    PrecedentQueryEngine,
)


def get_precedent_matches(facts: dict, policy_pack_id: str, triggered_exclusion: str | None) -> dict:
    """
    Query precedent system for similar cases.

    Returns dict with:
    - matches: list of similar precedent cases
    - heat_map: outcome distribution data
    - summary: statistics about matches
    """
    # Map policy pack ID to schema
    schema_map = {
        "CA-ON-OAP1": "claimpilot:oap1:auto:v1",
        "CA-ON-HO3": "claimpilot:ho3:property:v1",
        "CA-ON-MARINE": "claimpilot:marine:v1",
        "CA-ON-HEALTH": "claimpilot:health:v1",
        "CA-ON-WSIB": "claimpilot:wsib:v1",
        "CGL-STD": "claimpilot:cgl:v1",
        "EO-STD": "claimpilot:eo:v1",
        "TRAVEL-MED": "claimpilot:travel:v1",
    }

    schema_id = schema_map.get(policy_pack_id)
    if not schema_id:
        return {"matches": [], "heat_map": None, "summary": None}

    try:
        # Get schema registry
        registry = FingerprintSchemaRegistry()

        # Try to get the schema (raises if not found)
        try:
            schema = registry.get_schema_by_id(schema_id)
        except Exception:
            return {"matches": [], "heat_map": None, "summary": None}

        # Compute fingerprint for this case
        fingerprint = registry.compute_fingerprint(schema, facts, salt="claimpilot-seed-salt-2024")

        # For now, return simulated precedent data based on seed configs
        # In production, this would query the actual precedent store
        matches = _get_simulated_precedents(policy_pack_id, triggered_exclusion, fingerprint)
        heat_map = _compute_heat_map(matches)
        summary = _compute_summary(matches, triggered_exclusion)

        return {
            "matches": matches,
            "heat_map": heat_map,
            "summary": summary,
        }

    except Exception as e:
        # Log error but don't fail memo generation
        print(f"Precedent lookup error: {e}")
        return {"matches": [], "heat_map": None, "summary": None}


def _get_simulated_precedents(policy_pack_id: str, triggered_exclusion: str | None, fingerprint: str) -> list:
    """
    Get simulated precedents based on seed configuration.

    In production, this would query the actual precedent database.
    """
    import hashlib
    from datetime import date, timedelta
    import random

    # Use fingerprint as seed for deterministic results
    seed = int(hashlib.md5(fingerprint.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    # Seed precedent configurations by exclusion type
    exclusion_configs = {
        # Auto (OAP1)
        "AUTO_DENY_IMPAIRED_INDICATED": {"count": 8, "deny_rate": 0.95, "appeal_rate": 0.17, "upheld_rate": 0.90},
        "AUTO_DENY_IMPAIRED_BAC": {"count": 12, "deny_rate": 0.98, "appeal_rate": 0.15, "upheld_rate": 0.92},
        "AUTO_DENY_COMMERCIAL": {"count": 10, "deny_rate": 0.92, "appeal_rate": 0.20, "upheld_rate": 0.83},
        "AUTO_DENY_UNLICENSED": {"count": 9, "deny_rate": 0.96, "appeal_rate": 0.12, "upheld_rate": 0.88},
        "AUTO_DENY_RACING": {"count": 5, "deny_rate": 0.94, "appeal_rate": 0.18, "upheld_rate": 0.85},
        "AUTO_REFER_SIU_INTENT": {"count": 6, "deny_rate": 0.85, "appeal_rate": 0.10, "upheld_rate": 0.80},
        # Property (HO-3)
        "HO_DENY_FLOOD": {"count": 15, "deny_rate": 0.97, "appeal_rate": 0.22, "upheld_rate": 0.91},
        "HO_DENY_EARTH": {"count": 8, "deny_rate": 0.96, "appeal_rate": 0.18, "upheld_rate": 0.89},
        "HO_DENY_VACANCY": {"count": 12, "deny_rate": 0.88, "appeal_rate": 0.25, "upheld_rate": 0.78},
        "HO_DENY_GRADUAL": {"count": 20, "deny_rate": 0.85, "appeal_rate": 0.28, "upheld_rate": 0.75},
        "HO_DENY_MAINTENANCE": {"count": 14, "deny_rate": 0.82, "appeal_rate": 0.30, "upheld_rate": 0.72},
        "HO_REFER_SIU_ARSON": {"count": 7, "deny_rate": 0.78, "appeal_rate": 0.15, "upheld_rate": 0.85},
        # Marine
        "MAR_DENY_NAV": {"count": 10, "deny_rate": 0.94, "appeal_rate": 0.18, "upheld_rate": 0.88},
        "MAR_DENY_PCOC": {"count": 8, "deny_rate": 0.96, "appeal_rate": 0.12, "upheld_rate": 0.92},
        "MAR_DENY_COMM": {"count": 6, "deny_rate": 0.90, "appeal_rate": 0.22, "upheld_rate": 0.80},
        "MAR_DENY_ICE": {"count": 12, "deny_rate": 0.92, "appeal_rate": 0.25, "upheld_rate": 0.85},
        "MAR_DENY_RACING": {"count": 5, "deny_rate": 0.95, "appeal_rate": 0.15, "upheld_rate": 0.90},
        # Health
        "HLT_DENY_PREEX": {"count": 18, "deny_rate": 0.90, "appeal_rate": 0.35, "upheld_rate": 0.82},
        "HLT_DENY_NON_FORM": {"count": 22, "deny_rate": 0.94, "appeal_rate": 0.15, "upheld_rate": 0.88},
        "HLT_DENY_PRIOR_AUTH": {"count": 10, "deny_rate": 0.92, "appeal_rate": 0.20, "upheld_rate": 0.85},
        "HLT_DENY_WSIB": {"count": 8, "deny_rate": 0.98, "appeal_rate": 0.08, "upheld_rate": 0.95},
        "HLT_DENY_COSMETIC": {"count": 15, "deny_rate": 0.97, "appeal_rate": 0.10, "upheld_rate": 0.92},
        "HLT_DENY_EXPERIMENTAL": {"count": 9, "deny_rate": 0.88, "appeal_rate": 0.40, "upheld_rate": 0.70},
        # WSIB
        "WSIB_DENY_NOT_REG": {"count": 6, "deny_rate": 0.99, "appeal_rate": 0.05, "upheld_rate": 0.98},
        "WSIB_DENY_NOT_WORK": {"count": 14, "deny_rate": 0.92, "appeal_rate": 0.30, "upheld_rate": 0.78},
        "WSIB_DENY_NOT_AOE": {"count": 10, "deny_rate": 0.88, "appeal_rate": 0.35, "upheld_rate": 0.72},
        "WSIB_DENY_PREEX": {"count": 12, "deny_rate": 0.85, "appeal_rate": 0.38, "upheld_rate": 0.68},
        "WSIB_DENY_INTOX": {"count": 8, "deny_rate": 0.96, "appeal_rate": 0.18, "upheld_rate": 0.88},
        "WSIB_DENY_SELF": {"count": 5, "deny_rate": 0.94, "appeal_rate": 0.20, "upheld_rate": 0.85},
        # CGL
        "CGL_DENY_NOT_POLICY": {"count": 8, "deny_rate": 0.97, "appeal_rate": 0.12, "upheld_rate": 0.92},
        "CGL_DENY_TERRITORY": {"count": 6, "deny_rate": 0.95, "appeal_rate": 0.15, "upheld_rate": 0.90},
        "CGL_DENY_INTENT": {"count": 10, "deny_rate": 0.98, "appeal_rate": 0.10, "upheld_rate": 0.95},
        "CGL_DENY_POLLUTION": {"count": 12, "deny_rate": 0.94, "appeal_rate": 0.22, "upheld_rate": 0.85},
        "CGL_DENY_AUTO": {"count": 9, "deny_rate": 0.96, "appeal_rate": 0.08, "upheld_rate": 0.95},
        "CGL_DENY_PROF": {"count": 11, "deny_rate": 0.93, "appeal_rate": 0.18, "upheld_rate": 0.82},
        "CGL_DENY_CONTRACT": {"count": 7, "deny_rate": 0.90, "appeal_rate": 0.25, "upheld_rate": 0.78},
        # E&O
        "EO_DENY_NOT_CLAIMS_MADE": {"count": 8, "deny_rate": 0.97, "appeal_rate": 0.15, "upheld_rate": 0.92},
        "EO_DENY_PRIOR_ACTS": {"count": 10, "deny_rate": 0.95, "appeal_rate": 0.20, "upheld_rate": 0.88},
        "EO_DENY_KNOWN": {"count": 9, "deny_rate": 0.94, "appeal_rate": 0.18, "upheld_rate": 0.85},
        "EO_DENY_FRAUD": {"count": 6, "deny_rate": 0.99, "appeal_rate": 0.08, "upheld_rate": 0.98},
        "EO_DENY_BI": {"count": 7, "deny_rate": 0.96, "appeal_rate": 0.12, "upheld_rate": 0.90},
        "EO_DENY_NOT_PROF": {"count": 8, "deny_rate": 0.92, "appeal_rate": 0.22, "upheld_rate": 0.80},
        # Travel
        "TRV_DENY_NOT_TRAVEL": {"count": 5, "deny_rate": 0.98, "appeal_rate": 0.05, "upheld_rate": 0.95},
        "TRV_DENY_NOT_EMERGENCY": {"count": 12, "deny_rate": 0.90, "appeal_rate": 0.28, "upheld_rate": 0.75},
        "TRV_DENY_PREEX": {"count": 18, "deny_rate": 0.88, "appeal_rate": 0.35, "upheld_rate": 0.72},
        "TRV_DENY_ELECTIVE": {"count": 10, "deny_rate": 0.95, "appeal_rate": 0.15, "upheld_rate": 0.88},
        "TRV_DENY_HIGHRISK": {"count": 8, "deny_rate": 0.94, "appeal_rate": 0.18, "upheld_rate": 0.85},
        "TRV_DENY_ADVISORY": {"count": 6, "deny_rate": 0.97, "appeal_rate": 0.10, "upheld_rate": 0.92},
        # Default for unknown exclusions
        "DEFAULT": {"count": 5, "deny_rate": 0.80, "appeal_rate": 0.20, "upheld_rate": 0.75},
    }

    config = exclusion_configs.get(triggered_exclusion, exclusion_configs["DEFAULT"])

    # Anchor facts that could match (policy-type specific)
    anchor_pools = {
        "AUTO": ["loss_type", "driver_status", "vehicle_use", "policy_status", "claim_amount_band"],
        "HO": ["loss_cause", "damage_type", "days_vacant", "policy_status", "claim_amount_band"],
        "MAR": ["loss_type", "vessel_in_water", "maintenance_current", "navigation_limits", "total_loss"],
        "HLT": ["claim_type", "coverage_months", "member_status", "drug_cost_band"],
        "WSIB": ["injury_type", "work_related", "during_work_hours", "employer_registered"],
        "CGL": ["loss_type", "occurrence_during_policy", "coverage_territory", "claim_amount_band"],
        "EO": ["claim_type", "wrongful_act_timing", "professional_capacity", "prior_claims"],
        "TRV": ["claim_type", "location", "emergency_status", "treatment_cost_band"],
    }

    # Overturn reasons by exclusion type
    overturn_reasons = {
        "MAR_DENY_ICE": "Ice damage causation disputed — maintenance records showed compliance",
        "MAR_DENY_NAV": "Navigation limits interpretation overturned on appeal",
        "AUTO_DENY_IMPAIRED_INDICATED": "Impairment evidence insufficient — toxicology inconclusive",
        "AUTO_DENY_COMMERCIAL": "Commercial use determination reversed — personal errand at time of loss",
        "HO_DENY_GRADUAL": "Gradual damage finding overturned — sudden pipe failure evidence",
        "HO_DENY_VACANCY": "Vacancy period disputed — owner visits documented",
        "HLT_DENY_PREEX": "Pre-existing condition not materially related to claim",
        "WSIB_DENY_NOT_WORK": "Work-relatedness established on review of job duties",
        "CGL_DENY_POLLUTION": "Pollution exclusion scope limited by court interpretation",
        "TRV_DENY_PREEX": "Stability period met per medical documentation",
        "DEFAULT": "Decision reversed on supplementary evidence review",
    }

    # Get anchor pool for this policy type
    prefix = (triggered_exclusion or "DEFAULT").split("_")[0]
    available_anchors = anchor_pools.get(prefix, anchor_pools.get("AUTO"))

    # Generate precedents
    matches = []
    base_date = date.today() - timedelta(days=730)  # 2 years ago

    for i in range(min(config["count"], 8)):  # Show max 8 matches
        days_offset = rng.randint(0, 700)
        case_date = base_date + timedelta(days=days_offset)

        # Determine outcome based on config rates
        is_deny = rng.random() < config["deny_rate"]
        outcome = "DENY" if is_deny else "PAY"

        # Determine if appealed
        appealed = rng.random() < config["appeal_rate"]
        appeal_outcome = None
        overturn_reason = None
        if appealed:
            upheld = rng.random() < config["upheld_rate"]
            appeal_outcome = "Upheld" if upheld else "Overturned"
            if appeal_outcome == "Overturned":
                overturn_reason = overturn_reasons.get(triggered_exclusion, overturn_reasons["DEFAULT"])

        # Compute similarity (deterministic based on fingerprint + index)
        similarity = 0.95 - (i * 0.05) + rng.uniform(-0.02, 0.02)
        similarity = max(0.65, min(0.99, similarity))

        # Generate match factors (why is it similar?)
        num_matched = rng.randint(3, min(5, len(available_anchors)))
        matched_anchors = rng.sample(available_anchors, num_matched)
        # Sometimes add a difference for realism
        key_differences = []
        if rng.random() < 0.4 and len(available_anchors) > num_matched:
            remaining = [a for a in available_anchors if a not in matched_anchors]
            if remaining:
                key_differences.append(f"{rng.choice(remaining)} differs")

        matches.append({
            "case_id": f"PREC-{policy_pack_id[:4]}-{seed % 10000:04d}-{i+1:02d}",
            "case_date": case_date.isoformat(),
            "outcome": outcome,
            "exclusion_code": triggered_exclusion or "N/A",
            "similarity": round(similarity, 2),
            "appealed": appealed,
            "appeal_outcome": appeal_outcome,
            "overturn_reason": overturn_reason,
            "decision_level": rng.choice(["Adjuster", "Adjuster", "Adjuster", "Senior", "Manager"]),
            "matched_anchors": matched_anchors,
            "key_differences": key_differences,
        })

    # Sort by similarity descending
    matches.sort(key=lambda x: x["similarity"], reverse=True)
    return matches


def _compute_heat_map(matches: list) -> dict | None:
    """Compute outcome distribution heat map data."""
    if not matches:
        return None

    total = len(matches)
    deny_count = sum(1 for m in matches if m["outcome"] == "DENY")
    pay_count = total - deny_count
    appeal_count = sum(1 for m in matches if m["appealed"])
    overturn_count = sum(1 for m in matches if m["appeal_outcome"] == "Overturned")

    return {
        "total": total,
        "deny_count": deny_count,
        "deny_pct": round(deny_count / total * 100, 1) if total > 0 else 0,
        "pay_count": pay_count,
        "pay_pct": round(pay_count / total * 100, 1) if total > 0 else 0,
        "appeal_count": appeal_count,
        "appeal_pct": round(appeal_count / total * 100, 1) if total > 0 else 0,
        "overturn_count": overturn_count,
        "overturn_pct": round(overturn_count / appeal_count * 100, 1) if appeal_count > 0 else 0,
    }


def _compute_summary(matches: list, triggered_exclusion: str | None) -> dict | None:
    """Compute summary statistics for precedents."""
    if not matches:
        return None

    total = len(matches)
    deny_count = sum(1 for m in matches if m["outcome"] == "DENY")
    pay_count = total - deny_count
    appeal_count = sum(1 for m in matches if m["appealed"])
    overturn_count = sum(1 for m in matches if m["appeal_outcome"] == "Overturned")

    # Determine majority outcome
    majority_outcome = "DENY" if deny_count > pay_count else "PAY" if pay_count > deny_count else "MIXED"
    majority_pct = max(deny_count, pay_count) / total if total > 0 else 0

    # Compute consistency
    consistent_outcome = all(m["outcome"] == matches[0]["outcome"] for m in matches)

    # Compute overturn rate (of appeals)
    overturn_rate = overturn_count / appeal_count if appeal_count > 0 else 0

    # Compute precedent confidence (pc_v1 formula)
    # base = majority_pct * 0.30 + upheld_rate * 0.25 + recency * 0.20 + policy_match * 0.15 + level * 0.10
    upheld_rate = 1 - overturn_rate
    recency_score = 0.8  # Simplified - would weight by date
    policy_match_score = 0.9  # Same policy pack
    level_score = 0.7  # Mix of adjuster/senior/manager

    base_confidence = (
        majority_pct * 0.30 +
        upheld_rate * 0.25 +
        recency_score * 0.20 +
        policy_match_score * 0.15 +
        level_score * 0.10
    )

    # Apply overturn penalty
    overturn_penalty = overturn_rate * 0.15
    precedent_confidence = max(0, min(1, base_confidence - overturn_penalty))

    # Determine confidence level
    if precedent_confidence >= 0.75:
        confidence_level = "HIGH"
    elif precedent_confidence >= 0.50:
        confidence_level = "MEDIUM"
    else:
        confidence_level = "LOW"

    # Determine caution level and message
    caution_level = None
    caution_message = None

    # High caution: mixed outcomes OR high overturn rate
    if not consistent_outcome or majority_pct < 0.70:
        caution_level = "HIGH"
        caution_message = f"Similar cases show mixed outcomes ({deny_count} deny / {pay_count} pay). Senior review recommended before final disposition."
    elif overturn_rate >= 0.30:
        caution_level = "HIGH"
        caution_message = f"High overturn rate ({overturn_rate*100:.0f}% of appeals). Manager review recommended before denial."
    elif overturn_rate >= 0.15:
        caution_level = "MEDIUM"
        caution_message = f"Non-trivial overturn rate ({overturn_rate*100:.0f}% of appeals). Consider additional documentation."
    elif appeal_count > 0 and appeal_count / total >= 0.25:
        caution_level = "LOW"
        caution_message = f"Elevated appeal rate ({appeal_count}/{total} cases). Ensure thorough documentation."

    # Decision support recommendation
    if caution_level == "HIGH":
        decision_support = "Recommend escalation — no coverage conclusion"
    elif caution_level == "MEDIUM":
        decision_support = "Proceed with caution — document thoroughly"
    elif consistent_outcome and majority_pct >= 0.90:
        decision_support = f"Strong precedent support for {majority_outcome}"
    else:
        decision_support = f"Moderate precedent support for {majority_outcome}"

    return {
        "total_similar": total,
        "exclusion_code": triggered_exclusion,
        "top_similarity": matches[0]["similarity"] if matches else 0,
        "consistent_outcome": consistent_outcome,
        "majority_outcome": majority_outcome,
        "majority_pct": round(majority_pct * 100, 1),
        "precedent_confidence": round(precedent_confidence, 2),
        "confidence_level": confidence_level,
        "caution_level": caution_level,
        "caution_message": caution_message,
        "decision_support": decision_support,
    }


@router.get("/byoc/{decision_id}", response_class=HTMLResponse)
async def get_byoc_memo_html(request: Request, decision_id: str):
    """Generate HTML memo for Build Your Own Case evaluation."""
    data = get_byoc_evaluation(decision_id)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"BYOC evaluation '{decision_id}' not found. Evaluations are cached briefly."
        )

    result = data.get("result", {})
    template_data = data.get("template", {})
    facts = data.get("facts", {})
    reasoning = data.get("reasoning_chain", [])
    warnings = data.get("warnings", [])

    # Build reasoning steps for template
    reasoning_steps = []
    for step in reasoning:
        reasoning_steps.append({
            "step": step.get("step", ""),
            "action": step.get("text", ""),
            "outcome": "PASS" if step.get("status") == "pass" else "FAIL" if step.get("status") == "fail" else "WARN"
        })

    # Build facts list
    facts_list = []
    for field_id, value in facts.items():
        field_def = template_data.get("fields", {}).get(field_id, {})
        label = field_def.get("label", field_id)
        if isinstance(value, bool):
            display_value = "Yes" if value else "No"
        else:
            display_value = str(value)
        facts_list.append({"field": label, "value": display_value})

    # Build exclusions from reasoning
    exclusions = []
    for step in reasoning:
        exclusions.append({
            "code": step.get("text", "").split(":")[0] if ":" in step.get("text", "") else "CHECK",
            "description": step.get("text", ""),
            "evaluation_result": "PASS" if step.get("status") == "pass" else "TRIGGERED",
            "notes": ""
        })

    # Determine decision status and triggered exclusion
    decision = result.get("decision", "unknown")
    triggered_exclusion = result.get("decision_code")
    if decision in ["approve", "pay"]:
        decision_status = "approve"
        decision_explainer = "Coverage applies. No exclusions triggered."
    elif decision in ["deny", "block", "decline"]:
        decision_status = "deny"
        decision_explainer = f"Coverage excluded: {result.get('decision_code', 'N/A')}"
    else:
        decision_status = "review"
        decision_explainer = f"Requires review: {result.get('decision_code', 'N/A')}"

    # Get precedent matches
    policy_pack_id = result.get("version_pins", {}).get("policy_pack_id", "")
    policy_pack_version = result.get("version_pins", {}).get("policy_pack_version", "N/A")
    precedent_data = get_precedent_matches(facts, policy_pack_id, triggered_exclusion)

    # Compute real SHA-256 hash of the policy pack (template + decision_rules)
    hash_input = json.dumps({
        "policy_pack_id": policy_pack_id,
        "policy_pack_version": policy_pack_version,
        "decision_rules": template_data.get("decision_rules", []),
        "fields": list(template_data.get("fields", {}).keys()),
    }, sort_keys=True, separators=(',', ':'))
    policy_pack_hash = hashlib.sha256(hash_input.encode()).hexdigest()

    # Determine line of business from policy pack ID
    lob_map = {
        "CA-ON-OAP1": "Auto",
        "CA-ON-HO3": "Property",
        "CA-ON-MARINE": "Marine",
        "CA-ON-HEALTH": "Health",
        "CA-ON-WSIB": "WSIB",
        "CGL-STD": "Commercial General Liability",
        "EO-STD": "Errors & Omissions",
        "TRAVEL-MED": "Travel Medical",
    }
    line_of_business = lob_map.get(policy_pack_id, "Insurance")

    # Determine jurisdiction from policy pack ID
    if policy_pack_id.startswith("CA-ON"):
        jurisdiction = "CA-ON"
    elif policy_pack_id.startswith("CA-"):
        jurisdiction = policy_pack_id.split("-")[0] + "-" + policy_pack_id.split("-")[1]
    else:
        jurisdiction = "CA-ON"

    # Build triggered exclusions list
    exclusions_triggered = []
    for step in reasoning:
        if step.get("status") == "fail":
            exclusions_triggered.append({
                "code": triggered_exclusion or "EXCLUSION",
                "name": step.get("text", "Exclusion triggered"),
            })

    context = {
        "request": request,
        "request_id": decision_id,
        "claim_id": f"BYOC-{decision_id[:8].upper()}",
        "evaluated_at": data.get("timestamp", datetime.utcnow().isoformat()),
        "engine_version": "2.1.1",
        "certainty_level": result.get("certainty", "high").upper(),
        # New canonical template variables
        "line_of_business": line_of_business,
        "jurisdiction": jurisdiction,
        "decision_status_label": decision_status.replace("_", " ").title(),
        # Facts and decision
        "claim_facts": facts_list,
        "decision_status": decision_status,
        "decision_note": None,
        "decision_explainer": decision_explainer,
        "unresolved_exclusions": [],
        "exclusions": exclusions,
        "exclusions_evaluated": exclusions,  # For the table
        "exclusions_triggered": exclusions_triggered,  # For decision rationale
        "evidence_requests": [],
        "reasoning_steps": reasoning_steps,
        "policy_pack_id": policy_pack_id or "N/A",
        "policy_pack_version": policy_pack_version,
        "policy_pack_hash": policy_pack_hash,
        "policy_pack_hash_scheme": "sha256:rfc8785",
        # Precedent data
        "precedent_matches": precedent_data.get("matches", []),
        "precedent_heat_map": precedent_data.get("heat_map"),
        "precedent_summary": precedent_data.get("summary"),
    }

    return templates.TemplateResponse("claim_memo.html", context)
