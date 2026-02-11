"""
Tests for decisiongraph.report module.

Tests cover:
- ReportManifest creation and serialization
- ReportBuilder validation and building
- JudgmentBuilder validation and building
- Report verification functions
- Report status and analysis
"""

import hashlib
import pytest
from dataclasses import dataclass

from decisiongraph import (
    DecisionCell, Header, Fact, LogicAnchor,
    CellType, SourceQuality,
    HASH_SCHEME_CANONICAL, NULL_HASH, get_current_timestamp
)
from decisiongraph.pack import create_universal_pack
from decisiongraph.report import (
    ReportError,
    IncompleteReportError,
    JudgmentError,
    ReportVerificationError,
    JudgmentAction,
    ReportStatus,
    ReportManifest,
    JudgmentData,
    ReportSummary,
    ReportBuilder,
    JudgmentBuilder,
    verify_report_artifact,
    verify_report_cells_included,
    get_report_status,
    analyze_report,
    compute_artifact_hash,
    create_approval_judgment,
    create_rejection_judgment,
    create_escalation_judgment,
)


# =============================================================================
# FIXTURES
# =============================================================================

def make_signal_cell(code: str = "SIGNAL_001") -> DecisionCell:
    """Create a mock SIGNAL cell for testing."""
    return DecisionCell(
        header=Header(
            version="1.0",
            graph_id="graph:test",
            cell_type=CellType.SIGNAL,
            system_time=get_current_timestamp(),
            prev_cell_hash=NULL_HASH,
            hash_scheme=HASH_SCHEME_CANONICAL
        ),
        fact=Fact(
            namespace="test",
            subject="case_001",
            predicate="signal.fired",
            object={
                "schema_version": "1.0",
                "code": code,
                "severity": "MEDIUM",
                "trigger_facts": [],
                "policy_refs": []
            },
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="test_rule",
            rule_logic_hash="abc123"
        )
    )


def make_verdict_cell() -> DecisionCell:
    """Create a mock VERDICT cell for testing."""
    return DecisionCell(
        header=Header(
            version="1.0",
            graph_id="graph:test",
            cell_type=CellType.VERDICT,
            system_time=get_current_timestamp(),
            prev_cell_hash=NULL_HASH,
            hash_scheme=HASH_SCHEME_CANONICAL
        ),
        fact=Fact(
            namespace="test",
            subject="case_001",
            predicate="verdict.rendered",
            object={
                "schema_version": "1.0",
                "outcome": "REVIEW",
                "confidence": "0.85",
                "signals": [],
                "mitigations": [],
                "final_score": "75"
            },
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="verdict_rule",
            rule_logic_hash="def456"
        )
    )


def make_report_cell(case_id: str = "case_001", included_ids: list = None) -> DecisionCell:
    """Create a mock REPORT_RUN cell for testing."""
    if included_ids is None:
        included_ids = ["a" * 64, "b" * 64]
    return DecisionCell(
        header=Header(
            version="1.0",
            graph_id="graph:test",
            cell_type=CellType.REPORT_RUN,
            system_time=get_current_timestamp(),
            prev_cell_hash=NULL_HASH,
            hash_scheme=HASH_SCHEME_CANONICAL
        ),
        fact=Fact(
            namespace="test",
            subject=case_id,
            predicate="report.generated",
            object={
                "schema_version": "1.0",
                "case_id": case_id,
                "pack_id": "universal",
                "pack_version": "1.0.0",
                "anchor_head_cell_id": "c" * 64,
                "included_cell_ids": included_ids,
                "template_id": "aml_sar",
                "template_version": "1.0",
                "rendered_artifact_hash": "d" * 64,
                "rendered_at": get_current_timestamp(),
            },
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="report:aml_sar:1.0",
            rule_logic_hash="ghi789"
        )
    )


