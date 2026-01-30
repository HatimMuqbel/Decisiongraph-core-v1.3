"""
ClaimPilot Recommendation Builder

Builds structured recommendations with full audit trail.

Key features:
- Recommendation-only semantics (not "decisions")
- Complete reasoning chain capture
- Authority citations
- Precedent surfacing
- RecommendationMemo generation
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from ..canon import content_hash, text_hash
from ..models import (
    AuthorityRef,
    AuthorityRule,
    AuthorityType,
    ClaimContext,
    DispositionType,
    EvidenceRule,
    EvidenceItem,
    GateStrictness,
    Policy,
    PrecedentHit,
    ReasoningStep,
    ReasoningStepResult,
    ReasoningStepType,
    RecommendationCertainty,
    RecommendationMemo,
    RecommendationRecord,
    TimelineRule,
    TriBool,
)
from .authority_router import AuthorityRoutingResult, AuthorityRouter
from .condition_evaluator import ConditionEvaluator
from .context_resolver import ContextResolver, ResolvedContext
from .evidence_gate import EvidenceGate, EvidenceGateResult
from .precedent_finder import PrecedentFinder, PrecedentKey, PrecedentRecord
from .timeline_calculator import TimelineCalculator, TimelineSummary


# =============================================================================
# Recommendation Builder
# =============================================================================

@dataclass
class RecommendationBuilder:
    """
    Builds complete claim recommendations with full audit trail.

    The builder orchestrates all engine components to produce a
    recommendation that includes:
    - Disposition recommendation (pay/deny/investigate/escalate)
    - Complete reasoning chain
    - All cited authorities
    - Similar precedent cases
    - Evidence status
    - Timeline compliance
    - Escalation requirements

    Core Principle: "The adjuster decides. ClaimPilot recommends and documents."

    Usage:
        builder = RecommendationBuilder(
            policy_engine=engine,
            precedent_finder=finder,
        )

        recommendation = builder.build(
            policy=policy,
            context=claim_context,
        )

        # Generate memo for human review
        memo = builder.generate_memo(recommendation)
    """

    # Component services
    condition_evaluator: ConditionEvaluator = field(default_factory=ConditionEvaluator)
    context_resolver: ContextResolver = field(default_factory=ContextResolver)
    evidence_gate: EvidenceGate = field(default_factory=EvidenceGate)
    authority_router: AuthorityRouter = field(default_factory=AuthorityRouter)
    timeline_calculator: TimelineCalculator = field(default_factory=TimelineCalculator)
    precedent_finder: Optional[PrecedentFinder] = None

    # Cached rules (would come from PolicyEngine in full integration)
    timeline_rules: list[TimelineRule] = field(default_factory=list)
    evidence_rules: list[EvidenceRule] = field(default_factory=list)
    authority_rules: list[AuthorityRule] = field(default_factory=list)
    authorities: dict[str, AuthorityRef] = field(default_factory=dict)

    def build(
        self,
        policy: Policy,
        context: ClaimContext,
        disposition_hint: Optional[DispositionType] = None,
    ) -> RecommendationRecord:
        """
        Build a complete recommendation for a claim.

        Args:
            policy: The applicable policy
            context: Claim context with facts and evidence
            disposition_hint: Optional hint for disposition analysis

        Returns:
            Complete RecommendationRecord
        """
        reasoning_steps: list[ReasoningStep] = []
        cited_authorities: list[AuthorityRef] = []
        supporting_fact_ids: list[str] = []

        # Step 1: Resolve applicable coverages and exclusions
        resolved = self.context_resolver.resolve(policy, context)
        step_1 = self._record_coverage_analysis(resolved)
        reasoning_steps.append(step_1)

        # Collect supporting facts from coverage evaluation
        for match in resolved.matched_coverages:
            for precond_result in match.precondition_results:
                supporting_fact_ids.extend(precond_result.supporting_fact_ids)

        # Step 2: Evaluate exclusions
        step_2 = self._record_exclusion_analysis(resolved, cited_authorities)
        reasoning_steps.append(step_2)

        # Step 3: Check evidence requirements
        evidence_result = self.evidence_gate.evaluate(
            self.evidence_rules,
            context,
            disposition_hint,
        )
        step_3 = self._record_evidence_analysis(evidence_result)
        reasoning_steps.append(step_3)

        # Step 4: Determine disposition
        disposition, certainty = self._determine_disposition(
            resolved,
            evidence_result,
            disposition_hint,
        )
        step_4 = self._record_disposition_reasoning(
            disposition,
            certainty,
            resolved,
            evidence_result,
        )
        reasoning_steps.append(step_4)

        # Step 5: Check authority/escalation requirements
        authority_result = self.authority_router.route(
            self.authority_rules,
            context,
            policy,
        )
        step_5 = self._record_authority_analysis(authority_result)
        reasoning_steps.append(step_5)

        # Step 6: Find similar precedents
        similar_cases: list[PrecedentHit] = []
        if self.precedent_finder:
            similar_cases = self._find_precedents(
                context,
                policy,
                resolved,
                disposition,
            )
            if similar_cases:
                step_6 = self._record_precedent_analysis(similar_cases)
                reasoning_steps.append(step_6)

        # Step 7: Calculate timeline
        timeline_summary = self.timeline_calculator.get_timeline_summary(
            self.timeline_rules,
            context,
        )
        step_7 = self._record_timeline_analysis(timeline_summary)
        reasoning_steps.append(step_7)

        # Build the recommendation record
        now = datetime.now(timezone.utc)

        # Compute content hash for integrity
        content_for_hash = {
            "claim_id": context.claim_id,
            "policy_id": policy.id,
            "disposition": disposition.value,
            "certainty": certainty.value,
            "reasoning_count": len(reasoning_steps),
            "generated_at": now.isoformat(),
        }
        rec_content_hash = content_hash(content_for_hash)

        # Build disposition reason from reasoning
        disposition_reasons = []
        for step in reasoning_steps:
            if step.step_type == ReasoningStepType.FINAL_DETERMINATION:
                disposition_reasons.append(step.result_reason)
        disposition_reason = "; ".join(disposition_reasons) if disposition_reasons else f"Recommend {disposition.value}"

        recommendation = RecommendationRecord(
            id=str(uuid4()),
            claim_id=context.claim_id,
            context_id=policy.id,
            recommended_disposition=disposition,
            disposition_reason=disposition_reason,
            certainty=certainty,
            unknown_facts=resolved.all_missing_facts,
            coverages_evaluated=[c.id for c in resolved.triggered_coverages],
            exclusions_triggered=[e.id for e in resolved.triggered_exclusions],
            authorities_cited=cited_authorities,
            similar_cases=similar_cases,
            facts_considered=list(set(supporting_fact_ids)),
            reasoning_steps=reasoning_steps,
            generated_at=now,
            requires_authority=authority_result.requires_escalation,
            required_role=authority_result.minimum_role if authority_result.requires_escalation else None,
        )

        return recommendation

    def _record_coverage_analysis(
        self,
        resolved: ResolvedContext,
    ) -> ReasoningStep:
        """Record the coverage analysis reasoning step."""
        triggered = [c.name for c in resolved.triggered_coverages]
        not_triggered = [
            m.coverage.name
            for m in resolved.matched_coverages
            if not m.triggered or not m.preconditions_met
        ]

        if triggered:
            conclusion = f"Coverages triggered: {', '.join(triggered)}"
            result = TriBool.TRUE
        else:
            conclusion = "No coverages triggered by this claim"
            result = TriBool.FALSE

        step_result = ReasoningStepResult.PASSED if result == TriBool.TRUE else (
            ReasoningStepResult.FAILED if result == TriBool.FALSE else ReasoningStepResult.UNCERTAIN
        )

        return ReasoningStep(
            id=str(uuid4()),
            sequence=1,
            step_type=ReasoningStepType.COVERAGE_CHECK,
            description="Coverage Analysis",
            result=step_result,
            result_reason=conclusion,
            supporting_fact_ids=[m.coverage.id for m in resolved.matched_coverages],
        )

    def _record_exclusion_analysis(
        self,
        resolved: ResolvedContext,
        cited_authorities: list[AuthorityRef],
    ) -> ReasoningStep:
        """Record the exclusion analysis reasoning step."""
        if resolved.triggered_exclusions:
            exclusion_names = [e.name for e in resolved.triggered_exclusions]
            conclusion = f"Exclusions apply: {', '.join(exclusion_names)}"
            result = TriBool.TRUE

            # Add authority citations
            for exc in resolved.triggered_exclusions:
                if exc.policy_section_ref:
                    # Create inline authority ref
                    auth = AuthorityRef(
                        id=f"exclusion-{exc.id}",
                        authority_type=AuthorityType.POLICY_WORDING,
                        title=exc.name,
                        section=exc.policy_section_ref,
                        source_name="Policy Document",
                        quote_excerpt=exc.policy_wording,
                    )
                    cited_authorities.append(auth)

        elif resolved.potential_exclusions:
            potential_names = [e.name for e in resolved.potential_exclusions]
            conclusion = f"Potential exclusions (need more facts): {', '.join(potential_names)}"
            result = TriBool.UNKNOWN
        else:
            conclusion = "No exclusions apply"
            result = TriBool.FALSE

        step_result = ReasoningStepResult.PASSED if result == TriBool.TRUE else (
            ReasoningStepResult.FAILED if result == TriBool.FALSE else ReasoningStepResult.UNCERTAIN
        )

        return ReasoningStep(
            id=str(uuid4()),
            sequence=2,
            step_type=ReasoningStepType.EXCLUSION_EVALUATION,
            description="Exclusion Analysis",
            result=step_result,
            result_reason=conclusion,
            supporting_fact_ids=[e.id for e in resolved.triggered_exclusions + resolved.potential_exclusions],
        )

    def _record_evidence_analysis(
        self,
        evidence_result: EvidenceGateResult,
    ) -> ReasoningStep:
        """Record the evidence analysis reasoning step."""
        if not evidence_result.can_recommend:
            missing = [d.doc_type for d in evidence_result.blocking_recommendation]
            conclusion = f"Cannot recommend - missing critical evidence: {', '.join(missing)}"
            result = TriBool.FALSE
        elif not evidence_result.can_finalize:
            missing = [d.doc_type for d in evidence_result.blocking_finalization]
            conclusion = f"Can recommend, but finalization needs: {', '.join(missing)}"
            result = TriBool.UNKNOWN
        else:
            conclusion = f"Evidence complete ({evidence_result.completeness_percentage:.0f}%)"
            result = TriBool.TRUE

        step_result = ReasoningStepResult.PASSED if result == TriBool.TRUE else (
            ReasoningStepResult.FAILED if result == TriBool.FALSE else ReasoningStepResult.UNCERTAIN
        )

        return ReasoningStep(
            id=str(uuid4()),
            sequence=3,
            step_type=ReasoningStepType.EVIDENCE_GATE,
            description="Evidence Gate Check",
            result=step_result,
            result_reason=conclusion,
            supporting_fact_ids=evidence_result.evaluated_rules,
        )

    def _determine_disposition(
        self,
        resolved: ResolvedContext,
        evidence_result: EvidenceGateResult,
        hint: Optional[DispositionType],
    ) -> tuple[DispositionType, RecommendationCertainty]:
        """Determine the recommended disposition and certainty level."""
        # If exclusion triggered, recommend deny
        if resolved.triggered_exclusions:
            if resolved.has_unknown_exclusions:
                return (DispositionType.INVESTIGATE, RecommendationCertainty.MEDIUM)
            return (DispositionType.DENY, RecommendationCertainty.HIGH)

        # If no coverages triggered, recommend deny
        if not resolved.triggered_coverages:
            return (DispositionType.DENY, RecommendationCertainty.HIGH)

        # If potential exclusions with missing facts, recommend investigate
        if resolved.potential_exclusions:
            return (DispositionType.INVESTIGATE, RecommendationCertainty.LOW)

        # If evidence incomplete for recommendation
        if not evidence_result.can_recommend:
            return (DispositionType.INVESTIGATE, RecommendationCertainty.LOW)

        # If evidence incomplete for finalization
        if not evidence_result.can_finalize:
            return (DispositionType.PAY, RecommendationCertainty.MEDIUM)

        # Coverage triggered, no exclusions, evidence complete
        return (DispositionType.PAY, RecommendationCertainty.HIGH)

    def _record_disposition_reasoning(
        self,
        disposition: DispositionType,
        certainty: RecommendationCertainty,
        resolved: ResolvedContext,
        evidence_result: EvidenceGateResult,
    ) -> ReasoningStep:
        """Record the disposition reasoning step."""
        reasons = []

        if disposition == DispositionType.PAY:
            reasons.append(f"Coverages triggered: {len(resolved.triggered_coverages)}")
            reasons.append("No exclusions apply")
            if evidence_result.can_finalize:
                reasons.append("Evidence complete")
            conclusion = "Recommend PAY - " + "; ".join(reasons)

        elif disposition == DispositionType.DENY:
            if resolved.triggered_exclusions:
                exc_names = [e.name for e in resolved.triggered_exclusions[:3]]
                reasons.append(f"Exclusions: {', '.join(exc_names)}")
            elif not resolved.triggered_coverages:
                reasons.append("No coverage triggered")
            conclusion = "Recommend DENY - " + "; ".join(reasons)

        elif disposition == DispositionType.INVESTIGATE:
            if resolved.potential_exclusions:
                reasons.append(f"Potential exclusions: {len(resolved.potential_exclusions)}")
            if not evidence_result.can_recommend:
                reasons.append("Missing critical evidence")
            if resolved.all_missing_facts:
                reasons.append(f"Missing facts: {len(resolved.all_missing_facts)}")
            conclusion = "Recommend INVESTIGATE - " + "; ".join(reasons)

        else:
            conclusion = f"Recommend {disposition.value} - requires further analysis"

        return ReasoningStep(
            id=str(uuid4()),
            sequence=4,
            step_type=ReasoningStepType.FINAL_DETERMINATION,
            description="Disposition Determination",
            result=ReasoningStepResult.PASSED,
            result_reason=f"{conclusion} (Certainty: {certainty.value})",
            supporting_fact_ids=[],
        )

    def _record_authority_analysis(
        self,
        authority_result: AuthorityRoutingResult,
    ) -> ReasoningStep:
        """Record the authority/escalation analysis."""
        if authority_result.requires_escalation:
            reasons = [r.reason for r in authority_result.triggered_requirements[:3]]
            conclusion = f"Escalation required to {authority_result.minimum_role}: {'; '.join(reasons)}"
            result = TriBool.TRUE
        else:
            conclusion = "No escalation required"
            result = TriBool.FALSE

        step_result = ReasoningStepResult.PASSED if result == TriBool.TRUE else ReasoningStepResult.FAILED

        return ReasoningStep(
            id=str(uuid4()),
            sequence=5,
            step_type=ReasoningStepType.ESCALATION_CHECK,
            description="Authority/Escalation Check",
            result=step_result,
            result_reason=conclusion,
            supporting_fact_ids=authority_result.evaluated_rules,
        )

    def _find_precedents(
        self,
        context: ClaimContext,
        policy: Policy,
        resolved: ResolvedContext,
        disposition: DispositionType,
    ) -> list[PrecedentHit]:
        """Find similar precedent cases."""
        if not self.precedent_finder:
            return []

        # Build precedent key
        from ..canon import text_hash

        coverage_ids = [c.id for c in resolved.triggered_coverages]
        exclusion_hashes = []
        for exc in resolved.triggered_exclusions:
            if exc.policy_wording:
                exclusion_hashes.append(text_hash(exc.policy_wording))

        query_key = PrecedentKey.compute(
            jurisdiction=policy.jurisdiction,
            line_of_business=policy.line_of_business.value,
            loss_type=context.loss_type,
            coverage_ids=coverage_ids,
            exclusion_clause_hashes=exclusion_hashes,
            disposition_type=disposition,
            fact_keys=set(context.facts.keys()),
        )

        return self.precedent_finder.find_similar(
            query=query_key,
            limit=5,
            jurisdiction_filter=policy.jurisdiction,
        )

    def _record_precedent_analysis(
        self,
        similar_cases: list[PrecedentHit],
    ) -> ReasoningStep:
        """Record the precedent analysis."""
        if similar_cases:
            top_case = similar_cases[0]
            conclusion = (
                f"Found {len(similar_cases)} similar cases. "
                f"Most similar: {top_case.case_id} ({top_case.similarity_score:.0%} match) - "
                f"recommended {top_case.recommended_disposition.value}"
            )
        else:
            conclusion = "No similar precedent cases found"

        step_result = ReasoningStepResult.PASSED if similar_cases else ReasoningStepResult.UNCERTAIN

        return ReasoningStep(
            id=str(uuid4()),
            sequence=6,
            step_type=ReasoningStepType.PRECEDENT_SEARCH,
            description="Precedent Analysis",
            result=step_result,
            result_reason=conclusion,
            supporting_fact_ids=[c.case_id for c in similar_cases],
        )

    def _record_timeline_analysis(
        self,
        timeline_summary: TimelineSummary,
    ) -> ReasoningStep:
        """Record the timeline compliance analysis."""
        overdue_count = len(timeline_summary.overdue_events)
        next_due = timeline_summary.next_due_event

        if overdue_count > 0:
            conclusion = f"ALERT: {overdue_count} overdue deadlines"
            result = TriBool.FALSE
        elif next_due:
            conclusion = f"Next deadline: {next_due.due_date.isoformat()}"
            result = TriBool.TRUE
        else:
            conclusion = "No pending deadlines"
            result = TriBool.TRUE

        step_result = ReasoningStepResult.PASSED if result == TriBool.TRUE else ReasoningStepResult.FAILED

        return ReasoningStep(
            id=str(uuid4()),
            sequence=7,
            step_type=ReasoningStepType.TIMELINE_CHECK,
            description="Timeline Compliance",
            result=step_result,
            result_reason=conclusion,
            supporting_fact_ids=[e.rule_id for e in timeline_summary.events],
        )

    def generate_memo(
        self,
        recommendation: RecommendationRecord,
        context: ClaimContext,
    ) -> RecommendationMemo:
        """
        Generate a RecommendationMemo for human review.

        The memo provides a structured summary suitable for:
        - Demo artifacts
        - Test fixtures
        - Future report generation
        """
        # Build summary
        summary_parts = []
        for step in recommendation.reasoning_steps:
            summary_parts.append(f"• {step.description}: {step.explanation}")
        summary = "\n".join(summary_parts)

        # Build alternatives
        alternatives: list[str] = []
        if recommendation.recommended_disposition == DispositionType.PAY:
            if recommendation.missing_fact_keys:
                alternatives.append("Request additional information before finalizing")
        elif recommendation.recommended_disposition == DispositionType.DENY:
            alternatives.append("Request review by supervisor")
            alternatives.append("Investigate further before denying")
        elif recommendation.recommended_disposition == DispositionType.INVESTIGATE:
            alternatives.append("Approve pending investigation completion")
            alternatives.append("Deny based on current information")

        # Build required evidence list
        required_evidence: list[str] = []
        for step in recommendation.reasoning_steps:
            if "missing" in step.explanation.lower():
                # Extract missing items from explanation
                required_evidence.append(step.explanation)

        return RecommendationMemo(
            claim_id=recommendation.claim_id,
            summary=summary,
            recommended_action=recommendation.recommended_disposition,
            alternatives=alternatives,
            citations=recommendation.cited_authorities,
            similar_cases=recommendation.similar_cases,
            missing_facts=recommendation.missing_fact_keys,
            required_evidence=required_evidence,
            escalation_required=recommendation.escalation_required,
            escalation_reason=recommendation.escalation_role,
            confidence=recommendation.certainty,
            generated_at=recommendation.generated_at,
        )


# =============================================================================
# Convenience Functions
# =============================================================================

def build_recommendation(
    policy: Policy,
    context: ClaimContext,
    timeline_rules: Optional[list[TimelineRule]] = None,
    evidence_rules: Optional[list[EvidenceRule]] = None,
    authority_rules: Optional[list[AuthorityRule]] = None,
) -> RecommendationRecord:
    """
    Build a recommendation for a claim.

    Convenience function that creates a temporary builder.
    """
    builder = RecommendationBuilder(
        timeline_rules=timeline_rules or [],
        evidence_rules=evidence_rules or [],
        authority_rules=authority_rules or [],
    )
    return builder.build(policy, context)


def quick_recommendation(
    policy: Policy,
    context: ClaimContext,
) -> tuple[DispositionType, RecommendationCertainty]:
    """
    Get a quick disposition recommendation without full reasoning.

    Returns (disposition, certainty) tuple.
    """
    resolver = ContextResolver()
    resolved = resolver.resolve(policy, context)

    # Quick determination
    if resolved.triggered_exclusions:
        return (DispositionType.DENY, RecommendationCertainty.HIGH)
    elif not resolved.triggered_coverages:
        return (DispositionType.DENY, RecommendationCertainty.HIGH)
    elif resolved.potential_exclusions or resolved.all_missing_facts:
        return (DispositionType.INVESTIGATE, RecommendationCertainty.LOW)
    else:
        return (DispositionType.PAY, RecommendationCertainty.MEDIUM)
