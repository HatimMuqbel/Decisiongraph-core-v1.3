"""
Audit Simulation Tests

Simulate real-world audit scenarios where someone challenges:
"How do we know you didn't change the rules after the fact?"

These tests prove the provenance story is bulletproof.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date

import pytest
from pydantic import ValidationError

from claimpilot.models import (
    Policy,
    CoverageSection,
    Exclusion,
    LineOfBusiness,
)
from claimpilot.canon import compute_policy_pack_hash, excerpt_hash
from claimpilot.packs.schema import PolicyPackSchema
from claimpilot.packs.loader import validate_reference_integrity


class TestSchemaStrictness:
    """Test that schemas reject unknown fields."""

    def test_schema_rejects_unknown_fields(self) -> None:
        """Unknown fields should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            PolicyPackSchema(
                id="TEST",
                jurisdiction="CA-ON",
                line_of_business="auto",
                product_code="TEST",
                name="Test",
                version="1.0",
                effective_date=date(2024, 1, 1),
                unknown_field="should fail"  # This should be rejected
            )

        assert "extra" in str(exc_info.value).lower()

    def test_misspelled_field_rejected(self) -> None:
        """Misspelled fields should raise validation error."""
        with pytest.raises(ValidationError):
            PolicyPackSchema(
                id="TEST",
                jurisdiction="CA-ON",
                line_of_business="auto",
                product_code="TEST",
                name="Test",
                version="1.0",
                effectiv_date=date(2024, 1, 1)  # Misspelled!
            )

    def test_valid_schema_passes(self) -> None:
        """Valid schema should pass validation."""
        schema = PolicyPackSchema(
            id="TEST",
            jurisdiction="CA-ON",
            line_of_business="auto",
            product_code="TEST",
            name="Test Policy",
            version="1.0",
            effective_date=date(2024, 1, 1),
        )
        assert schema.id == "TEST"


class TestReferenceIntegrity:
    """Test reference integrity validation."""

    def test_invalid_coverage_reference_rejected(self) -> None:
        """Exclusion referencing non-existent coverage should fail."""
        policy = Policy(
            id="TEST",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.AUTO,
            product_code="T",
            name="T",
            version="1.0",
            effective_date=date(2024, 1, 1),
            coverage_sections=[
                CoverageSection(id="real", code="R", name="R", description="R")
            ],
            exclusions=[
                Exclusion(
                    id="ex",
                    code="E",
                    name="E",
                    description="E",
                    policy_wording="E",
                    policy_section_ref="E",
                    applies_to_coverages=["nonexistent"]  # Invalid!
                )
            ]
        )

        with pytest.raises(ValueError, match="non-existent"):
            validate_reference_integrity(policy, "test.yaml")

    def test_duplicate_coverage_id_rejected(self) -> None:
        """Duplicate coverage IDs should fail."""
        policy = Policy(
            id="TEST",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.AUTO,
            product_code="T",
            name="T",
            version="1.0",
            effective_date=date(2024, 1, 1),
            coverage_sections=[
                CoverageSection(id="same", code="A", name="A", description="A"),
                CoverageSection(id="same", code="B", name="B", description="B"),  # Duplicate!
            ]
        )

        with pytest.raises(ValueError, match="Duplicate coverage ID"):
            validate_reference_integrity(policy, "test.yaml")

    def test_duplicate_exclusion_id_rejected(self) -> None:
        """Duplicate exclusion IDs should fail."""
        policy = Policy(
            id="TEST",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.AUTO,
            product_code="T",
            name="T",
            version="1.0",
            effective_date=date(2024, 1, 1),
            exclusions=[
                Exclusion(id="dup", code="A", name="A", description="A",
                         policy_wording="A", policy_section_ref="A"),
                Exclusion(id="dup", code="B", name="B", description="B",
                         policy_wording="B", policy_section_ref="B"),  # Duplicate!
            ]
        )

        with pytest.raises(ValueError, match="Duplicate exclusion ID"):
            validate_reference_integrity(policy, "test.yaml")

    def test_valid_references_pass(self) -> None:
        """Valid references should pass."""
        policy = Policy(
            id="TEST",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.AUTO,
            product_code="T",
            name="T",
            version="1.0",
            effective_date=date(2024, 1, 1),
            coverage_sections=[
                CoverageSection(id="cov1", code="A", name="A", description="A")
            ],
            exclusions=[
                Exclusion(
                    id="ex1",
                    code="E",
                    name="E",
                    description="E",
                    policy_wording="E",
                    policy_section_ref="E",
                    applies_to_coverages=["cov1"]  # Valid reference
                )
            ]
        )

        # Should not raise
        validate_reference_integrity(policy, "test.yaml")


