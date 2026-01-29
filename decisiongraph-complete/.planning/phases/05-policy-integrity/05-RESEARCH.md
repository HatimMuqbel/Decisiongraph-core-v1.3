# Phase 5: Policy Integrity - Research

**Researched:** 2026-01-28
**Domain:** Cryptographic verification, policy hash integrity, promotion validation
**Confidence:** HIGH

## Summary

This research investigates what is needed to implement Policy Integrity (INT-01 through INT-04) for DecisionGraph v1.5. The phase focuses on making PolicyHead cells cryptographically verifiable and protecting against tampering and invalid operations.

The codebase already has substantial infrastructure in place:
1. **PolicyHead cells exist** with `policy_hash` computed as SHA-256 of sorted `promoted_rule_ids`
2. **Signature infrastructure exists** via Ed25519 in `signing.py` with `verify_signature()`
3. **Promotion workflow exists** with threshold checking in `finalize_promotion()`
4. **Error codes are standardized** (DG_INPUT_INVALID, DG_UNAUTHORIZED, etc.)

The primary gaps are:
1. **INT-01:** PolicyHead cells are created without cryptographic signatures (bootstrap mode)
2. **INT-02:** `verify_policy_hash()` exists but is not enforced at append time
3. **INT-03:** No namespace validation for rule_ids in `submit_promotion()`
4. **INT-04:** Already implemented in `finalize_promotion()` - raises DG_UNAUTHORIZED
5. **Concurrent promotion detection:** No prev_policy_head validation at finalize time

**Primary recommendation:** Add validation checks at appropriate points in the promotion workflow, leveraging existing verification infrastructure.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| cryptography | 41.0+ | Ed25519 signing/verification | Already in use for signing.py |
| hashlib | stdlib | SHA-256 for policy_hash | Already used in cell.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json | stdlib | Canonical JSON serialization | Already used for policy data |
| dataclasses | stdlib | Immutable data structures | Already used for Cell, PromotionRequest |

**No new dependencies required.** All necessary cryptographic and hashing infrastructure already exists.

## Architecture Patterns

### Current PolicyHead Creation Flow
```
submit_promotion(namespace, rule_ids, submitter_id)
    |
    v
PromotionRequest created (PENDING status)
    |
    v
collect_witness_signature(promotion_id, witness_id, signature, public_key)
    |-- Authorization check (witness in WitnessSet)
    |-- Signature verification (Ed25519)
    v
Status updates: PENDING -> COLLECTING -> THRESHOLD_MET
    |
    v
finalize_promotion(promotion_id)
    |-- Threshold check (INT-04 - ALREADY EXISTS)
    |-- Create PolicyHead cell
    |-- Append to chain
    v
PolicyHead on chain (FINALIZED status)
```

### Recommended Validation Points

**INT-01 (PolicyHead signature verification):**
- PolicyHead cells currently have `signature=None` and `signature_required=False`
- To verify: PolicyHead must be signed at creation or include witness signatures
- Decision: Store aggregated witness signatures OR sign at finalization

**INT-02 (policy_hash verification):**
- `verify_policy_hash()` already exists in policyhead.py
- Call at Chain.append() or at finalize_promotion() before append
- Recommended: Verify at finalize_promotion() before creating cell

**INT-03 (namespace validation for rule_ids):**
- Must check that all rule_ids belong to the same namespace as promotion
- Validation point: `submit_promotion()` or `finalize_promotion()`
- Recommended: `submit_promotion()` - fail fast

**INT-04 (threshold enforcement):**
- Already implemented in `finalize_promotion()` lines 554-563
- Raises UnauthorizedError if status != THRESHOLD_MET

**Concurrent promotion detection:**
- At finalize time, check if prev_policy_head has changed since submit
- Get current PolicyHead, compare to expected
- If different, another promotion was finalized - race condition

### Pattern 1: Fail-Fast Namespace Validation
**What:** Validate rule namespace at submit time, not finalize time
**When to use:** Always - prevents wasted witness signatures
**Example:**
```python
def submit_promotion(self, namespace: str, rule_ids: List[str], ...):
    # Validate each rule_id belongs to namespace
    for rule_id in rule_ids:
        rule_cell = self.chain.get_cell(rule_id)
        if rule_cell is None:
            raise InputInvalidError(f"Rule {rule_id} not found")
        if rule_cell.fact.namespace != namespace:
            raise InputInvalidError(
                f"Rule {rule_id} is from namespace {rule_cell.fact.namespace}, "
                f"not {namespace}"
            )
```

