"""
Domain Registry — v3 Precedent Engine data structures.

Defines FieldDefinition, ComparabilityGate, ConfidenceLevel, and DomainRegistry.
These structures drive all three layers of the v3 comparability model:
  Layer 1 (Comparability Gate) reads comparability_gates
  Layer 2 (Causal Factor Alignment) reads fields with typed comparisons
  Layer 3 (Governed Confidence) reads confidence thresholds and critical_fields

The engine is domain-agnostic — it reads the registry and adapts.
Banking AML is the first concrete domain (see banking_domain.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class FieldType(str, Enum):
    """Data type of a registry field."""
    BOOLEAN = "BOOLEAN"
    CATEGORICAL = "CATEGORICAL"
    NUMERIC = "NUMERIC"
    ORDINAL = "ORDINAL"
    SET = "SET"


class ComparisonFn(str, Enum):
    """Comparison function used for similarity scoring."""
    EXACT = "EXACT"
    EQUIVALENCE_CLASS = "EQUIVALENCE_CLASS"
    DISTANCE_DECAY = "DISTANCE_DECAY"
    STEP = "STEP"
    JACCARD = "JACCARD"


class FieldTier(str, Enum):
    """Field tier — determines role in the three-layer model."""
    STRUCTURAL = "STRUCTURAL"      # Layer 1: comparability gate filter
    BEHAVIORAL = "BEHAVIORAL"      # Layer 2: scoring (2x when driver)
    CONTEXTUAL = "CONTEXTUAL"      # Layer 2: scoring (1x, stabilizer)


class ConfidenceLevel(str, Enum):
    """Governed confidence levels (ordered worst to best)."""
    NONE = "NONE"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"

    def __lt__(self, other: ConfidenceLevel) -> bool:
        return _LEVEL_ORDER[self] < _LEVEL_ORDER[other]

    def __le__(self, other: ConfidenceLevel) -> bool:
        return _LEVEL_ORDER[self] <= _LEVEL_ORDER[other]

    def __gt__(self, other: ConfidenceLevel) -> bool:
        return _LEVEL_ORDER[self] > _LEVEL_ORDER[other]

    def __ge__(self, other: ConfidenceLevel) -> bool:
        return _LEVEL_ORDER[self] >= _LEVEL_ORDER[other]


_LEVEL_ORDER: dict[ConfidenceLevel, int] = {
    ConfidenceLevel.NONE: 0,
    ConfidenceLevel.LOW: 1,
    ConfidenceLevel.MODERATE: 2,
    ConfidenceLevel.HIGH: 3,
    ConfidenceLevel.VERY_HIGH: 4,
}


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FieldDefinition:
    """A single field in the domain registry with comparison metadata.

    Drives Layer 2 causal factor alignment: the engine reads this to
    know HOW to compare each field between case and precedent.
    """
    name: str                                       # canonical dot-path: "customer.type"
    label: str                                      # human-readable: "Customer entity type"
    type: FieldType                                 # BOOLEAN | CATEGORICAL | NUMERIC | ORDINAL | SET
    comparison: ComparisonFn                        # EXACT | EQUIVALENCE_CLASS | DISTANCE_DECAY | STEP | JACCARD
    weight: float                                   # 0.0–1.0, domain-specific importance
    tier: FieldTier                                 # STRUCTURAL | BEHAVIORAL | CONTEXTUAL
    required: bool = True                           # must be present for valid comparison
    critical: bool = False                          # absence caps confidence at LOW
    equivalence_classes: dict[str, list[str]] = field(default_factory=dict)
    ordered_values: list[str] = field(default_factory=list)   # for STEP/ORDINAL comparison
    max_distance: int = 4                           # for DISTANCE_DECAY comparison
    domain: str = "banking_aml"

    def __post_init__(self) -> None:
        if not 0.0 <= self.weight <= 1.0:
            raise ValueError(f"weight must be 0.0–1.0, got {self.weight} for {self.name}")
        if self.comparison == ComparisonFn.EQUIVALENCE_CLASS and not self.equivalence_classes:
            raise ValueError(f"EQUIVALENCE_CLASS comparison requires equivalence_classes for {self.name}")
        if self.comparison == ComparisonFn.STEP and not self.ordered_values:
            raise ValueError(f"STEP comparison requires ordered_values for {self.name}")


@dataclass(frozen=True)
class ComparabilityGate:
    """A Layer 1 gate that filters incomparable precedents.

    Each gate defines equivalence classes for a field. Values within the
    same class are treated as identical for gating purposes.
    """
    field: str                                      # field name (may be a virtual field like "jurisdiction_regime")
    equivalence_classes: dict[str, list[str]]       # class_name -> [raw values...]

    def classify(self, value: Any) -> str | None:
        """Return the equivalence class name for a value, or None if not found."""
        if value is None:
            return None
        v = str(value).lower().strip()
        for class_name, members in self.equivalence_classes.items():
            if v in [str(m).lower().strip() for m in members]:
                return class_name
        return None

    def broadest_class(self) -> str:
        """Return the class with the most members (fallback for missing fields)."""
        return max(self.equivalence_classes, key=lambda k: len(self.equivalence_classes[k]))


@dataclass
class DomainRegistry:
    """Complete domain configuration for the v3 precedent engine.

    The comparison engine reads this registry and adapts to any domain.
    """
    domain: str                                     # "banking_aml"
    version: str                                    # "3.0"
    fields: dict[str, FieldDefinition]              # canonical_name -> FieldDefinition
    comparability_gates: list[ComparabilityGate]    # Layer 1 gates
    similarity_floor: float = 0.60                  # default minimum similarity threshold
    similarity_floor_overrides: dict[str, float] = field(default_factory=dict)  # typology -> floor
    pool_minimum: int = 5                           # min precedents for reliable confidence
    critical_fields: frozenset[str] = field(default_factory=frozenset)  # absence caps confidence at LOW
    disposition_mapping: dict[str, str] = field(default_factory=dict)   # raw -> canonical disposition
    reporting_mapping: dict[str, str] = field(default_factory=dict)     # raw -> canonical reporting
    basis_mapping: dict[str, str] = field(default_factory=dict)         # raw -> canonical basis

    def get_gate_fields(self) -> list[str]:
        """Return the list of field names used as comparability gates."""
        return [gate.field for gate in self.comparability_gates]

    def get_structural_fields(self) -> list[FieldDefinition]:
        """Fields with tier STRUCTURAL (used in Layer 1)."""
        return [f for f in self.fields.values() if f.tier == FieldTier.STRUCTURAL]

    def get_behavioral_fields(self) -> list[FieldDefinition]:
        """Fields with tier BEHAVIORAL (scored with driver awareness in Layer 2)."""
        return [f for f in self.fields.values() if f.tier == FieldTier.BEHAVIORAL]

    def get_contextual_fields(self) -> list[FieldDefinition]:
        """Fields with tier CONTEXTUAL (scored at 1x weight in Layer 2)."""
        return [f for f in self.fields.values() if f.tier == FieldTier.CONTEXTUAL]

    def get_scoring_fields(self) -> list[FieldDefinition]:
        """All fields that participate in Layer 2 scoring (BEHAVIORAL + CONTEXTUAL)."""
        return [
            f for f in self.fields.values()
            if f.tier in (FieldTier.BEHAVIORAL, FieldTier.CONTEXTUAL)
        ]

    def get_similarity_floor_for_typology(self, typology: str) -> float:
        """Return the similarity floor for a given typology, or the default."""
        return self.similarity_floor_overrides.get(typology, self.similarity_floor)

    def total_weight(self) -> float:
        """Sum of all scoring field weights (for normalization)."""
        return sum(f.weight for f in self.get_scoring_fields())


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "FieldType",
    "ComparisonFn",
    "FieldTier",
    "ConfidenceLevel",
    "FieldDefinition",
    "ComparabilityGate",
    "DomainRegistry",
]
