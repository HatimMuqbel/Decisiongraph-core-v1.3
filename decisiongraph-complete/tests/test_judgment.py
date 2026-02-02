"""
Tests for DecisionGraph Judgment Module (Precedent System)

Tests cover:
- JudgmentPayload creation and validation
- compute_case_id_hash() determinism
- JUDGMENT cell creation and parsing
- Validation error cases
"""

import pytest
from decisiongraph.judgment import (
    AnchorFact,
    JudgmentPayload,
    JudgmentPayloadError,
    JudgmentValidationError,
    JudgmentCreationError,
    compute_case_id_hash,
    create_judgment_cell,
    parse_judgment_payload,
    is_judgment_cell,
)
from decisiongraph.cell import CellType, NULL_HASH, HASH_SCHEME_CANONICAL
from decisiongraph.chain import Chain


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def valid_anchor_facts():
    """Create valid anchor facts for testing."""
    return [
        AnchorFact(
            field_id="driver.rideshare_app_active",
            value=True,
            label="Rideshare App Active",
        ),
        AnchorFact(
            field_id="vehicle.use_at_loss",
            value="commercial",
            label="Vehicle Use at Loss",
        ),
    ]


@pytest.fixture
def valid_judgment_payload(valid_anchor_facts):
    """Create a valid JudgmentPayload for testing."""
    return JudgmentPayload.create(
        case_id_hash="a" * 64,
        jurisdiction_code="CA-ON",
        fingerprint_hash="b" * 64,
        fingerprint_schema_id="claimpilot:oap1:auto:v1",
        exclusion_codes=["4.2.1", "4.3.3"],
        reason_codes=["RC-COMMERCIAL-USE"],
        reason_code_registry_id="claimpilot:auto:v1",
        outcome_code="deny",
        certainty="high",
        anchor_facts=valid_anchor_facts,
        policy_pack_hash="c" * 64,
        policy_pack_id="CA-ON-OAP1-2024",
        policy_version="2024.1",
        decision_level="adjuster",
        decided_at="2026-01-15T12:00:00Z",
        decided_by_role="adjuster",
    )


@pytest.fixture
def test_chain():
    """Create a test chain with genesis using canonical hash scheme."""
    chain = Chain()
    # Use canonical hash scheme to support JUDGMENT cells with structured payloads
    chain.initialize(
        graph_name="TestGraph",
        root_namespace="test",
        hash_scheme=HASH_SCHEME_CANONICAL,
    )
    return chain


# =============================================================================
# AnchorFact Tests
# =============================================================================

class TestAnchorFact:
    """Tests for AnchorFact dataclass."""

    def test_create_valid_anchor_fact(self):
        """AnchorFact creation with valid data succeeds."""
        af = AnchorFact(
            field_id="driver.rideshare_app_active",
            value=True,
            label="Rideshare App Active",
        )
        assert af.field_id == "driver.rideshare_app_active"
        assert af.value is True
        assert af.label == "Rideshare App Active"

    def test_anchor_fact_with_string_value(self):
        """AnchorFact accepts string values."""
        af = AnchorFact(
            field_id="vehicle.use",
            value="commercial",
            label="Vehicle Use",
        )
        assert af.value == "commercial"

    def test_anchor_fact_with_none_value(self):
        """AnchorFact accepts None values."""
        af = AnchorFact(
            field_id="driver.bac_level",
            value=None,
            label="BAC Level",
        )
        assert af.value is None

    def test_anchor_fact_empty_field_id_fails(self):
        """AnchorFact with empty field_id raises error."""
        with pytest.raises(JudgmentValidationError, match="field_id cannot be empty"):
            AnchorFact(field_id="", value=True, label="Test")

    def test_anchor_fact_empty_label_fails(self):
        """AnchorFact with empty label raises error."""
        with pytest.raises(JudgmentValidationError, match="label cannot be empty"):
            AnchorFact(field_id="test", value=True, label="")

    def test_anchor_fact_to_dict(self):
        """AnchorFact.to_dict() returns correct dict."""
        af = AnchorFact(field_id="test", value="value", label="Test Label")
        d = af.to_dict()
        assert d == {
            "field_id": "test",
            "value": "value",
            "label": "Test Label",
        }

    def test_anchor_fact_from_dict(self):
        """AnchorFact.from_dict() creates correct object."""
        data = {"field_id": "test", "value": True, "label": "Label"}
        af = AnchorFact.from_dict(data)
        assert af.field_id == "test"
        assert af.value is True
        assert af.label == "Label"


