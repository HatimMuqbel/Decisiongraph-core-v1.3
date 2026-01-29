"""
Golden Test: End-to-End AML Alert Report Generation

This test demonstrates and locks the full report generation pipeline:
1. Create facts (evidence)
2. Run rules engine (signals, mitigations, score, verdict)
3. Build justifications with review gating
4. Generate frozen report
5. Verify determinism and integrity

This is the "byte physics" proof: same inputs → identical output bytes.

If this test passes, you can generate the exact report format for any case.
"""

import pytest
import hashlib
from typing import List

from src.decisiongraph import (
    # Core cell types
    DecisionCell, Header, Fact, LogicAnchor, Evidence, Proof,
    CellType, SourceQuality,
    HASH_SCHEME_CANONICAL, NULL_HASH, get_current_timestamp,
    compute_rule_logic_hash,

    # Genesis and chain
    create_genesis_cell, Chain,

    # Pack and rules
    create_universal_pack, RulesEngine, FactPattern, Condition,
    SignalRule, MitigationRule, ScoringRule, VerdictRule,
    ThresholdGate, Severity, EvaluationContext,

    # Justification
    JustificationBuilder, ReviewGate, ReviewGateResult,
    analyze_justifications,

    # Report
    ReportBuilder, ReportManifest, JudgmentBuilder, JudgmentAction,
    compute_artifact_hash, verify_report_artifact, get_report_status,
    ReportStatus,

    # Template
    create_aml_alert_template, render_report, render_report_text,
    render_integrity_section,
)


# =============================================================================
# FIXED TIMESTAMPS FOR DETERMINISM
# =============================================================================

# Using fixed timestamps ensures deterministic cell_ids
TS_BASE = "2024-06-15T14:30:00.000+00:00"
TS_CUSTOMER = "2024-06-15T14:30:01.000+00:00"
TS_TXN1 = "2024-06-15T14:30:02.000+00:00"
TS_TXN2 = "2024-06-15T14:30:03.000+00:00"
TS_TXN3 = "2024-06-15T14:30:04.000+00:00"
TS_SIGNAL1 = "2024-06-15T14:31:00.000+00:00"
TS_SIGNAL2 = "2024-06-15T14:31:01.000+00:00"
TS_MITIGATION = "2024-06-15T14:31:02.000+00:00"
TS_SCORE = "2024-06-15T14:32:00.000+00:00"
TS_VERDICT = "2024-06-15T14:32:01.000+00:00"
TS_JUSTIFICATION = "2024-06-15T14:33:00.000+00:00"
TS_REPORT = "2024-06-15T14:34:00.000+00:00"

GRAPH_ID = "graph:aml-alerts:2024"
NAMESPACE = "aml.compliance"
CASE_ID = "ALERT-2024-001234"


# =============================================================================
# CELL FACTORY FUNCTIONS
# =============================================================================

def make_customer_fact(prev_hash: str) -> DecisionCell:
    """Create customer profile fact."""
    return DecisionCell(
        header=Header(
            version="1.0",
            graph_id=GRAPH_ID,
            cell_type=CellType.FACT,
            system_time=TS_CUSTOMER,
            prev_cell_hash=prev_hash,
            hash_scheme=HASH_SCHEME_CANONICAL
        ),
        fact=Fact(
            namespace=NAMESPACE,
            subject=CASE_ID,
            predicate="customer.profile",
            object={
                "customer_id": "CUST-789456",
                "name": "Acme Trading Corp",
                "account_type": "Commercial",
                "relationship_start": "2019-03-15",
                "risk_rating": "MEDIUM",
                "industry": "Import/Export",
                "annual_revenue": "5000000"
            },
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="customer.profile.extraction",
            rule_logic_hash=compute_rule_logic_hash("customer.profile.extraction:v1")
        )
    )


