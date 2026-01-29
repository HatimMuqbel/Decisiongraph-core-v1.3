"""
DecisionGraph Pack Module (v2.0)

Packs are domain-specific configurations that define:
- Predicate taxonomy (what predicates are valid)
- Payload schemas per CellType (what structured objects look like)
- Signal/mitigation/score rule definitions
- Policy references
- Shadow question sets
- Report templates

A Pack makes DecisionGraph work for any industry:
- AML pack for financial crime
- Insurance pack for claims
- Healthcare pack for clinical decisions
- HR pack for employment decisions

Core Principle: Same engine, different packs. Packs are versioned and immutable
once locked in genesis.

USAGE:
    from decisiongraph.pack import Pack, load_pack, validate_payload

    # Load a pack
    pack = load_pack("path/to/aml_pack.json")

    # Validate a payload against its schema
    validate_payload(pack, CellType.SIGNAL, payload)
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
import hashlib

from .cell import CellType


# =============================================================================
# EXCEPTIONS
# =============================================================================

class PackError(Exception):
    """Base exception for pack errors."""
    pass


class PackLoadError(PackError):
    """Raised when pack cannot be loaded."""
    pass


class PackValidationError(PackError):
    """Raised when pack definition is invalid."""
    pass


class SchemaValidationError(PackError):
    """Raised when payload doesn't match schema."""

    def __init__(self, message: str, path: str = "", expected: str = "", actual: str = ""):
        self.path = path
        self.expected = expected
        self.actual = actual
        super().__init__(message)


class PredicateError(PackError):
    """Raised when predicate is not in pack taxonomy."""
    pass


# =============================================================================
# SCHEMA TYPES
# =============================================================================

class SchemaType(str, Enum):
    """Supported schema field types."""
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    CELL_ID = "cell_id"          # 64-char hex string
    TIMESTAMP = "timestamp"      # ISO 8601 string
    HASH = "hash"                # 64-char hex string
    DECIMAL = "decimal"          # String-encoded decimal (e.g., "0.95")
    ENUM = "enum"                # One of specified values


# Pattern for cell_id and hash validation (64 hex chars)
HEX64_PATTERN = re.compile(r'^[a-f0-9]{64}$')

# Pattern for ISO 8601 timestamp
ISO_TIMESTAMP_PATTERN = re.compile(
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$'
)

# Pattern for string-encoded decimal (e.g., "0.95", "-1.5", "100.0")
DECIMAL_PATTERN = re.compile(r'^-?\d+(\.\d+)?$')


# =============================================================================
# SCHEMA DEFINITIONS
# =============================================================================

@dataclass
class FieldSchema:
    """Schema for a single field in a payload."""
    name: str
    type: SchemaType
    required: bool = True
    description: str = ""
    # For arrays: type of items
    items_type: Optional[SchemaType] = None
    # For enums: allowed values
    enum_values: Optional[List[str]] = None
    # For objects: nested schema (field name -> FieldSchema)
    properties: Optional[Dict[str, 'FieldSchema']] = None
    # Default value if not required and not present
    default: Optional[Any] = None

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        result = {
            "name": self.name,
            "type": self.type.value,
            "required": self.required,
        }
        if self.description:
            result["description"] = self.description
        if self.items_type:
            result["items_type"] = self.items_type.value
        if self.enum_values:
            result["enum_values"] = self.enum_values
        if self.properties:
            result["properties"] = {k: v.to_dict() for k, v in self.properties.items()}
        if self.default is not None:
            result["default"] = self.default
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'FieldSchema':
        """Deserialize from dict."""
        properties = None
        if "properties" in data:
            properties = {
                k: cls.from_dict(v) for k, v in data["properties"].items()
            }
        return cls(
            name=data["name"],
            type=SchemaType(data["type"]),
            required=data.get("required", True),
            description=data.get("description", ""),
            items_type=SchemaType(data["items_type"]) if data.get("items_type") else None,
            enum_values=data.get("enum_values"),
            properties=properties,
            default=data.get("default"),
        )


