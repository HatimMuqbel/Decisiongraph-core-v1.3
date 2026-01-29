# Requirements: DecisionGraph v1.6

**Defined:** 2026-01-28
**Core Value:** Safe simulation of policy/rule changes against historical data without contaminating the real vault — deterministic, bitemporal, governed, provable, non-mutating.

## v1.6 Requirements

Requirements for v1.6 release. Each maps to roadmap phases.

### Shadow Infrastructure

- [ ] **SHD-01**: Shadow cell types exist (ShadowPolicyHead, ShadowRuleCell, ShadowFactCell, ShadowBridgeCell)
- [ ] **SHD-02**: OverlayContext holds shadow cells with deterministic precedence rules
- [ ] **SHD-03**: SimulationResult contains base_result, shadow_result, delta_report, anchors, proof_bundle
- [ ] **SHD-04**: Zero contamination — simulation never calls Chain.append() for overlay cells
- [ ] **SHD-05**: Bitemporal simulation respects frozen (at_valid_time, as_of_system_time) coordinates
- [ ] **SHD-06**: Simulation proof bundle includes no_contamination_attestation (chain head unchanged)

### Core Simulation

- [ ] **SIM-01**: engine.simulate_rfa() accepts RFA + simulation_spec + coordinates and returns SimulationResult
- [ ] **SIM-02**: Base reality frozen at specified coordinates before simulation
- [ ] **SIM-03**: Shadow overlay injection follows deterministic precedence (shadow overrides base)
- [ ] **SIM-04**: Delta report includes verdict_changed, status_before/after, score_delta, facts_diff, rules_diff
- [ ] **SIM-05**: Proof bundle nodes tagged with origin ("BASE" or "SHADOW")
- [ ] **SIM-06**: Deterministic outputs — same RFA + same simulation_spec = identical SimulationResult

### Counterfactual Analysis

- [ ] **CTF-01**: Delta report computed deterministically with sorted lists
- [ ] **CTF-02**: Execution bounded by limits (max_anchor_attempts, max_runtime_ms)
- [ ] **CTF-03**: Counterfactual anchors identify minimal set of components causing delta
- [ ] **CTF-04**: Anchor detection bounded — returns anchors_incomplete=True if budget exceeded

### Batch Operations

- [ ] **BAT-01**: oracle.run_backtest() executes simulation over multiple RFAs/historical subjects
- [ ] **BAT-02**: Backtest bounded by limits (max_cases, max_runtime_ms, max_cells_touched)
- [ ] **BAT-03**: Backtest output deterministically ordered

### Audit Trail

- [ ] **AUD-01**: oracle.to_audit_text() produces human-readable simulation report
- [ ] **AUD-02**: Simulation proof bundle records RFA hash, simulation_spec hash, overlay cell hashes
- [ ] **AUD-03**: oracle.to_dot() produces BASE vs SHADOW lineage graph with color tags

---

## Validated Requirements (v1.5)

Shipped and confirmed valuable.

### PolicyHead Cell (v1.5)

- [x] **POL-01**: User can create PolicyHead cell with namespace, policy_hash, promoted_rule_ids, and prev_policy_head
- [x] **POL-02**: PolicyHead.policy_hash is deterministically computed as hash(sorted(promoted_rule_ids))
- [x] **POL-03**: PolicyHead chain is append-only with prev_policy_head linking to previous head (or null for first)
- [x] **POL-04**: User can query current PolicyHead for a namespace via `get_current_policy_head(namespace)`

### WitnessSet (v1.5)

- [x] **WIT-01**: User can define WitnessSet with namespace, witnesses list, and threshold
- [x] **WIT-02**: WitnessSet threshold validates 1 <= threshold <= len(witnesses)
- [x] **WIT-03**: Genesis cell can bootstrap initial WitnessSet for a namespace
- [x] **WIT-04**: WitnessSet changes require promotion through existing witness set

### Promotion Workflow (v1.5)

