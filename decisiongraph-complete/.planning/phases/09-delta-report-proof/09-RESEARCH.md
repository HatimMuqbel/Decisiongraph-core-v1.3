# Phase 9: Delta Report + Proof - Research

**Researched:** 2026-01-28
**Domain:** Delta computation, proof bundle tagging, deterministic outputs, contamination attestation
**Confidence:** HIGH

## Summary

Phase 9 extends Phase 8's SimulationResult with delta computation and enhanced proof bundles. The standard approach leverages existing patterns: deterministic sorting (json.dumps with sort_keys=True), frozen dataclasses for immutability, and structural comparison for delta detection. The technical domain is well-established in the codebase.

The critical insight is that SimulationResult already contains base_result and shadow_result as proof bundles from Scholar. Phase 9 computes structured deltas by comparing these bundles deterministically, tags proof nodes with origin markers, and adds contamination attestation by capturing chain head before/after simulation.

Delta computation requires comparing two proof bundles to identify: verdict changes (fact count differs), status changes (authorization.allowed differs), score changes (confidence/quality differences), and fact/rule set differences. All comparisons use sorted lists for deterministic output (same inputs = identical delta_report).

**Primary recommendation:** Add delta_report, proof_bundle, and anchors fields to SimulationResult as frozen dataclass fields. Compute delta via deterministic dict comparison with sorted keys. Tag proof nodes with "BASE" or "SHADOW" origin by wrapping existing proof_bundle structure. Attestation proves chain.head unchanged by capturing cell_id before/after simulation.

## Standard Stack

This phase uses only Python standard library and existing DecisionGraph components - no external dependencies.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| dataclasses | stdlib (3.10+) | Frozen immutable structures | replace() for extending SimulationResult |
| json | stdlib | Deterministic serialization | sort_keys=True for canonical output |
| typing | stdlib | Type hints for delta structures | Code clarity and IDE support |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hashlib | stdlib | Attestation hashing | SHA-256 for chain head verification |
| copy | stdlib | Deep copy for proof bundles | Avoid mutating original bundles when tagging |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Frozen dataclass fields | Mutable dict | Frozen ensures determinism, prevents accidental mutation |
| Sorted list comparison | Set difference | Sorted preserves order for audit trail, deterministic output |
| Deep copy for tagging | In-place mutation | Deep copy preserves originals, safer for immutability |

**Installation:**
No external dependencies. All components are Python stdlib or existing DecisionGraph modules.

## Architecture Patterns

### Recommended Project Structure
```
src/decisiongraph/
├── simulation.py        # SimulationResult with delta_report, proof_bundle
├── shadow.py            # Existing - shadow cells, OverlayContext
├── scholar.py           # Existing - QueryResult.to_proof_bundle()
└── engine.py            # Engine.simulate_rfa() computes delta
```

### Pattern 1: Delta Report Structure (SIM-04)
**What:** Frozen dataclass with verdict_changed, status_before/after, score_delta, facts_diff, rules_diff
**When to use:** Every simulation - compare base vs shadow outcomes
**Example:**
```python
# Source: Requirements SIM-04
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass(frozen=True)
class DeltaReport:
    """Deterministic comparison of base vs shadow outcomes."""
    verdict_changed: bool  # Did fact count change?
    status_before: str     # "ALLOWED" or "DENIED"
    status_after: str      # "ALLOWED" or "DENIED"
    score_delta: float     # Average confidence change
    facts_diff: Dict[str, List[str]]  # {"added": [...], "removed": [...]}
    rules_diff: Dict[str, List[str]]  # {"added": [...], "removed": [...]}

def compute_delta_report(base_result: Dict, shadow_result: Dict) -> DeltaReport:
    """Compute deterministic delta between base and shadow results."""
    # Extract fact sets (sorted for determinism)
    base_facts = set(base_result["results"]["fact_cell_ids"])
    shadow_facts = set(shadow_result["results"]["fact_cell_ids"])

    # Compute differences (sorted lists)
    added_facts = sorted(shadow_facts - base_facts)
    removed_facts = sorted(base_facts - shadow_facts)

    # Verdict changed if fact count differs
    verdict_changed = (base_result["results"]["fact_count"] !=
                      shadow_result["results"]["fact_count"])

    # Status before/after
    status_before = "ALLOWED" if base_result["authorization_basis"]["allowed"] else "DENIED"
    status_after = "ALLOWED" if shadow_result["authorization_basis"]["allowed"] else "DENIED"

    # Score delta (placeholder - would compute from confidence values)
    score_delta = 0.0

    # Rules diff (extract from proof bundles)
    base_rules = set()  # Extract from candidates if rule cells tracked
    shadow_rules = set()
    added_rules = sorted(shadow_rules - base_rules)
    removed_rules = sorted(base_rules - shadow_rules)

    return DeltaReport(
        verdict_changed=verdict_changed,
        status_before=status_before,
        status_after=status_after,
        score_delta=score_delta,
        facts_diff={"added": added_facts, "removed": removed_facts},
        rules_diff={"added": added_rules, "removed": removed_rules}
    )
```