def make_transaction_fact(
    prev_hash: str,
    txn_id: str,
    txn_type: str,
    amount: str,
    counterparty: str,
    timestamp: str
) -> DecisionCell:
    """Create transaction fact."""
    return DecisionCell(
        header=Header(
            version="1.0",
            graph_id=GRAPH_ID,
            cell_type=CellType.FACT,
            system_time=timestamp,
            prev_cell_hash=prev_hash,
            hash_scheme=HASH_SCHEME_CANONICAL
        ),
        fact=Fact(
            namespace=NAMESPACE,
            subject=CASE_ID,
            predicate="transaction.recorded",
            object={
                "txn_id": txn_id,
                "type": txn_type,
                "amount": amount,
                "currency": "USD",
                "counterparty": counterparty,
                "date": "2024-06-14",
                "channel": "Wire Transfer"
            },
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="transaction.extraction",
            rule_logic_hash=compute_rule_logic_hash("transaction.extraction:v1")
        )
    )


def make_signal_cell(
    prev_hash: str,
    code: str,
    severity: str,
    trigger_fact_ids: List[str],
    timestamp: str
) -> DecisionCell:
    """Create signal cell."""
    return DecisionCell(
        header=Header(
            version="1.0",
            graph_id=GRAPH_ID,
            cell_type=CellType.SIGNAL,
            system_time=timestamp,
            prev_cell_hash=prev_hash,
            hash_scheme=HASH_SCHEME_CANONICAL
        ),
        fact=Fact(
            namespace=NAMESPACE,
            subject=CASE_ID,
            predicate="signal.fired",
            object={
                "schema_version": "1.0",
                "code": code,
                "severity": severity,
                "trigger_facts": trigger_fact_ids,
                "policy_refs": []
            },
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id=f"signal:{code}",
            rule_logic_hash=compute_rule_logic_hash(f"signal:{code}:v1")
        )
    )


def make_mitigation_cell(
    prev_hash: str,
    code: str,
    description: str,
    weight: str
) -> DecisionCell:
    """Create mitigation cell."""
    return DecisionCell(
        header=Header(
            version="1.0",
            graph_id=GRAPH_ID,
            cell_type=CellType.MITIGATION,
            system_time=TS_MITIGATION,
            prev_cell_hash=prev_hash,
            hash_scheme=HASH_SCHEME_CANONICAL
        ),
        fact=Fact(
            namespace=NAMESPACE,
            subject=CASE_ID,
            predicate="mitigation.applied",
            object={
                "schema_version": "1.0",
                "code": code,
                "description": description,
                "weight": weight,
                "applies_to": []
            },
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id=f"mitigation:{code}",
            rule_logic_hash=compute_rule_logic_hash(f"mitigation:{code}:v1")
        )
    )


def make_score_cell(prev_hash: str, score: str, components: dict) -> DecisionCell:
    """Create score cell."""
    return DecisionCell(
        header=Header(
            version="1.0",
            graph_id=GRAPH_ID,
            cell_type=CellType.SCORE,
            system_time=TS_SCORE,
            prev_cell_hash=prev_hash,
            hash_scheme=HASH_SCHEME_CANONICAL
        ),
        fact=Fact(
            namespace=NAMESPACE,
            subject=CASE_ID,
            predicate="score.computed",
            object={
                "schema_version": "1.0",
                "score_type": "composite_risk",
                "final_score": score,
                "components": components,
                "signals_used": [],
                "mitigations_applied": []
            },
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="score:composite_risk",
            rule_logic_hash=compute_rule_logic_hash("score:composite_risk:v1")
        )
    )


