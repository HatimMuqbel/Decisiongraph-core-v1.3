# How to Add a New Section to the Compliance Report

There are **two rendering paths** for the same report data. Both must be updated or the section will appear in one place but not the other.

## The Two Rendering Paths

| Path | What it powers | Technology |
|------|---------------|------------|
| **Jinja HTML template** | `generate_demo_reports.py` output, raw `/report/{id}` endpoint, PDF export | Server-side Jinja2 |
| **React dashboard** | decisiongraph.pro live reports | Client-side React (Vite/TypeScript) |

Both paths consume the **same JSON** from the report pipeline. The JSON is the single source of truth.

## Step-by-Step Checklist

### 1. Build the data in the report pipeline

All report data flows through a 4-stage pipeline:

```
Engine decision
    |
    v
NORMALIZE  -->  service/routers/report/normalize.py
    |           Extracts raw engine fields into a flat dict
    v
DERIVE     -->  service/routers/report/derive.py
    |           Computes derived/calculated fields (this is where most new sections go)
    v
VIEW MODEL -->  service/routers/report/view_model.py
    |           Flattens everything into a single dict for rendering
    v
RENDER     -->  Jinja template OR JSON endpoint (consumed by React)
```

**To add new data:**

1. If it comes directly from the engine, extract it in `normalize.py`
2. If it's computed/derived, build it in `derive.py` (add a helper function like `_build_my_section()`)
3. **Expose it in `view_model.py`** -- add a line like:
   ```python
   "my_new_field": derived.get("my_new_field", {}),
   ```
   This is the key file. If it's not in view_model.py, neither rendering path can see it.

### 2. Add to the Jinja HTML template

**File:** `service/templates/decision_report.html`

Template structure (approximate section order):
```
Administrative Details (header, metadata)
Investigation Outcome Summary (linchpin statement)
Decision Path                    <-- line ~404
Case Classification
Regulatory Determination
Suspicion Classification
Decision Drivers
Precedent Intelligence (v3)
Negative Path Search
Evidence Gap Tracker
Full Evidence Table
Causal Chain
Audit Metadata
```

Add your section with a conditional guard:
```html
{% if my_new_field %}
<h2>My Section Title</h2>
<div class="card break">
  <!-- your content here -->
</div>
{% endif %}
```

**Test:** Run `python generate_demo_reports.py` and open an HTML file to verify.

### 3. Add to the React dashboard

This is the part that gets missed. The React dashboard does NOT use the Jinja template. It builds the report from JSON using its own components.

#### 3a. Add the TypeScript type

**File:** `services/dashboard/src/types/index.ts`

Find the `ReportViewModel` interface and add your field:
```typescript
// inside ReportViewModel
my_new_field?: {
  // match the JSON shape from view_model.py
};
```

#### 3b. Create the React component

**File:** `services/dashboard/src/components/report/MyNewSection.tsx`

```tsx
import type { ReportViewModel } from '../../types';

export default function MyNewSection({ report }: { report: ReportViewModel }) {
  if (!report.my_new_field) return null;

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800 p-5">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-white">
        My Section Title
      </h3>
      {/* render your data */}
    </div>
  );
}
```

#### 3c. Export from barrel file

**File:** `services/dashboard/src/components/report/index.ts`

```typescript
export { default as MyNewSection } from './MyNewSection';
```

#### 3d. Place in the page

**File:** `services/dashboard/src/pages/ReportViewer.tsx`

The page has three tier sections:

```
Tier1Content (always visible)     -- Analyst View
  LinchpinStatement
  RiskHeatmap + DecisionOutcome
  DecisionConflict
  KeySignals
  EvidenceSnapshot
  DecisionPathNarrative           <-- added here as example
  ActionButtons
  GovernanceCards
  PrecedentIntelligence

Tier2Content (visible at tier >= 2) -- Reviewer View
  CollapsibleSection: TypologyMap
  CollapsibleSection: NegativePathSearch
  CollapsibleSection: EvidenceGapTracker
  CollapsibleSection: ReportEvidenceTable
  CollapsibleSection: BranchPathViz
  CollapsibleSection: SignalDetails
  EscalationSummary
  EddRecommendations
  CollapsibleSection: PrecedentTechnicalDetail

Tier3Content (visible at tier >= 3) -- Regulator View
  VerbatimCitations
  CausalChain
  AuditMetadata
  FullRationale
```

Import and place your component in the appropriate tier:
```tsx
import { MyNewSection } from '../components/report';

// then inside the tier function:
<MyNewSection report={report} />
```

### 4. Build and deploy the dashboard

```bash
cd services/dashboard
npm run build
```

