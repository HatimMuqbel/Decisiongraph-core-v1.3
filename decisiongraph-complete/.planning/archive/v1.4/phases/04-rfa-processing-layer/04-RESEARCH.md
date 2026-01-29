# Phase 4: RFA Processing Layer - Research

**Researched:** 2026-01-27
**Domain:** Request-For-Authorization (RFA) processing pipeline with validation, signing, and proof generation
**Confidence:** HIGH

## Summary

This research investigated how to implement the RFA (Request-For-Authorization) processing layer that provides a single validated entry point to DecisionGraph. The goal is to create `engine.process_rfa(rfa_dict)` which orchestrates input canonicalization, schema validation, field validation, Scholar query execution, proof bundle generation, and optional cryptographic signing.

The RFA layer is the **external API boundary** that wraps the existing v1.3 engine (Scholar, Chain, Namespace). It transforms raw dictionaries into validated queries, catches internal exceptions, maps them to DG_* error codes, and returns either a signed ProofPacket or a DecisionGraphError.

**Key architectural insight:** The RFA layer is a **stateless orchestrator** that doesn't maintain its own state. It accepts a dictionary, validates it, calls Scholar (which reads the Chain), and packages the QueryResult into a ProofPacket. This preserves the existing architecture where Chain is the single source of truth.

**Primary recommendation:** Create an `Engine` class with `process_rfa()` method that implements a 7-step pipeline: (1) canonicalize input, (2) validate RFA schema, (3) validate field formats, (4) call Scholar.query_facts(), (5) generate ProofBundle from QueryResult, (6) wrap in ProofPacket with metadata, (7) optionally sign ProofPacket. Create a `ProofPacket` dataclass to represent the final signed output.

---

## What Do I Need to Know to PLAN This Phase Well?

### 1. RFA Schema Design

**What is an RFA?**
An RFA (Request-For-Authorization) is the standardized input format for querying DecisionGraph. It's a dictionary containing:

```python
rfa_dict = {
    "namespace": "corp.hr.compensation",    # Target namespace
    "subject": "employee:jane_doe",         # Subject filter (optional)
    "predicate": "has_salary",              # Predicate filter (optional)
    "object": None,                         # Object filter (optional)
    "requester_namespace": "corp.hr",       # Who is asking
    "requester_id": "user:alice",           # Identity for audit
    "at_valid_time": "2026-01-27T12:00:00Z", # Bitemporal coordinate (optional)
    "as_of_system_time": "2026-01-27T12:00:00Z", # Bitemporal coordinate (optional)
}
```

**Required vs Optional Fields:**
- **Required:** `namespace`, `requester_namespace`, `requester_id`
- **Optional:** `subject`, `predicate`, `object`, `at_valid_time`, `as_of_system_time`

**Why this schema?**
This maps directly to `Scholar.query_facts()` parameters (see scholar.py:703-713). The RFA is a thin validation wrapper around Scholar's existing API.

---

### 2. ProofPacket vs ProofBundle

**Critical distinction:**

| Concept | What It Is | Who Creates It | What It Contains |
|---------|-----------|----------------|------------------|
| **QueryResult** | Scholar's internal result object | `Scholar.query_facts()` | facts, candidates, bridges_used, resolution_events, authorization |
| **ProofBundle** | Deterministic audit record | `QueryResult.to_proof_bundle()` | Canonical dict with sorted lists, ready for hashing/signing |
| **ProofPacket** | External API response | `engine.process_rfa()` | ProofBundle + metadata + optional engine signature |

**ProofBundle structure (already exists in Scholar):**
```python
proof_bundle = {
    "query": {
        "namespace_scope": "corp.hr",
        "requester_id": "user:alice",
        # ...
    },
    "results": {
        "fact_count": 1,
        "fact_cell_ids": ["abc123..."],
        # ...
    },
    "proof": {
        "candidates_considered": 2,
        "candidate_cell_ids": ["abc123...", "def456..."],
        "bridges_used": ["bridge789..."],
        "resolution_events": [...],
        # ...
    },
    "time_filters": {
        "at_valid_time": "2026-01-27T12:00:00Z",
        "as_of_system_time": "2026-01-27T12:00:00Z"
    },
    "authorization_basis": {
        "allowed": true,
        "reason": "same_namespace",
        "bridges_used": [],
        "bridge_effectiveness": []
    },
    "scholar_version": "1.3"
}
```

