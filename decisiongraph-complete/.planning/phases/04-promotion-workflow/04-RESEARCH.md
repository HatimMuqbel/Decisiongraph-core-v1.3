# Phase 4: Promotion Workflow - Research

**Researched:** 2026-01-28
**Domain:** Multi-phase workflow state machine with Ed25519 signature collection and threshold validation
**Confidence:** HIGH

## Summary

Phase 4 implements a three-phase promotion workflow (Submit -> Collect -> Finalize) that transforms rule hypotheses into active policy. The workflow is implemented as a PromotionRequest state machine with states PENDING, COLLECTING, THRESHOLD_MET, FINALIZED, and REJECTED. The standard approach leverages the existing infrastructure: WitnessRegistry for witness validation (Phase 2), Ed25519 signing utilities (signing.py), PolicyHead creation (Phase 1), and the existing error code hierarchy (DG_UNAUTHORIZED, DG_SIGNATURE_INVALID).

**Critical finding:** PromotionRequest is NOT a Cell. It's an in-memory state machine that coordinates signature collection until finalization, when a PolicyHead Cell is atomically appended to the Chain. This follows the pattern where only finalized state becomes immutable on-chain. The promotion workflow maintains a canonical payload (sorted rule_ids, promotion_id, namespace, timestamp) to prevent replay attacks.

**Primary recommendation:** Implement PromotionRequest as a frozen dataclass holding immutable configuration plus mutable signature collection state, add promotion methods to Engine class (submit_promotion, collect_witness_signature, finalize_promotion), use existing verify_signature() for witness signatures, and create PolicyHead on finalization using existing create_policy_head().

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.10+ | dataclasses, typing, enum, json, uuid, hashlib | Existing v1.3 patterns, type hints throughout |
| cryptography | latest | Ed25519 via signing.py | Already used in RFA layer, proven Ed25519 implementation |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | latest | Test framework | All existing tests use pytest patterns |
| None | - | No external state store | Promotion state is in-memory, finalized to Chain |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| In-memory PromotionRequest | On-chain PENDING cell | On-chain adds complexity; in-memory is simpler for workflow state |
| Single Engine class | Separate PromotionEngine | Single Engine maintains API consistency with existing process_rfa() |
| Dict for signatures | Dict[witness_id, bytes] | Dict is appropriate - mutable during collection, frozen at finalization |

**Installation:**
```bash
# No new dependencies needed - all available in existing v1.3/v1.4
pip install cryptography pytest
```

## Architecture Patterns

### Recommended Project Structure
```
src/decisiongraph/
├── engine.py            # EXTEND: add submit_promotion, collect_witness_signature, finalize_promotion
├── promotion.py         # NEW: PromotionRequest dataclass, PromotionStatus enum
├── policyhead.py        # EXISTING: create_policy_head (Phase 1)
├── signing.py           # EXISTING: verify_signature (already implemented)
├── registry.py          # EXISTING: WitnessRegistry.get_witness_set (Phase 2)
├── witnessset.py        # EXISTING: WitnessSet (Phase 2)
└── exceptions.py        # EXISTING: UnauthorizedError, SignatureInvalidError

tests/
├── test_promotion.py    # NEW: PromotionRequest state machine, signature collection
├── test_engine_promotion.py  # NEW: Engine.submit/collect/finalize integration
└── test_promotion_adversarial.py  # NEW: Replay attacks, unauthorized witnesses
```

