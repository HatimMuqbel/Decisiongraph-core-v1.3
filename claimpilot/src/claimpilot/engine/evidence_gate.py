"""
ClaimPilot Evidence Gate

Enforces two-stage evidence requirements:
1. BLOCKING_RECOMMENDATION - Cannot recommend without this evidence
2. BLOCKING_FINALIZATION - Can recommend, but can't finalize without it

Key features:
- Track missing required documents
- Evaluate conditional requirements
- Generate evidence checklists
- Support two-stage workflow
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

from ..exceptions import EvidenceGateError, MissingEvidenceError
from ..models import (
    ClaimContext,
    DispositionType,
    DocumentRequirement,
    EvaluationResult,
    EvidenceItem,
    EvidenceRule,
    GateStrictness,
    TriBool,
)
from .condition_evaluator import ConditionEvaluator


# =============================================================================
# Evidence Status
# =============================================================================

@dataclass
class DocumentStatus:
    """Status of a required document."""
    requirement: DocumentRequirement
    present: bool
    evidence_item: Optional[EvidenceItem] = None
    alternatives_present: list[str] = field(default_factory=list)
    satisfies_requirement: bool = False


@dataclass
class EvidenceGateResult:
    """
    Result of evaluating evidence requirements.

    Contains:
    - Whether recommendation is allowed
    - Whether finalization is allowed
    - List of missing documents by strictness level
    - Warnings for recommended but missing documents
    """
    # Gate status
    can_recommend: bool = True
    can_finalize: bool = True

    # Document status
    all_documents: list[DocumentStatus] = field(default_factory=list)

    # Missing by strictness
    blocking_recommendation: list[DocumentRequirement] = field(default_factory=list)
    blocking_finalization: list[DocumentRequirement] = field(default_factory=list)
    recommended_missing: list[DocumentRequirement] = field(default_factory=list)
    optional_missing: list[DocumentRequirement] = field(default_factory=list)

    # Summary
    total_required: int = 0
    total_present: int = 0
    completeness_percentage: float = 0.0

    # Evaluation metadata
    evaluated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    evaluated_rules: list[str] = field(default_factory=list)


# =============================================================================
# Evidence Gate
# =============================================================================

@dataclass
class EvidenceGate:
    """
    Evaluates evidence requirements for claim recommendations.

    Implements two-stage evidence gating:
    1. BLOCKING_RECOMMENDATION: Hard stop - cannot even recommend
    2. BLOCKING_FINALIZATION: Can recommend, human can't finalize

    Usage:
        gate = EvidenceGate()

        # Check if we can proceed
        result = gate.evaluate(
            rules=evidence_rules,
            context=claim_context,
            disposition=DispositionType.PAY,
        )

        if not result.can_recommend:
            print("Cannot recommend - missing:", result.blocking_recommendation)
        elif not result.can_finalize:
            print("Can recommend, but finalization needs:", result.blocking_finalization)
    """

    # Condition evaluator for applies_when checks
    evaluator: ConditionEvaluator = field(default_factory=ConditionEvaluator)

    def evaluate(
        self,
        rules: list[EvidenceRule],
        context: ClaimContext,
        disposition: Optional[DispositionType] = None,
    ) -> EvidenceGateResult:
        """
        Evaluate evidence requirements against claim context.

        Args:
            rules: Evidence rules to evaluate
            context: Claim context with evidence items
            disposition: Optional disposition type to filter rules

        Returns:
            EvidenceGateResult with gate status and missing documents
        """
        result = EvidenceGateResult()

        # Get all evidence items from context
        evidence_by_type: dict[str, EvidenceItem] = {}
        for item in context.evidence:
            evidence_by_type[item.doc_type] = item

        # Evaluate each applicable rule
        applicable_rules = self._filter_applicable_rules(
            rules, context, disposition
        )

        for rule in applicable_rules:
            result.evaluated_rules.append(rule.id)
            self._evaluate_rule(rule, context, evidence_by_type, result)

        # Calculate summary
        result.total_required = len(result.blocking_recommendation) + \
                               len(result.blocking_finalization) + \
                               len([d for d in result.all_documents if d.satisfies_requirement])

        result.total_present = len([d for d in result.all_documents if d.satisfies_requirement])

        if result.total_required > 0:
            result.completeness_percentage = (
                result.total_present / result.total_required * 100
            )
        else:
            result.completeness_percentage = 100.0

        # Determine gate status
        result.can_recommend = len(result.blocking_recommendation) == 0
        result.can_finalize = len(result.blocking_finalization) == 0 and result.can_recommend

        return result

    def _filter_applicable_rules(
        self,
        rules: list[EvidenceRule],
        context: ClaimContext,
        disposition: Optional[DispositionType],
    ) -> list[EvidenceRule]:
        """Filter rules that apply to this context."""
        applicable: list[EvidenceRule] = []

        # Sort by priority for deterministic order
        sorted_rules = sorted(
            rules,
            key=lambda r: (-r.priority, r.id)
        )

        for rule in sorted_rules:
            if not rule.enabled:
                continue

            # Check disposition type filter
            if rule.disposition_type and disposition:
                if rule.disposition_type != disposition:
                    continue

            # Check applies_when condition
            if rule.applies_when:
                eval_result = self.evaluator.evaluate(rule.applies_when, context)
                if eval_result.value != TriBool.TRUE:
                    continue

            applicable.append(rule)

        return applicable

    def _evaluate_rule(
        self,
        rule: EvidenceRule,
        context: ClaimContext,
        evidence_by_type: dict[str, EvidenceItem],
        result: EvidenceGateResult,
    ) -> None:
        """Evaluate a single evidence rule."""
        # Check required documents
        for doc_req in rule.required_documents:
            status = self._check_document(doc_req, context, evidence_by_type)
            result.all_documents.append(status)

            if not status.satisfies_requirement:
                # Categorize by strictness
                if doc_req.strictness == GateStrictness.BLOCKING_RECOMMENDATION:
                    result.blocking_recommendation.append(doc_req)
                elif doc_req.strictness == GateStrictness.BLOCKING_FINALIZATION:
                    result.blocking_finalization.append(doc_req)

        # Check recommended documents
        for doc_req in rule.recommended_documents:
            status = self._check_document(doc_req, context, evidence_by_type)
            result.all_documents.append(status)

            if not status.satisfies_requirement:
                if doc_req.strictness == GateStrictness.RECOMMENDED:
                    result.recommended_missing.append(doc_req)
                elif doc_req.strictness == GateStrictness.OPTIONAL:
                    result.optional_missing.append(doc_req)

    def _check_document(
        self,
        doc_req: DocumentRequirement,
        context: ClaimContext,
        evidence_by_type: dict[str, EvidenceItem],
    ) -> DocumentStatus:
        """Check if a document requirement is satisfied."""
        status = DocumentStatus(
            requirement=doc_req,
            present=False,
        )

        # Check if document condition applies
        if doc_req.applies_when:
            eval_result = self.evaluator.evaluate(doc_req.applies_when, context)
            if eval_result.value != TriBool.TRUE:
                # Condition doesn't apply, so requirement is satisfied
                status.satisfies_requirement = True
                return status

        # Check primary document type
        if doc_req.doc_type in evidence_by_type:
            status.present = True
            status.evidence_item = evidence_by_type[doc_req.doc_type]
            status.satisfies_requirement = True
            return status

        # Check alternatives
        if doc_req.alternatives:
            for alt_type in doc_req.alternatives:
                if alt_type in evidence_by_type:
                    status.alternatives_present.append(alt_type)
                    status.satisfies_requirement = True

        return status

    def get_missing_documents(
        self,
        rules: list[EvidenceRule],
        context: ClaimContext,
        disposition: Optional[DispositionType] = None,
    ) -> list[DocumentRequirement]:
        """
        Get list of all missing required documents.

        Convenience method for quick lookup.
        """
        result = self.evaluate(rules, context, disposition)
        return result.blocking_recommendation + result.blocking_finalization

    def can_recommend(
        self,
        rules: list[EvidenceRule],
        context: ClaimContext,
        disposition: Optional[DispositionType] = None,
    ) -> bool:
        """Check if recommendation is allowed."""
        result = self.evaluate(rules, context, disposition)
        return result.can_recommend

    def can_finalize(
        self,
        rules: list[EvidenceRule],
        context: ClaimContext,
        disposition: Optional[DispositionType] = None,
    ) -> bool:
        """Check if finalization is allowed."""
        result = self.evaluate(rules, context, disposition)
        return result.can_finalize


# =============================================================================
# Evidence Checklist Generator
# =============================================================================

@dataclass
class EvidenceChecklist:
    """A checklist of evidence requirements for a claim."""
    claim_id: str
    generated_at: datetime

    # Required items (blocking)
    required_items: list[dict] = field(default_factory=list)

    # Recommended items
    recommended_items: list[dict] = field(default_factory=list)

    # Status
    complete: bool = False
    percentage_complete: float = 0.0


def generate_evidence_checklist(
    rules: list[EvidenceRule],
    context: ClaimContext,
    disposition: Optional[DispositionType] = None,
) -> EvidenceChecklist:
    """
    Generate an evidence checklist for a claim.

    Returns a checklist with all required and recommended documents,
    showing which are present and which are missing.
    """
    gate = EvidenceGate()
    result = gate.evaluate(rules, context, disposition)

    checklist = EvidenceChecklist(
        claim_id=context.claim_id,
        generated_at=datetime.now(timezone.utc),
    )

    # Build required items
    for doc_status in result.all_documents:
        if doc_status.requirement.strictness in {
            GateStrictness.BLOCKING_RECOMMENDATION,
            GateStrictness.BLOCKING_FINALIZATION,
        }:
            checklist.required_items.append({
                "doc_type": doc_status.requirement.doc_type,
                "description": doc_status.requirement.description,
                "strictness": doc_status.requirement.strictness.value,
                "present": doc_status.present or doc_status.satisfies_requirement,
                "alternatives": doc_status.requirement.alternatives,
                "alternatives_present": doc_status.alternatives_present,
            })

    # Build recommended items
    for doc_status in result.all_documents:
        if doc_status.requirement.strictness in {
            GateStrictness.RECOMMENDED,
            GateStrictness.OPTIONAL,
        }:
            checklist.recommended_items.append({
                "doc_type": doc_status.requirement.doc_type,
                "description": doc_status.requirement.description,
                "strictness": doc_status.requirement.strictness.value,
                "present": doc_status.present or doc_status.satisfies_requirement,
            })

    # Calculate completion
    total = len(checklist.required_items)
    present = len([i for i in checklist.required_items if i["present"]])

    if total > 0:
        checklist.percentage_complete = present / total * 100
        checklist.complete = present == total
    else:
        checklist.percentage_complete = 100.0
        checklist.complete = True

    return checklist


# =============================================================================
# Convenience Functions
# =============================================================================

def evaluate_evidence(
    rules: list[EvidenceRule],
    context: ClaimContext,
    disposition: Optional[DispositionType] = None,
) -> EvidenceGateResult:
    """
    Evaluate evidence requirements.

    Convenience function that creates a temporary gate.
    """
    gate = EvidenceGate()
    return gate.evaluate(rules, context, disposition)


def check_evidence_complete(
    rules: list[EvidenceRule],
    context: ClaimContext,
    disposition: Optional[DispositionType] = None,
) -> bool:
    """
    Check if all evidence requirements are satisfied.

    Returns True only if both recommendation and finalization are allowed.
    """
    gate = EvidenceGate()
    result = gate.evaluate(rules, context, disposition)
    return result.can_recommend and result.can_finalize
