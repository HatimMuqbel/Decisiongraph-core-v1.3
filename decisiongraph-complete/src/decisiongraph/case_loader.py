"""
case_loader.py - CaseBundle → DecisionGraph Cells

This module transforms a Financial Crime CaseBundle into DecisionGraph cells.
It's a pure transformation layer - no side effects, no chain mutations.

Mapping:
    CaseBundle Component    →  Cell Type      →  Namespace
    ─────────────────────────────────────────────────────────
    CaseMeta                →  FACT           →  fincrime.case
    Individual              →  FACT           →  fincrime.entity
    Organization            →  FACT           →  fincrime.entity
    Account                 →  FACT           →  fincrime.account
    Relationship            →  FACT           →  fincrime.relationship
    EvidenceItem            →  EVIDENCE       →  fincrime.evidence
    TransactionEvent        →  FACT           →  fincrime.transaction
    AlertEvent              →  FACT           →  fincrime.alert
    ScreeningEvent          →  FACT           →  fincrime.screening
    VerificationEvent       →  FACT           →  fincrime.verification
    Assertion               →  FACT           →  fincrime.assertion

Usage:
    from case_schema import CaseBundle
    from case_loader import load_case_bundle

    bundle = CaseBundle(...)
    cells = load_case_bundle(bundle, graph_id, prev_hash)

    for cell in cells:
        chain.append(cell)
"""

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

# Import from the complete package (adjust path as needed)
import sys
from pathlib import Path

# Add the complete package to path for imports
_complete_path = Path(__file__).parent.parent.parent / "decisiongraph-complete" / "src"
if _complete_path.exists():
    sys.path.insert(0, str(_complete_path))

from decisiongraph.cell import (
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Evidence as CellEvidence,
    Proof,
    CellType,
    SourceQuality,
    HASH_SCHEME_CANONICAL,
    get_current_timestamp,
    compute_rule_logic_hash,
    compute_content_id,
)

from .case_schema import (
    CaseBundle,
    CaseMeta,
    CaseType,
    CasePhase,
    EntityType,
    Individual,
    Organization,
    Account,
    Relationship,
    RelationshipType,
    EvidenceItem,
    EvidenceType,
    Event,
    TransactionEvent,
    AlertEvent,
    ScreeningEvent,
    VerificationEvent,
    Assertion,
    Sensitivity,
    RiskRating,
    PEPCategory,
)


# ============================================================================
# CONSTANTS
# ============================================================================

# Schema version for case loading
CASE_LOADER_VERSION = "1.0"

# Namespace hierarchy for Financial Crime
NS_FINCRIME = "fincrime"
NS_CASE = f"{NS_FINCRIME}.case"
NS_PHASE = f"{NS_FINCRIME}.phase"  # Explicit phase transitions for audit trail
NS_ENTITY = f"{NS_FINCRIME}.entity"
NS_ACCOUNT = f"{NS_FINCRIME}.account"
NS_RELATIONSHIP = f"{NS_FINCRIME}.relationship"
NS_EVIDENCE = f"{NS_FINCRIME}.evidence"
NS_TRANSACTION = f"{NS_FINCRIME}.transaction"
NS_ALERT = f"{NS_FINCRIME}.alert"
NS_SCREENING = f"{NS_FINCRIME}.screening"
NS_VERIFICATION = f"{NS_FINCRIME}.verification"
NS_ASSERTION = f"{NS_FINCRIME}.assertion"

# Rule definitions for case loading
CASE_LOAD_RULE = """
-- CaseLoader Rule v1.0
-- Transforms CaseBundle components into DecisionGraph cells

LOAD CASE:
  INPUT: CaseBundle (Financial Crime schema v1.0)
  OUTPUT: List[DecisionCell]

  TRANSFORM:
    - CaseMeta → FACT cell (case header)
    - Entities → FACT cells (identity facts)
    - Relationships → FACT cells (edge facts)
    - Evidence → EVIDENCE cells (supporting docs)
    - Events → FACT cells (things that happened)
    - Assertions → FACT cells (derived facts)

  CONSTRAINTS:
    - All cells share same graph_id
    - All cells use canonical hash scheme
    - Evidence CIDs are content-addressable
    - Timestamps are ISO 8601 UTC
"""

