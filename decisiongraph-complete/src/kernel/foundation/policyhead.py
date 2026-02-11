"""
DecisionGraph Core: PolicyHead Module (v1.5)

PolicyHead cells are immutable policy snapshots that track which rules
are promoted (active policy) at any point in time.

Key properties:
- PolicyHead is a specialized DecisionCell with CellType.POLICY_HEAD
- Stored in main Chain (uses existing append-only infrastructure)
- policy_hash is SHA-256 of sorted promoted_rule_ids (deterministic)
- prev_policy_head links PolicyHead cells for a namespace (chain within chain)
- fact.object contains JSON-serialized policy data

This enables bitemporal "what policy was active when?" queries.

Threshold validation (v1.5):
- Bootstrap mode: 1-of-1 threshold allows single witness operation
- Production mode: Requires minimum 2-of-N threshold
- Validation enforces 1 <= threshold <= len(witnesses)

INT-01: PolicyHead Signature Verification Audit Trail (v1.5)
- PolicyHead stores witness_signatures (base64 encoded) for audit trail
- PolicyHead stores canonical_payload that was signed
- verify_policy_head_signatures() enables independent verification
"""

import base64
import json
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

# Use TYPE_CHECKING to avoid circular import with Chain
if TYPE_CHECKING:
    from .chain import Chain

from .cell import (
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Proof,
    CellType,
    SourceQuality,
    compute_policy_hash,
    compute_rule_logic_hash,
    get_current_timestamp,
    validate_namespace
)


# The policy promotion rule - embedded in the system
POLICY_PROMOTION_RULE = """
-- DecisionGraph Policy Promotion Rule v1.5
-- This rule defines the creation of a PolicyHead cell
-- that captures the promoted rules for a namespace

CREATE POLICY_HEAD:
  WHEN promotion_finalized
  THEN create_policy_head_cell
  WITH cell_type = "policy_head"
  AND namespace = target_namespace
  AND policy_hash = sha256(sorted(promoted_rule_ids))
  AND prev_policy_head = current_policy_head_id or None
  AND subject = "policy:head"
  AND predicate = "policy_snapshot"
  AND confidence = 1.0
  AND source_quality = "verified"
"""

POLICY_PROMOTION_RULE_HASH = compute_rule_logic_hash(POLICY_PROMOTION_RULE)

# Schema version for PolicyHead cells
POLICYHEAD_SCHEMA_VERSION = "1.5"


