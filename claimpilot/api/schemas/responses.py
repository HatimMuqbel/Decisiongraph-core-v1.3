"""Response schemas for the API."""

from pydantic import BaseModel
from typing import Optional


class AuthorityCited(BaseModel):
    """Authority citation in recommendation."""
    authority_type: str
    title: str
    section: str
    excerpt: Optional[str] = None
    excerpt_hash: Optional[str] = None


class ReasoningStep(BaseModel):
    """A step in the reasoning chain."""
    sequence: int
    step_type: str
    description: str
    rule_id: Optional[str] = None
    rule_name: Optional[str] = None
    result: str  # passed|failed|uncertain|not_applicable
    result_reason: Optional[str] = None


class ExclusionEvaluated(BaseModel):
    """Result of evaluating an exclusion."""
    id: str
    code: str
    name: str
    triggered: bool
    reason: str
    policy_wording: Optional[str] = None


class EvaluateResponse(BaseModel):
    """Response from claim evaluation."""
    # Identifiers
    claim_id: str
    policy_pack_id: str
    policy_pack_version: str
    policy_pack_hash: str

    # Recommendation
    recommended_disposition: str  # pay|deny|partial|escalate|request_info|hold|refer_siu
    disposition_reason: str
    certainty: str  # high|medium|low|requires_judgment

    # Coverage evaluation
    coverages_evaluated: list[str]
    coverage_applies: bool

    # Exclusion evaluation
    exclusions_evaluated: list[ExclusionEvaluated]
    exclusions_triggered: list[str]
    exclusions_ruled_out: list[str]
    exclusions_uncertain: list[str]

    # Authority
    requires_authority: bool
    required_role: Optional[str] = None
    authority_rule_triggered: Optional[str] = None

    # Evidence
    evidence_complete: bool
    evidence_missing: list[str]

    # Guidance
    unknown_facts: list[str]
    next_best_questions: list[str]

    # Reasoning
    authorities_cited: list[AuthorityCited]
    reasoning_steps: list[ReasoningStep]

    # Provenance
    evaluated_at: str
    engine_version: str


class PolicySummary(BaseModel):
    """Summary of a policy pack."""
    id: str
    name: str
    jurisdiction: str
    line_of_business: str
    product_code: str
    version: str
    effective_date: str
    coverage_count: int
    exclusion_count: int


class CoverageSummary(BaseModel):
    """Summary of a coverage section."""
    id: str
    code: str
    name: str
    description: str
    loss_types: list[str]


class ExclusionSummary(BaseModel):
    """Summary of an exclusion."""
    id: str
    code: str
    name: str
    description: str
    policy_wording: str
    applies_to: list[str]
    evaluation_questions: list[str]


class PolicyDetail(BaseModel):
    """Full details of a policy pack."""
    id: str
    name: str
    jurisdiction: str
    line_of_business: str
    product_code: str
    version: str
    effective_date: str
    policy_pack_hash: str
    coverages: list[CoverageSummary]
    exclusions: list[ExclusionSummary]


class DemoCase(BaseModel):
    """A pre-built demo case."""
    id: str
    name: str
    description: str
    line_of_business: str
    policy_id: str
    expected_outcome: str  # pay|deny|escalate|etc
    expected_reason: str
    facts: list[dict]
    evidence: list[dict]

    # Key facts that drive the outcome
    key_facts: list[str]