**ProofPacket structure (NEW in Phase 4):**
```python
proof_packet = {
    "packet_version": "1.4",
    "packet_id": "uuid-v4",
    "generated_at": "2026-01-27T12:00:00.123Z",
    "graph_id": "graph:...",
    "proof_bundle": { ... },  # The canonical bundle from Scholar
    "signature": {            # NEW: Engine signature (SIG-04)
        "algorithm": "Ed25519",
        "public_key": "base64...",  # Engine's public key
        "signature": "base64...",   # Signature of canonical proof_bundle
        "signed_at": "2026-01-27T12:00:00.123Z"
    }
}
```

**Why separate ProofBundle and ProofPacket?**
- **ProofBundle** is deterministic and canonical (same query = same bundle). It can be signed.
- **ProofPacket** adds transport metadata (packet_id, generated_at, signature). It's the final response.
- This separation allows external verifiers to extract the ProofBundle, verify the signature, and independently verify the proof.

---

### 3. Canonicalization Strategy (RFA-03)

**Requirement:** RFA canonicalizes input to deterministic JSON before validation.

**Why canonicalize?**
- Prevents signature bypass via field reordering
- Ensures deterministic hashing
- Normalizes whitespace/encoding

**Standard approach in Python:**
```python
import json

def canonicalize_rfa(rfa_dict: dict) -> dict:
    """
    Canonicalize RFA dict to deterministic form.

    Operations:
    1. Strip whitespace from string values
    2. Sort dictionary keys alphabetically
    3. Remove null/None values (optional fields)
    4. Validate top-level structure
    """
    # Convert to JSON with sorted keys, then back to dict
    # This ensures deterministic key ordering
    canonical_json = json.dumps(rfa_dict, sort_keys=True, separators=(',', ':'))
    canonical_dict = json.loads(canonical_json)

    # Strip whitespace from string values
    for key, value in canonical_dict.items():
        if isinstance(value, str):
            canonical_dict[key] = value.strip()

    # Remove None values (only keep explicitly provided fields)
    canonical_dict = {k: v for k, v in canonical_dict.items() if v is not None}

    return canonical_dict
```

**Tradeoff:** Full JSON canonicalization (like RFC 8785 JCS) is complex. For Phase 4, **simple key sorting + whitespace stripping** is sufficient. Advanced canonicalization can be Phase 5+ if needed.

---

### 4. Schema Validation (RFA-02)

**Requirement:** RFA pipeline validates schema (required fields present) before processing.

**What to validate:**
```python
def validate_rfa_schema(rfa: dict) -> None:
    """
    Validate RFA schema before processing.

    Raises:
        SchemaInvalidError: If required fields missing or wrong types
    """
    # Required fields
    required = ["namespace", "requester_namespace", "requester_id"]
    missing = [f for f in required if f not in rfa]
    if missing:
        raise SchemaInvalidError(
            message=f"Missing required fields: {', '.join(missing)}",
            details={"missing_fields": missing, "provided_fields": list(rfa.keys())}
        )

    # Type validation
    for field in required:
        if not isinstance(rfa[field], str):
            raise SchemaInvalidError(
                message=f"Field '{field}' must be a string",
                details={"field": field, "actual_type": type(rfa[field]).__name__}
            )

    # Optional fields type validation
    optional_str = ["subject", "predicate", "object", "at_valid_time", "as_of_system_time"]
    for field in optional_str:
        if field in rfa and rfa[field] is not None and not isinstance(rfa[field], str):
            raise SchemaInvalidError(
                message=f"Field '{field}' must be a string or null",
                details={"field": field, "actual_type": type(rfa[field]).__name__}
            )
```

**Why separate schema and field validation?**
- **Schema validation** (RFA-02): Structural correctness (fields exist, types correct)
- **Field validation** (VAL-01/02/03): Content correctness (patterns match, lengths valid)

This separation provides clearer error messages: "missing field" vs "invalid format".

---

### 5. Field Validation Integration (VAL-01/02/03)

**What we already have (from Phase 2):**
- `validate_subject_field(subject)` - VAL-01
- `validate_predicate_field(predicate)` - VAL-02
- `validate_object_field(obj)` - VAL-03

