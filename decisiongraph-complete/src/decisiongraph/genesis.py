"""
DecisionGraph Core: Genesis Module (v1.3 - Universal Base)

The Genesis Cell is the "Big Bang" of a DecisionGraph instance.
It is the root of the entire universe - every cell traces back to it.

Key properties:
- Only ONE Genesis cell can exist per graph
- prev_cell_hash = NULL_HASH (all zeros)
- cell_type = "genesis"
- namespace = root namespace (no dots)
- Creates the graph_id that ALL subsequent cells must reference
- Cannot be created after other cells exist

IMPORTANT: Uniqueness and "first cell" constraints are enforced by the 
Commit Gate (Chain.append), NOT by verify_genesis(). This module can only
validate a cell's structure, not its position in the chain.

v1.3 CHANGES:
- Generates graph_id to bind all cells
- Complete verify_genesis() with all checks
- Strict root namespace validation
- Canonicalized boot rule hashing (compute_rule_logic_hash canonicalizes internally)
- Bootstrap mode for initial deployment (signature optional)
- graph_id format validation
"""

import re
from typing import Optional, Tuple, List

from .cell import (
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Proof,
    CellType,
    SourceQuality,
    NULL_HASH,
    get_current_timestamp,
    compute_rule_logic_hash,
    generate_graph_id,
    validate_root_namespace,
    validate_timestamp,
    canonicalize_rule_content
)


# ============================================================================
# CONSTANTS
# ============================================================================

# The boot rule - embedded in the system
# NOTE: compute_rule_logic_hash() canonicalizes internally before hashing,
# so whitespace differences won't create different hashes.
GENESIS_RULE = """
-- DecisionGraph Genesis Rule v1.3
-- This rule defines the creation of a new DecisionGraph instance
-- with a unique graph_id and root namespace

CREATE GRAPH:
  WHEN no_cells_exist
  THEN create_genesis_cell
  WITH prev_cell_hash = NULL_HASH
  AND cell_type = "genesis"
  AND graph_id = generate_graph_id()
  AND namespace = root_namespace (no dots, lowercase alphanumeric)
  AND subject = "graph:root"
  AND predicate = "instance_of"
  AND confidence = 1.0
  AND source_quality = "verified"
  AND valid_to = None (open-ended)

TIME MODEL:
  header.system_time = when engine recorded this cell (ISO 8601 UTC)
  fact.valid_from = when fact became true (same as system_time for genesis)
  fact.valid_to = when fact stops being true (None = forever)
"""

# Hash is computed with canonicalization (whitespace-insensitive)
GENESIS_RULE_HASH = compute_rule_logic_hash(GENESIS_RULE)

# Default root namespace
DEFAULT_ROOT_NAMESPACE = "corp"

# Expected schema version for v1.3
SCHEMA_VERSION = "1.3"

# graph_id format: "graph:<uuid-v4>"
GRAPH_ID_PATTERN = re.compile(
    r'^graph:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
    re.IGNORECASE
)


# ============================================================================
# EXCEPTIONS
# ============================================================================

class GenesisError(Exception):
    """Raised when Genesis creation fails"""
    pass


class GenesisValidationError(GenesisError):
    """Raised when Genesis validation fails with detailed check results"""
    def __init__(self, message: str, failed_checks: List[str]):
        super().__init__(message)
        self.failed_checks = failed_checks


# ============================================================================
# VALIDATION HELPERS
# ============================================================================

def validate_graph_id(graph_id: str) -> bool:
    """
    Validate that a graph_id follows the required format.
    
    Format: "graph:<uuid-v4>"
    Example: "graph:a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
    
    This becomes your universal partition key, so format matters.
    """
    if not graph_id:
        return False
    return bool(GRAPH_ID_PATTERN.match(graph_id))


# ============================================================================
# GENESIS CREATION
# ============================================================================