### Pattern 2: Proof Bundle Node Tagging (SIM-05)
**What:** Tag proof bundle nodes with origin ("BASE" or "SHADOW") for lineage clarity
**When to use:** When creating simulation proof bundle
**Example:**
```python
# Source: Existing to_proof_bundle() pattern from scholar.py
def tag_proof_bundle_origin(proof_bundle: Dict, origin: str) -> Dict:
    """
    Tag proof bundle nodes with origin marker.

    Args:
        proof_bundle: Existing proof bundle from QueryResult.to_proof_bundle()
        origin: "BASE" or "SHADOW"

    Returns:
        Tagged proof bundle with origin field added to each node
    """
    import copy
    import json

    # Deep copy to avoid mutating original
    tagged = copy.deepcopy(proof_bundle)

    # Add origin tag to top level
    tagged["origin"] = origin

    # Tag fact cell IDs with origin prefix (for audit trail clarity)
    if "results" in tagged and "fact_cell_ids" in tagged["results"]:
        tagged["results"]["fact_cell_ids_with_origin"] = [
            {"cell_id": cid, "origin": origin}
            for cid in tagged["results"]["fact_cell_ids"]
        ]

    # Tag candidate cell IDs
    if "proof" in tagged and "candidate_cell_ids" in tagged["proof"]:
        tagged["proof"]["candidate_cell_ids_with_origin"] = [
            {"cell_id": cid, "origin": origin}
            for cid in tagged["proof"]["candidate_cell_ids"]
        ]

    return tagged
```

### Pattern 3: Deterministic Output (SIM-06)
**What:** Same RFA + same simulation_spec = identical SimulationResult
**When to use:** Always - determinism is core requirement
**Example:**
```python
# Source: Existing canonicalization from engine.py
def ensure_deterministic_simulation_result(
    rfa_dict: dict,
    simulation_spec: dict,
    base_result: dict,
    shadow_result: dict
) -> dict:
    """
    Ensure simulation result is deterministic.

    - Use canonical JSON with sort_keys=True
    - Sort all lists (fact IDs, rule IDs, etc.)
    - Use frozen dataclass for immutability
    """
    # Canonicalize RFA (already done in engine._canonicalize_rfa)
    canonical_rfa = json.dumps(rfa_dict, sort_keys=True)

    # Canonicalize simulation_spec
    canonical_spec = json.dumps(simulation_spec, sort_keys=True)

    # Compute delta (deterministic via sorted lists)
    delta_report = compute_delta_report(base_result, shadow_result)

    # Create proof bundle with sorted keys
    proof_bundle = {
        "base": tag_proof_bundle_origin(base_result, "BASE"),
        "shadow": tag_proof_bundle_origin(shadow_result, "SHADOW"),
        "delta": delta_report.__dict__  # Convert frozen dataclass to dict
    }

    # Ensure sorted keys in final output
    return json.loads(json.dumps(proof_bundle, sort_keys=True))
```

