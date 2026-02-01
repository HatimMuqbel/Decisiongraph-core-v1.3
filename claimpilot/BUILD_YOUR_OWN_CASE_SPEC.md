# Build Your Own Case — Field Specifications

## Goal

Add "Build Your Own Case" to both ClaimPilot and DecisionGraph with **dropdown/toggle only** inputs. No free text = no format errors.

---

# PART 1: CLAIMPILOT (Insurance)

## Global Fields (All Policy Types)

```
Policy Pack:        [Ontario Auto ▼] [Homeowners ▼] [Marine ▼] [Health ▼] [WSIB ▼] [CGL ▼] [E&O ▼] [Travel ▼]
Loss Date:          [Date picker - defaults to today]
Policy Status:      [Active ▼] [Lapsed ▼] [Cancelled ▼]
Claim Amount:       [$0-10K ▼] [$10K-25K ▼] [$25K-50K ▼] [$50K-100K ▼] [$100K+ ▼]
```

---

## AUTO (Ontario OAP 1)

### Loss Type
```
[Collision ▼] [Comprehensive ▼] [Accident Benefits ▼] [Liability ▼]
```

### Key Facts
```
Vehicle Use at Loss:     [Personal ▼] [Commute ▼] [Business ▼] [Rideshare/Delivery ▼]
Rideshare App Active:    [○ Yes] [● No]
Driver License Status:   [Valid ▼] [Suspended ▼] [Expired ▼] [Never Licensed ▼]
BAC Level:               [0.00 ▼] [0.05 ▼] [0.08 ▼] [0.10 ▼] [0.12+ ▼]
Impairment Indicated:    [○ Yes] [● No]
Racing/Speed Contest:    [○ Yes] [● No]
Intentional Damage:      [○ Yes] [● No]
Vehicle Listed on Policy:[● Yes] [○ No]
Named Driver/Permitted:  [● Yes] [○ No]
```

### Evidence
```
[✓] Police Report
[✓] Damage Estimate  
[ ] Driver Statement
[ ] Witness Statement
[ ] Photos
[ ] Toxicology Report
[ ] App Activity Records (rideshare)
[ ] MTO Driver Abstract
```

### Expected Outcomes
| Scenario | Outcome |
|----------|---------|
| Personal use, licensed, no impairment | ✅ PAY |
| Rideshare app active | ❌ DENY (4.2.1 Commercial) |
| BAC ≥ 0.08 | ❌ DENY (4.3.3 Impaired) |
| License suspended | ❌ DENY (4.1.2 Unlicensed) |
| Racing activity | ❌ DENY (4.5.1 Racing) |
| Claim > $50K | ⚠️ ESCALATE (Manager) |
| Intentional damage | 🔍 REFER SIU |

---

## PROPERTY (Homeowners HO-3)

### Loss Type
```
[Fire ▼] [Water Damage ▼] [Theft ▼] [Wind/Hail ▼] [Vandalism ▼] [Liability ▼]
```

### Key Facts
```
Loss Cause:              [Fire ▼] [Flood/Surface Water ▼] [Pipe Burst ▼] [Sewer Backup ▼] 
                         [Roof Leak ▼] [Earthquake ▼] [Theft ▼] [Wind ▼]
Water Source:            [Internal Plumbing ▼] [Surface Water ▼] [Sewer ▼] [Roof ▼] [N/A ▼]
Damage Type:             [Sudden ▼] [Gradual ▼]
Days Vacant:             [0 ▼] [1-15 ▼] [16-30 ▼] [31-45 ▼] [46-60 ▼] [60+ ▼]
Dwelling Occupied:       [● Yes] [○ No]
Arson Suspected:         [○ Yes] [● No]
Maintenance Issue:       [○ Yes] [● No]
Prior Claims (3 yrs):    [0 ▼] [1 ▼] [2 ▼] [3+ ▼]
```

### Evidence
```
[✓] Claim Form (Proof of Loss)
[✓] Damage Photos
[ ] Fire Department Report
[ ] Police Report (theft)
[ ] Contractor Estimate
[ ] Adjuster Inspection
[ ] Weather Report
[ ] Maintenance Records
```

### Expected Outcomes
| Scenario | Outcome |
|----------|---------|
| Fire, occupied, no issues | ✅ PAY |
| Flood/surface water | ❌ DENY (Flood Exclusion) |
| Earthquake | ❌ DENY (Earth Movement) |
| Gradual water damage | ❌ DENY (Wear & Tear) |
| Vacant > 30 days | ❌ DENY (Vacancy) |
| Arson suspected | 🔍 REFER SIU |

