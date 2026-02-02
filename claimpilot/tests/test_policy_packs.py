"""
ClaimPilot Policy Pack Stress Tests

Tests that verify:
1. All policy packs load without errors
2. Schema validation passes
3. Cross-reference integrity (coverage IDs exist)
4. Condition complexity handles all lines of business
5. Determinism (same inputs = same outputs)
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from claimpilot.models import (
    Policy,
    CoverageSection,
    Exclusion,
    LineOfBusiness,
    ClaimantType,
)
from claimpilot.canon import compute_policy_pack_hash


# Path to policy packs
PACKS_DIR = Path(__file__).parent.parent / "packs"


def get_all_pack_paths() -> list[Path]:
    """Get all YAML policy pack files (excluding examples directory)."""
    packs = []
    for root, dirs, files in os.walk(PACKS_DIR):
        # Skip examples directory which uses a different schema format
        if "examples" in root:
            continue
        for file in files:
            if file.endswith(".yaml") or file.endswith(".yml"):
                packs.append(Path(root) / file)
    return packs


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file."""
    with open(path, "r") as f:
        return yaml.safe_load(f)


class TestPolicyPackLoading:
    """Test that all policy packs can be loaded."""

    @pytest.mark.parametrize("pack_path", get_all_pack_paths())
    def test_pack_loads_without_error(self, pack_path: Path) -> None:
        """Each policy pack should load without YAML errors."""
        data = load_yaml(pack_path)
        assert data is not None
        # Policy packs have fields at root level (flat structure)
        assert "id" in data
        assert "coverage_sections" in data or "exclusions" in data

    @pytest.mark.parametrize("pack_path", get_all_pack_paths())
    def test_pack_has_required_policy_fields(self, pack_path: Path) -> None:
        """Each policy should have required fields."""
        data = load_yaml(pack_path)

        required_fields = ["id", "jurisdiction", "line_of_business", "name", "version"]
        for field in required_fields:
            assert field in data, f"Missing {field} in {pack_path.name}"

    @pytest.mark.parametrize("pack_path", get_all_pack_paths())
    def test_coverage_sections_have_ids(self, pack_path: Path) -> None:
        """Each coverage section should have a unique ID."""
        data = load_yaml(pack_path)
        coverage_sections = data.get("coverage_sections", [])

        ids = [cs["id"] for cs in coverage_sections]
        assert len(ids) == len(set(ids)), f"Duplicate coverage IDs in {pack_path.name}"

    @pytest.mark.parametrize("pack_path", get_all_pack_paths())
    def test_exclusions_reference_valid_coverages(self, pack_path: Path) -> None:
        """Exclusions should reference existing coverage IDs."""
        data = load_yaml(pack_path)

        coverage_ids = {cs["id"] for cs in data.get("coverage_sections", [])}
        exclusions = data.get("exclusions", [])

        for exclusion in exclusions:
            applies_to = exclusion.get("applies_to_coverages", [])
            for coverage_id in applies_to:
                assert coverage_id in coverage_ids, (
                    f"Exclusion {exclusion['id']} references unknown coverage "
                    f"'{coverage_id}' in {pack_path.name}"
                )


class TestLineOfBusinessCoverage:
    """Test that all major lines of business are covered."""

    def test_auto_pack_exists(self) -> None:
        """Ontario OAP1 auto pack should exist."""
        path = PACKS_DIR / "auto" / "ontario_oap1.yaml"
        assert path.exists()
        data = load_yaml(path)
        assert data["line_of_business"] == "auto"

    def test_property_pack_exists(self) -> None:
        """Homeowners property pack should exist."""
        path = PACKS_DIR / "property" / "homeowners_ho3.yaml"
        assert path.exists()
        data = load_yaml(path)
        assert data["line_of_business"] == "property"

    def test_marine_pack_exists(self) -> None:
        """Marine pleasure craft pack should exist."""
        path = PACKS_DIR / "marine" / "pleasure_craft.yaml"
        assert path.exists()
        data = load_yaml(path)
        assert data["line_of_business"] == "marine"

    def test_health_pack_exists(self) -> None:
        """Group health pack should exist."""
        path = PACKS_DIR / "health" / "group_health.yaml"
        assert path.exists()
        data = load_yaml(path)
        assert data["line_of_business"] == "health"

    def test_workers_comp_pack_exists(self) -> None:
        """Workers compensation pack should exist."""
        path = PACKS_DIR / "workers_comp" / "ontario_wsib.yaml"
        assert path.exists()
        data = load_yaml(path)
        assert data["line_of_business"] == "workers_comp"

    def test_cgl_pack_exists(self) -> None:
        """Commercial general liability pack should exist."""
        path = PACKS_DIR / "liability" / "cgl.yaml"
        assert path.exists()
        data = load_yaml(path)
        assert data["line_of_business"] == "liability"

    def test_eo_pack_exists(self) -> None:
        """Professional E&O pack should exist."""
        path = PACKS_DIR / "liability" / "professional_eo.yaml"
        assert path.exists()
        data = load_yaml(path)
        assert data["line_of_business"] == "professional"

    def test_travel_pack_exists(self) -> None:
        """Travel medical pack should exist."""
        path = PACKS_DIR / "travel" / "travel_medical.yaml"
        assert path.exists()
        data = load_yaml(path)
        # Travel is categorized under health in this case
        assert data["line_of_business"] == "health"


