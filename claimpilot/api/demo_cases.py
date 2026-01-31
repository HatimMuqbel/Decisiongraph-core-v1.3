"""Pre-built demo cases for the interactive demo."""

DEMO_CASES = [
    # ============== AUTO CASES ==============
    {
        "id": "auto-approve-standard",
        "name": "Standard Collision - APPROVE",
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
        "name": "Rideshare Delivery - DENY",
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
        "name": "Impaired Driver - DENY",
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
        "name": "Unlicensed Driver - DENY",
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
        "name": "High Value Claim - ESCALATE",
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
        "name": "Kitchen Fire - APPROVE",
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
        "name": "Basement Flood - DENY",
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
        "name": "Vacant Property Theft - DENY",
        "description": "Property vacant for 45 days when theft occurred.",
        "line_of_business": "property",
        "policy_id": "CA-ON-HO3-2024",
        "expected_outcome": "deny",
        "expected_reason": "Vacancy Exclusion (EX-VACANT) triggered - vacant > 30 days",
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
        "name": "Storm Damage - APPROVE",
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
        "name": "Outside Navigation Limits - DENY",
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
        "name": "Formulary Drug - APPROVE",
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
        "name": "Pre-existing Condition - DENY",
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
        "name": "Work Injury - APPROVE",
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
        "name": "Weekend Soccer Injury - DENY",
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
        "name": "Slip and Fall - APPROVE",
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
        "name": "Chemical Spill - DENY",
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
