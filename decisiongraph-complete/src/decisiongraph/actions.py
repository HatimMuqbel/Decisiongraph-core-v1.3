"""
DecisionGraph Required Actions Module (v2.0)

Generates required follow-up actions based on evaluation results.
Actions are triggered by verdict outcomes, signal codes, or score thresholds.

Pack authors can define action rules with:
- Trigger conditions (verdict, signal, score threshold)
- Action descriptions
- SLA (Service Level Agreement) hours

USAGE:
    from decisiongraph.actions import (
        ActionRule, ActionConfig, ActionGenerator, GeneratedAction
    )

    # Load action config from pack
    config = ActionConfig.from_pack(pack_data)

    # Create generator
    generator = ActionGenerator(config)

    # Generate actions from evaluation result
    actions = generator.generate(
        verdict="ANALYST_REVIEW",
        signal_codes=["TXN_LARGE_CASH", "GEO_HIGH_RISK"],
        residual_score=Decimal("0.75")
    )

    for action in actions:
        print(f"- {action.description} (SLA: {action.sla_hours}h)")
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import re


# =============================================================================
# EXCEPTIONS
# =============================================================================

class ActionError(Exception):
    """Base exception for action errors."""
    pass


class TriggerParseError(ActionError):
    """Raised when trigger expression cannot be parsed."""
    pass


class ActionConfigError(ActionError):
    """Raised when action configuration is invalid."""
    pass


# =============================================================================
# ENUMS
# =============================================================================

class TriggerType(str, Enum):
    """Types of action triggers."""
    VERDICT = "verdict"           # Trigger on specific verdict
    SIGNAL = "signal"             # Trigger on signal code
    SCORE_ABOVE = "score_above"   # Trigger when score above threshold
    SCORE_BELOW = "score_below"   # Trigger when score below threshold
    GATE_FAIL = "gate_fail"       # Trigger when gate fails
    ALWAYS = "always"             # Always trigger


class ActionPriority(str, Enum):
    """Priority levels for actions."""
    CRITICAL = "CRITICAL"   # Immediate action required
    HIGH = "HIGH"           # Same day
    MEDIUM = "MEDIUM"       # Within SLA
    LOW = "LOW"             # Best effort


# =============================================================================
# ACTION RULE
# =============================================================================

@dataclass
class ActionRule:
    """
    A rule that triggers required actions.

    Trigger syntax:
    - verdict == "ANALYST_REVIEW"
    - signal == "SANCTIONS_POSSIBLE_MATCH"
    - score > 0.75
    - gate_fail == 4
    - always
    """
    rule_id: str
    trigger: str                  # Trigger expression
    actions: List[str]            # Action descriptions
    sla_hours: int = 168          # Default 7 days
    priority: ActionPriority = ActionPriority.MEDIUM
    escalate_to: Optional[str] = None  # Role to escalate to
    enabled: bool = True

    def __post_init__(self):
        if not self.rule_id:
            raise ActionConfigError("Action rule must have rule_id")
        if not self.trigger:
            raise ActionConfigError("Action rule must have trigger")
        if not self.actions:
            raise ActionConfigError("Action rule must have at least one action")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "trigger": self.trigger,
            "actions": self.actions,
            "sla_hours": self.sla_hours,
            "priority": self.priority.value,
            "escalate_to": self.escalate_to,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any], index: int = 0) -> "ActionRule":
        """Create ActionRule from dict."""
        return cls(
            rule_id=d.get("rule_id", f"action_{index}"),
            trigger=d.get("trigger", ""),
            actions=d.get("actions", []),
            sla_hours=d.get("sla_hours", 168),
            priority=ActionPriority(d.get("priority", "MEDIUM")),
            escalate_to=d.get("escalate_to"),
            enabled=d.get("enabled", True),
        )


# =============================================================================
# GENERATED ACTION
# =============================================================================

@dataclass
class GeneratedAction:
    """
    A generated action from rule evaluation.

    Contains the action description, SLA, and source rule information.
    """
    description: str
    sla_hours: int
    priority: ActionPriority
    rule_id: str
    trigger_reason: str           # What triggered this action
    escalate_to: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "sla_hours": self.sla_hours,
            "priority": self.priority.value,
            "rule_id": self.rule_id,
            "trigger_reason": self.trigger_reason,
            "escalate_to": self.escalate_to,
        }

    @property
    def sla_days(self) -> float:
        """Return SLA in days."""
        return self.sla_hours / 24

    @property
    def sla_business_days(self) -> float:
        """Return SLA in business days (assuming 8-hour days)."""
        return self.sla_hours / 8


# =============================================================================
# ACTION CONFIG
# =============================================================================

@dataclass
class ActionConfig:
    """
    Configuration for action generation.

    Contains all action rules and default settings.
    """
    rules: List[ActionRule] = field(default_factory=list)
    default_sla_hours: int = 168  # 7 days
    default_priority: ActionPriority = ActionPriority.MEDIUM
    # Role escalation mapping
    escalation_roles: Dict[str, str] = field(default_factory=lambda: {
        "ANALYST_REVIEW": "ANALYST",
        "SENIOR_REVIEW": "SENIOR_ANALYST",
        "COMPLIANCE_ESCALATION": "COMPLIANCE_OFFICER",
        "STR_CONSIDERATION": "COMPLIANCE_OFFICER",
        "CLEAR_AND_CLOSE": None,
    })

    @classmethod
    def from_pack(cls, pack_data: Dict[str, Any]) -> "ActionConfig":
        """
        Load action configuration from pack data.

        Args:
            pack_data: Pack YAML data with optional 'required_actions' section

        Returns:
            ActionConfig with rules from pack
        """
        actions_data = pack_data.get("required_actions", [])
        rules = []

        for i, rule_data in enumerate(actions_data):
            try:
                rule = ActionRule.from_dict(rule_data, i)
                rules.append(rule)
            except ActionConfigError:
                # Skip invalid rules but log (in production)
                continue

        # Load escalation roles if provided
        escalation = pack_data.get("escalation_roles", {})

        return cls(
            rules=rules,
            default_sla_hours=pack_data.get("default_sla_hours", 168),
            escalation_roles={**cls().escalation_roles, **escalation},
        )

    @classmethod
    def default_fincrime_config(cls) -> "ActionConfig":
        """
        Create default FinCrime action configuration.

        Provides sensible defaults for AML/KYC case processing.
        """
        return cls(rules=[
            # Verdict-based actions
            ActionRule(
                rule_id="verdict_analyst_review",
                trigger='verdict == "ANALYST_REVIEW"',
                actions=[
                    "Complete case review and document findings",
                    "Update customer risk rating if warranted",
                ],
                sla_hours=168,
                priority=ActionPriority.MEDIUM,
                escalate_to="ANALYST",
            ),
            ActionRule(
                rule_id="verdict_senior_review",
                trigger='verdict == "SENIOR_REVIEW"',
                actions=[
                    "Senior analyst review required",
                    "Document escalation rationale",
                ],
                sla_hours=72,
                priority=ActionPriority.HIGH,
                escalate_to="SENIOR_ANALYST",
            ),
            ActionRule(
                rule_id="verdict_str_consideration",
                trigger='verdict == "STR_CONSIDERATION"',
                actions=[
                    "Formal STR determination required",
                    "Document grounds for reasonable suspicion",
                    "Escalate to Compliance Officer",
                ],
                sla_hours=120,
                priority=ActionPriority.HIGH,
                escalate_to="COMPLIANCE_OFFICER",
            ),
            # Signal-based actions
            ActionRule(
                rule_id="signal_sanctions",
                trigger='signal == "SANCTIONS_POSSIBLE_MATCH"',
                actions=[
                    "Escalate to Sanctions Compliance immediately",
                    "Obtain additional documentation from customer",
                    "Do not process further transactions",
                ],
                sla_hours=24,
                priority=ActionPriority.CRITICAL,
                escalate_to="SANCTIONS_COMPLIANCE",
            ),
            ActionRule(
                rule_id="signal_pep",
                trigger='signal == "PEP_MATCH"',
                actions=[
                    "Verify PEP status with enhanced due diligence",
                    "Document source of wealth",
                ],
                sla_hours=72,
                priority=ActionPriority.HIGH,
                escalate_to="SENIOR_ANALYST",
            ),
            # Score-based actions
            ActionRule(
                rule_id="score_high_risk",
                trigger="score > 0.80",
                actions=[
                    "High-risk case requires enhanced monitoring",
                    "Consider relationship review",
                ],
                sla_hours=48,
                priority=ActionPriority.HIGH,
            ),
        ])

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for pack export."""
        return {
            "required_actions": [r.to_dict() for r in self.rules],
            "default_sla_hours": self.default_sla_hours,
            "escalation_roles": self.escalation_roles,
        }