**How to integrate with RFA pipeline:**
```python
def validate_rfa_fields(rfa: dict) -> None:
    """
    Validate RFA field contents using Phase 2 validators.

    Raises:
        InputInvalidError: If field validation fails
    """
    # Namespace validation (existing function from cell.py)
    from .cell import validate_namespace
    if not validate_namespace(rfa["namespace"]):
        raise InputInvalidError(
            message=f"Invalid namespace: {rfa['namespace']}",
            details={"field": "namespace", "value": rfa["namespace"]}
        )

    if not validate_namespace(rfa["requester_namespace"]):
        raise InputInvalidError(
            message=f"Invalid requester_namespace: {rfa['requester_namespace']}",
            details={"field": "requester_namespace", "value": rfa["requester_namespace"]}
        )

    # Subject validation (optional field)
    if rfa.get("subject"):
        validate_subject_field(rfa["subject"], field_name="subject")

    # Predicate validation (optional field)
    if rfa.get("predicate"):
        validate_predicate_field(rfa["predicate"], field_name="predicate")

    # Object validation (optional field)
    if rfa.get("object"):
        validate_object_field(rfa["object"], field_name="object")

    # Timestamp validation (optional fields)
    if rfa.get("at_valid_time"):
        if not validate_timestamp(rfa["at_valid_time"]):
            raise InputInvalidError(
                message=f"Invalid at_valid_time format",
                details={"field": "at_valid_time", "value": rfa["at_valid_time"]}
            )

    if rfa.get("as_of_system_time"):
        if not validate_timestamp(rfa["as_of_system_time"]):
            raise InputInvalidError(
                message=f"Invalid as_of_system_time format",
                details={"field": "as_of_system_time", "value": rfa["as_of_system_time"]}
            )
```

**Key insight:** We reuse existing validators. No new validation logic needed, just orchestration.

---

### 6. Signature Integration (SIG-03/04)

**Two signature requirements:**

#### SIG-03: Commit Gate Cell Signature Verification
"Commit Gate optionally verifies cell signatures when `signature_required=True`"

**Where this happens:** During `Chain.append()` in the Commit Gate.

**Implementation approach:**
```python
# In chain.py, modify the append() method
def append(self, cell: DecisionCell, verify_signatures: bool = False) -> None:
    """
    Append a cell to the chain.

    Args:
        cell: Cell to append
        verify_signatures: If True, verify cell signature if signature_required=True
    """
    # Existing validations...

    # NEW: Signature verification (SIG-03)
    if verify_signatures and cell.proof.signature_required:
        if not cell.proof.signature:
            raise SignatureInvalidError(
                message="Cell requires signature but none provided",
                details={"cell_id": cell.cell_id[:32], "signature_required": True}
            )

        # Verify signature
        from .signing import verify_signature
        canonical_bytes = self._compute_canonical_cell_bytes(cell)

        if not verify_signature(
            public_key=cell.proof.signer_key_id,  # Need to resolve key
            data=canonical_bytes,
            signature=cell.proof.signature
        ):
            raise SignatureInvalidError(
                message="Cell signature verification failed",
                details={"cell_id": cell.cell_id[:32]}
            )

    # Continue with append...
```

**Challenge:** Where do we get the public key? Options:
1. **Key registry in Chain:** Chain maintains a dict of `key_id -> public_key_bytes`
2. **Pass key resolver:** Accept `key_resolver: Callable[[str], bytes]` parameter
3. **Bootstrap mode:** If `verify_signatures=False`, skip verification (default for Phase 4)

**Recommendation for Phase 4:** Use **bootstrap mode** (verify_signatures=False by default). Full key management is v2 scope. This satisfies "opt-in but enforceable" principle.

#### SIG-04: ProofPacket Signing
"ProofPacket can be signed by engine and verified by external parties"

**Implementation:**
```python
class Engine:
    def __init__(
        self,
        chain: Chain,
        signing_key: Optional[bytes] = None,
        public_key: Optional[bytes] = None
    ):
        self.chain = chain
        self.scholar = create_scholar(chain)
        self.signing_key = signing_key
        self.public_key = public_key

    def process_rfa(self, rfa_dict: dict) -> dict:
        """Process RFA and return ProofPacket."""
        # ... validation and query ...

        # Build ProofPacket
        proof_packet = {
            "packet_version": "1.4",
            "packet_id": str(uuid.uuid4()),
            "generated_at": get_current_timestamp(),
            "graph_id": self.chain.graph_id,
            "proof_bundle": proof_bundle,
            "signature": None
        }

        # Sign if key provided (SIG-04)
        if self.signing_key:
            canonical_bundle_bytes = json.dumps(
                proof_bundle, sort_keys=True, separators=(',', ':')
            ).encode('utf-8')

            signature = sign_bytes(self.signing_key, canonical_bundle_bytes)

            proof_packet["signature"] = {
                "algorithm": "Ed25519",
                "public_key": base64.b64encode(self.public_key).decode('ascii'),
                "signature": base64.b64encode(signature).decode('ascii'),
                "signed_at": get_current_timestamp()
            }

        return proof_packet
```