def create_policy_head(
    namespace: str,
    promoted_rule_ids: List[str],
    graph_id: str,
    prev_cell_hash: str,
    prev_policy_head: Optional[str] = None,
    system_time: Optional[str] = None,
    creator: Optional[str] = None,
    bootstrap_mode: bool = True,
    witness_signatures: Optional[Dict[str, bytes]] = None,
    canonical_payload: Optional[bytes] = None
) -> DecisionCell:
    """
    Create a PolicyHead cell for a namespace.

    PolicyHead captures the current promoted rules (active policy) for a namespace.
    It is a specialized DecisionCell that links via prev_policy_head to form
    a policy chain within the main Chain.

    INT-01: PolicyHead stores witness_signatures and canonical_payload for audit trail.
    These enable independent verification of who approved the promotion.

    Args:
        namespace: Target namespace for this policy (e.g., "corp.hr")
        promoted_rule_ids: List of rule IDs that are promoted (active)
        graph_id: Graph ID (must match chain's graph_id)
        prev_cell_hash: Hash of the previous cell in the main Chain
        prev_policy_head: Cell ID of previous PolicyHead for this namespace (None for first)
        system_time: Optional timestamp (defaults to now, must be ISO 8601 UTC)
        creator: Optional identifier of who created this PolicyHead
        bootstrap_mode: If True, signature is not required
        witness_signatures: Optional dict mapping witness_id -> Ed25519 signature bytes
        canonical_payload: Optional bytes that witnesses signed (for verification)

    Returns:
        DecisionCell with CellType.POLICY_HEAD

    Raises:
        ValueError: If namespace is invalid

    Example:
        >>> policy_head = create_policy_head(
        ...     namespace="corp.hr",
        ...     promoted_rule_ids=["rule:salary_v2", "rule:benefits_v1"],
        ...     graph_id=chain.graph_id,
        ...     prev_cell_hash=chain.head.cell_id,
        ...     witness_signatures={"alice": sig_bytes},
        ...     canonical_payload=payload_bytes
        ... )
    """
    # Validate namespace
    if not validate_namespace(namespace):
        raise ValueError(
            f"Invalid namespace format: '{namespace}'. "
            f"Must be lowercase alphanumeric/underscore segments separated by dots."
        )

    # Compute deterministic policy_hash
    policy_hash = compute_policy_hash(promoted_rule_ids)
    sorted_rule_ids = sorted(promoted_rule_ids)

    # Use provided system_time or current time
    ts = system_time or get_current_timestamp()

    # Policy data as JSON in fact.object
    # INT-01: Include witness signatures and canonical payload for audit trail
    policy_data = {
        "policy_hash": policy_hash,
        "promoted_rule_ids": sorted_rule_ids,
        "prev_policy_head": prev_policy_head,  # None for first PolicyHead in namespace
        "witness_signatures": {
            witness_id: base64.b64encode(sig).decode('ascii')
            for witness_id, sig in (witness_signatures or {}).items()
        },
        "canonical_payload": base64.b64encode(canonical_payload).decode('ascii') if canonical_payload else None
    }

    # Create the PolicyHead header
    header = Header(
        version=POLICYHEAD_SCHEMA_VERSION,
        graph_id=graph_id,
        cell_type=CellType.POLICY_HEAD,
        system_time=ts,
        prev_cell_hash=prev_cell_hash
    )

    # Create the PolicyHead fact
    fact = Fact(
        namespace=namespace,
        subject="policy:head",
        predicate="policy_snapshot",
        object=json.dumps(policy_data, sort_keys=True),
        confidence=1.0,
        source_quality=SourceQuality.VERIFIED,
        valid_from=ts,
        valid_to=None  # PolicyHead is point-in-time snapshot
    )

    # Create the Logic Anchor
    logic_anchor = LogicAnchor(
        rule_id="system:policy_promotion_v1.5",
        rule_logic_hash=POLICY_PROMOTION_RULE_HASH,
        interpreter="system:v1.5"
    )

    # Create the proof
    proof = Proof(
        signer_id=creator or "system:policy",
        signer_key_id=None,
        signature=None,
        merkle_root=None,
        signature_required=not bootstrap_mode
    )

    # Create and return the PolicyHead cell
    return DecisionCell(
        header=header,
        fact=fact,
        logic_anchor=logic_anchor,
        evidence=[],
        proof=proof
    )


# ============================================================================
# THRESHOLD VALIDATION (v1.5)
# ============================================================================

def validate_threshold(threshold: int, witnesses: List[str]) -> Tuple[bool, str]:
    """
    Validate that a threshold value is valid for a given witness set.

    Rules:
    - threshold must be >= 1 (threshold=0 is INVALID)
    - threshold must be <= len(witnesses) (can't require more than available)
    - witnesses list cannot be empty
    - witness identifiers must be non-empty strings

    Args:
        threshold: Number of witnesses required for approval
        witnesses: List of witness identifiers

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if threshold is valid
        - error_message: Empty string if valid, error description if invalid

    Examples:
        >>> validate_threshold(1, ["alice"])
        (True, "")
        >>> validate_threshold(0, ["alice"])
        (False, "threshold must be >= 1, got 0")
        >>> validate_threshold(3, ["alice", "bob"])
        (False, "threshold (3) cannot exceed number of witnesses (2)")
    """
    # Check witnesses list
    if not witnesses:
        return (False, "witnesses list cannot be empty")

    # Check for empty or invalid witness identifiers
    for i, witness in enumerate(witnesses):
        if not witness or not isinstance(witness, str):
            return (False, f"witness at index {i} must be a non-empty string")
        if not witness.strip():
            return (False, f"witness at index {i} cannot be whitespace-only")

    # Check threshold lower bound
    if threshold < 1:
        return (False, f"threshold must be >= 1, got {threshold}")

    # Check threshold upper bound
    if threshold > len(witnesses):
        return (False, f"threshold ({threshold}) cannot exceed number of witnesses ({len(witnesses)})")

    return (True, "")


