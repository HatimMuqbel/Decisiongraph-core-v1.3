# Features Research: Oracle Layer (Layer 5)

**Project:** DecisionGraph v1.6 — Oracle/Counterfactual Simulation
**Domain:** Counterfactual simulation, what-if analysis, policy testing
**Researched:** 2026-01-28
**Confidence:** HIGH (authoritative sources + existing DecisionGraph foundation)

---

## Executive Summary

Oracle layer counterfactual simulation systems enable policy testing and what-if analysis by running modified policy scenarios against historical or hypothetical data without mutating the base system. Research shows this domain requires **shadow testing with baseline comparison**, **bitemporal replay with deterministic outcomes**, **minimal change explanations**, and **batch backtesting capabilities**. DecisionGraph's existing bitemporal foundation (valid_time, system_time) and immutable audit trail position it uniquely for deterministic, cryptographically verifiable counterfactual analysis — a differentiator in policy simulation where most systems lack reproducibility guarantees.

**Key insight from research:** The standard for counterfactual systems is shifting from "what changed?" to "can you prove what changed?" — requiring simulation proof bundles, not just delta reports.

---

## Table Stakes

Features users expect from any counterfactual simulation system. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes | Sources |
|---------|--------------|------------|-------|---------|
| **Shadow testing** | Industry standard — run new policy alongside base without mutation | Medium | Non-mutating overlay pattern; shadow cells vs base cells | [Shadow Testing - Microsoft Eng Playbook](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/shadow-testing/), [Shadow Testing Superpowers](https://www.signadot.com/blog/shadow-testing-superpowers-four-ways-to-bulletproof-apis) |
| **Baseline comparison** | Core value prop — "show me what changed" | Medium | Delta report with verdict/score/set diffs | [Statsig Counterfactual Analysis](https://www.statsig.com/perspectives/counterfactual-analysis-what-if), [Azure ML Counterfactual](https://learn.microsoft.com/en-us/azure/machine-learning/concept-counterfactual-analysis?view=azureml-api-2) |
| **Minimal change identification** | Users need actionable insight — "what's the smallest change?" | High | Counterfactual anchors showing minimal input perturbation | [Interpretable ML Book](https://christophm.github.io/interpretable-ml-book/counterfactual.html), [Achievable Minimally-Contrastive CFEs](https://www.mdpi.com/2504-4990/5/3/48) |
| **Batch backtesting** | Real-world use — test policy against 1000s of historical cases | Medium | Asynchronous batch job against historical event log | [Lithic Authorization Rules Engine](https://www.lithic.com/blog/authorization-rules-engine), [CFA Backtesting 2026](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/backtesting-and-simulation) |
| **Deterministic replay** | Debugging requires reproducibility — same input = same output | High | Critical for audit/compliance; most systems fail here | [Trustworthy AI Deterministic Replay](https://www.sakurasky.com/blog/missing-primitives-for-trustworthy-ai-part-8/), [Taming Chaos: DST](https://developersummit.com/session/taming-chaos-deterministic-simulation-testing-for-distributed-systems) |
| **Audit trail** | Compliance requirement — every simulation logged | Low | Append-only log feeding data warehouse | [Lithic Authorization Rules](https://www.lithic.com/blog/authorization-rules-engine), [Immutable Audit Logs](https://hoop.dev/blog/immutable-audit-logs-the-baseline-for-security-compliance-and-operational-integrity/) |

**Complexity Legend:**
- **Low:** Uses existing infrastructure (e.g., audit trail leverages existing PolicyHead chain pattern)
- **Medium:** New pattern but well-understood (e.g., shadow testing documented extensively)
- **High:** Novel challenge requiring research (e.g., minimal change in bitemporal context)

---

## Differentiators

Features that set DecisionGraph Oracle apart. Not expected, but highly valued.

| Feature | Value Proposition | Complexity | How DecisionGraph Uniquely Delivers | Sources |
|---------|-------------------|------------|-------------------------------------|---------|
| **Bitemporal counterfactual** | "What if policy X was active from date Y?" | High | Leverage existing bitemporal semantics (valid_time, system_time) for time-travel simulation | [BiTemporal RDF](https://www.mdpi.com/2227-7390/13/13/2109), [Counterfactual Time Series](https://arxiv.org/html/2512.14559) |
| **Simulation proof bundle** | Cryptographically verifiable simulation results | Medium | Extends existing proof bundles (Merkle root, signatures) to include overlay context | [AAAI-26 Reproducibility](https://aaai.org/conference/aaai/aaai-26/reproducibility-checklist/), [FormaliSE 2026 Artifacts](https://2026.formalise.org/) |
| **Deterministic counterfactual anchors** | Minimal changes are reproducible across runs | High | Deterministic conflict resolution (Scholar) + sorted promoted_rule_ids = stable anchors | [Achievable Minimally-Contrastive CFEs](https://www.mdpi.com/2504-4990/5/3/48), [Interpretable Model-Aware CFEs](https://arxiv.org/html/2510.27397v1) |
| **Namespace-isolated simulation** | Test policy changes without department interference | Low | Extends existing namespace isolation to shadow cells | DecisionGraph v1.4 existing namespace foundation |
| **Policy chain time-travel** | Replay decisions using policy that was active at any historical point | Medium | PolicyHead chain (v1.5) enables traversal to find active policy at as_of_system_time | [Time Travel BiTemporal RDF](https://www.mdpi.com/2227-7390/13/13/2109) |
| **Threshold witness simulation** | "What if we required 3-of-5 instead of 2-of-3?" | Medium | Simulate alternate WitnessSet configs without mutating production registry | DecisionGraph v1.5 WitnessSet foundation |
| **Overlay precedence rules** | Deterministic resolution when shadow conflicts with base | High | Extends Scholar's deterministic conflict resolution to overlay context | [AI Context Protocols 2026](https://sdtimes.com/https-assets-sdtimes-com-supercast-ai-in-test/) |

**Why these are differentiators:**
- Most policy engines lack bitemporal semantics (can't replay "as-of" a date)
- Most simulation systems produce non-reproducible results (no determinism guarantee)
- Most authorization engines lack cryptographic verification (proof bundles are rare)
- Most what-if tools don't handle namespace isolation (single-tenant mindset)

**Research confidence: HIGH** — These capabilities leverage existing DecisionGraph infrastructure (bitemporal queries, PolicyHead chain, namespace isolation, Ed25519 signatures) in ways competitors cannot easily replicate without similar foundations.

---

## Anti-Features

Features to **deliberately NOT build**. Common mistakes in this domain.

| Anti-Feature | Why Avoid | What to Do Instead | Evidence |
|--------------|-----------|-------------------|----------|
| **Auto-apply simulation results** | Destroys trust boundary; simulations can be adversarial | Manual promotion workflow — simulation informs, humans decide | [Shadow AI Data Security 2026](https://www.kiteworks.com/cybersecurity-risk-management/ai-data-security-crisis-shadow-ai-governance-strategies-2026/) warns of 223 AI incidents/month; auto-apply would amplify risk |
| **Unbounded simulation depth** | Enables DoS — simulate 10M cases crashes system | Hard limits: max 1000 simulations per batch, timeout per simulation | [Vallignus Bounded Execution](https://github.com/jacobgadek/vallignus) enforces "processes forcibly terminated upon violating time, output, or request policies" |
| **Mutable simulation state** | Non-reproducible results undermine audit value | Shadow cells are immutable; new simulation = new shadow cell set | [Deterministic Replay Survey](https://dl.acm.org/doi/10.1145/2790077) shows mutation destroys reproducibility |
| **Implicit overlay precedence** | Non-deterministic conflict resolution confuses users | Explicit precedence rules (e.g., "shadow wins" or "base wins") documented in OverlayContext | [Trustworthy AI Deterministic Replay](https://www.sakurasky.com/blog/missing-primitives-for-trustworthy-ai-part-8/) requires explicit semantics |
| **Cross-namespace simulation** | Security nightmare — simulate policy changes across department boundaries | Simulation respects namespace isolation; can only simulate within requester's namespace | DecisionGraph v1.4 namespace isolation prevents cross-contamination |
| **Live simulation (no sandbox)** | Testing in production is reckless | Isolated shadow cells; simulation never touches base PolicyHead or production facts | [Tiered Sandboxes for AI](https://www.startuphub.ai/ai-news/ai-research/2026/tiered-sandboxes-are-essential-for-testing-ai-agents/) — 2026 standard requires isolation |
| **Simulation without proof bundle** | Unverifiable claims are worthless for audit | Every simulation produces proof bundle with overlay_context, base_policy_head_id, shadow_policy_head_id, delta_report | [AAAI-26 Reproducibility](https://aaai.org/conference/aaai/aaai-26/reproducibility-checklist/) requires artifacts for verification |
| **Non-deterministic minimal changes** | Different runs produce different "minimal changes" | Sort rules deterministically; use stable hash-based anchors | [Robustness Analysis of CFEs](https://arxiv.org/html/2512.14559) shows "generated counterfactuals are highly sensitive to stochastic noise" |

**Critical anti-feature to emphasize: AUTO-APPLY**
Research shows this is the #1 pitfall. Shadow testing exists to observe, not to mutate. DecisionGraph must maintain hard boundary: `simulate_rfa()` produces DeltaReport; promotion workflow (v1.5) is the only path to PolicyHead mutation.

---

## Feature Dependencies

How Oracle features connect to existing DecisionGraph capabilities.

### Dependency Graph

```
Existing Foundation (v1.0-v1.5)
│
├─ Cell/Chain/Genesis (v1.0)
│  └─ Append-only immutable chain
│     └─ ENABLES: Shadow cells as immutable snapshots
│
├─ Namespace/Bridge (v1.1)
│  └─ Department isolation
│     └─ ENABLES: Namespace-isolated simulation
│
├─ Scholar (v1.2)
│  ├─ Bitemporal queries (valid_time, system_time)
│  │  └─ ENABLES: Time-travel counterfactual ("what if policy X at date Y")
│  ├─ Deterministic conflict resolution
│  │  └─ ENABLES: Deterministic overlay precedence
│  └─ QueryResult with proof bundles
│     └─ ENABLES: Simulation proof bundles
│
├─ PolicyHead (v1.5)
│  ├─ PolicyHead chain (prev_policy_head)
│  │  └─ ENABLES: Find active policy at any as_of_system_time
│  ├─ policy_hash (deterministic)
│  │  └─ ENABLES: Verify simulation used correct base policy
│  └─ promoted_rule_ids (sorted list)
│     └─ ENABLES: Counterfactual anchors (minimal rule change)
│
└─ Promotion Workflow (v1.5)
   ├─ WitnessSet with threshold
   │  └─ ENABLES: Simulate alternate threshold requirements
   └─ Manual promotion with signatures
      └─ PREVENTS: Auto-apply anti-feature

New Oracle Features (v1.6)
│
├─ Shadow Cells
│  ├─ ShadowPolicyHead (modified promoted_rule_ids)
│  ├─ ShadowRuleCell (what-if rule variants)
│  ├─ ShadowFactCell (hypothetical facts)
│  └─ ShadowBridgeCell (alternate bridge authorizations)
│
├─ OverlayContext
│  ├─ precedence_rule: Literal["shadow_wins", "base_wins", "merge"]
│  ├─ base_policy_head_id: str
│  └─ shadow_policy_head_id: str
│
├─ simulate_rfa()
│  ├─ Run RFA against base + shadow overlay
│  ├─ Return DeltaReport (verdict_changed, score_delta, set_diffs)
│  └─ Return SimulationProofBundle (overlay_context + delta + anchors)
│
├─ Counterfactual Anchors
│  ├─ minimal_rule_changes: list of (rule_id, change_type)
│  ├─ minimal_fact_changes: list of (subject, predicate, object, change_type)
│  └─ anchor_hash: SHA-256 of sorted changes (deterministic)
│
└─ run_backtest()
   ├─ Batch simulation over historical events
   ├─ Filter by namespace + time range
   └─ Return BacktestReport (aggregated deltas, statistical summary)
```

### Critical Dependencies Table

| Oracle Feature | Depends On | Why Dependency Exists | Risk if Missing |
|----------------|------------|----------------------|-----------------|
| Shadow cells | Cell/Chain immutability (v1.0) | Shadow cells must be append-only to prevent tampering | Mutable shadows = non-reproducible simulations |
| OverlayContext precedence | Scholar deterministic conflict resolution (v1.2) | Overlay rules must resolve deterministically | Non-deterministic overlay = different results per run |
| Bitemporal counterfactual | Scholar bitemporal queries (v1.2) | "What if policy X at date Y" requires as_of_system_time | No bitemporal = can only simulate "now" |
| Policy chain traversal | PolicyHead chain (v1.5) | Find active policy at any historical system_time | No chain = can't replay historical policy context |
| Counterfactual anchors | PolicyHead.promoted_rule_ids sorted (v1.5) | Minimal changes require stable baseline | Unsorted list = non-deterministic anchor hash |
| Simulation proof bundle | QueryResult.to_proof_bundle() (v1.2) | Extend existing proof pattern to include overlay | New proof format = inconsistent with existing audits |
| Namespace-isolated simulation | Namespace isolation (v1.1) | Simulation must respect department boundaries | No isolation = cross-namespace contamination |
| Prevent auto-apply | Promotion workflow (v1.5) | Hard boundary: simulate observes, promote mutates | No boundary = simulation can corrupt production |

### Feature Enablement Chain

**Level 1: Foundation (Already Built)**
- Immutable chain → Shadow cells possible
- Namespace isolation → Simulation scoping
- Bitemporal queries → Time-travel counterfactual

**Level 2: Policy Infrastructure (Already Built)**
- PolicyHead chain → Find historical policy
- Deterministic Scholar → Deterministic overlay
- Proof bundles → Simulation verification

**Level 3: Oracle Features (To Build)**
- Shadow cells + OverlayContext → simulate_rfa()
- Delta comparison → DeltaReport
- Minimal change detection → Counterfactual anchors
- Batch processing → run_backtest()

**Level 4: Quality Guarantees (To Build)**
- Deterministic anchors → Reproducible minimal changes
- Simulation proof bundle → Cryptographic verification
- Bounded execution → DoS prevention
- Audit trail → Compliance

---

## MVP Recommendation

For Oracle layer MVP, prioritize:

### Phase 1: Core Simulation (Must Have)
1. **Shadow cells** — ShadowPolicyHead with modified promoted_rule_ids
2. **OverlayContext** — Precedence rules for base vs shadow
3. **simulate_rfa()** — Run single RFA against overlay
4. **DeltaReport** — Verdict changed? Score delta? Set diffs?

**Why first:** Core value proposition — "test policy changes before promotion"

### Phase 2: Verification (Must Have)
5. **SimulationProofBundle** — Extend existing proof bundles
6. **Deterministic anchors** — Minimal change identification
7. **Audit trail** — Log simulations to chain

**Why second:** Without verification, simulation results are untrustworthy

### Phase 3: Batch Backtesting (Should Have)
8. **run_backtest()** — Batch simulation over historical events
9. **BacktestReport** — Aggregated statistics

**Why third:** Enables real-world workflows (test 1000s of cases) but not MVP-critical

### Defer to Post-MVP

**Bitemporal counterfactual** ("What if policy X was active at date Y")
- **Reason:** Complex — requires PolicyHead chain traversal + bitemporal shadow overlay
- **When:** After core simulation proven stable

**Threshold witness simulation** ("What if we required 3-of-5?")
- **Reason:** Edge case — most users won't simulate WitnessSet changes
- **When:** User-requested feature based on adoption data

**ShadowBridgeCell** (alternate bridge authorizations)
- **Reason:** Niche — most simulations test rules, not bridges
- **When:** Cross-namespace simulation becomes common

**ShadowFactCell** (hypothetical facts)
- **Reason:** Scope creep — Oracle should simulate policy, not invent facts
- **When:** Clear use case emerges (e.g., "what if employee count was 500?")

---

## Implementation Sequence by Dependency

### Wave 1: Shadow Infrastructure
- ShadowPolicyHead cell type
- OverlayContext dataclass
- Shadow cell creation helpers

**Blocks:** Wave 2 (can't simulate without shadow cells)

### Wave 2: Single Simulation
- simulate_rfa() function
- DeltaReport generation
- Precedence rule enforcement

**Blocks:** Wave 3 (can't verify without working simulation)

### Wave 3: Verification
- SimulationProofBundle
- Counterfactual anchors
- Audit trail integration

**Blocks:** Wave 4 (batch needs single simulation + verification)

### Wave 4: Batch Operations
- run_backtest() function
- BacktestReport aggregation
- Performance optimization (parallel simulation)

**Blocks:** None (optional feature)

---

## Open Questions for Requirements Phase

Research identified these gaps requiring phase-specific investigation:

1. **Overlay precedence semantics:**
   - Should DecisionGraph support "merge" mode or only "shadow_wins"/"base_wins"?
   - What's the expected behavior when shadow promotes rule A but base promotes rule B?

2. **Counterfactual anchor granularity:**
   - Minimal changes at rule level (rule_id added/removed)?
   - Or at fact level (subject-predicate-object triples)?
   - Or both?

3. **Batch backtest filtering:**
   - How to select "relevant" historical events for backtesting?
   - Time range + namespace is obvious, but what about rule_id filtering?

4. **Simulation proof bundle format:**
   - Extend existing QueryResult.to_proof_bundle()?
   - Or new SimulationResult.to_proof_bundle()?

5. **Bounded execution limits:**
   - What's a reasonable max for batch simulations (1000? 10000?)?
   - What's a reasonable timeout per simulation (1s? 10s?)?

These should be resolved during requirements definition, not research.

---

## Sources

### Table Stakes Features
- [Shadow Testing - Microsoft Eng Playbook](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/shadow-testing/)
- [Shadow Testing Superpowers](https://www.signadot.com/blog/shadow-testing-superpowers-four-ways-to-bulletproof-apis)
- [Statsig Counterfactual Analysis](https://www.statsig.com/perspectives/counterfactual-analysis-what-if)
- [Azure ML Counterfactual](https://learn.microsoft.com/en-us/azure/machine-learning/concept-counterfactual-analysis?view=azureml-api-2)
- [Interpretable ML Book](https://christophm.github.io/interpretable-ml-book/counterfactual.html)
- [Achievable Minimally-Contrastive CFEs](https://www.mdpi.com/2504-4990/5/3/48)
- [Lithic Authorization Rules Engine](https://www.lithic.com/blog/authorization-rules-engine)
- [CFA Backtesting 2026](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/backtesting-and-simulation)
- [Trustworthy AI Deterministic Replay](https://www.sakurasky.com/blog/missing-primitives-for-trustworthy-ai-part-8/)
- [Taming Chaos: DST](https://developersummit.com/session/taming-chaos-deterministic-simulation-testing-for-distributed-systems)
- [Immutable Audit Logs](https://hoop.dev/blog/immutable-audit-logs-the-baseline-for-security-compliance-and-operational-integrity/)

### Differentiators
- [BiTemporal RDF](https://www.mdpi.com/2227-7390/13/13/2109)
- [Counterfactual Time Series](https://arxiv.org/html/2512.14559)
- [AAAI-26 Reproducibility](https://aaai.org/conference/aaai/aaai-26/reproducibility-checklist/)
- [FormaliSE 2026 Artifacts](https://2026.formalise.org/)
- [Interpretable Model-Aware CFEs](https://arxiv.org/html/2510.27397v1)
- [AI Context Protocols 2026](https://sdtimes.com/https-assets-sdtimes-com-supercast-ai-in-test/)

### Anti-Features
- [Shadow AI Data Security 2026](https://www.kiteworks.com/cybersecurity-risk-management/ai-data-security-crisis-shadow-ai-governance-strategies-2026/)
- [Vallignus Bounded Execution](https://github.com/jacobgadek/vallignus)
- [Deterministic Replay Survey](https://dl.acm.org/doi/10.1145/2790077)
- [Tiered Sandboxes for AI](https://www.startuphub.ai/ai-news/ai-research/2026/tiered-sandboxes-are-essential-for-testing-ai-agents/)

### Additional Context
- [PolicySimEval Benchmark](https://arxiv.org/html/2502.07853v1)
- [Time Travel BiTemporal](https://www.mdpi.com/2227-7390/13/13/2109)
- [Audit Trail for AI](https://chatfin.ai/blog/audit-trails-for-ai-how-to-prove-an-agents-work-to-the-auditors/)
- [SQL Server Ledger Immutable Audit](https://dzone.com/articles/sql-server-ledger-tamper-evident-audit-trails)
- [GitClear Diff Delta](https://www.gitclear.com/diff_delta_factors)
- [SIGSIM PADS 2026 Artifact Evaluation](https://sigsim.acm.org/conf/pads/2026/blog/artifact-evaluation/)

---

*Research complete. Ready for requirements definition.*
