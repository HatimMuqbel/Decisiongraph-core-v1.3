# Build Your Own Case — Schema-Driven Architecture

## Context

ClaimPilot (claimpilot.pro) and DecisionGraph (decisiongraph.pro) need a "Build Your Own Case" feature where prospects can test custom scenarios using **dropdowns/toggles only** — no free text.

Reference spec: `BUILD_YOUR_OWN_CASE_SPEC.md` has all field definitions per policy type.

## Requirements

### 1. Schema-Driven Templates

Create a `CaseTemplate` config for each policy/scenario type:
- `template_id` (e.g., `ca-on-oap1-auto`)
- `title`, `version`
- `field_groups` (Facts, Evidence)
- `fields` with: id, label, control_type (select/toggle/checkbox), options, default
- `evidence_items` with: doc_type, label, required_rule, suggested_rule

**Adding new policy = add config file, not code.**

### 2. Map-Based Payload

Change facts from list to map:
```json
{
  "template_id": "ca-on-oap1-auto",
  "facts": {
    "driver.bac_level": "0.00",
    "driver.rideshare_app_active": false,
    "vehicle.use_at_loss": "personal"
  },
  "evidence": {
    "police_report": "verified",
    "damage_estimate": "verified",
    "driver_statement": "missing"
  }
}
```

### 3. Visibility Rules

Show fields conditionally:
- `high_risk_activity_type` only if `high_risk_activity = true`
- `water_source` only if `loss_type = water_damage`
- `destination_country` only if `cross_border = true`

Define in template: `visibility_rule: "loss_type == 'water_damage'"`

### 4. Disable Rules

Prevent impossible combinations:
- Can't select `flood` cause with `fire` loss type
- `sanctions_match = true` disables approve outcomes
- `license_status = suspended` shows warning

Define in template: `disable_if: "loss_type == 'fire'"`

### 5. Auto-Evaluate

- Re-run `/evaluate` on every change
- 250ms debounce
- Cancel in-flight requests on new change
- Show "Evaluating..." state
- Cache results by (template_id + facts hash) for instant toggle-back

### 6. Missing Evidence Warnings

Evidence items have:
- `required_if`: condition when mandatory
- `suggested_if`: condition when recommended
- `missing_behavior`: `warn` | `block` | `downgrade_certainty`

Show in results:
- "⚠️ Missing: Police Report — certainty downgraded"
- Or block: "Cannot evaluate — missing required evidence"

### 7. Case Summary Header

Auto-generate from selections:
```
Ontario Auto • Collision • Personal Use • Licensed • No Impairment • $8.5K
```

Sticky at top, updates live as user toggles.

### 8. Version Pinning

Every evaluation records:
- `template_version`
- `policy_pack_version`
- `policy_pack_hash` (already have this)
- `evaluated_at`

## UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│ Ontario Auto • Collision • Personal • $8.5K                 │  ← Summary
├─────────────────────────────────────────────────────────────┤
│ Template: [Ontario Auto (OAP 1) ▼]                          │
├──────────────────────────┬──────────────────────────────────┤
│ FACTS                    │ RESULT                           │
│                          │                                  │
│ Loss Type: [Collision ▼] │ ✅ PAY                           │
│ Vehicle Use: [Personal ▼]│ Certainty: HIGH                  │
│ Rideshare: [○ Yes][● No] │                                  │
│ BAC: [0.00 ▼]            │ Exclusions Evaluated:            │
│ Licensed: [● Yes][○ No]  │ ✓ Commercial — not triggered     │
│                          │ ✓ Impaired — not triggered       │
│ ─────────────────────    │                                  │
│ EVIDENCE                 │ ─────────────────────────────    │
│ [✓] Police Report        │ REASONING                        │
│ [✓] Damage Estimate      │ 1. Policy active ✓               │
│ [ ] Driver Statement     │ 2. Coverage applies ✓            │
│                          │ 3. No exclusions triggered ✓     │
│ ⚠️ Missing: Driver stmt  │                                  │
│    (suggested)           │ Provenance: 7a3f2b1c...          │
├──────────────────────────┴──────────────────────────────────┤
│ [✓] Auto-evaluate                    Evaluated: 2 sec ago   │
└─────────────────────────────────────────────────────────────┘
```

## Templates to Create

### ClaimPilot (Insurance)
1. `ca-on-oap1-auto` — Ontario Auto
2. `ca-on-ho3-property` — Homeowners
3. `ca-on-marine` — Pleasure Craft
4. `ca-on-health` — Group Health
5. `ca-on-wsib` — Workers Comp
6. `ca-cgl` — Commercial Liability
7. `ca-eo` — Professional E&O
8. `ca-travel` — Travel Medical

### DecisionGraph (Banking/AML)
1. `aml-txn-monitoring` — Transaction Monitoring
2. `aml-kyc-onboarding` — Customer Onboarding
3. `aml-pep-screening` — PEP/Sanctions Screening

## Field Reference

See `BUILD_YOUR_OWN_CASE_SPEC.md` for complete field definitions:
- All dropdowns/toggles per template
- All evidence items
- Expected outcomes tables

## Deliverables

1. Template schema format (JSON/YAML)
2. Template configs for all 11 scenarios
3. Updated `/evaluate` endpoint accepting map-based payload
4. Frontend component rendering templates dynamically
5. Visibility/disable rule engine
6. Auto-evaluate with debounce
7. Evidence warning system
8. Case summary generator

Both sites use same component, different templates.