class TestConditionComplexity:
    """Test that complex conditions can be parsed from YAML."""

    def test_nested_and_or_conditions(self) -> None:
        """Auto pack has nested AND/OR conditions in exclusions."""
        path = PACKS_DIR / "auto" / "ontario_oap1.yaml"
        data = load_yaml(path)

        # Find the impaired exclusion which has OR with multiple children
        impaired = next(
            (e for e in data["exclusions"] if e["id"] == "ex_impaired"),
            None
        )
        assert impaired is not None

        conditions = impaired["trigger_conditions"]
        assert len(conditions) > 0
        assert conditions[0]["op"] == "or"
        assert len(conditions[0]["children"]) >= 2

    def test_marine_combined_conditions(self) -> None:
        """Marine pack has combined AND conditions."""
        path = PACKS_DIR / "marine" / "pleasure_craft.yaml"
        data = load_yaml(path)

        # Ice damage exclusion has AND condition
        ice_exclusion = next(
            (e for e in data["exclusions"] if e["id"] == "ex_ice_damage"),
            None
        )
        assert ice_exclusion is not None

        conditions = ice_exclusion["trigger_conditions"]
        assert conditions[0]["op"] == "and"

    def test_health_waiting_period_condition(self) -> None:
        """Health pack has GTE condition for waiting periods."""
        path = PACKS_DIR / "health" / "group_health.yaml"
        data = load_yaml(path)

        # Find dental_major which has waiting period precondition
        dental_major = next(
            (cs for cs in data["coverage_sections"] if cs["id"] == "dental_major"),
            None
        )
        assert dental_major is not None

        # Find the GTE condition
        preconditions = dental_major["preconditions"]
        found_gte = False
        for pc in preconditions:
            if pc.get("op") == "and":
                for child in pc.get("children", []):
                    if child.get("op") == "gte":
                        found_gte = True
                        break
        assert found_gte, "Should have GTE condition for waiting period"


class TestEvidenceDiversity:
    """Test that different lines have different evidence requirements."""

    def test_auto_evidence_types(self) -> None:
        """Auto pack requires police reports, damage estimates."""
        path = PACKS_DIR / "auto" / "ontario_oap1.yaml"
        data = load_yaml(path)

        evidence_rules = data.get("evidence_rules", [])
        all_doc_types = set()
        for rule in evidence_rules:
            for doc in rule.get("required_documents", []):
                all_doc_types.add(doc["doc_type"])

        assert "police_report" in all_doc_types
        assert "damage_estimate" in all_doc_types

    def test_marine_evidence_types(self) -> None:
        """Marine pack requires coast guard reports, marine surveys."""
        path = PACKS_DIR / "marine" / "pleasure_craft.yaml"
        data = load_yaml(path)

        evidence_rules = data.get("evidence_rules", [])
        all_doc_types = set()
        for rule in evidence_rules:
            for doc in rule.get("required_documents", []):
                all_doc_types.add(doc["doc_type"])

        assert "coast_guard_report" in all_doc_types or "marine_survey" in all_doc_types

    def test_health_evidence_types(self) -> None:
        """Health pack requires pharmacy receipts, prescriptions."""
        path = PACKS_DIR / "health" / "group_health.yaml"
        data = load_yaml(path)

        evidence_rules = data.get("evidence_rules", [])
        all_doc_types = set()
        for rule in evidence_rules:
            for doc in rule.get("required_documents", []):
                all_doc_types.add(doc["doc_type"])

        assert "pharmacy_receipt" in all_doc_types or "prescription" in all_doc_types

    def test_workers_comp_evidence_types(self) -> None:
        """Workers comp requires Form 7, Form 8."""
        path = PACKS_DIR / "workers_comp" / "ontario_wsib.yaml"
        data = load_yaml(path)

        evidence_rules = data.get("evidence_rules", [])
        all_doc_types = set()
        for rule in evidence_rules:
            for doc in rule.get("required_documents", []):
                all_doc_types.add(doc["doc_type"])

        assert "form_7" in all_doc_types
        assert "form_8" in all_doc_types


