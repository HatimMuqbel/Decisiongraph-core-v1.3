# State - DecisionGraph v1.6

**Last Updated:** 2026-01-28 18:50 UTC

---

## Project Reference

**Core Value:** Safe simulation of policy/rule changes against historical data without contaminating the real vault — deterministic, bitemporal, governed, provable, non-mutating.

**Current Focus:** v1.6 milestone - Oracle Layer (Counterfactual Decision Space)

**Foundation (Existing):**
- 933 passing tests (753 from v1.5 + 180 v1.6 tests)
- Cell/Chain/Genesis append-only ledger
- Namespace/Bridge isolation
- Scholar bitemporal query resolver
- RFA layer with Ed25519 signatures
- PolicyHead promotion gates with multi-witness approval
- WitnessSet registry with threshold rules
- 6 deterministic error codes
- Shadow cell creation via dataclasses.replace() (v1.6)
- OverlayContext and fork_shadow_chain (v1.6)
- SimulationContext and SimulationResult (v1.6)
- Engine.simulate_rfa() simulation orchestration with anchor detection (v1.6)
- DeltaReport and ContaminationAttestation (v1.6)
- Delta computation and proof bundle tagging (v1.6)
- Engine delta integration with comprehensive tests (v1.6)
- ExecutionBudget and AnchorResult (v1.6)
- detect_counterfactual_anchors() greedy ablation algorithm (v1.6)
- Anchor detection integrated into Engine.simulate_rfa() (v1.6)
- BatchBacktestResult dataclass with execution tracking (v1.6)
- Engine.run_backtest() with bounded execution (max_cases, max_runtime_ms, max_cells_touched) (v1.6)
- simulation_result_to_audit_text() human-readable audit reports with SHA-256 hashing (v1.6)
- simulation_result_to_dot() DOT graph visualization with BASE vs SHADOW color-tagging (v1.6)

**Constraints:**
- Keep existing 753 tests passing
- Python 3.10+ only
- Deterministic outputs (same input = same output)
- No external services (in-memory, self-contained)
- Zero new dependencies (dataclasses.replace() sufficient)

---

## Current Position

**Phase:** 12 of 12 (Audit Trail - COMPLETE)
**Plan:** 02 of 02 (DOT Visualization - COMPLETE)
**Status:** v1.6 MILESTONE COMPLETE
**Last activity:** 2026-01-28 - Fixed Phase 12 gaps, completed v1.6 milestone

**Progress:** ████████████████████ 100% (12 v1.6 plans complete, all phases delivered)

**Overall:** v1.6 Milestone COMPLETE - All 6 phases (7-12) delivered, 933 tests passing

---

## Performance Metrics

**Velocity:**
- v1.5 milestone: ~2.7 minutes per plan (14 plans)
- v1.6 current: 4.7 minutes per plan average (12 plans: 07-01, 07-02, 08-01, 08-02, 09-01, 09-02, 10-01, 10-02, 11-01, 11-02, 12-01, 12-02)
  - 07-01: 3.5 minutes
  - 07-02: 6 minutes
  - 08-01: 2 minutes
  - 08-02: 6 minutes
  - 09-01: 11 minutes
  - 09-02: 7 minutes
  - 10-01: 2.2 minutes
  - 10-02: 8 minutes
  - 11-01: 2 minutes
  - 11-02: 4.3 minutes
  - 12-01: 2.0 minutes
  - 12-02: 2.5 minutes

**Quality:**
- Test coverage: 933/933 passing
- Regressions: 0 (all existing tests pass)
- New functionality: 180 v1.6 tests (100% pass rate)
  - 18 shadow cell tests (07-01)
  - 15 OverlayContext tests (07-02)
  - 9 contamination prevention tests (07-02)
  - 19 simulation tests (08-01, 08-02)
  - 32 delta report and engine integration tests (09-02)
  - 22 anchor detection tests (10-01, 10-02)
  - 24 batch backtest tests (11-01, 11-02)
  - 41 audit trail tests (22 audit text + 19 DOT visualization) (12-01, 12-02)