class TestAuditSimulation:
    """Simulate audit scenarios to prove provenance integrity."""

    @pytest.fixture
    def sample_policy(self) -> Policy:
        return Policy(
            id="AUDIT-TEST-001",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.AUTO,
            product_code="OAP1",
            name="Audit Test Policy",
            version="1.0",
            effective_date=date(2024, 1, 1),
            coverage_sections=[
                CoverageSection(
                    id="collision",
                    code="C",
                    name="Collision",
                    description="Collision coverage"
                )
            ],
            exclusions=[
                Exclusion(
                    id="ex_commercial",
                    code="4.2.1",
                    name="Commercial Use",
                    description="Commercial use exclusion",
                    policy_wording="We do not cover loss while vehicle is used for commercial purposes.",
                    policy_section_ref="Section 4.2.1",
                    applies_to_coverages=["collision"]
                )
            ]
        )

    def test_detects_wording_change(self, sample_policy: Policy) -> None:
        """Changing exclusion wording must change hash."""
        original_hash = compute_policy_pack_hash(sample_policy)

        modified = deepcopy(sample_policy)
        modified.exclusions[0].policy_wording = "MODIFIED WORDING"
        modified_hash = compute_policy_pack_hash(modified)

        assert original_hash != modified_hash, \
            "Hash must change when exclusion wording is modified"

    def test_detects_exclusion_added(self, sample_policy: Policy) -> None:
        """Adding exclusion must change hash."""
        original_hash = compute_policy_pack_hash(sample_policy)

        modified = deepcopy(sample_policy)
        modified.exclusions.append(
            Exclusion(
                id="ex_new",
                code="NEW",
                name="New",
                description="Added",
                policy_wording="New exclusion",
                policy_section_ref="New",
                applies_to_coverages=["collision"]
            )
        )
        modified_hash = compute_policy_pack_hash(modified)

        assert original_hash != modified_hash, \
            "Hash must change when exclusion is added"

    def test_detects_exclusion_removed(self, sample_policy: Policy) -> None:
        """Removing exclusion must change hash."""
        original_hash = compute_policy_pack_hash(sample_policy)

        modified = deepcopy(sample_policy)
        modified.exclusions = []
        modified_hash = compute_policy_pack_hash(modified)

        assert original_hash != modified_hash, \
            "Hash must change when exclusion is removed"

    def test_detects_version_change(self, sample_policy: Policy) -> None:
        """Changing version must change hash."""
        original_hash = compute_policy_pack_hash(sample_policy)

        modified = deepcopy(sample_policy)
        modified.version = "2.0"
        modified_hash = compute_policy_pack_hash(modified)

        assert original_hash != modified_hash, \
            "Hash must change when version is changed"

    def test_detects_coverage_added(self, sample_policy: Policy) -> None:
        """Adding coverage must change hash."""
        original_hash = compute_policy_pack_hash(sample_policy)

        modified = deepcopy(sample_policy)
        modified.coverage_sections.append(
            CoverageSection(
                id="new_cov",
                code="N",
                name="New Coverage",
                description="Added"
            )
        )
        modified_hash = compute_policy_pack_hash(modified)

        assert original_hash != modified_hash, \
            "Hash must change when coverage is added"

    def test_detects_jurisdiction_change(self, sample_policy: Policy) -> None:
        """Changing jurisdiction must change hash."""
        original_hash = compute_policy_pack_hash(sample_policy)

        modified = deepcopy(sample_policy)
        modified.jurisdiction = "CA-BC"
        modified_hash = compute_policy_pack_hash(modified)

        assert original_hash != modified_hash, \
            "Hash must change when jurisdiction is changed"


class TestExcerptHashing:
    """Test excerpt hashing for policy wording provenance."""

    def test_excerpt_hash_detects_wording_change(self) -> None:
        """Excerpt hash must detect wording changes."""
        original = "We do not cover commercial use."
        modified = "We do not cover business use."

        assert excerpt_hash(original) != excerpt_hash(modified), \
            "Excerpt hash must change when wording changes"

    def test_excerpt_hash_stable_for_whitespace(self) -> None:
        """Whitespace differences should not change excerpt hash."""
        v1 = "We do not cover   loss or damage."
        v2 = "We do not cover loss or damage."
        v3 = "We do not cover\nloss or damage."
        v4 = "  We do not cover loss or damage.  "

        assert excerpt_hash(v1) == excerpt_hash(v2), \
            "Multiple spaces should normalize"
        assert excerpt_hash(v2) == excerpt_hash(v3), \
            "Newlines should normalize to spaces"
        assert excerpt_hash(v2) == excerpt_hash(v4), \
            "Leading/trailing whitespace should be stripped"

    def test_case_sensitivity_preserved(self) -> None:
        """Case changes should change hash (legal text fidelity)."""
        v1 = "We do not cover loss."
        v2 = "we do not cover loss."
        v3 = "WE DO NOT COVER LOSS."

        assert excerpt_hash(v1) != excerpt_hash(v2), \
            "Lowercase change should be detected"
        assert excerpt_hash(v1) != excerpt_hash(v3), \
            "Uppercase change should be detected"

    def test_special_characters_preserved(self) -> None:
        """Special characters should be preserved in hash."""
        v1 = 'Coverage "A" applies.'
        v2 = "Coverage 'A' applies."

        assert excerpt_hash(v1) != excerpt_hash(v2), \
            "Quote style change should be detected"

    def test_empty_string_hashes(self) -> None:
        """Empty and whitespace-only strings should hash consistently."""
        assert excerpt_hash("") == excerpt_hash("")
        assert excerpt_hash("   ") == excerpt_hash("\t\n")