def is_bootstrap_threshold(threshold: int, witnesses: List[str]) -> bool:
    """
    Check if threshold configuration represents bootstrap mode.

    Bootstrap mode is defined as:
    - Exactly 1 witness
    - Threshold of 1 (1-of-1)

    This allows single-witness operation during development and initial deployment.
    Bootstrap mode is valid but represents minimal security.

    Args:
        threshold: Number of witnesses required for approval
        witnesses: List of witness identifiers

    Returns:
        True if configuration is bootstrap mode (1-of-1)

    Examples:
        >>> is_bootstrap_threshold(1, ["alice"])
        True
        >>> is_bootstrap_threshold(1, ["alice", "bob"])
        False  # Not bootstrap - has multiple witnesses
        >>> is_bootstrap_threshold(2, ["alice", "bob"])
        False  # Not bootstrap - requires 2-of-2
    """
    # Must be valid first
    is_valid, _ = validate_threshold(threshold, witnesses)
    if not is_valid:
        return False

    # Bootstrap = exactly 1 witness with threshold 1
    return threshold == 1 and len(witnesses) == 1


def is_production_threshold(threshold: int, witnesses: List[str]) -> bool:
    """
    Check if threshold configuration meets production requirements.

    Production mode requires:
    - At least 2 witnesses
    - Threshold >= 2 (requires multiple approvals)

    This ensures no single witness can unilaterally approve policy changes.

    Args:
        threshold: Number of witnesses required for approval
        witnesses: List of witness identifiers

    Returns:
        True if configuration meets production requirements

    Examples:
        >>> is_production_threshold(2, ["alice", "bob"])
        True  # 2-of-2
        >>> is_production_threshold(2, ["alice", "bob", "charlie"])
        True  # 2-of-3
        >>> is_production_threshold(3, ["alice", "bob", "charlie"])
        True  # 3-of-3 (unanimous)
        >>> is_production_threshold(1, ["alice", "bob"])
        False  # threshold too low (single approval allowed)
        >>> is_production_threshold(1, ["alice"])
        False  # bootstrap mode, not production
    """
    # Must be valid first
    is_valid, _ = validate_threshold(threshold, witnesses)
    if not is_valid:
        return False

    # Production = at least 2 witnesses AND threshold >= 2
    return len(witnesses) >= 2 and threshold >= 2


# ============================================================================
# POLICY DATA PARSING
# ============================================================================

def parse_policy_data(policy_head: DecisionCell) -> dict:
    """
    Parse policy data from a PolicyHead cell's fact.object.

    Args:
        policy_head: A DecisionCell with CellType.POLICY_HEAD

    Returns:
        Dict with keys: policy_hash, promoted_rule_ids, prev_policy_head

    Raises:
        ValueError: If cell is not a PolicyHead or data is malformed
    """
    if policy_head.header.cell_type != CellType.POLICY_HEAD:
        raise ValueError(
            f"Expected POLICY_HEAD cell, got {policy_head.header.cell_type.value}"
        )

    try:
        return json.loads(policy_head.fact.object)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed policy data in PolicyHead: {e}")


def verify_policy_hash(policy_head: DecisionCell) -> bool:
    """
    Verify that a PolicyHead's policy_hash matches its promoted_rule_ids.

    This is a tamper-detection check: if someone modified the promoted_rule_ids
    without updating policy_hash, this will return False.

    Args:
        policy_head: A DecisionCell with CellType.POLICY_HEAD

    Returns:
        True if policy_hash is valid, False if tampered
    """
    policy_data = parse_policy_data(policy_head)
    expected_hash = compute_policy_hash(policy_data["promoted_rule_ids"])
    return policy_data["policy_hash"] == expected_hash