# =============================================================================
# compute_case_id_hash Tests
# =============================================================================

class TestComputeCaseIdHash:
    """Tests for compute_case_id_hash function."""

    def test_hash_is_deterministic(self):
        """Same inputs produce same hash."""
        hash1 = compute_case_id_hash("CLAIM-123", "salt123")
        hash2 = compute_case_id_hash("CLAIM-123", "salt123")
        assert hash1 == hash2

    def test_hash_is_64_chars(self):
        """Hash is 64-character hex string."""
        h = compute_case_id_hash("CLAIM-123", "salt123")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_different_case_ids_different_hashes(self):
        """Different case IDs produce different hashes."""
        hash1 = compute_case_id_hash("CLAIM-123", "salt")
        hash2 = compute_case_id_hash("CLAIM-456", "salt")
        assert hash1 != hash2

    def test_different_salts_different_hashes(self):
        """Different salts produce different hashes."""
        hash1 = compute_case_id_hash("CLAIM-123", "salt1")
        hash2 = compute_case_id_hash("CLAIM-123", "salt2")
        assert hash1 != hash2

    def test_empty_case_id_fails(self):
        """Empty case_id raises error."""
        with pytest.raises(JudgmentValidationError, match="case_id cannot be empty"):
            compute_case_id_hash("", "salt")

    def test_empty_salt_fails(self):
        """Empty salt raises error."""
        with pytest.raises(JudgmentValidationError, match="salt cannot be empty"):
            compute_case_id_hash("case", "")


# =============================================================================
# JudgmentPayload Tests
# =============================================================================

