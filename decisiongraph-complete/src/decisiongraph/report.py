"""
DecisionGraph Report Module (v2.0)

Implements frozen, reproducible report generation.

A report captures a point-in-time snapshot of a decision process:
- All cells included in the decision
- The pack/rules used for evaluation
- The rendered artifact (hash for verification)
- Human/system judgments as signoffs

Key concepts:
- REPORT_RUN: Freezes the execution context at report generation time
- JUDGMENT: Records human or system signoffs
- ReportManifest: In-memory snapshot of a report

Reports are immutable once generated. Re-running with the same inputs
and pack version MUST produce the same output (deterministic).

USAGE:
    from decisiongraph.report import ReportBuilder, JudgmentBuilder

    # Build a report
    builder = ReportBuilder(pack=my_pack)
    builder.set_case_id("case_001")
    builder.set_anchor_head(chain.head.cell_id)
    builder.add_cells([signal, verdict, justification])
    builder.set_template("aml_sar", "1.0")
    builder.set_rendered_hash(compute_hash(rendered_pdf))

    report_cell = builder.build(context)

    # Add judgment
    j_builder = JudgmentBuilder()
    j_builder.set_action(JudgmentAction.APPROVE)
    j_builder.set_reviewer("analyst_001", tier=1)
    j_builder.set_target(verdict.cell_id)
    j_builder.set_rationale("Evidence sufficient, patterns match")

    judgment_cell = j_builder.build(context)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib

from .cell import (
    DecisionCell, Header, Fact, LogicAnchor, Evidence, Proof,
    CellType, SourceQuality,
    HASH_SCHEME_CANONICAL, get_current_timestamp,
    compute_rule_logic_hash
)
from .pack import Pack, validate_payload
from .canon import canonical_json_bytes


# =============================================================================
# EXCEPTIONS
# =============================================================================

class ReportError(Exception):
    """Base exception for report errors."""
    pass


class IncompleteReportError(ReportError):
    """Raised when report is incomplete."""
    pass


class JudgmentError(ReportError):
    """Raised for judgment-related errors."""
    pass


class ReportVerificationError(ReportError):
    """Raised when report verification fails."""
    pass


# =============================================================================
# ENUMS
# =============================================================================

class JudgmentAction(str, Enum):
    """Actions for judgment cells."""
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"
    DEFER = "DEFER"
    OVERRIDE = "OVERRIDE"


class ReportStatus(str, Enum):
    """Status of a report."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


# =============================================================================
# REPORT MANIFEST
# =============================================================================

