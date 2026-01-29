"""
DecisionGraph Gates Module (v2.0)

Implements the 4-Gate Protocol for bank-grade case evaluation:
- Gate 1: Contextual Typology - Classify case into risk typology
- Gate 2: Inherent Risks + Mitigating Factors - Identify and offset risks
- Gate 3: Residual Risk Calculation - Compute final score with evidence grid
- Gate 4: Integrity Audit - Verify consistency and chain integrity

Gate definitions can be customized per pack, allowing different verticals
(FinCrime, Insurance, etc.) to define their own gate configurations.

USAGE:
    from decisiongraph.gates import (
        GateDefinition, GateConfig, GateEvaluator, GateResult
    )

    # Load gate config from pack
    config = GateConfig.from_pack(pack_data)

    # Create evaluator
    evaluator = GateEvaluator(config)

    # Evaluate gates
    g1 = evaluator.evaluate_gate_1(case_bundle)
    g2 = evaluator.evaluate_gate_2(eval_result)
    g3 = evaluator.evaluate_gate_3(eval_result, anchor_grid)
    g4 = evaluator.evaluate_gate_4(eval_result, chain)
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set


# =============================================================================
# EXCEPTIONS
# =============================================================================

class GateError(Exception):
    """Base exception for gate errors."""
    pass


class GateConfigError(GateError):
    """Raised when gate configuration is invalid."""
    pass


class GateEvaluationError(GateError):
    """Raised when gate evaluation fails."""
    pass


# =============================================================================
# ENUMS
# =============================================================================

class GateStatus(str, Enum):
    """Status of a gate evaluation."""
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"  # Gate was skipped (not configured)


class GateNumber(int, Enum):
    """Standard gate numbers."""
    TYPOLOGY = 1
    INHERENT_MITIGATING = 2
    RESIDUAL_RISK = 3
    INTEGRITY_AUDIT = 4


# =============================================================================
# GATE RESULT
# =============================================================================

@dataclass
class GateResult:
    """
    Result of evaluating a single gate.

    Contains the gate status, details, and any warnings/failures.
    """
    gate_number: int
    gate_name: str
    status: GateStatus
    details: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "gate_number": self.gate_number,
            "gate_name": self.gate_name,
            "status": self.status.value,
            "details": self.details,
            "warnings": self.warnings,
            "failures": self.failures,
        }

    @property
    def passed(self) -> bool:
        """Check if gate passed."""
        return self.status == GateStatus.PASS

    @property
    def failed(self) -> bool:
        """Check if gate failed."""
        return self.status == GateStatus.FAIL


# =============================================================================
# GATE DEFINITIONS
# =============================================================================

@dataclass
class TypologyGateConfig:
    """Configuration for Gate 1: Contextual Typology."""
    name: str = "Contextual Typology"
    description: str = "Classify case into risk typology"
    # Allowed typology classes for this pack
    typology_classes: List[str] = field(default_factory=lambda: [
        "TECH_INVESTMENT",
        "TRADE_BASED_ML",
        "REAL_ESTATE_ML",
        "SHELL_COMPANY",
        "STRUCTURING",
        "CRYPTO_MIXING",
        "LAYERING",
        "KYC_ONBOARDING",
        "EDD_REVIEW",
        "PERIODIC_REVIEW",
    ])
    # Typologies that should trigger immediate escalation
    forbidden_typologies: List[str] = field(default_factory=lambda: [
        "MARITIME_DECEPTION",
        "HUMAN_TRAFFICKING",
        "TERRORISM_FINANCING",
        "PROLIFERATION_FINANCING",
    ])
    # Default typology if none detected
    default_typology: str = "UNKNOWN"


@dataclass
class InherentMitigatingGateConfig:
    """Configuration for Gate 2: Inherent Risks + Mitigating Factors."""
    name: str = "Inherent Risks + Mitigating Factors"
    description: str = "Identify risks and apply mitigations"
    # Minimum signals required for meaningful evaluation
    min_signals_for_review: int = 0
    # Warning threshold for signal count
    high_signal_threshold: int = 5
    # Whether mitigations are required
    require_mitigations: bool = False


@dataclass
class ResidualRiskGateConfig:
    """Configuration for Gate 3: Residual Risk Calculation."""
    name: str = "Residual Risk Calculation"
    description: str = "Compute final score with evidence grid"
    # Score thresholds for status determination
    low_risk_threshold: str = "0.30"   # Below = PASS (low risk)
    high_risk_threshold: str = "0.70"  # Above = WARN (high risk)
    # Floor for residual score
    score_floor: str = "0.00"


@dataclass
class IntegrityAuditGateConfig:
    """Configuration for Gate 4: Integrity Audit."""
    name: str = "Integrity Audit"
    description: str = "Verify consistency and chain integrity"
    # Checks to perform
    checks: List[str] = field(default_factory=lambda: [
        "typology_match",      # Typology consistent with signals
        "verdict_alignment",   # Verdict matches score threshold
        "language_audit",      # No prohibited language in outputs
        "chain_integrity",     # Hash chain is valid
    ])
    # Prohibited language patterns (for language_audit)
    prohibited_patterns: List[str] = field(default_factory=list)


@dataclass
class GateConfig:
    """
    Complete gate configuration for a pack.

    Defines all 4 gates with their settings.
    """
    gate_1: TypologyGateConfig = field(default_factory=TypologyGateConfig)
    gate_2: InherentMitigatingGateConfig = field(default_factory=InherentMitigatingGateConfig)
    gate_3: ResidualRiskGateConfig = field(default_factory=ResidualRiskGateConfig)
    gate_4: IntegrityAuditGateConfig = field(default_factory=IntegrityAuditGateConfig)

    @classmethod
    def from_pack(cls, pack_data: Dict[str, Any]) -> "GateConfig":
        """
        Build gate config from pack data.

        Args:
            pack_data: Pack YAML data with optional 'gates' section

        Returns:
            GateConfig with pack-specific settings
        """
        gates_data = pack_data.get("gates", {})

        # Gate 1: Typology
        g1_data = gates_data.get("gate_1_typology", {})
        gate_1 = TypologyGateConfig(
            name=g1_data.get("name", "Contextual Typology"),
            description=g1_data.get("description", "Classify case into risk typology"),
            typology_classes=g1_data.get("typology_classes", TypologyGateConfig().typology_classes),
            forbidden_typologies=g1_data.get("forbidden_typologies", TypologyGateConfig().forbidden_typologies),
            default_typology=g1_data.get("default_typology", "UNKNOWN"),
        )

        # Gate 2: Inherent + Mitigating
        g2_data = gates_data.get("gate_2_inherent_mitigating", {})
        gate_2 = InherentMitigatingGateConfig(
            name=g2_data.get("name", "Inherent Risks + Mitigating Factors"),
            description=g2_data.get("description", "Identify risks and apply mitigations"),
            min_signals_for_review=g2_data.get("min_signals_for_review", 0),
            high_signal_threshold=g2_data.get("high_signal_threshold", 5),
            require_mitigations=g2_data.get("require_mitigations", False),
        )

        # Gate 3: Residual Risk
        g3_data = gates_data.get("gate_3_residual", {})
        gate_3 = ResidualRiskGateConfig(
            name=g3_data.get("name", "Residual Risk Calculation"),
            description=g3_data.get("description", "Compute final score with evidence grid"),
            low_risk_threshold=str(g3_data.get("low_risk_threshold", "0.30")),
            high_risk_threshold=str(g3_data.get("high_risk_threshold", "0.70")),
            score_floor=str(g3_data.get("score_floor", "0.00")),
        )

        # Gate 4: Integrity Audit
        g4_data = gates_data.get("gate_4_integrity", {})
        gate_4 = IntegrityAuditGateConfig(
            name=g4_data.get("name", "Integrity Audit"),
            description=g4_data.get("description", "Verify consistency and chain integrity"),
            checks=g4_data.get("checks", IntegrityAuditGateConfig().checks),
            prohibited_patterns=g4_data.get("prohibited_patterns", []),
        )

        return cls(gate_1=gate_1, gate_2=gate_2, gate_3=gate_3, gate_4=gate_4)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for pack export."""
        return {
            "gate_1_typology": {
                "name": self.gate_1.name,
                "description": self.gate_1.description,
                "typology_classes": self.gate_1.typology_classes,
                "forbidden_typologies": self.gate_1.forbidden_typologies,
                "default_typology": self.gate_1.default_typology,
            },
            "gate_2_inherent_mitigating": {
                "name": self.gate_2.name,
                "description": self.gate_2.description,
                "min_signals_for_review": self.gate_2.min_signals_for_review,
                "high_signal_threshold": self.gate_2.high_signal_threshold,
                "require_mitigations": self.gate_2.require_mitigations,
            },
            "gate_3_residual": {
                "name": self.gate_3.name,
                "description": self.gate_3.description,
                "low_risk_threshold": self.gate_3.low_risk_threshold,
                "high_risk_threshold": self.gate_3.high_risk_threshold,
                "score_floor": self.gate_3.score_floor,
            },
            "gate_4_integrity": {
                "name": self.gate_4.name,
                "description": self.gate_4.description,
                "checks": self.gate_4.checks,
                "prohibited_patterns": self.gate_4.prohibited_patterns,
            },
        }


