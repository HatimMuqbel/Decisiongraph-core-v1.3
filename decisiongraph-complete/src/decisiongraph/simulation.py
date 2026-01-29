"""
DecisionGraph Core: Simulation Module (v1.6)

SimulationContext and SimulationResult - the core building blocks for safe simulation.

Purpose:
- Enable safe "what-if" simulation without contaminating the base chain
- Context manager ensures shadow resources are always cleaned up (even on exception)
- Frozen result ensures simulation outputs are immutable

Key Components:
1. SimulationContext: Context manager that creates shadow chain, appends shadow cells,
   creates shadow scholar, and guarantees cleanup on exit
2. SimulationResult: Frozen dataclass for immutable simulation results

Architecture:
- Uses fork_shadow_chain() for structural isolation (Phase 7)
- Applies OverlayContext shadow cells to shadow_chain in __enter__
- Scholar created AFTER shadow cells appended (so it sees them)
- Cleanup guaranteed even on exception (__exit__ returns False)

Example:
    >>> ctx = OverlayContext()
    >>> ctx.add_shadow_fact(shadow_cell, base_cell.cell_id)
    >>>
    >>> with SimulationContext(base_chain, ctx, valid_time, system_time) as sim:
    ...     # sim.shadow_chain has base + shadow cells
    ...     # sim.shadow_scholar queries shadow_chain
    ...     result = sim.shadow_scholar.query(...)
    >>>
    >>> # After exit: sim.shadow_chain = None (guaranteed cleanup)
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import copy
import hashlib
import json

from .shadow import fork_shadow_chain, OverlayContext
from .scholar import create_scholar, Scholar
from .chain import Chain


class SimulationContext:
    """
    Context manager for safe simulation with guaranteed cleanup.

    SimulationContext creates a shadow chain from the base chain, appends
    shadow cells from the OverlayContext, and creates a shadow Scholar
    that queries the combined base + shadow cell set.

    The context manager pattern ensures shadow resources (shadow_chain,
    shadow_scholar) are always cleaned up on exit, even if an exception
    is raised during simulation.

    Attributes:
        base_chain: Production chain (never modified)
        overlay_context: Container of shadow cells to apply
        at_valid_time: Valid-time coordinate for simulation (ISO 8601 UTC)
        as_of_system_time: System-time coordinate for simulation (ISO 8601 UTC)
        shadow_chain: Shadow chain created on __enter__ (None after __exit__)
        shadow_scholar: Scholar for shadow_chain (None after __exit__)

    Usage:
        with SimulationContext(base_chain, overlay_ctx, vtime, stime) as sim:
            # sim.shadow_chain contains base + shadow cells
            # sim.shadow_scholar queries shadow_chain
            result = sim.shadow_scholar.query(...)
        # After exit: shadow_chain and shadow_scholar are None

    Why this order matters (SIM-03):
        Shadow cells MUST be appended to shadow_chain BEFORE creating
        shadow_scholar. This ensures the Scholar sees shadow cells during
        query execution. Shadow cells are NOT marked differently - they're
        valid DecisionCells. The Scholar queries the chain it's given.
    """

    def __init__(
        self,
        base_chain: Chain,
        overlay_context: OverlayContext,
        at_valid_time: str,
        as_of_system_time: str
    ):
        """
        Initialize SimulationContext.

        Args:
            base_chain: Production chain to fork from
            overlay_context: Container of shadow cells to apply
            at_valid_time: Valid-time coordinate (ISO 8601 UTC)
            as_of_system_time: System-time coordinate (ISO 8601 UTC)
        """
        self.base_chain = base_chain
        self.overlay_context = overlay_context
        self._at_valid_time = at_valid_time
        self._as_of_system_time = as_of_system_time

        # Shadow resources (created in __enter__, cleaned up in __exit__)
        self.shadow_chain: Optional[Chain] = None
        self.shadow_scholar: Optional[Scholar] = None

    @property
    def at_valid_time(self) -> str:
        """Valid-time coordinate for this simulation."""
        return self._at_valid_time

    @property
    def as_of_system_time(self) -> str:
        """System-time coordinate for this simulation."""
        return self._as_of_system_time

    def __enter__(self) -> 'SimulationContext':
        """
        Enter context: Create shadow chain, append shadow cells, create scholar.

        Steps:
        1. Fork base_chain to create shadow_chain (structural isolation)
        2. Append all shadow cells from overlay_context to shadow_chain
        3. Create shadow_scholar from shadow_chain (sees base + shadow cells)

        Returns:
            self (SimulationContext with shadow_chain and shadow_scholar ready)

        Note:
            Order matters! Shadow cells appended BEFORE scholar creation
            ensures Scholar sees shadow cells during query.
        """
        # Step 1: Fork chain (structural isolation)
        self.shadow_chain = fork_shadow_chain(self.base_chain)

        # Step 2: Append shadow cells from OverlayContext
        # CRITICAL: This must happen BEFORE creating shadow_scholar
        # so the Scholar sees shadow cells during query execution

        # Append shadow facts (for each base_cell_id, append all shadow variants)
        for fact_cells in self.overlay_context.shadow_facts.values():
            for cell in fact_cells:
                self.shadow_chain.append(cell)

        # Append shadow rules
        for rule_cell in self.overlay_context.shadow_rules.values():
            self.shadow_chain.append(rule_cell)

        # Append shadow policy heads
        for policy_cell in self.overlay_context.shadow_policy_heads.values():
            self.shadow_chain.append(policy_cell)

        # Append shadow bridges
        for bridge_cell in self.overlay_context.shadow_bridges.values():
            self.shadow_chain.append(bridge_cell)

        # Step 3: Create shadow scholar AFTER shadow cells appended
        # Scholar queries the chain it's given - by appending shadow cells first,
        # the Scholar will see them during query execution
        self.shadow_scholar = create_scholar(self.shadow_chain)

        # Return self for use in with block
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback) -> bool:
        """
        Exit context: Clean up shadow resources.

        Shadow chain and shadow scholar are discarded (set to None).
        This cleanup is GUARANTEED to happen even if an exception
        was raised during simulation.

        Args:
            exc_type: Exception type (if exception raised, else None)
            exc_value: Exception instance (if exception raised, else None)
            exc_traceback: Exception traceback (if exception raised, else None)

        Returns:
            False (do NOT suppress exceptions - propagate them)
        """
        # Cleanup shadow resources
        self.shadow_chain = None
        self.shadow_scholar = None

        # Return False to propagate exceptions (do NOT suppress)
        return False


@dataclass(frozen=True)
class DeltaReport:
    """Deterministic delta between base and shadow query results (SIM-04).

    All fields computed from comparing base_result and shadow_result proof bundles.
    Uses sorted lists for deterministic output (same inputs = identical DeltaReport).
    """
    verdict_changed: bool          # Did fact count change?
    status_before: str             # "ALLOWED" or "DENIED" (base)
    status_after: str              # "ALLOWED" or "DENIED" (shadow)
    score_delta: float             # Average confidence change (placeholder: 0.0)
    facts_diff: Dict[str, List[str]]   # {"added": [...], "removed": [...]}
    rules_diff: Dict[str, List[str]]   # {"added": [...], "removed": [...]}


@dataclass(frozen=True)
class ContaminationAttestation:
    """Proof that chain head unchanged during simulation (SHD-06).

    Captures chain.head.cell_id before and after simulation.
    attestation_hash is SHA-256 of (before|after|simulation_id) for tamper-evidence.
    contamination_detected should NEVER be True due to structural isolation.
    """
    chain_head_before: str
    chain_head_after: str
    attestation_hash: str
    contamination_detected: bool


@dataclass(frozen=True)
class SimulationResult:
    """
    Immutable simulation result (SHD-03).

    Phase 8 fields: simulation_id, rfa_dict, simulation_spec, base_result,
                    shadow_result, at_valid_time, as_of_system_time

    Phase 9 additions (SHD-03, SIM-04, SIM-05, SHD-06):
        delta_report: DeltaReport comparing base vs shadow (SIM-04)
        anchors: Dict for counterfactual anchors (empty until Phase 10)
        proof_bundle: Combined tagged bundles with attestation (SIM-05, SHD-06)

    Usage:
        result = SimulationResult(
            simulation_id="sim-123",
            rfa_dict={"namespace": "corp.hr", ...},
            simulation_spec={"shadow_facts": [...]},
            base_result={...},
            shadow_result={...},
            at_valid_time="2025-01-01T00:00:00Z",
            as_of_system_time="2025-01-01T00:00:00Z"
        )
        # Modification attempts raise FrozenInstanceError
    """
    # Phase 8 fields (existing)
    simulation_id: str
    rfa_dict: Dict[str, Any]
    simulation_spec: Dict[str, Any]
    base_result: Dict[str, Any]    # proof_bundle from base query
    shadow_result: Dict[str, Any]  # proof_bundle from shadow query
    at_valid_time: str
    as_of_system_time: str

    # Phase 9 additions (SHD-03)
    delta_report: Optional['DeltaReport'] = None      # SIM-04
    anchors: Dict[str, Any] = field(default_factory=dict)  # CTF-03 (Phase 10, empty for now)
    proof_bundle: Dict[str, Any] = field(default_factory=dict)  # SIM-05, SHD-06

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dict with deterministic ordering (SIM-06)."""
        result = {
            "simulation_id": self.simulation_id,
            "rfa_dict": self.rfa_dict,
            "simulation_spec": self.simulation_spec,
            "base_result": self.base_result,
            "shadow_result": self.shadow_result,
            "at_valid_time": self.at_valid_time,
            "as_of_system_time": self.as_of_system_time,
            "anchors": self.anchors,
            "proof_bundle": self.proof_bundle
        }
        # Add delta_report if present
        if self.delta_report is not None:
            result["delta_report"] = {
                "verdict_changed": self.delta_report.verdict_changed,
                "status_before": self.delta_report.status_before,
                "status_after": self.delta_report.status_after,
                "score_delta": self.delta_report.score_delta,
                "facts_diff": self.delta_report.facts_diff,
                "rules_diff": self.delta_report.rules_diff
            }
        # Return with sorted keys for determinism
        return json.loads(json.dumps(result, sort_keys=True))