### Pattern 1: PromotionRequest State Machine
**What:** Immutable configuration with mutable signature collection state
**When to use:** Tracking promotion lifecycle from submission to finalization
**Example:**
```python
# Source: Derived from existing dataclass patterns in witnessset.py, cell.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import uuid
import hashlib
import json

class PromotionStatus(str, Enum):
    """Promotion workflow states (PRO-03)"""
    PENDING = "pending"          # Created, no signatures yet
    COLLECTING = "collecting"    # Has at least one signature
    THRESHOLD_MET = "threshold_met"  # Threshold reached, ready to finalize
    FINALIZED = "finalized"      # PolicyHead created
    REJECTED = "rejected"        # Explicitly rejected or expired

@dataclass
class PromotionRequest:
    """
    Tracks a promotion request through its lifecycle.

    Immutable fields set at creation:
    - promotion_id: Unique identifier
    - namespace: Target namespace
    - rule_ids: Rules being promoted (sorted)
    - submitter_id: Who submitted
    - created_at: Submission timestamp
    - canonical_payload: Bytes to sign (deterministic)

    Mutable state during collection:
    - status: Current workflow state
    - signatures: Collected witness signatures
    """
    promotion_id: str
    namespace: str
    rule_ids: tuple  # Immutable, sorted at creation
    submitter_id: str
    created_at: str
    canonical_payload: bytes  # What witnesses sign
    required_threshold: int

    # Mutable state
    status: PromotionStatus = PromotionStatus.PENDING
    signatures: Dict[str, bytes] = field(default_factory=dict)  # witness_id -> signature

    @classmethod
    def create(
        cls,
        namespace: str,
        rule_ids: List[str],
        submitter_id: str,
        threshold: int,
        created_at: str
    ) -> 'PromotionRequest':
        """Factory method ensuring canonical payload creation."""
        promotion_id = str(uuid.uuid4())
        sorted_ids = tuple(sorted(rule_ids))

        # Canonical payload for signing (prevents replay)
        payload_dict = {
            "promotion_id": promotion_id,
            "namespace": namespace,
            "rule_ids": list(sorted_ids),
            "timestamp": created_at
        }
        canonical_payload = json.dumps(
            payload_dict, sort_keys=True, separators=(',', ':')
        ).encode('utf-8')

        return cls(
            promotion_id=promotion_id,
            namespace=namespace,
            rule_ids=sorted_ids,
            submitter_id=submitter_id,
            created_at=created_at,
            canonical_payload=canonical_payload,
            required_threshold=threshold,
            status=PromotionStatus.PENDING,
            signatures={}
        )
```

### Pattern 2: Engine Promotion Methods
**What:** Extend Engine with submit/collect/finalize methods
**When to use:** External API for promotion workflow (PRO-01, PRO-02, PRO-04)
**Example:**
```python
# Source: Derived from engine.py process_rfa() pattern
class Engine:
    # Existing __init__ and process_rfa...

    def __init__(self, chain: Chain, ...):
        self.chain = chain
        self.scholar = create_scholar(chain)
        # NEW: Track active promotions
        self._promotions: Dict[str, PromotionRequest] = {}
        self._registry = WitnessRegistry(chain)  # For WitnessSet lookup

    def submit_promotion(
        self,
        namespace: str,
        rule_ids: List[str],
        submitter_id: str
    ) -> str:
        """
        Submit a promotion request (PRO-01).

        Returns:
            promotion_id: Unique identifier for this promotion

        Raises:
            InputInvalidError: If namespace invalid or rule_ids empty
        """
        # Validate namespace
        if not validate_namespace(namespace):
            raise InputInvalidError(f"Invalid namespace: {namespace}")

        # Get WitnessSet for threshold
        witness_set = self._registry.get_witness_set(namespace)
        if not witness_set:
            raise InputInvalidError(f"No WitnessSet configured for namespace: {namespace}")

        # Create promotion request
        promotion = PromotionRequest.create(
            namespace=namespace,
            rule_ids=rule_ids,
            submitter_id=submitter_id,
            threshold=witness_set.threshold,
            created_at=get_current_timestamp()
        )

        self._promotions[promotion.promotion_id] = promotion
        return promotion.promotion_id

    def collect_witness_signature(
        self,
        promotion_id: str,
        witness_id: str,
        signature: bytes
    ) -> PromotionStatus:
        """
        Collect a witness signature (PRO-02).

        Returns:
            Current promotion status after signature collection

        Raises:
            UnauthorizedError: If witness not in WitnessSet (PRO-05)
            SignatureInvalidError: If signature verification fails (PRO-06)
        """
        promotion = self._promotions.get(promotion_id)
        if not promotion:
            raise InputInvalidError(f"Promotion not found: {promotion_id}")

        # Get WitnessSet for authorization check
        witness_set = self._registry.get_witness_set(promotion.namespace)
        if witness_id not in witness_set.witnesses:
            raise UnauthorizedError(
                message=f"Witness '{witness_id}' not in WitnessSet for namespace '{promotion.namespace}'",
                details={
                    "witness_id": witness_id,
                    "namespace": promotion.namespace,
                    "allowed_witnesses": list(witness_set.witnesses)
                }
            )

        # Get witness public key and verify signature
        # NOTE: In production, public_key lookup from witness registry
        # For now, caller must provide valid signature
        public_key = self._get_witness_public_key(witness_id)
        if not verify_signature(public_key, promotion.canonical_payload, signature):
            raise SignatureInvalidError(
                message=f"Signature verification failed for witness '{witness_id}'",
                details={"witness_id": witness_id, "promotion_id": promotion_id}
            )

        # Store signature
        promotion.signatures[witness_id] = signature

        # Update status based on signature count
        sig_count = len(promotion.signatures)
        if sig_count == 1 and promotion.status == PromotionStatus.PENDING:
            promotion.status = PromotionStatus.COLLECTING
        if sig_count >= promotion.required_threshold:
            promotion.status = PromotionStatus.THRESHOLD_MET

        return promotion.status

    def finalize_promotion(self, promotion_id: str) -> str:
        """
        Finalize promotion and create PolicyHead (PRO-04).

        Returns:
            cell_id of the created PolicyHead

        Raises:
            UnauthorizedError: If threshold not met (INT-04)
        """
        promotion = self._promotions.get(promotion_id)
        if not promotion:
            raise InputInvalidError(f"Promotion not found: {promotion_id}")

        if promotion.status != PromotionStatus.THRESHOLD_MET:
            raise UnauthorizedError(
                message=f"Cannot finalize: status is {promotion.status.value}, need THRESHOLD_MET",
                details={
                    "current_status": promotion.status.value,
                    "signatures_collected": len(promotion.signatures),
                    "threshold_required": promotion.required_threshold
                }
            )

        # Get previous PolicyHead for linking
        prev_policy_head = get_current_policy_head(self.chain, promotion.namespace)
        prev_policy_head_id = prev_policy_head.cell_id if prev_policy_head else None

        # Create PolicyHead cell
        policy_head = create_policy_head(
            namespace=promotion.namespace,
            promoted_rule_ids=list(promotion.rule_ids),
            graph_id=self.chain.graph_id,
            prev_cell_hash=self.chain.head.cell_id,
            prev_policy_head=prev_policy_head_id,
            system_time=get_current_timestamp()
        )

        # Append to chain (atomic)
        self.chain.append(policy_head)

        # Update promotion status
        promotion.status = PromotionStatus.FINALIZED

        return policy_head.cell_id
```