def create_genesis_cell(
    graph_name: str = "UniversalDecisionGraph",
    root_namespace: str = DEFAULT_ROOT_NAMESPACE,
    graph_id: Optional[str] = None,
    creator: Optional[str] = None,
    creator_key_id: Optional[str] = None,
    system_time: Optional[str] = None,
    bootstrap_mode: bool = True
) -> DecisionCell:
    """
    Create the Genesis cell for a new DecisionGraph instance.
    
    This is the "Big Bang" - the root of all cells.
    It establishes:
    - The graph_id that ALL subsequent cells must reference
    - The root namespace for the entire graph
    - The time model (bitemporal: system_time + valid_time)
    
    Args:
        graph_name: Human-readable name for this graph instance
        root_namespace: The root namespace (no dots, e.g., "corp", "acme")
        graph_id: Optional specific graph_id (auto-generated if not provided)
        creator: Optional identifier of who/what created this graph
        creator_key_id: Optional reference to signing key
        system_time: Optional timestamp (defaults to now, must be ISO 8601 UTC)
        bootstrap_mode: If True, signature is not required (initial deployment)
    
    Returns:
        The Genesis DecisionCell
    
    Raises:
        GenesisError: If root_namespace or graph_id is invalid
    
    Note:
        Uniqueness (only one Genesis per graph) is enforced by the Commit Gate
        (Chain.append), not by this function.
    
    Example:
        >>> genesis = create_genesis_cell(
        ...     graph_name="AcmeCorp_v1",
        ...     root_namespace="acme",
        ...     creator="system:initializer"
        ... )
        >>> print(genesis.header.graph_id)
        'graph:a1b2c3d4-...'
    """
    # Validate root namespace
    if not validate_root_namespace(root_namespace):
        raise GenesisError(
            f"Invalid root namespace: '{root_namespace}'. "
            f"Must be lowercase letter followed by alphanumeric/underscore, "
            f"2-64 chars, no dots, no trailing underscores."
        )
    
    # Generate or validate graph_id
    gid = graph_id or generate_graph_id()
    if not validate_graph_id(gid):
        raise GenesisError(
            f"Invalid graph_id format: '{gid}'. "
            f"Must be 'graph:<uuid-v4>' format."
        )
    
    # Use provided system_time or current time
    ts = system_time or get_current_timestamp()
    if not validate_timestamp(ts):
        raise GenesisError(
            f"Invalid system_time format: '{ts}'. "
            f"Must be ISO 8601 with UTC timezone (e.g., '2026-01-26T15:00:00Z')"
        )
    
    # Create the Genesis header
    header = Header(
        version=SCHEMA_VERSION,
        graph_id=gid,
        cell_type=CellType.GENESIS,
        system_time=ts,
        prev_cell_hash=NULL_HASH  # The signature of Genesis - all zeros
    )
    
    # Create the Genesis fact with root namespace
    # Bitemporal: system_time is when recorded, valid_from is when true
    # For Genesis, these are the same. valid_to=None means "forever"
    fact = Fact(
        namespace=root_namespace,
        subject="graph:root",
        predicate="instance_of",
        object=graph_name,
        confidence=1.0,
        source_quality=SourceQuality.VERIFIED,
        valid_from=ts,
        valid_to=None  # Open-ended (forever)
    )
    
    # Create the Logic Anchor pointing to the boot rule
    # Exact match required for Genesis - no variations allowed
    logic_anchor = LogicAnchor(
        rule_id="system:genesis_boot_v1.3",
        rule_logic_hash=GENESIS_RULE_HASH,
        interpreter="system:v1.3"
    )
    
    # Create the proof
    # In bootstrap_mode, signature is optional (for initial deployment)
    # In production, Genesis should be signed by engine_root_key
    proof = Proof(
        signer_id=creator or "system:genesis",
        signer_key_id=creator_key_id,
        signature=None,  # Set by signing layer if bootstrap_mode=False
        merkle_root=None,  # Set when Merkle tree is built
        signature_required=not bootstrap_mode
    )
    
    # Create and return the Genesis cell
    genesis = DecisionCell(
        header=header,
        fact=fact,
        logic_anchor=logic_anchor,
        evidence=[],
        proof=proof
    )
    
    return genesis


# ============================================================================
# GENESIS VERIFICATION
# ============================================================================

