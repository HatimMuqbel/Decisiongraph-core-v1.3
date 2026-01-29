# Research Summary: DecisionGraph v1.6 — Oracle Layer

**Project:** DecisionGraph v1.6 Oracle Layer for Counterfactual Simulation
**Domain:** Append-only decision engine with "what-if" simulation capabilities
**Researched:** 2026-01-28
**Confidence:** HIGH (core patterns), MEDIUM (integration specifics)

## Executive Summary

DecisionGraph v1.6 adds the Oracle layer to enable counterfactual "what-if" simulation: users can inject hypothetical facts into a shadow reality and compare outcomes against the real decision chain. This feature supports regulatory compliance ("what if policy had been different?"), policy testing before promotion, and decision analysis without contaminating production data.

Research reveals that counterfactual simulation for append-only ledgers requires zero contamination guarantees (simulation never mutates real chain), deterministic outputs (same inputs always produce same results), and efficient structural sharing to avoid O(N) deep copy overhead. The critical innovation: **no new dependencies are required**. Python's standard library `dataclasses.replace()` and in-memory overlay patterns are sufficient. The Oracle layer builds on existing DecisionGraph primitives (immutable cells, bitemporal queries, cryptographic sealing) without modification to the core chain or scholar.

The primary risks are chain contamination (simulation cells leak into production ledger) and non-deterministic overlay application. Both are addressable through context manager patterns for isolation, explicit simulation timestamps, and sorted overlay precedence. The v1.6 implementation must maintain backwards compatibility with 753 existing tests while adding simulation capabilities.

## Key Findings

### Recommended Stack

**STACK.md summary:** Zero new dependencies required. Counterfactual simulation leverages existing DecisionGraph immutability guarantees and standard library features.

**Core technologies:**
- **Python 3.10+ dataclasses.replace()** — Efficient shallow copy for creating shadow cells — Standard library, zero dependencies
- **In-memory overlay pattern** — Two Chain instances (base + shadow) in same process — Structural isolation without modification
- **Python difflib** — Delta computation for comparing base vs shadow state — Standard library, designed for sequence comparison
- **Deterministic execution** — Same simulation inputs always produce identical outputs — Extends existing DecisionGraph guarantee

**Not adding:**
- Pyrsistent library (structural sharing benefits large persistent structures, not one-shot simulations)
- CARLA/DiCE (ML model explainability, different domain from decision engine simulation)
- Temporal.io (workflow orchestration, not in-memory simulation)

**Confidence:** HIGH — All recommendations based on DecisionGraph's existing frozen dataclass architecture. Standard library patterns are well-documented and verified.

### Expected Features

**Must have (table stakes for simulation):**
- Shadow chain creation without contaminating base chain
- Counterfactual fact injection into shadow reality
- Delta reports comparing base vs shadow outcomes
- Deterministic simulation outputs (reproducibility)
- Zero contamination guarantee (real chain never mutated)
- Bitemporal simulation (respects valid_time and system_time)

**Should have (differentiators):**
- Counterfactual anchors (minimal change explanation: which fact changes caused outcome delta)
- Shadow PolicyHead simulation (test policy changes before promotion)
- Bridge-aware simulation (namespace isolation preserved)
- Simulation watermarking (proof bundles clearly marked as hypothetical)

**Defer to v1.7+:**
- Persistent shadow state across multiple simulations
- Incremental simulation (reuse shadow chain for multiple scenarios)
- Simulation time-travel (fork from arbitrary chain state, not just HEAD)

**Confidence:** HIGH for must-haves (standard simulation requirements), MEDIUM for differentiators (DecisionGraph-specific features need requirements validation).

### Architecture Approach

**Major Oracle components:**
1. **Oracle class** — Layer 5 orchestrator that creates shadow reality, injects counterfactual facts, and computes deltas
2. **Shadow Chain** — Parallel Chain instance forked from base chain, accepts hypothetical cells without affecting production
3. **Shadow Scholar** — Scholar instance querying shadow chain with identical bitemporal logic
4. **DeltaReport** — Diff between base QueryResult and shadow QueryResult (which facts changed, which decisions changed)
5. **SimulationConfig** — Explicit parameters for deterministic simulation (frozen timestamp, sorted overlays, seeded RNG)