**Scope (v1.6):**
- Requirements: 22 total (SHD, SIM, CTF, BAT, AUD)
- Phases: 6 planned (Phases 7-12)
- Plans: TBD (to be determined during phase planning)

---

## Accumulated Context

### Key Decisions

| Decision | Rationale | Phase |
|----------|-----------|-------|
| dataclasses.replace() for shadow cells | Standard library, zero new dependencies, works with frozen dataclasses | Initialization |
| cell_id excluded from replace() (init=False) | cell_id is computed, not assigned - automatically recomputed via __post_init__ | 07-01 |
| Confidence not part of cell_id | Existing design - cell_id based on fact object, not confidence metadata | 07-01 |
| OverlayScholar pattern | Scholar code unchanged, shadow queries via separate instance | Initialization |
| Context manager for cleanup | Prevents shadow chain memory leaks | Initialization |
| Bounded anchor detection | Prevent DoS via exponential traversal (max_anchor_attempts, max_runtime_ms) | Initialization |
| Simulation watermarking | Proof bundles tagged as hypothetical to prevent confusion with real results | Initialization |
| Zero contamination guarantee | Structural isolation via separate Chain instances (fork_shadow_chain) | 07-02 |
| Tuple fact keys for OverlayContext | Deterministic O(1) lookup, no hash collision risk from string concat | 07-02 |
| List accumulation for shadow_facts | Multiple shadow facts per key (temporal, confidence variations) | 07-02 |
| Shallow copy for fork_shadow_chain | Memory efficient - cells immutable, only list/dict containers copied | 07-02 |
| Shadow cells appended before Scholar creation | Scholar queries chain it's given - append first ensures Scholar sees shadow cells | 08-01 |
| Context manager for simulation cleanup | Guarantees shadow resource cleanup even on exception | 08-01 |
| Frozen SimulationResult | Immutable results prevent accidental modification | 08-01 |
| simulate_rfa() orchestration | Single method handles complete simulation workflow (validation, base query, overlay build, shadow query, result packaging) | 08-02 |
| Frozen coordinates for both queries | Base and shadow queries use same at_valid_time and as_of_system_time for fair comparison | 08-02 |
| _build_overlay_context() builder | Converts user-friendly dict format to OverlayContext, gracefully handles missing cells | 08-02 |
| DeltaReport frozen dataclass | Immutable delta report ensures reproducible "before vs after" analysis with deterministic sorting | 09-01 |
| ContaminationAttestation with SHA-256 | Cryptographic tamper-evident proof of chain integrity before/after simulation | 09-01 |
| tag_proof_bundle_origin uses deep copy | Preserves original proof bundle immutability while adding lineage metadata | 09-01 |
| SimulationResult extended with Optional fields | Backward compatible with existing Phase 8 code via Optional delta_report and default_factory | 09-01 |
| Chain head capture for contamination detection | Engine captures chain.head.cell_id before and after simulation for cryptographic proof of zero contamination | 09-02 |
| proof_bundle assembly with tagged bundles | Structured dict with base/shadow/attestation provides clean API and extensibility for future phases | 09-02 |
| Comprehensive Phase 9 test suite | 32 tests isolate each component and verify Engine integration, ensuring all requirements met | 09-02 |
| 6-phase structure (7-12) | Derived from requirement dependencies: Foundation → Core → Reports → Anchors → Batch → Audit | Roadmap |
| Greedy ablation over exhaustive search | Polynomial time (O(N²)) vs exponential (2^N), locally minimal sufficient for debugging | 10-01 |
| Bounded execution mandatory | Unbounded anchor search is DoS vector, return anchors_incomplete=True when budget exceeded | 10-01 |
| Component-level anchor granularity | Track at cell_id level, not field level (coarser but simpler) | 10-01 |
| Return first minimal anchor | Multiple disjoint minimal sets could exist, greedy returns first found (not all) | 10-01 |
| Conditional anchor detection (only when verdict_changed=True) | Avoid expensive anchor search when shadow doesn't change verdict | 10-02 |
| Empty anchor structure when no verdict change | Consistent API - always return anchor dict with fields | 10-02 |
| Default bounded execution limits | max_anchor_attempts=100, max_runtime_ms=5000 balance performance vs completeness | 10-02 |
| Frozen BatchBacktestResult dataclass | Follows SimulationResult immutability pattern for batch execution results | 11-01 |
| Underscore prefix for helper functions | _sort_results and _count_cells_in_simulation are internal but testable | 11-01 |
| Deterministic sorting key (subject, valid_time, system_time) | Three-level sort ensures reproducible batch results ordering | 11-01 |
| Cell counting from base and shadow proof bundles | Aggregate fact_cell_ids, candidate_cell_ids, bridges_used for budget tracking | 11-01 |
| Reused ExecutionBudget for run_backtest | Consistent bounded execution pattern across Engine methods (simulate_rfa, run_backtest) | 11-02 |
| Separate max_cells_touched check | Cumulative metric (sum across simulations) requires separate check from per-iteration budget | 11-02 |
| Sort before return in run_backtest | Call _sort_results() before returning BatchBacktestResult (cleaner API guarantee) | 11-02 |
| Empty rfa_list returns success | Empty input returns empty result with backtest_incomplete=False (not error) | 11-02 |
| Follow QueryResult.to_audit_text() pattern | Consistent audit pattern with lines.append() + '\n'.join(lines) | 12-01 |
| SHA-256 for RFA and simulation spec hashing | Canonical JSON hashing (sort_keys=True) for auditability (AUD-02) | 12-01 |
| Truncate IDs to 16 chars in audit text | Improves readability while maintaining uniqueness prefix | 12-01 |
| [SHADOW] tags for shadow-only facts | Visual clarity for facts not present in base reality | 12-01 |
| Follow QueryResult.to_dot() pattern | Consistent DOT visualization pattern with helper functions inside | 12-02 |
| BASE vs SHADOW color-tagging | Orange for shadow-only nodes, lightblue for base nodes (intuitive visual distinction) | 12-02 |
| Anchor highlighting with double border | peripheries=2 and penwidth=3.0 for visual prominence | 12-02 |
| Delta highlighting colors | lightgreen (added), pink (removed), red diamond (verdict change) | 12-02 |
| Deterministic sorted fact lists | sorted() on all lists before iteration for reproducible DOT output | 12-02 |

