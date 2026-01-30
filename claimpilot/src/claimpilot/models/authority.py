"""
ClaimPilot Authority References

First-class citations for policy wording, regulations, and other authorities.
Every recommendation cites its authorities, making decisions defensible.

Key features:
- Versioned with effective/expiry dates
- Content-hashed for verification
- Supports multiple authority types
- Jurisdiction-aware

This enables "defensible byproduct" - proving which text was relied upon.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from .enums import AuthorityType
from ..canon import text_hash


# =============================================================================
# Authority Reference (Citation)
# =============================================================================

@dataclass
class AuthorityRef:
    """
    A citation to an authority that supports a recommendation.

    Authorities include policy wording, regulations, statutes,
    internal guidelines, case law, and more.

    The content_hash field enables verification that the cited
    text hasn't changed since the recommendation was made.

    Attributes:
        id: Unique identifier for this reference
        authority_type: Type of authority (policy, regulation, etc.)
        title: Human-readable title
        section: Section/paragraph reference
        jurisdiction: Applicable jurisdiction (e.g., "US-CA", "CA-ON")
        source_name: Name of the source document/system
        source_uri: Optional URL/URI to the source
        effective_date: When this authority became effective
        expiry_date: When this authority expires (if known)
        quote_excerpt: Short excerpt of the relevant text
        full_text: Full text of the cited authority (for hashing)
        content_hash: SHA-256 hash of the full text
        created_at: When this reference was created
    """
    id: str
    authority_type: AuthorityType
    title: str
    section: str

    # Source identification
    source_name: str
    source_uri: Optional[str] = None

    # Jurisdiction (required for most authorities)
    jurisdiction: Optional[str] = None

    # Temporal validity
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None

    # The actual text being cited
    quote_excerpt: Optional[str] = None  # Short excerpt for display
    full_text: Optional[str] = None       # Full text for hashing

    # Content hash for verification
    content_hash: Optional[str] = None

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Compute content hash if full_text provided but hash not set."""
        if self.full_text and not self.content_hash:
            self.content_hash = text_hash(self.full_text)

    @classmethod
    def create(
        cls,
        authority_type: AuthorityType,
        title: str,
        section: str,
        source_name: str,
        quote_excerpt: Optional[str] = None,
        full_text: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        effective_date: Optional[date] = None,
        source_uri: Optional[str] = None,
    ) -> AuthorityRef:
        """
        Factory method to create a new AuthorityRef with auto-generated ID.
        """
        return cls(
            id=str(uuid4()),
            authority_type=authority_type,
            title=title,
            section=section,
            source_name=source_name,
            source_uri=source_uri,
            jurisdiction=jurisdiction,
            effective_date=effective_date,
            quote_excerpt=quote_excerpt,
            full_text=full_text,
        )

    def verify_content(self, text: str) -> bool:
        """
        Verify that provided text matches the stored content hash.

        Args:
            text: Text to verify

        Returns:
            True if hash matches, False otherwise
        """
        if not self.content_hash:
            return False
        return text_hash(text) == self.content_hash

    def is_effective_on(self, check_date: date) -> bool:
        """
        Check if this authority is effective on a given date.

        Args:
            check_date: Date to check

        Returns:
            True if authority is effective, False otherwise
        """
        if self.effective_date and check_date < self.effective_date:
            return False
        if self.expiry_date and check_date > self.expiry_date:
            return False
        return True

    @property
    def is_currently_effective(self) -> bool:
        """Check if authority is currently effective."""
        return self.is_effective_on(date.today())

    @property
    def short_citation(self) -> str:
        """Generate a short citation string for display."""
        parts = [self.title]
        if self.section:
            parts.append(f"§{self.section}")
        return ", ".join(parts)

    @property
    def full_citation(self) -> str:
        """Generate a full citation string."""
        parts = [self.title]
        if self.section:
            parts.append(f"Section {self.section}")
        if self.source_name:
            parts.append(f"({self.source_name})")
        if self.effective_date:
            parts.append(f"[eff. {self.effective_date.isoformat()}]")
        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        result: dict[str, Any] = {
            "id": self.id,
            "authority_type": self.authority_type.value,
            "title": self.title,
            "section": self.section,
            "source_name": self.source_name,
        }
        if self.source_uri:
            result["source_uri"] = self.source_uri
        if self.jurisdiction:
            result["jurisdiction"] = self.jurisdiction
        if self.effective_date:
            result["effective_date"] = self.effective_date.isoformat()
        if self.expiry_date:
            result["expiry_date"] = self.expiry_date.isoformat()
        if self.quote_excerpt:
            result["quote_excerpt"] = self.quote_excerpt
        if self.content_hash:
            result["content_hash"] = self.content_hash
        return result


# =============================================================================
# Authority Rule (Escalation)
# =============================================================================

@dataclass
class AuthorityRule:
    """
    Defines when a recommendation requires elevated authority.

    Used to route claims to supervisors, managers, SIU, or legal
    based on configurable conditions.

    Attributes:
        id: Unique identifier
        name: Human-readable name
        description: Detailed description of when this rule applies
        trigger_conditions: Condition that triggers escalation
        required_role: Role that must approve (supervisor, manager, etc.)
        authority_ref: Optional citation explaining why escalation is needed
    """
    id: str
    name: str
    description: str
    required_role: str  # "supervisor", "manager", "siu", "legal", etc.

    # The condition is stored as a reference ID or inline
    # (The actual Condition object is resolved at evaluation time)
    trigger_condition_id: Optional[str] = None

    # Optional citation for the rule
    authority_ref: Optional[AuthorityRef] = None

    # Metadata
    priority: int = 0  # Higher priority rules are evaluated first
    enabled: bool = True

    @classmethod
    def create(
        cls,
        name: str,
        description: str,
        required_role: str,
        trigger_condition_id: Optional[str] = None,
        authority_ref: Optional[AuthorityRef] = None,
        priority: int = 0,
    ) -> AuthorityRule:
        """Factory method to create a new AuthorityRule."""
        return cls(
            id=str(uuid4()),
            name=name,
            description=description,
            required_role=required_role,
            trigger_condition_id=trigger_condition_id,
            authority_ref=authority_ref,
            priority=priority,
        )


# =============================================================================
# Authority Registry (Collection)
# =============================================================================

@dataclass
class AuthorityRegistry:
    """
    A registry of authority references for a policy pack.

    Provides lookup by ID and type for efficient citation.
    """
    authorities: dict[str, AuthorityRef] = field(default_factory=dict)

    def add(self, authority: AuthorityRef) -> None:
        """Add an authority to the registry."""
        self.authorities[authority.id] = authority

    def get(self, authority_id: str) -> Optional[AuthorityRef]:
        """Get an authority by ID."""
        return self.authorities.get(authority_id)

    def get_by_type(self, authority_type: AuthorityType) -> list[AuthorityRef]:
        """Get all authorities of a specific type."""
        return [
            a for a in self.authorities.values()
            if a.authority_type == authority_type
        ]

    def get_effective_on(self, check_date: date) -> list[AuthorityRef]:
        """Get all authorities effective on a specific date."""
        return [
            a for a in self.authorities.values()
            if a.is_effective_on(check_date)
        ]

    def find_by_section(self, section_pattern: str) -> list[AuthorityRef]:
        """
        Find authorities by section pattern (case-insensitive contains).
        """
        pattern = section_pattern.lower()
        return [
            a for a in self.authorities.values()
            if pattern in a.section.lower()
        ]

    def __len__(self) -> int:
        return len(self.authorities)

    def __iter__(self):
        return iter(self.authorities.values())