def make_judgment_cell(
    target_cell_id: str,
    action: JudgmentAction = JudgmentAction.APPROVE,
    tier: int = 1
) -> DecisionCell:
    """Create a mock JUDGMENT cell for testing."""
    return DecisionCell(
        header=Header(
            version="1.0",
            graph_id="graph:test",
            cell_type=CellType.JUDGMENT,
            system_time=get_current_timestamp(),
            prev_cell_hash=NULL_HASH,
            hash_scheme=HASH_SCHEME_CANONICAL
        ),
        fact=Fact(
            namespace="test",
            subject="case_001",
            predicate="judgment.recorded",
            object={
                "schema_version": "1.0",
                "action": action.value,
                "tier": tier,
                "reviewer": "analyst_001",
                "target_cell_id": target_cell_id,
                "rationale": "Test rationale",
                "evidence_refs": [],
            },
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id=f"judgment:{action.value.lower()}:tier{tier}",
            rule_logic_hash="jkl012"
        )
    )


# =============================================================================
# REPORT MANIFEST TESTS
# =============================================================================

class TestReportManifest:
    """Tests for ReportManifest."""

    def test_manifest_to_dict(self):
        """Test manifest serialization."""
        manifest = ReportManifest(
            case_id="case_001",
            pack_id="universal",
            pack_version="1.0.0",
            anchor_head_cell_id="a" * 64,
            included_cell_ids=["b" * 64, "c" * 64],
            template_id="aml_sar",
            template_version="1.0",
            rendered_artifact_hash="d" * 64,
            rendered_at="2024-01-01T00:00:00.000+00:00"
        )

        data = manifest.to_dict()

        assert data["schema_version"] == "1.0"
        assert data["case_id"] == "case_001"
        assert data["pack_id"] == "universal"
        assert len(data["included_cell_ids"]) == 2

    def test_manifest_from_dict(self):
        """Test manifest deserialization."""
        data = {
            "case_id": "case_002",
            "pack_id": "aml",
            "pack_version": "2.0.0",
            "anchor_head_cell_id": "e" * 64,
            "included_cell_ids": ["f" * 64],
            "template_id": "sar",
            "template_version": "2.0",
            "rendered_artifact_hash": "g" * 64,
            "rendered_at": "2024-01-02T00:00:00.000+00:00"
        }

        manifest = ReportManifest.from_dict(data)

        assert manifest.case_id == "case_002"
        assert manifest.pack_id == "aml"
        assert manifest.template_version == "2.0"

    def test_manifest_from_cell(self):
        """Test manifest extraction from REPORT_RUN cell."""
        cell = make_report_cell(case_id="case_003")

        manifest = ReportManifest.from_cell(cell)

        assert manifest.case_id == "case_003"
        assert manifest.pack_id == "universal"

    def test_manifest_from_wrong_cell_type_raises(self):
        """Test manifest extraction from wrong cell type raises."""
        cell = make_signal_cell()

        with pytest.raises(ReportError, match="Expected REPORT_RUN"):
            ReportManifest.from_cell(cell)

    def test_manifest_compute_content_hash(self):
        """Test manifest content hash is deterministic."""
        manifest1 = ReportManifest(
            case_id="case_001",
            pack_id="universal",
            pack_version="1.0.0",
            anchor_head_cell_id="a" * 64,
            included_cell_ids=["b" * 64],
            template_id="aml_sar",
            template_version="1.0",
            rendered_artifact_hash="c" * 64,
            rendered_at="2024-01-01T00:00:00.000+00:00"
        )
        manifest2 = ReportManifest(
            case_id="case_001",
            pack_id="universal",
            pack_version="1.0.0",
            anchor_head_cell_id="a" * 64,
            included_cell_ids=["b" * 64],
            template_id="aml_sar",
            template_version="1.0",
            rendered_artifact_hash="c" * 64,
            rendered_at="2024-01-01T00:00:00.000+00:00"
        )

        assert manifest1.compute_content_hash() == manifest2.compute_content_hash()

    def test_manifest_different_content_different_hash(self):
        """Test different manifest content produces different hash."""
        manifest1 = ReportManifest(
            case_id="case_001",
            pack_id="universal",
            pack_version="1.0.0",
            anchor_head_cell_id="a" * 64,
            included_cell_ids=["b" * 64],
            template_id="aml_sar",
            template_version="1.0",
            rendered_artifact_hash="c" * 64,
            rendered_at="2024-01-01T00:00:00.000+00:00"
        )
        manifest2 = ReportManifest(
            case_id="case_002",  # Different case
            pack_id="universal",
            pack_version="1.0.0",
            anchor_head_cell_id="a" * 64,
            included_cell_ids=["b" * 64],
            template_id="aml_sar",
            template_version="1.0",
            rendered_artifact_hash="c" * 64,
            rendered_at="2024-01-01T00:00:00.000+00:00"
        )

        assert manifest1.compute_content_hash() != manifest2.compute_content_hash()


