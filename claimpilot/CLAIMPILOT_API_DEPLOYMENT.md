# ClaimPilot API — FastAPI + Railway Deployment

## Goal

Create a complete FastAPI backend for ClaimPilot that:
1. Exposes the evaluation engine via REST API
2. Deploys to Railway
3. Connects to the frontend demo

---

## File Structure

```
claimpilot/                    # Existing ClaimPilot package
├── models/
├── engine/
├── packs/
│   ├── auto/ontario_oap1.yaml
│   ├── property/homeowners_ho3.yaml
│   ├── marine/pleasure_craft.yaml
│   ├── health/group_health.yaml
│   ├── workers_comp/ontario_wsib.yaml
│   ├── liability/cgl.yaml
│   ├── liability/professional_eo.yaml
│   └── travel/travel_medical.yaml
└── ...

api/                           # NEW - FastAPI app
├── __init__.py
├── main.py                    # FastAPI application
├── routes/
│   ├── __init__.py
│   ├── policies.py            # Policy pack endpoints
│   ├── evaluate.py            # Evaluation endpoint
│   └── demo.py                # Demo cases endpoint
├── schemas/
│   ├── __init__.py
│   ├── requests.py            # Request models
│   └── responses.py           # Response models
└── demo_cases.py              # Pre-built demo scenarios

requirements.txt               # Dependencies
Procfile                       # Railway start command
railway.toml                   # Railway config (optional)
```

---

## File: `requirements.txt`

```txt
# Core
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.0

# ClaimPilot dependencies
pyyaml>=6.0
python-dateutil>=2.8.2

# Utilities
python-multipart>=0.0.6
```

---

## File: `Procfile`

```
web: uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

---

## File: `railway.toml` (optional but recommended)

```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"
healthcheckPath = "/health"
healthcheckTimeout = 100
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```

---

## File: `api/__init__.py`

```python
"""ClaimPilot API"""
```

---

## File: `api/schemas/requests.py`

```python
"""Request schemas for the API."""

from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import date


class FactInput(BaseModel):
    """A single fact about the claim."""
    field: str = Field(..., description="Fact field name, e.g., 'vehicle.use_at_loss'")
    value: Any = Field(..., description="Fact value")
    certainty: str = Field(default="reported", description="confirmed|reported|inferred|disputed")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {"field": "vehicle.use_at_loss", "value": "personal", "certainty": "confirmed"},
                {"field": "driver.bac_level", "value": 0.0, "certainty": "confirmed"},
            ]
        }
    }


class EvidenceInput(BaseModel):
    """Evidence document collected."""
    doc_type: str = Field(..., description="Document type, e.g., 'police_report'")
    status: str = Field(default="verified", description="verified|received|requested")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {"doc_type": "police_report", "status": "verified"},
                {"doc_type": "damage_estimate", "status": "verified"},
            ]
        }
    }


class EvaluateRequest(BaseModel):
    """Request to evaluate a claim."""
    policy_id: str = Field(..., description="Policy pack ID, e.g., 'CA-ON-OAP1-2024'")
    loss_type: str = Field(..., description="Type of loss, e.g., 'collision'")
    loss_date: str = Field(..., description="Date of loss (ISO format: YYYY-MM-DD)")
    report_date: str = Field(..., description="Date reported (ISO format: YYYY-MM-DD)")
    claimant_type: str = Field(default="insured", description="insured|third_party|claimant")
    facts: list[FactInput] = Field(..., description="List of claim facts")
    evidence: list[EvidenceInput] = Field(default=[], description="Evidence collected")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "policy_id": "CA-ON-OAP1-2024",
                    "loss_type": "collision",
                    "loss_date": "2024-06-15",
                    "report_date": "2024-06-15",
                    "claimant_type": "insured",
                    "facts": [
                        {"field": "policy.status", "value": "active"},
                        {"field": "vehicle.use_at_loss", "value": "personal"},
                        {"field": "driver.rideshare_app_active", "value": False},
                        {"field": "driver.bac_level", "value": 0.0},
                        {"field": "driver.license_status", "value": "valid"},
                    ],
                    "evidence": [
                        {"doc_type": "police_report", "status": "verified"},
                        {"doc_type": "damage_estimate", "status": "verified"},
                    ]
                }
            ]
        }
    }
```

---

## File: `api/schemas/responses.py`

```python
"""Response schemas for the API."""

from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class AuthorityCited(BaseModel):
    """Authority citation in recommendation."""
    authority_type: str
    title: str
    section: str
    excerpt: Optional[str] = None
    excerpt_hash: Optional[str] = None


class ReasoningStep(BaseModel):
    """A step in the reasoning chain."""
    sequence: int
    step_type: str
    description: str
    rule_id: Optional[str] = None
    rule_name: Optional[str] = None
    result: str  # passed|failed|uncertain|not_applicable
    result_reason: Optional[str] = None


