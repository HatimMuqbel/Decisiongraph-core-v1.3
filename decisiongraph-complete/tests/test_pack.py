"""
Tests for DecisionGraph Pack Module (v2.0)

Tests cover:
- Pack creation and serialization
- Schema validation
- Predicate validation
- Built-in universal schemas
- Pack loading from files
"""

import json
import pytest
import tempfile
from pathlib import Path

from decisiongraph import CellType
from decisiongraph.pack import (
    # Exceptions
    PackError,
    PackLoadError,
    PackValidationError,
    SchemaValidationError,
    PredicateError,
    # Schema types
    SchemaType,
    FieldSchema,
    PayloadSchema,
    PredicateDefinition,
    # Pack
    Pack,
    # Loading
    load_pack,
    # Validation
    validate_payload,
    validate_predicate,
    # Built-in schemas
    create_signal_schema,
    create_mitigation_schema,
    create_score_schema,
    create_verdict_schema,
    create_justification_schema,
    create_report_run_schema,
    create_judgment_schema,
    create_universal_pack,
)


# =============================================================================
# FIELD SCHEMA TESTS
# =============================================================================

class TestFieldSchema:
    """Tests for FieldSchema dataclass."""

    def test_basic_field(self):
        """Test basic field creation."""
        field = FieldSchema(
            name="code",
            type=SchemaType.STRING,
            required=True,
            description="Signal code"
        )
        assert field.name == "code"
        assert field.type == SchemaType.STRING
        assert field.required is True

    def test_field_to_dict(self):
        """Test field serialization."""
        field = FieldSchema(
            name="score",
            type=SchemaType.DECIMAL,
            required=True,
            description="Risk score"
        )
        d = field.to_dict()
        assert d["name"] == "score"
        assert d["type"] == "decimal"
        assert d["required"] is True

    def test_field_from_dict(self):
        """Test field deserialization."""
        data = {
            "name": "severity",
            "type": "enum",
            "required": True,
            "enum_values": ["LOW", "MEDIUM", "HIGH"]
        }
        field = FieldSchema.from_dict(data)
        assert field.name == "severity"
        assert field.type == SchemaType.ENUM
        assert field.enum_values == ["LOW", "MEDIUM", "HIGH"]

    def test_array_field(self):
        """Test array field with items_type."""
        field = FieldSchema(
            name="cell_ids",
            type=SchemaType.ARRAY,
            required=True,
            items_type=SchemaType.CELL_ID
        )
        d = field.to_dict()
        assert d["items_type"] == "cell_id"

    def test_nested_object_field(self):
        """Test nested object field with properties."""
        field = FieldSchema(
            name="answers",
            type=SchemaType.OBJECT,
            required=True,
            properties={
                "sufficient": FieldSchema(
                    name="sufficient",
                    type=SchemaType.BOOLEAN,
                    required=True
                )
            }
        )
        d = field.to_dict()
        assert "properties" in d
        assert d["properties"]["sufficient"]["type"] == "boolean"


# =============================================================================
# PAYLOAD SCHEMA TESTS
# =============================================================================

class TestPayloadSchema:
    """Tests for PayloadSchema dataclass."""

    def test_schema_creation(self):
        """Test schema creation."""
        schema = PayloadSchema(
            cell_type=CellType.SIGNAL,
            schema_version="1.0",
            description="Signal schema"
        )
        assert schema.cell_type == CellType.SIGNAL
        assert schema.schema_version == "1.0"

    def test_schema_roundtrip(self):
        """Test schema serialization and deserialization."""
        schema = create_signal_schema()
        d = schema.to_dict()
        restored = PayloadSchema.from_dict(d)
        assert restored.cell_type == schema.cell_type
        assert restored.schema_version == schema.schema_version
        assert len(restored.fields) == len(schema.fields)


# =============================================================================
# PREDICATE DEFINITION TESTS
# =============================================================================

class TestPredicateDefinition:
    """Tests for PredicateDefinition dataclass."""

    def test_predicate_creation(self):
        """Test predicate creation."""
        pred = PredicateDefinition(
            code="signal.fired",
            description="Signal was triggered",
            cell_types=[CellType.SIGNAL]
        )
        assert pred.code == "signal.fired"
        assert CellType.SIGNAL in pred.cell_types

    def test_predicate_roundtrip(self):
        """Test predicate serialization and deserialization."""
        pred = PredicateDefinition(
            code="verdict.rendered",
            description="Verdict rendered",
            cell_types=[CellType.VERDICT]
        )
        d = pred.to_dict()
        restored = PredicateDefinition.from_dict(d)
        assert restored.code == pred.code
        assert restored.cell_types == pred.cell_types


