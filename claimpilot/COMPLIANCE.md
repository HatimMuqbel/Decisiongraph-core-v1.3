# ClaimPilot Compliance & Regulatory Alignment

## System Overview

ClaimPilot is a **deterministic, rule-based insurance claim evaluation system**.
It evaluates claims strictly against predefined policy rules and policy wording in force at the time of loss.

The system **does not use**:
- Machine learning
- Large language models
- Statistical inference
- Heuristics or probabilistic scoring

All decisions are **fully reproducible** given identical inputs.

---

## Regulatory Mapping

### A. OSFI — Guideline E-23: Model Risk Management

**Reference:** [OSFI Guideline E-23 – Model Risk Management (2027)](https://www.osfi-bsif.gc.ca/en/guidance/guidance-library/guideline-e-23-model-risk-management-2027)

OSFI's Guideline E-23 sets expectations for enterprise model risk management, including governance, inventory, controls, and monitoring.

| E-23 Requirement | ClaimPilot Control |
|------------------|-------------------|
| **Model inventory & identification** | `policy_pack_id`, `policy_pack_version`, `policy_pack_hash`, `engine_version` |
| **Controls & change management** | Strict YAML schemas, deterministic hashing, version control, `/validate/policies` endpoint |
| **Monitoring & outcomes** | Deterministic behavior, traceable decision deltas, override logging |
| **Auditability** | Provenance hashes, clause-level citations, `/verify` endpoint for post-hoc verification |

**Additional context:** See [Blake's analysis of E-23](https://www.blakes.com/insights/osfi-releases-final-guideline-e-23-for-model-risk-management-and-ai-use-by-frfis/)

---

### B. FSRA Ontario — Fair Consumer Outcomes & Underwriting Controls

**Reference:** [FSRA Automobile Insurance Rating and Underwriting Guidance](https://www.fsrao.ca/industry/auto-insurance/regulatory-framework/guidance-auto-insurance/automobile-insurance-rating-and-underwriting-guidance)

FSRA's guidance emphasizes that insurers must be able to **support decision-making** and consider outcomes holistically.

| FSRA Expectation | ClaimPilot Control |
|------------------|-------------------|
| **Decision supportability** | Reasoning chain with explicit exclusion evaluation and policy citations |
| **Transparency** | "Needs evidence" state prevents silent denials; uncertainty is surfaced |
| **Governance** | Override pathway with logged rationale and optional supervisor approvals |
| **Documentation & oversight** | `/validate/policies`, consistent request IDs, deterministic replay capability |

**Additional context:** See [FSRA 2025 Auto Supervision Interim Report](https://www.fsrao.ca/media/28756/download) for expectations around controls in automated processes.

---

### C. NAIC — AI Systems Model Bulletin (US)

**Reference:** [NAIC Model Bulletin on AI Systems](https://content.naic.org/sites/default/files/cmte-h-big-data-artificial-intelligence-wg-ai-model-bulletin.pdf.pdf)

The NAIC Model Bulletin focuses on governance programs designed to mitigate risk of adverse consumer outcomes and expects documentation and examination readiness.

| NAIC Expectation | ClaimPilot Control |
|------------------|-------------------|
| **Governance & documentation** | Explicit policy rules, versioning, validation |
| **Explainability** | Reasoning chains and citations by design |
| **Examination readiness** | Reproduce results; verify applied rules via `/verify` |
| **Adverse outcome mitigation** | Structured "request evidence" instead of opaque denial |

**Note:** Although ClaimPilot is **Zero LLM**, controls align with the *spirit* of the NAIC bulletin.

**Additional context:** See [NAIC AI Model Bulletin Compilation (April 2024)](https://content.naic.org/sites/default/files/inline-files/AI%20Model%20Bulletin%20-%20April%202024.pdf)

---

### D. NAIC — Insurance Data Security Model Law (Model 668)

**Reference:** [NAIC Model Law 668](https://content.naic.org/sites/default/files/model-law-668.pdf)

Model 668 establishes standards for information security programs and includes governance expectations.

| Model 668 Requirement | ClaimPilot Control |
|----------------------|-------------------|
| **Audit-ready recordkeeping** | Request IDs, event logs, verification records |
| **Security posture support** | Clear audit trails; integrate with InfoSec program (access control, logging, retention) |

---

## Compliance Statement

> ClaimPilot is a deterministic, rule-based claim evaluation engine that produces reproducible decisions with full reasoning chains, policy citations, and cryptographic provenance hashes. Policy packs are strictly validated and versioned. Decisions are verifiable post hoc via a provenance verification endpoint, supporting audit, dispute resolution, and governance controls aligned with model risk management and fair consumer outcome expectations.

---

## Decision Finalization Workflow

### Case States

| State | Description |
|-------|-------------|
| `draft` | Claim created, not evaluated |
| `evaluated` | Recommendation produced |
| `evidence_requested` | Indeterminate exclusions exist (needs evidence) |
| `evidence_received` | New documents/facts received |
| `re_evaluated` | Engine re-run with updated facts |
| `finalized` | Disposition confirmed (pay/deny/partial) |
| `overridden` | Human override applied (must record rationale) |
| `appealed` | Dispute workflow triggered (optional) |
| `closed` | Case completed |

### Events and Required Actions

#### Event: `evaluate_claim`
- **Input:** ClaimContext + PolicyPack selector
- **Output:** RecommendationRecord
- If any exclusion is `requires_evidence` → transition to `evidence_requested`

#### Event: `request_evidence`
- System generates an **EvidenceRequestList** from the exclusion evidence matrix
- Sends to adjuster/customer portal

#### Event: `submit_evidence`
- Evidence is uploaded/entered (docs, fields, attestations)
- System extracts structured facts
- Transition to `evidence_received`

#### Event: `re_evaluate`
- Re-run engine with updated facts
- Compare to previous recommendation
- Log decision delta if disposition changed
- Transition to `re_evaluated`

#### Event: `finalize_decision`
- Allowed only when:
  - No `requires_evidence` exclusions remain, **OR**
  - Adjuster explicitly accepts residual uncertainty with documented reason
- Transition to `finalized`

#### Event: `override_decision`
- Adjuster changes disposition or triggered exclusions
- Must provide:
  - Override reason code
  - Narrative justification
  - Supervisor approval flag if needed
- Transition to `overridden`
- Override **appends** to original recommendation; never deletes

### Audit Trail Requirements (Append-Only)

For every event, log:
- `request_id` (evaluation)
- `case_id`
- `actor` (system/adjuster)
- `timestamp`
- `inputs_hash` (hash of normalized claim facts)
- `output_hash` (hash of recommendation record)
- `policy_pack_id/version/hash`
- `authority_hashes[]`
- `reasoning_chain[]`
- Diffs between recommendation versions (optional)

---

## Policy Evaluation Methodology

For each claim submission:

1. The applicable **policy pack** is selected using a unique policy identifier and version
2. The policy pack is validated against a strict schema
3. All coverage conditions and exclusions are evaluated using explicit rule logic
4. Each exclusion is classified:
   - **Not Applicable**
   - **Triggered**
   - **Indeterminate (Additional Evidence Required)**
5. A recommended disposition is produced based solely on the evaluated results
6. A complete **reasoning chain** is generated, documenting each evaluation step
7. All cited policy clauses are recorded with **cryptographic hashes**

No exclusion is applied unless its triggering conditions are explicitly satisfied.

---

## Handling of Uncertainty

Where available claim facts are insufficient to conclusively determine the applicability of a policy exclusion, the exclusion is marked as:

**"Additional Evidence Required"**

In such cases:
- Coverage is **not denied by assumption**
- The system explicitly documents what information is missing
- The decision remains procedurally conservative and transparent

---

## Provenance and Auditability

Each recommendation includes:
- Policy Pack ID
- Policy Pack Version
- SHA-256 hash of the canonical policy pack content
- SHA-256 hashes of each cited policy clause excerpt
- Engine version
- Evaluation timestamp
- Unique request identifier

This allows any recommendation to be independently verified at a later date to confirm:
- Which policy rules were applied
- That no post-hoc modification occurred

---

## Determinism Guarantee

ClaimPilot guarantees that:
- Identical inputs will always produce identical outputs
- Policy pack ordering does not affect evaluation
- Decisions can be re-verified months or years later
