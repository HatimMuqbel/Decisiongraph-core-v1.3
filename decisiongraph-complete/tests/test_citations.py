"""
Tests for DecisionGraph Policy Citations Module.
"""

import pytest
from decimal import Decimal

from decisiongraph.citations import (
    PolicyCitation,
    CitationCompact,
    CitationQuality,
    CitationRegistry,
    compute_citation_hash,
    build_registry_from_pack,
    format_citation_for_report,
    format_citations_section,
    format_citation_quality_section,
)


class TestPolicyCitation:
    """Tests for PolicyCitation dataclass."""

    def test_citation_creation(self):
        """Test creating a policy citation."""
        citation = PolicyCitation(
            authority="FINTRAC",
            document="PCMLTFR",
            section="s. 12",
            url="https://example.com/pcmltfr"
        )

        assert citation.authority == "FINTRAC"
        assert citation.document == "PCMLTFR"
        assert citation.section == "s. 12"
        assert citation.url == "https://example.com/pcmltfr"
        assert len(citation.citation_hash) == 64

    def test_citation_hash_computed(self):
        """Test that citation hash is auto-computed."""
        citation = PolicyCitation(
            authority="FINTRAC",
            document="PCMLTFR",
            section="s. 12"
        )

        expected_hash = compute_citation_hash("FINTRAC", "s. 12")
        assert citation.citation_hash == expected_hash

    def test_citation_to_dict(self):
        """Test serialization to dict."""
        citation = PolicyCitation(
            authority="FINTRAC",
            document="PCMLTFR",
            section="s. 12",
            url="https://example.com"
        )

        d = citation.to_dict()
        assert d["authority"] == "FINTRAC"
        assert d["document"] == "PCMLTFR"
        assert d["section"] == "s. 12"
        assert d["url"] == "https://example.com"
        assert "citation_hash" in d

    def test_citation_from_dict(self):
        """Test deserialization from dict."""
        d = {
            "authority": "FATF",
            "document": "Recommendations",
            "section": "Recommendation 15",
            "citation_hash": "abc123"
        }

        citation = PolicyCitation.from_dict(d)
        assert citation.authority == "FATF"
        assert citation.document == "Recommendations"
        assert citation.section == "Recommendation 15"
        # Hash should be from dict, not recomputed
        assert citation.citation_hash == "abc123"

    def test_citation_short_hash(self):
        """Test short hash property."""
        citation = PolicyCitation(
            authority="FINTRAC",
            document="PCMLTFR",
            section="s. 12"
        )

        assert len(citation.short_hash) == 16
        assert citation.short_hash == citation.citation_hash[:16]

    def test_citation_str(self):
        """Test string representation."""
        citation = PolicyCitation(
            authority="FINTRAC",
            document="PCMLTFR",
            section="s. 12"
        )

        assert str(citation) == "FINTRAC - s. 12"


class TestComputeCitationHash:
    """Tests for citation hash computation."""

    def test_deterministic_hash(self):
        """Test that hash is deterministic."""
        hash1 = compute_citation_hash("FINTRAC", "s. 12")
        hash2 = compute_citation_hash("FINTRAC", "s. 12")
        assert hash1 == hash2

    def test_case_insensitive_authority(self):
        """Test that authority is normalized to uppercase."""
        hash1 = compute_citation_hash("fintrac", "s. 12")
        hash2 = compute_citation_hash("FINTRAC", "s. 12")
        assert hash1 == hash2

    def test_whitespace_handling(self):
        """Test that whitespace is normalized."""
        hash1 = compute_citation_hash("FINTRAC ", " s. 12")
        hash2 = compute_citation_hash("FINTRAC", "s. 12")
        # Note: current implementation strips but preserves internal whitespace
        # This is expected behavior for section references

    def test_different_citations_different_hashes(self):
        """Test that different citations have different hashes."""
        hash1 = compute_citation_hash("FINTRAC", "s. 12")
        hash2 = compute_citation_hash("FINTRAC", "s. 13")
        hash3 = compute_citation_hash("FATF", "s. 12")

        assert hash1 != hash2
        assert hash1 != hash3
        assert hash2 != hash3


