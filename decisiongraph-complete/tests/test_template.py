"""
Tests for decisiongraph.template module.

Tests cover:
- Template validation
- Cell filtering and sorting
- Section rendering (all layout types)
- Full report rendering
- Determinism verification (critical!)
- Template serialization round-trip
"""

import pytest
import hashlib
from dataclasses import dataclass

from decisiongraph import (
    DecisionCell, Header, Fact, LogicAnchor,
    CellType, SourceQuality,
    HASH_SCHEME_CANONICAL, NULL_HASH, get_current_timestamp
)
from decisiongraph.report import ReportManifest
from decisiongraph.template import (
    TemplateError,
    TemplateValidationError,
    RenderError,
    SectionLayout,
    Alignment,
    ColumnDefinition,
    SectionDefinition,
    CitationFormat,
    ScoreGridFormat,
    ReportTemplate,
    filter_cells_for_section,
    sort_cells_deterministic,
    render_report,
    render_report_text,
    render_section,
    render_integrity_section,
    create_aml_alert_template,
    template_to_dict,
    template_from_dict,
)


# =============================================================================
# FIXTURES
# =============================================================================

def make_fact_cell(
    subject: str = "case_001",
    predicate: str = "fact.recorded",
    obj: dict = None,
    timestamp: str = None
) -> DecisionCell:
    """Create a FACT cell for testing."""
    if obj is None:
        obj = {"key": "value"}
    return DecisionCell(
        header=Header(
            version="1.0",
            graph_id="graph:test",
            cell_type=CellType.FACT,
            system_time=timestamp or get_current_timestamp(),
            prev_cell_hash=NULL_HASH,
            hash_scheme=HASH_SCHEME_CANONICAL
        ),
        fact=Fact(
            namespace="test",
            subject=subject,
            predicate=predicate,
            object=obj,
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="fact_rule",
            rule_logic_hash="abc123"
        )
    )


def make_signal_cell(
    code: str = "TEST_SIGNAL",
    severity: str = "MEDIUM",
    timestamp: str = None
) -> DecisionCell:
    """Create a SIGNAL cell for testing."""
    return DecisionCell(
        header=Header(
            version="1.0",
            graph_id="graph:test",
            cell_type=CellType.SIGNAL,
            system_time=timestamp or get_current_timestamp(),
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
                "severity": severity,
                "trigger_facts": [],
                "policy_refs": []
            },
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="signal_rule",
            rule_logic_hash="def456"
        )
    )


def make_score_cell(score: str = "75", timestamp: str = None) -> DecisionCell:
    """Create a SCORE cell for testing."""
    return DecisionCell(
        header=Header(
            version="1.0",
            graph_id="graph:test",
            cell_type=CellType.SCORE,
            system_time=timestamp or get_current_timestamp(),
            prev_cell_hash=NULL_HASH,
            hash_scheme=HASH_SCHEME_CANONICAL
        ),
        fact=Fact(
            namespace="test",
            subject="case_001",
            predicate="score.computed",
            object={
                "schema_version": "1.0",
                "final_score": score,
                "score_type": "risk_score",
                "components": []
            },
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="score_rule",
            rule_logic_hash="ghi789"
        )
    )