---

## MARINE (Pleasure Craft)

### Loss Type
```
[Storm Damage ▼] [Collision ▼] [Sinking ▼] [Grounding ▼] [Fire ▼] [Theft ▼] [Vandalism ▼]
```

### Key Facts
```
Within Navigation Limits: [● Yes] [○ No]
Operator PCOC Valid:      [● Yes] [○ No]
Vessel in Water:          [● Yes] [○ No]
Commercial Use:           [○ Yes] [● No]
Racing Activity:          [○ Yes] [● No]
Maintenance Current:      [● Yes] [○ No]
Ice Damage:               [○ Yes] [● No]
Total Loss:               [○ Yes] [● No]
```

### Evidence
```
[✓] Claim Form
[✓] Damage Photos
[ ] Coast Guard Report
[ ] Marine Survey
[ ] GPS/AIS Records
[ ] Weather Report
[ ] Maintenance Logs
[ ] Operator Credentials
```

### Expected Outcomes
| Scenario | Outcome |
|----------|---------|
| Storm, within limits, PCOC valid | ✅ PAY |
| Outside navigation limits | ❌ DENY (Navigation) |
| No PCOC | ❌ DENY (Operator) |
| Commercial use | ❌ DENY (Commercial) |
| Ice damage, in water | ❌ DENY (Ice) |
| Racing | ❌ DENY (Racing) |
| Sinking/Total loss | ⚠️ ESCALATE (Marine Manager) |

---

## HEALTH (Group Benefits)

### Claim Type
```
[Prescription Drug ▼] [Dental ▼] [Paramedical ▼] [Vision ▼] [Hospital ▼]
```

### Key Facts
```
Member Status:           [Active ▼] [Terminated ▼] [COBRA ▼]
Coverage Months:         [0-3 ▼] [3-6 ▼] [6-12 ▼] [12+ ▼]
Drug on Formulary:       [● Yes] [○ No]
Prior Auth Required:     [○ Yes] [● No]
Prior Auth Approved:     [● Yes] [○ No] [N/A ▼]
Pre-existing Condition:  [○ Yes] [● No]
Work Related Injury:     [○ Yes] [● No]
Cosmetic Procedure:      [○ Yes] [● No]
Experimental Treatment:  [○ Yes] [● No]
Monthly Drug Cost:       [Under $100 ▼] [$100-$500 ▼] [$500-$1000 ▼] [$1000+ ▼]
```

### Evidence
```
[✓] Claim Form
[✓] Prescription/Receipt
[ ] Physician Letter
[ ] Prior Auth Form
[ ] Medical Records
[ ] Formulary Exception Request
```

### Expected Outcomes
| Scenario | Outcome |
|----------|---------|
| Formulary drug, active member | ✅ PAY |
| Non-formulary, no prior auth | ❌ DENY (Non-Formulary) |
| Pre-existing, < 12 months coverage | ❌ DENY (Pre-existing) |
| Work-related | ❌ DENY (WSIB covers) |
| Cosmetic | ❌ DENY (Cosmetic) |
| Drug cost > $500/month | ⚠️ ESCALATE (Clinical Review) |

---

## WORKERS COMP (Ontario WSIB)

### Injury Type
```
[Strain/Sprain ▼] [Fracture ▼] [Laceration ▼] [Repetitive Strain ▼] [Mental Health ▼] [Fatality ▼]
```

### Key Facts
```
Employer WSIB Registered: [● Yes] [○ No]
Injury Work Related:      [● Yes] [○ No]
Arose Out of Employment:  [● Yes] [○ No]
In Course of Employment:  [● Yes] [○ No]
During Work Hours:        [● Yes] [○ No]
At Workplace:             [● Yes] [○ No]
Self-Inflicted:           [○ Yes] [● No]
Intoxication Sole Cause:  [○ Yes] [● No]
Pre-existing Condition:   [○ Yes] [● No]
Pre-existing Aggravated:  [● Yes] [○ No] [N/A ▼]
Fatality:                 [○ Yes] [● No]
```

### Evidence
```
[✓] Form 7 (Employer Report)
[✓] Form 8 (Physician Report)
[✓] Worker Statement
[ ] Witness Statement
[ ] Incident Report
[ ] Medical Records
[ ] Toxicology Report
```

### Expected Outcomes
| Scenario | Outcome |
|----------|---------|
| Work injury, during work, at workplace | ✅ PAY |
| Not work related | ❌ DENY (Not Work Related) |
| Pre-existing, not aggravated | ❌ DENY (Pre-existing) |
| Intoxication sole cause | ❌ DENY (Intoxication) |
| Self-inflicted | ❌ DENY (Self-Inflicted) |
| Fatality | ⚠️ ESCALATE (Manager) |

