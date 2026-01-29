# DecisionGraph v1.6 — Oracle Layer (Counterfactual Decision Space)

## What This Is

DecisionGraph is a zero-trust decision engine with cryptographic namespace isolation. The v1.5 engine provides bitemporal semantics, deterministic conflict resolution (Scholar), bridge-based cross-namespace authorization, PolicyHead promotion gates with multi-witness approval, and a hardened RFA ingress layer with Ed25519 signatures.

**This milestone (v1.6)** adds the Oracle layer for counterfactual simulation:
- Shadow cell infrastructure for hypothetical fact/policy injection
- SimulationContext with OverlayScholar pattern for isolated what-if queries
- Zero-contamination guarantee (simulation never mutates real chain)
- Delta reports comparing base vs shadow outcomes
- Counterfactual anchor detection (minimal changes causing outcome delta)
- Batch backtest over historical RFAs
- Simulation audit trail with BASE vs SHADOW lineage graphs

## Core Value

**Safe simulation of policy/rule changes against historical data without contaminating the real vault — deterministic, bitemporal, governed, provable, non-mutating.**

Users can ask "what if we had promoted different rules?" or "what if this fact had been different?" and receive provable comparisons without affecting production data. This enables regulatory compliance analysis, policy testing before promotion, and decision analysis with audit trails.

## Guiding Principles

1. **Zero contamination** — Simulations observe, never mutate the real chain
2. **Deterministic outputs** — Same simulation inputs = identical results always
3. **Bounded execution** — All operations have execution limits (prevent DoS)
4. **Provable watermarking** — Simulation results clearly marked as hypothetical
5. **Bitemporal native** — Simulations respect frozen (valid_time, system_time) coordinates

## Existing Foundation (v1.5)

- **Cell/Chain/Genesis** — Append-only cryptographic ledger
- **Namespace/Bridge** — Department isolation with dual-signature bridges
- **Scholar** — Bitemporal query resolver with deterministic conflict resolution
- **RFA Layer** — Single entry point with schema/input validation
- **Error Codes** — 6 deterministic DG_* error codes
- **Signatures** — Ed25519 signing and verification
- **PolicyHead** — Active policy tracking with promotion gates
- **WitnessSet** — Threshold witness configuration per namespace
- **Promotion Workflow** — Submit → collect signatures → finalize
- **Adversarial Tests** — 155 attack vectors proven to fail correctly
- **Lineage Visualizer** — to_audit_text() and to_dot() methods
- **753 passing tests** — Core through Adversarial

## What We're Building (v1.6)

### 1. Shadow Cell Infrastructure

Shadow cells are counterfactual variants of real cells created via `dataclasses.replace()`:

```python
# Create shadow variant of fact
base_fact = chain.get_cell(fact_id)
shadow_fact = dataclasses.replace(
    base_fact,
    object="hypothetical_value",
    cell_id=compute_shadow_cell_id(base_fact, "hypothetical_value")
)
```

**Why shadow cells?**
- Immutable by default (frozen dataclasses)
- Distinct cell_id based on modified content
- Never appended to real chain (structural isolation)
- Reuse existing cell validation logic

### 2. Simulation Core

Oracle layer creates isolated shadow reality for what-if analysis:

```python
# Run simulation
result = engine.simulate_rfa(
    rfa=request,
    simulation_spec={
        "overlay_facts": [shadow_fact],
        "overlay_policy": shadow_policy_head
    },
    at_valid_time=datetime(2026, 1, 15),
    as_of_system_time=datetime(2026, 1, 20)
)

# result.base_result: outcome with real chain
# result.shadow_result: outcome with shadow overlay
# result.delta_report: comparison of outcomes
```

**Context manager pattern ensures cleanup:**
```python
with oracle.simulate(rfa, simulation_spec) as sim:
    shadow_result = sim.run()
# Shadow chain automatically released
```

### 3. Delta Reports

Compare base vs shadow outcomes with deterministic diff computation:

```python
delta_report = {
    "verdict_changed": True,
    "status_before": "APPROVED",
    "status_after": "REJECTED",
    "score_delta": -15,
    "facts_diff": {
        "added": [shadow_fact_id],
        "removed": [],
        "modified": [fact_id_1, fact_id_2]
    },
    "rules_diff": {
        "added": [],
        "removed": [rule_id_3],
        "modified": []
    }
}
```

### 4. Counterfactual Anchors

Identify minimal set of changes causing outcome delta:

```python
# Anchor detection (bounded execution)
anchors = oracle.find_anchors(
    base_result=result.base_result,
    shadow_result=result.shadow_result,
    max_anchor_attempts=100,
    max_runtime_ms=5000
)

# anchors.components: minimal set of shadow facts/rules causing delta
# anchors.incomplete: True if budget exceeded
```

### 5. Batch Backtest

Run simulations over multiple historical RFAs:

```python
backtest_results = oracle.run_backtest(
    rfas=[rfa1, rfa2, rfa3],
    simulation_spec={"overlay_policy": new_policy},
    max_cases=1000,
    max_runtime_ms=30000
)
# Returns deterministically ordered list of SimulationResults
```

### 6. Simulation Audit Trail

Human-readable reports and visualizations:

```python
# Audit text
audit = oracle.to_audit_text()
# Shows base vs shadow comparison with delta summary

# DOT graph with color tags
dot = oracle.to_dot()
# BASE nodes in blue, SHADOW nodes in red
```

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| dataclasses.replace() for shadow cells | Standard library, zero new dependencies | Selected |
| OverlayScholar pattern | Scholar unchanged, shadow queries via separate instance | Selected |
| Context manager for cleanup | Prevents shadow chain memory leaks | Selected |
| Bounded anchor detection | Prevent DoS via exponential traversal | Selected |
| Simulation watermarking | Prevent confusion with real results | Selected |

## Constraints

- **Keep existing 753 tests passing** — No regressions
- **Python 3.10+ only** — Standard library + cryptography
- **Deterministic outputs** — Same input = same output always
- **No external services** — In-memory, self-contained
- **Zero new dependencies** — dataclasses.replace() sufficient

## Out of Scope

- Nested simulations — deferred to v2
- Simulation persistence — one-shot simulations only
- Cross-namespace simulation — single namespace per simulation
- Simulation caching — adds invalidation complexity

## Requirements

### Active (v1.6)

See `.planning/REQUIREMENTS.md` for full list. Summary:

**Shadow Infrastructure (6 requirements):**
- SHD-01 through SHD-06: Shadow cells, overlay context, zero contamination

**Core Simulation (6 requirements):**
- SIM-01 through SIM-06: simulate_rfa() API, frozen coordinates, deterministic outputs

**Counterfactual Analysis (4 requirements):**
- CTF-01 through CTF-04: Delta reports, bounded anchor detection

**Batch Operations (3 requirements):**
- BAT-01 through BAT-03: Backtest API with execution limits

**Audit Trail (3 requirements):**
- AUD-01 through AUD-03: to_audit_text(), to_dot(), proof bundles

**Total: 22 v1.6 requirements**

### Validated (v1.5)

- [x] PolicyHead cell type — active policy tracking
- [x] WitnessSet registry — threshold witness configuration
- [x] Promotion workflow — submit → collect → finalize
- [x] Scholar policy integration — policy-aware queries
- [x] Policy integrity validation — tamper detection
- [x] Policy audit trail — to_audit_text(), to_dot()

### Out of Scope

- Auto-apply simulation results — simulations observe, never mutate
- Unbounded anchor detection — DoS vector
- Cross-namespace simulation — v2 scope
- Real-time simulation streaming — batch sufficient for v1.6
- Simulation caching — one-shot simulations

---

## Completed Milestones

### v1.5: Promotion Gate + Policy Snapshots (Complete)

**Core Value:** Rules are hypotheses until promoted. Promoted rules become the active policy, tracked as PolicyHead cells — enabling bitemporal "what policy was active when?" queries and multi-witness approval workflows.

**Delivered:**
- PolicyHead cell type for active policy management per namespace
- Promotion workflow: submit → collect witness signatures → finalize
- Witness set model with threshold rules (e.g., 2-of-3)
- Bitemporal policy queries (what policy was active as-of date X)
- Policy snapshot hashing for integrity verification

**Metrics:**
- 27/27 requirements complete
- 753 tests passing (517 existing + 236 new)
- 6 phases executed

### v1.4: RFA Layer + Security Hardening (Complete)

**Core Value:** External developers can integrate with DecisionGraph through a single, validated, signed entry point — and every failure returns a deterministic, actionable error code.

**Delivered:**
- RFA processing layer with `engine.process_rfa()`
- 6 standardized error codes (DG_SCHEMA_INVALID through DG_INTERNAL_ERROR)
- Input validation (subject, predicate, object, namespace)
- Ed25519 signature signing and verification
- Adversarial test suite (155 tests for 5 attack vectors)
- Lineage visualizer (to_audit_text, to_dot)

**Metrics:**
- 20/20 requirements complete
- 517 tests passing
- 6 phases executed

---

*Last updated: 2026-01-28 — v1.6 milestone initialized*