class TestTimelineVariation:
    """Test that different lines have different timeline requirements."""

    def test_auto_has_60_day_decision(self) -> None:
        """Ontario auto has 60 calendar day coverage decision."""
        path = PACKS_DIR / "auto" / "ontario_oap1.yaml"
        data = load_yaml(path)

        timeline_rules = data.get("timeline_rules", [])
        decision_rule = next(
            (r for r in timeline_rules if r["event_type"] == "coverage_decision_due"),
            None
        )
        assert decision_rule is not None
        assert decision_rule["days_from_anchor"] == 60
        assert decision_rule["business_days"] is False

    def test_workers_comp_has_14_day_decision(self) -> None:
        """WSIB has 14 business day initial decision."""
        path = PACKS_DIR / "workers_comp" / "ontario_wsib.yaml"
        data = load_yaml(path)

        timeline_rules = data.get("timeline_rules", [])
        decision_rule = next(
            (r for r in timeline_rules if r["event_type"] == "coverage_decision_due"),
            None
        )
        assert decision_rule is not None
        assert decision_rule["days_from_anchor"] == 14
        assert decision_rule["business_days"] is True

    def test_health_has_30_day_adjudication(self) -> None:
        """Health claims have 30 day adjudication."""
        path = PACKS_DIR / "health" / "group_health.yaml"
        data = load_yaml(path)

        timeline_rules = data.get("timeline_rules", [])
        adjudicate_rule = next(
            (r for r in timeline_rules if r["event_type"] == "coverage_decision_due"),
            None
        )
        assert adjudicate_rule is not None
        assert adjudicate_rule["days_from_anchor"] == 30


class TestAuthorityRules:
    """Test that authority/escalation rules are properly defined."""

    def test_auto_denial_requires_supervisor(self) -> None:
        """Auto denials should require supervisor."""
        path = PACKS_DIR / "auto" / "ontario_oap1.yaml"
        data = load_yaml(path)

        authority_rules = data.get("authority_rules", [])
        denial_rule = next(
            (r for r in authority_rules if "denial" in r["id"].lower()),
            None
        )
        assert denial_rule is not None
        assert denial_rule["required_role"] == "supervisor"

    def test_cgl_lawsuit_requires_counsel(self) -> None:
        """CGL lawsuits should require claims counsel."""
        path = PACKS_DIR / "liability" / "cgl.yaml"
        data = load_yaml(path)

        authority_rules = data.get("authority_rules", [])
        lawsuit_rule = next(
            (r for r in authority_rules if "lawsuit" in r["id"].lower()),
            None
        )
        assert lawsuit_rule is not None
        assert "counsel" in lawsuit_rule["required_role"].lower()

    def test_marine_pollution_requires_specialist(self) -> None:
        """Marine pollution should require environmental specialist."""
        path = PACKS_DIR / "marine" / "pleasure_craft.yaml"
        data = load_yaml(path)

        authority_rules = data.get("authority_rules", [])
        pollution_rule = next(
            (r for r in authority_rules if "pollution" in r["id"].lower()),
            None
        )
        assert pollution_rule is not None
        assert "environmental" in pollution_rule["required_role"].lower()


class TestExclusionCoverage:
    """Test common exclusion patterns across lines."""

    def test_intentional_exclusion_exists(self) -> None:
        """Multiple lines should have intentional act exclusion."""
        packs_with_intentional = 0

        for pack_path in get_all_pack_paths():
            data = load_yaml(pack_path)
            exclusions = data.get("exclusions", [])

            has_intentional = any(
                "intent" in e["id"].lower() or "intent" in e.get("name", "").lower()
                for e in exclusions
            )
            if has_intentional:
                packs_with_intentional += 1

        assert packs_with_intentional >= 3, "Multiple lines should have intentional exclusion"

    def test_preexisting_exclusion_in_health(self) -> None:
        """Health lines should have pre-existing condition exclusion."""
        health_packs = [
            PACKS_DIR / "health" / "group_health.yaml",
            PACKS_DIR / "travel" / "travel_medical.yaml",
        ]

        for pack_path in health_packs:
            data = load_yaml(pack_path)
            exclusions = data.get("exclusions", [])

            has_preexisting = any(
                "preexist" in e["id"].lower() or "pre-exist" in e.get("name", "").lower()
                for e in exclusions
            )
            assert has_preexisting, f"Expected pre-existing exclusion in {pack_path.name}"