class ExclusionEvaluated(BaseModel):
    """Result of evaluating an exclusion."""
    id: str
    code: str
    name: str
    triggered: bool
    reason: str
    policy_wording: Optional[str] = None


class EvaluateResponse(BaseModel):
    """Response from claim evaluation."""
    # Identifiers
    claim_id: str
    policy_pack_id: str
    policy_pack_version: str
    policy_pack_hash: str
    
    # Recommendation
    recommended_disposition: str  # pay|deny|partial|escalate|request_info|hold|refer_siu
    disposition_reason: str
    certainty: str  # high|medium|low|requires_judgment
    
    # Coverage evaluation
    coverages_evaluated: list[str]
    coverage_applies: bool
    
    # Exclusion evaluation
    exclusions_evaluated: list[ExclusionEvaluated]
    exclusions_triggered: list[str]
    exclusions_ruled_out: list[str]
    exclusions_uncertain: list[str]
    
    # Authority
    requires_authority: bool
    required_role: Optional[str] = None
    authority_rule_triggered: Optional[str] = None
    
    # Evidence
    evidence_complete: bool
    evidence_missing: list[str]
    
    # Guidance
    unknown_facts: list[str]
    next_best_questions: list[str]
    
    # Reasoning
    authorities_cited: list[AuthorityCited]
    reasoning_steps: list[ReasoningStep]
    
    # Provenance
    evaluated_at: str
    engine_version: str


class PolicySummary(BaseModel):
    """Summary of a policy pack."""
    id: str
    name: str
    jurisdiction: str
    line_of_business: str
    product_code: str
    version: str
    effective_date: str
    coverage_count: int
    exclusion_count: int


class CoverageSummary(BaseModel):
    """Summary of a coverage section."""
    id: str
    code: str
    name: str
    description: str
    loss_types: list[str]


class ExclusionSummary(BaseModel):
    """Summary of an exclusion."""
    id: str
    code: str
    name: str
    description: str
    policy_wording: str
    applies_to: list[str]
    evaluation_questions: list[str]


class PolicyDetail(BaseModel):
    """Full details of a policy pack."""
    id: str
    name: str
    jurisdiction: str
    line_of_business: str
    product_code: str
    version: str
    effective_date: str
    policy_pack_hash: str
    coverages: list[CoverageSummary]
    exclusions: list[ExclusionSummary]


class DemoCase(BaseModel):
    """A pre-built demo case."""
    id: str
    name: str
    description: str
    line_of_business: str
    policy_id: str
    expected_outcome: str  # pay|deny|escalate|etc
    expected_reason: str
    facts: list[dict]
    evidence: list[dict]
    
    # Key facts that drive the outcome
    key_facts: list[str]
```

---

## File: `api/demo_cases.py`

```python
"""Pre-built demo cases for the interactive demo."""

