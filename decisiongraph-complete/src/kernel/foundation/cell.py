"""
DecisionGraph Core: Cell Module (v1.3 → v2.0 Universal Base)

This module implements the Decision-Cell, the atomic DNA of DecisionGraph.
Every cell is a cryptographically sealed packet with:
- Header (metadata + chain link + graph binding)
- Fact (the what) - with namespace and bitemporal semantics
- Logic Anchor (the why) - with canonicalized hashing
- Proof (verification) - with key references

CHANGES IN v1.3:
- Added graph_id to bind cells to specific graph instance
- Renamed timestamp → system_time (clear bitemporal semantics)
- Added signer_key_id for future cryptographic verification
- Strict namespace validation with regex
- Canonicalized rule hashing (whitespace-insensitive)
- valid_to can be None (means "forever")

CHANGES IN v2.0:
- Fact.object can be structured (dict/list) with canonical scheme enforcement
- Added CellTypes: SIGNAL, MITIGATION, SCORE, VERDICT, JUSTIFICATION,
  POLICY_REF, POLICY_CITATION, REPORT_RUN, JUDGMENT
- Legacy hash_scheme only supports string objects

Core Principle: Namespace Isolation via Cryptographic Bridges
"""

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any, Union


class CellType(str, Enum):
    """Valid cell types in DecisionGraph"""
    # Core types (v1.0)
    GENESIS = "genesis"
    FACT = "fact"
    RULE = "rule"
    DECISION = "decision"
    EVIDENCE = "evidence"
    OVERRIDE = "override"
    # Namespace types (v1.3)
    ACCESS_RULE = "access_rule"
    BRIDGE_RULE = "bridge_rule"
    NAMESPACE_DEF = "namespace_def"
    # Policy types (v1.5)
    POLICY_HEAD = "policy_head"
    # Reasoning output types (v2.0)
    SIGNAL = "signal"
    MITIGATION = "mitigation"
    SCORE = "score"
    VERDICT = "verdict"
    # Audit/justification types (v2.0)
    JUSTIFICATION = "justification"
    POLICY_REF = "policy_ref"
    POLICY_CITATION = "policy_citation"
    REPORT_RUN = "report_run"
    JUDGMENT = "judgment"


class SourceQuality(str, Enum):
    """Source quality levels - affects conflict resolution"""
    VERIFIED = "verified"
    SELF_REPORTED = "self_reported"
    INFERRED = "inferred"