@dataclass
class ReportManifest:
    """
    In-memory representation of a frozen report.

    Contains all data needed to reproduce the report:
    - The cells included
    - Pack and template used
    - Hash of rendered artifact
    """
    case_id: str
    pack_id: str
    pack_version: str
    anchor_head_cell_id: str
    included_cell_ids: List[str]
    template_id: str
    template_version: str
    rendered_artifact_hash: str
    rendered_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for cell payload."""
        return {
            "schema_version": "1.0",
            "case_id": self.case_id,
            "pack_id": self.pack_id,
            "pack_version": self.pack_version,
            "anchor_head_cell_id": self.anchor_head_cell_id,
            "included_cell_ids": self.included_cell_ids,
            "template_id": self.template_id,
            "template_version": self.template_version,
            "rendered_artifact_hash": self.rendered_artifact_hash,
            "rendered_at": self.rendered_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReportManifest':
        """Create from dict."""
        return cls(
            case_id=data["case_id"],
            pack_id=data["pack_id"],
            pack_version=data["pack_version"],
            anchor_head_cell_id=data["anchor_head_cell_id"],
            included_cell_ids=data.get("included_cell_ids", []),
            template_id=data["template_id"],
            template_version=data["template_version"],
            rendered_artifact_hash=data["rendered_artifact_hash"],
            rendered_at=data["rendered_at"],
        )

    @classmethod
    def from_cell(cls, cell: DecisionCell) -> 'ReportManifest':
        """Extract manifest from a REPORT_RUN cell."""
        if cell.header.cell_type != CellType.REPORT_RUN:
            raise ReportError(f"Expected REPORT_RUN cell, got {cell.header.cell_type}")
        return cls.from_dict(cell.fact.object)

    def compute_content_hash(self) -> str:
        """Compute deterministic hash of manifest content."""
        # Use canonical JSON for determinism
        content_bytes = canonical_json_bytes(self.to_dict())
        return hashlib.sha256(content_bytes).hexdigest()


# =============================================================================
# REPORT BUILDER
# =============================================================================

class ReportBuilder:
    """
    Builder for creating REPORT_RUN cells.

    A REPORT_RUN cell captures the frozen state of a report at generation time.
    """

    def __init__(self, pack: Optional[Pack] = None):
        self.pack = pack
        self.case_id: Optional[str] = None
        self.anchor_head_cell_id: Optional[str] = None
        self.included_cell_ids: List[str] = []
        self.template_id: Optional[str] = None
        self.template_version: Optional[str] = None
        self.rendered_artifact_hash: Optional[str] = None
        self.rendered_at: Optional[str] = None

    def set_case_id(self, case_id: str) -> 'ReportBuilder':
        """Set the case identifier."""
        self.case_id = case_id
        return self

    def set_anchor_head(self, cell_id: str) -> 'ReportBuilder':
        """Set the chain head at time of report."""
        self.anchor_head_cell_id = cell_id
        return self

    def add_cell(self, cell: DecisionCell) -> 'ReportBuilder':
        """Add a cell to the report."""
        self.included_cell_ids.append(cell.cell_id)
        return self

    def add_cells(self, cells: List[DecisionCell]) -> 'ReportBuilder':
        """Add multiple cells to the report."""
        for cell in cells:
            self.included_cell_ids.append(cell.cell_id)
        return self

    def add_cell_ids(self, cell_ids: List[str]) -> 'ReportBuilder':
        """Add cell IDs directly."""
        self.included_cell_ids.extend(cell_ids)
        return self

    def set_template(self, template_id: str, template_version: str) -> 'ReportBuilder':
        """Set the report template."""
        self.template_id = template_id
        self.template_version = template_version
        return self

    def set_rendered_hash(self, hash_value: str) -> 'ReportBuilder':
        """Set the hash of the rendered artifact."""
        self.rendered_artifact_hash = hash_value
        return self

    def set_rendered_at(self, timestamp: str) -> 'ReportBuilder':
        """Set when the report was rendered."""
        self.rendered_at = timestamp
        return self

    def validate(self) -> tuple[bool, List[str]]:
        """
        Validate the report is complete.

        Returns:
            (is_valid: bool, errors: List[str])
        """
        errors = []

        if not self.case_id:
            errors.append("case_id is required")
        if not self.anchor_head_cell_id:
            errors.append("anchor_head_cell_id is required")
        if not self.included_cell_ids:
            errors.append("At least one cell must be included")
        if not self.template_id:
            errors.append("template_id is required")
        if not self.template_version:
            errors.append("template_version is required")
        if not self.rendered_artifact_hash:
            errors.append("rendered_artifact_hash is required")

        return len(errors) == 0, errors

    def build(
        self,
        graph_id: str,
        namespace: str,
        prev_cell_hash: str,
        system_time: Optional[str] = None
    ) -> DecisionCell:
        """
        Build the REPORT_RUN cell.

        Args:
            graph_id: Graph ID for the cell
            namespace: Namespace for the cell
            prev_cell_hash: Previous cell hash for chaining
            system_time: Optional timestamp (defaults to now)

        Returns:
            REPORT_RUN DecisionCell

        Raises:
            IncompleteReportError: If report is incomplete
        """
        is_valid, errors = self.validate()
        if not is_valid:
            raise IncompleteReportError(
                f"Report incomplete: {', '.join(errors)}"
            )

        if not system_time:
            system_time = get_current_timestamp()

        if not self.rendered_at:
            self.rendered_at = system_time

        payload = {
            "schema_version": "1.0",
            "case_id": self.case_id,
            "pack_id": self.pack.pack_id if self.pack else "unknown",
            "pack_version": self.pack.version if self.pack else "0.0.0",
            "anchor_head_cell_id": self.anchor_head_cell_id,
            "included_cell_ids": sorted(set(self.included_cell_ids)),  # Dedupe and sort
            "template_id": self.template_id,
            "template_version": self.template_version,
            "rendered_artifact_hash": self.rendered_artifact_hash,
            "rendered_at": self.rendered_at,
        }

        # Validate against pack if provided
        if self.pack:
            validate_payload(self.pack, CellType.REPORT_RUN, payload, strict=False)

        return DecisionCell(
            header=Header(
                version="1.0",
                graph_id=graph_id,
                cell_type=CellType.REPORT_RUN,
                system_time=system_time,
                prev_cell_hash=prev_cell_hash,
                hash_scheme=HASH_SCHEME_CANONICAL
            ),
            fact=Fact(
                namespace=namespace,
                subject=self.case_id,
                predicate="report.generated",
                object=payload,
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(
                rule_id=f"report:{self.template_id}:{self.template_version}",
                rule_logic_hash=compute_rule_logic_hash(
                    f"report:{self.template_id}:{self.template_version}"
                ),
                interpreter="decisiongraph:report:v2"
            )
        )

    def build_manifest(self) -> ReportManifest:
        """Build a ReportManifest without creating a cell."""
        is_valid, errors = self.validate()
        if not is_valid:
            raise IncompleteReportError(
                f"Report incomplete: {', '.join(errors)}"
            )

        return ReportManifest(
            case_id=self.case_id,
            pack_id=self.pack.pack_id if self.pack else "unknown",
            pack_version=self.pack.version if self.pack else "0.0.0",
            anchor_head_cell_id=self.anchor_head_cell_id,
            included_cell_ids=sorted(set(self.included_cell_ids)),
            template_id=self.template_id,
            template_version=self.template_version,
            rendered_artifact_hash=self.rendered_artifact_hash,
            rendered_at=self.rendered_at or get_current_timestamp(),
        )


# =============================================================================
# JUDGMENT BUILDER
# =============================================================================

@dataclass
class JudgmentData:
    """Data for a judgment."""
    action: JudgmentAction
    tier: int
    reviewer: str
    target_cell_id: str
    rationale: str
    evidence_refs: List[str] = field(default_factory=list)
    conditions: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for cell payload."""
        result = {
            "schema_version": "1.0",
            "action": self.action.value,
            "tier": self.tier,
            "reviewer": self.reviewer,
            "target_cell_id": self.target_cell_id,
            "rationale": self.rationale,
            "evidence_refs": self.evidence_refs,
        }
        if self.conditions:
            result["conditions"] = self.conditions
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JudgmentData':
        """Create from dict."""
        return cls(
            action=JudgmentAction(data["action"]),
            tier=data["tier"],
            reviewer=data["reviewer"],
            target_cell_id=data["target_cell_id"],
            rationale=data["rationale"],
            evidence_refs=data.get("evidence_refs", []),
            conditions=data.get("conditions"),
        )

    @classmethod
    def from_cell(cls, cell: DecisionCell) -> 'JudgmentData':
        """Extract judgment data from a JUDGMENT cell."""
        if cell.header.cell_type != CellType.JUDGMENT:
            raise JudgmentError(f"Expected JUDGMENT cell, got {cell.header.cell_type}")
        return cls.from_dict(cell.fact.object)


