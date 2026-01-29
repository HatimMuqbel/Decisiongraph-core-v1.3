"""
DecisionGraph Rules Module (v2.0)

Deterministic rule evaluation engine that transforms facts into:
- SIGNAL cells (detection triggers)
- MITIGATION cells (risk reducers)
- SCORE cells (computed risk values)
- VERDICT cells (final decisions)

Core Principle: Rules are pure functions. Same inputs always produce same outputs.
No randomness, no external state, no side effects.

The rules engine is the "reasoning layer" of DecisionGraph:
1. Facts are ingested (from external systems or prior cells)
2. Signal rules evaluate facts → produce SIGNAL cells
3. Mitigation rules evaluate facts + signals → produce MITIGATION cells
4. Scoring rules aggregate signals + mitigations → produce SCORE cells
5. Verdict rules evaluate score → produce VERDICT cells

All outputs are deterministic and auditable.

USAGE:
    from decisiongraph.rules import (
        RulesEngine, SignalRule, MitigationRule, ScoringRule, VerdictRule
    )

    # Create engine with rules
    engine = RulesEngine()
    engine.add_signal_rule(SignalRule(...))
    engine.add_mitigation_rule(MitigationRule(...))

    # Evaluate against facts
    results = engine.evaluate(facts, context)
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from .cell import (
    DecisionCell, Header, Fact, LogicAnchor, Evidence, Proof,
    CellType, SourceQuality, NULL_HASH,
    HASH_SCHEME_CANONICAL, get_current_timestamp,
    compute_rule_logic_hash
)
from .pack import Pack, validate_payload
from .canon import score_to_string


# =============================================================================
# EVIDENCE ANCHORING
# =============================================================================

@dataclass
class DetailedEvidenceAnchor:
    """
    Detailed evidence anchor for audit trail.

    Links a mitigation to the specific evidence that supports it.
    This creates a traceable path from decision back to source data.
    """
    field: str           # Data field (e.g., "crypto_source", "tenure_years")
    value: str           # The actual value that matched
    source: str          # Full source path (e.g., "case.customer.tenure_years")
    cell_id: str = ""    # Reference to source fact cell (if available)

    def to_dict(self) -> Dict[str, str]:
        """Serialize to dict for cell payload."""
        d = {
            "field": self.field,
            "value": self.value,
            "source": self.source,
        }
        if self.cell_id:
            d["cell_id"] = self.cell_id
        return d

    @classmethod
    def from_fact(cls, fact: Fact, cell_id: str = "") -> "DetailedEvidenceAnchor":
        """
        Create evidence anchor from a triggering fact.

        Extracts field, value, and source from the fact's structure.
        """
        # Extract field from predicate (e.g., "txn.amount" -> "amount")
        field = fact.predicate.split(".")[-1] if "." in fact.predicate else fact.predicate

        # Extract value - handle different object types
        if isinstance(fact.object, dict):
            # For structured objects, use the first meaningful value or stringify
            value = str(fact.object.get("value", fact.object))
        else:
            value = str(fact.object)

        # Build source path from namespace + predicate
        source = f"{fact.namespace}.{fact.predicate}" if fact.namespace else fact.predicate

        return cls(
            field=field,
            value=value,
            source=source,
            cell_id=cell_id
        )


# =============================================================================
# EXCEPTIONS
# =============================================================================

class RuleError(Exception):
    """Base exception for rule errors."""
    pass


class RuleDefinitionError(RuleError):
    """Raised when rule definition is invalid."""
    pass


class RuleEvaluationError(RuleError):
    """Raised when rule evaluation fails."""
    pass


class ConditionError(RuleError):
    """Raised when condition evaluation fails."""
    pass


# =============================================================================
# HELPER FUNCTIONS (INTERNAL)
# =============================================================================

def _dedupe_facts(facts: List[Fact]) -> List[Fact]:
    """
    Deduplicate facts by identity (since Fact is not hashable).

    Uses object identity to deduplicate.
    """
    seen = set()
    result = []
    for f in facts:
        if id(f) not in seen:
            seen.add(id(f))
            result.append(f)
    return result


# =============================================================================
# SEVERITY LEVELS
# =============================================================================

class Severity(str, Enum):
    """Signal severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def weight(self) -> str:
        """Default weight for severity level (string-encoded)."""
        weights = {
            Severity.LOW: "0.25",
            Severity.MEDIUM: "0.50",
            Severity.HIGH: "0.75",
            Severity.CRITICAL: "1.00",
        }
        return weights[self]


# =============================================================================
# CONDITION MATCHING
# =============================================================================

