"""Pre-built demo cases for the interactive banking demo.

Each case is designed to demonstrate different decision outcomes
when key fields are modified by the user.

All cases comply with input.case.schema.json v1.0.0
"""

DEMO_CASES = [
    # ============== PASS CASES (Should NOT escalate) ==============
    {
        "id": "pep-legal-fees",
        "name": "Foreign PEP - Legal Fees",
        "description": "Italian minister paying London law firm. PEP status alone cannot trigger escalation.",
        "category": "PASS",
        "expected_verdict": "PASS_WITH_EDD",
        "key_levers": ["pep_flag", "amt_base_cad", "match_count"],
        "tags": ["PEP", "Wire", "Legal"],
        "input": {
            "header": {
                "system_id": "DEMO-001",
                "export_timestamp": "2026-01-31T12:00:00Z",
                "batch_sequence": 1
            },
            "alert_details": {
                "external_id": "DEMO-PEP-LEGAL-001",
                "work_item_type": "PEP_REVIEW",
                "assigned_queue": "FIU_TIER_1",
                "previous_analyst": None,
                "hit_rule_ids": ["RULE_772", "GEO_009"]
            },
            "customer_record": {
                "SRC_SYS_KEY": "99283-IT-MOR",
                "fullName": "Elena Moretti",
                "c_type": "IND",
                "residence_iso": "IT",
                "onboarding_epoch": 1084147200,
                "last_kyc_refresh": "2025-05-10",
                "pep_flag": "Y",
                "pep_category_code": "FOREIGN",
                "disclosure_docs_received": True
            },
            "transaction_history_slice": [
                {
                    "tx_id": "TX-001",
                    "amt_native": 150000.00,
                    "currency_iso": "GBP",
                    "amt_base_cad": 265000.00,
                    "flow_direction": "OUT",
                    "method": "WIRE",
                    "target_name": "LONDON LEGAL PARTNERS",
                    "status_code": "COMPLETED"
                }
            ],
            "screening_payload": {
                "provider": "WORLD_CHECK",
                "match_count": 1,
                "top_match": {
                    "match_score": 95,
                    "list_type": "PEP",
                    "matched_name": "Elena Moretti",
                    "match_reason": "Minister of Infrastructure - Italy"
                }
            },
            "mitigating_factors": {
                "relationship_tenure_years": 22,
                "documentation_complete": True,
                "source_of_funds_verified": True
            }
        }
    },
    {
        "id": "high-value-explained",
        "name": "High Value Wire - Fully Documented",
        "description": "Large corporate wire with complete documentation. Amount alone cannot trigger.",
        "category": "PASS",
        "expected_verdict": "PASS",
        "key_levers": ["amt_base_cad", "documentation_complete"],
        "tags": ["Corporate", "Wire", "High-Value"],
        "input": {
            "header": {
                "system_id": "DEMO-002",
                "export_timestamp": "2026-01-31T12:00:00Z",
                "batch_sequence": 2
            },
            "alert_details": {
                "external_id": "DEMO-CORP-WIRE-001",
                "work_item_type": "TXN_MONITORING",
                "assigned_queue": "FIU_TIER_1",
                "previous_analyst": None,
                "hit_rule_ids": ["RULE_HIGH_VALUE"]
            },
            "customer_record": {
                "SRC_SYS_KEY": "CORP-8842-CA",
                "fullName": "Maple Industries Inc.",
                "c_type": "CORP",
                "residence_iso": "CA",
                "onboarding_epoch": 1262304000,
                "last_kyc_refresh": "2025-09-15",
                "pep_flag": "N",
                "pep_category_code": None,
                "disclosure_docs_received": True
            },
            "transaction_history_slice": [
                {
                    "tx_id": "TX-002",
                    "amt_native": 2500000.00,
                    "currency_iso": "CAD",
                    "amt_base_cad": 2500000.00,
                    "flow_direction": "OUT",
                    "method": "WIRE",
                    "target_name": "DEUTSCHE MACHINERY GMBH",
                    "status_code": "COMPLETED"
                }
            ],
            "screening_payload": {
                "provider": "WORLD_CHECK",
                "match_count": 0,
                "top_match": None
            },
            "mitigating_factors": {
                "relationship_tenure_years": 15,
                "documentation_complete": True,
                "source_of_funds_verified": True
            }
        }
    },
    {
        "id": "cross-border-routine",
        "name": "Cross-Border - Routine Pattern",
        "description": "Regular cross-border payments matching historical pattern. Geography alone cannot trigger.",
        "category": "PASS",
        "expected_verdict": "PASS",
        "key_levers": ["amt_base_cad", "flow_direction"],
        "tags": ["Cross-Border", "Routine"],
        "input": {
            "header": {
                "system_id": "DEMO-003",
                "export_timestamp": "2026-01-31T12:00:00Z",
                "batch_sequence": 3
            },
            "alert_details": {
                "external_id": "DEMO-XBORDER-001",
                "work_item_type": "TXN_MONITORING",
                "assigned_queue": "FIU_TIER_1",
                "previous_analyst": None,
                "hit_rule_ids": ["GEO_HIGH_RISK"]
            },
            "customer_record": {
                "SRC_SYS_KEY": "IND-7721-CA",
                "fullName": "Michael Chen",
                "c_type": "IND",
                "residence_iso": "CA",
                "onboarding_epoch": 1420070400,
                "last_kyc_refresh": "2025-06-01",
                "pep_flag": "N",
                "pep_category_code": None,
                "disclosure_docs_received": True
            },
            "transaction_history_slice": [
                {
                    "tx_id": "TX-003",
                    "amt_native": 25000.00,
                    "currency_iso": "CAD",
                    "amt_base_cad": 25000.00,
                    "flow_direction": "OUT",
                    "method": "WIRE",
                    "target_name": "CHEN FAMILY TRUST",
                    "benef_country": "HK",
                    "status_code": "COMPLETED"
                }
            ],
            "screening_payload": {
                "provider": "WORLD_CHECK",
                "match_count": 0,
                "top_match": None
            },
            "mitigating_factors": {
                "relationship_tenure_years": 10,
                "documentation_complete": True,
                "source_of_funds_verified": True
            }
        }
    },

    # ============== ESCALATE CASES (Should escalate) ==============
    {
        "id": "sanctions-hit",
        "name": "Sanctions Match - Hard Stop",
        "description": "Confirmed OFAC sanctions match. Immediate escalation required.",
        "category": "ESCALATE",
        "expected_verdict": "HARD_STOP",
        "key_levers": ["list_type", "match_score"],
        "tags": ["Sanctions", "Hard-Stop"],
        "input": {
            "header": {
                "system_id": "DEMO-004",
                "export_timestamp": "2026-01-31T12:00:00Z",
                "batch_sequence": 4
            },
            "alert_details": {
                "external_id": "DEMO-SANCTIONS-001",
                "work_item_type": "SANCTIONS_SCREENING",
                "assigned_queue": "FIU_PRIORITY",
                "previous_analyst": None,
                "hit_rule_ids": ["SANCTIONS_OFAC"]
            },
            "customer_record": {
                "SRC_SYS_KEY": "ENT-9912-RU",
                "fullName": "Viktor Petrov",
                "c_type": "IND",
                "residence_iso": "RU",
                "onboarding_epoch": 1609459200,
                "last_kyc_refresh": "2024-01-15",
                "pep_flag": "N",
                "pep_category_code": None,
                "disclosure_docs_received": True
            },
            "transaction_history_slice": [
                {
                    "tx_id": "TX-004",
                    "amt_native": 500000.00,
                    "currency_iso": "USD",
                    "amt_base_cad": 680000.00,
                    "flow_direction": "OUT",
                    "method": "WIRE",
                    "target_name": "PETROCHEMICAL TRADING LLC",
                    "benef_country": "AE",
                    "status_code": "PENDING"
                }
            ],
            "screening_payload": {
                "provider": "WORLD_CHECK",
                "match_count": 1,
                "top_match": {
                    "match_score": 98,
                    "list_type": "OFAC_SDN",
                    "matched_name": "Viktor PETROV",
                    "match_reason": "OFAC SDN List - Energy Sector"
                }
            },
            "mitigating_factors": {
                "relationship_tenure_years": 3,
                "documentation_complete": False,
                "source_of_funds_verified": False
            }
        }
    },
    {
        "id": "structuring-pattern",
        "name": "Structuring - Multiple Just-Under",
        "description": "Multiple cash deposits just under $10K threshold. Classic structuring pattern.",
        "category": "ESCALATE",
        "expected_verdict": "STR",
        "key_levers": ["amt_base_cad", "method"],
        "tags": ["Structuring", "Cash", "Pattern"],
        "input": {
            "header": {
                "system_id": "DEMO-005",
                "export_timestamp": "2026-01-31T12:00:00Z",
                "batch_sequence": 5
            },
            "alert_details": {
                "external_id": "DEMO-STRUCT-001",
                "work_item_type": "TXN_MONITORING",
                "assigned_queue": "FIU_TIER_2",
                "previous_analyst": None,
                "hit_rule_ids": ["RULE_STRUCTURING", "RULE_VELOCITY"]
            },
            "customer_record": {
                "SRC_SYS_KEY": "IND-4421-CA",
                "fullName": "James Wilson",
                "c_type": "IND",
                "residence_iso": "CA",
                "onboarding_epoch": 1577836800,
                "last_kyc_refresh": "2025-02-01",
                "pep_flag": "N",
                "pep_category_code": None,
                "disclosure_docs_received": True
            },
            "transaction_history_slice": [
                {
                    "tx_id": "TX-005-A",
                    "amt_native": 9500.00,
                    "currency_iso": "CAD",
                    "amt_base_cad": 9500.00,
                    "flow_direction": "IN",
                    "method": "CASH",
                    "target_name": "CASH DEPOSIT",
                    "status_code": "COMPLETED"
                },
                {
                    "tx_id": "TX-005-B",
                    "amt_native": 9400.00,
                    "currency_iso": "CAD",
                    "amt_base_cad": 9400.00,
                    "flow_direction": "IN",
                    "method": "CASH",
                    "target_name": "CASH DEPOSIT",
                    "status_code": "COMPLETED"
                },
                {
                    "tx_id": "TX-005-C",
                    "amt_native": 9600.00,
                    "currency_iso": "CAD",
                    "amt_base_cad": 9600.00,
                    "flow_direction": "IN",
                    "method": "CASH",
                    "target_name": "CASH DEPOSIT",
                    "status_code": "COMPLETED"
                }
            ],
            "screening_payload": {
                "provider": "WORLD_CHECK",
                "match_count": 0,
                "top_match": None
            },
            "suspicion_evidence": {
                "has_intent": True,
                "has_deception": True,
                "has_sustained_pattern": True
            },
            "indicators": [
                {"code": "FINTRAC_A1", "description": "Transactions just below reporting threshold"},
                {"code": "FINTRAC_A3", "description": "Multiple transactions in short period"}
            ],
            "typology_maturity": "CONFIRMED"
        }
    },
    {
        "id": "shell-company-layering",
        "name": "Shell Company Layering",
        "description": "Funds moving through multiple shell companies in tax havens.",
        "category": "ESCALATE",
        "expected_verdict": "STR",
        "key_levers": ["c_type", "residence_iso", "disclosure_docs_received"],
        "tags": ["Layering", "Shell", "Corporate"],
        "input": {
            "header": {
                "system_id": "DEMO-006",
                "export_timestamp": "2026-01-31T12:00:00Z",
                "batch_sequence": 6
            },
            "alert_details": {
                "external_id": "DEMO-LAYER-001",
                "work_item_type": "ENHANCED_MONITORING",
                "assigned_queue": "FIU_TIER_2",
                "previous_analyst": None,
                "hit_rule_ids": ["RULE_LAYERING", "RULE_SHELL"]
            },
            "customer_record": {
                "SRC_SYS_KEY": "CORP-1192-VG",
                "fullName": "Global Ventures Holdings Ltd",
                "c_type": "CORP",
                "residence_iso": "VG",
                "onboarding_epoch": 1640995200,
                "last_kyc_refresh": "2025-01-10",
                "pep_flag": "N",
                "pep_category_code": None,
                "disclosure_docs_received": False
            },
            "transaction_history_slice": [
                {
                    "tx_id": "TX-006",
                    "amt_native": 1200000.00,
                    "currency_iso": "USD",
                    "amt_base_cad": 1632000.00,
                    "flow_direction": "OUT",
                    "method": "WIRE",
                    "target_name": "PACIFIC RIM INVESTMENTS LTD",
                    "benef_country": "SG",
                    "status_code": "PENDING"
                }
            ],
            "screening_payload": {
                "provider": "WORLD_CHECK",
                "match_count": 0,
                "top_match": None
            },
            "suspicion_evidence": {
                "has_intent": True,
                "has_deception": True,
                "has_sustained_pattern": False
            },
            "indicators": [
                {"code": "FINTRAC_B2", "description": "Complex corporate structure"},
                {"code": "FINTRAC_B5", "description": "Beneficial ownership unclear"}
            ],
            "typology_maturity": "ESTABLISHED"
        }
    },

    # ============== EDGE CASES (Boundary conditions) ==============
    {
        "id": "pep-plus-adverse-media",
        "name": "PEP + Adverse Media - Edge",
        "description": "Foreign PEP with recent adverse media. Tests corroboration requirements.",
        "category": "EDGE",
        "expected_verdict": "ESCALATE",
        "key_levers": ["pep_flag", "mltf_linked", "documentation_complete"],
        "tags": ["PEP", "Adverse-Media", "Edge"],
        "input": {
            "header": {
                "system_id": "DEMO-007",
                "export_timestamp": "2026-01-31T12:00:00Z",
                "batch_sequence": 7
            },
            "alert_details": {
                "external_id": "DEMO-PEP-ADVERSE-001",
                "work_item_type": "PEP_REVIEW",
                "assigned_queue": "FIU_TIER_2",
                "previous_analyst": None,
                "hit_rule_ids": ["RULE_772", "RULE_ADVERSE"]
            },
            "customer_record": {
                "SRC_SYS_KEY": "99921-BR-SIL",
                "fullName": "Ricardo Silva",
                "c_type": "IND",
                "residence_iso": "BR",
                "onboarding_epoch": 1483228800,
                "last_kyc_refresh": "2024-08-01",
                "pep_flag": "Y",
                "pep_category_code": "FOREIGN",
                "disclosure_docs_received": True
            },
            "transaction_history_slice": [
                {
                    "tx_id": "TX-007",
                    "amt_native": 350000.00,
                    "currency_iso": "USD",
                    "amt_base_cad": 476000.00,
                    "flow_direction": "OUT",
                    "method": "WIRE",
                    "target_name": "SILVA FAMILY OFFICE - MIAMI",
                    "benef_country": "US",
                    "status_code": "COMPLETED"
                }
            ],
            "screening_payload": {
                "provider": "WORLD_CHECK",
                "match_count": 1,
                "top_match": {
                    "match_score": 92,
                    "list_type": "ADVERSE_MEDIA",
                    "matched_name": "Ricardo Silva",
                    "match_reason": "Named in Operation Car Wash documents"
                },
                "adverse_media": {
                    "found": True,
                    "mltf_linked": True,
                    "categories": ["CORRUPTION", "MONEY_LAUNDERING"]
                }
            },
            "mitigating_factors": {
                "relationship_tenure_years": 8,
                "documentation_complete": False,
                "source_of_funds_verified": False
            }
        }
    },
    {
        "id": "crypto-high-risk-corridor",
        "name": "Crypto - High Risk Corridor",
        "description": "Crypto conversion to wire through high-risk jurisdiction.",
        "category": "EDGE",
        "expected_verdict": "ESCALATE",
        "key_levers": ["method", "benef_country", "source_of_funds_verified"],
        "tags": ["Crypto", "High-Risk", "Edge"],
        "input": {
            "header": {
                "system_id": "DEMO-008",
                "export_timestamp": "2026-01-31T12:00:00Z",
                "batch_sequence": 8
            },
            "alert_details": {
                "external_id": "DEMO-CRYPTO-001",
                "work_item_type": "TXN_MONITORING",
                "assigned_queue": "FIU_TIER_2",
                "previous_analyst": None,
                "hit_rule_ids": ["RULE_CRYPTO", "GEO_HIGH_RISK"]
            },
            "customer_record": {
                "SRC_SYS_KEY": "IND-8821-CA",
                "fullName": "Alex Thompson",
                "c_type": "IND",
                "residence_iso": "CA",
                "onboarding_epoch": 1609459200,
                "last_kyc_refresh": "2025-03-01",
                "pep_flag": "N",
                "pep_category_code": None,
                "disclosure_docs_received": True
            },
            "transaction_history_slice": [
                {
                    "tx_id": "TX-008-A",
                    "amt_native": 75000.00,
                    "currency_iso": "USD",
                    "amt_base_cad": 102000.00,
                    "flow_direction": "IN",
                    "method": "CRYPTO",
                    "target_name": "EXTERNAL WALLET",
                    "status_code": "COMPLETED"
                },
                {
                    "tx_id": "TX-008-B",
                    "amt_native": 74000.00,
                    "currency_iso": "CAD",
                    "amt_base_cad": 74000.00,
                    "flow_direction": "OUT",
                    "method": "WIRE",
                    "target_name": "TRADING COMPANY FZE",
                    "benef_country": "AE",
                    "status_code": "PENDING"
                }
            ],
            "screening_payload": {
                "provider": "WORLD_CHECK",
                "match_count": 0,
                "top_match": None
            },
            "mitigating_factors": {
                "relationship_tenure_years": 2,
                "documentation_complete": False,
                "source_of_funds_verified": False
            }
        }
    },
    {
        "id": "velocity-spike",
        "name": "Velocity Spike - Sudden Change",
        "description": "Long-term customer with sudden 10x increase in transaction volume.",
        "category": "EDGE",
        "expected_verdict": "ESCALATE",
        "key_levers": ["amt_base_cad", "documentation_complete"],
        "tags": ["Velocity", "Behavioral", "Edge"],
        "input": {
            "header": {
                "system_id": "DEMO-009",
                "export_timestamp": "2026-01-31T12:00:00Z",
                "batch_sequence": 9
            },
            "alert_details": {
                "external_id": "DEMO-VELOCITY-001",
                "work_item_type": "TXN_MONITORING",
                "assigned_queue": "FIU_TIER_1",
                "previous_analyst": None,
                "hit_rule_ids": ["RULE_VELOCITY_SPIKE"]
            },
            "customer_record": {
                "SRC_SYS_KEY": "CORP-5543-CA",
                "fullName": "Northern Supplies Ltd",
                "c_type": "CORP",
                "residence_iso": "CA",
                "onboarding_epoch": 1325376000,
                "last_kyc_refresh": "2025-04-15",
                "pep_flag": "N",
                "pep_category_code": None,
                "disclosure_docs_received": True
            },
            "transaction_history_slice": [
                {
                    "tx_id": "TX-009",
                    "amt_native": 850000.00,
                    "currency_iso": "CAD",
                    "amt_base_cad": 850000.00,
                    "flow_direction": "OUT",
                    "method": "WIRE",
                    "target_name": "SHENZHEN ELECTRONICS CO",
                    "benef_country": "CN",
                    "status_code": "COMPLETED"
                }
            ],
            "screening_payload": {
                "provider": "WORLD_CHECK",
                "match_count": 0,
                "top_match": None
            },
            "mitigating_factors": {
                "relationship_tenure_years": 12,
                "documentation_complete": False,
                "source_of_funds_verified": False
            }
        }
    },
    {
        "id": "beneficial-owner-pep",
        "name": "Corporate - Hidden PEP Owner",
        "description": "Corporate entity with undisclosed PEP beneficial owner.",
        "category": "EDGE",
        "expected_verdict": "ESCALATE",
        "key_levers": ["pep_flag", "disclosure_docs_received", "match_score"],
        "tags": ["Corporate", "PEP", "Ownership"],
        "input": {
            "header": {
                "system_id": "DEMO-010",
                "export_timestamp": "2026-01-31T12:00:00Z",
                "batch_sequence": 10
            },
            "alert_details": {
                "external_id": "DEMO-HIDDEN-PEP-001",
                "work_item_type": "PERIODIC_REVIEW",
                "assigned_queue": "FIU_TIER_2",
                "previous_analyst": None,
                "hit_rule_ids": ["RULE_HIDDEN_PEP", "RULE_OWNERSHIP"]
            },
            "customer_record": {
                "SRC_SYS_KEY": "CORP-7721-CY",
                "fullName": "Mediterranean Holdings Ltd",
                "c_type": "CORP",
                "residence_iso": "CY",
                "onboarding_epoch": 1546300800,
                "last_kyc_refresh": "2024-12-01",
                "pep_flag": "N",
                "pep_category_code": None,
                "disclosure_docs_received": False
            },
            "transaction_history_slice": [
                {
                    "tx_id": "TX-010",
                    "amt_native": 2000000.00,
                    "currency_iso": "EUR",
                    "amt_base_cad": 2900000.00,
                    "flow_direction": "OUT",
                    "method": "WIRE",
                    "target_name": "SWISS PRIVATE BANK AG",
                    "benef_country": "CH",
                    "status_code": "PENDING"
                }
            ],
            "screening_payload": {
                "provider": "WORLD_CHECK",
                "match_count": 1,
                "top_match": {
                    "match_score": 88,
                    "list_type": "PEP",
                    "matched_name": "Maria Konstantinos",
                    "match_reason": "Former Minister of Finance - Greece (Beneficial Owner)"
                }
            },
            "mitigating_factors": {
                "relationship_tenure_years": 5,
                "documentation_complete": False,
                "source_of_funds_verified": False
            }
        }
    }
]


def get_demo_cases() -> list[dict]:
    """Return all demo cases (without full input for list view)."""
    return [{
        "id": c["id"],
        "name": c["name"],
        "description": c["description"],
        "category": c["category"],
        "expected_verdict": c["expected_verdict"],
        "key_levers": c["key_levers"],
        "tags": c["tags"]
    } for c in DEMO_CASES]


def get_demo_case(case_id: str) -> dict | None:
    """Get a specific demo case by ID (with full input)."""
    for case in DEMO_CASES:
        if case["id"] == case_id:
            return case
    return None


def get_demo_cases_by_category(category: str) -> list[dict]:
    """Get demo cases filtered by category (PASS/ESCALATE/EDGE)."""
    return [c for c in DEMO_CASES if c["category"] == category]
