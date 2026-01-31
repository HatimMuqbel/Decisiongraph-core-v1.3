"""
Standardized Evidence Matrix

Defines what evidence is required to resolve each uncertain exclusion.
Turns uncertainty into structured next steps.
"""

EVIDENCE_MATRIX = {
    # Property exclusions
    "EX-WEAR": {
        "name": "Wear and Tear",
        "purpose": "Determine whether damage resulted from gradual deterioration rather than a sudden insured event.",
        "evidence_items": [
            "Maintenance and service records (past 12-24 months)",
            "Inspection reports",
            "Contractor or adjuster assessment",
            "Photographs documenting pre-loss condition"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },
    "EX-INTENT": {
        "name": "Intentional Loss",
        "purpose": "Determine whether the loss was deliberately caused.",
        "evidence_items": [
            "Fire marshal or investigator report",
            "Police incident report (if applicable)",
            "Witness statements",
            "Cause-and-origin analysis"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },
    "EX-VACANT": {
        "name": "Vacancy",
        "purpose": "Determine occupancy status at time of loss.",
        "evidence_items": [
            "Utility usage records",
            "Lease or occupancy documentation",
            "Sworn statement of insured",
            "Mail forwarding records"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },
    "EX-NEGLECT": {
        "name": "Neglect",
        "purpose": "Determine whether failure to mitigate or maintain caused or worsened the loss.",
        "evidence_items": [
            "Maintenance history",
            "Prior damage reports",
            "Adjuster observations",
            "Photographs of property condition"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },
    "EX-FLOOD": {
        "name": "Flood",
        "purpose": "Determine whether water damage was caused by flooding vs. covered peril.",
        "evidence_items": [
            "Weather data for loss date",
            "Flood zone maps",
            "Water damage assessment",
            "Photos showing water source/direction"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },
    "EX-QUAKE": {
        "name": "Earthquake",
        "purpose": "Determine whether damage was caused by earth movement.",
        "evidence_items": [
            "Seismic data for loss date/location",
            "Structural assessment",
            "Geological survey",
            "Engineer's report"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },
    "EX-COMM": {
        "name": "Commercial Use",
        "purpose": "Determine whether insured property was used for commercial purposes.",
        "evidence_items": [
            "Business registration records",
            "Invoicing or payment evidence",
            "Usage logs or advertisements",
            "Sworn statement of insured"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },

    # Auto exclusions
    "EX-IMPAIR": {
        "name": "Impairment",
        "purpose": "Determine whether driver was impaired at time of loss.",
        "evidence_items": [
            "Toxicology report",
            "Police report with BAC results",
            "Witness statements",
            "Hospital records (if applicable)"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },
    "EX-RIDESHARE": {
        "name": "Rideshare/Commercial Use",
        "purpose": "Determine whether vehicle was being used for rideshare or commercial purposes.",
        "evidence_items": [
            "App activity logs from rideshare platforms",
            "Trip records",
            "Driver's statement",
            "Passenger statements"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },
    "EX-RACING": {
        "name": "Racing/Speed Contest",
        "purpose": "Determine whether vehicle was involved in racing or speed contest.",
        "evidence_items": [
            "Witness statements",
            "Event records",
            "Vehicle telemetry data",
            "Police report"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },
    "EX-UNLICENSED": {
        "name": "Unlicensed Driver",
        "purpose": "Determine driver's license status at time of loss.",
        "evidence_items": [
            "Driver's license verification",
            "DMV records",
            "Police report"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },

    # Health/Workers Comp exclusions
    "EX-PREEXIST": {
        "name": "Pre-existing Condition",
        "purpose": "Determine whether condition existed prior to coverage effective date.",
        "evidence_items": [
            "Prior medical records",
            "Intake forms",
            "Physician statements",
            "Insurance application"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },
    "EX-EXPERIMENTAL": {
        "name": "Experimental Treatment",
        "purpose": "Determine whether treatment is considered experimental or investigational.",
        "evidence_items": [
            "Treatment protocols",
            "Clinical guidelines",
            "Medical literature",
            "Physician justification"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },
    "EX-INTOX": {
        "name": "Intoxication",
        "purpose": "Determine whether injury occurred while intoxicated.",
        "evidence_items": [
            "BAC test results",
            "Police report",
            "Hospital toxicology screen",
            "Witness statements"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },
    "EX-FELONY": {
        "name": "Felony Commission",
        "purpose": "Determine whether injury occurred during commission of a felony.",
        "evidence_items": [
            "Court records",
            "Police report",
            "Arrest records",
            "Witness statements"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },
    "EX-HORSEPLAY": {
        "name": "Horseplay/Misconduct",
        "purpose": "Determine whether injury resulted from horseplay or willful misconduct.",
        "evidence_items": [
            "Witness statements",
            "Incident report",
            "Supervisor statements",
            "Video footage (if available)"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },

    # Liability exclusions
    "EX-EXPECTED": {
        "name": "Expected/Intended Injury",
        "purpose": "Determine whether bodily injury or property damage was expected or intended.",
        "evidence_items": [
            "Witness statements",
            "Police report",
            "Incident documentation",
            "Prior history between parties"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },
    "EX-POLLUTION": {
        "name": "Pollution",
        "purpose": "Determine whether damage was caused by pollution discharge.",
        "evidence_items": [
            "Environmental assessment",
            "Discharge records",
            "Regulatory citations",
            "Testing results"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },
    "EX-FRAUD": {
        "name": "Fraud/Misrepresentation",
        "purpose": "Determine whether claim involves fraud or material misrepresentation.",
        "evidence_items": [
            "SIU investigation report",
            "Financial records",
            "Statement analysis",
            "Background check results"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },
    "EX-MISREP": {
        "name": "Material Misrepresentation",
        "purpose": "Determine whether application contained material misrepresentations.",
        "evidence_items": [
            "Original application",
            "Underwriting notes",
            "Verification documents",
            "Comparison analysis"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },

    # Travel exclusions
    "EX-ADVISORY": {
        "name": "Travel Advisory",
        "purpose": "Determine whether travel was to a location under government advisory.",
        "evidence_items": [
            "Travel advisory records for dates",
            "Itinerary documentation",
            "Booking records"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },
    "EX-EXTREME": {
        "name": "Extreme Sports",
        "purpose": "Determine whether injury occurred during excluded extreme sports activity.",
        "evidence_items": [
            "Activity records",
            "Witness statements",
            "Medical records describing circumstances",
            "Equipment rental records"
        ],
        "resolution_if_applies": "Claim Denied",
        "resolution_if_not_applies": "Exclusion Ruled Out"
    },
}


def get_evidence_requirement(exclusion_code: str) -> dict | None:
    """Get evidence requirement for an exclusion code."""
    return EVIDENCE_MATRIX.get(exclusion_code)


def get_all_evidence_requirements() -> dict:
    """Get the full evidence matrix."""
    return EVIDENCE_MATRIX