class TestJudgmentPayload:
    """Tests for JudgmentPayload dataclass."""

    def test_create_valid_payload(self, valid_anchor_facts):
        """JudgmentPayload.create() with valid data succeeds."""
        payload = JudgmentPayload.create(
            case_id_hash="a" * 64,
            jurisdiction_code="CA-ON",
            fingerprint_hash="b" * 64,
            fingerprint_schema_id="claimpilot:oap1:auto:v1",
            exclusion_codes=["4.2.1"],
            reason_codes=["RC-4.2.1"],
            reason_code_registry_id="claimpilot:auto:v1",
            outcome_code="deny",
            certainty="high",
            anchor_facts=valid_anchor_facts,
            policy_pack_hash="c" * 64,
            policy_pack_id="CA-ON-OAP1-2024",
            policy_version="2024.1",
            decision_level="adjuster",
            decided_at="2026-01-15T12:00:00Z",
            decided_by_role="adjuster",
        )

        assert payload.jurisdiction_code == "CA-ON"
        assert payload.outcome_code == "deny"
        assert payload.certainty == "high"
        assert len(payload.precedent_id) == 36  # UUID format

    def test_invalid_outcome_code_fails(self, valid_anchor_facts):
        """Invalid outcome_code raises error."""
        with pytest.raises(JudgmentValidationError, match="Invalid outcome_code"):
            JudgmentPayload.create(
                case_id_hash="a" * 64,
                jurisdiction_code="CA-ON",
                fingerprint_hash="b" * 64,
                fingerprint_schema_id="test:v1",
                exclusion_codes=[],
                reason_codes=[],
                reason_code_registry_id="test:v1",
                outcome_code="invalid",  # Invalid
                certainty="high",
                anchor_facts=valid_anchor_facts,
                policy_pack_hash="c" * 64,
                policy_pack_id="test",
                policy_version="1.0",
                decision_level="adjuster",
                decided_at="2026-01-15T12:00:00Z",
                decided_by_role="adjuster",
            )

    def test_invalid_certainty_fails(self, valid_anchor_facts):
        """Invalid certainty raises error."""
        with pytest.raises(JudgmentValidationError, match="Invalid certainty"):
            JudgmentPayload.create(
                case_id_hash="a" * 64,
                jurisdiction_code="CA-ON",
                fingerprint_hash="b" * 64,
                fingerprint_schema_id="test:v1",
                exclusion_codes=[],
                reason_codes=[],
                reason_code_registry_id="test:v1",
                outcome_code="pay",
                certainty="very_high",  # Invalid
                anchor_facts=valid_anchor_facts,
                policy_pack_hash="c" * 64,
                policy_pack_id="test",
                policy_version="1.0",
                decision_level="adjuster",
                decided_at="2026-01-15T12:00:00Z",
                decided_by_role="adjuster",
            )

    def test_invalid_decision_level_fails(self, valid_anchor_facts):
        """Invalid decision_level raises error."""
        with pytest.raises(JudgmentValidationError, match="Invalid decision_level"):
            JudgmentPayload.create(
                case_id_hash="a" * 64,
                jurisdiction_code="CA-ON",
                fingerprint_hash="b" * 64,
                fingerprint_schema_id="test:v1",
                exclusion_codes=[],
                reason_codes=[],
                reason_code_registry_id="test:v1",
                outcome_code="pay",
                certainty="high",
                anchor_facts=valid_anchor_facts,
                policy_pack_hash="c" * 64,
                policy_pack_id="test",
                policy_version="1.0",
                decision_level="ceo",  # Invalid
                decided_at="2026-01-15T12:00:00Z",
                decided_by_role="adjuster",
            )

    def test_invalid_hash_format_fails(self, valid_anchor_facts):
        """Invalid hash format raises error."""
        with pytest.raises(JudgmentValidationError, match="must be 64-character"):
            JudgmentPayload.create(
                case_id_hash="tooshort",  # Invalid
                jurisdiction_code="CA-ON",
                fingerprint_hash="b" * 64,
                fingerprint_schema_id="test:v1",
                exclusion_codes=[],
                reason_codes=[],
                reason_code_registry_id="test:v1",
                outcome_code="pay",
                certainty="high",
                anchor_facts=valid_anchor_facts,
                policy_pack_hash="c" * 64,
                policy_pack_id="test",
                policy_version="1.0",
                decision_level="adjuster",
                decided_at="2026-01-15T12:00:00Z",
                decided_by_role="adjuster",
            )

    def test_payload_to_dict(self, valid_judgment_payload):
        """JudgmentPayload.to_dict() returns correct dict."""
        d = valid_judgment_payload.to_dict()
        assert d["jurisdiction_code"] == "CA-ON"
        assert d["outcome_code"] == "deny"
        assert d["exclusion_codes"] == ["4.2.1", "4.3.3"]
        assert len(d["anchor_facts"]) == 2

    def test_payload_from_dict(self, valid_judgment_payload):
        """JudgmentPayload.from_dict() creates correct object."""
        d = valid_judgment_payload.to_dict()
        payload2 = JudgmentPayload.from_dict(d)
        assert payload2.precedent_id == valid_judgment_payload.precedent_id
        assert payload2.outcome_code == valid_judgment_payload.outcome_code


# =============================================================================
# JUDGMENT Cell Tests
# =============================================================================

