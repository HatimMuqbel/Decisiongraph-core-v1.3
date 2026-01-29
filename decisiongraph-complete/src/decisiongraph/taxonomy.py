"""
DecisionGraph 6-Layer Decision Taxonomy (v2.1 - Fixed)

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

CRITICAL RULES (v2.1 fixes):
1. Hard stops ONLY come from Layer 1 facts (confirmed sanctions match, false docs, refusal)
2. Cash signals NEVER apply to wire transfers (instrument exclusivity)
3. FORMING typologies do NOT trigger suspicion (must be ESTABLISHED or CONFIRMED)
4. Obligations (L2) can NEVER activate suspicion (L6)
5. Suspicion requires evidence of intent, deception, or sustained pattern
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


class TypologyMaturity(Enum):
    """
    Maturity states for typologies (FIX #3).

    CRITICAL: Only ESTABLISHED or CONFIRMED typologies can trigger suspicion.
    FORMING means "observe only" - it does NOT trigger escalation.
    """
    FORMING = "forming"         # Hypothesis, early signals - OBSERVE ONLY
    ESTABLISHED = "established" # Pattern confirmed - eligible for suspicion
    CONFIRMED = "confirmed"     # Multiple confirmations - escalation warranted


class InstrumentType(Enum):
    """
    Transaction instrument types (FIX #2).

    CRITICAL: Cash rules NEVER apply to wires. This is instrument exclusivity.
    """
    CASH = "cash"
    WIRE = "wire"
    ACH = "ach"
    CHECK = "check"
    CRYPTO = "crypto"
    CARD = "card"
    UNKNOWN = "unknown"


class HardStopType(Enum):
    """
    Hard stop conditions (FIX #1).

    CRITICAL: Hard stops ONLY come from Layer 1 FACTS, not signals or obligations.
    A hard stop requires:
    - CONFIRMED sanctions match (not just screening occurred)
    - FALSE or FORGED documentation
    - REFUSAL to provide required information
    - LEGAL prohibition to proceed
    """
    SANCTIONS_CONFIRMED = "sanctions_confirmed"  # Actual match, not screening
    FALSE_DOCUMENTATION = "false_docs"           # Forged, fraudulent docs
    REFUSAL = "refusal"                          # Customer refused to comply
    LEGAL_PROHIBITION = "legal_prohibition"      # Cannot legally proceed


class SuspicionBasis(Enum):
    """Basis for suspicion (Layer 6) - requires at least one."""
    INTENT = "intent"               # Evidence of deliberate concealment
    DECEPTION = "deception"         # False statements, forged docs
    PATTERN = "pattern"             # Repeated suspicious behavior
    TYPOLOGY_ESTABLISHED = "typology_established"  # ESTABLISHED (not forming) typology
    HARD_STOP = "hard_stop"         # Confirmed hard stop from Layer 1


class VerdictCategory(Enum):
    """Verdict categories based on layer activation."""
    CLEAR = "CLEAR"                         # No obligations, no indicators
    OBLIGATION_ONLY = "OBLIGATION_REVIEW"   # L2 only - EDD/reporting, no suspicion
    INDICATOR_REVIEW = "INDICATOR_REVIEW"   # L3 signals need analyst triage
    TYPOLOGY_FORMING = "TYPOLOGY_FORMING"   # L4 pattern forming - OBSERVE, not escalate
    TYPOLOGY_REVIEW = "TYPOLOGY_REVIEW"     # L4 ESTABLISHED pattern - senior review
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
    # Reporting thresholds (instrument-specific)
    "TXN_LARGE_CASH": ObligationType.REPORTING_THRESHOLD,
    "TXN_LARGE_EFT": ObligationType.REPORTING_THRESHOLD,
    # Sanctions screening obligation (NOT a hard stop by itself!)
    "GEO_SANCTIONED_COUNTRY": ObligationType.SANCTIONS_SCREENING,
}

# Layer 3: Indicators (weak signals, require corroboration)
INDICATOR_SIGNALS: Dict[str, IndicatorStrength] = {
    # Transaction indicators (instrument-agnostic)
    "TXN_JUST_BELOW_THRESHOLD": IndicatorStrength.MODERATE,
    "TXN_RAPID_MOVEMENT": IndicatorStrength.WEAK,
    "TXN_ROUND_AMOUNT": IndicatorStrength.WEAK,
    "TXN_CRYPTO": IndicatorStrength.WEAK,
    "TXN_UNUSUAL_PATTERN": IndicatorStrength.MODERATE,
    # Geographic indicators
    "GEO_HIGH_RISK_COUNTRY": IndicatorStrength.WEAK,
    "GEO_TAX_HAVEN": IndicatorStrength.WEAK,
    # Structuring indicators (CASH-ONLY - excluded from wires)
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

# Signals that are CASH-ONLY (FIX #2 - instrument exclusivity)
CASH_ONLY_SIGNALS: Set[str] = {
    "TXN_LARGE_CASH",
    "STRUCT_CASH_MULTIPLE",
    "STRUCT_SMURFING",
}

# Signals that indicate a TRUE hard stop (FIX #1)
# NOTE: SCREEN_SANCTIONS_HIT is NOT here - it's just screening, not a confirmed match
HARD_STOP_FACT_SIGNALS: Set[str] = {
    "SANCTIONS_CONFIRMED_MATCH",     # Actual confirmed sanctions match
    "DOC_FALSE_POSITIVE_CONFIRMED",  # False documents confirmed
    "CUSTOMER_REFUSAL",              # Customer refused to provide info
}

# Typology detection rules (Layer 4)
# NOTE: These use ONLY wire-compatible signals
TYPOLOGY_RULES: Dict[TypologyCategory, Set[str]] = {
    TypologyCategory.STRUCTURING: {
        "TXN_JUST_BELOW_THRESHOLD", "STRUCT_CASH_MULTIPLE", "STRUCT_SMURFING"
    },
    TypologyCategory.PROFESSIONAL_ABUSE: {
        "TXN_UNUSUAL_PATTERN", "CDD_SHELL_COMPANY", "GEO_TAX_HAVEN"
    },
    TypologyCategory.PEP_CORRUPTION: {
        "TXN_UNUSUAL_PATTERN", "CDD_SOW_UNDOCUMENTED", "SCREEN_ADVERSE_MEDIA"
    },
}

# Typology rules by instrument (wire-safe typologies)
WIRE_TYPOLOGY_RULES: Dict[TypologyCategory, Set[str]] = {
    # Structuring on wires requires different signals (no cash)
    TypologyCategory.LAYERING: {
        "TXN_RAPID_MOVEMENT", "TXN_UNUSUAL_PATTERN", "GEO_TAX_HAVEN"
    },
    TypologyCategory.PROFESSIONAL_ABUSE: {
        "TXN_UNUSUAL_PATTERN", "CDD_SHELL_COMPANY", "GEO_TAX_HAVEN"
    },
    TypologyCategory.PEP_CORRUPTION: {
        "TXN_UNUSUAL_PATTERN", "CDD_SOW_UNDOCUMENTED", "SCREEN_ADVERSE_MEDIA"
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
    excluded_reason: Optional[str] = None  # If signal was excluded (e.g., cash on wire)


@dataclass
class TypologyAssessment:
    """Assessment of whether a typology is forming."""
    typology: TypologyCategory
    matching_signals: List[str]
    confidence: float  # 0-1
    maturity: TypologyMaturity  # FIX #3: Maturity state
    description: str = ""

    @property
    def is_forming(self) -> bool:
        """Backward compatibility - but forming does NOT trigger suspicion."""
        return self.maturity in (TypologyMaturity.FORMING, TypologyMaturity.ESTABLISHED, TypologyMaturity.CONFIRMED)

    @property
    def is_suspicion_eligible(self) -> bool:
        """Only ESTABLISHED or CONFIRMED typologies can trigger suspicion."""
        return self.maturity in (TypologyMaturity.ESTABLISHED, TypologyMaturity.CONFIRMED)


@dataclass
class HardStopAssessment:
    """
    Assessment of hard stop conditions (FIX #1).

    Hard stops ONLY come from Layer 1 facts:
    - Confirmed sanctions match (not just screening)
    - False/forged documentation
    - Customer refusal
    """
    has_hard_stop: bool
    hard_stop_type: Optional[HardStopType] = None
    reasoning: str = ""
    fact_evidence: List[str] = field(default_factory=list)


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
    excluded_signals: List[LayerClassification] = field(default_factory=list)  # Signals excluded by instrument
    typologies: List[TypologyAssessment] = field(default_factory=list)
    mitigations: List[str] = field(default_factory=list)
    hard_stop: Optional[HardStopAssessment] = None
    suspicion: Optional[SuspicionAssessment] = None

    # Derived verdict
    verdict_category: VerdictCategory = VerdictCategory.CLEAR
    verdict_reasoning: str = ""

    # Key metrics
    obligation_count: int = 0
    indicator_count: int = 0
    indicator_strength_sum: float = 0.0
    typology_forming: bool = False      # Any typology forming (for observation)
    typology_established: bool = False  # ESTABLISHED typology (for suspicion)
    suspicion_activated: bool = False
    instrument_type: InstrumentType = InstrumentType.UNKNOWN

    # Backward compatibility
    @property
    def typology_match(self) -> bool:
        """Backward compat - but FORMING does not trigger suspicion."""
        return self.typology_forming


class TaxonomyClassifier:
    """
    Classifies signals into the 6-layer decision taxonomy.

    This is the constitutional core of the decision system.

    v2.1 FIXES:
    1. Hard stops only from Layer 1 facts
    2. Instrument exclusivity (cash signals don't apply to wires)
    3. Typology maturity (FORMING ≠ suspicion)
    """

    def __init__(self):
        self.obligation_signals = OBLIGATION_SIGNALS
        self.indicator_signals = INDICATOR_SIGNALS
        self.typology_rules = TYPOLOGY_RULES
        self.wire_typology_rules = WIRE_TYPOLOGY_RULES
        self.cash_only_signals = CASH_ONLY_SIGNALS
        self.hard_stop_signals = HARD_STOP_FACT_SIGNALS

    def detect_instrument_type(self, signal_codes: List[str], instrument_hint: Optional[str] = None) -> InstrumentType:
        """Detect transaction instrument type."""
        if instrument_hint:
            hint_lower = instrument_hint.lower()
            if 'wire' in hint_lower or 'swift' in hint_lower or 'eft' in hint_lower:
                return InstrumentType.WIRE
            if 'cash' in hint_lower:
                return InstrumentType.CASH
            if 'crypto' in hint_lower:
                return InstrumentType.CRYPTO

        # Infer from signals
        if any('CASH' in code for code in signal_codes):
            return InstrumentType.CASH
        if any('WIRE' in code or 'EFT' in code for code in signal_codes):
            return InstrumentType.WIRE
        if any('CRYPTO' in code for code in signal_codes):
            return InstrumentType.CRYPTO

        return InstrumentType.UNKNOWN

    def filter_signals_by_instrument(
        self,
        signal_codes: List[str],
        instrument: InstrumentType
    ) -> tuple:
        """
        FIX #2: Filter signals based on instrument type.

        Cash signals NEVER apply to wires. This is instrument exclusivity.
        """
        valid_signals = []
        excluded_signals = []

        for code in signal_codes:
            if code in self.cash_only_signals and instrument == InstrumentType.WIRE:
                excluded_signals.append((code, "Cash signal excluded from wire transaction"))
            else:
                valid_signals.append(code)

        return valid_signals, excluded_signals

    def assess_hard_stop(self, signal_codes: List[str], facts: Dict[str, Any] = None) -> HardStopAssessment:
        """
        FIX #1: Hard stops ONLY from Layer 1 facts.

        CRITICAL: The presence of SCREEN_SANCTIONS_HIT does NOT mean there's a hard stop.
        That signal means "screening occurred" - the disposition determines outcome.

        Hard stops require:
        - sanctions_result = "MATCH" (confirmed match, not just screening)
        - document_status = "FORGED" or "FALSE"
        - customer_response = "REFUSED"
        """
        facts = facts or {}

        # Check for confirmed sanctions match (not just screening)
        if facts.get("sanctions_result") == "MATCH":
            return HardStopAssessment(
                has_hard_stop=True,
                hard_stop_type=HardStopType.SANCTIONS_CONFIRMED,
                reasoning="Confirmed sanctions match - immediate escalation required",
                fact_evidence=["sanctions_result=MATCH"]
            )

        # Check for false documents
        if facts.get("document_status") in ("FORGED", "FALSE", "FRAUDULENT"):
            return HardStopAssessment(
                has_hard_stop=True,
                hard_stop_type=HardStopType.FALSE_DOCUMENTATION,
                reasoning="False or forged documentation detected",
                fact_evidence=[f"document_status={facts.get('document_status')}"]
            )

        # Check for customer refusal
        if facts.get("customer_response") == "REFUSED":
            return HardStopAssessment(
                has_hard_stop=True,
                hard_stop_type=HardStopType.REFUSAL,
                reasoning="Customer refused to provide required information",
                fact_evidence=["customer_response=REFUSED"]
            )

        # Check for explicit hard stop signals (rare, from fact layer)
        hard_stop_found = set(signal_codes).intersection(self.hard_stop_signals)
        if hard_stop_found:
            return HardStopAssessment(
                has_hard_stop=True,
                hard_stop_type=HardStopType.SANCTIONS_CONFIRMED,
                reasoning=f"Hard stop signal detected: {', '.join(hard_stop_found)}",
                fact_evidence=list(hard_stop_found)
            )

        # NO HARD STOP - screening signals alone do not constitute hard stops
        return HardStopAssessment(
            has_hard_stop=False,
            reasoning="No hard stop conditions present (screening != confirmed match)"
        )

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

    def assess_typologies(
        self,
        signal_codes: List[str],
        instrument: InstrumentType = InstrumentType.UNKNOWN
    ) -> List[TypologyAssessment]:
        """
        FIX #3: Assess typologies with maturity states.

        CRITICAL:
        - FORMING = 50-74% match, observe only, NO suspicion
        - ESTABLISHED = 75-99% match, eligible for suspicion
        - CONFIRMED = 100% match, escalation warranted
        """
        assessments = []
        signal_set = set(signal_codes)

        # Use instrument-appropriate rules
        if instrument == InstrumentType.WIRE:
            rules = self.wire_typology_rules
        else:
            rules = self.typology_rules

        for typology, required_signals in rules.items():
            matching = signal_set.intersection(required_signals)
            match_ratio = len(matching) / len(required_signals) if required_signals else 0

            # Determine maturity based on match ratio
            if match_ratio >= 1.0:
                maturity = TypologyMaturity.CONFIRMED
            elif match_ratio >= 0.75:
                maturity = TypologyMaturity.ESTABLISHED
            elif match_ratio >= 0.5 and len(matching) >= 2:
                maturity = TypologyMaturity.FORMING
            else:
                continue  # Not enough to even form

            if matching:
                assessments.append(TypologyAssessment(
                    typology=typology,
                    matching_signals=list(matching),
                    confidence=match_ratio,
                    maturity=maturity,
                    description=f"{len(matching)}/{len(required_signals)} signals = {maturity.value}"
                ))

        return assessments

    def assess_suspicion(
        self,
        typologies: List[TypologyAssessment],
        hard_stop: HardStopAssessment,
        has_deception: bool = False,
        has_intent_evidence: bool = False,
        mitigations_applied: int = 0
    ) -> SuspicionAssessment:
        """
        Assess whether Layer 6 (Suspicion) should be activated.

        CRITICAL RULES:
        1. Hard stops from Layer 1 facts activate suspicion
        2. FORMING typologies do NOT activate suspicion
        3. Only ESTABLISHED/CONFIRMED typologies can activate suspicion
        4. Mitigations can reduce even established typologies
        5. Status alone (PEP, foreign, geography) NEVER activates suspicion
        """
        # FIX #1: Only FACT-level hard stops activate suspicion
        if hard_stop.has_hard_stop:
            return SuspicionAssessment(
                is_activated=True,
                basis=SuspicionBasis.HARD_STOP,
                reasoning=hard_stop.reasoning,
                supporting_evidence=hard_stop.fact_evidence
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

        # FIX #3: Only ESTABLISHED or CONFIRMED typologies can trigger suspicion
        suspicion_eligible = [t for t in typologies if t.is_suspicion_eligible]

        if suspicion_eligible and mitigations_applied == 0:
            strongest = max(suspicion_eligible, key=lambda t: t.confidence)
            return SuspicionAssessment(
                is_activated=True,
                basis=SuspicionBasis.TYPOLOGY_ESTABLISHED,
                reasoning=f"ESTABLISHED typology {strongest.typology.value} detected without mitigating factors",
                supporting_evidence=strongest.matching_signals
            )

        # Mitigations reduce established typology concern
        if suspicion_eligible and mitigations_applied > 0:
            return SuspicionAssessment(
                is_activated=False,
                reasoning=f"Established typology present but mitigated by {mitigations_applied} factors",
                supporting_evidence=[]
            )

        # FORMING typologies - observe only, NO suspicion
        forming_only = [t for t in typologies if t.maturity == TypologyMaturity.FORMING]
        if forming_only:
            return SuspicionAssessment(
                is_activated=False,
                reasoning=f"Typology FORMING (observe only) - not sufficient for suspicion. {len(forming_only)} pattern(s) under observation.",
                supporting_evidence=[]
            )

        # No suspicion
        return SuspicionAssessment(
            is_activated=False,
            reasoning="No basis for suspicion (status/obligations alone are insufficient)",
            supporting_evidence=[]
        )

    def determine_verdict(self, result: TaxonomyResult) -> VerdictCategory:
        """
        Determine the verdict category based on layer activation.

        Key principle: Escalation requires Layer 6 activation.
        FORMING typologies trigger observation, not escalation.
        Mitigated ESTABLISHED typologies downgrade to OBLIGATION_ONLY.
        """
        # Layer 6 activated -> Suspicion escalation
        if result.suspicion_activated:
            return VerdictCategory.SUSPICION_ESCALATE

        # Layer 4 ESTABLISHED typology - check if mitigated
        if result.typology_established:
            # FIX v2.1.1: If typology was established but mitigations prevented
            # suspicion activation, downgrade to OBLIGATION_ONLY
            if len(result.mitigations) >= 2 and not result.suspicion_activated:
                # Sufficient mitigations resolved the typology concern
                # Downgrade to obligation-only (pass with EDD recorded)
                if result.obligation_count > 0:
                    return VerdictCategory.OBLIGATION_ONLY
            # Unmitigated established typology -> Senior review
            return VerdictCategory.TYPOLOGY_REVIEW

        # Layer 4 FORMING typology -> Observation only (not escalation!)
        if result.typology_forming and not result.typology_established:
            return VerdictCategory.TYPOLOGY_FORMING

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
        facts: Dict[str, Any] = None,
        instrument_hint: Optional[str] = None,
        has_deception: bool = False,
        has_intent_evidence: bool = False,
        # Deprecated - use facts dict instead
        has_hard_stop: bool = False
    ) -> TaxonomyResult:
        """
        Perform complete taxonomy analysis.

        This is the main entry point for classifying a case.

        Args:
            signal_codes: List of signal codes fired
            mitigation_codes: List of mitigation codes applied
            facts: Layer 1 facts dict (for hard stop detection)
            instrument_hint: Transaction instrument type hint (e.g., "wire", "cash")
            has_deception: Evidence of deception exists
            has_intent_evidence: Evidence of intent exists
            has_hard_stop: DEPRECATED - use facts dict with sanctions_result=MATCH
        """
        mitigation_codes = mitigation_codes or []
        facts = facts or {}
        result = TaxonomyResult()

        # Detect instrument type
        result.instrument_type = self.detect_instrument_type(signal_codes, instrument_hint)

        # FIX #2: Filter signals by instrument (cash signals don't apply to wires)
        valid_signals, excluded = self.filter_signals_by_instrument(
            signal_codes, result.instrument_type
        )

        # Record excluded signals
        for code, reason in excluded:
            result.excluded_signals.append(LayerClassification(
                signal_code=code,
                layer=DecisionLayer.INDICATORS,
                excluded_reason=reason
            ))

        # Classify each valid signal
        for code in valid_signals:
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

        # FIX #1: Assess hard stops from FACTS only
        result.hard_stop = self.assess_hard_stop(valid_signals, facts)

        # FIX #3: Assess typologies with maturity states
        result.typologies = self.assess_typologies(valid_signals, result.instrument_type)
        result.typology_forming = any(t.maturity == TypologyMaturity.FORMING for t in result.typologies)
        result.typology_established = any(t.is_suspicion_eligible for t in result.typologies)

        # Record mitigations
        result.mitigations = mitigation_codes

        # Assess suspicion (Layer 6) with all fixes applied
        result.suspicion = self.assess_suspicion(
            typologies=result.typologies,
            hard_stop=result.hard_stop,
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

        if result.excluded_signals:
            parts.append(f"Instrument exclusivity: {len(result.excluded_signals)} signal(s) excluded")

        if result.obligation_count > 0:
            parts.append(f"L2: {result.obligation_count} regulatory obligation(s) - EDD/reporting required, NOT suspicion")

        if result.indicator_count > 0:
            parts.append(f"L3: {result.indicator_count} indicator(s) (strength: {result.indicator_strength_sum:.2f})")

        if result.typology_forming and not result.typology_established:
            forming = [t for t in result.typologies if t.maturity == TypologyMaturity.FORMING]
            names = [t.typology.value for t in forming]
            parts.append(f"L4: Typology FORMING ({', '.join(names)}) - observe only, NOT escalation")

        if result.typology_established:
            established = [t for t in result.typologies if t.is_suspicion_eligible]
            names = [t.typology.value for t in established]
            # Check if mitigations resolved the typology concern
            if len(result.mitigations) >= 2 and not result.suspicion_activated:
                parts.append(f"L4: Typology ESTABLISHED ({', '.join(names)}) - MITIGATED by {len(result.mitigations)} factors")
            else:
                parts.append(f"L4: Typology ESTABLISHED ({', '.join(names)})")

        if result.mitigations:
            parts.append(f"L5: {len(result.mitigations)} mitigation(s) applied")

        if result.suspicion_activated:
            parts.append(f"L6: SUSPICION ACTIVATED ({result.suspicion.basis.value})")
        else:
            parts.append("L6: No suspicion (obligations/forming patterns are insufficient)")

        return "; ".join(parts)


# =============================================================================
# VERDICT MAPPING
# =============================================================================

# Map taxonomy verdicts to existing verdict codes for compatibility
TAXONOMY_TO_VERDICT: Dict[VerdictCategory, str] = {
    VerdictCategory.CLEAR: "CLEAR_AND_CLOSE",
    VerdictCategory.OBLIGATION_ONLY: "PASS_WITH_EDD",  # Pass with EDD recorded
    VerdictCategory.INDICATOR_REVIEW: "ANALYST_REVIEW",
    VerdictCategory.TYPOLOGY_FORMING: "OBSERVE_ENHANCED",  # Enhanced monitoring, not escalation
    VerdictCategory.TYPOLOGY_REVIEW: "SENIOR_REVIEW",
    VerdictCategory.SUSPICION_ESCALATE: "STR_CONSIDERATION",
}

# Map to review tiers
TAXONOMY_TO_TIER: Dict[VerdictCategory, int] = {
    VerdictCategory.CLEAR: 0,
    VerdictCategory.OBLIGATION_ONLY: 0,  # Pass, just record EDD
    VerdictCategory.INDICATOR_REVIEW: 1,
    VerdictCategory.TYPOLOGY_FORMING: 1,  # Monitor, don't escalate
    VerdictCategory.TYPOLOGY_REVIEW: 2,
    VerdictCategory.SUSPICION_ESCALATE: 3,
}

# Map to auto-archive permission
TAXONOMY_AUTO_ARCHIVE: Dict[VerdictCategory, bool] = {
    VerdictCategory.CLEAR: True,
    VerdictCategory.OBLIGATION_ONLY: True,  # Can archive after EDD recorded
    VerdictCategory.INDICATOR_REVIEW: False,
    VerdictCategory.TYPOLOGY_FORMING: False,  # Keep for monitoring
    VerdictCategory.TYPOLOGY_REVIEW: False,
    VerdictCategory.SUSPICION_ESCALATE: False,
}


def get_taxonomy_verdict(
    signal_codes: List[str],
    mitigation_codes: List[str] = None,
    facts: Dict[str, Any] = None,
    instrument_hint: Optional[str] = None,
    has_hard_stop: bool = False  # Deprecated
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
        facts=facts,
        instrument_hint=instrument_hint
    )

    verdict_code = TAXONOMY_TO_VERDICT[result.verdict_category]
    tier = TAXONOMY_TO_TIER[result.verdict_category]
    auto_archive = TAXONOMY_AUTO_ARCHIVE[result.verdict_category]

    return verdict_code, tier, auto_archive, result