CASE_LOAD_RULE_HASH = compute_rule_logic_hash(CASE_LOAD_RULE)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _decimal_to_str(value: Optional[Decimal]) -> Optional[str]:
    """Convert Decimal to string for canonical JSON."""
    if value is None:
        return None
    return str(value)


def _enum_to_str(value) -> Optional[str]:
    """Convert enum to string value."""
    if value is None:
        return None
    if hasattr(value, 'value'):
        return value.value
    return str(value)


def _date_to_str(value) -> Optional[str]:
    """Convert date to ISO string."""
    if value is None:
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


def _datetime_to_iso(value) -> Optional[str]:
    """Convert datetime to ISO 8601 UTC string."""
    if value is None:
        return None
    if hasattr(value, 'isoformat'):
        # Ensure UTC timezone
        if hasattr(value, 'tzinfo') and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        iso = value.isoformat()
        # Ensure Z suffix for UTC
        if iso.endswith('+00:00'):
            iso = iso[:-6] + 'Z'
        return iso
    return str(value)


def _compute_object_hash(obj: dict) -> str:
    """Compute deterministic hash of a dict object."""
    canonical = json.dumps(obj, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _source_to_quality(source: str) -> SourceQuality:
    """
    Map evidence/data source to SourceQuality.

    Sensitivity and SourceQuality are DIFFERENT concepts:
    - Sensitivity = privacy classification (who can see it)
    - SourceQuality = trustworthiness of the source

    A restricted document can be low quality, and a public document can be verified.
    """
    # Bank system feeds are verified
    if source in ("bank_system", "core_banking", "screening_vendor", "kyc_vendor"):
        return SourceQuality.VERIFIED
    # Customer declarations are self-reported
    elif source in ("customer", "customer_upload", "self_declaration", "application"):
        return SourceQuality.SELF_REPORTED
    # Third-party vendors are generally verified
    elif source in ("vendor", "bureau", "registry", "government"):
        return SourceQuality.VERIFIED
    # Analyst assessments are verified
    elif source in ("analyst", "compliance", "reviewer"):
        return SourceQuality.VERIFIED
    # Default to self-reported for unknown sources
    else:
        return SourceQuality.SELF_REPORTED


def _create_cell(
    graph_id: str,
    prev_cell_hash: str,
    cell_type: CellType,
    namespace: str,
    subject: str,
    predicate: str,
    obj: dict,
    system_time: str,
    source_quality: SourceQuality = SourceQuality.SELF_REPORTED,
    confidence: float = 0.9,
    valid_from: Optional[str] = None,
    evidence_list: list = None,
) -> DecisionCell:
    """
    Create a DecisionCell with canonical hash scheme.

    All structured objects use canonical JSON hashing for deterministic cell IDs.
    """
    header = Header(
        version="1.3",
        graph_id=graph_id,
        cell_type=cell_type,
        system_time=system_time,
        prev_cell_hash=prev_cell_hash,
        hash_scheme=HASH_SCHEME_CANONICAL,
    )

    fact = Fact(
        namespace=namespace,
        subject=subject,
        predicate=predicate,
        object=obj,
        confidence=confidence,
        source_quality=source_quality,
        valid_from=valid_from or system_time,
        valid_to=None,
    )

    logic_anchor = LogicAnchor(
        rule_id="fincrime:case_loader_v1.0",
        rule_logic_hash=CASE_LOAD_RULE_HASH,
        interpreter="case_loader:v1.0",
    )

    evidence = evidence_list or []

    return DecisionCell(
        header=header,
        fact=fact,
        logic_anchor=logic_anchor,
        evidence=evidence,
        proof=Proof(),
    )


# ============================================================================
# COMPONENT LOADERS
# ============================================================================

def _load_case_meta(
    meta: CaseMeta,
    graph_id: str,
    prev_hash: str,
    system_time: str,
) -> DecisionCell:
    """Convert CaseMeta to a FACT cell."""
    obj = {
        "case_id": meta.id,
        "case_type": _enum_to_str(meta.case_type),
        "case_phase": _enum_to_str(meta.case_phase),
        "jurisdiction": meta.jurisdiction,
        "primary_entity_type": _enum_to_str(meta.primary_entity_type),
        "primary_entity_id": meta.primary_entity_id,
        "status": meta.status,
        "priority": meta.priority,
        "assigned_to": meta.assigned_to,
        "assigned_team": meta.assigned_team,
        "due_date": _date_to_str(meta.due_date),
        "sla_deadline": _datetime_to_iso(meta.sla_deadline),
        "sla_breached": meta.sla_breached,
        "regulatory_deadline": _date_to_str(meta.regulatory_deadline),
        "filing_required": meta.filing_required,
        "filing_type": meta.filing_type,
        "opened_by": meta.opened_by,
        "created_at": _datetime_to_iso(meta.created_at),
        "sensitivity": _enum_to_str(meta.sensitivity),
        "access_tags": meta.access_tags,
    }

    return _create_cell(
        graph_id=graph_id,
        prev_cell_hash=prev_hash,
        cell_type=CellType.FACT,
        namespace=NS_CASE,
        subject=f"case:{meta.id}",
        predicate="case_opened",
        obj=obj,
        system_time=system_time,
        source_quality=SourceQuality.VERIFIED,
        confidence=1.0,
    )


def _load_case_phase(
    case_id: str,
    phase: CasePhase,
    previous_phase: Optional[CasePhase],
    graph_id: str,
    prev_hash: str,
    system_time: str,
    reason: Optional[str] = None,
) -> DecisionCell:
    """
    Create explicit case phase transition cell.

    Phase transitions are explicit events for audit trail clarity.
    Even if CaseMeta includes phase, this makes phase changes visible
    in reports and audit sections.
    """
    obj = {
        "case_id": case_id,
        "phase": _enum_to_str(phase),
        "previous_phase": _enum_to_str(previous_phase) if previous_phase else None,
        "transition_reason": reason or "initial_load",
    }

    return _create_cell(
        graph_id=graph_id,
        prev_cell_hash=prev_hash,
        cell_type=CellType.FACT,
        namespace=NS_PHASE,
        subject=f"case:{case_id}",
        predicate="phase_transition",
        obj=obj,
        system_time=system_time,
        source_quality=SourceQuality.VERIFIED,
        confidence=1.0,
    )


def _load_individual(
    individual: Individual,
    graph_id: str,
    prev_hash: str,
    system_time: str,
) -> DecisionCell:
    """Convert Individual entity to a FACT cell."""
    addresses = [
        {
            "line1": a.line1,
            "line2": a.line2,
            "city": a.city,
            "state_province": a.state_province,
            "postal_code": a.postal_code,
            "country": a.country,
            "address_type": a.address_type,
            "verified": a.verified,
        }
        for a in individual.addresses
    ]

    obj = {
        "entity_id": individual.id,
        "entity_type": "individual",
        "given_name": individual.given_name,
        "family_name": individual.family_name,
        "full_name": individual.full_name,
        "date_of_birth": _date_to_str(individual.date_of_birth),
        "nationality": individual.nationality,
        "country_of_residence": individual.country_of_residence,
        "tax_id": individual.tax_id,
        "occupation": individual.occupation,
        "employer": individual.employer,
        "pep_status": _enum_to_str(individual.pep_status),
        "risk_rating": _enum_to_str(individual.risk_rating),
        "customer_status": _enum_to_str(individual.customer_status),
        "addresses": addresses,
        "sensitivity": _enum_to_str(individual.sensitivity),
        "access_tags": individual.access_tags,
    }

    return _create_cell(
        graph_id=graph_id,
        prev_cell_hash=prev_hash,
        cell_type=CellType.FACT,
        namespace=NS_ENTITY,
        subject=f"individual:{individual.id}",
        predicate="entity_profile",
        obj=obj,
        system_time=system_time,
        source_quality=_source_to_quality("core_banking"),  # Entity profiles from bank systems
    )


def _load_organization(
    org: Organization,
    graph_id: str,
    prev_hash: str,
    system_time: str,
) -> DecisionCell:
    """Convert Organization entity to a FACT cell."""
    addresses = [
        {
            "line1": a.line1,
            "line2": a.line2,
            "city": a.city,
            "state_province": a.state_province,
            "postal_code": a.postal_code,
            "country": a.country,
            "address_type": a.address_type,
            "verified": a.verified,
        }
        for a in org.addresses
    ]

    obj = {
        "entity_id": org.id,
        "entity_type": "organization",
        "legal_name": org.legal_name,
        "entity_subtype": org.entity_type,
        "jurisdiction": org.jurisdiction,
        "registration_number": org.registration_number,
        "date_of_incorporation": _date_to_str(org.date_of_incorporation),
        "industry_code": org.industry_code,
        "industry_description": org.industry_description,
        "website": org.website,
        "risk_rating": _enum_to_str(org.risk_rating),
        "customer_status": _enum_to_str(org.customer_status),
        "addresses": addresses,
        "sensitivity": _enum_to_str(org.sensitivity),
        "access_tags": org.access_tags,
    }

    return _create_cell(
        graph_id=graph_id,
        prev_cell_hash=prev_hash,
        cell_type=CellType.FACT,
        namespace=NS_ENTITY,
        subject=f"organization:{org.id}",
        predicate="entity_profile",
        obj=obj,
        system_time=system_time,
        source_quality=_source_to_quality("core_banking"),  # Entity profiles from bank systems
    )


def _load_account(
    account: Account,
    graph_id: str,
    prev_hash: str,
    system_time: str,
) -> DecisionCell:
    """Convert Account to a FACT cell."""
    obj = {
        "account_id": account.id,
        "account_number": account.account_number,
        "account_type": account.account_type,
        "currency": account.currency,
        "opened_date": _date_to_str(account.opened_date),
        "closed_date": _date_to_str(account.closed_date),
        "status": account.status,
        "branch_code": account.branch_code,
        "product_code": account.product_code,
        "sensitivity": _enum_to_str(account.sensitivity),
        "access_tags": account.access_tags,
    }

    return _create_cell(
        graph_id=graph_id,
        prev_cell_hash=prev_hash,
        cell_type=CellType.FACT,
        namespace=NS_ACCOUNT,
        subject=f"account:{account.id}",
        predicate="account_profile",
        obj=obj,
        system_time=system_time,
        source_quality=_source_to_quality("core_banking"),  # Account data from bank systems
    )


def _load_relationship(
    rel: Relationship,
    graph_id: str,
    prev_hash: str,
    system_time: str,
) -> DecisionCell:
    """Convert Relationship to a FACT cell."""
    obj = {
        "relationship_id": rel.id,
        "relationship_type": _enum_to_str(rel.relationship_type),
        "from_entity_type": _enum_to_str(rel.from_entity_type),
        "from_entity_id": rel.from_entity_id,
        "to_entity_type": _enum_to_str(rel.to_entity_type),
        "to_entity_id": rel.to_entity_id,
        "ownership_percentage": _decimal_to_str(rel.ownership_percentage),
        "voting_percentage": _decimal_to_str(rel.voting_percentage),
        "is_direct": rel.is_direct,
        "verified": rel.verified,
        "verified_date": _date_to_str(rel.verified_date),
        "verified_by": rel.verified_by,
        "effective_from": _date_to_str(rel.effective_from),
        "effective_to": _date_to_str(rel.effective_to),
        "evidence_ids": rel.evidence_ids,
        "sensitivity": _enum_to_str(rel.sensitivity),
        "access_tags": rel.access_tags,
    }

    # Subject captures the edge with type: type:from:to
    # This prevents collisions when same entities have multiple relationships
    # e.g., rel:ubo:org:123:individual:456 vs rel:director:org:123:individual:456
    rel_type = _enum_to_str(rel.relationship_type)
    from_type = _enum_to_str(rel.from_entity_type)
    to_type = _enum_to_str(rel.to_entity_type)
    subject = f"rel:{rel_type}:{from_type}:{rel.from_entity_id}:{to_type}:{rel.to_entity_id}"

    return _create_cell(
        graph_id=graph_id,
        prev_cell_hash=prev_hash,
        cell_type=CellType.FACT,
        namespace=NS_RELATIONSHIP,
        subject=subject,
        predicate=rel_type,
        obj=obj,
        system_time=system_time,
        source_quality=_source_to_quality("bank_system"),  # Relationships from bank systems
    )


def _load_evidence_item(
    evidence: EvidenceItem,
    graph_id: str,
    prev_hash: str,
    system_time: str,
) -> DecisionCell:
    """Convert EvidenceItem to an EVIDENCE cell."""
    obj = {
        "evidence_id": evidence.id,
        "evidence_type": _enum_to_str(evidence.evidence_type),
        "description": evidence.description,
        "source": evidence.source,
        "collected_date": _date_to_str(evidence.collected_date),
        "document_date": _date_to_str(evidence.document_date),
        "expiry_date": _date_to_str(evidence.expiry_date),
        "issuing_authority": evidence.issuing_authority,
        "document_number": evidence.document_number,
        "verified": evidence.verified,
        "verified_by": evidence.verified_by,
        "verified_date": _date_to_str(evidence.verified_date),
        "storage_ref": evidence.storage_ref,
        "subject_entity_type": _enum_to_str(evidence.subject_entity_type),
        "subject_entity_id": evidence.subject_entity_id,
        "sensitivity": _enum_to_str(evidence.sensitivity),
        "access_tags": evidence.access_tags,
    }

    # Compute content hash for subject anchoring
    # This enables cross-system reconciliation and prevents duplicate evidence
    content_hash = _compute_object_hash(obj)[:16]  # First 16 chars of SHA256

    # Create cell evidence reference
    cell_evidence = []
    if evidence.storage_ref:
        cell_evidence.append(CellEvidence(
            type="document_reference",
            cid=evidence.storage_ref,
            source=evidence.source,
            description=evidence.description,
        ))

    # Subject includes both id and content hash for stability
    # evidence:{id}:{content_hash_prefix}
    subject = f"evidence:{evidence.id}:{content_hash}"

    return _create_cell(
        graph_id=graph_id,
        prev_cell_hash=prev_hash,
        cell_type=CellType.EVIDENCE,
        namespace=NS_EVIDENCE,
        subject=subject,
        predicate="evidence_collected",
        obj=obj,
        system_time=system_time,
        source_quality=_source_to_quality(evidence.source),
        confidence=1.0 if evidence.verified else 0.8,
        evidence_list=cell_evidence,
    )


def _load_transaction_event(
    txn: TransactionEvent,
    graph_id: str,
    prev_hash: str,
    system_time: str,
) -> DecisionCell:
    """Convert TransactionEvent to a FACT cell."""
    obj = {
        "event_id": txn.id,
        "event_type": txn.event_type,
        "timestamp": _datetime_to_iso(txn.timestamp),
        "description": txn.description,
        "amount": _decimal_to_str(txn.amount),
        "currency": txn.currency,
        "direction": txn.direction,
        "counterparty_name": txn.counterparty_name,
        "counterparty_country": txn.counterparty_country,
        "counterparty_account": txn.counterparty_account,
        "counterparty_bank": txn.counterparty_bank,
        "payment_method": txn.payment_method,
        "purpose": txn.purpose,
        "reference": txn.reference,
        "account_id": txn.account_id,
        "evidence_ids": txn.evidence_ids,
        "sensitivity": _enum_to_str(txn.sensitivity),
        "access_tags": txn.access_tags,
    }

    return _create_cell(
        graph_id=graph_id,
        prev_cell_hash=prev_hash,
        cell_type=CellType.FACT,
        namespace=NS_TRANSACTION,
        subject=f"txn:{txn.id}",
        predicate="transaction_occurred",
        obj=obj,
        system_time=system_time,
        valid_from=_datetime_to_iso(txn.timestamp),
        source_quality=SourceQuality.VERIFIED,
        confidence=1.0,
    )


def _load_alert_event(
    alert: AlertEvent,
    graph_id: str,
    prev_hash: str,
    system_time: str,
) -> DecisionCell:
    """Convert AlertEvent to a FACT cell."""
    obj = {
        "event_id": alert.id,
        "event_type": alert.event_type,
        "timestamp": _datetime_to_iso(alert.timestamp),
        "description": alert.description,
        "alert_type": alert.alert_type,
        "rule_id": alert.rule_id,
        "rule_name": alert.rule_name,
        "score": _decimal_to_str(alert.score),
        "threshold": _decimal_to_str(alert.threshold),
        "triggering_transactions": alert.triggering_transactions,
        "evidence_ids": alert.evidence_ids,
        "sensitivity": _enum_to_str(alert.sensitivity),
        "access_tags": alert.access_tags,
    }

    return _create_cell(
        graph_id=graph_id,
        prev_cell_hash=prev_hash,
        cell_type=CellType.FACT,
        namespace=NS_ALERT,
        subject=f"alert:{alert.id}",
        predicate="alert_triggered",
        obj=obj,
        system_time=system_time,
        valid_from=_datetime_to_iso(alert.timestamp),
        source_quality=SourceQuality.VERIFIED,
        confidence=1.0,
    )


def _load_screening_event(
    screening: ScreeningEvent,
    graph_id: str,
    prev_hash: str,
    system_time: str,
) -> DecisionCell:
    """Convert ScreeningEvent to a FACT cell."""
    obj = {
        "event_id": screening.id,
        "event_type": screening.event_type,
        "timestamp": _datetime_to_iso(screening.timestamp),
        "description": screening.description,
        "screening_type": screening.screening_type,
        "vendor": screening.vendor,
        "match_score": _decimal_to_str(screening.match_score),
        "matched_list": screening.matched_list,
        "matched_name": screening.matched_name,
        "match_details": screening.match_details,
        "disposition": screening.disposition,
        "screened_entity_type": _enum_to_str(screening.screened_entity_type),
        "screened_entity_id": screening.screened_entity_id,
        "evidence_ids": screening.evidence_ids,
        "sensitivity": _enum_to_str(screening.sensitivity),
        "access_tags": screening.access_tags,
    }

    return _create_cell(
        graph_id=graph_id,
        prev_cell_hash=prev_hash,
        cell_type=CellType.FACT,
        namespace=NS_SCREENING,
        subject=f"screening:{screening.id}",
        predicate="screening_completed",
        obj=obj,
        system_time=system_time,
        valid_from=_datetime_to_iso(screening.timestamp),
        source_quality=SourceQuality.VERIFIED,
        confidence=1.0,
    )


def _load_verification_event(
    verification: VerificationEvent,
    graph_id: str,
    prev_hash: str,
    system_time: str,
) -> DecisionCell:
    """Convert VerificationEvent to a FACT cell."""
    obj = {
        "event_id": verification.id,
        "event_type": verification.event_type,
        "timestamp": _datetime_to_iso(verification.timestamp),
        "description": verification.description,
        "verification_type": verification.verification_type,
        "vendor": verification.vendor,
        "result": verification.result,
        "confidence_score": _decimal_to_str(verification.confidence_score),
        "failure_reasons": verification.failure_reasons,
        "verified_entity_type": _enum_to_str(verification.verified_entity_type),
        "verified_entity_id": verification.verified_entity_id,
        "evidence_id": verification.evidence_id,
        "evidence_ids": verification.evidence_ids,
        "sensitivity": _enum_to_str(verification.sensitivity),
        "access_tags": verification.access_tags,
    }

    return _create_cell(
        graph_id=graph_id,
        prev_cell_hash=prev_hash,
        cell_type=CellType.FACT,
        namespace=NS_VERIFICATION,
        subject=f"verification:{verification.id}",
        predicate="verification_completed",
        obj=obj,
        system_time=system_time,
        valid_from=_datetime_to_iso(verification.timestamp),
        source_quality=SourceQuality.VERIFIED,
        confidence=1.0,
    )


def _load_assertion(
    assertion: Assertion,
    graph_id: str,
    prev_hash: str,
    system_time: str,
) -> DecisionCell:
    """Convert Assertion to a FACT cell."""
    obj = {
        "assertion_id": assertion.id,
        "subject_type": assertion.subject_type,
        "subject_id": assertion.subject_id,
        "predicate": assertion.predicate,
        "value": assertion.value,
        "asserted_at": _datetime_to_iso(assertion.asserted_at),
        "asserted_by": assertion.asserted_by,
        "assertion_source": assertion.assertion_source,
        "confidence": _decimal_to_str(assertion.confidence),
        "evidence_ids": assertion.evidence_ids,
        "supersedes": assertion.supersedes,
        "valid_from": _datetime_to_iso(assertion.valid_from),
        "valid_to": _datetime_to_iso(assertion.valid_to),
        "sensitivity": _enum_to_str(assertion.sensitivity),
        "access_tags": assertion.access_tags,
    }

    # Subject is what the assertion is about
    subject = f"{assertion.subject_type}:{assertion.subject_id}"

    return _create_cell(
        graph_id=graph_id,
        prev_cell_hash=prev_hash,
        cell_type=CellType.FACT,
        namespace=NS_ASSERTION,
        subject=subject,
        predicate=assertion.predicate,
        obj=obj,
        system_time=system_time,
        valid_from=_datetime_to_iso(assertion.asserted_at),
        source_quality=SourceQuality.VERIFIED if assertion.assertion_source == "system" else SourceQuality.SELF_REPORTED,
        confidence=float(assertion.confidence) if assertion.confidence else 0.9,
    )


# ============================================================================
# MAIN LOADER
# ============================================================================

def load_case_bundle(
    bundle: CaseBundle,
    graph_id: str,
    prev_cell_hash: str,
    system_time: Optional[str] = None,
) -> list[DecisionCell]:
    """
    Transform a CaseBundle into a list of DecisionGraph cells.

    This is a pure transformation - it does not mutate the chain.
    The caller is responsible for appending cells to the chain.

    Cell ordering:
    1. CaseMeta (case header)
    2. CasePhase (explicit phase transition for audit trail)
    3. Individuals (entity profiles)
    4. Organizations (entity profiles)
    5. Accounts (account profiles)
    6. Relationships (edges between entities)
    7. Evidence (supporting documents)
    8. Events (transactions, alerts, screenings, verifications)
    9. Assertions (derived facts)

    Args:
        bundle: The CaseBundle to transform
        graph_id: The graph_id for all cells (must match chain's graph_id)
        prev_cell_hash: Hash of the cell to link to (chain head)
        system_time: Optional timestamp (defaults to now)

    Returns:
        List of DecisionCells ready to be appended to a chain

    Example:
        >>> bundle = CaseBundle(meta=..., individuals=[...], ...)
        >>> cells = load_case_bundle(bundle, chain.graph_id, chain.head.cell_id)
        >>> for cell in cells:
        ...     chain.append(cell)
    """
    cells = []
    ts = system_time or get_current_timestamp()
    current_prev = prev_cell_hash

    # 1. Load CaseMeta
    cell = _load_case_meta(bundle.meta, graph_id, current_prev, ts)
    cells.append(cell)
    current_prev = cell.cell_id

    # 2. Load explicit CasePhase transition (for audit trail clarity)
    cell = _load_case_phase(
        case_id=bundle.meta.id,
        phase=bundle.meta.case_phase,
        previous_phase=None,  # Initial load has no previous phase
        graph_id=graph_id,
        prev_hash=current_prev,
        system_time=ts,
        reason="case_bundle_loaded",
    )
    cells.append(cell)
    current_prev = cell.cell_id

    # 3. Load Individuals
    for individual in bundle.individuals:
        cell = _load_individual(individual, graph_id, current_prev, ts)
        cells.append(cell)
        current_prev = cell.cell_id

    # 4. Load Organizations
    for org in bundle.organizations:
        cell = _load_organization(org, graph_id, current_prev, ts)
        cells.append(cell)
        current_prev = cell.cell_id

    # 5. Load Accounts
    for account in bundle.accounts:
        cell = _load_account(account, graph_id, current_prev, ts)
        cells.append(cell)
        current_prev = cell.cell_id

    # 6. Load Relationships
    for rel in bundle.relationships:
        cell = _load_relationship(rel, graph_id, current_prev, ts)
        cells.append(cell)
        current_prev = cell.cell_id

    # 7. Load Evidence
    for evidence in bundle.evidence:
        cell = _load_evidence_item(evidence, graph_id, current_prev, ts)
        cells.append(cell)
        current_prev = cell.cell_id

    # 8. Load Events (sorted by timestamp for proper ordering)
    sorted_events = sorted(bundle.events, key=lambda e: e.timestamp)
    for event in sorted_events:
        if isinstance(event, TransactionEvent):
            cell = _load_transaction_event(event, graph_id, current_prev, ts)
        elif isinstance(event, AlertEvent):
            cell = _load_alert_event(event, graph_id, current_prev, ts)
        elif isinstance(event, ScreeningEvent):
            cell = _load_screening_event(event, graph_id, current_prev, ts)
        elif isinstance(event, VerificationEvent):
            cell = _load_verification_event(event, graph_id, current_prev, ts)
        else:
            # Generic event - skip for now
            continue
        cells.append(cell)
        current_prev = cell.cell_id

    # 9. Load Assertions
    for assertion in bundle.assertions:
        cell = _load_assertion(assertion, graph_id, current_prev, ts)
        cells.append(cell)
        current_prev = cell.cell_id

    return cells


def load_case_bundle_to_chain(
    bundle: CaseBundle,
    chain,  # Chain type from chain.py
    system_time: Optional[str] = None,
) -> list[DecisionCell]:
    """
    Load a CaseBundle directly into a Chain.

    Convenience function that loads and appends in one step.

    Args:
        bundle: The CaseBundle to load
        chain: The Chain to append to (must have Genesis)
        system_time: Optional timestamp (defaults to now)

    Returns:
        List of cells that were appended

    Raises:
        ValueError: If chain has no Genesis
    """
    if not chain.has_genesis():
        raise ValueError("Chain must have Genesis before loading cases")

    cells = load_case_bundle(
        bundle=bundle,
        graph_id=chain.graph_id,
        prev_cell_hash=chain.head.cell_id,
        system_time=system_time,
    )

    for cell in cells:
        chain.append(cell)

    return cells


# ============================================================================
# VALIDATION
# ============================================================================

def validate_bundle_for_loading(bundle: CaseBundle) -> list[str]:
    """
    Validate a CaseBundle before loading.

    Returns list of error messages (empty if valid).
    This extends the schema validation with loader-specific checks.
    """
    from .case_schema import validate_case_bundle

    # Run schema validation first
    errors = validate_case_bundle(bundle)

    # Add loader-specific validation
    if not bundle.meta.id:
        errors.append("CaseMeta.id is required")

    if not bundle.meta.jurisdiction:
        errors.append("CaseMeta.jurisdiction is required")

    # Check for duplicate IDs
    individual_ids = [i.id for i in bundle.individuals]
    if len(individual_ids) != len(set(individual_ids)):
        errors.append("Duplicate individual IDs found")

    org_ids = [o.id for o in bundle.organizations]
    if len(org_ids) != len(set(org_ids)):
        errors.append("Duplicate organization IDs found")

    account_ids = [a.id for a in bundle.accounts]
    if len(account_ids) != len(set(account_ids)):
        errors.append("Duplicate account IDs found")

    evidence_ids = [e.id for e in bundle.evidence]
    if len(evidence_ids) != len(set(evidence_ids)):
        errors.append("Duplicate evidence IDs found")

    return errors


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Main functions
    'load_case_bundle',
    'load_case_bundle_to_chain',
    'validate_bundle_for_loading',

    # Constants
    'CASE_LOADER_VERSION',
    'NS_FINCRIME',
    'NS_CASE',
    'NS_PHASE',
    'NS_ENTITY',
    'NS_ACCOUNT',
    'NS_RELATIONSHIP',
    'NS_EVIDENCE',
    'NS_TRANSACTION',
    'NS_ALERT',
    'NS_SCREENING',
    'NS_VERIFICATION',
    'NS_ASSERTION',
]