@dataclass
class FactPattern:
    """
    Pattern for matching facts.

    Supports exact match, prefix match, regex match, and value comparisons.
    """
    namespace: Optional[str] = None      # Exact or prefix match
    namespace_prefix: bool = False       # If True, namespace is prefix match
    subject: Optional[str] = None        # Exact match or regex
    subject_regex: Optional[str] = None  # Regex pattern for subject
    predicate: Optional[str] = None      # Exact match
    predicate_regex: Optional[str] = None  # Regex pattern for predicate
    object_value: Optional[Any] = None   # Exact object match
    object_contains: Optional[str] = None  # Object contains substring
    min_confidence: Optional[float] = None  # Minimum confidence
    source_quality: Optional[SourceQuality] = None  # Required quality

    def matches(self, fact: Fact) -> bool:
        """Check if a fact matches this pattern."""
        # Namespace match
        if self.namespace:
            if self.namespace_prefix:
                if not (fact.namespace == self.namespace or
                        fact.namespace.startswith(self.namespace + ".")):
                    return False
            else:
                if fact.namespace != self.namespace:
                    return False

        # Subject match
        if self.subject and fact.subject != self.subject:
            return False
        if self.subject_regex and not re.match(self.subject_regex, fact.subject):
            return False

        # Predicate match
        if self.predicate and fact.predicate != self.predicate:
            return False
        if self.predicate_regex and not re.match(self.predicate_regex, fact.predicate):
            return False

        # Object match
        if self.object_value is not None:
            if isinstance(fact.object, str):
                if fact.object != self.object_value:
                    return False
            elif isinstance(fact.object, dict):
                # For structured objects, check if object_value is a subset
                if isinstance(self.object_value, dict):
                    for k, v in self.object_value.items():
                        if fact.object.get(k) != v:
                            return False
                else:
                    return False

        if self.object_contains:
            obj_str = str(fact.object) if not isinstance(fact.object, str) else fact.object
            if self.object_contains not in obj_str:
                return False

        # Confidence match
        if self.min_confidence is not None and fact.confidence < self.min_confidence:
            return False

        # Source quality match
        if self.source_quality and fact.source_quality != self.source_quality:
            return False

        return True


@dataclass
class Condition:
    """
    A condition that evaluates against a set of facts.

    Conditions can be:
    - Pattern match (any fact matching pattern)
    - Count threshold (N or more facts match)
    - All match (all specified patterns must have matches)
    - Any match (at least one pattern must have matches)
    - Value comparison (fact object value compared to threshold)
    """
    pattern: Optional[FactPattern] = None
    patterns: Optional[List[FactPattern]] = None  # For all/any match
    match_mode: str = "any"  # "any", "all", "count"
    min_count: int = 1  # For count mode
    # Value extraction and comparison
    extract_path: Optional[str] = None  # JSON path to extract from object (e.g., "amount")
    compare_op: Optional[str] = None  # "gt", "gte", "lt", "lte", "eq", "ne"
    compare_value: Optional[Any] = None

    def evaluate(self, facts: List[Fact]) -> Tuple[bool, List[Fact]]:
        """
        Evaluate condition against facts.

        Returns:
            (matched: bool, matching_facts: List[Fact])
        """
        if self.pattern:
            matching = [f for f in facts if self.pattern.matches(f)]

            # Value comparison if specified
            if self.compare_op and matching:
                matching = self._filter_by_value(matching)

            if self.match_mode == "count":
                return len(matching) >= self.min_count, matching
            else:
                return len(matching) > 0, matching

        elif self.patterns:
            if self.match_mode == "all":
                # All patterns must match at least one fact
                all_matching = []
                for pattern in self.patterns:
                    pattern_matches = [f for f in facts if pattern.matches(f)]
                    if not pattern_matches:
                        return False, []
                    all_matching.extend(pattern_matches)
                # Deduplicate without using set (Fact not hashable)
                return True, _dedupe_facts(all_matching)

            elif self.match_mode == "any":
                # At least one pattern must match
                any_matching = []
                for pattern in self.patterns:
                    pattern_matches = [f for f in facts if pattern.matches(f)]
                    any_matching.extend(pattern_matches)
                return len(any_matching) > 0, _dedupe_facts(any_matching)

        return False, []

    def _filter_by_value(self, facts: List[Fact]) -> List[Fact]:
        """Filter facts by value comparison."""
        result = []
        for fact in facts:
            value = self._extract_value(fact)
            if value is not None and self._compare(value):
                result.append(fact)
        return result

    def _extract_value(self, fact: Fact) -> Optional[Any]:
        """Extract value from fact object using path."""
        obj = fact.object

        # Empty or None extract_path means use the object directly
        if not self.extract_path:
            if isinstance(obj, str):
                # Try to parse as number for simple string values
                try:
                    return Decimal(obj)
                except:
                    return obj
            elif isinstance(obj, (int, float)):
                return Decimal(str(obj))
            return obj

        # Navigate path for dict objects (e.g., "details.amount")
        if isinstance(obj, dict):
            parts = self.extract_path.split(".")
            for part in parts:
                if isinstance(obj, dict) and part in obj:
                    obj = obj[part]
                else:
                    return None
            # Convert string numbers to Decimal
            if isinstance(obj, str):
                try:
                    return Decimal(obj)
                except:
                    return obj
            elif isinstance(obj, (int, float)):
                return Decimal(str(obj))
            return obj

        return None

    def _compare(self, value: Any) -> bool:
        """Compare extracted value to threshold."""
        if self.compare_value is None or self.compare_op is None:
            return True

        # Convert compare_value to same type
        compare_val = self.compare_value
        if isinstance(value, Decimal) and not isinstance(compare_val, Decimal):
            try:
                compare_val = Decimal(str(compare_val))
            except:
                return False

        ops = {
            "gt": lambda a, b: a > b,
            "gte": lambda a, b: a >= b,
            "lt": lambda a, b: a < b,
            "lte": lambda a, b: a <= b,
            "eq": lambda a, b: a == b,
            "ne": lambda a, b: a != b,
        }

        op_func = ops.get(self.compare_op)
        if op_func:
            try:
                return op_func(value, compare_val)
            except:
                return False
        return False