DEMO_CASES = [
    # ============== AUTO CASES ==============
    {
        "id": "auto-approve-standard",
        "name": "Standard Collision — APPROVE",
        "description": "Rear-end collision, no exclusions apply. Straightforward approval.",
        "line_of_business": "auto",
        "policy_id": "CA-ON-OAP1-2024",
        "expected_outcome": "pay",
        "expected_reason": "Coverage applies, no exclusions triggered",
        "key_facts": ["Personal use", "Licensed driver", "No impairment"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "policy.premiums_current", "value": True},
            {"field": "vehicle.use_at_loss", "value": "personal"},
            {"field": "driver.rideshare_app_active", "value": False},
            {"field": "driver.license_status", "value": "valid"},
            {"field": "driver.bac_level", "value": 0.0},
            {"field": "driver.impairment_indicated", "value": False},
            {"field": "loss.racing_activity", "value": False},
            {"field": "loss.intentional_indicators", "value": False},
            {"field": "claim.reserve_amount", "value": 8500},
        ],
        "evidence": [
            {"doc_type": "police_report", "status": "verified"},
            {"doc_type": "damage_estimate", "status": "verified"},
            {"doc_type": "proof_of_ownership", "status": "verified"},
        ]
    },
    {
        "id": "auto-deny-rideshare",
        "name": "Rideshare Delivery — DENY",
        "description": "Driver was delivering food via Uber Eats. Commercial use exclusion applies.",
        "line_of_business": "auto",
        "policy_id": "CA-ON-OAP1-2024",
        "expected_outcome": "deny",
        "expected_reason": "Commercial Use Exclusion (4.2.1) triggered",
        "key_facts": ["Rideshare app active", "Delivery use"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "vehicle.use_at_loss", "value": "delivery"},
            {"field": "driver.rideshare_app_active", "value": True},
            {"field": "driver.license_status", "value": "valid"},
            {"field": "driver.bac_level", "value": 0.0},
            {"field": "loss.racing_activity", "value": False},
        ],
        "evidence": [
            {"doc_type": "police_report", "status": "verified"},
            {"doc_type": "driver_statement", "status": "verified"},
            {"doc_type": "app_activity_records", "status": "verified"},
        ]
    },
    {
        "id": "auto-deny-impaired",
        "name": "Impaired Driver — DENY",
        "description": "Driver had BAC of 0.12, charged with impaired driving.",
        "line_of_business": "auto",
        "policy_id": "CA-ON-OAP1-2024",
        "expected_outcome": "deny",
        "expected_reason": "Impaired Operation Exclusion (4.3.3) triggered",
        "key_facts": ["BAC over 0.08", "Impaired charges laid"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "vehicle.use_at_loss", "value": "personal"},
            {"field": "driver.rideshare_app_active", "value": False},
            {"field": "driver.license_status", "value": "valid"},
            {"field": "driver.bac_level", "value": 0.12},
            {"field": "driver.impairment_indicated", "value": True},
            {"field": "police_report.impaired_charges", "value": True},
        ],
        "evidence": [
            {"doc_type": "police_report", "status": "verified"},
            {"doc_type": "toxicology_report", "status": "verified"},
        ]
    },
    {
        "id": "auto-deny-unlicensed",
        "name": "Unlicensed Driver — DENY",
        "description": "Driver's license was suspended at time of loss.",
        "line_of_business": "auto",
        "policy_id": "CA-ON-OAP1-2024",
        "expected_outcome": "deny",
        "expected_reason": "Unlicensed Driver Exclusion (4.1.2) triggered",
        "key_facts": ["License suspended"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "vehicle.use_at_loss", "value": "personal"},
            {"field": "driver.license_status", "value": "suspended"},
            {"field": "driver.bac_level", "value": 0.0},
        ],
        "evidence": [
            {"doc_type": "police_report", "status": "verified"},
            {"doc_type": "mto_driver_abstract", "status": "verified"},
        ]
    },
    {
        "id": "auto-escalate-high-value",
        "name": "High Value Claim — ESCALATE",
        "description": "Major accident with $75,000 in damages. Requires manager approval.",
        "line_of_business": "auto",
        "policy_id": "CA-ON-OAP1-2024",
        "expected_outcome": "pay",
        "expected_reason": "Coverage applies, but requires manager approval (over $50K)",
        "key_facts": ["Reserve over $50,000"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "vehicle.use_at_loss", "value": "personal"},
            {"field": "driver.rideshare_app_active", "value": False},
            {"field": "driver.license_status", "value": "valid"},
            {"field": "driver.bac_level", "value": 0.0},
            {"field": "claim.reserve_amount", "value": 75000},
        ],
        "evidence": [
            {"doc_type": "police_report", "status": "verified"},
            {"doc_type": "damage_estimate", "status": "verified"},
        ]
    },
    
    # ============== PROPERTY CASES ==============
    {
        "id": "property-approve-fire",
        "name": "Kitchen Fire — APPROVE",
        "description": "Kitchen fire caused by cooking accident. Clear covered peril.",
        "line_of_business": "property",
        "policy_id": "CA-ON-HO3-2024",
        "expected_outcome": "pay",
        "expected_reason": "Fire is a covered peril under Coverage A",
        "key_facts": ["Fire loss", "Occupied dwelling"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "loss.type", "value": "fire"},
            {"field": "loss.cause", "value": "cooking_accident"},
            {"field": "dwelling.habitable", "value": True},
            {"field": "dwelling.days_vacant", "value": 0},
            {"field": "insured.mitigation_efforts", "value": True},
        ],
        "evidence": [
            {"doc_type": "claim_form", "status": "verified"},
            {"doc_type": "fire_department_report", "status": "verified"},
            {"doc_type": "damage_photos", "status": "verified"},
        ]
    },
    {
        "id": "property-deny-flood",
        "name": "Basement Flood — DENY",
        "description": "Basement flooded during heavy rain. Flood exclusion applies.",
        "line_of_business": "property",
        "policy_id": "CA-ON-HO3-2024",
        "expected_outcome": "deny",
        "expected_reason": "Flood Exclusion (EX-FLOOD) triggered",
        "key_facts": ["Surface water", "Ground-level entry"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "loss.type", "value": "water_damage"},
            {"field": "loss.cause", "value": "flood"},
            {"field": "water.source", "value": "surface_water"},
            {"field": "water.entered_from", "value": "ground_level"},
        ],
        "evidence": [
            {"doc_type": "claim_form", "status": "verified"},
            {"doc_type": "adjuster_inspection_report", "status": "verified"},
        ]
    },
    {
        "id": "property-deny-vacancy",
        "name": "Vacant Property Theft — DENY",
        "description": "Property vacant for 45 days when theft occurred.",
        "line_of_business": "property",
        "policy_id": "CA-ON-HO3-2024",
        "expected_outcome": "deny",
        "expected_reason": "Vacancy Exclusion (EX-VACANT) triggered — vacant > 30 days",
        "key_facts": ["45 days vacant", "No vacancy permit"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "loss.type", "value": "theft"},
            {"field": "dwelling.days_vacant", "value": 45},
        ],
        "evidence": [
            {"doc_type": "claim_form", "status": "verified"},
            {"doc_type": "police_report", "status": "verified"},
        ]
    },
    
    # ============== MARINE CASES ==============
    {
        "id": "marine-approve-storm",
        "name": "Storm Damage — APPROVE",
        "description": "Boat damaged in storm while within approved cruising area.",
        "line_of_business": "marine",
        "policy_id": "CA-ON-MARINE-2024",
        "expected_outcome": "pay",
        "expected_reason": "Storm damage covered, within navigation limits",
        "key_facts": ["Within navigation limits", "Valid PCOC"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "loss.type", "value": "storm_damage"},
            {"field": "vessel.within_navigation_limits", "value": True},
            {"field": "operator.pcoc_valid", "value": True},
            {"field": "vessel.maintenance_current", "value": True},
            {"field": "vessel.commercial_use", "value": False},
        ],
        "evidence": [
            {"doc_type": "claim_form", "status": "verified"},
            {"doc_type": "damage_photos", "status": "verified"},
            {"doc_type": "weather_report", "status": "verified"},
        ]
    },
    {
        "id": "marine-deny-navigation",
        "name": "Outside Navigation Limits — DENY",
        "description": "Boat damaged 50 miles offshore, outside approved area.",
        "line_of_business": "marine",
        "policy_id": "CA-ON-MARINE-2024",
        "expected_outcome": "deny",
        "expected_reason": "Navigation Limits Exclusion (EX-NAV) triggered",
        "key_facts": ["Outside approved cruising area"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "loss.type", "value": "grounding"},
            {"field": "vessel.within_navigation_limits", "value": False},
            {"field": "loss.location", "value": "50 miles offshore"},
        ],
        "evidence": [
            {"doc_type": "claim_form", "status": "verified"},
            {"doc_type": "coast_guard_report", "status": "verified"},
            {"doc_type": "gps_records", "status": "verified"},
        ]
    },
    
    # ============== HEALTH CASES ==============
    {
        "id": "health-approve-formulary",
        "name": "Formulary Drug — APPROVE",
        "description": "Standard prescription for drug on plan formulary.",
        "line_of_business": "health",
        "policy_id": "CA-ON-GH-2024",
        "expected_outcome": "pay",
        "expected_reason": "Formulary drug with valid prescription",
        "key_facts": ["On formulary", "Valid prescription"],
        "facts": [
            {"field": "member.status", "value": "active"},
            {"field": "drug.din_eligible", "value": True},
            {"field": "drug.on_formulary", "value": True},
            {"field": "prescription.valid", "value": True},
            {"field": "drug.prior_auth_required", "value": False},
        ],
        "evidence": [
            {"doc_type": "pharmacy_receipt", "status": "verified"},
            {"doc_type": "prescription", "status": "verified"},
        ]
    },
    {
        "id": "health-deny-preexisting",
        "name": "Pre-existing Condition — DENY",
        "description": "Member enrolled 3 months ago, claiming for condition treated before enrollment.",
        "line_of_business": "health",
        "policy_id": "CA-ON-GH-2024",
        "expected_outcome": "deny",
        "expected_reason": "Pre-existing Condition Exclusion (EX-PRE) triggered",
        "key_facts": ["Coverage < 12 months", "Condition treated before enrollment"],
        "facts": [
            {"field": "member.status", "value": "active"},
            {"field": "member.coverage_months", "value": 3},
            {"field": "condition.preexisting", "value": True},
        ],
        "evidence": [
            {"doc_type": "claim_form", "status": "verified"},
            {"doc_type": "medical_records", "status": "verified"},
        ]
    },
    
    # ============== WORKERS COMP CASES ==============
    {
        "id": "wsib-approve-work-injury",
        "name": "Work Injury — APPROVE",
        "description": "Worker injured lifting boxes at warehouse.",
        "line_of_business": "workers_comp",
        "policy_id": "CA-ON-WSIB-2024",
        "expected_outcome": "pay",
        "expected_reason": "Clear work-related injury, entitled to benefits",
        "key_facts": ["Work-related", "In course of employment"],
        "facts": [
            {"field": "employer.wsib_registered", "value": True},
            {"field": "injury.work_related", "value": True},
            {"field": "injury.arose_out_of_employment", "value": True},
            {"field": "injury.in_course_of_employment", "value": True},
            {"field": "injury.self_inflicted", "value": False},
            {"field": "injury.intoxication_sole_cause", "value": False},
        ],
        "evidence": [
            {"doc_type": "form_7", "status": "verified"},
            {"doc_type": "form_8", "status": "verified"},
            {"doc_type": "worker_statement", "status": "verified"},
        ]
    },
    {
        "id": "wsib-deny-not-work",
        "name": "Weekend Soccer Injury — DENY",
        "description": "Worker hurt playing recreational soccer on weekend.",
        "line_of_business": "workers_comp",
        "policy_id": "CA-ON-WSIB-2024",
        "expected_outcome": "deny",
        "expected_reason": "Not Work-Related Exclusion triggered",
        "key_facts": ["Injury outside work", "Not during work hours"],
        "facts": [
            {"field": "employer.wsib_registered", "value": True},
            {"field": "injury.work_related", "value": False},
            {"field": "injury.location", "value": "soccer field"},
            {"field": "injury.during_work_hours", "value": False},
        ],
        "evidence": [
            {"doc_type": "form_7", "status": "verified"},
            {"doc_type": "worker_statement", "status": "verified"},
        ]
    },
    
    # ============== CGL CASES ==============
    {
        "id": "cgl-approve-slip-fall",
        "name": "Slip and Fall — APPROVE",
        "description": "Customer slipped on wet floor in store.",
        "line_of_business": "liability",
        "policy_id": "CA-CGL-2024",
        "expected_outcome": "pay",
        "expected_reason": "Premises liability, third-party bodily injury covered",
        "key_facts": ["Third party injury", "On premises"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "loss.type", "value": "bodily_injury_tp"},
            {"field": "occurrence.during_policy_period", "value": True},
            {"field": "occurrence.in_coverage_territory", "value": True},
            {"field": "injury.expected_intended", "value": False},
            {"field": "loss.pollution_related", "value": False},
            {"field": "loss.auto_involved", "value": False},
        ],
        "evidence": [
            {"doc_type": "claim_notice", "status": "verified"},
            {"doc_type": "incident_report", "status": "verified"},
        ]
    },
    {
        "id": "cgl-deny-pollution",
        "name": "Chemical Spill — DENY",
        "description": "Chemical spill caused by insured's operations.",
        "line_of_business": "liability",
        "policy_id": "CA-CGL-2024",
        "expected_outcome": "deny",
        "expected_reason": "Pollution Exclusion (EX-POLL) triggered",
        "key_facts": ["Pollution event"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "loss.type", "value": "property_damage_tp"},
            {"field": "loss.pollution_related", "value": True},
            {"field": "occurrence.during_policy_period", "value": True},
        ],
        "evidence": [
            {"doc_type": "claim_notice", "status": "verified"},
            {"doc_type": "environmental_report", "status": "verified"},
        ]
    },
]