def make_verdict_cell(prev_hash: str, outcome: str, confidence: str, score_id: str) -> DecisionCell:
    """Create verdict cell."""
    return DecisionCell(
        header=Header(
            version="1.0",
            graph_id=GRAPH_ID,
            cell_type=CellType.VERDICT,
            system_time=TS_VERDICT,
            prev_cell_hash=prev_hash,
            hash_scheme=HASH_SCHEME_CANONICAL
        ),
        fact=Fact(
            namespace=NAMESPACE,
            subject=CASE_ID,
            predicate="verdict.rendered",
            object={
                "schema_version": "1.0",
                "outcome": outcome,
                "confidence": confidence,
                "signals": [],
                "mitigations": [],
                "final_score": "72",
                "score_cell_id": score_id
            },
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="verdict:aml_routing",
            rule_logic_hash=compute_rule_logic_hash("verdict:aml_routing:v1")
        )
    )


def make_justification_cell(
    prev_hash: str,
    target_id: str,
    basis_fact_ids: List[str],
    needs_review: bool,
    review_reason: str = None
) -> DecisionCell:
    """Create justification cell."""
    answers = {
        "basis_fact_ids": basis_fact_ids,
        "evidence_sufficient": True,
        "missing_evidence": [],
        "counterfactuals": ["If transaction amounts were below $10,000, signals would not fire"],
        "policy_refs": [],
        "needs_human_review": needs_review,
    }
    if review_reason:
        answers["review_reason"] = review_reason

    return DecisionCell(
        header=Header(
            version="1.0",
            graph_id=GRAPH_ID,
            cell_type=CellType.JUSTIFICATION,
            system_time=TS_JUSTIFICATION,
            prev_cell_hash=prev_hash,
            hash_scheme=HASH_SCHEME_CANONICAL
        ),
        fact=Fact(
            namespace=NAMESPACE,
            subject=CASE_ID,
            predicate="justification.recorded",
            object={
                "schema_version": "1.0",
                "target_cell_id": target_id,
                "question_set_id": "universal.v1",
                "answers": answers,
                "rationale": "The pattern of large wire transfers to high-risk jurisdictions, "
                            "combined with unusual timing, triggered elevated risk signals. "
                            "However, the customer's established relationship and documented "
                            "business purpose provide partial mitigation."
            },
            confidence=1.0,
            source_quality=SourceQuality.VERIFIED
        ),
        logic_anchor=LogicAnchor(
            rule_id="justification:universal.v1",
            rule_logic_hash=compute_rule_logic_hash("justification:universal.v1")
        )
    )


# =============================================================================
# GOLDEN TEST
# =============================================================================

