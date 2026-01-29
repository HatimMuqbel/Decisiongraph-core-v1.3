# Feature Landscape: Promotion Gate + Policy Snapshots

**Domain:** Policy promotion/approval systems with cryptographic governance
**Researched:** 2026-01-27
**Confidence:** HIGH for table stakes, MEDIUM for differentiators, HIGH for anti-features

## Executive Summary

Policy promotion systems in 2026 span from traditional approval workflows to cryptographic governance systems. Research reveals three feature clusters:

1. **Core Approval Mechanics** - Threshold signatures, witness sets, approval tracking
2. **Temporal/Audit Features** - Version control, audit trails, snapshot management, bitemporal queries
3. **Integrity Features** - Hash validation, tamper-evident logs, rollback protection

DecisionGraph v1.5's innovation is **combining cryptographic integrity (blockchain-style) with bitemporal policy queries** - a feature combination rare in the ecosystem. Most systems offer either traditional approval workflows OR blockchain governance, but not both with time-travel queries.

---

## Table Stakes

Features users expect in any policy promotion/approval system. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Multi-party approval (threshold)** | Standard in 2026 governance; 2-of-3, 3-of-5 patterns are universal | Medium | Already have Ed25519 signatures; need witness set management |
| **Submission → Review → Approval workflow** | Three-phase pattern is industry standard | Low | Maps to `submit_promotion()` → `collect_witness_signature()` → `finalize_promotion()` |
| **Audit trail of approval decisions** | Regulatory requirement (GLP, SOX, etc.) | Low | Append-only chain provides this natively |
| **Who approved what and when** | Baseline accountability expectation | Low | Witness signatures + system_time gives this |
| **Clear approval status tracking** | Users need to know "pending", "approved", "rejected" | Low | PromotionRequest cell with status field |
| **Policy versioning** | Must track which policy version is active | Medium | policy_hash + promoted_rule_ids provides this |
| **Current policy query** | "What's the active policy now?" | Low | HEAD of PolicyHead chain |
| **Tamper-evident audit log** | Trust requirement for governance | Medium | Hash-linking + Logic Seal provides this |
| **Threshold configuration** | Different namespaces need different quorums | Medium | WitnessSet per namespace with threshold field |
| **Signature validation** | Verify approvers are who they claim | Low | Already have Ed25519 verify_signature() |

**MVP Recommendation:** All 10 features above are table stakes for v1.5. Users expect these in any modern policy governance system.

---

## Differentiators

Features that set DecisionGraph apart. Not expected, but high value when present.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Bitemporal policy queries** | "What policy was active on date X?" - rare in approval systems | High | Combines PolicyHead chain with Scholar's bitemporal resolution |
| **Cryptographic policy snapshots** | Tamper-proof policy state at any point in time | Medium | policy_hash = hash(sorted(promoted_rule_ids)) |
| **Witness set as promotable rule** | Solves bootstrap problem elegantly | Medium | WitnessSet is itself a policy that requires promotion |
| **Policy chain visualization** | "Show me all policy changes over time" | Medium | PolicyHead chain → to_audit_text() / to_dot() |
| **Proof bundle inclusion** | PolicyHead can be included in Scholar results | High | Enables "show me the policy that produced this decision" |
| **Atomic all-or-nothing promotion** | Either all rules promote or none | Low | Prevents partial policy states |
| **Policy rollback prevention** | Can't revert to old policy without new promotion | Low | Append-only chain prevents rollback attacks |
| **Namespace-scoped policies** | Each namespace has independent policy chain | Medium | corp.hr and corp.sales have separate PolicyHead chains |
| **Policy dependency graph** | "Which rules depend on which witness sets?" | High | Requires dependency tracking in promoted_rule_ids |
| **Witness signature time bounds** | Signatures expire after time window | Medium | Prevents stale approvals from being used |

**Value Ranking:**
1. **Bitemporal policy queries** (HIGH) - Unique capability, enables compliance/audit use cases
2. **Cryptographic policy snapshots** (HIGH) - Tamper-proof governance trail
3. **Witness set as promotable rule** (MEDIUM) - Elegant bootstrap solution
4. **Policy chain visualization** (MEDIUM) - Debugging and audit value
5. Rest are NICE-TO-HAVE for v1.5+

---

## Anti-Features