### Pattern 2: Race Condition Detection via prev_policy_head
**What:** Check for concurrent promotions at finalize time
**When to use:** Multi-user environments where concurrent promotions possible
**Example:**
```python
def finalize_promotion(self, promotion_id: str):
    promotion = self._promotions.get(promotion_id)
    # ... threshold check ...

    # Race detection: check current policy head
    current_policy_head = get_current_policy_head(self.chain, promotion.namespace)
    expected_prev = promotion.expected_prev_policy_head  # Store at submit time

    if current_policy_head and current_policy_head.cell_id != expected_prev:
        raise InputInvalidError(
            f"Concurrent promotion detected. Expected prev_policy_head "
            f"{expected_prev}, but current is {current_policy_head.cell_id}"
        )
```

### Anti-Patterns to Avoid
- **Skipping validation for "trusted" sources:** All promotions must be validated regardless of submitter
- **Validating at wrong time:** Namespace validation should be at submit (fail fast), not finalize (wastes signatures)
- **Silent failures:** All validation failures must raise appropriate DG_* error codes

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Ed25519 verification | Custom crypto | `signing.verify_signature()` | Already tested, handles edge cases |
| Policy hash computation | Custom hash | `compute_policy_hash()` | Deterministic, already canonical |
| Threshold checking | Custom counter | Existing `finalize_promotion()` logic | Already handles edge cases |
| Error codes | Custom exceptions | Existing DG_* exceptions | Consistent with v1.4 API |

**Key insight:** The infrastructure exists. Phase 5 is about adding validation calls, not building new systems.

## Common Pitfalls

### Pitfall 1: Signature Verification Order
**What goes wrong:** Verifying signature before authorization check
**Why it happens:** Seems more secure to check crypto first
**How to avoid:** Authorization first, then signature - saves compute and gives better error messages
**Warning signs:** SignatureInvalidError when user isn't even a witness

### Pitfall 2: Race Condition False Positives
**What goes wrong:** Detecting race condition when there isn't one (first promotion)
**Why it happens:** First promotion has no prev_policy_head
**How to avoid:** Handle null prev_policy_head case - only flag race if expected != actual AND expected is not None
**Warning signs:** First promotion for namespace always fails

### Pitfall 3: Namespace Matching Strictness
**What goes wrong:** "corp.hr" rules in "corp" namespace promotion
**Why it happens:** Hierarchical namespace confusion
**How to avoid:** Exact match required: `rule.namespace == promotion.namespace`, not prefix matching
**Warning signs:** Rules from child namespaces sneaking into parent namespace promotions

### Pitfall 4: Bootstrap vs Production Mode Confusion
**What goes wrong:** Enforcing signatures in bootstrap mode, or skipping in production
**Why it happens:** create_policy_head has bootstrap_mode=True by default
**How to avoid:** Mode should be determined by WitnessSet configuration, not hardcoded
**Warning signs:** All tests pass but production fails signature verification

## Code Examples

Verified patterns from existing codebase:

### Existing verify_policy_hash (policyhead.py:332-347)
```python
# Source: policyhead.py
def verify_policy_hash(policy_head: DecisionCell) -> bool:
    """
    Verify that a PolicyHead's policy_hash matches its promoted_rule_ids.
    """
    policy_data = parse_policy_data(policy_head)
    expected_hash = compute_policy_hash(policy_data["promoted_rule_ids"])
    return policy_data["policy_hash"] == expected_hash
```

### Existing threshold check (engine.py:554-563)
```python
# Source: engine.py
# Already implements INT-04
if promotion.status != PromotionStatus.THRESHOLD_MET:
    raise UnauthorizedError(
        message=f"Cannot finalize: status is {promotion.status.value}, need THRESHOLD_MET",
        details={
            "current_status": promotion.status.value,
            "signatures_collected": len(promotion.signatures),
            "threshold_required": promotion.required_threshold
        }
    )
```