def compute_delta_report(base_result: Dict, shadow_result: Dict) -> DeltaReport:
    """Compute deterministic delta report between base and shadow results (SIM-04, SIM-06).

    Args:
        base_result: Proof bundle from base query (via QueryResult.to_proof_bundle())
        shadow_result: Proof bundle from shadow query

    Returns:
        DeltaReport with deterministic diff fields (sorted lists for reproducibility)
    """
    # Extract fact sets
    base_facts = set(base_result.get("results", {}).get("fact_cell_ids", []))
    shadow_facts = set(shadow_result.get("results", {}).get("fact_cell_ids", []))

    # Compute differences (CRITICAL: sorted for determinism - SIM-06)
    added_facts = sorted(list(shadow_facts - base_facts))
    removed_facts = sorted(list(base_facts - shadow_facts))

    # Verdict changed if fact count differs
    base_count = base_result.get("results", {}).get("fact_count", 0)
    shadow_count = shadow_result.get("results", {}).get("fact_count", 0)
    verdict_changed = (base_count != shadow_count)

    # Authorization status
    base_auth = base_result.get("authorization_basis", {})
    shadow_auth = shadow_result.get("authorization_basis", {})
    status_before = "ALLOWED" if base_auth.get("allowed", False) else "DENIED"
    status_after = "ALLOWED" if shadow_auth.get("allowed", False) else "DENIED"

    # Score delta (placeholder - Phase 10 may compute from confidence)
    score_delta = 0.0

    # Rules diff (extract from candidates if tracked - placeholder for now)
    rules_diff = {"added": [], "removed": []}

    return DeltaReport(
        verdict_changed=verdict_changed,
        status_before=status_before,
        status_after=status_after,
        score_delta=score_delta,
        facts_diff={"added": added_facts, "removed": removed_facts},
        rules_diff=rules_diff
    )