def verify_genesis(cell: DecisionCell, strict_signature: bool = False) -> Tuple[bool, List[str]]:
    """
    Verify that a cell is a valid Genesis cell.
    
    IMPORTANT: This function validates the STRUCTURE of a Genesis cell.
    It does NOT enforce:
    - Uniqueness (only one Genesis per graph)
    - Position (Genesis must be first cell)
    - Graph ID binding (all cells must share same graph_id)
    Those constraints are enforced by the Commit Gate (Chain.append).
    
    Complete verification checks (21 total):
    
    HEADER (1-5):
    [1] cell_type == GENESIS
    [2] prev_cell_hash == NULL_HASH
    [3] version == SCHEMA_VERSION
    [4] graph_id is valid format (graph:<uuid-v4>, lowercase)
    [5] system_time is valid ISO 8601 UTC ending with 'Z'
    
    FACT (6-14):
    [6] namespace is valid root (no dots, lowercase alphanumeric)
    [7] subject == "graph:root"
    [8] predicate == "instance_of"
    [9] object (graph_name) is non-empty
    [10] confidence == 1.0
    [11] source_quality == "verified"
    [12] valid_from is valid ISO 8601 UTC ending with 'Z'
    [13] valid_to is None (open-ended)
    [14] valid_from == system_time (Genesis creates moment = record moment)
    
    LOGIC ANCHOR (15-17):
    [15] rule_id == "system:genesis_boot_v1.3" (exact match)
    [16] rule_logic_hash == GENESIS_RULE_HASH
    [17] interpreter == "system:v1.3" (exact match)
    
    STRUCTURE (18):
    [18] evidence == [] (Genesis must be pure, no extra claims)
    
    PROOF (19-21, conditional):
    [19] If strict_signature: signer_key_id is present
    [20] If strict_signature: signature is present
    [21] If NOT strict_signature: signature is None OR signature_required is False
         (prevents bootstrap cell pretending to be signed)
    
    INTEGRITY (22):
    [22] cell_id matches computed hash (tamper detection)
    
    Args:
        cell: The cell to verify
        strict_signature: If True, require signature to be present
    
    Returns:
        Tuple of (is_valid, failed_checks)
        - is_valid: True if all checks pass
        - failed_checks: List of check descriptions that failed (with [N] prefix)
    """
    failed_checks = []
    
    # === HEADER CHECKS (1-5) ===
    
    # [1] Cell type
    if cell.header.cell_type != CellType.GENESIS:
        failed_checks.append(
            f"[1] header.cell_type: expected 'genesis', got '{cell.header.cell_type.value}'"
        )
    
    # [2] prev_cell_hash
    if cell.header.prev_cell_hash != NULL_HASH:
        failed_checks.append(
            f"[2] header.prev_cell_hash: expected NULL_HASH (64 zeros), "
            f"got '{cell.header.prev_cell_hash[:16]}...'"
        )
    
    # [3] Version
    if cell.header.version != SCHEMA_VERSION:
        failed_checks.append(
            f"[3] header.version: expected '{SCHEMA_VERSION}', got '{cell.header.version}'"
        )
    
    # [4] Graph ID format (validates format AND canonical form)
    if not validate_graph_id(cell.header.graph_id):
        failed_checks.append(
            f"[4] header.graph_id: invalid format '{cell.header.graph_id}', "
            f"expected 'graph:<uuid-v4>' in lowercase"
        )
    
    # [5] System time: valid ISO 8601 UTC with Z suffix
    if not _is_valid_utc_timestamp(cell.header.system_time):
        failed_checks.append(
            f"[5] header.system_time: must be ISO 8601 UTC ending with 'Z', "
            f"got '{cell.header.system_time}'"
        )
    
    # === FACT CHECKS (6-14) ===
    
    # [6] Namespace is valid root
    if not validate_root_namespace(cell.fact.namespace):
        failed_checks.append(
            f"[6] fact.namespace: '{cell.fact.namespace}' is not a valid root namespace "
            f"(must be lowercase alphanumeric/underscore, 2-64 chars, no dots)"
        )
    
    # [7] Subject
    if cell.fact.subject != "graph:root":
        failed_checks.append(
            f"[7] fact.subject: expected 'graph:root', got '{cell.fact.subject}'"
        )
    
    # [8] Predicate
    if cell.fact.predicate != "instance_of":
        failed_checks.append(
            f"[8] fact.predicate: expected 'instance_of', got '{cell.fact.predicate}'"
        )
    
    # [9] Object (graph_name)
    if not cell.fact.object or not cell.fact.object.strip():
        failed_checks.append("[9] fact.object: graph_name cannot be empty")
    
    # [10] Confidence
    if cell.fact.confidence != 1.0:
        failed_checks.append(
            f"[10] fact.confidence: expected 1.0, got {cell.fact.confidence}"
        )
    
    # [11] Source quality
    if cell.fact.source_quality != SourceQuality.VERIFIED:
        failed_checks.append(
            f"[11] fact.source_quality: expected 'verified', got '{cell.fact.source_quality.value}'"
        )
    
    # [12] valid_from: valid ISO 8601 UTC with Z suffix
    if not _is_valid_utc_timestamp(cell.fact.valid_from):
        failed_checks.append(
            f"[12] fact.valid_from: must be ISO 8601 UTC ending with 'Z', "
            f"got '{cell.fact.valid_from}'"
        )
    
    # [13] valid_to must be None (open-ended)
    if cell.fact.valid_to is not None:
        failed_checks.append(
            f"[13] fact.valid_to: expected None (open-ended), got '{cell.fact.valid_to}'"
        )
    
    # [14] valid_from should match system_time (for Genesis, creation = record)
    if cell.fact.valid_from and cell.header.system_time:
        if cell.fact.valid_from != cell.header.system_time:
            failed_checks.append(
                f"[14] fact.valid_from: must match system_time for Genesis. "
                f"valid_from='{cell.fact.valid_from}', system_time='{cell.header.system_time}'"
            )
    
    # === LOGIC ANCHOR CHECKS (15-17) ===
    
    # [15] Rule ID (exact match - no variations for Genesis)
    expected_rule_id = "system:genesis_boot_v1.3"
    if cell.logic_anchor.rule_id != expected_rule_id:
        failed_checks.append(
            f"[15] logic_anchor.rule_id: expected '{expected_rule_id}', "
            f"got '{cell.logic_anchor.rule_id}'"
        )
    
    # [16] Rule logic hash
    if cell.logic_anchor.rule_logic_hash != GENESIS_RULE_HASH:
        failed_checks.append(
            f"[16] logic_anchor.rule_logic_hash: expected '{GENESIS_RULE_HASH[:16]}...', "
            f"got '{cell.logic_anchor.rule_logic_hash[:16]}...'"
        )
    
    # [17] Interpreter (exact match - no variations for Genesis)
    expected_interpreter = "system:v1.3"
    if cell.logic_anchor.interpreter != expected_interpreter:
        failed_checks.append(
            f"[17] logic_anchor.interpreter: expected '{expected_interpreter}', "
            f"got '{cell.logic_anchor.interpreter}'"
        )
    
    # === STRUCTURE CHECK (18) ===
    
    # [18] Genesis must have no evidence (pure root, no smuggled claims)
    if cell.evidence and len(cell.evidence) > 0:
        failed_checks.append(
            f"[18] evidence: Genesis must have no evidence (got {len(cell.evidence)} items)"
        )
    
    # === PROOF CHECKS (19-21, conditional) ===
    
    if strict_signature:
        # [19] signer_key_id required in strict mode
        if not cell.proof.signer_key_id:
            failed_checks.append("[19] proof.signer_key_id: required in strict mode but not present")
        
        # [20] signature required in strict mode
        if not cell.proof.signature:
            failed_checks.append("[20] proof.signature: required in strict mode but not present")
    else:
        # [21] In bootstrap mode, ensure consistent state
        # Either signature is None, OR signature_required is False
        # This prevents a cell that looks signed but isn't validated
        if cell.proof.signature is not None and cell.proof.signature_required:
            failed_checks.append(
                "[21] proof: in bootstrap mode, if signature is present, "
                "signature_required must be False (or omit signature)"
            )
    
    # === INTEGRITY CHECK (22) ===
    
    # [22] Cell ID matches computed hash
    if not cell.verify_integrity():
        failed_checks.append(
            "[22] integrity: cell_id does not match computed hash (cell may be tampered)"
        )
    
    is_valid = len(failed_checks) == 0
    return is_valid, failed_checks