def verify_policy_head_signatures(
    policy_head: DecisionCell,
    witness_public_keys: Dict[str, bytes]
) -> Tuple[bool, List[str]]:
    """
    Verify witness signatures stored in a PolicyHead cell (INT-01).

    Each signature in the PolicyHead was made by a witness over the
    canonical_payload. This function verifies those signatures using
    the provided public keys.

    This enables independent audit verification: anyone with the witness
    public keys can verify that the policy was properly approved.

    Args:
        policy_head: A DecisionCell with CellType.POLICY_HEAD
        witness_public_keys: Dict mapping witness_id -> Ed25519 public key (32 bytes)

    Returns:
        Tuple of (all_valid, error_messages)
        - all_valid: True if ALL signatures verify successfully
        - error_messages: List of errors (empty if all valid)

    Example:
        >>> is_valid, errors = verify_policy_head_signatures(
        ...     policy_head,
        ...     {"alice": alice_pub, "bob": bob_pub}
        ... )
        >>> if not is_valid:
        ...     for err in errors:
        ...         print(f"Signature error: {err}")
    """
    from .signing import verify_signature

    errors: List[str] = []

    # Parse policy data
    policy_data = parse_policy_data(policy_head)

    # Get witness signatures and canonical payload
    witness_sigs = policy_data.get("witness_signatures", {})
    canonical_payload_b64 = policy_data.get("canonical_payload")

    # If no canonical payload, cannot verify signatures
    if not canonical_payload_b64:
        return (False, ["PolicyHead does not contain canonical_payload for verification"])

    # Decode canonical payload
    try:
        canonical_payload = base64.b64decode(canonical_payload_b64)
    except Exception as e:
        return (False, [f"Failed to decode canonical_payload: {e}"])

    # No signatures to verify is valid (e.g., bootstrap mode)
    if not witness_sigs:
        return (True, [])

    # Verify each signature
    for witness_id, sig_b64 in witness_sigs.items():
        # Get public key for this witness
        pub_key = witness_public_keys.get(witness_id)
        if pub_key is None:
            errors.append(f"No public key provided for witness '{witness_id}'")
            continue

        # Decode signature
        try:
            signature = base64.b64decode(sig_b64)
        except Exception as e:
            errors.append(f"Failed to decode signature for witness '{witness_id}': {e}")
            continue

        # Verify signature
        try:
            is_valid = verify_signature(pub_key, canonical_payload, signature)
            if not is_valid:
                errors.append(f"Signature verification failed for witness '{witness_id}'")
        except Exception as e:
            errors.append(f"Signature verification error for witness '{witness_id}': {e}")

    return (len(errors) == 0, errors)


# ============================================================================
# CHAIN OPERATIONS AND QUERIES (POL-03, POL-04)
# ============================================================================

def get_current_policy_head(chain: 'Chain', namespace: str) -> Optional[DecisionCell]:
    """
    Get the current (most recent) PolicyHead for a namespace.

    Scans all PolicyHead cells in the chain and returns the one with the
    latest system_time for the given namespace.

    Args:
        chain: The Chain to search
        namespace: The namespace to query (e.g., "corp.hr")

    Returns:
        The most recent PolicyHead cell for the namespace, or None if none exist

    Example:
        >>> current = get_current_policy_head(chain, "corp.hr")
        >>> if current:
        ...     data = parse_policy_data(current)
        ...     print(f"Active rules: {data['promoted_rule_ids']}")
    """
    policy_heads = chain.find_by_type(CellType.POLICY_HEAD)

    # Filter by namespace and find latest
    namespace_heads = [
        ph for ph in policy_heads
        if ph.fact.namespace == namespace
    ]

    if not namespace_heads:
        return None

    # Return the one with latest system_time
    # Since chain is append-only and temporally ordered, the last one is current
    return max(namespace_heads, key=lambda ph: ph.header.system_time)


def get_policy_head_chain(chain: 'Chain', namespace: str) -> List[DecisionCell]:
    """
    Get the full PolicyHead chain for a namespace (oldest to newest).

    Returns all PolicyHead cells for the namespace, ordered by system_time.
    This represents the complete policy history for the namespace.

    Args:
        chain: The Chain to search
        namespace: The namespace to query (e.g., "corp.hr")

    Returns:
        List of PolicyHead cells ordered from oldest to newest (empty if none)

    Example:
        >>> history = get_policy_head_chain(chain, "corp.hr")
        >>> for ph in history:
        ...     data = parse_policy_data(ph)
        ...     print(f"{ph.header.system_time}: {len(data['promoted_rule_ids'])} rules")
    """
    policy_heads = chain.find_by_type(CellType.POLICY_HEAD)

    # Filter by namespace
    namespace_heads = [
        ph for ph in policy_heads
        if ph.fact.namespace == namespace
    ]

    # Sort by system_time (oldest first)
    return sorted(namespace_heads, key=lambda ph: ph.header.system_time)


