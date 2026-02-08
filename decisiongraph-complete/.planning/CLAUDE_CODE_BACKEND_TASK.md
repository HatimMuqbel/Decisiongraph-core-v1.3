# CLAUDE CODE TASK: DecisionGraph Backend Pipeline Fix

## CONTEXT

DecisionGraph is a deterministic AML/ATF decision engine for Canadian banks. 
The website (decisiongraph.pro) has a "Build Your Own Case" form with 28 fields.
The backend generates seed precedents and matches incoming cases against them.

**THE PROBLEM:** Seeds only populate 8 of 28 website fields, and use different 
names than the similarity scorer expects. Result: 0 scored matches, 50% default 
confidence, empty precedent section. Also: seeds use insurance vocabulary 
(pay/deny/escalate) instead of banking vocabulary (ALLOW/EDD/BLOCK).

**THE FIX:** Work backwards from the website. Every field the user can fill in 
must have corresponding data in seeds, using the same names throughout the pipeline.

## FILES YOU NEED TO KNOW

```
decisiongraph-complete/
├── src/decisiongraph/
│   ├── aml_seed_generator.py      ← REWRITE: generates banking seeds
│   ├── judgment.py                ← MODIFY: JudgmentPayload validation
│   ├── aml_fingerprint.py         ← READ: fingerprint schema definitions
│   └── precedent_registry.py      ← MODIFY: find_by_exclusion_codes rename
│
├── service/
│   ├── main.py                    ← MODIFY: outcome mapping (L942-955), 
│   │                                 similarity scoring (L1424-1966),
│   │                                 name lookups throughout
│   ├── template_loader.py         ← MODIFY: add website→internal name map
│   └── routers/report/
│       ├── render_md.py           ← MODIFY: evidence table display names
│       └── pipeline.py            ← READ: rendering pipeline
│
└── website frontend              ← READ ONLY: extract field names/values
    (find the BYOC form component)
```

---

## TASK 1: CREATE THE FIELD REGISTRY

Create `src/decisiongraph/banking_field_registry.py`

This is the SINGLE SOURCE OF TRUTH. Every layer reads from it.

