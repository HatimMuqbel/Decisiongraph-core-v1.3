"""
Template Loader for Build Your Own Case feature.

Loads and manages case templates from YAML files.
"""

import yaml
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# In-memory cache for BYOC evaluations (for memo generation)
_byoc_cache: dict[str, dict] = {}


def cache_byoc_evaluation(eval_id: str, data: dict):
    """Cache a BYOC evaluation for memo generation."""
    _byoc_cache[eval_id] = data
    if len(_byoc_cache) > 100:
        oldest = next(iter(_byoc_cache))
        del _byoc_cache[oldest]


def get_byoc_evaluation(eval_id: str) -> dict | None:
    """Get cached BYOC evaluation."""
    return _byoc_cache.get(eval_id)


class TemplateLoader:
    """Loads and caches case templates."""

    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir
        self.templates: dict[str, dict] = {}

    def load_all(self) -> int:
        """Load all templates from the templates directory."""
        if not self.templates_dir.exists():
            print(f"Templates directory not found: {self.templates_dir}")
            return 0

        loaded = 0
        for yaml_file in self.templates_dir.glob("*.yaml"):
            try:
                template = self._load_template(yaml_file)
                if template:
                    template_id = template.get("template_id")
                    if template_id:
                        self.templates[template_id] = template
                        loaded += 1
            except Exception as e:
                print(f"  [ERROR] Failed to load template {yaml_file.name}: {e}")

        return loaded

    def _load_template(self, path: Path) -> dict | None:
        """Load a single template file."""
        with open(path, "r") as f:
            template = yaml.safe_load(f)
        return template

    def get_template(self, template_id: str) -> dict | None:
        """Get a template by ID."""
        return self.templates.get(template_id)

    def list_templates(self) -> list[dict]:
        """List all templates with summary info."""
        result = []
        for tid, template in self.templates.items():
            result.append({
                "template_id": tid,
                "title": template.get("ui", {}).get("title", tid),
                "domain": template.get("domain", "unknown"),
                "version": template.get("template_version", "1.0.0"),
                "policy_pack_id": template.get("policy_pack_id") or template.get("reg_pack_id"),
            })
        return result

    def get_template_for_ui(self, template_id: str) -> dict | None:
        """Get template formatted for UI rendering."""
        template = self.get_template(template_id)
        if not template:
            return None

        # Build UI-ready structure
        return {
            "template_id": template.get("template_id"),
            "template_version": template.get("template_version"),
            "domain": template.get("domain"),
            "policy_pack_id": template.get("policy_pack_id") or template.get("reg_pack_id"),
            "policy_pack_version": template.get("policy_pack_version") or template.get("reg_pack_version"),
            "ui": template.get("ui", {}),
            "fields": template.get("fields", {}),
            "field_groups": template.get("field_groups", []),
            "evidence": template.get("evidence", []),
            "visibility_rules": template.get("visibility_rules", []),
            "disable_rules": template.get("disable_rules", []),
            "expected_outcomes": template.get("expected_outcomes", []),
        }

    def evaluate_with_template(self, template_id: str, facts: dict, evidence: dict) -> dict:
        """
        Evaluate facts against template decision rules.

        Returns a decision result with reasoning chain.
        """
        template = self.get_template(template_id)
        if not template:
            return {"error": f"Template not found: {template_id}"}

        decision_rules = template.get("decision_rules", [])
        evidence_rules = template.get("evidence_rules", [])

        reasoning_chain = []
        warnings = []
        step = 1

        # Check evidence requirements first
        for rule in evidence_rules:
            condition = rule.get("when", {})
            if self._evaluate_condition(condition, facts):
                required = rule.get("require_evidence", [])
                missing_behavior = rule.get("missing_behavior", "warn")
                for doc_id in required:
                    if evidence.get(doc_id) not in ["provided", "verified", True]:
                        warning_text = f"Missing: {doc_id}"
                        if missing_behavior == "downgrade_certainty":
                            warning_text += " — certainty downgraded"
                        elif missing_behavior == "block":
                            warning_text += " — REQUIRED"
                        warnings.append({
                            "code": "MISSING_EVIDENCE",
                            "doc_id": doc_id,
                            "behavior": missing_behavior,
                            "text": warning_text
                        })

        # Evaluate decision rules in order (first match wins)
        matched_outcome = None
        for rule in decision_rules:
            condition = rule.get("when", {})

            # Check if this is the default rule
            if condition.get("default"):
                if not matched_outcome:
                    matched_outcome = rule.get("outcome")
                    reasoning_chain.append({
                        "step": step,
                        "status": "pass",
                        "text": "Default rule applied — no exclusions triggered"
                    })
                continue

            # Evaluate the condition
            if self._evaluate_condition(condition, facts):
                matched_outcome = rule.get("outcome")
                reasoning_chain.append({
                    "step": step,
                    "status": "fail" if matched_outcome.get("severity") == "critical" else "warn",
                    "text": f"{matched_outcome.get('code')}: {', '.join(matched_outcome.get('citations', []))}"
                })
                break
            else:
                # Rule didn't match - record as passed check
                outcome = rule.get("outcome", {})
                citations = outcome.get("citations", [])
                if citations:
                    reasoning_chain.append({
                        "step": step,
                        "status": "pass",
                        "text": f"Checked: {citations[0]} — not triggered"
                    })
            step += 1

        if not matched_outcome:
            matched_outcome = {
                "decision": "unknown",
                "code": "NO_RULE_MATCHED",
                "label": "UNKNOWN",
                "severity": "warning",
                "citations": []
            }

        # Determine certainty based on warnings
        certainty = "high"
        if any(w.get("behavior") == "downgrade_certainty" for w in warnings):
            certainty = "medium"
        if any(w.get("behavior") == "block" for w in warnings):
            certainty = "low"

        # Generate decision_id for memo caching
        decision_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + "Z"

        result = {
            "decision_id": decision_id,
            "decision": matched_outcome.get("decision"),
            "decision_label": matched_outcome.get("label"),
            "decision_code": matched_outcome.get("code"),
            "severity": matched_outcome.get("severity"),
            "certainty": certainty,
            "citations": [{"ref": c, "title": c} for c in matched_outcome.get("citations", [])],
            "reasoning_chain": reasoning_chain,
            "warnings": warnings,
            "version_pins": {
                "template_id": template.get("template_id"),
                "template_version": template.get("template_version"),
                "policy_pack_id": template.get("policy_pack_id") or template.get("reg_pack_id"),
                "policy_pack_version": template.get("policy_pack_version") or template.get("reg_pack_version"),
            }
        }

        # Cache for memo generation
        cache_byoc_evaluation(decision_id, {
            "decision_id": decision_id,
            "timestamp": timestamp,
            "template": template,
            "facts": facts,
            "evidence": evidence,
            "result": result,
            "reasoning_chain": reasoning_chain,
            "warnings": warnings,
        })

        return result

    def _evaluate_condition(self, condition: dict, facts: dict) -> bool:
        """Evaluate a condition against facts."""
        if not condition:
            return False

        # Handle different condition types
        if "eq" in condition:
            field, expected = condition["eq"]
            actual = facts.get(field)
            return actual == expected

        if "ne" in condition:
            field, expected = condition["ne"]
            actual = facts.get(field)
            return actual != expected

        if "in" in condition:
            field, values = condition["in"]
            actual = facts.get(field)
            return actual in values

        # YAML parses 'true:' as boolean True key, not string "true"
        if True in condition or "true" in condition:
            fields = condition.get(True) or condition.get("true")
            return all(facts.get(f) is True for f in fields)

        if False in condition or "false" in condition:
            fields = condition.get(False) or condition.get("false")
            return all(facts.get(f) is False for f in fields)

        if "and" in condition:
            return all(self._evaluate_condition(c, facts) for c in condition["and"])

        if "or" in condition:
            return any(self._evaluate_condition(c, facts) for c in condition["or"])

        if "default" in condition:
            return condition["default"]

        return False
