"""
Tests for DecisionGraph Bank-Grade Report Module.
"""

import pytest
from decimal import Decimal
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime, timezone

from decisiongraph.bank_report import (
    BankReportError,
    RenderError,
    TypologyClass,
    GateStatus,
    ReportConfig,
    EvidenceAnchor,
    EvidenceAnchorGrid,
    FeedbackScores,
    RequiredAction,
    GateResult,
    BankReportRenderer,
    render_bank_report,
)
from decisiongraph.citations import (
    CitationRegistry,
    PolicyCitation,
    CitationQuality,
)


# =============================================================================
# MOCK CLASSES FOR TESTING
# =============================================================================

@dataclass
class MockCaseMeta:
    id: str = "TEST-001"
    case_type: "MockCaseType" = None
    jurisdiction: str = "CA"
    status: str = "open"
    priority: str = "high"
    created_at: str = "2026-01-29T00:00:00Z"

    def __post_init__(self):
        if self.case_type is None:
            self.case_type = MockCaseType()


@dataclass
class MockCaseType:
    value: str = "aml_alert"


@dataclass
class MockIndividual:
    id: str = "IND-001"
    given_name: str = "John"
    family_name: str = "Doe"
    risk_rating: Optional["MockRiskRating"] = None

    @property
    def full_name(self):
        return f"{self.given_name} {self.family_name}"


@dataclass
class MockRiskRating:
    value: str = "high"


@dataclass
class MockCaseBundle:
    meta: MockCaseMeta = None
    individuals: List[MockIndividual] = None
    organizations: List = None
    accounts: List = None
    relationships: List = None
    evidence: List = None
    events: List = None

    def __post_init__(self):
        if self.meta is None:
            self.meta = MockCaseMeta()
        if self.individuals is None:
            self.individuals = [MockIndividual()]
        if self.organizations is None:
            self.organizations = []
        if self.accounts is None:
            self.accounts = []
        if self.relationships is None:
            self.relationships = []
        if self.evidence is None:
            self.evidence = []
        if self.events is None:
            self.events = []


@dataclass
class MockFact:
    object: dict


@dataclass
class MockCell:
    fact: MockFact
    cell_id: str = "cell_123"


@dataclass
class MockScore:
    fact: MockFact


@dataclass
class MockVerdict:
    fact: MockFact


@dataclass
class MockEvalResult:
    signals: List[MockCell] = None
    mitigations: List[MockCell] = None
    score: Optional[MockScore] = None
    verdict: Optional[MockVerdict] = None
    signals_fired: int = 0
    mitigations_applied: int = 0

    def __post_init__(self):
        if self.signals is None:
            self.signals = []
        if self.mitigations is None:
            self.mitigations = []


@dataclass
class MockPackRuntime:
    pack_id: str = "fincrime_canada_v1"
    pack_version: str = "1.0.0"
    pack_hash: str = "abc123def456" * 5
    name: str = "Canadian Financial Crime Pack"


@dataclass
class MockValidation:
    is_valid: bool = True


class MockChain:
    graph_id: str = "graph:test-123"

    def __len__(self):
        return 10

    def validate(self):
        return MockValidation()


# =============================================================================
# TESTS
# =============================================================================