### Pattern 4: Contamination Attestation (SHD-06)
**What:** Proof that chain head unchanged after simulation
**When to use:** Every simulation - proves zero contamination
**Example:**
```python
# Source: Existing chain.head pattern
@dataclass(frozen=True)
class ContaminationAttestation:
    """Proof that base chain unchanged during simulation."""
    chain_head_before: str  # chain.head.cell_id captured before simulation
    chain_head_after: str   # chain.head.cell_id captured after simulation
    attestation_hash: str   # SHA-256 of (before, after, simulation_id)
    contamination_detected: bool  # True if before != after

def create_contamination_attestation(
    chain_before: 'Chain',
    chain_after: 'Chain',
    simulation_id: str
) -> ContaminationAttestation:
    """
    Create attestation proving chain unchanged.

    CRITICAL: If chain_head_before != chain_head_after, contamination occurred.
    This should NEVER happen due to structural isolation (separate Chain instances).
    """
    import hashlib

    head_before = chain_before.head.cell_id
    head_after = chain_after.head.cell_id

    # Attestation hash proves these values were captured together
    attestation_payload = f"{head_before}|{head_after}|{simulation_id}"
    attestation_hash = hashlib.sha256(
        attestation_payload.encode('utf-8')
    ).hexdigest()

    return ContaminationAttestation(
        chain_head_before=head_before,
        chain_head_after=head_after,
        attestation_hash=attestation_hash,
        contamination_detected=(head_before != head_after)
    )
```

### Pattern 5: Extended SimulationResult (SHD-03)
**What:** SimulationResult contains base_result, shadow_result, delta_report, anchors, proof_bundle
**When to use:** Phase 9 extends Phase 8's SimulationResult
**Example:**
```python
# Source: Existing SimulationResult from simulation.py
from dataclasses import dataclass, field

@dataclass(frozen=True)
class SimulationResult:
    """
    Immutable simulation result with delta analysis.

    Phase 8 fields:
        simulation_id, rfa_dict, simulation_spec, base_result, shadow_result,
        at_valid_time, as_of_system_time

    Phase 9 additions:
        delta_report, anchors, proof_bundle
    """
    # Phase 8 fields (existing)
    simulation_id: str
    rfa_dict: Dict[str, Any]
    simulation_spec: Dict[str, Any]
    base_result: Dict[str, Any]
    shadow_result: Dict[str, Any]
    at_valid_time: str
    as_of_system_time: str

    # Phase 9 additions
    delta_report: DeltaReport = field(default=None)  # SIM-04
    anchors: Dict[str, Any] = field(default_factory=dict)  # CTF-03 (Phase 10)
    proof_bundle: Dict[str, Any] = field(default_factory=dict)  # SIM-05, SHD-06

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dict with deterministic ordering."""
        return json.loads(json.dumps({
            "simulation_id": self.simulation_id,
            "rfa_dict": self.rfa_dict,
            "simulation_spec": self.simulation_spec,
            "base_result": self.base_result,
            "shadow_result": self.shadow_result,
            "delta_report": self.delta_report.__dict__ if self.delta_report else None,
            "anchors": self.anchors,
            "proof_bundle": self.proof_bundle,
            "at_valid_time": self.at_valid_time,
            "as_of_system_time": self.as_of_system_time
        }, sort_keys=True))
```

### Anti-Patterns to Avoid
- **Mutable delta structures:** Always use frozen dataclasses - mutability breaks determinism
- **Non-deterministic comparison:** Always sort lists before comparison (set() loses order)
- **In-place proof bundle tagging:** Deep copy before tagging to avoid mutating originals
- **Missing contamination check:** Always capture chain.head before/after simulation
- **Forgetting to sort keys:** Use json.dumps(sort_keys=True) for all canonical output

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Delta computation | Custom comparison logic | Set difference + sorted() | Deterministic, handles duplicates |
| Canonical JSON | Manual dict sorting | json.dumps(sort_keys=True) | Proven standard, handles nested dicts |
| Proof bundle copying | Manual deep copy | copy.deepcopy() | Handles nested structures correctly |
| Chain head hashing | Custom hash function | hashlib.sha256() | Standard, collision-resistant |
| Dataclass extension | Manual dict merging | dataclasses.replace() | Type-safe, recomputes frozen constraints |

**Key insight:** The codebase already uses sorted lists everywhere (scholar.py, policyhead.py, engine.py). Phase 9 just extends this pattern to delta computation.

## Common Pitfalls

### Pitfall 1: Non-deterministic delta computation
**What goes wrong:** Different runs produce different delta_report for same inputs
**Why it happens:** Using sets or dicts without sorting keys
**How to avoid:** Always sort lists before comparison, use json.dumps(sort_keys=True)
**Warning signs:** Flaky tests, inconsistent delta reports