def get_policy_head_at_time(
    chain: 'Chain',
    namespace: str,
    as_of_time: str
) -> Optional[DecisionCell]:
    """
    Get the PolicyHead that was active at a specific point in time (bitemporal query).

    Finds the latest PolicyHead for the namespace with system_time <= as_of_time.
    This enables "what was the policy at time X?" queries.

    Args:
        chain: The Chain to search
        namespace: The namespace to query (e.g., "corp.hr")
        as_of_time: ISO 8601 UTC timestamp to query against

    Returns:
        The PolicyHead that was active at as_of_time, or None if no policy existed

    Example:
        >>> # What was the policy on Jan 15?
        >>> old_policy = get_policy_head_at_time(chain, "corp.hr", "2026-01-15T00:00:00Z")
        >>> if old_policy:
        ...     data = parse_policy_data(old_policy)
        ...     print(f"Had {len(data['promoted_rule_ids'])} rules on Jan 15")
    """
    policy_heads = chain.find_by_type(CellType.POLICY_HEAD)

    # Filter by namespace and time constraint
    valid_heads = [
        ph for ph in policy_heads
        if ph.fact.namespace == namespace and ph.header.system_time <= as_of_time
    ]

    if not valid_heads:
        return None

    # Return the most recent one before or at as_of_time
    return max(valid_heads, key=lambda ph: ph.header.system_time)


def validate_policy_head_chain(chain: 'Chain', namespace: str) -> Tuple[bool, List[str]]:
    """
    Validate the integrity of a PolicyHead chain for a namespace.

    Checks:
    1. All PolicyHead cells have valid policy_hash
    2. prev_policy_head links form a valid chain (no orphans, no cycles)
    3. prev_policy_head references exist in the chain
    4. Temporal ordering matches prev_policy_head links

    Args:
        chain: The Chain to validate
        namespace: The namespace to validate

    Returns:
        Tuple of (is_valid, list of error messages)
        If is_valid is True, error list is empty

    Example:
        >>> is_valid, errors = validate_policy_head_chain(chain, "corp.hr")
        >>> if not is_valid:
        ...     for err in errors:
        ...         print(f"Error: {err}")
    """
    errors: List[str] = []

    # Get all PolicyHeads for namespace in temporal order
    policy_heads = get_policy_head_chain(chain, namespace)

    if not policy_heads:
        # No PolicyHeads is valid (namespace hasn't promoted any rules yet)
        return (True, [])

    # Build index for fast lookup
    ph_by_id = {ph.cell_id: ph for ph in policy_heads}

    # Track which cells are referenced as prev_policy_head
    referenced_as_prev = set()

    for i, ph in enumerate(policy_heads):
        # Check 1: Valid policy_hash
        if not verify_policy_hash(ph):
            errors.append(
                f"PolicyHead {ph.cell_id[:16]}... has invalid policy_hash "
                f"(possible tampering)"
            )

        # Parse policy data
        try:
            policy_data = parse_policy_data(ph)
        except ValueError as e:
            errors.append(f"PolicyHead {ph.cell_id[:16]}... has malformed data: {e}")
            continue

        prev_head_id = policy_data.get("prev_policy_head")

        # Check 2: First PolicyHead should have prev_policy_head = None
        if i == 0:
            if prev_head_id is not None:
                errors.append(
                    f"First PolicyHead {ph.cell_id[:16]}... has non-null prev_policy_head "
                    f"(expected None for first policy in namespace)"
                )
        else:
            # Check 3: prev_policy_head should reference an existing cell
            if prev_head_id is None:
                errors.append(
                    f"PolicyHead {ph.cell_id[:16]}... (not first) has null prev_policy_head"
                )
            elif prev_head_id not in ph_by_id:
                # Check if it exists in the main chain but isn't for this namespace
                main_chain_cell = chain.get_cell(prev_head_id)
                if main_chain_cell is None:
                    errors.append(
                        f"PolicyHead {ph.cell_id[:16]}... references non-existent "
                        f"prev_policy_head: {prev_head_id[:16]}..."
                    )
                elif main_chain_cell.header.cell_type != CellType.POLICY_HEAD:
                    errors.append(
                        f"PolicyHead {ph.cell_id[:16]}... prev_policy_head "
                        f"{prev_head_id[:16]}... is not a POLICY_HEAD cell"
                    )
                elif main_chain_cell.fact.namespace != namespace:
                    errors.append(
                        f"PolicyHead {ph.cell_id[:16]}... prev_policy_head "
                        f"{prev_head_id[:16]}... is for different namespace "
                        f"'{main_chain_cell.fact.namespace}'"
                    )
            else:
                referenced_as_prev.add(prev_head_id)

                # Check 4: Temporal ordering - prev should be before current
                prev_ph = ph_by_id[prev_head_id]
                if prev_ph.header.system_time >= ph.header.system_time:
                    errors.append(
                        f"PolicyHead {ph.cell_id[:16]}... has prev_policy_head with "
                        f"later or equal system_time (temporal violation)"
                    )

    # Check for orphaned heads (not first, and not referenced by anyone)
    # The current head won't be referenced, which is correct
    # First head shouldn't be referenced as prev either
    if len(policy_heads) > 1:
        # All but the last (current) and first should be referenced
        middle_heads = set(ph.cell_id for ph in policy_heads[1:-1])
        unreferenced = middle_heads - referenced_as_prev
        for orphan_id in unreferenced:
            errors.append(
                f"PolicyHead {orphan_id[:16]}... is orphaned "
                f"(not referenced by any successor)"
            )

    return (len(errors) == 0, errors)


