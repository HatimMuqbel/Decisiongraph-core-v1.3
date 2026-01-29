"""
DecisionGraph Policy Citations Module (v2.0)

Provides structured policy citations for audit-trail anchoring.
Every signal can be tied to specific regulatory requirements with
verifiable citation hashes.

Key concepts:
- PolicyCitation: Structured reference to a regulatory document
- CitationRegistry: Manages citations and computes quality metrics
- Citation Hash: SHA256 of (authority + section) for verification

USAGE:
    from decisiongraph.citations import (
        PolicyCitation, CitationRegistry, compute_citation_hash
    )

    citation = PolicyCitation(
        authority="FINTRAC",
        document="Proceeds of Crime (Money Laundering) Act",
        section="3. Reporting requirements - Large cash transactions",
        url="https://www.fintrac-canafe.gc.ca/guidance..."
    )

    registry = CitationRegistry()
    registry.register_citation("TXN_LARGE_CASH", citation)

    # Quality metrics
    quality = registry.compute_citation_quality(fired_signals)
"""

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from decimal import Decimal


# =============================================================================
# EXCEPTIONS
# =============================================================================

class CitationError(Exception):
    """Base exception for citation errors."""
    pass


class CitationNotFoundError(CitationError):
    """Raised when citation is not found."""
    pass


# =============================================================================
# POLICY CITATION
# =============================================================================

@dataclass
class PolicyCitation:
    """
    Structured reference to a regulatory document or policy.

    Each citation anchors a signal/mitigation to specific regulatory
    requirements for audit purposes.
    """
    authority: str                # Regulatory authority (e.g., FINTRAC, FATF, EU)
    document: str                 # Full document name
    section: str                  # Section reference
    url: Optional[str] = None     # Source URL (optional)
    citation_hash: str = ""       # Auto-computed SHA256

    def __post_init__(self):
        """Compute citation hash if not provided."""
        if not self.citation_hash:
            self.citation_hash = compute_citation_hash(self.authority, self.section)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "authority": self.authority,
            "document": self.document,
            "section": self.section,
            "citation_hash": self.citation_hash,
        }
        if self.url:
            result["url"] = self.url
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PolicyCitation':
        """Create from dictionary."""
        return cls(
            authority=data.get("authority", ""),
            document=data.get("document", ""),
            section=data.get("section", ""),
            url=data.get("url"),
            citation_hash=data.get("citation_hash", ""),
        )

    def __str__(self) -> str:
        """Human-readable representation."""
        return f"{self.authority} - {self.section}"

    @property
    def short_hash(self) -> str:
        """First 16 characters of citation hash."""
        return self.citation_hash[:16] if self.citation_hash else ""


def compute_citation_hash(authority: str, section: str) -> str:
    """
    Compute deterministic hash for a citation.

    This hash can be used to verify citation integrity and
    detect changes to regulatory references.
    """
    canonical = f"{authority.upper().strip()}|{section.strip()}"
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


# =============================================================================
# CITATION COMPACT (for embedding in cells)
# =============================================================================