# =============================================================================
# REPORT BUILDER TESTS
# =============================================================================

class TestReportBuilder:
    """Tests for ReportBuilder."""

    def test_builder_fluent_interface(self):
        """Test builder returns self for chaining."""
        builder = ReportBuilder()

        result = builder.set_case_id("case_001")
        assert result is builder

        result = builder.set_anchor_head("a" * 64)
        assert result is builder

    def test_builder_validate_missing_fields(self):
        """Test validation catches missing fields."""
        builder = ReportBuilder()

        is_valid, errors = builder.validate()

        assert not is_valid
        assert "case_id is required" in errors
        assert "anchor_head_cell_id is required" in errors
        assert "At least one cell must be included" in errors

    def test_builder_validate_complete(self):
        """Test validation passes with all fields."""
        builder = ReportBuilder()
        builder.set_case_id("case_001")
        builder.set_anchor_head("a" * 64)
        builder.add_cell_ids(["b" * 64])
        builder.set_template("aml_sar", "1.0")
        builder.set_rendered_hash("c" * 64)

        is_valid, errors = builder.validate()

        assert is_valid
        assert len(errors) == 0

    def test_builder_add_cells(self):
        """Test adding cells to builder."""
        builder = ReportBuilder()
        cell1 = make_signal_cell(code="SIG1")
        cell2 = make_signal_cell(code="SIG2")

        builder.add_cell(cell1)
        builder.add_cells([cell2])

        assert cell1.cell_id in builder.included_cell_ids
        assert cell2.cell_id in builder.included_cell_ids

    def test_builder_build_success(self):
        """Test building REPORT_RUN cell."""
        pack = create_universal_pack()
        builder = ReportBuilder(pack=pack)
        builder.set_case_id("case_001")
        builder.set_anchor_head("a" * 64)
        builder.add_cell_ids(["b" * 64, "c" * 64])
        builder.set_template("aml_sar", "1.0")
        builder.set_rendered_hash("d" * 64)

        cell = builder.build(
            graph_id="graph:test",
            namespace="test",
            prev_cell_hash=NULL_HASH
        )

        assert cell.header.cell_type == CellType.REPORT_RUN
        assert cell.fact.object["case_id"] == "case_001"
        assert cell.fact.object["pack_id"] == "universal"
        assert len(cell.fact.object["included_cell_ids"]) == 2

    def test_builder_build_incomplete_raises(self):
        """Test building incomplete report raises."""
        builder = ReportBuilder()
        builder.set_case_id("case_001")
        # Missing other required fields

        with pytest.raises(IncompleteReportError):
            builder.build(
                graph_id="graph:test",
                namespace="test",
                prev_cell_hash=NULL_HASH
            )

    def test_builder_dedupes_and_sorts_cells(self):
        """Test builder deduplicates and sorts included cells."""
        builder = ReportBuilder()
        builder.set_case_id("case_001")
        builder.set_anchor_head("a" * 64)
        builder.add_cell_ids(["z" * 64, "a" * 64, "z" * 64])  # Duplicates and unsorted
        builder.set_template("aml_sar", "1.0")
        builder.set_rendered_hash("c" * 64)

        cell = builder.build(
            graph_id="graph:test",
            namespace="test",
            prev_cell_hash=NULL_HASH
        )

        included = cell.fact.object["included_cell_ids"]
        assert len(included) == 2  # Deduped
        assert included == sorted(included)  # Sorted

    def test_builder_build_manifest(self):
        """Test building manifest without cell."""
        pack = create_universal_pack()
        builder = ReportBuilder(pack=pack)
        builder.set_case_id("case_001")
        builder.set_anchor_head("a" * 64)
        builder.add_cell_ids(["b" * 64])
        builder.set_template("aml_sar", "1.0")
        builder.set_rendered_hash("c" * 64)

        manifest = builder.build_manifest()

        assert manifest.case_id == "case_001"
        assert manifest.pack_id == "universal"


