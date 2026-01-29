"""
Tests for DecisionGraph Required Actions Module (v2.0)

Tests cover:
- Action rule creation and validation
- Trigger evaluation (verdict, signal, score, gate)
- Action generation from rules
- Action configuration from pack
- Generated action properties
"""

import pytest
from decimal import Decimal
from dataclasses import dataclass
from typing import List, Optional

from decisiongraph.actions import (
    # Exceptions
    ActionError,
    TriggerParseError,
    ActionConfigError,
    # Enums
    TriggerType,
    ActionPriority,
    # Data classes
    ActionRule,
    GeneratedAction,
    ActionConfig,
    # Evaluator
    TriggerEvaluator,
    # Generator
    ActionGenerator,
    # Convenience
    generate_required_actions,
    format_actions_for_report,
)
from decisiongraph.gates import GateResult, GateStatus


# =============================================================================
# ACTION RULE TESTS
# =============================================================================

class TestActionRule:
    """Tests for ActionRule."""

    def test_rule_creation(self):
        """Test creating an action rule."""
        rule = ActionRule(
            rule_id="test_rule",
            trigger='verdict == "ANALYST_REVIEW"',
            actions=["Review the case", "Document findings"],
            sla_hours=168
        )

        assert rule.rule_id == "test_rule"
        assert len(rule.actions) == 2
        assert rule.sla_hours == 168

    def test_rule_default_values(self):
        """Test default values for rule."""
        rule = ActionRule(
            rule_id="test",
            trigger="always",
            actions=["Do something"]
        )

        assert rule.sla_hours == 168
        assert rule.priority == ActionPriority.MEDIUM
        assert rule.enabled is True

    def test_rule_validation_no_id(self):
        """Test rule validation fails without ID."""
        with pytest.raises(ActionConfigError):
            ActionRule(rule_id="", trigger="always", actions=["test"])

    def test_rule_validation_no_trigger(self):
        """Test rule validation fails without trigger."""
        with pytest.raises(ActionConfigError):
            ActionRule(rule_id="test", trigger="", actions=["test"])

    def test_rule_validation_no_actions(self):
        """Test rule validation fails without actions."""
        with pytest.raises(ActionConfigError):
            ActionRule(rule_id="test", trigger="always", actions=[])

    def test_rule_to_dict(self):
        """Test rule serialization."""
        rule = ActionRule(
            rule_id="test",
            trigger='verdict == "TEST"',
            actions=["Action 1"],
            sla_hours=24,
            priority=ActionPriority.HIGH
        )

        d = rule.to_dict()
        assert d["rule_id"] == "test"
        assert d["sla_hours"] == 24
        assert d["priority"] == "HIGH"

    def test_rule_from_dict(self):
        """Test rule deserialization."""
        d = {
            "rule_id": "test",
            "trigger": "always",
            "actions": ["Test action"],
            "sla_hours": 48,
            "priority": "CRITICAL"
        }

        rule = ActionRule.from_dict(d)
        assert rule.rule_id == "test"
        assert rule.sla_hours == 48
        assert rule.priority == ActionPriority.CRITICAL


# =============================================================================
# GENERATED ACTION TESTS
# =============================================================================

class TestGeneratedAction:
    """Tests for GeneratedAction."""

    def test_action_creation(self):
        """Test creating a generated action."""
        action = GeneratedAction(
            description="Complete case review",
            sla_hours=168,
            priority=ActionPriority.MEDIUM,
            rule_id="test_rule",
            trigger_reason="Verdict is ANALYST_REVIEW"
        )

        assert action.description == "Complete case review"
        assert action.sla_hours == 168

    def test_sla_days(self):
        """Test SLA in days conversion."""
        action = GeneratedAction(
            description="Test",
            sla_hours=48,
            priority=ActionPriority.HIGH,
            rule_id="test",
            trigger_reason="test"
        )

        assert action.sla_days == 2.0

    def test_sla_business_days(self):
        """Test SLA in business days conversion."""
        action = GeneratedAction(
            description="Test",
            sla_hours=24,
            priority=ActionPriority.HIGH,
            rule_id="test",
            trigger_reason="test"
        )

        assert action.sla_business_days == 3.0

    def test_action_to_dict(self):
        """Test action serialization."""
        action = GeneratedAction(
            description="Test action",
            sla_hours=72,
            priority=ActionPriority.HIGH,
            rule_id="rule_1",
            trigger_reason="Signal fired",
            escalate_to="MANAGER"
        )

        d = action.to_dict()
        assert d["description"] == "Test action"
        assert d["escalate_to"] == "MANAGER"