### Existing signature verification (engine.py:497-506)
```python
# Source: engine.py
# Already implements PRO-06
is_valid = verify_signature(public_key, promotion.canonical_payload, signature)
if not is_valid:
    raise SignatureInvalidError(
        message=f"Signature verification failed for witness '{witness_id}'",
        details={
            "witness_id": witness_id,
            "promotion_id": promotion_id
        }
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No policy versioning | PolicyHead cells with prev_policy_head chain | v1.5 Phase 1 | Enables bitemporal queries |
| Single-signer promotion | Multi-witness threshold | v1.5 Phase 4 | Zero-trust policy changes |
| Implicit rules | Explicit promoted_rule_ids | v1.5 Phase 1 | Audit trail for what's active |

**Deprecated/outdated:**
- Direct rule activation (v1.4): Replaced by promotion workflow

## Research Questions Answered

### Q1: How is PolicyHead signed currently?
**Answer:** PolicyHead cells are created via `create_policy_head()` with:
- `proof.signature = None`
- `proof.signature_required = False` (bootstrap_mode=True default)

The cell itself is NOT cryptographically signed. Instead, the promotion workflow relies on witness signatures on the `canonical_payload` which includes the rule_ids. The PolicyHead's integrity comes from:
1. Cell's `cell_id` being a hash of contents (detects tampering)
2. Witness signatures on the promotion payload (proves approval)

**Recommendation for INT-01:** Either:
- Option A: Store witness signatures in PolicyHead cell data (already have them)
- Option B: Create a separate verification function that checks witness signatures match policy content

### Q2: How is policy_hash computed? Is it already verifiable?
**Answer:** Yes, fully verifiable:
- `compute_policy_hash()` in cell.py: `SHA-256(json.dumps(sorted(rule_ids), separators=(',', ':')))`
- `verify_policy_hash()` in policyhead.py: Compares stored hash to recomputed hash
- Currently only called in tests, not enforced at runtime

**Recommendation for INT-02:** Call `verify_policy_hash()` in `finalize_promotion()` before chain append.

### Q3: Where should namespace validation for rule_ids happen?
**Answer:** At `submit_promotion()` - fail fast principle. Benefits:
- Prevents collecting signatures for invalid promotion
- Gives clear error to submitter immediately
- Doesn't waste witness effort

**Implementation:** Loop through rule_ids, get each rule cell from chain, verify `rule_cell.fact.namespace == namespace`.

### Q4: Is INT-04 (threshold check) already implemented?
**Answer:** Yes, fully implemented in `finalize_promotion()` lines 554-563. Raises `UnauthorizedError` with code `DG_UNAUTHORIZED` if `promotion.status != PromotionStatus.THRESHOLD_MET`.

**No additional work needed** for INT-04.

### Q5: How should concurrent promotion race conditions be detected?
**Answer:** At finalize time:
1. Store `expected_prev_policy_head` in PromotionRequest at submit time
2. At finalize, get current policy head
3. If current != expected (and expected was set), another promotion was finalized
4. Raise `InputInvalidError` with appropriate message

**Edge case:** First promotion has null expected and null current - not a race.

## Open Questions

1. **Witness signature storage in PolicyHead**
   - What we know: Witness signatures are stored in PromotionRequest during collection
   - What's unclear: Should they be embedded in PolicyHead.fact.object for audit?
   - Recommendation: Store witness_signatures in policy_data JSON for auditability

2. **PolicyHead cell-level signing**
   - What we know: Current cells have signature=None (bootstrap mode)
   - What's unclear: Should PolicyHead be signed by system/creator for INT-01?
   - Recommendation: For INT-01, verify witness signatures cover the promoted content; cell-level signing is secondary

## Sources

### Primary (HIGH confidence)
- `policyhead.py` - PolicyHead creation, verify_policy_hash, policy_hash computation
- `engine.py` - Promotion workflow, finalize_promotion threshold check
- `signing.py` - Ed25519 verify_signature implementation
- `cell.py` - compute_policy_hash, DecisionCell structure
- `exceptions.py` - DG_* error codes and exception hierarchy

### Secondary (MEDIUM confidence)
- `test_policyhead.py` - Test patterns for PolicyHead verification
- `test_engine_promotion.py` - Test patterns for promotion workflow
- `test_adversarial_integrity.py` - Integrity violation test patterns

### Tertiary (LOW confidence)
- None - all findings verified from codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - verified from imports and codebase
- Architecture: HIGH - traced actual code flow
- Pitfalls: HIGH - identified from test patterns and existing implementations

**Research date:** 2026-01-28
**Valid until:** 2026-02-28 (stable internal codebase)

---

## Recommended Plan Structure

Based on this research, Phase 5 should have **2 plans**:

### Plan 05-01: Namespace and Hash Validation (INT-02, INT-03)
**Tasks:**
1. Add namespace validation in `submit_promotion()` - verify all rule_ids are from the target namespace
2. Add `verify_policy_hash()` call in `finalize_promotion()` before chain append
3. Add race condition detection in `finalize_promotion()` via prev_policy_head check
4. Tests for each validation case

### Plan 05-02: PolicyHead Signature Verification (INT-01)
**Tasks:**
1. Store witness_signatures in PolicyHead policy_data
2. Create `verify_policy_head_signatures()` function
3. Integrate verification check (optional mode in finalize or separate verification utility)
4. Tests for signature verification

**Note:** INT-04 is already complete - just need tests confirming the existing behavior.
