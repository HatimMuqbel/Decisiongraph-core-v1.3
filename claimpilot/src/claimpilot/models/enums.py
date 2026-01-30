"""
ClaimPilot Enumerations

All enumeration types used throughout the ClaimPilot system.
Organized by domain area for clarity.

All enums inherit from (str, Enum) for JSON serialization compatibility.
"""
from __future__ import annotations

from enum import Enum


# =============================================================================
# Line of Business
# =============================================================================

class LineOfBusiness(str, Enum):
    """Insurance lines of business supported by ClaimPilot."""
    AUTO = "auto"
    PROPERTY = "property"
    HEALTH = "health"
    WORKERS_COMP = "workers_comp"
    LIABILITY = "liability"
    MARINE = "marine"
    LIFE = "life"
    PROFESSIONAL = "professional"  # E&O, D&O, etc.
    CYBER = "cyber"
    OTHER = "other"


# =============================================================================
# Claimant Types
# =============================================================================

class ClaimantType(str, Enum):
    """Relationship of claimant to the policy."""
    INSURED = "insured"
    NAMED_INSURED = "named_insured"
    ADDITIONAL_INSURED = "additional_insured"
    THIRD_PARTY = "third_party"
    CLAIMANT = "claimant"  # Generic
    BENEFICIARY = "beneficiary"
    ASSIGNEE = "assignee"


# =============================================================================
# Disposition Types
# =============================================================================

class DispositionType(str, Enum):
    """
    Possible claim disposition recommendations/outcomes.

    Note: These are RECOMMENDATIONS from ClaimPilot.
    The human adjuster makes the final decision.
    """
    PAY = "pay"                        # Full payment recommended
    DENY = "deny"                      # Denial recommended
    PARTIAL = "partial"                # Partial payment recommended
    ESCALATE = "escalate"              # Requires higher authority
    REQUEST_INFO = "request_info"      # Need more information
    HOLD = "hold"                      # Hold for investigation
    REFER_SIU = "refer_siu"            # Refer to Special Investigations
    SUBROGATION = "subrogation"        # Pursue subrogation
    RESERVE_ONLY = "reserve_only"      # Set reserve, no payment yet
    CLOSE_NO_PAY = "close_no_pay"      # Close without payment


# =============================================================================
# Recommendation Certainty
# =============================================================================

class RecommendationCertainty(str, Enum):
    """
    Confidence level in the recommendation.

    This helps adjusters understand when to apply more scrutiny.
    """
    HIGH = "high"                      # Clear-cut case
    MEDIUM = "medium"                  # Some ambiguity but solid recommendation
    LOW = "low"                        # Significant uncertainty, needs review
    REQUIRES_JUDGMENT = "requires_judgment"  # Cannot recommend, human must decide


# =============================================================================
# Fact Source and Certainty
# =============================================================================

class FactSource(str, Enum):
    """Origin of a fact in the claim context."""
    POLICY_SYSTEM = "policy_system"      # From insurer's policy admin
    CLAIM_INTAKE = "claim_intake"        # From FNOL / intake
    ADJUSTER_INPUT = "adjuster_input"    # Adjuster entered
    DOCUMENT = "document"                # Extracted from document
    EXTERNAL_SYSTEM = "external_system"  # API / integration
    CLAIMANT_STATEMENT = "claimant_statement"
    WITNESS_STATEMENT = "witness_statement"
    EXPERT_REPORT = "expert_report"
    POLICE_REPORT = "police_report"
    MEDICAL_RECORD = "medical_record"
    DERIVED = "derived"                  # Computed from other facts


class FactCertainty(str, Enum):
    """Confidence level in a fact."""
    CONFIRMED = "confirmed"              # Verified, high confidence
    REPORTED = "reported"                # Stated but not verified
    INFERRED = "inferred"                # Derived from other facts
    DISPUTED = "disputed"                # Conflicting information
    UNKNOWN = "unknown"                  # Not yet determined


# =============================================================================
# Evidence Types and Status
# =============================================================================

class EvidenceStatus(str, Enum):
    """Status of an evidence item."""
    REQUESTED = "requested"
    PENDING = "pending"                  # Waiting for receipt
    RECEIVED = "received"
    UNDER_REVIEW = "under_review"
    VERIFIED = "verified"
    REJECTED = "rejected"                # Did not meet requirements
    NOT_APPLICABLE = "not_applicable"
    WAIVED = "waived"                    # Requirement waived


class GateStrictness(str, Enum):
    """
    Evidence gate strictness levels.

    Separates "block recommendation" from "block finalization" per design spec.
    """
    BLOCKING_RECOMMENDATION = "blocking_recommendation"  # Can't recommend without
    BLOCKING_FINALIZATION = "blocking_finalization"      # Can recommend, can't finalize
    RECOMMENDED = "recommended"                          # Proceed with warning
    OPTIONAL = "optional"                                # Nice to have


