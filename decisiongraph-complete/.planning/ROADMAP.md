# Roadmap: DecisionGraph v1.6 - Oracle Layer

## Milestones

- ✅ **v1.4 RFA Layer** - Phases 1-6 (shipped 2026-01-15)
- ✅ **v1.5 Promotion Gate** - Phases 1-6 (shipped 2026-01-28)
- 🚧 **v1.6 Oracle Layer** - Phases 7-12 (in progress)

## Overview

DecisionGraph v1.6 adds the Oracle layer for counterfactual simulation: users can inject hypothetical facts/policies into a shadow reality and compare outcomes against the real decision chain. This enables "what-if" analysis without contaminating production data — supporting regulatory compliance, policy testing before promotion, and decision analysis. The implementation leverages existing immutability guarantees with zero new dependencies, using Python's dataclasses.replace() and in-memory overlay patterns.

## Phases

<details>
<summary>✅ v1.5 Promotion Gate (Phases 1-6) - SHIPPED 2026-01-28</summary>

### Phase 1: PolicyHead Foundation
**Goal**: PolicyHead cells exist as immutable policy snapshots with deterministic hashing and bootstrap capability
**Plans**: 3 plans (complete)

Plans:
- [x] 01-01: Core PolicyHead infrastructure
- [x] 01-02: PolicyHead chain operations and query
- [x] 01-03: Bootstrap infrastructure

### Phase 2: WitnessSet Registry
**Goal**: Namespaces have configurable witness sets with threshold rules governing promotion approval
**Plans**: 2 plans (complete)

Plans:
- [x] 02-01: WitnessSet frozen dataclass with validation
- [x] 02-02: WitnessRegistry stateless query layer

### Phase 3: Scholar Integration
**Goal**: Scholar respects PolicyHead when resolving facts, enabling policy-aware and bitemporal queries
**Plans**: 2 plans (complete)

Plans:
- [x] 03-01: Extend Scholar with policy_mode parameter
- [x] 03-02: Tests for policy-aware queries

### Phase 4: Promotion Workflow
**Goal**: Users can submit promotion requests, collect witness signatures, and finalize when threshold is met
**Plans**: 3 plans (complete)

Plans:
- [x] 04-01: PromotionRequest dataclass and PromotionStatus enum
- [x] 04-02: Engine.submit_promotion() and Engine.collect_witness_signature()
- [x] 04-03: Engine.finalize_promotion() and integration tests

### Phase 5: Policy Integrity
**Goal**: PolicyHead cells are cryptographically verifiable and protect against tampering
**Plans**: 2 plans (complete)

Plans:
- [x] 05-01: Namespace validation, policy_hash verification, race detection
- [x] 05-02: PolicyHead signature audit trail

### Phase 6: Audit Trail
**Goal**: PolicyHead chain is human-readable and visualizable for audit and debugging
**Plans**: 2 plans (complete)

Plans:
- [x] 06-01: policy_head_to_audit_text() function
- [x] 06-02: policy_head_chain_to_dot() function

**v1.5 Totals**: 14 plans, 753 tests (517 existing + 236 new)

</details>

### 🚧 v1.6 Oracle Layer (In Progress)

**Milestone Goal:** Safe simulation of policy/rule changes against historical data without contaminating the real vault — deterministic, bitemporal, governed, provable, non-mutating.

#### Phase 7: Shadow Cell Foundation

**Goal**: Shadow cells exist without contaminating base chain

**Depends on**: v1.5 complete (Phases 1-6)

**Requirements**: SHD-01, SHD-02, SHD-04

**Success Criteria** (what must be TRUE):
1. User can create shadow variants of any cell type (ShadowPolicyHead, ShadowRuleCell, ShadowFactCell, ShadowBridgeCell) using dataclasses.replace()
2. Shadow cells are frozen dataclasses with distinct cell_id based on modified content
3. Shadow cells never call Chain.append() — structural validation prevents contamination

**Plans**: 2/2 complete

Plans:
- [x] 07-01: Shadow cell creation functions with dataclasses.replace()
- [x] 07-02: OverlayContext container and structural contamination prevention

---

#### Phase 8: Simulation Core

**Goal**: Oracle fork/overlay creates isolated shadow reality

**Depends on**: Phase 7

**Requirements**: SIM-01, SIM-02, SIM-03, SHD-05

**Success Criteria** (what must be TRUE):
1. User can call engine.simulate_rfa() with RFA + simulation_spec + bitemporal coordinates and receive SimulationResult
2. Base reality is frozen at specified (at_valid_time, as_of_system_time) before simulation begins
3. Shadow overlay injection follows deterministic precedence (shadow cells override base cells when both exist)
4. Context manager pattern ensures shadow chain cleanup after simulation completes

**Plans**: 2/2 complete

Plans:
- [x] 08-01-PLAN.md — SimulationContext context manager + SimulationResult frozen dataclass
- [x] 08-02-PLAN.md — Engine.simulate_rfa() method + comprehensive tests

---