# =============================================================================
# PACK TESTS
# =============================================================================

class TestPack:
    """Tests for Pack dataclass."""

    def test_pack_creation(self):
        """Test basic pack creation."""
        pack = Pack(
            pack_id="test_pack",
            name="Test Pack",
            version="1.0.0"
        )
        assert pack.pack_id == "test_pack"
        assert pack.version == "1.0.0"

    def test_pack_hash_deterministic(self):
        """Test pack hash is deterministic."""
        pack1 = create_universal_pack()
        pack2 = create_universal_pack()
        assert pack1.pack_hash == pack2.pack_hash

    def test_pack_hash_changes_with_version(self):
        """Test pack hash changes with version."""
        pack1 = create_universal_pack(version="1.0.0")
        pack2 = create_universal_pack(version="1.0.1")
        assert pack1.pack_hash != pack2.pack_hash

    def test_pack_has_predicate(self):
        """Test has_predicate method."""
        pack = create_universal_pack()
        assert pack.has_predicate("signal.fired")
        assert not pack.has_predicate("nonexistent.predicate")

    def test_pack_has_schema(self):
        """Test has_schema method."""
        pack = create_universal_pack()
        assert pack.has_schema(CellType.SIGNAL)
        assert not pack.has_schema(CellType.GENESIS)

    def test_pack_get_schema(self):
        """Test get_schema method."""
        pack = create_universal_pack()
        schema = pack.get_schema(CellType.SIGNAL)
        assert schema is not None
        assert schema.cell_type == CellType.SIGNAL
        assert pack.get_schema(CellType.GENESIS) is None

    def test_pack_roundtrip(self):
        """Test pack JSON serialization and deserialization."""
        pack = create_universal_pack()
        json_str = pack.to_json()
        restored = Pack.from_json(json_str)
        assert restored.pack_id == pack.pack_id
        assert restored.version == pack.version
        assert restored.pack_hash == pack.pack_hash


# =============================================================================
# PACK LOADING TESTS
# =============================================================================

class TestPackLoading:
    """Tests for pack loading from files."""

    def test_load_pack_from_file(self):
        """Test loading pack from JSON file."""
        pack = create_universal_pack()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(pack.to_json())
            f.flush()
            path = Path(f.name)

        try:
            loaded = load_pack(path)
            assert loaded.pack_id == pack.pack_id
            assert loaded.pack_hash == pack.pack_hash
        finally:
            path.unlink()

    def test_load_pack_file_not_found(self):
        """Test error when pack file doesn't exist."""
        with pytest.raises(PackLoadError, match="not found"):
            load_pack("/nonexistent/path/pack.json")

    def test_load_pack_invalid_json(self):
        """Test error when pack file has invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json {{{")
            f.flush()
            path = Path(f.name)

        try:
            with pytest.raises(PackLoadError, match="Invalid JSON"):
                load_pack(path)
        finally:
            path.unlink()

    def test_load_pack_missing_required_field(self):
        """Test error when pack is missing required fields."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"name": "Test"}')  # Missing pack_id, version
            f.flush()
            path = Path(f.name)

        try:
            with pytest.raises(PackValidationError):
                load_pack(path)
        finally:
            path.unlink()


# =============================================================================
# PAYLOAD VALIDATION TESTS
# =============================================================================