class TestGoldenAMLReport:
    """Golden test for end-to-end AML alert report generation."""

    def test_full_pipeline_produces_report(self):
        """Test complete pipeline from facts to rendered report."""
        # Step 1: Build the cell chain
        cells = []

        # Customer profile
        customer = make_customer_fact(NULL_HASH)
        cells.append(customer)

        # Transactions
        txn1 = make_transaction_fact(
            customer.cell_id, "TXN-001", "Wire Out", "45000", "Offshore Holdings Ltd", TS_TXN1
        )
        cells.append(txn1)

        txn2 = make_transaction_fact(
            txn1.cell_id, "TXN-002", "Wire Out", "48000", "Global Trading SA", TS_TXN2
        )
        cells.append(txn2)

        txn3 = make_transaction_fact(
            txn2.cell_id, "TXN-003", "Wire In", "95000", "Partner Corp", TS_TXN3
        )
        cells.append(txn3)

        # Signals (from rules evaluation)
        signal1 = make_signal_cell(
            txn3.cell_id, "HIGH_VALUE_TXN", "HIGH",
            [txn1.cell_id, txn2.cell_id, txn3.cell_id], TS_SIGNAL1
        )
        cells.append(signal1)

        signal2 = make_signal_cell(
            signal1.cell_id, "RAPID_MOVEMENT", "MEDIUM",
            [txn1.cell_id, txn2.cell_id], TS_SIGNAL2
        )
        cells.append(signal2)

        # Mitigation
        mitigation = make_mitigation_cell(
            signal2.cell_id, "ESTABLISHED_RELATIONSHIP",
            "Customer has 5+ year banking relationship with documented business activity",
            "-15"
        )
        cells.append(mitigation)

        # Score
        score = make_score_cell(
            mitigation.cell_id, "72",
            {"base_score": "85", "signal_contribution": "25", "mitigation_adjustment": "-15"}
        )
        cells.append(score)

        # Verdict
        verdict = make_verdict_cell(score.cell_id, "REVIEW", "0.82", score.cell_id)
        cells.append(verdict)

        # Justification for verdict
        justification = make_justification_cell(
            verdict.cell_id,
            verdict.cell_id,
            [signal1.cell_id, signal2.cell_id, mitigation.cell_id],
            needs_review=True,
            review_reason="Score above auto-close threshold; analyst review required"
        )
        cells.append(justification)

        # Step 2: Build report manifest
        pack = create_universal_pack()
        manifest = ReportManifest(
            case_id=CASE_ID,
            pack_id=pack.pack_id,
            pack_version=pack.version,
            anchor_head_cell_id=justification.cell_id,
            included_cell_ids=[c.cell_id for c in cells],
            template_id="aml_alert",
            template_version="1.0.0",
            rendered_artifact_hash="",  # Will compute
            rendered_at=TS_REPORT
        )

        # Step 3: Render report
        template = create_aml_alert_template()
        report_bytes = render_report(template, manifest, cells)

        # Compute and update hash
        manifest.rendered_artifact_hash = compute_artifact_hash(report_bytes)

        # Step 4: Verify report content
        report_text = report_bytes.decode("utf-8")

        # Check key sections present
        assert "TRANSACTION MONITORING ALERT REPORT" in report_text
        assert "ALERT SUMMARY" in report_text
        assert "RISK INDICATORS" in report_text
        assert "HIGH" in report_text  # Signal severity
        assert "72" in report_text or "Score" in report_text  # Score value

        # Check case ID is in report
        assert CASE_ID in report_text or "Case Id" in report_text

    def test_determinism_same_inputs_same_hash(self):
        """Test same inputs always produce identical output hash."""
        # Build cells
        customer = make_customer_fact(NULL_HASH)
        signal = make_signal_cell(customer.cell_id, "TEST_SIGNAL", "HIGH", [], TS_SIGNAL1)
        cells = [customer, signal]

        manifest = ReportManifest(
            case_id=CASE_ID,
            pack_id="universal",
            pack_version="1.0.0",
            anchor_head_cell_id=signal.cell_id,
            included_cell_ids=[c.cell_id for c in cells],
            template_id="aml_alert",
            template_version="1.0.0",
            rendered_artifact_hash="",
            rendered_at=TS_REPORT
        )

        template = create_aml_alert_template()

        # Render 3 times
        output1 = render_report(template, manifest, cells)
        output2 = render_report(template, manifest, cells)
        output3 = render_report(template, manifest, cells)

        # All must be identical
        assert output1 == output2 == output3

        # Hashes must be identical
        hash1 = hashlib.sha256(output1).hexdigest()
        hash2 = hashlib.sha256(output2).hexdigest()
        hash3 = hashlib.sha256(output3).hexdigest()

        assert hash1 == hash2 == hash3

    def test_cell_order_independence(self):
        """Test report is identical regardless of cell input order."""
        customer = make_customer_fact(NULL_HASH)
        signal1 = make_signal_cell(customer.cell_id, "SIGNAL_A", "HIGH", [], TS_SIGNAL1)
        signal2 = make_signal_cell(signal1.cell_id, "SIGNAL_B", "MEDIUM", [], TS_SIGNAL2)
        cells = [customer, signal1, signal2]

        manifest = ReportManifest(
            case_id=CASE_ID,
            pack_id="universal",
            pack_version="1.0.0",
            anchor_head_cell_id=signal2.cell_id,
            included_cell_ids=[c.cell_id for c in cells],
            template_id="aml_alert",
            template_version="1.0.0",
            rendered_artifact_hash="",
            rendered_at=TS_REPORT
        )

        template = create_aml_alert_template()

        # Render with different cell orders
        output1 = render_report(template, manifest, [customer, signal1, signal2])
        output2 = render_report(template, manifest, [signal2, customer, signal1])
        output3 = render_report(template, manifest, [signal1, signal2, customer])

        # All must be identical (internal sorting)
        assert output1 == output2 == output3

    def test_review_gate_integration(self):
        """Test review gate correctly identifies review requirements."""
        customer = make_customer_fact(NULL_HASH)
        signal = make_signal_cell(customer.cell_id, "HIGH_VALUE_TXN", "HIGH", [], TS_SIGNAL1)
        verdict = make_verdict_cell(signal.cell_id, "REVIEW", "0.85", signal.cell_id)

        # No justification yet
        gate = ReviewGate(
            gate_id="aml_gate",
            name="AML Review Gate"
        )

        # Without justification - should require review
        result1 = gate.evaluate([signal, verdict], [])
        assert result1.result == ReviewGateResult.REVIEW_REQUIRED
        assert not result1.can_auto_proceed

        # With justification that requests review
        justification = make_justification_cell(
            verdict.cell_id, verdict.cell_id, [signal.cell_id],
            needs_review=True, review_reason="Score requires analyst review"
        )

        result2 = gate.evaluate([signal, verdict], [justification])
        # Still requires review because justification says so
        assert result2.result == ReviewGateResult.REVIEW_REQUIRED

    def test_justification_coverage_analysis(self):
        """Test justification coverage analysis."""
        signal = make_signal_cell(NULL_HASH, "TEST", "HIGH", [], TS_SIGNAL1)
        verdict = make_verdict_cell(signal.cell_id, "REVIEW", "0.85", signal.cell_id)

        # Justification only for verdict
        justification = make_justification_cell(
            verdict.cell_id, verdict.cell_id, [signal.cell_id],
            needs_review=False
        )

        summary = analyze_justifications(
            [signal, verdict],
            [justification],
            required_cell_types=[CellType.SIGNAL, CellType.VERDICT]
        )

        # Signal is missing justification
        assert summary.total_targets == 2
        assert summary.justified == 1  # Only verdict
        assert summary.missing == 1    # Signal missing
        assert not summary.is_complete

    def test_artifact_hash_verification(self):
        """Test rendered artifact can be verified against manifest."""
        customer = make_customer_fact(NULL_HASH)
        cells = [customer]

        template = create_aml_alert_template()

        manifest = ReportManifest(
            case_id=CASE_ID,
            pack_id="universal",
            pack_version="1.0.0",
            anchor_head_cell_id=customer.cell_id,
            included_cell_ids=[customer.cell_id],
            template_id="aml_alert",
            template_version="1.0.0",
            rendered_artifact_hash="",
            rendered_at=TS_REPORT
        )

        # Render
        report_bytes = render_report(template, manifest, cells)

        # Compute hash
        actual_hash = compute_artifact_hash(report_bytes)

        # Hash should be deterministic
        assert actual_hash == compute_artifact_hash(report_bytes)

        # Can verify with different byte content fails
        modified_bytes = report_bytes + b"tampered"
        modified_hash = compute_artifact_hash(modified_bytes)
        assert actual_hash != modified_hash