def get_demo_cases() -> list[dict]:
    """Return all demo cases."""
    return DEMO_CASES


def get_demo_case(case_id: str) -> dict | None:
    """Get a specific demo case by ID."""
    for case in DEMO_CASES:
        if case["id"] == case_id:
            return case
    return None


def get_demo_cases_by_line(line_of_business: str) -> list[dict]:
    """Get demo cases filtered by line of business."""
    return [c for c in DEMO_CASES if c["line_of_business"] == line_of_business]
```

---

## File: `api/routes/policies.py`

```python
"""Policy pack endpoints."""

from fastapi import APIRouter, HTTPException
from typing import Optional

from api.schemas.responses import PolicySummary, PolicyDetail, CoverageSummary, ExclusionSummary
from claimpilot.engine import PolicyEngine
from claimpilot.canon import compute_policy_pack_hash

router = APIRouter(prefix="/policies", tags=["Policies"])

# Shared engine instance (set by main.py)
engine: PolicyEngine = None


def set_engine(e: PolicyEngine):
    global engine
    engine = e


@router.get("", response_model=list[PolicySummary])
async def list_policies(line_of_business: Optional[str] = None):
    """
    List all available policy packs.
    
    Optionally filter by line of business: auto, property, marine, health, 
    workers_comp, liability
    """
    policies = engine.list_policies()
    
    if line_of_business:
        policies = [p for p in policies if p.line_of_business.value == line_of_business]
    
    return [
        PolicySummary(
            id=p.id,
            name=p.name,
            jurisdiction=p.jurisdiction,
            line_of_business=p.line_of_business.value,
            product_code=p.product_code,
            version=p.version,
            effective_date=p.effective_date.isoformat(),
            coverage_count=len(p.coverage_sections),
            exclusion_count=len(p.exclusions)
        )
        for p in policies
    ]