**External verification:**
```python
def verify_proof_packet(proof_packet: dict, engine_public_key: bytes) -> bool:
    """
    Verify ProofPacket signature.

    Args:
        proof_packet: The packet returned by process_rfa()
        engine_public_key: Engine's public key (32 bytes)

    Returns:
        True if signature valid, False otherwise
    """
    if not proof_packet.get("signature"):
        return False  # Unsigned packet

    # Extract signature
    sig_info = proof_packet["signature"]
    signature = base64.b64decode(sig_info["signature"])

    # Reconstruct canonical bytes
    proof_bundle = proof_packet["proof_bundle"]
    canonical_bytes = json.dumps(
        proof_bundle, sort_keys=True, separators=(',', ':')
    ).encode('utf-8')

    # Verify
    return verify_signature(engine_public_key, canonical_bytes, signature)
```

---

### 7. Pipeline Architecture

**The 7-step process_rfa() pipeline:**

```python
def process_rfa(self, rfa_dict: dict) -> dict:
    """
    Process Request-For-Authorization and return ProofPacket.

    Pipeline:
    1. Canonicalize input (RFA-03)
    2. Validate schema (RFA-02)
    3. Validate field formats (VAL-01/02/03)
    4. Query Scholar
    5. Generate ProofBundle
    6. Wrap in ProofPacket
    7. Sign packet (SIG-04)

    Returns:
        ProofPacket dict (signed if signing key provided)

    Raises:
        SchemaInvalidError: Missing/invalid schema
        InputInvalidError: Invalid field format
        UnauthorizedError: Access denied
        IntegrityFailError: Chain integrity issue
        SignatureInvalidError: Signature verification failed
        InternalError: Unexpected error
    """
    try:
        # Step 1: Canonicalize (RFA-03)
        canonical_rfa = self._canonicalize_rfa(rfa_dict)

        # Step 2: Validate schema (RFA-02)
        self._validate_rfa_schema(canonical_rfa)

        # Step 3: Validate fields (VAL-01/02/03)
        self._validate_rfa_fields(canonical_rfa)

        # Step 4: Query Scholar
        result = self.scholar.query_facts(
            requester_namespace=canonical_rfa["requester_namespace"],
            namespace=canonical_rfa["namespace"],
            subject=canonical_rfa.get("subject"),
            predicate=canonical_rfa.get("predicate"),
            object_value=canonical_rfa.get("object"),
            at_valid_time=canonical_rfa.get("at_valid_time"),
            as_of_system_time=canonical_rfa.get("as_of_system_time"),
            requester_id=canonical_rfa["requester_id"]
        )

        # Step 5: Generate ProofBundle (already exists on QueryResult)
        proof_bundle = result.to_proof_bundle()

        # Step 6: Wrap in ProofPacket
        proof_packet = self._create_proof_packet(proof_bundle)

        # Step 7: Sign if key provided (SIG-04)
        if self.signing_key:
            proof_packet = self._sign_proof_packet(proof_packet)

        return proof_packet

    except (SchemaInvalidError, InputInvalidError, UnauthorizedError,
            IntegrityFailError, SignatureInvalidError, InternalError):
        # DecisionGraphError subclasses - re-raise as-is
        raise

    except (ChainError, NamespaceError, GenesisError) as e:
        # Internal exceptions - wrap using EXCEPTION_MAP
        raise wrap_internal_exception(e, details={"rfa": rfa_dict}) from e

    except Exception as e:
        # Unexpected error - wrap as InternalError
        raise InternalError(
            message=f"Unexpected error processing RFA: {str(e)}",
            details={"error_type": type(e).__name__, "rfa": rfa_dict}
        ) from e
```

**Why wrap exceptions?**
- Internal exceptions (ChainError, etc.) leak implementation details
- External API should only return DecisionGraphError hierarchy
- Exception chaining (`from e`) preserves traceback for debugging

---

### 8. Engine Class Design

**Should we have an Engine class or standalone function?**

**Option A: Standalone function**
```python
def process_rfa(chain: Chain, rfa_dict: dict, signing_key: Optional[bytes] = None) -> dict:
    """Process RFA and return ProofPacket."""
    pass
```