```python
"""
Banking Field Registry — Single source of truth for all field names,
types, values, and display labels across the entire pipeline.

Website → API → Seeds → Fingerprint → Scorer → Evidence Table
All use THIS registry. No hardcoded field lists anywhere else.
"""

BANKING_FIELDS = {
    # === CUSTOMER ===
    "customer.type": {
        "website_name": "customer_type",
        "display_name": "Customer entity type",
        "type": "enum",
        "values": ["individual", "sole_proprietor", "corporation", 
                   "partnership", "trust", "npo"],
        "website_values": {
            "Individual": "individual",
            "Sole Proprietor": "sole_proprietor",
            "Corporation": "corporation",
            "Partnership": "partnership",
            "Trust": "trust",
            "Non-Profit": "npo",
        },
        "fingerprint": True,
        "required": True,
    },
    "customer.relationship_length": {
        "website_name": "relationship_length",
        "display_name": "Customer relationship duration",
        "type": "enum",
        "values": ["new", "established", "long_term"],
        "website_values": {
            "New (< 6 months)": "new",
            "Established (6mo - 2yr)": "established",
            "Long-term (2yr+)": "long_term",
        },
        "fingerprint": True,
        "required": True,
    },

    # === RISK PROFILE ===
    "customer.pep": {
        "website_name": "pep",
        "display_name": "Politically Exposed Person status",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "customer.high_risk_jurisdiction": {
        "website_name": "high_risk_jurisdiction",
        "display_name": "High-risk jurisdiction indicator",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "customer.high_risk_industry": {
        "website_name": "high_risk_industry",
        "display_name": "High-risk industry indicator",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "customer.cash_intensive": {
        "website_name": "cash_intensive_business",
        "display_name": "Cash-intensive business indicator",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },

    # === TRANSACTION ===
    "txn.type": {
        "website_name": "transaction_type",
        "display_name": "Transaction type",
        "type": "enum",
        "values": ["wire", "cash_deposit", "cash_withdrawal", "cheque",
                   "eft", "crypto_purchase", "crypto_sale", "international_transfer"],
        "website_values": {
            "Wire Transfer": "wire",
            "Cash Deposit": "cash_deposit",
            "Cash Withdrawal": "cash_withdrawal",
            "Check": "cheque",
            "ACH/EFT": "eft",
            "Crypto Purchase": "crypto_purchase",
            "Crypto Sale": "crypto_sale",
            "International Transfer": "international_transfer",
        },
        "fingerprint": True,
        "required": True,
    },
    "txn.amount_band": {
        "website_name": "amount",
        "display_name": "Transaction amount range",
        "type": "enum",
        "values": ["under_3k", "3k_10k", "10k_25k", "25k_100k", "over_100k"],
        "website_values": {
            "Under $3K": "under_3k",
            "$3K - $10K": "3k_10k",
            "$10K - $25K": "10k_25k",
            "$25K - $100K": "25k_100k",
            "$100K+": "over_100k",
        },
        "fingerprint": True,
        "required": True,
    },
    "txn.cross_border": {
        "website_name": "cross_border",
        "display_name": "Cross-border transaction indicator",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "txn.destination_country_risk": {
        "website_name": "destination_country",
        "display_name": "Destination country risk level",
        "type": "enum",
        "values": ["low", "medium", "high"],
        "website_values": {
            "Canada": "low",
            "USA": "low",
            "UK": "low",
            "High-Risk Country": "high",
        },
        "fingerprint": True,
        "required": True,
    },
    "txn.round_amount": {
        "website_name": "round_amount",
        "display_name": "Round amount indicator",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "txn.just_below_threshold": {
        "website_name": "just_below_10k",
        "display_name": "Transaction just below reporting threshold",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "txn.multiple_same_day": {
        "website_name": "multiple_same_day_txns",
        "display_name": "Multiple same-day transactions",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "txn.pattern_matches_profile": {
        "website_name": "pattern_matches_profile",
        "display_name": "Transaction pattern consistent with customer profile",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "txn.source_of_funds_clear": {
        "website_name": "source_of_funds_clear",
        "display_name": "Source of funds clarity",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "txn.stated_purpose": {
        "website_name": "stated_purpose",
        "display_name": "Stated transaction purpose",
        "type": "enum",
        "values": ["personal", "business", "investment", "gift", "unclear"],
        "website_values": {
            "Personal": "personal",
            "Business": "business",
            "Investment": "investment",
            "Gift": "gift",
            "Unclear": "unclear",
        },
        "fingerprint": True,
        "required": True,
    },

    # === RED FLAGS ===
    "flag.structuring": {
        "website_name": "structuring_suspected",
        "display_name": "Structuring indicators present",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "flag.rapid_movement": {
        "website_name": "rapid_movement",
        "display_name": "Rapid fund movement indicator",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "flag.layering": {
        "website_name": "layering_indicators",
        "display_name": "Layering indicators present",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "flag.unusual_for_profile": {
        "website_name": "unusual_for_profile",
        "display_name": "Activity unusual for customer profile",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "flag.third_party": {
        "website_name": "third_party_payment",
        "display_name": "Third-party payment indicator",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "flag.shell_company": {
        "website_name": "shell_company_indicators",
        "display_name": "Shell company indicators present",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },

    # === SCREENING ===
    "screening.sanctions_match": {
        "website_name": "sanctions_match",
        "display_name": "Sanctions screening match",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "screening.pep_match": {
        "website_name": "pep_match",
        "display_name": "PEP screening match",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "screening.adverse_media": {
        "website_name": "adverse_media",
        "display_name": "Adverse media indicator",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
    "prior.sars_filed": {
        "website_name": "prior_sars_filed",
        "display_name": "Prior Suspicious Activity Reports filed",
        "type": "enum",
        "values": [0, 1, 2, 3, 4],
        "website_values": {
            "0": 0, "1": 1, "2": 2, "3": 3, "4+": 4,
        },
        "fingerprint": True,
        "required": True,
    },
    "prior.account_closures": {
        "website_name": "previous_account_closures",
        "display_name": "Previous account closures on record",
        "type": "boolean",
        "fingerprint": True,
        "required": True,
    },
}

# ─── DERIVED HELPERS ───

def get_website_to_internal_map():
    """Returns {website_field_name: internal_canonical_name}"""
    return {
        field["website_name"]: canonical_name
        for canonical_name, field in BANKING_FIELDS.items()
    }

def get_internal_to_display_map():
    """Returns {internal_canonical_name: human_readable_display_name}"""
    return {
        canonical_name: field["display_name"]
        for canonical_name, field in BANKING_FIELDS.items()
    }

def get_fingerprint_fields():
    """Returns list of canonical field names used for fingerprint hashing"""
    return [
        name for name, field in BANKING_FIELDS.items()
        if field.get("fingerprint", False)
    ]

def normalize_website_value(canonical_name, website_value):
    """Converts website display value to internal normalized value"""
    field = BANKING_FIELDS.get(canonical_name)
    if not field:
        raise ValueError(f"Unknown field: {canonical_name}")
    if field["type"] == "boolean":
        if isinstance(website_value, bool):
            return website_value
        return str(website_value).lower() in ("yes", "true", "1")
    if "website_values" in field:
        normalized = field["website_values"].get(website_value)
        if normalized is not None:
            return normalized
    return website_value

def validate_field_value(canonical_name, value):
    """Validates a value against the registry. Returns True or raises."""
    field = BANKING_FIELDS.get(canonical_name)
    if not field:
        raise ValueError(f"Unknown field: {canonical_name}")
    if field["type"] == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{canonical_name}: expected bool, got {type(value)}")
    elif field["type"] == "enum":
        if value not in field["values"]:
            raise ValueError(
                f"{canonical_name}: '{value}' not in {field['values']}"
            )
    return True
```

