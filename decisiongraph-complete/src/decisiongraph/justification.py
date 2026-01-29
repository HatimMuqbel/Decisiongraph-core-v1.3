"""
DecisionGraph Justification Module (v2.0)

Implements "shadow node" justifications - structured answers to universal
questions that explain WHY a decision was made, not just WHAT was decided.

Every material cell (SIGNAL, MITIGATION, SCORE, VERDICT) should have a
paired JUSTIFICATION cell that answers the universal questions:

1. BASIS: Which facts triggered this?
2. EVIDENCE SUFFICIENCY: Is evidence complete? What's missing?
3. COUNTERFACTUAL: What would falsify this?
4. POLICY ALIGNMENT: Which policies apply?
5. HUMAN REVIEW: Can we auto-close? If not, why?

These justifications are how DecisionGraph achieves:
- Zero-hallucination audit trails
- Deterministic "Integrity Audit PASS" sections
- Explainable AI without LLM generation
- Regulatory-grade documentation

USAGE:
    from decisiongraph.justification import (
        JustificationBuilder, UniversalQuestionSet, ReviewGate
    )

    # Build justification for a signal
    builder = JustificationBuilder(question_set=UniversalQuestionSet.V1)
    builder.set_target(signal_cell.cell_id)
    builder.set_basis_facts([fact1.cell_id, fact2.cell_id])
    builder.set_evidence_sufficient(True)
    builder.set_counterfactuals(["If transaction < $10k, signal would not fire"])
    builder.set_policy_refs([policy_ref.cell_id])
    builder.set_needs_human_review(False)

    justification_cell = builder.build(context)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .cell import (
    DecisionCell, Header, Fact, LogicAnchor, Evidence, Proof,
    CellType, SourceQuality,
    HASH_SCHEME_CANONICAL, get_current_timestamp,
    compute_rule_logic_hash
)
from .pack import Pack, validate_payload


# =============================================================================
# EXCEPTIONS
# =============================================================================

class JustificationError(Exception):
    """Base exception for justification errors."""
    pass


class IncompleteJustificationError(JustificationError):
    """Raised when justification is incomplete."""
    pass


class GatingError(JustificationError):
    """Raised when gating logic fails."""
    pass


# =============================================================================
# QUESTION SETS
# =============================================================================

class UniversalQuestionSet(str, Enum):
    """
    Versioned question sets.

    Each version defines a specific set of required questions.
    Once a version is used, it's locked - new questions require new version.
    """
    V1 = "universal.v1"


# Universal questions - these work for any domain
UNIVERSAL_QUESTIONS_V1 = {
    "basis_fact_ids": {
        "question": "Which facts triggered this decision?",
        "type": "array:cell_id",
        "required": True,
        "description": "Cell IDs of facts that directly led to this output",
    },
    "evidence_sufficient": {
        "question": "Is the evidence sufficient for this conclusion?",
        "type": "boolean",
        "required": True,
        "description": "Whether available evidence supports the conclusion",
    },
    "missing_evidence": {
        "question": "What evidence is missing?",
        "type": "array:string",
        "required": True,
        "description": "List of evidence items that would strengthen the conclusion",
    },
    "counterfactuals": {
        "question": "What would falsify this conclusion?",
        "type": "array:string",
        "required": True,
        "description": "Conditions that would invalidate this decision",
    },
    "policy_refs": {
        "question": "Which policies apply to this decision?",
        "type": "array:cell_id",
        "required": True,
        "description": "Cell IDs of policy references that govern this decision",
    },
    "needs_human_review": {
        "question": "Does this require human review?",
        "type": "boolean",
        "required": True,
        "description": "Whether automated processing is insufficient",
    },
    "review_reason": {
        "question": "Why is human review needed?",
        "type": "string",
        "required": False,  # Only required if needs_human_review is True
        "description": "Explanation for why human judgment is required",
    },
}


def get_question_set(version: UniversalQuestionSet) -> Dict[str, Dict]:
    """Get question definitions for a version."""
    if version == UniversalQuestionSet.V1:
        return UNIVERSAL_QUESTIONS_V1
    raise ValueError(f"Unknown question set version: {version}")


# =============================================================================
# JUSTIFICATION ANSWERS
# =============================================================================

@dataclass
class JustificationAnswers:
    """
    Structured answers to universal questions.

    This is the payload for JUSTIFICATION cells.
    """
    basis_fact_ids: List[str] = field(default_factory=list)
    evidence_sufficient: bool = False
    missing_evidence: List[str] = field(default_factory=list)
    counterfactuals: List[str] = field(default_factory=list)
    policy_refs: List[str] = field(default_factory=list)
    needs_human_review: bool = True  # Default to needing review (safe default)
    review_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for cell payload."""
        result = {
            "basis_fact_ids": self.basis_fact_ids,
            "evidence_sufficient": self.evidence_sufficient,
            "missing_evidence": self.missing_evidence,
            "counterfactuals": self.counterfactuals,
            "policy_refs": self.policy_refs,
            "needs_human_review": self.needs_human_review,
        }
        if self.review_reason is not None:
            result["review_reason"] = self.review_reason
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JustificationAnswers':
        """Create from dict."""
        return cls(
            basis_fact_ids=data.get("basis_fact_ids", []),
            evidence_sufficient=data.get("evidence_sufficient", False),
            missing_evidence=data.get("missing_evidence", []),
            counterfactuals=data.get("counterfactuals", []),
            policy_refs=data.get("policy_refs", []),
            needs_human_review=data.get("needs_human_review", True),
            review_reason=data.get("review_reason"),
        )

    def is_complete(self, question_set: UniversalQuestionSet = UniversalQuestionSet.V1) -> Tuple[bool, List[str]]:
        """
        Check if all required questions are answered.

        Returns:
            (is_complete: bool, missing_fields: List[str])
        """
        questions = get_question_set(question_set)
        missing = []

        for field_name, q_def in questions.items():
            if not q_def["required"]:
                continue

            value = getattr(self, field_name, None)

            # Check if field has a meaningful value
            if value is None:
                missing.append(field_name)
            elif isinstance(value, list) and len(value) == 0:
                # Empty list is acceptable for some fields
                pass
            elif isinstance(value, bool):
                # Boolean is always present
                pass
            elif isinstance(value, str) and value == "":
                missing.append(field_name)

        # Special case: review_reason required if needs_human_review
        if self.needs_human_review and not self.review_reason:
            missing.append("review_reason")

        return len(missing) == 0, missing


