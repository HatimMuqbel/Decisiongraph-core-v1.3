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