class TestReportConfig:
    """Tests for ReportConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ReportConfig()

        assert config.line_width == 72
        assert config.include_citations is True
        assert config.include_feedback_scores is True
        assert config.include_audit_trail is True
        assert config.template_id == "bank_grade_v1"

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ReportConfig(
            line_width=80,
            include_citations=False,
            template_id="custom_v1"
        )

        assert config.line_width == 80
        assert config.include_citations is False
        assert config.template_id == "custom_v1"


class TestEvidenceAnchorGrid:
    """Tests for EvidenceAnchorGrid."""

    def test_empty_grid(self):
        """Test empty evidence anchor grid."""
        grid = EvidenceAnchorGrid(inherent_weight=Decimal("1.00"))

        assert grid.inherent_weight == Decimal("1.00")
        assert grid.mitigation_sum == Decimal("0")
        assert grid.residual_score == Decimal("1.00")

    def test_grid_with_mitigations(self):
        """Test grid with mitigations."""
        grid = EvidenceAnchorGrid(
            inherent_weight=Decimal("1.00"),
            anchors=[
                EvidenceAnchor(
                    offset_type="Documentation",
                    data_anchor="docs_complete",
                    weight=Decimal("-0.25")
                ),
                EvidenceAnchor(
                    offset_type="Established",
                    data_anchor="tenure_5y",
                    weight=Decimal("-0.30")
                ),
            ]
        )

        assert grid.mitigation_sum == Decimal("-0.55")
        assert grid.residual_score == Decimal("0.45")

    def test_residual_floor_zero(self):
        """Test that residual score floors at zero."""
        grid = EvidenceAnchorGrid(
            inherent_weight=Decimal("0.50"),
            anchors=[
                EvidenceAnchor(
                    offset_type="Heavy Mitigation",
                    data_anchor="test",
                    weight=Decimal("-1.00")
                ),
            ]
        )

        assert grid.residual_score == Decimal("0")


class TestFeedbackScores:
    """Tests for FeedbackScores."""

    def test_compute_scores_full_coverage(self):
        """Test computing scores with full coverage."""
        quality = CitationQuality(
            total_signals=10,
            signals_with_citations=10,
            total_citations=10,
            coverage_ratio=Decimal("1.00"),
            missing_signals=[]
        )

        scores = FeedbackScores.compute(
            citation_quality=quality,
            signals_fired=5,
            total_signals=10,
            evidence_anchored=5,
            total_evidence=5,
            auto_archive=True,
            docs_on_file=8,
            docs_required=8,
        )

        assert scores.citation_quality == Decimal("1.00")
        assert scores.documentation_completeness == Decimal("1.00")
        assert scores.decision_clarity == Decimal("1.00")
        assert scores.confidence >= Decimal("0.90")

    def test_compute_scores_partial_coverage(self):
        """Test computing scores with partial coverage."""
        quality = CitationQuality(
            total_signals=10,
            signals_with_citations=5,
            total_citations=5,
            coverage_ratio=Decimal("0.50"),
            missing_signals=["SIG_1", "SIG_2"]
        )

        scores = FeedbackScores.compute(
            citation_quality=quality,
            signals_fired=3,
            total_signals=10,
            evidence_anchored=3,
            total_evidence=5,
            auto_archive=False,
            docs_on_file=4,
            docs_required=8,
        )

        assert scores.citation_quality == Decimal("0.50")
        assert scores.documentation_completeness == Decimal("0.50")
        assert scores.decision_clarity == Decimal("0.50")

    def test_scores_to_dict(self):
        """Test scores serialization."""
        scores = FeedbackScores(
            confidence=Decimal("0.75"),
            citation_quality=Decimal("1.00"),
            signal_coverage=Decimal("0.50"),
            evidence_completeness=Decimal("0.80"),
            decision_clarity=Decimal("0.50"),
            documentation_completeness=Decimal("0.75"),
        )

        d = scores.to_dict()
        assert d["confidence"] == "0.75"
        assert d["citation_quality"] == "1.00"


class TestGateResult:
    """Tests for GateResult."""

    def test_gate_result_pass(self):
        """Test passing gate result."""
        gate = GateResult(
            gate_name="Integrity Audit",
            gate_number=4,
            status=GateStatus.PASS,
            details={"chain_valid": True}
        )

        assert gate.gate_name == "Integrity Audit"
        assert gate.gate_number == 4
        assert gate.status == GateStatus.PASS

    def test_gate_result_to_dict(self):
        """Test gate result serialization."""
        gate = GateResult(
            gate_name="Test Gate",
            gate_number=1,
            status=GateStatus.WARN,
            details={"warning": "test"}
        )

        d = gate.to_dict()
        assert d["gate_name"] == "Test Gate"
        assert d["status"] == "WARN"


class TestBankReportRenderer:
    """Tests for BankReportRenderer."""

    def test_render_basic_report(self):
        """Test rendering a basic report."""
        renderer = BankReportRenderer()

        bundle = MockCaseBundle()
        eval_result = MockEvalResult()
        pack_runtime = MockPackRuntime()
        chain = MockChain()

        report_bytes = renderer.render(
            case_bundle=bundle,
            eval_result=eval_result,
            pack_runtime=pack_runtime,
            chain=chain,
        )

        assert isinstance(report_bytes, bytes)
        report_text = report_bytes.decode('utf-8')

        # Check for expected sections
        assert "CASE SUMMARY" in report_text
        assert "TEST-001" in report_text
        assert "END OF REPORT" in report_text

    def test_render_with_signals(self):
        """Test rendering a report with signals."""
        renderer = BankReportRenderer()

        bundle = MockCaseBundle()
        eval_result = MockEvalResult(
            signals=[
                MockCell(
                    fact=MockFact(object={
                        "code": "TXN_LARGE_CASH",
                        "severity": "MEDIUM",
                        "name": "Large Cash Transaction"
                    }),
                    cell_id="sig_001"
                ),
            ],
            signals_fired=1
        )
        pack_runtime = MockPackRuntime()
        chain = MockChain()

        report_bytes = renderer.render(
            case_bundle=bundle,
            eval_result=eval_result,
            pack_runtime=pack_runtime,
            chain=chain,
        )

        report_text = report_bytes.decode('utf-8')

        assert "INHERENT RISKS DETECTED" in report_text
        assert "TXN_LARGE_CASH" in report_text

    def test_render_with_verdict(self):
        """Test rendering a report with verdict."""
        renderer = BankReportRenderer()

        bundle = MockCaseBundle()
        eval_result = MockEvalResult(
            score=MockScore(
                fact=MockFact(object={
                    "inherent_score": "0.75",
                    "mitigation_sum": "-0.25",
                    "residual_score": "0.50",
                    "threshold_gate": "ANALYST_REVIEW"
                })
            ),
            verdict=MockVerdict(
                fact=MockFact(object={
                    "verdict": "ANALYST_REVIEW",
                    "auto_archive_permitted": False
                })
            ),
        )
        pack_runtime = MockPackRuntime()
        chain = MockChain()

        report_bytes = renderer.render(
            case_bundle=bundle,
            eval_result=eval_result,
            pack_runtime=pack_runtime,
            chain=chain,
        )

        report_text = report_bytes.decode('utf-8')

        assert "DECISION" in report_text
        assert "ANALYST_REVIEW" in report_text

    def test_render_with_citations(self):
        """Test rendering a report with citations."""
        renderer = BankReportRenderer(config=ReportConfig(include_citations=True))

        bundle = MockCaseBundle()
        eval_result = MockEvalResult(
            signals=[
                MockCell(
                    fact=MockFact(object={
                        "code": "TXN_LARGE_CASH",
                        "severity": "MEDIUM"
                    }),
                    cell_id="sig_001"
                ),
            ],
            signals_fired=1
        )
        pack_runtime = MockPackRuntime()
        chain = MockChain()

        # Create citation registry
        registry = CitationRegistry()
        registry.register_signal_citation("TXN_LARGE_CASH", PolicyCitation(
            authority="FINTRAC",
            document="PCMLTFR",
            section="s. 12"
        ))

        report_bytes = renderer.render(
            case_bundle=bundle,
            eval_result=eval_result,
            pack_runtime=pack_runtime,
            chain=chain,
            citation_registry=registry,
        )

        report_text = report_bytes.decode('utf-8')

        assert "POLICY CITATIONS" in report_text
        assert "FINTRAC" in report_text

    def test_render_deterministic(self):
        """Test that rendering is deterministic."""
        renderer = BankReportRenderer()

        bundle = MockCaseBundle()
        eval_result = MockEvalResult()
        pack_runtime = MockPackRuntime()
        chain = MockChain()

        report1 = renderer.render(
            case_bundle=bundle,
            eval_result=eval_result,
            pack_runtime=pack_runtime,
            chain=chain,
            report_timestamp="2026-01-29T12:00:00Z"
        )

        report2 = renderer.render(
            case_bundle=bundle,
            eval_result=eval_result,
            pack_runtime=pack_runtime,
            chain=chain,
            report_timestamp="2026-01-29T12:00:00Z"
        )

        assert report1 == report2

    def test_render_4_gate_sections(self):
        """Test that all 4 gates are rendered."""
        renderer = BankReportRenderer()

        bundle = MockCaseBundle()
        eval_result = MockEvalResult()
        pack_runtime = MockPackRuntime()
        chain = MockChain()

        report_bytes = renderer.render(
            case_bundle=bundle,
            eval_result=eval_result,
            pack_runtime=pack_runtime,
            chain=chain,
        )

        report_text = report_bytes.decode('utf-8')

        assert "GATE 1: CONTEXTUAL TYPOLOGY" in report_text
        assert "GATE 2: INHERENT RISKS DETECTED" in report_text
        assert "GATE 3: RESIDUAL RISK CALCULATION" in report_text
        assert "GATE 4: INTEGRITY AUDIT" in report_text


class TestRenderBankReport:
    """Tests for render_bank_report convenience function."""

    def test_render_convenience_function(self):
        """Test the convenience function."""
        bundle = MockCaseBundle()
        eval_result = MockEvalResult()
        pack_runtime = MockPackRuntime()
        chain = MockChain()

        report_bytes = render_bank_report(
            case_bundle=bundle,
            eval_result=eval_result,
            pack_runtime=pack_runtime,
            chain=chain,
        )

        assert isinstance(report_bytes, bytes)
        report_text = report_bytes.decode('utf-8')
        assert "CASE SUMMARY" in report_text


class TestRequiredAction:
    """Tests for RequiredAction."""

    def test_action_creation(self):
        """Test creating a required action."""
        action = RequiredAction(
            action="Complete case review",
            sla_hours=168
        )

        assert action.action == "Complete case review"
        assert action.sla_hours == 168

    def test_action_to_dict(self):
        """Test action serialization."""
        action = RequiredAction(
            action="Escalate to compliance",
            sla_hours=24
        )

        d = action.to_dict()
        assert d["action"] == "Escalate to compliance"
        assert d["sla_hours"] == 24


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
