"""
ClaimPilot Recommendation Models

Models for the output of ClaimPilot — recommendations, not decisions.

Key components:
- ReasoningStep: A single step in the reasoning chain
- RecommendationRecord: Full recommendation with audit trail
- RecommendationMemo: Structured output for display/reporting

Core Principle: "The adjuster decides. ClaimPilot recommends and documents."
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from .enums import (
    AuthorityType,
    DispositionType,
    ReasoningStepResult,
    ReasoningStepType,
    RecommendationCertainty,
)
from .authority import AuthorityRef
from .precedent import PrecedentHit


# =============================================================================
# Authority Citation (Hash-Verified)
# =============================================================================

@dataclass
class AuthorityCitation:
    """
    A hash-verified citation to a specific policy clause or regulation.

    Enables provenance verification: "This exact text was cited in this recommendation."

    Attributes:
        authority_ref_id: Reference to the AuthorityRef that was cited
        authority_type: Type of authority (policy_wording, regulation, etc.)
        section_ref: Section reference (e.g., "Section 4.2.1")
        excerpt: The actual text that was cited
        excerpt_hash: SHA-256 of normalized excerpt
        source_document_hash: Hash of full source document if available
        effective_as_of: When this authority text was effective
        cited_at: When we cited it (for bitemporal queries)
    """
    authority_ref_id: str
    authority_type: AuthorityType
    section_ref: str
    excerpt: str
    excerpt_hash: str  # SHA-256 of normalized excerpt

    # Optional provenance
    source_document_hash: Optional[str] = None

    # Temporal markers
    effective_as_of: Optional[date] = None
    cited_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_authority_ref(cls, authority: AuthorityRef) -> "AuthorityCitation":
        """
        Create an AuthorityCitation from an AuthorityRef.

        Computes the excerpt hash automatically.
        """
        from ..canon import normalize_excerpt, text_hash

        excerpt = authority.quote_excerpt or ""
        normalized = normalize_excerpt(excerpt)

        return cls(
            authority_ref_id=authority.id,
            authority_type=authority.authority_type,
            section_ref=authority.section,
            excerpt=excerpt,
            excerpt_hash=text_hash(normalized),
            source_document_hash=authority.content_hash,
            effective_as_of=authority.effective_date,
        )

    def verify_excerpt(self, text: str) -> bool:
        """
        Verify that provided text matches the stored excerpt hash.

        Args:
            text: Text to verify

        Returns:
            True if hash matches, False otherwise
        """
        from ..canon import normalize_excerpt, text_hash

        normalized = normalize_excerpt(text)
        return text_hash(normalized) == self.excerpt_hash

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        result = {
            "authority_ref_id": self.authority_ref_id,
            "authority_type": self.authority_type.value,
            "section_ref": self.section_ref,
            "excerpt": self.excerpt,
            "excerpt_hash": self.excerpt_hash,
            "cited_at": self.cited_at.isoformat(),
        }
        if self.source_document_hash:
            result["source_document_hash"] = self.source_document_hash
        if self.effective_as_of:
            result["effective_as_of"] = self.effective_as_of.isoformat()
        return result


# =============================================================================
# Reasoning Step
# =============================================================================

@dataclass
class ReasoningStep:
    """
    A single step in the reasoning chain.

    Captures what was evaluated, what the result was, and what
    facts/evidence/authorities supported it.

    Attributes:
        id: Unique identifier
        sequence: Order in the chain
        step_type: Type of step
        description: Human-readable description
        rule_id: ID of the rule evaluated
        rule_name: Name of the rule
        result: Outcome of evaluation
        result_reason: Why this result
        supporting_fact_ids: Facts that supported this
        supporting_evidence_ids: Evidence reviewed
        authority_ref: Authority cited
        timestamp: When step was executed
    """
    id: str
    sequence: int
    step_type: ReasoningStepType
    description: str

    # What was evaluated
    rule_id: Optional[str] = None
    rule_name: Optional[str] = None

    # Result
    result: ReasoningStepResult = ReasoningStepResult.PASSED
    result_reason: Optional[str] = None

    # What facts/evidence supported this
    supporting_fact_ids: list[str] = field(default_factory=list)
    supporting_evidence_ids: list[str] = field(default_factory=list)

    # Authority cited for this step
    authority_ref: Optional[AuthorityRef] = None

    # Timing
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        sequence: int,
        step_type: ReasoningStepType,
        description: str,
        result: ReasoningStepResult = ReasoningStepResult.PASSED,
        rule_id: Optional[str] = None,
        rule_name: Optional[str] = None,
    ) -> ReasoningStep:
        """Factory method to create a new ReasoningStep."""
        return cls(
            id=str(uuid4()),
            sequence=sequence,
            step_type=step_type,
            description=description,
            result=result,
            rule_id=rule_id,
            rule_name=rule_name,
        )

    @property
    def passed(self) -> bool:
        """Check if step passed."""
        return self.result == ReasoningStepResult.PASSED

    @property
    def failed(self) -> bool:
        """Check if step failed."""
        return self.result == ReasoningStepResult.FAILED

    @property
    def uncertain(self) -> bool:
        """Check if result is uncertain."""
        return self.result == ReasoningStepResult.UNCERTAIN

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "sequence": self.sequence,
            "step_type": self.step_type.value,
            "description": self.description,
            "result": self.result.value,
            "result_reason": self.result_reason,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
        }


# =============================================================================
# Recommendation Record
# =============================================================================

@dataclass
class RecommendationRecord:
    """
    A recommendation produced by ClaimPilot.

    The adjuster/supervisor makes the final decision — this is
    just the system's recommendation with full audit trail.

    Attributes:
        id: Unique identifier
        claim_id: Associated claim
        context_id: Reference to ClaimContext
        recommended_disposition: What we recommend
        disposition_reason: Why we recommend this
        certainty: Confidence level
        unknown_facts: What we don't know
        next_best_questions: What to find out
        coverages_evaluated: Coverage IDs checked
        exclusions_triggered: Exclusions that applied
        exclusions_ruled_out: Exclusions that don't apply
        exclusions_uncertain: Exclusions we couldn't determine
        authorities_cited: All citations
        similar_cases: Precedents surfaced
        facts_considered: Fact IDs used
        evidence_reviewed: Evidence IDs reviewed
        evidence_missing: What evidence is still needed
        reasoning_steps: Full reasoning chain
        generated_at: When recommendation was made
        generated_by_version: ClaimPilot version
        requires_authority: Whether escalation is needed
        authority_rule_triggered: Which rule triggered escalation
        required_role: Role needed to approve
    """
    id: str
    claim_id: str
    context_id: str

    # The recommendation
    recommended_disposition: DispositionType
    disposition_reason: str

    # Certainty and confidence
    certainty: RecommendationCertainty
    unknown_facts: list[str] = field(default_factory=list)
    next_best_questions: list[str] = field(default_factory=list)

    # What rules drove this
    coverages_evaluated: list[str] = field(default_factory=list)
    exclusions_triggered: list[str] = field(default_factory=list)
    exclusions_ruled_out: list[str] = field(default_factory=list)
    exclusions_uncertain: list[str] = field(default_factory=list)

    # Citations (first-class!)
    authorities_cited: list[AuthorityRef] = field(default_factory=list)

    # Precedents (first-class!)
    similar_cases: list[PrecedentHit] = field(default_factory=list)

    # Evidence basis
    facts_considered: list[str] = field(default_factory=list)
    evidence_reviewed: list[str] = field(default_factory=list)
    evidence_missing: list[str] = field(default_factory=list)

    # Reasoning chain (for full traceability)
    reasoning_steps: list[ReasoningStep] = field(default_factory=list)

    # Metadata
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    generated_by_version: str = ""

    # Escalation (if needed)
    requires_authority: bool = False
    authority_rule_triggered: Optional[str] = None
    required_role: Optional[str] = None

    # Alternatives considered
    alternative_dispositions: list[str] = field(default_factory=list)

    # === POLICY PROVENANCE ===
    # Enables verification that policy rules haven't changed since recommendation
    policy_pack_id: str = ""                 # e.g., "CA-ON-OAP1-2024"
    policy_pack_version: str = ""            # e.g., "2024.1"
    policy_pack_hash: str = ""               # SHA-256 of canonical JSON rendering
    authority_hashes: list[AuthorityCitation] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        claim_id: str,
        context_id: str,
        recommended_disposition: DispositionType,
        disposition_reason: str,
        certainty: RecommendationCertainty,
    ) -> RecommendationRecord:
        """Factory method to create a new RecommendationRecord."""
        return cls(
            id=str(uuid4()),
            claim_id=claim_id,
            context_id=context_id,
            recommended_disposition=recommended_disposition,
            disposition_reason=disposition_reason,
            certainty=certainty,
        )

    def add_reasoning_step(self, step: ReasoningStep) -> None:
        """Add a reasoning step to the chain."""
        self.reasoning_steps.append(step)

    def cite_authority(self, authority: AuthorityRef) -> None:
        """Add an authority citation."""
        if authority not in self.authorities_cited:
            self.authorities_cited.append(authority)

    def add_precedent(self, precedent: PrecedentHit) -> None:
        """Add a similar case."""
        if precedent not in self.similar_cases:
            self.similar_cases.append(precedent)

    @property
    def has_uncertainty(self) -> bool:
        """Check if recommendation has uncertainty."""
        return (
            self.certainty in {
                RecommendationCertainty.LOW,
                RecommendationCertainty.REQUIRES_JUDGMENT,
            }
            or len(self.unknown_facts) > 0
            or len(self.exclusions_uncertain) > 0
        )

    @property
    def requires_escalation(self) -> bool:
        """Check if escalation is required."""
        return self.requires_authority

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "claim_id": self.claim_id,
            "recommended_disposition": self.recommended_disposition.value,
            "disposition_reason": self.disposition_reason,
            "certainty": self.certainty.value,
            "unknown_facts": self.unknown_facts,
            "coverages_evaluated": self.coverages_evaluated,
            "exclusions_triggered": self.exclusions_triggered,
            "requires_authority": self.requires_authority,
            "required_role": self.required_role,
            "generated_at": self.generated_at.isoformat(),
        }


# =============================================================================
# Recommendation Memo (Structured Output)
# =============================================================================

@dataclass
class RecommendationMemo:
    """
    Deterministic structured output for display/reporting.

    This is the "premium" output format — everything an adjuster
    needs to understand and act on the recommendation.

    Used as:
    - Demo artifact
    - Test fixture output
    - Future report generator input
    """
    claim_id: str
    summary: str  # Human-readable summary

    # The recommendation
    recommended_action: DispositionType
    recommended_action_reason: str

    # Alternatives considered
    alternatives: list[str]

    # Citations
    citations: list[AuthorityRef]

    # Similar cases
    similar_cases: list[PrecedentHit]

    # What's unknown/missing
    missing_facts: list[str]
    required_evidence: list[str]

    # Escalation
    escalation_required: bool
    escalation_reason: Optional[str]
    escalation_role: Optional[str]

    # Confidence
    confidence: RecommendationCertainty

    # Metadata
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    recommendation_id: Optional[str] = None

    @classmethod
    def from_recommendation(
        cls,
        recommendation: RecommendationRecord,
        summary: str,
    ) -> RecommendationMemo:
        """
        Create a memo from a RecommendationRecord.

        Args:
            recommendation: The source recommendation
            summary: Human-readable summary

        Returns:
            RecommendationMemo instance
        """
        return cls(
            claim_id=recommendation.claim_id,
            summary=summary,
            recommended_action=recommendation.recommended_disposition,
            recommended_action_reason=recommendation.disposition_reason,
            alternatives=recommendation.alternative_dispositions,
            citations=recommendation.authorities_cited,
            similar_cases=recommendation.similar_cases,
            missing_facts=recommendation.unknown_facts,
            required_evidence=recommendation.evidence_missing,
            escalation_required=recommendation.requires_authority,
            escalation_reason=(
                f"Rule {recommendation.authority_rule_triggered} triggered"
                if recommendation.authority_rule_triggered else None
            ),
            escalation_role=recommendation.required_role,
            confidence=recommendation.certainty,
            generated_at=recommendation.generated_at,
            recommendation_id=recommendation.id,
        )

    @property
    def action_blocked(self) -> bool:
        """Check if action is blocked (missing required items)."""
        return len(self.required_evidence) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are warnings."""
        return (
            len(self.missing_facts) > 0
            or self.confidence in {
                RecommendationCertainty.LOW,
                RecommendationCertainty.REQUIRES_JUDGMENT,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "claim_id": self.claim_id,
            "summary": self.summary,
            "recommended_action": self.recommended_action.value,
            "recommended_action_reason": self.recommended_action_reason,
            "alternatives": self.alternatives,
            "citations": [c.to_dict() for c in self.citations],
            "similar_cases": [s.to_dict() for s in self.similar_cases],
            "missing_facts": self.missing_facts,
            "required_evidence": self.required_evidence,
            "escalation_required": self.escalation_required,
            "escalation_reason": self.escalation_reason,
            "escalation_role": self.escalation_role,
            "confidence": self.confidence.value,
            "generated_at": self.generated_at.isoformat(),
        }

    def to_markdown(self) -> str:
        """Generate markdown representation."""
        lines = [
            f"# Recommendation Memo",
            f"",
            f"**Claim:** {self.claim_id}",
            f"**Generated:** {self.generated_at.isoformat()}",
            f"",
            f"## Summary",
            f"",
            f"{self.summary}",
            f"",
            f"## Recommendation",
            f"",
            f"**Action:** {self.recommended_action.value.upper()}",
            f"**Confidence:** {self.confidence.value}",
            f"",
            f"**Reason:** {self.recommended_action_reason}",
            f"",
        ]

        if self.escalation_required:
            lines.extend([
                f"## Escalation Required",
                f"",
                f"**Role:** {self.escalation_role}",
                f"**Reason:** {self.escalation_reason}",
                f"",
            ])

        if self.citations:
            lines.extend([
                f"## Authorities Cited",
                f"",
            ])
            for citation in self.citations:
                lines.append(f"- {citation.short_citation}")
            lines.append("")

        if self.similar_cases:
            lines.extend([
                f"## Similar Cases",
                f"",
            ])
            for case in self.similar_cases:
                score = f" ({case.similarity_score})" if case.similarity_score else ""
                lines.append(f"- **{case.case_id}**{score}: {case.similarity_basis}")
            lines.append("")

        if self.missing_facts:
            lines.extend([
                f"## Missing Facts",
                f"",
            ])
            for fact in self.missing_facts:
                lines.append(f"- {fact}")
            lines.append("")

        if self.required_evidence:
            lines.extend([
                f"## Required Evidence",
                f"",
            ])
            for evidence in self.required_evidence:
                lines.append(f"- {evidence}")
            lines.append("")

        if self.alternatives:
            lines.extend([
                f"## Alternatives Considered",
                f"",
            ])
            for alt in self.alternatives:
                lines.append(f"- {alt}")
            lines.append("")

        return "\n".join(lines)
