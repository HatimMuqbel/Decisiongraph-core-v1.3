# ClaimPilot — Combine Landing + Interactive Demo

## Existing Files

- `claimpilot-landing.jsx` (905 lines) — Full marketing landing page with hero, problem section, benefits, Calendly modal, static demo walkthrough
- `claimpilot-demo.jsx` (786 lines) — Interactive demo with scenario data, exclusion evaluation, policy wording, reasoning chain

## Task

Combine into ONE page that:

1. **Keeps the landing page structure** — Hero, Problem, Benefits, Calendly
2. **Replaces the static demo walkthrough** with the interactive demo from `claimpilot-demo.jsx`
3. **Connects to the API** for real evaluation

## API Endpoints

```
Base URL: process.env.NEXT_PUBLIC_API_URL

GET  /demo/cases     → Pre-built scenarios
GET  /policies       → Available policy packs  
POST /evaluate       → Evaluate claim, returns recommendation
```

## Combined Page Flow

```
┌─────────────────────────────────────────┐
│ HERO                                    │
│ "Every satisfactory claim denial..."    │
│ [Schedule Demo] [Try It Now ↓]          │
├─────────────────────────────────────────┤
│ PROBLEM SECTION                         │
│ Why adjusters struggle today            │
├─────────────────────────────────────────┤
│ HOW IT WORKS (Interactive Demo)         │  ← Replace static with interactive
│                                         │
│ [Select Case: Auto - Rideshare ▼]       │
│                                         │
│ ┌─────────────┐  ┌──────────────────┐  │
│ │ FACTS       │  │ RECOMMENDATION   │  │
│ │             │  │                  │  │
│ │ Rideshare:  │  │ ❌ DENY          │  │
│ │ [● Yes][No] │  │                  │  │
│ │             │  │ Exclusion 4.2.1  │  │
│ │ BAC: [0.0]  │  │ triggered        │  │
│ │             │  │                  │  │
│ │ Licensed:   │  │ Policy Wording:  │  │
│ │ [Yes][● No] │  │ "We do not..."   │  │
│ └─────────────┘  └──────────────────┘  │
│                                         │
│ [Evaluate] ← Calls POST /evaluate       │
├─────────────────────────────────────────┤
│ BENEFITS SECTION                        │
│ Defensible, Consistent, Fast            │
├─────────────────────────────────────────┤
│ CTA                                     │
│ [Schedule Demo via Calendly]            │
└─────────────────────────────────────────┘
```

## Key Behaviors

1. **Load demo cases on mount** from `GET /demo/cases`
2. **Pre-populate facts** when user selects a case
3. **Editable facts** — toggles and dropdowns that user can change
4. **Live evaluation** — calls `POST /evaluate` when user clicks Evaluate or changes facts
5. **Show full reasoning** — exclusions evaluated, policy wording cited, provenance hash
6. **Custom case option** — user can build their own case from scratch

## Custom Case Feature

Add a "Build Your Own Case" option in the case selector dropdown.

When selected, show an empty form:

```
┌─────────────────────────────────────────┐
│ BUILD YOUR OWN CASE                     │
├─────────────────────────────────────────┤
│ Policy Pack: [Ontario Auto OAP 1 ▼]     │
│ Loss Type:   [collision ▼]              │
│ Loss Date:   [2024-06-15]               │
│                                         │
│ FACTS                                   │
│ ┌──────────────────┬────────────┬───┐  │
│ │ Field            │ Value      │   │  │
│ ├──────────────────┼────────────┼───┤  │
│ │ vehicle.use      │ [personal▼]│ ✕ │  │
│ │ driver.bac       │ [0.0     ] │ ✕ │  │
│ │ driver.licensed  │ [Yes ▼]    │ ✕ │  │
│ └──────────────────┴────────────┴───┘  │
│                                         │
│ [+ Add Fact]                            │
│                                         │
│ Common facts for selected policy:       │
│ [+ rideshare_app_active]                │
│ [+ racing_activity]                     │
│ [+ impairment_indicated]                │
│                                         │
│ EVIDENCE                                │
│ [✓] Police report                       │
│ [ ] Damage estimate                     │
│ [ ] Driver statement                    │
│ [+ Add evidence type]                   │
│                                         │
│ [EVALUATE CLAIM]                        │
└─────────────────────────────────────────┘
```

### How it works:

1. User selects "Build Your Own" from case dropdown
2. UI shows policy pack selector (from `GET /policies`)
3. Based on policy selected, show common facts as quick-add buttons
4. User can also type custom field names
5. Same evaluate flow — calls `POST /evaluate` with user-entered facts

### Suggested facts per policy (show as quick-add buttons):

**Auto:**
- vehicle.use_at_loss (personal/commercial/rideshare)
- driver.rideshare_app_active (true/false)
- driver.bac_level (number)
- driver.license_status (valid/suspended/expired)
- loss.racing_activity (true/false)

**Property:**
- loss.cause (fire/flood/theft/wind)
- dwelling.days_vacant (number)
- damage.gradual (true/false)

**Health:**
- drug.on_formulary (true/false)
- condition.preexisting (true/false)
- member.coverage_months (number)

**Workers Comp:**
- injury.work_related (true/false)
- injury.arose_out_of_employment (true/false)
- injury.intoxication_sole_cause (true/false)

## The "Aha Moment"

User selects "Auto - Standard Collision" → sees ✅ PAY

User toggles `rideshare_app_active` to `true` → instantly sees ❌ DENY with:
- Exclusion 4.2.1 triggered
- Policy wording quoted
- Reasoning chain showing why

## Fallback

If API unavailable, use the static demo data from `claimpilot-demo.jsx` so the page still works.

## Environment

```
NEXT_PUBLIC_API_URL=https://claimpilot-api.up.railway.app
```

## Deliverable

One combined React component that:
- Is the full marketing landing page
- Has embedded interactive demo connected to API
- Works standalone if API is down
- Mobile responsive
- Calendly integration for booking demos
