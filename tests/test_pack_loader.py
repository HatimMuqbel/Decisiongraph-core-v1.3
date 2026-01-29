"""
Tests for pack_loader.py

Validates:
- Malformed YAML fails
- Missing keys fail
- Float present fails
- Unknown signal reference fails
- Determinism: same YAML → same pack_hash and same runtime
"""

import pytest
import tempfile
import yaml
from pathlib import Path

import sys
_complete_path = Path(__file__).parent.parent / "decisiongraph-complete" / "src"
if _complete_path.exists():
    sys.path.insert(0, str(_complete_path))

from decisiongraph.pack_loader import (
    load_pack_yaml,
    load_pack_dict,
    validate_pack,
    compile_pack,
    compute_pack_hash,
    PackLoaderError,
    PackValidationError,
    PackCompilationError,
    PackRuntime,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def minimal_valid_pack():
    """Minimal valid pack for testing."""
    return {
        "pack_id": "test_pack",
        "name": "Test Pack",
        "version": "1.0.0",
        "domain": "test",
        "jurisdiction": "TEST",
        "signals": [
            {
                "code": "TEST_SIGNAL",
                "name": "Test Signal",
                "severity": "MEDIUM",
                "policy_ref": "TEST s. 1",
            }
        ],
        "mitigations": [
            {
                "code": "MF_TEST",
                "name": "Test Mitigation",
                "weight": "-0.25",
                "applies_to": ["TEST_SIGNAL"],
            }
        ],
        "scoring": {
            "rule_id": "test_score",
            "name": "Test Scoring",
            "signal_weights": {
                "TEST_SIGNAL": "0.50",
            },
            "threshold_gates": [
                {"code": "LOW", "max_score": "0.50"},
                {"code": "HIGH", "max_score": "999.00"},
            ],
        },
        "verdicts": {
            "rule_id": "test_verdict",
            "name": "Test Verdict",
            "gate_verdicts": {
                "LOW": {"verdict": "CLOSE", "auto_archive_permitted": True},
                "HIGH": {"verdict": "REVIEW", "auto_archive_permitted": False},
            },
        },
    }


@pytest.fixture
def pack_yaml_file(minimal_valid_pack):
    """Create a temporary YAML file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(minimal_valid_pack, f)
        return f.name


# ============================================================================
# BASIC LOADING TESTS
# ============================================================================

def test_load_valid_pack(pack_yaml_file):
    """Test loading a valid pack file."""
    runtime = load_pack_yaml(pack_yaml_file)

    assert runtime.pack_id == "test_pack"
    assert runtime.pack_version == "1.0.0"
    assert runtime.domain == "test"
    assert len(runtime.signals_by_code) == 1
    assert len(runtime.mitigations_by_code) == 1
    assert runtime.pack_hash is not None
    assert len(runtime.pack_hash) == 64


def test_load_from_dict(minimal_valid_pack):
    """Test loading from dictionary."""
    runtime = load_pack_dict(minimal_valid_pack)

    assert runtime.pack_id == "test_pack"
    assert "TEST_SIGNAL" in runtime.signals_by_code
    assert "MF_TEST" in runtime.mitigations_by_code


def test_file_not_found():
    """Test error on missing file."""
    with pytest.raises(PackLoaderError) as exc_info:
        load_pack_yaml("/nonexistent/path/pack.yaml")

    assert "not found" in str(exc_info.value)


# ============================================================================
# VALIDATION TESTS - MISSING FIELDS
# ============================================================================

def test_missing_pack_id(minimal_valid_pack):
    """Test validation fails on missing pack_id."""
    del minimal_valid_pack["pack_id"]

    with pytest.raises(PackValidationError) as exc_info:
        validate_pack(minimal_valid_pack)

    assert "pack_id" in str(exc_info.value)


def test_missing_signals(minimal_valid_pack):
    """Test validation fails on missing signals."""
    del minimal_valid_pack["signals"]

    with pytest.raises(PackValidationError) as exc_info:
        validate_pack(minimal_valid_pack)

    assert "signals" in str(exc_info.value)


def test_missing_signal_code(minimal_valid_pack):
    """Test validation fails on signal missing code."""
    del minimal_valid_pack["signals"][0]["code"]

    with pytest.raises(PackValidationError) as exc_info:
        validate_pack(minimal_valid_pack)

    assert "code" in str(exc_info.value)


def test_missing_signal_policy_ref(minimal_valid_pack):
    """Test validation fails on signal missing policy_ref."""
    del minimal_valid_pack["signals"][0]["policy_ref"]

    with pytest.raises(PackValidationError) as exc_info:
        validate_pack(minimal_valid_pack)

    assert "policy_ref" in str(exc_info.value)


def test_missing_mitigation_weight(minimal_valid_pack):
    """Test validation fails on mitigation missing weight."""
    del minimal_valid_pack["mitigations"][0]["weight"]

    with pytest.raises(PackValidationError) as exc_info:
        validate_pack(minimal_valid_pack)

    assert "weight" in str(exc_info.value)


# ============================================================================
# VALIDATION TESTS - FLOAT REJECTION
# ============================================================================

def test_float_in_weight_fails(minimal_valid_pack):
    """Test that float values are rejected."""
    minimal_valid_pack["mitigations"][0]["weight"] = -0.25  # Float, not string

    with pytest.raises(PackValidationError) as exc_info:
        validate_pack(minimal_valid_pack)

    assert "float" in str(exc_info.value).lower()


def test_float_in_signal_weight_fails(minimal_valid_pack):
    """Test that float in signal weights is rejected."""
    minimal_valid_pack["scoring"]["signal_weights"]["TEST_SIGNAL"] = 0.50  # Float

    with pytest.raises(PackValidationError) as exc_info:
        validate_pack(minimal_valid_pack)

    assert "float" in str(exc_info.value).lower()


def test_float_in_threshold_fails(minimal_valid_pack):
    """Test that float in threshold is rejected."""
    minimal_valid_pack["scoring"]["threshold_gates"][0]["max_score"] = 0.50  # Float

    with pytest.raises(PackValidationError) as exc_info:
        validate_pack(minimal_valid_pack)

    assert "float" in str(exc_info.value).lower()


def test_integer_in_weight_fails(minimal_valid_pack):
    """Test that integer values are rejected (must be string)."""
    minimal_valid_pack["mitigations"][0]["weight"] = -1  # Integer, not string

    with pytest.raises(PackValidationError) as exc_info:
        validate_pack(minimal_valid_pack)

    assert "integer" in str(exc_info.value).lower() or "string" in str(exc_info.value).lower()


# ============================================================================
# VALIDATION TESTS - REFERENCE INTEGRITY
# ============================================================================

def test_unknown_signal_reference_fails(minimal_valid_pack):
    """Test that mitigation referencing unknown signal fails."""
    minimal_valid_pack["mitigations"][0]["applies_to"] = ["NONEXISTENT_SIGNAL"]

    with pytest.raises(PackValidationError) as exc_info:
        validate_pack(minimal_valid_pack)

    assert "unknown signal" in str(exc_info.value).lower()


def test_unknown_signal_in_weights_fails(minimal_valid_pack):
    """Test that scoring referencing unknown signal fails."""
    minimal_valid_pack["scoring"]["signal_weights"]["NONEXISTENT"] = "0.50"

    with pytest.raises(PackValidationError) as exc_info:
        validate_pack(minimal_valid_pack)

    assert "unknown signal" in str(exc_info.value).lower()


def test_unknown_gate_in_verdicts_fails(minimal_valid_pack):
    """Test that verdict referencing unknown gate fails."""
    minimal_valid_pack["verdicts"]["gate_verdicts"]["NONEXISTENT_GATE"] = {
        "verdict": "TEST",
        "auto_archive_permitted": False,
    }

    with pytest.raises(PackValidationError) as exc_info:
        validate_pack(minimal_valid_pack)

    assert "unknown gate" in str(exc_info.value).lower()


# ============================================================================
# VALIDATION TESTS - FORMAT
# ============================================================================

def test_invalid_version_format(minimal_valid_pack):
    """Test that invalid version format fails."""
    minimal_valid_pack["version"] = "1.0"  # Missing patch

    with pytest.raises(PackValidationError) as exc_info:
        validate_pack(minimal_valid_pack)

    assert "version" in str(exc_info.value).lower()


def test_invalid_signal_code_format(minimal_valid_pack):
    """Test that invalid signal code format fails."""
    minimal_valid_pack["signals"][0]["code"] = "invalid-code"  # Lowercase and hyphen

    with pytest.raises(PackValidationError) as exc_info:
        validate_pack(minimal_valid_pack)

    assert "code" in str(exc_info.value).lower()


def test_invalid_severity(minimal_valid_pack):
    """Test that invalid severity fails."""
    minimal_valid_pack["signals"][0]["severity"] = "INVALID"

    with pytest.raises(PackValidationError) as exc_info:
        validate_pack(minimal_valid_pack)

    assert "severity" in str(exc_info.value).lower()


def test_positive_mitigation_weight_fails(minimal_valid_pack):
    """Test that positive mitigation weight fails."""
    minimal_valid_pack["mitigations"][0]["weight"] = "0.25"  # Positive

    with pytest.raises(PackValidationError) as exc_info:
        validate_pack(minimal_valid_pack)

    assert "negative" in str(exc_info.value).lower()


def test_duplicate_signal_code_fails(minimal_valid_pack):
    """Test that duplicate signal codes fail."""
    minimal_valid_pack["signals"].append({
        "code": "TEST_SIGNAL",  # Duplicate
        "name": "Another Test",
        "severity": "LOW",
        "policy_ref": "TEST s. 2",
    })

    with pytest.raises(PackValidationError) as exc_info:
        validate_pack(minimal_valid_pack)

    assert "duplicate" in str(exc_info.value).lower()


def test_unordered_thresholds_fail(minimal_valid_pack):
    """Test that unordered threshold gates fail."""
    minimal_valid_pack["scoring"]["threshold_gates"] = [
        {"code": "HIGH", "max_score": "999.00"},  # Wrong order
        {"code": "LOW", "max_score": "0.50"},
    ]

    with pytest.raises(PackValidationError) as exc_info:
        validate_pack(minimal_valid_pack)

    assert "greater" in str(exc_info.value).lower()


# ============================================================================
# DETERMINISM TESTS
# ============================================================================

def test_same_yaml_same_hash(minimal_valid_pack):
    """Test that same YAML produces same hash."""
    hash1 = compute_pack_hash(minimal_valid_pack)
    hash2 = compute_pack_hash(minimal_valid_pack)

    assert hash1 == hash2
    assert len(hash1) == 64


def test_different_yaml_different_hash(minimal_valid_pack):
    """Test that different YAML produces different hash."""
    hash1 = compute_pack_hash(minimal_valid_pack)

    # Modify pack
    minimal_valid_pack["signals"][0]["severity"] = "HIGH"
    hash2 = compute_pack_hash(minimal_valid_pack)

    assert hash1 != hash2


def test_same_yaml_same_runtime(minimal_valid_pack):
    """Test that same YAML produces identical runtime."""
    runtime1 = load_pack_dict(minimal_valid_pack)
    runtime2 = load_pack_dict(minimal_valid_pack)

    assert runtime1.pack_hash == runtime2.pack_hash
    assert runtime1.pack_id == runtime2.pack_id
    assert len(runtime1.signals_by_code) == len(runtime2.signals_by_code)
    assert len(runtime1.mitigations_by_code) == len(runtime2.mitigations_by_code)


def test_hash_ignores_whitespace_in_yaml(minimal_valid_pack, tmp_path):
    """Test that hash is deterministic regardless of YAML formatting."""
    # Write with different formatting
    file1 = tmp_path / "pack1.yaml"
    file2 = tmp_path / "pack2.yaml"

    with open(file1, 'w') as f:
        yaml.dump(minimal_valid_pack, f, default_flow_style=False)

    with open(file2, 'w') as f:
        yaml.dump(minimal_valid_pack, f, default_flow_style=True)

    runtime1 = load_pack_yaml(str(file1))
    runtime2 = load_pack_yaml(str(file2))

    assert runtime1.pack_hash == runtime2.pack_hash


# ============================================================================
# COMPILATION TESTS
# ============================================================================

def test_compile_creates_rules_engine(minimal_valid_pack):
    """Test that compiled runtime can create rules engine."""
    runtime = load_pack_dict(minimal_valid_pack)
    engine = runtime.create_rules_engine()

    assert engine is not None
    assert len(engine.signal_rules) >= 0  # May be 0 if signals have no conditions
    assert engine.scoring_rule is not None
    assert engine.verdict_rule is not None


def test_compile_extracts_policy_refs(minimal_valid_pack):
    """Test that policy references are extracted."""
    runtime = load_pack_dict(minimal_valid_pack)

    assert len(runtime.policy_refs) >= 1
    assert any("test" in r.ref_id for r in runtime.policy_refs)


def test_compile_builds_policy_map(minimal_valid_pack):
    """Test that policy map by signal is built."""
    runtime = load_pack_dict(minimal_valid_pack)

    assert "TEST_SIGNAL" in runtime.policy_map_by_signal
    assert len(runtime.policy_map_by_signal["TEST_SIGNAL"]) >= 1


def test_scoring_rule_compiled(minimal_valid_pack):
    """Test that scoring rule is properly compiled."""
    runtime = load_pack_dict(minimal_valid_pack)

    assert runtime.scoring_rule is not None
    assert runtime.scoring_rule.rule_id == "test_score"
    assert "TEST_SIGNAL" in runtime.scoring_rule.signal_weights
    assert len(runtime.scoring_rule.threshold_gates) == 2


def test_verdict_rule_compiled(minimal_valid_pack):
    """Test that verdict rule is properly compiled."""
    runtime = load_pack_dict(minimal_valid_pack)

    assert runtime.verdict_rule is not None
    assert runtime.verdict_rule.rule_id == "test_verdict"
    assert "LOW" in runtime.verdict_rule.gate_verdicts
    assert "HIGH" in runtime.verdict_rule.gate_verdicts


# ============================================================================
# MALFORMED YAML TESTS
# ============================================================================

def test_invalid_yaml_syntax(tmp_path):
    """Test that invalid YAML syntax is rejected."""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("pack_id: test\n  invalid: indentation")

    with pytest.raises(PackLoaderError) as exc_info:
        load_pack_yaml(str(bad_yaml))

    assert "YAML" in str(exc_info.value)


def test_yaml_not_dict(tmp_path):
    """Test that non-dict YAML is rejected."""
    list_yaml = tmp_path / "list.yaml"
    list_yaml.write_text("- item1\n- item2")

    with pytest.raises(PackLoaderError) as exc_info:
        load_pack_yaml(str(list_yaml))

    assert "dictionary" in str(exc_info.value)


# ============================================================================
# REAL PACK TEST
# ============================================================================

def test_load_fincrime_canada_pack():
    """Test loading the real Canadian Financial Crime pack."""
    pack_path = Path(__file__).parent.parent / "packs" / "fincrime_canada.yaml"

    if not pack_path.exists():
        pytest.skip("fincrime_canada.yaml not found")

    runtime = load_pack_yaml(str(pack_path))

    # Verify it loaded correctly
    assert runtime.pack_id == "fincrime_canada_v1"
    assert runtime.jurisdiction == "CA"
    assert len(runtime.signals_by_code) >= 20  # We defined ~22 signals
    assert len(runtime.mitigations_by_code) >= 15  # We defined ~24 mitigations
    assert runtime.pack_hash is not None

    # Verify policy refs extracted
    assert len(runtime.policy_refs) > 0

    # Verify can create engine
    engine = runtime.create_rules_engine()
    assert engine is not None


# ============================================================================
# POLICY CELL CREATION TESTS
# ============================================================================

def test_create_policy_cells(minimal_valid_pack):
    """Test that policy cells can be created."""
    runtime = load_pack_dict(minimal_valid_pack)

    cells = runtime.create_policy_cells(
        graph_id="graph:test-uuid-1234",
        prev_hash="0" * 64,
    )

    assert len(cells) >= 1
    for cell in cells:
        assert cell.header.cell_type.value == "policy_ref"
        assert cell.fact.namespace == "fincrime.policy"


# ============================================================================
# RUNTIME SERIALIZATION TESTS
# ============================================================================

def test_runtime_to_dict(minimal_valid_pack):
    """Test runtime serialization to dict."""
    runtime = load_pack_dict(minimal_valid_pack)
    d = runtime.to_dict()

    assert d["pack_id"] == "test_pack"
    assert d["pack_hash"] == runtime.pack_hash
    assert d["signal_count"] == 1
    assert d["mitigation_count"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