class TestPayloadValidation:
    """Tests for payload validation against schemas."""

    def test_valid_signal_payload(self):
        """Test valid SIGNAL payload passes validation."""
        pack = create_universal_pack()
        payload = {
            "schema_version": "1.0",
            "code": "HIGH_VALUE_CRYPTO",
            "severity": "MEDIUM",
            "trigger_facts": [
                "a" * 64,  # Valid cell_id
                "b" * 64,
            ],
            "policy_refs": []
        }
        warnings = validate_payload(pack, CellType.SIGNAL, payload)
        assert len(warnings) == 0

    def test_missing_required_field(self):
        """Test missing required field raises error."""
        pack = create_universal_pack()
        payload = {
            "schema_version": "1.0",
            "code": "HIGH_VALUE_CRYPTO",
            # Missing severity, trigger_facts
        }
        with pytest.raises(SchemaValidationError, match="Missing required field"):
            validate_payload(pack, CellType.SIGNAL, payload)

    def test_invalid_enum_value(self):
        """Test invalid enum value raises error."""
        pack = create_universal_pack()
        payload = {
            "schema_version": "1.0",
            "code": "TEST",
            "severity": "INVALID_SEVERITY",
            "trigger_facts": []
        }
        with pytest.raises(SchemaValidationError, match="must be one of"):
            validate_payload(pack, CellType.SIGNAL, payload)

    def test_invalid_cell_id_format(self):
        """Test invalid cell_id format raises error."""
        pack = create_universal_pack()
        payload = {
            "schema_version": "1.0",
            "code": "TEST",
            "severity": "LOW",
            "trigger_facts": ["not-a-valid-cell-id"]
        }
        with pytest.raises(SchemaValidationError, match="64-char hex"):
            validate_payload(pack, CellType.SIGNAL, payload)

    def test_invalid_decimal_format(self):
        """Test invalid decimal format raises error."""
        pack = create_universal_pack()
        payload = {
            "schema_version": "1.0",
            "code": "MF_001",
            "weight": "not-a-decimal",  # Invalid
            "anchors": [],
            "applies_to_signals": []
        }
        with pytest.raises(SchemaValidationError, match="string-encoded decimal"):
            validate_payload(pack, CellType.MITIGATION, payload)

    def test_valid_decimal_formats(self):
        """Test valid decimal formats pass."""
        pack = create_universal_pack()
        for weight in ["-0.50", "0.0", "1.5", "-100.25", "0"]:
            payload = {
                "schema_version": "1.0",
                "code": "MF_001",
                "weight": weight,
                "anchors": [],
                "applies_to_signals": []
            }
            warnings = validate_payload(pack, CellType.MITIGATION, payload)
            assert len(warnings) == 0

    def test_unknown_fields_strict_mode(self):
        """Test unknown fields rejected in strict mode."""
        pack = create_universal_pack()
        payload = {
            "schema_version": "1.0",
            "code": "TEST",
            "severity": "LOW",
            "trigger_facts": [],
            "unknown_field": "should fail"
        }
        with pytest.raises(SchemaValidationError, match="Unknown fields"):
            validate_payload(pack, CellType.SIGNAL, payload, strict=True)

    def test_unknown_fields_non_strict_mode(self):
        """Test unknown fields allowed in non-strict mode."""
        pack = create_universal_pack()
        payload = {
            "schema_version": "1.0",
            "code": "TEST",
            "severity": "LOW",
            "trigger_facts": [],
            "unknown_field": "should pass"
        }
        # Should not raise
        warnings = validate_payload(pack, CellType.SIGNAL, payload, strict=False)
        assert len(warnings) == 0

    def test_schema_version_mismatch_warning(self):
        """Test schema version mismatch produces warning."""
        pack = create_universal_pack()
        payload = {
            "schema_version": "2.0",  # Different from pack's 1.0
            "code": "TEST",
            "severity": "LOW",
            "trigger_facts": []
        }
        warnings = validate_payload(pack, CellType.SIGNAL, payload)
        assert any("version mismatch" in w for w in warnings)

    def test_valid_score_payload(self):
        """Test valid SCORE payload passes validation."""
        pack = create_universal_pack()
        payload = {
            "schema_version": "1.0",
            "inherent_score": "1.00",
            "mitigation_sum": "-0.50",
            "residual_score": "0.50",
            "threshold_gate": "CLEAR_AND_CLOSE"
        }
        warnings = validate_payload(pack, CellType.SCORE, payload)
        assert len(warnings) == 0

    def test_valid_verdict_payload(self):
        """Test valid VERDICT payload passes validation."""
        pack = create_universal_pack()
        payload = {
            "schema_version": "1.0",
            "verdict": "CLEAR_AND_CLOSE",
            "rationale_fact_refs": ["a" * 64],
            "auto_archive_permitted": True
        }
        warnings = validate_payload(pack, CellType.VERDICT, payload)
        assert len(warnings) == 0

    def test_valid_report_run_payload(self):
        """Test valid REPORT_RUN payload passes validation."""
        pack = create_universal_pack()
        payload = {
            "schema_version": "1.0",
            "case_id": "CASE-001",
            "pack_id": "aml_pack",
            "pack_version": "1.0.0",
            "anchor_head_cell_id": "a" * 64,
            "included_cell_ids": ["b" * 64, "c" * 64],
            "template_id": "full_report",
            "template_version": "1.0.0",
            "rendered_artifact_hash": "d" * 64,
            "rendered_at": "2026-01-28T12:00:00Z"
        }
        warnings = validate_payload(pack, CellType.REPORT_RUN, payload)
        assert len(warnings) == 0

    def test_invalid_timestamp_format(self):
        """Test invalid timestamp format raises error."""
        pack = create_universal_pack()
        payload = {
            "schema_version": "1.0",
            "case_id": "CASE-001",
            "pack_id": "aml_pack",
            "pack_version": "1.0.0",
            "anchor_head_cell_id": "a" * 64,
            "included_cell_ids": [],
            "template_id": "full_report",
            "template_version": "1.0.0",
            "rendered_artifact_hash": "d" * 64,
            "rendered_at": "Jan 28, 2026"  # Invalid format
        }
        with pytest.raises(SchemaValidationError, match="ISO 8601"):
            validate_payload(pack, CellType.REPORT_RUN, payload)

    def test_valid_judgment_payload(self):
        """Test valid JUDGMENT payload passes validation."""
        pack = create_universal_pack()
        payload = {
            "schema_version": "1.0",
            "action": "APPROVE",
            "tier": 1,
            "reviewer": "analyst_001",
            "target_cell_id": "a" * 64
        }
        warnings = validate_payload(pack, CellType.JUDGMENT, payload)
        assert len(warnings) == 0

    def test_invalid_judgment_action(self):
        """Test invalid JUDGMENT action raises error."""
        pack = create_universal_pack()
        payload = {
            "schema_version": "1.0",
            "action": "INVALID_ACTION",
            "tier": 1,
            "reviewer": "analyst_001",
            "target_cell_id": "a" * 64
        }
        with pytest.raises(SchemaValidationError, match="must be one of"):
            validate_payload(pack, CellType.JUDGMENT, payload)