class TestJudgmentCell:
    """Tests for JUDGMENT cell creation and parsing."""

    def test_create_judgment_cell(self, valid_judgment_payload, test_chain):
        """create_judgment_cell() creates valid JUDGMENT cell."""
        cell = create_judgment_cell(
            payload=valid_judgment_payload,
            namespace="test.precedents",
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
        )

        assert cell.header.cell_type == CellType.JUDGMENT
        assert cell.fact.namespace == "test.precedents"
        assert is_judgment_cell(cell)
        assert isinstance(cell.fact.object, dict)

    def test_parse_judgment_payload(self, valid_judgment_payload, test_chain):
        """parse_judgment_payload() extracts correct payload."""
        cell = create_judgment_cell(
            payload=valid_judgment_payload,
            namespace="test.precedents",
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
        )

        parsed = parse_judgment_payload(cell)
        assert parsed.precedent_id == valid_judgment_payload.precedent_id
        assert parsed.outcome_code == valid_judgment_payload.outcome_code
        assert parsed.exclusion_codes == valid_judgment_payload.exclusion_codes

    def test_judgment_cell_round_trip(self, valid_judgment_payload, test_chain):
        """JUDGMENT cell survives create -> serialize -> deserialize -> parse."""
        from decisiongraph.cell import DecisionCell

        cell = create_judgment_cell(
            payload=valid_judgment_payload,
            namespace="test.precedents",
            graph_id=test_chain.graph_id,
            prev_cell_hash=test_chain.head.cell_id,
        )

        # Serialize and deserialize
        cell_dict = cell.to_dict()
        cell2 = DecisionCell.from_dict(cell_dict)

        # Parse should still work
        parsed = parse_judgment_payload(cell2)
        assert parsed.precedent_id == valid_judgment_payload.precedent_id

    def test_invalid_namespace_fails(self, valid_judgment_payload, test_chain):
        """Invalid namespace raises error."""
        with pytest.raises(JudgmentCreationError, match="Invalid namespace"):
            create_judgment_cell(
                payload=valid_judgment_payload,
                namespace="Invalid Namespace",
                graph_id=test_chain.graph_id,
                prev_cell_hash=test_chain.head.cell_id,
            )

    def test_is_judgment_cell_false_for_non_judgment(self, test_chain):
        """is_judgment_cell() returns False for non-JUDGMENT cells."""
        genesis = test_chain.genesis
        assert not is_judgment_cell(genesis)


# =============================================================================
# Appeal Fields Tests
# =============================================================================

class TestAppealFields:
    """Tests for appeal-related fields in JudgmentPayload."""

    def test_appealed_with_outcome(self, valid_anchor_facts):
        """Appealed case with outcome validates correctly."""
        payload = JudgmentPayload.create(
            case_id_hash="a" * 64,
            jurisdiction_code="CA-ON",
            fingerprint_hash="b" * 64,
            fingerprint_schema_id="test:v1",
            exclusion_codes=["4.2.1"],
            reason_codes=[],
            reason_code_registry_id="test:v1",
            outcome_code="deny",
            certainty="high",
            anchor_facts=valid_anchor_facts,
            policy_pack_hash="c" * 64,
            policy_pack_id="test",
            policy_version="1.0",
            decision_level="adjuster",
            decided_at="2026-01-15T12:00:00Z",
            decided_by_role="adjuster",
            appealed=True,
            appeal_outcome="upheld",
            appeal_decided_at="2026-02-15T12:00:00Z",
            appeal_level="tribunal",
        )

        assert payload.appealed is True
        assert payload.appeal_outcome == "upheld"

    def test_invalid_appeal_outcome_fails(self, valid_anchor_facts):
        """Invalid appeal_outcome raises error."""
        with pytest.raises(JudgmentValidationError, match="Invalid appeal_outcome"):
            JudgmentPayload.create(
                case_id_hash="a" * 64,
                jurisdiction_code="CA-ON",
                fingerprint_hash="b" * 64,
                fingerprint_schema_id="test:v1",
                exclusion_codes=[],
                reason_codes=[],
                reason_code_registry_id="test:v1",
                outcome_code="pay",
                certainty="high",
                anchor_facts=valid_anchor_facts,
                policy_pack_hash="c" * 64,
                policy_pack_id="test",
                policy_version="1.0",
                decision_level="adjuster",
                decided_at="2026-01-15T12:00:00Z",
                decided_by_role="adjuster",
                appealed=True,
                appeal_outcome="won",  # Invalid
            )

    def test_outcome_notable_values(self, valid_anchor_facts):
        """Valid outcome_notable values work."""
        for notable in ["boundary_case", "landmark", "overturned"]:
            payload = JudgmentPayload.create(
                case_id_hash="a" * 64,
                jurisdiction_code="CA-ON",
                fingerprint_hash="b" * 64,
                fingerprint_schema_id="test:v1",
                exclusion_codes=[],
                reason_codes=[],
                reason_code_registry_id="test:v1",
                outcome_code="pay",
                certainty="high",
                anchor_facts=valid_anchor_facts,
                policy_pack_hash="c" * 64,
                policy_pack_id="test",
                policy_version="1.0",
                decision_level="adjuster",
                decided_at="2026-01-15T12:00:00Z",
                decided_by_role="adjuster",
                outcome_notable=notable,
            )
            assert payload.outcome_notable == notable