@dataclass
class PayloadSchema:
    """Schema for a CellType's structured payload."""
    cell_type: CellType
    schema_version: str
    description: str = ""
    fields: Dict[str, FieldSchema] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        return {
            "cell_type": self.cell_type.value,
            "schema_version": self.schema_version,
            "description": self.description,
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PayloadSchema':
        """Deserialize from dict."""
        return cls(
            cell_type=CellType(data["cell_type"]),
            schema_version=data["schema_version"],
            description=data.get("description", ""),
            fields={k: FieldSchema.from_dict(v) for k, v in data.get("fields", {}).items()},
        )


# =============================================================================
# PREDICATE TAXONOMY
# =============================================================================

@dataclass
class PredicateDefinition:
    """Definition of a valid predicate in the pack."""
    code: str                    # e.g., "signal.fired", "score.computed"
    description: str = ""
    cell_types: List[CellType] = field(default_factory=list)  # Which cell types can use this
    example_object: Optional[str] = None  # Example of what object looks like

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "description": self.description,
            "cell_types": [ct.value for ct in self.cell_types],
            "example_object": self.example_object,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PredicateDefinition':
        return cls(
            code=data["code"],
            description=data.get("description", ""),
            cell_types=[CellType(ct) for ct in data.get("cell_types", [])],
            example_object=data.get("example_object"),
        )


# =============================================================================
# PACK DEFINITION
# =============================================================================

@dataclass
class Pack:
    """
    A domain-specific pack definition.

    Packs define the "vocabulary" and "grammar" for a specific domain:
    - What predicates are valid
    - What payloads look like for each CellType
    - What signals/mitigations/scores are defined
    """
    pack_id: str                 # Unique identifier (e.g., "aml_fintrac_v1")
    name: str                    # Human-readable name
    version: str                 # Semantic version (e.g., "1.0.0")
    description: str = ""
    domain: str = ""             # e.g., "financial_crime", "insurance", "healthcare"

    # Predicate taxonomy
    predicates: Dict[str, PredicateDefinition] = field(default_factory=dict)

    # Payload schemas per CellType
    schemas: Dict[CellType, PayloadSchema] = field(default_factory=dict)

    # Pack metadata
    author: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        """Compute pack hash after initialization."""
        self._pack_hash: Optional[str] = None

    @property
    def pack_hash(self) -> str:
        """
        Compute deterministic hash of pack definition.

        This hash is stored in genesis to lock the pack version.
        """
        if self._pack_hash is None:
            # Canonical representation for hashing
            canonical = {
                "pack_id": self.pack_id,
                "version": self.version,
                "predicates": {k: v.to_dict() for k, v in sorted(self.predicates.items())},
                "schemas": {
                    ct.value: schema.to_dict()
                    for ct, schema in sorted(self.schemas.items(), key=lambda x: x[0].value)
                },
            }
            # Use canonical JSON (sorted keys, no whitespace)
            json_bytes = json.dumps(canonical, sort_keys=True, separators=(',', ':')).encode('utf-8')
            self._pack_hash = hashlib.sha256(json_bytes).hexdigest()
        return self._pack_hash

    def has_predicate(self, predicate: str) -> bool:
        """Check if predicate is defined in pack."""
        return predicate in self.predicates

    def has_schema(self, cell_type: CellType) -> bool:
        """Check if schema exists for cell type."""
        return cell_type in self.schemas

    def get_schema(self, cell_type: CellType) -> Optional[PayloadSchema]:
        """Get schema for cell type."""
        return self.schemas.get(cell_type)

    def to_dict(self) -> dict:
        """Serialize pack to dict for JSON storage."""
        return {
            "pack_id": self.pack_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "domain": self.domain,
            "predicates": {k: v.to_dict() for k, v in self.predicates.items()},
            "schemas": {ct.value: schema.to_dict() for ct, schema in self.schemas.items()},
            "author": self.author,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Pack':
        """Deserialize pack from dict."""
        pack = cls(
            pack_id=data["pack_id"],
            name=data["name"],
            version=data["version"],
            description=data.get("description", ""),
            domain=data.get("domain", ""),
            predicates={
                k: PredicateDefinition.from_dict(v)
                for k, v in data.get("predicates", {}).items()
            },
            schemas={
                CellType(ct): PayloadSchema.from_dict(schema)
                for ct, schema in data.get("schemas", {}).items()
            },
            author=data.get("author", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
        return pack

    def to_json(self, indent: int = 2) -> str:
        """Serialize pack to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> 'Pack':
        """Deserialize pack from JSON string."""
        return cls.from_dict(json.loads(json_str))


# =============================================================================
# PACK LOADING
# =============================================================================

def load_pack(path: Union[str, Path]) -> Pack:
    """
    Load a pack from a JSON file.

    Args:
        path: Path to pack JSON file

    Returns:
        Pack instance

    Raises:
        PackLoadError: If file cannot be read or parsed
        PackValidationError: If pack definition is invalid
    """
    path = Path(path)

    if not path.exists():
        raise PackLoadError(f"Pack file not found: {path}")

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise PackLoadError(f"Invalid JSON in pack file: {e}")
    except IOError as e:
        raise PackLoadError(f"Cannot read pack file: {e}")

    try:
        pack = Pack.from_dict(data)
    except (KeyError, ValueError) as e:
        raise PackValidationError(f"Invalid pack definition: {e}")

    # Validate pack structure
    _validate_pack_structure(pack)

    return pack


def _validate_pack_structure(pack: Pack) -> None:
    """
    Validate pack structure is internally consistent.

    Raises:
        PackValidationError: If pack is invalid
    """
    if not pack.pack_id:
        raise PackValidationError("Pack must have pack_id")
    if not pack.version:
        raise PackValidationError("Pack must have version")

    # Validate schemas reference valid cell types
    for cell_type, schema in pack.schemas.items():
        if schema.cell_type != cell_type:
            raise PackValidationError(
                f"Schema cell_type mismatch: key={cell_type.value}, schema={schema.cell_type.value}"
            )

    # Validate predicates reference valid cell types
    for pred_code, pred_def in pack.predicates.items():
        if pred_def.code != pred_code:
            raise PackValidationError(
                f"Predicate code mismatch: key={pred_code}, definition={pred_def.code}"
            )


# =============================================================================
# PAYLOAD VALIDATION
# =============================================================================

def validate_payload(
    pack: Pack,
    cell_type: CellType,
    payload: Dict[str, Any],
    strict: bool = True
) -> List[str]:
    """
    Validate a payload against its schema.

    Args:
        pack: Pack containing schema definitions
        cell_type: CellType of the payload
        payload: The structured payload to validate
        strict: If True, reject unknown fields. If False, allow extra fields.

    Returns:
        List of warning messages (empty if valid)

    Raises:
        SchemaValidationError: If payload doesn't match schema
    """
    schema = pack.get_schema(cell_type)
    if schema is None:
        if strict:
            raise SchemaValidationError(
                f"No schema defined for {cell_type.value} in pack {pack.pack_id}",
                path="",
                expected="schema definition",
                actual="none"
            )
        return [f"No schema for {cell_type.value}, skipping validation"]

    warnings = []

    # Check schema_version in payload
    if "schema_version" not in payload:
        warnings.append("Missing schema_version in payload")
    elif payload["schema_version"] != schema.schema_version:
        warnings.append(
            f"Schema version mismatch: payload={payload['schema_version']}, "
            f"pack={schema.schema_version}"
        )

    # Validate each field
    for field_name, field_schema in schema.fields.items():
        if field_name not in payload:
            if field_schema.required:
                raise SchemaValidationError(
                    f"Missing required field: {field_name}",
                    path=field_name,
                    expected=field_schema.type.value,
                    actual="missing"
                )
            continue

        _validate_field(payload[field_name], field_schema, field_name)

    # Check for unknown fields
    if strict:
        known_fields = set(schema.fields.keys()) | {"schema_version"}
        unknown = set(payload.keys()) - known_fields
        if unknown:
            raise SchemaValidationError(
                f"Unknown fields in payload: {unknown}",
                path="",
                expected=str(known_fields),
                actual=str(set(payload.keys()))
            )

    return warnings


def _validate_field(value: Any, schema: FieldSchema, path: str) -> None:
    """
    Validate a single field against its schema.

    Raises:
        SchemaValidationError: If field doesn't match schema
    """
    if value is None:
        if schema.required:
            raise SchemaValidationError(
                f"Field {path} is required but got null",
                path=path,
                expected=schema.type.value,
                actual="null"
            )
        return

    # Type-specific validation
    if schema.type == SchemaType.STRING:
        if not isinstance(value, str):
            raise SchemaValidationError(
                f"Field {path} must be string",
                path=path,
                expected="string",
                actual=type(value).__name__
            )

    elif schema.type == SchemaType.INTEGER:
        if not isinstance(value, int) or isinstance(value, bool):
            raise SchemaValidationError(
                f"Field {path} must be integer",
                path=path,
                expected="integer",
                actual=type(value).__name__
            )

    elif schema.type == SchemaType.BOOLEAN:
        if not isinstance(value, bool):
            raise SchemaValidationError(
                f"Field {path} must be boolean",
                path=path,
                expected="boolean",
                actual=type(value).__name__
            )

    elif schema.type == SchemaType.CELL_ID:
        if not isinstance(value, str) or not HEX64_PATTERN.match(value):
            raise SchemaValidationError(
                f"Field {path} must be 64-char hex cell_id",
                path=path,
                expected="64-char hex string",
                actual=str(value)[:32] + "..." if len(str(value)) > 32 else str(value)
            )

    elif schema.type == SchemaType.HASH:
        if not isinstance(value, str) or not HEX64_PATTERN.match(value):
            raise SchemaValidationError(
                f"Field {path} must be 64-char hex hash",
                path=path,
                expected="64-char hex string",
                actual=str(value)[:32] + "..." if len(str(value)) > 32 else str(value)
            )

    elif schema.type == SchemaType.TIMESTAMP:
        if not isinstance(value, str) or not ISO_TIMESTAMP_PATTERN.match(value):
            raise SchemaValidationError(
                f"Field {path} must be ISO 8601 timestamp",
                path=path,
                expected="ISO 8601 timestamp",
                actual=str(value)
            )

    elif schema.type == SchemaType.DECIMAL:
        if not isinstance(value, str) or not DECIMAL_PATTERN.match(value):
            raise SchemaValidationError(
                f"Field {path} must be string-encoded decimal",
                path=path,
                expected="string decimal (e.g., '0.95')",
                actual=str(value)
            )

    elif schema.type == SchemaType.ENUM:
        if schema.enum_values is None:
            raise SchemaValidationError(
                f"Enum field {path} has no enum_values defined",
                path=path,
                expected="enum_values list",
                actual="none"
            )
        if value not in schema.enum_values:
            raise SchemaValidationError(
                f"Field {path} must be one of {schema.enum_values}",
                path=path,
                expected=str(schema.enum_values),
                actual=str(value)
            )

    elif schema.type == SchemaType.ARRAY:
        if not isinstance(value, list):
            raise SchemaValidationError(
                f"Field {path} must be array",
                path=path,
                expected="array",
                actual=type(value).__name__
            )
        # Validate items if items_type specified
        if schema.items_type:
            for i, item in enumerate(value):
                item_schema = FieldSchema(
                    name=f"{path}[{i}]",
                    type=schema.items_type,
                    required=True
                )
                _validate_field(item, item_schema, f"{path}[{i}]")

    elif schema.type == SchemaType.OBJECT:
        if not isinstance(value, dict):
            raise SchemaValidationError(
                f"Field {path} must be object",
                path=path,
                expected="object",
                actual=type(value).__name__
            )
        # Validate nested properties if defined
        if schema.properties:
            for prop_name, prop_schema in schema.properties.items():
                if prop_name not in value:
                    if prop_schema.required:
                        raise SchemaValidationError(
                            f"Missing required property: {path}.{prop_name}",
                            path=f"{path}.{prop_name}",
                            expected=prop_schema.type.value,
                            actual="missing"
                        )
                    continue
                _validate_field(value[prop_name], prop_schema, f"{path}.{prop_name}")


def validate_predicate(pack: Pack, predicate: str, cell_type: CellType) -> None:
    """
    Validate predicate is defined in pack and allowed for cell type.

    Args:
        pack: Pack containing predicate definitions
        predicate: Predicate code to validate
        cell_type: CellType using this predicate

    Raises:
        PredicateError: If predicate is invalid
    """
    if not pack.has_predicate(predicate):
        raise PredicateError(
            f"Predicate '{predicate}' not defined in pack {pack.pack_id}"
        )

    pred_def = pack.predicates[predicate]
    if pred_def.cell_types and cell_type not in pred_def.cell_types:
        raise PredicateError(
            f"Predicate '{predicate}' not allowed for {cell_type.value}. "
            f"Allowed: {[ct.value for ct in pred_def.cell_types]}"
        )


# =============================================================================
# BUILT-IN UNIVERSAL SCHEMAS
# =============================================================================

def create_signal_schema(version: str = "1.0") -> PayloadSchema:
    """Create the universal SIGNAL payload schema."""
    return PayloadSchema(
        cell_type=CellType.SIGNAL,
        schema_version=version,
        description="Signal fired by a detection rule",
        fields={
            "code": FieldSchema(
                name="code",
                type=SchemaType.STRING,
                required=True,
                description="Signal code (e.g., HIGH_VALUE_CRYPTO)"
            ),
            "severity": FieldSchema(
                name="severity",
                type=SchemaType.ENUM,
                required=True,
                enum_values=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                description="Signal severity level"
            ),
            "trigger_facts": FieldSchema(
                name="trigger_facts",
                type=SchemaType.ARRAY,
                required=True,
                items_type=SchemaType.CELL_ID,
                description="Cell IDs of facts that triggered this signal"
            ),
            "policy_refs": FieldSchema(
                name="policy_refs",
                type=SchemaType.ARRAY,
                required=False,
                items_type=SchemaType.CELL_ID,
                description="Cell IDs of policy references"
            ),
        }
    )


def create_mitigation_schema(version: str = "1.0") -> PayloadSchema:
    """Create the universal MITIGATION payload schema."""
    return PayloadSchema(
        cell_type=CellType.MITIGATION,
        schema_version=version,
        description="Mitigating factor that reduces risk",
        fields={
            "code": FieldSchema(
                name="code",
                type=SchemaType.STRING,
                required=True,
                description="Mitigation code (e.g., MF_TXN_002)"
            ),
            "weight": FieldSchema(
                name="weight",
                type=SchemaType.DECIMAL,
                required=True,
                description="Weight to apply (e.g., '-0.50')"
            ),
            "anchors": FieldSchema(
                name="anchors",
                type=SchemaType.ARRAY,
                required=True,
                items_type=SchemaType.CELL_ID,
                description="Cell IDs of supporting facts/evidence"
            ),
            "applies_to_signals": FieldSchema(
                name="applies_to_signals",
                type=SchemaType.ARRAY,
                required=True,
                items_type=SchemaType.CELL_ID,
                description="Cell IDs of signals this mitigates"
            ),
        }
    )


def create_score_schema(version: str = "1.0") -> PayloadSchema:
    """Create the universal SCORE payload schema."""
    return PayloadSchema(
        cell_type=CellType.SCORE,
        schema_version=version,
        description="Computed risk score",
        fields={
            "inherent_score": FieldSchema(
                name="inherent_score",
                type=SchemaType.DECIMAL,
                required=True,
                description="Base score before mitigations"
            ),
            "mitigation_sum": FieldSchema(
                name="mitigation_sum",
                type=SchemaType.DECIMAL,
                required=True,
                description="Sum of mitigation weights"
            ),
            "residual_score": FieldSchema(
                name="residual_score",
                type=SchemaType.DECIMAL,
                required=True,
                description="Final score after mitigations"
            ),
            "threshold_gate": FieldSchema(
                name="threshold_gate",
                type=SchemaType.STRING,
                required=True,
                description="Threshold gate result (e.g., CLEAR_AND_CLOSE)"
            ),
        }
    )


def create_verdict_schema(version: str = "1.0") -> PayloadSchema:
    """Create the universal VERDICT payload schema."""
    return PayloadSchema(
        cell_type=CellType.VERDICT,
        schema_version=version,
        description="Final verdict for a case",
        fields={
            "verdict": FieldSchema(
                name="verdict",
                type=SchemaType.STRING,
                required=True,
                description="Verdict code (e.g., CLEAR_AND_CLOSE, ESCALATE)"
            ),
            "rationale_fact_refs": FieldSchema(
                name="rationale_fact_refs",
                type=SchemaType.ARRAY,
                required=True,
                items_type=SchemaType.CELL_ID,
                description="Cell IDs supporting the verdict"
            ),
            "auto_archive_permitted": FieldSchema(
                name="auto_archive_permitted",
                type=SchemaType.BOOLEAN,
                required=True,
                description="Whether case can be auto-archived"
            ),
        }
    )


def create_justification_schema(version: str = "1.0") -> PayloadSchema:
    """Create the universal JUSTIFICATION (shadow node) payload schema."""
    return PayloadSchema(
        cell_type=CellType.JUSTIFICATION,
        schema_version=version,
        description="Shadow node answers for audit trail",
        fields={
            "target_cell_id": FieldSchema(
                name="target_cell_id",
                type=SchemaType.CELL_ID,
                required=True,
                description="Cell ID being justified"
            ),
            "question_set_id": FieldSchema(
                name="question_set_id",
                type=SchemaType.STRING,
                required=True,
                description="Question set version (e.g., universal.v1)"
            ),
            "answers": FieldSchema(
                name="answers",
                type=SchemaType.OBJECT,
                required=True,
                description="Structured answers to shadow questions",
                properties={
                    "basis_fact_ids": FieldSchema(
                        name="basis_fact_ids",
                        type=SchemaType.ARRAY,
                        required=True,
                        items_type=SchemaType.CELL_ID,
                        description="Which facts triggered this?"
                    ),
                    "evidence_sufficient": FieldSchema(
                        name="evidence_sufficient",
                        type=SchemaType.BOOLEAN,
                        required=True,
                        description="Is evidence sufficient?"
                    ),
                    "missing_evidence": FieldSchema(
                        name="missing_evidence",
                        type=SchemaType.ARRAY,
                        required=True,
                        items_type=SchemaType.STRING,
                        description="What evidence is missing?"
                    ),
                    "counterfactuals": FieldSchema(
                        name="counterfactuals",
                        type=SchemaType.ARRAY,
                        required=True,
                        items_type=SchemaType.STRING,
                        description="What would falsify this?"
                    ),
                    "policy_refs": FieldSchema(
                        name="policy_refs",
                        type=SchemaType.ARRAY,
                        required=True,
                        items_type=SchemaType.CELL_ID,
                        description="Which policy refs apply?"
                    ),
                    "needs_human_review": FieldSchema(
                        name="needs_human_review",
                        type=SchemaType.BOOLEAN,
                        required=True,
                        description="Does this need human review?"
                    ),
                    "review_reason": FieldSchema(
                        name="review_reason",
                        type=SchemaType.STRING,
                        required=False,
                        description="Why human review is needed"
                    ),
                }
            ),
        }
    )


def create_report_run_schema(version: str = "1.0") -> PayloadSchema:
    """Create the universal REPORT_RUN payload schema."""
    return PayloadSchema(
        cell_type=CellType.REPORT_RUN,
        schema_version=version,
        description="Frozen report generation run",
        fields={
            "case_id": FieldSchema(
                name="case_id",
                type=SchemaType.STRING,
                required=True,
                description="Case identifier"
            ),
            "pack_id": FieldSchema(
                name="pack_id",
                type=SchemaType.STRING,
                required=True,
                description="Pack used for this report"
            ),
            "pack_version": FieldSchema(
                name="pack_version",
                type=SchemaType.STRING,
                required=True,
                description="Pack version"
            ),
            "anchor_head_cell_id": FieldSchema(
                name="anchor_head_cell_id",
                type=SchemaType.CELL_ID,
                required=True,
                description="Chain head at time of report"
            ),
            "included_cell_ids": FieldSchema(
                name="included_cell_ids",
                type=SchemaType.ARRAY,
                required=True,
                items_type=SchemaType.CELL_ID,
                description="All cells included in report"
            ),
            "template_id": FieldSchema(
                name="template_id",
                type=SchemaType.STRING,
                required=True,
                description="Report template identifier"
            ),
            "template_version": FieldSchema(
                name="template_version",
                type=SchemaType.STRING,
                required=True,
                description="Report template version"
            ),
            "rendered_artifact_hash": FieldSchema(
                name="rendered_artifact_hash",
                type=SchemaType.HASH,
                required=True,
                description="SHA-256 of rendered report bytes"
            ),
            "rendered_at": FieldSchema(
                name="rendered_at",
                type=SchemaType.TIMESTAMP,
                required=True,
                description="When report was rendered"
            ),
        }
    )


def create_judgment_schema(version: str = "1.0") -> PayloadSchema:
    """Create the universal JUDGMENT payload schema."""
    return PayloadSchema(
        cell_type=CellType.JUDGMENT,
        schema_version=version,
        description="Human or system judgment/signoff",
        fields={
            "action": FieldSchema(
                name="action",
                type=SchemaType.ENUM,
                required=True,
                enum_values=["APPROVE", "REJECT", "ESCALATE", "DEFER", "OVERRIDE"],
                description="Judgment action"
            ),
            "tier": FieldSchema(
                name="tier",
                type=SchemaType.INTEGER,
                required=True,
                description="Approval tier (1, 2, 3...)"
            ),
            "reviewer": FieldSchema(
                name="reviewer",
                type=SchemaType.STRING,
                required=True,
                description="Reviewer identifier"
            ),
            "target_cell_id": FieldSchema(
                name="target_cell_id",
                type=SchemaType.CELL_ID,
                required=True,
                description="Cell being judged"
            ),
            "rationale": FieldSchema(
                name="rationale",
                type=SchemaType.STRING,
                required=False,
                description="Reason for judgment"
            ),
        }
    )


def create_universal_pack(pack_id: str = "universal", version: str = "1.0.0") -> Pack:
    """
    Create a universal pack with all standard schemas.

    This is the base pack that works for any domain.
    Domain-specific packs extend this with additional predicates and schemas.
    """
    pack = Pack(
        pack_id=pack_id,
        name="Universal Pack",
        version=version,
        description="Base pack with universal schemas for all domains",
        domain="universal",
        schemas={
            CellType.SIGNAL: create_signal_schema(),
            CellType.MITIGATION: create_mitigation_schema(),
            CellType.SCORE: create_score_schema(),
            CellType.VERDICT: create_verdict_schema(),
            CellType.JUSTIFICATION: create_justification_schema(),
            CellType.REPORT_RUN: create_report_run_schema(),
            CellType.JUDGMENT: create_judgment_schema(),
        },
        predicates={
            "signal.fired": PredicateDefinition(
                code="signal.fired",
                description="A detection signal was triggered",
                cell_types=[CellType.SIGNAL]
            ),
            "mitigation.applied": PredicateDefinition(
                code="mitigation.applied",
                description="A mitigating factor was applied",
                cell_types=[CellType.MITIGATION]
            ),
            "score.computed": PredicateDefinition(
                code="score.computed",
                description="A risk score was computed",
                cell_types=[CellType.SCORE]
            ),
            "verdict.rendered": PredicateDefinition(
                code="verdict.rendered",
                description="A verdict was rendered",
                cell_types=[CellType.VERDICT]
            ),
            "justification.recorded": PredicateDefinition(
                code="justification.recorded",
                description="Shadow node justification recorded",
                cell_types=[CellType.JUSTIFICATION]
            ),
            "report.generated": PredicateDefinition(
                code="report.generated",
                description="A report was generated",
                cell_types=[CellType.REPORT_RUN]
            ),
            "judgment.recorded": PredicateDefinition(
                code="judgment.recorded",
                description="A human/system judgment was recorded",
                cell_types=[CellType.JUDGMENT]
            ),
        }
    )
    return pack


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Exceptions
    'PackError',
    'PackLoadError',
    'PackValidationError',
    'SchemaValidationError',
    'PredicateError',
    # Schema types
    'SchemaType',
    'FieldSchema',
    'PayloadSchema',
    'PredicateDefinition',
    # Pack
    'Pack',
    # Loading
    'load_pack',
    # Validation
    'validate_payload',
    'validate_predicate',
    # Built-in schemas
    'create_signal_schema',
    'create_mitigation_schema',
    'create_score_schema',
    'create_verdict_schema',
    'create_justification_schema',
    'create_report_run_schema',
    'create_judgment_schema',
    'create_universal_pack',
]