# ============================================================================
# AUDIT TEXT GENERATION (AUD-01)
# ============================================================================

def policy_head_to_audit_text(policy_head: DecisionCell) -> str:
    """
    Generate human-readable audit report for a PolicyHead cell (AUD-01).

    Returns deterministic plain text report containing:
    - Policy Snapshot (namespace, cell_id, system_time)
    - Policy Hash (hash value, promoted rules count, rule list)
    - Chain Link (previous PolicyHead or genesis indicator)
    - Witness Signatures (count, witness IDs sorted alphabetically)
    - Promotion Context (submitter from proof.signer_id)
    - Schema Version

    Same PolicyHead always produces identical output (deterministic).

    Args:
        policy_head: A DecisionCell with CellType.POLICY_HEAD

    Returns:
        Multi-line string with audit report

    Raises:
        ValueError: If cell is not a PolicyHead or data is malformed

    Example:
        policy_head = get_current_policy_head(chain, "corp.hr")
        report = policy_head_to_audit_text(policy_head)
        print(report)
        # Or save to file:
        with open('policyhead_audit.txt', 'w') as f:
            f.write(report)
    """
    # Parse policy data (validates cell type)
    policy_data = parse_policy_data(policy_head)

    lines = []

    # Header
    lines.append("POLICYHEAD AUDIT REPORT")
    lines.append("=" * 50)
    lines.append("")

    # Policy Snapshot
    lines.append("Policy Snapshot:")
    lines.append(f"  Namespace: {policy_head.fact.namespace}")
    # Truncate cell_id to 16 chars + "..."
    cell_id_display = policy_head.cell_id[:16] + "..."
    lines.append(f"  Cell ID: {cell_id_display}")
    lines.append(f"  System Time: {policy_head.header.system_time}")
    lines.append("")

    # Policy Hash
    lines.append("Policy Hash:")
    policy_hash = policy_data.get("policy_hash", "")
    policy_hash_display = policy_hash[:16] + "..." if len(policy_hash) > 16 else policy_hash
    lines.append(f"  Hash: {policy_hash_display}")
    promoted_rule_ids = policy_data.get("promoted_rule_ids", [])
    lines.append(f"  Promoted Rules: {len(promoted_rule_ids)}")
    # Rules are already sorted in policy_data (create_policy_head sorts them)
    for rule_id in promoted_rule_ids:
        lines.append(f"    - {rule_id}")
    lines.append("")

    # Chain Link
    lines.append("Chain Link:")
    prev_policy_head = policy_data.get("prev_policy_head")
    if prev_policy_head is None:
        lines.append("  Previous PolicyHead: (genesis - first policy)")
    else:
        prev_display = prev_policy_head[:16] + "..." if len(prev_policy_head) > 16 else prev_policy_head
        lines.append(f"  Previous PolicyHead: {prev_display}")
    lines.append("")

    # Witness Signatures
    lines.append("Witness Signatures:")
    witness_signatures = policy_data.get("witness_signatures", {})
    lines.append(f"  Signatures Collected: {len(witness_signatures)}")
    # Sort witness IDs alphabetically for deterministic output
    sorted_witness_ids = sorted(witness_signatures.keys())
    for witness_id in sorted_witness_ids:
        lines.append(f"    - {witness_id}: (signature present)")
    lines.append("")

    # Promotion Context
    lines.append("Promotion Context:")
    submitter = policy_head.proof.signer_id or "unknown"
    lines.append(f"  Submitter: {submitter}")
    lines.append("")

    # Footer
    lines.append(f"Schema Version: {policy_head.header.version}")

    return "\n".join(lines)