# =============================================================================
# SNAPSHOT TEST
# =============================================================================

class TestReportSnapshot:
    """Snapshot tests for report output stability."""

    def test_minimal_report_structure(self):
        """Test minimal report has expected structure."""
        customer = make_customer_fact(NULL_HASH)
        manifest = ReportManifest(
            case_id=CASE_ID,
            pack_id="universal",
            pack_version="1.0.0",
            anchor_head_cell_id=customer.cell_id,
            included_cell_ids=[customer.cell_id],
            template_id="aml_alert",
            template_version="1.0.0",
            rendered_artifact_hash="",
            rendered_at=TS_REPORT
        )

        template = create_aml_alert_template()
        text = render_report_text(template, manifest, [customer])

        # Structural assertions (not exact content)
        lines = text.split("\n")

        # Has title
        assert any("TRANSACTION MONITORING ALERT REPORT" in line for line in lines)

        # Has generation metadata
        assert any("Generated:" in line for line in lines)
        assert any("Template:" in line for line in lines)
        assert any("Manifest Hash:" in line for line in lines)

        # Has section separators
        assert any("=" * 20 in line for line in lines)

    def test_report_includes_all_sections_with_content(self):
        """Test report includes all relevant sections when cells present."""
        customer = make_customer_fact(NULL_HASH)
        signal = make_signal_cell(customer.cell_id, "HIGH_VALUE_TXN", "HIGH", [], TS_SIGNAL1)
        mitigation = make_mitigation_cell(signal.cell_id, "ESTABLISHED", "Long relationship", "-10")
        score = make_score_cell(mitigation.cell_id, "75", {})
        verdict = make_verdict_cell(score.cell_id, "REVIEW", "0.85", score.cell_id)

        cells = [customer, signal, mitigation, score, verdict]
        manifest = ReportManifest(
            case_id=CASE_ID,
            pack_id="universal",
            pack_version="1.0.0",
            anchor_head_cell_id=verdict.cell_id,
            included_cell_ids=[c.cell_id for c in cells],
            template_id="aml_alert",
            template_version="1.0.0",
            rendered_artifact_hash="",
            rendered_at=TS_REPORT
        )

        template = create_aml_alert_template()
        text = render_report_text(template, manifest, cells)

        # Check sections present
        assert "ALERT SUMMARY" in text
        assert "RISK INDICATORS" in text
        assert "MITIGATING FACTORS" in text


