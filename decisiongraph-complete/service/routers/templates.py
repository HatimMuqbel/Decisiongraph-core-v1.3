"""
Templates routes for Build Your Own Case feature.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any


router = APIRouter(prefix="/templates", tags=["Templates"])

# Module-level reference to template loader
_template_loader = None


def set_loader(loader):
    """Set the template loader from main app."""
    global _template_loader
    _template_loader = loader


class TemplateEvaluateRequest(BaseModel):
    """Request to evaluate facts against a template."""
    template_id: str
    facts: dict[str, Any]
    evidence: dict[str, str] = {}  # doc_id -> "missing" | "provided" | "verified"


@router.get("")
async def list_templates():
    """
    List all available case templates.

    Returns summary info for each template (Transaction Monitoring, KYC Onboarding, PEP/Sanctions Screening).
    """
    if not _template_loader:
        raise HTTPException(status_code=500, detail="Template loader not initialized")

    return _template_loader.list_templates()


@router.get("/{template_id}")
async def get_template(template_id: str):
    """
    Get a specific template with all fields for UI rendering.

    Returns field definitions, groups, visibility rules, evidence requirements.
    """
    if not _template_loader:
        raise HTTPException(status_code=500, detail="Template loader not initialized")

    template = _template_loader.get_template_for_ui(template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")

    return template


@router.post("/evaluate")
async def evaluate_template(request: TemplateEvaluateRequest):
    """
    Evaluate facts against a template's decision rules.

    This is for the Build Your Own Case feature where users configure
    AML/KYC scenarios using dropdowns/toggles and see the resulting decision.

    Request body:
    - template_id: Template to evaluate against (dg.txn.monitoring, dg.kyc.onboarding, dg.screening.pep_sanctions)
    - facts: Map of field_id -> value
    - evidence: Map of doc_id -> status ("missing", "provided", "verified")

    Returns:
    - decision: The outcome (approve, block, escalate, investigate, hold, decline)
    - decision_label: Human-readable label
    - decision_code: Machine-readable code
    - reasoning_chain: Step-by-step evaluation
    - warnings: Evidence warnings
    - version_pins: Template/regulation version info for audit
    """
    if not _template_loader:
        raise HTTPException(status_code=500, detail="Template loader not initialized")

    result = _template_loader.evaluate_with_template(
        request.template_id,
        request.facts,
        request.evidence
    )

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result