# =============================================================================
# JUDGMENT DATA TESTS
# =============================================================================

class TestJudgmentData:
    """Tests for JudgmentData."""

    def test_judgment_data_to_dict(self):
        """Test judgment data serialization."""
        data = JudgmentData(
            action=JudgmentAction.APPROVE,
            tier=1,
            reviewer="analyst_001",
            target_cell_id="a" * 64,
            rationale="Sufficient evidence",
            evidence_refs=["b" * 64],
            conditions=None
        )

        result = data.to_dict()

        assert result["action"] == "APPROVE"
        assert result["tier"] == 1
        assert result["reviewer"] == "analyst_001"

    def test_judgment_data_with_conditions(self):
        """Test judgment data with conditions."""
        data = JudgmentData(
            action=JudgmentAction.APPROVE,
            tier=1,
            reviewer="analyst_001",
            target_cell_id="a" * 64,
            rationale="Conditional approval",
            conditions="Subject to manager review"
        )

        result = data.to_dict()

        assert "conditions" in result
        assert result["conditions"] == "Subject to manager review"

    def test_judgment_data_from_dict(self):
        """Test judgment data deserialization."""
        input_data = {
            "action": "REJECT",
            "tier": 2,
            "reviewer": "manager_001",
            "target_cell_id": "c" * 64,
            "rationale": "Insufficient evidence",
            "evidence_refs": []
        }

        data = JudgmentData.from_dict(input_data)

        assert data.action == JudgmentAction.REJECT
        assert data.tier == 2
        assert data.reviewer == "manager_001"

    def test_judgment_data_from_cell(self):
        """Test judgment data extraction from JUDGMENT cell."""
        cell = make_judgment_cell("a" * 64, JudgmentAction.ESCALATE, tier=2)

        data = JudgmentData.from_cell(cell)

        assert data.action == JudgmentAction.ESCALATE
        assert data.tier == 2

    def test_judgment_data_from_wrong_cell_raises(self):
        """Test extraction from wrong cell type raises."""
        cell = make_signal_cell()

        with pytest.raises(JudgmentError, match="Expected JUDGMENT"):
            JudgmentData.from_cell(cell)


# =============================================================================
# JUDGMENT BUILDER TESTS
# =============================================================================

class TestJudgmentBuilder:
    """Tests for JudgmentBuilder."""

    def test_builder_fluent_interface(self):
        """Test builder returns self for chaining."""
        builder = JudgmentBuilder()

        result = builder.approve()
        assert result is builder

        result = builder.set_reviewer("analyst_001", tier=1)
        assert result is builder

    def test_builder_action_shortcuts(self):
        """Test action shortcut methods."""
        builder = JudgmentBuilder()

        builder.approve()
        assert builder.action == JudgmentAction.APPROVE

        builder.reject()
        assert builder.action == JudgmentAction.REJECT

        builder.escalate()
        assert builder.action == JudgmentAction.ESCALATE

        builder.defer()
        assert builder.action == JudgmentAction.DEFER

        builder.override()
        assert builder.action == JudgmentAction.OVERRIDE

    def test_builder_validate_missing_fields(self):
        """Test validation catches missing fields."""
        builder = JudgmentBuilder()

        is_valid, errors = builder.validate()

        assert not is_valid
        assert "action is required" in errors
        assert "reviewer is required" in errors
        assert "target_cell_id is required" in errors
        assert "rationale is required" in errors

    def test_builder_validate_invalid_tier(self):
        """Test validation catches invalid tier."""
        builder = JudgmentBuilder()
        builder.approve()
        builder.set_reviewer("analyst_001", tier=0)  # Invalid
        builder.set_target("a" * 64)
        builder.set_rationale("Test")

        is_valid, errors = builder.validate()

        assert not is_valid
        assert "tier must be >= 1" in errors

    def test_builder_validate_complete(self):
        """Test validation passes with all fields."""
        builder = JudgmentBuilder()
        builder.approve()
        builder.set_reviewer("analyst_001", tier=1)
        builder.set_target("a" * 64)
        builder.set_rationale("Sufficient evidence")

        is_valid, errors = builder.validate()

        assert is_valid
        assert len(errors) == 0

    def test_builder_build_success(self):
        """Test building JUDGMENT cell."""
        builder = JudgmentBuilder()
        builder.approve()
        builder.set_reviewer("analyst_001", tier=1)
        builder.set_target("a" * 64)
        builder.set_rationale("Evidence is sufficient")
        builder.add_evidence_ref("b" * 64)

        cell = builder.build(
            graph_id="graph:test",
            namespace="test",
            subject="case_001",
            prev_cell_hash=NULL_HASH
        )

        assert cell.header.cell_type == CellType.JUDGMENT
        assert cell.fact.object["action"] == "APPROVE"
        assert cell.fact.object["reviewer"] == "analyst_001"
        assert len(cell.fact.object["evidence_refs"]) == 1

    def test_builder_build_incomplete_raises(self):
        """Test building incomplete judgment raises."""
        builder = JudgmentBuilder()
        builder.approve()
        # Missing other required fields

        with pytest.raises(JudgmentError):
            builder.build(
                graph_id="graph:test",
                namespace="test",
                subject="case_001",
                prev_cell_hash=NULL_HASH
            )

    def test_builder_with_conditions(self):
        """Test building judgment with conditions."""
        builder = JudgmentBuilder()
        builder.approve()
        builder.set_reviewer("analyst_001", tier=1)
        builder.set_target("a" * 64)
        builder.set_rationale("Conditional approval")
        builder.set_conditions("Subject to manager review")

        cell = builder.build(
            graph_id="graph:test",
            namespace="test",
            subject="case_001",
            prev_cell_hash=NULL_HASH
        )

        assert cell.fact.object.get("conditions") == "Subject to manager review"