### Pattern 3: Canonical Payload for Replay Prevention
**What:** Deterministic bytes that witnesses sign
**When to use:** Creating the message that witnesses will sign
**Example:**
```python
# Source: Derived from cell.py compute_policy_hash(), engine.py _sign_proof_packet()
def create_canonical_payload(
    promotion_id: str,
    namespace: str,
    rule_ids: List[str],
    timestamp: str
) -> bytes:
    """
    Create canonical payload for witness signatures.

    Deterministic serialization prevents:
    - Replay attacks (promotion_id is unique)
    - Order manipulation (rule_ids are sorted)
    - Timestamp manipulation (timestamp is fixed at creation)
    """
    payload = {
        "promotion_id": promotion_id,
        "namespace": namespace,
        "rule_ids": sorted(rule_ids),
        "timestamp": timestamp
    }
    # Canonical JSON: sorted keys, no whitespace
    return json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
```

### Pattern 4: Witness Authorization Check
**What:** Verify witness is in WitnessSet before accepting signature
**When to use:** Every collect_witness_signature call (PRO-05)
**Example:**
```python
# Source: Derived from registry.py WitnessRegistry.get_witness_set()
def verify_witness_authorized(
    registry: WitnessRegistry,
    namespace: str,
    witness_id: str
) -> None:
    """
    Verify witness is authorized for namespace.

    Raises:
        UnauthorizedError: If witness not in WitnessSet
    """
    witness_set = registry.get_witness_set(namespace)
    if witness_set is None:
        raise UnauthorizedError(
            message=f"No WitnessSet configured for namespace: {namespace}",
            details={"namespace": namespace}
        )

    if witness_id not in witness_set.witnesses:
        raise UnauthorizedError(
            message=f"Witness '{witness_id}' not authorized for namespace '{namespace}'",
            details={
                "witness_id": witness_id,
                "namespace": namespace,
                "authorized_witnesses": list(witness_set.witnesses)
            }
        )
```

### Pattern 5: Signature Verification
**What:** Verify Ed25519 signature from witness
**When to use:** Every collect_witness_signature call (PRO-06)
**Example:**
```python
# Source: Directly from signing.py verify_signature()
from decisiongraph.signing import verify_signature

def verify_witness_signature(
    public_key: bytes,
    canonical_payload: bytes,
    signature: bytes,
    witness_id: str,
    promotion_id: str
) -> None:
    """
    Verify witness signature against canonical payload.

    Raises:
        SignatureInvalidError: If verification fails
    """
    # verify_signature returns False for invalid (not exception)
    if not verify_signature(public_key, canonical_payload, signature):
        raise SignatureInvalidError(
            message=f"Invalid signature from witness '{witness_id}'",
            details={
                "witness_id": witness_id,
                "promotion_id": promotion_id,
                "signature_length": len(signature)
            }
        )
```