- [x] **PRO-01**: User can call `engine.submit_promotion(namespace, rule_ids, submitter_id)` to create PromotionRequest
- [x] **PRO-02**: User can call `engine.collect_witness_signature(promotion_id, witness_id, signature)` to add witness
- [x] **PRO-03**: PromotionRequest tracks status: PENDING, COLLECTING, THRESHOLD_MET, FINALIZED, REJECTED
- [x] **PRO-04**: User can call `engine.finalize_promotion(promotion_id)` when threshold met, creating PolicyHead cell
- [x] **PRO-05**: Promotion fails with DG_UNAUTHORIZED if witness not in WitnessSet for namespace
- [x] **PRO-06**: Promotion fails with DG_SIGNATURE_INVALID if witness signature verification fails

### Scholar Integration (v1.5)

- [x] **SCH-01**: User can query with `policy_mode="promoted_only"` to use only promoted rules
- [x] **SCH-02**: User can query with `as_of_system_time` to use PolicyHead active at that time
- [x] **SCH-03**: QueryResult includes policy_head_id when policy_mode is promoted_only
- [x] **SCH-04**: Unpromoted rules are ignored when policy_mode="promoted_only"

### Policy Integrity (v1.5)

- [x] **INT-01**: PolicyHead cell signature verifiable via existing verify_signature()
- [x] **INT-02**: policy_hash matches actual hash of promoted_rule_ids (tamper-evident)
- [x] **INT-03**: Cannot promote rules from different namespace (DG_INPUT_INVALID)
- [x] **INT-04**: Cannot finalize promotion without meeting threshold (DG_UNAUTHORIZED)

### Audit Trail (v1.5)

- [x] **AUD-01-v1.5**: PolicyHead.to_audit_text() produces deterministic human-readable policy report
- [x] **AUD-02-v1.5**: PolicyHead chain can be visualized via to_dot() showing policy evolution

### Bootstrap (v1.5)

- [x] **BOT-01**: Genesis cell includes initial WitnessSet for namespace (bootstrap mode)
- [x] **BOT-02**: Bootstrap mode allows 1-of-1 witness set for development
- [x] **BOT-03**: Production mode requires minimum 2-of-N threshold

---

## v2 Requirements (Deferred)

### Advanced Simulation

- **ADV-01**: Nested simulations (simulate within simulation)
- **ADV-02**: Simulation persistence (save/restore simulation contexts)
- **ADV-03**: Simulation branching (fork simulation into multiple paths)

### Integration

- **INT-01-v2**: Simulation results exportable to external audit systems
- **INT-02-v2**: Simulation webhooks for async notification

---

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Auto-apply simulation results | Simulations observe, never mutate — promotion is separate workflow |
| Unbounded anchor detection | DoS vector — must always have execution limits |
| Cross-namespace simulation | v1.6 focuses on single-namespace what-if; cross-namespace is v2 |
| Real-time simulation streaming | Batch is sufficient for v1.6; streaming adds complexity |
| Simulation caching | One-shot simulations; caching adds invalidation complexity |
| Oracle fact injection (external) | In-memory overlay only; external oracles are future milestone |

---

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SHD-01 | Phase 7 | Complete |
| SHD-02 | Phase 7 | Complete |
| SHD-04 | Phase 7 | Complete |
| SIM-01 | Phase 8 | Complete |
| SIM-02 | Phase 8 | Complete |
| SIM-03 | Phase 8 | Complete |
| SHD-05 | Phase 8 | Complete |
| SIM-04 | Phase 9 | Complete |
| SIM-05 | Phase 9 | Complete |
| SIM-06 | Phase 9 | Complete |
| SHD-03 | Phase 9 | Complete |
| SHD-06 | Phase 9 | Complete |
| CTF-01 | Phase 10 | Complete |
| CTF-02 | Phase 10 | Complete |
| CTF-03 | Phase 10 | Complete |
| CTF-04 | Phase 10 | Complete |
| BAT-01 | Phase 11 | Complete |
| BAT-02 | Phase 11 | Complete |
| BAT-03 | Phase 11 | Complete |
| AUD-01 | Phase 12 | Complete |
| AUD-02 | Phase 12 | Complete |
| AUD-03 | Phase 12 | Complete |

**Coverage:**
- v1.6 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0 ✓

---
*Requirements defined: 2026-01-28*
*Last updated: 2026-01-28 — v1.6 COMPLETE (all 22 requirements satisfied)*