### Carried from v1.5

- PolicyHead cell pattern for policy tracking
- Threshold signatures with WitnessSet registry
- Policy-aware Scholar queries (policy_mode parameter)
- Bitemporal policy lookups (as_of_system_time)
- Determinism discipline: no now() calls, no random, sorted iteration
- Bootstrap mode pattern for development

### Active TODOs

- [x] Plan Phase 7: Shadow Cell Foundation (COMPLETE)
  - [x] 07-01: Shadow Cell Creation (COMPLETE)
  - [x] 07-02: OverlayContext + Contamination Prevention (COMPLETE)
- [x] Phase 8: Simulation Core (COMPLETE)
  - [x] 08-01: SimulationContext + SimulationResult (COMPLETE)
  - [x] 08-02: Simulation Engine Orchestration (COMPLETE)
- [x] Phase 9: Delta Report + Proof (COMPLETE)
  - [x] 09-01: DeltaReport and ContaminationAttestation (COMPLETE)
  - [x] 09-02: Engine Integration for Delta Reporting (COMPLETE)
- [x] Phase 10: Counterfactual Anchors (COMPLETE)
  - [x] 10-01: Anchor Detection Module (COMPLETE)
  - [x] 10-02: Engine Integration for Anchor Detection (COMPLETE)
- [x] Phase 11: Batch Backtest (COMPLETE)
  - [x] 11-01: Backtest Foundation (COMPLETE)
  - [x] 11-02: Engine Integration for Batch Backtest (COMPLETE)