def tag_proof_bundle_origin(proof_bundle: Dict, origin: str) -> Dict:
    """Tag proof bundle nodes with origin ("BASE" or "SHADOW") for lineage clarity (SIM-05).

    Deep copies bundle to avoid mutating original (immutability preservation).
    Adds origin field to top level and tags each cell ID.

    Args:
        proof_bundle: Proof bundle from QueryResult.to_proof_bundle()
        origin: "BASE" or "SHADOW"

    Returns:
        Tagged copy of proof bundle with origin markers
    """
    # CRITICAL: Deep copy to preserve original immutability
    tagged = copy.deepcopy(proof_bundle)

    # Add origin to top level
    tagged["origin"] = origin

    # Tag result fact cell IDs (backward compatible - keep original list)
    if "results" in tagged and "fact_cell_ids" in tagged["results"]:
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

    # Tag bridges used
    if "proof" in tagged and "bridges_used" in tagged["proof"]:
        original_ids = tagged["proof"]["bridges_used"]
        tagged["proof"]["bridges_used_with_origin"] = [
            {"cell_id": cid, "origin": origin}
            for cid in original_ids
        ]

    return tagged


def create_contamination_attestation(
    chain_head_before: str,
    chain_head_after: str,
    simulation_id: str
) -> ContaminationAttestation:
    """Create attestation proving chain unchanged during simulation (SHD-06).

    Args:
        chain_head_before: chain.head.cell_id captured before simulation
        chain_head_after: chain.head.cell_id captured after simulation
        simulation_id: Unique simulation identifier for attestation

    Returns:
        ContaminationAttestation with SHA-256 attestation hash
    """
    # Create attestation payload (pipe-delimited for clarity)
    payload = f"{chain_head_before}|{chain_head_after}|{simulation_id}"

    # SHA-256 hash for tamper-evidence
    attestation_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()

    # Detect contamination (should NEVER be True due to structural isolation)
    contamination_detected = (chain_head_before != chain_head_after)

    return ContaminationAttestation(
        chain_head_before=chain_head_before,
        chain_head_after=chain_head_after,
        attestation_hash=attestation_hash,
        contamination_detected=contamination_detected
    )