**Integration points:**
- Chain: Shadow chain uses same append/validation logic (zero modification)
- Scholar: Shadow Scholar instance queries shadow chain (zero modification to Scholar code)
- Engine: Oracle wraps Engine to provide simulation entry points (Engine remains Layer 4)
- PolicyHead: Shadow reality can simulate policy changes (test promotion before executing)

**Confidence:** HIGH for component boundaries, MEDIUM for PolicyHead simulation semantics (requires requirements clarification: does simulating PolicyHead change which rules apply?).

### Critical Pitfalls

Top 5 from PITFALLS.md (14 total pitfalls researched):

1. **Chain Contamination (CATASTROPHIC)** — Simulation cells leak into production ledger. Once contaminated, append-only chain cannot be cleaned. **Prevention:** Context manager pattern with immutable base chain reference, structural sharing (not deep copy), validation before any real append.

2. **Non-Deterministic Overlay Precedence** — Dict iteration order or hash tiebreaking without lexicographic fallback causes same simulation to produce different results. **Prevention:** Sorted overlay application by (namespace, subject, predicate, cell_id), explicit simulation timestamp (never `get_current_timestamp()`), deterministic Scholar conflict resolution.

3. **Bitemporal Confusion** — Mixing simulation_time with real system_time causes incorrect fact visibility (e.g., simulation uses PolicyHead that didn't exist at simulated time). **Prevention:** Parse timestamps as datetime objects (not string comparison), explicit simulation parameters for both valid_time and system_time axes, document time semantics clearly.

4. **Unbounded Anchor Detection** — Recursive anchor detection without depth limit causes exponential traversal, timeouts, or memory exhaustion (especially with circular Bridges). **Prevention:** Max depth limit (10 hops), visited set for cycle detection, iterative (not recursive) traversal, timeout decorators.

5. **Proof Bundle Contamination** — Simulation results presented as real decisions to auditors/compliance systems. **Prevention:** Simulation flag in QueryResult (`simulation=True`), proof bundle watermarking with simulation_metadata, distinct UI rendering (red "SIMULATION" banner).

**Also critical:** Scholar modification breaking 753 existing tests (Phase 3 risk), memory leaks from unreleased simulation chains (all phases), deep copy performance degradation (O(N) overhead per simulation).

**Confidence:** HIGH for pitfalls 1-5 (verified against DST literature, snapshot isolation patterns, bitemporal DB documentation).

## Implications for Roadmap

Based on combined research, the Oracle layer naturally structures into 6 phases following DecisionGraph's layered architecture:

### Phase 1: Shadow Cell Factory
**Rationale:** Foundation phase establishes shadow cell creation using `dataclasses.replace()` pattern. Must implement chain isolation and deterministic execution from the start (non-negotiable for all subsequent phases).

**Delivers:**
- Shadow cell creation via `dataclasses.replace()`
- Immutability validation (shadow cells are frozen like base cells)
- Deterministic hashing (shadow cells have distinct cell_id based on modified content)

**Stack:** Standard library `dataclasses.replace()`, existing Cell dataclass structure
**Avoids:** Pitfall 1 (chain contamination via shallow reference), Pitfall 2 (non-deterministic cell creation)
**Complexity:** LOW (standard library pattern)

### Phase 2: Oracle Fork/Overlay
**Rationale:** Second foundation phase creates structural isolation between base and shadow chains. Context manager pattern ensures cleanup and prevents contamination.

**Delivers:**
- `Oracle.fork_shadow_reality()` creates shadow Chain instance
- Shadow chain shares immutable cells from base (structural sharing, not deep copy)
- Shadow Scholar instance for querying shadow chain
- Context manager pattern (`with Oracle.simulate() as sim:`) for automatic cleanup

**Stack:** In-memory overlay pattern, Python context managers
**Avoids:** Pitfall 1 (chain contamination), Pitfall 12 (memory leaks from unreleased references), Pitfall 13 (deep copy O(N) overhead)
**Complexity:** MEDIUM (Chain/Scholar instantiation, structural sharing strategy)

### Phase 3: Counterfactual Injection
**Rationale:** With isolated shadow chain established, add capability to inject hypothetical facts. Reuses existing cell creation logic from Engine.

**Delivers:**
- `Oracle.inject_counterfactual_fact()` creates shadow fact cells
- Shadow chain appends accept new facts (validation reused from base chain)
- Base chain guaranteed unchanged (validation step)
- Deterministic injection ordering (sorted by namespace, subject, predicate)

**Stack:** Reuses Engine's cell creation logic
**Avoids:** Pitfall 1 (contamination validation), Pitfall 2 (sorted injection for determinism)
**Complexity:** LOW (reuses existing primitives)

### Phase 4: Delta Computation
**Rationale:** Core Oracle value proposition: compare base vs shadow outcomes. Standard set operations over fact lists.

**Delivers:**
- `compute_fact_diff()` using set operations on base vs shadow QueryResults
- DeltaReport dataclass with added/removed/modified facts
- Fact-level comparison (which subjects/predicates changed)
- Decision-level comparison (did final outcome differ?)

**Stack:** Python `difflib` for structured comparison, set operations for fact deltas
**Avoids:** Pitfall 5 (DeltaReport must be watermarked as simulation output)
**Complexity:** MEDIUM (state comparison logic, diff presentation)

### Phase 5: Deterministic Simulation Framework
**Rationale:** Tie together all components with explicit determinism guarantees. SimulationRequest/SimulationResult enforce reproducibility.

**Delivers:**
- SimulationConfig dataclass (frozen timestamp, sorted overlays, simulation_id)
- SimulationRequest with deterministic inputs (base_chain_hash, counterfactual_facts, query_params)
- SimulationResult with watermarking (simulation=True flag, simulation_metadata)
- Validation: same SimulationRequest always produces identical SimulationResult

**Stack:** Frozen timestamps (explicit parameter, never `get_current_timestamp()`), deterministic simulation_id generation
**Avoids:** Pitfall 2 (non-determinism), Pitfall 9 (timestamp variation), Pitfall 5 (proof bundle contamination)
**Complexity:** MEDIUM (input validation, determinism testing, watermarking)

### Phase 6: PolicyHead Integration
**Rationale:** Enable "what if we promoted different policy?" scenarios. Requires resolving PolicyHead precedence semantics (does simulated PolicyHead override base PolicyHead?).

**Delivers:**
- Shadow PolicyHead simulation (inject hypothetical PolicyHead into shadow chain)
- Policy mode parameter: `base_only` (use real policy) vs `allow_simulated_policy` (use shadow policy)
- Scholar integration: PolicyHeadResolver respects shadow PolicyHead when querying shadow chain
- Test policy changes before actual promotion (v1.5 integration)

**Stack:** Reuses PolicyHead cells from v1.5, PolicyHeadResolver bitemporal query logic
**Avoids:** Pitfall 7 (PolicyHead simulation paradox — explicit semantics resolve precedence)
**Complexity:** MEDIUM-HIGH (policy precedence resolution, bitemporal interaction)
**Research flag:** Requires requirements clarification on PolicyHead simulation semantics

### Phase Ordering Rationale

**Sequential dependencies:**
1. Phase 1 → Phase 2 (shadow cells must exist before shadow chain)
2. Phase 2 → Phase 3 (shadow chain must exist before injection)
3. Phase 3 → Phase 4 (need shadow facts before computing deltas)
4. Phase 4 → Phase 5 (delta computation integrated into deterministic framework)
5. Phase 5 → Phase 6 (determinism established before complex PolicyHead interaction)

**Parallelization opportunities:** None — strict sequential dependency chain.

**Critical path validation:** Each phase builds on previous foundations. Cannot defer Phase 1 or Phase 2 (contamination and determinism are non-negotiable). Phase 6 could be deferred to v1.7 if PolicyHead simulation semantics are complex.

**Why this avoids pitfalls:**
- Phases 1-2 establish isolation and determinism (addresses Pitfalls 1, 2, 9, 12, 13)
- Phase 3 validates contamination prevention (Pitfall 1 tests)
- Phase 4 introduces watermarking (Pitfall 5)
- Phase 5 formalizes determinism guarantees (Pitfalls 2, 9, 10, 11)
- Phase 6 isolated from core (prevents breaking v1.5, addresses Pitfall 6)

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 2 (Oracle Fork/Overlay):** Optimal structural sharing strategy for DecisionGraph's cell structure (RRB-Tree? HAMTs? Custom persistent data structure? Or simple shared list reference?)
- **Phase 6 (PolicyHead Integration):** PolicyHead simulation semantics require requirements definition (does shadow PolicyHead change rule application? Bitemporal precedence rules?)

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Shadow Cell Factory):** Standard `dataclasses.replace()` pattern, well-documented
- **Phase 3 (Counterfactual Injection):** Reuses existing Engine cell creation logic
- **Phase 4 (Delta Computation):** Standard set operations and diffing