# =============================================================================
# SIGNAL RULES
# =============================================================================

@dataclass
class SignalRule:
    """
    Rule that fires a signal when conditions are met.

    A signal indicates a risk indicator or detection trigger.
    """
    rule_id: str
    code: str                    # Signal code (e.g., "HIGH_VALUE_CRYPTO")
    name: str                    # Human-readable name
    description: str = ""
    severity: Severity = Severity.MEDIUM
    conditions: List[Condition] = field(default_factory=list)
    policy_ref_ids: List[str] = field(default_factory=list)  # Policy references
    enabled: bool = True
    version: str = "1.0"

    def __post_init__(self):
        if not self.rule_id:
            raise RuleDefinitionError("Signal rule must have rule_id")
        if not self.code:
            raise RuleDefinitionError("Signal rule must have code")
        if not self.conditions:
            raise RuleDefinitionError("Signal rule must have at least one condition")

    @property
    def rule_logic_hash(self) -> str:
        """Compute hash of rule logic for audit trail."""
        # Canonical representation
        logic = f"{self.rule_id}:{self.code}:{self.severity.value}:{self.version}"
        for cond in self.conditions:
            if cond.pattern:
                logic += f"|pattern:{cond.pattern.namespace}:{cond.pattern.predicate}"
        return compute_rule_logic_hash(logic)

    def evaluate(self, facts: List[Fact]) -> Tuple[bool, List[Fact]]:
        """
        Evaluate rule against facts.

        Returns:
            (fires: bool, trigger_facts: List[Fact])
        """
        if not self.enabled:
            return False, []

        # All conditions must be satisfied
        all_trigger_facts = []
        for condition in self.conditions:
            matched, matching_facts = condition.evaluate(facts)
            if not matched:
                return False, []
            all_trigger_facts.extend(matching_facts)

        return True, _dedupe_facts(all_trigger_facts)


# =============================================================================
# MITIGATION RULES
# =============================================================================

@dataclass
class MitigationRule:
    """
    Rule that applies a mitigating factor when conditions are met.

    A mitigation reduces risk when supporting evidence exists.
    """
    rule_id: str
    code: str                    # Mitigation code (e.g., "MF_TXN_002")
    name: str
    description: str = ""
    weight: str = "-0.25"        # String-encoded decimal (negative = reduces risk)
    conditions: List[Condition] = field(default_factory=list)
    applies_to_signals: List[str] = field(default_factory=list)  # Signal codes this mitigates
    enabled: bool = True
    version: str = "1.0"

    def __post_init__(self):
        if not self.rule_id:
            raise RuleDefinitionError("Mitigation rule must have rule_id")
        if not self.code:
            raise RuleDefinitionError("Mitigation rule must have code")
        # Validate weight is valid decimal string
        try:
            Decimal(self.weight)
        except:
            raise RuleDefinitionError(f"Invalid weight format: {self.weight}")

    @property
    def rule_logic_hash(self) -> str:
        """Compute hash of rule logic for audit trail."""
        logic = f"{self.rule_id}:{self.code}:{self.weight}:{self.version}"
        return compute_rule_logic_hash(logic)

    def evaluate(
        self,
        facts: List[Fact],
        fired_signals: List[str]
    ) -> Tuple[bool, List[Fact], List[str]]:
        """
        Evaluate rule against facts and fired signals.

        Args:
            facts: Available facts
            fired_signals: List of signal codes that fired

        Returns:
            (applies: bool, anchor_facts: List[Fact], mitigated_signals: List[str])
        """
        if not self.enabled:
            return False, [], []

        # Check if any applicable signals fired
        mitigated = []
        if self.applies_to_signals:
            mitigated = [s for s in fired_signals if s in self.applies_to_signals]
            if not mitigated:
                return False, [], []

        # All conditions must be satisfied
        all_anchor_facts = []
        for condition in self.conditions:
            matched, matching_facts = condition.evaluate(facts)
            if not matched:
                return False, [], []
            all_anchor_facts.extend(matching_facts)

        return True, _dedupe_facts(all_anchor_facts), mitigated