#### Phase 9: Delta Report + Proof

**Goal**: Compare base vs shadow outcomes with provable watermarking

**Depends on**: Phase 8

**Requirements**: SIM-04, SIM-05, SIM-06, SHD-03, SHD-06

**Success Criteria** (what must be TRUE):
1. SimulationResult contains base_result, shadow_result, delta_report, anchors, and proof_bundle
2. Delta report includes verdict_changed (bool), status_before/after, score_delta, facts_diff, rules_diff computed deterministically
3. Proof bundle nodes tagged with origin ("BASE" or "SHADOW") for lineage clarity
4. Same RFA + same simulation_spec always produces identical SimulationResult (deterministic outputs)
5. Proof bundle includes no_contamination_attestation proving chain head unchanged after simulation

**Plans**: 2/2 complete

Plans:
- [x] 09-01-PLAN.md — DeltaReport + ContaminationAttestation dataclasses and helper functions
- [x] 09-02-PLAN.md — Engine integration + comprehensive tests

---

#### Phase 10: Counterfactual Anchors

**Goal**: Identify minimal changes causing outcome delta

**Depends on**: Phase 9

**Requirements**: CTF-01, CTF-02, CTF-03, CTF-04

**Success Criteria** (what must be TRUE):
1. Delta report computed deterministically with sorted fact/rule lists (stable diff output) - already complete from Phase 9
2. Counterfactual anchor detection bounded by max_anchor_attempts and max_runtime_ms limits
3. Anchors identify minimal set of shadow components (facts/rules/policy) causing verdict delta
4. When execution budget exceeded, oracle returns anchors_incomplete=True with partial results

**Plans**: 2/2 complete

Plans:
- [x] 10-01-PLAN.md — ExecutionBudget, AnchorResult, detect_counterfactual_anchors module
- [x] 10-02-PLAN.md — Engine integration + comprehensive tests

---

#### Phase 11: Batch Backtest

**Goal**: Run simulations over multiple historical RFAs

**Depends on**: Phase 10

**Requirements**: BAT-01, BAT-02, BAT-03

**Success Criteria** (what must be TRUE):
1. User can call engine.run_backtest() with list of RFAs/historical subjects and receive BatchBacktestResult
2. Backtest bounded by max_cases, max_runtime_ms, max_cells_touched limits to prevent DoS
3. Backtest output deterministically ordered (sorted by subject, then valid_time, then system_time)

**Plans**: 2/2 complete

Plans:
- [x] 11-01-PLAN.md — BatchBacktestResult dataclass + helper functions
- [x] 11-02-PLAN.md — Engine.run_backtest() method + comprehensive tests

---

#### Phase 12: Audit Trail

**Goal**: Human-readable simulation reports and visualizations

**Depends on**: Phase 11

**Requirements**: AUD-01, AUD-02, AUD-03

**Success Criteria** (what must be TRUE):
1. User can call oracle.to_audit_text() and receive human-readable simulation report showing base vs shadow comparison
2. Simulation proof bundle records RFA hash, simulation_spec hash, and all overlay cell hashes for auditability
3. User can call oracle.to_dot() and receive DOT graph with BASE vs SHADOW lineage color-tagged for visualization

**Plans**: 2/2 complete

Plans:
- [x] 12-01-PLAN.md — simulation_result_to_audit_text() function (AUD-01, AUD-02)
- [x] 12-02-PLAN.md — simulation_result_to_dot() function (AUD-03)

---

## Progress

**Execution Order:**
Phases execute in numeric order: 7 → 8 → 9 → 10 → 11 → 12

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. PolicyHead Foundation | v1.5 | 3/3 | Complete | 2026-01-27 |
| 2. WitnessSet Registry | v1.5 | 2/2 | Complete | 2026-01-27 |
| 3. Scholar Integration | v1.5 | 2/2 | Complete | 2026-01-27 |
| 4. Promotion Workflow | v1.5 | 3/3 | Complete | 2026-01-27 |
| 5. Policy Integrity | v1.5 | 2/2 | Complete | 2026-01-28 |
| 6. Audit Trail | v1.5 | 2/2 | Complete | 2026-01-28 |
| 7. Shadow Cell Foundation | v1.6 | 2/2 | Complete | 2026-01-28 |
| 8. Simulation Core | v1.6 | 2/2 | Complete | 2026-01-28 |
| 9. Delta Report + Proof | v1.6 | 2/2 | Complete | 2026-01-28 |
| 10. Counterfactual Anchors | v1.6 | 2/2 | Complete | 2026-01-28 |
| 11. Batch Backtest | v1.6 | 2/2 | Complete | 2026-01-28 |
| 12. Audit Trail | v1.6 | 2/2 | Complete | 2026-01-28 |

---

## Coverage

**v1.6 Requirements:** 22 total
**Mapped:** 22
**Orphaned:** 0

All requirements mapped to phases.

---

*Last updated: 2026-01-28 — v1.6 COMPLETE (all 6 phases delivered, 933 tests passing)*