**Phases requiring Scholar integration caution:**
- **Phase 6 (PolicyHead Integration):** Modify Scholar.query_facts() or create separate `query_facts_with_simulation()` to avoid breaking 753 tests (Pitfall 6)

**Recommend /gsd:research-phase for:**
- Phase 2: "Research optimal structural sharing for shadow chain creation"
- Phase 6: "Research PolicyHead simulation precedence semantics"

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero new dependencies, standard library patterns verified in Python 3.13 docs and DecisionGraph's existing frozen dataclass architecture |
| Features | HIGH | Table stakes features well-defined (shadow chain, injection, deltas, determinism). Differentiators like counterfactual anchors need requirements validation |
| Architecture | MEDIUM-HIGH | Component boundaries clear (Oracle, Shadow Chain, Shadow Scholar, DeltaReport). PolicyHead simulation semantics need clarification |
| Pitfalls | HIGH | 14 pitfalls researched, top 5 critical risks verified against DST literature, snapshot isolation papers, bitemporal DB documentation |

**Overall confidence:** HIGH for core Oracle implementation (Phases 1-5), MEDIUM for PolicyHead integration (Phase 6 needs requirements work).

### Gaps to Address

**Structural sharing strategy (Phase 2):** Should shadow chain deep copy all cells or share immutable cell references? Research recommends structural sharing for performance, but implementation complexity depends on Chain's internal structure. **Resolution:** Profile both approaches during Phase 2 planning — if chain has circular references or mutable internal state, structural sharing becomes complex.