# =============================================================================
# SCORING RULES
# =============================================================================

@dataclass
class ThresholdGate:
    """A threshold gate for verdict determination."""
    code: str                    # e.g., "CLEAR_AND_CLOSE", "ESCALATE_L1"
    max_score: str               # String-encoded decimal, exclusive upper bound
    description: str = ""

    def matches(self, score: Decimal) -> bool:
        """Check if score falls within this gate."""
        return score < Decimal(self.max_score)


@dataclass
class ScoringRule:
    """
    Rule that computes risk score from signals and mitigations.

    The scoring formula is:
    residual_score = inherent_score + sum(mitigation_weights)

    Where inherent_score is sum of signal severity weights.
    """
    rule_id: str
    name: str
    description: str = ""
    # How to compute inherent score from signals
    signal_weights: Dict[str, str] = field(default_factory=dict)  # signal_code -> weight
    default_signal_weight: str = "0.50"  # Default weight if not in map
    # Threshold gates for verdict (ordered by max_score ascending)
    threshold_gates: List[ThresholdGate] = field(default_factory=list)
    version: str = "1.0"

    def __post_init__(self):
        if not self.rule_id:
            raise RuleDefinitionError("Scoring rule must have rule_id")
        # Validate threshold gates are ordered
        for i in range(len(self.threshold_gates) - 1):
            if Decimal(self.threshold_gates[i].max_score) >= Decimal(self.threshold_gates[i+1].max_score):
                raise RuleDefinitionError("Threshold gates must be ordered by max_score ascending")

    @property
    def rule_logic_hash(self) -> str:
        """Compute hash of rule logic for audit trail."""
        logic = f"{self.rule_id}:{self.version}"
        for code, weight in sorted(self.signal_weights.items()):
            logic += f"|{code}:{weight}"
        for gate in self.threshold_gates:
            logic += f"|gate:{gate.code}:{gate.max_score}"
        return compute_rule_logic_hash(logic)

    def compute_score(
        self,
        signal_codes: List[str],
        mitigation_weights: List[str]
    ) -> Tuple[str, str, str, str, str, str]:
        """
        Compute risk score using dual-score methodology.

        Raw scores are additive (sum of weights) for explainability.
        Normalized scores use probability union formula for threshold matching.

        Args:
            signal_codes: Codes of fired signals
            mitigation_weights: Weights of applied mitigations

        Returns:
            (inherent_raw, inherent_normalized, mitigation_sum,
             residual_raw, residual_normalized, threshold_gate_code)
        """
        # Compute RAW inherent score (additive - for explainability)
        inherent_raw = Decimal("0")
        signal_weights_decimal = []
        for code in signal_codes:
            weight_str = self.signal_weights.get(code, self.default_signal_weight)
            weight = Decimal(weight_str)
            inherent_raw += weight
            signal_weights_decimal.append(weight)

        # Compute NORMALIZED inherent score using probability union formula:
        # P(A ∪ B) = 1 - (1-P(A))(1-P(B))
        # This caps the score at ~1.0 regardless of how many signals fire
        if signal_weights_decimal:
            product = Decimal("1")
            for w in signal_weights_decimal:
                # Clamp individual weights to [0, 1] for probability interpretation
                w_clamped = min(Decimal("1"), max(Decimal("0"), w))
                product *= (Decimal("1") - w_clamped)
            inherent_normalized = Decimal("1") - product
        else:
            inherent_normalized = Decimal("0")

        # Sum mitigations (these are negative values)
        mitigation_sum = Decimal("0")
        for weight in mitigation_weights:
            mitigation_sum += Decimal(weight)

        # Compute RAW residual (floor at 0)
        residual_raw = max(Decimal("0"), inherent_raw + mitigation_sum)

        # Compute NORMALIZED residual
        # Scale mitigation impact proportionally to normalized score
        # If raw inherent is 12.25 and mitigations are -1.25, that's ~10% reduction
        # Apply same percentage to normalized
        if inherent_raw > Decimal("0"):
            mitigation_ratio = mitigation_sum / inherent_raw  # negative ratio
            residual_normalized = max(
                Decimal("0"),
                inherent_normalized * (Decimal("1") + mitigation_ratio)
            )
        else:
            residual_normalized = inherent_normalized

        # Round normalized to 2 decimal places for cleaner output
        residual_normalized = residual_normalized.quantize(Decimal("0.01"))
        inherent_normalized = inherent_normalized.quantize(Decimal("0.01"))

        # Determine threshold gate using NORMALIZED residual
        gate_code = "MANUAL_REVIEW"  # Default if no gate matches
        for gate in self.threshold_gates:
            if gate.matches(residual_normalized):
                gate_code = gate.code
                break

        return (
            score_to_string(float(inherent_raw)),
            score_to_string(float(inherent_normalized)),
            score_to_string(float(mitigation_sum)),
            score_to_string(float(residual_raw)),
            score_to_string(float(residual_normalized)),
            gate_code
        )