# =============================================================================
# Authority Types
# =============================================================================

class AuthorityType(str, Enum):
    """Types of authorities that can be cited."""
    POLICY_WORDING = "policy_wording"
    REGULATION = "regulation"
    STATUTE = "statute"
    INTERNAL_GUIDELINE = "internal_guideline"
    INDUSTRY_STANDARD = "industry_standard"
    CASE_LAW = "case_law"
    REGULATOR_BULLETIN = "regulator_bulletin"
    INTERNAL_MEMO = "internal_memo"
    TRAINING_MATERIAL = "training_material"


# =============================================================================
# Precedent Types
# =============================================================================

class PrecedentOutcome(str, Enum):
    """What happened with a precedent case."""
    UPHELD = "upheld"                          # Recommendation followed, no dispute
    OVERTURNED_INTERNAL = "overturned_internal"  # Changed on internal review
    OVERTURNED_EXTERNAL = "overturned_external"  # Changed by regulator/court
    SETTLED = "settled"
    PENDING = "pending"                        # Not yet resolved
    UNKNOWN = "unknown"


# =============================================================================
# Timeline Types
# =============================================================================

class TimelineAnchor(str, Enum):
    """Reference point for timeline calculations."""
    LOSS_DATE = "loss_date"
    REPORT_DATE = "report_date"
    ACKNOWLEDGMENT_DATE = "acknowledgment_date"
    LAST_ACTIVITY_DATE = "last_activity_date"
    EVIDENCE_RECEIVED_DATE = "evidence_received_date"
    COVERAGE_DECISION_DATE = "coverage_decision_date"
    CLAIM_ASSIGNED_DATE = "claim_assigned_date"


class TimelineEventType(str, Enum):
    """Types of timeline events."""
    ACKNOWLEDGE = "acknowledge"
    REQUEST_INFO = "request_info"
    COVERAGE_DECISION_DUE = "coverage_decision_due"
    PAYMENT_DUE = "payment_due"
    DENIAL_NOTICE_DUE = "denial_notice_due"
    APPEAL_WINDOW_OPENS = "appeal_window_opens"
    APPEAL_WINDOW_CLOSES = "appeal_window_closes"
    REGULATORY_REPORT_DUE = "regulatory_report_due"
    STATUTE_OF_LIMITATIONS = "statute_of_limitations"
    RESERVATION_OF_RIGHTS_DUE = "reservation_of_rights_due"


# =============================================================================
# Condition Operators
# =============================================================================

class ConditionOperator(str, Enum):
    """Operators for condition evaluation."""
    # Logical operators (for composing conditions)
    AND = "and"
    OR = "or"
    NOT = "not"

    # Comparison operators (for predicates)
    EQ = "eq"                # Equal
    NE = "ne"                # Not equal
    GT = "gt"                # Greater than
    LT = "lt"                # Less than
    GTE = "gte"              # Greater than or equal
    LTE = "lte"              # Less than or equal
    IN = "in"                # In list
    NOT_IN = "not_in"        # Not in list
    CONTAINS = "contains"    # String/list contains
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES = "matches"      # Regex match
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"
    BETWEEN = "between"      # Value between two bounds (inclusive)


# =============================================================================
# Reasoning Step Types
# =============================================================================

class ReasoningStepType(str, Enum):
    """Types of steps in the reasoning chain."""
    COVERAGE_CHECK = "coverage_check"
    PRECONDITION_CHECK = "precondition_check"
    EXCLUSION_EVALUATION = "exclusion_evaluation"
    EVIDENCE_GATE = "evidence_gate"
    TIMELINE_CHECK = "timeline_check"
    AUTHORITY_LOOKUP = "authority_lookup"
    PRECEDENT_SEARCH = "precedent_search"
    LIMIT_CHECK = "limit_check"
    DEDUCTIBLE_CALCULATION = "deductible_calculation"
    ESCALATION_CHECK = "escalation_check"
    FINAL_DETERMINATION = "final_determination"


class ReasoningStepResult(str, Enum):
    """Result of a reasoning step."""
    PASSED = "passed"
    FAILED = "failed"
    UNCERTAIN = "uncertain"       # Could not determine
    NOT_APPLICABLE = "not_applicable"
    SKIPPED = "skipped"           # Skipped due to earlier failure


# =============================================================================
# Seal/Audit Status
# =============================================================================

class SealStatus(str, Enum):
    """Status of record sealing for audit."""
    UNSEALED = "unsealed"         # Can still be modified
    SEALED = "sealed"             # Immutable, hash computed
    VERIFIED = "verified"         # Seal verified by third party
