"""
ClaimPilot Policy Pack Schemas

Pydantic models for validating policy pack YAML/JSON files.

These schemas define the structure of policy packs that can be loaded
at runtime. They map to the domain models in claimpilot.models.

Schema versioning:
- schema_version field tracks breaking changes
- Loaders should check version compatibility

Focus: Ontario, Canada insurance regulations (FSRA, Insurance Act)
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# Schema Version
# =============================================================================

SCHEMA_VERSION = "1.0.0"


# =============================================================================
# Enums as Literals (for YAML validation)
# =============================================================================

LineOfBusinessType = Literal[
    "auto", "property", "health", "workers_comp",
    "liability", "marine", "life", "professional", "cyber", "other"
]

ClaimantTypeValue = Literal[
    "insured", "named_insured", "additional_insured",
    "third_party", "claimant", "beneficiary", "assignee"
]

DispositionTypeValue = Literal[
    "pay", "deny", "partial", "escalate", "request_info",
    "hold", "refer_siu", "subrogation", "reserve_only", "close_no_pay"
]

AuthorityTypeValue = Literal[
    "policy_wording", "regulation", "statute", "internal_guideline",
    "industry_standard", "case_law", "regulator_bulletin", "internal_memo"
]

GateStrictnessValue = Literal[
    "blocking_recommendation", "blocking_finalization", "recommended", "optional"
]

ConditionOperatorValue = Literal[
    "and", "or", "not",
    "eq", "ne", "gt", "lt", "gte", "lte",
    "in", "not_in", "contains", "starts_with", "ends_with",
    "matches", "is_null", "is_not_null", "is_empty", "is_not_empty", "between"
]

TimelineAnchorValue = Literal[
    "loss_date", "report_date", "acknowledgment_date",
    "last_activity_date", "evidence_received_date",
    "coverage_decision_date", "claim_assigned_date"
]

TimelineEventTypeValue = Literal[
    "acknowledge", "request_info", "coverage_decision_due",
    "payment_due", "denial_notice_due", "appeal_window_opens",
    "appeal_window_closes", "regulatory_report_due", "statute_of_limitations",
    "reservation_of_rights_due"
]


# =============================================================================
# Base Schemas
# =============================================================================

class PredicateSchema(BaseModel):
    """Schema for a condition predicate (leaf comparison)."""
    field: str = Field(..., description="Dot-notation field path (e.g., 'claim.amount')")
    operator: ConditionOperatorValue = Field(..., description="Comparison operator")
    value: Any = Field(..., description="Value to compare against")
    description: Optional[str] = Field(None, description="Human-readable description")


class ConditionSchema(BaseModel):
    """
    Schema for a composable condition.

    For logical operators (and, or, not), use children.
    For comparison operators, use predicate fields directly.
    """
    op: ConditionOperatorValue = Field(..., description="Operator")

    # For logical composition
    children: Optional[list["ConditionSchema"]] = Field(
        None, description="Child conditions for AND/OR/NOT"
    )

    # For leaf predicates (alternative to children)
    field: Optional[str] = Field(None, description="Field path for comparison")
    value: Optional[Any] = Field(None, description="Value for comparison")

    # Metadata
    id: Optional[str] = Field(None, description="Condition ID for references")
    description: Optional[str] = Field(None, description="Human-readable description")

    @model_validator(mode="after")
    def validate_structure(self) -> "ConditionSchema":
        """Validate condition structure based on operator type."""
        logical_ops = {"and", "or", "not"}

        if self.op in logical_ops:
            if not self.children:
                raise ValueError(f"Logical operator '{self.op}' requires 'children'")
            if self.op == "not" and len(self.children) != 1:
                raise ValueError("NOT operator must have exactly one child")
        else:
            # Comparison operator
            if self.field is None:
                raise ValueError(f"Comparison operator '{self.op}' requires 'field'")

        return self


# =============================================================================
# Authority Schemas
# =============================================================================

class AuthorityRefSchema(BaseModel):
    """Schema for an authority reference (citation)."""
    id: str = Field(..., description="Unique identifier")
    type: AuthorityTypeValue = Field(..., description="Type of authority")
    title: str = Field(..., description="Title of the authority")
    section: str = Field(..., description="Section/paragraph reference")
    source_name: str = Field(..., description="Source document/system name")
    source_uri: Optional[str] = Field(None, description="URL/URI to source")
    jurisdiction: Optional[str] = Field(None, description="Applicable jurisdiction (e.g., CA-ON)")
    effective_date: Optional[date] = Field(None, description="When authority became effective")
    expiry_date: Optional[date] = Field(None, description="When authority expires")
    quote_excerpt: Optional[str] = Field(None, description="Short excerpt for display")
    full_text: Optional[str] = Field(None, description="Full text for hashing")


class AuthorityRuleSchema(BaseModel):
    """Schema for an authority/escalation rule."""
    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="When this rule applies")
    required_role: str = Field(..., description="Role required to approve")
    trigger_condition_id: Optional[str] = Field(None, description="ID of trigger condition")
    trigger_condition: Optional[ConditionSchema] = Field(None, description="Inline condition")
    authority_ref_id: Optional[str] = Field(None, description="Reference to authority")
    priority: int = Field(0, description="Higher priority rules evaluated first")
    enabled: bool = Field(True, description="Whether rule is active")


# =============================================================================
# Coverage Schemas
# =============================================================================

class CoverageLimitsSchema(BaseModel):
    """Schema for coverage limits."""
    per_occurrence: Optional[Decimal] = None
    per_person: Optional[Decimal] = None
    per_accident: Optional[Decimal] = None
    aggregate: Optional[Decimal] = None
    property_damage: Optional[Decimal] = None
    bodily_injury: Optional[Decimal] = None
    currency: str = Field("CAD", description="Currency code (default: CAD for Ontario)")


class DeductiblesSchema(BaseModel):
    """Schema for deductibles."""
    standard: Optional[Decimal] = None
    collision: Optional[Decimal] = None
    comprehensive: Optional[Decimal] = None
    per_claim: Optional[Decimal] = None
    per_occurrence: Optional[Decimal] = None
    annual_aggregate: Optional[Decimal] = None
    currency: str = Field("CAD", description="Currency code")


class LossTypeTriggerSchema(BaseModel):
    """Schema for a loss type trigger."""
    loss_type: str = Field(..., description="Loss type that triggers coverage")
    claimant_types: list[ClaimantTypeValue] = Field(
        default_factory=list,
        description="Claimant types (empty = all)"
    )


class CoverageSectionSchema(BaseModel):
    """Schema for a coverage section within a policy."""
    id: str = Field(..., description="Unique identifier")
    code: str = Field(..., description="Section code (e.g., 'Section A')")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Coverage description")
    triggers: list[LossTypeTriggerSchema] = Field(
        default_factory=list,
        description="Loss types that activate this coverage"
    )
    preconditions: list[ConditionSchema] = Field(
        default_factory=list,
        description="Conditions for coverage to apply"
    )
    limits: Optional[CoverageLimitsSchema] = None
    deductibles: Optional[DeductiblesSchema] = None
    authority_ref_id: Optional[str] = Field(None, description="Reference to authority")
    exclusion_ids: list[str] = Field(
        default_factory=list,
        description="IDs of exclusions for this coverage"
    )
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    enabled: bool = Field(True)


# =============================================================================
# Exclusion Schemas
# =============================================================================

class ExclusionSchema(BaseModel):
    """Schema for a policy exclusion."""
    id: str = Field(..., description="Unique identifier")
    code: str = Field(..., description="Policy reference code (e.g., '4.2.1')")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Exclusion description")
    policy_wording: str = Field(..., description="Actual policy language")
    policy_section_ref: str = Field(..., description="Reference to policy section")
    applies_to_coverages: list[str] = Field(
        default_factory=list,
        description="Coverage IDs this exclusion can negate"
    )
    trigger_conditions: list[ConditionSchema] = Field(
        default_factory=list,
        description="When to evaluate this exclusion"
    )
    evaluation_questions: list[str] = Field(
        default_factory=list,
        description="Questions for adjuster guidance"
    )
    evidence_to_confirm: list[str] = Field(
        default_factory=list,
        description="Evidence needed to confirm exclusion"
    )
    evidence_to_rule_out: list[str] = Field(
        default_factory=list,
        description="Evidence needed to rule out exclusion"
    )
    authority_ref_id: Optional[str] = None
    severity: str = Field("standard", description="Severity level")
    enabled: bool = Field(True)


# =============================================================================
# Timeline Schemas
# =============================================================================

class TimelineRuleSchema(BaseModel):
    """
    Schema for a timeline rule.

    Ontario-specific: FSRA requires specific timelines for claim handling.
    """
    id: str = Field(..., description="Unique identifier")
    name: Optional[str] = Field(None, description="Human-readable name")
    event_type: TimelineEventTypeValue = Field(..., description="Type of event")
    anchor: TimelineAnchorValue = Field(..., description="Reference point")
    days_from_anchor: int = Field(..., description="Days from anchor (can be negative)")
    business_days: bool = Field(False, description="True = business days, False = calendar")
    description: str = Field("", description="Description")
    penalty_description: Optional[str] = Field(None, description="What happens if missed")
    authority_ref_id: Optional[str] = None
    applies_when_id: Optional[str] = Field(None, description="Condition ID")
    applies_when: Optional[ConditionSchema] = Field(None, description="Inline condition")
    jurisdiction: Optional[str] = Field("CA-ON", description="Jurisdiction")
    line_of_business: Optional[str] = None
    enabled: bool = Field(True)
    priority: int = Field(0)


# =============================================================================
# Evidence Schemas
# =============================================================================

class DocumentRequirementSchema(BaseModel):
    """Schema for a document requirement."""
    doc_type: str = Field(..., description="Document type identifier")
    description: str = Field(..., description="Human-readable description")
    strictness: GateStrictnessValue = Field(
        "blocking_finalization",
        description="How strictly enforced"
    )
    alternatives: list[str] = Field(
        default_factory=list,
        description="Acceptable substitute documents"
    )
    condition_id: Optional[str] = None
    applies_when: Optional[ConditionSchema] = None


class EvidenceRuleSchema(BaseModel):
    """Schema for an evidence requirement rule."""
    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Human-readable name")
    description: str = Field("", description="Description")
    disposition_type: Optional[DispositionTypeValue] = Field(
        None, description="Applies to this disposition (None = all)"
    )
    applies_when_id: Optional[str] = None
    applies_when: Optional[ConditionSchema] = None
    required_documents: list[DocumentRequirementSchema] = Field(default_factory=list)
    recommended_documents: list[DocumentRequirementSchema] = Field(default_factory=list)
    authority_ref_id: Optional[str] = None
    jurisdiction: Optional[str] = Field("CA-ON")
    line_of_business: Optional[str] = None
    enabled: bool = Field(True)
    priority: int = Field(0)


# =============================================================================
# Policy Pack Schema (Top-Level)
# =============================================================================

class PolicyPackSchema(BaseModel):
    """
    Top-level schema for a policy pack YAML/JSON file.

    A policy pack defines all rules for a specific insurance product
    in a specific jurisdiction.
    """
    # Metadata
    schema_version: str = Field(SCHEMA_VERSION, description="Schema version for compatibility")
    id: str = Field(..., description="Unique identifier (e.g., 'CA-ON-OAP1-2024')")
    jurisdiction: str = Field(..., description="Jurisdiction (e.g., 'CA-ON' for Ontario)")
    line_of_business: LineOfBusinessType = Field(..., description="Insurance line")
    product_code: str = Field(..., description="Product identifier (e.g., 'OAP1')")
    name: str = Field(..., description="Human-readable name")
    version: str = Field(..., description="Version string (e.g., '2024.1')")
    effective_date: date = Field(..., description="When this version is effective")
    expiry_date: Optional[date] = Field(None, description="When this version expires")

    # Optional metadata
    description: Optional[str] = None
    issuer: Optional[str] = Field(None, description="Insurance company")
    regulatory_body: Optional[str] = Field(
        "FSRA", description="Regulatory body (default: FSRA for Ontario)"
    )

    # Authorities (citations)
    authorities: list[AuthorityRefSchema] = Field(
        default_factory=list,
        description="Authority references for citations"
    )

    # Reusable conditions
    conditions: list[ConditionSchema] = Field(
        default_factory=list,
        description="Reusable condition definitions"
    )

    # Coverage and exclusions
    coverage_sections: list[CoverageSectionSchema] = Field(
        default_factory=list,
        description="Coverage sections"
    )
    exclusions: list[ExclusionSchema] = Field(
        default_factory=list,
        description="Policy exclusions"
    )

    # Rules
    timeline_rules: list[TimelineRuleSchema] = Field(
        default_factory=list,
        description="Regulatory timeline requirements"
    )
    evidence_rules: list[EvidenceRuleSchema] = Field(
        default_factory=list,
        description="Evidence requirements"
    )
    authority_rules: list[AuthorityRuleSchema] = Field(
        default_factory=list,
        description="Escalation/authority rules"
    )

    @field_validator("jurisdiction")
    @classmethod
    def validate_jurisdiction(cls, v: str) -> str:
        """Validate jurisdiction format."""
        # Expected format: XX-YY (country-province/state)
        if "-" not in v and len(v) != 2:
            # Allow 2-letter country codes or XX-YY format
            pass  # Flexible for now
        return v.upper()

    model_config = {
        "extra": "forbid",  # Reject unknown fields
    }


# =============================================================================
# Validation Helpers
# =============================================================================

def validate_policy_pack(data: dict[str, Any]) -> PolicyPackSchema:
    """
    Validate a policy pack dictionary against the schema.

    Args:
        data: Dictionary loaded from YAML/JSON

    Returns:
        Validated PolicyPackSchema

    Raises:
        pydantic.ValidationError: If validation fails
    """
    return PolicyPackSchema.model_validate(data)


def check_schema_version(data: dict[str, Any]) -> bool:
    """
    Check if a policy pack's schema version is compatible.

    Args:
        data: Dictionary with schema_version field

    Returns:
        True if compatible, False otherwise
    """
    pack_version = data.get("schema_version", "1.0.0")
    # For now, just check major version matches
    pack_major = pack_version.split(".")[0]
    current_major = SCHEMA_VERSION.split(".")[0]
    return pack_major == current_major