- [x] Phase 12: Audit Trail (COMPLETE)
  - [x] 12-01: Audit Text Generation (COMPLETE)
  - [x] 12-02: DOT Visualization (COMPLETE)

### Blockers

None. Phase 12 complete. v1.6 milestone complete - all 6 phases (7-12) delivered.

### Research Flags (from SUMMARY.md)

**Phases needing deeper research during planning:**
- ~~Phase 8 (Simulation Core): Optimal structural sharing strategy~~ - RESOLVED in 07-02 (shallow copy with shared immutable cells)
- No other phases flagged for additional research (standard patterns apply)

### Learnings

(Carried from v1.5 + new from v1.6)

- Frozen dataclasses prevent field reassignment and ensure immutability
- Context managers (with statement) ensure cleanup even on exceptions
- Structural sharing via immutable references more efficient than deep copy
- Deterministic hashing requires explicit sorting before serialization
- Test-first approach validates integration immediately
- Zero contamination requires structural validation, not just convention
- **NEW (07-01):** dataclasses.replace() automatically calls __post_init__, enabling automatic cell_id recomputation
- **NEW (07-01):** Nested replace() required for modifying nested dataclass fields (e.g., fact.object)
- **NEW (07-01):** Confidence changes alone don't affect cell_id (by existing design)
- **NEW (07-02):** Tuple keys provide O(1) lookup with no hash collision risk (vs string concat)
- **NEW (07-02):** Shallow copy is safe and efficient for immutable frozen dataclasses
- **NEW (07-02):** Structural isolation (separate Chain instances) impossible to violate
- **NEW (08-01):** Context manager __exit__ ALWAYS runs, guaranteeing cleanup even on exception
- **NEW (08-01):** Shadow cells appended before Scholar creation ensures Scholar sees them during query
- **NEW (08-02):** simulate_rfa() single entry point simplifies API - one call for complete simulation workflow
- **NEW (08-02):** Frozen coordinates (same at_valid_time, as_of_system_time) for base and shadow queries ensures bitemporal consistency
- **NEW (08-02):** _build_overlay_context() gracefully handles nonexistent base_cell_id (skips silently)
- **NEW (09-01):** sorted() on set differences ensures determinism (same inputs = identical DeltaReport)
- **NEW (09-01):** Deep copy (copy.deepcopy) required to avoid mutating nested dicts/lists in proof bundles
- **NEW (09-02):** Chain head capture timing critical - must be before/after simulation boundaries
- **NEW (09-02):** Test fixtures need current timestamps (get_current_timestamp) to avoid TemporalViolation
- **NEW (09-02):** 13-step pipeline in Engine.simulate_rfa() clearly documents Phase 9 integration flow
- **NEW (09-01):** Optional[Type] = None and field(default_factory=dict) enable backward compatibility with existing code
- **NEW (09-01):** SHA-256 provides cryptographic tamper-evidence (collision-resistant, 256-bit security)
- **NEW (10-01):** Greedy ablation finds locally minimal anchors (sufficient for debugging, not globally optimal)
- **NEW (10-01):** ExecutionBudget checks both in outer and inner loops prevent timeout exceeded by large margin
- **NEW (10-01):** Deep copy simulation_spec before filtering prevents contamination during iterative ablation
- **NEW (10-02):** Conditional expensive operations crucial for performance (only run when needed)
- **NEW (10-02):** Consistent API structure better than null/None (always return anchor dict)
- **NEW (10-02):** Test fixture timestamps must use current time for bitemporal queries (get_current_timestamp)
- **NEW (10-02):** Shadow fact replacement doesn't change fact_count (replaces base, not adds)
- **NEW (11-01):** Frozen dataclass pattern consistency - BatchBacktestResult follows SimulationResult for immutability
- **NEW (11-01):** Helper function naming with underscore prefix signals internal use while maintaining testability
- **NEW (11-01):** Three-level sort key (subject, valid_time, system_time) ensures deterministic ordering
- **NEW (11-01):** .get() with defaults prevents KeyError on missing dict keys (graceful degradation)
- **NEW (11-02):** ExecutionBudget reuse across Engine methods (simulate_rfa, run_backtest) creates consistent bounded execution pattern
- **NEW (11-02):** Cumulative metrics (max_cells_touched) require separate check from per-iteration budget (max_cases, max_runtime_ms)
- **NEW (11-02):** Sort before return ensures API contract (caller always receives sorted results, never needs to sort)
- **NEW (11-02):** Empty input = success pattern (empty list returns success, not error) follows principle of least surprise
- **NEW (12-01):** lines.append() + '\n'.join(lines) pattern for deterministic multi-line text generation
- **NEW (12-01):** SHA-256 of canonical JSON (sort_keys=True, separators=(',', ':')) for reproducible hashing
- **NEW (12-01):** Truncate IDs to 16 chars improves readability while maintaining enough entropy for identification
- **NEW (12-01):** [SHADOW] visual tags improve human readability of overlay differences
- **NEW (12-02):** Helper functions inside to_dot() keep namespace clean (same pattern as QueryResult.to_dot())
- **NEW (12-02):** Color coding intuitive: orange=new, pink=removed, green=added, red=alert
- **NEW (12-02):** Deterministic sorted() on fact lists essential for reproducible visualization
- **NEW (12-02):** DOT subgraphs (cluster_base, cluster_shadow) provide clear visual separation