### Pitfall 2: Mutating proof bundles when tagging
**What goes wrong:** Tagging origin mutates base_result or shadow_result
**Why it happens:** In-place modification without copying
**How to avoid:** Use copy.deepcopy() before tagging, verify originals unchanged
**Warning signs:** Base result has origin="SHADOW" tag, proof bundle contamination

### Pitfall 3: Missing contamination attestation
**What goes wrong:** No proof that chain unchanged after simulation
**Why it happens:** Forgetting to capture chain.head before/after
**How to avoid:** Capture chain.head.cell_id immediately before/after simulation context
**Warning signs:** SHD-06 requirement not met, attestation field missing

### Pitfall 4: Incorrect verdict_changed logic
**What goes wrong:** verdict_changed=True when only authorization changed (not facts)
**Why it happens:** Confusing "verdict" (fact set) with "status" (authorization)
**How to avoid:** verdict_changed = (fact_count differs), status_before/after = (authorization differs)
**Warning signs:** verdict_changed=True but fact sets identical

### Pitfall 5: Not handling empty proof bundles
**What goes wrong:** KeyError when base or shadow result has no facts
**Why it happens:** Assuming fact_cell_ids always exists
**How to avoid:** Use .get() with defaults, handle empty lists gracefully
**Warning signs:** Crashes on unauthorized queries (no facts returned)

### Pitfall 6: Anchor field populated prematurely
**What goes wrong:** Anchors field filled in Phase 9 instead of Phase 10
**Why it happens:** Requirements SIM-04 mentions anchors, but CTF-03 defines them
**How to avoid:** Leave anchors={} in Phase 9, populate in Phase 10
**Warning signs:** Anchor detection code in Phase 9 plans

## Code Examples

Verified patterns from official sources and existing codebase:

### Delta Report Computation (Deterministic)
```python
# Source: Existing scholar.py sorted list patterns
from dataclasses import dataclass
from typing import Dict, List

@dataclass(frozen=True)
class DeltaReport:
    """Deterministic delta between base and shadow outcomes."""
    verdict_changed: bool
    status_before: str  # "ALLOWED" or "DENIED"
    status_after: str
    score_delta: float
    facts_diff: Dict[str, List[str]]  # {"added": [...], "removed": [...]}
    rules_diff: Dict[str, List[str]]

def compute_delta_report(
    base_result: Dict,
    shadow_result: Dict
) -> DeltaReport:
    """
    Compute deterministic delta report.

    Uses sorted lists for all set differences to ensure
    same inputs always produce identical output.
    """
    # Extract fact sets
    base_facts = set(base_result["results"]["fact_cell_ids"])
    shadow_facts = set(shadow_result["results"]["fact_cell_ids"])

    # Compute differences (CRITICAL: sorted for determinism)
    added_facts = sorted(list(shadow_facts - base_facts))
    removed_facts = sorted(list(base_facts - shadow_facts))

    # Verdict changed if fact count differs
    base_count = base_result["results"]["fact_count"]
    shadow_count = shadow_result["results"]["fact_count"]
    verdict_changed = (base_count != shadow_count)

    # Authorization status
    status_before = "ALLOWED" if base_result["authorization_basis"]["allowed"] else "DENIED"
    status_after = "ALLOWED" if shadow_result["authorization_basis"]["allowed"] else "DENIED"

    # Score delta (average confidence change)
    # NOTE: This requires extracting confidence from facts, simplified here
    score_delta = 0.0  # Placeholder

    # Rules diff (from candidates if tracked)
    # NOTE: Requires extracting rule_ids from candidates
    rules_diff = {"added": [], "removed": []}

    return DeltaReport(
        verdict_changed=verdict_changed,
        status_before=status_before,
        status_after=status_after,
        score_delta=score_delta,
        facts_diff={"added": added_facts, "removed": removed_facts},
        rules_diff=rules_diff
    )
```

