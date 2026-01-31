"""Pre-built demo cases for the interactive banking demo.

Uses fact-based format for toggleable UI controls.
Each fact can be boolean, number, or string for different input types.
"""

DEMO_CASES = [
    # ============== PASS CASES (Should NOT escalate) ==============
    {
        "id": "pep-legal-fees",
        "name": "Foreign PEP - Legal Fees (PASS)",
        "description": "Italian minister paying London law firm. PEP status alone cannot trigger escalation.",
        "category": "PASS",
        "expected_outcome": "pass",
        "key_facts": ["PEP flag Y", "Docs verified", "High tenure"],
        "facts": [
            {"field": "customer.pep_flag", "value": True, "label": "Is PEP"},
            {"field": "customer.type", "value": "IND", "label": "Customer Type"},
            {"field": "customer.residence", "value": "IT", "label": "Residence Country"},
            {"field": "transaction.amount_cad", "value": 265000, "label": "Amount (CAD)"},
            {"field": "transaction.method", "value": "WIRE", "label": "Payment Method"},
            {"field": "screening.match_score", "value": 95, "label": "Match Score"},
            {"field": "screening.list_type", "value": "PEP", "label": "List Type"},
            {"field": "docs.complete", "value": True, "label": "Documentation Complete"},
            {"field": "docs.source_verified", "value": True, "label": "Source of Funds Verified"},
            {"field": "relationship.tenure_years", "value": 22, "label": "Relationship Tenure (Years)"},
        ]
    },
    {
        "id": "high-value-explained",
        "name": "High Value Wire - Documented (PASS)",
        "description": "Large corporate wire with complete documentation. Amount alone cannot trigger.",
        "category": "PASS",
        "expected_outcome": "pass",
        "key_facts": ["$2.5M wire", "Docs complete", "Long-term customer"],
        "facts": [
            {"field": "customer.pep_flag", "value": False, "label": "Is PEP"},
            {"field": "customer.type", "value": "CORP", "label": "Customer Type"},
            {"field": "customer.residence", "value": "CA", "label": "Residence Country"},
            {"field": "transaction.amount_cad", "value": 2500000, "label": "Amount (CAD)"},
            {"field": "transaction.method", "value": "WIRE", "label": "Payment Method"},
            {"field": "screening.match_count", "value": 0, "label": "Screening Matches"},
            {"field": "docs.complete", "value": True, "label": "Documentation Complete"},
            {"field": "docs.source_verified", "value": True, "label": "Source of Funds Verified"},
            {"field": "relationship.tenure_years", "value": 15, "label": "Relationship Tenure (Years)"},
        ]
    },
    {
        "id": "cross-border-routine",
        "name": "Cross-Border - Routine (PASS)",
        "description": "Regular cross-border payments matching historical pattern. Geography alone cannot trigger.",
        "category": "PASS",
        "expected_outcome": "pass",
        "key_facts": ["Hong Kong destination", "Family transfer", "Documented"],
        "facts": [
            {"field": "customer.pep_flag", "value": False, "label": "Is PEP"},
            {"field": "customer.type", "value": "IND", "label": "Customer Type"},
            {"field": "customer.residence", "value": "CA", "label": "Residence Country"},
            {"field": "transaction.amount_cad", "value": 25000, "label": "Amount (CAD)"},
            {"field": "transaction.method", "value": "WIRE", "label": "Payment Method"},
            {"field": "transaction.destination", "value": "HK", "label": "Destination Country"},
            {"field": "screening.match_count", "value": 0, "label": "Screening Matches"},
            {"field": "docs.complete", "value": True, "label": "Documentation Complete"},
            {"field": "docs.source_verified", "value": True, "label": "Source of Funds Verified"},
            {"field": "relationship.tenure_years", "value": 10, "label": "Relationship Tenure (Years)"},
        ]
    },

    # ============== ESCALATE CASES (Should escalate) ==============
    {
        "id": "sanctions-hit",
        "name": "Sanctions Match - OFAC (ESCALATE)",
        "description": "Confirmed OFAC sanctions match. Immediate hard stop required.",
        "category": "ESCALATE",
        "expected_outcome": "escalate",
        "key_facts": ["OFAC SDN match", "Score 98%", "Russian entity"],
        "facts": [
            {"field": "customer.pep_flag", "value": False, "label": "Is PEP"},
            {"field": "customer.type", "value": "IND", "label": "Customer Type"},
            {"field": "customer.residence", "value": "RU", "label": "Residence Country"},
            {"field": "transaction.amount_cad", "value": 680000, "label": "Amount (CAD)"},
            {"field": "transaction.method", "value": "WIRE", "label": "Payment Method"},
            {"field": "transaction.destination", "value": "AE", "label": "Destination Country"},
            {"field": "screening.match_score", "value": 98, "label": "Match Score"},
            {"field": "screening.list_type", "value": "OFAC_SDN", "label": "List Type"},
            {"field": "docs.complete", "value": False, "label": "Documentation Complete"},
            {"field": "docs.source_verified", "value": False, "label": "Source of Funds Verified"},
        ]
    },
    {
        "id": "structuring-pattern",
        "name": "Structuring - Just Under $10K (ESCALATE)",
        "description": "Multiple cash deposits just under $10K threshold. Classic structuring pattern.",
        "category": "ESCALATE",
        "expected_outcome": "escalate",
        "key_facts": ["3x cash deposits", "All ~$9,500", "Same day"],
        "facts": [
            {"field": "customer.pep_flag", "value": False, "label": "Is PEP"},
            {"field": "customer.type", "value": "IND", "label": "Customer Type"},
            {"field": "customer.residence", "value": "CA", "label": "Residence Country"},
            {"field": "transaction.amount_cad", "value": 9500, "label": "Amount (CAD)"},
            {"field": "transaction.method", "value": "CASH", "label": "Payment Method"},
            {"field": "transaction.count", "value": 3, "label": "Transaction Count"},
            {"field": "pattern.structuring", "value": True, "label": "Structuring Pattern Detected"},
            {"field": "pattern.velocity_spike", "value": True, "label": "Velocity Spike"},
            {"field": "docs.complete", "value": True, "label": "Documentation Complete"},
            {"field": "screening.match_count", "value": 0, "label": "Screening Matches"},
        ]
    },
    {
        "id": "shell-company-layering",
        "name": "Shell Company - BVI (ESCALATE)",
        "description": "Funds moving through shell company in tax haven with unclear ownership.",
        "category": "ESCALATE",
        "expected_outcome": "escalate",
        "key_facts": ["BVI entity", "Missing docs", "$1.6M wire"],
        "facts": [
            {"field": "customer.pep_flag", "value": False, "label": "Is PEP"},
            {"field": "customer.type", "value": "CORP", "label": "Customer Type"},
            {"field": "customer.residence", "value": "VG", "label": "Residence Country"},
            {"field": "transaction.amount_cad", "value": 1632000, "label": "Amount (CAD)"},
            {"field": "transaction.method", "value": "WIRE", "label": "Payment Method"},
            {"field": "transaction.destination", "value": "SG", "label": "Destination Country"},
            {"field": "pattern.layering", "value": True, "label": "Layering Pattern"},
            {"field": "docs.complete", "value": False, "label": "Documentation Complete"},
            {"field": "docs.source_verified", "value": False, "label": "Source of Funds Verified"},
            {"field": "docs.ownership_clear", "value": False, "label": "Beneficial Ownership Clear"},
        ]
    },

    # ============== EDGE CASES (Boundary conditions) ==============
    {
        "id": "pep-plus-adverse-media",
        "name": "PEP + Adverse Media (EDGE)",
        "description": "Foreign PEP with adverse media linking to money laundering. Tests corroboration.",
        "category": "EDGE",
        "expected_outcome": "escalate",
        "key_facts": ["PEP flag Y", "Adverse media MLTF", "Missing docs"],
        "facts": [
            {"field": "customer.pep_flag", "value": True, "label": "Is PEP"},
            {"field": "customer.type", "value": "IND", "label": "Customer Type"},
            {"field": "customer.residence", "value": "BR", "label": "Residence Country"},
            {"field": "transaction.amount_cad", "value": 476000, "label": "Amount (CAD)"},
            {"field": "transaction.method", "value": "WIRE", "label": "Payment Method"},
            {"field": "screening.match_score", "value": 92, "label": "Match Score"},
            {"field": "screening.list_type", "value": "ADVERSE_MEDIA", "label": "List Type"},
            {"field": "screening.mltf_linked", "value": True, "label": "Linked to Money Laundering"},
            {"field": "docs.complete", "value": False, "label": "Documentation Complete"},
            {"field": "docs.source_verified", "value": False, "label": "Source of Funds Verified"},
        ]
    },
    {
        "id": "crypto-high-risk-corridor",
        "name": "Crypto to Wire - UAE (EDGE)",
        "description": "Crypto conversion to wire through high-risk jurisdiction.",
        "category": "EDGE",
        "expected_outcome": "escalate",
        "key_facts": ["Crypto source", "UAE destination", "Unverified funds"],
        "facts": [
            {"field": "customer.pep_flag", "value": False, "label": "Is PEP"},
            {"field": "customer.type", "value": "IND", "label": "Customer Type"},
            {"field": "customer.residence", "value": "CA", "label": "Residence Country"},
            {"field": "transaction.amount_cad", "value": 102000, "label": "Amount (CAD)"},
            {"field": "transaction.method", "value": "CRYPTO", "label": "Payment Method"},
            {"field": "transaction.destination", "value": "AE", "label": "Destination Country"},
            {"field": "screening.match_count", "value": 0, "label": "Screening Matches"},
            {"field": "docs.complete", "value": False, "label": "Documentation Complete"},
            {"field": "docs.source_verified", "value": False, "label": "Source of Funds Verified"},
            {"field": "relationship.tenure_years", "value": 2, "label": "Relationship Tenure (Years)"},
        ]
    },
    {
        "id": "velocity-spike",
        "name": "10x Velocity Spike (EDGE)",
        "description": "Long-term customer with sudden 10x increase in transaction volume.",
        "category": "EDGE",
        "expected_outcome": "escalate",
        "key_facts": ["12yr customer", "10x volume spike", "Missing docs"],
        "facts": [
            {"field": "customer.pep_flag", "value": False, "label": "Is PEP"},
            {"field": "customer.type", "value": "CORP", "label": "Customer Type"},
            {"field": "customer.residence", "value": "CA", "label": "Residence Country"},
            {"field": "transaction.amount_cad", "value": 850000, "label": "Amount (CAD)"},
            {"field": "transaction.method", "value": "WIRE", "label": "Payment Method"},
            {"field": "transaction.destination", "value": "CN", "label": "Destination Country"},
            {"field": "pattern.velocity_spike", "value": True, "label": "Velocity Spike"},
            {"field": "pattern.multiplier", "value": 10, "label": "Volume Multiplier"},
            {"field": "docs.complete", "value": False, "label": "Documentation Complete"},
            {"field": "relationship.tenure_years", "value": 12, "label": "Relationship Tenure (Years)"},
        ]
    },
    {
        "id": "beneficial-owner-pep",
        "name": "Hidden PEP Owner (EDGE)",
        "description": "Corporate entity with undisclosed PEP beneficial owner discovered in screening.",
        "category": "EDGE",
        "expected_outcome": "escalate",
        "key_facts": ["Cyprus entity", "Hidden PEP owner", "$2.9M to Swiss bank"],
        "facts": [
            {"field": "customer.pep_flag", "value": False, "label": "Customer PEP Flag"},
            {"field": "customer.type", "value": "CORP", "label": "Customer Type"},
            {"field": "customer.residence", "value": "CY", "label": "Residence Country"},
            {"field": "transaction.amount_cad", "value": 2900000, "label": "Amount (CAD)"},
            {"field": "transaction.method", "value": "WIRE", "label": "Payment Method"},
            {"field": "transaction.destination", "value": "CH", "label": "Destination Country"},
            {"field": "screening.match_score", "value": 88, "label": "Match Score"},
            {"field": "screening.list_type", "value": "PEP", "label": "List Type"},
            {"field": "screening.beneficial_owner_pep", "value": True, "label": "Beneficial Owner is PEP"},
            {"field": "docs.complete", "value": False, "label": "Documentation Complete"},
            {"field": "docs.ownership_clear", "value": False, "label": "Beneficial Ownership Clear"},
        ]
    },
]


def get_demo_cases() -> list[dict]:
    """Return all demo cases for list view."""
    return [{
        "id": c["id"],
        "name": c["name"],
        "description": c["description"],
        "category": c["category"],
        "expected_outcome": c["expected_outcome"],
        "key_facts": c["key_facts"],
        "facts": c["facts"]
    } for c in DEMO_CASES]


def get_demo_case(case_id: str) -> dict | None:
    """Get a specific demo case by ID."""
    for case in DEMO_CASES:
        if case["id"] == case_id:
            return case
    return None


def get_demo_cases_by_category(category: str) -> list[dict]:
    """Get demo cases filtered by category (PASS/ESCALATE/EDGE)."""
    return [c for c in DEMO_CASES if c["category"] == category]
