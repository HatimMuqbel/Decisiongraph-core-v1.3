# Codebase Structure

**Version:** 2.0
**Analysis Date:** 2026-01-29
**Tests:** 1432 passing
**Modules:** 26 Python files (16,824 lines)

---

## Architecture Overview

DecisionGraph is a zero-trust decision engine with cryptographic namespace isolation. The codebase is organized into **6 architectural layers**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LAYER 6: REPORT GENERATION                       │
│  template.py │ report.py │ justification.py                        │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 5: DOMAIN CONFIGURATION                    │
│  pack.py │ rules.py                                                 │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 4: SIMULATION (ORACLE)                     │
│  simulation.py │ shadow.py │ anchors.py │ backtest.py              │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 3: GOVERNANCE                              │
│  policyhead.py │ promotion.py │ witnessset.py │ registry.py        │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 2: QUERY & VALIDATION                      │
│  scholar.py │ engine.py │ validators.py │ exceptions.py            │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 1: STORAGE PRIMITIVES                      │
│  cell.py │ chain.py │ genesis.py │ namespace.py │ canon.py         │
│  wal.py │ segmented_wal.py │ signing.py                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Directory Layout

```
decisiongraph-complete/
├── README.md                    # Quick start and overview
├── pyproject.toml              # Package metadata, pytest config
├── docs/
│   ├── ARCHITECTURE.md         # Detailed architecture documentation
│   ├── GENESIS_CHECKLIST.md    # 22-point Genesis verification checklist
│   ├── SCHEMA_V1.3.md          # Complete schema specification
│   └── ROADMAP.md              # Future development plan
├── specs/
│   ├── DecisionGraph.tla       # TLA+ formal specification (14 invariants)
│   └── DecisionGraphV2.tla     # TLA+ spec with namespace invariants
├── src/decisiongraph/          # 26 modules, 16,824 lines
│   ├── __init__.py             # Public API exports
│   │
│   │  ─── LAYER 1: STORAGE PRIMITIVES ───
│   ├── cell.py                 # Cell types, hashing, validation (722 lines)
│   ├── chain.py                # Append-only ledger, Commit Gate (660 lines)
│   ├── genesis.py              # Bootstrap cell, 22-point verification (873 lines)
│   ├── namespace.py            # Namespace isolation, bridges (471 lines)
│   ├── canon.py                # RFC 8785 canonical JSON (557 lines)
│   ├── wal.py                  # Write-ahead log persistence (797 lines)
│   ├── segmented_wal.py        # Unbounded storage segments (838 lines)
│   ├── signing.py              # Ed25519 signatures (236 lines)
│   │
│   │  ─── LAYER 2: QUERY & VALIDATION ───
│   ├── scholar.py              # Bitemporal query resolver (1,180 lines)
│   ├── engine.py               # RFA processing orchestrator (1,141 lines)
│   ├── validators.py           # Input validation (262 lines)
│   ├── exceptions.py           # 6 DG_* error codes (296 lines)
│   │
│   │  ─── LAYER 3: GOVERNANCE ───
│   ├── policyhead.py           # Active policy tracking (893 lines)
│   ├── promotion.py            # Submit → collect → finalize (215 lines)
│   ├── witnessset.py           # Threshold witness rules (109 lines)
│   ├── registry.py             # WitnessSet registry (248 lines)
│   │
│   │  ─── LAYER 4: SIMULATION (ORACLE) ───
│   ├── simulation.py           # SimulationContext, DeltaReport (707 lines)
│   ├── shadow.py               # Shadow cells, OverlayContext (540 lines)
│   ├── anchors.py              # Counterfactual anchor detection (406 lines)
│   ├── backtest.py             # Batch historical simulation (130 lines)
│   │
│   │  ─── LAYER 5: DOMAIN CONFIGURATION ───
│   ├── pack.py                 # Domain packs (signals, mitigations) (1,073 lines)
│   ├── rules.py                # Deterministic rule evaluation (1,148 lines)
│   │
│   │  ─── LAYER 6: REPORT GENERATION ───
│   ├── justification.py        # Shadow node audit trails (788 lines)
│   ├── report.py               # Frozen reports + judgments (901 lines)
│   └── template.py             # Declarative rendering (1,046 lines)
│
├── tests/                       # 40 test files, 1432 tests
│   ├── test_core.py            # Cell ID, Genesis, integrity
│   ├── test_chain.py           # Chain validation
│   ├── test_scholar.py         # Query resolver
│   ├── test_engine.py          # RFA processing
│   ├── test_policyhead.py      # Policy management
│   ├── test_simulation.py      # Oracle simulation
│   ├── test_shadow_cells.py    # Shadow infrastructure
│   ├── test_anchors.py         # Anchor detection
│   ├── test_backtest.py        # Batch operations
│   ├── test_pack.py            # Domain packs
│   ├── test_rules.py           # Rule evaluation
│   ├── test_justification.py   # Audit trails
│   ├── test_report.py          # Report generation
│   ├── test_template.py        # Template rendering
│   ├── test_golden_report.py   # E2E determinism proof
│   ├── test_adversarial_*.py   # 5 attack vector suites (155 tests)
│   └── ...                     # 40 files total
│
├── demo.py                      # Basic demonstration
└── demo_corporate.py            # Corporate namespace example
```