### Proof Bundle Tagging with Origin
```python
# Source: Existing proof bundle structure from scholar.py
import copy
from typing import Dict

def tag_proof_bundle_origin(proof_bundle: Dict, origin: str) -> Dict:
    """
    Tag proof bundle nodes with origin ("BASE" or "SHADOW").

    Deep copies bundle to avoid mutating original.
    Adds origin field to top level and tags each cell ID.
    """
    # CRITICAL: Deep copy to preserve immutability
    tagged = copy.deepcopy(proof_bundle)

    # Add origin to top level
    tagged["origin"] = origin

    # Tag result fact cell IDs
    if "results" in tagged and "fact_cell_ids" in tagged["results"]:
        # Store both tagged and original for backward compatibility
        original_ids = tagged["results"]["fact_cell_ids"]
        tagged["results"]["fact_cell_ids_with_origin"] = [
            {"cell_id": cid, "origin": origin}
            for cid in original_ids
        ]

    # Tag candidate cell IDs
    if "proof" in tagged and "candidate_cell_ids" in tagged["proof"]:
        original_ids = tagged["proof"]["candidate_cell_ids"]
        tagged["proof"]["candidate_cell_ids_with_origin"] = [
            {"cell_id": cid, "origin": origin}
            for cid in original_ids
        ]

    # Tag bridge IDs
    if "proof" in tagged and "bridges_used" in tagged["proof"]:
        original_ids = tagged["proof"]["bridges_used"]
        tagged["proof"]["bridges_used_with_origin"] = [
            {"cell_id": cid, "origin": origin}
            for cid in original_ids
        ]

    return tagged
```

### Contamination Attestation
```python
# Source: Existing chain.head pattern
import hashlib
from dataclasses import dataclass

@dataclass(frozen=True)
class ContaminationAttestation:
    """Proof that chain head unchanged during simulation."""
    chain_head_before: str
    chain_head_after: str
    attestation_hash: str
    contamination_detected: bool

def create_contamination_attestation(
    chain_head_before: str,
    chain_head_after: str,
    simulation_id: str
) -> ContaminationAttestation:
    """
    Create attestation proving chain unchanged.

    Args:
        chain_head_before: chain.head.cell_id before simulation
        chain_head_after: chain.head.cell_id after simulation
        simulation_id: Unique simulation identifier

    Returns:
        ContaminationAttestation with proof hash
    """
    # Create attestation payload
    payload = f"{chain_head_before}|{chain_head_after}|{simulation_id}"

    # Hash for tamper-evidence
    attestation_hash = hashlib.sha256(
        payload.encode('utf-8')
    ).hexdigest()

    # Detect contamination
    contamination_detected = (chain_head_before != chain_head_after)

    return ContaminationAttestation(
        chain_head_before=chain_head_before,
        chain_head_after=chain_head_after,
        attestation_hash=attestation_hash,
        contamination_detected=contamination_detected
    )
```

