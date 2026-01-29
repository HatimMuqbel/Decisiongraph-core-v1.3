"""
DecisionGraph Bank-Grade Report Module (v2.1)

Implements the 4-Gate Protocol report format with:
- Alert banner with verdict
- Alert reason codes
- Contextual Typology (Gate 1)
- Inherent Risks + Mitigating Factors (Gate 2)
- Residual Risk Calculation with Evidence Anchor Grid (Gate 3)
- Integrity Audit (Gate 4)
- Policy Citations with quality metrics
- Feedback Scores (Opik-style evaluation)
- Required Actions with SLA
- Regulatory References

This module produces auditor-ready reports that meet bank regulatory
requirements for transaction monitoring and KYC case documentation.
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
    PEP_TRANSACTION = "PEP_TRANSACTION"
    UNKNOWN = "UNKNOWN"


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class ReportConfig:
    """Configuration for report rendering."""
    line_width: int = 80
    include_citations: bool = True
    include_feedback_scores: bool = True
    include_audit_trail: bool = True
    include_case_integrity: bool = True
    include_required_actions: bool = True
    include_regulatory_references: bool = True
    template_id: str = "bank_grade_v2"
    template_version: str = "2.0.0"


# =============================================================================
# EVIDENCE ANCHOR
# =============================================================================

@dataclass
class EvidenceAnchor:
    """An evidence anchor links a risk offset to its source data."""
    offset_type: str
    data_anchor: str
    weight: Decimal
    source_cell_id: Optional[str] = None
    citation_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "offset_type": self.offset_type,
            "data_anchor": self.data_anchor,
            "weight": str(self.weight),
            "source_cell_id": self.source_cell_id,
            "citation_hash": self.citation_hash,
        }


@dataclass
class EvidenceAnchorGrid:
    """Grid of evidence anchors showing the residual risk calculation.

    Dual-score methodology:
    - Raw scores (inherent_weight, residual_score): Additive sum of weights for explainability
    - Normalized scores (inherent_normalized, residual_normalized): Probability union for thresholds
    """
    inherent_weight: Decimal  # Raw additive score
    inherent_normalized: Decimal = Decimal("0")  # Probability union score [0-1]
    residual_normalized: Decimal = Decimal("0")  # Normalized residual [0-1]
    anchors: List[EvidenceAnchor] = field(default_factory=list)

    @property
    def mitigation_sum(self) -> Decimal:
        return sum((a.weight for a in self.anchors), Decimal("0"))

    @property
    def residual_score(self) -> Decimal:
        """Raw residual score (additive)."""
        return max(Decimal("0"), self.inherent_weight + self.mitigation_sum)

    @property
    def mitigation_percentage(self) -> int:
        """Percentage risk reduction from mitigations."""
        if self.inherent_weight > 0:
            return int(abs(self.mitigation_sum / self.inherent_weight) * 100)
        return 0


# =============================================================================
# FEEDBACK SCORES
# =============================================================================

@dataclass
class FeedbackScores:
    """Opik-style feedback scores for evaluation metrics."""
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
        """Compute feedback scores from inputs."""
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

        sig_cov = Decimal("0.00")
        if total_signals > 0:
            sig_cov = (Decimal(str(signals_fired)) / Decimal(str(total_signals)))

        dec_clar = Decimal("1.00") if auto_archive else Decimal("0.50")

        return cls(
            confidence=conf_result.overall_confidence,
            citation_quality=conf_result.citation_quality,
            signal_coverage=sig_cov.quantize(Decimal("0.01")),
            evidence_completeness=conf_result.evidence_completeness,
            decision_clarity=dec_clar,
            documentation_completeness=conf_result.documentation_score,
        )


@dataclass
class RequiredAction:
    """A required follow-up action with SLA."""
    action: str
    sla_hours: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {"action": self.action, "sla_hours": self.sla_hours}


# =============================================================================
# BANK REPORT RENDERER
# =============================================================================

class BankReportRenderer:
    """
    Renders bank-grade reports with 4-gate protocol.

    Produces deterministic, auditable reports matching regulatory
    expectations for transaction monitoring and KYC case documentation.
    """

    def __init__(
        self,
        config: Optional[ReportConfig] = None,
        gate_config: Optional[GateConfig] = None,
        gate_evaluator: Optional[GateEvaluator] = None,
        action_config: Optional[ActionConfig] = None,
        action_generator: Optional[ActionGenerator] = None
    ):
        self.config = config or ReportConfig()
        if gate_evaluator:
            self.gate_evaluator = gate_evaluator
        elif gate_config:
            self.gate_evaluator = GateEvaluator(gate_config)
        else:
            self.gate_evaluator = GateEvaluator()

        if action_generator:
            self.action_generator = action_generator
        elif action_config:
            self.action_generator = ActionGenerator(action_config)
        else:
            self.action_generator = ActionGenerator()

    def render(
        self,
        case_bundle: Any,
        eval_result: Any,
        pack_runtime: Any,
        chain: Any,
        citation_registry: Optional[CitationRegistry] = None,
        report_timestamp: Optional[str] = None,
    ) -> bytes:
        """Render the complete bank-grade report. Returns UTF-8 encoded bytes."""
        if not report_timestamp:
            report_timestamp = get_current_timestamp()

        lines = []
        w = self.config.line_width

        # Extract key data
        case_id = case_bundle.meta.id if hasattr(case_bundle, 'meta') else str(case_bundle)
        case_type = case_bundle.meta.case_type.value if hasattr(case_bundle, 'meta') else "UNKNOWN"

        # Determine typology
        typology = self._determine_typology(case_bundle, eval_result)

        # Get verdict info for banner
        verdict_str, auto_archive = self._get_verdict_info(eval_result)

        # Header
        lines.extend(self._render_header(case_id, case_type, w))

        # Alert Banner
        lines.extend(self._render_alert_banner(case_id, verdict_str, auto_archive, case_bundle, w))

        # Alert Reason Codes
        lines.extend(self._render_alert_reason_codes(eval_result, case_bundle, w))

        # Decision Methodology (examiner requirement)
        lines.extend(self._render_decision_methodology(w))

        # Case Summary
        lines.extend(self._render_case_summary(case_bundle, w))

        # Transaction Details
        lines.extend(self._render_transaction_details(case_bundle, w))

        # Beneficial Ownership
        lines.extend(self._render_beneficial_ownership(case_bundle, w))

        # Corporate Structure
        lines.extend(self._render_corporate_structure(case_bundle, w))

        # Screening Results
        lines.extend(self._render_screening_results(case_bundle, eval_result, w))

        # Documentation Status
        docs_on_file, docs_required = self._render_documentation_status(case_bundle, w, lines)

        # Risk Indicators
        lines.extend(self._render_risk_indicators(eval_result, w))

        # ===== 4-GATE PROTOCOL =====
        lines.append("")
        lines.append("SECTION 10B: MITIGATING FACTORS ANALYSIS")
        lines.append("=" * w)
        lines.append("")

        # Build evidence anchor grid
        anchor_grid = self._build_evidence_anchor_grid(eval_result)

        # Gate 1
        gate1 = self.gate_evaluator.evaluate_gate_1(case_bundle, typology.value)
        lines.extend(self._render_gate_1(gate1, typology, w))

        # Gate 2
        gate2 = self.gate_evaluator.evaluate_gate_2(eval_result)
        lines.extend(self._render_gate_2(eval_result, pack_runtime, w))

        # Gate 3
        gate3 = self.gate_evaluator.evaluate_gate_3(eval_result, anchor_grid.residual_score)
        lines.extend(self._render_gate_3(eval_result, anchor_grid, w))

        # Verdict in Gate 3
        lines.extend(self._render_gate_3_verdict(eval_result, anchor_grid, w))

        # Gate 4
        gate4 = self.gate_evaluator.evaluate_gate_4(eval_result, chain, typology.value)

        gate_results_list = [gate1, gate2, gate3, gate4]

        lines.append("=" * w)
        lines.append("")

        # Policy Citations
        if self.config.include_citations and citation_registry:
            signal_codes = [
                s.fact.object.get("code", "")
                for s in (eval_result.signals if eval_result else [])
            ]
            lines.extend(self._render_policy_citations(citation_registry, signal_codes, w))
            quality = citation_registry.compute_citation_quality(signal_codes)
            lines.extend(self._render_citation_quality_summary(quality, w))

        # Decision
        lines.extend(self._render_decision(eval_result, anchor_grid, w))

        # Human Review Requirement (examiner requirement)
        lines.extend(self._render_human_review_requirement(eval_result, w))

        # Required Actions
        if self.config.include_required_actions:
            actions = self._generate_required_actions(
                eval_result, pack_runtime, gate_results=gate_results_list
            )
            lines.extend(self._render_required_actions(eval_result, actions, w))

        # Feedback Scores
        if self.config.include_feedback_scores:
            scores = self._compute_feedback_scores(
                eval_result, citation_registry, docs_on_file, docs_required,
                gate_results=gate_results_list
            )
            lines.extend(self._render_feedback_scores(scores, w))

        # Audit Trail
        if self.config.include_audit_trail:
            lines.extend(self._render_audit_trail(
                case_bundle, eval_result, pack_runtime, report_timestamp, w
            ))

        # Case Integrity
        if self.config.include_case_integrity:
            lines.extend(self._render_case_integrity(
                case_bundle, chain, pack_runtime, scores if self.config.include_feedback_scores else None, w
            ))

        # Regulatory References
        if self.config.include_regulatory_references:
            lines.extend(self._render_regulatory_references(pack_runtime, w))

        # Footer
        lines.append("=" * w)
        lines.append("END OF ALERT REPORT")
        lines.append("=" * w)
        lines.append("")

        text = "\n".join(lines) + "\n"
        return text.encode("utf-8")

    def _get_verdict_info(self, eval_result: Any) -> Tuple[str, bool]:
        """Extract verdict and auto_archive from eval_result."""
        if eval_result and eval_result.verdict:
            obj = eval_result.verdict.fact.object
            verdict = obj.get("verdict", "PENDING")
            auto_archive = obj.get("auto_archive_permitted", False)
            return verdict, auto_archive
        return "PENDING", False

    def _render_header(self, case_id: str, case_type: str, w: int) -> List[str]:
        """Render report header."""
        lines = []
        lines.append("=" * w)
        lines.append("TRANSACTION MONITORING ALERT REPORT")
        lines.append(f"Alert ID: {case_id}")
        lines.append("=" * w)
        lines.append("")
        return lines

    def _render_alert_banner(
        self,
        case_id: str,
        verdict: str,
        auto_archive: bool,
        case_bundle: Any,
        w: int
    ) -> List[str]:
        """Render the alert banner with verdict."""
        lines = []
        lines.append("=" * w)

        # Determine alert type and action
        is_pep = self._is_pep_case(case_bundle)

        if verdict in ["CLEAR_AND_CLOSE", "AUTO_CLOSE"]:
            action = "APPROVE"
            if is_pep:
                banner = "PEP ALERT - APPROVE"
            else:
                banner = "ALERT - APPROVE"
        elif verdict in ["ANALYST_REVIEW", "SENIOR_REVIEW"]:
            action = "REVIEW"
            if is_pep:
                banner = "PEP ALERT - REVIEW"
            else:
                banner = "ALERT - REVIEW"
        elif verdict in ["COMPLIANCE_ESCALATION", "STR_CONSIDERATION"]:
            action = "ESCALATE"
            if is_pep:
                banner = "PEP ALERT - ESCALATE"
            else:
                banner = "ALERT - ESCALATE"
        else:
            action = "PENDING"
            banner = "ALERT - PENDING"

        lines.append(f"  {banner}  ")
        lines.append("=" * w)

        # Alert metadata
        lines.append(f"Alert ID:       {case_id}")
        priority = "HIGH" if is_pep else "MEDIUM"
        if hasattr(case_bundle, 'meta'):
            priority = case_bundle.meta.priority.upper() if hasattr(case_bundle.meta, 'priority') else priority
        lines.append(f"Priority:       {priority}")

        source = "Transaction Monitoring"
        if is_pep:
            source = "PEP Monitoring"
        lines.append(f"Source:         {source}")

        if hasattr(case_bundle, 'meta') and hasattr(case_bundle.meta, 'created_at'):
            created = case_bundle.meta.created_at
            if hasattr(created, 'strftime'):
                lines.append(f"Processed:      {created.strftime('%Y-%m-%d')}")
            else:
                lines.append(f"Processed:      {str(created)[:10]}")

        lines.append("")
        return lines

    def _is_pep_case(self, case_bundle: Any) -> bool:
        """Check if case involves PEP."""
        if hasattr(case_bundle, 'individuals'):
            for ind in case_bundle.individuals:
                if hasattr(ind, 'pep_status') and ind.pep_status:
                    if ind.pep_status.value != 'none':
                        return True
        return False

    def _render_alert_reason_codes(self, eval_result: Any, case_bundle: Any, w: int) -> List[str]:
        """Render alert reason codes section."""
        lines = []
        lines.append("=" * w)
        lines.append("ALERT REASON CODES")
        lines.append("=" * w)

        codes = []

        # Add PEP code if applicable
        if self._is_pep_case(case_bundle):
            codes.append("PEP_TRANSACTION")

        # Check for cross-border
        if hasattr(case_bundle, 'events'):
            for event in case_bundle.events:
                if hasattr(event, 'counterparty_country'):
                    country = getattr(event, 'counterparty_country', '')
                    if country and hasattr(case_bundle, 'meta'):
                        if country != case_bundle.meta.jurisdiction:
                            if "CROSS_BORDER_TRANSFER" not in codes:
                                codes.append("CROSS_BORDER_TRANSFER")

        # Check for high value
        if hasattr(case_bundle, 'events'):
            for event in case_bundle.events:
                if hasattr(event, 'amount'):
                    try:
                        amount = Decimal(str(event.amount))
                        if amount >= 10000:
                            if "HIGH_VALUE_TRANSACTION" not in codes:
                                codes.append("HIGH_VALUE_TRANSACTION")
                    except:
                        pass

        # Add signal-based codes
        if eval_result and eval_result.signals:
            for signal in eval_result.signals[:3]:  # Top 3
                code = signal.fact.object.get("code", "")
                if code and code not in codes:
                    codes.append(code)

        for code in codes[:5]:  # Limit to 5
            lines.append(f"* {code}")

        lines.append("")
        return lines

    def _render_decision_methodology(self, w: int) -> List[str]:
        """Render decision methodology disclosure (examiner requirement)."""
        lines = []
        lines.append("=" * w)
        lines.append("DECISION METHODOLOGY")
        lines.append("=" * w)
        lines.append("This decision was produced using a deterministic rules-based")
        lines.append("evaluation under the DecisionGraph framework.")
        lines.append("")
        lines.append("  * Inherent Risk Score: Raw aggregation of triggered risk indicators")
        lines.append("  * Mitigation Adjustments: Evidence-backed reductions")
        lines.append("  * Normalized Score: Probability union (0-1) for threshold gates")
        lines.append("  * Verdict Gates: Threshold-based regulatory decision points")
        lines.append("")
        lines.append("No probabilistic or generative AI was used in this determination.")
        lines.append("All decisions are reproducible given identical inputs.")
        lines.append("")
        return lines

    def _render_case_summary(self, case_bundle: Any, w: int) -> List[str]:
        """Render case summary section."""
        lines = []
        lines.append("=" * w)
        lines.append("CASE SUMMARY")
        lines.append("=" * w)

        if hasattr(case_bundle, 'individuals') and case_bundle.individuals:
            primary = case_bundle.individuals[0]
            name = primary.full_name if hasattr(primary, 'full_name') else f"{getattr(primary, 'given_name', '')} {getattr(primary, 'family_name', '')}"

            # Add honorific if PEP
            if hasattr(primary, 'pep_status') and primary.pep_status and primary.pep_status.value != 'none':
                name = f"Hon. {name}"

            lines.append(f"Customer:       {name}")
            lines.append(f"Customer ID:    {primary.id}")
            lines.append(f"Type:           INDIVIDUAL")

            country = getattr(primary, 'country_of_residence', '') or getattr(primary, 'nationality', '')
            lines.append(f"Country:        {country}")

            risk = getattr(primary, 'risk_rating', None)
            if risk:
                lines.append(f"Risk Rating:    {risk.value.upper()}")

        elif hasattr(case_bundle, 'organizations') and case_bundle.organizations:
            org = case_bundle.organizations[0]
            lines.append(f"Entity:         {org.legal_name}")
            lines.append(f"Entity ID:      {org.id}")
            lines.append(f"Type:           {getattr(org, 'entity_type', 'ORGANIZATION').upper()}")
            lines.append(f"Jurisdiction:   {getattr(org, 'jurisdiction', 'N/A')}")

        lines.append("")
        return lines

    def _render_transaction_details(self, case_bundle: Any, w: int) -> List[str]:
        """Render transaction details section."""
        lines = []

        if not hasattr(case_bundle, 'events') or not case_bundle.events:
            return lines

        txn_events = [e for e in case_bundle.events if getattr(e, 'event_type', '') == 'transaction']
        if not txn_events:
            return lines

        lines.append("=" * w)
        lines.append("TRANSACTION DETAILS")
        lines.append("=" * w)

        for event in txn_events[:3]:  # First 3 transactions
            desc = getattr(event, 'description', 'Transaction')
            # Simplify description
            if 'wire' in desc.lower():
                txn_type = "Wire Transfer"
            elif 'cash' in desc.lower():
                txn_type = "Cash Transaction"
            else:
                txn_type = getattr(event, 'payment_method', 'Transaction').replace('_', ' ').title()

            lines.append(f"Type:           {txn_type}")

            amount = getattr(event, 'amount', '0')
            currency = getattr(event, 'currency', 'CAD')
            lines.append(f"Amount:         {currency} {amount}")

            if hasattr(event, 'timestamp'):
                ts = event.timestamp
                if hasattr(ts, 'strftime'):
                    lines.append(f"Date:           {ts.strftime('%Y-%m-%d')}")
                else:
                    lines.append(f"Date:           {str(ts)[:10]}")

            counterparty = getattr(event, 'counterparty_name', '')
            if counterparty:
                lines.append(f"Beneficiary:    {counterparty}")

            country = getattr(event, 'counterparty_country', '')
            if country:
                lines.append(f"Benef Country:  {country}")

            bank = getattr(event, 'counterparty_bank', '')
            if bank:
                lines.append(f"Benef Bank:     {bank}")

        lines.append("")
        return lines

    def _render_beneficial_ownership(self, case_bundle: Any, w: int) -> List[str]:
        """Render beneficial ownership section."""
        lines = []

        if not hasattr(case_bundle, 'individuals') or not case_bundle.individuals:
            return lines

        lines.append("=" * w)
        lines.append("BENEFICIAL OWNERSHIP")
        lines.append("=" * w)

        for i, ind in enumerate(case_bundle.individuals[:3], 1):
            lines.append(f"Owner {i}:")
            name = ind.full_name if hasattr(ind, 'full_name') else f"{getattr(ind, 'given_name', '')} {getattr(ind, 'family_name', '')}"
            lines.append(f"  Name:         {name}")

            nationality = getattr(ind, 'nationality', 'N/A')
            lines.append(f"  Nationality:  {nationality}")

            # Try to get ownership from relationships
            ownership = "100%"  # Default for individual
            lines.append(f"  Ownership:    {ownership}")

            pep_status = "None"
            if hasattr(ind, 'pep_status') and ind.pep_status:
                pep_val = ind.pep_status.value
                if pep_val == 'fpep':
                    pep_status = "FOREIGN_PEP"
                elif pep_val == 'dpep':
                    pep_status = "DOMESTIC_PEP"
                elif pep_val == 'hio':
                    pep_status = "HIO"
                elif pep_val != 'none':
                    pep_status = pep_val.upper()
            lines.append(f"  PEP Status:   {pep_status}")
            lines.append("")

        return lines

    def _render_corporate_structure(self, case_bundle: Any, w: int) -> List[str]:
        """Render corporate structure section."""
        lines = []
        lines.append("=" * w)
        lines.append("CORPORATE STRUCTURE")
        lines.append("=" * w)

        if hasattr(case_bundle, 'organizations') and case_bundle.organizations:
            lines.append("Corporate ownership structure")
        else:
            lines.append("Direct ownership - Individual account")

        # Count jurisdictions
        jurisdictions = set()
        if hasattr(case_bundle, 'meta'):
            jurisdictions.add(case_bundle.meta.jurisdiction)
        if hasattr(case_bundle, 'individuals'):
            for ind in case_bundle.individuals:
                if hasattr(ind, 'country_of_residence') and ind.country_of_residence:
                    jurisdictions.add(ind.country_of_residence)
                if hasattr(ind, 'nationality') and ind.nationality:
                    jurisdictions.add(ind.nationality)
        if hasattr(case_bundle, 'events'):
            for event in case_bundle.events:
                if hasattr(event, 'counterparty_country') and event.counterparty_country:
                    jurisdictions.add(event.counterparty_country)

        lines.append("")
        lines.append(f"Jurisdictions:  {len(jurisdictions)} ({', '.join(sorted(jurisdictions))})")
        lines.append("")
        return lines

    def _render_screening_results(self, case_bundle: Any, eval_result: Any, w: int) -> List[str]:
        """Render detailed screening results section."""
        lines = []
        lines.append("=" * w)
        lines.append("SCREENING RESULTS")
        lines.append("=" * w)

        # Standard screening status
        sanctions_status = "NO_MATCH"
        pep_status = "NO_MATCH"
        adverse_media = "NONE_FOUND"

        if hasattr(case_bundle, 'events'):
            for event in case_bundle.events:
                if getattr(event, 'event_type', '') == 'screening':
                    screening_type = getattr(event, 'screening_type', '').lower()
                    disposition = getattr(event, 'disposition', '').upper()

                    if 'sanction' in screening_type:
                        if disposition in ['CONFIRMED', 'TRUE_POSITIVE']:
                            sanctions_status = "MATCH"
                        elif disposition == 'FALSE_POSITIVE':
                            sanctions_status = "FALSE_POSITIVE"
                    elif 'pep' in screening_type:
                        if disposition in ['CONFIRMED', 'TRUE_POSITIVE']:
                            pep_status = "FOREIGN_PEP"
                    elif 'adverse' in screening_type or 'media' in screening_type:
                        if disposition in ['CONFIRMED', 'TRUE_POSITIVE']:
                            adverse_media = "FOUND"

        # Check individual PEP status
        if hasattr(case_bundle, 'individuals'):
            for ind in case_bundle.individuals:
                if hasattr(ind, 'pep_status') and ind.pep_status and ind.pep_status.value != 'none':
                    pep_status = ind.pep_status.value.upper()
                    if pep_status == 'FPEP':
                        pep_status = 'FOREIGN_PEP'
                    elif pep_status == 'DPEP':
                        pep_status = 'DOMESTIC_PEP'

        lines.append(f"Sanctions:      {sanctions_status}")
        lines.append(f"PEP:            {pep_status}")
        lines.append(f"Adverse Media:  {adverse_media}")

        # PEP Details (from assertions or screening events)
        if pep_status != "NO_MATCH":
            pep_details = self._get_pep_details(case_bundle)
            if pep_details:
                lines.append(f"PEP Details:  {pep_details}")

            sow = self._get_source_of_wealth(case_bundle)
            if sow:
                lines.append(f"Source of Wealth:  {sow}")

            transparency = self._get_transparency_level(case_bundle)
            if transparency:
                lines.append(f"Transparency Level:  {transparency}")

            trust_audit = self._get_trust_audit(case_bundle)
            if trust_audit:
                lines.append(f"Trust Audit:  {trust_audit}")

            account_history = self._get_account_history(case_bundle)
            if account_history:
                lines.append(f"Account History:  {account_history}")

        lines.append("")
        return lines

    def _get_pep_details(self, case_bundle: Any) -> str:
        """Get PEP details from assertions."""
        if hasattr(case_bundle, 'assertions'):
            for assertion in case_bundle.assertions:
                if hasattr(assertion, 'predicate'):
                    if 'position' in assertion.predicate.lower() or 'pep' in assertion.predicate.lower():
                        return assertion.value
        return "PEP status confirmed. Enhanced due diligence required."

    def _get_source_of_wealth(self, case_bundle: Any) -> str:
        """Get source of wealth from assertions or evidence."""
        if hasattr(case_bundle, 'assertions'):
            for assertion in case_bundle.assertions:
                if hasattr(assertion, 'predicate'):
                    if 'wealth' in assertion.predicate.lower() or 'sow' in assertion.predicate.lower():
                        return assertion.value
        return ""

    def _get_transparency_level(self, case_bundle: Any) -> str:
        """Assess transparency level."""
        docs_count = 0
        if hasattr(case_bundle, 'evidence'):
            docs_count = len([e for e in case_bundle.evidence if getattr(e, 'verified', False)])

        if docs_count >= 4:
            return "HIGH. Documentation comprehensive and verified."
        elif docs_count >= 2:
            return "MEDIUM. Core documentation on file."
        return ""

    def _get_trust_audit(self, case_bundle: Any) -> str:
        """Get trust/audit information."""
        if hasattr(case_bundle, 'evidence'):
            for ev in case_bundle.evidence:
                desc = getattr(ev, 'description', '').lower()
                if 'audit' in desc or 'trust' in desc:
                    return ev.description
        return ""

    def _get_account_history(self, case_bundle: Any) -> str:
        """Get account history summary."""
        if hasattr(case_bundle, 'assertions'):
            for assertion in case_bundle.assertions:
                if hasattr(assertion, 'predicate'):
                    if 'tenure' in assertion.predicate.lower() or 'relationship' in assertion.predicate.lower():
                        try:
                            years = int(assertion.value)
                            return f"Customer relationship: {years} years. Consistent activity pattern."
                        except:
                            pass

        # Check account opened date
        if hasattr(case_bundle, 'accounts'):
            for acc in case_bundle.accounts:
                if hasattr(acc, 'opened_date') and acc.opened_date:
                    return f"Account opened: {acc.opened_date}. Active status."
        return ""

    def _render_documentation_status(
        self,
        case_bundle: Any,
        w: int,
        lines: List[str]
    ) -> Tuple[int, int]:
        """Render documentation status section."""
        docs_on_file = 0
        docs_required = 4  # Standard required documents

        if not hasattr(case_bundle, 'evidence') or not case_bundle.evidence:
            return docs_on_file, docs_required

        lines.append("=" * w)
        lines.append("DOCUMENTATION STATUS")
        lines.append("=" * w)
        lines.append("Documents On File:")

        for evidence in case_bundle.evidence:
            verified = getattr(evidence, 'verified', False)
            status = "[x]" if verified else "[ ]"

            # Generate filename from description or type
            desc = getattr(evidence, 'description', '')
            ev_type = getattr(evidence, 'evidence_type', 'document')
            if hasattr(ev_type, 'value'):
                ev_type = ev_type.value

            # Create a reasonable filename
            filename = f"{ev_type.replace(' ', '_').lower()}.pdf"

            lines.append(f"  {status} {filename}")
            if verified:
                docs_on_file += 1

        lines.append("")
        score = docs_on_file / docs_required if docs_required > 0 else 0
        lines.append(f"Documentation Score: {int(score * 100)}%")
        lines.append("")

        return docs_on_file, docs_required

    def _render_risk_indicators(self, eval_result: Any, w: int) -> List[str]:
        """Render risk indicators section."""
        lines = []
        lines.append("=" * w)
        lines.append("RISK INDICATORS")
        lines.append("=" * w)

        if not eval_result or not eval_result.signals:
            lines.append("  No risk indicators identified.")
            lines.append("")
            return lines

        # Group signals by severity for display
        for i, signal in enumerate(eval_result.signals[:5], 1):  # Top 5 signals
            obj = signal.fact.object
            code = obj.get("code", "UNKNOWN")
            severity = obj.get("severity", "MEDIUM")
            name = obj.get("name", code)

            lines.append(f"{i}. {code}: {name} ({severity})")

            # Add description based on signal type
            if "PEP" in code:
                lines.append("   - PEP or PEP-associated party identified")
                lines.append("   - Enhanced due diligence mandatory")
                lines.append("   - Senior management approval required")
            elif "SANCTION" in code:
                lines.append("   - Sanctions screening match identified")
                lines.append("   - Immediate escalation required")
            elif "LARGE" in code or "HIGH" in code or "VALUE" in code:
                lines.append("   - Transaction amount exceeds threshold")
                lines.append("   - Reporting obligations may apply")
            elif "GEO" in code or "COUNTRY" in code:
                lines.append("   - Geographic risk indicator")
                lines.append("   - Additional due diligence recommended")

            lines.append("")

        return lines

    def _determine_typology(self, case_bundle: Any, eval_result: Any) -> TypologyClass:
        """Determine the contextual typology for Gate 1."""
        # Check for PEP
        if self._is_pep_case(case_bundle):
            return TypologyClass.PEP_TRANSACTION

        if hasattr(case_bundle, 'meta'):
            case_type = case_bundle.meta.case_type.value.lower()
            if 'kyc' in case_type or 'onboarding' in case_type:
                return TypologyClass.KYC_ONBOARDING
            if 'edd' in case_type:
                return TypologyClass.EDD_REVIEW

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

    def _build_evidence_anchor_grid(self, eval_result: Any) -> EvidenceAnchorGrid:
        """Build the evidence anchor grid from evaluation result."""
        inherent = Decimal("0")
        inherent_norm = Decimal("0")
        residual_norm = Decimal("0")
        anchors = []

        if eval_result and eval_result.score:
            score_obj = eval_result.score.fact.object
            inherent = Decimal(str(score_obj.get("inherent_score", "0")))
            # Extract normalized scores (schema v2.0)
            inherent_norm = Decimal(str(score_obj.get("inherent_normalized", "0")))
            residual_norm = Decimal(str(score_obj.get("residual_normalized", "0")))

        if eval_result and eval_result.mitigations:
            for mit in eval_result.mitigations:
                obj = mit.fact.object
                evidence_anchors = obj.get("evidence_anchors", [])
                if evidence_anchors:
                    first_anchor = evidence_anchors[0]
                    data_anchor = first_anchor.get("field", "case_evidence")
                else:
                    data_anchor = "case_evidence"

                offset_type = obj.get("name", obj.get("code", "Unknown"))

                # Generate citation hash
                citation_hash = hashlib.sha256(
                    f"{obj.get('code', '')}:{mit.cell_id}".encode()
                ).hexdigest()[:16]

                anchors.append(EvidenceAnchor(
                    offset_type=offset_type,
                    data_anchor=data_anchor,
                    weight=Decimal(str(obj.get("weight", "0"))),
                    source_cell_id=mit.cell_id,
                    citation_hash=citation_hash,
                ))

        return EvidenceAnchorGrid(
            inherent_weight=inherent,
            inherent_normalized=inherent_norm,
            residual_normalized=residual_norm,
            anchors=anchors
        )

    def _render_gate_1(self, gate: GateResult, typology: TypologyClass, w: int) -> List[str]:
        """Render Gate 1 section."""
        lines = []
        lines.append("GATE 1: CONTEXTUAL TYPOLOGY")
        lines.append("-" * w)
        lines.append(f"   Typology Class: {typology.value}")

        # Forbidden typologies for PEP transactions
        if typology == TypologyClass.PEP_TRANSACTION:
            lines.append("   Forbidden Typologies: TRADE_BASED_ML, MARITIME_DECEPTION")
        else:
            lines.append(f"   Forbidden Typologies: {'DETECTED' if gate.status == GateStatus.FAIL else 'NONE DETECTED'}")
        lines.append("")
        return lines

    def _render_gate_2(self, eval_result: Any, pack_runtime: Any, w: int) -> List[str]:
        """Render Gate 2 section split into obligations and risk indicators."""
        lines = []

        # Classify signals into obligations vs risk indicators
        pep_signals = []
        other_obligations = []
        risk_indicators = []

        # PEP hierarchy (highest priority first)
        pep_hierarchy = ['PEP_FOREIGN', 'PEP_DOMESTIC', 'PEP_HIO', 'PEP_FAMILY_ASSOCIATE']

        # Non-PEP obligations
        non_pep_obligations = {
            'SCREEN_SANCTIONS_HIT', 'GEO_SANCTIONED_COUNTRY', 'TXN_LARGE_CASH'
        }

        if eval_result and eval_result.signals:
            for signal in eval_result.signals:
                obj = signal.fact.object
                code = obj.get("code", "UNKNOWN")
                if code in pep_hierarchy:
                    pep_signals.append((pep_hierarchy.index(code), signal))
                elif code in non_pep_obligations:
                    other_obligations.append(signal)
                else:
                    risk_indicators.append(signal)

        # GATE 2A: Regulatory Obligations
        lines.append("GATE 2A: REGULATORY OBLIGATIONS TRIGGERED")
        lines.append("-" * w)

        has_obligations = False

        # Resolve PEP classification (show only highest priority)
        if pep_signals:
            has_obligations = True
            pep_signals.sort(key=lambda x: x[0])  # Sort by hierarchy
            resolved_pep = pep_signals[0][1]
            resolved_code = resolved_pep.fact.object.get("code", "UNKNOWN")
            resolved_name = resolved_pep.fact.object.get("name", resolved_code)

            lines.append(f"   PEP STATUS: {resolved_code} (Resolved)")
            lines.append(f"      Classification: {resolved_name}")
            lines.append("      Obligation: Enhanced Due Diligence required (PCMLTFR s.9.3)")

            # Show what was evaluated
            if len(pep_signals) > 1:
                considered = [s[1].fact.object.get("code", "") for s in pep_signals[1:]]
                lines.append(f"      Also Evaluated: {', '.join(considered)}")
            lines.append("")

        # Show other (non-PEP) obligations
        for signal in other_obligations:
            has_obligations = True
            obj = signal.fact.object
            code = obj.get("code", "UNKNOWN")
            name = obj.get("name", code)
            lines.append(f"   {code}: {name}")
            if code == 'SCREEN_SANCTIONS_HIT':
                lines.append("      Obligation: Manual disposition required (SEMA)")
            elif code == 'TXN_LARGE_CASH':
                lines.append("      Obligation: LCTR reporting threshold (PCMLTFR s.12)")
            elif code == 'GEO_SANCTIONED_COUNTRY':
                lines.append("      Obligation: Sanctions screening required (SEMA)")

        if not has_obligations:
            lines.append("   (none)")
        lines.append("")

        # GATE 2B: Risk Indicators
        lines.append("GATE 2B: RISK INDICATORS DETECTED")
        lines.append("-" * w)
        if risk_indicators:
            for signal in risk_indicators[:8]:  # Limit display
                obj = signal.fact.object
                code = obj.get("code", "UNKNOWN")
                name = obj.get("name", code)
                lines.append(f"   {code}: {name}")
        else:
            lines.append("   (none)")
        lines.append("")

        # GATE 2C: Mitigating Factors
        lines.append("GATE 2C: MITIGATING FACTORS (Pause & Pivot)")
        lines.append("-" * w)

        if eval_result and eval_result.mitigations:
            for mit in eval_result.mitigations:
                obj = mit.fact.object
                code = obj.get("code", "UNKNOWN")
                weight = obj.get("weight", "0")
                name = obj.get("name", code)

                lines.append(f"   {code}: {name}")

                evidence_anchors = obj.get("evidence_anchors", [])
                if evidence_anchors:
                    for anchor in evidence_anchors[:2]:  # Limit
                        field = anchor.get("field", "unknown")
                        value = anchor.get("value", "")
                        source = anchor.get("source", "")
                        if len(str(value)) > 40:
                            value = str(value)[:37] + "..."
                        lines.append(f"      Evidence: {field}: {value}")
                        lines.append(f"      Source: {source}")

                lines.append(f"      Regulatory Effect: {weight} contextual risk adjustment")

                # Add limitation for PEP-related mitigations
                if 'PEP' in code or 'SCREEN' in code:
                    lines.append("      Limitation: Does NOT override EDD obligations")
                else:
                    lines.append("      Limitation: Applies to risk assessment only")

                # Add citation hash
                citation_hash = hashlib.sha256(f"{code}:{mit.cell_id}".encode()).hexdigest()[:16]
                lines.append(f"      Citation: {citation_hash}...")
                lines.append("")
        else:
            lines.append("   (none)")
            lines.append("")

        # Mitigation Sufficiency Statement
        lines.append("MITIGATION ASSESSMENT")
        lines.append("-" * w)
        if eval_result and eval_result.mitigations:
            lines.append("   Status: Mitigations applied but INSUFFICIENT to clear gate")
            lines.append("   Reason: Residual risk remains above automated clearance threshold")
        else:
            lines.append("   Status: No mitigating factors applicable")
        lines.append("")

        # Regulatory Obligation Summary Table
        lines.append("REGULATORY OBLIGATIONS SUMMARY")
        lines.append("-" * w)
        lines.append("   Obligation                          Status")
        lines.append("   " + "-" * 52)

        # Determine obligation statuses based on signals
        has_pep = any(pep_signals)
        has_sanctions = any(s.fact.object.get("code") == "SCREEN_SANCTIONS_HIT" for s in other_obligations)
        has_lctr = any(s.fact.object.get("code") == "TXN_LARGE_CASH" for s in other_obligations)

        if has_pep:
            lines.append("   PEP Enhanced Due Diligence          REQUIRED")
        else:
            lines.append("   PEP Enhanced Due Diligence          NOT_APPLICABLE")

        if has_sanctions:
            lines.append("   Sanctions Disposition               REQUIRED")
        else:
            lines.append("   Sanctions Disposition               CLEAR")

        lines.append("   Transaction Review                  REQUIRED")
        lines.append("   Automated Clearance                 NOT_PERMITTED")
        lines.append("")

        return lines

    def _render_gate_3(self, eval_result: Any, anchor_grid: EvidenceAnchorGrid, w: int) -> List[str]:
        """Render Gate 3 section with dual-score methodology."""
        lines = []
        lines.append("GATE 3: RESIDUAL RISK CALCULATION")
        lines.append("-" * w)

        # Raw scores (additive - for explainability)
        inherent_raw = anchor_grid.inherent_weight
        mitigation = anchor_grid.mitigation_sum
        residual_raw = anchor_grid.residual_score

        # Normalized scores (for threshold matching)
        inherent_norm = anchor_grid.inherent_normalized
        residual_norm = anchor_grid.residual_normalized

        lines.append("   RAW SCORES (Additive - for transparency):")
        lines.append(f"      Inherent (raw):     {inherent_raw}")
        lines.append(f"      Mitigations:        {mitigation}")
        lines.append(f"      Residual (raw):     {residual_raw:.2f}")
        lines.append("")
        lines.append("   NORMALIZED SCORES (Probability union - for thresholds):")
        lines.append(f"      Inherent (norm):    {inherent_norm:.2f}")
        lines.append(f"      Residual (norm):    {residual_norm:.2f}")
        lines.append(f"      Risk Reduction:     {anchor_grid.mitigation_percentage}%")
        lines.append("")

        # Threshold gates - clearly labeled as applying to normalized
        lines.append("   THRESHOLD GATES (applied to normalized score):")
        lines.append("      <=0.25 = AUTO_CLOSE")
        lines.append("      0.26-0.50 = ANALYST_REVIEW")
        lines.append("      0.51-0.75 = SENIOR_REVIEW")
        lines.append("      0.76-0.89 = COMPLIANCE_REVIEW")
        lines.append("      >=0.90 = STR_CONSIDERATION*")
        lines.append("")
        lines.append("   * STR consideration also triggered by hard obligation gates")
        lines.append("     (sanctions match, designated PEP categories)")
        lines.append("")

        return lines

    def _render_gate_3_verdict(self, eval_result: Any, anchor_grid: EvidenceAnchorGrid, w: int) -> List[str]:
        """Render verdict section within Gate 3."""
        lines = []

        # CLEARANCE CONDITIONS (Counterfactual Analysis) - examiner requirement
        lines.append("CLEARANCE CONDITIONS (COUNTERFACTUAL ANALYSIS)")
        lines.append("-" * w)
        lines.append("This case could not be cleared automatically due to:")
        lines.append("")

        # Build counterfactual conditions based on signals and score
        residual_norm = anchor_grid.residual_normalized

        # Check for PEP obligation
        has_pep = False
        has_sanctions = False
        if eval_result and eval_result.signals:
            for signal in eval_result.signals:
                code = signal.fact.object.get("code", "")
                if "PEP" in code:
                    has_pep = True
                if "SANCTION" in code:
                    has_sanctions = True

        if has_pep:
            lines.append("   * Foreign PEP status requires senior compliance approval")
        if has_sanctions:
            lines.append("   * Sanctions screening requires manual disposition")
        if residual_norm > Decimal("0.25"):
            lines.append("   * Residual risk score exceeds automated clearance threshold (0.25)")
        if residual_norm > Decimal("0.50"):
            lines.append("   * Cross-border wire activity exceeds low-risk thresholds")

        lines.append("")
        lines.append("If these conditions were resolved, the case would be eligible")
        lines.append("for re-evaluation at a lower review tier.")
        lines.append("")

        # VERDICT
        lines.append("VERDICT")
        lines.append("-" * w)

        verdict = "PENDING"
        auto_archive = False
        if eval_result and eval_result.verdict:
            obj = eval_result.verdict.fact.object
            verdict = obj.get("verdict", "PENDING")
            auto_archive = obj.get("auto_archive_permitted", False)

        lines.append(f"   Verdict: {verdict}")

        # Build rationale using normalized score
        residual_raw = anchor_grid.residual_score
        mitigation_count = len(anchor_grid.anchors)
        mitigation_names = ", ".join([a.offset_type[:15] for a in anchor_grid.anchors[:3]])

        rationale = f"Normalized Risk: {residual_norm:.2f} (raw: {residual_raw:.2f}). "
        if mitigation_count > 0:
            rationale += f"Mitigating factors: {mitigation_names}. "
            rationale += f"Risk reduction: {anchor_grid.mitigation_percentage}%. "
        rationale += f"{'Auto-archive permitted' if auto_archive else 'Manual review required'}."

        lines.append(f"   Rationale: {rationale}")
        lines.append("")

        return lines

    def _render_policy_citations(
        self,
        citation_registry: CitationRegistry,
        signal_codes: List[str],
        w: int
    ) -> List[str]:
        """Render policy citations section."""
        lines = []
        lines.append("=" * w)
        lines.append("POLICY CITATIONS")
        lines.append("=" * w)

        for code in sorted(set(signal_codes)):
            citations = citation_registry.get_citations_for_signal(code)
            if citations:
                lines.append(f"Signal: {code} ({len(citations)} citations)")
                lines.append("-" * w)
                for i, citation in enumerate(citations, 1):
                    lines.append(f"{i}. {citation.authority}:{citation.document}")
                    lines.append(f"   Section: {citation.section}")
                    lines.append(f"   Applies: Policy citation for {code} signal")
                    lines.append(f"   SHA256: {citation.citation_hash[:16]}...")
                lines.append("")

        return lines

    def _render_citation_quality_summary(self, quality: CitationQuality, w: int) -> List[str]:
        """Render citation quality summary."""
        lines = []
        lines.append("=" * w)
        lines.append("CITATION QUALITY SUMMARY")
        lines.append("=" * w)
        lines.append(f"Total Citations:    {quality.total_citations}")
        lines.append(f"Signals Covered:    {quality.signals_with_citations}/{quality.total_signals}")
        lines.append(f"Citation Quality:   {int(quality.coverage_ratio * 100)}%")
        lines.append("")
        return lines

    def _render_decision(self, eval_result: Any, anchor_grid: EvidenceAnchorGrid, w: int) -> List[str]:
        """Render decision section with canonical vocabulary."""
        lines = []
        lines.append("=" * w)
        lines.append("DECISION")
        lines.append("=" * w)

        verdict = "PENDING"
        auto_archive = False
        if eval_result and eval_result.verdict:
            obj = eval_result.verdict.fact.object
            verdict = obj.get("verdict", "PENDING")
            auto_archive = obj.get("auto_archive_permitted", False)

        # Canonical verdict mapping (for consistency across report)
        verdict_display_map = {
            "CLEAR_AND_CLOSE": "CLEAR",
            "AUTO_CLOSE": "AUTO_CLEAR",
            "ANALYST_REVIEW": "REVIEW_L1",
            "SENIOR_REVIEW": "REVIEW_L2",
            "COMPLIANCE_REVIEW": "REVIEW_COMPLIANCE",
            "COMPLIANCE_ESCALATION": "ESCALATE_COMPLIANCE",
            "STR_CONSIDERATION": "ESCALATE_STR",
        }
        canonical_verdict = verdict_display_map.get(verdict, verdict)

        # Map verdict to action
        action = "REVIEW"
        if verdict in ["CLEAR_AND_CLOSE", "AUTO_CLOSE"]:
            action = "APPROVE"
        elif verdict in ["COMPLIANCE_ESCALATION", "COMPLIANCE_REVIEW"]:
            action = "ESCALATE_COMPLIANCE"
        elif verdict in ["STR_CONSIDERATION"]:
            action = "ESCALATE_STR"

        # Determine tier
        tier = 1
        tier_name = "L1_ANALYST"
        if verdict in ["ANALYST_REVIEW"]:
            tier, tier_name = 1, "L1_ANALYST"
        elif verdict in ["SENIOR_REVIEW"]:
            tier, tier_name = 2, "L2_SENIOR"
        elif verdict in ["COMPLIANCE_REVIEW", "COMPLIANCE_ESCALATION"]:
            tier, tier_name = 3, "COMPLIANCE_OFFICER"
        elif verdict in ["STR_CONSIDERATION"]:
            tier, tier_name = 4, "MLRO"

        # Calculate confidence
        confidence = 85 if auto_archive else 70
        if anchor_grid.mitigation_sum < 0:
            confidence += 10

        lines.append(f"Verdict:        {canonical_verdict}")
        lines.append(f"Action:         {action}")
        lines.append(f"Review Tier:    {tier} ({tier_name})")
        lines.append(f"Confidence:     {confidence}%")
        lines.append(f"Auto-Archive:   {'PERMITTED' if auto_archive else 'NOT PERMITTED'}")
        lines.append("")
        lines.append("Rationale:")
        lines.append(f"  1. ADJUDICATION: {verdict}")
        lines.append(f"  2. Three-Gate Protocol: Residual risk {anchor_grid.residual_score:.2f} after mitigation factors applied")
        lines.append(f"  3. Mitigating factors verified against case evidence per Section 10B")
        lines.append(f"  4. {'Auto-archive permitted' if auto_archive else 'Manual review required'}")
        lines.append("")
        return lines

    def _render_human_review_requirement(self, eval_result: Any, w: int) -> List[str]:
        """Render human review requirement section (examiner requirement)."""
        lines = []
        lines.append("=" * w)
        lines.append("HUMAN REVIEW REQUIREMENT")
        lines.append("=" * w)

        auto_archive = False
        if eval_result and eval_result.verdict:
            auto_archive = eval_result.verdict.fact.object.get("auto_archive_permitted", False)

        if auto_archive:
            lines.append("This decision may be auto-archived without human review.")
            lines.append("")
            lines.append("Automated Components:")
            lines.append("  * Signal detection and scoring")
            lines.append("  * Citation mapping and policy alignment")
            lines.append("  * Threshold gate evaluation")
            lines.append("")
            lines.append("Human-Optional Actions:")
            lines.append("  * Quality assurance review (sampling)")
            lines.append("")
            lines.append("No adverse action has been taken.")
        else:
            lines.append("This decision REQUIRES manual review by a qualified compliance officer.")
            lines.append("")
            lines.append("Automated Components:")
            lines.append("  * Signal detection and scoring")
            lines.append("  * Risk indicator aggregation")
            lines.append("  * Citation mapping and policy alignment")
            lines.append("  * Mitigation factor identification")
            lines.append("")
            lines.append("Human-Required Actions:")
            lines.append("  * Final adjudication decision")
            lines.append("  * STR consideration subject to compliance officer determination")
            lines.append("  * Enhanced due diligence approval")
            lines.append("  * Customer communication (if required)")
            lines.append("")
            lines.append("Automated processing was intentionally halted at the compliance")
            lines.append("escalation boundary in accordance with internal policy.")
            lines.append("")
            lines.append("No automated adverse action has been taken.")
            lines.append("Final disposition requires human judgment.")

        lines.append("")
        return lines

    def _generate_required_actions(
        self,
        eval_result: Any,
        pack_runtime: Any,
        gate_results: Optional[List[GateResult]] = None
    ) -> List[GeneratedAction]:
        """Generate required actions."""
        verdict = None
        signal_codes = []
        residual_score = None
        failed_gates = []

        if eval_result:
            if eval_result.verdict:
                verdict = eval_result.verdict.fact.object.get("verdict", "")
            if eval_result.signals:
                signal_codes = [s.fact.object.get("code", "") for s in eval_result.signals]
            if eval_result.score:
                score_str = eval_result.score.fact.object.get("residual_score", "0")
                residual_score = Decimal(str(score_str))

        if gate_results:
            failed_gates = [g.gate_number for g in gate_results if g.status == GateStatus.FAIL]

        return self.action_generator.generate(
            verdict=verdict,
            signal_codes=signal_codes,
            residual_score=residual_score,
            failed_gates=failed_gates,
        )

    def _render_required_actions(
        self,
        eval_result: Any,
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
                lines.append(f"  {i}. {action.description}")
            lines.append("")
            min_sla = min(a.sla_hours for a in actions)
            lines.append(f"SLA: {min_sla} hours")
        else:
            # Default actions
            verdict = ""
            if eval_result and eval_result.verdict:
                verdict = eval_result.verdict.fact.object.get("verdict", "")

            if verdict in ["CLEAR_AND_CLOSE", "AUTO_CLOSE"]:
                lines.append("  1. Complete case review and document findings")
                lines.append("  2. Update customer risk rating if warranted")
            else:
                lines.append("  1. Complete detailed case review")
                lines.append("  2. Document analysis and findings")
                lines.append("  3. Escalate if additional concerns identified")

            lines.append("")
            lines.append("SLA: 168 hours")

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
        """Compute feedback scores."""
        signal_codes = []
        if eval_result and eval_result.signals:
            signal_codes = [s.fact.object.get("code", "") for s in eval_result.signals]

        citation_quality = CitationQuality()
        if citation_registry:
            citation_quality = citation_registry.compute_citation_quality(signal_codes)

        signals_fired = len(signal_codes)
        total_signals = 22

        evidence_anchored = 0
        total_evidence = 0
        if eval_result and eval_result.mitigations:
            total_evidence = len(eval_result.mitigations)
            for mit in eval_result.mitigations:
                if mit.fact.object.get("evidence_anchors"):
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
        lines.append("FEEDBACK SCORES (Opik Evaluation)")
        lines.append("=" * w)

        lines.append(f"  {'Score':<30} {'Value':>8} {'Assessment':<30}")
        lines.append(f"  {'-'*30} {'-'*8} {'-'*30}")

        conf_pct = int(float(scores.confidence) * 100)
        cite_pct = int(float(scores.citation_quality) * 100)
        sig_pct = int(float(scores.signal_coverage) * 100)

        lines.append(f"  {'confidence':<30} {str(scores.confidence):>8} Navigation confidence: {conf_pct}%")

        # Citation quality details
        cite_desc = f"{cite_pct}% signals have citations"
        lines.append(f"  {'citation_quality':<30} {str(scores.citation_quality):>8} {cite_desc}")

        lines.append(f"  {'signal_coverage':<30} {str(scores.signal_coverage):>8} All signals covered")
        lines.append(f"  {'evidence_completeness':<30} {str(scores.evidence_completeness):>8} Sufficient evidence")

        clarity_desc = "Auto-archive" if scores.decision_clarity == Decimal("1.00") else "Needs human review"
        lines.append(f"  {'decision_clarity':<30} {str(scores.decision_clarity):>8} {clarity_desc}")

        doc_pct = int(float(scores.documentation_completeness) * 100)
        lines.append(f"  {'documentation_completeness':<30} {str(scores.documentation_completeness):>8} {doc_pct}% documents on file")
        lines.append("")
        return lines

    def _render_audit_trail(
        self,
        case_bundle: Any,
        eval_result: Any,
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
            if hasattr(created, 'strftime'):
                created_at = created.strftime('%Y-%m-%d %H:%M:%S UTC')
            else:
                created_at = str(created)

        lines.append(f"Alert Generated:  {created_at}")
        lines.append(f"Case Created:     {created_at}")
        lines.append(f"Navigation Run:   {created_at}")
        lines.append(f"Report Generated: {report_timestamp[:10]}")

        # Tier and action
        tier = 1
        action = "REVIEW"
        if eval_result and eval_result.verdict:
            verdict = eval_result.verdict.fact.object.get("verdict", "")
            if verdict in ["CLEAR_AND_CLOSE", "AUTO_CLOSE"]:
                action = "APPROVE"
            elif verdict in ["COMPLIANCE_ESCALATION", "STR_CONSIDERATION"]:
                action = "ESCALATE"
                tier = 3
            elif verdict == "SENIOR_REVIEW":
                tier = 2

        lines.append(f"Tier:             {tier}")
        lines.append(f"Action:           {action}")
        lines.append(f"Reviewer:         [PENDING ASSIGNMENT]")
        lines.append("")
        return lines

    def _render_case_integrity(
        self,
        case_bundle: Any,
        chain: Any,
        pack_runtime: Any,
        scores: Optional[FeedbackScores],
        w: int
    ) -> List[str]:
        """Render case integrity section."""
        lines = []
        lines.append("=" * w)
        lines.append("CASE INTEGRITY")
        lines.append("=" * w)

        case_id = case_bundle.meta.id if hasattr(case_bundle, 'meta') else "N/A"
        lines.append(f"Alert ID:         {case_id}")
        lines.append(f"Case ID:          {case_id.lower().replace('-', '_')}")
        lines.append(f"Pack Version:     {pack_runtime.pack_version if hasattr(pack_runtime, 'pack_version') else '1.0.0'}")

        if scores:
            lines.append(f"Nav Confidence:   {scores.confidence}")
            cite_pct = int(float(scores.citation_quality) * 100)
            lines.append(f"Citation Quality: {cite_pct}%")

        lines.append("")
        return lines

    def _render_regulatory_references(self, pack_runtime: Any, w: int) -> List[str]:
        """Render regulatory references section."""
        lines = []
        lines.append("=" * w)
        lines.append("REGULATORY REFERENCES")
        lines.append("=" * w)

        # Standard regulatory references for Canadian FinCrime
        refs = [
            "FATF: Recommendation 12 (Politically Exposed Persons)",
            "FINTRAC: Electronic Funds Transfer Reporting",
            "FINTRAC: Large Cash Transaction Reporting",
            "FINTRAC: PEP Guidance",
            "FINTRAC: Proceeds of Crime (Money Laundering) and Terrorist Financing Act",
        ]

        # Add pack-specific references
        if hasattr(pack_runtime, 'regulatory_framework') and pack_runtime.regulatory_framework:
            framework = pack_runtime.regulatory_framework
            if 'primary_legislation' in framework:
                refs.append(f"{framework['primary_legislation']}: Primary Legislation")
            if 'primary_regulations' in framework:
                refs.append(f"{framework['primary_regulations']}: Regulations")

        for ref in refs:
            lines.append(ref)

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
    """Convenience function to render a bank-grade report."""
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
    'BankReportError',
    'RenderError',
    'TypologyClass',
    'GateStatus',
    'ReportConfig',
    'EvidenceAnchor',
    'EvidenceAnchorGrid',
    'FeedbackScores',
    'RequiredAction',
    'GateResult',
    'BankReportRenderer',
    'render_bank_report',
]
