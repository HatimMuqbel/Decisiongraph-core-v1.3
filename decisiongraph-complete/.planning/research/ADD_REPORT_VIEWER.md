# ADD REPORT VIEWER — DecisionGraph Core v1.3
# The Report Viewer is the primary product page. Add it to the existing frontend.

## ⚠️ CRITICAL: THE REPORT IS THE PRODUCT

The entire DecisionGraph pipeline exists to produce ONE thing: the **Progressive Disclosure Compliance Report**. Everything else (seeds, scoring, policy shifts) feeds into it. The report is what compliance officers, reviewers, and regulators actually see and use. **Build the Report Viewer FIRST, then the supporting pages.**

## Context
We have a DecisionGraph Core v1.3 backend with a completed 7-task banking pipeline fix. The backend produces AML/KYC compliance decision reports with three tiers of progressive disclosure. The frontend needs to render these reports beautifully and provide supporting tools.

## What the Backend Produces
1. **banking_field_registry.py** — 28 fields, single source of truth for all field names/labels/types
2. **aml_seed_generator.py** — 20 AML scenarios, 1,500 seeds, all 28 fields populated
3. **policy_shift_shadows.py** — 4 policy shifts with shadow projections
4. **main.py** — Decision pipeline: ingests case → scores → navigates policy tree → produces report
5. **render_md.py** — Renders the compliance report with registry-driven evidence tables
6. **JudgmentPayload** — Domain-aware human judgment submission with signal_codes
7. **New API endpoints** — `/api/policy-shifts` router

## Tech Stack
- React 18 + TypeScript
- Vite for build
- Tailwind CSS for styling
- React Query for data fetching
- React Router for navigation
- Recharts for charts/visualizations

---

## Project Structure
```
services/dashboard/
├── src/
│   ├── api/
│   │   └── client.ts                    # API client — connect to FastAPI backend
│   ├── components/
│   │   ├── report/                      # ← REPORT COMPONENTS (most important)
│   │   │   ├── ReportShell.tsx          # Shared report frame (header, hash, pack version)
│   │   │   ├── RiskHeatmap.tsx          # Probability × severity grid
│   │   │   ├── LinchpinStatement.tsx    # Single-sentence decision summary
│   │   │   ├── TypologyMap.tsx          # Pattern match percentages
│   │   │   ├── NegativePathSearch.tsx   # Policies checked but NOT triggered
│   │   │   ├── EvidenceGapTracker.tsx   # Required vs optional vs present
│   │   │   ├── BranchPathViz.tsx        # ltree navigation breadcrumb visualization
│   │   │   ├── VerbatimCitations.tsx    # Side-by-side policy text | case data
│   │   │   ├── CausalChain.tsx         # Signal → node → decision chain
│   │   │   ├── AuditMetadata.tsx        # Microsecond timestamps per inference step
│   │   │   ├── EvidenceTable.tsx        # Registry-driven field labels and values
│   │   │   └── TierBadge.tsx           # Shows which tier and why (auto-escalation reason)
│   │   ├── Badge.tsx                    # Outcome/confidence/risk badges
│   │   ├── ErrorMessage.tsx             # Error display
│   │   ├── Layout.tsx                   # Sidebar navigation layout
│   │   ├── Loading.tsx                  # Loading spinners
│   │   ├── Modal.tsx                    # Reusable modal
│   │   ├── StatsCard.tsx                # Dashboard stat cards
│   │   ├── PolicyShiftCard.tsx          # Policy shift shadow display
│   │   └── index.ts
│   ├── hooks/
│   │   └── useApi.ts                    # React Query hooks for all endpoints
│   ├── pages/
│   │   ├── ReportViewer.tsx             # ← PRIMARY PAGE — the compliance report
│   │   ├── Dashboard.tsx                # Stats, charts, recent decisions
│   │   ├── JudgmentQueue.tsx            # Pending judgments with review modal
│   │   ├── SeedExplorer.tsx             # Browse scenarios & seeds, run through pipeline
│   │   ├── PolicyShifts.tsx             # Policy shift shadow analysis
│   │   ├── AuditSearch.tsx              # Search with filters, CSV export
│   │   ├── FieldRegistry.tsx            # View all 28 banking fields
│   │   └── index.ts
│   ├── types/
│   │   └── index.ts                     # TypeScript interfaces matching backend schemas
│   ├── App.tsx                          # Router + QueryClient setup
│   ├── main.tsx
│   └── index.css                        # Tailwind CSS
├── package.json
├── vite.config.ts
├── Dockerfile
└── tsconfig.json
```