class TestFullAuditTrail:
    """Full audit trail simulation tests."""

    def test_full_audit_trail_tampering_detected(self) -> None:
        """
        Full audit simulation:
        1. Record provenance at recommendation time
        2. Attempt to modify policy
        3. Verify tampering is detected
        """
        # Step 1: Create policy and record provenance
        policy = Policy(
            id="AUDIT-001",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.AUTO,
            product_code="OAP1",
            name="Test",
            version="1.0",
            effective_date=date(2024, 1, 1),
            exclusions=[
                Exclusion(
                    id="ex1",
                    code="4.2.1",
                    name="Commercial Use",
                    description="Desc",
                    policy_wording="We do not cover commercial use.",
                    policy_section_ref="4.2.1"
                )
            ]
        )

        # Record at "recommendation time"
        stored = {
            "policy_pack_hash": compute_policy_pack_hash(policy),
            "excerpt_hash": excerpt_hash(policy.exclusions[0].policy_wording)
        }

        # Step 2: Tamper with the policy
        policy.exclusions[0].policy_wording = "TAMPERED WORDING"

        # Step 3: Verify tampering is detected
        current_hash = compute_policy_pack_hash(policy)
        current_excerpt_hash = excerpt_hash(policy.exclusions[0].policy_wording)

        assert stored["policy_pack_hash"] != current_hash, \
            "Pack hash verification must fail after tampering"
        assert stored["excerpt_hash"] != current_excerpt_hash, \
            "Excerpt hash verification must fail after tampering"

    def test_audit_trail_integrity_maintained(self) -> None:
        """Policy that hasn't changed should verify successfully."""
        policy = Policy(
            id="AUDIT-002",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.PROPERTY,
            product_code="HO3",
            name="Test",
            version="1.0",
            effective_date=date(2024, 1, 1),
            coverage_sections=[
                CoverageSection(id="cov_a", code="A", name="Dwelling", description="D")
            ]
        )

        # Record
        stored_hash = compute_policy_pack_hash(policy)

        # Verify (no changes)
        current_hash = compute_policy_pack_hash(policy)

        assert stored_hash == current_hash, \
            "Unchanged policy should verify successfully"

    def test_ordering_does_not_affect_hash(self) -> None:
        """Policy with same content in different order should have same hash."""
        cov_a = CoverageSection(id="cov_a", code="A", name="A", description="A")
        cov_b = CoverageSection(id="cov_b", code="B", name="B", description="B")

        ex_x = Exclusion(
            id="ex_x", code="X", name="X", description="X",
            policy_wording="X", policy_section_ref="X"
        )
        ex_y = Exclusion(
            id="ex_y", code="Y", name="Y", description="Y",
            policy_wording="Y", policy_section_ref="Y"
        )

        # Order 1: A, B, X, Y
        policy1 = Policy(
            id="TEST", jurisdiction="CA-ON", line_of_business=LineOfBusiness.AUTO,
            product_code="T", name="T", version="1.0", effective_date=date(2024, 1, 1),
            coverage_sections=[cov_a, cov_b], exclusions=[ex_x, ex_y]
        )

        # Order 2: B, A, Y, X (reversed)
        policy2 = Policy(
            id="TEST", jurisdiction="CA-ON", line_of_business=LineOfBusiness.AUTO,
            product_code="T", name="T", version="1.0", effective_date=date(2024, 1, 1),
            coverage_sections=[cov_b, cov_a], exclusions=[ex_y, ex_x]
        )

        assert compute_policy_pack_hash(policy1) == compute_policy_pack_hash(policy2), \
            "Hash must be identical regardless of list insertion order"