**Option B: Engine class (RECOMMENDED)**
```python
class Engine:
    """
    DecisionGraph RFA processing engine.

    Provides validated entry point for querying the decision graph.
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

    def process_rfa(self, rfa_dict: dict) -> dict:
        """Process RFA and return ProofPacket."""
        pass
```

**Why Engine class?**
1. **State encapsulation:** Keeps signing keys, Scholar instance, config together
2. **Testability:** Can mock Engine, swap Scholar implementations
3. **Extensibility:** Easy to add `process_batch_rfa()`, `get_metrics()`, etc.
4. **Consistency:** Matches domain language ("the engine processes requests")

**Where does Engine live?**
- New file: `src/decisiongraph/engine.py`
- Exports: `Engine`, `process_rfa` (convenience function that creates Engine)

---

### 9. Error Mapping Strategy

**Which exceptions can Scholar.query_facts() raise?**
Looking at scholar.py, Scholar doesn't raise exceptions directly. It returns QueryResult with `authorization.allowed=False` on access denial.

**Which exceptions can Chain operations raise?**
- `IntegrityViolation` → `IntegrityFailError` (already mapped)
- `ChainBreak` → `IntegrityFailError`
- `GraphIdMismatch` → `IntegrityFailError`
- `GenesisViolation` → `SchemaInvalidError`

**Error mapping locations:**

| Phase | What Raises | Maps To |
|-------|------------|---------|
| Canonicalization | JSON decode error | `SchemaInvalidError` |
| Schema validation | Missing fields | `SchemaInvalidError` |
| Field validation | Pattern mismatch | `InputInvalidError` (already raises this) |
| Scholar query | Access denied | Check `authorization.allowed`, raise `UnauthorizedError` |
| Signing | Invalid key | `SignatureInvalidError` (already raises this) |

**Special case: Access denied**
Scholar returns `QueryResult` with empty facts and `authorization.allowed=False`. We should detect this and raise UnauthorizedError:

```python
# After Scholar query
if not result.authorization.allowed:
    raise UnauthorizedError(
        message=f"Access denied: {result.authorization.reason}",
        details={
            "requester_namespace": canonical_rfa["requester_namespace"],
            "target_namespace": canonical_rfa["namespace"],
            "reason": result.authorization.reason,
            "bridges_used": result.authorization.bridges_used
        }
    )
```

**Should we always raise on access denial?**
**NO.** Access denial is a valid outcome. The ProofPacket should include the authorization_basis showing WHY access was denied. This allows external verifiers to audit the denial.

**Revised approach:** Return ProofPacket even on access denial. Let caller decide if `authorization.allowed=False` is an error or expected behavior.

---

### 10. Testing Strategy

**What tests are required?**

From success criteria:
1. ✓ `process_rfa()` with valid RFA returns ProofPacket containing decision and proof bundle
2. ✓ `process_rfa()` with missing required field returns DG_SCHEMA_INVALID
3. ✓ `process_rfa()` with invalid subject/predicate/object returns DG_INPUT_INVALID
4. ✓ ProofPacket can be signed and verified by external party
5. ✓ When `signature_required=True`, unsigned cells are rejected with DG_SIGNATURE_INVALID
6. ✓ Existing 313 tests remain passing

**Test categories:**

### Happy Path Tests
```python
def test_process_rfa_valid_query_returns_proof_packet():
    """Valid RFA returns ProofPacket with proof bundle."""
    pass

def test_process_rfa_includes_scholar_results():
    """ProofPacket includes facts, bridges, resolution events."""
    pass

def test_process_rfa_unsigned_packet_when_no_key():
    """ProofPacket.signature is null when Engine has no signing key."""
    pass

def test_process_rfa_signed_packet_when_key_provided():
    """ProofPacket.signature is populated when Engine has signing key."""
    pass
```

### Schema Validation Tests (RFA-02)
```python
def test_process_rfa_missing_namespace_raises_schema_invalid():
    """Missing 'namespace' field raises DG_SCHEMA_INVALID."""
    pass

def test_process_rfa_missing_requester_namespace_raises_schema_invalid():
    """Missing 'requester_namespace' field raises DG_SCHEMA_INVALID."""
    pass

def test_process_rfa_wrong_type_raises_schema_invalid():
    """Providing integer for 'namespace' raises DG_SCHEMA_INVALID."""
    pass
```

