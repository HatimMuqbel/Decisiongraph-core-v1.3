"""
ClaimPilot Policy Pack Loader

Loads and validates policy packs from YAML or JSON files.

Converts Pydantic schema models to ClaimPilot domain models.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Union

import yaml
from pydantic import ValidationError

from ..exceptions import PolicyLoadError, PolicyValidationError, PolicyVersionMismatch
from ..models import (
    AuthorityRef,
    AuthorityRule,
    AuthorityType,
    ClaimantType,
    Condition,
    ConditionOperator,
    CoverageLimits,
    CoverageSection,
    Deductibles,
    DispositionType,
    DocumentRequirement,
    EvidenceRule,
    Exclusion,
    GateStrictness,
    LineOfBusiness,
    LossTypeTrigger,
    Policy,
    Predicate,
    TimelineAnchor,
    TimelineEventType,
    TimelineRule,
)
from .schema import (
    SCHEMA_VERSION,
    AuthorityRefSchema,
    AuthorityRuleSchema,
    ConditionSchema,
    CoverageLimitsSchema,
    CoverageSectionSchema,
    DeductiblesSchema,
    DocumentRequirementSchema,
    EvidenceRuleSchema,
    ExclusionSchema,
    LossTypeTriggerSchema,
    PolicyPackSchema,
    TimelineRuleSchema,
    check_schema_version,
    validate_policy_pack,
)


# =============================================================================
# Reference Integrity Validation
# =============================================================================

def validate_reference_integrity(policy: Policy, path: str = "") -> None:
    """
    Validate internal references are consistent.

    Catches:
    - Exclusions referencing non-existent coverages
    - Duplicate coverage IDs
    - Duplicate exclusion IDs

    Args:
        policy: The policy to validate
        path: File path for error messages

    Raises:
        ValueError: If reference integrity errors are found
    """
    errors = []

    # Collect valid coverage IDs
    coverage_ids = {c.id for c in policy.coverage_sections}

    # Check exclusion references
    for exc in policy.exclusions:
        for cov_id in exc.applies_to_coverages:
            if cov_id not in coverage_ids:
                errors.append(
                    f"Exclusion '{exc.id}' references non-existent coverage '{cov_id}'"
                )

    # Check for duplicate coverage IDs
    seen_coverage_ids: set[str] = set()
    for cov in policy.coverage_sections:
        if cov.id in seen_coverage_ids:
            errors.append(f"Duplicate coverage ID: '{cov.id}'")
        seen_coverage_ids.add(cov.id)

    # Check for duplicate exclusion IDs
    seen_exclusion_ids: set[str] = set()
    for exc in policy.exclusions:
        if exc.id in seen_exclusion_ids:
            errors.append(f"Duplicate exclusion ID: '{exc.id}'")
        seen_exclusion_ids.add(exc.id)

    if errors:
        path_str = f" in {path}" if path else ""
        raise ValueError(
            f"Reference integrity errors{path_str}:\n" +
            "\n".join(f"  - {e}" for e in errors)
        )


# =============================================================================
# Schema to Model Converters
# =============================================================================

def _convert_condition(schema: ConditionSchema) -> Condition:
    """Convert ConditionSchema to Condition model."""
    op = ConditionOperator(schema.op)
    logical_ops = {ConditionOperator.AND, ConditionOperator.OR, ConditionOperator.NOT}

    if op in logical_ops:
        # Logical condition with children
        children = [_convert_condition(c) for c in (schema.children or [])]
        return Condition(
            op=op,
            children=children,
            id=schema.id,
            description=schema.description,
        )
    else:
        # Leaf predicate
        predicate = Predicate(
            field=schema.field or "",
            operator=op,
            value=schema.value,
            description=schema.description,
        )
        return Condition(
            op=op,
            predicate=predicate,
            id=schema.id,
            description=schema.description,
        )


def _convert_authority_ref(schema: AuthorityRefSchema) -> AuthorityRef:
    """Convert AuthorityRefSchema to AuthorityRef model."""
    return AuthorityRef(
        id=schema.id,
        authority_type=AuthorityType(schema.type),
        title=schema.title,
        section=schema.section,
        source_name=schema.source_name,
        source_uri=schema.source_uri,
        jurisdiction=schema.jurisdiction,
        effective_date=schema.effective_date,
        expiry_date=schema.expiry_date,
        quote_excerpt=schema.quote_excerpt,
        full_text=schema.full_text,
    )


def _convert_authority_rule(schema: AuthorityRuleSchema) -> AuthorityRule:
    """Convert AuthorityRuleSchema to AuthorityRule model."""
    return AuthorityRule(
        id=schema.id,
        name=schema.name,
        description=schema.description,
        required_role=schema.required_role,
        trigger_condition_id=schema.trigger_condition_id,
        priority=schema.priority,
        enabled=schema.enabled,
    )


def _convert_coverage_limits(schema: Optional[CoverageLimitsSchema]) -> Optional[CoverageLimits]:
    """Convert CoverageLimitsSchema to CoverageLimits model."""
    if schema is None:
        return None
    return CoverageLimits(
        per_occurrence=schema.per_occurrence,
        per_person=schema.per_person,
        per_accident=schema.per_accident,
        aggregate=schema.aggregate,
        property_damage=schema.property_damage,
        bodily_injury=schema.bodily_injury,
        currency=schema.currency,
    )


def _convert_deductibles(schema: Optional[DeductiblesSchema]) -> Optional[Deductibles]:
    """Convert DeductiblesSchema to Deductibles model."""
    if schema is None:
        return None
    return Deductibles(
        standard=schema.standard,
        collision=schema.collision,
        comprehensive=schema.comprehensive,
        per_claim=schema.per_claim,
        per_occurrence=schema.per_occurrence,
        annual_aggregate=schema.annual_aggregate,
        currency=schema.currency,
    )


def _convert_loss_trigger(schema: LossTypeTriggerSchema) -> LossTypeTrigger:
    """Convert LossTypeTriggerSchema to LossTypeTrigger model."""
    return LossTypeTrigger(
        loss_type=schema.loss_type,
        claimant_types=[ClaimantType(ct) for ct in schema.claimant_types],
    )


def _convert_coverage_section(schema: CoverageSectionSchema) -> CoverageSection:
    """Convert CoverageSectionSchema to CoverageSection model."""
    return CoverageSection(
        id=schema.id,
        code=schema.code,
        name=schema.name,
        description=schema.description,
        triggers=[_convert_loss_trigger(t) for t in schema.triggers],
        preconditions=[_convert_condition(c) for c in schema.preconditions],
        limits=_convert_coverage_limits(schema.limits),
        deductibles=_convert_deductibles(schema.deductibles),
        exclusion_ids=schema.exclusion_ids,
        effective_date=schema.effective_date,
        expiry_date=schema.expiry_date,
        enabled=schema.enabled,
    )


def _convert_exclusion(schema: ExclusionSchema) -> Exclusion:
    """Convert ExclusionSchema to Exclusion model."""
    return Exclusion(
        id=schema.id,
        code=schema.code,
        name=schema.name,
        description=schema.description,
        policy_wording=schema.policy_wording,
        policy_section_ref=schema.policy_section_ref,
        applies_to_coverages=schema.applies_to_coverages,
        trigger_conditions=[_convert_condition(c) for c in schema.trigger_conditions],
        evaluation_questions=schema.evaluation_questions,
        evidence_to_confirm=schema.evidence_to_confirm,
        evidence_to_rule_out=schema.evidence_to_rule_out,
        severity=schema.severity,
        enabled=schema.enabled,
    )


def _convert_timeline_rule(schema: TimelineRuleSchema) -> TimelineRule:
    """Convert TimelineRuleSchema to TimelineRule model."""
    return TimelineRule(
        id=schema.id,
        name=schema.name,
        event_type=TimelineEventType(schema.event_type),
        anchor=TimelineAnchor(schema.anchor),
        days_from_anchor=schema.days_from_anchor,
        business_days=schema.business_days,
        description=schema.description,
        penalty_description=schema.penalty_description,
        applies_when=_convert_condition(schema.applies_when) if schema.applies_when else None,
        applies_when_id=schema.applies_when_id,
        jurisdiction=schema.jurisdiction,
        line_of_business=schema.line_of_business,
        enabled=schema.enabled,
        priority=schema.priority,
    )


def _convert_document_requirement(schema: DocumentRequirementSchema) -> DocumentRequirement:
    """Convert DocumentRequirementSchema to DocumentRequirement model."""
    return DocumentRequirement(
        doc_type=schema.doc_type,
        description=schema.description,
        strictness=GateStrictness(schema.strictness),
        alternatives=schema.alternatives,
        condition_id=schema.condition_id,
        applies_when=_convert_condition(schema.applies_when) if schema.applies_when else None,
    )


def _convert_evidence_rule(schema: EvidenceRuleSchema) -> EvidenceRule:
    """Convert EvidenceRuleSchema to EvidenceRule model."""
    return EvidenceRule(
        id=schema.id,
        name=schema.name,
        description=schema.description,
        disposition_type=DispositionType(schema.disposition_type) if schema.disposition_type else None,
        applies_when=_convert_condition(schema.applies_when) if schema.applies_when else None,
        applies_when_id=schema.applies_when_id,
        required_documents=[_convert_document_requirement(d) for d in schema.required_documents],
        recommended_documents=[_convert_document_requirement(d) for d in schema.recommended_documents],
        jurisdiction=schema.jurisdiction,
        line_of_business=schema.line_of_business,
        enabled=schema.enabled,
        priority=schema.priority,
    )


def _convert_policy_pack(schema: PolicyPackSchema) -> Policy:
    """Convert PolicyPackSchema to Policy model."""
    # Build conditions dictionary
    conditions_dict: dict[str, Condition] = {}
    for cond_schema in schema.conditions:
        if cond_schema.id:
            conditions_dict[cond_schema.id] = _convert_condition(cond_schema)

    return Policy(
        id=schema.id,
        jurisdiction=schema.jurisdiction,
        line_of_business=LineOfBusiness(schema.line_of_business),
        product_code=schema.product_code,
        name=schema.name,
        version=schema.version,
        effective_date=schema.effective_date,
        expiry_date=schema.expiry_date,
        description=schema.description,
        issuer=schema.issuer,
        regulatory_body=schema.regulatory_body,
        coverage_sections=[_convert_coverage_section(c) for c in schema.coverage_sections],
        exclusions=[_convert_exclusion(e) for e in schema.exclusions],
        conditions=conditions_dict,
        timeline_rule_ids=[r.id for r in schema.timeline_rules],
        evidence_rule_ids=[r.id for r in schema.evidence_rules],
        authority_rule_ids=[r.id for r in schema.authority_rules],
    )


# =============================================================================
# Policy Pack Loader
# =============================================================================

class PolicyPackLoader:
    """
    Loads policy packs from YAML or JSON files.

    Usage:
        loader = PolicyPackLoader()
        policy = loader.load("path/to/policy.yaml")
    """

    def __init__(self, strict_version: bool = True):
        """
        Initialize the loader.

        Args:
            strict_version: If True, reject packs with incompatible schema versions
        """
        self.strict_version = strict_version

        # Caches for loaded components
        self._policies: dict[str, Policy] = {}
        self._authorities: dict[str, AuthorityRef] = {}
        self._timeline_rules: dict[str, TimelineRule] = {}
        self._evidence_rules: dict[str, EvidenceRule] = {}
        self._authority_rules: dict[str, AuthorityRule] = {}

    def load(self, path: Union[str, Path]) -> Policy:
        """
        Load a policy pack from a file.

        Args:
            path: Path to YAML or JSON file

        Returns:
            Loaded Policy model

        Raises:
            PolicyLoadError: If file cannot be read
            PolicyValidationError: If validation fails
            PolicyVersionMismatch: If schema version incompatible
        """
        path = Path(path)

        # Load raw data
        try:
            data = self._load_file(path)
        except Exception as e:
            raise PolicyLoadError(
                message=f"Failed to load policy pack: {e}",
                details={"path": str(path), "error": str(e)},
            )

        # Check schema version
        if self.strict_version and not check_schema_version(data):
            pack_version = data.get("schema_version", "unknown")
            raise PolicyVersionMismatch(
                message=f"Schema version mismatch: pack has {pack_version}, expected {SCHEMA_VERSION}",
                details={
                    "pack_version": pack_version,
                    "expected_version": SCHEMA_VERSION,
                },
            )

        # Validate against schema
        try:
            schema = validate_policy_pack(data)
        except ValidationError as e:
            raise PolicyValidationError(
                message=f"Policy pack validation failed: {e.error_count()} errors",
                details={"errors": e.errors(), "path": str(path)},
            )

        # Convert to domain models
        policy = _convert_policy_pack(schema)

        # Validate reference integrity
        try:
            validate_reference_integrity(policy, str(path))
        except ValueError as e:
            raise PolicyValidationError(
                message=f"Reference integrity validation failed",
                details={"errors": str(e), "path": str(path)},
            )

        # Cache authorities
        for auth_schema in schema.authorities:
            auth = _convert_authority_ref(auth_schema)
            self._authorities[auth.id] = auth

        # Cache timeline rules
        for rule_schema in schema.timeline_rules:
            rule = _convert_timeline_rule(rule_schema)
            self._timeline_rules[rule.id] = rule

        # Cache evidence rules
        for rule_schema in schema.evidence_rules:
            rule = _convert_evidence_rule(rule_schema)
            self._evidence_rules[rule.id] = rule

        # Cache authority rules
        for rule_schema in schema.authority_rules:
            rule = _convert_authority_rule(rule_schema)
            self._authority_rules[rule.id] = rule

        # Cache policy
        self._policies[policy.id] = policy

        return policy

    def _load_file(self, path: Path) -> dict[str, Any]:
        """Load data from YAML or JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            if path.suffix.lower() in {".yaml", ".yml"}:
                return yaml.safe_load(f)
            elif path.suffix.lower() == ".json":
                return json.load(f)
            else:
                # Try YAML first, then JSON
                content = f.read()
                try:
                    return yaml.safe_load(content)
                except yaml.YAMLError:
                    return json.loads(content)

    def get_policy(self, policy_id: str) -> Optional[Policy]:
        """Get a cached policy by ID."""
        return self._policies.get(policy_id)

    def get_authority(self, authority_id: str) -> Optional[AuthorityRef]:
        """Get a cached authority reference by ID."""
        return self._authorities.get(authority_id)

    def get_timeline_rule(self, rule_id: str) -> Optional[TimelineRule]:
        """Get a cached timeline rule by ID."""
        return self._timeline_rules.get(rule_id)

    def get_evidence_rule(self, rule_id: str) -> Optional[EvidenceRule]:
        """Get a cached evidence rule by ID."""
        return self._evidence_rules.get(rule_id)

    def get_authority_rule(self, rule_id: str) -> Optional[AuthorityRule]:
        """Get a cached authority rule by ID."""
        return self._authority_rules.get(rule_id)

    def list_policies(self) -> list[str]:
        """List IDs of all loaded policies."""
        return list(self._policies.keys())


# =============================================================================
# Convenience Functions
# =============================================================================

def load_policy_pack(path: Union[str, Path]) -> Policy:
    """
    Load a policy pack from a file.

    Convenience function that creates a temporary loader.

    Args:
        path: Path to YAML or JSON file

    Returns:
        Loaded Policy model
    """
    loader = PolicyPackLoader()
    return loader.load(path)


def load_policy_pack_from_string(
    content: str,
    format: str = "yaml",
) -> Policy:
    """
    Load a policy pack from a string.

    Args:
        content: YAML or JSON string
        format: "yaml" or "json"

    Returns:
        Loaded Policy model
    """
    if format.lower() == "json":
        data = json.loads(content)
    else:
        data = yaml.safe_load(content)

    schema = validate_policy_pack(data)
    return _convert_policy_pack(schema)