---

## PAGE 1: REPORT VIEWER (/reports/:id) — BUILD THIS FIRST

This is the product. This is what compliance officers see. This is what gets printed for regulators. This is what gets attached to emails. Everything else supports this page.

### Three-Tier Progressive Disclosure

The report has 3 tiers. The user sees the appropriate tier based on their role AND the system auto-escalates based on risk signals. All tiers share a common header (ReportShell).

#### Report Header (all tiers)
- Case ID and decision ID
- Case integrity hash (SHA256) — proves the report hasn't been tampered with
- Pack version — which rule version was used
- Tier badge — shows current tier AND why (role-based or auto-escalated)
- Timestamp of decision
- One-click tier navigation tabs (if user has permission to see higher tiers)

---

#### TIER 1: ANALYST VIEW (target: <30 seconds to read and act)
**This is the fast path. An analyst should be able to approve/escalate in under 30 seconds.**

Components:
1. **LinchpinStatement** — Single sentence summarizing why the decision was made. Example: "Transaction flagged due to high-risk jurisdiction (Iran) combined with structuring pattern across 3 accounts."

2. **RiskHeatmap** — A probability × severity grid (2×2 or 3×3). Shows at a glance where this case sits. Color-coded: green (low/low), yellow (medium), red (high/high).

3. **Quick Decision Outcome** — Large, clear badge showing the recommended action: APPROVE (green), ESCALATE (amber), DECLINE (red) with confidence percentage.

4. **Key Signals Summary** — The top 3-5 signals that drove the decision, with icons and one-line explanations. Not the full list — just the ones that mattered most.

5. **One-Click Actions** — Three prominent buttons:
   - ✅ **Approve** — Accept the recommendation
   - ℹ️ **Request Info** — Need more data before deciding
   - 🔍 **Expand to Reviewer View** — Drill into Tier 2

6. **Evidence Snapshot** — Compact table showing the 3-5 most critical evidence items from the 28 registry fields. Uses registry labels, not field names. Shows: field label, value, source, confidence.

**Design:** Clean, minimal, lots of whitespace. The analyst's eye should flow: linchpin → heatmap → outcome → action buttons. No scrolling required on a standard monitor.

---

#### TIER 2: REVIEWER VIEW (target: <2 minutes to review)
**Includes everything in Tier 1 PLUS deeper analysis.**

Additional Components:

7. **TypologyMap** — Shows match percentages against ALL known AML/KYC patterns (e.g., "Structuring: 87%, Trade-Based ML: 12%, Funnel Account: 3%"). Visual bar chart or radar chart. Helps reviewer understand what the system thinks is happening.

8. **NegativePathSearch** — THIS IS CRITICAL FOR COMPLIANCE. Shows policies that were checked but NOT triggered. Proves the system didn't just find what it was looking for — it also verified what doesn't apply. Example: "Checked: Sanctions screening (CLEAR), PEP match (CLEAR), Adverse media (CLEAR)." This is what auditors want to see.

9. **EvidenceGapTracker** — Three-column layout:
   - ✅ **Present** — Evidence we have (field, value, source)
   - ⚠️ **Required but missing** — Evidence we should have but don't (with impact on confidence)
   - ℹ️ **Optional** — Evidence that would strengthen the assessment if available

10. **Full Evidence Table** — All 28 registry fields displayed with their banking_field_registry labels. Grouped by category. Shows: label, value, source, confidence, whether it was used in the decision.