---

## CGL (Commercial General Liability)

### Loss Type
```
[Bodily Injury ▼] [Property Damage ▼] [Personal Injury ▼] [Advertising Injury ▼] [Products Liability ▼]
```

### Key Facts
```
Occurrence During Policy:  [● Yes] [○ No]
In Coverage Territory:     [● Yes] [○ No]
Expected/Intended:         [○ Yes] [● No]
Pollution Related:         [○ Yes] [● No]
Auto Involved:             [○ Yes] [● No]
Contractual Liability:     [○ Yes] [● No]
Professional Services:     [○ Yes] [● No]
Your Work/Product:         [○ Yes] [● No]
Lawsuit Filed:             [○ Yes] [● No]
Claim Amount:              [Under $25K ▼] [$25K-$100K ▼] [$100K-$500K ▼] [$500K+ ▼]
```

### Evidence
```
[✓] Claim Notice
[✓] Incident Report
[ ] Police Report
[ ] Medical Records (BI)
[ ] Repair Estimates (PD)
[ ] Witness Statements
[ ] Contract/Agreement
[ ] Lawsuit Documents
```

### Expected Outcomes
| Scenario | Outcome |
|----------|---------|
| Slip & fall on premises | ✅ PAY |
| Expected/intended injury | ❌ DENY (Intentional) |
| Pollution event | ❌ DENY (Pollution) |
| Auto involved | ❌ DENY (Auto Exclusion) |
| Professional services | ❌ DENY (Professional - need E&O) |
| Lawsuit filed | ⚠️ ESCALATE (Claims Counsel) |

---

## E&O (Professional Liability)

### Claim Type
```
[Negligence ▼] [Error ▼] [Omission ▼] [Misrepresentation ▼] [Breach of Duty ▼]
```

### Key Facts
```
Claim First Made During Policy: [● Yes] [○ No]
Wrongful Act Date:              [Before Retro Date ▼] [After Retro Date ▼]
In Professional Capacity:       [● Yes] [○ No]
Known Before Policy:            [○ Yes] [● No]
Fraudulent/Dishonest Act:       [○ Yes] [● No]
Bodily Injury Involved:         [○ Yes] [● No]
Defense Costs Incurred:         [○ Yes] [● No]
Prior Similar Claims:           [0 ▼] [1 ▼] [2+ ▼]
```

### Evidence
```
[✓] Claim Notice
[✓] Engagement Letter/Contract
[ ] Work Product at Issue
[ ] Client Correspondence
[ ] Expert Opinion
[ ] Demand Letter
[ ] Lawsuit Documents
```

### Expected Outcomes
| Scenario | Outcome |
|----------|---------|
| Error in professional work, after retro | ✅ PAY |
| Wrongful act before retro date | ❌ DENY (Prior Acts) |
| Known before policy | ❌ DENY (Known Circumstances) |
| Fraudulent act | ❌ DENY (Fraud/Dishonesty) |
| Bodily injury | ❌ DENY (BI Exclusion - need CGL) |

---

## TRAVEL (Medical)

### Claim Type
```
[Emergency Medical ▼] [Trip Cancellation ▼] [Trip Interruption ▼] [Baggage ▼] [Evacuation ▼]
```

### Key Facts
```
Outside Home Province:    [● Yes] [○ No]
Emergency Treatment:      [● Yes] [○ No]
Pre-existing Condition:   [○ Yes] [● No]
Condition Stable (90 days):[● Yes] [○ No] [N/A ▼]
High-Risk Activity:       [○ Yes] [● No]
Travel Advisory in Effect:[○ Yes] [● No]
Elective Treatment:       [○ Yes] [● No]
Hospital Admission:       [○ Yes] [● No]
Treatment Cost:           [Under $1K ▼] [$1K-$10K ▼] [$10K-$50K ▼] [$50K+ ▼]
```

### High-Risk Activities (if Yes)
```
[Skydiving ▼] [Bungee ▼] [Mountaineering ▼] [Scuba (uncertified) ▼] [Racing ▼] [Other ▼]
```

### Evidence
```
[✓] Claim Form
[✓] Medical Bills/Receipts
[ ] Physician Report
[ ] Hospital Records
[ ] Travel Itinerary
[ ] Proof of Trip Cost
[ ] Cancellation Notice
```

