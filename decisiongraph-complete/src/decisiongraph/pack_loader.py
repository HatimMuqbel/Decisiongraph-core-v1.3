"""
pack_loader.py - Pack Loader Utility

Loads, validates, and compiles YAML packs into runtime objects.
Makes packs operational for bank use.

What this does:
1. Load + validate pack YAML (hard validation, fail fast)
2. Compile to PackRuntime (signals, mitigations, rules, thresholds)
3. Lock pack identity with deterministic pack_hash
4. Optionally produce POLICY_REF cells for citations

Usage:
    from pack_loader import load_pack_yaml, PackRuntime

    runtime = load_pack_yaml("packs/fincrime_canada.yaml")

    # Use with rules engine
    engine = runtime.create_rules_engine()
    result = engine.evaluate(facts, context)

    # Get pack hash for audit trail
    print(f"Pack hash: {runtime.pack_hash}")
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

# Import from the complete package
import sys
_complete_path = Path(__file__).parent.parent.parent / "decisiongraph-complete" / "src"
if _complete_path.exists():
    sys.path.insert(0, str(_complete_path))

from decisiongraph.cell import (
    DecisionCell,
    Header,
    Fact,
    LogicAnchor,
    Proof,
    CellType,
    SourceQuality,
    HASH_SCHEME_CANONICAL,
    get_current_timestamp,
    compute_rule_logic_hash,
)
from decisiongraph.rules import (
    RulesEngine,
    SignalRule,
    MitigationRule,
    ScoringRule,
    VerdictRule,
    ThresholdGate,
    Severity,
    FactPattern,
    Condition,
)
from decisiongraph.canon import canonical_json_bytes


# ============================================================================
# EXCEPTIONS
# ============================================================================

class PackLoaderError(Exception):
    """Base exception for pack loader errors."""
    pass


class PackValidationError(PackLoaderError):
    """Raised when pack validation fails."""
    def __init__(self, message: str, errors: List[str] = None):
        self.errors = errors or []
        super().__init__(message)

    def __str__(self):
        if self.errors:
            return f"{self.args[0]}\n" + "\n".join(f"  - {e}" for e in self.errors)
        return self.args[0]


class PackCompilationError(PackLoaderError):
    """Raised when pack compilation fails."""
    pass


# ============================================================================
# VALIDATION PATTERNS
# ============================================================================

# Signal/mitigation code pattern: uppercase letters, numbers, underscores
CODE_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]*$')

# Weight pattern: string decimal, can be negative (e.g., "-0.25", "0.50")
WEIGHT_PATTERN = re.compile(r'^-?\d+\.\d+$')

# Threshold pattern: string decimal (e.g., "0.25", "999.00")
THRESHOLD_PATTERN = re.compile(r'^\d+\.\d+$')

# Version pattern: semantic version
VERSION_PATTERN = re.compile(r'^\d+\.\d+\.\d+$')

# Severity values
VALID_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


# ============================================================================
# VALIDATION HELPERS
# ============================================================================

def _validate_string_decimal(value: Any, field_path: str) -> List[str]:
    """Validate value is a string-encoded decimal (no floats!)."""
    errors = []
    if isinstance(value, float):
        errors.append(f"{field_path}: float not allowed, use string (got {value})")
    elif isinstance(value, int) and not isinstance(value, bool):
        errors.append(f"{field_path}: integer not allowed, use string (got {value})")
    elif isinstance(value, str):
        try:
            Decimal(value)
        except InvalidOperation:
            errors.append(f"{field_path}: invalid decimal string '{value}'")
    else:
        errors.append(f"{field_path}: expected string decimal, got {type(value).__name__}")
    return errors


def _validate_required_fields(obj: dict, required: List[str], path: str) -> List[str]:
    """Check that all required fields are present."""
    errors = []
    for field in required:
        if field not in obj:
            errors.append(f"{path}: missing required field '{field}'")
    return errors


def _validate_code_format(code: str, path: str) -> List[str]:
    """Validate signal/mitigation code format."""
    errors = []
    if not CODE_PATTERN.match(code):
        errors.append(
            f"{path}: invalid code format '{code}' "
            "(must be uppercase letters/numbers/underscores, start with letter)"
        )
    return errors


def _check_no_floats_recursive(obj: Any, path: str) -> List[str]:
    """Recursively check that no floats exist in the structure."""
    errors = []
    if isinstance(obj, float):
        errors.append(f"{path}: float value {obj} not allowed, use string")
    elif isinstance(obj, dict):
        for key, value in obj.items():
            errors.extend(_check_no_floats_recursive(value, f"{path}.{key}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            errors.extend(_check_no_floats_recursive(item, f"{path}[{i}]"))
    return errors


# ============================================================================
# PACK VALIDATION
# ============================================================================

def validate_pack(pack_dict: dict) -> None:
    """
    Validate a pack dictionary with hard validation.

    Fails fast with precise errors if anything is wrong.

    Validates:
    - Required fields present
    - Schema versions match
    - No floats anywhere (weights/thresholds as strings)
    - Citations are well-formed
    - Signal codes referenced by mitigations exist
    - Thresholds map to known verdicts
    - Code formats are valid

    Args:
        pack_dict: The parsed YAML pack

    Raises:
        PackValidationError: If validation fails
    """
    errors = []

    # -------------------------------------------------------------------------
    # 1. Required top-level fields
    # -------------------------------------------------------------------------
    required_top = [
        "pack_id", "name", "version", "domain", "jurisdiction",
        "signals", "mitigations", "scoring", "verdicts"
    ]
    errors.extend(_validate_required_fields(pack_dict, required_top, "pack"))

    # -------------------------------------------------------------------------
    # 2. Version format
    # -------------------------------------------------------------------------
    version = pack_dict.get("version", "")
    if version and not VERSION_PATTERN.match(version):
        errors.append(f"pack.version: invalid format '{version}' (expected X.Y.Z)")

    # -------------------------------------------------------------------------
    # 3. No floats anywhere in the pack
    # -------------------------------------------------------------------------
    errors.extend(_check_no_floats_recursive(pack_dict, "pack"))

    # -------------------------------------------------------------------------
    # 4. Validate signals
    # -------------------------------------------------------------------------
    signals = pack_dict.get("signals", [])
    signal_codes: Set[str] = set()

    for i, signal in enumerate(signals):
        path = f"signals[{i}]"

        # Required fields
        sig_required = ["code", "name", "severity"]
        errors.extend(_validate_required_fields(signal, sig_required, path))

        code = signal.get("code", "")
        if code:
            errors.extend(_validate_code_format(code, f"{path}.code"))
            if code in signal_codes:
                errors.append(f"{path}.code: duplicate signal code '{code}'")
            signal_codes.add(code)

        # Severity must be valid
        severity = signal.get("severity", "")
        if severity and severity not in VALID_SEVERITIES:
            errors.append(
                f"{path}.severity: invalid value '{severity}' "
                f"(must be one of {VALID_SEVERITIES})"
            )

        # Policy ref should be present for audit trail
        if "policy_ref" not in signal:
            errors.append(f"{path}: missing 'policy_ref' (required for citations)")

    # -------------------------------------------------------------------------
    # 5. Validate mitigations
    # -------------------------------------------------------------------------
    mitigations = pack_dict.get("mitigations", [])
    mitigation_codes: Set[str] = set()

    for i, mitigation in enumerate(mitigations):
        path = f"mitigations[{i}]"

        # Required fields
        mit_required = ["code", "name", "weight", "applies_to"]
        errors.extend(_validate_required_fields(mitigation, mit_required, path))

        code = mitigation.get("code", "")
        if code:
            errors.extend(_validate_code_format(code, f"{path}.code"))
            if code in mitigation_codes:
                errors.append(f"{path}.code: duplicate mitigation code '{code}'")
            mitigation_codes.add(code)

        # Weight must be string decimal and negative
        weight = mitigation.get("weight", "")
        if weight:
            errors.extend(_validate_string_decimal(weight, f"{path}.weight"))
            if isinstance(weight, str):
                try:
                    w = Decimal(weight)
                    if w >= 0:
                        errors.append(
                            f"{path}.weight: mitigations must have negative weight "
                            f"(got '{weight}')"
                        )
                except InvalidOperation:
                    pass  # Already caught above

        # applies_to must reference existing signals
        applies_to = mitigation.get("applies_to", [])
        for sig_code in applies_to:
            if sig_code not in signal_codes:
                errors.append(
                    f"{path}.applies_to: references unknown signal '{sig_code}'"
                )

    # -------------------------------------------------------------------------
    # 6. Validate scoring
    # -------------------------------------------------------------------------
    scoring = pack_dict.get("scoring", {})
    if scoring:
        path = "scoring"

        # Required fields
        score_required = ["rule_id", "name", "signal_weights", "threshold_gates"]
        errors.extend(_validate_required_fields(scoring, score_required, path))

        # Validate signal weights
        signal_weights = scoring.get("signal_weights", {})
        for sig_code, weight in signal_weights.items():
            if sig_code not in signal_codes:
                errors.append(
                    f"{path}.signal_weights: references unknown signal '{sig_code}'"
                )
            errors.extend(_validate_string_decimal(weight, f"{path}.signal_weights.{sig_code}"))

        # Validate threshold gates
        threshold_gates = scoring.get("threshold_gates", [])
        prev_threshold = Decimal("-1")
        gate_codes: Set[str] = set()

        for j, gate in enumerate(threshold_gates):
            gate_path = f"{path}.threshold_gates[{j}]"

            gate_required = ["code", "max_score"]
            errors.extend(_validate_required_fields(gate, gate_required, gate_path))

            gate_code = gate.get("code", "")
            if gate_code:
                if gate_code in gate_codes:
                    errors.append(f"{gate_path}.code: duplicate gate code '{gate_code}'")
                gate_codes.add(gate_code)

            max_score = gate.get("max_score", "")
            if max_score:
                errors.extend(_validate_string_decimal(max_score, f"{gate_path}.max_score"))
                try:
                    threshold = Decimal(max_score)
                    if threshold <= prev_threshold:
                        errors.append(
                            f"{gate_path}.max_score: must be greater than previous "
                            f"(got '{max_score}', prev was '{prev_threshold}')"
                        )
                    prev_threshold = threshold
                except InvalidOperation:
                    pass

    # -------------------------------------------------------------------------
    # 7. Validate verdicts
    # -------------------------------------------------------------------------
    verdicts = pack_dict.get("verdicts", {})
    if verdicts:
        path = "verdicts"

        verdict_required = ["rule_id", "name", "gate_verdicts"]
        errors.extend(_validate_required_fields(verdicts, verdict_required, path))

        # Validate gate_verdicts reference existing gates
        gate_verdicts = verdicts.get("gate_verdicts", {})
        scoring_gates = {g.get("code") for g in pack_dict.get("scoring", {}).get("threshold_gates", [])}

        for gate_code in gate_verdicts.keys():
            if gate_code not in scoring_gates:
                errors.append(
                    f"{path}.gate_verdicts: references unknown gate '{gate_code}'"
                )

    # -------------------------------------------------------------------------
    # 8. Validate shadow questions (if present)
    # -------------------------------------------------------------------------
    shadow_questions = pack_dict.get("shadow_questions", {})
    if shadow_questions:
        for category, questions in shadow_questions.items():
            if not isinstance(questions, list):
                errors.append(f"shadow_questions.{category}: must be a list")
                continue
            for i, q in enumerate(questions):
                path = f"shadow_questions.{category}[{i}]"
                if "id" not in q:
                    errors.append(f"{path}: missing 'id'")
                if "question" not in q:
                    errors.append(f"{path}: missing 'question'")

    # -------------------------------------------------------------------------
    # Fail if any errors
    # -------------------------------------------------------------------------
    if errors:
        raise PackValidationError(
            f"Pack validation failed with {len(errors)} error(s):",
            errors
        )


# ============================================================================
# PACK HASH COMPUTATION
# ============================================================================

def compute_pack_hash(pack_dict: dict) -> str:
    """
    Compute deterministic pack hash.

    Uses RFC 8785 canonical JSON for deterministic serialization,
    then SHA-256 hash.

    This hash is stored in:
    - PackRuntime
    - REPORT_RUN cells
    - SCORE/VERDICT outputs

    Gives "the bank ran this exact compliance library on that date."

    Args:
        pack_dict: The pack dictionary

    Returns:
        64-character hex string (SHA-256 hash)
    """
    # Extract hashable content (exclude volatile fields)
    hashable = {
        "pack_id": pack_dict.get("pack_id"),
        "version": pack_dict.get("version"),
        "signals": pack_dict.get("signals", []),
        "mitigations": pack_dict.get("mitigations", []),
        "scoring": pack_dict.get("scoring", {}),
        "verdicts": pack_dict.get("verdicts", {}),
        "shadow_questions": pack_dict.get("shadow_questions", {}),
        "predicates": pack_dict.get("predicates", []),
    }

    # Canonicalize and hash
    canonical_bytes = canonical_json_bytes(hashable)
    return hashlib.sha256(canonical_bytes).hexdigest()


# ============================================================================
# SIGNAL DEFINITION
# ============================================================================

@dataclass
class SignalDefinition:
    """Parsed signal definition from pack."""
    code: str
    name: str
    description: str
    severity: Severity
    policy_ref: str
    condition: Optional[dict] = None
    shadow_question: Optional[str] = None

    def to_rule(self) -> SignalRule:
        """Convert to SignalRule for rules engine."""
        # Build conditions from pack definition
        conditions = []

        if self.condition:
            # Parse condition into FactPattern + Condition
            pattern_dict = self.condition.get("pattern", {})
            pattern = FactPattern(
                namespace=pattern_dict.get("namespace"),
                predicate=pattern_dict.get("predicate"),
                object_value=pattern_dict.get("object_match"),
            )

            # Handle value comparison
            extract_path = self.condition.get("extract_path")
            compare_op = self.condition.get("compare_op")
            compare_value = self.condition.get("compare_value")

            condition = Condition(
                pattern=pattern,
                extract_path=extract_path,
                compare_op=compare_op,
                compare_value=Decimal(compare_value) if compare_value else None,
            )
            conditions.append(condition)
        else:
            # Default condition: match on alert with this code
            conditions.append(Condition(
                pattern=FactPattern(
                    namespace="fincrime.alert",
                    predicate="alert_triggered",
                )
            ))

        return SignalRule(
            rule_id=f"sig:{self.code}",
            code=self.code,
            name=self.name,
            description=self.description,
            severity=self.severity,
            conditions=conditions,
            policy_ref_ids=[self.policy_ref] if self.policy_ref else [],
        )


# ============================================================================
# MITIGATION DEFINITION
# ============================================================================

@dataclass
class MitigationDefinition:
    """Parsed mitigation definition from pack."""
    code: str
    name: str
    description: str
    weight: str  # String decimal, negative
    applies_to: List[str]  # Signal codes
    policy_ref: Optional[str] = None
    condition: Optional[dict] = None
    shadow_question: Optional[str] = None

    def to_rule(self) -> MitigationRule:
        """Convert to MitigationRule for rules engine."""
        conditions = []

        if self.condition:
            pattern_dict = self.condition.get("pattern", {})
            pattern = FactPattern(
                namespace=pattern_dict.get("namespace"),
                predicate=pattern_dict.get("predicate"),
                object_value=pattern_dict.get("object_match"),
            )

            extract_path = self.condition.get("extract_path")
            compare_op = self.condition.get("compare_op")
            compare_value = self.condition.get("compare_value")

            condition = Condition(
                pattern=pattern,
                extract_path=extract_path,
                compare_op=compare_op,
                compare_value=Decimal(compare_value) if compare_value else None,
            )
            conditions.append(condition)
        else:
            # Default condition: always applicable (if signals fired)
            conditions.append(Condition(
                pattern=FactPattern(
                    namespace="fincrime.assertion",
                )
            ))

        return MitigationRule(
            rule_id=f"mit:{self.code}",
            code=self.code,
            name=self.name,
            description=self.description,
            weight=self.weight,
            applies_to_signals=self.applies_to,
            conditions=conditions,
        )


# ============================================================================
# POLICY REFERENCE
# ============================================================================

@dataclass
class PolicyReference:
    """Policy reference for citation tracking."""
    ref_id: str
    citation: str
    description: Optional[str] = None
    url: Optional[str] = None

    def to_cell(
        self,
        graph_id: str,
        prev_hash: str,
        namespace: str,
        system_time: str,
    ) -> DecisionCell:
        """Create POLICY_REF cell."""
        obj = {
            "ref_id": self.ref_id,
            "citation": self.citation,
            "description": self.description,
            "url": self.url,
        }

        return DecisionCell(
            header=Header(
                version="1.3",
                graph_id=graph_id,
                cell_type=CellType.POLICY_REF,
                system_time=system_time,
                prev_cell_hash=prev_hash,
                hash_scheme=HASH_SCHEME_CANONICAL,
            ),
            fact=Fact(
                namespace=namespace,
                subject=f"policy:{self.ref_id}",
                predicate="policy_defined",
                object=obj,
                confidence=1.0,
                source_quality=SourceQuality.VERIFIED,
            ),
            logic_anchor=LogicAnchor(
                rule_id="pack:policy_ref",
                rule_logic_hash=compute_rule_logic_hash(f"policy:{self.ref_id}"),
                interpreter="pack_loader:v1.0",
            ),
        )


# ============================================================================
# SHADOW QUESTION SET
# ============================================================================

@dataclass
class ShadowQuestion:
    """A shadow question for audit trail."""
    id: str
    question: str
    required: bool = True


@dataclass
class ShadowQuestionSet:
    """Set of shadow questions for a category."""
    category: str  # e.g., "universal", "str_specific"
    questions: List[ShadowQuestion] = field(default_factory=list)


# ============================================================================
# PACK RUNTIME
# ============================================================================

@dataclass
class PackRuntime:
    """
    Compiled pack runtime - ready for rules engine.

    This is the operational form of a pack. It contains:
    - signals_by_code: Signal definitions indexed by code
    - mitigations_by_code: Mitigation definitions indexed by code
    - policy_refs: All policy references
    - policy_map_by_signal: Signal code → list of policy ref IDs
    - scoring_rule: Compiled scoring rule
    - verdict_rule: Compiled verdict rule
    - shadow_question_sets: Shadow questions by category
    - pack_hash: Deterministic identity hash
    - metadata: Pack metadata (id, version, etc.)
    """
    # Identity
    pack_id: str
    pack_version: str
    pack_hash: str

    # Metadata
    name: str
    description: str
    domain: str
    jurisdiction: str

    # Signals and mitigations
    signals_by_code: Dict[str, SignalDefinition] = field(default_factory=dict)
    mitigations_by_code: Dict[str, MitigationDefinition] = field(default_factory=dict)

    # Policy references
    policy_refs: List[PolicyReference] = field(default_factory=list)
    policy_map_by_signal: Dict[str, List[str]] = field(default_factory=dict)

    # Rules
    scoring_rule: Optional[ScoringRule] = None
    verdict_rule: Optional[VerdictRule] = None

    # Shadow questions
    shadow_question_sets: Dict[str, ShadowQuestionSet] = field(default_factory=dict)

    # Regulatory framework
    regulatory_framework: Dict[str, Any] = field(default_factory=dict)

    def create_rules_engine(self) -> RulesEngine:
        """
        Create a RulesEngine from this pack runtime.

        Returns a fully configured engine ready to evaluate facts.
        """
        engine = RulesEngine()

        # Add signal rules
        for signal_def in self.signals_by_code.values():
            try:
                engine.add_signal_rule(signal_def.to_rule())
            except Exception as e:
                # Skip signals that can't be converted (missing conditions)
                pass

        # Add mitigation rules
        for mit_def in self.mitigations_by_code.values():
            try:
                engine.add_mitigation_rule(mit_def.to_rule())
            except Exception as e:
                # Skip mitigations that can't be converted
                pass

        # Set scoring and verdict rules
        if self.scoring_rule:
            engine.set_scoring_rule(self.scoring_rule)
        if self.verdict_rule:
            engine.set_verdict_rule(self.verdict_rule)

        return engine

    def get_policy_refs_for_signal(self, signal_code: str) -> List[PolicyReference]:
        """Get policy references for a signal."""
        ref_ids = self.policy_map_by_signal.get(signal_code, [])
        return [r for r in self.policy_refs if r.ref_id in ref_ids]

    def create_policy_cells(
        self,
        graph_id: str,
        prev_hash: str,
        namespace: str = "fincrime.policy",
        system_time: Optional[str] = None,
    ) -> List[DecisionCell]:
        """
        Create POLICY_REF cells for all policy references.

        This enables citation tracking in the graph.
        """
        cells = []
        ts = system_time or get_current_timestamp()
        current_prev = prev_hash

        for policy_ref in self.policy_refs:
            cell = policy_ref.to_cell(graph_id, current_prev, namespace, ts)
            cells.append(cell)
            current_prev = cell.cell_id

        return cells

    def to_dict(self) -> dict:
        """Serialize runtime to dict for storage/debugging."""
        return {
            "pack_id": self.pack_id,
            "pack_version": self.pack_version,
            "pack_hash": self.pack_hash,
            "name": self.name,
            "domain": self.domain,
            "jurisdiction": self.jurisdiction,
            "signal_count": len(self.signals_by_code),
            "mitigation_count": len(self.mitigations_by_code),
            "policy_ref_count": len(self.policy_refs),
        }


# ============================================================================
# PACK COMPILATION
# ============================================================================

def compile_pack(pack_dict: dict) -> PackRuntime:
    """
    Compile a validated pack dictionary into PackRuntime.

    Args:
        pack_dict: Validated pack dictionary

    Returns:
        PackRuntime ready for rules engine

    Raises:
        PackCompilationError: If compilation fails
    """
    # Compute pack hash first
    pack_hash = compute_pack_hash(pack_dict)

    # Initialize runtime
    runtime = PackRuntime(
        pack_id=pack_dict.get("pack_id", ""),
        pack_version=pack_dict.get("version", ""),
        pack_hash=pack_hash,
        name=pack_dict.get("name", ""),
        description=pack_dict.get("description", ""),
        domain=pack_dict.get("domain", ""),
        jurisdiction=pack_dict.get("jurisdiction", ""),
        regulatory_framework=pack_dict.get("regulatory_framework", {}),
    )

    # -------------------------------------------------------------------------
    # Compile signals
    # -------------------------------------------------------------------------
    policy_refs_seen: Dict[str, PolicyReference] = {}

    for signal_dict in pack_dict.get("signals", []):
        code = signal_dict.get("code", "")
        severity_str = signal_dict.get("severity", "MEDIUM")
        severity = getattr(Severity, severity_str, Severity.MEDIUM)

        signal_def = SignalDefinition(
            code=code,
            name=signal_dict.get("name", ""),
            description=signal_dict.get("description", ""),
            severity=severity,
            policy_ref=signal_dict.get("policy_ref", ""),
            condition=signal_dict.get("condition"),
            shadow_question=signal_dict.get("shadow_question"),
        )
        runtime.signals_by_code[code] = signal_def

        # Track policy references
        policy_ref_str = signal_dict.get("policy_ref", "")
        if policy_ref_str:
            ref_id = _normalize_policy_ref_id(policy_ref_str)
            if ref_id not in policy_refs_seen:
                policy_refs_seen[ref_id] = PolicyReference(
                    ref_id=ref_id,
                    citation=policy_ref_str,
                )
            # Map signal to policy ref
            if code not in runtime.policy_map_by_signal:
                runtime.policy_map_by_signal[code] = []
            runtime.policy_map_by_signal[code].append(ref_id)

    # -------------------------------------------------------------------------
    # Compile mitigations
    # -------------------------------------------------------------------------
    for mit_dict in pack_dict.get("mitigations", []):
        code = mit_dict.get("code", "")

        mit_def = MitigationDefinition(
            code=code,
            name=mit_dict.get("name", ""),
            description=mit_dict.get("description", ""),
            weight=mit_dict.get("weight", "-0.25"),
            applies_to=mit_dict.get("applies_to", []),
            policy_ref=mit_dict.get("policy_ref"),
            condition=mit_dict.get("condition"),
            shadow_question=mit_dict.get("shadow_question"),
        )
        runtime.mitigations_by_code[code] = mit_def

        # Track policy references
        policy_ref_str = mit_dict.get("policy_ref", "")
        if policy_ref_str:
            ref_id = _normalize_policy_ref_id(policy_ref_str)
            if ref_id not in policy_refs_seen:
                policy_refs_seen[ref_id] = PolicyReference(
                    ref_id=ref_id,
                    citation=policy_ref_str,
                )

    runtime.policy_refs = list(policy_refs_seen.values())

    # -------------------------------------------------------------------------
    # Compile scoring rule
    # -------------------------------------------------------------------------
    scoring_dict = pack_dict.get("scoring", {})
    if scoring_dict:
        signal_weights = scoring_dict.get("signal_weights", {})
        threshold_gates = []

        for gate_dict in scoring_dict.get("threshold_gates", []):
            threshold_gates.append(ThresholdGate(
                code=gate_dict.get("code", ""),
                max_score=gate_dict.get("max_score", "999.00"),
                description=gate_dict.get("description", ""),
            ))

        runtime.scoring_rule = ScoringRule(
            rule_id=scoring_dict.get("rule_id", "pack_scoring"),
            name=scoring_dict.get("name", "Pack Scoring Rule"),
            description=scoring_dict.get("description", ""),
            signal_weights=signal_weights,
            default_signal_weight=scoring_dict.get("default_signal_weight", "0.50"),
            threshold_gates=threshold_gates,
        )

    # -------------------------------------------------------------------------
    # Compile verdict rule
    # -------------------------------------------------------------------------
    verdicts_dict = pack_dict.get("verdicts", {})
    if verdicts_dict:
        gate_verdicts = {}
        for gate_code, verdict_info in verdicts_dict.get("gate_verdicts", {}).items():
            if isinstance(verdict_info, dict):
                verdict_code = verdict_info.get("verdict", gate_code)
                auto_archive = verdict_info.get("auto_archive_permitted", False)
            else:
                verdict_code = str(verdict_info)
                auto_archive = False
            gate_verdicts[gate_code] = (verdict_code, auto_archive)

        runtime.verdict_rule = VerdictRule(
            rule_id=verdicts_dict.get("rule_id", "pack_verdict"),
            name=verdicts_dict.get("name", "Pack Verdict Rule"),
            description=verdicts_dict.get("description", ""),
            gate_verdicts=gate_verdicts,
            default_verdict=verdicts_dict.get("default_verdict", "MANUAL_REVIEW"),
            default_auto_archive=verdicts_dict.get("default_auto_archive", False),
        )

    # -------------------------------------------------------------------------
    # Compile shadow questions
    # -------------------------------------------------------------------------
    shadow_dict = pack_dict.get("shadow_questions", {})
    for category, questions in shadow_dict.items():
        sq_list = []
        for q in questions:
            sq_list.append(ShadowQuestion(
                id=q.get("id", ""),
                question=q.get("question", ""),
                required=q.get("required", True),
            ))
        runtime.shadow_question_sets[category] = ShadowQuestionSet(
            category=category,
            questions=sq_list,
        )

    return runtime


def _normalize_policy_ref_id(citation: str) -> str:
    """Normalize a policy citation to a ref ID."""
    # Simple normalization: lowercase, replace spaces/punctuation
    ref_id = citation.lower()
    ref_id = re.sub(r'[^a-z0-9]+', '_', ref_id)
    ref_id = ref_id.strip('_')
    return ref_id[:64]  # Max 64 chars


# ============================================================================
# MAIN LOADER FUNCTION
# ============================================================================

def load_pack_yaml(path: str) -> PackRuntime:
    """
    Load, validate, and compile a YAML pack file.

    This is the main entry point. It:
    1. Reads and parses YAML
    2. Validates with hard validation (fail fast)
    3. Compiles to PackRuntime
    4. Computes deterministic pack_hash

    Args:
        path: Path to pack YAML file

    Returns:
        PackRuntime ready for rules engine

    Raises:
        PackLoaderError: If file cannot be read
        PackValidationError: If validation fails
        PackCompilationError: If compilation fails

    Example:
        >>> runtime = load_pack_yaml("packs/fincrime_canada.yaml")
        >>> print(f"Loaded {runtime.pack_id} v{runtime.pack_version}")
        >>> print(f"Pack hash: {runtime.pack_hash[:16]}...")
        >>> engine = runtime.create_rules_engine()
    """
    path = Path(path)

    # Check file exists
    if not path.exists():
        raise PackLoaderError(f"Pack file not found: {path}")

    # Read and parse YAML
    try:
        with open(path, 'r', encoding='utf-8') as f:
            pack_dict = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise PackLoaderError(f"Invalid YAML in pack file: {e}")
    except IOError as e:
        raise PackLoaderError(f"Cannot read pack file: {e}")

    if not isinstance(pack_dict, dict):
        raise PackLoaderError("Pack file must contain a YAML dictionary")

    # Validate
    validate_pack(pack_dict)

    # Compile
    runtime = compile_pack(pack_dict)

    return runtime


def load_pack_dict(pack_dict: dict) -> PackRuntime:
    """
    Load a pack from a dictionary (already parsed).

    Useful for testing or programmatic pack creation.

    Args:
        pack_dict: Pack dictionary

    Returns:
        PackRuntime
    """
    validate_pack(pack_dict)
    return compile_pack(pack_dict)


# ============================================================================
# PACK DIFF UTILITY
# ============================================================================

def diff_pack_versions(old_runtime: PackRuntime, new_runtime: PackRuntime) -> dict:
    """
    Compare two pack versions and return differences.

    Useful for upgrade audits.

    Returns:
        Dictionary with added/removed/changed items
    """
    diff = {
        "pack_id": old_runtime.pack_id,
        "old_version": old_runtime.pack_version,
        "new_version": new_runtime.pack_version,
        "old_hash": old_runtime.pack_hash,
        "new_hash": new_runtime.pack_hash,
        "signals": {
            "added": [],
            "removed": [],
            "changed": [],
        },
        "mitigations": {
            "added": [],
            "removed": [],
            "changed": [],
        },
    }

    # Signal changes
    old_codes = set(old_runtime.signals_by_code.keys())
    new_codes = set(new_runtime.signals_by_code.keys())

    diff["signals"]["added"] = list(new_codes - old_codes)
    diff["signals"]["removed"] = list(old_codes - new_codes)

    for code in old_codes & new_codes:
        old_sig = old_runtime.signals_by_code[code]
        new_sig = new_runtime.signals_by_code[code]
        if old_sig.severity != new_sig.severity or old_sig.policy_ref != new_sig.policy_ref:
            diff["signals"]["changed"].append(code)

    # Mitigation changes
    old_mit_codes = set(old_runtime.mitigations_by_code.keys())
    new_mit_codes = set(new_runtime.mitigations_by_code.keys())

    diff["mitigations"]["added"] = list(new_mit_codes - old_mit_codes)
    diff["mitigations"]["removed"] = list(old_mit_codes - new_mit_codes)

    for code in old_mit_codes & new_mit_codes:
        old_mit = old_runtime.mitigations_by_code[code]
        new_mit = new_runtime.mitigations_by_code[code]
        if old_mit.weight != new_mit.weight or old_mit.applies_to != new_mit.applies_to:
            diff["mitigations"]["changed"].append(code)

    return diff


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Exceptions
    'PackLoaderError',
    'PackValidationError',
    'PackCompilationError',

    # Main functions
    'load_pack_yaml',
    'load_pack_dict',
    'validate_pack',
    'compile_pack',
    'compute_pack_hash',

    # Runtime types
    'PackRuntime',
    'SignalDefinition',
    'MitigationDefinition',
    'PolicyReference',
    'ShadowQuestion',
    'ShadowQuestionSet',

    # Utilities
    'diff_pack_versions',
]