### Field Validation Tests (VAL-01/02/03)
```python
def test_process_rfa_invalid_subject_raises_input_invalid():
    """Subject 'USER:alice' raises DG_INPUT_INVALID (uppercase)."""
    pass

def test_process_rfa_invalid_predicate_raises_input_invalid():
    """Predicate 'has salary' raises DG_INPUT_INVALID (space)."""
    pass

def test_process_rfa_invalid_object_raises_input_invalid():
    """Object with control char raises DG_INPUT_INVALID."""
    pass
```

### Signature Tests (SIG-03/04)
```python
def test_verify_proof_packet_valid_signature():
    """verify_proof_packet() returns True for valid signature."""
    pass

def test_verify_proof_packet_invalid_signature():
    """verify_proof_packet() returns False for tampered data."""
    pass

def test_verify_proof_packet_wrong_key():
    """verify_proof_packet() returns False for wrong public key."""
    pass

def test_commit_gate_rejects_unsigned_cell_when_required():
    """Chain.append() raises DG_SIGNATURE_INVALID for unsigned cell with signature_required=True."""
    pass
```

### Integration Tests
```python
def test_process_rfa_end_to_end_with_bridge():
    """Full pipeline: RFA → validation → Scholar → ProofPacket with bridge."""
    pass

def test_process_rfa_deterministic_output():
    """Same RFA produces identical ProofPacket (excluding packet_id/timestamps)."""
    pass
```

**Total new tests:** ~20-25 tests

---

### 11. Files to Create/Modify

**New files:**
- `src/decisiongraph/engine.py` - Engine class with process_rfa()
- `src/decisiongraph/canonicalize.py` - RFA canonicalization utilities (or inline in engine.py)
- `tests/test_engine.py` - Engine tests
- `tests/test_rfa_validation.py` - RFA schema/field validation tests

**Modified files:**
- `src/decisiongraph/chain.py` - Add signature verification to append() (SIG-03)
- `src/decisiongraph/__init__.py` - Export Engine, process_rfa, verify_proof_packet
- `README.md` - Update with process_rfa() example (if applicable)

**Total files:** 4 new, 3 modified

---

### 12. Dependencies on Previous Phases

**Phase 1 (Error Foundation):**
- ✓ DecisionGraphError hierarchy with 6 subclasses
- ✓ wrap_internal_exception() for mapping exceptions
- **Used by:** All error handling in engine.py

**Phase 2 (Input Validation):**
- ✓ validate_subject_field()
- ✓ validate_predicate_field()
- ✓ validate_object_field()
- **Used by:** RFA field validation step

**Phase 3 (Signing Utilities):**
- ✓ sign_bytes()
- ✓ verify_signature()
- ✓ generate_ed25519_keypair() (for testing)
- **Used by:** ProofPacket signing (SIG-04), cell verification (SIG-03)

**Existing v1.3:**
- ✓ Scholar.query_facts()
- ✓ QueryResult.to_proof_bundle()
- ✓ Chain, Cell, Namespace modules
- **Used by:** Core query execution

---

### 13. Open Questions & Decisions Needed

#### Q1: Should process_rfa() raise exception on access denial?
**Options:**
A. Raise `UnauthorizedError` when `authorization.allowed=False`
B. Return ProofPacket with `authorization.allowed=False`, let caller decide

**Recommendation:** **Option B**. Access denial is a valid outcome that should be auditable. The ProofPacket includes the authorization_basis explaining WHY access was denied. This enables:
- Audit: "User X tried to access namespace Y but was denied because Z"
- Debugging: "Let me see the proof bundle to understand what went wrong"
- Flexibility: Caller can check `proof_packet["proof_bundle"]["authorization_basis"]["allowed"]`

#### Q2: Where to store Engine signing keys?
**Options:**
A. Pass keys to Engine.__init__()
B. Load from environment variables
C. Load from file path

**Recommendation for Phase 4:** **Option A** (pass to __init__). Key management is v2 scope. For Phase 4, tests can use `generate_ed25519_keypair()` to create test keys.

#### Q3: Should we support batch RFAs (list of RFAs)?
**Recommendation:** **No, not in Phase 4.** Single RFA processing first. Batch can be Phase 5+ feature.

#### Q4: What's the format for ProofPacket signature encoding?
**Options:**
A. Raw bytes (consistent with signing.py)
B. Base64 string (easier for JSON transport)
C. Hex string

