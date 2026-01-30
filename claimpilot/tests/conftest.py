"""
Pytest configuration and fixtures for ClaimPilot tests.

Provides helper factories and common fixtures matching actual model definitions.
"""
import pytest
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from claimpilot.models import (
    ClaimContext,
    ClaimantType,
    Condition,
    ConditionOperator,
    CoverageSection,
    DispositionType,
    DocumentRequirement,
    EvidenceItem,
    EvidenceRule,
    EvidenceStatus,
    Exclusion,
    Fact,
    FactCertainty,
    FactSource,
    GateStrictness,
    LineOfBusiness,
    LossTypeTrigger,
    Policy,
    Predicate,
    TimelineAnchor,
    TimelineEventType,
    TimelineRule,
)


# =============================================================================
# Factory Helpers
# =============================================================================

def make_fact(
    field: str,
    value,
    claim_id: str = "CLM-001",
    source: FactSource = FactSource.ADJUSTER_INPUT,
    certainty: FactCertainty = FactCertainty.REPORTED,
) -> Fact:
    """Create a Fact with required fields."""
    # Infer value type
    if isinstance(value, bool):
        value_type = "boolean"
    elif isinstance(value, (int, float)):
        value_type = "number"
    elif isinstance(value, Decimal):
        value_type = "decimal"
    elif isinstance(value, date):
        value_type = "date"
    elif isinstance(value, list):
        value_type = "list"
    else:
        value_type = "string"

    return Fact(
        id=str(uuid4()),
        claim_id=claim_id,
        field=field,
        value=value,
        value_type=value_type,
        source=source,
        certainty=certainty,
    )


def make_evidence(
    doc_type: str,
    claim_id: str = "CLM-001",
    status: EvidenceStatus = EvidenceStatus.RECEIVED,
    description: str = None,
) -> EvidenceItem:
    """Create an EvidenceItem with required fields."""
    return EvidenceItem(
        id=str(uuid4()),
        claim_id=claim_id,
        doc_type=doc_type,
        description=description or f"{doc_type} document",
        status=status,
        received_at=datetime.now(timezone.utc) if status == EvidenceStatus.RECEIVED else None,
    )


def make_claim_context(
    claim_id: str = "CLM-001",
    policy_id: str = "POL-001",
    jurisdiction: str = "CA-ON",
    line_of_business: LineOfBusiness = LineOfBusiness.AUTO,
    loss_type: str = "collision",
    loss_date: date = None,
    report_date: date = None,
    claimant_type: ClaimantType = ClaimantType.INSURED,
    facts: dict = None,
    evidence: list = None,
    metadata: dict = None,
) -> ClaimContext:
    """Create a ClaimContext with required fields."""
    if loss_date is None:
        loss_date = date(2024, 6, 10)
    if report_date is None:
        report_date = date(2024, 6, 15)

    return ClaimContext(
        claim_id=claim_id,
        policy_id=policy_id,
        jurisdiction=jurisdiction,
        line_of_business=line_of_business,
        loss_type=loss_type,
        loss_date=loss_date,
        report_date=report_date,
        claimant_type=claimant_type,
        facts=facts or {},
        evidence=evidence or [],
        metadata=metadata or {},
    )


def make_coverage_section(
    id: str,
    name: str,
    code: str = None,
    description: str = None,
    triggers: list = None,
    preconditions: list = None,
) -> CoverageSection:
    """Create a CoverageSection with required fields."""
    return CoverageSection(
        id=id,
        code=code or id.upper(),
        name=name,
        description=description or f"{name} coverage",
        triggers=triggers or [],
        preconditions=preconditions or [],
    )


def make_exclusion(
    id: str,
    name: str,
    code: str = None,
    description: str = None,
    policy_wording: str = None,
    policy_section_ref: str = None,
    applies_to_coverages: list = None,
    trigger_conditions: list = None,
) -> Exclusion:
    """Create an Exclusion with required fields."""
    return Exclusion(
        id=id,
        code=code or f"{id}-code",
        name=name,
        description=description or f"{name} exclusion",
        policy_wording=policy_wording or f"This policy does not cover {name.lower()}",
        policy_section_ref=policy_section_ref or f"Section {id}",
        applies_to_coverages=applies_to_coverages or [],
        trigger_conditions=trigger_conditions or [],
    )


def make_policy(
    id: str = "TEST-POL-001",
    jurisdiction: str = "CA-ON",
    line_of_business: LineOfBusiness = LineOfBusiness.AUTO,
    product_code: str = "OAP1",
    name: str = "Test Policy",
    version: str = "2024.1",
    effective_date: date = None,
    coverage_sections: list = None,
    exclusions: list = None,
) -> Policy:
    """Create a Policy with required fields."""
    if effective_date is None:
        effective_date = date(2024, 1, 1)

    return Policy(
        id=id,
        jurisdiction=jurisdiction,
        line_of_business=line_of_business,
        product_code=product_code,
        name=name,
        version=version,
        effective_date=effective_date,
        coverage_sections=coverage_sections or [],
        exclusions=exclusions or [],
    )