Then copy the built assets to the backend static directory:
```bash
# Remove old assets
rm decisiongraph-complete/service/static/dashboard/assets/index-*.js
rm decisiongraph-complete/service/static/dashboard/assets/index-*.css

# Copy new assets
cp services/dashboard/dist/assets/* decisiongraph-complete/service/static/dashboard/assets/

# Update index.html with new asset filenames
# Compare services/dashboard/dist/index.html with
# decisiongraph-complete/service/static/dashboard/index.html
# and update the <script> and <link> tags to match the new hashed filenames
```

### 5. Regenerate static reports

```bash
cd decisiongraph-complete
python generate_demo_reports.py
```

This regenerates all 40 demo case HTML files in `validation_reports/v3/`.

### 6. Commit everything

Files that typically change:
```
# Pipeline (data)
service/routers/report/derive.py
service/routers/report/view_model.py

# Jinja template
service/templates/decision_report.html

# React dashboard
services/dashboard/src/types/index.ts
services/dashboard/src/components/report/MyNewSection.tsx
services/dashboard/src/components/report/index.ts
services/dashboard/src/pages/ReportViewer.tsx

# Built assets
decisiongraph-complete/service/static/dashboard/assets/index-*.js
decisiongraph-complete/service/static/dashboard/assets/index-*.css
decisiongraph-complete/service/static/dashboard/index.html

# Regenerated reports
decisiongraph-complete/validation_reports/v3/*.html
```

## Key Files Quick Reference

| Purpose | File |
|---------|------|
| Raw engine data extraction | `service/routers/report/normalize.py` |
| Computed/derived fields | `service/routers/report/derive.py` |
| JSON shape exposed to renderers | `service/routers/report/view_model.py` |
| Jinja HTML template | `service/templates/decision_report.html` |
| React types | `services/dashboard/src/types/index.ts` |
| React components | `services/dashboard/src/components/report/` |
| React page layout + tier placement | `services/dashboard/src/pages/ReportViewer.tsx` |
| Component barrel export | `services/dashboard/src/components/report/index.ts` |
| Static assets served by backend | `decisiongraph-complete/service/static/dashboard/` |
| Report generator script | `decisiongraph-complete/generate_demo_reports.py` |

---

# Decision Path — Visual Component Spec

This section is the design spec for the Decision Path component. Follow the checklist above to implement it across both rendering paths.

## What This Component Does

Shows **how the system evaluated the case and reached its disposition**, step by step. Replaces the collapsed "DECISION PATH NAVIGATION" dropdown (which is a status dump) with a visual, always-visible flow of connected cards.

## Current State (Replace This)

The current implementation is a collapsed dropdown in Tier 2 that shows:

```
▶ DECISION PATH NAVIGATION

NO_ESCALATION
⤵
NO_ESCALATION
Route
Gate 1 (Escalation)    PROHIBITED
Gate 2 (STR)           PROHIBITED
```

This tells the reader what happened but not why. A compliance officer or regulator cannot follow the reasoning.

## Placement

Move the Decision Path to **immediately after the Decision Summary** — the second content section in the report. It must be **always visible, never collapsed**.

Report reading order becomes:

```
1. Decision Summary       → what happened
2. Decision Path           → how the system got there (THIS COMPONENT)
3. Decision Outcome        → the result
4. Decision Conflict       → if applicable
5. Everything else         → unchanged
```

In `ReportViewer.tsx` Tier1Content, this means:

```
LinchpinStatement          ← Decision Summary
DecisionPathNarrative      ← THIS COMPONENT (move here)
RiskHeatmap + DecisionOutcome
DecisionConflict
KeySignals
EvidenceSnapshot
ActionButtons
GovernanceCards
PrecedentIntelligence
```

Remove the `BranchPathViz` CollapsibleSection from Tier2Content — this component replaces it.

## Visual Design

The Decision Path renders as a **vertical flow of connected cards** — one card per evaluation step, connected by arrows showing the flow direction.

### Card Design

Each card represents one step in the evaluation. A card has:

| Element | Description |
|---------|-------------|
| **Step number** | Circled number (①②③④⑤) color-matched to status |
| **Title** | Step name (e.g., "Gate 1 — Typology Maturity Assessment") |
| **Summary** | One-line plain-language description of what happened |
| **Status badge** | Right-aligned pill showing outcome (BLOCKED, PASSED, NOT EVALUATED, etc.) |
| **Expandable detail** | Click to reveal full reasoning (rule that fired, what was evaluated, why) |

### Color Coding by Status