### Anti-Patterns to Avoid
- **Storing PromotionRequest on-chain before finalization:** Only finalized PolicyHead goes on chain. In-flight state is in-memory.
- **Mutable rule_ids after submission:** Rule IDs must be immutable (use tuple) to prevent manipulation after signatures.
- **Non-deterministic payload serialization:** Always use sorted keys and compact separators for canonical payload.
- **Accepting signatures without authorization check:** ALWAYS verify witness in WitnessSet BEFORE verifying signature.
- **Allowing duplicate signatures from same witness:** Track signatures by witness_id in dict to prevent duplication.
- **Finalizing without threshold check:** Status machine enforces threshold requirement.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Signature verification | Custom crypto | signing.verify_signature() | Already tested, handles edge cases, returns bool not exception |
| Witness lookup | Manual chain traversal | WitnessRegistry.get_witness_set() | Stateless rebuild from chain, correct Genesis extraction |
| PolicyHead creation | Custom cell construction | create_policy_head() | Handles prev_policy_head linking, policy_hash computation |
| Error codes | Custom exception types | UnauthorizedError, SignatureInvalidError | DG_UNAUTHORIZED, DG_SIGNATURE_INVALID already defined |
| Canonical serialization | Manual string building | json.dumps(sort_keys=True, separators=(',',':')) | Matches existing patterns in cell.py, engine.py |
| Timestamp generation | datetime.now() | get_current_timestamp() | Ensures UTC, ISO 8601, consistent format |
| UUID generation | Custom ID | uuid.uuid4() | Standard, no collision risk |

**Key insight:** The promotion workflow orchestrates existing components. New code is the state machine and workflow coordination, not crypto or storage.

## Common Pitfalls

### Pitfall 1: Accepting Signatures for Unknown Promotions
**What goes wrong:** collect_witness_signature called with non-existent promotion_id
**Why it happens:** Network delays, typos, malicious attempts
**How to avoid:** Always validate promotion_id exists in _promotions dict before any operation
**Warning signs:** KeyError when accessing promotion, NoneType errors

### Pitfall 2: Race Condition in Threshold Check
**What goes wrong:** Two witnesses submit at same time, both see under-threshold, both added
**Why it happens:** Check-then-act without synchronization
**How to avoid:** In single-threaded Python, dict operations are atomic. For multi-threaded, use locks around collect_witness_signature.
**Warning signs:** More signatures than threshold in THRESHOLD_MET state (acceptable, just over-collected)

### Pitfall 3: Signature Replay Across Promotions
**What goes wrong:** Signature from one promotion reused for another
**Why it happens:** Canonical payload doesn't include promotion-specific data
**How to avoid:** promotion_id is part of canonical_payload. Each promotion has unique payload.
**Warning signs:** Same signature bytes appearing for different promotions

### Pitfall 4: Modifying Rule IDs After Submission
**What goes wrong:** Attacker tries to add/remove rules after witnesses signed
**Why it happens:** Mutable list passed to PromotionRequest
**How to avoid:** Store rule_ids as tuple (immutable). canonical_payload includes sorted rule_ids.
**Warning signs:** rule_ids mismatch between promotion and finalized PolicyHead

### Pitfall 5: Finalizing Without Full Authorization
**What goes wrong:** Finalization creates PolicyHead even though witness was unauthorized
**Why it happens:** Authorization check missing or bypassed
**How to avoid:** collect_witness_signature ALWAYS checks WitnessSet membership FIRST, before signature verification. Order matters: authorization -> verification -> storage.
**Warning signs:** PolicyHead created with signatures from non-witnesses

### Pitfall 6: verify_signature Returns False, Not Exception
**What goes wrong:** Code assumes verify_signature raises on invalid signature
**Why it happens:** Different mental model from other verification functions
**How to avoid:** Explicitly check return value: `if not verify_signature(...): raise SignatureInvalidError(...)`
**Warning signs:** Silent acceptance of invalid signatures (no error raised)