# =============================================================================
# TRIGGER EVALUATOR
# =============================================================================

class TriggerEvaluator:
    """
    Evaluates trigger expressions against case data.

    Supports:
    - verdict == "VALUE"
    - signal == "CODE"
    - score > 0.75, score >= 0.75, score < 0.25, score <= 0.25
    - gate_fail == N
    - always
    """

    # Regex patterns for trigger parsing
    VERDICT_PATTERN = re.compile(r'verdict\s*==\s*["\'](\w+)["\']')
    SIGNAL_PATTERN = re.compile(r'signal\s*==\s*["\'](\w+)["\']')
    SCORE_GT_PATTERN = re.compile(r'score\s*>\s*([\d.]+)')
    SCORE_GTE_PATTERN = re.compile(r'score\s*>=\s*([\d.]+)')
    SCORE_LT_PATTERN = re.compile(r'score\s*<\s*([\d.]+)')
    SCORE_LTE_PATTERN = re.compile(r'score\s*<=\s*([\d.]+)')
    GATE_FAIL_PATTERN = re.compile(r'gate_fail\s*==\s*(\d+)')
    ALWAYS_PATTERN = re.compile(r'always')

    def evaluate(
        self,
        trigger: str,
        verdict: Optional[str] = None,
        signal_codes: Optional[List[str]] = None,
        residual_score: Optional[Decimal] = None,
        failed_gates: Optional[List[int]] = None,
    ) -> tuple[bool, str]:
        """
        Evaluate a trigger expression.

        Args:
            trigger: Trigger expression string
            verdict: Current verdict code
            signal_codes: List of fired signal codes
            residual_score: Residual risk score
            failed_gates: List of failed gate numbers

        Returns:
            (triggered: bool, reason: str)
        """
        trigger = trigger.strip()
        signal_codes = signal_codes or []
        failed_gates = failed_gates or []

        # Check for 'always' trigger
        if self.ALWAYS_PATTERN.match(trigger):
            return True, "Always triggered"

        # Check verdict trigger
        match = self.VERDICT_PATTERN.match(trigger)
        if match:
            expected_verdict = match.group(1)
            if verdict == expected_verdict:
                return True, f"Verdict is {verdict}"
            return False, ""

        # Check signal trigger
        match = self.SIGNAL_PATTERN.match(trigger)
        if match:
            expected_signal = match.group(1)
            if expected_signal in signal_codes:
                return True, f"Signal {expected_signal} fired"
            return False, ""

        # Check score > threshold
        match = self.SCORE_GT_PATTERN.match(trigger)
        if match:
            threshold = Decimal(match.group(1))
            if residual_score is not None and residual_score > threshold:
                return True, f"Score {residual_score} > {threshold}"
            return False, ""

        # Check score >= threshold
        match = self.SCORE_GTE_PATTERN.match(trigger)
        if match:
            threshold = Decimal(match.group(1))
            if residual_score is not None and residual_score >= threshold:
                return True, f"Score {residual_score} >= {threshold}"
            return False, ""

        # Check score < threshold
        match = self.SCORE_LT_PATTERN.match(trigger)
        if match:
            threshold = Decimal(match.group(1))
            if residual_score is not None and residual_score < threshold:
                return True, f"Score {residual_score} < {threshold}"
            return False, ""

        # Check score <= threshold
        match = self.SCORE_LTE_PATTERN.match(trigger)
        if match:
            threshold = Decimal(match.group(1))
            if residual_score is not None and residual_score <= threshold:
                return True, f"Score {residual_score} <= {threshold}"
            return False, ""

        # Check gate_fail trigger
        match = self.GATE_FAIL_PATTERN.match(trigger)
        if match:
            gate_num = int(match.group(1))
            if gate_num in failed_gates:
                return True, f"Gate {gate_num} failed"
            return False, ""

        # Unknown trigger format
        return False, ""