| Status | Card Background | Border/Badge Color | Meaning |
|--------|----------------|-------------------|---------|
| PASSED / CONFIRMED | Light green (`emerald-500/10`) | Green (`emerald`) | Step cleared, no issue |
| BLOCKED / PROHIBITED | Light red (`red-500/10`) | Red (`red`) | Gate blocked escalation |
| NOT EVALUATED / SKIPPED | Light grey (`slate-700/30`) | Grey (`slate-500`) | Upstream gate blocked, step never reached |
| EDD REQUIRED / PENDING | Light amber (`amber-500/10`) | Amber (`amber`) | Requires further action |
| STR REQUIRED | Light amber (`amber-500/10`) | Amber (`amber`) | STR filing recommended |

### Connectors Between Cards

- Vertical line + triangle connecting each card to the next
- Connector color reflects the flow:
  - **Red** — the step blocked
  - **Grey** — next step was skipped
  - **Blue/slate** — normal flow
- Connectors are centered between cards

### Dimming

Cards with status NOT EVALUATED or SKIPPED render at **55% opacity** to visually communicate they were not part of the active decision path.

### Final Outcome Bar

After the last card, render a dark slate horizontal bar showing the **Governed Disposition** — the final resolved outcome. This anchors the entire flow with the terminal result.

### Expand/Collapse Detail

Each card (except those without detail) is clickable. Clicking expands an indented detail section below the summary showing:
- Specific values from this case
- The rule or policy that applied
- Why the outcome was what it was

A subtle "tap for detail" hint appears on expandable cards.

## Data Structure

The component receives `decision_path_narrative` from the report JSON:

```typescript
interface DecisionPathStep {
  number: number;           // 1-5
  symbol: string;           // ①②③④⑤
  title: string;            // "Classifier Assessment", "Gate 1 — Typology Maturity Assessment"
  detail_lines: string[];   // reasoning lines shown on expand
  arrow_line: string;       // "→ Classifier recommends: STR REQUIRED"
  // Derived by the component from arrow_line content:
  // status is parsed from the arrow_line and title context
}

interface DecisionPathNarrative {
  steps: DecisionPathStep[];
  path_code: string;        // "PATH_1_HARD_STOP" | "PATH_2_SUSPICION" | "NO_ESCALATION"
}
```

### Status Mapping

The component derives the visual status from the step data:

| Step | How to determine status |
|------|------------------------|
| ① Classifier | Parse `arrow_line` for disposition: "STR REQUIRED" → amber, "EDD REQUIRED" → amber, "NO REPORT" → green |
| ② Gate 1 | Check if `arrow_line` contains "BLOCKED" → red, "PERMITTED" → green |
| ③ Gate 2 | Check if `arrow_line` contains "NOT EVALUATED" → grey/dimmed, "INSUFFICIENT" → red, otherwise parse |
| ④ Resolution | Parse `arrow_line` for governed disposition |
| ⑤ Terminal | Parse `arrow_line` for terminal disposition |

## Content Rules

These rules govern what text appears in each step. They are critical for report integrity.

1. **Every gate must explain its rule.** "BLOCKED" or "PROHIBITED" alone is never acceptable. The detail must state what the gate requires and why this case didn't meet it.

2. **Gate dependencies must be explicit.** If Gate 2 was not evaluated because Gate 1 blocked, the Gate 2 card must say so. Don't show both as independently "PROHIBITED."

3. **Typology maturity must match the Evidence Snapshot.** If Evidence says FORMING, the path says FORMING. If it says EMERGING, the path says EMERGING. FORMING is not EMERGING is not ESTABLISHED is not MATURE. Any mismatch is a report defect.

4. **The governed resolution step must explain reconciliation.** When the classifier and engine disagree (e.g., classifier wants STR but gates block), explain how the system resolved the conflict and why the fallback is appropriate.

5. **Use case-specific values.** Reference the actual signals, typology, maturity level, and counts from this case. No boilerplate.

6. **Active voice, declarative tone.** "Gate 1 blocked escalation" not "Escalation was blocked by Gate 1."

7. **Consistent with Decision Conflict section.** If a conflict block exists elsewhere in the report, gate names, outcomes, and resolution text must match exactly.

## Standard Step Templates

### Step ① — Classifier Assessment
Always present. Shows what the classifier found and what it recommends.
- Summary format: "[N] Tier [X] [suspicion/investigative] signals · [other findings]"
- Status: The classifier's recommended disposition
- Detail: List each signal, note what tier, note absence of higher-tier indicators if relevant

### Step ② — Gate 1 (name varies by case)
The first gate evaluation.
- If classifier didn't request escalation: status = PASSED, summary explains no escalation was requested
- If classifier requested escalation and gate blocks: status = BLOCKED, summary states the blocking reason, detail shows the rule and the case's typology maturity
- Detail must always include: what was evaluated, the rule in plain language, why this case hit or missed