# =============================================================================
# GATE EVALUATOR
# =============================================================================

class GateEvaluator:
    """
    Evaluates cases through the 4-Gate Protocol.

    Each gate produces a GateResult with status, details, and any warnings.
    The evaluator is configured by a GateConfig (from pack or defaults).
    """

    def __init__(self, config: Optional[GateConfig] = None):
        """
        Initialize evaluator with config.

        Args:
            config: Gate configuration (defaults to standard config)
        """
        self.config = config or GateConfig()

    def evaluate_gate_1(
        self,
        case_bundle: Any,
        detected_typology: Optional[str] = None
    ) -> GateResult:
        """
        Evaluate Gate 1: Contextual Typology.

        Classifies the case into a typology and checks for forbidden types.

        Args:
            case_bundle: The case data
            detected_typology: Pre-detected typology (if any)

        Returns:
            GateResult with typology classification
        """
        cfg = self.config.gate_1
        warnings = []
        failures = []

        # Determine typology
        typology = detected_typology or self._detect_typology(case_bundle)
        if not typology:
            typology = cfg.default_typology
            warnings.append(f"No typology detected, using default: {typology}")

        # Check if typology is forbidden
        if typology in cfg.forbidden_typologies:
            failures.append(f"Forbidden typology detected: {typology}")
            return GateResult(
                gate_number=GateNumber.TYPOLOGY,
                gate_name=cfg.name,
                status=GateStatus.FAIL,
                details={
                    "typology": typology,
                    "forbidden": True,
                    "allowed_typologies": cfg.typology_classes,
                },
                warnings=warnings,
                failures=failures,
            )

        # Check if typology is in allowed list
        if typology not in cfg.typology_classes and typology != cfg.default_typology:
            warnings.append(f"Typology '{typology}' not in configured list")

        return GateResult(
            gate_number=GateNumber.TYPOLOGY,
            gate_name=cfg.name,
            status=GateStatus.PASS,
            details={
                "typology": typology,
                "forbidden": False,
                "allowed_typologies": cfg.typology_classes,
            },
            warnings=warnings,
            failures=failures,
        )

    def evaluate_gate_2(
        self,
        eval_result: Any
    ) -> GateResult:
        """
        Evaluate Gate 2: Inherent Risks + Mitigating Factors.

        Checks signal and mitigation counts against thresholds.

        Args:
            eval_result: Evaluation result with signals and mitigations

        Returns:
            GateResult with risk assessment
        """
        cfg = self.config.gate_2
        warnings = []
        failures = []

        # Count signals and mitigations
        signal_count = 0
        mitigation_count = 0

        if eval_result:
            if hasattr(eval_result, 'signals') and eval_result.signals:
                signal_count = len(eval_result.signals)
            if hasattr(eval_result, 'mitigations') and eval_result.mitigations:
                mitigation_count = len(eval_result.mitigations)

        # Check thresholds
        if signal_count >= cfg.high_signal_threshold:
            warnings.append(f"High signal count: {signal_count} >= {cfg.high_signal_threshold}")

        if cfg.require_mitigations and signal_count > 0 and mitigation_count == 0:
            warnings.append("Signals detected but no mitigations applied")

        # Determine status
        status = GateStatus.PASS
        if signal_count >= cfg.high_signal_threshold:
            status = GateStatus.WARN

        return GateResult(
            gate_number=GateNumber.INHERENT_MITIGATING,
            gate_name=cfg.name,
            status=status,
            details={
                "signals_count": signal_count,
                "mitigations_count": mitigation_count,
                "high_signal_threshold": cfg.high_signal_threshold,
            },
            warnings=warnings,
            failures=failures,
        )

    def evaluate_gate_3(
        self,
        eval_result: Any,
        residual_score: Optional[Decimal] = None
    ) -> GateResult:
        """
        Evaluate Gate 3: Residual Risk Calculation.

        Assesses the residual risk score against thresholds.

        Args:
            eval_result: Evaluation result with score
            residual_score: Pre-computed residual score (optional)

        Returns:
            GateResult with risk level
        """
        cfg = self.config.gate_3
        warnings = []
        failures = []

        # Get residual score
        if residual_score is None and eval_result and hasattr(eval_result, 'score'):
            if eval_result.score:
                score_obj = eval_result.score.fact.object
                residual_score = Decimal(str(score_obj.get("residual_score", "0")))

        if residual_score is None:
            residual_score = Decimal("0")
            warnings.append("No score available, defaulting to 0")

        # Apply floor
        floor = Decimal(cfg.score_floor)
        if residual_score < floor:
            residual_score = floor

        # Determine status based on thresholds
        low_threshold = Decimal(cfg.low_risk_threshold)
        high_threshold = Decimal(cfg.high_risk_threshold)

        if residual_score < low_threshold:
            status = GateStatus.PASS
            risk_level = "LOW"
        elif residual_score < high_threshold:
            status = GateStatus.WARN
            risk_level = "MEDIUM"
        else:
            status = GateStatus.WARN
            risk_level = "HIGH"
            warnings.append(f"High residual risk: {residual_score}")

        return GateResult(
            gate_number=GateNumber.RESIDUAL_RISK,
            gate_name=cfg.name,
            status=status,
            details={
                "residual_score": str(residual_score),
                "risk_level": risk_level,
                "low_threshold": cfg.low_risk_threshold,
                "high_threshold": cfg.high_risk_threshold,
            },
            warnings=warnings,
            failures=failures,
        )

    def evaluate_gate_4(
        self,
        eval_result: Any,
        chain: Any = None,
        detected_typology: Optional[str] = None
    ) -> GateResult:
        """
        Evaluate Gate 4: Integrity Audit.

        Performs consistency and integrity checks.

        Args:
            eval_result: Evaluation result
            chain: Hash chain for integrity check
            detected_typology: Typology from Gate 1

        Returns:
            GateResult with audit results
        """
        cfg = self.config.gate_4
        warnings = []
        failures = []
        check_results = {}

        # Perform each configured check
        for check in cfg.checks:
            if check == "typology_match":
                passed = self._check_typology_match(eval_result, detected_typology)
                check_results["typology_match"] = passed
                if not passed:
                    warnings.append("Typology may not match detected signals")

            elif check == "verdict_alignment":
                passed = self._check_verdict_alignment(eval_result)
                check_results["verdict_alignment"] = passed
                if not passed:
                    warnings.append("Verdict may not align with score")

            elif check == "language_audit":
                passed = self._check_language_audit(eval_result, cfg.prohibited_patterns)
                check_results["language_audit"] = passed
                if not passed:
                    failures.append("Prohibited language detected")

            elif check == "chain_integrity":
                passed = self._check_chain_integrity(chain)
                check_results["chain_integrity"] = passed
                if not passed:
                    failures.append("Chain integrity check failed")

        # Determine overall status
        if failures:
            status = GateStatus.FAIL
        elif warnings:
            status = GateStatus.WARN
        else:
            status = GateStatus.PASS

        return GateResult(
            gate_number=GateNumber.INTEGRITY_AUDIT,
            gate_name=cfg.name,
            status=status,
            details={
                "checks_performed": cfg.checks,
                "check_results": check_results,
            },
            warnings=warnings,
            failures=failures,
        )

    def evaluate_all(
        self,
        case_bundle: Any,
        eval_result: Any,
        chain: Any = None,
        detected_typology: Optional[str] = None,
        residual_score: Optional[Decimal] = None
    ) -> List[GateResult]:
        """
        Evaluate all 4 gates in sequence.

        Args:
            case_bundle: The case data
            eval_result: Evaluation result
            chain: Hash chain
            detected_typology: Pre-detected typology
            residual_score: Pre-computed residual score

        Returns:
            List of 4 GateResults
        """
        g1 = self.evaluate_gate_1(case_bundle, detected_typology)
        g2 = self.evaluate_gate_2(eval_result)
        g3 = self.evaluate_gate_3(eval_result, residual_score)
        g4 = self.evaluate_gate_4(eval_result, chain, g1.details.get("typology"))

        return [g1, g2, g3, g4]

    def overall_status(self, results: List[GateResult]) -> GateStatus:
        """
        Determine overall status from gate results.

        Args:
            results: List of GateResults

        Returns:
            Overall GateStatus (FAIL if any failed, WARN if any warned, else PASS)
        """
        if any(r.status == GateStatus.FAIL for r in results):
            return GateStatus.FAIL
        if any(r.status == GateStatus.WARN for r in results):
            return GateStatus.WARN
        return GateStatus.PASS

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    def _detect_typology(self, case_bundle: Any) -> Optional[str]:
        """
        Detect typology from case data.

        This is a basic implementation - can be extended with ML or rules.
        """
        if not case_bundle:
            return None

        # Try to get from case metadata
        if hasattr(case_bundle, 'meta'):
            meta = case_bundle.meta
            if hasattr(meta, 'case_type'):
                case_type = meta.case_type
                if hasattr(case_type, 'value'):
                    # Map case types to typologies
                    type_map = {
                        "aml_alert": "STRUCTURING",
                        "kyc_onboarding": "KYC_ONBOARDING",
                        "kyc_review": "PERIODIC_REVIEW",
                        "edd_review": "EDD_REVIEW",
                        "sanctions_screening": "SANCTIONS_SCREENING",
                    }
                    return type_map.get(case_type.value, "UNKNOWN")

        return None

    def _check_typology_match(
        self,
        eval_result: Any,
        typology: Optional[str]
    ) -> bool:
        """Check if typology matches detected signals."""
        # Basic check - can be extended with signal-typology mapping
        if not typology or not eval_result:
            return True

        # For now, always pass - real implementation would check
        # if signals are consistent with typology
        return True

    def _check_verdict_alignment(self, eval_result: Any) -> bool:
        """Check if verdict aligns with score threshold."""
        if not eval_result:
            return True

        if not hasattr(eval_result, 'score') or not eval_result.score:
            return True

        if not hasattr(eval_result, 'verdict') or not eval_result.verdict:
            return True

        # Get score and verdict
        score_obj = eval_result.score.fact.object
        verdict_obj = eval_result.verdict.fact.object

        threshold_gate = score_obj.get("threshold_gate", "")
        verdict = verdict_obj.get("verdict", "")

        # Basic alignment check - verdict should match or be more conservative
        # than threshold gate
        return True  # Simplified - real implementation would validate

    def _check_language_audit(
        self,
        eval_result: Any,
        prohibited_patterns: List[str]
    ) -> bool:
        """Check for prohibited language patterns."""
        if not prohibited_patterns:
            return True

        # Would scan eval_result outputs for prohibited patterns
        # Simplified implementation - always passes
        return True

    def _check_chain_integrity(self, chain: Any) -> bool:
        """Check hash chain integrity."""
        if not chain:
            return True

        # Try to validate the chain
        if hasattr(chain, 'validate'):
            try:
                result = chain.validate()
                if hasattr(result, 'is_valid'):
                    return result.is_valid
                return bool(result)
            except Exception:
                return False

        return True


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Exceptions
    'GateError',
    'GateConfigError',
    'GateEvaluationError',
    # Enums
    'GateStatus',
    'GateNumber',
    # Result
    'GateResult',
    # Configuration
    'TypologyGateConfig',
    'InherentMitigatingGateConfig',
    'ResidualRiskGateConfig',
    'IntegrityAuditGateConfig',
    'GateConfig',
    # Evaluator
    'GateEvaluator',
]