**IMPORTANT:** Before creating this file, first find the website frontend code 
and VERIFY the field names and values match exactly. If the frontend uses 
different names than listed above, UPDATE the registry to match the frontend.

---

## TASK 2: REBUILD SEED GENERATOR

Rewrite `src/decisiongraph/aml_seed_generator.py` to:

### 2.1 Use ALL 28 Fields from Registry

Every seed must populate ALL 28 fields from `BANKING_FIELDS`. No field left empty.
Import field names and allowed values from the registry — no hardcoded field lists.

### 2.2 Three-Field Outcomes (not pay/deny/escalate)

Every seed outcome must have three fields:

```python
# WRONG (current — insurance vocabulary):
outcome_code: "pay"  # or "deny" or "escalate"

# RIGHT (banking vocabulary):
outcome = {
    "disposition": "ALLOW" | "EDD" | "BLOCK",
    "disposition_basis": "MANDATORY" | "DISCRETIONARY",
    "reporting": "NO_REPORT" | "FILE_STR" | "FILE_LCTR" | "FILE_TPR" | "PENDING_EDD",
}
```

Rules for outcomes:
- BLOCK + MANDATORY = sanctions match, court order (SEMA/UNA/Criminal Code s.83.08)
- BLOCK + DISCRETIONARY = bank risk appetite (exit review, pattern)
- EDD + DISCRETIONARY = investigation needed (structuring, PEP, adverse media)
- ALLOW + DISCRETIONARY = cleared after review
- FILE_STR = reasonable grounds to suspect (PCMLTFA s. 7)
- FILE_LCTR = cash ≥ $10,000 (PCMLTFA s. 12)
- PENDING_EDD = reporting not yet determined (awaiting investigation)

### 2.3 Generate from Website's Expected Outcomes

The website shows 20 expected outcome scenarios. Each one becomes a seed template.
Generate 50-100 variations per scenario = 1,000-2,000 total seeds.

Here are the 20 scenarios with their outcomes:

```python
SCENARIOS = [
    # ─── APPROVE scenarios ───
    {
        "name": "clean_known_customer",
        "description": "Known customer, normal pattern, under $10K",
        "base_facts": {
            "customer.type": "individual",
            "customer.relationship_length": "long_term",
            "txn.amount_band": "3k_10k",
            "txn.cross_border": False,
            "txn.pattern_matches_profile": True,
            "txn.source_of_funds_clear": True,
            "flag.structuring": False,
            "screening.sanctions_match": False,
            "screening.adverse_media": False,
            "prior.sars_filed": 0,
        },
        "outcome": {
            "disposition": "ALLOW",
            "disposition_basis": "DISCRETIONARY",
            "reporting": "NO_REPORT",
        },
        "weight": 0.25,  # 25% of total seeds — most common case
    },
    {
        "name": "new_customer_large_clear",
        "description": "New customer, >$10K, source clear",
        "base_facts": {
            "customer.type": "individual",
            "customer.relationship_length": "new",
            "txn.amount_band": "10k_25k",
            "txn.source_of_funds_clear": True,
            "txn.cross_border": False,
            "flag.structuring": False,
            "screening.sanctions_match": False,
        },
        "outcome": {
            "disposition": "ALLOW",
            "disposition_basis": "DISCRETIONARY",
            "reporting": "FILE_LCTR",  # cash over $10K
        },
        "weight": 0.08,
    },

    # ─── INVESTIGATE scenarios ───
    {
        "name": "structuring_suspected",
        "description": "Just below $10K, multiple same day",
        "base_facts": {
            "txn.amount_band": "3k_10k",
            "txn.just_below_threshold": True,
            "txn.multiple_same_day": True,
            "flag.structuring": True,
            "txn.round_amount": True,
        },
        "outcome": {
            "disposition": "EDD",
            "disposition_basis": "DISCRETIONARY",
            "reporting": "PENDING_EDD",
        },
        "weight": 0.06,
    },
    {
        "name": "round_amount_reporting",
        "description": "Round amount in reporting range",
        "base_facts": {
            "txn.amount_band": "10k_25k",
            "txn.round_amount": True,
            "txn.pattern_matches_profile": False,
        },
        "outcome": {
            "disposition": "EDD",
            "disposition_basis": "DISCRETIONARY",
            "reporting": "PENDING_EDD",
        },
        "weight": 0.04,
    },
    {
        "name": "source_of_funds_unclear",
        "description": "Source of funds unclear",
        "base_facts": {
            "txn.source_of_funds_clear": False,
            "txn.stated_purpose": "unclear",
        },
        "outcome": {
            "disposition": "EDD",
            "disposition_basis": "DISCRETIONARY",
            "reporting": "PENDING_EDD",
        },
        "weight": 0.05,
    },
    {
        "name": "stated_purpose_unclear",
        "description": "Stated purpose unclear",
        "base_facts": {
            "txn.stated_purpose": "unclear",
            "txn.pattern_matches_profile": False,
        },
        "outcome": {
            "disposition": "EDD",
            "disposition_basis": "DISCRETIONARY",
            "reporting": "PENDING_EDD",
        },
        "weight": 0.04,
    },
    {
        "name": "adverse_media",
        "description": "Adverse media match",
        "base_facts": {
            "screening.adverse_media": True,
        },
        "outcome": {
            "disposition": "EDD",
            "disposition_basis": "DISCRETIONARY",
            "reporting": "PENDING_EDD",
        },
        "weight": 0.04,
    },
    {
        "name": "rapid_movement",
        "description": "Rapid in/out movement",
        "base_facts": {
            "flag.rapid_movement": True,
            "txn.pattern_matches_profile": False,
        },
        "outcome": {
            "disposition": "EDD",
            "disposition_basis": "DISCRETIONARY",
            "reporting": "PENDING_EDD",
        },
        "weight": 0.04,
    },
    {
        "name": "profile_deviation",
        "description": "Unusual for customer profile",
        "base_facts": {
            "flag.unusual_for_profile": True,
            "txn.pattern_matches_profile": False,
        },
        "outcome": {
            "disposition": "EDD",
            "disposition_basis": "DISCRETIONARY",
            "reporting": "PENDING_EDD",
        },
        "weight": 0.04,
    },
    {
        "name": "third_party",
        "description": "Third-party payment",
        "base_facts": {
            "flag.third_party": True,
        },
        "outcome": {
            "disposition": "EDD",
            "disposition_basis": "DISCRETIONARY",
            "reporting": "PENDING_EDD",
        },
        "weight": 0.03,
    },
    {
        "name": "layering_shell",
        "description": "Layering/shell company indicators",
        "base_facts": {
            "flag.layering": True,
            "flag.shell_company": True,
        },
        "outcome": {
            "disposition": "EDD",
            "disposition_basis": "DISCRETIONARY",
            "reporting": "PENDING_EDD",
        },
        "weight": 0.04,
    },

    # ─── ESCALATE scenarios (to senior/compliance) ───
    {
        "name": "high_risk_country",
        "description": "High-risk country destination",
        "base_facts": {
            "txn.cross_border": True,
            "txn.destination_country_risk": "high",
            "customer.high_risk_jurisdiction": True,
        },
        "outcome": {
            "disposition": "EDD",
            "disposition_basis": "DISCRETIONARY",
            "reporting": "PENDING_EDD",
        },
        "decision_level": "senior_analyst",
        "weight": 0.04,
    },
    {
        "name": "cash_intensive_large",
        "description": "Cash-intensive business, large amount",
        "base_facts": {
            "customer.cash_intensive": True,
            "txn.amount_band": "25k_100k",
            "txn.type": "cash_deposit",
        },
        "outcome": {
            "disposition": "EDD",
            "disposition_basis": "DISCRETIONARY",
            "reporting": "PENDING_EDD",
        },
        "decision_level": "senior_analyst",
        "weight": 0.04,
    },
    {
        "name": "pep_large_amount",
        "description": "PEP, large amount",
        "base_facts": {
            "customer.pep": True,
            "screening.pep_match": True,
            "txn.amount_band": "25k_100k",
        },
        "outcome": {
            "disposition": "EDD",
            "disposition_basis": "DISCRETIONARY",
            "reporting": "PENDING_EDD",
        },
        "decision_level": "senior_analyst",
        "weight": 0.04,
    },
    {
        "name": "pep_screening_match",
        "description": "PEP screening match",
        "base_facts": {
            "screening.pep_match": True,
            "customer.pep": True,
        },
        "outcome": {
            "disposition": "EDD",
            "disposition_basis": "DISCRETIONARY",
            "reporting": "PENDING_EDD",
        },
        "decision_level": "senior_analyst",
        "weight": 0.03,
    },

    # ─── BLOCK scenarios ───
    {
        "name": "sanctions_match",
        "description": "Sanctions match",
        "base_facts": {
            "screening.sanctions_match": True,
        },
        "outcome": {
            "disposition": "BLOCK",
            "disposition_basis": "MANDATORY",
            "reporting": "FILE_STR",
        },
        "weight": 0.03,
    },

    # ─── MONITORING / SAR HISTORY scenarios ───
    {
        "name": "one_prior_sar",
        "description": "1 prior SAR — normal processing with monitoring",
        "base_facts": {
            "prior.sars_filed": 1,
        },
        "outcome": {
            "disposition": "ALLOW",
            "disposition_basis": "DISCRETIONARY",
            "reporting": "NO_REPORT",
        },
        "weight": 0.03,
    },
    {
        "name": "multiple_prior_sars",
        "description": "2-3 prior SARs — escalate",
        "base_facts": {
            "prior.sars_filed": 3,
        },
        "outcome": {
            "disposition": "EDD",
            "disposition_basis": "DISCRETIONARY",
            "reporting": "PENDING_EDD",
        },
        "decision_level": "senior_analyst",
        "weight": 0.03,
    },
    {
        "name": "heavy_sar_history",
        "description": "4+ prior SARs — block for exit review",
        "base_facts": {
            "prior.sars_filed": 4,
        },
        "outcome": {
            "disposition": "BLOCK",
            "disposition_basis": "DISCRETIONARY",
            "reporting": "FILE_STR",
        },
        "weight": 0.02,
    },
    {
        "name": "previous_closure",
        "description": "Previous account closure — escalate",
        "base_facts": {
            "prior.account_closures": True,
        },
        "outcome": {
            "disposition": "EDD",
            "disposition_basis": "DISCRETIONARY",
            "reporting": "PENDING_EDD",
        },
        "decision_level": "senior_analyst",
        "weight": 0.03,
    },
]
```