---

## Session Continuity

**Last session:** 2026-01-28 18:50 UTC
**Stopped at:** v1.6 Milestone COMPLETE
**Resume file:** None (milestone complete)

**v1.6 Milestone Status:**
- Phase 7: COMPLETE (Shadow Cell Foundation)
  - 07-01: Shadow Cell Creation ✓
  - 07-02: OverlayContext + Contamination Prevention ✓
- Phase 8: COMPLETE (Simulation Core)
  - 08-01: SimulationContext + SimulationResult ✓
  - 08-02: Simulation Engine Orchestration ✓
  - Requirements satisfied: SHD-01, SHD-02, SHD-03, SHD-04, SHD-05, SIM-01, SIM-02, SIM-03
- Phase 9: COMPLETE (Delta Report + Proof)
  - 09-01: DeltaReport and ContaminationAttestation ✓
  - 09-02: Engine Integration for Delta Reporting ✓
  - Requirements satisfied: SIM-04, SIM-05, SIM-06, SHD-03 (extended), SHD-06
- Phase 10: COMPLETE (Counterfactual Anchors)
  - 10-01: Anchor Detection Module ✓
  - 10-02: Engine Integration for Anchor Detection ✓
  - Requirements satisfied: CTF-01, CTF-02, CTF-03, CTF-04
- Phase 11: COMPLETE (Batch Backtest)
  - 11-01: Backtest Foundation ✓
  - 11-02: Engine Integration for Batch Backtest ✓
  - Requirements satisfied: BAT-01, BAT-02, BAT-03
- Phase 12: COMPLETE (Audit Trail)
  - 12-01: Audit Text Generation ✓
  - 12-02: DOT Visualization ✓
  - Requirements satisfied: AUD-01, AUD-02, AUD-03
  - 933/933 tests passing (0 regressions)

**v1.6 MILESTONE STATUS: COMPLETE**

All 22 requirements satisfied:
- SHD-01 through SHD-06: Shadow infrastructure
- SIM-01 through SIM-06: Core simulation
- CTF-01 through CTF-04: Counterfactual analysis
- BAT-01 through BAT-03: Batch operations
- AUD-01 through AUD-03: Audit trail

**Next steps:**
- Tag v1.6 release
- Update MILESTONES.md to archive v1.6
- Integration testing and stakeholder demonstrations
- Consider v1.7/v2.0 planning (advanced simulation features)

---

*This file is the single source of truth for project state. Update after every phase/plan completion.*
