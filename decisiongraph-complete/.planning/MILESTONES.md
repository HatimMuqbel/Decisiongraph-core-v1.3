# Milestones — DecisionGraph

## Completed Milestones

### v1.4: RFA Layer + Security Hardening

**Completed:** 2026-01-27

**Core Value:** External developers can integrate with DecisionGraph through a single, validated, signed entry point — and every failure returns a deterministic, actionable error code.

**Phases:**
1. Error Foundation — DecisionGraphError hierarchy with 6 DG_* codes
2. Input Validation — Subject, predicate, object, namespace validation
3. Signing Utilities — Ed25519 sign_bytes() and verify_signature()
4. RFA Processing Layer — engine.process_rfa() with ProofPacket signing
5. Adversarial Test Suite — 155 attack vector tests (SEC-01 through SEC-05)
6. Lineage Visualizer — to_audit_text() and to_dot() methods

**Requirements:** 20/20 complete
**Tests:** 517 passing
**Archive:** `.planning/archive/v1.4/`

---

### v1.3: Scholar + Bridges (Pre-GSD)

**Completed:** Pre-milestone tracking

**Core Value:** Bitemporal decision engine with deterministic conflict resolution and namespace isolation.

**Features:**
- Cell/Chain/Genesis — Append-only cryptographic ledger
- Namespace/Bridge — Department isolation with dual-signature bridges
- Scholar — Bitemporal query resolver with conflict resolution
- Commit Gate — Cell validation before append

**Tests:** 69 passing (baseline)

---

## Active Milestone

### v1.5: Promotion Gate + Policy Snapshots

**Started:** 2026-01-27

**Core Value:** Rules are hypotheses until promoted. Promoted rules become the active policy, tracked as PolicyHead cells — enabling bitemporal "what policy was active when?" queries and multi-witness approval workflows.

**Status:** Initializing (research → requirements → roadmap)

---

*Last updated: 2026-01-27*
