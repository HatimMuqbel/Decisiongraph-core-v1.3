"""
ClaimPilot Authority Router

Routes claims to appropriate authority levels for approval/review.

Key features:
- Evaluate authority rules against claim context
- Determine required approval roles
- Track escalation reasons
- Support multiple escalation levels
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ..models import (
    AuthorityRule,
    ClaimContext,
    Condition,
    EvaluationResult,
    Policy,
    TriBool,
)
from .condition_evaluator import ConditionEvaluator


# =============================================================================
# Authority/Escalation Levels
# =============================================================================

# Standard role hierarchy (can be customized per organization)
STANDARD_ROLE_HIERARCHY = [
    "adjuster",
    "senior_adjuster",
    "supervisor",
    "manager",
    "director",
    "siu",  # Special Investigation Unit
    "legal",
    "executive",
]


@dataclass
class RoleRequirement:
    """A required role with its trigger reason."""
    role: str
    rule_id: str
    rule_name: str
    reason: str
    priority: int
    triggered_by: Optional[EvaluationResult] = None


@dataclass
class AuthorityRoutingResult:
    """
    Result of authority routing evaluation.

    Contains the minimum required role and all triggered requirements.
    """
    # Primary result
    requires_escalation: bool = False
    minimum_role: str = "adjuster"  # Default role

    # All triggered requirements (sorted by priority)
    triggered_requirements: list[RoleRequirement] = field(default_factory=list)

    # Grouped by role
    requirements_by_role: dict[str, list[RoleRequirement]] = field(default_factory=dict)

    # Evaluation metadata
    evaluated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    evaluated_rules: list[str] = field(default_factory=list)
    claim_id: str = ""

    def get_escalation_summary(self) -> str:
        """Get a human-readable escalation summary."""
        if not self.requires_escalation:
            return "No escalation required"

        reasons = [r.reason for r in self.triggered_requirements[:3]]
        more = len(self.triggered_requirements) - 3
        summary = f"Escalation to {self.minimum_role}: " + "; ".join(reasons)
        if more > 0:
            summary += f" (+{more} more reasons)"
        return summary


# =============================================================================
# Authority Router
# =============================================================================

@dataclass
class AuthorityRouter:
    """
    Routes claims to appropriate authority levels.

    Evaluates authority rules to determine:
    - Whether escalation is required
    - What role level is needed
    - Why escalation is required

    Usage:
        router = AuthorityRouter()

        result = router.route(
            rules=authority_rules,
            context=claim_context,
            policy=policy,
        )

        if result.requires_escalation:
            print(f"Needs: {result.minimum_role}")
            for req in result.triggered_requirements:
                print(f"  - {req.reason}")
    """

    # Condition evaluator
    evaluator: ConditionEvaluator = field(default_factory=ConditionEvaluator)

    # Role hierarchy (lower index = lower authority)
    role_hierarchy: list[str] = field(
        default_factory=lambda: STANDARD_ROLE_HIERARCHY.copy()
    )

    # Default role if no escalation
    default_role: str = "adjuster"

    def route(
        self,
        rules: list[AuthorityRule],
        context: ClaimContext,
        policy: Optional[Policy] = None,
        current_role: Optional[str] = None,
    ) -> AuthorityRoutingResult:
        """
        Evaluate authority rules and determine routing.

        Args:
            rules: Authority rules to evaluate
            context: Claim context
            policy: Optional policy for condition lookups
            current_role: Current user's role (to check if escalation needed)

        Returns:
            AuthorityRoutingResult with escalation requirements
        """
        result = AuthorityRoutingResult(
            claim_id=context.claim_id,
        )

        # Sort rules by priority (descending) then ID for determinism
        sorted_rules = sorted(
            rules,
            key=lambda r: (-r.priority, r.id)
        )

        # Evaluate each rule
        for rule in sorted_rules:
            if not rule.enabled:
                continue

            result.evaluated_rules.append(rule.id)

            # Get the trigger condition
            condition = self._get_trigger_condition(rule, policy)
            if condition is None:
                continue

            # Evaluate condition
            eval_result = self.evaluator.evaluate(condition, context)

            if eval_result.value == TriBool.TRUE:
                # Rule triggered
                req = RoleRequirement(
                    role=rule.required_role,
                    rule_id=rule.id,
                    rule_name=rule.name,
                    reason=rule.description or rule.name,
                    priority=rule.priority,
                    triggered_by=eval_result,
                )
                result.triggered_requirements.append(req)

                # Add to role grouping
                if rule.required_role not in result.requirements_by_role:
                    result.requirements_by_role[rule.required_role] = []
                result.requirements_by_role[rule.required_role].append(req)

        # Determine minimum required role
        if result.triggered_requirements:
            result.requires_escalation = True
            result.minimum_role = self._get_highest_role(
                [r.role for r in result.triggered_requirements]
            )

            # Check if escalation is relative to current role
            if current_role:
                current_level = self._get_role_level(current_role)
                required_level = self._get_role_level(result.minimum_role)
                result.requires_escalation = required_level > current_level
        else:
            result.minimum_role = self.default_role

        return result

    def _get_trigger_condition(
        self,
        rule: AuthorityRule,
        policy: Optional[Policy],
    ) -> Optional[Condition]:
        """Get the trigger condition for a rule."""
        # Check for condition ID reference
        if rule.trigger_condition_id and policy and policy.conditions:
            return policy.conditions.get(rule.trigger_condition_id)

        # No inline condition support in current AuthorityRule model
        # Could be extended in future
        return None

    def _get_role_level(self, role: str) -> int:
        """Get the authority level of a role (higher = more authority)."""
        try:
            return self.role_hierarchy.index(role)
        except ValueError:
            # Unknown role, put at end
            return len(self.role_hierarchy)

    def _get_highest_role(self, roles: list[str]) -> str:
        """Get the highest authority role from a list."""
        if not roles:
            return self.default_role

        return max(roles, key=self._get_role_level)

    def check_authorization(
        self,
        rules: list[AuthorityRule],
        context: ClaimContext,
        user_role: str,
        policy: Optional[Policy] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a user's role is authorized to process a claim.

        Args:
            rules: Authority rules
            context: Claim context
            user_role: User's current role
            policy: Optional policy for condition lookups

        Returns:
            Tuple of (authorized: bool, required_role: Optional[str])
        """
        result = self.route(rules, context, policy, user_role)

        if not result.requires_escalation:
            return (True, None)

        # Check if user's role meets requirement
        user_level = self._get_role_level(user_role)
        required_level = self._get_role_level(result.minimum_role)

        if user_level >= required_level:
            return (True, None)
        else:
            return (False, result.minimum_role)

    def get_escalation_chain(
        self,
        from_role: str,
        to_role: str,
    ) -> list[str]:
        """
        Get the escalation chain from one role to another.

        Returns list of roles in the escalation path.
        """
        from_level = self._get_role_level(from_role)
        to_level = self._get_role_level(to_role)

        if from_level >= to_level:
            return []

        return self.role_hierarchy[from_level + 1:to_level + 1]