---

## Module Reference

### Layer 1: Storage Primitives

| Module | Lines | Purpose |
|--------|-------|---------|
| `cell.py` | 722 | **9 CellTypes** (GENESIS, FACT, LOGIC_ANCHOR, EVIDENCE, PROOF, BRIDGE, POLICY_HEAD, SIGNAL, MITIGATION) + structured payloads, hashing, validation |
| `chain.py` | 660 | Append-only ledger with **Commit Gate** validation, integrity verification |
| `genesis.py` | 873 | Bootstrap cell creation, **22-point verification checklist** |
| `namespace.py` | 471 | Namespace isolation, **dual-signature bridges**, access rules |
| `canon.py` | 557 | RFC 8785 canonical JSON for deterministic hashing |
| `wal.py` | 797 | Write-ahead log for persistence |
| `segmented_wal.py` | 838 | Unbounded storage via segment rotation |
| `signing.py` | 236 | Ed25519 `sign_bytes()` and `verify_signature()` |

### Layer 2: Query & Validation

| Module | Lines | Purpose |
|--------|-------|---------|
| `scholar.py` | 1,180 | **Bitemporal query resolver** with conflict resolution, policy-aware queries |
| `engine.py` | 1,141 | **RFA processing** (`process_rfa()`, `simulate_rfa()`, `run_backtest()`) |
| `validators.py` | 262 | Input validation (subject, predicate, object, namespace) |
| `exceptions.py` | 296 | **6 error codes**: DG_SCHEMA_INVALID, DG_AUTH_FAILED, DG_TEMPORAL_VIOLATION, DG_CONFLICT, DG_INTEGRITY_VIOLATION, DG_INTERNAL_ERROR |

### Layer 3: Governance

| Module | Lines | Purpose |
|--------|-------|---------|
| `policyhead.py` | 893 | **PolicyHead cells** for active policy tracking per namespace |
| `promotion.py` | 215 | **Promotion workflow**: submit → collect signatures → finalize |
| `witnessset.py` | 109 | Threshold witness rules (e.g., 2-of-3 approval) |
| `registry.py` | 248 | WitnessSet registry for namespace configuration |

### Layer 4: Simulation (Oracle)

| Module | Lines | Purpose |
|--------|-------|---------|
| `simulation.py` | 707 | **SimulationContext**, **SimulationResult**, **DeltaReport**, audit functions |
| `shadow.py` | 540 | Shadow cell creation via `dataclasses.replace()`, **OverlayContext** |
| `anchors.py` | 406 | **Counterfactual anchor detection** (greedy ablation algorithm) |
| `backtest.py` | 130 | **BatchBacktestResult**, bounded batch simulation |

### Layer 5: Domain Configuration

| Module | Lines | Purpose |
|--------|-------|---------|
| `pack.py` | 1,073 | **Domain packs** with signal definitions, severity mappings, outcome labels |
| `rules.py` | 1,148 | **Deterministic rule evaluation**: score computation, verdict derivation |

### Layer 6: Report Generation

| Module | Lines | Purpose |
|--------|-------|---------|
| `justification.py` | 788 | **Shadow nodes** for audit trails, review gating, coverage analysis |
| `report.py` | 901 | **Frozen reports** with manifest hashing, artifact verification |
| `template.py` | 1,046 | **Declarative templates** with 8 layouts, `render_report()` → deterministic bytes |

---

## Key Concepts

### CellTypes (9 types)

```python
class CellType(str, Enum):
    GENESIS       # Bootstrap cell (one per chain)
    FACT          # Immutable facts with confidence
    LOGIC_ANCHOR  # Business rules
    EVIDENCE      # Supporting documentation
    PROOF         # Verification records
    BRIDGE        # Cross-namespace authorization
    POLICY_HEAD   # Active policy snapshot
    SIGNAL        # Risk indicators (v2.0)
    MITIGATION    # Risk mitigators (v2.0)
```

### Bitemporal Semantics

Every cell has two timestamps:
- **valid_time**: When the fact became true in reality
- **system_time**: When the fact was recorded in the system

Scholar queries support both:
```python
result = scholar.query_facts(
    subject="customer_123",
    at_valid_time=datetime(2026, 1, 15),    # Reality snapshot
    as_of_system_time=datetime(2026, 1, 20)  # Knowledge snapshot
)
```

