"""
DecisionGraph Confidence Calculation Module (v2.0)

Computes confidence scores for case decisions using weighted factors:
- Citation coverage: % of signals with policy citations
- Evidence completeness: % of mitigations with evidence anchors
- Gate pass rate: % of gates that passed evaluation
- Documentation score: % of required documents on file

The confidence score helps analysts and auditors understand how
well-supported a decision is by the available evidence and citations.

USAGE:
    from decisiongraph.confidence import (
        ConfidenceConfig, ConfidenceCalculator, ConfidenceResult
    )

    calculator = ConfidenceCalculator()
    result = calculator.compute(
        citation_quality=citation_quality,
        gate_results=gate_results,
        evidence_anchored=5,
        total_evidence=6,
        docs_on_file=8,
        docs_required=10,
        auto_archive=False
    )
    print(f"Confidence: {result.overall_confidence}")
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

from .gates import GateResult, GateStatus


# =============================================================================
# EXCEPTIONS
# =============================================================================

class ConfidenceError(Exception):
    """Base exception for confidence calculation errors."""
    pass


class ConfigurationError(ConfidenceError):
    """Raised when configuration is invalid."""
    pass


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class ConfidenceWeights:
    """
    Weights for confidence calculation factors.

    All weights should sum to 1.0 for proper normalization.
    """
    citation_coverage: Decimal = Decimal("0.25")
    evidence_completeness: Decimal = Decimal("0.25")
    gate_pass_rate: Decimal = Decimal("0.25")
    documentation_score: Decimal = Decimal("0.25")

    def __post_init__(self):
        # Ensure weights sum to 1.0
        total = (
            self.citation_coverage +
            self.evidence_completeness +
            self.gate_pass_rate +
            self.documentation_score
        )
        if abs(total - Decimal("1.0")) > Decimal("0.01"):
            # Normalize weights
            self.citation_coverage = self.citation_coverage / total
            self.evidence_completeness = self.evidence_completeness / total
            self.gate_pass_rate = self.gate_pass_rate / total
            self.documentation_score = self.documentation_score / total

    def to_dict(self) -> Dict[str, str]:
        return {
            "citation_coverage": str(self.citation_coverage),
            "evidence_completeness": str(self.evidence_completeness),
            "gate_pass_rate": str(self.gate_pass_rate),
            "documentation_score": str(self.documentation_score),
        }


@dataclass
class ConfidenceConfig:
    """
    Configuration for confidence calculation.
    """
    weights: ConfidenceWeights = field(default_factory=ConfidenceWeights)
    # Minimum confidence threshold for auto-archive
    auto_archive_threshold: Decimal = Decimal("0.80")
    # Penalty for WARN status gates (0.5 means count as half-pass)
    warn_penalty: Decimal = Decimal("0.50")
    # Whether to include decision clarity in overall confidence
    include_decision_clarity: bool = False
    # Precision for rounding results
    precision: int = 2

    @classmethod
    def from_pack(cls, pack_data: Dict[str, Any]) -> "ConfidenceConfig":
        """Load configuration from pack data."""
        conf_data = pack_data.get("confidence", {})

        weights_data = conf_data.get("weights", {})
        weights = ConfidenceWeights(
            citation_coverage=Decimal(str(weights_data.get("citation_coverage", "0.25"))),
            evidence_completeness=Decimal(str(weights_data.get("evidence_completeness", "0.25"))),
            gate_pass_rate=Decimal(str(weights_data.get("gate_pass_rate", "0.25"))),
            documentation_score=Decimal(str(weights_data.get("documentation_score", "0.25"))),
        )

        return cls(
            weights=weights,
            auto_archive_threshold=Decimal(str(conf_data.get("auto_archive_threshold", "0.80"))),
            warn_penalty=Decimal(str(conf_data.get("warn_penalty", "0.50"))),
            include_decision_clarity=conf_data.get("include_decision_clarity", False),
            precision=conf_data.get("precision", 2),
        )


# =============================================================================
# CONFIDENCE FACTORS
# =============================================================================

@dataclass
class ConfidenceFactor:
    """
    A single factor contributing to confidence score.
    """
    name: str
    raw_value: Decimal          # The raw ratio (0.0 to 1.0)
    weight: Decimal             # Weight in overall calculation
    weighted_value: Decimal     # raw_value * weight
    description: str = ""       # Human-readable description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "raw_value": str(self.raw_value),
            "weight": str(self.weight),
            "weighted_value": str(self.weighted_value),
            "description": self.description,
        }


@dataclass
class ConfidenceResult:
    """
    Result of confidence calculation.

    Contains overall confidence and breakdown of contributing factors.
    """
    overall_confidence: Decimal
    factors: List[ConfidenceFactor]
    # Additional metrics
    citation_quality: Decimal
    evidence_completeness: Decimal
    gate_pass_rate: Decimal
    documentation_score: Decimal
    decision_clarity: Decimal
    # Recommendations
    auto_archive_eligible: bool
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_confidence": str(self.overall_confidence),
            "factors": [f.to_dict() for f in self.factors],
            "citation_quality": str(self.citation_quality),
            "evidence_completeness": str(self.evidence_completeness),
            "gate_pass_rate": str(self.gate_pass_rate),
            "documentation_score": str(self.documentation_score),
            "decision_clarity": str(self.decision_clarity),
            "auto_archive_eligible": self.auto_archive_eligible,
            "recommendations": self.recommendations,
        }

    @property
    def confidence_percentage(self) -> int:
        """Return confidence as percentage (0-100)."""
        return int(self.overall_confidence * 100)


# =============================================================================
# CONFIDENCE CALCULATOR
# =============================================================================

class ConfidenceCalculator:
    """
    Calculates confidence scores for case decisions.

    Uses weighted factors to produce an overall confidence score
    that represents how well-supported the decision is.
    """

    def __init__(self, config: Optional[ConfidenceConfig] = None):
        """
        Initialize calculator with configuration.

        Args:
            config: Confidence configuration (uses defaults if None)
        """
        self.config = config or ConfidenceConfig()

    def compute(
        self,
        citation_quality: Optional[Any] = None,  # CitationQuality
        gate_results: Optional[List[GateResult]] = None,
        evidence_anchored: int = 0,
        total_evidence: int = 0,
        docs_on_file: int = 0,
        docs_required: int = 0,
        auto_archive: bool = False,
        signals_fired: int = 0,
        total_signals: int = 0,
    ) -> ConfidenceResult:
        """
        Compute confidence score from inputs.

        Args:
            citation_quality: CitationQuality from registry
            gate_results: List of GateResult from gate evaluation
            evidence_anchored: Number of mitigations with evidence anchors
            total_evidence: Total number of mitigations/evidence items
            docs_on_file: Number of documents on file
            docs_required: Number of required documents
            auto_archive: Whether auto-archive was permitted
            signals_fired: Number of signals that fired
            total_signals: Total signals in pack

        Returns:
            ConfidenceResult with overall score and factor breakdown
        """
        factors = []
        recommendations = []
        precision = Decimal(10) ** -self.config.precision

        # 1. Citation Coverage
        cit_coverage = self._compute_citation_coverage(citation_quality)
        factors.append(ConfidenceFactor(
            name="citation_coverage",
            raw_value=cit_coverage,
            weight=self.config.weights.citation_coverage,
            weighted_value=(cit_coverage * self.config.weights.citation_coverage).quantize(precision),
            description=f"Signals with citations: {self._format_ratio(citation_quality)}"
        ))
        if cit_coverage < Decimal("1.0"):
            recommendations.append("Add policy citations for uncited signals")

        # 2. Evidence Completeness
        ev_completeness = self._compute_evidence_completeness(evidence_anchored, total_evidence)
        factors.append(ConfidenceFactor(
            name="evidence_completeness",
            raw_value=ev_completeness,
            weight=self.config.weights.evidence_completeness,
            weighted_value=(ev_completeness * self.config.weights.evidence_completeness).quantize(precision),
            description=f"Evidence anchored: {evidence_anchored}/{total_evidence}"
        ))
        if ev_completeness < Decimal("1.0") and total_evidence > 0:
            recommendations.append("Ensure all mitigations have evidence anchors")

        # 3. Gate Pass Rate
        gate_pass = self._compute_gate_pass_rate(gate_results)
        factors.append(ConfidenceFactor(
            name="gate_pass_rate",
            raw_value=gate_pass,
            weight=self.config.weights.gate_pass_rate,
            weighted_value=(gate_pass * self.config.weights.gate_pass_rate).quantize(precision),
            description=f"Gates passed: {self._format_gate_ratio(gate_results)}"
        ))
        if gate_pass < Decimal("1.0"):
            recommendations.append("Review gate warnings and failures")

        # 4. Documentation Score
        doc_score = self._compute_documentation_score(docs_on_file, docs_required)
        factors.append(ConfidenceFactor(
            name="documentation_score",
            raw_value=doc_score,
            weight=self.config.weights.documentation_score,
            weighted_value=(doc_score * self.config.weights.documentation_score).quantize(precision),
            description=f"Documents on file: {docs_on_file}/{docs_required}"
        ))
        if doc_score < Decimal("1.0") and docs_required > 0:
            recommendations.append("Obtain missing required documents")

        # Compute overall confidence
        overall = sum(f.weighted_value for f in factors)
        overall = overall.quantize(precision, rounding=ROUND_HALF_UP)

        # Decision clarity (for reference, not in overall by default)
        decision_clarity = Decimal("1.00") if auto_archive else Decimal("0.50")

        # Check auto-archive eligibility
        auto_archive_eligible = (
            overall >= self.config.auto_archive_threshold and
            gate_pass == Decimal("1.0") and
            auto_archive
        )

        return ConfidenceResult(
            overall_confidence=overall,
            factors=factors,
            citation_quality=cit_coverage.quantize(precision),
            evidence_completeness=ev_completeness.quantize(precision),
            gate_pass_rate=gate_pass.quantize(precision),
            documentation_score=doc_score.quantize(precision),
            decision_clarity=decision_clarity,
            auto_archive_eligible=auto_archive_eligible,
            recommendations=recommendations,
        )

    def compute_from_eval_result(
        self,
        eval_result: Any,
        gate_results: Optional[List[GateResult]] = None,
        citation_quality: Optional[Any] = None,
        docs_on_file: int = 0,
        docs_required: int = 0,
    ) -> ConfidenceResult:
        """
        Compute confidence from evaluation result.

        Convenience method that extracts values from eval_result.

        Args:
            eval_result: EvaluationResult from rules engine
            gate_results: Gate evaluation results
            citation_quality: CitationQuality from registry
            docs_on_file: Documents on file
            docs_required: Required documents

        Returns:
            ConfidenceResult
        """
        # Extract values from eval_result
        signals_fired = 0
        evidence_anchored = 0
        total_evidence = 0
        auto_archive = False

        if eval_result:
            if hasattr(eval_result, 'signals') and eval_result.signals:
                signals_fired = len(eval_result.signals)

            if hasattr(eval_result, 'mitigations') and eval_result.mitigations:
                total_evidence = len(eval_result.mitigations)
                # Count mitigations with evidence_anchors
                for mit in eval_result.mitigations:
                    obj = mit.fact.object
                    if obj.get("evidence_anchors"):
                        evidence_anchored += 1

            if hasattr(eval_result, 'verdict') and eval_result.verdict:
                verdict_obj = eval_result.verdict.fact.object
                auto_archive = verdict_obj.get("auto_archive_permitted", False)

        return self.compute(
            citation_quality=citation_quality,
            gate_results=gate_results,
            evidence_anchored=evidence_anchored,
            total_evidence=total_evidence,
            docs_on_file=docs_on_file,
            docs_required=docs_required,
            auto_archive=auto_archive,
            signals_fired=signals_fired,
        )

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    def _compute_citation_coverage(self, citation_quality: Optional[Any]) -> Decimal:
        """Compute citation coverage ratio."""
        if not citation_quality:
            return Decimal("0.00")

        if hasattr(citation_quality, 'coverage_ratio'):
            return Decimal(str(citation_quality.coverage_ratio))

        return Decimal("0.00")

    def _compute_evidence_completeness(
        self,
        evidence_anchored: int,
        total_evidence: int
    ) -> Decimal:
        """Compute evidence completeness ratio."""
        if total_evidence <= 0:
            return Decimal("1.00")  # No evidence needed = complete

        return (Decimal(str(evidence_anchored)) / Decimal(str(total_evidence)))

    def _compute_gate_pass_rate(
        self,
        gate_results: Optional[List[GateResult]]
    ) -> Decimal:
        """
        Compute gate pass rate.

        PASS = 1.0, WARN = warn_penalty (default 0.5), FAIL = 0.0, SKIP = excluded
        """
        if not gate_results:
            return Decimal("1.00")  # No gates = assume pass

        total = Decimal("0")
        count = 0

        for gate in gate_results:
            if gate.status == GateStatus.SKIP:
                continue

            count += 1
            if gate.status == GateStatus.PASS:
                total += Decimal("1.0")
            elif gate.status == GateStatus.WARN:
                total += self.config.warn_penalty
            # FAIL adds 0

        if count == 0:
            return Decimal("1.00")

        return total / Decimal(str(count))

    def _compute_documentation_score(
        self,
        docs_on_file: int,
        docs_required: int
    ) -> Decimal:
        """Compute documentation completeness ratio."""
        if docs_required <= 0:
            return Decimal("1.00")  # No docs required = complete

        return min(
            Decimal("1.00"),
            Decimal(str(docs_on_file)) / Decimal(str(docs_required))
        )

    def _format_ratio(self, citation_quality: Optional[Any]) -> str:
        """Format citation quality as ratio string."""
        if not citation_quality:
            return "0/0"

        if hasattr(citation_quality, 'signals_with_citations') and hasattr(citation_quality, 'total_signals'):
            return f"{citation_quality.signals_with_citations}/{citation_quality.total_signals}"

        return "N/A"

    def _format_gate_ratio(self, gate_results: Optional[List[GateResult]]) -> str:
        """Format gate results as ratio string."""
        if not gate_results:
            return "0/0"

        passed = sum(1 for g in gate_results if g.status == GateStatus.PASS)
        total = sum(1 for g in gate_results if g.status != GateStatus.SKIP)

        return f"{passed}/{total}"


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def compute_confidence(
    citation_quality: Optional[Any] = None,
    gate_results: Optional[List[GateResult]] = None,
    evidence_anchored: int = 0,
    total_evidence: int = 0,
    docs_on_file: int = 0,
    docs_required: int = 0,
    auto_archive: bool = False,
    config: Optional[ConfidenceConfig] = None,
) -> ConfidenceResult:
    """
    Convenience function to compute confidence.

    Args:
        citation_quality: CitationQuality from registry
        gate_results: Gate evaluation results
        evidence_anchored: Mitigations with evidence anchors
        total_evidence: Total mitigations
        docs_on_file: Documents on file
        docs_required: Required documents
        auto_archive: Whether auto-archive is permitted
        config: Optional configuration

    Returns:
        ConfidenceResult
    """
    calculator = ConfidenceCalculator(config)
    return calculator.compute(
        citation_quality=citation_quality,
        gate_results=gate_results,
        evidence_anchored=evidence_anchored,
        total_evidence=total_evidence,
        docs_on_file=docs_on_file,
        docs_required=docs_required,
        auto_archive=auto_archive,
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Exceptions
    'ConfidenceError',
    'ConfigurationError',
    # Configuration
    'ConfidenceWeights',
    'ConfidenceConfig',
    # Results
    'ConfidenceFactor',
    'ConfidenceResult',
    # Calculator
    'ConfidenceCalculator',
    # Convenience
    'compute_confidence',
]