**Recommendation:** **Base64** for ProofPacket (external API), raw bytes internally. Reason: ProofPacket is JSON, base64 is JSON-safe.

#### Q5: Should ProofPacket be a dataclass or plain dict?
**Options:**
A. Plain dict (matches proof_bundle)
B. Dataclass with to_dict() method
C. Pydantic model

**Recommendation:** **Plain dict**. Keep it simple. ProofPacket is the output format, not an internal data structure. Returning a dict makes it directly JSON-serializable.

---

## Standard Stack

### Core Libraries
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| json | stdlib | Canonicalization, ProofPacket serialization | Universal JSON handling, supports sort_keys |
| uuid | stdlib | Generate packet_id | Standard for unique IDs |
| base64 | stdlib | Encode signatures for JSON transport | Standard encoding for binary data |
| typing | stdlib | Type hints for Engine API | Static analysis support |

### Existing DecisionGraph Modules
| Module | Purpose | Used For |
|--------|---------|----------|
| exceptions | Error codes | All exception handling |
| validators | Field validation | RFA field validation |
| signing | Ed25519 sign/verify | ProofPacket signing, cell signature verification |
| scholar | Query engine | Core query execution |
| cell | Cell structures | Timestamp validation, namespace validation |
| chain | Chain management | graph_id access, append with signature verification |

**No new external dependencies needed.** All required functionality exists in stdlib or existing modules.

---

## Architecture Patterns

### Pattern 1: Pipeline Architecture
**What:** Sequence of independent validation/transformation steps
**Why:** Each step has single responsibility, easy to test, clear failure points
**Example:**
```python
def process_rfa(self, rfa_dict: dict) -> dict:
    canonical = self._canonicalize_rfa(rfa_dict)     # Step 1
    self._validate_schema(canonical)                  # Step 2
    self._validate_fields(canonical)                  # Step 3
    result = self._query_scholar(canonical)           # Step 4
    bundle = result.to_proof_bundle()                 # Step 5
    packet = self._wrap_in_packet(bundle)             # Step 6
    return self._sign_if_needed(packet)               # Step 7
```

### Pattern 2: Exception Chaining at API Boundary
**What:** Catch internal exceptions, wrap as DecisionGraphError, preserve traceback
**Why:** Hides implementation details, provides consistent external errors
**Example:**
```python
try:
    result = self.scholar.query_facts(...)
except NamespaceError as e:
    # Map to external error code, preserve traceback
    raise wrap_internal_exception(e, details={...}) from e
```

### Pattern 3: Canonical Representation
**What:** Deterministic JSON serialization (sorted keys, no whitespace)
**Why:** Enables signature verification, reproducible hashes
**Example:**
```python
canonical_json = json.dumps(data, sort_keys=True, separators=(',', ':'))
```

### Pattern 4: Optional Signature Wrapping
**What:** Same data structure, signature field is optional
**Why:** Bootstrap mode (no keys) vs production mode (signed)
**Example:**
```python
packet = {"proof_bundle": bundle, "signature": None}
if self.signing_key:
    packet["signature"] = self._create_signature(bundle)
```

---

## Implementation Recommendations

### File: `src/decisiongraph/engine.py`

**Structure:**
```python
"""
DecisionGraph RFA Processing Engine (v1.4)

Provides validated entry point for querying the decision graph.
"""

import json
import uuid
import base64
from typing import Optional, Dict, Any
from .chain import Chain
from .scholar import create_scholar
from .signing import sign_bytes, verify_signature
from .validators import validate_subject_field, validate_predicate_field, validate_object_field
from .cell import validate_namespace, validate_timestamp, get_current_timestamp
from .exceptions import *

__all__ = [
    'Engine',
    'process_rfa',           # Convenience function
    'verify_proof_packet'
]

class Engine:
    """Main RFA processing engine."""
    pass

def process_rfa(chain: Chain, rfa_dict: dict, signing_key: Optional[bytes] = None,
                public_key: Optional[bytes] = None) -> dict:
    """Convenience function - creates Engine and calls process_rfa()."""
    engine = Engine(chain, signing_key, public_key)
    return engine.process_rfa(rfa_dict)

def verify_proof_packet(proof_packet: dict, engine_public_key: bytes) -> bool:
    """Verify ProofPacket signature."""
    pass
```

### Testing Approach