### Expected Outcomes
| Scenario | Outcome |
|----------|---------|
| Emergency abroad, no pre-existing | ✅ PAY |
| Pre-existing, not stable | ❌ DENY (Pre-existing) |
| Elective treatment | ❌ DENY (Not Emergency) |
| High-risk activity | ❌ DENY (High-Risk) |
| Travel advisory | ❌ DENY (Travel Advisory) |
| Cost > $50K | ⚠️ ESCALATE (Medical Director) |

---

# PART 2: DECISIONGRAPH (Banking/AML)

## Customer Profile

### Customer Type
```
[Individual ▼] [Sole Proprietor ▼] [Corporation ▼] [Partnership ▼] [Trust ▼] [Non-Profit ▼]
```

### Risk Category
```
PEP (Politically Exposed):    [○ Yes] [● No]
High-Risk Jurisdiction:       [○ Yes] [● No]
High-Risk Industry:           [○ Yes] [● No]
Cash-Intensive Business:      [○ Yes] [● No]
Relationship Length:          [New (<6mo) ▼] [Established (6mo-2yr) ▼] [Long-term (2yr+) ▼]
```

### High-Risk Industries (if Yes)
```
[Money Services ▼] [Crypto/Virtual Assets ▼] [Gaming/Gambling ▼] [Real Estate ▼] 
[Precious Metals ▼] [Arms/Defense ▼] [Adult Entertainment ▼]
```

---

## Transaction Details

### Transaction Type
```
[Wire Transfer ▼] [Cash Deposit ▼] [Cash Withdrawal ▼] [Check ▼] [ACH/EFT ▼] 
[Crypto Purchase ▼] [Crypto Sale ▼] [International Transfer ▼]
```

### Transaction Facts
```
Amount (CAD):              [Under $3K ▼] [$3K-$10K ▼] [$10K-$25K ▼] [$25K-$100K ▼] [$100K+ ▼]
Cross-Border:              [○ Yes] [● No]
Destination Country:       [Canada ▼] [USA ▼] [UK ▼] [High-Risk Country ▼]
Round Amount:              [○ Yes] [● No]
Just Below $10K:           [○ Yes] [● No]
Multiple Same-Day Txns:    [○ Yes] [● No]
Pattern Matches Profile:   [● Yes] [○ No]
Source of Funds Clear:     [● Yes] [○ No]
Stated Purpose:            [Personal ▼] [Business ▼] [Investment ▼] [Gift ▼] [Unclear ▼]
```

---

## KYC Status

### Identity Verification
```
ID Verified:               [● Yes] [○ No]
ID Document Type:          [Passport ▼] [Driver's License ▼] [Government ID ▼] [None ▼]
ID Expired:                [○ Yes] [● No]
Address Verified:          [● Yes] [○ No]
Address Proof Type:        [Utility Bill ▼] [Bank Statement ▼] [Government Letter ▼] [None ▼]
```

### Business Verification (if applicable)
```
Business Registered:       [● Yes] [○ No]
Beneficial Owners Identified: [● Yes] [○ No]
UBO Above 25%:             [● Yes] [○ No] [N/A ▼]
Source of Wealth Documented: [● Yes] [○ No]
Business Activity Verified: [● Yes] [○ No]
```

### Enhanced Due Diligence
```
EDD Required:              [○ Yes] [● No]
EDD Completed:             [● Yes] [○ No] [N/A ▼]
Senior Management Approval: [● Yes] [○ No] [N/A ▼]
```

---

## Red Flags / Indicators

### Transaction Red Flags
```
Structuring Suspected:          [○ Yes] [● No]
Rapid Movement (in/out):        [○ Yes] [● No]
Layering Indicators:            [○ Yes] [● No]
Unusual for Customer Profile:   [○ Yes] [● No]
Third-Party Payment:            [○ Yes] [● No]
Shell Company Indicators:       [○ Yes] [● No]
```

### Screening Results
```
Sanctions Match:           [○ Yes] [● No]
PEP Match:                 [○ Yes] [● No]
Adverse Media:             [○ Yes] [● No]
Prior SARs Filed:          [0 ▼] [1 ▼] [2+ ▼]
Previous Account Closures: [○ Yes] [● No]
```

---

## Documents Available

### Individual Documents
```
[ ] Government-issued Photo ID
[ ] Secondary ID
[ ] Proof of Address (< 3 months)
[ ] Source of Funds Declaration
[ ] Employment Verification
[ ] Tax Returns
```

### Business Documents
```
[ ] Articles of Incorporation
[ ] Business License
[ ] Beneficial Ownership Declaration
[ ] Financial Statements
[ ] Bank References
[ ] Board Resolution (for signatories)
```