# =============================================================================
# TRIGGER EVALUATOR TESTS
# =============================================================================

class TestTriggerEvaluator:
    """Tests for TriggerEvaluator."""

    def test_verdict_trigger_match(self):
        """Test verdict trigger matches."""
        evaluator = TriggerEvaluator()

        triggered, reason = evaluator.evaluate(
            trigger='verdict == "ANALYST_REVIEW"',
            verdict="ANALYST_REVIEW"
        )

        assert triggered is True
        assert "ANALYST_REVIEW" in reason

    def test_verdict_trigger_no_match(self):
        """Test verdict trigger doesn't match."""
        evaluator = TriggerEvaluator()

        triggered, reason = evaluator.evaluate(
            trigger='verdict == "ANALYST_REVIEW"',
            verdict="CLEAR_AND_CLOSE"
        )

        assert triggered is False

    def test_signal_trigger_match(self):
        """Test signal trigger matches."""
        evaluator = TriggerEvaluator()

        triggered, reason = evaluator.evaluate(
            trigger='signal == "SANCTIONS_POSSIBLE_MATCH"',
            signal_codes=["TXN_LARGE_CASH", "SANCTIONS_POSSIBLE_MATCH"]
        )

        assert triggered is True
        assert "SANCTIONS_POSSIBLE_MATCH" in reason

    def test_signal_trigger_no_match(self):
        """Test signal trigger doesn't match."""
        evaluator = TriggerEvaluator()

        triggered, reason = evaluator.evaluate(
            trigger='signal == "SANCTIONS_POSSIBLE_MATCH"',
            signal_codes=["TXN_LARGE_CASH"]
        )

        assert triggered is False

    def test_score_gt_trigger_match(self):
        """Test score > threshold trigger matches."""
        evaluator = TriggerEvaluator()

        triggered, reason = evaluator.evaluate(
            trigger="score > 0.75",
            residual_score=Decimal("0.80")
        )

        assert triggered is True

    def test_score_gt_trigger_no_match(self):
        """Test score > threshold trigger doesn't match."""
        evaluator = TriggerEvaluator()

        triggered, reason = evaluator.evaluate(
            trigger="score > 0.75",
            residual_score=Decimal("0.50")
        )

        assert triggered is False

    def test_score_gte_trigger(self):
        """Test score >= threshold trigger."""
        evaluator = TriggerEvaluator()

        triggered, _ = evaluator.evaluate(
            trigger="score >= 0.75",
            residual_score=Decimal("0.75")
        )

        assert triggered is True

    def test_score_lt_trigger(self):
        """Test score < threshold trigger."""
        evaluator = TriggerEvaluator()

        triggered, _ = evaluator.evaluate(
            trigger="score < 0.30",
            residual_score=Decimal("0.20")
        )

        assert triggered is True

    def test_score_lte_trigger(self):
        """Test score <= threshold trigger."""
        evaluator = TriggerEvaluator()

        triggered, _ = evaluator.evaluate(
            trigger="score <= 0.30",
            residual_score=Decimal("0.30")
        )

        assert triggered is True

    def test_gate_fail_trigger_match(self):
        """Test gate_fail trigger matches."""
        evaluator = TriggerEvaluator()

        triggered, reason = evaluator.evaluate(
            trigger="gate_fail == 4",
            failed_gates=[4]
        )

        assert triggered is True
        assert "Gate 4" in reason

    def test_gate_fail_trigger_no_match(self):
        """Test gate_fail trigger doesn't match."""
        evaluator = TriggerEvaluator()

        triggered, reason = evaluator.evaluate(
            trigger="gate_fail == 4",
            failed_gates=[1, 2]
        )

        assert triggered is False

    def test_always_trigger(self):
        """Test always trigger."""
        evaluator = TriggerEvaluator()

        triggered, reason = evaluator.evaluate(trigger="always")

        assert triggered is True
        assert "Always" in reason