### 2.4 Seed Generation Logic

For each scenario:
1. Start with `base_facts` — these are the defining characteristics
2. Fill ALL remaining fields randomly but realistically
3. Create 50-100 variations by randomizing the non-base fields
4. Add realistic noise: 10% of cases have a minority outcome 
   (e.g., structuring case that was ALLOW after EDD cleared it)

```python
def generate_seed(scenario, variation_number):
    """Generate one seed with all 28 fields populated."""
    from banking_field_registry import BANKING_FIELDS, validate_field_value
    
    facts = {}
    
    # 1. Set base facts from scenario (these define the pattern)
    for field_name, value in scenario["base_facts"].items():
        facts[field_name] = value
    
    # 2. Fill ALL remaining fields with realistic random values
    for field_name, field_def in BANKING_FIELDS.items():
        if field_name not in facts:
            facts[field_name] = random_realistic_value(field_name, field_def, scenario)
    
    # 3. Validate every field
    for field_name, value in facts.items():
        validate_field_value(field_name, value)
    
    # 4. Build the seed
    return {
        "precedent_id": str(uuid4()),
        "case_id_hash": sha256(f"seed-{scenario['name']}-{variation_number}"),
        "fingerprint_schema_id": "decisiongraph:aml:txn_monitoring:v2",
        "anchor_facts": [
            {"field_id": k, "value": v, "label": BANKING_FIELDS[k]["display_name"]}
            for k, v in facts.items()
        ],
        # THREE-FIELD OUTCOME (not pay/deny/escalate):
        "outcome": scenario["outcome"],  
        "disposition_basis": scenario["outcome"]["disposition_basis"],
        "reporting_obligation": scenario["outcome"]["reporting"],
        # Metadata:
        "policy_version": "2026.01.01",
        "policy_pack_id": "CA-FINTRAC-AML",
        "policy_pack_hash": sha256("CA-FINTRAC-AML-v2026.01.01"),
        "decision_level": scenario.get("decision_level", "analyst"),
        "decided_by_role": "aml_analyst",
        "decided_at": random_timestamp_2026(),
        "source_type": "seed",
        "scenario_code": scenario["name"],
        "seed_category": "aml",
        # Signal codes (NOT exclusion_codes):
        "signal_codes": derive_signal_codes(facts, scenario),
        "reason_codes": derive_reason_codes(facts, scenario),
    }
```