Features to explicitly NOT build in v1.5. Common mistakes in this domain.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Email-based approvals** | Buried in inbox, missed deadlines, no audit trail | In-system witness signature collection only |
| **Spreadsheet tracking** | Versioning chaos, information inconsistency | PolicyHead cells as single source of truth |
| **Vague approval deadlines** | Stalls workflows indefinitely | Consider time-bound signatures (future enhancement) |
| **Too many required approvers** | Analysis paralysis; every additional approver adds delay | Recommend 2-of-3 or 3-of-5, not 5-of-7 |
| **Informal approval channels** | "Slack approval" or "hallway approval" destroys audit trail | Signatures must be in-chain only |
| **Manual policy activation** | Human must "flip switch" after approval | `finalize_promotion()` creates PolicyHead atomically |
| **Policy promotion without witness threshold** | Single point of failure | Always require threshold witnesses (even in dev mode, use 1-of-1) |
| **Mutable policy history** | Allows rewriting what policy was active when | Append-only PolicyHead chain, no updates |
| **Cross-namespace policy promotion** | One promotion affecting multiple namespaces = complexity nightmare | One PolicyHead per namespace |
| **Automated approval rules without human-in-loop** | Security vulnerability; no human intervention to catch mistakes | All promotions require witness signatures, no auto-promote |
| **Missing escalation for stuck promotions** | Approvals fall into limbo | Consider timeout/escalation (future enhancement) |
| **Policy gaps (no active policy)** | Uncertainty about which rules apply | Bootstrap mode: Genesis establishes initial policy |
| **File upload vulnerabilities in workflow** | CVE-2026-21858 style attacks on webhook endpoints | No file uploads in promotion workflow; signatures only |

**Critical Anti-Patterns:**
1. **Email/Slack approvals** - Destroys audit trail
2. **Single approver** - Eliminates promotion gate value
3. **Mutable history** - Breaks "what policy was active when?" queries

---

## Feature Dependencies

```
Genesis Cell
    ↓
WitnessSet Definition (bootstrap via Genesis)
    ↓
Promotion Workflow (submit → collect → finalize)
    ↓
PolicyHead Cell Creation
    ↓
    ├─→ Bitemporal Policy Queries (requires PolicyHead chain)
    ├─→ Policy Snapshot Hashing (requires promoted_rule_ids)
    └─→ Scholar Integration (requires PolicyHead chain + policy_mode flag)

Parallel/Optional:
- Policy Chain Visualization (uses PolicyHead chain)
- Proof Bundle Inclusion (requires Scholar changes)
- Witness Signature Time Bounds (enhances witness collection)
```

**Critical Path for v1.5 MVP:**
1. WitnessSet cell type
2. PromotionRequest cell type (optional, could be ephemeral)
3. PolicyHead cell type
4. Promotion workflow methods (`submit_promotion`, `collect_witness_signature`, `finalize_promotion`)
5. Scholar integration with `policy_mode` flag

**Post-MVP Dependencies:**
- Bitemporal queries → Scholar must traverse PolicyHead chain by system_time
- Visualization → PolicyHead.to_audit_text() and to_dot() methods
- Time-bound signatures → Signature expiration validation

---

## Feature Complexity Analysis

### Low Complexity (1-2 days)
- Approval status tracking
- Current policy query (HEAD of PolicyHead chain)
- Atomic promotion (transaction-style finalize)
- Policy rollback prevention (append-only enforces this)
- Namespace-scoped policies (one PolicyHead chain per namespace)

### Medium Complexity (3-5 days)
- Multi-party threshold approval
- Witness set configuration per namespace
- Policy versioning with policy_hash
- Cryptographic policy snapshots
- WitnessSet as promotable rule (bootstrap)
- Policy chain visualization

### High Complexity (1-2 weeks)
- Bitemporal policy queries (Scholar integration)
- Policy dependency graph
- Proof bundle inclusion (Scholar changes)
- Witness signature time bounds (expiration logic)

---

## MVP Feature Set for v1.5

**MUST HAVE (Core Table Stakes):**
1. WitnessSet cell type with threshold configuration
2. PolicyHead cell type with policy_hash
3. Three-phase promotion workflow
4. Witness signature collection and validation
5. Approval status tracking
6. Audit trail (built-in via chain)
7. Current policy query
8. Atomic promotion (all-or-nothing)
9. Namespace-scoped PolicyHead chains
10. Cryptographic policy snapshots (policy_hash)

**SHOULD HAVE (Key Differentiators):**
11. Bitemporal policy queries ("what policy was active when?")
12. WitnessSet as promotable rule (bootstrap solution)
13. Policy chain visualization (to_audit_text, to_dot)

**DEFER to v1.6+ (Nice-to-Have):**
- Policy dependency graph
- Witness signature time bounds
- Proof bundle inclusion in Scholar results
- Promotion timeout/escalation
- Policy diff visualization

---

## Ecosystem Insights

### What's Standard in 2026

**Traditional Approval Workflow Systems:**
- Customizable approval paths with drag-and-drop
- Real-time notifications
- Audit-ready reporting
- Integration with CRM/ERP systems
- AI-enhanced policy gap detection

**Cryptographic Governance (Blockchain/DAO):**
- Multi-signature wallets (Gnosis Safe standard)
- Threshold schemes (t-of-n signing)
- Tamper-evident audit logs with hash-chaining
- Quorum-based voting
- Append-only transaction history

**Regulatory/Compliance Systems:**
- Bitemporal data for "what did we know when?"
- Version control for policies
- Comprehensive audit trails
- Signature validation with timestamps
- Immutable historical records

**DecisionGraph's Position:**
Combines **cryptographic governance** (blockchain-style integrity) with **bitemporal queries** (compliance system capability) - a rare combination. Most systems pick one paradigm; DecisionGraph fuses them.

### Innovation Opportunity