def make_condition(
    op: ConditionOperator,
    field: str = None,
    value = None,
    children: list = None,
    id: str = None,
    description: str = None,
) -> Condition:
    """Create a Condition (either predicate or logical)."""
    logical_ops = {ConditionOperator.AND, ConditionOperator.OR, ConditionOperator.NOT}

    if op in logical_ops:
        return Condition(
            id=id,
            op=op,
            children=children or [],
            description=description,
        )
    else:
        return Condition(
            id=id,
            op=op,
            predicate=Predicate(
                field=field or "",
                operator=op,
                value=value,
                description=description,
            ),
            description=description,
        )


def make_timeline_rule(
    id: str,
    name: str,
    event_type: TimelineEventType,
    anchor: TimelineAnchor,
    days_from_anchor: int,
    business_days: bool = True,
    description: str = None,
) -> TimelineRule:
    """Create a TimelineRule."""
    return TimelineRule(
        id=id,
        name=name,
        event_type=event_type,
        anchor=anchor,
        days_from_anchor=days_from_anchor,
        business_days=business_days,
        description=description or name,
    )


def make_evidence_rule(
    id: str,
    name: str,
    required_documents: list = None,
    recommended_documents: list = None,
    applies_when: Condition = None,
    disposition_type: DispositionType = None,
) -> EvidenceRule:
    """Create an EvidenceRule."""
    return EvidenceRule(
        id=id,
        name=name,
        required_documents=required_documents or [],
        recommended_documents=recommended_documents or [],
        applies_when=applies_when,
        disposition_type=disposition_type,
    )


def make_document_requirement(
    doc_type: str,
    description: str = None,
    strictness: GateStrictness = GateStrictness.BLOCKING_FINALIZATION,
    alternatives: list = None,
) -> DocumentRequirement:
    """Create a DocumentRequirement."""
    return DocumentRequirement(
        doc_type=doc_type,
        description=description or f"Required: {doc_type}",
        strictness=strictness,
        alternatives=alternatives or [],
    )


# =============================================================================
# Common Fixtures
# =============================================================================

@pytest.fixture
def sample_facts():
    """Common fact set for testing."""
    return {
        "vehicle_use": make_fact("vehicle_use", "personal"),
        "claim_amount": make_fact("claim_amount", 15000),
        "fault_percentage": make_fact("fault_percentage", 30),
        "is_total_loss": make_fact("is_total_loss", False),
    }


@pytest.fixture
def sample_evidence():
    """Common evidence set for testing."""
    return [
        make_evidence("photos"),
        make_evidence("repair_estimate"),
        make_evidence("proof_of_loss"),
    ]


@pytest.fixture
def basic_collision_coverage():
    """Basic collision coverage section."""
    return make_coverage_section(
        id="collision",
        name="Collision Coverage",
        triggers=[
            LossTypeTrigger(
                loss_type="collision",
                claimant_types=[ClaimantType.INSURED],
            ),
        ],
    )


@pytest.fixture
def comprehensive_coverage():
    """Comprehensive coverage section."""
    return make_coverage_section(
        id="comprehensive",
        name="Comprehensive Coverage",
        triggers=[
            LossTypeTrigger(loss_type="theft"),
            LossTypeTrigger(loss_type="vandalism"),
            LossTypeTrigger(loss_type="fire"),
        ],
    )


@pytest.fixture
def commercial_use_exclusion():
    """Commercial use exclusion."""
    return make_exclusion(
        id="commercial-use",
        name="Commercial Use Exclusion",
        code="4.1",
        applies_to_coverages=["collision", "comprehensive"],
        trigger_conditions=[
            make_condition(
                op=ConditionOperator.EQ,
                field="vehicle_use",
                value="commercial",
            ),
        ],
    )


@pytest.fixture
def basic_policy(basic_collision_coverage, comprehensive_coverage, commercial_use_exclusion):
    """Basic test policy."""
    return make_policy(
        coverage_sections=[basic_collision_coverage, comprehensive_coverage],
        exclusions=[commercial_use_exclusion],
    )


@pytest.fixture
def basic_claim(sample_facts, sample_evidence):
    """Basic collision claim."""
    return make_claim_context(
        facts=sample_facts,
        evidence=sample_evidence,
    )


@pytest.fixture
def acknowledge_rule():
    """FSRA acknowledgment rule."""
    return make_timeline_rule(
        id="acknowledge",
        name="Acknowledge Claim",
        event_type=TimelineEventType.ACKNOWLEDGE,
        anchor=TimelineAnchor.REPORT_DATE,
        days_from_anchor=3,
        business_days=True,
    )


@pytest.fixture
def collision_evidence_rule():
    """Collision claim evidence rule."""
    return make_evidence_rule(
        id="collision-evidence",
        name="Collision Evidence",
        required_documents=[
            make_document_requirement(
                "photos",
                strictness=GateStrictness.BLOCKING_RECOMMENDATION,
            ),
            make_document_requirement(
                "repair_estimate",
                strictness=GateStrictness.BLOCKING_FINALIZATION,
            ),
        ],
        applies_when=make_condition(
            op=ConditionOperator.EQ,
            field="loss_type",
            value="collision",
        ),
    )