### 2.5 Target Volume

Generate 1,500 seeds total for policy version v2026.01.01:
- Use the `weight` field in each scenario to determine how many seeds per scenario
- Example: clean_known_customer (weight=0.25) → 375 seeds
- Example: sanctions_match (weight=0.03) → 45 seeds

---

## TASK 3: POLICY SHIFT SEEDS (EPOCH 2)

After generating the 1,500 v1 seeds, generate SHADOW projections under 4 policy changes.
These are NOT new seeds — they are re-evaluations of existing seeds under new rules.

### 3.1 Four Policy Changes

```python
POLICY_SHIFTS = [
    {
        "id": "lctr_threshold",
        "name": "LCTR Reporting Threshold",
        "description": "$10K → $8K",
        "policy_version": "2026.04.01",
        "citation": "PCMLTFA s. 12 (amended)",
        "rule_change": {
            "rule_id": "LCTR_THRESHOLD",
            "before": {"cash_reporting_threshold": 10000},
            "after": {"cash_reporting_threshold": 8000},
        },
        "affects": lambda seed: (
            seed_has_cash_type(seed) and
            seed_amount_in_range(seed, "3k_10k")  # $8K-$10K range
        ),
        "new_outcome": lambda seed, old_outcome: {
            **old_outcome,
            "reporting": "FILE_LCTR",  # was NO_REPORT
        },
    },
    {
        "id": "pep_risk_appetite",
        "name": "PEP Risk Appetite Tightened",
        "description": "PEP + ≥$25K → Senior Management sign-off",
        "policy_version": "2026.04.01",
        "citation": "Internal Policy 3.4.1 (revised)",
        "trigger": "FINTRAC Examination Finding #2026-EX-014",
        "rule_change": {
            "rule_id": "PEP_ESCALATION",
            "before": {"pep_any_amount": "edd_analyst"},
            "after": {"pep_over_25k": "edd_senior_management"},
        },
        "affects": lambda seed: (
            seed_fact(seed, "customer.pep") == True and
            seed_fact(seed, "txn.amount_band") in ["25k_100k", "over_100k"]
        ),
        "new_outcome": lambda seed, old_outcome: {
            **old_outcome,
            "disposition": "EDD",
            # decision_level changes, not outcome per se
        },
        "new_decision_level": "senior_management",
    },
    {
        "id": "crypto_classification",
        "name": "Crypto High-Risk Classification",
        "description": "All crypto → automatic EDD; unhosted wallet → BLOCK",
        "policy_version": "2026.07.01",
        "citation": "FINTRAC Guideline 5 (updated)",
        "rule_change": {
            "rule_id": "CRYPTO_RISK_CLASS",
            "before": {"crypto_treatment": "standard"},
            "after": {"crypto_treatment": "high_risk", "unhosted_wallet": "block"},
        },
        "affects": lambda seed: (
            seed_fact(seed, "txn.type") in ["crypto_purchase", "crypto_sale"]
        ),
        "new_outcome": lambda seed, old_outcome: {
            "disposition": "EDD",  # minimum: EDD for all crypto
            "disposition_basis": "DISCRETIONARY",
            "reporting": "PENDING_EDD",
        },
    },
    {
        "id": "structuring_window",
        "name": "Structuring Detection Window Extended",
        "description": "24-hour → 48-hour aggregation",
        "policy_version": "2026.04.15",
        "citation": "Internal Policy 4.2.1 (revised)",
        "trigger": "Internal Audit Report IA-2026-007",
        "rule_change": {
            "rule_id": "STRUCTURING_WINDOW",
            "before": {"aggregation_hours": 24},
            "after": {"aggregation_hours": 48},
        },
        "affects": lambda seed: (
            # Seeds that have just_below_threshold + multiple_same_day
            # but structuring was NOT flagged under v1
            # (simulates patterns spread across 24-48hr window)
            seed_fact(seed, "txn.just_below_threshold") == True and
            seed_fact(seed, "flag.structuring") == False
        ),
        "new_outcome": lambda seed, old_outcome: {
            "disposition": "EDD",
            "disposition_basis": "DISCRETIONARY",
            "reporting": "PENDING_EDD",
        },
    },
]
```

### 3.2 Shadow Record Format

For each affected seed, create a shadow record:

```python
{
    "shadow_id": str(uuid4()),
    "original_precedent_id": original_seed["precedent_id"],
    "policy_shift_id": shift["id"],
    "policy_version_before": "2026.01.01",
    "policy_version_after": shift["policy_version"],
    "rule_id_changed": shift["rule_change"]["rule_id"],
    "rule_hash_before": sha256(str(shift["rule_change"]["before"])),
    "rule_hash_after": sha256(str(shift["rule_change"]["after"])),
    "outcome_before": original_seed["outcome"],
    "outcome_after": new_outcome,
    "decision_level_before": original_seed["decision_level"],
    "decision_level_after": shift.get("new_decision_level", original_seed["decision_level"]),
    "change_type": determine_change_type(original_seed["outcome"], new_outcome),
    "change_description": shift["description"],
    "citation": shift["citation"],
    "shadow": True,
    "namespace": "shadow/policy_impact",
}
```

### 3.3 Expected Counts

Design the v1 seeds so these approximate counts of affected cases result:
- LCTR threshold: ~38 cases (cash txns in $8K-$10K range)
- PEP risk appetite: ~31 cases (PEP + amount ≥ $25K)
- Crypto classification: ~42 cases (all crypto transaction seeds)
- Structuring window: ~23 cases (just-below + multiple-same-day but not flagged)

---

## TASK 4: FIX NAME MISMATCHES IN SCORER

The similarity scorer in `service/main.py` (around L1424-1966) uses dimension 
names that don't match the seed field names. Fix them.

### 4.1 Scorer Dimension Mapping

Find each scorer dimension and make it read from the registry:

```python
# CURRENT (broken — looks for wrong names):
amount_bucket → looks for "amount_bucket" field
channel_method → looks for "channel" field  
corridor_match → looks for "corridor" field
customer_profile → looks for "customer_type" field
pep_match → looks for "pep" field

# FIX (read from registry):
from banking_field_registry import BANKING_FIELDS

# Each dimension should reference canonical names:
amount_bucket → reads seed["txn.amount_band"]
channel_method → reads seed["txn.type"]  
corridor_match → reads seed["txn.cross_border"] + seed["txn.destination_country_risk"]
customer_profile → reads seed["customer.type"] + seed["customer.relationship_length"]
pep_match → reads seed["customer.pep"]
```

### 4.2 Also Fix

- `find_by_exclusion_codes()` → rename to `find_by_signal_codes()`
- Outcome comparison: compare `outcome.disposition` (not `outcome_code`)
  - ALLOW vs ALLOW = supporting
  - BLOCK vs BLOCK = supporting
  - ALLOW vs BLOCK = contrary
  - EDD vs anything = neutral (INV-005: EDD is procedural)
- Remove the v1 outcome_map in main.py (around L942-955) that translates 
  engine verdicts to pay/deny/escalate

---

## TASK 5: FIX EVIDENCE TABLE DISPLAY NAMES

In `service/routers/report/render_md.py`, the `_EVIDENCE_SCOPE_LABELS` map 
is missing labels for several fields. Add them from the registry:

```python
from banking_field_registry import get_internal_to_display_map

# Replace the hardcoded _EVIDENCE_SCOPE_LABELS with:
_EVIDENCE_SCOPE_LABELS = get_internal_to_display_map()

# PLUS these non-registry fields that come from decision_pack:
_EVIDENCE_SCOPE_LABELS.update({
    "facts.sanctions_result": "Sanctions screening determination",
    "facts.adverse_media_mltf": "Adverse media ML/TF relevance indicator",
    "suspicion.has_intent": "Suspicion element: intent indicators present",
    "suspicion.has_deception": "Suspicion element: deception indicators present",
    "suspicion.has_sustained_pattern": "Suspicion element: sustained transaction pattern",
    "obligations.count": "Count of regulatory obligations triggered",
    "mitigations.count": "Count of mitigating factors identified",
    "typology.maturity": "Typology assessment maturity level",
})
```

---

## TASK 6: FIX JUDGMENT PAYLOAD

In `src/decisiongraph/judgment.py`:

### 6.1 Add Domain-Aware Validation

```python
# Current: validates only pay/deny/partial/escalate
# Fix: validate based on domain

BANKING_DISPOSITIONS = {"ALLOW", "EDD", "BLOCK"}
BANKING_REPORTING = {"NO_REPORT", "FILE_STR", "FILE_LCTR", "FILE_TPR", "PENDING_EDD"}
BANKING_BASIS = {"MANDATORY", "DISCRETIONARY"}
BANKING_DECISION_LEVELS = {"analyst", "senior_analyst", "manager", "cco", "senior_management"}

INSURANCE_OUTCOMES = {"pay", "deny", "partial", "escalate"}  # backward compat

def validate_outcome(payload):
    if payload.domain == "banking":
        assert payload.outcome["disposition"] in BANKING_DISPOSITIONS
        assert payload.outcome["disposition_basis"] in BANKING_BASIS
        assert payload.outcome["reporting"] in BANKING_REPORTING
        assert payload.decision_level in BANKING_DECISION_LEVELS
    elif payload.domain == "insurance":
        assert payload.outcome_code in INSURANCE_OUTCOMES
```