# ============================================================================
# AUDIT TRAIL VISUALIZATION (AUD-02)
# ============================================================================

def policy_head_chain_to_dot(chain: 'Chain', namespace: str) -> str:
    """
    Generate Graphviz DOT format for PolicyHead chain visualization.

    Creates a visual representation of policy evolution for a namespace,
    showing PolicyHead nodes and supersedes edges between them.

    Output can be rendered with Graphviz:
        $ dot -Tpng policy_chain.dot -o policy_chain.png
        $ dot -Tsvg policy_chain.dot -o policy_chain.svg

    Or online tools: viz-js.com, Graphviz Online

    Same chain + namespace always produces identical output (deterministic).

    Args:
        chain: The Chain to visualize
        namespace: The namespace to query (e.g., "corp.hr")

    Returns:
        String containing valid DOT syntax

    Example:
        >>> dot_text = policy_head_chain_to_dot(chain, "corp.hr")
        >>> with open('policy_chain.dot', 'w') as f:
        ...     f.write(dot_text)
        # Then: dot -Tpng policy_chain.dot -o policy_chain.png
    """
    def _escape_dot_string(s: str) -> str:
        """Escape quotes, backslashes, and newlines for DOT format"""
        return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

    def _short_id(cell_id: str) -> str:
        """Truncate cell ID to first 12 chars + ellipsis"""
        return cell_id[:12] + "..."

    lines = []

    # Graph header
    lines.append("digraph policy_chain {")
    lines.append(f"  // PolicyHead Chain: {_escape_dot_string(namespace)}")
    lines.append("  rankdir=TB;")
    lines.append("  node [shape=box, style=filled];")
    lines.append("")

    # Get PolicyHead chain for namespace (oldest to newest)
    policy_heads = get_policy_head_chain(chain, namespace)

    # Build node definitions and edges
    # Process newest first for visual clarity (reversed order)
    lines.append("  // PolicyHead nodes")
    for ph in reversed(policy_heads):
        policy_data = parse_policy_data(ph)
        # Extract date portion from system_time (YYYY-MM-DD)
        date_str = ph.header.system_time[:10] if len(ph.header.system_time) >= 10 else ph.header.system_time
        rule_count = len(policy_data.get("promoted_rule_ids", []))
        label = f"PolicyHead\\n{_escape_dot_string(namespace)}\\n{date_str}\\nRules: {rule_count}"
        node_id = _short_id(ph.cell_id)
        lines.append(f'  "{node_id}" [label="{label}", fillcolor=lightyellow];')
    lines.append("")

    # Chain edges (from current to prev_policy_head)
    lines.append("  // Chain edges")
    for ph in policy_heads:
        policy_data = parse_policy_data(ph)
        prev_head_id = policy_data.get("prev_policy_head")
        if prev_head_id:
            current_node = _short_id(ph.cell_id)
            prev_node = _short_id(prev_head_id)
            lines.append(f'  "{current_node}" -> "{prev_node}" [label="supersedes"];')
    lines.append("")

    # Graph footer
    lines.append("}")

    return "\n".join(lines)


# Export public interface
__all__ = [
    # Creation
    'create_policy_head',

    # Parsing/verification
    'parse_policy_data',
    'verify_policy_hash',
    'verify_policy_head_signatures',  # INT-01: Signature verification for audit trail

    # Chain operations and queries (POL-03, POL-04)
    'get_current_policy_head',
    'get_policy_head_chain',
    'get_policy_head_at_time',
    'validate_policy_head_chain',

    # Audit text generation (AUD-01)
    'policy_head_to_audit_text',

    # Audit trail visualization (AUD-02)
    'policy_head_chain_to_dot',

    # Threshold validation (v1.5)
    'validate_threshold',
    'is_bootstrap_threshold',
    'is_production_threshold',

    # Constants
    'POLICY_PROMOTION_RULE',
    'POLICY_PROMOTION_RULE_HASH',
    'POLICYHEAD_SCHEMA_VERSION'
]