# =============================================================================
# VERDICT RULES
# =============================================================================

@dataclass
class VerdictRule:
    """
    Rule that determines final verdict from score.

    Simple mapping from threshold gate to verdict + auto-archive permission.
    """
    rule_id: str
    name: str
    description: str = ""
    # Map threshold gate code to (verdict, auto_archive_permitted)
    gate_verdicts: Dict[str, Tuple[str, bool]] = field(default_factory=dict)
    default_verdict: str = "MANUAL_REVIEW"
    default_auto_archive: bool = False
    version: str = "1.0"

    def __post_init__(self):
        if not self.rule_id:
            raise RuleDefinitionError("Verdict rule must have rule_id")

    @property
    def rule_logic_hash(self) -> str:
        """Compute hash of rule logic for audit trail."""
        logic = f"{self.rule_id}:{self.version}"
        for gate, (verdict, auto) in sorted(self.gate_verdicts.items()):
            logic += f"|{gate}:{verdict}:{auto}"
        return compute_rule_logic_hash(logic)

    def determine_verdict(self, threshold_gate: str) -> Tuple[str, bool]:
        """
        Determine verdict from threshold gate.

        Returns:
            (verdict_code, auto_archive_permitted)
        """
        if threshold_gate in self.gate_verdicts:
            return self.gate_verdicts[threshold_gate]
        return self.default_verdict, self.default_auto_archive


# =============================================================================
# EVALUATION CONTEXT
# =============================================================================

@dataclass
class EvaluationContext:
    """
    Context for rule evaluation.

    Carries information needed to create cells.
    """
    graph_id: str
    namespace: str
    case_id: str                 # Subject for all produced cells
    system_time: Optional[str] = None
    prev_cell_hash: str = NULL_HASH  # For chaining
    pack: Optional[Pack] = None  # For payload validation

    def __post_init__(self):
        if not self.system_time:
            self.system_time = get_current_timestamp()


@dataclass
class EvaluationResult:
    """
    Result of rules evaluation.

    Contains all produced cells and audit information.
    """
    signals: List[DecisionCell] = field(default_factory=list)
    mitigations: List[DecisionCell] = field(default_factory=list)
    score: Optional[DecisionCell] = None
    verdict: Optional[DecisionCell] = None
    # Audit trail
    rules_evaluated: int = 0
    signals_fired: int = 0
    mitigations_applied: int = 0

    @property
    def all_cells(self) -> List[DecisionCell]:
        """Get all produced cells in order."""
        cells = []
        cells.extend(self.signals)
        cells.extend(self.mitigations)
        if self.score:
            cells.append(self.score)
        if self.verdict:
            cells.append(self.verdict)
        return cells


# =============================================================================
# RULES ENGINE
# =============================================================================