def make_verdict_cell(outcome: str = "REVIEW", timestamp: str = None) -> DecisionCell:
    """Create a VERDICT cell for testing."""
    return DecisionCell(
        header=Header(
            version="1.0",
            graph_id="graph:test",
            cell_type=CellType.VERDICT,
            system_time=timestamp or get_current_timestamp(),
            prev_cell_hash=NULL_HASH,
            hash_scheme=HASH_SCHEME_CANONICAL
        ),
        fact=Fact(
            namespace="test",
            subject="case_001",
            predicate="verdict.rendered",
            object={
                "schema_version": "1.0",
                "outcome": outcome,
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
            rule_logic_hash="jkl012"
        )
    )


def make_justification_cell(target_id: str, timestamp: str = None) -> DecisionCell:
    """Create a JUSTIFICATION cell for testing."""
    return DecisionCell(
        header=Header(
            version="1.0",
            graph_id="graph:test",
            cell_type=CellType.JUSTIFICATION,
            system_time=timestamp or get_current_timestamp(),
            prev_cell_hash=NULL_HASH,
            hash_scheme=HASH_SCHEME_CANONICAL
        ),
        fact=Fact(
            namespace="test",
            subject="case_001",
            predicate="justification.recorded",
            object={
                "schema_version": "1.0",
                "target_cell_id": target_id,
                "question_set_id": "universal.v1",
                "answers": {
                    "basis_fact_ids": ["a" * 64],
                    "evidence_sufficient": True,
                    "missing_evidence": [],
                    "counterfactuals": ["If X were different"],
                    "policy_refs": [],
                    "needs_human_review": False
                },
                "rationale": "The evidence clearly supports this conclusion based on the pattern analysis."
            },
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="justification_rule",
            rule_logic_hash="mno345"
        )
    )


def make_mitigation_cell(code: str = "ESTABLISHED_CUSTOMER", timestamp: str = None) -> DecisionCell:
    """Create a MITIGATION cell for testing."""
    return DecisionCell(
        header=Header(
            version="1.0",
            graph_id="graph:test",
            cell_type=CellType.MITIGATION,
            system_time=timestamp or get_current_timestamp(),
            prev_cell_hash=NULL_HASH,
            hash_scheme=HASH_SCHEME_CANONICAL
        ),
        fact=Fact(
            namespace="test",
            subject="case_001",
            predicate="mitigation.applied",
            object={
                "schema_version": "1.0",
                "code": code,
                "description": "Customer has 10+ year relationship",
                "weight": "-10"
            },
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="mitigation_rule",
            rule_logic_hash="pqr678"
        )
    )


def make_manifest(
    case_id: str = "case_001",
    included_ids: list = None,
    rendered_at: str = "2024-01-15T10:30:00.000+00:00"
) -> ReportManifest:
    """Create a ReportManifest for testing."""
    if included_ids is None:
        included_ids = []
    return ReportManifest(
        case_id=case_id,
        pack_id="universal",
        pack_version="1.0.0",
        anchor_head_cell_id="a" * 64,
        included_cell_ids=included_ids,
        template_id="aml_alert",
        template_version="1.0.0",
        rendered_artifact_hash="b" * 64,
        rendered_at=rendered_at
    )


def make_simple_template() -> ReportTemplate:
    """Create a simple template for testing."""
    return ReportTemplate(
        template_id="test",
        template_version="1.0",
        name="Test Template",
        sections=[
            SectionDefinition(
                id="header",
                title="TEST REPORT",
                layout=SectionLayout.HEADER,
                show_empty=True
            ),
            SectionDefinition(
                id="signals",
                title="Signals",
                layout=SectionLayout.SIGNALS,
                cell_types=[CellType.SIGNAL]
            ),
        ]
    )


# =============================================================================
# TEMPLATE VALIDATION TESTS
# =============================================================================

class TestTemplateValidation:
    """Tests for template validation."""

    def test_valid_template(self):
        """Test validation of valid template."""
        template = make_simple_template()

        is_valid, errors = template.validate()

        assert is_valid
        assert len(errors) == 0

    def test_missing_template_id(self):
        """Test validation catches missing template_id."""
        template = ReportTemplate(
            template_id="",
            template_version="1.0",
            name="Test",
            sections=[SectionDefinition(id="s", title="S", layout=SectionLayout.LIST)]
        )

        is_valid, errors = template.validate()

        assert not is_valid
        assert "template_id is required" in errors

    def test_missing_sections(self):
        """Test validation catches missing sections."""
        template = ReportTemplate(
            template_id="test",
            template_version="1.0",
            name="Test",
            sections=[]
        )

        is_valid, errors = template.validate()

        assert not is_valid
        assert "At least one section is required" in errors

    def test_duplicate_section_ids(self):
        """Test validation catches duplicate section IDs."""
        template = ReportTemplate(
            template_id="test",
            template_version="1.0",
            name="Test",
            sections=[
                SectionDefinition(id="dup", title="First", layout=SectionLayout.LIST),
                SectionDefinition(id="dup", title="Second", layout=SectionLayout.LIST),
            ]
        )

        is_valid, errors = template.validate()

        assert not is_valid
        assert any("Duplicate section id" in e for e in errors)

    def test_table_without_columns(self):
        """Test validation catches TABLE layout without columns."""
        template = ReportTemplate(
            template_id="test",
            template_version="1.0",
            name="Test",
            sections=[
                SectionDefinition(
                    id="table",
                    title="Table",
                    layout=SectionLayout.TABLE,
                    columns=[]  # Empty!
                )
            ]
        )

        is_valid, errors = template.validate()

        assert not is_valid
        assert any("TABLE layout but no columns" in e for e in errors)

    def test_get_label_with_mapping(self):
        """Test label lookup with mapping."""
        template = ReportTemplate(
            template_id="test",
            template_version="1.0",
            name="Test",
            sections=[SectionDefinition(id="s", title="S", layout=SectionLayout.LIST)],
            label_map={"HIGH_VALUE_TXN": "High Value Transaction"}
        )

        assert template.get_label("HIGH_VALUE_TXN") == "High Value Transaction"

    def test_get_label_without_mapping(self):
        """Test label lookup falls back to title case."""
        template = ReportTemplate(
            template_id="test",
            template_version="1.0",
            name="Test",
            sections=[SectionDefinition(id="s", title="S", layout=SectionLayout.LIST)]
        )

        assert template.get_label("some_code") == "Some Code"


# =============================================================================
# CELL FILTERING TESTS
# =============================================================================

class TestCellFiltering:
    """Tests for cell filtering."""

    def test_filter_by_cell_type(self):
        """Test filtering by cell type."""
        signal = make_signal_cell()
        fact = make_fact_cell()
        section = SectionDefinition(
            id="signals",
            title="Signals",
            layout=SectionLayout.SIGNALS,
            cell_types=[CellType.SIGNAL]
        )

        result = filter_cells_for_section([signal, fact], section)

        assert len(result) == 1
        assert result[0].header.cell_type == CellType.SIGNAL

    def test_filter_by_predicate_pattern(self):
        """Test filtering by predicate pattern."""
        customer_fact = make_fact_cell(predicate="customer.profile")
        transaction_fact = make_fact_cell(predicate="transaction.deposit")
        section = SectionDefinition(
            id="customer",
            title="Customer",
            layout=SectionLayout.KEY_VALUE,
            cell_types=[CellType.FACT],
            predicate_patterns=["customer\\..*"]
        )

        result = filter_cells_for_section([customer_fact, transaction_fact], section)

        assert len(result) == 1
        assert result[0].fact.predicate == "customer.profile"

    def test_filter_combined_type_and_predicate(self):
        """Test filtering by both cell type and predicate."""
        signal = make_signal_cell()
        customer_fact = make_fact_cell(predicate="customer.profile")
        section = SectionDefinition(
            id="customer",
            title="Customer",
            layout=SectionLayout.KEY_VALUE,
            cell_types=[CellType.FACT],
            predicate_patterns=["customer\\..*"]
        )

        result = filter_cells_for_section([signal, customer_fact], section)

        assert len(result) == 1
        assert result[0].fact.predicate == "customer.profile"

    def test_filter_no_constraints_returns_all(self):
        """Test filtering with no constraints returns all cells."""
        signal = make_signal_cell()
        fact = make_fact_cell()
        section = SectionDefinition(
            id="all",
            title="All",
            layout=SectionLayout.LIST
        )

        result = filter_cells_for_section([signal, fact], section)

        assert len(result) == 2


# =============================================================================
# CELL SORTING TESTS
# =============================================================================

class TestCellSorting:
    """Tests for deterministic cell sorting."""

    def test_sort_by_timestamp(self):
        """Test cells are sorted by timestamp."""
        cell1 = make_signal_cell(code="FIRST", timestamp="2024-01-01T00:00:00.000+00:00")
        cell2 = make_signal_cell(code="SECOND", timestamp="2024-01-02T00:00:00.000+00:00")

        # Pass in reverse order
        result = sort_cells_deterministic([cell2, cell1])

        assert result[0].fact.object["code"] == "FIRST"
        assert result[1].fact.object["code"] == "SECOND"

    def test_sort_stable_with_same_timestamp(self):
        """Test sort is stable (deterministic) for same timestamp."""
        ts = "2024-01-01T00:00:00.000+00:00"
        cell1 = make_signal_cell(code="A", timestamp=ts)
        cell2 = make_signal_cell(code="B", timestamp=ts)

        # Sort twice
        result1 = sort_cells_deterministic([cell1, cell2])
        result2 = sort_cells_deterministic([cell2, cell1])

        # Should be same order (sorted by cell_id)
        assert result1[0].cell_id == result2[0].cell_id
        assert result1[1].cell_id == result2[1].cell_id


# =============================================================================
# SECTION RENDERING TESTS
# =============================================================================

class TestSectionRendering:
    """Tests for individual section rendering."""

    def test_render_signals_section(self):
        """Test signals section rendering."""
        template = make_simple_template()
        signal_high = make_signal_cell(code="HIGH_RISK", severity="HIGH")
        signal_med = make_signal_cell(code="MEDIUM_RISK", severity="MEDIUM")
        manifest = make_manifest()

        section = template.sections[1]  # signals section
        lines = render_section(section, [signal_high, signal_med], manifest, template, [])

        text = "\n".join(lines)
        assert "HIGH" in text
        assert "MEDIUM" in text
        assert "Signals" in text

    def test_render_empty_section_hidden(self):
        """Test empty sections are hidden by default."""
        template = make_simple_template()
        manifest = make_manifest()

        section = template.sections[1]  # signals section
        lines = render_section(section, [], manifest, template, [])

        assert len(lines) == 0

    def test_render_empty_section_shown_when_configured(self):
        """Test empty sections shown when show_empty=True."""
        template = make_simple_template()
        manifest = make_manifest()

        section = template.sections[0]  # header section (show_empty=True)
        lines = render_section(section, [], manifest, template, [])

        assert len(lines) > 0
        assert "TEST REPORT" in "\n".join(lines)

    def test_render_key_value_section(self):
        """Test key-value section rendering."""
        template = ReportTemplate(
            template_id="test",
            template_version="1.0",
            name="Test",
            sections=[
                SectionDefinition(
                    id="kv",
                    title="Customer Info",
                    layout=SectionLayout.KEY_VALUE,
                    cell_types=[CellType.FACT]
                )
            ]
        )
        fact = make_fact_cell(obj={"name": "John Doe", "age": 42})
        manifest = make_manifest()

        lines = render_section(template.sections[0], [fact], manifest, template, [])

        text = "\n".join(lines)
        assert "Name:" in text or "name:" in text.lower()
        assert "John Doe" in text

    def test_render_table_section(self):
        """Test table section rendering."""
        template = ReportTemplate(
            template_id="test",
            template_version="1.0",
            name="Test",
            sections=[
                SectionDefinition(
                    id="table",
                    title="Transactions",
                    layout=SectionLayout.TABLE,
                    cell_types=[CellType.FACT],
                    columns=[
                        ColumnDefinition(key="fact.object.type", header="Type", width=10),
                        ColumnDefinition(key="fact.object.amount", header="Amount", width=10),
                    ]
                )
            ]
        )
        fact = make_fact_cell(obj={"type": "DEPOSIT", "amount": "1000"})
        manifest = make_manifest()

        lines = render_section(template.sections[0], [fact], manifest, template, [])

        text = "\n".join(lines)
        assert "Type" in text
        assert "Amount" in text
        # Label transformation converts DEPOSIT to Deposit (title case)
        assert "Deposit" in text or "DEPOSIT" in text
        assert "1000" in text

    def test_render_grid_section(self):
        """Test grid section rendering."""
        template = ReportTemplate(
            template_id="test",
            template_version="1.0",
            name="Test",
            sections=[
                SectionDefinition(
                    id="grid",
                    title="Risk Summary",
                    layout=SectionLayout.GRID,
                    cell_types=[CellType.SCORE, CellType.VERDICT]
                )
            ]
        )
        score = make_score_cell(score="75")
        verdict = make_verdict_cell(outcome="REVIEW")
        manifest = make_manifest()

        lines = render_section(template.sections[0], [score, verdict], manifest, template, [])

        text = "\n".join(lines)
        assert "75" in text
        assert "VERDICT" in text

    def test_render_list_section(self):
        """Test list section rendering."""
        template = ReportTemplate(
            template_id="test",
            template_version="1.0",
            name="Test",
            sections=[
                SectionDefinition(
                    id="list",
                    title="Mitigations",
                    layout=SectionLayout.LIST,
                    cell_types=[CellType.MITIGATION]
                )
            ]
        )
        mitigation = make_mitigation_cell(code="ESTABLISHED_CUSTOMER")
        manifest = make_manifest()

        lines = render_section(template.sections[0], [mitigation], manifest, template, [])

        text = "\n".join(lines)
        assert "*" in text  # Bullet
        # Description is used and gets label transformation (title case)
        assert "10+" in text.lower() or "relationship" in text.lower()

    def test_render_prose_section(self):
        """Test prose section rendering."""
        template = ReportTemplate(
            template_id="test",
            template_version="1.0",
            name="Test",
            sections=[
                SectionDefinition(
                    id="prose",
                    title="Rationale",
                    layout=SectionLayout.PROSE,
                    cell_types=[CellType.JUSTIFICATION]
                )
            ]
        )
        justification = make_justification_cell("a" * 64)
        manifest = make_manifest()

        lines = render_section(template.sections[0], [justification], manifest, template, [])

        text = "\n".join(lines)
        assert "Rationale" in text


# =============================================================================
# FULL REPORT RENDERING TESTS
# =============================================================================

class TestFullReportRendering:
    """Tests for full report rendering."""

    def test_render_simple_report(self):
        """Test rendering a simple report."""
        template = make_simple_template()
        signal = make_signal_cell(code="TEST_SIGNAL", severity="HIGH")
        manifest = make_manifest(included_ids=[signal.cell_id])

        report_bytes = render_report(template, manifest, [signal])

        assert isinstance(report_bytes, bytes)
        text = report_bytes.decode("utf-8")
        assert "TEST REPORT" in text
        assert "HIGH" in text

    def test_render_returns_utf8_bytes(self):
        """Test render returns UTF-8 encoded bytes."""
        template = make_simple_template()
        manifest = make_manifest()

        report_bytes = render_report(template, manifest, [])

        assert isinstance(report_bytes, bytes)
        # Should be valid UTF-8
        text = report_bytes.decode("utf-8")
        assert isinstance(text, str)

    def test_render_text_convenience(self):
        """Test render_report_text convenience function."""
        template = make_simple_template()
        manifest = make_manifest()

        text = render_report_text(template, manifest, [])

        assert isinstance(text, str)
        assert "TEST REPORT" in text

    def test_render_includes_footer(self):
        """Test report includes footer text."""
        template = ReportTemplate(
            template_id="test",
            template_version="1.0",
            name="Test",
            sections=[SectionDefinition(id="s", title="Section", layout=SectionLayout.LIST, show_empty=True)],
            footer_text="This is the footer."
        )
        manifest = make_manifest()

        text = render_report_text(template, manifest, [])

        assert "This is the footer." in text

    def test_render_includes_generation_metadata(self):
        """Test report includes generation metadata."""
        template = make_simple_template()
        manifest = make_manifest()

        text = render_report_text(template, manifest, [])

        assert "Generated:" in text
        assert "Template:" in text
        assert "Manifest Hash:" in text

    def test_render_invalid_template_raises(self):
        """Test rendering with invalid template raises."""
        template = ReportTemplate(
            template_id="",  # Invalid
            template_version="1.0",
            name="Test",
            sections=[]
        )
        manifest = make_manifest()

        with pytest.raises(TemplateValidationError):
            render_report(template, manifest, [])


# =============================================================================
# DETERMINISM TESTS (CRITICAL!)
# =============================================================================

class TestDeterminism:
    """Tests for deterministic rendering - THE critical property."""

    def test_same_inputs_same_output(self):
        """Test same inputs produce identical output."""
        template = create_aml_alert_template()
        signal = make_signal_cell(code="HIGH_VALUE_TXN", timestamp="2024-01-15T10:00:00.000+00:00")
        score = make_score_cell(score="75", timestamp="2024-01-15T10:01:00.000+00:00")
        verdict = make_verdict_cell(outcome="REVIEW", timestamp="2024-01-15T10:02:00.000+00:00")
        manifest = make_manifest(
            included_ids=[signal.cell_id, score.cell_id, verdict.cell_id]
        )

        cells = [signal, score, verdict]

        # Render multiple times
        output1 = render_report(template, manifest, cells)
        output2 = render_report(template, manifest, cells)
        output3 = render_report(template, manifest, cells)

        assert output1 == output2
        assert output2 == output3

    def test_cell_order_does_not_affect_output(self):
        """Test cell order doesn't affect output (internal sorting)."""
        template = create_aml_alert_template()
        signal1 = make_signal_cell(code="FIRST", timestamp="2024-01-15T10:00:00.000+00:00")
        signal2 = make_signal_cell(code="SECOND", timestamp="2024-01-15T10:01:00.000+00:00")
        manifest = make_manifest(included_ids=[signal1.cell_id, signal2.cell_id])

        # Pass cells in different orders
        output1 = render_report(template, manifest, [signal1, signal2])
        output2 = render_report(template, manifest, [signal2, signal1])

        assert output1 == output2

    def test_output_hash_deterministic(self):
        """Test output hash is deterministic."""
        template = create_aml_alert_template()
        signal = make_signal_cell(timestamp="2024-01-15T10:00:00.000+00:00")
        manifest = make_manifest(included_ids=[signal.cell_id])

        output1 = render_report(template, manifest, [signal])
        output2 = render_report(template, manifest, [signal])

        hash1 = hashlib.sha256(output1).hexdigest()
        hash2 = hashlib.sha256(output2).hexdigest()

        assert hash1 == hash2

    def test_different_content_different_hash(self):
        """Test different content produces different hash."""
        template = create_aml_alert_template()
        signal1 = make_signal_cell(code="CODE_A", timestamp="2024-01-15T10:00:00.000+00:00")
        signal2 = make_signal_cell(code="CODE_B", timestamp="2024-01-15T10:00:00.000+00:00")
        manifest1 = make_manifest(included_ids=[signal1.cell_id])
        manifest2 = make_manifest(included_ids=[signal2.cell_id])

        output1 = render_report(template, manifest1, [signal1])
        output2 = render_report(template, manifest2, [signal2])

        hash1 = hashlib.sha256(output1).hexdigest()
        hash2 = hashlib.sha256(output2).hexdigest()

        assert hash1 != hash2


# =============================================================================
# AML TEMPLATE TESTS
# =============================================================================

class TestAMLAlertTemplate:
    """Tests for AML alert template."""

    def test_aml_template_valid(self):
        """Test AML template passes validation."""
        template = create_aml_alert_template()

        is_valid, errors = template.validate()

        assert is_valid
        assert len(errors) == 0

    def test_aml_template_has_required_sections(self):
        """Test AML template has required sections."""
        template = create_aml_alert_template()

        section_ids = {s.id for s in template.sections}

        assert "header" in section_ids
        assert "alert_summary" in section_ids
        assert "risk_indicators" in section_ids
        assert "citations" in section_ids

    def test_aml_template_label_map(self):
        """Test AML template has label mappings."""
        template = create_aml_alert_template()

        assert template.get_label("HIGH_VALUE_TXN") == "High Value Transaction"
        assert template.get_label("STRUCTURING") == "Potential Structuring"
        assert template.get_label("SAR") == "File SAR"

    def test_aml_template_renders_full_report(self):
        """Test AML template renders a full report."""
        template = create_aml_alert_template()

        # Create a realistic set of cells
        customer_fact = make_fact_cell(
            predicate="customer.profile",
            obj={"name": "John Doe", "account_age": "5 years", "risk_rating": "MEDIUM"}
        )
        signal = make_signal_cell(code="HIGH_VALUE_TXN", severity="HIGH")
        mitigation = make_mitigation_cell(code="ESTABLISHED_CUSTOMER")
        score = make_score_cell(score="65")
        verdict = make_verdict_cell(outcome="REVIEW")
        justification = make_justification_cell(verdict.cell_id)

        cells = [customer_fact, signal, mitigation, score, verdict, justification]
        manifest = make_manifest(included_ids=[c.cell_id for c in cells])

        text = render_report_text(template, manifest, cells)

        # Verify key sections present
        assert "TRANSACTION MONITORING ALERT REPORT" in text
        assert "ALERT SUMMARY" in text
        assert "RISK INDICATORS" in text
        assert "HIGH" in text  # Signal severity
        assert "Generated:" in text


# =============================================================================
# TEMPLATE SERIALIZATION TESTS
# =============================================================================

class TestTemplateSerialization:
    """Tests for template serialization."""

    def test_serialize_roundtrip(self):
        """Test template serialization round-trip."""
        original = create_aml_alert_template()

        # Serialize and deserialize
        data = template_to_dict(original)
        restored = template_from_dict(data)

        # Verify key properties
        assert restored.template_id == original.template_id
        assert restored.template_version == original.template_version
        assert len(restored.sections) == len(original.sections)
        assert restored.label_map == original.label_map

    def test_serialize_to_json_compatible(self):
        """Test serialized dict is JSON-compatible."""
        import json

        template = create_aml_alert_template()
        data = template_to_dict(template)

        # Should be serializable to JSON
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

        # And back
        restored_data = json.loads(json_str)
        restored = template_from_dict(restored_data)
        assert restored.template_id == template.template_id

    def test_serialized_template_produces_same_output(self):
        """Test serialized/restored template produces same output."""
        original = create_aml_alert_template()
        signal = make_signal_cell(timestamp="2024-01-15T10:00:00.000+00:00")
        manifest = make_manifest(included_ids=[signal.cell_id])

        # Render with original
        output1 = render_report(original, manifest, [signal])

        # Serialize and restore
        data = template_to_dict(original)
        restored = template_from_dict(data)

        # Render with restored
        output2 = render_report(restored, manifest, [signal])

        assert output1 == output2


# =============================================================================
# INTEGRITY SECTION TESTS
# =============================================================================

class TestIntegritySection:
    """Tests for integrity audit section."""

    def test_integrity_all_cells_present(self):
        """Test integrity check when all cells present."""
        template = make_simple_template()
        signal = make_signal_cell()
        manifest = make_manifest(included_ids=[signal.cell_id])

        lines = render_integrity_section(manifest, [signal], template)

        text = "\n".join(lines)
        assert "[PASS] Cell Inclusion Check" in text

    def test_integrity_missing_cells(self):
        """Test integrity check when cells missing."""
        template = make_simple_template()
        signal = make_signal_cell()
        manifest = make_manifest(included_ids=[signal.cell_id, "missing" + "0" * 57])

        lines = render_integrity_section(manifest, [signal], template)

        text = "\n".join(lines)
        assert "[FAIL] Cell Inclusion Check" in text

    def test_integrity_justification_coverage(self):
        """Test integrity reports justification coverage."""
        template = make_simple_template()
        signal = make_signal_cell()
        justification = make_justification_cell(signal.cell_id)
        manifest = make_manifest()

        lines = render_integrity_section(manifest, [signal, justification], template)

        text = "\n".join(lines)
        assert "Justification Coverage" in text

    def test_integrity_shows_evidence_count(self):
        """Test integrity shows evidence cell count."""
        template = make_simple_template()
        manifest = make_manifest()

        lines = render_integrity_section(manifest, [], template)

        text = "\n".join(lines)
        assert "Evidence Cells:" in text


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    def test_render_with_no_cells(self):
        """Test rendering with no cells."""
        template = create_aml_alert_template()
        manifest = make_manifest()

        # Should not raise
        text = render_report_text(template, manifest, [])

        assert "TRANSACTION MONITORING ALERT REPORT" in text

    def test_render_with_unicode_content(self):
        """Test rendering with unicode content."""
        template = make_simple_template()
        fact = make_fact_cell(obj={"name": "Jean-Pierre Müller", "city": "北京"})
        manifest = make_manifest()

        text = render_report_text(template, manifest, [fact])

        assert isinstance(text, str)
        # Unicode should be preserved
        # (The fact might not show in output due to section filtering,
        # but the render should not fail)

    def test_render_with_very_long_values(self):
        """Test rendering with very long values (truncation)."""
        template = ReportTemplate(
            template_id="test",
            template_version="1.0",
            name="Test",
            sections=[
                SectionDefinition(
                    id="table",
                    title="Data",
                    layout=SectionLayout.TABLE,
                    cell_types=[CellType.FACT],
                    columns=[
                        ColumnDefinition(key="fact.object.value", header="Value", width=10),
                    ]
                )
            ]
        )
        fact = make_fact_cell(obj={"value": "A" * 100})  # Very long
        manifest = make_manifest()

        text = render_report_text(template, manifest, [fact])

        # Should truncate, not fail (label transformation may change case)
        assert "a" * 10 in text.lower()  # 10 chars (case insensitive)
        assert "a" * 100 not in text.lower()  # Not full 100