11. **BranchPathViz** — Visual breadcrumb showing the ltree navigation path through the policy tree. Shows which branch was selected at Route stage, which nodes at Narrow stage, which citations at Cite stage. Clickable to expand each stage's reasoning.

12. **Signal Details** — Full list of all signals detected, categorized as DISQUALIFIER vs MANDATORY_ESCALATION, with the signal_codes from JudgmentPayload.

**Design:** Expandable sections. Starts with Tier 1 content at top, then progressive sections below. Each section has a collapse/expand toggle. Reviewer can drill into what they need without being overwhelmed.

---

#### TIER 3: REGULATOR VIEW (target: comprehensive, can be async/printed)
**This is the full audit package. What gets printed for FINTRAC examiners.**

Additional Components:

13. **VerbatimCitations** — Side-by-side display:
    - LEFT: Exact policy text from the regulation (with section numbers, paragraph references)
    - RIGHT: The case data that triggered that policy
    - Connected by visual lines showing the mapping
    - Every citation includes: canonical_id, content_hash, source document reference

14. **CausalChain** — Complete signal → node → decision chain visualization. Shows:
    - Input signals (from case data)
    - Which policy nodes they activated
    - How the navigation stages narrowed to the final citations
    - The evidence gates that were passed/triggered
    - The final decision with full reasoning

15. **AuditMetadata** — Full technical audit trail:
    - Microsecond timestamps for every inference step
    - LLM call IDs and latencies (if Opik integration active)
    - Pack version and hash at time of decision
    - Navigation stage timings (Route, Narrow, Cite)
    - Evidence gate events (EVIDENCE_GATE_TRIGGERED if applicable)
    - Top-K filter events with input/output counts

16. **PDF Export Button** — Generates a PDF that matches the screen layout exactly. This is what gets attached to regulatory submissions and emails. Must include: all three tiers, the integrity hash, pack version, and full audit metadata.

**Design:** Dense but organized. Legal/regulatory professionals expect comprehensive documentation. Use clear section headings, page breaks between tiers when printed, and consistent formatting. The PDF export must look professional.

---

### Auto-Escalation Rules (Built into ReportViewer)
The system automatically selects the minimum tier based on risk signals:

**Auto-escalate to TIER 2 if ANY of:**
- MANDATORY_ESCALATION signal present
- Transaction amount > $25,000
- Prior suspicious activity reports >= 2
- Attorney or legal representative involved

**Auto-escalate to TIER 3 if ANY of:**
- DISQUALIFIER signal present
- SIU referral or investigation
- Active litigation
- Regulatory examination
- Decision is DECLINE
- Transaction amount > $100,000

**Display logic:** Always show the auto-escalated tier as minimum. User can manually escalate UP but never DOWN below the auto-escalated level. Show a badge explaining why: "Auto-escalated to Reviewer View: amount exceeds $25,000 threshold."

---

## PAGE 2: Dashboard (/)
- Stats cards: total decisions, pending judgments, approval rate, avg confidence
- Pie chart: decisions by AML scenario type (20 types from seed generator)
- Bar chart: decisions by outcome (APPROVE, DECLINE, ESCALATE)
- Recent decisions list — **click any row opens Report Viewer**
- Risk distribution heatmap across all recent cases
- Quick link to Judgment Queue with pending count badge

## PAGE 3: Judgment Queue (/judgments)
- Table of pending judgments (from JudgmentPayload with signal_codes)
- **Click opens Report Viewer for that case** (Tier 1 by default, auto-escalated if needed)
- After reviewing the report, analyst submits judgment from within the Report Viewer action buttons
- Domain-aware validation feedback on submission
- Bulk actions for low-risk approvals (if all signals are clear)

## PAGE 4: Seed Explorer (/seeds)
- Browse all 20 AML scenario types with descriptions
- Filter/search across 1,500 seeds
- Click any seed to see all 28 fields populated (using registry labels)
- **"Run Through Pipeline" button** — processes the seed and **opens Report Viewer with the result**
- Scenario distribution chart
- Useful for testing, demos, and training