# =============================================================================
# SIU Referral Helper
# =============================================================================

@dataclass
class SIUReferralResult:
    """Result of SIU (Special Investigation Unit) referral check."""
    requires_siu: bool = False
    referral_reasons: list[str] = field(default_factory=list)
    fraud_score: Optional[float] = None
    fraud_indicators: list[str] = field(default_factory=list)


def check_siu_referral(
    context: ClaimContext,
    fraud_score_threshold: float = 70.0,
) -> SIUReferralResult:
    """
    Check if a claim should be referred to SIU.

    Looks for common fraud indicators in the claim context.
    """
    result = SIUReferralResult()

    # Check fraud score in facts
    fraud_score_fact = context.facts.get("fraud_score")
    if fraud_score_fact:
        result.fraud_score = float(fraud_score_fact.value)
        if result.fraud_score >= fraud_score_threshold:
            result.requires_siu = True
            result.referral_reasons.append(
                f"Fraud score {result.fraud_score} exceeds threshold {fraud_score_threshold}"
            )

    # Check explicit fraud indicators
    fraud_indicators_fact = context.facts.get("fraud_indicators")
    if fraud_indicators_fact and fraud_indicators_fact.value:
        result.requires_siu = True
        result.referral_reasons.append("Fraud indicators flagged")
        if isinstance(fraud_indicators_fact.value, list):
            result.fraud_indicators = fraud_indicators_fact.value

    # Check for suspicious patterns in metadata
    if context.metadata.get("suspicious_claim"):
        result.requires_siu = True
        result.referral_reasons.append("Claim marked as suspicious")

    return result


# =============================================================================
# Convenience Functions
# =============================================================================

def route_authority(
    rules: list[AuthorityRule],
    context: ClaimContext,
    policy: Optional[Policy] = None,
) -> AuthorityRoutingResult:
    """
    Route a claim to appropriate authority level.

    Convenience function that creates a temporary router.
    """
    router = AuthorityRouter()
    return router.route(rules, context, policy)


def get_required_role(
    rules: list[AuthorityRule],
    context: ClaimContext,
    policy: Optional[Policy] = None,
) -> str:
    """
    Get the minimum required role for a claim.

    Quick lookup without full routing details.
    """
    result = route_authority(rules, context, policy)
    return result.minimum_role


def requires_escalation(
    rules: list[AuthorityRule],
    context: ClaimContext,
    current_role: str,
    policy: Optional[Policy] = None,
) -> bool:
    """
    Check if escalation is required for a claim.

    Returns True if the claim requires a higher authority than current_role.
    """
    router = AuthorityRouter()
    result = router.route(rules, context, policy, current_role)
    return result.requires_escalation