### Step ③ — Gate 2 (name varies by case)
The second gate evaluation.
- If Gate 1 blocked: status = NOT EVALUATED, summary = "Upstream gate blocked — not evaluated", dimmed at 55% opacity
- If Gate 1 passed: evaluate normally with same detail requirements as Gate 1

### Step ④ — Governed Resolution
How the system reconciled all inputs into a final disposition.
- Summary format: "[Classifier said X] → [Gates did Y] → [Resolved to Z]"
- Detail: List each component's recommendation, explain any conflict, state the fallback logic
- Status: The resolved disposition

### Step ⑤ — Terminal Disposition
The final status and what happens next.
- Summary: One line on what action is required
- Status: The terminal disposition
- Outcome: Used for the final outcome bar

## Example Flows

### Flow A: No Conflict (Foreign PEP — EDD path)

```
① Classifier: 3 Tier 2 signals, recommends EDD          [EDD REQUIRED - amber]
        ↓ (blue)
② Gate 1: No escalation requested, passes through        [PASSED - green]
        ↓ (blue)
③ Gate 2: No escalation in pipeline, not evaluated       [NOT EVALUATED - grey, dimmed]
        ↓ (grey)
④ Resolution: All agree → EDD REQUIRED confirmed         [CONFIRMED - green]
        ↓ (blue)
⑤ Terminal: EDD required before final determination      [EDD REQUIRED - amber]
        ↓
━━━ Governed Disposition: EDD REQUIRED ━━━
```

### Flow B: Conflict with Gate Block (Shell Company Layering)

```
① Classifier: 2 Tier 1 suspicion indicators, wants STR   [STR REQUIRED - amber]
        ↓ (blue)
② Gate 1: EMERGING typology, below threshold              [BLOCKED - red]
        ↓ (red)
③ Gate 2: Upstream blocked, not evaluated                  [NOT EVALUATED - grey, dimmed]
        ↓ (grey)
④ Resolution: STR blocked → fallback EDD                  [EDD REQUIRED - amber]
        ↓ (blue)
⑤ Terminal: Pending compliance officer post-EDD            [PENDING - amber]
        ↓
━━━ Governed Disposition: EDD REQUIRED ━━━
```

### Flow C: Clean Pass (low risk, no flags)

```
① Classifier: No suspicion or investigative signals       [NO REPORT - green]
        ↓ (blue)
② Gate 1: No escalation requested                         [PASSED - green]
        ↓ (blue)
③ Gate 2: No escalation in pipeline                       [NOT EVALUATED - grey, dimmed]
        ↓ (grey)
④ Resolution: All agree → NO REPORT                       [CONFIRMED - green]
        ↓ (blue)
⑤ Terminal: Transaction cleared                            [PASS - green]
        ↓
━━━ Governed Disposition: PASS ━━━
```

### Flow D: Hard Stop (Sanctions Match)

```
① Classifier: Hard stop triggered — SANCTIONS_MATCH      [STR REQUIRED - amber]
        ↓ (blue)
② Gate 1: Hard stop fast-tracks — passes immediately     [PASSED - green]
        ↓ (blue)
③ Gate 2: STR threshold evaluated                         [STR REQUIRED - amber]
        ↓ (blue)
④ Resolution: All paths agree → STR REQUIRED              [STR REQUIRED - amber]
        ↓ (blue)
⑤ Terminal: File STR within statutory timeframe            [STR REQUIRED - amber]
        ↓
━━━ Governed Disposition: STR REQUIRED ━━━
```

## Implementation Checklist

When building this component, follow the general checklist at the top of this doc, plus these specific steps:

1. **Backend data** — already exists. `decision_path_narrative` is built in `derive.py:_build_decision_path_narrative()` and exposed in `view_model.py:217`. No backend changes needed.

2. **Jinja template** — already has the section at `decision_report.html:404`. Consider moving it earlier (after linchpin statement) to match the new placement order.

3. **React component** — replace the current `DecisionPathNarrative.tsx` with the visual card-based design described above. Key changes:
   - Parse status from `arrow_line` for color coding
   - Add click-to-expand for `detail_lines`
   - Add connectors between cards
   - Add dimming for NOT EVALUATED steps
   - Add final outcome bar

4. **React placement** — move `<DecisionPathNarrative>` from its current position (after EvidenceSnapshot) to immediately after `<LinchpinStatement>`. Remove the `BranchPathViz` CollapsibleSection from Tier2Content.

5. **Build, copy assets, regenerate, commit** — per the standard checklist above.
