"""
DecisionGraph Precedent System: Judgment Cell Module

This module implements the JUDGMENT cell payload schema for storing finalized
decisions as precedents in the DecisionGraph chain.

Key components:
- JudgmentPayload: The structured payload for JUDGMENT cells
- create_judgment_cell(): Creates a JUDGMENT cell from a payload
- parse_judgment_payload(): Extracts payload from a JUDGMENT cell
- validate_judgment_payload(): Schema validation for JUDGMENT payloads
- compute_case_id_hash(): Privacy-preserving hash of case ID

Design Principles:
- Privacy-preserving: case_id is hashed, precedent_id is random UUID
- Self-contained: Anchor facts included for matching without chain traversal
- Deterministic: All hashing uses canonical JSON (RFC 8785)
- Bitemporal: system_time comes from cell header (not payload)

v2.0 CHANGES:
- Initial implementation of JUDGMENT cell payload
- Supports precedent storage for decision consistency

Core Principle: "Precedent retrieval and scoring remain deterministic and auditable."
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, TYPE_CHECKING
from uuid import uuid4

from .cell import (
    CellType,
    DecisionCell,
    Evidence,
    Fact,
    Header,
    LogicAnchor,
    Proof,
    SourceQuality,
    HASH_SCHEME_CANONICAL,
    get_current_timestamp,
    validate_namespace,
    validate_timestamp,
)
from .canon import canonical_json_bytes, validate_canonical_safe

if TYPE_CHECKING:
    from .chain import Chain


# =============================================================================
# Constants
# =============================================================================

JUDGMENT_RULE_ID = "judgment:precedent:v1"
JUDGMENT_RULE_HASH = hashlib.sha256(b"judgment:precedent:v1").hexdigest()
JUDGMENT_INTERPRETER = "precedent:v1"


# =============================================================================
# Exceptions
# =============================================================================

class JudgmentPayloadError(Exception):
    """Base exception for JUDGMENT payload errors."""
    pass


class JudgmentValidationError(JudgmentPayloadError):
    """Raised when JUDGMENT payload validation fails."""
    pass


class JudgmentCreationError(JudgmentPayloadError):
    """Raised when JUDGMENT cell creation fails."""
    pass


# =============================================================================
# Anchor Fact
# =============================================================================

@dataclass
class AnchorFact:
    """
    A self-contained fact for precedent matching.

    Anchor facts are stored directly in the JUDGMENT payload to enable
    matching without requiring chain traversal.

    Attributes:
        field_id: Stable identifier for the fact field (e.g., "driver.rideshare_app_active")
        value: The fact value (must be JSON-serializable, no floats)
        label: Human-readable label for display
    """
    field_id: str
    value: Any  # Must be JSON-serializable (no floats)
    label: str

    def __post_init__(self) -> None:
        """Validate anchor fact on construction."""
        if not self.field_id:
            raise JudgmentValidationError("field_id cannot be empty")
        if not self.label:
            raise JudgmentValidationError("label cannot be empty")
        # Validate value is canonical-safe (no floats)
        try:
            validate_canonical_safe({"value": self.value}, "anchor_fact")
        except Exception as e:
            raise JudgmentValidationError(f"Invalid anchor fact value: {e}")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "field_id": self.field_id,
            "value": self.value,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnchorFact:
        """Create from dictionary."""
        return cls(
            field_id=data["field_id"],
            value=data["value"],
            label=data["label"],
        )


# =============================================================================
# Judgment Payload
# =============================================================================

@dataclass
class JudgmentPayload:
    """
    The payload for a JUDGMENT cell.

    JUDGMENT cells store finalized decisions as precedents for future
    consistency checking and confidence scoring.

    Privacy Design:
    - precedent_id: Random UUID (NOT case_id) for external reference
    - case_id_hash: SHA256(salt + case_id) for privacy-preserving lookup
    - anchor_facts: Self-contained facts for matching (no PII)

    Matching Design:
    - fingerprint_hash: SHA256(salt + banded_facts) for Tier 0 exact matching
    - exclusion_codes: For Tier 0.5/1 code-based matching
    - outcome_code: For same-outcome filtering

    Attributes:
        precedent_id: Random UUID for external reference
        case_id_hash: SHA256(salt + case_id) for privacy-preserving lookup
        jurisdiction_code: Jurisdiction code (e.g., "CA-ON", "CA-QC")

        fingerprint_hash: SHA256(salt + banded_facts) for exact matching
        fingerprint_schema_id: Schema identifier (e.g., "claimpilot:oap1:auto:v1")

        exclusion_codes: List of exclusion clause codes (e.g., ["4.2.1", "4.3.3"])
        reason_codes: List of reason codes (e.g., ["RC-COMMERCIAL-USE"])
        reason_code_registry_id: Registry identifier for reason codes
        outcome_code: Decision outcome (pay, deny, partial, escalate)
        certainty: Decision certainty level (high, medium, low)

        anchor_facts: Self-contained facts for matching

        policy_pack_hash: Hash of the policy pack used
        policy_pack_id: Policy pack identifier
        policy_version: Policy version

        decision_level: Authority level (adjuster, manager, tribunal, court)
        decided_at: When the decision was made (ISO 8601)
        decided_by_role: Role of the decider (never name)

        appealed: Whether the decision was appealed
        appeal_outcome: Outcome if appealed (upheld, overturned, settled, pending)
        appeal_decided_at: When appeal was decided
        appeal_level: Appeal authority level

        source_type: How this precedent was created
        scenario_code: Scenario identifier for audit/analytics
        seed_category: Seed category when source_type is seed/seeded
        outcome_notable: Notable outcome marker (boundary_case, landmark, overturned)

        authority_hashes: Hashes of policy wording cited
    """
    # Identity (privacy-preserving)
    precedent_id: str
    case_id_hash: str
    jurisdiction_code: str

    # Fingerprint
    fingerprint_hash: str
    fingerprint_schema_id: str

    # Decision codes
    exclusion_codes: list[str]
    reason_codes: list[str]
    reason_code_registry_id: str
    outcome_code: str
    certainty: str

    # Self-contained anchor facts
    anchor_facts: list[AnchorFact]

    # Policy context
    policy_pack_hash: str
    policy_pack_id: str
    policy_version: str

    # Authority
    decision_level: str
    decided_at: str
    decided_by_role: str

    # Appeals
    appealed: bool = False
    appeal_outcome: Optional[str] = None
    appeal_decided_at: Optional[str] = None
    appeal_level: Optional[str] = None

    # Metadata
    source_type: str = "system_generated"
    scenario_code: Optional[str] = None
    seed_category: Optional[str] = None
    outcome_notable: Optional[str] = None

    # Provenance
    authority_hashes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate payload on construction."""
        self._validate()

    def _validate(self) -> None:
        """Validate the payload fields."""
        # Validate required string fields are not empty
        required_strings = [
            ("precedent_id", self.precedent_id),
            ("case_id_hash", self.case_id_hash),
            ("jurisdiction_code", self.jurisdiction_code),
            ("fingerprint_hash", self.fingerprint_hash),
            ("fingerprint_schema_id", self.fingerprint_schema_id),
            ("reason_code_registry_id", self.reason_code_registry_id),
            ("outcome_code", self.outcome_code),
            ("certainty", self.certainty),
            ("policy_pack_hash", self.policy_pack_hash),
            ("policy_pack_id", self.policy_pack_id),
            ("policy_version", self.policy_version),
            ("decision_level", self.decision_level),
            ("decided_at", self.decided_at),
            ("decided_by_role", self.decided_by_role),
        ]
        for name, value in required_strings:
            if not value:
                raise JudgmentValidationError(f"{name} cannot be empty")

        # Validate outcome_code
        valid_outcomes = {"pay", "deny", "partial", "escalate"}
        if self.outcome_code not in valid_outcomes:
            raise JudgmentValidationError(
                f"Invalid outcome_code '{self.outcome_code}'. "
                f"Must be one of: {valid_outcomes}"
            )

        # Validate certainty
        valid_certainties = {"high", "medium", "low"}
        if self.certainty not in valid_certainties:
            raise JudgmentValidationError(
                f"Invalid certainty '{self.certainty}'. "
                f"Must be one of: {valid_certainties}"
            )

        # Validate decision_level
        valid_levels = {"adjuster", "manager", "tribunal", "court"}
        if self.decision_level not in valid_levels:
            raise JudgmentValidationError(
                f"Invalid decision_level '{self.decision_level}'. "
                f"Must be one of: {valid_levels}"
            )

        # Validate source_type
        valid_sources = {
            "seed",
            "seeded",
            "system_generated",
            "prod",
            "byoc",
            "imported",
            "tribunal",
        }
        if self.source_type not in valid_sources:
            raise JudgmentValidationError(
                f"Invalid source_type '{self.source_type}'. "
                f"Must be one of: {valid_sources}"
            )

        if self.scenario_code is not None and not self.scenario_code:
            raise JudgmentValidationError("scenario_code cannot be empty")

        if self.seed_category is not None and not self.seed_category:
            raise JudgmentValidationError("seed_category cannot be empty")

        # Validate timestamp format
        if not validate_timestamp(self.decided_at):
            raise JudgmentValidationError(
                f"Invalid decided_at timestamp format: '{self.decided_at}'. "
                f"Must be ISO 8601 with timezone."
            )

        # Validate appeal fields consistency
        if self.appealed:
            valid_appeal_outcomes = {"upheld", "overturned", "settled", "pending"}
            if self.appeal_outcome and self.appeal_outcome not in valid_appeal_outcomes:
                raise JudgmentValidationError(
                    f"Invalid appeal_outcome '{self.appeal_outcome}'. "
                    f"Must be one of: {valid_appeal_outcomes}"
                )
            if self.appeal_decided_at and not validate_timestamp(self.appeal_decided_at):
                raise JudgmentValidationError(
                    f"Invalid appeal_decided_at timestamp format: '{self.appeal_decided_at}'"
                )

        # Validate outcome_notable if provided
        if self.outcome_notable:
            valid_notable = {"boundary_case", "landmark", "overturned"}
            if self.outcome_notable not in valid_notable:
                raise JudgmentValidationError(
                    f"Invalid outcome_notable '{self.outcome_notable}'. "
                    f"Must be one of: {valid_notable}"
                )

        # Validate hashes are 64-character hex strings
        for name, value in [
            ("case_id_hash", self.case_id_hash),
            ("fingerprint_hash", self.fingerprint_hash),
            ("policy_pack_hash", self.policy_pack_hash),
        ]:
            if len(value) != 64 or not all(c in "0123456789abcdef" for c in value):
                raise JudgmentValidationError(
                    f"Invalid {name}: must be 64-character lowercase hex string"
                )

        for i, auth_hash in enumerate(self.authority_hashes):
            if len(auth_hash) != 64 or not all(c in "0123456789abcdef" for c in auth_hash):
                raise JudgmentValidationError(
                    f"Invalid authority_hashes[{i}]: must be 64-character lowercase hex string"
                )

    @classmethod
    def create(
        cls,
        case_id_hash: str,
        jurisdiction_code: str,
        fingerprint_hash: str,
        fingerprint_schema_id: str,
        exclusion_codes: list[str],
        reason_codes: list[str],
        reason_code_registry_id: str,
        outcome_code: str,
        certainty: str,
        anchor_facts: list[AnchorFact],
        policy_pack_hash: str,
        policy_pack_id: str,
        policy_version: str,
        decision_level: str,
        decided_at: str,
        decided_by_role: str,
        **kwargs: Any,
    ) -> JudgmentPayload:
        """
        Factory method to create a new JudgmentPayload.

        Generates a random precedent_id automatically.
        """
        return cls(
            precedent_id=str(uuid4()),
            case_id_hash=case_id_hash,
            jurisdiction_code=jurisdiction_code,
            fingerprint_hash=fingerprint_hash,
            fingerprint_schema_id=fingerprint_schema_id,
            exclusion_codes=exclusion_codes,
            reason_codes=reason_codes,
            reason_code_registry_id=reason_code_registry_id,
            outcome_code=outcome_code,
            certainty=certainty,
            anchor_facts=anchor_facts,
            policy_pack_hash=policy_pack_hash,
            policy_pack_id=policy_pack_id,
            policy_version=policy_version,
            decision_level=decision_level,
            decided_at=decided_at,
            decided_by_role=decided_by_role,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for cell payload."""
        result: dict[str, Any] = {
            "precedent_id": self.precedent_id,
            "case_id_hash": self.case_id_hash,
            "jurisdiction_code": self.jurisdiction_code,
            "fingerprint_hash": self.fingerprint_hash,
            "fingerprint_schema_id": self.fingerprint_schema_id,
            "exclusion_codes": self.exclusion_codes,
            "reason_codes": self.reason_codes,
            "reason_code_registry_id": self.reason_code_registry_id,
            "outcome_code": self.outcome_code,
            "certainty": self.certainty,
            "anchor_facts": [af.to_dict() for af in self.anchor_facts],
            "policy_pack_hash": self.policy_pack_hash,
            "policy_pack_id": self.policy_pack_id,
            "policy_version": self.policy_version,
            "decision_level": self.decision_level,
            "decided_at": self.decided_at,
            "decided_by_role": self.decided_by_role,
            "appealed": self.appealed,
            "source_type": self.source_type,
            "scenario_code": self.scenario_code,
            "seed_category": self.seed_category,
            "authority_hashes": self.authority_hashes,
        }

        # Include optional fields only if set
        if self.appeal_outcome is not None:
            result["appeal_outcome"] = self.appeal_outcome
        if self.appeal_decided_at is not None:
            result["appeal_decided_at"] = self.appeal_decided_at
        if self.appeal_level is not None:
            result["appeal_level"] = self.appeal_level
        if self.outcome_notable is not None:
            result["outcome_notable"] = self.outcome_notable

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JudgmentPayload:
        """Create from dictionary."""
        anchor_facts = [
            AnchorFact.from_dict(af) for af in data.get("anchor_facts", [])
        ]

        return cls(
            precedent_id=data["precedent_id"],
            case_id_hash=data["case_id_hash"],
            jurisdiction_code=data["jurisdiction_code"],
            fingerprint_hash=data["fingerprint_hash"],
            fingerprint_schema_id=data["fingerprint_schema_id"],
            exclusion_codes=data.get("exclusion_codes", []),
            reason_codes=data.get("reason_codes", []),
            reason_code_registry_id=data["reason_code_registry_id"],
            outcome_code=data["outcome_code"],
            certainty=data["certainty"],
            anchor_facts=anchor_facts,
            policy_pack_hash=data["policy_pack_hash"],
            policy_pack_id=data["policy_pack_id"],
            policy_version=data["policy_version"],
            decision_level=data["decision_level"],
            decided_at=data["decided_at"],
            decided_by_role=data["decided_by_role"],
            appealed=data.get("appealed", False),
            appeal_outcome=data.get("appeal_outcome"),
            appeal_decided_at=data.get("appeal_decided_at"),
            appeal_level=data.get("appeal_level"),
            source_type=data.get("source_type", "system_generated"),
            scenario_code=data.get("scenario_code"),
            seed_category=data.get("seed_category"),
            outcome_notable=data.get("outcome_notable"),
            authority_hashes=data.get("authority_hashes", []),
        )


# =============================================================================
# Helper Functions
# =============================================================================

def compute_case_id_hash(case_id: str, salt: str) -> str:
    """
    Compute privacy-preserving hash of case ID.

    Args:
        case_id: The original case ID
        salt: The salt value (stored in namespace config, never in JUDGMENT cells)

    Returns:
        64-character lowercase hex string (SHA-256)
    """
    if not case_id:
        raise JudgmentValidationError("case_id cannot be empty")
    if not salt:
        raise JudgmentValidationError("salt cannot be empty")

    combined = f"{salt}{case_id}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def normalize_scenario_code(code: Optional[str]) -> Optional[str]:
    """Normalize scenario codes into a canonical uppercase identifier."""
    if code is None:
        return None
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in str(code).strip().upper())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or None


def normalize_seed_category(category: Optional[str]) -> Optional[str]:
    """Normalize seed category labels into a canonical lowercase identifier."""
    if category is None:
        return None
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in str(category).strip().lower())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or None


def validate_judgment_payload(payload: JudgmentPayload) -> None:
    """
    Validate a JudgmentPayload for correctness.

    This is called automatically in JudgmentPayload.__post_init__,
    but can be called explicitly for validation.

    Raises:
        JudgmentValidationError: If validation fails
    """
    payload._validate()


# =============================================================================
# Cell Creation/Parsing
# =============================================================================

def create_judgment_cell(
    payload: JudgmentPayload,
    namespace: str,
    graph_id: str,
    prev_cell_hash: str,
    system_time: Optional[str] = None,
    evidence: Optional[list[Evidence]] = None,
    proof: Optional[Proof] = None,
) -> DecisionCell:
    """
    Create a JUDGMENT cell from a JudgmentPayload.

    The cell stores the payload in fact.object as a structured dict.
    Uses canonical hash scheme (RFC 8785) for deterministic cell_id.

    Args:
        payload: The JudgmentPayload to store
        namespace: Namespace for the cell (e.g., "claims.precedents")
        graph_id: The graph ID this cell belongs to
        prev_cell_hash: Hash of the previous cell in the chain
        system_time: When the cell is recorded (defaults to now)
        evidence: Optional evidence list
        proof: Optional proof

    Returns:
        DecisionCell with CellType.JUDGMENT

    Raises:
        JudgmentCreationError: If cell creation fails
    """
    # Validate namespace
    if not validate_namespace(namespace):
        raise JudgmentCreationError(f"Invalid namespace: {namespace}")

    # Default system_time to now
    if system_time is None:
        system_time = get_current_timestamp()

    # Validate payload
    validate_judgment_payload(payload)

    # Create the cell
    try:
        header = Header(
            version="2.0",
            graph_id=graph_id,
            cell_type=CellType.JUDGMENT,
            system_time=system_time,
            prev_cell_hash=prev_cell_hash,
            hash_scheme=HASH_SCHEME_CANONICAL,
        )

        fact = Fact(
            namespace=namespace,
            subject=f"judgment:{payload.precedent_id}",
            predicate="precedent_recorded",
            object=payload.to_dict(),
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED,
        )

        logic_anchor = LogicAnchor(
            rule_id=JUDGMENT_RULE_ID,
            rule_logic_hash=JUDGMENT_RULE_HASH,
            interpreter=JUDGMENT_INTERPRETER,
        )

        cell = DecisionCell(
            header=header,
            fact=fact,
            logic_anchor=logic_anchor,
            evidence=evidence or [],
            proof=proof or Proof(),
        )

        return cell

    except Exception as e:
        raise JudgmentCreationError(f"Failed to create JUDGMENT cell: {e}")


def parse_judgment_payload(cell: DecisionCell) -> JudgmentPayload:
    """
    Extract JudgmentPayload from a JUDGMENT cell.

    Args:
        cell: A DecisionCell with CellType.JUDGMENT

    Returns:
        JudgmentPayload extracted from the cell

    Raises:
        JudgmentPayloadError: If cell is not a valid JUDGMENT cell
    """
    if cell.header.cell_type != CellType.JUDGMENT:
        raise JudgmentPayloadError(
            f"Expected JUDGMENT cell, got {cell.header.cell_type.value}"
        )

    if not isinstance(cell.fact.object, dict):
        raise JudgmentPayloadError(
            f"Expected dict payload in JUDGMENT cell, got {type(cell.fact.object).__name__}"
        )

    try:
        return JudgmentPayload.from_dict(cell.fact.object)
    except Exception as e:
        raise JudgmentPayloadError(f"Failed to parse JUDGMENT payload: {e}")


def is_judgment_cell(cell: DecisionCell) -> bool:
    """Check if a cell is a JUDGMENT cell."""
    return cell.header.cell_type == CellType.JUDGMENT


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Exceptions
    "JudgmentPayloadError",
    "JudgmentValidationError",
    "JudgmentCreationError",

    # Data classes
    "AnchorFact",
    "JudgmentPayload",

    # Functions
    "compute_case_id_hash",
    "validate_judgment_payload",
    "create_judgment_cell",
    "parse_judgment_payload",
    "is_judgment_cell",

    # Constants
    "JUDGMENT_RULE_ID",
    "JUDGMENT_RULE_HASH",
    "JUDGMENT_INTERPRETER",
]
