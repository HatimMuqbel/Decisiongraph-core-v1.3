"""
Tests for case_mapper.py

Validates:
- Adapter loading and validation
- JSONPath extraction
- Field mapping
- Value transforms
- CaseBundle output structure
"""

import pytest
import json
import tempfile
from pathlib import Path

import sys
_complete_path = Path(__file__).parent.parent / "decisiongraph-complete" / "src"
if _complete_path.exists():
    sys.path.insert(0, str(_complete_path))

from decisiongraph.case_mapper import (
    load_adapter,
    validate_adapter,
    CaseMapper,
    map_case,
    jsonpath_extract,
    AdapterError,
    AdapterValidationError,
    MappingError,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def minimal_adapter():
    """Minimal valid adapter for testing."""
    return {
        "adapter": {
            "name": "test_adapter",
            "vendor": "Test Vendor",
            "version": "1.0.0",
            "input_format": "json",
        },
        "roots": {
            "case": "$.case",
            "customers": "$.customers[*]",
        },
        "mappings": {
            "CaseMeta.case_id": "$.case.id",
            "CaseMeta.case_type": "!literal aml_alert",
            "CaseMeta.jurisdiction": "$.case.jurisdiction",
            "CaseMeta.primary_entity_id": "$.case.customer_id",
            "Individual.id": "$.customer_id",
            "Individual.given_name": "$.first_name",
            "Individual.family_name": "$.last_name",
        },
    }


@pytest.fixture
def minimal_input():
    """Minimal valid input for testing."""
    return {
        "case": {
            "id": "TEST-001",
            "jurisdiction": "US",
            "customer_id": "CUST-001",
        },
        "customers": [
            {
                "customer_id": "CUST-001",
                "first_name": "John",
                "last_name": "Doe",
            }
        ],
    }


@pytest.fixture
def adapter_yaml_file(minimal_adapter, tmp_path):
    """Create a temporary adapter YAML file."""
    import yaml
    file_path = tmp_path / "test_adapter.yaml"
    with open(file_path, 'w') as f:
        yaml.dump(minimal_adapter, f)
    return file_path


# ============================================================================
# JSONPATH TESTS
# ============================================================================

def test_jsonpath_simple_field():
    """Test simple field extraction."""
    data = {"name": "John"}
    assert jsonpath_extract(data, "$.name") == "John"


def test_jsonpath_nested_field():
    """Test nested field extraction."""
    data = {"person": {"name": "John"}}
    assert jsonpath_extract(data, "$.person.name") == "John"


def test_jsonpath_array_index():
    """Test array index extraction."""
    data = {"items": ["a", "b", "c"]}
    assert jsonpath_extract(data, "$.items[0]") == "a"
    assert jsonpath_extract(data, "$.items[2]") == "c"


def test_jsonpath_array_wildcard():
    """Test array wildcard extraction."""
    data = {"items": [{"id": 1}, {"id": 2}]}
    result = jsonpath_extract(data, "$.items[*].id")
    assert result == [1, 2]


def test_jsonpath_missing_field():
    """Test missing field returns None."""
    data = {"name": "John"}
    assert jsonpath_extract(data, "$.missing") is None


def test_jsonpath_invalid_path():
    """Test invalid path returns None."""
    data = {"name": "John"}
    assert jsonpath_extract(data, "invalid") is None


# ============================================================================
# ADAPTER LOADING TESTS
# ============================================================================

def test_load_valid_adapter(adapter_yaml_file):
    """Test loading a valid adapter."""
    adapter = load_adapter(adapter_yaml_file)

    assert adapter.metadata.name == "test_adapter"
    assert adapter.metadata.vendor == "Test Vendor"
    assert adapter.metadata.version == "1.0.0"
    assert "case" in adapter.roots
    assert "CaseMeta.case_id" in adapter.mappings


def test_load_adapter_file_not_found():
    """Test error on missing file."""
    with pytest.raises(AdapterError) as exc_info:
        load_adapter("/nonexistent/path/adapter.yaml")
    assert "not found" in str(exc_info.value)


def test_validate_adapter_missing_metadata(minimal_adapter, tmp_path):
    """Test validation fails on missing adapter metadata."""
    import yaml
    del minimal_adapter["adapter"]

    file_path = tmp_path / "bad_adapter.yaml"
    with open(file_path, 'w') as f:
        yaml.dump(minimal_adapter, f)

    is_valid, errors = validate_adapter(file_path)
    assert not is_valid
    assert "adapter" in str(errors)


def test_validate_adapter_missing_roots(minimal_adapter, tmp_path):
    """Test validation fails on missing roots."""
    import yaml
    del minimal_adapter["roots"]

    file_path = tmp_path / "bad_adapter.yaml"
    with open(file_path, 'w') as f:
        yaml.dump(minimal_adapter, f)

    is_valid, errors = validate_adapter(file_path)
    assert not is_valid
    assert "roots" in str(errors)


def test_validate_adapter_missing_case_root(minimal_adapter, tmp_path):
    """Test validation fails on missing case root."""
    import yaml
    minimal_adapter["roots"] = {"customers": "$.customers[*]"}

    file_path = tmp_path / "bad_adapter.yaml"
    with open(file_path, 'w') as f:
        yaml.dump(minimal_adapter, f)

    is_valid, errors = validate_adapter(file_path)
    assert not is_valid
    assert "case" in str(errors)


def test_validate_adapter_missing_required_mapping(minimal_adapter, tmp_path):
    """Test validation fails on missing required mapping."""
    import yaml
    del minimal_adapter["mappings"]["CaseMeta.case_id"]

    file_path = tmp_path / "bad_adapter.yaml"
    with open(file_path, 'w') as f:
        yaml.dump(minimal_adapter, f)

    is_valid, errors = validate_adapter(file_path)
    assert not is_valid
    assert "CaseMeta.case_id" in str(errors)


# ============================================================================
# MAPPING TESTS
# ============================================================================

def test_map_case_meta(adapter_yaml_file, minimal_input):
    """Test CaseMeta mapping."""
    adapter = load_adapter(adapter_yaml_file)
    mapper = CaseMapper(adapter)

    result = mapper.map(minimal_input)
    bundle = result.bundle

    assert bundle["meta"]["id"] == "TEST-001"
    assert bundle["meta"]["case_type"] == "aml_alert"
    assert bundle["meta"]["jurisdiction"] == "US"
    assert bundle["meta"]["primary_entity_id"] == "CUST-001"


def test_map_individuals(adapter_yaml_file, minimal_input):
    """Test Individual mapping."""
    adapter = load_adapter(adapter_yaml_file)
    mapper = CaseMapper(adapter)

    result = mapper.map(minimal_input)
    bundle = result.bundle

    assert len(bundle["individuals"]) == 1
    ind = bundle["individuals"][0]
    assert ind["id"] == "CUST-001"
    assert ind["given_name"] == "John"
    assert ind["family_name"] == "Doe"


def test_map_literal_value(adapter_yaml_file, minimal_input):
    """Test literal value mapping."""
    adapter = load_adapter(adapter_yaml_file)
    mapper = CaseMapper(adapter)

    result = mapper.map(minimal_input)
    bundle = result.bundle

    # case_type is mapped as "!literal aml_alert"
    assert bundle["meta"]["case_type"] == "aml_alert"


def test_map_with_transforms(tmp_path):
    """Test value transforms."""
    import yaml

    adapter_dict = {
        "adapter": {
            "name": "test",
            "vendor": "Test",
            "version": "1.0.0",
            "input_format": "json",
        },
        "roots": {
            "case": "$.case",
        },
        "mappings": {
            "CaseMeta.case_id": "$.case.id",
            "CaseMeta.case_type": "$.case.type",
            "CaseMeta.jurisdiction": "$.case.jurisdiction",
            "CaseMeta.primary_entity_id": "$.case.customer",
        },
        "transforms": {
            "case_type": {
                "SAR": "aml_alert",
                "KYC": "kyc_refresh",
            },
        },
    }

    file_path = tmp_path / "adapter.yaml"
    with open(file_path, 'w') as f:
        yaml.dump(adapter_dict, f)

    input_data = {
        "case": {
            "id": "TEST-001",
            "type": "SAR",
            "jurisdiction": "US",
            "customer": "CUST-001",
        },
    }

    adapter = load_adapter(file_path)
    mapper = CaseMapper(adapter)
    result = mapper.map(input_data)

    assert result.bundle["meta"]["case_type"] == "aml_alert"


def test_map_with_defaults(tmp_path):
    """Test default values."""
    import yaml

    adapter_dict = {
        "adapter": {
            "name": "test",
            "vendor": "Test",
            "version": "1.0.0",
            "input_format": "json",
        },
        "roots": {
            "case": "$.case",
        },
        "mappings": {
            "CaseMeta.case_id": "$.case.id",
            "CaseMeta.case_type": "!literal aml_alert",
            "CaseMeta.jurisdiction": "$.case.jurisdiction",
            "CaseMeta.primary_entity_id": "$.case.customer",
        },
        "defaults": {
            "CaseMeta.sensitivity": "confidential",
            "CaseMeta.access_tags": ["aml"],
        },
    }

    file_path = tmp_path / "adapter.yaml"
    with open(file_path, 'w') as f:
        yaml.dump(adapter_dict, f)

    input_data = {
        "case": {
            "id": "TEST-001",
            "jurisdiction": "US",
            "customer": "CUST-001",
        },
    }

    adapter = load_adapter(file_path)
    mapper = CaseMapper(adapter)
    result = mapper.map(input_data)

    assert result.bundle["meta"]["sensitivity"] == "confidential"
    assert result.bundle["meta"]["access_tags"] == ["aml"]


# ============================================================================
# REAL ADAPTER TESTS
# ============================================================================

def test_load_actimize_adapter():
    """Test loading the real Actimize adapter."""
    adapter_path = Path(__file__).parent.parent / "adapters" / "fincrime" / "actimize" / "mapping.yaml"

    if not adapter_path.exists():
        pytest.skip("Actimize adapter not found")

    adapter = load_adapter(adapter_path)

    assert adapter.metadata.name == "actimize_tm_v1"
    assert adapter.metadata.vendor == "NICE Actimize"
    assert len(adapter.mappings) > 0
    assert len(adapter.transforms) > 0


def test_map_actimize_example():
    """Test mapping the real Actimize example."""
    adapter_path = Path(__file__).parent.parent / "adapters" / "fincrime" / "actimize" / "mapping.yaml"
    input_path = Path(__file__).parent.parent / "adapters" / "fincrime" / "actimize" / "example_input.json"

    if not adapter_path.exists() or not input_path.exists():
        pytest.skip("Actimize adapter or example not found")

    with open(input_path) as f:
        input_data = json.load(f)

    adapter = load_adapter(adapter_path)
    mapper = CaseMapper(adapter)
    result = mapper.map(input_data)
    bundle = result.bundle

    # Verify structure
    assert bundle["meta"]["id"] == "ACT-2026-00789"
    assert bundle["meta"]["case_type"] == "aml_alert"
    assert len(bundle["individuals"]) == 1
    assert len(bundle["accounts"]) == 2
    assert len(bundle["events"]) == 7  # 4 txns + 2 alerts + 1 screening


def test_map_case_high_level_api():
    """Test the high-level map_case API."""
    adapter_path = Path(__file__).parent.parent / "adapters" / "fincrime" / "actimize" / "mapping.yaml"
    input_path = Path(__file__).parent.parent / "adapters" / "fincrime" / "actimize" / "example_input.json"

    if not adapter_path.exists() or not input_path.exists():
        pytest.skip("Actimize adapter or example not found")

    result = map_case(input_path, adapter_path)
    bundle = result.bundle

    assert bundle["meta"]["id"] == "ACT-2026-00789"
    assert "individuals" in bundle
    assert "accounts" in bundle
    assert "events" in bundle


# ============================================================================
# OUTPUT STRUCTURE TESTS
# ============================================================================

def test_bundle_has_required_sections(adapter_yaml_file, minimal_input):
    """Test bundle has all required sections."""
    adapter = load_adapter(adapter_yaml_file)
    mapper = CaseMapper(adapter)
    result = mapper.map(minimal_input)
    bundle = result.bundle

    required_sections = [
        "meta",
        "individuals",
        "organizations",
        "accounts",
        "relationships",
        "evidence",
        "events",
        "assertions",
    ]

    for section in required_sections:
        assert section in bundle


def test_bundle_meta_has_required_fields(adapter_yaml_file, minimal_input):
    """Test bundle meta has required fields."""
    adapter = load_adapter(adapter_yaml_file)
    mapper = CaseMapper(adapter)
    result = mapper.map(minimal_input)
    bundle = result.bundle

    meta = bundle["meta"]
    assert "id" in meta
    assert "case_type" in meta
    assert "jurisdiction" in meta
    assert "primary_entity_id" in meta


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
