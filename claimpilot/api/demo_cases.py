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

    # ============== MARINE BOUNDARY CASES ==============
    {
        "id": "marine-edge-nav-boundary",
        "name": "Nav Boundary Edge - NEEDS EVIDENCE",
        "description": "Loss occurred at exact edge of navigation limits. GPS shows position on boundary line.",
        "line_of_business": "marine",
        "policy_id": "CA-ON-MARINE-2024",
        "expected_outcome": "request_info",
        "expected_reason": "Navigation limits boundary requires verification",
        "key_facts": ["GPS position on boundary", "Limits interpretation unclear"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "loss.type", "value": "grounding"},
            {"field": "vessel.within_navigation_limits", "value": "unknown"},
            {"field": "loss.gps_latitude", "value": 43.7942},
            {"field": "loss.gps_longitude", "value": -79.2654},
            {"field": "operator.pcoc_valid", "value": True},
        ],
        "evidence": [
            {"doc_type": "claim_form", "status": "verified"},
            {"doc_type": "gps_records", "status": "verified"},
            {"doc_type": "navigation_chart", "status": "pending"},
        ]
    },
    {
        "id": "marine-deny-nav-exceeded",
        "name": "Nav Limits Exceeded by 2nm - DENY",
        "description": "Vessel grounded 2 nautical miles outside approved cruising area.",
        "line_of_business": "marine",
        "policy_id": "CA-ON-MARINE-2024",
        "expected_outcome": "deny",
        "expected_reason": "Navigation Limits Exclusion (EX-NAV) triggered - 2nm outside boundary",
        "key_facts": ["2nm outside limits", "GPS verified"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "loss.type", "value": "grounding"},
            {"field": "vessel.within_navigation_limits", "value": False},
            {"field": "vessel.distance_outside_limits_nm", "value": 2},
            {"field": "operator.pcoc_valid", "value": True},
        ],
        "evidence": [
            {"doc_type": "claim_form", "status": "verified"},
            {"doc_type": "gps_records", "status": "verified"},
            {"doc_type": "coast_guard_report", "status": "verified"},
        ]
    },
    {
        "id": "marine-edge-pcoc-expired",
        "name": "PCOC Expired 3 Days Ago - NEEDS EVIDENCE",
        "description": "Operator's PCOC expired 3 days before loss. Renewal may have been in process.",
        "line_of_business": "marine",
        "policy_id": "CA-ON-MARINE-2024",
        "expected_outcome": "request_info",
        "expected_reason": "PCOC validity requires documentation of renewal status",
        "key_facts": ["PCOC expired 3 days prior", "Possible renewal pending"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "loss.type", "value": "collision"},
            {"field": "vessel.within_navigation_limits", "value": True},
            {"field": "operator.pcoc_valid", "value": False},
            {"field": "operator.pcoc_expiry_date", "value": "2024-07-12"},
            {"field": "loss.date", "value": "2024-07-15"},
            {"field": "operator.pcoc_days_expired", "value": 3},
        ],
        "evidence": [
            {"doc_type": "claim_form", "status": "verified"},
            {"doc_type": "pcoc_certificate", "status": "pending"},
            {"doc_type": "renewal_application", "status": "pending"},
        ]
    },
    {
        "id": "marine-edge-commercial-mixed",
        "name": "Mixed Use Charter - NEEDS EVIDENCE",
        "description": "Owner occasionally charters vessel. Loss occurred during claimed personal use.",
        "line_of_business": "marine",
        "policy_id": "CA-ON-MARINE-2024",
        "expected_outcome": "request_info",
        "expected_reason": "Commercial Use Exclusion requires verification of use at time of loss",
        "key_facts": ["Known charter history", "Claims personal use at loss"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "loss.type", "value": "storm_damage"},
            {"field": "vessel.within_navigation_limits", "value": True},
            {"field": "operator.pcoc_valid", "value": True},
            {"field": "vessel.commercial_use", "value": "unknown"},
            {"field": "vessel.charter_history", "value": True},
            {"field": "owner.stated_use_at_loss", "value": "personal"},
        ],
        "evidence": [
            {"doc_type": "claim_form", "status": "verified"},
            {"doc_type": "charter_records", "status": "pending"},
            {"doc_type": "marina_log", "status": "pending"},
        ]
    },
    {
        "id": "marine-edge-maintenance-gap",
        "name": "Maintenance Lapsed 45 Days - NEEDS EVIDENCE",
        "description": "Scheduled maintenance was 45 days overdue. Loss may be related to unmaintained systems.",
        "line_of_business": "marine",
        "policy_id": "CA-ON-MARINE-2024",
        "expected_outcome": "request_info",
        "expected_reason": "Maintenance Exclusion requires determination of causal relationship",
        "key_facts": ["45-day maintenance gap", "Possible causal link"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "loss.type", "value": "mechanical_failure"},
            {"field": "vessel.within_navigation_limits", "value": True},
            {"field": "operator.pcoc_valid", "value": True},
            {"field": "vessel.maintenance_current", "value": False},
            {"field": "vessel.days_since_scheduled_maintenance", "value": 45},
            {"field": "loss.system_affected", "value": "engine"},
        ],
        "evidence": [
            {"doc_type": "claim_form", "status": "verified"},
            {"doc_type": "maintenance_records", "status": "verified"},
            {"doc_type": "marine_surveyor_report", "status": "pending"},
        ]
    },
    {
        "id": "marine-edge-ice-offseason",
        "name": "Ice Damage Outside Lay-Up - NEEDS EVIDENCE",
        "description": "Ice damage occurred in early November. Policy lay-up period starts November 15.",
        "line_of_business": "marine",
        "policy_id": "CA-ON-MARINE-2024",
        "expected_outcome": "request_info",
        "expected_reason": "Seasonal coverage boundary requires verification",
        "key_facts": ["Loss Nov 8", "Lay-up starts Nov 15", "Ice conditions unusual"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "loss.type", "value": "ice_damage"},
            {"field": "loss.date", "value": "2024-11-08"},
            {"field": "policy.layup_start_date", "value": "2024-11-15"},
            {"field": "vessel.within_navigation_limits", "value": True},
            {"field": "vessel.in_water", "value": True},
            {"field": "weather.conditions", "value": "early_freeze"},
        ],
        "evidence": [
            {"doc_type": "claim_form", "status": "verified"},
            {"doc_type": "weather_report", "status": "verified"},
            {"doc_type": "marina_haul_out_records", "status": "pending"},
        ]
    },

    # ============== AUTO BOUNDARY CASES ==============
    {
        "id": "auto-edge-bac-threshold",
        "name": "BAC Exactly 0.08 - NEEDS EVIDENCE",
        "description": "Driver BAC measured at exactly 0.08. Breathalyzer calibration and timing may be relevant.",
        "line_of_business": "auto",
        "policy_id": "CA-ON-OAP1-2024",
        "expected_outcome": "request_info",
        "expected_reason": "Impairment Exclusion threshold at exact boundary - requires verification",
        "key_facts": ["BAC exactly 0.08", "Calibration records needed"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "vehicle.use_at_loss", "value": "personal"},
            {"field": "driver.rideshare_app_active", "value": False},
            {"field": "driver.license_status", "value": "valid"},
            {"field": "driver.bac_level", "value": 0.08},
            {"field": "driver.impairment_indicated", "value": "unknown"},
            {"field": "police_report.impaired_charges", "value": False},
        ],
        "evidence": [
            {"doc_type": "police_report", "status": "verified"},
            {"doc_type": "breathalyzer_calibration_cert", "status": "pending"},
            {"doc_type": "toxicology_report", "status": "pending"},
        ]
    },
    {
        "id": "auto-edge-license-same-day",
        "name": "License Expired Same Day - NEEDS EVIDENCE",
        "description": "Driver's license expired on the same day as the loss. Time of expiry vs time of loss unclear.",
        "line_of_business": "auto",
        "policy_id": "CA-ON-OAP1-2024",
        "expected_outcome": "request_info",
        "expected_reason": "License validity at exact time of loss requires verification",
        "key_facts": ["License expired same day", "Time of loss unclear"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "vehicle.use_at_loss", "value": "personal"},
            {"field": "driver.rideshare_app_active", "value": False},
            {"field": "driver.license_status", "value": "unknown"},
            {"field": "driver.license_expiry_date", "value": "2024-08-15"},
            {"field": "loss.date", "value": "2024-08-15"},
            {"field": "loss.time", "value": "unknown"},
            {"field": "driver.bac_level", "value": 0.0},
        ],
        "evidence": [
            {"doc_type": "police_report", "status": "verified"},
            {"doc_type": "mto_driver_abstract", "status": "pending"},
        ]
    },
    {
        "id": "auto-approve-rideshare-inactive",
        "name": "Rideshare Installed but Inactive - APPROVE",
        "description": "Driver has Uber app installed but was not logged in or accepting rides at time of loss.",
        "line_of_business": "auto",
        "policy_id": "CA-ON-OAP1-2024",
        "expected_outcome": "pay",
        "expected_reason": "Commercial Use Exclusion not triggered - app not active during loss",
        "key_facts": ["App installed", "Not logged in", "Personal use confirmed"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "vehicle.use_at_loss", "value": "personal"},
            {"field": "driver.rideshare_app_installed", "value": True},
            {"field": "driver.rideshare_app_active", "value": False},
            {"field": "driver.rideshare_logged_in", "value": False},
            {"field": "driver.license_status", "value": "valid"},
            {"field": "driver.bac_level", "value": 0.0},
        ],
        "evidence": [
            {"doc_type": "police_report", "status": "verified"},
            {"doc_type": "driver_statement", "status": "verified"},
            {"doc_type": "app_activity_records", "status": "verified"},
        ]
    },

    # ============== PROPERTY BOUNDARY CASES ==============
    {
        "id": "property-edge-vacancy-30",
        "name": "Vacant Exactly 30 Days - NEEDS EVIDENCE",
        "description": "Property was vacant for exactly 30 days when loss occurred. Exclusion threshold is 30 days.",
        "line_of_business": "property",
        "policy_id": "CA-ON-HO3-2024",
        "expected_outcome": "request_info",
        "expected_reason": "Vacancy Exclusion at exact 30-day boundary - verification required",
        "key_facts": ["30 days vacant exactly", "Threshold boundary"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "loss.type", "value": "vandalism"},
            {"field": "dwelling.days_vacant", "value": 30},
            {"field": "dwelling.vacancy_start_date", "value": "2024-06-15"},
            {"field": "loss.date", "value": "2024-07-15"},
        ],
        "evidence": [
            {"doc_type": "claim_form", "status": "verified"},
            {"doc_type": "police_report", "status": "verified"},
            {"doc_type": "utility_records", "status": "pending"},
            {"doc_type": "neighbor_statements", "status": "pending"},
        ]
    },
    {
        "id": "property-edge-gradual-sudden",
        "name": "Gradual + Sudden Damage - NEEDS EVIDENCE",
        "description": "Pipe burst (sudden) but evidence of prior slow leak (gradual). Damage attribution unclear.",
        "line_of_business": "property",
        "policy_id": "CA-ON-HO3-2024",
        "expected_outcome": "request_info",
        "expected_reason": "Mixed gradual/sudden causation requires damage attribution",
        "key_facts": ["Pipe burst (sudden)", "Prior slow leak (gradual)", "Damage separation needed"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "loss.type", "value": "water_damage"},
            {"field": "loss.cause", "value": "pipe_burst"},
            {"field": "loss.sudden_event", "value": True},
            {"field": "loss.gradual_damage_present", "value": True},
            {"field": "dwelling.days_vacant", "value": 0},
        ],
        "evidence": [
            {"doc_type": "claim_form", "status": "verified"},
            {"doc_type": "plumber_report", "status": "verified"},
            {"doc_type": "damage_attribution_report", "status": "pending"},
        ]
    },

    # ============== HEALTH BOUNDARY CASES ==============
    {
        "id": "health-edge-preexisting-boundary",
        "name": "Pre-existing at 12-Month Boundary - NEEDS EVIDENCE",
        "description": "Member enrolled exactly 12 months ago. Condition was treated 13 months ago.",
        "line_of_business": "health",
        "policy_id": "CA-ON-GH-2024",
        "expected_outcome": "request_info",
        "expected_reason": "Pre-existing waiting period boundary requires exact enrollment date verification",
        "key_facts": ["12 months coverage exactly", "Condition treated 13 months ago"],
        "facts": [
            {"field": "member.status", "value": "active"},
            {"field": "member.coverage_months", "value": 12},
            {"field": "member.enrollment_date", "value": "2023-08-15"},
            {"field": "condition.preexisting", "value": True},
            {"field": "condition.last_treatment_date", "value": "2023-07-10"},
            {"field": "claim.service_date", "value": "2024-08-15"},
        ],
        "evidence": [
            {"doc_type": "claim_form", "status": "verified"},
            {"doc_type": "enrollment_records", "status": "pending"},
            {"doc_type": "medical_records", "status": "verified"},
        ]
    },
    {
        "id": "health-edge-experimental-approved",
        "name": "Experimental Later Approved - NEEDS EVIDENCE",
        "description": "Treatment was experimental when started but FDA/HC approved during treatment course.",
        "line_of_business": "health",
        "policy_id": "CA-ON-GH-2024",
        "expected_outcome": "request_info",
        "expected_reason": "Experimental Exclusion applicability depends on approval timeline",
        "key_facts": ["Treatment started as experimental", "Approved mid-treatment"],
        "facts": [
            {"field": "member.status", "value": "active"},
            {"field": "treatment.type", "value": "gene_therapy"},
            {"field": "treatment.start_date", "value": "2024-03-01"},
            {"field": "treatment.experimental_at_start", "value": True},
            {"field": "treatment.regulatory_approval_date", "value": "2024-05-15"},
            {"field": "claim.service_date", "value": "2024-06-01"},
        ],
        "evidence": [
            {"doc_type": "claim_form", "status": "verified"},
            {"doc_type": "treatment_records", "status": "verified"},
            {"doc_type": "hc_approval_notice", "status": "pending"},
        ]
    },

    # ============== CGL/E&O BOUNDARY CASES ==============
    {
        "id": "cgl-edge-pollution-secondary",
        "name": "Pollution as Secondary Cause - NEEDS EVIDENCE",
        "description": "Equipment failure caused fire; fire suppression chemicals caused secondary contamination.",
        "line_of_business": "liability",
        "policy_id": "CA-CGL-2024",
        "expected_outcome": "request_info",
        "expected_reason": "Pollution Exclusion applicability unclear when pollution is secondary consequence",
        "key_facts": ["Primary cause: equipment failure", "Secondary: chemical contamination"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "loss.type", "value": "property_damage_tp"},
            {"field": "loss.primary_cause", "value": "equipment_failure"},
            {"field": "loss.pollution_related", "value": True},
            {"field": "loss.pollution_primary", "value": False},
            {"field": "occurrence.during_policy_period", "value": True},
        ],
        "evidence": [
            {"doc_type": "claim_notice", "status": "verified"},
            {"doc_type": "fire_investigation_report", "status": "verified"},
            {"doc_type": "environmental_assessment", "status": "pending"},
        ]
    },
    {
        "id": "eo-edge-prior-acts-known",
        "name": "E&O Prior Acts - Known Circumstance - NEEDS EVIDENCE",
        "description": "Professional error occurred before policy inception. Insured was aware of potential claim.",
        "line_of_business": "liability",
        "policy_id": "CA-EO-2024",
        "expected_outcome": "request_info",
        "expected_reason": "Prior Acts/Known Circumstance Exclusion requires disclosure verification",
        "key_facts": ["Error pre-policy", "Possible knowledge at inception"],
        "facts": [
            {"field": "policy.status", "value": "active"},
            {"field": "policy.inception_date", "value": "2024-01-01"},
            {"field": "loss.type", "value": "professional_liability"},
            {"field": "occurrence.error_date", "value": "2023-11-15"},
            {"field": "occurrence.claim_made_date", "value": "2024-06-01"},
            {"field": "insured.knew_of_circumstances", "value": "unknown"},
            {"field": "occurrence.in_coverage_territory", "value": True},
        ],
        "evidence": [
            {"doc_type": "claim_notice", "status": "verified"},
            {"doc_type": "application_disclosure", "status": "pending"},
            {"doc_type": "client_correspondence", "status": "pending"},
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