def simulation_result_to_audit_text(sim_result: SimulationResult) -> str:
    """
    Generate human-readable audit report for simulation (AUD-01, AUD-02).

    Returns deterministic plain text report containing:
    - Simulation context (ID, RFA hash, simulation spec hash, timestamps)
    - BASE reality (facts, authorization, cells)
    - SHADOW reality (facts, authorization, cells with shadow tags)
    - DELTA analysis (verdict changes, score delta, diffs)
    - Counterfactual anchors (minimal changes, completeness)
    - Contamination attestation (chain integrity proof)
    - Overlay metadata (shadow facts/rules/policies/bridges counts)
    - Schema version and generation timestamp

    Same SimulationResult always produces identical output (deterministic).

    Args:
        sim_result: SimulationResult to convert to audit text

    Returns:
        Multi-line string with audit report

    Example:
        result = engine.simulate_rfa(...)
        report = simulation_result_to_audit_text(result)
        print(report)
        # Or save to file:
        with open('simulation_audit.txt', 'w') as f:
            f.write(report)
    """
    lines = []

    # Header
    lines.append("SIMULATION AUDIT REPORT")
    lines.append("=" * 50)
    lines.append("")

    # Simulation Context
    lines.append("Simulation Context:")
    # Truncate simulation_id to 16 chars
    sim_id_display = sim_result.simulation_id[:16] + "..." if len(sim_result.simulation_id) > 16 else sim_result.simulation_id
    lines.append(f"  Simulation ID: {sim_id_display}")

    # RFA Hash: SHA-256 of canonical JSON (AUD-02)
    rfa_canonical = json.dumps(sim_result.rfa_dict, sort_keys=True, separators=(',', ':'))
    rfa_hash = hashlib.sha256(rfa_canonical.encode('utf-8')).hexdigest()
    lines.append(f"  RFA Hash: {rfa_hash[:16]}...")

    # Simulation Spec Hash: SHA-256 of canonical JSON (AUD-02)
    spec_canonical = json.dumps(sim_result.simulation_spec, sort_keys=True, separators=(',', ':'))
    spec_hash = hashlib.sha256(spec_canonical.encode('utf-8')).hexdigest()
    lines.append(f"  Simulation Spec Hash: {spec_hash[:16]}...")

    lines.append(f"  Valid Time: {sim_result.at_valid_time}")
    lines.append(f"  System Time: {sim_result.as_of_system_time}")
    lines.append("")

    # BASE Reality
    lines.append("BASE Reality:")
    base_fact_count = sim_result.base_result.get("results", {}).get("fact_count", 0)
    lines.append(f"  Facts Returned: {base_fact_count}")
    base_allowed = sim_result.base_result.get("authorization_basis", {}).get("allowed", False)
    base_status = "ALLOWED" if base_allowed else "DENIED"
    lines.append(f"  Authorization: {base_status}")

    base_fact_ids = sim_result.base_result.get("results", {}).get("fact_cell_ids", [])
    if base_fact_ids:
        lines.append("  Fact Cells:")
        for cell_id in base_fact_ids:
            cell_display = cell_id[:16] + "..." if len(cell_id) > 16 else cell_id
            lines.append(f"    - {cell_display}")
    lines.append("")

    # SHADOW Reality
    lines.append("SHADOW Reality:")
    shadow_fact_count = sim_result.shadow_result.get("results", {}).get("fact_count", 0)
    lines.append(f"  Facts Returned: {shadow_fact_count}")
    shadow_allowed = sim_result.shadow_result.get("authorization_basis", {}).get("allowed", False)
    shadow_status = "ALLOWED" if shadow_allowed else "DENIED"
    lines.append(f"  Authorization: {shadow_status}")

    shadow_fact_ids = sim_result.shadow_result.get("results", {}).get("fact_cell_ids", [])
    if shadow_fact_ids:
        lines.append("  Fact Cells:")
        base_fact_set = set(base_fact_ids)
        for cell_id in shadow_fact_ids:
            cell_display = cell_id[:16] + "..." if len(cell_id) > 16 else cell_id
            # Tag cells not in base with [SHADOW]
            tag = " [SHADOW]" if cell_id not in base_fact_set else ""
            lines.append(f"    - {cell_display}{tag}")
    lines.append("")

    # DELTA Analysis
    lines.append("DELTA Analysis:")
    if sim_result.delta_report:
        dr = sim_result.delta_report
        # verdict_changed as lowercase string
        verdict_changed_str = "true" if dr.verdict_changed else "false"
        lines.append(f"  Verdict Changed: {verdict_changed_str}")
        lines.append(f"  Status Change: {dr.status_before} -> {dr.status_after}")
        lines.append(f"  Score Delta: {dr.score_delta}")

        # Facts diff
        added_count = len(dr.facts_diff.get("added", []))
        removed_count = len(dr.facts_diff.get("removed", []))
        lines.append(f"  Facts Diff: Added={added_count}, Removed={removed_count}")

        # Rules diff
        rules_added_count = len(dr.rules_diff.get("added", []))
        rules_removed_count = len(dr.rules_diff.get("removed", []))
        lines.append(f"  Rules Diff: Added={rules_added_count}, Removed={rules_removed_count}")
    else:
        lines.append("  Delta Report: Not available")
    lines.append("")

    # Counterfactual Anchors
    lines.append("Counterfactual Anchors:")
    anchors_list = sim_result.anchors.get("anchors", [])
    lines.append(f"  Anchors Detected: {len(anchors_list)}")
    if anchors_list:
        lines.append("  Minimal Changes:")
        for anchor in anchors_list:
            lines.append(f"    - {anchor}")
    anchors_incomplete = sim_result.anchors.get("anchors_incomplete", False)
    if anchors_incomplete:
        lines.append("  [INCOMPLETE] Anchor search reached execution budget limit")
    lines.append("")

    # Contamination Attestation
    lines.append("Contamination Attestation:")
    attestation = sim_result.proof_bundle.get("contamination_attestation", {})
    if attestation:
        head_before = attestation.get("chain_head_before", "")
        head_before_display = head_before[:16] + "..." if len(head_before) > 16 else head_before
        lines.append(f"  Chain Head Before: {head_before_display}")

        head_after = attestation.get("chain_head_after", "")
        head_after_display = head_after[:16] + "..." if len(head_after) > 16 else head_after
        lines.append(f"  Chain Head After: {head_after_display}")

        contamination = attestation.get("contamination_detected", False)
        contamination_str = "true" if contamination else "false"
        lines.append(f"  Contamination Detected: {contamination_str}")

        att_hash = attestation.get("attestation_hash", "")
        att_hash_display = att_hash[:16] + "..." if len(att_hash) > 16 else att_hash
        lines.append(f"  Attestation Hash: {att_hash_display}")
    else:
        lines.append("  Attestation: Not available")
    lines.append("")

    # Overlay Metadata (AUD-02)
    lines.append("Overlay Metadata:")
    shadow_facts = sim_result.simulation_spec.get("shadow_facts", [])
    lines.append(f"  Shadow Facts: {len(shadow_facts)}")

    shadow_rules = sim_result.simulation_spec.get("shadow_rules", [])
    lines.append(f"  Shadow Rules: {len(shadow_rules)}")

    shadow_policy_heads = sim_result.simulation_spec.get("shadow_policy_heads", [])
    lines.append(f"  Shadow PolicyHeads: {len(shadow_policy_heads)}")

    shadow_bridges = sim_result.simulation_spec.get("shadow_bridges", [])
    lines.append(f"  Shadow Bridges: {len(shadow_bridges)}")
    lines.append("")

    # Footer
    lines.append("Schema Version: 1.6")
    lines.append(f"Generated: {sim_result.as_of_system_time}")

    return "\n".join(lines)