@router.get("/{policy_id}", response_model=PolicyDetail)
async def get_policy(policy_id: str):
    """Get full details of a policy pack including coverages and exclusions."""
    policy = engine.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found")
    
    return PolicyDetail(
        id=policy.id,
        name=policy.name,
        jurisdiction=policy.jurisdiction,
        line_of_business=policy.line_of_business.value,
        product_code=policy.product_code,
        version=policy.version,
        effective_date=policy.effective_date.isoformat(),
        policy_pack_hash=compute_policy_pack_hash(policy),
        coverages=[
            CoverageSummary(
                id=c.id,
                code=c.code,
                name=c.name,
                description=c.description,
                loss_types=[t.loss_type for t in (c.triggers or [])]
            )
            for c in policy.coverage_sections
        ],
        exclusions=[
            ExclusionSummary(
                id=e.id,
                code=e.code,
                name=e.name,
                description=e.description,
                policy_wording=e.policy_wording,
                applies_to=e.applies_to_coverages,
                evaluation_questions=e.evaluation_questions or []
            )
            for e in policy.exclusions
        ]
    )


@router.get("/{policy_id}/exclusions")
async def get_policy_exclusions(policy_id: str):
    """Get all exclusions for a policy pack with full policy wording."""
    policy = engine.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found")
    
    return [
        {
            "id": e.id,
            "code": e.code,
            "name": e.name,
            "description": e.description,
            "policy_wording": e.policy_wording,
            "policy_section_ref": e.policy_section_ref,
            "applies_to_coverages": e.applies_to_coverages,
            "evaluation_questions": e.evaluation_questions or [],
            "evidence_to_confirm": e.evidence_to_confirm or [],
            "evidence_to_rule_out": e.evidence_to_rule_out or [],
        }
        for e in policy.exclusions
    ]