class RulesEngine:
    """
    Deterministic rules evaluation engine.

    Evaluates facts against rules to produce:
    - SIGNAL cells
    - MITIGATION cells
    - SCORE cells
    - VERDICT cells
    """

    def __init__(self):
        self.signal_rules: List[SignalRule] = []
        self.mitigation_rules: List[MitigationRule] = []
        self.scoring_rule: Optional[ScoringRule] = None
        self.verdict_rule: Optional[VerdictRule] = None

    def add_signal_rule(self, rule: SignalRule) -> None:
        """Add a signal rule."""
        self.signal_rules.append(rule)

    def add_mitigation_rule(self, rule: MitigationRule) -> None:
        """Add a mitigation rule."""
        self.mitigation_rules.append(rule)

    def set_scoring_rule(self, rule: ScoringRule) -> None:
        """Set the scoring rule."""
        self.scoring_rule = rule

    def set_verdict_rule(self, rule: VerdictRule) -> None:
        """Set the verdict rule."""
        self.verdict_rule = rule

    def evaluate(
        self,
        facts: List[Fact],
        context: EvaluationContext
    ) -> EvaluationResult:
        """
        Evaluate all rules against facts.

        This is the main entry point. It:
        1. Evaluates signal rules → produces SIGNAL cells
        2. Evaluates mitigation rules → produces MITIGATION cells
        3. Computes score → produces SCORE cell
        4. Determines verdict → produces VERDICT cell

        Args:
            facts: List of facts to evaluate
            context: Evaluation context

        Returns:
            EvaluationResult with all produced cells
        """
        result = EvaluationResult()
        prev_hash = context.prev_cell_hash

        # Track what fires for downstream rules
        fired_signal_codes: List[str] = []
        signal_cell_ids: List[str] = []
        mitigation_weights: List[str] = []
        mitigation_cell_ids: List[str] = []
        all_trigger_fact_ids: List[str] = []

        # 1. Evaluate signal rules
        for rule in self.signal_rules:
            result.rules_evaluated += 1
            fires, trigger_facts = rule.evaluate(facts)
            if fires:
                result.signals_fired += 1
                fired_signal_codes.append(rule.code)

                # Get trigger fact cell_ids (assuming facts have been persisted)
                trigger_ids = self._get_fact_cell_ids(trigger_facts)
                all_trigger_fact_ids.extend(trigger_ids)

                # Create SIGNAL cell
                signal_cell = self._create_signal_cell(
                    rule, trigger_ids, context, prev_hash
                )
                result.signals.append(signal_cell)
                signal_cell_ids.append(signal_cell.cell_id)
                prev_hash = signal_cell.cell_id

        # 2. Evaluate mitigation rules
        for rule in self.mitigation_rules:
            result.rules_evaluated += 1
            applies, anchor_facts, mitigated_signals = rule.evaluate(
                facts, fired_signal_codes
            )
            if applies:
                result.mitigations_applied += 1
                mitigation_weights.append(rule.weight)

                # Get cell IDs of mitigated signals
                mitigated_signal_cell_ids = [
                    cell.cell_id for cell in result.signals
                    if cell.fact.object.get("code") in mitigated_signals
                ]

                # Create MITIGATION cell with detailed evidence anchors
                mit_cell = self._create_mitigation_cell(
                    rule, anchor_facts, mitigated_signal_cell_ids, context, prev_hash
                )
                result.mitigations.append(mit_cell)
                mitigation_cell_ids.append(mit_cell.cell_id)
                prev_hash = mit_cell.cell_id

        # 3. Compute score
        if self.scoring_rule and fired_signal_codes:
            result.rules_evaluated += 1
            (inherent_raw, inherent_norm, mit_sum,
             residual_raw, residual_norm, gate) = self.scoring_rule.compute_score(
                fired_signal_codes, mitigation_weights
            )

            score_cell = self._create_score_cell(
                self.scoring_rule, inherent_raw, inherent_norm, mit_sum,
                residual_raw, residual_norm, gate, context, prev_hash
            )
            result.score = score_cell
            prev_hash = score_cell.cell_id

            # 4. Determine verdict
            if self.verdict_rule:
                result.rules_evaluated += 1
                verdict_code, auto_archive = self.verdict_rule.determine_verdict(gate)

                # Collect all supporting cell IDs
                rationale_ids = signal_cell_ids + mitigation_cell_ids
                if result.score:
                    rationale_ids.append(result.score.cell_id)

                verdict_cell = self._create_verdict_cell(
                    self.verdict_rule, verdict_code, rationale_ids,
                    auto_archive, context, prev_hash
                )
                result.verdict = verdict_cell

        return result

    def _get_fact_cell_ids(self, facts: List[Fact]) -> List[str]:
        """
        Get cell IDs for facts.

        In a real system, facts would be persisted cells with IDs.
        For evaluation, we use a placeholder pattern.
        """
        # Facts should be from cells - use cell_id if available
        # For now, return empty list (will be filled by cell creation)
        return []

    def _create_signal_cell(
        self,
        rule: SignalRule,
        trigger_fact_ids: List[str],
        context: EvaluationContext,
        prev_hash: str
    ) -> DecisionCell:
        """Create a SIGNAL cell."""
        payload = {
            "schema_version": "1.0",
            "code": rule.code,
            "name": rule.name,
            "severity": rule.severity.value,
            "trigger_facts": trigger_fact_ids,
            "policy_refs": rule.policy_ref_ids,
        }

        # Validate against pack if available
        if context.pack:
            validate_payload(context.pack, CellType.SIGNAL, payload, strict=False)

        return DecisionCell(
            header=Header(
                version="1.0",
                graph_id=context.graph_id,
                cell_type=CellType.SIGNAL,
                system_time=context.system_time,
                prev_cell_hash=prev_hash,
                hash_scheme=HASH_SCHEME_CANONICAL
            ),
            fact=Fact(
                namespace=context.namespace,
                subject=context.case_id,
                predicate="signal.fired",
                object=payload,
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(
                rule_id=rule.rule_id,
                rule_logic_hash=rule.rule_logic_hash,
                interpreter="decisiongraph:rules:v2"
            )
        )

    def _create_mitigation_cell(
        self,
        rule: MitigationRule,
        anchor_facts: List[Fact],
        applies_to_signal_ids: List[str],
        context: EvaluationContext,
        prev_hash: str
    ) -> DecisionCell:
        """Create a MITIGATION cell with detailed evidence anchors."""
        # Build detailed evidence anchors from anchor facts
        evidence_anchors = []
        anchor_cell_ids = []
        for fact in anchor_facts:
            # Try to get cell_id from fact if it has one (stored as attribute)
            cell_id = getattr(fact, '_cell_id', "")
            anchor = DetailedEvidenceAnchor.from_fact(fact, cell_id)
            evidence_anchors.append(anchor.to_dict())
            if cell_id:
                anchor_cell_ids.append(cell_id)

        payload = {
            "schema_version": "1.0",
            "code": rule.code,
            "name": rule.name,
            "weight": rule.weight,
            "anchors": anchor_cell_ids,  # Backward-compatible cell ID list
            "evidence_anchors": evidence_anchors,  # NEW: detailed evidence
            "applies_to_signals": applies_to_signal_ids,
        }

        if context.pack:
            validate_payload(context.pack, CellType.MITIGATION, payload, strict=False)

        return DecisionCell(
            header=Header(
                version="1.0",
                graph_id=context.graph_id,
                cell_type=CellType.MITIGATION,
                system_time=context.system_time,
                prev_cell_hash=prev_hash,
                hash_scheme=HASH_SCHEME_CANONICAL
            ),
            fact=Fact(
                namespace=context.namespace,
                subject=context.case_id,
                predicate="mitigation.applied",
                object=payload,
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(
                rule_id=rule.rule_id,
                rule_logic_hash=rule.rule_logic_hash,
                interpreter="decisiongraph:rules:v2"
            )
        )

    def _create_score_cell(
        self,
        rule: ScoringRule,
        inherent_raw: str,
        inherent_normalized: str,
        mitigation_sum: str,
        residual_raw: str,
        residual_normalized: str,
        threshold_gate: str,
        context: EvaluationContext,
        prev_hash: str
    ) -> DecisionCell:
        """Create a SCORE cell with dual scoring methodology."""
        payload = {
            "schema_version": "2.0",
            # Raw scores (additive) - for explainability
            "inherent_score": inherent_raw,
            "residual_score": residual_raw,
            # Normalized scores (probability union) - for threshold matching
            "inherent_normalized": inherent_normalized,
            "residual_normalized": residual_normalized,
            # Mitigations and gate
            "mitigation_sum": mitigation_sum,
            "threshold_gate": threshold_gate,
        }

        if context.pack:
            validate_payload(context.pack, CellType.SCORE, payload, strict=False)

        return DecisionCell(
            header=Header(
                version="1.0",
                graph_id=context.graph_id,
                cell_type=CellType.SCORE,
                system_time=context.system_time,
                prev_cell_hash=prev_hash,
                hash_scheme=HASH_SCHEME_CANONICAL
            ),
            fact=Fact(
                namespace=context.namespace,
                subject=context.case_id,
                predicate="score.computed",
                object=payload,
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(
                rule_id=rule.rule_id,
                rule_logic_hash=rule.rule_logic_hash,
                interpreter="decisiongraph:rules:v2"
            )
        )

    def _create_verdict_cell(
        self,
        rule: VerdictRule,
        verdict_code: str,
        rationale_fact_ids: List[str],
        auto_archive_permitted: bool,
        context: EvaluationContext,
        prev_hash: str
    ) -> DecisionCell:
        """Create a VERDICT cell."""
        payload = {
            "schema_version": "1.0",
            "verdict": verdict_code,
            "rationale_fact_refs": rationale_fact_ids,
            "auto_archive_permitted": auto_archive_permitted,
        }

        if context.pack:
            validate_payload(context.pack, CellType.VERDICT, payload, strict=False)

        return DecisionCell(
            header=Header(
                version="1.0",
                graph_id=context.graph_id,
                cell_type=CellType.VERDICT,
                system_time=context.system_time,
                prev_cell_hash=prev_hash,
                hash_scheme=HASH_SCHEME_CANONICAL
            ),
            fact=Fact(
                namespace=context.namespace,
                subject=context.case_id,
                predicate="verdict.rendered",
                object=payload,
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED
            ),
            logic_anchor=LogicAnchor(
                rule_id=rule.rule_id,
                rule_logic_hash=rule.rule_logic_hash,
                interpreter="decisiongraph:rules:v2"
            )
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_aml_example_engine() -> RulesEngine:
    """
    Create an example AML rules engine for testing.

    This demonstrates the pattern for real rule packs.
    """
    engine = RulesEngine()

    # Signal: High-value cryptocurrency transaction
    engine.add_signal_rule(SignalRule(
        rule_id="sig_001",
        code="HIGH_VALUE_CRYPTO",
        name="High-Value Cryptocurrency Transaction",
        description="Transaction involves cryptocurrency above threshold",
        severity=Severity.MEDIUM,
        conditions=[
            Condition(
                pattern=FactPattern(
                    predicate="txn.type",
                    object_value="CRYPTOCURRENCY"
                )
            ),
            Condition(
                pattern=FactPattern(
                    predicate="txn.amount",
                ),
                extract_path="",  # Direct value
                compare_op="gte",
                compare_value=10000
            )
        ]
    ))

    # Signal: High-risk jurisdiction
    engine.add_signal_rule(SignalRule(
        rule_id="sig_002",
        code="HIGH_RISK_JURISDICTION",
        name="High-Risk Jurisdiction",
        description="Transaction involves high-risk country",
        severity=Severity.HIGH,
        conditions=[
            Condition(
                patterns=[
                    FactPattern(predicate="txn.benef_country", object_value="CAYMAN_ISLANDS"),
                    FactPattern(predicate="txn.benef_country", object_value="PANAMA"),
                    FactPattern(predicate="txn.benef_country", object_value="BVI"),
                ],
                match_mode="any"
            )
        ]
    ))

    # Mitigation: Documentation complete
    engine.add_mitigation_rule(MitigationRule(
        rule_id="mit_001",
        code="MF_DOC_COMPLETE",
        name="Documentation Complete",
        description="All required documentation is on file",
        weight="-0.30",
        applies_to_signals=["HIGH_VALUE_CRYPTO", "HIGH_RISK_JURISDICTION"],
        conditions=[
            Condition(
                pattern=FactPattern(
                    predicate="documentation.status",
                    object_value="COMPLETE"
                )
            )
        ]
    ))

    # Mitigation: Long-standing customer
    engine.add_mitigation_rule(MitigationRule(
        rule_id="mit_002",
        code="MF_LONG_CUSTOMER",
        name="Long-Standing Customer",
        description="Customer relationship over 5 years",
        weight="-0.25",
        applies_to_signals=["HIGH_VALUE_CRYPTO"],
        conditions=[
            Condition(
                pattern=FactPattern(
                    predicate="customer.tenure_years",
                ),
                extract_path="",
                compare_op="gte",
                compare_value=5
            )
        ]
    ))

    # Scoring rule
    engine.set_scoring_rule(ScoringRule(
        rule_id="score_001",
        name="AML Risk Score",
        signal_weights={
            "HIGH_VALUE_CRYPTO": "0.50",
            "HIGH_RISK_JURISDICTION": "0.75",
        },
        threshold_gates=[
            ThresholdGate("CLEAR_AND_CLOSE", "0.30", "Low risk - auto-close"),
            ThresholdGate("ANALYST_REVIEW", "0.60", "Medium risk - analyst review"),
            ThresholdGate("ESCALATE_L2", "0.80", "High risk - senior review"),
        ]
    ))

    # Verdict rule
    engine.set_verdict_rule(VerdictRule(
        rule_id="verdict_001",
        name="AML Verdict",
        gate_verdicts={
            "CLEAR_AND_CLOSE": ("CLEAR_AND_CLOSE", True),
            "ANALYST_REVIEW": ("ANALYST_REVIEW", False),
            "ESCALATE_L2": ("ESCALATE_L2", False),
        },
        default_verdict="MANUAL_REVIEW",
        default_auto_archive=False
    ))

    return engine


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Exceptions
    'RuleError',
    'RuleDefinitionError',
    'RuleEvaluationError',
    'ConditionError',
    # Severity
    'Severity',
    # Evidence anchoring
    'DetailedEvidenceAnchor',
    # Conditions
    'FactPattern',
    'Condition',
    # Rules
    'SignalRule',
    'MitigationRule',
    'ScoringRule',
    'VerdictRule',
    'ThresholdGate',
    # Context and results
    'EvaluationContext',
    'EvaluationResult',
    # Engine
    'RulesEngine',
    # Helpers
    'create_aml_example_engine',
]
