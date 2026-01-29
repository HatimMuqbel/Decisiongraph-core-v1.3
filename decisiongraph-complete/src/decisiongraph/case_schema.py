"""
case_schema.py - Financial Crime Case Schema v1

Scope: KYC + AML + EDD + Sanctions (one Financial Crime department)
Out of scope: Credit, Insurance, HR (different buyers, different regulations)

This schema supports the full Financial Crime lifecycle:
- KYC/Onboarding
- Ongoing Due Diligence (CDD/EDD)
- Transaction Monitoring (AML)
- Sanctions/PEP Screening
- Periodic Reviews

Design principles:
- Universal across Financial Crime case types
- Entities are nodes, relationships are edges (graph-native)
- Evidence is shared across case types
- Assertions bridge KYC → AML → EDD
- Sensitivity/access tags enable future RBAC without baking it in
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Union


# ============================================================================
# ENUMS - Case Classification
# ============================================================================

class CaseType(Enum):
    """
    What kind of case - matches how banks organize work.
    One Financial Crime department, five case types.
    """
    KYC_ONBOARDING = "kyc_onboarding"      # New customer intake
    KYC_REFRESH = "kyc_refresh"            # Periodic review
    AML_ALERT = "aml_alert"                # Transaction monitoring hit
    EDD_REVIEW = "edd_review"              # Enhanced due diligence
    SANCTIONS_MATCH = "sanctions_match"    # Screening hit


class CasePhase(Enum):
    """
    Where you are in the lifecycle - drives gating and SLAs.
    Universal across all case types.
    Maps to JUDGMENT + REVIEW_GATE logic in DecisionGraph.
    """
    INTAKE = "intake"                      # Case opened, awaiting triage
    EVIDENCE_GATHERING = "evidence_gathering"  # Collecting docs/data
    ANALYSIS = "analysis"                  # Analyst review in progress
    DECISION_PENDING = "decision_pending"  # Awaiting senior review
    DECIDED = "decided"                    # Decision made, awaiting action
    CLOSED = "closed"                      # Case complete
    LEGAL_HOLD = "legal_hold"              # Frozen for legal/regulatory


# ============================================================================
# ENUMS - Data Classification
# ============================================================================

class Sensitivity(Enum):
    """
    Data sensitivity level - enables future access control.
    Don't solve RBAC here, just tag for enforcement layer.
    """
    PUBLIC = "public"           # No restrictions
    INTERNAL = "internal"       # Internal use only
    CONFIDENTIAL = "confidential"  # Need-to-know basis
    RESTRICTED = "restricted"   # Highest protection (PII, SAR details)


# ============================================================================
# ENUMS - Entity Classification
# ============================================================================

class EntityType(Enum):
    INDIVIDUAL = "individual"
    ORGANIZATION = "organization"


class RiskRating(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PROHIBITED = "prohibited"


class CustomerStatus(Enum):
    PROSPECT = "prospect"
    ACTIVE = "active"
    DORMANT = "dormant"
    EXITED = "exited"
    BLOCKED = "blocked"


class PEPCategory(Enum):
    """Canadian PEP categories (PCMLTFR)."""
    NONE = "none"
    DPEP = "dpep"              # Domestic PEP
    FPEP = "fpep"              # Foreign PEP
    HIO = "hio"                # Head of International Org
    FAMILY = "family"          # Family member of PEP
    ASSOCIATE = "associate"    # Close associate of PEP


# ============================================================================
# ENUMS - Relationship Types
# ============================================================================

class RelationshipType(Enum):
    """
    Edge types between entities.
    BeneficialOwner is a relationship, not a separate entity.
    """
    # Ownership/Control
    UBO = "ubo"                    # Ultimate Beneficial Owner
    SHAREHOLDER = "shareholder"   # Direct shareholder
    DIRECTOR = "director"         # Board director
    OFFICER = "officer"           # Corporate officer
    SIGNATORY = "signatory"       # Authorized signatory
    CONTROL = "control"           # Control without ownership

    # Account relationships
    ACCOUNT_HOLDER = "account_holder"
    JOINT_HOLDER = "joint_holder"
    POWER_OF_ATTORNEY = "poa"

    # Personal relationships (for PEP family/associate)
    FAMILY_MEMBER = "family_member"
    CLOSE_ASSOCIATE = "close_associate"

    # Corporate structure
    PARENT_COMPANY = "parent_company"
    SUBSIDIARY = "subsidiary"
    AFFILIATE = "affiliate"


# ============================================================================
# ENUMS - Evidence Classification
# ============================================================================

class EvidenceType(Enum):
    """Evidence types shared across KYC and AML."""
    # Identity
    GOVERNMENT_ID = "government_id"
    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"

    # Address
    UTILITY_BILL = "utility_bill"
    BANK_STATEMENT = "bank_statement"
    TAX_DOCUMENT = "tax_document"

    # Source of Wealth/Funds
    EMPLOYMENT_LETTER = "employment_letter"
    FINANCIAL_STATEMENTS = "financial_statements"
    INHERITANCE_DOCS = "inheritance_docs"
    SALE_PROCEEDS = "sale_proceeds"

    # Corporate
    CERTIFICATE_OF_INCORPORATION = "cert_of_inc"
    ARTICLES_OF_ASSOCIATION = "articles"
    SHAREHOLDER_REGISTER = "shareholder_register"
    BOARD_RESOLUTION = "board_resolution"
    CORPORATE_STRUCTURE_CHART = "corp_structure"

    # Screening
    SANCTIONS_RESULT = "sanctions_result"
    PEP_RESULT = "pep_result"
    ADVERSE_MEDIA = "adverse_media"

    # AML
    TRANSACTION_RECORDS = "transaction_records"
    ALERT_DETAILS = "alert_details"
    ANALYST_NOTES = "analyst_notes"
    CUSTOMER_EXPLANATION = "customer_explanation"

    # Other
    OTHER = "other"


# ============================================================================
# BASE CLASSES
# ============================================================================

@dataclass(kw_only=True)
class Tagged:
    """
    Mixin for sensitivity and access control.
    Enables future RBAC without baking it into schema.
    """
    sensitivity: Sensitivity = Sensitivity.INTERNAL
    access_tags: list[str] = field(default_factory=lambda: ["fincrime"])


# ============================================================================
# ENTITIES (nodes in the graph)
# ============================================================================

@dataclass
class Address:
    """Physical or mailing address."""
    line1: str
    city: str
    country: str  # ISO 3166-1 alpha-2
    line2: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    address_type: str = "residential"  # residential, business, mailing
    verified: bool = False
    verified_date: Optional[date] = None


@dataclass(kw_only=True)
class Individual(Tagged):
    """
    Natural person - customer, UBO, counterparty, or related party.
    This is an entity node, not a relationship.
    """
    id: str
    given_name: str
    family_name: str
    date_of_birth: Optional[date] = None
    nationality: Optional[str] = None  # ISO 3166-1 alpha-2
    country_of_residence: Optional[str] = None
    tax_id: Optional[str] = None
    occupation: Optional[str] = None
    employer: Optional[str] = None
    pep_status: PEPCategory = PEPCategory.NONE
    risk_rating: Optional[RiskRating] = None
    customer_status: Optional[CustomerStatus] = None
    addresses: list[Address] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.given_name} {self.family_name}"


@dataclass(kw_only=True)
class Organization(Tagged):
    """
    Legal entity - corporate customer, counterparty, or related party.
    This is an entity node, not a relationship.
    """
    id: str
    legal_name: str
    entity_type: str  # corporation, partnership, trust, foundation, etc.
    jurisdiction: str  # ISO 3166-1 alpha-2
    registration_number: Optional[str] = None
    date_of_incorporation: Optional[date] = None
    industry_code: Optional[str] = None  # NAICS or SIC
    industry_description: Optional[str] = None
    website: Optional[str] = None
    risk_rating: Optional[RiskRating] = None
    customer_status: Optional[CustomerStatus] = None
    addresses: list[Address] = field(default_factory=list)


@dataclass(kw_only=True)
class Account(Tagged):
    """
    Financial account - shared across KYC and AML.
    This is an entity node; holder relationships are edges.
    """
    id: str
    account_number: str
    account_type: str  # checking, savings, investment, loan, etc.
    currency: str  # ISO 4217
    opened_date: Optional[date] = None
    closed_date: Optional[date] = None
    status: str = "active"  # active, dormant, closed, frozen
    branch_code: Optional[str] = None
    product_code: Optional[str] = None


# ============================================================================
# RELATIONSHIPS (edges in the graph)
# ============================================================================

@dataclass(kw_only=True)
class Relationship(Tagged):
    """
    Edge between two entities.

    BeneficialOwner is a relationship, not a separate entity type.
    This keeps entities as clean nodes and relationships as edges.

    Examples:
    - Individual --[UBO 25%]--> Organization
    - Individual --[ACCOUNT_HOLDER]--> Account
    - Organization --[SUBSIDIARY]--> Organization
    """
    id: str
    relationship_type: RelationshipType
    from_entity_type: EntityType
    from_entity_id: str
    to_entity_type: EntityType  # Can also be "account"
    to_entity_id: str

    # Ownership details (for UBO/SHAREHOLDER)
    ownership_percentage: Optional[Decimal] = None
    voting_percentage: Optional[Decimal] = None
    is_direct: bool = True  # Direct vs indirect ownership

    # Verification
    verified: bool = False
    verified_date: Optional[date] = None
    verified_by: Optional[str] = None

    # Temporal
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None

    # Evidence supporting this relationship
    evidence_ids: list[str] = field(default_factory=list)


# ============================================================================
# EVIDENCE
# ============================================================================

@dataclass(kw_only=True)
class EvidenceItem(Tagged):
    """
    A piece of evidence supporting a case.
    Same model for ID docs, transaction logs, analyst notes, etc.

    This becomes an EVIDENCE cell in DecisionGraph.
    """
    id: str
    evidence_type: EvidenceType
    description: str
    collected_date: date
    source: str  # e.g., "customer_upload", "screening_vendor", "analyst"

    # Document metadata
    document_date: Optional[date] = None
    expiry_date: Optional[date] = None
    issuing_authority: Optional[str] = None
    document_number: Optional[str] = None

    # Verification
    verified: bool = False
    verified_by: Optional[str] = None
    verified_date: Optional[date] = None

    # Storage reference (not the content itself)
    storage_ref: Optional[str] = None

    # Link to entity this evidence is about
    subject_entity_type: Optional[EntityType] = None
    subject_entity_id: Optional[str] = None


# ============================================================================
# EVENTS
# ============================================================================

@dataclass(kw_only=True)
class Event(Tagged):
    """
    Base event - something that happened.
    KYC events and AML events share this structure.
    """
    id: str
    event_type: str
    timestamp: datetime
    description: Optional[str] = None
    evidence_ids: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class TransactionEvent(Event):
    """Financial transaction - core of AML monitoring."""
    amount: Decimal
    currency: str
    direction: str  # inbound, outbound, internal

    # Counterparty
    counterparty_name: Optional[str] = None
    counterparty_country: Optional[str] = None
    counterparty_account: Optional[str] = None
    counterparty_bank: Optional[str] = None

    # Transaction details
    payment_method: Optional[str] = None  # wire, ach, cash, check, crypto
    purpose: Optional[str] = None
    reference: Optional[str] = None

    # Account reference
    account_id: Optional[str] = None

    def __post_init__(self):
        self.event_type = "transaction"


@dataclass(kw_only=True)
class AlertEvent(Event):
    """Alert generated by monitoring system."""
    alert_type: str  # e.g., "structuring", "high_risk_jurisdiction", "velocity"
    rule_id: Optional[str] = None
    rule_name: Optional[str] = None
    score: Optional[Decimal] = None
    threshold: Optional[Decimal] = None
    triggering_transactions: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.event_type = "alert"


@dataclass(kw_only=True)
class ScreeningEvent(Event):
    """Sanctions/PEP/Adverse Media screening result."""
    screening_type: str  # sanctions, pep, adverse_media
    vendor: str
    match_score: Optional[Decimal] = None
    matched_list: Optional[str] = None
    matched_name: Optional[str] = None
    match_details: Optional[str] = None
    disposition: Optional[str] = None  # confirmed, false_positive, pending

    # Entity being screened
    screened_entity_type: Optional[EntityType] = None
    screened_entity_id: Optional[str] = None

    def __post_init__(self):
        self.event_type = "screening"


@dataclass(kw_only=True)
class VerificationEvent(Event):
    """Identity or document verification result."""
    verification_type: str  # identity, document, address, employment
    vendor: Optional[str] = None
    result: str  # pass, fail, refer, inconclusive
    confidence_score: Optional[Decimal] = None
    failure_reasons: list[str] = field(default_factory=list)

    # What was verified
    verified_entity_type: Optional[EntityType] = None
    verified_entity_id: Optional[str] = None
    evidence_id: Optional[str] = None

    def __post_init__(self):
        self.event_type = "verification"


# ============================================================================
# ASSERTIONS (bridge KYC → AML → EDD)
# ============================================================================

@dataclass(kw_only=True)
class Assertion(Tagged):
    """
    A fact asserted about an entity or case.
    This is how KYC feeds into AML rules.

    Example: KYC asserts customer.risk_rating = HIGH
             AML rules consume that assertion

    Assertions become FACT cells in DecisionGraph.
    """
    id: str
    subject_type: str  # "individual", "organization", "account", "case"
    subject_id: str
    predicate: str     # e.g., "risk_rating", "pep_status", "identity_verified"
    value: str         # e.g., "HIGH", "FPEP", "true"

    # Provenance
    asserted_at: datetime
    asserted_by: str   # system or user ID
    assertion_source: str = "system"  # system, analyst, external

    # Confidence and evidence
    confidence: Optional[Decimal] = None
    evidence_ids: list[str] = field(default_factory=list)

    # Version control
    supersedes: Optional[str] = None  # ID of assertion this replaces
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None


# ============================================================================
# CASE META
# ============================================================================

@dataclass(kw_only=True)
class CaseMeta(Tagged):
    """
    Case metadata - the wrapper for a Financial Crime case.
    CaseType = what kind, CasePhase = where in lifecycle.
    """
    id: str
    case_type: CaseType
    case_phase: CasePhase
    created_at: datetime
    jurisdiction: str  # Regulatory jurisdiction (CA, US, UK, etc.)

    # Customer reference
    primary_entity_type: EntityType
    primary_entity_id: str

    # Status tracking
    status: str = "open"  # open, pending_review, escalated, closed
    assigned_to: Optional[str] = None
    assigned_team: Optional[str] = None
    priority: str = "normal"  # low, normal, high, critical
    due_date: Optional[date] = None

    # SLA tracking
    sla_deadline: Optional[datetime] = None
    sla_breached: bool = False

    # Regulatory
    regulatory_deadline: Optional[date] = None
    filing_required: bool = False
    filing_type: Optional[str] = None  # STR, SAR, LCTR, etc.
    filing_date: Optional[date] = None
    filing_reference: Optional[str] = None

    # Audit trail
    opened_by: Optional[str] = None
    closed_at: Optional[datetime] = None
    closed_by: Optional[str] = None
    closure_reason: Optional[str] = None
    closure_code: Optional[str] = None  # e.g., "no_suspicious_activity"

    # Linking
    parent_case_id: Optional[str] = None  # For escalations/referrals
    related_case_ids: list[str] = field(default_factory=list)


# ============================================================================
# CASE BUNDLE (the main container)
# ============================================================================

@dataclass
class CaseBundle:
    """
    Complete Financial Crime case - ready for DecisionGraph processing.

    This is the universal input format. The case_loader converts this
    to DecisionGraph cells (EVIDENCE cells, FACT cells, etc.)

    Covers: KYC, AML, EDD, Sanctions - one Financial Crime department.

    Structure:
    - meta: case header (type + phase + sensitivity)
    - entities: nodes (Individual, Organization, Account)
    - relationships: edges (UBO, control, account holder)
    - evidence: supporting documents and data
    - events: things that happened (transactions, alerts, screenings)
    - assertions: facts derived from evidence
    """
    # Case identification
    meta: CaseMeta

    # Entities (nodes)
    individuals: list[Individual] = field(default_factory=list)
    organizations: list[Organization] = field(default_factory=list)
    accounts: list[Account] = field(default_factory=list)

    # Relationships (edges)
    relationships: list[Relationship] = field(default_factory=list)

    # Evidence collected
    evidence: list[EvidenceItem] = field(default_factory=list)

    # Events (transactions, alerts, screenings, verifications)
    events: list[Event] = field(default_factory=list)

    # Assertions (facts derived from KYC, consumed by AML)
    assertions: list[Assertion] = field(default_factory=list)

    # Schema version for forward compatibility
    schema_version: str = "1.0"

    # -------------------------------------------------------------------------
    # Convenience methods
    # -------------------------------------------------------------------------

    def get_primary_entity(self) -> Union[Individual, Organization, None]:
        """Get the primary customer entity."""
        if self.meta.primary_entity_type == EntityType.INDIVIDUAL:
            return next(
                (i for i in self.individuals if i.id == self.meta.primary_entity_id),
                None
            )
        else:
            return next(
                (o for o in self.organizations if o.id == self.meta.primary_entity_id),
                None
            )

    def get_entity(self, entity_type: EntityType, entity_id: str) -> Union[Individual, Organization, Account, None]:
        """Get any entity by type and ID."""
        if entity_type == EntityType.INDIVIDUAL:
            return next((i for i in self.individuals if i.id == entity_id), None)
        else:
            return next((o for o in self.organizations if o.id == entity_id), None)

    def get_account(self, account_id: str) -> Optional[Account]:
        """Get account by ID."""
        return next((a for a in self.accounts if a.id == account_id), None)

    def get_evidence_by_type(self, etype: EvidenceType) -> list[EvidenceItem]:
        """Filter evidence by type."""
        return [e for e in self.evidence if e.evidence_type == etype]

    def get_evidence_for_entity(self, entity_id: str) -> list[EvidenceItem]:
        """Get all evidence about a specific entity."""
        return [e for e in self.evidence if e.subject_entity_id == entity_id]

    def get_assertions_for(self, subject_id: str) -> list[Assertion]:
        """Get all assertions about a subject."""
        return [a for a in self.assertions if a.subject_id == subject_id]

    def get_relationships_for(self, entity_id: str) -> list[Relationship]:
        """Get all relationships involving an entity."""
        return [
            r for r in self.relationships
            if r.from_entity_id == entity_id or r.to_entity_id == entity_id
        ]

    def get_ubos(self, org_id: str) -> list[tuple[Individual, Relationship]]:
        """Get beneficial owners of an organization with ownership details."""
        result = []
        for rel in self.relationships:
            if (rel.to_entity_id == org_id and
                rel.relationship_type == RelationshipType.UBO and
                rel.from_entity_type == EntityType.INDIVIDUAL):
                individual = next(
                    (i for i in self.individuals if i.id == rel.from_entity_id),
                    None
                )
                if individual:
                    result.append((individual, rel))
        return result

    def get_transactions(self) -> list[TransactionEvent]:
        """Get all transaction events."""
        return [e for e in self.events if isinstance(e, TransactionEvent)]

    def get_alerts(self) -> list[AlertEvent]:
        """Get all alert events."""
        return [e for e in self.events if isinstance(e, AlertEvent)]

    def get_screenings(self) -> list[ScreeningEvent]:
        """Get all screening events."""
        return [e for e in self.events if isinstance(e, ScreeningEvent)]


# ============================================================================
# VALIDATION HELPERS
# ============================================================================

def validate_case_bundle(bundle: CaseBundle) -> list[str]:
    """
    Validate a CaseBundle for consistency.
    Returns list of error messages (empty if valid).
    """
    errors = []

    # Check primary entity exists
    if bundle.get_primary_entity() is None:
        errors.append(
            f"Primary entity not found: {bundle.meta.primary_entity_type.value} "
            f"with id {bundle.meta.primary_entity_id}"
        )

    # Check relationship references
    all_entity_ids = (
        {i.id for i in bundle.individuals} |
        {o.id for o in bundle.organizations} |
        {a.id for a in bundle.accounts}
    )

    for rel in bundle.relationships:
        if rel.from_entity_id not in all_entity_ids:
            errors.append(
                f"Relationship {rel.id} references unknown from_entity: {rel.from_entity_id}"
            )
        if rel.to_entity_id not in all_entity_ids:
            errors.append(
                f"Relationship {rel.id} references unknown to_entity: {rel.to_entity_id}"
            )

    # Check evidence references
    all_evidence_ids = {e.id for e in bundle.evidence}

    for rel in bundle.relationships:
        for eid in rel.evidence_ids:
            if eid not in all_evidence_ids:
                errors.append(
                    f"Relationship {rel.id} references unknown evidence: {eid}"
                )

    for assertion in bundle.assertions:
        for eid in assertion.evidence_ids:
            if eid not in all_evidence_ids:
                errors.append(
                    f"Assertion {assertion.id} references unknown evidence: {eid}"
                )

    # Check assertion subjects exist
    for assertion in bundle.assertions:
        if assertion.subject_type in ("individual", "organization"):
            if assertion.subject_id not in all_entity_ids:
                errors.append(
                    f"Assertion {assertion.id} references unknown subject: {assertion.subject_id}"
                )

    return errors