### Pitfall 7: Missing Namespace Validation in submit_promotion
**What goes wrong:** Invalid namespace accepted, later fails at PolicyHead creation
**Why it happens:** Validation deferred to finalization
**How to avoid:** Validate namespace format AND WitnessSet existence at submission time
**Warning signs:** InputInvalidError at finalization instead of submission

### Pitfall 8: State Machine Transition Errors
**What goes wrong:** Status doesn't update correctly (stuck in PENDING, skips COLLECTING)
**Why it happens:** Complex conditional logic for state transitions
**How to avoid:** Clear state transition rules:
  - PENDING -> COLLECTING: first signature added
  - COLLECTING -> THRESHOLD_MET: signature count >= threshold
  - THRESHOLD_MET -> FINALIZED: finalize_promotion called
  - Any -> REJECTED: explicit rejection (future feature)
**Warning signs:** finalize_promotion succeeds in COLLECTING state

## Code Examples

Verified patterns from official sources:

### Existing Error Handling Pattern
```python
# Source: src/decisiongraph/exceptions.py lines 141-178
class UnauthorizedError(DecisionGraphError):
    """
    Access denied.
    Raised when an operation is not permitted.
    """
    code: str = "DG_UNAUTHORIZED"

class SignatureInvalidError(DecisionGraphError):
    """
    Cryptographic signature invalid or missing.
    """
    code: str = "DG_SIGNATURE_INVALID"

# Usage in promotion workflow:
raise UnauthorizedError(
    message="Witness not in WitnessSet",
    details={"witness_id": witness_id, "namespace": namespace}
)

raise SignatureInvalidError(
    message="Signature verification failed",
    details={"witness_id": witness_id, "promotion_id": promotion_id}
)
```

### Existing Signature Verification Pattern
```python
# Source: src/decisiongraph/signing.py lines 100-189
def verify_signature(public_key: bytes, data: bytes, signature: bytes) -> bool:
    """
    Verify Ed25519 signature.

    Returns True if valid, False if verification fails.
    Note: Verification failure returns False, not exception.
    Only format errors raise SignatureInvalidError.
    """
    # Format validation (raises SignatureInvalidError)
    if len(public_key) != 32:
        raise SignatureInvalidError(...)
    if len(signature) != 64:
        raise SignatureInvalidError(...)

    # Verification (returns bool)
    try:
        key.verify(signature, data)
        return True
    except InvalidSignature:
        return False  # NOT an exception - normal control flow

# CORRECT usage:
is_valid = verify_signature(pub_key, payload, signature)
if not is_valid:
    raise SignatureInvalidError(message="...", details={...})

# WRONG usage (will not work):
try:
    verify_signature(pub_key, payload, signature)  # No exception on invalid
except:
    handle_error()  # Never reached for invalid signature
```

### Existing WitnessRegistry Pattern
```python
# Source: src/decisiongraph/registry.py lines 112-147
def get_witness_set(self, namespace: str) -> Optional[WitnessSet]:
    """
    Get the current WitnessSet for a namespace.

    Returns None if no WitnessSet configured.
    """
    witness_sets = self._build_registry()
    return witness_sets.get(namespace)

# Usage:
registry = WitnessRegistry(chain)
ws = registry.get_witness_set("corp")
if ws is None:
    raise InputInvalidError("No WitnessSet for namespace")
if witness_id not in ws.witnesses:
    raise UnauthorizedError("Witness not authorized")
```

### Existing PolicyHead Creation Pattern
```python
# Source: src/decisiongraph/policyhead.py lines 69-175
def create_policy_head(
    namespace: str,
    promoted_rule_ids: List[str],
    graph_id: str,
    prev_cell_hash: str,
    prev_policy_head: Optional[str] = None,
    system_time: Optional[str] = None,
    creator: Optional[str] = None,
    bootstrap_mode: bool = True
) -> DecisionCell:
    """
    Create a PolicyHead cell for a namespace.

    - policy_hash computed from sorted promoted_rule_ids
    - prev_policy_head links to previous PolicyHead (None for first)
    - Policy data stored as JSON in fact.object
    """
    # Validate namespace
    if not validate_namespace(namespace):
        raise ValueError(f"Invalid namespace: {namespace}")

    # Compute deterministic policy_hash
    policy_hash = compute_policy_hash(promoted_rule_ids)
    sorted_rule_ids = sorted(promoted_rule_ids)

    # ... creates DecisionCell with CellType.POLICY_HEAD
```

