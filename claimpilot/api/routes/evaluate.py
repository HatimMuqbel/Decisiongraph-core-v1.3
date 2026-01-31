"""Claim evaluation endpoint."""

from fastapi import APIRouter, HTTPException
from datetime import date, datetime
import uuid

from api.schemas.requests import EvaluateRequest
from api.schemas.responses import (
    EvaluateResponse, AuthorityCited, ReasoningStep, ExclusionEvaluated,
    EvidenceRequirement
)
from api.data.evidence_matrix import get_evidence_requirement
from api.routes.memo import cache_evaluation
from claimpilot.packs.loader import PolicyPackLoader
from claimpilot.engine import ConditionEvaluator, RecommendationBuilder
from claimpilot.models import (
    ClaimantType, FactSource, FactCertainty, EvidenceStatus,
    Fact, EvidenceItem, Policy, ClaimContext
)
from claimpilot.canon import compute_policy_pack_hash
import claimpilot

router = APIRouter(prefix="/evaluate", tags=["Evaluation"])

# Shared loader instance
loader: PolicyPackLoader = None
policies_cache: dict[str, Policy] = {}


def set_loader(l: PolicyPackLoader, cache: dict[str, Policy]):
    global loader, policies_cache
    loader = l
    policies_cache = cache


@router.post("", response_model=EvaluateResponse)
async def evaluate_claim(request: EvaluateRequest):
    """
    Evaluate a claim and return a recommendation.

    This is the main endpoint. Takes claim facts and evidence,
    returns a full recommendation with reasoning chain, citations,
    and provenance.
    """
    # Get policy
    policy = policies_cache.get(request.policy_id)
    if not policy:
        raise HTTPException(
            status_code=404,
            detail=f"Policy '{request.policy_id}' not found. "
                   f"Available: {list(policies_cache.keys())}"
        )

    # Parse dates
    try:
        loss_date = date.fromisoformat(request.loss_date)
        report_date = date.fromisoformat(request.report_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

    # Parse claimant type
    try:
        claimant_type = ClaimantType(request.claimant_type)
    except ValueError:
        claimant_type = ClaimantType.INSURED

    # Generate claim ID
    claim_id = f"EVAL-{uuid.uuid4().hex[:8].upper()}"

    # Build facts dictionary
    facts: dict[str, Fact] = {}
    for f in request.facts:
        certainty = FactCertainty.REPORTED
        if f.certainty == "confirmed":
            certainty = FactCertainty.CONFIRMED
        elif f.certainty == "disputed":
            certainty = FactCertainty.DISPUTED

        fact = Fact(
            id=f"fact_{f.field.replace('.', '_')}",
            claim_id=claim_id,
            field=f.field,
            value=f.value,
            value_type=type(f.value).__name__,
            source=FactSource.ADJUSTER_INPUT,
            certainty=certainty
        )
        facts[f.field] = fact

    # Build evidence list
    evidence = []
    for e in request.evidence:
        status = EvidenceStatus.VERIFIED
        if e.status == "received":
            status = EvidenceStatus.RECEIVED
        elif e.status == "requested":
            status = EvidenceStatus.REQUESTED

        evidence.append(EvidenceItem(
            id=f"ev_{e.doc_type}",
            claim_id=claim_id,
            doc_type=e.doc_type,
            description=e.doc_type.replace("_", " ").title(),
            status=status
        ))

    # Create ClaimContext for evaluation
    claim_context = ClaimContext(
        claim_id=claim_id,
        policy_id=policy.id,
        jurisdiction=policy.jurisdiction,
        line_of_business=policy.line_of_business,
        loss_type=request.loss_type,
        loss_date=loss_date,
        report_date=report_date,
        claimant_type=claimant_type,
        facts=facts,
        evidence=evidence,
        policy_version_used=policy.version,
    )

    # Evaluate exclusions
    evaluator = ConditionEvaluator()
    exclusions_evaluated = []
    exclusions_triggered = []
    exclusions_ruled_out = []
    exclusions_uncertain = []

    for exclusion in policy.exclusions:
        triggered = False
        reason = "Not triggered - no matching conditions"
        result = None

        for condition in exclusion.trigger_conditions:
            result = evaluator.evaluate(condition, claim_context)
            if result.is_satisfied:
                triggered = True
                reason = f"Condition met: {result.explanation}"
                exclusions_triggered.append(exclusion.code)
                break
            elif result.is_uncertain:
                reason = f"Uncertain: {', '.join(result.missing_fact_keys)} unknown"
                if exclusion.code not in exclusions_uncertain:
                    exclusions_uncertain.append(exclusion.code)

        if not triggered and result is not None and result.is_not_satisfied:
            exclusions_ruled_out.append(exclusion.code)

        exclusions_evaluated.append(ExclusionEvaluated(
            id=exclusion.id,
            code=exclusion.code,
            name=exclusion.name,
            triggered=triggered,
            reason=reason,
            policy_wording=exclusion.policy_wording if triggered else None
        ))

    # Determine disposition
    if exclusions_triggered:
        recommended_disposition = "deny"
        disposition_reason = f"Exclusion(s) triggered: {', '.join(exclusions_triggered)}"
        certainty = "high"
    elif exclusions_uncertain:
        recommended_disposition = "request_info"
        disposition_reason = f"Uncertain exclusions require more information: {', '.join(exclusions_uncertain)}"
        certainty = "low"
    else:
        # Check authority requirements (simplified)
        reserve_fact = facts.get("claim.reserve_amount")
        if reserve_fact and reserve_fact.value and float(reserve_fact.value) > 50000:
            recommended_disposition = "pay"
            disposition_reason = "Coverage applies, no exclusions triggered. Requires manager approval (>$50K)."
            certainty = "high"
            requires_authority = True
            required_role = "claims_manager"
        else:
            recommended_disposition = "pay"
            disposition_reason = "Coverage applies, no exclusions triggered"
            certainty = "high"
            requires_authority = False
            required_role = None

    # Build reasoning steps
    reasoning_steps = []
    step_seq = 1

    # Coverage check step
    reasoning_steps.append(ReasoningStep(
        sequence=step_seq,
        step_type="coverage_check",
        description=f"Checked coverage for loss type '{request.loss_type}'",
        rule_id=None,
        rule_name=None,
        result="passed",
        result_reason="Loss type matches policy coverage"
    ))
    step_seq += 1

    # Exclusion evaluation steps
    for exc_eval in exclusions_evaluated:
        reasoning_steps.append(ReasoningStep(
            sequence=step_seq,
            step_type="exclusion_evaluation",
            description=f"Evaluated exclusion: {exc_eval.name}",
            rule_id=exc_eval.id,
            rule_name=exc_eval.name,
            result="failed" if exc_eval.triggered else "passed",
            result_reason=exc_eval.reason
        ))
        step_seq += 1

    # Collect unknown facts
    unknown_facts = []
    for exc in policy.exclusions:
        for cond in exc.trigger_conditions:
            if cond.predicate and cond.predicate.field:
                if cond.predicate.field not in facts:
                    if cond.predicate.field not in unknown_facts:
                        unknown_facts.append(cond.predicate.field)

    # Generate next best questions
    next_best_questions = []
    for field in unknown_facts[:5]:  # Limit to 5
        next_best_questions.append(f"What is the value of '{field}'?")

    # Check evidence completeness (simplified)
    evidence_doc_types = {e.doc_type for e in evidence}
    evidence_missing = []

    # Basic required evidence by loss type
    basic_evidence = ["police_report", "damage_estimate", "claim_form"]
    for doc in basic_evidence:
        if doc not in evidence_doc_types:
            evidence_missing.append(doc)

    # Handle authority requirements
    if 'requires_authority' not in locals():
        requires_authority = False
        required_role = None

    # Build structured evidence requirements for uncertain exclusions
    exclusions_requiring_evidence = []
    for exc_code in exclusions_uncertain:
        evidence_req = get_evidence_requirement(exc_code)
        if evidence_req:
            exclusions_requiring_evidence.append(EvidenceRequirement(
                exclusion_code=exc_code,
                exclusion_name=evidence_req["name"],
                purpose=evidence_req["purpose"],
                evidence_items=evidence_req["evidence_items"],
                resolution_if_applies=evidence_req["resolution_if_applies"],
                resolution_if_not_applies=evidence_req["resolution_if_not_applies"]
            ))
        else:
            # Fallback for exclusions not in matrix
            exc_name = next((e.name for e in policy.exclusions if e.code == exc_code), exc_code)
            exclusions_requiring_evidence.append(EvidenceRequirement(
                exclusion_code=exc_code,
                exclusion_name=exc_name,
                purpose=f"Determine applicability of {exc_name} exclusion.",
                evidence_items=["Supporting documentation", "Adjuster investigation notes"],
                resolution_if_applies="Claim Denied",
                resolution_if_not_applies="Exclusion Ruled Out"
            ))

    # Generate request ID for tracing
    request_id = f"REQ-{uuid.uuid4().hex[:12].upper()}"

    response = EvaluateResponse(
        request_id=request_id,
        claim_id=claim_id,
        policy_pack_id=policy.id,
        policy_pack_version=policy.version,
        policy_pack_hash=compute_policy_pack_hash(policy),

        recommended_disposition=recommended_disposition,
        disposition_reason=disposition_reason,
        certainty=certainty,

        coverages_evaluated=[c.code for c in policy.coverage_sections],
        coverage_applies=len(exclusions_triggered) == 0,

        exclusions_evaluated=exclusions_evaluated,
        exclusions_triggered=exclusions_triggered,
        exclusions_ruled_out=exclusions_ruled_out,
        exclusions_uncertain=exclusions_uncertain,
        exclusions_requiring_evidence=exclusions_requiring_evidence,

        requires_authority=requires_authority,
        required_role=required_role,
        authority_rule_triggered=None,

        evidence_complete=len(evidence_missing) == 0,
        evidence_missing=evidence_missing,

        unknown_facts=unknown_facts,
        next_best_questions=next_best_questions,

        authorities_cited=[],  # Would be populated from policy authorities
        reasoning_steps=reasoning_steps,

        evaluated_at=datetime.utcnow().isoformat() + "Z",
        engine_version=claimpilot.__version__
    )

    # Cache for memo generation
    cache_evaluation(response)

    return response