# =============================================================================
# REPORT VERIFICATION TESTS
# =============================================================================

class TestReportVerification:
    """Tests for report verification functions."""

    def test_verify_artifact_matches(self):
        """Test artifact verification when hash matches."""
        artifact = b"Test report content"
        artifact_hash = hashlib.sha256(artifact).hexdigest()

        cell = make_report_cell()
        # Override the hash with actual hash
        cell.fact.object["rendered_artifact_hash"] = artifact_hash

        assert verify_report_artifact(cell, artifact)

    def test_verify_artifact_mismatch(self):
        """Test artifact verification when hash doesn't match."""
        artifact = b"Test report content"
        cell = make_report_cell()  # Has different hash

        assert not verify_report_artifact(cell, artifact)

    def test_verify_artifact_wrong_cell_type_raises(self):
        """Test artifact verification with wrong cell type raises."""
        cell = make_signal_cell()

        with pytest.raises(ReportVerificationError):
            verify_report_artifact(cell, b"content")

    def test_verify_cells_included_all_present(self):
        """Test cell verification when all cells present."""
        cell1 = make_signal_cell(code="SIG1")
        cell2 = make_signal_cell(code="SIG2")

        report_cell = make_report_cell(
            included_ids=[cell1.cell_id, cell2.cell_id]
        )

        all_included, missing, extra = verify_report_cells_included(
            report_cell, [cell1, cell2]
        )

        assert all_included
        assert len(missing) == 0
        assert len(extra) == 0

    def test_verify_cells_included_missing_cells(self):
        """Test cell verification with missing cells."""
        cell1 = make_signal_cell(code="SIG1")
        cell2 = make_signal_cell(code="SIG2")

        report_cell = make_report_cell(included_ids=[cell1.cell_id])

        all_included, missing, extra = verify_report_cells_included(
            report_cell, [cell1, cell2]
        )

        assert not all_included
        assert cell2.cell_id in missing

    def test_verify_cells_included_extra_cells(self):
        """Test cell verification with extra cells."""
        cell1 = make_signal_cell(code="SIG1")
        cell2 = make_signal_cell(code="SIG2")

        report_cell = make_report_cell(
            included_ids=[cell1.cell_id, cell2.cell_id, "extra" + "0" * 58]
        )

        all_included, missing, extra = verify_report_cells_included(
            report_cell, [cell1, cell2]
        )

        assert not all_included
        assert len(extra) == 1


# =============================================================================
# REPORT STATUS TESTS
# =============================================================================