def _is_valid_utc_timestamp(ts: str) -> bool:
    """
    Check if timestamp is valid ISO 8601 UTC (must end with 'Z').
    
    This combines format validation and UTC requirement in one check.
    """
    if not ts:
        return False
    if not ts.endswith('Z'):
        return False
    return validate_timestamp(ts)


def verify_genesis_strict(cell: DecisionCell, require_signature: bool = False) -> bool:
    """
    Strict Genesis verification that raises on failure.
    
    Args:
        cell: The cell to verify
        require_signature: If True, require cryptographic signature
    
    Returns:
        True if valid
    
    Raises:
        GenesisValidationError: If any check fails, with details
    """
    is_valid, failed_checks = verify_genesis(cell, strict_signature=require_signature)
    
    if not is_valid:
        raise GenesisValidationError(
            f"Genesis validation failed: {len(failed_checks)} check(s) failed\n" +
            "\n".join(f"  - {check}" for check in failed_checks),
            failed_checks
        )
    
    return True


def is_genesis(cell: DecisionCell) -> bool:
    """
    Quick check if a cell is a Genesis cell.
    
    Only checks cell_type and prev_cell_hash.
    Use verify_genesis() for complete validation.
    
    This is useful for filtering/finding Genesis in a chain.
    """
    return (
        cell.header.cell_type == CellType.GENESIS and
        cell.header.prev_cell_hash == NULL_HASH
    )


# ============================================================================
# ACCESSORS
# ============================================================================

def get_genesis_rule() -> str:
    """Return the Genesis rule definition (original with whitespace)"""
    return GENESIS_RULE


def get_genesis_rule_hash() -> str:
    """Return the hash of the Genesis rule (canonicalized before hashing)"""
    return GENESIS_RULE_HASH


def get_canonicalized_genesis_rule() -> str:
    """Return the canonicalized Genesis rule (as used for hashing)"""
    return canonicalize_rule_content(GENESIS_RULE)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Main functions
    'create_genesis_cell',
    'verify_genesis',
    'verify_genesis_strict',
    'is_genesis',
    
    # Validation
    'validate_graph_id',
    
    # Rule access
    'get_genesis_rule',
    'get_genesis_rule_hash',
    'get_canonicalized_genesis_rule',
    
    # Exceptions
    'GenesisError',
    'GenesisValidationError',
    
    # Constants
    'GENESIS_RULE',
    'GENESIS_RULE_HASH',
    'DEFAULT_ROOT_NAMESPACE',
    'SCHEMA_VERSION',
    'GRAPH_ID_PATTERN'
]