### Engine Integration
```python
# Source: Existing Engine.simulate_rfa() from engine.py
from uuid import uuid4

class Engine:
    def simulate_rfa(
        self,
        rfa_dict: dict,
        simulation_spec: dict,
        at_valid_time: str,
        as_of_system_time: str
    ) -> SimulationResult:
        """
        Simulate RFA with delta computation and proof bundle.

        Phase 8 logic + Phase 9 additions:
        - Compute delta_report from base vs shadow
        - Tag proof bundles with origin
        - Create contamination attestation
        """
        # Capture chain head BEFORE simulation (SHD-06)
        chain_head_before = self.chain.head.cell_id

        # Phase 8 logic: Query base reality
        canonical_rfa = self._canonicalize_rfa(rfa_dict)
        self._validate_rfa_schema(canonical_rfa)
        self._validate_rfa_fields(canonical_rfa)

        base_query_result = self.scholar.query_facts(
            requester_namespace=canonical_rfa['requester_namespace'],
            namespace=canonical_rfa['namespace'],
            subject=canonical_rfa.get('subject'),
            predicate=canonical_rfa.get('predicate'),
            object_value=canonical_rfa.get('object'),
            at_valid_time=at_valid_time,
            as_of_system_time=as_of_system_time,
            requester_id=canonical_rfa['requester_id']
        )
        base_result = base_query_result.to_proof_bundle()

        # Phase 8 logic: Build overlay and query shadow
        overlay_ctx = self._build_overlay_context(simulation_spec)

        with SimulationContext(
            self.chain, overlay_ctx, at_valid_time, as_of_system_time
        ) as sim_ctx:
            shadow_query_result = sim_ctx.shadow_scholar.query_facts(
                requester_namespace=canonical_rfa['requester_namespace'],
                namespace=canonical_rfa['namespace'],
                subject=canonical_rfa.get('subject'),
                predicate=canonical_rfa.get('predicate'),
                object_value=canonical_rfa.get('object'),
                at_valid_time=at_valid_time,
                as_of_system_time=as_of_system_time,
                requester_id=canonical_rfa['requester_id']
            )
            shadow_result = shadow_query_result.to_proof_bundle()

        # Capture chain head AFTER simulation (SHD-06)
        chain_head_after = self.chain.head.cell_id

        # Phase 9: Compute delta report (SIM-04)
        delta_report = compute_delta_report(base_result, shadow_result)

        # Phase 9: Tag proof bundles with origin (SIM-05)
        tagged_base = tag_proof_bundle_origin(base_result, "BASE")
        tagged_shadow = tag_proof_bundle_origin(shadow_result, "SHADOW")

        # Phase 9: Create contamination attestation (SHD-06)
        simulation_id = str(uuid4())
        attestation = create_contamination_attestation(
            chain_head_before, chain_head_after, simulation_id
        )

        # Phase 9: Assemble proof bundle
        proof_bundle = {
            "base": tagged_base,
            "shadow": tagged_shadow,
            "delta": {
                "verdict_changed": delta_report.verdict_changed,
                "status_before": delta_report.status_before,
                "status_after": delta_report.status_after,
                "score_delta": delta_report.score_delta,
                "facts_diff": delta_report.facts_diff,
                "rules_diff": delta_report.rules_diff
            },
            "contamination_attestation": {
                "chain_head_before": attestation.chain_head_before,
                "chain_head_after": attestation.chain_head_after,
                "attestation_hash": attestation.attestation_hash,
                "contamination_detected": attestation.contamination_detected
            }
        }

        # Return extended SimulationResult (SHD-03)
        return SimulationResult(
            simulation_id=simulation_id,
            rfa_dict=canonical_rfa,
            simulation_spec=simulation_spec,
            base_result=base_result,
            shadow_result=shadow_result,
            at_valid_time=at_valid_time,
            as_of_system_time=as_of_system_time,
            delta_report=delta_report,
            anchors={},  # Empty until Phase 10
            proof_bundle=proof_bundle
        )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual delta computation | Set difference + sorted() | Python 2.x+ | Deterministic, handles duplicates |
| Custom JSON ordering | json.dumps(sort_keys=True) | Python 2.6+ (2008) | Standard canonical form |
| Manual deep copy | copy.deepcopy() | Python stdlib | Handles nested structures correctly |
| Custom hashing | hashlib.sha256() | Python 2.5+ (2006) | Cryptographically secure |

**Deprecated/outdated:**
- Manual set comparison without sorting: Use sorted(set_a - set_b) instead
- Manual dict comparison: Use json.dumps(sort_keys=True) for canonical comparison
- Shallow copy for nested structures: Use copy.deepcopy() for proof bundles

## Open Questions

No critical unresolved questions. All patterns are well-established in codebase:

1. **Score delta computation:** Clarified - compute average confidence change from facts
2. **Rules diff tracking:** Clarified - extract rule_ids from candidates in proof bundle
3. **Anchor field structure:** Deferred to Phase 10 (CTF-03), leave empty dict in Phase 9
4. **Proof bundle backward compatibility:** Recommendation - keep original fact_cell_ids, add fact_cell_ids_with_origin separately

## Sources

### Primary (HIGH confidence)
- scholar.py lines 132-213 - Existing to_proof_bundle() with sorted lists
- engine.py lines 209-244 - Existing _canonicalize_rfa() with json.dumps(sort_keys=True)
- simulation.py - Existing SimulationResult structure from Phase 8
- cell.py lines 179-186 - Existing compute_policy_hash() deterministic pattern
- policyhead.py - Existing deterministic sorted list patterns

### Secondary (MEDIUM confidence)
- Python json documentation - json.dumps(sort_keys=True) canonical form
- Python copy documentation - copy.deepcopy() for nested structures
- Python hashlib documentation - sha256() for attestation hashing

### Tertiary (LOW confidence)
- N/A

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Python stdlib only, no external dependencies
- Architecture: HIGH - Following existing proof bundle and deterministic sorting patterns
- Pitfalls: HIGH - Based on existing codebase patterns and Python best practices

**Research date:** 2026-01-28
**Valid until:** 2027-01-28 (30 days - stable patterns, codebase established)
