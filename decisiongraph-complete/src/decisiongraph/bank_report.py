"""
DecisionGraph Bank-Grade Report Module (v2.0)

Implements the 4-Gate Protocol report format with:
- Contextual Typology (Gate 1)
- Inherent Risks + Mitigating Factors (Gate 2)
- Residual Risk Calculation with Evidence Anchor Grid (Gate 3)
- Integrity Audit (Gate 4)
- Policy Citations with quality metrics
- Feedback Scores (Opik-style evaluation)
- Required Actions with SLA

This module produces auditor-ready reports that meet bank regulatory
requirements for transaction monitoring and KYC case documentation.

USAGE:
    from decisiongraph.bank_report import (
        BankReportRenderer, ReportConfig, render_bank_report
    )

    renderer = BankReportRenderer(config=ReportConfig())
    report_bytes = renderer.render(
        case_bundle=bundle,
        eval_result=result,
        pack_runtime=pack,
        chain=chain,
        citation_registry=registry,
    )
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import hashlib

from .cell import DecisionCell, CellType, get_current_timestamp
from .citations import (
    CitationRegistry, CitationQuality,
    format_citations_section, format_citation_quality_section
)
from .gates import (
    GateStatus, GateResult, GateConfig, GateEvaluator
)
from .confidence import (
    ConfidenceCalculator, ConfidenceConfig, ConfidenceResult
)
from .actions import (
    ActionGenerator, ActionConfig, GeneratedAction, ActionPriority,
    format_actions_for_report
)


# =============================================================================
# EXCEPTIONS
# =============================================================================

class BankReportError(Exception):
    """Base exception for bank report errors."""
    pass


class RenderError(BankReportError):
    """Raised when rendering fails."""
    pass


# =============================================================================
# ENUMS
# =============================================================================

class TypologyClass(str, Enum):
    """Typology classifications for Gate 1."""
    TECH_INVESTMENT = "TECH_INVESTMENT"
    TRADE_BASED_ML = "TRADE_BASED_ML"
    REAL_ESTATE_ML = "REAL_ESTATE_ML"
    SHELL_COMPANY = "SHELL_COMPANY"
    STRUCTURING = "STRUCTURING"
    CRYPTO_MIXING = "CRYPTO_MIXING"
    LAYERING = "LAYERING"
    INTEGRATION = "INTEGRATION"
    PLACEMENT = "PLACEMENT"
    KYC_ONBOARDING = "KYC_ONBOARDING"
    EDD_REVIEW = "EDD_REVIEW"
    PERIODIC_REVIEW = "PERIODIC_REVIEW"
    SANCTIONS_SCREENING = "SANCTIONS_SCREENING"
    UNKNOWN = "UNKNOWN"


# GateStatus imported from gates module

# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class ReportConfig:
    """Configuration for report rendering."""
    line_width: int = 72
    include_citations: bool = True
    include_feedback_scores: bool = True
    include_audit_trail: bool = True
    include_case_integrity: bool = True
    include_required_actions: bool = True
    template_id: str = "bank_grade_v1"
    template_version: str = "1.0.0"


# =============================================================================
# EVIDENCE ANCHOR
# =============================================================================

@dataclass
class EvidenceAnchor:
    """
    An evidence anchor links a risk offset to its source data.

    This creates the audit trail showing WHY a weight was applied.
    """
    offset_type: str              # e.g., "Inherent Risk", "Proactive Transparency"
    data_anchor: str              # e.g., "ubo_proactive_disclosure"
    weight: Decimal               # e.g., Decimal("-0.20")
    source_cell_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "offset_type": self.offset_type,
            "data_anchor": self.data_anchor,
            "weight": str(self.weight),
            "source_cell_id": self.source_cell_id,
        }


@dataclass
class EvidenceAnchorGrid:
    """
    Grid of evidence anchors showing the residual risk calculation.

    Provides transparency on how inherent + mitigations = residual.
    """
    inherent_weight: Decimal
    anchors: List[EvidenceAnchor] = field(default_factory=list)

    @property
    def mitigation_sum(self) -> Decimal:
        """Sum of all mitigation weights (should be negative)."""
        return sum((a.weight for a in self.anchors), Decimal("0"))

    @property
    def residual_score(self) -> Decimal:
        """Computed residual score."""
        return max(Decimal("0"), self.inherent_weight + self.mitigation_sum)


# =============================================================================
# FEEDBACK SCORES
# =============================================================================

@dataclass
class FeedbackScores:
    """
    Opik-style feedback scores for evaluation metrics.

    These scores help assess the quality and confidence of the decision.
    """
    confidence: Decimal = Decimal("0.00")
    citation_quality: Decimal = Decimal("0.00")
    signal_coverage: Decimal = Decimal("0.00")
    evidence_completeness: Decimal = Decimal("0.00")
    decision_clarity: Decimal = Decimal("0.00")
    documentation_completeness: Decimal = Decimal("0.00")

    def to_dict(self) -> Dict[str, str]:
        return {
            "confidence": str(self.confidence),
            "citation_quality": str(self.citation_quality),
            "signal_coverage": str(self.signal_coverage),
            "evidence_completeness": str(self.evidence_completeness),
            "decision_clarity": str(self.decision_clarity),
            "documentation_completeness": str(self.documentation_completeness),
        }

    @classmethod
    def compute(
        cls,
        citation_quality: CitationQuality,
        signals_fired: int,
        total_signals: int,
        evidence_anchored: int,
        total_evidence: int,
        auto_archive: bool,
        docs_on_file: int,
        docs_required: int,
        gate_results: Optional[List[GateResult]] = None,
        confidence_config: Optional[ConfidenceConfig] = None,
    ) -> 'FeedbackScores':
        """
        Compute feedback scores from inputs.

        Args:
            citation_quality: CitationQuality from registry
            signals_fired: Number of signals that fired
            total_signals: Total signals in pack
            evidence_anchored: Number of mitigations with evidence anchors
            total_evidence: Total number of mitigations
            auto_archive: Whether auto-archive is permitted
            docs_on_file: Documents on file
            docs_required: Required documents
            gate_results: Optional list of GateResults for gate pass rate
            confidence_config: Optional confidence configuration

        Returns:
            FeedbackScores with all metrics computed
        """
        # Use ConfidenceCalculator for proper weighted confidence
        calculator = ConfidenceCalculator(confidence_config)
        conf_result = calculator.compute(
            citation_quality=citation_quality,
            gate_results=gate_results,
            evidence_anchored=evidence_anchored,
            total_evidence=total_evidence,
            docs_on_file=docs_on_file,
            docs_required=docs_required,
            auto_archive=auto_archive,
            signals_fired=signals_fired,
            total_signals=total_signals,
        )

        # Signal coverage (for backward compatibility)
        sig_cov = Decimal("0.00")
        if total_signals > 0:
            sig_cov = (Decimal(str(signals_fired)) / Decimal(str(total_signals)))

        # Decision clarity
        dec_clar = Decimal("1.00") if auto_archive else Decimal("0.50")

        return cls(
            confidence=conf_result.overall_confidence,
            citation_quality=conf_result.citation_quality,
            signal_coverage=sig_cov.quantize(Decimal("0.01")),
            evidence_completeness=conf_result.evidence_completeness,
            decision_clarity=dec_clar,
            documentation_completeness=conf_result.documentation_score,
        )


# =============================================================================
# REQUIRED ACTION
# =============================================================================

@dataclass
class RequiredAction:
    """A required follow-up action with SLA."""
    action: str
    sla_hours: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "sla_hours": self.sla_hours,
        }


# =============================================================================
# GATE RESULTS
# =============================================================================

# GateResult imported from gates module

# =============================================================================
# BANK REPORT RENDERER
# =============================================================================

class BankReportRenderer:
    """
    Renders bank-grade reports with 4-gate protocol.

    Produces deterministic, auditable reports matching regulatory
    expectations for transaction monitoring and KYC case documentation.

    Can use either inline gate evaluation (default) or a configurable
    GateEvaluator for pack-specific gate definitions.
    """

    def __init__(
        self,
        config: Optional[ReportConfig] = None,
        gate_config: Optional[GateConfig] = None,
        gate_evaluator: Optional[GateEvaluator] = None,
        action_config: Optional[ActionConfig] = None,
        action_generator: Optional[ActionGenerator] = None
    ):
        """
        Initialize renderer.

        Args:
            config: Report rendering configuration
            gate_config: Gate configuration (creates GateEvaluator if provided)
            gate_evaluator: Pre-configured GateEvaluator (takes precedence)
            action_config: Action configuration (creates ActionGenerator if provided)
            action_generator: Pre-configured ActionGenerator (takes precedence)
        """
        self.config = config or ReportConfig()
        # Use provided evaluator, or create from config, or use defaults
        if gate_evaluator:
            self.gate_evaluator = gate_evaluator
        elif gate_config:
            self.gate_evaluator = GateEvaluator(gate_config)
        else:
            self.gate_evaluator = GateEvaluator()  # Default config

        # Action generator
        if action_generator:
            self.action_generator = action_generator
        elif action_config:
            self.action_generator = ActionGenerator(action_config)
        else:
            self.action_generator = ActionGenerator()  # Default config

    def render(
        self,
        case_bundle: Any,  # CaseBundle
        eval_result: Any,  # EvaluationResult
        pack_runtime: Any,  # PackRuntime
        chain: Any,  # Chain
        citation_registry: Optional[CitationRegistry] = None,
        report_timestamp: Optional[str] = None,
    ) -> bytes:
        """
        Render the complete bank-grade report.

        Returns UTF-8 encoded report bytes.
        """
        if not report_timestamp:
            report_timestamp = get_current_timestamp()

        lines = []
        w = self.config.line_width

        # Extract key data
        case_id = case_bundle.meta.id if hasattr(case_bundle, 'meta') else str(case_bundle)
        case_type = case_bundle.meta.case_type.value if hasattr(case_bundle, 'meta') else "UNKNOWN"

        # Determine typology
        typology = self._determine_typology(case_bundle, eval_result)

        # Header
        lines.extend(self._render_header(case_id, case_type, pack_runtime, report_timestamp, w))

        # Case Summary
        lines.extend(self._render_case_summary(case_bundle, w))

        # Transaction/Event Details (if applicable)
        lines.extend(self._render_transaction_details(case_bundle, w))

        # Beneficial Ownership (if applicable)
        lines.extend(self._render_beneficial_ownership(case_bundle, w))

        # Screening Results
        lines.extend(self._render_screening_results(case_bundle, w))

        # Documentation Status
        docs_on_file, docs_required = self._render_documentation_status(case_bundle, w, lines)

        # ===== 4-GATE PROTOCOL =====
        lines.append("")
        lines.append("=" * w)
        lines.append("SECTION 10B: MITIGATING FACTORS ANALYSIS")
        lines.append("=" * w)
        lines.append("")

        # Build evidence anchor grid (needed for Gate 3)
        anchor_grid = self._build_evidence_anchor_grid(eval_result)

        # Gate 1: Contextual Typology
        gate1 = self.gate_evaluator.evaluate_gate_1(case_bundle, typology.value)
        lines.extend(self._render_gate_1(gate1, typology, w))

        # Gate 2: Inherent Risks + Mitigating Factors
        gate2 = self.gate_evaluator.evaluate_gate_2(eval_result)
        lines.extend(self._render_gate_2(eval_result, pack_runtime, w))

        # Gate 3: Residual Risk Calculation
        gate3 = self.gate_evaluator.evaluate_gate_3(eval_result, anchor_grid.residual_score)
        lines.extend(self._render_gate_3(eval_result, anchor_grid, w))

        # Gate 4: Integrity Audit
        gate4 = self.gate_evaluator.evaluate_gate_4(eval_result, chain, typology.value)
        lines.extend(self._render_gate_4(gate4, w))

        # Collect gate results for downstream use
        gate_results_list = [gate1, gate2, gate3, gate4]

        # Policy Citations
        if self.config.include_citations and citation_registry:
            signal_codes = [
                s.fact.object.get("code", "")
                for s in (eval_result.signals if eval_result else [])
            ]
            lines.extend(format_citations_section(citation_registry, signal_codes, w))

            # Citation Quality Summary
            quality = citation_registry.compute_citation_quality(signal_codes)
            lines.extend(format_citation_quality_section(quality, w))

        # Decision
        lines.extend(self._render_decision(eval_result, w))

        # Required Actions (uses gate results for trigger evaluation)
        if self.config.include_required_actions:
            actions = self._generate_required_actions(
                eval_result, pack_runtime, gate_results=gate_results_list
            )
            lines.extend(self._render_required_actions(actions, w))

        # Feedback Scores (uses gate results for confidence calculation)
        if self.config.include_feedback_scores:
            scores = self._compute_feedback_scores(
                eval_result, citation_registry, docs_on_file, docs_required,
                gate_results=gate_results_list
            )
            lines.extend(self._render_feedback_scores(scores, w))

        # Audit Trail
        if self.config.include_audit_trail:
            lines.extend(self._render_audit_trail(
                case_bundle, pack_runtime, report_timestamp, w
            ))

        # Case Integrity
        if self.config.include_case_integrity:
            lines.extend(self._render_case_integrity(chain, pack_runtime, w))

        # Footer
        lines.append("=" * w)
        lines.append("END OF REPORT")
        lines.append("=" * w)
        lines.append("")

        # Join with consistent line endings
        text = "\n".join(lines) + "\n"
        return text.encode("utf-8")

    def _render_header(
        self,
        case_id: str,
        case_type: str,
        pack_runtime: Any,
        timestamp: str,
        w: int
    ) -> List[str]:
        """Render report header."""
        lines = []
        lines.append("=" * w)

        # Determine title based on case type
        if "kyc" in case_type.lower() or "onboarding" in case_type.lower():
            title = "KYC ONBOARDING CASE REPORT"
        elif "aml" in case_type.lower() or "alert" in case_type.lower():
            title = "TRANSACTION MONITORING ALERT REPORT"
        else:
            title = "FINANCIAL CRIME CASE REPORT"

        lines.append(title)
        lines.append(f"Alert ID: {case_id}")
        lines.append("=" * w)
        lines.append("")
        return lines

    def _render_case_summary(self, case_bundle: Any, w: int) -> List[str]:
        """Render case summary section."""
        lines = []
        lines.append("=" * w)
        lines.append("CASE SUMMARY")
        lines.append("=" * w)

        if hasattr(case_bundle, 'meta'):
            meta = case_bundle.meta
            lines.append(f"Case ID:        {meta.id}")
            lines.append(f"Case Type:      {meta.case_type.value.upper()}")
            lines.append(f"Jurisdiction:   {meta.jurisdiction}")
            lines.append(f"Status:         {meta.status.upper()}")
            lines.append(f"Priority:       {meta.priority.upper()}")

        # Primary entity info
        if hasattr(case_bundle, 'individuals') and case_bundle.individuals:
            primary = case_bundle.individuals[0]
            lines.append("")
            lines.append("Primary Customer:")
            lines.append(f"  Name:         {primary.full_name if hasattr(primary, 'full_name') else ''}")
            lines.append(f"  ID:           {primary.id}")
            if hasattr(primary, 'risk_rating') and primary.risk_rating:
                lines.append(f"  Risk Rating:  {primary.risk_rating.value.upper()}")

        if hasattr(case_bundle, 'organizations') and case_bundle.organizations:
            for org in case_bundle.organizations:
                lines.append("")
                lines.append("Organization:")
                lines.append(f"  Name:         {org.legal_name}")
                lines.append(f"  ID:           {org.id}")
                if hasattr(org, 'jurisdiction'):
                    lines.append(f"  Jurisdiction: {org.jurisdiction}")

        lines.append("")
        return lines

    def _render_transaction_details(self, case_bundle: Any, w: int) -> List[str]:
        """Render transaction/event details."""
        lines = []

        if not hasattr(case_bundle, 'events') or not case_bundle.events:
            return lines

        # Filter to transaction events
        txn_events = [e for e in case_bundle.events if getattr(e, 'event_type', '') == 'transaction']
        if not txn_events:
            return lines

        lines.append("=" * w)
        lines.append("TRANSACTION DETAILS")
        lines.append("=" * w)

        for event in txn_events[:5]:  # Limit to first 5
            amount = getattr(event, 'amount', '0')
            currency = getattr(event, 'currency', 'CAD')
            direction = getattr(event, 'direction', '').upper()
            counterparty = getattr(event, 'counterparty_name', '')
            country = getattr(event, 'counterparty_country', '')

            lines.append(f"  [{direction:8}] {amount} {currency}")
            if counterparty:
                lines.append(f"             To: {counterparty}")
            if country:
                lines.append(f"             Country: {country}")

        lines.append("")
        return lines

    def _render_beneficial_ownership(self, case_bundle: Any, w: int) -> List[str]:
        """Render beneficial ownership table."""
        lines = []

        if not hasattr(case_bundle, 'relationships'):
            return lines

        # Look for UBO relationships
        ubo_rels = [
            r for r in case_bundle.relationships
            if hasattr(r, 'relationship_type') and r.relationship_type.value == 'ubo'
        ]

        if not ubo_rels:
            return lines

        lines.append("=" * w)
        lines.append("BENEFICIAL OWNERSHIP")
        lines.append("=" * w)

        # Build UBO table
        lines.append(f"{'Name':<25} {'Ownership':<12} {'PEP Status':<15}")
        lines.append("-" * 52)

        # Look up individual details for each UBO
        individuals_by_id = {}
        if hasattr(case_bundle, 'individuals'):
            individuals_by_id = {ind.id: ind for ind in case_bundle.individuals}

        for rel in ubo_rels:
            from_id = rel.from_entity_id
            ownership = rel.ownership_percentage if hasattr(rel, 'ownership_percentage') else "N/A"
            ownership_str = f"{ownership}%" if ownership != "N/A" else "N/A"

            name = from_id
            pep_status = "None"

            if from_id in individuals_by_id:
                ind = individuals_by_id[from_id]
                if hasattr(ind, 'full_name'):
                    name = ind.full_name
                elif hasattr(ind, 'given_name') and hasattr(ind, 'family_name'):
                    name = f"{ind.given_name} {ind.family_name}"
                if hasattr(ind, 'pep_status') and ind.pep_status:
                    pep_status = ind.pep_status.value.upper()

            lines.append(f"{name:<25} {ownership_str:<12} {pep_status:<15}")

        lines.append("")
        return lines

    def _render_screening_results(self, case_bundle: Any, w: int) -> List[str]:
        """Render screening results section."""
        lines = []

        if not hasattr(case_bundle, 'events'):
            return lines

        screening_events = [
            e for e in case_bundle.events
            if getattr(e, 'event_type', '') == 'screening'
        ]

        if not screening_events:
            return lines

        lines.append("=" * w)
        lines.append("SCREENING RESULTS")
        lines.append("=" * w)

        for event in screening_events:
            screening_type = getattr(event, 'screening_type', 'UNKNOWN').upper()
            disposition = getattr(event, 'disposition', 'UNKNOWN').upper()
            vendor = getattr(event, 'vendor', '')

            status_symbol = "[CLEAR]" if disposition == "CLEAR" else "[HIT]" if disposition == "CONFIRMED" else "[PEND]"
            lines.append(f"  {status_symbol:8} {screening_type:<15} {disposition}")
            if vendor:
                lines.append(f"           Vendor: {vendor}")

        lines.append("")
        return lines

    def _render_documentation_status(
        self,
        case_bundle: Any,
        w: int,
        lines: List[str]
    ) -> Tuple[int, int]:
        """Render documentation status section. Returns (docs_on_file, docs_required)."""
        docs_on_file = 0
        docs_required = 8  # Standard required documents

        if not hasattr(case_bundle, 'evidence') or not case_bundle.evidence:
            return docs_on_file, docs_required

        lines.append("=" * w)
        lines.append("DOCUMENTATION STATUS")
        lines.append("=" * w)

        for evidence in case_bundle.evidence:
            status = "[OK]" if getattr(evidence, 'verified', False) else "[--]"
            ev_type = getattr(evidence, 'evidence_type', 'unknown')
            if hasattr(ev_type, 'value'):
                ev_type = ev_type.value

            lines.append(f"  {status} {ev_type}")
            if getattr(evidence, 'verified', False):
                docs_on_file += 1

        # Summary
        lines.append("")
        score = docs_on_file / docs_required if docs_required > 0 else 0
        lines.append(f"  Documentation Score: {docs_on_file}/{docs_required} ({score:.0%})")
        lines.append("")

        return docs_on_file, docs_required

    def _determine_typology(self, case_bundle: Any, eval_result: Any) -> TypologyClass:
        """Determine the contextual typology for Gate 1."""
        if hasattr(case_bundle, 'meta'):
            case_type = case_bundle.meta.case_type.value.lower()
            if 'kyc' in case_type or 'onboarding' in case_type:
                return TypologyClass.KYC_ONBOARDING
            if 'edd' in case_type:
                return TypologyClass.EDD_REVIEW

        # Check signals for typology indicators
        if eval_result and eval_result.signals:
            for signal in eval_result.signals:
                code = signal.fact.object.get("code", "").upper()
                if "STRUCT" in code:
                    return TypologyClass.STRUCTURING
                if "SHELL" in code:
                    return TypologyClass.SHELL_COMPANY
                if "CRYPTO" in code:
                    return TypologyClass.CRYPTO_MIXING

        return TypologyClass.UNKNOWN

    def _evaluate_gate_1(self, typology: TypologyClass) -> GateResult:
        """Evaluate Gate 1: Contextual Typology."""
        forbidden = [
            TypologyClass.CRYPTO_MIXING,  # Example forbidden typology
        ]

        if typology in forbidden:
            return GateResult(
                gate_name="Contextual Typology",
                gate_number=1,
                status=GateStatus.FAIL,
                details={"typology": typology.value, "forbidden": True}
            )

        return GateResult(
            gate_name="Contextual Typology",
            gate_number=1,
            status=GateStatus.PASS,
            details={"typology": typology.value, "forbidden": False}
        )

    def _evaluate_gate_2(self, eval_result: Any) -> GateResult:
        """Evaluate Gate 2: Inherent Risks + Mitigating Factors."""
        if not eval_result:
            return GateResult(
                gate_name="Inherent Risks + Mitigating Factors",
                gate_number=2,
                status=GateStatus.WARN,
                details={"signals": 0, "mitigations": 0}
            )

        return GateResult(
            gate_name="Inherent Risks + Mitigating Factors",
            gate_number=2,
            status=GateStatus.PASS,
            details={
                "signals": len(eval_result.signals) if eval_result.signals else 0,
                "mitigations": len(eval_result.mitigations) if eval_result.mitigations else 0,
            }
        )

    def _build_evidence_anchor_grid(self, eval_result: Any) -> EvidenceAnchorGrid:
        """Build the evidence anchor grid from evaluation result."""
        inherent = Decimal("0")
        anchors = []

        if eval_result and eval_result.score:
            score_obj = eval_result.score.fact.object
            inherent = Decimal(str(score_obj.get("inherent_score", "0")))

        if eval_result and eval_result.mitigations:
            for mit in eval_result.mitigations:
                obj = mit.fact.object
                # Extract data_anchor from evidence_anchors if available
                evidence_anchors = obj.get("evidence_anchors", [])
                if evidence_anchors:
                    # Use first evidence anchor's field as data_anchor
                    first_anchor = evidence_anchors[0]
                    data_anchor = first_anchor.get("field", "case_evidence")
                else:
                    data_anchor = "case_evidence"

                # Use name if available, otherwise code
                offset_type = obj.get("name", obj.get("code", "Unknown"))

                anchors.append(EvidenceAnchor(
                    offset_type=offset_type,
                    data_anchor=data_anchor,
                    weight=Decimal(str(obj.get("weight", "0"))),
                    source_cell_id=mit.cell_id,
                ))

        return EvidenceAnchorGrid(inherent_weight=inherent, anchors=anchors)

    def _evaluate_gate_3(
        self,
        eval_result: Any,
        anchor_grid: EvidenceAnchorGrid
    ) -> GateResult:
        """Evaluate Gate 3: Residual Risk Calculation."""
        return GateResult(
            gate_name="Residual Risk Calculation",
            gate_number=3,
            status=GateStatus.PASS,
            details={
                "inherent_score": str(anchor_grid.inherent_weight),
                "mitigation_sum": str(anchor_grid.mitigation_sum),
                "residual_score": str(anchor_grid.residual_score),
            }
        )

    def _evaluate_gate_4(self, eval_result: Any, chain: Any) -> GateResult:
        """Evaluate Gate 4: Integrity Audit."""
        typology_match = True
        verdict_alignment = True
        language_audit = True

        if eval_result and eval_result.verdict:
            verdict = eval_result.verdict.fact.object.get("verdict", "")
            if eval_result.score:
                gate = eval_result.score.fact.object.get("threshold_gate", "")
                # Check alignment
                verdict_alignment = (verdict == gate or verdict in ["CLEAR_AND_CLOSE", "ESCALATE"])

        # Chain integrity
        chain_valid = True
        if chain and hasattr(chain, 'validate'):
            validation = chain.validate()
            chain_valid = validation.is_valid

        overall = GateStatus.PASS
        if not chain_valid or not verdict_alignment:
            overall = GateStatus.FAIL

        return GateResult(
            gate_name="Integrity Audit",
            gate_number=4,
            status=overall,
            details={
                "typology_match": typology_match,
                "verdict_alignment": verdict_alignment,
                "language_audit": language_audit,
                "chain_integrity": chain_valid,
            }
        )

    def _render_gate_1(
        self,
        gate: GateResult,
        typology: TypologyClass,
        w: int
    ) -> List[str]:
        """Render Gate 1 section."""
        lines = []
        lines.append("GATE 1: CONTEXTUAL TYPOLOGY")
        lines.append("-" * w)
        lines.append(f"   Typology Class: {typology.value}")
        lines.append(f"   Forbidden Typologies: {'DETECTED' if gate.status == GateStatus.FAIL else 'NONE DETECTED'}")
        lines.append("")
        return lines

    def _render_gate_2(
        self,
        eval_result: Any,
        pack_runtime: Any,
        w: int
    ) -> List[str]:
        """Render Gate 2 section."""
        lines = []
        lines.append("GATE 2: INHERENT RISKS DETECTED")
        lines.append("-" * w)

        if eval_result and eval_result.signals:
            for i, signal in enumerate(eval_result.signals, 1):
                obj = signal.fact.object
                code = obj.get("code", "UNKNOWN")
                severity = obj.get("severity", "MEDIUM")
                name = obj.get("name", code)
                policy_ref = obj.get("policy_ref", "")

                lines.append(f"   {i:02d}. [{severity:8}] {code}")
                if name and name != code:
                    lines.append(f"       {name}")
                if policy_ref:
                    lines.append(f"       Ref: {policy_ref}")
        else:
            lines.append("   (none)")

        lines.append("")
        lines.append("GATE 2: MITIGATING FACTORS (Pause & Pivot)")
        lines.append("-" * w)

        if eval_result and eval_result.mitigations:
            for mit in eval_result.mitigations:
                obj = mit.fact.object
                code = obj.get("code", "UNKNOWN")
                weight = obj.get("weight", "0")
                name = obj.get("name", code)

                lines.append(f"   {code}: {name}")
                # Display evidence anchors if available
                evidence_anchors = obj.get("evidence_anchors", [])
                if evidence_anchors:
                    for anchor in evidence_anchors:
                        field = anchor.get("field", "unknown")
                        value = anchor.get("value", "")
                        source = anchor.get("source", "")
                        # Truncate value if too long
                        if len(value) > 30:
                            value = value[:27] + "..."
                        lines.append(f"      Data: {field}: {value}")
                        if source:
                            lines.append(f"      Source: {source}")
                lines.append(f"      Impact: {weight} Risk Weight applied")
        else:
            lines.append("   (none)")

        lines.append("")
        return lines

    def _render_gate_3(
        self,
        eval_result: Any,
        anchor_grid: EvidenceAnchorGrid,
        w: int
    ) -> List[str]:
        """Render Gate 3 section with evidence anchor grid."""
        lines = []
        lines.append("GATE 3: RESIDUAL RISK CALCULATION")
        lines.append("-" * w)
        lines.append("   EVIDENCE ANCHOR GRID:")
        lines.append("   " + "-" * 60)
        lines.append(f"   {'Offset Type':<25} {'Data Anchor':<20} {'Weight':>10}")
        lines.append("   " + "-" * 60)

        # Inherent risk row
        lines.append(f"   {'Inherent Risk':<25} {'All Signals':<20} {'+' + str(anchor_grid.inherent_weight):>10}")

        # Mitigation rows
        for anchor in anchor_grid.anchors:
            weight_str = str(anchor.weight)
            if anchor.weight < 0:
                weight_str = str(anchor.weight)
            lines.append(f"   {anchor.offset_type:<25} {anchor.data_anchor:<20} {weight_str:>10}")

        lines.append("   " + "-" * 60)
        lines.append(f"   {'RESIDUAL SCORE':<45} {str(anchor_grid.residual_score):>10}")
        lines.append("")

        # Score and gate
        if eval_result and eval_result.score:
            score_obj = eval_result.score.fact.object
            gate = score_obj.get("threshold_gate", "UNKNOWN")
            residual = score_obj.get("residual_score", "0")
            lines.append(f"   Residual Score: {residual}")
            lines.append(f"   Threshold Gate: {gate}")

        lines.append("")
        return lines

    def _render_gate_4(self, gate: GateResult, w: int) -> List[str]:
        """Render Gate 4 section."""
        lines = []
        lines.append("GATE 4: INTEGRITY AUDIT")
        lines.append("-" * w)

        details = gate.details
        status_str = lambda x: "PASS" if x else "FAIL"

        # Handle both old format (flat details) and new format (check_results dict)
        check_results = details.get('check_results', details)

        lines.append(f"   Typology Match:     {status_str(check_results.get('typology_match', True))}")
        lines.append(f"   Verdict Alignment:  {status_str(check_results.get('verdict_alignment', True))}")
        lines.append(f"   Language Audit:     {status_str(check_results.get('language_audit', True))}")
        lines.append(f"   Chain Integrity:    {status_str(check_results.get('chain_integrity', True))}")
        lines.append(f"   Overall Integrity:  {gate.status.value}")

        # Show warnings and failures if present (new GateResult format)
        if hasattr(gate, 'warnings') and gate.warnings:
            for warning in gate.warnings:
                lines.append(f"   WARNING: {warning}")
        if hasattr(gate, 'failures') and gate.failures:
            for failure in gate.failures:
                lines.append(f"   FAILURE: {failure}")

        lines.append("")
        return lines

    def _render_decision(self, eval_result: Any, w: int) -> List[str]:
        """Render decision section."""
        lines = []
        lines.append("=" * w)
        lines.append("DECISION")
        lines.append("=" * w)

        if eval_result and eval_result.verdict:
            obj = eval_result.verdict.fact.object
            verdict = obj.get("verdict", "UNKNOWN")
            auto_archive = obj.get("auto_archive_permitted", False)

            # Determine tier
            tier = 1
            if verdict in ["SENIOR_REVIEW", "COMPLIANCE_ESCALATION"]:
                tier = 2
            elif verdict in ["STR_CONSIDERATION"]:
                tier = 3

            # Escalate to
            escalate_to = "NONE"
            if tier == 2:
                escalate_to = "SENIOR_ANALYST"
            elif tier == 3:
                escalate_to = "COMPLIANCE_OFFICER"

            lines.append(f"Action:         {verdict}")
            lines.append(f"Auto-Archive:   {'YES' if auto_archive else 'NO'}")
            lines.append(f"Tier:           {tier}")
            lines.append(f"Escalate To:    {escalate_to}")
        else:
            lines.append("Action:         PENDING")

        lines.append("")
        return lines

    def _generate_required_actions(
        self,
        eval_result: Any,
        pack_runtime: Any,
        gate_results: Optional[List[GateResult]] = None
    ) -> List[GeneratedAction]:
        """Generate required actions using ActionGenerator."""
        # Extract data for action generation
        verdict = None
        signal_codes = []
        residual_score = None
        failed_gates = []

        if eval_result:
            if eval_result.verdict:
                verdict = eval_result.verdict.fact.object.get("verdict", "")

            if eval_result.signals:
                signal_codes = [
                    s.fact.object.get("code", "")
                    for s in eval_result.signals
                ]

            if eval_result.score:
                score_str = eval_result.score.fact.object.get("residual_score", "0")
                residual_score = Decimal(str(score_str))

        if gate_results:
            failed_gates = [
                g.gate_number for g in gate_results
                if g.status == GateStatus.FAIL
            ]

        return self.action_generator.generate(
            verdict=verdict,
            signal_codes=signal_codes,
            residual_score=residual_score,
            failed_gates=failed_gates,
        )

    def _render_required_actions(
        self,
        actions: List[GeneratedAction],
        w: int
    ) -> List[str]:
        """Render required actions section."""
        lines = []
        lines.append("=" * w)
        lines.append("REQUIRED ACTIONS")
        lines.append("=" * w)

        if actions:
            for i, action in enumerate(actions, 1):
                # Add priority marker for high/critical
                priority_marker = ""
                if action.priority == ActionPriority.CRITICAL:
                    priority_marker = " [CRITICAL]"
                elif action.priority == ActionPriority.HIGH:
                    priority_marker = " [HIGH]"

                lines.append(f"  {i}. {action.description}{priority_marker}")

                if action.escalate_to:
                    lines.append(f"     Escalate to: {action.escalate_to}")

            lines.append("")
            # Use minimum SLA (most urgent)
            min_sla = min(a.sla_hours for a in actions)
            lines.append(f"SLA: {min_sla} hours")
        else:
            lines.append("  (none)")

        lines.append("")
        return lines

    def _compute_feedback_scores(
        self,
        eval_result: Any,
        citation_registry: Optional[CitationRegistry],
        docs_on_file: int,
        docs_required: int,
        gate_results: Optional[List[GateResult]] = None
    ) -> FeedbackScores:
        """Compute feedback scores with confidence calculation."""
        signal_codes = []
        if eval_result and eval_result.signals:
            signal_codes = [s.fact.object.get("code", "") for s in eval_result.signals]

        citation_quality = CitationQuality()
        if citation_registry:
            citation_quality = citation_registry.compute_citation_quality(signal_codes)

        signals_fired = len(signal_codes)
        total_signals = 22  # From pack

        # Count evidence anchored from mitigations
        evidence_anchored = 0
        total_evidence = 0
        if eval_result and eval_result.mitigations:
            total_evidence = len(eval_result.mitigations)
            for mit in eval_result.mitigations:
                obj = mit.fact.object
                if obj.get("evidence_anchors"):
                    evidence_anchored += 1

        auto_archive = False
        if eval_result and eval_result.verdict:
            auto_archive = eval_result.verdict.fact.object.get("auto_archive_permitted", False)

        return FeedbackScores.compute(
            citation_quality=citation_quality,
            signals_fired=signals_fired,
            total_signals=total_signals,
            evidence_anchored=evidence_anchored,
            total_evidence=total_evidence,
            auto_archive=auto_archive,
            docs_on_file=docs_on_file,
            docs_required=docs_required,
            gate_results=gate_results,
        )

    def _render_feedback_scores(self, scores: FeedbackScores, w: int) -> List[str]:
        """Render feedback scores section."""
        lines = []
        lines.append("=" * w)
        lines.append("FEEDBACK SCORES")
        lines.append("=" * w)

        lines.append(f"  {'Score':<30} {'Value':>8} {'Assessment':<26}")
        lines.append(f"  {'-'*30} {'-'*8} {'-'*26}")

        lines.append(f"  {'confidence':<30} {str(scores.confidence):>8} Navigation confidence")
        lines.append(f"  {'citation_quality':<30} {str(scores.citation_quality):>8} Signals with citations")
        lines.append(f"  {'signal_coverage':<30} {str(scores.signal_coverage):>8} Signals evaluated")
        lines.append(f"  {'evidence_completeness':<30} {str(scores.evidence_completeness):>8} Evidence anchored")
        lines.append(f"  {'decision_clarity':<30} {str(scores.decision_clarity):>8} {'Auto-archive' if scores.decision_clarity == Decimal('1.00') else 'Needs review'}")
        lines.append(f"  {'documentation_completeness':<30} {str(scores.documentation_completeness):>8} Docs on file")
        lines.append("")
        return lines

    def _render_audit_trail(
        self,
        case_bundle: Any,
        pack_runtime: Any,
        report_timestamp: str,
        w: int
    ) -> List[str]:
        """Render audit trail section."""
        lines = []
        lines.append("=" * w)
        lines.append("AUDIT TRAIL")
        lines.append("=" * w)

        created_at = ""
        if hasattr(case_bundle, 'meta') and hasattr(case_bundle.meta, 'created_at'):
            created = case_bundle.meta.created_at
            if hasattr(created, 'isoformat'):
                created_at = created.isoformat()
            else:
                created_at = str(created)

        lines.append(f"Case Created:     {created_at}")
        lines.append(f"Report Generated: {report_timestamp}")
        lines.append(f"Engine Version:   1.0.0")
        lines.append(f"Pack Version:     {pack_runtime.pack_version if hasattr(pack_runtime, 'pack_version') else '1.0.0'}")
        lines.append(f"Pack Hash:        {pack_runtime.pack_hash[:32] if hasattr(pack_runtime, 'pack_hash') else 'N/A'}...")
        lines.append("")
        return lines

    def _render_case_integrity(
        self,
        chain: Any,
        pack_runtime: Any,
        w: int
    ) -> List[str]:
        """Render case integrity section."""
        lines = []
        lines.append("=" * w)
        lines.append("CASE INTEGRITY")
        lines.append("=" * w)

        # Chain stats
        if chain:
            lines.append(f"Graph ID:         {chain.graph_id if hasattr(chain, 'graph_id') else 'N/A'}")
            lines.append(f"Chain Length:     {len(chain) if hasattr(chain, '__len__') else 0} cells")

            if hasattr(chain, 'validate'):
                validation = chain.validate()
                status = "VALID" if validation.is_valid else "INVALID"
                lines.append(f"Chain Status:     {status}")

        lines.append("")
        return lines


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def render_bank_report(
    case_bundle: Any,
    eval_result: Any,
    pack_runtime: Any,
    chain: Any,
    citation_registry: Optional[CitationRegistry] = None,
    config: Optional[ReportConfig] = None,
) -> bytes:
    """
    Convenience function to render a bank-grade report.

    Returns UTF-8 encoded report bytes.
    """
    renderer = BankReportRenderer(config=config)
    return renderer.render(
        case_bundle=case_bundle,
        eval_result=eval_result,
        pack_runtime=pack_runtime,
        chain=chain,
        citation_registry=citation_registry,
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Exceptions
    'BankReportError',
    'RenderError',
    # Enums
    'TypologyClass',
    'GateStatus',
    # Config
    'ReportConfig',
    # Evidence anchoring
    'EvidenceAnchor',
    'EvidenceAnchorGrid',
    # Feedback
    'FeedbackScores',
    # Actions
    'RequiredAction',
    # Gates
    'GateResult',
    # Renderer
    'BankReportRenderer',
    'render_bank_report',
]