class TestReportStatus:
    """Tests for report status functions."""

    def test_status_pending_no_judgments(self):
        """Test status is pending when no judgments."""
        report_cell = make_report_cell()

        status = get_report_status(report_cell, [])

        assert status == ReportStatus.PENDING_REVIEW

    def test_status_approved_single_tier(self):
        """Test status is approved with single tier approval."""
        report_cell = make_report_cell()
        judgment = make_judgment_cell(
            report_cell.cell_id,
            JudgmentAction.APPROVE,
            tier=1
        )

        status = get_report_status(report_cell, [judgment], required_tiers=1)

        assert status == ReportStatus.APPROVED

    def test_status_pending_missing_tier(self):
        """Test status is pending when tier missing."""
        report_cell = make_report_cell()
        judgment = make_judgment_cell(
            report_cell.cell_id,
            JudgmentAction.APPROVE,
            tier=1
        )

        status = get_report_status(report_cell, [judgment], required_tiers=2)

        assert status == ReportStatus.PENDING_REVIEW

    def test_status_approved_multi_tier(self):
        """Test status is approved with multi-tier approval."""
        report_cell = make_report_cell()
        j1 = make_judgment_cell(report_cell.cell_id, JudgmentAction.APPROVE, tier=1)
        j2 = make_judgment_cell(report_cell.cell_id, JudgmentAction.APPROVE, tier=2)

        status = get_report_status(report_cell, [j1, j2], required_tiers=2)

        assert status == ReportStatus.APPROVED

    def test_status_rejected(self):
        """Test status is rejected with rejection."""
        report_cell = make_report_cell()
        judgment = make_judgment_cell(
            report_cell.cell_id,
            JudgmentAction.REJECT,
            tier=1
        )

        status = get_report_status(report_cell, [judgment])

        assert status == ReportStatus.REJECTED

    def test_status_escalated(self):
        """Test status is escalated with escalation."""
        report_cell = make_report_cell()
        judgment = make_judgment_cell(
            report_cell.cell_id,
            JudgmentAction.ESCALATE,
            tier=1
        )

        status = get_report_status(report_cell, [judgment])

        assert status == ReportStatus.ESCALATED

    def test_status_rejection_overrides_approval(self):
        """Test rejection takes precedence over approval."""
        report_cell = make_report_cell()
        j1 = make_judgment_cell(report_cell.cell_id, JudgmentAction.APPROVE, tier=1)
        j2 = make_judgment_cell(report_cell.cell_id, JudgmentAction.REJECT, tier=2)

        status = get_report_status(report_cell, [j1, j2])

        assert status == ReportStatus.REJECTED


# =============================================================================
# REPORT ANALYSIS TESTS
# =============================================================================

class TestReportAnalysis:
    """Tests for report analysis."""

    def test_analyze_empty_report(self):
        """Test analysis with no judgments."""
        report_cell = make_report_cell()

        summary = analyze_report(report_cell, [])

        assert summary.report_cell_id == report_cell.cell_id
        assert summary.status == ReportStatus.PENDING_REVIEW
        assert summary.judgment_count == 0
        assert len(summary.approved_tiers) == 0

    def test_analyze_approved_report(self):
        """Test analysis of approved report."""
        report_cell = make_report_cell()
        j1 = make_judgment_cell(report_cell.cell_id, JudgmentAction.APPROVE, tier=1)
        j2 = make_judgment_cell(report_cell.cell_id, JudgmentAction.APPROVE, tier=2)

        summary = analyze_report(report_cell, [j1, j2], required_tiers=2)

        assert summary.status == ReportStatus.APPROVED
        assert summary.judgment_count == 2
        assert 1 in summary.approved_tiers
        assert 2 in summary.approved_tiers
        assert len(summary.pending_tiers) == 0
        assert summary.is_complete

    def test_analyze_pending_tiers(self):
        """Test analysis shows pending tiers."""
        report_cell = make_report_cell()
        j1 = make_judgment_cell(report_cell.cell_id, JudgmentAction.APPROVE, tier=1)

        summary = analyze_report(report_cell, [j1], required_tiers=3)

        assert summary.status == ReportStatus.PENDING_REVIEW
        assert 1 in summary.approved_tiers
        assert 2 in summary.pending_tiers
        assert 3 in summary.pending_tiers
        assert not summary.is_complete

    def test_analyze_rejected_report(self):
        """Test analysis of rejected report."""
        report_cell = make_report_cell()
        judgment = make_judgment_cell(
            report_cell.cell_id,
            JudgmentAction.REJECT
        )

        summary = analyze_report(report_cell, [judgment])

        assert summary.status == ReportStatus.REJECTED
        assert summary.rejected
        assert summary.is_complete

    def test_analyze_escalated_report(self):
        """Test analysis of escalated report."""
        report_cell = make_report_cell()
        judgment = make_judgment_cell(
            report_cell.cell_id,
            JudgmentAction.ESCALATE
        )

        summary = analyze_report(report_cell, [judgment])

        assert summary.status == ReportStatus.ESCALATED
        assert summary.escalated

    def test_analyze_ignores_other_report_judgments(self):
        """Test analysis ignores judgments for other reports."""
        report_cell = make_report_cell()
        other_judgment = make_judgment_cell(
            "other" + "0" * 59,  # Different target
            JudgmentAction.APPROVE
        )

        summary = analyze_report(report_cell, [other_judgment])

        assert summary.judgment_count == 0
        assert summary.status == ReportStatus.PENDING_REVIEW


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================