The feature **"query active policy as-of system_time X"** is:
- Standard in bitemporal databases (XTDB, MariaDB temporal tables)
- Rare in approval workflow systems
- Non-existent in most DAO governance tools

This is DecisionGraph's **killer feature** for regulated industries (banking AML, healthcare compliance, financial auditing).

---

## Research Confidence Assessment

| Feature Category | Confidence | Source Quality |
|-----------------|------------|----------------|
| Table Stakes | HIGH | Multiple 2026 approval workflow vendor docs + NIST threshold crypto standards |
| Multi-sig/Threshold | HIGH | NIST multi-party threshold cryptography project (Jan 2026), BitGo institutional wallets |
| Bitemporal Queries | HIGH | XTDB docs, MariaDB temporal tables, Snowflake ASOF JOIN (Jan 2026 article) |
| Audit Trail Requirements | HIGH | CMS security standards, GLP compliance docs, Microsoft Purview |
| Anti-Patterns | HIGH | Documented enterprise approval workflow mistakes (SnohAI, Cflow) |
| DAO Governance | MEDIUM | WebSearch of 2026 DAO governance articles; less formal than NIST standards |
| Time-Bound Signatures | MEDIUM | Not widely documented; inferred from signature workflow best practices |

**Overall Assessment:** HIGH confidence for core features and anti-patterns. Ecosystem understanding is comprehensive.

---

## Open Questions for Requirements Phase

1. **Bootstrap Mode:** How should dev mode handle witness sets? Allow 1-of-1 for testing?
2. **Promotion Request Lifecycle:** Should PromotionRequest be a cell type or ephemeral object?
3. **Failed Promotions:** What happens to promotion requests that don't reach threshold? Store as failed cell?
4. **Witness Set Changes:** How to promote a new WitnessSet when old witnesses are unavailable?
5. **Policy Diff:** Should we show what changed between policy versions?
6. **Rollback Semantics:** Can you "promote" an older policy version as new HEAD? (Answer: YES, it's a new promotion)
7. **Concurrent Promotions:** Can two promotions run simultaneously for same namespace? (Likely: NO, chain serialization prevents)
8. **Witness Rotation:** How often should witness sets change? Guidance for users?

---

## Sources

### High Confidence (Official/Authoritative)
- [NIST Multi-Party Threshold Cryptography Project](https://csrc.nist.gov/projects/threshold-cryptography) - January 2026 workshop
- [XTDB Bitemporality Concepts](https://v1-docs.xtdb.com/concepts/bitemporality/) - Bitemporal database design
- [Database Trends: Bitemporality in Data Governance](https://www.dbta.com/Editorial/Trends-and-Applications/The-Role-of-Bitemporality-in-Data-Governance-and-Compliance-117412.aspx)
- [Microsoft Purview Audit Solutions](https://learn.microsoft.com/en-us/purview/audit-solutions-overview) - Enterprise audit logging
- [Snowflake Bitemporal Modeling](https://medium.com/@joshirish/modeling-bi-temporality-and-using-temporal-joins-asof-join-in-snowflake-db-d2b871f4934a) - January 2026
- [Approval Process Guide - Kissflow](https://kissflow.com/workflow/approval-process/)

### Medium Confidence (Industry Practice)
- [Common Approval Workflow Mistakes - SnohAI](https://snohai.com/common-approval-workflow-mistakes-enterprises-make/)
- [Approval Workflow Design Patterns - Cflow](https://www.cflowapps.com/approval-workflow-design-patterns/)
- [DAO Governance Models - Metana](https://metana.io/blog/dao-governance-models-what-you-need-to-know/)
- [Multi-Signature Wallets in Web3 - Chiliz](https://www.chiliz.com/multi-signature-wallet-web3-security-governance/)
- [BitGo Multi-Sig Wallets for Institutions](https://www.bitgo.com/resources/blog/multi-sig-wallets-for-institutions/)
- [Policy Rollback - ServiceNow](https://www.cflowapps.com/operations-workflow-management/application-rollback-procedure-workflow/)
- [DevOps Audit Logging Best Practices - MOSS](https://moss.sh/devops-monitoring/devops-audit-logging-best-practices/)
- [Threshold Signatures - Qredo](https://www.qredo.com/blog/what-are-threshold-signatures)

### Security Vulnerabilities (2026)
- [Critical n8n Workflow Vulnerability CVE-2026-21858](https://thehackernews.com/2026/01/critical-n8n-vulnerability-cvss-100.html) - CVSS 10.0
- [Orca Security: n8n RCE Analysis](https://orca.security/resources/blog/cve-2026-21858-n8n-rce-vulnerability/)

### Policy Management
- [Top 5 Policy Management Software 2026 - V-Comply](https://www.v-comply.com/blog/top-policy-management-softwares/)
- [Policy as Code Tools 2026 - Spacelift](https://spacelift.io/blog/policy-as-code-tools)
- [Policy Versioning Importance - Collaboris](https://www.collaboris.com/importance-of-policy-versioning/)

---

**Research completed:** 2026-01-27
**Valid until:** 2026-03-27 (stable domain, 60-day validity)
**Next step:** Requirements definition using this feature landscape