# =============================================================================
# JUSTIFICATION BUILDER
# =============================================================================

class JustificationBuilder:
    """
    Builder for creating JUSTIFICATION cells.

    Provides a fluent interface for constructing justifications.
    """

    def __init__(self, question_set: UniversalQuestionSet = UniversalQuestionSet.V1):
        self.question_set = question_set
        self.target_cell_id: Optional[str] = None
        self.answers = JustificationAnswers()

    def set_target(self, cell_id: str) -> 'JustificationBuilder':
        """Set the target cell this justifies."""
        self.target_cell_id = cell_id
        return self

    def set_basis_facts(self, cell_ids: List[str]) -> 'JustificationBuilder':
        """Set the basis facts that triggered the decision."""
        self.answers.basis_fact_ids = cell_ids
        return self

    def add_basis_fact(self, cell_id: str) -> 'JustificationBuilder':
        """Add a basis fact."""
        self.answers.basis_fact_ids.append(cell_id)
        return self

    def set_evidence_sufficient(self, sufficient: bool) -> 'JustificationBuilder':
        """Set whether evidence is sufficient."""
        self.answers.evidence_sufficient = sufficient
        return self

    def set_missing_evidence(self, items: List[str]) -> 'JustificationBuilder':
        """Set list of missing evidence items."""
        self.answers.missing_evidence = items
        return self

    def add_missing_evidence(self, item: str) -> 'JustificationBuilder':
        """Add a missing evidence item."""
        self.answers.missing_evidence.append(item)
        return self

    def set_counterfactuals(self, items: List[str]) -> 'JustificationBuilder':
        """Set counterfactual conditions."""
        self.answers.counterfactuals = items
        return self

    def add_counterfactual(self, item: str) -> 'JustificationBuilder':
        """Add a counterfactual condition."""
        self.answers.counterfactuals.append(item)
        return self

    def set_policy_refs(self, cell_ids: List[str]) -> 'JustificationBuilder':
        """Set policy reference cell IDs."""
        self.answers.policy_refs = cell_ids
        return self

    def add_policy_ref(self, cell_id: str) -> 'JustificationBuilder':
        """Add a policy reference."""
        self.answers.policy_refs.append(cell_id)
        return self

    def set_needs_human_review(self, needs_review: bool, reason: Optional[str] = None) -> 'JustificationBuilder':
        """Set whether human review is needed."""
        self.answers.needs_human_review = needs_review
        if needs_review and reason:
            self.answers.review_reason = reason
        elif not needs_review:
            self.answers.review_reason = None
        return self

    def set_review_reason(self, reason: str) -> 'JustificationBuilder':
        """Set the reason for human review."""
        self.answers.review_reason = reason
        return self

    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate the justification is complete.

        Returns:
            (is_valid: bool, errors: List[str])
        """
        errors = []

        if not self.target_cell_id:
            errors.append("target_cell_id is required")

        is_complete, missing = self.answers.is_complete(self.question_set)
        if not is_complete:
            for field in missing:
                errors.append(f"Missing required answer: {field}")

        return len(errors) == 0, errors

    def build(
        self,
        graph_id: str,
        namespace: str,
        subject: str,
        prev_cell_hash: str,
        system_time: Optional[str] = None,
        pack: Optional[Pack] = None
    ) -> DecisionCell:
        """
        Build the JUSTIFICATION cell.

        Args:
            graph_id: Graph ID for the cell
            namespace: Namespace for the cell
            subject: Subject (typically case_id)
            prev_cell_hash: Previous cell hash for chaining
            system_time: Optional timestamp (defaults to now)
            pack: Optional pack for payload validation

        Returns:
            JUSTIFICATION DecisionCell

        Raises:
            IncompleteJustificationError: If justification is incomplete
        """
        is_valid, errors = self.validate()
        if not is_valid:
            raise IncompleteJustificationError(
                f"Justification incomplete: {', '.join(errors)}"
            )

        if not system_time:
            system_time = get_current_timestamp()

        payload = {
            "schema_version": "1.0",
            "target_cell_id": self.target_cell_id,
            "question_set_id": self.question_set.value,
            "answers": self.answers.to_dict(),
        }

        # Validate against pack if provided
        if pack:
            validate_payload(pack, CellType.JUSTIFICATION, payload, strict=False)

        return DecisionCell(
            header=Header(
                version="1.0",
                graph_id=graph_id,
                cell_type=CellType.JUSTIFICATION,
                system_time=system_time,
                prev_cell_hash=prev_cell_hash,
                hash_scheme=HASH_SCHEME_CANONICAL
            ),
            fact=Fact(
                namespace=namespace,
                subject=subject,
                predicate="justification.recorded",
                object=payload,
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(
                rule_id=f"justification:{self.question_set.value}",
                rule_logic_hash=compute_rule_logic_hash(
                    f"justification:{self.question_set.value}:target:{self.target_cell_id}"
                ),
                interpreter="decisiongraph:justification:v2"
            )
        )


# =============================================================================
# REVIEW GATING
# =============================================================================

class ReviewGateResult(str, Enum):
    """Result of review gate evaluation."""
    PASS = "pass"           # Can proceed without human review
    REVIEW_REQUIRED = "review_required"  # Human review needed
    ESCALATE = "escalate"   # Escalate to higher authority
    BLOCK = "block"         # Cannot proceed


@dataclass
class GateEvaluation:
    """Result of evaluating a review gate."""
    result: ReviewGateResult
    reasons: List[str] = field(default_factory=list)
    missing_justifications: List[str] = field(default_factory=list)
    incomplete_justifications: List[str] = field(default_factory=list)

    @property
    def can_auto_proceed(self) -> bool:
        """Whether the case can proceed without human intervention."""
        return self.result == ReviewGateResult.PASS


@dataclass
class ReviewGate:
    """
    Gate that determines if a case can proceed without human review.

    Evaluates justifications to determine if:
    - All required justifications exist
    - All justifications are complete
    - No justifications require human review
    - Evidence is sufficient
    """
    gate_id: str
    name: str
    description: str = ""
    # Which cell types require justification
    requires_justification_for: List[CellType] = field(default_factory=lambda: [
        CellType.SIGNAL,
        CellType.MITIGATION,
        CellType.SCORE,
        CellType.VERDICT,
    ])
    # If True, block if any evidence is insufficient
    block_on_insufficient_evidence: bool = True
    # If True, block if any counterfactuals are not addressed
    require_counterfactuals: bool = True
    # Minimum number of policy refs required
    min_policy_refs: int = 0

    def evaluate(
        self,
        target_cells: List[DecisionCell],
        justifications: List[DecisionCell]
    ) -> GateEvaluation:
        """
        Evaluate whether case can proceed.

        Args:
            target_cells: Cells that should have justifications
            justifications: Available justification cells

        Returns:
            GateEvaluation with result and details
        """
        evaluation = GateEvaluation(result=ReviewGateResult.PASS)

        # Build map of target_cell_id -> justification
        justification_map: Dict[str, DecisionCell] = {}
        for j in justifications:
            if j.header.cell_type == CellType.JUSTIFICATION:
                target_id = j.fact.object.get("target_cell_id")
                if target_id:
                    justification_map[target_id] = j

        # Check each target cell
        for cell in target_cells:
            if cell.header.cell_type not in self.requires_justification_for:
                continue

            # Check if justification exists
            if cell.cell_id not in justification_map:
                evaluation.missing_justifications.append(cell.cell_id)
                evaluation.result = ReviewGateResult.REVIEW_REQUIRED
                evaluation.reasons.append(
                    f"Missing justification for {cell.header.cell_type.value} cell {cell.cell_id[:16]}..."
                )
                continue

            # Get and validate justification
            j_cell = justification_map[cell.cell_id]
            answers_dict = j_cell.fact.object.get("answers", {})
            answers = JustificationAnswers.from_dict(answers_dict)

            # Check completeness
            is_complete, missing = answers.is_complete()
            if not is_complete:
                evaluation.incomplete_justifications.append(cell.cell_id)
                evaluation.result = ReviewGateResult.REVIEW_REQUIRED
                evaluation.reasons.append(
                    f"Incomplete justification for {cell.cell_id[:16]}...: missing {missing}"
                )
                continue

            # Check if human review needed
            if answers.needs_human_review:
                evaluation.result = ReviewGateResult.REVIEW_REQUIRED
                reason = answers.review_reason or "No reason provided"
                evaluation.reasons.append(
                    f"Human review required for {cell.cell_id[:16]}...: {reason}"
                )
                continue

            # Check evidence sufficiency
            if self.block_on_insufficient_evidence and not answers.evidence_sufficient:
                evaluation.result = ReviewGateResult.REVIEW_REQUIRED
                evaluation.reasons.append(
                    f"Insufficient evidence for {cell.cell_id[:16]}..."
                )
                if answers.missing_evidence:
                    evaluation.reasons.append(
                        f"  Missing: {', '.join(answers.missing_evidence)}"
                    )
                continue

            # Check counterfactuals
            if self.require_counterfactuals and not answers.counterfactuals:
                evaluation.result = ReviewGateResult.REVIEW_REQUIRED
                evaluation.reasons.append(
                    f"No counterfactuals provided for {cell.cell_id[:16]}..."
                )
                continue

            # Check policy refs
            if self.min_policy_refs > 0 and len(answers.policy_refs) < self.min_policy_refs:
                evaluation.result = ReviewGateResult.REVIEW_REQUIRED
                evaluation.reasons.append(
                    f"Insufficient policy refs for {cell.cell_id[:16]}...: "
                    f"need {self.min_policy_refs}, have {len(answers.policy_refs)}"
                )
                continue

        return evaluation


# =============================================================================
# AUTO-JUSTIFICATION HELPERS
# =============================================================================

def create_signal_justification(
    signal_cell: DecisionCell,
    trigger_facts: List[DecisionCell],
    policy_refs: List[DecisionCell],
    counterfactuals: List[str],
    evidence_sufficient: bool = True,
    missing_evidence: Optional[List[str]] = None,
    needs_human_review: bool = False,
    review_reason: Optional[str] = None,
) -> JustificationBuilder:
    """
    Create a justification builder pre-populated for a SIGNAL cell.

    Args:
        signal_cell: The SIGNAL cell to justify
        trigger_facts: Facts that triggered the signal
        policy_refs: Policy references that apply
        counterfactuals: What would falsify this signal
        evidence_sufficient: Whether evidence is complete
        missing_evidence: What evidence is missing
        needs_human_review: Whether human review is needed
        review_reason: Why review is needed

    Returns:
        JustificationBuilder ready to build
    """
    builder = JustificationBuilder()
    builder.set_target(signal_cell.cell_id)
    builder.set_basis_facts([f.cell_id for f in trigger_facts])
    builder.set_policy_refs([p.cell_id for p in policy_refs])
    builder.set_counterfactuals(counterfactuals)
    builder.set_evidence_sufficient(evidence_sufficient)
    builder.set_missing_evidence(missing_evidence or [])
    builder.set_needs_human_review(needs_human_review, review_reason)
    return builder


def create_verdict_justification(
    verdict_cell: DecisionCell,
    supporting_cells: List[DecisionCell],
    policy_refs: List[DecisionCell],
    counterfactuals: List[str],
    evidence_sufficient: bool = True,
    missing_evidence: Optional[List[str]] = None,
    needs_human_review: bool = False,
    review_reason: Optional[str] = None,
) -> JustificationBuilder:
    """
    Create a justification builder pre-populated for a VERDICT cell.

    Args:
        verdict_cell: The VERDICT cell to justify
        supporting_cells: Cells supporting the verdict (signals, mitigations, score)
        policy_refs: Policy references that apply
        counterfactuals: What would change the verdict
        evidence_sufficient: Whether evidence is complete
        missing_evidence: What evidence is missing
        needs_human_review: Whether human review is needed
        review_reason: Why review is needed

    Returns:
        JustificationBuilder ready to build
    """
    builder = JustificationBuilder()
    builder.set_target(verdict_cell.cell_id)
    builder.set_basis_facts([c.cell_id for c in supporting_cells])
    builder.set_policy_refs([p.cell_id for p in policy_refs])
    builder.set_counterfactuals(counterfactuals)
    builder.set_evidence_sufficient(evidence_sufficient)
    builder.set_missing_evidence(missing_evidence or [])
    builder.set_needs_human_review(needs_human_review, review_reason)
    return builder


def create_auto_justification(
    target_cell: DecisionCell,
    basis_facts: List[str],
    policy_refs: List[str],
    default_counterfactual: str = "If basis facts were different, conclusion would change",
) -> JustificationBuilder:
    """
    Create a minimal auto-generated justification.

    This is for cases where the decision is straightforward and
    doesn't require human judgment. The justification is complete
    but minimal.

    Args:
        target_cell: Cell to justify
        basis_facts: Cell IDs of basis facts
        policy_refs: Cell IDs of policy references
        default_counterfactual: Default counterfactual statement

    Returns:
        JustificationBuilder ready to build
    """
    builder = JustificationBuilder()
    builder.set_target(target_cell.cell_id)
    builder.set_basis_facts(basis_facts)
    builder.set_policy_refs(policy_refs)
    builder.set_counterfactuals([default_counterfactual])
    builder.set_evidence_sufficient(True)
    builder.set_missing_evidence([])
    builder.set_needs_human_review(False)
    return builder


# =============================================================================
# JUSTIFICATION ANALYSIS
# =============================================================================

@dataclass
class JustificationSummary:
    """Summary of justifications for a case."""
    total_targets: int = 0
    justified: int = 0
    missing: int = 0
    incomplete: int = 0
    needs_review: int = 0
    evidence_gaps: List[str] = field(default_factory=list)
    policy_coverage: float = 0.0  # Percentage of targets with policy refs

    @property
    def completion_rate(self) -> float:
        """Percentage of targets that are fully justified."""
        if self.total_targets == 0:
            return 1.0
        return self.justified / self.total_targets

    @property
    def is_complete(self) -> bool:
        """Whether all targets have complete justifications."""
        return self.missing == 0 and self.incomplete == 0

    @property
    def can_auto_close(self) -> bool:
        """Whether case can be auto-closed based on justifications."""
        return self.is_complete and self.needs_review == 0


def analyze_justifications(
    target_cells: List[DecisionCell],
    justifications: List[DecisionCell],
    required_cell_types: Optional[List[CellType]] = None
) -> JustificationSummary:
    """
    Analyze justification coverage for a case.

    Args:
        target_cells: Cells that should have justifications
        justifications: Available justification cells
        required_cell_types: Cell types that require justification
            (defaults to SIGNAL, MITIGATION, SCORE, VERDICT)

    Returns:
        JustificationSummary with analysis
    """
    if required_cell_types is None:
        required_cell_types = [
            CellType.SIGNAL,
            CellType.MITIGATION,
            CellType.SCORE,
            CellType.VERDICT,
        ]

    summary = JustificationSummary()

    # Filter to required cell types
    targets = [c for c in target_cells if c.header.cell_type in required_cell_types]
    summary.total_targets = len(targets)

    if summary.total_targets == 0:
        return summary

    # Build justification map
    j_map: Dict[str, DecisionCell] = {}
    for j in justifications:
        if j.header.cell_type == CellType.JUSTIFICATION:
            target_id = j.fact.object.get("target_cell_id")
            if target_id:
                j_map[target_id] = j

    # Analyze each target
    with_policy_refs = 0

    for target in targets:
        if target.cell_id not in j_map:
            summary.missing += 1
            continue

        j_cell = j_map[target.cell_id]
        answers_dict = j_cell.fact.object.get("answers", {})
        answers = JustificationAnswers.from_dict(answers_dict)

        is_complete, _ = answers.is_complete()
        if not is_complete:
            summary.incomplete += 1
            continue

        summary.justified += 1

        if answers.needs_human_review:
            summary.needs_review += 1

        if not answers.evidence_sufficient and answers.missing_evidence:
            summary.evidence_gaps.extend(answers.missing_evidence)

        if answers.policy_refs:
            with_policy_refs += 1

    summary.policy_coverage = with_policy_refs / summary.total_targets if summary.total_targets > 0 else 0.0

    return summary


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Exceptions
    'JustificationError',
    'IncompleteJustificationError',
    'GatingError',
    # Question sets
    'UniversalQuestionSet',
    'UNIVERSAL_QUESTIONS_V1',
    'get_question_set',
    # Answers
    'JustificationAnswers',
    # Builder
    'JustificationBuilder',
    # Gating
    'ReviewGateResult',
    'GateEvaluation',
    'ReviewGate',
    # Helpers
    'create_signal_justification',
    'create_verdict_justification',
    'create_auto_justification',
    # Analysis
    'JustificationSummary',
    'analyze_justifications',
]