### Zero Contamination (Oracle Layer)

Simulations never mutate the real chain:
```python
result = engine.simulate_rfa(
    rfa=request,
    simulation_spec={"overlay_facts": [shadow_fact]},
    at_valid_time=datetime(2026, 1, 15)
)
# result.base_result: Real chain outcome
# result.shadow_result: Hypothetical outcome
# result.delta_report: Comparison
# Chain unchanged (cryptographically proven)
```

### Report-Grade Determinism

Same inputs → identical output bytes:
```python
report_bytes = render_report(template, manifest, cells)
# SHA-256(report_bytes) is reproducible on any machine
```

---

## Test Organization

### By Category

| Category | Files | Tests | Purpose |
|----------|-------|-------|---------|
| Core | 6 | ~200 | Cell, chain, genesis, namespace |
| Scholar | 3 | ~150 | Query resolution, policy-aware |
| Engine | 3 | ~100 | RFA processing, promotion |
| Simulation | 6 | ~180 | Shadow, overlay, anchors, backtest |
| Governance | 4 | ~120 | PolicyHead, witness, registry |
| Report-Grade | 6 | ~247 | Pack, rules, justification, report, template |
| Adversarial | 5 | 155 | Attack vectors (injection, tampering, etc.) |
| Golden | 1 | 10 | E2E determinism proof |

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific layer
pytest tests/test_simulation*.py -v

# With coverage
pytest tests/ --cov=src/decisiongraph --cov-report=term-missing
```

---

## Import Graph

```
__init__.py (public API facade)
│
├── LAYER 1: Storage
│   ├── cell.py (no internal deps)
│   ├── canon.py (no internal deps)
│   ├── signing.py (no internal deps)
│   ├── genesis.py → cell
│   ├── chain.py → cell, genesis
│   ├── namespace.py → cell
│   ├── wal.py → cell, chain
│   └── segmented_wal.py → wal
│
├── LAYER 2: Query
│   ├── exceptions.py (no internal deps)
│   ├── validators.py → exceptions
│   ├── scholar.py → cell, chain, namespace
│   └── engine.py → scholar, validators, exceptions
│
├── LAYER 3: Governance
│   ├── witnessset.py (no internal deps)
│   ├── registry.py → witnessset
│   ├── policyhead.py → cell, chain
│   └── promotion.py → policyhead, witnessset
│
├── LAYER 4: Simulation
│   ├── shadow.py → cell
│   ├── simulation.py → shadow, scholar
│   ├── anchors.py → simulation
│   └── backtest.py → simulation, anchors
│
├── LAYER 5: Domain
│   ├── pack.py (no internal deps)
│   └── rules.py → pack
│
└── LAYER 6: Reports
    ├── justification.py → cell, rules
    ├── report.py → justification, pack
    └── template.py → report, pack
```

**No circular dependencies.** Each layer only imports from layers below it.

---

## Where to Add New Code

### New Cell Type
1. Add enum value to `CellType` in `cell.py`
2. Add structured payload dataclass if needed
3. Add validation in `chain.py` Commit Gate
4. Add tests in `tests/test_core.py`
5. Export from `__init__.py`

### New Simulation Feature
1. Add to `simulation.py` or create new module in Layer 4
2. Wire into `engine.py` if it needs RFA integration
3. Add tests in `tests/test_simulation*.py`

### New Report Section
1. Add `SectionLayout` enum value in `template.py`
2. Add rendering logic in `_render_section()`
3. Add tests in `tests/test_template.py`

### New Domain Pack
1. Create pack definition using `pack.py` dataclasses
2. Define signal codes, severity mappings, outcome labels
3. Add tests in `tests/test_pack.py`

---

## Configuration

### pyproject.toml
- Python: `>=3.10`
- Dependencies: `cryptography` (for Ed25519)
- Dev dependencies: `pytest`, `black`, `mypy`
- Line length: 100 characters

### No External Services
- All storage is in-memory or file-based (WAL)
- No database connections
- No network calls
- Fully deterministic

---

## Key Files Quick Reference

| What | Where |
|------|-------|
| Create a chain | `chain.py:create_chain()` |
| Process an RFA | `engine.py:Engine.process_rfa()` |
| Run simulation | `engine.py:Engine.simulate_rfa()` |
| Query facts | `scholar.py:Scholar.query_facts()` |
| Create policy | `policyhead.py:create_policy_head()` |
| Render report | `template.py:render_report()` |
| Build justification | `justification.py:build_justification()` |
| Detect anchors | `anchors.py:detect_counterfactual_anchors()` |
| Run backtest | `engine.py:Engine.run_backtest()` |

---

*Structure analysis: 2026-01-29 | v2.0 | 1432 tests | 16,824 lines*