**PolicyHead simulation semantics (Phase 6):** When simulation injects hypothetical PolicyHead, does that change which rules are considered promoted for the shadow query? Two interpretations:
1. **Base policy only:** Shadow PolicyHead is just data, doesn't affect rule application (simpler)
2. **Simulated policy affects rules:** Shadow PolicyHead determines promoted rules for shadow Scholar (more powerful, enables "what if we promoted rule X?" scenarios)

**Resolution:** Requires product decision during requirements phase. Recommend option 2 with explicit `policy_mode` parameter for clarity.

**Bridge authorization under simulation (Phase 6):** Can simulation create hypothetical Bridges that bypass real authorization? Or must shadow Bridges respect base authorization model? **Resolution:** Shadow Bridges should be validated against base authorization (preserve security model). Flag for Phase 6 design review.

**Performance benchmarks:** What's acceptable simulation overhead vs real query? 2x? 10x? **Resolution:** Establish performance SLOs during Phase 5 planning (recommend <2x overhead for interactive what-if analysis).

## Sources

### Primary (HIGH confidence)
- **STACK.md** — Python 3.13 dataclasses.replace(), Pyrsistent evaluation, immutable data structure patterns
- **FEATURES_ORACLE.md** — Oracle-specific features (counterfactual injection, delta reports, simulation watermarking)
- **ORACLE_ARCHITECTURE.md** — Oracle component architecture, shadow overlay patterns, integration points
- **PITFALLS.md** — 14 pitfalls with prevention strategies, verified against DST and snapshot isolation literature

### Secondary (MEDIUM confidence from web research)
- [Deterministic Simulation Testing (Antithesis)](https://antithesis.com/resources/deterministic_simulation_testing/) — DST principles for state isolation
- [Python 3.13 copy.replace()](https://medium.com/@bnln/python-3-13s-new-copy-replace-24bf61c37be7) — New standard library feature
- [Pyrsistent GitHub](https://github.com/tobgu/pyrsistent) — Structural sharing benefits for persistent structures
- [XTDB Bitemporality](https://v1-docs.xtdb.com/concepts/bitemporality/) — Bitemporal query semantics
- [Snapshot Isolation Memory Leaks (VLDB 2024)](https://www.vldb.org/pvldb/vol16/p1426-alhomssi.pdf) — Memory management in snapshot isolation
- [Peridot Conflict Resolution](https://fuchsia.googlesource.com/peridot/+/master/docs/ledger/conflict_resolution.md) — Deterministic merge strategies

### Tertiary (LOW confidence, needs validation)
- Counterfactual anchor algorithm (minimal change explanation) — no direct research found, needs algorithm design during Phase 4 or defer to v1.7

---
*Research completed: 2026-01-28*
*Ready for roadmap: YES*
*Recommended roadmap structure: 6 sequential phases (Phases 1-5 core MVP, Phase 6 PolicyHead integration optional)*