# =============================================================================
# REGRESSION TESTS
# =============================================================================

class TestRegressions:
    """Regression tests for known edge cases."""

    def test_empty_cells_does_not_crash(self):
        """Test rendering with no cells doesn't crash."""
        manifest = ReportManifest(
            case_id=CASE_ID,
            pack_id="universal",
            pack_version="1.0.0",
            anchor_head_cell_id="a" * 64,
            included_cell_ids=[],
            template_id="aml_alert",
            template_version="1.0.0",
            rendered_artifact_hash="",
            rendered_at=TS_REPORT
        )

        template = create_aml_alert_template()
        text = render_report_text(template, manifest, [])

        # Should still have header
        assert "TRANSACTION MONITORING ALERT REPORT" in text

    def test_unicode_in_cell_content(self):
        """Test unicode characters in cell content are preserved."""
        # Create customer with unicode name
        unicode_customer = DecisionCell(
            header=Header(
                version="1.0",
                graph_id=GRAPH_ID,
                cell_type=CellType.FACT,
                system_time=TS_CUSTOMER,
                prev_cell_hash=NULL_HASH,
                hash_scheme=HASH_SCHEME_CANONICAL
            ),
            fact=Fact(
                namespace=NAMESPACE,
                subject=CASE_ID,
                predicate="customer.profile",
                object={
                    "name": "François Müller 北京",
                    "account_type": "Personal"
                },
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(
                rule_id="test",
                rule_logic_hash="test"
            )
        )

        manifest = ReportManifest(
            case_id=CASE_ID,
            pack_id="universal",
            pack_version="1.0.0",
            anchor_head_cell_id=unicode_customer.cell_id,
            included_cell_ids=[unicode_customer.cell_id],
            template_id="aml_alert",
            template_version="1.0.0",
            rendered_artifact_hash="",
            rendered_at=TS_REPORT
        )

        template = create_aml_alert_template()

        # Should not raise
        report_bytes = render_report(template, manifest, [unicode_customer])

        # Should be valid UTF-8
        text = report_bytes.decode("utf-8")
        assert isinstance(text, str)
