# FRONTEND BUILD TASK — DecisionGraph Core v1.3

## Context
We have an existing React dashboard (previously in `services/dashboard/` in the decision-engine repo) that needs to be rebuilt/adapted for the new DecisionGraph Core v1.3 backend. The backend just completed a 7-task banking pipeline fix.

## What Changed in Backend (v1.3)
1. **banking_field_registry.py** — 28 fields, single source of truth for all field names/labels/types
2. **aml_seed_generator.py** — 20 AML scenarios, 1,500 seeds, all 28 fields populated
3. **policy_shift_shadows.py** — 4 policy shifts with shadow projections (what-if analysis)
4. **main.py** — Updated scorer with outcome_map and decision_level_weight fixes
5. **render_md.py** — Fixed evidence table with registry-driven labels
6. **JudgmentPayload** — Domain-aware validation, signal_codes field
7. **New API endpoints** — `/api/policy-shifts` router added

## Frontend Requirements

### Tech Stack
- React 18 + TypeScript
- Vite for build
- Tailwind CSS for styling
- React Query for data fetching
- React Router for navigation
- Recharts for charts/visualizations

### Project Structure
```
services/dashboard/
├── src/
│   ├── api/
│   │   └── client.ts              # API client — connect to FastAPI backend
│   ├── components/
│   │   ├── Badge.tsx              # Outcome/confidence/risk badges
│   │   ├── ErrorMessage.tsx       # Error display
│   │   ├── Layout.tsx             # Sidebar navigation layout
│   │   ├── Loading.tsx            # Loading spinners
│   │   ├── Modal.tsx              # Reusable modal
│   │   ├── StatsCard.tsx          # Dashboard stat cards
│   │   ├── EvidenceTable.tsx      # Registry-driven evidence display (NEW)
│   │   ├── PolicyShiftCard.tsx    # Policy shift shadow display (NEW)
│   │   └── index.ts
│   ├── hooks/
│   │   └── useApi.ts              # React Query hooks for all endpoints
│   ├── pages/
│   │   ├── Dashboard.tsx          # Stats, charts, recent decisions
│   │   ├── JudgmentQueue.tsx      # Pending judgments with review modal
│   │   ├── DecisionViewer.tsx     # Full decision details, trace, facts
│   │   ├── SeedExplorer.tsx       # Browse 20 AML scenarios & 1500 seeds (NEW)
│   │   ├── PolicyShifts.tsx       # Policy shift shadow analysis (NEW)
│   │   ├── AuditSearch.tsx        # Search with filters, CSV export
│   │   ├── FieldRegistry.tsx      # View all 28 banking fields (NEW)
│   │   └── index.ts
│   ├── types/
│   │   └── index.ts               # TypeScript interfaces matching backend schemas
│   ├── App.tsx                    # Router + QueryClient setup
│   ├── main.tsx
│   └── index.css                  # Tailwind CSS
├── package.json
├── vite.config.ts
├── Dockerfile
└── tsconfig.json
```

### Pages to Build

#### 1. Dashboard (/)
- Stats cards: total decisions, pending judgments, approval rate, avg confidence
- Pie chart: decisions by AML scenario type
- Bar chart: decisions by outcome (APPROVE, DECLINE, ESCALATE)
- Recent decisions list with quick status badges
- Risk distribution heatmap

#### 2. Judgment Queue (/judgments)
- Table of pending judgments (from JudgmentPayload with signal_codes)
- Click to open full-context modal
- Modal shows: all 28 registry fields with labels, signals detected, recommended action
- Submit judgment: approve/reject/escalate with reason field
- Domain-aware validation feedback

#### 3. Decision Viewer (/decisions/:id)
- Full decision details with all 28 fields displayed using registry labels
- Elimination trace visualization (step by step through policy tree)
- Evidence table — registry-driven labels from banking_field_registry
- Signal codes with explanations
- Confidence scoring breakdown (decision_level_weight)
- Conflict display if any

#### 4. Seed Explorer (/seeds) — NEW
- Browse all 20 AML scenario types
- Filter/search across 1,500 seeds
- Click seed to see all 28 fields populated
- Run seed through pipeline and see decision output
- Scenario distribution chart

#### 5. Policy Shifts (/policy-shifts) — NEW
- Display 4 current policy shifts from policy_shift_shadows.py
- For each shift: show before/after rule comparison
- Shadow projection: how many existing decisions would change
- Impact analysis visualization (who gets affected)
- "What-if" toggle to simulate shift activation

#### 6. Audit Search (/audit)
- Search by: customer ID, scenario type, outcome, date range, signal codes
- Results table with sortable columns
- CSV export button
- Click any row to navigate to Decision Viewer

#### 7. Field Registry (/fields) — NEW
- Display all 28 fields from banking_field_registry
- Show: field name, label, type, description, which scenarios use it
- Search/filter fields
- Useful as reference documentation

### API Client (client.ts)
```typescript
// Base URL — configure for local dev vs production
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Endpoints to connect:
// GET  /api/decisions           — list decisions
// GET  /api/decisions/:id       — single decision detail
// POST /api/decisions/run       — run a seed through pipeline
// GET  /api/judgments            — pending judgments
// POST /api/judgments/:id        — submit judgment
// GET  /api/seeds               — list seeds/scenarios
// GET  /api/policy-shifts       — get policy shifts and shadows
// GET  /api/fields              — get field registry
// GET  /api/audit               — search audit log
// GET  /api/stats               — dashboard statistics
```

### Design Guidelines
- Dark theme (slate-900 background, slate-800 cards)
- Accent colors: emerald for success/approve, red for decline, amber for escalate
- Clean, professional — this is bank-grade compliance software
- Responsive but desktop-first (compliance officers use monitors)
- All data tables should be sortable and filterable
- Use the banking_field_registry labels everywhere — never hardcode field names

### Important Notes
- Check the actual backend API endpoints in main.py and routers/ before building API client
- Use the banking_field_registry.py field definitions for TypeScript types
- JudgmentPayload has domain-aware validation — respect it in the form
- Evidence table must use registry-driven labels from the registry, not hardcoded strings
- Policy shifts endpoint is at /api/policy-shifts (new router)

## Commands
```bash
cd services/dashboard
npm install
npm run dev          # dev server
npm run build        # production build
```