### Existing Engine Pattern for New Methods
```python
# Source: src/decisiongraph/engine.py lines 43-80
class Engine:
    """
    The Engine is the validated entry point for DecisionGraph queries.
    """

    def __init__(
        self,
        chain: Chain,
        signing_key: Optional[bytes] = None,
        public_key: Optional[bytes] = None,
        verify_cell_signatures: bool = False
    ):
        self.chain = chain
        self.scholar = create_scholar(chain)
        self.signing_key = signing_key
        self.public_key = public_key
        self.verify_cell_signatures = verify_cell_signatures
        # Extend __init__ to add:
        # self._promotions: Dict[str, PromotionRequest] = {}
        # self._registry = WitnessRegistry(chain)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FROST threshold signatures | Independent Ed25519 signatures | v1.5 design | Simpler, leverages existing signing.py |
| Single-step promotion | Three-phase (Submit -> Collect -> Finalize) | v1.5 design | Clear workflow, atomic finalization |
| WitnessSet promotion first | Genesis-embedded WitnessSet | v1.5 Phase 1 | Bootstrap paradox solved |
| Custom workflow cells | In-memory state machine | v1.5 design | Only finalized state on chain |

**Deprecated/outdated:**
- FROST multi-sig: Not needed; independent signatures with threshold count work for this use case
- Real-time consensus: Asynchronous signature collection is sufficient for policy changes
- On-chain promotion state: Too complex; in-memory with atomic finalization is simpler

## Open Questions

Things that couldn't be fully resolved:

1. **Witness Public Key Storage**
   - What we know: signing.py has generate_ed25519_keypair() and verify_signature()
   - What's unclear: Where are witness public keys stored? Not in WitnessSet currently.
   - Recommendation: For Phase 4, require public_key passed with signature OR add public_key to WitnessSet in a follow-up. For now, tests can use generated keypairs. Document as INT-01 dependency.

2. **Promotion Timeout/Expiry**
   - What we know: REQUIREMENTS.md lists "Promotion timeout and escalation workflows" as v2
   - What's unclear: Should Phase 4 implement basic timeout?
   - Recommendation: NO timeout in Phase 4. Mark status REJECTED only on explicit rejection. Timeout is v2 scope.

3. **Concurrent Promotions for Same Namespace**
   - What we know: Multiple promotions can be active for same namespace
   - What's unclear: What happens if two reach THRESHOLD_MET? Both finalize?
   - Recommendation: Both CAN finalize. Chain.append validates prev_cell_hash, so they chain correctly. PolicyHead chain tracks all promotions. No conflict - each creates its own PolicyHead.

4. **Witness Signature Storage Format**
   - What we know: Ed25519 signatures are 64 bytes
   - What's unclear: Should signatures be stored in PromotionRequest as raw bytes or base64?
   - Recommendation: Raw bytes internally (Dict[str, bytes]). Base64 for API boundaries only if needed. Matches signing.py pattern.

## Sources

### Primary (HIGH confidence)
- `src/decisiongraph/signing.py` - Ed25519 sign/verify implementation (lines 36-190)
- `src/decisiongraph/policyhead.py` - create_policy_head(), get_current_policy_head() (lines 69-420)
- `src/decisiongraph/registry.py` - WitnessRegistry.get_witness_set() (lines 52-187)
- `src/decisiongraph/witnessset.py` - WitnessSet frozen dataclass (lines 34-109)
- `src/decisiongraph/engine.py` - Engine class, process_rfa() pattern (lines 43-188)
- `src/decisiongraph/exceptions.py` - UnauthorizedError, SignatureInvalidError (lines 141-178)
- `.planning/REQUIREMENTS.md` - PRO-01 through PRO-06 requirements
- `.planning/STATE.md` - Prior decisions (Independent Ed25519, Three-Phase Promotion)

### Secondary (MEDIUM confidence)
- `tests/test_signing.py` - Ed25519 test patterns (lines 1-100)
- `tests/test_witnessset.py` - WitnessSet validation patterns (lines 1-100)
- `.planning/phases/01-policyhead-foundation/01-RESEARCH.md` - PolicyHead patterns

### Tertiary (LOW confidence)
- None - all findings verified with source code

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in use, patterns from existing code
- Architecture: HIGH - Derived from existing Engine, signing, registry patterns
- Pitfalls: HIGH - Based on explicit v1.4 decisions (verify_signature returns bool) and state machine edge cases

**Research date:** 2026-01-28
**Valid until:** 60 days (stable architecture, patterns well-established)