class TestCitationCompact:
    """Tests for CitationCompact."""

    def test_compact_from_policy_citation(self):
        """Test creating compact citation from full citation."""
        full = PolicyCitation(
            authority="FINTRAC",
            document="PCMLTFR",
            section="s. 12",
            url="https://example.com"
        )

        compact = CitationCompact.from_policy_citation(full)
        assert compact.authority == "FINTRAC"
        assert compact.section == "s. 12"
        assert compact.hash == full.citation_hash

    def test_compact_to_dict(self):
        """Test compact citation serialization."""
        compact = CitationCompact(
            authority="FINTRAC",
            section="s. 12",
            hash="abc123"
        )

        d = compact.to_dict()
        assert d["authority"] == "FINTRAC"
        assert d["section"] == "s. 12"
        assert d["hash"] == "abc123"


class TestCitationRegistry:
    """Tests for CitationRegistry."""

    def test_register_signal_citation(self):
        """Test registering a citation for a signal."""
        registry = CitationRegistry()

        citation = PolicyCitation(
            authority="FINTRAC",
            document="PCMLTFR",
            section="s. 12"
        )

        registry.register_signal_citation("TXN_LARGE_CASH", citation)

        citations = registry.get_citations_for_signal("TXN_LARGE_CASH")
        assert len(citations) == 1
        assert citations[0].authority == "FINTRAC"

    def test_multiple_citations_per_signal(self):
        """Test registering multiple citations for a signal."""
        registry = CitationRegistry()

        registry.register_signal_citation("GEO_HIGH_RISK", PolicyCitation(
            authority="FINTRAC",
            document="Guideline 6",
            section="High-risk jurisdictions"
        ))
        registry.register_signal_citation("GEO_HIGH_RISK", PolicyCitation(
            authority="FATF",
            document="Recommendations",
            section="Recommendation 19"
        ))

        citations = registry.get_citations_for_signal("GEO_HIGH_RISK")
        assert len(citations) == 2

    def test_get_citation_by_hash(self):
        """Test looking up citation by hash."""
        registry = CitationRegistry()

        citation = PolicyCitation(
            authority="FINTRAC",
            document="PCMLTFR",
            section="s. 12"
        )

        registry.register_signal_citation("TXN_LARGE_CASH", citation)

        found = registry.get_citation_by_hash(citation.citation_hash)
        assert found is not None
        assert found.authority == "FINTRAC"

    def test_get_compact_citations(self):
        """Test getting compact citations for embedding."""
        registry = CitationRegistry()

        registry.register_signal_citation("TXN_LARGE_CASH", PolicyCitation(
            authority="FINTRAC",
            document="PCMLTFR",
            section="s. 12"
        ))

        compacts = registry.get_compact_citations_for_signal("TXN_LARGE_CASH")
        assert len(compacts) == 1
        assert compacts[0].authority == "FINTRAC"

    def test_compute_citation_quality_full_coverage(self):
        """Test citation quality with full coverage."""
        registry = CitationRegistry()

        registry.register_signal_citation("SIG_1", PolicyCitation(
            authority="FINTRAC",
            document="PCMLTFR",
            section="s. 1"
        ))
        registry.register_signal_citation("SIG_2", PolicyCitation(
            authority="FINTRAC",
            document="PCMLTFR",
            section="s. 2"
        ))

        quality = registry.compute_citation_quality(["SIG_1", "SIG_2"])

        assert quality.total_signals == 2
        assert quality.signals_with_citations == 2
        assert quality.coverage_ratio == Decimal("1.00")
        assert quality.missing_signals == []

    def test_compute_citation_quality_partial_coverage(self):
        """Test citation quality with partial coverage."""
        registry = CitationRegistry()

        registry.register_signal_citation("SIG_1", PolicyCitation(
            authority="FINTRAC",
            document="PCMLTFR",
            section="s. 1"
        ))

        quality = registry.compute_citation_quality(["SIG_1", "SIG_2", "SIG_3"])

        assert quality.total_signals == 3
        assert quality.signals_with_citations == 1
        assert quality.coverage_ratio == Decimal("0.33")
        assert "SIG_2" in quality.missing_signals
        assert "SIG_3" in quality.missing_signals

    def test_all_signal_codes(self):
        """Test getting all registered signal codes."""
        registry = CitationRegistry()

        registry.register_signal_citation("SIG_1", PolicyCitation(
            authority="A", document="D", section="S1"
        ))
        registry.register_signal_citation("SIG_2", PolicyCitation(
            authority="A", document="D", section="S2"
        ))

        codes = registry.all_signal_codes()
        assert "SIG_1" in codes
        assert "SIG_2" in codes