### 6.2 Rename Fields

```
exclusion_codes → signal_codes  (for banking domain)
decision_level: "adjuster" → never valid for banking (use analyst/manager/cco)
```

Keep backward compatibility for insurance domain — only banking gets the new validation.

---

## TASK 7: POLICY SHIFT API ENDPOINTS

Add two new endpoints to `service/main.py` (or a new router):

```python
@router.get("/api/policy-shifts")
async def list_policy_shifts():
    """Returns summary of all 4 policy shift scenarios with impact stats."""
    return [
        {
            "id": "lctr_threshold",
            "name": "LCTR Reporting Threshold", 
            "description": "$10K → $8K",
            "citation": "PCMLTFA s. 12 (amended)",
            "policy_version_before": "2026.01.01",
            "policy_version_after": "2026.04.01",
            "total_cases_analyzed": 1500,
            "cases_affected": 38,
            "pct_affected": 2.5,
            "primary_change": "reporting",
            "summary": "38 cash transactions in $8K-$10K range gain LCTR filing obligation",
        },
        # ... 3 more
    ]

@router.get("/api/policy-shifts/{shift_id}/cases")
async def get_policy_shift_cases(shift_id: str):
    """Returns affected cases with before/after comparison."""
    shadows = load_shadow_records(shift_id)
    return {
        "shift": get_shift_metadata(shift_id),
        "cases": [
            {
                "precedent_id": s["original_precedent_id"],
                "case_summary": summarize_case_facts(s),
                "outcome_before": s["outcome_before"],
                "outcome_after": s["outcome_after"],
                "decision_level_before": s["decision_level_before"],
                "decision_level_after": s["decision_level_after"],
                "change_type": s["change_type"],
                "rule_hash_before": s["rule_hash_before"],
                "rule_hash_after": s["rule_hash_after"],
            }
            for s in shadows
        ],
    }
```

---

## EXECUTION ORDER

Do these in order — each depends on the previous:

```
STEP 1: Create banking_field_registry.py (Task 1)
         → Verify against actual frontend field names first
         
STEP 2: Fix JudgmentPayload (Task 6)
         → Add banking outcome validation
         → Rename exclusion_codes → signal_codes
         → Keep insurance backward compat

STEP 3: Rebuild seed generator (Task 2)
         → Import from registry
         → All 28 fields populated
         → Three-field outcomes
         → 1,500 seeds for policy v2026.01.01

STEP 4: Fix scorer name mismatches (Task 4)
         → Read field names from registry
         → Fix outcome comparison logic
         → Remove v1 outcome_map

STEP 5: Fix evidence table (Task 5)
         → Display names from registry

STEP 6: Generate policy shift shadows (Task 3)
         → Re-evaluate v1 seeds under 4 policy changes
         → Store shadow records

STEP 7: Add policy shift API endpoints (Task 7)

TEST AFTER EACH STEP:
  - All existing tests still pass
  - Insurance pipeline unchanged
  - No insurance vocabulary in banking output
```

## VALIDATION

After all steps, run this check:

```bash
# Zero insurance terms in banking seeds:
grep -ri "pay\|deny\|escalate\|partial\|exclusion\|adjuster\|claim" banking_seeds/ 
# Expected: 0 results

# All seeds have 28 fields:
python -c "
from aml_seed_generator import load_seeds
from banking_field_registry import BANKING_FIELDS
seeds = load_seeds()
for s in seeds:
    fact_fields = {f['field_id'] for f in s['anchor_facts']}
    missing = set(BANKING_FIELDS.keys()) - fact_fields
    if missing:
        print(f'Seed {s[\"precedent_id\"]}: missing {missing}')
"
# Expected: no missing fields

# Similarity scorer finds matches:
# Enter on website: Corporation, Wire, $10K-$25K, Cross-Border, Structuring
# Expected: precedent section shows scored matches (not 0)
```

---

## WHAT NOT TO TOUCH

- Insurance/ClaimPilot pipeline — leave completely alone
- Layers 1-5 (Cell, Chain, Commit Gate, Governance, Resolver) — unchanged
- Existing test fixtures for insurance — unchanged
- Website frontend — that's a separate task