class TestHelperFunctions:
    """Tests for helper functions."""

    def test_compute_artifact_hash(self):
        """Test artifact hash computation."""
        content = b"Test content"
        expected = hashlib.sha256(content).hexdigest()

        assert compute_artifact_hash(content) == expected

    def test_create_approval_judgment(self):
        """Test approval judgment helper."""
        target = make_verdict_cell()

        builder = create_approval_judgment(
            target_cell=target,
            reviewer="analyst_001",
            rationale="Evidence sufficient",
            tier=1
        )

        assert builder.action == JudgmentAction.APPROVE
        assert builder.target_cell_id == target.cell_id
        assert builder.reviewer == "analyst_001"

    def test_create_rejection_judgment(self):
        """Test rejection judgment helper."""
        target = make_verdict_cell()

        builder = create_rejection_judgment(
            target_cell=target,
            reviewer="analyst_001",
            rationale="Insufficient evidence",
            tier=1
        )

        assert builder.action == JudgmentAction.REJECT

    def test_create_escalation_judgment(self):
        """Test escalation judgment helper."""
        target = make_verdict_cell()

        builder = create_escalation_judgment(
            target_cell=target,
            reviewer="analyst_001",
            rationale="Requires senior review"
        )

        assert builder.action == JudgmentAction.ESCALATE

    def test_approval_with_evidence_refs(self):
        """Test approval helper with evidence refs."""
        target = make_verdict_cell()

        builder = create_approval_judgment(
            target_cell=target,
            reviewer="analyst_001",
            rationale="Evidence sufficient",
            evidence_refs=["a" * 64, "b" * 64]
        )

        assert len(builder.evidence_refs) == 2


# =============================================================================
# REPORT SUMMARY TESTS
# =============================================================================

class TestReportSummary:
    """Tests for ReportSummary properties."""

    def test_summary_is_complete_approved(self):
        """Test is_complete for approved status."""
        summary = ReportSummary(
            report_cell_id="a" * 64,
            case_id="case_001",
            status=ReportStatus.APPROVED,
            included_cell_count=5,
            judgment_count=2,
            approved_tiers=[1, 2],
            pending_tiers=[],
            rejected=False,
            escalated=False
        )

        assert summary.is_complete

    def test_summary_is_complete_rejected(self):
        """Test is_complete for rejected status."""
        summary = ReportSummary(
            report_cell_id="a" * 64,
            case_id="case_001",
            status=ReportStatus.REJECTED,
            included_cell_count=5,
            judgment_count=1,
            approved_tiers=[],
            pending_tiers=[],
            rejected=True,
            escalated=False
        )

        assert summary.is_complete

    def test_summary_not_complete_pending(self):
        """Test is_complete for pending status."""
        summary = ReportSummary(
            report_cell_id="a" * 64,
            case_id="case_001",
            status=ReportStatus.PENDING_REVIEW,
            included_cell_count=5,
            judgment_count=0,
            approved_tiers=[],
            pending_tiers=[1],
            rejected=False,
            escalated=False
        )

        assert not summary.is_complete
