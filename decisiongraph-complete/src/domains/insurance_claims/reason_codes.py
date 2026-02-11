"""
Insurance Claims Reason Code Registry

Modeled on domains/banking_aml/reason_codes.py.  Provides structured
reason codes for insurance claims decision workflows.

Registries Defined:
- decisiongraph:insurance:fraud:v1       - Fraud indicators (~15 codes)
- decisiongraph:insurance:coverage:v1    - Coverage/exclusion (~12 codes)
- decisiongraph:insurance:evidence:v1    - Documentation gaps (~8 codes)
- decisiongraph:insurance:regulatory:v1  - Regulatory requirements (~8 codes)
- decisiongraph:insurance:siu:v1         - SIU referral reasons (~8 codes)

Total: ~51 unique reason codes
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# =============================================================================
# Exceptions
# =============================================================================

class InsuranceReasonCodeError(Exception):
    pass


class InsuranceCodeNotFoundError(InsuranceReasonCodeError):
    pass


# =============================================================================
# Reason Code
# =============================================================================

@dataclass
class InsuranceReasonCode:
    code: str
    name: str
    description: str
    regulation_ref: Optional[str] = None
    red_flags: list[str] = field(default_factory=list)
    category: str = ""

    def __post_init__(self) -> None:
        if not self.code:
            raise InsuranceReasonCodeError("code cannot be empty")
        if not self.name:
            raise InsuranceReasonCodeError("name cannot be empty")
        if not self.description:
            raise InsuranceReasonCodeError("description cannot be empty")

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "regulation_ref": self.regulation_ref,
            "red_flags": self.red_flags,
            "category": self.category,
        }


# =============================================================================
# Reason Code Registry
# =============================================================================

class InsuranceReasonCodeRegistry:
    def __init__(self) -> None:
        self._codes: dict[str, InsuranceReasonCode] = {}
        self._by_category: dict[str, list[str]] = {}
        self._registries: dict[str, str] = {}
        self._register_builtin_codes()

    def _register_builtin_codes(self) -> None:
        for code in create_fraud_codes():
            self.register_code(code)
        self._registries["decisiongraph:insurance:fraud:v1"] = "Fraud Indicator Codes"

        for code in create_coverage_codes():
            self.register_code(code)
        self._registries["decisiongraph:insurance:coverage:v1"] = "Coverage/Exclusion Codes"

        for code in create_evidence_codes():
            self.register_code(code)
        self._registries["decisiongraph:insurance:evidence:v1"] = "Evidence/Documentation Codes"

        for code in create_regulatory_codes():
            self.register_code(code)
        self._registries["decisiongraph:insurance:regulatory:v1"] = "Regulatory Requirement Codes"

        for code in create_siu_codes():
            self.register_code(code)
        self._registries["decisiongraph:insurance:siu:v1"] = "SIU Referral Codes"

    def register_code(self, reason_code: InsuranceReasonCode) -> None:
        self._codes[reason_code.code] = reason_code
        category = reason_code.category
        if category not in self._by_category:
            self._by_category[category] = []
        self._by_category[category].append(reason_code.code)

    def get_code(self, code: str) -> InsuranceReasonCode:
        if code not in self._codes:
            raise InsuranceCodeNotFoundError(f"Reason code not found: {code}")
        return self._codes[code]

    def get_codes_by_category(self, category: str) -> list[InsuranceReasonCode]:
        codes = self._by_category.get(category, [])
        return [self._codes[code] for code in codes]

    def validate_code(self, code: str) -> bool:
        return code in self._codes

    def validate_codes(self, codes: list[str]) -> list[str]:
        return [code for code in codes if code not in self._codes]

    def list_codes(self) -> list[str]:
        return list(self._codes.keys())

    def count(self) -> int:
        return len(self._codes)


# =============================================================================
# Fraud Indicator Codes
# =============================================================================

def create_fraud_codes() -> list[InsuranceReasonCode]:
    return [
        InsuranceReasonCode(
            code="RC-FRD-STAGED",
            name="Staged Accident",
            description="Indicators consistent with staged collision or loss event",
            red_flags=["staged_accident", "inconsistent_statements", "prior_claims"],
            category="fraud",
        ),
        InsuranceReasonCode(
            code="RC-FRD-EXAGGERATED",
            name="Exaggerated Claim",
            description="Claim amount or injuries appear inflated beyond evidence",
            category="fraud",
        ),
        InsuranceReasonCode(
            code="RC-FRD-INCONSISTENT",
            name="Inconsistent Statements",
            description="Claimant statements contradict evidence or prior statements",
            red_flags=["inconsistent_statements"],
            category="fraud",
        ),
        InsuranceReasonCode(
            code="RC-FRD-LATE-REPORT",
            name="Suspicious Late Reporting",
            description="Claim reported significantly after loss event without justification",
            red_flags=["late_reporting", "delayed_report"],
            category="fraud",
        ),
        InsuranceReasonCode(
            code="RC-FRD-PRE-EXISTING",
            name="Pre-Existing Damage",
            description="Evidence of damage predating the claimed loss event",
            red_flags=["pre_existing_damage"],
            category="fraud",
        ),
        InsuranceReasonCode(
            code="RC-FRD-HISTORY",
            name="Excessive Claim History",
            description="Claimant has abnormally high frequency of prior claims",
            red_flags=["excessive_claim_history", "prior_claims_frequency"],
            category="fraud",
        ),
        InsuranceReasonCode(
            code="RC-FRD-RING",
            name="Fraud Ring Pattern",
            description="Claim matches known fraud ring operational patterns",
            regulation_ref="IBC Fraud Prevention Guidelines",
            red_flags=["staged_accident", "fraud_ring_link"],
            category="fraud",
        ),
        InsuranceReasonCode(
            code="RC-FRD-ARSON",
            name="Suspected Arson",
            description="Fire loss with indicators of deliberate ignition",
            red_flags=["arson_suspected", "accelerant_detected"],
            category="fraud",
        ),
        InsuranceReasonCode(
            code="RC-FRD-PHANTOM",
            name="Phantom Vehicle/Injury",
            description="Claimed vehicle or injury cannot be independently verified",
            category="fraud",
        ),
        InsuranceReasonCode(
            code="RC-FRD-CLEAR",
            name="No Fraud Indicators",
            description="No fraud indicators detected in claim assessment",
            category="fraud",
        ),
        InsuranceReasonCode(
            code="RC-FRD-DENY-PRIOR",
            name="Prior Claims Denied",
            description="Claimant has multiple prior denied claims",
            red_flags=["prior_denied"],
            category="fraud",
        ),
        InsuranceReasonCode(
            code="RC-FRD-ID-THEFT",
            name="Identity Fraud Suspected",
            description="Claimant identity verification failed or suspicious",
            category="fraud",
        ),
    ]


# =============================================================================
# Coverage/Exclusion Codes
# =============================================================================

def create_coverage_codes() -> list[InsuranceReasonCode]:
    return [
        InsuranceReasonCode(
            code="RC-COV-COVERED",
            name="Loss Covered",
            description="Loss falls within policy coverage terms",
            category="coverage",
        ),
        InsuranceReasonCode(
            code="RC-COV-EXCLUDED",
            name="Policy Exclusion Applies",
            description="Loss falls under a named exclusion in the policy",
            regulation_ref="Policy Terms and Conditions",
            category="coverage",
        ),
        InsuranceReasonCode(
            code="RC-COV-OUTSIDE-PERIOD",
            name="Outside Policy Period",
            description="Loss occurred outside the active policy period",
            category="coverage",
        ),
        InsuranceReasonCode(
            code="RC-COV-DEDUCTIBLE",
            name="Below Deductible",
            description="Claim amount below policy deductible",
            category="coverage",
        ),
        InsuranceReasonCode(
            code="RC-COV-LIMIT-EXCEEDED",
            name="Coverage Limit Exceeded",
            description="Claim exceeds policy coverage limits",
            category="coverage",
        ),
        InsuranceReasonCode(
            code="RC-COV-PARTIAL",
            name="Partial Coverage",
            description="Claim partially covered — some elements excluded",
            category="coverage",
        ),
        InsuranceReasonCode(
            code="RC-COV-SUBROGATION",
            name="Subrogation Rights",
            description="Third party liability established — recovery rights exist",
            category="coverage",
        ),
        InsuranceReasonCode(
            code="RC-COV-IMPAIRMENT",
            name="Impairment Exclusion",
            description="Driver impairment exclusion applies (OAP 1)",
            regulation_ref="OAP 1 Section 4.1",
            category="coverage",
        ),
        InsuranceReasonCode(
            code="RC-COV-COMMERCIAL-USE",
            name="Commercial Use Exclusion",
            description="Vehicle/vessel used for undisclosed commercial purposes",
            category="coverage",
        ),
        InsuranceReasonCode(
            code="RC-COV-VACANCY",
            name="Vacancy Exclusion",
            description="Property vacant beyond policy vacancy provision",
            category="coverage",
        ),
        InsuranceReasonCode(
            code="RC-COV-PREEXISTING",
            name="Pre-existing Condition Exclusion",
            description="Health condition pre-existed coverage effective date",
            category="coverage",
        ),
        InsuranceReasonCode(
            code="RC-COV-WORKPLACE",
            name="Workplace Injury Coverage",
            description="Injury arose out of and in the course of employment",
            regulation_ref="WSIA s. 13",
            category="coverage",
        ),
    ]


# =============================================================================
# Evidence/Documentation Codes
# =============================================================================

def create_evidence_codes() -> list[InsuranceReasonCode]:
    return [
        InsuranceReasonCode(
            code="RC-EVD-COMPLETE",
            name="Documentation Complete",
            description="All required documentation received and verified",
            category="evidence",
        ),
        InsuranceReasonCode(
            code="RC-EVD-POLICE-MISSING",
            name="Police Report Missing",
            description="Police report not filed or not yet received",
            category="evidence",
        ),
        InsuranceReasonCode(
            code="RC-EVD-MEDICAL-MISSING",
            name="Medical Records Missing",
            description="Medical documentation not yet received",
            category="evidence",
        ),
        InsuranceReasonCode(
            code="RC-EVD-PHOTOS-MISSING",
            name="Photo Documentation Missing",
            description="Photos or damage documentation not provided",
            category="evidence",
        ),
        InsuranceReasonCode(
            code="RC-EVD-WITNESS-MISSING",
            name="Witness Statements Missing",
            description="Witness statements not yet obtained",
            category="evidence",
        ),
        InsuranceReasonCode(
            code="RC-EVD-ESTIMATE-PENDING",
            name="Repair Estimate Pending",
            description="Independent damage/repair estimate not yet received",
            category="evidence",
        ),
        InsuranceReasonCode(
            code="RC-EVD-IME-REQUIRED",
            name="Independent Medical Exam Required",
            description="IME needed to assess injury claims",
            category="evidence",
        ),
        InsuranceReasonCode(
            code="RC-EVD-EUO-REQUIRED",
            name="Examination Under Oath Required",
            description="EUO required to clarify inconsistencies",
            category="evidence",
        ),
    ]


# =============================================================================
# Regulatory Requirement Codes
# =============================================================================

def create_regulatory_codes() -> list[InsuranceReasonCode]:
    return [
        InsuranceReasonCode(
            code="RC-REG-FSRA-NOTICE",
            name="FSRA Notice Required",
            description="Regulatory notice required to FSRA",
            regulation_ref="Insurance Act (Ontario) s. 441",
            category="regulatory",
        ),
        InsuranceReasonCode(
            code="RC-REG-FSRA-COMPLAINT",
            name="FSRA Complaint File",
            description="Consumer complaint filed with FSRA",
            regulation_ref="FSRA Consumer Protection Framework",
            category="regulatory",
        ),
        InsuranceReasonCode(
            code="RC-REG-ADRQ",
            name="Alternative Dispute Resolution",
            description="Claim eligible for ADR process",
            regulation_ref="Insurance Act (Ontario) s. 280",
            category="regulatory",
        ),
        InsuranceReasonCode(
            code="RC-REG-PRIORITY",
            name="Priority Claims Processing",
            description="Claim qualifies for priority processing timeline",
            regulation_ref="SABS s. 51",
            category="regulatory",
        ),
        InsuranceReasonCode(
            code="RC-REG-AB-BENEFITS",
            name="Accident Benefits Applicable",
            description="Statutory accident benefits apply regardless of fault",
            regulation_ref="SABS O.Reg. 34/10",
            category="regulatory",
        ),
        InsuranceReasonCode(
            code="RC-REG-CLIMATE-EXPEDITE",
            name="Climate Event Expedited Processing",
            description="Declared climate event — expedited claims handling required",
            regulation_ref="FSRA Climate Adaptation Framework",
            category="regulatory",
        ),
        InsuranceReasonCode(
            code="RC-REG-MINOR-CAP",
            name="Minor Injury Cap Applied",
            description="Minor injury definition and cap applied",
            regulation_ref="SABS s. 3(1) Minor Injury Guideline",
            category="regulatory",
        ),
        InsuranceReasonCode(
            code="RC-REG-NONE",
            name="No Regulatory Action Required",
            description="No regulatory filing or notice required",
            category="regulatory",
        ),
    ]


# =============================================================================
# SIU Referral Codes
# =============================================================================

def create_siu_codes() -> list[InsuranceReasonCode]:
    return [
        InsuranceReasonCode(
            code="RC-SIU-REFER",
            name="SIU Referral",
            description="Claim referred to Special Investigations Unit",
            category="siu",
        ),
        InsuranceReasonCode(
            code="RC-SIU-FRAUD-RING",
            name="SIU — Fraud Ring Investigation",
            description="Claim linked to suspected organized fraud ring",
            regulation_ref="IBC Anti-Fraud Guidelines",
            category="siu",
        ),
        InsuranceReasonCode(
            code="RC-SIU-SURVEILLANCE",
            name="SIU — Surveillance Authorized",
            description="Surveillance authorized to verify claim",
            category="siu",
        ),
        InsuranceReasonCode(
            code="RC-SIU-FORENSIC",
            name="SIU — Forensic Investigation",
            description="Forensic investigation ordered (fire/accident)",
            category="siu",
        ),
        InsuranceReasonCode(
            code="RC-SIU-CLEARED",
            name="SIU — Investigation Cleared",
            description="SIU investigation found no fraud",
            category="siu",
        ),
        InsuranceReasonCode(
            code="RC-SIU-CONFIRMED",
            name="SIU — Fraud Confirmed",
            description="SIU investigation confirmed fraudulent claim",
            category="siu",
        ),
        InsuranceReasonCode(
            code="RC-SIU-CRIMINAL",
            name="SIU — Criminal Referral",
            description="Evidence sufficient for criminal fraud referral",
            regulation_ref="Criminal Code s. 380 (Fraud)",
            category="siu",
        ),
        InsuranceReasonCode(
            code="RC-SIU-IBC",
            name="SIU — IBC Database Flag",
            description="Claim flagged in IBC CANATICS database",
            regulation_ref="IBC CANATICS Program",
            category="siu",
        ),
    ]


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "InsuranceReasonCodeError",
    "InsuranceCodeNotFoundError",
    "InsuranceReasonCode",
    "InsuranceReasonCodeRegistry",
    "create_fraud_codes",
    "create_coverage_codes",
    "create_evidence_codes",
    "create_regulatory_codes",
    "create_siu_codes",
]