# =============================================================================
# ACTION GENERATOR
# =============================================================================

class ActionGenerator:
    """
    Generates required actions from evaluation results.

    Evaluates action rules against case data and produces
    a list of required actions with SLAs.
    """

    def __init__(self, config: Optional[ActionConfig] = None):
        """
        Initialize generator with configuration.

        Args:
            config: Action configuration (uses defaults if None)
        """
        self.config = config or ActionConfig()
        self.trigger_evaluator = TriggerEvaluator()

    def generate(
        self,
        verdict: Optional[str] = None,
        signal_codes: Optional[List[str]] = None,
        residual_score: Optional[Decimal] = None,
        failed_gates: Optional[List[int]] = None,
    ) -> List[GeneratedAction]:
        """
        Generate required actions from case data.

        Args:
            verdict: Current verdict code
            signal_codes: List of fired signal codes
            residual_score: Residual risk score
            failed_gates: List of failed gate numbers

        Returns:
            List of GeneratedAction objects
        """
        actions = []
        signal_codes = signal_codes or []
        failed_gates = failed_gates or []

        for rule in self.config.rules:
            if not rule.enabled:
                continue

            triggered, reason = self.trigger_evaluator.evaluate(
                trigger=rule.trigger,
                verdict=verdict,
                signal_codes=signal_codes,
                residual_score=residual_score,
                failed_gates=failed_gates,
            )

            if triggered:
                for action_desc in rule.actions:
                    actions.append(GeneratedAction(
                        description=action_desc,
                        sla_hours=rule.sla_hours,
                        priority=rule.priority,
                        rule_id=rule.rule_id,
                        trigger_reason=reason,
                        escalate_to=rule.escalate_to,
                    ))

        # Deduplicate actions by description
        seen = set()
        unique_actions = []
        for action in actions:
            if action.description not in seen:
                seen.add(action.description)
                unique_actions.append(action)

        # Sort by priority (CRITICAL first) then SLA
        priority_order = {
            ActionPriority.CRITICAL: 0,
            ActionPriority.HIGH: 1,
            ActionPriority.MEDIUM: 2,
            ActionPriority.LOW: 3,
        }
        unique_actions.sort(key=lambda a: (priority_order[a.priority], a.sla_hours))

        return unique_actions

    def generate_from_eval_result(
        self,
        eval_result: Any,
        gate_results: Optional[List[Any]] = None,
    ) -> List[GeneratedAction]:
        """
        Generate actions from evaluation result.

        Convenience method that extracts data from eval_result.

        Args:
            eval_result: EvaluationResult from rules engine
            gate_results: List of GateResult objects

        Returns:
            List of GeneratedAction objects
        """
        verdict = None
        signal_codes = []
        residual_score = None
        failed_gates = []

        if eval_result:
            # Extract verdict
            if hasattr(eval_result, 'verdict') and eval_result.verdict:
                verdict_obj = eval_result.verdict.fact.object
                verdict = verdict_obj.get("verdict")

            # Extract signal codes
            if hasattr(eval_result, 'signals') and eval_result.signals:
                signal_codes = [
                    s.fact.object.get("code", "")
                    for s in eval_result.signals
                ]

            # Extract residual score
            if hasattr(eval_result, 'score') and eval_result.score:
                score_obj = eval_result.score.fact.object
                score_str = score_obj.get("residual_score", "0")
                residual_score = Decimal(str(score_str))

        # Extract failed gates
        if gate_results:
            from .gates import GateStatus
            failed_gates = [
                g.gate_number for g in gate_results
                if g.status == GateStatus.FAIL
            ]

        return self.generate(
            verdict=verdict,
            signal_codes=signal_codes,
            residual_score=residual_score,
            failed_gates=failed_gates,
        )

    def get_escalation_role(self, verdict: str) -> Optional[str]:
        """
        Get escalation role for a verdict.

        Args:
            verdict: Verdict code

        Returns:
            Role name or None
        """
        return self.config.escalation_roles.get(verdict)

    def compute_aggregate_sla(self, actions: List[GeneratedAction]) -> int:
        """
        Compute aggregate SLA from actions.

        Returns the minimum SLA (most urgent) from the list.

        Args:
            actions: List of generated actions

        Returns:
            Minimum SLA hours
        """
        if not actions:
            return self.config.default_sla_hours

        return min(a.sla_hours for a in actions)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def generate_required_actions(
    verdict: Optional[str] = None,
    signal_codes: Optional[List[str]] = None,
    residual_score: Optional[Decimal] = None,
    config: Optional[ActionConfig] = None,
) -> List[GeneratedAction]:
    """
    Convenience function to generate required actions.

    Args:
        verdict: Current verdict code
        signal_codes: List of fired signal codes
        residual_score: Residual risk score
        config: Optional action configuration

    Returns:
        List of GeneratedAction objects
    """
    generator = ActionGenerator(config)
    return generator.generate(
        verdict=verdict,
        signal_codes=signal_codes,
        residual_score=residual_score,
    )