class SensitivityLevel(str, Enum):
    """Data sensitivity levels for namespace metadata"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


# The null hash - only valid for Genesis cell
NULL_HASH = "0" * 64

# Namespace validation: lowercase alphanumeric, underscores, dots for hierarchy
# Must start with letter, segments separated by dots
# Examples: "corp", "corp.hr", "acme.sales.discounts"
NAMESPACE_SEGMENT_PATTERN = re.compile(r'^[a-z][a-z0-9_]{0,63}$')
NAMESPACE_PATTERN = re.compile(r'^[a-z][a-z0-9_]{0,63}(\.[a-z][a-z0-9_]{0,63})*$')

# Root namespace pattern: single segment, no dots
ROOT_NAMESPACE_PATTERN = re.compile(r'^[a-z][a-z0-9_]{1,63}$')

# ISO 8601 timestamp pattern (basic validation)
ISO_TIMESTAMP_PATTERN = re.compile(
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$'
)


def validate_namespace(namespace: str) -> bool:
    """
    Validate that a namespace follows the hierarchical format.
    
    Rules:
    - Lowercase letters, digits, underscores only
    - Must start with a letter
    - Segments separated by dots
    - Each segment max 64 characters
    - No empty segments, no leading/trailing dots
    
    Valid: "corp", "corp.hr", "acme.sales.discounts", "my_company.dept_1"
    Invalid: "", ".corp", "corp.", "corp..hr", "Corp.HR", "123corp", "corp/hr"
    """
    if not namespace:
        return False
    return bool(NAMESPACE_PATTERN.match(namespace))


def validate_root_namespace(namespace: str) -> bool:
    """
    Validate that a namespace is a valid root (no dots).
    
    Valid: "corp", "acme", "my_company"
    Invalid: "corp.hr", ".corp", "Corp"
    """
    if not namespace:
        return False
    return bool(ROOT_NAMESPACE_PATTERN.match(namespace))


def validate_timestamp(ts: str) -> bool:
    """
    Validate that a timestamp is ISO 8601 format with timezone.
    
    Valid: "2026-01-26T15:00:00Z", "2026-01-26T15:00:00.123456+00:00"
    Invalid: "2026-01-26", "15:00:00", "Jan 26, 2026"
    """
    if not ts:
        return False
    return bool(ISO_TIMESTAMP_PATTERN.match(ts))


def get_parent_namespace(namespace: str) -> Optional[str]:
    """
    Get the parent namespace.
    
    "corp.hr.compensation" -> "corp.hr"
    "corp.hr" -> "corp"
    "corp" -> None
    """
    if '.' not in namespace:
        return None
    return namespace.rsplit('.', 1)[0]


def is_namespace_prefix(prefix: str, full: str) -> bool:
    """
    Check if 'prefix' is a prefix of 'full' namespace.
    
    is_namespace_prefix("corp.hr", "corp.hr.compensation") -> True
    is_namespace_prefix("corp.hr", "corp.hr") -> True
    is_namespace_prefix("corp.hr", "corp.sales") -> False
    """
    if prefix == full:
        return True
    return full.startswith(prefix + ".")


def generate_graph_id() -> str:
    """
    Generate a unique graph ID.
    
    Format: "graph:<uuid4>"
    """
    return f"graph:{uuid.uuid4()}"


def canonicalize_rule_content(content: str) -> str:
    """
    Canonicalize rule content before hashing.
    
    This ensures that whitespace differences don't create different hashes.
    
    Operations:
    1. Strip leading/trailing whitespace from each line
    2. Remove empty lines
    3. Normalize line endings to \\n
    4. Strip leading/trailing whitespace from result
    """
    lines = content.split('\n')
    # Strip each line and filter empty
    lines = [line.strip() for line in lines]
    lines = [line for line in lines if line]
    # Join with single newline
    return '\n'.join(lines)


def compute_rule_logic_hash(rule_content: str) -> str:
    """
    Compute the hash of rule logic with canonicalization.
    
    This hash is stored in logic_anchor.rule_logic_hash and
    allows verification that a decision used the correct version
    of a rule.
    
    The content is canonicalized before hashing to ensure
    whitespace differences don't create different hashes.
    """
    canonical = canonicalize_rule_content(rule_content)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def compute_content_id(content: bytes) -> str:
    """
    Compute a Content ID (CID) for evidence.

    Similar to IPFS CID - the content IS the address.
    If content changes, CID changes.
    """
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def compute_policy_hash(promoted_rule_ids: List[str]) -> str:
    """
    Compute deterministic policy_hash from promoted_rule_ids.

    Follows v1.3 canonicalization pattern:
    1. Sort rule IDs (deterministic ordering)
    2. JSON serialize with consistent separators
    3. SHA-256 hash

    Returns:
        64-character hex string (SHA-256 hash)
    """
    sorted_ids = sorted(promoted_rule_ids)
    # Use separators=(',', ':') for compact, deterministic JSON
    canonical_json = json.dumps(sorted_ids, separators=(',', ':'))
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()


_LAST_TIMESTAMP_MS = 0


def get_current_timestamp() -> str:
    """Get current UTC timestamp in ISO-8601 format with Z suffix.

    Ensures monotonic millisecond precision to avoid duplicate timestamps
    within the same process.
    """
    global _LAST_TIMESTAMP_MS
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if now_ms <= _LAST_TIMESTAMP_MS:
        now_ms = _LAST_TIMESTAMP_MS + 1
    _LAST_TIMESTAMP_MS = now_ms
    return datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


# ============================================================================
# HASH SCHEME CONSTANTS
# ============================================================================

# Legacy hash scheme: string concatenation (v1.3 original)
HASH_SCHEME_LEGACY = "legacy:concat:v1"

# Canonical hash scheme: RFC 8785 JSON canonicalization (v2.0+)
HASH_SCHEME_CANONICAL = "canon:rfc8785:v1"

# Default scheme for existing cells without explicit hash_scheme
HASH_SCHEME_DEFAULT = HASH_SCHEME_LEGACY


@dataclass
class Header:
    """
    Cell header containing metadata and chain link.

    v1.3 CHANGES:
    - Added graph_id: binds cell to specific graph instance
    - Renamed timestamp → system_time: when the engine recorded this cell

    v2.0 CHANGES:
    - Added hash_scheme: identity algorithm for cell_id computation
      - None or "legacy:concat:v1": original string-concat method
      - "canon:rfc8785:v1": RFC 8785 canonical JSON method
    """
    version: str
    graph_id: str                    # Binds cell to specific graph
    cell_type: CellType
    system_time: str                 # When engine recorded (not when fact is valid)
    prev_cell_hash: str
    hash_scheme: Optional[str] = None  # Identity algorithm (None = legacy)

    def __post_init__(self):
        # Validate system_time format
        if not validate_timestamp(self.system_time):
            raise ValueError(
                f"Invalid system_time format: '{self.system_time}'. "
                f"Must be ISO 8601 with timezone (e.g., '2026-01-26T15:00:00Z')"
            )
        # Validate hash_scheme if provided
        if self.hash_scheme is not None:
            valid_schemes = (HASH_SCHEME_LEGACY, HASH_SCHEME_CANONICAL)
            if self.hash_scheme not in valid_schemes:
                raise ValueError(
                    f"Invalid hash_scheme: '{self.hash_scheme}'. "
                    f"Must be one of: {valid_schemes}"
                )

    def get_effective_hash_scheme(self) -> str:
        """Return effective hash scheme, defaulting to legacy if None."""
        return self.hash_scheme or HASH_SCHEME_DEFAULT

    def to_dict(self) -> dict:
        result = {
            "version": self.version,
            "graph_id": self.graph_id,
            "cell_type": self.cell_type.value,
            "system_time": self.system_time,
            "prev_cell_hash": self.prev_cell_hash
        }
        # Only include hash_scheme if explicitly set (backward compat)
        if self.hash_scheme is not None:
            result["hash_scheme"] = self.hash_scheme
        return result


@dataclass
class Fact:
    """
    The fact being recorded - Namespace + Subject-Predicate-Object triple.

    Bitemporal semantics:
    - system_time (in Header): When the engine recorded this fact
    - valid_from/valid_to: When this fact is/was true in the real world

    v1.3 CHANGES:
    - valid_to can be None (means "forever" / open-ended)
    - Stricter namespace validation

    v2.0 CHANGES:
    - object can be structured (dict/list) for rich payloads (signals, scores, etc.)
    - Structured objects REQUIRE hash_scheme="canon:rfc8785:v1" (enforced at cell level)
    - All numeric values in structured payloads must be strings (no floats)
    """
    namespace: str
    subject: str
    predicate: str
    object: Union[str, Dict[str, Any], List[Any]]  # v2.0: structured payloads allowed
    confidence: float  # 0.0 to 1.0
    source_quality: SourceQuality
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None      # None means "forever" (open-ended)

    def __post_init__(self):
        # Validate namespace format
        if not validate_namespace(self.namespace):
            raise ValueError(
                f"Invalid namespace format: '{self.namespace}'. "
                f"Must be lowercase alphanumeric/underscore segments separated by dots. "
                f"Example: 'corp.hr.compensation'"
            )

        # Validate confidence
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")
        if self.confidence == 1.0 and self.source_quality != SourceQuality.VERIFIED:
            raise ValueError("Confidence 1.0 requires source_quality='verified'")

        # Validate timestamps if provided
        if self.valid_from and not validate_timestamp(self.valid_from):
            raise ValueError(f"Invalid valid_from format: '{self.valid_from}'")
        if self.valid_to and not validate_timestamp(self.valid_to):
            raise ValueError(f"Invalid valid_to format: '{self.valid_to}'")

    def has_structured_object(self) -> bool:
        """Check if object is structured (dict or list) vs simple string."""
        return isinstance(self.object, (dict, list))

    def to_dict(self) -> dict:
        return {
            "namespace": self.namespace,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "confidence": self.confidence,
            "source_quality": self.source_quality.value,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to
        }


@dataclass
class LogicAnchor:
    """Links the fact to the rule/law that produced it"""
    rule_id: str
    rule_logic_hash: str
    interpreter: Optional[str] = None  # e.g., "datalog:v2", "dmn:1.3"
    
    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "rule_logic_hash": self.rule_logic_hash,
            "interpreter": self.interpreter
        }


@dataclass
class Evidence:
    """Supporting evidence for a fact"""
    type: str  # "document_blob", "external_verification", "api_response", "approval"
    cid: Optional[str] = None
    source: Optional[str] = None
    payload_hash: Optional[str] = None
    description: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "cid": self.cid,
            "source": self.source,
            "payload_hash": self.payload_hash,
            "description": self.description
        }


@dataclass
class Proof:
    """
    Cryptographic proof of cell integrity.
    
    v1.3 CHANGES:
    - Added signer_key_id: reference to signing key for verification
    - Added signature_required: indicates if signature is mandatory
    """
    signer_id: Optional[str] = None
    signer_key_id: Optional[str] = None  # Reference to signing key
    signature: Optional[str] = None
    merkle_root: Optional[str] = None
    signature_required: bool = False  # If True, signature must be present for valid cell
    
    def to_dict(self) -> dict:
        return {
            "signer_id": self.signer_id,
            "signer_key_id": self.signer_key_id,
            "signature": self.signature,
            "merkle_root": self.merkle_root,
            "signature_required": self.signature_required
        }


@dataclass
class DecisionCell:
    """
    The atomic unit of DecisionGraph (v1.3 → v2.0).

    A cryptographically sealed packet where:
    - cell_id is DERIVED from content (not assigned)
    - Changing ANY field invalidates the cell_id
    - The Logic Anchor binds fact to law
    - graph_id binds cell to specific graph instance

    v1.3 CHANGES:
    - graph_id included in cell_id computation
    - system_time instead of timestamp
    - Canonicalized rule hashing

    v2.0 CHANGES:
    - Structured fact.object (dict/list) requires hash_scheme="canon:rfc8785:v1"
    - Legacy hash_scheme only supports string objects
    """
    header: Header
    fact: Fact
    logic_anchor: LogicAnchor
    evidence: List[Evidence] = field(default_factory=list)
    proof: Proof = field(default_factory=Proof)
    cell_id: str = field(default="", init=False)

    def __post_init__(self):
        """Validate constraints and compute cell_id after initialization."""
        # v2.0: Structured objects require canonical hash scheme
        if self.fact.has_structured_object():
            scheme = self.header.get_effective_hash_scheme()
            if scheme != HASH_SCHEME_CANONICAL:
                raise ValueError(
                    f"Structured fact.object (dict/list) requires "
                    f"hash_scheme='{HASH_SCHEME_CANONICAL}', but got '{scheme}'. "
                    f"Legacy hash_scheme only supports string objects."
                )
            # Validate structured payload is canonical-safe (no floats)
            self._validate_structured_object(self.fact.object, "fact.object")

        self.cell_id = self.compute_cell_id()

    def _validate_structured_object(self, obj: Any, path: str) -> None:
        """
        Validate structured object is canonical-safe.

        Rules:
        - No float values (use string-encoded decimals)
        - All dict keys must be strings
        - Nested structures are recursively validated
        """
        if obj is None or isinstance(obj, (bool, int, str)):
            return

        if isinstance(obj, float):
            raise ValueError(
                f"Float value {obj} at '{path}' not allowed in structured payload. "
                f"Use string-encoded decimal (e.g., '{obj}' as string)."
            )

        if isinstance(obj, dict):
            for key, value in obj.items():
                if not isinstance(key, str):
                    raise ValueError(
                        f"Dict key must be string at '{path}', got {type(key).__name__}"
                    )
                self._validate_structured_object(value, f"{path}.{key}")
            return

        if isinstance(obj, list):
            for i, item in enumerate(obj):
                self._validate_structured_object(item, f"{path}[{i}]")
            return

        raise ValueError(
            f"Unsupported type {type(obj).__name__} at '{path}' in structured payload"
        )
    
    def compute_cell_id(self) -> str:
        """
        THE LOGIC SEAL (v1.3 / v2.0)

        Compute cell_id using SHA-256. Method depends on hash_scheme:

        - legacy:concat:v1 (default): String concatenation of fields
        - canon:rfc8785:v1: RFC 8785 canonical JSON of full cell dict

        The hash_scheme is determined by header.hash_scheme field.
        If not set, defaults to legacy for backward compatibility.

        Formula (legacy):
        cell_id = SHA256(
            header.version +
            header.graph_id +
            header.cell_type +
            header.system_time +
            header.prev_cell_hash +
            fact.namespace +
            fact.subject +
            fact.predicate +
            fact.object +  # Must be string for legacy scheme
            logic_anchor.rule_id +
            logic_anchor.rule_logic_hash
        )

        Formula (canonical):
        cell_id = SHA256(canonical_json_bytes(cell_to_canonical_dict(self)))

        If graph_id changes, cell_id breaks -> cell cannot move between graphs.
        If namespace changes, cell_id breaks -> cell cannot move between namespaces.

        v2.0: Legacy scheme rejects structured objects (dict/list) because
        str(dict) is non-deterministic across Python versions.
        """
        scheme = self.header.get_effective_hash_scheme()

        if scheme == HASH_SCHEME_CANONICAL:
            # RFC 8785 canonical JSON method
            from .canon import cell_to_canonical_dict, canonical_json_bytes
            canonical_dict = cell_to_canonical_dict(self)
            return hashlib.sha256(canonical_json_bytes(canonical_dict)).hexdigest()
        else:
            # Legacy string concatenation method (default)
            # Guard: reject structured objects (dict/list) - they're non-deterministic
            if self.fact.has_structured_object():
                raise TypeError(
                    f"Legacy hash_scheme cannot compute cell_id for structured "
                    f"fact.object ({type(self.fact.object).__name__}). "
                    f"Use hash_scheme='{HASH_SCHEME_CANONICAL}' for dict/list payloads."
                )
            seal_string = (
                self.header.version +
                self.header.graph_id +
                self.header.cell_type.value +
                self.header.system_time +
                self.header.prev_cell_hash +
                self.fact.namespace +
                self.fact.subject +
                self.fact.predicate +
                self.fact.object +  # Guaranteed to be string here
                self.logic_anchor.rule_id +
                self.logic_anchor.rule_logic_hash
            )
            return hashlib.sha256(seal_string.encode('utf-8')).hexdigest()
    
    def verify_integrity(self) -> bool:
        """
        Verify that the cell_id matches the computed hash.
        
        Returns True if cell is valid, False if tampered.
        """
        return self.cell_id == self.compute_cell_id()
    
    def is_genesis(self) -> bool:
        """Check if this is the Genesis cell"""
        return (
            self.header.cell_type == CellType.GENESIS and
            self.header.prev_cell_hash == NULL_HASH
        )
    
    def to_dict(self) -> dict:
        """Convert cell to dictionary for serialization"""
        return {
            "cell_id": self.cell_id,
            "header": self.header.to_dict(),
            "fact": self.fact.to_dict(),
            "logic_anchor": self.logic_anchor.to_dict(),
            "evidence": [e.to_dict() for e in self.evidence],
            "proof": self.proof.to_dict()
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert cell to JSON string"""
        return json.dumps(self.to_dict(), indent=indent)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DecisionCell':
        """Create a cell from dictionary"""
        header = Header(
            version=data["header"]["version"],
            graph_id=data["header"]["graph_id"],
            cell_type=CellType(data["header"]["cell_type"]),
            system_time=data["header"]["system_time"],
            prev_cell_hash=data["header"]["prev_cell_hash"],
            hash_scheme=data["header"].get("hash_scheme")  # None if not present (legacy)
        )
        
        fact = Fact(
            namespace=data["fact"]["namespace"],
            subject=data["fact"]["subject"],
            predicate=data["fact"]["predicate"],
            object=data["fact"]["object"],
            confidence=data["fact"]["confidence"],
            source_quality=SourceQuality(data["fact"]["source_quality"]),
            valid_from=data["fact"].get("valid_from"),
            valid_to=data["fact"].get("valid_to")
        )
        
        logic_anchor = LogicAnchor(
            rule_id=data["logic_anchor"]["rule_id"],
            rule_logic_hash=data["logic_anchor"]["rule_logic_hash"],
            interpreter=data["logic_anchor"].get("interpreter")
        )
        
        evidence = [
            Evidence(
                type=e["type"],
                cid=e.get("cid"),
                source=e.get("source"),
                payload_hash=e.get("payload_hash"),
                description=e.get("description")
            )
            for e in data.get("evidence", [])
        ]
        
        proof = Proof(
            signer_id=data.get("proof", {}).get("signer_id"),
            signer_key_id=data.get("proof", {}).get("signer_key_id"),
            signature=data.get("proof", {}).get("signature"),
            merkle_root=data.get("proof", {}).get("merkle_root")
        )
        
        cell = cls(
            header=header,
            fact=fact,
            logic_anchor=logic_anchor,
            evidence=evidence,
            proof=proof
        )
        
        # Verify the cell_id matches
        if cell.cell_id != data.get("cell_id"):
            raise ValueError(
                f"Cell ID mismatch! Computed: {cell.cell_id}, "
                f"Provided: {data.get('cell_id')}. Cell may be tampered."
            )
        
        return cell


# Export public interface
__all__ = [
    # Enums
    'CellType',
    'SourceQuality',
    'SensitivityLevel',

    # Constants
    'NULL_HASH',
    'NAMESPACE_PATTERN',
    'ROOT_NAMESPACE_PATTERN',
    'HASH_SCHEME_LEGACY',
    'HASH_SCHEME_CANONICAL',
    'HASH_SCHEME_DEFAULT',

    # Data classes
    'Header',
    'Fact',
    'LogicAnchor',
    'Evidence',
    'Proof',
    'DecisionCell',

    # Validation functions
    'validate_namespace',
    'validate_root_namespace',
    'validate_timestamp',

    # Namespace utilities
    'get_parent_namespace',
    'is_namespace_prefix',

    # ID generation
    'generate_graph_id',

    # Hashing utilities
    'canonicalize_rule_content',
    'compute_rule_logic_hash',
    'compute_content_id',
    'compute_policy_hash',

    # Timestamp
    'get_current_timestamp'
]