# =============================================================================
# JUSTIFICATION VALIDATION TESTS
# =============================================================================

class TestJustificationValidation:
    """Tests for JUSTIFICATION (shadow node) payload validation."""

    def test_valid_justification_payload(self):
        """Test valid JUSTIFICATION payload passes validation."""
        pack = create_universal_pack()
        payload = {
            "schema_version": "1.0",
            "target_cell_id": "a" * 64,
            "question_set_id": "universal.v1",
            "answers": {
                "basis_fact_ids": ["b" * 64, "c" * 64],
                "evidence_sufficient": True,
                "missing_evidence": [],
                "counterfactuals": ["If X were false, require Y evidence"],
                "policy_refs": ["d" * 64],
                "needs_human_review": False
            }
        }
        warnings = validate_payload(pack, CellType.JUSTIFICATION, payload)
        assert len(warnings) == 0

    def test_justification_missing_answer_field(self):
        """Test JUSTIFICATION with missing answer field raises error."""
        pack = create_universal_pack()
        payload = {
            "schema_version": "1.0",
            "target_cell_id": "a" * 64,
            "question_set_id": "universal.v1",
            "answers": {
                "basis_fact_ids": [],
                # Missing other required fields
            }
        }
        with pytest.raises(SchemaValidationError, match="Missing required property"):
            validate_payload(pack, CellType.JUSTIFICATION, payload)

    def test_justification_with_review_reason(self):
        """Test JUSTIFICATION with optional review_reason."""
        pack = create_universal_pack()
        payload = {
            "schema_version": "1.0",
            "target_cell_id": "a" * 64,
            "question_set_id": "universal.v1",
            "answers": {
                "basis_fact_ids": [],
                "evidence_sufficient": False,
                "missing_evidence": ["Bank statement"],
                "counterfactuals": [],
                "policy_refs": [],
                "needs_human_review": True,
                "review_reason": "Missing documentation requires analyst review"
            }
        }
        warnings = validate_payload(pack, CellType.JUSTIFICATION, payload)
        assert len(warnings) == 0


# =============================================================================
# PREDICATE VALIDATION TESTS
# =============================================================================

class TestPredicateValidation:
    """Tests for predicate validation."""

    def test_valid_predicate(self):
        """Test valid predicate passes validation."""
        pack = create_universal_pack()
        # Should not raise
        validate_predicate(pack, "signal.fired", CellType.SIGNAL)

    def test_unknown_predicate(self):
        """Test unknown predicate raises error."""
        pack = create_universal_pack()
        with pytest.raises(PredicateError, match="not defined"):
            validate_predicate(pack, "unknown.predicate", CellType.SIGNAL)

    def test_predicate_wrong_cell_type(self):
        """Test predicate with wrong cell type raises error."""
        pack = create_universal_pack()
        with pytest.raises(PredicateError, match="not allowed for"):
            validate_predicate(pack, "signal.fired", CellType.VERDICT)