def format_actions_for_report(
    actions: List[GeneratedAction],
    line_width: int = 72
) -> List[str]:
    """
    Format actions for report output.

    Args:
        actions: List of generated actions
        line_width: Report line width

    Returns:
        List of formatted lines
    """
    lines = []
    lines.append("=" * line_width)
    lines.append("REQUIRED ACTIONS")
    lines.append("=" * line_width)

    if not actions:
        lines.append("  (none)")
        lines.append("")
        return lines

    # Group by priority
    for i, action in enumerate(actions, 1):
        priority_marker = ""
        if action.priority == ActionPriority.CRITICAL:
            priority_marker = " [CRITICAL]"
        elif action.priority == ActionPriority.HIGH:
            priority_marker = " [HIGH]"

        lines.append(f"  {i}. {action.description}{priority_marker}")

        if action.escalate_to:
            lines.append(f"     Escalate to: {action.escalate_to}")

    lines.append("")

    # Compute and show aggregate SLA
    if actions:
        min_sla = min(a.sla_hours for a in actions)
        lines.append(f"SLA: {min_sla} hours")

    lines.append("")
    return lines


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Exceptions
    'ActionError',
    'TriggerParseError',
    'ActionConfigError',
    # Enums
    'TriggerType',
    'ActionPriority',
    # Data classes
    'ActionRule',
    'GeneratedAction',
    'ActionConfig',
    # Evaluator
    'TriggerEvaluator',
    # Generator
    'ActionGenerator',
    # Convenience
    'generate_required_actions',
    'format_actions_for_report',
]