@dataclass
class CitationCompact:
    """
    Compact citation format for embedding in cells.

    Contains only the essential fields needed for the audit trail.
    """
    authority: str
    section: str
    hash: str

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary."""
        return {
            "authority": self.authority,
            "section": self.section,
            "hash": self.hash,
        }

    @classmethod
    def from_policy_citation(cls, citation: PolicyCitation) -> 'CitationCompact':
        """Create compact version from full citation."""
        return cls(
            authority=citation.authority,
            section=citation.section,
            hash=citation.citation_hash,
        )


# =============================================================================
# CITATION REGISTRY
# =============================================================================

@dataclass
class CitationQuality:
    """Quality metrics for citation coverage."""
    total_signals: int = 0
    signals_with_citations: int = 0
    total_citations: int = 0
    coverage_ratio: Decimal = Decimal("0.00")
    missing_signals: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_signals": self.total_signals,
            "signals_with_citations": self.signals_with_citations,
            "total_citations": self.total_citations,
            "coverage_ratio": str(self.coverage_ratio),
            "missing_signals": self.missing_signals,
        }


class CitationRegistry:
    """
    Registry for managing policy citations.

    Maps signal/mitigation codes to their regulatory citations.
    Computes citation quality metrics for reports.
    """

    def __init__(self):
        self._signal_citations: Dict[str, List[PolicyCitation]] = {}
        self._mitigation_citations: Dict[str, List[PolicyCitation]] = {}
        self._all_citations: Dict[str, PolicyCitation] = {}  # by hash

    def register_signal_citation(
        self,
        signal_code: str,
        citation: PolicyCitation
    ) -> None:
        """Register a citation for a signal."""
        if signal_code not in self._signal_citations:
            self._signal_citations[signal_code] = []
        self._signal_citations[signal_code].append(citation)
        self._all_citations[citation.citation_hash] = citation

    def register_mitigation_citation(
        self,
        mitigation_code: str,
        citation: PolicyCitation
    ) -> None:
        """Register a citation for a mitigation."""
        if mitigation_code not in self._mitigation_citations:
            self._mitigation_citations[mitigation_code] = []
        self._mitigation_citations[mitigation_code].append(citation)
        self._all_citations[citation.citation_hash] = citation

    def get_citations_for_signal(self, signal_code: str) -> List[PolicyCitation]:
        """Get all citations for a signal."""
        return self._signal_citations.get(signal_code, [])

    def get_citations_for_mitigation(self, mitigation_code: str) -> List[PolicyCitation]:
        """Get all citations for a mitigation."""
        return self._mitigation_citations.get(mitigation_code, [])

    def get_citation_by_hash(self, citation_hash: str) -> Optional[PolicyCitation]:
        """Look up citation by its hash."""
        return self._all_citations.get(citation_hash)

    def get_compact_citations_for_signal(
        self,
        signal_code: str
    ) -> List[CitationCompact]:
        """Get compact citations for embedding in cells."""
        return [
            CitationCompact.from_policy_citation(c)
            for c in self.get_citations_for_signal(signal_code)
        ]

    def compute_citation_quality(
        self,
        signal_codes: List[str]
    ) -> CitationQuality:
        """
        Compute citation quality metrics.

        Args:
            signal_codes: List of signal codes that fired

        Returns:
            CitationQuality with coverage metrics
        """
        signals_with_citations = 0
        total_citations = 0
        missing = []

        for code in signal_codes:
            citations = self.get_citations_for_signal(code)
            if citations:
                signals_with_citations += 1
                total_citations += len(citations)
            else:
                missing.append(code)

        total_signals = len(signal_codes)
        coverage = Decimal("0.00")
        if total_signals > 0:
            coverage = Decimal(str(signals_with_citations)) / Decimal(str(total_signals))
            coverage = coverage.quantize(Decimal("0.01"))

        return CitationQuality(
            total_signals=total_signals,
            signals_with_citations=signals_with_citations,
            total_citations=total_citations,
            coverage_ratio=coverage,
            missing_signals=missing,
        )

    def all_signal_codes(self) -> Set[str]:
        """Get all registered signal codes."""
        return set(self._signal_citations.keys())

    def all_mitigation_codes(self) -> Set[str]:
        """Get all registered mitigation codes."""
        return set(self._mitigation_citations.keys())

    def total_citations(self) -> int:
        """Get total number of unique citations."""
        return len(self._all_citations)


# =============================================================================
# PACK INTEGRATION HELPERS
# =============================================================================

def build_registry_from_pack(pack_data: Dict[str, Any]) -> CitationRegistry:
    """
    Build a CitationRegistry from pack YAML data.

    Expects signals to have policy_refs in the enhanced format:
    policy_refs:
      - authority: FINTRAC
        document: "PCMLTFR"
        section: "s. 12"
        url: "https://..."

    Or simple format (backwards compatible):
    policy_ref: PCMLTFR s. 12
    """
    registry = CitationRegistry()

    # Process signals
    for signal in pack_data.get("signals", []):
        code = signal.get("code", "")
        if not code:
            continue

        # Check for enhanced policy_refs format
        policy_refs = signal.get("policy_refs", [])
        if policy_refs and isinstance(policy_refs, list):
            for ref in policy_refs:
                if isinstance(ref, dict):
                    citation = PolicyCitation(
                        authority=ref.get("authority", ""),
                        document=ref.get("document", ""),
                        section=ref.get("section", ""),
                        url=ref.get("url"),
                    )
                    registry.register_signal_citation(code, citation)

        # Fall back to simple policy_ref
        elif signal.get("policy_ref"):
            simple_ref = signal["policy_ref"]
            # Parse simple format like "PCMLTFR s. 12"
            parts = simple_ref.split(" ", 1)
            authority = parts[0] if parts else simple_ref
            section = parts[1] if len(parts) > 1 else simple_ref

            citation = PolicyCitation(
                authority=authority,
                document=authority,
                section=section,
            )
            registry.register_signal_citation(code, citation)

    # Process mitigations
    for mitigation in pack_data.get("mitigations", []):
        code = mitigation.get("code", "")
        if not code:
            continue

        # Check for enhanced policy_refs format
        policy_refs = mitigation.get("policy_refs", [])
        if policy_refs and isinstance(policy_refs, list):
            for ref in policy_refs:
                if isinstance(ref, dict):
                    citation = PolicyCitation(
                        authority=ref.get("authority", ""),
                        document=ref.get("document", ""),
                        section=ref.get("section", ""),
                        url=ref.get("url"),
                    )
                    registry.register_mitigation_citation(code, citation)

        # Fall back to simple policy_ref
        elif mitigation.get("policy_ref"):
            simple_ref = mitigation["policy_ref"]
            parts = simple_ref.split(" ", 1)
            authority = parts[0] if parts else simple_ref
            section = parts[1] if len(parts) > 1 else simple_ref

            citation = PolicyCitation(
                authority=authority,
                document=authority,
                section=section,
            )
            registry.register_mitigation_citation(code, citation)

    return registry


# =============================================================================
# REPORT SECTION HELPERS
# =============================================================================

def format_citation_for_report(citation: PolicyCitation, index: int = 1) -> List[str]:
    """
    Format a single citation for report output.

    Returns list of lines.
    """
    lines = [
        f"{index}. {citation.authority}",
        f"   Section: {citation.section}",
    ]
    if citation.document and citation.document != citation.authority:
        lines.insert(1, f"   Document: {citation.document}")
    lines.append(f"   SHA256: {citation.short_hash}...")
    return lines


def format_citations_section(
    registry: CitationRegistry,
    signal_codes: List[str],
    line_width: int = 72
) -> List[str]:
    """
    Format the policy citations section for a report.

    Returns list of lines ready for output.
    """
    lines = []
    lines.append("=" * line_width)
    lines.append("POLICY CITATIONS")
    lines.append("=" * line_width)

    for code in sorted(signal_codes):
        citations = registry.get_citations_for_signal(code)
        if citations:
            lines.append(f"\nSignal: {code} ({len(citations)} citation{'s' if len(citations) > 1 else ''})")
            lines.append("-" * line_width)
            for i, citation in enumerate(citations, 1):
                lines.extend(format_citation_for_report(citation, i))
                lines.append("")

    return lines


def format_citation_quality_section(
    quality: CitationQuality,
    line_width: int = 72
) -> List[str]:
    """
    Format the citation quality summary section.

    Returns list of lines.
    """
    lines = []
    lines.append("=" * line_width)
    lines.append("CITATION QUALITY SUMMARY")
    lines.append("=" * line_width)

    coverage_pct = int(quality.coverage_ratio * 100)
    lines.append(f"Total Citations:    {quality.total_citations}")
    lines.append(f"Signals Covered:    {quality.signals_with_citations}/{quality.total_signals}")
    lines.append(f"Citation Quality:   {coverage_pct}%")

    if quality.missing_signals:
        lines.append("")
        lines.append("Signals Without Citations:")
        for code in quality.missing_signals:
            lines.append(f"  - {code}")

    lines.append("")
    return lines


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Exceptions
    'CitationError',
    'CitationNotFoundError',
    # Data classes
    'PolicyCitation',
    'CitationCompact',
    'CitationQuality',
    # Registry
    'CitationRegistry',
    # Helpers
    'compute_citation_hash',
    'build_registry_from_pack',
    'format_citation_for_report',
    'format_citations_section',
    'format_citation_quality_section',
]