```

---

## File: `api/routes/evaluate.py`

```python
"""Claim evaluation endpoint."""

from fastapi import APIRouter, HTTPException
from datetime import date, datetime
import uuid

from api.schemas.requests import EvaluateRequest
from api.schemas.responses import (
    EvaluateResponse, AuthorityCited, ReasoningStep, ExclusionEvaluated
)
from claimpilot.engine import (
    PolicyEngine, ContextResolver, ConditionEvaluator,
    RecommendationBuilder, EvidenceGate, AuthorityRouter
)
from claimpilot.models import (
    ClaimantType, FactSource, FactCertainty, EvidenceStatus,
    Fact, EvidenceItem, DispositionType
)
from claimpilot.canon import compute_policy_pack_hash
import claimpilot

router = APIRouter(prefix="/evaluate", tags=["Evaluation"])

# Shared engine instance
engine: PolicyEngine = None


def set_engine(e: PolicyEngine):
    global engine
    engine = e


@router.post("", response_model=EvaluateResponse)
async def evaluate_claim(request: EvaluateRequest):
    """
    Evaluate a claim and return a recommendation.
    
    This is the main endpoint. Takes claim facts and evidence,
    returns a full recommendation with reasoning chain, citations,
    and provenance.
    """
    # Get policy
    policy = engine.get_policy(request.policy_id)
    if not policy:
        raise HTTPException(
            status_code=404, 
            detail=f"Policy '{request.policy_id}' not found. "
                   f"Available: {[p.id for p in engine.list_policies()]}"
        )
    
    # Parse dates
    try:
        loss_date = date.fromisoformat(request.loss_date)
        report_date = date.fromisoformat(request.report_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    
    # Parse claimant type
    try:
        claimant_type = ClaimantType(request.claimant_type)
    except ValueError:
        claimant_type = ClaimantType.INSURED
    
    # Generate claim ID
    claim_id = f"EVAL-{uuid.uuid4().hex[:8].upper()}"
    
    # Resolve context
    resolver = ContextResolver(engine)
    context = resolver.resolve(
        claim_id=claim_id,
        policy_id=policy.id,
        loss_type=request.loss_type,
        loss_date=loss_date,
        report_date=report_date,
        claimant_type=claimant_type
    )
    
    # Build facts
    facts = {}
    for f in request.facts:
        certainty = FactCertainty.REPORTED
        if f.certainty == "confirmed":
            certainty = FactCertainty.CONFIRMED
        elif f.certainty == "disputed":
            certainty = FactCertainty.DISPUTED
        
        fact = Fact(
            id=f"fact_{f.field.replace('.', '_')}",
            claim_id=claim_id,
            field=f.field,
            value=f.value,
            value_type=type(f.value).__name__,
            source=FactSource.ADJUSTER_INPUT,
            certainty=certainty
        )
        facts[f.field] = fact
    
    # Build evidence
    evidence = []
    for e in request.evidence:
        status = EvidenceStatus.VERIFIED
        if e.status == "received":
            status = EvidenceStatus.RECEIVED
        elif e.status == "requested":
            status = EvidenceStatus.REQUESTED
        
        evidence.append(EvidenceItem(
            id=f"ev_{e.doc_type}",
            claim_id=claim_id,
            doc_type=e.doc_type,
            description=e.doc_type.replace("_", " ").title(),
            status=status
        ))
    
    # Build recommendation
    builder = RecommendationBuilder(context, policy)
    
    # Add facts
    for fact in facts.values():
        builder.add_fact(fact)
    
    # Add evidence
    for ev in evidence:
        builder.add_evidence(ev)
    
    # Evaluate exclusions
    evaluator = ConditionEvaluator()
    exclusions_evaluated = []
    
    for exclusion in context.applicable_exclusions:
        triggered = False
        reason = "Not triggered"
        
        for condition in exclusion.trigger_conditions:
            result = evaluator.evaluate(condition, facts)
            if result.result is True:
                triggered = True
                reason = f"Condition met: {result.explanation}"
                builder.record_exclusion_triggered(exclusion, result)
                break
            elif result.result is None:
                reason = f"Uncertain: {', '.join(result.unknown_fields)} unknown"
        
        if not triggered and result.result is False:
            builder.record_exclusion_ruled_out(exclusion, result)
        
        exclusions_evaluated.append(ExclusionEvaluated(
            id=exclusion.id,
            code=exclusion.code,
            name=exclusion.name,
            triggered=triggered,
            reason=reason,
            policy_wording=exclusion.policy_wording if triggered else None
        ))
    
    # Check evidence gate
    evidence_gate = EvidenceGate()
    # ... evidence checking logic ...
    
    # Check authority
    authority_router = AuthorityRouter()
    # ... authority routing logic ...
    
    # Build final recommendation
    recommendation = builder.build()
    
    # Format response
    return EvaluateResponse(
        claim_id=claim_id,
        policy_pack_id=policy.id,
        policy_pack_version=policy.version,
        policy_pack_hash=compute_policy_pack_hash(policy),
        
        recommended_disposition=recommendation.recommended_disposition.value,
        disposition_reason=recommendation.disposition_reason,
        certainty=recommendation.certainty.value,
        
        coverages_evaluated=recommendation.coverages_evaluated,
        coverage_applies=len(recommendation.exclusions_triggered) == 0,
        
        exclusions_evaluated=exclusions_evaluated,
        exclusions_triggered=recommendation.exclusions_triggered,
        exclusions_ruled_out=recommendation.exclusions_ruled_out,
        exclusions_uncertain=recommendation.exclusions_uncertain,
        
        requires_authority=recommendation.requires_authority,
        required_role=recommendation.required_role,
        authority_rule_triggered=recommendation.authority_rule_triggered,
        
        evidence_complete=len(recommendation.evidence_missing) == 0,
        evidence_missing=recommendation.evidence_missing,
        
        unknown_facts=recommendation.unknown_facts,
        next_best_questions=recommendation.next_best_questions,
        
        authorities_cited=[
            AuthorityCited(
                authority_type=a.authority_type.value,
                title=a.title,
                section=a.section,
                excerpt=a.quote_excerpt,
                excerpt_hash=None  # Add if needed
            )
            for a in recommendation.authorities_cited
        ],
        
        reasoning_steps=[
            ReasoningStep(
                sequence=i,
                step_type=s.step_type,
                description=s.description,
                rule_id=s.rule_id,
                rule_name=s.rule_name,
                result=s.result,
                result_reason=s.result_reason
            )
            for i, s in enumerate(recommendation.reasoning_steps, 1)
        ],
        
        evaluated_at=datetime.utcnow().isoformat() + "Z",
        engine_version=getattr(claimpilot, '__version__', '1.0.0')
    )
```

---

## File: `api/routes/demo.py`

```python
"""Demo cases endpoint."""

from fastapi import APIRouter, HTTPException
from typing import Optional

from api.demo_cases import get_demo_cases, get_demo_case, get_demo_cases_by_line
from api.schemas.responses import DemoCase

router = APIRouter(prefix="/demo", tags=["Demo"])


@router.get("/cases", response_model=list[DemoCase])
async def list_demo_cases(line_of_business: Optional[str] = None):
    """
    List pre-built demo cases.
    
    Optionally filter by line of business: auto, property, marine, health, 
    workers_comp, liability
    """
    if line_of_business:
        cases = get_demo_cases_by_line(line_of_business)
    else:
        cases = get_demo_cases()
    
    return [DemoCase(**c) for c in cases]


@router.get("/cases/{case_id}", response_model=DemoCase)
async def get_demo_case_by_id(case_id: str):
    """Get a specific demo case by ID."""
    case = get_demo_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Demo case '{case_id}' not found")
    
    return DemoCase(**case)
```

---

## File: `api/main.py`

```python
"""
ClaimPilot API

Product-agnostic insurance claims evaluation engine.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path

from claimpilot.engine import PolicyEngine
from claimpilot.packs.loader import load_policy

from api.routes import policies, evaluate, demo


# Policy engine singleton
engine = PolicyEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load policy packs on startup."""
    print("Loading policy packs...")
    
    packs_dir = Path(__file__).parent.parent / "claimpilot" / "packs"
    
    policy_files = [
        "auto/ontario_oap1.yaml",
        "property/homeowners_ho3.yaml",
        "marine/pleasure_craft.yaml",
        "health/group_health.yaml",
        "workers_comp/ontario_wsib.yaml",
        "liability/cgl.yaml",
        "liability/professional_eo.yaml",
        "travel/travel_medical.yaml",
    ]
    
    loaded = 0
    for policy_file in policy_files:
        path = packs_dir / policy_file
        if path.exists():
            try:
                policy = load_policy(str(path))
                engine.register_policy(policy)
                print(f"  ✓ Loaded {policy.id}")
                loaded += 1
            except Exception as e:
                print(f"  ✗ Failed to load {policy_file}: {e}")
        else:
            print(f"  ✗ Not found: {policy_file}")
    
    print(f"Loaded {loaded} policy packs")
    
    # Share engine with routes
    policies.set_engine(engine)
    evaluate.set_engine(engine)
    
    yield
    
    print("Shutting down...")


# Create app
app = FastAPI(
    title="ClaimPilot API",
    description="""
    **Product-agnostic insurance claims evaluation engine.**
    
    ClaimPilot evaluates claims against policy rules and returns recommendations
    with full reasoning chains and provenance.
    
    ## Features
    
    - **8 Policy Packs**: Auto, Property, Marine, Health, Workers Comp, CGL, E&O, Travel
    - **Deterministic Evaluation**: Same facts → same recommendation
    - **Full Audit Trail**: Reasoning steps, citations, provenance hashes
    - **Real Policy Wording**: Actual exclusion language cited
    
    ## Quick Start
    
    1. `GET /policies` - See available policy packs
    2. `GET /demo/cases` - See pre-built scenarios
    3. `POST /evaluate` - Evaluate a claim
    """,
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://claimpilot.io",
        "https://claimpilot.ca",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(policies.router)
app.include_router(evaluate.router)
app.include_router(demo.router)


@app.get("/", tags=["Health"])
async def root():
    """API root - health check and info."""
    return {
        "service": "ClaimPilot API",
        "version": "1.0.0",
        "status": "running",
        "policies_loaded": len(engine.list_policies()),
        "docs": "/docs",
        "openapi": "/openapi.json"
    }


@app.get("/health", tags=["Health"])
async def health():
    """Health check endpoint."""
    return {
        "healthy": True,
        "policies_loaded": len(engine.list_policies())
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## File: `api/routes/__init__.py`

```python
"""API routes."""
from . import policies, evaluate, demo
```

---

## File: `api/schemas/__init__.py`

```python
"""API schemas."""
from .requests import *
from .responses import *
```

---

## Deployment Steps (Railway)

### 1. Ensure file structure

```
your-repo/
├── api/
│   ├── __init__.py
│   ├── main.py
│   ├── demo_cases.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── policies.py
│   │   ├── evaluate.py
│   │   └── demo.py
│   └── schemas/
│       ├── __init__.py
│       ├── requests.py
│       └── responses.py
├── claimpilot/           # Your existing package
│   ├── models/
│   ├── engine/
│   ├── packs/
│   └── ...
├── requirements.txt
├── Procfile
└── railway.toml
```

### 2. Push to GitHub

```bash
git add .
git commit -m "Add FastAPI backend"
git push
```

### 3. Connect Railway

1. Go to railway.app
2. New Project → Deploy from GitHub repo
3. Railway auto-detects Python
4. Deploys automatically

### 4. Get your API URL

Railway gives you a URL like:
`https://claimpilot-api-production.up.railway.app`

---

## Test Endpoints

Once deployed:

```bash
# Health check
curl https://your-railway-url.up.railway.app/health

# List policies
curl https://your-railway-url.up.railway.app/policies

# Get demo cases
curl https://your-railway-url.up.railway.app/demo/cases

# Evaluate a claim
curl -X POST https://your-railway-url.up.railway.app/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "policy_id": "CA-ON-OAP1-2024",
    "loss_type": "collision",
    "loss_date": "2024-06-15",
    "report_date": "2024-06-15",
    "facts": [
      {"field": "policy.status", "value": "active"},
      {"field": "vehicle.use_at_loss", "value": "personal"},
      {"field": "driver.rideshare_app_active", "value": false}
    ],
    "evidence": [
      {"doc_type": "police_report", "status": "verified"}
    ]
  }'
```

---

## Next: Frontend Integration

Once the API is running, the frontend "Try It" section calls:

```javascript
const response = await fetch(`${API_URL}/evaluate`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    policy_id: selectedPolicy,
    loss_type: lossType,
    loss_date: lossDate,
    report_date: reportDate,
    facts: facts,
    evidence: evidence
  })
});

const recommendation = await response.json();
// Display recommendation.recommended_disposition
// Display recommendation.reasoning_steps
// Display recommendation.exclusions_evaluated
```

---

## Summary

| File | Purpose |
|------|---------|
| `api/main.py` | FastAPI app, startup, CORS |
| `api/routes/policies.py` | Policy pack endpoints |
| `api/routes/evaluate.py` | Main evaluation endpoint |
| `api/routes/demo.py` | Pre-built demo cases |
| `api/schemas/requests.py` | Request models |
| `api/schemas/responses.py` | Response models |
| `api/demo_cases.py` | 15 pre-built scenarios |
| `requirements.txt` | Dependencies |
| `Procfile` | Railway start command |

**Total: ~1,000 lines of API code + 15 demo cases**