class TestCollisionResistance:
    """Sanity checks for hash collision resistance."""

    def test_similar_packs_different_hashes(self) -> None:
        """Two similar but different packs must have different hashes."""
        policy1 = Policy(
            id="PACK-A",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.AUTO,
            product_code="OAP1",
            name="Policy A",
            version="1.0",
            effective_date=date(2024, 1, 1),
        )

        policy2 = Policy(
            id="PACK-B",  # Only ID differs
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.AUTO,
            product_code="OAP1",
            name="Policy A",
            version="1.0",
            effective_date=date(2024, 1, 1),
        )

        hash1 = compute_policy_pack_hash(policy1)
        hash2 = compute_policy_pack_hash(policy2)

        assert hash1 != hash2, \
            "Different packs must have different hashes"

    def test_hash_format_validity(self) -> None:
        """Hash must be valid hex string of correct length."""
        policy = Policy(
            id="FORMAT-TEST",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.AUTO,
            product_code="OAP1",
            name="Test",
            version="1.0",
            effective_date=date(2024, 1, 1),
        )

        hash_value = compute_policy_pack_hash(policy)

        # SHA-256 produces 64 hex characters
        assert len(hash_value) == 64, \
            f"Hash must be 64 characters, got {len(hash_value)}"
        assert all(c in "0123456789abcdef" for c in hash_value), \
            "Hash must be valid lowercase hex"

    def test_empty_vs_populated_different(self) -> None:
        """Empty policy vs policy with content must differ."""
        empty = Policy(
            id="EMPTY",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.AUTO,
            product_code="E",
            name="Empty",
            version="1.0",
            effective_date=date(2024, 1, 1),
        )

        populated = Policy(
            id="EMPTY",
            jurisdiction="CA-ON",
            line_of_business=LineOfBusiness.AUTO,
            product_code="E",
            name="Empty",
            version="1.0",
            effective_date=date(2024, 1, 1),
            coverage_sections=[
                CoverageSection(id="cov", code="C", name="Cov", description="D")
            ]
        )

        assert compute_policy_pack_hash(empty) != compute_policy_pack_hash(populated), \
            "Empty vs populated must have different hashes"


class TestSchemaAuthorityReferences:
    """Test authority reference validation at schema level."""

    def test_duplicate_authority_id_rejected(self) -> None:
        """Duplicate authority IDs should fail."""
        from claimpilot.packs.loader import validate_schema_reference_integrity
        from claimpilot.packs.schema import PolicyPackSchema, AuthorityRefSchema

        schema = PolicyPackSchema(
            id="TEST",
            jurisdiction="CA-ON",
            line_of_business="auto",
            product_code="T",
            name="T",
            version="1.0",
            effective_date=date(2024, 1, 1),
            authorities=[
                AuthorityRefSchema(
                    id="auth-1", type="policy_wording", title="A",
                    section="1", source_name="S"
                ),
                AuthorityRefSchema(
                    id="auth-1", type="policy_wording", title="B",  # Duplicate!
                    section="2", source_name="S"
                ),
            ]
        )

        with pytest.raises(ValueError, match="Duplicate authority ID"):
            validate_schema_reference_integrity(schema, "test.yaml")

    def test_invalid_authority_ref_in_coverage_rejected(self) -> None:
        """Coverage referencing non-existent authority should fail."""
        from claimpilot.packs.loader import validate_schema_reference_integrity
        from claimpilot.packs.schema import PolicyPackSchema, CoverageSectionSchema

        schema = PolicyPackSchema(
            id="TEST",
            jurisdiction="CA-ON",
            line_of_business="auto",
            product_code="T",
            name="T",
            version="1.0",
            effective_date=date(2024, 1, 1),
            coverage_sections=[
                CoverageSectionSchema(
                    id="cov-1", code="C", name="Cov", description="D",
                    authority_ref_id="nonexistent"  # Invalid!
                )
            ]
        )

        with pytest.raises(ValueError, match="non-existent authority"):
            validate_schema_reference_integrity(schema, "test.yaml")

    def test_valid_authority_refs_pass(self) -> None:
        """Valid authority references should pass."""
        from claimpilot.packs.loader import validate_schema_reference_integrity
        from claimpilot.packs.schema import (
            PolicyPackSchema, AuthorityRefSchema, CoverageSectionSchema
        )

        schema = PolicyPackSchema(
            id="TEST",
            jurisdiction="CA-ON",
            line_of_business="auto",
            product_code="T",
            name="T",
            version="1.0",
            effective_date=date(2024, 1, 1),
            authorities=[
                AuthorityRefSchema(
                    id="auth-1", type="policy_wording", title="A",
                    section="1", source_name="S"
                )
            ],
            coverage_sections=[
                CoverageSectionSchema(
                    id="cov-1", code="C", name="Cov", description="D",
                    authority_ref_id="auth-1"  # Valid reference
                )
            ]
        )

        # Should not raise
        validate_schema_reference_integrity(schema, "test.yaml")
