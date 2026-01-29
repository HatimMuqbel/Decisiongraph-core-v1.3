"""
DecisionGraph 6-Layer Decision Taxonomy

This module implements the constitutional decision architecture that separates:
- Facts from opinions
- Obligations from risk indicators
- Indicators from typologies
- Suspicion from everything else

The 6 layers are:
1. FACTS - Immutable, provable data points
2. OBLIGATIONS - Binary legal requirements (PEP EDD, reporting thresholds)
3. INDICATORS - Weak signals that require corroboration
4. TYPOLOGIES - Narrative risk patterns (multiple indicators + temporal)
5. MITIGATIONS - Evidence-backed risk reductions
6. SUSPICION - Reasonable grounds for ML/TF concern (requires intent/deception/pattern)

Key Principle: Escalation requires Layer 6 activation.
Status alone (PEP, foreign, high-risk country) is NEVER sufficient for suspicion.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Set, Any
from decimal import Decimal


class DecisionLayer(Enum):
    """The 6 layers of the decision taxonomy."""
    FACTS = "L1_FACTS"
    OBLIGATIONS = "L2_OBLIGATIONS"
    INDICATORS = "L3_INDICATORS"
    TYPOLOGIES = "L4_TYPOLOGIES"
    MITIGATIONS = "L5_MITIGATIONS"
    SUSPICION = "L6_SUSPICION"


class ObligationType(Enum):
    """Types of regulatory obligations (Layer 2)."""
    EDD_REQUIRED = "edd_required"           # Enhanced Due Diligence
    REPORTING_THRESHOLD = "reporting"        # LCTR, EFT reports
    SANCTIONS_SCREENING = "sanctions"        # Sanctions check required
    PEP_SCREENING = "pep_screening"          # PEP identification
    DOCUMENTATION = "documentation"          # KYC documentation


class IndicatorStrength(Enum):
    """Strength of risk indicators (Layer 3)."""
    WEAK = "weak"           # Requires 3+ corroborating indicators
    MODERATE = "moderate"   # Requires 2+ corroborating indicators
    STRONG = "strong"       # Can contribute to typology with 1 other


class TypologyCategory(Enum):
    """Categories of ML/TF typologies (Layer 4)."""
    STRUCTURING = "structuring"
    LAYERING = "layering"
    INTEGRATION = "integration"
    TRADE_BASED = "trade_based"
    PROFESSIONAL_ABUSE = "professional_abuse"  # Lawyers, accountants
    PEP_CORRUPTION = "pep_corruption"
    TAX_EVASION = "tax_evasion"
    SANCTIONS_EVASION = "sanctions_evasion"
    NONE = "none"


class SuspicionBasis(Enum):
    """Basis for suspicion (Layer 6) - requires at least one."""
    INTENT = "intent"               # Evidence of deliberate concealment
    DECEPTION = "deception"         # False statements, forged docs
    PATTERN = "pattern"             # Repeated suspicious behavior
    TYPOLOGY_MATCH = "typology"     # Confirmed typology survives mitigation
    HARD_STOP = "hard_stop"         # Sanctions hit, false docs, refusal


class VerdictCategory(Enum):
    """Verdict categories based on layer activation."""
    CLEAR = "CLEAR"                         # No obligations, no indicators
    OBLIGATION_ONLY = "OBLIGATION_REVIEW"   # L2 only - EDD/reporting, no suspicion
    INDICATOR_REVIEW = "INDICATOR_REVIEW"   # L3 signals need analyst triage
    TYPOLOGY_REVIEW = "TYPOLOGY_REVIEW"     # L4 pattern forming, senior review
    SUSPICION_ESCALATE = "SUSPICION_ESCALATE"  # L6 activated - compliance/STR


# =============================================================================
# SIGNAL CLASSIFICATION
# =============================================================================

# Layer 2: Obligations (binary, non-negotiable)
OBLIGATION_SIGNALS: Dict[str, ObligationType] = {
    # PEP obligations
    "PEP_FOREIGN": ObligationType.EDD_REQUIRED,
    "PEP_DOMESTIC": ObligationType.EDD_REQUIRED,
    "PEP_HIO": ObligationType.EDD_REQUIRED,
    "PEP_FAMILY_ASSOCIATE": ObligationType.EDD_REQUIRED,
    # Reporting thresholds
    "TXN_LARGE_CASH": ObligationType.REPORTING_THRESHOLD,
    # Sanctions
    "SCREEN_SANCTIONS_HIT": ObligationType.SANCTIONS_SCREENING,
    "GEO_SANCTIONED_COUNTRY": ObligationType.SANCTIONS_SCREENING,
}

# Layer 3: Indicators (weak signals, require corroboration)
INDICATOR_SIGNALS: Dict[str, IndicatorStrength] = {
    # Transaction indicators
    "TXN_JUST_BELOW_THRESHOLD": IndicatorStrength.MODERATE,
    "TXN_RAPID_MOVEMENT": IndicatorStrength.WEAK,
    "TXN_ROUND_AMOUNT": IndicatorStrength.WEAK,
    "TXN_CRYPTO": IndicatorStrength.WEAK,
    "TXN_UNUSUAL_PATTERN": IndicatorStrength.MODERATE,
    # Geographic indicators
    "GEO_HIGH_RISK_COUNTRY": IndicatorStrength.WEAK,
    "GEO_TAX_HAVEN": IndicatorStrength.WEAK,
    # Structuring indicators
    "STRUCT_CASH_MULTIPLE": IndicatorStrength.MODERATE,
    "STRUCT_SMURFING": IndicatorStrength.STRONG,
    # Screening indicators
    "SCREEN_ADVERSE_MEDIA": IndicatorStrength.MODERATE,
    # CDD indicators
    "CDD_INCOMPLETE_ID": IndicatorStrength.MODERATE,
    "CDD_UBO_UNKNOWN": IndicatorStrength.MODERATE,
    "CDD_SHELL_COMPANY": IndicatorStrength.STRONG,
    "CDD_SOW_UNDOCUMENTED": IndicatorStrength.MODERATE,
    "CDD_HIGH_RISK_INDUSTRY": IndicatorStrength.WEAK,
}

# Typology detection rules (Layer 4)
TYPOLOGY_RULES: Dict[TypologyCategory, Set[str]] = {
    TypologyCategory.STRUCTURING: {
        "TXN_JUST_BELOW_THRESHOLD", "STRUCT_CASH_MULTIPLE", "STRUCT_SMURFING"
    },
    TypologyCategory.PROFESSIONAL_ABUSE: {
        "TXN_UNUSUAL_PATTERN", "CDD_SHELL_COMPANY", "GEO_TAX_HAVEN"
    },
    TypologyCategory.PEP_CORRUPTION: {
        "PEP_FOREIGN", "TXN_UNUSUAL_PATTERN", "CDD_SOW_UNDOCUMENTED"
    },
}


@dataclass
class LayerClassification:
    """Classification of a signal into the taxonomy layers."""
    signal_code: str
    layer: DecisionLayer
    obligation_type: Optional[ObligationType] = None
    indicator_strength: Optional[IndicatorStrength] = None
    description: str = ""


@dataclass
class TypologyAssessment:
    """Assessment of whether a typology is forming."""
    typology: TypologyCategory
    matching_signals: List[str]
    confidence: float  # 0-1
    is_forming: bool
    description: str = ""


@dataclass
class SuspicionAssessment:
    """Assessment of Layer 6 - whether suspicion is warranted."""
    is_activated: bool
    basis: Optional[SuspicionBasis] = None
    reasoning: str = ""
    supporting_evidence: List[str] = field(default_factory=list)


@dataclass
class TaxonomyResult:
    """Complete taxonomy analysis result."""
    # Layer classifications
    facts: List[str] = field(default_factory=list)
    obligations: List[LayerClassification] = field(default_factory=list)
    indicators: List[LayerClassification] = field(default_factory=list)
    typologies: List[TypologyAssessment] = field(default_factory=list)
    mitigations: List[str] = field(default_factory=list)
    suspicion: Optional[SuspicionAssessment] = None

    # Derived verdict
    verdict_category: VerdictCategory = VerdictCategory.CLEAR
    verdict_reasoning: str = ""

    # Key metrics
    obligation_count: int = 0
    indicator_count: int = 0
    indicator_strength_sum: float = 0.0
    typology_match: bool = False
    suspicion_activated: bool = False


class TaxonomyClassifier:
    """
    Classifies signals into the 6-layer decision taxonomy.

    This is the constitutional core of the decision system.
    """

    def __init__(self):
        self.obligation_signals = OBLIGATION_SIGNALS
        self.indicator_signals = INDICATOR_SIGNALS
        self.typology_rules = TYPOLOGY_RULES

    def classify_signal(self, signal_code: str) -> LayerClassification:
        """Classify a single signal into the taxonomy."""
        # Check if it's an obligation
        if signal_code in self.obligation_signals:
            return LayerClassification(
                signal_code=signal_code,
                layer=DecisionLayer.OBLIGATIONS,
                obligation_type=self.obligation_signals[signal_code],
                description=f"Regulatory obligation: {self.obligation_signals[signal_code].value}"
            )

        # Check if it's an indicator
        if signal_code in self.indicator_signals:
            return LayerClassification(
                signal_code=signal_code,
                layer=DecisionLayer.INDICATORS,
                indicator_strength=self.indicator_signals[signal_code],
                description=f"Risk indicator ({self.indicator_signals[signal_code].value})"
            )

        # Default: treat as weak indicator
        return LayerClassification(
            signal_code=signal_code,
            layer=DecisionLayer.INDICATORS,
            indicator_strength=IndicatorStrength.WEAK,
            description="Unclassified signal (treated as weak indicator)"
        )

    def assess_typologies(self, signal_codes: List[str]) -> List[TypologyAssessment]:
        """Assess whether any ML/TF typologies are forming."""
        assessments = []
        signal_set = set(signal_codes)

        for typology, required_signals in self.typology_rules.items():
            matching = signal_set.intersection(required_signals)
            match_ratio = len(matching) / len(required_signals) if required_signals else 0

            # Typology requires at least 2 matching signals AND >50% match
            is_forming = len(matching) >= 2 and match_ratio >= 0.5

            if matching:  # Only report if any signals match
                assessments.append(TypologyAssessment(
                    typology=typology,
                    matching_signals=list(matching),
                    confidence=match_ratio,
                    is_forming=is_forming,
                    description=f"{len(matching)}/{len(required_signals)} signals match {typology.value}"
                ))

        return assessments

    def assess_suspicion(
        self,
        typologies: List[TypologyAssessment],
        has_hard_stop: bool = False,
        has_deception: bool = False,
        has_intent_evidence: bool = False,
        mitigations_applied: int = 0
    ) -> SuspicionAssessment:
        """
        Assess whether Layer 6 (Suspicion) should be activated.

        Key principle: Status alone is NEVER sufficient.
        Suspicion requires intent, deception, pattern, or hard stop.
        """
        # Hard stops always activate suspicion
        if has_hard_stop:
            return SuspicionAssessment(
                is_activated=True,
                basis=SuspicionBasis.HARD_STOP,
                reasoning="Hard stop condition detected (sanctions hit, false documents, or refusal)",
                supporting_evidence=["hard_stop_condition"]
            )

        # Deception activates suspicion
        if has_deception:
            return SuspicionAssessment(
                is_activated=True,
                basis=SuspicionBasis.DECEPTION,
                reasoning="Evidence of deception detected (false statements or forged documents)",
                supporting_evidence=["deception_evidence"]
            )

        # Intent evidence activates suspicion
        if has_intent_evidence:
            return SuspicionAssessment(
                is_activated=True,
                basis=SuspicionBasis.INTENT,
                reasoning="Evidence of deliberate concealment or intent to circumvent controls",
                supporting_evidence=["intent_evidence"]
            )

        # Typology match that survives mitigation
        forming_typologies = [t for t in typologies if t.is_forming]
        if forming_typologies and mitigations_applied == 0:
            strongest = max(forming_typologies, key=lambda t: t.confidence)
            return SuspicionAssessment(
                is_activated=True,
                basis=SuspicionBasis.TYPOLOGY_MATCH,
                reasoning=f"Typology {strongest.typology.value} detected without mitigating factors",
                supporting_evidence=strongest.matching_signals
            )

        # Mitigations reduce typology concern
        if forming_typologies and mitigations_applied > 0:
            return SuspicionAssessment(
                is_activated=False,
                reasoning=f"Typology indicators present but mitigated by {mitigations_applied} factors",
                supporting_evidence=[]
            )

        # No suspicion
        return SuspicionAssessment(
            is_activated=False,
            reasoning="No basis for suspicion identified (status alone is insufficient)",
            supporting_evidence=[]
        )

    def determine_verdict(self, result: TaxonomyResult) -> VerdictCategory:
        """
        Determine the verdict category based on layer activation.

        Key principle: Escalation requires Layer 6 activation.
        """
        # Layer 6 activated -> Suspicion escalation
        if result.suspicion_activated:
            return VerdictCategory.SUSPICION_ESCALATE

        # Layer 4 typology forming -> Senior review
        if result.typology_match:
            return VerdictCategory.TYPOLOGY_REVIEW

        # Layer 3 indicators present -> Analyst triage
        if result.indicator_count >= 3 or result.indicator_strength_sum >= 1.5:
            return VerdictCategory.INDICATOR_REVIEW

        # Layer 2 obligations only -> Obligation review (EDD, reporting)
        if result.obligation_count > 0:
            return VerdictCategory.OBLIGATION_ONLY

        # Nothing significant -> Clear
        return VerdictCategory.CLEAR

    def analyze(
        self,
        signal_codes: List[str],
        mitigation_codes: List[str] = None,
        has_hard_stop: bool = False,
        has_deception: bool = False,
        has_intent_evidence: bool = False
    ) -> TaxonomyResult:
        """
        Perform complete taxonomy analysis.

        This is the main entry point for classifying a case.
        """
        mitigation_codes = mitigation_codes or []
        result = TaxonomyResult()

        # Classify each signal
        for code in signal_codes:
            classification = self.classify_signal(code)

            if classification.layer == DecisionLayer.OBLIGATIONS:
                result.obligations.append(classification)
                result.obligation_count += 1
            elif classification.layer == DecisionLayer.INDICATORS:
                result.indicators.append(classification)
                result.indicator_count += 1
                # Sum indicator strengths
                strength_map = {
                    IndicatorStrength.WEAK: 0.25,
                    IndicatorStrength.MODERATE: 0.5,
                    IndicatorStrength.STRONG: 1.0
                }
                if classification.indicator_strength:
                    result.indicator_strength_sum += strength_map.get(
                        classification.indicator_strength, 0.25
                    )

        # Assess typologies
        result.typologies = self.assess_typologies(signal_codes)
        result.typology_match = any(t.is_forming for t in result.typologies)

        # Record mitigations
        result.mitigations = mitigation_codes

        # Assess suspicion (Layer 6)
        result.suspicion = self.assess_suspicion(
            typologies=result.typologies,
            has_hard_stop=has_hard_stop,
            has_deception=has_deception,
            has_intent_evidence=has_intent_evidence,
            mitigations_applied=len(mitigation_codes)
        )
        result.suspicion_activated = result.suspicion.is_activated

        # Determine verdict
        result.verdict_category = self.determine_verdict(result)

        # Build reasoning
        result.verdict_reasoning = self._build_reasoning(result)

        return result

    def _build_reasoning(self, result: TaxonomyResult) -> str:
        """Build human-readable reasoning for the verdict."""
        parts = []

        if result.obligation_count > 0:
            parts.append(f"L2: {result.obligation_count} regulatory obligation(s) triggered")

        if result.indicator_count > 0:
            parts.append(f"L3: {result.indicator_count} indicator(s) detected (strength: {result.indicator_strength_sum:.2f})")

        if result.typology_match:
            forming = [t for t in result.typologies if t.is_forming]
            names = [t.typology.value for t in forming]
            parts.append(f"L4: Typology forming ({', '.join(names)})")

        if result.suspicion_activated:
            parts.append(f"L6: SUSPICION ACTIVATED ({result.suspicion.basis.value})")
        else:
            parts.append("L6: No suspicion (status alone is insufficient)")

        if result.mitigations:
            parts.append(f"L5: {len(result.mitigations)} mitigation(s) applied")

        return "; ".join(parts)


# =============================================================================
# VERDICT MAPPING
# =============================================================================

# Map taxonomy verdicts to existing verdict codes for compatibility
TAXONOMY_TO_VERDICT: Dict[VerdictCategory, str] = {
    VerdictCategory.CLEAR: "CLEAR_AND_CLOSE",
    VerdictCategory.OBLIGATION_ONLY: "OBLIGATION_REVIEW",
    VerdictCategory.INDICATOR_REVIEW: "ANALYST_REVIEW",
    VerdictCategory.TYPOLOGY_REVIEW: "SENIOR_REVIEW",
    VerdictCategory.SUSPICION_ESCALATE: "STR_CONSIDERATION",
}

# Map to review tiers
TAXONOMY_TO_TIER: Dict[VerdictCategory, int] = {
    VerdictCategory.CLEAR: 0,
    VerdictCategory.OBLIGATION_ONLY: 1,
    VerdictCategory.INDICATOR_REVIEW: 1,
    VerdictCategory.TYPOLOGY_REVIEW: 2,
    VerdictCategory.SUSPICION_ESCALATE: 3,
}

# Map to auto-archive permission
TAXONOMY_AUTO_ARCHIVE: Dict[VerdictCategory, bool] = {
    VerdictCategory.CLEAR: True,
    VerdictCategory.OBLIGATION_ONLY: False,  # EDD must be completed
    VerdictCategory.INDICATOR_REVIEW: False,
    VerdictCategory.TYPOLOGY_REVIEW: False,
    VerdictCategory.SUSPICION_ESCALATE: False,
}


def get_taxonomy_verdict(
    signal_codes: List[str],
    mitigation_codes: List[str] = None,
    has_hard_stop: bool = False
) -> tuple:
    """
    Convenience function to get taxonomy-based verdict.

    Returns:
        (verdict_code, tier, auto_archive, taxonomy_result)
    """
    classifier = TaxonomyClassifier()
    result = classifier.analyze(
        signal_codes=signal_codes,
        mitigation_codes=mitigation_codes,
        has_hard_stop=has_hard_stop
    )

    verdict_code = TAXONOMY_TO_VERDICT[result.verdict_category]
    tier = TAXONOMY_TO_TIER[result.verdict_category]
    auto_archive = TAXONOMY_AUTO_ARCHIVE[result.verdict_category]

    return verdict_code, tier, auto_archive, result