class TestDeterminism:
    """Test that policy pack hashing is deterministic."""

    def test_same_pack_same_hash(self) -> None:
        """Loading the same pack twice should produce same hash."""
        path = PACKS_DIR / "auto" / "ontario_oap1.yaml"

        # Load twice
        data1 = load_yaml(path)
        data2 = load_yaml(path)

        # Create Policy objects (flat YAML structure - fields at root level)
        policy1 = Policy(
            id=data1["id"],
            jurisdiction=data1["jurisdiction"],
            line_of_business=LineOfBusiness.AUTO,
            product_code=data1["product_code"],
            name=data1["name"],
            version=data1["version"],
            effective_date=date.fromisoformat(data1["effective_date"]),
        )

        policy2 = Policy(
            id=data2["id"],
            jurisdiction=data2["jurisdiction"],
            line_of_business=LineOfBusiness.AUTO,
            product_code=data2["product_code"],
            name=data2["name"],
            version=data2["version"],
            effective_date=date.fromisoformat(data2["effective_date"]),
        )

        hash1 = compute_policy_pack_hash(policy1)
        hash2 = compute_policy_pack_hash(policy2)

        assert hash1 == hash2

    def test_different_packs_different_hashes(self) -> None:
        """Different packs should have different hashes."""
        auto_path = PACKS_DIR / "auto" / "ontario_oap1.yaml"
        marine_path = PACKS_DIR / "marine" / "pleasure_craft.yaml"

        auto_data = load_yaml(auto_path)
        marine_data = load_yaml(marine_path)

        # Flat YAML structure - fields at root level
        auto_policy = Policy(
            id=auto_data["id"],
            jurisdiction=auto_data["jurisdiction"],
            line_of_business=LineOfBusiness.AUTO,
            product_code=auto_data["product_code"],
            name=auto_data["name"],
            version=auto_data["version"],
            effective_date=date.fromisoformat(auto_data["effective_date"]),
        )

        marine_policy = Policy(
            id=marine_data["id"],
            jurisdiction=marine_data["jurisdiction"],
            line_of_business=LineOfBusiness.MARINE,
            product_code=marine_data["product_code"],
            name=marine_data["name"],
            version=marine_data["version"],
            effective_date=date.fromisoformat(marine_data["effective_date"]),
        )

        auto_hash = compute_policy_pack_hash(auto_policy)
        marine_hash = compute_policy_pack_hash(marine_policy)

        assert auto_hash != marine_hash


class TestPackMetrics:
    """Gather metrics about the policy packs."""

    def test_pack_count(self) -> None:
        """Should have at least 8 policy packs."""
        packs = get_all_pack_paths()
        # Filter out examples directory
        real_packs = [p for p in packs if "examples" not in str(p)]
        assert len(real_packs) >= 8, f"Expected 8+ packs, got {len(real_packs)}"

    def test_total_coverage_sections(self) -> None:
        """Count total coverage sections across all packs."""
        total = 0
        for pack_path in get_all_pack_paths():
            if "examples" in str(pack_path):
                continue
            data = load_yaml(pack_path)
            total += len(data.get("coverage_sections", []))

        assert total >= 30, f"Expected 30+ coverage sections, got {total}"

    def test_total_exclusions(self) -> None:
        """Count total exclusions across all packs."""
        total = 0
        for pack_path in get_all_pack_paths():
            if "examples" in str(pack_path):
                continue
            data = load_yaml(pack_path)
            total += len(data.get("exclusions", []))

        assert total >= 35, f"Expected 35+ exclusions, got {total}"

    def test_exclusions_have_policy_wording(self) -> None:
        """All exclusions should have actual policy wording."""
        missing_wording = []

        for pack_path in get_all_pack_paths():
            if "examples" in str(pack_path):
                continue
            data = load_yaml(pack_path)

            for exclusion in data.get("exclusions", []):
                if not exclusion.get("policy_wording"):
                    missing_wording.append(f"{pack_path.name}:{exclusion['id']}")

        assert len(missing_wording) == 0, f"Exclusions missing policy_wording: {missing_wording}"