### Transaction Documents
```
[ ] Wire Instructions
[ ] Invoice/Contract (for business purpose)
[ ] Gift Letter (for gifts)
[ ] Loan Agreement (for loan proceeds)
[ ] Sale Agreement (for asset sales)
```

---

## Expected Outcomes

### Transaction Decisions
| Scenario | Outcome |
|----------|---------|
| Known customer, normal pattern, under $10K | ✅ APPROVE |
| New customer, >$10K, source clear | ✅ APPROVE + Report |
| Just below $10K, multiple same day | 🔍 INVESTIGATE (Structuring) |
| High-risk country destination | ⚠️ ESCALATE (Compliance) |
| Sanctions match | ❌ BLOCK + Report |
| PEP, large amount | ⚠️ ESCALATE (Senior Management) |

### Customer Onboarding
| Scenario | Outcome |
|----------|---------|
| Full KYC complete, low risk | ✅ APPROVE |
| Missing ID verification | ❌ DECLINE (Incomplete KYC) |
| PEP, EDD not complete | ⏸️ HOLD (Pending EDD) |
| High-risk industry, no senior approval | ⚠️ ESCALATE |
| Sanctions match | ❌ DECLINE + Report |
| Adverse media, serious | ❌ DECLINE |

### Reporting Triggers
| Scenario | Action |
|----------|--------|
| Cash > $10K | → Large Cash Transaction Report (LCTR) |
| Suspicious activity | → Suspicious Transaction Report (STR) |
| Terrorist Property | → Terrorist Property Report |
| Sanctions match | → Block + Report to FINTRAC |

---

# IMPLEMENTATION NOTES

## UI Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  BUILD YOUR OWN CASE                                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Policy/Scenario Type: [Ontario Auto ▼]                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌───────────────────────┐  ┌────────────────────────────────┐ │
│  │ FACTS                 │  │ RECOMMENDATION                 │ │
│  │                       │  │                                │ │
│  │ Vehicle Use:          │  │ ✅ PAY                         │ │
│  │ [Personal ▼]          │  │                                │ │
│  │                       │  │ or                             │ │
│  │ Rideshare Active:     │  │                                │ │
│  │ [○ Yes] [● No]        │  │ ❌ DENY                        │ │
│  │                       │  │ Exclusion: 4.2.1               │ │
│  │ BAC Level:            │  │ Commercial Use                 │ │
│  │ [0.00 ▼]              │  │                                │ │
│  │                       │  │ Policy Wording:                │ │
│  │ ...                   │  │ "We do not cover..."           │ │
│  │                       │  │                                │ │
│  ├───────────────────────┤  ├────────────────────────────────┤ │
│  │ EVIDENCE              │  │ REASONING CHAIN                │ │
│  │ [✓] Police Report     │  │ 1. ✓ Policy active             │ │
│  │ [✓] Damage Estimate   │  │ 2. ✓ Coverage applies          │ │
│  │ [ ] Driver Statement  │  │ 3. ✓ Commercial - NOT triggered│ │
│  │                       │  │ 4. ✓ Impaired - NOT triggered  │ │
│  └───────────────────────┘  └────────────────────────────────┘ │
│                                                                 │
│  [EVALUATE]                                                     │
└─────────────────────────────────────────────────────────────────┘
```

## Auto-Evaluate Option

Consider adding toggle:
```
[✓] Auto-evaluate on change
```

When checked, re-evaluates immediately when any fact changes (no need to click button).

## Validation Rules

1. Show only relevant fields for selected policy type
2. Disable incompatible combinations (e.g., can't select "Flood" cause with "Fire" loss type)
3. Evidence checkboxes should reflect what's typically required for that scenario
4. Show warning if required evidence is missing

## API Call

```javascript
POST /evaluate
{
  "policy_id": "CA-ON-OAP1-2024",
  "loss_type": "collision",
  "loss_date": "2024-06-15",
  "report_date": "2024-06-15",
  "facts": [
    {"field": "vehicle.use_at_loss", "value": "personal"},
    {"field": "driver.rideshare_app_active", "value": false},
    {"field": "driver.bac_level", "value": 0.0},
    ...
  ],
  "evidence": [
    {"doc_type": "police_report", "status": "verified"},
    {"doc_type": "damage_estimate", "status": "verified"}
  ]
}
```

## Mobile Considerations

- Stack facts and results vertically on small screens
- Use collapsible sections for evidence
- Keep dropdowns full-width
- Make toggles touch-friendly (larger tap targets)
