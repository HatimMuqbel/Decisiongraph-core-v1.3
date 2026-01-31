"""Policy pack endpoints."""

from fastapi import APIRouter, HTTPException
from typing import Optional

from api.schemas.responses import PolicySummary, PolicyDetail, CoverageSummary, ExclusionSummary
from claimpilot.packs.loader import PolicyPackLoader
from claimpilot.canon import compute_policy_pack_hash
from claimpilot.models import Policy

router = APIRouter(prefix="/policies", tags=["Policies"])

# Shared loader instance (set by main.py)
loader: PolicyPackLoader = None
policies_cache: dict[str, Policy] = {}


def set_loader(l: PolicyPackLoader, cache: dict[str, Policy]):
    global loader, policies_cache
    loader = l
    policies_cache = cache


@router.get("", response_model=list[PolicySummary])
async def list_policies(line_of_business: Optional[str] = None):
    """
    List all available policy packs.

    Optionally filter by line of business: auto, property, marine, health,
    workers_comp, liability
    """
    policies = list(policies_cache.values())

    if line_of_business:
        policies = [p for p in policies if p.line_of_business.value == line_of_business]

    return [
        PolicySummary(
            id=p.id,
            name=p.name,
            jurisdiction=p.jurisdiction,
            line_of_business=p.line_of_business.value,
            product_code=p.product_code,
            version=p.version,
            effective_date=p.effective_date.isoformat(),
            coverage_count=len(p.coverage_sections),
            exclusion_count=len(p.exclusions)
        )
        for p in policies
    ]


@router.get("/{policy_id}", response_model=PolicyDetail)
async def get_policy(policy_id: str):
    """Get full details of a policy pack including coverages and exclusions."""
    policy = policies_cache.get(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found")

    return PolicyDetail(
        id=policy.id,
        name=policy.name,
        jurisdiction=policy.jurisdiction,
        line_of_business=policy.line_of_business.value,
        product_code=policy.product_code,
        version=policy.version,
        effective_date=policy.effective_date.isoformat(),
        policy_pack_hash=compute_policy_pack_hash(policy),
        coverages=[
            CoverageSummary(
                id=c.id,
                code=c.code,
                name=c.name,
                description=c.description,
                loss_types=[t.loss_type for t in (c.triggers or [])]
            )
            for c in policy.coverage_sections
        ],
        exclusions=[
            ExclusionSummary(
                id=e.id,
                code=e.code,
                name=e.name,
                description=e.description,
                policy_wording=e.policy_wording,
                applies_to=e.applies_to_coverages,
                evaluation_questions=e.evaluation_questions or []
            )
            for e in policy.exclusions
        ]
    )


@router.get("/{policy_id}/exclusions")
async def get_policy_exclusions(policy_id: str):
    """Get all exclusions for a policy pack with full policy wording."""
    policy = policies_cache.get(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found")

    return [
        {
            "id": e.id,
            "code": e.code,
            "name": e.name,
            "description": e.description,
            "policy_wording": e.policy_wording,
            "policy_section_ref": e.policy_section_ref,
            "applies_to_coverages": e.applies_to_coverages,
            "evaluation_questions": e.evaluation_questions or [],
            "evidence_to_confirm": e.evidence_to_confirm or [],
            "evidence_to_rule_out": e.evidence_to_rule_out or [],
        }
        for e in policy.exclusions
    ]