# =============================================================================
# ACTION CONFIG TESTS
# =============================================================================

class TestActionConfig:
    """Tests for ActionConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = ActionConfig()

        assert config.default_sla_hours == 168
        assert len(config.rules) == 0

    def test_from_pack_empty(self):
        """Test loading from empty pack data."""
        config = ActionConfig.from_pack({})

        assert len(config.rules) == 0

    def test_from_pack_with_actions(self):
        """Test loading from pack with action rules."""
        pack_data = {
            "required_actions": [
                {
                    "rule_id": "test_1",
                    "trigger": 'verdict == "REVIEW"',
                    "actions": ["Review case"],
                    "sla_hours": 48
                },
                {
                    "rule_id": "test_2",
                    "trigger": "always",
                    "actions": ["Log activity"],
                    "sla_hours": 24
                }
            ]
        }

        config = ActionConfig.from_pack(pack_data)

        assert len(config.rules) == 2
        assert config.rules[0].sla_hours == 48

    def test_default_fincrime_config(self):
        """Test default FinCrime configuration."""
        config = ActionConfig.default_fincrime_config()

        assert len(config.rules) > 0
        # Should have verdict-based rules
        verdict_rules = [r for r in config.rules if "verdict" in r.trigger]
        assert len(verdict_rules) > 0

    def test_to_dict(self):
        """Test configuration serialization."""
        config = ActionConfig(rules=[
            ActionRule(
                rule_id="test",
                trigger="always",
                actions=["Test"]
            )
        ])

        d = config.to_dict()
        assert "required_actions" in d
        assert len(d["required_actions"]) == 1


# =============================================================================
# ACTION GENERATOR TESTS
# =============================================================================

class TestActionGenerator:
    """Tests for ActionGenerator."""

    def test_default_generator(self):
        """Test creating generator with defaults."""
        generator = ActionGenerator()
        assert generator.config is not None

    def test_generate_no_rules(self):
        """Test generation with no rules."""
        generator = ActionGenerator(ActionConfig())

        actions = generator.generate(verdict="ANALYST_REVIEW")

        assert len(actions) == 0

    def test_generate_verdict_match(self):
        """Test generation with matching verdict."""
        config = ActionConfig(rules=[
            ActionRule(
                rule_id="test",
                trigger='verdict == "ANALYST_REVIEW"',
                actions=["Review the case"],
                sla_hours=168
            )
        ])
        generator = ActionGenerator(config)

        actions = generator.generate(verdict="ANALYST_REVIEW")

        assert len(actions) == 1
        assert actions[0].description == "Review the case"

    def test_generate_multiple_actions(self):
        """Test generation with multiple actions per rule."""
        config = ActionConfig(rules=[
            ActionRule(
                rule_id="test",
                trigger='verdict == "REVIEW"',
                actions=["Action 1", "Action 2", "Action 3"],
                sla_hours=48
            )
        ])
        generator = ActionGenerator(config)

        actions = generator.generate(verdict="REVIEW")

        assert len(actions) == 3

    def test_generate_deduplicates(self):
        """Test that duplicate actions are deduplicated."""
        config = ActionConfig(rules=[
            ActionRule(
                rule_id="rule1",
                trigger='verdict == "REVIEW"',
                actions=["Same action"],
                sla_hours=48
            ),
            ActionRule(
                rule_id="rule2",
                trigger="always",
                actions=["Same action"],
                sla_hours=72
            )
        ])
        generator = ActionGenerator(config)

        actions = generator.generate(verdict="REVIEW")

        # Should be deduplicated
        assert len(actions) == 1

    def test_generate_sorted_by_priority(self):
        """Test that actions are sorted by priority."""
        config = ActionConfig(rules=[
            ActionRule(
                rule_id="low",
                trigger="always",
                actions=["Low priority"],
                priority=ActionPriority.LOW,
                sla_hours=168
            ),
            ActionRule(
                rule_id="critical",
                trigger="always",
                actions=["Critical priority"],
                priority=ActionPriority.CRITICAL,
                sla_hours=24
            ),
            ActionRule(
                rule_id="medium",
                trigger="always",
                actions=["Medium priority"],
                priority=ActionPriority.MEDIUM,
                sla_hours=72
            ),
        ])
        generator = ActionGenerator(config)

        actions = generator.generate()

        assert actions[0].priority == ActionPriority.CRITICAL
        assert actions[-1].priority == ActionPriority.LOW

    def test_generate_disabled_rules(self):
        """Test that disabled rules are skipped."""
        config = ActionConfig(rules=[
            ActionRule(
                rule_id="enabled",
                trigger="always",
                actions=["Enabled action"],
                enabled=True
            ),
            ActionRule(
                rule_id="disabled",
                trigger="always",
                actions=["Disabled action"],
                enabled=False
            )
        ])
        generator = ActionGenerator(config)

        actions = generator.generate()

        assert len(actions) == 1
        assert actions[0].description == "Enabled action"

    def test_compute_aggregate_sla(self):
        """Test aggregate SLA computation."""
        generator = ActionGenerator()

        actions = [
            GeneratedAction(
                description="A",
                sla_hours=168,
                priority=ActionPriority.MEDIUM,
                rule_id="1",
                trigger_reason=""
            ),
            GeneratedAction(
                description="B",
                sla_hours=24,
                priority=ActionPriority.CRITICAL,
                rule_id="2",
                trigger_reason=""
            ),
        ]

        assert generator.compute_aggregate_sla(actions) == 24

    def test_get_escalation_role(self):
        """Test escalation role lookup."""
        generator = ActionGenerator()

        role = generator.get_escalation_role("ANALYST_REVIEW")
        assert role == "ANALYST"

        role = generator.get_escalation_role("STR_CONSIDERATION")
        assert role == "COMPLIANCE_OFFICER"


class TestGenerateFromEvalResult:
    """Tests for generate_from_eval_result method."""

    @dataclass
    class MockFact:
        object: dict

    @dataclass
    class MockCell:
        fact: "TestGenerateFromEvalResult.MockFact"

    @dataclass
    class MockEvalResult:
        verdict: Optional["TestGenerateFromEvalResult.MockCell"] = None
        signals: List["TestGenerateFromEvalResult.MockCell"] = None
        score: Optional["TestGenerateFromEvalResult.MockCell"] = None

        def __post_init__(self):
            if self.signals is None:
                self.signals = []

    def test_generate_from_eval_result(self):
        """Test generation from evaluation result."""
        config = ActionConfig(rules=[
            ActionRule(
                rule_id="test",
                trigger='verdict == "ANALYST_REVIEW"',
                actions=["Review case"],
                sla_hours=168
            )
        ])
        generator = ActionGenerator(config)

        eval_result = self.MockEvalResult(
            verdict=self.MockCell(
                fact=self.MockFact(object={"verdict": "ANALYST_REVIEW"})
            )
        )

        actions = generator.generate_from_eval_result(eval_result)

        assert len(actions) == 1


# =============================================================================
# CONVENIENCE FUNCTION TESTS
# =============================================================================

class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_generate_required_actions(self):
        """Test generate_required_actions function."""
        actions = generate_required_actions(
            verdict="TEST",
            config=ActionConfig()
        )

        assert isinstance(actions, list)

    def test_format_actions_for_report(self):
        """Test format_actions_for_report function."""
        actions = [
            GeneratedAction(
                description="Test action",
                sla_hours=48,
                priority=ActionPriority.HIGH,
                rule_id="test",
                trigger_reason="test",
                escalate_to="MANAGER"
            )
        ]

        lines = format_actions_for_report(actions)

        assert any("REQUIRED ACTIONS" in line for line in lines)
        assert any("Test action" in line for line in lines)
        assert any("[HIGH]" in line for line in lines)
        assert any("48 hours" in line for line in lines)

    def test_format_actions_empty(self):
        """Test formatting empty actions list."""
        lines = format_actions_for_report([])

        assert any("(none)" in line for line in lines)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