class JudgmentBuilder:
    """
    Builder for creating JUDGMENT cells.

    A JUDGMENT cell records a human or system signoff on a decision.
    """

    def __init__(self):
        self.action: Optional[JudgmentAction] = None
        self.tier: int = 1
        self.reviewer: Optional[str] = None
        self.target_cell_id: Optional[str] = None
        self.rationale: Optional[str] = None
        self.evidence_refs: List[str] = []
        self.conditions: Optional[str] = None

    def set_action(self, action: JudgmentAction) -> 'JudgmentBuilder':
        """Set the judgment action."""
        self.action = action
        return self

    def approve(self) -> 'JudgmentBuilder':
        """Shorthand for set_action(APPROVE)."""
        self.action = JudgmentAction.APPROVE
        return self

    def reject(self) -> 'JudgmentBuilder':
        """Shorthand for set_action(REJECT)."""
        self.action = JudgmentAction.REJECT
        return self

    def escalate(self) -> 'JudgmentBuilder':
        """Shorthand for set_action(ESCALATE)."""
        self.action = JudgmentAction.ESCALATE
        return self

    def defer(self) -> 'JudgmentBuilder':
        """Shorthand for set_action(DEFER)."""
        self.action = JudgmentAction.DEFER
        return self

    def override(self) -> 'JudgmentBuilder':
        """Shorthand for set_action(OVERRIDE)."""
        self.action = JudgmentAction.OVERRIDE
        return self

    def set_reviewer(self, reviewer: str, tier: int = 1) -> 'JudgmentBuilder':
        """Set the reviewer and tier."""
        self.reviewer = reviewer
        self.tier = tier
        return self

    def set_target(self, cell_id: str) -> 'JudgmentBuilder':
        """Set the target cell being judged."""
        self.target_cell_id = cell_id
        return self

    def set_rationale(self, rationale: str) -> 'JudgmentBuilder':
        """Set the rationale for the judgment."""
        self.rationale = rationale
        return self

    def add_evidence_ref(self, cell_id: str) -> 'JudgmentBuilder':
        """Add an evidence reference."""
        self.evidence_refs.append(cell_id)
        return self

    def set_evidence_refs(self, cell_ids: List[str]) -> 'JudgmentBuilder':
        """Set all evidence references."""
        self.evidence_refs = cell_ids
        return self

    def set_conditions(self, conditions: str) -> 'JudgmentBuilder':
        """Set conditions for the judgment (e.g., for conditional approval)."""
        self.conditions = conditions
        return self

    def validate(self) -> tuple[bool, List[str]]:
        """
        Validate the judgment is complete.

        Returns:
            (is_valid: bool, errors: List[str])
        """
        errors = []

        if not self.action:
            errors.append("action is required")
        if self.tier < 1:
            errors.append("tier must be >= 1")
        if not self.reviewer:
            errors.append("reviewer is required")
        if not self.target_cell_id:
            errors.append("target_cell_id is required")
        if not self.rationale:
            errors.append("rationale is required")

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
        Build the JUDGMENT cell.

        Args:
            graph_id: Graph ID for the cell
            namespace: Namespace for the cell
            subject: Subject (typically case_id)
            prev_cell_hash: Previous cell hash for chaining
            system_time: Optional timestamp (defaults to now)
            pack: Optional pack for payload validation

        Returns:
            JUDGMENT DecisionCell

        Raises:
            JudgmentError: If judgment is incomplete
        """
        is_valid, errors = self.validate()
        if not is_valid:
            raise JudgmentError(
                f"Judgment incomplete: {', '.join(errors)}"
            )

        if not system_time:
            system_time = get_current_timestamp()

        payload = JudgmentData(
            action=self.action,
            tier=self.tier,
            reviewer=self.reviewer,
            target_cell_id=self.target_cell_id,
            rationale=self.rationale,
            evidence_refs=self.evidence_refs,
            conditions=self.conditions,
        ).to_dict()

        # Validate against pack if provided
        if pack:
            validate_payload(pack, CellType.JUDGMENT, payload, strict=False)

        return DecisionCell(
            header=Header(
                version="1.0",
                graph_id=graph_id,
                cell_type=CellType.JUDGMENT,
                system_time=system_time,
                prev_cell_hash=prev_cell_hash,
                hash_scheme=HASH_SCHEME_CANONICAL
            ),
            fact=Fact(
                namespace=namespace,
                subject=subject,
                predicate="judgment.recorded",
                object=payload,
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(
                rule_id=f"judgment:{self.action.value.lower()}:tier{self.tier}",
                rule_logic_hash=compute_rule_logic_hash(
                    f"judgment:{self.action.value}:tier{self.tier}:reviewer:{self.reviewer}"
                ),
                interpreter="decisiongraph:judgment:v2"
            )
        )


# =============================================================================
# REPORT VERIFICATION
# =============================================================================

def verify_report_artifact(
    report_cell: DecisionCell,
    artifact_bytes: bytes
) -> bool:
    """
    Verify a rendered artifact matches its report cell.

    Args:
        report_cell: The REPORT_RUN cell
        artifact_bytes: The rendered artifact bytes

    Returns:
        True if artifact hash matches, False otherwise

    Raises:
        ReportVerificationError: If cell is not a REPORT_RUN
    """
    if report_cell.header.cell_type != CellType.REPORT_RUN:
        raise ReportVerificationError(
            f"Expected REPORT_RUN cell, got {report_cell.header.cell_type}"
        )

    expected_hash = report_cell.fact.object.get("rendered_artifact_hash")
    actual_hash = hashlib.sha256(artifact_bytes).hexdigest()

    return expected_hash == actual_hash


def verify_report_cells_included(
    report_cell: DecisionCell,
    cells: List[DecisionCell]
) -> tuple[bool, List[str], List[str]]:
    """
    Verify all required cells are included in the report.

    Args:
        report_cell: The REPORT_RUN cell
        cells: Cells that should be in the report

    Returns:
        (all_included: bool, missing: List[str], extra: List[str])
    """
    if report_cell.header.cell_type != CellType.REPORT_RUN:
        raise ReportVerificationError(
            f"Expected REPORT_RUN cell, got {report_cell.header.cell_type}"
        )

    included = set(report_cell.fact.object.get("included_cell_ids", []))
    expected = {c.cell_id for c in cells}

    missing = list(expected - included)
    extra = list(included - expected)

    return len(missing) == 0 and len(extra) == 0, missing, extra


def get_report_status(
    report_cell: DecisionCell,
    judgments: List[DecisionCell],
    required_tiers: int = 1
) -> ReportStatus:
    """
    Determine the status of a report based on judgments.

    Args:
        report_cell: The REPORT_RUN cell
        judgments: Judgment cells for this report
        required_tiers: Number of approval tiers required

    Returns:
        ReportStatus
    """
    if report_cell.header.cell_type != CellType.REPORT_RUN:
        raise ReportVerificationError(
            f"Expected REPORT_RUN cell, got {report_cell.header.cell_type}"
        )

    # Filter judgments targeting this report
    report_judgments = [
        j for j in judgments
        if j.header.cell_type == CellType.JUDGMENT
        and j.fact.object.get("target_cell_id") == report_cell.cell_id
    ]

    if not report_judgments:
        return ReportStatus.PENDING_REVIEW

    # Check for any rejections
    for j in report_judgments:
        if j.fact.object.get("action") == JudgmentAction.REJECT.value:
            return ReportStatus.REJECTED

    # Check for escalations
    for j in report_judgments:
        if j.fact.object.get("action") == JudgmentAction.ESCALATE.value:
            return ReportStatus.ESCALATED

    # Count approval tiers
    approved_tiers = set()
    for j in report_judgments:
        if j.fact.object.get("action") == JudgmentAction.APPROVE.value:
            approved_tiers.add(j.fact.object.get("tier", 1))

    if len(approved_tiers) >= required_tiers:
        return ReportStatus.APPROVED

    return ReportStatus.PENDING_REVIEW


@dataclass
class ReportSummary:
    """Summary of a report and its judgments."""
    report_cell_id: str
    case_id: str
    status: ReportStatus
    included_cell_count: int
    judgment_count: int
    approved_tiers: List[int]
    pending_tiers: List[int]
    rejected: bool
    escalated: bool

    @property
    def is_complete(self) -> bool:
        """Whether the report has completed review."""
        return self.status in (ReportStatus.APPROVED, ReportStatus.REJECTED)


def analyze_report(
    report_cell: DecisionCell,
    judgments: List[DecisionCell],
    required_tiers: int = 1
) -> ReportSummary:
    """
    Analyze a report and its judgments.

    Args:
        report_cell: The REPORT_RUN cell
        judgments: All judgment cells
        required_tiers: Number of approval tiers required

    Returns:
        ReportSummary with analysis
    """
    if report_cell.header.cell_type != CellType.REPORT_RUN:
        raise ReportVerificationError(
            f"Expected REPORT_RUN cell, got {report_cell.header.cell_type}"
        )

    # Filter judgments for this report
    report_judgments = [
        j for j in judgments
        if j.header.cell_type == CellType.JUDGMENT
        and j.fact.object.get("target_cell_id") == report_cell.cell_id
    ]

    approved_tiers = []
    rejected = False
    escalated = False

    for j in report_judgments:
        action = j.fact.object.get("action")
        tier = j.fact.object.get("tier", 1)

        if action == JudgmentAction.APPROVE.value:
            if tier not in approved_tiers:
                approved_tiers.append(tier)
        elif action == JudgmentAction.REJECT.value:
            rejected = True
        elif action == JudgmentAction.ESCALATE.value:
            escalated = True

    # Determine pending tiers
    all_required = list(range(1, required_tiers + 1))
    pending_tiers = [t for t in all_required if t not in approved_tiers]

    return ReportSummary(
        report_cell_id=report_cell.cell_id,
        case_id=report_cell.fact.object.get("case_id", ""),
        status=get_report_status(report_cell, judgments, required_tiers),
        included_cell_count=len(report_cell.fact.object.get("included_cell_ids", [])),
        judgment_count=len(report_judgments),
        approved_tiers=sorted(approved_tiers),
        pending_tiers=sorted(pending_tiers),
        rejected=rejected,
        escalated=escalated,
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def compute_artifact_hash(artifact_bytes: bytes) -> str:
    """Compute SHA-256 hash of artifact bytes."""
    return hashlib.sha256(artifact_bytes).hexdigest()


def create_approval_judgment(
    target_cell: DecisionCell,
    reviewer: str,
    rationale: str,
    tier: int = 1,
    evidence_refs: Optional[List[str]] = None
) -> JudgmentBuilder:
    """
    Create a pre-populated approval judgment builder.

    Args:
        target_cell: Cell being approved
        reviewer: Reviewer identifier
        rationale: Reason for approval
        tier: Approval tier
        evidence_refs: Optional evidence references

    Returns:
        JudgmentBuilder ready to build
    """
    builder = JudgmentBuilder()
    builder.approve()
    builder.set_target(target_cell.cell_id)
    builder.set_reviewer(reviewer, tier)
    builder.set_rationale(rationale)
    if evidence_refs:
        builder.set_evidence_refs(evidence_refs)
    return builder


def create_rejection_judgment(
    target_cell: DecisionCell,
    reviewer: str,
    rationale: str,
    tier: int = 1,
    evidence_refs: Optional[List[str]] = None
) -> JudgmentBuilder:
    """
    Create a pre-populated rejection judgment builder.

    Args:
        target_cell: Cell being rejected
        reviewer: Reviewer identifier
        rationale: Reason for rejection
        tier: Approval tier
        evidence_refs: Optional evidence references

    Returns:
        JudgmentBuilder ready to build
    """
    builder = JudgmentBuilder()
    builder.reject()
    builder.set_target(target_cell.cell_id)
    builder.set_reviewer(reviewer, tier)
    builder.set_rationale(rationale)
    if evidence_refs:
        builder.set_evidence_refs(evidence_refs)
    return builder


def create_escalation_judgment(
    target_cell: DecisionCell,
    reviewer: str,
    rationale: str,
    tier: int = 1
) -> JudgmentBuilder:
    """
    Create a pre-populated escalation judgment builder.

    Args:
        target_cell: Cell being escalated
        reviewer: Reviewer identifier
        rationale: Reason for escalation
        tier: Current tier

    Returns:
        JudgmentBuilder ready to build
    """
    builder = JudgmentBuilder()
    builder.escalate()
    builder.set_target(target_cell.cell_id)
    builder.set_reviewer(reviewer, tier)
    builder.set_rationale(rationale)
    return builder


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Exceptions
    'ReportError',
    'IncompleteReportError',
    'JudgmentError',
    'ReportVerificationError',
    # Enums
    'JudgmentAction',
    'ReportStatus',
    # Data classes
    'ReportManifest',
    'JudgmentData',
    'ReportSummary',
    # Builders
    'ReportBuilder',
    'JudgmentBuilder',
    # Verification
    'verify_report_artifact',
    'verify_report_cells_included',
    'get_report_status',
    'analyze_report',
    # Helpers
    'compute_artifact_hash',
    'create_approval_judgment',
    'create_rejection_judgment',
    'create_escalation_judgment',
]