**Test file structure:**
```python
# tests/test_engine.py
class TestEngineHappyPath:
    """Tests for valid RFA processing."""
    pass

class TestEngineSchemaValidation:
    """Tests for RFA-02 schema validation."""
    pass

class TestEngineFieldValidation:
    """Tests for VAL-01/02/03 field validation."""
    pass

class TestEngineSignatures:
    """Tests for SIG-04 ProofPacket signing."""
    pass

class TestEngineErrorMapping:
    """Tests for exception mapping to DG_* codes."""
    pass

# tests/test_commit_gate_signatures.py
class TestCommitGateSignatureVerification:
    """Tests for SIG-03 cell signature verification."""
    pass
```

**Fixture strategy:**
```python
@pytest.fixture
def test_chain():
    """Chain with genesis + some facts."""
    return create_chain(...)

@pytest.fixture
def test_engine(test_chain):
    """Engine without signing key."""
    return Engine(test_chain)

@pytest.fixture
def test_engine_with_key(test_chain):
    """Engine with signing key."""
    priv, pub = generate_ed25519_keypair()
    return Engine(test_chain, signing_key=priv, public_key=pub)

@pytest.fixture
def valid_rfa():
    """Valid RFA dict for testing."""
    return {
        "namespace": "corp.hr",
        "requester_namespace": "corp.hr",
        "requester_id": "user:alice"
    }
```

---

## Risk Analysis

### HIGH RISK: ProofBundle immutability
**Risk:** If ProofBundle format changes between Scholar call and signature, signature becomes invalid.
**Mitigation:**
- ProofBundle format is already stable (v1.3)
- Sign the exact bytes returned by `to_proof_bundle()`
- Add test: "re-serialize proof_bundle doesn't change bytes"

### MEDIUM RISK: Canonicalization inconsistency
**Risk:** Different Python versions might serialize JSON differently.
**Mitigation:**
- Use explicit separators: `separators=(',', ':')`
- Test on Python 3.10, 3.11, 3.12
- Document required Python version (3.10+)

### MEDIUM RISK: Timestamp precision
**Risk:** get_current_timestamp() might have different precision across calls.
**Impact:** packet_id and generated_at might differ even for identical queries.
**Resolution:** This is OK. packet_id and generated_at are metadata, not part of proof. The proof_bundle is deterministic.

### LOW RISK: Base64 encoding consistency
**Risk:** base64 might add newlines on some platforms.
**Mitigation:** Use `.decode('ascii')` which strips newlines.

---

## Performance Considerations

**Bottlenecks:**
1. **JSON serialization:** For large ProofBundles (100+ facts), json.dumps() could be slow
2. **Signature computation:** Ed25519 signing is ~50µs, negligible
3. **Scholar query:** Most time spent here (existing code)

**Optimizations for Phase 4:**
- None needed. Profile after implementation if performance issues arise.

**Future optimizations (v2+):**
- Cache canonicalized RFAs (LRU cache keyed by RFA hash)
- Lazy signature computation (only sign if requested)
- Parallel batch RFA processing

---

## Success Metrics

**How do we know Phase 4 is complete?**

1. ✅ All 6 success criteria pass:
   - Valid RFA → ProofPacket with proof bundle
   - Missing field → DG_SCHEMA_INVALID
   - Invalid field → DG_INPUT_INVALID
   - ProofPacket can be signed and verified
   - unsigned cells rejected when signature_required=True
   - All 313 existing tests pass

2. ✅ All 5 requirements implemented:
   - RFA-01: process_rfa() returns ProofPacket or error
   - RFA-02: Schema validation before processing
   - RFA-03: Input canonicalization
   - SIG-03: Cell signature verification in Commit Gate
   - SIG-04: ProofPacket signing and verification

3. ✅ Test coverage:
   - ~20-25 new tests
   - All error paths covered
   - Signature verification tested with tampered data

4. ✅ Documentation:
   - engine.py has comprehensive docstrings
   - Examples in tests/test_engine.py show usage patterns
   - Error messages are actionable

---

## Glossary

**RFA (Request-For-Authorization):** Input dictionary containing query parameters (namespace, subject, predicate, etc.)

**ProofBundle:** Canonical audit record from Scholar, deterministically generated from QueryResult

**ProofPacket:** External API response containing ProofBundle + metadata + optional signature

**Canonicalization:** Transforming data to deterministic form (sorted keys, normalized whitespace)

**Commit Gate:** Validation layer in Chain that verifies cells before appending (includes signature verification)

**Bootstrap mode:** Operation without cryptographic signatures (for development/testing)

---

*Last updated: 2026-01-27*
