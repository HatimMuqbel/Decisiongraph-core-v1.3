"""
ClaimPilot Context Resolver

Resolves applicable rules, coverages, and exclusions for a given claim context.

Key features:
- Match coverages by loss type and claimant type
- Evaluate preconditions and exclusion triggers
- Collect applicable timeline, evidence, and authority rules
- Stable, deterministic rule ordering
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from ..models import (
    AuthorityRule,
    ClaimContext,
    Condition,
    CoverageSection,
    EvaluationResult,
    EvidenceRule,
    Exclusion,
    Policy,
    TimelineRule,
    TriBool,
)
from .condition_evaluator import ConditionEvaluator, evaluate_condition


# =============================================================================
# Coverage Matching
# =============================================================================

@dataclass
class CoverageMatch:
    """Result of matching a coverage section to a claim."""
    coverage: CoverageSection
    triggered: bool
    trigger_loss_type: Optional[str] = None
    precondition_results: list[EvaluationResult] = field(default_factory=list)
    preconditions_met: bool = True
    missing_facts: list[str] = field(default_factory=list)


@dataclass
class ExclusionMatch:
    """Result of evaluating an exclusion against a claim."""
    exclusion: Exclusion
    triggered: TriBool
    trigger_results: list[EvaluationResult] = field(default_factory=list)
    missing_facts: list[str] = field(default_factory=list)


@dataclass
class ResolvedContext:
    """
    Complete resolution of applicable rules for a claim.

    Contains all coverages, exclusions, and rules that apply,
    along with evaluation results explaining why.
    """
    # Source
    policy: Policy
    claim: ClaimContext
    resolved_at: date

    # Coverage analysis
    matched_coverages: list[CoverageMatch] = field(default_factory=list)
    triggered_coverages: list[CoverageSection] = field(default_factory=list)

    # Exclusion analysis
    exclusion_matches: list[ExclusionMatch] = field(default_factory=list)
    triggered_exclusions: list[Exclusion] = field(default_factory=list)
    potential_exclusions: list[Exclusion] = field(default_factory=list)  # UNKNOWN

    # Applicable rules (sorted by priority)
    timeline_rules: list[TimelineRule] = field(default_factory=list)
    evidence_rules: list[EvidenceRule] = field(default_factory=list)
    authority_rules: list[AuthorityRule] = field(default_factory=list)

    # Aggregated missing facts
    all_missing_facts: list[str] = field(default_factory=list)

    # Summary flags
    has_unknown_exclusions: bool = False
    requires_escalation: bool = False
    escalation_reasons: list[str] = field(default_factory=list)


# =============================================================================
# Context Resolver
# =============================================================================

@dataclass
class ContextResolver:
    """
    Resolves applicable policy rules for a claim context.

    The resolver evaluates:
    1. Which coverages are triggered by the loss type
    2. Whether coverage preconditions are met
    3. Which exclusions apply (or might apply with UNKNOWN)
    4. Which timeline, evidence, and authority rules are relevant

    Usage:
        resolver = ContextResolver()
        resolved = resolver.resolve(policy, claim_context)

        # Check triggered coverages
        for cov in resolved.triggered_coverages:
            print(f"Coverage: {cov.name}")

        # Check exclusions
        if resolved.has_unknown_exclusions:
            print("Need more facts to determine exclusions")
    """

    # Condition evaluator instance
    evaluator: ConditionEvaluator = field(default_factory=ConditionEvaluator)

    def resolve(
        self,
        policy: Policy,
        context: ClaimContext,
        as_of: Optional[date] = None,
    ) -> ResolvedContext:
        """
        Resolve all applicable rules for a claim context.

        Args:
            policy: The policy to evaluate against
            context: The claim context with facts
            as_of: Date to check rule effectiveness (defaults to today)

        Returns:
            ResolvedContext with all applicable rules and evaluations
        """
        as_of = as_of or date.today()

        # Initialize result
        resolved = ResolvedContext(
            policy=policy,
            claim=context,
            resolved_at=as_of,
        )

        # 1. Match coverages
        self._resolve_coverages(policy, context, resolved)

        # 2. Evaluate exclusions
        self._resolve_exclusions(policy, context, resolved)

        # 3. Collect timeline rules
        self._resolve_timeline_rules(policy, context, resolved)

        # 4. Collect evidence rules
        self._resolve_evidence_rules(policy, context, resolved)

        # 5. Collect authority rules (escalation)
        self._resolve_authority_rules(policy, context, resolved)

        # 6. Aggregate missing facts
        self._aggregate_missing_facts(resolved)

        return resolved

    def _resolve_coverages(
        self,
        policy: Policy,
        context: ClaimContext,
        resolved: ResolvedContext,
    ) -> None:
        """Match coverages to the claim."""
        loss_type = context.loss_type
        claimant_type = context.claimant_type

        # Sort coverages by ID for deterministic order
        sorted_coverages = sorted(policy.coverage_sections, key=lambda c: c.id)

        for coverage in sorted_coverages:
            if not coverage.enabled:
                continue

            match = CoverageMatch(
                coverage=coverage,
                triggered=False,
            )

            # Check if any trigger matches
            for trigger in coverage.triggers:
                # Check loss type
                if trigger.loss_type != loss_type:
                    continue

                # Check claimant type if specified
                if trigger.claimant_types:
                    if claimant_type not in trigger.claimant_types:
                        continue

                # Trigger matches!
                match.triggered = True
                match.trigger_loss_type = trigger.loss_type
                break

            # If triggered, check preconditions
            if match.triggered and coverage.preconditions:
                all_met = True
                for precond in coverage.preconditions:
                    result = self.evaluator.evaluate(precond, context)
                    match.precondition_results.append(result)

                    if result.value == TriBool.FALSE:
                        all_met = False
                    elif result.value == TriBool.UNKNOWN:
                        all_met = False
                        match.missing_facts.extend(result.missing_fact_keys)

                match.preconditions_met = all_met

            resolved.matched_coverages.append(match)

            # Add to triggered list if both triggered and preconditions met
            if match.triggered and match.preconditions_met:
                resolved.triggered_coverages.append(coverage)

    def _resolve_exclusions(
        self,
        policy: Policy,
        context: ClaimContext,
        resolved: ResolvedContext,
    ) -> None:
        """Evaluate exclusions against the claim."""
        triggered_coverage_ids = {c.id for c in resolved.triggered_coverages}

        # Sort exclusions by ID for deterministic order
        sorted_exclusions = sorted(policy.exclusions, key=lambda e: e.id)

        for exclusion in sorted_exclusions:
            if not exclusion.enabled:
                continue

            # Check if exclusion applies to any triggered coverage
            if exclusion.applies_to_coverages:
                # Empty list means applies to all
                applies = any(
                    cov_id in triggered_coverage_ids
                    for cov_id in exclusion.applies_to_coverages
                ) if exclusion.applies_to_coverages else True

                if not applies:
                    continue

            match = ExclusionMatch(
                exclusion=exclusion,
                triggered=TriBool.FALSE,
            )

            # Evaluate trigger conditions
            if exclusion.trigger_conditions:
                # All conditions must be TRUE for exclusion to trigger
                # (implicit AND over multiple conditions)
                all_true = True
                any_unknown = False

                for condition in exclusion.trigger_conditions:
                    result = self.evaluator.evaluate(condition, context)
                    match.trigger_results.append(result)

                    if result.value == TriBool.FALSE:
                        all_true = False
                    elif result.value == TriBool.UNKNOWN:
                        any_unknown = True
                        match.missing_facts.extend(result.missing_fact_keys)

                if all_true and not any_unknown:
                    match.triggered = TriBool.TRUE
                elif any_unknown and all_true:
                    # Could go either way
                    match.triggered = TriBool.UNKNOWN
                # else stays FALSE

            resolved.exclusion_matches.append(match)

            # Categorize
            if match.triggered == TriBool.TRUE:
                resolved.triggered_exclusions.append(exclusion)
            elif match.triggered == TriBool.UNKNOWN:
                resolved.potential_exclusions.append(exclusion)
                resolved.has_unknown_exclusions = True

    def _resolve_timeline_rules(
        self,
        policy: Policy,
        context: ClaimContext,
        resolved: ResolvedContext,
    ) -> None:
        """Collect applicable timeline rules."""
        # Get rule IDs from policy
        # In a real implementation, these would be looked up from an engine
        # For now, we just note which IDs apply
        # The actual TimelineRule objects would be fetched from PolicyEngine
        pass  # Timeline rules are fetched from PolicyEngine separately

    def _resolve_evidence_rules(
        self,
        policy: Policy,
        context: ClaimContext,
        resolved: ResolvedContext,
    ) -> None:
        """Collect applicable evidence rules."""
        # Evidence rules are fetched from PolicyEngine separately
        # They're matched by their applies_when conditions
        pass

    def _resolve_authority_rules(
        self,
        policy: Policy,
        context: ClaimContext,
        resolved: ResolvedContext,
    ) -> None:
        """Evaluate authority/escalation rules."""
        # Authority rules are fetched from PolicyEngine separately
        # Here we just track escalation requirements
        pass

    def _aggregate_missing_facts(self, resolved: ResolvedContext) -> None:
        """Collect all unique missing facts."""
        seen: set[str] = set()

        # From coverage matches
        for match in resolved.matched_coverages:
            for fact in match.missing_facts:
                if fact not in seen:
                    seen.add(fact)
                    resolved.all_missing_facts.append(fact)

        # From exclusion matches
        for match in resolved.exclusion_matches:
            for fact in match.missing_facts:
                if fact not in seen:
                    seen.add(fact)
                    resolved.all_missing_facts.append(fact)


# =============================================================================
# Extended Context Resolver (with PolicyEngine integration)
# =============================================================================

@dataclass
class FullContextResolver:
    """
    Extended resolver that integrates with PolicyEngine for rule lookups.

    This version fetches timeline, evidence, and authority rules from
    the engine and evaluates their applicability conditions.
    """

    evaluator: ConditionEvaluator = field(default_factory=ConditionEvaluator)

    def resolve(
        self,
        policy: Policy,
        context: ClaimContext,
        timeline_rules: list[TimelineRule],
        evidence_rules: list[EvidenceRule],
        authority_rules: list[AuthorityRule],
        as_of: Optional[date] = None,
    ) -> ResolvedContext:
        """
        Resolve context with full rule evaluation.

        Args:
            policy: The policy to evaluate
            context: The claim context
            timeline_rules: Available timeline rules
            evidence_rules: Available evidence rules
            authority_rules: Available authority rules
            as_of: Date for rule effectiveness

        Returns:
            Complete ResolvedContext
        """
        # Start with basic resolution
        basic_resolver = ContextResolver(evaluator=self.evaluator)
        resolved = basic_resolver.resolve(policy, context, as_of)

        # Add timeline rules that apply
        resolved.timeline_rules = self._filter_timeline_rules(
            timeline_rules, context, policy
        )

        # Add evidence rules that apply
        resolved.evidence_rules = self._filter_evidence_rules(
            evidence_rules, context, policy
        )

        # Add authority rules and check escalation
        resolved.authority_rules = self._filter_authority_rules(
            authority_rules, context, policy, resolved
        )

        return resolved

    def _filter_timeline_rules(
        self,
        rules: list[TimelineRule],
        context: ClaimContext,
        policy: Policy,
    ) -> list[TimelineRule]:
        """Filter timeline rules that apply to this context."""
        applicable: list[TimelineRule] = []

        # Sort by priority (descending) then ID for stability
        sorted_rules = sorted(
            rules,
            key=lambda r: (-r.priority, r.id)
        )

        for rule in sorted_rules:
            if not rule.enabled:
                continue

            # Check jurisdiction match
            if rule.jurisdiction and rule.jurisdiction != policy.jurisdiction:
                continue

            # Check line of business match
            if rule.line_of_business:
                if rule.line_of_business != policy.line_of_business.value:
                    continue

            # Check applies_when condition
            if rule.applies_when:
                result = self.evaluator.evaluate(rule.applies_when, context)
                if result.value != TriBool.TRUE:
                    continue

            applicable.append(rule)

        return applicable

    def _filter_evidence_rules(
        self,
        rules: list[EvidenceRule],
        context: ClaimContext,
        policy: Policy,
    ) -> list[EvidenceRule]:
        """Filter evidence rules that apply to this context."""
        applicable: list[EvidenceRule] = []

        # Sort by priority (descending) then ID
        sorted_rules = sorted(
            rules,
            key=lambda r: (-r.priority, r.id)
        )

        for rule in sorted_rules:
            if not rule.enabled:
                continue

            # Check jurisdiction
            if rule.jurisdiction and rule.jurisdiction != policy.jurisdiction:
                continue

            # Check line of business
            if rule.line_of_business:
                if rule.line_of_business != policy.line_of_business.value:
                    continue

            # Check applies_when condition
            if rule.applies_when:
                result = self.evaluator.evaluate(rule.applies_when, context)
                if result.value != TriBool.TRUE:
                    continue

            applicable.append(rule)

        return applicable

    def _filter_authority_rules(
        self,
        rules: list[AuthorityRule],
        context: ClaimContext,
        policy: Policy,
        resolved: ResolvedContext,
    ) -> list[AuthorityRule]:
        """Filter authority rules and determine escalation needs."""
        applicable: list[AuthorityRule] = []

        # Sort by priority (descending) then ID
        sorted_rules = sorted(
            rules,
            key=lambda r: (-r.priority, r.id)
        )

        for rule in sorted_rules:
            if not rule.enabled:
                continue

            # Authority rules typically have a trigger_condition_id
            # that references a condition in the policy
            # For inline conditions, we'd evaluate directly

            # If there's a trigger condition in the policy's conditions dict
            if rule.trigger_condition_id and policy.conditions:
                condition = policy.conditions.get(rule.trigger_condition_id)
                if condition:
                    result = self.evaluator.evaluate(condition, context)
                    if result.value == TriBool.TRUE:
                        applicable.append(rule)
                        resolved.requires_escalation = True
                        resolved.escalation_reasons.append(
                            f"{rule.name}: {rule.description}"
                        )

        return applicable


# =============================================================================
# Convenience Functions
# =============================================================================

def resolve_context(
    policy: Policy,
    context: ClaimContext,
    as_of: Optional[date] = None,
) -> ResolvedContext:
    """
    Resolve applicable rules for a claim context.

    Convenience function that creates a temporary resolver.

    Args:
        policy: The policy to evaluate
        context: The claim context
        as_of: Date for effectiveness check

    Returns:
        ResolvedContext with matches and evaluations
    """
    resolver = ContextResolver()
    return resolver.resolve(policy, context, as_of)


def get_triggered_coverages(
    policy: Policy,
    context: ClaimContext,
) -> list[CoverageSection]:
    """
    Get list of coverages triggered by a claim.

    Quick lookup without full resolution details.
    """
    resolved = resolve_context(policy, context)
    return resolved.triggered_coverages


def get_applicable_exclusions(
    policy: Policy,
    context: ClaimContext,
) -> tuple[list[Exclusion], list[Exclusion]]:
    """
    Get exclusions that apply to a claim.

    Returns:
        Tuple of (definitely_triggered, potentially_triggered)
    """
    resolved = resolve_context(policy, context)
    return (resolved.triggered_exclusions, resolved.potential_exclusions)