def simulation_result_to_dot(sim_result: SimulationResult) -> str:
    """
    Generate Graphviz DOT format for simulation lineage visualization (AUD-03).

    Creates a dual-origin graph showing BASE reality vs SHADOW reality with
    color-coded nodes for visual debugging and stakeholder presentations.

    Color coding:
    - BASE nodes: lightblue
    - SHADOW nodes (new): orange
    - SHADOW nodes (from BASE): lightblue
    - Anchor nodes: double border (peripheries=2, penwidth=3.0)
    - Added facts: lightgreen
    - Removed facts: pink
    - Verdict change: red diamond

    Output can be rendered with Graphviz:
        $ dot -Tpng simulation.dot -o simulation.png
        $ dot -Tsvg simulation.dot -o simulation.svg

    Same SimulationResult always produces identical output (deterministic).

    Args:
        sim_result: SimulationResult from Engine.simulate_rfa()

    Returns:
        String containing valid DOT syntax

    Example:
        result = engine.simulate_rfa(...)
        dot_text = simulation_result_to_dot(result)
        with open('simulation.dot', 'w') as f:
            f.write(dot_text)
        # Then: dot -Tpng simulation.dot -o simulation.png
    """
    lines = []

    # Helper to escape DOT strings
    def _escape_dot_string(s: str) -> str:
        """Escape quotes, backslashes, and newlines for DOT format"""
        return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

    # Helper to truncate cell ID
    def _short_id(cell_id: str) -> str:
        """Truncate cell ID to first 12 chars + ellipsis"""
        return cell_id[:12] + "..."

    # Graph header
    lines.append("digraph simulation_lineage {")
    lines.append(f"  // Simulation: {_short_id(sim_result.simulation_id)}")
    lines.append("  rankdir=TB;")
    lines.append("  node [shape=box, style=filled];")
    lines.append("")

    # Extract data
    base_facts = sim_result.base_result.get("results", {}).get("fact_cell_ids", [])
    shadow_facts = sim_result.shadow_result.get("results", {}).get("fact_cell_ids", [])
    anchor_cell_ids = set(sim_result.anchors.get("anchors", []))

    # BASE Subgraph
    lines.append("  subgraph cluster_base {")
    lines.append('    label="BASE Reality";')
    lines.append("    style=filled;")
    lines.append("    fillcolor=lightgray;")
    lines.append("")
    for fact_id in sorted(base_facts):  # sorted for determinism
        node_id = f"base_{_short_id(fact_id)}"
        label = f"Fact\\n{_short_id(fact_id)}"
        lines.append(f'    "{node_id}" [label="{label}", fillcolor=lightblue];')
    lines.append("  }")
    lines.append("")

    # SHADOW Subgraph
    lines.append("  subgraph cluster_shadow {")
    lines.append('    label="SHADOW Reality (Overlay)";')
    lines.append("    style=filled;")
    lines.append("    fillcolor=lightyellow;")
    lines.append("")
    base_fact_set = set(base_facts)
    for fact_id in sorted(shadow_facts):  # sorted for determinism
        node_id = f"shadow_{_short_id(fact_id)}"
        label = f"Fact\\n{_short_id(fact_id)}"

        # Color: orange if shadow-origin (not in base), lightblue otherwise
        fillcolor = "orange" if fact_id not in base_fact_set else "lightblue"

        # Anchor highlighting (double border, thick pen)
        extra_attrs = ""
        if fact_id in anchor_cell_ids:
            extra_attrs = ", peripheries=2, penwidth=3.0"

        lines.append(f'    "{node_id}" [label="{label}", fillcolor={fillcolor}{extra_attrs}];')
    lines.append("  }")
    lines.append("")

    # Delta edges
    lines.append("  // Delta edges")
    # Removed facts (pink)
    if sim_result.delta_report:
        for removed_id in sorted(sim_result.delta_report.facts_diff.get("removed", [])):
            lines.append(f'  "base_{_short_id(removed_id)}" [fillcolor=pink];  // REMOVED')

        # Added facts (lightgreen)
        for added_id in sorted(sim_result.delta_report.facts_diff.get("added", [])):
            lines.append(f'  "shadow_{_short_id(added_id)}" [fillcolor=lightgreen];  // ADDED')
    lines.append("")

    # Verdict change annotation
    if sim_result.delta_report and sim_result.delta_report.verdict_changed:
        lines.append('  "verdict_delta" [label="VERDICT CHANGED", shape=diamond, fillcolor=red, fontcolor=white];')
        lines.append("")

    # Graph footer
    lines.append("}")

    return "\n".join(lines)


# Export public interface
__all__ = [
    'SimulationContext',
    'SimulationResult',
    'DeltaReport',
    'ContaminationAttestation',
    'compute_delta_report',
    'tag_proof_bundle_origin',
    'create_contamination_attestation',
    'simulation_result_to_audit_text',
    'simulation_result_to_dot',
]