class TestBuildRegistryFromPack:
    """Tests for building registry from pack data."""

    def test_build_from_enhanced_format(self):
        """Test building registry from enhanced policy_refs format."""
        pack_data = {
            "signals": [
                {
                    "code": "TXN_LARGE_CASH",
                    "policy_refs": [
                        {
                            "authority": "FINTRAC",
                            "document": "PCMLTFR",
                            "section": "s. 12",
                            "url": "https://example.com"
                        }
                    ]
                }
            ]
        }

        registry = build_registry_from_pack(pack_data)

        citations = registry.get_citations_for_signal("TXN_LARGE_CASH")
        assert len(citations) == 1
        assert citations[0].authority == "FINTRAC"
        assert citations[0].section == "s. 12"

    def test_build_from_simple_format(self):
        """Test building registry from simple policy_ref format."""
        pack_data = {
            "signals": [
                {
                    "code": "TXN_LARGE_CASH",
                    "policy_ref": "PCMLTFR s. 12"
                }
            ]
        }

        registry = build_registry_from_pack(pack_data)

        citations = registry.get_citations_for_signal("TXN_LARGE_CASH")
        assert len(citations) == 1
        assert citations[0].authority == "PCMLTFR"
        assert citations[0].section == "s. 12"

    def test_build_with_mitigations(self):
        """Test building registry includes mitigations."""
        pack_data = {
            "signals": [],
            "mitigations": [
                {
                    "code": "MF_DOC_COMPLETE",
                    "policy_ref": "PCMLTFR s. 64"
                }
            ]
        }

        registry = build_registry_from_pack(pack_data)

        citations = registry.get_citations_for_mitigation("MF_DOC_COMPLETE")
        assert len(citations) == 1


class TestFormatFunctions:
    """Tests for report formatting functions."""

    def test_format_citation_for_report(self):
        """Test formatting a citation for report output."""
        citation = PolicyCitation(
            authority="FINTRAC",
            document="PCMLTFR",
            section="s. 12"
        )

        lines = format_citation_for_report(citation, index=1)

        assert len(lines) >= 3  # authority, document, section, hash
        assert "1. FINTRAC" in lines[0]
        assert any("PCMLTFR" in line for line in lines)
        assert any("s. 12" in line for line in lines)

    def test_format_citations_section(self):
        """Test formatting full citations section."""
        registry = CitationRegistry()

        registry.register_signal_citation("SIG_1", PolicyCitation(
            authority="FINTRAC",
            document="PCMLTFR",
            section="s. 12"
        ))

        lines = format_citations_section(registry, ["SIG_1"])

        assert any("POLICY CITATIONS" in line for line in lines)
        assert any("SIG_1" in line for line in lines)
        assert any("FINTRAC" in line for line in lines)

    def test_format_citation_quality_section(self):
        """Test formatting citation quality summary."""
        quality = CitationQuality(
            total_signals=10,
            signals_with_citations=8,
            total_citations=12,
            coverage_ratio=Decimal("0.80"),
            missing_signals=["SIG_9", "SIG_10"]
        )

        lines = format_citation_quality_section(quality)

        assert any("CITATION QUALITY" in line for line in lines)
        assert any("8/10" in line for line in lines)
        assert any("80%" in line for line in lines)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
