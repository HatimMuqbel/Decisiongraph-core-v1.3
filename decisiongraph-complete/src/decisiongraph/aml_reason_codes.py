"""
DecisionGraph Banking/AML Precedent System: Reason Code Registry Module

This module implements reason code registries for AML/Banking decision workflows.
Reason codes provide standardized coding for decision rationale with regulatory
citations.

Key components:
- AMLReasonCode: Structured reason code with regulatory references
- AMLReasonCodeRegistry: Registry of codes by decision category
- Validation functions for code lookups

Registries Defined:
- decisiongraph:aml:txn:v1 - Transaction Monitoring (~25 codes)
- decisiongraph:aml:kyc:v1 - KYC Onboarding (~22 codes)
- decisiongraph:aml:report:v1 - Reporting (~12 codes)
- decisiongraph:aml:screening:v1 - Sanctions/Screening (~18 codes)
- decisiongraph:aml:monitoring:v1 - Ongoing Monitoring (~15 codes)

Total: ~92 unique reason codes

Example:
    >>> registry = AMLReasonCodeRegistry()
    >>> code = registry.get_code("RC-TXN-STRUCT")
    >>> print(code.name)  # "Structuring Indicators"
    >>> print(code.regulation_ref)  # "PCMLTFA Guidelines 3.1"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# =============================================================================
# Exceptions
# =============================================================================

class AMLReasonCodeError(Exception):
    """Base exception for AML reason code errors."""
    pass


class AMLCodeNotFoundError(AMLReasonCodeError):
    """Raised when a reason code is not found in the registry."""
    pass


class AMLRegistryNotFoundError(AMLReasonCodeError):
    """Raised when a registry is not found."""
    pass


# =============================================================================
# Reason Code
# =============================================================================

@dataclass
class AMLReasonCode:
    """
    Structured AML reason code with regulatory references.

    Reason codes provide standardized coding for decision rationale,
    enabling consistent precedent matching and audit trails.

    Attributes:
        code: Unique code identifier (e.g., "RC-TXN-STRUCT")
        name: Human-readable name (e.g., "Structuring Indicators")
        description: Detailed description of the code
        regulation_ref: Regulatory reference (e.g., "PCMLTFA Guidelines 3.1")
        red_flags: List of red flag indicators this code relates to
        category: Decision category (txn, kyc, report, screening, monitoring)
    """
    code: str
    name: str
    description: str
    regulation_ref: Optional[str] = None
    red_flags: list[str] = field(default_factory=list)
    category: str = ""

    def __post_init__(self) -> None:
        """Validate code on construction."""
        if not self.code:
            raise AMLReasonCodeError("code cannot be empty")
        if not self.name:
            raise AMLReasonCodeError("name cannot be empty")
        if not self.description:
            raise AMLReasonCodeError("description cannot be empty")

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
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

class AMLReasonCodeRegistry:
    """
    Registry of AML reason codes organized by category.

    Provides lookup and validation for reason codes used in
    AML/Banking decision workflows.

    Usage:
        >>> registry = AMLReasonCodeRegistry()
        >>> code = registry.get_code("RC-TXN-STRUCT")
        >>> codes = registry.get_codes_by_category("txn")
        >>> is_valid = registry.validate_code("RC-TXN-STRUCT")
    """

    def __init__(self) -> None:
        """Initialize with built-in codes."""
        self._codes: dict[str, AMLReasonCode] = {}
        self._by_category: dict[str, list[str]] = {}
        self._registries: dict[str, str] = {}  # registry_id -> description
        self._register_builtin_codes()

    def _register_builtin_codes(self) -> None:
        """Register all built-in AML reason codes."""
        # Transaction Monitoring
        for code in create_txn_monitoring_codes():
            self.register_code(code)
        self._registries["decisiongraph:aml:txn:v1"] = "Transaction Monitoring Codes"

        # KYC Onboarding
        for code in create_kyc_onboarding_codes():
            self.register_code(code)
        self._registries["decisiongraph:aml:kyc:v1"] = "KYC Onboarding Codes"

        # Reporting
        for code in create_reporting_codes():
            self.register_code(code)
        self._registries["decisiongraph:aml:report:v1"] = "Reporting Codes"

        # Sanctions/Screening
        for code in create_screening_codes():
            self.register_code(code)
        self._registries["decisiongraph:aml:screening:v1"] = "Sanctions/Screening Codes"

        # Ongoing Monitoring
        for code in create_monitoring_codes():
            self.register_code(code)
        self._registries["decisiongraph:aml:monitoring:v1"] = "Ongoing Monitoring Codes"

    def register_code(self, reason_code: AMLReasonCode) -> None:
        """
        Register a reason code.

        Args:
            reason_code: The AMLReasonCode to register
        """
        self._codes[reason_code.code] = reason_code

        # Index by category
        category = reason_code.category
        if category not in self._by_category:
            self._by_category[category] = []
        self._by_category[category].append(reason_code.code)

    def get_code(self, code: str) -> AMLReasonCode:
        """
        Get a reason code by its identifier.

        Args:
            code: The code identifier (e.g., "RC-TXN-STRUCT")

        Returns:
            The AMLReasonCode

        Raises:
            AMLCodeNotFoundError: If code not found
        """
        if code not in self._codes:
            raise AMLCodeNotFoundError(f"Reason code not found: {code}")
        return self._codes[code]

    def get_codes_by_category(self, category: str) -> list[AMLReasonCode]:
        """
        Get all reason codes for a category.

        Args:
            category: The category (txn, kyc, report, screening, monitoring)

        Returns:
            List of AMLReasonCode objects
        """
        codes = self._by_category.get(category, [])
        return [self._codes[code] for code in codes]

    def validate_code(self, code: str) -> bool:
        """
        Check if a code exists in the registry.

        Args:
            code: The code to validate

        Returns:
            True if code exists, False otherwise
        """
        return code in self._codes

    def validate_codes(self, codes: list[str]) -> list[str]:
        """
        Validate multiple codes, returning invalid ones.

        Args:
            codes: List of codes to validate

        Returns:
            List of invalid codes (empty if all valid)
        """
        return [code for code in codes if code not in self._codes]

    def list_codes(self) -> list[str]:
        """Return list of all registered code identifiers."""
        return list(self._codes.keys())

    def list_registries(self) -> list[str]:
        """Return list of all registry IDs."""
        return list(self._registries.keys())

    def count(self) -> int:
        """Return total number of registered codes."""
        return len(self._codes)


# =============================================================================
# Transaction Monitoring Codes
# =============================================================================

def create_txn_monitoring_codes() -> list[AMLReasonCode]:
    """Create transaction monitoring reason codes."""
    return [
        # Approvals
        AMLReasonCode(
            code="RC-TXN-NORMAL",
            name="Normal Transaction",
            description="Transaction consistent with customer profile and risk level",
            category="txn",
        ),
        AMLReasonCode(
            code="RC-TXN-VERIFIED",
            name="Source Verified",
            description="Source of funds verified and documented",
            category="txn",
        ),
        AMLReasonCode(
            code="RC-TXN-PROFILE-MATCH",
            name="Profile Consistent",
            description="Activity matches expected customer behavior",
            category="txn",
        ),
        # Structuring
        AMLReasonCode(
            code="RC-TXN-STRUCT",
            name="Structuring Indicators",
            description="Pattern suggests intentional threshold avoidance",
            regulation_ref="PCMLTFA Guidelines 3.1",
            red_flags=["just_below_threshold", "multiple_same_day", "round_amounts"],
            category="txn",
        ),
        AMLReasonCode(
            code="RC-TXN-STRUCT-MULTI",
            name="Multiple Transaction Structuring",
            description="Multiple transactions same day avoiding threshold",
            regulation_ref="FINTRAC Guidance FIN-2023-G01",
            category="txn",
        ),
        # High-risk jurisdiction
        AMLReasonCode(
            code="RC-TXN-FATF-BLACK",
            name="FATF Blacklist Country",
            description="Transaction involves FATF high-risk jurisdiction",
            regulation_ref="PCMLTFA Guidelines 4.2",
            category="txn",
        ),
        AMLReasonCode(
            code="RC-TXN-FATF-GREY",
            name="FATF Greylist Country",
            description="Transaction involves FATF increased monitoring jurisdiction",
            regulation_ref="PCMLTFA Guidelines 4.2",
            category="txn",
        ),
        AMLReasonCode(
            code="RC-TXN-CORRESP",
            name="Correspondent Banking Risk",
            description="Transaction through high-risk correspondent relationship",
            regulation_ref="PCMLTFA Section 9.4",
            category="txn",
        ),
        # PEP
        AMLReasonCode(
            code="RC-TXN-PEP",
            name="PEP Transaction",
            description="Transaction by Politically Exposed Person",
            regulation_ref="PCMLTFA Section 9.6",
            category="txn",
        ),
        AMLReasonCode(
            code="RC-TXN-PEP-EDD",
            name="PEP - EDD Complete",
            description="PEP transaction with completed enhanced due diligence",
            category="txn",
        ),
        AMLReasonCode(
            code="RC-TXN-PEP-RCA",
            name="PEP Related Party",
            description="Transaction by PEP family member or close associate",
            regulation_ref="PCMLTFA Section 9.6(3)",
            category="txn",
        ),
        # Crypto
        AMLReasonCode(
            code="RC-TXN-CRYPTO-UNREG",
            name="Unregulated Crypto Exchange",
            description="Funds from/to unregulated virtual currency exchange",
            regulation_ref="PCMLTFA Part 1.1",
            category="txn",
        ),
        AMLReasonCode(
            code="RC-TXN-CRYPTO-UNHOSTED",
            name="Unhosted Wallet",
            description="Transaction involves unhosted/private wallet",
            category="txn",
        ),
        AMLReasonCode(
            code="RC-TXN-CRYPTO-MIX",
            name="Mixer/Tumbler Indicators",
            description="Transaction shows signs of mixing service usage",
            category="txn",
        ),
        # Layering
        AMLReasonCode(
            code="RC-TXN-LAYER",
            name="Layering Indicators",
            description="Pattern suggests layering to obscure origin",
            red_flags=["rapid_movement", "multiple_jurisdictions", "no_business_purpose"],
            category="txn",
        ),
        AMLReasonCode(
            code="RC-TXN-RAPID",
            name="Rapid Movement",
            description="Funds moved through account within 24-72 hours",
            category="txn",
        ),
        AMLReasonCode(
            code="RC-TXN-ROUNDTRIP",
            name="Round-Trip Transaction",
            description="Funds returned to origin with no apparent purpose",
            category="txn",
        ),
        # Unusual
        AMLReasonCode(
            code="RC-TXN-UNUSUAL",
            name="Unusual Pattern",
            description="Activity inconsistent with stated purpose or profile",
            category="txn",
        ),
        AMLReasonCode(
            code="RC-TXN-DEVIATION",
            name="Profile Deviation",
            description="Significant deviation from established transaction pattern",
            category="txn",
        ),
        # Trade-based
        AMLReasonCode(
            code="RC-TXN-TRADE-ML",
            name="Trade-Based ML Indicators",
            description="Transaction shows trade-based money laundering patterns",
            red_flags=["over_invoicing", "under_invoicing", "phantom_shipment"],
            category="txn",
        ),
        # Blocks
        AMLReasonCode(
            code="RC-TXN-SANCTION",
            name="Sanctions Match",
            description="Party matches sanctioned entity",
            regulation_ref="SEMA, UN Act, JMLSG",
            category="txn",
        ),
        AMLReasonCode(
            code="RC-TXN-BLOCK-RISK",
            name="Unacceptable Risk",
            description="Transaction risk exceeds acceptable threshold",
            category="txn",
        ),
        # SAR history
        AMLReasonCode(
            code="RC-TXN-SAR-HISTORY",
            name="Prior SAR History",
            description="Customer has prior SARs filed requiring enhanced monitoring",
            regulation_ref="FINTRAC:EnhancedMonitoring",
            category="txn",
        ),
        AMLReasonCode(
            code="RC-TXN-SAR-EXIT",
            name="SAR Pattern - Exit Review",
            description="Pattern of SARs indicates potential exit consideration",
            regulation_ref="FINTRAC:PatternOfSuspicion, Policy:ExitConsideration",
            category="txn",
        ),
        # Prior closure
        AMLReasonCode(
            code="RC-TXN-PRIOR-CLOSURE",
            name="Prior Account Closure",
            description="Customer previously exited for AML concerns",
            regulation_ref="FINTRAC:ExitedCustomer, Policy:EnhancedReview",
            category="txn",
        ),
    ]


# =============================================================================
# KYC Onboarding Codes
# =============================================================================

def create_kyc_onboarding_codes() -> list[AMLReasonCode]:
    """Create KYC onboarding reason codes."""
    return [
        # Approvals
        AMLReasonCode(
            code="RC-KYC-COMPLETE",
            name="KYC Complete",
            description="All KYC requirements satisfied",
            category="kyc",
        ),
        AMLReasonCode(
            code="RC-KYC-LOW-RISK",
            name="Low Risk Customer",
            description="Customer meets low-risk criteria",
            category="kyc",
        ),
        AMLReasonCode(
            code="RC-KYC-EDD-COMPLETE",
            name="EDD Complete",
            description="Enhanced due diligence satisfactorily completed",
            category="kyc",
        ),
        AMLReasonCode(
            code="RC-KYC-SENIOR-APPROVED",
            name="Senior Management Approval",
            description="High-risk relationship approved by senior management",
            regulation_ref="PCMLTFA Section 9.6(4)",
            category="kyc",
        ),
        # Holds
        AMLReasonCode(
            code="RC-KYC-PENDING-EDD",
            name="Pending EDD",
            description="Enhanced due diligence required before approval",
            regulation_ref="PCMLTFA Section 9.6",
            category="kyc",
        ),
        AMLReasonCode(
            code="RC-KYC-PENDING-ID",
            name="Pending ID Verification",
            description="Identity verification incomplete",
            category="kyc",
        ),
        AMLReasonCode(
            code="RC-KYC-PENDING-BO",
            name="Pending Beneficial Owner",
            description="Beneficial ownership verification incomplete",
            regulation_ref="PCMLTFA Section 11.1",
            category="kyc",
        ),
        AMLReasonCode(
            code="RC-KYC-PENDING-SOW",
            name="Pending Source of Wealth",
            description="Source of wealth documentation required",
            category="kyc",
        ),
        AMLReasonCode(
            code="RC-KYC-PENDING-ADDR",
            name="Pending Address Verification",
            description="Address verification incomplete",
            category="kyc",
        ),
        AMLReasonCode(
            code="RC-KYC-EXPIRED-ID",
            name="Expired ID",
            description="Identification document has expired",
            regulation_ref="FINTRAC:ValidID",
            category="kyc",
        ),
        # PEP specific
        AMLReasonCode(
            code="RC-KYC-PEP-APPROVED",
            name="PEP Approved",
            description="PEP relationship approved with controls",
            category="kyc",
        ),
        AMLReasonCode(
            code="RC-KYC-PEP-DECLINED",
            name="PEP Declined",
            description="PEP relationship outside risk appetite",
            category="kyc",
        ),
        # High-risk industry
        AMLReasonCode(
            code="RC-KYC-MSB",
            name="Money Service Business",
            description="MSB requiring enhanced controls",
            regulation_ref="PCMLTFA Section 5",
            category="kyc",
        ),
        AMLReasonCode(
            code="RC-KYC-CRYPTO-VASP",
            name="Virtual Asset Service Provider",
            description="Crypto business requiring enhanced controls",
            regulation_ref="PCMLTFA Part 1.1",
            category="kyc",
        ),
        # Shell company
        AMLReasonCode(
            code="RC-KYC-SHELL",
            name="Shell Company Indicators",
            description="Entity shows shell company characteristics",
            red_flags=["nominee_directors", "registered_agent_only", "no_physical_presence"],
            category="kyc",
        ),
        AMLReasonCode(
            code="RC-KYC-SHELL-DECLINE",
            name="Shell Company Decline",
            description="Multiple shell indicators - outside risk appetite",
            regulation_ref="FINTRAC:ShellCompany, Policy:RiskAppetite",
            category="kyc",
        ),
        # Adverse media
        AMLReasonCode(
            code="RC-KYC-ADVERSE-MINOR",
            name="Minor Adverse Media",
            description="Adverse media - low severity, mitigated",
            category="kyc",
        ),
        AMLReasonCode(
            code="RC-KYC-ADVERSE-MAJOR",
            name="Major Adverse Media",
            description="Significant adverse media requiring decline",
            category="kyc",
        ),
        # Declines
        AMLReasonCode(
            code="RC-KYC-MISSING-ID",
            name="Missing ID",
            description="Required identification not provided",
            category="kyc",
        ),
        AMLReasonCode(
            code="RC-KYC-SANCTION",
            name="Sanctions Match",
            description="Customer matches sanctioned entity",
            regulation_ref="SEMA",
            category="kyc",
        ),
        AMLReasonCode(
            code="RC-KYC-OUTSIDE-APPETITE",
            name="Outside Risk Appetite",
            description="Customer risk exceeds institutional appetite",
            category="kyc",
        ),
        # SAR history
        AMLReasonCode(
            code="RC-KYC-SAR-HISTORY",
            name="Prior SAR History",
            description="Pattern of prior SARs indicates unacceptable risk",
            regulation_ref="Policy:RiskAppetite, FINTRAC:PatternOfSuspicion",
            category="kyc",
        ),
    ]


# =============================================================================
# Reporting Codes
# =============================================================================

def create_reporting_codes() -> list[AMLReasonCode]:
    """Create reporting reason codes."""
    return [
        # LCTR
        AMLReasonCode(
            code="RC-RPT-LCTR",
            name="LCTR Required",
            description="Large cash transaction over $10,000",
            regulation_ref="PCMLTFA Section 9",
            category="report",
        ),
        AMLReasonCode(
            code="RC-RPT-LCTR-MULTI",
            name="LCTR - Multiple Transactions",
            description="Multiple cash transactions totaling over $10,000",
            regulation_ref="PCMLTFA Section 9(1)",
            category="report",
        ),
        # STR
        AMLReasonCode(
            code="RC-RPT-STR",
            name="STR Required",
            description="Reasonable grounds to suspect ML/TF",
            regulation_ref="PCMLTFA Section 7",
            category="report",
        ),
        AMLReasonCode(
            code="RC-RPT-STR-STRUCT",
            name="STR - Structuring",
            description="Suspected structuring to avoid reporting",
            category="report",
        ),
        AMLReasonCode(
            code="RC-RPT-STR-UNUSUAL",
            name="STR - Unusual Activity",
            description="Activity unusual for customer profile",
            category="report",
        ),
        AMLReasonCode(
            code="RC-RPT-STR-3RD",
            name="STR - Third Party",
            description="Suspected third party involvement",
            category="report",
        ),
        AMLReasonCode(
            code="RC-RPT-STR-LAYER",
            name="STR - Layering",
            description="Suspected layering activity",
            category="report",
        ),
        AMLReasonCode(
            code="RC-RPT-STR-SOF",
            name="STR - Source of Funds",
            description="Unable to verify source of funds",
            category="report",
        ),
        # TPR
        AMLReasonCode(
            code="RC-RPT-TPR",
            name="Terrorist Property Report",
            description="Property of listed terrorist entity",
            regulation_ref="Criminal Code Section 83.1",
            category="report",
        ),
        # No report
        AMLReasonCode(
            code="RC-RPT-NONE",
            name="No Report Required",
            description="No reporting threshold met",
            category="report",
        ),
        AMLReasonCode(
            code="RC-RPT-NONE-EXPLAINED",
            name="Unusual Activity Explained",
            description="Initially unusual activity satisfactorily explained",
            category="report",
        ),
        # Reporting required with approve
        AMLReasonCode(
            code="RC-RPT-APPROVE-REPORT",
            name="Approve with Reporting",
            description="Transaction approved but reporting required",
            regulation_ref="FINTRAC:Reporting",
            category="report",
        ),
    ]


# =============================================================================
# Sanctions/Screening Codes
# =============================================================================

def create_screening_codes() -> list[AMLReasonCode]:
    """Create sanctions/screening reason codes."""
    return [
        # True positive
        AMLReasonCode(
            code="RC-SCR-SANCTION",
            name="Sanctions Match Confirmed",
            description="Entity confirmed on sanctions list",
            regulation_ref="SEMA, OFAC, UN",
            category="screening",
        ),
        AMLReasonCode(
            code="RC-SCR-OFAC",
            name="OFAC SDN Match",
            description="Match to OFAC Specially Designated Nationals list",
            category="screening",
        ),
        AMLReasonCode(
            code="RC-SCR-UN",
            name="UN Sanctions Match",
            description="Match to UN consolidated sanctions list",
            category="screening",
        ),
        AMLReasonCode(
            code="RC-SCR-SEMA",
            name="Canadian SEMA Match",
            description="Match to Canadian sanctions under SEMA",
            category="screening",
        ),
        AMLReasonCode(
            code="RC-SCR-EU",
            name="EU Sanctions Match",
            description="Match to EU consolidated sanctions list",
            category="screening",
        ),
        # False positive
        AMLReasonCode(
            code="RC-SCR-FP",
            name="False Positive",
            description="Screening match determined to be false positive",
            category="screening",
        ),
        AMLReasonCode(
            code="RC-SCR-FP-NAME",
            name="False Positive - Common Name",
            description="Match due to common name, different person confirmed",
            category="screening",
        ),
        AMLReasonCode(
            code="RC-SCR-FP-DOB",
            name="False Positive - DOB Mismatch",
            description="Name similar but date of birth does not match",
            category="screening",
        ),
        AMLReasonCode(
            code="RC-SCR-FP-PARTIAL",
            name="False Positive - Partial Match",
            description="Partial name match, secondary identifiers confirm different person",
            category="screening",
        ),
        # Ownership
        AMLReasonCode(
            code="RC-SCR-OWN-50",
            name="Sanctioned Ownership >50%",
            description="Entity >50% owned by sanctioned party",
            regulation_ref="OFAC 50% Rule",
            category="screening",
        ),
        AMLReasonCode(
            code="RC-SCR-OWN-CLEAR",
            name="Ownership Below Threshold",
            description="Sanctioned ownership below 50% threshold",
            category="screening",
        ),
        # De-listed
        AMLReasonCode(
            code="RC-SCR-DELIST-CLEAR",
            name="De-listed - Clear",
            description="Entity removed from sanctions list, cleared",
            category="screening",
        ),
        AMLReasonCode(
            code="RC-SCR-DELIST-MONITOR",
            name="De-listed - Enhanced Monitoring",
            description="Recently de-listed, enhanced monitoring applied",
            category="screening",
        ),
        # Secondary
        AMLReasonCode(
            code="RC-SCR-SECONDARY",
            name="Secondary Sanctions Exposure",
            description="Transaction may trigger secondary sanctions",
            category="screening",
        ),
        # PEP
        AMLReasonCode(
            code="RC-SCR-PEP-CONF",
            name="PEP Status Confirmed",
            description="Politically exposed person status confirmed",
            category="screening",
        ),
        AMLReasonCode(
            code="RC-SCR-PEP-FP",
            name="PEP False Positive",
            description="PEP screening match is false positive",
            category="screening",
        ),
        # Adverse media
        AMLReasonCode(
            code="RC-SCR-ADVERSE",
            name="Adverse Media Confirmed",
            description="Adverse media finding confirmed and relevant",
            category="screening",
        ),
        # Clear
        AMLReasonCode(
            code="RC-SCR-CLEAR",
            name="Screening Clear",
            description="No matches found in sanctions/PEP/adverse media screening",
            category="screening",
        ),
    ]


# =============================================================================
# Ongoing Monitoring Codes
# =============================================================================

def create_monitoring_codes() -> list[AMLReasonCode]:
    """Create ongoing monitoring reason codes."""
    return [
        # Activity triggers
        AMLReasonCode(
            code="RC-MON-SPIKE",
            name="Activity Spike",
            description="Significant increase in transaction activity",
            category="monitoring",
        ),
        AMLReasonCode(
            code="RC-MON-NEW-PATTERN",
            name="New Transaction Pattern",
            description="Previously unseen transaction behavior",
            category="monitoring",
        ),
        AMLReasonCode(
            code="RC-MON-NEW-JURIS",
            name="New Jurisdiction",
            description="Transactions to previously unseen jurisdiction",
            category="monitoring",
        ),
        # Periodic review
        AMLReasonCode(
            code="RC-MON-REVIEW-CLEAR",
            name="Periodic Review - Clear",
            description="Annual review completed, no concerns",
            category="monitoring",
        ),
        AMLReasonCode(
            code="RC-MON-REVIEW-UPGRADE",
            name="Risk Upgrade",
            description="Customer risk rating increased",
            category="monitoring",
        ),
        AMLReasonCode(
            code="RC-MON-REVIEW-DOWNGRADE",
            name="Risk Downgrade",
            description="Customer risk rating decreased",
            category="monitoring",
        ),
        AMLReasonCode(
            code="RC-MON-KYC-REFRESH",
            name="KYC Refresh Required",
            description="Customer due for KYC information update",
            category="monitoring",
        ),
        # Profile changes
        AMLReasonCode(
            code="RC-MON-PROFILE-CHG",
            name="Profile Change Review",
            description="Customer profile change requires review",
            category="monitoring",
        ),
        AMLReasonCode(
            code="RC-MON-BO-CHG",
            name="Beneficial Owner Change",
            description="Change in beneficial ownership structure",
            category="monitoring",
        ),
        # Dormant
        AMLReasonCode(
            code="RC-MON-DORM-REACT",
            name="Dormant Reactivation",
            description="Previously dormant account reactivated",
            category="monitoring",
        ),
        AMLReasonCode(
            code="RC-MON-DORM-SUSP",
            name="Suspicious Reactivation",
            description="Dormant account reactivation shows suspicious patterns",
            category="monitoring",
        ),
        # Exit
        AMLReasonCode(
            code="RC-MON-EXIT",
            name="Relationship Exit",
            description="Decision to terminate customer relationship",
            category="monitoring",
        ),
        AMLReasonCode(
            code="RC-MON-EXIT-RISK",
            name="Risk-Based Exit",
            description="Exit due to unacceptable risk level",
            category="monitoring",
        ),
        AMLReasonCode(
            code="RC-MON-EXIT-SAR",
            name="SAR-Related Exit",
            description="Exit following suspicious activity reporting",
            category="monitoring",
        ),
        AMLReasonCode(
            code="RC-MON-EXIT-REG",
            name="Regulatory Exit",
            description="Exit due to regulatory requirement",
            category="monitoring",
        ),
    ]


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Exceptions
    "AMLReasonCodeError",
    "AMLCodeNotFoundError",
    "AMLRegistryNotFoundError",

    # Data class
    "AMLReasonCode",

    # Registry
    "AMLReasonCodeRegistry",

    # Code factory functions
    "create_txn_monitoring_codes",
    "create_kyc_onboarding_codes",
    "create_reporting_codes",
    "create_screening_codes",
    "create_monitoring_codes",
]