# =============================================================================
# BUILT-IN SCHEMA TESTS
# =============================================================================

class TestBuiltInSchemas:
    """Tests for built-in universal schemas."""

    def test_signal_schema_has_required_fields(self):
        """Test SIGNAL schema has expected fields."""
        schema = create_signal_schema()
        assert "code" in schema.fields
        assert "severity" in schema.fields
        assert "trigger_facts" in schema.fields
        assert schema.fields["severity"].type == SchemaType.ENUM

    def test_mitigation_schema_has_required_fields(self):
        """Test MITIGATION schema has expected fields."""
        schema = create_mitigation_schema()
        assert "code" in schema.fields
        assert "weight" in schema.fields
        assert "anchors" in schema.fields
        assert "applies_to_signals" in schema.fields
        assert schema.fields["weight"].type == SchemaType.DECIMAL

    def test_score_schema_has_required_fields(self):
        """Test SCORE schema has expected fields."""
        schema = create_score_schema()
        assert "inherent_score" in schema.fields
        assert "mitigation_sum" in schema.fields
        assert "residual_score" in schema.fields
        assert "threshold_gate" in schema.fields

    def test_verdict_schema_has_required_fields(self):
        """Test VERDICT schema has expected fields."""
        schema = create_verdict_schema()
        assert "verdict" in schema.fields
        assert "rationale_fact_refs" in schema.fields
        assert "auto_archive_permitted" in schema.fields

    def test_justification_schema_has_shadow_questions(self):
        """Test JUSTIFICATION schema has the 5 universal questions."""
        schema = create_justification_schema()
        assert "answers" in schema.fields
        answers = schema.fields["answers"]
        assert answers.properties is not None
        # Check all 5 universal questions are represented
        assert "basis_fact_ids" in answers.properties
        assert "evidence_sufficient" in answers.properties
        assert "missing_evidence" in answers.properties
        assert "counterfactuals" in answers.properties
        assert "policy_refs" in answers.properties
        assert "needs_human_review" in answers.properties

    def test_report_run_schema_has_required_fields(self):
        """Test REPORT_RUN schema has expected fields."""
        schema = create_report_run_schema()
        assert "case_id" in schema.fields
        assert "pack_id" in schema.fields
        assert "anchor_head_cell_id" in schema.fields
        assert "included_cell_ids" in schema.fields
        assert "rendered_artifact_hash" in schema.fields
        assert "rendered_at" in schema.fields

    def test_judgment_schema_has_required_fields(self):
        """Test JUDGMENT schema has expected fields."""
        schema = create_judgment_schema()
        assert "action" in schema.fields
        assert "tier" in schema.fields
        assert "reviewer" in schema.fields
        assert "target_cell_id" in schema.fields
        assert schema.fields["action"].type == SchemaType.ENUM
        assert "APPROVE" in schema.fields["action"].enum_values


class TestUniversalPack:
    """Tests for universal pack creation."""

    def test_universal_pack_has_all_schemas(self):
        """Test universal pack has all required schemas."""
        pack = create_universal_pack()
        expected_types = [
            CellType.SIGNAL,
            CellType.MITIGATION,
            CellType.SCORE,
            CellType.VERDICT,
            CellType.JUSTIFICATION,
            CellType.REPORT_RUN,
            CellType.JUDGMENT,
        ]
        for cell_type in expected_types:
            assert pack.has_schema(cell_type), f"Missing schema for {cell_type}"

    def test_universal_pack_has_all_predicates(self):
        """Test universal pack has all required predicates."""
        pack = create_universal_pack()
        expected_predicates = [
            "signal.fired",
            "mitigation.applied",
            "score.computed",
            "verdict.rendered",
            "justification.recorded",
            "report.generated",
            "judgment.recorded",
        ]
        for pred in expected_predicates:
            assert pack.has_predicate(pred), f"Missing predicate: {pred}"

    def test_universal_pack_version_in_hash(self):
        """Test pack version affects pack hash."""
        pack1 = create_universal_pack(version="1.0.0")
        pack2 = create_universal_pack(version="1.0.1")
        assert pack1.pack_hash != pack2.pack_hash

    def test_universal_pack_id_in_hash(self):
        """Test pack id affects pack hash."""
        pack1 = create_universal_pack(pack_id="pack_a")
        pack2 = create_universal_pack(pack_id="pack_b")
        assert pack1.pack_hash != pack2.pack_hash