## PAGE 5: Policy Shifts (/policy-shifts)
- Display 4 current policy shifts from policy_shift_shadows.py
- For each shift: before/after rule comparison
- Shadow projection: how many existing decisions would change outcome
- Impact analysis visualization
- "What-if" toggle to simulate shift activation
- **Links to affected cases in Report Viewer**

## PAGE 6: Audit Search (/audit)
- Search by: customer ID, scenario type, outcome, date range, signal codes
- Results table with sortable columns
- CSV export button
- **Click any row → opens Report Viewer for that decision**

## PAGE 7: Field Registry (/fields)
- Display all 28 fields from banking_field_registry
- Show: field name, label, type, description, category
- Search/filter fields
- Reference documentation for the team

---

## API Client (client.ts)
```typescript
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// REPORT (primary — this is the product)
// GET  /api/reports/:id              — full report data for Report Viewer (all 3 tiers)
// GET  /api/reports/:id/pdf          — PDF export of complete report

// DECISIONS
// GET  /api/decisions                — list decisions (for dashboard, audit)
// GET  /api/decisions/:id            — single decision detail
// POST /api/decisions/run            — run a seed through pipeline, returns report

// JUDGMENTS
// GET  /api/judgments                — pending judgments
// POST /api/judgments/:id            — submit judgment (approve/reject/escalate + reason)

// SEEDS
// GET  /api/seeds                    — list seeds/scenarios
// GET  /api/seeds/:id                — single seed detail with all 28 fields

// POLICY SHIFTS
// GET  /api/policy-shifts            — get policy shifts and shadow projections

// FIELDS
// GET  /api/fields                   — get full field registry (28 fields)

// AUDIT
// GET  /api/audit                    — search audit log with filters

// STATS
// GET  /api/stats                    — dashboard statistics
```

**IMPORTANT:** Check the actual backend endpoints in main.py and routers/ before building. The above are expected — adapt to what actually exists. If an endpoint doesn't exist yet, create the API client function but mark it as TODO and use mock data so the UI is still functional.

---

## Design Guidelines
- Dark theme: slate-900 background, slate-800 cards, slate-700 borders
- **Report Viewer exception:** Use lighter background (white or slate-50) for Tier 3 / print mode — regulators expect paper-like readability
- Accent colors: emerald-500 for APPROVE/clear, red-500 for DECLINE/disqualifier, amber-500 for ESCALATE/warning
- Typography: Clear hierarchy — the report must be scannable in under 30 seconds at Tier 1
- **The Report Viewer is the hero page** — spend the most design effort here
- All evidence tables use banking_field_registry labels, NEVER hardcoded field names
- Responsive but desktop-first (compliance officers use large monitors)
- Print stylesheet for Tier 3 — must look professional when printed or exported to PDF
- Every page that shows a decision should link to its Report Viewer

## Navigation Flow
```
Dashboard ──→ click decision ──→ Report Viewer
Judgment Queue ──→ click case ──→ Report Viewer ──→ submit judgment
Seed Explorer ──→ run seed ──→ Report Viewer
Audit Search ──→ click result ──→ Report Viewer
Policy Shifts ──→ click affected case ──→ Report Viewer
```
**The Report Viewer is the hub. Everything leads to it.**

## Build Priority
1. **ReportViewer + all report/ components** (this IS the product)
2. **JudgmentQueue** (daily workflow, leads to ReportViewer)
3. **Dashboard** (overview, entry point to ReportViewer)
4. **SeedExplorer** (testing/demos, leads to ReportViewer)
5. **AuditSearch** (compliance requirement, leads to ReportViewer)
6. **PolicyShifts** (analysis tool)
7. **FieldRegistry** (reference)

## Commands
```bash
cd services/dashboard
npm install
npm run dev          # dev server on :5173
npm run build        # production build
```
